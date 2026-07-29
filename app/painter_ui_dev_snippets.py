"""Adapter-owned developer values and snippets for Painter UI selections."""
from __future__ import annotations

import copy
import json
import re
import textwrap
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document
from app.painter_ui_motion_bridge import resolved_ui_geometry


DEV_SNIPPET_SCHEMA = "tigerstudio.painter.ui.dev_snippets.v2"
WEB_CSS_ADAPTER = "tigerstudio.painter.ui.web_css.v1"
SWIFTUI_ADAPTER = "tigerstudio.painter.ui.swiftui.v1"
COMPOSE_ADAPTER = "tigerstudio.painter.ui.compose.v1"


def _css_number(value: object) -> str:
    number = float(value or 0.0)
    return f"{number:g}px"


def _css_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _platform_unsupported(row: Mapping[str, Any]) -> list[str]:
    style = dict(row.get("style") or {})
    content = dict(row.get("content") or {})
    unsupported: list[str] = []
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
    if isinstance(style.get("fill"), Mapping):
        unsupported.append("non_solid_fill")
    return unsupported


def _rgba(value: object) -> tuple[int, int, int, int] | None:
    text = str(value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text) + "FF"
    elif len(text) == 6:
        text += "FF"
    if len(text) != 8:
        return None
    try:
        return tuple(int(text[index : index + 2], 16) for index in range(0, 8, 2))
    except ValueError:
        return None


def _swift_color(value: object) -> str | None:
    rgba = _rgba(value)
    if rgba is None:
        return None
    red, green, blue, alpha = rgba
    return (
        "Color(red: {red:.4f}, green: {green:.4f}, blue: {blue:.4f}, "
        "opacity: {alpha:.4f})"
    ).format(
        red=red / 255.0,
        green=green / 255.0,
        blue=blue / 255.0,
        alpha=alpha / 255.0,
    )


def _compose_color(value: object) -> str | None:
    rgba = _rgba(value)
    if rgba is None:
        return None
    red, green, blue, alpha = rgba
    return f"Color(0x{alpha:02X}{red:02X}{green:02X}{blue:02X})"


def _swift_font_weight(value: object) -> str:
    named = str(value or "").strip().lower().replace("-", "")
    if named and not named.isdigit():
        return {
            "ultralight": "ultraLight",
            "extralight": "thin",
            "regular": "regular",
            "normal": "regular",
            "medium": "medium",
            "semibold": "semibold",
            "demibold": "semibold",
            "bold": "bold",
            "extrabold": "heavy",
            "black": "black",
        }.get(named, "regular")
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        return "regular"
    if numeric >= 900:
        return "black"
    if numeric >= 800:
        return "heavy"
    if numeric >= 700:
        return "bold"
    if numeric >= 600:
        return "semibold"
    if numeric >= 500:
        return "medium"
    if numeric <= 200:
        return "ultraLight"
    if numeric <= 300:
        return "light"
    return "regular"


def _android_resource_name(value: object) -> str:
    name = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower())
    name = name.strip("_") or "image_asset"
    if name[0].isdigit():
        name = f"asset_{name}"
    return name


def _pascal_identifier(value: object, fallback: str = "TigerObject") -> str:
    words = re.findall(r"[A-Za-z0-9]+", str(value or ""))
    name = "".join(word[:1].upper() + word[1:] for word in words) or fallback
    if name[0].isdigit():
        name = f"Tiger{name}"
    return name


def _swiftui_snippet(
    row: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    style = dict(row.get("style") or {})
    layout = dict(row.get("layout") or {})
    content = dict(row.get("content") or {})
    kind = str(row.get("kind") or "frame")
    text = json.dumps(str(content.get("text") or row.get("name") or "Text"))
    if kind == "text":
        expression = f"Text({text})"
    elif kind == "button":
        expression = f"Button(action: {{ }}) {{ Text({text}) }}"
    elif kind == "image":
        asset = json.dumps(str(content.get("resource_id") or row.get("name") or "Asset"))
        expression = f"Image({asset}).resizable()"
    elif kind == "ellipse":
        expression = "Ellipse()"
    else:
        expression = "Rectangle()"

    modifiers = [
        ".frame(width: {width:g}, height: {height:g})".format(
            width=float(geometry.get("width") or 0.0),
            height=float(geometry.get("height") or 0.0),
        ),
        ".position(x: {x:g}, y: {y:g})".format(
            x=float(geometry.get("x") or 0.0)
            + float(geometry.get("width") or 0.0) / 2.0,
            y=float(geometry.get("y") or 0.0)
            + float(geometry.get("height") or 0.0) / 2.0,
        ),
    ]
    fill = _swift_color(style.get("fill"))
    if fill:
        modifier = "foregroundStyle" if kind in {"text", "ellipse"} else "background"
        modifiers.append(f".{modifier}({fill})")
    radius = float(style.get("radius") or 0.0)
    if radius:
        modifiers.append(f".clipShape(RoundedRectangle(cornerRadius: {radius:g}))")
    stroke = _swift_color(style.get("stroke"))
    stroke_width = float(style.get("stroke_width") or 0.0)
    if stroke and stroke_width > 0:
        modifiers.append(
            ".overlay(RoundedRectangle(cornerRadius: {radius:g})"
            ".stroke({stroke}, lineWidth: {width:g}))".format(
                radius=radius,
                stroke=stroke,
                width=stroke_width,
            )
        )
    if kind == "text":
        if style.get("font_size"):
            modifiers.append(f".font(.system(size: {float(style['font_size']):g}))")
        if style.get("font_weight"):
            modifiers.append(
                f".fontWeight(.{_swift_font_weight(style['font_weight'])})"
            )
    opacity = float(row.get("opacity", 1.0))
    if opacity != 1.0:
        modifiers.append(f".opacity({opacity:g})")
    rotation = float(row.get("rotation") or 0.0)
    if rotation:
        modifiers.append(f".rotationEffect(.degrees({rotation:g}))")
    shadow = style.get("shadow")
    if isinstance(shadow, Mapping) and shadow:
        shadow_color = _swift_color(shadow.get("color") or "#00000040")
        if shadow_color:
            modifiers.append(
                ".shadow(color: {color}, radius: {blur:g}, x: {x:g}, y: {y:g})".format(
                    color=shadow_color,
                    blur=float(shadow.get("blur") or 0.0),
                    x=float(shadow.get("x") or 0.0),
                    y=float(shadow.get("y") or 0.0),
                )
            )
    mode = str(layout.get("mode") or "none")
    if mode in {"horizontal", "vertical"}:
        container = "HStack" if mode == "horizontal" else "VStack"
        expression = (
            f"{container}(spacing: {float(layout.get('gap') or 0.0):g}) {{\n"
            f"    {expression}\n"
            "}"
        )
        padding = dict(layout.get("padding") or {})
        for edge in ("top", "right", "bottom", "left"):
            value = float(padding.get(edge) or 0.0)
            if value:
                swift_edge = {"right": "trailing", "left": "leading"}.get(edge, edge)
                modifiers.append(f".padding(.{swift_edge}, {value:g})")
    body = expression
    if modifiers:
        body += "\n" + "\n".join(modifiers)
    view_name = _pascal_identifier(row.get("name"), "TigerObject") + "View"
    code = (
        "import SwiftUI\n\n"
        f"struct {view_name}: View {{\n"
        "    var body: some View {\n"
        f"{textwrap.indent(body, '        ')}\n"
        "    }\n"
        "}"
    )
    return {
        "id": "ios_swiftui",
        "target": "ios",
        "label": "iOS / SwiftUI",
        "adapter": SWIFTUI_ADAPTER,
        "language": "swift",
        "available": True,
        "code": code,
        "unsupported": _platform_unsupported(row),
    }


def _compose_snippet(
    row: Mapping[str, Any],
    geometry: Mapping[str, Any],
) -> dict[str, Any]:
    style = dict(row.get("style") or {})
    layout = dict(row.get("layout") or {})
    content = dict(row.get("content") or {})
    kind = str(row.get("kind") or "frame")
    text = json.dumps(str(content.get("text") or row.get("name") or "Text"))
    modifiers = [
        "Modifier",
        ".offset(x = {x:g}.dp, y = {y:g}.dp)".format(
            x=float(geometry.get("x") or 0.0),
            y=float(geometry.get("y") or 0.0),
        ),
        ".size(width = {width:g}.dp, height = {height:g}.dp)".format(
            width=float(geometry.get("width") or 0.0),
            height=float(geometry.get("height") or 0.0),
        ),
    ]
    fill = _compose_color(style.get("fill"))
    radius = float(style.get("radius") or 0.0)
    shape = f"RoundedCornerShape({radius:g}.dp)" if radius else "RectangleShape"
    if fill and kind != "text":
        modifiers.append(f".background({fill}, {shape})")
    stroke = _compose_color(style.get("stroke"))
    stroke_width = float(style.get("stroke_width") or 0.0)
    if stroke and stroke_width > 0:
        modifiers.append(f".border({stroke_width:g}.dp, {stroke}, {shape})")
    opacity = float(row.get("opacity", 1.0))
    if opacity != 1.0:
        modifiers.append(f".alpha({opacity:g}f)")
    rotation = float(row.get("rotation") or 0.0)
    if rotation:
        modifiers.append(f".rotate({rotation:g}f)")
    modifier = "\n        ".join(modifiers)
    if kind == "text":
        color = _compose_color(style.get("fill"))
        arguments = [f"text = {text}", f"modifier = {modifier}"]
        if color:
            arguments.append(f"color = {color}")
        if style.get("font_size"):
            arguments.append(f"fontSize = {float(style['font_size']):g}.sp")
        expression = "Text(\n    " + ",\n    ".join(arguments) + "\n)"
    elif kind == "button":
        expression = (
            "Button(\n"
            "    onClick = { },\n"
            f"    modifier = {modifier}\n"
            f") {{ Text({text}) }}"
        )
    elif kind == "image":
        resource = _android_resource_name(
            content.get("resource_id") or row.get("name") or "image_asset"
        )
        expression = (
            "Image(\n"
            f"    painter = painterResource(R.drawable.{resource}),\n"
            f"    contentDescription = {text},\n"
            f"    modifier = {modifier}\n"
            ")"
        )
    else:
        expression = f"Box(modifier = {modifier})"
    mode = str(layout.get("mode") or "none")
    if mode in {"horizontal", "vertical"}:
        container = "Row" if mode == "horizontal" else "Column"
        expression = f"{container}(horizontalArrangement = Arrangement.spacedBy({float(layout.get('gap') or 0.0):g}.dp)) {{\n    {expression}\n}}"
    function_name = _pascal_identifier(row.get("name"), "TigerObject")
    code = (
        "import androidx.compose.foundation.*\n"
        "import androidx.compose.foundation.layout.*\n"
        "import androidx.compose.foundation.shape.*\n"
        "import androidx.compose.material3.*\n"
        "import androidx.compose.ui.Modifier\n"
        "import androidx.compose.ui.draw.*\n"
        "import androidx.compose.ui.graphics.Color\n"
        "import androidx.compose.ui.res.painterResource\n"
        "import androidx.compose.ui.unit.*\n"
        "import androidx.compose.runtime.Composable\n\n"
        "@Composable\n"
        f"fun {function_name}() {{\n"
        f"{textwrap.indent(expression, '    ')}\n"
        "}"
    )
    unsupported = _platform_unsupported(row)
    if isinstance(style.get("shadow"), Mapping) and style.get("shadow"):
        unsupported.append("custom_shadow")
    return {
        "id": "android_compose",
        "target": "android",
        "label": "Android / Compose",
        "adapter": COMPOSE_ADAPTER,
        "language": "kotlin",
        "available": True,
        "code": code,
        "unsupported": unsupported,
    }


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
    unsupported = _platform_unsupported(row)
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
        _swiftui_snippet(row, geometry),
        _compose_snippet(row, geometry),
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
    "COMPOSE_ADAPTER",
    "SWIFTUI_ADAPTER",
    "WEB_CSS_ADAPTER",
    "inspect_ui_dev_snippets",
]
