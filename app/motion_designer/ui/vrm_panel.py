from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty, MotionLayer
from app.motion_designer.vrm_source import VRM_SOURCE_KIND


def _default(value: Any, fallback: Any, value_type: str = "scalar") -> Any:
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        return evaluate_property(AnimatedProperty.from_dict(value, value_type=value_type), 0.0)
    return fallback if value is None else value


class VRMPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionVRMPanel")
        self._loading = False
        self._loaded_asset = ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionVRMScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionVRMContent")
        self.form = QFormLayout(content)
        self.form.setContentsMargins(8, 6, 8, 8)
        self.form.setSpacing(5)

        self.asset = QLineEdit(content)
        self.asset.setReadOnly(True)
        asset_row = QWidget(content)
        asset_layout = QHBoxLayout(asset_row)
        asset_layout.setContentsMargins(0, 0, 0, 0)
        asset_layout.setSpacing(4)
        asset_layout.addWidget(self.asset, 1)
        self.asset_browse = QPushButton("...", asset_row)
        self.asset_browse.setObjectName("MotionVRMFileButton")
        self.asset_browse.setToolTip("Choose VRM avatar")
        self.asset_browse.setFixedWidth(30)
        asset_layout.addWidget(self.asset_browse)
        self.form.addRow("Avatar", asset_row)

        self.source_exposure = QComboBox(content)
        self.source_exposure.addItems(["face_only", "chest_up", "upper_body", "full_body", "unknown"])
        self.framing = QComboBox(content)
        self.framing.addItems(["bust_up", "half_body", "full_body"])
        self.allow_narrower = QCheckBox("Allow narrower than source", content)
        self.form.addRow("Source Exposure", self.source_exposure)
        self.form.addRow("Avatar Framing", self.framing)
        self.form.addRow("Visibility", self.allow_narrower)

        self.idle_motion = QCheckBox("Procedural idle", content)
        self.loop = QCheckBox("Loop", content)
        self.form.addRow("Playback", self._inline_checks(content, self.idle_motion, self.loop))
        self.rate = self._spin(content, 0.05, 8.0, 0.05, 2)
        self.idle_strength = self._spin(content, 0.0, 2.0, 0.05, 2)
        self.form.addRow("Rate", self.rate)
        self.form.addRow("Idle Strength", self.idle_strength)

        self.yaw = self._spin(content, -45.0, 45.0, 1.0, 1)
        self.pitch = self._spin(content, -35.0, 35.0, 1.0, 1)
        self.roll = self._spin(content, -30.0, 30.0, 1.0, 1)
        self.shoulder = self._spin(content, -25.0, 25.0, 1.0, 1)
        self.mouth = self._spin(content, 0.0, 1.0, 0.05, 2)
        self.blink_l = self._spin(content, 0.0, 1.0, 0.05, 2)
        self.blink_r = self._spin(content, 0.0, 1.0, 0.05, 2)
        self.form.addRow("Head Yaw", self.yaw)
        self.form.addRow("Head Pitch", self.pitch)
        self.form.addRow("Head Roll", self.roll)
        self.form.addRow("Shoulder Roll", self.shoulder)
        self.form.addRow("Mouth Open", self.mouth)
        self.form.addRow("Blink Left", self.blink_l)
        self.form.addRow("Blink Right", self.blink_r)

        self.target_width = self._spin(content, 0.1, 1.5, 0.02, 2)
        self.target_height = self._spin(content, 0.1, 1.5, 0.02, 2)
        self.center_x = self._spin(content, -0.5, 1.5, 0.01, 3)
        self.bottom_y = self._spin(content, 0.0, 1.5, 0.01, 3)
        self.form.addRow("Target Width", self.target_width)
        self.form.addRow("Target Height", self.target_height)
        self.form.addRow("Center X", self.center_x)
        self.form.addRow("Bottom Anchor", self.bottom_y)

        self.light_azimuth = self._spin(content, -180.0, 180.0, 1.0, 1)
        self.light_elevation = self._spin(content, -89.0, 89.0, 1.0, 1)
        self.direct = self._spin(content, 0.0, 4.0, 0.05, 2)
        self.ibl = self._spin(content, 0.0, 4.0, 0.05, 2)
        self.shadow = self._spin(content, 0.0, 1.0, 0.05, 2)
        self.form.addRow("Light Azimuth", self.light_azimuth)
        self.form.addRow("Light Elevation", self.light_elevation)
        self.form.addRow("Direct Light", self.direct)
        self.form.addRow("IBL Exposure", self.ibl)
        self.form.addRow("Shadow", self.shadow)

        self.status = QLabel("", content)
        self.status.setObjectName("MotionVRMStatus")
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
        self.asset_browse.clicked.connect(self._browse_asset)
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
            self.source_exposure, self.framing, self.allow_narrower,
            self.idle_motion, self.loop, self.rate, self.idle_strength,
            self.yaw, self.pitch, self.roll, self.shoulder, self.mouth,
            self.blink_l, self.blink_r, self.target_width, self.target_height,
            self.center_x, self.bottom_y, self.light_azimuth,
            self.light_elevation, self.direct, self.ibl, self.shadow,
        )

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._loading = True
        supported = layer is not None and (
            layer.layer_type == VRM_SOURCE_KIND or layer.source.kind == VRM_SOURCE_KIND
        )
        self.setEnabled(supported)
        if not supported or layer is None:
            self._loading = False
            return
        params = layer.source.params
        asset = params.get("asset") if isinstance(params.get("asset"), Mapping) else {}
        pose = params.get("pose") if isinstance(params.get("pose"), Mapping) else {}
        placement = params.get("placement") if isinstance(params.get("placement"), Mapping) else {}
        lighting = params.get("lighting") if isinstance(params.get("lighting"), Mapping) else {}
        playback = params.get("playback") if isinstance(params.get("playback"), Mapping) else {}
        catalog = params.get("catalog") if isinstance(params.get("catalog"), Mapping) else {}
        self._loaded_asset = str(asset.get("avatar_vrm") or layer.source.uri)
        self.asset.setText(self._loaded_asset)
        self.source_exposure.setCurrentText(str(placement.get("source_exposure") or "full_body"))
        self.framing.setCurrentText(str(placement.get("framing_preset") or "full_body"))
        self.allow_narrower.setChecked(bool(placement.get("allow_narrower_than_source", False)))
        self.idle_motion.setChecked(bool(playback.get("idle_motion", True)))
        self.loop.setChecked(bool(playback.get("loop", True)))
        self.rate.setValue(float(_default(playback.get("rate"), 1.0)))
        self.idle_strength.setValue(float(_default(pose.get("idle_strength"), 1.0)))
        for control, key, fallback in (
            (self.yaw, "yaw_deg", 0.0), (self.pitch, "pitch_deg", 0.0),
            (self.roll, "roll_deg", 0.0), (self.shoulder, "shoulder_roll_deg", 0.0),
            (self.mouth, "mouth_open", 0.0), (self.blink_l, "blink_l", 0.0),
            (self.blink_r, "blink_r", 0.0),
        ):
            control.setValue(float(_default(pose.get(key), fallback)))
        for control, key, fallback in (
            (self.target_width, "target_width_ratio", 0.72),
            (self.target_height, "target_height_ratio", 0.94),
            (self.center_x, "output_center_x", 0.50),
            (self.bottom_y, "output_bottom_y", 0.985),
        ):
            control.setValue(float(_default(placement.get(key), fallback)))
        for control, key, fallback in (
            (self.light_azimuth, "light_azimuth", 28.0),
            (self.light_elevation, "light_elevation", 42.0),
            (self.direct, "direct_strength", 0.65),
            (self.ibl, "ibl_exposure", 1.15),
            (self.shadow, "shadow_strength", 0.42),
        ):
            control.setValue(float(_default(lighting.get(key), fallback)))
        profile = catalog.get("profile") if isinstance(catalog.get("profile"), Mapping) else {}
        try:
            from app.motion_designer.adapters.vrm import vrm_diagnostics

            runtime = vrm_diagnostics(layer.id)
        except Exception:
            runtime = {}
        cache = "Cache ready" if runtime.get("canonical_frame_cache") else "Cache pending"
        render_seconds = float(runtime.get("frame_render_seconds", 0.0) or 0.0)
        timing = f" | {render_seconds:.2f}s last frame" if render_seconds > 0.0 else ""
        self.status.setText(
            f"VRM {profile.get('profile') or '?'} | MToon GPU | "
            f"{int(profile.get('humanoid_bone_count', 0) or 0)} humanoid bones\n"
            f"{cache}{timing} | cached playback; no realtime claim"
        )
        self._loading = False

    def _browse_asset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose VRM avatar", self.asset.text(), "VRM Avatar (*.vrm)")
        if path:
            self.asset.setText(str(Path(path).resolve()))
            self._emit_values()

    def _emit_values(self) -> None:
        if self._loading or not self.isEnabled():
            return
        changes: dict[str, Any] = {
            "pose": {
                "yaw_deg": self.yaw.value(), "pitch_deg": self.pitch.value(),
                "roll_deg": self.roll.value(), "shoulder_roll_deg": self.shoulder.value(),
                "mouth_open": self.mouth.value(), "blink_l": self.blink_l.value(),
                "blink_r": self.blink_r.value(), "idle_strength": self.idle_strength.value(),
            },
            "placement": {
                "source_exposure": self.source_exposure.currentText(),
                "framing_preset": self.framing.currentText(),
                "allow_narrower_than_source": self.allow_narrower.isChecked(),
                "target_width_ratio": self.target_width.value(),
                "target_height_ratio": self.target_height.value(),
                "output_center_x": self.center_x.value(),
                "output_bottom_y": self.bottom_y.value(),
            },
            "lighting": {
                "light_azimuth": self.light_azimuth.value(),
                "light_elevation": self.light_elevation.value(),
                "direct_strength": self.direct.value(),
                "ibl_exposure": self.ibl.value(),
                "shadow_strength": self.shadow.value(),
            },
            "playback": {
                "loop": self.loop.isChecked(), "idle_motion": self.idle_motion.isChecked(),
                "rate": self.rate.value(),
            },
        }
        current_asset = self.asset.text().strip()
        if current_asset and current_asset != self._loaded_asset:
            changes["asset"] = {"avatar_vrm": current_asset}
        self.source_changed.emit(changes)


__all__ = ["VRMPanel"]
