"""Persistent OpenGL presenter for the shared Motion Designer render graph."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from .render_graph import build_render_graph, paint_render_graph
from .schema import MotionComposition
from .typography_gpu_renderer import MotionTypographyGpuRenderer
from .vector_gpu_renderer import MotionVectorGpuRenderer


class MotionPreviewWidget(QOpenGLWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._composition: MotionComposition | None = None
        self._time_ms = 0.0
        self._vector_gpu = MotionVectorGpuRenderer(self)
        self._typography_gpu = MotionTypographyGpuRenderer(self)
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
        self.doneCurrent()
        self._cleanup_connected = False

    def paintGL(self) -> None:
        composition = self._composition
        graph = (
            build_render_graph(composition, self._time_ms, include_vector_gpu=True)
            if composition is not None else None
        )
        if composition is not None:
            scale = min(self.width() / composition.width, self.height() / composition.height)
            width, height = composition.width * scale, composition.height * scale
            target = QRectF((self.width() - width) * .5, (self.height() - height) * .5, width, height)
            context = self.context()
            if context is not None and context.isValid() and graph is not None:
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
            paint_render_graph(painter, graph, target)
        painter.end()

    def diagnostics(self) -> dict[str, object]:
        context = self.context()
        if self._last_gpu_backend == "typography":
            backend_diagnostics = self._typography_gpu.last_diagnostics
        elif self._last_gpu_backend == "vector":
            backend_diagnostics = self._vector_gpu.last_diagnostics
        else:
            typography_reason = self._typography_gpu.last_diagnostics.get("reason", "")
            vector_reason = self._vector_gpu.last_diagnostics.get("reason", "")
            backend_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": typography_reason or vector_reason or "unsupported_graph",
                "vector_gpu_reason": vector_reason,
                "typography_gpu_reason": typography_reason,
            }
        return {
            "presenter": "QOpenGLWidget",
            "context_valid": bool(context and context.isValid()),
            "premultiplied_alpha": True,
            "shared_render_graph": True,
            **backend_diagnostics,
        }
