from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.motion_designer.schema import MotionComposition, MotionLayer


class AdvancedMotionPanel(QWidget):
    metadata_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loading = False
        self._layer_id = ""
        self._replicator_extra: dict = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 7, 7, 7)
        form = QFormLayout()
        root.addLayout(form)

        depth_title = QLabel("2.5D Layer", self)
        depth_title.setObjectName("MotionInspectorSection")
        form.addRow(depth_title)
        self.three_d_enabled = QCheckBox("Enable 3D card", self)
        self.depth = self._double(-8.0, 8.0, 0.05)
        self.rotation_x = self._double(-180.0, 180.0, 0.5)
        self.rotation_y = self._double(-180.0, 180.0, 0.5)
        self.camera_excluded = QCheckBox("Exclude from 2.5D camera", self)
        self.cast_shadows = QCheckBox("Cast shadows", self)
        self.receive_shadows = QCheckBox("Receive shadows", self)
        self.shadow_strength = self._double(0.0, 1.0, 0.05)
        self.shadow_softness = self._double(0.0, 32.0, 0.5)
        form.addRow(self.three_d_enabled)
        form.addRow("Depth Z", self.depth)
        form.addRow("Rotation X", self.rotation_x)
        form.addRow("Rotation Y", self.rotation_y)
        form.addRow(self.camera_excluded)
        form.addRow(self.cast_shadows)
        form.addRow(self.receive_shadows)
        form.addRow("Shadow Strength", self.shadow_strength)
        form.addRow("Shadow Softness", self.shadow_softness)

        blur_title = QLabel("Motion Blur", self)
        blur_title.setObjectName("MotionInspectorSection")
        form.addRow(blur_title)
        self.blur_enabled = QCheckBox("Enabled", self)
        self.blur_samples = QSpinBox(self)
        self.blur_samples.setRange(2, 32)
        self.blur_shutter = self._double(0.0, 2.0, 0.05)
        form.addRow(self.blur_enabled)
        form.addRow("Samples", self.blur_samples)
        form.addRow("Shutter", self.blur_shutter)

        repeat_title = QLabel("Replicator", self)
        repeat_title.setObjectName("MotionInspectorSection")
        form.addRow(repeat_title)
        self.repeat_enabled = QCheckBox("Enabled", self)
        self.repeat_count = QSpinBox(self)
        self.repeat_count.setRange(1, 256)
        self.repeat_x = self._double(-10000, 10000, 1)
        self.repeat_y = self._double(-10000, 10000, 1)
        self.repeat_rotation = self._double(-360, 360, 0.5)
        self.repeat_scale = self._double(0.1, 4.0, 0.01)
        self.repeat_opacity = self._double(0.0, 1.0, 0.01)
        self.repeat_jitter = self._double(0.0, 1000.0, 1.0)
        form.addRow(self.repeat_enabled)
        form.addRow("Copies", self.repeat_count)
        form.addRow("Offset X", self.repeat_x)
        form.addRow("Offset Y", self.repeat_y)
        form.addRow("Rotation", self.repeat_rotation)
        form.addRow("Scale / copy", self.repeat_scale)
        form.addRow("End opacity", self.repeat_opacity)
        form.addRow("Jitter", self.repeat_jitter)

        matte_title = QLabel("Track Matte", self)
        matte_title.setObjectName("MotionInspectorSection")
        form.addRow(matte_title)
        self.matte_layer = QComboBox(self)
        self.matte_mode = QComboBox(self)
        self.matte_mode.addItems(["alpha", "luma"])
        self.matte_inverted = QCheckBox("Invert", self)
        form.addRow("Source", self.matte_layer)
        form.addRow("Mode", self.matte_mode)
        form.addRow(self.matte_inverted)
        root.addStretch(1)

        for control in (
            self.depth, self.rotation_x, self.rotation_y,
            self.shadow_strength, self.shadow_softness,
            self.blur_samples, self.blur_shutter,
            self.repeat_count, self.repeat_x, self.repeat_y, self.repeat_rotation,
            self.repeat_scale, self.repeat_opacity, self.repeat_jitter,
        ):
            control.valueChanged.connect(lambda _value: self._emit())
        for control in (
            self.three_d_enabled, self.camera_excluded, self.cast_shadows,
            self.receive_shadows, self.blur_enabled, self.repeat_enabled,
            self.matte_inverted,
        ):
            control.toggled.connect(lambda _value: self._emit())
        self.matte_layer.currentIndexChanged.connect(lambda _index: self._emit())
        self.matte_mode.currentTextChanged.connect(lambda _text: self._emit())

    def _double(self, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(3)
        return control

    def set_layer(self, layer: MotionLayer | None, composition: MotionComposition) -> None:
        self._loading = True
        self._layer_id = layer.id if layer is not None else ""
        self._replicator_extra = {}
        self.setEnabled(layer is not None)
        self.matte_layer.clear()
        self.matte_layer.addItem("None", "")
        for candidate in reversed(composition.layers):
            if layer is None or candidate.id != layer.id:
                self.matte_layer.addItem(candidate.name, candidate.id)
        if layer is not None:
            metadata = layer.metadata
            three_d = metadata.get("three_d")
            three_d = three_d if isinstance(three_d, Mapping) else {}
            self.three_d_enabled.setChecked(bool(three_d.get("enabled", False)))
            self.depth.setValue(float(metadata.get("depth_z", 0.0) or 0.0))
            self.rotation_x.setValue(float(three_d.get("rotation_x", 0.0) or 0.0))
            self.rotation_y.setValue(float(three_d.get("rotation_y", 0.0) or 0.0))
            self.camera_excluded.setChecked(bool(metadata.get("camera_2_5d_excluded", False)))
            self.cast_shadows.setChecked(bool(three_d.get("cast_shadows", False)))
            self.receive_shadows.setChecked(bool(three_d.get("receive_shadows", False)))
            self.shadow_strength.setValue(
                float(three_d.get("shadow_strength", 0.45) or 0.0)
            )
            self.shadow_softness.setValue(
                float(three_d.get("shadow_softness", 6.0) or 0.0)
            )
            blur = metadata.get("motion_blur")
            blur = blur if isinstance(blur, Mapping) else {}
            self.blur_enabled.setChecked(bool(blur.get("enabled", False)))
            self.blur_samples.setValue(int(blur.get("samples", 8) or 8))
            self.blur_shutter.setValue(float(blur.get("shutter", 0.65) or 0.0))
            repeat = metadata.get("replicator")
            repeat = repeat if isinstance(repeat, Mapping) else {}
            self._replicator_extra = dict(repeat)
            offset = list(repeat.get("offset") or [0.0, 0.0])
            scale = list(repeat.get("scale") or [1.0, 1.0])
            jitter = list(repeat.get("jitter") or [0.0, 0.0])
            self.repeat_enabled.setChecked(bool(repeat.get("enabled", False)))
            self.repeat_count.setValue(int(repeat.get("count", 1) or 1))
            self.repeat_x.setValue(float(offset[0] if offset else 0.0))
            self.repeat_y.setValue(float(offset[1] if len(offset) > 1 else 0.0))
            self.repeat_rotation.setValue(float(repeat.get("rotation", 0.0) or 0.0))
            self.repeat_scale.setValue(float(scale[0] if scale else 1.0))
            self.repeat_opacity.setValue(float(repeat.get("opacity_end", 1.0) or 0.0))
            self.repeat_jitter.setValue(float(jitter[0] if jitter else 0.0))
            matte_id = str(metadata.get("matte_layer_id") or "")
            index = self.matte_layer.findData(matte_id)
            self.matte_layer.setCurrentIndex(max(0, index))
            self.matte_mode.setCurrentText(str(metadata.get("matte_mode") or "alpha"))
            self.matte_inverted.setChecked(bool(metadata.get("matte_inverted", False)))
        self._loading = False

    def _emit(self) -> None:
        if self._loading or not self._layer_id:
            return
        self.metadata_changed.emit({
            "depth_z": self.depth.value(),
            "camera_2_5d_excluded": self.camera_excluded.isChecked(),
            "three_d": {
                "enabled": self.three_d_enabled.isChecked(),
                "rotation_x": self.rotation_x.value(),
                "rotation_y": self.rotation_y.value(),
                "cast_shadows": self.cast_shadows.isChecked(),
                "receive_shadows": self.receive_shadows.isChecked(),
                "shadow_strength": self.shadow_strength.value(),
                "shadow_softness": self.shadow_softness.value(),
                "projection_model": "affine_card_2_5d",
            },
            "motion_blur": {
                "enabled": self.blur_enabled.isChecked(),
                "samples": self.blur_samples.value(),
                "shutter": self.blur_shutter.value(),
            },
            "replicator": {
                **self._replicator_extra,
                "enabled": self.repeat_enabled.isChecked(),
                "count": self.repeat_count.value(),
                "offset": [self.repeat_x.value(), self.repeat_y.value()],
                "rotation": self.repeat_rotation.value(),
                "scale": [self.repeat_scale.value(), self.repeat_scale.value()],
                "opacity_start": 1.0,
                "opacity_end": self.repeat_opacity.value(),
                "jitter": [self.repeat_jitter.value(), self.repeat_jitter.value()],
            },
            "matte_layer_id": str(self.matte_layer.currentData() or ""),
            "matte_mode": self.matte_mode.currentText(),
            "matte_inverted": self.matte_inverted.isChecked(),
        })


__all__ = ["AdvancedMotionPanel"]
