from __future__ import annotations

from types import SimpleNamespace

from app.motion_designer.image_motion_validation import (
    validate_compiled_image_layers,
)
from app.motion_designer.schema import MotionLayer


def test_compiled_validation_rejects_missing_parent() -> None:
    layer = MotionLayer(name="Child", layer_type="image", parent_id="missing")
    report = validate_compiled_image_layers([layer])
    assert report.ok is False
    assert "missing parent" in report.errors[0].casefold()


def test_compiled_validation_detects_identical_independent_motion() -> None:
    cue = {
        "lock_to_background": False,
        "lock_to_parent": False,
        "end_offset_ratio": [0.1, 0.0],
        "start_ms": 100,
    }
    layers = [
        SimpleNamespace(
            id=f"layer_{index}",
            name=f"Layer {index}",
            parent_id="",
            metadata={
                "image_decomposition": {"role": "secondary_element"},
                "motion_choreography": dict(cue),
            },
        )
        for index in range(2)
    ]
    report = validate_compiled_image_layers(layers)
    assert report.ok is True
    assert any("same motion signature" in item for item in report.warnings)
