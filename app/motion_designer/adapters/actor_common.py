"""Shared image and cache helpers for Motion actor adapters."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import premultiplied, transparent_image


def actor_source_signature(layer: MotionLayer) -> tuple[Any, ...]:
    path = Path(layer.source.uri)
    try:
        stat = path.stat()
        file_signature = (str(path.resolve()), int(stat.st_size), int(stat.st_mtime_ns))
    except OSError:
        file_signature = (str(path), 0, 0)
    return (
        *file_signature,
        str(layer.source.revision or ""),
        json.dumps(layer.source.params, sort_keys=True, ensure_ascii=True, default=str),
        json.dumps(layer.metadata.get("lip_sync_cues") or [], sort_keys=True, ensure_ascii=True, default=str),
    )


def actor_qimage(value: Any, width: int, height: int) -> QImage:
    if isinstance(value, QImage):
        return premultiplied(value.copy())
    try:
        import numpy as np

        if hasattr(value, "convert") and not isinstance(value, np.ndarray):
            value = np.asarray(value.convert("RGBA"), dtype=np.uint8)
        array = np.asarray(value, dtype=np.uint8)
        if array.ndim == 3 and array.shape[2] in {3, 4}:
            if array.shape[2] == 3:
                alpha = np.full((*array.shape[:2], 1), 255, dtype=np.uint8)
                array = np.concatenate((array, alpha), axis=2)
            rgba = np.ascontiguousarray(array)
            image = QImage(
                rgba.data, int(rgba.shape[1]), int(rgba.shape[0]), int(rgba.strides[0]), QImage.Format_RGBA8888,
            ).copy()
            return premultiplied(image)
    except Exception:
        pass
    return transparent_image(width, height)


__all__ = ["actor_qimage", "actor_source_signature"]
