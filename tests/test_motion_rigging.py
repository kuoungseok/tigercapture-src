from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.composition_service import CompositionService
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.rigging import (
    apply_motion_preset,
    apply_pose,
    bake_two_bone_ik_constraint,
    bind_layer,
    composition_rigs,
    create_rig,
    create_humanoid_rig,
    mirror_rig_bones,
    save_pose,
    set_rig_constraint_enabled,
    set_two_bone_ik_constraint,
    solve_two_bone_ik,
    update_bone,
)
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.ui.canvas import MotionCanvas
from app.motion_designer.ui.window import MotionDocumentController
from app.motion_designer.validation import validate_composition


def _composition() -> MotionComposition:
    layers = [
        MotionLayer(id="layer_body", name="Body", layer_type="image"),
        MotionLayer(id="layer_arm", name="Arm", layer_type="image"),
        MotionLayer(id="layer_hand", name="Hand", layer_type="image"),
    ]
    return MotionComposition(
        id="composition_rig",
        width=1000,
        height=800,
        duration_ms=3000,
        layers=layers,
    )


def _bones() -> list[dict]:
    return [
        {
            "id": "bone_root",
            "name": "Root",
            "role": "root",
            "rest_position": [500, 560],
        },
        {
            "id": "bone_shoulder",
            "name": "Right Shoulder",
            "role": "upper_arm",
            "side": "right",
            "parent_id": "bone_root",
            "rest_position": [575, 330],
            "rotation_min": -95,
            "rotation_max": 95,
        },
        {
            "id": "bone_hand",
            "name": "Right Hand",
            "role": "hand",
            "side": "right",
            "parent_id": "bone_shoulder",
            "rest_position": [690, 430],
        },
    ]


def test_rig_contract_roundtrip_and_validation() -> None:
    composition = _composition()
    rig = create_rig(
        composition,
        name="Hero",
        bones=_bones(),
        bindings=[
            {"layer_id": "layer_body", "bone_id": "bone_root"},
            {"layer_id": "layer_arm", "bone_id": "bone_shoulder"},
            {"layer_id": "layer_hand", "bone_id": "bone_hand"},
        ],
    )
    assert validate_composition(composition).ok
    restored = MotionComposition.from_dict(composition.to_dict())
    restored_rig = composition_rigs(restored)[0]
    assert restored_rig.id == rig.id
    assert restored_rig.root_bone_id == "bone_root"
    assert restored_rig.bones[1].rotation_min == -95
    assert restored_rig.bindings[2].layer_id == "layer_hand"


def test_humanoid_rig_builds_symmetric_seventeen_bone_hierarchy() -> None:
    composition = _composition()
    rig = create_humanoid_rig(
        composition,
        layer_slots={
            "torso": "layer_body",
            "right_upper_arm": "layer_arm",
            "right_hand": "layer_hand",
        },
    )
    assert len(rig.bones) == 17
    assert len(rig.bindings) == 3
    roles = {(bone.role, bone.side) for bone in rig.bones}
    assert ("upper_arm", "left") in roles
    assert ("upper_arm", "right") in roles
    assert ("foot", "left") in roles
    assert ("foot", "right") in roles
    assert validate_composition(composition).ok


def test_rig_validation_rejects_cycles_and_missing_bindings() -> None:
    composition = _composition()
    create_rig(
        composition,
        bones=[
            {
                "id": "bone_a",
                "parent_id": "bone_b",
                "rest_position": [100, 100],
            },
            {
                "id": "bone_b",
                "parent_id": "bone_a",
                "rest_position": [200, 100],
            },
        ],
        bindings=[{"layer_id": "missing", "bone_id": "missing"}],
    )
    codes = {issue.code for issue in validate_composition(composition).issues}
    assert "rig_bone_cycle" in codes
    assert "missing_rig_binding_layer" in codes
    assert "missing_rig_binding_bone" in codes


def test_rig_service_mutation_is_validated() -> None:
    composition = _composition()
    rig = create_rig(composition, bones=_bones())
    service = CompositionService([composition])
    result = service.mutate_rig(
        composition.id,
        lambda candidate: {
            "bone": update_bone(
                candidate,
                rig.id,
                "bone_hand",
                {"rest_position": [720, 460]},
            ).to_dict(),
        },
        undo_label="Move Rig Bone",
    )
    assert result.changed and result.validation.ok
    moved = composition_rigs(service.get(composition.id))[0]
    assert moved.bones[2].rest_position == (720.0, 460.0)


def test_deleting_bound_layer_removes_rig_binding() -> None:
    composition = _composition()
    rig = create_rig(
        composition,
        bones=_bones(),
        bindings=[{"layer_id": "layer_arm", "bone_id": "bone_shoulder"}],
    )
    service = CompositionService([composition])
    result = service.delete_layer(composition.id, "layer_arm")
    assert result.changed and result.validation.ok
    restored_rig = composition_rigs(service.get(composition.id))[0]
    assert rig.id == restored_rig.id
    assert restored_rig.bindings == []


def test_two_bone_ik_is_limited_and_affects_bound_layer_evaluation() -> None:
    composition = _composition()
    composition.layers[2].transform.position.default = [690.0, 430.0]
    rig = create_rig(
        composition,
        bones=_bones(),
        bindings=[{"layer_id": "layer_hand", "bone_id": "bone_hand"}],
    )
    before = {
        row.id: row.matrix for row in evaluate_composition(composition, 0)
    }["layer_hand"]
    result = solve_two_bone_ik(
        composition,
        rig.id,
        root_bone_id="bone_root",
        mid_bone_id="bone_shoulder",
        end_bone_id="bone_hand",
        target=[720, 260],
        pole=[650, 500],
    )
    after = {
        row.id: row.matrix for row in evaluate_composition(composition, 0)
    }["layer_hand"]
    assert result["chain"] == ["bone_root", "bone_shoulder", "bone_hand"]
    assert result["rotation"]["bone_shoulder"] <= 95
    assert after != before


def test_persistent_ik_constraint_evaluates_without_mutating_document() -> None:
    composition = _composition()
    composition.layers[2].transform.position.default = [690.0, 430.0]
    rig = create_rig(
        composition,
        bones=_bones(),
        bindings=[{"layer_id": "layer_hand", "bone_id": "bone_hand"}],
    )
    constraint = set_two_bone_ik_constraint(
        composition,
        rig.id,
        root_bone_id="bone_root",
        mid_bone_id="bone_shoulder",
        end_bone_id="bone_hand",
        target={
            "default": [720, 260],
            "keyframes": [
                {"time_ms": 0, "value": [720, 260]},
                {"time_ms": 1000, "value": [760, 300]},
            ],
        },
        pole=[650, 500],
        lock_end=True,
    )
    assert validate_composition(composition).ok
    before = composition.to_dict()
    frame_0 = {
        row.id: row.matrix for row in evaluate_composition(composition, 0)
    }["layer_hand"]
    frame_1 = {
        row.id: row.matrix for row in evaluate_composition(composition, 1000)
    }["layer_hand"]
    assert frame_0 != frame_1
    assert composition.to_dict() == before
    set_rig_constraint_enabled(composition, rig.id, constraint["id"], False)
    disabled = {
        row.id: row.matrix for row in evaluate_composition(composition, 0)
    }["layer_hand"]
    assert disabled != frame_0


def test_ik_constraint_bakes_to_fk_and_disables_constraint() -> None:
    composition = _composition()
    rig = create_rig(composition, bones=_bones())
    constraint = set_two_bone_ik_constraint(
        composition,
        rig.id,
        root_bone_id="bone_root",
        mid_bone_id="bone_shoulder",
        end_bone_id="bone_hand",
        target=[720, 260],
        pole=[650, 500],
    )
    result = bake_two_bone_ik_constraint(
        composition,
        rig.id,
        constraint["id"],
        start_ms=0,
        end_ms=1000,
        sample_fps=10,
    )
    restored = composition_rigs(composition)[0]
    root = next(row for row in restored.bones if row.id == "bone_root")
    assert result["sample_count"] == 11
    assert len(root.rotation.keyframes) == 11
    assert restored.constraints[0]["enabled"] is False
    assert validate_composition(composition).ok


def test_pose_mirror_and_motion_presets_are_serialized() -> None:
    composition = _composition()
    bones = _bones() + [
        {
            "id": "bone_left_shoulder",
            "name": "Left Shoulder",
            "role": "upper_arm",
            "side": "left",
            "parent_id": "bone_root",
            "rest_position": [425, 330],
        },
    ]
    rig = create_rig(composition, bones=bones)
    update_bone(composition, rig.id, "bone_shoulder", {"rotation": 35.0})
    pose = save_pose(composition, rig.id, name="Wave")
    apply_pose(composition, rig.id, pose["id"], mirrored=True)
    restored = composition_rigs(composition)[0]
    left = next(row for row in restored.bones if row.id == "bone_left_shoulder")
    assert left.rotation.default == -35.0
    preset = apply_motion_preset(
        composition, rig.id, "arm_wave", start_ms=100, end_ms=1300,
    )
    assert preset["affected_bone_ids"]
    restored = MotionComposition.from_dict(composition.to_dict())
    right = next(
        row for row in composition_rigs(restored)[0].bones
        if row.id == "bone_shoulder"
    )
    assert [key.time_ms for key in right.rotation.keyframes] == [100, 340, 1060, 1300]


def test_mirror_bone_updates_counterpart_pose_limits_and_keys() -> None:
    composition = _composition()
    bones = _bones() + [
        {
            "id": "bone_left_shoulder",
            "name": "Left Shoulder",
            "role": "upper_arm",
            "side": "left",
            "parent_id": "bone_root",
            "rest_position": [425, 330],
        },
    ]
    rig = create_rig(composition, bones=bones)
    update_bone(
        composition,
        rig.id,
        "bone_shoulder",
        {
            "rotation_min": -80,
            "rotation_max": 110,
            "rotation": {
                "default": 15,
                "keyframes": [{"time_ms": 500, "value": 30}],
            },
        },
    )
    result = mirror_rig_bones(
        composition,
        rig.id,
        bone_ids=["bone_shoulder"],
        axis_x=500,
    )
    mirrored_rig = composition_rigs(composition)[0]
    left = next(row for row in mirrored_rig.bones if row.id == "bone_left_shoulder")
    assert result["updated_bone_ids"] == ["bone_left_shoulder"]
    assert left.rest_position == (425.0, 330.0)
    assert (left.rotation_min, left.rotation_max) == (-110.0, 80.0)
    assert left.rotation.default == -15.0
    assert left.rotation.keyframes[0].value == -30.0


def test_rig_canvas_overlay_and_controller_undo() -> None:
    QApplication.instance() or QApplication([])
    composition = _composition()
    rig = create_rig(composition, bones=_bones())
    bind_layer(composition, rig.id, "layer_arm", "bone_shoulder")
    controller = MotionDocumentController(composition, lambda _item: None)
    controller.update_rig_bone(
        rig.id, "bone_shoulder", {"rest_position": [600, 350]},
    )
    assert composition_rigs(controller.composition)[0].bones[1].rest_position == (
        600.0, 350.0,
    )
    controller.undo()
    assert composition_rigs(controller.composition)[0].bones[1].rest_position == (
        575.0, 330.0,
    )

    canvas = MotionCanvas()
    canvas.set_composition(controller.composition)
    canvas.set_selected_layer("layer_arm")
    handles = [
        item
        for item in canvas.scene().items()
        if item.data(1) == "rig_bone_handle"
    ]
    lines = [
        item
        for item in canvas.scene().items()
        if item.data(1) == "rig_bone_line"
    ]
    assert len(handles) == 3
    assert len(lines) == 2


class _Owner:
    def __init__(self) -> None:
        self._motion_compositions: dict[str, MotionComposition] = {}


def test_rig_actions_create_update_bind_and_inspect() -> None:
    owner = _Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {"name": "Rig Action", "duration_ms": 3000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    for layer in _composition().layers:
        assert registry.execute(
            "motion.layer.add",
            {"composition_id": composition_id, "layer": layer.to_dict()},
        ).ok
    rig_result = registry.execute(
        "motion.rig.create",
        {
            "composition_id": composition_id,
            "name": "Action Rig",
            "bones": _bones(),
        },
    )
    assert rig_result.ok
    rig_id = rig_result.result["payload"]["rig"]["id"]
    assert registry.execute(
        "motion.rig.layer.bind",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "bone_id": "bone_shoulder",
            "layer_id": "layer_arm",
        },
    ).ok
    assert registry.execute(
        "motion.rig.bone.update",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "bone_id": "bone_shoulder",
            "changes": {"rest_position": [610, 345]},
        },
    ).ok
    inspected = registry.execute(
        "motion.rig.inspect",
        {"composition_id": composition_id, "rig_id": rig_id},
    )
    assert inspected.ok
    assert inspected.result["rig"]["bones"][1]["rest_position"] == [610.0, 345.0]
    assert inspected.result["rig"]["bindings"][0]["layer_id"] == "layer_arm"
    solved = registry.execute(
        "motion.rig.ik.solve",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "root_bone_id": "bone_root",
            "mid_bone_id": "bone_shoulder",
            "end_bone_id": "bone_hand",
            "target": [720, 260],
        },
    )
    assert solved.ok
    constraint = registry.execute(
        "motion.rig.constraint.set",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "root_bone_id": "bone_root",
            "mid_bone_id": "bone_shoulder",
            "end_bone_id": "bone_hand",
            "target": [720, 260],
            "pole": [650, 500],
        },
    )
    assert constraint.ok
    constraint_id = constraint.result["payload"]["constraint"]["id"]
    assert registry.execute(
        "motion.rig.constraint.enable",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "constraint_id": constraint_id,
            "enabled": False,
        },
    ).ok
    assert registry.execute(
        "motion.rig.ik.bake",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "constraint_id": constraint_id,
            "start_ms": 0,
            "end_ms": 500,
            "sample_fps": 10,
        },
    ).ok
    assert registry.execute(
        "motion.rig.bone.mirror",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "bone_ids": ["bone_shoulder"],
            "axis_x": 500,
        },
    ).ok
    saved = registry.execute(
        "motion.rig.pose.save",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "name": "IK Pose",
        },
    )
    assert saved.ok
    assert registry.execute(
        "motion.rig.motion.apply",
        {
            "composition_id": composition_id,
            "rig_id": rig_id,
            "preset_id": "arm_wave",
            "start_ms": 0,
            "end_ms": 1200,
        },
    ).ok
    humanoid = registry.execute(
        "motion.rig.humanoid.create",
        {
            "composition_id": composition_id,
            "name": "Generated Humanoid",
            "layer_slots": {"torso": "layer_body"},
        },
    )
    assert humanoid.ok
    assert len(humanoid.result["payload"]["rig"]["bones"]) == 17
