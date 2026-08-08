"""Import editor creative objects into the paint dialog.

The PPT maker already has a bridge that converts media and actor assets into
portable presentation elements. Paint uses the same idea, but the portable
target is a PNG sticker layer so imported objects can be moved, resized, copied,
and exported with the existing drawing pipeline.
"""
from __future__ import annotations

import hashlib
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


PAINT_IMPORT_SCHEMA = "tigerstudio.paint.editor_object_import.v1"
DEFAULT_IMPORT_DIR = Path("external/assets/paint_imports")


@dataclass(frozen=True)
class PaintImportObject:
    id: str
    kind: str
    label: str
    source_path: str = ""
    active: bool = True
    start_ms: int = 0
    end_ms: int = -1
    x_norm: float = 0.18
    y_norm: float = 0.18
    width_norm: float = 0.34
    height_norm: float = 0.20
    payload: dict[str, Any] = field(default_factory=dict)

    def menu_label(self) -> str:
        status = "active" if self.active else "inactive"
        kind = self.kind.replace("_", " ").title()
        return f"{kind} | {self.label} ({status})"


def collect_editor_paint_objects(
    owner: Any,
    *,
    time_ms: int = 0,
    include_inactive: bool = True,
) -> list[PaintImportObject]:
    """Return editor objects that can be imported as paint sticker layers."""
    t = _as_int(time_ms)
    rows: list[PaintImportObject] = []
    rows.extend(_collect_typography_objects(owner, t, include_inactive=include_inactive))
    rows.extend(_collect_ar_pbr_objects(owner, t, include_inactive=include_inactive))
    rows.extend(_collect_mmd_objects(owner, t, include_inactive=include_inactive))
    rows.extend(_collect_sidecar_actor_objects(owner, t, include_inactive=include_inactive))
    rows.sort(key=lambda row: (not row.active, row.kind, row.start_ms, row.label.casefold()))
    return rows


def coerce_paint_import_object(value: PaintImportObject | Mapping[str, Any]) -> PaintImportObject:
    if isinstance(value, PaintImportObject):
        return value
    data = dict(value or {})
    return PaintImportObject(
        id=str(data.get("id") or "editor_object"),
        kind=str(data.get("kind") or "media_actor"),
        label=str(data.get("label") or data.get("name") or "Editor object"),
        source_path=str(data.get("source_path") or ""),
        active=bool(data.get("active", True)),
        start_ms=_as_int(data.get("start_ms"), 0),
        end_ms=_as_int(data.get("end_ms"), -1),
        x_norm=_clamp(float(data.get("x_norm", 0.18)), 0.0, 0.95),
        y_norm=_clamp(float(data.get("y_norm", 0.18)), 0.0, 0.95),
        width_norm=_clamp(float(data.get("width_norm", 0.34)), 0.04, 1.0),
        height_norm=_clamp(float(data.get("height_norm", 0.20)), 0.04, 1.0),
        payload=dict(data.get("payload") or {}),
    )


def render_paint_import_object(
    value: PaintImportObject | Mapping[str, Any],
    *,
    canvas_size: tuple[int, int] = (1920, 1080),
    output_dir: str | Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Render an import object to a PNG suitable for ``Sticker``."""
    obj = coerce_paint_import_object(value)
    out_dir = Path(output_dir) if output_dir is not None else DEFAULT_IMPORT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(
        f"{obj.kind}|{obj.id}|{obj.label}|{obj.source_path}|{obj.payload}".encode("utf-8", errors="replace")
    ).hexdigest()[:14]
    out_path = out_dir / f"{_safe_slug(obj.kind)}_{_safe_slug(obj.id)}_{key}.png"
    if out_path.exists() and not force:
        return _render_report(obj, out_path)
    if obj.kind == "typography_actor":
        _render_typography_png(obj, out_path, canvas_size=canvas_size)
    else:
        _render_actor_poster_png(obj, out_path)
    return _render_report(obj, out_path)


def _collect_typography_objects(owner: Any, time_ms: int, *, include_inactive: bool) -> list[PaintImportObject]:
    rows: list[PaintImportObject] = []
    seen: set[str] = set()
    for track_index, track in enumerate(list(getattr(owner, "_tracks", []) or []), start=1):
        offset = _as_int(getattr(track, "offset_ms", 0), 0)
        local_ms = time_ms - offset
        for actor_index, actor in enumerate(list(getattr(track, "typography_actors", []) or []), start=1):
            key = f"track:{getattr(track, 'id', track_index)}:{getattr(actor, 'id', actor_index)}:{id(actor)}"
            if key in seen:
                continue
            seen.add(key)
            active = _actor_contains(actor, local_ms)
            if not active and not include_inactive:
                continue
            rows.append(_typography_import_object(track, actor, track_index, actor_index, offset, active))
    return rows


def _typography_import_object(
    track: Any,
    actor: Any,
    track_index: int,
    actor_index: int,
    track_offset_ms: int,
    active: bool,
) -> PaintImportObject:
    text = str(getattr(actor, "text", "") or getattr(actor, "display_text", lambda: "")() or "Typography")
    style = getattr(actor, "style", None)
    x, y, w, h = _typography_rect(style, text)
    start = track_offset_ms + _as_int(getattr(actor, "start_ms", 0), 0)
    end = track_offset_ms + _as_int(getattr(actor, "end_ms", start + 2000), start + 2000)
    payload = {
        "schema": PAINT_IMPORT_SCHEMA,
        "source": "editor_typography",
        "track_id": getattr(track, "id", track_index),
        "actor_id": getattr(actor, "id", actor_index),
        "text": text,
        "style": _style_payload(style),
        "animation": _simple_payload(getattr(actor, "animation", None)),
    }
    try:
        from app.pptgen.asset_bridge import slide_element_from_typography

        ppt_el = slide_element_from_typography(actor, f"paint-typo-{track_index}-{actor_index}", x=x, y=y, w=w, h=h)
        payload["ppt_bridge"] = {
            "kind": ppt_el.kind,
            "name": ppt_el.name,
            "editable_actor": bool(ppt_el.metadata.get("editable_actor")),
        }
    except Exception:
        pass
    return PaintImportObject(
        id=f"typography_{getattr(track, 'id', track_index)}_{getattr(actor, 'id', actor_index)}",
        kind="typography_actor",
        label=(text[:36] or "Typography"),
        active=active,
        start_ms=start,
        end_ms=end,
        x_norm=x,
        y_norm=y,
        width_norm=w,
        height_norm=h,
        payload=payload,
    )


def _collect_ar_pbr_objects(owner: Any, time_ms: int, *, include_inactive: bool) -> list[PaintImportObject]:
    rows: list[PaintImportObject] = []
    tracks = list(getattr(owner, "_ar_pbr_tracks", []) or [])
    if not tracks:
        return rows
    for index, track in enumerate(tracks, start=1):
        if not isinstance(track, Mapping):
            continue
        start = _as_int(track.get("start_ms"), 0)
        end = _as_int(track.get("end_ms"), start + 1)
        active = start <= time_ms < end
        if not active and not include_inactive:
            continue
        source = str(track.get("asset_path") or track.get("source_path") or "")
        label = Path(source).stem if source else str(track.get("id") or f"AR/PBR {index}")
        cx, cy = _ar_pbr_center(track)
        scale = _ar_pbr_scale(track)
        w = _clamp(0.18 + scale * 0.045, 0.16, 0.46)
        h = _clamp(w * 1.12, 0.18, 0.58)
        rows.append(
            PaintImportObject(
                id=str(track.get("id") or f"ar_pbr_{index:03d}"),
                kind="ar_pbr_actor",
                label=label,
                source_path=source,
                active=active,
                start_ms=start,
                end_ms=end,
                x_norm=_clamp(cx - w * 0.5, 0.0, 1.0 - w),
                y_norm=_clamp(cy - h * 0.5, 0.0, 1.0 - h),
                width_norm=w,
                height_norm=h,
                payload={
                    "schema": PAINT_IMPORT_SCHEMA,
                    "source": "editor_ar_pbr",
                    "track": dict(track),
                },
            )
        )
    return rows


def _collect_mmd_objects(owner: Any, time_ms: int, *, include_inactive: bool) -> list[PaintImportObject]:
    rows: list[PaintImportObject] = []
    for index, track in enumerate(list(getattr(owner, "_mmd_tracks", []) or []), start=1):
        if not isinstance(track, Mapping):
            continue
        start = _as_int(track.get("start_ms"), 0)
        end = _as_int(track.get("end_ms"), start + 1)
        active = start <= time_ms < end
        if not active and not include_inactive:
            continue
        source = str(track.get("model_path") or track.get("asset_path") or track.get("source_path") or "")
        label = Path(source).stem if source else str(track.get("id") or f"MMD {index}")
        rows.append(
            PaintImportObject(
                id=str(track.get("id") or f"mmd_{index:03d}"),
                kind="mmd_actor",
                label=label,
                source_path=source,
                active=active,
                start_ms=start,
                end_ms=end,
                x_norm=0.58,
                y_norm=0.22,
                width_norm=0.28,
                height_norm=0.46,
                payload={"schema": PAINT_IMPORT_SCHEMA, "source": "editor_mmd", "track": dict(track)},
            )
        )
    return rows


def _collect_sidecar_actor_objects(owner: Any, time_ms: int, *, include_inactive: bool) -> list[PaintImportObject]:
    specs = (
        ("_spine_actor_tracks", "spine_actor", "Spine"),
        ("_live2d_actor_tracks", "live2d_actor", "Live2D"),
    )
    rows: list[PaintImportObject] = []
    for attr, kind, family in specs:
        for track_index, track in enumerate(list(getattr(owner, attr, []) or []), start=1):
            for clip_index, clip in enumerate(list(getattr(track, "clips", []) or []), start=1):
                start = _as_int(getattr(clip, "start_ms", 0), 0)
                end = _as_int(getattr(clip, "end_ms", start + 1), start + 1)
                active = start <= time_ms < end
                if not active and not include_inactive:
                    continue
                source = str(
                    getattr(clip, "asset_path", "")
                    or getattr(clip, "model_path", "")
                    or getattr(track, "asset_path", "")
                    or getattr(track, "model_path", "")
                    or ""
                )
                label = Path(source).stem if source else f"{family} {clip_index}"
                rows.append(
                    PaintImportObject(
                        id=f"{kind}_{track_index}_{getattr(clip, 'id', clip_index)}",
                        kind=kind,
                        label=label,
                        source_path=source,
                        active=active,
                        start_ms=start,
                        end_ms=end,
                        x_norm=0.60,
                        y_norm=0.18,
                        width_norm=0.26,
                        height_norm=0.50,
                        payload={
                            "schema": PAINT_IMPORT_SCHEMA,
                            "source": f"editor_{kind}",
                            "track_index": track_index,
                            "clip_id": getattr(clip, "id", clip_index),
                        },
                    )
                )
    return rows


def _render_report(obj: PaintImportObject, out_path: Path) -> dict[str, Any]:
    return {
        "schema": PAINT_IMPORT_SCHEMA,
        "kind": obj.kind,
        "id": obj.id,
        "label": obj.label,
        "png_path": str(out_path.resolve()),
        "rect_norm": {
            "x": obj.x_norm,
            "y": obj.y_norm,
            "w": obj.width_norm,
            "h": obj.height_norm,
        },
    }


def _render_typography_png(
    obj: PaintImportObject,
    out_path: Path,
    *,
    canvas_size: tuple[int, int],
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required to import typography into Paint") from exc

    canvas_w, canvas_h = max(1, int(canvas_size[0])), max(1, int(canvas_size[1]))
    width = max(240, min(1800, int(canvas_w * obj.width_norm)))
    height = max(80, min(720, int(canvas_h * obj.height_norm)))
    style = dict((obj.payload or {}).get("style") or {})
    font_size = max(16, min(int(height * 0.72), _as_int(style.get("font_size"), 72)))
    font = _load_font(font_size, style.get("font_family"))
    text = str((obj.payload or {}).get("text") or obj.label or "Typography")
    lines = _wrapped_lines(text, max_chars=max(10, int(width / max(12, font_size * 0.55))))
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    pad = max(8, _as_int(style.get("background_padding"), 14))
    bg = _parse_color(style.get("background_color"))
    if bg is not None:
        radius = max(0, _as_int(style.get("background_radius"), 14))
        draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=bg)
    color = _parse_color(style.get("color"), fallback=(255, 255, 255, 255))
    shadow = _parse_color(style.get("shadow_color"))
    align = str(style.get("alignment") or "center").casefold()
    line_gap = max(2, int(font_size * 0.16))
    metrics = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [box[3] - box[1] for box in metrics]
    total_h = sum(line_heights) + line_gap * max(0, len(lines) - 1)
    y = max(pad, int((height - total_h) / 2))
    if shadow is not None:
        shadow_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        _draw_lines(shadow_draw, lines, metrics, font, width, y, line_heights, line_gap, align, shadow, pad)
        blur = max(0, _as_int(style.get("shadow_blur"), 2))
        ox = _as_int(style.get("shadow_offset_x"), 2)
        oy = _as_int(style.get("shadow_offset_y"), 2)
        if blur:
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur))
        image.alpha_composite(shadow_layer, (ox, oy))
    outline = _parse_color(style.get("outline_color"))
    outline_w = max(0, _as_int(style.get("outline_width"), 0))
    if outline is not None and outline_w > 0:
        for dx in range(-outline_w, outline_w + 1):
            for dy in range(-outline_w, outline_w + 1):
                if dx == 0 and dy == 0:
                    continue
                _draw_lines(draw, lines, metrics, font, width, y + dy, line_heights, line_gap, align, outline, pad, x_offset=dx)
    _draw_lines(draw, lines, metrics, font, width, y, line_heights, line_gap, align, color, pad)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "PNG")


def _render_actor_poster_png(obj: PaintImportObject, out_path: Path) -> None:
    if obj.kind in {"ar_pbr_actor", "vrm_actor", "mmd_actor", "video_actor", "audio_actor", "media_actor"}:
        try:
            from app.pptgen.actor_posters import ensure_actor_poster
            from app.pptgen.asset_bridge import slide_element_from_media_asset

            element = slide_element_from_media_asset(
                obj.source_path or obj.label,
                obj.id,
                kind=obj.kind,
                name=obj.label,
                source="paint_editor_object_import",
            )
            report = ensure_actor_poster(element, output_dir=out_path.parent, force=True)
            poster = Path(str(report.get("poster_path") or ""))
            if poster.is_file():
                if poster.resolve() != out_path.resolve():
                    out_path.write_bytes(poster.read_bytes())
                return
        except Exception:
            pass
    _draw_generic_actor_card(obj, out_path)


def _draw_generic_actor_card(obj: PaintImportObject, out_path: Path) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - dependency guard
        raise RuntimeError("Pillow is required to import actor objects into Paint") from exc

    image = Image.new("RGBA", (960, 540), (16, 22, 32, 238))
    draw = ImageDraw.Draw(image)
    title_font = _load_font(54, "arial")
    meta_font = _load_font(25, "arial")
    accent = _accent_for_kind(obj.kind)
    draw.rounded_rectangle((36, 36, 924, 504), radius=34, outline=accent, width=5)
    draw.rounded_rectangle((58, 58, 190, 104), radius=16, fill=accent)
    draw.text((82, 68), obj.kind.split("_", 1)[0].upper(), fill=(10, 14, 22, 255), font=meta_font)
    label = obj.label or obj.kind.replace("_", " ").title()
    source = Path(obj.source_path).name if obj.source_path else obj.kind.replace("_", " ").title()
    _draw_center_text(draw, label, title_font, (70, 190, 890, 260), (245, 248, 255, 255))
    _draw_center_text(draw, source, meta_font, (70, 280, 890, 350), (165, 178, 196, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path, "PNG")


def _draw_lines(draw: Any, lines: list[str], metrics: list[tuple[int, int, int, int]], font: Any, width: int,
                y: int, line_heights: list[int], line_gap: int, align: str,
                fill: tuple[int, int, int, int], pad: int, *, x_offset: int = 0) -> None:
    cur_y = y
    for line, box, line_h in zip(lines, metrics, line_heights):
        tw = box[2] - box[0]
        if align == "left":
            x = pad
        elif align == "right":
            x = width - pad - tw
        else:
            x = int((width - tw) / 2)
        draw.text((x + x_offset, cur_y), line, font=font, fill=fill)
        cur_y += line_h + line_gap


def _draw_center_text(draw: Any, text: str, font: Any, box: tuple[int, int, int, int],
                      fill: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x0 + (x1 - x0 - tw) / 2, y0 + (y1 - y0 - th) / 2), text, fill=fill, font=font)


def _load_font(size: int, family: Any = None) -> Any:
    from PIL import ImageFont

    candidates = []
    if family:
        text = str(family).strip()
        if text:
            candidates.extend([text, f"{text}.ttf"])
    candidates.extend(["malgun.ttf", "arial.ttf", "segoeui.ttf"])
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, int(size))
        except Exception:
            continue
    return ImageFont.load_default()


def _wrapped_lines(text: str, *, max_chars: int) -> list[str]:
    raw_lines = str(text or "").splitlines() or [str(text or "")]
    lines: list[str] = []
    for raw in raw_lines:
        if len(raw) <= max_chars:
            lines.append(raw)
        else:
            lines.extend(textwrap.wrap(raw, width=max_chars) or [raw])
    return lines[:6] or ["Typography"]


def _typography_rect(style: Any, text: str) -> tuple[float, float, float, float]:
    position_x = _clamp(_safe_float(getattr(style, "position_x", 0.5), 0.5), 0.0, 1.0)
    position_y = _clamp(_safe_float(getattr(style, "position_y", 0.5), 0.5), 0.0, 1.0)
    font_size = _as_int(getattr(style, "font_size", 72), 72)
    line_count = max(1, len(str(text or "").splitlines()))
    width = _clamp(0.34 + min(0.28, len(str(text or "")) * 0.006), 0.26, 0.72)
    height = _clamp((font_size / 1080.0) * 1.65 * line_count, 0.08, 0.30)
    return (
        _clamp(position_x - width * 0.5, 0.0, 1.0 - width),
        _clamp(position_y - height * 0.5, 0.0, 1.0 - height),
        width,
        height,
    )


def _actor_contains(actor: Any, local_ms: int) -> bool:
    contains = getattr(actor, "contains", None)
    if callable(contains):
        try:
            return bool(contains(int(local_ms)))
        except Exception:
            pass
    start = _as_int(getattr(actor, "start_ms", 0), 0)
    end = _as_int(getattr(actor, "end_ms", start + 1), start + 1)
    return start <= int(local_ms) < end


def _ar_pbr_center(track: Mapping[str, Any]) -> tuple[float, float]:
    try:
        from app.ar_pbr.gizmo import track_center_norm

        return track_center_norm(dict(track))
    except Exception:
        placement = track.get("placement")
        if isinstance(placement, Mapping):
            point = placement.get("image_point")
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                return (_clamp(_safe_float(point[0], 0.5), 0.0, 1.0), _clamp(_safe_float(point[1], 0.62), 0.0, 1.0))
    return (0.5, 0.62)


def _ar_pbr_scale(track: Mapping[str, Any]) -> float:
    try:
        from app.ar_pbr.gizmo import track_uniform_scale

        return max(0.05, float(track_uniform_scale(dict(track))))
    except Exception:
        transform = track.get("transform")
        if isinstance(transform, Mapping):
            values = transform.get("scale")
            if isinstance(values, (list, tuple)) and values:
                return _safe_float(values[0], 1.0)
    return 1.0


def _style_payload(style: Any) -> dict[str, Any]:
    keys = (
        "font_family",
        "font_size",
        "font_weight",
        "color",
        "alignment",
        "letter_spacing",
        "line_height",
        "position_x",
        "position_y",
        "rotation",
        "outline_color",
        "outline_width",
        "shadow_color",
        "shadow_offset_x",
        "shadow_offset_y",
        "shadow_blur",
        "background_color",
        "background_padding",
        "background_radius",
    )
    return {key: getattr(style, key) for key in keys if hasattr(style, key)}


def _simple_payload(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    data: dict[str, Any] = {}
    for key in dir(value):
        if key.startswith("_"):
            continue
        raw = getattr(value, key, None)
        if isinstance(raw, (str, int, float, bool, type(None), list, dict, tuple)):
            data[key] = raw
    return data


def _parse_color(value: Any, *, fallback: tuple[int, int, int, int] | None = None) -> tuple[int, int, int, int] | None:
    if value is None:
        return fallback
    text = str(value).strip()
    if not text or text.casefold() == "transparent":
        return fallback
    if text.startswith("#"):
        raw = text[1:]
        try:
            if len(raw) == 3:
                r, g, b = [int(ch * 2, 16) for ch in raw]
                return (r, g, b, 255)
            if len(raw) == 6:
                return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255)
            if len(raw) == 8:
                return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), int(raw[6:8], 16))
        except Exception:
            return fallback
    return fallback


def _accent_for_kind(kind: str) -> tuple[int, int, int, int]:
    if kind == "ar_pbr_actor":
        return (108, 234, 146, 255)
    if kind == "mmd_actor":
        return (184, 139, 255, 255)
    if kind == "live2d_actor":
        return (255, 154, 200, 255)
    if kind == "spine_actor":
        return (255, 190, 94, 255)
    return (106, 162, 255, 255)


def _safe_slug(value: Any, fallback: str = "object") -> str:
    chars = [ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value or "")]
    slug = "".join(chars).strip("._")
    return slug[:72] or fallback


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


__all__ = [
    "DEFAULT_IMPORT_DIR",
    "PAINT_IMPORT_SCHEMA",
    "PaintImportObject",
    "coerce_paint_import_object",
    "collect_editor_paint_objects",
    "render_paint_import_object",
]
