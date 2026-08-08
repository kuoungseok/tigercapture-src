from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.mmd_source import MMD_SOURCE_KIND
from app.motion_designer.schema import AnimatedProperty, MotionLayer


def _default(value: Any, fallback: Any, value_type: str = "scalar") -> Any:
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        return evaluate_property(AnimatedProperty.from_dict(value, value_type=value_type), 0.0)
    return fallback if value is None else value


class MMDPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionMMDPanel")
        self._loading = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionMMDScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionMMDContent")
        self.form = QFormLayout(content)
        self.form.setContentsMargins(8, 6, 8, 8)
        self.form.setSpacing(5)

        self.model = QLabel("", content)
        self.model.setWordWrap(True)
        self.form.addRow("Model", self.model)
        self.motion = QLineEdit(content)
        self.motion.setReadOnly(True)
        motion_row = QWidget(content)
        motion_layout = QHBoxLayout(motion_row)
        motion_layout.setContentsMargins(0, 0, 0, 0)
        motion_layout.setSpacing(4)
        motion_layout.addWidget(self.motion, 1)
        self.motion_browse = QPushButton("...", motion_row)
        self.motion_browse.setObjectName("MotionMMDFileButton")
        self.motion_browse.setToolTip("Choose VMD motion")
        self.motion_browse.setFixedWidth(30)
        motion_layout.addWidget(self.motion_browse)
        self.form.addRow("VMD Motion", motion_row)

        self.loop = QCheckBox("Loop", content)
        self.vmd_camera = QCheckBox("Use VMD camera when present", content)
        self.ik = QCheckBox("IK", content)
        self.physics = QCheckBox("Physics", content)
        self.gpu_skinning = QCheckBox("GPU skinning", content)
        self.physics_backend = QComboBox(content)
        self.physics_backend.addItems(["auto", "spring", "pybullet", "none"])
        self.form.addRow("Playback", self.loop)
        self.form.addRow("Camera", self.vmd_camera)
        self.form.addRow("Deformation", self._inline_checks(content, self.ik, self.physics, self.gpu_skinning))
        self.form.addRow("Physics Backend", self.physics_backend)
        self.rate = self._spin(content, 0.05, 8.0, 0.05, 2)
        self.spring = self._spin(content, 0.0, 1.0, 0.05, 2)
        self.form.addRow("Rate", self.rate)
        self.form.addRow("Spring Response", self.spring)

        self.yaw = self._spin(content, -180.0, 180.0, 1.0, 1)
        self.pitch = self._spin(content, -80.0, 45.0, 1.0, 1)
        self.zoom = self._spin(content, 0.05, 2.2, 0.05, 2)
        self.offset_y = self._spin(content, -2.0, 2.0, 0.01, 2)
        self.form.addRow("Yaw", self.yaw)
        self.form.addRow("Pitch", self.pitch)
        self.form.addRow("Framing Zoom", self.zoom)
        self.form.addRow("Vertical Offset", self.offset_y)

        self.bloom = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.key_light = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.fill_light = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.rim_light = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.ambient = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.shadow = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.form.addRow("Bloom", self.bloom)
        self.form.addRow("Key Light", self.key_light)
        self.form.addRow("Fill Light", self.fill_light)
        self.form.addRow("Rim Light", self.rim_light)
        self.form.addRow("Ambient", self.ambient)
        self.form.addRow("Shadow", self.shadow)

        self.skin = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.hair = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.eye = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.lip = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.matcap = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.emissive = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.form.addRow("Skin Warmth", self.skin)
        self.form.addRow("Hair Highlight", self.hair)
        self.form.addRow("Eye Highlight", self.eye)
        self.form.addRow("Lip Specular", self.lip)
        self.form.addRow("Matcap", self.matcap)
        self.form.addRow("Emissive", self.emissive)
        self.status = QLabel("", content)
        self.status.setObjectName("MotionMMDStatus")
        self.status.setWordWrap(True)
        self.form.addRow("Runtime", self.status)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

        for control in self._controls():
            signal = getattr(control, "valueChanged", None)
            if signal is None:
                signal = getattr(control, "toggled", None)
            if signal is None:
                signal = getattr(control, "currentTextChanged")
            signal.connect(lambda _value: self._emit_values())
        self.motion_browse.clicked.connect(self._browse_motion)
        self.set_layer(None)

    @staticmethod
    def _spin(parent, minimum: float, maximum: float, step: float, decimals: int) -> QDoubleSpinBox:
        control = QDoubleSpinBox(parent)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(decimals)
        return control

    @staticmethod
    def _inline_checks(parent, *controls: QWidget) -> QWidget:
        row = QWidget(parent)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        for control in controls:
            layout.addWidget(control)
        layout.addStretch(1)
        return row

    def _controls(self) -> tuple[QWidget, ...]:
        return (
            self.loop, self.vmd_camera, self.ik, self.physics, self.gpu_skinning,
            self.physics_backend, self.rate, self.spring, self.yaw, self.pitch,
            self.zoom, self.offset_y, self.bloom, self.key_light, self.fill_light,
            self.rim_light, self.ambient, self.shadow, self.skin, self.hair,
            self.eye, self.lip, self.matcap, self.emissive,
        )

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._loading = True
        supported = layer is not None and (
            layer.layer_type == MMD_SOURCE_KIND or layer.source.kind == MMD_SOURCE_KIND
        )
        self.setEnabled(supported)
        if not supported or layer is None:
            self._loading = False
            return
        params = layer.source.params
        asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
        view = params.get("view") if isinstance(params.get("view"), Mapping) else {}
        render = params.get("render") if isinstance(params.get("render"), Mapping) else {}
        lighting = render.get("lighting") if isinstance(render.get("lighting"), Mapping) else {}
        material = render.get("material") if isinstance(render.get("material"), Mapping) else {}
        playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
        catalog = params.get("catalog") if isinstance(params.get("catalog"), Mapping) else {}
        self.model.setText(str(asset.get("model_path") or layer.source.uri))
        self.motion.setText(str(asset.get("motion_path") or ""))
        self.loop.setChecked(bool(playback.get("loop", True)))
        self.vmd_camera.setChecked(bool(playback.get("use_vmd_camera", True)))
        self.ik.setChecked(bool(playback.get("enable_ik", True)))
        self.physics.setChecked(bool(playback.get("enable_physics", True)))
        self.gpu_skinning.setChecked(bool(playback.get("gpu_skinning", True)))
        self.physics_backend.setCurrentText(str(playback.get("physics_backend") or "auto"))
        self.rate.setValue(float(_default(playback.get("rate"), 1.0)))
        self.spring.setValue(float(playback.get("physics_spring_response", 0.6)))
        self.yaw.setValue(float(_default(view.get("yaw"), 0.0)))
        self.pitch.setValue(float(_default(view.get("pitch"), -4.0)))
        self.zoom.setValue(float(_default(view.get("zoom"), 0.96)))
        self.offset_y.setValue(float(_default(view.get("offset_y"), 0.02)))
        self.bloom.setValue(float(_default(render.get("bloom_strength"), 0.3)))
        for control, key, fallback in (
            (self.key_light, "key_intensity", 1.0),
            (self.fill_light, "fill_intensity", 0.32),
            (self.rim_light, "rim_intensity", 0.12),
            (self.ambient, "ambient_intensity", 0.4),
            (self.shadow, "shadow_strength", 0.64),
        ):
            control.setValue(float(_default(lighting.get(key), fallback)))
        for control, key in (
            (self.skin, "skin_warmth"), (self.hair, "hair_highlight"),
            (self.eye, "eye_highlight"), (self.lip, "lip_specular"),
            (self.matcap, "matcap_specular"), (self.emissive, "emissive"),
        ):
            control.setValue(float(_default(material.get(key), 1.0)))
        model_info = catalog.get("model") if isinstance(catalog.get("model"), Mapping) else {}
        motion_info = catalog.get("motion") if isinstance(catalog.get("motion"), Mapping) else {}
        try:
            from app.motion_designer.adapters.mmd import mmd_diagnostics

            runtime = mmd_diagnostics(layer.id)
        except Exception:
            runtime = {}
        cache_state = "Cache ready" if runtime.get("canonical_frame_cache") else "Cache pending"
        gpu_state = "GPU skinning" if runtime.get("track_gpu_skinning_active") else "GPU pending/fallback"
        physics_state = str(runtime.get("track_physics_backend") or playback.get("physics_backend") or "auto")
        self.status.setText(
            f"OpenGL Toon | {int(model_info.get('vertices', 0) or 0):,} vertices | "
            f"{int(model_info.get('bones', 0) or 0)} bones | "
            f"{int(motion_info.get('max_frame', 0) or 0)} VMD frames\n"
            f"{cache_state} | {gpu_state} | physics: {physics_state}"
        )
        self._loading = False

    def _browse_motion(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose VMD motion", self.motion.text(), "VMD Motion (*.vmd)")
        if path:
            self.motion.setText(str(Path(path).resolve()))
            self._emit_values()

    def _emit_values(self) -> None:
        if self._loading or not self.isEnabled():
            return
        self.source_changed.emit({
            "asset": {"motion_path": self.motion.text().strip()},
            "view": {
                "yaw": self.yaw.value(), "pitch": self.pitch.value(),
                "zoom": self.zoom.value(), "offset_y": self.offset_y.value(),
            },
            "render": {
                "bloom_strength": self.bloom.value(),
                "lighting": {
                    "key_intensity": self.key_light.value(),
                    "fill_intensity": self.fill_light.value(),
                    "rim_intensity": self.rim_light.value(),
                    "ambient_intensity": self.ambient.value(),
                    "shadow_strength": self.shadow.value(),
                },
                "material": {
                    "skin_warmth": self.skin.value(),
                    "hair_highlight": self.hair.value(),
                    "eye_highlight": self.eye.value(),
                    "lip_specular": self.lip.value(),
                    "matcap_specular": self.matcap.value(),
                    "emissive": self.emissive.value(),
                },
            },
            "playback": {
                "loop": self.loop.isChecked(),
                "use_vmd_camera": self.vmd_camera.isChecked(),
                "enable_ik": self.ik.isChecked(),
                "enable_physics": self.physics.isChecked(),
                "gpu_skinning": self.gpu_skinning.isChecked(),
                "physics_backend": self.physics_backend.currentText(),
                "physics_spring_response": self.spring.value(),
                "rate": self.rate.value(),
            },
        })


__all__ = ["MMDPanel"]
