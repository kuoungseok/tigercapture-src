from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest
import numpy as np

from app.actions.registry import ActionRegistry
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.mask_tracking import MotionTrackingCache, evaluate_tracking_cache
from app.motion_designer.tracking_provider import (
    MotionTrackingRequest,
    generate_tracking_cache,
    tracking_request_for_mask,
)
from app.motion_designer.schema import (
    AnimatedProperty, Keyframe, MotionComposition, MotionLayer, MotionMaskRef, SourceRef,
)
from app.motion_designer.validation import validate_composition


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _rectangle_path(x: float, y: float, width: float, height: float) -> dict:
    return {
        "closed": True,
        "points": [
            {"position": [x, y]},
            {"position": [x + width, y]},
            {"position": [x + width, y + height]},
            {"position": [x, y + height]},
        ],
    }


def _write_tracking_video(path, *, planar: bool = False, shot_cut: bool = False) -> None:
    import cv2

    width, height = 320, 240
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (width, height),
    )
    assert writer.isOpened()
    rng = np.random.default_rng(4107)
    patch = rng.integers(24, 236, size=(100, 120, 3), dtype=np.uint8)
    for y in range(0, patch.shape[0], 10):
        cv2.line(patch, (0, y), (patch.shape[1] - 1, y), (245, 245, 245), 1)
    for x in range(0, patch.shape[1], 10):
        cv2.line(patch, (x, 0), (x, patch.shape[0] - 1), (12, 12, 12), 1)
    base = np.zeros((height, width, 3), dtype=np.uint8)
    base[70:170, 90:210] = patch
    cut_frame = np.zeros_like(base)
    cut_frame[:, :] = (230, 230, 230)
    cut_frame[30:210, 40:280] = rng.integers(0, 255, size=(180, 240, 3), dtype=np.uint8)
    for index in range(31):
        if shot_cut and index >= 15:
            frame = cut_frame.copy()
        elif planar:
            matrix = cv2.getRotationMatrix2D((150.0, 120.0), index * 0.4, 1.0 + index * 0.003)
            matrix[:, 2] += [index * 0.8, index * 0.35]
            frame = cv2.warpAffine(base, matrix, (width, height))
        else:
            matrix = np.asarray([[1.0, 0.0, index * 1.6], [0.0, 1.0, index * 0.7]])
            frame = cv2.warpAffine(base, matrix, (width, height))
        writer.write(frame)
    writer.release()


def _write_featureless_intro_tracking_video(path) -> None:
    import cv2

    width, height = 320, 240
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (width, height),
    )
    assert writer.isOpened()
    rng = np.random.default_rng(9127)
    patch = rng.integers(24, 236, size=(100, 120, 3), dtype=np.uint8)
    for index in range(42):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        if index >= 12:
            offset = index - 12
            x = 90 + offset
            y = 70 + offset // 2
            frame[y:y + 100, x:x + 120] = patch
        writer.write(frame)
    writer.release()


def _write_occluded_tracking_video(path) -> None:
    import cv2

    width, height = 320, 240
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (width, height),
    )
    assert writer.isOpened()
    rng = np.random.default_rng(613)
    patch = rng.integers(24, 236, size=(100, 120, 3), dtype=np.uint8)
    for index in range(42):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        if not 14 <= index <= 19:
            x = 90 + index
            y = 70 + index // 2
            frame[y:y + 100, x:x + 120] = patch
        writer.write(frame)
    writer.release()


def _write_teleport_tracking_video(path) -> None:
    import cv2

    width, height = 320, 240
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30.0, (width, height),
    )
    assert writer.isOpened()
    rng = np.random.default_rng(317)
    patch = rng.integers(24, 236, size=(80, 80, 3), dtype=np.uint8)
    for index in range(31):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        x = 30 + (index % 8) * 20
        frame[80:160, x:x + 80] = patch
        writer.write(frame)
    writer.release()


def test_point_and_planar_tracking_cache_interpolate_deterministically() -> None:
    rows = [
        {"time_ms": 0, "translate": [0, 0], "scale": [1, 1], "rotation": 0},
        {"time_ms": 1000, "translate": [100, 40], "scale": [2, .5], "rotation": 90},
    ]
    point = evaluate_tracking_cache({"mode": "point", "samples": rows}, 250)
    assert point.translate == pytest.approx((25, 10))
    assert point.scale == (1, 1)
    assert point.rotation == 0
    planar = evaluate_tracking_cache({"mode": "planar", "samples": rows}, 500)
    assert planar.translate == pytest.approx((50, 20))
    assert planar.scale == pytest.approx((1.5, .75))
    assert planar.rotation == pytest.approx(45)


def test_tracking_correction_keyframes_are_interpolated_over_cached_motion() -> None:
    cache = MotionTrackingCache.from_dict({
        "mode": "planar",
        "samples": [
            {"time_ms": 0, "translate": [0, 0], "scale": [1, 1], "rotation": 0},
            {"time_ms": 1000, "translate": [100, 40], "scale": [2, 2], "rotation": 20},
        ],
        "corrections": [
            {"time_ms": 0, "translate": [0, 0], "scale": [1, 1], "rotation": 0},
            {"time_ms": 1000, "translate": [20, -10], "scale": [0.5, 1.5], "rotation": 10},
        ],
    })
    result = evaluate_tracking_cache(cache, 500)
    assert result.translate == pytest.approx((60, 15))
    assert result.scale == pytest.approx((1.125, 1.875))
    assert result.rotation == pytest.approx(15)


def test_animated_path_and_tracking_cache_match_seeked_render_positions() -> None:
    app = _app()
    path = AnimatedProperty(value_type="path", default=_rectangle_path(0, 0, 24, 40), keyframes=[
        Keyframe(time_ms=0, value=_rectangle_path(0, 0, 24, 40)),
        Keyframe(time_ms=1000, value=_rectangle_path(20, 0, 24, 40)),
    ])
    mask = MotionMaskRef(kind="path", mode="add", params={
        "path": path,
        "opacity": AnimatedProperty(default=1.0),
        "feather": AnimatedProperty(default=0.0),
        "expansion": AnimatedProperty(default=0.0),
    }, metadata={"tracking_cache": MotionTrackingCache.from_dict({
        "mode": "point",
        "samples": [
            {"time_ms": 0, "translate": [0, 0]},
            {"time_ms": 1000, "translate": [40, 0]},
        ],
    }).to_dict()})
    layer = MotionLayer(
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 100, "height": 40, "fill": "#ffffff", "stroke_width": 0,
        }),
        out_ms=1100,
        masks=[mask],
    )
    layer.transform.position.default = [0, 0]
    layer.transform.anchor.default = [0, 0]
    composition = MotionComposition(width=100, height=40, duration_ms=1000, layers=[layer])
    renderer = MotionExportRenderer()
    start = renderer.render_rgba_array(composition, 0)
    middle = renderer.render_rgba_array(composition, 500)
    end = renderer.render_rgba_array(composition, 1000)
    assert start[20, 10, 3] > 200 and start[20, 70, 3] == 0
    assert middle[20, 40, 3] > 200 and middle[20, 10, 3] == 0
    assert end[20, 70, 3] > 200 and end[20, 10, 3] == 0
    app.processEvents()


def test_mask_feather_expansion_and_tracking_validation() -> None:
    app = _app()
    mask = MotionMaskRef(kind="rectangle", mode="add", params={
        "x": AnimatedProperty(default=20), "y": AnimatedProperty(default=10),
        "width": AnimatedProperty(default=20), "height": AnimatedProperty(default=20),
        "feather": AnimatedProperty(default=3.0), "expansion": AnimatedProperty(default=4.0),
        "opacity": AnimatedProperty(default=.5),
    }, metadata={"tracking_cache": {"mode": "point", "enabled": True, "samples": []}})
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 64, "height": 48, "fill": "#ffffff", "stroke_width": 0,
    }), out_ms=1000, masks=[mask])
    layer.transform.position.default = [0, 0]
    layer.transform.anchor.default = [0, 0]
    composition = MotionComposition(width=64, height=48, duration_ms=1000, layers=[layer])
    alpha = MotionExportRenderer().render_rgba_array(composition, 0)[..., 3]
    assert 80 < int(alpha[20, 25]) < 160
    assert 0 < int(alpha[20, 15]) < int(alpha[20, 25])
    report = validate_composition(composition)
    assert report.ok
    assert any(issue.code == "empty_mask_tracking_cache" for issue in report.issues)
    app.processEvents()


def test_point_tracking_provider_recovers_known_translation(tmp_path) -> None:
    video = tmp_path / "point.avi"
    _write_tracking_video(video)
    cache = generate_tracking_cache(MotionTrackingRequest(
        video_path=str(video),
        mode="point",
        end_ms=1000,
        sample_interval_ms=100,
        target_size=(320, 240),
        roi=(85, 65, 140, 115),
        max_analysis_dimension=320,
    ))
    assert cache.metadata["provider"] == "opencv_lk_ransac_v1"
    assert len(cache.samples) >= 9
    assert cache.samples[-1].translate == pytest.approx((48.0, 21.0), abs=2.5)
    assert cache.metadata["failed_frames"] <= 1
    assert cache.metadata["mean_confidence"] > 0.45


def test_planar_tracking_provider_recovers_rotation_and_scale(tmp_path) -> None:
    video = tmp_path / "planar.avi"
    _write_tracking_video(video, planar=True)
    cache = generate_tracking_cache(MotionTrackingRequest(
        video_path=str(video),
        mode="planar",
        end_ms=1000,
        sample_interval_ms=100,
        target_size=(320, 240),
        roi=(80, 60, 150, 125),
        max_analysis_dimension=320,
    ))
    final = cache.samples[-1]
    assert len(cache.samples) >= 9
    assert final.scale[0] == pytest.approx(1.09, abs=0.035)
    assert final.scale[1] == pytest.approx(1.09, abs=0.035)
    assert abs(final.rotation) == pytest.approx(12.0, abs=2.0)
    assert final.confidence > 0.35


def test_layer_request_maps_source_time_to_composition_and_uses_mask_roi(tmp_path) -> None:
    video = tmp_path / "timing.avi"
    _write_tracking_video(video)
    mask = MotionMaskRef(kind="rectangle", params={
        "x": AnimatedProperty(default=80), "y": AnimatedProperty(default=60),
        "width": AnimatedProperty(default=140), "height": AnimatedProperty(default=120),
    }, metadata={"tracking_cache": {"mode": "point"}})
    layer = MotionLayer(
        layer_type="image",
        source=SourceRef(kind="image", uri=str(video), params={"width": 320, "height": 240}),
        in_ms=500,
        out_ms=1000,
        source_in_ms=0,
        time_scale=2.0,
        masks=[mask],
    )
    composition = MotionComposition(width=320, height=240, duration_ms=1500, layers=[layer])
    request = tracking_request_for_mask(composition, layer, mask, sample_interval_ms=100)
    assert request.roi == (80.0, 60.0, 140.0, 120.0)
    cache = generate_tracking_cache(request)
    assert cache.samples[0].time_ms == 500
    assert cache.samples[-1].time_ms == pytest.approx(1000, abs=20)
    assert cache.metadata["timeline_time_scale"] == 2.0


def test_tracking_generate_action_persists_provider_cache(tmp_path) -> None:
    video = tmp_path / "action-point.avi"
    _write_tracking_video(video)

    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Tracked", "width": 320, "height": 240, "duration_ms": 1000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {
            "name": "Footage", "layer_type": "image", "out_ms": 1000,
            "source": {
                "kind": "image", "uri": str(video),
                "params": {"width": 320, "height": 240},
            },
        },
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    mask_result = registry.execute("motion.mask.add", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask": {
            "kind": "rectangle",
            "params": {
                "x": {"default": 85}, "y": {"default": 65},
                "width": {"default": 140}, "height": {"default": 115},
            },
            "metadata": {"tracking_cache": {"mode": "point"}},
        },
    })
    mask_id = mask_result.result["mask"]["id"]
    tracked = registry.execute("motion.mask.tracking.generate", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask_id": mask_id,
        "sample_interval_ms": 100,
    })
    assert tracked.ok
    assert tracked.result["sample_count"] >= 9
    stored = owner._motion_compositions[composition_id].layers[0].masks[0]
    cache = stored.metadata["tracking_cache"]
    assert cache["metadata"]["provider"] == "opencv_lk_ransac_v1"
    assert cache["samples"][-1]["translate"] == pytest.approx([48.0, 21.0], abs=2.5)


def test_matte_correction_freeze_and_diagnostics_actions() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Matte", "width": 100, "height": 100, "duration_ms": 1000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {
            "id": "footage",
            "name": "Footage",
            "layer_type": "image",
            "out_ms": 1000,
            "source": {"kind": "image", "uri": "missing.mp4"},
        },
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    mask_result = registry.execute("motion.mask.add", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask": {"id": "subject", "kind": "rectangle"},
    })
    mask_id = mask_result.result["mask"]["id"]
    assert registry.execute("motion.mask.tracking.set", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask_id": mask_id,
        "tracking": {
            "mode": "point",
            "samples": [
                {"time_ms": 0, "translate": [0, 0], "confidence": 0.9},
                {"time_ms": 1000, "translate": [10, 4], "confidence": 0.8},
            ],
        },
    }).ok
    corrected = registry.execute("motion.matte.correction.set", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask_id": mask_id,
        "time_ms": 500,
        "translate": [3, -2],
        "rotation": 4,
    })
    assert corrected.ok and corrected.result["correction_count"] == 1
    frozen = registry.execute("motion.matte.freeze", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask_id": mask_id,
        "frozen": True,
    })
    assert frozen.ok and frozen.result["frozen"] is True
    diagnostics = registry.execute("motion.matte.diagnostics", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask_id": mask_id,
    })
    assert diagnostics.ok
    assert diagnostics.result["masks"][0]["sample_count"] == 2
    assert diagnostics.result["masks"][0]["correction_count"] == 1
    assert diagnostics.result["masks"][0]["frozen"] is True
    blocked = registry.execute("motion.matte.propagate", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "mask_id": mask_id,
    })
    assert not blocked.ok
    assert "frozen" in blocked.error.lower()


def test_tracking_provider_stops_at_shot_cut_instead_of_carrying_transform(tmp_path) -> None:
    video = tmp_path / "shot-cut.avi"
    _write_tracking_video(video, shot_cut=True)
    cache = generate_tracking_cache(MotionTrackingRequest(
        video_path=str(video),
        mode="planar",
        end_ms=1000,
        sample_interval_ms=100,
        target_size=(320, 240),
        roi=(85, 65, 140, 115),
        max_analysis_dimension=320,
    ))
    assert cache.metadata["terminated_reason"] == "shot_cut"
    assert cache.metadata["shot_cut_frames"] == 1
    assert 400 <= cache.metadata["actual_end_ms"] <= 550
    assert cache.samples[-1].confidence == 0.0


def test_tracking_provider_acquires_after_featureless_opening(tmp_path) -> None:
    video = tmp_path / "featureless-intro.avi"
    _write_featureless_intro_tracking_video(video)
    cache = generate_tracking_cache(MotionTrackingRequest(
        video_path=str(video),
        mode="point",
        end_ms=1350,
        sample_interval_ms=100,
        target_size=(320, 240),
        roi=(80, 60, 170, 140),
        max_analysis_dimension=320,
    ))
    assert cache.metadata["acquisition_frames_skipped"] >= 12
    assert len(cache.samples) >= 7
    assert cache.samples[0].translate == (0.0, 0.0)
    assert cache.samples[-1].translate[0] == pytest.approx(29.0, abs=3.0)
    assert cache.samples[-1].translate[1] == pytest.approx(14.0, abs=3.0)
    assert cache.metadata["mean_confidence"] > 0.4


def test_tracking_provider_reacquires_after_full_occlusion(tmp_path) -> None:
    video = tmp_path / "occluded.avi"
    _write_occluded_tracking_video(video)
    cache = generate_tracking_cache(MotionTrackingRequest(
        video_path=str(video),
        mode="point",
        end_ms=1350,
        sample_interval_ms=100,
        target_size=(320, 240),
        roi=(80, 60, 180, 150),
        max_analysis_dimension=320,
        analysis_fps=30,
    ))
    assert cache.metadata["failed_frames"] >= 1
    assert cache.metadata["reacquired_frames"] >= 1
    assert 1 <= cache.metadata["predicted_frames"] <= 15
    assert cache.samples[-1].translate[0] == pytest.approx(41.0, abs=5.0)
    assert cache.samples[-1].translate[1] == pytest.approx(20.0, abs=4.0)


def test_tracking_provider_rejects_implausible_point_teleport(tmp_path) -> None:
    video = tmp_path / "teleport.avi"
    _write_teleport_tracking_video(video)
    cache = generate_tracking_cache(MotionTrackingRequest(
        video_path=str(video),
        mode="point",
        end_ms=1000,
        sample_interval_ms=100,
        target_size=(320, 240),
        roi=(20, 60, 290, 130),
        max_analysis_dimension=320,
        analysis_fps=30,
    ))
    steps = [
        (
            (current.translate[0] - previous.translate[0]) ** 2
            + (current.translate[1] - previous.translate[1]) ** 2
        ) ** 0.5
        for previous, current in zip(cache.samples, cache.samples[1:])
    ]
    assert cache.metadata["failed_frames"] >= 1
    assert cache.metadata["motion_outlier_frames"] >= 1
    assert max(steps, default=0.0) < 50.0
