"""Compact Painter UI panel for inspecting and repairing Motion links."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


MOTION_LINK_REPORT_SCHEMA = "tigerstudio.painter.ui.motion_links.v2"
MOTION_LINK_STATUSES = (
    "ok",
    "legacy_link",
    "missing_binding",
    "missing_composition",
    "stale_revision",
    "orphan_object",
)

_STATUS_COPY = {
    "ok": ("Ready", "The Painter object and Motion binding are synchronized."),
    "legacy_link": (
        "Legacy link",
        "This link uses a composition ID and should be migrated to a binding ID.",
    ),
    "missing_binding": (
        "Missing binding",
        "The Motion composition exists, but its referenced binding cannot be found.",
    ),
    "missing_composition": (
        "Missing composition",
        "The linked Motion composition is unavailable. Relink it to continue.",
    ),
    "stale_revision": (
        "Stale revision",
        "Painter references an older Motion composition revision.",
    ),
    "orphan_object": (
        "Orphan object",
        "The link points to a Painter object that no longer exists.",
    ),
}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _links(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _selected_link(report: Mapping[str, Any]) -> dict[str, Any]:
    direct = _mapping(report.get("link") or report.get("selected_link"))
    if direct:
        return direct
    rows = _links(report.get("links"))
    selected_id = str(
        report.get("selected_object_id")
        or report.get("object_id")
        or ""
    )
    if selected_id:
        return next(
            (row for row in rows if str(row.get("object_id") or "") == selected_id),
            {},
        )
    return rows[0] if rows else {}


class PainterUIMotionBindingPanel(QWidget):
    """Read-only Motion link status with explicit repair requests."""

    migrate_requested = Signal(str)
    relink_requested = Signal(str, str, str)
    detach_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterMotionBindingPanel")
        self._report: dict[str, Any] = {}
        self._object_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        heading_row = QHBoxLayout()
        heading = QLabel("Motion Link")
        heading.setObjectName("painterPanelSectionTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        self.status_badge = QLabel("No report")
        self.status_badge.setObjectName("painterMotionLinkStatus")
        heading_row.addWidget(self.status_badge)
        root.addLayout(heading_row)

        self.empty_label = QLabel(
            "No Motion link report. Select a linked UI object to inspect it."
        )
        self.empty_label.setObjectName("painterMutedLabel")
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("painterMotionLinkSummary")
        summary_layout = QVBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(8, 7, 8, 7)
        summary_layout.setSpacing(3)
        self.object_label = QLabel("No object selected")
        self.object_label.setObjectName("painterMotionLinkObject")
        self.status_detail_label = QLabel("")
        self.status_detail_label.setObjectName("painterMutedLabel")
        self.status_detail_label.setWordWrap(True)
        self.identifiers_label = QLabel("")
        self.identifiers_label.setObjectName("painterMotionLinkIdentifiers")
        self.identifiers_label.setTextInteractionFlags(
            self.identifiers_label.textInteractionFlags()
        )
        self.identifiers_label.setWordWrap(True)
        summary_layout.addWidget(self.object_label)
        summary_layout.addWidget(self.status_detail_label)
        summary_layout.addWidget(self.identifiers_label)
        root.addWidget(self.summary_frame)

        repair_frame = QFrame()
        repair_frame.setObjectName("painterMotionLinkRepair")
        repair_layout = QVBoxLayout(repair_frame)
        repair_layout.setContentsMargins(8, 7, 8, 7)
        repair_layout.setSpacing(5)

        relink_title = QLabel("Relink")
        relink_title.setObjectName("painterMotionLinkSubheading")
        repair_layout.addWidget(relink_title)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(4)
        self.composition_id_edit = QLineEdit()
        self.composition_id_edit.setPlaceholderText("Motion composition ID")
        self.binding_id_edit = QLineEdit()
        self.binding_id_edit.setPlaceholderText("Canonical binding ID")
        form.addRow("Composition", self.composition_id_edit)
        form.addRow("Binding", self.binding_id_edit)
        repair_layout.addLayout(form)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        self.migrate_button = QPushButton("Migrate")
        self.migrate_button.setToolTip(
            "Request migration from a legacy composition link to a canonical binding."
        )
        self.migrate_button.clicked.connect(
            lambda: self.migrate_requested.emit(self._object_id)
        )
        self.relink_button = QPushButton("Relink")
        self.relink_button.clicked.connect(self._emit_relink)
        action_row.addWidget(self.migrate_button)
        action_row.addWidget(self.relink_button)
        repair_layout.addLayout(action_row)

        self.detach_warning_label = QLabel(
            "Detach removes this Painter-to-Motion link. "
            "The Motion composition is not deleted."
        )
        self.detach_warning_label.setObjectName("painterMotionDetachWarning")
        self.detach_warning_label.setWordWrap(True)
        repair_layout.addWidget(self.detach_warning_label)
        self.detach_button = QPushButton("Detach Link")
        self.detach_button.setObjectName("painterMotionDangerButton")
        self.detach_button.setToolTip(
            "Danger: request removal of the selected object's Motion link."
        )
        self.detach_button.clicked.connect(
            lambda: self.detach_requested.emit(self._object_id)
        )
        repair_layout.addWidget(self.detach_button)
        root.addWidget(repair_frame)
        root.addStretch(1)

        self.composition_id_edit.textChanged.connect(self._update_relink_enabled)
        self.binding_id_edit.textChanged.connect(self._update_relink_enabled)

        self.setStyleSheet(
            """
            QWidget#painterMotionBindingPanel {
                background: #11161E;
                color: #E8EDF3;
            }
            QFrame#painterMotionLinkSummary, QFrame#painterMotionLinkRepair {
                background: #171E28;
                border: 1px solid #2A3442;
                border-radius: 5px;
            }
            QLabel#painterMotionLinkObject,
            QLabel#painterMotionLinkSubheading {
                color: #F2F5F8;
                font-weight: 600;
            }
            QLabel#painterMutedLabel, QLabel#painterMotionLinkIdentifiers {
                color: #9BA8B7;
            }
            QLabel#painterMotionLinkStatus {
                color: #9EC5FF;
                background: #1C2C42;
                border: 1px solid #365677;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QLabel#painterMotionLinkStatus[severity="warning"] {
                color: #E4C48A;
                background: #30291C;
                border-color: #665538;
            }
            QLabel#painterMotionLinkStatus[severity="error"] {
                color: #E4A097;
                background: #35201F;
                border-color: #70413D;
            }
            QLabel#painterMotionDetachWarning {
                color: #D7A29B;
            }
            QLineEdit {
                min-height: 24px;
                color: #E8EDF3;
                background: #10151D;
                border: 1px solid #354357;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton {
                min-height: 24px;
                color: #E8EDF3;
                background: #202A38;
                border: 1px solid #354357;
                border-radius: 4px;
                padding: 2px 9px;
            }
            QPushButton:hover {
                background: #29374A;
                border-color: #55749A;
            }
            QPushButton:disabled {
                color: #66717F;
                background: #171C24;
                border-color: #252D38;
            }
            QPushButton#painterMotionDangerButton {
                color: #F0C0B9;
                background: #34201F;
                border-color: #74423D;
            }
            QPushButton#painterMotionDangerButton:hover {
                background: #462725;
                border-color: #A45A52;
            }
            """
        )
        self.set_report(None)

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        self._report = _mapping(report)
        if not self._report:
            self._show_empty(
                "No Motion link report. Select a linked UI object to inspect it."
            )
            return
        if str(self._report.get("schema") or "") != MOTION_LINK_REPORT_SCHEMA:
            self._show_empty("This Motion link report is not a supported v2 report.")
            return

        link = _selected_link(self._report)
        if not link:
            self._show_empty("The selected UI object has no Motion link.")
            return

        self._object_id = str(link.get("object_id") or "")
        status = str(link.get("status") or "missing_binding").strip().casefold()
        if status not in MOTION_LINK_STATUSES:
            status = "missing_binding"
        title, detail = _STATUS_COPY[status]
        severity = (
            "ok"
            if status == "ok"
            else "warning"
            if status in {"legacy_link", "stale_revision"}
            else "error"
        )
        self.status_badge.setText(title)
        self.status_badge.setProperty("severity", severity)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)
        self.status_badge.setVisible(True)
        self.empty_label.setVisible(False)
        self.summary_frame.setVisible(True)

        object_name = str(
            link.get("object_name")
            or self._report.get("object_name")
            or self._object_id
            or "Motion link"
        )
        composition_id = str(link.get("composition_id") or "")
        binding_id = str(
            link.get("binding_id")
            or link.get("resolved_binding_id")
            or ""
        )
        linked_revision = int(link.get("composition_revision") or 0)
        current_revision = int(link.get("current_composition_revision") or 0)
        self.object_label.setText(object_name)
        self.status_detail_label.setText(detail)
        self.identifiers_label.setText(
            f"Composition  {composition_id or 'Not set'}\n"
            f"Binding  {binding_id or 'Not set'}\n"
            f"Revision  {linked_revision} linked / {current_revision} current"
        )

        self.composition_id_edit.blockSignals(True)
        self.binding_id_edit.blockSignals(True)
        self.composition_id_edit.setText(composition_id)
        self.binding_id_edit.setText(binding_id)
        self.composition_id_edit.blockSignals(False)
        self.binding_id_edit.blockSignals(False)

        has_object = bool(self._object_id)
        self.migrate_button.setEnabled(has_object and status == "legacy_link")
        self.detach_button.setEnabled(has_object)
        self.detach_warning_label.setVisible(has_object)
        self._update_relink_enabled()

    def _show_empty(self, text: str) -> None:
        self._object_id = ""
        self.empty_label.setText(text)
        self.empty_label.setVisible(True)
        self.summary_frame.setVisible(False)
        self.status_badge.setText("No link")
        self.status_badge.setProperty("severity", "warning")
        self.status_badge.setVisible(False)
        self.composition_id_edit.clear()
        self.binding_id_edit.clear()
        self.migrate_button.setEnabled(False)
        self.relink_button.setEnabled(False)
        self.detach_button.setEnabled(False)
        self.detach_warning_label.setVisible(False)

    def _update_relink_enabled(self) -> None:
        self.relink_button.setEnabled(
            bool(
                self._object_id
                and self.composition_id_edit.text().strip()
                and self.binding_id_edit.text().strip()
            )
        )

    def _emit_relink(self) -> None:
        if not self.relink_button.isEnabled():
            return
        self.relink_requested.emit(
            self._object_id,
            self.composition_id_edit.text().strip(),
            self.binding_id_edit.text().strip(),
        )


__all__ = [
    "MOTION_LINK_REPORT_SCHEMA",
    "MOTION_LINK_STATUSES",
    "PainterUIMotionBindingPanel",
]
