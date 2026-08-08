from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QLineEdit, QStyle, QToolButton, QVBoxLayout, QWidget,
)

from app.icons import app_icon
from app.motion_designer.keyframes import evaluate_property
from app.motion_designer.adjustment_scope import (
    ADJUSTMENT_SCOPE_ALL_BELOW,
    ADJUSTMENT_SCOPE_SELECTED_BELOW,
    adjustment_scope,
    eligible_adjustment_target_ids,
)
from app.motion_designer.effect_group import (
    EFFECT_GROUP_DESCENDANTS,
    EFFECT_GROUP_SELECTED,
    descendant_layer_ids,
    effect_group_scope,
)
from app.motion_designer.schema import MotionComposition, MotionLayer


EFFECT_PARAMS = {
    "brightness_contrast": (("brightness", -1.0, 1.0, 0.01), ("contrast", 0.0, 4.0, 0.05)),
    "saturation": (("amount", 0.0, 4.0, 0.05),),
    "gaussian_blur": (("radius", 0.0, 100.0, 0.25),),
    "glow": (("threshold", 0.0, 1.0, 0.01), ("radius", 0.0, 100.0, 0.25),
             ("intensity", 0.0, 5.0, 0.05)),
    "unsharp_mask": (("radius", 0.0, 30.0, 0.25), ("amount", 0.0, 5.0, 0.05)),
    "vignette": (("amount", 0.0, 1.0, 0.01), ("softness", 0.05, 1.0, 0.01)),
    "drop_shadow": (
        ("offset_x", -500.0, 500.0, 1.0), ("offset_y", -500.0, 500.0, 1.0),
        ("radius", 0.0, 100.0, 0.25), ("opacity", 0.0, 1.0, 0.01),
    ),
    "light_sweep": (
        ("center_x", -1.0, 2.0, 0.01), ("center_y", -1.0, 2.0, 0.01),
        ("angle", -360.0, 360.0, 1.0), ("width", 0.005, 1.0, 0.01),
        ("softness", 0.01, 1.0, 0.01), ("intensity", 0.0, 8.0, 0.05),
    ),
    "fractal_noise": (
        ("amount", 0.0, 1.0, 0.01), ("scale", 2.0, 1000.0, 1.0),
        ("octaves", 1.0, 8.0, 1.0), ("contrast", 0.0, 8.0, 0.05),
        ("evolution", -10000.0, 10000.0, 0.05), ("speed", -20.0, 20.0, 0.05),
        ("seed", 0.0, 100000.0, 1.0),
    ),
    "posterize": (
        ("levels", 2.0, 64.0, 1.0), ("amount", 0.0, 1.0, 0.01),
    ),
    "directional_blur": (
        ("length", 0.0, 200.0, 0.5), ("angle", -360.0, 360.0, 1.0),
        ("samples", 2.0, 32.0, 1.0),
    ),
    "displacement": (
        ("strength", 0.0, 300.0, 0.5), ("scale", 2.0, 1000.0, 1.0),
        ("speed", -20.0, 20.0, 0.1),
    ),
    "corner_pin": (("amount", 0.0, 1.0, 0.01),),
    "mesh_warp": (
        ("amplitude_x", -300.0, 300.0, 0.5), ("amplitude_y", -300.0, 300.0, 0.5),
        ("frequency_x", 0.1, 20.0, 0.1), ("frequency_y", 0.1, 20.0, 0.1),
        ("phase", -100.0, 100.0, 0.05),
    ),
    "paper_fold": (
        ("strength", 0.0, 1.0, 0.01), ("angle", -180.0, 180.0, 1.0),
        ("width", 2.0, 500.0, 1.0),
    ),
    "paper_crumple": (
        ("amount", 0.0, 1.0, 0.01),
        ("crease_density", 1.0, 12.0, 1.0),
        ("sharpness", 1.0, 24.0, 0.25),
        ("depth", 0.0, 100.0, 0.5),
        ("residual_wrinkle", 0.0, 1.0, 0.01),
        ("seed", 0.0, 100000.0, 1.0),
    ),
    "scan_cleanup": (
        ("white_balance", 0.0, 1.0, 0.01),
        ("paper_remove", 0.0, 1.0, 0.01),
        ("ink_preserve", 0.0, 1.0, 0.01),
        ("threshold", 0.05, 0.98, 0.01),
    ),
    "craft_style": (
        ("amount", 0.0, 1.0, 0.01),
        ("grain_amount", 0.0, 1.0, 0.01),
        ("grain_size", 1.0, 12.0, 0.1),
        ("grain_cadence", 0.1, 120.0, 0.5),
        ("weave_x", 0.0, 100.0, 0.1),
        ("weave_y", 0.0, 100.0, 0.1),
        ("weave_rotation", 0.0, 10.0, 0.01),
        ("weave_frequency", 0.0, 30.0, 0.1),
        ("flicker_amount", 0.0, 1.0, 0.001),
        ("flicker_frequency", 0.0, 60.0, 0.1),
        ("flicker_warmth", -1.0, 1.0, 0.01),
        ("dust_amount", 0.0, 1.0, 0.01),
        ("scratch_amount", 0.0, 1.0, 0.01),
        ("misregistration", 0.0, 20.0, 0.1),
        ("halation_amount", 0.0, 1.0, 0.01),
        ("halation_radius", 0.1, 100.0, 0.25),
        ("warmth", -1.0, 1.0, 0.01),
        ("vhs_amount", 0.0, 1.0, 0.01),
        ("edge_roughness", 0.0, 1.0, 0.01),
        ("loop_period", 0.1, 3600.0, 0.1),
        ("seed", 0.0, 2147483647.0, 1.0),
    ),
    "painterly_look": (
        ("amount", 0.0, 1.0, 0.01),
        ("color_levels", 2.0, 32.0, 1.0),
        ("toon_amount", 0.0, 1.0, 0.01),
        ("smoothing", 0.0, 1.0, 0.01),
        ("edge_strength", 0.0, 2.0, 0.01),
        ("edge_threshold", 0.0, 1.0, 0.01),
        ("edge_softness", 0.001, 1.0, 0.01),
        ("brush_amount", 0.0, 1.0, 0.01),
        ("brush_scale", 2.0, 256.0, 1.0),
        ("granulation", 0.0, 1.0, 0.01),
        ("paper_amount", 0.0, 1.0, 0.01),
        ("hatch_amount", 0.0, 1.0, 0.01),
        ("hatch_spacing", 2.0, 128.0, 1.0),
        ("working_limit", 320.0, 4096.0, 16.0),
        ("seed", 0.0, 2147483647.0, 1.0),
    ),
    "chroma_key": (
        ("similarity", 0.0, 1.0, 0.01), ("softness", 0.001, 1.0, 0.01),
        ("choke", -100.0, 100.0, 0.5), ("feather", 0.0, 100.0, 0.25),
        ("despill", 0.0, 1.0, 0.01),
    ),
    "luma_key": (
        ("threshold", 0.0, 1.0, 0.01), ("softness", 0.001, 1.0, 0.01),
        ("choke", -100.0, 100.0, 0.5), ("feather", 0.0, 100.0, 0.25),
    ),
    "difference_key": (
        ("threshold", 0.0, 1.0, 0.01), ("softness", 0.001, 1.0, 0.01),
        ("choke", -100.0, 100.0, 0.5), ("feather", 0.0, 100.0, 0.25),
    ),
}

EFFECT_STRING_PARAMS = {
    "chroma_key": (("key_color", "#00ff00"),),
    "difference_key": (("reference_uri", ""),),
    "drop_shadow": (("color", "#000000"),),
    "light_sweep": (("color", "#ffffff"),),
}

MASK_PARAMS = (
    ("x", -100000.0, 100000.0, 1.0), ("y", -100000.0, 100000.0, 1.0),
    ("width", 0.0, 100000.0, 1.0), ("height", 0.0, 100000.0, 1.0),
    ("radius", 0.0, 10000.0, 1.0),
    ("feather", 0.0, 1000.0, 0.5), ("expansion", -1000.0, 1000.0, 0.5),
    ("opacity", 0.0, 1.0, 0.01),
)


class EffectMaskPanel(QWidget):
    add_requested = Signal(str)
    delete_requested = Signal(str)
    parameter_changed = Signal(str, str, object)
    keyframe_toggled = Signal(str, str, object, bool)
    item_changed = Signal(str, str, object)
    tracking_requested = Signal(str, object)
    tracking_cancel_requested = Signal(str)
    adjustment_scope_changed = Signal(str, object)
    effect_group_scope_changed = Signal(str, object)

    def __init__(self, mode: str, parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self._loading = False
        self._items_by_id: dict[str, object] = {}
        self._layer: MotionLayer | None = None
        self._composition: MotionComposition | None = None
        self._time_ms = 0
        self._parameter_controls: dict[tuple[str, str], QDoubleSpinBox] = {}
        self._keyframe_buttons: dict[tuple[str, str], QToolButton] = {}
        self._tracking_states: dict[str, dict[str, object]] = {}
        self._tracking_status_labels: dict[str, QLabel] = {}
        self._tracking_buttons: dict[str, QToolButton] = {}
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        tools = QHBoxLayout()
        self.kind = QComboBox(self)
        if mode == "effect":
            self.kind.addItems(list(EFFECT_PARAMS))
        else:
            self.kind.addItems(["rectangle", "ellipse", "path"])
        add = QToolButton(self)
        add.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        add.setToolTip(f"Add {mode}")
        remove = QToolButton(self)
        remove.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        remove.setToolTip(f"Delete {mode}")
        tools.addWidget(self.kind, 1)
        tools.addWidget(add)
        tools.addWidget(remove)
        root.addLayout(tools)
        self.scope_host = QWidget(self)
        scope_layout = QFormLayout(self.scope_host)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        self.scope_mode = QComboBox(self.scope_host)
        self.scope_mode.addItem("All Layers Below", ADJUSTMENT_SCOPE_ALL_BELOW)
        self.scope_mode.addItem(
            "Selected Layers Below",
            ADJUSTMENT_SCOPE_SELECTED_BELOW,
        )
        self.scope_layers = QListWidget(self.scope_host)
        self.scope_layers.setMaximumHeight(112)
        scope_layout.addRow("Scope", self.scope_mode)
        scope_layout.addRow("Targets", self.scope_layers)
        self.scope_host.setVisible(False)
        root.addWidget(self.scope_host)
        self.items = QListWidget(self)
        self.items.setMinimumHeight(80)
        root.addWidget(self.items)
        self.parameter_host = QWidget(self)
        self.parameter_form = QFormLayout(self.parameter_host)
        root.addWidget(self.parameter_host)
        root.addStretch(1)
        add.clicked.connect(lambda: self.add_requested.emit(self.kind.currentText()))
        remove.clicked.connect(self._delete_current)
        self.items.currentItemChanged.connect(lambda _current, _previous: self._rebuild_parameters())
        self.scope_mode.currentIndexChanged.connect(self._emit_adjustment_scope)
        self.scope_layers.itemChanged.connect(
            lambda _item: self._emit_adjustment_scope()
        )

    def set_layer(self, layer: MotionLayer | None) -> None:
        self.set_context(layer, self._composition)

    def set_context(
        self,
        layer: MotionLayer | None,
        composition: MotionComposition | None,
    ) -> None:
        self._layer = layer
        self._composition = composition
        selected_id = self.current_id()
        self._loading = True
        self.items.clear()
        values = [] if layer is None else (layer.effects if self.mode == "effect" else layer.masks)
        self._items_by_id = {item.id: item for item in values}
        for item in values:
            row = QListWidgetItem(item.kind.replace("_", " ").title())
            row.setData(Qt.UserRole, item.id)
            self.items.addItem(row)
            if item.id == selected_id:
                self.items.setCurrentItem(row)
        if self.items.currentItem() is None and self.items.count():
            self.items.setCurrentRow(0)
        self.setEnabled(layer is not None)
        self._refresh_effect_scope()
        self._loading = False
        self._rebuild_parameters()

    def _refresh_effect_scope(self) -> None:
        visible = bool(
            self.mode == "effect"
            and self._layer is not None
            and self._layer.layer_type in {"adjustment", "group"}
            and self._composition is not None
        )
        self.scope_host.setVisible(visible)
        self.scope_layers.clear()
        if not visible or self._layer is None or self._composition is None:
            return
        is_group = self._layer.layer_type == "group"
        self.scope_mode.blockSignals(True)
        self.scope_mode.clear()
        if is_group:
            self.scope_mode.addItem("All Descendants", EFFECT_GROUP_DESCENDANTS)
            self.scope_mode.addItem("Selected Descendants", EFFECT_GROUP_SELECTED)
            value = effect_group_scope(self._layer)
            eligible_ids = descendant_layer_ids(
                self._composition,
                self._layer.id,
            )
            selected_mode = EFFECT_GROUP_SELECTED
        else:
            self.scope_mode.addItem("All Layers Below", ADJUSTMENT_SCOPE_ALL_BELOW)
            self.scope_mode.addItem(
                "Selected Layers Below",
                ADJUSTMENT_SCOPE_SELECTED_BELOW,
            )
            value = adjustment_scope(self._layer)
            eligible_ids = eligible_adjustment_target_ids(
                self._composition,
                self._layer.id,
            )
            selected_mode = ADJUSTMENT_SCOPE_SELECTED_BELOW
        index = self.scope_mode.findData(value["mode"])
        self.scope_mode.setCurrentIndex(max(0, index))
        self.scope_mode.blockSignals(False)
        selected = set(value["layer_ids"])
        by_id = {layer.id: layer for layer in self._composition.layers}
        for layer_id in eligible_ids:
            layer = by_id[layer_id]
            row = QListWidgetItem(layer.name)
            row.setData(Qt.UserRole, layer.id)
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(
                Qt.Checked if layer.id in selected else Qt.Unchecked
            )
            self.scope_layers.addItem(row)
        self.scope_layers.setVisible(
            value["mode"] == selected_mode
        )

    def _emit_adjustment_scope(self, *_args) -> None:
        if self._loading or self.scope_host.isHidden():
            return
        is_group = bool(self._layer and self._layer.layer_type == "group")
        fallback = EFFECT_GROUP_DESCENDANTS if is_group else ADJUSTMENT_SCOPE_ALL_BELOW
        selected_mode = EFFECT_GROUP_SELECTED if is_group else ADJUSTMENT_SCOPE_SELECTED_BELOW
        mode = str(self.scope_mode.currentData() or fallback)
        self.scope_layers.setVisible(mode == selected_mode)
        layer_ids = [
            str(row.data(Qt.UserRole) or "")
            for index in range(self.scope_layers.count())
            for row in [self.scope_layers.item(index)]
            if row.checkState() == Qt.Checked
        ]
        if is_group:
            self.effect_group_scope_changed.emit(mode, layer_ids)
        else:
            self.adjustment_scope_changed.emit(mode, layer_ids)

    def current_id(self) -> str:
        item = self.items.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def _clear_form(self) -> None:
        self._tracking_status_labels.clear()
        self._tracking_buttons.clear()
        self._parameter_controls.clear()
        self._keyframe_buttons.clear()
        while self.parameter_form.rowCount():
            self.parameter_form.removeRow(0)

    def _rebuild_parameters(self) -> None:
        self._clear_form()
        item_id = self.current_id()
        item = self._items_by_id.get(item_id)
        if item is None:
            return
        if self.mode == "mask":
            mode = QComboBox(self.parameter_host)
            mode.addItems(["add", "subtract", "intersect", "exclude", "garbage", "holdout"])
            mode.setCurrentText("add" if item.mode == "alpha" else item.mode)
            mode.currentTextChanged.connect(
                lambda value, row_id=item_id: self._emit_item(row_id, "mode", value)
            )
            self.parameter_form.addRow("Mode", mode)
            tracking = item.metadata.get("tracking_cache", {})
            tracking_mode = str(tracking.get("mode") or "none") if isinstance(tracking, dict) else "none"
            tracking_box = QComboBox(self.parameter_host)
            tracking_box.addItems(["none", "point", "planar"])
            tracking_box.setCurrentText(tracking_mode if tracking_mode in {"point", "planar"} else "none")
            tracking_box.currentTextChanged.connect(
                lambda value, row_id=item_id: self._emit_item(row_id, "tracking_mode", value)
            )
            self.parameter_form.addRow("Tracking", tracking_box)
            sample_count = len(tracking.get("samples", [])) if isinstance(tracking, dict) else 0
            metadata = tracking.get("metadata", {}) if isinstance(tracking, dict) else {}
            source_uri = str(metadata.get("source_uri") or "") if isinstance(metadata, dict) else ""
            if not source_uri and self._layer is not None:
                source_uri = str(self._layer.source.uri or "")
            source_status = QLabel(Path(source_uri).name if source_uri else "Choose on Track", self.parameter_host)
            source_status.setToolTip(source_uri or "A source video picker opens when tracking starts.")
            self.parameter_form.addRow("Source", source_status)
            state = self._tracking_states.get(item_id, {})
            cached_message = f"{sample_count} cached samples"
            if isinstance(metadata, dict) and metadata.get("terminated_reason") == "shot_cut":
                cached_message += " - stopped at cut"
            sample_status = QLabel(
                str(state.get("message") or cached_message),
                self.parameter_host,
            )
            sample_status.setToolTip(
                "Point/planar samples are generated from the selected video and shared by preview and export."
            )
            self.parameter_form.addRow("Track Cache", sample_status)
            self._tracking_status_labels[item_id] = sample_status
            frozen = bool(tracking.get("frozen", False)) if isinstance(tracking, dict) else False
            freeze_box = QCheckBox("Freeze propagated matte", self.parameter_host)
            freeze_box.setChecked(frozen)
            freeze_box.setEnabled(sample_count > 0)
            freeze_box.setToolTip(
                "Locks the current propagation cache so tracking cannot overwrite approved matte samples."
            )
            freeze_box.toggled.connect(
                lambda value, row_id=item_id: self._emit_item(row_id, "tracking_frozen", value)
            )
            self.parameter_form.addRow("Propagation", freeze_box)
            track_button = QToolButton(self.parameter_host)
            track_button.setObjectName("MotionTrackingButton")
            track_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            track_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            busy = bool(state.get("busy"))
            track_button.setText("Cancel" if busy else ("Frozen" if frozen else "Track Video..."))
            track_button.setEnabled(busy or (not frozen and tracking_box.currentText() in {"point", "planar"}))
            track_button.clicked.connect(
                lambda _checked=False, row_id=item_id: self._request_tracking(row_id)
            )
            self.parameter_form.addRow("Analysis", track_button)
            self._tracking_buttons[item_id] = track_button
        specs = EFFECT_PARAMS.get(item.kind, ()) if self.mode == "effect" else MASK_PARAMS
        for key, minimum, maximum, step in specs:
            spin = QDoubleSpinBox(self.parameter_host)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            spin.setDecimals(3)
            prop = item.params.get(key)
            if prop is not None and isinstance(prop.default, (int, float)):
                spin.setValue(float(prop.default))
            spin.valueChanged.connect(
                lambda value, row_id=item_id, name=key: self._emit_parameter(row_id, name, value)
            )
            keyframe = QToolButton(self.parameter_host)
            keyframe.setObjectName("MotionParameterKeyframeButton")
            keyframe.setAutoRaise(True)
            keyframe.setCheckable(True)
            keyframe.setFixedSize(24, 24)
            keyframe.clicked.connect(
                lambda _checked=False, row_id=item_id, name=key:
                self._toggle_keyframe(row_id, name)
            )
            row = QWidget(self.parameter_host)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            row_layout.addWidget(spin, 1)
            row_layout.addWidget(keyframe)
            self._parameter_controls[(item_id, key)] = spin
            self._keyframe_buttons[(item_id, key)] = keyframe
            self.parameter_form.addRow(key.replace("_", " ").title(), row)
        if self.mode == "effect":
            for key, default in EFFECT_STRING_PARAMS.get(item.kind, ()):
                editor = QLineEdit(self.parameter_host)
                prop = item.params.get(key)
                value = prop.default if prop is not None else default
                editor.setText(str(value or default))
                editor.editingFinished.connect(
                    lambda row_id=item_id, name=key, field=editor:
                    self._emit_parameter(row_id, name, field.text())
                )
                self.parameter_form.addRow(
                    key.replace("_", " ").title(),
                    editor,
                )
        self._refresh_animated_values()

    def set_time(self, time_ms: int | float) -> None:
        self._time_ms = max(0, int(round(float(time_ms))))
        self._refresh_animated_values()

    def keyframe_button(self, item_id: str, key: str) -> QToolButton | None:
        return self._keyframe_buttons.get((str(item_id), str(key)))

    def parameter_control(self, item_id: str, key: str) -> QDoubleSpinBox | None:
        return self._parameter_controls.get((str(item_id), str(key)))

    def _refresh_animated_values(self) -> None:
        for (item_id, key), control in self._parameter_controls.items():
            item = self._items_by_id.get(item_id)
            prop = item.params.get(key) if item is not None else None
            if prop is None:
                continue
            value = evaluate_property(prop, self._time_ms)
            if isinstance(value, (int, float)):
                control.blockSignals(True)
                control.setValue(float(value))
                control.blockSignals(False)
            button = self._keyframe_buttons.get((item_id, key))
            if button is None:
                continue
            at_keyframe = any(
                int(frame.time_ms) == self._time_ms
                for frame in prop.keyframes
            )
            animated = bool(prop.keyframes)
            button.blockSignals(True)
            button.setChecked(at_keyframe)
            button.blockSignals(False)
            color = "#F0B65A" if at_keyframe else ("#78A8D8" if animated else "#707985")
            button.setIcon(app_icon("keyframe", size=13, color=color))
            button.setToolTip(
                "Remove keyframe at current time"
                if at_keyframe
                else "Add keyframe at current time"
            )

    def _toggle_keyframe(self, item_id: str, key: str) -> None:
        item = self._items_by_id.get(item_id)
        prop = item.params.get(key) if item is not None else None
        control = self._parameter_controls.get((item_id, key))
        if prop is None or control is None:
            return
        at_keyframe = any(
            int(frame.time_ms) == self._time_ms
            for frame in prop.keyframes
        )
        value = evaluate_property(prop, self._time_ms)
        if isinstance(value, (int, float)):
            value = float(control.value())
        self.keyframe_toggled.emit(item_id, key, value, not at_keyframe)

    def _emit_parameter(self, item_id: str, key: str, value: float) -> None:
        if not self._loading:
            self.parameter_changed.emit(item_id, key, value)

    def _emit_item(self, item_id: str, key: str, value: object) -> None:
        if not self._loading:
            self.item_changed.emit(item_id, key, value)

    def _request_tracking(self, item_id: str) -> None:
        state = self._tracking_states.get(item_id, {})
        if state.get("busy"):
            self.tracking_cancel_requested.emit(item_id)
            return
        item = self._items_by_id.get(item_id)
        if item is None:
            return
        tracking = item.metadata.get("tracking_cache", {})
        mode = str(tracking.get("mode") or "point") if isinstance(tracking, dict) else "point"
        source_path = str(self._layer.source.uri or "") if self._layer is not None else ""
        if not source_path.lower().endswith((".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v")):
            source_path, _filter = QFileDialog.getOpenFileName(
                self,
                "Select tracking video",
                "",
                "Video (*.mp4 *.mov *.mkv *.avi *.webm *.m4v);;All files (*)",
            )
        if source_path:
            self.tracking_requested.emit(item_id, {"video_path": source_path, "mode": mode})

    def set_tracking_progress(self, item_id: str, done: int, total: int) -> None:
        percent = int(round(max(0, done) * 100.0 / max(1, total)))
        self._tracking_states[item_id] = {
            "busy": True,
            "message": f"Tracking... {percent}%",
        }
        label = self._tracking_status_labels.get(item_id)
        if label is not None:
            label.setText(f"Tracking... {percent}%")
        button = self._tracking_buttons.get(item_id)
        if button is not None:
            button.setText("Cancel")

    def set_tracking_status(self, item_id: str, message: str, *, busy: bool = False) -> None:
        self._tracking_states[item_id] = {"busy": bool(busy), "message": str(message)}
        label = self._tracking_status_labels.get(item_id)
        if label is not None:
            label.setText(str(message))
        button = self._tracking_buttons.get(item_id)
        if button is not None:
            button.setText("Cancel" if busy else "Track Video...")

    def _delete_current(self) -> None:
        item_id = self.current_id()
        if item_id:
            self.delete_requested.emit(item_id)
