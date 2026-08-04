"""Presentation and preview windows for Painter UI documents."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtCore import QRectF
from PySide6.QtGui import (
    QColor,
    QImage,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.painter_i18n import painter_text
from app.painter_ui_asset_export import render_ui_artboard
from app.painter_ui_document import normalize_ui_document


class PainterUIPreviewWindow(QWidget):
    """A real rendered-artboard viewer with preview and presentation modes."""

    def __init__(
        self,
        document: Mapping[str, Any],
        *,
        mode: str = "preview",
        prototype_settings: Mapping[str, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self._mode = (
            "presentation"
            if str(mode).casefold() == "presentation"
            else "preview"
        )
        normalized = normalize_ui_document(document)
        artboard_id = str(normalized.get("active_artboard_id") or "")
        settings = (
            dict(prototype_settings)
            if isinstance(prototype_settings, Mapping)
            else {}
        )
        self._device = dict(settings.get("device") or {})
        self._background = str(
            settings.get("background") or "#000000"
        )
        source_image: QImage = render_ui_artboard(
            normalized,
            artboard_id,
            density=1.0,
        )
        self._image = self._device_image(source_image)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setWindowTitle(
            painter_text(
                "Presentation"
                if self._mode == "presentation"
                else "Preview"
            )
        )
        self.setMinimumSize(480, 320)
        self.resize(1100, 760)
        self.setStyleSheet(
            f"QWidget {{ background-color: {self._background}; }}"
            "QLabel { background-color: transparent; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label, 1)
        self._sync_pixmap()

    def _device_image(self, source: QImage) -> QImage:
        width = int(self._device.get("width") or 0)
        height = int(self._device.get("height") or 0)
        family = str(self._device.get("family") or "none")
        if width <= 0 or height <= 0 or family in {
            "none",
            "presentation",
            "custom",
        }:
            return source
        scaled = source.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        screen = QImage(
            width,
            height,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        screen.fill(QColor("#FFFFFF"))
        screen_painter = QPainter(screen)
        screen_painter.drawImage(
            (width - scaled.width()) // 2,
            (height - scaled.height()) // 2,
            scaled,
        )
        screen_painter.end()
        shell_x = 18
        shell_top = 28 if family in {"iphone", "android"} else 18
        shell_bottom = 20
        output = QImage(
            width + shell_x * 2,
            height + shell_top + shell_bottom,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        output.fill(Qt.GlobalColor.transparent)
        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        shell = QRectF(0, 0, output.width(), output.height())
        shell_path = QPainterPath()
        shell_path.addRoundedRect(shell, 30, 30)
        painter.fillPath(shell_path, QColor("#101114"))
        painter.drawImage(shell_x, shell_top, screen)
        if family in {"iphone", "android"}:
            painter.setBrush(QColor("#050506"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                QRectF(output.width() * 0.40, 9, output.width() * 0.20, 7),
                4,
                4,
            )
        painter.end()
        return output

    def open_mode(self) -> None:
        if self._mode == "presentation":
            self.showFullScreen()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def _sync_pixmap(self) -> None:
        target = self.image_label.size()
        if target.width() <= 1 or target.height() <= 1:
            target = self.size()
        pixmap = QPixmap.fromImage(self._image).scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._sync_pixmap()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.close()
            event.accept()
            return
        if event.key() == Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            event.accept()
            return
        super().keyPressEvent(event)


__all__ = ["PainterUIPreviewWindow"]
