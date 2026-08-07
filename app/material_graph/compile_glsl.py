"""Compile an authored material graph into a GLSL 120 fragment shader.

The graph is authored against Unreal's vocabulary - HLSL in the Custom nodes,
Unreal-shaped output pins - and previewed through the same GLSL 120 offscreen
path the rest of the app already uses.  This module walks the graph in
dependency order and emits one statement per node.

Emission never guesses: a node whose input is unconnected falls back to a
declared default, and anything the translator refuses stops the compile with the
node and line that caused it.
"""
from __future__ import annotations

from typing import Any, Mapping

from app.material_graph import document as graph_document
from app.material_graph.hlsl_to_glsl import (
    GLSL_VERSION,
    HLSLTranslationError,
    translate_custom_node,
)
from app.material_graph.registry import PIN_TYPES, node_pins


SCHEMA_ID = "tigerstudio.material_graph.compile_glsl.v1"


class GraphCompileError(ValueError):
    """A graph that cannot be turned into a shader, with the node to blame."""

    def __init__(self, message: str, *, node_id: str = "") -> None:
        super().__init__(
            f"{node_id}: {message}" if node_id else str(message)
        )
        self.node_id = str(node_id)


_GLSL_TYPE = {
    "float": "float",
    "vec2": "vec2",
    "vec3": "vec3",
    "vec4": "vec4",
    "bool": "bool",
    "texture": "sampler2D",
}

_ZERO = {
    "float": "0.0",
    "vec2": "vec2(0.0)",
    "vec3": "vec3(0.0)",
    "vec4": "vec4(0.0, 0.0, 0.0, 1.0)",
    "bool": "false",
}

# What the preview feeds the graph.  Kept small and explicit so the shader the
# editor compiles is the shader the tests read.
PREAMBLE = """varying vec2 v_uv;
uniform sampler2D u_source;
uniform vec2 u_resolution;
"""


def _cast(expression: str, source_type: str, target_type: str) -> str:
    """Widen or narrow a value the way the pin promotion rules allow."""
    if source_type == target_type:
        return expression
    source_size = int(PIN_TYPES.get(source_type, {}).get("components", 1))
    target_size = int(PIN_TYPES.get(target_type, {}).get("components", 1))
    if source_type == "bool":
        expression = f"float({expression})"
        source_size = 1
    if target_type == "bool":
        return f"({expression} != 0.0)"
    if source_size == 1 and target_size > 1:
        return f"{_GLSL_TYPE[target_type]}({expression})"
    if source_size == 3 and target_type == "vec4":
        return f"vec4({expression}, 1.0)"
    if source_size == 4 and target_type == "vec3":
        return f"({expression}).rgb"
    if source_size > target_size:
        swizzle = "xyzw"[:target_size]
        return f"({expression}).{swizzle}"
    if source_size < target_size:
        padding = ", ".join(["0.0"] * (target_size - source_size))
        return f"{_GLSL_TYPE[target_type]}({expression}, {padding})"
    return expression


def _default_expression(pin: Mapping[str, Any], node: Mapping[str, Any]) -> str:
    """What an unconnected input reads as.

    A pin may declare its own resting value - an unconnected Opacity is 1, not
    0 - which is what keeps a half-built graph previewing as something visible.
    """
    pin_type = str(pin["type"])
    if pin_type == "texture":
        return "u_source"
    if "default" in pin:
        return _literal(pin["default"], pin_type)
    return _ZERO.get(pin_type, "0.0")


def _param(node: Mapping[str, Any], name: str, fallback: Any = 0.0) -> Any:
    params = node.get("params") or {}
    return params.get(name, fallback)


def _literal(value: Any, pin_type: str) -> str:
    if isinstance(value, (list, tuple)):
        numbers = ", ".join(f"{float(item):.9g}" for item in value)
        return f"{_GLSL_TYPE.get(pin_type, 'vec4')}({numbers})"
    return f"{float(value):.9g}"


def compile_graph_glsl(
    graph: Mapping[str, Any],
    *,
    entry_point: str = "main",
) -> dict[str, Any]:
    """Emit a complete GLSL 120 fragment shader for the graph."""
    current = graph_document.normalize_graph(graph)
    report = graph_document.graph_report(current)
    by_id = {row["id"]: row for row in current["nodes"]}
    output_id = report["output_id"]
    if not output_id:
        raise GraphCompileError("the graph has no output node")

    incoming: dict[tuple[str, str], dict[str, Any]] = {
        (row["to_node"], row["to_pin"]): row for row in current["links"]
    }
    reachable = set(report["evaluation_order"]) - set(report["unreachable_node_ids"])
    helpers: list[str] = []
    functions: list[str] = []
    body: list[str] = []
    notes: list[str] = []
    values: dict[tuple[str, str], tuple[str, str]] = {}

    def value_of(node_id: str, pin: Mapping[str, Any]) -> str:
        """GLSL expression driving an input pin, cast to the pin's type."""
        link = incoming.get((node_id, str(pin["name"])))
        if link is None:
            return _default_expression(pin, by_id[node_id])
        stored = values.get((link["from_node"], link["from_pin"]))
        if stored is None:
            raise GraphCompileError(
                f"input {pin['name']} is driven by a node that has not been "
                "emitted yet",
                node_id=node_id,
            )
        expression, source_type = stored
        return _cast(expression, source_type, str(pin["type"]))

    for node_id in report["evaluation_order"]:
        if node_id not in reachable:
            continue
        node = by_id[node_id]
        inputs, outputs = node_pins(node)
        emitted = _emit_node(
            node,
            inputs,
            outputs,
            value_of=value_of,
            body=body,
            functions=functions,
            helpers=helpers,
            notes=notes,
        )
        for pin_name, (expression, pin_type) in emitted.items():
            values[(node_id, pin_name)] = (expression, pin_type)

    output_node = by_id[output_id]
    output_inputs, _ = node_pins(output_node)
    channels = {
        str(pin["name"]): value_of(output_id, pin) for pin in output_inputs
    }
    if current["surface"] == "ui":
        colour = channels.get("Final Color", "vec3(0.0)")
        opacity = channels.get("Opacity", "1.0")
        body.append(f"    vec3 _final_color = {colour};")
        body.append(f"    float _final_opacity = {opacity};")
        body.append("    gl_FragColor = vec4(_final_color, _final_opacity);")
    else:
        base = channels.get("Base Color", "vec3(0.0)")
        body.append(f"    vec3 _base_color = {base};")
        body.append("    gl_FragColor = vec4(_base_color, 1.0);")

    source = "\n".join(
        [
            GLSL_VERSION,
            PREAMBLE.rstrip(),
            "",
            *_unique(helpers),
            "",
            *functions,
            "",
            f"void {entry_point}() {{",
            *body,
            "}",
            "",
        ]
    )
    return {
        "schema": SCHEMA_ID,
        "surface": current["surface"],
        "glsl": source,
        "channels": sorted(channels),
        "notes": sorted(set(notes)),
        "emitted_node_ids": [
            node_id for node_id in report["evaluation_order"] if node_id in reachable
        ],
        "skipped_node_ids": list(report["unreachable_node_ids"]),
    }


def _unique(rows: list[str]) -> list[str]:
    seen: set[str] = set()
    kept: list[str] = []
    for row in rows:
        if row in seen:
            continue
        seen.add(row)
        kept.append(row)
    return kept


def _emit_node(
    node: Mapping[str, Any],
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    *,
    value_of,
    body: list[str],
    functions: list[str],
    helpers: list[str],
    notes: list[str],
) -> dict[str, tuple[str, str]]:
    node_id = str(node["id"])
    node_type = str(node["type"])
    name = f"n_{node_id}"

    def read(pin_name: str) -> str:
        for pin in inputs:
            if str(pin["name"]) == pin_name:
                return value_of(node_id, pin)
        return "0.0"

    def declare(pin_name: str, pin_type: str, expression: str) -> None:
        symbol = f"{name}_{_symbol(pin_name)}"
        body.append(f"    {_GLSL_TYPE[pin_type]} {symbol} = {expression};")
        emitted[pin_name] = (symbol, pin_type)

    emitted: dict[str, tuple[str, str]] = {}

    if node_type == "TextureCoordinate":
        tiling = _literal(_param(node, "Tiling", [1.0, 1.0]), "vec2")
        declare("UV", "vec2", f"v_uv * {tiling}")
    elif node_type == "SourceImage":
        body.append(f"    vec4 {name}_texel = texture2D(u_source, v_uv);")
        emitted["RGB"] = (f"{name}_texel.rgb", "vec3")
        emitted["Alpha"] = (f"{name}_texel.a", "float")
        declare(
            "Luminance",
            "float",
            f"dot({name}_texel.rgb, vec3(0.2126, 0.7152, 0.0722))",
        )
    elif node_type == "ScalarParameter":
        declare("Value", "float", _literal(_param(node, "Value", 1.0), "float"))
    elif node_type == "ColorParameter":
        declare(
            "Color",
            "vec4",
            _literal(_param(node, "Value", [1.0, 1.0, 1.0, 1.0]), "vec4"),
        )
        emitted["RGB"] = (f"{name}_Color.rgb", "vec3")
    elif node_type == "TextureSample":
        uv = read("UV")
        body.append(f"    vec4 {name}_texel = texture2D(u_source, {uv});")
        emitted["RGB"] = (f"{name}_texel.rgb", "vec3")
        for channel in "RGBA":
            emitted[channel] = (
                f"{name}_texel.{channel.lower()}",
                "float",
            )
    elif node_type == "NormalFromHeight":
        strength = _literal(_param(node, "Strength", 1.0), "float")
        height = read("Height")
        body.append(f"    float {name}_h = {height};")
        body.append(
            f"    vec3 {name}_n = normalize(vec3("
            f"-dFdx({name}_h) * {strength} * 8.0, "
            f"-dFdy({name}_h) * {strength} * 8.0, 1.0));"
        )
        emitted["Normal"] = (f"({name}_n * 0.5 + 0.5)", "vec3")
        notes.append(
            "Normal From Height previews with screen-space derivatives; the "
            "exported map is generated at full resolution instead"
        )
    elif node_type == "AmbientOcclusionFromHeight":
        strength = _literal(_param(node, "Strength", 1.0), "float")
        height = read("Height")
        declare(
            "Occlusion",
            "float",
            f"clamp(1.0 - ({height}) * {strength}, 0.0, 1.0)",
        )
        notes.append(
            "AO From Height previews as a height falloff; the exported map "
            "uses the Texture Lab solver"
        )
    elif node_type in {"Add", "Multiply", "Power"}:
        left = read("A" if node_type != "Power" else "Base")
        right = read("B" if node_type != "Power" else "Exponent")
        operator = {"Add": "+", "Multiply": "*"}.get(node_type)
        if operator is None:
            declare("Result", "float", f"pow(max({left}, 0.0), {right})")
        else:
            declare("Result", "float", f"({left}) {operator} ({right})")
    elif node_type == "Lerp":
        declare(
            "Result",
            "float",
            f"mix({read('A')}, {read('B')}, {read('Alpha')})",
        )
    elif node_type == "OneMinus":
        declare("Result", "float", f"1.0 - ({read('Input')})")
    elif node_type == "Clamp":
        low = _literal(_param(node, "Min", 0.0), "float")
        high = _literal(_param(node, "Max", 1.0), "float")
        declare("Result", "float", f"clamp({read('Input')}, {low}, {high})")
    elif node_type == "Desaturation":
        colour = read("Color")
        fraction = read("Fraction")
        body.append(f"    vec3 {name}_c = {colour};")
        declare(
            "Result",
            "vec3",
            f"mix({name}_c, vec3(dot({name}_c, vec3(0.3, 0.59, 0.11))), "
            f"{fraction})",
        )
    elif node_type == "Append":
        declare("Result", "vec2", f"vec2({read('A')}, {read('B')})")
    elif node_type == "ComponentMask":
        channels = str(_param(node, "Channels", "R")) or "R"
        swizzle = "".join(
            {"R": "r", "G": "g", "B": "b", "A": "a"}.get(item.upper(), "r")
            for item in channels
        )[:4] or "r"
        pin_type = {1: "float", 2: "vec2", 3: "vec3", 4: "vec4"}[len(swizzle)]
        declare("Result", pin_type, f"({read('Input')}).{swizzle}")
    elif node_type == "Reroute":
        declare("Out", "float", read("In"))
    elif node_type == "LinearGradient":
        start = _literal(_param(node, "Start", [0.0, 0.0]), "vec2")
        end = _literal(_param(node, "End", [1.0, 0.0]), "vec2")
        first = _literal(_param(node, "StartColor", [0, 0, 0, 1]), "vec4")
        last = _literal(_param(node, "EndColor", [1, 1, 1, 1]), "vec4")
        uv = read("UV")
        body.append(f"    vec2 {name}_axis = {end} - {start};")
        body.append(
            f"    float {name}_t = clamp(dot(({uv}) - {start}, {name}_axis) "
            f"/ max(dot({name}_axis, {name}_axis), 1e-6), 0.0, 1.0);"
        )
        declare("Color", "vec4", f"mix({first}, {last}, {name}_t)")
    elif node_type == "RoundedCard":
        radius = _literal(_param(node, "CornerRadius", 12.0), "float")
        stroke = _literal(_param(node, "StrokeWidth", 0.0), "float")
        uv = read("UV")
        fill = read("Fill")
        body.append(f"    vec2 {name}_p = (({uv}) - 0.5) * u_resolution;")
        body.append(f"    vec2 {name}_half = u_resolution * 0.5;")
        body.append(
            f"    vec2 {name}_q = abs({name}_p) - ({name}_half - {radius});"
        )
        body.append(
            f"    float {name}_sdf = length(max({name}_q, vec2(0.0))) "
            f"+ min(max({name}_q.x, {name}_q.y), 0.0) - {radius};"
        )
        declare(
            "Mask",
            "float",
            f"clamp(0.5 - {name}_sdf, 0.0, 1.0)",
        )
        stroke_term = (
            f"clamp(0.5 - abs({name}_sdf + {stroke} * 0.5) + {stroke} * 0.5, "
            "0.0, 1.0)"
        )
        declare(
            "Color",
            "vec4",
            f"vec4(({fill}).rgb, ({fill}).a * max({name}_Mask, {stroke_term}))",
        )
    elif node_type == "CustomHLSL":
        emitted.update(
            _emit_custom_hlsl(
                node,
                inputs,
                outputs,
                read=read,
                body=body,
                functions=functions,
                helpers=helpers,
                notes=notes,
            )
        )
    elif node_type in {"UIOutput", "PBROutput"}:
        pass
    else:
        raise GraphCompileError(
            f"no shader emitter for node type {node_type}",
            node_id=node_id,
        )
    return emitted


def _emit_custom_hlsl(
    node: Mapping[str, Any],
    inputs: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
    *,
    read,
    body: list[str],
    functions: list[str],
    helpers: list[str],
    notes: list[str],
) -> dict[str, tuple[str, str]]:
    node_id = str(node["id"])
    function_name = f"custom_{_symbol(node_id)}"
    output_type = str(outputs[0]["type"]) if outputs else "vec4"
    try:
        translated = translate_custom_node(
            str(_param(node, "Code", "return A;")),
            inputs=[
                {"name": str(row["name"]), "type": str(row["type"])}
                for row in inputs
            ],
            output_type=output_type,
            function_name=function_name,
        )
    except HLSLTranslationError as error:
        raise GraphCompileError(str(error), node_id=node_id) from error
    helpers.extend(translated["helpers"])
    functions.append(translated["glsl"])
    notes.extend(translated["notes"])
    arguments = ", ".join(read(str(row["name"])) for row in inputs)
    symbol = f"n_{node_id}_Result"
    body.append(
        f"    {_GLSL_TYPE[output_type]} {symbol} = "
        f"{function_name}({arguments});"
    )
    return {"Result": (symbol, output_type)}


def _symbol(value: str) -> str:
    text = "".join(
        character if character.isalnum() else "_" for character in str(value)
    )
    return text or "v"
