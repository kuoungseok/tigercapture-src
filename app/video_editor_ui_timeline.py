from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.effect_cards import Live2DCard, SpeedCard, SpineCard, TypographyCard, ZoomCard
from app.i18n import tr
from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import COLOR_TEXT_TERTIARY, editor_scrollbar_qss
from app.timeline_cursor import _timeline_tool_cursor
from app.timeline_ruler import TimelineRuler
from app.timeline_striped_host import StripedHost
from app.video_editor_audio_widgets import AudioMixerPanel
from app.video_editor_layout_specs import horizontal_tool_scroll_qss
from app.video_editor_timeline_palette import configure_timeline_tile
from app.video_editor_window_widgets import _AnimatedTimelineToolButton


def build_timeline_area(self):
    # --- Unified timeline palette (edit tools + drag/drop tools) ---
    track_bar_host = QWidget(self)
    track_bar_host.setObjectName("TimelinePaletteBar")
    self._timeline_palette_host = track_bar_host
    palette_layout = QHBoxLayout(track_bar_host)
    palette_layout.setContentsMargins(6, 2, 6, 2)
    palette_layout.setSpacing(5)

    self._timeline_palette_toggle_btn = QToolButton(track_bar_host)
    self._timeline_palette_toggle_btn.setObjectName("PaletteCollapseButton")
    self._timeline_palette_toggle_btn.setCheckable(True)
    self._timeline_palette_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._timeline_palette_toggle_btn.setIcon(
        app_icon("chevron-down", size=12, color="#AEB7C6")
    )
    self._timeline_palette_toggle_btn.setIconSize(icon_size(12))
    self._timeline_palette_toggle_btn.setToolTip(
        tr("veditor.timeline_tools.hide")
    )
    self._timeline_palette_toggle_btn.toggled.connect(
        self._set_timeline_palette_collapsed
    )
    palette_layout.addWidget(
        self._timeline_palette_toggle_btn,
        alignment=Qt.AlignmentFlag.AlignVCenter,
    )
    self._timeline_palette_collapsed_label = QLabel(
        tr("veditor.timeline_tools.collapsed_label"),
        track_bar_host,
    )
    self._timeline_palette_collapsed_label.setObjectName(
        "TimelinePaletteCollapsedLabel"
    )
    self._timeline_palette_collapsed_label.setAlignment(
        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
    )
    self._timeline_palette_collapsed_label.setVisible(False)
    palette_layout.addWidget(
        self._timeline_palette_collapsed_label,
        alignment=Qt.AlignmentFlag.AlignVCenter,
    )

    tool_row_host = QWidget(track_bar_host)
    tool_row_host.setObjectName("TimelineToolBar")
    track_bar = QHBoxLayout(tool_row_host)
    track_bar.setContentsMargins(0, 0, 0, 0)
    track_bar.setSpacing(5)

    def _configure_timeline_tile(
        btn,
        label: str,
        icon_name: str,
        *,
        color: str = "#B8C1CF",
        size: int = 30,
        role: str | None = None,
    ) -> None:
        configure_timeline_tile(
            btn,
            label,
            icon_name,
            color=color,
            size=size,
            role=role,
            cursor_factory=_timeline_tool_cursor,
            install_pulse=self._install_icon_pulse,
            animated_button_type=_AnimatedTimelineToolButton,
        )

    track_bar.addWidget(self.add_track_btn)
    track_bar.addWidget(self.add_audio_btn)
    track_bar.addWidget(self.del_track_btn)
    track_bar.addSpacing(8)
    track_entries = (
        ("Add Video Track", self._add_empty_track),
        ("Add Audio Track", self._add_empty_audio_track),
        ("Delete Active Track", self._delete_active_track),
    )
    self._track_menu_btn = self._make_command_menu_button(
        "Tracks",
        "Add or delete timeline tracks.",
    )
    self._install_lazy_action_menu(
        self._track_menu_btn,
        track_entries,
        object_name="TrackCommandMenu",
    )
    _configure_timeline_tile(self._track_menu_btn, "Tracks", "slide", role="tracks")
    track_bar.insertWidget(0, self._track_menu_btn)
    self.add_track_btn.hide()
    self.add_audio_btn.hide()
    self.del_track_btn.hide()
    # Edit-tools group ??sits next to the track-management buttons
    # because Blade operates on the tracks below it. Industry NLEs
    # (DaVinci/Premiere/FCP) all place editing tools directly above
    # the timeline for the same spatial-association reason.
    self._timeline_tool_buttons: dict[str, QToolButton] = {}
    self._timeline_tool_group = QButtonGroup(self)
    self._timeline_tool_group.setExclusive(True)
    for mode, label, shortcut, icon_name, tip in (
        ("select", "Select", "V", "cursor", "Select/move clips"),
        ("blade", "Blade", "B", "scissors", "Click a clip to split it"),
        ("ripple", "Ripple", "R", "ripple", "Trim an edge and ripple later clips"),
        ("roll", "Roll", "N", "roll", "Drag a shared cut point"),
        ("slip", "Slip", "Y", "slip", "Keep clip position, change source frames"),
        ("slide", "Slide", "U", "slide", "Slide between adjacent clips"),
    ):
        btn = _AnimatedTimelineToolButton(mode, icon_name, tool_row_host)
        btn.setCheckable(True)
        _configure_timeline_tile(btn, label, icon_name, role=mode)
        btn.setToolTip(f"{label} ({shortcut}) - {tip}")
        btn.clicked.connect(lambda _checked=False, m=mode: self._set_timeline_tool_mode(m))
        self._timeline_tool_group.addButton(btn)
        self._timeline_tool_buttons[mode] = btn
        track_bar.addWidget(btn)
    self._timeline_tool_buttons["select"].setChecked(True)
    self.precision_trim_btn = QToolButton(tool_row_host)
    _configure_timeline_tile(self.precision_trim_btn, "Trim", "sliders", role="trim")
    self.precision_trim_btn.setToolTip("Precision trim selected clip (Ctrl+Alt+T)")
    self.precision_trim_btn.clicked.connect(self._open_precision_trim_dialog)
    track_bar.addWidget(self.precision_trim_btn)
    self.nest_btn = QToolButton(tool_row_host)
    _configure_timeline_tile(self.nest_btn, "Nest", "nest", role="nest")
    self.nest_btn.setToolTip("Create compound/nested group from selected clips")
    self.nest_btn.clicked.connect(self._create_nested_group_from_selection)
    track_bar.addWidget(self.nest_btn)
    _configure_timeline_tile(self.blade_btn, "Split", "scissors", role="split")
    track_bar.addWidget(self.blade_btn)
    self.zoom_review_btn = QToolButton(tool_row_host)
    _configure_timeline_tile(self.zoom_review_btn, "Review Frame", "zoom", role="zoom")
    self.zoom_review_btn.setToolTip(
        "Frame the Timeline around the current edit for review screenshots"
    )
    self.zoom_review_btn.clicked.connect(
        lambda _checked=False: self._apply_timeline_review_framing()
    )
    track_bar.addWidget(self.zoom_review_btn)
    self._timeline_status_label = QLabel("", tool_row_host)
    self._timeline_status_label.setObjectName("TimelineStatusChip")
    self._timeline_status_label.setMinimumWidth(260)
    self._timeline_status_label.setMaximumWidth(520)
    self._timeline_status_label.hide()
    track_bar.addWidget(self._timeline_status_label)
    effects_bar_host = QWidget(track_bar_host)
    effects_bar_host.setObjectName("TimelineEffectsBar")
    effects_bar = QHBoxLayout(effects_bar_host)
    effects_bar.setContentsMargins(0, 0, 0, 0)
    effects_bar.setSpacing(5)
    # Track effects ??Fade / Typography / Zoom / Speed are
    # time-anchored timeline actors (they live on the track at a
    # specific ms range), so their drag sources sit directly
    # above the tracks. Distinct from the Color page node graph,
    # which handles pixel-level transformations across the whole
    # clip. Effects Library left-dock section was removed once
    # this layout landed ??too much UI for four cards.
    # Label so users know these are drag-and-drop items
    drag_hint = QLabel("?쒕옒洹명빐??異붽?", effects_bar_host)
    drag_hint.setStyleSheet(
        "color: #606070; font-size: 10px; padding: 0 6px;"
    )
    drag_hint.setMinimumWidth(96)
    drag_hint.setText("Drag to add")
    drag_hint.setObjectName("PaletteHint")
    drag_hint.setStyleSheet("")
    drag_hint.hide()

    self.fade_card   = self._build_fade_card()
    self.typo_card   = TypographyCard()
    self.zoom_card   = ZoomCard()
    self.speed_card  = SpeedCard()
    self.spine_card  = SpineCard()
    self.live2d_card = Live2DCard()
    for card in (self.fade_card, self.typo_card, self.zoom_card,
                 self.speed_card, self.spine_card, self.live2d_card):
        card.setFixedSize(30, 30)
        card.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        muted = QGraphicsOpacityEffect(card)
        muted.setOpacity(0.52)
        card.setGraphicsEffect(muted)
        effects_bar.addWidget(card)
    # Scopes toggle ??right side of timeline toolbar
    self.audio_scopes_tl_btn = QToolButton(tool_row_host)
    self.audio_scopes_tl_btn.setCheckable(True)
    self.audio_scopes_tl_btn.setChecked(False)
    _configure_timeline_tile(self.audio_scopes_tl_btn, "Scopes", "scopes", role="scopes")
    self.audio_scopes_tl_btn.setToolTip("怨좊땲?ㅻ???+ LUFS ?⑤꼸 ?좉?")
    self.audio_scopes_tl_btn.setToolTip("Audio scopes and LUFS panel")
    self.audio_scopes_tl_btn.toggled.connect(
        lambda checked: self._on_audio_scopes_toggled(checked)
    )
    track_bar.addWidget(self.audio_scopes_tl_btn)
    # Mixer toggle ??right side of timeline toolbar
    self.audio_mixer_tl_btn = QToolButton(tool_row_host)
    self.audio_mixer_tl_btn.setCheckable(True)
    self.audio_mixer_tl_btn.setChecked(False)
    _configure_timeline_tile(self.audio_mixer_tl_btn, "Mixer", "mixer", role="mixer")
    self.audio_mixer_tl_btn.setToolTip("?ㅻ뵒??誘뱀꽌 ?⑤꼸 ?좉?")
    self.audio_mixer_tl_btn.setToolTip("Audio mixer panel")
    self.audio_mixer_tl_btn.toggled.connect(
        lambda checked: self._on_audio_mixer_toggled(checked)
    )
    track_bar.addWidget(self.audio_mixer_tl_btn)
    palette_layout.addWidget(tool_row_host)
    palette_layout.addSpacing(6)
    palette_divider = QFrame(track_bar_host)
    palette_divider.setObjectName("PaletteDivider")
    palette_divider.setFrameShape(QFrame.Shape.VLine)
    palette_divider.setFixedWidth(1)
    palette_layout.addWidget(palette_divider)
    palette_layout.addSpacing(6)
    palette_layout.addWidget(effects_bar_host)
    palette_layout.addStretch(1)
    self._timeline_palette_content_widgets = (
        tool_row_host,
        palette_divider,
        effects_bar_host,
    )
    track_bar_host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    self._timeline_palette_scroll = QScrollArea(self)
    self._timeline_palette_scroll.setObjectName("TimelinePaletteScroll")
    self._timeline_palette_scroll.setWidget(track_bar_host)
    self._timeline_palette_scroll.setWidgetResizable(False)
    self._timeline_palette_scroll.setFrameShape(QFrame.Shape.NoFrame)
    self._timeline_palette_scroll.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
    )
    self._timeline_palette_scroll.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
    )
    self._timeline_palette_scroll.setMinimumHeight(40)
    self._timeline_palette_scroll.setMaximumHeight(42)
    self._timeline_palette_scroll.setStyleSheet(horizontal_tool_scroll_qss("QScrollArea#TimelinePaletteScroll"))
    self._set_timeline_palette_collapsed(True)
    self._yield_startup_ui("timeline_palette")

    # --- Tracks container (scrollable vertically). Continuous 45deg
    # stripe background so every gap / empty area reads as "timeline". ---
    self._tracks_host = StripedHost()
    self._tracks_host.setAcceptDrops(True)
    self._tracks_host.installEventFilter(self)
    self._tracks_layout = QVBoxLayout(self._tracks_host)
    self._tracks_layout.setContentsMargins(0, 0, 0, 0)
    self._tracks_layout.setSpacing(0)  # rows handle their own dividers
    self._tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    # Shared project-time ruler at the top of the scroll viewport so it
    # scrolls horizontally with the tracks.
    self._timeline_ruler = TimelineRuler()
    self._timeline_ruler.scrub_requested.connect(self._player.set_position)
    self._timeline_ruler.marker_delete_requested.connect(self._delete_timeline_marker)
    self._tracks_layout.addWidget(self._timeline_ruler)

    self._tracks_layout.addStretch(1)

    self._tracks_scroll = QScrollArea()
    self._tracks_scroll.setObjectName("TimelineScroll")
    self._tracks_scroll.setWidgetResizable(True)
    self._tracks_scroll.setWidget(self._tracks_host)
    self._tracks_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    self._tracks_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._tracks_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    self._tracks_scroll.setMinimumHeight(170)
    # Keep the scroll viewport transparent so StripedHost's pattern fills
    # the entire visible area (especially below the last track).
    self._tracks_scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollArea > QWidget > QWidget { background: transparent; }"
        + editor_scrollbar_qss("QScrollArea#TimelineScroll")
    )
    # Mouse wheel over the timeline zooms its horizontal length.
    self._tracks_scroll.viewport().installEventFilter(self)
    self._tracks_scroll.horizontalScrollBar().valueChanged.connect(
        lambda _value: [
            row.update() for row in getattr(self, "_track_rows", {}).values()
        ]
    )

    # Wrap the timeline in a section host so we can detach the
    # whole thing (header + scroll) into a floating popout window
    # ??same pattern as the colour grading section. The header sits
    # above the scroll with a pop-out icon on the right.
    self._timeline_section_host = QWidget()
    self._timeline_section_host.setObjectName("TimelineSectionHost")
    self._timeline_compact_min_height = 220
    self._timeline_compact_max_height = 320
    self._timeline_mixer_min_height = 430
    self._timeline_mixer_max_height = 560
    self._timeline_section_host.setMinimumHeight(self._timeline_compact_min_height)
    self._timeline_section_host.setMaximumHeight(self._timeline_compact_max_height)
    ts_layout = QVBoxLayout(self._timeline_section_host)
    ts_layout.setContentsMargins(0, 0, 0, 0)
    ts_layout.setSpacing(0)
    timeline_header = QWidget()
    timeline_header.setObjectName("TimelineSectionHeader")
    th_layout = QHBoxLayout(timeline_header)
    th_layout.setContentsMargins(0, 0, 8, 0)
    th_layout.setSpacing(0)
    self._timeline_section_label = self._make_section_header(
        tr("veditor.section.timeline"), "timeline",
    )
    th_layout.addWidget(self._timeline_section_label, stretch=1)
    self.timeline_popout_btn = QPushButton("")
    self.timeline_popout_btn.setObjectName("PreviewPopoutIcon")
    self.timeline_popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.timeline_popout_btn.setToolTip(
        tr("veditor.timeline_popout.tooltip"),
    )
    self.timeline_popout_btn.setFixedSize(28, 24)
    self.timeline_popout_btn.setText("")
    self.timeline_popout_btn.setIcon(app_icon("popout", size=16))
    self.timeline_popout_btn.setIconSize(icon_size(16))
    self._install_icon_pulse(self.timeline_popout_btn, peak=21)
    self.timeline_popout_btn.clicked.connect(self._toggle_timeline_popout)
    th_layout.addWidget(self.timeline_popout_btn)
    ts_layout.addWidget(timeline_header)
    ts_layout.addWidget(self._timeline_palette_scroll)
    ts_layout.addWidget(self._tracks_scroll, stretch=1)

    # --- Audio Mixer panel (includes built-in scopes column on the right) ---
    self._audio_mixer_panel = AudioMixerPanel()
    self._audio_mixer_panel.setVisible(False)
    self._audio_mixer_panel.set_volume_callback(self._on_mixer_fader_changed)
    self._audio_mixer_panel.set_pan_callback(self._on_mixer_pan_changed)
    self._audio_mixer_panel.visibility_changed.connect(
        self._on_audio_mixer_visibility_changed,
    )
    self._active_audio_track_id: int | None = None
    ts_layout.addWidget(self._audio_mixer_panel)

    self._editor_outer_layout.addWidget(self._timeline_section_host, stretch=1)
    self._yield_startup_ui("timeline_section")
    # Track where in the main column the timeline lives so the
    # popout can leave a placeholder and put it back later.
    self._timeline_root_layout = self._editor_outer_layout
    self._timeline_root_index = self._editor_outer_layout.indexOf(
        self._timeline_section_host,
    )
    self._timeline_popout: "TimelinePopoutWindow | None" = None
    self._timeline_placeholder: QLabel | None = None

    # --- Selection / clear-selection row (controls bar) ---
    # Speed-rate buttons used to live here too, but the SpeedCard
    # (drag-drop) and right-click context menu cover the same
    # workflow with less clutter, so the buttons were removed.
    # ``_speed_buttons`` stays as an empty list so the existing
    # selection-state update loop is a no-op rather than a bug.
    controls_bar = QWidget(self)
    controls_bar.setObjectName("SelectionBar")
    controls_bar.setMinimumHeight(36)
    controls_bar.setMaximumHeight(38)
    sel_row = QHBoxLayout(controls_bar)
    sel_row.setContentsMargins(8, 2, 8, 2)
    sel_row.setSpacing(7)
    self.selection_label = QLabel(tr("veditor.no_selection"))
    self.selection_label.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;"
    )
    self.selection_label.setToolTip(
        "Selection status is kept here for accessibility; active tools show details in tooltips."
    )
    self.selection_label.hide()
    sel_row.addWidget(self.selection_label)
    sel_row.addStretch(1)

    self._speed_buttons: list[QPushButton] = []

    self.clear_sel_btn = QPushButton(tr("veditor.btn.clear_selection"))
    self.clear_sel_btn.setObjectName("ToolButton")
    self.clear_sel_btn.setProperty("selectionAction", True)
    self.clear_sel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.clear_sel_btn.setFixedSize(40, 34)
    self.clear_sel_btn.setText("")
    self.clear_sel_btn.setIcon(app_icon("x", size=15, color="#C8CCD9"))
    self.clear_sel_btn.setIconSize(icon_size(15))
    self.clear_sel_btn.setToolTip(tr("veditor.btn.clear_selection"))
    self.clear_sel_btn.setEnabled(False)
    self.clear_sel_btn.clicked.connect(self._clear_selection_active_track)
    sel_row.addWidget(self.clear_sel_btn)

    sel_row.addSpacing(6)
    return controls_bar, sel_row

