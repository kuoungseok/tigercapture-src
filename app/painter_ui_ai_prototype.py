"""Review-first AI prototype planning built on canonical Painter UI services."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.painter_ui_ai_design import (
    apply_ui_co_design,
    audit_ui_design,
    plan_ui_co_design,
)
from app.painter_ui_advanced_delivery import inspect_advanced_ui_delivery
from app.painter_ui_document import (
    add_ui_interaction,
    normalize_ui_document,
)
from app.painter_ui_prototype import inspect_ui_prototype
from app.painter_ui_review import diff_ui_documents


AI_PROTOTYPE_PLAN_SCHEMA = "tigerstudio.painter.ui.ai_prototype_plan.v1"
AI_PROTOTYPE_APPLY_SCHEMA = "tigerstudio.painter.ui.ai_prototype_apply.v1"


def _plan_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "ui-ai-prototype-" + hashlib.sha256(encoded).hexdigest()[:16]


def _interaction_specs(
    value: Mapping[str, Any],
) -> list[dict[str, Any]]:
    document = normalize_ui_document(value)
    artboard_ids = [str(row["id"]) for row in document["artboards"]]
    artboard_index = {
        artboard_id: index
        for index, artboard_id in enumerate(artboard_ids)
    }
    existing = {
        (
            str(row["source_object_id"]),
            str(row["trigger"]),
            str(row["action"]),
            str(row["target_artboard_id"]),
            str(row["target_object_id"]),
        )
        for row in document["interactions"]
    }
    specs: list[dict[str, Any]] = []
    for row in document["objects"]:
        if row["kind"] != "button" or not row["visible"] or row["locked"]:
            continue
        source_id = str(row["id"])
        hover_key = (source_id, "hover", "change_state", "", source_id)
        if hover_key not in existing:
            specs.append(
                {
                    "name": f"{row['name']} Hover",
                    "source_object_id": source_id,
                    "trigger": "hover",
                    "action": "change_state",
                    "target_object_id": source_id,
                    "parameters": {"state": "hover"},
                }
            )
        current_index = artboard_index.get(str(row["artboard_id"]), 0)
        if len(artboard_ids) > 1:
            target_artboard_id = artboard_ids[
                min(current_index + 1, len(artboard_ids) - 1)
            ]
            click_key = (
                source_id,
                "click",
                "navigate",
                target_artboard_id,
                "",
            )
            if click_key not in existing:
                specs.append(
                    {
                        "name": f"{row['name']} Navigate",
                        "source_object_id": source_id,
                        "trigger": "click",
                        "action": "navigate",
                        "target_artboard_id": target_artboard_id,
                        "parameters": {"transition": "instant"},
                    }
                )
        else:
            click_key = (
                source_id,
                "click",
                "change_state",
                "",
                source_id,
            )
            if click_key not in existing:
                specs.append(
                    {
                        "name": f"{row['name']} Pressed",
                        "source_object_id": source_id,
                        "trigger": "click",
                        "action": "change_state",
                        "target_object_id": source_id,
                        "parameters": {"state": "pressed"},
                    }
                )
    return specs


def _apply_interaction_specs(
    value: Mapping[str, Any],
    specs: list[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    document = normalize_ui_document(value)
    object_ids = {str(row["id"]) for row in document["objects"]}
    added_ids: list[str] = []
    for spec in specs:
        source_id = str(spec.get("source_object_id") or "")
        if source_id not in object_ids:
            raise ValueError(
                f"AI prototype source object is missing: {source_id}"
            )
        document, interaction = add_ui_interaction(
            document,
            name=str(spec.get("name") or "AI Prototype Interaction"),
            source_object_id=source_id,
            trigger=str(spec.get("trigger") or "click"),
            action=str(spec.get("action") or "change_state"),
            target_artboard_id=str(spec.get("target_artboard_id") or ""),
            target_object_id=str(spec.get("target_object_id") or ""),
            parameters=dict(spec.get("parameters") or {}),
        )
        added_ids.append(str(interaction["id"]))
    return document, added_ids


def plan_ui_prototype_build(
    value: Mapping[str, Any],
    *,
    prompt: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    design_plan = plan_ui_co_design(document, prompt=prompt)
    preview = normalize_ui_document(design_plan["preview_document"])
    interaction_specs = _interaction_specs(preview)
    preview, interaction_ids = _apply_interaction_specs(
        preview,
        interaction_specs,
    )
    prototype = inspect_ui_prototype(preview)
    audit = audit_ui_design(preview)
    delivery = inspect_advanced_ui_delivery(preview)
    operations = [
        {
            "id": "build-editable-ui",
            "kind": "apply_design_plan",
            "title": "Build editable UI structure",
            "required": True,
        },
        {
            "id": "wire-prototype",
            "kind": "add_interactions",
            "title": (
                f"Add {len(interaction_specs)} bounded prototype interactions"
            ),
            "required": False,
            "enabled": bool(interaction_specs),
        },
    ]
    seed = {
        "document_id": document["document_id"],
        "source_revision": document["revision"],
        "prompt": str(prompt),
        "design_plan_id": design_plan["plan_id"],
        "interaction_specs": interaction_specs,
    }
    return {
        "schema": AI_PROTOTYPE_PLAN_SCHEMA,
        "plan_id": _plan_id(seed),
        **seed,
        "summary": (
            f"{design_plan['summary']} Add reviewable Hover/Click behavior "
            "without creating a second prototype runtime."
        ),
        "operations": operations,
        "design_plan": design_plan,
        "preview_document": preview,
        "preview_diff": diff_ui_documents(document, preview),
        "prototype": prototype,
        "delivery": delivery,
        "audit": audit,
        "preview_interaction_ids": interaction_ids,
        "requires_explicit_apply": True,
    }


def apply_ui_prototype_build(
    value: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    selected_operation_ids: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if plan.get("schema") != AI_PROTOTYPE_PLAN_SCHEMA:
        raise ValueError("Unsupported Painter UI AI prototype plan schema")
    if str(plan.get("document_id") or "") != document["document_id"]:
        raise ValueError("AI prototype plan belongs to a different document")
    if int(plan.get("source_revision") or 0) != int(document["revision"]):
        raise ValueError(
            "AI prototype plan is stale; regenerate it for this revision"
        )
    selected = set(
        str(row)
        for row in (
            selected_operation_ids
            if selected_operation_ids is not None
            else ("build-editable-ui", "wire-prototype")
        )
    )
    if "build-editable-ui" not in selected:
        raise ValueError("build-editable-ui is required")
    updated, design_report = apply_ui_co_design(
        document,
        dict(plan.get("design_plan") or {}),
    )
    added_ids: list[str] = []
    if "wire-prototype" in selected:
        specs = [
            dict(row)
            for row in plan.get("interaction_specs", [])
            if isinstance(row, Mapping)
        ]
        updated, added_ids = _apply_interaction_specs(updated, specs)
    prototype = inspect_ui_prototype(updated)
    audit = audit_ui_design(updated)
    delivery = inspect_advanced_ui_delivery(updated)
    return updated, {
        "schema": AI_PROTOTYPE_APPLY_SCHEMA,
        "plan_id": str(plan.get("plan_id") or ""),
        "selected_operation_ids": sorted(selected),
        "added_interaction_ids": added_ids,
        "design_apply": design_report,
        "diff": diff_ui_documents(document, updated),
        "prototype": prototype,
        "delivery": delivery,
        "audit": audit,
    }


__all__ = [
    "AI_PROTOTYPE_APPLY_SCHEMA",
    "AI_PROTOTYPE_PLAN_SCHEMA",
    "apply_ui_prototype_build",
    "plan_ui_prototype_build",
]
