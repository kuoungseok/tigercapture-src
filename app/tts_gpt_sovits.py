"""Optional GPT-SoVITS sidecar provider boundary."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from app.tts_synthesis import VoiceSynthesisResult


GPT_SOVITS_PROVIDER_ID = "gpt_sovits_sidecar"
GPT_SOVITS_SCHEMA_VERSION = "tigercapture.tts_gpt_sovits.v1"
GPT_SOVITS_ENV_ROOT = "TIGERCAPTURE_GPT_SOVITS_ROOT"
GPT_SOVITS_DEFAULT_ENDPOINT = "http://127.0.0.1:9880"
GPT_SOVITS_DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts" / "gpt-sovits"
GPT_SOVITS_REPOSITORY = "https://github.com/RVC-Boss/GPT-SoVITS"
GPT_SOVITS_LICENSE_NOTICE = (
    "GPT-SoVITS is an optional external voice-cloning/TTS sidecar. Keep the "
    "engine, user reference audio, trained weights, and downloaded models out "
    "of the closed editor source tree."
)


@dataclass(frozen=True)
class GptSoVitsRootStatus:
    root: str
    exists: bool
    valid_install: bool
    available: bool
    python_path: str = ""
    api_path: str = ""
    config_path: str = ""
    preset_count: int = 0
    preset_names: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "exists": bool(self.exists),
            "valid": bool(self.valid_install),
            "valid_install": bool(self.valid_install),
            "available": bool(self.available),
            "runtime_ready": bool(self.python_path),
            "python_path": self.python_path,
            "api_path": self.api_path,
            "config_path": self.config_path,
            "preset_count": int(self.preset_count),
            "preset_names": list(self.preset_names),
            "model_count": int(self.preset_count),
            "model_names": list(self.preset_names),
            "voice_rows": [dict(row) for row in gpt_sovits_voice_rows(self.root)],
            "missing": list(self.missing),
        }


def _path_text(value: Any) -> str:
    return str(value or "").strip().strip('"')


def gpt_sovits_default_root() -> Path:
    return GPT_SOVITS_DEFAULT_ROOT


def gpt_sovits_voice_preset_dir(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else GPT_SOVITS_DEFAULT_ROOT
    return base / "voice_presets"


def gpt_sovits_python_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else GPT_SOVITS_DEFAULT_ROOT
    candidates = [
        base / ".venv" / "Scripts" / "python.exe",
        base / "runtime" / "python.exe",
        base / "runtime" / "python" / "python.exe",
        base / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def gpt_sovits_api_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else GPT_SOVITS_DEFAULT_ROOT
    return base / "api_v2.py"


def gpt_sovits_config_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else GPT_SOVITS_DEFAULT_ROOT
    return base / "GPT_SoVITS" / "configs" / "tts_infer.yaml"


def _candidate_root(env: Mapping[str, str] | None = None, root: str | Path | None = None) -> Path:
    if root not in ("", None):
        return Path(root).expanduser()
    source = env or {}
    explicit = _path_text(source.get(GPT_SOVITS_ENV_ROOT))
    return Path(explicit).expanduser() if explicit else GPT_SOVITS_DEFAULT_ROOT


def _preset_payloads(root: str | Path | None = None) -> list[dict[str, Any]]:
    preset_dir = gpt_sovits_voice_preset_dir(root)
    rows: list[dict[str, Any]] = []
    if not preset_dir.exists():
        return rows
    for path in sorted(preset_dir.glob("*.json"), key=lambda item: item.name.casefold()):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        preset_id = _path_text(payload.get("id")) or path.stem
        label = _path_text(payload.get("label") or payload.get("name")) or preset_id
        rows.append({**payload, "id": preset_id, "label": label, "path": str(path)})
    return rows


def _reference_audio_path(root: str | Path | None, value: Any) -> Path:
    raw = _path_text(value)
    path = Path(raw).expanduser()
    if not path.is_absolute():
        base = Path(root).expanduser() if root else GPT_SOVITS_DEFAULT_ROOT
        path = base / path
    return path


def _reference_audio_ready(root: str | Path | None, value: Any) -> bool:
    raw = _path_text(value)
    if not raw:
        return False
    return _reference_audio_path(root, raw).exists()


def gpt_sovits_voice_rows(root: str | Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for payload in _preset_payloads(root):
        rows.append(
            {
                "id": str(payload.get("id") or ""),
                "label": str(payload.get("label") or payload.get("id") or ""),
                "language": str(payload.get("text_lang") or payload.get("language") or ""),
                "prompt_lang": str(payload.get("prompt_lang") or ""),
                "ref_audio_path": str(payload.get("ref_audio_path") or ""),
                "ready": _reference_audio_ready(root, payload.get("ref_audio_path")),
            }
        )
    return rows


def _voice_preset(root: str | Path | None, preset_id: str) -> dict[str, Any]:
    wanted = str(preset_id or "").strip()
    for payload in _preset_payloads(root):
        if str(payload.get("id") or "") == wanted:
            return payload
    return {}


def gpt_sovits_root_status(
    root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> GptSoVitsRootStatus:
    path = _candidate_root(env, root)
    api_path = gpt_sovits_api_path(path)
    config_path = gpt_sovits_config_path(path)
    python_path = gpt_sovits_python_path(path)
    missing: list[str] = []
    if not path.exists():
        missing.append("root")
    if not api_path.exists():
        missing.append("api_v2.py")
    if not config_path.exists():
        missing.append("GPT_SoVITS/configs/tts_infer.yaml")
    if not python_path.exists():
        missing.append(".venv/Scripts/python.exe or runtime/python.exe")
    presets = _preset_payloads(path)
    ready_presets = [row for row in presets if _reference_audio_ready(path, row.get("ref_audio_path"))]
    valid_install = path.exists() and api_path.exists() and config_path.exists()
    available = bool(valid_install and ready_presets)
    if valid_install and not ready_presets:
        missing.append("voice_presets/*.json with existing ref_audio_path")
    return GptSoVitsRootStatus(
        root=str(path),
        exists=path.exists(),
        valid_install=valid_install,
        available=available,
        python_path=str(python_path) if python_path.exists() else "",
        api_path=str(api_path) if api_path.exists() else "",
        config_path=str(config_path) if config_path.exists() else "",
        preset_count=len(ready_presets),
        preset_names=tuple(str(row.get("id") or "") for row in ready_presets),
        missing=tuple(missing),
    )


def gpt_sovits_server_command(
    root: str | Path,
    *,
    endpoint: str = GPT_SOVITS_DEFAULT_ENDPOINT,
) -> list[str]:
    path = Path(root).expanduser()
    python_path = gpt_sovits_python_path(path)
    api_path = gpt_sovits_api_path(path)
    config_path = gpt_sovits_config_path(path)
    host = "127.0.0.1"
    port = "9880"
    try:
        from urllib.parse import urlparse

        parsed = urlparse(endpoint)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = str(parsed.port)
    except Exception:
        pass
    executable = str(python_path) if python_path.exists() else "python"
    return [executable, str(api_path), "-a", host, "-p", port, "-c", str(config_path)]


def gpt_sovits_provider_status(
    env: Mapping[str, str] | None = None,
    root: str | Path | None = None,
    *,
    endpoint: str = GPT_SOVITS_DEFAULT_ENDPOINT,
) -> dict[str, Any]:
    status = gpt_sovits_root_status(root, env)
    installed = bool(status.valid_install)
    runtime_ready = bool(status.python_path)
    if installed:
        if status.available and runtime_ready:
            setup_state = "ready_to_start"
        elif status.available:
            setup_state = "needs_runtime"
        elif runtime_ready:
            setup_state = "needs_voice_preset"
        else:
            setup_state = "needs_runtime_and_voice_preset"
    else:
        setup_state = "incomplete_install" if status.exists else "needs_install"
    if status.available and runtime_ready:
        reason = f"GPT-SoVITS sidecar detected with {status.preset_count} usable voice preset(s)."
    elif installed and status.available:
        reason = "GPT-SoVITS has a usable voice preset, but no local Python runtime was detected for api_v2.py."
    elif installed and runtime_ready:
        reason = "GPT-SoVITS is downloaded, but no usable voice preset with existing reference audio is configured."
    elif installed:
        reason = "GPT-SoVITS is downloaded, but runtime dependencies and a usable reference voice preset still need setup."
    elif status.exists:
        reason = "A partial GPT-SoVITS folder was found; missing " + ", ".join(status.missing)
    else:
        reason = "GPT-SoVITS sidecar is not downloaded under external/tools/tts/gpt-sovits."
    if not installed:
        server_message = "Download or connect GPT-SoVITS before starting the API server."
    elif not runtime_ready:
        server_message = "Install GPT-SoVITS runtime dependencies or start an existing API server manually before synthesis."
    else:
        server_message = "Start api_v2.py from the connected GPT-SoVITS sidecar."
    return {
        "schema": GPT_SOVITS_SCHEMA_VERSION,
        "provider_id": GPT_SOVITS_PROVIDER_ID,
        "label": "GPT-SoVITS",
        "kind": "tts",
        "configured": bool(status.available),
        "installed": installed,
        "available": bool(status.available),
        "setup_needed": not bool(status.available),
        "setup_state": setup_state,
        "requires_network": False,
        "local_first": True,
        "requires_server": True,
        "requires_reference_audio": True,
        "endpoint": endpoint,
        "root": status.to_dict(),
        "reason": reason,
        "server_command": gpt_sovits_server_command(status.root, endpoint=endpoint) if installed else [],
        "server_message": server_message,
        "supports": [
            "voice_cloning",
            "reference_voice",
            "few_shot_voice",
            "subtitle_to_voice",
            "cross_lingual_tts",
            "local_sidecar",
        ],
        "license": {
            "engine": "GPT-SoVITS",
            "license": "upstream project license",
            "notice": GPT_SOVITS_LICENSE_NOTICE,
            "bundle_policy": "optional_sidecar_only",
        },
    }


def gpt_sovits_install_plan(install_root: str | Path | None = None) -> dict[str, Any]:
    target = Path(install_root).expanduser() if install_root else GPT_SOVITS_DEFAULT_ROOT
    script = Path(__file__).resolve().parents[1] / "tools" / "install_gpt_sovits.py"
    return {
        "schema": GPT_SOVITS_SCHEMA_VERSION,
        "provider_id": GPT_SOVITS_PROVIDER_ID,
        "title": "Download GPT-SoVITS sidecar",
        "target_root": str(target),
        "requires_network": True,
        "requires_user_consent": True,
        "estimated_download": "Large. Repository download first; Python/CUDA dependencies and model weights are separate.",
        "license_notice": GPT_SOVITS_LICENSE_NOTICE,
        "source": {
            "engine": "GPT-SoVITS",
            "repository": GPT_SOVITS_REPOSITORY,
            "api": "api_v2.py",
        },
        "steps": [
            {
                "id": "download_repo",
                "label": "Download GPT-SoVITS",
                "description": "Clone the official RVC-Boss/GPT-SoVITS repository into external/tools/tts/gpt-sovits.",
            },
            {
                "id": "install_runtime",
                "label": "Install Python/CUDA runtime",
                "description": "Use upstream install.ps1/install.sh or a dedicated external .venv; keep it outside the editor process.",
            },
            {
                "id": "configure_voice_preset",
                "label": "Configure reference voice preset",
                "description": "Create voice_presets/*.json with ref_audio_path, prompt_text, prompt_lang, and text_lang.",
            },
            {
                "id": "start_api",
                "label": "Start api_v2.py",
                "description": "Run api_v2.py on 127.0.0.1:9880 and use /tts for synthesis.",
            },
        ],
        "commands": {
            "download": [str(Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"), str(script), "--target", str(target)],
        },
        "ui_copy": {
            "primary": "Download GPT-SoVITS",
            "secondary": "Connect existing GPT-SoVITS",
            "safe_default": "Voice samples, trained weights, and model caches stay on this machine.",
            "why": "Needed for reference-voice cloning and few-shot character narration.",
        },
        "actions_after_install": [
            {"action": "tts.provider.select", "params": {"provider_id": GPT_SOVITS_PROVIDER_ID}},
            {"action": "tts.connect_installed_sidecar", "params": {"provider_id": GPT_SOVITS_PROVIDER_ID, "root_path": str(target)}},
            {"action": "tts.provider.status", "params": {"provider_id": GPT_SOVITS_PROVIDER_ID}},
        ],
    }


def gpt_sovits_install_execution_gate(install_root: str | Path | None = None) -> dict[str, Any]:
    plan = gpt_sovits_install_plan(install_root)
    return {
        "schema": GPT_SOVITS_SCHEMA_VERSION,
        "ready_to_execute": True,
        "requires_confirmation": True,
        "destructive": False,
        "network_download": True,
        "long_running": True,
        "title": "Confirm GPT-SoVITS download",
        "message": (
            "This downloads the optional GPT-SoVITS sidecar into external/tools. "
            "It does not add voice samples, trained weights, or model caches to Git."
        ),
        "plan": plan,
    }


def connect_installed_gpt_sovits(root_path: str | Path) -> dict[str, Any]:
    status = gpt_sovits_root_status(root_path)
    if not status.valid_install:
        return {
            "schema": GPT_SOVITS_SCHEMA_VERSION,
            "ok": False,
            "connected": False,
            "status": status.to_dict(),
            "error": "Selected folder is not a complete GPT-SoVITS repository.",
            "missing": list(status.missing),
        }
    return {
        "schema": GPT_SOVITS_SCHEMA_VERSION,
        "ok": True,
        "connected": True,
        "status": status.to_dict(),
    }


def synthesize_gpt_sovits_voice(
    *,
    text: str,
    output_path: str | Path,
    endpoint: str = GPT_SOVITS_DEFAULT_ENDPOINT,
    root: str | Path | None = None,
    preset_id: str = "",
    language: str = "",
    timeout_s: float = 180.0,
) -> VoiceSynthesisResult:
    body_text = str(text or "").strip()
    if not body_text:
        raise ValueError("TTS text is empty")
    out = Path(output_path).expanduser()
    if not out.is_absolute():
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    status = gpt_sovits_root_status(root)
    if not status.valid_install:
        raise RuntimeError("GPT-SoVITS sidecar is not connected or downloaded.")
    preset = _voice_preset(status.root, preset_id)
    if not preset:
        raise RuntimeError("GPT-SoVITS voice preset is missing. Add voice_presets/<id>.json with reference audio first.")
    ref_audio = _path_text(preset.get("ref_audio_path"))
    if not ref_audio:
        raise RuntimeError("GPT-SoVITS voice preset has no ref_audio_path.")
    if not _reference_audio_ready(status.root, ref_audio):
        raise RuntimeError(f"GPT-SoVITS reference audio does not exist: {_reference_audio_path(status.root, ref_audio)}")
    payload = {
        "text": body_text,
        "text_lang": _path_text(language or preset.get("text_lang") or preset.get("language") or "ja"),
        "ref_audio_path": ref_audio,
        "prompt_lang": _path_text(preset.get("prompt_lang") or preset.get("text_lang") or "ja"),
        "prompt_text": _path_text(preset.get("prompt_text")),
        "text_split_method": _path_text(preset.get("text_split_method") or "cut5"),
        "batch_size": int(preset.get("batch_size") or 1),
        "speed_factor": float(preset.get("speed_factor") or 1.0),
        "media_type": "wav",
        "streaming_mode": False,
    }
    for key in ("top_k", "top_p", "temperature", "repetition_penalty", "sample_steps"):
        if key in preset:
            payload[key] = preset[key]
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = urljoin(str(endpoint or GPT_SOVITS_DEFAULT_ENDPOINT).rstrip("/") + "/", "tts")
    req = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=max(1.0, float(timeout_s or 180.0))) as response:
            audio = response.read()
    except URLError as exc:
        raise RuntimeError(f"GPT-SoVITS API is not reachable at {endpoint}: {exc}") from exc
    if not audio:
        raise RuntimeError("GPT-SoVITS API returned empty audio")
    out.write_bytes(audio)
    duration_ms = 0
    try:
        from app.audio_tracks import probe_audio_duration_ms

        duration_ms = int(probe_audio_duration_ms(out) or 0)
    except Exception:
        duration_ms = 0
    return VoiceSynthesisResult(
        path=out.resolve(),
        byte_count=len(audio),
        duration_ms=max(0, duration_ms),
        endpoint=str(endpoint or GPT_SOVITS_DEFAULT_ENDPOINT),
        model_name=str(preset_id or ""),
    )


__all__ = [
    "GPT_SOVITS_DEFAULT_ENDPOINT",
    "GPT_SOVITS_DEFAULT_ROOT",
    "GPT_SOVITS_ENV_ROOT",
    "GPT_SOVITS_PROVIDER_ID",
    "GPT_SOVITS_SCHEMA_VERSION",
    "connect_installed_gpt_sovits",
    "gpt_sovits_api_path",
    "gpt_sovits_config_path",
    "gpt_sovits_default_root",
    "gpt_sovits_install_execution_gate",
    "gpt_sovits_install_plan",
    "gpt_sovits_provider_status",
    "gpt_sovits_python_path",
    "gpt_sovits_root_status",
    "gpt_sovits_server_command",
    "gpt_sovits_voice_preset_dir",
    "gpt_sovits_voice_rows",
    "synthesize_gpt_sovits_voice",
]
