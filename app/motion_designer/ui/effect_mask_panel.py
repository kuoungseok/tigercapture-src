from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QStyle, QToolButton, QVBoxLayout, QWidget,
)

from app.motion_designer.schema import MotionLayer


EFFECT_PARAMS = {
    "brightness_contrast": (("brightness", -1.0, 1.0, 0.01), ("contrast", 0.0, 4.0, 0.05)),
    "saturation": (("amount", 0.0, 4.0, 0.05),),
    "gaussian_blur": (("radius", 0.0, 100.0, 0.25),),
    "glow": (("threshold", 0.0, 1.0, 0.01), ("radius", 0.0, 100.0, 0.25),
             ("intensity", 0.0, 5.0, 0.05)),
    "unsharp_mask": (("radius", 0.0, 30.0, 0.25), ("amount", 0.0, 5.0, 0.05)),
    "vignette": (("amount", 0.0, 1.0, 0.01), ("softness", 0.05, 1.0, 0.01)),
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
    item_changed = Signal(str, str, object)
    tracking_requested = Signal(str, object)
    tracking_cancel_requested = Signal(str)

    def __init__(self, mode: str, parent=None) -> None:
        super().__init__(parent)
        self.mode = mode
        self._loading = False
        self._items_by_id: dict[str, object] = {}
        self._layer: MotionLayer | None = None
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

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._layer = layer
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
        self._loading = False
        self._rebuild_parameters()

    def current_id(self) -> str:
        item = self.items.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def _clear_form(self) -> None:
        self._tracking_status_labels.clear()
        self._tracking_buttons.clear()
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
            mode.addItems(["add", "subtract", "intersect", "exclude"])
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
            track_button = QToolButton(self.parameter_host)
            track_button.setObjectName("MotionTrackingButton")
            track_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            track_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            busy = bool(state.get("busy"))
            track_button.setText("Cancel" if busy else "Track Video...")
            track_button.setEnabled(busy or tracking_box.currentText() in {"point", "planar"})
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
            self.parameter_form.addRow(key.replace("_", " ").title(), spin)

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
