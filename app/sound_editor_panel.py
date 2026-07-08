"""Renewed sound editor surfaces for Workbench and detached use.

Normal timeline/media-pool editing uses the compact panel and dock shell in
this module. The advanced lab now unfolds inside the renewed panel instead of
opening the legacy ``SoundEditorWindow`` from the Workbench path.
"""
from __future__ import annotations

import copy
import math
import time
import zlib
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.audio_tracks import (
    AudioClip,
    CLIP_EXPORT_FORMATS,
    ClipExporter,
    DEFAULT_AUDIO_QUALITY_ID,
    default_effects_state,
)
from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import FONT_FAMILY, editor_scrollbar_qss


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOUND_JOG_DIAL_TEXTURE = _PROJECT_ROOT / "resources" / "ui" / "sound_editor" / "jog_dial_metal_sparse_base.png"


def _fmt_ms(ms: int | float | None) -> str:
    try:
        value = max(0, int(ms or 0))
    except Exception:
        value = 0
    s = value // 1000
    return f"{s // 60}:{s % 60:02d}"


def _compact_mixer_label(text: str, max_chars: int = 9) -> str:
    value = " ".join(str(text or "").replace("_", " ").split())
    if not value:
        return "Audio"
    if len(value) <= max_chars:
        return value
    return value[: max(1, max_chars - 1)].rstrip() + "..."


def _mixer_track_type(track: Any) -> str:
    value = str(getattr(track, "track_type", "") or "").strip().lower()
    if value:
        return value
    bus = str(getattr(track, "bus_id", "") or "").strip().lower()
    if bus in {"dialogue", "music", "sfx", "ambience"}:
        return bus
    label = str(getattr(track, "label", "") or getattr(track, "display_name", "") or "").lower()
    if any(key in label for key in ("voice", "dialog", "vocal", "extract")):
        return "dialogue"
    if any(key in label for key in ("music", "bgm", "stem")):
        return "music"
    if any(key in label for key in ("sfx", "fx", "effect")):
        return "sfx"
    return "dialogue"


def _mixer_type_code(track_type: str) -> str:
    return {
        "dialogue": "DIA",
        "music": "MUS",
        "sfx": "SFX",
        "ambience": "AMB",
    }.get(str(track_type or "").lower(), "AUD")


def _mixer_next_type(track_type: str) -> str:
    order = ["dialogue", "music", "sfx", "ambience"]
    current = str(track_type or "").lower()
    try:
        return order[(order.index(current) + 1) % len(order)]
    except ValueError:
        return order[0]


def _mixer_insert_slots(track: Any) -> list[dict[str, Any]]:
    defaults = [
        {"id": "eq", "label": "EQ", "enabled": False, "bypassed": False},
        {"id": "dyn", "label": "DYN", "enabled": False, "bypassed": False},
        {"id": "fx", "label": "FX", "enabled": False, "bypassed": False},
    ]
    by_id = {row["id"]: dict(row) for row in defaults}
    for row in list(getattr(track, "insert_slots", None) or []):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("id") or row.get("slot") or "").strip().lower()
        if sid in {"dynamics", "dynamic"}:
            sid = "dyn"
        if not sid:
            continue
        base = dict(by_id.get(sid, {"id": sid, "label": sid.upper(), "enabled": False, "bypassed": False}))
        base["enabled"] = bool(row.get("enabled", base.get("enabled", False)))
        base["bypassed"] = bool(row.get("bypassed", base.get("bypassed", False)))
        base["label"] = str(row.get("label") or base.get("label") or sid.upper())
        by_id[sid] = base
    return [by_id["eq"], by_id["dyn"], by_id["fx"]]


def _mixer_sends(track: Any) -> dict[str, float]:
    sends = {"reverb": 0.0, "delay": 0.0}
    raw = getattr(track, "sends", None) or {}
    if isinstance(raw, dict):
        for key, value in raw.items():
            sid = str(key or "").strip().lower()
            if sid in {"rev", "verb"}:
                sid = "reverb"
            if sid == "dly":
                sid = "delay"
            try:
                sends[sid] = max(0.0, min(1.0, float(value or 0.0)))
            except Exception:
                sends[sid] = 0.0
    return sends


def _compact_path_label(path: Path | str | None, *, max_chars: int = 34) -> str:
    if path is None:
        return "No source"
    try:
        p = Path(path)
        text = p.name
    except Exception:
        text = str(path)
    if len(text) <= max_chars:
        return text
    return f"{text[:12]}...{text[-max(8, max_chars - 15):]}"


class SoundEditStateStore:
    """Keeps media-pool sound-edit states separate from timeline clips.

    Timeline clips already carry their edit data directly on ``AudioClip``.
    Media-pool audio files do not, so they get a persistent temporary clip
    keyed by the resolved source path.
    """

    def __init__(self) -> None:
        self._media_clips: dict[str, AudioClip] = {}
        self._recent_keys: list[str] = []

    @staticmethod
    def media_key(path: Path | str) -> str:
        try:
            return f"media:{Path(path).expanduser().resolve()}"
        except Exception:
            return f"media:{path}"

    @staticmethod
    def timeline_key(track: Any, clip: Any) -> str:
        return f"timeline:{getattr(track, 'id', 'none')}:{getattr(clip, 'id', 'none')}"

    def touch(self, key: str) -> None:
        if not key:
            return
        try:
            self._recent_keys.remove(key)
        except ValueError:
            pass
        self._recent_keys.insert(0, key)
        del self._recent_keys[64:]

    def media_clip(self, path: Path | str, duration_ms: int = 0) -> AudioClip:
        key = self.media_key(path)
        clip = self._media_clips.get(key)
        if clip is None:
            source = Path(path).expanduser().resolve()
            crc = zlib.crc32(str(source).encode("utf-8", errors="replace")) & 0x7FFFFFFF
            clip = AudioClip(
                id=crc or int(time.time() * 1000) & 0x7FFFFFFF,
                source_path=source,
                duration_ms=max(0, int(duration_ms or 0)),
                trim_start_ms=0,
                trim_end_ms=max(0, int(duration_ms or 0)),
                effects=copy.deepcopy(default_effects_state()),
            )
            self._media_clips[key] = clip
        elif duration_ms and not int(getattr(clip, "duration_ms", 0) or 0):
            clip.duration_ms = max(0, int(duration_ms))
            clip.trim_end_ms = max(0, int(duration_ms))
        self.touch(key)
        return clip

    def recent_keys(self) -> list[str]:
        return list(self._recent_keys)


class _ValueSlider(QWidget):
    value_changed = Signal(float)

    def __init__(
        self,
        label: str,
        minimum: int,
        maximum: int,
        value: int,
        *,
        scale: float = 1.0,
        suffix: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._scale = float(scale or 1.0)
        self._suffix = suffix
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self._label = QLabel(label, self)
        self._label.setObjectName("SoundFieldLabel")
        self._value_label = QLabel("", self)
        self._value_label.setObjectName("SoundFieldValue")
        row.addWidget(self._label, 1)
        row.addWidget(self._value_label, 0)
        root.addLayout(row)
        self._slider = StudioSlider("audio", self)
        self._slider.setMinimumHeight(15)
        self._slider.setMaximumHeight(18)
        self._slider.setRange(int(minimum), int(maximum))
        self._slider.setValue(int(value))
        self._slider.valueChanged.connect(self._on_value_changed)
        root.addWidget(self._slider)
        self._on_value_changed(int(value))

    def set_raw_value(self, value: int) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(int(value))
        self._slider.blockSignals(False)
        self._on_value_changed(int(value), emit=False)

    def _on_value_changed(self, raw: int, *, emit: bool = True) -> None:
        value = raw / self._scale
        if self._scale == 1.0:
            text = f"{int(value)}{self._suffix}"
        else:
            text = f"{value:.1f}{self._suffix}"
        self._value_label.setText(text)
        if emit:
            self.value_changed.emit(float(value))


class _MiniSoundGraph(QWidget):
    """Small non-interactive audio visual used to make each tab legible."""

    value_edited = Signal(int, float)
    dynamics_edited = Signal(float, float)

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self._values: tuple[float, ...] = ()
        self._drag_index: int | None = None
        self._hover_index: int | None = None
        self._pulse_index: int | None = None
        self._pulse_started = 0.0
        self._pulse_duration_s = 0.46
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(16)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self.setMinimumHeight(44)
        self.setMaximumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        if kind in {"eq", "dyn", "fx", "ai"}:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        if kind == "eq":
            self.setToolTip("Drag EQ points to tune Low, Mid, and High gain. Double-click a point to reset it.")
        elif kind == "dyn":
            self.setToolTip("Drag the knee for threshold, or the right point for ratio. Double-click a point to reset it.")
        elif kind == "fx":
            self.setToolTip("Drag FX points to tune Reverb, Delay, and De-esser. Double-click a point to reset it.")
        elif kind == "ai":
            self.setToolTip("Drag AI macro points to tune Air, Clarity, Warmth, Width, Punch, and Excite. Double-click a point to reset it.")

    def set_values(self, *values: float) -> None:
        self._values = tuple(float(v or 0.0) for v in values)
        self.update()

    def _plot_rect(self) -> QRectF:
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        return rect.adjusted(10.0, 8.0, -10.0, -8.0)

    def _eq_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        vals = (self._values + (0.0, 0.0, 0.0))[:3]
        points: list[QPointF] = []
        for i, gain in enumerate(vals):
            x = plot.left() + plot.width() * i / 2.0
            y = plot.center().y() - max(-12.0, min(12.0, gain)) / 12.0 * plot.height() * 0.42
            points.append(QPointF(x, y))
        return points

    def _nearest_eq_index(self, pos: QPointF) -> int:
        points = self._eq_points()
        if not points:
            return 0
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.35, index) for index, point in enumerate(points)]
        return min(distances)[1]

    def _eq_gain_from_y(self, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 0.0
        normalized = (plot.center().y() - y) / (plot.height() * 0.42)
        return max(-12.0, min(12.0, normalized * 12.0))

    def _emit_eq_edit(self, index: int, y: float) -> None:
        self.value_edited.emit(max(0, min(2, int(index))), round(self._eq_gain_from_y(float(y)), 1))

    def _dyn_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
        ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
        knee_x = plot.left() + plot.width() * ((threshold + 60.0) / 60.0)
        low = QPointF(plot.left(), plot.bottom())
        knee = QPointF(knee_x, plot.bottom() - plot.height() * 0.58)
        high = QPointF(plot.right(), knee.y() - plot.height() * (0.30 / ratio))
        return [low, knee, high]

    def _nearest_dyn_index(self, pos: QPointF) -> int:
        points = self._dyn_points()
        handles = ((0, points[1]), (1, points[2]))
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.6, index) for index, point in handles]
        return min(distances)[1]

    def _dyn_threshold_from_x(self, x: float) -> float:
        plot = self._plot_rect()
        if plot.width() <= 0:
            return -20.0
        normalized = max(0.0, min(1.0, (float(x) - plot.left()) / plot.width()))
        return -60.0 + normalized * 60.0

    def _dyn_ratio_from_y(self, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 4.0
        knee_y = plot.bottom() - plot.height() * 0.58
        distance = max(plot.height() * 0.015, knee_y - float(y))
        ratio = plot.height() * 0.30 / distance
        return max(1.0, min(20.0, ratio))

    def _emit_dyn_edit(self, handle_index: int, pos: QPointF) -> None:
        threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
        ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
        if int(handle_index) == 0:
            threshold = self._dyn_threshold_from_x(pos.x())
        else:
            ratio = self._dyn_ratio_from_y(pos.y())
        self.dynamics_edited.emit(round(threshold, 1), round(ratio, 1))

    def _fx_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        vals = (self._values + (0.0, 0.0, 0.0))[:3]
        baseline = plot.bottom() - plot.height() * 0.24
        points = [QPointF(plot.left(), baseline)]
        for index, value in enumerate(vals):
            normalized = max(0.0, min(1.0, float(value) / 100.0))
            x = plot.left() + plot.width() * (index + 1.0) / 4.0
            y = plot.bottom() - plot.height() * (0.14 + normalized * 0.74)
            points.append(QPointF(x, y))
        points.append(QPointF(plot.right(), baseline))
        return points

    def _nearest_fx_index(self, pos: QPointF) -> int:
        handles = self._fx_points()[1:4]
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.55, index) for index, point in enumerate(handles)]
        return min(distances)[1]

    def _fx_value_from_y(self, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 0.0
        normalized = (plot.bottom() - float(y)) / plot.height()
        return max(0.0, min(100.0, (normalized - 0.14) / 0.74 * 100.0))

    def _emit_fx_edit(self, index: int, y: float) -> None:
        self.value_edited.emit(max(0, min(2, int(index))), round(self._fx_value_from_y(float(y)), 0))

    @staticmethod
    def _ai_max_values() -> tuple[float, ...]:
        return (8.0, 100.0, 100.0, 200.0, 100.0, 100.0)

    def _ai_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        max_values = self._ai_max_values()
        vals = (self._values + (0.0,) * len(max_values))[: len(max_values)]
        points: list[QPointF] = []
        for index, value in enumerate(vals):
            normalized = max(0.0, min(1.0, float(value) / max_values[index]))
            x = plot.left() + plot.width() * (index + 0.5) / len(max_values)
            y = plot.bottom() - plot.height() * (0.10 + normalized * 0.78)
            points.append(QPointF(x, y))
        return points

    def _nearest_ai_index(self, pos: QPointF) -> int:
        points = self._ai_points()
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.48, index) for index, point in enumerate(points)]
        return min(distances)[1]

    def _ai_value_from_y(self, index: int, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 0.0
        max_value = self._ai_max_values()[max(0, min(len(self._ai_max_values()) - 1, int(index)))]
        normalized = (plot.bottom() - float(y)) / plot.height()
        value = max(0.0, min(1.0, (normalized - 0.10) / 0.78)) * max_value
        return round(value, 1 if int(index) == 0 else 0)

    def _emit_ai_edit(self, index: int, y: float) -> None:
        index = max(0, min(len(self._ai_max_values()) - 1, int(index)))
        self.value_edited.emit(index, self._ai_value_from_y(index, float(y)))

    def _reset_handle(self, index: int) -> None:
        if self._kind == "eq":
            self.value_edited.emit(max(0, min(2, int(index))), 0.0)
            return
        if self._kind == "dyn":
            threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
            ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
            if int(index) == 0:
                threshold = -20.0
            else:
                ratio = 4.0
            self.dynamics_edited.emit(round(threshold, 1), round(ratio, 1))
            return
        if self._kind == "fx":
            defaults = (20.0, 20.0, 40.0)
            reset_index = max(0, min(2, int(index)))
            self.value_edited.emit(reset_index, defaults[reset_index])
            return
        if self._kind == "ai":
            defaults = (0.0, 0.0, 0.0, 100.0, 0.0, 0.0)
            reset_index = max(0, min(len(defaults) - 1, int(index)))
            self.value_edited.emit(reset_index, defaults[reset_index])


    def _nearest_index(self, pos: QPointF) -> int | None:
        if self._kind == "eq":
            return self._nearest_eq_index(pos)
        if self._kind == "dyn":
            return self._nearest_dyn_index(pos)
        if self._kind == "fx":
            return self._nearest_fx_index(pos)
        if self._kind == "ai":
            return self._nearest_ai_index(pos)
        return None

    def _set_hover_index(self, index: int | None) -> None:
        if self._hover_index == index:
            return
        self._hover_index = index
        self.update()

    def _active_index(self) -> int | None:
        return self._drag_index if self._drag_index is not None else self._hover_index

    def _tick_pulse(self) -> None:
        if self._pulse_index is None:
            self._pulse_timer.stop()
            return
        if time.monotonic() - self._pulse_started >= self._pulse_duration_s:
            self._pulse_index = None
            self._pulse_timer.stop()
        self.update()

    def _start_release_pulse(self, index: int | None) -> None:
        if index is None:
            return
        self._pulse_index = int(index)
        self._pulse_started = time.monotonic()
        if not self._pulse_timer.isActive():
            self._pulse_timer.start()
        self.update()

    def _pulse_amount(self, index: int) -> float:
        if self._pulse_index != index:
            return 0.0
        elapsed = time.monotonic() - self._pulse_started
        if elapsed >= self._pulse_duration_s:
            return 0.0
        t = max(0.0, min(1.0, 1.0 - elapsed / self._pulse_duration_s))
        return t * t * (3.0 - 2.0 * t)

    def _pin_emphasis(self, index: int) -> float:
        if self._active_index() == index:
            return 1.0
        return self._pulse_amount(index)

    def mousePressEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton:
            if self._kind == "eq":
                self._drag_index = self._nearest_eq_index(event.position())
                self._emit_eq_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._kind == "dyn":
                self._drag_index = self._nearest_dyn_index(event.position())
                self._emit_dyn_edit(self._drag_index, event.position())
                event.accept()
                return
            if self._kind == "fx":
                self._drag_index = self._nearest_fx_index(event.position())
                self._emit_fx_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._kind == "ai":
                self._drag_index = self._nearest_ai_index(event.position())
                self._emit_ai_edit(self._drag_index, event.position().y())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton and self._kind in {"eq", "dyn", "fx", "ai"}:
            index = self._nearest_index(event.position())
            if index is not None:
                self._reset_handle(index)
                self._start_release_pulse(index)
                self._drag_index = None
                self._hover_index = None
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._kind in {"eq", "dyn", "fx", "ai"}:
            if self._drag_index is None:
                self._set_hover_index(self._nearest_index(event.position()))
            if self._drag_index is not None and self._kind == "eq":
                self._emit_eq_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._drag_index is not None and self._kind == "dyn":
                self._emit_dyn_edit(self._drag_index, event.position())
                event.accept()
                return
            if self._drag_index is not None and self._kind == "fx":
                self._emit_fx_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._drag_index is not None and self._kind == "ai":
                self._emit_ai_edit(self._drag_index, event.position().y())
                event.accept()
                return
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._drag_index is not None and event.button() == Qt.MouseButton.LeftButton:
            if self._kind == "eq":
                self._emit_eq_edit(self._drag_index, event.position().y())
            elif self._kind == "dyn":
                self._emit_dyn_edit(self._drag_index, event.position())
            elif self._kind == "fx":
                self._emit_fx_edit(self._drag_index, event.position().y())
            elif self._kind == "ai":
                self._emit_ai_edit(self._drag_index, event.position().y())
            self._start_release_pulse(self._drag_index)
            self._hover_index = None
            self._drag_index = None
            event.accept()
            self.update()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # pragma: no cover - visual QA
        self._set_hover_index(None)
        super().leaveEvent(event)

    def _accent_color(self, index: int | None = None) -> QColor:
        palettes = {
            "eq": ("#6CCFA6", "#72B9DC", "#D8B35F"),
            "dyn": ("#DDB25D", "#D58272"),
            "fx": ("#A981E0", "#62B9D3", "#D47F8A"),
            "ai": ("#77B8E8", "#8ED59D", "#D9B75F", "#B48BE8", "#D88499", "#65D0C2"),
        }
        colors = palettes.get(self._kind) or ("#AEB6C2",)
        idx = max(0, min(len(colors) - 1, int(index or 0)))
        return QColor(colors[idx])

    def _line_gradient(self, start: QPointF, end: QPointF, accent: QColor | None = None) -> QLinearGradient:
        grad = QLinearGradient(start, end)
        left = QColor("#858E98")
        mid = QColor("#C1C8CF")
        right = QColor("#8F969D")
        for col, alpha in ((left, 198), (mid, 232), (right, 198)):
            col.setAlpha(alpha)
        grad.setColorAt(0.0, left)
        if accent is not None and accent.isValid():
            acc = QColor(accent)
            acc.setAlpha(224)
            soft = QColor(accent)
            soft.setAlpha(154)
            grad.setColorAt(0.38, soft)
            grad.setColorAt(0.55, acc)
            grad.setColorAt(0.72, soft)
        else:
            grad.setColorAt(0.50, mid)
        grad.setColorAt(1.0, right)
        return grad

    def _draw_path(
        self,
        p: QPainter,
        points: list[QPointF],
        plot: QRectF,
        *,
        width: float = 2.15,
        accent: QColor | None = None,
    ) -> None:
        if len(points) < 2:
            return
        accent = QColor(accent or self._accent_color())
        shadow_pen = QPen(QColor(0, 0, 0, 118), width + 1.65)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        shadow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(shadow_pen)
        p.drawPolyline(points)
        glow = QColor(accent)
        glow.setAlpha(42)
        under_glow = QPen(glow, width + 1.35)
        under_glow.setCapStyle(Qt.PenCapStyle.RoundCap)
        under_glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(under_glow)
        p.drawPolyline(points)
        line_pen = QPen(
            QBrush(self._line_gradient(QPointF(plot.left(), plot.center().y()), QPointF(plot.right(), plot.center().y()), accent)),
            width,
        )
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(line_pen)
        p.drawPolyline(points)
        accent_hi = QColor(accent)
        accent_hi.setAlpha(112)
        accent_pen = QPen(accent_hi, max(0.7, width * 0.46))
        accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        accent_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(accent_pen)
        p.drawPolyline([QPointF(point.x(), point.y() - 0.2) for point in points])
        highlight = QColor(255, 255, 255, 56)
        hi_pen = QPen(highlight, max(0.65, width * 0.36))
        hi_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        hi_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(hi_pen)
        p.drawPolyline([QPointF(point.x(), point.y() - 0.75) for point in points])

    @staticmethod
    def _draw_pin(
        p: QPainter,
        point: QPointF,
        *,
        radius: float = 3.7,
        emphasis: float = 0.0,
        accent: QColor | None = None,
    ) -> None:
        emphasis = max(0.0, min(1.0, float(emphasis)))
        accent = QColor(accent or QColor("#AEB6C2"))
        radius += 0.55 * emphasis
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, int(120 + 15 * emphasis)))
        p.drawEllipse(QPointF(point.x(), point.y() + 1.2), radius + 0.9, radius + 0.9)
        halo = QColor(accent)
        halo.setAlpha(int(42 + 42 * emphasis))
        p.setBrush(halo)
        p.drawEllipse(point, radius + 1.7 + 0.4 * emphasis, radius + 1.7 + 0.4 * emphasis)
        pin = QRadialGradient(QPointF(point.x() - 1.2, point.y() - 1.4), radius + 2.1)
        core = QColor(
            int((59 + accent.red() * 0.12) + (82 - 59) * emphasis),
            int((66 + accent.green() * 0.10) + (88 - 66) * emphasis),
            int((75 + accent.blue() * 0.10) + (98 - 75) * emphasis),
        )
        mid = QColor(
            int(37 + (46 - 37) * emphasis),
            int(42 + (53 - 42) * emphasis),
            int(49 + (64 - 49) * emphasis),
        )
        pin.setColorAt(0.0, core)
        pin.setColorAt(0.58, mid)
        pin.setColorAt(1.0, QColor("#171B20"))
        p.setBrush(QBrush(pin))
        rim = QColor(accent)
        rim.setAlpha(int(162 + 70 * emphasis))
        p.setPen(QPen(rim, 0.85 + 0.2 * emphasis))
        p.drawEllipse(point, radius, radius)
        p.setPen(QPen(QColor(255, 255, 255, int(42 + 26 * emphasis)), 0.75))
        p.drawPoint(QPointF(point.x() - 1.2, point.y() - 1.2))

    def _active_point_label(self, index: int, point: QPointF) -> str:
        if self._kind == "eq":
            names = ("Low", "Mid", "High")
            values = (self._values + (0.0, 0.0, 0.0))[:3]
            return f"{names[index]} {float(values[index]):.1f} dB"
        if self._kind == "dyn":
            if index == 0:
                threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
                return f"Threshold {threshold:.1f} dB"
            ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
            return f"Ratio {ratio:.1f}:1"
        if self._kind == "fx":
            names = ("Reverb", "Delay", "De-ess")
            values = (self._values + (0.0, 0.0, 0.0))[:3]
            return f"{names[index]} {float(values[index]):.0f}%"
        if self._kind == "ai":
            names = ("Air", "Clarity", "Warmth", "Width", "Punch", "Excite")
            values = (self._values + (0.0,) * len(names))[: len(names)]
            suffix = " dB" if index == 0 else "%"
            return f"{names[index]} {float(values[index]):.1f}{suffix}" if index == 0 else f"{names[index]} {float(values[index]):.0f}{suffix}"
        return ""

    def _draw_active_label(self, p: QPainter, plot: QRectF, index: int, point: QPointF) -> None:
        label = self._active_point_label(index, point)
        if not label:
            return
        font = p.font()
        font.setPixelSize(8)
        font.setBold(True)
        p.setFont(font)
        metrics = p.fontMetrics()
        width = min(plot.width() - 6.0, float(metrics.horizontalAdvance(label) + 12))
        height = 16.0
        x = point.x() + 7.0
        if x + width > plot.right():
            x = point.x() - width - 7.0
        x = max(plot.left() + 2.0, min(x, plot.right() - width - 2.0))
        y = point.y() - height - 8.0
        if y < plot.top() + 2.0:
            y = point.y() + 8.0
        rect = QRectF(x, y, width, height)
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QColor(34, 39, 46, 226))
        bg.setColorAt(1.0, QColor(20, 23, 28, 236))
        p.setPen(QPen(QColor(220, 226, 236, 58), 0.8))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, 4.0, 4.0)
        p.setPen(QColor("#DCE2EA"))
        p.drawText(rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QColor(29, 34, 40, 168))
        bg.setColorAt(1.0, QColor(16, 18, 20, 210))
        p.setPen(QPen(QColor(178, 186, 202, 38), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 6.0, 6.0)

        plot = self._plot_rect()
        p.setPen(QPen(QColor(255, 255, 255, 16), 1.0))
        for i in range(1, 4):
            y = plot.top() + plot.height() * i / 4.0
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        for i in range(1, 5):
            x = plot.left() + plot.width() * i / 5.0
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))

        if self._kind == "eq":
            points = self._eq_points(plot)
            active = self._active_index()
            self._draw_path(p, points, plot, accent=self._accent_color(1))
            for index, point in enumerate(points):
                self._draw_pin(p, point, emphasis=self._pin_emphasis(index), accent=self._accent_color(index))
            if active is not None and 0 <= active < len(points):
                self._draw_active_label(p, plot, active, points[active])
            return

        if self._kind == "dyn":
            low, knee, high = self._dyn_points(plot)
            active = self._active_index()
            self._draw_path(p, [low, knee, high], plot, width=1.65, accent=self._accent_color(0))
            p.setPen(QPen(QColor(220, 226, 236, 64), 0.85))
            p.drawLine(QPointF(knee.x(), plot.top()), QPointF(knee.x(), plot.bottom()))
            self._draw_pin(p, knee, radius=3.5, emphasis=self._pin_emphasis(0), accent=self._accent_color(0))
            self._draw_pin(p, high, radius=3.0, emphasis=self._pin_emphasis(1), accent=self._accent_color(1))
            if active == 0:
                self._draw_active_label(p, plot, active, knee)
            elif active == 1:
                self._draw_active_label(p, plot, active, high)
            return

        if self._kind == "fx":
            points = self._fx_points(plot)
            active = self._active_index()
            self._draw_path(p, points, plot, width=1.45, accent=self._accent_color(0))
            for index, point in enumerate(points[1:4]):
                self._draw_pin(p, point, radius=2.8, emphasis=self._pin_emphasis(index), accent=self._accent_color(index))
            if active is not None and 0 <= active < 3:
                self._draw_active_label(p, plot, active, points[active + 1])
            return

        if self._kind == "ai":
            points = self._ai_points(plot)
            max_values = self._ai_max_values()
            vals = (self._values + (0.0,) * len(max_values))[: len(max_values)]
            bar_w = max(12.0, plot.width() / 12.0)
            active = self._active_index()
            p.setPen(Qt.PenStyle.NoPen)
            baseline = plot.bottom() - plot.height() * 0.06
            p.setPen(QPen(QColor(220, 226, 236, 22), 1.0))
            p.drawLine(QPointF(plot.left(), baseline), QPointF(plot.right(), baseline))
            for i, (value, point) in enumerate(zip(vals, points)):
                normalized = max(0.035, min(1.0, float(value) / max_values[i]))
                h = plot.height() * (0.10 + normalized * 0.78)
                bar = QRectF(point.x() - bar_w * 0.5, plot.bottom() - h, bar_w, h)
                grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
                top = self._accent_color(i)
                top.setAlpha(206 if i != 3 else 226)
                bottom = QColor("#242A31")
                bottom.setAlpha(218)
                mid = QColor(top)
                mid.setAlpha(96)
                grad.setColorAt(0.0, top)
                grad.setColorAt(0.62, mid)
                grad.setColorAt(1.0, bottom)
                p.setBrush(QBrush(grad))
                p.setPen(QPen(QColor(220, 226, 236, 34), 0.75))
                p.drawRoundedRect(bar, 2.4, 2.4)
                self._draw_pin(p, point, radius=2.55, emphasis=self._pin_emphasis(i), accent=self._accent_color(i))
            if active is not None and 0 <= active < len(points):
                self._draw_active_label(p, plot, active, points[active])
            return

        values = self._values or (0.0,)
        count = max(1, len(values))
        bar_w = max(10.0, plot.width() / max(8.0, count * 2.4))
        p.setPen(Qt.PenStyle.NoPen)
        for i, value in enumerate(values):
            normalized = max(0.035, min(1.0, float(value)))
            x = plot.left() + plot.width() * (float(i) + 0.5) / float(count)
            h = plot.height() * (0.10 + normalized * 0.78)
            bar = QRectF(x - bar_w * 0.5, plot.bottom() - h, bar_w, h)
            grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            top = QColor("#B7C8A2" if i % 2 else "#9AA8BD")
            top.setAlpha(170)
            bottom = QColor("#252A31")
            bottom.setAlpha(210)
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bottom)
            p.setBrush(QBrush(grad))
            p.setPen(QPen(QColor(220, 226, 236, 42), 0.75))
            p.drawRoundedRect(bar, 2.5, 2.5)
            self._draw_pin(p, QPointF(bar.center().x(), bar.top()), radius=2.6, accent=self._accent_color(i))


class _SoundJogShuttle05(QWidget):
    """Speed Editor-inspired deck: transport stack, matte jog wheel, key bank."""

    position_changed = Signal(int)
    playing_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self._position_ms = 0
        self._duration_ms = 1
        self._level = 0.0
        self._playing = False
        self._dial_pressed = False
        self._slot_anim_tick = 0
        self._slot_anim_timer = QTimer(self)
        self._slot_anim_timer.setInterval(90)
        self._slot_anim_timer.timeout.connect(self._tick_slot_animation)
        self._dial_texture = QPixmap(str(_SOUND_JOG_DIAL_TEXTURE)) if _SOUND_JOG_DIAL_TEXTURE.is_file() else QPixmap()
        self.setObjectName("SoundJogShuttle05")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(126)
        self.setMaximumHeight(142)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 15, 10, 15)
        root.setSpacing(0)
        stack = QVBoxLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(7)
        self._prev_btn = self._transport_button("previous", "Step back")
        self._stop_btn = self._transport_button("stop", "Stop and return to start")
        self._next_btn = self._transport_button("next", "Step forward")
        self._prev_btn.clicked.connect(lambda: self._step(-1000))
        self._stop_btn.clicked.connect(self._stop)
        self._next_btn.clicked.connect(lambda: self._step(1000))
        for button in (self._prev_btn, self._stop_btn, self._next_btn):
            stack.addWidget(button)
        root.addLayout(stack)
        root.addStretch(1)

    def _transport_button(self, icon: str, tooltip: str) -> QPushButton:
        button = QPushButton("", self)
        button.setObjectName("SoundJogButton")
        button.setIcon(app_icon(icon, size=14, color="#D7DAE7"))
        button.setIconSize(icon_size(13))
        button.setToolTip(tooltip)
        button.setFixedSize(36, 30)
        return button

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self._duration_ms = max(1, int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 1))
        self._position_ms = max(0, min(self._duration_ms, int(getattr(clip, "_se_jog_ms", 0) or 0))) if clip is not None else 0
        self._playing = bool(getattr(clip, "_se_jog_playing", False)) if clip is not None else False
        self._level = self._derive_level(clip)
        if self._playing:
            self._slot_anim_timer.start()
        else:
            self._slot_anim_timer.stop()
        self.update()

    def _derive_level(self, clip: AudioClip | None) -> float:
        if clip is None:
            return 0.0
        waveform = getattr(clip, "waveform", None)
        try:
            if waveform is not None and int(getattr(waveform, "size", 0) or 0) > 0:
                peak = float(abs(waveform).max())
                return max(0.05, min(1.0, peak))
        except Exception:
            pass
        try:
            return max(0.05, min(1.0, float(getattr(clip, "gain", 1.0) or 1.0) / 1.5))
        except Exception:
            return 0.2

    def _ring_values(self, count: int = 36) -> list[float]:
        waveform = getattr(self._clip, "waveform", None) if self._clip is not None else None
        if waveform is None or not getattr(waveform, "size", 0):
            return [0.24 if i % 3 else 0.42 for i in range(count)]
        try:
            import numpy as np

            data = np.asarray(waveform, dtype=np.float32)
            mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
            if not mono.size:
                return [0.24 if i % 3 else 0.42 for i in range(count)]
            idx = np.linspace(0, mono.size - 1, count, dtype=np.int32)
            vals = np.abs(mono[idx])
            peak = max(float(vals.max()), 0.005)
            return [max(0.16, min(1.0, float(v) / peak)) for v in vals]
        except Exception:
            return [0.24 if i % 3 else 0.42 for i in range(count)]

    def _deck_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(52.0, 12.0, -35.0, -12.0)

    def _dial_rect(self) -> QRectF:
        deck = self._deck_rect()
        meter = self._meter_rect()
        available = QRectF(deck.left(), deck.top(), max(80.0, meter.left() - deck.left() - 18.0), deck.height())
        size = max(66.0, min(available.height() * 0.88, available.width() * 0.25))
        cx = available.right() - size * 0.62
        cy = available.center().y() + 2.0
        return QRectF(cx - size * 0.5, cy - size * 0.5, size, size)

    def _aux_key_rects(self) -> list[QRectF]:
        deck = self._deck_rect()
        dial = self._dial_rect()
        left = deck.left() + 12.0
        top = deck.top() + 34.0
        cols = 4
        gap = 5.0
        available = max(145.0, min(236.0, dial.left() - left - 22.0))
        key_w = max(34.0, min(52.0, (available - gap * (cols - 1)) / cols))
        key_h = max(22.0, min(29.0, (deck.height() - 52.0 - gap) / 2.0))
        return [
            QRectF(left + col * (key_w + gap), top + row * (key_h + gap), key_w, key_h)
            for row in range(2)
            for col in range(cols)
        ]

    def _aux_dial_rects(self) -> list[QRectF]:
        """Compatibility shim for older tests; these are now rectangular deck keys."""
        return self._aux_key_rects()

    def _display_rect(self) -> QRectF:
        deck = self._deck_rect()
        keys = self._aux_key_rects()
        dial = self._dial_rect()
        key_right = max((r.right() for r in keys), default=deck.left() + 190.0)
        left = key_right + 18.0
        right = max(left + 94.0, dial.left() - 18.0)
        width = min(260.0, right - left)
        return QRectF(left, deck.top() + 45.0, width, 46.0)

    def _mode_key_rects(self) -> list[tuple[str, QRectF, bool]]:
        dial = self._dial_rect()
        width = max(38.0, min(50.0, dial.width() * 0.32))
        gap = 5.0
        total = width * 3.0 + gap * 2.0
        left = dial.center().x() - total * 0.5
        top = max(self._deck_rect().top() + 17.0, dial.top() - 4.0)
        return [
            ("SHUT", QRectF(left, top, width, 22.0), False),
            ("JOG", QRectF(left + width + gap, top, width, 22.0), True),
            ("SCRL", QRectF(left + (width + gap) * 2.0, top, width, 22.0), False),
        ]

    def _aux_dial_specs(self) -> list[tuple[str, float, QColor]]:
        clip = self._clip
        gain = 0.5
        fade_in = 0.0
        fade_out = 0.0
        speed = 0.5
        pitch = 0.5
        ai_amount = 0.0
        if clip is not None:
            try:
                gain = max(0.0, min(1.0, float(getattr(clip, "gain", 1.0) or 1.0) / 2.0))
            except Exception:
                gain = 0.5
            try:
                fade_in = max(0.0, min(1.0, float(getattr(clip, "fade_in_ms", 0) or 0) / 5000.0))
                fade_out = max(0.0, min(1.0, float(getattr(clip, "fade_out_ms", 0) or 0) / 5000.0))
            except Exception:
                fade_in = fade_out = 0.0
            try:
                speed = (float(getattr(clip, "_se_speed", 1.0) or 1.0) - 0.5) / 1.5
                speed = max(0.0, min(1.0, speed))
            except Exception:
                speed = 0.5
            try:
                pitch = (float(getattr(clip, "_se_pitch", 0.0) or 0.0) + 12.0) / 24.0
                pitch = max(0.0, min(1.0, pitch))
            except Exception:
                pitch = 0.5
            try:
                ai = (getattr(clip, "effects", {}) or {}).get("ai_master", {}) or {}
                ai_values = [
                    float(ai.get("air", 0.0) or 0.0) / 8.0,
                    float(ai.get("clarity", 0.0) or 0.0) / 100.0,
                    float(ai.get("warmth", 0.0) or 0.0) / 100.0,
                    float(ai.get("width", 100.0) or 100.0) / 200.0,
                    float(ai.get("punch", 0.0) or 0.0) / 100.0,
                    float(ai.get("excite", 0.0) or 0.0) / 100.0,
                ]
                ai_amount = max(0.0, min(1.0, sum(ai_values) / max(1, len(ai_values))))
            except Exception:
                ai_amount = 0.0
        return [
            ("GAIN", gain, QColor(118, 145, 123, 198)),
            ("PAN", 0.5, QColor(90, 139, 154, 164)),
            ("IN", fade_in, QColor(118, 145, 123, 164)),
            ("OUT", fade_out, QColor(164, 150, 105, 176)),
            ("SPD", speed, QColor(90, 139, 154, 194)),
            ("PCH", pitch, QColor(136, 121, 160, 186)),
            ("AI", ai_amount, QColor(164, 99, 94, 186)),
            ("LVL", max(0.0, min(1.0, self._level)), QColor(164, 150, 105, 192)),
        ]

    def _meter_rect(self) -> QRectF:
        rect = QRectF(self.rect())
        return QRectF(rect.right() - 25.0, rect.top() + 16.0, 10.0, rect.height() - 32.0)

    def _normalized_position(self) -> float:
        return max(0.0, min(1.0, self._position_ms / max(1, self._duration_ms)))

    def _set_position_ms(self, value: int, *, emit: bool = True) -> None:
        value = max(0, min(self._duration_ms, int(value)))
        if value == self._position_ms:
            return
        self._position_ms = value
        self._slot_anim_tick = (self._slot_anim_tick + 2) % 10000
        if self._clip is not None:
            setattr(self._clip, "_se_jog_ms", value)
        self.update()
        if emit:
            self.position_changed.emit(value)

    def _set_playing(self, playing: bool) -> None:
        playing = bool(playing)
        if self._playing == playing:
            return
        self._playing = playing
        if self._clip is not None:
            setattr(self._clip, "_se_jog_playing", playing)
        if playing:
            self._slot_anim_timer.start()
        else:
            self._slot_anim_timer.stop()
        self.update()
        self.playing_changed.emit(playing)

    def _tick_slot_animation(self) -> None:
        self._slot_anim_tick = (self._slot_anim_tick + 1) % 10000
        self.update()

    def _step(self, delta_ms: int) -> None:
        self._set_position_ms(self._position_ms + int(delta_ms))

    def _stop(self) -> None:
        self._set_playing(False)
        self._set_position_ms(0)

    def _position_from_point(self, point: QPointF) -> int:
        dial = self._dial_rect()
        center = dial.center()
        angle = math.atan2(point.y() - center.y(), point.x() - center.x())
        normalized = (angle + math.pi * 1.25) / (math.pi * 1.5)
        normalized = max(0.0, min(1.0, normalized))
        return int(round(normalized * self._duration_ms))

    def mousePressEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton and self._dial_rect().contains(event.position()):
            self._dial_pressed = True
            self._set_position_ms(self._position_from_point(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._dial_pressed:
            self._set_position_ms(self._position_from_point(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._dial_pressed and event.button() == Qt.MouseButton.LeftButton:
            self._dial_pressed = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton and self._dial_rect().contains(event.position()):
            self._set_playing(not self._playing)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        delta = 250 if event.angleDelta().y() > 0 else -250
        self._step(delta)
        event.accept()

    def _draw_deck_key(self, p: QPainter, rect: QRectF, label: str, value: float, accent: QColor) -> None:
        value = max(0.0, min(1.0, float(value)))
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(34, 40, 47, 235))
        grad.setColorAt(1.0, QColor(18, 22, 27, 245))
        p.setBrush(grad)
        p.setPen(QPen(QColor(82, 92, 104, 96), 0.85))
        p.drawRoundedRect(rect, 4.5, 4.5)

        fill = QRectF(rect.left() + 5.0, rect.bottom() - 5.0, max(4.0, (rect.width() - 10.0) * value), 1.8)
        accent_line = QColor(accent)
        accent_line.setAlpha(186)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent_line)
        p.drawRoundedRect(fill, 1.0, 1.0)

        font = p.font()
        font.setPixelSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(218, 224, 234, 170))
        p.drawText(rect.adjusted(1.0, 1.0, -1.0, -3.0), Qt.AlignmentFlag.AlignCenter, label)

    def _draw_mode_key(self, p: QPainter, rect: QRectF, label: str, active: bool) -> None:
        fill = QColor(176, 182, 180, 218) if active else QColor(22, 27, 33, 235)
        border = QColor(230, 235, 236, 70) if active else QColor(82, 92, 104, 72)
        p.setPen(QPen(border, 0.85))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 4.0, 4.0)
        font = p.font()
        font.setPixelSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(24, 27, 29, 230) if active else QColor(206, 214, 225, 145))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_slotted_jog_dial(self, p: QPainter, dial: QRectF) -> None:
        center = dial.center()
        radius = dial.width() * 0.5

        metal = dial.adjusted(radius * 0.13, radius * 0.13, -radius * 0.13, -radius * 0.13)
        texture_used = not self._dial_texture.isNull()
        if texture_used:
            texture_rect = dial.adjusted(-radius * 0.20, -radius * 0.20, radius * 0.20, radius * 0.20)
            source = QRectF(self._dial_texture.rect()).adjusted(115.0, 115.0, -115.0, -115.0)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.save()
            clip = QPainterPath()
            clip.addEllipse(texture_rect.adjusted(1.0, 1.0, -1.0, -1.0))
            p.setClipPath(clip)
            p.drawPixmap(texture_rect, self._dial_texture, source)
            p.restore()
        else:
            p.setPen(QPen(QColor(5, 7, 9, 220), 1.0))
            p.setBrush(QColor(8, 10, 13, 235))
            p.drawEllipse(dial.adjusted(-8.0, -8.0, 8.0, 8.0))

            outer = dial.adjusted(radius * 0.02, radius * 0.02, -radius * 0.02, -radius * 0.02)
            outer_grad = QRadialGradient(center, radius)
            outer_grad.setColorAt(0.0, QColor(44, 48, 50, 222))
            outer_grad.setColorAt(0.58, QColor(28, 31, 33, 240))
            outer_grad.setColorAt(0.84, QColor(10, 12, 14, 250))
            outer_grad.setColorAt(1.0, QColor(4, 5, 6, 255))
            p.setPen(QPen(QColor(225, 230, 236, 34), 1.0))
            p.setBrush(QBrush(outer_grad))
            p.drawEllipse(outer)

            metal_grad = QRadialGradient(
                QPointF(center.x() - radius * 0.14, center.y() - radius * 0.18),
                radius * 0.90,
            )
            metal_grad.setColorAt(0.0, QColor(178, 181, 174, 220))
            metal_grad.setColorAt(0.25, QColor(108, 112, 110, 232))
            metal_grad.setColorAt(0.54, QColor(57, 62, 62, 242))
            metal_grad.setColorAt(0.78, QColor(88, 91, 86, 232))
            metal_grad.setColorAt(1.0, QColor(18, 20, 21, 252))
            p.setPen(QPen(QColor(240, 244, 245, 28), 0.8))
            p.setBrush(QBrush(metal_grad))
            p.drawEllipse(metal)

            for i in range(80):
                angle = math.radians(i * 360.0 / 80.0)
                p.setPen(QPen(QColor(245, 247, 242, 4 if i % 5 else 7), 0.22))
                start = QPointF(
                    center.x() + math.cos(angle) * radius * 0.18,
                    center.y() + math.sin(angle) * radius * 0.18,
                )
                end = QPointF(
                    center.x() + math.cos(angle) * radius * 0.69,
                    center.y() + math.sin(angle) * radius * 0.69,
                )
                p.drawLine(start, end)

            for scale, alpha in ((0.28, 10), (0.48, 12), (0.69, 15)):
                p.setPen(QPen(QColor(255, 255, 255, alpha), 0.45))
                inset = radius * (1.0 - scale)
                p.drawEllipse(dial.adjusted(inset, inset, -inset, -inset))

        slot_count = 8
        active_index = int(round(self._normalized_position() * slot_count)) % slot_count
        if self._playing:
            active_index = (active_index + self._slot_anim_tick // 4) % slot_count
        slot_radius = radius * 0.82
        slot_w = max(1.35, radius * 0.022)
        slot_h = max(3.4, radius * 0.052)

        for i in range(slot_count):
            angle_deg = -90.0 + i * 360.0 / slot_count
            angle = math.radians(angle_deg)
            slot_center = QPointF(
                center.x() + math.cos(angle) * slot_radius,
                center.y() + math.sin(angle) * slot_radius,
            )
            trail = (active_index - i) % slot_count
            intensity = 0.0
            if trail <= 2:
                intensity = 1.0 - trail / 3.0

            p.save()
            p.translate(slot_center)
            p.rotate(angle_deg + 90.0)
            slot = QRectF(-slot_w * 0.5, -slot_h * 0.5, slot_w, slot_h)
            if intensity > 0.0:
                glow = QColor(92, 196, 158, int(52 + 104 * intensity))
                if trail == 0:
                    glow = QColor(232, 198, 122, int(80 + 128 * intensity))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawRoundedRect(slot.adjusted(-2.0, -1.8, 2.0, 1.8), slot_w * 0.80, slot_w * 0.80)

            p.setPen(QPen(QColor(0, 0, 0, 118), 0.45))
            if intensity > 0.0:
                if trail == 0:
                    fill = QColor(246, 213, 135, int(190 + 54 * intensity))
                else:
                    fill = QColor(105, 218, 172, int(150 + 70 * intensity))
            else:
                fill = QColor(5, 6, 7, 132)
            p.setBrush(fill)
            p.drawRoundedRect(slot, slot_w * 0.45, slot_w * 0.45)
            if intensity > 0.0:
                p.setPen(QPen(QColor(255, 250, 214, int(86 + 80 * intensity)), 0.35))
                p.drawLine(QPointF(0.0, slot.top() + 1.2), QPointF(0.0, slot.bottom() - 1.2))
            p.restore()

        if not texture_used:
            cap = QRectF(center.x() - radius * 0.11, center.y() - radius * 0.11, radius * 0.22, radius * 0.22)
            cap_grad = QRadialGradient(cap.center(), cap.width() * 0.58)
            cap_grad.setColorAt(0.0, QColor(168, 170, 164, 36))
            cap_grad.setColorAt(0.54, QColor(78, 82, 80, 64))
            cap_grad.setColorAt(1.0, QColor(18, 20, 21, 118))
            p.setPen(QPen(QColor(240, 244, 245, 18), 0.55))
            p.setBrush(QBrush(cap_grad))
            p.drawEllipse(cap)
        if self._playing:
            p.setPen(QPen(QColor(104, 144, 128, 108), 0.9))
            p.setBrush(Qt.BrushStyle.NoBrush)
            active_ring = (
                dial.adjusted(radius * 0.23, radius * 0.23, -radius * 0.23, -radius * 0.23)
                if texture_used
                else metal.adjusted(radius * 0.08, radius * 0.08, -radius * 0.08, -radius * 0.08)
            )
            p.drawEllipse(active_ring)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        panel_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        panel_grad.setColorAt(0.0, QColor(20, 24, 30, 246))
        panel_grad.setColorAt(1.0, QColor(10, 13, 16, 248))
        p.setPen(QPen(QColor(178, 186, 202, 32), 1.0))
        p.setBrush(panel_grad)
        p.drawRoundedRect(rect, 8.0, 8.0)

        deck = self._deck_rect()
        deck_grad = QLinearGradient(deck.topLeft(), deck.bottomLeft())
        deck_grad.setColorAt(0.0, QColor(25, 30, 36, 235))
        deck_grad.setColorAt(1.0, QColor(13, 17, 21, 244))
        p.setPen(QPen(QColor(178, 186, 202, 34), 1.0))
        p.setBrush(deck_grad)
        p.drawRoundedRect(deck, 8.0, 8.0)
        p.setPen(QPen(QColor(220, 225, 238, 18), 0.8))
        p.drawLine(QPointF(deck.left() + 10.0, deck.top() + 2.0), QPointF(deck.right() - 10.0, deck.top() + 2.0))

        font = p.font()
        font.setPixelSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(150, 160, 172, 118))
        p.drawText(QRectF(deck.left() + 13.0, deck.top() + 9.0, 92.0, 16.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "EDIT KEYS")
        p.drawText(QRectF(self._display_rect().left(), deck.top() + 9.0, 92.0, 16.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "TRANSPORT")

        for aux_rect, (label, value, accent) in zip(self._aux_key_rects(), self._aux_dial_specs()):
            self._draw_deck_key(p, aux_rect, label, value, accent)

        display = self._display_rect()
        p.setPen(QPen(QColor(85, 95, 108, 72), 0.9))
        p.setBrush(QColor(8, 11, 14, 226))
        p.drawRoundedRect(display, 5.0, 5.0)
        font = p.font()
        font.setPixelSize(16)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(198, 211, 206, 218))
        p.drawText(display.adjusted(9.0, 4.0, -8.0, -18.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{_fmt_ms(self._position_ms)}")
        font.setPixelSize(7)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor(150, 160, 172, 115))
        p.drawText(display.adjusted(9.0, 23.0, -8.0, -4.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"of {_fmt_ms(self._duration_ms)}  jog ready")
        rail_left = display.left()
        rail_top = display.bottom() + 12.0
        rail_w = display.width()
        for row, color in enumerate((QColor(118, 145, 123, 142), QColor(90, 139, 154, 132), QColor(164, 150, 105, 126))):
            y = rail_top + row * 10.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(8, 10, 12, 155))
            p.drawRoundedRect(QRectF(rail_left, y, rail_w, 3.4), 1.7, 1.7)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(rail_left, y, rail_w * (0.72 - row * 0.16), 3.4), 1.7, 1.7)

        self._draw_slotted_jog_dial(p, self._dial_rect())

        meter = self._meter_rect()
        p.setPen(QPen(QColor(178, 186, 202, 32), 1.0))
        p.setBrush(QColor(8, 10, 12, 190))
        p.drawRoundedRect(meter.adjusted(-4.0, -4.0, 4.0, 4.0), 4.0, 4.0)
        bars = 12
        active = int(round(max(0.0, min(1.0, self._level)) * bars))
        gap = 2.0
        bar_h = (meter.height() - gap * (bars - 1)) / bars
        for index in range(bars):
            y = meter.bottom() - (index + 1) * bar_h - index * gap
            bar = QRectF(meter.left(), y, meter.width(), max(1.0, bar_h))
            if index < active:
                if index >= 10:
                    color = QColor(164, 99, 94, 204)
                elif index >= 8:
                    color = QColor(164, 150, 105, 194)
                else:
                    color = QColor(118, 145, 123, 180)
            else:
                color = QColor(74, 80, 90, 72)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(bar, 1.5, 1.5)
        p.end()


class _MiniWaveformStrip(QWidget):
    """Compact waveform evidence strip for the renewed sound editor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self.setMinimumHeight(54)
        self.setMaximumHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self.update()

    def refresh(self) -> None:
        self.update()

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(root.topLeft(), root.bottomLeft())
        bg.setColorAt(0.0, QColor(25, 29, 34, 206))
        bg.setColorAt(1.0, QColor(13, 15, 17, 230))
        p.setPen(QPen(QColor(178, 186, 202, 28), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(root, 6.0, 6.0)

        clip = self._clip
        plot = root.adjusted(9.0, 14.0, -9.0, -8.0)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawLine(QPointF(plot.left(), plot.center().y()), QPointF(plot.right(), plot.center().y()))

        title_font = p.font()
        title_font.setPixelSize(8)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#A7AFBA"))
        label = "waveform"
        if clip is not None:
            label = f"waveform  {_fmt_ms(getattr(clip, 'trim_start_ms', 0))}-{_fmt_ms(getattr(clip, 'trim_end_ms', getattr(clip, 'duration_ms', 0)))}"
        p.drawText(root.adjusted(9, 3, -9, -root.height() + 14), Qt.AlignmentFlag.AlignLeft, label)

        wf = getattr(clip, "waveform", None) if clip is not None else None
        if wf is None or not getattr(wf, "size", 0):
            p.setPen(QColor("#6F7782"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "waveform pending")
            return

        try:
            import numpy as np

            data = np.asarray(wf, dtype=np.float32)
            mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
            if not mono.size:
                return
            trim_start = int(getattr(clip, "trim_start_ms", 0) or 0)
            trim_end = int(getattr(clip, "trim_end_ms", getattr(clip, "duration_ms", 0)) or 0)
            duration = max(1, int(getattr(clip, "duration_ms", 0) or 0))
            start_i = max(0, min(mono.size - 1, int(mono.size * trim_start / duration)))
            end_i = max(start_i + 1, min(mono.size, int(mono.size * max(trim_end, trim_start + 1) / duration)))
            mono = mono[start_i:end_i]
            if not mono.size:
                return
            count = max(2, int(plot.width()))
            idx = np.linspace(0, mono.size - 1, count, dtype=np.int32)
            vals = mono[idx]
            peak = max(float(np.max(np.abs(vals))), 0.005)
            cy = plot.center().y()
            amp = max(6.0, plot.height() * 0.42)
            pts_top: list[QPointF] = []
            pts_bot: list[QPointF] = []
            for i, val in enumerate(vals):
                x = plot.left() + i / max(count - 1, 1) * plot.width()
                h = abs(float(val)) / peak * amp
                pts_top.append(QPointF(x, cy - h))
                pts_bot.append(QPointF(x, cy + h))
            p.setPen(QPen(QColor(142, 218, 158, 226), 1.15))
            p.drawPolyline(pts_top)
            p.setPen(QPen(QColor(105, 181, 218, 190), 0.85))
            p.drawPolyline(pts_bot)

            fade_in = int(getattr(clip, "fade_in_ms", 0) or 0)
            fade_out = int(getattr(clip, "fade_out_ms", 0) or 0)
            eff = max(1, trim_end - trim_start)
            if fade_in > 0:
                w = min(plot.width(), plot.width() * fade_in / eff)
                grad = QLinearGradient(QPointF(plot.left(), 0), QPointF(plot.left() + w, 0))
                grad.setColorAt(0.0, QColor(0, 0, 0, 110))
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.fillRect(QRectF(plot.left(), plot.top(), w, plot.height()), grad)
            if fade_out > 0:
                w = min(plot.width(), plot.width() * fade_out / eff)
                grad = QLinearGradient(QPointF(plot.right() - w, 0), QPointF(plot.right(), 0))
                grad.setColorAt(0.0, QColor(0, 0, 0, 0))
                grad.setColorAt(1.0, QColor(0, 0, 0, 110))
                p.fillRect(QRectF(plot.right() - w, plot.top(), w, plot.height()), grad)
        except Exception:
            p.setPen(QColor("#6F7782"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "waveform unavailable")


class _MiniSpectrumStrip(QWidget):
    """Small spectrum / level evidence strip derived from the active clip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self.setObjectName("SoundSpectrumStrip")
        self.setMinimumHeight(42)
        self.setMaximumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self.update()

    def refresh(self) -> None:
        self.update()

    @staticmethod
    def _spectrum_from_waveform(waveform: Any, count: int = 28) -> tuple[list[float], float]:
        import numpy as np

        data = np.asarray(waveform, dtype=np.float32)
        mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
        if mono.size < 8:
            return [], 0.0
        mono = mono[-min(mono.size, 2048):]
        level = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
        centered = mono - float(np.mean(mono))
        window = np.hanning(centered.size).astype(np.float32)
        mag = np.abs(np.fft.rfft(centered * window)).astype(np.float32)
        if mag.size <= 2:
            return [], level
        mag = mag[1:]
        edges = np.geomspace(1, max(2, mag.size), count + 1).astype(np.int32)
        bins: list[float] = []
        for i in range(count):
            lo = int(max(0, min(mag.size - 1, edges[i] - 1)))
            hi = int(max(lo + 1, min(mag.size, edges[i + 1])))
            bins.append(float(np.mean(mag[lo:hi])))
        peak = max(max(bins), 1e-5)
        return [max(0.02, min(1.0, value / peak)) for value in bins], level

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(root.topLeft(), root.bottomLeft())
        bg.setColorAt(0.0, QColor(24, 27, 31, 196))
        bg.setColorAt(1.0, QColor(11, 13, 15, 224))
        p.setPen(QPen(QColor(178, 186, 202, 24), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(root, 5.5, 5.5)

        label_font = p.font()
        label_font.setPixelSize(8)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QColor("#9EA7B3"))
        p.drawText(root.adjusted(8, 3, -8, -root.height() + 14), Qt.AlignmentFlag.AlignLeft, "spectrum / level")

        clip = self._clip
        plot = root.adjusted(8.0, 17.0, -74.0, -7.0)
        meter = QRectF(root.right() - 58.0, plot.top(), 48.0, plot.height())
        bins: list[float] = []
        level = 0.0
        try:
            import numpy as np

            spectrum = getattr(clip, "spectrum_bins", None) if clip is not None else None
            if spectrum is not None and getattr(spectrum, "size", 0):
                raw = np.asarray(spectrum, dtype=np.float32).ravel()
                peak = max(float(raw.max()), 1e-5)
                step = max(1, int(len(raw) / 28))
                bins = [max(0.02, min(1.0, float(raw[i:i + step].mean()) / peak)) for i in range(0, len(raw), step)][:28]
                wf = getattr(clip, "waveform", None)
                if wf is not None and getattr(wf, "size", 0):
                    level = float(np.sqrt(np.mean(np.square(np.asarray(wf, dtype=np.float32)))))
            else:
                wf = getattr(clip, "waveform", None) if clip is not None else None
                if wf is not None and getattr(wf, "size", 0):
                    bins, level = self._spectrum_from_waveform(wf)
        except Exception:
            bins = []
            level = 0.0

        if not bins:
            p.setPen(QColor("#68717D"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "spectrum pending")
            return

        count = len(bins)
        gap = 2.0
        bar_w = max(2.0, (plot.width() - gap * (count - 1)) / max(1, count))
        for i, value in enumerate(bins):
            x = plot.left() + i * (bar_w + gap)
            h = max(2.0, plot.height() * (0.16 + float(value) * 0.82))
            bar = QRectF(x, plot.bottom() - h, bar_w, h)
            grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            if i < count * 0.38:
                top = QColor("#7FD79A")
            elif i < count * 0.72:
                top = QColor("#6CB9DA")
            elif i < count * 0.90:
                top = QColor("#D8B35F")
            else:
                top = QColor("#D9806D")
            top.setAlpha(212)
            mid = QColor(top)
            mid.setAlpha(106)
            grad.setColorAt(0.0, top)
            grad.setColorAt(0.55, mid)
            grad.setColorAt(1.0, QColor(38, 43, 49, 230))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(bar, 1.6, 1.6)

        safe_level = max(0.0, min(1.0, float(level) * 3.0))
        p.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        p.drawRoundedRect(meter, 3.0, 3.0)
        p.setPen(QPen(QColor(216, 179, 95, 68), 0.75))
        p.drawLine(QPointF(meter.left() + 2.0, meter.top() + meter.height() * 0.42), QPointF(meter.right() - 2.0, meter.top() + meter.height() * 0.42))
        p.setPen(QPen(QColor(217, 128, 109, 76), 0.75))
        p.drawLine(QPointF(meter.left() + 2.0, meter.top() + meter.height() * 0.18), QPointF(meter.right() - 2.0, meter.top() + meter.height() * 0.18))
        fill = QRectF(meter.left() + 2.0, meter.bottom() - 2.0 - (meter.height() - 4.0) * safe_level, meter.width() - 4.0, (meter.height() - 4.0) * safe_level)
        level_grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        if safe_level >= 0.82:
            level_grad.setColorAt(0.0, QColor(217, 128, 109, 224))
            level_grad.setColorAt(0.28, QColor(216, 179, 95, 192))
        elif safe_level >= 0.58:
            level_grad.setColorAt(0.0, QColor(216, 179, 95, 214))
            level_grad.setColorAt(0.28, QColor(126, 215, 154, 172))
        else:
            level_grad.setColorAt(0.0, QColor(126, 215, 154, 214))
            level_grad.setColorAt(0.28, QColor(108, 185, 218, 128))
        level_grad.setColorAt(0.58, QColor(126, 215, 154, 128))
        level_grad.setColorAt(1.0, QColor(58, 64, 72, 220))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(level_grad)
        p.drawRoundedRect(fill, 2.0, 2.0)


class _SoundMacroJogBank(QWidget):
    """Compact legacy-style knob bank for Basic and AI Master macro state."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self._track: Any = None
        self.setObjectName("SoundMacroJogBank")
        self.setMinimumHeight(82)
        self.setMaximumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_source(self, clip: AudioClip | None, track: Any = None) -> None:
        self._clip = clip
        self._track = track
        self.update()

    def _specs(self) -> list[tuple[str, float, QColor]]:
        clip = self._clip
        track = self._track

        def _clamp(value: float) -> float:
            return max(0.0, min(1.0, float(value)))

        gain = _clamp(float(getattr(clip, "gain", 1.0) or 1.0) / 2.0) if clip is not None else 0.5
        pan = _clamp((float(getattr(track, "pan", 0.0) or 0.0) + 1.0) * 0.5) if track is not None else 0.5
        fade_in = _clamp(float(getattr(clip, "fade_in_ms", 0) or 0) / 5000.0) if clip is not None else 0.0
        fade_out = _clamp(float(getattr(clip, "fade_out_ms", 0) or 0) / 5000.0) if clip is not None else 0.0
        speed = _clamp((float(getattr(clip, "_se_speed", 1.0) or 1.0) - 0.5) / 1.5) if clip is not None else 0.33
        pitch = _clamp((float(getattr(clip, "_se_pitch", 0.0) or 0.0) + 12.0) / 24.0) if clip is not None else 0.5
        ai = {}
        if clip is not None and isinstance(getattr(clip, "effects", None), dict):
            ai = (clip.effects.get("ai_master") or {})
        return [
            ("VOL", gain, QColor(126, 215, 154, 210)),
            ("PAN", pan, QColor(108, 185, 218, 205)),
            ("FIN", fade_in, QColor(126, 215, 154, 170)),
            ("FOUT", fade_out, QColor(216, 179, 95, 188)),
            ("SPD", speed, QColor(108, 185, 218, 205)),
            ("PCH", pitch, QColor(169, 143, 215, 198)),
            ("AIR", _clamp(float(ai.get("air", 0.0) or 0.0) / 8.0), QColor(126, 215, 154, 210)),
            ("CLR", _clamp(float(ai.get("clarity", 0.0) or 0.0) / 100.0), QColor(108, 185, 218, 205)),
            ("WRM", _clamp(float(ai.get("warmth", 0.0) or 0.0) / 100.0), QColor(216, 179, 95, 195)),
            ("WID", _clamp(float(ai.get("width", 100.0) or 100.0) / 200.0), QColor(126, 215, 154, 185)),
            ("PNC", _clamp(float(ai.get("punch", 0.0) or 0.0) / 100.0), QColor(108, 185, 218, 205)),
            ("EXC", _clamp(float(ai.get("excite", 0.0) or 0.0) / 100.0), QColor(217, 128, 109, 198)),
        ]

    def _draw_knob(self, p: QPainter, rect: QRectF, label: str, value: float, accent: QColor) -> None:
        value = max(0.0, min(1.0, float(value)))
        center = rect.center()
        radius = rect.width() * 0.5
        p.setPen(QPen(QColor(178, 186, 202, 28), 0.8))
        p.setBrush(QColor(9, 11, 14, 205))
        p.drawEllipse(rect)
        for i in range(17):
            angle = math.radians(-132 + i * 264 / 16)
            inner = QPointF(center.x() + math.cos(angle) * (radius - 5.0), center.y() + math.sin(angle) * (radius - 5.0))
            outer = QPointF(center.x() + math.cos(angle) * (radius - 1.5), center.y() + math.sin(angle) * (radius - 1.5))
            color = QColor(accent)
            color.setAlpha(126 if i <= int(value * 16) else 34)
            p.setPen(QPen(color, 0.8))
            p.drawLine(inner, outer)
        knob = rect.adjusted(radius * 0.30, radius * 0.30, -radius * 0.30, -radius * 0.30)
        grad = QRadialGradient(knob.center(), knob.width() * 0.65)
        grad.setColorAt(0.0, QColor(47, 52, 60, 226))
        grad.setColorAt(0.78, QColor(19, 22, 26, 238))
        grad.setColorAt(1.0, QColor(7, 8, 10, 245))
        p.setPen(QPen(QColor(220, 225, 238, 34), 0.8))
        p.setBrush(grad)
        p.drawEllipse(knob)
        angle = math.radians(-132 + value * 264)
        pointer = QPointF(center.x() + math.cos(angle) * (radius * 0.55), center.y() + math.sin(angle) * (radius * 0.55))
        p.setPen(QPen(accent, 1.0))
        p.drawLine(center, pointer)
        font = p.font()
        font.setPixelSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(218, 224, 234, 128))
        p.drawText(rect.adjusted(-4.0, rect.height() + 1.0, 4.0, 11.0), Qt.AlignmentFlag.AlignCenter, label)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(root.topLeft(), root.bottomLeft())
        bg.setColorAt(0.0, QColor(24, 27, 31, 196))
        bg.setColorAt(1.0, QColor(10, 12, 15, 224))
        p.setPen(QPen(QColor(178, 186, 202, 24), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(root, 5.5, 5.5)

        title_font = p.font()
        title_font.setPixelSize(8)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#A7AFBA"))
        p.drawText(root.adjusted(8, 3, -8, -root.height() + 14), Qt.AlignmentFlag.AlignLeft, "macro jog bank")

        specs = self._specs()
        cols = 6 if root.width() >= 220 else 4
        size = max(18.0, min(22.0, (root.width() - 18.0 - (cols - 1) * 5.0) / cols))
        left = root.left() + 8.0
        top = root.top() + 18.0
        gap_x = max(5.0, (root.width() - 16.0 - cols * size) / max(1, cols - 1))
        gap_y = 14.0
        for index, (label, value, accent) in enumerate(specs):
            row = index // cols
            col = index % cols
            x = left + col * (size + gap_x)
            y = top + row * (size + gap_y)
            self._draw_knob(p, QRectF(x, y, size, size), label, value, accent)
        p.end()


class _SoundMixerMeter(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._l = 0.0
        self._r = 0.0
        self._peak = 0.0
        self._clipped = False
        self.setFixedSize(18, 84)

    def set_levels(self, left: float, right: float, *, peak: float | None = None, clipped: bool = False) -> None:
        self._l = max(0.0, min(1.0, float(left or 0.0)))
        self._r = max(0.0, min(1.0, float(right or 0.0)))
        self._peak = max(self._l, self._r) if peak is None else max(0.0, min(1.0, float(peak or 0.0)))
        self._clipped = bool(clipped)
        self.update()

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(2, 3, -2, -3)
        bar_w = max(3, int((r.width() - 2) / 2))
        clip_led = QRectF(r.left(), r.top(), r.width(), 3.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(164, 99, 94, 230) if self._clipped else QColor(164, 99, 94, 42))
        p.drawRoundedRect(clip_led, 1.5, 1.5)
        meter_r = r.adjusted(0, 5, 0, 0)
        for index, level in enumerate((self._l, self._r)):
            x = meter_r.left() + index * (bar_w + 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 13))
            p.drawRoundedRect(QRectF(x, meter_r.top(), bar_w, meter_r.height()), 1.8, 1.8)
            fill_h = meter_r.height() * level
            fill = QRectF(x, meter_r.bottom() - fill_h, bar_w, fill_h)
            grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
            grad.setColorAt(0.0, QColor(164, 99, 94, 210))
            grad.setColorAt(0.42, QColor(164, 150, 105, 205))
            grad.setColorAt(1.0, QColor(118, 145, 123, 220))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill, 1.8, 1.8)
        if self._peak > 0:
            y = meter_r.bottom() - meter_r.height() * self._peak
            p.setPen(QPen(QColor(226, 219, 178, 150), 0.8))
            p.drawLine(QPointF(meter_r.left() - 0.5, y), QPointF(meter_r.right() + 0.5, y))
        p.end()


class _SoundMixerPanSlider(QSlider):
    """Compact pan rail for mixer strips, drawn in the renewed audio theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setObjectName("SoundMixerPanSlider")
        self.setRange(-100, 100)
        self.setFixedSize(66, 22)
        self.setMouseTracking(True)

    def _ratio(self) -> float:
        span = max(1, self.maximum() - self.minimum())
        return max(0.0, min(1.0, (self.value() - self.minimum()) / span))

    def _set_from_x(self, x: float) -> None:
        rail = self.rect().adjusted(8, 0, -8, 0)
        left = float(rail.left())
        width = max(1.0, float(rail.width()))
        ratio = max(0.0, min(1.0, (float(x) - left) / width))
        value = self.minimum() + ratio * (self.maximum() - self.minimum())
        self.setValue(int(round(value)))

    def mousePressEvent(self, event) -> None:  # pragma: no cover - UI interaction
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(True)
            self._set_from_x(event.position().x())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - UI interaction
        if self.isSliderDown():
            self._set_from_x(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - UI interaction
        self.setSliderDown(False)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(6.5, 2.0, -6.5, -2.0)
        cy = root.center().y()
        rail_left = root.left()
        rail_right = root.right()
        rail_w = max(1.0, rail_right - rail_left)
        center_x = rail_left + rail_w * 0.5
        handle_x = rail_left + rail_w * self._ratio()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 126))
        p.drawRoundedRect(QRectF(rail_left - 1.0, cy - 3.2, rail_w + 2.0, 6.4), 3.2, 3.2)
        slot_grad = QLinearGradient(rail_left, cy - 2.0, rail_left, cy + 2.0)
        slot_grad.setColorAt(0.0, QColor(255, 255, 255, 22))
        slot_grad.setColorAt(0.48, QColor(18, 21, 24, 185))
        slot_grad.setColorAt(1.0, QColor(255, 255, 255, 8))
        p.setBrush(QBrush(slot_grad))
        p.drawRoundedRect(QRectF(rail_left, cy - 2.0, rail_w, 4.0), 2.0, 2.0)

        fill_left = min(center_x, handle_x)
        fill_w = abs(handle_x - center_x)
        if fill_w >= 1.0:
            fill = QRectF(fill_left, cy - 1.25, fill_w, 2.5)
            grad = QLinearGradient(fill.left(), cy, fill.right(), cy)
            if handle_x < center_x:
                grad.setColorAt(0.0, QColor(83, 110, 102, 185))
                grad.setColorAt(1.0, QColor(155, 164, 171, 128))
            else:
                grad.setColorAt(0.0, QColor(155, 164, 171, 128))
                grad.setColorAt(1.0, QColor(138, 146, 114, 185))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill, 1.25, 1.25)

        p.setPen(QPen(QColor(218, 225, 232, 62), 0.75))
        p.drawLine(QPointF(center_x, cy - 4.8), QPointF(center_x, cy + 4.8))

        handle = QRectF(handle_x - 4.6, cy - 6.0, 9.2, 12.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(handle.translated(0, 1.2).adjusted(-1.0, 0, 1.0, 0.8), 3.8, 3.8)
        hgrad = QLinearGradient(handle.topLeft(), handle.bottomLeft())
        hgrad.setColorAt(0.0, QColor(213, 219, 224, 232))
        hgrad.setColorAt(0.18, QColor(159, 168, 175, 236))
        hgrad.setColorAt(0.58, QColor(98, 108, 116, 242))
        hgrad.setColorAt(1.0, QColor(55, 62, 69, 238))
        p.setBrush(QBrush(hgrad))
        p.setPen(QPen(QColor(224, 230, 236, 116), 0.75))
        p.drawRoundedRect(handle, 3.8, 3.8)
        p.setPen(QPen(QColor(255, 255, 255, 56), 0.65))
        p.drawLine(QPointF(handle.left() + 2.2, handle.top() + 2.0), QPointF(handle.right() - 2.2, handle.top() + 2.0))
        p.setPen(QPen(QColor(13, 16, 19, 74), 0.7))
        p.drawLine(QPointF(handle.center().x(), handle.top() + 3.0), QPointF(handle.center().x(), handle.bottom() - 3.0))
        p.end()


class _SoundMixerFader(QSlider):
    """Vertical mixer fader with a quiet metal cap and recessed rail."""

    def __init__(self, parent: QWidget | None = None, *, master: bool = False) -> None:
        super().__init__(Qt.Orientation.Vertical, parent)
        self._master = bool(master)
        self.setObjectName("SoundMixerFader")
        self.setRange(0, 150)
        self.setFixedSize(32, 94)
        self.setMouseTracking(True)

    def _rail_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(0.0, 13.0, 0.0, -13.0)

    def _ratio(self) -> float:
        span = max(1, self.maximum() - self.minimum())
        return max(0.0, min(1.0, (self.value() - self.minimum()) / span))

    def _set_from_y(self, y: float) -> None:
        rail = self._rail_rect()
        top = float(rail.top())
        height = max(1.0, float(rail.height()))
        ratio = max(0.0, min(1.0, (float(rail.bottom()) - float(y)) / height))
        value = self.minimum() + ratio * (self.maximum() - self.minimum())
        self.setValue(int(round(value)))

    def mousePressEvent(self, event) -> None:  # pragma: no cover - UI interaction
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setSliderDown(True)
            self._set_from_y(event.position().y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - UI interaction
        if self.isSliderDown() and self.isEnabled():
            self._set_from_y(event.position().y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - UI interaction
        self.setSliderDown(False)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(0.0, 5.0, 0.0, -5.0)
        cx = root.center().x()
        rail = self._rail_rect()
        rail_top = rail.top()
        rail_bottom = rail.bottom()
        rail_h = max(1.0, rail_bottom - rail_top)
        handle_y = rail_bottom - rail_h * self._ratio()

        panel = QRectF(cx - 9.0, root.top(), 18.0, root.height())
        p.setPen(Qt.PenStyle.NoPen)
        panel_grad = QLinearGradient(panel.topLeft(), panel.topRight())
        panel_grad.setColorAt(0.0, QColor(255, 255, 255, 6))
        panel_grad.setColorAt(0.35, QColor(0, 0, 0, 92))
        panel_grad.setColorAt(0.66, QColor(0, 0, 0, 118))
        panel_grad.setColorAt(1.0, QColor(255, 255, 255, 8))
        p.setBrush(QBrush(panel_grad))
        p.drawRoundedRect(panel, 4.0, 4.0)

        slot = QRectF(cx - 3.9, root.top() + 2.0, 7.8, root.height() - 4.0)
        p.setBrush(QColor(0, 0, 0, 156))
        p.drawRoundedRect(slot.adjusted(-1.0, 0.0, 1.0, 0.0), 3.6, 3.6)
        slot_grad = QLinearGradient(slot.topLeft(), slot.topRight())
        slot_grad.setColorAt(0.0, QColor(255, 255, 255, 16))
        slot_grad.setColorAt(0.38, QColor(12, 14, 16, 205))
        slot_grad.setColorAt(1.0, QColor(255, 255, 255, 8))
        p.setBrush(QBrush(slot_grad))
        p.drawRoundedRect(slot, 3.2, 3.2)

        for i in range(7):
            y = rail_top + rail_h * i / 6.0
            p.setPen(QPen(QColor(188, 198, 206, 22), 0.65))
            p.drawLine(QPointF(cx - 13.0, y), QPointF(cx - 10.4, y))
            p.drawLine(QPointF(cx + 10.4, y), QPointF(cx + 13.0, y))

        fill = QRectF(cx - 2.3, handle_y, 4.6, max(1.0, rail_bottom - handle_y + 9.0))
        if fill.height() > 1.0:
            grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
            if self._master:
                grad.setColorAt(0.0, QColor(144, 151, 118, 150))
                grad.setColorAt(1.0, QColor(96, 128, 112, 198))
            else:
                grad.setColorAt(0.0, QColor(133, 148, 158, 158))
                grad.setColorAt(1.0, QColor(92, 123, 112, 196))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(fill, 2.3, 2.3)

        handle = QRectF(cx - 12.0, handle_y - 7.0, 24.0, 14.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 168))
        p.drawRoundedRect(handle.translated(0, 1.7).adjusted(-1.0, 0, 1.0, 0.8), 4.0, 4.0)
        hgrad = QLinearGradient(handle.topLeft(), handle.bottomLeft())
        hgrad.setColorAt(0.0, QColor(220, 225, 229, 232))
        hgrad.setColorAt(0.16, QColor(171, 180, 187, 238))
        hgrad.setColorAt(0.48, QColor(112, 123, 132, 244))
        hgrad.setColorAt(1.0, QColor(60, 68, 77, 240))
        if not self.isEnabled():
            hgrad.setColorAt(0.0, QColor(176, 184, 190, 176))
            hgrad.setColorAt(0.48, QColor(108, 118, 126, 184))
            hgrad.setColorAt(1.0, QColor(68, 75, 82, 178))
        p.setBrush(QBrush(hgrad))
        p.setPen(QPen(QColor(232, 237, 242, 112), 0.8))
        p.drawRoundedRect(handle, 3.8, 3.8)
        p.setPen(QPen(QColor(255, 255, 255, 60), 0.7))
        p.drawLine(QPointF(handle.left() + 4.0, handle.top() + 2.2), QPointF(handle.right() - 4.0, handle.top() + 2.2))
        p.setPen(QPen(QColor(13, 16, 19, 82), 0.8))
        p.drawLine(QPointF(handle.left() + 4.0, handle.center().y()), QPointF(handle.right() - 4.0, handle.center().y()))
        led = QRectF(handle.right() - 5.4, handle.top() + 4.0, 2.2, 6.0)
        led_color = QColor(111, 151, 127, 145 if self.isEnabled() else 72)
        if self._master:
            led_color = QColor(151, 143, 104, 130 if self.isEnabled() else 64)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(led_color)
        p.drawRoundedRect(led, 1.1, 1.1)
        p.end()


class _SoundMixerStrip(QWidget):
    volume_changed = Signal(int, float)
    pan_changed = Signal(int, float)
    mute_changed = Signal(int, bool)
    solo_changed = Signal(int, bool)
    meta_changed = Signal(int, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._track: Any = None
        self._track_id = -1
        self._suppress = False
        self.setObjectName("SoundMixerStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(82)
        self.setFixedHeight(286)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        title_row = QWidget(self)
        title_row.setStyleSheet("background: transparent;")
        title_layout = QHBoxLayout(title_row)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(3)
        self._title = QLabel("A1", title_row)
        self._title.setObjectName("SoundMixerTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setFixedHeight(16)
        title_layout.addWidget(self._title, 1)
        self._type = QPushButton("DIA", title_row)
        self._type.setObjectName("SoundMixerType")
        self._type.setFixedSize(28, 16)
        self._type.clicked.connect(self._on_type_clicked)
        title_layout.addWidget(self._type, 0)
        root.addWidget(title_row)

        self._pan = _SoundMixerPanSlider(self)
        self._pan.valueChanged.connect(self._on_pan_changed)
        root.addWidget(self._pan, alignment=Qt.AlignmentFlag.AlignCenter)

        inserts = QWidget(self)
        inserts.setStyleSheet("background: transparent;")
        inserts_layout = QHBoxLayout(inserts)
        inserts_layout.setContentsMargins(0, 0, 0, 0)
        inserts_layout.setSpacing(2)
        self._insert_buttons: dict[str, QPushButton] = {}
        for slot_id, label in (("eq", "EQ"), ("dyn", "DY"), ("fx", "FX")):
            button = QPushButton(label, inserts)
            button.setObjectName("SoundMixerInsert")
            button.setCheckable(True)
            button.setFixedSize(22, 15)
            button.toggled.connect(lambda checked, sid=slot_id: self._on_insert_toggled(sid, checked))
            self._insert_buttons[slot_id] = button
            inserts_layout.addWidget(button)
        root.addWidget(inserts)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)
        self._meter = _SoundMixerMeter(body)
        body_layout.addWidget(self._meter)
        self._fader = _SoundMixerFader(body)
        self._fader.valueChanged.connect(self._on_volume_changed)
        body_layout.addWidget(self._fader)
        root.addWidget(body)

        self._value = QLabel("1.00", self)
        self._value.setObjectName("SoundMixerValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setFixedHeight(12)
        root.addWidget(self._value)

        buttons = QWidget(self)
        buttons.setStyleSheet("background: transparent;")
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(2)
        self._mute = QPushButton("M", buttons)
        self._mute.setObjectName("SoundMixerToggle")
        self._mute.setProperty("kind", "mute")
        self._mute.setCheckable(True)
        self._mute.setFixedSize(16, 17)
        self._mute.toggled.connect(self._on_mute_changed)
        buttons_layout.addWidget(self._mute)
        self._solo = QPushButton("S", buttons)
        self._solo.setObjectName("SoundMixerToggle")
        self._solo.setProperty("kind", "solo")
        self._solo.setCheckable(True)
        self._solo.setFixedSize(16, 17)
        self._solo.toggled.connect(self._on_solo_changed)
        buttons_layout.addWidget(self._solo)
        self._auto_read = QPushButton("R", buttons)
        self._auto_read.setObjectName("SoundMixerToggle")
        self._auto_read.setProperty("kind", "read")
        self._auto_read.setCheckable(True)
        self._auto_read.setFixedSize(16, 17)
        self._auto_read.toggled.connect(self._on_automation_changed)
        buttons_layout.addWidget(self._auto_read)
        self._auto_write = QPushButton("W", buttons)
        self._auto_write.setObjectName("SoundMixerToggle")
        self._auto_write.setProperty("kind", "write")
        self._auto_write.setCheckable(True)
        self._auto_write.setFixedSize(16, 17)
        self._auto_write.toggled.connect(self._on_automation_changed)
        buttons_layout.addWidget(self._auto_write)
        root.addWidget(buttons)

        sends = QWidget(self)
        sends.setStyleSheet("background: transparent;")
        sends_layout = QHBoxLayout(sends)
        sends_layout.setContentsMargins(0, 0, 0, 0)
        sends_layout.setSpacing(3)
        self._send_buttons: dict[str, QPushButton] = {}
        for send_id, label in (("reverb", "RV"), ("delay", "DL")):
            button = QPushButton(f"{label} 0", sends)
            button.setObjectName("SoundMixerSend")
            button.setFixedSize(33, 16)
            button.clicked.connect(lambda _checked=False, sid=send_id: self._on_send_clicked(sid))
            self._send_buttons[send_id] = button
            sends_layout.addWidget(button)
        root.addWidget(sends)

        self._name = QLabel("", self)
        self._name.setObjectName("SoundMixerName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setFixedHeight(14)
        root.addWidget(self._name)

    @property
    def track_id(self) -> int:
        return self._track_id

    def set_track(self, track: Any, index: int, *, active: bool = False, solo_active: bool = False) -> None:
        self._track = track
        self._track_id = int(getattr(track, "id", index + 1))
        name = str(getattr(track, "display_name", "") or getattr(track, "label", "") or f"Audio {index + 1}")
        self._title.setText(f"A{index + 1}")
        self._title.setToolTip(name)
        bus = str(getattr(track, "bus_id", "master") or "master")
        track_type = _mixer_track_type(track)
        self._name.setText(_compact_mixer_label(name, 9))
        self._name.setToolTip(f"{name} / {track_type} / {bus}")
        self.setProperty("active", bool(active))
        self.style().unpolish(self)
        self.style().polish(self)
        self._suppress = True
        try:
            volume = max(0.0, min(1.5, float(getattr(track, "volume", 1.0) or 0.0)))
            pan = max(-1.0, min(1.0, float(getattr(track, "pan", 0.0) or 0.0)))
            self._fader.setValue(int(round(volume * 100)))
            self._pan.setValue(int(round(pan * 100)))
            self._mute.setChecked(bool(getattr(track, "muted", False)))
            self._solo.setChecked(bool(getattr(track, "solo", False)))
            self._auto_read.setChecked(bool(getattr(track, "automation_read", True)))
            self._auto_write.setChecked(bool(getattr(track, "automation_write", False)))
            self._type.setText(_mixer_type_code(track_type))
            self._type.setToolTip(f"Track type: {track_type}")
            for row in _mixer_insert_slots(track):
                slot_id = str(row.get("id") or "")
                button = self._insert_buttons.get(slot_id)
                if button is None:
                    continue
                button.setChecked(bool(row.get("enabled")) and not bool(row.get("bypassed")))
                button.setToolTip(f"Insert {str(row.get('label') or slot_id).upper()}")
            sends = _mixer_sends(track)
            for send_id, button in self._send_buttons.items():
                value = sends.get(send_id, 0.0)
                prefix = "RV" if send_id == "reverb" else "DL"
                button.setText(f"{prefix} {int(round(value * 9))}")
                button.setToolTip(f"{send_id.title()} send {value:.2f}")
            self._value.setText(f"{volume:.2f}")
            audible = not bool(getattr(track, "muted", False)) and (
                not solo_active or bool(getattr(track, "solo", False))
            )
            level = 0.0 if not audible else min(0.96, max(0.06, volume * 0.54))
            level_l = level * (1.0 - max(0.0, pan) * 0.35)
            level_r = level * (1.0 + min(0.0, pan) * 0.35)
            peak = min(1.0, max(level_l, level_r) + (0.13 if volume > 0.82 else 0.06))
            self._meter.set_levels(level_l, level_r, peak=peak, clipped=volume >= 1.18 and audible)
        finally:
            self._suppress = False

    def _on_volume_changed(self, value: int) -> None:
        volume = value / 100.0
        self._value.setText(f"{volume:.2f}")
        if not self._suppress:
            self.volume_changed.emit(self._track_id, volume)

    def _on_pan_changed(self, value: int) -> None:
        if not self._suppress:
            self.pan_changed.emit(self._track_id, value / 100.0)

    def _on_mute_changed(self, muted: bool) -> None:
        if not self._suppress:
            self.mute_changed.emit(self._track_id, bool(muted))

    def _on_solo_changed(self, solo: bool) -> None:
        if not self._suppress:
            self.solo_changed.emit(self._track_id, bool(solo))

    def _on_insert_toggled(self, slot_id: str, checked: bool) -> None:
        if not self._suppress:
            self.meta_changed.emit(self._track_id, {"kind": "insert", "slot": slot_id, "enabled": bool(checked), "bypassed": False})

    def _on_send_clicked(self, send_id: str) -> None:
        if self._suppress or self._track is None:
            return
        sends = _mixer_sends(self._track)
        current = sends.get(send_id, 0.0)
        next_value = 0.0 if current >= 0.95 else min(1.0, current + 0.25)
        self.meta_changed.emit(self._track_id, {"kind": "send", "send_id": send_id, "level": next_value})

    def _on_automation_changed(self, _checked: bool) -> None:
        if not self._suppress:
            self.meta_changed.emit(
                self._track_id,
                {
                    "kind": "automation",
                    "read": self._auto_read.isChecked(),
                    "write": self._auto_write.isChecked(),
                },
            )

    def _on_type_clicked(self) -> None:
        if self._suppress or self._track is None:
            return
        self.meta_changed.emit(self._track_id, {"kind": "type", "track_type": _mixer_next_type(_mixer_track_type(self._track))})


class _SoundMixerMasterStrip(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SoundMixerMasterStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(86)
        self.setFixedHeight(286)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(3)

        title = QLabel("MASTER", self)
        title.setObjectName("SoundMixerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(14)
        root.addWidget(title)

        bus = QLabel("mix bus", self)
        bus.setObjectName("SoundMixerName")
        bus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bus.setFixedHeight(18)
        root.addWidget(bus)

        snap = QWidget(self)
        snap.setStyleSheet("background: transparent;")
        snap_layout = QHBoxLayout(snap)
        snap_layout.setContentsMargins(0, 0, 0, 0)
        snap_layout.setSpacing(3)
        self._snapshot_a = QLabel("S1", snap)
        self._snapshot_a.setObjectName("SoundMixerSnapshot")
        self._snapshot_a.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._snapshot_a.setFixedSize(29, 16)
        snap_layout.addWidget(self._snapshot_a)
        self._snapshot_b = QLabel("A/B", snap)
        self._snapshot_b.setObjectName("SoundMixerSnapshot")
        self._snapshot_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._snapshot_b.setFixedSize(32, 16)
        snap_layout.addWidget(self._snapshot_b)
        root.addWidget(snap)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(6)
        self._meter = _SoundMixerMeter(body)
        body_layout.addWidget(self._meter)
        self._fader = _SoundMixerFader(body, master=True)
        self._fader.setValue(100)
        self._fader.setEnabled(False)
        body_layout.addWidget(self._fader)
        root.addWidget(body)

        self._value = QLabel("0.00", self)
        self._value.setObjectName("SoundMixerValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setFixedHeight(12)
        root.addWidget(self._value)

        self._name = QLabel("master", self)
        self._name.setObjectName("SoundMixerName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setFixedHeight(34)
        root.addWidget(self._name)

    def set_tracks(self, tracks: list[Any] | tuple[Any, ...]) -> None:
        track_rows = list(tracks or [])
        solo_active = any(bool(getattr(track, "solo", False)) for track in track_rows)
        audible: list[Any] = [
            track for track in track_rows
            if not bool(getattr(track, "muted", False))
            and (not solo_active or bool(getattr(track, "solo", False)))
        ]
        level_l = 0.0
        level_r = 0.0
        for track in audible:
            volume = max(0.0, min(1.5, float(getattr(track, "volume", 1.0) or 0.0)))
            pan = max(-1.0, min(1.0, float(getattr(track, "pan", 0.0) or 0.0)))
            base = min(0.96, max(0.04, volume * 0.46))
            level_l += base * (1.0 - max(0.0, pan) * 0.35)
            level_r += base * (1.0 + min(0.0, pan) * 0.35)
        level_l = min(0.98, level_l)
        level_r = min(0.98, level_r)
        peak_hold = min(1.0, max(level_l, level_r) + (0.12 if audible else 0.0))
        clipped = any(max(0.0, min(1.5, float(getattr(track, "volume", 1.0) or 0.0))) >= 1.18 for track in audible)
        self._meter.set_levels(level_l, level_r, peak=peak_hold, clipped=clipped)
        peak = max(level_l, level_r)
        self._value.setText(f"{peak:.2f}")
        self._name.setText(f"{len(audible)}/{len(track_rows)} live")


class SoundEditorPanel(QWidget):
    """Compact sound editor embedded in the Workbench Audio tab."""

    BASIC_PRESETS: dict[str, dict[str, float]] = {
        "Voice Recording": {"gain": 1.41, "pan": 0.0, "fade_in_ms": 100, "fade_out_ms": 300, "speed": 1.0, "pitch": 0.0},
        "Background Music": {"gain": 0.50, "pan": 0.0, "fade_in_ms": 1500, "fade_out_ms": 2000, "speed": 1.0, "pitch": 0.0},
        "Game Audio": {"gain": 1.0, "pan": 0.0, "fade_in_ms": 0, "fade_out_ms": 200, "speed": 1.0, "pitch": 0.0},
        "Podcast": {"gain": 1.26, "pan": 0.0, "fade_in_ms": 500, "fade_out_ms": 500, "speed": 1.0, "pitch": 0.0},
    }
    EQ_PRESETS: dict[str, dict[str, float]] = {
        "Flat": {"low_g": 0.0, "mid_g": 0.0, "high_g": 0.0},
        "Vocal Boost": {"low_g": -2.0, "mid_g": 4.0, "high_g": 2.0},
        "Bass Boost": {"low_g": 6.0, "mid_g": 0.0, "high_g": 0.0},
        "Podcast": {"low_g": -3.0, "mid_g": 2.0, "high_g": 3.0},
        "Treble Cut": {"low_g": 0.0, "mid_g": 0.0, "high_g": -4.0},
    }
    DYN_PRESETS: dict[str, dict[str, float]] = {
        "Voice Gentle": {"threshold": -20.0, "ratio": 3.0, "attack_ms": 5.0, "release_ms": 120.0, "makeup_db": 2.0, "knee_db": 4.0},
        "Voice Strong": {"threshold": -24.0, "ratio": 6.0, "attack_ms": 2.0, "release_ms": 80.0, "makeup_db": 4.0, "knee_db": 2.0},
        "Podcast": {"threshold": -18.0, "ratio": 4.0, "attack_ms": 5.0, "release_ms": 150.0, "makeup_db": 3.0, "knee_db": 3.0},
    }
    FX_PRESETS: dict[str, dict[str, Any]] = {
        "Small Room": {"type": "Room", "size": 20.0, "decay_s": 0.8, "damping": 60.0, "mix": 20.0},
        "Concert Hall": {"type": "Hall", "size": 80.0, "decay_s": 3.0, "damping": 30.0, "mix": 35.0},
        "Plate": {"type": "Plate", "size": 50.0, "decay_s": 2.0, "damping": 40.0, "mix": 30.0},
        "Spring": {"type": "Spring", "size": 30.0, "decay_s": 1.5, "damping": 50.0, "mix": 25.0},
        "Slap Delay": {
            "type": "Room", "size": 15.0, "decay_s": 0.5, "damping": 50.0, "mix": 15.0,
            "_delay": {"time_ms": 150.0, "feedback": 0.0, "mix": 40.0},
        },
    }
    AI_PRESETS: dict[str, dict[str, float]] = {
        "Suno v3": {"air": 5, "clarity": 60, "warmth": 40, "width": 130, "punch": 50, "excite": 70},
        "Suno v4": {"air": 3, "clarity": 50, "warmth": 30, "width": 120, "punch": 40, "excite": 50},
        "Udio": {"air": 4, "clarity": 45, "warmth": 35, "width": 110, "punch": 55, "excite": 60},
        "ACE-Step": {"air": 6, "clarity": 55, "warmth": 50, "width": 140, "punch": 45, "excite": 75},
        "Generic AI": {"air": 4, "clarity": 50, "warmth": 40, "width": 120, "punch": 50, "excite": 60},
        "Custom": {"air": 0, "clarity": 0, "warmth": 0, "width": 100, "punch": 0, "excite": 0},
    }

    changed = Signal()
    mixer_track_changed = Signal(object)
    target_changed = Signal(str)
    # Kept for compatibility with older editor wiring. The renewed panel handles
    # Advanced Lab inline, so the Workbench path no longer emits this signal.
    advanced_lab_requested = Signal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self._track: Any = None
        self._context_key = ""
        self._exporter: ClipExporter | None = None
        self._tab_buttons: dict[str, QPushButton] = {}
        self._mixer_tracks: list[Any] = []
        self._mixer_active_track_id: int | None = None
        self._mixer_strips: dict[int, _SoundMixerStrip] = {}
        self._mixer_master_strip: _SoundMixerMasterStrip | None = None
        self._chain_labels: dict[str, QLabel] = {}
        self._ai_preset_buttons: dict[str, QPushButton] = {}
        self._ui_lock = False
        self._advanced_expanded = False
        self.setObjectName("EmbeddedSoundEditor")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(self._qss())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(5)

        header = QWidget(self)
        header.setObjectName("SoundHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(7, 5, 7, 5)
        header_layout.setSpacing(6)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(1)
        self._title = QLabel("Sound Editor", header)
        self._title.setObjectName("SoundTitle")
        self._subtitle = QLabel("Select an audio source", header)
        self._subtitle.setObjectName("SoundSubtitle")
        title_box.addWidget(self._title)
        title_box.addWidget(self._subtitle)
        header_layout.addLayout(title_box, 1)
        self._export_btn = QPushButton("", header)
        self._export_btn.setObjectName("SoundIconButton")
        self._export_btn.setIcon(app_icon("download", size=13, color="#D7DAE7"))
        self._export_btn.setIconSize(icon_size(13))
        self._export_btn.setToolTip("Export edited audio")
        self._export_btn.setFixedSize(26, 24)
        self._export_btn.clicked.connect(self._export_clip)
        header_layout.addWidget(self._export_btn)
        self._advanced_btn = QPushButton("", header)
        self._advanced_btn.setObjectName("SoundIconButton")
        self._advanced_btn.setProperty("role", "advanced_audio_lab")
        self._advanced_btn.setProperty("expanded", False)
        self._advanced_btn.setIcon(app_icon("waveform", size=13, color="#D7DAE7"))
        self._advanced_btn.setIconSize(icon_size(13))
        self._advanced_btn.setToolTip("Expand advanced audio lab")
        self._advanced_btn.setFixedSize(26, 24)
        self._advanced_btn.clicked.connect(self._toggle_advanced_lab)
        header_layout.addWidget(self._advanced_btn)
        root.addWidget(header)

        self._jog_shuttle = _SoundJogShuttle05(self)
        root.addWidget(self._jog_shuttle)

        self._waveform_strip = _MiniWaveformStrip(self)
        root.addWidget(self._waveform_strip)
        self._spectrum_strip = _MiniSpectrumStrip(self)
        root.addWidget(self._spectrum_strip)

        tabs = QWidget(self)
        tabs.setObjectName("SoundTabs")
        self._tabs_bar = tabs
        tabs_layout = QHBoxLayout(tabs)
        tabs_layout.setContentsMargins(4, 0, 4, 0)
        tabs_layout.setSpacing(3)
        for tab_id, label, icon in (
            ("basic", "Basic", "audio"),
            ("mixer", "Mixer", "mixer"),
            ("eq", "EQ", "sliders"),
            ("dyn", "Dynamics", "mixer"),
            ("fx", "FX", "effects"),
            ("ai", "AI Master", "spark"),
        ):
            button = QPushButton("", tabs)
            button.setObjectName("SoundTab")
            button.setCheckable(True)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setFixedSize(27, 23)
            button.setIcon(app_icon(icon, size=14, color="#D7DAE7"))
            button.setIconSize(icon_size(13))
            button.clicked.connect(lambda _checked=False, t=tab_id: self._set_tab(t))
            self._tab_buttons[tab_id] = button
            tabs_layout.addWidget(button)
        tabs_layout.addStretch(1)
        root.addWidget(tabs)

        chain = QWidget(self)
        chain.setObjectName("SoundChain")
        self._chain_bar = chain
        chain_layout = QHBoxLayout(chain)
        chain_layout.setContentsMargins(4, 0, 4, 0)
        chain_layout.setSpacing(4)
        for key, label in (
            ("basic", "Basic"),
            ("mixer", "Mix"),
            ("eq", "EQ"),
            ("dyn", "Dyn"),
            ("fx", "FX"),
            ("ai", "AI"),
        ):
            chip = QLabel(label, chain)
            chip.setObjectName("SoundChip")
            chip.setProperty("active", False)
            chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._chain_labels[key] = chip
            chain_layout.addWidget(chip)
        chain_layout.addStretch(1)
        root.addWidget(chain)

        self._workspace = QWidget(self)
        self._workspace.setObjectName("SoundWorkspace")
        workspace_layout = QHBoxLayout(self._workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(5)

        self._advanced_lab_panel = self._build_advanced_lab_panel()
        self._advanced_lab_host = self._scroll_page(self._advanced_lab_panel)
        self._advanced_lab_host.setObjectName("SoundAdvancedLabScroll")
        self._advanced_lab_host.hide()
        workspace_layout.addWidget(self._advanced_lab_host, 1)

        self._stack = QStackedWidget(self)
        self._stack.setObjectName("SoundStack")
        self._stack.addWidget(self._scroll_page(self._build_basic_page()))
        self._stack.addWidget(self._scroll_page(self._build_mixer_page()))
        self._stack.addWidget(self._scroll_page(self._build_eq_page()))
        self._stack.addWidget(self._scroll_page(self._build_dynamics_page()))
        self._stack.addWidget(self._scroll_page(self._build_fx_page()))
        self._stack.addWidget(self._scroll_page(self._build_ai_page()))
        workspace_layout.addWidget(self._stack, 2)
        root.addWidget(self._workspace, 1)
        self._set_tab("basic")
        self.setEnabled(False)

    def set_clip(
        self,
        clip: AudioClip | None,
        *,
        track: Any = None,
        context_label: str = "",
        context_key: str = "",
    ) -> None:
        self._clip = clip
        self._track = track
        self._context_key = context_key or ""
        self.setEnabled(clip is not None)
        if clip is None:
            self._title.setText("Sound Editor")
            self._subtitle.setText("Select an audio source")
            self._jog_shuttle.set_clip(None)
            self.set_mixer_tracks([], active_track_id=None)
            if hasattr(self, "_macro_jog_bank"):
                self._macro_jog_bank.set_source(None, None)
            self._waveform_strip.set_clip(None)
            self._spectrum_strip.set_clip(None)
            self._refresh_chain()
            self._refresh_visuals()
            return
        if not isinstance(getattr(clip, "effects", None), dict):
            clip.effects = copy.deepcopy(default_effects_state())
        else:
            defaults = default_effects_state()
            for key, value in defaults.items():
                clip.effects.setdefault(key, copy.deepcopy(value))

        src = getattr(clip, "source_path", None)
        self._title.setText(context_label or "Sound Editor")
        self._subtitle.setText(f"{_compact_path_label(src)}   {_fmt_ms(getattr(clip, 'duration_ms', 0))}")
        self._jog_shuttle.set_clip(clip)
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(clip, track)
        if track is not None:
            self.set_mixer_tracks([track], active_track_id=getattr(track, "id", None))
        self._waveform_strip.set_clip(clip)
        self._spectrum_strip.set_clip(clip)
        self._sync_from_clip()
        self._refresh_chain()
        self._refresh_visuals()
        self.target_changed.emit(self._context_key)

    def current_clip(self) -> AudioClip | None:
        return self._clip

    def refresh_waveform(self) -> None:
        self._jog_shuttle.set_clip(self._clip)
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        self._waveform_strip.refresh()
        self._spectrum_strip.refresh()

    def set_mixer_tracks(self, tracks: list[Any] | tuple[Any, ...], *, active_track_id: Any = None) -> None:
        unique: list[Any] = []
        seen: set[int] = set()
        for track in list(tracks or []):
            key = id(track)
            if key in seen:
                continue
            seen.add(key)
            unique.append(track)
        self._mixer_tracks = unique
        try:
            self._mixer_active_track_id = int(active_track_id) if active_track_id is not None else None
        except Exception:
            self._mixer_active_track_id = None
        self._refresh_mixer_tracks()
        self._refresh_chain()

    def _qss(self) -> str:
        return (
            f"QWidget#EmbeddedSoundEditor {{ background:#101112; font-family:{FONT_FAMILY}; }}"
            "QWidget#SoundHeader { background:rgba(255,255,255,4); border:1px solid rgba(178,186,202,18); border-radius:6px; }"
            "QLabel#SoundTitle { color:#ECEFF4; font-size:10px; font-weight:660; background:transparent; }"
            "QLabel#SoundSubtitle { color:#929AA6; font-size:9px; background:transparent; }"
            "QPushButton#SoundIconButton, QPushButton#SoundTab, QPushButton#SoundToggle {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24); border-radius:5px; padding:0px;"
            "}"
            "QPushButton#SoundIconButton:hover, QPushButton#SoundTab:hover, QPushButton#SoundToggle:hover {"
            "background:rgba(255,255,255,11); border-color:rgba(220,225,238,70); color:#FFFFFF;"
            "}"
            "QPushButton#SoundTab:checked, QPushButton#SoundToggle:checked {"
            "background:rgba(178,186,202,13); border-color:rgba(238,242,250,56); color:#FFFFFF;"
            "}"
            "QPushButton#SoundIconButton[expanded=\"true\"] {"
            "background:rgba(178,186,202,15); border-color:rgba(238,242,250,72); color:#FFFFFF;"
            "}"
            "QPushButton#SoundPresetButton {"
            "background:rgba(255,255,255,5); color:#C7CEDA; border:1px solid rgba(178,186,202,22);"
            "border-radius:5px; padding:4px 6px; font-size:8px; font-weight:650;"
            "}"
            "QPushButton#SoundPresetButton:hover {"
            "background:rgba(255,255,255,11); border-color:rgba(220,225,238,62); color:#FFFFFF;"
            "}"
            "QPushButton#SoundPresetButton[selected=\"true\"] {"
            "background:rgba(126,215,154,18); border-color:rgba(126,215,154,92); color:#E5F2EA;"
            "}"
            "QComboBox#SoundCombo {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:5px; padding:2px 7px; font-size:9px; min-height:18px;"
            "}"
            "QComboBox#SoundCombo:hover { background:rgba(255,255,255,11); border-color:rgba(220,225,238,62); }"
            "QWidget#SoundJogShuttle05 { background:transparent; border:none; }"
            "QPushButton#SoundJogButton {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:5px; padding:0px;"
            "}"
            "QPushButton#SoundJogButton:hover {"
            "background:rgba(255,255,255,11); border-color:rgba(220,225,238,70); color:#FFFFFF;"
            "}"
            "QPushButton#SoundToggle { font-size:8px; font-weight:620; padding:0px 8px; }"
            "QWidget#SoundTabs { background:transparent; border:none; }"
            "QWidget#SoundChain { background:transparent; border:none; }"
            "QWidget#SoundWorkspace { background:transparent; border:none; }"
            "QLabel#SoundChip {"
            "background:rgba(255,255,255,4); color:#79818D; border:1px solid rgba(178,186,202,14);"
            "border-radius:5px; padding:2px 7px; font-size:8px; font-weight:620;"
            "}"
            "QLabel#SoundChip[active=\"true\"] {"
            "background:rgba(178,186,202,10); color:#DDE2EA; border-color:rgba(220,225,238,48);"
            "}"
            "QStackedWidget#SoundStack { background:#101112; border:none; }"
            "QFrame#SoundCard { background:transparent; border:none; border-top:1px solid rgba(178,186,202,16); border-radius:0px; }"
            "QWidget#SoundMixerStrip {"
            "background:rgba(255,255,255,4); border:1px solid rgba(178,186,202,20); border-radius:6px;"
            "}"
            "QWidget#SoundMixerMasterStrip {"
            "background:rgba(118,145,123,7); border:1px solid rgba(178,186,202,24); border-radius:6px;"
            "}"
            "QWidget#SoundMixerStrip[active=\"true\"] {"
            "background:rgba(178,186,202,9); border-color:rgba(220,225,238,54);"
            "}"
            "QLabel#SoundMixerTitle { color:#DDE2EA; font-size:10px; font-weight:680; background:transparent; }"
            "QLabel#SoundMixerValue { color:#C8CED8; font-size:9px; font-family:Consolas, monospace; background:transparent; }"
            "QLabel#SoundMixerName { color:#7E8793; font-size:8px; font-weight:620; background:transparent; }"
            "QPushButton#SoundMixerToggle {"
            "background:rgba(255,255,255,5); color:#8F98A5; border:1px solid rgba(178,186,202,24);"
            "border-radius:4px; font-size:9px; font-weight:700; padding:0px;"
            "}"
            "QPushButton#SoundMixerToggle:hover { background:rgba(255,255,255,10); color:#E7EAF0; border-color:rgba(220,225,238,64); }"
            "QPushButton#SoundMixerToggle[kind=\"mute\"]:checked { background:rgba(164,99,94,30); color:#F0D6D3; border-color:rgba(164,99,94,120); }"
            "QPushButton#SoundMixerToggle[kind=\"solo\"]:checked { background:rgba(164,150,105,30); color:#F1E8C8; border-color:rgba(164,150,105,120); }"
            "QPushButton#SoundMixerToggle[kind=\"read\"]:checked { background:rgba(110,132,145,28); color:#D9E2E8; border-color:rgba(132,158,174,95); }"
            "QPushButton#SoundMixerToggle[kind=\"write\"]:checked { background:rgba(164,99,94,34); color:#F1D6D2; border-color:rgba(164,99,94,118); }"
            "QPushButton#SoundMixerType {"
            "background:rgba(118,145,123,18); color:#C8D4CB; border:1px solid rgba(118,145,123,70);"
            "border-radius:4px; font-size:8px; font-weight:800; padding:0px;"
            "}"
            "QPushButton#SoundMixerType:hover { background:rgba(118,145,123,28); color:#EEF4EF; }"
            "QPushButton#SoundMixerInsert {"
            "background:rgba(255,255,255,4); color:#69727D; border:1px solid rgba(178,186,202,20);"
            "border-radius:3px; font-size:8px; font-weight:760; padding:0px;"
            "}"
            "QPushButton#SoundMixerInsert:checked {"
            "background:rgba(143,158,169,24); color:#DDE3E8; border-color:rgba(172,184,194,92);"
            "}"
            "QPushButton#SoundMixerInsert:hover, QPushButton#SoundMixerSend:hover {"
            "background:rgba(255,255,255,10); color:#E5EAF0; border-color:rgba(220,225,238,58);"
            "}"
            "QPushButton#SoundMixerSend {"
            "background:rgba(255,255,255,4); color:#85909B; border:1px solid rgba(178,186,202,20);"
            "border-radius:4px; font-size:8px; font-weight:700; padding:0px;"
            "}"
            "QLabel#SoundMixerSnapshot {"
            "background:rgba(255,255,255,4); color:#7D8792; border:1px solid rgba(178,186,202,18);"
            "border-radius:4px; font-size:8px; font-weight:740;"
            "}"
            "QFrame#SoundAdvancedLab {"
            "background:rgba(255,255,255,4); border:1px solid rgba(178,186,202,22); border-radius:6px;"
            "}"
            "QFrame#SoundPresetPanel { background:transparent; border:none; }"
            "QLabel#SoundAdvancedTitle { color:#ECEFF4; font-size:10px; font-weight:680; background:transparent; }"
            "QLabel#SoundCardTitle { color:#DDE2EA; font-size:9px; font-weight:650; background:transparent; }"
            "QLabel#SoundFieldLabel { color:#A3ABB7; font-size:9px; font-weight:560; background:transparent; }"
            "QLabel#SoundFieldValue { color:#DDE2EA; font-size:9px; background:transparent; }"
            "QScrollArea#SoundScroll, QScrollArea#SoundAdvancedLabScroll, QScrollArea#SoundMixerScroll { background:transparent; border:none; }"
            "QScrollArea#SoundScroll > QWidget > QWidget { background:transparent; }"
            "QScrollArea#SoundAdvancedLabScroll > QWidget > QWidget { background:transparent; }"
            "QScrollArea#SoundMixerScroll > QWidget > QWidget { background:transparent; }"
            + editor_scrollbar_qss("QWidget#EmbeddedSoundEditor")
        )

    def _scroll_page(self, page: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setObjectName("SoundScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def _card(self, title: str, *actions: QWidget) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(self)
        card.setObjectName("SoundCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(6)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        label = QLabel(title, card)
        label.setObjectName("SoundCardTitle")
        header.addWidget(label, 0)
        for action in actions:
            header.addWidget(action, 0)
        header.addStretch(1)
        layout.addLayout(header)
        return card, layout

    def _toggle(
        self,
        text: str,
        handler,
        *,
        icon_name: str | None = None,
        compact: bool = False,
    ) -> QPushButton:
        btn = QPushButton(text, self)
        btn.setObjectName("SoundToggle")
        btn.setCheckable(True)
        if icon_name:
            btn.setIcon(app_icon(icon_name, size=13, color="#D7DAE7"))
            btn.setIconSize(icon_size(12))
        if compact:
            btn.setText("")
            btn.setFixedSize(27, 24)
            btn.setToolTip(text)
            btn.setAccessibleName(text)
        else:
            btn.setMinimumHeight(22)
            btn.setMaximumHeight(22)
            btn.setMaximumWidth(max(76, min(126, 11 + len(text) * 7)))
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(handler)
        return btn

    def _preset_row(self, names, callback) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        label = QLabel("Presets", row)
        label.setObjectName("SoundFieldLabel")
        label.setFixedWidth(44)
        layout.addWidget(label, 0)
        for name in names:
            button = QPushButton(str(name), row)
            button.setObjectName("SoundPresetButton")
            button.setMinimumHeight(22)
            button.setMaximumHeight(22)
            button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda _checked=False, n=name: callback(n))
            layout.addWidget(button, 0)
        layout.addStretch(1)
        return row

    def _combo(self, values: list[str], handler) -> QComboBox:
        combo = QComboBox(self)
        combo.setObjectName("SoundCombo")
        combo.addItems(values)
        combo.currentTextChanged.connect(handler)
        return combo

    @staticmethod
    def _set_combo_text(combo: QComboBox | None, value: Any) -> None:
        if combo is None:
            return
        text = str(value or "")
        combo.blockSignals(True)
        idx = combo.findText(text)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _build_advanced_lab_panel(self) -> QWidget:
        panel = QFrame(self)
        panel.setObjectName("SoundAdvancedLab")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(7, 6, 7, 7)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        title = QLabel("Advanced Lab", panel)
        title.setObjectName("SoundAdvancedTitle")
        header.addWidget(title, 1)
        self._advanced_close_btn = QPushButton("", panel)
        self._advanced_close_btn.setObjectName("SoundIconButton")
        self._advanced_close_btn.setIcon(app_icon("x", size=12, color="#D7DAE7"))
        self._advanced_close_btn.setIconSize(icon_size(12))
        self._advanced_close_btn.setToolTip("Collapse advanced audio lab")
        self._advanced_close_btn.setFixedSize(23, 21)
        self._advanced_close_btn.clicked.connect(lambda: self._set_advanced_lab_expanded(False))
        header.addWidget(self._advanced_close_btn, 0)
        layout.addLayout(header)

        layout.addWidget(self._build_ai_preset_panel())
        self._macro_jog_bank = _SoundMacroJogBank(self)
        layout.addWidget(self._macro_jog_bank)

        self._dialogue_enabled = self._toggle(
            "Dialogue cleanup",
            lambda on: self._set_fx("dialogue_cleanup", "enabled", bool(on)),
            icon_name="spark",
            compact=True,
        )
        card, card_layout = self._card("Dialogue cleanup", self._dialogue_enabled)
        self._dialogue_strength = _ValueSlider("Strength", 0, 100, 0, suffix="%")
        self._noise_reduction = _ValueSlider("Noise Reduction", 0, 300, 0, scale=10.0, suffix=" dB")
        self._de_reverb = _ValueSlider("De-reverb", 0, 100, 0, suffix="%")
        self._presence = _ValueSlider("Presence", -60, 60, 0, scale=10.0, suffix=" dB")
        self._dialogue_strength.value_changed.connect(lambda v: self._set_fx("dialogue_cleanup", "strength", max(0.0, min(1.0, v / 100.0))))
        self._noise_reduction.value_changed.connect(lambda v: self._set_fx("dialogue_cleanup", "noise_reduction", v))
        self._de_reverb.value_changed.connect(lambda v: self._set_fx("dialogue_cleanup", "de_reverb", max(0.0, min(1.0, v / 100.0))))
        self._presence.value_changed.connect(lambda v: self._set_fx("dialogue_cleanup", "presence_db", v))
        for widget in (self._dialogue_strength, self._noise_reduction, self._de_reverb, self._presence):
            card_layout.addWidget(widget)
        layout.addWidget(card)

        self._lab_deesser_enabled = self._toggle(
            "De-esser",
            lambda on: self._set_fx("deesser", "enabled", bool(on)),
            icon_name="waveform",
            compact=True,
        )
        self._time_enabled = self._toggle(
            "Time stretch",
            lambda on: self._set_fx("time_stretch", "enabled", bool(on)),
            icon_name="loop",
            compact=True,
        )
        card, card_layout = self._card("Sibilance / timing", self._lab_deesser_enabled, self._time_enabled)
        self._lab_deesser_freq = _ValueSlider("De-ess Freq", 2000, 12000, 6000, suffix=" Hz")
        self._lab_deesser_threshold = _ValueSlider("Threshold", -600, 0, -300, scale=10.0, suffix=" dB")
        self._lab_deesser_reduction = _ValueSlider("Reduction", 0, 100, 40, suffix="%")
        self._time_ratio = _ValueSlider("Stretch Ratio", 50, 200, 100, scale=100.0, suffix="x")
        self._time_algorithm = self._combo(
            ["atempo", "rubberband"],
            lambda text: self._set_fx("time_stretch", "algorithm", str(text)),
        )
        self._lab_deesser_freq.value_changed.connect(lambda v: self._set_fx("deesser", "freq", v))
        self._lab_deesser_threshold.value_changed.connect(lambda v: self._set_fx("deesser", "threshold", v))
        self._lab_deesser_reduction.value_changed.connect(lambda v: self._set_fx("deesser", "reduction", v))
        self._time_ratio.value_changed.connect(lambda v: self._set_fx("time_stretch", "ratio", v))
        for widget in (self._lab_deesser_freq, self._lab_deesser_threshold, self._lab_deesser_reduction, self._time_ratio):
            card_layout.addWidget(widget)
        algo_row = QHBoxLayout()
        algo_row.setContentsMargins(0, 0, 0, 0)
        algo_row.setSpacing(5)
        algo_label = QLabel("Algorithm", panel)
        algo_label.setObjectName("SoundFieldLabel")
        algo_row.addWidget(algo_label, 1)
        algo_row.addWidget(self._time_algorithm, 0)
        card_layout.addLayout(algo_row)
        layout.addWidget(card)

        self._loudness_enabled = self._toggle(
            "Loudness",
            lambda on: self._set_fx("loudness", "enabled", bool(on)),
            icon_name="sliders",
            compact=True,
        )
        card, card_layout = self._card("Delivery loudness", self._loudness_enabled)
        self._target_lufs = _ValueSlider("Target", -360, -50, -140, scale=10.0, suffix=" LUFS")
        self._true_peak = _ValueSlider("True Peak", -90, 0, -10, scale=10.0, suffix=" dBTP")
        self._lra = _ValueSlider("LRA", 10, 200, 110, scale=10.0, suffix=" LU")
        self._target_lufs.value_changed.connect(lambda v: self._set_fx("loudness", "target_i", v))
        self._true_peak.value_changed.connect(lambda v: self._set_fx("loudness", "true_peak", v))
        self._lra.value_changed.connect(lambda v: self._set_fx("loudness", "lra", v))
        for widget in (self._target_lufs, self._true_peak, self._lra):
            card_layout.addWidget(widget)
        layout.addWidget(card)
        return panel

    def _build_ai_preset_panel(self) -> QWidget:
        card = QFrame(self)
        card.setObjectName("SoundPresetPanel")
        card.setMinimumHeight(24)
        card.setMaximumHeight(26)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(3)
        title = QLabel("AI", card)
        title.setObjectName("SoundCardTitle")
        title.setFixedWidth(16)
        title.setFixedHeight(22)
        card_layout.addWidget(title, 0)
        short_labels = {
            "Suno v3": "S3",
            "Suno v4": "S4",
            "Udio": "Udi",
            "ACE-Step": "ACE",
            "Generic AI": "Gen",
            "Custom": "Cus",
        }
        for index, name in enumerate(self.AI_PRESETS):
            button = QPushButton(name, self)
            button.setObjectName("SoundPresetButton")
            button.setProperty("selected", False)
            button.setToolTip(f"Apply AI Master preset: {name}")
            button.setText(short_labels.get(name, name))
            button.setFixedSize(31, 22)
            button.clicked.connect(lambda _checked=False, n=name: self._apply_ai_preset(n))
            button.setAccessibleName(f"AI preset {name}")
            button.setProperty("preset", name)
            button.setObjectName("SoundPresetButton")
            self._ai_preset_buttons[name] = button
            card_layout.addWidget(button, 1)
        card_layout.addStretch(1)
        return card

    def _apply_ai_preset(self, name: str) -> None:
        if self._ui_lock or self._clip is None:
            return
        preset = self.AI_PRESETS.get(str(name))
        if preset is None:
            return
        state = self._clip.effects.setdefault("ai_master", copy.deepcopy(default_effects_state().get("ai_master", {})))
        for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
            if key in preset:
                state[key] = float(preset[key])
        state["preset"] = str(name)
        if name != "Custom":
            state["enabled"] = True
        self._set_tab("ai")
        self._sync_from_clip()
        self._refresh_chain()
        self._refresh_visuals()
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        self.changed.emit()

    def _refresh_ai_preset_buttons(self) -> None:
        clip = self._clip
        preset = ""
        if clip is not None and isinstance(getattr(clip, "effects", None), dict):
            preset = str((clip.effects.get("ai_master") or {}).get("preset") or "")
        for name, button in self._ai_preset_buttons.items():
            button.setProperty("selected", preset == name)
            button.style().unpolish(button)
            button.style().polish(button)

    def _build_basic_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        card, card_layout = self._card("Clip tone")
        card_layout.setSpacing(4)
        self._gain = _ValueSlider("Gain", 0, 200, 100, scale=100.0, suffix="x")
        self._gain.value_changed.connect(lambda v: self._set_attr("gain", max(0.0, v)))
        self._pan = _ValueSlider("Pan", -100, 100, 0, suffix="%")
        self._pan.value_changed.connect(lambda v: self._set_pan(max(-1.0, min(1.0, v / 100.0))))
        self._fade_in = _ValueSlider("Fade In", 0, 5000, 0, suffix=" ms")
        self._fade_in.value_changed.connect(lambda v: self._set_attr("fade_in_ms", int(v)))
        self._fade_out = _ValueSlider("Fade Out", 0, 5000, 0, suffix=" ms")
        self._fade_out.value_changed.connect(lambda v: self._set_attr("fade_out_ms", int(v)))
        self._speed = _ValueSlider("Speed", 50, 200, 100, scale=100.0, suffix="x")
        self._speed.value_changed.connect(lambda v: self._set_private("_se_speed", max(0.1, v)))
        self._pitch = _ValueSlider("Pitch", -120, 120, 0, scale=10.0, suffix=" st")
        self._pitch.value_changed.connect(lambda v: self._set_private("_se_pitch", v))
        for widget in (self._gain, self._pan, self._fade_in, self._fade_out, self._speed, self._pitch):
            card_layout.addWidget(widget)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._reverse_btn = self._toggle(
            "Reverse",
            lambda on: self._set_private("_se_reverse", bool(on)),
            icon_name="loop",
            compact=True,
        )
        self._mute_btn = self._toggle(
            "Mute",
            lambda on: self._set_attr("gain", 0.0 if on else max(0.01, getattr(self._clip, "gain", 1.0) or 1.0)),
            icon_name="x",
            compact=True,
        )
        self._reset_basic_btn = QPushButton("", self)
        self._reset_basic_btn.setObjectName("SoundIconButton")
        self._reset_basic_btn.setIcon(app_icon("reset", size=12, color="#D7DAE7"))
        self._reset_basic_btn.setIconSize(icon_size(12))
        self._reset_basic_btn.setFixedSize(27, 24)
        self._reset_basic_btn.setToolTip("Reset basic controls")
        self._reset_basic_btn.setAccessibleName("Reset basic controls")
        self._reset_basic_btn.clicked.connect(self._reset_basic)
        row.addWidget(self._reverse_btn)
        row.addWidget(self._mute_btn)
        row.addWidget(self._reset_basic_btn)
        row.addStretch(1)
        card_layout.addLayout(row)
        card_layout.addWidget(self._preset_row(self.BASIC_PRESETS.keys(), self._apply_basic_preset))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_eq_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self._eq_enabled = self._toggle("Enable EQ", lambda on: self._set_fx("eq", "enabled", bool(on)))
        card, card_layout = self._card("Equalizer", self._eq_enabled)
        self._eq_graph = _MiniSoundGraph("eq", self)
        self._eq_low_freq = _ValueSlider("Low Freq", 20, 250, 80, suffix=" Hz")
        self._eq_low = _ValueSlider("Low", -120, 120, 0, scale=10.0, suffix=" dB")
        self._eq_low_q = _ValueSlider("Low Q", 1, 100, 7, scale=10.0)
        self._eq_mid_freq = _ValueSlider("Mid Freq", 200, 5000, 1000, suffix=" Hz")
        self._eq_mid = _ValueSlider("Mid", -120, 120, 0, scale=10.0, suffix=" dB")
        self._eq_mid_q = _ValueSlider("Mid Q", 1, 100, 10, scale=10.0)
        self._eq_high_freq = _ValueSlider("High Freq", 2000, 20000, 10000, suffix=" Hz")
        self._eq_high = _ValueSlider("High", -120, 120, 0, scale=10.0, suffix=" dB")
        self._eq_high_q = _ValueSlider("High Q", 1, 100, 7, scale=10.0)
        self._eq_graph.value_edited.connect(self._set_eq_gain_from_graph)
        self._eq_low_freq.value_changed.connect(lambda v: self._set_fx("eq", ("low", "freq"), v))
        self._eq_low.value_changed.connect(lambda v: self._set_fx("eq", ("low", "gain"), v))
        self._eq_low_q.value_changed.connect(lambda v: self._set_fx("eq", ("low", "q"), v))
        self._eq_mid_freq.value_changed.connect(lambda v: self._set_fx("eq", ("mid", "freq"), v))
        self._eq_mid.value_changed.connect(lambda v: self._set_fx("eq", ("mid", "gain"), v))
        self._eq_mid_q.value_changed.connect(lambda v: self._set_fx("eq", ("mid", "q"), v))
        self._eq_high_freq.value_changed.connect(lambda v: self._set_fx("eq", ("high", "freq"), v))
        self._eq_high.value_changed.connect(lambda v: self._set_fx("eq", ("high", "gain"), v))
        self._eq_high_q.value_changed.connect(lambda v: self._set_fx("eq", ("high", "q"), v))
        for widget in (
            self._eq_graph,
            self._eq_low_freq, self._eq_low, self._eq_low_q,
            self._eq_mid_freq, self._eq_mid, self._eq_mid_q,
            self._eq_high_freq, self._eq_high, self._eq_high_q,
        ):
            card_layout.addWidget(widget)
        card_layout.addWidget(self._preset_row(self.EQ_PRESETS.keys(), self._apply_eq_preset))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_mixer_page(self) -> QWidget:
        page = QWidget(self)
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        card, card_layout = self._card("Mixer")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._mixer_scroll = QScrollArea(card)
        self._mixer_scroll.setObjectName("SoundMixerScroll")
        self._mixer_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._mixer_scroll.setWidgetResizable(True)
        self._mixer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._mixer_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._mixer_scroll.setMinimumHeight(292)
        self._mixer_host = QWidget(self._mixer_scroll)
        self._mixer_host.setStyleSheet("background: transparent;")
        self._mixer_layout = QHBoxLayout(self._mixer_host)
        self._mixer_layout.setContentsMargins(0, 0, 0, 0)
        self._mixer_layout.setSpacing(5)
        self._mixer_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._mixer_scroll.setWidget(self._mixer_host)
        card_layout.addWidget(self._mixer_scroll, 1)
        layout.addWidget(card, 1)
        self._refresh_mixer_tracks()
        return page

    def _refresh_mixer_tracks(self) -> None:
        layout = getattr(self, "_mixer_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._mixer_strips.clear()
        self._mixer_master_strip = None
        solo_active = any(bool(getattr(track, "solo", False)) for track in self._mixer_tracks)
        for index, track in enumerate(self._mixer_tracks):
            strip = _SoundMixerStrip(self._mixer_host)
            strip.set_track(
                track,
                index,
                active=getattr(track, "id", None) == self._mixer_active_track_id,
                solo_active=solo_active,
            )
            strip.volume_changed.connect(self._set_mixer_track_volume)
            strip.pan_changed.connect(self._set_mixer_track_pan)
            strip.mute_changed.connect(self._set_mixer_track_mute)
            strip.solo_changed.connect(self._set_mixer_track_solo)
            strip.meta_changed.connect(self._set_mixer_track_meta)
            self._mixer_strips[strip.track_id] = strip
            layout.addWidget(strip)
        if self._mixer_tracks:
            self._mixer_master_strip = _SoundMixerMasterStrip(self._mixer_host)
            self._mixer_master_strip.set_tracks(self._mixer_tracks)
            layout.addWidget(self._mixer_master_strip)
        layout.addStretch(1)

    def _mixer_track_by_id(self, track_id: int) -> Any | None:
        target = int(track_id)
        for track in self._mixer_tracks:
            try:
                if int(getattr(track, "id", -1)) == target:
                    return track
            except Exception:
                continue
        return None

    def _refresh_mixer_strip_states(self) -> None:
        solo_active = any(bool(getattr(track, "solo", False)) for track in self._mixer_tracks)
        for index, track in enumerate(self._mixer_tracks):
            try:
                tid = int(getattr(track, "id", index + 1))
            except Exception:
                continue
            strip = self._mixer_strips.get(tid)
            if strip is not None:
                strip.set_track(
                    track,
                    index,
                    active=tid == self._mixer_active_track_id,
                    solo_active=solo_active,
                )
        if self._mixer_master_strip is not None:
            self._mixer_master_strip.set_tracks(self._mixer_tracks)

    def _emit_mixer_track_changed(self, track: Any) -> None:
        self._refresh_mixer_strip_states()
        self._refresh_chain()
        self.mixer_track_changed.emit(track)
        self.changed.emit()

    def _set_mixer_track_volume(self, track_id: int, volume: float) -> None:
        track = self._mixer_track_by_id(track_id)
        if track is None:
            return
        track.volume = max(0.0, min(1.5, float(volume or 0.0)))
        self._emit_mixer_track_changed(track)

    def _set_mixer_track_pan(self, track_id: int, pan: float) -> None:
        track = self._mixer_track_by_id(track_id)
        if track is None:
            return
        track.pan = max(-1.0, min(1.0, float(pan or 0.0)))
        self._emit_mixer_track_changed(track)

    def _set_mixer_track_mute(self, track_id: int, muted: bool) -> None:
        track = self._mixer_track_by_id(track_id)
        if track is None:
            return
        track.muted = bool(muted)
        self._emit_mixer_track_changed(track)

    def _set_mixer_track_solo(self, track_id: int, solo: bool) -> None:
        track = self._mixer_track_by_id(track_id)
        if track is None:
            return
        track.solo = bool(solo)
        self._emit_mixer_track_changed(track)

    def _set_mixer_track_meta(self, track_id: int, payload: object) -> None:
        track = self._mixer_track_by_id(track_id)
        if track is None or not isinstance(payload, dict):
            return
        kind = str(payload.get("kind") or "").strip().lower()
        if kind == "insert":
            slot = str(payload.get("slot") or "").strip().lower()
            slots = _mixer_insert_slots(track)
            for row in slots:
                if str(row.get("id")) == slot:
                    row["enabled"] = bool(payload.get("enabled"))
                    row["bypassed"] = bool(payload.get("bypassed", False))
            track.insert_slots = slots
        elif kind == "send":
            sends = _mixer_sends(track)
            sid = str(payload.get("send_id") or "").strip().lower()
            try:
                sends[sid] = max(0.0, min(1.0, float(payload.get("level") or 0.0)))
            except Exception:
                sends[sid] = 0.0
            track.sends = sends
        elif kind == "automation":
            track.automation_read = bool(payload.get("read", True))
            track.automation_write = bool(payload.get("write", False))
        elif kind == "type":
            track.track_type = str(payload.get("track_type") or "dialogue")
        else:
            return
        self._emit_mixer_track_changed(track)

    def _build_dynamics_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self._comp_enabled = self._toggle("Compressor", lambda on: self._set_fx("comp", "enabled", bool(on)))
        self._gate_enabled = self._toggle("Gate", lambda on: self._set_fx("gate", "enabled", bool(on)))
        card, card_layout = self._card("Dynamics", self._comp_enabled, self._gate_enabled)
        self._dyn_graph = _MiniSoundGraph("dyn", self)
        self._comp_threshold = _ValueSlider("Threshold", -600, 0, -200, scale=10.0, suffix=" dB")
        self._comp_ratio = _ValueSlider("Ratio", 10, 200, 40, scale=10.0, suffix=":1")
        self._comp_attack = _ValueSlider("Attack", 1, 1000, 50, scale=10.0, suffix=" ms")
        self._comp_release = _ValueSlider("Release", 10, 1000, 150, suffix=" ms")
        self._comp_makeup = _ValueSlider("Makeup", -120, 120, 0, scale=10.0, suffix=" dB")
        self._comp_knee = _ValueSlider("Knee", 0, 100, 20, scale=10.0, suffix=" dB")
        self._gate_threshold = _ValueSlider("Gate Threshold", -700, -100, -500, scale=10.0, suffix=" dB")
        self._gate_reduction = _ValueSlider("Gate Reduction", 0, 100, 50, suffix="%")
        self._dyn_graph.dynamics_edited.connect(self._set_dynamics_from_graph)
        self._comp_threshold.value_changed.connect(lambda v: self._set_fx("comp", "threshold", v))
        self._comp_ratio.value_changed.connect(lambda v: self._set_fx("comp", "ratio", v))
        self._comp_attack.value_changed.connect(lambda v: self._set_fx("comp", "attack_ms", v))
        self._comp_release.value_changed.connect(lambda v: self._set_fx("comp", "release_ms", v))
        self._comp_makeup.value_changed.connect(lambda v: self._set_fx("comp", "makeup_db", v))
        self._comp_knee.value_changed.connect(lambda v: self._set_fx("comp", "knee_db", v))
        self._gate_threshold.value_changed.connect(lambda v: self._set_fx("gate", "threshold", v))
        self._gate_reduction.value_changed.connect(lambda v: self._set_fx("gate", "reduction", v))
        for widget in (
            self._dyn_graph, self._comp_threshold, self._comp_ratio,
            self._comp_attack, self._comp_release, self._comp_makeup, self._comp_knee,
            self._gate_threshold, self._gate_reduction,
        ):
            card_layout.addWidget(widget)
        card_layout.addWidget(self._preset_row(self.DYN_PRESETS.keys(), self._apply_dyn_preset))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_fx_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self._reverb_enabled = self._toggle("Reverb", lambda on: self._set_fx("reverb", "enabled", bool(on)))
        self._delay_enabled = self._toggle("Delay", lambda on: self._set_fx("delay", "enabled", bool(on)))
        self._deesser_enabled = self._toggle("De-esser", lambda on: self._set_fx("deesser", "enabled", bool(on)))
        card, card_layout = self._card("Space / cleanup", self._reverb_enabled, self._delay_enabled, self._deesser_enabled)
        self._fx_graph = _MiniSoundGraph("fx", self)
        self._reverb_type = self._combo(
            ["Room", "Hall", "Plate", "Spring"],
            lambda text: self._set_fx("reverb", "type", str(text)),
        )
        self._reverb_size = _ValueSlider("Reverb Size", 0, 100, 30, suffix="%")
        self._reverb_decay = _ValueSlider("Reverb Decay", 1, 100, 15, scale=10.0, suffix=" s")
        self._reverb_damping = _ValueSlider("Damping", 0, 100, 50, suffix="%")
        self._reverb_mix = _ValueSlider("Reverb Mix", 0, 100, 20, suffix="%")
        self._delay_time = _ValueSlider("Delay Time", 0, 2000, 250, suffix=" ms")
        self._delay_feedback = _ValueSlider("Feedback", 0, 95, 30, suffix="%")
        self._delay_mix = _ValueSlider("Delay Mix", 0, 100, 20, suffix="%")
        self._deesser_reduction = _ValueSlider("Reduction", 0, 100, 40, suffix="%")
        self._fx_graph.value_edited.connect(self._set_fx_value_from_graph)
        self._reverb_size.value_changed.connect(lambda v: self._set_fx("reverb", "size", v))
        self._reverb_decay.value_changed.connect(lambda v: self._set_fx("reverb", "decay_s", v))
        self._reverb_damping.value_changed.connect(lambda v: self._set_fx("reverb", "damping", v))
        self._reverb_mix.value_changed.connect(lambda v: self._set_fx("reverb", "mix", v))
        self._delay_time.value_changed.connect(lambda v: self._set_fx("delay", "time_ms", v))
        self._delay_feedback.value_changed.connect(lambda v: self._set_fx("delay", "feedback", v))
        self._delay_mix.value_changed.connect(lambda v: self._set_fx("delay", "mix", v))
        self._deesser_reduction.value_changed.connect(lambda v: self._set_fx("deesser", "reduction", v))
        type_row = QHBoxLayout()
        type_row.setContentsMargins(0, 0, 0, 0)
        type_row.setSpacing(5)
        type_label = QLabel("Reverb Type", page)
        type_label.setObjectName("SoundFieldLabel")
        type_row.addWidget(type_label, 1)
        type_row.addWidget(self._reverb_type, 0)
        for widget in (
            self._fx_graph,
        ):
            card_layout.addWidget(widget)
        card_layout.addLayout(type_row)
        for widget in (
            self._reverb_size, self._reverb_decay, self._reverb_damping, self._reverb_mix,
            self._delay_time, self._delay_feedback, self._delay_mix, self._deesser_reduction,
        ):
            card_layout.addWidget(widget)
        card_layout.addWidget(self._preset_row(self.FX_PRESETS.keys(), self._apply_fx_preset))
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_ai_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        self._ai_enabled = self._toggle("Enable AI Master", lambda on: self._set_fx("ai_master", "enabled", bool(on)))
        card, card_layout = self._card("AI master", self._ai_enabled)
        self._ai_graph = _MiniSoundGraph("ai", self)
        self._ai_air = _ValueSlider("Air", 0, 80, 0, scale=10.0, suffix=" dB")
        self._ai_clarity = _ValueSlider("Clarity", 0, 100, 0, suffix="%")
        self._ai_warmth = _ValueSlider("Warmth", 0, 100, 0, suffix="%")
        self._ai_width = _ValueSlider("Width", 0, 200, 100, suffix="%")
        self._ai_punch = _ValueSlider("Punch", 0, 100, 0, suffix="%")
        self._ai_excite = _ValueSlider("Excite", 0, 100, 0, suffix="%")
        self._ai_graph.value_edited.connect(self._set_ai_value_from_graph)
        self._ai_air.value_changed.connect(lambda v: self._set_fx("ai_master", "air", v))
        self._ai_clarity.value_changed.connect(lambda v: self._set_fx("ai_master", "clarity", v))
        self._ai_warmth.value_changed.connect(lambda v: self._set_fx("ai_master", "warmth", v))
        self._ai_width.value_changed.connect(lambda v: self._set_fx("ai_master", "width", v))
        self._ai_punch.value_changed.connect(lambda v: self._set_fx("ai_master", "punch", v))
        self._ai_excite.value_changed.connect(lambda v: self._set_fx("ai_master", "excite", v))
        for widget in (
            self._ai_graph, self._ai_air, self._ai_clarity, self._ai_warmth,
            self._ai_width, self._ai_punch, self._ai_excite,
        ):
            card_layout.addWidget(widget)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _set_tab(self, tab_id: str) -> None:
        order = {"basic": 0, "mixer": 1, "eq": 2, "dyn": 3, "fx": 4, "ai": 5}
        self._stack.setCurrentIndex(order.get(tab_id, 0))
        for key, button in self._tab_buttons.items():
            button.setChecked(key == tab_id)
        self._set_mixer_tab_compact_mode(tab_id == "mixer")

    def _set_mixer_tab_compact_mode(self, compact: bool) -> None:
        for widget in (self._jog_shuttle, self._waveform_strip, self._spectrum_strip):
            widget.setVisible(not compact)

    def _sync_from_clip(self) -> None:
        clip = self._clip
        if clip is None:
            return
        self._ui_lock = True
        try:
            self._gain.set_raw_value(int(round(float(getattr(clip, "gain", 1.0) or 1.0) * 100)))
            pan_value = getattr(clip, "_se_pan", getattr(self._track, "pan", 0.0) if self._track is not None else 0.0)
            self._pan.set_raw_value(int(round(float(pan_value or 0.0) * 100.0)))
            self._fade_in.set_raw_value(int(getattr(clip, "fade_in_ms", 0) or 0))
            self._fade_out.set_raw_value(int(getattr(clip, "fade_out_ms", 0) or 0))
            self._speed.set_raw_value(int(round(float(getattr(clip, "_se_speed", 1.0) or 1.0) * 100)))
            self._pitch.set_raw_value(int(round(float(getattr(clip, "_se_pitch", 0.0) or 0.0) * 10)))
            self._reverse_btn.setChecked(bool(getattr(clip, "_se_reverse", False)))
            self._mute_btn.setChecked(float(getattr(clip, "gain", 1.0) or 1.0) <= 0.001)
            fx = clip.effects
            eq = fx.get("eq", {})
            self._eq_enabled.setChecked(bool(eq.get("enabled")))
            self._eq_low_freq.set_raw_value(int(round(float((eq.get("low") or {}).get("freq", 80.0)))))
            self._eq_low.set_raw_value(int(round(float((eq.get("low") or {}).get("gain", 0.0)) * 10)))
            self._eq_low_q.set_raw_value(int(round(float((eq.get("low") or {}).get("q", 0.7)) * 10)))
            self._eq_mid_freq.set_raw_value(int(round(float((eq.get("mid") or {}).get("freq", 1000.0)))))
            self._eq_mid.set_raw_value(int(round(float((eq.get("mid") or {}).get("gain", 0.0)) * 10)))
            self._eq_mid_q.set_raw_value(int(round(float((eq.get("mid") or {}).get("q", 1.0)) * 10)))
            self._eq_high_freq.set_raw_value(int(round(float((eq.get("high") or {}).get("freq", 10000.0)))))
            self._eq_high.set_raw_value(int(round(float((eq.get("high") or {}).get("gain", 0.0)) * 10)))
            self._eq_high_q.set_raw_value(int(round(float((eq.get("high") or {}).get("q", 0.7)) * 10)))
            comp = fx.get("comp", {})
            gate = fx.get("gate", {})
            self._comp_enabled.setChecked(bool(comp.get("enabled")))
            self._comp_threshold.set_raw_value(int(round(float(comp.get("threshold", -20.0)) * 10)))
            self._comp_ratio.set_raw_value(int(round(float(comp.get("ratio", 4.0)) * 10)))
            self._comp_attack.set_raw_value(int(round(float(comp.get("attack_ms", 5.0)) * 10)))
            self._comp_release.set_raw_value(int(round(float(comp.get("release_ms", 150.0)))))
            self._comp_makeup.set_raw_value(int(round(float(comp.get("makeup_db", 0.0)) * 10)))
            self._comp_knee.set_raw_value(int(round(float(comp.get("knee_db", 2.0)) * 10)))
            self._gate_enabled.setChecked(bool(gate.get("enabled")))
            self._gate_threshold.set_raw_value(int(round(float(gate.get("threshold", -50.0)) * 10)))
            self._gate_reduction.set_raw_value(int(round(float(gate.get("reduction", 50.0)))))
            reverb = fx.get("reverb", {})
            delay = fx.get("delay", {})
            deesser = fx.get("deesser", {})
            self._reverb_enabled.setChecked(bool(reverb.get("enabled")))
            self._set_combo_text(self._reverb_type, reverb.get("type", "Room"))
            self._reverb_size.set_raw_value(int(round(float(reverb.get("size", 30.0)))))
            self._reverb_decay.set_raw_value(int(round(float(reverb.get("decay_s", 1.5)) * 10.0)))
            self._reverb_damping.set_raw_value(int(round(float(reverb.get("damping", 50.0)))))
            self._reverb_mix.set_raw_value(int(round(float(reverb.get("mix", 20.0)))))
            self._delay_enabled.setChecked(bool(delay.get("enabled")))
            self._delay_time.set_raw_value(int(round(float(delay.get("time_ms", 250.0)))))
            self._delay_feedback.set_raw_value(int(round(float(delay.get("feedback", 30.0)))))
            self._delay_mix.set_raw_value(int(round(float(delay.get("mix", 20.0)))))
            self._deesser_enabled.setChecked(bool(deesser.get("enabled")))
            self._deesser_reduction.set_raw_value(int(round(float(deesser.get("reduction", 40.0)))))
            dialogue = fx.get("dialogue_cleanup", {})
            self._dialogue_enabled.setChecked(bool(dialogue.get("enabled")))
            self._dialogue_strength.set_raw_value(int(round(float(dialogue.get("strength", 0.0)) * 100.0)))
            self._noise_reduction.set_raw_value(int(round(float(dialogue.get("noise_reduction", 0.0)) * 10.0)))
            self._de_reverb.set_raw_value(int(round(float(dialogue.get("de_reverb", 0.0)) * 100.0)))
            self._presence.set_raw_value(int(round(float(dialogue.get("presence_db", 0.0)) * 10.0)))
            self._lab_deesser_enabled.setChecked(bool(deesser.get("enabled")))
            self._lab_deesser_freq.set_raw_value(int(round(float(deesser.get("freq", 6000.0)))))
            self._lab_deesser_threshold.set_raw_value(int(round(float(deesser.get("threshold", -30.0)) * 10.0)))
            self._lab_deesser_reduction.set_raw_value(int(round(float(deesser.get("reduction", 40.0)))))
            time_stretch = fx.get("time_stretch", {})
            self._time_enabled.setChecked(bool(time_stretch.get("enabled")))
            self._time_ratio.set_raw_value(int(round(float(time_stretch.get("ratio", 1.0)) * 100.0)))
            self._set_combo_text(self._time_algorithm, time_stretch.get("algorithm", "atempo"))
            loudness = fx.get("loudness", {})
            self._loudness_enabled.setChecked(bool(loudness.get("enabled")))
            self._target_lufs.set_raw_value(int(round(float(loudness.get("target_i", -14.0)) * 10.0)))
            self._true_peak.set_raw_value(int(round(float(loudness.get("true_peak", -1.0)) * 10.0)))
            self._lra.set_raw_value(int(round(float(loudness.get("lra", 11.0)) * 10.0)))
            ai = fx.get("ai_master", {})
            self._ai_enabled.setChecked(bool(ai.get("enabled")))
            self._ai_air.set_raw_value(int(round(float(ai.get("air", 0.0)) * 10)))
            self._ai_clarity.set_raw_value(int(round(float(ai.get("clarity", 0.0)))))
            self._ai_warmth.set_raw_value(int(round(float(ai.get("warmth", 0.0)))))
            self._ai_width.set_raw_value(int(round(float(ai.get("width", 100.0)))))
            self._ai_punch.set_raw_value(int(round(float(ai.get("punch", 0.0)))))
            self._ai_excite.set_raw_value(int(round(float(ai.get("excite", 0.0)))))
        finally:
            self._ui_lock = False
        self._refresh_ai_preset_buttons()
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        self._refresh_visuals()

    def _set_attr(self, name: str, value: Any) -> None:
        if self._ui_lock or self._clip is None:
            return
        setattr(self._clip, name, value)
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        self._refresh_chain()
        self.changed.emit()

    def _set_private(self, name: str, value: Any) -> None:
        self._set_attr(name, value)

    def _set_pan(self, value: float) -> None:
        if self._ui_lock or self._clip is None:
            return
        pan = max(-1.0, min(1.0, float(value)))
        setattr(self._clip, "_se_pan", pan)
        if self._track is not None:
            try:
                setattr(self._track, "pan", pan)
            except Exception:
                pass
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        self._refresh_chain()
        self.changed.emit()

    def _reset_basic(self) -> None:
        if self._ui_lock or self._clip is None:
            return
        self._clip.gain = 1.0
        self._clip.fade_in_ms = 0
        self._clip.fade_out_ms = 0
        setattr(self._clip, "_se_speed", 1.0)
        setattr(self._clip, "_se_pitch", 0.0)
        setattr(self._clip, "_se_reverse", False)
        setattr(self._clip, "_se_pan", 0.0)
        if self._track is not None:
            try:
                setattr(self._track, "pan", 0.0)
            except Exception:
                pass
        self._sync_from_clip()
        self._refresh_chain()
        self.changed.emit()

    def _apply_basic_preset(self, name: str) -> None:
        if self._ui_lock or self._clip is None:
            return
        preset = self.BASIC_PRESETS.get(str(name))
        if not preset:
            return
        self._clip.gain = max(0.0, float(preset.get("gain", 1.0)))
        self._clip.fade_in_ms = int(preset.get("fade_in_ms", 0))
        self._clip.fade_out_ms = int(preset.get("fade_out_ms", 0))
        setattr(self._clip, "_se_speed", max(0.1, float(preset.get("speed", 1.0))))
        setattr(self._clip, "_se_pitch", float(preset.get("pitch", 0.0)))
        pan = max(-1.0, min(1.0, float(preset.get("pan", 0.0))))
        setattr(self._clip, "_se_pan", pan)
        if self._track is not None:
            try:
                setattr(self._track, "pan", pan)
            except Exception:
                pass
        self._sync_from_clip()
        self._refresh_chain()
        self.changed.emit()

    def _apply_eq_preset(self, name: str) -> None:
        if self._ui_lock or self._clip is None:
            return
        preset = self.EQ_PRESETS.get(str(name))
        if not preset:
            return
        eq = self._clip.effects.setdefault("eq", copy.deepcopy(default_effects_state().get("eq", {})))
        for band, key in (("low", "low_g"), ("mid", "mid_g"), ("high", "high_g")):
            eq.setdefault(band, copy.deepcopy(default_effects_state()["eq"][band]))
            eq[band]["gain"] = float(preset.get(key, 0.0))
        eq["enabled"] = True
        self._sync_from_clip()
        self._refresh_chain()
        self.changed.emit()

    def _apply_dyn_preset(self, name: str) -> None:
        if self._ui_lock or self._clip is None:
            return
        preset = self.DYN_PRESETS.get(str(name))
        if not preset:
            return
        comp = self._clip.effects.setdefault("comp", copy.deepcopy(default_effects_state().get("comp", {})))
        for key in ("threshold", "ratio", "attack_ms", "release_ms", "makeup_db", "knee_db"):
            if key in preset:
                comp[key] = float(preset[key])
        comp["enabled"] = True
        self._sync_from_clip()
        self._refresh_chain()
        self.changed.emit()

    def _apply_fx_preset(self, name: str) -> None:
        if self._ui_lock or self._clip is None:
            return
        preset = self.FX_PRESETS.get(str(name))
        if not preset:
            return
        reverb = self._clip.effects.setdefault("reverb", copy.deepcopy(default_effects_state().get("reverb", {})))
        for key in ("type", "size", "decay_s", "damping", "mix"):
            if key in preset:
                reverb[key] = preset[key] if key == "type" else float(preset[key])
        reverb["enabled"] = True
        if isinstance(preset.get("_delay"), dict):
            delay = self._clip.effects.setdefault("delay", copy.deepcopy(default_effects_state().get("delay", {})))
            for key, value in preset["_delay"].items():
                delay[key] = float(value)
            delay["enabled"] = True
        self._sync_from_clip()
        self._refresh_chain()
        self.changed.emit()

    def _set_eq_gain_from_graph(self, band_index: int, gain: float) -> None:
        if self._ui_lock or self._clip is None:
            return
        bands = ("low", "mid", "high")
        sliders = (self._eq_low, self._eq_mid, self._eq_high)
        index = max(0, min(2, int(band_index)))
        value = max(-12.0, min(12.0, float(gain)))
        sliders[index].set_raw_value(int(round(value * 10.0)))
        self._set_fx("eq", (bands[index], "gain"), round(value, 1))

    def _set_dynamics_from_graph(self, threshold: float, ratio: float) -> None:
        if self._ui_lock or self._clip is None:
            return
        thr = max(-60.0, min(0.0, float(threshold)))
        rat = max(1.0, min(20.0, float(ratio)))
        self._comp_threshold.set_raw_value(int(round(thr * 10.0)))
        self._comp_ratio.set_raw_value(int(round(rat * 10.0)))
        self._set_fx("comp", "threshold", round(thr, 1))
        self._set_fx("comp", "ratio", round(rat, 1))

    def _set_fx_value_from_graph(self, effect_index: int, value: float) -> None:
        if self._ui_lock or self._clip is None:
            return
        bindings = (
            ("reverb", "mix", self._reverb_mix),
            ("delay", "mix", self._delay_mix),
            ("deesser", "reduction", self._deesser_reduction),
        )
        index = max(0, min(len(bindings) - 1, int(effect_index)))
        fx_key, sub_key, slider = bindings[index]
        val = max(0.0, min(100.0, float(value)))
        slider.set_raw_value(int(round(val)))
        self._set_fx(fx_key, sub_key, round(val, 1))

    def _set_ai_value_from_graph(self, macro_index: int, value: float) -> None:
        if self._ui_lock or self._clip is None:
            return
        bindings = (
            ("air", self._ai_air, 0.0, 8.0, 10.0),
            ("clarity", self._ai_clarity, 0.0, 100.0, 1.0),
            ("warmth", self._ai_warmth, 0.0, 100.0, 1.0),
            ("width", self._ai_width, 0.0, 200.0, 1.0),
            ("punch", self._ai_punch, 0.0, 100.0, 1.0),
            ("excite", self._ai_excite, 0.0, 100.0, 1.0),
        )
        index = max(0, min(len(bindings) - 1, int(macro_index)))
        key, slider, minimum, maximum, raw_scale = bindings[index]
        val = max(minimum, min(maximum, float(value)))
        slider.set_raw_value(int(round(val * raw_scale)))
        self._set_fx("ai_master", key, round(val, 1 if key == "air" else 0))

    def _set_fx(self, fx_key: str, sub_key: Any, value: Any) -> None:
        if self._ui_lock or self._clip is None:
            return
        effects = self._clip.effects
        defaults = default_effects_state()
        state = effects.setdefault(fx_key, copy.deepcopy(defaults.get(fx_key, {})))
        if isinstance(sub_key, tuple) and len(sub_key) == 2:
            section = state.setdefault(sub_key[0], {})
            if isinstance(section, dict):
                section[sub_key[1]] = value
        else:
            state[sub_key] = value
        if fx_key == "ai_master" and sub_key not in {"enabled", "preset"}:
            state["preset"] = "Custom"
        if sub_key != "enabled" and self._fx_has_audible_change(fx_key, state):
            state["enabled"] = True
        self._refresh_ai_preset_buttons()
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        self._refresh_chain()
        self._refresh_visuals()
        self.changed.emit()

    def _refresh_visuals(self) -> None:
        clip = self._clip
        effects = getattr(clip, "effects", {}) if clip is not None and isinstance(getattr(clip, "effects", None), dict) else {}
        eq = effects.get("eq") or {}
        self._eq_graph.set_values(
            float((eq.get("low") or {}).get("gain", 0.0) or 0.0),
            float((eq.get("mid") or {}).get("gain", 0.0) or 0.0),
            float((eq.get("high") or {}).get("gain", 0.0) or 0.0),
        )
        comp = effects.get("comp") or {}
        self._dyn_graph.set_values(
            float(comp.get("threshold", -20.0) or -20.0),
            float(comp.get("ratio", 4.0) or 4.0),
        )
        reverb = effects.get("reverb") or {}
        delay = effects.get("delay") or {}
        deesser = effects.get("deesser") or {}
        self._fx_graph.set_values(
            float(reverb.get("mix", 0.0) or 0.0),
            float(delay.get("mix", 0.0) or 0.0),
            float(deesser.get("reduction", 0.0) or 0.0),
        )
        ai = effects.get("ai_master") or {}
        self._ai_graph.set_values(
            float(ai.get("air", 0.0) or 0.0),
            float(ai.get("clarity", 0.0) or 0.0),
            float(ai.get("warmth", 0.0) or 0.0),
            float(ai.get("width", 100.0) or 100.0),
            float(ai.get("punch", 0.0) or 0.0),
            float(ai.get("excite", 0.0) or 0.0),
        )
        self._refresh_ai_preset_buttons()
        if hasattr(self, "_macro_jog_bank"):
            self._macro_jog_bank.set_source(self._clip, self._track)
        advanced_active = any(
            bool((effects.get(key) or {}).get("enabled")) or self._fx_has_audible_change(key, effects.get(key) or {})
            for key in ("dialogue_cleanup", "loudness", "time_stretch")
        )
        if hasattr(self, "_advanced_btn"):
            self._advanced_btn.setProperty("active", bool(advanced_active))
            self._advanced_btn.style().unpolish(self._advanced_btn)
            self._advanced_btn.style().polish(self._advanced_btn)

    def _refresh_chain(self) -> None:
        clip = self._clip
        active = {key: False for key in self._chain_labels}
        if clip is not None:
            active["basic"] = (
                abs(float(getattr(clip, "gain", 1.0) or 1.0) - 1.0) > 0.001
                or int(getattr(clip, "fade_in_ms", 0) or 0) > 0
                or int(getattr(clip, "fade_out_ms", 0) or 0) > 0
                or abs(float(getattr(clip, "_se_speed", 1.0) or 1.0) - 1.0) > 0.001
                or abs(float(getattr(clip, "_se_pitch", 0.0) or 0.0)) > 0.001
                or bool(getattr(clip, "_se_reverse", False))
                or abs(float(getattr(clip, "_se_pan", getattr(self._track, "pan", 0.0) if self._track is not None else 0.0) or 0.0)) > 0.001
            )
            effects = getattr(clip, "effects", {}) if isinstance(getattr(clip, "effects", None), dict) else {}
            active["eq"] = self._fx_has_audible_change("eq", effects.get("eq") or {}) or bool((effects.get("eq") or {}).get("enabled"))
            active["dyn"] = any(
                bool((effects.get(key) or {}).get("enabled")) or self._fx_has_audible_change(key, effects.get(key) or {})
                for key in ("comp", "gate")
            )
            active["fx"] = any(bool((effects.get(key) or {}).get("enabled")) for key in ("reverb", "delay", "deesser"))
            active["ai"] = bool((effects.get("ai_master") or {}).get("enabled")) or self._fx_has_audible_change("ai_master", effects.get("ai_master") or {})
        active["mixer"] = any(
            abs(float(getattr(track, "volume", 1.0) or 0.0) - 1.0) > 0.001
            or abs(float(getattr(track, "pan", 0.0) or 0.0)) > 0.001
            or bool(getattr(track, "muted", False))
            or bool(getattr(track, "solo", False))
            for track in self._mixer_tracks
        )
        for key, label in self._chain_labels.items():
            label.setProperty("active", bool(active.get(key)))
            label.style().unpolish(label)
            label.style().polish(label)

    @staticmethod
    def _fx_has_audible_change(fx_key: str, state: dict) -> bool:
        if fx_key == "eq":
            return any(abs(float((state.get(b) or {}).get("gain", 0.0) or 0.0)) > 0.01 for b in ("low", "mid", "high"))
        if fx_key == "comp":
            return abs(float(state.get("threshold", -20.0)) + 20.0) > 0.01 or abs(float(state.get("makeup_db", 0.0))) > 0.01
        if fx_key == "gate":
            return abs(float(state.get("threshold", -50.0)) + 50.0) > 0.01
        if fx_key in {"reverb", "delay", "deesser"}:
            return True
        if fx_key == "ai_master":
            return any(abs(float(state.get(k, 0.0) or 0.0)) > 0.01 for k in ("air", "clarity", "warmth", "punch", "excite")) or abs(float(state.get("width", 100.0) or 100.0) - 100.0) > 0.01
        if fx_key == "dialogue_cleanup":
            return (
                abs(float(state.get("strength", 0.0) or 0.0)) > 0.001
                or abs(float(state.get("noise_reduction", 0.0) or 0.0)) > 0.01
                or abs(float(state.get("de_reverb", 0.0) or 0.0)) > 0.001
                or abs(float(state.get("presence_db", 0.0) or 0.0)) > 0.01
                or abs(float(state.get("air_db", 0.0) or 0.0)) > 0.01
                or bool(state.get("hum_remove"))
                or bool(state.get("mouth_click"))
                or bool(state.get("plosive"))
                or bool(state.get("auto_level"))
            )
        if fx_key == "loudness":
            return (
                abs(float(state.get("target_i", -14.0) or -14.0) + 14.0) > 0.01
                or abs(float(state.get("true_peak", -1.0) or -1.0) + 1.0) > 0.01
                or abs(float(state.get("lra", 11.0) or 11.0) - 11.0) > 0.01
            )
        if fx_key == "time_stretch":
            return abs(float(state.get("ratio", 1.0) or 1.0) - 1.0) > 0.001
        return False

    def _export_clip(self) -> None:
        clip = self._clip
        if clip is None or clip.source_path is None:
            return
        src = Path(clip.source_path)
        default = str(src.with_name(f"{src.stem}_edited.mp3"))
        filters = [CLIP_EXPORT_FORMATS[k]["filter"] for k in ("mp3", "wav", "flac", "aac", "ogg") if k in CLIP_EXPORT_FORMATS]
        out_path, chosen = QFileDialog.getSaveFileName(
            self,
            "Export edited audio",
            default,
            ";;".join(filters),
            filters[0] if filters else "MP3 Audio (*.mp3)",
        )
        if not out_path:
            return
        format_key = "mp3"
        for key, spec in CLIP_EXPORT_FORMATS.items():
            if spec.get("filter") == chosen:
                format_key = key
                break
        expected_ext = CLIP_EXPORT_FORMATS.get(format_key, {}).get("ext", ".mp3")
        out_obj = Path(out_path)
        if out_obj.suffix.lower() != str(expected_ext).lower():
            out_obj = out_obj.with_suffix(str(expected_ext))
        self._export_btn.setEnabled(False)
        self._exporter = ClipExporter(
            clip,
            str(out_obj),
            format_key,
            parent=self,
            quality_id=DEFAULT_AUDIO_QUALITY_ID,
        )
        self._exporter.done.connect(self._on_export_done)
        self._exporter.failed.connect(self._on_export_failed)
        self._exporter.finished.connect(self._exporter.deleteLater)
        self._exporter.finished.connect(lambda: setattr(self, "_exporter", None))
        self._exporter.start()

    def _on_export_done(self, path: str) -> None:
        self._export_btn.setEnabled(True)
        QMessageBox.information(self, "Export edited audio", f"Exported:\n{path}")

    def _on_export_failed(self, reason: str) -> None:
        self._export_btn.setEnabled(True)
        QMessageBox.warning(self, "Export edited audio", str(reason or "Export failed"))

    def _request_advanced_lab(self) -> None:
        self._toggle_advanced_lab()

    def _toggle_advanced_lab(self) -> None:
        self._set_advanced_lab_expanded(not self._advanced_expanded)

    def _set_advanced_lab_expanded(self, expanded: bool) -> None:
        self._advanced_expanded = bool(expanded)
        if self._clip is not None:
            setattr(self._clip, "_se_advanced_lab_expanded", self._advanced_expanded)
        host = getattr(self, "_advanced_lab_host", None)
        if host is not None:
            host.setVisible(self._advanced_expanded)
        elif hasattr(self, "_advanced_lab_panel"):
            self._advanced_lab_panel.setVisible(self._advanced_expanded)
        if hasattr(self, "_advanced_btn"):
            self._advanced_btn.setProperty("expanded", self._advanced_expanded)
            self._advanced_btn.setToolTip(
                "Collapse advanced audio lab" if self._advanced_expanded else "Expand advanced audio lab"
            )
            self._advanced_btn.style().unpolish(self._advanced_btn)
            self._advanced_btn.style().polish(self._advanced_btn)


class SoundEditorDockWindow(QWidget):
    """Standalone shell for the renewed embedded sound editor."""

    changed = Signal()

    def __init__(
        self,
        clip: AudioClip,
        *,
        track: Any = None,
        mixer_tracks: list[Any] | tuple[Any, ...] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self._clip = clip
        self._track = track
        self.setObjectName("SoundEditorDockWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        src = getattr(clip, "source_path", None)
        name = getattr(clip, "display_name", None) or (Path(src).name if src else "Audio clip")
        self.setWindowTitle(f"Sound Editor - {name}")
        self.resize(420, 760)
        self.setMinimumSize(340, 520)
        self.setStyleSheet("QWidget#SoundEditorDockWindow { background:#101112; }")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._panel = SoundEditorPanel(self)
        self._panel.changed.connect(self.changed)
        root.addWidget(self._panel)
        context_key = (
            f"timeline:{getattr(track, 'id', 'none')}:{getattr(clip, 'id', 'none')}"
            if track is not None
            else f"media:{src}"
        )
        self._panel.set_clip(
            clip,
            track=track,
            context_label="Timeline Audio" if track is not None else "Media Pool Audio",
            context_key=context_key,
        )
        if mixer_tracks is not None:
            self._panel.set_mixer_tracks(mixer_tracks, active_track_id=getattr(track, "id", None))

    def current_clip(self) -> AudioClip:
        return self._clip

    @property
    def clip(self) -> AudioClip:
        return self._clip

    def refresh_waveform(self) -> None:
        self._panel.refresh_waveform()
