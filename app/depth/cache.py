"""Persistent depth-frame cache helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def depth_cache_root() -> Path:
    root = ROOT / "debugCapture" / "depth_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def depth_source_id(source_path: str, *, backend: str = "synthetic", version: str = "v1") -> str:
    material = f"{Path(source_path)}|{backend}|{version}"
    return "depth_" + hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:16]


def _entry_dir(source_id: str, root: Path | None = None) -> Path:
    sid = "".join(ch for ch in str(source_id or "") if ch.isalnum() or ch in {"_", "-"})
    return (root or depth_cache_root()) / (sid or "depth_unknown")


def store_depth_frame(
    source_id: str,
    time_ms: int,
    depth_frame: Any,
    *,
    diagnostics: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    import numpy as np

    folder = _entry_dir(source_id, root)
    folder.mkdir(parents=True, exist_ok=True)
    frame_path = folder / f"{int(time_ms):010d}.npy"
    arr = np.asarray(depth_frame, dtype=np.float32)
    np.save(frame_path, arr)
    payload = {
        "ok": True,
        "depth_source_id": str(source_id),
        "time_ms": int(time_ms),
        "shape": list(arr.shape),
        "frame_path": str(frame_path),
        "diagnostics": diagnostics or {},
    }
    (folder / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return payload


def load_depth_frame(source_id: str, time_ms: int, *, root: Path | None = None):
    import numpy as np

    frame_path = _entry_dir(source_id, root) / f"{int(time_ms):010d}.npy"
    if not frame_path.exists():
        return None
    return np.load(frame_path)


def depth_cache_diagnostics(source_id: str, *, root: Path | None = None) -> dict[str, Any]:
    folder = _entry_dir(source_id, root)
    frames = sorted(folder.glob("*.npy")) if folder.exists() else []
    return {
        "ok": folder.exists(),
        "depth_source_id": str(source_id),
        "cache_path": str(folder),
        "frame_count": len(frames),
        "frames": [str(path) for path in frames[:20]],
    }

