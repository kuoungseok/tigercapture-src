"""Persistent actor loading/probe/cache metadata."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


STAGE_PROGRESS = {
    "queued": 5,
    "file_check": 10,
    "repair": 20,
    "compat": 30,
    "isolated_probe": 42,
    "parse": 55,
    "textures": 70,
    "first_frame": 90,
    "ready": 100,
    "error": 100,
    "timeout": 100,
    "cancelled": 100,
}


def default_actor_cache_path() -> Path:
    return Path(__file__).resolve().parents[1] / "debugCapture" / "actor_loading_cache.json"


def actor_progress_for_stage(stage: str) -> int:
    return int(STAGE_PROGRESS.get(str(stage or ""), 0))


def actor_cache_key(kind: str, path: str) -> str:
    p = Path(path)
    try:
        st = p.stat()
        material = f"{kind}|{p.resolve()}|{st.st_mtime_ns}|{st.st_size}"
    except Exception:
        material = f"{kind}|{path}"
    return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()


def _load_cache(path: Path | None = None) -> dict[str, Any]:
    source = path or default_actor_cache_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "entries": {}}
    if not isinstance(payload, dict):
        return {"version": 1, "entries": {}}
    payload.setdefault("version", 1)
    payload.setdefault("entries", {})
    if not isinstance(payload["entries"], dict):
        payload["entries"] = {}
    return payload


def _write_cache(payload: dict[str, Any], path: Path | None = None) -> Path:
    target = path or default_actor_cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return target


def record_actor_load(
    kind: str,
    path: str,
    *,
    status: str,
    stage: str = "",
    message: str = "",
    elapsed_ms: int | None = None,
    isolated_probe: dict[str, Any] | None = None,
    prerender: dict[str, Any] | None = None,
    thumbnail_path: str = "",
    metadata: dict[str, Any] | None = None,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    payload = _load_cache(cache_path)
    key = actor_cache_key(kind, path)
    entry = dict(payload["entries"].get(key) or {})
    now = time.time()
    entry.update({
        "key": key,
        "kind": str(kind),
        "path": str(path),
        "status": str(status),
        "stage": str(stage or status),
        "progress": actor_progress_for_stage(stage or status),
        "message": str(message or ""),
        "updated_at": now,
        "updated_at_iso": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
    })
    if elapsed_ms is not None:
        entry["elapsed_ms"] = int(elapsed_ms)
    if isolated_probe is not None:
        entry["isolated_probe"] = isolated_probe
    if prerender is not None:
        entry["prerender"] = prerender
    if thumbnail_path:
        entry["thumbnail_path"] = str(thumbnail_path)
    if metadata:
        merged = dict(entry.get("metadata") or {})
        merged.update(metadata)
        entry["metadata"] = merged
    try:
        from app.actor_loading_status import actor_loading_diagnostic_card

        entry["diagnostic_card"] = actor_loading_diagnostic_card(
            kind,
            path,
            status=status,
            stage=stage or status,
            message=message,
            metadata=dict(entry.get("metadata") or {}),
        )
    except Exception:
        pass
    payload["entries"][key] = entry
    _write_cache(payload, cache_path)
    try:
        from app.loading_performance import record_loading_event

        record_loading_event(
            f"actor.{kind}",
            stage or status,
            path=path,
            status=status,
            elapsed_ms=elapsed_ms,
            detail=message,
            metadata=metadata or {},
        )
    except Exception:
        pass
    return entry


def actor_loading_cache_report(cache_path: Path | None = None) -> dict[str, Any]:
    payload = _load_cache(cache_path)
    entries = list((payload.get("entries") or {}).values())
    entries.sort(key=lambda row: float(row.get("updated_at", 0.0) or 0.0), reverse=True)
    counts: dict[str, int] = {}
    for row in entries:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "ok": True,
        "path": str(cache_path or default_actor_cache_path()),
        "summary": {
            "entries": len(entries),
            "status_counts": dict(sorted(counts.items())),
        },
        "entries": entries,
    }


def clear_actor_loading_cache(cache_path: Path | None = None) -> Path:
    return _write_cache({"version": 1, "entries": {}}, cache_path)
