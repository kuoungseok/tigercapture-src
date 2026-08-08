from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFormLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.schema import AnimatedProperty, MotionLayer


def _default(params: Mapping[str, Any], key: str, fallback: Any) -> Any:
    value = params.get(key, fallback)
    if isinstance(value, Mapping) and ({"default", "keyframes"} & set(value)):
        return evaluate_property(AnimatedProperty.from_dict(value), 0.0)
    return value


class ArPbrPanel(QWidget):
    source_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionArPbrPanel")
        self._loading = False
        self._layer_type = ""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("MotionArPbrScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget(self.scroll)
        content.setObjectName("MotionArPbrContent")
        self.form = QFormLayout(content)
        self.form.setContentsMargins(8, 6, 8, 8)
        self.form.setSpacing(5)
        self.asset = QLabel("", content)
        self.asset.setWordWrap(True)
        self.form.addRow("Asset", self.asset)

        self._object_controls: dict[str, QDoubleSpinBox] = {}
        self._camera_controls: dict[str, QDoubleSpinBox] = {}
        self._light_controls: dict[str, QDoubleSpinBox] = {}
        self._rows: dict[str, tuple[QLabel, QWidget]] = {}

        self._section("Object")
        self.auto_fit = QCheckBox("Fit model inside its layer", content)
        self.auto_fit.toggled.connect(lambda _checked: self._emit_values())
        auto_fit_label = QLabel("Auto Frame", content)
        self.form.addRow(auto_fit_label, self.auto_fit)
        self._rows["object_auto_fit"] = (auto_fit_label, self.auto_fit)
        for name, label, minimum, maximum, step in (
            ("rotation_x", "Pitch", -360, 360, .5),
            ("rotation_y", "Yaw", -360, 360, .5),
            ("rotation_z", "Roll", -360, 360, .5),
            ("scale", "Scale", .05, 20, .05),
            ("roughness", "Roughness", .04, 1, .01),
            ("metallic", "Metallic", 0, 1, .01),
            ("clearcoat", "Clearcoat", 0, 1, .01),
            ("ibl_exposure", "IBL Exposure", 0, 8, .05),
            ("shadow_strength", "Shadow", 0, 1, .01),
            ("ao_strength", "Contact AO", 0, 2, .02),
            ("bloom_strength", "Bloom", 0, 4, .02),
            ("depth_of_field_strength", "Depth Of Field", 0, 1, .01),
        ):
            self._object_controls[name] = self._spin(name, label, minimum, maximum, step)

        self._section("Camera")
        self.apply_to_2d = QCheckBox("Apply camera to 2D layers", content)
        self.apply_to_2d.toggled.connect(lambda _checked: self._emit_values())
        apply_2d_label = QLabel("2.5D Camera", content)
        self.form.addRow(apply_2d_label, self.apply_to_2d)
        self._rows["camera_apply_to_2d"] = (apply_2d_label, self.apply_to_2d)
        self.camera_projection = QComboBox(content)
        self.camera_projection.addItem("Perspective", "perspective")
        self.camera_projection.addItem("Orthographic", "orthographic")
        self.camera_projection.currentIndexChanged.connect(
            lambda _index: self._emit_values()
        )
        projection_label = QLabel("Projection", content)
        self.form.addRow(projection_label, self.camera_projection)
        self._rows["camera_projection"] = (
            projection_label,
            self.camera_projection,
        )
        self.orthographic_size = self._spin(
            "camera_orthographic_size", "Orthographic Size", 0.05, 100.0, 0.05,
        )
        self.parallax_strength = self._spin(
            "camera_parallax_strength", "Parallax", 0.0, 4.0, 0.05,
        )
        for name, label, minimum, maximum, step in (
            ("position_x", "Position X", -20, 20, .05),
            ("position_y", "Position Y", -20, 20, .05),
            ("position_z", "Position Z", .2, 20, .05),
            ("rotation_x", "Rotation X", -180, 180, .5),
            ("rotation_y", "Rotation Y", -360, 360, .5),
            ("rotation_z", "Rotation Z", -180, 180, .5),
            ("fov", "Field Of View", 10, 120, .5),
            ("focus_distance", "Focus Distance", .01, 100, .05),
            ("focus_range", "Focus Range", .001, 10, .01),
        ):
            self._camera_controls[name] = self._spin(f"camera_{name}", label, minimum, maximum, step)

        self._section("Light")
        self.light_type = QComboBox(content)
        self.light_type.addItem("Directional", "directional")
        self.light_type.addItem("Point", "point")
        self.light_type.addItem("Spot", "spot")
        self.light_type.currentIndexChanged.connect(
            lambda _index: self._emit_values()
        )
        light_type_label = QLabel("Type", content)
        self.form.addRow(light_type_label, self.light_type)
        self._rows["light_type"] = (light_type_label, self.light_type)
        for name, label, minimum, maximum, step in (
            ("azimuth", "Azimuth", -180, 180, .5),
            ("elevation", "Elevation", -20, 89, .5),
            ("position_x", "Position X", -100, 100, .05),
            ("position_y", "Position Y", -100, 100, .05),
            ("position_z", "Position Z", -100, 100, .05),
            ("intensity", "Intensity", 0, 4, .02),
            ("range", "Range", .05, 100, .05),
            ("spot_inner_angle", "Spot Inner", 0, 88, .5),
            ("spot_outer_angle", "Spot Outer", 1, 89, .5),
        ):
            self._light_controls[name] = self._spin(f"light_{name}", label, minimum, maximum, step)
        self.light_color = QPushButton("#ffffff", content)
        self.light_color.clicked.connect(self._pick_light_color)
        label = QLabel("Color", content)
        self.form.addRow(label, self.light_color)
        self._rows["light_color"] = (label, self.light_color)
        self.form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        self.set_layer(None)

    def _section(self, text: str) -> None:
        label = QLabel(text, self)
        label.setObjectName("MotionInspectorSection")
        self.form.addRow(label)
        self._rows[f"section_{text.lower()}"] = (label, label)

    def _spin(self, name: str, label_text: str, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
        control = QDoubleSpinBox(self)
        control.setRange(minimum, maximum)
        control.setSingleStep(step)
        control.setDecimals(3)
        control.valueChanged.connect(lambda _value: self._emit_values())
        label = QLabel(label_text, self)
        self.form.addRow(label, control)
        self._rows[name] = (label, control)
        return control

    def _set_group_visible(self, prefix: str, visible: bool) -> None:
        for name, (label, widget) in self._rows.items():
            if name == f"section_{prefix}" or name.startswith(f"{prefix}_"):
                label.setVisible(visible)
                widget.setVisible(visible)
        if prefix == "object":
            names = set(self._object_controls)
            for name in names:
                label, widget = self._rows[name]
                label.setVisible(visible)
                widget.setVisible(visible)

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._loading = True
        self._layer_type = layer.layer_type if layer is not None else ""
        supported = self._layer_type in {"ar_pbr", "camera", "light"}
        self.setEnabled(supported)
        self.asset.setVisible(self._layer_type == "ar_pbr")
        label = self.form.labelForField(self.asset)
        if label is not None:
            label.setVisible(self._layer_type == "ar_pbr")
        self._set_group_visible("object", self._layer_type == "ar_pbr")
        self._set_group_visible("camera", self._layer_type == "camera")
        self._set_group_visible("light", self._layer_type == "light")
        if layer is None:
            self._loading = False
            return
        params = layer.source.params
        if self._layer_type == "ar_pbr":
            self.asset.setText(layer.source.uri)
            obj = params.get("object") if isinstance(params.get("object"), Mapping) else {}
            material = params.get("material") if isinstance(params.get("material"), Mapping) else {}
            render = params.get("render") if isinstance(params.get("render"), Mapping) else {}
            rotation = list(_default(obj, "rotation", [0, 18, 0]))
            scale = list(_default(obj, "scale", [3.25, 3.25, 3.25]))
            values = {
                "rotation_x": rotation[0], "rotation_y": rotation[1], "rotation_z": rotation[2],
                "scale": scale[0], "roughness": _default(material, "roughness", .45),
                "metallic": _default(material, "metallic", 0), "clearcoat": _default(material, "clearcoat", 0),
                "ibl_exposure": _default(render, "ibl_exposure", 1.1),
                "shadow_strength": _default(render, "shadow_strength", .72),
                "ao_strength": _default(render, "ao_strength", .55),
                "bloom_strength": _default(render, "bloom_strength", 0),
                "depth_of_field_strength": _default(render, "depth_of_field_strength", 0),
            }
            self.auto_fit.setChecked(bool(render.get("auto_fit", True)))
            for name, value in values.items():
                self._object_controls[name].setValue(float(value))
        elif self._layer_type == "camera":
            position = list(_default(params, "position", [0, 0, 3.25]))
            rotation = list(_default(params, "rotation", [0, 0, 0]))
            values = {
                "position_x": position[0], "position_y": position[1], "position_z": position[2],
                "rotation_x": rotation[0], "rotation_y": rotation[1], "rotation_z": rotation[2],
                "fov": _default(params, "fov", 45), "focus_distance": _default(params, "focus_distance", 3.25),
                "focus_range": _default(params, "focus_range", .28),
            }
            for name, value in values.items():
                self._camera_controls[name].setValue(float(value))
            projection = str(_default(params, "projection", "perspective"))
            index = self.camera_projection.findData(projection)
            self.camera_projection.setCurrentIndex(max(0, index))
            self.orthographic_size.setValue(
                float(_default(params, "orthographic_size", 3.25))
            )
            self.apply_to_2d.setChecked(bool(params.get("apply_to_2d", False)))
            self.parallax_strength.setValue(float(params.get("parallax_strength", 1.0) or 0.0))
        elif self._layer_type == "light":
            light_type = str(params.get("light_type") or "directional")
            index = self.light_type.findData(light_type)
            self.light_type.setCurrentIndex(max(0, index))
            position = list(_default(params, "position", [0, 1.5, 2]))
            for name, fallback in (
                ("azimuth", 45),
                ("elevation", 45),
                ("position_x", position[0]),
                ("position_y", position[1]),
                ("position_z", position[2]),
                ("intensity", .42),
                ("range", 6.0),
                ("spot_inner_angle", 24.0),
                ("spot_outer_angle", 36.0),
            ):
                self._light_controls[name].setValue(float(_default(params, name, fallback)))
            color = list(_default(params, "color", [1, 1, 1]))
            self._set_color_button(color)
        self._loading = False

    def _pick_light_color(self) -> None:
        color = QColorDialog.getColor(QColor(self.light_color.text()), self, "Light Color")
        if color.isValid():
            self._set_color_button([color.redF(), color.greenF(), color.blueF()])
            self._emit_values()

    def _set_color_button(self, color: list[float]) -> None:
        rgb = [max(0, min(255, int(round(float(value) * 255)))) for value in color[:3]]
        text = "#{:02x}{:02x}{:02x}".format(*rgb)
        self.light_color.setText(text)
        self.light_color.setStyleSheet(f"background: {text}; color: {'#111111' if sum(rgb) > 420 else '#ffffff'};")

    def _emit_values(self) -> None:
        if self._loading:
            return
        if self._layer_type == "ar_pbr":
            c = self._object_controls
            scale = c["scale"].value()
            self.source_changed.emit({
                "object": {"rotation": [c["rotation_x"].value(), c["rotation_y"].value(), c["rotation_z"].value()],
                           "scale": [scale, scale, scale]},
                "material": {"roughness": c["roughness"].value(), "metallic": c["metallic"].value(),
                             "clearcoat": c["clearcoat"].value(),
                             "override_strength": 1.0 if c["roughness"].value() != .45 or c["metallic"].value() > 0 else 0.0},
                "render": {"auto_fit": self.auto_fit.isChecked(),
                           "ibl_exposure": c["ibl_exposure"].value(), "shadow_strength": c["shadow_strength"].value(),
                           "ao_strength": c["ao_strength"].value(), "bloom_strength": c["bloom_strength"].value(),
                           "depth_of_field_strength": c["depth_of_field_strength"].value()},
            })
        elif self._layer_type == "camera":
            c = self._camera_controls
            self.source_changed.emit({
                "position": [c["position_x"].value(), c["position_y"].value(), c["position_z"].value()],
                "rotation": [c["rotation_x"].value(), c["rotation_y"].value(), c["rotation_z"].value()],
                "fov": c["fov"].value(), "focus_distance": c["focus_distance"].value(),
                "focus_range": c["focus_range"].value(),
                "projection": str(
                    self.camera_projection.currentData() or "perspective"
                ),
                "orthographic_size": self.orthographic_size.value(),
                "apply_to_2d": self.apply_to_2d.isChecked(),
                "parallax_strength": self.parallax_strength.value(),
            })
        elif self._layer_type == "light":
            color = QColor(self.light_color.text())
            c = self._light_controls
            self.source_changed.emit({
                "light_type": str(self.light_type.currentData() or "directional"),
                "azimuth": c["azimuth"].value(), "elevation": c["elevation"].value(),
                "position": [
                    c["position_x"].value(),
                    c["position_y"].value(),
                    c["position_z"].value(),
                ],
                "intensity": c["intensity"].value(), "color": [color.redF(), color.greenF(), color.blueF()],
                "range": c["range"].value(),
                "spot_inner_angle": c["spot_inner_angle"].value(),
                "spot_outer_angle": c["spot_outer_angle"].value(),
            })


__all__ = ["ArPbrPanel"]
