"""Runtime keyboard-focus audit for the visible Painter UI Design surface."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QScrollBar,
    QTabBar,
    QWidget,
)


SCHEMA = "tigerstudio.painter.ui.focus_audit.v1"
_INTERACTIVE_TYPES = (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QTabBar,
)
_FOCUS_RING_TYPES = _INTERACTIVE_TYPES


def _widget_kind(widget: QWidget) -> str:
    return type(widget).__name__


def _widget_label(widget: QWidget) -> str:
    values = [
        widget.accessibleName(),
        widget.toolTip(),
    ]
    if isinstance(widget, QAbstractButton):
        values.insert(0, widget.text().replace("&", ""))
    elif isinstance(widget, QLineEdit):
        values.insert(0, widget.placeholderText())
    elif isinstance(widget, QComboBox):
        values.insert(0, widget.currentText())
    elif isinstance(widget, QTabBar) and widget.count():
        values.insert(
            0,
            ", ".join(widget.tabText(index) for index in range(widget.count())),
        )
    return next((str(value).strip() for value in values if str(value).strip()), "")


def _stable_widget_id(widget: QWidget, index: int) -> str:
    object_name = str(widget.objectName() or "").strip()
    return object_name or f"{_widget_kind(widget)}-{index + 1}"


def inspect_painter_ui_focus(root: QWidget) -> dict[str, Any]:
    """Inspect visible interactive widgets without mutating the document."""

    candidates = [
        widget
        for widget in root.findChildren(QWidget)
        if isinstance(widget, _INTERACTIVE_TYPES)
        and not isinstance(widget, QScrollBar)
        and not (
            isinstance(widget, QAbstractButton)
            and isinstance(widget.parentWidget(), QLineEdit)
        )
        and not (
            isinstance(widget, QLineEdit)
            and isinstance(widget.parentWidget(), QAbstractSpinBox)
        )
        and widget.isVisibleTo(root)
        and widget.isEnabled()
    ]
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, widget in enumerate(candidates):
        policy = widget.focusPolicy()
        tab_focus = bool(policy & Qt.FocusPolicy.TabFocus)
        label = _widget_label(widget)
        ring_supported = isinstance(widget, _FOCUS_RING_TYPES)
        issue_codes = []
        if not tab_focus:
            issue_codes.append("not_in_tab_order")
        if not label:
            issue_codes.append("missing_accessible_label")
        if not ring_supported:
            issue_codes.append("missing_focus_ring_contract")
        row = {
            "id": _stable_widget_id(widget, index),
            "kind": _widget_kind(widget),
            "label": label,
            "tab_focus": tab_focus,
            "focus_ring": ring_supported,
            "width": int(widget.width()),
            "height": int(widget.height()),
            "issue_codes": issue_codes,
            "status": "blocked" if issue_codes else "covered",
        }
        rows.append(row)
        if issue_codes:
            issues.append(dict(row))
    return {
        "schema": SCHEMA,
        "status": "blocked" if issues else "covered",
        "control_count": len(rows),
        "tab_focus_count": sum(bool(row["tab_focus"]) for row in rows),
        "focus_ring_count": sum(bool(row["focus_ring"]) for row in rows),
        "labelled_count": sum(bool(row["label"]) for row in rows),
        "issue_count": len(issues),
        "controls": rows,
        "issues": issues,
    }


__all__ = ["SCHEMA", "inspect_painter_ui_focus"]
