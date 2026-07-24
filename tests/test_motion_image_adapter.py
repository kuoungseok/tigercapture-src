from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage

from app.motion_designer.adapters.image import render_image
from app.motion_designer.schema import MotionLayer, SourceRef


def _alpha_count(image) -> int:
    alpha = image.convertToFormat(QImage.Format.Format_Alpha8)
    bits = alpha.constBits()
    return sum(1 for value in bytes(bits) if value)


def test_image_tilt_changes_pixels_and_exposes_transparent_corners(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "source.png"
    Image.new("RGBA", (180, 120), (230, 90, 45, 255)).save(source_path)
    layer = MotionLayer(
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(source_path),
            params={
                "width": 180,
                "height": 120,
                "fit": "cover",
                "tilt_x": 0.0,
                "tilt_y": 0.0,
                "perspective": 2.6,
            },
        ),
    )

    flat = render_image(layer, time_ms=0.0)
    layer.source.params["tilt_x"] = 18.0
    layer.source.params["tilt_y"] = -22.0
    tilted = render_image(layer, time_ms=0.0)

    assert flat.size() == tilted.size()
    assert _alpha_count(flat) == flat.width() * flat.height()
    assert _alpha_count(tilted) < _alpha_count(flat)
    assert bytes(flat.constBits()) != bytes(tilted.constBits())
