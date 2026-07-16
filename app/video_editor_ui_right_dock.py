from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size, unreal_engine_icon
from app.studio_slider import StudioSlider
from app.style import COLOR_TEXT_TERTIARY
from app.video_editor_lazy_panel import LazyPanelHost
from app.video_editor_layout_specs import (
    RIGHT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH,
    RIGHT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
    TOP_WORK_MIN_HEIGHT,
    right_dock_sections_splitter_qss,
)
from app.video_editor_workbench_section_scroll import make_workbench_section_scroll_area
from app.subtitles import SubtitleLaneRow, SubtitlePanel
from app.workbench_panel import WorkbenchPanel


_WORKBENCH_MAIN_MIN_HEIGHT = max(500, TOP_WORK_MIN_HEIGHT + 90)
_CREATOR_TOOLS_CLOSED_HEIGHT = 146
_WORKBENCH_SECTION_CLOSED_HEIGHT = 51
_WORKBENCH_TOOLS_OPEN_HEIGHT = 320
_WORKBENCH_TOOLS_SHORT_OPEN_HEIGHT = 154
_WORKBENCH_LONG_PANEL_CONTENT_HEIGHT = 440


def _editor_settings() -> QSettings:
    return QSettings("TigerCapture", "TigerCapture")


def _restore_right_dock_sections_splitter_state(splitter: QSplitter) -> bool:
    try:
        state = _editor_settings().value(RIGHT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY)
    except Exception:
        return False
    if state is None:
        return False
    if isinstance(state, QByteArray):
        if state.isEmpty():
            return False
    elif isinstance(state, (bytes, bytearray)):
        state = QByteArray(bytes(state))
    else:
        return False
    try:
        return bool(splitter.restoreState(state))
    except Exception:
        return False


def _save_right_dock_sections_splitter_state(owner) -> None:
    splitter = getattr(owner, "_right_dock_sections_splitter", None)
    if splitter is None:
        return
    try:
        _editor_settings().setValue(
            RIGHT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
            splitter.saveState(),
        )
    except Exception:
        pass


def _refresh_right_secondary_sections_height(owner) -> None:
    host = getattr(owner, "_right_secondary_sections_host", None)
    layout = getattr(owner, "_right_secondary_sections_layout", None)
    splitter = getattr(owner, "_right_dock_sections_splitter", None)
    workbench_host = getattr(owner, "_workbench_section_host", None)
    if host is None or layout is None:
        return

    total = 0
    visible_widgets = 0
    try:
        margins = layout.contentsMargins()
        total += int(margins.top()) + int(margins.bottom())
    except Exception:
        pass

    for idx in range(layout.count()):
        item = layout.itemAt(idx)
        widget = item.widget() if item is not None else None
        if widget is None or not widget.isVisible():
            continue
        visible_widgets += 1
        try:
            hint = int(widget.sizeHint().height() or 0)
        except Exception:
            hint = 0
        try:
            minimum = int(widget.minimumHeight() or 0)
        except Exception:
            minimum = 0
        try:
            current = int(widget.height() or 0)
        except Exception:
            current = 0
        total += max(minimum, hint, current, 38)

    try:
        total += max(0, int(layout.spacing())) * max(0, visible_widgets - 1)
    except Exception:
        pass

    total = max(190, total)
    try:
        host.setMinimumHeight(total)
        host.updateGeometry()
    except Exception:
        pass

    if splitter is None:
        return
    try:
        workbench_min = int(workbench_host.minimumHeight() if workbench_host is not None else 0)
    except Exception:
        workbench_min = 0
    try:
        handle = int(splitter.handleWidth() or 0)
    except Exception:
        handle = 0
    try:
        splitter.setMinimumHeight(max(splitter.minimumHeight(), workbench_min + total + handle + 8))
        sizes = list(splitter.sizes())
        if len(sizes) >= 2 and sizes[1] < total:
            splitter.setSizes([max(workbench_min, sizes[0]), max(total, sizes[1])])
        splitter.updateGeometry()
    except Exception:
        pass


def _wire_right_secondary_section_height_refresh(owner) -> None:
    host = getattr(owner, "_right_secondary_sections_host", None)
    if host is None:
        return
    for button in host.findChildren(QPushButton, "SectionDisclosure"):
        button.toggled.connect(
            lambda _checked=False, _owner=owner: QTimer.singleShot(
                0,
                lambda: _refresh_right_secondary_sections_height(_owner),
            )
        )
    QTimer.singleShot(0, lambda: _refresh_right_secondary_sections_height(owner))


def build_right_dock_sections(self) -> None:
    prebuilt_ai_command_section = getattr(self, "_ai_command_section_host", None)
    if prebuilt_ai_command_section is not None:
        try:
            idx = self._right_dock_layout.indexOf(prebuilt_ai_command_section)
            if idx >= 0:
                self._right_dock_layout.removeWidget(prebuilt_ai_command_section)
                prebuilt_ai_command_section.setParent(None)
        except Exception:
            pass

    self._right_dock_sections_splitter = QSplitter(
        Qt.Orientation.Vertical,
        self._right_dock_host,
    )
    self._right_dock_sections_splitter.setObjectName("RightDockSectionsSplitter")
    self._right_dock_sections_splitter.setChildrenCollapsible(False)
    self._right_dock_sections_splitter.setHandleWidth(
        RIGHT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH,
    )
    self._right_dock_sections_splitter.setStyleSheet(
        right_dock_sections_splitter_qss(),
    )
    self._right_dock_sections_splitter.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    self._right_dock_layout.addWidget(self._right_dock_sections_splitter, stretch=1)

    self._right_workbench_pane = QWidget(self._right_dock_sections_splitter)
    self._right_workbench_pane.setObjectName("RightWorkbenchPane")
    self._right_workbench_pane.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    self._right_workbench_pane_layout = QVBoxLayout(self._right_workbench_pane)
    self._right_workbench_pane_layout.setContentsMargins(0, 0, 0, 0)
    self._right_workbench_pane_layout.setSpacing(0)

    self._right_secondary_sections_host = QWidget(self._right_dock_sections_splitter)
    self._right_secondary_sections_host.setObjectName("RightSecondarySectionsHost")
    self._right_secondary_sections_host.setMinimumHeight(190)
    self._right_secondary_sections_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    self._right_secondary_sections_layout = QVBoxLayout(
        self._right_secondary_sections_host,
    )
    self._right_secondary_sections_layout.setContentsMargins(0, 0, 0, 0)
    self._right_secondary_sections_layout.setSpacing(2)

    self._right_dock_sections_splitter.addWidget(self._right_workbench_pane)
    self._right_dock_sections_splitter.addWidget(self._right_secondary_sections_host)

    # --- Inspector section ??DaVinci-style contextual properties
    # for the currently selected track / clip. Read-only Phase B1;
    # editable knobs (transform, opacity, per-clip speed) come in
    # Phase B2 once VideoTrack supports multi-clip splits.
    workbench_parent = self._right_workbench_pane
    self._workbench_section_host = QWidget(workbench_parent)
    self._workbench_section_host.setObjectName("WorkbenchSectionHost")
    self._workbench_section_host.setMinimumHeight(_WORKBENCH_MAIN_MIN_HEIGHT)
    self._workbench_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    ish = QVBoxLayout(self._workbench_section_host)
    ish.setContentsMargins(0, 0, 0, 0)
    ish.setSpacing(0)
    self._workbench_header_widget = QWidget(self._workbench_section_host)
    self._workbench_header_widget.setObjectName("WorkbenchHeader")
    self._workbench_header_widget.setFixedHeight(23)
    wh_layout = QHBoxLayout(self._workbench_header_widget)
    wh_layout.setContentsMargins(3, 0, 4, 0)
    wh_layout.setSpacing(0)
    self._workbench_header_title = self._make_section_header(
        tr("veditor.section.workbench"),
        "workbench",
        self._workbench_header_widget,
    )
    wh_layout.addWidget(self._workbench_header_title, stretch=1)
    self.workbench_ppt_btn = QPushButton("PPT", self._workbench_header_widget)
    self.workbench_ppt_btn.setObjectName("WorkbenchPptEntryButton")
    self.workbench_ppt_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.workbench_ppt_btn.setToolTip("Open PPT Editor")
    self.workbench_ppt_btn.setFixedSize(0, 0)
    self.workbench_ppt_btn.clicked.connect(lambda: self._open_ppt_generator())
    self.workbench_ppt_btn.hide()
    self.workbench_popout_btn = QPushButton("", self._workbench_header_widget)
    self.workbench_popout_btn.setObjectName("PreviewPopoutIcon")
    self.workbench_popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.workbench_popout_btn.setToolTip(tr("veditor.workbench_popout.tooltip"))
    self.workbench_popout_btn.setFixedSize(15, 20)
    self.workbench_popout_btn.setText("")
    self.workbench_popout_btn.setIcon(app_icon("popout", size=10))
    self.workbench_popout_btn.setIconSize(icon_size(10))
    self._install_icon_pulse(self.workbench_popout_btn, peak=14)
    self.workbench_popout_btn.clicked.connect(self._toggle_workbench_popout)
    wh_layout.addWidget(self.workbench_popout_btn)
    ish.addWidget(self._workbench_header_widget)
    self._workbench_panel = WorkbenchPanel(self._workbench_section_host)
    self._workbench_panel.fade_in_changed.connect(
        self._on_workbench_fade_in_changed,
    )
    self._workbench_panel.fade_out_changed.connect(
        self._on_workbench_fade_out_changed,
    )
    self._workbench_panel.volume_changed.connect(
        self._on_workbench_volume_changed,
    )
    self._workbench_panel.sound_editor_changed.connect(
        self._on_workbench_sound_editor_changed,
    )
    self._workbench_panel.sound_editor_mixer_track_changed.connect(
        self._on_workbench_sound_editor_mixer_track_changed,
    )
    self._workbench_panel.advanced_sound_lab_requested.connect(
        self._open_advanced_sound_lab,
    )
    self._workbench_panel.music_lab_action_requested.connect(
        self._on_workbench_music_lab_action_requested,
    )
    self._workbench_panel.music_lab_selection_changed.connect(
        self._on_workbench_music_lab_selection_changed,
    )
    self._workbench_panel.mmd_physics_rotation_hint_scale_changed.connect(
        self._on_workbench_mmd_rotation_hint_changed,
    )
    self._workbench_panel.mmd_physics_spring_response_changed.connect(
        self._on_workbench_mmd_spring_response_changed,
    )
    # History savepoints ??fire on slider release so a drag of
    # the fade-in slider produces one undo entry, not 50.
    self._workbench_panel.fade_in_committed.connect(
        lambda _v: self._register_change("workbench fade-in"),
    )
    self._workbench_panel.fade_out_committed.connect(
        lambda _v: self._register_change("workbench fade-out"),
    )
    self._workbench_panel.volume_committed.connect(
        lambda _v: self._register_change("workbench volume"),
    )
    self._workbench_panel.mmd_physics_rotation_hint_scale_committed.connect(
        lambda _v: self._register_change("workbench mmd cloth/hair"),
    )
    self._workbench_panel.mmd_physics_spring_response_committed.connect(
        lambda _v: self._register_change("workbench mmd follow"),
    )
    self._workbench_panel.open_clip_fx_requested.connect(self._open_selected_clip_fx)
    self._workbench_panel.toggle_clip_fx_requested.connect(self._toggle_selected_clip_fx_enabled)
    self._workbench_panel.clear_clip_fx_requested.connect(self._clear_selected_clip_fx)
    self._workbench_panel.clear_clip_transition_requested.connect(self._clear_selected_clip_transition)
    self._workbench_panel.open_live2d_editor_requested.connect(self._open_selected_live2d_editor)
    self._workbench_panel.apply_live2d_performance_source_requested.connect(
        self._apply_performance_source_to_selected_live2d
    )
    self._workbench_panel.open_vtuber_studio_requested.connect(self._open_vtuber_broadcast_studio)
    self._workbench_panel.open_mmd_editor_requested.connect(self._open_selected_mmd_actor_editor)
    # NodeGraph row click ??focus the matching panel. Today only
    # the Color node is wired; future LUT/Blur nodes will land
    # here as separate kinds and route to their own panels.
    self._workbench_panel.node_focused.connect(self._on_workbench_node_focused)

    def _wire_workbench_node_graph(ngw) -> None:
        if ngw is None or bool(getattr(ngw, "_editor_signals_wired", False)):
            return
        setattr(ngw, "_editor_signals_wired", True)
        ngw.selected_node_changed.connect(self._on_node_graph_selection)
        # Rebuild the active track's chain whenever the graph
        # topology changes (node added/deleted/connected). Slider
        # edits don't fire graph_mutated ??they mutate the
        # ColorGrade in place, so the cached chain references
        # stay valid.
        ngw.scene.graph_mutated.connect(self._rebuild_active_chain)
        # Phase E ??node mask add / edit / clear requests from
        # the right-click submenu. The editor handler attaches
        # the mask, opens any needed dialog, and refreshes the
        # preview.
        ngw.mask_request.connect(self._on_node_mask_request)

    self._workbench_panel.node_graph_ready.connect(_wire_workbench_node_graph)
    # DaVinci routing ??when the user picks a node in the graph,
    # bind the Color panel sliders to that node's grade.
    _wire_workbench_node_graph(self._workbench_panel.expose_node_graph_widget())
    self._color_workbench_panel = self._build_color_reference_workbench_panel()
    self._color_workbench_panel.hide()
    self._workbench_stack = QStackedWidget(self._workbench_section_host)
    self._workbench_stack.setObjectName("WorkbenchModeStack")
    self._workbench_stack.addWidget(self._workbench_panel)
    self._workbench_stack.addWidget(self._color_workbench_panel)
    ish.addWidget(self._workbench_stack, stretch=1)
    top_workbench_layout = getattr(self, "_top_workbench_layout", None)
    self._workbench_root_layout = self._right_workbench_pane_layout
    self._right_workbench_pane_layout.addWidget(
        self._workbench_section_host,
        stretch=1,
    )
    self._workbench_root_index = self._right_workbench_pane_layout.indexOf(
        self._workbench_section_host,
    )
    if top_workbench_layout is not None:
        self._right_dock_scroll.setParent(self._top_workbench_slot)
        self._right_dock_scroll.setMinimumHeight(230)
        self._right_dock_scroll.setMaximumHeight(16777215)
        top_workbench_layout.addWidget(self._right_dock_scroll, stretch=1)
        self._right_dock_scroll.show()
    else:
        self._right_dock_scroll.show()
    self._workbench_popout: "WorkbenchPopoutWindow | None" = None
    self._workbench_placeholder: QLabel | None = None
    self._yield_startup_ui("workbench")

    self._creator_assist_panel = None
    self._creator_assist_section_host = None
    self._creator_assist_placeholder = None
    if self._capcut_feature_enabled("creator_assist"):
        self._creator_assist_section_host = QWidget(self._right_dock_host)
        self._creator_assist_section_host.setObjectName("WorkbenchSectionHost")
        self._creator_assist_section_host.setProperty(
            "compactClosedHeight",
            _CREATOR_TOOLS_CLOSED_HEIGHT,
        )
        self._creator_assist_section_host.setProperty(
            "compactOpenedHeight",
            _WORKBENCH_TOOLS_OPEN_HEIGHT,
        )
        ca_lay = QVBoxLayout(self._creator_assist_section_host)
        ca_lay.setContentsMargins(0, 0, 0, 0)
        ca_lay.setSpacing(0)
        self._creator_assist_placeholder = QLabel(tr("veditor.creator_assist.placeholder"))
        self._creator_assist_placeholder.setObjectName("CreatorAssistSummary")
        self._creator_assist_placeholder.setWordWrap(True)
        self._creator_tools_body = QWidget(self._creator_assist_section_host)
        self._creator_tools_body.setObjectName("CreatorToolsBody")
        creator_tools_lay = QVBoxLayout(self._creator_tools_body)
        creator_tools_lay.setContentsMargins(7, 5, 7, 7)
        creator_tools_lay.setSpacing(5)
        creator_tools_summary = QLabel(tr("veditor.creator_tools.summary"))
        creator_tools_summary.setObjectName("CreatorToolSummary")
        creator_tools_summary.setWordWrap(True)
        creator_tools_lay.addWidget(creator_tools_summary)
        self._creator_ppt_maker_btn = QPushButton(tr("veditor.creator_tools.ppt_maker"))
        self._creator_ppt_maker_btn.setObjectName("CreatorToolButton")
        self._creator_ppt_maker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._creator_ppt_maker_btn.setToolTip(
            tr("veditor.creator_tools.ppt_maker.tooltip")
        )
        self._creator_ppt_maker_btn.setIcon(app_icon("layers", size=13))
        self._creator_ppt_maker_btn.setIconSize(icon_size(13))
        self._creator_ppt_maker_btn.setMinimumHeight(34)
        self._creator_ppt_maker_btn.clicked.connect(lambda: self._open_ppt_generator())
        creator_tools_lay.addWidget(self._creator_ppt_maker_btn)
        self._creator_unreal_engine_link_btn = QPushButton(
            tr("veditor.creator_tools.unreal_engine_link")
        )
        self._creator_unreal_engine_link_btn.setObjectName("CreatorToolButton")
        self._creator_unreal_engine_link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._creator_unreal_engine_link_btn.setToolTip(
            tr("veditor.creator_tools.unreal_engine_link.tooltip")
        )
        self._creator_unreal_engine_link_btn.setIcon(unreal_engine_icon(16))
        self._creator_unreal_engine_link_btn.setIconSize(icon_size(16))
        self._creator_unreal_engine_link_btn.setMinimumHeight(34)
        self._creator_unreal_engine_link_btn.clicked.connect(
            lambda: self._open_unreal_engine_link()
        )
        creator_tools_lay.addWidget(self._creator_unreal_engine_link_btn)
        self._creator_tools_body.setStyleSheet(
            "QWidget#CreatorToolsBody{background:#101112;border-top:1px solid #22262B;}"
            "QLabel#CreatorToolSummary{color:#AEB5BF;font-size:10px;background:transparent;border:none;}"
            "QPushButton#CreatorToolButton{color:#E8EDF6;background:#15181D;border:1px solid #2B3037;"
            "border-radius:5px;padding:5px 8px;font-size:10px;font-weight:720;text-align:left;}"
            "QPushButton#CreatorToolButton:hover{background:#20252B;border-color:#68717E;color:#FFFFFF;}"
        )

        def _ensure_creator_assist_with_tools():
            loaded = self._ensure_creator_assist_panel()
            if loaded:
                return loaded
            return [self._creator_assist_placeholder]

        ca_lay.addWidget(
            self._make_collapsible_section_header(
                tr("veditor.section.creator_assist"),
                "workbench",
                [self._creator_assist_placeholder],
                start_open=False,
                on_open=_ensure_creator_assist_with_tools,
                popout_callback=self._toggle_creator_assist_popout,
            )
        )
        ca_lay.addWidget(self._creator_tools_body, stretch=0)
        ca_lay.addWidget(self._creator_assist_placeholder, stretch=0)
        self._right_secondary_sections_layout.addWidget(
            self._creator_assist_section_host,
            stretch=0,
        )

    if prebuilt_ai_command_section is not None:
        prebuilt_ai_command_section.setParent(self._right_secondary_sections_host)
        self._right_secondary_sections_layout.addWidget(
            prebuilt_ai_command_section,
            stretch=0,
        )

    self._ai_script_edit_panel = None
    self._ai_script_edit_section_host = QWidget(self._right_dock_host)
    self._ai_script_edit_section_host.setObjectName("WorkbenchSectionHost")
    self._ai_script_edit_section_host.setProperty("compactClosedHeight", 39)
    self._ai_script_edit_section_host.setProperty(
        "compactOpenedHeight",
        _WORKBENCH_TOOLS_OPEN_HEIGHT,
    )
    script_lay = QVBoxLayout(self._ai_script_edit_section_host)
    script_lay.setContentsMargins(0, 0, 0, 0)
    script_lay.setSpacing(4)
    self._ai_script_edit_placeholder = QLabel(tr("veditor.script_edit.placeholder"))
    self._ai_script_edit_placeholder.setObjectName("CreatorAssistSummary")
    self._ai_script_edit_placeholder.setWordWrap(True)
    script_lay.addWidget(
        self._make_collapsible_section_header(
            tr("veditor.section.script_edit"),
            "workbench",
            [self._ai_script_edit_placeholder],
            start_open=False,
            on_open=self._ensure_ai_script_edit_panel,
            popout_callback=self._toggle_script_edit_popout,
        )
    )
    script_lay.addWidget(self._ai_script_edit_placeholder, stretch=0)
    self._right_secondary_sections_layout.addWidget(
        self._ai_script_edit_section_host,
        stretch=0,
    )

    self._render_queue_section_host = QWidget(self._right_dock_host)
    self._render_queue_section_host.setObjectName("WorkbenchSectionHost")
    self._render_queue_section_host.setProperty("compactClosedHeight", 51)
    self._render_queue_section_host.setProperty(
        "compactOpenedHeight",
        _WORKBENCH_TOOLS_OPEN_HEIGHT,
    )
    rq_lay = QVBoxLayout(self._render_queue_section_host)
    rq_lay.setContentsMargins(0, 0, 0, 0)
    rq_lay.setSpacing(4)

    def _build_render_queue_panel(parent: QWidget) -> QWidget:
        from app.render_queue_panel import RenderQueuePanel

        panel = RenderQueuePanel(parent)
        self._render_queue_panel = panel
        return panel

    render_queue_host = LazyPanelHost(
        _build_render_queue_panel,
        self._render_queue_section_host,
    )
    render_queue_host.setMinimumHeight(_WORKBENCH_LONG_PANEL_CONTENT_HEIGHT)
    self._render_queue_scroll_area = make_workbench_section_scroll_area(
        self._render_queue_section_host,
        render_queue_host,
        object_name="RenderQueueWorkbenchScrollArea",
        min_content_height=_WORKBENCH_LONG_PANEL_CONTENT_HEIGHT,
    )
    self._render_queue_panel = render_queue_host

    def _ensure_render_queue_panel() -> QWidget | None:
        try:
            return render_queue_host.ensure_panel()
        except Exception as exc:
            try:
                self._flash_status(f"Render Queue load failed: {exc}")
            except Exception:
                pass
            return None

    self._ensure_render_queue_panel = _ensure_render_queue_panel
    rq_lay.addWidget(
        self._make_collapsible_section_header(
            "Render Queue",
            "workbench",
            [self._render_queue_scroll_area],
            start_open=False,
            on_open=lambda: [self._render_queue_scroll_area]
            if _ensure_render_queue_panel() is not None
            else [self._render_queue_scroll_area],
            popout_callback=self._toggle_render_queue_popout,
        )
    )
    rq_lay.addWidget(self._render_queue_scroll_area, stretch=1)
    self._right_secondary_sections_layout.addWidget(
        self._render_queue_section_host,
        stretch=0,
    )

    self._audio_workspace_section_host = QWidget(self._right_dock_host)
    self._audio_workspace_section_host.setObjectName("WorkbenchSectionHost")
    self._audio_workspace_section_host.setProperty("compactClosedHeight", 51)
    self._audio_workspace_section_host.setProperty(
        "compactOpenedHeight",
        _WORKBENCH_TOOLS_SHORT_OPEN_HEIGHT,
    )
    aw_lay = QVBoxLayout(self._audio_workspace_section_host)
    aw_lay.setContentsMargins(0, 0, 0, 0)
    aw_lay.setSpacing(4)
    aw_body = QWidget(self._audio_workspace_section_host)
    aw_body.setObjectName("InspectorPanel")
    aw_body_lay = QVBoxLayout(aw_body)
    aw_body_lay.setContentsMargins(7, 6, 7, 7)
    aw_body_lay.setSpacing(5)
    self._audio_workspace_label = QLabel("No audio clip selected")
    self._audio_workspace_label.setWordWrap(True)
    self._audio_workspace_label.setStyleSheet(
        f"color:{COLOR_TEXT_TERTIARY}; font-size:11px;"
    )
    aw_body_lay.addWidget(self._audio_workspace_label)
    aw_btn_row = QHBoxLayout()
    aw_btn_row.setSpacing(4)
    self._audio_workspace_edit_btn = QPushButton("Sound Editor")
    self._audio_workspace_edit_btn.setObjectName("ToolButton")
    self._audio_workspace_edit_btn.clicked.connect(self._open_selected_audio_workspace)
    aw_btn_row.addWidget(self._audio_workspace_edit_btn)
    self._audio_workspace_mixer_btn = QPushButton("Mixer")
    self._audio_workspace_mixer_btn.setObjectName("ToolButton")
    self._audio_workspace_mixer_btn.setCheckable(True)
    self._audio_workspace_mixer_btn.clicked.connect(self._toggle_audio_workspace_mixer)
    aw_btn_row.addWidget(self._audio_workspace_mixer_btn)
    self._audio_workspace_scopes_btn = QPushButton("Scopes")
    self._audio_workspace_scopes_btn.setObjectName("ToolButton")
    self._audio_workspace_scopes_btn.setCheckable(True)
    self._audio_workspace_scopes_btn.clicked.connect(self._toggle_audio_workspace_scopes)
    aw_btn_row.addWidget(self._audio_workspace_scopes_btn)
    aw_body_lay.addLayout(aw_btn_row)
    aw_lay.addWidget(
        self._make_collapsible_section_header(
            "Audio",
            "workbench",
            [aw_body],
            start_open=False,
            popout_callback=self._toggle_audio_workspace_popout,
        )
    )
    aw_lay.addWidget(aw_body)
    self._right_secondary_sections_layout.addWidget(
        self._audio_workspace_section_host,
        stretch=0,
    )

    # --- PIP section ??Picture-in-Picture controls for the active track.
    # Shown / hidden dynamically by ``_refresh_pip_panel`` depending on
    # whether the active track is a non-bottom track (track index > 0).
    self._pip_section_host = QWidget(self._right_dock_host)
    pip_sh = QVBoxLayout(self._pip_section_host)
    pip_sh.setContentsMargins(0, 0, 0, 0)
    pip_sh.setSpacing(4)
    _pip_hdr_row = QWidget(self._pip_section_host)
    _pip_hdr_row.setObjectName("CollapsibleSectionHeader")
    _pip_hdr_row.setProperty("accent", "pip")
    _pip_hdr_lay = QHBoxLayout(_pip_hdr_row)
    _pip_hdr_lay.setContentsMargins(0, 0, 5, 0)
    _pip_hdr_lay.setSpacing(0)
    _pip_hdr_lay.addWidget(self._make_section_header(tr("PIP"), "pip", _pip_hdr_row), stretch=1)
    self._pip_popout_btn = QPushButton("", _pip_hdr_row)
    self._pip_popout_btn.setObjectName("PreviewPopoutIcon")
    self._pip_popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._pip_popout_btn.setToolTip("Pop out PIP controls")
    self._pip_popout_btn.setFixedSize(18, 27)
    self._pip_popout_btn.setText("")
    self._pip_popout_btn.setIcon(app_icon("popout", size=10))
    self._pip_popout_btn.setIconSize(icon_size(10))
    self._install_icon_pulse(self._pip_popout_btn, peak=13)
    self._pip_popout_btn.clicked.connect(self._toggle_pip_popout)
    _pip_hdr_lay.addWidget(self._pip_popout_btn)
    pip_sh.addWidget(_pip_hdr_row)
    pip_body = QWidget(self._pip_section_host)
    pip_body.setObjectName("PIPPanel")
    pip_body_layout = QVBoxLayout(pip_body)
    pip_body_layout.setContentsMargins(8, 4, 8, 4)
    pip_body_layout.setSpacing(6)

    # Enable PIP toggle
    self._pip_enable_btn = QPushButton(tr("Enable PIP"))
    self._pip_enable_btn.setCheckable(True)
    self._pip_enable_btn.setObjectName("ToolButton")
    self._pip_enable_btn.toggled.connect(self._on_pip_enable_toggled)
    pip_body_layout.addWidget(self._pip_enable_btn)

    def _make_pip_row(label_text: str, lo: int, hi: int, step: int):
        row_w = QWidget(self._pip_section_host)
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(52)
        lbl.setObjectName("SmallLabel")
        sl = StudioSlider("accent")
        sl.setRange(lo, hi)
        sl.setSingleStep(step)
        sl.setPageStep(step * 5)
        val_lbl = QLabel(f"{lo}")
        val_lbl.setFixedWidth(30)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setObjectName("SmallLabel")
        row_l.addWidget(lbl)
        row_l.addWidget(sl, stretch=1)
        row_l.addWidget(val_lbl)
        return row_w, sl, val_lbl

    _pip_x_row, self._pip_x_slider, self._pip_x_val = _make_pip_row("X pos", -100, 200, 1)
    _pip_y_row, self._pip_y_slider, self._pip_y_val = _make_pip_row("Y pos", -100, 200, 1)
    _pip_s_row, self._pip_scale_slider, self._pip_scale_val = _make_pip_row("Scale", 0, 200, 5)
    _pip_o_row, self._pip_opacity_slider, self._pip_opacity_val = _make_pip_row("Opacity", 0, 100, 5)

    # Default slider positions (50 / 50 / 30 / 100)
    self._pip_x_slider.setValue(50)
    self._pip_y_slider.setValue(50)
    self._pip_scale_slider.setValue(30)
    self._pip_opacity_slider.setValue(100)
    self._pip_x_val.setText("50")
    self._pip_y_val.setText("50")
    self._pip_scale_val.setText("30")
    self._pip_opacity_val.setText("100")

    for _row, _sl, _vl, _attr in [
        (_pip_x_row,    self._pip_x_slider,      self._pip_x_val,      "pip_x"),
        (_pip_y_row,    self._pip_y_slider,      self._pip_y_val,      "pip_y"),
        (_pip_s_row,    self._pip_scale_slider,  self._pip_scale_val,  "pip_scale"),
        (_pip_o_row,    self._pip_opacity_slider, self._pip_opacity_val, "pip_opacity"),
    ]:
        pip_body_layout.addWidget(_row)
        # Capture _sl / _vl / _attr by value via default arg.
        def _on_slider(v: int, sl=_sl, vl=_vl, attr=_attr):
            vl.setText(str(v))
            self._on_pip_slider_changed(attr, v)
        _sl.valueChanged.connect(_on_slider)

    # Keyframe controls
    _kf_btn_row = QWidget(self._pip_section_host)
    _kf_btn_layout = QHBoxLayout(_kf_btn_row)
    _kf_btn_layout.setContentsMargins(0, 0, 0, 0)
    _kf_btn_layout.setSpacing(4)
    self._pip_add_kf_btn = QPushButton("Keyframe +")
    self._pip_add_kf_btn.setObjectName("ToolButton")
    self._pip_add_kf_btn.clicked.connect(self._pip_add_keyframe)
    self._pip_del_kf_btn = QPushButton("??젣")
    self._pip_del_kf_btn.setObjectName("ToolButton")
    self._pip_del_kf_btn.setText("Delete")
    self._pip_del_kf_btn.clicked.connect(self._pip_delete_keyframe)
    _kf_btn_layout.addWidget(self._pip_add_kf_btn, stretch=1)
    _kf_btn_layout.addWidget(self._pip_del_kf_btn)
    pip_body_layout.addWidget(_kf_btn_row)

    from PySide6.QtWidgets import QListWidget as _QListWidget
    self._pip_kf_list = _QListWidget(self._pip_section_host)
    self._pip_kf_list.setObjectName("SmallList")
    self._pip_kf_list.setMaximumHeight(80)
    self._pip_kf_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    pip_body_layout.addWidget(self._pip_kf_list)

    pip_sh.addWidget(pip_body)
    self._pip_section_host.setVisible(False)   # hidden until a non-bottom track is selected
    self._right_secondary_sections_layout.addWidget(
        self._pip_section_host,
        stretch=0,
    )

    # --- Subtitles section ??lives in the right dock column, but
    # can also pop out into its own floating window. The whole
    # section (header + panel) is wrapped in a host widget that
    # gets reparented across pop-out / dock the same way as the
    # colour grading and timeline sections.
    self._subtitle_section_host = QWidget(self._right_dock_host)
    self._subtitle_section_host.setObjectName("WorkbenchSectionHost")
    self._subtitle_section_host.setProperty(
        "compactClosedHeight",
        _WORKBENCH_SECTION_CLOSED_HEIGHT,
    )
    self._subtitle_section_host.setProperty(
        "compactOpenedHeight",
        _WORKBENCH_TOOLS_OPEN_HEIGHT,
    )
    ssh = QVBoxLayout(self._subtitle_section_host)
    ssh.setContentsMargins(0, 0, 0, 0)
    ssh.setSpacing(4)
    subtitle_body = QWidget(self._subtitle_section_host)
    subtitle_body.setObjectName("SubtitleToolsBody")
    subtitle_body_layout = QVBoxLayout(subtitle_body)
    subtitle_body_layout.setContentsMargins(7, 5, 7, 7)
    subtitle_body_layout.setSpacing(6)
    _sub_hdr_row = QWidget(subtitle_body)
    _sub_hdr_h = QHBoxLayout(_sub_hdr_row)
    _sub_hdr_h.setContentsMargins(0, 0, 0, 0)
    _sub_hdr_h.setSpacing(5)
    _ai_sub_btn = QPushButton("AI Subtitles")
    _ai_sub_btn.setObjectName("ToolButton")
    _ai_sub_btn.setToolTip("Generate subtitles with Whisper.")
    _ai_sub_btn.clicked.connect(self._generate_ai_subtitles)
    _sub_hdr_h.addWidget(_ai_sub_btn, stretch=1)
    _srt_sub_btn = QPushButton("SRT")
    _srt_sub_btn.setObjectName("ToolButton")
    _srt_sub_btn.setToolTip("Import an SRT file using Screen Studio subtitle defaults.")
    _srt_sub_btn.clicked.connect(self._import_screenstudio_srt_subtitles)
    _sub_hdr_h.addWidget(_srt_sub_btn)
    self._subtitle_panel_toggle_btn = QPushButton("Show")
    self._subtitle_panel_toggle_btn.setObjectName("ToolButton")
    self._subtitle_panel_toggle_btn.setCheckable(True)
    self._subtitle_panel_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._subtitle_panel_toggle_btn.setToolTip("Show or hide subtitle editor")
    _sub_hdr_h.addWidget(self._subtitle_panel_toggle_btn)
    subtitle_body_layout.addWidget(_sub_hdr_row)
    self._subtitle_panel = SubtitlePanel(
        position_provider=lambda: self._player.position()
    )
    self._subtitle_panel.subtitles_changed.connect(self._on_subtitles_changed)
    self._subtitle_panel.popout_requested.connect(
        self._toggle_subtitle_popout,
    )
    # Phase 5 Step A: bind the subtitle layer to the timeline
    # ruler so its marker strip refreshes whenever the user adds /
    # edits / deletes a subtitle.
    self._timeline_ruler.set_subtitle_layer(self._subtitle_panel.layer)

    # Phase 5 Step B: drop a SubtitleLaneRow into the tracks scroll
    # right after the ruler. Sits at the top of the tracks area so
    # it's always visible (DaVinci's titles-on-top convention).
    self._subtitle_lane = SubtitleLaneRow(self._subtitle_panel.layer)
    self._subtitle_lane.set_px_per_sec(self._px_per_sec)
    self._subtitle_lane.request_edit.connect(self._on_subtitle_lane_edit)
    # Insert directly after the ruler (index 1) ??the existing
    # stretch / track rows shift down by one.
    ruler_idx = self._tracks_layout.indexOf(self._timeline_ruler)
    self._tracks_layout.insertWidget(ruler_idx + 1, self._subtitle_lane)
    subtitle_body_layout.addWidget(self._subtitle_panel)
    def _apply_subtitle_panel(opened: bool) -> None:
        self._subtitle_panel.setVisible(bool(opened))
        self._subtitle_panel_toggle_btn.setText("Hide" if opened else "Show")
    self._subtitle_panel_toggle_btn.toggled.connect(_apply_subtitle_panel)
    self._subtitle_panel_toggle_btn.setChecked(False)
    _apply_subtitle_panel(False)
    ssh.addWidget(
        self._make_collapsible_section_header(
            tr("veditor.section.subtitles"),
            "subtitles",
            [subtitle_body],
            start_open=False,
            popout_callback=self._toggle_subtitle_popout,
        )
    )
    ssh.addWidget(subtitle_body, stretch=0)
    self._right_secondary_sections_layout.addWidget(
        self._subtitle_section_host,
        stretch=0,
    )
    self._subtitle_root_layout = self._right_secondary_sections_layout
    self._subtitle_root_index = self._right_secondary_sections_layout.count() - 1
    self._subtitle_popout: "SubtitlePopoutWindow | None" = None
    self._subtitle_placeholder: QLabel | None = None
    # Pad the bottom of the dock so the panel hugs the top.
    self._right_secondary_bottom_spacer = QWidget(self._right_secondary_sections_host)
    self._right_secondary_bottom_spacer.setObjectName("RightSecondaryBottomSpacer")
    self._right_secondary_bottom_spacer.setFixedHeight(36)
    self._right_secondary_sections_layout.addWidget(
        self._right_secondary_bottom_spacer,
        stretch=0,
    )
    self._right_secondary_sections_layout.addStretch(1)
    self._right_dock_sections_splitter.setStretchFactor(0, 7)
    self._right_dock_sections_splitter.setStretchFactor(1, 3)
    if not _restore_right_dock_sections_splitter_state(
        self._right_dock_sections_splitter,
    ):
        self._right_dock_sections_splitter.setSizes([540, 260])
    _wire_right_secondary_section_height_refresh(self)
    self._right_dock_sections_splitter.splitterMoved.connect(
        lambda _pos, _index: _save_right_dock_sections_splitter_state(self),
    )
    self._yield_startup_ui("right_dock")
    self._apply_professional_ui_labels()
    self._apply_screenstudio_simple_mode_ui()
    self._refresh_command_bar_responsive()
    self._update_preview_placeholder()
    self._refresh_audio_workspace_panel()
    self._update_timeline_status()
    self._yield_startup_ui("final_refresh")
