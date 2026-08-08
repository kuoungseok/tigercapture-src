from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMenu, QPushButton, QVBoxLayout, QWidget,
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
        self.working_space = QComboBox(self)
        for label, value in (
            ("sRGB", "srgb"), ("Rec.709", "rec709"),
            ("ACEScg", "acescg"), ("ACEScct", "acescct"),
            ("Rec.2020", "rec2020"),
        ):
            self.working_space.addItem(label, value)
        form.addRow("Working", self.working_space)
        self.output_space = QComboBox(self)
        for label, value in (
            ("sRGB", "srgb"), ("Rec.709", "rec709"),
            ("Rec.2020", "rec2020"), ("P3-D65", "p3-d65"),
        ):
            self.output_space.addItem(label, value)
        form.addRow("Output", self.output_space)
        self.output_transfer = QComboBox(self)
        for label, value in (
            ("sRGB", "srgb"), ("BT.709", "bt709"),
            ("PQ", "pq"), ("HLG", "hlg"),
        ):
            self.output_transfer.addItem(label, value)
        form.addRow("Transfer", self.output_transfer)
        self.view_transform = QComboBox(self)
        for label, value in (
            ("sRGB", "srgb"), ("Rec.709", "rec709"),
            ("ACES 1.3", "aces-1.3"), ("HDR PQ", "hdr-pq"),
            ("HDR HLG", "hdr-hlg"), ("Bypass", "none"),
        ):
            self.view_transform.addItem(label, value)
        form.addRow("View", self.view_transform)
        self.tone_map = QComboBox(self)
        self.tone_map.addItem("None", "none")
        self.tone_map.addItem("Reinhard", "reinhard")
        self.tone_map.addItem("ACES Fitted", "aces-fitted")
        form.addRow("Tone Map", self.tone_map)
        self.ocio_path = QLineEdit(self)
        self.ocio_path.setPlaceholderText("Optional OCIO config.ocio")
        self.ocio_browse = QPushButton("...", self)
        self.ocio_browse.setFixedWidth(30)
        self.ocio_browse.setToolTip("Choose an OpenColorIO config")
        self.ocio_browse.setMenu(self._build_ocio_menu())
        ocio_row = QHBoxLayout()
        ocio_row.addWidget(self.ocio_path, 1)
        ocio_row.addWidget(self.ocio_browse)
        form.addRow("OCIO", ocio_row)
        self._lut_controls: dict[str, tuple[QLineEdit, QDoubleSpinBox, QPushButton]] = {}
        for slot_name, label in (
            ("input_lut", "Input LUT"),
            ("creative_lut", "Creative LUT"),
            ("output_lut", "Output LUT"),
        ):
            form.addRow(label, self._create_lut_row(slot_name))
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
        self.working_space.currentIndexChanged.connect(self._emit_color_settings)
        self.output_space.currentIndexChanged.connect(self._emit_color_settings)
        self.output_transfer.currentIndexChanged.connect(self._emit_color_settings)
        self.view_transform.currentIndexChanged.connect(self._emit_color_settings)
        self.tone_map.currentIndexChanged.connect(self._emit_color_settings)
        self.ocio_path.editingFinished.connect(self._emit_color_settings)
        self.output_path.textChanged.connect(self._refresh_preflight)
        self.export_button.clicked.connect(self._export_or_cancel)
        self._busy = False

    def set_composition(self, composition: MotionComposition) -> None:
        self._composition = MotionComposition.from_dict(composition.to_dict())
        settings = settings_from_composition_metadata(composition.metadata)
        self._loading = True
        index = self.blend_space.findData(settings.blend_space)
        self.blend_space.setCurrentIndex(max(0, index))
        project = settings.project
        for combo, value in (
            (self.working_space, project.working_space),
            (self.output_space, project.output_space),
            (self.output_transfer, project.output_transfer),
            (self.view_transform, project.view_transform),
            (self.tone_map, settings.tone_map),
        ):
            index = combo.findData(value)
            combo.setCurrentIndex(max(0, index))
        self.ocio_path.setText(project.ocio_config_path)
        for slot_name, slot in (
            ("input_lut", project.input_lut),
            ("creative_lut", project.creative_lut),
            ("output_lut", project.output_lut),
        ):
            path_edit, strength, _browse = self._lut_controls[slot_name]
            path_edit.setText(slot.path)
            strength.setValue(float(slot.strength) * 100.0)
        self._loading = False
        self._refresh_preflight()

    def _emit_color_settings(self) -> None:
        if self._loading or self._composition is None:
            return
        settings = settings_from_composition_metadata(self._composition.metadata).to_dict()
        blend_space = str(self.blend_space.currentData())
        settings["blend_space"] = blend_space
        settings["tone_map"] = str(self.tone_map.currentData())
        settings["alpha"]["premultiply_space"] = "linear" if blend_space == "linear-srgb" else "display"
        project = dict(settings.get("project") or {})
        project.update({
            "working_space": str(self.working_space.currentData()),
            "output_space": str(self.output_space.currentData()),
            "output_transfer": str(self.output_transfer.currentData()),
            "view_transform": str(self.view_transform.currentData()),
            "hdr_mode": str(self.output_transfer.currentData()) in {"pq", "hlg"},
            "ocio_config_path": self.ocio_path.text().strip(),
        })
        for slot_name, (path_edit, strength, _browse) in self._lut_controls.items():
            path = path_edit.text().strip()
            project[slot_name] = {
                "path": path,
                "strength": float(strength.value()) / 100.0,
                "enabled": bool(path),
            }
        if (
            not project["ocio_config_path"]
            and (
                project["working_space"] in {"acescg", "acescct"}
                or project["view_transform"] == "aces-1.3"
            )
        ):
            from app.color_ocio import preferred_aces_ocio_uri

            project["ocio_config_path"] = preferred_aces_ocio_uri()
            self.ocio_path.setText(project["ocio_config_path"])
        settings["project"] = project
        self.color_settings_changed.emit(settings)

    def _create_lut_row(self, slot_name: str) -> QHBoxLayout:
        path_edit = QLineEdit(self)
        path_edit.setPlaceholderText("3D .cube")
        strength = QDoubleSpinBox(self)
        strength.setRange(0.0, 100.0)
        strength.setDecimals(0)
        strength.setSuffix("%")
        strength.setFixedWidth(62)
        strength.setValue(100.0)
        browse = QPushButton("...", self)
        browse.setFixedWidth(30)
        browse.setToolTip("Choose a 3D .cube LUT")
        row = QHBoxLayout()
        row.addWidget(path_edit, 1)
        row.addWidget(strength)
        row.addWidget(browse)
        self._lut_controls[slot_name] = (path_edit, strength, browse)
        path_edit.editingFinished.connect(self._emit_color_settings)
        strength.valueChanged.connect(self._emit_color_settings)
        browse.clicked.connect(lambda _checked=False, name=slot_name: self._browse_lut(name))
        return row

    def _browse_lut(self, slot_name: str) -> None:
        path_edit, _strength, _browse = self._lut_controls[slot_name]
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose 3D LUT",
            path_edit.text(),
            "3D Cube LUT (*.cube);;All Files (*)",
        )
        if path:
            path_edit.setText(path)
            self._emit_color_settings()

    def _browse_ocio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose OpenColorIO Config",
            self.ocio_path.text(),
            "OpenColorIO Config (*.ocio *.yaml *.yml);;All Files (*)",
        )
        if path:
            self.ocio_path.setText(path)
            self._emit_color_settings()

    def _set_ocio_config(self, config_spec: str) -> None:
        self.ocio_path.setText(str(config_spec or ""))
        self._emit_color_settings()

    def _build_ocio_menu(self) -> QMenu:
        menu = QMenu(self)
        try:
            from app.color_ocio import list_builtin_ocio_configs

            for row in list_builtin_ocio_configs():
                name = str(row["name"])
                if "v2.2.0_aces-v1.3" not in name:
                    continue
                family = "Studio" if row["studio"] else "CG"
                action = menu.addAction(f"{family} ACES 1.3")
                action.setToolTip(str(row["description"]))
                action.triggered.connect(
                    lambda _checked=False, uri=str(row["uri"]): self._set_ocio_config(uri)
                )
        except Exception:
            unavailable = menu.addAction("OpenColorIO runtime unavailable")
            unavailable.setEnabled(False)
        if not menu.isEmpty():
            menu.addSeparator()
        menu.addAction("Choose config file...", self._browse_ocio)
        clear = menu.addAction("Clear OCIO config")
        clear.triggered.connect(lambda _checked=False: self._set_ocio_config(""))
        return menu

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
        self.tone_map.setEnabled(not busy)
        for path_edit, strength, browse in self._lut_controls.values():
            path_edit.setEnabled(not busy)
            strength.setEnabled(not busy)
            browse.setEnabled(not busy)
        self.resume_sequence.setEnabled(not busy and str(self.profile.currentData()) == "png_sequence")
        self.export_button.setEnabled(True if busy else bool(self.output_path.text().strip()))
        self.export_button.setText("Cancel" if busy else "Export")
        if not busy:
            self._refresh_preflight()
        if message:
            self.preflight_status.setText(message)


__all__ = ["MotionOutputPanel"]
