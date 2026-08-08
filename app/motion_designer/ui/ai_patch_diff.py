"""Compact review widget for conversational Motion AI edits."""
from __future__ import annotations

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _display_value(value: object) -> str:
    if isinstance(value, list) and all(
        isinstance(item, dict) and "kind" in item
        for item in value
    ):
        if not value:
            return "None"
        labels = []
        for item in value:
            start_ms = int(item.get("start_ms", 0) or 0)
            end_ms = int(item.get("end_ms", 0) or 0)
            labels.append(
                f"{item.get('kind', 'behavior')} ({start_ms}-{end_ms} ms)"
            )
        return ", ".join(labels)
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
    else:
        text = str(value)
    return text if len(text) <= 120 else f"{text[:117]}..."


class MotionAIPatchDiffWidget(QWidget):
    apply_requested = Signal()
    dismissed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionAIPatchDiff")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 4)
        root.setSpacing(5)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)
        self.table = QTreeWidget(self)
        self.table.setHeaderLabels(["Layer", "Change", "Before", "After"])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setMinimumHeight(128)
        self.table.setColumnWidth(0, 92)
        self.table.setColumnWidth(1, 72)
        self.table.setColumnWidth(2, 96)
        self.table.setColumnWidth(3, 96)
        root.addWidget(self.table)
        actions = QHBoxLayout()
        self.range_label = QLabel(self)
        actions.addWidget(self.range_label)
        actions.addStretch(1)
        dismiss = QPushButton("Dismiss", self)
        dismiss.clicked.connect(self.dismissed.emit)
        actions.addWidget(dismiss)
        apply_button = QPushButton("Apply Revision", self)
        apply_button.setObjectName("MotionPrimaryButton")
        apply_button.clicked.connect(self.apply_requested.emit)
        actions.addWidget(apply_button)
        root.addLayout(actions)
        self.setVisible(False)

    def set_diff(self, report: dict) -> None:
        self.table.clear()
        for row in report.get("rows", []):
            if not isinstance(row, dict):
                continue
            item = QTreeWidgetItem([
                str(row.get("layer_name") or row.get("layer_id") or "Layer"),
                str(row.get("property") or row.get("operation") or "Change"),
                _display_value(row.get("before")),
                _display_value(row.get("after")),
            ])
            item.setToolTip(1, str(row.get("reason") or ""))
            item.setToolTip(2, _display_value(row.get("before")))
            item.setToolTip(3, _display_value(row.get("after")))
            self.table.addTopLevelItem(item)
        count = int(report.get("operation_count", 0) or 0)
        layers = int(report.get("affected_layer_count", 0) or 0)
        self.summary.setText(
            f"{report.get('summary', '')}  {count} change(s) across {layers} layer(s)."
        )
        interval = report.get("affected_range_ms") or [0, 0]
        self.range_label.setText(
            f"Review {float(interval[0]) / 1000:.2f}s - {float(interval[1]) / 1000:.2f}s"
        )
        self.setVisible(True)


__all__ = ["MotionAIPatchDiffWidget"]
