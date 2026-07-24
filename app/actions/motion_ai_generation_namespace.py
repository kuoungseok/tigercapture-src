"""Registered actions for reviewable Motion Designer AI generation."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


REFERENCE_SCHEMA = {
    "type": "array",
    "items": {"type": "object"},
    "description": "Image/text references already admitted by the Motion AI intake contract.",
}
DECOMPOSITION_SCHEMA = {
    "type": "object",
    "description": "A tigerstudio.motion.image_decomposition.v1 manifest.",
}
POINT_HINTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "array",
        "items": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "minItems": 2,
        "maxItems": 2,
    },
}


def _decomposition_params() -> dict[str, Any]:
    return {
        "source_path": {"type": "string"},
        "width": {"type": "integer", "minimum": 64, "maximum": 8192},
        "height": {"type": "integer", "minimum": 64, "maximum": 8192},
        "max_elements": {"type": "integer", "minimum": 1, "maximum": 12},
        "include_depth": {"type": "boolean"},
        "segmentation_mode": {"type": "string", "enum": ["auto", "basic", "sam"]},
        "point_hints": POINT_HINTS_SCHEMA,
        "inpaint_mode": {"type": "string", "enum": ["auto", "fast", "enhanced_local"]},
        "reconstruct_text": {"type": "boolean"},
        "ocr_native_threshold": {"type": "number", "minimum": 0.5, "maximum": 0.98},
        "force": {"type": "boolean"},
    }


def register_motion_ai_generation_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "motion.ai.provider.status",
        "Inspect the shared Tiger Studio AI provider used by Motion Designer.",
        "motion",
        "motion_ai_provider_status",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.reference.analyze",
        "Probe Motion AI reference facts without mutating a project.",
        "motion",
        "motion_ai_reference_analyze",
        params_schema=schema_object({"references": REFERENCE_SCHEMA}),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.reference.decompose",
        "Decompose one local image into cached editable background, subject, text, mask, and depth assets.",
        "motion",
        "motion_ai_reference_decompose",
        params_schema=schema_object(
            _decomposition_params(),
            required=("source_path", "width", "height"),
        ),
        required=("source_path", "width", "height"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.analyze",
        "Analyze one local image into semantic candidates, integrity reports, OCR, depth, and a layer graph.",
        "motion",
        "motion_ai_layer_analyze",
        params_schema=schema_object(
            _decomposition_params(),
            required=("source_path", "width", "height"),
        ),
        required=("source_path", "width", "height"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.segment",
        "Run the requested Basic Local or optional SAM segmentation provider.",
        "motion",
        "motion_ai_layer_segment",
        params_schema=schema_object(
            _decomposition_params(),
            required=("source_path", "width", "height"),
        ),
        required=("source_path", "width", "height"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.mask.refine",
        "Refine image segmentation from normalized foreground point hints without changing a project.",
        "motion",
        "motion_ai_layer_mask_refine",
        params_schema=schema_object(
            _decomposition_params(),
            required=("source_path", "width", "height", "point_hints"),
        ),
        required=("source_path", "width", "height", "point_hints"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.merge",
        "Merge visual elements into a new non-destructive decomposition revision.",
        "motion",
        "motion_ai_layer_merge",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "element_ids": {"type": "array", "items": {"type": "string"}, "minItems": 2},
        }, required=("decomposition", "element_ids")),
        required=("decomposition", "element_ids"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.mask.replace",
        "Replace one element mask from an edited grayscale image in a non-destructive revision.",
        "motion",
        "motion_ai_layer_mask_replace",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "element_id": {"type": "string"},
            "mask_path": {"type": "string"},
        }, required=("decomposition", "element_id", "mask_path")),
        required=("decomposition", "element_id", "mask_path"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.split",
        "Split one visual element horizontally or vertically into a new decomposition revision.",
        "motion",
        "motion_ai_layer_split",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "element_id": {"type": "string"},
            "axis": {"type": "string", "enum": ["horizontal", "vertical"]},
            "position": {"type": "number", "minimum": 0.02, "maximum": 0.98},
        }, required=("decomposition", "element_id", "axis", "position")),
        required=("decomposition", "element_id", "axis", "position"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.lock",
        "Lock or unlock visual elements against the reconstructed background motion.",
        "motion",
        "motion_ai_layer_lock",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "element_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "locked": {"type": "boolean"},
        }, required=("decomposition", "element_ids", "locked")),
        required=("decomposition", "element_ids", "locked"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.group",
        "Parent visual elements to another decomposition element or clear their parent.",
        "motion",
        "motion_ai_layer_group",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "child_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "parent_id": {"type": "string"},
        }, required=("decomposition", "child_ids")),
        required=("decomposition", "child_ids"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.pivot",
        "Set an element pivot in decomposition canvas coordinates.",
        "motion",
        "motion_ai_layer_pivot",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "element_id": {"type": "string"},
            "pivot": {
                "type": "array", "items": {"type": "number"},
                "minItems": 2, "maxItems": 2,
            },
        }, required=("decomposition", "element_id", "pivot")),
        required=("decomposition", "element_id", "pivot"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.layer.order",
        "Set an element z-order in a non-destructive decomposition revision.",
        "motion",
        "motion_ai_layer_order",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "element_id": {"type": "string"},
            "z_order": {"type": "integer"},
        }, required=("decomposition", "element_id", "z_order")),
        required=("decomposition", "element_id", "z_order"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.background.inpaint",
        "Rebuild a decomposition with the requested local background reconstruction quality.",
        "motion",
        "motion_ai_background_inpaint",
        params_schema=schema_object(
            _decomposition_params(),
            required=("source_path", "width", "height"),
        ),
        required=("source_path", "width", "height"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.text.reconstruct",
        "Analyze high-confidence OCR regions for native editable Motion typography.",
        "motion",
        "motion_ai_text_reconstruct",
        params_schema=schema_object(
            _decomposition_params(),
            required=("source_path", "width", "height"),
        ),
        required=("source_path", "width", "height"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.choreography.plan",
        "Plan Clean, Dynamic, or Collage motion while preserving rigid and parent locks.",
        "motion",
        "motion_ai_choreography_plan",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
            "duration_ms": {"type": "integer", "minimum": 1, "maximum": 3600000},
            "variant": {"type": "string", "enum": ["auto", "clean", "dynamic", "collage"]},
            "prompt": {"type": "string"},
            "motion_style": {"type": "string"},
            "audio_hits_ms": {"type": "array", "items": {"type": "integer", "minimum": 0}},
        }, required=("decomposition", "duration_ms")),
        required=("decomposition", "duration_ms"),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.integrity.validate",
        "Validate decomposition assets, layer graph, and first-frame reconstruction.",
        "motion",
        "motion_ai_integrity_validate",
        params_schema=schema_object({
            "decomposition": DECOMPOSITION_SCHEMA,
        }, required=("decomposition",)),
        required=("decomposition",),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.ai.choreography.apply",
        "Compile one reviewed decomposition and choreography into a Motion composition revision.",
        "motion",
        "motion_ai_choreography_apply",
        params_schema=schema_object({
            "composition_id": {"type": "string"},
            "decomposition": DECOMPOSITION_SCHEMA,
            "reference_id": {"type": "string"},
            "name": {"type": "string"},
            "in_ms": {"type": "integer", "minimum": 0},
            "out_ms": {"type": "integer", "minimum": 1},
            "center": {
                "type": "array", "items": {"type": "number"},
                "minItems": 2, "maxItems": 2,
            },
            "size": {
                "type": "array", "items": {"type": "integer", "minimum": 1},
                "minItems": 2, "maxItems": 2,
            },
            "variant": {"type": "string", "enum": ["auto", "clean", "dynamic", "collage"]},
            "prompt": {"type": "string"},
            "motion_style": {"type": "string"},
            "audio_hits_ms": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "base_revision": {"type": "integer", "minimum": 0},
        }, required=(
            "composition_id", "decomposition", "in_ms", "out_ms",
        )),
        required=("composition_id", "decomposition", "in_ms", "out_ms"),
        mutating=True,
        changed=True,
        requires_review=True,
        undo_label="Apply Layered Image Choreography",
        dry_summary="The reviewed image decomposition would be added as editable Motion layers",
    )
    registry.register_adapter_action(
        "motion.ai.candidate.preview",
        "Render review PNGs for a Motion AI proposal without changing the composition.",
        "motion",
        "motion_ai_candidate_preview",
        params_schema=schema_object({
            "composition_id": {"type": "string"},
            "proposal": {"type": "object"},
            "output_dir": {"type": "string"},
            "times_ms": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0},
            },
        }, required=("composition_id", "proposal", "output_dir")),
        required=("composition_id", "proposal", "output_dir"),
        mutating=False,
        changed=False,
    )
    common = {
        "composition_id": {"type": "string"},
        "prompt": {"type": "string"},
        "references": REFERENCE_SCHEMA,
        "provider": {"type": "string"},
        "decompose_images": {"type": "boolean"},
        "max_decomposed_elements": {"type": "integer", "minimum": 1, "maximum": 12},
        "segmentation_mode": {"type": "string", "enum": ["auto", "basic", "sam"]},
        "inpaint_mode": {"type": "string", "enum": ["auto", "fast", "enhanced_local"]},
        "reconstruct_text": {"type": "boolean"},
        "ocr_native_threshold": {"type": "number", "minimum": 0.5, "maximum": 0.98},
        "motion_variant": {"type": "string", "enum": ["auto", "clean", "dynamic", "collage"]},
    }
    registry.register_adapter_action(
        "motion.ai.candidates.generate",
        "Generate Clean, Dynamic, and Collage candidates from one validated AI plan.",
        "motion",
        "motion_ai_candidates_generate",
        params_schema=schema_object(common, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ai.brief.create",
        "Create a reviewable Motion creative brief from prompt and references.",
        "motion",
        "motion_ai_brief_create",
        params_schema=schema_object(common, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ai.storyboard.generate",
        "Generate a validated beat storyboard through the shared AI provider contract.",
        "motion",
        "motion_ai_storyboard_generate",
        params_schema=schema_object(common, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
    )
    registry.register_adapter_action(
        "motion.ai.candidate.generate",
        "Compile prompt and references into reviewable editable Motion layers.",
        "motion",
        "motion_ai_candidate_generate",
        params_schema=schema_object(common, required=("composition_id",)),
        required=("composition_id",),
        mutating=False,
        changed=False,
        dry_summary="An editable Motion candidate would be generated without changing the composition",
    )
    registry.register_adapter_action(
        "motion.ai.patch.plan",
        "Plan a validated layer-scoped conversational Motion patch.",
        "motion",
        "motion_ai_patch_plan",
        params_schema=schema_object({
            "composition_id": {"type": "string"},
            "prompt": {"type": "string"},
            "layer_ids": {"type": "array", "items": {"type": "string"}},
            "provider": {"type": "string"},
        }, required=("composition_id", "prompt")),
        required=("composition_id", "prompt"),
        mutating=False,
        changed=False,
        dry_summary="A scoped Motion patch would be planned without changing the composition",
    )
    registry.register_adapter_action(
        "motion.ai.patch.apply",
        "Apply one reviewed Motion AI patch as one revision.",
        "motion",
        "motion_ai_patch_apply",
        params_schema=schema_object({
            "composition_id": {"type": "string"},
            "patch": {"type": "object"},
        }, required=("composition_id", "patch")),
        required=("composition_id", "patch"),
        mutating=True,
        changed=True,
        requires_review=True,
        undo_label="Apply Motion AI Patch",
        dry_summary="The reviewed Motion AI patch would be applied as one undoable edit",
    )


__all__ = ["register_motion_ai_generation_actions"]
