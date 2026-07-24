"""Qt window for the AR/PBR image texture-map lab."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tempfile
from typing import Any

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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
    DEFAULT_SEPARATE_MAPS,
    PACKED_LAYOUTS,
    PREVIEW_MODES,
    default_texture_map_settings,
    export_texture_maps,
    generate_texture_maps,
    normalize_texture_map_settings,
    pack_texture_channels,
    render_plane_preview_from_generated,
    select_texture_map_backend,
    texture_map_settings_fingerprint,
    texture_map_to_image,
)


_TEXTURE_THUMBNAILS: tuple[tuple[str, str], ...] = (
    ("Base", "base_color"),
    ("Normal", "normal"),
    ("AO", "ao"),
    ("Rough", "roughness"),
    ("Height", "height"),
    ("Cavity", "cavity"),
    ("Curv", "curvature"),
    ("F0", "f0"),
    ("F90", "f90_mask"),
    ("ORM", "unreal_orm"),
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


class _TextureLabPreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._preview_pixmap = QPixmap()
        self._thumbnails: list[tuple[str, QPixmap, bool]] = []
        self.setObjectName("TextureLabPreview")
        self.setMinimumSize(620, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def set_preview_pixmap(self, pixmap: QPixmap) -> None:
        self._preview_pixmap = QPixmap(pixmap) if pixmap is not None else QPixmap()
        self.update()

    def preview_pixmap(self) -> QPixmap:
        return QPixmap(self._preview_pixmap)

    def set_thumbnail_pixmaps(self, thumbnails: list[tuple[str, QPixmap, bool]]) -> None:
        self._thumbnails = [
            (str(label), QPixmap(pixmap), bool(active))
            for label, pixmap, active in thumbnails
            if pixmap is not None and not pixmap.isNull()
        ]
        self.update()

    def thumbnail_count(self) -> int:
        return len(self._thumbnails)

    def paintEvent(self, _event) -> None:  # pragma: no cover - visual paint path
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.fillRect(self.rect(), QColor("#08090C"))
        painter.setPen(QPen(QColor("#252A34"), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(frame, 6, 6)

        content = frame.adjusted(12, 12, -12, -12)
        if self._preview_pixmap.isNull():
            painter.setPen(QColor("#8F98A7"))
            painter.drawText(content, Qt.AlignmentFlag.AlignCenter, "No preview")
            painter.end()
            return

        preview_rect = self._scaled_rect(self._preview_pixmap, content)
        painter.drawPixmap(preview_rect.toRect(), self._preview_pixmap)
        self._draw_thumbnails(painter, content, preview_rect)
        painter.end()

    def _scaled_rect(self, pixmap: QPixmap, content: QRectF) -> QRectF:
        scale = min(
            content.width() / max(1, pixmap.width()),
            content.height() / max(1, pixmap.height()),
        )
        width = max(1.0, pixmap.width() * scale)
        height = max(1.0, pixmap.height() * scale)
        x = content.left() + (content.width() - width) * 0.5
        y = content.top() + (content.height() - height) * 0.5
        return QRectF(x, y, width, height)

    def _draw_thumbnails(self, painter: QPainter, content: QRectF, preview_rect: QRectF) -> None:
        if not self._thumbnails:
            return
        left_width = max(0.0, preview_rect.left() - content.left())
        right_width = max(0.0, content.right() - preview_rect.right())
        min_side_width = 86.0
        if left_width >= min_side_width and right_width >= min_side_width:
            split = (len(self._thumbnails) + 1) // 2
            self._draw_thumbnail_column(painter, content, content.left(), left_width, self._thumbnails[:split])
            self._draw_thumbnail_column(
                painter,
                content,
                preview_rect.right(),
                right_width,
                self._thumbnails[split:],
            )
            return
        if right_width >= min_side_width:
            self._draw_thumbnail_column(painter, content, preview_rect.right(), right_width, self._thumbnails[:7])
            return
        if left_width >= min_side_width:
            self._draw_thumbnail_column(painter, content, content.left(), left_width, self._thumbnails[:7])
            return
        self._draw_thumbnail_strip(painter, content, preview_rect)

    def _draw_thumbnail_column(
        self,
        painter: QPainter,
        content: QRectF,
        x_start: float,
        gutter_width: float,
        thumbnails: list[tuple[str, QPixmap, bool]],
    ) -> None:
        if not thumbnails:
            return
        gap = 7.0
        side_pad = 8.0
        width = max(64.0, min(138.0, gutter_width - side_pad * 2.0))
        x = x_start + (gutter_width - width) * 0.5
        usable_height = content.height()
        item_height = min(86.0, max(46.0, (usable_height - gap * (len(thumbnails) - 1)) / len(thumbnails)))
        visible_count = min(len(thumbnails), max(1, int((usable_height + gap) / max(1.0, item_height + gap))))
        rows = thumbnails[:visible_count]
        total_height = item_height * len(rows) + gap * max(0, len(rows) - 1)
        y = content.top() + max(0.0, (usable_height - total_height) * 0.5)
        for label, pixmap, active in rows:
            self._draw_thumbnail_card(painter, QRectF(x, y, width, item_height), label, pixmap, active)
            y += item_height + gap

    def _draw_thumbnail_strip(self, painter: QPainter, content: QRectF, preview_rect: QRectF) -> None:
        gap = 6.0
        rows = self._thumbnails[:6]
        if not rows:
            return
        width = min(92.0, max(58.0, (content.width() - gap * (len(rows) - 1)) / len(rows)))
        height = 52.0
        total_width = width * len(rows) + gap * max(0, len(rows) - 1)
        x = content.left() + (content.width() - total_width) * 0.5
        y = min(content.bottom() - height, preview_rect.bottom() + 8.0)
        for label, pixmap, active in rows:
            self._draw_thumbnail_card(painter, QRectF(x, y, width, height), label, pixmap, active)
            x += width + gap

    def _draw_thumbnail_card(
        self,
        painter: QPainter,
        rect: QRectF,
        label: str,
        pixmap: QPixmap,
        active: bool,
    ) -> None:
        painter.setPen(QPen(QColor("#58D38A" if active else "#303746"), 1.0))
        painter.setBrush(QColor(18, 21, 27, 226))
        painter.drawRoundedRect(rect, 5, 5)
        label_rect = QRectF(rect.left() + 5, rect.top() + 3, rect.width() - 10, 13)
        font = QFont("Cascadia Mono")
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#F2F5FB" if active else "#B8C2D2"))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, label)
        image_rect = rect.adjusted(5, 18, -5, -5)
        if image_rect.width() < 8 or image_rect.height() < 8:
            return
        scaled = self._scaled_rect(pixmap, image_rect)
        painter.drawPixmap(scaled.toRect(), pixmap)


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
        self._last_preview_path: Path | None = None
        self._clipboard_shortcuts: list[QShortcut] = []
        self._advanced_map_checks: dict[str, QCheckBox] = {}
        self._generated_maps_cache: dict[str, Any] | None = None
        self._backend_selection = select_texture_map_backend()
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

    def copy_preview_to_clipboard(self) -> dict[str, Any]:
        pix = QPixmap()
        preview_path = getattr(self, "_last_preview_path", None)
        if preview_path is not None and Path(preview_path).exists():
            pix = QPixmap(str(preview_path))
        if pix.isNull():
            pix = self._preview.preview_pixmap()
        if pix.isNull():
            raise ValueError("no Texture Lab preview image is available to copy")
        QApplication.clipboard().setImage(pix.toImage())
        payload = {
            "copied": True,
            "preview_path": str(preview_path or ""),
            "width": int(pix.width()),
            "height": int(pix.height()),
        }
        self._status.setText(f"Copied preview to clipboard | {pix.width()} x {pix.height()}")
        return payload

    def paste_image_from_clipboard(self) -> dict[str, Any]:
        clipboard = QApplication.clipboard()
        mime = clipboard.mimeData()
        image = clipboard.image()
        if image is not None and not image.isNull():
            root = Path(tempfile.gettempdir()) / "tiger_ar_pbr_texture_lab"
            root.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = root / f"clipboard_source_{stamp}.png"
            if not image.save(str(path), "PNG"):
                raise ValueError("clipboard image could not be saved")
            source_kind = "clipboard_image"
        else:
            path = self._clipboard_path(mime)
            if path is None:
                raise ValueError("clipboard does not contain an image or image file path")
            source_kind = "clipboard_path"
        self._set_source_image_path(path)
        self.refresh_preview()
        return {
            "pasted": True,
            "source_kind": source_kind,
            "source_path": str(self.image_path),
        }

    def _clipboard_path(self, mime) -> Path | None:
        candidates: list[str] = []
        if mime is not None and mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    candidates.append(url.toLocalFile())
        if mime is not None and mime.hasText():
            text = mime.text().strip().strip('"')
            if text:
                candidates.append(text)
        for candidate in candidates:
            path = Path(candidate).expanduser()
            if path.exists() and path.is_file():
                return path
        return None

    def _set_source_image_path(self, path: str | Path) -> None:
        self.image_path = Path(path).expanduser()
        self._last_preview_path = None
        self._generated_maps_cache = None
        self.setWindowTitle(f"AR/PBR Texture Lab - {self.image_path.name}")
        if hasattr(self, "_subtitle"):
            self._subtitle.setText(str(self.image_path))

    def _copy_preview_to_clipboard_from_ui(self) -> None:
        try:
            self.copy_preview_to_clipboard()
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab Clipboard", f"Copy failed.\n\n{type(exc).__name__}: {exc}")

    def _paste_image_from_clipboard_from_ui(self) -> None:
        try:
            self.paste_image_from_clipboard()
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab Clipboard", f"Paste failed.\n\n{type(exc).__name__}: {exc}")

    def _backend_status_text(self) -> str:
        selection = select_texture_map_backend()
        self._backend_selection = selection
        active = str(selection.get("active", "cpu"))
        status = selection.get("status", {})
        torch_status = dict(status.get("backends", {}).get("torch_cuda", {}))
        if active == "torch_cuda":
            device = str(torch_status.get("device") or "CUDA GPU")
            return f"GPU acceleration: torch_cuda | {device}"
        if not torch_status.get("module_installed"):
            return "GPU acceleration: CPU fallback | PyTorch CUDA is not installed"
        if not torch_status.get("available"):
            return "GPU acceleration: CPU fallback | PyTorch is installed but CUDA is unavailable"
        return f"GPU acceleration: CPU fallback | {selection.get('reason', 'gpu backend unavailable')}"

    def _show_gpu_setup_help(self) -> None:
        selection = select_texture_map_backend()
        guidance = dict(selection.get("status", {}).get("install_guidance", {}))
        pip_command = str(guidance.get("pip_command") or "")
        verify_command = str(guidance.get("verify_command") or "")
        env_override = str(guidance.get("env_override") or "")
        details = "\n".join(
            [
                str(guidance.get("summary") or "Texture Lab GPU acceleration needs PyTorch with CUDA."),
                "",
                "Install:",
                pip_command,
                "",
                "Verify:",
                verify_command,
                "",
                "Optional forced backend:",
                env_override,
                "",
                "After install, restart TigerCapture and reopen Texture Lab.",
            ]
        )
        QApplication.clipboard().setText(f"{pip_command}\n{verify_command}\n{env_override}".strip())
        QMessageBox.information(
            self,
            "Texture Lab GPU Setup",
            details + "\n\nThe commands were copied to the clipboard.",
        )

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
        self._subtitle = subtitle
        self._backend_status = QLabel(self._backend_status_text(), central)
        self._backend_status.setObjectName("TextureLabBackendStatus")
        title_block = QVBoxLayout()
        title_block.setSpacing(1)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_block.addWidget(self._backend_status)
        top.addLayout(title_block, 1)
        self._preview_mode_combo = QComboBox(central)
        self._preview_mode_combo.setObjectName("TextureLabCombo")
        for mode in PREVIEW_MODES:
            self._preview_mode_combo.addItem(mode.replace("_", " ").title(), mode)
        self._preview_mode_combo.currentIndexChanged.connect(self.queue_preview)
        paste_image = QPushButton("Paste Image", central)
        paste_image.setIcon(app_icon("paste", size=16))
        paste_image.setIconSize(icon_size(16))
        paste_image.setToolTip("Paste an image or image file path from the clipboard as the source (Ctrl+V)")
        paste_image.clicked.connect(self._paste_image_from_clipboard_from_ui)
        copy_preview = QPushButton("Copy Preview", central)
        copy_preview.setIcon(app_icon("copy", size=16))
        copy_preview.setIconSize(icon_size(16))
        copy_preview.setToolTip("Copy the current Texture Lab preview image to the clipboard (Ctrl+C)")
        copy_preview.clicked.connect(self._copy_preview_to_clipboard_from_ui)
        gpu_setup = QPushButton("GPU Setup", central)
        gpu_setup.setIcon(app_icon("settings", size=16))
        gpu_setup.setIconSize(icon_size(16))
        gpu_setup.setToolTip("Show Texture Lab GPU acceleration install and verification steps")
        gpu_setup.clicked.connect(self._show_gpu_setup_help)
        export_maps = QPushButton("Export Maps", central)
        export_maps.setIcon(app_icon("export", size=16))
        export_maps.setIconSize(icon_size(16))
        export_maps.clicked.connect(self.export_maps)
        export_packed = QPushButton("Export Packed", central)
        export_packed.setIcon(app_icon("save", size=16))
        export_packed.setIconSize(icon_size(16))
        export_packed.clicked.connect(self.export_packed)
        top.addWidget(self._preview_mode_combo)
        top.addWidget(paste_image)
        top.addWidget(copy_preview)
        top.addWidget(gpu_setup)
        top.addWidget(export_maps)
        top.addWidget(export_packed)
        copy_shortcut = QShortcut(QKeySequence.StandardKey.Copy, self)
        copy_shortcut.activated.connect(self._copy_preview_to_clipboard_from_ui)
        paste_shortcut = QShortcut(QKeySequence.StandardKey.Paste, self)
        paste_shortcut.activated.connect(self._paste_image_from_clipboard_from_ui)
        self._clipboard_shortcuts.extend([copy_shortcut, paste_shortcut])
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
        self._preview = _TextureLabPreviewCanvas(preview_panel)
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
        self._add_slider(controls_layout, "AO Height Scale", "ao_height_scale", 0.1, 64.0, 0.1)
        self._add_slider(controls_layout, "Cavity", "cavity_strength", 0.0, 2.0, 0.01)
        self._add_slider(controls_layout, "Cavity Radius", "cavity_radius_px", 0.2, 32.0, 0.1)
        self._add_slider(controls_layout, "Curvature", "curvature_strength", 0.0, 8.0, 0.01)
        controls_layout.addWidget(_section_label("Surface", controls))
        self._add_slider(controls_layout, "Roughness Bias", "roughness_bias", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Roughness Contrast", "roughness_contrast", 0.1, 3.0, 0.01)
        self._add_slider(controls_layout, "Roughness Detail", "roughness_detail", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "Metallic", "metallic_value", 0.0, 1.0, 0.01)
        controls_layout.addWidget(_section_label("Substrate Optional Maps", controls))
        self._add_advanced_map_check(controls_layout, controls, "Export F0 Map", "f0")
        self._add_advanced_map_check(controls_layout, controls, "Export F90 Mask", "f90_mask")
        self._add_slider(controls_layout, "F0 Reflectance", "substrate_reflectance", 0.0, 1.0, 0.01)
        self._add_slider(controls_layout, "F90 Mask", "f90_mask_strength", 0.0, 1.0, 0.01)
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

    def _add_advanced_map_check(self, layout: QVBoxLayout, parent: QWidget, label: str, map_name: str) -> None:
        check = QCheckBox(label, parent)
        check.setObjectName("TextureLabCheck")
        check.setChecked(False)
        check.setToolTip(f"Include {map_name} when exporting separate maps")
        self._advanced_map_checks[map_name] = check
        layout.addWidget(check)

    def queue_preview(self) -> None:
        self._preview_timer.start(120)

    def _source_cache_identity(self) -> str:
        try:
            stat = self.image_path.stat()
            return f"{self.image_path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
        except Exception:
            return str(self.image_path)

    def _cached_generated_maps(self, *, max_size: int = 960) -> tuple[dict[str, Any], bool]:
        settings = self.settings()
        key = {
            "source": self._source_cache_identity(),
            "settings": texture_map_settings_fingerprint(settings),
            "max_size": int(max_size),
        }
        cached = self._generated_maps_cache
        if isinstance(cached, dict) and cached.get("key") == key:
            return cached["generated"], True
        generated = generate_texture_maps(self.image_path, settings, max_size=max_size)
        self._generated_maps_cache = {"key": key, "generated": generated}
        return generated, False

    def refresh_preview(self) -> None:
        if not self.image_path.exists():
            self._status.setText(f"Missing source image: {self.image_path}")
            return
        try:
            mode = str(self._preview_mode_combo.currentData() or "material")
            out = Path(tempfile.gettempdir()) / "tiger_ar_pbr_texture_lab" / f"{self.image_path.stem}_{mode}.png"
            generated, cache_hit = self._cached_generated_maps(max_size=960)
            payload = render_plane_preview_from_generated(
                generated,
                self.settings(),
                preview_mode=mode,
                output_path=out,
                width=960,
                source_path=self.image_path,
            )
            if hasattr(self, "_backend_status"):
                self._backend_status.setText(self._backend_status_text())
            self._last_preview_path = Path(payload["preview_path"])
            pix = QPixmap(str(payload["preview_path"]))
            self._preview.set_preview_pixmap(pix)
            self._preview.set_thumbnail_pixmaps(self._thumbnail_pixmaps(active_mode=mode, generated=generated))
            backend = str(payload.get("backend", {}).get("active", "cpu"))
            cache = "cached" if cache_hit else "rendered"
            self._status.setText(f"{mode} | {payload['size'][0]} x {payload['size'][1]} | {backend} | {cache}")
        except Exception as exc:
            self._status.setText(f"Preview failed: {type(exc).__name__}: {exc}")

    def _thumbnail_pixmaps(
        self,
        *,
        active_mode: str,
        generated: dict[str, Any] | None = None,
    ) -> list[tuple[str, QPixmap, bool]]:
        if generated is None:
            generated, _cache_hit = self._cached_generated_maps(max_size=192)
        maps = generated["maps"]
        root = Path(tempfile.gettempdir()) / "tiger_ar_pbr_texture_lab"
        root.mkdir(parents=True, exist_ok=True)
        thumbnails: list[tuple[str, QPixmap, bool]] = []
        for label, mode in _TEXTURE_THUMBNAILS:
            if mode in maps:
                image = texture_map_to_image(mode, maps[mode])
            elif mode in PACKED_LAYOUTS:
                image = texture_map_to_image(mode, pack_texture_channels(maps, mode))
            else:
                continue
            path = root / f"{self.image_path.stem}_thumb_{mode}.png"
            image.save(path)
            pix = QPixmap(str(path))
            if not pix.isNull():
                thumbnails.append((label, pix, active_mode == mode))
        return thumbnails

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
            map_names = self._selected_export_maps()
            payload = export_texture_maps(
                self.image_path,
                selected,
                self.settings(),
                maps=map_names,
                packed_layouts=packed_layouts,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Texture Lab", f"Export failed.\n\n{type(exc).__name__}: {exc}")
            return
        self._status.setText(f"Exported: {payload['output_dir']}")

    def _selected_export_maps(self) -> list[str]:
        names = list(DEFAULT_SEPARATE_MAPS)
        for name, check in self._advanced_map_checks.items():
            if check.isChecked() and name not in names:
                names.append(name)
        return names


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
QLabel#TextureLabBackendStatus,
QLabel#TextureLabStatus {
    color: #8F98A7;
    font-size: 11px;
}
QLabel#TextureLabBackendStatus {
    color: #B9C3D2;
}
QFrame#TextureLabPreviewPanel {
    background: #15171D;
    border: 1px solid #2B303B;
    border-radius: 8px;
}
QWidget#TextureLabPreview {
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
QCheckBox#TextureLabCheck {
    color: #C9D2E1;
    font-size: 11px;
    font-weight: 700;
    spacing: 8px;
    padding: 3px 0px;
}
QCheckBox#TextureLabCheck::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3A4353;
    border-radius: 3px;
    background: #11141B;
}
QCheckBox#TextureLabCheck::indicator:checked {
    background: #58D38A;
    border-color: #77E5A0;
}
"""
    + editor_scrollbar_qss()
)
