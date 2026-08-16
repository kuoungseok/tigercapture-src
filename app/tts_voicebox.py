"""Optional Voicebox (jamiepine/voicebox) sidecar provider boundary."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.tts_synthesis import VoiceSynthesisResult


VOICEBOX_PROVIDER_ID = "voicebox_sidecar"
VOICEBOX_SCHEMA_VERSION = "tigercapture.tts_voicebox.v1"
VOICEBOX_ENV_ROOT = "TIGERCAPTURE_VOICEBOX_ROOT"
VOICEBOX_DEFAULT_ENDPOINT = "http://127.0.0.1:8000"
VOICEBOX_DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "external" / "tools" / "tts" / "voicebox"
VOICEBOX_REPOSITORY = "https://github.com/jamiepine/voicebox"
VOICEBOX_LICENSE_NOTICE = (
    "Voicebox (jamiepine/voicebox) is MIT-licensed. Its bundled TTS engines "
    "(Qwen3-TTS, LuxTTS, Chatterbox, HumeAI TADA, Kokoro, etc.) download their "
    "own weights from Hugging Face on first use under their individual "
    "licenses. Run it as an optional local sidecar; keep engine caches and "
    "voice profiles out of the closed editor source tree."
)


@dataclass(frozen=True)
class VoiceboxRootStatus:
    root: str
    exists: bool
    valid_install: bool
    python_path: str = ""
    entry_path: str = ""
    requirements_path: str = ""
    missing: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "exists": bool(self.exists),
            "valid": bool(self.valid_install),
            "valid_install": bool(self.valid_install),
            "runtime_ready": bool(self.python_path),
            "python_path": self.python_path,
            "entry_path": self.entry_path,
            "requirements_path": self.requirements_path,
            "model_count": 0,
            "model_names": [],
            "voice_rows": [],
            "missing": list(self.missing),
        }


def _path_text(value: Any) -> str:
    return str(value or "").strip().strip('"')


def voicebox_default_root() -> Path:
    return VOICEBOX_DEFAULT_ROOT


def voicebox_entry_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else VOICEBOX_DEFAULT_ROOT
    return base / "backend" / "main.py"


def voicebox_requirements_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else VOICEBOX_DEFAULT_ROOT
    return base / "requirements.txt"


def voicebox_python_path(root: str | Path | None = None) -> Path:
    base = Path(root).expanduser() if root else VOICEBOX_DEFAULT_ROOT
    candidates = [
        base / ".venv" / "Scripts" / "python.exe",
        base / "venv" / "Scripts" / "python.exe",
        base / "backend" / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _candidate_root(env: Mapping[str, str] | None = None, root: str | Path | None = None) -> Path:
    if root not in ("", None):
        return Path(root).expanduser()
    source = env or {}
    explicit = _path_text(source.get(VOICEBOX_ENV_ROOT))
    return Path(explicit).expanduser() if explicit else VOICEBOX_DEFAULT_ROOT


def voicebox_root_status(
    root: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> VoiceboxRootStatus:
    path = _candidate_root(env, root)
    entry_path = voicebox_entry_path(path)
    requirements_path = voicebox_requirements_path(path)
    python_path = voicebox_python_path(path)
    missing: list[str] = []
    if not path.exists():
        missing.append("root")
    if not entry_path.exists():
        missing.append("backend/main.py")
    if not requirements_path.exists():
        missing.append("requirements.txt")
    if not python_path.exists():
        missing.append(".venv/Scripts/python.exe")
    valid_install = path.exists() and entry_path.exists() and requirements_path.exists()
    return VoiceboxRootStatus(
        root=str(path),
        exists=path.exists(),
        valid_install=valid_install,
        python_path=str(python_path) if python_path.exists() else "",
        entry_path=str(entry_path) if entry_path.exists() else "",
        requirements_path=str(requirements_path) if requirements_path.exists() else "",
        missing=tuple(missing),
    )


def voicebox_server_command(
    root: str | Path,
    *,
    endpoint: str = VOICEBOX_DEFAULT_ENDPOINT,
) -> list[str]:
    path = Path(root).expanduser()
    python_path = voicebox_python_path(path)
    host = "127.0.0.1"
    port = "8000"
    try:
        parsed = urlparse(endpoint)
        if parsed.hostname:
            host = parsed.hostname
        if parsed.port:
            port = str(parsed.port)
    except Exception:
        pass
    executable = str(python_path) if python_path.exists() else "python"
    return [executable, "-m", "backend.main", "--host", host, "--port", port]


def voicebox_profile_rows(endpoint: str, *, timeout_s: float = 1.0) -> list[dict[str, Any]]:
    url = str(endpoint or VOICEBOX_DEFAULT_ENDPOINT).rstrip("/") + "/profiles"
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=max(0.2, float(timeout_s or 1.0))) as response:
            payload = json.loads(response.read().decode("utf-8") or "[]")
    except Exception:
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        rows.append(
            {
                "id": str(item.get("id") or ""),
                "label": str(item.get("name") or item.get("id") or ""),
                "language": str(item.get("language") or ""),
                "voice_type": str(item.get("voice_type") or ""),
                "default_engine": str(item.get("default_engine") or ""),
            }
        )
    return rows


def voicebox_provider_status(
    env: Mapping[str, str] | None = None,
    root: str | Path | None = None,
    *,
    endpoint: str = VOICEBOX_DEFAULT_ENDPOINT,
) -> dict[str, Any]:
    status = voicebox_root_status(root, env)
    installed = bool(status.valid_install)
    runtime_ready = bool(status.python_path)
    from app.tts_sidecar_runtime import tts_endpoint_health

    health = tts_endpoint_health(endpoint, timeout_s=0.4)
    server_running = bool(health.get("running"))
    profile_rows = voicebox_profile_rows(endpoint, timeout_s=1.0) if server_running else []
    if installed:
        setup_state = "ready_to_start" if (server_running or runtime_ready) else "needs_runtime"
    else:
        setup_state = "incomplete_install" if status.exists else "needs_install"
    if server_running:
        reason = f"Voicebox sidecar is running with {len(profile_rows)} voice profile(s) available."
    elif installed and runtime_ready:
        reason = "Voicebox sidecar is installed; start the server, then create or select a voice profile."
    elif installed:
        reason = "Voicebox source is downloaded, but no local Python runtime was detected for backend/main.py."
    elif status.exists:
        reason = "A partial Voicebox folder was found; missing " + ", ".join(status.missing)
    else:
        reason = "Voicebox sidecar is not downloaded under external/tools/tts/voicebox."
    root_dict = status.to_dict()
    root_dict["voice_rows"] = profile_rows
    root_dict["model_count"] = len(profile_rows)
    root_dict["model_names"] = [row["id"] for row in profile_rows]
    return {
        "schema": VOICEBOX_SCHEMA_VERSION,
        "provider_id": VOICEBOX_PROVIDER_ID,
        "label": "Voicebox",
        "kind": "tts",
        "configured": installed,
        "installed": installed,
        "available": bool(installed and (server_running or runtime_ready)),
        "setup_needed": not installed,
        "setup_state": setup_state,
        "requires_network": False,
        "local_first": True,
        "requires_server": True,
        "requires_voice_profile": True,
        "endpoint": endpoint,
        "root": root_dict,
        "reason": reason,
        "server_command": voicebox_server_command(status.root, endpoint=endpoint) if installed else [],
        "server_message": (
            "Start backend/main.py from the connected Voicebox sidecar, then create a voice profile at "
            f"{endpoint}/docs before generating."
            if installed
            else "Download or connect Voicebox before starting the server."
        ),
        "supports": [
            "voice_cloning",
            "multi_engine_tts",
            "subtitle_to_voice",
            "character_narration",
            "local_sidecar",
        ],
        "license": {
            "engine": "Voicebox",
            "license": "MIT",
            "notice": VOICEBOX_LICENSE_NOTICE,
            "bundle_policy": "optional_sidecar_only",
        },
    }


def voicebox_install_plan(install_root: str | Path | None = None) -> dict[str, Any]:
    target = Path(install_root).expanduser() if install_root else VOICEBOX_DEFAULT_ROOT
    script = Path(__file__).resolve().parents[1] / "tools" / "install_voicebox.py"
    return {
        "schema": VOICEBOX_SCHEMA_VERSION,
        "provider_id": VOICEBOX_PROVIDER_ID,
        "title": "Download Voicebox sidecar",
        "target_root": str(target),
        "requires_network": True,
        "requires_user_consent": True,
        "estimated_download": "~150 MB source checkout; TTS engine weights download from Hugging Face on first use.",
        "license_notice": VOICEBOX_LICENSE_NOTICE,
        "source": {
            "engine": "Voicebox",
            "repository": VOICEBOX_REPOSITORY,
            "backend_entry": "backend/main.py",
        },
        "steps": [
            {
                "id": "download_repo",
                "label": "Download Voicebox",
                "description": "Clone jamiepine/voicebox into external/tools/tts/voicebox.",
            },
            {
                "id": "install_runtime",
                "label": "Install backend Python dependencies",
                "description": "Create a .venv under the sidecar root and install requirements.txt (Python 3.12+).",
            },
            {
                "id": "start_backend",
                "label": "Start backend/main.py",
                "description": "Run `python -m backend.main --host 127.0.0.1 --port 8000` from the sidecar root.",
            },
            {
                "id": "create_voice_profile",
                "label": "Create a voice profile",
                "description": "Open http://127.0.0.1:8000/docs and use POST /profiles (or /profiles/import) to add a voice before generating.",
            },
        ],
        "commands": {
            "download": [
                "python",
                str(script),
                "--target",
                str(target),
            ],
        },
        "ui_copy": {
            "primary": "Download Voicebox",
            "secondary": "Connect existing Voicebox",
            "safe_default": "Voice profiles, samples, and downloaded model caches stay on this machine.",
            "why": "Adds Qwen3-TTS/LuxTTS/Chatterbox/TADA/Kokoro-based voice cloning as a local sidecar option.",
        },
        "actions_after_install": [
            {"action": "tts.provider.select", "params": {"provider_id": VOICEBOX_PROVIDER_ID}},
            {"action": "tts.connect_installed_sidecar", "params": {"provider_id": VOICEBOX_PROVIDER_ID, "root_path": str(target)}},
            {"action": "tts.provider.status", "params": {"provider_id": VOICEBOX_PROVIDER_ID}},
        ],
    }


def voicebox_install_execution_gate(install_root: str | Path | None = None) -> dict[str, Any]:
    plan = voicebox_install_plan(install_root)
    return {
        "schema": VOICEBOX_SCHEMA_VERSION,
        "ready_to_execute": True,
        "requires_confirmation": True,
        "destructive": False,
        "network_download": True,
        "long_running": True,
        "title": "Confirm Voicebox download",
        "message": (
            "This downloads the optional Voicebox sidecar into external/tools. "
            "It does not add voice profiles, samples, or model caches to Git."
        ),
        "plan": plan,
    }


def connect_installed_voicebox(root_path: str | Path) -> dict[str, Any]:
    status = voicebox_root_status(root_path)
    if not status.valid_install:
        return {
            "schema": VOICEBOX_SCHEMA_VERSION,
            "ok": False,
            "connected": False,
            "status": status.to_dict(),
            "error": "Selected folder is not a complete Voicebox checkout.",
            "missing": list(status.missing),
        }
    return {
        "schema": VOICEBOX_SCHEMA_VERSION,
        "ok": True,
        "connected": True,
        "status": status.to_dict(),
    }


def synthesize_voicebox_voice(
    *,
    text: str,
    output_path: str | Path,
    endpoint: str = VOICEBOX_DEFAULT_ENDPOINT,
    profile_id: str = "",
    language: str = "en",
    engine: str = "",
    timeout_s: float = 180.0,
) -> VoiceSynthesisResult:
    body_text = str(text or "").strip()
    if not body_text:
        raise ValueError("TTS text is empty")
    profile = str(profile_id or "").strip()
    if not profile:
        raise RuntimeError(
            "Voicebox needs a voice profile id. Create one at "
            f"{str(endpoint or VOICEBOX_DEFAULT_ENDPOINT).rstrip('/')}/docs (POST /profiles) and select it in Voice Lab."
        )
    out = Path(output_path).expanduser()
    if not out.is_absolute():
        out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "profile_id": profile,
        "text": body_text,
        "language": str(language or "en"),
    }
    if engine:
        payload["engine"] = str(engine)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = urljoin(str(endpoint or VOICEBOX_DEFAULT_ENDPOINT).rstrip("/") + "/", "generate/stream")
    req = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=max(1.0, float(timeout_s or 180.0))) as response:
            audio = response.read()
    except URLError as exc:
        raise RuntimeError(f"Voicebox API is not reachable at {endpoint}: {exc}") from exc
    if not audio:
        raise RuntimeError("Voicebox API returned empty audio")
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
        endpoint=str(endpoint or VOICEBOX_DEFAULT_ENDPOINT),
        model_name=profile,
    )


__all__ = [
    "VOICEBOX_DEFAULT_ENDPOINT",
    "VOICEBOX_DEFAULT_ROOT",
    "VOICEBOX_ENV_ROOT",
    "VOICEBOX_PROVIDER_ID",
    "VOICEBOX_SCHEMA_VERSION",
    "connect_installed_voicebox",
    "voicebox_default_root",
    "voicebox_entry_path",
    "voicebox_install_execution_gate",
    "voicebox_install_plan",
    "voicebox_profile_rows",
    "voicebox_provider_status",
    "voicebox_python_path",
    "voicebox_requirements_path",
    "voicebox_root_status",
    "voicebox_server_command",
    "synthesize_voicebox_voice",
]
