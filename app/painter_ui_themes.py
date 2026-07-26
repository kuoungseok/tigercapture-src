"""Theme and design-token resolution for Painter UI preview documents."""
from __future__ import annotations

import copy
import re
from typing import Any, Mapping


UI_THEME_MODES = ("light", "dark", "high_contrast")
_THEME_ALIASES = {
    "high-contrast": "high_contrast",
    "high contrast": "high_contrast",
    "contrast": "high_contrast",
    "hc": "high_contrast",
}
_BINDING_ROOTS = {"style", "content", "layout", "constraints", "accessibility"}
_BINDING_SCALARS = {"opacity", "visible"}


def normalize_ui_theme(value: object, default: str = "light") -> str:
    text = str(value or "").strip().casefold()
    text = _THEME_ALIASES.get(text, text)
    text = re.sub(r"[^a-z0-9_]+", "_", text).strip("_")
    return text or default


def normalize_ui_theme_values(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        normalize_ui_theme(theme): copy.deepcopy(theme_value)
        for theme, theme_value in value.items()
        if str(theme or "").strip()
    }


def ui_theme_for_artboard(artboard: Mapping[str, Any] | None) -> str:
    return normalize_ui_theme((artboard or {}).get("theme"), "light")


def _token_value(
    token_id: str,
    *,
    theme: str,
    tokens: Mapping[str, Mapping[str, Any]],
    stack: tuple[str, ...] = (),
) -> tuple[Any, list[str]]:
    token = tokens.get(str(token_id))
    if token is None or token_id in stack:
        return None, list(stack)
    chain = [*stack, token_id]
    theme_values = normalize_ui_theme_values(token.get("theme_values"))
    if theme in theme_values:
        return copy.deepcopy(theme_values[theme]), chain
    alias_id = str(token.get("alias_token_id") or "")
    value = token.get("value")
    if value is not None:
        return copy.deepcopy(value), chain
    if alias_id:
        return _token_value(
            alias_id,
            theme=theme,
            tokens=tokens,
            stack=tuple(chain),
        )
    return None, chain


def _set_binding_path(row: dict[str, Any], path: str, value: Any) -> bool:
    parts = [part for part in str(path or "").split(".") if part]
    if not parts:
        return False
    if len(parts) == 1:
        if parts[0] not in _BINDING_SCALARS:
            return False
        row[parts[0]] = copy.deepcopy(value)
        return True
    if parts[0] not in _BINDING_ROOTS:
        return False
    target: dict[str, Any] = row
    for part in parts[:-1]:
        current = target.get(part)
        if not isinstance(current, Mapping):
            current = {}
            target[part] = current
        elif not isinstance(current, dict):
            current = dict(current)
            target[part] = current
        target = current
    target[parts[-1]] = copy.deepcopy(value)
    return True


def resolve_ui_theme_object(
    row: Mapping[str, Any],
    *,
    theme: str,
    tokens: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    resolved = copy.deepcopy(dict(row))
    applied: dict[str, dict[str, Any]] = {}
    normalized_theme = normalize_ui_theme(theme)
    bindings = row.get("token_bindings")
    bindings = bindings if isinstance(bindings, Mapping) else {}
    for path, token_id_value in sorted(bindings.items(), key=lambda item: str(item[0])):
        token_id = str(token_id_value or "")
        value, chain = _token_value(
            token_id,
            theme=normalized_theme,
            tokens=tokens,
        )
        if value is None or not _set_binding_path(resolved, str(path), value):
            continue
        applied[str(path)] = {
            "token_id": token_id,
            "alias_chain": chain,
            "value": copy.deepcopy(value),
        }
    resolved["resolved_theme"] = normalized_theme
    resolved["resolved_tokens"] = applied
    return resolved


def resolve_ui_theme_document(value: Mapping[str, Any]) -> dict[str, Any]:
    from app.painter_ui_components import resolve_ui_component_document
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_responsive import resolve_ui_responsive_document

    document = resolve_ui_component_document(normalize_ui_document(value))
    document = resolve_ui_responsive_document(document)
    tokens = {row["id"]: row for row in document["tokens"]}
    artboard_themes = {
        row["id"]: ui_theme_for_artboard(row)
        for row in document["artboards"]
    }
    document["objects"] = [
        resolve_ui_theme_object(
            row,
            theme=artboard_themes.get(row["artboard_id"], "light"),
            tokens=tokens,
        )
        for row in document["objects"]
    ]
    document["resolved_themes"] = artboard_themes
    return document


def inspect_ui_theme(value: Mapping[str, Any], *, artboard_id: str = "") -> dict[str, Any]:
    document = resolve_ui_theme_document(value)
    selected_artboard_id = str(
        artboard_id or document["active_artboard_id"]
    )
    artboard = next(
        row for row in document["artboards"] if row["id"] == selected_artboard_id
    )
    objects = [
        row for row in document["objects"] if row["artboard_id"] == selected_artboard_id
    ]
    return {
        "schema": "tigerstudio.painter.ui.theme.inspect.v1",
        "artboard_id": selected_artboard_id,
        "theme": ui_theme_for_artboard(artboard),
        "token_count": len(document["tokens"]),
        "bound_object_count": sum(bool(row["resolved_tokens"]) for row in objects),
        "resolved_binding_count": sum(len(row["resolved_tokens"]) for row in objects),
        "objects": [
            {
                "object_id": row["id"],
                "resolved_tokens": copy.deepcopy(row["resolved_tokens"]),
            }
            for row in objects
            if row["resolved_tokens"]
        ],
    }


def set_ui_token_theme_value(
    token: Mapping[str, Any],
    *,
    theme: str,
    value: Any,
) -> dict[str, Any]:
    themes = normalize_ui_theme_values(token.get("theme_values"))
    themes[normalize_ui_theme(theme)] = copy.deepcopy(value)
    return themes


def remove_ui_token_theme_value(
    token: Mapping[str, Any],
    *,
    theme: str,
) -> dict[str, Any]:
    themes = normalize_ui_theme_values(token.get("theme_values"))
    themes.pop(normalize_ui_theme(theme), None)
    return themes


__all__ = [
    "UI_THEME_MODES",
    "inspect_ui_theme",
    "normalize_ui_theme",
    "normalize_ui_theme_values",
    "remove_ui_token_theme_value",
    "resolve_ui_theme_document",
    "resolve_ui_theme_object",
    "set_ui_token_theme_value",
    "ui_theme_for_artboard",
]
