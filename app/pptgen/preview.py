"""Pillow preview rendering for the PPT generator."""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.pptgen.animation_runtime import animated_rect, element_animation_state
from app.pptgen.fonts import pil_font_candidates
from app.pptgen.formula import evaluate_numeric_formula, format_formula_value
from app.pptgen.overlays import slide_overlay_elements
from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


DEFAULT_SIZE = (1280, 720)
ACTOR_PLACEHOLDER_KINDS = {"video_actor", "ar_pbr_actor", "vrm_actor", "mmd_actor", "audio_actor", "media_actor"}


def _rgb(hex_color: str, fallback: str = "#FFFFFF") -> tuple[int, int, int]:
    raw = str(hex_color or fallback).strip().lstrip("#")
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6:
        raw = fallback.lstrip("#")
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return tuple(int(fallback.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))


def _rgba(hex_color: str | None, alpha: float = 1.0, fallback: str = "#FFFFFF") -> tuple[int, int, int, int]:
    r, g, b = _rgb(hex_color or fallback, fallback)
    return r, g, b, max(0, min(255, int(round(float(alpha) * 255))))


def _rect(element: SlideElement, size: tuple[int, int]) -> tuple[int, int, int, int]:
    w, h = size
    return (
        int(round(element.x * w)),
        int(round(element.y * h)),
        int(round((element.x + element.w) * w)),
        int(round((element.y + element.h) * h)),
    )


def _rect_xywh(element: SlideElement, size: tuple[int, int]) -> tuple[int, int, int, int]:
    left, top, right, bottom = _rect(element, size)
    return left, top, max(1, right - left), max(1, bottom - top)


def _box_from_xywh(rect: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    return x, y, x + max(1, w), y + max(1, h)


def _with_opacity(element: SlideElement, opacity: float) -> SlideElement:
    return replace(element, opacity=max(0.0, min(1.0, float(opacity))))


def _font(size: int, bold: bool = False, italic: bool = False, family: str = "") -> ImageFont.ImageFont:
    for candidate in pil_font_candidates(family, bold=bold, italic=italic):
        try:
            return ImageFont.truetype(candidate, max(8, int(size)))
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text or "").splitlines() or [""]:
        current = ""
        for word in paragraph.split(" "):
            probe = f"{current} {word}".strip()
            if not current or draw.textbbox((0, 0), probe, font=font)[2] <= max_width:
                current = probe
                continue
            lines.append(current)
            current = word
        if current:
            lines.append(current)
    return lines or [""]


def _draw_text(
    draw: ImageDraw.ImageDraw,
    element: SlideElement,
    box: tuple[int, int, int, int],
    *,
    font_scale: float = 1.0,
) -> None:
    left, top, right, bottom = box
    width = max(1, right - left)
    font_size = max(8, int(round(element.style.font_size * float(font_scale))))
    font = _font(font_size, element.style.bold, element.style.italic, element.style.font_family)
    line_h = max(10, int(font_size * max(0.8, min(2.4, float(element.style.line_height or 1.2)))))
    y = top
    for line in _wrap(draw, element.text, font, width):
        if y + line_h > bottom:
            break
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = left
        if element.style.align in {"center", "ctr", "c"}:
            x = left + max(0, width - text_w) // 2
        elif element.style.align in {"right", "r"}:
            x = right - text_w
        draw.text((x, y), line, font=font, fill=_rgba(element.style.color, element.opacity))
        if element.style.underline:
            underline_y = min(bottom - 1, y + max(1, bbox[3] - bbox[1]) + max(1, font_size // 12))
            draw.line((x, underline_y, x + text_w, underline_y), fill=_rgba(element.style.color, element.opacity), width=max(1, font_size // 18))
        y += line_h


def _cover_image(path: Path, width: int, height: int) -> Image.Image | None:
    try:
        image = Image.open(path).convert("RGBA")
    except Exception:
        return None
    scale = max(width / max(1, image.width), height / max(1, image.height))
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), Image.Resampling.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _actor_poster_path(element: SlideElement) -> Path | None:
    for key in ("poster_path", "thumbnail_path", "preview_path", "render_path"):
        raw = str(element.metadata.get(key) or "").strip()
        if not raw:
            continue
        path = Path(raw)
        if path.is_file():
            return path
    return None


def _draw_placeholder(
    draw: ImageDraw.ImageDraw,
    element: SlideElement,
    box: tuple[int, int, int, int],
    *,
    font_scale: float = 1.0,
) -> None:
    fill = element.style.fill or "#F3F6FA"
    stroke = element.style.stroke or "#2F6FED"
    draw.rounded_rectangle(box, radius=14, fill=_rgba(fill, element.opacity), outline=_rgb(stroke), width=max(1, int(element.style.stroke_width or 1)))
    label = element.name or element.kind.replace("_", " ").title()
    font = _font(max(8, int(round(22 * float(font_scale)))), True)
    text_box = draw.textbbox((0, 0), label, font=font)
    x = box[0] + max(0, (box[2] - box[0] - (text_box[2] - text_box[0])) // 2)
    y = box[1] + max(0, (box[3] - box[1] - (text_box[3] - text_box[1])) // 2)
    draw.text((x, y), label, font=font, fill=_rgba(element.style.color or "#182033", 0.9))


def _table_cells(element: SlideElement) -> tuple[int, int, list[list[str]]]:
    rows = max(1, int(element.metadata.get("rows", 3) or 3))
    cols = max(1, int(element.metadata.get("cols", 3) or 3))
    raw_cells = element.metadata.get("cells")
    cells: list[list[str]] = []
    if isinstance(raw_cells, list):
        for row in raw_cells[:rows]:
            if isinstance(row, list):
                cells.append([str(cell) for cell in row[:cols]])
    while len(cells) < rows:
        cells.append([])
    for row_index, row in enumerate(cells):
        while len(row) < cols:
            row.append(f"Cell {row_index + 1}-{len(row) + 1}")
    return rows, cols, cells


def _draw_table(
    draw: ImageDraw.ImageDraw,
    element: SlideElement,
    box: tuple[int, int, int, int],
    *,
    font_scale: float = 1.0,
) -> None:
    left, top, right, bottom = box
    rows, cols, cells = _table_cells(element)
    width = max(1, right - left)
    height = max(1, bottom - top)
    cell_w = width / cols
    cell_h = height / rows
    header = bool(element.metadata.get("header", True))
    header_fill = str(element.metadata.get("header_fill") or "#EAF1FF")
    body_fill = str(element.metadata.get("body_fill") or element.style.fill or "#FFFFFF")
    grid_color = str(element.metadata.get("grid_color") or element.style.stroke or "#B8C2D6")
    font = _font(max(8, int(round(float(element.style.font_size or 16) * font_scale))), bool(element.style.bold), False, element.style.font_family)
    for row in range(rows):
        for col in range(cols):
            x0 = int(round(left + col * cell_w))
            y0 = int(round(top + row * cell_h))
            x1 = int(round(left + (col + 1) * cell_w))
            y1 = int(round(top + (row + 1) * cell_h))
            fill = header_fill if header and row == 0 else body_fill
            draw.rectangle((x0, y0, x1, y1), fill=_rgba(fill, element.opacity), outline=_rgb(grid_color), width=1)
            text = format_formula_value(cells[row][col], cells=cells)
            bbox = draw.textbbox((0, 0), text, font=font)
            tx = x0 + 8
            ty = y0 + max(3, int((y1 - y0 - (bbox[3] - bbox[1])) / 2))
            draw.text((tx, ty), text, font=font, fill=_rgba(element.style.color or "#182033", element.opacity))


def _draw_line(draw: ImageDraw.ImageDraw, element: SlideElement, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    stroke = element.style.stroke or element.style.color or "#2F6FED"
    width = max(1, int(round(float(element.style.stroke_width or 2))))
    y = top + max(1, bottom - top) // 2
    draw.line((left, y, right, y), fill=_rgba(stroke, element.opacity), width=width)


def _draw_chart(
    draw: ImageDraw.ImageDraw,
    element: SlideElement,
    box: tuple[int, int, int, int],
    *,
    font_scale: float = 1.0,
) -> None:
    left, top, right, bottom = box
    fill = element.style.fill or "#F7F9FC"
    stroke = element.style.stroke or "#2F6FED"
    draw.rounded_rectangle(box, radius=14, fill=_rgba(fill, element.opacity), outline=_rgb(stroke), width=max(1, int(element.style.stroke_width or 1)))
    raw_labels = element.metadata.get("labels") or ["A", "B", "C", "D"]
    raw_values = element.metadata.get("values") or [32, 58, 44, 72]
    labels = [str(label) for label in raw_labels] if isinstance(raw_labels, list) else ["A", "B", "C", "D"]
    source_values = list(raw_values) if isinstance(raw_values, list) else [32.0, 58.0, 44.0, 72.0]
    cells = [[labels[index] if index < len(labels) else f"Item {index + 1}", value] for index, value in enumerate(source_values)]
    values: list[float] = []
    for value in source_values:
        try:
            values.append(evaluate_numeric_formula(value, cells=cells))
        except Exception:
            values.append(0.0)
    if not values:
        values = [32.0, 58.0, 44.0, 72.0]
    count = max(1, min(len(labels), len(values), 8))
    labels = labels[:count] or ["A"]
    values = values[:count] or [1.0]
    max_value = max(1.0, max(values))
    pad_x = max(14, int((right - left) * 0.08))
    pad_y = max(14, int((bottom - top) * 0.12))
    plot_left = left + pad_x
    plot_right = right - pad_x
    plot_top = top + pad_y
    plot_bottom = bottom - pad_y
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill=_rgb("#9AA7BA"), width=1)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill=_rgb("#9AA7BA"), width=1)
    gap = max(3, int((plot_right - plot_left) * 0.04 / count))
    slot = max(1, (plot_right - plot_left) / count)
    bar_w = max(2, int(slot - gap * 2))
    bar_fill = str(element.metadata.get("bar_fill") or "#2F6FED")
    font = _font(max(7, int(round(11 * font_scale))), False, False, element.style.font_family)
    for index, (label, value) in enumerate(zip(labels, values)):
        x0 = int(round(plot_left + index * slot + gap))
        x1 = x0 + bar_w
        y1 = plot_bottom
        y0 = int(round(plot_bottom - (plot_bottom - plot_top) * max(0.0, value) / max_value))
        draw.rounded_rectangle((x0, y0, x1, y1), radius=4, fill=_rgba(bar_fill, element.opacity))
        bbox = draw.textbbox((0, 0), label, font=font)
        tx = x0 + max(0, bar_w - (bbox[2] - bbox[0])) // 2
        draw.text((tx, min(bottom - 13, plot_bottom + 3)), label, font=font, fill=_rgba("#5E6A7D", element.opacity))


def render_slide_image(
    deck: DeckSpec,
    slide: SlideSpec,
    *,
    size: tuple[int, int] = DEFAULT_SIZE,
    playhead_ms: int | None = None,
) -> Image.Image:
    background = slide.background or deck.theme.background
    image = Image.new("RGBA", size, _rgba(background, 1.0))
    draw = ImageDraw.Draw(image, "RGBA")
    font_scale = max(0.25, min(2.0, size[0] / float(DEFAULT_SIZE[0])))
    for element in sorted(slide.elements, key=lambda row: int(row.z_index)):
        if not element.visible:
            continue
        state = element_animation_state(element, playhead_ms)
        if not state.visible:
            continue
        draw_element = _with_opacity(element, state.opacity)
        box = _box_from_xywh(animated_rect(_rect_xywh(element, size), size, state))
        if draw_element.kind in {"text", "typography_actor"}:
            if draw_element.style.fill:
                draw.rounded_rectangle(box, radius=int(draw_element.style.radius or 0), fill=_rgba(draw_element.style.fill, draw_element.opacity))
            _draw_text(draw, draw_element, box, font_scale=font_scale)
        elif draw_element.kind == "table":
            _draw_table(draw, draw_element, box, font_scale=font_scale)
        elif draw_element.kind == "line":
            _draw_line(draw, draw_element, box)
        elif draw_element.kind == "chart":
            _draw_chart(draw, draw_element, box, font_scale=font_scale)
        elif draw_element.kind in {"image", "timeline_moment", "screen_capture"} and draw_element.source_path:
            loaded = _cover_image(Path(draw_element.source_path), max(1, box[2] - box[0]), max(1, box[3] - box[1]))
            if loaded is None:
                _draw_placeholder(draw, draw_element, box, font_scale=font_scale)
            else:
                if draw_element.opacity < 0.999:
                    alpha = loaded.getchannel("A").point(lambda value: int(value * draw_element.opacity))
                    loaded.putalpha(alpha)
                image.alpha_composite(loaded, (box[0], box[1]))
        elif draw_element.kind in ACTOR_PLACEHOLDER_KINDS:
            poster = _actor_poster_path(draw_element)
            loaded = _cover_image(poster, max(1, box[2] - box[0]), max(1, box[3] - box[1])) if poster is not None else None
            if loaded is None:
                _draw_placeholder(draw, draw_element, box, font_scale=font_scale)
            else:
                if draw_element.opacity < 0.999:
                    alpha = loaded.getchannel("A").point(lambda value: int(value * draw_element.opacity))
                    loaded.putalpha(alpha)
                image.alpha_composite(loaded, (box[0], box[1]))
        elif draw_element.kind == "shape":
            draw.rounded_rectangle(
                box,
                radius=int(draw_element.style.radius or 10),
                fill=_rgba(draw_element.style.fill or deck.theme.surface, draw_element.opacity),
                outline=_rgb(draw_element.style.stroke or deck.theme.accent),
                width=max(0, int(round(draw_element.style.stroke_width or 0))),
            )
        else:
            _draw_placeholder(draw, draw_element, box, font_scale=font_scale)
    try:
        slide_index = deck.slides.index(slide) + 1
    except ValueError:
        slide_index = 1
    for overlay in slide_overlay_elements(deck, slide.id, slide_index=slide_index, slide_count=len(deck.slides)):
        _draw_text(draw, overlay, _rect(overlay, size), font_scale=font_scale)
    return image.convert("RGB")


def render_deck_pngs(deck: DeckSpec, output_dir: str | Path, *, size: tuple[int, int] = DEFAULT_SIZE) -> list[Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for index, slide in enumerate(deck.slides, start=1):
        path = out / f"slide_{index:03d}.png"
        render_slide_image(deck, slide, size=size).save(path)
        paths.append(path)
    return paths


def render_contact_sheet(deck: DeckSpec, output_path: str | Path, *, thumb_size: tuple[int, int] = (320, 180)) -> Path:
    count = max(1, len(deck.slides))
    cols = min(3, count)
    rows = int(math.ceil(count / cols))
    gap = 18
    sheet = Image.new("RGB", (cols * thumb_size[0] + (cols + 1) * gap, rows * (thumb_size[1] + 32) + (rows + 1) * gap), "#F0F3F8")
    draw = ImageDraw.Draw(sheet)
    font = _font(16, True)
    for idx, slide in enumerate(deck.slides):
        col = idx % cols
        row = idx // cols
        x = gap + col * (thumb_size[0] + gap)
        y = gap + row * (thumb_size[1] + 32 + gap)
        thumb = render_slide_image(deck, slide, size=thumb_size)
        sheet.paste(thumb, (x, y))
        draw.text((x, y + thumb_size[1] + 8), f"{idx + 1}. {slide.title or slide.id}", font=font, fill="#182033")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


__all__ = ["DEFAULT_SIZE", "render_contact_sheet", "render_deck_pngs", "render_slide_image"]
