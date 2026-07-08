"""Timeline paint helpers for Final Cut-style NLE feedback.

The pure builders in this module keep the visual rules testable while the
paint helpers keep TrackRow from accumulating more inline drawing code.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygon

from app.nle_connected_clips import ROLE_LABELS, infer_clip_role, normalize_clip_role, role_color_for


CLIP_ANCHOR_CUE_SCHEMA = "tigerstudio.timeline.clip_anchor_cue.v1"
DRAG_PREVIEW_VISUAL_SCHEMA = "tigerstudio.timeline.drag_preview_visual.v1"
ROLE_FOCUS_CUE_SCHEMA = "tigerstudio.timeline.role_focus_cue.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def build_clip_anchor_cue(track: Any, clip: Any, *, selected: bool = False) -> dict[str, Any]:
    """Return a small UI cue for role/connected-clip anchor painting."""

    parent_clip_id = getattr(clip, "connected_parent_clip_id", None)
    parent_track_id = getattr(clip, "connected_parent_track_id", None)
    connected = parent_clip_id is not None or parent_track_id is not None
    explicit_role = str(getattr(clip, "clip_role", "") or "").strip()
    if not connected and not explicit_role:
        return {"schema": CLIP_ANCHOR_CUE_SCHEMA, "ready": False}

    try:
        role = infer_clip_role(track, clip)
    except Exception:
        role = explicit_role or "primary"
    color = role_color_for(role, str(getattr(clip, "role_color", "") or ""))
    label = ROLE_LABELS.get(role, role.replace("_", " ").title())
    start_ms = _int(getattr(clip, "timeline_in_ms", 0), 0)
    offset_ms = _int(getattr(clip, "connected_offset_ms", 0), 0)
    return {
        "schema": CLIP_ANCHOR_CUE_SCHEMA,
        "ready": True,
        "clip_id": _int(getattr(clip, "id", -1), -1),
        "role": role,
        "label": label,
        "color": color,
        "selected": bool(selected),
        "connected": bool(connected),
        "state": "connected" if connected else "role",
        "anchor_ms": start_ms,
        "connected_offset_ms": offset_ms,
    }


def build_drag_preview_visual_cue(tone: str) -> dict[str, Any]:
    """Normalize drag feedback tone into painter-friendly visual metadata."""

    normalized = str(tone or "move").strip().casefold()
    if normalized in {"blocked", "collision"}:
        return {
            "schema": DRAG_PREVIEW_VISUAL_SCHEMA,
            "tone": "blocked",
            "label": "BLOCKED",
            "accent": "#FF687E",
            "fill": "#FF506E",
            "alpha": 62,
            "edge_alpha": 235,
            "field_lines": 0,
            "hatch": True,
        }
    if normalized in {"snap", "magnetic"}:
        return {
            "schema": DRAG_PREVIEW_VISUAL_SCHEMA,
            "tone": "snap",
            "label": "SNAP",
            "accent": "#7EDBFF",
            "fill": "#7068FF",
            "alpha": 56,
            "edge_alpha": 230,
            "field_lines": 3,
            "hatch": False,
        }
    if normalized in {"push", "ripple"}:
        return {
            "schema": DRAG_PREVIEW_VISUAL_SCHEMA,
            "tone": "push",
            "label": "MAGNETIC",
            "accent": "#65D6A6",
            "fill": "#42C6AE",
            "alpha": 48,
            "edge_alpha": 218,
            "field_lines": 2,
            "hatch": False,
        }
    return {
        "schema": DRAG_PREVIEW_VISUAL_SCHEMA,
        "tone": "move",
        "label": "MOVE",
        "accent": "#E6EBFF",
        "fill": "#FFFFFF",
        "alpha": 30,
        "edge_alpha": 170,
        "field_lines": 0,
        "hatch": False,
    }


def build_role_focus_cue(track: Any, clip: Any, focused_role: str = "") -> dict[str, Any]:
    """Return whether a clip should be dimmed by a focused role filter."""

    focus_text = str(focused_role or "").strip()
    if not focus_text:
        return {"schema": ROLE_FOCUS_CUE_SCHEMA, "ready": False, "dimmed": False}
    focus = normalize_clip_role(focus_text, fallback="primary")
    try:
        role = infer_clip_role(track, clip)
    except Exception:
        role = normalize_clip_role(str(getattr(clip, "clip_role", "") or ""), fallback="primary")
    dimmed = role != focus
    return {
        "schema": ROLE_FOCUS_CUE_SCHEMA,
        "ready": True,
        "focused_role": focus,
        "role": role,
        "dimmed": bool(dimmed),
        "clip_id": _int(getattr(clip, "id", -1), -1),
    }


def _valid_color(text: str, fallback: str) -> QColor:
    color = QColor(str(text or ""))
    if not color.isValid():
        color = QColor(fallback)
    return color


def paint_clip_anchor_cue(painter: QPainter, clip_rect: QRect, cue: dict[str, Any]) -> None:
    """Paint a compact connected-clip anchor cue inside a timeline clip."""

    if not cue.get("ready") or not cue.get("connected"):
        return
    if clip_rect.width() < 24 or clip_rect.height() < 22:
        return

    accent = _valid_color(str(cue.get("color") or ""), "#5EA2FF")
    accent_line = QColor(accent)
    accent_line.setAlpha(205 if cue.get("selected") else 150)
    accent_soft = QColor(accent)
    accent_soft.setAlpha(70)

    anchor_x = clip_rect.left() + min(max(14, clip_rect.width() // 6), max(14, clip_rect.width() - 12))
    rail_y = clip_rect.top() + 5
    diamond_y = min(clip_rect.bottom() - 9, clip_rect.top() + 22)

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    if clip_rect.width() >= 48:
        leash = QRect(clip_rect.left() + 5, rail_y, max(8, anchor_x - clip_rect.left() - 12), 2)
        grad = QLinearGradient(leash.topLeft(), leash.topRight())
        grad.setColorAt(0.0, accent_soft)
        fade = QColor(accent_soft)
        fade.setAlpha(0)
        grad.setColorAt(1.0, fade)
        painter.fillRect(leash, grad)

    painter.setPen(QPen(accent_line, 1.4))
    painter.drawLine(anchor_x, rail_y + 1, anchor_x, diamond_y - 6)
    node = QPolygon(
        [
            QPoint(anchor_x, diamond_y - 6),
            QPoint(anchor_x + 6, diamond_y),
            QPoint(anchor_x, diamond_y + 6),
            QPoint(anchor_x - 6, diamond_y),
        ]
    )
    fill = QColor(accent)
    fill.setAlpha(235 if cue.get("selected") else 205)
    painter.setBrush(fill)
    painter.setPen(QPen(QColor(255, 255, 255, 86), 1))
    painter.drawPolygon(node)
    painter.restore()


def paint_drag_preview_guides(
    painter: QPainter,
    ghost: QRect,
    cue: dict[str, Any],
    *,
    pop: float = 0.0,
) -> None:
    """Paint inner guide marks for a drag preview rectangle."""

    if ghost.width() < 18 or ghost.height() < 10:
        return
    accent = _valid_color(str(cue.get("accent") or ""), "#E6EBFF")
    accent.setAlpha(max(70, min(255, _int(cue.get("edge_alpha", 170), 170) + int(18 * pop))))
    mid_y = ghost.center().y()
    left = ghost.left() + 7
    right = ghost.right() - 7

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(accent, 1.2 + 0.4 * max(0.0, min(1.0, pop)))
    if cue.get("tone") == "blocked":
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.drawLine(left, mid_y, right, mid_y)
    field_lines = max(0, _int(cue.get("field_lines"), 0))
    if field_lines:
        for idx in range(field_lines):
            offset = 5 + idx * 5
            field = QColor(accent)
            field.setAlpha(max(18, 95 - idx * 24 + int(20 * pop)))
            painter.setPen(QPen(field, 1.0))
            painter.drawLine(ghost.left() - offset, ghost.top() + 5, ghost.left() - offset, ghost.bottom() - 5)
            painter.drawLine(ghost.right() + offset, ghost.top() + 5, ghost.right() + offset, ghost.bottom() - 5)
        painter.setPen(pen)
    if cue.get("hatch"):
        for x in range(left + 5, right, 13):
            painter.drawLine(x - 4, mid_y - 5, x + 4, mid_y + 5)
    else:
        chevron = max(5, min(9, ghost.width() // 12))
        for x in (left + chevron, right - chevron):
            painter.drawLine(x - chevron, mid_y - 5, x, mid_y)
            painter.drawLine(x - chevron, mid_y + 5, x, mid_y)
    if ghost.width() >= 76:
        label = str(cue.get("label") or "")
        font = painter.font()
        font.setPixelSize(7)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(245, 248, 255, 170))
        painter.drawText(
            ghost.adjusted(8, 2, -8, -2),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
            label,
        )
    painter.restore()


def paint_role_focus_dim(painter: QPainter, clip_rect: QRect, cue: dict[str, Any]) -> None:
    """Dim clips that are outside the focused role lane."""

    if not cue.get("ready") or not cue.get("dimmed"):
        return
    if clip_rect.width() <= 0 or clip_rect.height() <= 0:
        return
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(4, 6, 13, 118))
    painter.drawRoundedRect(clip_rect.adjusted(1, 2, -1, -2), 5, 5)
    painter.setPen(QPen(QColor(255, 255, 255, 30), 1, Qt.PenStyle.DotLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(clip_rect.adjusted(4, 5, -4, -5), 4, 4)
    painter.restore()


__all__ = [
    "CLIP_ANCHOR_CUE_SCHEMA",
    "DRAG_PREVIEW_VISUAL_SCHEMA",
    "ROLE_FOCUS_CUE_SCHEMA",
    "build_clip_anchor_cue",
    "build_drag_preview_visual_cue",
    "build_role_focus_cue",
    "paint_clip_anchor_cue",
    "paint_drag_preview_guides",
    "paint_role_focus_dim",
]
