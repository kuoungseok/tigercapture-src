"""Runtime setup diagnostics for local word-level transcription."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def candidate_whisper_model_paths(root: str | Path = ".") -> list[Path]:
    root_path = Path(root).resolve()
    candidates: list[Path] = []
    env = os.environ.get("TIGERCAPTURE_LOCAL_WHISPER_MODEL", "").strip()
    if env:
        candidates.append(Path(env))
    try:
        from app.transcription_settings import local_whisper_model_candidates

        for size in ("small", "base", "medium"):
            candidates.extend(local_whisper_model_candidates(size))
    except Exception:
        pass
    env_dir = os.environ.get("TIGERCAPTURE_LOCAL_MODEL_DIR", "").strip()
    if env_dir:
        base = Path(env_dir) / "whisper"
        candidates.extend([base / "small", base / "base", base / "medium"])
    base = root_path / "models" / "whisper"
    candidates.extend([base / "small", base / "base", base / "medium"])
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def build_transcription_runtime_setup_report(root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    try:
        from app.transcription_providers import transcription_provider_readiness

        readiness = transcription_provider_readiness()
    except Exception as exc:
        readiness = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    try:
        from app.transcription_settings import local_transcription_settings_state

        settings = local_transcription_settings_state()
    except Exception as exc:
        settings = {"error": f"{type(exc).__name__}: {exc}"}
    candidates = candidate_whisper_model_paths(root_path)
    existing = [path for path in candidates if path.exists()]
    local_whisper = dict(readiness.get("local_whisper") or {})
    runtime_ready = bool(readiness.get("runtime_model_ready"))
    next_actions: list[str] = []
    if not readiness.get("faster_whisper_installed"):
        next_actions.append("Install faster-whisper in the bundled Python environment.")
    if not existing:
        next_actions.append("Run tools/configure_local_whisper_model.py --model-path <local faster-whisper model folder>, use an existing Hugging Face cache model, or place it at models/whisper/small.")
    if existing and not runtime_ready:
        next_actions.append("Rerun tools/qa_descript_lite_p2_transcription.py and check the local_whisper status reason.")
    if runtime_ready:
        next_actions.append("Run tools/qa_descript_lite_readiness.py to refresh Descript-lite claim status.")
    return {
        "kind": "transcription_runtime_setup",
        "ok": True,
        "runtime_model_ready": runtime_ready,
        "candidate_paths": [str(path) for path in candidates],
        "existing_paths": [str(path) for path in existing],
        "environment": {
            "TIGERCAPTURE_LOCAL_WHISPER_MODEL": os.environ.get("TIGERCAPTURE_LOCAL_WHISPER_MODEL", ""),
            "TIGERCAPTURE_LOCAL_MODEL_DIR": os.environ.get("TIGERCAPTURE_LOCAL_MODEL_DIR", ""),
        },
        "settings": settings,
        "provider_readiness": readiness,
        "local_whisper": local_whisper,
        "next_actions": next_actions,
        "user_facing_message": (
            "Local word-level transcription is ready."
            if runtime_ready
            else "Local word-level transcription needs a saved faster-whisper model folder; no cloud download is attempted automatically."
        ),
    }


__all__ = ["build_transcription_runtime_setup_report", "candidate_whisper_model_paths"]
