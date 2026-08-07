"""Node vocabulary shared by the UI material and PBR texture graphs.

The video workbench graph (``app.workbench.node_graph``) speaks DaVinci: fixed
RGB/KEY ports, thumbnail bodies, no pin names.  Unreal-facing surfaces need the
opposite - named, typed pins on nodes whose title tells you what they do - so
they get their own vocabulary here rather than borrowing that one's tokens.

The look follows the conventions an Unreal node editor uses publicly: a title
bar tinted by node category, pins carrying their own name and a colour taken
from the value type, and wires that inherit the source pin's colour.  Nothing
here is derived from Unreal Engine source; the mapping below is ours.
"""
from __future__ import annotations

from typing import Any, Mapping


SCHEMA_ID = "tigerstudio.material_graph.registry.v1"

# ---------------------------------------------------------------- pin types

PIN_TYPES: dict[str, dict[str, Any]] = {
    "float": {"label": "Float", "color": "#86D96B", "components": 1},
    "vec2": {"label": "Vector 2", "color": "#5BC0DE", "components": 2},
    "vec3": {"label": "Vector 3", "color": "#F5C842", "components": 3},
    "vec4": {"label": "Vector 4", "color": "#E8A33D", "components": 4},
    "bool": {"label": "Bool", "color": "#A63B3B", "components": 1},
    "texture": {"label": "Texture", "color": "#7A5CD6", "components": 0},
}

# A link is legal when the source type can stand in for the target type.  Scalar
# promotion matches what a material editor does when you drop a float into a
# colour input; everything else has to match exactly.
PIN_PROMOTIONS: dict[str, tuple[str, ...]] = {
    "float": ("float", "vec2", "vec3", "vec4"),
    "vec2": ("vec2",),
    "vec3": ("vec3", "vec4"),
    "vec4": ("vec4", "vec3"),
    "bool": ("bool", "float"),
    "texture": ("texture",),
}

# ------------------------------------------------------------- categories

CATEGORIES: dict[str, dict[str, Any]] = {
    "input": {"label": "Input", "title_color": "#26456E"},
    "parameter": {"label": "Parameter", "title_color": "#2E6B5B"},
    "texture": {"label": "Texture", "title_color": "#5A3E86"},
    "math": {"label": "Math", "title_color": "#3D4A5C"},
    "color": {"label": "Color", "title_color": "#6B3F6B"},
    "utility": {"label": "Utility", "title_color": "#3F4A45"},
    "output": {"label": "Output", "title_color": "#7A3B2E"},
}


def _pin(name: str, pin_type: str, **extra: Any) -> dict[str, Any]:
    row = {"name": name, "type": pin_type}
    row.update(extra)
    return row


def _node(
    node_type: str,
    title: str,
    category: str,
    *,
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    params: list[dict[str, Any]] | None = None,
    surfaces: tuple[str, ...] = ("ui", "pbr"),
    summary: str = "",
) -> dict[str, Any]:
    return {
        "type": node_type,
        "title": title,
        "category": category,
        "inputs": list(inputs or []),
        "outputs": list(outputs or []),
        "params": list(params or []),
        "surfaces": tuple(surfaces),
        "summary": summary,
    }


def _param(
    name: str,
    param_type: str,
    default: Any,
    **extra: Any,
) -> dict[str, Any]:
    row = {"name": name, "type": param_type, "default": default}
    row.update(extra)
    return row


_NODE_LIST: list[dict[str, Any]] = [
    # -- input -----------------------------------------------------------
    _node(
        "TextureCoordinate",
        "Texture Coordinate",
        "input",
        outputs=[_pin("UV", "vec2")],
        params=[_param("Tiling", "vec2", [1.0, 1.0])],
        summary="Surface UV, optionally tiled.",
    ),
    _node(
        "SourceImage",
        "Source Image",
        "input",
        outputs=[
            _pin("RGB", "vec3"),
            _pin("Alpha", "float"),
            _pin("Luminance", "float"),
        ],
        surfaces=("pbr",),
        summary="The image the Texture Lab was opened on.",
    ),
    # -- parameter -------------------------------------------------------
    _node(
        "ScalarParameter",
        "Scalar Parameter",
        "parameter",
        outputs=[_pin("Value", "float")],
        params=[
            _param("Name", "string", "Scalar"),
            _param("Value", "float", 1.0, minimum=-64.0, maximum=64.0),
        ],
        summary="Named float exposed to the material instance.",
    ),
    _node(
        "ColorParameter",
        "Color Parameter",
        "parameter",
        outputs=[_pin("Color", "vec4"), _pin("RGB", "vec3")],
        params=[
            _param("Name", "string", "Color"),
            _param("Value", "vec4", [1.0, 1.0, 1.0, 1.0]),
        ],
        summary="Named RGBA exposed to the material instance.",
    ),
    # -- texture ---------------------------------------------------------
    _node(
        "TextureSample",
        "Texture Sample",
        "texture",
        inputs=[_pin("UV", "vec2")],
        outputs=[
            _pin("RGB", "vec3"),
            _pin("R", "float"),
            _pin("G", "float"),
            _pin("B", "float"),
            _pin("A", "float"),
        ],
        params=[_param("Texture", "asset", "")],
        summary="Sample a texture at the given UV.",
    ),
    _node(
        "NormalFromHeight",
        "Normal From Height",
        "texture",
        inputs=[_pin("Height", "float")],
        outputs=[_pin("Normal", "vec3")],
        params=[
            _param("Strength", "float", 1.0, minimum=0.0, maximum=8.0),
        ],
        surfaces=("pbr",),
        summary="Derive a tangent-space normal from a height field.",
    ),
    _node(
        "AmbientOcclusionFromHeight",
        "AO From Height",
        "texture",
        inputs=[_pin("Height", "float")],
        outputs=[_pin("Occlusion", "float")],
        params=[
            _param("Radius", "float", 0.5, minimum=0.0, maximum=1.0),
            _param("Strength", "float", 1.0, minimum=0.0, maximum=4.0),
        ],
        surfaces=("pbr",),
        summary="Cavity occlusion estimated from a height field.",
    ),
    # -- math ------------------------------------------------------------
    _node(
        "Add",
        "Add",
        "math",
        inputs=[_pin("A", "float"), _pin("B", "float")],
        outputs=[_pin("Result", "float")],
        summary="A + B, component-wise.",
    ),
    _node(
        "Multiply",
        "Multiply",
        "math",
        inputs=[_pin("A", "float"), _pin("B", "float")],
        outputs=[_pin("Result", "float")],
        summary="A * B, component-wise.",
    ),
    _node(
        "Lerp",
        "Linear Interpolate",
        "math",
        inputs=[
            _pin("A", "float"),
            _pin("B", "float"),
            _pin("Alpha", "float"),
        ],
        outputs=[_pin("Result", "float")],
        summary="Blend A to B by Alpha.",
    ),
    _node(
        "OneMinus",
        "One Minus",
        "math",
        inputs=[_pin("Input", "float")],
        outputs=[_pin("Result", "float")],
        summary="1 - Input.",
    ),
    _node(
        "Clamp",
        "Clamp",
        "math",
        inputs=[_pin("Input", "float")],
        outputs=[_pin("Result", "float")],
        params=[
            _param("Min", "float", 0.0),
            _param("Max", "float", 1.0),
        ],
        summary="Hold the input between two bounds.",
    ),
    _node(
        "Power",
        "Power",
        "math",
        inputs=[_pin("Base", "float"), _pin("Exponent", "float")],
        outputs=[_pin("Result", "float")],
        summary="Base raised to Exponent.",
    ),
    # -- color -----------------------------------------------------------
    _node(
        "Desaturation",
        "Desaturation",
        "color",
        inputs=[_pin("Color", "vec3"), _pin("Fraction", "float")],
        outputs=[_pin("Result", "vec3")],
        summary="Pull colour toward its luminance.",
    ),
    _node(
        "LinearGradient",
        "Linear Gradient",
        "color",
        inputs=[_pin("UV", "vec2")],
        outputs=[_pin("Color", "vec4")],
        params=[
            _param("Start", "vec2", [0.0, 0.0]),
            _param("End", "vec2", [1.0, 0.0]),
            _param("StartColor", "vec4", [0.0, 0.0, 0.0, 1.0]),
            _param("EndColor", "vec4", [1.0, 1.0, 1.0, 1.0]),
        ],
        surfaces=("ui",),
        summary="Two-stop gradient along an axis.",
    ),
    _node(
        "RoundedCard",
        "Rounded Card",
        "color",
        inputs=[_pin("UV", "vec2"), _pin("Fill", "vec4")],
        outputs=[_pin("Color", "vec4"), _pin("Mask", "float")],
        params=[
            _param("CornerRadius", "float", 12.0, minimum=0.0),
            _param("Smoothing", "float", 0.0, minimum=0.0, maximum=1.0),
            _param("StrokeWidth", "float", 0.0, minimum=0.0),
        ],
        surfaces=("ui",),
        summary="Rounded rectangle SDF with optional stroke.",
    ),
    # -- utility ---------------------------------------------------------
    _node(
        "Append",
        "Append",
        "utility",
        inputs=[_pin("A", "float"), _pin("B", "float")],
        outputs=[_pin("Result", "vec2")],
        summary="Join two values into a wider vector.",
    ),
    _node(
        "ComponentMask",
        "Component Mask",
        "utility",
        inputs=[_pin("Input", "vec4")],
        outputs=[_pin("Result", "float")],
        params=[_param("Channels", "string", "R")],
        summary="Pick channels out of a vector.",
    ),
    _node(
        "CustomHLSL",
        "Custom HLSL",
        "utility",
        params=[
            _param(
                "Inputs",
                "pin_list",
                [{"name": "A", "type": "vec4"}],
                maximum=8,
            ),
            _param("Output Type", "pin_type", "vec4"),
            _param(
                "Code",
                "code",
                "return A;",
                language="hlsl",
            ),
        ],
        summary=(
            "Author HLSL the way an Unreal Custom node takes it; the preview "
            "translates it to GLSL."
        ),
    ),
    _node(
        "Reroute",
        "Reroute",
        "utility",
        inputs=[_pin("In", "float")],
        outputs=[_pin("Out", "float")],
        summary="Wire tidy-up point; passes its input through.",
    ),
    # -- output ----------------------------------------------------------
    _node(
        "UIOutput",
        "UI Material Output",
        "output",
        inputs=[
            _pin("Final Color", "vec3", default=[0.0, 0.0, 0.0]),
            _pin("Opacity", "float", default=1.0),
        ],
        surfaces=("ui",),
        summary="What the UMG material draws.",
    ),
    _node(
        "PBROutput",
        "PBR Material Output",
        "output",
        inputs=[
            _pin("Base Color", "vec3", default=[0.5, 0.5, 0.5]),
            _pin("Normal", "vec3", default=[0.5, 0.5, 1.0]),
            _pin("Roughness", "float", default=0.5),
            _pin("Metallic", "float", default=0.0),
            _pin("Ambient Occlusion", "float", default=1.0),
            _pin("Height", "float", default=0.0),
        ],
        surfaces=("pbr",),
        summary="The map set the Texture Lab exports.",
    ),
]

NODE_TYPES: dict[str, dict[str, Any]] = {row["type"]: row for row in _NODE_LIST}

OUTPUT_TYPES: dict[str, str] = {"ui": "UIOutput", "pbr": "PBROutput"}


def node_definition(node_type: str) -> dict[str, Any] | None:
    row = NODE_TYPES.get(str(node_type))
    return dict(row) if row is not None else None


def node_types_for_surface(surface: str) -> list[dict[str, Any]]:
    """Every node the given surface is allowed to place, in palette order."""
    wanted = str(surface)
    rows = [
        dict(row)
        for row in _NODE_LIST
        if wanted in row["surfaces"]
    ]
    order = list(CATEGORIES)
    rows.sort(key=lambda row: (order.index(row["category"]), row["title"]))
    return rows


def pin_color(pin_type: str) -> str:
    return str(PIN_TYPES.get(str(pin_type), PIN_TYPES["float"])["color"])


def category_title_color(category: str) -> str:
    row = CATEGORIES.get(str(category), CATEGORIES["utility"])
    return str(row["title_color"])


def pins_are_compatible(source_type: str, target_type: str) -> bool:
    """Whether an output of ``source_type`` may drive ``target_type``."""
    allowed = PIN_PROMOTIONS.get(str(source_type))
    if not allowed:
        return False
    return str(target_type) in allowed


def default_param_values(node_type: str) -> dict[str, Any]:
    definition = NODE_TYPES.get(str(node_type))
    if definition is None:
        return {}
    values: dict[str, Any] = {}
    for row in definition["params"]:
        default = row["default"]
        values[str(row["name"])] = (
            list(default) if isinstance(default, (list, tuple)) else default
        )
    return values


def registry_report() -> dict[str, Any]:
    """Machine-readable dump used by tests and the palette UI."""
    return {
        "schema": SCHEMA_ID,
        "pin_types": {key: dict(value) for key, value in PIN_TYPES.items()},
        "categories": {key: dict(value) for key, value in CATEGORIES.items()},
        "node_types": sorted(NODE_TYPES),
        "surfaces": {
            surface: [row["type"] for row in node_types_for_surface(surface)]
            for surface in ("ui", "pbr")
        },
        "claim_boundary": {
            "unreal_source_derived": False,
            "unreal_pixel_parity": False,
        },
    }


DYNAMIC_PIN_TYPES = frozenset({"CustomHLSL"})

MAX_DYNAMIC_PINS = 8

_IDENTIFIER = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


def normalize_pin_list(value: Any) -> list[dict[str, str]]:
    """Clean a user-declared pin list: valid identifiers, known types, unique."""
    rows: list[dict[str, str]] = []
    taken: set[str] = set()
    for item in value or []:
        if not isinstance(item, Mapping):
            continue
        name = "".join(
            character
            for character in str(item.get("name") or "")
            if character in _IDENTIFIER
        )
        if not name or name[0].isdigit():
            continue
        if name in taken:
            continue
        pin_type = str(item.get("type") or "float")
        if pin_type not in PIN_TYPES:
            pin_type = "float"
        taken.add(name)
        rows.append({"name": name, "type": pin_type})
        if len(rows) >= MAX_DYNAMIC_PINS:
            break
    return rows


def node_pins(node: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Inputs and outputs of one node instance.

    Most nodes take theirs straight from the type definition; a Custom node
    declares its own, the way an Unreal Custom node does.
    """
    node_type = str(node.get("type") or "")
    definition = NODE_TYPES.get(node_type)
    if definition is None:
        return [], []
    if node_type not in DYNAMIC_PIN_TYPES:
        return (
            [dict(row) for row in definition["inputs"]],
            [dict(row) for row in definition["outputs"]],
        )
    params = node.get("params")
    params = params if isinstance(params, Mapping) else {}
    inputs = normalize_pin_list(params.get("Inputs"))
    output_type = str(params.get("Output Type") or "vec4")
    if output_type not in PIN_TYPES:
        output_type = "vec4"
    return (
        [dict(row) for row in inputs],
        [{"name": "Result", "type": output_type}],
    )


def resolve_pin(
    node_type: str,
    pin_name: str,
    *,
    is_input: bool,
    node: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    if node is not None:
        inputs, outputs = node_pins(node)
        rows = inputs if is_input else outputs
    else:
        definition = NODE_TYPES.get(str(node_type))
        if definition is None:
            return None
        rows = definition["inputs"] if is_input else definition["outputs"]
    for row in rows:
        if str(row["name"]) == str(pin_name):
            return dict(row)
    return None
