"""Compact Figma-style Gradient and Effects editor for Painter UI objects."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_appearance import (
    UI_EFFECT_BLEND_MODES,
    merge_ui_appearance_style,
    normalize_ui_effect,
    normalize_ui_effects,
    normalize_ui_gradient,
)


class PainterUIAppearanceDialog(QDialog):
    """Edit provider-neutral appearance without exposing Figma-only payloads."""

    def __init__(
        self,
        style: Mapping[str, Any] | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Appearance")
        self.resize(520, 520)
        self._source_style = copy.deepcopy(dict(style or {}))
        self._syncing = False
        self._stop_index = -1
        self._effect_index = -1
        gradient = self._source_style.get("fill_gradient")
        self._gradient = (
            normalize_ui_gradient(gradient)
            if isinstance(gradient, Mapping)
            else None
        )
        self._effects = normalize_ui_effects(self._source_style.get("effects"))
        if not self._effects and isinstance(self._source_style.get("shadow"), Mapping):
            self._effects = [
                normalize_ui_effect(
                    {
                        "type": "drop_shadow",
                        **dict(self._source_style["shadow"]),
                    }
                )
            ]

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        tabs = QTabWidget()
        tabs.addTab(self._build_gradient_tab(), "Fill Gradient")
        tabs.addTab(self._build_effects_tab(), "Effects")
        root.addWidget(tabs, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._load_gradient()
        self._refresh_effects()

    def _build_gradient_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        form = QFormLayout()
        self.gradient_type_combo = QComboBox()
        self.gradient_type_combo.addItem("Solid", "")
        self.gradient_type_combo.addItem("Linear", "linear")
        self.gradient_type_combo.addItem("Radial", "radial")
        self.gradient_type_combo.currentIndexChanged.connect(
            self._gradient_type_changed
        )
        form.addRow("Fill", self.gradient_type_combo)
        self.gradient_angle_spin = QDoubleSpinBox()
        self.gradient_angle_spin.setRange(-180.0, 180.0)
        self.gradient_angle_spin.setSuffix(" deg")
        self.gradient_angle_spin.setDecimals(1)
        form.addRow("Angle", self.gradient_angle_spin)
        center = QFrame()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)
        self.gradient_center_x_spin = self._normalized_spin("X ")
        self.gradient_center_y_spin = self._normalized_spin("Y ")
        self.gradient_radius_spin = self._normalized_spin("R ")
        center_layout.addWidget(self.gradient_center_x_spin)
        center_layout.addWidget(self.gradient_center_y_spin)
        center_layout.addWidget(self.gradient_radius_spin)
        form.addRow("Radial", center)
        layout.addLayout(form)
        layout.addWidget(QLabel("Color Stops"))
        self.gradient_stop_list = QListWidget()
        self.gradient_stop_list.currentRowChanged.connect(
            self._gradient_stop_selected
        )
        layout.addWidget(self.gradient_stop_list, 1)
        stop_buttons = QHBoxLayout()
        add_stop = QPushButton("+")
        add_stop.setToolTip("Add gradient stop")
        add_stop.clicked.connect(self._add_gradient_stop)
        remove_stop = QPushButton("-")
        remove_stop.setToolTip("Remove selected gradient stop")
        remove_stop.clicked.connect(self._remove_gradient_stop)
        stop_buttons.addWidget(add_stop)
        stop_buttons.addWidget(remove_stop)
        stop_buttons.addStretch(1)
        layout.addLayout(stop_buttons)
        stop_form = QFormLayout()
        self.gradient_stop_position_spin = QDoubleSpinBox()
        self.gradient_stop_position_spin.setRange(0.0, 100.0)
        self.gradient_stop_position_spin.setSuffix("%")
        self.gradient_stop_position_spin.setDecimals(1)
        self.gradient_stop_position_spin.editingFinished.connect(
            self._commit_gradient_stop
        )
        self.gradient_stop_color_edit = QLineEdit()
        self.gradient_stop_color_edit.setPlaceholderText("#RRGGBBAA")
        self.gradient_stop_color_edit.editingFinished.connect(
            self._commit_gradient_stop
        )
        stop_form.addRow("Position", self.gradient_stop_position_spin)
        stop_form.addRow("Color", self.gradient_stop_color_edit)
        layout.addLayout(stop_form)
        return panel

    def _build_effects_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.effect_list = QListWidget()
        self.effect_list.currentRowChanged.connect(self._effect_selected)
        layout.addWidget(self.effect_list, 1)
        buttons = QHBoxLayout()
        for label, callback, tooltip in (
            ("+ Drop", self._add_drop_shadow, "Add Drop Shadow"),
            ("+ Inner", self._add_inner_shadow, "Add Inner Shadow"),
            ("-", self._remove_effect, "Remove selected effect"),
            ("Up", lambda: self._move_effect(-1), "Move effect up"),
            ("Down", lambda: self._move_effect(1), "Move effect down"),
        ):
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        form = QFormLayout()
        self.effect_type_combo = QComboBox()
        self.effect_type_combo.addItem("Drop Shadow", "drop_shadow")
        self.effect_type_combo.addItem("Inner Shadow", "inner_shadow")
        self.effect_color_edit = QLineEdit()
        self.effect_color_edit.setPlaceholderText("#00000066")
        metrics = QFrame()
        metrics_layout = QHBoxLayout(metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(4)
        self.effect_x_spin = self._metric_spin("X ")
        self.effect_y_spin = self._metric_spin("Y ")
        self.effect_blur_spin = self._metric_spin("Blur ", minimum=0.0)
        self.effect_spread_spin = self._metric_spin("Spread ")
        for widget in (
            self.effect_x_spin,
            self.effect_y_spin,
            self.effect_blur_spin,
            self.effect_spread_spin,
        ):
            metrics_layout.addWidget(widget)
        self.effect_blend_combo = QComboBox()
        for mode in sorted(UI_EFFECT_BLEND_MODES):
            self.effect_blend_combo.addItem(
                mode.replace("_", " ").title(),
                mode,
            )
        form.addRow("Type", self.effect_type_combo)
        form.addRow("Color", self.effect_color_edit)
        form.addRow("Geometry", metrics)
        form.addRow("Blend", self.effect_blend_combo)
        layout.addLayout(form)
        for widget in (
            self.effect_type_combo,
            self.effect_blend_combo,
        ):
            widget.currentIndexChanged.connect(self._commit_effect)
        self.effect_color_edit.editingFinished.connect(self._commit_effect)
        for widget in (
            self.effect_x_spin,
            self.effect_y_spin,
            self.effect_blur_spin,
            self.effect_spread_spin,
        ):
            widget.editingFinished.connect(self._commit_effect)
        return panel

    @staticmethod
    def _normalized_spin(prefix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-4.0, 4.0)
        spin.setDecimals(3)
        spin.setSingleStep(0.05)
        spin.setPrefix(prefix)
        return spin

    @staticmethod
    def _metric_spin(
        prefix: str,
        *,
        minimum: float = -512.0,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(minimum, 512.0)
        spin.setDecimals(1)
        spin.setPrefix(prefix)
        return spin

    def _load_gradient(self) -> None:
        self._syncing = True
        gradient = self._gradient
        gradient_type = gradient["type"] if gradient is not None else ""
        self.gradient_type_combo.setCurrentIndex(
            max(0, self.gradient_type_combo.findData(gradient_type))
        )
        if gradient is not None:
            start = gradient["start"]
            end = gradient["end"]
            angle = math.degrees(
                math.atan2(
                    end["y"] - start["y"],
                    end["x"] - start["x"],
                )
            )
            self.gradient_angle_spin.setValue(angle)
            self.gradient_center_x_spin.setValue(start["x"])
            self.gradient_center_y_spin.setValue(start["y"])
            self.gradient_radius_spin.setValue(
                math.hypot(
                    end["x"] - start["x"],
                    end["y"] - start["y"],
                )
            )
        self._syncing = False
        self._refresh_gradient_stops()
        self._sync_gradient_controls()

    def _gradient_type_changed(self) -> None:
        if self._syncing:
            return
        gradient_type = str(self.gradient_type_combo.currentData() or "")
        if not gradient_type:
            self._gradient = None
        else:
            self._gradient = normalize_ui_gradient(
                {
                    **(self._gradient or {}),
                    "type": gradient_type,
                }
            )
        self._refresh_gradient_stops()
        self._sync_gradient_controls()

    def _sync_gradient_controls(self) -> None:
        enabled = self._gradient is not None
        radial = (
            enabled
            and str(self.gradient_type_combo.currentData()) == "radial"
        )
        self.gradient_stop_list.setEnabled(enabled)
        self.gradient_stop_position_spin.setEnabled(enabled)
        self.gradient_stop_color_edit.setEnabled(enabled)
        self.gradient_angle_spin.setEnabled(enabled and not radial)
        for widget in (
            self.gradient_center_x_spin,
            self.gradient_center_y_spin,
            self.gradient_radius_spin,
        ):
            widget.setEnabled(radial)

    def _refresh_gradient_stops(self) -> None:
        self._syncing = True
        self.gradient_stop_list.clear()
        for stop in (self._gradient or {}).get("stops", []):
            self.gradient_stop_list.addItem(
                f"{float(stop['position']) * 100:.1f}%  {stop['color']}"
            )
        self._syncing = False
        if self.gradient_stop_list.count():
            self.gradient_stop_list.setCurrentRow(
                max(0, min(self._stop_index, self.gradient_stop_list.count() - 1))
            )
        else:
            self._stop_index = -1

    def _gradient_stop_selected(self, index: int) -> None:
        if self._syncing:
            return
        self._stop_index = index
        stops = (self._gradient or {}).get("stops", [])
        self._syncing = True
        if 0 <= index < len(stops):
            self.gradient_stop_position_spin.setValue(
                float(stops[index]["position"]) * 100.0
            )
            self.gradient_stop_color_edit.setText(str(stops[index]["color"]))
        else:
            self.gradient_stop_color_edit.clear()
        self._syncing = False

    def _commit_gradient_stop(self) -> None:
        if self._syncing or self._gradient is None:
            return
        if not 0 <= self._stop_index < len(self._gradient["stops"]):
            return
        self._gradient["stops"][self._stop_index] = {
            "position": self.gradient_stop_position_spin.value() / 100.0,
            "color": self.gradient_stop_color_edit.text().strip()
            or "#000000FF",
        }
        self._gradient["stops"].sort(key=lambda row: row["position"])
        self._refresh_gradient_stops()

    def _add_gradient_stop(self) -> None:
        if self._gradient is None:
            return
        stops = self._gradient["stops"]
        stops.append({"position": 0.5, "color": "#808080FF"})
        stops.sort(key=lambda row: row["position"])
        self._stop_index = next(
            index for index, row in enumerate(stops) if row["position"] == 0.5
        )
        self._refresh_gradient_stops()

    def _remove_gradient_stop(self) -> None:
        if self._gradient is None or len(self._gradient["stops"]) <= 2:
            return
        if 0 <= self._stop_index < len(self._gradient["stops"]):
            self._gradient["stops"].pop(self._stop_index)
            self._stop_index = max(0, self._stop_index - 1)
            self._refresh_gradient_stops()

    def _refresh_effects(self) -> None:
        self._syncing = True
        self.effect_list.clear()
        for effect in self._effects:
            label = (
                "Inner Shadow"
                if effect["type"] == "inner_shadow"
                else "Drop Shadow"
            )
            self.effect_list.addItem(
                f"{label}  {effect['color']}  "
                f"{effect['x']:.1f}, {effect['y']:.1f}"
            )
        self._syncing = False
        if self.effect_list.count():
            self.effect_list.setCurrentRow(
                max(0, min(self._effect_index, self.effect_list.count() - 1))
            )
        else:
            self._effect_index = -1
            self._sync_effect_controls()

    def _effect_selected(self, index: int) -> None:
        if self._syncing:
            return
        self._effect_index = index
        self._sync_effect_controls()

    def _sync_effect_controls(self) -> None:
        enabled = 0 <= self._effect_index < len(self._effects)
        for widget in (
            self.effect_type_combo,
            self.effect_color_edit,
            self.effect_x_spin,
            self.effect_y_spin,
            self.effect_blur_spin,
            self.effect_spread_spin,
            self.effect_blend_combo,
        ):
            widget.setEnabled(enabled)
        if not enabled:
            return
        effect = self._effects[self._effect_index]
        self._syncing = True
        self.effect_type_combo.setCurrentIndex(
            max(0, self.effect_type_combo.findData(effect["type"]))
        )
        self.effect_color_edit.setText(effect["color"])
        self.effect_x_spin.setValue(effect["x"])
        self.effect_y_spin.setValue(effect["y"])
        self.effect_blur_spin.setValue(effect["blur"])
        self.effect_spread_spin.setValue(effect["spread"])
        self.effect_blend_combo.setCurrentIndex(
            max(0, self.effect_blend_combo.findData(effect["blend_mode"]))
        )
        self._syncing = False

    def _commit_effect(self) -> None:
        if self._syncing or not 0 <= self._effect_index < len(self._effects):
            return
        self._effects[self._effect_index] = normalize_ui_effect(
            {
                "type": self.effect_type_combo.currentData(),
                "color": self.effect_color_edit.text().strip(),
                "x": self.effect_x_spin.value(),
                "y": self.effect_y_spin.value(),
                "blur": self.effect_blur_spin.value(),
                "spread": self.effect_spread_spin.value(),
                "blend_mode": self.effect_blend_combo.currentData(),
            }
        )
        self._refresh_effects()

    def _add_drop_shadow(self) -> None:
        self._effects.append(normalize_ui_effect({"type": "drop_shadow"}))
        self._effect_index = len(self._effects) - 1
        self._refresh_effects()

    def _add_inner_shadow(self) -> None:
        self._effects.append(normalize_ui_effect({"type": "inner_shadow"}))
        self._effect_index = len(self._effects) - 1
        self._refresh_effects()

    def _remove_effect(self) -> None:
        if 0 <= self._effect_index < len(self._effects):
            self._effects.pop(self._effect_index)
            self._effect_index = min(
                self._effect_index,
                len(self._effects) - 1,
            )
            self._refresh_effects()

    def _move_effect(self, direction: int) -> None:
        if not 0 <= self._effect_index < len(self._effects):
            return
        target = max(
            0,
            min(len(self._effects) - 1, self._effect_index + direction),
        )
        if target == self._effect_index:
            return
        row = self._effects.pop(self._effect_index)
        self._effects.insert(target, row)
        self._effect_index = target
        self._refresh_effects()

    def appearance_style(self) -> dict[str, Any]:
        if self._gradient is not None:
            gradient_type = str(self.gradient_type_combo.currentData() or "linear")
            if gradient_type == "radial":
                center = {
                    "x": self.gradient_center_x_spin.value(),
                    "y": self.gradient_center_y_spin.value(),
                }
                radius = max(0.0001, self.gradient_radius_spin.value())
                self._gradient.update(
                    {
                        "type": "radial",
                        "start": center,
                        "end": {"x": center["x"] + radius, "y": center["y"]},
                        "width": {"x": center["x"], "y": center["y"] + radius},
                    }
                )
            else:
                angle = math.radians(self.gradient_angle_spin.value())
                dx = math.cos(angle) * 0.5
                dy = math.sin(angle) * 0.5
                self._gradient.update(
                    {
                        "type": "linear",
                        "start": {"x": 0.5 - dx, "y": 0.5 - dy},
                        "end": {"x": 0.5 + dx, "y": 0.5 + dy},
                        "width": {"x": 0.5 - dy, "y": 0.5 + dx},
                    }
                )
        return merge_ui_appearance_style(
            self._source_style,
            gradient=self._gradient,
            effects=self._effects,
        )


def appearance_summary(style: Mapping[str, Any] | None) -> str:
    style = style if isinstance(style, Mapping) else {}
    gradient = style.get("fill_gradient")
    gradient_name = (
        str(gradient.get("type") or "Gradient").title()
        if isinstance(gradient, Mapping)
        else "Solid"
    )
    effects = normalize_ui_effects(style.get("effects"))
    if not effects and isinstance(style.get("shadow"), Mapping):
        effects = [normalize_ui_effect(style["shadow"])]
    suffix = f" · {len(effects)} FX" if effects else ""
    return gradient_name + suffix


__all__ = ["PainterUIAppearanceDialog", "appearance_summary"]
