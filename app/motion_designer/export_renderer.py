"""Motion Designer still, sequence, and video renderer."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QCoreApplication, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtWidgets import QApplication

from .cache import MotionFrameCache
from .gpu_export_renderer import MotionGpuExportRenderer
from .render_graph import build_render_graph, paint_render_graph
from .schema import MotionComposition
from .source_frame import transparent_image


class MotionExportRenderer:
    def __init__(self, *, cache_capacity: int = 120) -> None:
        self._owned_application = None
        application = QCoreApplication.instance()
        if application is None:
            self._owned_application = QApplication([])
            application = self._owned_application
        # Standalone/headless exports do not pass through main_window's UI font
        # bootstrap. Register known Windows fonts before shaping typography.
        if isinstance(application, QGuiApplication):
            from app.font_fallback import load_application_ui_fonts

            load_application_ui_fonts()
        self.cache = MotionFrameCache(cache_capacity)
        self.last_tiled_report: dict[str, object] = {}
        self._gpu = MotionGpuExportRenderer()
        self.last_render_report: dict[str, object] = {
            "backend": "not_rendered",
        }

    def render_frame(self, composition: MotionComposition, time_ms: float, *, width: int | None = None,
                     height: int | None = None, use_cache: bool = True) -> QImage:
        output_width = max(1, int(width or composition.width))
        output_height = max(1, int(height or composition.height))
        tiled_settings = composition.metadata.get("tiled_export")
        tiled_settings = tiled_settings if isinstance(tiled_settings, dict) else {}
        tiled_enabled = bool(tiled_settings.get("enabled", False))
        tile_size = max(64, int(tiled_settings.get("tile_size", 512) or 512))
        key = (
            composition.id,
            composition.revision,
            round(float(time_ms), 3),
            output_width,
            output_height,
            tiled_enabled,
            tile_size if tiled_enabled else 0,
        )
        cached = self.cache.get(key) if use_cache else None
        if isinstance(cached, QImage):
            return cached.copy()
        if tiled_enabled:
            if (
                output_width != composition.width
                or output_height != composition.height
            ):
                raise ValueError(
                    "Motion tiled export currently requires native composition resolution"
                )
            image = self.render_frame_tiled(
                composition,
                time_ms,
                tile_size=tile_size,
            )
            if use_cache:
                self.cache.put(key, image.copy())
            return image
        graph = build_render_graph(
            composition,
            time_ms,
            render_quality="export",
            output_size=(output_width, output_height),
        )
        try:
            gpu_image = self._gpu.render(
                graph,
                width=output_width,
                height=output_height,
            )
        except Exception as exc:
            gpu_image = None
            self._gpu.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": (
                    f"offscreen_gpu_exception:"
                    f"{type(exc).__name__}:{exc}"
                ),
            }
        if gpu_image is not None:
            image = gpu_image
            self.last_render_report = dict(self._gpu.last_diagnostics)
            if use_cache:
                self.cache.put(key, image.copy())
            return image
        image = transparent_image(output_width, output_height)
        painter = QPainter(image)
        paint_render_graph(
            painter,
            graph,
            QRectF(0, 0, output_width, output_height),
        )
        painter.end()
        self.last_render_report = {
            **self._gpu.last_diagnostics,
            "backend": "qt_painter_export",
            "gpu_fallback": True,
        }
        if use_cache:
            self.cache.put(key, image.copy())
        return image

    def render_frame_tiled(
        self,
        composition: MotionComposition,
        time_ms: float,
        *,
        tile_size: int = 512,
    ) -> QImage:
        from .tiled_renderer import render_graph_tiled

        graph = build_render_graph(
            composition,
            time_ms,
            render_quality="export",
            output_size=(composition.width, composition.height),
        )
        image, report = render_graph_tiled(graph, tile_size=tile_size)
        self.last_tiled_report = report
        return image

    def render_rgba_array(self, composition: MotionComposition, time_ms: float, *, width: int | None = None,
                          height: int | None = None):
        import numpy as np

        image = self.render_frame(composition, time_ms, width=width, height=height)
        image = image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)
        array = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(image.height(), image.bytesPerLine())
        return array[:, : image.width() * 4].reshape(image.height(), image.width(), 4).copy()

    def save_png(self, composition: MotionComposition, time_ms: float, path: str | Path) -> Path:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        if not self.render_frame(composition, time_ms).save(str(output), "PNG"):
            raise RuntimeError(f"Failed to save motion frame: {output}")
        return output

    def export_png_sequence(self, composition: MotionComposition, output_dir: str | Path, *, fps: float | None = None) -> list[Path]:
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        frame_rate = float(fps or composition.fps)
        frame_count = max(1, int(round(composition.duration_ms / 1000.0 * frame_rate)))
        outputs: list[Path] = []
        for index in range(frame_count):
            outputs.append(self.save_png(composition, index * 1000.0 / frame_rate, directory / f"frame_{index:06d}.png"))
        return outputs

    def export_mp4(self, composition: MotionComposition, path: str | Path, *, fps: float | None = None) -> Path:
        from .export_pipeline import MotionProfileExporter

        output = Path(path).expanduser().resolve()
        MotionProfileExporter(self).export(composition, "h264_mp4", output, fps=fps)
        return output
