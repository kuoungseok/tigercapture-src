"""Read-only graph inspector for generated Unreal UMG UI materials.

The video workbench node graph owns video/color semantics, so this dialog only
borrows its visual tokens.  Its scene is a deliberately small, generated
projection of the provider-neutral UMG material record. Gradient and Rounded
Card materials use different fixed graphs, but neither graph is editable.
"""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from PySide6.QtCore import (
    QEvent,
    QLineF,
    QPoint,
    QPointF,
    QRectF,
    QSize,
    Signal,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.unreal_umg_material import (
    material_custom_hlsl,
    umg_material_graph,
    umg_material_preview_style,
    validate_umg_material_record,
)
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as GRAPH_COLORS,
    NODE_GRAPH_SIZES as GRAPH_SIZES,
)


_NODE_WIDTH = 190.0
_NODE_HEIGHT = 72.0
_PORT_RADIUS = 4.0

_NODE_ACCENTS = {
    "TextureCoordinate": "#55A8D7",
    "GeometryUV": "#55A8D7",
    "Fill": "#4EA89B",
    "CornersBorder": "#D8994B",
    "RoundedCardSDF": "#D8994B",
    "Shadows": "#7387D9",
    "Parameters": "#D8994B",
    "CustomHLSL": "#A878D4",
    "UIOutput": "#64B78A",
}


def _rgba_color(value: object, fallback: str = "#FFFFFFFF") -> QColor:
    """Parse the shared #RRGGBBAA format without Qt's #AARRGGBB ambiguity."""
    text = str(value or fallback).strip().lstrip("#")
    if len(text) == 6:
        text += "FF"
    if len(text) != 8:
        text = fallback.lstrip("#")
    try:
        return QColor(
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
            int(text[6:8], 16),
        )
    except ValueError:
        return QColor(255, 255, 255, 255)


def _finite_number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _style_mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rounded_card_radii(
    style: Mapping[str, Any],
    rect: QRectF,
) -> tuple[float, float, float, float]:
    """Return CSS-clamped TL/TR/BR/BL radii for a preview rectangle."""
    fallback = max(0.0, _finite_number(style.get("radius"), 0.0))
    source = _style_mapping(
        style.get("corner_radii") or style.get("CornerRadii")
    )

    def radius(*keys: str) -> float:
        for key in keys:
            if key in source:
                return max(0.0, _finite_number(source.get(key), fallback))
        return fallback

    radii = (
        radius("top_left", "TopLeft", "topLeft", "X"),
        radius("top_right", "TopRight", "topRight", "Y"),
        radius("bottom_right", "BottomRight", "bottomRight", "Z"),
        radius("bottom_left", "BottomLeft", "bottomLeft", "W"),
    )
    width = max(0.0, rect.width())
    height = max(0.0, rect.height())
    denominators = (
        radii[0] + radii[1],
        radii[3] + radii[2],
        radii[0] + radii[3],
        radii[1] + radii[2],
    )
    limits = (
        width / denominators[0] if denominators[0] > 0.0 else 1.0,
        width / denominators[1] if denominators[1] > 0.0 else 1.0,
        height / denominators[2] if denominators[2] > 0.0 else 1.0,
        height / denominators[3] if denominators[3] > 0.0 else 1.0,
    )
    scale = min(1.0, *limits)
    return tuple(value * scale for value in radii)


def _rounded_card_path(
    rect: QRectF,
    radii: tuple[float, float, float, float],
    smoothing: float = 0.0,
) -> QPainterPath:
    """Construct the v2 per-corner superellipse used by the local preview.

    The generated HLSL interpolates ``CornerPower`` from 2 (a conventional
    round corner) to 4 (a continuous/squircle corner). Sampling the same
    superellipse keeps the read-only Qt preview semantically aligned with that
    shader while remaining deterministic across platforms.
    """
    top_left, top_right, bottom_right, bottom_left = radii
    corner_power = 2.0 + 2.0 * max(0.0, min(1.0, _finite_number(smoothing)))
    exponent = 2.0 / corner_power
    samples = 12

    def component(value: float) -> float:
        return max(0.0, value) ** exponent

    path = QPainterPath()
    path.moveTo(rect.left() + top_left, rect.top())
    path.lineTo(rect.right() - top_right, rect.top())
    if top_right > 0.0:
        center_x = rect.right() - top_right
        center_y = rect.top() + top_right
        for index in range(1, samples + 1):
            angle = math.pi * 0.5 * (1.0 - index / samples)
            path.lineTo(
                center_x + top_right * component(math.cos(angle)),
                center_y - top_right * component(math.sin(angle)),
            )
    else:
        path.lineTo(rect.right(), rect.top())
    path.lineTo(rect.right(), rect.bottom() - bottom_right)
    if bottom_right > 0.0:
        center_x = rect.right() - bottom_right
        center_y = rect.bottom() - bottom_right
        for index in range(1, samples + 1):
            angle = math.pi * 0.5 * index / samples
            path.lineTo(
                center_x + bottom_right * component(math.cos(angle)),
                center_y + bottom_right * component(math.sin(angle)),
            )
    else:
        path.lineTo(rect.right(), rect.bottom())
    path.lineTo(rect.left() + bottom_left, rect.bottom())
    if bottom_left > 0.0:
        center_x = rect.left() + bottom_left
        center_y = rect.bottom() - bottom_left
        for index in range(1, samples + 1):
            angle = math.pi * 0.5 * (1.0 - index / samples)
            path.lineTo(
                center_x - bottom_left * component(math.cos(angle)),
                center_y + bottom_left * component(math.sin(angle)),
            )
    else:
        path.lineTo(rect.left(), rect.bottom())
    path.lineTo(rect.left(), rect.top() + top_left)
    if top_left > 0.0:
        center_x = rect.left() + top_left
        center_y = rect.top() + top_left
        for index in range(1, samples + 1):
            angle = math.pi * 0.5 * index / samples
            path.lineTo(
                center_x - top_left * component(math.cos(angle)),
                center_y - top_left * component(math.sin(angle)),
            )
    else:
        path.lineTo(rect.left(), rect.top())
    path.closeSubpath()
    return path


class _MaterialNodeItem(QGraphicsItem):
    """Compact, immutable node used by the generated-material inspector."""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        super().__init__()
        self.spec = copy.deepcopy(dict(spec))
        self.node_id = str(self.spec.get("id") or "")
        self.node_type = str(self.spec.get("type") or "Node")
        self.label = str(self.spec.get("label") or self.node_type)
        position = list(self.spec.get("position") or [0.0, 0.0])
        x = float(position[0]) if position else 0.0
        y = float(position[1]) if len(position) > 1 else 0.0
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setData(0, self.node_id)
        self._hovered = False

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        return QRectF(-5.0, -5.0, _NODE_WIDTH + 10.0, _NODE_HEIGHT + 10.0)

    def input_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(0.0, _NODE_HEIGHT / 2.0))

    def output_anchor(self) -> QPointF:
        return self.mapToScene(QPointF(_NODE_WIDTH, _NODE_HEIGHT / 2.0))

    def paint(self, painter: QPainter, option, widget=None) -> None:
        del option, widget
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body = QRectF(0.0, 0.0, _NODE_WIDTH, _NODE_HEIGHT)
        accent = QColor(_NODE_ACCENTS.get(self.node_type, "#7A8796"))

        shadow = body.translated(0.0, 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 78))
        painter.drawRoundedRect(shadow, 7.0, 7.0)

        border = QColor(GRAPH_COLORS["node_border_normal"])
        if self.isSelected():
            border = QColor(GRAPH_COLORS["node_border_selected"])
        elif self._hovered:
            border = QColor(GRAPH_COLORS["node_border_hover"])
        painter.setBrush(QColor(GRAPH_COLORS["node_bg_normal"]))
        painter.setPen(QPen(border, 1.4 if self.isSelected() else 1.0))
        painter.drawRoundedRect(body, 7.0, 7.0)

        header = QRectF(0.0, 0.0, _NODE_WIDTH, 25.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        painter.drawRoundedRect(header, 7.0, 7.0)
        painter.drawRect(QRectF(0.0, 18.0, _NODE_WIDTH, 7.0))

        title_font = QFont("Segoe UI")
        title_font.setPointSizeF(8.5)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#F5F7FA"))
        painter.drawText(
            QRectF(10.0, 1.0, _NODE_WIDTH - 20.0, 23.0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.label,
        )

        type_font = QFont("Segoe UI")
        type_font.setPointSizeF(7.5)
        painter.setFont(type_font)
        painter.setPen(QColor("#9FAAB7"))
        painter.drawText(
            QRectF(10.0, 31.0, _NODE_WIDTH - 20.0, 30.0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.node_type,
        )

        painter.setPen(QPen(QColor("#DCE5EF"), 1.0))
        painter.setBrush(QBrush(accent.lighter(125)))
        painter.drawEllipse(
            QPointF(0.0, _NODE_HEIGHT / 2.0),
            _PORT_RADIUS,
            _PORT_RADIUS,
        )
        painter.drawEllipse(
            QPointF(_NODE_WIDTH, _NODE_HEIGHT / 2.0),
            _PORT_RADIUS,
            _PORT_RADIUS,
        )

    def hoverEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)


class _MaterialConnectionItem(QGraphicsPathItem):
    """Non-editable cubic link between two material nodes."""

    def __init__(
        self,
        source: _MaterialNodeItem,
        target: _MaterialNodeItem,
        port_label: str,
    ) -> None:
        super().__init__()
        self.source = source
        self.target = target
        self.port_label = str(port_label or "")
        self.setZValue(-1.0)
        self.setPen(QPen(QColor("#8394A8"), 2.0))
        self._update_path()

    def _update_path(self) -> None:
        start = self.source.output_anchor()
        end = self.target.input_anchor()
        distance = abs(end.x() - start.x())
        control = max(52.0, distance * 0.48)
        path = QPainterPath(start)
        path.cubicTo(
            QPointF(start.x() + control, start.y()),
            QPointF(end.x() - control, end.y()),
            end,
        )
        self.setPath(path)


class _MaterialGraphScene(QGraphicsScene):
    """Small scene that validates and displays ``umg_material_graph`` output."""

    def __init__(self, graph: Mapping[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.graph = copy.deepcopy(dict(graph))
        self.node_items: dict[str, _MaterialNodeItem] = {}
        self.connection_items: list[_MaterialConnectionItem] = []
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)
        self.setBackgroundBrush(QColor(GRAPH_COLORS["canvas_bg"]))
        self._build()

    def _build(self) -> None:
        for node_spec in self.graph.get("nodes", []):
            if not isinstance(node_spec, Mapping):
                continue
            node = _MaterialNodeItem(node_spec)
            self.node_items[node.node_id] = node
            self.addItem(node)
        for connection_spec in self.graph.get("connections", []):
            if not isinstance(connection_spec, Mapping):
                continue
            source = self.node_items.get(str(connection_spec.get("from") or ""))
            target = self.node_items.get(str(connection_spec.get("to") or ""))
            if source is None or target is None:
                continue
            connection = _MaterialConnectionItem(
                source,
                target,
                str(connection_spec.get("port") or ""),
            )
            self.connection_items.append(connection)
            self.addItem(connection)
        bounds = self.itemsBoundingRect()
        self.setSceneRect(bounds.adjusted(-180.0, -160.0, 180.0, 160.0))


class _MaterialGraphView(QGraphicsView):
    """Grid view with wheel zoom and middle/Space+left drag panning."""

    def __init__(self, scene: QGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setObjectName("PainterUMGMaterialGraphView")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._zoom = 1.0
        self._panning = False
        self._space_down = False
        self._pan_origin = QPoint()
        self._restored_view_state = False

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        painter.fillRect(rect, QColor(GRAPH_COLORS["canvas_bg"]))
        for spacing, color_key, alpha in (
            (GRAPH_SIZES["grid_minor_spacing"], "grid_minor", 120),
            (GRAPH_SIZES["grid_major_spacing"], "grid_major", 180),
        ):
            color = QColor(GRAPH_COLORS[color_key])
            color.setAlpha(alpha)
            painter.setPen(QPen(color, 1.0))
            left = math.floor(rect.left() / spacing) * spacing
            top = math.floor(rect.top() / spacing) * spacing
            lines: list[QLineF] = []
            x = float(left)
            while x <= rect.right():
                lines.append(QLineF(x, rect.top(), x, rect.bottom()))
                x += spacing
            y = float(top)
            while y <= rect.bottom():
                lines.append(QLineF(rect.left(), y, rect.right(), y))
                y += spacing
            painter.drawLines(lines)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        direction = event.angleDelta().y()
        if not direction:
            event.ignore()
            return
        factor = (
            float(GRAPH_SIZES["zoom_step"])
            if direction > 0
            else 1.0 / float(GRAPH_SIZES["zoom_step"])
        )
        proposed = self._zoom * factor
        minimum = float(GRAPH_SIZES["min_zoom"])
        maximum = float(GRAPH_SIZES["max_zoom"])
        if minimum <= proposed <= maximum:
            self.scale(factor, factor)
            self._zoom = proposed
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = True
            if not self._panning:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = False
            if not self._panning:
                self.unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_down
        ):
            self._panning = True
            self._pan_origin = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._panning:
            position = event.position().toPoint()
            delta = position - self._pan_origin
            self._pan_origin = position
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._panning and event.button() in {
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        }:
            self._panning = False
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self._space_down
                else Qt.CursorShape.ArrowCursor
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._space_down = False
        self._panning = False
        self.unsetCursor()
        super().focusOutEvent(event)

    def fit_graph(self, *, force: bool = False) -> None:
        # Dock allocation can queue more than one automatic fit. Once a saved
        # graph transform has been restored, those late layout fits must not
        # overwrite it. The visible Fit graph button explicitly forces a fit.
        if self._restored_view_state and not force:
            return
        scene = self.scene()
        if scene is None or scene.itemsBoundingRect().isEmpty():
            return
        self.resetTransform()
        self.fitInView(
            scene.itemsBoundingRect().adjusted(-42.0, -42.0, 42.0, 42.0),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self._zoom = float(self.transform().m11())

    def zoom_level(self) -> float:
        return float(self._zoom)

    def view_state(self) -> dict[str, Any]:
        center = self.mapToScene(self.viewport().rect().center())
        return {
            "zoom": float(self._zoom),
            "center": [float(center.x()), float(center.y())],
        }

    def set_view_state(self, value: Mapping[str, Any] | None) -> None:
        state = value if isinstance(value, Mapping) else {}
        zoom = max(0.01, float(state.get("zoom") or 1.0))
        center = state.get("center")
        self.resetTransform()
        self.scale(zoom, zoom)
        self._zoom = zoom
        self._restored_view_state = True
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            self.centerOn(float(center[0]), float(center[1]))

    def space_pan_active(self) -> bool:
        return bool(self._space_down)


class _MaterialPreview(QWidget):
    """Paint the same normalized style used by the UMG comparison preview."""

    def __init__(self, preview_style: Mapping[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.preview_style = copy.deepcopy(dict(preview_style))
        self.setObjectName("PainterUMGMaterialPreview")
        self.setMinimumHeight(96)

    def _effects(self, effect_type: str) -> list[dict[str, Any]]:
        effects = self.preview_style.get("effects")
        rows = (
            [dict(row) for row in effects if isinstance(row, Mapping)]
            if isinstance(effects, list)
            else []
        )
        matching = [
            row
            for row in rows
            if str(row.get("type") or "").strip().casefold() == effect_type
            and bool(row.get("visible", True))
        ]
        if matching:
            return matching
        if effect_type == "drop_shadow":
            shadow = self.preview_style.get("shadow")
            if isinstance(shadow, Mapping):
                return [dict(shadow)]
        return []

    def _card_rect(self) -> QRectF:
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        # Keep outer effects visible in the compact inspector. The exact
        # VisualPadding remains in the material record; this is only a
        # scale-independent local presentation margin.
        extension = 0.0
        for effect in self._effects("drop_shadow"):
            extension = max(
                extension,
                abs(_finite_number(effect.get("x"), 0.0)),
                abs(_finite_number(effect.get("y"), 0.0)),
                max(0.0, _finite_number(effect.get("blur"), 0.0)) * 0.75,
                max(0.0, _finite_number(effect.get("spread"), 0.0)),
            )
        margin = max(10.0, min(28.0, 8.0 + extension))
        return rect.adjusted(margin, margin, -margin, -margin)

    def shape_path(self) -> QPainterPath:
        """Expose a copy-friendly preview path for deterministic UI tests."""
        rect = self._card_rect()
        return _rounded_card_path(
            rect,
            _rounded_card_radii(self.preview_style, rect),
            self._corner_smoothing(),
        )

    def _corner_smoothing(self) -> float:
        return max(
            0.0,
            min(
                1.0,
                _finite_number(
                    self.preview_style.get("corner_smoothing"),
                    0.0,
                ),
            ),
        )

    def _fill_brush(self, rect: QRectF) -> QBrush:
        gradient_spec = _style_mapping(self.preview_style.get("fill_gradient"))
        if not gradient_spec:
            fills = self.preview_style.get("fills")
            if isinstance(fills, list):
                paint = next(
                    (
                        dict(row)
                        for row in fills
                        if isinstance(row, Mapping)
                        and bool(row.get("visible", True))
                    ),
                    {},
                )
                gradient_spec = _style_mapping(paint.get("gradient"))
        if not gradient_spec:
            return QBrush(_rgba_color(self.preview_style.get("fill")))
        start = _style_mapping(gradient_spec.get("start"))
        end = _style_mapping(gradient_spec.get("end"))
        start_point = QPointF(
            rect.left() + _finite_number(start.get("x"), 0.0) * rect.width(),
            rect.top() + _finite_number(start.get("y"), 0.5) * rect.height(),
        )
        end_point = QPointF(
            rect.left() + _finite_number(end.get("x"), 1.0) * rect.width(),
            rect.top() + _finite_number(end.get("y"), 0.5) * rect.height(),
        )
        if str(gradient_spec.get("type") or "linear") == "radial":
            width = _style_mapping(gradient_spec.get("width"))
            width_point = QPointF(
                rect.left()
                + _finite_number(width.get("x"), 0.0) * rect.width(),
                rect.top()
                + _finite_number(width.get("y"), 1.0) * rect.height(),
            )
            axis_x = end_point - start_point
            axis_y = width_point - start_point
            if QLineF(QPointF(), axis_x).length() < 0.0001:
                axis_x = QPointF(1.0, 0.0)
            if QLineF(QPointF(), axis_y).length() < 0.0001:
                axis_y = QPointF(-axis_x.y(), axis_x.x())
            determinant = axis_x.x() * axis_y.y() - axis_x.y() * axis_y.x()
            if abs(determinant) < 0.0001:
                axis_y_length = max(
                    1.0,
                    QLineF(QPointF(), axis_y).length(),
                )
                axis_x_length = max(
                    0.0001,
                    QLineF(QPointF(), axis_x).length(),
                )
                axis_y = QPointF(
                    -axis_x.y() * axis_y_length / axis_x_length,
                    axis_x.x() * axis_y_length / axis_x_length,
                )
            # A unit radial gradient transformed by the two authored handle
            # vectors reproduces Figma's rotated, non-uniform radial basis.
            gradient = QRadialGradient(QPointF(0.0, 0.0), 1.0)
        else:
            gradient = QLinearGradient(start_point, end_point)
        for stop in gradient_spec.get("stops", []):
            if not isinstance(stop, Mapping):
                continue
            gradient.setColorAt(
                max(0.0, min(1.0, _finite_number(stop.get("position"), 0.0))),
                _rgba_color(stop.get("color")),
            )
        brush = QBrush(gradient)
        if str(gradient_spec.get("type") or "linear") == "radial":
            brush.setTransform(
                QTransform(
                    axis_x.x(),
                    axis_x.y(),
                    axis_y.x(),
                    axis_y.y(),
                    start_point.x(),
                    start_point.y(),
                )
            )
        return brush

    def _draw_drop_shadows(
        self,
        painter: QPainter,
        rect: QRectF,
        radii: tuple[float, float, float, float],
        smoothing: float,
    ) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for effect in self._effects("drop_shadow"):
            color = _rgba_color(effect.get("color"), "#00000066")
            if color.alpha() <= 0:
                continue
            offset_x = _finite_number(effect.get("x"), 0.0)
            offset_y = _finite_number(effect.get("y"), 0.0)
            blur = max(0.0, _finite_number(effect.get("blur"), 0.0))
            spread = _finite_number(effect.get("spread"), 0.0)
            base = rect.translated(offset_x, offset_y).adjusted(
                -spread,
                -spread,
                spread,
                spread,
            )
            bands = max(1, min(10, int(math.ceil(blur / 2.5))))
            for index in range(bands, -1, -1):
                amount = blur * index / max(1, bands)
                band_color = QColor(color)
                fade = (1.0 - index / (bands + 1.0)) ** 2
                band_color.setAlpha(max(1, int(round(color.alpha() * fade))))
                expanded = base.adjusted(-amount, -amount, amount, amount)
                expanded_radii = tuple(
                    max(0.0, value + spread + amount) for value in radii
                )
                painter.setBrush(band_color)
                painter.drawPath(
                    _rounded_card_path(expanded, expanded_radii, smoothing)
                )
        painter.restore()

    def _draw_inner_shadows(
        self,
        painter: QPainter,
        rect: QRectF,
        radii: tuple[float, float, float, float],
        clip_path: QPainterPath,
        smoothing: float,
    ) -> None:
        painter.save()
        painter.setClipPath(clip_path)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for effect in self._effects("inner_shadow"):
            color = _rgba_color(effect.get("color"), "#00000066")
            if color.alpha() <= 0:
                continue
            offset_x = _finite_number(effect.get("x"), 0.0)
            offset_y = _finite_number(effect.get("y"), 0.0)
            blur = max(0.0, _finite_number(effect.get("blur"), 0.0))
            spread = _finite_number(effect.get("spread"), 0.0)
            shifted = rect.translated(offset_x, offset_y).adjusted(
                spread,
                spread,
                -spread,
                -spread,
            )
            shifted_radii = tuple(max(0.0, value - spread) for value in radii)
            bands = max(1, min(10, int(math.ceil(blur / 2.5))))
            for index in range(bands, -1, -1):
                amount = max(1.0, blur * (index + 1) / max(1, bands))
                band_color = QColor(color)
                fade = (1.0 - index / (bands + 1.0)) ** 2
                band_color.setAlpha(max(1, int(round(color.alpha() * fade))))
                painter.setPen(QPen(band_color, amount * 2.0))
                painter.drawPath(
                    _rounded_card_path(shifted, shifted_radii, smoothing)
                )
        painter.restore()

    def _stroke_values(self) -> tuple[QColor, float, str]:
        color = _rgba_color(self.preview_style.get("stroke"), "#00000000")
        width = max(0.0, _finite_number(self.preview_style.get("stroke_width")))
        alignment = str(
            self.preview_style.get("stroke_align") or "center"
        ).strip().casefold()
        strokes = self.preview_style.get("strokes")
        if isinstance(strokes, list):
            paint = next(
                (
                    dict(row)
                    for row in strokes
                    if isinstance(row, Mapping)
                    and bool(row.get("visible", True))
                ),
                {},
            )
            if paint:
                color = _rgba_color(paint.get("color"), "#00000000")
                width = max(0.0, _finite_number(paint.get("width"), width))
                alignment = str(
                    paint.get("align") or alignment
                ).strip().casefold()
        if alignment not in {"inside", "center", "outside"}:
            alignment = "center"
        return color, width, alignment

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        canvas = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        painter.fillRect(canvas, QColor("#151A21"))
        rect = self._card_rect()
        radii = _rounded_card_radii(self.preview_style, rect)
        smoothing = self._corner_smoothing()
        body_path = _rounded_card_path(rect, radii, smoothing)
        self._draw_drop_shadows(painter, rect, radii, smoothing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._fill_brush(rect))
        painter.drawPath(body_path)

        stroke_color, stroke_width, stroke_align = self._stroke_values()
        if stroke_color.alpha() > 0 and stroke_width > 0.0:
            adjustment = (
                stroke_width / 2.0
                if stroke_align == "inside"
                else -stroke_width / 2.0
                if stroke_align == "outside"
                else 0.0
            )
            stroke_rect = rect.adjusted(
                adjustment,
                adjustment,
                -adjustment,
                -adjustment,
            )
            stroke_radii = tuple(
                max(0.0, value - adjustment) for value in radii
            )
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(stroke_color, stroke_width))
            painter.drawPath(
                _rounded_card_path(stroke_rect, stroke_radii, smoothing)
            )
        self._draw_inner_shadows(
            painter,
            rect,
            radii,
            body_path,
            smoothing,
        )


class PainterUMGMaterialEditorPanel(QWidget):
    """Embeddable inspector for one deterministic UMG material graph."""

    close_requested = Signal()

    def __init__(
        self,
        material: Mapping[str, Any],
        parent: QWidget | None = None,
        *,
        close_text: str = "Hide graph",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUMGMaterialEditorPanel")
        self.setMinimumHeight(176)
        self._initial_graph_fit_pending = True
        self._explicit_graph_view_state = False

        self._graph_spec = umg_material_graph(material)
        self._material_spec = copy.deepcopy(self._graph_spec["material"])
        self._preview_style = umg_material_preview_style(self._material_spec)
        self._hlsl = material_custom_hlsl(self._material_spec)
        self._validation_errors = validate_umg_material_record(
            self._material_spec,
            layer_kind="Image",
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("UMG Material Generator", self)
        title.setObjectName("PainterUMGMaterialTitle")
        status_text = (
            "Validated"
            if not self._validation_errors
            else f"Invalid - {', '.join(self._validation_errors)}"
        )
        self.status_label = QLabel(status_text, self)
        self.status_label.setObjectName("PainterUMGMaterialStatus")
        fit_button = QPushButton("Fit graph", self)
        fit_button.setObjectName("PainterUMGMaterialButton")
        self.close_button = QPushButton(str(close_text), self)
        self.close_button.setObjectName("PainterUMGMaterialButton")
        header.addWidget(title)
        header.addWidget(self.status_label, 1)
        header.addWidget(fit_button)
        header.addWidget(self.close_button)
        root.addLayout(header)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.setObjectName("PainterUMGMaterialSplitter")
        self.scene = _MaterialGraphScene(self._graph_spec, self.splitter)
        self.graph_view = _MaterialGraphView(self.scene, self.splitter)
        self.graph_view.setMinimumSize(0, 0)
        self.splitter.addWidget(self.graph_view)

        self.inspector_tabs = QTabWidget(self.splitter)
        self.inspector_tabs.setObjectName("PainterUMGMaterialInspectorTabs")
        self.inspector_tabs.setMinimumSize(220, 100)

        preview_tab = QWidget(self.inspector_tabs)
        preview_tab.setObjectName("PainterUMGMaterialPreviewTab")
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(0)
        self.preview = _MaterialPreview(self._preview_style, preview_tab)
        preview_layout.addWidget(self.preview)
        self.inspector_tabs.addTab(preview_tab, "Preview")

        hlsl_tab = QWidget(self.inspector_tabs)
        hlsl_tab.setObjectName("PainterUMGMaterialHLSLTab")
        hlsl_layout = QVBoxLayout(hlsl_tab)
        hlsl_layout.setContentsMargins(8, 8, 8, 8)
        hlsl_layout.setSpacing(5)
        code_title = QLabel(
            "Generated Custom HLSL - read only",
            hlsl_tab,
        )
        code_title.setObjectName("PainterUMGMaterialSectionTitle")
        self.hlsl_edit = QPlainTextEdit(hlsl_tab)
        self.hlsl_edit.setObjectName("PainterUMGMaterialHLSL")
        self.hlsl_edit.setReadOnly(True)
        self.hlsl_edit.setMinimumSize(0, 0)
        self.hlsl_edit.setPlainText(self._hlsl)
        hlsl_layout.addWidget(code_title)
        hlsl_layout.addWidget(self.hlsl_edit, 1)
        self.inspector_tabs.addTab(hlsl_tab, "HLSL")

        self.splitter.addWidget(self.inspector_tabs)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 7)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([760, 340])
        root.addWidget(self.splitter, 1)

        fit_button.clicked.connect(
            lambda _checked=False: self.graph_view.fit_graph(force=True)
        )
        self.setStyleSheet(
            """
            QWidget#PainterUMGMaterialEditorPanel {
                background: #10151D;
                color: #E7EDF5;
                border: 1px solid #2A3748;
                border-radius: 6px;
            }
            QLabel#PainterUMGMaterialTitle {
                color: #F3F7FC;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#PainterUMGMaterialStatus {
                color: #79C99E;
                padding-left: 8px;
            }
            QLabel#PainterUMGMaterialSectionTitle {
                color: #C7D2E0;
                font-size: 11px;
                font-weight: 650;
            }
            QTabWidget#PainterUMGMaterialInspectorTabs::pane {
                background: #151C25;
                border: 1px solid #2A3748;
                border-radius: 6px;
            }
            QTabWidget#PainterUMGMaterialInspectorTabs QTabBar::tab {
                color: #91A0B4;
                background: #121923;
                border: 1px solid #2A3748;
                padding: 4px 12px;
            }
            QTabWidget#PainterUMGMaterialInspectorTabs QTabBar::tab:selected {
                color: #FFFFFF;
                background: #245D8E;
                border-color: #35A5FF;
            }
            QPlainTextEdit#PainterUMGMaterialHLSL {
                color: #C9D7E7;
                background: #0C1118;
                border: 1px solid #2E3B4D;
                border-radius: 5px;
                padding: 7px;
                font-family: Consolas, monospace;
                font-size: 10px;
            }
            QPushButton#PainterUMGMaterialButton {
                color: #DCE7F4;
                background: #1B2633;
                border: 1px solid #34475D;
                border-radius: 5px;
                padding: 5px 10px;
            }
            QPushButton#PainterUMGMaterialButton:hover {
                background: #243448;
                border-color: #59789E;
            }
            QSplitter#PainterUMGMaterialSplitter::handle {
                background: #263344;
                width: 3px;
            }
            """
        )

        self.close_button.clicked.connect(self.close_requested.emit)

    def material_spec(self) -> dict[str, Any]:
        """Return a defensive copy of the normalized provider-neutral record."""
        return copy.deepcopy(self._material_spec)

    def graph_spec(self) -> dict[str, Any]:
        return copy.deepcopy(self._graph_spec)

    def preview_style(self) -> dict[str, Any]:
        return copy.deepcopy(self._preview_style)

    def validation_errors(self) -> list[str]:
        return list(self._validation_errors)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(520, 176)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(900, 300)

    def view_state(self) -> dict[str, Any]:
        return {
            "graph": self.graph_view.view_state(),
            "splitter_sizes": [int(value) for value in self.splitter.sizes()],
            "inspector_tab": int(self.inspector_tabs.currentIndex()),
        }

    def set_view_state(self, value: Mapping[str, Any] | None) -> None:
        state = value if isinstance(value, Mapping) else {}
        sizes = state.get("splitter_sizes")
        if (
            isinstance(sizes, (list, tuple))
            and len(sizes) == 2
            and all(float(value) > 0.0 for value in sizes)
        ):
            self.splitter.setSizes([int(float(value)) for value in sizes])
        tab = max(
            0,
            min(
                self.inspector_tabs.count() - 1,
                int(state.get("inspector_tab") or 0),
            ),
        )
        self.inspector_tabs.setCurrentIndex(tab)
        graph_state = state.get("graph")
        if isinstance(graph_state, Mapping):
            self._explicit_graph_view_state = True
            QTimer.singleShot(
                0,
                lambda: self.graph_view.set_view_state(graph_state),
            )

    def _fit_initial_graph(self) -> None:
        if not self._initial_graph_fit_pending:
            return
        self._initial_graph_fit_pending = False
        if not self._explicit_graph_view_state:
            self.graph_view.fit_graph()

    def showEvent(self, event: QEvent) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if self._initial_graph_fit_pending:
            QTimer.singleShot(0, self._fit_initial_graph)


class PainterUMGMaterialEditorDialog(QDialog):
    """Compatibility wrapper for callers that still request a dialog."""

    def __init__(
        self,
        material: Mapping[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUMGMaterialEditorDialog")
        self.setWindowTitle("UMG Material Generator")
        self.setModal(False)
        self.resize(1120, 680)
        self.setMinimumSize(780, 480)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.panel = PainterUMGMaterialEditorPanel(
            material,
            self,
            close_text="Close",
        )
        root.addWidget(self.panel)
        self.panel.close_requested.connect(self.close)

        # Preserve the original inspection surface for compatibility tests and
        # external callers while the UMG widget view embeds ``panel`` directly.
        self.scene = self.panel.scene
        self.graph_view = self.panel.graph_view
        self.preview = self.panel.preview
        self.hlsl_edit = self.panel.hlsl_edit
        self.status_label = self.panel.status_label

    def material_spec(self) -> dict[str, Any]:
        return self.panel.material_spec()

    def graph_spec(self) -> dict[str, Any]:
        return self.panel.graph_spec()

    def preview_style(self) -> dict[str, Any]:
        return self.panel.preview_style()

    def validation_errors(self) -> list[str]:
        return self.panel.validation_errors()


__all__ = [
    "PainterUMGMaterialEditorDialog",
    "PainterUMGMaterialEditorPanel",
]
