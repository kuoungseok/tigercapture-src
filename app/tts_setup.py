"""Local TTS provider setup contracts.

The product direction needs anime/subculture voice generation, but the current
reference engine is a large AGPL Style-Bert-VITS2 sidecar. Keep this module as
the safe boundary: detect, explain, and expose setup actions without importing
the heavy torch stack into the editor process.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Mapping

try:
    from PySide6.QtCore import QSettings
except Exception:  # pragma: no cover - non-Qt test hosts
    QSettings = None  # type: ignore


TTS_PROVIDER_ID = "style_bert_vits2_sidecar"
TTS_SCHEMA_VERSION = "tigercapture.tts_setup.v1"
TTS_SETTINGS_ORG = "TigerCapture"
TTS_SETTINGS_APP = "TigerCapture"
TTS_ROOT_SETTINGS_KEY = "tts/style_bert_vits2/root"
TTS_ENDPOINT_SETTINGS_KEY = "tts/style_bert_vits2/endpoint"
TTS_AUTO_START_SETTINGS_KEY = "tts/style_bert_vits2/auto_start"
TTS_DEFAULT_ENDPOINT = "http://127.0.0.1:5000"
TTS_DEFAULT_LOCAL_ROOT = Path(r"D:\TTS\sbv2\Style-Bert-VITS2")
TTS_REPO_SIDECAR_ROOT = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts" / "style-bert-vits2"
TTS_ENV_ROOT = "TIGERCAPTURE_TTS_ROOT"
TTS_ENV_ENDPOINT = "TIGERCAPTURE_TTS_ENDPOINT"
TTS_AGPL_NOTICE = (
    "Style-Bert-VITS2 is AGPL-3.0. Use it as an optional sidecar/provider; "
    "do not copy the engine into the closed editor source tree."
)


@dataclass(frozen=True)
class TtsInstallRootStatus:
    root: str
    exists: bool
    valid: bool
    python_path: str = ""
    server_path: str = ""
    app_kr_path: str = ""
    model_count: int = 0
    model_names: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "exists": bool(self.exists),
            "valid": bool(self.valid),
            "python_path": self.python_path,
            "server_path": self.server_path,
            "app_kr_path": self.app_kr_path,
            "model_count": int(self.model_count),
            "model_names": list(self.model_names),
            "missing": list(self.missing),
        }


def _settings() -> Any:
    if QSettings is None:
        return None
    try:
        return QSettings(TTS_SETTINGS_ORG, TTS_SETTINGS_APP)
    except Exception:
        return None


def _settings_value(key: str, default: Any = "") -> Any:
    settings = _settings()
    if settings is None:
        return default
    try:
        return settings.value(key, default)
    except Exception:
        return default


def _settings_set_value(key: str, value: Any) -> bool:
    settings = _settings()
    if settings is None:
        return False
    try:
        settings.setValue(key, value)
        return True
    except Exception:
        return False


def _path_text(value: Any) -> str:
    return str(value or "").strip().strip('"')


def saved_tts_provider_config() -> dict[str, Any]:
    auto_raw = str(_settings_value(TTS_AUTO_START_SETTINGS_KEY, "false") or "").strip().lower()
    return {
        "root": _path_text(_settings_value(TTS_ROOT_SETTINGS_KEY, "")),
        "endpoint": _path_text(_settings_value(TTS_ENDPOINT_SETTINGS_KEY, TTS_DEFAULT_ENDPOINT)) or TTS_DEFAULT_ENDPOINT,
        "auto_start": auto_raw in {"1", "true", "yes", "on"},
    }


def save_tts_provider_config(
    *,
    root: str | Path = "",
    endpoint: str = TTS_DEFAULT_ENDPOINT,
    auto_start: bool = False,
) -> bool:
    ok = True
    if root not in ("", None):
        ok = _settings_set_value(TTS_ROOT_SETTINGS_KEY, str(Path(root))) and ok
    if endpoint:
        ok = _settings_set_value(TTS_ENDPOINT_SETTINGS_KEY, str(endpoint).strip()) and ok
    ok = _settings_set_value(TTS_AUTO_START_SETTINGS_KEY, "true" if auto_start else "false") and ok
    return bool(ok)


def _candidate_roots(env: Mapping[str, str] | None = None) -> list[Path]:
    source = env if env is not None else os.environ
    explicit_root = _path_text(source.get(TTS_ENV_ROOT) if source is not None else "")
    if explicit_root:
        return [Path(explicit_root).expanduser()]
    raw: list[str] = [
        saved_tts_provider_config().get("root", ""),
        str(TTS_DEFAULT_LOCAL_ROOT),
        str(TTS_REPO_SIDECAR_ROOT),
    ]
    roots: list[Path] = []
    seen: set[str] = set()
    for value in raw:
        if not value:
            continue
        path = Path(value).expanduser()
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def style_bert_vits2_root_status(root: str | Path) -> TtsInstallRootStatus:
    path = Path(root).expanduser()
    python_path = path / "venv" / "Scripts" / "python.exe"
    server_path = path / "server_fastapi.py"
    app_kr_path = path / "App-KR.bat"
    model_root = path / "model_assets"
    missing: list[str] = []
    if not path.exists():
        missing.append("root")
    if not python_path.exists():
        missing.append("venv/Scripts/python.exe")
    if not server_path.exists():
        missing.append("server_fastapi.py")
    if not model_root.exists():
        missing.append("model_assets")
    model_names: list[str] = []
    if model_root.exists():
        try:
            for child in sorted(model_root.iterdir(), key=lambda item: item.name.casefold()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                has_config = (child / "config.json").exists()
                has_weight = any(
                    file.suffix.casefold() in {".safetensors", ".onnx", ".pth", ".pt"}
                    for file in child.iterdir()
                    if file.is_file()
                )
                if has_config and has_weight:
                    model_names.append(child.name)
        except Exception:
            pass
    if model_root.exists() and not model_names:
        missing.append("voice models")
    valid = path.exists() and python_path.exists() and server_path.exists() and bool(model_names)
    return TtsInstallRootStatus(
        root=str(path),
        exists=path.exists(),
        valid=valid,
        python_path=str(python_path) if python_path.exists() else "",
        server_path=str(server_path) if server_path.exists() else "",
        app_kr_path=str(app_kr_path) if app_kr_path.exists() else "",
        model_count=len(model_names),
        model_names=tuple(model_names),
        missing=tuple(missing),
    )


def _best_root_status(env: Mapping[str, str] | None = None) -> TtsInstallRootStatus:
    statuses = [style_bert_vits2_root_status(root) for root in _candidate_roots(env)]
    for row in statuses:
        if row.valid:
            return row
    for row in statuses:
        if row.exists:
            return row
    return style_bert_vits2_root_status(_candidate_roots(env)[0] if _candidate_roots(env) else TTS_DEFAULT_LOCAL_ROOT)


def _endpoint_from_env(env: Mapping[str, str] | None = None) -> str:
    source = env if env is not None else os.environ
    endpoint = _path_text(source.get(TTS_ENV_ENDPOINT) if source is not None else "")
    if endpoint:
        return endpoint
    return saved_tts_provider_config().get("endpoint", TTS_DEFAULT_ENDPOINT) or TTS_DEFAULT_ENDPOINT


def tts_provider_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    root = _best_root_status(env)
    endpoint = _endpoint_from_env(env)
    installed = bool(root.valid)
    setup_state = "ready_to_start" if installed else ("incomplete_install" if root.exists else "needs_install")
    reason = (
        f"Style-Bert-VITS2 sidecar detected with {root.model_count} voice model(s)."
        if installed
        else (
            "A partial Style-Bert-VITS2 folder was found; missing "
            + ", ".join(root.missing)
            if root.exists
            else "Style-Bert-VITS2 sidecar is not installed or not connected."
        )
    )
    return {
        "schema": TTS_SCHEMA_VERSION,
        "provider_id": TTS_PROVIDER_ID,
        "label": "Style-Bert-VITS2",
        "kind": "tts",
        "configured": installed,
        "installed": installed,
        "available": installed,
        "setup_needed": not installed,
        "setup_state": setup_state,
        "requires_network": False,
        "local_first": True,
        "endpoint": endpoint,
        "root": root.to_dict(),
        "reason": reason,
        "server_command": tts_server_command(root.root) if installed else [],
        "supports": [
            "anime_voiceover",
            "character_narration",
            "subtitle_to_voice",
            "ppt_narration",
            "sentence_replacement",
            "local_sidecar",
        ],
        "license": {
            "engine": "Style-Bert-VITS2",
            "license": "AGPL-3.0",
            "notice": TTS_AGPL_NOTICE,
            "bundle_policy": "optional_sidecar_only",
        },
    }


def tts_server_command(root: str | Path) -> list[str]:
    path = Path(root).expanduser()
    python_path = path / "venv" / "Scripts" / "python.exe"
    server_path = path / "server_fastapi.py"
    return [str(python_path), str(server_path)]


def tts_install_plan(install_root: str | Path | None = None) -> dict[str, Any]:
    target = Path(install_root).expanduser() if install_root else TTS_REPO_SIDECAR_ROOT
    return {
        "schema": TTS_SCHEMA_VERSION,
        "provider_id": TTS_PROVIDER_ID,
        "title": "Install local anime/subculture TTS",
        "target_root": str(target),
        "requires_network": True,
        "requires_user_consent": True,
        "estimated_download": "2GB+ including engine, torch stack, BERT assets, and voice models",
        "license_notice": TTS_AGPL_NOTICE,
        "source": {
            "engine": "Style-Bert-VITS2",
            "repository": "https://github.com/litagin02/Style-Bert-VITS2",
            "quickstart_archive": "https://github.com/litagin02/Style-Bert-VITS2/releases/latest/download/sbv2.zip",
        },
        "steps": [
            {
                "id": "choose_location",
                "label": "Choose install location",
                "description": "Use external/tools/tts for a project-managed sidecar, or connect an existing D:/TTS install.",
            },
            {
                "id": "download_engine",
                "label": "Download Style-Bert-VITS2",
                "description": "Fetch the official quickstart archive or clone the upstream repository.",
            },
            {
                "id": "install_python_stack",
                "label": "Install Python/CUDA dependencies",
                "description": "Run the upstream installer in its own venv so TigerCapture stays stable.",
            },
            {
                "id": "download_voice_models",
                "label": "Download or connect voice models",
                "description": "Install default voices or point to user-trained models under model_assets.",
            },
            {
                "id": "verify_server",
                "label": "Verify /voice endpoint",
                "description": "Start server_fastapi.py and confirm models/info before enabling synthesis.",
            },
        ],
        "ui_copy": {
            "primary": "Install local TTS",
            "secondary": "Connect existing TTS",
            "safe_default": "Nothing is uploaded. Voice models stay on this machine unless you choose a cloud provider later.",
            "why": "Needed for character narration, anime voiceover, subtitle-to-voice, PPT narration, and VTuber/actor dialogue.",
        },
        "actions_after_install": [
            {"action": "tts.connect_installed_sidecar", "params": {"root_path": str(target)}},
            {"action": "tts.provider.status", "params": {}},
        ],
    }


def tts_install_execution_gate(install_root: str | Path | None = None) -> dict[str, Any]:
    plan = tts_install_plan(install_root)
    return {
        "schema": TTS_SCHEMA_VERSION,
        "ready_to_execute": True,
        "requires_confirmation": True,
        "destructive": False,
        "network_download": True,
        "long_running": True,
        "title": "Confirm TTS sidecar installation",
        "message": (
            "This will download and install a large AGPL Style-Bert-VITS2 sidecar "
            "outside the editor process. Existing projects are not modified."
        ),
        "plan": plan,
    }


def tts_server_start_plan(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    status = tts_provider_status(env)
    installed = bool(status.get("installed"))
    root = dict(status.get("root") or {})
    return {
        "schema": TTS_SCHEMA_VERSION,
        "provider_id": TTS_PROVIDER_ID,
        "ready": installed,
        "requires_user_action": True,
        "title": "Start local TTS server",
        "endpoint": status.get("endpoint", TTS_DEFAULT_ENDPOINT),
        "cwd": root.get("root", ""),
        "command": list(status.get("server_command") or []),
        "message": (
            "Start server_fastapi.py from the connected Style-Bert-VITS2 sidecar."
            if installed
            else "Install or connect Style-Bert-VITS2 before starting the TTS server."
        ),
    }


def connect_installed_tts(root_path: str | Path, *, endpoint: str = TTS_DEFAULT_ENDPOINT, auto_start: bool = False) -> dict[str, Any]:
    status = style_bert_vits2_root_status(root_path)
    if not status.valid:
        return {
            "schema": TTS_SCHEMA_VERSION,
            "ok": False,
            "connected": False,
            "status": status.to_dict(),
            "error": "Selected folder is not a valid Style-Bert-VITS2 install.",
            "missing": list(status.missing),
        }
    saved = save_tts_provider_config(root=status.root, endpoint=endpoint, auto_start=auto_start)
    return {
        "schema": TTS_SCHEMA_VERSION,
        "ok": bool(saved),
        "connected": bool(saved),
        "status": status.to_dict(),
        "endpoint": endpoint,
        "auto_start": bool(auto_start),
    }


def tts_setup_instructions(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    status = tts_provider_status(env)
    plan = tts_install_plan()
    installed = bool(status.get("installed"))
    return {
        "schema": TTS_SCHEMA_VERSION,
        "provider_id": TTS_PROVIDER_ID,
        "ready": installed,
        "status": status,
        "headline": "Local TTS is ready" if installed else "Set up local TTS",
        "summary": (
            "Use Style-Bert-VITS2 for local character voice generation."
            if installed
            else "Install or connect Style-Bert-VITS2 to unlock voiceover, subtitles-to-voice, and PPT narration."
        ),
        "primary_action": "tts.provider.status" if installed else "tts.install.plan",
        "cards": [
            {
                "id": "local_first",
                "title": "Local-first voice generation",
                "body": "Generated WAV files can be registered in the Media Pool and placed on audio tracks.",
                "ready": installed,
            },
            {
                "id": "license_boundary",
                "title": "Sidecar boundary",
                "body": TTS_AGPL_NOTICE,
                "ready": True,
            },
            {
                "id": "friendly_setup",
                "title": "Guided setup",
                "body": "Offer Install, Connect existing, Start server, and Guide actions instead of exposing raw Python setup first.",
                "ready": True,
            },
        ],
        "install_plan": plan,
    }


def tts_setup_view_model(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    instructions = tts_setup_instructions(env)
    status = dict(instructions.get("status") or {})
    installed = bool(status.get("installed"))
    return {
        "schema": TTS_SCHEMA_VERSION,
        "title": "Voice Lab",
        "subtitle": "Local anime/subculture TTS",
        "state": status.get("setup_state", "needs_install"),
        "ready": installed,
        "status_label": "Ready" if installed else "Setup needed",
        "detail": status.get("reason", ""),
        "endpoint": status.get("endpoint", TTS_DEFAULT_ENDPOINT),
        "root": (status.get("root") or {}).get("root", ""),
        "model_count": int((status.get("root") or {}).get("model_count", 0) or 0),
        "model_names": list((status.get("root") or {}).get("model_names", []) or []),
        "buttons": [
            {"id": "install", "label": "Install", "action": "tts.install.plan", "enabled": not installed},
            {"id": "connect", "label": "Connect", "action": "tts.connect_installed_sidecar", "enabled": True},
            {"id": "start", "label": "Start server", "action": "tts.server.start_plan", "enabled": installed},
            {"id": "guide", "label": "Guide", "action": "tts.setup.instructions", "enabled": True},
        ],
        "warnings": [] if installed else ["TTS is not bundled. Install or connect a local sidecar first."],
        "license_notice": TTS_AGPL_NOTICE,
        "instructions": instructions,
    }


def capcut_voice_tts_provider_row(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    status = tts_provider_status(env)
    installed = bool(status.get("installed"))
    return {
        "id": TTS_PROVIDER_ID,
        "label": "Style-Bert-VITS2 local TTS",
        "kind": "tts",
        "configured": installed,
        "requires_network": False,
        "local_first": True,
        "supports": tuple(status.get("supports") or ()),
        "description": "Local anime/subculture voice generation through an external Style-Bert-VITS2 sidecar.",
        "setup_hint": "Install or connect Style-Bert-VITS2 before generating character voiceover.",
        "status": "configured" if installed else "needs_setup",
        "warning": "" if installed else "Install or connect the local TTS sidecar first.",
        "setup": tts_setup_view_model(env),
    }


__all__ = [
    "TTS_PROVIDER_ID",
    "TTS_SCHEMA_VERSION",
    "capcut_voice_tts_provider_row",
    "connect_installed_tts",
    "save_tts_provider_config",
    "saved_tts_provider_config",
    "style_bert_vits2_root_status",
    "tts_install_execution_gate",
    "tts_install_plan",
    "tts_provider_status",
    "tts_server_start_plan",
    "tts_server_command",
    "tts_setup_instructions",
    "tts_setup_view_model",
]
