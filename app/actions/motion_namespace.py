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
