"""Mixer strip widgets and helpers for the renewed sound editor."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget


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

def _mixer_type_color(track_type: str, *, alpha: int = 190) -> QColor:
    return {
        "dialogue": QColor(148, 126, 196, alpha),
        "music": QColor(128, 154, 126, alpha),
        "sfx": QColor(162, 123, 116, alpha),
        "ambience": QColor(114, 145, 160, alpha),
    }.get(str(track_type or "").lower(), QColor(142, 150, 158, alpha))

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

class _SoundMixerMeter(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._l = 0.0
        self._r = 0.0
        self._peak = 0.0
        self._clipped = False
        self.setFixedSize(18, 70)

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
            channel = QRectF(x, meter_r.top(), bar_w, meter_r.height())
            slot_grad = QLinearGradient(channel.topLeft(), channel.topRight())
            slot_grad.setColorAt(0.0, QColor(255, 255, 255, 11))
            slot_grad.setColorAt(0.42, QColor(0, 0, 0, 130))
            slot_grad.setColorAt(1.0, QColor(255, 255, 255, 7))
            p.setBrush(QBrush(slot_grad))
            p.drawRoundedRect(channel, 1.8, 1.8)
            fill_h = meter_r.height() * level
            fill = QRectF(x, meter_r.bottom() - fill_h, bar_w, fill_h)
            grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
            grad.setColorAt(0.0, QColor(181, 88, 78, 220))
            grad.setColorAt(0.28, QColor(185, 157, 92, 218))
            grad.setColorAt(0.62, QColor(101, 160, 117, 226))
            grad.setColorAt(1.0, QColor(95, 175, 130, 235))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fill, 1.8, 1.8)
            p.setPen(QPen(QColor(7, 9, 10, 72), 0.7))
            for row in range(1, 10):
                y = meter_r.bottom() - meter_r.height() * row / 10.0
                p.drawLine(QPointF(channel.left() + 0.7, y), QPointF(channel.right() - 0.7, y))
        if self._peak > 0:
            y = meter_r.bottom() - meter_r.height() * self._peak
            p.setPen(QPen(QColor(238, 221, 166, 180), 0.9))
            p.drawLine(QPointF(meter_r.left() - 0.5, y), QPointF(meter_r.right() + 0.5, y))
        p.end()

class _SoundMixerStereoVu(QWidget):
    """Compact analog-style L/R bus meter for the Sound Editor master strip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SoundMixerStereoVu")
        self._l = 0.0
        self._r = 0.0
        self._clipped = False
        self.setFixedSize(112, 56)

    def set_levels(self, left: float, right: float, *, clipped: bool = False) -> None:
        self._l = max(0.0, min(1.0, float(left or 0.0)))
        self._r = max(0.0, min(1.0, float(right or 0.0)))
        self._clipped = bool(clipped)
        self.update()

    def _draw_meter(self, p: QPainter, rect: QRectF, label: str, level: float) -> None:
        panel = rect.adjusted(1.0, 1.0, -1.0, -1.0)
        p.setPen(QPen(QColor(0, 0, 0, 158), 0.7))
        grad = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        grad.setColorAt(0.0, QColor(119, 43, 41, 225))
        grad.setColorAt(0.48, QColor(93, 35, 36, 235))
        grad.setColorAt(1.0, QColor(35, 21, 23, 245))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(panel, 5.5, 5.5)

        glass = QLinearGradient(panel.topLeft(), panel.bottomLeft())
        glass.setColorAt(0.0, QColor(255, 235, 216, 35))
        glass.setColorAt(0.45, QColor(255, 255, 255, 5))
        glass.setColorAt(1.0, QColor(0, 0, 0, 40))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glass))
        p.drawRoundedRect(panel.adjusted(1.0, 1.0, -1.0, -1.0), 4.8, 4.8)

        center = QPointF(panel.center().x(), panel.bottom() - 7.0)
        radius = min(panel.width() * 0.58, panel.height() * 0.68)
        for i in range(7):
            ratio = i / 6.0
            angle = math.radians(204.0 - ratio * 128.0)
            inner = QPointF(center.x() + math.cos(angle) * radius * 0.78, center.y() - math.sin(angle) * radius * 0.78)
            outer = QPointF(center.x() + math.cos(angle) * radius * 0.94, center.y() - math.sin(angle) * radius * 0.94)
            color = QColor(229, 190, 133, 120 if i < 5 else 170)
            if i >= 5:
                color = QColor(221, 137, 114, 175)
            p.setPen(QPen(color, 0.7))
            p.drawLine(inner, outer)

        p.setPen(QPen(QColor(245, 206, 144, 105), 0.6))
        for i, text in enumerate(("-20", "0", "+3")):
            ratio = i / 2.0
            angle = math.radians(204.0 - ratio * 128.0)
            pos = QPointF(center.x() + math.cos(angle) * radius * 0.59, center.y() - math.sin(angle) * radius * 0.59)
            p.drawText(QRectF(pos.x() - 8.0, pos.y() - 4.0, 16.0, 8.0), Qt.AlignmentFlag.AlignCenter, text)

        needle_angle = math.radians(204.0 - max(0.0, min(1.0, level)) * 128.0)
        needle_end = QPointF(
            center.x() + math.cos(needle_angle) * radius * 0.82,
            center.y() - math.sin(needle_angle) * radius * 0.82,
        )
        p.setPen(QPen(QColor(239, 207, 150, 210), 1.1))
        p.drawLine(center, needle_end)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(12, 10, 11, 205))
        p.drawEllipse(center, 2.2, 2.2)

        p.setPen(QPen(QColor(247, 221, 190, 168), 0.8))
        p.drawText(panel.adjusted(0, 7, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)
        db = -20.0 + level * 24.0
        db_text = f"{db:+.1f}"
        p.setPen(QPen(QColor(238, 187, 151, 165), 0.7))
        p.drawText(panel.adjusted(0, 0, 0, -4), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom, db_text)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(178, 186, 202, 24), 0.8))
        p.setBrush(QColor(255, 255, 255, 4))
        p.drawRoundedRect(root, 6.0, 6.0)
        half = (root.width() - 4.0) / 2.0
        self._draw_meter(p, QRectF(root.left() + 2.0, root.top() + 2.0, half, root.height() - 4.0), "L", self._l)
        self._draw_meter(p, QRectF(root.left() + 2.0 + half + 2.0, root.top() + 2.0, half, root.height() - 4.0), "R", self._r)
        if self._clipped:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(198, 98, 88, 205))
            p.drawRoundedRect(QRectF(root.right() - 13.0, root.top() + 4.0, 8.0, 3.0), 1.5, 1.5)
        p.end()

class _SoundMixerPanSlider(QSlider):
    """Compact pan rail for mixer strips, drawn in the renewed audio theme."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setObjectName("SoundMixerPanSlider")
        self._accent = QColor(148, 126, 196, 170)
        self.setRange(-100, 100)
        self.setFixedSize(58, 18)
        self.setMouseTracking(True)

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self.update()

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
        accent = QColor(self._accent)
        hgrad.setColorAt(0.0, QColor(222, 226, 231, 232))
        hgrad.setColorAt(0.20, QColor(accent.red() + 28 if accent.red() < 220 else 232, accent.green() + 24 if accent.green() < 220 else 232, accent.blue() + 26 if accent.blue() < 220 else 232, 222))
        hgrad.setColorAt(0.60, QColor(accent.red(), accent.green(), accent.blue(), 206))
        hgrad.setColorAt(1.0, QColor(52, 58, 68, 240))
        p.setBrush(QBrush(hgrad))
        p.setPen(QPen(QColor(236, 231, 242, 124), 0.75))
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
        self._accent = QColor(151, 143, 104, 170) if self._master else QColor(148, 126, 196, 178)
        self.setObjectName("SoundMixerFader")
        self.setRange(0, 150)
        self.setFixedSize(28, 74)
        self.setMouseTracking(True)

    def set_accent_color(self, color: QColor) -> None:
        self._accent = QColor(color)
        self.update()

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
                grad.setColorAt(0.0, QColor(174, 160, 107, 166))
                grad.setColorAt(1.0, QColor(108, 136, 112, 210))
            else:
                grad.setColorAt(0.0, QColor(151, 131, 189, 164))
                grad.setColorAt(1.0, QColor(94, 140, 117, 208))
            p.setBrush(QBrush(grad))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(fill, 2.3, 2.3)

        handle = QRectF(cx - 12.0, handle_y - 7.0, 24.0, 14.0)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 168))
        p.drawRoundedRect(handle.translated(0, 1.7).adjusted(-1.0, 0, 1.0, 0.8), 4.0, 4.0)
        hgrad = QLinearGradient(handle.topLeft(), handle.bottomLeft())
        accent = QColor(self._accent)
        hgrad.setColorAt(0.0, QColor(226, 230, 234, 235))
        hgrad.setColorAt(0.18, QColor(min(255, accent.red() + 48), min(255, accent.green() + 46), min(255, accent.blue() + 44), 226))
        hgrad.setColorAt(0.52, QColor(accent.red(), accent.green(), accent.blue(), 222))
        hgrad.setColorAt(1.0, QColor(54, 61, 74, 242))
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
        led_color = QColor(accent.red(), accent.green(), accent.blue(), 155 if self.isEnabled() else 72)
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
        self._accent = QColor(148, 126, 196, 170)
        self.setObjectName("SoundMixerStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(74)
        self.setFixedHeight(226)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(3)

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
        self._type.setFixedSize(25, 15)
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
            button.setFixedSize(19, 14)
            button.toggled.connect(lambda checked, sid=slot_id: self._on_insert_toggled(sid, checked))
            self._insert_buttons[slot_id] = button
            inserts_layout.addWidget(button)
        root.addWidget(inserts)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)
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
        self._mute.setFixedSize(14, 15)
        self._mute.toggled.connect(self._on_mute_changed)
        buttons_layout.addWidget(self._mute)
        self._solo = QPushButton("S", buttons)
        self._solo.setObjectName("SoundMixerToggle")
        self._solo.setProperty("kind", "solo")
        self._solo.setCheckable(True)
        self._solo.setFixedSize(14, 15)
        self._solo.toggled.connect(self._on_solo_changed)
        buttons_layout.addWidget(self._solo)
        self._auto_read = QPushButton("R", buttons)
        self._auto_read.setObjectName("SoundMixerToggle")
        self._auto_read.setProperty("kind", "read")
        self._auto_read.setCheckable(True)
        self._auto_read.setFixedSize(14, 15)
        self._auto_read.toggled.connect(self._on_automation_changed)
        buttons_layout.addWidget(self._auto_read)
        self._auto_write = QPushButton("W", buttons)
        self._auto_write.setObjectName("SoundMixerToggle")
        self._auto_write.setProperty("kind", "write")
        self._auto_write.setCheckable(True)
        self._auto_write.setFixedSize(14, 15)
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
            button.setFixedSize(29, 15)
            button.clicked.connect(lambda _checked=False, sid=send_id: self._on_send_clicked(sid))
            self._send_buttons[send_id] = button
            sends_layout.addWidget(button)
        root.addWidget(sends)

        self._name = QLabel("", self)
        self._name.setObjectName("SoundMixerName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setFixedHeight(14)
        root.addWidget(self._name)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        accent = QColor(self._accent)
        p.setPen(Qt.PenStyle.NoPen)
        glow = QLinearGradient(root.left(), root.top(), root.right(), root.top())
        glow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 88))
        glow.setColorAt(0.26, QColor(accent.red(), accent.green(), accent.blue(), 32))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(QRectF(root.left() + 2.0, root.top() + 2.0, root.width() - 4.0, 16.0), 4.0, 4.0)
        p.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 135))
        p.drawRoundedRect(QRectF(root.left() + 3.0, root.top() + 4.0, 2.2, root.height() - 8.0), 1.1, 1.1)
        p.setPen(QPen(QColor(255, 255, 255, 18), 0.7))
        p.drawLine(QPointF(root.left() + 8.0, root.top() + 1.5), QPointF(root.right() - 8.0, root.top() + 1.5))
        p.end()

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
        self._accent = _mixer_type_color(track_type, alpha=178)
        self._pan.set_accent_color(_mixer_type_color(track_type, alpha=178))
        self._fader.set_accent_color(_mixer_type_color(track_type, alpha=188))
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
        self.setFixedWidth(128)
        self.setFixedHeight(226)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(2)

        title = QLabel("MASTER", self)
        title.setObjectName("SoundMixerTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(14)
        root.addWidget(title)

        bus = QLabel("mix bus", self)
        bus.setObjectName("SoundMixerName")
        bus.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bus.setFixedHeight(14)
        root.addWidget(bus)

        self._vu = _SoundMixerStereoVu(self)
        root.addWidget(self._vu, 0, Qt.AlignmentFlag.AlignHCenter)

        snap = QWidget(self)
        snap.setStyleSheet("background: transparent;")
        snap_layout = QHBoxLayout(snap)
        snap_layout.setContentsMargins(0, 0, 0, 0)
        snap_layout.setSpacing(3)
        self._snapshot_a = QLabel("S1", snap)
        self._snapshot_a.setObjectName("SoundMixerSnapshot")
        self._snapshot_a.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._snapshot_a.setFixedSize(27, 15)
        snap_layout.addWidget(self._snapshot_a)
        self._snapshot_b = QLabel("A/B", snap)
        self._snapshot_b.setObjectName("SoundMixerSnapshot")
        self._snapshot_b.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._snapshot_b.setFixedSize(30, 15)
        snap_layout.addWidget(self._snapshot_b)
        root.addWidget(snap)

        body = QWidget(self)
        body.setStyleSheet("background: transparent;")
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)
        body_layout.addStretch(1)
        self._meter = _SoundMixerMeter(body)
        body_layout.addWidget(self._meter)
        self._fader = _SoundMixerFader(body, master=True)
        self._fader.set_accent_color(QColor(174, 151, 104, 178))
        self._fader.setValue(100)
        self._fader.setEnabled(False)
        body_layout.addWidget(self._fader)
        body_layout.addStretch(1)
        root.addWidget(body)

        self._value = QLabel("0.00", self)
        self._value.setObjectName("SoundMixerValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setFixedHeight(12)
        root.addWidget(self._value)

        self._name = QLabel("master", self)
        self._name.setObjectName("SoundMixerName")
        self._name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name.setFixedHeight(24)
        root.addWidget(self._name)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        accent = QColor(174, 151, 104)
        glow = QLinearGradient(root.left(), root.top(), root.right(), root.top())
        glow.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 78))
        glow.setColorAt(0.34, QColor(118, 145, 123, 30))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawRoundedRect(QRectF(root.left() + 2.0, root.top() + 2.0, root.width() - 4.0, 18.0), 4.0, 4.0)
        p.setBrush(QColor(174, 151, 104, 122))
        p.drawRoundedRect(QRectF(root.left() + 3.0, root.top() + 4.0, 2.2, root.height() - 8.0), 1.1, 1.1)
        p.setPen(QPen(QColor(255, 255, 255, 22), 0.7))
        p.drawLine(QPointF(root.left() + 9.0, root.top() + 1.5), QPointF(root.right() - 9.0, root.top() + 1.5))
        p.end()

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
        self._vu.set_levels(level_l, level_r, clipped=clipped)
        peak = max(level_l, level_r)
        self._value.setText(f"{peak:.2f}")
        self._name.setText(f"{len(audible)}/{len(track_rows)} live")
