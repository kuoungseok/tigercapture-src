"""Compact MMD actor editor used by the main video editor."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.mmd.editor_workflow import (
    add_mmd_motion_to_library,
    apply_mmd_motion_to_track,
    apply_mmd_settings_to_track,
    mmd_motion_library_for_track,
)
from app.mmd.lighting import MMD_LIGHTING_PRESETS
from app.mmd.schema import normalize_playback, normalize_render


class MMDActorEditorDialog(QDialog):
    """Track-scoped editor for MMD motion, physics, lighting, and materials."""

    track_changed = Signal(dict)

    def __init__(self, track: dict[str, Any], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MMD Actor Editor")
        self.setMinimumSize(520, 560)
        self._track = track
        self._suppress = False
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        model_path = str(track.get("model_path") or "")
        self._title = QLabel(Path(model_path).name or str(track.get("id") or "MMD Actor"), self)
        self._title.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F2F6;")
        root.addWidget(self._title)
        self._model_label = QLabel(model_path or "-", self)
        self._model_label.setWordWrap(True)
        self._model_label.setStyleSheet("color: #9EA7B5;")
        root.addWidget(self._model_label)

        motion_header = QHBoxLayout()
        motion_header.addWidget(QLabel("Motion Library", self), 1)
        self._add_motion_btn = QPushButton("Add Motion", self)
        self._apply_motion_btn = QPushButton("Apply", self)
        motion_header.addWidget(self._add_motion_btn)
        motion_header.addWidget(self._apply_motion_btn)
        root.addLayout(motion_header)

        self._motion_list = QListWidget(self)
        self._motion_list.setMinimumHeight(120)
        root.addWidget(self._motion_list)

        playback = normalize_playback(track.get("playback"))
        render = normalize_render(track.get("render"))
        material = dict(render.get("material") or {})

        self._physics_check = QCheckBox("Physics", self)
        self._physics_check.setChecked(bool(playback.get("enable_physics", True)))
        self._gpu_check = QCheckBox("GPU Skinning", self)
        self._gpu_check.setChecked(bool(playback.get("gpu_skinning", True)))
        toggle_row = QHBoxLayout()
        toggle_row.addWidget(self._physics_check)
        toggle_row.addWidget(self._gpu_check)
        toggle_row.addStretch(1)
        root.addLayout(toggle_row)

        self._physics_backend_combo = QComboBox(self)
        self._physics_backend_combo.addItem("Auto", "auto")
        self._physics_backend_combo.addItem("Spring", "spring")
        self._physics_backend_combo.addItem("PyBullet", "pybullet")
        self._physics_backend_combo.addItem("None", "none")
        backend_index = self._physics_backend_combo.findData(str(playback.get("physics_backend") or "auto"))
        self._physics_backend_combo.setCurrentIndex(backend_index if backend_index >= 0 else 0)
        backend_row = QHBoxLayout()
        backend_row.addWidget(QLabel("Physics Backend", self))
        backend_row.addWidget(self._physics_backend_combo, 1)
        root.addLayout(backend_row)

        self._cloth_slider, self._cloth_value = self._slider_row(
            root, "Cloth/Hair", 0, 30, int(round(float(playback.get("physics_rotation_hint_scale", 0.12)) * 100.0)), scale=100.0
        )
        self._follow_slider, self._follow_value = self._slider_row(
            root, "Follow", 15, 150, int(round(float(playback.get("physics_spring_response", 0.60)) * 100.0)), scale=100.0
        )

        self._lighting_combo = QComboBox(self)
        for key, preset in MMD_LIGHTING_PRESETS.items():
            self._lighting_combo.addItem(str(preset.get("label") or key), key)
        current_preset = str(render.get("lighting_preset") or "studio_soft")
        idx = self._lighting_combo.findData(current_preset)
        self._lighting_combo.setCurrentIndex(idx if idx >= 0 else 0)
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Light Preset", self))
        preset_row.addWidget(self._lighting_combo, 1)
        root.addLayout(preset_row)

        lighting = dict(render.get("lighting") or {})
        self._bloom_slider, self._bloom_value = self._slider_row(
            root, "Bloom", 0, 200, int(round(float(render.get("bloom_strength", 0.30)) * 100.0)), scale=100.0
        )
        self._key_slider, self._key_value = self._slider_row(
            root, "Key", 0, 200, int(round(float(lighting.get("key_intensity", 1.0)) * 100.0)), scale=100.0
        )
        self._fill_slider, self._fill_value = self._slider_row(
            root, "Fill", 0, 150, int(round(float(lighting.get("fill_intensity", 0.32)) * 100.0)), scale=100.0
        )
        self._rim_slider, self._rim_value = self._slider_row(
            root, "Rim", 0, 150, int(round(float(lighting.get("rim_intensity", 0.12)) * 100.0)), scale=100.0
        )
        self._ambient_slider, self._ambient_value = self._slider_row(
            root, "Ambient", 0, 120, int(round(float(lighting.get("ambient_intensity", 0.40)) * 100.0)), scale=100.0
        )
        self._shadow_slider, self._shadow_value = self._slider_row(
            root, "Shadow", 0, 120, int(round(float(lighting.get("shadow_strength", 0.64)) * 100.0)), scale=100.0
        )

        self._skin_slider, self._skin_value = self._slider_row(
            root, "Skin", 0, 200, int(round(float(material.get("skin_warmth", 1.0)) * 100.0)), scale=100.0
        )
        self._hair_slider, self._hair_value = self._slider_row(
            root, "Hair", 0, 200, int(round(float(material.get("hair_highlight", 1.0)) * 100.0)), scale=100.0
        )
        self._eye_slider, self._eye_value = self._slider_row(
            root, "Eye", 0, 200, int(round(float(material.get("eye_highlight", 1.0)) * 100.0)), scale=100.0
        )
        self._spec_slider, self._spec_value = self._slider_row(
            root, "Specular", 0, 200, int(round(float(material.get("matcap_specular", 1.0)) * 100.0)), scale=100.0
        )

        self._close_btn = QPushButton("Close", self)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_row.addWidget(self._close_btn)
        root.addLayout(close_row)

        self._add_motion_btn.clicked.connect(self._add_motion)
        self._apply_motion_btn.clicked.connect(self._apply_selected_motion)
        self._motion_list.itemDoubleClicked.connect(lambda _item: self._apply_selected_motion())
        self._close_btn.clicked.connect(self.accept)
        self._wire_live_controls()
        self.reload_motion_library()

    def _slider_row(self, parent_layout: QVBoxLayout, label: str, minimum: int, maximum: int, value: int, *, scale: float) -> tuple[QSlider, QLabel]:
        row = QHBoxLayout()
        name = QLabel(label, self)
        name.setMinimumWidth(74)
        slider = QSlider(Qt.Orientation.Horizontal, self)
        slider.setRange(int(minimum), int(maximum))
        slider.setValue(int(value))
        readout = QLabel(f"{float(value) / scale:.2f}", self)
        readout.setMinimumWidth(42)
        readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        slider.valueChanged.connect(lambda raw, out=readout, s=scale: out.setText(f"{float(raw) / s:.2f}"))
        row.addWidget(name)
        row.addWidget(slider, 1)
        row.addWidget(readout)
        parent_layout.addLayout(row)
        return slider, readout

    def reload_motion_library(self) -> None:
        self._motion_list.clear()
        current = str(self._track.get("motion_path") or "")
        for row in mmd_motion_library_for_track(self._track):
            path = str(row.get("path") or "")
            if not path:
                continue
            item = QListWidgetItem(str(row.get("filename") or Path(path).name), self._motion_list)
            item.setData(Qt.ItemDataRole.UserRole, path)
            if path == current:
                item.setText(f"* {item.text()}")
                self._motion_list.setCurrentItem(item)

    def _add_motion(self) -> None:
        start_dir = str(Path(str(self._track.get("model_path") or "")).parent)
        path, _filter = QFileDialog.getOpenFileName(self, "Add MMD Motion", start_dir, "VMD Motion (*.vmd)")
        if not path:
            return
        resolved = add_mmd_motion_to_library(self._track, path)
        self.reload_motion_library()
        self._select_motion_path(resolved)

    def _select_motion_path(self, path: str) -> None:
        for i in range(self._motion_list.count()):
            item = self._motion_list.item(i)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == str(path):
                self._motion_list.setCurrentItem(item)
                return

    def _apply_selected_motion(self) -> None:
        item = self._motion_list.currentItem()
        if item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not path:
            return
        apply_mmd_motion_to_track(self._track, path)
        self.reload_motion_library()
        self.track_changed.emit(self._track)

    def _wire_live_controls(self) -> None:
        for widget in (
            self._physics_check,
            self._gpu_check,
            self._physics_backend_combo,
            self._lighting_combo,
            self._cloth_slider,
            self._follow_slider,
            self._bloom_slider,
            self._key_slider,
            self._fill_slider,
            self._rim_slider,
            self._ambient_slider,
            self._shadow_slider,
            self._skin_slider,
            self._hair_slider,
            self._eye_slider,
            self._spec_slider,
        ):
            signal = getattr(widget, "valueChanged", None) or getattr(widget, "toggled", None) or getattr(widget, "currentIndexChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: self._apply_live_settings())

    def _apply_live_settings(self) -> None:
        if self._suppress:
            return
        playback = {
            "enable_physics": bool(self._physics_check.isChecked()),
            "gpu_skinning": bool(self._gpu_check.isChecked()),
            "physics_backend": str(self._physics_backend_combo.currentData() or "auto"),
            "physics_rotation_hint_scale": self._cloth_slider.value() / 100.0,
            "physics_spring_response": self._follow_slider.value() / 100.0,
        }
        render = {
            "lighting_preset": str(self._lighting_combo.currentData() or "studio_soft"),
            "bloom_strength": self._bloom_slider.value() / 100.0,
            "lighting": {
                "key_intensity": self._key_slider.value() / 100.0,
                "fill_intensity": self._fill_slider.value() / 100.0,
                "rim_intensity": self._rim_slider.value() / 100.0,
                "ambient_intensity": self._ambient_slider.value() / 100.0,
                "shadow_strength": self._shadow_slider.value() / 100.0,
            },
        }
        material = {
            "skin_warmth": self._skin_slider.value() / 100.0,
            "hair_highlight": self._hair_slider.value() / 100.0,
            "eye_highlight": self._eye_slider.value() / 100.0,
            "lip_specular": self._spec_slider.value() / 100.0,
            "matcap_specular": self._spec_slider.value() / 100.0,
        }
        apply_mmd_settings_to_track(self._track, playback=playback, render=render, material=material)
        self.track_changed.emit(self._track)
