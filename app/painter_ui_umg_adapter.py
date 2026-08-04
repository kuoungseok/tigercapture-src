"""Painter provider adapter for the shared TigerStudioUMG backend."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_constraints import (
    normalize_ui_constraints,
    resolve_ui_constraints,
)
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_motion_bridge import resolved_ui_geometry
from app.painter_ui_responsive import resolve_ui_responsive_document
from app.painter_ui_scroll import normalize_ui_scroll
from app.unreal_umg_layout import (
    TIGER_UMG_SCHEMA_VERSION,
    painter_layer_layout,
)
from app.unreal_umg_image_fill import (
    painter_image_fill_conversion,
    validate_umg_image_fill_record,
)
from app.unreal_umg_material import (
    painter_style_umg_material,
    validate_umg_material_record,
)


PAINTER_UMG_ADAPTER_SCHEMA = "tigerstudio.painter.ui.umg_adapter.v7"
_VISIBLE_UNIFORM_RADIUS_KINDS = {"button", "frame", "image"}
_DYNAMIC_CANVAS_CONSTRAINTS = {"stretch", "scale"}


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_id(path: Path, kind: str) -> str:
    key = f"{kind}:{path.resolve()}".encode("utf-8", errors="surrogatepass")
    return f"{kind}_{hashlib.sha256(key).hexdigest()[:20]}"


def _umg_kind(kind: str) -> str:
    return {
        "frame": "Group",
        "group": "Group",
        "text": "Text",
        "image": "Image",
        "button": "Button",
        "progress": "Image",
        "rectangle": "Image",
        "ellipse": "Image",
        "line": "Image",
        "path": "Image",
    }.get(kind, "Unsupported")


def _visible_style_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        row
        for row in value
        if isinstance(row, Mapping) and bool(row.get("visible", True))
    ]


def _active_strokes(style: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        row
        for row in _visible_style_rows(style.get("strokes"))
        if float(row.get("width", 1.0) or 0.0) > 0.0001
    ]


def _appearance_effects(style: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    effects = _visible_style_rows(style.get("effects"))
    if effects:
        return effects
    shadow = style.get("shadow")
    return (
        [{"type": "drop_shadow", **dict(shadow)}]
        if isinstance(shadow, Mapping)
        else []
    )


def _has_advanced_appearance(
    style: Mapping[str, Any],
    *,
    include_uniform_radius: bool = True,
) -> bool:
    if isinstance(style.get("fill_gradient"), Mapping):
        return True
    if any(
        str(row.get("type") or "solid").strip().casefold()
        in {"linear", "radial"}
        for row in _visible_style_rows(style.get("fills"))
    ):
        return True
    corner_radii = style.get("corner_radii")
    corner_radii = corner_radii if isinstance(corner_radii, Mapping) else {}
    radius = float(style.get("radius", 0.0) or 0.0)
    corner_values = [
        round(float(value or 0.0), 4) for value in corner_radii.values()
    ]
    if include_uniform_radius:
        if radius > 0.0001 or any(value > 0.0001 for value in corner_values):
            return True
    elif len(set(corner_values)) > 1:
        # The legacy/default Painter style assigns a uniform radius to every
        # object and normalization mirrors it into all four corners. That is
        # not an authored independent-corner request on Text/Group/Button.
        return True
    if float(style.get("corner_smoothing", 0.0) or 0.0) > 0.0001:
        return True
    if _active_strokes(style) or _appearance_effects(style):
        return True
    return False


def _row_size(row: Mapping[str, Any], override: object = None) -> dict[str, float]:
    source = override if isinstance(override, Mapping) else row
    return {
        "X": max(
            0.0001,
            float(source.get("X", source.get("width", 100.0)) or 100.0),
        ),
        "Y": max(
            0.0001,
            float(source.get("Y", source.get("height", 100.0)) or 100.0),
        ),
    }


def _constraints_require_runtime_size(
    constraints: Mapping[str, Any],
) -> bool:
    horizontal = str(constraints.get("horizontal") or "left")
    vertical = str(constraints.get("vertical") or "top")
    if (
        horizontal in _DYNAMIC_CANVAS_CONSTRAINTS
        or vertical in _DYNAMIC_CANVAS_CONSTRAINTS
    ):
        return True
    return (
        horizontal == "custom"
        and abs(
            float(constraints.get("anchor_max_x", 0.0))
            - float(constraints.get("anchor_min_x", 0.0))
        )
        > 0.000001
    ) or (
        vertical == "custom"
        and abs(
            float(constraints.get("anchor_max_y", 0.0))
            - float(constraints.get("anchor_min_y", 0.0))
        )
        > 0.000001
    )


def _umg_disposition(
    row: Mapping[str, Any],
    style: Mapping[str, Any],
    content: Mapping[str, Any],
    kind: str,
    *,
    resolved_size: object = None,
    runtime_size_dynamic: bool = False,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    source_kind = str(row.get("kind") or "").strip().casefold()
    image_fill = painter_image_fill_conversion(
        row,
        style,
        content,
        size=(resolved_size if isinstance(resolved_size, Mapping) else row),
    )
    reasons.extend(image_fill.block_reasons if image_fill is not None else [])
    if (
        image_fill is not None
        and image_fill.record.get("Mode") == "Fill"
        and runtime_size_dynamic
    ):
        reasons.append(
            "image_fill_runtime_resize_requires_dynamic_uv_binding"
        )
    material = (
        None
        if image_fill is not None
        else painter_style_umg_material(
            style,
            source_kind=source_kind,
            size=_row_size(row, resolved_size),
        )
    )
    if kind == "Unsupported":
        reasons.append("unsupported_object_kind")
    mask = dict(row.get("mask") or {})
    if mask.get("enabled"):
        reasons.append("painter_ui_mask_requires_umg_material_or_bake")
    boolean = dict(content.get("boolean") or {})
    if boolean.get("enabled"):
        reasons.append("painter_ui_boolean_requires_deterministic_bake")
    if content.get("text_ranges"):
        reasons.append("mixed_text_ranges_require_rich_text_conversion")
    if content.get("flip_x") or content.get("flip_y"):
        reasons.append("object_flip_requires_umg_render_transform_support")
    if style.get("font_axes"):
        reasons.append("variable_font_axes_require_unavailable_text_bake")
    remote = dict(content.get("remote_component") or {})
    if remote.get("status") == "missing":
        reasons.append("remote_component_must_be_relinked_or_localized")
    visible_fills = _visible_style_rows(style.get("fills"))
    if len(visible_fills) > 1:
        reasons.append("multiple_fills_require_umg_material_or_bake")
    if isinstance(style.get("fill_gradient"), Mapping) and material is None:
        reasons.append("gradient_material_requires_leaf_rectangle")
    for paint in visible_fills:
        paint_type = str(paint.get("type") or "solid").casefold()
        if paint_type in {"linear", "radial"}:
            if material is None:
                reasons.append("gradient_material_requires_leaf_rectangle")
        elif paint_type == "pattern":
            reasons.append("pattern_fill_requires_deterministic_bake")
        elif paint_type == "image":
            if image_fill is None:
                reasons.append("image_fill_missing_source_path")
        elif paint_type == "video":
            reasons.append("video_fill_requires_runtime_media_adapter")
        elif paint_type == "shader":
            reasons.append("shader_fill_requires_ui_material_or_bake")
        if (
            paint_type != "image"
            and str(paint.get("blend_mode") or "normal").casefold()
            != "normal"
        ):
            reasons.append("fill_blend_mode_requires_deterministic_bake")
    active_strokes = _active_strokes(style)
    if len(active_strokes) > 1:
        reasons.append("multiple_strokes_require_umg_material_or_bake")
    for stroke in active_strokes:
        stroke_type = str(stroke.get("type") or "solid").strip().casefold()
        if stroke_type in {"linear", "radial"}:
            reasons.append("gradient_stroke_requires_deterministic_bake")
        elif stroke_type != "solid":
            reasons.append("unsupported_stroke_requires_deterministic_bake")
        if str(stroke.get("blend_mode") or "normal").casefold() != "normal":
            reasons.append("stroke_blend_mode_requires_deterministic_bake")
    effects = _appearance_effects(style)
    effect_counts = {"drop_shadow": 0, "inner_shadow": 0}
    for effect in effects:
        effect_type = str(effect.get("type") or "").strip().casefold()
        if effect_type in effect_counts:
            effect_counts[effect_type] += 1
            if str(effect.get("blend_mode") or "normal").casefold() != "normal":
                reasons.append("effect_blend_mode_requires_deterministic_bake")
        elif effect_type == "layer_blur":
            reasons.append("layer_blur_requires_deterministic_bake")
        elif effect_type == "background_blur":
            reasons.append("background_blur_requires_native_umg_widget")
        else:
            reasons.append("unsupported_effect_requires_deterministic_bake")
    if effect_counts["drop_shadow"] > 1:
        reasons.append("multiple_drop_shadows_require_deterministic_bake")
    if effect_counts["inner_shadow"] > 1:
        reasons.append("multiple_inner_shadows_require_deterministic_bake")
    if str(style.get("blend_mode") or "normal") not in {
        "normal",
        "pass_through",
    }:
        reasons.append("blend_mode_requires_umg_material")
    appearance_style = dict(style)
    if image_fill is not None:
        # ImageFill owns the corner geometry.  Keep strokes/effects visible to
        # the advanced-appearance checks, but do not ask RoundedCard to paint
        # a second background over the texture.
        appearance_style["radius"] = 0.0
        appearance_style["corner_radii"] = {}
        appearance_style["corner_smoothing"] = 0.0
    if source_kind != "rectangle" and _has_advanced_appearance(
        appearance_style,
        include_uniform_radius=(
            source_kind in _VISIBLE_UNIFORM_RADIUS_KINDS
        ),
    ):
        reasons.append("advanced_appearance_requires_leaf_rectangle")
    if material is not None:
        reasons.extend(
            validate_umg_material_record(material, layer_kind=kind)
        )
        if (
            str(material.get("Kind") or "") == "RoundedCard"
            and runtime_size_dynamic
        ):
            reasons.append(
                "rounded_card_runtime_resize_requires_dynamic_size_binding"
            )
    elif (
        image_fill is None
        and source_kind == "rectangle"
        and _has_advanced_appearance(style)
    ):
        reasons.append("rounded_card_material_unsupported")
    if not reasons:
        return ("Material", []) if material is not None else ("Native", [])
    return "Blocked", sorted(set(reasons))


def painter_ui_to_umg_document(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    source_document = normalize_ui_document(value)
    document = resolve_ui_responsive_document(source_document)
    selected_artboard_id = str(artboard_id or document["active_artboard_id"])
    artboard = next(
        (
            row
            for row in document["artboards"]
            if row["id"] == selected_artboard_id
        ),
        None,
    )
    if artboard is None:
        raise ValueError(f"Painter UI artboard not found: {selected_artboard_id}")
    included_ids = {
        row["id"]
        for row in document["objects"]
        if row["artboard_id"] == selected_artboard_id
    }
    export_rows = sorted(
        (
            row
            for row in document["objects"]
            if row["artboard_id"] == selected_artboard_id
        ),
        key=lambda item: (item["z_index"], item["id"]),
    )
    from app.painter_ui_umg_auto_layout import (
        painter_umg_auto_layout_contract,
    )

    auto_layout_contract = painter_umg_auto_layout_contract(document)
    panel_kind_by_id = dict(auto_layout_contract["panel_kind_by_id"])
    flow_slot_by_id = dict(auto_layout_contract["flow_slot_by_id"])
    layout_blockers_by_id = dict(auto_layout_contract["blockers_by_id"])
    component_by_id = {
        str(row["id"]): row for row in document.get("components", [])
    }
    native_group_ids = {
        row["id"]
        for row in export_rows
        if _umg_kind(str(row["kind"])) == "Group"
        and _umg_disposition(
            row,
            dict(row.get("style") or {}),
            dict(row.get("content") or {}),
            "Group",
        )[0]
        == "Native"
        and row["id"] not in layout_blockers_by_id
    }
    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    root_geometry = {
        "x": 0.0,
        "y": 0.0,
        "width": float(artboard["width"]),
        "height": float(artboard["height"]),
    }
    resources: dict[str, dict[str, Any]] = {}
    layers: list[dict[str, Any]] = []
    for row in export_rows:
        style = dict(row.get("style") or {})
        content = dict(row.get("content") or {})
        slot_property = str(row.get("component_slot_property") or "")
        slot_definition = dict(
            (
                component_by_id.get(str(row.get("component_id") or ""), {})
                .get("property_definitions", {})
                .get(slot_property, {})
            )
            if slot_property
            else {}
        )
        kind = _umg_kind(str(row["kind"]))
        resolved_rect = geometry[row["id"]]
        authored_constraints = normalize_ui_constraints(
            row.get("constraints"),
            width=float(resolved_rect["width"]),
            height=float(resolved_rect["height"]),
        )
        parent_panel_kind = panel_kind_by_id.get(
            str(row.get("parent_id") or ""),
            "None",
        )
        runtime_size_dynamic = (
            _constraints_require_runtime_size(authored_constraints)
            or str(row["id"]) in flow_slot_by_id
            or parent_panel_kind in {"Horizontal", "Vertical", "Grid"}
        )
        disposition, block_reasons = _umg_disposition(
            row,
            style,
            content,
            kind,
            resolved_size=resolved_rect,
            runtime_size_dynamic=runtime_size_dynamic,
        )
        block_reasons = sorted(
            set(
                [
                    *block_reasons,
                    *layout_blockers_by_id.get(str(row["id"]), []),
                    *(
                        ["prototype_sticky_requires_umg_runtime_binding"]
                        if normalize_ui_scroll(row.get("scroll"))["position"]
                        == "sticky"
                        else []
                    ),
                ]
            )
        )
        if block_reasons:
            disposition = "Blocked"
        image_fill_conversion = painter_image_fill_conversion(
            row,
            style,
            content,
            size=resolved_rect,
        )
        material_record = (
            None
            if image_fill_conversion is not None
            else painter_style_umg_material(
                style,
                source_kind=str(row.get("kind") or ""),
                size=_row_size(row, resolved_rect),
            )
        )
        asset_id = ""
        image_fill_record: dict[str, Any] = {}
        source_path = (
            image_fill_conversion.source_path
            if image_fill_conversion is not None
            else ""
        )
        if image_fill_conversion is not None and source_path:
            path = Path(source_path).expanduser()
            asset_id = _resource_id(path, "texture")
            resources[asset_id] = {
                "Id": asset_id,
                "Kind": "texture",
                "SourcePath": str(path),
                "DestinationName": f"TS_{asset_id}",
                "ContentHash": _hash_file(path) if path.is_file() else "",
                "SettingsJson": json.dumps(
                    {"Usage": "ImageFill", "SRGB": True},
                    separators=(",", ":"),
                ),
            }
        if image_fill_conversion is not None:
            image_fill_record = image_fill_conversion.bind_asset(asset_id)
        payload = {
            "source_kind": row["kind"],
            "clip_content": bool(row.get("clip_content", False)),
            "source_params": {
                "shape": (
                    "ellipse" if row["kind"] == "ellipse" else "rectangle"
                ),
                "radius": float(style.get("radius", 0.0) or 0.0),
                "stroke": str(style.get("stroke") or "#00000000"),
                "stroke_width": float(
                    style.get("stroke_width", 0.0) or 0.0
                ),
                "fills": list(style.get("fills") or []),
                "strokes": list(style.get("strokes") or []),
                "blend_mode": str(style.get("blend_mode") or "normal"),
                "corner_radii": dict(style.get("corner_radii") or {}),
                "corner_smoothing": float(
                    style.get("corner_smoothing", 0.0) or 0.0
                ),
                "stroke_align": str(
                    style.get("stroke_align") or "center"
                ),
                "effects": list(style.get("effects") or []),
                "shadow": dict(style.get("shadow") or {}),
            },
            "text": str(content.get("text") or row["name"]),
            "fill": str(
                style.get("text_color")
                if row["kind"] == "text"
                else style.get("fill")
                or "#FFFFFFFF"
            ),
            "font_size": float(style.get("font_size", 16.0) or 16.0),
            "font_axes": dict(style.get("font_axes") or {}),
            "painter_conversion": (
                "ui_material_custom_hlsl"
                if disposition == "Material"
                else "native"
                if row["kind"]
                in {"frame", "group", "text", "image", "button"}
                else "converted_to_slate_image"
            ),
            "token_bindings": dict(row.get("token_bindings") or {}),
            "accessibility": dict(row.get("accessibility") or {}),
            "mask": dict(row.get("mask") or {}),
            "boolean": dict(content.get("boolean") or {}),
            "text_ranges": list(content.get("text_ranges") or []),
            "remote_component": dict(
                content.get("remote_component") or {}
            ),
            "image_fill": dict(image_fill_record),
            "umg_mapping": (
                "ui_material_custom_hlsl"
                if disposition == "Material"
                else "native_or_converted" if disposition == "Native"
                else "blocked_preflight"
            ),
            "umg_block_reasons": (
                block_reasons
            ),
            "auto_layout": {
                "panel_kind": panel_kind_by_id.get(str(row["id"]), "None"),
                "flow_slot": flow_slot_by_id.get(str(row["id"]), {}),
            },
            "component_slot": {
                "property_name": slot_property,
                "mapping": "native_panel_static_content" if slot_property else "none",
                "runtime_mutable": False,
                "description": str(slot_definition.get("description") or ""),
                "preferred_values": list(
                    slot_definition.get("preferred_values") or []
                ),
                "settings": dict(slot_definition.get("slot_settings") or {}),
            },
        }
        effective_parent_id = (
            str(row.get("parent_id") or "")
            if str(row.get("parent_id") or "") in native_group_ids
            else ""
        )
        parent_geometry = (
            geometry[effective_parent_id]
            if effective_parent_id
            else root_geometry
        )
        layout_fields = painter_layer_layout(
            rect=resolved_rect,
            parent_rect=parent_geometry,
            constraints=authored_constraints,
        )
        layers.append(
            {
                "Id": row["id"],
                "ParentId": (
                    row["parent_id"]
                    if row["parent_id"] in included_ids
                    else ""
                ),
                "Name": row["name"],
                "Kind": kind,
                "Disposition": disposition,
                "BlockReasons": block_reasons,
                "PanelKind": panel_kind_by_id.get(str(row["id"]), "None"),
                "FlowSlot": flow_slot_by_id.get(str(row["id"]), {}),
                "ComponentSlot": dict(payload["component_slot"]),
                "ScrollOverflow": normalize_ui_scroll(
                    row.get("scroll")
                )["overflow"].title(),
                "ScrollPosition": normalize_ui_scroll(
                    row.get("scroll")
                )["position"].title(),
                **layout_fields,
                "Scale": {"X": 1.0, "Y": 1.0},
                "RotationDegrees": float(row["rotation"]),
                "Opacity": float(row["opacity"]),
                "AssetId": asset_id,
                "ImageFill": image_fill_record,
                "Material": (
                    material_record if disposition == "Material" else {}
                ),
                "PayloadJson": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )
    interactions = []
    for row in document["interactions"]:
        if row["source_object_id"] not in included_ids:
            continue
        parameters = dict(row.get("parameters") or {})
        interactions.append(
            {
                "ComponentId": row["source_object_id"],
                "Trigger": row["trigger"],
                "Actions": [
                    {
                        "Type": row["action"],
                        "TargetId": (
                            row["target_object_id"]
                            or row["target_artboard_id"]
                            or row["component_id"]
                        ),
                        "Name": row["name"],
                        "ResourceId": "",
                        "ResourcePath": str(parameters.get("uri") or ""),
                        "ValueJson": json.dumps(
                            parameters.get("value"),
                            ensure_ascii=False,
                        ),
                        "ParametersJson": json.dumps(
                            parameters,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                ],
            }
        )
    return {
        "SchemaVersion": TIGER_UMG_SCHEMA_VERSION,
        "Provider": "painter",
        "DocumentId": (
            f"painter-{document['document_id']}-{selected_artboard_id}"
        ),
        "Revision": int(document["revision"]),
        "Width": int(artboard["width"]),
        "Height": int(artboard["height"]),
        "FrameRate": 30.0,
        "DurationMilliseconds": 1000,
        "Resources": list(resources.values()),
        "Layers": layers,
        "Animations": [],
        "Interactions": interactions,
        "PainterSource": {
            "Schema": PAINTER_UMG_ADAPTER_SCHEMA,
            "DocumentId": document["document_id"],
            "ArtboardId": selected_artboard_id,
            "Revision": document["revision"],
            "Sections": [
                row
                for row in document.get("sections", [])
                if any(
                    object_id in included_ids
                    for object_id in row.get("object_ids", [])
                )
            ],
            "Review": dict(
                document.get("linked_targets", {}).get("review", {})
            ),
        },
    }


def preflight_painter_umg(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    document = painter_ui_to_umg_document(value, artboard_id=artboard_id)
    counts = {"Native": 0, "Material": 0, "Baked": 0, "Blocked": 0}
    blockers: list[dict[str, Any]] = []
    for row in document["Layers"]:
        disposition = str(row["Disposition"] or "Blocked")
        counts[disposition] = counts.get(disposition, 0) + 1
        image_reasons = validate_umg_image_fill_record(
            row.get("ImageFill"),
            layer_asset_id=str(row.get("AssetId") or ""),
        )
        if disposition == "Material":
            reasons = [
                *image_reasons,
                *validate_umg_material_record(
                    row.get("Material"),
                    layer_kind=str(row.get("Kind") or ""),
                    document_schema_version=int(document["SchemaVersion"]),
                ),
            ]
            if reasons:
                blockers.append(
                    {
                        "object_id": row["Id"],
                        "name": row["Name"],
                        "reasons": reasons,
                    }
                )
        elif disposition == "Baked":
            blockers.append(
                {
                    "object_id": row["Id"],
                    "name": row["Name"],
                    "reasons": ["baked_generation_unavailable"],
                }
            )
        elif disposition == "Blocked":
            blockers.append(
                {
                    "object_id": row["Id"],
                    "name": row["Name"],
                    "reasons": list(row.get("BlockReasons") or []),
                }
            )
        elif image_reasons:
            blockers.append(
                {
                    "object_id": row["Id"],
                    "name": row["Name"],
                    "reasons": image_reasons,
                }
            )
    missing_resources = [
        row["SourcePath"]
        for row in document["Resources"]
        if not Path(str(row["SourcePath"])).expanduser().is_file()
    ]
    for interaction in document["Interactions"]:
        for action in interaction.get("Actions", []):
            if str(action.get("Type") or "").strip().casefold() == "change_variant":
                blockers.append(
                    {
                        "object_id": str(interaction.get("ComponentId") or ""),
                        "name": str(action.get("Name") or "Change variant"),
                        "reasons": [
                            "interactive_component_change_to_runtime_unsupported"
                        ],
                    }
                )
    return {
        "schema": PAINTER_UMG_ADAPTER_SCHEMA,
        "ok": not blockers and not missing_resources,
        "document_id": document["DocumentId"],
        "artboard_id": document["PainterSource"]["ArtboardId"],
        "counts": counts,
        "blockers": blockers,
        "missing_resources": missing_resources,
        "interaction_count": len(document["Interactions"]),
        "resource_count": len(document["Resources"]),
    }


def package_painter_umg(
    value: Mapping[str, Any],
    output_dir: str | Path,
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    document = painter_ui_to_umg_document(value, artboard_id=artboard_id)
    root = Path(output_dir).expanduser().resolve()
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    packaged = json.loads(json.dumps(document, ensure_ascii=False))
    missing: list[str] = []
    copied: list[str] = []
    for row in packaged["Resources"]:
        source = Path(str(row["SourcePath"])).expanduser()
        if not source.is_file():
            missing.append(str(source))
            continue
        destination = assets / f"{row['Id']}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        row["SourcePath"] = destination.relative_to(root).as_posix()
        row["ContentHash"] = _hash_file(destination)
        copied.append(str(destination))
    document_path = root / "tiger_umg_document.json"
    document_path.write_text(
        json.dumps(packaged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    preflight = preflight_painter_umg(value, artboard_id=artboard_id)
    return {
        "ok": preflight["ok"] and not missing,
        "document_path": str(document_path),
        "asset_count": len(packaged["Resources"]),
        "copied": copied,
        "missing": missing,
        "document": packaged,
        "preflight": preflight,
    }


def generate_painter_umg(
    value: Mapping[str, Any],
    *,
    project_path: str | Path,
    output_dir: str | Path,
    artboard_id: str = "",
    destination_root: str = "/Game/TigerStudio/Generated",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    package = package_painter_umg(
        value,
        output_dir,
        artboard_id=artboard_id,
    )
    if not package["ok"]:
        return package
    from app.unreal_umg_workflow import run_unreal_umg_generation

    generated = run_unreal_umg_generation(
        project_path,
        package["document_path"],
        destination_root=destination_root,
        timeout_seconds=timeout_seconds,
    )
    return {**generated, "package": package}


__all__ = [
    "PAINTER_UMG_ADAPTER_SCHEMA",
    "TIGER_UMG_SCHEMA_VERSION",
    "generate_painter_umg",
    "package_painter_umg",
    "painter_ui_to_umg_document",
    "preflight_painter_umg",
]
