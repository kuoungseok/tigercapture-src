"""Registered Motion tracking, stabilization, and assisted camera-solve actions."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_motion_tracking_actions(registry: Any) -> None:
    cid = {"composition_id": {"type": "string"}}
    video = {
        **cid,
        "video_path": {"type": "string"},
        "start_ms": {"type": "integer", "minimum": 0},
        "end_ms": {"type": "integer", "minimum": 1},
        "sample_interval_ms": {"type": "integer", "minimum": 1, "maximum": 5000},
        "target_size": {"type": "array", "minItems": 2, "maxItems": 2},
        "roi": {"type": "array", "minItems": 4, "maxItems": 4},
        "name": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.restoration.preflight",
        "Estimate restored-pixel exposure and clamp unsafe camera travel.",
        "motion",
        "motion_restoration_preflight",
        params_schema=schema_object({
            "restoration_mask_path": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "max_camera_travel_ratio": {"type": "number", "minimum": 0},
            "camera_dx_ratio": {"type": "number"},
            "camera_dy_ratio": {"type": "number"},
            "grid_size": {"type": "integer", "minimum": 2, "maximum": 32},
        }, required=(
            "restoration_mask_path",
            "confidence",
            "max_camera_travel_ratio",
        )),
        required=(
            "restoration_mask_path",
            "confidence",
            "max_camera_travel_ratio",
        ),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.matte.temporal.validate",
        "Detect propagated matte pop, boundary flicker, centroid drift, confidence loss, and the first unsafe frame.",
        "motion",
        "motion_matte_temporal_validate",
        params_schema=schema_object({
            "mask_paths": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 2,
            },
            "times_ms": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "confidences": {"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 1}},
            "thin_structure": {"type": "boolean"},
        }, required=("mask_paths",)),
        required=("mask_paths",),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    for action_id, method, title in (
        ("motion.track.point", "motion_track_point", "Analyze Point Track"),
        ("motion.track.multi_point", "motion_track_multi_point", "Analyze Multi-point Track"),
        ("motion.track.planar", "motion_track_planar", "Analyze Planar Track"),
    ):
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object(
                video,
                required=("composition_id", "video_path"),
            ),
            required=("composition_id", "video_path"),
            mutating=True,
            changed=True,
            undo_label=title,
            dry_summary=f"{title} would generate a reusable tracking asset",
        )
    registry.register_adapter_action(
        "motion.track.mask",
        "Analyze a reusable mask track.",
        "motion",
        "motion_track_mask",
        params_schema=schema_object(
            {
                **video,
                "mode": {"type": "string", "enum": ["point", "planar"]},
            },
            required=("composition_id", "video_path"),
        ),
        required=("composition_id", "video_path"),
        mutating=True,
        changed=True,
        undo_label="Analyze Mask Track",
        dry_summary="A reusable mask tracking asset would be generated",
    )
    registry.register_adapter_action(
        "motion.track.face",
        "Store normalized face-landmark motion samples as a reusable Motion track.",
        "motion",
        "motion_track_face",
        params_schema=schema_object(
            {
                **cid,
                "samples": {
                    "type": "array",
                    "items": {"type": "object"},
                    "minItems": 1,
                },
                "name": {"type": "string"},
                "source_uri": {"type": "string"},
                "source_revision": {"type": "string"},
                "origin": {"type": "array", "minItems": 2, "maxItems": 2},
                "video_path": {"type": "string"},
                "backend": {
                    "type": "string",
                    "enum": ["auto", "mediapipe_tasks", "mediapipe", "opencv"],
                },
                "max_fps": {"type": "number", "minimum": 1, "maximum": 60},
                "max_frames": {"type": "integer", "minimum": 1},
                "source_in_ms": {"type": "integer", "minimum": 0},
                "timeline_in_ms": {"type": "integer", "minimum": 0},
                "timeline_out_ms": {"type": "integer", "minimum": 1},
                "time_scale": {"type": "number", "exclusiveMinimum": 0},
            },
            required=("composition_id",),
        ),
        required=("composition_id",),
        mutating=True,
        changed=True,
        undo_label="Create Face Track",
        dry_summary="Face motion samples would become a reusable track asset",
    )
    registry.register_adapter_action(
        "motion.track.create",
        "Store provider-neutral tracking samples.",
        "motion",
        "motion_track_create",
        params_schema=schema_object(
            {
                **cid,
                "kind": {
                    "type": "string",
                    "enum": ["point", "multi_point", "planar", "mask", "face"],
                },
                "samples": {
                    "type": "array",
                    "items": {"type": "object"},
                    "minItems": 1,
                },
                "name": {"type": "string"},
                "source_uri": {"type": "string"},
                "source_revision": {"type": "string"},
                "origin": {"type": "array", "minItems": 2, "maxItems": 2},
                "metadata": {"type": "object"},
            },
            required=("composition_id", "kind", "samples"),
        ),
        required=("composition_id", "kind", "samples"),
        mutating=True,
        changed=True,
        undo_label="Create Motion Track",
        dry_summary="Provider-neutral samples would become a Motion track",
    )
    apply_props = {
        **cid,
        "track_id": {"type": "string"},
        "layer_id": {"type": "string"},
        "channels": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["position", "scale", "rotation"],
            },
        },
        "target_kind": {
            "type": "string",
            "enum": ["layer", "effect_point", "puppet_pin", "corner_pin"],
        },
        "effect_id": {"type": "string"},
        "parameter": {"type": "string"},
        "pin_id": {"type": "string"},
    }
    registry.register_adapter_action(
        "motion.track.apply",
        "Bake a reusable track onto layer transform channels.",
        "motion",
        "motion_track_apply",
        params_schema=schema_object(
            apply_props,
            required=("composition_id", "track_id", "layer_id"),
        ),
        required=("composition_id", "track_id", "layer_id"),
        mutating=True,
        changed=True,
        undo_label="Apply Motion Track",
        dry_summary="Tracking samples would be baked onto the target layer",
    )
    registry.register_adapter_action(
        "motion.stabilize.create",
        "Bake the inverse of a reusable track onto a layer.",
        "motion",
        "motion_stabilize_create",
        params_schema=schema_object(
            apply_props,
            required=("composition_id", "track_id", "layer_id"),
        ),
        required=("composition_id", "track_id", "layer_id"),
        mutating=True,
        changed=True,
        undo_label="Stabilize Motion Layer",
        dry_summary="Inverse tracking transforms would stabilize the target layer",
    )
    registry.register_adapter_action(
        "motion.track.diagnostics",
        "Report confidence, occlusion, reacquisition, step size, and source revision state.",
        "motion",
        "motion_track_diagnostics",
        params_schema=schema_object(
            {
                **cid,
                "track_id": {"type": "string"},
                "current_source_revision": {"type": "string"},
            },
            required=("composition_id",),
        ),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.track.relink",
        "Relink a cached Motion track to a source revision.",
        "motion",
        "motion_track_relink",
        params_schema=schema_object(
            {
                **cid,
                "track_id": {"type": "string"},
                "source_uri": {"type": "string"},
                "source_revision": {"type": "string"},
            },
            required=("composition_id", "track_id", "source_uri"),
        ),
        required=("composition_id", "track_id", "source_uri"),
        mutating=True,
        changed=True,
        undo_label="Relink Motion Track",
        dry_summary="The cached track source revision would be relinked",
    )
    registry.register_adapter_action(
        "motion.camera_solve.create",
        "Create a manual-assisted depth plane and camera-intrinsics contract.",
        "motion",
        "motion_camera_solve_create",
        params_schema=schema_object(
            {
                **cid,
                "image_points": {
                    "type": "array",
                    "items": {"type": "array", "minItems": 2, "maxItems": 2},
                    "minItems": 3,
                },
                "frame_size": {"type": "array", "minItems": 2, "maxItems": 2},
                "source_id": {"type": "string"},
                "depth_source_id": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "focal_length_px": {"type": "number", "minimum": 1},
            },
            required=("composition_id", "image_points", "frame_size"),
        ),
        required=("composition_id", "image_points", "frame_size"),
        mutating=True,
        changed=True,
        undo_label="Create Assisted Camera Solve",
        dry_summary="A manual-assisted camera and ground-plane solution would be stored",
    )


__all__ = ["register_motion_tracking_actions"]
