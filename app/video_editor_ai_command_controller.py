from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.video_editor_ai_command_dock import (
    AI_COMMAND_DOCK_MAX_HEIGHT,
    AI_COMMAND_DOCK_MIN_HEIGHT,
    AI_COMMAND_DOCK_QSS,
)


class _ZeroMinimumWidget(QWidget):
    """Container that may shrink below child size hints in compact windows."""

    def minimumSizeHint(self) -> QSize:  # pragma: no cover - covered by UI QA
        return QSize(0, 0)


def build_ai_command_dock(owner, parent: QWidget) -> QWidget:
    dock = _ZeroMinimumWidget(parent)
    dock.setObjectName("AICommandDock")
    dock.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    dock.setMinimumHeight(AI_COMMAND_DOCK_MIN_HEIGHT)
    dock.setMaximumHeight(AI_COMMAND_DOCK_MAX_HEIGHT)
    dock.setStyleSheet(AI_COMMAND_DOCK_QSS)

    root = QVBoxLayout(dock)
    root.setContentsMargins(4, 0, 4, 0)
    root.setSpacing(0)

    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(3)

    badge = QLabel("AI", dock)
    badge.setObjectName("AICommandBadge")
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setFixedSize(19, 17)
    row.addWidget(badge)

    owner._ai_command_provider_combo = QComboBox(dock)
    owner._ai_command_provider_combo.setObjectName("AICommandProviderCombo")
    owner._ai_command_provider_combo.setMinimumHeight(18)
    owner._ai_command_provider_combo.setMaximumHeight(20)
    owner._ai_command_provider_combo.setMaximumWidth(96)
    owner._ai_command_provider_combo.currentIndexChanged.connect(owner._on_ai_command_provider_changed)
    row.addWidget(owner._ai_command_provider_combo)
    owner._ai_command_provider_loading = False

    setup_btn = QToolButton(dock)
    setup_btn.setObjectName("AICommandIconButton")
    setup_btn.setIcon(app_icon("settings", size=12, color="#DDE3F7"))
    setup_btn.setIconSize(icon_size(12))
    setup_btn.setFixedSize(18, 18)
    setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    setup_btn.setToolTip(tr("veditor.ai_command.setup.tooltip"))
    setup_btn.clicked.connect(owner._open_ai_provider_setup_dialog)
    row.addWidget(setup_btn)
    owner._ai_command_provider_setup_btn = setup_btn

    owner._ai_command_input = QLineEdit(dock)
    owner._ai_command_input.setObjectName("AICommandInput")
    owner._ai_command_input.setMinimumWidth(80)
    owner._ai_command_input.setMaximumHeight(20)
    owner._ai_command_input.setPlaceholderText(tr("veditor.ai_command.placeholder"))
    owner._ai_command_input.returnPressed.connect(owner._generate_ai_command_plan)
    row.addWidget(owner._ai_command_input, stretch=1)

    run_btn = QPushButton(tr("veditor.ai_command.run"), dock)
    run_btn.setObjectName("AICommandRunButton")
    run_btn.setIcon(app_icon("ai-script", size=12, color="#FFFFFF"))
    run_btn.setIconSize(icon_size(12))
    run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    run_btn.setFixedWidth(36)
    run_btn.setMaximumHeight(20)
    run_btn.setToolTip(tr("veditor.ai_command.status.default"))
    run_btn.clicked.connect(owner._generate_ai_command_plan)
    row.addWidget(run_btn)
    owner._ai_command_run_btn = run_btn

    review_btn = QPushButton(tr("veditor.ai_command.review"), dock)
    review_btn.setObjectName("AICommandReviewButton")
    review_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    review_btn.setFixedWidth(42)
    review_btn.setMaximumHeight(20)
    review_btn.clicked.connect(owner._open_ai_command_review_panel)
    row.addWidget(review_btn)
    owner._ai_command_review_btn = review_btn

    popout_btn = QToolButton(dock)
    popout_btn.setObjectName("AICommandIconButton")
    popout_btn.setIcon(app_icon("popout", size=12, color="#DDE3F7"))
    popout_btn.setIconSize(icon_size(12))
    popout_btn.setFixedSize(18, 18)
    popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    popout_btn.setToolTip(tr("veditor.ai_command.popout.tooltip"))
    popout_btn.clicked.connect(owner._toggle_ai_command_popout)
    row.addWidget(popout_btn)
    owner._ai_command_popout_btn = popout_btn

    close_btn = QToolButton(dock)
    close_btn.setObjectName("AICommandIconButton")
    close_btn.setIcon(app_icon("x", size=12, color="#DDE3F7"))
    close_btn.setIconSize(icon_size(12))
    close_btn.setFixedSize(18, 18)
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.setToolTip(tr("veditor.ai_command.hide.tooltip"))
    close_btn.clicked.connect(owner._hide_ai_command_dock)
    row.addWidget(close_btn)
    owner._ai_command_close_btn = close_btn

    root.addLayout(row)

    owner._ai_command_chat_log = QPlainTextEdit(dock)
    owner._ai_command_chat_log.setObjectName("AICommandChatLog")
    owner._ai_command_chat_log.setReadOnly(True)
    owner._ai_command_chat_log.setMinimumHeight(0)
    owner._ai_command_chat_log.setMaximumHeight(0)
    try:
        owner._ai_command_chat_log.document().setMaximumBlockCount(80)
    except Exception:
        pass
    owner._ai_command_chat_log.setPlaceholderText(tr("veditor.ai_command.chat_placeholder"))
    root.addWidget(owner._ai_command_chat_log)
    owner._ai_command_chat_log.hide()

    owner._ai_command_status = QLabel(tr("veditor.ai_command.status.default"), dock)
    owner._ai_command_status.setObjectName("AICommandStatus")
    owner._ai_command_status.setWordWrap(False)
    owner._ai_command_status.setMaximumHeight(0)
    owner._ai_command_status.setText(tr("veditor.ai_command.status.default"))
    root.addWidget(owner._ai_command_status)
    owner._ai_command_status.hide()

    owner._ai_command_provider_status = QLabel("", dock)
    owner._ai_command_provider_status.setObjectName("AICommandStatus")
    owner._ai_command_provider_status.setWordWrap(False)
    owner._ai_command_provider_status.setMaximumHeight(0)
    root.addWidget(owner._ai_command_provider_status)
    owner._ai_command_provider_status.hide()
    owner._refresh_ai_command_provider_status()
    return dock


def toggle_ai_command_dock(owner) -> None:
    popout = getattr(owner, "_ai_command_popout", None)
    if popout is not None and popout.isVisible():
        popout.raise_()
        popout.activateWindow()
        return
    dock = getattr(owner, "_ai_command_dock", None)
    if dock is None:
        return
    if dock.isVisible():
        owner._hide_ai_command_dock()
    else:
        owner._show_ai_command_dock()


def show_ai_command_dock(owner) -> None:
    dock = getattr(owner, "_ai_command_dock", None)
    if dock is None:
        return
    host = getattr(owner, "_ai_command_section_host", None)
    if host is not None:
        owner._set_collapsible_host_open(host, True)
    else:
        dock.show()
    try:
        owner._ai_command_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        owner._ai_command_input.selectAll()
    except Exception:
        pass
    try:
        owner._flash_status(tr("veditor.ai_command.opened"))
    except Exception:
        pass


def hide_ai_command_dock(owner) -> None:
    popout = getattr(owner, "_ai_command_popout", None)
    if popout is not None and popout.isVisible():
        owner._ai_command_hide_after_restore = True
        popout.close()
        return
    dock = getattr(owner, "_ai_command_dock", None)
    host = getattr(owner, "_ai_command_section_host", None)
    if host is not None:
        owner._set_collapsible_host_open(host, False)
    elif dock is not None:
        dock.hide()


def toggle_ai_command_popout(owner) -> None:
    popout = getattr(owner, "_ai_command_popout", None)
    if popout is not None and popout.isVisible():
        popout.close()
        return

    dock = getattr(owner, "_ai_command_dock", None)
    root = getattr(owner, "_ai_command_root_layout", None)
    if dock is None or root is None:
        return
    dock.show()
    idx = root.indexOf(dock)
    if idx < 0:
        idx = getattr(owner, "_ai_command_root_index", root.count())
    else:
        owner._ai_command_root_index = idx
        root.removeWidget(dock)

    placeholder = QLabel(tr("veditor.ai_command.popout.placeholder"), owner)
    placeholder.setObjectName("AICommandPlaceholder")
    placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    placeholder.setMinimumHeight(46)
    placeholder.setStyleSheet(
        "QLabel#AICommandPlaceholder {"
        " color: rgba(220,225,255,180);"
        " background: rgba(18,20,33,120);"
        " border: 1px dashed rgba(122,99,255,125);"
        " border-radius: 14px;"
        " font-weight: 800;"
        "}"
    )
    root.insertWidget(max(0, idx), placeholder, stretch=0)
    owner._ai_command_placeholder = placeholder

    dialog = QDialog(owner)
    dialog.setObjectName("AICommandPopout")
    dialog.setWindowTitle(tr("veditor.ai_command.popout.title"))
    dialog.setModal(False)
    dialog.resize(820, 132)
    dialog.setStyleSheet(
        "QDialog#AICommandPopout {"
        " background: #11131D;"
        " border: 1px solid rgba(122,99,255,140);"
        "}"
    )
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(0)
    dock.setParent(dialog)
    layout.addWidget(dock)
    owner._ai_command_popout = dialog
    try:
        owner._ai_command_popout_btn.setToolTip(tr("veditor.ai_command.dock.tooltip"))
    except Exception:
        pass
    dialog.finished.connect(lambda _code=0: owner._restore_ai_command_dock_from_popout())
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def restore_ai_command_dock_from_popout(owner) -> None:
    popout = getattr(owner, "_ai_command_popout", None)
    dock = getattr(owner, "_ai_command_dock", None)
    root = getattr(owner, "_ai_command_root_layout", None)
    if popout is None or dock is None or root is None:
        return
    owner._ai_command_popout = None

    try:
        layout = popout.layout()
        if layout is not None:
            layout.removeWidget(dock)
    except Exception:
        pass

    placeholder = getattr(owner, "_ai_command_placeholder", None)
    if placeholder is not None:
        idx = root.indexOf(placeholder)
        root.removeWidget(placeholder)
        placeholder.deleteLater()
        owner._ai_command_placeholder = None
    else:
        idx = getattr(owner, "_ai_command_root_index", root.count())

    dock.setParent(getattr(owner, "_ai_command_section_host", None) or owner)
    root.insertWidget(max(0, idx), dock, stretch=0)
    owner._ai_command_root_index = root.indexOf(dock)
    dock.show()
    try:
        owner._ai_command_popout_btn.setToolTip(tr("veditor.ai_command.popout.tooltip"))
    except Exception:
        pass
    if getattr(owner, "_ai_command_hide_after_restore", False):
        host = getattr(owner, "_ai_command_section_host", None)
        if host is not None:
            owner._set_collapsible_host_open(host, False)
        else:
            dock.hide()
        owner._ai_command_hide_after_restore = False
    else:
        host = getattr(owner, "_ai_command_section_host", None)
        if host is not None:
            owner._set_collapsible_host_open(host, True)
    popout.deleteLater()
