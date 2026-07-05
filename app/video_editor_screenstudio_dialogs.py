"""Screen Studio-style automatic polish settings dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class ScreenStudioPolishDialog(QDialog):
    settings_changed = Signal(object)
    auto_polish_requested = Signal()
    candidate_selected = Signal(object)

    def __init__(self, settings: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto Polish")
        self.resize(760, 540)
        self._syncing = False
        self._candidate_syncing = False
        self._dirty = False
        self._sliders: dict[str, tuple[QSlider, QLabel, object]] = {}
        self._preset_buttons: dict[str, QToolButton] = {}
        self._zoom_candidates: list[dict] = []
        self._candidate_overrides: dict[str, dict] = {}
        self._candidate_override_spins: dict[str, QSpinBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.setStyleSheet(
            """
            QDialog {
                background: #0D101B;
                color: #F7F8FF;
            }
            QFrame#PolishHero, QFrame#PolishCard {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 rgba(35,42,70,210),
                    stop:.55 rgba(19,22,38,230),
                    stop:1 rgba(32,24,54,220));
                border: 1px solid rgba(122,139,190,90);
                border-radius: 18px;
            }
            QLabel#PolishTitle {
                font-size: 20px;
                font-weight: 900;
                letter-spacing: 0px;
                color: #FFFFFF;
            }
            QLabel#PolishHint {
                font-size: 11px;
                color: #9FA8C9;
            }
            QLabel#PolishCardTitle {
                font-size: 12px;
                font-weight: 900;
                color: #FFFFFF;
            }
            QLabel#PolishControlLabel {
                color: #CAD1EA;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel#PolishValue {
                color: #FFFFFF;
                font-family: Consolas, monospace;
                font-size: 11px;
                font-weight: 800;
                padding: 2px 8px;
                border-radius: 9px;
                background: rgba(255,255,255,18);
            }
            QToolButton#PolishPreset {
                min-height: 54px;
                padding: 6px 10px;
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,76);
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 900;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #FF8057, stop:.52 #8F7CFF, stop:1 #28C7E5);
            }
            QToolButton#PolishPreset:hover {
                border-color: #FFFFFF;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #FF9B70, stop:.50 #9B8CFF, stop:1 #45D7F1);
            }
            QToolButton#PolishPreset:checked {
                border: 2px solid #FFFFFF;
            }
            QPushButton#PolishPrimary {
                min-height: 38px;
                padding: 0 16px;
                border: 0;
                border-radius: 14px;
                color: #FFFFFF;
                font-weight: 900;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #FF775A, stop:1 #7C68FF);
            }
            QPushButton#PolishTool {
                min-height: 34px;
                padding: 0 14px;
                border-radius: 13px;
                border: 1px solid rgba(255,255,255,60);
                color: #E8ECFF;
                font-weight: 800;
                background: rgba(255,255,255,18);
            }
            QComboBox {
                min-height: 30px;
                border-radius: 11px;
                padding: 0 10px;
                color: #F7F8FF;
                background: rgba(255,255,255,18);
                border: 1px solid rgba(255,255,255,54);
            }
            QSpinBox {
                min-height: 26px;
                border-radius: 10px;
                padding: 0 8px;
                color: #F7F8FF;
                background: rgba(255,255,255,16);
                border: 1px solid rgba(255,255,255,42);
                font-family: Consolas, monospace;
                font-size: 11px;
                font-weight: 800;
            }
            QSlider::groove:horizontal {
                background: rgba(255,255,255,18);
                height: 6px;
                border-radius: 3px;
                border: none;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #FF8057, stop:.45 #8F7CFF, stop:1 #28C7E5);
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: rgba(255,255,255,14);
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 18px;
                height: 18px;
                border: 2px solid #8F7CFF;
                border-radius: 9px;
                margin: -7px 0;
            }
            QListWidget#PolishCandidateList {
                background: rgba(5,7,14,120);
                border: 1px solid rgba(255,255,255,42);
                border-radius: 14px;
                padding: 4px;
                color: #EEF2FF;
                outline: none;
            }
            QListWidget#PolishCandidateList::item {
                min-height: 24px;
                border-radius: 9px;
                padding: 3px 7px;
            }
            QListWidget#PolishCandidateList::item:hover {
                background: rgba(255,255,255,22);
            }
            QListWidget#PolishCandidateList::item:selected {
                background: rgba(126,107,255,90);
                color: #FFFFFF;
            }
            """
        )

        hero = QFrame()
        hero.setObjectName("PolishHero")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(16, 14, 16, 14)
        hero_lay.setSpacing(4)
        title = QLabel("Screen Studio Auto Polish")
        title.setObjectName("PolishTitle")
        hint = QLabel("Cursor, click, zoom, wallpaper framing. Changes update the preview immediately.")
        hint.setObjectName("PolishHint")
        hero_lay.addWidget(title)
        hero_lay.addWidget(hint)
        root.addWidget(hero)

        preset_card = QFrame()
        preset_card.setObjectName("PolishCard")
        preset_lay = QVBoxLayout(preset_card)
        preset_lay.setContentsMargins(12, 12, 12, 12)
        preset_lay.setSpacing(8)
        preset_title = QLabel("Presets")
        preset_title.setObjectName("PolishCardTitle")
        preset_lay.addWidget(preset_title)
        preset_grid = QGridLayout()
        preset_grid.setContentsMargins(0, 0, 0, 0)
        preset_grid.setHorizontalSpacing(8)
        preset_grid.setVerticalSpacing(8)
        from app.screenstudio_polish import SCREENSTUDIO_POLISH_PRESETS, screenstudio_polish_preset_ids
        for idx, preset_id in enumerate(screenstudio_polish_preset_ids()):
            label = str(SCREENSTUDIO_POLISH_PRESETS[preset_id].get("label") or preset_id)
            btn = QToolButton()
            btn.setObjectName("PolishPreset")
            btn.setText(label)
            btn.setCheckable(True)
            btn.setToolTip(f"Apply {label}")
            btn.clicked.connect(lambda _checked=False, pid=preset_id: self._apply_preset(pid))
            self._preset_buttons[preset_id] = btn
            preset_grid.addWidget(btn, idx // 3, idx % 3)
        preset_lay.addLayout(preset_grid)
        root.addWidget(preset_card)

        body = QGridLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setHorizontalSpacing(10)
        body.setVerticalSpacing(10)
        body.addWidget(self._make_cursor_card(), 0, 0)
        body.addWidget(self._make_canvas_card(), 0, 1)
        body.addWidget(self._make_zoom_card(), 1, 0)
        body.addWidget(self._make_action_card(), 1, 1)
        root.addLayout(body, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        reset = QPushButton("Reset")
        reset.setObjectName("PolishTool")
        reset.clicked.connect(lambda: self._apply_preset("clean_tutorial"))
        close = QPushButton("Close")
        close.setObjectName("PolishTool")
        close.clicked.connect(self.accept)
        buttons.addWidget(reset)
        buttons.addWidget(close)
        root.addLayout(buttons)

        self._set_payload(settings or {}, emit=False)

    def is_dirty(self) -> bool:
        return bool(self._dirty)

    def _make_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("PolishCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("PolishCardTitle")
        lay.addWidget(title_label)
        return card, lay

    def _make_cursor_card(self) -> QFrame:
        card, lay = self._make_card("Cursor")
        lay.addWidget(self._slider_row("cursor_scale", "Cursor size", 60, 250, 135, lambda v: f"{v}%"))
        lay.addWidget(self._slider_row("cursor_smoothing", "Smoothing", 0, 95, 72, lambda v: f"{v}%"))
        lay.addWidget(self._slider_row("hide_static_after_ms", "Hide static", 0, 3000, 900, lambda v: "off" if v <= 0 else f"{v} ms"))
        lay.addWidget(self._slider_row("click_ring_ms", "Click ring", 120, 1200, 420, lambda v: f"{v} ms"))
        lay.addWidget(self._slider_row("click_hold_ms", "Click hold", 0, 360, 120, lambda v: "off" if v <= 0 else f"{v} ms"))
        lay.addWidget(self._slider_row("drag_trail_ms", "Drag trail", 0, 1200, 620, lambda v: "off" if v <= 0 else f"{v} ms"))
        row = QHBoxLayout()
        label = QLabel("Ring color")
        label.setObjectName("PolishControlLabel")
        self._ring_color_combo = QComboBox()
        for name, value in (
            ("Orange", "#FF6A3D"),
            ("Violet", "#8B78FF"),
            ("Aqua", "#4BD9D9"),
            ("Pink", "#FF7CB8"),
            ("Blue", "#5AD7F2"),
        ):
            self._ring_color_combo.addItem(name, value)
        self._ring_color_combo.currentIndexChanged.connect(self._emit_changed)
        row.addWidget(label)
        row.addWidget(self._ring_color_combo, stretch=1)
        lay.addLayout(row)
        return card

    def _make_canvas_card(self) -> QFrame:
        card, lay = self._make_card("Wallpaper Frame")
        row = QHBoxLayout()
        label = QLabel("Palette")
        label.setObjectName("PolishControlLabel")
        self._background_combo = QComboBox()
        for name, value in (
            ("Wallpaper", "wallpaper-gradient"),
            ("Candy Sky", "candy-sky"),
            ("Product Warm", "product-warm"),
            ("Cursor Focus", "cursor-focus"),
            ("Vertical Pop", "vertical-pop"),
            ("Clean Dark", "clean-dark"),
        ):
            self._background_combo.addItem(name, value)
        self._background_combo.currentIndexChanged.connect(self._emit_changed)
        row.addWidget(label)
        row.addWidget(self._background_combo, stretch=1)
        lay.addLayout(row)
        lay.addWidget(self._slider_row("padding", "Padding", 0, 32, 8, lambda v: f"{v}%"))
        lay.addWidget(self._slider_row("shadow", "Shadow", 0, 100, 55, lambda v: f"{v}%"))
        lay.addWidget(self._slider_row("corner_radius", "Rounding", 0, 12, 4, lambda v: f"{v}%"))
        row2 = QHBoxLayout()
        label2 = QLabel("Vertical")
        label2.setObjectName("PolishControlLabel")
        self._vertical_combo = QComboBox()
        for name, value in (("Auto", "auto"), ("Off", "off")):
            self._vertical_combo.addItem(name, value)
        self._vertical_combo.currentIndexChanged.connect(self._emit_changed)
        row2.addWidget(label2)
        row2.addWidget(self._vertical_combo, stretch=1)
        lay.addLayout(row2)
        return card

    def _make_zoom_card(self) -> QFrame:
        card, lay = self._make_card("Auto Zoom")
        lay.addWidget(self._slider_row("zoom_scale", "Zoom scale", 120, 260, 178, lambda v: f"{v / 100:.2f}x"))
        lay.addWidget(self._slider_row("zoom_duration_ms", "Zoom length", 800, 3500, 1900, lambda v: f"{v} ms"))
        row = QHBoxLayout()
        label = QLabel("Motion")
        label.setObjectName("PolishControlLabel")
        self._zoom_easing_combo = QComboBox()
        for name, value in (
            ("Smooth Pop", "smooth_pop"),
            ("Cinematic", "cinematic"),
            ("Snappy", "snappy"),
            ("Linear", "linear"),
        ):
            self._zoom_easing_combo.addItem(name, value)
        self._zoom_easing_combo.currentIndexChanged.connect(self._emit_changed)
        row.addWidget(label)
        row.addWidget(self._zoom_easing_combo, stretch=1)
        lay.addLayout(row)
        lay.addWidget(self._slider_row("zoom_motion_blur", "Transition blur", 0, 60, 18, lambda v: "off" if v <= 0 else f"{v}%"))
        lay.addWidget(self._slider_row("zoom_focus_bias", "Cursor framing", 12, 40, 22, lambda v: f"{v}%"))
        return card

    def _make_action_card(self) -> QFrame:
        card, lay = self._make_card("Generate")
        text = QLabel("Use the selected clips, or all video clips when nothing is selected.")
        text.setObjectName("PolishHint")
        text.setWordWrap(True)
        lay.addWidget(text)
        btn = QPushButton("Generate Zoom Windows")
        btn.setObjectName("PolishPrimary")
        btn.clicked.connect(self.auto_polish_requested.emit)
        lay.addWidget(btn)
        self._status_label = QLabel("Analyzing selected clips...")
        self._status_label.setObjectName("PolishHint")
        self._status_label.setWordWrap(True)
        lay.addWidget(self._status_label)
        candidates_label = QLabel("Zoom candidates")
        candidates_label.setObjectName("PolishControlLabel")
        lay.addWidget(candidates_label)
        self._candidate_list = QListWidget()
        self._candidate_list.setObjectName("PolishCandidateList")
        self._candidate_list.setMaximumHeight(118)
        self._candidate_list.itemChanged.connect(self._on_candidate_changed)
        self._candidate_list.itemSelectionChanged.connect(self._on_candidate_selection_changed)
        lay.addWidget(self._candidate_list)
        edit_grid = QGridLayout()
        edit_grid.setContentsMargins(0, 0, 0, 0)
        edit_grid.setHorizontalSpacing(6)
        edit_grid.setVerticalSpacing(4)
        for idx, (key, label, maximum) in enumerate(
            (
                ("start_ms", "Start", 24 * 60 * 60 * 1000),
                ("end_ms", "End", 24 * 60 * 60 * 1000),
                ("target_x", "X", 100000),
                ("target_y", "Y", 100000),
                ("target_w", "W", 100000),
                ("target_h", "H", 100000),
            )
        ):
            label_widget = QLabel(label)
            label_widget.setObjectName("PolishControlLabel")
            spin = QSpinBox()
            spin.setRange(0, int(maximum))
            spin.setSingleStep(10 if key.endswith("_ms") else 4)
            if key.endswith("_ms"):
                spin.setSuffix(" ms")
            spin.valueChanged.connect(lambda _value, k=key: self._on_candidate_override_changed(k))
            self._candidate_override_spins[key] = spin
            row = idx // 3
            col = (idx % 3) * 2
            edit_grid.addWidget(label_widget, row, col)
            edit_grid.addWidget(spin, row, col + 1)
        lay.addLayout(edit_grid)
        lay.addStretch(1)
        return card

    def set_readiness_report(self, report: dict | None) -> None:
        if not hasattr(self, "_status_label"):
            return
        report = dict(report or {})
        if not report:
            self._status_label.setText("No Auto Polish status yet.")
            return
        warnings = list(report.get("warnings") or [])
        counts = report.get("counts", {}) or {}
        labels = ", ".join(list(report.get("hotkey_labels") or [])[:3])
        status = "Ready" if not warnings else "Needs capture data"
        self._status_label.setText(
            f"{status}: {int(report.get('readiness', 0) or 0)}% 쨌 "
            f"{int(report.get('target_count', 0) or 0)} clip(s) 쨌 "
            f"{int(report.get('auto_zoom_count', 0) or 0)} zoom window(s)\n"
            f"click {counts.get('click', 0)} / drag {counts.get('drag', 0)} / "
            f"hotkey {counts.get('hotkey', 0) + counts.get('key', 0)} 쨌 "
            f"parity {'ok' if report.get('parity_ok') else 'needs check'}"
            + (f"\nkeys: {labels}" if labels else "")
            + (f"\nwarning: {', '.join(warnings[:3])}" if warnings else "")
        )
        self.set_zoom_candidates(list(report.get("zoom_candidates") or []))

    @staticmethod
    def _format_ms(ms: int) -> str:
        ms = max(0, int(ms or 0))
        return f"{ms // 1000}:{(ms % 1000) // 10:02d}"

    def set_zoom_candidates(self, candidates: list[dict] | None) -> None:
        if not hasattr(self, "_candidate_list"):
            return
        current_key = self._current_candidate_key()
        self._candidate_syncing = True
        try:
            self._zoom_candidates = [dict(row) for row in list(candidates or [])[:24]]
            self._candidate_list.clear()
            rows = self._zoom_candidates
            if not rows:
                item = QListWidgetItem("No cursor/click zoom candidates yet")
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self._candidate_list.addItem(item)
                return
            select_row = 0
            for idx, candidate in enumerate(rows, start=1):
                key = str(candidate.get("key") or f"0:{candidate.get('point_index', idx - 1)}")
                clip_name = str(candidate.get("clip_name") or "clip")
                kind = str(candidate.get("kind") or "action")
                start = self._format_ms(int(candidate.get("start_ms", 0) or 0))
                end = self._format_ms(int(candidate.get("end_ms", 0) or 0))
                w = int(candidate.get("target_w", 0) or 0)
                h = int(candidate.get("target_h", 0) or 0)
                item = QListWidgetItem(f"{idx}. {clip_name} 쨌 {kind} 쨌 {start}-{end} 쨌 {w}x{h}")
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsSelectable
                )
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setData(Qt.ItemDataRole.UserRole + 1, dict(candidate))
                item.setCheckState(
                    Qt.CheckState.Checked
                    if bool(candidate.get("enabled", True))
                    else Qt.CheckState.Unchecked
                )
                self._candidate_list.addItem(item)
                if current_key and key == current_key:
                    select_row = idx - 1
            self._candidate_list.setCurrentRow(select_row)
        finally:
            self._candidate_syncing = False
            self._sync_candidate_editor()

    def disabled_zoom_candidate_keys(self) -> list[str]:
        if not hasattr(self, "_candidate_list"):
            return []
        disabled: list[str] = []
        for idx in range(self._candidate_list.count()):
            item = self._candidate_list.item(idx)
            key = item.data(Qt.ItemDataRole.UserRole)
            if key and item.checkState() == Qt.CheckState.Unchecked:
                disabled.append(str(key))
        return disabled

    def _on_candidate_changed(self, _item=None) -> None:
        if self._candidate_syncing:
            return
        self._emit_changed()

    def _on_candidate_selection_changed(self) -> None:
        if self._candidate_syncing:
            return
        self._sync_candidate_editor()
        data = self._current_candidate_data()
        key = self._current_candidate_key()
        if key and data:
            data["key"] = key
            override = dict(getattr(self, "_candidate_overrides", {}) or {}).get(key)
            if isinstance(override, dict):
                data.update(override)
            self.candidate_selected.emit(data)

    def _current_candidate_key(self) -> str:
        if not hasattr(self, "_candidate_list"):
            return ""
        item = self._candidate_list.currentItem()
        if item is None:
            return ""
        key = item.data(Qt.ItemDataRole.UserRole)
        return str(key or "")

    def _current_candidate_data(self) -> dict:
        if not hasattr(self, "_candidate_list"):
            return {}
        item = self._candidate_list.currentItem()
        if item is None:
            return {}
        data = item.data(Qt.ItemDataRole.UserRole + 1)
        return dict(data or {}) if isinstance(data, dict) else {}

    def select_zoom_candidate_key(self, key: str) -> bool:
        if not hasattr(self, "_candidate_list"):
            return False
        key = str(key or "")
        if not key:
            return False
        for idx in range(self._candidate_list.count()):
            item = self._candidate_list.item(idx)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == key:
                self._candidate_list.setCurrentItem(item)
                return True
        return False

    def zoom_candidate_overrides(self) -> dict:
        cleaned: dict[str, dict] = {}
        for key, raw in dict(getattr(self, "_candidate_overrides", {}) or {}).items():
            values = {}
            for name in ("start_ms", "end_ms", "target_x", "target_y", "target_w", "target_h"):
                if name in raw:
                    try:
                        values[name] = int(raw[name])
                    except Exception:
                        continue
            if values:
                cleaned[str(key)] = values
        return cleaned

    def visible_zoom_candidates(self) -> list[dict]:
        disabled = set(self.disabled_zoom_candidate_keys())
        out: list[dict] = []
        for raw in list(getattr(self, "_zoom_candidates", []) or []):
            row = dict(raw)
            key = str(row.get("key") or "")
            if key in disabled:
                continue
            override = dict(getattr(self, "_candidate_overrides", {}) or {}).get(key)
            if isinstance(override, dict):
                row.update(override)
            row["key"] = key
            out.append(row)
        return out

    def set_zoom_candidate_override(self, key: str, values: dict, *, emit: bool = True) -> None:
        key = str(key or "")
        if not key:
            return
        cleaned: dict[str, int] = {}
        for name in ("start_ms", "end_ms", "target_x", "target_y", "target_w", "target_h"):
            if name not in values:
                continue
            try:
                cleaned[name] = max(0, int(values[name]))
            except Exception:
                continue
        if not cleaned:
            return
        current = dict(self._candidate_overrides.get(key, {}) or {})
        current.update(cleaned)
        self._candidate_overrides[key] = current
        if self._current_candidate_key() == key:
            self._sync_candidate_editor()
        self._dirty = True
        if emit:
            self._emit_changed(force=True)

    def commit_zoom_candidate_override(self) -> None:
        self._emit_changed(force=True)

    def _sync_candidate_editor(self) -> None:
        if not hasattr(self, "_candidate_override_spins"):
            return
        key = self._current_candidate_key()
        data = self._current_candidate_data()
        override = dict(getattr(self, "_candidate_overrides", {}) or {}).get(key)
        if isinstance(override, dict):
            data.update(override)
        self._candidate_syncing = True
        try:
            enabled = bool(key)
            for name, spin in self._candidate_override_spins.items():
                spin.setEnabled(enabled)
                spin.setValue(max(0, int(data.get(name, 0) or 0)) if enabled else 0)
        finally:
            self._candidate_syncing = False

    def _on_candidate_override_changed(self, key: str) -> None:
        if self._candidate_syncing:
            return
        candidate_key = self._current_candidate_key()
        if not candidate_key:
            return
        data = self._candidate_overrides.setdefault(candidate_key, {})
        spin = self._candidate_override_spins.get(key)
        if spin is not None:
            data[str(key)] = int(spin.value())
        self._emit_changed()

    def _slider_row(self, key: str, title: str, minimum: int, maximum: int, value: int, formatter) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        label = QLabel(title)
        label.setObjectName("PolishControlLabel")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(minimum), int(maximum))
        slider.setValue(int(value))
        value_label = QLabel("")
        value_label.setObjectName("PolishValue")
        value_label.setFixedWidth(72)
        self._sliders[key] = (slider, value_label, formatter)
        slider.valueChanged.connect(lambda _v, k=key: self._on_slider_changed(k))
        lay.addWidget(label)
        lay.addWidget(slider, stretch=1)
        lay.addWidget(value_label)
        self._sync_slider_label(key)
        return row

    def _sync_slider_label(self, key: str) -> None:
        slider, label, formatter = self._sliders[key]
        try:
            label.setText(str(formatter(int(slider.value()))))
        except Exception:
            label.setText(str(slider.value()))

    def _on_slider_changed(self, key: str) -> None:
        self._sync_slider_label(key)
        self._emit_changed()

    def _apply_preset(self, preset_id: str) -> None:
        from app.screenstudio_polish import screenstudio_polish_preset
        self._set_payload(screenstudio_polish_preset(preset_id), emit=True)

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)

    def _set_slider(self, key: str, value: int) -> None:
        slider, _label, _formatter = self._sliders[key]
        slider.setValue(int(max(slider.minimum(), min(slider.maximum(), value))))
        self._sync_slider_label(key)

    def _set_payload(self, payload: dict | None, *, emit: bool) -> None:
        from app.screenstudio_polish import normalize_screenstudio_polish
        normalized = normalize_screenstudio_polish(payload or {})
        cursor = normalized.get("cursor", {})
        screen = normalized.get("screen", {})
        self._syncing = True
        try:
            self._set_slider("cursor_scale", round(float(cursor.get("cursor_scale", 1.35)) * 100))
            self._set_slider("cursor_smoothing", round(float(cursor.get("cursor_smoothing", 0.72)) * 100))
            self._set_slider("hide_static_after_ms", int(cursor.get("hide_static_after_ms", 900)))
            self._set_slider("click_ring_ms", int(cursor.get("click_ring_ms", 420)))
            self._set_slider("click_hold_ms", int(cursor.get("click_hold_ms", 110)))
            self._set_slider("drag_trail_ms", int(cursor.get("drag_trail_ms", 620)))
            self._set_combo_data(self._ring_color_combo, str(cursor.get("click_ring_color", "#FF6A3D")))
            self._set_combo_data(self._background_combo, str(screen.get("background", "wallpaper-gradient")))
            self._set_slider("padding", round(float(screen.get("padding", 0.08)) * 100))
            self._set_slider("shadow", round(float(screen.get("shadow", 0.55)) * 100))
            self._set_slider("corner_radius", round(float(screen.get("corner_radius", 0.035)) * 100))
            self._set_combo_data(self._vertical_combo, str(screen.get("vertical_mode", "auto")))
            self._set_slider("zoom_scale", round(float(screen.get("zoom_scale", 1.78)) * 100))
            self._set_slider("zoom_duration_ms", int(screen.get("zoom_duration_ms", 1900)))
            self._set_combo_data(self._zoom_easing_combo, str(screen.get("zoom_easing", "smooth_pop")))
            self._set_slider("zoom_motion_blur", round(float(screen.get("zoom_motion_blur", 0.18)) * 100))
            self._set_slider("zoom_focus_bias", round(float(screen.get("zoom_focus_bias", 0.22)) * 100))
            overrides: dict[str, dict] = {}
            for key, value in dict(screen.get("zoom_candidate_overrides", {}) or {}).items():
                if isinstance(value, dict):
                    overrides[str(key)] = dict(value)
            self._candidate_overrides = overrides
            preset_id = str(normalized.get("preset_id") or "")
            for pid, btn in self._preset_buttons.items():
                btn.setChecked(pid == preset_id)
        finally:
            self._syncing = False
        if emit:
            self._emit_changed(force=True)

    def payload(self) -> dict:
        from app.screenstudio_polish import normalize_screenstudio_polish
        preset_id = ""
        for pid, btn in self._preset_buttons.items():
            if btn.isChecked():
                preset_id = pid
                break
        raw = {
            "version": 1,
            "source": "screenstudio_auto_polish",
            "preset_id": preset_id,
            "cursor": {
                "cursor_scale": self._sliders["cursor_scale"][0].value() / 100.0,
                "cursor_smoothing": self._sliders["cursor_smoothing"][0].value() / 100.0,
                "hide_static_after_ms": self._sliders["hide_static_after_ms"][0].value(),
                "click_ring_ms": self._sliders["click_ring_ms"][0].value(),
                "click_hold_ms": self._sliders["click_hold_ms"][0].value(),
                "drag_trail_ms": self._sliders["drag_trail_ms"][0].value(),
                "click_ring_color": self._ring_color_combo.currentData(),
            },
            "screen": {
                "background": self._background_combo.currentData(),
                "padding": self._sliders["padding"][0].value() / 100.0,
                "shadow": self._sliders["shadow"][0].value() / 100.0,
                "inset": 0.02,
                "corner_radius": self._sliders["corner_radius"][0].value() / 100.0,
                "vertical_mode": self._vertical_combo.currentData(),
                "zoom_scale": self._sliders["zoom_scale"][0].value() / 100.0,
                "zoom_duration_ms": self._sliders["zoom_duration_ms"][0].value(),
                "zoom_easing": self._zoom_easing_combo.currentData(),
                "zoom_motion_blur": self._sliders["zoom_motion_blur"][0].value() / 100.0,
                "zoom_focus_bias": self._sliders["zoom_focus_bias"][0].value() / 100.0,
                "disabled_zoom_candidate_keys": self.disabled_zoom_candidate_keys(),
                "zoom_candidate_overrides": self.zoom_candidate_overrides(),
            },
        }
        return normalize_screenstudio_polish(raw)

    def _emit_changed(self, *args, force: bool = False) -> None:
        if self._syncing and not force:
            return
        self._dirty = True
        self.settings_changed.emit(self.payload())
