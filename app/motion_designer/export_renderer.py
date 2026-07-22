"""Motion Designer still, sequence, and video renderer."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter

from .cache import MotionFrameCache
from .render_graph import build_render_graph, paint_render_graph
from .schema import MotionComposition
from .source_frame import transparent_image


class MotionExportRenderer:
    def __init__(self, *, cache_capacity: int = 120) -> None:
        self.cache = MotionFrameCache(cache_capacity)

    def render_frame(self, composition: MotionComposition, time_ms: float, *, width: int | None = None,
                     height: int | None = None, use_cache: bool = True) -> QImage:
        output_width = max(1, int(width or composition.width))
        output_height = max(1, int(height or composition.height))
        key = (composition.id, composition.revision, round(float(time_ms), 3), output_width, output_height)
        cached = self.cache.get(key) if use_cache else None
        if isinstance(cached, QImage):
            return cached.copy()
        image = transparent_image(output_width, output_height)
        painter = QPainter(image)
        paint_render_graph(painter, build_render_graph(composition, time_ms), QRectF(0, 0, output_width, output_height))
        painter.end()
        if use_cache:
            self.cache.put(key, image.copy())
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
        import cv2

        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        frame_rate = float(fps or composition.fps)
        writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), frame_rate,
                                 (composition.width, composition.height))
        if not writer.isOpened():
            raise RuntimeError(f"Failed to open MP4 writer: {output}")
        try:
            frame_count = max(1, int(round(composition.duration_ms / 1000.0 * frame_rate)))
            for index in range(frame_count):
                rgba = self.render_rgba_array(composition, index * 1000.0 / frame_rate)
                writer.write(cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR))
        finally:
            writer.release()
        return output
