"""Shared Painter UI appearance mutations for Inspector and automation."""
from __future__ import annotations

import copy
import math
from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


UI_GRADIENT_TYPES = {"linear", "radial"}
UI_EFFECT_TYPES = {
    "drop_shadow",
    "inner_shadow",
    "layer_blur",
    "background_blur",
}
UI_EFFECT_BLEND_MODES = {
    "normal",
    "darken",
    "multiply",
    "color_burn",
    "lighten",
    "screen",
    "color_dodge",
    "overlay",
    "soft_light",
    "hard_light",
    "difference",
    "exclusion",
    "hue",
    "saturation",
    "color",
    "luminosity",
}


def _number(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = float(default)
    return result if math.isfinite(result) else float(default)


def _point(value: object, fallback: tuple[float, float]) -> dict[str, float]:
    value = value if isinstance(value, Mapping) else {}
    return {
        "x": _number(value.get("x"), fallback[0]),
        "y": _number(value.get("y"), fallback[1]),
    }


def normalize_ui_gradient(value: object) -> dict[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    gradient_type = str(value.get("type") or "linear").strip().casefold()
    if gradient_type not in UI_GRADIENT_TYPES:
        gradient_type = "linear"
    raw_stops = value.get("stops")
    raw_stops = raw_stops if isinstance(raw_stops, list) else []
    stops = [
        {
            "position": max(
                0.0,
                min(1.0, _number(row.get("position"))),
            ),
            "color": str(row.get("color") or "#000000FF"),
        }
        for row in raw_stops
        if isinstance(row, Mapping)
    ]
    stops.sort(key=lambda row: row["position"])
    if len(stops) < 2:
        stops = [
            {"position": 0.0, "color": "#FFFFFFFF"},
            {"position": 1.0, "color": "#000000FF"},
        ]
    return {
        "type": gradient_type,
        "start": _point(value.get("start"), (0.0, 0.5)),
        "end": _point(value.get("end"), (1.0, 0.5)),
        "width": _point(value.get("width"), (0.0, 1.0)),
        "stops": stops,
    }


def normalize_ui_effect(value: object) -> dict[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    effect_type = str(value.get("type") or "drop_shadow").strip().casefold()
    if effect_type not in UI_EFFECT_TYPES:
        effect_type = "drop_shadow"
    if effect_type in {"layer_blur", "background_blur"}:
        return {
            "type": effect_type,
            "radius": max(
                0.0,
                min(256.0, _number(value.get("radius"), 8.0)),
            ),
        }
    blend_mode = str(value.get("blend_mode") or "normal").strip().casefold()
    if blend_mode not in UI_EFFECT_BLEND_MODES:
        blend_mode = "normal"
    return {
        "type": effect_type,
        "color": str(value.get("color") or "#00000066"),
        "x": _number(value.get("x")),
        "y": _number(value.get("y"), 4.0),
        "blur": max(0.0, _number(value.get("blur"), 8.0)),
        "spread": _number(value.get("spread")),
        "blend_mode": blend_mode,
    }


def normalize_ui_effects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [
        normalize_ui_effect(row)
        for row in value
        if isinstance(row, Mapping)
    ]


def _object_style(
    document: Mapping[str, Any] | None,
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized = normalize_ui_document(document)
    row = next(
        (
            item
            for item in normalized["objects"]
            if item["id"] == str(object_id)
        ),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    return normalized, copy.deepcopy(dict(row.get("style") or {}))


def _sync_legacy_shadow(style: dict[str, Any]) -> None:
    first = next(
        (
            row
            for row in normalize_ui_effects(style.get("effects"))
            if row["type"] == "drop_shadow"
        ),
        None,
    )
    if first is None:
        style.pop("shadow", None)
        return
    style["shadow"] = {
        key: copy.deepcopy(value)
        for key, value in first.items()
        if key not in {"type", "blend_mode"}
    }


def inspect_ui_appearance(
    document: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    normalized, style = _object_style(document, object_id)
    gradient = style.get("fill_gradient")
    effects = normalize_ui_effects(style.get("effects"))
    if not effects and isinstance(style.get("shadow"), Mapping):
        effects = [
            normalize_ui_effect(
                {"type": "drop_shadow", **dict(style["shadow"])}
            )
        ]
    return {
        "object_id": str(object_id),
        "revision": normalized["revision"],
        "fill": str(style.get("fill") or ""),
        "gradient": (
            normalize_ui_gradient(gradient)
            if isinstance(gradient, Mapping)
            else None
        ),
        "effects": effects,
    }


def merge_ui_appearance_style(
    style: Mapping[str, Any] | None,
    *,
    gradient: Mapping[str, Any] | None,
    effects: list[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    result = copy.deepcopy(dict(style or {}))
    if gradient is None:
        result.pop("fill_gradient", None)
    else:
        result["fill_gradient"] = normalize_ui_gradient(gradient)
    normalized_effects = normalize_ui_effects(effects)
    if normalized_effects:
        result["effects"] = normalized_effects
    else:
        result.pop("effects", None)
    _sync_legacy_shadow(result)
    return result


def set_ui_fill_gradient(
    document: Mapping[str, Any] | None,
    object_id: str,
    gradient: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized, style = _object_style(document, object_id)
    style["fill_gradient"] = normalize_ui_gradient(gradient)
    return update_ui_object(normalized, str(object_id), {"style": style})


def remove_ui_fill_gradient(
    document: Mapping[str, Any] | None,
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized, style = _object_style(document, object_id)
    style.pop("fill_gradient", None)
    return update_ui_object(normalized, str(object_id), {"style": style})


def add_ui_effect(
    document: Mapping[str, Any] | None,
    object_id: str,
    effect: Mapping[str, Any],
    *,
    index: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized, style = _object_style(document, object_id)
    effects = normalize_ui_effects(style.get("effects"))
    row = normalize_ui_effect(effect)
    insert_at = (
        len(effects)
        if index is None
        else max(0, min(len(effects), int(index)))
    )
    effects.insert(insert_at, row)
    style["effects"] = effects
    _sync_legacy_shadow(style)
    document_out, _object = update_ui_object(
        normalized,
        str(object_id),
        {"style": style},
    )
    return document_out, copy.deepcopy(effects[insert_at])


def update_ui_effect(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized, style = _object_style(document, object_id)
    effects = normalize_ui_effects(style.get("effects"))
    if index < 0 or index >= len(effects):
        raise PainterUIDocumentError(f"UI effect index out of range: {index}")
    effects[index] = normalize_ui_effect({**effects[index], **dict(changes)})
    style["effects"] = effects
    _sync_legacy_shadow(style)
    document_out, _object = update_ui_object(
        normalized,
        str(object_id),
        {"style": style},
    )
    return document_out, copy.deepcopy(effects[index])


def remove_ui_effect(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized, style = _object_style(document, object_id)
    effects = normalize_ui_effects(style.get("effects"))
    if index < 0 or index >= len(effects):
        raise PainterUIDocumentError(f"UI effect index out of range: {index}")
    removed = effects.pop(index)
    if effects:
        style["effects"] = effects
    else:
        style.pop("effects", None)
    _sync_legacy_shadow(style)
    document_out, _object = update_ui_object(
        normalized,
        str(object_id),
        {"style": style},
    )
    return document_out, removed


def reorder_ui_effect(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
    target_index: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized, style = _object_style(document, object_id)
    effects = normalize_ui_effects(style.get("effects"))
    if index < 0 or index >= len(effects):
        raise PainterUIDocumentError(f"UI effect index out of range: {index}")
    target = max(0, min(len(effects) - 1, int(target_index)))
    row = effects.pop(index)
    effects.insert(target, row)
    style["effects"] = effects
    _sync_legacy_shadow(style)
    document_out, _object = update_ui_object(
        normalized,
        str(object_id),
        {"style": style},
    )
    return document_out, copy.deepcopy(effects)


def _require_blur_effect(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
) -> dict[str, Any]:
    appearance = inspect_ui_appearance(document, object_id)
    effects = appearance["effects"]
    if index < 0 or index >= len(effects):
        raise PainterUIDocumentError(f"UI effect index out of range: {index}")
    row = effects[index]
    if row["type"] not in {"layer_blur", "background_blur"}:
        raise PainterUIDocumentError(
            f"UI effect at index {index} is not a blur"
        )
    return row


def add_ui_blur(
    document: Mapping[str, Any] | None,
    object_id: str,
    blur_type: str,
    radius: float,
    *,
    index: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_type = str(blur_type).strip().casefold()
    if normalized_type not in {"layer_blur", "background_blur"}:
        raise PainterUIDocumentError(
            "blur_type must be layer_blur or background_blur"
        )
    return add_ui_effect(
        document,
        object_id,
        {"type": normalized_type, "radius": radius},
        index=index,
    )


def update_ui_blur(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
    radius: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_blur_effect(document, object_id, index)
    return update_ui_effect(
        document,
        object_id,
        index,
        {"radius": radius},
    )


def remove_ui_blur(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _require_blur_effect(document, object_id, index)
    return remove_ui_effect(document, object_id, index)


def reorder_ui_blur(
    document: Mapping[str, Any] | None,
    object_id: str,
    index: int,
    target_index: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    _require_blur_effect(document, object_id, index)
    return reorder_ui_effect(document, object_id, index, target_index)


__all__ = [
    "UI_EFFECT_BLEND_MODES",
    "UI_EFFECT_TYPES",
    "UI_GRADIENT_TYPES",
    "add_ui_effect",
    "add_ui_blur",
    "inspect_ui_appearance",
    "merge_ui_appearance_style",
    "normalize_ui_effect",
    "normalize_ui_effects",
    "normalize_ui_gradient",
    "remove_ui_effect",
    "remove_ui_blur",
    "remove_ui_fill_gradient",
    "reorder_ui_effect",
    "reorder_ui_blur",
    "set_ui_fill_gradient",
    "update_ui_effect",
    "update_ui_blur",
]
