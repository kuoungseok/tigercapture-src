"""Provider-neutral Web/App/UMG delivery inspection for Painter UI."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.painter_ui_document import (
    UI_OBJECT_KINDS,
    normalize_ui_document,
    validate_ui_document,
)


ADVANCED_DELIVERY_SCHEMA = "tigerstudio.painter.ui.advanced_delivery.v1"
ADVANCED_DELIVERY_TARGETS = ("web", "app", "umg")
ADVANCED_DELIVERY_RESULTS = (
    "Native",
    "Vector",
    "Platform Effect",
    "Material",
    "Baked",
    "Actor Only",
    "Blocked",
)
_VECTOR_KINDS = {"path", "polygon", "star", "arc"}
_NATIVE_KINDS = UI_OBJECT_KINDS - _VECTOR_KINDS - {"motion_actor"}


def _has_effect(style: Mapping[str, Any]) -> bool:
    effects = style.get("effects")
    return bool(
        style.get("gradient")
        or style.get("background_blur")
        or style.get("blur")
        or style.get("shadow")
        or (isinstance(effects, list) and effects)
    )


def _classify_object(
    row: Mapping[str, Any],
    target: str,
) -> tuple[str, str]:
    kind = str(row.get("kind") or "")
    style = row.get("style")
    style = style if isinstance(style, Mapping) else {}
    if kind == "motion_actor":
        return (
            "Actor Only",
            "time-varying actor content stays linked to its shared runtime",
        )
    if style.get("paint_layer_id"):
        return (
            "Baked",
            "Painter raster appearance requires a deterministic asset bake",
        )
    if target == "umg":
        from app.painter_ui_delivery import classify_ui_object_delivery

        result = classify_ui_object_delivery(row, "unreal_umg")
        disposition = {
            "native": "Native",
            "material": "Material",
            "baked": "Baked",
            "blocked": "Blocked",
        }[str(result["disposition"])]
        return disposition, str(result["reason"])
    if kind in _VECTOR_KINDS:
        return (
            "Vector",
            (
                "represented by SVG/Canvas vector geometry"
                if target == "web"
                else "represented by the application vector adapter"
            ),
        )
    if kind in _NATIVE_KINDS:
        if _has_effect(style):
            return (
                "Platform Effect",
                (
                    "represented by CSS/SVG visual effects"
                    if target == "web"
                    else "represented by the application effect adapter"
                ),
            )
        return (
            "Native",
            (
                "represented by semantic DOM/CSS"
                if target == "web"
                else "represented by native application widgets"
            ),
        )
    return "Blocked", f"no declared {target} adapter for object kind '{kind}'"


def inspect_advanced_ui_delivery(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    validation = validate_ui_document(document)
    targets: dict[str, dict[str, Any]] = {}
    blockers = list(validation["errors"])
    for target in ADVANCED_DELIVERY_TARGETS:
        features = []
        for row in document["objects"]:
            resolved, reason = _classify_object(row, target)
            features.append(
                {
                    "object_id": str(row["id"]),
                    "object_name": str(row["name"]),
                    "object_kind": str(row["kind"]),
                    "resolved": resolved,
                    "reason": reason,
                }
            )
            if resolved == "Blocked":
                blockers.append(
                    f"{target}:{row['id']}:{reason}"
                )
        counts = Counter(row["resolved"] for row in features)
        target_blockers = [
            row
            for row in features
            if row["resolved"] == "Blocked"
        ]
        targets[target] = {
            "target": target,
            "ok": not target_blockers,
            "counts": {
                result: int(counts.get(result, 0))
                for result in ADVANCED_DELIVERY_RESULTS
            },
            "features": features,
            "blockers": [
                f"{row['object_id']}:{row['reason']}"
                for row in target_blockers
            ],
        }
    prototype = {
        "interaction_count": len(document["interactions"]),
        "preserve": [
            "stable_object_id",
            "accessibility",
            "focus_order",
            "hit_test",
            "localized_text",
        ],
    }
    return {
        "schema": ADVANCED_DELIVERY_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "ok": not blockers,
        "targets": targets,
        "prototype": prototype,
        "blockers": sorted(set(blockers)),
        "warnings": list(validation["warnings"]),
        "claim_scope": "capability_preflight_only",
    }


__all__ = [
    "ADVANCED_DELIVERY_RESULTS",
    "ADVANCED_DELIVERY_SCHEMA",
    "ADVANCED_DELIVERY_TARGETS",
    "inspect_advanced_ui_delivery",
]
