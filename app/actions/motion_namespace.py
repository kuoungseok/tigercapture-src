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
        "motion.ui.language.get",
        "Get the Motion Designer interface language.",
        "motion",
        "motion_ui_language_get",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ui.language.set",
        "Set and persist the Motion Designer interface language.",
        "motion",
        "motion_ui_language_set",
        params_schema=schema_object(
            {
                "language": {
                    "type": "string",
                    "enum": ["ko", "en", "ja", "zh", "fr", "de"],
                },
            },
            required=("language",),
        ),
        required=("language",),
        mutating=True,
        changed=False,
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
        "motion.precomp.create",
        "Pre-compose selected Motion Designer layers.",
        "motion",
        "motion_precomp_create",
        params_schema=schema_object({
            **cid,
            "layer_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "name": {"type": "string"},
        }, required=("composition_id", "layer_ids")),
        required=("composition_id", "layer_ids"),
        undo_label="Pre-compose Layers",
        dry_summary="Selected layers would become a nested composition",
    )
    registry.register_adapter_action(
        "motion.precomp.inspect",
        "Inspect a nested Motion Designer composition.",
        "motion",
        "motion_precomp_inspect",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.precomp.override.set",
        "Set a per-instance nested layer override.",
        "motion",
        "motion_precomp_override_set",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "child_layer_id": {"type": "string"},
            "changes": {"type": "object"},
        }, required=(
            "composition_id", "layer_id", "child_layer_id", "changes",
        )),
        required=(
            "composition_id", "layer_id", "child_layer_id", "changes",
        ),
        undo_label="Set Pre-compose Override",
        dry_summary="Nested layer overrides would be updated",
    )
    registry.register_adapter_action(
        "motion.precomp.refresh",
        "Refresh a pre-compose instance from its editable child composition.",
        "motion",
        "motion_precomp_refresh",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "nested_composition_id": {"type": "string"},
        }, required=(
            "composition_id", "layer_id", "nested_composition_id",
        )),
        required=(
            "composition_id", "layer_id", "nested_composition_id",
        ),
        undo_label="Refresh Pre-compose",
        dry_summary="The embedded nested composition would be refreshed",
    )
    registry.register_adapter_action(
        "motion.property.publish",
        "Publish a child composition property for instance overrides.",
        "motion",
        "motion_property_publish",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "property_name": {"type": "string"},
            "name": {"type": "string"},
        }, required=("composition_id", "layer_id", "property_name")),
        required=("composition_id", "layer_id", "property_name"),
        undo_label="Publish Motion Property",
        dry_summary="The property would be exposed to pre-compose instances",
    )
    registry.register_adapter_action(
        "motion.precomp.published_value.set",
        "Set a published property on one pre-compose instance.",
        "motion",
        "motion_precomp_published_value_set",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "publication_id": {"type": "string"},
            "value": {},
        }, required=(
            "composition_id", "layer_id", "publication_id", "value",
        )),
        required=(
            "composition_id", "layer_id", "publication_id", "value",
        ),
        undo_label="Set Published Property",
        dry_summary="The pre-compose instance value would be updated",
    )
    registry.register_adapter_action(
        "motion.controller.create",
        "Create a non-rendering Controller Null.",
        "motion",
        "motion_controller_create",
        params_schema=schema_object({
            **cid,
            "name": {"type": "string"},
            "position": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
        }, required=("composition_id",)),
        required=("composition_id",),
        undo_label="Create Motion Controller",
        dry_summary="A Controller Null would be added",
    )
    registry.register_adapter_action(
        "motion.controller.link",
        "Link a target transform property to a Controller Null.",
        "motion",
        "motion_controller_link",
        params_schema=schema_object({
            **cid,
            "target_layer_id": {"type": "string"},
            "target_property": {"type": "string"},
            "controller_layer_id": {"type": "string"},
            "controller_property": {"type": "string"},
        }, required=(
            "composition_id", "target_layer_id", "target_property",
            "controller_layer_id", "controller_property",
        )),
        required=(
            "composition_id", "target_layer_id", "target_property",
            "controller_layer_id", "controller_property",
        ),
        undo_label="Link Motion Controller",
        dry_summary="The target property would follow the Controller Null",
    )
    registry.register_adapter_action(
        "motion.time_remap.set",
        "Set keyframed source time for a Motion layer.",
        "motion",
        "motion_time_remap_set",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "keyframes": {
                "type": "array",
                "items": {"type": "object"},
                "minItems": 1,
            },
            "default": {"type": "number"},
        }, required=("composition_id", "layer_id", "keyframes")),
        required=("composition_id", "layer_id", "keyframes"),
        undo_label="Set Time Remap",
        dry_summary="Source-time keyframes would be replaced",
    )
    registry.register_adapter_action(
        "motion.time_remap.preset",
        "Apply a linear, reverse, freeze, or speed-ramp source-time preset.",
        "motion",
        "motion_time_remap_preset",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "preset": {
                "type": "string",
                "enum": ["linear", "reverse", "freeze", "speed_ramp"],
            },
        }, required=("composition_id", "layer_id", "preset")),
        required=("composition_id", "layer_id", "preset"),
        undo_label="Apply Time Remap Preset",
        dry_summary="A source-time preset would be applied",
    )
    registry.register_adapter_action(
        "motion.time_remap.clear",
        "Clear source-time remapping from a Motion layer.",
        "motion",
        "motion_time_remap_clear",
        params_schema=schema_object({
            **cid, "layer_id": {"type": "string"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Clear Time Remap",
        dry_summary="Source-time remapping would be removed",
    )
    registry.register_adapter_action(
        "motion.time_remap.inspect",
        "Inspect source-time remap speed, reverse, and freeze segments.",
        "motion",
        "motion_time_remap_inspect",
        params_schema=schema_object({
            **cid, "layer_id": {"type": "string"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.frame_blending.set",
        "Set off, Frame Mix, or Optical Flow mode for a Motion layer.",
        "motion",
        "motion_frame_blending_set",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": ["off", "frame_mix", "optical_flow"],
            },
            "source_fps": {"type": "number", "minimum": 0.0},
        }, required=("composition_id", "layer_id", "mode")),
        required=("composition_id", "layer_id", "mode"),
        undo_label="Set Frame Blending",
        dry_summary="Frame sampling mode would be updated",
    )
    registry.register_adapter_action(
        "motion.frame_blending.preflight",
        "Inspect Frame Mix and Optical Flow backend availability and fallback.",
        "motion",
        "motion_frame_blending_preflight",
        params_schema=schema_object({
            **cid, "layer_id": {"type": "string"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.graph.tangent.update",
        "Update keyframe interpolation and Bezier tangents.",
        "motion",
        "motion_graph_tangent_update",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "property_name": {"type": "string"},
            "keyframe_id": {"type": "string"},
            "mode": {
                "type": "string",
                "enum": ["auto", "continuous", "broken", "linear", "hold"],
            },
            "in_tangent": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
            "out_tangent": {
                "type": "array",
                "items": {"type": "number"},
                "minItems": 2,
                "maxItems": 2,
            },
        }, required=(
            "composition_id", "layer_id", "property_name", "keyframe_id",
        )),
        required=(
            "composition_id", "layer_id", "property_name", "keyframe_id",
        ),
        undo_label="Update Graph Tangent",
        dry_summary="Keyframe tangent interpolation would be updated",
    )
    registry.register_adapter_action(
        "motion.graph.roving.set",
        "Enable or disable automatic temporal spacing for keyframes.",
        "motion",
        "motion_graph_roving_set",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "property_name": {"type": "string"},
            "keyframe_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "enabled": {"type": "boolean"},
        }, required=(
            "composition_id", "layer_id", "property_name", "keyframe_ids",
        )),
        required=(
            "composition_id", "layer_id", "property_name", "keyframe_ids",
        ),
        undo_label="Set Roving Keyframes",
        dry_summary="Selected keyframes would be redistributed in time",
    )
    registry.register_adapter_action(
        "motion.project.save", "Save a composition as an independent .tgmotion project.",
        "motion", "motion_project_save",
        params_schema=schema_object({
            **cid, "path": {"type": "string"},
        }, required=("composition_id", "path")),
        required=("composition_id", "path"), mutating=False, changed=False,
    )
    registry.register_adapter_action(
        "motion.project.load", "Load an independent .tgmotion project into Tiger Studio.",
        "motion", "motion_project_load",
        params_schema=schema_object({
            "path": {"type": "string"},
            "replace_existing": {"type": "boolean"},
        }, required=("path",)),
        required=("path",), mutating=True, changed=True,
        undo_label="Load Motion Project",
        dry_summary="The Motion project would be validated and loaded",
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
    rid = {**cid, "rig_id": {"type": "string"}}
    bid = {**rid, "bone_id": {"type": "string"}}
    rig_ops = (
        (
            "motion.rig.list", "motion_rig_list", cid,
            ("composition_id",), False, False,
        ),
        (
            "motion.rig.inspect", "motion_rig_inspect", rid,
            ("composition_id", "rig_id"), False, False,
        ),
        (
            "motion.rig.create", "motion_rig_create",
            {
                **cid,
                "name": {"type": "string"},
                "kind": {"type": "string", "enum": ["cutout_2d"]},
                "bones": {"type": "array", "items": {"type": "object"}},
                "bindings": {"type": "array", "items": {"type": "object"}},
            },
            ("composition_id",), True, False,
        ),
        (
            "motion.rig.humanoid.create", "motion_rig_humanoid_create",
            {
                **cid,
                "name": {"type": "string"},
                "layer_slots": {"type": "object"},
            },
            ("composition_id",), True, False,
        ),
        (
            "motion.rig.delete", "motion_rig_delete", rid,
            ("composition_id", "rig_id"), True, True,
        ),
        (
            "motion.rig.bone.add", "motion_rig_bone_add",
            {**rid, "bone": {"type": "object"}},
            ("composition_id", "rig_id", "bone"), True, False,
        ),
        (
            "motion.rig.bone.update", "motion_rig_bone_update",
            {**bid, "changes": {"type": "object"}},
            ("composition_id", "rig_id", "bone_id", "changes"), True, False,
        ),
        (
            "motion.rig.bone.delete", "motion_rig_bone_delete", bid,
            ("composition_id", "rig_id", "bone_id"), True, True,
        ),
        (
            "motion.rig.bone.mirror", "motion_rig_bone_mirror",
            {
                **rid,
                "bone_ids": {"type": "array", "items": {"type": "string"}},
                "axis_x": {"type": "number"},
                "create_missing": {"type": "boolean"},
            },
            ("composition_id", "rig_id"), True, False,
        ),
        (
            "motion.rig.layer.bind", "motion_rig_layer_bind",
            {
                **bid,
                "layer_id": {"type": "string"},
                "inherit_rotation": {"type": "boolean"},
                "inherit_scale": {"type": "boolean"},
            },
            ("composition_id", "rig_id", "bone_id", "layer_id"), True, False,
        ),
        (
            "motion.rig.layer.unbind", "motion_rig_layer_unbind",
            {**rid, "layer_id": {"type": "string"}},
            ("composition_id", "rig_id", "layer_id"), True, False,
        ),
        (
            "motion.rig.ik.solve", "motion_rig_ik_solve",
            {
                **rid,
                "root_bone_id": {"type": "string"},
                "mid_bone_id": {"type": "string"},
                "end_bone_id": {"type": "string"},
                "target": {
                    "type": "array", "items": {"type": "number"},
                    "minItems": 2, "maxItems": 2,
                },
                "pole": {
                    "type": "array", "items": {"type": "number"},
                    "minItems": 2, "maxItems": 2,
                },
                "time_ms": {"type": "integer", "minimum": 0},
            },
            (
                "composition_id", "rig_id", "root_bone_id",
                "mid_bone_id", "end_bone_id", "target",
            ),
            True,
            False,
        ),
        (
            "motion.rig.constraint.set", "motion_rig_constraint_set",
            {
                **rid,
                "constraint_id": {"type": "string"},
                "root_bone_id": {"type": "string"},
                "mid_bone_id": {"type": "string"},
                "end_bone_id": {"type": "string"},
                "target": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        {"type": "object"},
                    ],
                },
                "pole": {
                    "oneOf": [
                        {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 2},
                        {"type": "object"},
                    ],
                },
                "weight": {"oneOf": [{"type": "number"}, {"type": "object"}]},
                "enabled": {"type": "boolean"},
                "lock_end": {"type": "boolean"},
            },
            (
                "composition_id", "rig_id", "root_bone_id",
                "mid_bone_id", "end_bone_id", "target",
            ),
            True,
            False,
        ),
        (
            "motion.rig.constraint.remove", "motion_rig_constraint_remove",
            {**rid, "constraint_id": {"type": "string"}},
            ("composition_id", "rig_id", "constraint_id"), True, True,
        ),
        (
            "motion.rig.constraint.enable", "motion_rig_constraint_enable",
            {
                **rid,
                "constraint_id": {"type": "string"},
                "enabled": {"type": "boolean"},
            },
            ("composition_id", "rig_id", "constraint_id", "enabled"), True, False,
        ),
        (
            "motion.rig.ik.bake", "motion_rig_ik_bake",
            {
                **rid,
                "constraint_id": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 0},
                "sample_fps": {"type": "number", "minimum": 1, "maximum": 120},
                "disable_after": {"type": "boolean"},
            },
            ("composition_id", "rig_id", "constraint_id"), True, False,
        ),
        (
            "motion.rig.pose.save", "motion_rig_pose_save",
            {
                **rid,
                "name": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
            },
            ("composition_id", "rig_id", "name"), True, False,
        ),
        (
            "motion.rig.pose.apply", "motion_rig_pose_apply",
            {
                **rid,
                "pose_id": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "mirrored": {"type": "boolean"},
            },
            ("composition_id", "rig_id", "pose_id"), True, False,
        ),
        (
            "motion.rig.motion.apply", "motion_rig_motion_apply",
            {
                **rid,
                "preset_id": {
                    "type": "string",
                    "enum": ["arm_wave", "head_nod", "walk_contact"],
                },
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 1},
                "side": {"type": "string", "enum": ["left", "right"]},
            },
            ("composition_id", "rig_id", "preset_id"), True, False,
        ),
    )
    for action_id, method, props, required, mutating, destructive in rig_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object(props, required=required),
            required=required,
            mutating=mutating,
            changed=mutating,
            destructive=destructive,
            undo_label=title if mutating else "",
            dry_summary=f"{title} would run",
        )
    puppet_ops = (
        (
            "motion.puppet.inspect", "motion_puppet_inspect",
            {**lid, "time_ms": {"type": "integer", "minimum": 0}},
            ("composition_id", "layer_id"), False, False,
        ),
        (
            "motion.puppet.mesh.create", "motion_puppet_mesh_create",
            {
                **lid,
                "columns": {"type": "integer", "minimum": 2, "maximum": 128},
                "rows": {"type": "integer", "minimum": 2, "maximum": 128},
                "adaptive": {"type": "boolean"},
                "alpha_threshold": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 255,
                },
            },
            ("composition_id", "layer_id"), True, False,
        ),
        (
            "motion.puppet.mesh.remove", "motion_puppet_mesh_remove",
            lid, ("composition_id", "layer_id"), True, True,
        ),
        (
            "motion.puppet.repair.configure", "motion_puppet_repair_configure",
            {
                **lid,
                "enabled": {"type": "boolean"},
                "max_edge_stretch": {
                    "type": "number",
                    "minimum": 1.01,
                    "maximum": 100.0,
                },
            },
            ("composition_id", "layer_id"), True, False,
        ),
        (
            "motion.puppet.pin.add", "motion_puppet_pin_add",
            {
                **lid,
                "kind": {
                    "type": "string",
                    "enum": ["position", "bend", "starch", "overlap"],
                },
                "position": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "name": {"type": "string"},
                "radius": {"type": "number", "minimum": 0.001, "maximum": 2},
                "strength": {"type": "number", "minimum": 0, "maximum": 2},
            },
            ("composition_id", "layer_id", "kind", "position"), True, False,
        ),
        (
            "motion.puppet.pin.update", "motion_puppet_pin_update",
            {
                **lid,
                "pin_id": {"type": "string"},
                "changes": {"type": "object"},
            },
            ("composition_id", "layer_id", "pin_id", "changes"), True, False,
        ),
        (
            "motion.puppet.bind.rig", "motion_puppet_pin_bind_rig",
            {
                **lid,
                "pin_id": {"type": "string"},
                "rig_id": {"type": "string"},
                "bone_id": {"type": "string"},
            },
            (
                "composition_id", "layer_id", "pin_id", "rig_id", "bone_id",
            ),
            True,
            False,
        ),
        (
            "motion.puppet.pin.delete", "motion_puppet_pin_delete",
            {**lid, "pin_id": {"type": "string"}},
            ("composition_id", "layer_id", "pin_id"), True, True,
        ),
    )
    for action_id, method, props, required, mutating, destructive in puppet_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object(props, required=required),
            required=required,
            mutating=mutating,
            changed=mutating,
            destructive=destructive,
            undo_label=title if mutating else "",
            dry_summary=f"{title} would run",
        )
    button_ops = (
        (
            "motion.button.inspect",
            "motion_button_inspect",
            lid,
            ("composition_id", "layer_id"),
            False,
            False,
        ),
        (
            "motion.button.create",
            "motion_button_create",
            {
                **lid,
                "transition_duration_ms": {"type": "integer", "minimum": 0, "maximum": 5000},
                "easing": {
                    "type": "string",
                    "enum": ["linear", "ease_out", "ease_in_out", "spring"],
                },
                "hit_padding": {"type": "number", "minimum": 0, "maximum": 500},
            },
            ("composition_id", "layer_id"),
            True,
            False,
        ),
        (
            "motion.button.update",
            "motion_button_update",
            {**lid, "changes": {"type": "object"}},
            ("composition_id", "layer_id", "changes"),
            True,
            False,
        ),
        (
            "motion.button.state.set",
            "motion_button_state_set",
            {
                **lid,
                "state": {
                    "type": "string",
                    "enum": ["normal", "hover", "pressed", "disabled", "focused"],
                },
            },
            ("composition_id", "layer_id", "state"),
            True,
            False,
        ),
        (
            "motion.button.remove",
            "motion_button_remove",
            lid,
            ("composition_id", "layer_id"),
            True,
            True,
        ),
    )
    for action_id, method, props, required, mutating, destructive in button_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object(props, required=required),
            required=required,
            mutating=mutating,
            changed=mutating,
            destructive=destructive,
            undo_label=title if mutating else "",
            dry_summary=f"{title} would run",
        )
    ui_binding_ops = (
        (
            "motion.ui_binding.list",
            "motion_ui_binding_list",
            cid,
            ("composition_id",),
            False,
            False,
        ),
        (
            "motion.ui_binding.set",
            "motion_ui_binding_set",
            {**cid, "binding": {"type": "object"}},
            ("composition_id", "binding"),
            True,
            False,
        ),
        (
            "motion.ui_binding.remove",
            "motion_ui_binding_remove",
            {**cid, "binding_id": {"type": "string"}},
            ("composition_id", "binding_id"),
            True,
            True,
        ),
        (
            "motion.ui_binding.preflight",
            "motion_ui_binding_preflight",
            cid,
            ("composition_id",),
            False,
            False,
        ),
    )
    for action_id, method, props, required, mutating, destructive in ui_binding_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object(props, required=required),
            required=required,
            mutating=mutating,
            changed=mutating,
            destructive=destructive,
            undo_label=title if mutating else "",
            dry_summary=f"{title} would run",
        )
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
    advanced_ops = (
        (
            "motion.matte.set", "motion_matte_set",
            {**lid, "matte_layer_id": {"type": "string"},
             "mode": {"type": "string", "enum": ["alpha", "luma"]},
             "inverted": {"type": "boolean"}},
            ("composition_id", "layer_id", "matte_layer_id"),
        ),
        (
            "motion.matte.clear", "motion_matte_clear", lid,
            ("composition_id", "layer_id"),
        ),
        (
            "motion.key.create", "motion_key_create",
            {**lid,
             "kind": {"type": "string", "enum": [
                 "chroma_key", "luma_key", "difference_key",
             ]},
             "params": {"type": "object"}},
            ("composition_id", "layer_id", "kind"),
        ),
        (
            "motion.key.update", "motion_key_update",
            {**lid, "effect_id": {"type": "string"},
             "params": {"type": "object"}},
            ("composition_id", "layer_id", "effect_id", "params"),
        ),
        (
            "motion.matte.correction.set", "motion_matte_correction_set",
            {**lid, "mask_id": {"type": "string"},
             "time_ms": {"type": "integer", "minimum": 0},
             "translate": {"type": "array", "minItems": 2, "maxItems": 2},
             "scale": {"type": "array", "minItems": 2, "maxItems": 2},
             "rotation": {"type": "number"}},
            ("composition_id", "layer_id", "mask_id", "time_ms"),
        ),
        (
            "motion.matte.freeze", "motion_matte_freeze",
            {**lid, "mask_id": {"type": "string"},
             "frozen": {"type": "boolean"}},
            ("composition_id", "layer_id", "mask_id"),
        ),
        (
            "motion.layer.depth.set", "motion_layer_depth_set",
            {**lid, "depth_z": {"type": "number", "minimum": -8, "maximum": 8},
             "camera_excluded": {"type": "boolean"}},
            ("composition_id", "layer_id", "depth_z"),
        ),
        (
            "motion.3d.layer.enable", "motion_3d_layer_enable",
            {
                **lid,
                "enabled": {"type": "boolean"},
                "depth_z": {"type": "number", "minimum": -8, "maximum": 8},
                "rotation_x": {"type": "number", "minimum": -180, "maximum": 180},
                "rotation_y": {"type": "number", "minimum": -180, "maximum": 180},
                "camera_excluded": {"type": "boolean"},
                "cast_shadows": {"type": "boolean"},
                "receive_shadows": {"type": "boolean"},
                "shadow_strength": {
                    "type": "number", "minimum": 0, "maximum": 1,
                },
                "shadow_softness": {
                    "type": "number", "minimum": 0, "maximum": 32,
                },
            },
            ("composition_id", "layer_id"),
        ),
        (
            "motion.blur.set", "motion_blur_set",
            {**lid, "enabled": {"type": "boolean"},
             "samples": {"type": "integer", "minimum": 2, "maximum": 32},
             "shutter": {"type": "number", "minimum": 0, "maximum": 2}},
            ("composition_id", "layer_id"),
        ),
        (
            "motion.replicator.set", "motion_replicator_set",
            {**lid, "enabled": {"type": "boolean"},
             "arrangement": {"type": "string", "enum": ["line", "grid", "radial"]},
             "count": {"type": "integer", "minimum": 1, "maximum": 256},
             "columns": {"type": "integer", "minimum": 1, "maximum": 256},
             "offset": {"type": "array"}, "rotation": {"type": "number"},
             "scale": {"type": "array"}, "opacity_start": {"type": "number"},
             "opacity_end": {"type": "number"}, "jitter": {"type": "array"},
             "seed": {"type": "integer"}},
            ("composition_id", "layer_id", "count"),
        ),
        (
            "motion.generator.create", "motion_generator_create",
            {**cid,
             "kind": {"type": "string", "enum": [
                 "solid", "gradient", "checkerboard", "grid", "noise", "rays",
             ]},
             "name": {"type": "string"},
             "width": {"type": "integer", "minimum": 0, "maximum": 16384},
             "height": {"type": "integer", "minimum": 0, "maximum": 16384},
             "duration_ms": {"type": "integer", "minimum": 0}},
            ("composition_id", "kind"),
        ),
        (
            "motion.generator.update", "motion_generator_update",
            {**lid, "changes": {"type": "object"}},
            ("composition_id", "layer_id", "changes"),
        ),
        (
            "motion.text.animator.set", "motion_text_animator_set",
            {**lid, "config": {"type": "object"}},
            ("composition_id", "layer_id", "config"),
        ),
        (
            "motion.text.animator.stack.set", "motion_text_animator_stack_set",
            {**lid, "animators": {
                "type": "array", "items": {"type": "object"}, "maxItems": 32,
            }},
            ("composition_id", "layer_id", "animators"),
        ),
        (
            "motion.text.animator.add", "motion_text_animator_add",
            {**lid, "animator": {"type": "object"}},
            ("composition_id", "layer_id", "animator"),
        ),
        (
            "motion.text.animator.update", "motion_text_animator_update",
            {**lid, "animator_id": {"type": "string"},
             "changes": {"type": "object"}},
            ("composition_id", "layer_id", "animator_id", "changes"),
        ),
        (
            "motion.text.animator.remove", "motion_text_animator_remove",
            {**lid, "animator_id": {"type": "string"}},
            ("composition_id", "layer_id", "animator_id"),
        ),
        (
            "motion.camera.2_5d.set", "motion_camera_2_5d_set",
            {**lid, "enabled": {"type": "boolean"},
             "parallax_strength": {"type": "number", "minimum": 0, "maximum": 4},
             "pixels_per_unit": {"type": "number", "minimum": 1, "maximum": 1000}},
            ("composition_id", "layer_id"),
        ),
        (
            "motion.paper_paste.create", "motion_paper_paste_create",
            {**lid, "start_ms": {"type": "integer", "minimum": 0},
             "tape_color": {"type": "string"},
             "fold_strength": {"type": "number", "minimum": 0, "maximum": 1}},
            ("composition_id", "layer_id", "start_ms"),
        ),
        (
            "motion.advanced_preset.apply", "motion_advanced_preset_apply",
            {**cid, "preset_id": {"type": "string", "enum": [
                "headline_slam", "paper_rip_reveal", "cutout_collage",
                "editorial_camera_push", "beat_synced_montage",
            ]}, "layer_ids": {"type": "array"},
             "start_ms": {"type": "integer", "minimum": 0},
             "beat_interval_ms": {"type": "integer", "minimum": 80}},
            ("composition_id", "preset_id"),
        ),
    )
    for action_id, method, props, required in advanced_ops:
        title = action_id.replace("motion.", "").replace(".", " ").title()
        registry.register_adapter_action(
            action_id, title, "motion", method,
            params_schema=schema_object(props, required=required), required=required,
            mutating=True, changed=True, undo_label=title,
            dry_summary=f"{title} would run",
        )
    registry.register_adapter_action(
        "motion.key.diagnostics",
        "Measure the current Motion keyer alpha result.",
        "motion",
        "motion_key_diagnostics",
        params_schema=schema_object(
            {
                **lid,
                "effect_id": {"type": "string"},
                "time_ms": {"type": "number", "minimum": 0},
            },
            required=("composition_id", "layer_id", "effect_id"),
        ),
        required=("composition_id", "layer_id", "effect_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.matte.propagate",
        "Propagate a Motion matte through source video frames.",
        "motion",
        "motion_mask_tracking_generate",
        params_schema=schema_object(
            {
                **lid,
                "mask_id": {"type": "string"},
                "video_path": {"type": "string"},
                "mode": {"type": "string", "enum": ["point", "planar"]},
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 1},
                "timeline_start_ms": {"type": "integer", "minimum": 0},
                "sample_interval_ms": {
                    "type": "integer", "minimum": 1, "maximum": 5000,
                },
                "target_size": {"type": "array", "minItems": 2, "maxItems": 2},
                "roi": {"type": "array", "minItems": 4, "maxItems": 4},
            },
            required=("composition_id", "layer_id", "mask_id"),
        ),
        required=("composition_id", "layer_id", "mask_id"),
        mutating=True,
        changed=True,
        undo_label="Propagate Motion Matte",
        dry_summary="The selected matte would be propagated and cached",
    )
    registry.register_adapter_action(
        "motion.matte.diagnostics",
        "Report Motion matte propagation confidence and cache state.",
        "motion",
        "motion_matte_diagnostics",
        params_schema=schema_object(
            {**lid, "mask_id": {"type": "string"}},
            required=("composition_id", "layer_id"),
        ),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.matte.assign",
        "Assign an alpha or luma layer matte to a Motion layer.",
        "motion",
        "motion_matte_set",
        params_schema=schema_object(
            {
                **lid,
                "matte_layer_id": {"type": "string"},
                "mode": {"type": "string", "enum": ["alpha", "luma"]},
                "inverted": {"type": "boolean"},
            },
            required=("composition_id", "layer_id", "matte_layer_id"),
        ),
        required=("composition_id", "layer_id", "matte_layer_id"),
        mutating=True,
        changed=True,
        undo_label="Assign Motion Matte",
        dry_summary="The selected alpha or luma matte would be assigned",
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
        ("motion.effect.keyframe.delete", "motion_effect_keyframe_delete", {**lid, "effect_id": {"type": "string"}, "key": {"type": "string"}, "time_ms": {"type": "integer", "minimum": 0}}, ("composition_id", "layer_id", "effect_id", "key", "time_ms"), True),
        ("motion.mask.list", "motion_mask_list", lid, ("composition_id", "layer_id"), False),
        ("motion.mask.add", "motion_mask_add", {**lid, "mask": {"type": "object"}}, ("composition_id", "layer_id", "mask"), True),
        ("motion.mask.update", "motion_mask_update", {**lid, "mask_id": {"type": "string"}, "changes": {"type": "object"}}, ("composition_id", "layer_id", "mask_id", "changes"), True),
        ("motion.mask.delete", "motion_mask_delete", {**lid, "mask_id": {"type": "string"}}, ("composition_id", "layer_id", "mask_id"), True),
        ("motion.mask.set_param", "motion_mask_set_param", {**lid, "mask_id": {"type": "string"}, "key": {"type": "string"}, "value": {}}, ("composition_id", "layer_id", "mask_id", "key", "value"), True),
        ("motion.mask.keyframe.set", "motion_mask_keyframe_set", {**lid, "mask_id": {"type": "string"}, "key": {"type": "string"}, "keyframe": {"type": "object"}}, ("composition_id", "layer_id", "mask_id", "key", "keyframe"), True),
        ("motion.mask.keyframe.delete", "motion_mask_keyframe_delete", {**lid, "mask_id": {"type": "string"}, "key": {"type": "string"}, "time_ms": {"type": "integer", "minimum": 0}}, ("composition_id", "layer_id", "mask_id", "key", "time_ms"), True),
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
    registry.register_adapter_action(
        "motion.adjustment.scope.get",
        "Get the target scope of a Motion adjustment layer.",
        "motion",
        "motion_adjustment_scope_get",
        params_schema=schema_object(
            lid,
            required=("composition_id", "layer_id"),
        ),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.adjustment.scope.set",
        "Set an adjustment layer to affect all or selected lower layers.",
        "motion",
        "motion_adjustment_scope_set",
        params_schema=schema_object(
            {
                **lid,
                "mode": {
                    "type": "string",
                    "enum": ["all_below", "selected_layers_below"],
                },
                "layer_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            required=("composition_id", "layer_id", "mode"),
        ),
        required=("composition_id", "layer_id", "mode"),
        undo_label="Set Adjustment Layer Scope",
        dry_summary="Adjustment layer scope would be updated",
    )
    registry.register_adapter_action(
        "motion.effect_group.scope.get",
        "Get the enabled state and descendant target scope of a Motion effect group.",
        "motion",
        "motion_effect_group_scope_get",
        params_schema=schema_object(
            lid,
            required=("composition_id", "layer_id"),
        ),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.effect_group.scope.set",
        "Enable a group effect stack for all or selected renderable descendants.",
        "motion",
        "motion_effect_group_scope_set",
        params_schema=schema_object(
            {
                **lid,
                "enabled": {"type": "boolean"},
                "mode": {
                    "type": "string",
                    "enum": ["descendants", "selected_descendants"],
                },
                "layer_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            required=("composition_id", "layer_id", "mode"),
        ),
        required=("composition_id", "layer_id", "mode"),
        undo_label="Set Effect Group Scope",
        dry_summary="Effect group scope would be updated",
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
        ("motion.shape.operator.merge_paths.set", "motion_vector_boolean_layers_set",
         {**lid, "operation": {
             "type": "string",
             "enum": ["union", "subtract", "intersect", "exclude", "xor"],
          }, "operand_layer_ids": {"type": "array"},
          "hide_operands": {"type": "boolean"}},
         ("composition_id", "layer_id", "operation", "operand_layer_ids")),
        ("motion.vector.trim.set", "motion_vector_trim_set",
         {**lid, "start": {"type": "number"}, "end": {"type": "number"},
          "offset": {"type": "number"}},
         ("composition_id", "layer_id", "start", "end")),
        ("motion.vector.offset_path.set", "motion_vector_offset_path_set",
         {**lid, "amount": {"type": "number"},
          "join": {"type": "string", "enum": ["round", "miter", "bevel"]}},
         ("composition_id", "layer_id", "amount")),
        ("motion.vector.path_morph.set", "motion_vector_path_morph_set",
         {**lid,
          "keyframes": {"type": "array", "items": {"type": "object"}, "minItems": 2},
          "auto_correspond": {"type": "boolean"},
          "target_count": {"type": "integer", "minimum": 0, "maximum": 4096}},
         ("composition_id", "layer_id", "keyframes")),
        ("motion.vector.stroke.set", "motion_vector_stroke_set",
         {**lid,
          "color": {"type": "string"},
          "width": {"type": "number", "minimum": 0},
          "gradient": {"type": "object"},
          "dash": {"type": "array", "items": {"type": "number"}},
          "dash_offset": {"type": "number"},
          "taper_start": {"type": "number", "minimum": 0},
          "taper_end": {"type": "number", "minimum": 0},
          "width_profile": {"type": "array", "items": {"type": "number"}}},
         ("composition_id", "layer_id")),
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
        ("motion.typography.character_3d.prepare",
         "motion_typography_character_3d_prepare",
         {**lid,
          "depth": {"type": "number", "minimum": 0},
          "bevel": {"type": "number", "minimum": 0},
          "z_spacing": {"type": "number"},
          "overrides": {"type": "object"}},
         ("composition_id", "layer_id"), True),
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
            "replace_existing": {"type": "boolean"},
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
        "motion.template.trend.capabilities",
        "List supported 2026 trend templates and explicit unavailable capabilities.",
        "motion",
        "motion_template_trend_capabilities",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.template.trend.preflight",
        "Validate editable trend variants and explicit Unreal bake or block results.",
        "motion",
        "motion_template_trend_preflight",
        params_schema=schema_object({
            "template_id": {"type": "string"},
        }),
        mutating=False,
        changed=False,
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
    umg_project = {
        "project_path": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.umg.plugin.status",
        "Inspect the project-local Tiger Studio UMG plugin.",
        "motion",
        "motion_umg_plugin_status",
        params_schema=schema_object(umg_project, required=("project_path",)),
        required=("project_path",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.umg.plugin.install",
        "Install or update and enable Tiger Studio UMG in an Unreal project.",
        "motion",
        "motion_umg_plugin_install",
        params_schema=schema_object(umg_project, required=("project_path",)),
        required=("project_path",),
        mutating=True,
        changed=True,
        undo_label="Install Tiger Studio UMG Plugin",
        dry_summary="The project-local Tiger Studio UMG plugin would be installed and enabled",
    )
    registry.register_adapter_action(
        "motion.umg.preflight",
        "Validate Motion and Unreal project readiness for native UMG generation.",
        "motion",
        "motion_umg_preflight",
        params_schema=schema_object(
            {**cid, **umg_project},
            required=("composition_id", "project_path"),
        ),
        required=("composition_id", "project_path"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.umg.package",
        "Package a Motion composition and its resources as a Tiger UMG document.",
        "motion",
        "motion_umg_package",
        params_schema=schema_object(
            {**cid, "output_dir": {"type": "string"}},
            required=("composition_id", "output_dir"),
        ),
        required=("composition_id", "output_dir"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.umg.generate",
        "Package Motion, install the plugin, generate and compile native Unreal UMG assets.",
        "motion",
        "motion_umg_generate",
        params_schema=schema_object(
            {
                **cid,
                **umg_project,
                "output_dir": {"type": "string"},
                "destination_root": {"type": "string"},
                "timeout_seconds": {"type": "integer", "minimum": 30, "maximum": 1800},
            },
            required=("composition_id", "project_path"),
        ),
        required=("composition_id", "project_path"),
        mutating=True,
        changed=True,
        undo_label="Generate Unreal UMG",
        dry_summary="Motion resources and a native Unreal Widget Blueprint would be generated",
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

    registry.register_adapter_action(
        "motion.craft.presets",
        "List deterministic Motion craft-style presets.",
        "motion",
        "motion_craft_presets",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.craft.get",
        "Inspect the craft style applied to a Motion layer.",
        "motion",
        "motion_craft_get",
        params_schema=schema_object(lid, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.craft.apply",
        "Apply or replace a deterministic craft style on a Motion layer.",
        "motion",
        "motion_craft_apply",
        params_schema=schema_object({
            **lid,
            "preset": {
                "type": "string",
                "enum": [
                    "subtle_film", "handmade", "archive_print", "luxury_paper",
                    "documentary_handheld", "vhs_tape", "printed_poster",
                    "warm_film", "rough_cut",
                ],
            },
            "settings": {"type": "object"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Apply Craft Style",
        dry_summary="A deterministic craft style would be applied",
    )
    registry.register_adapter_action(
        "motion.craft.clear",
        "Remove the craft style from a Motion layer.",
        "motion",
        "motion_craft_clear",
        params_schema=schema_object(lid, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Clear Craft Style",
        dry_summary="The craft style would be removed",
    )
    registry.register_adapter_action(
        "motion.craft.set",
        "Set or replace the editable craft style on a Motion layer.",
        "motion",
        "motion_craft_apply",
        params_schema=schema_object({
            **lid,
            "preset": {
                "type": "string",
                "enum": [
                    "subtle_film", "handmade", "archive_print", "luxury_paper",
                    "documentary_handheld", "vhs_tape", "printed_poster",
                    "warm_film", "rough_cut",
                ],
            },
            "settings": {"type": "object"},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Set Craft Style",
        dry_summary="The craft style would be replaced",
    )
    registry.register_adapter_action(
        "motion.craft.preset.list",
        "List Motion craft-style presets.",
        "motion",
        "motion_craft_presets",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.craft.preset.apply",
        "Apply a named Motion craft-style preset.",
        "motion",
        "motion_craft_apply",
        params_schema=schema_object({
            **lid,
            "preset": {
                "type": "string",
                "enum": [
                    "subtle_film", "handmade", "archive_print", "luxury_paper",
                    "documentary_handheld", "vhs_tape", "printed_poster",
                    "warm_film", "rough_cut",
                ],
            },
            "settings": {"type": "object"},
        }, required=("composition_id", "layer_id", "preset")),
        required=("composition_id", "layer_id", "preset"),
        undo_label="Apply Craft Preset",
        dry_summary="A named craft preset would be applied",
    )
    texture_props = {
        **lid,
        "uri": {"type": "string"},
        "blend_mode": {
            "type": "string",
            "enum": ["multiply", "screen", "overlay"],
        },
        "opacity": {"type": "number", "minimum": 0, "maximum": 1},
    }
    for action_id in ("motion.craft.texture.attach", "motion.craft.texture.relink"):
        registry.register_adapter_action(
            action_id,
            "Attach or relink a durable texture to a Motion craft style.",
            "motion",
            "motion_craft_texture_attach",
            params_schema=schema_object(
                texture_props,
                required=("composition_id", "layer_id", "uri"),
            ),
            required=("composition_id", "layer_id", "uri"),
            undo_label="Attach Craft Texture",
            dry_summary="A durable craft texture would be linked",
        )
    registry.register_adapter_action(
        "motion.craft.seed.randomize",
        "Randomize or explicitly set the deterministic Motion craft seed.",
        "motion",
        "motion_craft_seed_randomize",
        params_schema=schema_object({
            **lid,
            "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
        }, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Randomize Craft Seed",
        dry_summary="The craft seed would change",
    )
    registry.register_adapter_action(
        "motion.craft.seed.lock",
        "Lock or unlock the Motion craft seed.",
        "motion",
        "motion_craft_seed_lock",
        params_schema=schema_object({
            **lid,
            "locked": {"type": "boolean"},
        }, required=("composition_id", "layer_id", "locked")),
        required=("composition_id", "layer_id", "locked"),
        undo_label="Set Craft Seed Lock",
        dry_summary="The craft seed lock would change",
    )
    registry.register_adapter_action(
        "motion.craft.preflight",
        "Validate deterministic craft resources and output disposition.",
        "motion",
        "motion_craft_preflight",
        params_schema=schema_object(lid, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    glass_presets = ["clear", "frosted", "tinted", "glossy", "liquid_cta"]
    registry.register_adapter_action(
        "motion.material.glass.preset.list",
        "List Tiger Glass material presets.",
        "motion",
        "motion_glass_presets",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.material.glass.get",
        "Inspect the Tiger Glass material on a Motion layer.",
        "motion",
        "motion_glass_get",
        params_schema=schema_object(lid, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    glass_set_props = {
        **lid,
        "preset": {"type": "string", "enum": glass_presets},
        "settings": {"type": "object"},
    }
    for action_id in ("motion.material.glass.create", "motion.material.glass.set"):
        registry.register_adapter_action(
            action_id,
            "Create or update backdrop-aware Tiger Glass.",
            "motion",
            "motion_glass_set",
            params_schema=schema_object(
                glass_set_props,
                required=("composition_id", "layer_id"),
            ),
            required=("composition_id", "layer_id"),
            undo_label="Set Tiger Glass",
            dry_summary="Backdrop-aware Tiger Glass would be set",
        )
    registry.register_adapter_action(
        "motion.material.glass.remove",
        "Remove Tiger Glass from a Motion layer.",
        "motion",
        "motion_glass_remove",
        params_schema=schema_object(lid, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        undo_label="Remove Tiger Glass",
        dry_summary="Tiger Glass would be removed",
    )
    registry.register_adapter_action(
        "motion.material.glass.driver.bind",
        "Bind pointer, velocity, scroll, or manual input to Tiger Glass.",
        "motion",
        "motion_glass_driver_bind",
        params_schema=schema_object({
            **lid,
            "source": {
                "type": "string",
                "enum": ["pointer", "velocity", "scroll", "manual"],
            },
            "strength": {"type": "number", "minimum": 0, "maximum": 10},
            "x": {"type": "number"},
            "y": {"type": "number"},
        }, required=("composition_id", "layer_id", "source")),
        required=("composition_id", "layer_id", "source"),
        undo_label="Bind Tiger Glass Driver",
        dry_summary="A Tiger Glass response driver would be bound",
    )
    registry.register_adapter_action(
        "motion.material.glass.preflight",
        "Report Tiger Glass renderer and Unreal output disposition.",
        "motion",
        "motion_glass_preflight",
        params_schema=schema_object(lid, required=("composition_id", "layer_id")),
        required=("composition_id", "layer_id"),
        mutating=False,
        changed=False,
    )
    collage_ref = {
        **cid,
        "board_id": {"type": "string"},
    }
    collage_item_ref = {
        **collage_ref,
        "item_id": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.collage.list",
        "List editable collage boards in a Motion composition.",
        "motion",
        "motion_collage_list",
        params_schema=schema_object(cid, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.collage.create",
        "Create an editable collage board from existing Motion layers.",
        "motion",
        "motion_collage_create",
        params_schema=schema_object({
            **cid,
            "layer_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "name": {"type": "string"},
            "layout": {
                "type": "string",
                "enum": ["manual", "editorial", "scatter", "education", "luxury"],
            },
            "seed": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "layer_ids")),
        required=("composition_id", "layer_ids"),
        undo_label="Create Collage Board",
        dry_summary="An editable collage board would be created",
    )
    registry.register_adapter_action(
        "motion.collage.item.add",
        "Add an existing Motion layer to a collage board.",
        "motion",
        "motion_collage_item_add",
        params_schema=schema_object({
            **collage_ref,
            "layer_id": {"type": "string"},
        }, required=("composition_id", "board_id", "layer_id")),
        required=("composition_id", "board_id", "layer_id"),
        undo_label="Add Collage Item",
        dry_summary="A layer would join the collage board",
    )
    registry.register_adapter_action(
        "motion.collage.item.update",
        "Update editable collage item metadata or rebind its source layer.",
        "motion",
        "motion_collage_item_update",
        params_schema=schema_object({
            **collage_item_ref,
            "changes": {"type": "object"},
        }, required=("composition_id", "board_id", "item_id", "changes")),
        required=("composition_id", "board_id", "item_id", "changes"),
        undo_label="Update Collage Item",
        dry_summary="Collage item metadata would change",
    )
    registry.register_adapter_action(
        "motion.collage.item.reorder",
        "Move a collage item through the board z-stack.",
        "motion",
        "motion_collage_item_reorder",
        params_schema=schema_object({
            **collage_item_ref,
            "z_index": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "board_id", "item_id", "z_index")),
        required=("composition_id", "board_id", "item_id", "z_index"),
        undo_label="Reorder Collage Item",
        dry_summary="The collage z-stack would change",
    )
    registry.register_adapter_action(
        "motion.collage.edge.set",
        "Set polygon, smart, torn, feathered, or fibrous collage edges.",
        "motion",
        "motion_collage_edge_set",
        params_schema=schema_object({
            **collage_item_ref,
            "mode": {
                "type": "string",
                "enum": ["smart", "polygon", "torn", "feather", "fiber"],
            },
            "roughness": {"type": "number", "minimum": 0, "maximum": 1},
            "feather": {"type": "number", "minimum": 0, "maximum": 64},
            "seed": {"type": "integer", "minimum": 0},
            "points": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                },
            },
        }, required=("composition_id", "board_id", "item_id", "mode")),
        required=("composition_id", "board_id", "item_id", "mode"),
        undo_label="Set Collage Edge",
        dry_summary="The collage edge treatment would change",
    )
    registry.register_adapter_action(
        "motion.collage.attachment.set",
        "Set glue, tape, staple, pin, or fold treatment on a collage item.",
        "motion",
        "motion_collage_attachment_set",
        params_schema=schema_object({
            **collage_item_ref,
            "kind": {
                "type": "string",
                "enum": ["none", "glue", "tape", "staple", "pin", "fold"],
            },
            "color": {"type": "string"},
            "strength": {"type": "number", "minimum": 0, "maximum": 1},
            "angle": {"type": "number", "minimum": -180, "maximum": 180},
        }, required=("composition_id", "board_id", "item_id", "kind")),
        required=("composition_id", "board_id", "item_id", "kind"),
        undo_label="Set Collage Attachment",
        dry_summary="The collage attachment treatment would change",
    )
    registry.register_adapter_action(
        "motion.collage.source.replace",
        "Replace collage media while preserving item, layer, pivot, parent, and timing.",
        "motion",
        "motion_collage_source_replace",
        params_schema=schema_object({
            **collage_item_ref,
            "source": {"type": "object"},
        }, required=("composition_id", "board_id", "item_id", "source")),
        required=("composition_id", "board_id", "item_id", "source"),
        undo_label="Replace Collage Source",
        dry_summary="Collage source media would be replaced without changing IDs",
    )
    registry.register_adapter_action(
        "motion.collage.scan.set",
        "Clean a scanned collage source while preserving ink and optional transparency.",
        "motion",
        "motion_collage_scan_set",
        params_schema=schema_object({
            **collage_item_ref,
            "white_balance": {"type": "number", "minimum": 0, "maximum": 1},
            "paper_remove": {"type": "number", "minimum": 0, "maximum": 1},
            "ink_preserve": {"type": "number", "minimum": 0, "maximum": 1},
            "threshold": {"type": "number", "minimum": 0.05, "maximum": 0.98},
        }, required=("composition_id", "board_id", "item_id")),
        required=("composition_id", "board_id", "item_id"),
        undo_label="Set Collage Scan Cleanup",
        dry_summary="Scanned paper would be balanced and its ink preserved",
    )
    registry.register_adapter_action(
        "motion.collage.paint.send",
        "Create a stable-ID collage handoff for Painter.",
        "motion",
        "motion_collage_paint_send",
        params_schema=schema_object({
            **collage_item_ref,
            "document_id": {"type": "string"},
            "object_id": {"type": "string"},
            "revision": {"type": "integer", "minimum": 1},
        }, required=(
            "composition_id", "board_id", "item_id",
            "document_id", "object_id",
        )),
        required=(
            "composition_id", "board_id", "item_id",
            "document_id", "object_id",
        ),
        undo_label="Send Collage Item To Painter",
        dry_summary="A stable Painter handoff would be stored",
    )
    registry.register_adapter_action(
        "motion.collage.paint.refresh",
        "Refresh collage source data from Painter without changing stable IDs.",
        "motion",
        "motion_collage_paint_refresh",
        params_schema=schema_object({
            **collage_item_ref,
            "revision": {"type": "integer", "minimum": 1},
            "source": {"type": "object"},
        }, required=("composition_id", "board_id", "item_id", "revision")),
        required=("composition_id", "board_id", "item_id", "revision"),
        undo_label="Refresh Collage Item From Painter",
        dry_summary="Painter changes would refresh the linked collage item",
    )
    registry.register_adapter_action(
        "motion.collage.preflight",
        "Validate collage IDs, layers, Painter links, and delivery disposition.",
        "motion",
        "motion_collage_preflight",
        params_schema=schema_object(
            collage_ref,
            required=("composition_id", "board_id"),
        ),
        required=("composition_id", "board_id"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.story.inspect",
        "Inspect editable story beats, intent, continuity, and story preflight.",
        "motion",
        "motion_story_inspect",
        params_schema=schema_object(cid, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.story.update",
        "Update story title, message, audience, or character continuity rules.",
        "motion",
        "motion_story_update",
        params_schema=schema_object({
            **cid,
            "changes": {"type": "object"},
        }, required=("composition_id", "changes")),
        required=("composition_id", "changes"),
        undo_label="Update Story Direction",
        dry_summary="Story direction would be updated",
    )
    registry.register_adapter_action(
        "motion.story.beat.add",
        "Add a Hook-to-CTA story beat linked to scene layers and time.",
        "motion",
        "motion_story_beat_add",
        params_schema=schema_object({
            **cid,
            "role": {
                "type": "string",
                "enum": [
                    "hook", "setup", "desire", "conflict",
                    "reveal", "proof", "payoff", "cta",
                ],
            },
            "start_ms": {"type": "integer", "minimum": 0},
            "end_ms": {"type": "integer", "minimum": 1},
            "purpose": {"type": "string"},
            "emotion": {"type": "string"},
            "character": {"type": "string"},
            "copy": {"type": "string"},
            "visual": {"type": "string"},
            "audio_cue": {"type": "string"},
            "scene_id": {"type": "string"},
            "layer_ids": {"type": "array", "items": {"type": "string"}},
        }, required=("composition_id", "role", "start_ms", "end_ms")),
        required=("composition_id", "role", "start_ms", "end_ms"),
        undo_label="Add Story Beat",
        dry_summary="A timed story beat would be added",
    )
    registry.register_adapter_action(
        "motion.story.beat.update",
        "Update the purpose, emotion, copy, visual, timing, or layer links of a story beat.",
        "motion",
        "motion_story_beat_update",
        params_schema=schema_object({
            **cid,
            "beat_id": {"type": "string"},
            "changes": {"type": "object"},
        }, required=("composition_id", "beat_id", "changes")),
        required=("composition_id", "beat_id", "changes"),
        undo_label="Update Story Beat",
        dry_summary="The story beat would be updated",
    )
    registry.register_adapter_action(
        "motion.story.beat.reorder",
        "Reorder a story beat without changing its stable ID or timing.",
        "motion",
        "motion_story_beat_reorder",
        params_schema=schema_object({
            **cid,
            "beat_id": {"type": "string"},
            "order": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "beat_id", "order")),
        required=("composition_id", "beat_id", "order"),
        undo_label="Reorder Story Beat",
        dry_summary="The story beat order would change",
    )
    registry.register_adapter_action(
        "motion.story.audio.bind",
        "Bind a Voice Lab line or Music Lab cue and tempo marker to a story beat.",
        "motion",
        "motion_story_audio_bind",
        params_schema=schema_object({
            **cid,
            "beat_id": {"type": "string"},
            "source_kind": {"type": "string", "enum": ["voice", "music"]},
            "source_id": {"type": "string"},
            "cue_ms": {"type": "integer", "minimum": 0},
            "label": {"type": "string"},
            "tempo_bpm": {"type": "number", "minimum": 20, "maximum": 320},
        }, required=(
            "composition_id", "beat_id", "source_kind", "source_id", "cue_ms",
        )),
        required=(
            "composition_id", "beat_id", "source_kind", "source_id", "cue_ms",
        ),
        undo_label="Bind Story Audio",
        dry_summary="A Voice or Music cue would be linked to the story beat",
    )
    platform_ref = {
        **cid,
        "platform": {
            "type": "string",
            "enum": [
                "landscape_16_9", "vertical_9_16", "square_1_1",
                "16:9", "9:16", "1:1", "youtube", "shorts",
                "reels", "tiktok", "feed",
            ],
        },
    }
    registry.register_adapter_action(
        "motion.platform.variant.plan",
        "Plan priority-based platform reflow and return a reviewable diff.",
        "motion",
        "motion_platform_variant_plan",
        params_schema=schema_object(
            platform_ref,
            required=("composition_id", "platform"),
        ),
        required=("composition_id", "platform"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.platform.variant.preview",
        "Preview a platform variant, its complete diff, and safe-area preflight.",
        "motion",
        "motion_platform_variant_preview",
        params_schema=schema_object(
            platform_ref,
            required=("composition_id", "platform"),
        ),
        required=("composition_id", "platform"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.platform.variant.apply",
        "Create a new platform composition from a reviewed reflow plan.",
        "motion",
        "motion_platform_variant_apply",
        params_schema=schema_object({
            **cid,
            "plan": {"type": "object"},
            "approved": {"type": "boolean"},
        }, required=("composition_id", "plan", "approved")),
        required=("composition_id", "plan", "approved"),
        undo_label="Create Platform Variant",
        dry_summary="An approved platform variant would be created",
    )
    registry.register_adapter_action(
        "motion.platform.preflight",
        "Check story continuity, safe areas, text density, and CTA hold for a platform.",
        "motion",
        "motion_platform_preflight",
        params_schema=schema_object(
            platform_ref,
            required=("composition_id", "platform"),
        ),
        required=("composition_id", "platform"),
        mutating=False,
        changed=False,
    )
    stop_scope = {
        **cid,
        "layer_ids": {"type": "array", "items": {"type": "string"}},
    }
    registry.register_adapter_action(
        "motion.stop_motion.get",
        "Get composition and effective layer stop-motion timing settings.",
        "motion",
        "motion_stop_motion_get",
        params_schema=schema_object(stop_scope, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.stop_motion.set",
        "Set ones, twos, or threes exposure timing and tactile motion controls.",
        "motion",
        "motion_stop_motion_set",
        params_schema=schema_object({
            **stop_scope,
            "settings": {"type": "object"},
        }, required=("composition_id", "settings")),
        required=("composition_id", "settings"),
        undo_label="Set Stop Motion Timing",
        dry_summary="Stop-motion exposure and tactile timing would be updated",
    )
    registry.register_adapter_action(
        "motion.stop_motion.pose.capture",
        "Capture selected layer transforms as a reusable stop-motion pose.",
        "motion",
        "motion_stop_motion_pose_capture",
        params_schema=schema_object({
            **stop_scope,
            "name": {"type": "string"},
            "time_ms": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "name", "time_ms")),
        required=("composition_id", "name", "time_ms"),
        undo_label="Capture Stop Motion Pose",
        dry_summary="A reusable stop-motion pose would be captured",
    )
    registry.register_adapter_action(
        "motion.stop_motion.pose.apply",
        "Apply a captured pose with stable hold-key identifiers.",
        "motion",
        "motion_stop_motion_pose_apply",
        params_schema=schema_object({
            **stop_scope,
            "pose_id": {"type": "string"},
            "time_ms": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "pose_id")),
        required=("composition_id", "pose_id"),
        undo_label="Apply Stop Motion Pose",
        dry_summary="A captured stop-motion pose would be applied",
    )
    registry.register_adapter_action(
        "motion.stop_motion.material.set",
        "Apply a clay, felt, cardboard, or painted-wood material treatment.",
        "motion",
        "motion_stop_motion_material_set",
        params_schema=schema_object({
            **cid,
            "layer_ids": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
            "preset": {
                "type": "string",
                "enum": ["clay", "felt", "cardboard", "painted_wood"],
            },
            "seed": {"type": "integer", "minimum": 0},
        }, required=("composition_id", "layer_ids", "preset")),
        required=("composition_id", "layer_ids", "preset"),
        undo_label="Set Stop Motion Material",
        dry_summary="A tactile stop-motion material would be applied",
    )
    registry.register_adapter_action(
        "motion.stop_motion.audio.snap",
        "Snap nearby pose keys to audio transients on the exposure grid.",
        "motion",
        "motion_stop_motion_audio_snap",
        params_schema=schema_object({
            **stop_scope,
            "transient_times_ms": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0},
            },
            "threshold_ms": {"type": "integer", "minimum": 0, "maximum": 2000},
        }, required=("composition_id", "transient_times_ms")),
        required=("composition_id", "transient_times_ms"),
        undo_label="Snap Stop Motion To Audio",
        dry_summary="Nearby pose keys would snap to audio transients",
    )
    registry.register_adapter_action(
        "motion.stop_motion.onion.inspect",
        "Inspect previous, current, and next held stop-motion poses.",
        "motion",
        "motion_stop_motion_onion_inspect",
        params_schema=schema_object({
            **cid,
            "layer_id": {"type": "string"},
            "time_ms": {"type": "number", "minimum": 0},
            "frames": {"type": "integer", "minimum": 0, "maximum": 4},
        }, required=("composition_id", "layer_id", "time_ms")),
        required=("composition_id", "layer_id", "time_ms"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.stop_motion.preflight",
        "Check exposure cadence, hold interpolation, poses, and material setup.",
        "motion",
        "motion_stop_motion_preflight",
        params_schema=schema_object(stop_scope, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    style_plan_fields = {
        **cid,
        "prompt": {"type": "string"},
        "references": {"type": "array", "items": {"type": "object"}},
        "layer_ids": {"type": "array", "items": {"type": "string"}},
        "seed": {"type": "integer", "minimum": 0},
    }
    registry.register_adapter_action(
        "motion.ai.style.plan",
        "Create a reviewable five-candidate style plan with backend and cost disclosure.",
        "motion",
        "motion_ai_style_plan",
        params_schema=schema_object(
            style_plan_fields,
            required=("composition_id", "prompt"),
        ),
        required=("composition_id", "prompt"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ai.style.candidates.generate",
        "Generate Clean, Craft, Collage, Glass, and Stop Motion editable candidates.",
        "motion",
        "motion_ai_style_candidates_generate",
        params_schema=schema_object(
            style_plan_fields,
            required=("composition_id", "prompt"),
        ),
        required=("composition_id", "prompt"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ai.style.apply",
        "Apply one reviewed style candidate while preserving source transforms and keyframes.",
        "motion",
        "motion_ai_style_apply",
        params_schema=schema_object({
            **cid,
            "plan": {"type": "object"},
            "candidate_id": {"type": "string"},
            "approved": {"type": "boolean"},
        }, required=("composition_id", "plan", "candidate_id", "approved")),
        required=("composition_id", "plan", "candidate_id", "approved"),
        undo_label="Apply AI Style Direction",
        dry_summary="The approved editable style candidate would be applied",
    )
    registry.register_adapter_action(
        "motion.ai.style.lock.set",
        "Lock brand font, texture, seed, mascot, and protected layers.",
        "motion",
        "motion_ai_style_lock_set",
        params_schema=schema_object({
            **cid,
            "changes": {"type": "object"},
        }, required=("composition_id", "changes")),
        required=("composition_id", "changes"),
        undo_label="Update AI Style Lock",
        dry_summary="Brand and protected-layer locks would be updated",
    )
    registry.register_adapter_action(
        "motion.ai.story.plan",
        "Create a reviewable Hook-to-CTA story plan separate from visual style.",
        "motion",
        "motion_ai_story_plan",
        params_schema=schema_object({
            **cid,
            "prompt": {"type": "string"},
        }, required=("composition_id", "prompt")),
        required=("composition_id", "prompt"),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ai.story.apply",
        "Apply an explicitly approved AI story plan as editable story beats.",
        "motion",
        "motion_ai_story_apply",
        params_schema=schema_object({
            **cid,
            "plan": {"type": "object"},
            "approved": {"type": "boolean"},
        }, required=("composition_id", "plan", "approved")),
        required=("composition_id", "plan", "approved"),
        undo_label="Apply AI Story Direction",
        dry_summary="The approved Hook-to-CTA story plan would be applied",
    )
    registry.register_adapter_action(
        "motion.ai.trend.preflight",
        "Inspect style locks, backend fallbacks, cost, and trend-candidate completeness.",
        "motion",
        "motion_ai_trend_preflight",
        params_schema=schema_object({
            **cid,
            "plan": {"type": "object"},
        }, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
