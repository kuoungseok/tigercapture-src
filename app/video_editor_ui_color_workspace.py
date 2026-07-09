from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import editor_scrollbar_qss
from app.video_editor_ai_command_dock import (
    AI_COMMAND_HOST_CLOSED_HEIGHT,
    AI_COMMAND_HOST_OPEN_HEIGHT,
)


def build_color_workspace(self, main_col, root, controls_bar, sel_row) -> None:
    # ---- Page switcher: Edit | Color ----
    _ps_qss = (
        "QPushButton { background: rgba(255,255,255,18); color: #BFC5D8; "
        "border: 1px solid #353D55; border-radius: 12px; "
        "padding: 0px; font-size: 12px; font-weight: 800; }"
        "QPushButton:hover { background: rgba(255,255,255,30); color: #FFFFFF; "
        "border-color: #5A6687; }"
        "QPushButton:checked { background: qlineargradient("
        "x1:0, y1:0, x2:1, y2:1, stop:0 #7069FF, stop:1 #8F7CFF); "
        "color: #ffffff; border-color: #A59AFF; }"
    )
    self._page_edit_btn = QPushButton("Edit")
    self._page_edit_btn.setProperty("selectionAction", True)
    self._page_edit_btn.setCheckable(True)
    self._page_edit_btn.setChecked(True)
    self._page_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._page_edit_btn.setFixedSize(42, 34)
    self._page_edit_btn.setText("")
    self._page_edit_btn.setIcon(app_icon("cursor", size=16, color="#FFFFFF"))
    self._page_edit_btn.setIconSize(icon_size(16))
    self._page_edit_btn.setToolTip("Edit")
    self._page_edit_btn.setStyleSheet(_ps_qss)
    self._page_edit_btn.clicked.connect(lambda: self._switch_page("edit"))
    sel_row.addWidget(self._page_edit_btn)

    self._page_color_btn = QPushButton("Color")
    self._page_color_btn.setProperty("selectionAction", True)
    self._page_color_btn.setCheckable(True)
    self._page_color_btn.setChecked(False)
    self._page_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._page_color_btn.setFixedSize(42, 34)
    self._page_color_btn.setText("")
    self._page_color_btn.setIcon(app_icon("grading", size=17, color="#FFFFFF"))
    self._page_color_btn.setIconSize(icon_size(16))
    self._page_color_btn.setToolTip("Color Grade")
    self._page_color_btn.setStyleSheet(_ps_qss)
    self._page_color_btn.clicked.connect(lambda: self._switch_page("color"))
    sel_row.addWidget(self._page_color_btn)

    self._color_page_window: "ColorPageWindow | None" = None

    self._selection_controls_bar = controls_bar
    controls_bar.hide()

    # --- Color grading section (panel + scopes, popout-capable) ---
    # Custom header with a pop-out button on the right, so the
    # user can detach the whole color surface into a floating
    # window (DaVinci-style docking, single-window app version).
    self._color_header_widget = QWidget(main_col)
    self._color_header_widget.setObjectName("ColorSectionHeader")
    chh = QHBoxLayout(self._color_header_widget)
    chh.setContentsMargins(0, 0, 8, 0)
    chh.setSpacing(0)
    self._color_section_label = self._make_section_header(tr("veditor.section.color"), "color")
    chh.addWidget(self._color_section_label, stretch=1)
    self.color_popout_btn = QPushButton("", self._color_header_widget)
    self.color_popout_btn.setObjectName("PreviewPopoutIcon")
    self.color_popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.color_popout_btn.setToolTip(tr("veditor.color_popout.tooltip"))
    self.color_popout_btn.setFixedSize(28, 24)
    self.color_popout_btn.setText("")
    self.color_popout_btn.setIcon(app_icon("popout", size=16))
    self.color_popout_btn.setIconSize(icon_size(16))
    self._install_icon_pulse(self.color_popout_btn, peak=21)
    self.color_popout_btn.clicked.connect(self._toggle_color_popout)
    chh.addWidget(self.color_popout_btn)
    # (Color section moved above timeline ??see addWidget calls near _timeline_section_host)
    # Mask toolbar ??DaVinci-style. The four primary mask
    # actions are surfaced as big always-visible buttons (when
    # the dock is open) so users don't have to right-click a
    # small node thumbnail. All actions act on the currently
    # selected NodeItem (``self._node_grade_target``) and
    # delegate to ``_on_node_mask_request`` so the same code
    # path handles toolbar + context-menu invocations.
    from PySide6.QtWidgets import QToolButton as _QToolButton
    self._mask_toolbar_widget = QWidget(main_col)
    mt_layout = QHBoxLayout(self._mask_toolbar_widget)
    mt_layout.setContentsMargins(8, 4, 8, 4)
    mt_layout.setSpacing(6)
    self._mask_btn_window = QPushButton("Window", self._mask_toolbar_widget)
    self._mask_btn_window.setObjectName("ToolButton")
    self._mask_btn_window.setIcon(app_icon("target", size=13, color="#D7DAE7"))
    self._mask_btn_window.setIconSize(icon_size(13))
    self._mask_btn_window.setCursor(Qt.CursorShape.PointingHandCursor)
    self._mask_btn_window.clicked.connect(
        lambda: self._mask_toolbar_action("power_window"),
    )
    self._mask_btn_qualifier = QPushButton("Qualifier", self._mask_toolbar_widget)
    self._mask_btn_qualifier.setObjectName("ToolButton")
    self._mask_btn_qualifier.setIcon(app_icon("grading", size=13, color="#D7DAE7"))
    self._mask_btn_qualifier.setIconSize(icon_size(13))
    self._mask_btn_qualifier.setCursor(Qt.CursorShape.PointingHandCursor)
    self._mask_btn_qualifier.clicked.connect(
        lambda: self._mask_toolbar_action("hsl"),
    )
    # Person - single-click selfie / background segmentation.
    # Removed the niche lips/eyes/face presets that aren't
    # standard in DaVinci/Premiere/AE ??keeping the toolbar
    # focused on the 80% workflow. Power Window + Rotoscope
    # cover everything else.
    self._mask_btn_person = QPushButton("Person", self._mask_toolbar_widget)
    self._mask_btn_person.setObjectName("ToolButton")
    self._mask_btn_person.setIcon(app_icon("person", size=13, color="#D7DAE7"))
    self._mask_btn_person.setIconSize(icon_size(13))
    self._mask_btn_person.setCursor(Qt.CursorShape.PointingHandCursor)
    self._mask_btn_person.clicked.connect(
        lambda: self._mask_toolbar_action("magic:person"),
    )

    # ?逾?Rotoscope ??GrabCut / SAM / manual polygon entry
    # points. All routes through ``_mask_toolbar_action`` and
    # ends in a node mask attachment.
    self._mask_btn_roto = _QToolButton(self._mask_toolbar_widget)
    self._mask_btn_roto.setText("Rotoscope")
    self._mask_btn_roto.setIcon(app_icon("scissors", size=13, color="#D7DAE7"))
    self._mask_btn_roto.setIconSize(icon_size(13))
    self._mask_btn_roto.setObjectName("ToolButton")
    self._mask_btn_roto.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    self._mask_btn_roto.setCursor(Qt.CursorShape.PointingHandCursor)
    self._mask_btn_roto.setPopupMode(
        _QToolButton.ToolButtonPopupMode.InstantPopup,
    )
    self._mask_btn_roto.setStyleSheet(
        "QToolButton { padding: 4px 12px; font-weight: 600; "
        "background-color: #2e2e2e; color: #ffffff; "
        "border: 1px solid #3a3a3a; border-radius: 4px; }"
        "QToolButton:hover { background-color: #383838; }"
        "QToolButton::menu-indicator { image: none; }"
    )
    self._install_lazy_action_menu(
        self._mask_btn_roto,
        (
            ("Track selected region", lambda: self._mask_toolbar_action("track_region")),
            None,
            (tr("nodemask.menu.roto_grabcut"), lambda: self._mask_toolbar_action("roto:grabcut")),
            (tr("nodemask.menu.roto_sam"), lambda: self._mask_toolbar_action("roto:sam")),
            (tr("nodemask.menu.roto_manual"), lambda: self._mask_toolbar_action("power_window")),
        ),
        object_name="RotoscopeCommandMenu",
    )

    self._mask_btn_clear = QPushButton("Clear", self._mask_toolbar_widget)
    self._mask_btn_clear.setObjectName("ToolButton")
    self._mask_btn_clear.setIcon(app_icon("clear", size=13, color="#D7DAE7"))
    self._mask_btn_clear.setIconSize(icon_size(13))
    self._mask_btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
    self._mask_btn_clear.clicked.connect(
        lambda: self._mask_toolbar_action("clear"),
    )
    for b in (
        self._mask_btn_window, self._mask_btn_qualifier,
        self._mask_btn_person, self._mask_btn_roto, self._mask_btn_clear,
    ):
        b.setToolTip(tr("nodemask.toolbar.tip"))
        mt_layout.addWidget(b)
    mt_layout.addStretch(1)
    self._mask_toolbar_widget.hide()  # follows _color_header_widget visibility
    # (mask toolbar added above timeline ??see earlier addWidget near _timeline_section_host)

    # The host widget is the single canonical container for the
    # color panel + scopes. We move (reparent) it between the
    # editor's root layout and the popout window ??same widget
    # tree, no state duplication.
    # The colour grading panel embeds the scopes panel internally
    # (as a sibling column to the wheels) so the histogram and the
    # wheels naturally align on the same row. The host widget is
    # the canonical container we reparent between the editor and
    # the popout window ??same widget tree, no state duplication.
    self._color_row_host = QWidget(main_col)
    color_row = QHBoxLayout(self._color_row_host)
    color_row.setContentsMargins(0, 0, 0, 0)
    color_row.setSpacing(0)
    # Wrap the colour panel in a QScrollArea so a short editor
    # window can scroll instead of crushing the fixed-size knobs /
    # wheels into each other. The popout window reparents the
    # whole ``_color_row_host`` (scroll area included) so the
    # scroll bar follows the panel into the floating window ??and
    # disappears there because the popout is tall enough to fit
    # everything natively.
    _color_scroll = QScrollArea(self._color_row_host)
    _color_scroll.setWidget(self._build_color_compact_palette_panel(_color_scroll))
    _color_scroll.setWidgetResizable(True)
    _color_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    _color_scroll.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded,
    )
    _color_scroll.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAsNeeded,
    )
    # Floor on the visible scroll area itself ??guarantees the user
    # always sees at least a wheel row of content even when the
    # main column is squeezed to its minimum.
    _color_scroll.setMinimumHeight(220)
    _color_scroll.setMaximumHeight(250)
    _color_scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        "QScrollArea > QWidget > QWidget { background: transparent; }"
        + editor_scrollbar_qss()
    )
    color_row.addWidget(_color_scroll, 1)
    # The row host should never collapse below the scroll area
    # either ??same defensive pattern.
    self._color_row_host.setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum,
    )
    self._color_row_host.setMinimumHeight(220)
    self._color_row_host.setMaximumHeight(250)
    # (color_row_host added above timeline ??see earlier addWidget near _timeline_section_host)
    # Remember where to put the host back after a popout closes.
    self._color_root_layout = root
    self._color_root_index = 2  # index in root: after preview, before timeline
    self._color_popout: "ColorPopoutWindow | None" = None
    # Placeholder shown in-place while the host is in the popout.
    self._color_placeholder: QLabel | None = None
    # Click-to-reveal: the color dock is hidden by
    # default and only appears when a Color-grading node is
    # selected in the workbench NodeGraph. Saves vertical space
    # for the timeline during plain capture / trim sessions while
    # keeping the wheels at full horizontal size when actually
    # grading. ``_update_color_dock_visibility()`` flips both the
    # header strip and the row host based on
    # ``self._node_grade_target``.
    self._color_header_widget.hide()
    self._color_row_host.hide()

    # Move color section ABOVE the timeline using a QSplitter so the user
    # can drag the divider to give the color wheels more vertical space.
    # The splitter replaces the plain stretch-based layout that was causing
    # the wheels to be vertically clipped when window height was limited.
    _color_container = QWidget(main_col)
    _cc_layout = QVBoxLayout(_color_container)
    _cc_layout.setContentsMargins(0, 0, 0, 0)
    _cc_layout.setSpacing(0)
    _cc_layout.addWidget(self._color_header_widget)
    _cc_layout.addWidget(self._mask_toolbar_widget)
    _cc_layout.addWidget(self._color_row_host, 1)
    self._color_container = _color_container
    self._color_container.setMaximumHeight(330)
    self._color_container.hide()  # hidden until a Color node is selected

    color_timeline_splitter = QSplitter(Qt.Orientation.Vertical, main_col)
    color_timeline_splitter.setChildrenCollapsible(False)
    color_timeline_splitter.setHandleWidth(2)
    color_timeline_splitter.addWidget(_color_container)
    color_timeline_splitter.addWidget(self._timeline_section_host)
    # Default split: compact color dock gets a short palette strip; the
    # timeline keeps the dominant editing surface.
    # Qt will honour these proportionally on first show.
    color_timeline_splitter.setSizes([230, 300])
    color_timeline_splitter.setStretchFactor(0, 0)
    color_timeline_splitter.setStretchFactor(1, 1)
    self._color_timeline_splitter = color_timeline_splitter

    # Remove the bare _timeline_section_host from root and replace with
    # the splitter at the same position.
    _tl_idx = self._timeline_root_layout.indexOf(self._timeline_section_host)
    self._timeline_root_layout.removeWidget(self._timeline_section_host)
    self._timeline_root_layout.insertWidget(_tl_idx, color_timeline_splitter, 1)
    self._yield_startup_ui("color_timeline_splitter")

    # Point popout plumbing at the color_container's layout so
    # reparenting in _toggle_color_popout / _on_color_popout_closed works.
    self._color_root_layout = _cc_layout
    self._color_root_index = 2  # after header + mask toolbar

    # Keep AI command entry inside the Workbench overflow stack instead
    # of spanning the full editor width. Default collapsed, like Media
    # Pool side sections; opening it reveals the prompt controls.
    self._ai_command_section_host = QWidget(self._right_dock_host)
    self._ai_command_section_host.setObjectName("WorkbenchSectionHost")
    self._ai_command_section_host.setProperty("compactOpenedHeight", AI_COMMAND_HOST_OPEN_HEIGHT)
    self._ai_command_section_host.setProperty("compactClosedHeight", AI_COMMAND_HOST_CLOSED_HEIGHT)
    ai_command_layout = QVBoxLayout(self._ai_command_section_host)
    ai_command_layout.setContentsMargins(0, 0, 0, 0)
    ai_command_layout.setSpacing(0)
    self._ai_command_dock = self._build_ai_command_dock(self._ai_command_section_host)
    self._ai_command_header = self._make_collapsible_section_header(
        tr("veditor.section.ai_command"),
        "workbench",
        [self._ai_command_dock],
        start_open=False,
    )
    self._ai_command_header.setFixedHeight(36)
    ai_command_layout.addWidget(self._ai_command_header)
    ai_command_layout.addWidget(self._ai_command_dock, stretch=0)
    self._right_dock_layout.addWidget(self._ai_command_section_host, stretch=0)
    self._ai_command_root_layout = ai_command_layout
    self._ai_command_root_index = ai_command_layout.indexOf(self._ai_command_dock)
    self._ai_command_popout: QDialog | None = None
    self._ai_command_placeholder: QLabel | None = None
    self._ai_command_hide_after_restore = False
