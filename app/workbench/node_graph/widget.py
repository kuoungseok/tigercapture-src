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
    QFrame,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import studio_chrome_qss
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
            "background-color: rgba(14, 14, 14, 0.88); "
            "border: 1px solid #303030; border-radius: 8px;"
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
        self.setStyleSheet(studio_chrome_qss(
            "QWidget{background:#0F1011;color:#E5E7EB;}"
            "QPushButton#ToolButton{min-width:18px;min-height:16px;padding:0px;}"
            "QToolButton#ToolButton{min-width:18px;min-height:16px;padding:0px;}"
        ))
        # Phase 2D: tracked so save_to_track / load_from_track stay
        # bound to the right object.
        self._track = None
        self._suspend_persist: bool = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(0)
        header.setStyleSheet("background:#111314;border-bottom:1px solid #202326;")
        header_lay = QHBoxLayout(header)
        header_lay.setContentsMargins(6, 0, 4, 0)
        header_lay.setSpacing(6)
        self._title_label = QLabel(tr("workbench.node_graph.title"))
        self._title_label.setStyleSheet(
            "color: #D4D9E1; font-family:'Segoe UI Variable','Segoe UI',sans-serif; "
            "font-size: 10px; font-weight: 620; letter-spacing: 0px;"
            "background: transparent; border: none; padding: 0px;"
        )
        header_lay.addWidget(self._title_label)
        header_lay.addStretch(1)
        self._popout_btn = QPushButton("")
        self._popout_btn.setObjectName("ToolButton")
        self._popout_btn.setIcon(app_icon("popout", size=11))
        self._popout_btn.setIconSize(icon_size(11))
        self._popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._popout_btn.setFixedSize(18, 16)
        self._popout_btn.setToolTip(tr("workbench.node_graph.popout.tooltip"))
        self._popout_btn.clicked.connect(self.popout_requested.emit)
        header_lay.addWidget(self._popout_btn)
        root.addWidget(header)
        header.hide()

        # Toolbar
        toolbar = QWidget()
        toolbar.setObjectName("NodeGraphToolbar")
        toolbar.setFixedHeight(23)
        toolbar.setStyleSheet(f"""
        QWidget#NodeGraphToolbar {{
            background-color: #101112;
            border: none;
            border-bottom: 1px solid rgba(178,186,202,20);
        }}
        QFrame#NodeGraphToolGroup {{
            background-color: rgba(255,255,255,5);
            border: 1px solid rgba(178,186,202,22);
            border-radius: 5px;
        }}
        QPushButton#ToolButton,
        QToolButton#ToolButton {{
            background-color: transparent;
            color: #B9BEC7;
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 0px;
            min-width: 0px;
            min-height: 0px;
        }}
        QPushButton#ToolButton:hover,
        QToolButton#ToolButton:hover {{
            background-color: rgba(255,255,255,10);
            border-color: rgba(220,225,238,58);
            color: #EEF0F4;
        }}
        QPushButton#ToolButton:pressed,
        QToolButton#ToolButton:pressed {{
            background-color: rgba(255,255,255,7);
            border-color: rgba(220,225,238,72);
        }}
        QPushButton#ToolButton:disabled,
        QToolButton#ToolButton:disabled {{
            background-color: transparent;
            border-color: transparent;
            color: #5C626B;
        }}
        QToolButton#ToolButton::menu-indicator {{
            image: none;
            width: 0px;
        }}
        """)
        tb_lay = QHBoxLayout(toolbar)
        tb_lay.setContentsMargins(8, 1, 6, 1)
        tb_lay.setSpacing(4)
        header_lay.removeWidget(self._title_label)
        header_lay.removeWidget(self._popout_btn)
        self._title_label.setParent(toolbar)
        self._popout_btn.setParent(toolbar)
        self._title_label.setStyleSheet(
            "color: #E0E4EA; font-family:'Segoe UI Variable','Segoe UI',sans-serif; "
            "font-size: 11px; font-weight: 520; letter-spacing: 0px;"
            "background: transparent; border: none; padding: 0px;"
        )
        tb_lay.addWidget(self._title_label)
        tb_lay.addSpacing(6)

        def _tool_group() -> tuple[QFrame, QHBoxLayout]:
            frame = QFrame(toolbar)
            frame.setObjectName("NodeGraphToolGroup")
            frame.setFixedHeight(19)
            lay = QHBoxLayout(frame)
            lay.setContentsMargins(2, 1, 2, 1)
            lay.setSpacing(1)
            return frame, lay

        def _icon_button(button, icon_name: str, tooltip: str) -> None:
            button.setText("")
            button.setIcon(app_icon(icon_name, size=11))
            button.setIconSize(icon_size(11))
            button.setFixedSize(18, 16)
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip.split("(")[0].strip())

        add_group, add_lay = _tool_group()
        graph_group, graph_lay = _tool_group()
        view_group, view_lay = _tool_group()

        self._btn_serial = QPushButton("")
        self._btn_serial.setObjectName("ToolButton")
        self._btn_serial.setCursor(Qt.CursorShape.PointingHandCursor)
        _icon_button(
            self._btn_serial,
            "plus",
            f"{tr('workbench.node_graph.toolbar.serial')} (Alt+S)",
        )
        self._btn_serial.clicked.connect(self.add_serial_node)
        add_lay.addWidget(self._btn_serial)
        # Phase 2E: Parallel Mixer is now active.
        self._btn_parallel = QPushButton("")
        self._btn_parallel.setObjectName("ToolButton")
        self._btn_parallel.setCursor(Qt.CursorShape.PointingHandCursor)
        _icon_button(
            self._btn_parallel,
            "layers",
            f"{tr('workbench.node_graph.toolbar.parallel')} (Alt+P)",
        )
        self._btn_parallel.clicked.connect(self.add_parallel_mixer)
        graph_lay.addWidget(self._btn_parallel)
        # Layer Mixer remains a Phase 2 follow-up.
        self._btn_layer = QPushButton("")
        self._btn_layer.setObjectName("ToolButton")
        self._btn_layer.setEnabled(False)
        _icon_button(
            self._btn_layer,
            "compound",
            f"{tr('workbench.node_graph.toolbar.layer')} - {tr('workbench.node_graph.toolbar.coming_soon')}",
        )
        self._btn_layer.setVisible(False)
        self._btn_blur = QPushButton("")
        self._btn_blur.setObjectName("ToolButton")
        self._btn_blur.setCursor(Qt.CursorShape.PointingHandCursor)
        _icon_button(self._btn_blur, "blur", "Add blur / out-of-focus node (Alt+B)")
        self._btn_blur.clicked.connect(self.add_blur_node)
        add_lay.addWidget(self._btn_blur)

        # ── Effect node buttons ──────────────────────────────────────────
        from PySide6.QtWidgets import QToolButton, QMenu
        eff_btn = QToolButton()
        eff_btn.setObjectName("ToolButton")
        eff_btn.setText("")
        eff_btn.setIcon(app_icon("effects", size=11))
        eff_btn.setIconSize(icon_size(11))
        eff_btn.setFixedSize(18, 16)
        eff_btn.setToolTip("Add effect node")
        eff_btn.setAccessibleName("Add effect node")
        eff_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        eff_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        eff_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        eff_menu = QMenu(eff_btn)
        eff_menu.setStyleSheet(studio_chrome_qss(""))
        _effects = [
            ("Curves", "curves"),
            ("Levels", "levels"),
            ("White Balance", "whitebalance"),
            ("Channel Mixer", "channelmixer"),
            None,
            ("Glow", "glow"),
            ("Vignette", "vignette"),
            ("Film Grain", "filmgrain"),
            ("Unsharp Mask", "unsharpmask"),
            ("Pixelate", "pixelate"),
            ("LUT", "lut"),
            None,
            ("SDR -> HDR EXR", "sdr_hdr_upmap"),
        ]
        for item in _effects:
            if item is None:
                eff_menu.addSeparator()
            else:
                label, kind = item
                act = eff_menu.addAction(label)
                act.triggered.connect(lambda checked=False, k=kind: self.add_effect_node(k))
        eff_btn.setMenu(eff_menu)
        add_lay.addWidget(eff_btn)
        self._effect_btn = eff_btn

        preset_btn = QToolButton()
        preset_btn.setObjectName("ToolButton")
        preset_btn.setText("")
        preset_btn.setIcon(app_icon("workflow", size=11))
        preset_btn.setIconSize(icon_size(11))
        preset_btn.setFixedSize(18, 16)
        preset_btn.setToolTip("Add node workflow preset")
        preset_btn.setAccessibleName("Add node workflow preset")
        preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        preset_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        preset_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        preset_menu = QMenu(preset_btn)
        preset_menu.setStyleSheet(studio_chrome_qss(""))
        preset_color = preset_menu.addAction("Color polish chain")
        preset_glow = preset_menu.addAction("Glow + mask chain")
        preset_hdr = preset_menu.addAction("HDR prep chain")
        preset_color.triggered.connect(lambda checked=False: self.add_workflow_preset("color_polish"))
        preset_glow.triggered.connect(lambda checked=False: self.add_workflow_preset("glow_mask"))
        preset_hdr.triggered.connect(lambda checked=False: self.add_workflow_preset("hdr_prep"))
        preset_btn.setMenu(preset_menu)
        graph_lay.addWidget(preset_btn)
        self._preset_btn = preset_btn

        tb_lay.addWidget(add_group)
        tb_lay.addWidget(graph_group)

        tb_lay.addStretch(1)
        # Auto-layout button (Phase 2E)
        self._btn_layout = QPushButton("")
        self._btn_layout.setObjectName("ToolButton")
        self._btn_layout.setCursor(Qt.CursorShape.PointingHandCursor)
        _icon_button(
            self._btn_layout,
            "fit",
            f"{tr('workbench.node_graph.toolbar.fit')} (Ctrl+9)",
        )
        self._btn_layout.clicked.connect(self.fit_all)
        view_lay.addWidget(self._btn_layout)
        view_lay.addWidget(self._popout_btn)
        tb_lay.addWidget(view_group)
        root.addWidget(toolbar)

        # Canvas — wrap in a host so we can overlay the minimap.
        canvas_host = QWidget()
        canvas_lay = QVBoxLayout(canvas_host)
        canvas_lay.setContentsMargins(0, 0, 0, 0)
        canvas_lay.setSpacing(0)
        self.scene = NodeGraphScene(self)
        self.view = NodeGraphView(self.scene, self)
        self.view.setMinimumHeight(150)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._on_view_context_menu)
        canvas_lay.addWidget(self.view, stretch=1)
        # Minimap (Phase 2E) sits as a child of the view so it floats
        # in the top-right of the canvas.
        self.minimap = _MiniMapView(self.scene, self.view, self.view)
        self.minimap.setFixedSize(140, 90)
        self.minimap.move(8, 8)
        self.minimap.hide()
        # Reposition on resize.
        self.view.installEventFilter(self)
        root.addWidget(canvas_host, stretch=1)

        # ── Effect params panel (hidden until an effect node is selected) ──
        self._effect_params_panel = _EffectParamsPanel(self)
        self._effect_params_panel.hide()
        root.addWidget(self._effect_params_panel)

        # Status bar
        status = QWidget()
        status.setFixedHeight(0)
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
        status.hide()

        # Wiring
        self.scene.selection_changed_label.connect(self._on_selection_label)
        self.scene.graph_mutated.connect(self._on_graph_mutated)
        self.view.zoom_changed.connect(self._on_zoom_changed)
        self.selected_node_changed.connect(self._on_selected_node_for_params)
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
            auto_connect=True,
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

    def add_effect_node(self, kind: str) -> None:
        node = self.scene.add_effect_node(effect_kind=kind)
        self.scene.clearSelection()
        node.setSelected(True)
        self._refresh_count()
        self.minimap.refresh()

    def add_workflow_preset(self, preset: str) -> None:
        """Add a small, real node chain preset to the current graph."""
        specs: dict[str, list[tuple[str, str]]] = {
            "color_polish": [
                ("whitebalance", "Balance"),
                ("curves", "Color Grade"),
                ("vignette", "Mask"),
            ],
            "glow_mask": [
                ("glow", "Neon Glow"),
                ("blur", "Soft Pass"),
                ("vignette", "Edge Mask"),
            ],
            "hdr_prep": [
                ("levels", "Levels"),
                ("unsharpmask", "Detail"),
                ("sdr_hdr_upmap", "HDR Prep"),
            ],
        }
        created = []
        for kind, label in specs.get(str(preset), []):
            if kind == "blur":
                created.append(self.scene.add_blur_node(label=label, auto_connect=True))
            else:
                created.append(
                    self.scene.add_effect_node(
                        effect_kind=kind,
                        label=label,
                        auto_connect=True,
                    )
                )
        if not created:
            return
        self.scene.clearSelection()
        created[-1].setSelected(True)
        self._refresh_count()
        self.minimap.refresh()
        self.fit_all()

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
        """Live preview thumbnails.

        ``pix`` is the fully-rendered preview frame from
        ``ProjectPlayer`` — every node effect + color_grade has
        already been applied CPU-side. So all node thumbnails just
        show the same scaled-down version of that frame; running the
        chain on top would double-apply.

        Per-node "cumulative-up-to-here" previews aren't possible
        without an ungraded source pixmap (the host only passes the
        graded one). Adding that path is a separate task — for now
        every serial node and OUT share ``scaled``, while IN keeps
        its own copy (visually identical until the host starts
        sending an ungraded source through a second channel).
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
        # OUT — full chain. ``pix`` is already the fully-graded /
        # fully-effected output frame coming from the project player
        # (``project_player.py`` applies ``_apply_node_effect_player``
        # per node before emitting ``frame_ready``), so the OUT
        # thumbnail is just that frame scaled — no further apply.
        # The legacy ``evaluate_chain_to`` re-apply path double-graded
        # the image and silently dropped effect_params (Curves / Glow
        # / Pixelate / …); that's the bug this rewrite fixes.
        if hasattr(self.scene._out_node, "set_thumbnail"):
            self.scene._out_node.set_thumbnail(io_scaled_src)

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
            br.adjusted(-32, -32, 32, 32),
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        # ``fitInView`` skews the view's transform — recalc effective zoom.
        self.view._zoom = self.view.transform().m11()
        self.view.zoom_changed.emit(self.view._zoom)

    def retranslate(self) -> None:
        self._title_label.setText(tr("workbench.node_graph.title"))
        self._popout_btn.setToolTip(tr("workbench.node_graph.popout.tooltip"))
        self._btn_serial.setText("")
        self._btn_serial.setToolTip(
            f"{tr('workbench.node_graph.toolbar.serial')} (Alt+S)"
        )
        self._btn_parallel.setText("")
        self._btn_parallel.setToolTip(
            f"{tr('workbench.node_graph.toolbar.parallel')} (Alt+P)"
        )
        self._btn_layer.setText("")
        self._btn_layer.setToolTip(
            f"{tr('workbench.node_graph.toolbar.layer')} - "
            f"{tr('workbench.node_graph.toolbar.coming_soon')}"
        )
        self._btn_blur.setText("")
        if hasattr(self, "_effect_btn"):
            self._effect_btn.setText("")
            self._effect_btn.setToolTip("Add effect node")
        if hasattr(self, "_preset_btn"):
            self._preset_btn.setText("")
            self._preset_btn.setToolTip("Add node workflow preset")
        self._btn_layout.setText("")
        self._btn_layout.setToolTip(
            f"{tr('workbench.node_graph.toolbar.fit')} (Ctrl+9)"
        )
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
        repaired_chain = False
        try:
            data = getattr(track, "node_graph_view_data", None) if track is not None else None
            if data:
                self.scene.load_from_data(data)
            else:
                # Reset scene to a clean state for fresh tracks, then
                # seed with Node 1 (DaVinci default).
                self.scene.load_from_data({"nodes": [], "connections": [], "next_id": 1})
                if track is not None:
                    self.scene.add_serial_node(label="Node 1", auto_connect=True)
            repaired_chain = bool(self.scene.ensure_default_chain())
        finally:
            self._suspend_persist = False
        if repaired_chain:
            self._save_to_current_track()
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
            act_track_region = mask_menu.addAction("Track selected region")
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
            elif chosen is act_track_region:
                self.mask_request.emit(clicked_node, "track_region")
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
        act_hdr = menu.addAction("SDR -> HDR EXR")
        menu.addSeparator()
        act_fit = menu.addAction(tr("workbench.node_graph.menu.fit"))
        act_fit.setShortcut(QKeySequence("Ctrl+9"))
        chosen = menu.exec(self.view.mapToGlobal(pos))
        if chosen is act_serial:
            self.add_serial_node()
        elif chosen is act_parallel:
            self.add_parallel_mixer()
        elif chosen is act_hdr:
            self.add_effect_node("sdr_hdr_upmap")
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

    def _on_selected_node_for_params(self, node) -> None:
        """Show/hide effect params panel when an EffectNodeItem is selected."""
        from app.workbench.node_graph.items.effect_node_item import EffectNodeItem
        if isinstance(node, EffectNodeItem):
            self._effect_params_panel.bind(node, self._on_effect_param_change)
        else:
            # Clear the panel's stale ``_node`` reference before hiding.
            # Without this, deleting the previously-bound node leaves
            # the panel pointing at a destroyed QGraphicsItem — the
            # next param-change slot would AttributeError or worse.
            self._effect_params_panel.bind(None, None)
            self._effect_params_panel.hide()

    def _on_effect_param_change(self) -> None:
        """Propagate effect param changes through graph_mutated so the
        rendering pipeline refreshes the preview."""
        self.scene.graph_mutated.emit()


# ── Effect params panel ───────────────────────────────────────────────────────

class _EffectParamsPanel(QWidget):
    """Inline parameter panel shown below the node graph canvas
    when an EffectNodeItem is selected."""

    _STYLE = (
        "QWidget{background:#101214;color:#E5E7EB;font-size:10px;}"
        "QWidget#EffectParamsPanel{background:#101214;border-top:1px solid #252A31;"
        "border-left:none;border-right:none;border-bottom:1px solid #171B20;}"
        "QWidget#EffectParamGrid{background:transparent;border:none;}"
        "QLabel#EffectParamTitle{color:#EEF2F7;font-size:10px;font-weight:660;"
        "background:transparent;border:none;}"
        "QWidget#EffectParamRow{background:transparent;border:none;border-radius:0px;}"
        "QLineEdit{background:#12161B;color:#DCE2EA;border:1px solid #2C333D;"
        "border-radius:7px;padding:4px 7px;font-size:9px;}"
        "QCheckBox{font-size:9px;color:#B5BDC8;background:transparent;spacing:6px;}"
        "QCheckBox::indicator{width:11px;height:11px;border:1px solid #59616C;"
        "border-radius:4px;background:#171A1E;}"
        "QCheckBox::indicator:checked{background:#A7B2C1;border-color:#DCE2EA;}"
    )
    _SLD = (
        "QSlider::groove:horizontal{background:#2B3037;height:3px;border-radius:2px;}"
        "QSlider::handle:horizontal{background:#B5C0CE;border:1px solid #E0E5EC;width:11px;height:11px;"
        "margin:-5px 0;border-radius:6px;}"
        "QSlider::handle:horizontal:hover{background:#D6DEE8;border-color:#FFFFFF;}"
        "QSlider::sub-page:horizontal{background:#7F8C9D;border-radius:2px;}"
        "QSlider::add-page:horizontal{background:#2B3037;border-radius:2px;}"
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("EffectParamsPanel")
        self._node = None
        self._on_change = None
        self._param_grid = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scrollable content area
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setStyleSheet(studio_chrome_qss(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:4px;margin:4px 0;}"
            "QScrollBar::handle:vertical{background:rgba(214,220,235,38);border-radius:2px;min-height:22px;}"
            "QScrollBar::handle:vertical:hover{background:rgba(214,220,235,120);border-radius:4px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;background:transparent;}"
        ))
        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;")
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(8, 5, 14, 6)
        self._inner_lay.setSpacing(4)
        scroll.setWidget(self._inner)
        outer.addWidget(scroll)

    def bind(self, node, on_change) -> None:
        """Bind to ``node`` (an EffectNodeItem) and call ``on_change``
        whenever a knob moves. Pass ``node=None`` to unbind — that
        clears the internal reference and hides the panel; callers
        use this when the user selects a non-effect node so we don't
        keep a dangling pointer at a possibly-deleted QGraphicsItem.
        """
        self._node = node
        self._on_change = on_change
        if node is None:
            # Don't bother rebuilding the inner widgets for an unbind.
            return
        self._rebuild()
        self.show()

    def _rebuild(self) -> None:
        from app.effect_node_params import _KIND_META
        # Clear
        while self._inner_lay.count():
            item = self._inner_lay.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        node = self._node
        if node is None:
            return
        ep = getattr(node, "effect_params", None)
        kind = getattr(node, "NODE_KIND", "")
        if ep is None:
            return

        meta = _KIND_META.get(kind, (node.label, "#607D8B", None))
        hdr_color = meta[1]
        self.setStyleSheet(self._STYLE + self._SLD)
        self.setMinimumHeight(88)
        self.setMaximumHeight(118)

        # Title row
        from PySide6.QtWidgets import QHBoxLayout as _HL
        title_w = QWidget(); title_w.setStyleSheet("background:transparent;border:none;")
        tr = _HL(title_w); tr.setContentsMargins(2, 0, 0, 2); tr.setSpacing(7)
        dot = QLabel(""); dot.setFixedSize(7, 7)
        dot.setStyleSheet(f"background:{hdr_color};border:none;border-radius:3px;")
        lbl = QLabel(f" {node.label}  [{meta[0]}]")
        lbl.setObjectName("EffectParamTitle")
        tr.addWidget(dot); tr.addWidget(lbl, 1)
        self._inner_lay.addWidget(title_w)
        self._param_grid = None
        use_grid = kind not in {"channelmixer", "sdr_hdr_upmap"}
        if use_grid:
            from PySide6.QtWidgets import QGridLayout as _Grid
            grid_host = QWidget()
            grid_host.setObjectName("EffectParamGrid")
            grid = _Grid(grid_host)
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(12)
            grid.setVerticalSpacing(2)
            self._param_grid = grid
            self._inner_lay.addWidget(grid_host)

        emit = self._emit
        display_labels = {
            "levels": ["Input Black", "Input White", "Gamma", "Output Black", "Output White"],
            "curves": ["Midtone"],
            "glow": ["Threshold", "Radius", "Intensity", "Red Tint", "Green Tint", "Blue Tint"],
            "filmgrain": ["Amount", "Grain Size"],
            "vignette": ["Amount", "Size", "Feather", "Roundness"],
            "lut": ["Blend"],
            "whitebalance": ["Temperature", "Tint"],
            "unsharpmask": ["Amount", "Radius", "Threshold"],
            "pixelate": ["Block Size"],
            "channelmixer": [
                "Input R", "Input G", "Input B",
                "Input R", "Input G", "Input B",
                "Input R", "Input G", "Input B",
            ],
            "sdr_hdr_upmap": ["Peak Nits", "Exposure", "Highlight", "Saturation", "Max Frames"],
        }.get(kind, [])
        row_index = 0
        display_checks = {
            "filmgrain": ["Monochrome"],
        }.get(kind, [])
        check_index = 0

        def _srow(label, lo, hi, val, setter, scale=1.0, fmt="{:.0f}"):
            from PySide6.QtWidgets import (QHBoxLayout as _H, QSlider as _Sl,
                                            QLabel as _Lb, QWidget as _W)
            nonlocal row_index
            idx = row_index
            if idx < len(display_labels):
                label = display_labels[idx]
            row_index += 1
            def _fmt(v: int) -> str:
                text = fmt.format(v * scale)
                return (
                    text.replace("%", " %")
                    .replace("px", " px")
                    .replace("K", " K")
                )
            row = _W(); row.setObjectName("EffectParamRow")
            row.setFixedHeight(20)
            rl = _H(row); rl.setContentsMargins(2, 0, 2, 0); rl.setSpacing(7)
            lb = _Lb(label); lb.setFixedWidth(78)
            lb.setStyleSheet("font-size:9px;color:#AAB2BD;background:transparent;border:none;")
            sl = _Sl(Qt.Orientation.Horizontal)
            sl.setMinimumWidth(120)
            safe_val = max(int(lo), min(int(hi), int(val)))
            sl.setRange(lo, hi); sl.setValue(safe_val)
            vl = _Lb(_fmt(safe_val))
            vl.setFixedWidth(48)
            vl.setStyleSheet("font-size:9px;color:#DDE3EA;background:transparent;border:none;")
            vl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            def _u(v, vl=vl, fn=setter):
                vl.setText(_fmt(v)); fn(v); emit()
            sl.valueChanged.connect(_u)
            rl.addWidget(lb); rl.addWidget(sl, 1); rl.addWidget(vl)
            grid = getattr(self, "_param_grid", None)
            if grid is not None:
                grid.addWidget(row, idx // 2, idx % 2)
            else:
                self._inner_lay.addWidget(row)
            return sl

        def _chk(label, checked, setter):
            from PySide6.QtWidgets import QCheckBox
            nonlocal check_index
            if check_index < len(display_checks):
                label = display_checks[check_index]
            check_index += 1
            cb = QCheckBox(label); cb.setChecked(checked)
            cb.setStyleSheet("font-size:9px;color:#A0A6AF;background:transparent;")
            cb.toggled.connect(lambda v: (setter(bool(v)), emit()))
            self._inner_lay.addWidget(cb)

        if kind == "levels":
            _srow("블랙 포인트", 0, 254, int(ep.in_black*255), lambda v: setattr(ep,"in_black",v/255))
            _srow("화이트 포인트", 1, 255, int(ep.in_white*255), lambda v: setattr(ep,"in_white",v/255))
            _srow("감마", 10, 300, int(ep.gamma*100), lambda v: setattr(ep,"gamma",v/100), 0.01, "{:.2f}")
            _srow("아웃 블랙", 0, 254, int(ep.out_black*255), lambda v: setattr(ep,"out_black",v/255))
            _srow("아웃 화이트", 1, 255, int(ep.out_white*255), lambda v: setattr(ep,"out_white",v/255))

        elif kind == "curves":
            mid = ep.master[1][1] if len(ep.master) > 1 else 0.5
            _srow("밝기 (중간)", 0, 100, int(mid*100),
                  lambda v: setattr(ep, "master", [[0,0],[0.5,v/100],[1,1]]), fmt="{:.0f}%")

        elif kind == "glow":
            _srow("임계값", 10, 100, int(ep.threshold*100), lambda v: setattr(ep,"threshold",v/100), fmt="{:.0f}%")
            _srow("반경", 2, 80, ep.radius, lambda v: setattr(ep,"radius",int(v)), fmt="{:.0f}px")
            _srow("강도", 0, 200, int(ep.intensity*100), lambda v: setattr(ep,"intensity",v/100), fmt="{:.0f}%")
            _srow("R 틴트", 50, 150, int(ep.tint_r*100), lambda v: setattr(ep,"tint_r",v/100), fmt="{:.0f}%")
            _srow("G 틴트", 50, 150, int(ep.tint_g*100), lambda v: setattr(ep,"tint_g",v/100), fmt="{:.0f}%")
            _srow("B 틴트", 50, 150, int(ep.tint_b*100), lambda v: setattr(ep,"tint_b",v/100), fmt="{:.0f}%")

        elif kind == "filmgrain":
            _srow("강도", 0, 300, int(ep.amount*1000), lambda v: setattr(ep,"amount",v/1000), 0.1, "{:.1f}%")
            _srow("입자 크기", 5, 50, int(ep.size*10), lambda v: setattr(ep,"size",v/10), 0.1, "{:.1f}×")
            _chk("모노크롬", ep.monochrome, lambda v: setattr(ep,"monochrome",bool(v)))

        elif kind == "vignette":
            _srow("강도", 0, 100, int(ep.amount*100), lambda v: setattr(ep,"amount",v/100), fmt="{:.0f}%")
            _srow("크기", 10, 100, int(ep.size*100), lambda v: setattr(ep,"size",v/100), fmt="{:.0f}%")
            _srow("부드러움", 0, 100, int(ep.feather*100), lambda v: setattr(ep,"feather",v/100), fmt="{:.0f}%")
            _srow("원형도", 0, 100, int(ep.round*100), lambda v: setattr(ep,"round",v/100), fmt="{:.0f}%")

        elif kind == "lut":
            from PySide6.QtWidgets import QHBoxLayout as _HL2, QLineEdit, QFileDialog
            pr = QWidget(); pr.setStyleSheet("background:transparent;")
            prl = _HL2(pr); prl.setContentsMargins(0,0,0,0); prl.setSpacing(4)
            pe = QLineEdit(ep.path or ""); pe.setReadOnly(True); pe.setPlaceholderText(".cube…")
            pe.setStyleSheet("background:rgba(255,255,255,13);color:#E8EAF4;border:1px solid #30384F;border-radius:10px;font-size:10px;padding:5px 8px;")
            pe.setPlaceholderText(".cube / .3dl")
            bb = QPushButton(""); bb.setFixedSize(26,22)
            bb.setIcon(app_icon("project", size=15))
            bb.setIconSize(icon_size(15))
            bb.setStyleSheet("QPushButton{background:rgba(255,255,255,18);color:#E8EAF4;border:1px solid #37405A;border-radius:10px;}"
                             "QPushButton:hover{background:rgba(255,255,255,30);border-color:#7580A5;}")
            def _browse(pe=pe):
                p, _ = QFileDialog.getOpenFileName(self, "Choose LUT", "", "LUT Files (*.cube *.3dl)")
                if p: ep.path=p; pe.setText(p); emit()
            bb.clicked.connect(_browse)
            prl.addWidget(pe,1); prl.addWidget(bb)
            self._inner_lay.addWidget(pr)
            _srow("블렌드", 0, 100, int(ep.strength*100), lambda v: setattr(ep,"strength",v/100), fmt="{:.0f}%")

        elif kind == "whitebalance":
            _srow("온도 (K)", 2000, 12000, ep.temperature, lambda v: setattr(ep,"temperature",int(v)), fmt="{:.0f}K")
            _srow("틴트", -100, 100, ep.tint, lambda v: setattr(ep,"tint",int(v)), fmt="{:+.0f}")

        elif kind == "unsharpmask":
            _srow("강도", 0, 300, int(ep.amount*100), lambda v: setattr(ep,"amount",v/100), fmt="{:.0f}%")
            _srow("반경", 1, 30, ep.radius, lambda v: setattr(ep,"radius",int(v)), fmt="{:.0f}px")
            _srow("임계값", 0, 50, ep.threshold, lambda v: setattr(ep,"threshold",int(v)), fmt="{:.0f}")

        elif kind == "pixelate":
            _srow("블록 크기", 2, 200, ep.block_size, lambda v: setattr(ep,"block_size",int(v)), fmt="{:.0f}px")

        elif kind == "channelmixer":
            for out_ch, out_label in [("r","출력 R"),("g","출력 G"),("b","출력 B")]:
                hdr = QLabel(out_label)
                hdr.setText({"r": "Output R", "g": "Output G", "b": "Output B"}.get(out_ch, out_label))
                hdr.setStyleSheet("font-size:9px;color:#A7ADC2;font-weight:bold;background:transparent;margin-top:2px;")
                self._inner_lay.addWidget(hdr)
                for in_ch, in_label in [("r","← R"),("g","← G"),("b","← B")]:
                    k = f"{out_ch}{in_ch}"
                    cur = int(getattr(ep, k, 1.0 if out_ch==in_ch else 0.0) * 100)
                    def _mk(key):
                        return lambda v: setattr(ep, key, v/100.0)
                    _srow(f"  {in_label}", -100, 200, cur, _mk(k), fmt="{:.0f}%")

        elif kind == "sdr_hdr_upmap":
            note = QLabel("Job node: creates HDR-capable float EXR frames. Preview stays realtime.")
            note.setWordWrap(True)
            note.setStyleSheet("font-size:10px;color:#A7ADC2;background:rgba(84,215,255,24);border-radius:8px;padding:6px;")
            self._inner_lay.addWidget(note)
            _srow("Peak nits", 100, 4000, int(ep.peak_nits), lambda v: setattr(ep, "peak_nits", int(v)), fmt="{:.0f}")
            _srow("Exposure", -300, 300, int(ep.exposure_stops * 100), lambda v: setattr(ep, "exposure_stops", v / 100.0), 0.01, "{:+.2f}")
            _srow("Highlight", 25, 800, int(ep.highlight_boost * 100), lambda v: setattr(ep, "highlight_boost", v / 100.0), 0.01, "{:.2f}x")
            _srow("Saturation", 0, 300, int(ep.saturation_boost * 100), lambda v: setattr(ep, "saturation_boost", v / 100.0), 0.01, "{:.2f}x")
            _srow("Max frames", 0, 600, int(ep.max_frames), lambda v: setattr(ep, "max_frames", int(v)), fmt="{:.0f}")

        self._inner_lay.addStretch(1)

    def _emit(self) -> None:
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass
