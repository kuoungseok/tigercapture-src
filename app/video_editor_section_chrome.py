from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)

from app.icons import app_icon, icon_size


_COLLAPSIBLE_HEADER_NAMES = {
    "CollapsibleSectionHeader",
    "MediaPoolCollapsibleSectionHeader",
}

_SECTION_HEADER_HEIGHT = 36
_SECTION_ICON_BUTTON_HEIGHT = 27


def make_section_header(title: str, accent: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(title.upper(), parent)
    label.setProperty("sectionHeader", "true")
    label.setProperty("accent", accent)
    return label


def make_header_popout_button(
    title: str,
    parent: QWidget,
    callback: Callable[..., None],
    *,
    install_icon_pulse: Callable[..., None] | None = None,
    button_size: int = 18,
    icon_px: int = 10,
    pulse_peak: int = 13,
) -> QPushButton:
    popout_btn = QPushButton("", parent)
    popout_btn.setObjectName("PreviewPopoutIcon")
    popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    popout_btn.setToolTip(f"Pop out {title}")
    popout_btn.setFixedSize(button_size, max(button_size, int(round(button_size * 1.5))))
    popout_btn.setText("")
    popout_btn.setIcon(app_icon("popout", size=icon_px))
    popout_btn.setIconSize(icon_size(icon_px))
    if install_icon_pulse is not None:
        install_icon_pulse(popout_btn, peak=pulse_peak)
    popout_btn.clicked.connect(callback)
    return popout_btn


def make_collapsible_section_header(
    parent: QWidget,
    title: str,
    accent: str,
    controlled_widgets: list[QWidget],
    *,
    start_open: bool = True,
    on_open: Callable[[], list[QWidget] | tuple[QWidget, ...] | None] | None = None,
    popout_callback: Callable[..., None] | None = None,
    install_icon_pulse: Callable[..., None] | None = None,
) -> QWidget:
    """Build the reusable chrome for collapsible editor sections."""
    row = QWidget(parent)
    row.setObjectName(
        "MediaPoolCollapsibleSectionHeader"
        if accent == "media_pool"
        else "CollapsibleSectionHeader"
    )
    row.setProperty("accent", accent)
    row.setFixedHeight(_SECTION_HEADER_HEIGHT)
    row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 5, 0)
    layout.setSpacing(0)
    layout.addWidget(make_section_header(title, accent, row), stretch=1)

    if popout_callback is not None:
        layout.addWidget(
            make_header_popout_button(
                title,
                row,
                popout_callback,
                install_icon_pulse=install_icon_pulse,
            )
        )

    toggle = QPushButton("", row)
    toggle.setObjectName("SectionDisclosure")
    toggle.setProperty("accent", accent)
    toggle.setCheckable(True)
    toggle.setCursor(Qt.CursorShape.PointingHandCursor)
    toggle.setToolTip(f"Show or hide {title}")
    toggle.setFixedSize(18, _SECTION_ICON_BUTTON_HEIGHT)
    toggle.setIcon(app_icon("chevron-down", size=10))
    toggle.setIconSize(icon_size(10))
    layout.addWidget(toggle)

    def _apply(opened: bool) -> None:
        row.setVisible(True)
        if opened and on_open is not None:
            try:
                loaded = on_open()
                if loaded:
                    controlled_widgets[:] = list(loaded)
            except Exception:
                pass
        for widget in controlled_widgets:
            widget.setVisible(bool(opened))
        _set_disclosure_state(toggle, opened, title)
        _set_header_collapsed_state(row, opened)
        host = row.parentWidget()
        if host is not None:
            host.setVisible(True)
            _set_host_height(
                host,
                opened,
                default_min_height=max(42, row.height() + 2),
            )
            if opened:
                _ensure_host_visible_in_scroll(host)
        row.updateGeometry()

    toggle.toggled.connect(_apply)
    toggle.setChecked(bool(start_open))
    _apply(bool(start_open))
    return row


def set_collapsible_host_open(host: QWidget | None, opened: bool) -> None:
    if host is None:
        return
    host.setVisible(True)
    _set_host_height(host, opened, default_min_height=42 if not opened else 220)
    for btn in _header_disclosure_buttons(host):
        try:
            btn.blockSignals(True)
            btn.setChecked(bool(opened))
            _set_disclosure_state(btn, opened, "section")
            header = btn.parentWidget()
            if header is not None:
                header.setVisible(True)
                _set_header_collapsed_state(header, opened)
        finally:
            try:
                btn.blockSignals(False)
            except Exception:
                pass
    layout = host.layout()
    if layout is not None:
        for idx in range(layout.count()):
            item = layout.itemAt(idx)
            widget = item.widget() if item is not None else None
            if widget is None:
                continue
            if widget.objectName() in _COLLAPSIBLE_HEADER_NAMES:
                widget.setVisible(True)
            else:
                widget.setVisible(bool(opened))
    if opened:
        _ensure_host_visible_in_scroll(host)


def _set_host_height(host: QWidget, opened: bool, *, default_min_height: int) -> None:
    try:
        compact_height = host.property("compactOpenedHeight")
        compact_closed_height = host.property("compactClosedHeight")
        if compact_height is not None or (not opened and compact_closed_height is not None):
            target_height = int(
                compact_height
                if opened and compact_height is not None
                else (compact_closed_height or 28)
            )
            host.setMinimumHeight(target_height)
            host.setMaximumHeight(target_height)
        else:
            host.setMinimumHeight(default_min_height)
            host.setMaximumHeight(16777215)
        host.updateGeometry()
    except Exception:
        pass


def _set_disclosure_state(button: QPushButton, opened: bool, target_label: str) -> None:
    state_label = "Hide" if opened else "Show"
    button.setText("")
    button.setIcon(app_icon("chevron-down" if opened else "chevron-right", size=10))
    button.setIconSize(icon_size(10))
    button.setAccessibleName(f"{state_label} {target_label}")
    button.setStatusTip(f"{state_label} {target_label}")
    button.setProperty("stateText", state_label)
    button.setToolTip(f"{state_label} {target_label}")


def _set_header_collapsed_state(header: QWidget, opened: bool) -> None:
    header.setProperty("collapsed", "false" if opened else "true")
    header.style().unpolish(header)
    header.style().polish(header)
    header.updateGeometry()


def _header_disclosure_buttons(host: QWidget) -> list[QPushButton]:
    buttons: list[QPushButton] = []
    layout = host.layout()
    if layout is None:
        return buttons
    for idx in range(layout.count()):
        item = layout.itemAt(idx)
        widget = item.widget() if item is not None else None
        if widget is None or widget.objectName() not in _COLLAPSIBLE_HEADER_NAMES:
            continue
        for child in widget.findChildren(
            QPushButton,
            "SectionDisclosure",
            Qt.FindChildOption.FindDirectChildrenOnly,
        ):
            buttons.append(child)
    return buttons


def _ensure_host_visible_in_scroll(host: QWidget) -> None:
    def _apply() -> None:
        node = host.parentWidget()
        while node is not None:
            if isinstance(node, QScrollArea):
                try:
                    scroll_widget = node.widget()
                    bar = node.verticalScrollBar()
                    if scroll_widget is not None and bar is not None:
                        y = host.mapTo(scroll_widget, QPoint(0, 0)).y()
                        target = max(bar.minimum(), min(bar.maximum(), y - 8))
                        bar.setValue(target)
                    else:
                        node.ensureWidgetVisible(host, 0, 12)
                except Exception:
                    pass
                return
            try:
                node = node.parentWidget()
            except Exception:
                return

    QTimer.singleShot(0, _apply)
