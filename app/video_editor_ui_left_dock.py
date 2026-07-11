from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QSplitter, QVBoxLayout, QWidget

from app.i18n import tr
from app.media_pool import MediaPool
from app.video_editor_layout_specs import (
    LEFT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH,
    LEFT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
    left_dock_sections_splitter_qss,
)
from app.video_editor_lazy_panel import LazyPanelHost
from app.video_editor_actor_library import ActorLibraryPanel


def _editor_settings() -> QSettings:
    return QSettings("TigerCapture", "TigerCapture")


def _restore_left_dock_sections_splitter_state(splitter: QSplitter) -> bool:
    try:
        state = _editor_settings().value(LEFT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY)
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


def _save_left_dock_sections_splitter_state(owner) -> None:
    splitter = getattr(owner, "_left_dock_sections_splitter", None)
    if splitter is None:
        return
    try:
        _editor_settings().setValue(
            LEFT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY,
            splitter.saveState(),
        )
    except Exception:
        pass


def build_left_dock_sections(self) -> None:
    self._left_dock_sections_splitter = QSplitter(
        Qt.Orientation.Vertical,
        self._left_dock_host,
    )
    self._left_dock_sections_splitter.setObjectName("LeftDockSectionsSplitter")
    self._left_dock_sections_splitter.setChildrenCollapsible(False)
    self._left_dock_sections_splitter.setHandleWidth(
        LEFT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH,
    )
    self._left_dock_sections_splitter.setStyleSheet(left_dock_sections_splitter_qss())
    self._left_dock_sections_splitter.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    self._left_dock_layout.addWidget(self._left_dock_sections_splitter, stretch=1)

    # --- Media Pool section ??DaVinci-style. OS file drops go
    # here and pool items can be dragged onto a track row to
    # create a clip without going through the right-click menu.
    # Lives in the LEFT dock column so the preview / timeline
    # stays the visual centre of the editor. Sits ABOVE the
    # Effects Library so a clip ??effects card workflow scans
    # top ??bottom.
    self._media_pool_section_host = QWidget(self._left_dock_host)
    self._media_pool_section_host.setObjectName("MediaPoolSectionHost")
    self._media_pool_section_host.setMinimumHeight(440)
    self._media_pool_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    self._media_pool_section_host.setStyleSheet(
        "QWidget#MediaPoolSectionHost{background:#151515;border:none;border-radius:0px;}"
    )
    mph = QVBoxLayout(self._media_pool_section_host)
    mph.setContentsMargins(0, 0, 0, 0)
    mph.setSpacing(6)
    self._media_pool = MediaPool(self._media_pool_section_host)
    self._media_pool.setMinimumHeight(390)
    self._media_pool.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    self._media_pool.popout_requested.connect(self._toggle_media_pool_popout)
    self._media_pool.auto_polish_requested.connect(self._open_auto_polish_for_media_path)
    self._media_pool.item_added.connect(self._on_media_pool_item_added)
    self._media_pool.selection_changed.connect(self._on_media_pool_selection_changed)
    self._media_pool.asset_preview_requested.connect(self._open_ar_pbr_asset_preview)
    self._media_pool.avatar_target_requested.connect(self._use_vrm_media_as_avatar_target)
    self._media_pool.vtuber_studio_requested.connect(self._open_vrm_media_in_vtuber_studio)
    self._media_pool.mmd_asset_requested.connect(self._add_mmd_asset_to_timeline)
    self._media_pool.character_asset_hub_requested.connect(self._open_character_asset_hub)
    self._media_pool_header = self._make_collapsible_section_header(
        tr("veditor.section.media_pool"),
        "media_pool",
        [self._media_pool],
        start_open=True,
    )
    self._media_pool_header.setStyleSheet(
        "QWidget#MediaPoolCollapsibleSectionHeader{"
        "background:transparent;border:none;border-radius:0px;min-height:36px;max-height:36px;"
        "}"
        "QWidget#MediaPoolCollapsibleSectionHeader QLabel[sectionHeader=\"true\"]{"
        "background:transparent;border:none;color:#DDE1E8;"
        "font-family:'Segoe UI Variable','Noto Sans KR','Segoe UI','Malgun Gothic';"
        "font-size:9px;font-weight:560;letter-spacing:0px;padding-left:8px;"
        "}"
        "QWidget#MediaPoolCollapsibleSectionHeader QPushButton#SectionDisclosure{"
        "background:transparent;border:none;border-radius:5px;padding:0px;"
        "min-width:18px;max-width:18px;min-height:27px;max-height:27px;"
        "}"
        "QWidget#MediaPoolCollapsibleSectionHeader QPushButton#SectionDisclosure:hover{"
        "background:rgba(255,255,255,9);border:none;"
        "}"
    )
    self._localized_collapsible_headers["media_pool"] = self._media_pool_header
    mph.addWidget(self._media_pool_header)
    mph.addWidget(self._media_pool, stretch=1)
    self._left_dock_sections_splitter.addWidget(self._media_pool_section_host)
    self._yield_startup_ui("media_pool")

    self._left_secondary_sections_host = QWidget(self._left_dock_sections_splitter)
    self._left_secondary_sections_host.setObjectName("LeftSecondarySectionsHost")
    self._left_secondary_sections_host.setMinimumHeight(190)
    self._left_secondary_sections_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Expanding,
    )
    left_secondary_sections_layout = QVBoxLayout(self._left_secondary_sections_host)
    left_secondary_sections_layout.setContentsMargins(0, 0, 0, 0)
    left_secondary_sections_layout.setSpacing(10)
    self._left_secondary_sections_layout = left_secondary_sections_layout

    # --- Actor Library section. Actor creation is item-first:
    # drag Live2D/Spine cards into the timeline/actor lanes instead of
    # exposing every actor command as a permanent top-bar button.
    self._actor_library_section_host = QWidget(self._left_dock_host)
    self._actor_library_section_host.setObjectName("ActorLibrarySectionHost")
    self._actor_library_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    alh = QVBoxLayout(self._actor_library_section_host)
    alh.setContentsMargins(0, 0, 0, 0)
    alh.setSpacing(6)
    self._actor_library_panel = ActorLibraryPanel(self._actor_library_section_host)
    self._actor_library_live2d_card = self._actor_library_panel.live2d_card
    self._actor_library_spine_card = self._actor_library_panel.spine_card
    self._actor_library_header = self._make_collapsible_section_header(
        tr("veditor.section.actor_library"),
        "timeline",
        [self._actor_library_panel],
        start_open=True,
        popout_callback=self._toggle_actor_library_popout,
    )
    alh.addWidget(self._actor_library_header)
    alh.addWidget(self._actor_library_panel)
    self._left_secondary_sections_layout.addWidget(self._actor_library_section_host)
    self._yield_startup_ui("actor_library")

    # --- Effects Presets section. Timeline actor cards still live above
    # the timeline; this compact library exposes reusable clip-level
    # effect presets from app.preset_library.
    self._effects_library_section_host = QWidget(self._left_dock_host)
    self._effects_library_section_host.setObjectName("EffectsLibrarySectionHost")
    self._effects_library_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    elh = QVBoxLayout(self._effects_library_section_host)
    elh.setContentsMargins(0, 0, 0, 0)
    elh.setSpacing(6)

    def _build_effects_preset_panel(parent: QWidget) -> QWidget:
        from app.video_editor_preset_cards import EffectsPresetPanel

        panel = EffectsPresetPanel(
            preview_provider=self._preset_preview_frame,
            live_preview_callback=self._begin_preset_live_preview,
            live_preview_clear_callback=self._clear_preset_live_preview,
            save_current_callback=self._save_selected_effect_preset,
            import_pack_callback=self._import_preset_pack,
            export_pack_callback=self._export_user_preset_pack,
            manage_pack_callback=self._manage_preset_packs,
            qa_callback=self._show_preset_qa_report,
            auto_template_callback=self._apply_auto_preset_plan,
            template_composer_callback=self._open_template_composer,
            cache_callback=self._manage_preset_preview_cache,
            visual_qa_callback=self._open_visual_qa_viewer,
            parent=parent,
        )
        panel.preset_activated.connect(self._apply_effect_preset_from_left_panel)
        self._effects_preset_panel = panel
        return panel

    effects_preset_host = LazyPanelHost(
        _build_effects_preset_panel,
        self._effects_library_section_host,
    )
    self._effects_preset_panel = effects_preset_host

    def _ensure_effects_preset_panel() -> list[QWidget]:
        try:
            effects_preset_host.ensure_panel()
        except Exception as exc:
            try:
                self._flash_status(f"Effects library load failed: {exc}")
            except Exception:
                pass
        return [effects_preset_host]

    self._ensure_effects_preset_panel = lambda: effects_preset_host.ensure_panel()
    self._effects_library_header = self._make_collapsible_section_header(
        tr("veditor.section.effects"),
        "timeline",
        [effects_preset_host],
        start_open=False,
        on_open=_ensure_effects_preset_panel,
        popout_callback=self._toggle_effects_library_popout,
    )
    self._localized_collapsible_headers["effects"] = self._effects_library_header
    elh.addWidget(self._effects_library_header)
    elh.addWidget(effects_preset_host)
    self._left_secondary_sections_layout.addWidget(self._effects_library_section_host)
    self._effects_popout_btn = None

    # --- Title Presets section ??drag-to-timeline typography presets.
    self._title_presets_section_host = QWidget(self._left_dock_host)
    self._title_presets_section_host.setObjectName("TitlePresetsSectionHost")
    self._title_presets_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    tpsh = QVBoxLayout(self._title_presets_section_host)
    tpsh.setContentsMargins(0, 0, 0, 0)
    tpsh.setSpacing(6)

    def _build_title_presets_panel(parent: QWidget) -> QWidget:
        from app.video_editor_preset_cards import TitlePresetsPanel

        panel = TitlePresetsPanel(
            preview_provider=self._preset_preview_frame,
            live_preview_callback=self._begin_preset_live_preview,
            live_preview_clear_callback=self._clear_preset_live_preview,
            parent=parent,
        )
        self._title_presets_panel = panel
        return panel

    title_presets_host = LazyPanelHost(
        _build_title_presets_panel,
        self._title_presets_section_host,
    )
    self._title_presets_panel = title_presets_host

    def _ensure_title_presets_panel() -> list[QWidget]:
        try:
            title_presets_host.ensure_panel()
        except Exception as exc:
            try:
                self._flash_status(f"Title presets load failed: {exc}")
            except Exception:
                pass
        return [title_presets_host]

    self._ensure_title_presets_panel = lambda: title_presets_host.ensure_panel()
    self._title_presets_header = self._make_collapsible_section_header(
        tr("veditor.section.title_presets"),
        "timeline",
        [title_presets_host],
        start_open=False,
        on_open=_ensure_title_presets_panel,
        popout_callback=self._toggle_title_presets_popout,
    )
    tpsh.addWidget(self._title_presets_header)
    tpsh.addWidget(title_presets_host)
    self._left_secondary_sections_layout.addWidget(self._title_presets_section_host)

    # --- Transitions section ??DaVinci-style clip-boundary transitions.
    # Each card can be dragged to a clip's right edge to set
    # clip.transition_out_type / clip.transition_out_ms.
    self._transitions_section_host = QWidget(self._left_dock_host)
    self._transitions_section_host.setObjectName("TransitionsSectionHost")
    self._transitions_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    tsh = QVBoxLayout(self._transitions_section_host)
    tsh.setContentsMargins(0, 0, 0, 0)
    tsh.setSpacing(6)

    def _build_transitions_panel(parent: QWidget) -> QWidget:
        from app.video_editor_preset_cards import TransitionsPanel

        panel = TransitionsPanel(
            preview_provider=self._preset_preview_frame,
            live_preview_callback=self._begin_preset_live_preview,
            live_preview_clear_callback=self._clear_preset_live_preview,
            parent=parent,
        )
        self._transitions_panel = panel
        return panel

    transitions_host = LazyPanelHost(
        _build_transitions_panel,
        self._transitions_section_host,
    )
    self._transitions_panel = transitions_host

    def _ensure_transitions_panel() -> list[QWidget]:
        try:
            transitions_host.ensure_panel()
        except Exception as exc:
            try:
                self._flash_status(f"Transitions load failed: {exc}")
            except Exception:
                pass
        return [transitions_host]

    self._ensure_transitions_panel = lambda: transitions_host.ensure_panel()
    self._transitions_header = self._make_collapsible_section_header(
        tr("veditor.section.transitions"),
        "timeline",
        [transitions_host],
        start_open=False,
        on_open=_ensure_transitions_panel,
        popout_callback=self._toggle_transitions_popout,
    )
    tsh.addWidget(self._transitions_header)
    tsh.addWidget(transitions_host)
    self._left_secondary_sections_layout.addWidget(self._transitions_section_host)

    # --- Workflow Presets section: one-click template/caption/sticker/motion
    # packs from the same preset library used by automation and CLI QA.
    self._workflow_presets_section_host = QWidget(self._left_dock_host)
    self._workflow_presets_section_host.setObjectName("WorkflowPresetsSectionHost")
    self._workflow_presets_section_host.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Fixed,
    )
    wpsh = QVBoxLayout(self._workflow_presets_section_host)
    wpsh.setContentsMargins(0, 0, 0, 0)
    wpsh.setSpacing(6)

    def _build_workflow_presets_panel(parent: QWidget) -> QWidget:
        from app.video_editor_preset_cards import WorkflowPresetPanel

        panel = WorkflowPresetPanel(
            preview_provider=self._preset_preview_frame,
            live_preview_callback=self._begin_preset_live_preview,
            live_preview_clear_callback=self._clear_preset_live_preview,
            parent=parent,
        )
        panel.preset_activated.connect(self._apply_workflow_preset)
        self._workflow_presets_panel = panel
        return panel

    workflow_presets_host = LazyPanelHost(
        _build_workflow_presets_panel,
        self._workflow_presets_section_host,
    )
    self._workflow_presets_panel = workflow_presets_host

    def _ensure_workflow_presets_panel() -> list[QWidget]:
        try:
            workflow_presets_host.ensure_panel()
        except Exception as exc:
            try:
                self._flash_status(f"Workflow presets load failed: {exc}")
            except Exception:
                pass
        return [workflow_presets_host]

    self._ensure_workflow_presets_panel = lambda: workflow_presets_host.ensure_panel()
    self._workflow_presets_header = self._make_collapsible_section_header(
        tr("veditor.section.workflow_presets"),
        "timeline",
        [workflow_presets_host],
        start_open=False,
        on_open=_ensure_workflow_presets_panel,
        popout_callback=self._toggle_workflow_presets_popout,
    )
    wpsh.addWidget(self._workflow_presets_header)
    wpsh.addWidget(workflow_presets_host)
    self._left_secondary_sections_layout.addWidget(self._workflow_presets_section_host)
    self._yield_startup_ui("preset_sections")

    # Keep later sections hugged to the top while giving spare height to
    # the media pool instead of an empty bottom gutter.
    self._left_secondary_sections_layout.addStretch(0)
    self._left_dock_sections_splitter.addWidget(self._left_secondary_sections_host)
    self._left_dock_sections_splitter.setStretchFactor(0, 7)
    self._left_dock_sections_splitter.setStretchFactor(1, 3)
    if not _restore_left_dock_sections_splitter_state(self._left_dock_sections_splitter):
        self._left_dock_sections_splitter.setSizes([520, 260])
    self._left_dock_sections_splitter.splitterMoved.connect(
        lambda _pos, _index: _save_left_dock_sections_splitter_state(self),
    )
    self._media_pool_root_layout = None
    self._media_pool_root_index = self._main_dock_splitter.indexOf(
        self._left_dock_scroll,
    )
    self._media_pool_popout: "MediaPoolPopoutWindow | None" = None
    # Secondary section popouts share a compact state map. The old
    # effects-only popout was kept for compatibility; now all left/right
    # helper panels use the same reparenting helper.
    self._section_popouts: dict[str, dict] = {}
    self._effects_library_root_layout = None
    self._effects_library_root_index = -1
    self._effects_library_popout = None
    self._effects_library_placeholder = None
    self._media_pool_placeholder: QLabel | None = None
