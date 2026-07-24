"""Registered actions for reviewable Motion Designer AI generation."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


REFERENCE_SCHEMA = {
    "type": "array",
    "items": {"type": "object"},
    "description": "Image/text references already admitted by the Motion AI intake contract.",
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
    common = {
        "composition_id": {"type": "string"},
        "prompt": {"type": "string"},
        "references": REFERENCE_SCHEMA,
        "provider": {"type": "string"},
    }
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
