from __future__ import annotations

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.puppet_mesh import (
    add_puppet_pin,
    create_grid_puppet_mesh,
    layer_puppet_mesh,
)
from app.motion_designer.schema import (
    AnimatedProperty,
    MotionEffectRef,
    MotionLayer,
)
from app.motion_designer.tracking_workflow import (
    apply_planar_track_to_corner_pin,
    apply_track_to_effect_point,
    apply_track_to_layer,
    apply_track_to_puppet_pin,
    face_tracking_cache_from_video,
    normalize_track_asset,
    retime_tracking_samples,
    track_asset_diagnostics,
)


def _track() -> dict:
    return normalize_track_asset({
        "id": "camera-track",
        "kind": "planar",
        "source_revision": "revision-a",
        "samples": [
            {
                "time_ms": 0,
                "translate": [0, 0],
                "scale": [1, 1],
                "rotation": 0,
                "confidence": 0.95,
            },
            {
                "time_ms": 100,
                "translate": [10, -4],
                "scale": [1.2, 0.8],
                "rotation": 8,
                "confidence": 0.0,
            },
            {
                "time_ms": 200,
                "translate": [18, -7],
                "scale": [1.4, 0.7],
                "rotation": 12,
                "confidence": 0.88,
            },
        ],
    })


def test_track_diagnostics_report_occlusion_reacquire_and_revision() -> None:
    diagnostics = track_asset_diagnostics(
        _track(),
        current_source_revision="revision-b",
    )
    assert diagnostics["sample_count"] == 3
    assert diagnostics["occluded_sample_count"] == 1
    assert diagnostics["reacquire_count"] == 1
    assert diagnostics["maximum_step_px"] == pytest.approx(10.77, abs=0.02)
    assert diagnostics["source_revision_matches"] is False
    assert diagnostics["quality_state"] == "relink_required"
    assert "source_revision_mismatch" in diagnostics["review_reasons"]


def test_face_video_result_becomes_shared_planar_track_cache(
    tmp_path,
    monkeypatch,
) -> None:
    from app.vtuber.video_face_driver import (
        FaceMotionFrame,
        VideoFaceMotionExtractor,
        VideoFaceMotionResult,
    )

    source = tmp_path / "face.mp4"
    source.write_bytes(b"face-source")
    result = VideoFaceMotionResult(
        ok=True,
        frames=(
            FaceMotionFrame(
                time_ms=0,
                roll_deg=0,
                confidence=0.9,
                face_box=(40, 20, 100, 100),
            ),
            FaceMotionFrame(
                time_ms=100,
                roll_deg=5,
                confidence=0.8,
                face_box=(50, 25, 110, 110),
            ),
        ),
        diagnostics={"selected_backend": "test-face"},
    )
    monkeypatch.setattr(
        VideoFaceMotionExtractor,
        "extract",
        lambda self, _path, max_frames=None: result,
    )
    cache = face_tracking_cache_from_video(source)
    assert cache.mode == "planar"
    assert cache.origin == (90.0, 70.0)
    assert cache.samples[-1].translate == (15.0, 10.0)
    assert cache.samples[-1].scale == pytest.approx((1.1, 1.1))
    assert cache.samples[-1].rotation == 5.0
    assert cache.metadata["provider"] == "test-face"


def test_face_samples_retime_to_trimmed_layer_range() -> None:
    samples = [
        {"time_ms": 0, "translate": [0, 0]},
        {"time_ms": 500, "translate": [1, 0]},
        {"time_ms": 1000, "translate": [2, 0]},
        {"time_ms": 2000, "translate": [3, 0]},
        {"time_ms": 2500, "translate": [4, 0]},
    ]
    retimed = retime_tracking_samples(
        samples,
        source_in_ms=500,
        timeline_in_ms=3000,
        timeline_out_ms=4000,
        time_scale=2.0,
    )
    assert [item["time_ms"] for item in retimed] == [3000, 3250, 3750, 4000]
    assert [item["translate"][0] for item in retimed] == [1, 2, 3, 4]


def test_track_application_and_stabilization_are_inverse_bakes() -> None:
    attached = MotionLayer(id="attached")
    stabilized = MotionLayer(id="stabilized")

    apply_track_to_layer(attached, _track())
    apply_track_to_layer(stabilized, _track(), stabilize=True)

    assert attached.transform.position.keyframes[-1].value == [18.0, -7.0]
    assert attached.transform.scale.keyframes[-1].value == [1.4, 0.7]
    assert attached.transform.rotation.keyframes[-1].value == 12.0
    assert stabilized.transform.position.keyframes[-1].value == [-18.0, 7.0]
    assert stabilized.transform.scale.keyframes[-1].value == pytest.approx(
        [1 / 1.4, 1 / 0.7],
    )
    assert stabilized.transform.rotation.keyframes[-1].value == -12.0


def test_track_can_drive_effect_points_and_puppet_pins() -> None:
    effect = MotionEffectRef(
        id="warp",
        kind="corner_pin",
        params={"center": AnimatedProperty(default=[40.0, 50.0])},
    )
    effect_layer = MotionLayer(id="effect-layer", effects=[effect])
    effect_result = apply_track_to_effect_point(
        effect_layer,
        _track(),
        effect_id="warp",
        parameter="center",
    )
    assert effect_result["keyframe_count"] == 3
    assert effect.params["center"].keyframes[-1].value == [58.0, 43.0]

    puppet_layer = MotionLayer(id="puppet-layer")
    create_grid_puppet_mesh(puppet_layer, columns=2, rows=2)
    pin = add_puppet_pin(
        puppet_layer,
        kind="position",
        position=(0.5, 0.5),
    )
    puppet_result = apply_track_to_puppet_pin(
        puppet_layer,
        _track(),
        pin_id=pin.id,
        target_size=(100, 100),
    )
    assert puppet_result["keyframe_count"] == 3
    stored_pin = next(
        item for item in layer_puppet_mesh(puppet_layer).pins
        if item.id == pin.id
    )
    assert stored_pin.position.keyframes[-1].value == pytest.approx([0.68, 0.43])
    assert stored_pin.rotation.keyframes[-1].value == 12.0


def test_planar_track_can_drive_corner_pin_offsets() -> None:
    effect = MotionEffectRef(id="pin", kind="corner_pin")
    layer = MotionLayer(id="screen", effects=[effect])
    result = apply_planar_track_to_corner_pin(
        layer,
        normalize_track_asset({
            "id": "track_planar",
            "kind": "planar",
            "origin": [100, 50],
            "samples": [
                {"time_ms": 0},
                {
                    "time_ms": 1000,
                    "translate": [10, 5],
                    "scale": [1.1, 1.1],
                    "rotation": 0,
                },
            ],
        }),
        effect_id="pin",
        target_size=(201, 101),
    )
    assert result["parameters"] == [
        "top_left", "top_right", "bottom_right", "bottom_left",
    ]
    assert effect.params["top_left"].keyframes[-1].value == pytest.approx([0, 0])
    assert effect.params["top_right"].keyframes[-1].value == pytest.approx([20, 0])
    assert effect.params["bottom_right"].keyframes[-1].value == pytest.approx([20, 10])
    assert effect.params["bottom_left"].keyframes[-1].value == pytest.approx([0, 10])
    assert effect.metadata["tracking"]["mode"] == "planar_affine_corner_pin"


def test_tracking_actions_store_apply_diagnose_and_assisted_camera_solve(tmp_path) -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Tracked",
        "width": 640,
        "height": 360,
        "duration_ms": 1000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    layer_result = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {
            "id": "subject",
            "name": "Subject",
            "layer_type": "image",
            "out_ms": 1000,
            "source": {"kind": "image", "revision": "revision-a"},
        },
    })
    layer_id = layer_result.result["payload"]["composition"]["layers"][0]["id"]
    tracked = registry.execute("motion.track.create", {
        "composition_id": composition_id,
        "kind": "planar",
        "samples": _track()["cache"]["samples"],
        "source_revision": "revision-a",
    })
    assert tracked.ok
    track_id = tracked.result["track"]["id"]
    applied = registry.execute("motion.track.apply", {
        "composition_id": composition_id,
        "track_id": track_id,
        "layer_id": layer_id,
    })
    assert applied.ok and applied.result["keyframe_count"] == 3
    effect_added = registry.execute("motion.effect.add", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "effect": {"id": "screen-pin", "kind": "corner_pin"},
    })
    assert effect_added.ok
    corner_pinned = registry.execute("motion.track.apply", {
        "composition_id": composition_id,
        "track_id": track_id,
        "layer_id": layer_id,
        "target_kind": "corner_pin",
        "effect_id": "screen-pin",
    })
    assert corner_pinned.ok
    assert corner_pinned.result["mode"] == "corner_pin"
    stored_layer = owner._motion_compositions[composition_id].layers[0]
    stored_effect = next(
        item for item in stored_layer.effects if item.id == "screen-pin"
    )
    assert len(stored_effect.params["top_left"].keyframes) == 3
    diagnostics = registry.execute("motion.track.diagnostics", {
        "composition_id": composition_id,
        "track_id": track_id,
        "current_source_revision": "revision-a",
    })
    assert diagnostics.ok
    assert diagnostics.result["tracks"][0]["source_revision_matches"] is True
    relink_source = tmp_path / "replacement.mp4"
    relink_source.write_bytes(b"replacement-source")
    relinked = registry.execute("motion.track.relink", {
        "composition_id": composition_id,
        "track_id": track_id,
        "source_uri": str(relink_source),
    })
    assert relinked.ok
    assert relinked.result["track"]["source_revision"] != "revision-a"

    solved = registry.execute("motion.camera_solve.create", {
        "composition_id": composition_id,
        "image_points": [[100, 260], [320, 210], [540, 260]],
        "frame_size": [640, 360],
        "source_id": "plate",
    })
    assert solved.ok
    assert solved.result["camera_solution"]["model"] == "manual_depth_plane_v1"
    assert solved.result["diagnostics"]["manual_assist_required"] is True


def test_m18_action_contract_is_registered() -> None:
    ids = {row["id"] for row in ActionRegistry().list_actions()}
    assert {
        "motion.track.point",
        "motion.track.multi_point",
        "motion.track.planar",
        "motion.track.mask",
        "motion.track.face",
        "motion.track.apply",
        "motion.stabilize.create",
        "motion.camera_solve.create",
        "motion.track.diagnostics",
        "motion.track.relink",
    } <= ids


def test_face_action_can_retime_supplied_samples() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Face",
        "width": 640,
        "height": 360,
        "duration_ms": 5000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    result = registry.execute("motion.track.face", {
        "composition_id": composition_id,
        "samples": [
            {"time_ms": 0},
            {"time_ms": 500},
            {"time_ms": 1000},
            {"time_ms": 2000},
        ],
        "source_in_ms": 500,
        "timeline_in_ms": 3000,
        "timeline_out_ms": 3750,
        "time_scale": 2.0,
        "origin": [320, 180],
    })
    assert result.ok
    samples = result.result["track"]["cache"]["samples"]
    assert [item["time_ms"] for item in samples] == [3000, 3250, 3750]
    assert result.result["track"]["cache"]["origin"] == [320.0, 180.0]
