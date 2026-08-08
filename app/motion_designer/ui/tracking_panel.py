from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QComboBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.tracking_workflow import track_asset_diagnostics


class TrackingPanel(QWidget):
    analyze_requested = Signal(str)
    apply_requested = Signal(str, bool)
    corner_pin_requested = Signal(str, str)
    relink_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layer: MotionLayer | None = None
        self._assets: dict[str, dict] = {}
        self._corner_pin_effect_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        self.assets = QListWidget(self)
        self.assets.setMinimumHeight(100)
        root.addWidget(self.assets)
        analyze_tools = QHBoxLayout()
        self.analysis_mode = QComboBox(self)
        self.analysis_mode.addItem("Point", "point")
        self.analysis_mode.addItem("Planar", "planar")
        self.analysis_mode.addItem("Face", "face")
        self.analyze = QPushButton("Analyze Video", self)
        analyze_tools.addWidget(self.analysis_mode)
        analyze_tools.addWidget(self.analyze)
        root.addLayout(analyze_tools)
        self.status = QLabel("", self)
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        details = QFormLayout()
        self.kind = QLabel("-", self)
        self.samples = QLabel("-", self)
        self.confidence = QLabel("-", self)
        self.occlusion = QLabel("-", self)
        self.reacquire = QLabel("-", self)
        self.maximum_step = QLabel("-", self)
        self.outliers = QLabel("-", self)
        self.revision = QLabel("-", self)
        self.quality = QLabel("-", self)
        details.addRow("Type", self.kind)
        details.addRow("Samples", self.samples)
        details.addRow("Confidence", self.confidence)
        details.addRow("Occlusion", self.occlusion)
        details.addRow("Reacquire", self.reacquire)
        details.addRow("Max step", self.maximum_step)
        details.addRow("Rejected", self.outliers)
        details.addRow("Source", self.revision)
        details.addRow("Quality", self.quality)
        root.addLayout(details)
        tools = QHBoxLayout()
        self.attach = QPushButton("Attach", self)
        self.stabilize = QPushButton("Stabilize", self)
        self.corner_pin = QPushButton("Pin", self)
        self.corner_pin.setToolTip("Bake the planar track into the selected layer's Corner Pin effect")
        self.relink = QPushButton("Relink...", self)
        tools.addWidget(self.attach)
        tools.addWidget(self.stabilize)
        tools.addWidget(self.corner_pin)
        tools.addWidget(self.relink)
        root.addLayout(tools)
        root.addStretch(1)
        self.assets.currentItemChanged.connect(
            lambda _current, _previous: self._update_details()
        )
        self.analyze.clicked.connect(
            lambda: self.analyze_requested.emit(
                str(self.analysis_mode.currentData() or "point")
            )
        )
        self.attach.clicked.connect(lambda: self._emit_apply(False))
        self.stabilize.clicked.connect(lambda: self._emit_apply(True))
        self.corner_pin.clicked.connect(self._emit_corner_pin)
        self.relink.clicked.connect(
            lambda: self.relink_requested.emit(self.current_track_id())
        )
        self._update_details()

    def set_analysis_status(self, text: str, *, busy: bool = False) -> None:
        self.status.setText(str(text))
        self.analyze.setEnabled(not busy and self._layer is not None)
        self.analysis_mode.setEnabled(not busy and self._layer is not None)

    def set_context(
        self,
        composition: MotionComposition,
        layer: MotionLayer | None,
    ) -> None:
        selected_id = self.current_track_id()
        self._layer = layer
        self._corner_pin_effect_id = next(
            (
                item.id
                for item in (layer.effects if layer is not None else [])
                if str(item.kind or "").lower() == "corner_pin"
            ),
            "",
        )
        self.assets.clear()
        self._assets = {}
        for value in composition.metadata.get("tracking_assets", []):
            if not isinstance(value, Mapping):
                continue
            asset = dict(value)
            track_id = str(asset.get("id") or "")
            if not track_id:
                continue
            self._assets[track_id] = asset
            row = QListWidgetItem(str(asset.get("name") or "Motion Track"))
            row.setData(Qt.UserRole, track_id)
            self.assets.addItem(row)
            if track_id == selected_id:
                self.assets.setCurrentItem(row)
        if self.assets.currentItem() is None and self.assets.count():
            self.assets.setCurrentRow(0)
        self._update_details()
        self.set_analysis_status(self.status.text(), busy=False)

    def current_track_id(self) -> str:
        row = self.assets.currentItem()
        return str(row.data(Qt.UserRole) or "") if row else ""

    def _update_details(self) -> None:
        asset = self._assets.get(self.current_track_id())
        current_revision = (
            str(self._layer.source.revision or "")
            if self._layer is not None else ""
        )
        if asset is None:
            values = {}
        else:
            values = track_asset_diagnostics(
                asset,
                current_source_revision=current_revision,
            )
        self.kind.setText(str(values.get("kind") or "-").replace("_", " ").title())
        self.samples.setText(str(values.get("sample_count", "-")))
        confidence = values.get("mean_confidence")
        self.confidence.setText(
            f"{float(confidence) * 100.0:.1f}%"
            if confidence is not None else "-"
        )
        self.occlusion.setText(str(values.get("occluded_sample_count", "-")))
        reacquire = values.get("reacquire_count")
        predicted = int(values.get("predicted_sample_count", 0) or 0)
        self.reacquire.setText(
            (
                f"{reacquire}"
                + (f" ({predicted} predicted)" if predicted else "")
            )
            if reacquire is not None else "-"
        )
        maximum_step = values.get("maximum_step_px")
        self.maximum_step.setText(
            f"{float(maximum_step):.1f} px"
            if maximum_step is not None else "-"
        )
        self.outliers.setText(str(values.get("motion_outlier_count", "-")))
        matches = values.get("source_revision_matches")
        self.revision.setText(
            "Matched" if matches is True else "Relink required" if matches is False else "-"
        )
        quality = str(values.get("quality_state") or "-")
        reasons = [
            str(item).replace("_", " ")
            for item in values.get("review_reasons", [])
        ]
        self.quality.setText(
            quality.replace("_", " ").title()
            + (f" ({', '.join(reasons)})" if reasons else "")
        )
        enabled = asset is not None and self._layer is not None and matches is not False
        self.attach.setEnabled(enabled)
        self.stabilize.setEnabled(enabled)
        self.corner_pin.setEnabled(
            enabled
            and str(values.get("kind") or "") == "planar"
            and bool(self._corner_pin_effect_id)
        )
        self.relink.setEnabled(asset is not None)

    def _emit_apply(self, stabilize: bool) -> None:
        track_id = self.current_track_id()
        if track_id and self._layer is not None:
            self.apply_requested.emit(track_id, bool(stabilize))

    def _emit_corner_pin(self) -> None:
        track_id = self.current_track_id()
        if track_id and self._corner_pin_effect_id:
            self.corner_pin_requested.emit(track_id, self._corner_pin_effect_id)


__all__ = ["TrackingPanel"]
