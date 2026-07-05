from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMenu, QPushButton

from app.i18n import SUPPORTED_LANGUAGES, current_language, save_language, set_language, tr
from app.icons import app_icon, icon_size
from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_BG_L3,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_PRIMARY,
)


def _language_display_name(self, code: str | None = None) -> str:
    active = str(code or current_language() or "").strip()
    return SUPPORTED_LANGUAGES.get(active, active.upper() or "Language")


def _refresh_language_button(self) -> None:
    btn = getattr(self, "language_btn", None)
    if btn is None:
        return
    label = self._language_display_name()
    btn.setAccessibleName(tr("settings.language"))
    btn.setToolTip(f"{tr('settings.language')}: {label}")
    btn.setText("")
    btn.setIcon(app_icon("language", size=18))
    btn.setIconSize(icon_size(18))


def _build_language_menu(self) -> None:
    btn = getattr(self, "language_btn", None)
    if btn is None:
        return
    menu = QMenu(btn)
    menu.setObjectName("LanguageMenu")
    menu.setStyleSheet(
        f"QMenu#LanguageMenu {{ "
        f"background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
        f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 6px; "
        f"padding: 6px; font-size: 12px; }}"
        f"QMenu#LanguageMenu::item {{ padding: 8px 18px 8px 34px; border-radius: 4px; }}"
        f"QMenu#LanguageMenu::item:selected {{ background-color: {COLOR_BG_L5}; }}"
        f"QMenu#LanguageMenu::item:checked {{ background-color: {COLOR_ACCENT_BLUE}; font-weight: 700; }}"
        f"QMenu#LanguageMenu::indicator {{ width: 16px; height: 16px; left: 10px; }}"
    )
    active = current_language()
    for code, name in SUPPORTED_LANGUAGES.items():
        act = menu.addAction(str(name))
        act.setCheckable(True)
        act.setChecked(code == active)
        act.triggered.connect(lambda _checked=False, c=code: self._on_language_picked(c))
    btn.setMenu(menu)


def _refresh_collapsible_header_title(self, key: str, title: str) -> None:
    row = getattr(self, "_localized_collapsible_headers", {}).get(key)
    if row is None:
        return
    label = row.findChild(QLabel)
    if label is not None:
        label.setText(str(title).upper())
    toggle = row.findChild(QPushButton)
    if toggle is not None:
        toggle.setToolTip(f"{toggle.text()} {title}")


def _refresh_top_project_breadcrumb(self) -> None:
    try:
        project_name = self._current_project_name()
    except Exception:
        project_name = "Untitled"
    text = f"Project > {project_name}"
    label = getattr(self, "_top_breadcrumb_label", None)
    if label is not None:
        label.setText(text)
    viewer_label = getattr(self, "_viewer_project_breadcrumb_label", None)
    if viewer_label is not None:
        viewer_label.setText(text)


def _refresh_localized_ui(self) -> None:
    self.setWindowTitle(tr("veditor.title"))
    if hasattr(self, "add_track_btn"):
        self.add_track_btn.setText(tr("veditor.btn.add_track"))
    if hasattr(self, "del_track_btn"):
        self.del_track_btn.setText(tr("veditor.btn.del_track"))
    if hasattr(self, "add_audio_btn"):
        self.add_audio_btn.setText(tr("veditor.btn.add_audio"))
        self.add_audio_btn.setToolTip(tr("veditor.audio.add_hint"))
    if hasattr(self, "reset_btn"):
        self.reset_btn.setText(tr("veditor.btn.reset"))
    if hasattr(self, "blade_btn"):
        self.blade_btn.setText(tr("veditor.btn.blade"))
        self.blade_btn.setToolTip(tr("veditor.btn.blade.tooltip"))
    if hasattr(self, "export_btn"):
        self.export_btn.setText("")
        self._refresh_export_button_tooltip()
    if hasattr(self, "zoom_fit_btn"):
        self.zoom_fit_btn.setText(tr("veditor.btn.zoom_fit"))
    if hasattr(self, "popout_btn"):
        self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
    if hasattr(self, "timeline_popout_btn"):
        self.timeline_popout_btn.setToolTip(tr("veditor.timeline_popout.tooltip"))
    if hasattr(self, "color_popout_btn"):
        self.color_popout_btn.setToolTip(tr("veditor.color_popout.tooltip"))
    if hasattr(self, "workbench_popout_btn"):
        docked = (
            getattr(self, "_workbench_popout", None) is not None
            and self._workbench_popout.isVisible()
        )
        self.workbench_popout_btn.setToolTip(
            tr("veditor.workbench_popout.tooltip_docked")
            if docked
            else tr("veditor.workbench_popout.tooltip")
        )
    self._refresh_top_project_breadcrumb()
    if hasattr(self, "_preview_section_label"):
        self._preview_section_label.setText("Viewer")
    if hasattr(self, "_timeline_section_label"):
        self._timeline_section_label.setText(tr("veditor.section.timeline").upper())
    if hasattr(self, "_color_section_label"):
        self._color_section_label.setText(tr("veditor.section.color").upper())
    if hasattr(self, "_workbench_header_title"):
        self._workbench_header_title.setText(tr("veditor.section.workbench").upper())
    if getattr(self, "_preview_placeholder_kind", "") == "empty" and hasattr(self, "_preview_label"):
        self._preview_label.setText(tr("veditor.no_file"))
    self._refresh_collapsible_header_title("media_pool", tr("veditor.section.media_pool"))
    self._refresh_collapsible_header_title("effects", tr("veditor.section.effects"))
    if hasattr(self, "resolution_btn"):
        self.resolution_btn.setToolTip(tr("veditor.export.resolution.tooltip"))
        self._refresh_resolution_btn_label()
        self.resolution_btn.setMenu(None)
    if hasattr(self, "fps_btn"):
        self.fps_btn.setToolTip(tr("veditor.export.fps.tooltip"))
        self._refresh_fps_btn_label()
        self.fps_btn.setMenu(None)
    if hasattr(self, "quality_btn"):
        self.quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
        self._refresh_quality_btn_label()
        self.quality_btn.setMenu(None)
    if hasattr(self, "format_btn"):
        self.format_btn.setToolTip(tr("veditor.export.format.tooltip"))
        self._refresh_format_btn_label()
        self.format_btn.setMenu(None)
    if hasattr(self, "language_btn"):
        self._refresh_language_button()
        self.language_btn.setMenu(None)
    for row in list(getattr(self, "_track_rows", {}).values()):
        try:
            row.update()
        except Exception:
            pass


def _on_language_picked(self, code: str) -> None:
    code = str(code or "").strip()
    if code not in SUPPORTED_LANGUAGES:
        return
    set_language(code)
    save_language(code)
    self._refresh_localized_ui()
    self._flash_status(tr("veditor.language.changed", language=self._language_display_name(code)))


def _apply_professional_ui_labels(self) -> None:
    """Normalize the high-traffic editor chrome labels.

    Older strings in this file come from several encoding eras; keep this
    narrow pass focused on always-visible controls so the main workspace is
    readable before the broader i18n cleanup.
    """
    replacements = {
        "new_project_btn": "New",
        "open_project_btn": "Open",
        "recovery_project_btn": "Recovery",
        "save_project_btn": "Save",
        "reset_btn": "Reset",
        "add_track_btn": "Video +",
        "add_audio_btn": "Audio +",
        "del_track_btn": "Delete",
        "blade_btn": "Split",
        "export_btn": "Export",
        "batch_export_btn": "Batch",
        "relink_project_btn": "Relink",
        "media_health_btn": "Health",
        "spine_editor_btn": "Spine Editor",
        "spine_actor_btn": "Actor Track",
        "spine_btn": "Spine",
        "live2d_btn": "Live2D",
        "zoom_out_btn": "-",
        "zoom_in_btn": "+",
        "zoom_fit_btn": "Fit",
        "audio_scopes_btn": "Scopes",
        "audio_scopes_tl_btn": "Scope",
        "audio_mixer_tl_btn": "Mixer",
        "mark_in_btn": "Mark In",
        "mark_out_btn": "Mark Out",
        "clear_sel_btn": "Clear",
        "add_marker_btn": "Marker",
        "precision_trim_btn": "Trim",
        "nest_btn": "Nest",
        "_page_edit_btn": "Edit",
        "_page_color_btn": "Color",
        "_pip_add_kf_btn": "Keyframe +",
        "_pip_del_kf_btn": "Delete",
    }
    icon_only_attrs = {
        "mark_in_btn",
        "mark_out_btn",
        "clear_range_btn",
        "clear_sel_btn",
        "add_marker_btn",
        "_page_edit_btn",
        "_page_color_btn",
    }
    for attr, text in replacements.items():
        widget = getattr(self, attr, None)
        if widget is not None and hasattr(widget, "setText"):
            if attr in icon_only_attrs:
                widget.setText("")
                if hasattr(widget, "setToolTip"):
                    widget.setToolTip(text)
            else:
                widget.setText(text)
    icons = {
        "new_project_btn": ("plus", "#D7DAE7"),
        "open_project_btn": ("project", "#D7DAE7"),
        "save_project_btn": ("save", "#D7DAE7"),
        "recovery_project_btn": ("reset", "#D7DAE7"),
        "relink_project_btn": ("link", "#D7DAE7"),
        "media_health_btn": ("health", "#D7DAE7"),
        "add_track_btn": ("video", "#D7DAE7"),
        "add_audio_btn": ("audio", "#D7DAE7"),
        "del_track_btn": ("trash", "#D7DAE7"),
        "reset_btn": ("reset", "#D7DAE7"),
        "spine_editor_btn": ("bone", "#D7DAE7"),
        "spine_actor_btn": ("actors", "#D7DAE7"),
        "spine_btn": ("bone", "#FFFFFF"),
        "live2d_btn": ("live2d", "#FFFFFF"),
        "mark_in_btn": ("mark-in", "#D7DAE7"),
        "mark_out_btn": ("mark-out", "#D7DAE7"),
        "clear_range_btn": ("x", "#D7DAE7"),
        "clear_sel_btn": ("clear", "#D7DAE7"),
        "add_marker_btn": ("marker", "#F3F5F8"),
        "precision_trim_btn": ("sliders", "#D7DAE7"),
        "nest_btn": ("nest", "#D7DAE7"),
        "blade_btn": ("scissors", "#D7DAE7"),
        "export_btn": ("export", "#FFFFFF"),
        "audio_scopes_btn": ("scopes", "#D7DAE7"),
        "audio_scopes_tl_btn": ("scopes", "#D7DAE7"),
        "audio_mixer_tl_btn": ("mixer", "#D7DAE7"),
        "_audio_workspace_edit_btn": ("audio", "#D7DAE7"),
        "_audio_workspace_mixer_btn": ("mixer", "#D7DAE7"),
        "_audio_workspace_scopes_btn": ("scopes", "#D7DAE7"),
        "_page_edit_btn": ("cursor", "#D7DAE7"),
        "_page_color_btn": ("color", "#D7DAE7"),
        "_pip_add_kf_btn": ("keyframe", "#D7DAE7"),
        "_pip_del_kf_btn": ("trash", "#D7DAE7"),
        "proxy_btn": ("proxy", "#D7DAE7"),
        "proxy_manage_btn": ("layers", "#D7DAE7"),
        "auto_polish_btn": ("spark", "#FFFFFF"),
        "zoom_fit_btn": ("fit", "#D7DAE7"),
        "zoom_review_btn": ("zoom", "#D7DAE7"),
    }
    for attr, (name, color) in icons.items():
        widget = getattr(self, attr, None)
        if widget is None or not hasattr(widget, "setIcon"):
            continue
        icon_px = 22 if str(widget.objectName()) == "ToolTile" else 16
        widget.setIcon(app_icon(name, size=icon_px, color=color))
        widget.setIconSize(icon_size(icon_px))
        if attr in icon_only_attrs and hasattr(widget, "setText"):
            widget.setText("")
        self._install_icon_pulse(widget, base=icon_px, peak=28 if icon_px > 16 else 22)
