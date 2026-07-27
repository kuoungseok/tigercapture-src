"""Production Painter UI template, review, prototype, delivery, UMG, and AI Actions."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object
from app.painter_ui_document import UI_INTERACTION_TRIGGERS


def register_paint_ui_production_actions(registry: Any) -> None:
    any_object = {"type": "object", "additionalProperties": True}
    string_array = {"type": "array", "items": {"type": "string"}}
    number_array = {"type": "array", "items": {"type": "number"}}

    def read_action(
        action_id: str,
        description: str,
        method: str,
        params: dict[str, Any],
        *,
        required: tuple[str, ...] = (),
    ) -> None:
        registry.register_adapter_action(
            action_id,
            description,
            "paint",
            method,
            params_schema=schema_object(params, required=required),
            required=required,
            mutating=False,
            changed=False,
            dry_summary=f"{description.rstrip('.')}.",
        )

    def undo_action(
        action_id: str,
        description: str,
        method: str,
        params: dict[str, Any],
        *,
        required: tuple[str, ...] = (),
        undo_label: str,
    ) -> None:
        registry.register_adapter_action(
            action_id,
            description,
            "paint",
            method,
            params_schema=schema_object(params, required=required),
            required=required,
            undo_label=undo_label,
            dry_summary=f"{description.rstrip('.')}.",
        )

    read_action(
        "paint.ui.template.store.inspect",
        "Inspect built-in, installed, favorite, and recent Painter UI templates",
        "paint_ui_template_store_inspect",
        {"store_root": {"type": "string"}},
    )
    read_action(
        "paint.ui.template.package.export",
        "Export the active editable UI document as a licensed .tstemplate package",
        "paint_ui_template_package_export",
        {
            "path": {"type": "string"},
            "template_id": {"type": "string"},
            "name": {"type": "string"},
            "category": {"type": "string"},
            "description": {"type": "string"},
            "tags": string_array,
            "version": {"type": "integer", "minimum": 1},
            "author": {"type": "string"},
            "license_id": {"type": "string"},
        },
        required=("path", "template_id", "name"),
    )
    read_action(
        "paint.ui.template.package.install",
        "Validate and install a .tstemplate package into the local library",
        "paint_ui_template_package_install",
        {"path": {"type": "string"}, "store_root": {"type": "string"}},
        required=("path",),
    )
    read_action(
        "paint.ui.template.user.save",
        "Save the active editable document as a reusable local user template",
        "paint_ui_template_user_save",
        {
            "template_id": {"type": "string"},
            "name": {"type": "string"},
            "store_root": {"type": "string"},
            "category": {"type": "string"},
            "description": {"type": "string"},
            "tags": string_array,
        },
        required=("template_id", "name"),
    )
    read_action(
        "paint.ui.template.favorite.set",
        "Add or remove a Painter UI template from local favorites",
        "paint_ui_template_favorite_set",
        {
            "template_id": {"type": "string"},
            "favorite": {"type": "boolean"},
            "store_root": {"type": "string"},
        },
        required=("template_id", "favorite"),
    )
    undo_action(
        "paint.ui.template.stored.apply",
        "Apply a built-in or installed template as an editable document copy",
        "paint_ui_template_stored_apply",
        {
            "template_id": {"type": "string"},
            "store_root": {"type": "string"},
        },
        required=("template_id",),
        undo_label="Apply stored UI template",
    )
    read_action(
        "paint.ui.template.update.inspect",
        "Compare a template package version and dependencies before update",
        "paint_ui_template_update_inspect",
        {
            "candidate_path": {"type": "string"},
            "current_manifest": any_object,
        },
        required=("candidate_path",),
    )

    read_action(
        "paint.ui.review.inspect",
        "Inspect object-anchored comments and named revision checkpoints",
        "paint_ui_review_inspect",
        {},
    )
    undo_action(
        "paint.ui.review.comment.add",
        "Add a review comment anchored to an object or artboard",
        "paint_ui_review_comment_add",
        {
            "text": {"type": "string"},
            "object_id": {"type": "string"},
            "artboard_id": {"type": "string"},
            "author": {"type": "string"},
            "x": {"type": "number", "minimum": 0, "maximum": 1},
            "y": {"type": "number", "minimum": 0, "maximum": 1},
        },
        required=("text",),
        undo_label="Add UI review comment",
    )
    undo_action(
        "paint.ui.review.comment.update",
        "Edit, resolve, or reply to an object-anchored review comment",
        "paint_ui_review_comment_update",
        {"comment_id": {"type": "string"}, "changes": any_object},
        required=("comment_id", "changes"),
        undo_label="Update UI review comment",
    )
    undo_action(
        "paint.ui.review.comment.remove",
        "Remove a Painter UI review comment",
        "paint_ui_review_comment_remove",
        {"comment_id": {"type": "string"}},
        required=("comment_id",),
        undo_label="Remove UI review comment",
    )
    undo_action(
        "paint.ui.review.checkpoint.create",
        "Create a named, diffable Painter UI revision checkpoint",
        "paint_ui_review_checkpoint_create",
        {"name": {"type": "string"}, "author": {"type": "string"}},
        required=("name",),
        undo_label="Create UI review checkpoint",
    )
    read_action(
        "paint.ui.review.checkpoint.diff",
        "Compare the current document with a named review checkpoint",
        "paint_ui_review_checkpoint_diff",
        {"checkpoint_id": {"type": "string"}},
        required=("checkpoint_id",),
    )
    read_action(
        "paint.ui.review.export",
        "Export an offline review package with comments and developer inspection",
        "paint_ui_review_export",
        {"output_dir": {"type": "string"}},
        required=("output_dir",),
    )
    read_action(
        "paint.ui.developer.inspect",
        "Inspect geometry, tokens, accessibility, resources, and target delivery",
        "paint_ui_developer_inspect",
        {},
    )

    read_action(
        "paint.ui.prototype.inspect",
        "Validate Painter UI prototype triggers and actions",
        "paint_ui_prototype_inspect",
        {},
    )
    read_action(
        "paint.ui.prototype.trigger",
        "Execute one prototype trigger without modifying the design document",
        "paint_ui_prototype_trigger",
        {
            "source_object_id": {"type": "string"},
            "trigger": {
                "type": "string",
                "enum": sorted(UI_INTERACTION_TRIGGERS),
            },
            "state": any_object,
            "key": {"type": "string"},
        },
        required=("source_object_id", "trigger"),
    )
    read_action(
        "paint.ui.prototype.export",
        "Export a self-contained pointer and keyboard review prototype",
        "paint_ui_prototype_export",
        {"output_dir": {"type": "string"}},
        required=("output_dir",),
    )
    read_action(
        "paint.ui.assets.export",
        "Export PNG, WebP, SVG, density variants, 9-slice metadata, and atlas",
        "paint_ui_assets_export",
        {
            "output_dir": {"type": "string"},
            "formats": string_array,
            "densities": number_array,
            "create_atlas": {"type": "boolean"},
            "object_ids": string_array,
            "trim_transparent": {"type": "boolean"},
            "padding": {"type": "integer", "minimum": 0, "maximum": 4096},
        },
        required=("output_dir",),
    )

    read_action(
        "paint.ui.figma.compatibility.inspect",
        "Classify Painter UI objects for editable Figma Plugin export",
        "paint_ui_figma_compatibility_inspect",
        {},
    )
    undo_action(
        "paint.ui.figma.import",
        "Import a Figma URL or REST JSON snapshot as editable Painter UI",
        "paint_ui_figma_import",
        {
            "source": {"type": "string"},
            "mode": {"type": "string", "enum": ["replace", "append"]},
            "json_snapshot": {"type": "boolean"},
        },
        required=("source",),
        undo_label="Import Figma UI",
    )
    read_action(
        "paint.ui.figma.export",
        "Export an editable Figma development-plugin exchange bundle",
        "paint_ui_figma_export",
        {"output_dir": {"type": "string"}},
        required=("output_dir",),
    )

    read_action(
        "paint.ui.umg.preflight",
        "Classify Painter objects for the shared TigerStudioUMG backend",
        "paint_ui_umg_preflight",
        {"artboard_id": {"type": "string"}},
    )
    read_action(
        "paint.ui.umg.package",
        "Package a Painter artboard through the shared TigerStudioUMG contract",
        "paint_ui_umg_package",
        {
            "output_dir": {"type": "string"},
            "artboard_id": {"type": "string"},
        },
        required=("output_dir",),
    )
    read_action(
        "paint.ui.umg.generate",
        "Install the shared plugin and generate a real UE 5.8 Widget Blueprint",
        "paint_ui_umg_generate",
        {
            "project_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "artboard_id": {"type": "string"},
            "destination_root": {"type": "string"},
            "timeout_seconds": {
                "type": "integer",
                "minimum": 30,
                "maximum": 1800,
            },
        },
        required=("project_path", "output_dir"),
    )

    read_action(
        "paint.ui.ai.plan",
        "Plan and preview a prompt-driven editable UI change without applying it",
        "paint_ui_ai_plan",
        {"prompt": {"type": "string"}},
        required=("prompt",),
    )
    undo_action(
        "paint.ui.ai.apply",
        "Apply all or selected operations from an approved AI UI design plan",
        "paint_ui_ai_apply",
        {"plan": any_object, "selected_operation_ids": string_array},
        required=("plan",),
        undo_label="Apply AI UI design plan",
    )
    read_action(
        "paint.ui.ai.audit",
        "Audit accessibility, localization, resource budgets, and delivery targets",
        "paint_ui_ai_audit",
        {},
    )


__all__ = ["register_paint_ui_production_actions"]
