"""Adapter-owned developer values and snippets for Painter UI selections."""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_motion_bridge import resolved_ui_geometry


DEV_SNIPPET_SCHEMA = "tigerstudio.painter.ui.dev_snippets.v1"
WEB_CSS_ADAPTER = "tigerstudio.painter.ui.web_css.v1"


def _css_number(value: object) -> str:
    number = float(value or 0.0)
    return f"{number:g}px"


def _css_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _web_css_snippet(
    row: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    style = dict(row.get("style") or {})
    layout = dict(row.get("layout") or {})
    content = dict(row.get("content") or {})
    declarations = [
        "position: absolute;",
        f"left: {_css_number(geometry.get('x'))};",
        f"top: {_css_number(geometry.get('y'))};",
        f"width: {_css_number(geometry.get('width'))};",
        f"height: {_css_number(geometry.get('height'))};",
        f"opacity: {float(row.get('opacity', 1.0)):g};",
    ]
    rotation = float(row.get("rotation") or 0.0)
    if rotation:
        declarations.append(f"transform: rotate({rotation:g}deg);")
    fill = style.get("fill")
    if fill:
        property_name = "color" if row.get("kind") == "text" else "background"
        declarations.append(f"{property_name}: {_css_value(fill)};")
    stroke = style.get("stroke")
    stroke_width = float(style.get("stroke_width") or 0.0)
    if stroke and stroke_width > 0:
        declarations.append(
            f"border: {_css_number(stroke_width)} solid {_css_value(stroke)};"
        )
    radius = float(style.get("radius") or 0.0)
    if radius:
        declarations.append(f"border-radius: {_css_number(radius)};")
    shadow = style.get("shadow")
    if isinstance(shadow, Mapping) and shadow:
        declarations.append(
            "box-shadow: {x} {y} {blur} {spread} {color};".format(
                x=_css_number(shadow.get("x")),
                y=_css_number(shadow.get("y")),
                blur=_css_number(shadow.get("blur")),
                spread=_css_number(shadow.get("spread")),
                color=_css_value(shadow.get("color") or "#00000040"),
            )
        )
    if row.get("kind") == "text":
        if style.get("font_family"):
            declarations.append(
                f"font-family: {json.dumps(str(style['font_family']))};"
            )
        if style.get("font_size"):
            declarations.append(f"font-size: {_css_number(style['font_size'])};")
        if style.get("font_weight"):
            declarations.append(f"font-weight: {_css_value(style['font_weight'])};")
        if style.get("line_height"):
            declarations.append(f"line-height: {_css_value(style['line_height'])};")
        if style.get("text_align"):
            declarations.append(f"text-align: {_css_value(style['text_align'])};")
    mode = str(layout.get("mode") or "none")
    if mode in {"horizontal", "vertical"}:
        declarations.extend(
            [
                "display: flex;",
                f"flex-direction: {'row' if mode == 'horizontal' else 'column'};",
                f"gap: {_css_number(layout.get('gap'))};",
            ]
        )
        padding = dict(layout.get("padding") or {})
        declarations.append(
            "padding: {top} {right} {bottom} {left};".format(
                top=_css_number(padding.get("top")),
                right=_css_number(padding.get("right")),
                bottom=_css_number(padding.get("bottom")),
                left=_css_number(padding.get("left")),
            )
        )
        main = {
            "start": "flex-start",
            "center": "center",
            "end": "flex-end",
            "space_between": "space-between",
        }.get(str(layout.get("main_alignment") or "start"), "flex-start")
        cross = {
            "start": "flex-start",
            "center": "center",
            "end": "flex-end",
            "stretch": "stretch",
        }.get(str(layout.get("cross_alignment") or "start"), "flex-start")
        declarations.extend(
            [f"justify-content: {main};", f"align-items: {cross};"]
        )
        if layout.get("wrap"):
            declarations.append("flex-wrap: wrap;")
    unsupported = []
    if row.get("mask", {}).get("enabled"):
        unsupported.append("mask")
    if content.get("boolean", {}).get("enabled"):
        unsupported.append("boolean_geometry")
    if content.get("text_ranges"):
        unsupported.append("mixed_text_ranges")
    if style.get("font_axes"):
        unsupported.append("variable_font_axes")
    if len(style.get("fills") or []) > 1:
        unsupported.append("multiple_fills")
    if len(style.get("strokes") or []) > 1:
        unsupported.append("multiple_strokes")
    if str(style.get("blend_mode") or "normal") not in {"normal", "pass_through"}:
        unsupported.append("blend_mode")
    selector = f'[data-tiger-id="{row["id"]}"]'
    code = selector + " {\n  " + "\n  ".join(declarations) + "\n}"
    return {
        "id": "web_css",
        "target": "web",
        "label": "Web / CSS",
        "adapter": WEB_CSS_ADAPTER,
        "language": "css",
        "available": True,
        "code": code,
        "unsupported": unsupported,
    }


def _canonical_snippet(
    row: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "geometry": copy.deepcopy(dict(geometry)),
        "layout": copy.deepcopy(dict(row.get("layout") or {})),
        "style": copy.deepcopy(dict(row.get("style") or {})),
        "content": copy.deepcopy(dict(row.get("content") or {})),
        "token_bindings": copy.deepcopy(dict(row.get("token_bindings") or {})),
        "accessibility": copy.deepcopy(dict(row.get("accessibility") or {})),
    }
    return {
        "id": "app_contract",
        "target": "app",
        "label": "App / Tiger JSON",
        "adapter": "tigerstudio.painter.ui.app_contract.v1",
        "language": "json",
        "available": True,
        "code": json.dumps(payload, ensure_ascii=False, indent=2),
        "unsupported": [],
    }


def _umg_snippet(
    document: Mapping[str, Any],
    object_id: str,
    artboard_id: str,
) -> dict[str, Any]:
    from app.painter_ui_umg_adapter import (
        PAINTER_UMG_ADAPTER_SCHEMA,
        painter_ui_to_umg_document,
    )

    umg_document = painter_ui_to_umg_document(
        document,
        artboard_id=artboard_id,
    )
    layer = next(
        (row for row in umg_document["Layers"] if row["Id"] == object_id),
        None,
    )
    if layer is None:
        return {
            "id": "unreal_umg",
            "target": "umg",
            "label": "Unreal / UMG",
            "adapter": PAINTER_UMG_ADAPTER_SCHEMA,
            "language": "json",
            "available": False,
            "code": "",
            "unsupported": ["object_not_emitted"],
        }
    return {
        "id": "unreal_umg",
        "target": "umg",
        "label": "Unreal / UMG",
        "adapter": PAINTER_UMG_ADAPTER_SCHEMA,
        "language": "json",
        "available": True,
        "code": json.dumps(layer, ensure_ascii=False, indent=2),
        "disposition": layer["Disposition"],
        "unsupported": list(layer.get("BlockReasons") or []),
    }


def _unavailable_snippet(target: str, label: str) -> dict[str, Any]:
    return {
        "id": f"{target}_unavailable",
        "target": target,
        "label": label,
        "adapter": "",
        "language": "",
        "available": False,
        "code": "",
        "unsupported": ["adapter_not_implemented"],
    }


def inspect_ui_dev_snippets(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    stable_id = str(object_id or "")
    row = next(
        (item for item in document["objects"] if item["id"] == stable_id),
        None,
    )
    if row is None:
        raise ValueError(f"Painter UI object not found: {stable_id}")
    geometry = resolved_ui_geometry(document).get(stable_id, {})
    snippets = [
        _web_css_snippet(row, geometry),
        _canonical_snippet(row, geometry),
        _umg_snippet(document, stable_id, row["artboard_id"]),
        _unavailable_snippet("ios", "iOS"),
        _unavailable_snippet("android", "Android"),
    ]
    return {
        "schema": DEV_SNIPPET_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "object_id": stable_id,
        "snippets": snippets,
    }


__all__ = [
    "DEV_SNIPPET_SCHEMA",
    "WEB_CSS_ADAPTER",
    "inspect_ui_dev_snippets",
]
