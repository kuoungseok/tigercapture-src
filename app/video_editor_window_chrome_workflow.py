from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QTimer, Qt, QVariantAnimation
from PySide6.QtWidgets import QLabel, QSplitter, QToolButton, QWidget

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import COLOR_BG_L2, COLOR_BORDER_DEFAULT, COLOR_TEXT_TERTIARY
from app.video_editor_command_bar import (
    configure_command_menu_button,
    install_lazy_action_menu,
    show_existing_button_menu as _show_button_menu,
)
from app.video_editor_popouts import TimelinePopoutWindow
from app.video_editor_section_chrome import (
    make_collapsible_section_header as _make_collapsible_section_header_chrome,
    make_section_header as _make_section_header_chrome,
)


def _make_section_header(title: str, accent: str, parent: QWidget | None = None) -> QLabel:
    return _make_section_header_chrome(title, accent, parent)


def _make_command_menu_button(
    self,
    text: str,
    tooltip: str = "",
    parent: QWidget | None = None,
) -> QToolButton:
    btn = QToolButton(parent or self)
    configure_command_menu_button(btn, text, tooltip)
    self._install_icon_pulse(btn, base=16, peak=21)
    return btn


def _install_lazy_action_menu(
    self,
    button: QToolButton,
    entries: tuple,
    *,
    object_name: str = "",
) -> None:
    install_lazy_action_menu(self, button, entries, object_name=object_name)


def _install_lazy_menu_builder(self, button: QToolButton, builder) -> None:
    def _ensure_menu() -> None:
        try:
            if button.menu() is None:
                builder()
        except Exception:
            pass

    try:
        button.pressed.connect(_ensure_menu)
    except Exception:
        pass


def _make_collapsible_section_header(
    self,
    title: str,
    accent: str,
    controlled_widgets: list[QWidget],
    *,
    start_open: bool = True,
    on_open=None,
    popout_callback=None,
) -> QWidget:
    """Build a compact section header for collapsible editor panels."""
    return _make_collapsible_section_header_chrome(
        self,
        title,
        accent,
        controlled_widgets,
        start_open=start_open,
        on_open=on_open,
        popout_callback=popout_callback,
        install_icon_pulse=self._install_icon_pulse,
    )


def _show_existing_button_menu(
    self,
    button_attr: str,
    builder=None,
    *,
    anchor_attr: str = "",
) -> None:
    button = getattr(self, button_attr, None)
    if button is None:
        return
    try:
        if button.menu() is None and builder is not None:
            builder()
        menu = button.menu()
    except Exception:
        menu = None
    if menu is None:
        return
    anchor = getattr(self, anchor_attr, None) if anchor_attr else None
    _show_button_menu(
        self,
        button,
        anchor=anchor,
        fallback_anchor=getattr(self, "_export_menu_btn", None),
    )


def _install_icon_pulse(self, button, *, base: int = 16, peak: int = 22) -> None:
    """Attach a short icon pop on button press."""
    if button is None:
        return
    try:
        button.setIconSize(icon_size(base))
    except Exception:
        return
    if not hasattr(self, "_icon_pulse_animations"):
        self._icon_pulse_animations = []
    if bool(button.property("_iconPulseInstalled")):
        return
    button.setProperty("_iconPulseInstalled", True)

    def _pulse() -> None:
        self._pulse_icon_button(button, base=base, peak=peak, duration=180)

    try:
        button.pressed.connect(_pulse)
    except Exception:
        pass


def _pulse_icon_button(self, button, *, base: int = 18, peak: int = 24, duration: int = 190) -> None:
    if button is None:
        return
    if not hasattr(self, "_icon_pulse_animations"):
        self._icon_pulse_animations = []
    anim = QVariantAnimation(button)
    anim.setDuration(int(duration))
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.setStartValue(int(base))
    anim.setKeyValueAt(0.44, int(peak))
    anim.setEndValue(int(base))
    anim.valueChanged.connect(lambda value: button.setIconSize(icon_size(int(value))))
    anim.finished.connect(
        lambda: self._icon_pulse_animations.remove(anim)
        if anim in self._icon_pulse_animations
        else None
    )
    self._icon_pulse_animations.append(anim)
    anim.start()


def _set_timeline_palette_collapsed(self, collapsed: bool) -> None:
    collapsed = bool(collapsed)
    self._timeline_palette_collapsed = collapsed
    for widget in getattr(self, "_timeline_palette_content_widgets", ()) or ():
        if widget is not None:
            widget.setVisible(not collapsed)
    label = getattr(self, "_timeline_palette_collapsed_label", None)
    if label is not None:
        label.setText(tr("veditor.timeline_tools.collapsed_label"))
        label.setVisible(collapsed)

    scroll = getattr(self, "_timeline_palette_scroll", None)
    if scroll is not None:
        height = 28 if collapsed else 40
        scroll.setMinimumHeight(height)
        scroll.setMaximumHeight(height if collapsed else 42)

    host = getattr(self, "_timeline_palette_host", None)
    if host is not None:
        host.setProperty("collapsed", collapsed)

    btn = getattr(self, "_timeline_palette_toggle_btn", None)
    if btn is not None:
        try:
            btn.blockSignals(True)
            btn.setChecked(collapsed)
        finally:
            btn.blockSignals(False)
        icon_name = "chevron-right" if collapsed else "chevron-down"
        btn.setIcon(app_icon(icon_name, size=12, color="#AEB7C6"))
        btn.setIconSize(icon_size(12))
        btn.setToolTip(
            tr("veditor.timeline_tools.show")
            if collapsed
            else tr("veditor.timeline_tools.hide")
        )

    for widget in (host, scroll, btn, label):
        if widget is None:
            continue
        try:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()
        except Exception:
            pass


def _flash_status(self, msg: str) -> None:
    """Show a short status banner near the editor center."""
    if not hasattr(self, "_status_banner"):
        self._status_banner = QLabel(self)
        self._status_banner.setObjectName("StatusBanner")
        self._status_banner.setStyleSheet(
            "QLabel#StatusBanner {"
            " background-color: rgba(18, 20, 33, 238);"
            " color: #FFFFFF; font-weight: 800; font-size: 12px;"
            " padding: 9px 18px; border-radius: 15px;"
            " border: 1px solid rgba(255, 128, 87, 210); }"
        )
        self._status_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_banner.hide()
        self._status_banner_timer = QTimer(self)
        self._status_banner_timer.setSingleShot(True)
        self._status_banner_timer.timeout.connect(self._status_banner.hide)
    self._status_banner.setText(msg)
    self._status_banner.adjustSize()
    x = max(0, (self.width() - self._status_banner.width()) // 2)
    y = self.height() // 3
    self._status_banner.move(x, y)
    self._status_banner.raise_()
    self._status_banner.show()
    self._status_banner_timer.start(2200)


def _toggle_timeline_popout(self) -> None:
    """Detach or re-attach the timeline section."""
    if self._timeline_popout is not None and self._timeline_popout.isVisible():
        self._timeline_popout.close()
        return
    self._timeline_popout = TimelinePopoutWindow(self)
    self._timeline_popout.closed.connect(self._on_timeline_popout_closed)
    splitter = getattr(self, "_color_timeline_splitter", None)
    if splitter is not None:
        self._timeline_root_index = splitter.indexOf(self._timeline_section_host)
        self._timeline_section_host.setParent(self)
    elif isinstance(self._timeline_root_layout, QSplitter):
        self._timeline_root_index = self._timeline_root_layout.indexOf(
            self._timeline_section_host,
        )
        self._timeline_section_host.setParent(self)
    else:
        self._timeline_root_layout.removeWidget(self._timeline_section_host)
    self._timeline_placeholder = QLabel(tr("veditor.timeline_popout.placeholder"))
    self._timeline_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._timeline_placeholder.setMinimumHeight(120)
    self._timeline_placeholder.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
        f"background-color: {COLOR_BG_L2}; "
        f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
    )
    if splitter is not None:
        splitter.insertWidget(self._timeline_root_index, self._timeline_placeholder)
    elif isinstance(self._timeline_root_layout, QSplitter):
        self._timeline_root_layout.insertWidget(
            self._timeline_root_index,
            self._timeline_placeholder,
        )
    else:
        self._timeline_root_layout.insertWidget(
            self._timeline_root_index,
            self._timeline_placeholder,
            stretch=1,
        )
    self._timeline_popout.install(self._timeline_section_host)
    self._timeline_popout.show()
    self._timeline_popout.raise_()
    self._timeline_popout.activateWindow()


def _on_timeline_popout_closed(self) -> None:
    splitter = getattr(self, "_color_timeline_splitter", None)
    if self._timeline_placeholder is not None:
        if splitter is not None:
            idx = splitter.indexOf(self._timeline_placeholder)
            self._timeline_placeholder.setParent(None)
        elif isinstance(self._timeline_root_layout, QSplitter):
            idx = self._timeline_root_layout.indexOf(self._timeline_placeholder)
            self._timeline_placeholder.setParent(None)
        else:
            idx = self._timeline_root_layout.indexOf(self._timeline_placeholder)
            self._timeline_root_layout.removeWidget(self._timeline_placeholder)
        self._timeline_placeholder.deleteLater()
        self._timeline_placeholder = None
    else:
        idx = self._timeline_root_index
    self._timeline_section_host.setParent(self)
    if splitter is not None:
        splitter.insertWidget(max(0, idx), self._timeline_section_host)
    elif isinstance(self._timeline_root_layout, QSplitter):
        self._timeline_root_layout.insertWidget(
            max(0, idx),
            self._timeline_section_host,
        )
    else:
        self._timeline_root_layout.insertWidget(
            max(0, idx),
            self._timeline_section_host,
            stretch=1,
        )
    self._timeline_section_host.show()
    if self._timeline_popout is not None:
        self._timeline_popout.deleteLater()
        self._timeline_popout = None
