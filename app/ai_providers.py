"""Provider registry for TigerCapture AI edit planning.

This layer is deliberately thin. It describes which AI sources are available
without letting any provider mutate a project directly. Real providers must
return validated ``EditPlan`` JSON and the editor decides whether to preview or
apply it.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import replace
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import urllib.error
from typing import Any

from app.ai_edit_plan import (
    AI_EDIT_PLAN_SCHEMA_V1,
    ALLOWED_OPERATION_TYPES,
    EditPlan,
    make_operation_id,
    validate_edit_plan_json,
)


QWEN_LOCAL_PROVIDER_ID = "qwen_local"
QWEN_LOCAL_MANIFEST: dict[str, Any] = {
    "provider_id": QWEN_LOCAL_PROVIDER_ID,
    "model_family": "Qwen3",
    "model_size": "1.7B",
    "quantization": "Q8_0",
    "license": "Apache-2.0",
    "mode": "local_bundled_optional_download",
    "model_ref": "Qwen/Qwen3-1.7B-GGUF:Q8_0",
    "model_page": "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF",
}

PROVIDER_DISPLAY_ORDER = (
    "qwen_local",
    "codex_mcp",
    "claude_mcp",
    "local_llm",
    "manual_json",
    "rule_based",
)

SUPPORTED_AI_PROVIDERS = PROVIDER_DISPLAY_ORDER

DEFAULT_PROVIDER_FALLBACK_ORDER = (
    "qwen_local",
    "local_llm",
    "codex_mcp",
    "claude_mcp",
    "rule_based",
)

AI_PROVIDER_SETTINGS_ORG = "TigerCapture"
AI_PROVIDER_SETTINGS_APP = "TigerCapture"
AI_PROVIDER_SETTINGS_KEY = "ai/provider"
AI_QWEN_MODEL_PATH_SETTINGS_KEY = "ai/qwen/model_path"
AI_QWEN_RUNNER_COMMAND_SETTINGS_KEY = "ai/qwen/runner_command"
AI_QWEN_ENDPOINT_SETTINGS_KEY = "ai/qwen/endpoint"
AI_QWEN_EXECUTOR_LAST_OK_SETTINGS_KEY = "ai/qwen/executor_last_ok"
AI_QWEN_EXECUTOR_LAST_ERROR_SETTINGS_KEY = "ai/qwen/executor_last_error"
AI_CLAUDE_MCP_ENABLED_SETTINGS_KEY = "ai/claude_mcp/enabled"
AI_CLAUDE_MCP_COMMAND_SETTINGS_KEY = "ai/claude_mcp/command"
AI_CLAUDE_CLI_COMMAND_SETTINGS_KEY = "ai/claude/cli_command"
AI_CLAUDE_EXECUTOR_LAST_OK_SETTINGS_KEY = "ai/claude/executor_last_ok"
AI_CLAUDE_EXECUTOR_LAST_ERROR_SETTINGS_KEY = "ai/claude/executor_last_error"
AI_LOCAL_LLM_COMMAND_SETTINGS_KEY = "ai/local_llm/command"
AI_CLAUDE_DIRECT_EXECUTOR_ENV = "TIGERCAPTURE_CLAUDE_DIRECT_EXECUTOR"
AI_CLAUDE_MODEL_ENV = "TIGERCAPTURE_CLAUDE_MODEL"
AI_CLAUDE_EFFORT_ENV = "TIGERCAPTURE_CLAUDE_EFFORT"
QWEN_DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1"
QWEN_LLAMA_SERVER_COMMAND = (
    f"llama-server -hf {QWEN_LOCAL_MANIFEST['model_ref']} "
    "--host 127.0.0.1 --port 8080 --alias qwen3-1.7b-q8"
)
EXECUTOR_PENDING_MESSAGE = "Provider setup/selection is ready; generation uses rule-based fallback until executor is wired."
QWEN_EXECUTOR_TIMEOUT_SECONDS = 90
CLAUDE_EXECUTOR_TIMEOUT_SECONDS = 120
LOCAL_LLM_EXECUTOR_TIMEOUT_SECONDS = 120
CODEX_EXECUTOR_TIMEOUT_SECONDS = 120
PROVIDER_USER_LABELS = {
    "qwen_local": "기본 무료 AI",
    "codex_mcp": "Codex",
    "claude_mcp": "Claude",
    "local_llm": "로컬 LLM",
    "manual_json": "JSON 가져오기",
    "rule_based": "규칙 모드",
}


def default_mcp_server_command_parts() -> tuple[str, str, str]:
    script = Path(__file__).resolve().parents[1] / "tools" / "automation_mcp_server.py"
    return sys.executable, str(script), "--stdio"


def default_mcp_server_command() -> str:
    python_exe, script, stdio_arg = default_mcp_server_command_parts()
    return f'"{python_exe}" "{script}" {stdio_arg}'


@dataclass(frozen=True)
class AIProviderStatus:
    id: str
    label: str
    available: bool
    mode: str
    requires_network: bool = False
    configured: bool = False
    reason: str = ""
    command: str = ""
    setup_needed: bool = False
    setup_state: str = ""
    manifest: Mapping[str, Any] | None = None
    endpoint: str = ""
    model_path: str = ""
    cli_command: str = ""
    executor_wired: bool = False
    direct_generation_enabled: bool = True
    generation_fallback_provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "available": bool(self.available),
            "mode": self.mode,
            "requires_network": bool(self.requires_network),
            "configured": bool(self.configured),
            "reason": self.reason,
            "command": self.command,
            "setup_needed": bool(self.setup_needed),
            "setup_state": self.setup_state or ("ready" if self.available else "unavailable"),
            "manifest": dict(self.manifest or {}),
            "endpoint": self.endpoint,
            "model_path": self.model_path,
            "cli_command": self.cli_command,
            "executor_wired": bool(self.executor_wired),
            "direct_generation_enabled": bool(self.direct_generation_enabled),
            "generation_fallback_provider": self.generation_fallback_provider,
        }


@dataclass(frozen=True)
class AIProviderPlanResult:
    ok: bool
    provider: str
    plan: EditPlan | None = None
    reason: str = ""
    metadata: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "provider": self.provider,
            "plan": self.plan.to_dict() if self.plan is not None else None,
            "reason": self.reason,
            "metadata": dict(self.metadata or {}),
        }


def _env(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def _normalized_provider_id(provider_id: str | None) -> str:
    value = str(provider_id or "").strip()
    return value if value in SUPPORTED_AI_PROVIDERS else ""


def provider_user_label(provider_id: str | None) -> str:
    normalized = _normalized_provider_id(provider_id)
    return PROVIDER_USER_LABELS.get(normalized, str(provider_id or "").strip() or "AI")


def is_ai_provider_status_prompt(prompt: str, provider_id: str | None = None) -> bool:
    """Return True when the AI command is a connection/status question, not an edit request."""
    text = " ".join(str(prompt or "").strip().casefold().split())
    if not text:
        return False
    edit_terms = (
        "자막",
        "대본",
        "컷",
        "잘라",
        "삭제",
        "편집",
        "배치",
        "불러",
        "가져",
        "미디어",
        "트랙",
        "줌",
        "효과",
        "블러",
        "색보정",
        "렌더",
        "내보내",
        "export",
        "subtitle",
        "caption",
        "cut",
        "trim",
        "import",
        "media",
        "timeline",
        "zoom",
        "effect",
        "render",
    )
    if any(term in text for term in edit_terms):
        return False
    provider_terms = (
        "ai",
        "llm",
        "클로드",
        "claude",
        "코덱스",
        "codex",
        "qwen",
        "무료 ai",
        "로컬 ai",
        "로컬 llm",
        "모델",
        "provider",
    )
    status_terms = (
        "연결",
        "연결됐",
        "연결 됐",
        "상태",
        "사용 가능",
        "가능",
        "작동",
        "동작",
        "테스트",
        "로그인",
        "왜",
        "뭐야",
        "안돼",
        "안되",
        "안됨",
        "되냐",
        "되나",
        "됐어",
        "connected",
        "connection",
        "status",
        "available",
        "ready",
        "working",
        "test",
        "login",
        "why",
    )
    explicit_provider = any(term in text for term in provider_terms)
    selected_provider = _normalized_provider_id(provider_id) in {
        QWEN_LOCAL_PROVIDER_ID,
        "codex_mcp",
        "claude_mcp",
        "local_llm",
    }
    return bool((explicit_provider or selected_provider) and any(term in text for term in status_terms))


def provider_state_label(row: Mapping[str, Any] | None) -> str:
    data = dict(row or {})
    provider_id = str(data.get("id") or "")
    if provider_id == "rule_based":
        return "항상 사용"
    if provider_id == "manual_json":
        return "가져오기"
    if data.get("setup_state") == "executor_failed":
        return "확인 필요"
    if provider_id == "claude_mcp":
        if data.get("available") and data.get("direct_generation_enabled"):
            return "직접 생성 가능"
        if data.get("available") and data.get("cli_command"):
            return "터미널 가능"
        if data.get("available"):
            return "MCP 등록됨"
    if data.get("available") and data.get("executor_wired"):
        return "사용 가능"
    if provider_id in {"claude_mcp", "codex_mcp"} and data.get("available"):
        return "MCP 등록됨"
    if data.get("available"):
        return "서버 연결됨"
    if data.get("setup_needed"):
        return "설치 필요"
    if not data.get("configured"):
        return "설정 필요"
    return "사용 불가"


def provider_interaction_model(provider_id: str | None, row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return user-facing interaction copy for an AI provider.

    The app has two very different AI surfaces: direct EditPlan generation and
    terminal/MCP handoff. Keeping that distinction explicit prevents Claude or
    local runners from feeling like a broken subtitle form.
    """
    provider = _normalized_provider_id(provider_id) or "rule_based"
    data = dict(row or {})
    state = provider_state_label({"id": provider, **data})
    available = bool(data.get("available"))
    executor_wired = bool(data.get("executor_wired"))
    if provider == "claude_mcp":
        direct_enabled = bool(data.get("direct_generation_enabled"))
        return {
            "provider_id": provider,
            "surface": "direct_editplan" if direct_enabled else "terminal_handoff",
            "state": state,
            "run_label": "Plan 생성" if direct_enabled else "Claude CLI 열기",
            "review_label": "Plan 검토",
            "setup_label": "Claude 연결",
            "placeholder": "Claude Code에 넘길 Tiger Studio 작업 지시 입력...",
            "summary": (
                (
                    "Claude 직접 Plan 생성이 켜져 있습니다. 그래도 프로젝트 적용은 Review에서 검토 후 진행합니다."
                    if direct_enabled
                    else "Claude Code 터미널을 열어 대화합니다. 앱 안의 Review는 Claude가 만든 Plan을 검토/적용하는 곳입니다."
                )
                if available
                else "Claude Code 터미널 연결이 필요합니다. 설정에서 Claude CLI와 tiger-studio MCP를 확인하세요."
            ),
            "can_direct_generate": direct_enabled,
            "opens_terminal": not direct_enabled,
        }
    if provider == "local_llm":
        return {
            "provider_id": provider,
            "surface": "local_command",
            "state": state,
            "run_label": "로컬 LLM 실행" if executor_wired else "로컬 LLM 설정",
            "review_label": "Plan 검토",
            "setup_label": "로컬 LLM 설정",
            "placeholder": "로컬 LLM에 넘길 편집 명령 입력...",
            "summary": (
                "설정된 로컬 LLM 명령으로 EditPlan JSON을 만들고, Review에서 검토 후 적용합니다."
                if executor_wired
                else "로컬 LLM 실행 명령이 아직 없습니다. 설정에서 실행 명령을 연결하세요."
            ),
            "can_direct_generate": bool(executor_wired),
            "opens_terminal": False,
        }
    if provider == QWEN_LOCAL_PROVIDER_ID:
        return {
            "provider_id": provider,
            "surface": "local_server",
            "state": state,
            "run_label": "무료 AI 실행" if available else "무료 AI 설치",
            "review_label": "Plan 검토",
            "setup_label": "무료 AI 설치/연결",
            "placeholder": "기본 무료 AI에 전달할 편집 명령 입력...",
            "summary": (
                "기본 무료 AI가 편집 명령을 직접 해석하고, Review에서 검토 후 적용합니다."
                if executor_wired
                else "무료 AI 설치 또는 서버 시작이 필요합니다. 준비 전에는 안전한 규칙 모드로 플랜을 만듭니다."
            ),
            "can_direct_generate": bool(executor_wired),
            "opens_terminal": False,
        }
    if provider == "codex_mcp":
        return {
            "provider_id": provider,
            "surface": "terminal_or_executor",
            "state": state,
            "run_label": "Codex 연결 안내" if not executor_wired else "Codex 실행",
            "review_label": "Plan 검토",
            "setup_label": "Codex 연결",
            "placeholder": "Codex에 넘길 Tiger Studio 작업 지시 입력...",
            "summary": (
                "Codex executor가 EditPlan JSON을 만들고, Review에서 검토 후 적용합니다."
                if executor_wired
                else "Codex는 MCP/터미널 handoff 또는 executor 명령 설정이 필요합니다."
            ),
            "can_direct_generate": bool(executor_wired),
            "opens_terminal": not bool(executor_wired),
        }
    if provider == "manual_json":
        return {
            "provider_id": provider,
            "surface": "manual_json",
            "state": state,
            "run_label": "JSON 검토",
            "review_label": "Plan 검토",
            "setup_label": "JSON 안내",
            "placeholder": "외부에서 만든 EditPlan JSON 또는 요청 메모 입력...",
            "summary": "외부에서 만든 EditPlan JSON을 Review에 올려 검증 후 적용합니다.",
            "can_direct_generate": False,
            "opens_terminal": False,
        }
    return {
        "provider_id": provider,
        "surface": "rule_based",
        "state": state,
        "run_label": "규칙 Plan 생성",
        "review_label": "Plan 검토",
        "setup_label": "규칙 모드 안내",
        "placeholder": "내장 규칙으로 만들 편집 명령 입력...",
        "summary": "오프라인 내장 규칙으로 안전한 편집 Plan을 만들고, Review에서 확인 후 적용합니다.",
        "can_direct_generate": True,
        "opens_terminal": False,
    }


def _provider_settings() -> Any | None:
    try:
        from PySide6.QtCore import QSettings

        return QSettings(AI_PROVIDER_SETTINGS_ORG, AI_PROVIDER_SETTINGS_APP)
    except Exception:
        return None


def saved_ai_provider_id(settings: Any | None = None) -> str:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return ""
    try:
        return _normalized_provider_id(str(store.value(AI_PROVIDER_SETTINGS_KEY, "") or ""))
    except Exception:
        return ""


def save_ai_provider_preference(provider_id: str, settings: Any | None = None) -> bool:
    normalized = _normalized_provider_id(provider_id)
    if not normalized:
        return False
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return False
    try:
        store.setValue(AI_PROVIDER_SETTINGS_KEY, normalized)
        store.sync()
        return True
    except Exception:
        return False


def saved_qwen_config(settings: Any | None = None) -> dict[str, str]:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return {"model_path": "", "runner_command": "", "endpoint": ""}
    try:
        return {
            "model_path": str(store.value(AI_QWEN_MODEL_PATH_SETTINGS_KEY, "") or "").strip(),
            "runner_command": str(store.value(AI_QWEN_RUNNER_COMMAND_SETTINGS_KEY, "") or "").strip(),
            "endpoint": str(store.value(AI_QWEN_ENDPOINT_SETTINGS_KEY, "") or "").strip(),
        }
    except Exception:
        return {"model_path": "", "runner_command": "", "endpoint": ""}


def save_qwen_provider_config(
    *,
    model_path: str | None = None,
    runner_command: str | None = None,
    endpoint: str | None = None,
    settings: Any | None = None,
) -> bool:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return False
    try:
        if model_path is not None:
            store.setValue(AI_QWEN_MODEL_PATH_SETTINGS_KEY, str(model_path or "").strip())
        if runner_command is not None:
            store.setValue(AI_QWEN_RUNNER_COMMAND_SETTINGS_KEY, str(runner_command or "").strip())
        if endpoint is not None:
            store.setValue(AI_QWEN_ENDPOINT_SETTINGS_KEY, str(endpoint or "").strip())
        store.sync()
        return True
    except Exception:
        return False


def saved_qwen_executor_state(settings: Any | None = None) -> dict[str, Any]:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return {"last_ok": False, "last_error": ""}
    try:
        ok_raw = store.value(AI_QWEN_EXECUTOR_LAST_OK_SETTINGS_KEY, False)
        error = str(store.value(AI_QWEN_EXECUTOR_LAST_ERROR_SETTINGS_KEY, "") or "").strip()
        last_ok = bool(ok_raw) if isinstance(ok_raw, bool) else _enabled(str(ok_raw))
        return {"last_ok": last_ok, "last_error": error}
    except Exception:
        return {"last_ok": False, "last_error": ""}


def save_qwen_executor_state(
    *,
    ok: bool,
    error: str = "",
    settings: Any | None = None,
) -> bool:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return False
    try:
        store.setValue(AI_QWEN_EXECUTOR_LAST_OK_SETTINGS_KEY, bool(ok))
        store.setValue(AI_QWEN_EXECUTOR_LAST_ERROR_SETTINGS_KEY, "" if ok else str(error or "").strip())
        store.sync()
        return True
    except Exception:
        return False


def saved_claude_mcp_config(settings: Any | None = None) -> dict[str, Any]:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return {"enabled": False, "command": ""}
    try:
        enabled_raw = store.value(AI_CLAUDE_MCP_ENABLED_SETTINGS_KEY, False)
        command = str(store.value(AI_CLAUDE_MCP_COMMAND_SETTINGS_KEY, "") or "").strip()
        enabled = bool(enabled_raw) if isinstance(enabled_raw, bool) else _enabled(str(enabled_raw))
        return {"enabled": enabled, "command": command}
    except Exception:
        return {"enabled": False, "command": ""}


def save_claude_mcp_config(
    *,
    enabled: bool = True,
    command: str | None = None,
    cli_command: str | None = None,
    settings: Any | None = None,
) -> bool:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return False
    try:
        store.setValue(AI_CLAUDE_MCP_ENABLED_SETTINGS_KEY, bool(enabled))
        if command is not None:
            store.setValue(AI_CLAUDE_MCP_COMMAND_SETTINGS_KEY, str(command or "").strip())
        if cli_command is not None:
            store.setValue(AI_CLAUDE_CLI_COMMAND_SETTINGS_KEY, str(cli_command or "").strip())
        store.sync()
        return True
    except Exception:
        return False


def saved_claude_cli_command(settings: Any | None = None) -> str:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return ""
    try:
        return str(store.value(AI_CLAUDE_CLI_COMMAND_SETTINGS_KEY, "") or "").strip()
    except Exception:
        return ""


def saved_claude_executor_state(settings: Any | None = None) -> dict[str, Any]:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return {"last_ok": False, "last_error": ""}
    try:
        ok_raw = store.value(AI_CLAUDE_EXECUTOR_LAST_OK_SETTINGS_KEY, False)
        error = str(store.value(AI_CLAUDE_EXECUTOR_LAST_ERROR_SETTINGS_KEY, "") or "").strip()
        last_ok = bool(ok_raw) if isinstance(ok_raw, bool) else _enabled(str(ok_raw))
        return {"last_ok": last_ok, "last_error": error}
    except Exception:
        return {"last_ok": False, "last_error": ""}


def save_claude_executor_state(
    *,
    ok: bool,
    error: str = "",
    settings: Any | None = None,
) -> bool:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return False
    try:
        store.setValue(AI_CLAUDE_EXECUTOR_LAST_OK_SETTINGS_KEY, bool(ok))
        store.setValue(AI_CLAUDE_EXECUTOR_LAST_ERROR_SETTINGS_KEY, "" if ok else str(error or "").strip())
        store.sync()
        return True
    except Exception:
        return False


def saved_local_llm_config(settings: Any | None = None) -> dict[str, str]:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return {"command": ""}
    try:
        return {
            "command": str(store.value(AI_LOCAL_LLM_COMMAND_SETTINGS_KEY, "") or "").strip(),
        }
    except Exception:
        return {"command": ""}


def save_local_llm_provider_config(
    *,
    command: str | None = None,
    settings: Any | None = None,
) -> bool:
    store = settings if settings is not None else _provider_settings()
    if store is None:
        return False
    try:
        if command is not None:
            store.setValue(AI_LOCAL_LLM_COMMAND_SETTINGS_KEY, str(command or "").strip())
        store.sync()
        return True
    except Exception:
        return False


def _find_claude_cli_command(env: Mapping[str, str] | None = None) -> str:
    e = _env(env)
    configured = str(e.get("TIGERCAPTURE_CLAUDE_CLI_COMMAND") or saved_claude_cli_command() or "").strip()
    if configured and _command_available(configured):
        return configured
    for name in ("claude", "claude.exe", "claude.cmd"):
        path = shutil.which(name)
        if path:
            return str(path)
    return ""


def qwen_install_plan() -> dict[str, Any]:
    return {
        "title": "기본 무료 AI 설치",
        "provider_id": QWEN_LOCAL_PROVIDER_ID,
        "model_family": QWEN_LOCAL_MANIFEST["model_family"],
        "model_size": QWEN_LOCAL_MANIFEST["model_size"],
        "quantization": QWEN_LOCAL_MANIFEST["quantization"],
        "license": QWEN_LOCAL_MANIFEST["license"],
        "model_ref": QWEN_LOCAL_MANIFEST["model_ref"],
        "model_page": QWEN_LOCAL_MANIFEST["model_page"],
        "endpoint": QWEN_DEFAULT_ENDPOINT,
        "server_command": QWEN_LLAMA_SERVER_COMMAND,
        "windows_install_command": "winget install llama.cpp",
        "environment": {
            "TIGERCAPTURE_QWEN_ENDPOINT": QWEN_DEFAULT_ENDPOINT,
            "TIGERCAPTURE_QWEN_RUNNER_COMMAND": QWEN_LLAMA_SERVER_COMMAND,
            "TIGERCAPTURE_AI_PROVIDER": QWEN_LOCAL_PROVIDER_ID,
        },
        "summary": (
            "기본 무료 AI는 로컬에서 실행되는 Qwen3 1.7B GGUF 모델입니다. "
            "앱은 llama.cpp가 있으면 로컬 서버 시작을 시도하고, 없으면 Windows winget 설치 경로를 안내합니다."
        ),
    }


def provider_setup_instructions(provider_id: str | None) -> dict[str, Any]:
    provider = _normalized_provider_id(provider_id) or "qwen_local"
    mcp_command = default_mcp_server_command()
    if provider == "qwen_local":
        plan = qwen_install_plan()
        body = "\n".join(
            [
                "1. '무료 AI 설치'를 누르면 llama.cpp가 설치되어 있는지 먼저 확인합니다.",
                f"2. 설치되어 있으면 `{plan['server_command']}`로 로컬 서버를 시작하고 `{plan['endpoint']}`를 저장합니다.",
                "3. 설치되어 있지 않으면 Windows에서는 `winget install llama.cpp` 설치를 시작할 수 있습니다.",
                "4. 이미 LM Studio, llama.cpp, vLLM 같은 로컬 서버가 있다면 서버 주소만 저장해도 됩니다.",
                "5. 모델 파일을 직접 받은 경우 모델 파일/폴더를 선택하고 runner 명령을 연결하면 됩니다.",
            ]
        )
        return {
            "title": "기본 무료 AI 설치",
            "summary": plan["summary"],
            "body": body,
            "primary_action": "무료 AI 설치",
            "model_page": plan["model_page"],
            "server_command": plan["server_command"],
            "endpoint": plan["endpoint"],
        }
    if provider == "codex_mcp":
        body = "\n".join(
            [
                "1. Codex 쪽에서 Tiger Studio MCP 서버를 등록합니다.",
                f"2. MCP server command: `{mcp_command}`",
                "3. Tiger Studio 실행 환경에 `TIGERCAPTURE_CODEX_MCP_ENABLED=1`을 설정합니다.",
                "4. 필요하면 `TIGERCAPTURE_CODEX_MCP_COMMAND`에 위 명령을 그대로 지정합니다.",
                "5. 앱에서 provider를 Codex로 선택하면 Review 단계에서 AI 플랜 JSON만 받습니다. 프로젝트 직접 수정은 Tiger Studio가 검증 후 적용합니다.",
            ]
        )
        return {
            "title": "Codex 연결 방법",
            "summary": "Codex는 MCP 브리지로 Tiger Studio의 안전한 편집 명령만 호출하게 연결합니다.",
            "body": body,
            "primary_action": "연결 안내",
            "server_command": mcp_command,
        }
    if provider == "claude_mcp":
        body = "\n".join(
            [
                "1. 'Claude Code 터미널 열기'를 누르면 Tiger Studio 작업 폴더에서 PowerShell 기반 Claude Code 콘솔을 엽니다.",
                "2. MCP 서버가 없으면 먼저 `claude mcp add --transport stdio tiger-studio -- <server command>`로 등록합니다.",
                "3. Tiger Studio 시작 안내 마크다운을 Claude 첫 프롬프트로 전달하고 클립보드에도 복사합니다.",
                "4. 열린 Claude Code 터미널에서 `/mcp`를 입력해 `tiger-studio` 서버를 승인/확인하세요.",
                "5. 이후 Claude Code 대화창에서 Tiger Studio 작업을 지시하고, 앱에서는 검토 후 적용합니다.",
                "6. 자동 등록이 실패하면 Claude Code CLI 설치 여부와 PATH를 확인하세요.",
            ]
        )
        return {
            "title": "Claude 연결 방법",
            "summary": "Claude Code 터미널을 열어 Tiger Studio MCP와 대화합니다.",
            "body": body,
            "primary_action": "Claude Code 터미널 열기",
            "server_command": mcp_command,
            "claude_command": f"claude mcp add --transport stdio tiger-studio -- {mcp_command}",
        }
    if provider == "local_llm":
        body = "\n".join(
            [
                "1. 로컬 LLM 실행 명령을 준비합니다.",
                "2. 앱의 로컬 LLM 설정 창에 실행 명령을 저장하면 바로 provider readiness에 반영됩니다.",
                "3. 고급 사용자는 Tiger Studio 실행 환경에 `TIGERCAPTURE_LOCAL_LLM_COMMAND`를 설정해 앱 저장값보다 우선 적용할 수 있습니다.",
                "4. 출력은 EditPlan JSON이어야 하며, 앱이 검증에 실패하면 적용하지 않습니다.",
            ]
        )
        return {
            "title": "로컬 LLM 연결 방법",
            "summary": "이미 쓰는 로컬 모델 runner를 실행 명령으로 연결합니다.",
            "body": body,
            "primary_action": "로컬 LLM 실행 명령 설정",
        }
    return {
        "title": "AI 연결 안내",
        "summary": "현재 선택한 AI는 별도 설치가 필요하지 않습니다.",
        "body": "규칙 모드는 오프라인 내장 플래너입니다. JSON 가져오기는 외부에서 만든 안전 플랜을 Review에 넣는 방식입니다.",
        "primary_action": "확인",
    }


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on", "enabled"}


def _enabled_default_true(value: str | None) -> bool:
    raw = str(value or "").strip()
    return True if not raw else _enabled(raw)


def _command_available(command: str) -> bool:
    raw = str(command or "").strip()
    if not raw:
        return False
    try:
        first = shlex.split(raw, posix=False)[0]
    except Exception:
        first = raw.split()[0] if raw.split() else raw
    if not first:
        return False
    path = Path(first.strip('"'))
    if path.is_file():
        return True
    return shutil.which(first) is not None


def _path_exists(path_text: str) -> bool:
    raw = str(path_text or "").strip().strip('"')
    if not raw:
        return False
    try:
        path = Path(raw).expanduser()
        return path.is_file() or path.is_dir()
    except Exception:
        return False


def _qwen_local_status(env: Mapping[str, str]) -> AIProviderStatus:
    saved = saved_qwen_config()
    executor_state = saved_qwen_executor_state()
    model_path = str(env.get("TIGERCAPTURE_QWEN_MODEL_PATH") or saved.get("model_path") or "").strip()
    runner_cmd = str(env.get("TIGERCAPTURE_QWEN_RUNNER_COMMAND") or saved.get("runner_command") or "").strip()
    endpoint = str(env.get("TIGERCAPTURE_QWEN_ENDPOINT") or saved.get("endpoint") or "").strip()
    model_ready = _path_exists(model_path)
    runner_ready = _command_available(runner_cmd)
    endpoint_configured = bool(endpoint)
    available = bool(endpoint_configured or (model_ready and runner_ready))
    missing: list[str] = []
    if not model_path:
        missing.append("TIGERCAPTURE_QWEN_MODEL_PATH")
    elif not model_ready:
        missing.append("existing Qwen model file or directory")
    if not runner_cmd and not endpoint_configured:
        missing.append("TIGERCAPTURE_QWEN_RUNNER_COMMAND or TIGERCAPTURE_QWEN_ENDPOINT")
    elif runner_cmd and not runner_ready and not endpoint_configured:
        missing.append("available Qwen runner command")

    executor_ready = bool(endpoint_configured)
    executor_last_error = str(executor_state.get("last_error") or "").strip()
    executor_failed = bool(endpoint_configured and executor_last_error and not executor_state.get("last_ok"))
    if available and endpoint_configured:
        if executor_failed:
            reason = f"Qwen endpoint is configured, but the last direct request failed: {executor_last_error}"
            setup_state = "executor_failed"
        else:
            reason = "Qwen endpoint is configured. The executor can request validated EditPlan JSON."
            setup_state = "endpoint_configured"
    elif available:
        reason = "Qwen model path and runner command are available. Start a local OpenAI-compatible endpoint to enable the executor."
        setup_state = "ready"
    else:
        missing_text = ", ".join(missing) if missing else "Qwen local setup"
        reason = f"Install default free AI or set {missing_text}. {EXECUTOR_PENDING_MESSAGE}"
        setup_state = "setup_needed"

    return AIProviderStatus(
        id=QWEN_LOCAL_PROVIDER_ID,
        label="Default Free AI (Qwen3 1.7B GGUF)",
        available=available,
        mode=QWEN_LOCAL_MANIFEST["mode"],
        configured=True,
        reason=reason,
        command=runner_cmd,
        setup_needed=not available,
        setup_state=setup_state,
        manifest=QWEN_LOCAL_MANIFEST,
        endpoint=endpoint,
        model_path=model_path,
        executor_wired=executor_ready,
        generation_fallback_provider="" if executor_ready else "rule_based",
    )


def ai_provider_readiness(env: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Return provider availability without starting external processes."""
    e = _env(env)
    saved_claude = saved_claude_mcp_config()
    claude_executor_state = saved_claude_executor_state()
    saved_local_llm = saved_local_llm_config()
    local_cmd = str(e.get("TIGERCAPTURE_LOCAL_LLM_COMMAND") or saved_local_llm.get("command") or "").strip()
    codex_enabled = _enabled(e.get("TIGERCAPTURE_CODEX_MCP_ENABLED"))
    codex_executor_cmd = str(
        e.get("TIGERCAPTURE_CODEX_EXECUTOR_COMMAND")
        or e.get("TIGERCAPTURE_CODEX_CLI_COMMAND")
        or ""
    ).strip()
    claude_enabled = bool(_enabled(e.get("TIGERCAPTURE_CLAUDE_MCP_ENABLED")) or saved_claude.get("enabled"))
    codex_cmd = str(e.get("TIGERCAPTURE_CODEX_MCP_COMMAND") or default_mcp_server_command()).strip()
    claude_cmd = str(
        e.get("TIGERCAPTURE_CLAUDE_MCP_COMMAND") or saved_claude.get("command") or default_mcp_server_command()
    ).strip()
    claude_cli_cmd = _find_claude_cli_command(e)
    claude_direct_enabled = _enabled_default_true(e.get(AI_CLAUDE_DIRECT_EXECUTOR_ENV))
    local_available = bool(local_cmd and _command_available(local_cmd))
    codex_mcp_available = bool(codex_enabled and _command_available(codex_cmd))
    codex_executor_available = bool(codex_executor_cmd and _command_available(codex_executor_cmd))
    codex_available = bool(codex_mcp_available or codex_executor_available)
    claude_available = bool(claude_enabled and _command_available(claude_cmd))
    claude_executor_ready = bool(claude_available and claude_cli_cmd)
    claude_direct_generation_ready = bool(claude_executor_ready and claude_direct_enabled)
    claude_executor_last_error = str(claude_executor_state.get("last_error") or "").strip()
    claude_executor_failed = bool(
        claude_direct_generation_ready and claude_executor_last_error and not claude_executor_state.get("last_ok")
    )
    claude_setup_state = "executor_failed" if claude_executor_failed else ("ready" if claude_available else "setup_needed")
    if not claude_enabled:
        claude_setup_state = "setup_needed"
    claude_reason = (
        f"Claude CLI direct plan execution failed recently: {claude_executor_last_error}"
        if claude_executor_failed
        else (
            "Claude Code 터미널 열기를 실행하면 Tiger Studio MCP 서버를 확인/등록하고 Claude Code를 시작합니다."
            if not claude_enabled
            else (
                (
                    "Claude CLI is available, but direct EditPlan generation is disabled by "
                    f"{AI_CLAUDE_DIRECT_EXECUTOR_ENV}=0. Clear the override to let Tiger Studio "
                    "auto-run validated Claude plans."
                )
                if claude_executor_ready and not claude_direct_enabled
                else "Claude direct executor is enabled automatically. The app can request validated EditPlan JSON before Review."
                if claude_direct_generation_ready
                else "Claude MCP bridge is registered, but Claude Code CLI was not found. Open setup to locate/install Claude Code."
                if claude_available
                else "Claude MCP is registered, but the local server command was not found. Run setup from Tiger Studio."
            )
        )
    )
    if claude_executor_ready and not claude_direct_enabled and not claude_executor_failed:
        claude_reason = (
            "Claude CLI is available, but direct EditPlan generation is disabled by "
            f"{AI_CLAUDE_DIRECT_EXECUTOR_ENV}=0. Clear the override to let Tiger Studio "
            "auto-run validated Claude plans."
        )

    rows = [
        _qwen_local_status(e),
        AIProviderStatus(
            id="codex_mcp",
            label="Codex MCP",
            available=codex_available,
            mode="external_agent",
            requires_network=True,
            configured=bool(codex_enabled or codex_executor_cmd),
            reason=(
                "Codex executor command is available. The app can request validated EditPlan JSON through Review-first safety."
                if codex_executor_available
                else "Set TIGERCAPTURE_CODEX_EXECUTOR_COMMAND to enable direct Codex EditPlan generation, or TIGERCAPTURE_CODEX_MCP_ENABLED=1 for terminal/MCP handoff."
                if not codex_enabled
                else (
                    "Local MCP bridge command is available. Direct generation still needs TIGERCAPTURE_CODEX_EXECUTOR_COMMAND."
                    if codex_mcp_available
                    else "Configured MCP command was not found. Direct generation also needs TIGERCAPTURE_CODEX_EXECUTOR_COMMAND."
                )
            ),
            command=codex_cmd,
            cli_command=codex_executor_cmd,
            executor_wired=codex_executor_available,
            generation_fallback_provider="" if codex_executor_available else "rule_based",
        ),
        AIProviderStatus(
            id="claude_mcp",
            label="Claude MCP",
            available=claude_available,
            mode="external_agent",
            requires_network=True,
            configured=claude_enabled,
            reason=claude_reason,
            command=claude_cmd,
            setup_state=claude_setup_state,
            cli_command=claude_cli_cmd,
            executor_wired=claude_executor_ready,
            direct_generation_enabled=claude_direct_generation_ready,
            generation_fallback_provider="" if claude_direct_generation_ready and not claude_executor_failed else "rule_based",
        ),
        AIProviderStatus(
            id="local_llm",
            label="Local LLM",
            available=local_available,
            mode="local_external",
            configured=bool(local_cmd),
            reason="Set TIGERCAPTURE_LOCAL_LLM_COMMAND to enable."
            if not local_cmd
            else (
                "Command is available. The app can request validated EditPlan JSON from this local LLM command."
                if local_available
                else "Configured command was not found."
            ),
            command=local_cmd,
            executor_wired=local_available,
            generation_fallback_provider="" if local_available else "rule_based",
        ),
        AIProviderStatus(
            id="manual_json",
            label="Manual JSON import",
            available=True,
            mode="local_manual",
            configured=True,
            reason="Paste or load validated EditPlan JSON.",
            executor_wired=True,
        ),
        AIProviderStatus(
            id="rule_based",
            label="Rule-based planner",
            available=True,
            mode="local_deterministic",
            configured=True,
            reason="Built in and safe for offline use.",
            executor_wired=True,
        ),
    ]
    return {row.id: row.to_dict() for row in rows}


def default_ai_provider_id(env: Mapping[str, str] | None = None) -> str:
    statuses = ai_provider_readiness(env)
    requested = str(_env(env).get("TIGERCAPTURE_AI_PROVIDER") or "").strip()
    if requested:
        return requested if statuses.get(requested, {}).get("available") else "rule_based"
    for provider_id in DEFAULT_PROVIDER_FALLBACK_ORDER:
        if statuses.get(provider_id, {}).get("available"):
            return provider_id
    return "rule_based"


def selected_ai_provider_id(env: Mapping[str, str] | None = None) -> str:
    statuses = ai_provider_readiness(env)
    requested = _normalized_provider_id(str(_env(env).get("TIGERCAPTURE_AI_PROVIDER") or "").strip())
    if requested:
        return requested
    saved = saved_ai_provider_id()
    if saved and saved in statuses:
        return saved
    return default_ai_provider_id(env)


def effective_generation_provider_id(env: Mapping[str, str] | None = None) -> str:
    statuses = ai_provider_readiness(env)
    selected = selected_ai_provider_id(env)
    row = statuses.get(selected) or {}
    if selected == "manual_json":
        return "manual_json"
    if selected == "claude_mcp":
        if row.get("available") and row.get("executor_wired") and row.get("direct_generation_enabled"):
            return selected
        return "rule_based"
    if row.get("available") and row.get("executor_wired"):
        return selected
    return "rule_based"


def provider_effective_generation_for_selection(
    provider_id: str | None,
    statuses: Mapping[str, Mapping[str, Any]] | None = None,
) -> str:
    selected = _normalized_provider_id(provider_id) or "rule_based"
    row = dict((statuses or ai_provider_readiness()).get(selected) or {})
    if selected == "manual_json":
        return "manual_json"
    if selected == "claude_mcp":
        if row.get("available") and row.get("executor_wired") and row.get("direct_generation_enabled"):
            return selected
        return "rule_based"
    if row.get("available") and row.get("executor_wired"):
        return selected
    return "rule_based"


def provider_user_state(
    env: Mapping[str, str] | None = None,
    *,
    provider_id: str | None = None,
) -> dict[str, Any]:
    """Return explicit UI copy for selected-vs-effective AI behavior."""

    statuses = ai_provider_readiness(env)
    selected = _normalized_provider_id(provider_id) or selected_ai_provider_id(env)
    row = statuses.get(selected) or {}
    effective = provider_effective_generation_for_selection(selected, statuses)
    selected_label = provider_user_label(selected)
    effective_label = provider_user_label(effective)
    interaction = provider_interaction_model(selected, row)
    uses_rule_fallback = selected != "rule_based" and effective == "rule_based"
    direct_ai = effective == selected and selected not in {"rule_based", "manual_json"}
    setup_state = str(row.get("setup_state") or "")

    headline = ""
    detail = ""
    next_action = ""
    badge = str(interaction.get("state") or provider_state_label(row))

    if selected == "rule_based":
        headline = "규칙 모드로 안전 플랜을 만듭니다."
        qwen = statuses.get(QWEN_LOCAL_PROVIDER_ID) or {}
        detail = (
            "기본 무료 AI는 아직 설치되지 않았습니다. 외부 AI 없이 내장 규칙으로 Plan을 만들고 Review에서 적용합니다."
            if qwen and not qwen.get("available")
            else "외부 AI 없이 내장 규칙으로 Plan을 만들고 Review에서 적용합니다."
        )
        next_action = "AI가 필요하면 기본 무료 AI, 로컬 LLM, Claude, Codex 중 하나를 선택하세요."
        badge = "규칙"
    elif selected == "manual_json":
        headline = "외부 EditPlan JSON을 검토합니다."
        detail = "모델 호출 없이 붙여넣은 JSON만 검증하고 Review에서 적용합니다."
        next_action = "외부 도구가 만든 EditPlan JSON을 붙여넣으세요."
        badge = "JSON"
    elif selected == "claude_mcp" and uses_rule_fallback:
        if row.get("available") and row.get("executor_wired"):
            headline = "Claude 직접 생성이 꺼져 있어 규칙 모드로 만듭니다."
            detail = (
                f"{AI_CLAUDE_DIRECT_EXECUTOR_ENV}=0 override가 설정되어 있습니다. "
                "이 값을 지우면 Claude가 앱 안에서 validated EditPlan을 자동 생성합니다."
            )
            next_action = "환경 override를 해제하거나 터미널-only 진단 모드로 계속 사용하세요."
            badge = "직접 생성 꺼짐"
        elif row.get("available"):
            headline = "Claude MCP는 등록됐지만 Claude CLI를 찾지 못했습니다."
            detail = "앱 내부 Plan은 규칙 모드로 만들고, Claude 대화는 CLI 연결 후 사용할 수 있습니다."
            next_action = "설정에서 Claude CLI 경로와 MCP 등록을 확인하세요."
            badge = "MCP"
        else:
            headline = "Claude 연결이 아직 준비되지 않았습니다."
            detail = "지금은 규칙 모드로 Plan을 만들며, Claude Code 터미널 연결이 필요합니다."
            next_action = "설정에서 Claude CLI 열기 또는 MCP 등록을 실행하세요."
            badge = "설정 필요"
    elif selected == QWEN_LOCAL_PROVIDER_ID and uses_rule_fallback:
        if setup_state == "executor_failed":
            headline = "무료 AI 호출이 실패해 규칙 모드로 전환했습니다."
            detail = "서버 주소는 있지만 마지막 응답이 실패했습니다. 기술 오류 대신 안전한 Plan을 먼저 만듭니다."
            next_action = "설정에서 무료 AI 서버를 다시 시작한 뒤 Plan을 다시 누르세요."
            badge = "확인 필요"
        else:
            headline = "기본 무료 AI는 아직 설치되지 않았습니다. 규칙 모드로 만듭니다."
            detail = "Qwen 서버 또는 모델 runner가 준비되면 편집 명령을 직접 해석할 수 있습니다."
            next_action = "설정에서 무료 AI 설치/연결을 실행하세요."
            badge = "설치 필요"
    elif selected == "local_llm" and uses_rule_fallback:
        headline = "로컬 LLM 실행 명령이 없어 규칙 모드로 만듭니다."
        detail = "로컬 모델을 쓰려면 EditPlan JSON을 출력하는 실행 명령이 필요합니다."
        next_action = "설정에서 로컬 LLM 실행 명령을 저장하세요."
        badge = "설정 필요"
    elif selected == "codex_mcp" and uses_rule_fallback:
        headline = "Codex executor가 없어 규칙 모드로 만듭니다."
        detail = "Codex MCP/터미널 연결은 가능해도 앱 내부 Plan 생성은 executor 명령이 있어야 합니다."
        next_action = "Codex executor 명령 또는 MCP 연결을 설정하세요."
        badge = "설정 필요"
    elif direct_ai:
        headline = f"{selected_label}가 편집 명령을 직접 해석합니다."
        detail = "AI가 만든 EditPlan JSON을 검증한 뒤 Review에서 체크한 항목만 적용합니다."
        next_action = "Plan을 누른 뒤 Review에서 작업 내용을 확인하세요."
        badge = "직접 생성"
    else:
        headline = provider_status_label(env)
        detail = str(row.get("reason") or interaction.get("summary") or "")
        next_action = str(interaction.get("setup_label") or "설정을 확인하세요.")

    return {
        "selected_provider": selected,
        "selected_label": selected_label,
        "effective_generation_provider": effective,
        "effective_label": effective_label,
        "provider_state": provider_state_label({"id": selected, **row}),
        "mode_badge": badge,
        "headline": headline,
        "detail": detail,
        "next_action": next_action,
        "action_label": str(interaction.get("run_label") or "AI Plan"),
        "review_label": str(interaction.get("review_label") or "Plan 검토"),
        "placeholder": str(interaction.get("placeholder") or ""),
        "can_direct_generate": bool(interaction.get("can_direct_generate")) and not uses_rule_fallback,
        "opens_terminal": bool(interaction.get("opens_terminal")),
        "uses_rule_fallback": bool(uses_rule_fallback),
        "direct_ai": bool(direct_ai),
    }


def _provider_chat_url(endpoint: str) -> str:
    base = str(endpoint or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/chat/completions" if base.endswith("/v1") else f"{base}/v1/chat/completions"


def _extract_json_object(text: str) -> str:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.casefold().startswith("json"):
            raw = raw[4:].strip()
    try:
        json.loads(raw)
        return raw
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        candidate = raw[start : end + 1]
        json.loads(candidate)
        return candidate
    raise ValueError("AI 응답에서 EditPlan JSON을 찾지 못했습니다.")


def _repair_provider_plan_json_from_baseline(text: str, base_plan: EditPlan) -> tuple[str, list[str]]:
    """Repair small local-model JSON omissions only when a safe baseline matches."""
    try:
        payload = json.loads(text)
    except Exception:
        return text, []
    if not isinstance(payload, dict):
        return text, []
    try:
        baseline = base_plan.to_dict()
    except Exception:
        return text, []
    baseline_ops = {
        str(op.get("id") or ""): op
        for op in baseline.get("operations", [])
        if isinstance(op, Mapping) and str(op.get("id") or "")
    }
    notes: list[str] = []
    operations = payload.get("operations")
    if isinstance(operations, list):
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                continue
            op_id = str(operation.get("id") or "")
            baseline_op = baseline_ops.get(op_id)
            if not baseline_op:
                continue
            for key in ("type", "target"):
                if not str(operation.get(key) or "").strip() and baseline_op.get(key) is not None:
                    operation[key] = baseline_op.get(key)
                    notes.append(f"op[{index}].{key}")
            for key in ("start_ms", "end_ms", "text", "style_preset_id"):
                if key not in operation and key in baseline_op:
                    operation[key] = baseline_op.get(key)
                    notes.append(f"op[{index}].{key}")
            if "confidence" in operation:
                try:
                    confidence = float(operation.get("confidence"))
                except Exception:
                    confidence = -1.0
                if not 0.0 <= confidence <= 1.0:
                    operation.pop("confidence", None)
                    notes.append(f"op[{index}].confidence")
            if "quality_score" in operation:
                try:
                    quality_score = int(operation.get("quality_score"))
                except Exception:
                    quality_score = -1
                if not 0 <= quality_score <= 100:
                    if baseline_op.get("quality_score") is not None:
                        operation["quality_score"] = baseline_op.get("quality_score")
                    else:
                        operation.pop("quality_score", None)
                    notes.append(f"op[{index}].quality_score")
    if not notes:
        return text, []
    return json.dumps(payload, ensure_ascii=False), notes


def _qwen_user_fallback_reason(exc: Exception | str | None = None) -> str:
    text = str(exc or "")
    lowered = text.casefold()
    if isinstance(exc, (ConnectionRefusedError, TimeoutError)) or "winerror 10061" in lowered or "connection refused" in lowered:
        return "무료 AI 서버가 꺼져 있거나 응답하지 않아 기본 자동 규칙으로 만들었습니다. 설정 버튼에서 무료 AI를 다시 시작하세요."
    if isinstance(exc, urllib.error.URLError) and isinstance(getattr(exc, "reason", None), ConnectionRefusedError):
        return "무료 AI 서버가 꺼져 있거나 응답하지 않아 기본 자동 규칙으로 만들었습니다. 설정 버튼에서 무료 AI를 다시 시작하세요."
    if "timed out" in lowered or "timeout" in lowered:
        return "무료 AI 응답이 오래 걸려 기본 자동 규칙으로 만들었습니다. 잠시 뒤 다시 시도하거나 설정 버튼에서 서버 상태를 확인하세요."
    if "editplan json" in lowered or "json" in lowered:
        return "무료 AI 응답 형식이 맞지 않아 기본 자동 규칙으로 만들었습니다. 검토 화면에서 결과를 확인하세요."
    return "무료 AI를 사용할 수 없어 기본 자동 규칙으로 만들었습니다. 설정 버튼에서 연결 상태를 확인하세요."


def _compact_document(document: Any, *, max_segments: int = 24) -> dict[str, Any]:
    if document is None:
        return {}
    try:
        data = document.to_dict()
    except Exception:
        return {}
    segments = data.get("segments")
    if isinstance(segments, list) and len(segments) > max_segments:
        data = dict(data)
        data["segments"] = segments[:max_segments]
        data["truncated_segment_count"] = len(segments) - max_segments
    return data


def _qwen_executor_messages(prompt: str, base_plan: EditPlan, document: Any | None) -> list[dict[str, str]]:
    contract = {
        "schema_version": AI_EDIT_PLAN_SCHEMA_V1["schema_version"],
        "required_plan_keys": AI_EDIT_PLAN_SCHEMA_V1["plan_keys"],
        "allowed_operation_types": sorted(ALLOWED_OPERATION_TYPES),
        "numeric_rules": {
            "quality_score": "integer 0..100",
            "confidence": "optional decimal 0.0..1.0; omit it unless already present in safe_baseline_plan",
        },
    }
    payload = {
        "user_command": str(prompt or "").strip(),
        "transcript": _compact_document(document),
        "safe_baseline_plan": _compact_provider_json(base_plan.to_dict()),
    }
    system = (
        "You are Tiger Studio's local video edit planner. "
        "Return only one valid JSON object matching the compact EditPlan contract. "
        "Never include markdown, commentary, shell commands, code, or fields outside the schema. "
        "Use review-safe operations only. If uncertain, copy safe_baseline_plan operations unchanged and improve only summary/metadata. "
        "Do not add confidence fields. If a confidence field is unavoidable, it must be a decimal between 0 and 1."
    )
    user = (
        "Compact EditPlan contract:\n"
        + json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n\nCurrent editing request and safe baseline:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _claude_executor_prompt(prompt: str, base_plan: EditPlan, document: Any | None) -> str:
    contract = {
        "schema_version": AI_EDIT_PLAN_SCHEMA_V1["schema_version"],
        "required_plan_keys": AI_EDIT_PLAN_SCHEMA_V1["plan_keys"],
        "allowed_operation_types": sorted(ALLOWED_OPERATION_TYPES),
        "safety": [
            "Return one JSON object only.",
            "Every operation must use an allowed type and valid time ranges.",
            "Never include code, shell, Python, scripts, or project mutations.",
            "If uncertain, return the safe_baseline_plan unchanged except provider/summary/metadata.",
        ],
    }
    payload = {
        "user_command": str(prompt or "").strip(),
        "transcript": _compact_document(document),
        "safe_baseline_plan": _compact_provider_json(base_plan.to_dict()),
    }
    return (
        "You are Tiger Studio's video edit planner.\n"
        "Return only one JSON object matching the compact EditPlan contract. Do not write markdown or explanation.\n"
        "Prefer preserving safe_baseline_plan operations unless the user's request clearly requires an allowed operation change.\n\n"
        "Compact EditPlan contract:\n"
        + json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n\nCurrent editing request, transcript, and safe baseline:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def _compact_provider_json(value: Any, *, max_text: int = 260, max_items: int = 36, depth: int = 0) -> Any:
    """Keep provider prompts bounded without changing validated plan semantics."""
    if isinstance(value, str):
        text = value.strip()
        if len(text) <= max_text:
            return text
        return text[: max_text - 1].rstrip() + "…"
    if isinstance(value, Mapping):
        return {
            str(key): _compact_provider_json(child, max_text=max_text, max_items=max_items, depth=depth + 1)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        items = list(value)
        limited = [
            _compact_provider_json(item, max_text=max_text, max_items=max_items, depth=depth + 1)
            for item in items[:max_items]
        ]
        if len(items) > max_items:
            limited.append({"_truncated_count": len(items) - max_items})
        return limited
    return value


def _local_llm_executor_payload(prompt: str, base_plan: EditPlan, document: Any | None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task": "tiger_studio_edit_plan",
        "instruction": (
            "Return only one JSON object matching the EditPlan contract. "
            "Never include markdown, shell commands, Python, scripts, or project mutations. "
            "If uncertain, preserve safe_baseline_plan operations and improve only summary/metadata."
        ),
        "plan_schema": AI_EDIT_PLAN_SCHEMA_V1,
        "allowed_operation_types": sorted(ALLOWED_OPERATION_TYPES),
        "user_command": str(prompt or "").strip(),
        "transcript": _compact_document(document),
        "safe_baseline_plan": base_plan.to_dict(),
    }


def _codex_executor_payload(prompt: str, base_plan: EditPlan, document: Any | None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task": "tiger_studio_codex_edit_plan",
        "instruction": (
            "You are Codex acting as Tiger Studio's video edit planner. "
            "Return only one JSON object matching the EditPlan contract. "
            "Do not write markdown, shell commands, Python, patches, or explanations. "
            "Never mutate files or projects. If uncertain, preserve safe_baseline_plan operations "
            "and improve only summary/metadata."
        ),
        "plan_schema": AI_EDIT_PLAN_SCHEMA_V1,
        "allowed_operation_types": sorted(ALLOWED_OPERATION_TYPES),
        "user_command": str(prompt or "").strip(),
        "transcript": _compact_document(document),
        "safe_baseline_plan": base_plan.to_dict(),
    }


def _command_parts(command: str) -> list[str]:
    raw = str(command or "").strip()
    if not raw:
        return []
    try:
        parts = shlex.split(raw, posix=False)
    except Exception:
        parts = raw.split()
    return [str(part).strip().strip('"') for part in parts if str(part).strip()]


def _run_local_llm_command(command: str, payload: Mapping[str, Any], *, timeout_seconds: int) -> str:
    import subprocess

    raw_command = str(command or "").strip()
    parts = _command_parts(raw_command)
    if not parts:
        raise RuntimeError("Local LLM command is empty.")
    payload_text = json.dumps(dict(payload or {}), ensure_ascii=False)
    if "{payload_json}" in raw_command or "{prompt_json}" in raw_command:
        replaced = raw_command.replace("{payload_json}", payload_text).replace("{prompt_json}", payload_text)
        parts = _command_parts(replaced)
        input_text = None
    elif "{prompt}" in raw_command:
        replaced = raw_command.replace("{prompt}", str(payload.get("user_command") or ""))
        parts = _command_parts(replaced)
        input_text = payload_text
    else:
        input_text = payload_text
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        parts,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1, int(timeout_seconds or LOCAL_LLM_EXECUTOR_TIMEOUT_SECONDS)),
        creationflags=creationflags,
    )
    if int(completed.returncode or 0) != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or f"Local LLM command exited with code {completed.returncode}")
    return str(completed.stdout or "")


def _run_claude_cli_print(cli_command: str, prompt_text: str, *, timeout_seconds: int) -> str:
    import subprocess

    parts = _command_parts(cli_command)
    if not parts:
        raise RuntimeError("Claude CLI command is empty.")
    args = [
        *parts,
        "--print",
        "--output-format",
        "json",
        "--input-format",
        "text",
        "--no-session-persistence",
        "--permission-mode",
        "plan",
    ]
    model = str(os.environ.get(AI_CLAUDE_MODEL_ENV) or "haiku").strip()
    if model:
        args.extend(["--model", model])
    effort = str(os.environ.get(AI_CLAUDE_EFFORT_ENV) or "low").strip()
    if effort:
        args.extend(["--effort", effort])
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        args,
        input=str(prompt_text or ""),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1, int(timeout_seconds or CLAUDE_EXECUTOR_TIMEOUT_SECONDS)),
        creationflags=creationflags,
    )
    if int(completed.returncode or 0) != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or f"Claude CLI exited with code {completed.returncode}")
    return str(completed.stdout or "")


def _content_text_from_provider_json(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("result", "content", "text", "message", "response", "output", "choices"):
            if key in value:
                text = _content_text_from_provider_json(value.get(key))
                if text:
                    return text
        return ""
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = _content_text_from_provider_json(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_provider_plan_json(text: str) -> str:
    raw = str(text or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        return _extract_json_object(raw)
    if isinstance(data, Mapping) and {"id", "intent", "summary", "operations"}.issubset(set(data.keys())):
        return json.dumps(data, ensure_ascii=False)
    content = _content_text_from_provider_json(data)
    if content:
        return _extract_json_object(content)
    return _extract_json_object(raw)


def _repair_provider_plan_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Repair narrow, schema-safe provider omissions before strict validation.

    LLMs often return the right EditPlan shape but omit Review-card ids or leave
    operation_ids empty. Those fields drive Tiger Studio's review UI selection;
    they do not authorize new project mutations. Keep the repair intentionally
    narrow and let ``validate_edit_plan_json`` reject unknown keys, bad operation
    types, unsafe params, or invalid time ranges.
    """
    data = dict(payload)
    repairs: list[str] = []
    operations_raw = data.get("operations")
    operation_ids: list[str] = []
    if isinstance(operations_raw, list) and all(isinstance(item, Mapping) for item in operations_raw):
        fixed_operations: list[dict[str, Any]] = []
        for idx, raw in enumerate(operations_raw, start=1):
            operation = dict(raw)
            op_id = str(operation.get("id") or "").strip()
            if not op_id:
                op_id = make_operation_id(idx, str(operation.get("type") or "operation"))
                operation["id"] = op_id
                if "operation_ids" not in repairs:
                    repairs.append("operation_ids")
            operation_ids.append(op_id)
            fixed_operations.append(operation)
        data["operations"] = fixed_operations

    cards_raw = data.get("review_cards")
    if isinstance(cards_raw, list) and all(isinstance(item, Mapping) for item in cards_raw):
        fixed_cards: list[dict[str, Any]] = []
        for idx, raw in enumerate(cards_raw, start=1):
            card = dict(raw)
            if not str(card.get("id") or "").strip():
                card["id"] = f"card_{idx:03d}"
                if "review_card_ids" not in repairs:
                    repairs.append("review_card_ids")
            if not str(card.get("title") or "").strip():
                card["title"] = f"Review {idx}"
                if "review_card_titles" not in repairs:
                    repairs.append("review_card_titles")

            raw_operation_ids = card.get("operation_ids")
            if isinstance(raw_operation_ids, str):
                candidate_ids = [raw_operation_ids]
            elif isinstance(raw_operation_ids, list):
                candidate_ids = [str(item).strip() for item in raw_operation_ids if isinstance(item, str)]
            else:
                candidate_ids = []
            candidate_ids = [op_id for op_id in candidate_ids if op_id and op_id in operation_ids]
            if not candidate_ids and operation_ids:
                if len(cards_raw) == len(operation_ids):
                    candidate_ids = [operation_ids[idx - 1]]
                else:
                    candidate_ids = list(operation_ids)
                if "review_card_operation_ids" not in repairs:
                    repairs.append("review_card_operation_ids")
            card["operation_ids"] = candidate_ids
            fixed_cards.append(card)
        data["review_cards"] = fixed_cards
    return data, repairs


def _provider_user_fallback_reason(provider_label: str, exc: Exception | str | None = None) -> str:
    text = str(exc or "")
    lowered = text.casefold()
    if "not logged in" in lowered or "auth" in lowered or "login" in lowered:
        return f"{provider_label} 로그인이 필요해 기본 자동 규칙으로 만들었습니다. Claude Code에서 로그인 상태를 확인하세요."
    if "timed out" in lowered or "timeout" in lowered:
        return f"{provider_label} 응답이 오래 걸려 기본 자동 규칙으로 만들었습니다. 잠시 뒤 다시 시도하세요."
    if "editplan json" in lowered or "json" in lowered:
        return f"{provider_label} 응답 형식이 맞지 않아 기본 자동 규칙으로 만들었습니다. 검토 화면에서 결과를 확인하세요."
    return f"{provider_label}를 직접 호출하지 못해 기본 자동 규칙으로 만들었습니다. 연결 상태를 확인하세요."


def _generate_claude_provider_plan(
    prompt: str,
    base_plan: EditPlan,
    *,
    document: Any | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = CLAUDE_EXECUTOR_TIMEOUT_SECONDS,
) -> AIProviderPlanResult:
    statuses = ai_provider_readiness(env)
    row = statuses.get("claude_mcp") or {}
    cli_command = str(row.get("cli_command") or "").strip()
    if not cli_command:
        save_claude_executor_state(ok=False, error="Claude CLI를 찾지 못했습니다.")
        return AIProviderPlanResult(
            ok=False,
            provider="claude_mcp",
            reason="Claude CLI를 찾지 못해 기본 자동 규칙을 사용합니다.",
        )
    try:
        raw = _run_claude_cli_print(
            cli_command,
            _claude_executor_prompt(prompt, base_plan, document),
            timeout_seconds=timeout_seconds,
        )
        json_text = _extract_provider_plan_json(raw)
        result = validate_provider_plan_json("claude_mcp", json_text)
        if not result.ok or result.plan is None:
            save_claude_executor_state(ok=False, error=result.reason or "Claude 응답에서 유효한 EditPlan을 만들지 못했습니다.")
            return result
        metadata = dict(result.plan.metadata or {})
        metadata.update(
            {
                "prompt_text": str(prompt or "").strip(),
                "prompt_mode": "claude_mcp",
                "provider_id": "claude_mcp",
                "provider_executor": "claude_cli_print",
                "fallback_used": False,
            }
        )
        plan = replace(result.plan, provider="claude_mcp", metadata=metadata)
        save_claude_executor_state(ok=True, error="")
        return AIProviderPlanResult(
            ok=True,
            provider="claude_mcp",
            plan=plan,
            metadata={"cli_command": cli_command, "bytes": len(raw.encode("utf-8", "replace"))},
        )
    except Exception as exc:
        reason = _provider_user_fallback_reason("Claude", exc)
        save_claude_executor_state(ok=False, error=reason)
        return AIProviderPlanResult(
            ok=False,
            provider="claude_mcp",
            reason=reason,
            metadata={"cli_command": cli_command, "technical_error": str(exc)},
        )


def _generate_local_llm_provider_plan(
    prompt: str,
    base_plan: EditPlan,
    *,
    document: Any | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = LOCAL_LLM_EXECUTOR_TIMEOUT_SECONDS,
) -> AIProviderPlanResult:
    statuses = ai_provider_readiness(env)
    row = statuses.get("local_llm") or {}
    command = str(row.get("command") or "").strip()
    if not command:
        return AIProviderPlanResult(
            ok=False,
            provider="local_llm",
            reason="로컬 LLM 명령이 없어 기본 자동 규칙을 사용합니다.",
        )
    try:
        payload = _local_llm_executor_payload(prompt, base_plan, document)
        raw = _run_local_llm_command(command, payload, timeout_seconds=timeout_seconds)
        json_text = _extract_provider_plan_json(raw)
        result = validate_provider_plan_json("local_llm", json_text)
        if not result.ok or result.plan is None:
            return result
        metadata = dict(result.plan.metadata or {})
        metadata.update(
            {
                "prompt_text": str(prompt or "").strip(),
                "prompt_mode": "local_llm",
                "provider_id": "local_llm",
                "provider_executor": "local_llm_command",
                "fallback_used": False,
            }
        )
        plan = replace(result.plan, provider="local_llm", metadata=metadata)
        return AIProviderPlanResult(
            ok=True,
            provider="local_llm",
            plan=plan,
            metadata={"command": command, "bytes": len(raw.encode("utf-8", "replace"))},
        )
    except Exception as exc:
        return AIProviderPlanResult(
            ok=False,
            provider="local_llm",
            reason=_provider_user_fallback_reason("로컬 LLM", exc),
            metadata={"command": command, "technical_error": str(exc)},
        )


def _generate_codex_provider_plan(
    prompt: str,
    base_plan: EditPlan,
    *,
    document: Any | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = CODEX_EXECUTOR_TIMEOUT_SECONDS,
) -> AIProviderPlanResult:
    statuses = ai_provider_readiness(env)
    row = statuses.get("codex_mcp") or {}
    command = str(row.get("cli_command") or "").strip()
    if not command:
        return AIProviderPlanResult(
            ok=False,
            provider="codex_mcp",
            reason=(
                "Codex direct executor is not configured. Set TIGERCAPTURE_CODEX_EXECUTOR_COMMAND "
                "or use the terminal/MCP handoff."
            ),
        )
    try:
        payload = _codex_executor_payload(prompt, base_plan, document)
        raw = _run_local_llm_command(command, payload, timeout_seconds=timeout_seconds)
        json_text = _extract_provider_plan_json(raw)
        result = validate_provider_plan_json("codex_mcp", json_text)
        if not result.ok or result.plan is None:
            return result
        metadata = dict(result.plan.metadata or {})
        metadata.update(
            {
                "prompt_text": str(prompt or "").strip(),
                "prompt_mode": "codex_mcp",
                "provider_id": "codex_mcp",
                "provider_executor": "codex_executor_command",
                "fallback_used": False,
            }
        )
        plan = replace(result.plan, provider="codex_mcp", metadata=metadata)
        return AIProviderPlanResult(
            ok=True,
            provider="codex_mcp",
            plan=plan,
            metadata={"command": command, "bytes": len(raw.encode("utf-8", "replace"))},
        )
    except Exception as exc:
        return AIProviderPlanResult(
            ok=False,
            provider="codex_mcp",
            reason=_provider_user_fallback_reason("Codex", exc),
            metadata={"command": command, "technical_error": str(exc)},
        )


def generate_selected_provider_plan(
    prompt: str,
    base_plan: EditPlan,
    *,
    document: Any | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = QWEN_EXECUTOR_TIMEOUT_SECONDS,
) -> AIProviderPlanResult:
    """Ask the selected provider for an EditPlan, then validate before use."""
    statuses = ai_provider_readiness(env)
    selected = selected_ai_provider_id(env)
    effective = effective_generation_provider_id(env)
    if effective == "claude_mcp":
        return _generate_claude_provider_plan(
            prompt,
            base_plan,
            document=document,
            env=env,
            timeout_seconds=timeout_seconds,
        )
    if effective == "local_llm":
        return _generate_local_llm_provider_plan(
            prompt,
            base_plan,
            document=document,
            env=env,
            timeout_seconds=timeout_seconds,
        )
    if effective == "codex_mcp":
        return _generate_codex_provider_plan(
            prompt,
            base_plan,
            document=document,
            env=env,
            timeout_seconds=timeout_seconds,
        )
    if effective != QWEN_LOCAL_PROVIDER_ID:
        if selected == "claude_mcp":
            row = statuses.get("claude_mcp") or {}
            if row.get("available") and row.get("executor_wired") and not row.get("direct_generation_enabled"):
                return AIProviderPlanResult(
                    ok=False,
                    provider=selected,
                    reason=(
                        "Claude direct EditPlan generation is disabled by "
                        f"{AI_CLAUDE_DIRECT_EXECUTOR_ENV}=0. Clear that override to let Tiger Studio "
                        "auto-run Claude plans through Review validation."
                    ),
                    metadata={"effective_generation_provider": effective, "direct_executor_disabled": True},
                )
            return AIProviderPlanResult(
                ok=False,
                provider=selected,
                reason=(
                    "Claude 직접 Plan 생성을 위한 CLI/MCP 연결이 아직 준비되지 않았습니다. "
                    "`Claude CLI 열기`를 눌러 Tiger Studio 작업 폴더의 Claude Code를 열거나 설정을 확인하세요."
                ),
                metadata={"effective_generation_provider": effective, "terminal_handoff": True},
            )
        return AIProviderPlanResult(
            ok=False,
            provider=selected,
            reason="선택한 AI가 아직 직접 플랜을 만들 수 없어 기본 자동 규칙을 사용합니다.",
            metadata={"effective_generation_provider": effective},
        )
    row = statuses.get(QWEN_LOCAL_PROVIDER_ID) or {}
    endpoint = str(row.get("endpoint") or "").strip()
    url = _provider_chat_url(endpoint)
    if not url:
        save_qwen_executor_state(ok=False, error="무료 AI 서버 주소가 없습니다.")
        return AIProviderPlanResult(
            ok=False,
            provider=QWEN_LOCAL_PROVIDER_ID,
            reason="무료 AI 서버 주소가 없어 기본 자동 규칙을 사용합니다.",
        )
    try:
        import urllib.request

        body = {
            "model": QWEN_LOCAL_MANIFEST["model_ref"],
            "messages": _qwen_executor_messages(prompt, base_plan, document),
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=max(1, int(timeout_seconds))) as response:
            raw = response.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise ValueError("AI 응답에 choices가 없습니다.")
        first = choices[0] or {}
        message = first.get("message") if isinstance(first, dict) else {}
        content = ""
        if isinstance(message, Mapping):
            content = str(message.get("content") or "")
        if not content and isinstance(first, Mapping):
            content = str(first.get("text") or "")
        json_text = _extract_json_object(content)
        json_text, repair_notes = _repair_provider_plan_json_from_baseline(json_text, base_plan)
        result = validate_provider_plan_json(QWEN_LOCAL_PROVIDER_ID, json_text)
        if not result.ok or result.plan is None:
            save_qwen_executor_state(ok=False, error=result.reason or "무료 AI 응답에서 유효한 EditPlan을 만들지 못했습니다.")
            return result
        metadata = dict(result.plan.metadata or {})
        metadata.update(
            {
                "prompt_text": str(prompt or "").strip(),
                "prompt_mode": "qwen_local",
                "provider_id": QWEN_LOCAL_PROVIDER_ID,
                "provider_executor": "qwen_local_openai_compatible",
                "provider_endpoint": endpoint,
                "fallback_used": False,
                "provider_repair_notes": repair_notes,
            }
        )
        plan = replace(result.plan, provider=QWEN_LOCAL_PROVIDER_ID, metadata=metadata)
        save_qwen_executor_state(ok=True, error="")
        return AIProviderPlanResult(
            ok=True,
            provider=QWEN_LOCAL_PROVIDER_ID,
            plan=plan,
            metadata={"endpoint": endpoint, "url": url, "bytes": len(raw.encode("utf-8", "replace"))},
        )
    except Exception as exc:
        reason = _qwen_user_fallback_reason(exc)
        save_qwen_executor_state(ok=False, error=reason)
        return AIProviderPlanResult(
            ok=False,
            provider=QWEN_LOCAL_PROVIDER_ID,
            reason=reason,
            metadata={"endpoint": endpoint, "url": url, "technical_error": str(exc)},
        )


def provider_status_label(env: Mapping[str, str] | None = None) -> str:
    statuses = ai_provider_readiness(env)
    selected = selected_ai_provider_id(env)
    current = effective_generation_provider_id(env)
    row = statuses.get(selected) or {}
    qwen = statuses.get(QWEN_LOCAL_PROVIDER_ID) or {}
    label = provider_user_label(selected)
    reason = str(row.get("reason") or "").strip()
    if selected == QWEN_LOCAL_PROVIDER_ID and row.get("setup_state") == "executor_failed":
        return (
            "무료 AI 서버 주소는 저장되어 있지만 마지막 호출이 실패했습니다. "
            "설정 버튼에서 서버를 다시 시작하거나 무료 AI 설치/연결을 다시 실행하세요."
        )
    if selected == "claude_mcp" and row.get("setup_state") == "executor_failed":
        return (
            "Claude CLI는 보이지만 마지막 앱 내부 호출이 실패했습니다. "
            "다시 시도하면 Claude direct Plan 생성을 재검증하고, 필요하면 설정에서 Claude Code 터미널을 열어 확인하세요."
        )
    if selected != current:
        if selected == QWEN_LOCAL_PROVIDER_ID and not row.get("available"):
            return "현재는 규칙 모드로 플랜을 만듭니다. 기본 무료 AI는 아직 설치되지 않았습니다."
        if selected == "claude_mcp" and row.get("available") and row.get("executor_wired") and not row.get("direct_generation_enabled"):
            return f"Claude 직접 Plan 생성이 {AI_CLAUDE_DIRECT_EXECUTOR_ENV}=0 override로 꺼져 있습니다."
        if selected == "claude_mcp" and row.get("available"):
            return "Claude MCP가 등록되어 있습니다. `Claude CLI 열기`는 앱 내부 Plan 대신 Claude Code 터미널을 엽니다."
        if selected == "local_llm" and not row.get("available"):
            return "로컬 LLM 명령이 설정되지 않아 지금은 규칙 모드로 플랜을 만듭니다."
        if row.get("available"):
            if selected == QWEN_LOCAL_PROVIDER_ID:
                return "무료 AI 연결 완료. 현재 Plan은 기본 자동 규칙으로 생성됩니다. 모델이 직접 명령을 해석하는 기능은 다음 단계에서 연결됩니다."
            return f"{label} 연결 완료. 현재 Plan은 기본 자동 규칙으로 생성됩니다. 모델이 직접 명령을 해석하는 기능은 다음 단계에서 연결됩니다."
        if selected in {"codex_mcp", "claude_mcp", "local_llm"}:
            return f"{label} 연결이 설정되지 않아 지금은 규칙 모드로 플랜을 만듭니다."
        return f"{label}를 사용할 수 없어 지금은 규칙 모드로 플랜을 만듭니다."
    if selected == "rule_based":
        if qwen and not qwen.get("available"):
            return "현재는 규칙 모드입니다. 기본 무료 AI는 아직 설치되지 않았습니다."
        return "현재는 규칙 모드입니다."
    if selected == QWEN_LOCAL_PROVIDER_ID and row.get("available") and row.get("executor_wired"):
        return "무료 AI가 편집 명령을 직접 해석합니다. Plan 후 검토 화면에서 확인하세요."
    if selected == "claude_mcp" and row.get("available") and row.get("direct_generation_enabled"):
        return "Claude 직접 Plan 생성 가능. 생성된 작업은 Review에서 확인 후 적용합니다."
    if selected == "claude_mcp" and row.get("available") and row.get("executor_wired"):
        return "Claude Code 터미널 사용 가능. `Claude CLI 열기`를 누르면 터미널을 열고 입력 명령을 전달합니다."
    if selected == "claude_mcp" and row.get("available"):
        return "Claude MCP 등록됨. Claude Code 터미널에서 Tiger Studio 도구를 사용할 수 있습니다."
    if selected == "local_llm" and row.get("available") and row.get("executor_wired"):
        return "로컬 LLM 실행 가능. `로컬 LLM 실행`을 누르면 편집 명령을 직접 해석해 Review용 Plan을 만듭니다."
    if row.get("available"):
        return f"현재 AI: {label}"
    return "현재는 규칙 모드입니다."


def validate_manual_plan_json(text: str) -> AIProviderPlanResult:
    try:
        plan = validate_edit_plan_json(text)
    except Exception as exc:
        return AIProviderPlanResult(ok=False, provider="manual_json", reason=str(exc))
    return AIProviderPlanResult(
        ok=True,
        provider="manual_json",
        plan=plan,
        metadata={"bytes": len(str(text).encode("utf-8"))},
    )


def validate_provider_plan_json(provider_id: str, text: str) -> AIProviderPlanResult:
    provider = _normalized_provider_id(provider_id) or str(provider_id or "").strip() or "unknown"
    repaired_fields: list[str] = []
    try:
        payload = json.loads(str(text or ""))
        if isinstance(payload, Mapping):
            payload, repaired_fields = _repair_provider_plan_payload(payload)
            text = json.dumps(payload, ensure_ascii=False)
        plan = validate_edit_plan_json(text)
        plan = replace(plan, provider=provider)
    except Exception as exc:
        return AIProviderPlanResult(ok=False, provider=provider, reason=str(exc))
    return AIProviderPlanResult(
        ok=True,
        provider=provider,
        plan=plan,
        metadata={
            "bytes": len(str(text).encode("utf-8")),
            "validated_provider": provider,
            "provider_repairs": repaired_fields,
        },
    )


def provider_snapshot(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    statuses = ai_provider_readiness(env)
    selected_provider = selected_ai_provider_id(env)
    default_provider = default_ai_provider_id(env)
    effective_provider = effective_generation_provider_id(env)
    user_state = provider_user_state(env, provider_id=selected_provider)
    return {
        "schema_version": 1,
        "selected_provider": selected_provider,
        "default_provider": default_provider,
        "effective_generation_provider": effective_provider,
        "fallback_reason": ""
        if selected_provider == effective_provider
        else str((statuses.get(selected_provider) or {}).get("reason") or "Provider unavailable; using rule-based fallback."),
        "provider_order": list(PROVIDER_DISPLAY_ORDER),
        "qwen_manifest": dict(QWEN_LOCAL_MANIFEST),
        "qwen_install_plan": qwen_install_plan(),
        "user_state": user_state,
        "providers": statuses,
        "supported": list(SUPPORTED_AI_PROVIDERS),
        "cloud_required": False,
        "automation_mcp": {
            "server_command": default_mcp_server_command(),
            "tool_names": [
                "tigercapture_ping",
                "tigercapture_schema",
                "tigercapture_list_commands",
                "tigercapture_execute_command",
                "tigercapture_list_actions",
                "tigercapture_get_action_schema",
                "tigercapture_preview_action",
                "tigercapture_execute_action",
                "tigercapture_execute_sequence",
            ],
            "registered_commands_only": True,
        },
    }


def provider_snapshot_json() -> str:
    return json.dumps(provider_snapshot(), ensure_ascii=False, sort_keys=True)
