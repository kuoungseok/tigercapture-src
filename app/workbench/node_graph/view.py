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

from app.icons import app_icon
from app.style import studio_chrome_qss
from app.workbench_scroll import forward_wheel_to_scroll_area
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
        minor = QColor(C["grid_minor"])
        minor.setAlpha(22)
        pen_minor = QPen(minor, 1)
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
        major = QColor(C["grid_major"])
        major.setAlpha(38)
        pen_major = QPen(major, 1)
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
        if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            if forward_wheel_to_scroll_area(self, event):
                return
            event.ignore()
            return
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
            # Blender / Houdini / Substance / Photoshop /
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
        """Right-click: context menu for connections, ports, nodes, or empty canvas."""
        from app.workbench.node_graph.items.connection_item import ConnectionItem
        from app.workbench.node_graph.items.port_item import PortItem
        from app.workbench.node_graph.items.node_item import NodeItem
        from app.workbench.node_graph.items.io_node import IONodeItem

        scene = self.scene()
        if scene is None:
            return
        scene_pos = self.mapToScene(event.position().toPoint())
        global_pos = event.globalPosition().toPoint()

        _menu_style = studio_chrome_qss("")

        # ── Connection / Port ─────────────────────────────────────────────
        for item in scene.items(scene_pos):
            if isinstance(item, ConnectionItem) and item.target is not None:
                menu = QMenu(self); menu.setStyleSheet(_menu_style)
                act = menu.addAction(app_icon("scissors", size=16), "연결 해제")
                if menu.exec(global_pos) == act:
                    scene.remove_connection(item)
                    scene.graph_mutated.emit()
                return
            if isinstance(item, PortItem) and item.connections:
                menu = QMenu(self); menu.setStyleSheet(_menu_style)
                n = len(item.connections)
                label = f"연결 해제 ({n}개)" if n > 1 else "연결 해제"
                act = menu.addAction(app_icon("scissors", size=16), label)
                if menu.exec(global_pos) == act:
                    for conn in list(item.connections):
                        scene.remove_connection(conn)
                    scene.graph_mutated.emit()
                return

        # ── Node item ─────────────────────────────────────────────────────
        for item in scene.items(scene_pos):
            if isinstance(item, NodeItem) and not isinstance(item, IONodeItem):
                menu = QMenu(self); menu.setStyleSheet(_menu_style)
                act_rename  = menu.addAction("✏️ 이름 변경 (F2)")
                act_bypass  = menu.addAction(
                    "✓ 바이패스 해제 (Ctrl+D)" if item.bypassed else "⊘ 바이패스 (Ctrl+D)")
                menu.addSeparator()
                act_delete  = menu.addAction(app_icon("trash", size=16), "삭제")
                chosen = menu.exec(global_pos)
                if chosen == act_rename:
                    from PySide6.QtWidgets import QInputDialog
                    new_label, ok = QInputDialog.getText(
                        self, "이름 변경", "노드 이름:", text=item.label)
                    if ok and new_label.strip():
                        item.label = new_label.strip()
                        item.update()
                elif chosen == act_bypass:
                    item.toggle_bypass()
                    scene.graph_mutated.emit()
                elif chosen == act_delete:
                    if hasattr(scene, "delete_selected"):
                        scene.clearSelection()
                        item.setSelected(True)
                        scene.delete_selected()
                return

        # ── Empty canvas → add node at cursor ────────────────────────────
        menu = QMenu(self); menu.setStyleSheet(_menu_style)
        menu.addAction("  ── 노드 추가 ──").setEnabled(False)
        menu.addSeparator()

        # Serial / Blur
        act_serial   = menu.addAction(app_icon("color", size=16), "시리얼 (색보정)")
        act_blur     = menu.addAction(app_icon("blur", size=16), "블러")
        menu.addSeparator()

        # Color correction
        color_menu = menu.addMenu(app_icon("color", size=16), "컬러")
        color_menu.setStyleSheet(_menu_style)
        act_curves = color_menu.addAction("커브")
        act_levels = color_menu.addAction("레벨")
        act_wb     = color_menu.addAction("화이트 밸런스")
        act_chmix  = color_menu.addAction("채널 믹서")
        act_lut    = color_menu.addAction("LUT")

        # Effects
        fx_menu = menu.addMenu(app_icon("effects", size=16), "이펙트")
        fx_menu.setStyleSheet(_menu_style)
        act_glow   = fx_menu.addAction("글로우")
        act_vign   = fx_menu.addAction("비네팅")
        act_grain  = fx_menu.addAction("필름 그레인")
        act_sharp  = fx_menu.addAction("선명도")
        act_pixel  = fx_menu.addAction("픽셀화")

        fx_menu.addSeparator()
        act_hdr = fx_menu.addAction("SDR -> HDR EXR")

        chosen = menu.exec(global_pos)
        if chosen is None:
            return

        _effect_map = {
            act_curves: "curves",   act_levels: "levels",
            act_wb:     "whitebalance", act_chmix: "channelmixer",
            act_lut:    "lut",      act_glow:  "glow",
            act_vign:   "vignette", act_grain: "filmgrain",
            act_sharp:  "unsharpmask", act_pixel: "pixelate",
            act_hdr: "sdr_hdr_upmap",
        }

        if chosen == act_serial:
            node = scene.add_serial_node(pos=scene_pos)
        elif chosen == act_blur:
            node = scene.add_blur_node(pos=scene_pos)
        elif chosen in _effect_map:
            node = scene.add_effect_node(_effect_map[chosen], pos=scene_pos)
        else:
            return

        scene.clearSelection()
        node.setSelected(True)
        scene.graph_mutated.emit()

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
