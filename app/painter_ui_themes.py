"""Theme and design-token resolution for Painter UI preview documents."""
from __future__ import annotations

import copy
import math
import re
from typing import Any, Mapping

from app.painter_ui_json_copy import json_deepcopy


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
    variable_modes: Mapping[str, str] | None,
    tokens: Mapping[str, Mapping[str, Any]],
    stack: tuple[str, ...] = (),
) -> tuple[Any, list[str]]:
    token = tokens.get(str(token_id))
    if token is None or token_id in stack:
        return None, list(stack)
    chain = [*stack, token_id]
    collection_id = str(token.get("collection_id") or "")
    theme_values = normalize_ui_theme_values(token.get("theme_values"))
    if (
        collection_id == "ui-variable-collection-theme"
        and theme in theme_values
    ):
        return copy.deepcopy(theme_values[theme]), chain
    active_modes = variable_modes or {}
    mode_id = str(active_modes.get(collection_id) or "")
    mode_values = token.get("mode_values")
    mode_values = mode_values if isinstance(mode_values, Mapping) else {}
    if mode_id and mode_id in mode_values:
        return copy.deepcopy(mode_values[mode_id]), chain
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
            variable_modes=active_modes,
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
        row[parts[0]] = json_deepcopy(value)
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
    target[parts[-1]] = json_deepcopy(value)
    return True


def _synchronize_canonical_style_binding(
    row: dict[str, Any],
    path: str,
    value: Any,
) -> None:
    """Keep legacy token paths aligned with the canonical paint stacks.

    ``style.fill``, ``style.stroke`` and ``style.stroke_width`` predate the
    Figma-style ``fills``/``strokes`` records.  Normalization retains both
    representations for compatibility, while render/export code consumes the
    canonical records.  Applying a token only to the legacy shortcut would
    therefore leave a stale paint color or width in preview and UMG output.

    A binding addresses the first paint, matching the Figma exchange path.  We
    never replace an authored gradient/image/shader paint with a solid color.
    """

    normalized_path = str(path or "")
    if normalized_path not in {
        "style.fill",
        "style.stroke",
        "style.stroke_width",
    }:
        return
    style_value = row.get("style")
    if not isinstance(style_value, Mapping):
        return
    if not isinstance(style_value, dict):
        style_value = dict(style_value)
        row["style"] = style_value
    style = style_value

    if normalized_path in {"style.fill", "style.stroke"}:
        if not isinstance(value, str) or not value.strip():
            return
        paint_key = "fills" if normalized_path == "style.fill" else "strokes"
        paints_value = style.get(paint_key)
        paints = list(paints_value) if isinstance(paints_value, list) else []
        if not paints:
            # A resolved legacy solid still needs a canonical record.  This is
            # normally relevant only to old documents because current
            # normalization already materializes legacy paints.
            from app.painter_ui_advanced_appearance import normalize_ui_paint

            paint_source: dict[str, Any] = {"color": value}
            if paint_key == "strokes":
                paint_source.update(
                    {
                        "width": style.get("stroke_width", 1.0),
                        "align": style.get("stroke_align", "center"),
                    }
                )
            style[paint_key] = [
                normalize_ui_paint(
                    paint_source,
                    stroke=paint_key == "strokes",
                )
            ]
            return
        first_paint = paints[0]
        if not isinstance(first_paint, Mapping):
            return
        if str(first_paint.get("type") or "solid").strip().casefold() != "solid":
            return
        updated_paint = json_deepcopy(dict(first_paint))
        updated_paint["color"] = json_deepcopy(value)
        paints[0] = updated_paint
        style[paint_key] = paints
        return

    if isinstance(value, bool):
        return
    try:
        width = float(value)
    except (TypeError, ValueError):
        return
    if not math.isfinite(width):
        return
    strokes_value = style.get("strokes")
    if not isinstance(strokes_value, list) or not strokes_value:
        return
    first_stroke = strokes_value[0]
    if not isinstance(first_stroke, Mapping):
        return
    strokes = list(strokes_value)
    updated_stroke = json_deepcopy(dict(first_stroke))
    updated_stroke["width"] = max(0.0, width)
    strokes[0] = updated_stroke
    style["strokes"] = strokes


def resolve_ui_theme_object(
    row: Mapping[str, Any],
    *,
    theme: str,
    tokens: Mapping[str, Mapping[str, Any]],
    variable_modes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    resolved = json_deepcopy(dict(row))
    applied: dict[str, dict[str, Any]] = {}
    normalized_theme = normalize_ui_theme(theme)
    bindings = row.get("token_bindings")
    bindings = bindings if isinstance(bindings, Mapping) else {}
    for path, token_id_value in sorted(bindings.items(), key=lambda item: str(item[0])):
        token_id = str(token_id_value or "")
        value, chain = _token_value(
            token_id,
            theme=normalized_theme,
            variable_modes=variable_modes,
            tokens=tokens,
        )
        if value is None or not _set_binding_path(resolved, str(path), value):
            continue
        _synchronize_canonical_style_binding(resolved, str(path), value)
        applied[str(path)] = {
            "token_id": token_id,
            "alias_chain": chain,
            "value": json_deepcopy(value),
        }
    resolved["resolved_theme"] = normalized_theme
    resolved["resolved_tokens"] = applied
    return resolved


# Resolution reads objects, artboards, components, tokens and variables, but
# never the selection or the revision counter.  Clicking an object therefore
# asks for the exact same resolved document again, and on a large imported file
# recomputing it costs seconds.  Digesting the document minus those two volatile
# keys is ~0.1s, so a small cache turns a click into a copy instead of a solve.
_RESOLVED_CACHE: dict[bytes, dict[str, Any]] = {}
_RESOLVED_CACHE_LIMIT = 4
_RESOLVED_CACHE_MIN_OBJECTS = 400

# Per-row theme resolution memo, keyed by input-row identity. Rebuilt from the
# live rows on every pass so it never outgrows the document, and discarded
# whenever the token table changes because that would invalidate every entry.
_THEME_ROW_CACHE: dict[int, tuple[Any, str, str, dict[str, Any]]] = {}
_THEME_ROW_CACHE_TOKENS: bytes | None = None


def _canonical_digest_of(value: Any) -> bytes | None:
    from app.painter_ui_document import canonical_payload_digest

    return canonical_payload_digest({"rows": value})


def _variable_modes_key(modes: Mapping[str, str]) -> str:
    return "|".join(f"{key}={modes[key]}" for key in sorted(modes))


_CACHE_KEY_MEMO: dict[int, tuple[Any, tuple[Any, ...], bytes | None]] = {}
_CACHE_KEY_MEMO_LIMIT = 8


def _cache_key_identity(
    document: Mapping[str, Any], objects: list[Any]
) -> tuple[Any, ...]:
    """Cheap witness that ``document``'s digested content is unchanged.

    Holds the identity and length of every collection the digest covers, so
    replacing or resizing any of them invalidates the memo. Rewriting a row
    in place would slip through -- the same invariant ``_THEME_ROW_CACHE``
    already relies on, and the resolver chain upholds it by rebuilding rows
    rather than editing them.
    """
    artboards = document.get("artboards")
    pages = document.get("pages")
    tokens = document.get("tokens")
    return (
        id(objects),
        len(objects),
        id(artboards),
        len(artboards) if isinstance(artboards, list) else -1,
        id(pages),
        len(pages) if isinstance(pages, list) else -1,
        id(tokens),
        len(tokens) if isinstance(tokens, list) else -1,
        document.get("active_page_id"),
        document.get("active_artboard_id"),
    )


def _resolved_cache_key(document: Mapping[str, Any]) -> bytes | None:
    if type(document) is not dict:
        return None
    objects = document.get("objects")
    if not isinstance(objects, list) or len(objects) < _RESOLVED_CACHE_MIN_OBJECTS:
        return None

    # Digesting the key marshals the whole document, which on a large import
    # costs about as much as a cache hit saves -- and one edit asks for the
    # key several times over the same document object (validate, canvas, and
    # two inspector passes). Memoise per document instead of re-digesting.
    identity = _cache_key_identity(document, objects)
    memo = _CACHE_KEY_MEMO.get(id(document))
    if memo is not None and memo[0] is document and memo[1] == identity:
        return memo[2]

    from app.painter_ui_document import canonical_payload_digest

    key = canonical_payload_digest(
        {
            key_name: item
            for key_name, item in document.items()
            if key_name not in {"selection", "revision"}
        }
    )
    # Keeping the document alive stops its id being recycled behind the memo.
    _CACHE_KEY_MEMO[id(document)] = (document, identity, key)
    while len(_CACHE_KEY_MEMO) > _CACHE_KEY_MEMO_LIMIT:
        _CACHE_KEY_MEMO.pop(next(iter(_CACHE_KEY_MEMO)))
    return key


def resolve_ui_theme_document(
    value: Mapping[str, Any],
    *,
    normalize: bool = True,
    shared: bool = False,
) -> dict[str, Any]:
    """Resolve components, responsive overrides and theme tokens.

    ``shared=True`` is for callers that only read the result - they get the
    cached document itself rather than a clone, and they must not mutate it or
    rely on ``selection``/``revision``, which the cache deliberately ignores.
    Cloning the resolved document was the single largest cost of a click on a
    large imported file, and it happened even when the cache hit.
    """
    from app.painter_ui_components import resolve_ui_component_document
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_responsive import resolve_ui_responsive_document

    cache_key = _resolved_cache_key(value)
    if cache_key is not None:
        cached = _RESOLVED_CACHE.get(cache_key)
        if cached is not None:
            if shared:
                return cached
            resolved = json_deepcopy(cached)
            resolved["selection"] = json_deepcopy(
                dict(value.get("selection") or {})
            )
            resolved["revision"] = value.get("revision", 0)
            return resolved

    document = resolve_ui_component_document(
        normalize_ui_document(value) if normalize else value,
        normalize=False,
    )
    # The component pass above already handed back a private envelope, and the
    # theme pass below rebuilds the object list itself, so responsive resolution
    # can share every row it does not actually override.
    document = resolve_ui_responsive_document(document, share=True)
    tokens = {row["id"]: row for row in document["tokens"]}
    artboard_themes = {
        row["id"]: ui_theme_for_artboard(row)
        for row in document["artboards"]
    }
    artboard_variable_modes = {
        row["id"]: dict(row.get("variable_modes") or {})
        for row in document["artboards"]
    }
    # The modes key depends only on the artboard, so derive it once per
    # artboard rather than once per object. On a large import that is 123
    # sorted joins instead of 8.9k.
    artboard_modes_keys = {
        artboard_id: _variable_modes_key(modes)
        for artboard_id, modes in artboard_variable_modes.items()
    }
    # Theme resolution is a pure function of a row plus its artboard's theme,
    # variable modes and the token table. Everything upstream now preserves the
    # object identity of rows an edit did not touch, so an unchanged row can
    # reuse the row it resolved to last time instead of being solved again.
    global _THEME_ROW_CACHE, _THEME_ROW_CACHE_TOKENS
    tokens_fingerprint = _canonical_digest_of(document["tokens"])
    previous = (
        _THEME_ROW_CACHE
        if tokens_fingerprint is not None
        and tokens_fingerprint == _THEME_ROW_CACHE_TOKENS
        else {}
    )
    current: dict[int, tuple[Any, str, str, dict[str, Any]]] = {}
    resolved_rows: list[dict[str, Any]] = []
    for row in document["objects"]:
        artboard_id = row["artboard_id"]
        theme = artboard_themes.get(artboard_id, "light")
        modes_key = artboard_modes_keys.get(artboard_id, "")
        cached = previous.get(id(row))
        if (
            cached is not None
            and cached[0] is row
            and cached[1] == theme
            and cached[2] == modes_key
        ):
            resolved_row = cached[3]
        else:
            resolved_row = resolve_ui_theme_object(
                row,
                theme=theme,
                variable_modes=artboard_variable_modes.get(artboard_id, {}),
                tokens=tokens,
            )
        # Holding the input row keeps its id from being recycled behind the key.
        current[id(row)] = (row, theme, modes_key, resolved_row)
        resolved_rows.append(resolved_row)
    _THEME_ROW_CACHE = current
    _THEME_ROW_CACHE_TOKENS = tokens_fingerprint
    document["objects"] = resolved_rows
    document["resolved_themes"] = artboard_themes
    document["resolved_variable_modes"] = artboard_variable_modes
    if cache_key is not None:
        # A shared caller promised not to mutate what it gets back, so the
        # cache can hold the very document being returned instead of paying
        # for a second full clone on every miss.
        _RESOLVED_CACHE[cache_key] = document if shared else json_deepcopy(document)
        while len(_RESOLVED_CACHE) > _RESOLVED_CACHE_LIMIT:
            _RESOLVED_CACHE.pop(next(iter(_RESOLVED_CACHE)))
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
                "resolved_tokens": json_deepcopy(row["resolved_tokens"]),
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
