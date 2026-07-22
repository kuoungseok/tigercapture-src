from app.actions.registry import ActionRegistry
from app.motion_designer.evaluator import evaluate_composition


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_motion_actions_share_service_and_support_dry_run() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    preview = registry.execute("motion.composition.create", {"name": "Dry"}, dry_run=True)
    assert preview.ok and not owner._motion_compositions

    created = registry.execute("motion.composition.create", {"name": "Real"})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Title", "layer_type": "text", "source": {"kind": "text", "params": {"text": "Tiger"}}},
    })
    assert added.ok
    listed = registry.execute("motion.layer.list", {"composition_id": composition_id})
    assert listed.result["count"] == 1
    specs = {row["id"]: row for row in registry.list_actions()}
    assert specs["motion.layer.add"]["undo_label"]


def test_advanced_keyframe_and_behavior_actions_are_automation_ready() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Automation", "duration_ms": 1000})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Box", "layer_type": "shape", "out_ms": 1000},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    first = registry.execute("motion.keyframe.add", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position",
        "keyframe": {"time_ms": 100, "value": [10, 20]},
    })
    assert first.ok
    key_id = owner._motion_compositions[composition_id].layers[0].transform.position.keyframes[0].id
    assert registry.execute("motion.keyframe.set_interpolation", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position",
        "keyframe_id": key_id, "interpolation": "hold",
    }).ok
    assert registry.execute("motion.keyframe.copy", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position",
    }).result["copied"] == 1
    assert registry.execute("motion.keyframe.paste", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position", "time_ms": 500,
    }).result["pasted"] == 1
    retimed = registry.execute("motion.curve.retime", {
        "composition_id": composition_id, "layer_id": layer_id, "property_name": "position", "offset_ms": 100,
    })
    assert retimed.result["retimed"] == 2

    behavior = registry.execute("motion.behavior.add", {
        "composition_id": composition_id, "layer_id": layer_id,
        "behavior": {"kind": "wiggle", "start_ms": 0, "end_ms": 1000, "params": {"amplitude": 8}},
    })
    behavior_id = behavior.result["behavior"]["id"]
    assert registry.execute("motion.behavior.set_param", {
        "composition_id": composition_id, "layer_id": layer_id, "behavior_id": behavior_id,
        "key": "frequency", "value": 3,
    }).ok
    before = evaluate_composition(owner._motion_compositions[composition_id], 250)[0].rotation
    baked = registry.execute("motion.behavior.bake", {
        "composition_id": composition_id, "layer_id": layer_id, "sample_fps": 20,
    })
    assert baked.ok and baked.result["keyframes"] > 0
    after = evaluate_composition(owner._motion_compositions[composition_id], 250)[0].rotation
    assert abs(before - after) < 1e-6
    assert owner._motion_compositions[composition_id].layers[0].behaviors == []

    effect = registry.execute("motion.effect.add", {
        "composition_id": composition_id, "layer_id": layer_id,
        "effect": {"kind": "brightness_contrast", "params": {"brightness": {"default": 0.1}}},
    })
    effect_id = effect.result["effect"]["id"]
    assert registry.execute("motion.effect.set_param", {
        "composition_id": composition_id, "layer_id": layer_id, "effect_id": effect_id,
        "key": "contrast", "value": 1.2,
    }).ok
    assert registry.execute("motion.effect.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id, "effect_id": effect_id,
        "key": "brightness", "keyframe": {"time_ms": 500, "value": 0.25},
    }).ok
    assert registry.execute("motion.effect.list", {
        "composition_id": composition_id, "layer_id": layer_id,
    }).result["count"] == 1

    mask = registry.execute("motion.mask.add", {
        "composition_id": composition_id, "layer_id": layer_id,
        "mask": {"kind": "ellipse", "params": {"width": {"default": 100}, "height": {"default": 100}}},
    })
    mask_id = mask.result["mask"]["id"]
    assert registry.execute("motion.mask.set_param", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "key": "x", "value": 12,
    }).ok
    path = {"closed": True, "points": [
        {"position": [0, 0]}, {"position": [100, 0]},
        {"position": [100, 100]}, {"position": [0, 100]},
    ]}
    assert registry.execute("motion.mask.path.set", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "path": path,
    }).ok
    assert registry.execute("motion.mask.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "key": "feather", "keyframe": {"time_ms": 500, "value": 8},
    }).ok
    tracking = registry.execute("motion.mask.tracking.set", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
        "tracking": {"mode": "planar", "origin": [50, 50], "samples": [
            {"time_ms": 0, "translate": [0, 0]},
            {"time_ms": 1000, "translate": [25, 10], "scale": [1.1, 1.1], "rotation": 5},
        ]},
    })
    assert tracking.ok and tracking.result["sample_count"] == 2
    assert registry.execute("motion.mask.tracking.clear", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
    }).ok
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.mask.keyframe.set", "motion.mask.path.set",
        "motion.mask.tracking.set", "motion.mask.tracking.generate",
        "motion.mask.tracking.clear",
    } <= specs
    assert registry.execute("motion.mask.delete", {
        "composition_id": composition_id, "layer_id": layer_id, "mask_id": mask_id,
    }, confirm_destructive=True).ok


def test_vector_shape_actions_update_shared_source_and_animated_params() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Vector", "duration_ms": 2000})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Logo", "layer_type": "shape", "out_ms": 2000,
                  "source": {"kind": "shape", "params": {"width": 400, "height": 300}}},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    assert registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Cutout", "layer_type": "shape", "out_ms": 2000,
                  "source": {"kind": "shape", "params": {
                      "width": 120, "height": 120, "shape": "ellipse",
                  }}},
    }).ok
    operand_id = owner._motion_compositions[composition_id].layers[-1].id
    path = {"closed": True, "points": [
        {"position": [20, 20]}, {"position": [380, 20]},
        {"position": [380, 280]}, {"position": [20, 280]},
    ]}
    assert registry.execute("motion.vector.path.set", {
        "composition_id": composition_id, "layer_id": layer_id, "path": path,
    }).ok
    assert registry.execute("motion.vector.boolean.layers.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "operation": "subtract", "operand_layer_ids": [operand_id],
        "hide_operands": True,
    }).ok
    assert registry.execute("motion.vector.trim.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "start": 0.1, "end": 0.8, "offset": 0.05,
    }).ok
    assert registry.execute("motion.vector.repeater.set", {
        "composition_id": composition_id, "layer_id": layer_id, "count": 4,
        "offset": [18, 0], "rotation": 5, "scale": [.95, .95],
        "opacity_start": 1, "opacity_end": .4,
    }).ok
    assert registry.execute("motion.vector.param.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "parameter_name": "trim", "keyframe": {
            "time_ms": 1000, "value": {"start": 0.2, "end": 1.0, "offset": 0.0},
        },
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["shape"] == "path"
    assert layer.source.params["repeater"]["count"] == 4
    assert layer.source.params["trim"]["value_type"] == "scalar"
    assert layer.source.params["trim"]["keyframes"][0]["time_ms"] == 1000
    assert layer.source.params["boolean"]["operand_layer_ids"] == [operand_id]
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.vector.path.set", "motion.vector.primitive.set",
        "motion.vector.boolean.set", "motion.vector.boolean.layers.set", "motion.vector.trim.set",
        "motion.vector.repeater.set", "motion.vector.param.keyframe.set",
    } <= specs


def test_typography_actions_update_style_animation_path_and_keyframes() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {"name": "Type", "duration_ms": 2400})
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.layer.add", {
        "composition_id": composition_id,
        "layer": {"name": "Title", "layer_type": "text", "out_ms": 2400,
                  "source": {"kind": "typography", "params": {"text": "Tiger"}}},
    })
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    assert registry.execute("motion.typography.style.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "changes": {"font_family": "Segoe UI", "font_size": 84, "fill": "#f7f7f7"},
    }).ok
    assert registry.execute("motion.typography.animation.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "animation": {"in": "typewriter-in", "hold": "hold-wave", "out": "fade-out",
                      "unit": "word", "stagger_ms": 80},
    }).ok
    text_path = {"closed": False, "points": [
        {"position": [0, 100]}, {"position": [500, 100]},
    ]}
    assert registry.execute("motion.typography.text_path.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "path": text_path, "offset": .4,
    }).ok
    assert registry.execute("motion.typography.text_path.offset.set", {
        "composition_id": composition_id, "layer_id": layer_id, "offset": .6,
    }).ok
    assert registry.execute("motion.typography.param.keyframe.set", {
        "composition_id": composition_id, "layer_id": layer_id,
        "parameter_name": "text_path_offset", "keyframe": {"time_ms": 900, "value": .7},
    }).ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["font_size"] == 84
    assert layer.source.params["text_animation"]["unit"] == "word"
    assert layer.source.params["text_path"]["points"][1]["position"] == [500, 100]
    assert layer.source.params["text_path_offset"]["default"] == .6
    assert layer.source.params["text_path_offset"]["keyframes"][0]["value"] == .7
    assert registry.execute("motion.typography.text_path.clear", {
        "composition_id": composition_id, "layer_id": layer_id,
    }).ok
    assert owner._motion_compositions[composition_id].layers[0].source.params["text_path"] is None
    specs = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.typography.style.set", "motion.typography.animation.set",
        "motion.typography.text_path.set", "motion.typography.text_path.clear",
        "motion.typography.text_path.offset.set", "motion.typography.param.keyframe.set",
        "motion.typography.preflight",
    } <= specs


def test_motion_ai_plan_and_apply_actions_share_the_reviewed_proposal_contract() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "AI Motion", "width": 1280, "height": 720, "duration_ms": 3000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    planned = registry.execute("motion.ai.plan", {
        "composition_id": composition_id,
        "prompt": 'fade in "AI TITLE"',
        "references": [{"kind": "image", "name": "reference.png", "uri": "C:/reference.png"}],
    })
    assert planned.ok
    proposal = planned.result
    assert proposal["schema"] == "tigercapture.motion.ai.proposal.v1"
    assert len(proposal["layers"]) == 2
    assert owner._motion_compositions[composition_id].layers == []

    applied = registry.execute("motion.ai.apply", {
        "composition_id": composition_id, "proposal": proposal,
    })
    assert applied.ok
    assert applied.result["added_layers"] == 2
    assert len(owner._motion_compositions[composition_id].layers) == 2
    specs = {row["id"] for row in registry.list_actions()}
    assert {"motion.ai.plan", "motion.ai.apply"} <= specs
