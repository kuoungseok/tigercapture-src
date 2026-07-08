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

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
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
from app.sound_editor_mixer_widgets import (
    _SoundMixerMasterStrip,
    _SoundMixerStrip,
    _mixer_insert_slots,
    _mixer_sends,
)
from app.sound_editor_visual_widgets import (
    _MiniSoundGraph,
    _MiniSpectrumStrip,
    _MiniWaveformStrip,
    _SoundJogShuttle05,
)
from app.studio_slider import StudioSlider
from app.style import FONT_FAMILY, editor_scrollbar_qss


def _fmt_ms(ms: int | float | None) -> str:
    try:
        value = max(0, int(ms or 0))
    except Exception:
        value = 0
    s = value // 1000
    return f"{s // 60}:{s % 60:02d}"


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


class _MusicLabArrangementView(QWidget):
    """Compact multitrack arranger preview for Music Lab."""

    selection_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SoundMusicArrangementView")
        self.setMinimumHeight(275)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._duration_s = 30
        self._mode = "stems"
        self._key = "auto key"
        self._genre = "electronic"
        self._mood = "confident"
        self._composition: dict[str, Any] | None = None
        self._selection: dict[str, Any] = {"role": "drums", "section_name": "main"}
        self._block_rects: list[tuple[QRectF, str, str]] = []
        self._muted_roles: set[str] = set()
        self._solo_roles: set[str] = set()

    def set_arrangement(
        self,
        *,
        duration_s: int,
        mode: str,
        key: str,
        genre: str,
        mood: str,
    ) -> None:
        self._duration_s = max(4, min(180, int(duration_s or 30)))
        self._mode = str(mode or "stems")
        self._key = str(key or "auto key")
        self._genre = str(genre or "")
        self._mood = str(mood or "")
        self.update()

    def set_composition(self, composition: dict[str, Any] | None) -> None:
        self._composition = dict(composition or {}) if isinstance(composition, dict) else None
        if self._composition:
            self._duration_s = max(4, int(round(float(self._composition.get("duration_ms") or 30000) / 1000.0)))
            self._key = str(self._composition.get("key") or self._key)
            self._genre = str(self._composition.get("genre") or self._genre)
            self._mood = str(self._composition.get("mood") or self._mood)
        valid_sections = [row[0] for row in self._sections()]
        valid_roles = ["chords" if row[0].lower() == "pad" else row[0].lower() for row in self._tracks()]
        if self._selection.get("section_name") not in valid_sections:
            self._selection["section_name"] = valid_sections[0] if valid_sections else "main"
        if self._selection.get("role") not in valid_roles:
            self._selection["role"] = valid_roles[0] if valid_roles else "drums"
        self.update()

    def composition(self) -> dict[str, Any] | None:
        return dict(self._composition or {}) if self._composition else None

    def selection(self) -> dict[str, Any]:
        row = dict(self._selection)
        if self._composition:
            row["composition_id"] = str(self._composition.get("id") or "")
        row["muted_roles"] = sorted(self._muted_roles)
        row["solo_roles"] = sorted(self._solo_roles)
        return row

    def set_selection(self, *, role: str = "", section_name: str = "") -> None:
        if role:
            self._selection["role"] = str(role).strip().lower()
        if section_name:
            self._selection["section_name"] = str(section_name).strip().lower()
        self.update()
        self.selection_changed.emit(self.selection())

    def set_role_muted(self, role: str, muted: bool) -> None:
        role_text = str(role or "").strip().lower()
        if not role_text:
            return
        if muted:
            self._muted_roles.add(role_text)
        else:
            self._muted_roles.discard(role_text)
        self.update()
        self.selection_changed.emit(self.selection())

    def set_role_solo(self, role: str, solo: bool) -> None:
        role_text = str(role or "").strip().lower()
        if not role_text:
            return
        if solo:
            self._solo_roles.add(role_text)
        else:
            self._solo_roles.discard(role_text)
        self.update()
        self.selection_changed.emit(self.selection())

    def _sections(self) -> list[tuple[str, float, QColor]]:
        composition = self._composition or {}
        section_rows = [row for row in list(composition.get("sections") or []) if isinstance(row, dict)]
        if section_rows:
            total = sum(max(1.0, float(row.get("duration_ms") or 0)) for row in section_rows)
            colors = {
                "intro": QColor(175, 145, 92, 210),
                "build": QColor(190, 162, 78, 220),
                "main": QColor(214, 177, 58, 230),
                "outro": QColor(138, 151, 177, 210),
            }
            return [
                (
                    str(row.get("name") or f"section {idx + 1}").lower(),
                    max(1.0, float(row.get("duration_ms") or 0)) / max(1.0, total),
                    colors.get(str(row.get("name") or "").lower(), QColor(138, 151, 177, 210)),
                )
                for idx, row in enumerate(section_rows)
            ]
        if self._duration_s <= 16:
            rows = (("intro", 0.25), ("main", 0.55), ("outro", 0.20))
        else:
            rows = (("intro", 0.18), ("build", 0.27), ("main", 0.38), ("outro", 0.17))
        colors = {
            "intro": QColor(175, 145, 92, 210),
            "build": QColor(190, 162, 78, 220),
            "main": QColor(214, 177, 58, 230),
            "outro": QColor(138, 151, 177, 210),
        }
        return [(name, ratio, colors[name]) for name, ratio in rows]

    def _tracks(self) -> list[tuple[str, QColor, int]]:
        mode = self._mode.lower()
        base_tracks = [
            ("Drums", QColor(216, 176, 49), 0),
            ("Bass", QColor(81, 122, 221), 1),
            ("Pad", QColor(48, 190, 189), 2),
            ("Melody", QColor(44, 160, 208), 3),
            ("FX", QColor(114, 151, 221), 4),
        ]
        composition = self._composition or {}
        comp_tracks = [row for row in list(composition.get("tracks") or []) if isinstance(row, dict)]
        if comp_tracks:
            palette = {
                "drums": (QColor(216, 176, 49), 0),
                "bass": (QColor(81, 122, 221), 1),
                "chords": (QColor(48, 190, 189), 2),
                "pad": (QColor(48, 190, 189), 2),
                "melody": (QColor(44, 160, 208), 3),
                "fx": (QColor(114, 151, 221), 4),
                "mix": (QColor(118, 196, 143), 5),
            }
            tracks = []
            for row in comp_tracks:
                role = str(row.get("role") or row.get("id") or "").strip().lower()
                color, index = palette.get(role, (QColor(138, 151, 177), 5))
                label = "Pad" if role == "chords" else (role.title() or "Track")
                tracks.append((label, color, index))
        else:
            tracks = base_tracks
        if mode == "drums + bass":
            return [row for row in tracks if row[0].lower() in {"drums", "bass"}]
        if mode == "pad only":
            return [row for row in tracks if row[0].lower() in {"pad", "chords"}] or [base_tracks[2]]
        if mode == "mix only":
            return [("Mix", QColor(118, 196, 143), 5)]
        return tracks

    def _track_data(self, role_label: str) -> dict[str, Any]:
        role = "chords" if role_label.lower() == "pad" else role_label.lower()
        for row in list((self._composition or {}).get("tracks") or []):
            if isinstance(row, dict) and str(row.get("role") or row.get("id") or "").lower() == role:
                return row
        return {}

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(rect, QColor("#0C0E10"))
        painter.setPen(QPen(QColor(178, 186, 202, 28), 1))
        painter.drawRoundedRect(QRectF(rect), 6, 6)

        left_w = 94
        top_h = 28
        bottom_pad = 12
        lane_gap = 4
        lanes = self._tracks()
        lane_h = max(24, int((rect.height() - top_h - bottom_pad - lane_gap * (len(lanes) - 1)) / max(1, len(lanes))))
        grid_x = rect.left() + left_w
        grid_w = max(1, rect.width() - left_w - 7)
        grid_y = rect.top() + top_h
        grid_h = lane_h * len(lanes) + lane_gap * max(0, len(lanes) - 1)

        painter.fillRect(QRectF(grid_x, grid_y, grid_w, grid_h), QColor(18, 21, 24, 220))
        painter.fillRect(QRectF(rect.left() + 5, grid_y, left_w - 8, grid_h), QColor(14, 16, 18, 235))

        title_font = painter.font()
        title_font.setPixelSize(9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QColor("#C8CED8"))
        painter.drawText(rect.left() + 8, rect.top() + 18, "Music Lab Arrange")

        info_font = painter.font()
        info_font.setPixelSize(8)
        info_font.setBold(False)
        painter.setFont(info_font)
        painter.setPen(QColor("#7F8793"))
        painter.drawText(grid_x + 4, rect.top() + 18, f"{self._duration_s}s  |  {self._genre}  |  {self._mood}  |  {self._key}")

        bars = max(8, min(48, int(round(self._duration_s / 2))))
        for i in range(bars + 1):
            x = grid_x + grid_w * i / bars
            alpha = 62 if i % 4 == 0 else 30
            painter.setPen(QPen(QColor(178, 186, 202, alpha), 1))
            painter.drawLine(int(x), grid_y, int(x), grid_y + grid_h)
            if i % 4 == 0:
                painter.setPen(QColor("#6D7581"))
                painter.drawText(int(x) + 3, rect.top() + 18, str(i + 1))

        y = grid_y
        self._block_rects = []
        for track_index, (name, color, role_index) in enumerate(lanes):
            lane_rect = QRectF(grid_x, y, grid_w, lane_h)
            label_rect = QRectF(rect.left() + 7, y, left_w - 12, lane_h)
            role_name = "chords" if name.lower() == "pad" else name.lower()
            muted = role_name in self._muted_roles
            soloed = role_name in self._solo_roles
            painter.fillRect(label_rect, QColor(16, 18, 20, 170 if muted else 230))
            painter.setPen(QPen(QColor(178, 186, 202, 26), 1))
            painter.drawRect(label_rect)
            painter.setPen(QColor("#F1E8C8") if soloed else QColor("#7E8793") if muted else QColor("#DDE2EA"))
            suffix = " S" if soloed else " M" if muted else ""
            painter.drawText(label_rect.adjusted(8, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, f"{name}{suffix}")
            painter.fillRect(lane_rect, QColor(13, 15, 17, 230))
            painter.setPen(QPen(QColor(178, 186, 202, 18), 1))
            painter.drawRect(lane_rect)
            self._paint_track_blocks(painter, lane_rect, color, role_index, track_index, role_name, muted=muted)
            y += lane_h + lane_gap
        painter.end()

    def _paint_track_blocks(
        self,
        painter: QPainter,
        lane_rect: QRectF,
        color: QColor,
        role_index: int,
        track_index: int,
        role_name: str,
        *,
        muted: bool = False,
    ) -> None:
        start_ratio = 0.0
        track_data = self._track_data(role_name)
        clips = [row for row in list(track_data.get("clips") or []) if isinstance(row, dict)]
        for section_index, (section, ratio, section_color) in enumerate(self._sections()):
            block_x = lane_rect.left() + lane_rect.width() * start_ratio
            block_w = max(12.0, lane_rect.width() * ratio - 3.0)
            if clips:
                active = any(str(clip.get("section_name") or "").lower() == section for clip in clips)
            else:
                active = not (section == "intro" and role_index in {3, 4}) and not (section == "outro" and role_index == 0)
            if active:
                block_h = lane_rect.height() - 9
                block_y = lane_rect.top() + 4
                block_rect = QRectF(block_x + 2, block_y, block_w, block_h)
                self._block_rects.append((QRectF(block_rect), role_name, section))
                mixed = QColor(
                    int(color.red() * 0.70 + section_color.red() * 0.30),
                    int(color.green() * 0.70 + section_color.green() * 0.30),
                    int(color.blue() * 0.70 + section_color.blue() * 0.30),
                    118 if muted else 220,
                )
                gradient = QLinearGradient(block_x, block_y, block_x, block_y + block_h)
                gradient.setColorAt(0.0, mixed.lighter(118))
                gradient.setColorAt(1.0, mixed.darker(132))
                path = QPainterPath()
                path.addRoundedRect(block_rect, 3, 3)
                painter.fillPath(path, QBrush(gradient))
                selected = self._selection.get("role") == role_name and self._selection.get("section_name") == section
                painter.setPen(QPen(QColor("#F3E8C5") if selected else mixed.lighter(130), 2 if selected else 1))
                painter.drawPath(path)
                note_count = 0
                if clips:
                    for clip in clips:
                        if str(clip.get("section_name") or "").lower() == section:
                            note_count += len(list(clip.get("notes") or []))
                self._paint_note_pattern(painter, QRectF(block_x + 6, block_y + 5, block_w - 10, block_h - 10), role_index, section_index, note_count=note_count)
            start_ratio += ratio

    def _paint_note_pattern(self, painter: QPainter, rect: QRectF, role_index: int, section_index: int, *, note_count: int = 0) -> None:
        if rect.width() <= 4 or rect.height() <= 4:
            return
        painter.setPen(QPen(QColor(6, 10, 13, 125), 1))
        if role_index == 0:
            steps = max(3, min(36, note_count or int(rect.width() // 13)))
            for i in range(steps):
                x = rect.left() + i * rect.width() / steps
                h = rect.height() * (0.45 + 0.35 * ((i + section_index) % 3 == 0))
                painter.drawLine(int(x), int(rect.bottom()), int(x), int(rect.bottom() - h))
        elif role_index == 1:
            y = rect.center().y()
            painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
            for i in range(4):
                x = rect.left() + i * rect.width() / 4
                painter.drawLine(int(x), int(y), int(x + rect.width() / 7), int(y - rect.height() * 0.18))
        elif role_index in {2, 5}:
            for offset in (0.25, 0.50, 0.75):
                y = rect.top() + rect.height() * offset
                painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        elif role_index == 3:
            points = []
            for i in range(7):
                x = rect.left() + i * rect.width() / 6
                y = rect.bottom() - rect.height() * (0.20 + 0.55 * ((i + section_index) % 4) / 3)
                points.append((x, y))
            for a, b in zip(points, points[1:]):
                painter.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
        else:
            painter.drawEllipse(QRectF(rect.left(), rect.top(), rect.height() * 0.75, rect.height() * 0.75))
            painter.drawLine(int(rect.left()), int(rect.center().y()), int(rect.right()), int(rect.center().y()))

    def mousePressEvent(self, event) -> None:  # pragma: no cover - exercised by widget tests
        pos = event.position() if hasattr(event, "position") else event.pos()
        for rect, role, section in reversed(self._block_rects):
            if rect.contains(pos):
                self.set_selection(role=role, section_name=section)
                return
        super().mousePressEvent(event)

    def wheelEvent(self, event) -> None:  # pragma: no cover - UI convenience
        selection = self.selection()
        role = str(selection.get("role") or "")
        if role:
            if event.angleDelta().y() < 0:
                self.set_role_muted(role, role not in self._muted_roles)
            else:
                self.set_role_solo(role, role not in self._solo_roles)
        event.accept()


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
    music_lab_action_requested = Signal(str, object)
    music_lab_selection_changed = Signal(object)
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
        self._music_composition: dict[str, Any] | None = None
        self._music_selection: dict[str, Any] = {"role": "drums", "section_name": "main"}
        self._music_preview_player: Any = None
        self._music_preview_output: Any = None
        self._music_preview_loaded_path = ""
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
            ("music", "Music Lab", "audio"),
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
            ("music", "Music"),
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
        self._stack.addWidget(self._scroll_page(self._build_music_lab_page()))
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
            "QLineEdit#SoundLineEdit, QSpinBox#SoundSpinBox {"
            "background:rgba(255,255,255,5); color:#D7DAE7; border:1px solid rgba(178,186,202,24);"
            "border-radius:5px; padding:3px 7px; font-size:9px; min-height:18px;"
            "}"
            "QLineEdit#SoundLineEdit:hover, QSpinBox#SoundSpinBox:hover {"
            "background:rgba(255,255,255,10); border-color:rgba(220,225,238,62);"
            "}"
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
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(167,154,198,32), stop:1 rgba(72,66,92,36));"
            "color:#D6D1E5; border:1px solid rgba(167,154,198,80);"
            "border-radius:4px; font-size:8px; font-weight:800; padding:0px;"
            "}"
            "QPushButton#SoundMixerType:hover { background:rgba(167,154,198,42); color:#F1EDF8; }"
            "QPushButton#SoundMixerInsert {"
            "background:rgba(255,255,255,4); color:#69727D; border:1px solid rgba(178,186,202,20);"
            "border-radius:3px; font-size:8px; font-weight:760; padding:0px;"
            "}"
            "QPushButton#SoundMixerInsert:checked {"
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 rgba(156,139,196,38), stop:1 rgba(80,94,88,34));"
            "color:#E3DFEE; border-color:rgba(178,166,214,96);"
            "}"
            "QPushButton#SoundMixerInsert:hover, QPushButton#SoundMixerSend:hover {"
            "background:rgba(255,255,255,10); color:#E5EAF0; border-color:rgba(220,225,238,58);"
            "}"
            "QPushButton#SoundMixerSend {"
            "background:rgba(255,255,255,4); color:#98A1AD; border:1px solid rgba(178,186,202,24);"
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

    def _build_music_lab_page(self) -> QWidget:
        page = QWidget(self)
        page.setObjectName("SoundMusicLabPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(6, 5, 6, 7)
        layout.setSpacing(6)

        card, card_layout = self._card("Music Lab")
        self._music_prompt = QLineEdit(page)
        self._music_prompt.setObjectName("SoundLineEdit")
        self._music_prompt.setPlaceholderText("Describe the BGM or score")
        self._music_prompt.setText("30s cinematic tech demo BGM")
        self._music_prompt.setMinimumHeight(24)
        self._music_prompt.setAccessibleName("Music Lab prompt")
        card_layout.addWidget(self._music_prompt)

        row = QWidget(page)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(5)
        self._music_genre = self._combo(
            ["cinematic electronic", "electronic", "lofi", "corporate electronic", "pop electronic"],
            lambda _text: self._refresh_music_arrangement(),
        )
        self._music_genre.setAccessibleName("Music Lab genre")
        self._music_mood = self._combo(
            ["confident", "epic", "chill", "clear", "bright", "tense"],
            lambda _text: self._refresh_music_arrangement(),
        )
        self._music_mood.setAccessibleName("Music Lab mood")
        self._music_duration = QSpinBox(page)
        self._music_duration.setObjectName("SoundSpinBox")
        self._music_duration.setRange(4, 180)
        self._music_duration.setValue(30)
        self._music_duration.setSuffix(" s")
        self._music_duration.setAccessibleName("Music Lab duration")
        self._music_duration.valueChanged.connect(lambda _value: self._refresh_music_arrangement())
        self._music_bpm = QSpinBox(page)
        self._music_bpm.setObjectName("SoundSpinBox")
        self._music_bpm.setRange(0, 180)
        self._music_bpm.setValue(0)
        self._music_bpm.setSpecialValueText("Auto BPM")
        self._music_bpm.setAccessibleName("Music Lab BPM")
        row_layout.addWidget(self._music_genre, 2)
        row_layout.addWidget(self._music_mood, 1)
        row_layout.addWidget(self._music_duration, 0)
        row_layout.addWidget(self._music_bpm, 0)
        card_layout.addWidget(row)

        roles_row = QWidget(page)
        roles_layout = QHBoxLayout(roles_row)
        roles_layout.setContentsMargins(0, 0, 0, 0)
        roles_layout.setSpacing(5)
        self._music_roles = self._combo(["stems", "mix only", "drums + bass", "pad only"], lambda _text: None)
        self._music_roles.currentTextChanged.connect(lambda _text: self._refresh_music_arrangement())
        self._music_roles.setAccessibleName("Music Lab render roles")
        self._music_key = self._combo(["auto key", "C minor", "D minor", "C major", "F major", "A minor"], lambda _text: None)
        self._music_key.currentTextChanged.connect(lambda _text: self._refresh_music_arrangement())
        self._music_key.setAccessibleName("Music Lab key")
        self._music_render_backend = self._combo(["auto renderer", "production", "soundfont", "studio EDM", "local v5"], lambda _text: None)
        self._music_render_backend.setAccessibleName("Music Lab render backend")
        roles_layout.addWidget(self._music_roles, 1)
        roles_layout.addWidget(self._music_key, 1)
        roles_layout.addWidget(self._music_render_backend, 0)
        card_layout.addWidget(roles_row)

        self._music_arrangement = _MusicLabArrangementView(page)
        self._music_arrangement.selection_changed.connect(self._on_music_arrangement_selected)
        card_layout.addWidget(self._music_arrangement, 1)

        edit_row = QWidget(page)
        edit_layout = QHBoxLayout(edit_row)
        edit_layout.setContentsMargins(0, 0, 0, 0)
        edit_layout.setSpacing(5)
        self._music_selection_label = QLabel("Selected: Drums / main", edit_row)
        self._music_selection_label.setObjectName("SoundSubtitle")
        self._music_regen_btn = QPushButton("Regenerate Selection", edit_row)
        self._music_regen_btn.setObjectName("SoundPresetButton")
        self._music_regen_btn.clicked.connect(self._request_music_regenerate_selection)
        self._music_shorter_btn = QPushButton("- Section", edit_row)
        self._music_shorter_btn.setObjectName("SoundPresetButton")
        self._music_shorter_btn.clicked.connect(lambda: self._request_music_section_resize(0.82))
        self._music_longer_btn = QPushButton("+ Section", edit_row)
        self._music_longer_btn.setObjectName("SoundPresetButton")
        self._music_longer_btn.clicked.connect(lambda: self._request_music_section_resize(1.18))
        for button in (self._music_regen_btn, self._music_shorter_btn, self._music_longer_btn):
            button.setMinimumHeight(23)
        edit_layout.addWidget(self._music_selection_label, 1)
        edit_layout.addWidget(self._music_regen_btn, 0)
        edit_layout.addWidget(self._music_shorter_btn, 0)
        edit_layout.addWidget(self._music_longer_btn, 0)
        card_layout.addWidget(edit_row)

        self._music_note_hint = QLabel("Notes: pattern preview follows generated MIDI clips.", page)
        self._music_note_hint.setObjectName("SoundSubtitle")
        self._music_note_hint.setWordWrap(True)
        card_layout.addWidget(self._music_note_hint)

        actions = QWidget(page)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(5)
        generate = QPushButton("Generate", actions)
        generate.setObjectName("SoundPresetButton")
        generate.setAccessibleName("Generate Music Lab music to timeline")
        generate.setToolTip("Generate or update Music Lab stems on the timeline")
        generate.clicked.connect(self._request_music_generate)
        update = QPushButton("Update", actions)
        update.setObjectName("SoundPresetButton")
        update.setAccessibleName("Update Music Lab timeline render")
        update.setToolTip("Re-render the latest Music Lab composition into existing timeline tracks")
        update.clicked.connect(self._request_music_update)
        preview = QPushButton("Preview", actions)
        preview.setObjectName("SoundPresetButton")
        preview.setAccessibleName("Play Music Lab preview mix")
        preview.setToolTip("Play the generated preview mix inside Music Lab")
        preview.clicked.connect(self._request_music_preview)
        stop = QPushButton("Stop", actions)
        stop.setObjectName("SoundPresetButton")
        stop.setAccessibleName("Stop Music Lab preview")
        stop.setToolTip("Stop Music Lab preview playback")
        stop.clicked.connect(self._stop_music_preview)
        export = QPushButton("MIDI", actions)
        export.setObjectName("SoundPresetButton")
        export.setAccessibleName("Export Music Lab MIDI")
        export.setToolTip("Export the latest Music Lab composition as a MIDI file")
        export.clicked.connect(self._request_music_export_midi)
        self._music_generate_btn = generate
        self._music_preview_btn = preview
        self._music_stop_btn = stop
        self._music_update_btn = update
        self._music_export_btn = export
        for button in (generate, preview, stop, update, export):
            button.setMinimumHeight(24)
            actions_layout.addWidget(button, 1)
        card_layout.addWidget(actions)

        self._music_status = QLabel("MIDI-first composition, timeline stems, and AI-action control.", page)
        self._music_status.setObjectName("SoundSubtitle")
        self._music_status.setWordWrap(True)
        card_layout.addWidget(self._music_status)
        layout.addWidget(card)
        layout.addStretch(1)
        self._refresh_music_arrangement()
        return page

    def open_music_lab(self) -> None:
        self._set_tab("music")

    def set_music_composition(self, composition: dict[str, Any] | None) -> None:
        self._music_composition = dict(composition or {}) if isinstance(composition, dict) else None
        arranger = getattr(self, "_music_arrangement", None)
        if arranger is not None:
            arranger.set_composition(self._music_composition)
            self._music_selection = arranger.selection()
        self._sync_music_controls_from_composition()
        self._refresh_music_arrangement()
        self._update_music_selection_ui()
        self._refresh_music_preview_controls()

    def _sync_music_controls_from_composition(self) -> None:
        composition = self._music_composition or {}
        if not composition:
            return
        self._music_prompt.setText(str(composition.get("prompt") or self._music_prompt.text()))
        self._set_combo_text(self._music_genre, composition.get("genre") or self._music_genre.currentText())
        self._set_combo_text(self._music_mood, composition.get("mood") or self._music_mood.currentText())
        self._set_combo_text(self._music_key, composition.get("key") or self._music_key.currentText())
        try:
            self._music_duration.blockSignals(True)
            self._music_duration.setValue(max(4, min(180, int(round(float(composition.get("duration_ms") or 30000) / 1000.0)))))
        finally:
            self._music_duration.blockSignals(False)
        try:
            self._music_bpm.setValue(max(0, min(180, int(composition.get("bpm") or 0))))
        except Exception:
            pass
        render_backend = composition.get("render_backend")
        backend = str(render_backend.get("backend") or "") if isinstance(render_backend, dict) else ""
        if backend == "fluidsynth_soundfont":
            self._set_combo_text(self._music_render_backend, "soundfont")
        elif backend == "studio_edm":
            self._set_combo_text(self._music_render_backend, "studio EDM")
        elif backend == "local_synth":
            self._set_combo_text(self._music_render_backend, "local v5")
        elif backend == "production_external":
            self._set_combo_text(self._music_render_backend, "production")

    def _on_music_arrangement_selected(self, selection) -> None:
        self._music_selection = dict(selection or {})
        self._update_music_selection_ui()
        self.music_lab_selection_changed.emit(self._music_selection_payload())

    def _music_selection_payload(self) -> dict[str, Any]:
        payload = dict(self._music_selection or {})
        composition = self._music_composition or {}
        if composition:
            payload["composition_id"] = str(composition.get("id") or payload.get("composition_id") or "")
        section = self._selected_section_row()
        payload["section_start_ms"] = int(section.get("start_ms") or 0) if section else 0
        payload["section_duration_ms"] = self._selected_section_duration_ms()
        payload["chord_progression"] = self._selected_chord_progression()
        payload["note_count"] = self._selected_note_count()
        payload["note_preview"] = self._selected_note_preview()
        return payload

    def _update_music_selection_ui(self) -> None:
        selection = self._music_selection_payload()
        role_text = str(selection.get("role") or "track")
        role = "Pad" if role_text.lower() == "chords" else role_text.title()
        section = str(selection.get("section_name") or "section")
        duration = int(selection.get("section_duration_ms") or 0)
        notes = int(selection.get("note_count") or 0)
        chords = [str(chord) for chord in list(selection.get("chord_progression") or []) if str(chord).strip()]
        note_preview = [str(note) for note in list(selection.get("note_preview") or []) if str(note).strip()]
        if hasattr(self, "_music_selection_label"):
            self._music_selection_label.setText(f"Selected: {role} / {section}  |  {duration / 1000.0:.1f}s")
        if hasattr(self, "_music_note_hint"):
            chord_text = " - ".join(chords[:4]) if chords else "auto chords"
            preview_text = ", ".join(note_preview[:6]) if note_preview else "no MIDI notes yet"
            self._music_note_hint.setText(
                f"Chords: {chord_text}  |  Notes: {notes} ({preview_text}). "
                "Regenerate or resize the selection, then Update refreshes timeline stems."
            )

    def _selected_section_row(self) -> dict[str, Any]:
        section_name = str((self._music_selection or {}).get("section_name") or "").lower()
        for row in list((self._music_composition or {}).get("sections") or []):
            if isinstance(row, dict) and str(row.get("name") or "").lower() == section_name:
                return row
        return {}

    def _selected_section_duration_ms(self) -> int:
        row = self._selected_section_row()
        if row:
            try:
                return max(1, int(row.get("duration_ms") or 0))
            except Exception:
                return 0
        return 0

    def _selected_chord_progression(self) -> list[str]:
        row = self._selected_section_row()
        return [str(chord) for chord in list(row.get("chord_progression") or []) if str(chord).strip()]

    def _selected_note_count(self) -> int:
        selection = self._music_selection or {}
        role = str(selection.get("role") or "").lower()
        if role == "pad":
            role = "chords"
        section_name = str(selection.get("section_name") or "").lower()
        total = 0
        for track in list((self._music_composition or {}).get("tracks") or []):
            if not isinstance(track, dict):
                continue
            track_role = str(track.get("role") or track.get("id") or "").lower()
            if role and track_role != role:
                continue
            for clip in list(track.get("clips") or []):
                if isinstance(clip, dict) and str(clip.get("section_name") or "").lower() == section_name:
                    total += len(list(clip.get("notes") or []))
        return total

    def _selected_note_preview(self) -> list[str]:
        selection = self._music_selection or {}
        role = str(selection.get("role") or "").lower()
        if role == "pad":
            role = "chords"
        section_name = str(selection.get("section_name") or "").lower()
        preview: list[str] = []
        for track in list((self._music_composition or {}).get("tracks") or []):
            if not isinstance(track, dict):
                continue
            track_role = str(track.get("role") or track.get("id") or "").lower()
            if role and track_role != role:
                continue
            for clip in list(track.get("clips") or []):
                if not isinstance(clip, dict) or str(clip.get("section_name") or "").lower() != section_name:
                    continue
                for note in list(clip.get("notes") or [])[:8]:
                    if isinstance(note, dict):
                        preview.append(str(note.get("pitch") or "?"))
                if preview:
                    return preview
        return preview

    def _refresh_music_arrangement(self) -> None:
        arranger = getattr(self, "_music_arrangement", None)
        if arranger is None:
            return
        try:
            arranger.set_arrangement(
                duration_s=int(self._music_duration.value()),
                mode=self._music_roles.currentText(),
                key=self._music_key.currentText(),
                genre=self._music_genre.currentText(),
                mood=self._music_mood.currentText(),
            )
            if self._music_composition:
                arranger.set_composition(self._music_composition)
        except Exception:
            pass

    def _music_roles_param(self) -> tuple[list[str] | None, bool]:
        value = str(getattr(self, "_music_roles", None).currentText() if hasattr(self, "_music_roles") else "").strip().lower()
        if value == "mix only":
            return None, True
        if value == "drums + bass":
            return ["drums", "bass"], False
        if value == "pad only":
            return ["chords"], False
        return None, False

    def _music_compose_params(self) -> dict[str, Any]:
        roles, create_mix = self._music_roles_param()
        params: dict[str, Any] = {
            "prompt": self._music_prompt.text().strip() or "AI background music",
            "duration_ms": int(self._music_duration.value()) * 1000,
            "genre": self._music_genre.currentText(),
            "mood": self._music_mood.currentText(),
            "include_fx": True,
            "at_ms": 0,
            "auto_balance": True,
            "update_existing": True,
            "create_mix": create_mix,
        }
        params.update(self._music_backend_params())
        if roles:
            params["roles"] = roles
        bpm = int(self._music_bpm.value())
        if bpm > 0:
            params["bpm"] = bpm
        key = self._music_key.currentText()
        if key and key != "auto key":
            params["key"] = key
        return params

    def _music_backend_params(self) -> dict[str, Any]:
        value = str(
            getattr(self, "_music_render_backend", None).currentText()
            if hasattr(self, "_music_render_backend")
            else ""
        ).strip().lower()
        if value == "soundfont":
            return {"backend": "soundfont"}
        if value == "production":
            return {"backend": "production"}
        if value == "studio edm":
            return {"backend": "studio_edm"}
        if value == "local v5":
            return {"backend": "local_synth"}
        return {"backend": "auto"}

    def _request_music_generate(self) -> None:
        self._music_status.setText("Generating Music Lab stems...")
        self.music_lab_action_requested.emit("music.compose_to_timeline", self._music_compose_params())

    def _request_music_update(self) -> None:
        roles, create_mix = self._music_roles_param()
        params: dict[str, Any] = {
            "at_ms": 0,
            "create_mix": create_mix,
            "update_existing": True,
        }
        params.update(self._music_backend_params())
        composition_id = str(self._music_selection_payload().get("composition_id") or "")
        if composition_id:
            params["composition_id"] = composition_id
        if roles:
            params["roles"] = roles
        self._music_status.setText("Updating existing Music Lab timeline tracks...")
        self.music_lab_action_requested.emit("music.render_to_timeline", params)

    def _request_music_export_midi(self) -> None:
        self._music_status.setText("Exporting Music Lab MIDI...")
        composition_id = str(self._music_selection_payload().get("composition_id") or "")
        params = {"composition_id": composition_id} if composition_id else {}
        self.music_lab_action_requested.emit("music.export_midi", params)

    def _music_preview_mix_path(self) -> Path | None:
        path_text = str((self._music_composition or {}).get("preview_mix_path") or "").strip()
        if not path_text:
            return None
        path = Path(path_text)
        return path if path.exists() else None

    def _refresh_music_preview_controls(self) -> None:
        path = self._music_preview_mix_path()
        enabled = path is not None
        if hasattr(self, "_music_preview_btn"):
            self._music_preview_btn.setProperty("has_preview", enabled)
            self._music_preview_btn.setToolTip(
                f"Play preview mix: {path.name}" if enabled else "Render or generate music before preview playback"
            )
        if hasattr(self, "_music_stop_btn"):
            self._music_stop_btn.setEnabled(True)
        if enabled and hasattr(self, "_music_status"):
            engine = str((self._music_composition or {}).get("render_engine") or "rendered preview")
            render_backend = (self._music_composition or {}).get("render_backend")
            quality = ""
            warning = ""
            if isinstance(render_backend, dict):
                quality = str(render_backend.get("quality_tier") or "")
                warning = str(render_backend.get("quality_warning") or "")
            suffix = f" | Quality: {quality}" if quality else ""
            if warning:
                suffix += f" | {warning}"
            self._music_status.setText(f"Preview ready: {path.name} | Renderer: {engine}{suffix}")

    def _ensure_music_preview_player(self) -> bool:
        if self._music_preview_player is not None:
            return True
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
        except Exception as exc:
            self._music_status.setText(f"Music preview playback is unavailable: {exc}")
            return False
        self._music_preview_output = QAudioOutput(self)
        self._music_preview_output.setVolume(0.85)
        self._music_preview_player = QMediaPlayer(self)
        self._music_preview_player.setAudioOutput(self._music_preview_output)
        self._music_preview_player.playbackStateChanged.connect(self._on_music_preview_state_changed)
        return True

    def _request_music_preview(self) -> None:
        path = self._music_preview_mix_path()
        if path is None:
            composition_id = str(self._music_selection_payload().get("composition_id") or "")
            if composition_id:
                self._music_status.setText("Rendering Music Lab preview mix...")
                params = {"composition_id": composition_id, "render_stems": False}
                params.update(self._music_backend_params())
                self.music_lab_action_requested.emit("music.render.preview", params)
            else:
                self._music_status.setText("Generate music first, then preview it here in Music Lab.")
            return
        if not self._ensure_music_preview_player() or self._music_preview_player is None:
            return
        resolved = str(path.resolve())
        if self._music_preview_loaded_path != resolved:
            self._music_preview_player.setSource(QUrl.fromLocalFile(resolved))
            self._music_preview_loaded_path = resolved
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            if self._music_preview_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._music_preview_player.pause()
                self._music_status.setText(f"Paused Music Lab preview: {path.name}")
                return
        except Exception:
            pass
        self._music_preview_player.play()
        self._music_status.setText(f"Playing Music Lab preview: {path.name}")

    def _stop_music_preview(self) -> None:
        player = self._music_preview_player
        if player is not None:
            try:
                player.stop()
            except Exception:
                pass
        self._music_status.setText("Music Lab preview stopped.")

    def _on_music_preview_state_changed(self, state) -> None:
        try:
            from PySide6.QtMultimedia import QMediaPlayer
            playing = state == QMediaPlayer.PlaybackState.PlayingState
        except Exception:
            playing = False
        if hasattr(self, "_music_preview_btn"):
            self._music_preview_btn.setText("Pause" if playing else "Preview")

    def _request_music_regenerate_selection(self) -> None:
        payload = self._music_selection_payload()
        composition_id = str(payload.get("composition_id") or "")
        section_name = str(payload.get("section_name") or "main")
        if not composition_id:
            self._music_status.setText("Generate music first, then regenerate a selected block.")
            return
        self._music_status.setText(f"Regenerating {section_name}...")
        params = {"composition_id": composition_id, "section_name": section_name, "intensity": 0.95}
        params.update(self._music_backend_params())
        self.music_lab_action_requested.emit(
            "music.regenerate_section",
            params,
        )

    def _request_music_section_resize(self, ratio: float) -> None:
        payload = self._music_selection_payload()
        composition_id = str(payload.get("composition_id") or "")
        section_name = str(payload.get("section_name") or "main")
        current = int(payload.get("section_duration_ms") or 0)
        if not composition_id or current <= 0:
            self._music_status.setText("Generate music first, then resize a selected section.")
            return
        duration = max(1000, int(round(current * float(ratio or 1.0))))
        self._music_status.setText(f"Resizing {section_name} to {duration / 1000.0:.1f}s...")
        params = {"composition_id": composition_id, "section_name": section_name, "duration_ms": duration}
        params.update(self._music_backend_params())
        self.music_lab_action_requested.emit(
            "music.section.set",
            params,
        )

    def _set_tab(self, tab_id: str) -> None:
        order = {"basic": 0, "mixer": 1, "eq": 2, "dyn": 3, "fx": 4, "ai": 5, "music": 6}
        self._stack.setCurrentIndex(order.get(tab_id, 0))
        for key, button in self._tab_buttons.items():
            button.setChecked(key == tab_id)
        self._set_mixer_tab_compact_mode(tab_id in {"mixer", "music"})

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
