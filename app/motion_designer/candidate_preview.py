"""Cached real-render thumbnails for Motion AI candidate review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import MotionComposition


CANDIDATE_PREVIEW_SCHEMA = "tigerstudio.motion.ai.candidate_preview_set.v1"


def _sample_time_ms(
    composition: MotionComposition,
    proposal: Mapping[str, Any],
) -> int:
    layers = [
        item
        for item in proposal.get("layers", [])
        if isinstance(item, Mapping)
    ]
    if not layers:
        return max(0, min(composition.duration_ms - 1, composition.duration_ms // 2))
    start = min(max(0, int(item.get("in_ms", 0) or 0)) for item in layers)
    end = max(
        max(start + 1, int(item.get("out_ms", composition.duration_ms) or composition.duration_ms))
        for item in layers
    )
    return max(0, min(composition.duration_ms - 1, start + (end - start) // 2))


def _cache_key(
    composition: MotionComposition,
    proposal: Mapping[str, Any],
    time_ms: int,
) -> str:
    payload = {
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "time_ms": int(time_ms),
        "proposal": proposal,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def render_candidate_preview_set(
    composition: MotionComposition,
    candidates: Iterable[Mapping[str, Any]],
    *,
    cache_root: str | Path,
    thumbnail_size: tuple[int, int] = (176, 100),
) -> dict[str, Any]:
    """Render one representative frame per candidate through the real renderer."""
    from PIL import Image, ImageOps

    from .ai_workspace import apply_motion_ai_proposal
    from .export_renderer import MotionExportRenderer

    root = Path(cache_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    renderer = MotionExportRenderer()
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(candidates):
        proposal = dict(raw)
        time_ms = _sample_time_ms(composition, proposal)
        key = _cache_key(composition, proposal, time_ms)
        frame_path = root / f"{key}_frame.png"
        thumbnail_path = root / f"{key}_thumb.png"
        cache_hit = frame_path.is_file() and thumbnail_path.is_file()
        if not cache_hit:
            candidate = apply_motion_ai_proposal(composition, proposal)
            renderer.save_png(candidate, time_ms, frame_path)
            with Image.open(frame_path) as opened:
                frame = opened.convert("RGB")
            thumb = ImageOps.contain(
                frame,
                thumbnail_size,
                method=Image.Resampling.LANCZOS,
            )
            canvas = Image.new("RGB", thumbnail_size, "#101419")
            canvas.paste(
                thumb,
                (
                    (thumbnail_size[0] - thumb.width) // 2,
                    (thumbnail_size[1] - thumb.height) // 2,
                ),
            )
            canvas.save(thumbnail_path)
        analysis = (
            proposal.get("analysis")
            if isinstance(proposal.get("analysis"), Mapping)
            else {}
        )
        rows.append({
            "index": index,
            "candidate_id": str(proposal.get("id") or ""),
            "variant": str(analysis.get("motion_variant") or f"candidate_{index + 1}"),
            "time_ms": time_ms,
            "frame_path": str(frame_path),
            "thumbnail_path": str(thumbnail_path),
            "cache_hit": cache_hit,
        })
    return {
        "schema": CANDIDATE_PREVIEW_SCHEMA,
        "composition_id": composition.id,
        "base_revision": composition.revision,
        "previews": rows,
    }


__all__ = [
    "CANDIDATE_PREVIEW_SCHEMA",
    "render_candidate_preview_set",
]
