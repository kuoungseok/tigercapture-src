from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.drawing import DrawingCanvas
from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import COLOR_TEXT_TERTIARY
from app.video_editor_layout_specs import (
    TOP_WORK_MAX_HEIGHT,
    TOP_WORK_MIN_HEIGHT,
    VIEWER_COLUMN_MIN_WIDTH,
    VIEWER_TOP_STRETCH,
    WORKBENCH_SLOT_MIN_WIDTH,
    WORKBENCH_TOP_STRETCH,
    horizontal_tool_scroll_qss,
)
from app.video_editor_window_widgets import _PreviewSurfaceLabel


def build_preview_transport_area(self, main_col, root) -> None:
    self._top_work_area = QWidget(main_col)
    self._top_work_area.setObjectName("TopWorkArea")
    self._top_work_area.setMinimumHeight(TOP_WORK_MIN_HEIGHT)
    self._top_work_area.setMaximumHeight(TOP_WORK_MAX_HEIGHT)
    top_work_layout = QHBoxLayout(self._top_work_area)
    top_work_layout.setContentsMargins(0, 0, 0, 0)
    top_work_layout.setSpacing(5)
    self._top_work_layout = top_work_layout
    root.addWidget(self._top_work_area, stretch=0)

    self._viewer_column = QWidget(self._top_work_area)
    self._viewer_column.setObjectName("ViewerColumn")
    self._viewer_column.setMinimumWidth(VIEWER_COLUMN_MIN_WIDTH)
    self._viewer_column.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    viewer_column_layout = QVBoxLayout(self._viewer_column)
    viewer_column_layout.setContentsMargins(0, 0, 0, 0)
    viewer_column_layout.setSpacing(0)
    self._viewer_column_layout = viewer_column_layout
    top_work_layout.addWidget(
        self._viewer_column,
        stretch=VIEWER_TOP_STRETCH,
    )

    self._top_workbench_slot = QWidget(self._top_work_area)
    self._top_workbench_slot.setObjectName("TopWorkbenchSlot")
    self._top_workbench_slot.setMinimumWidth(WORKBENCH_SLOT_MIN_WIDTH)
    self._top_workbench_slot.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    top_workbench_layout = QVBoxLayout(self._top_workbench_slot)
    top_workbench_layout.setContentsMargins(0, 0, 0, 0)
    top_workbench_layout.setSpacing(0)
    self._top_workbench_layout = top_workbench_layout
    top_work_layout.addWidget(self._top_workbench_slot, stretch=WORKBENCH_TOP_STRETCH)

    self._viewer_project_breadcrumb_label = QLabel(self._viewer_column)
    self._viewer_project_breadcrumb_label.setObjectName("ViewerProjectBreadcrumb")
    self._viewer_project_breadcrumb_label.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    self._refresh_top_project_breadcrumb()
    viewer_column_layout.addWidget(self._viewer_project_breadcrumb_label)

    # --- Preview section ---
    # Custom header: section label on the left, pop-out icon on the
    # right. The container itself carries the accent bar + bg so the
    # row renders as one cohesive strip.
    preview_header = QWidget(self._viewer_column)
    preview_header.setObjectName("PreviewSectionHeader")
    pheader_layout = QHBoxLayout(preview_header)
    pheader_layout.setContentsMargins(0, 0, 8, 0)
    pheader_layout.setSpacing(0)
    self._preview_section_label = QLabel("Viewer", preview_header)
    self._preview_section_label.setObjectName("PreviewSectionTitle")
    pheader_layout.addWidget(self._preview_section_label, stretch=1)
    pheader_layout.addWidget(self.popout_btn)
    self.popout_btn.show()
    viewer_column_layout.addWidget(preview_header)
    preview_host = QWidget(self._viewer_column)
    preview_host.setObjectName("PreviewHost")
    preview_host.setMinimumHeight(270)
    preview_host.setMaximumHeight(380)
    preview_host.setAcceptDrops(True)
    preview_host.installEventFilter(self)
    preview_host.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
    )
    host_layout = QVBoxLayout(preview_host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(0)
    self._preview_label = _PreviewSurfaceLabel()
    self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._preview_label.setWordWrap(True)
    self._preview_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY};")
    self._preview_label.setSizePolicy(
        QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding
    )
    self._preview_label.setMinimumSize(0, 0)
    self._preview_label.setText(tr("veditor.no_file"))
    self._preview_placeholder_kind = "empty"
    self._preview_label.setCursor(Qt.CursorShape.PointingHandCursor)
    self._preview_label.setToolTip(tr("paint.hint"))
    self._preview_label.setAcceptDrops(True)
    self._preview_label.installEventFilter(self)
    self._preview_pixmap: QPixmap | None = None
    self._latest_preview_rgb = None
    host_layout.addWidget(self._preview_label)

    # GPU preview surface ??sits on top of the QLabel as a sibling
    # Deferred until the first real frame; eager QOpenGLWidget creation
    # creates transient Qt/NVIDIA helper windows during launcher startup.
    self._preview_gl = None
    # Track latest frame size for video-rect math when no QLabel
    # pixmap is available (during the brief moment between drop and
    # first frame).
    self._preview_gl_frame_size: tuple[int, int] = (0, 0)

    # Drawing canvas ??transparent overlay above the preview, below subtitles.
    # Stays in "off" tool mode so mouse events pass through to preview_label.
    self._drawing_canvas = DrawingCanvas(
        get_time_ms=lambda: self._player.position(),
        get_strokes=lambda: self._strokes,
        parent=preview_host,
    )
    try:
        self._drawing_canvas.set_extra_paint_hook(self._paint_preview_canvas_overlay)
    except Exception:
        pass

    # Subtitle overlay (child of preview host, positioned at bottom)
    self._subtitle_overlay = QLabel(preview_host)
    self._subtitle_overlay.setStyleSheet(
        "QLabel { color: white; "
        "background-color: rgba(0, 0, 0, 180); "
        "padding: 6px 14px; "
        "border-radius: 4px; "
        "font-size: 18px; "
        "font-weight: 600; }"
    )
    self._subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._subtitle_overlay.setWordWrap(True)
    self._subtitle_overlay.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    self._subtitle_overlay.hide()
    self._preview_host = preview_host

    viewer_column_layout.addWidget(preview_host, stretch=1)
    self._yield_startup_ui("preview_host")

    # --- Paint hint ---
    self._paint_hint_label = QLabel(tr("paint.hint"))
    self._paint_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._paint_hint_label.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; padding: 4px;"
    )
    root.addWidget(self._paint_hint_label)
    self._paint_hint_label.hide()

    # --- Play bar ---
    play_bar = QWidget()
    play_bar.setObjectName("PlayBar")
    transport = QHBoxLayout(play_bar)
    transport.setContentsMargins(8, 2, 8, 2)
    transport.setSpacing(5)
    self.play_btn = QPushButton("")
    self.play_btn.setObjectName("PlayButton")
    self.play_btn.setFixedSize(20, 20)
    self.play_btn.setIcon(app_icon("play", size=11, color="#D7DAE7"))
    self.play_btn.setIconSize(icon_size(11))
    self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._install_icon_pulse(self.play_btn, base=18, peak=25)
    self.play_btn.setToolTip("Play or pause preview")
    self.play_btn.clicked.connect(self._toggle_play)

    self.prev_frame_btn = QPushButton("")
    self.prev_frame_btn.setObjectName("ToolButton")
    self.prev_frame_btn.setProperty("transportAction", True)
    self.prev_frame_btn.setFixedSize(20, 20)
    self.prev_frame_btn.setIcon(app_icon("previous", size=11, color="#D7DAE7"))
    self.prev_frame_btn.setIconSize(icon_size(11))
    self.prev_frame_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.prev_frame_btn.setToolTip("Step back one frame")
    self._install_icon_pulse(self.prev_frame_btn, base=14, peak=19)
    self.prev_frame_btn.clicked.connect(lambda: self._step_timeline_frames(-1))

    self.stop_btn = QPushButton("")
    self.stop_btn.setObjectName("ToolButton")
    self.stop_btn.setProperty("transportAction", True)
    self.stop_btn.setFixedSize(20, 20)
    self.stop_btn.setIcon(app_icon("stop", size=10, color="#D7DAE7"))
    self.stop_btn.setIconSize(icon_size(10))
    self.stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.stop_btn.setToolTip("Stop playback")
    self._install_icon_pulse(self.stop_btn, base=13, peak=18)
    self.stop_btn.clicked.connect(self._stop_transport)

    self.next_frame_btn = QPushButton("")
    self.next_frame_btn.setObjectName("ToolButton")
    self.next_frame_btn.setProperty("transportAction", True)
    self.next_frame_btn.setFixedSize(20, 20)
    self.next_frame_btn.setIcon(app_icon("next", size=11, color="#D7DAE7"))
    self.next_frame_btn.setIconSize(icon_size(11))
    self.next_frame_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.next_frame_btn.setToolTip("Step forward one frame")
    self._install_icon_pulse(self.next_frame_btn, base=14, peak=19)
    self.next_frame_btn.clicked.connect(lambda: self._step_timeline_frames(1))

    self.time_label = QLabel("0:00 / 0:00")
    self.time_label.setObjectName("TimeLabel")

    self.current_speed_label = QPushButton("1.0x")
    self.current_speed_label.setObjectName("SpeedLabel")
    self.current_speed_label.setCursor(Qt.CursorShape.PointingHandCursor)
    self.current_speed_label.setFixedSize(42, 20)
    self.current_speed_label.setToolTip(tr("veditor.current_speed", speed="1.0"))
    self.current_speed_label.clicked.connect(self._show_viewer_speed_menu)

    self.viewer_compare_btn = QPushButton("Compare")
    self.viewer_compare_btn.setObjectName("ViewerDropdownButton")
    self.viewer_compare_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.viewer_compare_btn.setFixedSize(70, 20)
    self.viewer_compare_btn.setToolTip("Comparison Templates")
    self.viewer_compare_btn.clicked.connect(self._show_viewer_compare_menu)

    self.viewer_fit_btn = QPushButton("Fit")
    self.viewer_fit_btn.setObjectName("ViewerDropdownButton")
    self.viewer_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.viewer_fit_btn.setFixedSize(38, 20)
    self.viewer_fit_btn.setToolTip("Fit frame to viewer")
    self.viewer_fit_btn.clicked.connect(lambda _checked=False: self._scale_preview_to_fit())

    # Mark In / Mark Out / Clear selection ??prosumer-editor style
    # range selection tied to the playhead. Tracks can still be
    # shift+dragged directly, but the buttons + I/O shortcuts are
    # the primary path now.
    self.mark_in_btn = QPushButton("")
    self.mark_in_btn.setObjectName("ToolButton")
    self.mark_in_btn.setProperty("transportAction", True)
    self.mark_in_btn.setFixedSize(42, 36)
    self.mark_in_btn.setIcon(app_icon("mark-in", size=16, color="#D7DAE7"))
    self.mark_in_btn.setIconSize(icon_size(16))
    self.mark_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.mark_in_btn.setToolTip(tr("veditor.mark_in.tooltip"))
    self._install_icon_pulse(self.mark_in_btn, base=16, peak=22)
    self.mark_in_btn.clicked.connect(self._mark_in_at_playhead)

    self.mark_out_btn = QPushButton("")
    self.mark_out_btn.setObjectName("ToolButton")
    self.mark_out_btn.setProperty("transportAction", True)
    self.mark_out_btn.setFixedSize(42, 36)
    self.mark_out_btn.setIcon(app_icon("mark-out", size=16, color="#D7DAE7"))
    self.mark_out_btn.setIconSize(icon_size(16))
    self.mark_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.mark_out_btn.setToolTip(tr("veditor.mark_out.tooltip"))
    self._install_icon_pulse(self.mark_out_btn, base=16, peak=22)
    self.mark_out_btn.clicked.connect(self._mark_out_at_playhead)

    self.clear_range_btn = QPushButton("")
    self.clear_range_btn.setObjectName("ToolButton")
    self.clear_range_btn.setProperty("transportAction", True)
    self.clear_range_btn.setFixedSize(42, 36)
    self.clear_range_btn.setIcon(app_icon("x", size=15, color="#D7DAE7"))
    self.clear_range_btn.setIconSize(icon_size(15))
    self.clear_range_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.clear_range_btn.setToolTip(tr("veditor.clear_sel.tooltip"))
    self._install_icon_pulse(self.clear_range_btn, base=15, peak=21)
    self.clear_range_btn.clicked.connect(self._clear_active_selection)

    self.add_marker_btn = QPushButton("")
    self.add_marker_btn.setObjectName("ToolButton")
    self.add_marker_btn.setProperty("transportAction", True)
    self.add_marker_btn.setFixedSize(42, 36)
    self.add_marker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.add_marker_btn.setToolTip("?뚮젅?댄뿤???꾩튂????꾨씪??留덉빱 異붽? (M)")
    self.add_marker_btn.setToolTip("Add marker at the playhead (M)")
    self.add_marker_btn.setIcon(app_icon("marker", size=16, color="#F3F5F8"))
    self.add_marker_btn.setIconSize(icon_size(16))
    self._install_icon_pulse(self.add_marker_btn, base=16, peak=22)
    self.add_marker_btn.clicked.connect(self._add_marker_at_playhead)

    transport.addWidget(self.time_label)
    transport.addStretch(1)
    transport.addWidget(self.prev_frame_btn)
    transport.addWidget(self.play_btn)
    transport.addWidget(self.stop_btn)
    transport.addWidget(self.next_frame_btn)
    transport.addStretch(1)
    transport.addWidget(self.mark_in_btn)
    transport.addWidget(self.mark_out_btn)
    transport.addWidget(self.clear_range_btn)
    transport.addSpacing(4)
    transport.addWidget(self.add_marker_btn)
    self.mark_in_btn.hide()
    self.mark_out_btn.hide()
    self.clear_range_btn.hide()
    self.add_marker_btn.hide()
    # Phase 7: mini Sony PVW-2800-style jog/shuttle. Inner ring
    # scrubs frame-by-frame; outer ring sets play rate. Sits in
    # the play bar between the speed label and the right edge so
    # it's discoverable without dominating the layout.
    from app.jog_shuttle import JogShuttleWidget
    self._jog_shuttle = JogShuttleWidget(size=44)
    self._jog_shuttle.setToolTip(tr("veditor.jog_shuttle.tooltip"))
    self._jog_shuttle.jog_delta.connect(self._on_jog_delta)
    self._jog_shuttle.shuttle_speed_changed.connect(
        self._on_shuttle_speed_changed,
    )
    transport.addWidget(self._jog_shuttle)
    self._jog_shuttle.hide()
    transport.addSpacing(4)
    transport.addWidget(self.viewer_compare_btn)
    transport.addWidget(self.viewer_fit_btn)
    transport.addWidget(self.current_speed_label)
    play_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self._play_bar_scroll = QScrollArea(self._viewer_column)
    self._play_bar_scroll.setObjectName("PlayBarScroll")
    self._play_bar_scroll.setWidget(play_bar)
    self._play_bar_scroll.setWidgetResizable(True)
    self._play_bar_scroll.setFrameShape(QFrame.Shape.NoFrame)
    self._play_bar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._play_bar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    self._play_bar_scroll.setMinimumHeight(32)
    self._play_bar_scroll.setMaximumHeight(36)
    self._play_bar_scroll.setStyleSheet(horizontal_tool_scroll_qss("QScrollArea#PlayBarScroll"))
    viewer_column_layout.addWidget(self._play_bar_scroll)

    # --- Keyboard shortcuts for selection ---
    from PySide6.QtGui import QKeySequence, QShortcut
    self._sc_mark_in = QShortcut(QKeySequence("I"), self)
    self._sc_mark_in.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_mark_in.activated.connect(self._mark_in_at_playhead)
    self._sc_mark_out = QShortcut(QKeySequence("O"), self)
    self._sc_mark_out.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_mark_out.activated.connect(self._mark_out_at_playhead)
    self._sc_clear_sel = QShortcut(QKeySequence("X"), self)
    self._sc_clear_sel.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_clear_sel.activated.connect(self._clear_active_selection)
    # M: add a timeline marker at the current playhead position.
    self._sc_add_marker = QShortcut(QKeySequence("M"), self)
    self._sc_add_marker.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_add_marker.activated.connect(self._add_marker_at_playhead)
    # Undo / redo ??10 levels (see app/history.py).
    self._sc_undo = QShortcut(QKeySequence.StandardKey.Undo, self)
    self._sc_undo.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_undo.activated.connect(self._on_undo)
    self._sc_redo = QShortcut(QKeySequence.StandardKey.Redo, self)
    self._sc_redo.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_redo.activated.connect(self._on_redo)
    # Ctrl+Y is the historical Windows redo binding; bind it
    # alongside the StandardKey.Redo (Ctrl+Shift+Z) for parity.
    self._sc_redo_y = QShortcut(QKeySequence("Ctrl+Y"), self)
    self._sc_redo_y.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_redo_y.activated.connect(self._on_redo)
    # Project Save / Load shortcuts
    self._sc_new = QShortcut(QKeySequence("Ctrl+N"), self)
    self._sc_new.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_new.activated.connect(self._on_new_project)
    self._sc_save = QShortcut(QKeySequence("Ctrl+S"), self)
    self._sc_save.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_save.activated.connect(self._on_save_project)
    self._sc_open = QShortcut(QKeySequence("Ctrl+O"), self)
    self._sc_open.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_open.activated.connect(self._on_open_project)
    self._sc_command_palette = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
    self._sc_command_palette.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_command_palette.activated.connect(self._open_command_palette)
    # Option C ??industry-standard editing shortcuts.
    # B / C: Blade at playhead (DaVinci / Premiere convention).
    self._sc_blade_b = QShortcut(QKeySequence("B"), self)
    self._sc_blade_b.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_blade_b.activated.connect(lambda: self._set_timeline_tool_mode("blade"))
    self._sc_blade_c = QShortcut(QKeySequence("C"), self)
    self._sc_blade_c.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_blade_c.activated.connect(self._blade_at_playhead)
    for seq, mode in (
        ("V", "select"),
        ("R", "ripple"),
        ("N", "roll"),
        ("Y", "slip"),
        ("U", "slide"),
    ):
        sc = QShortcut(QKeySequence(seq), self)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(lambda m=mode: self._set_timeline_tool_mode(m))
        setattr(self, f"_sc_tool_{mode}", sc)
    # Ctrl+K (Premiere "Add Edit") + Ctrl+\ (DaVinci "Split").
    self._sc_blade_ctrl_k = QShortcut(QKeySequence("Ctrl+K"), self)
    self._sc_blade_ctrl_k.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_blade_ctrl_k.activated.connect(self._blade_at_playhead)
    self._sc_blade_ctrl_bs = QShortcut(QKeySequence("Ctrl+\\"), self)
    self._sc_blade_ctrl_bs.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_blade_ctrl_bs.activated.connect(self._blade_at_playhead)
    # Delete = ripple-delete the selected clip(s). Backspace too
    # so trackpad-only users on Mac-style keyboards can reach it.
    self._sc_clip_delete = QShortcut(QKeySequence("Delete"), self)
    self._sc_clip_delete.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_clip_delete.activated.connect(self._ripple_delete_selected)
    self._sc_clip_backspace = QShortcut(QKeySequence("Backspace"), self)
    self._sc_clip_backspace.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_clip_backspace.activated.connect(self._ripple_delete_selected)
    self._sc_precision_trim = QShortcut(QKeySequence("Ctrl+Alt+T"), self)
    self._sc_precision_trim.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_precision_trim.activated.connect(self._open_precision_trim_dialog)
    # Timeline zoom shortcuts: match common NLE/browser muscle memory.
    self._sc_timeline_zoom_in_eq = QShortcut(QKeySequence("Ctrl+="), self)
    self._sc_timeline_zoom_in_eq.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_timeline_zoom_in_eq.activated.connect(self._shortcut_zoom_in)
    self._sc_timeline_zoom_in_plus = QShortcut(QKeySequence("Ctrl++"), self)
    self._sc_timeline_zoom_in_plus.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_timeline_zoom_in_plus.activated.connect(self._shortcut_zoom_in)
    self._sc_timeline_zoom_out = QShortcut(QKeySequence("Ctrl+-"), self)
    self._sc_timeline_zoom_out.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_timeline_zoom_out.activated.connect(self._shortcut_zoom_out)
    self._sc_timeline_zoom_fit = QShortcut(QKeySequence("Ctrl+0"), self)
    self._sc_timeline_zoom_fit.setContext(Qt.ShortcutContext.WindowShortcut)
    self._sc_timeline_zoom_fit.activated.connect(self._shortcut_zoom_fit)
    self._yield_startup_ui("transport_shortcuts")
