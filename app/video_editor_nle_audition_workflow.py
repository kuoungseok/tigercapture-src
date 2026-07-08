from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
)

from app.nle_audition_visuals import build_audition_card_model


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _ms_text(value: Any) -> str:
    ms = max(0, _safe_int(value, 0))
    sec = ms / 1000.0
    if sec >= 60:
        return f"{int(sec // 60)}:{int(sec % 60):02d}.{int(ms % 1000 / 100)}"
    return f"{sec:.1f}s"


def _action_result_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "to_dict"):
        try:
            result = result.to_dict()
        except Exception:
            result = {}
    return result if isinstance(result, dict) else {}


def _audition_card_qss(*, active: bool = False, selected: bool = False) -> str:
    if active:
        background = "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FF7A50, stop:1 #B46DFF)"
        border = "#FFD6A0"
        text = "#FFFFFF"
    elif selected:
        background = "qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #272B42, stop:1 #453A86)"
        border = "#8D7CFF"
        text = "#F4F6FF"
    else:
        background = "#171B29"
        border = "#313A52"
        text = "#DDE4F4"
    return (
        "QToolButton#NleAuditionCard {"
        f"background:{background};"
        f"border:1px solid {border};"
        "border-radius:12px;"
        f"color:{text};"
        "font-size:11px;"
        "font-weight:800;"
        "padding:7px;"
        "text-align:left;"
        "}"
        "QToolButton#NleAuditionCard:hover {"
        "border:1px solid rgba(255,255,255,145);"
        "}"
    )


class AuditionPickerDialog(QDialog):
    """Small Final Cut-style audition/take picker backed by Python Actions."""

    def __init__(self, owner: Any, track_id: int, clip_id: int, parent=None) -> None:
        super().__init__(parent)
        self._owner = owner
        self._track_id = int(track_id)
        self._clip_id = int(clip_id)
        self._compare: dict[str, Any] = {}
        self.setWindowTitle("Audition Takes")
        self.setMinimumSize(680, 380)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self._title = QLabel("Audition Takes", self)
        self._title.setObjectName("NleAuditionTitle")
        self._title.setStyleSheet("font-size:18px;font-weight:800;color:#F4F7FF;")
        root.addWidget(self._title)

        self._summary = QLabel("", self)
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color:#AEB7CE;font-size:12px;")
        root.addWidget(self._summary)

        self._card_scroll = QScrollArea(self)
        self._card_scroll.setObjectName("NleAuditionCardScroll")
        self._card_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._card_scroll.setWidgetResizable(False)
        self._card_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._card_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._card_scroll.setMinimumHeight(92)
        self._card_scroll.setMaximumHeight(96)
        self._card_scroll.setStyleSheet(
            """
            QScrollArea#NleAuditionCardScroll {
                background:#0D1018;
                border:1px solid #30394F;
                border-radius:12px;
            }
            QScrollBar:horizontal {
                background:#0D1018;
                height:8px;
                border:0;
            }
            QScrollBar::handle:horizontal {
                background:#48536B;
                border-radius:4px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width:0;
                height:0;
            }
            """
        )
        self._card_host = QFrame(self._card_scroll)
        self._card_host.setObjectName("NleAuditionCardHost")
        self._card_layout = QHBoxLayout(self._card_host)
        self._card_layout.setContentsMargins(8, 8, 8, 8)
        self._card_layout.setSpacing(8)
        self._card_scroll.setWidget(self._card_host)
        self._card_buttons: dict[str, QToolButton] = {}
        root.addWidget(self._card_scroll)

        self._table = QTableWidget(self)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["Active", "Take", "Source", "In", "Out", "Delta"])
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            """
            QTableWidget {
                background:#10131D;
                color:#F2F5FF;
                gridline-color:#2C3449;
                border:1px solid #30394F;
                border-radius:10px;
            }
            QHeaderView::section {
                background:#171B29;
                color:#AEB7CE;
                border:0;
                padding:6px;
                font-weight:700;
            }
            QTableWidget::item:selected {
                background:#6657F4;
                color:#FFFFFF;
            }
            """
        )
        self._table.itemDoubleClicked.connect(lambda _item: self._switch_selected_take())
        self._table.itemSelectionChanged.connect(self._sync_card_selection)
        root.addWidget(self._table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._refresh_btn = QPushButton("Refresh", self)
        self._switch_btn = QPushButton("Switch", self)
        self._rename_btn = QPushButton("Rename", self)
        self._remove_btn = QPushButton("Remove", self)
        self._close_btn = QPushButton("Close", self)
        for button in (self._refresh_btn, self._switch_btn, self._rename_btn, self._remove_btn, self._close_btn):
            button.setMinimumHeight(34)
            buttons.addWidget(button)
        root.addLayout(buttons)

        self._refresh_btn.clicked.connect(self._refresh)
        self._switch_btn.clicked.connect(self._switch_selected_take)
        self._rename_btn.clicked.connect(self._rename_selected_take)
        self._remove_btn.clicked.connect(self._remove_selected_take)
        self._close_btn.clicked.connect(self.accept)

        self._refresh()

    def _registry(self):
        fn = getattr(self._owner, "_ensure_python_action_registry", None)
        if not callable(fn):
            raise RuntimeError("Python Action registry is not available")
        return fn()

    def _execute(self, action_id: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            result = self._registry().execute(action_id, params)
            payload = _action_result_payload(result)
        except Exception as exc:
            payload = {"ok": False, "error": str(exc)}
        if not payload.get("ok", False):
            message = str(payload.get("error") or payload.get("message") or f"{action_id} failed")
            QMessageBox.warning(self, "Audition Takes", message)
        return payload

    def _refresh_editor(self) -> None:
        row = getattr(self._owner, "_track_rows", {}).get(self._track_id)
        if row is not None:
            try:
                row.update()
            except Exception:
                pass
        for name in ("_refresh_player_tracks", "_refresh_workbench", "_update_tracks_host_width"):
            fn = getattr(self._owner, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
        player = getattr(self._owner, "_player", None)
        refresh = getattr(player, "refresh_current_frame", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    def _refresh(self) -> None:
        payload = self._execute(
            "timeline.audition.compare",
            {"track_id": self._track_id, "clip_id": self._clip_id},
        )
        self._compare = payload.get("result") if isinstance(payload.get("result"), dict) else {}
        takes = [row for row in list(self._compare.get("takes") or []) if isinstance(row, dict)]
        active = str(self._compare.get("active_take_id") or "")
        title = str(self._compare.get("audition_name") or "Audition Takes").strip()
        self._title.setText(title or "Audition Takes")
        self._summary.setText(
            f"{len(takes)} take(s), active: {active or '-'}  |  "
            "Double-click a row or press Switch to preview/export with that take."
        )
        self._rebuild_cards()
        self._table.setRowCount(len(takes))
        for row_idx, take in enumerate(takes):
            take_id = str(take.get("id") or "")
            delta = _safe_int(take.get("timeline_duration_delta_ms"), 0)
            values = [
                "ACTIVE" if take.get("active") else "",
                str(take.get("label") or take_id),
                str(take.get("source_name") or take.get("source_path") or ""),
                _ms_text(take.get("source_in_ms")),
                _ms_text(take.get("source_out_ms")),
                f"{delta:+d} ms" if delta else "0 ms",
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, take_id)
                if take.get("active"):
                    item.setForeground(Qt.GlobalColor.white)
                self._table.setItem(row_idx, col, item)
        self._table.resizeColumnsToContents()
        if takes and not self._table.selectedItems():
            self._table.selectRow(0)
        self._remove_btn.setEnabled(bool(self._compare.get("can_remove")))
        enabled = bool(takes)
        self._switch_btn.setEnabled(enabled)
        self._rename_btn.setEnabled(enabled)

    def _rebuild_cards(self) -> None:
        while self._card_layout.count():
            item = self._card_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._card_buttons.clear()
        model = build_audition_card_model(self._compare)
        cards = [row for row in list(model.get("cards") or []) if isinstance(row, dict)]
        self._card_scroll.setVisible(bool(cards))
        for card in cards:
            take_id = str(card.get("id") or "")
            button = QToolButton(self._card_host)
            button.setObjectName("NleAuditionCard")
            button.setCheckable(True)
            button.setChecked(bool(card.get("active")))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(154, 68)
            button.setText(
                f"{card.get('badge') or 'TAKE'}\n"
                f"{card.get('label') or take_id}\n"
                f"{card.get('duration_label') or ''}  {card.get('delta_label') or ''}"
            )
            source = str(card.get("source") or "")
            button.setToolTip(
                f"{card.get('label') or take_id}\n"
                f"{source}\n"
                "Click to select. Double-click the row or press Switch to apply."
            )
            button.setStyleSheet(_audition_card_qss(active=bool(card.get("active"))))
            button.clicked.connect(lambda _checked=False, tid=take_id: self._select_take_id(tid))
            self._card_buttons[take_id] = button
            self._card_layout.addWidget(button)
        self._card_layout.addStretch(1)
        self._card_host.adjustSize()

    def _select_take_id(self, take_id: str) -> None:
        wanted = str(take_id or "").strip()
        if not wanted:
            return
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0) or self._table.item(row, 1)
            if item is not None and str(item.data(Qt.ItemDataRole.UserRole) or "") == wanted:
                self._table.selectRow(row)
                break
        self._sync_card_selection()

    def _sync_card_selection(self) -> None:
        selected = self._selected_take_id()
        active = str(self._compare.get("active_take_id") or "")
        for take_id, button in self._card_buttons.items():
            is_active = bool(active and take_id == active)
            is_selected = bool(selected and take_id == selected)
            button.setChecked(is_active or is_selected)
            button.setStyleSheet(_audition_card_qss(active=is_active, selected=is_selected))

    def _selected_take_id(self) -> str:
        row = self._table.currentRow()
        if row < 0:
            return ""
        item = self._table.item(row, 0) or self._table.item(row, 1)
        if item is None:
            return ""
        return str(item.data(Qt.ItemDataRole.UserRole) or "").strip()

    def _selected_take_label(self) -> str:
        row = self._table.currentRow()
        item = self._table.item(row, 1) if row >= 0 else None
        return str(item.text() if item is not None else "")

    def _switch_selected_take(self) -> None:
        take_id = self._selected_take_id()
        if not take_id:
            return
        payload = self._execute(
            "timeline.audition.switch_take",
            {"track_id": self._track_id, "clip_id": self._clip_id, "take_id": take_id},
        )
        if payload.get("ok"):
            self._refresh_editor()
            self._refresh()

    def _rename_selected_take(self) -> None:
        take_id = self._selected_take_id()
        if not take_id:
            return
        label, ok = QInputDialog.getText(
            self,
            "Rename Take",
            "Take label",
            text=self._selected_take_label(),
        )
        if not ok:
            return
        payload = self._execute(
            "timeline.audition.rename_take",
            {"track_id": self._track_id, "clip_id": self._clip_id, "take_id": take_id, "label": str(label)},
        )
        if payload.get("ok"):
            self._refresh_editor()
            self._refresh()

    def _remove_selected_take(self) -> None:
        take_id = self._selected_take_id()
        if not take_id:
            return
        if QMessageBox.question(
            self,
            "Remove Take",
            "Remove this audition take? The last remaining take is protected.",
        ) != QMessageBox.StandardButton.Yes:
            return
        payload = self._execute(
            "timeline.audition.remove_take",
            {"track_id": self._track_id, "clip_id": self._clip_id, "take_id": take_id},
        )
        if payload.get("ok"):
            self._refresh_editor()
            self._refresh()


def open_nle_audition_picker(owner: Any, track: Any, clip: Any) -> None:
    track_id = _safe_int(getattr(track, "id", 0), 0)
    clip_id = _safe_int(getattr(clip, "id", 0), 0)
    if track_id <= 0 or clip_id <= 0:
        return
    dlg = AuditionPickerDialog(owner, track_id, clip_id, parent=owner)
    dlg.exec()


def focus_connected_parent_clip(owner: Any, track: Any, clip: Any) -> bool:
    parent_track_id = getattr(clip, "connected_parent_track_id", None)
    parent_clip_id = getattr(clip, "connected_parent_clip_id", None)
    if parent_track_id is None or parent_clip_id is None:
        return False
    find_track = getattr(owner, "_find_track", None)
    if not callable(find_track):
        return False
    parent_track = find_track(_safe_int(parent_track_id, -1))
    parent_clip = None
    for candidate in list(getattr(parent_track, "clips", []) or []):
        if _safe_int(getattr(candidate, "id", -1), -1) == _safe_int(parent_clip_id, -2):
            parent_clip = candidate
            break
    if parent_track is None or parent_clip is None:
        return False
    select = getattr(owner, "_select_workflow_video_clip", None)
    if callable(select):
        select(parent_track, parent_clip)
    focus = getattr(owner, "_focus_preview_at_workflow_ms", None)
    if callable(focus):
        focus(max(0, _safe_int(getattr(parent_clip, "timeline_in_ms", 0))), track=parent_track)
    row = getattr(owner, "_track_rows", {}).get(_safe_int(getattr(parent_track, "id", 0), 0))
    if row is not None:
        try:
            row.update()
        except Exception:
            pass
    return True

