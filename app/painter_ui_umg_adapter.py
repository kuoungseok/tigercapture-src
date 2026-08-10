"""Painter provider adapter for the shared TigerStudioUMG backend."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_constraints import (
    normalize_ui_constraints,
    resolve_ui_constraints,
)
from app.painter_ui_appearance import ui_effect_render_block_reasons
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_components import (
    component_property_defaults,
    component_variant_properties,
    normalize_ui_component_properties,
    normalize_ui_component_property_bindings,
    normalize_ui_component_property_definitions,
    normalize_ui_component_state_overrides,
    normalize_ui_instance_overrides,
    resolve_ui_component_document,
)
from app.painter_ui_motion_bridge import resolved_ui_geometry
from app.painter_ui_scroll import normalize_ui_scroll
from app.unreal_umg_layout import (
    TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION,
    TIGER_UMG_SCHEMA_VERSION,
    TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION,
    painter_layer_layout,
    validate_umg_panel_record,
    validate_umg_widget_visibility,
)
from app.unreal_umg_button import (
    TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION,
    painter_button_style_conversion,
    validate_umg_button_style_record,
)
from app.unreal_umg_baked import (
    SUPPORTED_TIGER_UMG_SCHEMA_VERSION,
    STATIC_APPEARANCE_BAKE_GATE,
    STATIC_APPEARANCE_BAKE_SCHEMA_VERSION,
    STATIC_TEXTURE_BAKE_GATE,
    STATIC_TEXTURE_BAKE_SCHEMA_VERSION,
    STATIC_VECTOR_BAKE_GATE,
    validate_umg_materialized_baked_layer,
    validate_umg_resource_identity_contract,
    validate_umg_static_appearance_source_plan,
    validate_umg_static_vector_source_plan,
)
from app.unreal_umg_document import (
    inspect_umg_document_records,
    validated_umg_disposition,
)
from app.unreal_umg_component import (
    TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION,
    UMG_STATIC_COMPONENT_BINDINGS,
    validate_umg_component_contract,
)
from app.unreal_umg_image_fill import (
    painter_image_fill_conversion,
    validate_umg_image_fill_record,
)
from app.unreal_umg_flipbook import (
    painter_flipbook_conversion,
    validate_umg_flipbook_record,
)
from app.unreal_umg_material import (
    TIGER_UMG_ROUNDED_CARD_DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION,
    painter_style_umg_material,
    validate_umg_material_record,
)
from app.unreal_umg_static_vector_bake import (
    expand_umg_layer_for_static_bake,
    plan_static_vector_bake,
    write_static_vector_bake,
)
from app.unreal_umg_static_appearance_bake import (
    STATIC_APPEARANCE_BAKE_KIND,
    STATIC_TEXTURE_BAKE_KIND,
    plan_static_appearance_bake,
    write_static_appearance_bake,
)


PAINTER_UMG_ADAPTER_SCHEMA = "tigerstudio.painter.ui.umg_adapter.v12"
PAINTER_UMG_FONT_SIZE_UNIT = "css_px_96dpi"
_VISIBLE_UNIFORM_RADIUS_KINDS = {"button", "frame", "image"}
_DYNAMIC_CANVAS_CONSTRAINTS = {"stretch", "scale"}
_ARTBOARD_BACKGROUND_LAYER_ID = "__tiger_artboard_background"


def _apply_static_vector_gate_transition(
    block_reasons: list[str],
    plan: Mapping[str, Any],
) -> tuple[list[str], dict[str, list[str]]]:
    """Apply only the one deterministic-bake gate a safe plan satisfies.

    The returned transition is direct evidence from the conversion point.  It
    deliberately retains arbitrary unrelated reasons byte-for-byte instead of
    reconstructing a hypothetical pre-bake state later in QA.
    """

    before = sorted(set(str(reason) for reason in block_reasons if str(reason)))
    after = list(before)
    satisfied: list[str] = []
    status = str(plan.get("status") or "")
    if status == "unsafe":
        after = sorted(
            set(
                [
                    *after,
                    *(
                        str(reason)
                        for reason in plan.get("reasons", [])
                        if str(reason)
                    ),
                ]
            )
        )
    elif plan.get("available") is True:
        if STATIC_VECTOR_BAKE_GATE in after:
            after.remove(STATIC_VECTOR_BAKE_GATE)
            satisfied.append(STATIC_VECTOR_BAKE_GATE)
        else:
            after.append("figma_vector_static_bake_gate_transition_missing")
            after.sort()
    return after, {
        "before": before,
        "after": after,
        "satisfied": satisfied,
    }


def _apply_static_appearance_gate_transition(
    block_reasons: list[str],
    plan: Mapping[str, Any],
) -> tuple[list[str], dict[str, list[str]]]:
    """Remove only the effect-specific gate proven by an available plan."""

    before = sorted(set(str(reason) for reason in block_reasons if str(reason)))
    after = list(before)
    satisfied: list[str] = []
    status = str(plan.get("status") or "")
    if status == "unsafe":
        after = sorted(
            set(
                [
                    *after,
                    *(
                        str(reason)
                        for reason in plan.get("reasons", [])
                        if str(reason)
                    ),
                ]
            )
        )
    elif plan.get("available") is True:
        kind = str(plan.get("kind") or "")
        expected_gate = (
            STATIC_TEXTURE_BAKE_GATE
            if kind == STATIC_TEXTURE_BAKE_KIND
            else STATIC_APPEARANCE_BAKE_GATE
            if kind == STATIC_APPEARANCE_BAKE_KIND
            else ""
        )
        intended_gate = str(plan.get("intended_gate") or "")
        if not expected_gate or intended_gate != expected_gate:
            after.append("figma_appearance_static_bake_contract_mismatch")
            after.sort()
        elif intended_gate in after:
            after.remove(intended_gate)
            satisfied.append(intended_gate)
        else:
            after.append("figma_appearance_static_bake_gate_transition_missing")
            after.sort()
    return after, {
        "before": before,
        "after": after,
        "satisfied": satisfied,
    }


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


def _canonical_umg_color(
    value: object,
    *,
    default: str = "#FFFFFFFF",
) -> str:
    source = str(value or "").strip()
    if source.casefold() == "transparent":
        return "#00000000"
    source = source.removeprefix("#")
    if len(source) in {3, 4} and all(
        character in "0123456789abcdefABCDEF" for character in source
    ):
        source = "".join(character * 2 for character in source)
    if len(source) == 6 and all(
        character in "0123456789abcdefABCDEF" for character in source
    ):
        return f"#{source.upper()}FF"
    if len(source) == 8 and all(
        character in "0123456789abcdefABCDEF" for character in source
    ):
        return f"#{source.upper()}"
    return str(default)


def _artboard_background_contract(
    artboard: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    color = _canonical_umg_color(artboard.get("background"))
    included = int(color[-2:], 16) > 0
    metadata = {
        "mode": "included" if included else "transparent",
        "color": color,
        "layer_id": _ARTBOARD_BACKGROUND_LAYER_ID if included else "",
    }
    if not included:
        return None, metadata
    width = max(1.0, float(artboard.get("width", 1.0) or 1.0))
    height = max(1.0, float(artboard.get("height", 1.0) or 1.0))
    layout_fields = painter_layer_layout(
        rect={"x": 0.0, "y": 0.0, "width": width, "height": height},
        parent_rect={
            "x": 0.0,
            "y": 0.0,
            "width": width,
            "height": height,
        },
        constraints={
            "horizontal": "stretch",
            "vertical": "stretch",
            "pivot_x": 0.0,
            "pivot_y": 0.0,
        },
    )
    payload = {
        "source_kind": "rectangle",
        "source_params": {
            "shape": "rectangle",
            "radius": 0.0,
            "stroke": "#00000000",
            "stroke_width": 0.0,
        },
        "text": "",
        "fill": color,
        "font_size": 16.0,
        "font_size_unit": PAINTER_UMG_FONT_SIZE_UNIT,
        "source_visible": True,
        "painter_conversion": "native",
        "umg_mapping": "native_or_converted",
        "umg_block_reasons": [],
        "artboard_background": True,
        "hit_test_visibility": "HitTestInvisible",
    }
    return {
        "Id": _ARTBOARD_BACKGROUND_LAYER_ID,
        "ParentId": "",
        "Name": "Artboard Background",
        "Kind": "Image",
        "Disposition": "Native",
        "BlockReasons": [],
        "PanelKind": "None",
        "FlowSlot": {},
        "SpacingStrategy": "Padding",
        "SpacerSizeRule": "Auto",
        "SpacerFillCoefficient": 1.0,
        "ComponentSlot": {},
        "ScrollOverflow": "None",
        "ScrollPosition": "Scroll",
        "Visibility": "HitTestInvisible",
        **layout_fields,
        "Scale": {"X": 1.0, "Y": 1.0},
        "RotationDegrees": 0.0,
        "Opacity": 1.0,
        "AssetId": "",
        "ImageFill": {},
        "Flipbook": {},
        "ButtonStyle": {},
        "Material": {},
        "PayloadJson": json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }, metadata


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


def _color_has_visible_alpha(value: object) -> bool:
    source = str(value or "").strip()
    if not source:
        return False
    color = _canonical_umg_color(source, default="#00000000")
    return int(color[-2:], 16) > 0


def _has_visible_surface_paint(style: Mapping[str, Any]) -> bool:
    """Return whether a container visibly paints its own leaf surface.

    Frames and groups are normally structural UMG panels.  A childless one,
    however, cannot contribute container semantics and Painter still renders
    its fill/stroke/effects.  This predicate keeps that exception narrow and
    avoids turning transparent structural groups into Images.
    """

    if isinstance(style.get("fill_gradient"), Mapping):
        return True
    for paint in _visible_style_rows(style.get("fills")):
        if float(paint.get("opacity", 1.0) or 0.0) <= 0.0001:
            continue
        paint_type = str(paint.get("type") or "solid").strip().casefold()
        if paint_type != "solid" or _color_has_visible_alpha(
            paint.get("color", style.get("fill"))
        ):
            return True
    if _color_has_visible_alpha(style.get("fill")):
        return True
    if _active_strokes(style) or _appearance_effects(style):
        return True
    return (
        float(style.get("stroke_width", 0.0) or 0.0) > 0.0001
        and _color_has_visible_alpha(style.get("stroke"))
    )


def _is_painted_leaf_container(
    row: Mapping[str, Any],
    parent_ids_with_children: set[str],
) -> bool:
    return (
        str(row.get("kind") or "").strip().casefold() in {"frame", "group"}
        and str(row.get("id") or "") not in parent_ids_with_children
        and _has_visible_surface_paint(dict(row.get("style") or {}))
    )


def _leaf_rectangle_conversion_row(
    row: Mapping[str, Any],
    *,
    painted_leaf_container: bool,
) -> Mapping[str, Any]:
    if not painted_leaf_container:
        return row
    # Keep every provider id/layout/content field intact.  Only the effective
    # primitive kind crosses the existing leaf-rectangle conversion boundary.
    return {**row, "kind": "rectangle"}


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


def _flow_slot_requires_runtime_size(
    parent_kind: str,
    flow_slot: Mapping[str, Any],
) -> bool:
    horizontal = str(
        flow_slot.get("HorizontalAlignment") or "Fill"
    ).casefold()
    vertical = str(
        flow_slot.get("VerticalAlignment") or "Fill"
    ).casefold()
    size_rule = str(flow_slot.get("SizeRule") or "Auto").casefold()
    if parent_kind == "Horizontal":
        return (
            size_rule == "fill" and horizontal == "fill"
        ) or vertical == "fill"
    if parent_kind == "Vertical":
        return (
            size_rule == "fill" and vertical == "fill"
        ) or horizontal == "fill"
    if parent_kind in {"Grid", "Overlay"}:
        return horizontal == "fill" or vertical == "fill"
    return False


def _umg_layer_requires_runtime_size(
    layer: Mapping[str, Any],
    parent_panel_kinds: Mapping[str, str],
    *,
    synthetic_overlay_root_ids: set[str] | frozenset[str] = frozenset(),
) -> bool:
    """Mirror the Unreal preflight's runtime-size classification."""
    # NamedSlot replacement roots are grafted into a generated UOverlay even
    # though their serialized ParentId remains the owning component instance.
    # Treat that generated parent as authoritative so preflight cannot accept
    # a FixedSize RoundedCard that the real WidgetTree will stretch.
    synthetic_overlay = (
        str(layer.get("Id") or "") in synthetic_overlay_root_ids
    )
    if not synthetic_overlay:
        slot = layer.get("CanvasSlot")
        slot = slot if isinstance(slot, Mapping) else {}
        anchor_min = slot.get("AnchorMinimum")
        anchor_min = anchor_min if isinstance(anchor_min, Mapping) else {}
        anchor_max = slot.get("AnchorMaximum")
        anchor_max = anchor_max if isinstance(anchor_max, Mapping) else {}
        if any(
            abs(
                float(anchor_max.get(axis, 0.0))
                - float(anchor_min.get(axis, 0.0))
            )
            > 0.000001
            for axis in ("X", "Y")
        ):
            return True
    parent_kind = (
        "Overlay"
        if synthetic_overlay
        else str(
            parent_panel_kinds.get(str(layer.get("ParentId") or "")) or ""
        )
    )
    flow_slot = layer.get("FlowSlot")
    flow_slot = flow_slot if isinstance(flow_slot, Mapping) else {}
    return _flow_slot_requires_runtime_size(parent_kind, flow_slot)


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
    button_style = painter_button_style_conversion(row, style, content)
    reasons.extend(
        button_style.block_reasons if button_style is not None else []
    )
    flipbook = painter_flipbook_conversion(row, style, content)
    reasons.extend(flipbook.block_reasons if flipbook is not None else [])
    flipbook_bake = content.get("flipbook_bake")
    if isinstance(flipbook_bake, Mapping):
        bake_reasons = [
            str(reason)
            for reason in flipbook_bake.get("block_reasons", [])
            if str(reason or "")
        ]
        reasons.extend(bake_reasons)
        if (
            flipbook_bake.get("material_ready") is False
            and not bake_reasons
        ):
            reasons.append("flipbook_bake_not_material_ready")
    image_fill = (
        None
        if flipbook is not None
        else painter_image_fill_conversion(
            row,
            style,
            content,
            size=(
                resolved_size
                if isinstance(resolved_size, Mapping)
                else row
            ),
        )
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
        or flipbook is not None
        or button_style is not None
        else painter_style_umg_material(
            style,
            source_kind=source_kind,
            size=_row_size(row, resolved_size),
        )
    )
    if material is not None and str(material.get("Kind") or "") == "RoundedCard":
        material["SizeBinding"] = (
            "WidgetGeometry" if runtime_size_dynamic else "FixedSize"
        )
    if kind == "Unsupported":
        reasons.append("unsupported_object_kind")
    component_bindings = normalize_ui_component_property_bindings(
        row.get("component_property_bindings")
    )
    if any(
        target_path not in {"content.text", "visible"}
        for target_path in component_bindings
    ):
        reasons.append(
            "figma_component_property_binding_requires_umg_component_parameter_binding"
        )
    recovered_component_property_bindings = content.get(
        "figma_component_property_bindings"
    )
    if isinstance(recovered_component_property_bindings, Mapping):
        for target_path in recovered_component_property_bindings:
            if str(target_path).startswith("figma_field:"):
                raw_field = str(target_path).split(":", 1)[1]
                reasons.append(
                    "figma_component_property_reference_field_unsupported"
                    if raw_field
                    not in {"characters", "visible", "mainComponent"}
                    else "figma_component_property_reference_value_missing"
                )
            else:
                reasons.append(
                    "figma_component_property_binding_requires_component_relink"
                )
    mask = dict(row.get("mask") or {})
    if mask.get("enabled"):
        reasons.append("painter_ui_mask_requires_umg_material_or_bake")
        figma_mask = content.get("figma_mask")
        if (
            isinstance(figma_mask, Mapping)
            and figma_mask.get("requires_raster_alpha")
        ):
            reasons.append(
                "figma_mask_raster_alpha_requires_deterministic_bake"
            )
    boolean = dict(content.get("boolean") or {})
    if boolean.get("enabled"):
        reasons.append("painter_ui_boolean_requires_deterministic_bake")
    if content.get("text_ranges"):
        reasons.append("mixed_text_ranges_require_rich_text_conversion")
    if content.get("flip_x") or content.get("flip_y"):
        reasons.append("object_flip_requires_umg_render_transform_support")
    if content.get("figma_unsupported_paints"):
        reasons.append("figma_conic_or_diamond_gradient_requires_material_or_bake")
    if isinstance(content.get("figma_auto_layout_recovery"), Mapping):
        reasons.append(
            "figma_transformed_auto_layout_requires_affine_layout"
        )
    affine_recovery = content.get("figma_affine_snapshot_geometry")
    if (
        isinstance(affine_recovery, Mapping)
        and str(affine_recovery.get("status") or "").startswith("blocked_")
    ):
        reasons.append(
            str(
                affine_recovery.get("reason")
                or "figma_affine_snapshot_requires_transform_support"
            )
        )
    vector_recovery = content.get("figma_vector_geometry_recovery")
    figma_type = str(content.get("figma_type") or "").upper()
    is_vector_geometry_object = figma_type in {
        "BOOLEAN_OPERATION",
        "LINE",
        "POLYGON",
        "REGULAR_POLYGON",
        "STAR",
        "VECTOR",
    }
    has_editable_vector_geometry = bool(
        content.get("vector_paths")
        or content.get("vector_fill_geometry")
        or content.get("vector_stroke_geometry")
    )
    if is_vector_geometry_object and has_editable_vector_geometry:
        reasons.append(
            "figma_vector_geometry_requires_deterministic_bake"
        )
    elif (
        is_vector_geometry_object
        and not (
            isinstance(vector_recovery, Mapping)
            and vector_recovery.get("source") == "figma_render_api"
        )
    ):
        reasons.append("figma_vector_source_geometry_missing")
    if (
        isinstance(vector_recovery, Mapping)
        and vector_recovery.get("source") == "figma_render_api"
    ):
        reasons.append(
            "figma_vector_render_fallback_requires_deterministic_bake"
        )
    elif (
        isinstance(vector_recovery, Mapping)
        and vector_recovery.get("source") == "semantic_primitive"
        and vector_recovery.get("kind") != "rectangle"
    ):
        reasons.append(
            "figma_semantic_vector_primitive_requires_deterministic_bake"
        )
    variable_bindings = content.get("figma_variable_bindings")
    if isinstance(variable_bindings, list) and any(
        isinstance(binding, Mapping)
        and str(binding.get("status") or "") != "native"
        for binding in variable_bindings
    ):
        reasons.append("figma_variable_binding_requires_token_relink")
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
            if image_fill is None and flipbook is None:
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
    individual_stroke_weights = style.get("individual_stroke_weights")
    if isinstance(individual_stroke_weights, Mapping):
        reasons.append(
            "figma_individual_stroke_weights_require_deterministic_bake"
        )
    if isinstance(style.get("stroke_dash"), list) and style.get("stroke_dash"):
        reasons.append("figma_dashed_stroke_requires_deterministic_bake")
    if str(style.get("stroke_cap") or "none").casefold() not in {
        "none",
        "butt",
    }:
        reasons.append("figma_stroke_cap_requires_deterministic_bake")
    if str(style.get("stroke_join") or "miter").casefold() != "miter":
        reasons.append("figma_stroke_join_requires_deterministic_bake")
    if abs(float(style.get("stroke_miter_limit", 4.0) or 4.0) - 4.0) > 0.0001:
        reasons.append(
            "figma_stroke_miter_angle_requires_deterministic_bake"
        )
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
        exact_render_reasons = ui_effect_render_block_reasons(
            effect,
            exact_render=content.get("figma_exact_render"),
        )
        if exact_render_reasons:
            reasons.extend(exact_render_reasons)
            continue
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
    if (
        source_kind != "rectangle"
        and not (button_style is not None and not button_style.block_reasons)
        and _has_advanced_appearance(
        appearance_style,
        include_uniform_radius=(
            source_kind in _VISIBLE_UNIFORM_RADIUS_KINDS
        ),
        )
    ):
        reasons.append("advanced_appearance_requires_leaf_rectangle")
    if material is not None:
        reasons.extend(
            validate_umg_material_record(material, layer_kind=kind)
        )
        if (
            str(material.get("Kind") or "") == "RoundedCard"
            and runtime_size_dynamic
            and str(material.get("SizeBinding") or "FixedSize")
            != "WidgetGeometry"
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
        return (
            ("Material", [])
            if material is not None or flipbook is not None
            else ("Native", [])
        )
    return "Blocked", sorted(set(reasons))


def _prepare_painter_umg_conversion(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    """Build document-wide UMG inputs once for one or many artboards."""
    source_document = normalize_ui_document(value)
    from app.painter_ui_themes import resolve_ui_theme_document

    # UMG must consume the same active theme/token values that Painter draws.
    # Keeping token ids in ``token_bindings`` still preserves authoring
    # provenance; only the exported static style is resolved here.
    document = resolve_ui_theme_document(source_document, normalize=False)
    # Static component properties and per-instance overrides must feed the
    # same visual conversion as Painter's canvas.  Schema 18 also preserves
    # their reusable meaning separately; resolving here is not a flattening
    # substitute, it is the static value used for exact preview/export.
    document = resolve_ui_component_document(document, normalize=False)
    from app.painter_ui_umg_auto_layout import (
        painter_umg_auto_layout_contract,
    )

    auto_layout_contract = painter_umg_auto_layout_contract(document)
    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    artboards_by_id = {
        str(row["id"]): row for row in document["artboards"]
    }
    objects_by_artboard: dict[str, list[Mapping[str, Any]]] = {
        artboard_id: [] for artboard_id in artboards_by_id
    }
    object_artboard_by_id: dict[str, str] = {}
    for row in document["objects"]:
        current_artboard_id = str(row["artboard_id"])
        objects_by_artboard.setdefault(current_artboard_id, []).append(row)
        object_artboard_by_id[str(row["id"])] = current_artboard_id
    for rows in objects_by_artboard.values():
        rows.sort(key=lambda item: (item["z_index"], item["id"]))

    interactions_by_artboard: dict[str, list[Mapping[str, Any]]] = {}
    for row in document["interactions"]:
        current_artboard_id = object_artboard_by_id.get(
            str(row["source_object_id"])
        )
        if current_artboard_id:
            interactions_by_artboard.setdefault(
                current_artboard_id,
                [],
            ).append(row)

    sections_by_artboard: dict[str, list[Mapping[str, Any]]] = {}
    for section in document.get("sections", []):
        section_artboard_ids = {
            object_artboard_by_id.get(str(object_id), "")
            for object_id in section.get("object_ids", [])
        }
        for current_artboard_id in section_artboard_ids - {""}:
            sections_by_artboard.setdefault(
                current_artboard_id,
                [],
            ).append(section)
    return {
        "document": document,
        "artboards_by_id": artboards_by_id,
        "objects_by_artboard": objects_by_artboard,
        "interactions_by_artboard": interactions_by_artboard,
        "sections_by_artboard": sections_by_artboard,
        "auto_layout_contract": auto_layout_contract,
        "component_by_id": {
            str(row["id"]): row for row in document.get("components", [])
        },
        "geometry": geometry,
    }


def _component_object_children(
    document: Mapping[str, Any],
) -> dict[str, list[Mapping[str, Any]]]:
    children: dict[str, list[Mapping[str, Any]]] = {}
    for row in document.get("objects", []):
        if not isinstance(row, Mapping):
            continue
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)
    for rows in children.values():
        rows.sort(
            key=lambda item: (
                int(item.get("z_index") or 0),
                str(item.get("id") or ""),
            )
        )
    return children


def _component_subtree_ids(
    root_id: str,
    children: Mapping[str, list[Mapping[str, Any]]],
) -> list[str]:
    ordered: list[str] = []

    def visit(object_id: str) -> None:
        ordered.append(object_id)
        for child in children.get(object_id, []):
            visit(str(child.get("id") or ""))

    if root_id:
        visit(str(root_id))
    return ordered


def _is_component_instance_root(
    row: Mapping[str, Any],
    component_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    component = component_by_id.get(str(row.get("component_id") or ""))
    return bool(
        component is not None
        and str(row.get("component_role") or "") == "instance"
        and str(row.get("component_source_object_id") or "")
        == str(component.get("root_object_id") or "")
    )


def _component_source_id(
    row: Mapping[str, Any],
    component_id: str,
) -> str:
    if str(row.get("component_scope_id") or "") == component_id:
        return str(row.get("component_scope_source_object_id") or "")
    if str(row.get("component_id") or "") == component_id:
        return str(row.get("component_source_object_id") or "")
    return ""


def _instance_slot_content_roots(
    document: Mapping[str, Any],
    instance_root: Mapping[str, Any],
    component: Mapping[str, Any],
    *,
    children: Mapping[str, list[Mapping[str, Any]]],
    object_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    component_id = str(component.get("id") or "")
    member_ids = set(
        _component_subtree_ids(str(instance_root.get("id") or ""), children)
    )
    definitions = normalize_ui_component_property_definitions(
        component.get("property_definitions")
    )
    contents: list[dict[str, Any]] = []
    for property_name, definition in definitions.items():
        if str(definition.get("type") or "") != "slot":
            continue
        source_slot_id = str(definition.get("default") or "")
        slot = next(
            (
                object_by_id[object_id]
                for object_id in member_ids
                if object_id in object_by_id
                and _component_source_id(
                    object_by_id[object_id], component_id
                )
                == source_slot_id
            ),
            None,
        )
        roots: list[str] = []
        if slot is not None:
            for child in children.get(str(slot.get("id") or ""), []):
                # A source-mapped child is the reusable component's default
                # slot content.  Only locally inserted roots belong to this
                # concrete instance's NamedSlot graft.
                if _component_source_id(child, component_id):
                    continue
                roots.append(str(child.get("id") or ""))
        contents.append(
            {
                "SlotName": str(property_name),
                "RootLayerIds": roots,
            }
        )
    return contents


def _flatten_component_override_changes(
    value: Mapping[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        name = str(key)
        path = f"{prefix}.{name}" if prefix else name
        if isinstance(item, Mapping) and name in {
            "style",
            "content",
            "layout",
            "constraints",
            "token_bindings",
            "accessibility",
        }:
            flattened.update(
                _flatten_component_override_changes(item, prefix=path)
            )
        else:
            flattened[path] = copy.deepcopy(item)
    return flattened


_DERIVABLE_INSTANCE_OVERRIDE_PATHS = ("content.text", "visible")


def _derived_instance_overrides(
    row: Mapping[str, Any],
    definition_row: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return the authored values an expanded instance holds over its source.

    Figma expands an instance into descendants that carry the authored values
    instead of recording them as overrides, so a row can differ from its
    definition while reporting no overrides at all. Replaying the definition
    then silently changes the information: a button labelled "Start" arrives as
    the default "Get started".

    Only the paths UMG can actually replay at runtime are derived. Widening
    this to style would not improve fidelity, because every derived path outside
    that set becomes an unsupported-override blocker below; those differences
    keep resolving to the definition exactly as they do today.
    """

    if definition_row is None:
        return {}
    derived: dict[str, Any] = {}
    for path in _DERIVABLE_INSTANCE_OVERRIDE_PATHS:
        if path == "visible":
            authored = bool(row.get("visible", True))
            source = bool(definition_row.get("visible", True))
        else:
            content = row.get("content")
            source_content = definition_row.get("content")
            authored = str(
                (content if isinstance(content, Mapping) else {}).get("text")
                or ""
            )
            source = str(
                (
                    source_content
                    if isinstance(source_content, Mapping)
                    else {}
                ).get("text")
                or ""
            )
        if authored != source:
            derived[path] = authored
    return derived


def _instance_resolved_overrides(
    document: Mapping[str, Any],
    instance_root: Mapping[str, Any],
    component: Mapping[str, Any],
    *,
    children: Mapping[str, list[Mapping[str, Any]]],
    object_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    component_id = str(component.get("id") or "")
    resolved: dict[str, dict[str, Any]] = {}
    properties = component_property_defaults(component)
    properties.update(
        normalize_ui_component_properties(
            instance_root.get("component_properties")
        )
    )
    active_state = str(properties.get("state") or "normal").casefold()
    state_rows = normalize_ui_component_state_overrides(
        component.get("state_overrides")
    ).get(active_state, {})
    for source_id, changes in state_rows.items():
        if isinstance(changes, Mapping):
            resolved.setdefault(str(source_id), {}).update(
                _flatten_component_override_changes(changes)
            )
    for object_id in _component_subtree_ids(
        str(instance_root.get("id") or ""), children
    ):
        row = object_by_id.get(object_id)
        if row is None:
            continue
        source_id = _component_source_id(row, component_id)
        overrides = normalize_ui_instance_overrides(
            row.get("instance_overrides")
        )
        if source_id and not overrides:
            overrides = _derived_instance_overrides(
                row,
                object_by_id.get(source_id),
            )
        if (
            object_id == str(instance_root.get("id") or "")
            and source_id == str(component.get("root_object_id") or "")
        ):
            # The instance UUserWidget's screen/parent slot already owns its
            # allocated width and height. The component definition root fills
            # that live allocation, so replaying these as child overrides is
            # both redundant and unsupported by UMG.
            overrides = {
                path: item
                for path, item in overrides.items()
                if path not in {"width", "height"}
            }
        if source_id and overrides:
            resolved.setdefault(source_id, {}).update(copy.deepcopy(overrides))
    supported_override_paths = {"content.text", "visible"}
    blockers = sorted(
        {
            "component_instance_override_runtime_unsupported:"
            f"{path}"
            for changes in resolved.values()
            for path in changes
            if path not in supported_override_paths
        }
    )
    return resolved, blockers


def _component_property_records(
    document: Mapping[str, Any],
    component: Mapping[str, Any],
    *,
    subtree_ids: set[str],
) -> list[dict[str, Any]]:
    component_id = str(component.get("id") or "")
    definitions = normalize_ui_component_property_definitions(
        component.get("property_definitions")
    )
    binding_rows: dict[str, list[dict[str, str]]] = {
        name: [] for name in definitions
    }
    for row in document.get("objects", []):
        if not isinstance(row, Mapping) or str(row.get("id") or "") not in subtree_ids:
            continue
        owned_definition_row = (
            str(row.get("component_id") or "") == component_id
            and str(row.get("component_role") or "") == "definition"
        )
        scoped_nested_row = (
            str(row.get("component_scope_id") or "") == component_id
            and bool(_component_source_id(row, component_id))
        )
        if not (owned_definition_row or scoped_nested_row):
            continue
        for target_path, property_name in normalize_ui_component_property_bindings(
            row.get("component_property_bindings")
        ).items():
            if property_name in binding_rows:
                binding_rows[property_name].append(
                    {
                        "LayerId": str(row.get("id") or ""),
                        "TargetPath": str(target_path),
                    }
                )
    return [
        {
            "Name": str(name),
            "Type": str(definition.get("type") or "text"),
            "DefaultValueJson": json.dumps(
                definition.get("default"),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            "Description": str(definition.get("description") or ""),
            "Values": [
                str(item) for item in definition.get("values", [])
            ],
            "Bindings": sorted(
                binding_rows.get(name, []),
                key=lambda item: (item["LayerId"], item["TargetPath"]),
            ),
        }
        for name, definition in definitions.items()
    ]


def _component_property_values(
    instance_root: Mapping[str, Any],
    component: Mapping[str, Any],
) -> dict[str, Any]:
    values = component_property_defaults(component)
    values.update(
        normalize_ui_component_properties(
            instance_root.get("resolved_component_properties")
            or instance_root.get("component_properties")
        )
    )
    # A variant component id is the static runtime selection.  Its authored
    # tuple therefore wins over stale/default instance property storage.
    values.update(component_variant_properties(component))
    return values


def _add_layer_block_reasons(
    layer: dict[str, Any],
    reasons: list[str],
) -> dict[str, Any]:
    if not reasons:
        return layer
    result = copy.deepcopy(layer)
    merged = sorted(
        set(
            [
                *(str(reason) for reason in result.get("BlockReasons", [])),
                *(str(reason) for reason in reasons),
            ]
        )
    )
    result["Disposition"] = "Blocked"
    result["BlockReasons"] = merged
    try:
        payload = json.loads(str(result.get("PayloadJson") or "{}"))
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["umg_block_reasons"] = merged
    payload["umg_mapping"] = "blocked_preflight"
    result["PayloadJson"] = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return result


def _attach_component_instance_payload(
    layer: dict[str, Any],
    *,
    instance_id: str,
    component_id: str,
    property_values: Mapping[str, Any],
    resolved_overrides: Mapping[str, Any],
    slot_contents: list[dict[str, Any]],
) -> dict[str, Any]:
    result = copy.deepcopy(layer)
    try:
        payload = json.loads(str(result.get("PayloadJson") or "{}"))
    except (TypeError, ValueError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload["component_instance"] = {
        "id": str(instance_id),
        "component_id": str(component_id),
        "property_values": copy.deepcopy(dict(property_values)),
        "resolved_overrides": copy.deepcopy(dict(resolved_overrides)),
        "slot_contents": copy.deepcopy(slot_contents),
    }
    # A component placement is represented by the generated UUserWidget, not
    # by the source root's leaf visual.  Rounded/image/button roots can carry a
    # Material, ImageFill, Flipbook, or ButtonStyle in the flat artboard pass;
    # leaving that disposition attached makes the schema-18 component contract
    # reject an otherwise valid instance and would duplicate the definition's
    # visual if generation ever consumed both records.
    result["Disposition"] = "Native"
    result["BlockReasons"] = []
    result["AssetId"] = ""
    result["ImageFill"] = {}
    result["Flipbook"] = {}
    result["ButtonStyle"] = {}
    result["Material"] = {}
    payload["painter_conversion"] = "component_instance"
    payload["umg_mapping"] = "native_component_instance"
    payload["umg_block_reasons"] = []
    result["PayloadJson"] = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return result


def _localize_component_root_layer(
    layer: dict[str, Any],
    root_rect: Mapping[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(layer)
    result["ParentId"] = ""
    origin_x = float(root_rect.get("x") or 0.0)
    origin_y = float(root_rect.get("y") or 0.0)
    position = result.get("Position")
    if isinstance(position, Mapping):
        result["Position"] = {
            "X": float(position.get("X") or 0.0) - origin_x,
            "Y": float(position.get("Y") or 0.0) - origin_y,
        }
    canvas_slot = result.get("CanvasSlot")
    if isinstance(canvas_slot, Mapping):
        result["CanvasSlot"] = {
            "AnchorMinimum": {"X": 0.0, "Y": 0.0},
            "AnchorMaximum": {"X": 1.0, "Y": 1.0},
            "Offsets": {
                "Left": 0.0,
                "Top": 0.0,
                "Right": 0.0,
                "Bottom": 0.0,
            },
            "Alignment": {"X": 0.0, "Y": 0.0},
        }
    material = result.get("Material")
    if (
        isinstance(material, Mapping)
        and str(material.get("Kind") or "") == "RoundedCard"
    ):
        result["Material"] = {
            **copy.deepcopy(dict(material)),
            "SizeBinding": "WidgetGeometry",
        }
    return result


def _apply_schema18_layer_defaults(layer: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(layer)
    result.setdefault("Visibility", "Visible")
    result.setdefault("SpacingStrategy", "Padding")
    result.setdefault("SpacerSizeRule", "Auto")
    result.setdefault("SpacerFillCoefficient", 1.0)
    return result


def _apply_material_size_binding_schema_contract(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    """Keep old strict plugins clean while making schema 19 explicit."""
    result = copy.deepcopy(dict(document))
    synthetic_overlay_root_ids: set[str] = set()
    for instance in result.get("ComponentInstances", []):
        if not isinstance(instance, Mapping):
            continue
        for slot in instance.get("SlotContents", []):
            if not isinstance(slot, Mapping):
                continue
            synthetic_overlay_root_ids.update(
                str(root_id)
                for root_id in slot.get("RootLayerIds", [])
                if str(root_id or "")
            )
    for component in result.get("Components", []):
        if not isinstance(component, Mapping):
            continue
        for layer in component.get("Layers", []):
            if not isinstance(layer, Mapping):
                continue
            try:
                marker = json.loads(str(layer.get("PayloadJson") or "{}"))
            except (TypeError, ValueError, json.JSONDecodeError):
                marker = {}
            marker = (
                marker.get("component_instance", {})
                if isinstance(marker, Mapping)
                else {}
            )
            if not isinstance(marker, Mapping):
                continue
            for slot in marker.get("slot_contents", []):
                if not isinstance(slot, Mapping):
                    continue
                roots = slot.get("root_layer_ids", slot.get("RootLayerIds", []))
                synthetic_overlay_root_ids.update(
                    str(root_id)
                    for root_id in roots
                    if str(root_id or "")
                )

    layer_groups: list[list[dict[str, Any]]] = [
        [row for row in result.get("Layers", []) if isinstance(row, dict)]
    ]
    layer_groups.extend(
        [row for row in component.get("Layers", []) if isinstance(row, dict)]
        for component in result.get("Components", [])
        if isinstance(component, dict)
    )
    slot_material_promoted = False
    for layers in layer_groups:
        for layer in layers:
            material = layer.get("Material")
            if (
                isinstance(material, dict)
                and str(material.get("Kind") or "") == "RoundedCard"
                and _umg_layer_requires_runtime_size(
                    layer,
                    {},
                    synthetic_overlay_root_ids=synthetic_overlay_root_ids,
                )
            ):
                material["SizeBinding"] = "WidgetGeometry"
                slot_material_promoted = True
            image_fill = layer.get("ImageFill")
            if (
                isinstance(image_fill, Mapping)
                and str(image_fill.get("Mode") or "") == "Fill"
                and _umg_layer_requires_runtime_size(
                    layer,
                    {},
                    synthetic_overlay_root_ids=synthetic_overlay_root_ids,
                )
            ):
                blocked = _add_layer_block_reasons(
                    layer,
                    ["image_fill_runtime_resize_requires_dynamic_uv_binding"],
                )
                layer.clear()
                layer.update(blocked)
    if slot_material_promoted:
        result["SchemaVersion"] = max(
            int(result.get("SchemaVersion") or 0),
            TIGER_UMG_ROUNDED_CARD_DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION,
        )
    schema_version = int(result.get("SchemaVersion") or 0)
    for layers in layer_groups:
        for layer in layers:
            material = layer.get("Material")
            if (
                not isinstance(material, dict)
                or str(material.get("Kind") or "") != "RoundedCard"
            ):
                continue
            if schema_version >= (
                TIGER_UMG_ROUNDED_CARD_DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION
            ):
                material.setdefault("SizeBinding", "FixedSize")
            else:
                material.pop("SizeBinding", None)
    return result


def _apply_painter_component_contract(
    flat_document: Mapping[str, Any],
    context: Mapping[str, Any],
    *,
    selected_artboard_id: str,
) -> dict[str, Any]:
    """Split reusable definitions and concrete instances for schema 18."""

    document = context["document"]
    components = [
        row
        for row in document.get("components", [])
        if isinstance(row, Mapping) and str(row.get("id") or "")
    ]
    if not components:
        result = copy.deepcopy(dict(flat_document))
        if int(result.get("SchemaVersion") or 0) >= (
            TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION
        ):
            result.setdefault("Components", [])
            result.setdefault("ComponentInstances", [])
        return result

    component_by_id = {
        str(row.get("id") or ""): row for row in components
    }
    object_by_id = {
        str(row.get("id") or ""): row
        for row in document.get("objects", [])
        if isinstance(row, Mapping) and str(row.get("id") or "")
    }
    children = _component_object_children(document)
    flat_by_artboard: dict[str, dict[str, Any]] = {
        selected_artboard_id: copy.deepcopy(dict(flat_document))
    }

    def flat_for_artboard(artboard_id: str) -> dict[str, Any]:
        if artboard_id not in flat_by_artboard:
            flat_by_artboard[artboard_id] = (
                _painter_ui_to_umg_document_from_context(
                    context,
                    artboard_id=artboard_id,
                    include_component_contract=False,
                )
            )
        return flat_by_artboard[artboard_id]

    definition_subtrees: dict[str, list[str]] = {}
    component_records: list[dict[str, Any]] = []
    for component in components:
        component_id = str(component.get("id") or "")
        root_id = str(component.get("root_object_id") or "")
        root = object_by_id.get(root_id)
        if root is None:
            # The provider-neutral validator will report the missing root
            # through the empty component layer list.
            definition_subtrees[component_id] = []
            component_records.append(
                {
                    "Id": component_id,
                    "Name": str(component.get("name") or component_id),
                    "RootLayerId": root_id,
                    "BaseComponentId": str(
                        component.get("base_component_id") or ""
                    ),
                    "VariantValuesJson": json.dumps(
                        component_variant_properties(component),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                    "DependencyComponentIds": [],
                    "Layers": [],
                    "Properties": [],
                    "Slots": [],
                }
            )
            continue
        subtree = _component_subtree_ids(root_id, children)
        definition_subtrees[component_id] = subtree
        subtree_set = set(subtree)
        artboard_id = str(root.get("artboard_id") or selected_artboard_id)
        source_document = flat_for_artboard(artboard_id)
        source_layers = {
            str(layer.get("Id") or ""): copy.deepcopy(dict(layer))
            for layer in source_document.get("Layers", [])
            if isinstance(layer, Mapping) and str(layer.get("Id") or "")
        }
        nested_roots = [
            object_by_id[object_id]
            for object_id in subtree
            if object_id != root_id
            and object_id in object_by_id
            and _is_component_instance_root(
                object_by_id[object_id], component_by_id
            )
            and str(
                object_by_id[object_id].get("component_scope_id") or ""
            )
            == component_id
        ]
        excluded_ids: set[str] = set()
        nested_markers: dict[str, dict[str, Any]] = {}
        nested_slot_root_owner: dict[str, str] = {}
        dependencies: set[str] = set()
        for nested_root in nested_roots:
            nested_component_id = str(nested_root.get("component_id") or "")
            nested_component = component_by_id.get(nested_component_id)
            if nested_component is None:
                continue
            dependencies.add(nested_component_id)
            slot_contents = _instance_slot_content_roots(
                document,
                nested_root,
                nested_component,
                children=children,
                object_by_id=object_by_id,
            )
            preserved_slot_ids = {
                object_id
                for slot in slot_contents
                for root_layer_id in slot["RootLayerIds"]
                for object_id in _component_subtree_ids(
                    root_layer_id, children
                )
            }
            for slot in slot_contents:
                for root_layer_id in slot["RootLayerIds"]:
                    nested_slot_root_owner[root_layer_id] = str(
                        nested_root.get("id") or ""
                    )
            excluded_ids.update(
                set(
                    _component_subtree_ids(
                        str(nested_root.get("id") or ""), children
                    )[1:]
                )
                - preserved_slot_ids
            )
            resolved_overrides, override_blockers = (
                _instance_resolved_overrides(
                    document,
                    nested_root,
                    nested_component,
                    children=children,
                    object_by_id=object_by_id,
                )
            )
            nested_markers[str(nested_root.get("id") or "")] = {
                "component_id": nested_component_id,
                "property_values": _component_property_values(
                    nested_root, nested_component
                ),
                "resolved_overrides": resolved_overrides,
                "slot_contents": slot_contents,
                "blockers": override_blockers,
            }
        definitions = normalize_ui_component_property_definitions(
            component.get("property_definitions")
        )
        for definition in definitions.values():
            if str(definition.get("type") or "") == "instance_swap":
                for dependency in [
                    definition.get("default"),
                    *definition.get("preferred_values", []),
                ]:
                    dependency_id = str(dependency or "")
                    if dependency_id in component_by_id:
                        dependencies.add(dependency_id)
        local_layers: list[dict[str, Any]] = []
        for object_id in subtree:
            if object_id in excluded_ids or object_id not in source_layers:
                continue
            layer = source_layers[object_id]
            if object_id in nested_slot_root_owner:
                layer["ParentId"] = nested_slot_root_owner[object_id]
            marker = nested_markers.get(object_id)
            if marker is not None:
                layer = _attach_component_instance_payload(
                    layer,
                    instance_id=object_id,
                    component_id=marker["component_id"],
                    property_values=marker["property_values"],
                    resolved_overrides=marker["resolved_overrides"],
                    slot_contents=marker["slot_contents"],
                )
                layer = _add_layer_block_reasons(
                    layer, marker["blockers"]
                )
            if object_id == root_id:
                layer = _localize_component_root_layer(
                    layer,
                    context["geometry"].get(root_id, root),
                )
            local_layers.append(_apply_schema18_layer_defaults(layer))
        slots = [
            {
                "Name": str(name),
                "LayerId": str(definition.get("default") or ""),
                "ExposeOnInstanceOnly": True,
            }
            for name, definition in definitions.items()
            if str(definition.get("type") or "") == "slot"
        ]
        component_records.append(
            {
                "Id": component_id,
                "Name": str(component.get("name") or component_id),
                "RootLayerId": root_id,
                "BaseComponentId": str(
                    component.get("base_component_id") or ""
                ),
                "VariantValuesJson": json.dumps(
                    component_variant_properties(component),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "DependencyComponentIds": sorted(
                    dependency for dependency in dependencies
                    if dependency != component_id
                ),
                "Layers": local_layers,
                "Properties": _component_property_records(
                    document,
                    component,
                    subtree_ids=subtree_set,
                ),
                "Slots": slots,
            }
        )

    selected_rows = list(
        context["objects_by_artboard"].get(selected_artboard_id, [])
    )
    selected_ids = {
        str(row.get("id") or "") for row in selected_rows
    }
    definition_screen_ids = {
        object_id
        for component_id, subtree in definition_subtrees.items()
        for object_id in subtree
        if object_id in selected_ids
        and str(
            object_by_id.get(object_id, {}).get("component_role") or ""
        )
        == "definition"
        and str(
            object_by_id.get(object_id, {}).get("component_id") or ""
        )
        == component_id
    }
    # Removing only definition-role rows is insufficient when a reusable
    # definition owns a nested component instance.  The complete definition
    # subtree belongs exclusively to Components[].Layers.
    definition_screen_ids.update(
        object_id
        for component_id, subtree in definition_subtrees.items()
        if (
            (root := object_by_id.get(
                str(component_by_id[component_id].get("root_object_id") or "")
            ))
            is not None
            and str(root.get("artboard_id") or "") == selected_artboard_id
        )
        for object_id in subtree
    )
    explicit_screen_instance_roots = [
        row
        for row in selected_rows
        if str(row.get("id") or "") not in definition_screen_ids
        and _is_component_instance_root(row, component_by_id)
        and not str(row.get("component_scope_id") or "")
    ]
    def nested_under_another_definition(row: Mapping[str, Any]) -> bool:
        parent = object_by_id.get(str(row.get("parent_id") or ""))
        while parent is not None:
            if str(parent.get("component_role") or "") == "definition":
                return True
            parent = object_by_id.get(str(parent.get("parent_id") or ""))
        return False

    selected_artboard = context["artboards_by_id"][selected_artboard_id]

    def intersects_selected_artboard(row: Mapping[str, Any]) -> bool:
        rect = context["geometry"].get(str(row.get("id") or ""), row)
        x = float(rect.get("x") or 0.0)
        y = float(rect.get("y") or 0.0)
        width = max(0.0, float(rect.get("width") or 0.0))
        height = max(0.0, float(rect.get("height") or 0.0))
        return bool(
            x + width > 0.0
            and y + height > 0.0
            and x < float(selected_artboard.get("width") or 0.0)
            and y < float(selected_artboard.get("height") or 0.0)
        )

    # Painter templates may intentionally turn the actual on-screen control
    # into the component definition instead of placing a second instance.
    # Every top-level definition intersecting this artboard is also an
    # authored placement; explicit sibling instances do not make it disappear.
    # Off-canvas definitions and separate library artboards remain authoring-only.
    implicit_definition_roots = [
        root
        for component_id, component in component_by_id.items()
        if (
            root := object_by_id.get(
                str(component.get("root_object_id") or "")
            )
        )
        is not None
        and str(root.get("artboard_id") or "") == selected_artboard_id
        and str(root.get("component_role") or "") == "definition"
        and not nested_under_another_definition(root)
        and intersects_selected_artboard(root)
    ]
    implicit_definition_root_ids = {
        str(row.get("id") or "") for row in implicit_definition_roots
    }
    screen_instance_roots = [
        *explicit_screen_instance_roots,
        *implicit_definition_roots,
    ]
    excluded_screen_ids: set[str] = set(definition_screen_ids)
    excluded_screen_ids.difference_update(implicit_definition_root_ids)
    slot_root_owner: dict[str, str] = {}
    instance_records: list[dict[str, Any]] = []
    marker_by_layer_id: dict[str, dict[str, Any]] = {}
    for instance_root in screen_instance_roots:
        instance_id = str(instance_root.get("id") or "")
        component_id = str(instance_root.get("component_id") or "")
        component = component_by_id[component_id]
        slot_contents = _instance_slot_content_roots(
            document,
            instance_root,
            component,
            children=children,
            object_by_id=object_by_id,
        )
        preserved_slot_ids: set[str] = set()
        for slot in slot_contents:
            for root_layer_id in slot["RootLayerIds"]:
                slot_root_owner[root_layer_id] = instance_id
                preserved_slot_ids.update(
                    _component_subtree_ids(root_layer_id, children)
                )
        excluded_screen_ids.update(
            set(_component_subtree_ids(instance_id, children)[1:])
            - preserved_slot_ids
        )
        resolved_overrides, override_blockers = _instance_resolved_overrides(
            document,
            instance_root,
            component,
            children=children,
            object_by_id=object_by_id,
        )
        property_values = _component_property_values(
            instance_root, component
        )
        marker_by_layer_id[instance_id] = {
            "component_id": component_id,
            "property_values": property_values,
            "resolved_overrides": resolved_overrides,
            "slot_contents": slot_contents,
            "blockers": override_blockers,
        }
        instance_records.append(
            {
                "Id": instance_id,
                "ComponentId": component_id,
                "LayerId": instance_id,
                "ParentId": str(instance_root.get("parent_id") or ""),
                "PropertyValuesJson": json.dumps(
                    property_values,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "ResolvedOverridesJson": json.dumps(
                    resolved_overrides,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                "SlotContents": slot_contents,
            }
        )

    for instance_record in instance_records:
        instance_id = str(instance_record.get("Id") or "")
        if instance_id in slot_root_owner:
            instance_record["ParentId"] = slot_root_owner[instance_id]

    screen_layers: list[dict[str, Any]] = []
    for raw_layer in flat_document.get("Layers", []):
        if not isinstance(raw_layer, Mapping):
            continue
        layer_id = str(raw_layer.get("Id") or "")
        if layer_id in excluded_screen_ids:
            continue
        layer = copy.deepcopy(dict(raw_layer))
        if layer_id in slot_root_owner:
            layer["ParentId"] = slot_root_owner[layer_id]
        marker = marker_by_layer_id.get(layer_id)
        if marker is not None:
            layer = _attach_component_instance_payload(
                layer,
                instance_id=layer_id,
                component_id=marker["component_id"],
                property_values=marker["property_values"],
                resolved_overrides=marker["resolved_overrides"],
                slot_contents=marker["slot_contents"],
            )
            layer = _add_layer_block_reasons(layer, marker["blockers"])
        screen_layers.append(_apply_schema18_layer_defaults(layer))

    resource_by_id: dict[str, dict[str, Any]] = {}
    for flat in flat_by_artboard.values():
        for resource in flat.get("Resources", []):
            if isinstance(resource, Mapping) and str(resource.get("Id") or ""):
                resource_by_id[str(resource.get("Id") or "")] = copy.deepcopy(
                    dict(resource)
                )
    definition_layer_ids = {
        str(layer.get("Id") or "")
        for component in component_records
        for layer in component.get("Layers", [])
        if isinstance(layer, Mapping) and str(layer.get("Id") or "")
    }
    interactions: list[dict[str, Any]] = []
    interaction_keys: set[str] = set()
    for flat in flat_by_artboard.values():
        for interaction in flat.get("Interactions", []):
            if not isinstance(interaction, Mapping):
                continue
            component_id = str(interaction.get("ComponentId") or "")
            if (
                flat is not flat_by_artboard[selected_artboard_id]
                and component_id not in definition_layer_ids
            ):
                continue
            item = copy.deepcopy(dict(interaction))
            key = json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if key in interaction_keys:
                continue
            interaction_keys.add(key)
            interactions.append(item)
    result = copy.deepcopy(dict(flat_document))
    component_has_dynamic_rounded_card = any(
        str((layer.get("Material") or {}).get("SizeBinding") or "")
        == "WidgetGeometry"
        for component in component_records
        for layer in component.get("Layers", [])
        if isinstance(layer, Mapping)
        and isinstance(layer.get("Material"), Mapping)
    )
    result["SchemaVersion"] = max(
        TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION,
        *(
            int(flat.get("SchemaVersion") or 0)
            for flat in flat_by_artboard.values()
        ),
        (
            TIGER_UMG_ROUNDED_CARD_DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION
            if component_has_dynamic_rounded_card
            else TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION
        ),
    )
    result["Resources"] = list(resource_by_id.values())
    result["Layers"] = screen_layers
    result["Interactions"] = interactions
    result["Components"] = component_records
    result["ComponentInstances"] = instance_records
    return result


def _painter_ui_to_umg_document_from_context(
    context: Mapping[str, Any],
    *,
    artboard_id: str,
    include_component_contract: bool = True,
) -> dict[str, Any]:
    document = context["document"]
    selected_artboard_id = str(artboard_id or document["active_artboard_id"])
    artboard = context["artboards_by_id"].get(selected_artboard_id)
    if artboard is None:
        raise ValueError(f"Painter UI artboard not found: {selected_artboard_id}")
    export_rows = list(
        context["objects_by_artboard"].get(selected_artboard_id, [])
    )
    included_ids = {row["id"] for row in export_rows}
    parent_ids_with_children = {
        str(row.get("parent_id") or "")
        for row in export_rows
        if str(row.get("parent_id") or "")
    }
    auto_layout_contract = context["auto_layout_contract"]
    panel_kind_by_id = dict(auto_layout_contract["panel_kind_by_id"])
    panel_classification_by_id = dict(
        auto_layout_contract.get("classification_by_id") or {}
    )
    flow_slot_by_id = dict(auto_layout_contract["flow_slot_by_id"])
    spacing_strategy_by_id = dict(
        auto_layout_contract["spacing_strategy_by_id"]
    )
    spacer_size_rule_by_id = dict(
        auto_layout_contract["spacer_size_rule_by_id"]
    )
    spacer_fill_coefficient_by_id = dict(
        auto_layout_contract["spacer_fill_coefficient_by_id"]
    )
    layout_blockers_by_id = dict(auto_layout_contract["blockers_by_id"])
    component_by_id = context["component_by_id"]
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
    geometry = context["geometry"]
    root_geometry = {
        "x": 0.0,
        "y": 0.0,
        "width": float(artboard["width"]),
        "height": float(artboard["height"]),
    }
    resources: dict[str, dict[str, Any]] = {}
    layers: list[dict[str, Any]] = []
    artboard_background_layer, artboard_background = (
        _artboard_background_contract(artboard)
    )
    requires_artboard_background_schema = artboard_background_layer is not None
    if artboard_background_layer is not None:
        layers.append(artboard_background_layer)
    requires_static_appearance_schema = False
    requires_static_texture_schema = False
    requires_button_style_schema = False
    requires_dynamic_rounded_card_schema = False
    requires_widget_visibility_schema = False
    for row in export_rows:
        if not bool(row.get("visible", True)):
            requires_widget_visibility_schema = True
        style = dict(row.get("style") or {})
        content = dict(row.get("content") or {})
        painted_leaf_container = _is_painted_leaf_container(
            row,
            parent_ids_with_children,
        )
        conversion_row = _leaf_rectangle_conversion_row(
            row,
            painted_leaf_container=painted_leaf_container,
        )
        authored_panel_kind = panel_kind_by_id.get(str(row["id"]), "None")
        authored_spacing_strategy = spacing_strategy_by_id.get(
            str(row["id"]), "Padding"
        )
        authored_spacer_size_rule = spacer_size_rule_by_id.get(
            str(row["id"]), "Auto"
        )
        authored_spacer_fill_coefficient = (
            spacer_fill_coefficient_by_id.get(str(row["id"]), 1.0)
        )
        effective_panel_kind = (
            "None" if painted_leaf_container else authored_panel_kind
        )
        effective_spacing_strategy = (
            "Padding"
            if painted_leaf_container
            else authored_spacing_strategy
        )
        effective_spacer_size_rule = (
            "Auto" if painted_leaf_container else authored_spacer_size_rule
        )
        effective_spacer_fill_coefficient = (
            1.0
            if painted_leaf_container
            else authored_spacer_fill_coefficient
        )
        button_style_conversion = painter_button_style_conversion(
            conversion_row,
            style,
            content,
        )
        button_style_record = (
            copy.deepcopy(button_style_conversion.record)
            if button_style_conversion is not None
            and not button_style_conversion.block_reasons
            else {}
        )
        if button_style_record:
            requires_button_style_schema = True
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
        kind = _umg_kind(str(conversion_row["kind"]))
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
        flow_slot = flow_slot_by_id.get(str(row["id"]), {})
        runtime_size_dynamic = (
            _constraints_require_runtime_size(authored_constraints)
            or _flow_slot_requires_runtime_size(
                parent_panel_kind,
                flow_slot,
            )
        )
        disposition, block_reasons = _umg_disposition(
            conversion_row,
            style,
            content,
            kind,
            resolved_size=resolved_rect,
            runtime_size_dynamic=runtime_size_dynamic,
        )
        static_vector_bake = plan_static_vector_bake(
            conversion_row,
            resolved_size=resolved_rect,
            has_children=str(row["id"]) in parent_ids_with_children,
            runtime_size_dynamic=runtime_size_dynamic,
        )
        static_appearance_bake = plan_static_appearance_bake(
            conversion_row,
            resolved_size=resolved_rect,
            has_children=str(row["id"]) in parent_ids_with_children,
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
        block_reasons, static_vector_transition = (
            _apply_static_vector_gate_transition(
                block_reasons,
                static_vector_bake,
            )
        )
        static_vector_bake = {
            **static_vector_bake,
            "gate_transition": static_vector_transition,
        }
        block_reasons, static_appearance_transition = (
            _apply_static_appearance_gate_transition(
                block_reasons,
                static_appearance_bake,
            )
        )
        static_appearance_bake = {
            **static_appearance_bake,
            "gate_transition": static_appearance_transition,
        }
        available_bakes = sum(
            plan.get("available") is True
            for plan in (static_vector_bake, static_appearance_bake)
        )
        if available_bakes > 1:
            block_reasons = sorted(
                set(
                    [
                        *block_reasons,
                        "multiple_static_bake_plans_conflict",
                    ]
                )
            )
        if block_reasons:
            disposition = "Blocked"
        elif available_bakes == 1:
            disposition = "Baked"
        if (
            disposition == "Baked"
            and static_appearance_bake.get("available") is True
        ):
            if (
                static_appearance_bake.get("kind")
                == STATIC_TEXTURE_BAKE_KIND
            ):
                requires_static_texture_schema = True
            else:
                requires_static_appearance_schema = True
        flipbook_conversion = painter_flipbook_conversion(
            conversion_row,
            style,
            content,
        )
        image_fill_conversion = (
            None
            if flipbook_conversion is not None
            else painter_image_fill_conversion(
                conversion_row,
                style,
                content,
                size=resolved_rect,
            )
        )
        material_record = (
            None
            if image_fill_conversion is not None
            or flipbook_conversion is not None
            else painter_style_umg_material(
                style,
                source_kind=str(conversion_row.get("kind") or ""),
                size=_row_size(row, resolved_rect),
            )
        )
        if (
            material_record is not None
            and str(material_record.get("Kind") or "") == "RoundedCard"
        ):
            material_record["SizeBinding"] = (
                "WidgetGeometry" if runtime_size_dynamic else "FixedSize"
            )
            if runtime_size_dynamic and disposition == "Material":
                requires_dynamic_rounded_card_schema = True
        asset_id = ""
        image_fill_record: dict[str, Any] = {}
        flipbook_record: dict[str, Any] = {}
        source_path = (
            flipbook_conversion.source_path
            if flipbook_conversion is not None
            else image_fill_conversion.source_path
            if image_fill_conversion is not None
            else ""
        )
        if flipbook_conversion is not None and source_path:
            path = Path(source_path).expanduser()
            flipbook_asset_id = _resource_id(path, "flipbook")
            resources[flipbook_asset_id] = {
                "Id": flipbook_asset_id,
                "Kind": "texture",
                "SourcePath": str(path),
                "DestinationName": f"TS_{flipbook_asset_id}",
                "ContentHash": _hash_file(path) if path.is_file() else "",
                "SettingsJson": json.dumps(
                    {
                        "Usage": "FlipbookAtlas",
                        "SRGB": True,
                        "AddressX": "Clamp",
                        "AddressY": "Clamp",
                    },
                    separators=(",", ":"),
                ),
            }
            flipbook_record = flipbook_conversion.bind_asset(
                flipbook_asset_id
            )
        elif image_fill_conversion is not None and source_path:
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
        elif flipbook_conversion is not None and not flipbook_record:
            flipbook_record = flipbook_conversion.bind_asset("")
        payload = {
            "source_kind": row["kind"],
            "umg_leaf_rectangle_classification": (
                {
                    "classification": "painted_leaf_container",
                    "original_source_kind": str(row["kind"]),
                    "effective_source_kind": "rectangle",
                    "effective_widget_kind": "Image",
                    "preserves_container_semantics": False,
                    "authored_panel_kind": authored_panel_kind,
                    "authored_spacing_strategy": authored_spacing_strategy,
                    "authored_spacer_size_rule": authored_spacer_size_rule,
                    "authored_spacer_fill_coefficient": (
                        authored_spacer_fill_coefficient
                    ),
                }
                if painted_leaf_container
                else {}
            ),
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
            # Painter and Figma persist typography in CSS-style pixels.  UE's
            # FSlateFontInfo::Size is measured in points and is converted to
            # Slate units at 96 DPI, so the editor backend must not interpret
            # this number as a native Slate point size.
            "font_size_unit": PAINTER_UMG_FONT_SIZE_UNIT,
            "font_weight": int(style.get("font_weight", 400) or 400),
            "font_family": str(style.get("font_family") or "Inter"),
            # Painter/Figma text is laid out inside its authored rectangle
            # unless the explicit auto-width mode asks the text box to grow.
            # Preserve that distinction for UTextBlock instead of relying on
            # Unreal's no-wrap default.
            "auto_wrap": str(
                content.get("text_resize") or ""
            ).strip().casefold().replace("-", "_") != "auto_width",
            "font_axes": dict(style.get("font_axes") or {}),
            "source_visible": bool(row.get("visible", True)),
            "painter_conversion": (
                "flipbook_ui_material"
                if flipbook_conversion is not None
                and disposition == "Material"
                else "ui_material_custom_hlsl"
                if disposition == "Material"
                else "static_appearance_png_bake"
                if disposition == "Baked"
                and static_appearance_bake.get("available") is True
                and static_appearance_bake.get("kind")
                == STATIC_APPEARANCE_BAKE_KIND
                else "static_texture_png_bake"
                if disposition == "Baked"
                and static_appearance_bake.get("available") is True
                and static_appearance_bake.get("kind")
                == STATIC_TEXTURE_BAKE_KIND
                else "static_vector_png_bake"
                if disposition == "Baked"
                else "painted_leaf_container_to_slate_image"
                if painted_leaf_container and disposition == "Native"
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
            "figma_variable_bindings": list(
                content.get("figma_variable_bindings") or []
            ),
            "component_property_bindings": dict(
                row.get("component_property_bindings") or {}
            ),
            "figma_component_property_bindings": dict(
                content.get("figma_component_property_bindings") or {}
            ),
            "figma_component_property_references": copy.deepcopy(
                dict(
                    content.get("figma_component_property_references") or {}
                )
            ),
            "remote_component": dict(
                content.get("remote_component") or {}
            ),
            "image_fill": dict(image_fill_record),
            "flipbook": dict(flipbook_record),
            "umg_button_style": copy.deepcopy(button_style_record),
            "flipbook_bake": copy.deepcopy(
                dict(content.get("flipbook_bake") or {})
            ),
            "static_vector_bake": copy.deepcopy(static_vector_bake),
            "static_appearance_bake": copy.deepcopy(
                static_appearance_bake
            ),
            "umg_mapping": (
                "flipbook_ui_material"
                if flipbook_conversion is not None
                and disposition == "Material"
                else "ui_material_custom_hlsl"
                if disposition == "Material"
                else "package_time_texture2d_image_fill"
                if disposition == "Baked"
                else "native_or_converted" if disposition == "Native"
                else "blocked_preflight"
            ),
            "umg_block_reasons": (
                block_reasons
            ),
            "auto_layout": {
                "panel_kind": effective_panel_kind,
                "panel_classification": copy.deepcopy(
                    panel_classification_by_id.get(str(row["id"]), {})
                ),
                "flow_slot": flow_slot_by_id.get(str(row["id"]), {}),
                "spacing_strategy": effective_spacing_strategy,
                "spacer_size_rule": effective_spacer_size_rule,
                "spacer_fill_coefficient": effective_spacer_fill_coefficient,
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
                "PanelKind": effective_panel_kind,
                "FlowSlot": flow_slot_by_id.get(str(row["id"]), {}),
                "SpacingStrategy": effective_spacing_strategy,
                "SpacerSizeRule": effective_spacer_size_rule,
                "SpacerFillCoefficient": effective_spacer_fill_coefficient,
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
                "Opacity": (
                    float(row["opacity"])
                    if bool(row.get("visible", True))
                    else 0.0
                ),
                # A hidden Painter layer already exports at zero opacity, which
                # makes it invisible but leaves it hit-testable: Slate tests
                # against visibility, not opacity, so the widget still eats
                # clicks meant for whatever sits behind it. Visible layers stay
                # silent here and keep taking the schema-16 default, so a
                # document that hides nothing gains no field it did not have.
                **(
                    {}
                    if bool(row.get("visible", True))
                    else {"Visibility": "HitTestInvisible"}
                ),
                "AssetId": asset_id,
                "ImageFill": image_fill_record,
                "Flipbook": flipbook_record,
                "ButtonStyle": button_style_record,
                "Material": (
                    material_record
                    if disposition == "Material"
                    and material_record is not None
                    else {}
                ),
                "PayloadJson": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )
    interactions = []
    umg_trigger_map = {
        "click": "clicked",
        "hover": "hovered",
        "mouse_enter": "hovered",
        "mouse_leave": "unhovered",
        "press": "pressed",
    }
    for row in context["interactions_by_artboard"].get(
        selected_artboard_id,
        [],
    ):
        parameters = dict(row.get("parameters") or {})
        parameters["painter_trigger"] = str(row.get("trigger") or "")
        interactions.append(
            {
                "ComponentId": row["source_object_id"],
                "Trigger": umg_trigger_map.get(
                    str(row.get("trigger") or ""),
                    str(row.get("trigger") or ""),
                ),
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
    figma_link = document.get("linked_targets", {}).get("figma", {})
    figma_link = figma_link if isinstance(figma_link, Mapping) else {}
    artboard_variable_bindings = [
        dict(binding)
        for binding in figma_link.get("artboard_variable_bindings", [])
        if isinstance(binding, Mapping)
        and str(binding.get("artboard_id") or "") == selected_artboard_id
    ]
    figma_reaction_recovery = [
        copy.deepcopy(dict(recovery))
        for recovery in figma_link.get("reaction_recovery", [])
        if isinstance(recovery, Mapping)
        and str(recovery.get("artboard_id") or "") == selected_artboard_id
    ]
    schema_version = max(
        TIGER_UMG_SCHEMA_VERSION,
        (
            TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION
            if any(
                str(layer.get("PanelKind") or "None") == "Overlay"
                or str(layer.get("SpacingStrategy") or "Padding")
                == "Spacer"
                for layer in layers
            )
            else TIGER_UMG_SCHEMA_VERSION
        ),
        (
            STATIC_TEXTURE_BAKE_SCHEMA_VERSION
            if requires_static_texture_schema
            else STATIC_APPEARANCE_BAKE_SCHEMA_VERSION
            if requires_static_appearance_schema
            else TIGER_UMG_SCHEMA_VERSION
        ),
        (
            TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION
            if requires_button_style_schema
            or requires_artboard_background_schema
            else TIGER_UMG_SCHEMA_VERSION
        ),
        (
            TIGER_UMG_ROUNDED_CARD_DYNAMIC_SIZE_DOCUMENT_SCHEMA_VERSION
            if requires_dynamic_rounded_card_schema
            else TIGER_UMG_SCHEMA_VERSION
        ),
        (
            TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION
            if requires_widget_visibility_schema
            else TIGER_UMG_SCHEMA_VERSION
        ),
    )
    if schema_version >= TIGER_UMG_WIDGET_VISIBILITY_DOCUMENT_SCHEMA_VERSION:
        for layer in layers:
            layer.setdefault("Visibility", "Visible")
    if schema_version >= TIGER_UMG_OVERLAY_DOCUMENT_SCHEMA_VERSION:
        # Schema 17 made these outer USTRUCT fields mandatory on every layer,
        # including provider-generated records such as the artboard background
        # and any future synthetic layers that bypass the normal row serializer.
        for layer in layers:
            layer.setdefault("SpacingStrategy", "Padding")
            layer.setdefault("SpacerSizeRule", "Auto")
            layer.setdefault("SpacerFillCoefficient", 1.0)
    else:
        for layer in layers:
            layer.pop("SpacingStrategy", None)
            layer.pop("SpacerSizeRule", None)
            layer.pop("SpacerFillCoefficient", None)
    converted = {
        "SchemaVersion": schema_version,
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
            "FigmaVariableBindings": artboard_variable_bindings,
            "FigmaReactionRecovery": figma_reaction_recovery,
            "Sections": list(
                context["sections_by_artboard"].get(
                    selected_artboard_id,
                    [],
                )
            ),
            "Review": dict(
                document.get("linked_targets", {}).get("review", {})
            ),
            "ArtboardBackground": artboard_background,
        },
    }
    if include_component_contract:
        converted = _apply_painter_component_contract(
            converted,
            context,
            selected_artboard_id=selected_artboard_id,
        )
    return _apply_material_size_binding_schema_contract(converted)


def painter_ui_to_umg_document(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    """Convert one Painter UI artboard to the shared Tiger UMG document."""
    context = _prepare_painter_umg_conversion(value)
    return _painter_ui_to_umg_document_from_context(
        context,
        artboard_id=artboard_id,
    )


def _static_bake_plan_from_layer(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(str(row.get("PayloadJson") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    plan = payload.get("static_vector_bake")
    return dict(plan) if isinstance(plan, Mapping) else {}


def _static_appearance_bake_plan_from_layer(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        payload = json.loads(str(row.get("PayloadJson") or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    plan = payload.get("static_appearance_bake")
    return dict(plan) if isinstance(plan, Mapping) else {}


def _bake_plan_from_layer(
    row: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    appearance = _static_appearance_bake_plan_from_layer(row)
    vector = _static_bake_plan_from_layer(row)
    appearance_active = str(appearance.get("status") or "") in {
        "available",
        "materialized",
    }
    vector_active = str(vector.get("status") or "") in {
        "available",
        "materialized",
    }
    if appearance_active and not vector_active:
        kind = str(appearance.get("kind") or "")
        if kind in {
            STATIC_APPEARANCE_BAKE_KIND,
            STATIC_TEXTURE_BAKE_KIND,
        }:
            return kind, appearance
        return "", {}
    if vector_active and not appearance_active:
        return "static_vector_png", vector
    return "", {}


def _preflight_painter_umg_document(
    document: Mapping[str, Any],
) -> dict[str, Any]:
    source_document = document if isinstance(document, Mapping) else {}
    counts = {"Native": 0, "Material": 0, "Baked": 0, "Blocked": 0}
    blockers: list[dict[str, Any]] = []
    record_contract = inspect_umg_document_records(
        document,
        resources_required=True,
    )
    layers = [
        *record_contract["layers"],
        *record_contract["component_layers"],
    ]
    parent_panel_kinds = {
        str(layer.get("Id") or ""): str(layer.get("PanelKind") or "None")
        for layer in layers
        if str(layer.get("Id") or "")
    }
    resources = record_contract["resources"]
    document_reasons = [
        *record_contract["reasons"],
        *validate_umg_component_contract(document),
        *validate_umg_resource_identity_contract(resources),
    ]
    raw_schema_version = source_document.get("SchemaVersion")
    schema_version = (
        raw_schema_version
        if isinstance(raw_schema_version, int)
        and not isinstance(raw_schema_version, bool)
        else 0
    )
    if not 4 <= schema_version <= SUPPORTED_TIGER_UMG_SCHEMA_VERSION:
        document_reasons.append("umg_schema_version_unsupported")
    if document_reasons:
        blockers.append(
            {
                "object_id": "",
                "name": "Tiger UMG document",
                "reasons": sorted(set(document_reasons)),
            }
        )
    resource_by_id = {
        str(resource.get("Id") or ""): resource
        for resource in resources
        if str(resource.get("Id") or "")
    }
    resource_ids = set(resource_by_id)
    synthetic_overlay_root_ids: set[str] = set()
    component_instance_layer_ids: set[str] = set()
    for instance in document.get("ComponentInstances", []):
        if not isinstance(instance, Mapping):
            continue
        layer_id = str(instance.get("LayerId") or "")
        if layer_id:
            component_instance_layer_ids.add(layer_id)
        for slot in instance.get("SlotContents", []):
            if isinstance(slot, Mapping):
                synthetic_overlay_root_ids.update(
                    str(root_id)
                    for root_id in slot.get("RootLayerIds", [])
                    if str(root_id or "")
                )
    for component in document.get("Components", []):
        if not isinstance(component, Mapping):
            continue
        for component_layer in component.get("Layers", []):
            if not isinstance(component_layer, Mapping):
                continue
            try:
                payload = json.loads(
                    str(component_layer.get("PayloadJson") or "{}")
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
            marker = (
                payload.get("component_instance", {})
                if isinstance(payload, Mapping)
                else {}
            )
            if not isinstance(marker, Mapping):
                continue
            component_layer_id = str(component_layer.get("Id") or "")
            if component_layer_id:
                component_instance_layer_ids.add(component_layer_id)
            for slot in marker.get("slot_contents", []):
                if not isinstance(slot, Mapping):
                    continue
                roots = slot.get("root_layer_ids", slot.get("RootLayerIds", []))
                synthetic_overlay_root_ids.update(
                    str(root_id)
                    for root_id in roots
                    if str(root_id or "")
                )
    for row in layers:
        disposition = validated_umg_disposition(row)
        if disposition is None:
            blockers.append(
                {
                    "object_id": str(row.get("Id") or ""),
                    "name": str(row.get("Name") or ""),
                    "reasons": ["umg_layer_disposition_invalid"],
                }
            )
            continue
        counts[disposition] += 1
        panel_reasons = validate_umg_panel_record(
            row,
            document_schema_version=schema_version,
        )
        image_reasons = validate_umg_image_fill_record(
            row.get("ImageFill"),
            layer_asset_id=str(row.get("AssetId") or ""),
        )
        image_fill = row.get("ImageFill")
        if (
            isinstance(image_fill, Mapping)
            and str(image_fill.get("Mode") or "") == "Fill"
            and _umg_layer_requires_runtime_size(
                row,
                parent_panel_kinds,
                synthetic_overlay_root_ids=synthetic_overlay_root_ids,
            )
        ):
            image_reasons.append(
                "image_fill_runtime_resize_requires_dynamic_uv_binding"
            )
        image_reasons = sorted(set(image_reasons))
        visibility_reasons = validate_umg_widget_visibility(
            row.get("Visibility"),
            document_schema_version=schema_version,
        )
        button_style = row.get("ButtonStyle")
        has_button_style = isinstance(button_style, Mapping) and bool(
            button_style
        )
        button_style_reasons = validate_umg_button_style_record(
            button_style,
            layer_kind=str(row.get("Kind") or "") if has_button_style else "",
            document_schema_version=schema_version,
            required=(
                schema_version
                >= TIGER_UMG_BUTTON_STYLE_DOCUMENT_SCHEMA_VERSION
                and disposition == "Native"
                and str(row.get("Kind") or "") == "Button"
                and str(row.get("Id") or "")
                not in component_instance_layer_ids
            ),
        )
        if has_button_style and disposition != "Native":
            button_style_reasons.append(
                "button_style_requires_native_disposition"
            )
        button_style_reasons = sorted(set(button_style_reasons))
        flipbook = row.get("Flipbook")
        has_flipbook = isinstance(flipbook, Mapping) and bool(flipbook)
        flipbook_reasons = validate_umg_flipbook_record(
            flipbook,
            layer_kind=str(row.get("Kind") or ""),
            document_schema_version=schema_version,
            resource_ids=resource_ids,
        )
        if has_flipbook and disposition != "Material":
            flipbook_reasons.append(
                "flipbook_requires_material_disposition"
            )
        if has_flipbook and (
            bool(row.get("ImageFill")) or bool(row.get("Material"))
        ):
            flipbook_reasons.append("flipbook_conflicting_visual_record")
        flipbook_reasons = sorted(set(flipbook_reasons))
        if disposition == "Material":
            material = row.get("Material")
            material = material if isinstance(material, Mapping) else {}
            dynamic_rounded_card_reasons = []
            if (
                str(material.get("Kind") or "") == "RoundedCard"
                and _umg_layer_requires_runtime_size(
                    row,
                    parent_panel_kinds,
                    synthetic_overlay_root_ids=synthetic_overlay_root_ids,
                )
                and str(material.get("SizeBinding") or "FixedSize")
                != "WidgetGeometry"
            ):
                dynamic_rounded_card_reasons.append(
                    "rounded_card_runtime_resize_requires_dynamic_size_binding"
                )
            reasons = [
                *panel_reasons,
                *image_reasons,
                *button_style_reasons,
                *visibility_reasons,
                *flipbook_reasons,
                *dynamic_rounded_card_reasons,
                *(
                    []
                    if has_flipbook
                    else validate_umg_material_record(
                        row.get("Material"),
                        layer_kind=str(row.get("Kind") or ""),
                        document_schema_version=schema_version,
                    )
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
            bake_kind, bake_plan = _bake_plan_from_layer(row)
            bake_status = str(bake_plan.get("status") or "")
            reasons = (
                validate_umg_materialized_baked_layer(
                    row,
                    document_schema_version=schema_version,
                    resources=resource_by_id,
                )
                if bake_status == "materialized"
                else validate_umg_static_appearance_source_plan(
                    row,
                    document_schema_version=schema_version,
                )
                if bake_kind
                in {
                    STATIC_APPEARANCE_BAKE_KIND,
                    STATIC_TEXTURE_BAKE_KIND,
                }
                else validate_umg_static_vector_source_plan(row)
                if bake_kind == "static_vector_png"
                else ["baked_source_plan_kind_invalid"]
            )
            reasons = sorted(
                set(
                    [
                        *panel_reasons,
                        *reasons,
                        *button_style_reasons,
                        *visibility_reasons,
                    ]
                )
            )
            if reasons:
                blockers.append(
                    {
                        "object_id": row["Id"],
                        "name": row["Name"],
                        "reasons": reasons,
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
        elif (
            panel_reasons
            or image_reasons
            or button_style_reasons
            or visibility_reasons
            or flipbook_reasons
        ):
            blockers.append(
                {
                    "object_id": row["Id"],
                    "name": row["Name"],
                    "reasons": sorted(
                        set(
                            [
                                *panel_reasons,
                                *image_reasons,
                                *button_style_reasons,
                                *visibility_reasons,
                                *flipbook_reasons,
                            ]
                        )
                    ),
                }
            )
    painter_source = source_document.get("PainterSource")
    painter_source = painter_source if isinstance(painter_source, Mapping) else {}
    artboard_variable_bindings = painter_source.get(
        "FigmaVariableBindings",
        [],
    )
    if isinstance(artboard_variable_bindings, list) and any(
        isinstance(binding, Mapping)
        and str(binding.get("status") or "") != "native"
        for binding in artboard_variable_bindings
    ):
        blockers.append(
            {
                "object_id": str(
                    painter_source.get("ArtboardId") or ""
                ),
                "name": "Figma artboard variable bindings",
                "reasons": ["figma_variable_binding_requires_token_relink"],
            }
        )
    figma_reaction_recovery = painter_source.get(
        "FigmaReactionRecovery",
        [],
    )
    if isinstance(figma_reaction_recovery, list):
        for recovery_index, recovery in enumerate(figma_reaction_recovery):
            if not isinstance(recovery, Mapping):
                continue
            recovery_reasons = [
                str(reason)
                for reason in recovery.get("reasons", [])
                if str(reason or "")
            ]
            blockers.append(
                {
                    "object_id": str(
                        recovery.get("source_object_id")
                        or recovery.get("source_artboard_id")
                        or recovery.get("id")
                        or f"figma-reaction-recovery-{recovery_index}"
                    ),
                    "name": "Figma reaction recovery",
                    "reasons": recovery_reasons
                    or [
                        "figma_reaction_recovery_requires_manual_resolution"
                    ],
                }
            )
    missing_resources = [
        str(row.get("SourcePath") or "")
        for row in resources
        if not Path(str(row.get("SourcePath") or "")).expanduser().is_file()
    ]
    layer_kind_by_id = {
        str(row.get("Id") or ""): str(row.get("Kind") or "")
        for row in layers
    }
    supported_runtime_triggers = {
        "clicked",
        "hovered",
        "unhovered",
        "pressed",
        "released",
    }
    supported_runtime_actions = {
        "emit_event",
        "play_animation",
        "play_sound",
        "set_opacity",
        "set_visibility",
        "set_material_scalar",
    }
    runtime_action_block_reasons = {
        "navigate": "figma_navigation_requires_umg_screen_router",
        "back": "figma_back_requires_umg_screen_router",
        "open_overlay": "figma_overlay_navigation_requires_umg_runtime",
        "close_overlay": "figma_overlay_navigation_requires_umg_runtime",
        "swap_overlay": "figma_overlay_navigation_requires_umg_runtime",
        "scroll_to": "figma_scroll_to_requires_umg_scrollbox_binding",
        "change_variant": (
            "interactive_component_change_to_runtime_unsupported"
        ),
    }
    raw_interactions = source_document.get("Interactions", [])
    interactions = raw_interactions if isinstance(raw_interactions, list) else []
    for interaction in interactions:
        if not isinstance(interaction, Mapping):
            continue
        component_id = str(interaction.get("ComponentId") or "")
        trigger = str(interaction.get("Trigger") or "").strip().casefold()
        if trigger not in supported_runtime_triggers:
            blockers.append(
                {
                    "object_id": component_id,
                    "name": "Unsupported interaction trigger",
                    "reasons": [
                        "umg_interaction_trigger_runtime_unsupported:"
                        f"{trigger or 'missing'}"
                    ],
                }
            )
        elif layer_kind_by_id.get(component_id) != "Button":
            blockers.append(
                {
                    "object_id": component_id,
                    "name": "Figma interaction source",
                    "reasons": [
                        "figma_interaction_source_requires_umg_button_widget"
                    ],
                }
            )
        for action in interaction.get("Actions", []):
            action_type = str(
                action.get("Type") or ""
            ).strip().casefold()
            if action_type not in supported_runtime_actions:
                blockers.append(
                    {
                        "object_id": component_id,
                        "name": str(
                            action.get("Name")
                            or action_type
                            or "Unsupported interaction action"
                        ),
                        "reasons": [
                            runtime_action_block_reasons.get(
                                action_type,
                                "umg_interaction_action_runtime_unsupported:"
                                f"{action_type or 'missing'}",
                            )
                        ],
                    }
                )
    return {
        "schema": PAINTER_UMG_ADAPTER_SCHEMA,
        "ok": not blockers and not missing_resources,
        "document_id": str(source_document.get("DocumentId") or ""),
        "artboard_id": str(painter_source.get("ArtboardId") or ""),
        "counts": counts,
        "blockers": blockers,
        "missing_resources": missing_resources,
        "interaction_count": len(interactions),
        "resource_count": len(resources),
        "bake_plans": [
            {
                "object_id": row["Id"],
                "name": row["Name"],
                "status": str(_bake_plan_from_layer(row)[1].get("status")),
                "kind": _bake_plan_from_layer(row)[0],
            }
            for row in layers
            if validated_umg_disposition(row) == "Baked"
            and bool(_bake_plan_from_layer(row)[1].get("available"))
        ],
    }


class PainterUMGConversionSession:
    """Reusable, call-scoped conversion state for multi-artboard documents.

    The session owns no global cache, so edits cannot accidentally reuse stale
    geometry.  Corpus and batch callers can preflight many artboards while the
    normalized document, Auto Layout contract, and resolved geometry are each
    computed only once.
    """

    def __init__(self, value: Mapping[str, Any]) -> None:
        self._context = _prepare_painter_umg_conversion(value)

    @property
    def artboard_ids(self) -> tuple[str, ...]:
        return tuple(self._context["artboards_by_id"])

    def to_umg_document(self, *, artboard_id: str = "") -> dict[str, Any]:
        return _painter_ui_to_umg_document_from_context(
            self._context,
            artboard_id=artboard_id,
        )

    def preflight(self, *, artboard_id: str = "") -> dict[str, Any]:
        return _preflight_painter_umg_document(
            self.to_umg_document(artboard_id=artboard_id)
        )


def preflight_painter_umg(
    value: Mapping[str, Any],
    *,
    artboard_id: str = "",
) -> dict[str, Any]:
    document = painter_ui_to_umg_document(value, artboard_id=artboard_id)
    return _preflight_painter_umg_document(document)


def _static_appearance_layout_preservation(
    layer: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "policy": "preserve_exact_layer_layout",
        "Size": copy.deepcopy(layer.get("Size")),
        "Anchor": copy.deepcopy(layer.get("Anchor")),
        "RenderTransformPivot": copy.deepcopy(
            layer.get("RenderTransformPivot")
        ),
        "Position": copy.deepcopy(layer.get("Position")),
        "RotationDegrees": copy.deepcopy(layer.get("RotationDegrees")),
        "CanvasSlot": copy.deepcopy(layer.get("CanvasSlot")),
    }


def _materialize_static_bakes(
    document: dict[str, Any],
    root: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    resources = {
        str(row.get("Id") or ""): row for row in document["Resources"]
    }
    # Component definition layers are Baked exactly like screen layers, and a
    # Figma document that keeps its art inside components has all of them
    # there. Skipping them left the layer claiming an available bake with no
    # asset, no ImageFill, and a status still reading "available", which the
    # plugin rejects as an invalid Baked record and which blocks the whole
    # document rather than just that layer.
    bakeable_layers = [
        *document["Layers"],
        *(
            component_layer
            for component in document.get("Components", [])
            if isinstance(component, Mapping)
            for component_layer in component.get("Layers", [])
            if isinstance(component_layer, dict)
        ),
    ]
    for layer in bakeable_layers:
        if str(layer.get("Disposition") or "") != "Baked":
            continue
        bake_kind, plan = _bake_plan_from_layer(layer)
        if not bool(plan.get("available")):
            continue
        if bake_kind in {
            STATIC_APPEARANCE_BAKE_KIND,
            STATIC_TEXTURE_BAKE_KIND,
        }:
            layout_preservation = _static_appearance_layout_preservation(
                layer
            )
            artifact = write_static_appearance_bake(plan, root / "bakes")
            layout_adjustment: dict[str, Any] = {}
        elif bake_kind == "static_vector_png":
            layout_preservation = {}
            artifact = write_static_vector_bake(plan, root / "bakes")
            layout_adjustment = expand_umg_layer_for_static_bake(layer, plan)
        else:
            raise ValueError("Baked layer has no unique static bake plan")
        source_path = Path(artifact["png_path"])
        asset_id = f"texture_{str(artifact['content_hash'])}"
        conversion = painter_image_fill_conversion(
            {"kind": "image"},
            {},
            {
                "source_path": str(source_path),
                "image_fit": "stretch",
                "original_width": float(layer["Size"]["X"]),
                "original_height": float(layer["Size"]["Y"]),
            },
            size={
                "width": float(layer["Size"]["X"]),
                "height": float(layer["Size"]["Y"]),
            },
        )
        if conversion is None or conversion.block_reasons:
            raise ValueError(
                "Static bake did not convert to a clean ImageFill: "
                + ",".join(
                    conversion.block_reasons
                    if conversion is not None
                    else ["conversion_missing"]
                )
            )
        image_fill_record = conversion.bind_asset(asset_id)
        resource_record = {
            "Id": asset_id,
            "Kind": "texture",
            "SourcePath": str(source_path),
            "DestinationName": f"TS_{asset_id}",
            "ContentHash": str(artifact["content_hash"]),
            "SettingsJson": json.dumps(
                {"Usage": "ImageFill", "SRGB": True},
                separators=(",", ":"),
            ),
        }
        existing_resource = resources.get(asset_id)
        if existing_resource is not None and (
            str(existing_resource.get("ContentHash") or "")
            != str(artifact["content_hash"])
            or str(existing_resource.get("Kind") or "") != "texture"
        ):
            raise ValueError(
                "Static bake resource identity collision: " + asset_id
            )
        resources[asset_id] = resource_record
        payload = json.loads(str(layer.get("PayloadJson") or "{}"))
        payload["image_fill"] = dict(image_fill_record)
        if bake_kind in {
            STATIC_APPEARANCE_BAKE_KIND,
            STATIC_TEXTURE_BAKE_KIND,
        }:
            is_texture_bake = bake_kind == STATIC_TEXTURE_BAKE_KIND
            payload["painter_conversion"] = (
                "static_texture_png_bake"
                if is_texture_bake
                else "static_appearance_png_bake"
            )
            payload["umg_mapping"] = (
                "texture2d_image_fill_from_static_texture_bake"
                if is_texture_bake
                else "texture2d_image_fill_from_static_appearance_bake"
            )
            payload["static_appearance_bake"] = {
                "kind": bake_kind,
                "status": "materialized",
                "available": True,
                "reasons": [],
                "source_hash": artifact["source_hash"],
                "effect_hash": artifact["effect_hash"],
                "source_canonical_json": artifact[
                    "source_canonical_json"
                ],
                "effect_canonical_json": artifact[
                    "effect_canonical_json"
                ],
                "content_hash": artifact["content_hash"],
                "pixel_rgba_sha256": artifact["pixel_rgba_sha256"],
                "origin_disposition": "Baked",
                "satisfied_gate": artifact["intended_gate"],
                "gate_transition": copy.deepcopy(
                    plan.get("gate_transition", {})
                ),
                "source": copy.deepcopy(artifact["source"]),
                "provenance": copy.deepcopy(artifact["provenance"]),
                "manifest_path": Path(artifact["manifest_path"])
                .relative_to(root)
                .as_posix(),
                "manifest_sha256": _hash_file(
                    Path(artifact["manifest_path"])
                ),
                "png_path": source_path.relative_to(root).as_posix(),
                "layout_preservation": layout_preservation,
                **(
                    {"intended_gate": artifact["intended_gate"]}
                    if is_texture_bake
                    else {}
                ),
                "integration_status": (
                    "tigerstudio_umg_schema15_materialized"
                    if is_texture_bake
                    else "tigerstudio_umg_schema14_materialized"
                ),
                "umg_support_claimed": True,
            }
        else:
            payload["painter_conversion"] = "static_vector_png_bake"
            payload["umg_mapping"] = (
                "texture2d_image_fill_from_static_vector_bake"
            )
            payload["static_vector_bake"] = {
                "status": "materialized",
                "available": True,
                "reasons": [],
                "source_hash": artifact["source_hash"],
                "content_hash": artifact["content_hash"],
                "pixel_rgba_sha256": artifact["pixel_rgba_sha256"],
                "origin_disposition": "Baked",
                "satisfied_gate": artifact["satisfied_gate"],
                "gate_transition": copy.deepcopy(
                    plan.get("gate_transition", {})
                ),
                "source": copy.deepcopy(artifact["source"]),
                "manifest_path": Path(artifact["manifest_path"])
                .relative_to(root)
                .as_posix(),
                "png_path": source_path.relative_to(root).as_posix(),
                "layout_adjustment": layout_adjustment,
            }
        # Baked remains durable provenance. Unreal consumes this narrowly
        # validated typed ImageFill; it does not run a bake itself.
        layer["Disposition"] = "Baked"
        layer["BlockReasons"] = []
        layer["AssetId"] = asset_id
        layer["ImageFill"] = image_fill_record
        layer["PayloadJson"] = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        results.append(
            {
                "object_id": layer["Id"],
                "kind": bake_kind,
                **artifact,
                "asset_id": asset_id,
                **(
                    {"layout_preservation": layout_preservation}
                    if bake_kind
                    in {
                        STATIC_APPEARANCE_BAKE_KIND,
                        STATIC_TEXTURE_BAKE_KIND,
                    }
                    else {"layout_adjustment": layout_adjustment}
                ),
            }
        )
    document["Resources"] = sorted(resources.values(), key=lambda row: row["Id"])
    return results


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
    source_preflight = _preflight_painter_umg_document(document)
    static_bakes = _materialize_static_bakes(packaged, root)
    packaged_preflight = _preflight_painter_umg_document(packaged)
    missing: list[str] = []
    copied: list[str] = []
    reused: list[str] = []
    collisions: list[str] = []
    for row in packaged["Resources"]:
        source = Path(str(row["SourcePath"])).expanduser()
        if not source.is_file():
            missing.append(str(source))
            continue
        destination = assets / f"{row['Id']}{source.suffix.lower()}"
        if destination.is_file():
            if _hash_file(destination) != _hash_file(source):
                collisions.append(str(destination))
                continue
            reused.append(str(destination))
        else:
            shutil.copy2(source, destination)
            copied.append(str(destination))
        row["SourcePath"] = destination.relative_to(root).as_posix()
        row["ContentHash"] = _hash_file(destination)
    document_path = root / "tiger_umg_document.json"
    document_path.write_text(
        json.dumps(packaged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": (
            source_preflight["ok"]
            and packaged_preflight["ok"]
            and not missing
            and not collisions
        ),
        "document_path": str(document_path),
        "asset_count": len(packaged["Resources"]),
        "copied": copied,
        "reused": reused,
        "missing": missing,
        "collisions": collisions,
        "static_bakes": static_bakes,
        "document": packaged,
        "preflight": source_preflight,
        "packaged_preflight": packaged_preflight,
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
    "PAINTER_UMG_FONT_SIZE_UNIT",
    "PainterUMGConversionSession",
    "TIGER_UMG_SCHEMA_VERSION",
    "generate_painter_umg",
    "package_painter_umg",
    "painter_ui_to_umg_document",
    "preflight_painter_umg",
]
