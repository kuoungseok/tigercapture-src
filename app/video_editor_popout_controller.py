from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.i18n import tr
from app.style import COLOR_BG_L2, COLOR_BORDER_DEFAULT, COLOR_TEXT_TERTIARY
from app.video_editor_popouts import MediaPoolPopoutWindow, SectionPopoutWindow, SubtitlePopoutWindow, WorkbenchPopoutWindow


def make_side_dock_placeholder(text: str, *, min_width: int) -> QLabel:
    placeholder = QLabel(text)
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder.setMinimumWidth(max(80, int(min_width)))
    placeholder.setMinimumHeight(160)
    placeholder.setWordWrap(True)
    placeholder.setObjectName("SideDockPlaceholder")
    placeholder.setStyleSheet(
        f"QLabel#SideDockPlaceholder {{"
        f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
        f"background-color: {COLOR_BG_L2}; "
        f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 8px;"
        f"padding: 12px;"
        f"}}"
    )
    return placeholder


def make_side_dock_placeholder_for_owner(self, text: str, *, min_width: int) -> QLabel:
    return make_side_dock_placeholder(text, min_width=min_width)


def toggle_actor_library_popout(self) -> None:
    self._toggle_section_popout("actor_library", "_actor_library_section_host", "Actor Library", width=520, height=520)


def toggle_effects_library_popout(self) -> None:
    self._toggle_section_popout("effects_library", "_effects_library_section_host", "Effect Library", width=620, height=620)


def toggle_title_presets_popout(self) -> None:
    self._toggle_section_popout("title_presets", "_title_presets_section_host", "Title Presets", width=620, height=520)


def toggle_transitions_popout(self) -> None:
    self._toggle_section_popout("transitions", "_transitions_section_host", "Transitions", width=620, height=520)


def toggle_workflow_presets_popout(self) -> None:
    self._toggle_section_popout("workflow_presets", "_workflow_presets_section_host", "Workflow Presets", width=620, height=520)


def toggle_creator_assist_popout(self) -> None:
    self._ensure_creator_assist_panel()
    self._toggle_section_popout("creator_assist", "_creator_assist_section_host", "Creator Assist", width=720, height=560)


def toggle_script_edit_popout(self) -> None:
    self._ensure_ai_script_edit_panel()
    self._toggle_section_popout("script_edit", "_ai_script_edit_section_host", "Script Edit", width=720, height=560)


def toggle_audio_workspace_popout(self) -> None:
    self._toggle_section_popout("audio_workspace", "_audio_workspace_section_host", "Audio Workspace", width=620, height=380)


def toggle_pip_popout(self) -> None:
    self._toggle_section_popout("pip", "_pip_section_host", "PIP", width=420, height=500, min_width=260, min_height=260)


def toggle_subtitle_popout(self) -> None:
    if self._subtitle_popout is not None and self._subtitle_popout.isVisible():
        self._subtitle_popout.close()
        return
    self._subtitle_popout = SubtitlePopoutWindow(self)
    self._subtitle_popout.closed.connect(self._on_subtitle_popout_closed)
    self._subtitle_root_layout.removeWidget(self._subtitle_section_host)
    self._subtitle_placeholder = QLabel(tr("veditor.subtitle_popout.placeholder"))
    self._subtitle_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._subtitle_placeholder.setMinimumHeight(80)
    self._subtitle_placeholder.setWordWrap(True)
    self._subtitle_placeholder.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
        f"background-color: {COLOR_BG_L2}; "
        f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
        f"padding: 12px;"
    )
    self._subtitle_root_layout.insertWidget(self._subtitle_root_index, self._subtitle_placeholder)
    self._subtitle_popout.install(self._subtitle_section_host)
    self._subtitle_popout.show()
    self._subtitle_popout.raise_()
    self._subtitle_popout.activateWindow()


def on_subtitle_popout_closed(self) -> None:
    if self._subtitle_placeholder is not None:
        idx = self._subtitle_root_layout.indexOf(self._subtitle_placeholder)
        self._subtitle_root_layout.removeWidget(self._subtitle_placeholder)
        self._subtitle_placeholder.deleteLater()
        self._subtitle_placeholder = None
    else:
        idx = self._subtitle_root_index
    self._subtitle_section_host.setParent(self)
    self._subtitle_root_layout.insertWidget(max(0, idx), self._subtitle_section_host)
    self._subtitle_section_host.show()
    if self._subtitle_popout is not None:
        self._subtitle_popout.deleteLater()
        self._subtitle_popout = None


def refresh_main_dock_splitter_roles(self) -> None:
    splitter = getattr(self, "_main_dock_splitter", None)
    if splitter is None:
        return
    for widget in (
        getattr(self, "_left_dock_scroll", None),
        getattr(self, "_media_pool_placeholder", None),
    ):
        if widget is not None:
            idx = splitter.indexOf(widget)
            if idx >= 0:
                splitter.setStretchFactor(idx, 1)
    center = getattr(self, "_center_workbench", None)
    if center is not None:
        idx = splitter.indexOf(center)
        if idx >= 0:
            splitter.setStretchFactor(idx, 7)


def toggle_section_popout(
    self,
    key: str,
    host_attr: str,
    title: str,
    *,
    width: int = 560,
    height: int = 480,
    min_width: int = 260,
    min_height: int = 220,
) -> None:
    popouts = getattr(self, "_section_popouts", None)
    if popouts is None:
        self._section_popouts = {}
        popouts = self._section_popouts
    state = popouts.get(key) or {}
    window = state.get("window")
    if window is not None and window.isVisible():
        window.close()
        return
    host = getattr(self, host_attr, None)
    if host is None:
        try:
            self._flash_status(f"{title} panel is not available")
        except Exception:
            pass
        return
    parent = host.parentWidget()
    root_layout = parent.layout() if parent is not None else None
    if root_layout is None:
        return
    root_index = root_layout.indexOf(host)
    if root_index < 0:
        return
    was_visible = bool(host.isVisible())
    root_layout.removeWidget(host)
    host.setParent(None)
    placeholder = self._make_side_dock_placeholder(
        f"{title} is detached.\nClose the window to dock it back.",
        min_width=max(110, min_width // 2),
    )
    placeholder.setMinimumHeight(min(140, max(70, min_height // 3)))
    root_layout.insertWidget(max(0, root_index), placeholder)
    window = SectionPopoutWindow(
        title,
        width=width,
        height=height,
        min_width=min_width,
        min_height=min_height,
        parent=self,
    )
    window_attr = f"_{key}_popout"
    setattr(self, window_attr, window)
    popouts[key] = {
        "window": window,
        "window_attr": window_attr,
        "host": host,
        "host_attr": host_attr,
        "placeholder": placeholder,
        "root_layout": root_layout,
        "root_index": root_index,
        "was_visible": was_visible,
    }
    window.closed.connect(lambda _key=key: self._on_section_popout_closed(_key))
    window.install(host)
    host.show()
    window.show()
    window.raise_()
    window.activateWindow()


def on_section_popout_closed(self, key: str) -> None:
    popouts = getattr(self, "_section_popouts", None)
    if not popouts:
        return
    state = popouts.get(key)
    if not state:
        return
    host = state.get("host")
    placeholder = state.get("placeholder")
    root_layout = state.get("root_layout")
    root_index = int(state.get("root_index", 0) or 0)
    was_visible = bool(state.get("was_visible", True))
    if root_layout is None or host is None:
        popouts.pop(key, None)
        return
    idx = root_index
    if placeholder is not None:
        try:
            idx = root_layout.indexOf(placeholder)
            root_layout.removeWidget(placeholder)
            placeholder.setParent(None)
            placeholder.deleteLater()
        except Exception:
            idx = root_index
    window = state.get("window")
    window_attr = state.get("window_attr")
    if window is not None:
        try:
            layout = window.layout()
            if layout is not None:
                layout.removeWidget(host)
        except Exception:
            pass
    try:
        parent_widget = root_layout.parentWidget()
    except Exception:
        parent_widget = None
    if parent_widget is not None:
        host.setParent(parent_widget)
    root_layout.insertWidget(max(0, idx), host)
    host.setVisible(was_visible)
    if window is not None:
        try:
            window.deleteLater()
        except Exception:
            pass
    if window_attr:
        try:
            setattr(self, str(window_attr), None)
        except Exception:
            pass
    popouts.pop(key, None)


def toggle_media_pool_popout(self) -> None:
    if self._media_pool_popout is not None and self._media_pool_popout.isVisible():
        self._media_pool_popout.close()
        return
    self._media_pool_popout = MediaPoolPopoutWindow(self)
    self._media_pool_popout.closed.connect(self._on_media_pool_popout_closed)
    splitter = self._main_dock_splitter
    self._media_pool_root_index = max(0, splitter.indexOf(self._left_dock_scroll))
    self._left_dock_scroll.setParent(None)
    self._media_pool_placeholder = self._make_side_dock_placeholder(
        tr("veditor.media_pool_popout.placeholder"),
        min_width=126,
    )
    splitter.insertWidget(self._media_pool_root_index, self._media_pool_placeholder)
    self._refresh_main_dock_splitter_roles()
    self._media_pool_popout.install(self._left_dock_scroll)
    self._media_pool_popout.show()
    self._media_pool_popout.raise_()
    self._media_pool_popout.activateWindow()


def on_media_pool_popout_closed(self) -> None:
    splitter = self._main_dock_splitter
    if self._media_pool_placeholder is not None:
        idx = splitter.indexOf(self._media_pool_placeholder)
        self._media_pool_placeholder.setParent(None)
        self._media_pool_placeholder.deleteLater()
        self._media_pool_placeholder = None
    else:
        idx = self._media_pool_root_index
    if self._media_pool_popout is not None:
        layout = self._media_pool_popout.layout()
        if layout is not None:
            layout.removeWidget(self._left_dock_scroll)
    self._left_dock_scroll.setParent(splitter)
    splitter.insertWidget(max(0, idx), self._left_dock_scroll)
    self._left_dock_scroll.show()
    self._refresh_main_dock_splitter_roles()
    if self._media_pool_popout is not None:
        self._media_pool_popout.deleteLater()
        self._media_pool_popout = None


def toggle_workbench_popout(self) -> None:
    if self._workbench_popout is not None and self._workbench_popout.isVisible():
        self._workbench_popout.close()
        return
    host = getattr(self, "_workbench_section_host", None)
    if host is None:
        return
    layout = getattr(self, "_workbench_root_layout", None)
    if layout is None:
        parent = host.parentWidget()
        layout = parent.layout() if parent is not None else None
    if layout is None:
        return
    self._workbench_popout = WorkbenchPopoutWindow(self)
    self._workbench_popout.closed.connect(self._on_workbench_popout_closed)
    self._workbench_root_layout = layout
    self._workbench_root_index = max(0, layout.indexOf(host))
    layout.removeWidget(host)
    host.setParent(None)
    self._workbench_placeholder = self._make_side_dock_placeholder(
        tr("veditor.workbench_popout.placeholder"),
        min_width=150,
    )
    layout.insertWidget(max(0, self._workbench_root_index), self._workbench_placeholder)
    self._workbench_popout.install(host)
    self._workbench_popout.show()
    self._workbench_popout.raise_()
    self._workbench_popout.activateWindow()
    if hasattr(self, "workbench_popout_btn"):
        self.workbench_popout_btn.setProperty("popped", True)
        self.workbench_popout_btn.setToolTip(tr("veditor.workbench_popout.tooltip_docked"))
        self.workbench_popout_btn.style().unpolish(self.workbench_popout_btn)
        self.workbench_popout_btn.style().polish(self.workbench_popout_btn)


def on_workbench_popout_closed(self) -> None:
    layout = getattr(self, "_workbench_root_layout", None)
    host = getattr(self, "_workbench_section_host", None)
    if layout is None or host is None:
        return
    if self._workbench_placeholder is not None:
        idx = layout.indexOf(self._workbench_placeholder)
        layout.removeWidget(self._workbench_placeholder)
        self._workbench_placeholder.setParent(None)
        self._workbench_placeholder.deleteLater()
        self._workbench_placeholder = None
    else:
        idx = self._workbench_root_index
    if self._workbench_popout is not None:
        layout = self._workbench_popout.layout()
        if layout is not None:
            layout.removeWidget(host)
    root_layout = getattr(self, "_workbench_root_layout", None)
    root_parent = None
    try:
        root_parent = root_layout.parentWidget() if root_layout is not None else None
    except Exception:
        root_parent = None
    if root_parent is not None:
        host.setParent(root_parent)
    if root_layout is not None:
        root_layout.insertWidget(max(0, idx), host, stretch=1)
    host.show()
    if hasattr(self, "workbench_popout_btn"):
        self.workbench_popout_btn.setProperty("popped", False)
        self.workbench_popout_btn.setToolTip(tr("veditor.workbench_popout.tooltip"))
        self.workbench_popout_btn.style().unpolish(self.workbench_popout_btn)
        self.workbench_popout_btn.style().polish(self.workbench_popout_btn)
    if self._workbench_popout is not None:
        self._workbench_popout.deleteLater()
        self._workbench_popout = None
