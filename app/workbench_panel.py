"""Right-dock Workbench panel — TigerCapture's contextual properties.

Populated by the editor when the user selects a track / clip on the
timeline. Replaces the old "Inspector" name (Phase 3 of the Media
Editor Pro plan): "Workbench" is TigerCapture's signature term —
the place where you put your selected piece down to mess with its
fades, speed, volume, and (Phase 2) the per-clip node graph.

Phase B1 was read-only; Phase B2 added editable sliders for fade in /
fade out / volume. Phase 1.5+ will expand this to per-clip transform,
opacity, and node-graph routing as the multi-clip data model lights
up the renderer.
"""
from __future__ import annotations

from os.path import basename
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


def _format_ms(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}.{(int(ms) % 1000) // 100}"


class _Row(QWidget):
    """Two-column key/value row used throughout the workbench."""

    def __init__(self, label: str, value: str = "—") -> None:
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self._key_text = label
        self._key = QLabel(label)
        # Explicit hex colours — ``palette(text)`` was resolving to
        # default-palette black on this Qt build, which made the
        # value text invisible on the dark dock background.
        self._key.setStyleSheet(
            "color: #8a8a8a; font-size: 11px;"
        )
        self._key.setFixedWidth(72)
        self._val = QLabel(value)
        self._val.setStyleSheet(
            "color: #ffffff; font-size: 11px;"
        )
        self._val.setWordWrap(True)
        self._val.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        h.addWidget(self._key, alignment=Qt.AlignmentFlag.AlignTop)
        h.addWidget(self._val, stretch=1)

    def set_label(self, text: str) -> None:
        self._key_text = text
        self._key.setText(text)

    def set_value(self, v: str) -> None:
        self._val.setText(v if v else "—")


class _SliderRow(QWidget):
    """Editable label + slider + readout. Emits ``value_changed(int)``
    on every drag tick (used to drive the live preview) and
    ``value_committed(int)`` once on slider release (used to push a
    history entry — registering on every tick would flood the stack
    with one snapshot per pixel of slider travel)."""

    value_changed = Signal(int)
    value_committed = Signal(int)

    def __init__(
        self,
        label: str,
        minimum: int,
        maximum: int,
        formatter=None,
    ) -> None:
        super().__init__()
        self._formatter = formatter or (lambda v: str(int(v)))
        self._suppress = False
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        self._key = QLabel(label)
        self._key.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        self._key.setFixedWidth(72)
        self._readout = QLabel(self._formatter(0))
        self._readout.setStyleSheet("color: #ffffff; font-size: 11px;")
        self._readout.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        head.addWidget(self._key)
        head.addWidget(self._readout, stretch=1)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(int(minimum), int(maximum))
        self._slider.setValue(0)
        self._slider.valueChanged.connect(self._on_slider)
        self._slider.sliderReleased.connect(self._on_release)

        v.addLayout(head)
        v.addWidget(self._slider)

    def set_label(self, text: str) -> None:
        self._key.setText(text)

    def set_value(self, v: int) -> None:
        """Push value without re-emitting."""
        self._suppress = True
        try:
            self._slider.setValue(int(v))
            self._readout.setText(self._formatter(int(v)))
        finally:
            self._suppress = False

    def set_enabled(self, enabled: bool) -> None:
        self._slider.setEnabled(bool(enabled))

    def _on_slider(self, value: int) -> None:
        self._readout.setText(self._formatter(int(value)))
        if self._suppress:
            return
        self.value_changed.emit(int(value))

    def _on_release(self) -> None:
        # Slider released — drive the history-savepoint signal. The
        # editor wires this to ``_register_change`` while ignoring
        # the per-tick ``value_changed`` so the undo stack only sees
        # one entry per gesture.
        if self._suppress:
            return
        self.value_committed.emit(int(self._slider.value()))


class _NodeRow(QWidget):
    """Single clickable row in the workbench's NodeGraph section.

    Phase 2 of the Media Editor Pro plan introduced ``track.node_graph``
    as a per-track effects DAG; today there's only a Color node, but
    LUT / Blur / TrackMatte will land in later phases. The row shows
    an icon + name + status badge and emits ``clicked(kind)`` so the
    editor can route focus to the matching panel."""

    clicked = Signal(str)

    def __init__(self, kind: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setStyleSheet(
            "QWidget { background-color: #1e1e22; border-radius: 4px; }"
            "QWidget:hover { background-color: #2a2a30; }"
        )
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(8)
        self._icon = QLabel({"color": "🎨"}.get(kind, "•"))
        self._icon.setStyleSheet("font-size: 13px;")
        h.addWidget(self._icon)
        self._label = QLabel(label)
        self._label.setStyleSheet(
            "color: #ffffff; font-size: 11px; font-weight: 600;"
        )
        h.addWidget(self._label)
        h.addStretch(1)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #8a8a8a; font-size: 10px;")
        h.addWidget(self._status)

    def set_status(self, text: str, accent: bool = False) -> None:
        self._status.setText(text)
        if accent:
            self._status.setStyleSheet(
                "color: #D85A30; font-size: 10px; font-weight: 700;"
            )
        else:
            self._status.setStyleSheet("color: #8a8a8a; font-size: 10px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._kind)
            return
        super().mousePressEvent(event)


class WorkbenchPanel(QWidget):
    """Right-dock contextual workbench. Call ``set_video_track``,
    ``set_audio_clip``, or ``clear()`` to update the displayed
    contents. Editable sliders for fade in / fade out (both video
    tracks and audio clips) and volume (audio clips). The panel emits
    signals; the editor decides what to mutate."""

    # Editable slider signals — value units in parentheses.
    fade_in_changed = Signal(int)         # ms — live during slider drag
    fade_out_changed = Signal(int)        # ms — live during slider drag
    volume_changed = Signal(float)        # dB — live during slider drag
    # Slider-release pulses for the history stack. Editor connects
    # these to ``_register_change`` so undo gets one entry per
    # gesture instead of one per tick.
    fade_in_committed = Signal(int)
    fade_out_committed = Signal(int)
    volume_committed = Signal(float)
    # Phase 2 NodeGraph integration: emitted when the user clicks one
    # of the node rows. Editor wires this to scroll/expand the
    # corresponding panel (currently only "color" → Color section).
    node_focused = Signal(str)

    # Slider ranges — picked to cover practical use without ceding
    # screen real-estate to extreme values.
    FADE_MAX_MS = 5000
    VOLUME_MIN_DB = -60.0
    VOLUME_MAX_DB = 12.0

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Minimum-height floor — without it, when the right dock is
        # short the subtitle panel's min-height pushes the workbench
        # to zero and the rows seem to disappear.
        self.setMinimumHeight(260)
        # ``_target`` remembers what the sliders are currently
        # editing. ``("video", track)`` or ``("audio", track, clip)``
        # — the editor reads this when it gets a slider signal so it
        # can route the mutation to the right object.
        self._target: tuple | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self._title = QLabel(tr("workbench.empty.title"))
        self._title.setStyleSheet(
            "color: #ffffff; font-weight: 600; font-size: 12px;"
        )
        root.addWidget(self._title)

        self._subtitle = QLabel(tr("workbench.empty.subtitle"))
        self._subtitle.setStyleSheet(
            "color: #8a8a8a; font-style: italic; font-size: 11px;"
        )
        self._subtitle.setWordWrap(True)
        root.addWidget(self._subtitle)

        # Property rows always live in the layout; they switch their
        # text contents between "selection placeholder" and concrete
        # values rather than hide/show. Always-visible avoids the
        # earlier issue where ``hide()`` during init left the rows
        # invisible even after ``set_video_track`` ran.
        self._rows_host = QWidget()
        rows = QVBoxLayout(self._rows_host)
        rows.setContentsMargins(0, 4, 0, 0)
        rows.setSpacing(4)

        self._row_name = _Row(tr("workbench.row.name"))
        self._row_source = _Row(tr("workbench.row.source"))
        self._row_duration = _Row(tr("workbench.row.duration"))
        self._row_position = _Row(tr("workbench.row.position"))
        self._row_fade_in = _SliderRow(
            tr("workbench.row.fade_in"),
            0, self.FADE_MAX_MS,
            formatter=_format_ms,
        )
        self._row_fade_out = _SliderRow(
            tr("workbench.row.fade_out"),
            0, self.FADE_MAX_MS,
            formatter=_format_ms,
        )
        # Volume slider stores int 10ths of dB (so -600..120 maps to
        # -60.0..+12.0 dB). Forward to listeners as float dB.
        self._row_volume = _SliderRow(
            tr("workbench.row.volume"),
            int(self.VOLUME_MIN_DB * 10),
            int(self.VOLUME_MAX_DB * 10),
            formatter=lambda raw: f"{raw / 10.0:+.1f} dB",
        )
        self._row_speed = _Row(tr("workbench.row.speed"))

        self._row_fade_in.value_changed.connect(self.fade_in_changed.emit)
        self._row_fade_out.value_changed.connect(self.fade_out_changed.emit)
        self._row_volume.value_changed.connect(
            lambda raw: self.volume_changed.emit(raw / 10.0),
        )
        self._row_fade_in.value_committed.connect(self.fade_in_committed.emit)
        self._row_fade_out.value_committed.connect(self.fade_out_committed.emit)
        self._row_volume.value_committed.connect(
            lambda raw: self.volume_committed.emit(raw / 10.0),
        )

        for row in (
            self._row_name, self._row_source, self._row_duration,
            self._row_position, self._row_fade_in, self._row_fade_out,
            self._row_volume, self._row_speed,
        ):
            rows.addWidget(row)
        # No internal stretch — rows hug the top so the NodeGraph
        # area below gets the lion's share of vertical space.
        # ``stretch=0`` on the root keeps the rows compact.
        root.addWidget(self._rows_host)

        # ---- NodeGraph section (Phase 2A) ----
        # The DaVinci-style node graph editor lives here as the
        # workbench's *primary* content. Properties rows above act as
        # the "metadata header"; the node graph gets the bulk of the
        # vertical real estate (``stretch=1``). Section header + ⛶
        # popout button live INSIDE the NodeGraphWidget so the panel
        # stays self-contained when reparented to the popout window.
        from app.workbench.node_graph.widget import NodeGraphWidget
        self._node_graph_widget = NodeGraphWidget()
        self._node_graph_widget.popout_requested.connect(
            self._toggle_node_graph_popout,
        )
        self._node_graph_widget.node_selection_changed.connect(
            self._on_node_graph_selection_changed,
        )
        # Hidden until the user selects a video track — audio clips
        # don't carry a node graph yet (Phase 2D+).
        self._node_graph_widget.hide()
        root.addWidget(self._node_graph_widget, stretch=1)
        # Popout state. Same pattern as Media Pool / Effects Library
        # popouts — ``_node_graph_root_layout`` is the layout we
        # reparent the widget out of and back into.
        self._node_graph_root_layout = root
        self._node_graph_popout = None
        self._node_graph_placeholder = None

    # ---- public API ----

    def set_blur_node(self, blur_node, on_change=None) -> None:
        """Show the blur controls section for the given BlurNodeItem.
        Called by the editor when a blur node is selected.
        ``on_change`` is called after any param change (triggers
        _rebuild_active_chain + preview refresh)."""
        if not hasattr(self, "_blur_section"):
            self._build_blur_section()
        if blur_node is None:
            self._blur_section.hide()
            return
        self._blur_node_ref = blur_node
        self._blur_on_change = on_change
        self._sync_blur_controls()
        self._blur_section.show()

    def _build_blur_section(self) -> None:
        """Lazily build the blur parameter controls and insert them
        just below the NodeGraph widget in the workbench layout."""
        from PySide6.QtWidgets import (
            QCheckBox, QComboBox, QHBoxLayout, QLabel,
            QSlider, QVBoxLayout, QWidget,
        )
        from PySide6.QtCore import Qt
        self._blur_section = QWidget()
        self._blur_section.setStyleSheet(
            "background-color: #1e3a4f; border-top: 1px solid #2a5a70;"
        )
        lay = QVBoxLayout(self._blur_section)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(6)
        title = QLabel("🔵 Blur — Out-of-Focus")
        title.setStyleSheet("color:#7dd4f0; font-size:11px; font-weight:700;")
        lay.addWidget(title)

        # Shape selector
        shape_row = QHBoxLayout()
        shape_row.addWidget(QLabel("Shape"))
        self._blur_shape_cb = QComboBox()
        self._blur_shape_cb.addItems(["Circle (Bokeh)", "Hexagon (Aperture)", "Gaussian (Soft)"])
        self._blur_shape_cb.setStyleSheet(
            "background:#1a1a1a; color:#ccc; border:1px solid #333; padding:2px;"
        )
        shape_row.addWidget(self._blur_shape_cb, stretch=1)
        lay.addLayout(shape_row)

        # Radius slider
        r_row = QHBoxLayout()
        r_row.addWidget(QLabel("Radius"))
        self._blur_radius_sld = QSlider(Qt.Orientation.Horizontal)
        self._blur_radius_sld.setRange(1, 50)
        self._blur_radius_sld.setValue(15)
        r_row.addWidget(self._blur_radius_sld, stretch=1)
        self._blur_radius_lbl = QLabel("15")
        self._blur_radius_lbl.setFixedWidth(28)
        r_row.addWidget(self._blur_radius_lbl)
        lay.addLayout(r_row)

        # Strength slider
        s_row = QHBoxLayout()
        s_row.addWidget(QLabel("Strength"))
        self._blur_strength_sld = QSlider(Qt.Orientation.Horizontal)
        self._blur_strength_sld.setRange(0, 100)
        self._blur_strength_sld.setValue(100)
        s_row.addWidget(self._blur_strength_sld, stretch=1)
        self._blur_strength_lbl = QLabel("100%")
        self._blur_strength_lbl.setFixedWidth(36)
        s_row.addWidget(self._blur_strength_lbl)
        lay.addLayout(s_row)

        # Mask inversion toggle
        self._blur_invert_chk = QCheckBox("Invert mask (background blur)")
        self._blur_invert_chk.setChecked(True)
        self._blur_invert_chk.setStyleSheet("color:#aaa; font-size:11px;")
        lay.addWidget(self._blur_invert_chk)

        # Main area-selection button (opens large canvas)
        from PySide6.QtWidgets import QPushButton
        select_btn = QPushButton("🎯 영역 선택... (큰 화면)")
        select_btn.setObjectName("ToolButton")
        select_btn.setToolTip("큰 캔버스에서 폴리곤/사각형/클릭으로 선택 → 추적")
        select_btn.clicked.connect(self._on_blur_select_area)
        lay.addWidget(select_btn)

        # Track checkbox
        self._blur_track_chk = QCheckBox("추적 (Track object through clip)")
        self._blur_track_chk.setChecked(True)
        self._blur_track_chk.setStyleSheet("color:#aaa; font-size:11px;")
        lay.addWidget(self._blur_track_chk)

        # Person-Follow shortcut
        person_btn = QPushButton("👤 인물 자동 선택 + 배경 블러")
        person_btn.setObjectName("ToolButton")
        person_btn.clicked.connect(self._on_blur_person_follow)
        lay.addWidget(person_btn)

        # Wire signals
        self._blur_shape_cb.currentIndexChanged.connect(self._on_blur_changed)
        self._blur_radius_sld.valueChanged.connect(self._on_blur_changed)
        self._blur_strength_sld.valueChanged.connect(self._on_blur_changed)
        self._blur_invert_chk.toggled.connect(self._on_blur_changed)

        # Insert into workbench below NodeGraph
        root_lay = self.layout()
        if root_lay is not None:
            root_lay.addWidget(self._blur_section)
        self._blur_section.hide()
        self._blur_node_ref = None
        self._blur_on_change = None

    def _sync_blur_controls(self) -> None:
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        from app.blur_params import BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON
        bp = node.blur_params
        shape_idx = {BLUR_SHAPE_CIRCLE: 0, BLUR_SHAPE_HEXAGON: 1}.get(bp.shape, 2)
        self._blur_shape_cb.blockSignals(True)
        self._blur_shape_cb.setCurrentIndex(shape_idx)
        self._blur_shape_cb.blockSignals(False)
        self._blur_radius_sld.blockSignals(True)
        self._blur_radius_sld.setValue(int(bp.radius))
        self._blur_radius_sld.blockSignals(False)
        self._blur_radius_lbl.setText(str(int(bp.radius)))
        self._blur_strength_sld.blockSignals(True)
        self._blur_strength_sld.setValue(int(bp.strength * 100))
        self._blur_strength_sld.blockSignals(False)
        self._blur_strength_lbl.setText(f"{int(bp.strength*100)}%")
        self._blur_invert_chk.blockSignals(True)
        self._blur_invert_chk.setChecked(bool(node.blur_invert_mask))
        self._blur_invert_chk.blockSignals(False)

    def _on_blur_changed(self, *_args) -> None:
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        from app.blur_params import (
            BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON, BLUR_SHAPE_GAUSSIAN,
        )
        shapes = [BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON, BLUR_SHAPE_GAUSSIAN]
        bp = node.blur_params
        bp.shape = shapes[self._blur_shape_cb.currentIndex()]
        bp.radius = int(self._blur_radius_sld.value())
        self._blur_radius_lbl.setText(str(bp.radius))
        bp.strength = self._blur_strength_sld.value() / 100.0
        self._blur_strength_lbl.setText(f"{int(bp.strength*100)}%")
        node.blur_invert_mask = bool(self._blur_invert_chk.isChecked())
        node.update()
        if self._blur_on_change:
            try:
                self._blur_on_change()
            except Exception:
                pass

    def _on_blur_select_area(self) -> None:
        """Open MaskEditorWindow (large canvas) so the user can
        draw a polygon, rect or click-to-select the subject.
        On OK, attach the resulting mask + optional tracker to the
        active blur node.  Invert setting determines whether the
        SELECTED area stays sharp (invert=True) or gets blurred."""
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        # Get the current preview frame from the editor.
        editor = self.window()
        rgb = None
        if editor is not None:
            try:
                rgb = editor._current_preview_rgb()
            except Exception:
                pass
        if rgb is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "영역 선택",
                "프리뷰 프레임이 없습니다.\n영상을 드롭하고 플레이헤드를 영상 위에 놓아주세요.",
            )
            return
        from app.mask_editor_window import MaskEditorWindow
        track = bool(getattr(self, "_blur_track_chk", None)
                     and self._blur_track_chk.isChecked())
        dlg = MaskEditorWindow.open_for_node(
            rgb, node,
            on_commit=self._blur_on_change,
            parent=self,
        )
        # Override the commit logic to use BitmapMask + optional
        # MaskTracker instead of attaching to node.color_grade.
        def _on_accept():
            mask_arr = dlg._canvas.current_mask()
            if mask_arr is None and len(dlg._canvas.current_polygon_points()) >= 3:
                mask_arr = dlg._canvas._eval_polygon_mask()
            if mask_arr is None:
                return
            from app.node_mask import BitmapMask, PowerWindow
            tool = dlg._canvas._tool
            softness = dlg._softness_sld.value() / 1000.0
            invert = dlg._invert_chk.isChecked()
            if tool == "polygon":
                pts = dlg._canvas.current_polygon_points()
                m = PowerWindow(points=pts, softness_norm=softness,
                                invert=invert)
                if track:
                    # Wrap in a tracker: use BitmapMask with track_object
                    bm = BitmapMask(softness_norm=softness, invert=invert,
                                    track_object=True)
                    bm.set_from_array(mask_arr)
                    node.masks = [bm]
                else:
                    node.masks = [m]
            else:
                bm = BitmapMask(softness_norm=softness, invert=invert,
                                track_object=track)
                bm.set_from_array(mask_arr)
                node.masks = [bm]
            # Invert mask = selected area stays sharp, rest blurs.
            node.blur_invert_mask = invert
            self._blur_invert_chk.setChecked(invert)
            node.update()
            if self._blur_on_change:
                try:
                    self._blur_on_change()
                except Exception:
                    pass

        dlg.accepted.connect(_on_accept)
        dlg.exec()

    def _on_blur_person_follow(self) -> None:
        """One-click: add MagicMask(person) + MaskTracker to the
        active blur node so it automatically tracks the person through
        the clip and blurs the background."""
        node = getattr(self, "_blur_node_ref", None)
        if node is None:
            return
        from app.node_mask import MagicMask, MaskTracker
        node.masks = [MagicMask(feature="person")]
        node.blur_invert_mask = True  # background blur
        self._blur_invert_chk.setChecked(True)
        node.update()
        if self._blur_on_change:
            try:
                self._blur_on_change()
            except Exception:
                pass

    def set_node_thumbnail(self, pix) -> None:
        """Forward the editor's current preview frame to the
        NodeGraph so every node renders a DaVinci-style live
        thumbnail. Throttling lives in the editor — this call is
        just a scale + setattr per node."""
        if hasattr(self, "_node_graph_widget"):
            self._node_graph_widget.set_source_pixmap(pix)

    def selected_node(self):
        """Return the currently-selected NodeItem (or None) so the
        editor can route the Color panel to that node's grade."""
        if not hasattr(self, "_node_graph_widget"):
            return None
        items = self._node_graph_widget.scene.selectedItems()
        from app.workbench.node_graph.items.node_item import NodeItem
        for it in items:
            if isinstance(it, NodeItem):
                return it
        return None

    def primary_node(self):
        """Return the first Serial node (the default Node 1) so the
        editor has a sensible grade target before the user clicks
        anything. None when the graph is empty."""
        if not hasattr(self, "_node_graph_widget"):
            return None
        nodes = self._node_graph_widget.scene._serial_nodes
        from app.workbench.node_graph.items.node_item import NodeItem
        for n in nodes:
            if isinstance(n, NodeItem):
                return n
        return None

    def expose_node_graph_widget(self):
        """Allow the editor to wire signals (selected_node_changed)
        without importing NodeGraphWidget. Returns the widget or None."""
        return getattr(self, "_node_graph_widget", None)

    def clear(self) -> None:
        self._target = None
        self._title.setText(tr("workbench.empty.title"))
        self._subtitle.setText(tr("workbench.empty.subtitle"))
        self._subtitle.show()
        for row in (
            self._row_name, self._row_source, self._row_duration,
            self._row_position, self._row_speed,
        ):
            row.set_value("—")
            row.show()
        # Slider rows: zero them out and disable to make "no target"
        # state explicit.
        for srow in (self._row_fade_in, self._row_fade_out, self._row_volume):
            srow.set_value(0)
            srow.set_enabled(False)
            srow.show()
        self._node_graph_widget.hide()

    def set_video_track(self, track) -> None:
        if track is None:
            self.clear()
            return
        self._target = ("video", track)
        self._title.setText(tr("workbench.video_track.title"))
        self._subtitle.hide()
        src = getattr(track, "source_path", None)
        name = basename(str(src)) if src else "—"
        self._row_name.set_value(name)
        self._row_source.set_value(str(src) if src else "—")
        self._row_duration.set_value(_format_ms(getattr(track, "duration_ms", 0)))
        offset_ms = int(getattr(track, "offset_ms", 0))
        self._row_position.set_value(_format_ms(offset_ms))
        # Video tracks model fades as a FadeSegment list. The
        # workbench treats a leading ``kind="in"`` segment at offset 0
        # as the fade-in and a trailing ``kind="out"`` segment ending
        # at duration as the fade-out. Slider edits push back through
        # the editor's ``_on_workbench_fade_*_changed`` handlers,
        # which create / update / remove these segments.
        fi_ms, fo_ms = self._derive_video_fades(track)
        self._row_fade_in.set_value(min(fi_ms, self.FADE_MAX_MS))
        self._row_fade_out.set_value(min(fo_ms, self.FADE_MAX_MS))
        self._row_fade_in.set_enabled(True)
        self._row_fade_out.set_enabled(True)
        self._row_fade_in.show()
        self._row_fade_out.show()
        # Video tracks don't carry a per-clip volume; hide that row.
        self._row_volume.hide()
        segs = getattr(track, "speed_segments", []) or []
        if segs:
            self._row_speed.set_value(
                tr("workbench.value.speed_segments", count=len(segs))
            )
        else:
            self._row_speed.set_value("1.00×")
        self._rows_host.show()

        # NodeGraph section is the workbench's *primary* content for
        # video tracks. Phase 2D: bind the widget to this track so its
        # scene state lives on ``track.node_graph_view_data``.
        self._node_graph_widget.set_track(track)
        self._node_graph_widget.show()

    def set_audio_clip(self, track, clip) -> None:
        if clip is None:
            self.clear()
            return
        self._target = ("audio", track, clip)
        self._title.setText(tr("workbench.audio_clip.title"))
        self._subtitle.hide()
        src = getattr(clip, "source_path", None)
        name = (
            getattr(clip, "display_name", None)
            or (basename(str(src)) if src else "—")
        )
        self._row_name.set_value(name)
        self._row_source.set_value(str(src) if src else "—")
        self._row_duration.set_value(_format_ms(getattr(clip, "duration_ms", 0)))
        self._row_position.set_value(_format_ms(int(getattr(clip, "offset_ms", 0))))
        fi = int(getattr(clip, "fade_in_ms", 0))
        fo = int(getattr(clip, "fade_out_ms", 0))
        self._row_fade_in.set_value(min(fi, self.FADE_MAX_MS))
        self._row_fade_out.set_value(min(fo, self.FADE_MAX_MS))
        self._row_fade_in.set_enabled(True)
        self._row_fade_out.set_enabled(True)
        self._row_fade_in.show()
        self._row_fade_out.show()
        # Volume slider — int tenths of dB.
        vol_db = float(getattr(track, "master_volume", 0.0) or 0.0)
        clamped = max(self.VOLUME_MIN_DB, min(self.VOLUME_MAX_DB, vol_db))
        self._row_volume.set_value(int(round(clamped * 10)))
        self._row_volume.set_enabled(True)
        self._row_volume.show()
        speed = float(getattr(clip, "speed", 1.0))
        self._row_speed.set_value(f"{speed:.2f}×")
        self._rows_host.show()
        # Audio clips don't carry a NodeGraph yet — hide the section.
        self._node_graph_widget.hide()

    def current_target(self) -> tuple | None:
        """Return the editor-side identifier for the currently
        displayed selection. Used by the editor to route slider
        signals to the right object."""
        return self._target

    def _derive_video_fades(self, track) -> tuple[int, int]:
        """Best-effort fade-in / fade-out duration extraction from a
        video track's ``FadeSegment`` list. Returns ``(in_ms, out_ms)``.
        A FadeSegment is treated as the leading fade if it starts at
        ms 0 and its kind is in / both, and as the trailing fade if it
        ends within ~100 ms of the track duration."""
        fades = getattr(track, "fades", []) or []
        dur = int(getattr(track, "duration_ms", 0) or 0)
        in_ms = 0
        out_ms = 0
        for f in fades:
            start = int(getattr(f, "start_ms", -1) or 0)
            end = int(getattr(f, "end_ms", -1) or 0)
            kind = getattr(f, "kind", "both")
            length = max(0, end - start)
            if start <= 0 and kind in ("in", "both"):
                in_ms = max(in_ms, length)
            if dur > 0 and end >= dur - 100 and kind in ("out", "both"):
                out_ms = max(out_ms, length)
        return in_ms, out_ms

    # ---- i18n ----

    def retranslate(self) -> None:
        self._title.setText(tr("workbench.empty.title"))
        self._subtitle.setText(tr("workbench.empty.subtitle"))
        self._row_name.set_label(tr("workbench.row.name"))
        self._row_source.set_label(tr("workbench.row.source"))
        self._row_duration.set_label(tr("workbench.row.duration"))
        self._row_position.set_label(tr("workbench.row.position"))
        self._row_fade_in.set_label(tr("workbench.row.fade_in"))
        self._row_fade_out.set_label(tr("workbench.row.fade_out"))
        self._row_volume.set_label(tr("workbench.row.volume"))
        self._row_speed.set_label(tr("workbench.row.speed"))
        self._node_graph_widget.retranslate()

    # ---- NodeGraph popout (Phase 2A) ----

    def _on_node_graph_selection_changed(self, label: str) -> None:
        """Bubble selection to the legacy ``node_focused`` signal so
        editor-side hooks (color popout routing) stay live. Empty
        label means nothing is selected."""
        if label and "Color" in label:
            self.node_focused.emit("color")

    def _toggle_node_graph_popout(self) -> None:
        if (
            self._node_graph_popout is not None
            and self._node_graph_popout.isVisible()
        ):
            self._node_graph_popout.close()
            return
        from app.workbench.node_graph.popout import NodeGraphPopoutWindow
        self._node_graph_popout = NodeGraphPopoutWindow(self)
        self._node_graph_popout.closed.connect(
            self._on_node_graph_popout_closed,
        )
        # Reparent the widget into the popout. Save the index so we
        # can re-insert at the same spot when the window closes.
        self._node_graph_popout_index = self._node_graph_root_layout.indexOf(
            self._node_graph_widget,
        )
        self._node_graph_root_layout.removeWidget(self._node_graph_widget)
        # Drop a placeholder so the dock layout doesn't collapse.
        self._node_graph_placeholder = QLabel(
            tr("workbench.node_graph_popout.placeholder"),
        )
        self._node_graph_placeholder.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )
        self._node_graph_placeholder.setMinimumHeight(80)
        self._node_graph_placeholder.setWordWrap(True)
        self._node_graph_placeholder.setStyleSheet(
            "color: #8a8a8a; font-style: italic; font-size: 11px; "
            "background-color: #15151a; border: 1px dashed #2a2a2a; "
            "border-radius: 4px; padding: 12px;"
        )
        self._node_graph_root_layout.insertWidget(
            self._node_graph_popout_index,
            self._node_graph_placeholder,
            stretch=1,
        )
        self._node_graph_popout.install(self._node_graph_widget)
        self._node_graph_popout.show()
        self._node_graph_popout.raise_()
        self._node_graph_popout.activateWindow()

    def _on_node_graph_popout_closed(self) -> None:
        if self._node_graph_placeholder is not None:
            idx = self._node_graph_root_layout.indexOf(
                self._node_graph_placeholder,
            )
            self._node_graph_root_layout.removeWidget(
                self._node_graph_placeholder,
            )
            self._node_graph_placeholder.deleteLater()
            self._node_graph_placeholder = None
        else:
            idx = self._node_graph_popout_index
        self._node_graph_widget.setParent(self)
        self._node_graph_root_layout.insertWidget(
            max(0, idx), self._node_graph_widget, stretch=1,
        )
        # Only reveal if a video track is currently selected — keeps
        # the panel hidden after re-dock when the user switched to an
        # audio clip while the popout was open.
        if self._target is not None and self._target[0] == "video":
            self._node_graph_widget.show()
        else:
            self._node_graph_widget.hide()
        if self._node_graph_popout is not None:
            self._node_graph_popout.deleteLater()
            self._node_graph_popout = None
