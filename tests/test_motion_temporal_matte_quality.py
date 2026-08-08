from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import os

from PIL import Image, ImageDraw

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.actions.registry import ActionRegistry
from app.motion_designer.temporal_matte_quality import (
    TEMPORAL_MATTE_QUALITY_SCHEMA,
    analyze_temporal_matte_sequence,
    finalize_tracked_motion_mask,
)


def _mask(path: Path, box: tuple[int, int, int, int] | None) -> Path:
    image = Image.new("L", (160, 90), 0)
    if box is not None:
        ImageDraw.Draw(image).ellipse(box, fill=255)
    image.save(path)
    return path


def test_small_temporal_change_remains_propagatable(tmp_path: Path) -> None:
    paths = [
        _mask(tmp_path / "a.png", (55, 15, 105, 80)),
        _mask(tmp_path / "b.png", (56, 15, 106, 80)),
        _mask(tmp_path / "c.png", (57, 16, 107, 81)),
    ]

    report = analyze_temporal_matte_sequence(
        paths,
        times_ms=[0, 100, 200],
        confidences=[0.95, 0.92, 0.90],
    )

    assert report["schema"] == TEMPORAL_MATTE_QUALITY_SCHEMA
    assert report["status"] in {"stable", "review"}
    assert report["can_propagate"] is True
    assert report["auto_stop_at_ms"] is None


def test_disappearing_matte_stops_at_first_unsafe_frame(tmp_path: Path) -> None:
    paths = [
        _mask(tmp_path / "a.png", (55, 15, 105, 80)),
        _mask(tmp_path / "b.png", (58, 16, 108, 81)),
        _mask(tmp_path / "c.png", None),
    ]

    report = analyze_temporal_matte_sequence(
        paths,
        times_ms=[0, 100, 200],
        confidences=[0.9, 0.8, 0.0],
    )

    assert report["status"] == "stop_required"
    assert report["can_propagate"] is False
    assert report["auto_stop_at_ms"] == 200
    assert "matte_disappeared" in report["issues"][-1]["codes"]
    assert report["correction_times_ms"][-1] == 200


def test_temporal_matte_action_is_ownerless_and_callable(tmp_path: Path) -> None:
    paths = [
        _mask(tmp_path / "a.png", (55, 15, 105, 80)),
        _mask(tmp_path / "b.png", (56, 15, 106, 80)),
    ]
    registry = ActionRegistry(SimpleNamespace())
    action_ids = {item["id"] for item in registry.list_actions()}

    assert "motion.matte.temporal.validate" in action_ids
    execution = registry.execute("motion.matte.temporal.validate", {
        "mask_paths": [str(item) for item in paths],
        "times_ms": [0, 100],
    })
    assert execution.ok
    assert execution.result["schema"] == TEMPORAL_MATTE_QUALITY_SCHEMA


def test_tracked_mask_is_trimmed_and_timeline_exposes_quality_marker() -> None:
    from PySide6.QtWidgets import QApplication

    from app.motion_designer.mask_tracking import (
        MotionTrackSample,
        MotionTrackingCache,
    )
    from app.motion_designer.schema import (
        AnimatedProperty,
        MotionComposition,
        MotionLayer,
        MotionMaskRef,
    )
    from app.motion_designer.ui.timeline_tracks import LayerTimelineView

    app = QApplication.instance() or QApplication([])
    mask = MotionMaskRef(
        kind="rectangle",
        params={
            "x": AnimatedProperty(default=20),
            "y": AnimatedProperty(default=20),
            "width": AnimatedProperty(default=45),
            "height": AnimatedProperty(default=50),
        },
    )
    cache = MotionTrackingCache(samples=[
        MotionTrackSample(time_ms=0, translate=(0, 0), confidence=1.0),
        MotionTrackSample(time_ms=100, translate=(2, 0), confidence=0.9),
        MotionTrackSample(time_ms=200, translate=(90, 0), confidence=0.0),
    ])

    finalized = finalize_tracked_motion_mask(
        mask,
        width=160,
        height=90,
        tracking=cache,
    )
    report = finalized.metadata["temporal_matte_quality"]
    assert report["status"] == "stop_required"
    assert report["auto_stop_at_ms"] == 200
    assert len(finalized.samples) == 2
    assert finalized.metadata["untrimmed_sample_count"] == 3

    mask.metadata["tracking_cache"] = finalized.to_dict()
    composition = MotionComposition(
        width=160,
        height=90,
        duration_ms=500,
        layers=[MotionLayer(masks=[mask], out_ms=500)],
    )
    timeline = LayerTimelineView()
    timeline.set_state(composition, 0)
    assert (200, "error") in timeline._quality_markers()
    timeline.close()
    app.processEvents()
