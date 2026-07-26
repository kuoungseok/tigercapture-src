"""Safe Action-driven AI co-design planning, partial apply, and product QA."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_review import diff_ui_documents
from app.painter_ui_templates import instantiate_ui_template, list_ui_templates


AI_DESIGN_PLAN_SCHEMA = "tigerstudio.painter.ui.ai_design_plan.v1"
AI_DESIGN_AUDIT_SCHEMA = "tigerstudio.painter.ui.ai_design_audit.v1"


def _prompt_template_id(prompt: str) -> str:
    text = str(prompt or "").casefold()
    rules = (
        (("checkout", "결제", "구매", "form", "폼"), "accessible_checkout"),
        (("game", "hud", "게임"), "game_hud"),
        (("broadcast", "stream", "방송"), "broadcast_overlay"),
        (("portfolio", "포트폴리오"), "portfolio_case_study"),
        (("shop", "commerce", "상품", "쇼핑"), "commerce_product"),
        (("finance", "금융", "가계부"), "mobile_finance"),
        (("dashboard", "대시보드", "analytics"), "saas_dashboard"),
        (("presentation", "pitch", "발표"), "pitch_deck_cover"),
        (("wireframe", "와이어프레임"), "wireframe_user_flow"),
        (("design system", "디자인 시스템"), "design_system_starter"),
        (("mobile", "모바일", "onboarding", "온보딩"), "mobile_onboarding"),
    )
    for needles, template_id in rules:
        if any(needle in text for needle in needles):
            return template_id
    return "saas_dashboard"


def _plan_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "ui-ai-plan-" + hashlib.sha256(encoded).hexdigest()[:16]


def plan_ui_co_design(
    value: Mapping[str, Any],
    *,
    prompt: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    if not str(prompt or "").strip():
        raise ValueError("AI UI design prompt is required")
    template_id = _prompt_template_id(prompt)
    preview, template_report = instantiate_ui_template(template_id)
    headline = next(
        (
            row
            for row in preview["objects"]
            if row["kind"] == "text"
            and str(row.get("content", {}).get("text") or "").strip()
        ),
        None,
    )
    operations: list[dict[str, Any]] = [
        {
            "id": "apply-template",
            "kind": "replace_document",
            "title": f"Start from {template_report['template']['name']}",
            "template_id": template_id,
            "required": True,
        }
    ]
    if headline is not None:
        requested_title = str(prompt).strip()
        if len(requested_title) > 80:
            requested_title = requested_title[:77].rstrip() + "..."
        headline["content"]["text"] = requested_title
        operations.append(
            {
                "id": "adapt-headline",
                "kind": "update_object",
                "title": "Adapt the primary headline to the request",
                "object_id": headline["id"],
                "changes": {"content": copy.deepcopy(headline["content"])},
                "required": False,
            }
        )
    operations.append(
        {
            "id": "repair-accessibility",
            "kind": "repair_accessibility",
            "title": "Fill missing accessibility labels and focus order",
            "required": False,
        }
    )
    preview = _apply_operations(
        document,
        operations,
        selected_operation_ids=[row["id"] for row in operations],
        template_document=preview,
    )
    seed = {
        "document_id": document["document_id"],
        "source_revision": document["revision"],
        "prompt": str(prompt),
        "template_id": template_id,
        "operations": operations,
    }
    return {
        "schema": AI_DESIGN_PLAN_SCHEMA,
        "plan_id": _plan_id(seed),
        **seed,
        "summary": (
            f"Create an editable {template_report['template']['name']} document, "
            "adapt its primary copy, and repair basic accessibility."
        ),
        "operations": operations,
        "preview_document": preview,
        "preview_diff": diff_ui_documents(document, preview),
        "audit": audit_ui_design(preview),
        "requires_explicit_apply": True,
    }


def _repair_accessibility(document: dict[str, Any]) -> None:
    focus_order = 1
    for row in sorted(
        document["objects"],
        key=lambda item: (item["artboard_id"], item["z_index"], item["id"]),
    ):
        accessibility = dict(row.get("accessibility") or {})
        if row["kind"] in {"button", "image", "text", "progress"}:
            if not str(accessibility.get("label") or "").strip():
                accessibility["label"] = str(
                    row.get("content", {}).get("text") or row["name"]
                )
            if row["kind"] == "button":
                accessibility["role"] = "button"
                if int(accessibility.get("focus_order", 0) or 0) <= 0:
                    accessibility["focus_order"] = focus_order
                    focus_order += 1
        row["accessibility"] = accessibility


def _apply_operations(
    source: Mapping[str, Any],
    operations: list[Mapping[str, Any]],
    *,
    selected_operation_ids: list[str],
    template_document: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected = {str(row) for row in selected_operation_ids}
    document = normalize_ui_document(source)
    for operation in operations:
        if str(operation["id"]) not in selected:
            continue
        kind = str(operation["kind"])
        if kind == "replace_document":
            if template_document is None:
                template_document, _ = instantiate_ui_template(
                    str(operation["template_id"])
                )
            document = normalize_ui_document(template_document)
        elif kind == "update_object":
            object_id = str(operation["object_id"])
            for row in document["objects"]:
                if row["id"] != object_id:
                    continue
                changes = dict(operation.get("changes") or {})
                if "content" in changes:
                    row["content"] = copy.deepcopy(changes["content"])
                if "style" in changes:
                    row["style"] = copy.deepcopy(changes["style"])
                break
        elif kind == "repair_accessibility":
            _repair_accessibility(document)
    document["revision"] = int(document["revision"]) + 1
    return normalize_ui_document(document)


def apply_ui_co_design(
    value: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    selected_operation_ids: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if plan.get("schema") != AI_DESIGN_PLAN_SCHEMA:
        raise ValueError("Unsupported Painter UI AI plan schema")
    if str(plan.get("document_id") or "") != document["document_id"]:
        raise ValueError("AI plan belongs to a different Painter UI document")
    if int(plan.get("source_revision") or 0) != int(document["revision"]):
        raise ValueError("AI plan is stale; regenerate it for the current revision")
    operations = [
        dict(row)
        for row in plan.get("operations", [])
        if isinstance(row, Mapping)
    ]
    selected = (
        [str(row) for row in selected_operation_ids]
        if selected_operation_ids is not None
        else [str(row["id"]) for row in operations]
    )
    required = {
        str(row["id"]) for row in operations if bool(row.get("required"))
    }
    if required and not required.issubset(set(selected)):
        raise ValueError(
            "Required AI operations were not selected: "
            + ", ".join(sorted(required - set(selected)))
        )
    updated = _apply_operations(
        document,
        operations,
        selected_operation_ids=selected,
    )
    return updated, {
        "plan_id": str(plan.get("plan_id") or ""),
        "selected_operation_ids": selected,
        "diff": diff_ui_documents(document, updated),
        "audit": audit_ui_design(updated),
    }


def audit_ui_design(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    issues: list[dict[str, Any]] = []
    focus_by_artboard: dict[str, dict[int, str]] = {}
    total_image_bytes = 0
    for row in document["objects"]:
        accessibility = dict(row.get("accessibility") or {})
        if row["kind"] in {"button", "image"} and not str(
            accessibility.get("label") or ""
        ).strip():
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_accessibility_label",
                    "object_id": row["id"],
                }
            )
        focus_order = int(accessibility.get("focus_order", 0) or 0)
        if focus_order > 0:
            used = focus_by_artboard.setdefault(row["artboard_id"], {})
            if focus_order in used:
                issues.append(
                    {
                        "severity": "error",
                        "code": "duplicate_focus_order",
                        "object_id": row["id"],
                        "other_object_id": used[focus_order],
                    }
                )
            used[focus_order] = row["id"]
        if row["kind"] == "text":
            text = str(row.get("content", {}).get("text") or "")
            if text and not str(
                row.get("content", {}).get("localization_key") or ""
            ):
                issues.append(
                    {
                        "severity": "warning",
                        "code": "hardcoded_text",
                        "object_id": row["id"],
                    }
                )
        if row["kind"] == "image":
            source = Path(
                str(
                    row.get("content", {}).get("source_path")
                    or row.get("content", {}).get("path")
                    or ""
                )
            ).expanduser()
            if source.is_file():
                total_image_bytes += source.stat().st_size
            else:
                issues.append(
                    {
                        "severity": "warning",
                        "code": "missing_image",
                        "object_id": row["id"],
                        "path": str(source),
                    }
                )
    object_count = len(document["objects"])
    if object_count > 1000:
        issues.append(
            {
                "severity": "error",
                "code": "object_budget_exceeded",
                "value": object_count,
                "budget": 1000,
            }
        )
    elif object_count > 500:
        issues.append(
            {
                "severity": "warning",
                "code": "object_budget_warning",
                "value": object_count,
                "budget": 500,
            }
        )
    if total_image_bytes > 64 * 1024 * 1024:
        issues.append(
            {
                "severity": "warning",
                "code": "image_memory_budget_warning",
                "value_bytes": total_image_bytes,
                "budget_bytes": 64 * 1024 * 1024,
            }
        )
    from app.painter_ui_delivery import preflight_ui_delivery

    severity_counts = {
        severity: sum(1 for row in issues if row["severity"] == severity)
        for severity in ("error", "warning", "info")
    }
    return {
        "schema": AI_DESIGN_AUDIT_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "ok": severity_counts["error"] == 0,
        "issues": issues,
        "severity_counts": severity_counts,
        "budgets": {
            "object_count": object_count,
            "image_bytes": total_image_bytes,
        },
        "delivery": {
            target: preflight_ui_delivery(document, target)
            for target in (
                "asset_export",
                "review_prototype",
                "unreal_umg",
            )
        },
        "available_template_ids": [
            row["id"] for row in list_ui_templates()
        ],
    }


__all__ = [
    "AI_DESIGN_AUDIT_SCHEMA",
    "AI_DESIGN_PLAN_SCHEMA",
    "apply_ui_co_design",
    "audit_ui_design",
    "plan_ui_co_design",
]
