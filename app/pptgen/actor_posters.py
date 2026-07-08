"""Generate poster images for PPT media/3D actors.

The renderer/exporter uses poster metadata when available. This module fills
that metadata deterministically without importing Qt.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.paths import runtime_data_dir
from app.pptgen import frame_extract
from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


POSTER_KEYS = ("poster_path", "thumbnail_path", "preview_path", "render_path")
ACTOR_KINDS = {"video_actor", "ar_pbr_actor", "vrm_actor", "mmd_actor", "audio_actor", "media_actor"}


def actor_poster_path(element: SlideElement) -> Path | None:
    for key in POSTER_KEYS:
        raw = str(element.metadata.get(key) or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if path.is_file():
            return path
    return None


def _safe_slug(value: str, fallback: str = "actor") -> str:
    chars = [char if char.isalnum() or char in {"-", "_", "."} else "_" for char in str(value or "")]
    slug = "".join(chars).strip("._")
    return slug or fallback


def _cache_path(element: SlideElement, *, output_dir: str | Path | None = None, suffix: str = ".png") -> Path:
    out_dir = Path(output_dir) if output_dir is not None else runtime_data_dir() / "pptgen" / "actor_posters"
    out_dir.mkdir(parents=True, exist_ok=True)
    source = str(element.source_path or element.metadata.get("source_path") or "")
    key = hashlib.sha1(f"{element.kind}|{element.id}|{source}|{element.name}".encode("utf-8")).hexdigest()[:14]
    return out_dir / f"{_safe_slug(element.id)}_{key}{suffix}"


def _card_palette(kind: str) -> tuple[str, str, str]:
    if kind == "video_actor":
        return "#101722", "#2F6FED", "#EAF2FF"
    if kind in {"ar_pbr_actor", "vrm_actor"}:
        return "#F3F6FA", "#3A8F5A", "#182033"
    if kind == "mmd_actor":
        return "#F7F1FF", "#8B5CF6", "#182033"
    if kind == "audio_actor":
        return "#FFF7E8", "#D88716", "#182033"
    return "#F3F6FA", "#2F6FED", "#182033"


def _draw_actor_card(element: SlideElement, target: Path, *, size: tuple[int, int] = (960, 540)) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required to generate PPT actor posters") from exc

    bg, accent, ink = _card_palette(element.kind)
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)
    w, h = size
    try:
        title_font = ImageFont.truetype("arial.ttf", max(18, int(h * 0.085)))
        meta_font = ImageFont.truetype("arial.ttf", max(12, int(h * 0.045)))
    except Exception:
        title_font = ImageFont.load_default()
        meta_font = ImageFont.load_default()

    margin = int(min(w, h) * 0.07)
    draw.rounded_rectangle(
        (margin, margin, w - margin, h - margin),
        radius=max(12, int(h * 0.04)),
        outline=accent,
        width=max(3, int(h * 0.012)),
    )
    label = element.name or element.kind.replace("_", " ").title()
    kind_label = element.kind.replace("_", " ").title()
    source = Path(str(element.source_path or element.metadata.get("source_path") or "")).name
    lines = [label, kind_label]
    if source:
        lines.append(source)
    y = int(h * 0.36)
    for index, text in enumerate(lines):
        font = title_font if index == 0 else meta_font
        try:
            box = draw.textbbox((0, 0), text, font=font)
            tw = box[2] - box[0]
            th = box[3] - box[1]
        except Exception:
            tw = len(text) * 8
            th = 16
        draw.text(((w - tw) / 2, y), text, fill=ink, font=font)
        y += th + int(h * (0.045 if index == 0 else 0.03))
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target)
    return target


def ensure_actor_poster(
    element: SlideElement,
    *,
    output_dir: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Ensure one actor has a usable poster and return a small report."""
    if element.kind not in ACTOR_KINDS:
        return {"element_id": element.id, "kind": element.kind, "generated": False, "reason": "not_actor"}
    existing = actor_poster_path(element)
    if existing is not None and not force:
        element.metadata["poster_path"] = str(existing)
        return {"element_id": element.id, "kind": element.kind, "generated": False, "poster_path": str(existing), "reason": "exists"}

    poster: Path
    if element.kind == "video_actor" and str(element.source_path or "").strip():
        source_ms = int(element.metadata.get("source_ms") or element.metadata.get("source_in_ms") or 0)
        try:
            poster = frame_extract.extract_video_still(element.source_path, source_ms=source_ms, output_dir=output_dir)
        except Exception:
            poster = _draw_actor_card(element, _cache_path(element, output_dir=output_dir))
    else:
        poster = _draw_actor_card(element, _cache_path(element, output_dir=output_dir))

    element.metadata["poster_path"] = str(poster)
    return {"element_id": element.id, "kind": element.kind, "generated": True, "poster_path": str(poster)}


def ensure_deck_actor_posters(
    deck: DeckSpec,
    *,
    output_dir: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for slide in deck.slides:
        for element in slide.elements:
            if element.kind in ACTOR_KINDS:
                row = ensure_actor_poster(element, output_dir=output_dir, force=force)
                row["slide_id"] = slide.id
                rows.append(row)
    generated = sum(1 for row in rows if row.get("generated"))
    return {
        "schema": "tigercapture.ppt.actor_posters.v1",
        "actor_count": len(rows),
        "generated_count": generated,
        "posters": rows,
    }


__all__ = [
    "ACTOR_KINDS",
    "POSTER_KEYS",
    "actor_poster_path",
    "ensure_actor_poster",
    "ensure_deck_actor_posters",
]
