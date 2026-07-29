"""Compact accessibility QA result panel for Painter UI."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.painter_i18n import painter_text


_RULE_LABELS = {
    "accessible_name": "Accessible name is missing",
    "focus_order_unique": "Focus order is duplicated",
    "focus_target_available": "Focus target is unavailable",
    "touch_target_size": "Touch target is too small",
    "text_contrast": "Text contrast is too low",
    "reading_order": "Focus order conflicts with visual order",
}


class PainterUIAccessibilityPanel(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIAccessibilityPanel")
        self.setStyleSheet(
            """
            QWidget#PainterUIAccessibilityPanel {
                background-color: #15191f;
                color: #dce5f0;
            }
            QWidget#PainterUIAccessibilityPanel QLabel {
                color: #c8d2df;
                background: transparent;
            }
            QWidget#PainterUIAccessibilityPanel QListWidget {
                background-color: #10151c;
                color: #dce5f0;
                border: 1px solid #293441;
                border-radius: 4px;
                outline: none;
            }
            QWidget#PainterUIAccessibilityPanel QListWidget::item {
                padding: 4px 5px;
                border-bottom: 1px solid #202833;
            }
            QWidget#PainterUIAccessibilityPanel QListWidget::item:selected {
                background-color: #33465f;
            }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(painter_text("Accessibility QA"))
        self.title_label.setObjectName("PainterUIPanelSectionTitle")
        self.summary_label = QLabel(painter_text("Not checked"))
        self.summary_label.setObjectName("PainterUIMeta")
        self.summary_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.summary_label)
        root.addLayout(header)

        self.coverage_label = QLabel(
            painter_text("Run Product QA to inspect the current UI document.")
        )
        self.coverage_label.setObjectName("PainterUIMeta")
        self.coverage_label.setWordWrap(True)
        root.addWidget(self.coverage_label)

        self.issue_list = QListWidget()
        self.issue_list.setObjectName("PainterUIAccessibilityIssueList")
        self.issue_list.setFrameShape(QFrame.Shape.NoFrame)
        self.issue_list.setAlternatingRowColors(False)
        self.issue_list.setWordWrap(True)
        self.issue_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.issue_list.setMinimumHeight(92)
        self.issue_list.setMaximumHeight(180)
        root.addWidget(self.issue_list)
        self.set_report(None)

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        payload = report if isinstance(report, Mapping) else {}
        counts = payload.get("severity_counts")
        counts = counts if isinstance(counts, Mapping) else {}
        issues = payload.get("issues")
        issues = issues if isinstance(issues, list) else []
        coverage = payload.get("coverage")
        coverage = coverage if isinstance(coverage, Mapping) else {}

        self.issue_list.clear()
        if not payload:
            self.summary_label.setText(painter_text("Not checked"))
            self.coverage_label.setText(
                painter_text("Run Product QA to inspect the current UI document.")
            )
            self._add_empty_item(painter_text("No audit report yet"))
            return

        error_count = int(counts.get("error") or 0)
        warning_count = int(counts.get("warning") or 0)
        self.summary_label.setText(
            painter_text("{errors} errors · {warnings} warnings").format(
                errors=error_count,
                warnings=warning_count,
            )
        )
        self.coverage_label.setText(
            painter_text(
                "{objects} objects · contrast {checked} checked"
                " · {unknown} unknown"
            ).format(
                objects=int(coverage.get("object_count") or 0),
                checked=int(coverage.get("contrast_checked") or 0),
                unknown=int(coverage.get("contrast_unknown") or 0),
            )
        )
        if not issues:
            self._add_empty_item(painter_text("No accessibility issues found"))
            return
        for issue in issues:
            if not isinstance(issue, Mapping):
                continue
            severity = str(issue.get("severity") or "info").strip().casefold()
            name = str(issue.get("object_name") or issue.get("object_id") or "Document")
            rule_id = str(issue.get("rule_id") or "")
            message = painter_text(
                _RULE_LABELS.get(
                    rule_id,
                    str(issue.get("message") or rule_id),
                )
            )
            item = QListWidgetItem(
                f"{severity.upper()} · {name}\n{message}"
            )
            item.setData(Qt.ItemDataRole.UserRole, str(issue.get("object_id") or ""))
            remediation = str(issue.get("remediation") or "")
            if remediation:
                item.setToolTip(remediation)
            if severity == "error":
                item.setForeground(QColor("#E28A83"))
            elif severity == "warning":
                item.setForeground(QColor("#D3B06F"))
            self.issue_list.addItem(item)

    def _add_empty_item(self, text: str) -> None:
        item = QListWidgetItem(str(text))
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(QColor("#8793A4"))
        self.issue_list.addItem(item)


__all__ = ["PainterUIAccessibilityPanel"]
