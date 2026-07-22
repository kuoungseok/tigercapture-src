from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from app.motion_designer.color_management import settings_from_composition_metadata
from app.motion_designer.export_profiles import (
    get_motion_export_profile, list_motion_export_profiles, preflight_motion_export,
)
from app.motion_designer.schema import MotionComposition


class MotionOutputPanel(QWidget):
    color_settings_changed = Signal(object)
    export_requested = Signal(object)
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionOutputPanel")
        self._composition: MotionComposition | None = None
        self._loading = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)
        heading = QLabel("Delivery", self)
        heading.setObjectName("MotionInspectorSection")
        layout.addWidget(heading)
        form = QFormLayout()
        self.blend_space = QComboBox(self)
        self.blend_space.addItem("Linear sRGB", "linear-srgb")
        self.blend_space.addItem("Legacy display sRGB", "display-srgb")
        form.addRow("Blend", self.blend_space)
        self.profile = QComboBox(self)
        for row in list_motion_export_profiles():
            self.profile.addItem(row["label"], row["id"])
        form.addRow("Profile", self.profile)
        self.output_path = QLineEdit(self)
        self.output_path.setPlaceholderText("Choose output path")
        browse = QPushButton("...", self)
        browse.setFixedWidth(30)
        browse.setToolTip("Choose output path")
        path_row = QHBoxLayout()
        path_row.addWidget(self.output_path, 1)
        path_row.addWidget(browse)
        form.addRow("Output", path_row)
        self.resume_sequence = QCheckBox("Resume completed PNG frames", self)
        self.resume_sequence.setToolTip(
            "Keep valid PNG frames from an interrupted export and render only missing frames"
        )
        form.addRow("Recovery", self.resume_sequence)
        layout.addLayout(form)
        self.alpha_status = QLabel("", self)
        self.alpha_status.setWordWrap(True)
        self.alpha_status.setObjectName("MotionOutputDetail")
        layout.addWidget(self.alpha_status)
        self.preflight_status = QLabel("Choose an output path", self)
        self.preflight_status.setWordWrap(True)
        self.preflight_status.setObjectName("MotionOutputStatus")
        layout.addWidget(self.preflight_status)
        self.export_button = QPushButton("Export", self)
        self.export_button.setObjectName("MotionPrimaryButton")
        self.export_button.setEnabled(False)
        layout.addWidget(self.export_button)
        layout.addStretch(1)
        browse.clicked.connect(self._browse)
        self.profile.currentIndexChanged.connect(self._refresh_preflight)
        self.blend_space.currentIndexChanged.connect(self._emit_color_settings)
        self.output_path.textChanged.connect(self._refresh_preflight)
        self.export_button.clicked.connect(self._export_or_cancel)
        self._busy = False

    def set_composition(self, composition: MotionComposition) -> None:
        self._composition = MotionComposition.from_dict(composition.to_dict())
        settings = settings_from_composition_metadata(composition.metadata)
        self._loading = True
        index = self.blend_space.findData(settings.blend_space)
        self.blend_space.setCurrentIndex(max(0, index))
        self._loading = False
        self._refresh_preflight()

    def _emit_color_settings(self) -> None:
        if self._loading or self._composition is None:
            return
        settings = settings_from_composition_metadata(self._composition.metadata).to_dict()
        blend_space = str(self.blend_space.currentData())
        settings["blend_space"] = blend_space
        settings["alpha"]["premultiply_space"] = "linear" if blend_space == "linear-srgb" else "display"
        self.color_settings_changed.emit(settings)

    def _browse(self) -> None:
        profile = get_motion_export_profile(str(self.profile.currentData()))
        if profile.kind == "sequence":
            path = QFileDialog.getExistingDirectory(self, "Choose sequence folder", self.output_path.text())
        else:
            filters = {
                ".mp4": "MP4 Video (*.mp4)", ".mov": "QuickTime Movie (*.mov)",
                ".png": "PNG Image (*.png)", ".jpg": "JPEG Image (*.jpg)",
                ".webp": "WebP Image (*.webp)",
            }
            path, _ = QFileDialog.getSaveFileName(
                self, "Export Motion", self.output_path.text(), filters.get(profile.extension, "All Files (*)"),
            )
            if path and not Path(path).suffix:
                path += profile.extension
        if path:
            self.output_path.setText(path)

    def _refresh_preflight(self) -> None:
        if self._composition is None:
            return
        path = self.output_path.text().strip()
        report = preflight_motion_export(
            self._composition, str(self.profile.currentData()), output_path=path,
        )
        profile_id = str(self.profile.currentData())
        self.resume_sequence.setEnabled(not self._busy and profile_id == "png_sequence")
        self.resume_sequence.setVisible(profile_id == "png_sequence")
        alpha = report["alpha_contract"]
        self.alpha_status.setText(
            f"Alpha: {alpha['storage']} storage · {alpha['internal']} internal · "
            f"{alpha['premultiply_space']} premultiply"
        )
        if report["errors"]:
            self.preflight_status.setText("Blocked · " + " · ".join(report["errors"]))
        elif not path:
            self.preflight_status.setText("Choose an output path")
        else:
            warning = f" · {len(report['warnings'])} note(s)" if report["warnings"] else ""
            self.preflight_status.setText(f"Ready · {report['frame_count']} frame(s){warning}")
        self.preflight_status.setToolTip("\n".join([*report["errors"], *report["warnings"]]))
        self.export_button.setEnabled(bool(path) and report["ok"] and not self._busy)

    def _export_or_cancel(self) -> None:
        if self._busy:
            self.cancel_requested.emit()
            return
        if self._composition is None or not self.output_path.text().strip():
            return
        profile_id = str(self.profile.currentData())
        self.export_requested.emit({
            "profile_id": profile_id,
            "output_path": self.output_path.text().strip(),
            "fps": self._composition.fps,
            "resume": profile_id == "png_sequence" and self.resume_sequence.isChecked(),
        })

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = bool(busy)
        self.profile.setEnabled(not busy)
        self.output_path.setEnabled(not busy)
        self.blend_space.setEnabled(not busy)
        self.resume_sequence.setEnabled(not busy and str(self.profile.currentData()) == "png_sequence")
        self.export_button.setEnabled(True if busy else bool(self.output_path.text().strip()))
        self.export_button.setText("Cancel" if busy else "Export")
        if not busy:
            self._refresh_preflight()
        if message:
            self.preflight_status.setText(message)


__all__ = ["MotionOutputPanel"]
