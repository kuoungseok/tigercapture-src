from __future__ import annotations

import pytest

from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.stop_motion import (
    STOP_MOTION_POSE_SCHEMA,
    STOP_MOTION_SCHEMA,
    apply_stop_motion_pose,
    capture_stop_motion_pose,
    composition_stop_motion,
    preflight_stop_motion,
    set_stop_motion,
    set_stop_motion_material,
    snap_stop_motion_to_audio,
    stop_motion_onion_samples,
    stop_motion_sample_time,
)


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="Mascot",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": 180,
                "height": 220,
                "fill": "#d86d4c",
            },
        ),
        out_ms=3000,
    )
    layer.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[100.0, 180.0],
        keyframes=[
            Keyframe(time_ms=0, value=[100.0, 180.0], interpolation="linear"),
            Keyframe(time_ms=1000, value=[500.0, 180.0], interpolation="linear"),
        ],
    )
    return MotionComposition(
        name="Stop Motion",
        width=640,
        height=360,
        fps=30,
        duration_ms=3000,
        layers=[layer],
    )


@pytest.mark.parametrize(
    ("exposure_frames", "expected"),
    [(1, 100.0), (2, 66.6666666667), (3, 100.0)],
)
def test_stop_motion_ones_twos_threes_quantize_time(exposure_frames, expected):
    composition = _composition()
    set_stop_motion(
        composition,
        {"enabled": True, "exposure_frames": exposure_frames},
    )
    sampled = stop_motion_sample_time(composition, composition.layers[0], 119.0)
    assert sampled == pytest.approx(expected)


def test_evaluator_holds_transform_and_jitter_inside_exposure():
    composition = _composition()
    set_stop_motion(
        composition,
        {
            "enabled": True,
            "exposure_frames": 3,
            "pose_jitter_px": 2.0,
            "rotation_jitter_deg": 0.4,
            "scale_jitter": 0.01,
            "seed": 29,
        },
    )
    left = evaluate_composition(composition, 105.0)[0]
    middle = evaluate_composition(composition, 166.0)[0]
    next_frame = evaluate_composition(composition, 205.0)[0]

    assert left.position == middle.position
    assert left.rotation == middle.rotation
    assert left.scale == middle.scale
    assert next_frame.position != middle.position


def test_layer_override_can_use_different_exposure_than_composition():
    composition = _composition()
    layer = composition.layers[0]
    set_stop_motion(composition, {"enabled": True, "exposure_frames": 3})
    set_stop_motion(
        composition,
        {"enabled": True, "exposure_frames": 1},
        layer_ids=[layer.id],
    )

    assert composition_stop_motion(composition)["exposure_frames"] == 3
    assert stop_motion_sample_time(composition, layer, 79) == pytest.approx(66.6666667)


def test_pose_capture_and_apply_preserve_pose_and_keyframe_ids():
    composition = _composition()
    set_stop_motion(composition, {"enabled": True, "exposure_frames": 2})
    pose = capture_stop_motion_pose(
        composition,
        name="Contact",
        time_ms=600,
        layer_ids=[composition.layers[0].id],
    )
    result = apply_stop_motion_pose(
        composition,
        pose["id"],
        time_ms=1200,
    )
    first_ids = result["applied"][0]["keyframe_ids"]
    result_again = apply_stop_motion_pose(
        composition,
        pose["id"],
        time_ms=1200,
    )

    assert pose["schema"] == STOP_MOTION_POSE_SCHEMA
    assert result_again["applied"][0]["keyframe_ids"] == first_ids
    assert all(
        key.interpolation == "hold"
        for prop in composition.layers[0].transform.properties().values()
        for key in prop.keyframes
        if key.time_ms == 1200
    )


@pytest.mark.parametrize("preset", ["clay", "felt", "cardboard", "painted_wood"])
def test_material_presets_add_craft_boil_and_contact_shadow(preset):
    composition = _composition()
    layer = composition.layers[0]
    result = set_stop_motion_material(
        composition,
        [layer.id],
        preset=preset,
        seed=31,
    )

    assert result["preset"] == preset
    assert layer.metadata["stop_motion_material"]["preset"] == preset
    assert layer.metadata["stop_motion"]["enabled"] is True
    assert {effect.kind for effect in layer.effects} >= {"craft_style", "drop_shadow"}
    assert all(effect.metadata["material_preset"] == preset for effect in layer.effects)


def test_audio_snap_moves_nearby_keys_to_exposure_grid_and_preflight_passes():
    composition = _composition()
    layer = composition.layers[0]
    layer.transform.position.keyframes[1].time_ms = 1015
    set_stop_motion(composition, {"enabled": True, "exposure_frames": 3})

    result = snap_stop_motion_to_audio(
        composition,
        transient_times_ms=[995],
        layer_ids=[layer.id],
        threshold_ms=40,
    )
    report = preflight_stop_motion(composition, layer_ids=[layer.id])

    assert result["move_count"] == 1
    assert layer.transform.position.keyframes[1].time_ms == 1000
    assert report["ok"]
    assert report["summary"]["cadence_violation_count"] == 0


def test_onion_samples_return_previous_current_and_next_held_pose():
    composition = _composition()
    layer = composition.layers[0]
    set_stop_motion(
        composition,
        {"enabled": True, "exposure_frames": 2, "onion_skin_frames": 1},
    )
    onion = stop_motion_onion_samples(
        composition,
        layer_id=layer.id,
        time_ms=500,
    )

    assert onion["schema"] == "tigerstudio.motion.stop_motion.onion.v1"
    assert [item["offset"] for item in onion["samples"]] == [-1, 0, 1]
    assert onion["exposure_ms"] == pytest.approx(66.6666667)


def test_stop_motion_contract_roundtrips_in_motion_document():
    composition = _composition()
    set_stop_motion(
        composition,
        {
            "enabled": True,
            "exposure_frames": 2,
            "motion_style": "contact_settle",
            "material_boil": 0.3,
        },
    )
    restored = MotionComposition.from_dict(composition.to_dict())

    assert restored.metadata["stop_motion"]["schema"] == STOP_MOTION_SCHEMA
    assert composition_stop_motion(restored)["motion_style"] == "contact_settle"


def test_stop_motion_umg_preflight_is_explicitly_blocked_for_bake():
    import json

    from app.unreal_umg_document import motion_composition_to_umg_document

    composition = _composition()
    set_stop_motion(composition, {"enabled": True, "exposure_frames": 2})
    document = motion_composition_to_umg_document(composition)
    payload = json.loads(document["Layers"][0]["PayloadJson"])

    assert document["Layers"][0]["Disposition"] == "Blocked"
    assert (
        "motion_feature_requires_bake:stop_motion"
        in payload["umg_block_reasons"]
    )


def test_stop_motion_actions_are_registered():
    from app.actions.motion_namespace import register_motion_actions

    class Registry:
        def __init__(self):
            self.rows = {}

        def register_adapter_action(self, action_id, *args, **kwargs):
            self.rows[action_id] = kwargs

    registry = Registry()
    register_motion_actions(registry)

    expected = {
        "motion.stop_motion.get",
        "motion.stop_motion.set",
        "motion.stop_motion.pose.capture",
        "motion.stop_motion.pose.apply",
        "motion.stop_motion.material.set",
        "motion.stop_motion.audio.snap",
        "motion.stop_motion.onion.inspect",
        "motion.stop_motion.preflight",
    }
    assert expected <= set(registry.rows)
    assert registry.rows["motion.stop_motion.get"]["mutating"] is False
    assert registry.rows["motion.stop_motion.preflight"]["changed"] is False
