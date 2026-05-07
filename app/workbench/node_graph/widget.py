"""NodeGraphWidget — header + toolbar + canvas + status bar.

Phase 2A: visual shell + Serial node creation.
Phase 2C: Delete / F2 / Ctrl+D shortcuts. Right-click context menu
          (rename / bypass / delete on a node, add-anywhere on empty
          canvas).
Phase 2D: ``set_track`` loads / saves ``track.node_graph_view_data``
          so each video track keeps its own scene state.
Phase 2E: + Parallel button + diamond Mixer + minimap overlay +
          Ctrl+9 fit-to-view auto layout.
Phase 2F: tooltips on the toolbar, keyboard zoom (Ctrl + / Ctrl -),
          double-click-to-rename surfaced through the scene.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QAction, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.workbench.node_graph.items.connection_item import ConnectionItem
from app.workbench.node_graph.items.io_node import IONodeItem
from app.workbench.node_graph.items.node_item import NodeItem
from app.workbench.node_graph.scene import NodeGraphScene
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)
from app.workbench.node_graph.view import NodeGraphView


class _MiniMapView(QGraphicsView):
    """Compact overview of the whole scene — non-interactive, just a
    visual aid for orienting in a long node chain. Phase 2E ships
    a static viewport indicator (the rectangle shown is the main
    view's current visible area)."""

    def __init__(self, scene, main_view, parent=None) -> None:
        super().__init__(scene, parent)
        self._main_view = main_view
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setStyleSheet(
            "background-color: rgba(18, 18, 18, 0.85); "
            "border: 1px solid #2a2a2a; border-radius: 4px;"
        )
        self.setInteractive(False)
        # Keep the minimap's transform separate from the main view —
        # it should always show *everything* in scene coordinates.
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.NoAnchor,
        )

    def refresh(self) -> None:
        scene = self.scene()
        if scene is not None:
            br = scene.itemsBoundingRect()
            if not br.isEmpty():
                self.fitInView(br.adjusted(-40, -40, 40, 40),
                               Qt.AspectRatioMode.KeepAspectRatio)


class NodeGraphWidget(QWidget):

    popout_requested = Signal()
    node_selection_changed = Signal(str)
    # Phase 2D — emit when a NodeItem is selected so the editor can
    # route the Color panel to that node's color_grade. Empty string
    # means deselected.
    selected_node_id_changed = Signal(str)
    # DaVinci Phase B — emits the selected NodeItem itself (or None)
    # so the editor can bind the Color panel sliders to that node's
    # ``color_grade`` directly. Cheaper than ID-based lookup since
    # the panel mutates the grade in place.
    selected_node_changed = Signal(object)
    # Phase E — user picked a mask kind from a node's right-click
    # menu. The editor catches this and either opens the mask dialog
    # (HSL / Magic / Power Window editor) or attaches a one-shot
    # mask preset to the node.
    mask_request = Signal(object, str)   # (NodeItem, "kind:variant")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Phase 2D: tracked so save_to_track / load_from_track stay
        # bound to the right object.
        self._track = None
        self._suspend_persist: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(28)
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(2, 0, 2, 0)
        header_lay.setSpacing(6)
        self._title_label = QLabel(tr("workbench.node_graph.title"))
        self._title_label.setStyleSheet(
            "color: #8a8a8a; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.5px;"
        )
        header_lay.addWidget(self._title_label)
        header_lay.addStretch(1)
        self._popout_btn = QPushButton("⛶")
        self._popout_btn.setObjectName("PreviewPopoutIcon")
        self._popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._popout_btn.setFixedSize(28, 24)
        self._popout_btn.setToolTip(tr("workbench.node_graph.popout.tooltip"))
        self._popout_btn.clicked.connect(self.popout_requested.emit)
        header_lay.addWidget(self._popout_btn)
        root.addWidget(header)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(32)
        toolbar.setStyleSheet(f"background-color: {C['toolbar_bg']};")
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(6, 4, 6, 4)
        tb_lay.setSpacing(4)
        self._btn_serial = QPushButton(tr("workbench.node_graph.toolbar.serial"))
        self._btn_serial.setObjectName("ToolButton")
        self._btn_serial.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_serial.setToolTip("Alt+S")
        self._btn_serial.clicked.connect(self.add_serial_node)
        tb_lay.addWidget(self._btn_serial)
        # Phase 2E: Parallel Mixer is now active.
        self._btn_parallel = QPushButton(tr("workbench.node_graph.toolbar.parallel"))
        self._btn_parallel.setObjectName("ToolButton")
        self._btn_parallel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_parallel.setToolTip("Alt+P")
        self._btn_parallel.clicked.connect(self.add_parallel_mixer)
        tb_lay.addWidget(self._btn_parallel)
        # Layer Mixer remains a Phase 2 follow-up.
        self._btn_layer = QPushButton(tr("workbench.node_graph.toolbar.layer"))
        self._btn_layer.setObjectName("ToolButton")
        self._btn_layer.setEnabled(False)
        self._btn_layer.setToolTip(tr("workbench.node_graph.toolbar.coming_soon"))
        tb_lay.addWidget(self._btn_layer)
        self._btn_blur = QPushButton("🔵 Blur")
        self._btn_blur.setObjectName("ToolButton")
        self._btn_blur.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_blur.setToolTip("Add blur / out-of-focus node (Alt+B)")
        self._btn_blur.clicked.connect(self.add_blur_node)
        tb_lay.addWidget(self._btn_blur)
        tb_lay.addStretch(1)
        # Auto-layout button (Phase 2E)
        self._btn_layout = QPushButton(tr("workbench.node_graph.toolbar.fit"))
        self._btn_layout.setObjectName("ToolButton")
        self._btn_layout.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_layout.setToolTip("Ctrl+9")
        self._btn_layout.clicked.connect(self.fit_all)
        tb_lay.addWidget(self._btn_layout)
        root.addWidget(toolbar)

        # Canvas — wrap in a host so we can overlay the minimap.
        canvas_host = QWidget()
        canvas_lay = QVBoxLayout(canvas_host)
        canvas_lay.setContentsMargins(0, 0, 0, 0)
        canvas_lay.setSpacing(0)
        self.scene = NodeGraphScene(self)
        self.view = NodeGraphView(self.scene, self)
        self.view.setMinimumHeight(200)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_view_context_menu)
        canvas_lay.addWidget(self.view, stretch=1)
        # Minimap (Phase 2E) sits as a child of the view so it floats
        # in the top-right of the canvas.
        self.minimap = _MiniMapView(self.scene, self.view, self.view)
        self.minimap.setFixedSize(140, 90)
        self.minimap.move(8, 8)
        self.minimap.show()
        # Reposition on resize.
        self.view.installEventFilter(self)
        root.addWidget(canvas_host, stretch=1)

        # Status bar
        status = QWidget()
        status.setFixedHeight(22)
        status.setStyleSheet(f"background-color: {C['statusbar_bg']};")
        sb_lay = QHBoxLayout(status)
        sb_lay.setContentsMargins(8, 0, 8, 0)
        sb_lay.setSpacing(12)
        sb_style = (
            f"color: {C['statusbar_text']}; font-size: 10px; "
            "font-family: 'Pretendard', 'Segoe UI', sans-serif;"
        )
        self._lbl_count = QLabel()
        self._lbl_count.setStyleSheet(sb_style)
        self._lbl_selected = QLabel(
            tr("workbench.node_graph.status.no_selection"),
        )
        self._lbl_selected.setStyleSheet(sb_style)
        self._lbl_zoom = QLabel("100%")
        self._lbl_zoom.setStyleSheet(sb_style)
        sb_lay.addWidget(self._lbl_count)
        sb_lay.addStretch(1)
        sb_lay.addWidget(self._lbl_selected)
        sb_lay.addStretch(1)
        sb_lay.addWidget(self._lbl_zoom)
        root.addWidget(status)

        # Wiring
        self.scene.selection_changed_label.connect(self._on_selection_label)
        self.scene.graph_mutated.connect(self._on_graph_mutated)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        self._refresh_count()

        # Shortcuts — bound to this widget so they're active wherever
        # the widget is parented (workbench dock OR popout window).
        self._sc_add_serial = self._mk_shortcut("Alt+S", self.add_serial_node)
        self._sc_add_parallel = self._mk_shortcut("Alt+P", self.add_parallel_mixer)
        self._sc_add_blur = self._mk_shortcut("Alt+B", self.add_blur_node)
        self._sc_delete = self._mk_shortcut("Delete", self.delete_selected)
        self._sc_delete2 = self._mk_shortcut("Backspace", self.delete_selected)
        self._sc_rename = self._mk_shortcut("F2", self.rename_selected)
        self._sc_bypass = self._mk_shortcut("Ctrl+D", self.bypass_selected)
        self._sc_fit = self._mk_shortcut("Ctrl+9", self.fit_all)
        self._sc_zoom_reset = self._mk_shortcut("Ctrl+0", self.view.reset_zoom)
        self._sc_zoom_in = self._mk_shortcut("Ctrl++", lambda: self._zoom_step(+1))
        self._sc_zoom_out = self._mk_shortcut("Ctrl+-", lambda: self._zoom_step(-1))

    def _mk_shortcut(self, key: str, slot) -> QShortcut:
        sc = QShortcut(QKeySequence(key), self)
        sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        sc.activated.connect(slot)
        return sc

    # ---- public — node management ----

    def add_serial_node(self) -> None:
        node = self.scene.add_serial_node(
            label=tr("workbench.node_graph.default_label"),
        )
        self.scene.clearSelection()
        node.setSelected(True)
        self._refresh_count()
        self.minimap.refresh()

    def add_blur_node(self) -> None:
        node = self.scene.add_blur_node(label="Blur")
        self.scene.clearSelection()
        node.setSelected(True)
        self._refresh_count()
        self.minimap.refresh()

    def add_parallel_mixer(self) -> None:
        node = self.scene.add_parallel_mixer()
        self.scene.clearSelection()
        node.setSelected(True)
        self._refresh_count()
        self.minimap.refresh()

    def delete_selected(self) -> None:
        self.scene.delete_selected()
        self._refresh_count()
        self.minimap.refresh()

    def rename_selected(self) -> None:
        items = self.scene.selectedItems()
        if not items:
            return
        for it in items:
            if isinstance(it, NodeItem):
                it.mouseDoubleClickEvent(None) if False else None
                # Trigger the rename modal directly (the double-click
                # handler is the canonical entry point).
                from PySide6.QtWidgets import QInputDialog
                new_label, ok = QInputDialog.getText(
                    self, "Rename node", "Label:", text=it.label,
                )
                if ok and new_label.strip():
                    it.label = new_label.strip()
                    it.update()
                    self.scene._emit_selection_label()
                    self.scene.graph_mutated.emit()
                return

    def bypass_selected(self) -> None:
        items = self.scene.selectedItems()
        for it in items:
            if hasattr(it, "toggle_bypass"):
                it.toggle_bypass()
        if items:
            self.scene.graph_mutated.emit()

    def set_source_pixmap(self, pix) -> None:
        """True DaVinci-style live preview thumbnails. Each node
        renders **its cumulative grade up to and including itself**
        applied to the source frame. The IN node always shows the
        ungraded source, OUT shows the full chain.

        Pipeline per call:
          1. Centre-crop ``pix`` to the node thumbnail aspect.
          2. Cache an RGB ndarray of the cropped source.
          3. For each Serial node: walk the IN→node chain, apply
             every grade in sequence to a copy of the cached array,
             convert back to QPixmap.
          4. IO IN: ungraded source. IO OUT: full chain.

        Cost: each node-level paint runs ``apply_to_rgb`` once (a
        few ms on a 160×90 image). With 5 nodes × 10 Hz that's a
        couple percent of CPU — acceptable for a live preview.
        """
        if pix is None or pix.isNull():
            return
        # Guard: reject tiny/degenerate pixmaps (eg. blank 16×9 black
        # frames from _emit_blank) to avoid overwriting valid thumbnails
        # with black when the player temporarily has no clip at playhead.
        if pix.width() < 32 or pix.height() < 18:
            return
        from PySide6.QtCore import Qt as _Qt
        from PySide6.QtGui import QImage as _QImage
        from PySide6.QtGui import QPixmap as _QPixmap
        import numpy as _np

        tw = S["thumbnail_width"]
        th = S["thumbnail_height"]
        # 1+2: centre-crop + numpy cache for cheap re-grading per node.
        scaled = pix.scaled(
            tw, th,
            _Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            _Qt.TransformationMode.SmoothTransformation,
        )
        if scaled.width() > tw or scaled.height() > th:
            x = max(0, (scaled.width() - tw) // 2)
            y = max(0, (scaled.height() - th) // 2)
            scaled = scaled.copy(x, y, tw, th)
        src_rgb = self._pixmap_to_rgb_array(scaled)

        # 3: all nodes share the same source frame.
        # Per-node cumulative grade computation was removed because the
        # source frame (_preview_pixmap) now already has the grade
        # applied CPU-side (new rendering path). Applying grades AGAIN
        # caused double-grading → colour overflow → black thumbnails.
        for n in self.scene._serial_nodes:
            n.thumbnail = scaled
            n.update()

        # 4: IO node thumbnails. IN = ungraded, OUT = full chain.
        io_tw = S.get("io_thumbnail_width", 112)
        io_th = S.get("io_thumbnail_height", 63)
        io_scaled_src = pix.scaled(
            io_tw, io_th,
            _Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            _Qt.TransformationMode.SmoothTransformation,
        )
        if io_scaled_src.width() > io_tw or io_scaled_src.height() > io_th:
            x = max(0, (io_scaled_src.width() - io_tw) // 2)
            y = max(0, (io_scaled_src.height() - io_th) // 2)
            io_scaled_src = io_scaled_src.copy(x, y, io_tw, io_th)
        if hasattr(self.scene._in_node, "set_thumbnail"):
            self.scene._in_node.set_thumbnail(io_scaled_src)
        # OUT — full chain via the out node.
        out_chain = self.scene.evaluate_chain_to(self.scene._out_node)
        if not out_chain:
            out_pix = io_scaled_src
        else:
            io_rgb = self._pixmap_to_rgb_array(io_scaled_src)
            for grade in out_chain:
                io_rgb = apply_to_rgb(io_rgb, grade)
            out_pix = self._rgb_array_to_pixmap(io_rgb)
        if hasattr(self.scene._out_node, "set_thumbnail"):
            self.scene._out_node.set_thumbnail(out_pix)

    @staticmethod
    def _pixmap_to_rgb_array(pix):
        """QPixmap → uint8 H×W×3 ndarray. Goes through QImage
        Format_RGB888 to dodge byte-order surprises with RGBA."""
        from PySide6.QtGui import QImage as _QImage
        import numpy as _np
        img = pix.toImage().convertToFormat(_QImage.Format.Format_RGB888)
        w, h = img.width(), img.height()
        ptr = img.bits()
        # Qt pads each row to 4-byte alignment — bytesPerLine ≥ w*3.
        bpl = img.bytesPerLine()
        buf = bytes(ptr)[:bpl * h]
        arr = _np.frombuffer(buf, dtype=_np.uint8).reshape(h, bpl)[:, :w * 3]
        return arr.reshape(h, w, 3).copy()

    @staticmethod
    def _rgb_array_to_pixmap(rgb):
        """uint8 H×W×3 ndarray → QPixmap."""
        from PySide6.QtGui import QImage as _QImage
        from PySide6.QtGui import QPixmap as _QPixmap
        import numpy as _np
        rgb = _np.ascontiguousarray(rgb)
        h, w = rgb.shape[:2]
        img = _QImage(
            rgb.data, w, h, rgb.strides[0], _QImage.Format.Format_RGB888,
        ).copy()
        return _QPixmap.fromImage(img)

    def fit_all(self) -> None:
        br = self.scene.itemsBoundingRect()
        if br.isEmpty():
            return
        self.view.fitInView(
            br.adjusted(-60, -60, 60, 60),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        # ``fitInView`` skews the view's transform — recalc effective zoom.
        self.view._zoom = self.view.transform().m11()
        self.view.zoom_changed.emit(self.view._zoom)

    def retranslate(self) -> None:
        self._title_label.setText(tr("workbench.node_graph.title"))
        self._popout_btn.setToolTip(tr("workbench.node_graph.popout.tooltip"))
        self._btn_serial.setText(tr("workbench.node_graph.toolbar.serial"))
        self._btn_parallel.setText(tr("workbench.node_graph.toolbar.parallel"))
        self._btn_layer.setText(tr("workbench.node_graph.toolbar.layer"))
        self._btn_layout.setText(tr("workbench.node_graph.toolbar.fit"))
        self._refresh_count()

    # ---- Phase 2D: persistence ----

    def set_track(self, track) -> None:
        """Bind to a video track. Loads the track's saved scene
        snapshot if present, or starts fresh — fresh tracks get a
        default Node 1 the same way DaVinci Resolve seeds every clip
        with one serial node so the user always has a place for the
        first grade (and a place for the live preview thumbnail to
        live)."""
        # Save current track's state before swapping.
        self._save_to_current_track()
        self._track = track
        self._suspend_persist = True
        try:
            data = getattr(track, "node_graph_view_data", None) if track is not None else None
            if data:
                self.scene.load_from_data(data)
            else:
                # Reset scene to a clean state for fresh tracks, then
                # seed with Node 1 (DaVinci default).
                self.scene.load_from_data({"nodes": [], "connections": [], "next_id": 1})
                if track is not None:
                    self.scene.add_serial_node(label="Node 1")
        finally:
            self._suspend_persist = False
        self._refresh_count()
        self.minimap.refresh()

    def _save_to_current_track(self) -> None:
        if self._track is None or self._suspend_persist:
            return
        try:
            self._track.node_graph_view_data = self.scene.to_data()
        except Exception:
            pass

    def _on_graph_mutated(self) -> None:
        # Phase 2D: persist after every meaningful scene change. The
        # ``_suspend_persist`` flag prevents save loops while loading.
        if not self._suspend_persist:
            self._save_to_current_track()
        self._refresh_count()
        self.minimap.refresh()

    # ---- internals ----

    def _on_view_context_menu(self, pos) -> None:
        scene_pos = self.view.mapToScene(pos)
        clicked_items = self.scene.items(scene_pos)
        clicked_node = None
        for it in clicked_items:
            if isinstance(it, NodeItem):
                clicked_node = it
                break
        menu = QMenu(self)
        if clicked_node is not None:
            self.scene.clearSelection()
            clicked_node.setSelected(True)
            act_rename = menu.addAction(tr("workbench.node_graph.menu.rename"))
            act_rename.setShortcut(QKeySequence("F2"))
            act_bypass = menu.addAction(tr("workbench.node_graph.menu.bypass"))
            act_bypass.setShortcut(QKeySequence("Ctrl+D"))

            # Phase E — Add Mask submenu. One-click Magic presets,
            # plus dialogs for Power Window and HSL Qualifier.
            menu.addSeparator()
            mask_menu = menu.addMenu(tr("nodemask.menu.add_mask"))
            act_pw = mask_menu.addAction(tr("nodemask.menu.power_window"))
            act_hsl = mask_menu.addAction(tr("nodemask.menu.hsl"))
            mask_menu.addSeparator()
            act_lips = mask_menu.addAction(tr("nodemask.menu.magic_lips"))
            act_face = mask_menu.addAction(tr("nodemask.menu.magic_face"))
            act_eyes = mask_menu.addAction(tr("nodemask.menu.magic_eyes"))
            act_person = mask_menu.addAction(tr("nodemask.menu.magic_person"))
            has_mask = bool(getattr(clicked_node, "masks", None))
            act_edit = None
            act_clear = None
            if has_mask:
                menu.addSeparator()
                act_edit = menu.addAction(tr("nodemask.menu.edit"))
                act_clear = menu.addAction(tr("nodemask.menu.clear"))

            menu.addSeparator()
            act_delete = menu.addAction(tr("workbench.node_graph.menu.delete"))
            act_delete.setShortcut(QKeySequence("Delete"))
            chosen = menu.exec(self.view.mapToGlobal(pos))
            if chosen is act_rename:
                self.rename_selected()
            elif chosen is act_bypass:
                self.bypass_selected()
            elif chosen is act_pw:
                self.mask_request.emit(clicked_node, "power_window")
            elif chosen is act_hsl:
                self.mask_request.emit(clicked_node, "hsl")
            elif chosen is act_lips:
                self.mask_request.emit(clicked_node, "magic:lips")
            elif chosen is act_face:
                self.mask_request.emit(clicked_node, "magic:face")
            elif chosen is act_eyes:
                self.mask_request.emit(clicked_node, "magic:eyes")
            elif chosen is act_person:
                self.mask_request.emit(clicked_node, "magic:person")
            elif chosen is act_edit:
                self.mask_request.emit(clicked_node, "edit")
            elif chosen is act_clear:
                self.mask_request.emit(clicked_node, "clear")
            elif chosen is act_delete:
                self.delete_selected()
            return
        # Empty-canvas menu
        act_serial = menu.addAction(tr("workbench.node_graph.menu.add_serial"))
        act_serial.setShortcut(QKeySequence("Alt+S"))
        act_parallel = menu.addAction(tr("workbench.node_graph.menu.add_parallel"))
        act_parallel.setShortcut(QKeySequence("Alt+P"))
        menu.addSeparator()
        act_fit = menu.addAction(tr("workbench.node_graph.menu.fit"))
        act_fit.setShortcut(QKeySequence("Ctrl+9"))
        chosen = menu.exec(self.view.mapToGlobal(pos))
        if chosen is act_serial:
            self.add_serial_node()
        elif chosen is act_parallel:
            self.add_parallel_mixer()
        elif chosen is act_fit:
            self.fit_all()

    def _on_selection_label(self, label: str) -> None:
        if label:
            self._lbl_selected.setText(
                tr("workbench.node_graph.status.selected", label=label)
            )
        else:
            self._lbl_selected.setText(
                tr("workbench.node_graph.status.no_selection")
            )
        self.node_selection_changed.emit(label)
        # Phase 2D — emit selected node id (or "" for none) so the
        # editor can route the Color panel to that node's grade.
        items = self.scene.selectedItems()
        if items and isinstance(items[0], NodeItem):
            self.selected_node_id_changed.emit(items[0].node_id)
            self.selected_node_changed.emit(items[0])
        else:
            self.selected_node_id_changed.emit("")
            self.selected_node_changed.emit(None)

    def _on_zoom_changed(self, zoom: float) -> None:
        self._lbl_zoom.setText(f"{int(round(zoom * 100))}%")

    def _refresh_count(self) -> None:
        self._lbl_count.setText(
            tr("workbench.node_graph.status.nodes",
               n=self.scene.node_count())
        )

    def _zoom_step(self, direction: int) -> None:
        from PySide6.QtCore import QEvent, QPoint
        from PySide6.QtGui import QWheelEvent
        # Synthesise a wheel event at the canvas centre so the zoom
        # transform anchors there (instead of at the cursor, which
        # might be off-canvas when hitting Ctrl + ).
        center = self.view.viewport().rect().center()
        angle = 120 * (1 if direction > 0 else -1)
        evt = QWheelEvent(
            QPoint(center.x(), center.y()),
            self.view.mapToGlobal(QPoint(center.x(), center.y())),
            QPoint(0, 0),
            QPoint(0, angle),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        self.view.wheelEvent(evt)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.view and event.type() == QEvent.Type.Resize:
            # Pin minimap to top-right corner.
            mw = self.minimap.width()
            self.minimap.move(self.view.width() - mw - 8, 8)
            self.minimap.refresh()
        return super().eventFilter(obj, event)
