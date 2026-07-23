"""Qt window for the AR/PBR image texture-map lab."""
from __future__ import annotations

from pathlib import Path
import tempfile
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import editor_scrollbar_qss, studio_chrome_qss
from app.ar_pbr.texture_map_lab import (
    PACKED_LAYOUTS,
    PREVIEW_MODES,
    default_texture_map_settings,
    export_texture_maps,
    normalize_texture_map_settings,
    render_plane_preview,
)


class _TextureLabSlider(QWidget):
    def __init__(
        self,
        label: str,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
        value: float,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.key = key
        self.minimum = float(minimum)
        self.maximum = float(maximum)
        self.step = float(step)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(3)
        self.label = QLabel(label, self)
        self.label.setObjectName("TextureLabControlLabel")
        self.value_label = QLabel("", self)
        self.value_label.setObjectName("TextureLabValueLabel")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.slider = StudioSlider("accent", self)
        self.slider.setRange(0, max(1, int(round((self.maximum - self.minimum) / self.step))))
        layout.addWidget(self.label, 0, 0)
        layout.addWidget(self.value_label, 0, 1)
        layout.addWidget(self.slider, 1, 0, 1, 2)
        self.set_value(value)

    def value(self) -> float:
        return self.minimum + float(self.slider.value()) * self.step

    def set_value(self, value: float) -> None:
        ratio = (float(value) - self.minimum) / self.step
        self.slider.setValue(max(self.slider.minimum(), min(self.slider.maximum(), int(round(ratio)))))
        self._sync_label()

    def connect_changed(self, callback) -> None:
        self.slider.valueChanged.connect(lambda _value: (self._sync_label(), callback()))

    def _sync_label(self) -> None:
        value = self.value()
        if self.maximum <= 3.0:
            text = f"{value:.2f}"
        else:
            text = f"{value:.1f}"
        self.value_label.setText(text)


class ArPbrTextureMapLabWindow(QMainWindow):
    """Image-to-material plane preview and export controls."""

    def __init__(self, image_path: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image_path = Path(image_path).expanduser()
        self._settings = normalize_texture_map_settings(default_texture_map_settings())
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.refresh_preview)
        self._sliders: dict[str, _TextureLabSlider] = {}
        self.setObjectName("ArPbrTextureMapLabWindow")
        self.setWindowTitle(f"AR/PBR Texture Lab - {self.image_path.name}")
        self.resize(1120, 780)
        self.setStyleSheet(studio_chrome_qss(_TEXTURE_LAB_QSS))
        self._build_ui()
        self.refresh_preview()

    def settings(self) -> dict[str, Any]:
        values = dict(self._settings)
        for key, slider in self._sliders.items():
            values[key] = slider.value()
        values["normal_format"] = str(self._normal_format_combo.currentData() or "unreal_directx")
        return normalize_texture_map_settings(values)

    def _build_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("TextureLabCentral")
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        top = QHBoxLayout()
        title = QLabel("AR/PBR Texture Lab", central)
        title.setObjectName("TextureLabTitle")
        subtitle = QLabel(str(self.image_path), central)
        subtitle.setObjectName("TextureLabSubtitle")
        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        top.addLayout(title_block, 1)
        self._preview_mode_combo = QComboBox(central)
        self._preview_mode_combo.setObjectName("TextureLabCombo")
        for mode in PREVIEW_MODES:
            self._preview_mode_combo.addItem(mode.replace("_", " ").title(), mode)
        self._preview_mode_combo.currentIndexChanged.connect(self.queue_preview)
        export_maps = QPushButton("Export Maps", central)
        export_maps.setIcon(app_icon("export", size=16))
        export_maps.setIconSize(icon_size(16))
        export_maps.clicked.connect(self.export_maps)
        export_packed = QPushButton("Export Packed", central)
        export_packed.setIcon(app_icon("save", size=16))
        export_packed.setIconSize(icon_size(16))
        export_packed.clicked.connect(self.export_packed)
        top.addWidget(self._preview_mode_combo)
        top.addWidget(export_maps)
        top.addWidget(export_packed)
        root.addLayout(top)

        content = QHBoxLayout()
        content.setSpacing(12)
        preview_panel = QFrame(central)
        preview_panel.setObjectName("TextureLabPreviewPanel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(10, 10, 10, 10)
        preview_layout.setSpacing(8)
        preview_label = QLabel("Plane Preview", preview_panel)
        preview_label.setObjectName("TextureLabSection")
        self._preview = QLabel(preview_panel)
        self._preview.setObjectName("TextureLabPreview")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumSize(620, 420)
        self._status = QLabel("", preview_panel)
        self._status.setObjectName("TextureLabStatus")
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self._preview, 1)
        preview_layout.addWidget(self._status)
        content.addWidget(preview_panel, 1)

        scroll = QScrollArea(central)
        scroll.setObjectName("TextureLabScroll")
        scroll.setWidgetResizable(True)
        controls = QWidget(scroll)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 10, 10, 10)
        controls_layout.setSpacing(9)
        self._normal_format_combo = QComboBox(controls)
        self._normal_format_combo.setObjectName("TextureLabCombo")
        self._normal_format_combo.addItem("Unreal / DirectX Normal", "unreal_directx")
        self._normal_format_combo.addItem("OpenGL Normal", "opengl")
        self._normal_format_combo.currentIndexChanged.connect(self.queue_preview)
        controls_layout.addWidget(_section_label("Normal", controls))
        controls_layout.addWidget(self._normal_format_combo)
        self._add_slider(controls_layout, "Strength", "normal_strength", 0.0, 12.0, 0.1)
        self._add_slider(controls_layout, "Radius", "normal_radius_px", 0.0, 24.0, 0.1)
        controls_layout.addWidget(_section_label("Height / AO", controls))
        self._add_slider(controls_layout, "Height Contrast", "height_contrast", 0.1, 4.0, 0.01)
        self._add_slider(controls_layout, "Height Blur", "height_blur_px", 0.0, 8.0, 0.05)
        self._add_slider(controls_layout, "AO Strength", "ao_strength", 0.0, 3.0, 0.01)
        self._add_slider(controls_layout, "AO Radius", "ao_radius_px", 0.0, 64.0, 0.5)
        self._add_slider(controls_layout, "Cavity", "cavity_strength", 0.0, 2.0, 0.01)
        controls_layout.addWidget(_section_label("Surface", controls))
        self._add_slider(controls_layout, "Roughness Bias", "roughness_bias", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Roughness Contrast", "roughness_contrast", 0.1, 3.0, 0.01)
        self._add_slider(controls_layout, "Roughness Detail", "roughness_detail", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Metallic", "metallic_value", 0.0, 1.0, 0.01)
        controls_layout.addWidget(_section_label("Preview Light", controls))
        self._add_slider(controls_layout, "Azimuth", "preview_light_azimuth", -180.0, 180.0, 1.0)
        self._add_slider(controls_layout, "Elevation", "preview_light_elevation", 3.0, 89.0, 1.0)
        self._add_slider(controls_layout, "Environment", "preview_environment", 0.0, 1.5, 0.01)
        controls_layout.addStretch(1)
        scroll.setWidget(controls)
        content.addWidget(scroll, 0)
        root.addLayout(content, 1)
        self.setCentralWidget(central)

    def _add_slider(
        self,
        layout: QVBoxLayout,
        label: str,
        key: str,
        minimum: float,
        maximum: float,
        step: float,
    ) -> None:
        slider = _TextureLabSlider(label, key, minimum, maximum, step, float(self._settings[key]), self)
        slider.connect_changed(self.queue_preview)
        self._sliders[key] = slider
        layout.addWidget(slider)

    def queue_preview(self) -> None:
        self._preview_timer.start(120)

    def refresh_preview(self) -> None:
        if not self.image_path.exists():
            self._status.setText(f"Missing source image: {self.image_path}")
            return
        try:
            mode = str(self._preview_mode_combo.currentData() or "material")
            out = Path(tempfile.gettempdir()) / "tiger_ar_pbr_texture_lab" / f"{self.image_path.stem}_{mode}.png"
            payload = render_plane_preview(
                self.image_path,
                self.settings(),
                preview_mode=mode,
                output_path=out,
                width=960,
            )
            pix = QPixmap(str(payload["preview_path"]))
            self._preview.setPixmap(
                pix.scaled(
                    self._preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            self._status.setText(f"{mode} | {payload['size'][0]} x {payload['size'][1]}")
        except Exception as exc:
            self._status.setText(f"Preview failed: {type(exc).__name__}: {exc}")

    def resizeEvent(self, event) -> None:  # pragma: no cover - visual resize sync
        super().resizeEvent(event)
        self.queue_preview()

    def export_maps(self) -> None:
        self._export_with_layouts([])

    def export_packed(self) -> None:
        self._export_with_layouts(list(PACKED_LAYOUTS))

    def _export_with_layouts(self, packed_layouts: list[str]) -> None:
        default_dir = self.image_path.with_name(f"{self.image_path.stem}_pbr_maps")
        selected = QFileDialog.getExistingDirectory(self, "Export AR/PBR textures", str(default_dir.parent))
        if not selected:
            return
        try:
            payload = export_texture_maps(
                self.image_path,
                selected,
                self.settings(),
                packed_layouts=packed_layouts,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab", f"Export failed.\n\n{type(exc).__name__}: {exc}")
            return
        self._status.setText(f"Exported: {payload['output_dir']}")


def _section_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("TextureLabSection")
    return label


_TEXTURE_LAB_QSS = (
    """
QWidget#TextureLabCentral {
    background: #101114;
}
QLabel#TextureLabTitle {
    color: #F2F5FB;
    font-size: 18px;
    font-weight: 700;
}
QLabel#TextureLabSubtitle,
QLabel#TextureLabStatus {
    color: #8F98A7;
    font-size: 11px;
}
QFrame#TextureLabPreviewPanel {
    background: #15171D;
    border: 1px solid #2B303B;
    border-radius: 8px;
}
QLabel#TextureLabPreview {
    background: #08090C;
    border: 1px solid #252A34;
    border-radius: 6px;
}
QLabel#TextureLabSection {
    color: #C9D2E1;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0px;
    padding-top: 6px;
}
QLabel#TextureLabControlLabel {
    color: #A9B4C5;
    font-size: 11px;
}
QLabel#TextureLabValueLabel {
    color: #D9E0EA;
    font-size: 11px;
    font-family: "Cascadia Mono", "Consolas";
}
QComboBox#TextureLabCombo {
    background: #1A1D25;
    color: #E8ECF5;
    border: 1px solid #303746;
    border-radius: 6px;
    padding: 7px 10px;
    min-width: 180px;
}
QComboBox#TextureLabCombo::drop-down {
    border: 0px;
    width: 22px;
}
QComboBox#TextureLabCombo QAbstractItemView {
    background: #141720;
    color: #E8ECF5;
    border: 1px solid #303746;
    selection-background-color: #273245;
}
QScrollArea#TextureLabScroll {
    background: #15171D;
    border: 1px solid #2B303B;
    border-radius: 8px;
    min-width: 300px;
    max-width: 360px;
}
QPushButton {
    background: #20242D;
    color: #F1F4FA;
    border: 1px solid #343B49;
    border-radius: 6px;
    padding: 8px 12px;
    font-weight: 700;
}
QPushButton:hover {
    background: #29303D;
}
QPushButton:pressed {
    background: #D85A30;
    color: #FFFFFF;
}
"""
    + editor_scrollbar_qss()
)
