"""Persistent settings for local transcription backends.

The local ASR path must not depend on hidden environment variables.  This
module stores user-selected model locations in the per-user TigerCapture data
directory and keeps tests isolated through an explicit settings-file override.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any


SETTINGS_FILE_ENV = "TIGERCAPTURE_TRANSCRIPTION_SETTINGS_FILE"
DISABLE_HF_CACHE_DISCOVERY_ENV = "TIGERCAPTURE_DISABLE_HF_WHISPER_CACHE_DISCOVERY"
LOCAL_WHISPER_MODEL_KEY = "local_whisper_model_path"
LOCAL_MODEL_DIR_KEY = "local_model_dir"


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def transcription_settings_path() -> Path:
    override = os.environ.get(SETTINGS_FILE_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    try:
        from app.paths import runtime_data_dir

        return runtime_data_dir() / "transcription_settings.json"
    except Exception:
        return Path.cwd() / "transcription_settings.json"


def _normalize_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _read_settings_file(path: Path | None = None) -> dict[str, Any]:
    settings_path = path or transcription_settings_path()
    try:
        if not settings_path.exists():
            return {}
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_settings_file(payload: dict[str, Any], path: Path | None = None) -> None:
    settings_path = path or transcription_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = settings_path.with_suffix(settings_path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(settings_path)


def read_transcription_settings() -> dict[str, Any]:
    return dict(_read_settings_file())


def local_whisper_model_path_status(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {"configured": False, "exists": False, "path": ""}
    model_path = _normalize_path(path)
    exists = model_path.exists()
    indicators: list[str] = []
    if model_path.is_dir():
        for name in ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"):
            if (model_path / name).exists():
                indicators.append(name)
    elif model_path.is_file() and model_path.suffix.lower() in {".bin", ".pt"}:
        indicators.append(model_path.suffix.lower())
    return {
        "configured": True,
        "path": str(model_path),
        "exists": exists,
        "kind": "directory" if model_path.is_dir() else "file" if model_path.is_file() else "missing",
        "likely_faster_whisper_model": bool(exists and (indicators or model_path.is_dir())),
        "indicators": indicators,
    }


def configured_local_whisper_model_path() -> Path | None:
    value = str(read_transcription_settings().get(LOCAL_WHISPER_MODEL_KEY) or "").strip()
    return _normalize_path(value) if value else None


def configured_local_model_dir() -> Path | None:
    value = str(read_transcription_settings().get(LOCAL_MODEL_DIR_KEY) or "").strip()
    return _normalize_path(value) if value else None


def configured_whisper_model_candidates(model_size: str = "small") -> list[Path]:
    candidates: list[Path] = []
    model_path = configured_local_whisper_model_path()
    if model_path is not None:
        candidates.append(model_path)
    model_dir = configured_local_model_dir()
    if model_dir is not None:
        base = model_dir / "whisper"
        candidates.extend([base / model_size, base / f"{model_size}.pt", base / f"{model_size}.bin"])
    return candidates


def huggingface_hub_cache_roots() -> list[Path]:
    if _truthy(os.environ.get(DISABLE_HF_CACHE_DISCOVERY_ENV)):
        return []
    roots: list[Path] = []
    hub_cache = os.environ.get("HF_HUB_CACHE", "").strip()
    if hub_cache:
        roots.append(_normalize_path(hub_cache))
    hf_home = os.environ.get("HF_HOME", "").strip()
    if hf_home:
        roots.append(_normalize_path(hf_home) / "hub")
    roots.append(_normalize_path(Path.home() / ".cache" / "huggingface" / "hub"))
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        roots.append(_normalize_path(Path(local_appdata) / "huggingface" / "hub"))
    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            out.append(root)
    return out


def cached_faster_whisper_model_candidates(model_size: str = "small") -> list[Path]:
    size = str(model_size or "small").strip()
    repo_names = [f"models--Systran--faster-whisper-{size}"]
    candidates: list[Path] = []
    for root in huggingface_hub_cache_roots():
        for repo_name in repo_names:
            snapshots = root / repo_name / "snapshots"
            if not snapshots.exists():
                continue
            try:
                snapshot_dirs = [path for path in snapshots.iterdir() if path.is_dir()]
            except Exception:
                snapshot_dirs = []
            snapshot_dirs.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
            for snapshot in snapshot_dirs:
                status = local_whisper_model_path_status(snapshot)
                if status.get("likely_faster_whisper_model"):
                    candidates.append(snapshot)
    return candidates


def local_whisper_model_candidates(model_size: str = "small") -> list[Path]:
    candidates = configured_whisper_model_candidates(model_size)
    candidates.extend(cached_faster_whisper_model_candidates(model_size))
    out: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def cached_faster_whisper_models_state(model_sizes: tuple[str, ...] = ("small", "base", "medium", "large-v3", "tiny")) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for size in model_sizes:
        for path in cached_faster_whisper_model_candidates(size):
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            status = local_whisper_model_path_status(path)
            status["model_size"] = size
            status["source"] = "huggingface_cache"
            rows.append(status)
    return rows


def save_local_whisper_model_path(path: str | Path, *, require_exists: bool = True) -> dict[str, Any]:
    model_path = _normalize_path(path)
    status = local_whisper_model_path_status(model_path)
    if require_exists and not bool(status.get("exists")):
        return {
            "ok": False,
            "reason": "model_path_missing",
            "settings_path": str(transcription_settings_path()),
            "model_path": str(model_path),
        }
    settings = read_transcription_settings()
    settings[LOCAL_WHISPER_MODEL_KEY] = str(model_path)
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_settings_file(settings)
    return {
        "ok": True,
        "settings_path": str(transcription_settings_path()),
        "local_whisper_model": status,
    }


def save_local_model_dir(path: str | Path, *, require_exists: bool = True) -> dict[str, Any]:
    model_dir = _normalize_path(path)
    if require_exists and not model_dir.exists():
        return {
            "ok": False,
            "reason": "model_dir_missing",
            "settings_path": str(transcription_settings_path()),
            "model_dir": str(model_dir),
        }
    settings = read_transcription_settings()
    settings[LOCAL_MODEL_DIR_KEY] = str(model_dir)
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_settings_file(settings)
    return {
        "ok": True,
        "settings_path": str(transcription_settings_path()),
        "local_model_dir": str(model_dir),
        "exists": model_dir.exists(),
    }


def clear_local_transcription_settings() -> dict[str, Any]:
    settings = read_transcription_settings()
    removed = []
    for key in (LOCAL_WHISPER_MODEL_KEY, LOCAL_MODEL_DIR_KEY):
        if key in settings:
            removed.append(key)
            settings.pop(key, None)
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_settings_file(settings)
    return {
        "ok": True,
        "settings_path": str(transcription_settings_path()),
        "removed": removed,
    }


def local_transcription_settings_state() -> dict[str, Any]:
    settings = read_transcription_settings()
    model_path = str(settings.get(LOCAL_WHISPER_MODEL_KEY) or "").strip()
    model_dir = str(settings.get(LOCAL_MODEL_DIR_KEY) or "").strip()
    model_dir_path = _normalize_path(model_dir) if model_dir else None
    return {
        "settings_path": str(transcription_settings_path()),
        "local_whisper_model": local_whisper_model_path_status(model_path),
        "local_model_dir": {
            "configured": bool(model_dir_path),
            "path": str(model_dir_path) if model_dir_path else "",
            "exists": bool(model_dir_path and model_dir_path.exists()),
        },
        "cached_faster_whisper_models": cached_faster_whisper_models_state(),
        "updated_at": settings.get("updated_at", ""),
    }


__all__ = [
    "DISABLE_HF_CACHE_DISCOVERY_ENV",
    "SETTINGS_FILE_ENV",
    "cached_faster_whisper_model_candidates",
    "cached_faster_whisper_models_state",
    "clear_local_transcription_settings",
    "configured_local_model_dir",
    "configured_local_whisper_model_path",
    "configured_whisper_model_candidates",
    "huggingface_hub_cache_roots",
    "local_transcription_settings_state",
    "local_whisper_model_candidates",
    "local_whisper_model_path_status",
    "read_transcription_settings",
    "save_local_model_dir",
    "save_local_whisper_model_path",
    "transcription_settings_path",
]
