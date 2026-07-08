"""Workbench evidence cards and compact visual rows."""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.icons import app_icon, icon_size


def _format_ms(ms: int) -> str:
    if ms is None or ms < 0:
        ms = 0
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}.{(int(ms) % 1000) // 100}"


def _text_keyframe_count(actor: Any) -> int:
    raw_keys = getattr(actor, "keyframes", None)
    if not isinstance(raw_keys, dict):
        animation = getattr(actor, "animation", None)
        custom = getattr(animation, "custom_params", {}) if animation is not None else {}
        raw_keys = custom.get("action_keyframes") if isinstance(custom, dict) else {}
    if not isinstance(raw_keys, dict):
        return 0
    count = 0
    for series in raw_keys.values():
        if isinstance(series, dict):
            series = series.get("keyframes") or series.get("keys") or []
        if isinstance(series, (list, tuple)):
            count += len(series)
    return int(count)


class _AudioEvidenceCard(QWidget):
    """Compact real-state audio workspace rendered from the selected clip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._track = None
        self._clip = None
        self.setObjectName("AudioEvidenceCard")
        self.setMinimumHeight(178)
        self.setMaximumHeight(230)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_clip(self, track: Any, clip: Any) -> None:
        self._track = track
        self._clip = clip
        self.update()

    @staticmethod
    def _fmt_level(value: float) -> str:
        try:
            return f"{float(value):+.1f} dB"
        except Exception:
            return "+0.0 dB"

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QPointF, QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = self.rect().adjusted(1, 1, -1, -1)
        bg = QColor("#101010")
        card = QColor("#151515")
        line = QColor("#292929")
        text = QColor("#D9DDE2")
        muted = QColor("#8C929B")
        signal = QColor("#B8C5B4")
        signal_dim = QColor("#78857C")
        accent = QColor("#9BA6B6")

        p.fillRect(self.rect(), bg)
        p.setPen(QPen(line, 1))
        p.setBrush(card)
        p.drawRoundedRect(root, 7, 7)

        clip = self._clip
        track = self._track
        duration_ms = int(getattr(clip, "duration_ms", 0) or 0) if clip is not None else 0
        speed = float(getattr(clip, "speed", 1.0) or 1.0) if clip is not None else 1.0
        volume_db = float(getattr(track, "master_volume", 0.0) or 0.0) if track is not None else 0.0
        fade_in = int(getattr(clip, "fade_in_ms", 0) or 0) if clip is not None else 0
        fade_out = int(getattr(clip, "fade_out_ms", 0) or 0) if clip is not None else 0

        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(text)
        p.drawText(root.adjusted(10, 8, -10, -root.height() + 28), Qt.AlignmentFlag.AlignLeft, "Extracted Audio Workspace")

        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(muted)
        meta = f"{_format_ms(duration_ms)}  |  {self._fmt_level(volume_db)}  |  {speed:.2f}x"
        p.drawText(root.adjusted(10, 25, -10, -root.height() + 45), Qt.AlignmentFlag.AlignLeft, meta)

        chip_x = root.right() - 156
        for idx, label in enumerate(("linked", "stereo", "export")):
            chip = QRectF(chip_x + idx * 50, root.top() + 8, 44, 16)
            p.setPen(QPen(QColor("#34383D"), 1))
            p.setBrush(QColor(255, 255, 255, 7))
            p.drawRoundedRect(chip, 5, 5)
            p.setPen(QColor("#AEB5BE"))
            p.drawText(chip, Qt.AlignmentFlag.AlignCenter, label)

        wave_rect = QRectF(root.left() + 10, root.top() + 50, max(20, root.width() - 84), max(48, root.height() - 124))
        spec_rect = QRectF(root.left() + 10, root.bottom() - 58, max(20, root.width() - 84), 46)
        meter_rect = QRectF(root.right() - 54, root.top() + 50, 34, max(60, root.height() - 72))

        for rect, label in ((wave_rect, "waveform"), (spec_rect, "spectrum")):
            p.setPen(QPen(QColor("#24272B"), 1))
            p.setBrush(QColor("#111111"))
            p.drawRoundedRect(rect, 5, 5)
            p.setPen(QColor("#5F6670"))
            p.drawText(rect.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, label)

        wf = getattr(clip, "waveform", None) if clip is not None else None
        if wf is not None and getattr(wf, "size", 0):
            try:
                import numpy as np

                data = np.asarray(wf, dtype=np.float32)
                mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
                if mono.size:
                    samples = np.linspace(0, mono.size - 1, max(2, int(wave_rect.width())), dtype=np.int32)
                    vals = mono[samples]
                    peak = max(float(np.max(np.abs(vals))), 0.005)
                    mid = wave_rect.center().y() + 5
                    amp = max(8.0, wave_rect.height() * 0.35)
                    path = QPainterPath()
                    path.moveTo(QPointF(wave_rect.left() + 3, mid))
                    for i, val in enumerate(vals):
                        x = wave_rect.left() + 3 + i / max(len(vals) - 1, 1) * (wave_rect.width() - 6)
                        y = mid - float(val) / peak * amp
                        path.lineTo(QPointF(x, y))
                    p.setPen(QPen(signal, 1.0))
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(path)
                    p.setPen(QPen(QColor(255, 255, 255, 24), 0.75))
                    p.drawLine(int(wave_rect.left() + 4), int(mid), int(wave_rect.right() - 4), int(mid))
            except Exception:
                pass
        else:
            p.setPen(muted)
            p.drawText(wave_rect, Qt.AlignmentFlag.AlignCenter, "waveform pending")

        bins = getattr(clip, "spectrum_bins", None) if clip is not None else None
        try:
            import numpy as np

            if bins is None or not getattr(bins, "size", 0):
                if wf is not None and getattr(wf, "size", 0):
                    data = np.asarray(wf, dtype=np.float32)
                    mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
                    chunks = np.array_split(np.abs(mono), 32)
                    vals = np.asarray([float(c.mean()) if c.size else 0.0 for c in chunks], dtype=np.float32)
                    peak = max(float(vals.max()), 0.005)
                    vals = vals / peak
                else:
                    vals = np.zeros(32, dtype=np.float32)
            else:
                vals = np.asarray(bins, dtype=np.float32).ravel()[:32]
                peak = max(float(vals.max()), 0.005)
                vals = vals / peak
            bar_w = max(1.0, (spec_rect.width() - 12) / max(len(vals), 1))
            for i, val in enumerate(vals):
                h = float(val) * (spec_rect.height() - 18)
                x = spec_rect.left() + 6 + i * bar_w
                y = spec_rect.bottom() - 5 - h
                t = i / max(len(vals) - 1, 1)
                col = QColor(int(120 + 26 * t), int(137 + 21 * t), int(128 + 30 * t), 172)
                p.fillRect(QRectF(x, y, max(1.0, bar_w - 1), h), col)
        except Exception:
            pass

        p.setPen(QPen(QColor("#24272B"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(meter_rect, 5, 5)
        p.setPen(QColor("#6B727B"))
        p.drawText(meter_rect.adjusted(0, 5, 0, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "mix")
        meter_top = meter_rect.top() + 26
        meter_h = meter_rect.height() - 42
        level = 0.35
        if wf is not None and getattr(wf, "size", 0):
            try:
                import numpy as np

                data = np.asarray(wf, dtype=np.float32)
                level = min(1.0, max(0.08, float(np.sqrt(np.mean(data * data))) * 2.6))
            except Exception:
                pass
        for idx, label in enumerate(("L", "R")):
            x = meter_rect.left() + 8 + idx * 10
            p.fillRect(QRectF(x, meter_top, 5, meter_h), QColor("#1D1F20"))
            fill_h = meter_h * level * (1.0 if idx == 0 else 0.92)
            grad = QLinearGradient(x, meter_top + meter_h, x, meter_top)
            grad.setColorAt(0.0, signal_dim)
            grad.setColorAt(1.0, signal)
            p.fillRect(QRectF(x, meter_top + meter_h - fill_h, 5, fill_h), grad)
            p.setPen(QColor("#7A818A"))
            p.drawText(QRectF(x - 2, meter_rect.bottom() - 17, 10, 10), Qt.AlignmentFlag.AlignCenter, label)

        if duration_ms > 0 and (fade_in > 0 or fade_out > 0):
            p.setPen(QPen(accent, 1))
            if fade_in > 0:
                fx = wave_rect.left() + min(1.0, fade_in / duration_ms) * wave_rect.width()
                p.drawLine(int(fx), int(wave_rect.top() + 18), int(fx), int(wave_rect.bottom() - 4))
            if fade_out > 0:
                fx = wave_rect.right() - min(1.0, fade_out / duration_ms) * wave_rect.width()
                p.drawLine(int(fx), int(wave_rect.top() + 18), int(fx), int(wave_rect.bottom() - 4))

        p.end()


class _TypographyEvidenceCard(QWidget):
    """Compact real-state card for text actors attached to the selected clip."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._actors: list[Any] = []
        self.setObjectName("TypographyEvidenceCard")
        self.setMinimumHeight(132)
        self.setMaximumHeight(170)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_actors(self, actors: list[Any]) -> None:
        self._actors = list(actors or [])
        self.update()

    @staticmethod
    def _key_series(actor: Any, channel: str) -> list[dict[str, Any]]:
        raw_keys = getattr(actor, "keyframes", None)
        if not isinstance(raw_keys, dict):
            animation = getattr(actor, "animation", None)
            custom = getattr(animation, "custom_params", {}) if animation is not None else {}
            raw_keys = custom.get("action_keyframes") if isinstance(custom, dict) else {}
        series = raw_keys.get(channel, []) if isinstance(raw_keys, dict) else []
        if isinstance(series, dict):
            series = series.get("keyframes") or series.get("keys") or []
        return [row for row in series if isinstance(row, dict)] if isinstance(series, (list, tuple)) else []

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QPoint, QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygon

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(self.rect(), QColor("#101010"))
        p.setPen(QPen(QColor("#292929"), 1))
        p.setBrush(QColor("#151515"))
        p.drawRoundedRect(root, 7, 7)

        actor = self._actors[0] if self._actors else None
        title = str(getattr(actor, "text", "") or "Typography") if actor is not None else "Typography"
        key_count = _text_keyframe_count(actor) if actor is not None else 0
        duration = (
            int(getattr(actor, "end_ms", 0) or 0) - int(getattr(actor, "start_ms", 0) or 0)
            if actor is not None
            else 0
        )
        style = getattr(actor, "style", None)

        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#F2F0EA"))
        p.drawText(root.adjusted(10, 8, -10, -root.height() + 28), Qt.AlignmentFlag.AlignLeft, "Typography Workspace")

        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#8F95A0"))
        meta = f"{_format_ms(duration)}  |  {key_count} keys"
        if style is not None:
            meta = f"{meta}  |  {int(getattr(style, 'font_size', 0) or 0)} px"
        p.drawText(root.adjusted(10, 25, -10, -root.height() + 45), Qt.AlignmentFlag.AlignLeft, meta)

        chip = QRectF(root.right() - 118, root.top() + 8, 98, 17)
        grad = QLinearGradient(chip.left(), chip.top(), chip.right(), chip.bottom())
        grad.setColorAt(0.0, QColor(86, 80, 94, 190))
        grad.setColorAt(1.0, QColor(65, 72, 86, 175))
        p.setPen(QPen(QColor("#807B88"), 1))
        p.setBrush(grad)
        p.drawRoundedRect(chip, 5, 5)
        p.setPen(QColor("#F4F0EA"))
        p.drawText(chip.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title[:16])

        text_rect = QRectF(root.left() + 10, root.top() + 48, root.width() - 20, 26)
        p.setPen(QPen(QColor("#24272B"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(text_rect, 5, 5)
        font.setPixelSize(13)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#F8FAFC"))
        p.drawText(text_rect.adjusted(9, 0, -9, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)

        lane_top = int(root.top() + 84)
        channels = (("opacity", "#D8C89E"), ("scale", "#9EA7B7"), ("position_y", "#A9B8AD"))
        span = max(1, int(duration))
        start_ms = int(getattr(actor, "start_ms", 0) or 0) if actor is not None else 0
        for idx, (channel, color) in enumerate(channels):
            y = lane_top + idx * 18
            label_rect = QRectF(root.left() + 10, y - 5, 58, 13)
            rail = QRectF(root.left() + 72, y, root.width() - 94, 2)
            font.setPixelSize(8)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor("#8F95A0"))
            p.drawText(label_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, channel.replace("_", " "))
            p.setPen(QPen(QColor("#303236"), 1))
            p.drawLine(int(rail.left()), int(rail.center().y()), int(rail.right()), int(rail.center().y()))
            p.setPen(QPen(QColor(20, 20, 24, 150), 1))
            p.setBrush(QColor(color))
            for key in self._key_series(actor, channel):
                try:
                    raw_time = int(round(float(key.get("time_ms", key.get("ms", 0)))))
                except Exception:
                    continue
                rel = raw_time - start_ms if start_ms <= raw_time <= start_ms + span else raw_time
                rel = max(0, min(span, rel))
                x = int(rail.left() + (rel / span) * max(1, rail.width()))
                p.drawPolygon(QPolygon([
                    QPoint(x, y - 4),
                    QPoint(x + 4, y),
                    QPoint(x, y + 4),
                    QPoint(x - 4, y),
                ]))
        p.end()


class _EditPointEvidenceCard(QWidget):
    """Compact real-state card for timeline cuts and adjacent edit points."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._track = None
        self._clip = None
        self._previous_clip = None
        self._next_clip = None
        self.setObjectName("EditPointEvidenceCard")
        self.setMinimumHeight(138)
        self.setMaximumHeight(164)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_context(self, track: Any, clip: Any) -> None:
        self._track = track
        self._clip = clip
        self._previous_clip = None
        self._next_clip = None
        clips = sorted(
            list(getattr(track, "clips", []) or []),
            key=lambda row: int(getattr(row, "timeline_in_ms", 0) or 0),
        )
        try:
            selected_id = int(getattr(clip, "id", -1) or -1)
        except Exception:
            selected_id = -1
        for index, candidate in enumerate(clips):
            if int(getattr(candidate, "id", -2) or -2) != selected_id:
                continue
            if index > 0:
                self._previous_clip = clips[index - 1]
            if index + 1 < len(clips):
                self._next_clip = clips[index + 1]
            break
        self.update()

    @staticmethod
    def has_edit_point(track: Any, clip: Any) -> bool:
        if track is None or clip is None:
            return False
        clips = sorted(
            list(getattr(track, "clips", []) or []),
            key=lambda row: int(getattr(row, "timeline_in_ms", 0) or 0),
        )
        if len(clips) < 2:
            return False
        selected_id = int(getattr(clip, "id", -1) or -1)
        for index, candidate in enumerate(clips):
            if int(getattr(candidate, "id", -2) or -2) != selected_id:
                continue
            if index > 0:
                prev = clips[index - 1]
                if abs(int(getattr(prev, "timeline_out_ms", 0) or 0) - int(getattr(candidate, "timeline_in_ms", 0) or 0)) <= 1:
                    return True
            if index + 1 < len(clips):
                nxt = clips[index + 1]
                if abs(int(getattr(candidate, "timeline_out_ms", 0) or 0) - int(getattr(nxt, "timeline_in_ms", 0) or 0)) <= 1:
                    return True
        return False

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QPoint, QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygon

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = self.rect().adjusted(1, 1, -1, -1)
        p.fillRect(self.rect(), QColor("#101010"))
        p.setPen(QPen(QColor("#2A2A2A"), 1))
        p.setBrush(QColor("#151515"))
        p.drawRoundedRect(root, 7, 7)

        clip = self._clip
        prev_clip = self._previous_clip
        next_clip = self._next_clip
        cut_ms = int(getattr(clip, "timeline_in_ms", 0) or 0)
        if prev_clip is not None:
            cut_ms = int(getattr(prev_clip, "timeline_out_ms", cut_ms) or cut_ms)
        transition_source = prev_clip if prev_clip is not None else clip
        ttype = str(getattr(transition_source, "transition_out_type", "") or "")
        tms = int(getattr(transition_source, "transition_out_ms", 0) or 0) if ttype else 0

        font = p.font()
        font.setPixelSize(10)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#F0EEE8"))
        p.drawText(root.adjusted(10, 7, -10, -root.height() + 25), Qt.AlignmentFlag.AlignLeft, "Edit Point Workspace")

        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#8F95A0"))
        meta = f"cut {_format_ms(cut_ms)}"
        if ttype:
            meta = f"{meta}  |  {ttype} {_format_ms(tms)}"
        p.drawText(root.adjusted(10, 24, -10, -root.height() + 41), Qt.AlignmentFlag.AlignLeft, meta)

        rail = QRectF(root.left() + 10, root.top() + 50, root.width() - 20, 43)
        p.setPen(QPen(QColor("#2A2D31"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(rail, 5, 5)
        half = rail.width() * 0.5
        left_rect = QRectF(rail.left() + 5, rail.top() + 7, max(12.0, half - 9), 18)
        right_rect = QRectF(rail.left() + half + 4, rail.top() + 7, max(12.0, half - 9), 18)
        for rect, selected, label, source_clip in (
            (left_rect, prev_clip is None and clip is not None, "A", prev_clip or clip),
            (right_rect, prev_clip is not None and clip is not None, "B", clip if prev_clip is not None else next_clip),
        ):
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            if selected:
                grad.setColorAt(0.0, QColor(86, 90, 96, 128))
                grad.setColorAt(1.0, QColor(56, 61, 66, 126))
                border = QColor("#B8BEC7")
            else:
                grad.setColorAt(0.0, QColor(54, 58, 63, 94))
                grad.setColorAt(1.0, QColor(38, 42, 47, 92))
                border = QColor("#555A62")
            p.setPen(QPen(border, 1))
            p.setBrush(grad)
            p.drawRoundedRect(rect, 3, 3)
            p.setPen(QColor("#DCE1E8"))
            p.drawText(rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            if source_clip is not None:
                dur = max(
                    0,
                    int(getattr(source_clip, "timeline_out_ms", 0) or 0)
                    - int(getattr(source_clip, "timeline_in_ms", 0) or 0),
                )
                font.setPixelSize(7)
                font.setBold(False)
                p.setFont(font)
                p.setPen(QColor("#8F95A0"))
                p.drawText(rect.adjusted(20, 0, -6, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, _format_ms(dur))
                font.setPixelSize(8)
                font.setBold(False)
                p.setFont(font)

        x = int(rail.left() + half)
        p.setPen(QPen(QColor("#D8C89E"), 1))
        p.drawLine(x, int(rail.top() + 2), x, int(rail.bottom() - 2))
        p.setBrush(QColor("#D8C89E"))
        p.setPen(QPen(QColor(18, 18, 18, 150), 1))
        p.drawPolygon(QPolygon([
            QPoint(x - 4, int(rail.top() + 4)),
            QPoint(x + 4, int(rail.top() + 4)),
            QPoint(x, int(rail.top() + 10)),
        ]))
        p.drawPolygon(QPolygon([
            QPoint(x - 4, int(rail.bottom() - 4)),
            QPoint(x + 4, int(rail.bottom() - 4)),
            QPoint(x, int(rail.bottom() - 10)),
        ]))
        if ttype:
            t_rect = QRectF(x - 26, rail.top() + 7, 52, rail.height() - 14)
            p.setPen(QPen(QColor("#7A725F"), 1))
            p.setBrush(QColor(216, 200, 158, 38))
            p.drawRoundedRect(t_rect, 3, 3)
            font.setPixelSize(7)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor("#E5D8B8"))
            p.drawText(t_rect, Qt.AlignmentFlag.AlignCenter, "TR")

        trim_y = rail.top() + 29
        label_font = p.font()
        label_font.setPixelSize(7)
        label_font.setBold(False)
        p.setFont(label_font)
        for rect, label, active in (
            (QRectF(rail.left() + 7, trim_y, half - 15, 8), "trim out", prev_clip is not None),
            (QRectF(rail.left() + half + 8, trim_y, half - 15, 8), "trim in", clip is not None),
        ):
            p.setPen(QPen(QColor("#35383D"), 1))
            p.drawLine(int(rect.left()), int(rect.center().y()), int(rect.right()), int(rect.center().y()))
            p.setBrush(QColor("#D8C89E") if active else QColor("#555A62"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(rect.center().x() - 2, rect.center().y() - 2, 4, 4))
            p.setPen(QColor("#8F95A0"))
            p.drawText(rect.adjusted(0, -9, 0, 0), Qt.AlignmentFlag.AlignCenter, label)

        footer = QRectF(root.left() + 10, root.bottom() - 28, root.width() - 20, 17)
        p.setPen(QPen(QColor("#292929"), 1))
        p.setBrush(QColor("#111111"))
        p.drawRoundedRect(footer, 4, 4)
        font.setPixelSize(8)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor("#AAB1C1"))
        footer_text = "selected side B" if prev_clip is not None else "selected side A"
        if ttype:
            footer_text += "   |   transition handle active"
        p.drawText(footer.adjusted(7, 0, -7, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, footer_text)

        p.end()


class _FxStackRail(QWidget):
    """Small real-state rail for the selected clip's FX/transition stack."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._state: dict[str, Any] = {}
        self.setObjectName("FxStackRail")
        self.setFixedHeight(32)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

    def set_state(self, **state: Any) -> None:
        self._state = dict(state)
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1, 0, -1, -1)

        state = self._state
        nodes = [
            ("SRC", True, "#717982"),
            ("FX", bool(state.get("has_clip_fx")), "#7C776B"),
            ("TR", bool(state.get("has_transition")), "#847B68"),
            ("GRAPH", bool(state.get("has_vfx_graph")), "#707782"),
            ("OUT", True, "#717982"),
        ]
        count = len(nodes)
        left = root.left() + 2
        top = root.top() + 4
        width = max(27.0, min(64.0, (root.width() - 4 - (count - 1) * 6) / count))
        center_y = top + 8
        p.setPen(QPen(QColor(132, 138, 148, 40), 1))
        p.drawLine(int(left + width * 0.5), int(center_y), int(left + (width + 6) * (count - 1) + width * 0.5), int(center_y))
        rects: list[QRectF] = []
        for index, (_label, active, color) in enumerate(nodes):
            r = QRectF(left + index * (width + 6), top, width, 16)
            rects.append(r)
            grad = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
            if active:
                base = QColor(color)
                grad.setColorAt(0.0, QColor(base.red(), base.green(), base.blue(), 82))
                grad.setColorAt(1.0, QColor(34, 36, 39, 118))
                border = QColor(176, 183, 193, 68)
                text = QColor("#E7EAF0")
            else:
                grad.setColorAt(0.0, QColor(38, 41, 45, 62))
                grad.setColorAt(1.0, QColor(25, 27, 30, 68))
                border = QColor(76, 81, 88, 36)
                text = QColor("#747A83")
            p.setPen(QPen(border, 1))
            p.setBrush(grad)
            p.drawRoundedRect(r, 4, 4)
            if active:
                p.setPen(QPen(QColor(220, 225, 236, 44), 1))
                p.drawLine(int(r.left() + 5), int(r.top() + 2), int(r.right() - 5), int(r.top() + 2))
            font = p.font()
            font.setPixelSize(8)
            font.setBold(True)
            p.setFont(font)
            p.setPen(text)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, _label)

        footer = str(state.get("footer") or "")
        if footer:
            font = p.font()
            font.setPixelSize(7)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor("#8F95A0"))
            p.drawText(
                QRectF(root.left() + 4, root.bottom() - 9, root.width() - 8, 8),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                footer,
            )
        p.end()


class _NodeRow(QWidget):
    """Single clickable row in the workbench's NodeGraph section.

    Phase 2 of the Media Editor Pro plan introduced ``track.node_graph``
    as a per-track effects DAG; today there's only a Color node, but
    LUT / Blur / TrackMatte will land in later phases. The row shows
    an icon + name + status badge and emits ``clicked(kind)`` so the
    editor can route focus to the matching panel."""

    clicked = Signal(str)

    def __init__(self, kind: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self._kind = kind
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(28)
        self.setStyleSheet(
            "QWidget { background-color: #171A25; border:1px solid #2A2E3C; border-radius: 8px; }"
            "QWidget:hover { background-color: #222635; border-color:#555A70; }"
        )
        h = QHBoxLayout(self)
        h.setContentsMargins(8, 0, 8, 0)
        h.setSpacing(8)
        self._icon = QLabel("", self)
        self._icon.setFixedSize(18, 18)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setPixmap(app_icon({"color": "color"}.get(kind, "target"), size=15).pixmap(icon_size(15)))
        h.addWidget(self._icon)
        self._label = QLabel(label, self)
        self._label.setStyleSheet(
            "color: #F2F0EA; font-size: 11px; font-weight: 700;"
        )
        h.addWidget(self._label)
        h.addStretch(1)
        self._status = QLabel("", self)
        self._status.setStyleSheet("color: #8F95A8; font-size: 10px;")
        h.addWidget(self._status)

    def set_status(self, text: str, accent: bool = False) -> None:
        self._status.setText(text)
        if accent:
            self._status.setStyleSheet(
                "color: #E85D35; font-size: 10px; font-weight: 700;"
            )
        else:
            self._status.setStyleSheet("color: #8F95A8; font-size: 10px;")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._kind)
            return
        super().mousePressEvent(event)

