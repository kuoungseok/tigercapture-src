"""NodeGraphView — QGraphicsView with grid background + zoom + pan.

Phase 2A scope:

- Two-tier grid (10 px minor, 50 px major) painted in
  ``drawBackground`` so the scene's items can stay agnostic.
- Mouse-wheel zoom anchored at the cursor (clamped 0.1×–5.0×).
- Pan with middle-click drag OR Alt+left-drag (the second binding
  matches Houdini / Substance / Touchdesigner ergonomics — Alt is
  the universal "navigate, don't manipulate" modifier).
- Scrollbars hidden — scene is huge, scrollbars distract from the
  visual flow. Phase 2E will add a minimap that surfaces the
  off-screen indicator instead.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsView, QMenu

from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)


class NodeGraphView(QGraphicsView):

    zoom_changed = Signal(float)

    def __init__(self, scene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        # Zoom anchors at the cursor — feels like a magnifying glass.
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse,
        )
        self.setResizeAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse,
        )
        self.setBackgroundBrush(QColor(C["canvas_bg"]))
        # Hide scrollbars — pan via middle / Alt+drag, see header docstring.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)

        self._zoom: float = 1.0
        self._panning: bool = False
        self._pan_start: QPointF = QPointF()

    # ---- background ----

    def drawBackground(self, painter: QPainter, rect) -> None:
        super().drawBackground(painter, rect)

        # Minor grid — painted FIRST so the major grid overprints it.
        pen_minor = QPen(QColor(C["grid_minor"]), 1)
        painter.setPen(pen_minor)
        spacing = S["grid_minor_spacing"]
        left = int(rect.left()) - (int(rect.left()) % spacing)
        top = int(rect.top()) - (int(rect.top()) % spacing)
        x = left
        while x < int(rect.right()) + spacing:
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += spacing
        y = top
        while y < int(rect.bottom()) + spacing:
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += spacing

        # Major grid — slightly brighter, every 50 px.
        pen_major = QPen(QColor(C["grid_major"]), 1)
        painter.setPen(pen_major)
        spacing = S["grid_major_spacing"]
        left = int(rect.left()) - (int(rect.left()) % spacing)
        top = int(rect.top()) - (int(rect.top()) % spacing)
        x = left
        while x < int(rect.right()) + spacing:
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += spacing
        y = top
        while y < int(rect.bottom()) + spacing:
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += spacing

    # ---- zoom ----

    def wheelEvent(self, event) -> None:
        step = S["zoom_step"]
        factor = step if event.angleDelta().y() > 0 else 1.0 / step
        new_zoom = self._zoom * factor
        if new_zoom < S["min_zoom"] or new_zoom > S["max_zoom"]:
            return
        self.scale(factor, factor)
        self._zoom = new_zoom
        self.zoom_changed.emit(self._zoom)

    # ---- pan ----

    def mousePressEvent(self, event) -> None:
        # Right-click → context menu for connections or ports
        if event.button() == Qt.MouseButton.RightButton:
            self._show_item_context_menu(event)
            return

        # Middle-click → pan. Alt+left → also pan (lets users on
        # laptops without a middle mouse button still navigate).
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton
            and (event.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        # Left-click on EMPTY canvas → pan (matches viewer-tool
        # convention; users were getting a rubber-band selection
        # instead and the view appeared to "jump away" from the
        # node area). Rubber-band selection is now Shift+left.
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        ):
            scene_pos = self.mapToScene(event.position().toPoint())
            from app.workbench.node_graph.items.connection_item import ConnectionItem
            from app.workbench.node_graph.items.io_node import IONodeItem
            from app.workbench.node_graph.items.node_item import NodeItem
            from app.workbench.node_graph.items.port_item import PortItem
            scene = self.scene()
            hit = False
            if scene is not None:
                for it in scene.items(scene_pos):
                    if isinstance(it, (NodeItem, IONodeItem, PortItem, ConnectionItem)):
                        hit = True
                        break
            if not hit:
                self._panning = True
                self._pan_start = event.position()
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                # Clear selection so empty-pan also acts as
                # "deselect everything" (matches DaVinci/Premiere).
                if scene is not None:
                    scene.clearSelection()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            # Grab-and-drag pan via scrollbar values — the scene
            # point under the cursor stays under the cursor (matches
            # Blender / Houdini / Substance / Unreal / Photoshop /
            # DaVinci convention). Decrementing the scrollbar by the
            # mouse delta moves the visible window LEFT, which makes
            # the scene appear to move RIGHT with the cursor.
            #
            # Why scrollbars instead of ``view.translate``:
            # ``translate`` shifts the view's transform but with
            # hidden scrollbars Qt sometimes clamps / fights back
            # against the change. Scrollbar values are the canonical
            # scroll offset and work cleanly even when the bars
            # themselves aren't shown.
            hsb = self.horizontalScrollBar()
            vsb = self.verticalScrollBar()
            hsb.setValue(hsb.value() - int(round(delta.x())))
            vsb.setValue(vsb.value() - int(round(delta.y())))
            return
        super().mouseMoveEvent(event)
        # Phase 2B: forward mid-drag connection updates to the scene
        # so the temporary preview line tracks the cursor.
        scene = self.scene()
        if scene is not None and getattr(scene, "_dragging_connection", None):
            scene_pos = self.mapToScene(event.position().toPoint())
            scene.update_connection_drag(scene_pos)

    def mouseReleaseEvent(self, event) -> None:
        if self._panning and event.button() in (
            Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton,
        ):
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        # Phase 2B: end an in-flight connection drag, picking the
        # target port at the release position (or None to cancel).
        scene = self.scene()
        if (
            event.button() == Qt.MouseButton.LeftButton
            and scene is not None
            and getattr(scene, "_dragging_connection", None)
        ):
            from app.workbench.node_graph.items.port_item import PortItem
            scene_pos = self.mapToScene(event.position().toPoint())
            target_port = None
            for it in scene.items(scene_pos):
                if isinstance(it, PortItem):
                    target_port = it
                    break
            scene.end_connection_drag(target_port)
            return
        super().mouseReleaseEvent(event)

    # ---- context menu ----

    def _show_item_context_menu(self, event) -> None:
        """Right-click: show disconnect menu for connections / ports."""
        from app.workbench.node_graph.items.connection_item import ConnectionItem
        from app.workbench.node_graph.items.port_item import PortItem

        scene = self.scene()
        if scene is None:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        global_pos = event.globalPosition().toPoint()

        # Find topmost connection or port under cursor
        for item in scene.items(scene_pos):
            if isinstance(item, ConnectionItem) and item.target is not None:
                menu = QMenu(self)
                act = menu.addAction("✂ 연결 해제")
                chosen = menu.exec(global_pos)
                if chosen is act:
                    scene.remove_connection(item)
                    try:
                        scene.graph_mutated.emit()
                    except Exception:
                        pass
                return
            if isinstance(item, PortItem) and item.connections:
                menu = QMenu(self)
                n = len(item.connections)
                label = f"✂ 연결 해제 ({n}개)" if n > 1 else "✂ 연결 해제"
                act = menu.addAction(label)
                chosen = menu.exec(global_pos)
                if chosen is act:
                    for conn in list(item.connections):
                        scene.remove_connection(conn)
                    try:
                        scene.graph_mutated.emit()
                    except Exception:
                        pass
                return

    # ---- keyboard ----

    def keyPressEvent(self, event) -> None:
        """Delete / Backspace — remove selected connections or nodes."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            scene = self.scene()
            if scene is not None and hasattr(scene, "delete_selected"):
                scene.delete_selected()
            return
        super().keyPressEvent(event)

    # ---- public ----

    def zoom_level(self) -> float:
        return self._zoom

    def reset_zoom(self) -> None:
        # Reset to 1.0 around the current viewport centre.
        factor = 1.0 / self._zoom
        self.scale(factor, factor)
        self._zoom = 1.0
        self.zoom_changed.emit(self._zoom)
