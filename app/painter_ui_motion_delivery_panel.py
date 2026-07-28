"""Compact Painter UI surface for Motion delivery inspection."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


_TARGETS = (
    ("web", "Web UI"),
    ("app", "App UI"),
    ("umg", "Unreal UMG"),
)
_DISPOSITIONS = (
    ("native", "Native"),
    ("vector", "Vector"),
    ("platform_effect", "Effect"),
    ("material", "Material"),
    ("baked", "Baked"),
    ("actor_only", "Actor"),
    ("blocked", "Blocked"),
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _disposition(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "effect": "platform_effect",
        "platformeffect": "platform_effect",
        "actor": "actor_only",
        "actoronly": "actor_only",
    }
    return aliases.get(text, text)


def _reason_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(row).strip() for row in value if str(row).strip()]
    return []


def _binding_from_report(report: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("binding", "animation_binding", "motion_binding"):
        row = _mapping(report.get(key))
        if row:
            return row
    bindings = _rows(report.get("bindings"))
    return bindings[0] if bindings else {}


def _selection_from_report(report: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("selection", "selected_object", "object"):
        row = _mapping(report.get(key))
        if row:
            return row
    return {
        "id": str(report.get("object_id") or ""),
        "name": str(report.get("object_name") or ""),
        "component_id": str(report.get("component_id") or ""),
    }


def _feature_rows(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("features", "feature_results", "feature_reports"):
        rows = _rows(report.get(key))
        if rows:
            return rows
    return []


def _target_result(feature: Mapping[str, Any], target: str) -> dict[str, Any]:
    targets = _mapping(feature.get("targets") or feature.get("delivery_targets"))
    row = _mapping(targets.get(target))
    if row:
        return row
    return _mapping(feature.get(target))


def _aggregate_targets(
    report: Mapping[str, Any],
) -> tuple[dict[str, Counter[str]], dict[str, list[str]]]:
    counts = {target: Counter() for target, _label in _TARGETS}
    blockers = {target: [] for target, _label in _TARGETS}
    features = _feature_rows(report)

    for index, feature in enumerate(features):
        feature_name = str(
            feature.get("feature")
            or feature.get("name")
            or feature.get("property")
            or f"Feature {index + 1}"
        )
        for target, _label in _TARGETS:
            result = _target_result(feature, target)
            disposition = _disposition(
                result.get("resolved")
                or result.get("disposition")
                or result.get("classification")
                or result.get("status")
            )
            if disposition in dict(_DISPOSITIONS):
                counts[target][disposition] += 1
            reasons = _reason_text(
                result.get("reasons")
                or result.get("blockers")
                or result.get("reason")
            )
            if disposition == "blocked" or reasons:
                blockers[target].extend(
                    f"{feature_name}: {reason}" for reason in reasons
                )

    # Also accept reports that already contain per-target aggregate results.
    raw_targets = report.get("targets") or report.get("delivery_targets")
    target_rows = _mapping(raw_targets)
    if isinstance(raw_targets, (list, tuple)):
        target_rows = {
            str(row.get("target") or ""): dict(row)
            for row in raw_targets
            if isinstance(row, Mapping) and row.get("target")
        }
    for target, _label in _TARGETS:
        row = _mapping(target_rows.get(target))
        if not row:
            continue
        supplied_counts = _mapping(row.get("counts"))
        for key, value in supplied_counts.items():
            disposition = _disposition(key)
            if disposition in dict(_DISPOSITIONS):
                try:
                    counts[target][disposition] = int(value)
                except (TypeError, ValueError):
                    pass
        for blocker in _rows(row.get("blockers")):
            feature_name = str(
                blocker.get("feature")
                or blocker.get("name")
                or blocker.get("property")
                or "Feature"
            )
            reasons = _reason_text(
                blocker.get("reasons")
                or blocker.get("reason")
                or blocker.get("message")
            )
            blockers[target].extend(
                f"{feature_name}: {reason}" for reason in reasons
            )
        blockers[target].extend(_reason_text(row.get("reasons")))
        for feature in _rows(row.get("features")):
            if _disposition(feature.get("resolved")) != "blocked":
                continue
            feature_name = str(feature.get("feature") or "Feature")
            blockers[target].extend(
                f"{feature_name}: {reason}"
                for reason in _reason_text(feature.get("reasons"))
            )

    return counts, blockers


class _TargetSummary(QFrame):
    def __init__(self, target: str, title: str, parent=None) -> None:
        super().__init__(parent)
        self.target = target
        self.setObjectName("painterMotionTarget")
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 6, 7, 6)
        root.setSpacing(3)
        heading = QLabel(title)
        heading.setObjectName("painterMotionTargetTitle")
        root.addWidget(heading)

        self.count_labels: dict[str, QLabel] = {}
        counts = QGridLayout()
        counts.setContentsMargins(0, 0, 0, 0)
        counts.setHorizontalSpacing(7)
        counts.setVerticalSpacing(2)
        for index, (key, label) in enumerate(_DISPOSITIONS):
            value = QLabel(f"{label} 0")
            value.setObjectName(
                "painterMotionBlockedCount"
                if key == "blocked"
                else "painterMotionCount"
            )
            self.count_labels[key] = value
            counts.addWidget(value, index // 2, index % 2)
        root.addLayout(counts)

    def set_counts(self, counts: Mapping[str, int]) -> None:
        for key, label in _DISPOSITIONS:
            self.count_labels[key].setText(f"{label} {int(counts.get(key, 0))}")


class PainterUIMotionDeliveryPanel(QWidget):
    """Read-only Motion delivery summary for the current Painter UI selection."""

    open_motion_requested = Signal(str)
    preview_hover_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("painterMotionDeliveryPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum,
        )
        self._report: dict[str, Any] = {}
        self._binding_id = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        heading_row = QHBoxLayout()
        heading = QLabel("Motion Delivery")
        heading.setObjectName("painterPanelSectionTitle")
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        self.transition_label = QLabel("Normal -> Hover")
        self.transition_label.setObjectName("painterMotionTransition")
        self.transition_label.setVisible(False)
        heading_row.addWidget(self.transition_label)
        root.addLayout(heading_row)

        self.empty_label = QLabel(
            "No Motion delivery report. Select an animated UI object to inspect it."
        )
        self.empty_label.setObjectName("painterMutedLabel")
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label)

        self.summary_frame = QFrame()
        self.summary_frame.setObjectName("painterMotionSummary")
        summary_layout = QVBoxLayout(self.summary_frame)
        summary_layout.setContentsMargins(8, 7, 8, 7)
        summary_layout.setSpacing(2)
        self.object_label = QLabel("No object selected")
        self.object_label.setObjectName("painterMotionObject")
        self.binding_label = QLabel("No Motion binding")
        self.binding_label.setObjectName("painterMutedLabel")
        self.binding_label.setWordWrap(True)
        summary_layout.addWidget(self.object_label)
        summary_layout.addWidget(self.binding_label)
        root.addWidget(self.summary_frame)

        target_row = QHBoxLayout()
        target_row.setContentsMargins(0, 0, 0, 0)
        target_row.setSpacing(5)
        self.target_summaries: dict[str, _TargetSummary] = {}
        self.target_count_labels: dict[str, dict[str, QLabel]] = {}
        for target, title in _TARGETS:
            summary = _TargetSummary(target, title)
            self.target_summaries[target] = summary
            self.target_count_labels[target] = summary.count_labels
            target_row.addWidget(summary, 1)
        root.addLayout(target_row)

        blocker_title = QLabel("Delivery blockers")
        blocker_title.setObjectName("painterMotionSubheading")
        root.addWidget(blocker_title)
        self.blocker_label = QLabel("No blockers reported.")
        self.blocker_label.setObjectName("painterMutedLabel")
        self.blocker_label.setWordWrap(True)
        root.addWidget(self.blocker_label)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        self.open_motion_button = QPushButton("Open Motion")
        self.open_motion_button.clicked.connect(
            lambda: self.open_motion_requested.emit(self._binding_id)
        )
        self.preview_hover_button = QPushButton("Preview Hover")
        self.preview_hover_button.clicked.connect(
            lambda: self.preview_hover_requested.emit(self._binding_id)
        )
        action_row.addWidget(self.open_motion_button)
        action_row.addWidget(self.preview_hover_button)
        root.addLayout(action_row)

        self.setStyleSheet(
            """
            QWidget#painterMotionDeliveryPanel {
                background-color: #15191F;
                color: #DCE5F0;
            }
            QLabel#painterPanelSectionTitle {
                color: #EEF3F9;
                font-size: 12px;
                font-weight: 600;
            }
            QFrame#painterMotionSummary, QFrame#painterMotionTarget {
                background-color: #1A2028;
                border: 1px solid #2B3541;
                border-radius: 4px;
            }
            QLabel#painterMotionObject, QLabel#painterMotionTargetTitle,
            QLabel#painterMotionSubheading {
                color: #F2F5F8;
                font-weight: 600;
            }
            QLabel#painterMutedLabel, QLabel#painterMotionCount {
                color: #98A5B4;
            }
            QLabel#painterMotionBlockedCount {
                color: #D9948A;
            }
            QLabel#painterMotionTransition {
                color: #9EC5FF;
                background: #1C2C42;
                border: 1px solid #365677;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton {
                min-height: 24px;
                color: #DCE5F0;
                background-color: #222A34;
                border: 1px solid #35414F;
                border-radius: 4px;
                padding: 2px 9px;
            }
            QPushButton:hover {
                background-color: #2A3542;
                border-color: #607C9C;
            }
            QPushButton:disabled {
                color: #66717D;
                background-color: #191E25;
                border-color: #272F39;
            }
            """
        )
        self.set_report(None)

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        self._report = _mapping(report)
        binding = _binding_from_report(self._report)
        selection = _selection_from_report(self._report)
        self._binding_id = str(binding.get("id") or binding.get("binding_id") or "")

        if not self._report:
            self._show_empty(
                "No Motion delivery report. Select an animated UI object to inspect it."
            )
            return
        if not binding:
            object_name = str(selection.get("name") or selection.get("id") or "selection")
            self._show_empty(f"{object_name} has no Motion binding yet.")
            return

        self.empty_label.setVisible(False)
        self.summary_frame.setVisible(True)
        for summary in self.target_summaries.values():
            summary.setVisible(True)
        self.blocker_label.setVisible(True)
        self.open_motion_button.setEnabled(True)

        object_name = str(
            selection.get("name")
            or binding.get("source_object_name")
            or binding.get("source_object_id")
            or "Selected UI object"
        )
        animation_name = str(
            binding.get("animation_name")
            or binding.get("name")
            or "Motion binding"
        )
        scope = str(binding.get("scope") or "transition")
        trigger = str(binding.get("trigger") or "")
        duration = binding.get("duration_ms")
        detail = f"{animation_name} | {scope}"
        if trigger:
            detail += f" | {trigger}"
        if duration not in (None, ""):
            detail += f" | {duration} ms"
        self.object_label.setText(object_name)
        self.binding_label.setText(detail)

        from_state = str(binding.get("from_state") or "").strip()
        to_state = str(binding.get("to_state") or "").strip()
        is_hover = from_state.casefold() == "normal" and to_state.casefold() == "hover"
        if from_state or to_state:
            self.transition_label.setText(
                f"{from_state or 'Any'} -> {to_state or 'Any'}"
            )
            self.transition_label.setVisible(True)
        else:
            self.transition_label.setVisible(False)
        self.preview_hover_button.setEnabled(is_hover)

        counts, blockers = _aggregate_targets(self._report)
        for target, _label in _TARGETS:
            self.target_summaries[target].set_counts(counts[target])

        blocker_lines: list[str] = []
        for target, title in _TARGETS:
            for reason in blockers[target]:
                row = f"{title}: {reason}"
                if row not in blocker_lines:
                    blocker_lines.append(row)
        self.blocker_label.setText(
            "\n".join(f"- {row}" for row in blocker_lines[:8])
            if blocker_lines
            else "No blockers reported."
        )

    def _show_empty(self, text: str) -> None:
        self._binding_id = ""
        self.empty_label.setText(text)
        self.empty_label.setVisible(True)
        self.summary_frame.setVisible(False)
        self.transition_label.setVisible(False)
        for summary in self.target_summaries.values():
            summary.setVisible(False)
            summary.set_counts({})
        self.blocker_label.setText("No blockers reported.")
        self.blocker_label.setVisible(False)
        self.open_motion_button.setEnabled(False)
        self.preview_hover_button.setEnabled(False)


__all__ = ["PainterUIMotionDeliveryPanel"]
