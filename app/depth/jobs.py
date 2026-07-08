"""Depth cache generation jobs for clips and review automation."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from app.depth.cache import depth_source_id, store_depth_frame, store_depth_manifest
from app.depth.providers import estimate_depth, select_depth_provider_id
from app.depth.refinement import refine_depth_for_compositing
from app.depth.temporal import stabilize_depth_frame


def generate_depth_cache_for_frames(
    source_path: str,
    frames: Iterable[tuple[int, Any]],
    *,
    provider: str | None = None,
    version: str = "v1",
    refine: bool = True,
    temporal: bool = True,
    root: Path | None = None,
) -> dict[str, Any]:
    """Estimate and store depth maps for ``(time_ms, frame)`` pairs."""
    provider_id = select_depth_provider_id(provider)
    sid = depth_source_id(source_path, backend=provider_id, version=version)
    stored_frames: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    previous_depth = None
    previous_frame = None
    for time_ms, frame in frames:
        depth, diag = estimate_depth(
            frame,
            provider=provider_id,
            source_id=sid,
            time_ms=int(time_ms),
        )
        if refine:
            try:
                depth = refine_depth_for_compositing(depth, frame)
                diag["refined"] = True
            except Exception as exc:
                diag.setdefault("warnings", []).append(f"depth refinement skipped: {type(exc).__name__}: {exc}")
        if temporal and previous_depth is not None:
            try:
                depth, temporal_diag = stabilize_depth_frame(
                    depth,
                    previous_depth,
                    reference_frame=frame,
                    previous_reference_frame=previous_frame,
                )
                diag["temporal"] = temporal_diag
            except Exception as exc:
                diag.setdefault("warnings", []).append(f"temporal stabilization skipped: {type(exc).__name__}: {exc}")
        payload = store_depth_frame(
            sid,
            int(time_ms),
            depth,
            diagnostics=diag,
            source_path=source_path,
            provider_id=str(diag.get("provider_id") or diag.get("backend") or provider_id),
            version=version,
            root=root,
        )
        stored_frames.append({
            "time_ms": int(time_ms),
            "frame_path": str(payload.get("frame_path") or ""),
            "shape": list(payload.get("shape") or []),
        })
        diagnostics.append(diag)
        previous_depth = depth
        previous_frame = frame
    return store_depth_manifest(
        sid,
        source_path=source_path,
        provider_id=provider_id,
        version=version,
        frames=stored_frames,
        diagnostics={
            "ok": True,
            "provider_id": provider_id,
            "frame_diagnostics": diagnostics[-5:],
            "generated_frame_count": len(stored_frames),
        },
        root=root,
    )


def depth_cache_job_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Return a short UI-safe summary for a generated depth manifest."""
    return {
        "ok": bool(manifest.get("ok")),
        "depth_source_id": str(manifest.get("depth_source_id") or ""),
        "provider_id": str(manifest.get("provider_id") or ""),
        "frame_count": int(manifest.get("frame_count") or len(manifest.get("frames") or [])),
        "source_path": str(manifest.get("source_path") or ""),
        "cache_path": str(manifest.get("cache_path") or ""),
    }
