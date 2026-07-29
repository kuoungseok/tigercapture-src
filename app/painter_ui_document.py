"""Provider-neutral document model for Painter's general UI Designer."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_auto_layout import normalize_ui_auto_layout


UI_DOCUMENT_SCHEMA = "tigerstudio.painter.ui.v1"
UI_DOCUMENT_VERSION = 18
UI_OBJECT_KINDS = {
    "frame",
    "group",
    "rectangle",
    "ellipse",
    "line",
    "polygon",
    "star",
    "arc",
    "path",
    "text",
    "image",
    "motion_actor",
    "button",
    "progress",
}
UI_DELIVERY_TARGETS = (
    "asset_export",
    "design_handoff",
    "review_prototype",
    "unreal_umg",
)
UI_ACCESSIBILITY_ROLES = {
    "auto",
    "none",
    "button",
    "checkbox",
    "heading",
    "image",
    "link",
    "progress",
    "slider",
    "text",
}
UI_TOKEN_KINDS = {
    "color",
    "typography",
    "spacing",
    "radius",
    "border",
    "shadow",
    "opacity",
    "icon",
    "image",
}
UI_INTERACTION_TRIGGERS = {
    "click",
    "double_click",
    "hover",
    "press",
    "focus",
    "keyboard",
}
UI_INTERACTION_ACTIONS = {
    "navigate",
    "back",
    "open_overlay",
    "close_overlay",
    "change_state",
    "play_animation",
    "play_sound",
    "set_visibility",
    "set_opacity",
    "set_material_scalar",
}


class PainterUIDocumentError(ValueError):
    pass


def _positive(value: Any, default: float) -> float:
    try:
        return max(1.0, float(value))
    except (TypeError, ValueError):
        return float(default)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_accessibility(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    role = str(row.get("role") or "auto").strip().casefold()
    if role not in UI_ACCESSIBILITY_ROLES:
        role = "auto"
    try:
        focus_order = max(0, int(row.get("focus_order") or 0))
    except (TypeError, ValueError):
        focus_order = 0
    return {
        "role": role,
        "label": str(row.get("label") or "").strip(),
        "focus_order": focus_order,
    }


def _next_id(prefix: str, rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    return f"{prefix}-{serial}"


def _default_delivery_profiles() -> list[dict[str, Any]]:
    return [
        {"id": target, "target": target, "enabled": True, "settings": {}}
        for target in UI_DELIVERY_TARGETS
    ]


def create_ui_document(
    width: int = 1920,
    height: int = 1080,
    *,
    name: str = "Main",
) -> dict[str, Any]:
    artboard_id = "artboard-1"
    return {
        "schema": UI_DOCUMENT_SCHEMA,
        "version": UI_DOCUMENT_VERSION,
        "document_id": "ui-document-1",
        "revision": 0,
        "active_artboard_id": artboard_id,
        "selection": {"object_id": "", "object_ids": []},
        "artboards": [
            {
                "id": artboard_id,
                "name": str(name or "Main"),
                "width": max(1, int(width)),
                "height": max(1, int(height)),
                "x": 0.0,
                "y": 0.0,
                "background": "#FFFFFF",
                "breakpoint": "custom",
                "orientation": "landscape" if width >= height else "portrait",
                "theme": "light",
                "layout_grid_style_id": "",
                "safe_area": {"left": 0, "top": 0, "right": 0, "bottom": 0},
                "safe_area_visible": False,
                "layout_grid": {
                    "id": "layout-grid-1",
                    "name": "None",
                    "mode": "none",
                    "visible": False,
                    "size": 8.0,
                    "count": 12,
                    "gutter": 20.0,
                    "margin": 24.0,
                    "alignment": "stretch",
                    "color": "#4C9AFF32",
                },
                "layout_grids": [
                    {
                        "id": "layout-grid-1",
                        "name": "None",
                        "mode": "none",
                        "visible": False,
                        "size": 8.0,
                        "count": 12,
                        "gutter": 20.0,
                        "margin": 24.0,
                        "alignment": "stretch",
                        "color": "#4C9AFF32",
                    }
                ],
                "guides": {
                    "visible": True,
                    "locked": False,
                    "origin": {"x": 0.0, "y": 0.0},
                    "vertical": [],
                    "horizontal": [],
                },
            }
        ],
        "objects": [],
        "components": [],
        "tokens": [],
        "interactions": [],
        "sections": [],
        "layout_grid_styles": [],
        "delivery_profiles": _default_delivery_profiles(),
        "linked_targets": {},
    }


def _normalize_artboard(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    width = _positive(row.get("width"), 1920.0)
    height = _positive(row.get("height"), 1080.0)
    from app.painter_ui_artboard_layout import normalize_ui_artboard_layout
    from app.painter_ui_themes import normalize_ui_theme

    layout = normalize_ui_artboard_layout(row, width=width, height=height)
    return {
        "id": str(row.get("id") or f"artboard-{index + 1}"),
        "name": str(row.get("name") or f"Artboard {index + 1}"),
        "width": int(round(width)),
        "height": int(round(height)),
        "x": _number(row.get("x")),
        "y": _number(row.get("y")),
        "background": str(row.get("background") or "#FFFFFF"),
        "breakpoint": str(row.get("breakpoint") or "custom"),
        "orientation": str(
            row.get("orientation")
            or ("landscape" if width >= height else "portrait")
        ),
        "theme": normalize_ui_theme(row.get("theme"), "light"),
        "layout_grid_style_id": str(row.get("layout_grid_style_id") or ""),
        **layout,
    }


def _normalize_object(
    row: Mapping[str, Any],
    index: int,
    default_artboard_id: str,
) -> dict[str, Any]:
    kind = str(row.get("kind") or "rectangle").strip().casefold()
    object_id = str(row.get("id") or f"ui-object-{index + 1}")
    style = row.get("style")
    content = row.get("content")
    constraints = row.get("constraints")
    layout = row.get("layout")
    token_bindings = row.get("token_bindings")
    from app.painter_ui_responsive import normalize_ui_responsive_overrides
    from app.painter_ui_components import (
        normalize_ui_component_property_bindings,
        normalize_ui_component_properties,
        normalize_ui_component_role,
        normalize_ui_instance_overrides,
    )
    from app.painter_ui_advanced_appearance import normalize_ui_advanced_style
    from app.painter_ui_boolean import normalize_ui_boolean
    from app.painter_ui_masks import normalize_ui_mask
    from app.painter_ui_remote_components import normalize_remote_component
    from app.painter_ui_text_ranges import normalize_ui_text_ranges

    normalized_style = normalize_ui_advanced_style(style)
    normalized_content = (
        copy.deepcopy(dict(content)) if isinstance(content, Mapping) else {}
    )
    from app.painter_ui_parametric_shapes import (
        normalize_parametric_shape_content,
    )

    normalized_content = normalize_parametric_shape_content(
        kind,
        normalized_content,
    )
    if kind == "path":
        from app.painter_ui_vector_network import normalize_vector_content

        normalized_content = normalize_vector_content(normalized_content)
    normalized_content["text_ranges"] = normalize_ui_text_ranges(
        normalized_content.get("text_ranges"),
        str(normalized_content.get("text") or ""),
    )
    normalized_content["boolean"] = normalize_ui_boolean(
        normalized_content.get("boolean")
    )
    if isinstance(normalized_content.get("remote_component"), Mapping):
        normalized_content["remote_component"] = normalize_remote_component(
            normalized_content["remote_component"]
        )

    return {
        "id": object_id,
        "kind": kind,
        "name": str(row.get("name") or kind.replace("_", " ").title()),
        "artboard_id": str(row.get("artboard_id") or default_artboard_id),
        "parent_id": str(row.get("parent_id") or ""),
        "x": _number(row.get("x")),
        "y": _number(row.get("y")),
        "width": _positive(row.get("width"), 160.0),
        "height": _positive(row.get("height"), 64.0),
        "rotation": _number(row.get("rotation")),
        "opacity": max(0.0, min(1.0, _number(row.get("opacity"), 1.0))),
        "visible": bool(row.get("visible", True)),
        "locked": bool(row.get("locked", False)),
        "clip_content": bool(row.get("clip_content", False)),
        "z_index": int(_number(row.get("z_index"), index)),
        "style": normalized_style,
        "content": normalized_content,
        "mask": normalize_ui_mask(row.get("mask")),
        "constraints": (
            copy.deepcopy(dict(constraints))
            if isinstance(constraints, Mapping)
            else {"horizontal": "left", "vertical": "top"}
        ),
        "layout": normalize_ui_auto_layout(
            dict(layout) if isinstance(layout, Mapping) else {}
        ),
        "component_id": str(row.get("component_id") or ""),
        "component_role": normalize_ui_component_role(row.get("component_role")),
        "component_source_object_id": str(
            row.get("component_source_object_id") or ""
        ),
        "instance_overrides": normalize_ui_instance_overrides(
            row.get("instance_overrides")
        ),
        "component_properties": normalize_ui_component_properties(
            row.get("component_properties")
        ),
        "component_property_bindings": normalize_ui_component_property_bindings(
            row.get("component_property_bindings")
        ),
        "component_scope_id": str(row.get("component_scope_id") or ""),
        "component_scope_source_object_id": str(
            row.get("component_scope_source_object_id") or ""
        ),
        "variant": str(row.get("variant") or ""),
        "token_bindings": (
            {
                str(key): str(token_id or "")
                for key, token_id in token_bindings.items()
                if str(key)
            }
            if isinstance(token_bindings, Mapping)
            else {}
        ),
        "accessibility": _normalize_accessibility(row.get("accessibility")),
        "responsive_overrides": normalize_ui_responsive_overrides(
            row.get("responsive_overrides"),
            object_id=object_id,
        ),
    }


def _normalize_component(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    from app.painter_ui_components import (
        normalize_ui_component_property_definitions,
        normalize_ui_component_state_overrides,
    )

    return {
        "id": str(row.get("id") or f"ui-component-{index + 1}"),
        "name": str(row.get("name") or f"Component {index + 1}"),
        "root_object_id": str(row.get("root_object_id") or ""),
        "base_component_id": str(row.get("base_component_id") or ""),
        "description": str(row.get("description") or ""),
        "property_definitions": normalize_ui_component_property_definitions(
            row.get("property_definitions")
        ),
        "state_overrides": normalize_ui_component_state_overrides(
            row.get("state_overrides")
        ),
        "variant_ids": [
            str(value)
            for value in row.get("variant_ids", [])
            if str(value or "")
        ],
        "metadata": copy.deepcopy(
            dict(row.get("metadata"))
            if isinstance(row.get("metadata"), Mapping)
            else {}
        ),
    }


def _normalize_token(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    kind = str(row.get("kind") or "color").strip().casefold()
    from app.painter_ui_themes import normalize_ui_theme_values

    return {
        "id": str(row.get("id") or f"ui-token-{index + 1}"),
        "name": str(row.get("name") or f"Token {index + 1}"),
        "kind": kind,
        "value": copy.deepcopy(row.get("value")),
        "theme_values": normalize_ui_theme_values(row.get("theme_values")),
        "alias_token_id": str(row.get("alias_token_id") or ""),
        "description": str(row.get("description") or ""),
    }


def _normalize_interaction(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    parameters = row.get("parameters")
    return {
        "id": str(row.get("id") or f"ui-interaction-{index + 1}"),
        "name": str(row.get("name") or f"Interaction {index + 1}"),
        "source_object_id": str(row.get("source_object_id") or ""),
        "trigger": str(row.get("trigger") or "click").strip().casefold(),
        "action": str(row.get("action") or "navigate").strip().casefold(),
        "target_artboard_id": str(row.get("target_artboard_id") or ""),
        "target_object_id": str(row.get("target_object_id") or ""),
        "component_id": str(row.get("component_id") or ""),
        "motion_clip_id": str(row.get("motion_clip_id") or ""),
        "parameters": (
            copy.deepcopy(dict(parameters)) if isinstance(parameters, Mapping) else {}
        ),
        "enabled": bool(row.get("enabled", True)),
    }


def _normalize_typed_rows(
    rows: Any,
    *,
    prefix: str,
    normalizer: Any,
) -> list[dict[str, Any]]:
    raw_rows = [row for row in (rows or []) if isinstance(row, Mapping)]
    reserved = {str(row.get("id") or "") for row in raw_rows if row.get("id")}
    normalized: list[dict[str, Any]] = []
    next_serial = 1
    for index, row in enumerate(raw_rows):
        item = normalizer(row, index)
        if not row.get("id"):
            while (
                f"{prefix}-{next_serial}" in reserved
                or f"{prefix}-{next_serial}"
                in {existing["id"] for existing in normalized}
            ):
                next_serial += 1
            item["id"] = f"{prefix}-{next_serial}"
            next_serial += 1
        normalized.append(item)
    return normalized


def normalize_ui_document(
    value: Mapping[str, Any] | None,
    *,
    fallback_width: int = 1920,
    fallback_height: int = 1080,
) -> dict[str, Any]:
    raw = copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}
    raw_artboards = [
        row for row in raw.get("artboards", []) if isinstance(row, Mapping)
    ]
    if not raw_artboards:
        raw_artboards = create_ui_document(
            fallback_width,
            fallback_height,
        )["artboards"]
    artboards = [
        _normalize_artboard(row, index) for index, row in enumerate(raw_artboards)
    ]
    active_artboard_id = str(raw.get("active_artboard_id") or artboards[0]["id"])
    if active_artboard_id not in {row["id"] for row in artboards}:
        active_artboard_id = artboards[0]["id"]
    raw_objects = [
        row for row in raw.get("objects", []) if isinstance(row, Mapping)
    ]
    objects = [
        _normalize_object(row, index, active_artboard_id)
        for index, row in enumerate(raw_objects)
    ]
    components = _normalize_typed_rows(
        raw.get("components"),
        prefix="ui-component",
        normalizer=_normalize_component,
    )
    tokens = _normalize_typed_rows(
        raw.get("tokens"),
        prefix="ui-token",
        normalizer=_normalize_token,
    )
    interactions = _normalize_typed_rows(
        raw.get("interactions"),
        prefix="ui-interaction",
        normalizer=_normalize_interaction,
    )
    from app.painter_ui_sections import normalize_ui_section

    sections = _normalize_typed_rows(
        raw.get("sections"),
        prefix="ui-section",
        normalizer=normalize_ui_section,
    )
    from app.painter_ui_layout_grid_styles import normalize_ui_layout_grid_style

    layout_grid_styles = _normalize_typed_rows(
        raw.get("layout_grid_styles"),
        prefix="ui-layout-grid-style",
        normalizer=normalize_ui_layout_grid_style,
    )
    selection = raw.get("selection")
    selection = selection if isinstance(selection, Mapping) else {}
    selected_id = str(selection.get("object_id") or "")
    object_by_id = {row["id"]: row for row in objects}
    raw_selected_ids = selection.get("object_ids")
    if not isinstance(raw_selected_ids, list):
        raw_selected_ids = [selected_id] if selected_id else []
    selected_ids: list[str] = []
    for value in raw_selected_ids:
        candidate = str(value or "")
        row = object_by_id.get(candidate)
        if (
            candidate
            and row is not None
            and row["artboard_id"] == active_artboard_id
            and candidate not in selected_ids
        ):
            selected_ids.append(candidate)
    selected_row = object_by_id.get(selected_id)
    if (
        selected_row is None
        or selected_row["artboard_id"] != active_artboard_id
    ):
        selected_id = ""
    if selected_id and selected_id not in selected_ids:
        selected_ids.append(selected_id)
    if not selected_id and selected_ids:
        selected_id = selected_ids[-1]
    profiles = [
        copy.deepcopy(dict(row))
        for row in raw.get("delivery_profiles", [])
        if isinstance(row, Mapping)
    ]
    known_targets = {str(row.get("target") or "") for row in profiles}
    profiles.extend(
        row
        for row in _default_delivery_profiles()
        if row["target"] not in known_targets
    )
    return {
        "schema": UI_DOCUMENT_SCHEMA,
        "version": UI_DOCUMENT_VERSION,
        "document_id": str(raw.get("document_id") or "ui-document-1"),
        "revision": max(0, int(_number(raw.get("revision"), 0))),
        "active_artboard_id": active_artboard_id,
        "selection": {
            "object_id": selected_id,
            "object_ids": selected_ids,
        },
        "artboards": artboards,
        "objects": objects,
        "components": components,
        "tokens": tokens,
        "interactions": interactions,
        "sections": sections,
        "layout_grid_styles": layout_grid_styles,
        "delivery_profiles": profiles,
        "linked_targets": copy.deepcopy(dict(raw.get("linked_targets") or {})),
    }


def migrate_ui_document(
    value: Mapping[str, Any] | None,
    *,
    fallback_width: int = 1920,
    fallback_height: int = 1080,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_version = (
        max(1, int(_number(value.get("version"), 1)))
        if isinstance(value, Mapping)
        else 1
    )
    document = normalize_ui_document(
        value,
        fallback_width=fallback_width,
        fallback_height=fallback_height,
    )
    return document, {
        "schema": "tigerstudio.painter.ui.migration.v1",
        "from_version": source_version,
        "to_version": UI_DOCUMENT_VERSION,
        "changed": source_version != UI_DOCUMENT_VERSION,
    }


def _append_cycle_errors(
    rows: list[Mapping[str, Any]],
    *,
    reference_key: str,
    error_prefix: str,
    errors: list[str],
) -> None:
    by_id = {str(row.get("id") or ""): row for row in rows}
    for row_id in by_id:
        seen: set[str] = set()
        current = by_id.get(row_id)
        while current:
            referenced = str(current.get(reference_key) or "")
            if not referenced:
                break
            if referenced in seen or referenced == row_id:
                errors.append(f"{error_prefix}:{row_id}")
                break
            seen.add(referenced)
            current = by_id.get(referenced)


def validate_ui_document(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    errors: list[str] = []
    warnings: list[str] = []
    artboard_ids = [row["id"] for row in document["artboards"]]
    object_ids = [row["id"] for row in document["objects"]]
    component_ids = [row["id"] for row in document["components"]]
    token_ids = [row["id"] for row in document["tokens"]]
    interaction_ids = [row["id"] for row in document["interactions"]]
    section_ids = [row["id"] for row in document["sections"]]
    layout_grid_style_ids = [
        row["id"] for row in document["layout_grid_styles"]
    ]
    responsive_override_ids = [
        override["id"]
        for row in document["objects"]
        for override in row["responsive_overrides"]
    ]
    if len(set(artboard_ids)) != len(artboard_ids):
        errors.append("duplicate_artboard_id")
    if len(set(object_ids)) != len(object_ids):
        errors.append("duplicate_object_id")
    if len(set(component_ids)) != len(component_ids):
        errors.append("duplicate_component_id")
    if len(set(token_ids)) != len(token_ids):
        errors.append("duplicate_token_id")
    if len(set(interaction_ids)) != len(interaction_ids):
        errors.append("duplicate_interaction_id")
    if len(set(section_ids)) != len(section_ids):
        errors.append("duplicate_section_id")
    if len(set(layout_grid_style_ids)) != len(layout_grid_style_ids):
        errors.append("duplicate_layout_grid_style_id")
    if len(set(responsive_override_ids)) != len(responsive_override_ids):
        errors.append("duplicate_responsive_override_id")
    all_ids = (
        artboard_ids
        + object_ids
        + component_ids
        + token_ids
        + interaction_ids
        + section_ids
        + layout_grid_style_ids
        + responsive_override_ids
    )
    if len(set(all_ids)) != len(all_ids):
        errors.append("duplicate_stable_id")
    object_by_id = {row["id"]: row for row in document["objects"]}
    artboard_id_set = set(artboard_ids)
    component_id_set = set(component_ids)
    component_by_id = {row["id"]: row for row in document["components"]}
    token_id_set = set(token_ids)
    layout_grid_style_id_set = set(layout_grid_style_ids)
    for artboard in document["artboards"]:
        style_id = artboard.get("layout_grid_style_id")
        if style_id and style_id not in layout_grid_style_id_set:
            errors.append(
                f"missing_layout_grid_style:{artboard['id']}:{style_id}"
            )
    focus_orders: dict[tuple[str, int], str] = {}
    for row in document["objects"]:
        if row["kind"] not in UI_OBJECT_KINDS:
            errors.append(f"unsupported_object_kind:{row['id']}:{row['kind']}")
        if row["artboard_id"] not in artboard_id_set:
            errors.append(f"missing_artboard:{row['id']}:{row['artboard_id']}")
        parent_id = row["parent_id"]
        if parent_id and parent_id not in object_by_id:
            errors.append(f"missing_parent:{row['id']}:{parent_id}")
        if (
            parent_id
            and parent_id in object_by_id
            and object_by_id[parent_id]["artboard_id"] != row["artboard_id"]
        ):
            errors.append(f"parent_artboard_mismatch:{row['id']}:{parent_id}")
        if parent_id == row["id"]:
            errors.append(f"self_parent:{row['id']}")
        mask = row["mask"]
        for target_id in mask["target_ids"]:
            target = object_by_id.get(target_id)
            if target is None:
                errors.append(f"missing_mask_target:{row['id']}:{target_id}")
            elif target["artboard_id"] != row["artboard_id"]:
                errors.append(
                    f"mask_target_artboard_mismatch:{row['id']}:{target_id}"
                )
            elif target["parent_id"] != row["parent_id"]:
                errors.append(
                    f"mask_target_parent_mismatch:{row['id']}:{target_id}"
                )
        component_id = row["component_id"]
        if component_id and component_id not in component_id_set:
            errors.append(f"missing_component:{row['id']}:{component_id}")
        component_scope_id = row["component_scope_id"]
        component_scope_source_id = row["component_scope_source_object_id"]
        if component_scope_id and component_scope_id not in component_id_set:
            errors.append(
                f"missing_component_scope:{row['id']}:{component_scope_id}"
            )
        scope_parent = object_by_id.get(row["parent_id"])
        if (
            component_scope_id
            and not component_scope_source_id
            and (
                scope_parent is None
                or scope_parent["component_scope_id"] != component_scope_id
            )
        ):
            errors.append(f"missing_component_scope_source:{row['id']}")
        if (
            component_scope_source_id
            and component_scope_source_id not in object_by_id
        ):
            errors.append(
                f"missing_component_scope_source:{row['id']}:"
                f"{component_scope_source_id}"
            )
        if component_scope_source_id and not component_scope_id:
            errors.append(f"missing_component_scope_owner:{row['id']}")
        if component_scope_id and component_scope_id == component_id:
            errors.append(f"redundant_component_scope:{row['id']}")
        component_role = row["component_role"]
        source_object_id = row["component_source_object_id"]
        if component_role != "none" and not component_id:
            errors.append(f"missing_component_role_owner:{row['id']}")
        if component_role == "definition" and source_object_id != row["id"]:
            errors.append(f"invalid_component_definition_source:{row['id']}")
        if component_role == "instance":
            source = object_by_id.get(source_object_id)
            if source is None:
                errors.append(
                    f"missing_component_instance_source:{row['id']}:{source_object_id}"
                )
            elif (
                source["component_role"] != "definition"
                or source["component_id"] != component_id
            ):
                errors.append(
                    f"invalid_component_instance_source:{row['id']}:{source_object_id}"
                )
            component = component_by_id.get(component_id)
            if component is not None:
                definitions = component["property_definitions"]
                for property_name, property_value in row[
                    "component_properties"
                ].items():
                    definition = definitions.get(property_name)
                    if definition is None:
                        errors.append(
                            f"missing_component_property:{row['id']}:{property_name}"
                        )
                    elif (
                        definition["type"] == "enum"
                        and definition["values"]
                        and str(property_value) not in definition["values"]
                    ):
                        errors.append(
                            f"invalid_component_property_value:{row['id']}:"
                            f"{property_name}:{property_value}"
                        )
        for target_path, property_name in row[
            "component_property_bindings"
        ].items():
            owner_component_id = (
                component_id if component_role == "definition" else ""
            )
            parent = object_by_id.get(row["parent_id"])
            while not owner_component_id and parent is not None:
                if parent["component_role"] == "definition":
                    owner_component_id = parent["component_id"]
                    break
                parent = object_by_id.get(parent["parent_id"])
            owner_component = component_by_id.get(owner_component_id)
            if owner_component is None:
                errors.append(
                    f"component_property_binding_outside_definition:"
                    f"{row['id']}:{target_path}"
                )
                continue
            if row["id"] == owner_component["root_object_id"]:
                errors.append(
                    f"component_property_binding_on_root:"
                    f"{row['id']}:{target_path}"
                )
            definition = owner_component["property_definitions"].get(
                property_name
            )
            if definition is None:
                errors.append(
                    f"missing_component_property_binding:"
                    f"{row['id']}:{property_name}"
                )
                continue
            expected_type = {
                "content.text": "text",
                "visible": "boolean",
                "component_id": "instance_swap",
            }.get(target_path)
            if expected_type is None:
                errors.append(
                    f"unsupported_component_property_binding:"
                    f"{row['id']}:{target_path}"
                )
            elif definition["type"] != expected_type:
                errors.append(
                    f"component_property_binding_type_mismatch:"
                    f"{row['id']}:{target_path}:{definition['type']}"
                )
            elif target_path == "content.text" and row["kind"] != "text":
                errors.append(
                    f"component_text_binding_requires_text:{row['id']}"
                )
            elif (
                target_path == "component_id"
                and component_role != "instance"
            ):
                errors.append(
                    f"component_swap_binding_requires_instance:{row['id']}"
                )
        for property_name, token_id in row["token_bindings"].items():
            if token_id and token_id not in token_id_set:
                errors.append(
                    f"missing_token:{row['id']}:{property_name}:{token_id}"
                )
        if row["opacity"] <= 0.0:
            warnings.append(f"fully_transparent:{row['id']}")
        if not row["visible"]:
            warnings.append(f"hidden:{row['id']}")
        accessibility = row["accessibility"]
        role = accessibility["role"]
        label = accessibility["label"]
        focus_order = accessibility["focus_order"]
        effective_role = (
            {
                "button": "button",
                "image": "image",
                "progress": "progress",
                "text": "text",
            }.get(row["kind"], "none")
            if role == "auto"
            else role
        )
        effective_label = label
        if not effective_label and effective_role in {"button", "heading", "text"}:
            effective_label = str(row["content"].get("text") or "").strip()
        if (
            effective_role
            in {"button", "checkbox", "image", "link", "progress", "slider"}
            and not effective_label
        ):
            warnings.append(f"missing_accessibility_label:{row['id']}")
        if focus_order > 0:
            focus_key = (row["artboard_id"], focus_order)
            existing_id = focus_orders.get(focus_key)
            if existing_id:
                warnings.append(
                    f"duplicate_focus_order:{row['artboard_id']}:{focus_order}:"
                    f"{existing_id}:{row['id']}"
                )
            else:
                focus_orders[focus_key] = row["id"]
    for object_id in object_ids:
        seen: set[str] = set()
        current = object_by_id.get(object_id)
        while current and current["parent_id"]:
            parent_id = current["parent_id"]
            if parent_id in seen:
                errors.append(f"parent_cycle:{object_id}")
                break
            seen.add(parent_id)
            current = object_by_id.get(parent_id)
    for row in document["components"]:
        root_id = row["root_object_id"]
        if root_id and root_id not in object_by_id:
            errors.append(f"missing_component_root:{row['id']}:{root_id}")
        elif root_id:
            root = object_by_id[root_id]
            if root["component_role"] not in {"none", "definition"}:
                errors.append(f"invalid_component_root_role:{row['id']}:{root_id}")
            if (
                root["component_role"] == "definition"
                and root["component_id"] != row["id"]
            ):
                errors.append(f"component_root_owner_mismatch:{row['id']}:{root_id}")
        base_id = row["base_component_id"]
        if base_id and base_id not in component_id_set:
            errors.append(f"missing_base_component:{row['id']}:{base_id}")
        for variant_id in row["variant_ids"]:
            if variant_id not in component_id_set:
                errors.append(f"missing_component_variant:{row['id']}:{variant_id}")
        for property_name, definition in row["property_definitions"].items():
            if (
                definition["type"] == "enum"
                and definition["values"]
                and str(definition["default"]) not in definition["values"]
            ):
                errors.append(
                    f"invalid_component_property_default:{row['id']}:"
                    f"{property_name}:{definition['default']}"
                )
        for state, source_rows in row["state_overrides"].items():
            state_definition = row["property_definitions"].get("state")
            if (
                state_definition
                and state_definition["type"] == "enum"
                and state_definition["values"]
                and state not in state_definition["values"]
            ):
                errors.append(
                    f"invalid_component_state:{row['id']}:{state}"
                )
            for source_id in source_rows:
                source = object_by_id.get(source_id)
                if (
                    source is None
                    or source["component_role"] != "definition"
                    or source["component_id"] != row["id"]
                ):
                    errors.append(
                        f"invalid_component_state_source:{row['id']}:"
                        f"{state}:{source_id}"
                    )
    _append_cycle_errors(
        document["components"],
        reference_key="base_component_id",
        error_prefix="component_cycle",
        errors=errors,
    )
    for section in document["sections"]:
        for object_id in section["object_ids"]:
            if object_id not in object_by_id:
                errors.append(
                    f"missing_section_object:{section['id']}:{object_id}"
                )
    for row in document["tokens"]:
        if row["kind"] not in UI_TOKEN_KINDS:
            errors.append(f"unsupported_token_kind:{row['id']}:{row['kind']}")
        alias_id = row["alias_token_id"]
        if alias_id and alias_id not in token_id_set:
            errors.append(f"missing_token_alias:{row['id']}:{alias_id}")
    _append_cycle_errors(
        document["tokens"],
        reference_key="alias_token_id",
        error_prefix="token_alias_cycle",
        errors=errors,
    )
    for row in document["interactions"]:
        interaction_id = row["id"]
        source_id = row["source_object_id"]
        if source_id and source_id not in object_by_id:
            errors.append(f"missing_interaction_source:{interaction_id}:{source_id}")
        if row["trigger"] not in UI_INTERACTION_TRIGGERS:
            errors.append(
                f"unsupported_interaction_trigger:{interaction_id}:{row['trigger']}"
            )
        if row["action"] not in UI_INTERACTION_ACTIONS:
            errors.append(
                f"unsupported_interaction_action:{interaction_id}:{row['action']}"
            )
        target_artboard_id = row["target_artboard_id"]
        if target_artboard_id and target_artboard_id not in artboard_id_set:
            errors.append(
                f"missing_interaction_artboard:{interaction_id}:{target_artboard_id}"
            )
        target_object_id = row["target_object_id"]
        if target_object_id and target_object_id not in object_by_id:
            errors.append(
                f"missing_interaction_target:{interaction_id}:{target_object_id}"
            )
        component_id = row["component_id"]
        if component_id and component_id not in component_id_set:
            errors.append(
                f"missing_interaction_component:{interaction_id}:{component_id}"
            )
    from app.painter_ui_layout_diagnostics import diagnose_ui_layout

    layout_diagnostics = diagnose_ui_layout(document)
    errors.extend(layout_diagnostics["errors"])
    warnings.extend(layout_diagnostics["warnings"])
    return {
        "schema": "tigerstudio.painter.ui.validation.v2",
        "ok": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "layout_diagnostics": layout_diagnostics,
        "artboard_count": len(artboard_ids),
        "object_count": len(object_ids),
        "component_count": len(document["components"]),
        "token_count": len(document["tokens"]),
        "interaction_count": len(document["interactions"]),
        "layout_grid_style_count": len(layout_grid_style_ids),
        "revision": document["revision"],
    }


def inspect_ui_document(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    return {
        "schema": "tigerstudio.painter.ui.inspect.v1",
        "document": copy.deepcopy(document),
        "validation": validate_ui_document(document),
        "active_artboard_id": document["active_artboard_id"],
        "selected_object_id": document["selection"]["object_id"],
        "selected_object_ids": list(document["selection"]["object_ids"]),
        "delivery_targets": list(UI_DELIVERY_TARGETS),
    }


def _revised(document: Mapping[str, Any]) -> dict[str, Any]:
    updated = normalize_ui_document(document)
    updated["revision"] += 1
    return updated


def _remove_dangling_records(
    document: dict[str, Any],
    *,
    removed_object_ids: set[str] | None = None,
    removed_artboard_ids: set[str] | None = None,
) -> dict[str, list[str]]:
    removed_objects = set(removed_object_ids or ())
    removed_artboards = set(removed_artboard_ids or ())
    removed_components = {
        row["id"]
        for row in document["components"]
        if row["root_object_id"] in removed_objects
    }
    document["components"] = [
        row
        for row in document["components"]
        if row["id"] not in removed_components
    ]
    for row in document["components"]:
        if row["base_component_id"] in removed_components:
            row["base_component_id"] = ""
        row["variant_ids"] = [
            component_id
            for component_id in row["variant_ids"]
            if component_id not in removed_components
        ]
    for row in document["objects"]:
        if row["component_id"] in removed_components:
            row["component_id"] = ""
            row["component_role"] = "none"
            row["component_source_object_id"] = ""
            row["instance_overrides"] = {}
            row["component_properties"] = {}
        if row["component_scope_id"] in removed_components:
            row["component_scope_id"] = ""
            row["component_scope_source_object_id"] = ""
        mask = dict(row.get("mask") or {})
        mask["target_ids"] = [
            object_id
            for object_id in mask.get("target_ids", [])
            if object_id not in removed_objects
        ]
        row["mask"] = mask
        content = dict(row.get("content") or {})
        boolean = dict(content.get("boolean") or {})
        operands = [
            object_id
            for object_id in boolean.get("operand_ids", [])
            if object_id not in removed_objects
        ]
        boolean["operand_ids"] = operands
        if len(operands) < 2:
            boolean["enabled"] = False
        if boolean:
            content["boolean"] = boolean
        row["content"] = content
    for section in document.get("sections", []):
        section["object_ids"] = [
            object_id
            for object_id in section.get("object_ids", [])
            if object_id not in removed_objects
        ]
    removed_interactions = {
        row["id"]
        for row in document["interactions"]
        if row["source_object_id"] in removed_objects
        or row["target_object_id"] in removed_objects
        or row["target_artboard_id"] in removed_artboards
        or row["component_id"] in removed_components
    }
    document["interactions"] = [
        row
        for row in document["interactions"]
        if row["id"] not in removed_interactions
    ]
    removed_motion_links: list[str] = []
    linked_targets = document.get("linked_targets")
    linked_targets = linked_targets if isinstance(linked_targets, dict) else {}
    motion_target = linked_targets.get("motion_designer")
    if isinstance(motion_target, Mapping):
        motion_target = copy.deepcopy(dict(motion_target))
        object_bindings = motion_target.get("object_bindings")
        object_bindings = (
            copy.deepcopy(dict(object_bindings))
            if isinstance(object_bindings, Mapping)
            else {}
        )
        removed_motion_links = sorted(
            object_id
            for object_id in removed_objects
            if object_id in object_bindings
        )
        for object_id in removed_motion_links:
            object_bindings.pop(object_id, None)
        motion_target["object_bindings"] = object_bindings
        linked_targets["motion_designer"] = motion_target
        document["linked_targets"] = linked_targets
    return {
        "removed_component_ids": sorted(removed_components),
        "removed_interaction_ids": sorted(removed_interactions),
        "removed_motion_link_object_ids": removed_motion_links,
    }


def add_ui_artboard(
    value: Mapping[str, Any],
    *,
    name: str = "",
    width: int = 1920,
    height: int = 1080,
    breakpoint: str = "custom",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    artboard_id = _next_id("artboard", document["artboards"])
    right_edge = max(
        float(item["x"]) + float(item["width"])
        for item in document["artboards"]
    )
    row = _normalize_artboard(
        {
            "id": artboard_id,
            "name": name or f"Artboard {len(document['artboards']) + 1}",
            "width": width,
            "height": height,
            "breakpoint": breakpoint,
            "x": right_edge + 80.0,
            "y": min(float(item["y"]) for item in document["artboards"]),
        },
        len(document["artboards"]),
    )
    document["artboards"].append(row)
    document["active_artboard_id"] = artboard_id
    document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = []
    return _revised(document), copy.deepcopy(row)


def update_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["artboards"]):
        if row["id"] != artboard_id:
            continue
        normalized_changes = dict(changes)
        if "layout_grid" in normalized_changes and "layout_grids" not in normalized_changes:
            grids = [dict(item) for item in row.get("layout_grids", [])]
            replacement = dict(normalized_changes["layout_grid"])
            if grids:
                grids[0] = {**grids[0], **replacement}
            else:
                grids = [replacement]
            normalized_changes["layout_grids"] = grids
        elif "layout_grids" in normalized_changes:
            grids = normalized_changes.get("layout_grids")
            if isinstance(grids, list) and grids:
                normalized_changes["layout_grid"] = dict(grids[0])
        merged = {**row, **normalized_changes, "id": row["id"]}
        updated_row = _normalize_artboard(merged, index)
        document["artboards"][index] = updated_row
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI artboard not found: {artboard_id}")


def remove_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if len(document["artboards"]) <= 1:
        raise PainterUIDocumentError("A UI document must keep at least one artboard")
    if artboard_id not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {artboard_id}")
    removed_objects = [
        row["id"] for row in document["objects"] if row["artboard_id"] == artboard_id
    ]
    document["artboards"] = [
        row for row in document["artboards"] if row["id"] != artboard_id
    ]
    document["objects"] = [
        row for row in document["objects"] if row["artboard_id"] != artboard_id
    ]
    cleanup = _remove_dangling_records(
        document,
        removed_object_ids=set(removed_objects),
        removed_artboard_ids={artboard_id},
    )
    if document["active_artboard_id"] == artboard_id:
        document["active_artboard_id"] = document["artboards"][0]["id"]
    if document["selection"]["object_id"] in removed_objects:
        document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = [
        object_id
        for object_id in document["selection"]["object_ids"]
        if object_id not in removed_objects
    ]
    return _revised(document), {
        "artboard_id": artboard_id,
        "removed_object_ids": removed_objects,
        **cleanup,
    }


def set_active_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    target = str(artboard_id or "")
    if target not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {target}")
    if document["active_artboard_id"] == target:
        return document
    document["active_artboard_id"] = target
    selected = document["selection"]["object_id"]
    selected_row = next(
        (row for row in document["objects"] if row["id"] == selected),
        None,
    )
    if selected_row is not None and selected_row["artboard_id"] != target:
        document["selection"]["object_id"] = ""
        document["selection"]["object_ids"] = []
    return _revised(document)


def add_ui_object(
    value: Mapping[str, Any],
    *,
    kind: str = "rectangle",
    name: str = "",
    artboard_id: str = "",
    parent_id: str = "",
    x: float = 0.0,
    y: float = 0.0,
    width: float = 160.0,
    height: float = 64.0,
    style: Mapping[str, Any] | None = None,
    content: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target_artboard = str(artboard_id or document["active_artboard_id"])
    if target_artboard not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {target_artboard}")
    if parent_id and parent_id not in {row["id"] for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI parent object not found: {parent_id}")
    parent_row = next(
        (row for row in document["objects"] if row["id"] == parent_id),
        None,
    )
    object_id = _next_id("ui-object", document["objects"])
    inherited_component_id = (
        str(parent_row["component_id"])
        if parent_row is not None
        and parent_row["component_role"] == "definition"
        else ""
    )
    row = _normalize_object(
        {
            "id": object_id,
            "kind": kind,
            "name": name or str(kind or "rectangle").title(),
            "artboard_id": target_artboard,
            "parent_id": parent_id,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "z_index": len(document["objects"]),
            "style": dict(style or {}),
            "content": dict(content or {}),
            "component_id": inherited_component_id,
            "component_role": "definition" if inherited_component_id else "none",
            "component_source_object_id": object_id if inherited_component_id else "",
        },
        len(document["objects"]),
        target_artboard,
    )
    document["objects"].append(row)
    if inherited_component_id:
        from app.painter_ui_components import sync_ui_component_instances

        document = sync_ui_component_instances(
            document,
            inherited_component_id,
            normalize=False,
        )
    document["selection"]["object_id"] = object_id
    document["selection"]["object_ids"] = [object_id]
    return _revised(document), copy.deepcopy(row)


def update_ui_object(
    value: Mapping[str, Any],
    object_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["objects"]):
        if row["id"] != object_id:
            continue
        effective_changes = dict(changes)
        if row["component_role"] == "instance":
            from app.painter_ui_components import merge_ui_instance_overrides

            effective_changes["instance_overrides"] = merge_ui_instance_overrides(
                row,
                effective_changes,
            )
        merged = {**row, **effective_changes, "id": row["id"]}
        updated_row = _normalize_object(
            merged,
            index,
            document["active_artboard_id"],
        )
        document["objects"][index] = updated_row
        sync_component_ids = set()
        if (
            updated_row["component_role"] == "definition"
            and updated_row["component_id"]
        ):
            sync_component_ids.add(updated_row["component_id"])
        if (
            updated_row["component_scope_id"]
            and updated_row["component_scope_source_object_id"] == object_id
        ):
            sync_component_ids.add(updated_row["component_scope_id"])
        if sync_component_ids:
            from app.painter_ui_components import sync_ui_component_instances

            for component_id in sorted(sync_component_ids):
                document = sync_ui_component_instances(
                    document,
                    component_id,
                    normalize=False,
                )
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise PainterUIDocumentError("Invalid UI object update: " + ", ".join(validation["errors"]))
        document["selection"]["object_id"] = object_id
        if object_id not in document["selection"]["object_ids"]:
            document["selection"]["object_ids"].append(object_id)
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI object not found: {object_id}")


def remove_ui_object(
    value: Mapping[str, Any],
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if object_id not in {row["id"] for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    removed = {object_id}
    changed = True
    while changed:
        before = len(removed)
        removed.update(
            row["id"]
            for row in document["objects"]
            if row["parent_id"] in removed
        )
        changed = len(removed) != before
    component_roots = {
        row["id"]: row["root_object_id"]
        for row in document["components"]
    }
    component_sync_ids = {
        row["component_id"]
        for row in document["objects"]
        if row["id"] in removed
        and row["component_role"] == "definition"
        and row["component_id"]
        and component_roots.get(row["component_id"]) not in removed
    }
    component_sync_ids.update(
        row["component_scope_id"]
        for row in document["objects"]
        if row["id"] in removed
        and row["component_scope_id"]
        and row["component_scope_source_object_id"] == row["id"]
        and component_roots.get(row["component_scope_id"]) not in removed
    )
    document["objects"] = [
        row for row in document["objects"] if row["id"] not in removed
    ]
    cleanup = _remove_dangling_records(
        document,
        removed_object_ids=removed,
    )
    if component_sync_ids:
        from app.painter_ui_components import sync_ui_component_instances

        for component_id in sorted(component_sync_ids):
            document = sync_ui_component_instances(
                document,
                component_id,
                normalize=False,
            )
    if document["selection"]["object_id"] in removed:
        document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = [
        selected
        for selected in document["selection"]["object_ids"]
        if selected not in removed
    ]
    if (
        not document["selection"]["object_id"]
        and document["selection"]["object_ids"]
    ):
        document["selection"]["object_id"] = document["selection"]["object_ids"][-1]
    return _revised(document), {
        "removed_object_ids": sorted(removed),
        **cleanup,
    }


def select_ui_object(
    value: Mapping[str, Any],
    object_id: str = "",
    *,
    mode: str = "replace",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    if object_id and object_id not in {row["id"] for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    selected = list(document["selection"]["object_ids"])
    target = str(object_id or "")
    operation = str(mode or "replace").strip().casefold()
    if not target:
        selected = []
    elif operation == "add":
        if target not in selected:
            selected.append(target)
    elif operation == "toggle":
        if target in selected:
            selected.remove(target)
        else:
            selected.append(target)
    else:
        selected = [target]
    document["selection"]["object_ids"] = selected
    document["selection"]["object_id"] = (
        target if target in selected else selected[-1] if selected else ""
    )
    return document


def select_ui_objects(
    value: Mapping[str, Any],
    object_ids: list[str] | tuple[str, ...],
    *,
    primary_object_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    active = document["active_artboard_id"]
    valid_by_id = {
        row["id"]: row
        for row in document["objects"]
        if row["artboard_id"] == active
    }
    selected: list[str] = []
    for value_id in object_ids:
        object_id = str(value_id or "")
        if object_id in valid_by_id and object_id not in selected:
            selected.append(object_id)
    primary = str(primary_object_id or "")
    if primary not in selected:
        primary = selected[-1] if selected else ""
    document["selection"] = {
        "object_id": primary,
        "object_ids": selected,
    }
    return document


def group_ui_objects(
    value: Mapping[str, Any],
    object_ids: list[str] | tuple[str, ...],
    *,
    name: str = "Group",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    active = document["active_artboard_id"]
    selected_ids = list(dict.fromkeys(str(item or "") for item in object_ids))
    rows = [
        row
        for row in document["objects"]
        if row["id"] in selected_ids and row["artboard_id"] == active
    ]
    if len(rows) < 2:
        raise PainterUIDocumentError("Grouping requires at least two UI objects")
    selected_set = {row["id"] for row in rows}
    if any(row["parent_id"] in selected_set for row in rows):
        raise PainterUIDocumentError(
            "Select sibling UI objects rather than an ancestor and its child"
        )
    parent_ids = {row["parent_id"] for row in rows}
    parent_id = parent_ids.pop() if len(parent_ids) == 1 else ""
    min_x = min(float(row["x"]) for row in rows)
    min_y = min(float(row["y"]) for row in rows)
    max_x = max(float(row["x"]) + float(row["width"]) for row in rows)
    max_y = max(float(row["y"]) + float(row["height"]) for row in rows)
    group_id = _next_id("ui-object", document["objects"])
    group_row = _normalize_object(
        {
            "id": group_id,
            "kind": "group",
            "name": str(name or "Group"),
            "artboard_id": active,
            "parent_id": parent_id,
            "x": min_x,
            "y": min_y,
            "width": max(1.0, max_x - min_x),
            "height": max(1.0, max_y - min_y),
            "z_index": max(int(row["z_index"]) for row in rows) + 1,
            "style": {"fill": "#00000000", "stroke": "#718096"},
        },
        len(document["objects"]),
        active,
    )
    for row in document["objects"]:
        if row["id"] in selected_set:
            row["parent_id"] = group_id
    document["objects"].append(group_row)
    document["selection"] = {
        "object_id": group_id,
        "object_ids": [group_id],
    }
    return _revised(document), copy.deepcopy(group_row)


def ungroup_ui_object(
    value: Mapping[str, Any],
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    group = next(
        (row for row in document["objects"] if row["id"] == object_id),
        None,
    )
    if group is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    if group["kind"] != "group":
        raise PainterUIDocumentError("Only a UI group can be ungrouped")
    child_ids = [
        row["id"] for row in document["objects"] if row["parent_id"] == object_id
    ]
    for row in document["objects"]:
        if row["parent_id"] == object_id:
            row["parent_id"] = group["parent_id"]
    document["objects"] = [
        row for row in document["objects"] if row["id"] != object_id
    ]
    document["selection"] = {
        "object_id": child_ids[-1] if child_ids else "",
        "object_ids": child_ids,
    }
    return _revised(document), {
        "removed_group_id": object_id,
        "child_object_ids": child_ids,
    }


def reorder_ui_objects(
    value: Mapping[str, Any],
    object_ids: list[str] | tuple[str, ...],
    command: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    active = document["active_artboard_id"]
    selected = {
        str(object_id or "")
        for object_id in object_ids
        if str(object_id or "")
    }
    if not selected:
        return document
    active_rows = sorted(
        (
            row
            for row in document["objects"]
            if row["artboard_id"] == active
        ),
        key=lambda row: int(row["z_index"]),
    )
    if not selected.issubset({row["id"] for row in active_rows}):
        raise PainterUIDocumentError(
            "UI reorder selection must belong to the active artboard"
        )
    operation = str(command or "").strip().casefold()
    if operation == "front":
        active_rows = [
            row for row in active_rows if row["id"] not in selected
        ] + [row for row in active_rows if row["id"] in selected]
    elif operation == "back":
        active_rows = [
            row for row in active_rows if row["id"] in selected
        ] + [row for row in active_rows if row["id"] not in selected]
    elif operation == "forward":
        for index in range(len(active_rows) - 2, -1, -1):
            if (
                active_rows[index]["id"] in selected
                and active_rows[index + 1]["id"] not in selected
            ):
                active_rows[index], active_rows[index + 1] = (
                    active_rows[index + 1],
                    active_rows[index],
                )
    elif operation == "backward":
        for index in range(1, len(active_rows)):
            if (
                active_rows[index]["id"] in selected
                and active_rows[index - 1]["id"] not in selected
            ):
                active_rows[index], active_rows[index - 1] = (
                    active_rows[index - 1],
                    active_rows[index],
                )
    else:
        raise PainterUIDocumentError(f"Unsupported UI reorder command: {command}")
    for z_index, row in enumerate(active_rows):
        row["z_index"] = z_index
    return _revised(document)


def move_ui_objects_in_hierarchy(
    value: Mapping[str, Any],
    object_ids: list[str] | tuple[str, ...],
    *,
    target_parent_id: str = "",
    anchor_id: str = "",
    placement: str = "inside",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    active = document["active_artboard_id"]
    object_by_id = {row["id"]: row for row in document["objects"]}
    selected_ids = list(dict.fromkeys(str(item or "") for item in object_ids))
    selected_ids = [
        object_id
        for object_id in selected_ids
        if object_id in object_by_id
        and object_by_id[object_id]["artboard_id"] == active
    ]
    if not selected_ids:
        raise PainterUIDocumentError("Hierarchy move requires UI objects")
    selected = set(selected_ids)
    if any(object_by_id[object_id]["parent_id"] in selected for object_id in selected):
        raise PainterUIDocumentError(
            "Move a parent or its child, not both in one hierarchy operation"
        )
    parent_id = str(target_parent_id or "")
    anchor = str(anchor_id or "")
    operation = str(placement or "inside").strip().casefold()
    if parent_id:
        parent = object_by_id.get(parent_id)
        if parent is None or parent["artboard_id"] != active:
            raise PainterUIDocumentError(f"UI parent object not found: {parent_id}")
        if parent["kind"] != "group":
            raise PainterUIDocumentError("UI objects can only nest inside a group")
    if anchor:
        anchor_row = object_by_id.get(anchor)
        if anchor_row is None or anchor_row["artboard_id"] != active:
            raise PainterUIDocumentError(f"UI anchor object not found: {anchor}")
    descendants = set(selected)
    changed = True
    while changed:
        before = len(descendants)
        descendants.update(
            row["id"]
            for row in document["objects"]
            if row["parent_id"] in descendants
        )
        changed = len(descendants) != before
    if parent_id in descendants or anchor in descendants:
        raise PainterUIDocumentError("Hierarchy move would create a cycle")

    if operation in {"before", "after"} and anchor:
        parent_id = object_by_id[anchor]["parent_id"]
    elif operation == "root":
        parent_id = ""
        anchor = ""
    elif operation != "inside":
        raise PainterUIDocumentError(
            f"Unsupported UI hierarchy placement: {placement}"
        )
    for row in document["objects"]:
        if row["id"] in selected:
            row["parent_id"] = parent_id

    active_rows = sorted(
        (
            row
            for row in document["objects"]
            if row["artboard_id"] == active
        ),
        key=lambda row: int(row["z_index"]),
    )
    moving = [row for row in active_rows if row["id"] in selected]
    stationary = [row for row in active_rows if row["id"] not in selected]
    if operation == "inside":
        insert_at = next(
            (
                index + 1
                for index, row in enumerate(stationary)
                if row["id"] == parent_id
            ),
            len(stationary),
        )
    elif operation == "before":
        insert_at = next(
            index + 1
            for index, row in enumerate(stationary)
            if row["id"] == anchor
        )
    elif operation == "after":
        insert_at = next(
            index
            for index, row in enumerate(stationary)
            if row["id"] == anchor
        )
    else:
        insert_at = len(stationary)
    active_rows = stationary[:insert_at] + moving + stationary[insert_at:]
    for z_index, row in enumerate(active_rows):
        row["z_index"] = z_index
    document["selection"] = {
        "object_id": selected_ids[-1],
        "object_ids": selected_ids,
    }
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid UI hierarchy move: " + ", ".join(validation["errors"])
        )
    return _revised(document)


def add_ui_component(
    value: Mapping[str, Any],
    *,
    name: str = "",
    root_object_id: str = "",
    base_component_id: str = "",
    description: str = "",
    property_definitions: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    component_id = _next_id("ui-component", document["components"])
    row = _normalize_component(
        {
            "id": component_id,
            "name": name or f"Component {len(document['components']) + 1}",
            "root_object_id": root_object_id,
            "base_component_id": base_component_id,
            "description": description,
            "property_definitions": dict(property_definitions or {}),
        },
        len(document["components"]),
    )
    document["components"].append(row)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid UI component: " + ", ".join(validation["errors"])
        )
    return _revised(document), copy.deepcopy(row)


def update_ui_component(
    value: Mapping[str, Any],
    component_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["components"]):
        if row["id"] != component_id:
            continue
        updated_row = _normalize_component(
            {**row, **dict(changes), "id": row["id"]},
            index,
        )
        document["components"][index] = updated_row
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise PainterUIDocumentError(
                "Invalid UI component update: " + ", ".join(validation["errors"])
            )
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI component not found: {component_id}")


def remove_ui_component(
    value: Mapping[str, Any],
    component_id: str,
    *,
    detach_references: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if component_id not in {row["id"] for row in document["components"]}:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    object_refs = [
        row["id"]
        for row in document["objects"]
        if row["component_id"] == component_id
        or row["component_scope_id"] == component_id
    ]
    component_refs = [
        row["id"]
        for row in document["components"]
        if row["base_component_id"] == component_id
        or component_id in row["variant_ids"]
    ]
    interaction_refs = [
        row["id"]
        for row in document["interactions"]
        if row["component_id"] == component_id
    ]
    if (object_refs or component_refs or interaction_refs) and not detach_references:
        raise PainterUIDocumentError(
            f"UI component is referenced: {component_id}"
        )
    document["components"] = [
        row for row in document["components"] if row["id"] != component_id
    ]
    if detach_references:
        for row in document["objects"]:
            if row["component_id"] == component_id:
                row["component_id"] = ""
                row["component_role"] = "none"
                row["component_source_object_id"] = ""
                row["instance_overrides"] = {}
                row["component_properties"] = {}
            if row["component_scope_id"] == component_id:
                row["component_scope_id"] = ""
                row["component_scope_source_object_id"] = ""
        for row in document["components"]:
            if row["base_component_id"] == component_id:
                row["base_component_id"] = ""
            row["variant_ids"] = [
                variant_id
                for variant_id in row["variant_ids"]
                if variant_id != component_id
            ]
        for row in document["interactions"]:
            if row["component_id"] == component_id:
                row["component_id"] = ""
    return _revised(document), {
        "component_id": component_id,
        "detached_object_ids": object_refs,
        "detached_component_ids": component_refs,
        "detached_interaction_ids": interaction_refs,
    }


def add_ui_token(
    value: Mapping[str, Any],
    *,
    name: str = "",
    kind: str = "color",
    token_value: Any = None,
    theme_values: Mapping[str, Any] | None = None,
    alias_token_id: str = "",
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    token_id = _next_id("ui-token", document["tokens"])
    row = _normalize_token(
        {
            "id": token_id,
            "name": name or f"Token {len(document['tokens']) + 1}",
            "kind": kind,
            "value": token_value,
            "theme_values": dict(theme_values or {}),
            "alias_token_id": alias_token_id,
            "description": description,
        },
        len(document["tokens"]),
    )
    document["tokens"].append(row)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid UI token: " + ", ".join(validation["errors"])
        )
    return _revised(document), copy.deepcopy(row)


def update_ui_token(
    value: Mapping[str, Any],
    token_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["tokens"]):
        if row["id"] != token_id:
            continue
        updated_row = _normalize_token(
            {**row, **dict(changes), "id": row["id"]},
            index,
        )
        document["tokens"][index] = updated_row
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise PainterUIDocumentError(
                "Invalid UI token update: " + ", ".join(validation["errors"])
            )
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI token not found: {token_id}")


def remove_ui_token(
    value: Mapping[str, Any],
    token_id: str,
    *,
    detach_references: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if token_id not in {row["id"] for row in document["tokens"]}:
        raise PainterUIDocumentError(f"UI token not found: {token_id}")
    object_refs = [
        row["id"]
        for row in document["objects"]
        if token_id in row["token_bindings"].values()
    ]
    alias_refs = [
        row["id"]
        for row in document["tokens"]
        if row["alias_token_id"] == token_id
    ]
    if (object_refs or alias_refs) and not detach_references:
        raise PainterUIDocumentError(f"UI token is referenced: {token_id}")
    document["tokens"] = [
        row for row in document["tokens"] if row["id"] != token_id
    ]
    if detach_references:
        for row in document["objects"]:
            row["token_bindings"] = {
                key: value
                for key, value in row["token_bindings"].items()
                if value != token_id
            }
        for row in document["tokens"]:
            if row["alias_token_id"] == token_id:
                row["alias_token_id"] = ""
    return _revised(document), {
        "token_id": token_id,
        "detached_object_ids": object_refs,
        "detached_alias_token_ids": alias_refs,
    }


def add_ui_interaction(
    value: Mapping[str, Any],
    *,
    name: str = "",
    source_object_id: str = "",
    trigger: str = "click",
    action: str = "navigate",
    target_artboard_id: str = "",
    target_object_id: str = "",
    component_id: str = "",
    motion_clip_id: str = "",
    parameters: Mapping[str, Any] | None = None,
    enabled: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    interaction_id = _next_id("ui-interaction", document["interactions"])
    row = _normalize_interaction(
        {
            "id": interaction_id,
            "name": name or f"Interaction {len(document['interactions']) + 1}",
            "source_object_id": source_object_id,
            "trigger": trigger,
            "action": action,
            "target_artboard_id": target_artboard_id,
            "target_object_id": target_object_id,
            "component_id": component_id,
            "motion_clip_id": motion_clip_id,
            "parameters": dict(parameters or {}),
            "enabled": enabled,
        },
        len(document["interactions"]),
    )
    document["interactions"].append(row)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid UI interaction: " + ", ".join(validation["errors"])
        )
    return _revised(document), copy.deepcopy(row)


def update_ui_interaction(
    value: Mapping[str, Any],
    interaction_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["interactions"]):
        if row["id"] != interaction_id:
            continue
        updated_row = _normalize_interaction(
            {**row, **dict(changes), "id": row["id"]},
            index,
        )
        document["interactions"][index] = updated_row
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise PainterUIDocumentError(
                "Invalid UI interaction update: "
                + ", ".join(validation["errors"])
            )
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI interaction not found: {interaction_id}")


def remove_ui_interaction(
    value: Mapping[str, Any],
    interaction_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if interaction_id not in {row["id"] for row in document["interactions"]}:
        raise PainterUIDocumentError(
            f"UI interaction not found: {interaction_id}"
        )
    document["interactions"] = [
        row for row in document["interactions"] if row["id"] != interaction_id
    ]
    return _revised(document), {"interaction_id": interaction_id}


__all__ = [
    "PainterUIDocumentError",
    "UI_DELIVERY_TARGETS",
    "UI_DOCUMENT_SCHEMA",
    "UI_DOCUMENT_VERSION",
    "UI_INTERACTION_ACTIONS",
    "UI_INTERACTION_TRIGGERS",
    "UI_OBJECT_KINDS",
    "UI_TOKEN_KINDS",
    "add_ui_artboard",
    "add_ui_component",
    "add_ui_interaction",
    "add_ui_object",
    "add_ui_token",
    "create_ui_document",
    "group_ui_objects",
    "inspect_ui_document",
    "move_ui_objects_in_hierarchy",
    "migrate_ui_document",
    "normalize_ui_document",
    "remove_ui_artboard",
    "remove_ui_component",
    "remove_ui_interaction",
    "remove_ui_object",
    "remove_ui_token",
    "reorder_ui_objects",
    "select_ui_object",
    "select_ui_objects",
    "set_active_ui_artboard",
    "update_ui_artboard",
    "update_ui_component",
    "update_ui_interaction",
    "update_ui_object",
    "update_ui_token",
    "ungroup_ui_object",
    "validate_ui_document",
]
