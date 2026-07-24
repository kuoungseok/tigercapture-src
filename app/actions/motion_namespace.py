"""Registered Motion Designer composition and layer actions."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_motion_actions(registry: Any) -> None:
    cid = {"composition_id": {"type": "string"}}
    lid = {**cid, "layer_id": {"type": "string"}}
    registry.register_adapter_action(
        "motion.ui.open", "Open the Motion Designer window.", "motion", "motion_ui_open",
        params_schema=schema_object(cid), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.composition.list", "List Motion Designer compositions.", "motion",
        "motion_composition_list", params_schema=schema_object({}), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.composition.create", "Create a Motion Designer composition.", "motion",
        "motion_composition_create", params_schema=schema_object({
            "name": {"type": "string"}, "width": {"type": "integer", "minimum": 1},
            "height": {"type": "integer", "minimum": 1}, "fps": {"type": "number", "minimum": 1},
            "duration_ms": {"type": "integer", "minimum": 1},
        }), undo_label="Create Motion Composition", dry_summary="motion composition would be created",
    )
    for action_id, title, method, destructive in (
        ("motion.composition.update", "Update a Motion Designer composition.", "motion_composition_update", False),
        ("motion.composition.duplicate", "Duplicate a Motion Designer composition.", "motion_composition_duplicate", False),
        ("motion.composition.delete", "Delete a Motion Designer composition.", "motion_composition_delete", True),
    ):
        props = dict(cid)
        if action_id.endswith("update"):
            props["changes"] = {"type": "object"}
        registry.register_adapter_action(action_id, title, "motion", method,
            params_schema=schema_object(props, required=tuple(props)), required=tuple(props),
            destructive=destructive, undo_label=title.rstrip("."), dry_summary=f"{title.rstrip('.')} would run")
    registry.register_adapter_action(
        "motion.composition.validate", "Validate a Motion Designer composition.", "motion",
        "motion_composition_validate", params_schema=schema_object(cid, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.layer.list", "List layers in a Motion Designer composition.", "motion", "motion_layer_list",
        params_schema=schema_object(cid, required=("composition_id",)), required=("composition_id",),
        mutating=False, changed=False,
    )
    layer_ops = (
        ("motion.layer.add", "motion_layer_add", {**cid, "layer": {"type": "object"}, "index": {"type": "integer"}}, ("composition_id", "layer")),
        ("motion.layer.update", "motion_layer_update", {**lid, "changes": {"type": "object"}}, ("composition_id", "layer_id", "changes")),
        ("motion.layer.delete", "motion_layer_delete", lid, ("composition_id", "layer_id")),
        ("motion.layer.reorder", "motion_layer_reorder", {**lid, "index": {"type": "integer"}}, ("composition_id", "layer_id", "index")),
        ("motion.layer.parent", "motion_layer_parent", {**lid, "parent_id": {"type": "string"}}, ("composition_id", "layer_id")),
    )
    for action_id, method, props, required in layer_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            destructive=action_id.endswith("delete"), undo_label=title, dry_summary=f"{title} would run")
    registry.register_adapter_action(
        "motion.cut_paper.create",
        "Create an editable cut-paper rig with a hole matte, released paper piece, "
        "trimmed fiber edge, shadow, and path-following scissors.",
        "motion",
        "motion_cut_paper_create",
        params_schema=schema_object(
            {
                **lid,
                "center_x": {"type": "number"},
                "center_y": {"type": "number"},
                "radius_x": {"type": "number", "exclusiveMinimum": 0},
                "radius_y": {"type": "number", "exclusiveMinimum": 0},
                "start_ms": {"type": "integer", "minimum": 0},
                "cut_duration_ms": {"type": "integer", "minimum": 120},
                "release_duration_ms": {"type": "integer", "minimum": 120},
                "seed": {"type": "integer"},
            },
            required=(
                "composition_id",
                "layer_id",
                "center_x",
                "center_y",
                "radius_x",
                "radius_y",
                "start_ms",
            ),
        ),
        required=(
            "composition_id",
            "layer_id",
            "center_x",
            "center_y",
            "radius_x",
            "radius_y",
            "start_ms",
        ),
        mutating=True,
        changed=True,
        undo_label="Create Cut Paper Rig",
        dry_summary="an editable cut-paper rig would be created",
    )
    registry.register_adapter_action(
        "motion.cutout_rig.arm_wave.create",
        "Connect torso, upper-arm, forearm, and hand layers at editable joints "
        "and create a waving FK animation.",
        "motion",
        "motion_cutout_arm_wave_create",
        params_schema=schema_object(
            {
                "composition_id": {"type": "string"},
                "torso_layer_id": {"type": "string"},
                "upper_arm_layer_id": {"type": "string"},
                "forearm_layer_id": {"type": "string"},
                "hand_layer_id": {"type": "string"},
                "shoulder": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "elbow": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "wrist": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 1},
                "side": {"type": "string", "enum": ["left", "right"]},
                "cycles": {"type": "integer", "minimum": 1, "maximum": 8},
            },
            required=(
                "composition_id",
                "torso_layer_id",
                "upper_arm_layer_id",
                "forearm_layer_id",
                "hand_layer_id",
                "shoulder",
                "elbow",
                "wrist",
                "start_ms",
                "end_ms",
            ),
        ),
        required=(
            "composition_id",
            "torso_layer_id",
            "upper_arm_layer_id",
            "forearm_layer_id",
            "hand_layer_id",
            "shoulder",
            "elbow",
            "wrist",
            "start_ms",
            "end_ms",
        ),
        mutating=True,
        changed=True,
        undo_label="Create Cutout Arm Wave",
        dry_summary="an editable cutout arm chain and wave animation would be created",
    )
    animation_ops = (
        ("motion.keyframe.set", "motion_keyframe_set", {**lid, "property_name": {"type": "string"}, "keyframe": {"type": "object"}}, ("composition_id", "layer_id", "property_name", "keyframe"), True),
        ("motion.keyframe.delete", "motion_keyframe_delete", {**lid, "property_name": {"type": "string"}, "keyframe_id": {"type": "string"}}, ("composition_id", "layer_id", "property_name", "keyframe_id"), True),
        ("motion.curve.update", "motion_curve_update", {**lid, "property_name": {"type": "string"}, "keyframe_id": {"type": "string"}, "interpolation": {"type": "string"}, "in_tangent": {"type": "array"}, "out_tangent": {"type": "array"}}, ("composition_id", "layer_id", "property_name", "keyframe_id"), True),
        ("motion.behavior.list", "motion_behavior_list", lid, ("composition_id", "layer_id"), False),
        ("motion.behavior.add", "motion_behavior_add", {**lid, "behavior": {"type": "object"}}, ("composition_id", "layer_id", "behavior"), True),
        ("motion.behavior.update", "motion_behavior_update", {**lid, "behavior_id": {"type": "string"}, "changes": {"type": "object"}}, ("composition_id", "layer_id", "behavior_id", "changes"), True),
        ("motion.behavior.delete", "motion_behavior_delete", {**lid, "behavior_id": {"type": "string"}}, ("composition_id", "layer_id", "behavior_id"), True),
    )
    for action_id, method, props, required, mutating in animation_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            mutating=mutating, changed=mutating, destructive=action_id.endswith("delete"),
            undo_label=title if mutating else "", dry_summary=f"{title} would run")
    key_props = {**lid, "property_name": {"type": "string"}, "keyframe": {"type": "object"}}
    advanced_animation_ops = (
        ("motion.keyframe.add", "motion_keyframe_add", key_props, ("composition_id", "layer_id", "property_name", "keyframe"), True),
        ("motion.keyframe.update", "motion_keyframe_update", {**lid, "property_name": {"type": "string"}, "keyframe_id": {"type": "string"}, "changes": {"type": "object"}}, ("composition_id", "layer_id", "property_name", "keyframe_id", "changes"), True),
        ("motion.keyframe.copy", "motion_keyframe_copy", {**lid, "property_name": {"type": "string"}, "keyframe_ids": {"type": "array"}}, ("composition_id", "layer_id", "property_name"), False),
        ("motion.keyframe.paste", "motion_keyframe_paste", {**lid, "property_name": {"type": "string"}, "time_ms": {"type": "integer"}}, ("composition_id", "layer_id", "property_name", "time_ms"), True),
        ("motion.keyframe.set_interpolation", "motion_keyframe_set_interpolation", {**lid, "property_name": {"type": "string"}, "keyframe_id": {"type": "string"}, "interpolation": {"type": "string"}, "in_tangent": {"type": "array"}, "out_tangent": {"type": "array"}}, ("composition_id", "layer_id", "property_name", "keyframe_id"), True),
        ("motion.curve.retime", "motion_curve_retime", {**lid, "property_name": {"type": "string"}, "scale": {"type": "number"}, "offset_ms": {"type": "integer"}, "anchor_ms": {"type": "integer"}, "keyframe_ids": {"type": "array"}}, ("composition_id", "layer_id", "property_name"), True),
        ("motion.behavior.set_param", "motion_behavior_set_param", {**lid, "behavior_id": {"type": "string"}, "key": {"type": "string"}, "value": {}}, ("composition_id", "layer_id", "behavior_id", "key"), True),
        ("motion.behavior.bake", "motion_behavior_bake", {**lid, "sample_fps": {"type": "number", "minimum": 1, "maximum": 120}}, ("composition_id", "layer_id"), True),
    )
    for action_id, method, props, required, mutating in advanced_animation_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required, mutating=mutating,
            changed=mutating, undo_label=title if mutating else "", dry_summary=f"{title} would run")
    image_parameter = {
        **lid,
        "parameter_name": {
            "type": "string",
            "enum": ["tilt_x", "tilt_y", "perspective"],
        },
    }
    image_animation_ops = (
        (
            "motion.image.param.set",
            "motion_image_param_set",
            {**image_parameter, "value": {"type": "number"}},
            ("composition_id", "layer_id", "parameter_name", "value"),
        ),
        (
            "motion.image.param.keyframe.set",
            "motion_image_param_keyframe_set",
            {**image_parameter, "keyframe": {"type": "object"}},
            ("composition_id", "layer_id", "parameter_name", "keyframe"),
        ),
        (
            "motion.image.param.keyframe.delete",
            "motion_image_param_keyframe_delete",
            {**image_parameter, "keyframe_id": {"type": "string"}},
            ("composition_id", "layer_id", "parameter_name", "keyframe_id"),
        ),
    )
    for action_id, method, props, required in image_animation_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object(props, required=required),
            required=required,
            mutating=True,
            changed=True,
            destructive=action_id.endswith("delete"),
            undo_label=title,
            dry_summary=f"{title} would run",
        )
    effect_mask_ops = (
        ("motion.effect.list", "motion_effect_list", lid, ("composition_id", "layer_id"), False),
        ("motion.effect.add", "motion_effect_add", {**lid, "effect": {"type": "object"}}, ("composition_id", "layer_id", "effect"), True),
        ("motion.effect.update", "motion_effect_update", {**lid, "effect_id": {"type": "string"}, "changes": {"type": "object"}}, ("composition_id", "layer_id", "effect_id", "changes"), True),
        ("motion.effect.delete", "motion_effect_delete", {**lid, "effect_id": {"type": "string"}}, ("composition_id", "layer_id", "effect_id"), True),
        ("motion.effect.set_param", "motion_effect_set_param", {**lid, "effect_id": {"type": "string"}, "key": {"type": "string"}, "value": {}}, ("composition_id", "layer_id", "effect_id", "key", "value"), True),
        ("motion.effect.keyframe.set", "motion_effect_keyframe_set", {**lid, "effect_id": {"type": "string"}, "key": {"type": "string"}, "keyframe": {"type": "object"}}, ("composition_id", "layer_id", "effect_id", "key", "keyframe"), True),
        ("motion.mask.list", "motion_mask_list", lid, ("composition_id", "layer_id"), False),
        ("motion.mask.add", "motion_mask_add", {**lid, "mask": {"type": "object"}}, ("composition_id", "layer_id", "mask"), True),
        ("motion.mask.update", "motion_mask_update", {**lid, "mask_id": {"type": "string"}, "changes": {"type": "object"}}, ("composition_id", "layer_id", "mask_id", "changes"), True),
        ("motion.mask.delete", "motion_mask_delete", {**lid, "mask_id": {"type": "string"}}, ("composition_id", "layer_id", "mask_id"), True),
        ("motion.mask.set_param", "motion_mask_set_param", {**lid, "mask_id": {"type": "string"}, "key": {"type": "string"}, "value": {}}, ("composition_id", "layer_id", "mask_id", "key", "value"), True),
        ("motion.mask.keyframe.set", "motion_mask_keyframe_set", {**lid, "mask_id": {"type": "string"}, "key": {"type": "string"}, "keyframe": {"type": "object"}}, ("composition_id", "layer_id", "mask_id", "key", "keyframe"), True),
        ("motion.mask.path.set", "motion_mask_path_set", {**lid, "mask_id": {"type": "string"}, "path": {"type": "object"}}, ("composition_id", "layer_id", "mask_id", "path"), True),
        ("motion.mask.tracking.set", "motion_mask_tracking_set", {**lid, "mask_id": {"type": "string"}, "tracking": {"type": "object"}}, ("composition_id", "layer_id", "mask_id", "tracking"), True),
        ("motion.mask.tracking.generate", "motion_mask_tracking_generate", {
            **lid,
            "mask_id": {"type": "string"},
            "video_path": {"type": "string"},
            "mode": {"type": "string", "enum": ["point", "planar"]},
            "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1},
            "timeline_start_ms": {"type": "integer", "minimum": 0},
            "sample_interval_ms": {"type": "integer", "minimum": 1, "maximum": 5000},
            "target_size": {"type": "array", "minItems": 2, "maxItems": 2},
            "roi": {"type": "array", "minItems": 4, "maxItems": 4},
        }, ("composition_id", "layer_id", "mask_id"), True),
        ("motion.mask.tracking.clear", "motion_mask_tracking_clear", {**lid, "mask_id": {"type": "string"}}, ("composition_id", "layer_id", "mask_id"), True),
    )
    for action_id, method, props, required, mutating in effect_mask_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            mutating=mutating, changed=mutating, destructive=action_id.endswith("delete"),
            undo_label=title if mutating else "", dry_summary=f"{title} would run",
        )
    vector_ops = (
        ("motion.vector.path.set", "motion_vector_path_set",
         {**lid, "path": {"type": "object"}}, ("composition_id", "layer_id", "path")),
        ("motion.vector.primitive.set", "motion_vector_primitive_set",
         {**lid, "kind": {"type": "string"}, "params": {"type": "object"}},
         ("composition_id", "layer_id", "kind")),
        ("motion.vector.boolean.set", "motion_vector_boolean_set",
         {**lid, "operation": {"type": "string"}, "paths": {"type": "array"}},
         ("composition_id", "layer_id", "operation", "paths")),
        ("motion.vector.boolean.layers.set", "motion_vector_boolean_layers_set",
         {**lid, "operation": {"type": "string"}, "operand_layer_ids": {"type": "array"},
          "hide_operands": {"type": "boolean"}},
         ("composition_id", "layer_id", "operation", "operand_layer_ids")),
        ("motion.vector.trim.set", "motion_vector_trim_set",
         {**lid, "start": {"type": "number"}, "end": {"type": "number"},
          "offset": {"type": "number"}},
         ("composition_id", "layer_id", "start", "end")),
        ("motion.vector.repeater.set", "motion_vector_repeater_set",
         {**lid, "count": {"type": "integer", "minimum": 1, "maximum": 512},
          "offset": {"type": "array"}, "rotation": {"type": "number"},
          "scale": {"type": "array"}, "opacity_start": {"type": "number"},
          "opacity_end": {"type": "number"}},
         ("composition_id", "layer_id", "count")),
        ("motion.vector.param.keyframe.set", "motion_vector_param_keyframe_set",
         {**lid, "parameter_name": {"type": "string"}, "keyframe": {"type": "object"}},
         ("composition_id", "layer_id", "parameter_name", "keyframe")),
    )
    for action_id, method, props, required in vector_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            mutating=True, changed=True, undo_label=title, dry_summary=f"{title} would run",
        )
    typography_ops = (
        ("motion.typography.style.set", "motion_typography_style_set",
         {**lid, "changes": {"type": "object"}},
         ("composition_id", "layer_id", "changes"), True),
        ("motion.typography.animation.set", "motion_typography_animation_set",
         {**lid, "animation": {"type": "object"}},
         ("composition_id", "layer_id", "animation"), True),
        ("motion.typography.text_path.set", "motion_typography_text_path_set",
         {**lid, "path": {"type": "object"}, "offset": {"type": "number"}},
         ("composition_id", "layer_id", "path"), True),
        ("motion.typography.text_path.clear", "motion_typography_text_path_clear",
         lid, ("composition_id", "layer_id"), True),
        ("motion.typography.text_path.offset.set", "motion_typography_text_path_offset_set",
         {**lid, "offset": {"type": "number", "minimum": 0, "maximum": 1}},
         ("composition_id", "layer_id", "offset"), True),
        ("motion.typography.param.keyframe.set", "motion_typography_param_keyframe_set",
         {**lid, "parameter_name": {"type": "string"}, "keyframe": {"type": "object"}},
         ("composition_id", "layer_id", "parameter_name", "keyframe"), True),
        ("motion.typography.preflight", "motion_typography_preflight", lid,
         ("composition_id", "layer_id"), False),
    )
    for action_id, method, props, required, mutating in typography_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            mutating=mutating, changed=mutating, undo_label=title if mutating else "",
            dry_summary=f"{title} would run",
        )
    registry.register_adapter_action(
        "motion.ai.plan", "Create a reviewable Motion Designer proposal from text and image references.",
        "motion", "motion_ai_plan",
        params_schema=schema_object({
            **cid,
            "prompt": {"type": "string"},
            "references": {"type": "array"},
            "provider": {"type": "string"},
        }, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
        dry_summary="Motion AI proposal would be created without changing the composition",
    )
    registry.register_adapter_action(
        "motion.ai.apply", "Apply a reviewed Motion Designer AI proposal as one edit.",
        "motion", "motion_ai_apply",
        params_schema=schema_object({
            **cid,
            "proposal": {"type": "object"},
        }, required=("composition_id", "proposal")),
        required=("composition_id", "proposal"), mutating=True, changed=True,
        undo_label="Apply Motion AI Proposal",
        dry_summary="Reviewed Motion AI proposal would be applied",
    )
    expression_props = {
        **lid,
        "property_name": {"type": "string", "enum": ["position", "scale", "rotation", "opacity", "anchor"]},
    }
    registry.register_adapter_action(
        "motion.expression.list", "List structured Motion Designer expressions.",
        "motion", "motion_expression_list",
        params_schema=schema_object({**cid, "layer_id": {"type": "string"}}, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.expression.set", "Set a safe structured expression on a transform property.",
        "motion", "motion_expression_set",
        params_schema=schema_object({**expression_props, "expression": {}},
                                    required=("composition_id", "layer_id", "property_name", "expression")),
        required=("composition_id", "layer_id", "property_name", "expression"),
        mutating=True, changed=True, undo_label="Set Motion Expression",
        dry_summary="A structured expression would be validated and set",
    )
    registry.register_adapter_action(
        "motion.expression.clear", "Clear one or all expressions from a layer.",
        "motion", "motion_expression_clear",
        params_schema=schema_object(expression_props, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"), mutating=True, changed=True,
        undo_label="Clear Motion Expression", dry_summary="Motion expressions would be cleared",
    )
    registry.register_adapter_action(
        "motion.expression.validate", "Validate expression operations and dependency cycles.",
        "motion", "motion_expression_validate",
        params_schema=schema_object(cid, required=("composition_id",)), required=("composition_id",),
        mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.expression.bake", "Bake expression, behavior, and audio-driven transform output to keyframes.",
        "motion", "motion_expression_bake",
        params_schema=schema_object({**lid, "sample_fps": {"type": "number", "minimum": 1, "maximum": 120}},
                                    required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"), mutating=True, changed=True,
        undo_label="Bake Motion Procedural Transform",
        dry_summary="Procedural transform output would be baked to deterministic keyframes",
    )
    registry.register_adapter_action(
        "motion.particle.add", "Add a deterministic GPU shape-particle emitter.",
        "motion", "motion_particle_add",
        params_schema=schema_object({
            **cid, "name": {"type": "string"}, "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1}, "params": {"type": "object"},
        }, required=("composition_id",)),
        required=("composition_id",), mutating=True, changed=True,
        undo_label="Add Motion Particle Emitter",
        dry_summary="A deterministic particle emitter would be added",
    )
    registry.register_adapter_action(
        "motion.particle.update", "Update emitter, simulation, appearance, and seed controls.",
        "motion", "motion_particle_update",
        params_schema=schema_object({**lid, "changes": {"type": "object"}},
                                    required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), mutating=True, changed=True,
        undo_label="Update Motion Particle Emitter",
        dry_summary="Particle controls would be validated and updated",
    )
    registry.register_adapter_action(
        "motion.particle.diagnostics", "Inspect deterministic particle count and GPU eligibility.",
        "motion", "motion_particle_diagnostics",
        params_schema=schema_object({**lid, "time_ms": {"type": "number", "minimum": 0}},
                                    required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.particle.bake", "Bake a particle layer to premultiplied-alpha PNG media.",
        "motion", "motion_particle_bake",
        params_schema=schema_object({
            **lid, "output_dir": {"type": "string"},
            "sample_fps": {"type": "number", "minimum": 1, "maximum": 120},
        }, required=("composition_id", "layer_id", "output_dir")),
        required=("composition_id", "layer_id", "output_dir"), mutating=True, changed=True,
        undo_label="Bake Motion Particle Alpha Media",
        dry_summary="Particle output would be rendered to an alpha image sequence",
    )
    registry.register_adapter_action(
        "motion.template.list", "List built-in Motion templates and published controls.",
        "motion", "motion_template_list", params_schema=schema_object({}),
        mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.template.inspect", "Inspect variants, controls, and realtime grade for a template.",
        "motion", "motion_template_inspect",
        params_schema=schema_object({"template_id": {"type": "string"}}, required=("template_id",)),
        required=("template_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.template.apply", "Apply a built-in Motion template using stable published controls.",
        "motion", "motion_template_apply",
        params_schema=schema_object({
            **cid, "template_id": {"type": "string"}, "variant": {"type": "string"},
            "controls": {"type": "object"},
        }, required=("composition_id", "template_id")),
        required=("composition_id", "template_id"), mutating=True, changed=True,
        undo_label="Apply Motion Template", dry_summary="A Motion template would be applied as one edit",
    )
    registry.register_adapter_action(
        "motion.template.preview", "Render a real animated template preview frame.",
        "motion", "motion_template_preview",
        params_schema=schema_object({
            "template_id": {"type": "string"}, "output_path": {"type": "string"},
            "variant": {"type": "string"}, "controls": {"type": "object"},
            "time_ms": {"type": "number", "minimum": 0},
        }, required=("template_id", "output_path")),
        required=("template_id", "output_path"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.template.cost", "Estimate template rendering cost and pre-render requirement.",
        "motion", "motion_template_cost",
        params_schema=schema_object({
            "template_id": {"type": "string"}, "variant": {"type": "string"},
            "controls": {"type": "object"},
        }, required=("template_id",)),
        required=("template_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.broadcast.preflight", "Validate Motion cost, cache, and Program Output readiness.",
        "motion", "motion_broadcast_preflight",
        params_schema=schema_object({
            **cid, "cache_manifest": {"type": "object"},
        }, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.broadcast.live_control.set", "Set stable published controls for a live Motion template.",
        "motion", "motion_broadcast_live_control_set",
        params_schema=schema_object({
            **cid, "changes": {"type": "object"},
        }, required=("composition_id", "changes")),
        required=("composition_id", "changes"), mutating=True, changed=True,
        undo_label="Set Motion Broadcast Live Controls",
        dry_summary="Published Motion template controls would be updated and stale caches invalidated",
    )
    registry.register_adapter_action(
        "motion.broadcast.stinger.plan", "Plan an alpha-preserving broadcast cache for a Motion stinger.",
        "motion", "motion_broadcast_stinger_plan",
        params_schema=schema_object({
            **cid, "output_dir": {"type": "string"},
            "fps": {"type": "number", "minimum": 1, "maximum": 120},
        }, required=("composition_id", "output_dir")),
        required=("composition_id", "output_dir"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.broadcast.stinger.render", "Render and register a premultiplied-alpha stinger cache.",
        "motion", "motion_broadcast_stinger_render",
        params_schema=schema_object({
            **cid, "output_dir": {"type": "string"},
            "fps": {"type": "number", "minimum": 1, "maximum": 120},
        }, required=("composition_id", "output_dir")),
        required=("composition_id", "output_dir"), mutating=True, changed=True,
        undo_label="Render Motion Broadcast Alpha Cache",
        dry_summary="A revision-bound premultiplied-alpha PNG cache would be rendered",
    )
    registry.register_adapter_action(
        "motion.color.get", "Read Motion color, transfer, tone-map, and alpha settings.",
        "motion", "motion_color_get",
        params_schema=schema_object(cid, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.color.set", "Set validated Motion color, transfer, tone-map, and alpha settings.",
        "motion", "motion_color_set",
        params_schema=schema_object({**cid, "settings": {"type": "object"}},
                                    required=("composition_id", "settings")),
        required=("composition_id", "settings"), mutating=True, changed=True,
        undo_label="Set Motion Color Management",
        dry_summary="Motion color metadata would be updated and stale caches invalidated",
    )
    registry.register_adapter_action(
        "motion.export.profile.list", "List standard Motion delivery profiles and installed encoders.",
        "motion", "motion_export_profile_list", params_schema=schema_object({}),
        mutating=False, changed=False,
    )
    export_profile_params = {
        **cid, "profile_id": {"type": "string"}, "output_path": {"type": "string"},
        "fps": {"type": "number", "minimum": 1, "maximum": 120},
    }
    registry.register_adapter_action(
        "motion.export.profile.preflight", "Validate a Motion delivery profile before rendering.",
        "motion", "motion_export_profile_preflight",
        params_schema=schema_object(export_profile_params, required=("composition_id", "profile_id")),
        required=("composition_id", "profile_id"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.export.profile.render", "Render Motion with a validated standard delivery profile.",
        "motion", "motion_export_profile_render",
        params_schema=schema_object({
            **export_profile_params, "time_ms": {"type": "number", "minimum": 0},
            "resume": {"type": "boolean"},
        }, required=("composition_id", "profile_id", "output_path")),
        required=("composition_id", "profile_id", "output_path"),
        mutating=False, changed=False,
    )
    relink_params = {
        **cid, "old_root": {"type": "string"}, "new_root": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.source.relink.plan", "Plan deterministic Motion source relinking after a project move.",
        "motion", "motion_source_relink_plan",
        params_schema=schema_object(relink_params, required=("composition_id", "old_root", "new_root")),
        required=("composition_id", "old_root", "new_root"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.source.relink.apply", "Apply a non-ambiguous Motion source relink plan.",
        "motion", "motion_source_relink_apply",
        params_schema=schema_object({**relink_params, "allow_partial": {"type": "boolean"}},
                                    required=("composition_id", "old_root", "new_root")),
        required=("composition_id", "old_root", "new_root"), mutating=True, changed=True,
        undo_label="Relink Motion Sources",
        dry_summary="Motion source paths would be relinked with ambiguity protection",
    )
    recovery_params = {
        **cid, "recovery_root": {"type": "string"}, "project_path": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.recovery.write", "Write an atomic Motion recovery record.",
        "motion", "motion_recovery_write",
        params_schema=schema_object(recovery_params, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.recovery.list", "List valid and damaged Motion recovery records.",
        "motion", "motion_recovery_list",
        params_schema=schema_object({
            "recovery_root": {"type": "string"}, "project_path": {"type": "string"},
        }), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.recovery.apply", "Apply a validated Motion recovery record to its composition.",
        "motion", "motion_recovery_apply",
        params_schema=schema_object({
            **cid, "path": {"type": "string"}, "allow_stale": {"type": "boolean"},
        }, required=("composition_id", "path")),
        required=("composition_id", "path"), mutating=True, changed=True,
        undo_label="Recover Motion Composition",
        dry_summary="A checksum-validated Motion recovery record would replace the current composition",
    )
    registry.register_adapter_action(
        "motion.interchange.list", "List limited Motion interchange formats and scopes.",
        "motion", "motion_interchange_list", params_schema=schema_object({}),
        mutating=False, changed=False,
    )
    interchange_params = {
        **cid, "format_id": {"type": "string"},
        "time_ms": {"type": "number", "minimum": 0},
    }
    registry.register_adapter_action(
        "motion.interchange.preflight", "Report unsupported and bake-required Motion interchange features.",
        "motion", "motion_interchange_preflight",
        params_schema=schema_object(interchange_params, required=("composition_id", "format_id")),
        required=("composition_id", "format_id"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.interchange.export", "Export a preflighted limited Motion interchange document.",
        "motion", "motion_interchange_export",
        params_schema=schema_object({**interchange_params, "output_path": {"type": "string"}},
                                    required=("composition_id", "format_id", "output_path")),
        required=("composition_id", "format_id", "output_path"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.release.evidence.validate", "Validate the complete Motion product-release evidence matrix.",
        "motion", "motion_release_evidence_validate",
        params_schema=schema_object({"evidence": {"type": "object"}}),
        mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.release.preflight", "Evaluate Motion render readiness separately from product release evidence.",
        "motion", "motion_release_preflight",
        params_schema=schema_object({
            **cid, "profile_id": {"type": "string"}, "output_path": {"type": "string"},
            "fps": {"type": "number", "minimum": 1, "maximum": 120},
            "gpu_diagnostics": {"type": "object"}, "evidence": {"type": "object"},
        }, required=("composition_id",)),
        required=("composition_id",), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.ar_pbr.add", "Add a GPU-rendered AR/PBR asset to a Motion composition.",
        "motion", "motion_ar_pbr_add",
        params_schema=schema_object({
            **cid, "asset_path": {"type": "string"}, "name": {"type": "string"},
            "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1}, "params": {"type": "object"},
        }, required=("composition_id", "asset_path")),
        required=("composition_id", "asset_path"), undo_label="Add Motion AR/PBR Object",
        dry_summary="An AR/PBR layer would be created with the existing OpenGL renderer",
    )
    registry.register_adapter_action(
        "motion.ar_pbr.set_material", "Set or keyframe AR/PBR surface and clearcoat controls.",
        "motion", "motion_ar_pbr_set_material",
        params_schema=schema_object({
            **lid, "changes": {"type": "object"}, "time_ms": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), undo_label="Set Motion AR/PBR Material",
        dry_summary="AR/PBR material controls would be updated",
    )
    registry.register_adapter_action(
        "motion.camera.add", "Add a shared AR/PBR camera layer.", "motion", "motion_camera_add",
        params_schema=schema_object({**cid, "name": {"type": "string"}, "params": {"type": "object"}},
                                    required=("composition_id",)),
        required=("composition_id",), undo_label="Add Motion Camera",
        dry_summary="A shared camera layer would be added",
    )
    registry.register_adapter_action(
        "motion.camera.update", "Set or keyframe Motion camera position, target, FOV, and focus.",
        "motion", "motion_camera_update",
        params_schema=schema_object({
            **lid, "changes": {"type": "object"}, "time_ms": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), undo_label="Update Motion Camera",
        dry_summary="Camera controls would be updated",
    )
    registry.register_adapter_action(
        "motion.light.add", "Add a shared AR/PBR key light layer.", "motion", "motion_light_add",
        params_schema=schema_object({**cid, "name": {"type": "string"}, "params": {"type": "object"}},
                                    required=("composition_id",)),
        required=("composition_id",), undo_label="Add Motion Light",
        dry_summary="A shared key light layer would be added",
    )
    registry.register_adapter_action(
        "motion.light.update", "Set or keyframe Motion key-light direction, color, and intensity.",
        "motion", "motion_light_update",
        params_schema=schema_object({
            **lid, "changes": {"type": "object"}, "time_ms": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), undo_label="Update Motion Light",
        dry_summary="Key-light controls would be updated",
    )
    registry.register_adapter_action(
        "motion.depth_group.set", "Assign AR/PBR layers to a depth-occlusion group.",
        "motion", "motion_depth_group_set",
        params_schema=schema_object({
            **cid, "group_id": {"type": "string"}, "member_layer_ids": {"type": "array"},
            "depth_source_id": {"type": "string"}, "depth_frame_path": {"type": "string"},
            "occlusion": {"type": "boolean"},
        }, required=("composition_id", "member_layer_ids")),
        required=("composition_id", "member_layer_ids"), undo_label="Set Motion Depth Group",
        dry_summary="AR/PBR depth-group membership would be updated",
    )
    registry.register_adapter_action(
        "motion.ar_pbr.diagnostics", "Read Motion AR/PBR OpenGL renderer diagnostics.",
        "motion", "motion_ar_pbr_diagnostics",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        mutating=False, changed=False,
    )
    actor_add_props = {
        **cid, "asset_path": {"type": "string"}, "name": {"type": "string"},
        "start_ms": {"type": "integer", "minimum": 0},
        "end_ms": {"type": "integer", "minimum": 1}, "params": {"type": "object"},
    }
    registry.register_adapter_action(
        "motion.live2d.add", "Add a Cubism Live2D actor to a Motion composition.",
        "motion", "motion_live2d_add",
        params_schema=schema_object(actor_add_props, required=("composition_id", "asset_path")),
        required=("composition_id", "asset_path"), undo_label="Add Motion Live2D Actor",
        dry_summary="A Live2D actor layer would be created with the existing Cubism renderer",
    )
    registry.register_adapter_action(
        "motion.spine.add", "Add a Spine actor to a Motion composition.",
        "motion", "motion_spine_add",
        params_schema=schema_object(actor_add_props, required=("composition_id", "asset_path")),
        required=("composition_id", "asset_path"), undo_label="Add Motion Spine Actor",
        dry_summary="A Spine actor layer would be created with the existing actor renderer",
    )
    registry.register_adapter_action(
        "motion.actor.update", "Update Live2D or Spine playback and placement controls.",
        "motion", "motion_actor_update",
        params_schema=schema_object({**lid, "changes": {"type": "object"}},
                                    required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), undo_label="Update Motion Actor",
        dry_summary="Motion actor controls would be updated",
    )
    registry.register_adapter_action(
        "motion.actor.lipsync.set", "Attach structured Voice Lab timing cues to a Motion actor.",
        "motion", "motion_actor_lipsync_set",
        params_schema=schema_object({
            **lid, "cues": {"type": "array"}, "source_id": {"type": "string"},
        }, required=("composition_id", "layer_id", "cues")),
        required=("composition_id", "layer_id", "cues"), undo_label="Set Motion Actor Lip Sync",
        dry_summary="Structured lip-sync timing would be attached to the actor",
    )
    registry.register_adapter_action(
        "motion.actor.diagnostics", "Read Motion Live2D/Spine renderer diagnostics.",
        "motion", "motion_actor_diagnostics",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.mmd.add", "Add a PMX/PMD model and optional VMD motion to a Motion composition.",
        "motion", "motion_mmd_add",
        params_schema=schema_object({
            **cid, "model_path": {"type": "string"}, "motion_path": {"type": "string"},
            "name": {"type": "string"}, "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1}, "params": {"type": "object"},
        }, required=("composition_id", "model_path")),
        required=("composition_id", "model_path"), undo_label="Add Motion MMD Actor",
        dry_summary="An MMD actor layer would be created with the existing OpenGL toon renderer",
    )
    registry.register_adapter_action(
        "motion.mmd.update", "Update MMD view, toon light, material, IK, physics, and playback controls.",
        "motion", "motion_mmd_update",
        params_schema=schema_object({**lid, "changes": {"type": "object"}},
                                    required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), undo_label="Update Motion MMD Actor",
        dry_summary="MMD source controls would be updated",
    )
    registry.register_adapter_action(
        "motion.mmd.motion.set", "Assign a VMD motion to an existing Motion MMD actor.",
        "motion", "motion_mmd_motion_set",
        params_schema=schema_object({**lid, "motion_path": {"type": "string"}},
                                    required=("composition_id", "layer_id", "motion_path")),
        required=("composition_id", "layer_id", "motion_path"), undo_label="Set Motion MMD Motion",
        dry_summary="The MMD actor VMD motion would be replaced",
    )
    registry.register_adapter_action(
        "motion.mmd.diagnostics", "Read Motion MMD OpenGL, GPU skinning, IK, physics, and cache diagnostics.",
        "motion", "motion_mmd_diagnostics",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.vrm.add", "Add a VRM avatar to a Motion composition using the internal MToon GPU renderer.",
        "motion", "motion_vrm_add",
        params_schema=schema_object({
            **cid, "avatar_path": {"type": "string"}, "name": {"type": "string"},
            "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1}, "params": {"type": "object"},
        }, required=("composition_id", "avatar_path")),
        required=("composition_id", "avatar_path"), undo_label="Add Motion VRM Avatar",
        dry_summary="A VRM avatar layer would be created with the internal MToon GPU renderer",
    )
    registry.register_adapter_action(
        "motion.vrm.update", "Update VRM pose, source-matched framing, MToon lighting, and playback controls.",
        "motion", "motion_vrm_update",
        params_schema=schema_object({**lid, "changes": {"type": "object"}},
                                    required=("composition_id", "layer_id", "changes")),
        required=("composition_id", "layer_id", "changes"), undo_label="Update Motion VRM Avatar",
        dry_summary="VRM source controls would be updated",
    )
    registry.register_adapter_action(
        "motion.vrm.pose.set", "Set explicit head, shoulder, mouth, and blink pose values on a Motion VRM avatar.",
        "motion", "motion_vrm_pose_set",
        params_schema=schema_object({**lid, "pose": {"type": "object"}},
                                    required=("composition_id", "layer_id", "pose")),
        required=("composition_id", "layer_id", "pose"), undo_label="Set Motion VRM Pose",
        dry_summary="The VRM avatar pose would be updated",
    )
    registry.register_adapter_action(
        "motion.vrm.diagnostics", "Read Motion VRM MToon GPU, framing, alpha, and frame-cache diagnostics.",
        "motion", "motion_vrm_diagnostics",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.audio.analyze", "Analyze an audio or video source into cached Motion envelopes and beats.",
        "motion", "motion_audio_analyze",
        params_schema=schema_object({
            **cid, "source_path": {"type": "string"},
            "timeline_start_ms": {"type": "integer", "minimum": 0},
            "trim_start_ms": {"type": "integer", "minimum": 0},
            "duration_ms": {"type": "integer", "minimum": 1},
            "source_revision": {"type": "string"},
            "hop_ms": {"type": "integer", "minimum": 5, "maximum": 250},
            "force": {"type": "boolean"},
        }, required=("composition_id", "source_path")),
        required=("composition_id", "source_path"), mutating=True, changed=True,
        undo_label="Analyze Motion Audio", async_kind="motion_audio_analysis",
        dry_summary="Audio envelopes and beat cache would be generated",
    )
    audio_binding = {
        **lid, "analysis_id": {"type": "string"}, "binding": {"type": "object"},
    }
    registry.register_adapter_action(
        "motion.audio_reactive.bind", "Bind a cached audio channel to a Motion transform property.",
        "motion", "motion_audio_reactive_bind",
        params_schema=schema_object(audio_binding, required=("composition_id", "layer_id", "analysis_id", "binding")),
        required=("composition_id", "layer_id", "analysis_id", "binding"),
        undo_label="Bind Audio Reactive", dry_summary="Audio reactive binding would be added",
    )
    registry.register_adapter_action(
        "motion.audio_reactive.update", "Update and recompile an audio-reactive Motion binding.",
        "motion", "motion_audio_reactive_update",
        params_schema=schema_object({
            **lid, "binding_id": {"type": "string"}, "changes": {"type": "object"},
        }, required=("composition_id", "layer_id", "binding_id", "changes")),
        required=("composition_id", "layer_id", "binding_id", "changes"),
        undo_label="Update Audio Reactive", dry_summary="Audio reactive binding would be updated",
    )
    registry.register_adapter_action(
        "motion.audio_reactive.bake", "Bake audio-reactive results into ordinary transform keyframes.",
        "motion", "motion_audio_reactive_bake",
        params_schema=schema_object({
            **lid, "sample_fps": {"type": "number", "minimum": 1, "maximum": 120},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"), undo_label="Bake Audio Reactive",
        dry_summary="Audio reactive transforms would be baked to keyframes",
    )
    registry.register_adapter_action(
        "motion.composer.import_timing", "Import exact Composer BPM, section, and note timing into Motion.",
        "motion", "motion_composer_import_timing",
        params_schema=schema_object({
            **cid, "music_composition_id": {"type": "string"}, "music": {"type": "object"},
            "timeline_start_ms": {"type": "integer", "minimum": 0},
        }, required=("composition_id",)), required=("composition_id",),
        undo_label="Import Composer Timing", dry_summary="Structured Composer timing would be imported",
    )
    registry.register_adapter_action(
        "motion.voice.import_timing", "Import Voice Lab sentence, word, and phoneme timing into Motion.",
        "motion", "motion_voice_import_timing",
        params_schema=schema_object({
            **cid, "rows": {"type": "array"},
            "timeline_start_ms": {"type": "integer", "minimum": 0},
            "text_layer_id": {"type": "string"}, "actor_layer_id": {"type": "string"},
        }, required=("composition_id", "rows")), required=("composition_id", "rows"),
        undo_label="Import Voice Timing", dry_summary="Voice Lab timing would be imported",
    )
    bridge_ops = (
        ("motion.import.typography", "motion_import_typography", {**cid, "clip": {"type": "object"}}, ("composition_id", "clip"), True),
        ("motion.import.ppt_element", "motion_import_ppt_element", {**cid, "element": {"type": "object"}, "duration_ms": {"type": "integer", "minimum": 1}}, ("composition_id", "element"), True),
        ("motion.export.ppt_element", "motion_export_ppt_element", lid, ("composition_id", "layer_id"), False),
    )
    for action_id, method, props, required, mutating in bridge_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            mutating=mutating, changed=mutating, undo_label=title if mutating else "",
            dry_summary=f"{title} would run",
        )
    clip_ops = (
        ("motion.clip.create_from_timeline", "motion_clip_create_from_timeline", {"name": {"type": "string"}, "start_ms": {"type": "integer"}, "duration_ms": {"type": "integer", "minimum": 1}}, (), True),
        ("motion.clip.place", "motion_clip_place", {**cid, "start_ms": {"type": "integer"}, "duration_ms": {"type": "integer"}, "loop": {"type": "boolean"}}, ("composition_id",), True),
        ("motion.clip.update", "motion_clip_update", {"clip_id": {"type": "string"}, "changes": {"type": "object"}}, ("clip_id", "changes"), True),
        ("motion.clip.remove", "motion_clip_remove", {"clip_id": {"type": "string"}}, ("clip_id",), True),
        ("motion.clip.split", "motion_clip_split", {"clip_id": {"type": "string"}, "timeline_ms": {"type": "integer"}}, ("clip_id", "timeline_ms"), True),
        ("motion.clip.duplicate", "motion_clip_duplicate", {"clip_id": {"type": "string"}, "start_ms": {"type": "integer"}}, ("clip_id",), True),
        ("motion.clip.cache", "motion_clip_cache", {"clip_id": {"type": "string"}, "sample_count": {"type": "integer", "minimum": 1, "maximum": 240}}, ("clip_id",), False),
        ("motion.clip.capture", "motion_clip_capture", {"clip_id": {"type": "string"}, "timeline_ms": {"type": "integer"}, "output_path": {"type": "string"}}, ("clip_id", "timeline_ms"), False),
    )
    for action_id, method, props, required, mutating in clip_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required, mutating=mutating,
            changed=mutating, destructive=action_id.endswith("remove"), undo_label=title if mutating else "",
            async_kind="motion_cache" if action_id.endswith("cache") else "", dry_summary=f"{title} would run")
