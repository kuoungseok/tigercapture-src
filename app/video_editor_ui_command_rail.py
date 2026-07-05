from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import COLOR_BG_L4, COLOR_BG_L5, COLOR_BG_L6, COLOR_BORDER_DEFAULT, COLOR_TEXT_PRIMARY
from app.video_editor_layout_specs import horizontal_tool_scroll_qss
from app.video_editor_window_widgets import _DraggableLive2DButton, _DraggableSpineButton


def build_command_rail(self) -> None:
    # --- Command rail ---
    toolbar_host = QWidget(self._left_dock_host)
    toolbar_host.setObjectName("AppCommandBar")
    toolbar_host.setProperty("railMode", "true")
    self._command_bar_host = toolbar_host
    self._command_bar_left_rail = True
    toolbar = QHBoxLayout(toolbar_host)
    self._command_bar_layout = toolbar
    toolbar.setContentsMargins(6, 4, 6, 4)
    toolbar.setSpacing(4)

    self.add_track_btn = QPushButton(tr("veditor.btn.add_track"), toolbar_host)
    self.add_track_btn.setObjectName("ToolButton")
    self.add_track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.add_track_btn.clicked.connect(self._add_empty_track)

    self.del_track_btn = QPushButton(tr("veditor.btn.del_track"), toolbar_host)
    self.del_track_btn.setObjectName("ToolButton")
    self.del_track_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.del_track_btn.clicked.connect(self._delete_active_track)

    self.add_audio_btn = QPushButton(tr("veditor.btn.add_audio"), toolbar_host)
    self.add_audio_btn.setObjectName("ToolButton")
    self.add_audio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.add_audio_btn.setToolTip(tr("veditor.audio.add_hint"))
    self.add_audio_btn.clicked.connect(self._add_empty_audio_track)

    self.reset_btn = QPushButton(tr("veditor.btn.reset"), toolbar_host)
    self.reset_btn.setObjectName("ToolButton")
    self.reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.reset_btn.clicked.connect(self._on_reset_active_track)

    # Blade button ??splits the active track's clip at the playhead.
    # Same behaviour as the B/C/Ctrl+K/Ctrl+\\ shortcuts; surfaces
    # the action for users who don't know them.
    self.blade_btn = QToolButton(toolbar_host)
    self.blade_btn.setText(tr("veditor.btn.blade"))
    self.blade_btn.setObjectName("ToolButton")
    self.blade_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.blade_btn.setToolTip(tr("veditor.btn.blade.tooltip"))
    self.blade_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    self.blade_btn.setIcon(app_icon("scissors", size=16))
    self.blade_btn.setIconSize(icon_size(16))
    self._install_icon_pulse(self.blade_btn, peak=24)
    self.blade_btn.clicked.connect(self._blade_at_playhead)

    self.export_btn = QPushButton(tr("veditor.btn.export"), toolbar_host)
    self.export_btn.setObjectName("PrimaryToolButton")
    self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.export_btn.setIcon(app_icon("export", size=16, color="#FFFFFF"))
    self.export_btn.setIconSize(icon_size(16))
    self._install_icon_pulse(self.export_btn, peak=23)
    self.export_btn.clicked.connect(self._on_export)
    self._refresh_export_button_tooltip()

    # Export quality + format dropdowns sit left of the Export
    # button. Default: high quality / mp4 ??matches the pre-tier
    # hardcoded values so existing exports stay byte-equivalent.
    from app.video_exporter import (
        DEFAULT_FORMAT_ID,
        DEFAULT_QUALITY_ID,
        EXPORT_FORMATS,
        QUALITY_PRESETS,
        get_export_format,
        get_quality_preset,
    )
    self._export_quality_id = DEFAULT_QUALITY_ID
    self._export_format_id = DEFAULT_FORMAT_ID
    # Export resolution and FPS presets. None means "original".
    self._export_resolution: "tuple[int,int] | None" = None   # (w, h) or None
    self._export_fps: "float | None" = None                    # fps or None
    _screenstudio_export_defaults = dict(
        (getattr(self, "_project_settings", {}) or {}).get("screenstudio_export_defaults") or {}
    )
    _default_res = _screenstudio_export_defaults.get("resolution")
    if isinstance(_default_res, (tuple, list)) and len(_default_res) >= 2:
        self._export_resolution = (int(_default_res[0]), int(_default_res[1]))
    _default_fps = _screenstudio_export_defaults.get("fps")
    if _default_fps:
        try:
            self._export_fps = float(_default_fps)
        except Exception:
            self._export_fps = None
    self._refresh_export_button_tooltip()

    _TOOLBTN_QSS = (
        f"QToolButton#{{name}} {{ "
        f"background-color: rgba(255,255,255,16); color: #F8F4EA; "
        f"border: 1px solid #37405A; border-radius: 14px; "
        f"padding: 0px 24px 0px 12px; font-size: 11px; font-weight: 800; min-height: 36px; }}"
        f"QToolButton#{{name}}:hover {{ "
        f"background-color: rgba(255,255,255,30); border-color: #7580A5; }}"
        f"QToolButton#{{name}}:pressed {{ "
        f"background-color: rgba(255,255,255,24); }}"
        f"QToolButton#{{name}}::menu-indicator {{ "
        f"image: none; subcontrol-origin: padding; "
        f"subcontrol-position: right center; right: 8px; }}"
    )

    self.resolution_btn = QToolButton(toolbar_host)
    self.resolution_btn.setObjectName("ResolutionDropdown")
    self.resolution_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.resolution_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self.resolution_btn.setToolTip(tr("veditor.export.resolution.tooltip"))
    self.resolution_btn.setMinimumHeight(38)
    self.resolution_btn.setStyleSheet(
        _TOOLBTN_QSS.replace("{name}", "ResolutionDropdown")
    )
    self._refresh_resolution_btn_label()
    self._install_lazy_menu_builder(self.resolution_btn, self._build_resolution_menu)

    self.fps_btn = QToolButton(toolbar_host)
    self.fps_btn.setObjectName("FpsDropdown")
    self.fps_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.fps_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self.fps_btn.setToolTip(tr("veditor.export.fps.tooltip"))
    self.fps_btn.setMinimumHeight(38)
    self.fps_btn.setStyleSheet(
        _TOOLBTN_QSS.replace("{name}", "FpsDropdown")
    )
    self._refresh_fps_btn_label()
    self._install_lazy_menu_builder(self.fps_btn, self._build_fps_menu)

    self.quality_btn = QToolButton(toolbar_host)
    self.quality_btn.setObjectName("QualityDropdown")
    self.quality_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.quality_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self.quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
    self.quality_btn.setMinimumHeight(38)
    self.quality_btn.setStyleSheet(
        _TOOLBTN_QSS.replace("{name}", "QualityDropdown")
    )
    self._refresh_quality_btn_label()
    self._install_lazy_menu_builder(self.quality_btn, self._build_quality_menu)

    # Format dropdown ??sibling of quality_btn, identical styling.
    self.format_btn = QToolButton(toolbar_host)
    self.format_btn.setObjectName("FormatDropdown")
    self.format_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.format_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self.format_btn.setToolTip(tr("veditor.export.format.tooltip"))
    self.format_btn.setMinimumHeight(38)
    self.format_btn.setStyleSheet(
        _TOOLBTN_QSS.replace("{name}", "FormatDropdown")
    )
    self._refresh_format_btn_label()
    self._install_lazy_menu_builder(self.format_btn, self._build_format_menu)

    self.zoom_out_btn = QPushButton("-", toolbar_host)
    self.zoom_out_btn.setObjectName("ToolButton")
    self.zoom_out_btn.setFixedWidth(32)
    self.zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.zoom_out_btn.setToolTip("Zoom timeline out (Ctrl+-)")
    self.zoom_out_btn.clicked.connect(lambda: self._change_zoom(0.6667))

    self.zoom_label = QLabel(self._format_zoom(), toolbar_host)
    self.zoom_label.setObjectName("ZoomLabel")
    self.zoom_label.setFixedWidth(70)
    self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.zoom_label.setToolTip("Timeline zoom: Ctrl+= / Ctrl+- / Ctrl+0")

    self.zoom_in_btn = QPushButton("+", toolbar_host)
    self.zoom_in_btn.setObjectName("ToolButton")
    self.zoom_in_btn.setFixedWidth(32)
    self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.zoom_in_btn.setToolTip("Zoom timeline in (Ctrl+=)")
    self.zoom_in_btn.clicked.connect(lambda: self._change_zoom(1.5))

    self.zoom_fit_btn = QPushButton(tr("veditor.btn.zoom_fit"), toolbar_host)
    self.zoom_fit_btn.setObjectName("ToolButton")
    self.zoom_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.zoom_fit_btn.setToolTip("Fit timeline to visible width (Ctrl+0)")
    self.zoom_fit_btn.clicked.connect(self._zoom_fit)

    # Pop-out icon is shown inside the PREVIEW section header (right
    # end) rather than here, so that it reads as "this control
    # belongs to the preview". Created eagerly so _build_preview_header
    # can reference it, attached there.
    self.popout_btn = QPushButton("", toolbar_host)
    self.popout_btn.setObjectName("PreviewPopoutIcon")
    self.popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
    self.popout_btn.setFixedSize(28, 24)
    self.popout_btn.setText("")
    self.popout_btn.setIcon(app_icon("popout", size=16))
    self.popout_btn.setIconSize(icon_size(16))
    self._install_icon_pulse(self.popout_btn, peak=21)
    self.popout_btn.clicked.connect(self._toggle_preview_popout)

    # Project Save / Load buttons
    self.new_project_btn = QPushButton("+ New", toolbar_host)
    self.new_project_btn.setObjectName("ToolButton")
    self.new_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.new_project_btn.setToolTip("???꾨줈?앺듃 留뚮뱾湲?(Ctrl+N)")
    self.new_project_btn.clicked.connect(self._on_new_project)
    self.new_project_btn.setStyleSheet(
        f"QPushButton{{background:{COLOR_BG_L5}; color:{COLOR_TEXT_PRIMARY};"
        f"border:1px solid {COLOR_BORDER_DEFAULT}; border-radius:4px;"
        "padding:5px 9px; font-size:11px; font-weight:600;}"
        f"QPushButton:hover{{background:{COLOR_BG_L6}; border-color:#4a4a52;}}"
        f"QPushButton:pressed{{background:{COLOR_BG_L4};}}"
    )

    self.save_project_btn = QPushButton("Save", toolbar_host)
    self.save_project_btn.setObjectName("ToolButton")
    self.save_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.save_project_btn.setToolTip("?꾨줈?앺듃 ???(Ctrl+S)")
    self.save_project_btn.clicked.connect(self._on_save_project)

    self.open_project_btn = QPushButton("Open", toolbar_host)
    self.open_project_btn.setObjectName("ToolButton")
    self.open_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.open_project_btn.setToolTip("?꾨줈?앺듃 ?닿린 (Ctrl+O)")
    self.open_project_btn.clicked.connect(self._on_open_project)

    self.recovery_project_btn = QPushButton("Recovery", toolbar_host)
    self.recovery_project_btn.setObjectName("ToolButton")
    self.recovery_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.recovery_project_btn.setToolTip("Find and open the newest autosave/recovery project")
    self.recovery_project_btn.clicked.connect(self._show_recovery_candidates)

    self.relink_project_btn = QPushButton("Relink...", toolbar_host)
    self.relink_project_btn.setObjectName("ToolButton")
    self.relink_project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.relink_project_btn.setToolTip("Find missing project media under selected search folders")
    self.relink_project_btn.clicked.connect(self._on_relink_project_media)

    self.media_health_btn = QPushButton("Health", toolbar_host)
    self.media_health_btn.setObjectName("ToolButton")
    self.media_health_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.media_health_btn.setToolTip(
        "Audit media, relink/proxy state, project stability, timeline, color, audio, and preview/export readiness"
    )
    self.media_health_btn.clicked.connect(self._show_media_health)

    self.command_palette_btn = QToolButton(toolbar_host)
    self.command_palette_btn.setObjectName("CommandMenuButton")
    self.command_palette_btn.setText("")
    self.command_palette_btn.setIcon(app_icon("search", size=18))
    self.command_palette_btn.setIconSize(icon_size(18))
    self.command_palette_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.command_palette_btn.setFixedSize(42, 40)
    self.command_palette_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.command_palette_btn.setToolTip("Command Palette: search media, presets, and commands (Ctrl+Shift+P)")
    self._install_icon_pulse(self.command_palette_btn, base=18, peak=23)
    self.command_palette_btn.clicked.connect(self._open_command_palette)

    self.language_btn = QToolButton(toolbar_host)
    self.language_btn.setObjectName("CommandMenuButton")
    self.language_btn.setText("")
    self.language_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.language_btn.setFixedSize(42, 40)
    self.language_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.language_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self._refresh_language_button()
    self._install_icon_pulse(self.language_btn, base=18, peak=23)
    self._install_lazy_menu_builder(self.language_btn, self._build_language_menu)

    self.template_browser_btn = QToolButton(toolbar_host)
    self.template_browser_btn.setObjectName("CommandMenuButton")
    self.template_browser_btn.setText("")
    self.template_browser_btn.setIcon(app_icon("spark", size=18))
    self.template_browser_btn.setIconSize(icon_size(18))
    self.template_browser_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.template_browser_btn.setFixedSize(42, 40)
    self.template_browser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.template_browser_btn.setProperty("startupTemplate", False)
    self.template_browser_btn.setToolTip("Templates: browse one-click editing templates")
    self._install_icon_pulse(self.template_browser_btn, base=18, peak=23)
    self.template_browser_btn.clicked.connect(self._open_template_browser)

    self.creator_assist_btn = QToolButton(toolbar_host)
    self.creator_assist_btn.setObjectName("CommandMenuButton")
    self.creator_assist_btn.setText("")
    self.creator_assist_btn.setIcon(app_icon("spark", size=18, color="#FFFFFF"))
    self.creator_assist_btn.setIconSize(icon_size(18))
    self.creator_assist_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.creator_assist_btn.setFixedSize(42, 40)
    self.creator_assist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    creator_assist_enabled = self._capcut_feature_enabled("creator_assist")
    self.creator_assist_btn.setToolTip(
        tr("veditor.creator_assist.tooltip")
        if creator_assist_enabled
        else self._capcut_disabled_reason("creator_assist")
    )
    self.creator_assist_btn.setEnabled(creator_assist_enabled)
    self.creator_assist_btn.setVisible(creator_assist_enabled)
    if creator_assist_enabled:
        self._install_icon_pulse(self.creator_assist_btn, base=18, peak=24)
        self.creator_assist_btn.clicked.connect(self._open_creator_assist_panel)

    self.script_edit_btn = QToolButton(toolbar_host)
    self.script_edit_btn.setObjectName("CommandMenuButton")
    self.script_edit_btn.setText("")
    self.script_edit_btn.setIcon(app_icon("ai-script", size=18, color="#FFFFFF"))
    self.script_edit_btn.setIconSize(icon_size(18))
    self.script_edit_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.script_edit_btn.setFixedSize(42, 40)
    self.script_edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.script_edit_btn.setToolTip(tr("veditor.script_edit.tooltip"))
    self._install_icon_pulse(self.script_edit_btn, base=18, peak=24)
    self.script_edit_btn.clicked.connect(self._toggle_ai_command_dock)

    self.auto_polish_btn = QToolButton(toolbar_host)
    self.auto_polish_btn.setObjectName("CommandMenuButton")
    self.auto_polish_btn.setText("")
    self.auto_polish_btn.setIcon(app_icon("spark", size=18, color="#FFFFFF"))
    self.auto_polish_btn.setIconSize(icon_size(18))
    self.auto_polish_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.auto_polish_btn.setFixedSize(42, 40)
    self.auto_polish_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.auto_polish_btn.setToolTip(
        "Auto Polish: tune Screen Studio-style cursor, zoom, and wallpaper polish"
    )
    self._install_icon_pulse(self.auto_polish_btn, base=18, peak=24)
    self.auto_polish_btn.clicked.connect(self._open_screenstudio_polish_panel)

    self.screenstudio_subtitle_btn = QToolButton(toolbar_host)
    self.screenstudio_subtitle_btn.setObjectName("CommandMenuButton")
    self.screenstudio_subtitle_btn.setText("")
    self.screenstudio_subtitle_btn.setIcon(app_icon("caption", size=18, color="#FFFFFF"))
    self.screenstudio_subtitle_btn.setIconSize(icon_size(18))
    self.screenstudio_subtitle_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.screenstudio_subtitle_btn.setFixedSize(42, 40)
    self.screenstudio_subtitle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.screenstudio_subtitle_btn.setToolTip("Captions: import SRT or generate AI subtitles")
    self.screenstudio_subtitle_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    self._install_icon_pulse(self.screenstudio_subtitle_btn, base=18, peak=23)
    self.screenstudio_subtitle_btn.clicked.connect(self._import_screenstudio_srt_subtitles)
    self._install_lazy_action_menu(
        self.screenstudio_subtitle_btn,
        (
            ("Import SRT", self._import_screenstudio_srt_subtitles),
            ("AI Subtitles", self._generate_ai_subtitles),
        ),
        object_name="CaptionCommandMenu",
    )

    self.workspace_mode_switch = QFrame(toolbar_host)
    self.workspace_mode_switch.setObjectName("WorkspaceModeSwitch")
    self.workspace_mode_switch.setToolTip(
        "Workspace mode: Standard shows the full editor; Simple keeps Media Pool and Workbench while hiding secondary panels."
    )
    self.workspace_mode_switch.setFixedHeight(40)
    workspace_mode_layout = QHBoxLayout(self.workspace_mode_switch)
    workspace_mode_layout.setContentsMargins(4, 4, 4, 4)
    workspace_mode_layout.setSpacing(4)
    self.workspace_mode_group = QButtonGroup(self)
    self.workspace_mode_group.setExclusive(True)
    self.workspace_standard_btn = QPushButton("Standard", self.workspace_mode_switch)
    self.workspace_standard_btn.setObjectName("WorkspaceModeButton")
    self.workspace_standard_btn.setCheckable(True)
    self.workspace_standard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.workspace_standard_btn.setToolTip("?쇰컲 ?뚰겕?ㅽ럹?댁뒪: 紐⑤뱺 ?몄쭛 ?⑤꼸???쒖떆")
    self.workspace_simple_btn = QPushButton("Simple", self.workspace_mode_switch)
    self.workspace_simple_btn.setObjectName("WorkspaceModeButton")
    self.workspace_simple_btn.setCheckable(True)
    self.workspace_simple_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.workspace_simple_btn.setToolTip("?ы뵆 ?뚰겕?ㅽ럹?댁뒪: 誘몃뵒???怨??뚰겕踰ㅼ튂瑜??좎??섍퀬 蹂댁“ ?⑤꼸留??④?")
    self.workspace_mode_group.addButton(self.workspace_standard_btn)
    self.workspace_mode_group.addButton(self.workspace_simple_btn)
    workspace_mode_layout.addWidget(self.workspace_standard_btn)
    workspace_mode_layout.addWidget(self.workspace_simple_btn)
    self.workspace_standard_btn.clicked.connect(lambda: self._on_workspace_mode_selected(False))
    self.workspace_simple_btn.clicked.connect(lambda: self._on_workspace_mode_selected(True))

    self.screenstudio_advanced_btn = QPushButton("Panels", toolbar_host)
    self.screenstudio_advanced_btn.setObjectName("ToolButton")
    self.screenstudio_advanced_btn.setCheckable(True)
    self.screenstudio_advanced_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.screenstudio_advanced_btn.setToolTip("Show secondary preset, render, audio, and subtitle panels")
    self.screenstudio_advanced_btn.clicked.connect(self._on_screenstudio_advanced_toggled)

    # Spine rendering is still under repair, so keep the editor entry hidden
    # until the runtime path is visually stable.
    self.spine_editor_btn = QPushButton("Spine", toolbar_host)
    self.spine_editor_btn.setObjectName("ToolButton")
    self.spine_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.spine_editor_btn.setToolTip("Spine 由ш퉭 ?먮뵒???닿린")
    self.spine_editor_btn.clicked.connect(self._open_spine_editor)
    self.spine_editor_btn.hide()

    toolbar.addWidget(self.new_project_btn)
    toolbar.addWidget(self.open_project_btn)
    toolbar.addWidget(self.recovery_project_btn)
    toolbar.addWidget(self.relink_project_btn)
    toolbar.addWidget(self.media_health_btn)
    toolbar.addWidget(self.command_palette_btn)
    toolbar.addWidget(self.language_btn)
    toolbar.addWidget(self.template_browser_btn)
    toolbar.addWidget(self.creator_assist_btn)
    toolbar.addWidget(self.script_edit_btn)
    toolbar.addWidget(self.auto_polish_btn)
    toolbar.addWidget(self.screenstudio_subtitle_btn)
    toolbar.addWidget(self.workspace_mode_switch)
    toolbar.addWidget(self.screenstudio_advanced_btn)
    toolbar.addWidget(self.save_project_btn)
    toolbar.addSpacing(8)
    self.spine_actor_btn = QPushButton("Actor Track", toolbar_host)
    self.spine_actor_btn.setObjectName("ToolButton")
    self.spine_actor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.spine_actor_btn.setToolTip("Spine 罹먮┃???몃옓 異붽?")
    self.spine_actor_btn.clicked.connect(self._add_spine_actor_track)
    self.spine_actor_btn.hide()
    self.live2d_btn = _DraggableLive2DButton("Live2D", toolbar_host)
    self.spine_btn = _DraggableSpineButton("Spine", toolbar_host)
    self.spine_btn.setObjectName("ToolButton")
    self.spine_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.spine_btn.setToolTip(
        "Click: add a Spine actor at the playhead\n"
        "Double-click: open the Spine editor\n"
        "Drag: place a Spine actor on the timeline"
    )
    self.spine_btn.clicked.connect(self._add_spine_actor_at_playhead)
    self.spine_btn.double_clicked.connect(self._open_spine_editor)
    self.live2d_btn.setObjectName("ToolButton")
    self.live2d_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.live2d_btn.setToolTip(
        "?대┃: ?뚮젅?댄뿤???꾩튂??Live2D ?≫꽣 異붽?\n"
        "?붾툝?대┃: Live2D ?먮뵒???닿린"
    )
    self.live2d_btn.clicked.connect(self._add_live2d_actor_at_playhead)
    self.live2d_btn.double_clicked.connect(self._open_live2d_viewer)
    toolbar.addWidget(self.spine_btn)
    toolbar.addWidget(self.live2d_btn)
    self.vtuber_studio_btn = QToolButton(toolbar_host)
    self.vtuber_studio_btn.setObjectName("CommandMenuButton")
    self.vtuber_studio_btn.setText("")
    self.vtuber_studio_btn.setIcon(app_icon("video", size=18, color="#FFFFFF"))
    self.vtuber_studio_btn.setIconSize(icon_size(18))
    self.vtuber_studio_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.vtuber_studio_btn.setFixedSize(42, 40)
    self.vtuber_studio_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.vtuber_studio_btn.setToolTip(
        "VTuber Studio: Program Output, Source Tracking, and Avatar Mapping"
    )
    self._install_icon_pulse(self.vtuber_studio_btn, base=18, peak=24)
    self.vtuber_studio_btn.clicked.connect(self._open_vtuber_broadcast_studio)
    toolbar.addWidget(self.vtuber_studio_btn)
    toolbar.addSpacing(8)
    toolbar.addWidget(self.reset_btn)
    toolbar.addStretch(1)
    toolbar.addWidget(self.zoom_out_btn)
    toolbar.addWidget(self.zoom_label)
    toolbar.addWidget(self.zoom_in_btn)
    toolbar.addWidget(self.zoom_fit_btn)
    toolbar.addSpacing(10)

    # Audio Scopes toggle button
    self.audio_scopes_btn = QPushButton("Scopes", toolbar_host)
    self.audio_scopes_btn.setObjectName("ToolButton")
    self.audio_scopes_btn.setCheckable(True)
    self.audio_scopes_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.audio_scopes_btn.setToolTip("Toggle Audio Scopes panel (Goniometer + LUFS)")
    self.audio_scopes_btn.toggled.connect(self._on_audio_scopes_toggled)
    toolbar.addWidget(self.audio_scopes_btn)
    toolbar.addSpacing(10)

    # Proxy toggle button ??checkable; enables proxy playback for
    # high-resolution sources so editing stays smooth.
    self.proxy_btn = QPushButton("", toolbar_host)
    self.proxy_btn.setObjectName("ToolButton")
    self.proxy_btn.setCheckable(True)
    self.proxy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.proxy_btn.setFixedSize(42, 40)
    self.proxy_btn.setIcon(app_icon("proxy", size=18))
    self.proxy_btn.setIconSize(icon_size(18))
    self._install_icon_pulse(self.proxy_btn, base=18, peak=23)
    self.proxy_btn.setToolTip(
        "Use fresh 540p proxy files for smoother high-resolution editing."
    )
    self.proxy_btn.toggled.connect(self._toggle_proxy_mode)
    toolbar.addWidget(self.proxy_btn)
    self.proxy_manage_btn = QToolButton(toolbar_host)
    self.proxy_manage_btn.setObjectName("CommandMenuButton")
    self.proxy_manage_btn.setText("")
    self.proxy_manage_btn.setIcon(app_icon("layers", size=18))
    self.proxy_manage_btn.setIconSize(icon_size(18))
    self.proxy_manage_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    self.proxy_manage_btn.setFixedSize(42, 40)
    self._install_icon_pulse(self.proxy_manage_btn, base=18, peak=23)
    self.proxy_manage_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.proxy_manage_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self.proxy_manage_btn.setToolTip("Generate, refresh, or delete the selected source proxy.")
    self.proxy_refresh_action = QAction("Generate / Refresh selected proxy", self)
    self.proxy_delete_action = QAction("Delete selected proxy", self)
    self.proxy_refresh_action.triggered.connect(self._regenerate_proxy_for_active_source)
    self.proxy_delete_action.triggered.connect(self._delete_proxy_for_active_source)
    def _ensure_proxy_menu() -> None:
        if self.proxy_manage_btn.menu() is not None:
            return
        menu = QMenu(self.proxy_manage_btn)
        menu.setObjectName("ProxyCommandMenu")
        menu.addAction(self.proxy_refresh_action)
        menu.addAction(self.proxy_delete_action)
        self.proxy_manage_btn.setMenu(menu)
    self._ensure_proxy_manage_menu = _ensure_proxy_menu
    self.proxy_manage_btn.pressed.connect(_ensure_proxy_menu)
    toolbar.addWidget(self.proxy_manage_btn)
    self.proxy_status_label = QLabel("Original", toolbar_host)
    self.proxy_status_label.setObjectName("ProxyStatusLabel")
    self.proxy_status_label.setMinimumWidth(82)
    self.proxy_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self.proxy_status_label.setStyleSheet(
        "color: #C9CEDC; font-size: 11px; font-weight: 700; padding: 7px 10px;"
        "border: 1px solid #30384F; border-radius: 13px;"
        "background-color: rgba(255,255,255,12);"
    )
    toolbar.addWidget(self.proxy_status_label)
    toolbar.addSpacing(4)

    toolbar.addWidget(self.resolution_btn)
    toolbar.addWidget(self.fps_btn)
    toolbar.addWidget(self.format_btn)
    toolbar.addWidget(self.quality_btn)
    toolbar.addWidget(self.export_btn)

    # Batch export button ??opens the batch-export queue dialog for
    # all timeline marker segments.
    self.batch_export_btn = QPushButton("Batch Export", toolbar_host)
    self.batch_export_btn.setObjectName("ToolButton")
    self.batch_export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self.batch_export_btn.setToolTip(
        "Queue timeline marker ranges for sequential export."
    )
    self.batch_export_btn.clicked.connect(self._on_batch_export)
    toolbar.addWidget(self.batch_export_btn)
    self.batch_export_btn.setText("Render Queue")
    self.batch_export_btn.setToolTip(
        "Queue timeline marker ranges for sequential export."
    )

    self._compact_command_bar(toolbar)
    toolbar_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    self._command_bar_scroll = QScrollArea(self._left_dock_host)
    self._command_bar_scroll.setObjectName("CommandBarScroll")
    self._command_bar_scroll.setWidget(toolbar_host)
    self._command_bar_scroll.setWidgetResizable(True)
    self._command_bar_scroll.setFrameShape(QFrame.Shape.NoFrame)
    self._command_bar_scroll.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
    )
    self._command_bar_scroll.setVerticalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
    )
    self._command_bar_scroll.setMinimumHeight(38)
    self._command_bar_scroll.setMaximumHeight(42)
    self._command_bar_scroll.setStyleSheet(horizontal_tool_scroll_qss("QScrollArea#CommandBarScroll"))
    self._left_dock_layout.addWidget(self._command_bar_scroll, stretch=0)
    try:
        self._main_dock_splitter.splitterMoved.connect(lambda *_args: self._refresh_command_bar_responsive())
    except Exception:
        pass
    QTimer.singleShot(0, self._refresh_command_bar_responsive)
    self._yield_startup_ui("top_toolbar")
