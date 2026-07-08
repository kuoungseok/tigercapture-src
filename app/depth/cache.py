"""Persistent depth-frame cache helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


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
    source_path: str = "",
    provider_id: str = "",
    version: str = "v1",
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
        "schema": "tigerstudio.depth.cache.frame.v1",
        "depth_source_id": str(source_id),
        "time_ms": int(time_ms),
        "shape": list(arr.shape),
        "frame_path": str(frame_path),
        "source_path": str(source_path or ""),
        "provider_id": str(provider_id or (diagnostics or {}).get("provider_id") or (diagnostics or {}).get("backend") or ""),
        "version": str(version or "v1"),
        "diagnostics": diagnostics or {},
    }
    manifest = load_depth_manifest(source_id, root=root)
    frames = list(manifest.get("frames") or []) if isinstance(manifest, dict) else []
    frames = [frame for frame in frames if int(frame.get("time_ms", -1)) != int(time_ms)]
    frames.append({
        "time_ms": int(time_ms),
        "frame_path": str(frame_path),
        "shape": list(arr.shape),
    })
    frames.sort(key=lambda item: int(item.get("time_ms", 0)))
    store_depth_manifest(
        source_id,
        source_path=source_path or str((manifest or {}).get("source_path") or ""),
        provider_id=payload["provider_id"] or str((manifest or {}).get("provider_id") or ""),
        version=version or str((manifest or {}).get("version") or "v1"),
        frames=frames,
        diagnostics=diagnostics or (manifest or {}).get("diagnostics") or {},
        root=root,
    )
    return payload


def load_depth_frame(
    source_id: str,
    time_ms: int,
    *,
    root: Path | None = None,
    allow_nearest_ms: int | None = None,
):
    import numpy as np

    frame_path = depth_frame_path(source_id, int(time_ms), root=root)
    if not frame_path.exists() and allow_nearest_ms is not None:
        nearest = nearest_depth_frame_path(source_id, int(time_ms), max_delta_ms=int(allow_nearest_ms), root=root)
        if nearest is not None:
            frame_path = nearest
    if not frame_path.exists():
        return None
    return np.load(frame_path)


def depth_frame_path(source_id: str, time_ms: int, *, root: Path | None = None) -> Path:
    return _entry_dir(source_id, root) / f"{int(time_ms):010d}.npy"


def _safe_read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    return {}


def load_depth_manifest(source_id: str, *, root: Path | None = None) -> dict[str, Any]:
    folder = _entry_dir(source_id, root)
    manifest = _safe_read_json(folder / "manifest.json")
    if not manifest:
        return {
            "ok": folder.exists(),
            "schema": "tigerstudio.depth.cache.manifest.v1",
            "depth_source_id": str(source_id),
            "cache_path": str(folder),
            "frames": [],
        }
    manifest.setdefault("schema", "tigerstudio.depth.cache.manifest.v1")
    manifest.setdefault("depth_source_id", str(source_id))
    manifest.setdefault("cache_path", str(folder))
    manifest.setdefault("frames", [])
    return manifest


def store_depth_manifest(
    source_id: str,
    *,
    source_path: str = "",
    provider_id: str = "",
    version: str = "v1",
    frames: Iterable[Mapping[str, Any]] = (),
    diagnostics: Mapping[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    folder = _entry_dir(source_id, root)
    folder.mkdir(parents=True, exist_ok=True)
    normalized_frames = [
        {
            "time_ms": int(frame.get("time_ms", 0)),
            "frame_path": str(frame.get("frame_path") or ""),
            "shape": list(frame.get("shape") or []),
        }
        for frame in frames
        if isinstance(frame, Mapping)
    ]
    normalized_frames.sort(key=lambda item: int(item.get("time_ms", 0)))
    source_mtime = None
    if source_path:
        try:
            source_mtime = Path(source_path).stat().st_mtime
        except Exception:
            source_mtime = None
    payload = {
        "ok": True,
        "schema": "tigerstudio.depth.cache.manifest.v1",
        "depth_source_id": str(source_id),
        "cache_path": str(folder),
        "source_path": str(source_path or ""),
        "source_mtime": source_mtime,
        "provider_id": str(provider_id or ""),
        "version": str(version or "v1"),
        "frame_count": len(normalized_frames),
        "frames": normalized_frames,
        "diagnostics": dict(diagnostics or {}),
    }
    (folder / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return payload


def nearest_depth_frame_path(
    source_id: str,
    time_ms: int,
    *,
    max_delta_ms: int,
    root: Path | None = None,
) -> Path | None:
    folder = _entry_dir(source_id, root)
    if not folder.exists():
        return None
    best: tuple[int, Path] | None = None
    for path in folder.glob("*.npy"):
        try:
            candidate_ms = int(path.stem)
        except Exception:
            continue
        delta = abs(candidate_ms - int(time_ms))
        if delta > int(max_delta_ms):
            continue
        if best is None or delta < best[0]:
            best = (delta, path)
    return best[1] if best is not None else None


def depth_cache_is_stale(source_id: str, *, root: Path | None = None) -> bool:
    manifest = load_depth_manifest(source_id, root=root)
    source_path = str(manifest.get("source_path") or "")
    if not source_path:
        return False
    try:
        current_mtime = Path(source_path).stat().st_mtime
    except Exception:
        return True
    recorded = manifest.get("source_mtime")
    try:
        return abs(float(current_mtime) - float(recorded)) > 0.001
    except Exception:
        return True


def depth_cache_diagnostics(source_id: str, *, root: Path | None = None) -> dict[str, Any]:
    folder = _entry_dir(source_id, root)
    frames = sorted(folder.glob("*.npy")) if folder.exists() else []
    manifest = load_depth_manifest(source_id, root=root)
    return {
        "ok": folder.exists(),
        "schema": "tigerstudio.depth.cache.diagnostics.v1",
        "depth_source_id": str(source_id),
        "cache_path": str(folder),
        "frame_count": len(frames),
        "frames": [str(path) for path in frames[:20]],
        "provider_id": str(manifest.get("provider_id") or ""),
        "source_path": str(manifest.get("source_path") or ""),
        "stale": depth_cache_is_stale(source_id, root=root) if folder.exists() else False,
    }
