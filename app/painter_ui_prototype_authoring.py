"""Prototype connection, transition, and flow authoring services."""
from __future__ import annotations

import copy
from typing import Any, Mapping


UI_PROTOTYPE_TRANSITIONS = (
    "instant",
    "dissolve",
    "move_in",
    "move_out",
    "push",
    "slide",
    "smart_animate",
)
UI_PROTOTYPE_EASINGS = (
    "linear",
    "ease_in",
    "ease_out",
    "ease_in_out",
    "spring",
)


def normalize_ui_prototype_contract(value: object) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    flows = []
    used = set()
    for index, raw in enumerate(source.get("flows") or []):
        if not isinstance(raw, Mapping):
            continue
        flow_id = str(raw.get("id") or f"ui-flow-{index + 1}")
        if flow_id in used:
            continue
        used.add(flow_id)
        flows.append(
            {
                "id": flow_id,
                "name": str(raw.get("name") or f"Flow {index + 1}"),
                "artboard_id": str(raw.get("artboard_id") or ""),
                "start_object_id": str(raw.get("start_object_id") or ""),
                "device_preset": str(raw.get("device_preset") or ""),
                "description": str(raw.get("description") or ""),
            }
        )
    active_flow_id = str(source.get("active_flow_id") or "")
    if active_flow_id not in {row["id"] for row in flows}:
        active_flow_id = flows[0]["id"] if flows else ""
    return {"flows": flows, "active_flow_id": active_flow_id}


def normalize_ui_transition(value: object) -> dict[str, Any]:
    source = value if isinstance(value, Mapping) else {}
    kind = str(source.get("kind") or "instant").strip().casefold()
    easing = str(source.get("easing") or "ease_out").strip().casefold()
    if kind not in UI_PROTOTYPE_TRANSITIONS:
        kind = "instant"
    if easing not in UI_PROTOTYPE_EASINGS:
        easing = "ease_out"
    return {
        "kind": kind,
        "duration_ms": max(0, min(10000, int(source.get("duration_ms") or 0))),
        "easing": easing,
        "direction": str(source.get("direction") or "right").strip().casefold(),
    }


def _prototype(document: dict[str, Any]) -> dict[str, Any]:
    linked = dict(document.get("linked_targets") or {})
    prototype = normalize_ui_prototype_contract(linked.get("prototype"))
    linked["prototype"] = prototype
    document["linked_targets"] = linked
    return prototype


def _next_flow_id(rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"ui-flow-{serial}" in used:
        serial += 1
    return f"ui-flow-{serial}"


def add_ui_prototype_flow(
    value: Mapping[str, Any],
    *,
    name: str,
    artboard_id: str,
    start_object_id: str = "",
    device_preset: str = "",
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    prototype = _prototype(document)
    if artboard_id not in {row["id"] for row in document["artboards"]}:
        raise ValueError(f"UI flow artboard not found: {artboard_id}")
    if start_object_id and start_object_id not in {
        row["id"] for row in document["objects"]
    }:
        raise ValueError(f"UI flow start object not found: {start_object_id}")
    row = {
        "id": _next_flow_id(prototype["flows"]),
        "name": str(name or f"Flow {len(prototype['flows']) + 1}"),
        "artboard_id": str(artboard_id),
        "start_object_id": str(start_object_id),
        "device_preset": str(device_preset),
        "description": str(description),
    }
    prototype["flows"].append(row)
    if not prototype["active_flow_id"]:
        prototype["active_flow_id"] = row["id"]
    document["revision"] += 1
    report = validate_ui_document(document)
    if not report["ok"]:
        raise ValueError("Invalid UI prototype flow: " + ", ".join(report["errors"]))
    return document, copy.deepcopy(row)


def update_ui_prototype_flow(
    value: Mapping[str, Any],
    flow_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    prototype = _prototype(document)
    for index, row in enumerate(prototype["flows"]):
        if row["id"] != str(flow_id):
            continue
        updated = {
            **row,
            **{
                key: str(value)
                for key, value in changes.items()
                if key
                in {
                    "name",
                    "artboard_id",
                    "start_object_id",
                    "device_preset",
                    "description",
                }
            },
            "id": row["id"],
        }
        prototype["flows"][index] = updated
        document["revision"] += 1
        report = validate_ui_document(document)
        if not report["ok"]:
            raise ValueError(
                "Invalid UI prototype flow update: "
                + ", ".join(report["errors"])
            )
        return document, copy.deepcopy(updated)
    raise ValueError(f"UI prototype flow not found: {flow_id}")


def remove_ui_prototype_flow(
    value: Mapping[str, Any],
    flow_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    prototype = _prototype(document)
    removed = next(
        (row for row in prototype["flows"] if row["id"] == str(flow_id)),
        None,
    )
    if removed is None:
        raise ValueError(f"UI prototype flow not found: {flow_id}")
    prototype["flows"] = [
        row for row in prototype["flows"] if row["id"] != str(flow_id)
    ]
    if prototype["active_flow_id"] == str(flow_id):
        prototype["active_flow_id"] = (
            prototype["flows"][0]["id"] if prototype["flows"] else ""
        )
    document["revision"] += 1
    return document, copy.deepcopy(removed)


def set_active_ui_prototype_flow(
    value: Mapping[str, Any],
    flow_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    prototype = _prototype(document)
    row = next(
        (row for row in prototype["flows"] if row["id"] == str(flow_id)),
        None,
    )
    if row is None:
        raise ValueError(f"UI prototype flow not found: {flow_id}")
    prototype["active_flow_id"] = row["id"]
    document["revision"] += 1
    return document, copy.deepcopy(row)


def set_ui_prototype_transition(
    value: Mapping[str, Any],
    interaction_id: str,
    transition: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, update_ui_interaction

    document = normalize_ui_document(value)
    interaction = next(
        (
            row
            for row in document["interactions"]
            if row["id"] == str(interaction_id)
        ),
        None,
    )
    if interaction is None:
        raise ValueError(f"UI interaction not found: {interaction_id}")
    parameters = dict(interaction["parameters"])
    parameters["transition"] = normalize_ui_transition(transition)
    return update_ui_interaction(
        document,
        interaction["id"],
        {"parameters": parameters},
    )


def reorder_ui_prototype_interaction(
    value: Mapping[str, Any],
    interaction_id: str,
    direction: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    current_index = next(
        (
            index
            for index, row in enumerate(document["interactions"])
            if row["id"] == str(interaction_id)
        ),
        -1,
    )
    if current_index < 0:
        raise ValueError(f"UI interaction not found: {interaction_id}")
    target_index = max(
        0,
        min(
            len(document["interactions"]) - 1,
            current_index + (-1 if int(direction) < 0 else 1),
        ),
    )
    if target_index != current_index:
        row = document["interactions"].pop(current_index)
        document["interactions"].insert(target_index, row)
        document["revision"] += 1
    return document, {
        "interaction_id": str(interaction_id),
        "from_index": current_index,
        "to_index": target_index,
    }


def _smart_animate_match_key(row: Mapping[str, Any]) -> str:
    scope_id = str(row.get("component_scope_id") or "")
    source_id = str(row.get("component_scope_source_object_id") or "")
    if scope_id and source_id:
        return f"scope:{scope_id}:{source_id}"
    component_id = str(row.get("component_id") or "")
    component_source_id = str(
        row.get("component_source_object_id") or ""
    )
    if component_id and str(row.get("component_role") or "") in {
        "definition",
        "instance",
    }:
        if component_source_id:
            return f"component:{component_id}:{component_source_id}"
    return ""


def _first_solid_color(
    style: Mapping[str, Any],
    key: str,
) -> str:
    for row in style.get(key) or []:
        if (
            isinstance(row, Mapping)
            and row.get("visible", True)
            and str(row.get("type") or "solid") == "solid"
        ):
            return str(row.get("color") or "")
    return ""


def _smart_animate_properties(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    animated = []
    fallback = []
    if any(
        float(source.get(key) or 0.0) != float(target.get(key) or 0.0)
        for key in ("x", "y", "width", "height", "rotation")
    ):
        animated.append("transform")
    if float(source.get("opacity") or 0.0) != float(
        target.get("opacity") or 0.0
    ):
        animated.append("opacity")
    source_style = dict(source.get("style") or {})
    target_style = dict(target.get("style") or {})
    if _first_solid_color(source_style, "fills") != _first_solid_color(
        target_style,
        "fills",
    ):
        animated.append("fill")
    if _first_solid_color(source_style, "strokes") != _first_solid_color(
        target_style,
        "strokes",
    ):
        animated.append("stroke")
    if dict(source_style.get("corner_radii") or {}) != dict(
        target_style.get("corner_radii") or {}
    ):
        animated.append("corner_radius")
    if str(source.get("kind") or "") != str(target.get("kind") or ""):
        fallback.append("kind_change")
    source_content = dict(source.get("content") or {})
    target_content = dict(target.get("content") or {})
    if str(source_content.get("text") or "") != str(
        target_content.get("text") or ""
    ):
        fallback.append("text_content_crossfade")
    if str(
        source_content.get("source_path")
        or source_content.get("path")
        or ""
    ) != str(
        target_content.get("source_path")
        or target_content.get("path")
        or ""
    ):
        fallback.append("image_content_crossfade")
    if str(source_style.get("blend_mode") or "normal") != str(
        target_style.get("blend_mode") or "normal"
    ):
        fallback.append("blend_mode_discrete")
    return animated, fallback


def inspect_ui_smart_animate(
    document: Mapping[str, Any],
    interaction: Mapping[str, Any],
) -> dict[str, Any]:
    transition = normalize_ui_transition(
        (interaction.get("parameters") or {}).get("transition")
    )
    if transition["kind"] != "smart_animate":
        return {
            "status": "not_applicable",
            "matched_pairs": [],
            "fallback_reasons": [],
        }
    source = next(
        (
            row
            for row in document["objects"]
            if row["id"] == str(interaction.get("source_object_id") or "")
        ),
        None,
    )
    target_artboard_id = str(
        interaction.get("target_artboard_id") or ""
    )
    if source is None:
        return {
            "status": "blocked",
            "matched_pairs": [],
            "fallback_reasons": ["missing_source_object"],
        }
    if target_artboard_id not in {
        row["id"] for row in document["artboards"]
    }:
        return {
            "status": "blocked",
            "matched_pairs": [],
            "fallback_reasons": ["missing_target_artboard"],
        }
    source_rows = [
        row
        for row in document["objects"]
        if row["artboard_id"] == source["artboard_id"]
    ]
    targets_by_key = {
        key: row
        for row in document["objects"]
        if row["artboard_id"] == target_artboard_id
        if (key := _smart_animate_match_key(row))
    }
    matched_pairs = []
    reasons = []
    for row in source_rows:
        key = _smart_animate_match_key(row)
        if not key or key not in targets_by_key:
            continue
        target = targets_by_key[key]
        properties, fallback = _smart_animate_properties(row, target)
        matched_pairs.append(
            {
                "match_key": key,
                "source_object_id": row["id"],
                "target_object_id": target["id"],
                "properties": properties,
                "fallback_properties": fallback,
            }
        )
        reasons.extend(fallback)
    if not matched_pairs:
        reasons.insert(0, "no_stable_component_matches")
    reasons = list(dict.fromkeys(reasons))
    return {
        "status": (
            "fallback"
            if not matched_pairs
            else "partial"
            if reasons
            else "supported"
        ),
        "matched_pairs": matched_pairs,
        "fallback_reasons": reasons,
    }


def inspect_ui_prototype_authoring(
    value: Mapping[str, Any],
    *,
    object_id: str = "",
) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    prototype = normalize_ui_prototype_contract(
        document["linked_targets"].get("prototype")
    )
    interactions = [
        {
            **copy.deepcopy(row),
            "transition": normalize_ui_transition(
                row["parameters"].get("transition")
            ),
            "broken": bool(
                row["source_object_id"]
                and row["source_object_id"]
                not in {item["id"] for item in document["objects"]}
            ),
            "smart_animate": inspect_ui_smart_animate(document, row),
        }
        for row in document["interactions"]
        if not object_id or row["source_object_id"] == str(object_id)
    ]
    return {
        "schema": "tigerstudio.painter.ui.prototype_authoring.inspect.v1",
        "object_id": str(object_id),
        "flows": prototype["flows"],
        "active_flow_id": prototype["active_flow_id"],
        "interactions": interactions,
        "interaction_count": len(interactions),
        "broken_interaction_ids": [
            row["id"] for row in interactions if row["broken"]
        ],
    }


__all__ = [
    "UI_PROTOTYPE_EASINGS",
    "UI_PROTOTYPE_TRANSITIONS",
    "add_ui_prototype_flow",
    "inspect_ui_prototype_authoring",
    "inspect_ui_smart_animate",
    "normalize_ui_prototype_contract",
    "normalize_ui_transition",
    "reorder_ui_prototype_interaction",
    "remove_ui_prototype_flow",
    "set_active_ui_prototype_flow",
    "set_ui_prototype_transition",
    "update_ui_prototype_flow",
]
