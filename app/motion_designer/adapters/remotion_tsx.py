from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from app.motion_designer.remotion_tsx import REMOTION_TSX_SOURCE_KIND, inspect_remotion_tsx
from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import premultiplied, transparent_image


def render_remotion_tsx(layer: MotionLayer, time_ms: float = 0.0, **_kwargs):
    if layer.layer_type != REMOTION_TSX_SOURCE_KIND and layer.source.kind != REMOTION_TSX_SOURCE_KIND:
        return transparent_image(1, 1)
    params = layer.source.params
    source = Path(layer.source.uri).expanduser().resolve(strict=False)
    frame_dir = Path(str(params.get("frame_dir") or "")).expanduser().resolve(strict=False)
    prepared_hash = str(params.get("prepared_source_sha256") or "")
    try:
        current_hash = inspect_remotion_tsx(source).source_sha256
    except (OSError, ValueError, UnicodeError):
        return transparent_image(1, 1)
    if not prepared_hash or current_hash != prepared_hash or not frame_dir.is_dir():
        return transparent_image(1, 1)
    fps = max(1.0, float(params.get("fps", 30.0) or 30.0))
    count = max(1, int(params.get("duration_frames", 1) or 1))
    frame = min(count - 1, max(0, int(round(float(time_ms) * fps / 1000.0))))
    image = QImage(str(frame_dir / f"frame_{frame:06d}.png"))
    if image.isNull():
        return transparent_image(1, 1)
    return premultiplied(image)


__all__ = ["render_remotion_tsx"]
