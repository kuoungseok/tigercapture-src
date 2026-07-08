"""Compact Final Cut-style role lane filter bar for the timeline."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from app.nle_connected_clips import ROLE_LABELS


class RoleLaneFilterBar(QWidget):
    """Small role filter strip driven by ``timeline.role_lanes.filter_model``."""

    roleSelected = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("NleRoleLaneFilterBar")
        self._buttons: dict[str, QToolButton] = {}
        self._focused_role = ""
        self._model: dict[str, Any] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 3)
        layout.setSpacing(5)
        self._layout = layout

        self._label = QLabel("Roles", self)
        self._label.setObjectName("NleRoleLaneFilterLabel")
        layout.addWidget(self._label)
        self._all_btn = self._make_button("all", "All", "#8D95A8")
        layout.addWidget(self._all_btn)
        layout.addStretch(1)
        self.setVisible(False)

    def _make_button(self, role: str, label: str, color: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setObjectName("NleRoleLaneFilterButton")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("role", role)
        btn.setProperty("roleColor", color)
        btn.setText(str(label or role).replace("_", " "))
        btn.setToolTip(f"Focus timeline role: {label or role}")
        btn.clicked.connect(lambda _checked=False, r=role: self.roleSelected.emit("" if r == "all" else r))
        self._buttons[role] = btn
        return btn

    def set_model(self, model: dict[str, Any]) -> None:
        self._model = dict(model or {})
        self._focused_role = str(self._model.get("focused_role") or "")
        filters = [row for row in list(self._model.get("filters") or []) if isinstance(row, dict)]
        active_filters = [row for row in filters if int(row.get("clip_count") or 0) > 0]

        wanted_roles = ["all"] + [str(row.get("role") or "") for row in active_filters if str(row.get("role") or "")]
        for role in list(self._buttons):
            if role == "all":
                continue
            if role not in wanted_roles:
                button = self._buttons.pop(role)
                self._layout.removeWidget(button)
                button.deleteLater()

        insert_at = max(1, self._layout.count() - 1)
        for row in active_filters:
            role = str(row.get("role") or "")
            if not role:
                continue
            label = str(row.get("label") or ROLE_LABELS.get(role, role))
            color = str(row.get("color") or "#8D95A8")
            count = int(row.get("clip_count") or 0)
            if role not in self._buttons:
                button = self._make_button(role, label, color)
                self._layout.insertWidget(insert_at, button)
                insert_at += 1
            button = self._buttons[role]
            button.setText(f"{label} {count}")
            button.setToolTip(f"Focus timeline role: {label} ({count} clip{'s' if count != 1 else ''})")
            button.setProperty("roleColor", color)
            button.setStyleSheet(_role_button_qss(color, focused=(role == self._focused_role)))

        self._all_btn.setChecked(not self._focused_role)
        self._all_btn.setStyleSheet(_role_button_qss("#8D95A8", focused=not self._focused_role))
        for role, button in self._buttons.items():
            if role == "all":
                continue
            button.setChecked(role == self._focused_role)
        clip_count = int(((self._model.get("lane_status") or {}) or {}).get("clip_count") or 0)
        self.setVisible(clip_count > 0)


def _role_button_qss(color: str, *, focused: bool) -> str:
    border = color if focused else "rgba(255,255,255,42)"
    background = f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {color}, stop:1 #171B2A)" if focused else "#171A25"
    text = "#FFFFFF" if focused else "#CDD3E0"
    return (
        "QToolButton#NleRoleLaneFilterButton {"
        f"background:{background};"
        f"color:{text};"
        f"border:1px solid {border};"
        "border-radius:10px;"
        "padding:3px 9px;"
        "font-size:11px;"
        "font-weight:700;"
        "}"
        "QToolButton#NleRoleLaneFilterButton:hover {"
        "border:1px solid rgba(255,255,255,120);"
        "}"
    )


def role_lane_filter_bar_qss() -> str:
    return """
    QWidget#NleRoleLaneFilterBar {
        background: rgba(12, 15, 25, 178);
        border-top: 1px solid rgba(111, 124, 160, 48);
        border-bottom: 1px solid rgba(111, 124, 160, 38);
    }
    QLabel#NleRoleLaneFilterLabel {
        color: #9EA8BD;
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0px;
        padding-right: 4px;
    }
    """


__all__ = ["RoleLaneFilterBar", "role_lane_filter_bar_qss"]
