"""Canvas controls for Painter UI Auto Layout."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from app.painter_ui_auto_layout import normalize_ui_auto_layout


_CONTAINER_KINDS = {"frame", "group"}
_MAIN_ALIGNMENT_LABELS = {
    "start": "M<",
    "center": "M=",
    "end": "M>",
    "space_between": "M|",
}
_CROSS_ALIGNMENT_LABELS = {
    "start": "C<",
    "center": "C=",
    "end": "C>",
    "stretch": "C#",
}
_MAIN_ALIGNMENT_ORDER = ("start", "center", "end", "space_between")
_CROSS_ALIGNMENT_ORDER = ("start", "center", "end", "stretch")
_TOOLTIPS = {
    "mode_horizontal": "Horizontal Auto Layout",
    "mode_vertical": "Vertical Auto Layout",
    "main_alignment": "Cycle main-axis alignment",
    "cross_alignment": "Cycle cross-axis alignment",
    "gap": "Drag to adjust item gap",
    "positioning": "Toggle flow or absolute positioning",
    "padding_left": "Drag to adjust left padding",
    "padding_top": "Drag to adjust top padding",
    "padding_right": "Drag to adjust right padding",
    "padding_bottom": "Drag to adjust bottom padding",
}


@dataclass(frozen=True)
class AutoLayoutCanvasControl:
    target: str
    rect: QRectF
    label: str
    active: bool = False


@dataclass(frozen=True)
class AutoLayoutCanvasControls:
    object_id: str
    controls: tuple[AutoLayoutCanvasControl, ...]
    padding_handles: tuple[AutoLayoutCanvasControl, ...]
    layout: dict[str, Any]

    def hit_test(self, point: QPointF) -> str:
        for control in (*self.controls, *self.padding_handles):
            if control.rect.contains(point):
                return control.target
        return ""

    def control(self, target: str) -> AutoLayoutCanvasControl | None:
        return next(
            (
                control
                for control in (*self.controls, *self.padding_handles)
                if control.target == target
            ),
            None,
        )


def _parent_auto_layout(
    row: Mapping[str, Any],
    document: Mapping[str, Any],
) -> dict[str, Any] | None:
    parent_id = str(row.get("parent_id") or "")
    if not parent_id:
        return None
    parent = next(
        (
            item
            for item in document.get("objects", [])
            if str(item.get("id") or "") == parent_id
        ),
        None,
    )
    if parent is None:
        return None
    layout = normalize_ui_auto_layout(parent.get("layout"))
    return layout if layout["mode"] in {"horizontal", "vertical"} else None


def build_auto_layout_canvas_controls(
    row: Mapping[str, Any] | None,
    rect: QRectF,
    document: Mapping[str, Any],
    bounds: QRectF,
    *,
    scale: float,
) -> AutoLayoutCanvasControls | None:
    if row is None or bool(row.get("locked", False)) or rect.isNull():
        return None
    layout = normalize_ui_auto_layout(row.get("layout"))
    is_container = str(row.get("kind") or "") in _CONTAINER_KINDS
    parent_layout = _parent_auto_layout(row, document)
    if not is_container and parent_layout is None:
        return None

    definitions: list[tuple[str, float, str, bool]] = []
    if is_container:
        definitions.extend(
            (
                ("mode_horizontal", 28.0, "H", layout["mode"] == "horizontal"),
                ("mode_vertical", 28.0, "V", layout["mode"] == "vertical"),
            )
        )
        if layout["mode"] in {"horizontal", "vertical"}:
            definitions.extend(
                (
                    (
                        "main_alignment",
                        36.0,
                        _MAIN_ALIGNMENT_LABELS[layout["main_alignment"]],
                        False,
                    ),
                    (
                        "cross_alignment",
                        36.0,
                        _CROSS_ALIGNMENT_LABELS[layout["cross_alignment"]],
                        False,
                    ),
                    ("gap", 54.0, f"G {layout['gap']:g}", False),
                )
            )
    if parent_layout is not None:
        definitions.append(
            (
                "positioning",
                54.0,
                "ABS" if layout["positioning"] == "absolute" else "FLOW",
                layout["positioning"] == "absolute",
            )
        )
    if not definitions:
        return None

    spacing = 3.0
    height = 26.0
    width = sum(item[1] for item in definitions)
    width += spacing * max(0, len(definitions) - 1)
    toolbar_x = max(
        bounds.left() + 6.0,
        min(rect.left(), bounds.right() - width - 6.0),
    )
    toolbar_y = (
        rect.top() - height - 34.0
        if rect.top() - height - 34.0 >= bounds.top() + 6.0
        else min(bounds.bottom() - height - 6.0, rect.bottom() + 10.0)
    )
    controls: list[AutoLayoutCanvasControl] = []
    cursor_x = toolbar_x
    for target, item_width, label, active in definitions:
        controls.append(
            AutoLayoutCanvasControl(
                target,
                QRectF(cursor_x, toolbar_y, item_width, height),
                label,
                active,
            )
        )
        cursor_x += item_width + spacing

    padding_handles: list[AutoLayoutCanvasControl] = []
    if is_container and layout["mode"] in {"horizontal", "vertical"}:
        padding = layout["padding"]
        scale = max(0.0001, float(scale))
        center = rect.center()
        vertical_span = max(12.0, min(36.0, rect.height() * 0.35))
        horizontal_span = max(12.0, min(36.0, rect.width() * 0.35))
        positions = {
            "padding_left": QRectF(
                rect.left() + float(padding["left"]) * scale - 5.0,
                center.y() - vertical_span * 0.5,
                10.0,
                vertical_span,
            ),
            "padding_right": QRectF(
                rect.right() - float(padding["right"]) * scale - 5.0,
                center.y() - vertical_span * 0.5,
                10.0,
                vertical_span,
            ),
            "padding_top": QRectF(
                center.x() - horizontal_span * 0.5,
                rect.top() + float(padding["top"]) * scale - 5.0,
                horizontal_span,
                10.0,
            ),
            "padding_bottom": QRectF(
                center.x() - horizontal_span * 0.5,
                rect.bottom() - float(padding["bottom"]) * scale - 5.0,
                horizontal_span,
                10.0,
            ),
        }
        for target, handle_rect in positions.items():
            edge = target.removeprefix("padding_")
            padding_handles.append(
                AutoLayoutCanvasControl(
                    target,
                    handle_rect,
                    f"{padding[edge]:g}",
                )
            )
    return AutoLayoutCanvasControls(
        str(row.get("id") or ""),
        tuple(controls),
        tuple(padding_handles),
        layout,
    )


def apply_auto_layout_canvas_click(
    layout: Mapping[str, Any] | None,
    target: str,
) -> dict[str, Any]:
    result = normalize_ui_auto_layout(layout)
    if target == "mode_horizontal":
        result["mode"] = "horizontal"
    elif target == "mode_vertical":
        result["mode"] = "vertical"
    elif target == "main_alignment":
        current = _MAIN_ALIGNMENT_ORDER.index(result["main_alignment"])
        result["main_alignment"] = _MAIN_ALIGNMENT_ORDER[
            (current + 1) % len(_MAIN_ALIGNMENT_ORDER)
        ]
    elif target == "cross_alignment":
        current = _CROSS_ALIGNMENT_ORDER.index(result["cross_alignment"])
        result["cross_alignment"] = _CROSS_ALIGNMENT_ORDER[
            (current + 1) % len(_CROSS_ALIGNMENT_ORDER)
        ]
    elif target == "positioning":
        result["positioning"] = (
            "auto" if result["positioning"] == "absolute" else "absolute"
        )
    return normalize_ui_auto_layout(result)


def apply_auto_layout_canvas_drag(
    layout: Mapping[str, Any] | None,
    target: str,
    delta: QPointF,
    *,
    scale: float,
) -> dict[str, Any]:
    result = copy.deepcopy(normalize_ui_auto_layout(layout))
    scale = max(0.0001, float(scale))
    dx = float(delta.x()) / scale
    dy = float(delta.y()) / scale
    if target == "gap":
        result["gap"] = max(0.0, round(float(result["gap"]) + dx))
    elif target.startswith("padding_"):
        edge = target.removeprefix("padding_")
        signed_delta = {
            "left": dx,
            "right": -dx,
            "top": dy,
            "bottom": -dy,
        }[edge]
        result["padding"][edge] = max(
            0.0,
            round(float(result["padding"][edge]) + signed_delta),
        )
    return normalize_ui_auto_layout(result)


def paint_auto_layout_canvas_controls(
    painter: QPainter,
    controls: AutoLayoutCanvasControls | None,
    *,
    active_target: str = "",
) -> None:
    if controls is None:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    font = painter.font()
    font.setPixelSize(10)
    font.setBold(True)
    painter.setFont(font)
    for control in controls.controls:
        active = control.active or control.target == active_target
        painter.setPen(QPen(QColor("#76A9FA") if active else QColor("#465163"), 1.0))
        painter.setBrush(QColor("#275EA8") if active else QColor("#171D26"))
        painter.drawRoundedRect(control.rect, 4.0, 4.0)
        painter.setPen(QColor("#F2F6FC") if active else QColor("#C7D0DC"))
        painter.drawText(
            control.rect,
            Qt.AlignmentFlag.AlignCenter,
            control.label,
        )
    for handle in controls.padding_handles:
        active = handle.target == active_target
        painter.setPen(
            QPen(QColor("#FFD37A") if active else QColor("#D9A847"), 1.0)
        )
        painter.setBrush(QColor("#FFC85A") if active else QColor("#D6A143"))
        painter.drawRoundedRect(handle.rect, 3.0, 3.0)
    painter.restore()


def auto_layout_canvas_tooltip(target: str) -> str:
    return _TOOLTIPS.get(str(target), "")


__all__ = [
    "AutoLayoutCanvasControl",
    "AutoLayoutCanvasControls",
    "apply_auto_layout_canvas_click",
    "apply_auto_layout_canvas_drag",
    "auto_layout_canvas_tooltip",
    "build_auto_layout_canvas_controls",
    "paint_auto_layout_canvas_controls",
]
