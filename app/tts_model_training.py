"""Voice model training bridge for the optional Style-Bert-VITS2 sidecar.

The editor must not import the heavy training stack.  This module only prepares
paths, exposes the upstream Gradio tools, and verifies completed model assets.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import re
import shutil
import subprocess


TTS_MODEL_TRAINING_SCHEMA = "tigercapture.tts_model_training.v1"
TRAINING_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _model_name(value: str) -> str:
    raw = str(value or "").strip()
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("._-")
    if not name:
        raise ValueError("model_name is required")
    if len(name) > 64:
        raise ValueError("model_name must be 64 characters or shorter")
    return name


def _root_from_status(status: Mapping[str, Any]) -> Path:
    root = status.get("root") if isinstance(status.get("root"), Mapping) else {}
    return Path(str(root.get("root") or "")).expanduser()


def _training_tool_ready(root: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for rel in (
        "venv/Scripts/python.exe",
        "gradio_tabs/dataset.py",
        "gradio_tabs/train.py",
        "Dataset.bat",
        "Train.bat",
    ):
        if not (root / rel).exists():
            missing.append(rel)
    return not missing, missing


def _training_command(root: Path, tool: str) -> list[str]:
    python_path = root / "venv" / "Scripts" / "python.exe"
    module = "gradio_tabs.dataset" if tool == "dataset" else "gradio_tabs.train"
    return [str(python_path), "-m", module]


def _model_asset_ready(path: Path) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if not path.exists():
        missing.append("model folder")
    if not (path / "config.json").exists():
        missing.append("config.json")
    has_weight = path.exists() and any(
        item.is_file() and item.suffix.casefold() in {".safetensors", ".onnx", ".pth", ".pt"}
        for item in path.iterdir()
    )
    if not has_weight:
        missing.append("model weights")
    return not missing, missing


def _audio_files(source: Path) -> list[Path]:
    if not source.exists() or not source.is_dir():
        return []
    rows: list[Path] = []
    for item in sorted(source.iterdir(), key=lambda path: path.name.casefold()):
        if item.is_file() and item.suffix.casefold() in TRAINING_AUDIO_EXTENSIONS:
            rows.append(item)
    return rows


def tts_model_training_plan(
    *,
    model_name: str = "",
    source_audio_dir: str | Path = "",
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the safe plan for creating a new local voice model."""
    from app.tts_setup import TTS_PROVIDER_ID, tts_provider_status

    status = tts_provider_status(env)
    root = _root_from_status(status)
    installed = bool(status.get("installed"))
    tools_ready, missing_tools = _training_tool_ready(root)
    name = ""
    try:
        name = _model_name(model_name)
    except ValueError:
        name = ""
    dataset_dir = root / "Data" / name if name else root / "Data"
    raw_dir = dataset_dir / "raw" if name else dataset_dir
    model_asset_dir = root / "model_assets" / name if name else root / "model_assets"
    model_ready, model_missing = _model_asset_ready(model_asset_dir) if name else (False, ["model_name"])
    source_dir = Path(str(source_audio_dir)).expanduser() if str(source_audio_dir or "").strip() else None
    source_files = _audio_files(source_dir) if source_dir is not None else []
    ready = installed and tools_ready and bool(name)
    warnings: list[str] = []
    if installed and not tools_ready:
        warnings.append("training tools are missing from the connected Style-Bert-VITS2 folder")
    if name and model_ready:
        warnings.append("a model asset with this name already exists")
    if source_dir is not None and not source_files:
        warnings.append("source_audio_dir has no supported audio files")
    return {
        "schema": TTS_MODEL_TRAINING_SCHEMA,
        "provider_id": TTS_PROVIDER_ID,
        "ready": ready,
        "installed": installed,
        "model_name": name,
        "root": str(root),
        "dataset_dir": str(dataset_dir),
        "raw_audio_dir": str(raw_dir),
        "transcription_path": str(dataset_dir / "esd.list") if name else "",
        "expected_model_asset_dir": str(model_asset_dir),
        "completed_model_ready": bool(model_ready),
        "completed_model_missing": list(model_missing),
        "source_audio_dir": str(source_dir) if source_dir is not None else "",
        "source_audio_count": len(source_files),
        "missing_tools": missing_tools,
        "commands": {
            "dataset_ui": _training_command(root, "dataset") if installed else [],
            "train_ui": _training_command(root, "train") if installed else [],
        },
        "cwd": str(root),
        "steps": [
            "Put source voice clips in raw_audio_dir or prepare it from source_audio_dir.",
            "Launch Dataset UI, slice audio, then transcribe into Data/<model>/esd.list.",
            "Launch Train UI, run preprocess, then train the model.",
            "When model_assets/<model> contains config.json and weights, register the result.",
        ],
        "warnings": warnings,
    }


def tts_model_training_execution_gate(
    *,
    model_name: str = "",
    source_audio_dir: str | Path = "",
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    plan = tts_model_training_plan(model_name=model_name, source_audio_dir=source_audio_dir, env=env)
    return {
        "schema": TTS_MODEL_TRAINING_SCHEMA,
        "ready_to_execute": bool(plan.get("ready")),
        "requires_confirmation": True,
        "destructive": False,
        "long_running": True,
        "gpu_heavy": True,
        "title": "Create local TTS voice model",
        "message": (
            "This opens the external Style-Bert-VITS2 Dataset and Train tools. "
            "Training can take a long time and uses GPU/VRAM, but the engine stays outside TigerCapture."
        ),
        "plan": plan,
    }


def tts_model_training_prepare_workspace(
    *,
    model_name: str,
    source_audio_dir: str | Path = "",
    overwrite: bool = False,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Create Data/<model>/raw and optionally copy source audio into it."""
    plan = tts_model_training_plan(model_name=model_name, source_audio_dir=source_audio_dir, env=env)
    if not bool(plan.get("ready")):
        raise RuntimeError("TTS model training is not ready. Connect a complete Style-Bert-VITS2 install first.")
    raw_dir = Path(str(plan.get("raw_audio_dir") or "")).expanduser()
    raw_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    skipped: list[str] = []
    source_dir = Path(str(source_audio_dir)).expanduser() if str(source_audio_dir or "").strip() else None
    if source_dir is not None:
        if not source_dir.exists() or not source_dir.is_dir():
            raise FileNotFoundError(f"source_audio_dir not found: {source_dir}")
        for src in _audio_files(source_dir):
            dst = raw_dir / src.name
            if dst.exists() and not overwrite:
                skipped.append(str(dst))
                continue
            shutil.copy2(src, dst)
            copied.append(str(dst))
    return {
        **plan,
        "prepared": True,
        "raw_audio_dir": str(raw_dir),
        "copied_count": len(copied),
        "copied": copied,
        "skipped": skipped,
    }


def tts_model_training_launch_tool(
    *,
    tool: str,
    model_name: str = "",
    source_audio_dir: str | Path = "",
) -> dict[str, Any]:
    """Launch the upstream Dataset or Train Gradio app."""
    key = str(tool or "").strip().lower()
    if key not in {"dataset", "train"}:
        raise ValueError("tool must be 'dataset' or 'train'")
    plan = tts_model_training_plan(model_name=model_name, source_audio_dir=source_audio_dir)
    if not bool(plan.get("installed")):
        raise RuntimeError("Style-Bert-VITS2 is not installed or connected.")
    if plan.get("missing_tools"):
        raise RuntimeError("Training tools are missing: " + ", ".join(plan.get("missing_tools") or []))
    command = list((plan.get("commands") or {}).get("dataset_ui" if key == "dataset" else "train_ui") or [])
    if len(command) < 3:
        raise RuntimeError("Training tool command is incomplete.")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = subprocess.Popen(
        [str(part) for part in command],
        cwd=str(plan.get("cwd") or "") or None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    return {
        "schema": TTS_MODEL_TRAINING_SCHEMA,
        "started": True,
        "tool": key,
        "pid": int(getattr(proc, "pid", 0) or 0),
        "command": command,
        "cwd": str(plan.get("cwd") or ""),
        "model_name": str(plan.get("model_name") or ""),
        "message": (
            "Dataset UI started. Use it to slice and transcribe source voice clips."
            if key == "dataset"
            else "Train UI started. Use it to preprocess, train, and export the model."
        ),
    }


def tts_model_training_register_result(
    *,
    model_name: str,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate model_assets/<model> so Voice Lab can use it after Refresh."""
    plan = tts_model_training_plan(model_name=model_name, env=env)
    name = str(plan.get("model_name") or "")
    if not name:
        raise ValueError("model_name is required")
    model_dir = Path(str(plan.get("expected_model_asset_dir") or "")).expanduser()
    ready, missing = _model_asset_ready(model_dir)
    if not ready:
        return {
            **plan,
            "registered": False,
            "available": False,
            "model_asset_dir": str(model_dir),
            "missing": missing,
            "message": "Model is not ready yet. Finish training and export config.json plus weights first.",
        }
    from app.tts_setup import tts_provider_status

    refreshed = tts_provider_status(env)
    models = list((refreshed.get("root") or {}).get("model_names", []) or [])
    return {
        **plan,
        "registered": name in models,
        "available": name in models,
        "model_asset_dir": str(model_dir),
        "missing": [],
        "models": models,
        "message": (
            f"{name} is available in Voice Lab."
            if name in models
            else f"{name} looks complete; press Refresh or reconnect the TTS sidecar if it does not appear."
        ),
    }


__all__ = [
    "TTS_MODEL_TRAINING_SCHEMA",
    "tts_model_training_execution_gate",
    "tts_model_training_launch_tool",
    "tts_model_training_plan",
    "tts_model_training_prepare_workspace",
    "tts_model_training_register_result",
]
