"""Unreal-style node editor widget for material and texture graphs.

Nodes carry a category-tinted title bar and a readable title, every pin shows
its own name next to a dot coloured by value type, and wires inherit the source
pin's colour - the vocabulary an Unreal node editor uses, reimplemented here.
The widget owns no material semantics: it edits a
``app.material_graph.document`` graph and reports every change.
"""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QMenu,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.material_graph import document as graph_document
from app.material_graph.registry import (
    category_title_color,
    node_definition,
    node_types_for_surface,
    pin_color,
    pins_are_compatible,
)


COLORS = {
    "canvas_bg": "#12131A",
    "grid_minor": "#191B23",
    "grid_major": "#232634",
    "node_bg": "#22242C",
    "node_bg_selected": "#2A2D37",
    "node_border": "#0C0D11",
    "node_border_selected": "#F5A623",
    "node_title_text": "#F2F4F8",
    "pin_label": "#C3C8D2",
    "node_shadow": "#00000066",
    "wire_pending": "#E8EAEE",
    "comment_text": "#8D94A2",
}

SIZES = {
    "node_width": 176,
    "title_height": 24,
    "pin_row_height": 20,
    "pin_radius": 4.5,
    "body_padding": 8,
    "corner_radius": 6,
    "grid_minor": 16,
    "grid_major": 128,
    "min_zoom": 0.2,
    "max_zoom": 3.0,
    "zoom_step": 1.15,
}


def _font(size: int, *, bold: bool = False) -> QFont:
    font = QFont()
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def node_layout(node: Mapping[str, Any]) -> dict[str, Any]:
    """Body size and pin offsets for a node, in scene units.

    Split out of the item so tests can assert the geometry without a view, and
    so hit-testing and painting cannot drift apart.
    """
    definition = node_definition(str(node.get("type") or "")) or {
        "inputs": [],
        "outputs": [],
        "title": "",
        "category": "utility",
    }
    inputs = list(definition["inputs"])
    outputs = list(definition["outputs"])
    rows = max(len(inputs), len(outputs))
    title_height = SIZES["title_height"]
    row_height = SIZES["pin_row_height"]
    padding = SIZES["body_padding"]
    height = title_height + padding + max(1, rows) * row_height + padding
    metrics = QFontMetricsF(_font(11, bold=True))
    title = str(node.get("title") or definition["title"])
    width = max(
        SIZES["node_width"],
        int(metrics.horizontalAdvance(title)) + 2 * padding + 18,
    )
    pins: list[dict[str, Any]] = []
    for index, pin in enumerate(inputs):
        pins.append(
            {
                "name": str(pin["name"]),
                "type": str(pin["type"]),
                "is_input": True,
                "pos": QPointF(0.0, title_height + padding + row_height * (index + 0.5)),
            }
        )
    for index, pin in enumerate(outputs):
        pins.append(
            {
                "name": str(pin["name"]),
                "type": str(pin["type"]),
                "is_input": False,
                "pos": QPointF(
                    float(width),
                    title_height + padding + row_height * (index + 0.5),
                ),
            }
        )
    return {
        "width": float(width),
        "height": float(height),
        "title": title,
        "category": str(definition["category"]),
        "pins": pins,
    }


class _NodeItem(QGraphicsItem):
    """One graph node: title bar, body, named pins."""

    def __init__(self, node: Mapping[str, Any]) -> None:
        super().__init__()
        self.node_id = str(node["id"])
        self.node = dict(node)
        self.layout = node_layout(node)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges,
            True,
        )
        self.setAcceptHoverEvents(True)
        self.setZValue(10.0)
        position = node.get("position") or [0.0, 0.0]
        self.setPos(float(position[0]), float(position[1]))

    def boundingRect(self) -> QRectF:
        radius = SIZES["pin_radius"] + 3.0
        return QRectF(
            -radius,
            -radius,
            self.layout["width"] + 2 * radius,
            self.layout["height"] + 2 * radius,
        )

    def body_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, self.layout["width"], self.layout["height"])

    def pin_at(self, point: QPointF) -> dict[str, Any] | None:
        reach = SIZES["pin_radius"] + 5.0
        for pin in self.layout["pins"]:
            if (point - pin["pos"]).manhattanLength() <= reach * 2:
                delta = point - pin["pos"]
                if delta.x() * delta.x() + delta.y() * delta.y() <= reach * reach:
                    return pin
        return None

    def pin_scene_pos(self, pin_name: str, *, is_input: bool) -> QPointF | None:
        for pin in self.layout["pins"]:
            if pin["name"] == pin_name and pin["is_input"] == is_input:
                return self.mapToScene(pin["pos"])
        return None

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.body_rect()
        radius = SIZES["corner_radius"]
        selected = self.isSelected()

        shadow = QPainterPath()
        shadow.addRoundedRect(rect.translated(0.0, 2.0), radius, radius)
        painter.fillPath(shadow, QColor(COLORS["node_shadow"]))

        body = QPainterPath()
        body.addRoundedRect(rect, radius, radius)
        painter.fillPath(
            body,
            QColor(COLORS["node_bg_selected"] if selected else COLORS["node_bg"]),
        )

        title_rect = QRectF(rect.left(), rect.top(), rect.width(), SIZES["title_height"])
        title_path = QPainterPath()
        title_path.addRoundedRect(title_rect, radius, radius)
        square = QPainterPath()
        square.addRect(
            QRectF(
                title_rect.left(),
                title_rect.bottom() - radius,
                title_rect.width(),
                radius,
            )
        )
        painter.fillPath(
            title_path.united(square),
            QColor(category_title_color(self.layout["category"])),
        )

        painter.setPen(
            QPen(
                QColor(
                    COLORS["node_border_selected"]
                    if selected
                    else COLORS["node_border"]
                ),
                2.0 if selected else 1.0,
            )
        )
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(body)

        painter.setPen(QColor(COLORS["node_title_text"]))
        painter.setFont(_font(11, bold=True))
        painter.drawText(
            title_rect.adjusted(SIZES["body_padding"], 0.0, -SIZES["body_padding"], 0.0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.layout["title"],
        )

        painter.setFont(_font(10))
        for pin in self.layout["pins"]:
            color = QColor(pin_color(pin["type"]))
            painter.setPen(QPen(color.darker(160), 1.0))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(pin["pos"], SIZES["pin_radius"], SIZES["pin_radius"])
            painter.setPen(QColor(COLORS["pin_label"]))
            label_rect = QRectF(
                rect.left() + SIZES["body_padding"] + 4.0,
                pin["pos"].y() - SIZES["pin_row_height"] * 0.5,
                rect.width() - 2 * (SIZES["body_padding"] + 4.0),
                SIZES["pin_row_height"],
            )
            alignment = (
                Qt.AlignmentFlag.AlignLeft
                if pin["is_input"]
                else Qt.AlignmentFlag.AlignRight
            )
            painter.drawText(
                label_rect,
                int(alignment | Qt.AlignmentFlag.AlignVCenter),
                pin["name"],
            )


class _LinkItem(QGraphicsItem):
    """A wire, drawn as a horizontal-tangent cubic in the source pin colour."""

    def __init__(self, color: str) -> None:
        super().__init__()
        self.color = QColor(color)
        self.start = QPointF()
        self.end = QPointF()
        self.setZValue(5.0)

    def set_endpoints(self, start: QPointF, end: QPointF) -> None:
        self.prepareGeometryChange()
        self.start = QPointF(start)
        self.end = QPointF(end)
        self.update()

    def path(self) -> QPainterPath:
        path = QPainterPath(self.start)
        span = max(40.0, abs(self.end.x() - self.start.x()) * 0.5)
        path.cubicTo(
            QPointF(self.start.x() + span, self.start.y()),
            QPointF(self.end.x() - span, self.end.y()),
            self.end,
        )
        return path

    def boundingRect(self) -> QRectF:
        return self.path().boundingRect().adjusted(-6.0, -6.0, 6.0, 6.0)

    def paint(self, painter: QPainter, _option, _widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.color.darker(180), 3.4))
        painter.drawPath(self.path())
        painter.setPen(QPen(self.color, 1.8))
        painter.drawPath(self.path())
        # Direction marker at the midpoint, so a wire reads even when both ends
        # are off screen.
        middle = self.path().pointAtPercent(0.5)
        angle = self.path().angleAtPercent(0.5)
        painter.save()
        painter.translate(middle)
        painter.rotate(-angle)
        painter.setBrush(QBrush(self.color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(
            QPolygonF(
                [QPointF(-3.0, -3.2), QPointF(3.6, 0.0), QPointF(-3.0, 3.2)]
            )
        )
        painter.restore()


class _GraphScene(QGraphicsScene):
    def __init__(self) -> None:
        super().__init__()
        self.setBackgroundBrush(QColor(COLORS["canvas_bg"]))

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        for spacing, key, width in (
            (SIZES["grid_minor"], "grid_minor", 1.0),
            (SIZES["grid_major"], "grid_major", 1.0),
        ):
            painter.setPen(QPen(QColor(COLORS[key]), width))
            left = int(rect.left()) - (int(rect.left()) % spacing)
            top = int(rect.top()) - (int(rect.top()) % spacing)
            x = float(left)
            while x < rect.right():
                painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
                x += spacing
            y = float(top)
            while y < rect.bottom():
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
                y += spacing


class _GraphView(QGraphicsView):
    def __init__(self, owner: "MaterialGraphView") -> None:
        super().__init__(owner)
        self._owner = owner
        self.setScene(_GraphScene())
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._panning = False
        self._pan_origin = QPointF()
        self._pending_link: _LinkItem | None = None
        self._pending_source: tuple[str, str, str] | None = None
        self._drag_started: dict[str, tuple[float, float]] = {}

    # -- input ---------------------------------------------------------

    def wheelEvent(self, event) -> None:
        step = SIZES["zoom_step"]
        factor = step if event.angleDelta().y() > 0 else 1.0 / step
        scale = self.transform().m11() * factor
        if scale < SIZES["min_zoom"] or scale > SIZES["max_zoom"]:
            return
        self.scale(factor, factor)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self._panning = True
            self._pan_origin = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            node, pin = self._pin_under(event.position())
            if node is not None and pin is not None:
                self._begin_link(node, pin)
                event.accept()
                return
            self._drag_started = {
                item.node_id: (item.pos().x(), item.pos().y())
                for item in self.scene().items()
                if isinstance(item, _NodeItem)
            }
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            delta = event.position() - self._pan_origin
            self._pan_origin = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        if self._pending_link is not None:
            self._pending_link.set_endpoints(
                self._pending_link.start,
                self.mapToScene(event.position().toPoint()),
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        if self._pending_link is not None:
            self._finish_link(event.position())
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._commit_moves()
        self._owner._push_selection(
            [
                item.node_id
                for item in self.scene().selectedItems()
                if isinstance(item, _NodeItem)
            ]
        )

    def mouseDoubleClickEvent(self, event) -> None:
        node, _pin = self._pin_under(event.position())
        if node is None:
            self._owner.show_palette(self.mapToScene(event.position().toPoint()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self._owner.delete_selected()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F:
            self.fit_graph()
            event.accept()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        node, pin = self._pin_under(event.pos())
        if node is not None and pin is not None and pin["is_input"]:
            menu = QMenu(self)
            action = QAction("Break this link", menu)
            action.triggered.connect(
                lambda: self._owner.disconnect_pin(node.node_id, pin["name"])
            )
            menu.addAction(action)
            menu.exec(event.globalPos())
            return
        self._owner.show_palette(self.mapToScene(event.pos()))

    # -- helpers -------------------------------------------------------

    def _pin_under(self, position) -> tuple[_NodeItem | None, dict[str, Any] | None]:
        scene_point = self.mapToScene(
            position.toPoint() if hasattr(position, "toPoint") else position
        )
        for item in self.scene().items(scene_point):
            if isinstance(item, _NodeItem):
                pin = item.pin_at(item.mapFromScene(scene_point))
                return item, pin
        # Pins stick out past the body, so also look nearby.
        for item in self.scene().items():
            if not isinstance(item, _NodeItem):
                continue
            pin = item.pin_at(item.mapFromScene(scene_point))
            if pin is not None:
                return item, pin
        return None, None

    def _begin_link(self, node: _NodeItem, pin: Mapping[str, Any]) -> None:
        if pin["is_input"]:
            # Dragging off a connected input picks the wire up, the way an
            # Unreal editor lets you re-target an existing connection.
            self._owner.disconnect_pin(node.node_id, pin["name"])
            return
        link = _LinkItem(pin_color(pin["type"]))
        start = node.mapToScene(pin["pos"])
        link.set_endpoints(start, start)
        link.setZValue(50.0)
        self.scene().addItem(link)
        self._pending_link = link
        self._pending_source = (node.node_id, pin["name"], pin["type"])

    def _finish_link(self, position) -> None:
        link = self._pending_link
        source = self._pending_source
        self._pending_link = None
        self._pending_source = None
        if link is not None:
            self.scene().removeItem(link)
        if source is None:
            return
        node, pin = self._pin_under(position)
        if node is None or pin is None or not pin["is_input"]:
            self._owner.report("Drop a wire on an input pin to connect it.")
            return
        if not pins_are_compatible(source[2], pin["type"]):
            self._owner.report(
                f"{source[2]} does not fit a {pin['type']} pin."
            )
            return
        self._owner.connect_pins(source[0], source[1], node.node_id, pin["name"])

    def _commit_moves(self) -> None:
        if not self._drag_started:
            return
        moved: list[tuple[str, tuple[float, float]]] = []
        for item in self.scene().items():
            if not isinstance(item, _NodeItem):
                continue
            before = self._drag_started.get(item.node_id)
            now = (item.pos().x(), item.pos().y())
            if before is None or before == now:
                continue
            moved.append((item.node_id, now))
        self._drag_started = {}
        if moved:
            self._owner.commit_moves(moved)

    def fit_graph(self) -> None:
        rect = self.scene().itemsBoundingRect()
        if rect.isEmpty():
            return
        self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)
        scale = self.transform().m11()
        if scale > SIZES["max_zoom"]:
            self.scale(SIZES["max_zoom"] / scale, SIZES["max_zoom"] / scale)


class MaterialGraphView(QWidget):
    """Editable Unreal-style node graph.

    ``graph_changed`` carries the whole revised document, so the host can push
    the previous one onto its undo stack and re-evaluate in one place.
    """

    graph_changed = Signal(object)
    selection_changed = Signal(object)
    status_message = Signal(str)

    def __init__(self, surface: str = "ui", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._graph = graph_document.create_graph(surface)
        self._view = _GraphView(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        self._rebuild_scene()

    def sizeHint(self) -> QSize:
        return QSize(720, 420)

    # -- document ------------------------------------------------------

    def graph(self) -> dict[str, Any]:
        return graph_document.normalize_graph(self._graph)

    def set_graph(self, value: Mapping[str, Any] | None) -> None:
        self._graph = graph_document.normalize_graph(value)
        self._rebuild_scene()

    def surface(self) -> str:
        return str(self._graph["surface"])

    def report(self, message: str) -> None:
        self.status_message.emit(str(message))

    def _apply(self, revised: Mapping[str, Any]) -> None:
        self._graph = graph_document.normalize_graph(revised)
        self._rebuild_scene()
        self.graph_changed.emit(self.graph())

    def _push_selection(self, node_ids: list[str]) -> None:
        current = list(self._graph["selection"]["node_ids"])
        if current == list(node_ids):
            return
        self._graph = graph_document.set_selection(self._graph, node_ids)
        self.selection_changed.emit(list(node_ids))

    # -- edits ---------------------------------------------------------

    def add_node(self, node_type: str, position: QPointF) -> None:
        try:
            revised, row = graph_document.add_node(
                self._graph,
                node_type,
                position=(position.x(), position.y()),
            )
        except graph_document.MaterialGraphError as error:
            self.report(str(error))
            return
        self._apply(revised)
        self.report(f"Added {row['title']}.")

    def connect_pins(
        self,
        from_node: str,
        from_pin: str,
        to_node: str,
        to_pin: str,
    ) -> None:
        try:
            revised = graph_document.connect(
                self._graph,
                from_node,
                from_pin,
                to_node,
                to_pin,
            )
        except graph_document.MaterialGraphError as error:
            self.report(str(error))
            return
        self._apply(revised)

    def disconnect_pin(self, node_id: str, pin_name: str) -> None:
        revised = graph_document.disconnect(self._graph, node_id, pin_name)
        if revised == self.graph():
            return
        self._apply(revised)

    def delete_selected(self) -> None:
        selected = [
            item.node_id
            for item in self._view.scene().selectedItems()
            if isinstance(item, _NodeItem)
        ]
        if not selected:
            return
        revised = graph_document.remove_nodes(self._graph, selected)
        if revised == self.graph():
            self.report("The output node cannot be deleted.")
            return
        self._apply(revised)

    def commit_moves(self, moved: list[tuple[str, tuple[float, float]]]) -> None:
        revised = self._graph
        for node_id, position in moved:
            revised = graph_document.move_node(revised, node_id, position)
        self._apply(revised)

    def show_palette(self, position: QPointF) -> None:
        """Searchable node palette, grouped by category."""
        menu = QMenu(self)
        search = QLineEdit(menu)
        search.setPlaceholderText("Search nodes")
        holder = QWidgetAction(menu)
        holder.setDefaultWidget(search)
        menu.addAction(holder)
        menu.addSeparator()
        rows = node_types_for_surface(self.surface())
        actions: list[tuple[QAction, str]] = []
        current_category = ""
        for row in rows:
            if row["category"] != current_category:
                current_category = row["category"]
                menu.addSection(str(current_category).title())
            action = QAction(str(row["title"]), menu)
            action.setToolTip(str(row["summary"]))
            action.triggered.connect(
                lambda _checked=False, node_type=row["type"]: self.add_node(
                    node_type,
                    position,
                )
            )
            menu.addAction(action)
            actions.append((action, f"{row['title']} {row['type']}".casefold()))

        def filter_actions(text: str) -> None:
            needle = text.strip().casefold()
            for action, haystack in actions:
                action.setVisible(not needle or needle in haystack)

        search.textChanged.connect(filter_actions)
        search.setFocus()
        menu.exec(self._view.mapToGlobal(self._view.mapFromScene(position)))

    def fit(self) -> None:
        self._view.fit_graph()

    # -- scene ---------------------------------------------------------

    def _rebuild_scene(self) -> None:
        scene = self._view.scene()
        scene.clear()
        items: dict[str, _NodeItem] = {}
        selected = set(self._graph["selection"]["node_ids"])
        for node in self._graph["nodes"]:
            item = _NodeItem(node)
            scene.addItem(item)
            item.setSelected(node["id"] in selected)
            items[node["id"]] = item
        for link in self._graph["links"]:
            source = items.get(link["from_node"])
            target = items.get(link["to_node"])
            if source is None or target is None:
                continue
            start = source.pin_scene_pos(link["from_pin"], is_input=False)
            end = target.pin_scene_pos(link["to_pin"], is_input=True)
            if start is None or end is None:
                continue
            pin_type = "float"
            for pin in source.layout["pins"]:
                if pin["name"] == link["from_pin"] and not pin["is_input"]:
                    pin_type = pin["type"]
                    break
            wire = _LinkItem(pin_color(pin_type))
            wire.set_endpoints(start, end)
            scene.addItem(wire)
        bounds = scene.itemsBoundingRect().adjusted(-400, -400, 400, 400)
        scene.setSceneRect(bounds)
