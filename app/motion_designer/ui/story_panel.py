"""Story beats and platform-variant controls for Motion Designer."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.story_direction import BEAT_ROLES, inspect_story
from app.motion_designer.composer_bridge import TIMING_SOURCES_KEY


class StoryDirectionPanel(QWidget):
    story_update_requested = Signal(object)
    beat_add_requested = Signal(object)
    audio_bind_requested = Signal(object)
    platform_preview_requested = Signal(str)
    platform_apply_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        heading = QLabel("Story Direction", self)
        heading.setObjectName("MotionInspectorSection")
        root.addWidget(heading)
        description = QLabel(
            "Build Hook-to-CTA beats, then review platform reflow before creating a variant.",
            self,
        )
        description.setWordWrap(True)
        root.addWidget(description)

        story_form = QFormLayout()
        self.title = QLineEdit(self)
        self.message = QLineEdit(self)
        self.audience = QLineEdit(self)
        story_form.addRow("Title", self.title)
        story_form.addRow("Message", self.message)
        story_form.addRow("Audience", self.audience)
        root.addLayout(story_form)
        self.save_story = QPushButton("Update Story", self)
        root.addWidget(self.save_story)

        self.beats = QListWidget(self)
        self.beats.setMinimumHeight(120)
        root.addWidget(self.beats)
        beat_form = QFormLayout()
        self.role = QComboBox(self)
        for value in BEAT_ROLES:
            self.role.addItem(value.title(), value)
        self.start_ms = QSpinBox(self)
        self.start_ms.setRange(0, 3_600_000)
        self.end_ms = QSpinBox(self)
        self.end_ms.setRange(1, 3_600_000)
        self.end_ms.setValue(1500)
        self.purpose = QLineEdit(self)
        self.emotion = QLineEdit(self)
        self.copy = QLineEdit(self)
        beat_form.addRow("Beat", self.role)
        beat_form.addRow("Start (ms)", self.start_ms)
        beat_form.addRow("End (ms)", self.end_ms)
        beat_form.addRow("Purpose", self.purpose)
        beat_form.addRow("Emotion", self.emotion)
        beat_form.addRow("Copy", self.copy)
        root.addLayout(beat_form)
        self.add_beat = QPushButton("Add Beat", self)
        root.addWidget(self.add_beat)

        audio_form = QFormLayout()
        self.audio_source = QComboBox(self)
        self.audio_source.setMinimumContentsLength(18)
        self.bind_audio = QPushButton("Bind Audio to Selected Beat", self)
        audio_form.addRow("Voice / Music", self.audio_source)
        root.addLayout(audio_form)
        root.addWidget(self.bind_audio)

        platform_row = QHBoxLayout()
        self.platform = QComboBox(self)
        self.platform.addItem("Landscape 16:9", "landscape_16_9")
        self.platform.addItem("Vertical 9:16", "vertical_9_16")
        self.platform.addItem("Square 1:1", "square_1_1")
        self.preview_variant = QPushButton("Preview Diff", self)
        self.apply_variant = QPushButton("Create Reviewed Variant", self)
        platform_row.addWidget(self.platform, 1)
        platform_row.addWidget(self.preview_variant)
        root.addLayout(platform_row)
        root.addWidget(self.apply_variant)

        self.diff = QTextEdit(self)
        self.diff.setReadOnly(True)
        self.diff.setMinimumHeight(110)
        self.diff.setPlaceholderText("Platform reflow diff and preflight appear here.")
        root.addWidget(self.diff)
        root.addStretch(1)

        self.save_story.clicked.connect(self._emit_story)
        self.add_beat.clicked.connect(self._emit_beat)
        self.bind_audio.clicked.connect(self._emit_audio_binding)
        self.preview_variant.clicked.connect(
            lambda: self.platform_preview_requested.emit(str(self.platform.currentData())),
        )
        self.apply_variant.clicked.connect(
            lambda: self.platform_apply_requested.emit(str(self.platform.currentData())),
        )

    def _emit_story(self) -> None:
        self.story_update_requested.emit({
            "title": self.title.text(),
            "message": self.message.text(),
            "audience": self.audience.text(),
        })

    def _emit_beat(self) -> None:
        self.beat_add_requested.emit({
            "role": str(self.role.currentData()),
            "start_ms": self.start_ms.value(),
            "end_ms": self.end_ms.value(),
            "purpose": self.purpose.text(),
            "emotion": self.emotion.text(),
            "copy": self.copy.text(),
        })

    def _emit_audio_binding(self) -> None:
        beat_item = self.beats.currentItem()
        source = self.audio_source.currentData()
        if beat_item is None or not isinstance(source, dict):
            return
        kind = str(source.get("kind") or "").lower()
        self.audio_bind_requested.emit({
            "beat_id": str(beat_item.data(0x0100) or ""),
            "source_kind": "music" if kind == "composer" else "voice",
            "source_id": str(source.get("id") or ""),
            "cue_ms": int(beat_item.data(0x0101) or 0),
            "label": self.audio_source.currentText(),
            "tempo_bpm": (
                float(source["bpm"])
                if source.get("bpm") is not None
                else None
            ),
        })

    @staticmethod
    def _audio_source_label(source: dict) -> str:
        kind = str(source.get("kind") or "").lower()
        metadata = source.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        if kind == "composer":
            path = Path(str(source.get("audio_path") or ""))
            detail = (
                path.stem
                or str(metadata.get("genre") or metadata.get("mood") or "")
                or "Composer"
            )
            return f"Music | {detail} | {int(source.get('bpm', 0))} BPM"
        sentences = source.get("sentences")
        if isinstance(sentences, list) and sentences:
            detail = str(sentences[0].get("text") or "Voice")
        else:
            detail = "Voice Lab"
        if len(detail) > 36:
            detail = f"{detail[:33]}..."
        return f"Voice | {detail}"

    def set_composition(self, composition) -> None:
        story = inspect_story(composition)
        blocked = self.title.blockSignals(True)
        self.title.setText(story["title"])
        self.title.blockSignals(blocked)
        self.message.setText(story["message"])
        self.audience.setText(story["audience"])
        self.end_ms.setMaximum(max(1, composition.duration_ms))
        self.start_ms.setMaximum(max(0, composition.duration_ms - 1))
        bindings = {
            (str(row.get("beat_id") or ""), str(row.get("source_kind") or "")): row
            for row in story.get("audio_bindings", [])
        }
        self.beats.clear()
        for beat in story["beats"]:
            bound_kinds = [
                kind.title()
                for kind in ("voice", "music")
                if (str(beat.get("id") or ""), kind) in bindings
            ]
            binding_label = (
                f"  [{' + '.join(bound_kinds)}]"
                if bound_kinds
                else ""
            )
            item = QListWidgetItem(
                f"{str(beat.get('role') or '').upper()}  "
                f"{int(beat.get('start_ms', 0)) / 1000:.1f}-"
                f"{int(beat.get('end_ms', 0)) / 1000:.1f}s  "
                f"{str(beat.get('purpose') or beat.get('copy') or '')}"
                f"{binding_label}",
            )
            item.setData(0x0100, str(beat.get("id") or ""))
            item.setData(0x0101, int(beat.get("start_ms", 0)))
            self.beats.addItem(item)
        self.audio_source.clear()
        sources = composition.metadata.get(TIMING_SOURCES_KEY)
        if isinstance(sources, dict):
            for source in sources.values():
                if not isinstance(source, dict):
                    continue
                if str(source.get("kind") or "").lower() not in {
                    "voice",
                    "composer",
                }:
                    continue
                self.audio_source.addItem(
                    self._audio_source_label(source),
                    dict(source),
                )
        self.bind_audio.setEnabled(
            self.beats.count() > 0 and self.audio_source.count() > 0,
        )

    def show_variant_result(self, payload: dict) -> None:
        plan = payload.get("plan") or {}
        preflight = payload.get("preflight") or {}
        summary = plan.get("diff_summary") or {}
        issues = list(preflight.get("issues") or [])
        lines = [
            f"{str(plan.get('platform') or '').replace('_', ' ').title()}",
            f"{summary.get('operation_count', 0)} changes across "
            f"{summary.get('layer_count', 0)} layers",
            f"Preflight: {'READY' if preflight.get('ok') else 'REVIEW'}",
        ]
        lines.extend(f"- {item.get('code')}" for item in issues[:8])
        self.diff.setPlainText("\n".join(lines))


__all__ = ["StoryDirectionPanel"]
