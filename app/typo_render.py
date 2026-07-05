"""Offscreen typography rendering for export.

Mirrors the live preview's rendering pipeline (whole-text fast path +
per-glyph dispatch for Folding) but writes into a fresh QImage with
alpha so the result can be composited as a video overlay during MP4
export.

Public entry points:

* ``render_clip_frames(clip, frame_w, frame_h, fps)`` → iterator of
  ``QImage`` (RGBA, premultiplied alpha cleared each frame).
* ``encode_frames_to_mov(frames, out_path, fps)`` → encodes the frame
  iterable as a small MOV with the QtRLE codec (alpha-preserving,
  widely supported by FFmpeg).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)

from app.subprocess_utils import hidden_subprocess_kwargs


def _draw_text_whole(
    painter: QPainter,
    clip,
    cx: float,
    cy: float,
    xf,
) -> None:
    """Whole-text rendering — geometric transform around the text's
    centre, then a single drawText per line. Mirrors the same path in
    the live preview."""
    text = clip.text or ""
    if not text:
        return
    style = clip.style

    font = QFont(style.font_family, int(style.font_size))
    font.setWeight(QFont.Weight(int(style.font_weight)))
    if style.letter_spacing:
        font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            float(style.letter_spacing),
        )
    painter.setFont(font)
    fm = QFontMetrics(font)

    lines = text.split("\n")
    line_h = int(fm.height() * float(style.line_height))
    total_h = max(line_h, line_h * len(lines))
    widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
    block_x = cx - widest / 2.0
    block_y = cy - total_h / 2.0

    painter.save()
    painter.setOpacity(max(0.0, min(1.0, xf.opacity)))
    painter.translate(cx + xf.offset_x, cy + xf.offset_y)
    if abs(xf.rotation_deg) > 0.05:
        painter.rotate(xf.rotation_deg)
    if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
        painter.scale(xf.scale_x, xf.scale_y)
    painter.translate(-cx, -cy)

    if style.background_color:
        pad = max(0, int(style.background_padding))
        radius = max(0, int(style.background_radius))
        painter.setBrush(QColor(style.background_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            int(block_x - pad), int(block_y - pad),
            int(widest + 2 * pad), int(total_h + 2 * pad),
            radius, radius,
        )

    for i, ln in enumerate(lines):
        ln_w = fm.horizontalAdvance(ln)
        if style.alignment == "left":
            lx = block_x
        elif style.alignment == "right":
            lx = block_x + (widest - ln_w)
        else:
            lx = block_x + (widest - ln_w) / 2.0
        ly = block_y + i * line_h + fm.ascent()

        if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
            painter.setPen(QColor(style.shadow_color))
            painter.drawText(
                int(lx + style.shadow_offset_x),
                int(ly + style.shadow_offset_y),
                ln,
            )

        if style.outline_color and style.outline_width and style.outline_width > 0:
            path = QPainterPath()
            path.addText(lx, ly, font, ln)
            pen = QPen(QColor(style.outline_color))
            pen.setWidth(int(style.outline_width))
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        painter.setPen(QColor(style.color or "#FFFFFF"))
        painter.drawText(int(lx), int(ly), ln)

    painter.restore()


def _draw_text_perglyph(
    painter: QPainter,
    clip,
    cx: float,
    cy: float,
    glyph_xfs: list,
) -> None:
    """Per-glyph rendering — each char drawn with its own transform
    around its own pivot. Mirrors the live preview's per-glyph path."""
    text = clip.text or ""
    if not text:
        return
    style = clip.style

    font = QFont(style.font_family, int(style.font_size))
    font.setWeight(QFont.Weight(int(style.font_weight)))
    if style.letter_spacing:
        font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            float(style.letter_spacing),
        )
    painter.setFont(font)
    fm = QFontMetrics(font)

    lines = text.split("\n")
    line_h = int(fm.height() * float(style.line_height))
    total_h = max(line_h, line_h * len(lines))
    widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
    block_x = cx - widest / 2.0
    block_y = cy - total_h / 2.0

    if style.background_color:
        pad = max(0, int(style.background_padding))
        radius = max(0, int(style.background_radius))
        painter.setBrush(QColor(style.background_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            int(block_x - pad), int(block_y - pad),
            int(widest + 2 * pad), int(total_h + 2 * pad),
            radius, radius,
        )

    mono = bool(getattr(clip.animation, "mono_color", False))
    char_idx = 0
    for line_no, ln in enumerate(lines):
        ln_w = fm.horizontalAdvance(ln)
        if style.alignment == "left":
            lx = block_x
        elif style.alignment == "right":
            lx = block_x + (widest - ln_w)
        else:
            lx = block_x + (widest - ln_w) / 2.0
        ly = block_y + line_no * line_h + fm.ascent()

        cursor_x = lx
        for ch in ln:
            gx = cursor_x
            gw = fm.horizontalAdvance(ch)
            if char_idx < len(glyph_xfs):
                xf = glyph_xfs[char_idx]
            else:
                xf = glyph_xfs[-1] if glyph_xfs else None
            char_idx += 1

            if xf is None or ch.strip() == "":
                cursor_x += gw
                continue

            pivot_px_x = gx + gw * float(xf.pivot_x)
            pivot_px_y = (ly - fm.ascent()) + fm.height() * float(xf.pivot_y)

            painter.save()
            painter.setOpacity(max(0.0, min(1.0, xf.opacity)))
            painter.translate(
                pivot_px_x + xf.offset_x,
                pivot_px_y + xf.offset_y,
            )
            if abs(xf.rotation_deg) > 0.05:
                painter.rotate(xf.rotation_deg)
            if abs(xf.scale_x - 1.0) > 1e-3 or abs(xf.scale_y - 1.0) > 1e-3:
                painter.scale(xf.scale_x, xf.scale_y)
            painter.translate(-pivot_px_x, -pivot_px_y)

            if style.shadow_color and (style.shadow_offset_x or style.shadow_offset_y):
                painter.setPen(QColor(style.shadow_color))
                painter.drawText(
                    int(gx + style.shadow_offset_x),
                    int(ly + style.shadow_offset_y),
                    ch,
                )
            if style.outline_color and style.outline_width and style.outline_width > 0:
                path = QPainterPath()
                path.addText(gx, ly, font, ch)
                pen = QPen(QColor(style.outline_color))
                pen.setWidth(int(style.outline_width))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            if mono:
                fill_color = style.color or "#FFFFFF"
            else:
                fill_color = xf.color_override or style.color or "#FFFFFF"
            painter.setPen(QColor(fill_color))
            painter.drawText(int(gx), int(ly), ch)
            painter.restore()
            cursor_x += gw
        if line_no < len(lines) - 1:
            char_idx += 1   # account for the implicit \n


def _draw_text_layers(
    painter: QPainter,
    clip,
    cx: float,
    cy: float,
    layers: list,
) -> None:
    """Multi-layer rendering — full text drawn once per LayerTransform."""
    text = clip.text or ""
    if not text:
        return
    style = clip.style

    font = QFont(style.font_family, int(style.font_size))
    font.setWeight(QFont.Weight(int(style.font_weight)))
    if style.letter_spacing:
        font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            float(style.letter_spacing),
        )
    painter.setFont(font)
    fm = QFontMetrics(font)

    lines = text.split("\n")
    line_h = int(fm.height() * float(style.line_height))
    total_h = max(line_h, line_h * len(lines))
    widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
    block_x = cx - widest / 2.0
    block_y = cy - total_h / 2.0

    if style.background_color:
        pad = max(0, int(style.background_padding))
        radius = max(0, int(style.background_radius))
        painter.setBrush(QColor(style.background_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(
            int(block_x - pad), int(block_y - pad),
            int(widest + 2 * pad), int(total_h + 2 * pad),
            radius, radius,
        )

    mono = bool(getattr(clip.animation, "mono_color", False))
    for layer in layers:
        painter.save()
        painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
        painter.translate(layer.offset_x, layer.offset_y)
        if mono:
            fill_color = style.color or "#FFFFFF"
        else:
            fill_color = layer.color_override or style.color or "#FFFFFF"

        for i, ln in enumerate(lines):
            ln_w = fm.horizontalAdvance(ln)
            if style.alignment == "left":
                lx = block_x
            elif style.alignment == "right":
                lx = block_x + (widest - ln_w)
            else:
                lx = block_x + (widest - ln_w) / 2.0
            ly = block_y + i * line_h + fm.ascent()

            is_top = layer is layers[-1]
            if is_top and style.outline_color and style.outline_width and style.outline_width > 0:
                path = QPainterPath()
                path.addText(lx, ly, font, ln)
                pen = QPen(QColor(style.outline_color))
                pen.setWidth(int(style.outline_width))
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            painter.setPen(QColor(fill_color))
            painter.drawText(int(lx), int(ly), ln)
        painter.restore()


def render_clip_frame(clip, time_s: float, frame_w: int, frame_h: int) -> QImage:
    """Render one frame of ``clip`` at ``time_s`` (seconds since clip
    start) into a transparent RGBA QImage of ``frame_w``×``frame_h``."""
    from app.typo_animations import (
        compute_clip_transform, compute_clip_glyph_transforms,
        compute_clip_layers, TextTransform,
    )

    img = QImage(frame_w, frame_h, QImage.Format.Format_ARGB32)
    img.fill(0)  # fully transparent

    if not clip.text:
        return img

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    style = clip.style
    cx = float(style.position_x) * frame_w
    cy = float(style.position_y) * frame_h

    # Multi-layer first (RGB split), then per-glyph, then whole-text.
    layers = compute_clip_layers(clip, time_s)
    if layers is not None:
        _draw_text_layers(painter, clip, cx, cy, layers)
    else:
        glyph_xfs = compute_clip_glyph_transforms(
            clip, time_s, len(clip.text or "")
        )
        if glyph_xfs is not None:
            _draw_text_perglyph(painter, clip, cx, cy, glyph_xfs)
        else:
            xf = compute_clip_transform(clip, time_s) or TextTransform.identity()
            _draw_text_whole(painter, clip, cx, cy, xf)

    painter.end()
    return img


def render_clip_to_mov(
    clip,
    out_path: Path,
    frame_w: int,
    frame_h: int,
    fps: int = 30,
) -> bool:
    """Pre-render a TextClip's full duration to a QtRLE-encoded MOV
    with alpha. Returns True on success.

    QtRLE = Apple Animation, lossless, RGBA — supported by every modern
    FFmpeg build and easy to overlay later via the ``-i input.mov`` +
    ``overlay`` filter pipeline.
    """
    from imageio_ffmpeg import get_ffmpeg_exe

    duration_s = clip.duration_s
    if duration_s <= 0:
        return False
    total_frames = max(1, int(round(duration_s * fps)))

    tmp_dir = tempfile.mkdtemp(prefix="tigercapture_typo_")
    try:
        for n in range(total_frames):
            t = n / fps
            img = render_clip_frame(clip, t, frame_w, frame_h)
            png_path = os.path.join(tmp_dir, f"frame_{n:05d}.png")
            if not img.save(png_path, "PNG"):
                return False

        cmd = [
            get_ffmpeg_exe(),
            "-y",
            "-hide_banner", "-loglevel", "error",
            "-framerate", str(int(fps)),
            "-i", os.path.join(tmp_dir, "frame_%05d.png"),
            "-c:v", "qtrle",
            "-pix_fmt", "argb",
            str(out_path),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True, text=True, errors="replace",
            **hidden_subprocess_kwargs(),
        )
        return proc.returncode == 0
    finally:
        # Best-effort cleanup of the PNG sequence.
        try:
            for fn in os.listdir(tmp_dir):
                try:
                    os.unlink(os.path.join(tmp_dir, fn))
                except OSError:
                    pass
            os.rmdir(tmp_dir)
        except OSError:
            pass
