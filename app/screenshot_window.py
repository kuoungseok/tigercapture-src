from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.capture import pil_to_qimage
from app.i18n import tr
from app.paths import open_in_explorer
from app.style import APP_QSS


class ScreenshotWindow(QWidget):
    """Preview + save window for a captured screenshot."""

    def __init__(self, image: Image.Image, save_dir: Path) -> None:
        super().__init__()
        self._image = image
        self._save_dir = save_dir
        self._saved_path: Path | None = None
        self._source_pixmap: QPixmap | None = None
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(40)
        self._resize_timer.timeout.connect(self._rescale_preview)

        self.setWindowTitle(tr("shot.title"))
        self.resize(900, 640)
        self.setStyleSheet(APP_QSS)

        self._build_ui()
        self._set_source(image)
        self._update_status(tr("shot.status.unsaved"))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.save_btn = QPushButton(tr("shot.btn.save"))
        self.save_btn.setObjectName("PrimaryToolButton")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._on_save)

        self.copy_btn = QPushButton(tr("shot.btn.copy"))
        self.copy_btn.setObjectName("ToolButton")
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.clicked.connect(self._on_copy)

        self.open_folder_btn = QPushButton(tr("shot.btn.open_folder"))
        self.open_folder_btn.setObjectName("ToolButton")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self._on_open_folder)

        toolbar.addWidget(self.save_btn)
        toolbar.addWidget(self.copy_btn)
        toolbar.addWidget(self.open_folder_btn)
        toolbar.addStretch(1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("StatusLabel")
        toolbar.addWidget(self.status_label)

        root.addLayout(toolbar)

        self._preview_host = QWidget()
        self._preview_host.setObjectName("PreviewHost")
        host_layout = QVBoxLayout(self._preview_host)
        host_layout.setContentsMargins(12, 12, 12, 12)

        self._preview = QLabel("")
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        host_layout.addWidget(self._preview, stretch=1)

        root.addWidget(self._preview_host, stretch=1)

    def _set_source(self, image: Image.Image) -> None:
        qimg = pil_to_qimage(image)
        self._source_pixmap = QPixmap.fromImage(qimg)
        self._rescale_preview()

    def _rescale_preview(self) -> None:
        if self._source_pixmap is None or self._preview_host.size().isEmpty():
            return
        target = self._preview_host.size()
        scaled = self._source_pixmap.scaled(
            target.width() - 24,
            target.height() - 24,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview.setPixmap(scaled)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._resize_timer.start()

    def _on_save(self) -> None:
        default = self._save_dir / self._suggested_name()
        path, selected = QFileDialog.getSaveFileName(
            self,
            tr("shot.dialog.title"),
            str(default),
            tr("shot.dialog.filter"),
        )
        if not path:
            return
        out = Path(path)
        suffix = out.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            rgb = self._image.convert("RGB")
            rgb.save(out, "JPEG", quality=92)
        else:
            if not suffix:
                out = out.with_suffix(".png")
            self._image.save(out, "PNG")
        self._saved_path = out
        self._update_status(tr("shot.status.saved", name=out.name))

    def _on_copy(self) -> None:
        qimg = pil_to_qimage(self._image)
        QGuiApplication.clipboard().setImage(qimg)
        self._update_status(tr("shot.status.copied"))

    def _on_open_folder(self) -> None:
        if self._saved_path and self._saved_path.exists():
            open_in_explorer(self._saved_path)
        else:
            open_in_explorer(self._save_dir)

    def _update_status(self, text: str) -> None:
        w, h = self._image.width, self._image.height
        self.status_label.setText(
            tr("shot.status.size_prefix", w=w, h=h, text=text)
        )

    @staticmethod
    def _suggested_name() -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"screenshot_{stamp}.png"
