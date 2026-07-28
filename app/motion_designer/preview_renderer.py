"""Persistent OpenGL presenter for the shared Motion Designer render graph."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from .color_management import settings_from_composition_metadata
from .color_runtime import (
    apply_motion_color_pipeline_premultiplied_rgba,
    motion_color_transform_required,
)
from .render_graph import build_render_graph, paint_render_graph, render_graph_image
from .schema import MotionComposition
from .puppet_gpu_renderer import MotionPuppetGpuRenderer
from .typography_gpu_renderer import MotionTypographyGpuRenderer
from .vector_gpu_renderer import MotionVectorGpuRenderer


class MotionPreviewWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._composition: MotionComposition | None = None
        self._time_ms = 0.0
        self._vector_gpu = MotionVectorGpuRenderer(self)
        self._typography_gpu = MotionTypographyGpuRenderer(self)
        self._puppet_gpu = MotionPuppetGpuRenderer(self)
        self._last_gpu_backend = "vector"
        self._cleanup_connected = False
        surface_format = QSurfaceFormat(self.format())
        surface_format.setSamples(max(4, surface_format.samples()))
        self.setFormat(surface_format)
        self.setMinimumSize(320, 180)

    def set_composition(self, composition: MotionComposition, time_ms: float = 0.0) -> None:
        self._composition = composition
        self._time_ms = float(time_ms)
        self.update()

    def set_time(self, time_ms: float) -> None:
        self._time_ms = float(time_ms)
        self.update()

    def initializeGL(self) -> None:
        context = self.context()
        if context is not None and not self._cleanup_connected:
            context.aboutToBeDestroyed.connect(self._cleanup_gpu)
            self._cleanup_connected = True

    def _cleanup_gpu(self) -> None:
        context = self.context()
        if context is None or not context.isValid():
            self._cleanup_connected = False
            return
        self.makeCurrent()
        self._vector_gpu.clear()
        self._typography_gpu.clear()
        self._puppet_gpu.clear()
        self.doneCurrent()
        self._cleanup_connected = False

    def paintGL(self) -> None:
        composition = self._composition
        color_settings = (
            settings_from_composition_metadata(composition.metadata)
            if composition is not None else None
        )
        needs_color_transform = bool(
            color_settings is not None
            and motion_color_transform_required(color_settings)
        )
        graph = (
            build_render_graph(
                composition, self._time_ms, include_vector_gpu=True,
                render_quality="preview", output_size=(composition.width, composition.height),
            )
            if composition is not None else None
        )
        if composition is not None:
            scale = min(self.width() / composition.width, self.height() / composition.height)
            width, height = composition.width * scale, composition.height * scale
            target = QRectF((self.width() - width) * .5, (self.height() - height) * .5, width, height)
            context = self.context()
            if (
                context is not None
                and context.isValid()
                and graph is not None
                and not needs_color_transform
            ):
                ratio = float(self.devicePixelRatioF())
                physical_target = QRectF(
                    target.x() * ratio, target.y() * ratio,
                    target.width() * ratio, target.height() * ratio,
                )
                try:
                    if self._vector_gpu.draw(
                        context.functions(), graph,
                        widget_width=max(1, int(round(self.width() * ratio))),
                        widget_height=max(1, int(round(self.height() * ratio))),
                        target=physical_target,
                    ):
                        self._last_gpu_backend = "vector"
                        return
                    if self._typography_gpu.draw(
                        context.functions(), graph,
                        widget_width=max(1, int(round(self.width() * ratio))),
                        widget_height=max(1, int(round(self.height() * ratio))),
                        target=physical_target,
                    ):
                        self._last_gpu_backend = "typography"
                        return
                    if self._puppet_gpu.draw(
                        context.functions(), graph,
                        widget_width=max(1, int(round(self.width() * ratio))),
                        widget_height=max(1, int(round(self.height() * ratio))),
                        target=physical_target,
                    ):
                        self._last_gpu_backend = "puppet"
                        return
                except Exception as exc:
                    self._typography_gpu.last_diagnostics = {
                        "backend": "qt_painter_fallback",
                        "reason": f"preview_gpu_exception:{type(exc).__name__}:{exc}",
                    }
        self._last_gpu_backend = "painter"
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0b0d11"))
        if graph is not None and composition is not None:
            scale = min(self.width() / composition.width, self.height() / composition.height)
            width, height = composition.width * scale, composition.height * scale
            target = QRectF((self.width() - width) * .5, (self.height() - height) * .5, width, height)
            if needs_color_transform and color_settings is not None:
                image = render_graph_image(graph).convertToFormat(
                    QImage.Format_RGBA8888_Premultiplied
                )
                rows = np.frombuffer(image.bits(), dtype=np.uint8).reshape(
                    image.height(),
                    image.bytesPerLine(),
                )
                rgba = rows[:, : image.width() * 4].reshape(
                    image.height(),
                    image.width(),
                    4,
                ).copy()
                transformed, _report = (
                    apply_motion_color_pipeline_premultiplied_rgba(
                        rgba,
                        color_settings,
                    )
                )
                display_image = QImage(
                    transformed.data,
                    image.width(),
                    image.height(),
                    transformed.strides[0],
                    QImage.Format_RGBA8888_Premultiplied,
                ).copy()
                painter.drawImage(target, display_image)
            else:
                paint_render_graph(painter, graph, target)
        painter.end()

    def diagnostics(self) -> dict[str, object]:
        context = self.context()
        if self._last_gpu_backend == "typography":
            backend_diagnostics = self._typography_gpu.last_diagnostics
        elif self._last_gpu_backend == "puppet":
            backend_diagnostics = self._puppet_gpu.last_diagnostics
        elif self._last_gpu_backend == "vector":
            backend_diagnostics = self._vector_gpu.last_diagnostics
        else:
            typography_reason = self._typography_gpu.last_diagnostics.get("reason", "")
            vector_reason = self._vector_gpu.last_diagnostics.get("reason", "")
            puppet_reason = self._puppet_gpu.last_diagnostics.get("reason", "")
            backend_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": puppet_reason or typography_reason or vector_reason or "unsupported_graph",
                "vector_gpu_reason": vector_reason,
                "typography_gpu_reason": typography_reason,
                "puppet_gpu_reason": puppet_reason,
            }
        return {
            "presenter": "QOpenGLWidget",
            "context_valid": bool(context and context.isValid()),
            "premultiplied_alpha": True,
            "shared_render_graph": True,
            **backend_diagnostics,
        }
