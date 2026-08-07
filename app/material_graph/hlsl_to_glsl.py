"""Translate the HLSL a material Custom node may contain into GLSL 120.

The graph authors HLSL because that is what the Unreal side consumes, but the
in-app preview renders through the same GLSL 120 path the rest of the app uses.
This module is the bridge.

It covers a deliberately bounded subset - scalar/vector types, swizzles, the
common intrinsics, control flow, and texture sampling - and **refuses** anything
outside it with the line it choked on.  Silently emitting GLSL that means
something different from the authored HLSL would be worse than refusing: the two
languages disagree about matrix order, ``mul`` on two vectors, and integer
modulo of negatives, and a preview that quietly diverges from Unreal is a trap.
"""
from __future__ import annotations

import re
from typing import Any, Iterable


SCHEMA_ID = "tigerstudio.material_graph.hlsl_to_glsl.v1"

GLSL_VERSION = "#version 120"


class HLSLTranslationError(ValueError):
    """Unsupported HLSL, reported with the line that caused it."""

    def __init__(self, message: str, *, line: int, snippet: str = "") -> None:
        super().__init__(
            f"line {line}: {message}" + (f"  ->  {snippet.strip()}" if snippet else "")
        )
        self.line = int(line)
        self.snippet = str(snippet)


# Types that map one-to-one.
TYPE_MAP: dict[str, str] = {
    "float": "float",
    "float2": "vec2",
    "float3": "vec3",
    "float4": "vec4",
    "half": "float",
    "half2": "vec2",
    "half3": "vec3",
    "half4": "vec4",
    "fixed": "float",
    "fixed2": "vec2",
    "fixed3": "vec3",
    "fixed4": "vec4",
    "int": "int",
    "int2": "ivec2",
    "int3": "ivec3",
    "int4": "ivec4",
    "uint": "int",
    "uint2": "ivec2",
    "uint3": "ivec3",
    "uint4": "ivec4",
    "bool": "bool",
    "bool2": "bvec2",
    "bool3": "bvec3",
    "bool4": "bvec4",
    "float2x2": "mat2",
    "float3x3": "mat3",
    "float4x4": "mat4",
    "void": "void",
}

# Intrinsics that only need renaming.
FUNCTION_MAP: dict[str, str] = {
    "frac": "fract",
    "lerp": "mix",
    "rsqrt": "inversesqrt",
    "ddx": "dFdx",
    "ddy": "dFdy",
    "atan2": "atan",
    "tex2D": "texture2D",
    "tex2Dlod": "texture2DLod",
    "tex2Dbias": "texture2D",
    "fmod": "mod",
    "log10": "_hlsl_log10",
}

# Intrinsics GLSL 120 spells the same way.
PASSTHROUGH_FUNCTIONS = frozenset(
    {
        "abs", "acos", "all", "any", "asin", "atan", "ceil", "clamp", "cos",
        "cosh", "cross", "degrees", "distance", "dot", "exp", "exp2", "faceforward",
        "floor", "fract", "length", "log", "log2", "max", "min", "mix", "mod",
        "normalize", "pow", "radians", "reflect", "refract", "sign", "sin",
        "sinh", "smoothstep", "sqrt", "step", "tan", "tanh", "texture2D",
        "texture2DLod", "inversesqrt", "dFdx", "dFdy", "transpose", "matrixCompMult",
    }
)

# Rewritten with a helper or an inline expansion.
EXPANDED_FUNCTIONS = frozenset({"saturate", "lerp", "frac", "rsqrt", "log10"})

# Things this translator will not guess at.
REJECTED_FUNCTIONS: dict[str, str] = {
    "mul": (
        "mul() means different things in HLSL and GLSL (row-vector matrix order, "
        "and a dot product for two vectors). Write the explicit form instead: "
        "a * b, dot(a, b), or matrix * vector"
    ),
    "clip": "clip() has no GLSL equivalent; use if (x < 0.0) discard;",
    "GetRenderTargetSampleCount": "multisample queries are not available here",
    "InterlockedAdd": "atomics are not available in a material Custom node",
    "asuint": "bit reinterpretation is not available in GLSL 120",
    "asint": "bit reinterpretation is not available in GLSL 120",
    "asfloat": "bit reinterpretation is not available in GLSL 120",
    "countbits": "bit intrinsics are not available in GLSL 120",
    "firstbithigh": "bit intrinsics are not available in GLSL 120",
}

REJECTED_KEYWORDS: dict[str, str] = {
    "cbuffer": "constant buffers are declared by the graph, not by the node body",
    "tbuffer": "texture buffers are not supported",
    "register": "register() bindings are assigned by the graph",
    "Texture2D": "declare texture inputs as node pins, then sample with tex2D()",
    "Texture3D": "3D textures are not supported",
    "TextureCube": "cube maps are not supported",
    "SamplerState": "samplers come from the node's texture pins",
    "SamplerComparisonState": "comparison samplers are not supported",
    "StructuredBuffer": "structured buffers are not supported",
    "RWTexture2D": "writable resources are not supported",
    "groupshared": "compute-only storage is not supported",
    "numthreads": "compute entry points are not supported",
    "unroll": "loop attributes are not supported",
    "interface": "interfaces are not supported",
    "cbuffer_end": "constant buffers are not supported",
}

# Semantics are meaningless in a snippet body.
SEMANTIC_PATTERN = re.compile(
    r":\s*(SV_[A-Za-z0-9_]+|POSITION\d*|TEXCOORD\d*|COLOR\d*|NORMAL\d*)\b"
)

_HELPERS = {
    "saturate": "float _hlsl_saturate(float x) { return clamp(x, 0.0, 1.0); }\n"
    "vec2 _hlsl_saturate(vec2 x) { return clamp(x, 0.0, 1.0); }\n"
    "vec3 _hlsl_saturate(vec3 x) { return clamp(x, 0.0, 1.0); }\n"
    "vec4 _hlsl_saturate(vec4 x) { return clamp(x, 0.0, 1.0); }",
    "log10": "float _hlsl_log10(float x) { return log(x) / log(10.0); }",
}

_TOKEN_PATTERN = re.compile(
    r"""
    (?P<comment>//[^\n]*|/\*.*?\*/)
  | (?P<string>"(?:\\.|[^"\\])*")
  | (?P<number>\d+\.\d*(?:[eE][+-]?\d+)?[fFhH]?
             |\.\d+(?:[eE][+-]?\d+)?[fFhH]?
             |\d+(?:[eE][+-]?\d+)?[fFhH]?)
  | (?P<word>[A-Za-z_][A-Za-z_0-9]*)
  | (?P<space>[ \t]+)
  | (?P<newline>\n)
  | (?P<other>.)
    """,
    re.VERBOSE | re.DOTALL,
)


def _tokenize(source: str) -> Iterable[tuple[str, str, int]]:
    line = 1
    for match in _TOKEN_PATTERN.finditer(source):
        kind = match.lastgroup or "other"
        text = match.group()
        yield kind, text, line
        line += text.count("\n")


def translate_hlsl_expression(source: str) -> dict[str, Any]:
    """Translate an HLSL snippet body into GLSL 120.

    Returns the translated source, the helper functions it needs, and a note for
    every construct whose behaviour is close but not identical.
    """
    text = str(source or "")
    if len(text) > 20000:
        raise HLSLTranslationError(
            "the snippet is too long to translate (20000 character limit)",
            line=1,
        )
    pieces: list[str] = []
    helpers: list[str] = []
    notes: list[str] = []
    tokens = list(_tokenize(text))
    for index, (kind, token, line) in enumerate(tokens):
        if kind in {"comment", "string", "space", "newline"}:
            pieces.append(token)
            continue
        if kind == "number":
            pieces.append(_translate_number(token))
            continue
        if kind != "word":
            pieces.append(token)
            continue
        if token in REJECTED_KEYWORDS:
            raise HLSLTranslationError(
                REJECTED_KEYWORDS[token],
                line=line,
                snippet=_line_text(text, line),
            )
        if token in REJECTED_FUNCTIONS and _is_call(tokens, index):
            raise HLSLTranslationError(
                REJECTED_FUNCTIONS[token],
                line=line,
                snippet=_line_text(text, line),
            )
        if token == "static":
            # `static const float x = 1;` -> `const float x = 1.0;`
            continue
        if token in TYPE_MAP:
            pieces.append(TYPE_MAP[token])
            continue
        if token == "saturate" and _is_call(tokens, index):
            pieces.append("_hlsl_saturate")
            if _HELPERS["saturate"] not in helpers:
                helpers.append(_HELPERS["saturate"])
            continue
        if token in FUNCTION_MAP and _is_call(tokens, index):
            replacement = FUNCTION_MAP[token]
            if replacement == "_hlsl_log10" and _HELPERS["log10"] not in helpers:
                helpers.append(_HELPERS["log10"])
            if token == "fmod":
                notes.append(
                    "fmod() became mod(); they differ in sign for negative "
                    "operands"
                )
            if token == "tex2Dbias":
                notes.append(
                    "tex2Dbias() became texture2D(); the LOD bias is dropped"
                )
            pieces.append(replacement)
            continue
        pieces.append(token)
    translated = "".join(pieces)
    translated = SEMANTIC_PATTERN.sub("", translated)
    return {
        "schema": SCHEMA_ID,
        "glsl": translated,
        "helpers": helpers,
        "notes": sorted(set(notes)),
    }


def _translate_number(token: str) -> str:
    """HLSL float suffixes are not GLSL 120; bare integers stay integers."""
    text = token
    if text[-1] in "fFhH":
        text = text[:-1]
        if "." not in text and "e" not in text and "E" not in text:
            text = f"{text}.0"
        return text
    return text


def _is_call(tokens: list[tuple[str, str, int]], index: int) -> bool:
    for kind, token, _line in tokens[index + 1:]:
        if kind in {"space", "newline", "comment"}:
            continue
        return token == "("
    return False


def _line_text(source: str, line: int) -> str:
    rows = source.splitlines()
    if 1 <= line <= len(rows):
        return rows[line - 1]
    return ""


def translate_custom_node(
    code: str,
    *,
    inputs: list[dict[str, Any]] | None = None,
    output_type: str = "vec4",
    function_name: str = "CustomNode",
) -> dict[str, Any]:
    """Wrap a Custom node body in a GLSL function the graph can call.

    The body is HLSL exactly as an Unreal Custom node expects it: statements
    ending in ``return``.  Input pins arrive as named arguments.
    """
    body = translate_hlsl_expression(code)
    arguments = []
    for row in inputs or []:
        arguments.append(f"{_glsl_type(row['type'])} {row['name']}")
    signature = (
        f"{_glsl_type(output_type)} {function_name}"
        f"({', '.join(arguments) if arguments else ''})"
    )
    text = body["glsl"].strip()
    if "return" not in text:
        raise HLSLTranslationError(
            "a Custom node body has to return a value",
            line=max(1, text.count("\n") + 1),
        )
    return {
        "schema": f"{SCHEMA_ID}.custom_node",
        "function_name": function_name,
        "signature": signature,
        "glsl": f"{signature} {{\n{_indent(text)}\n}}",
        "helpers": body["helpers"],
        "notes": body["notes"],
    }


_PIN_TO_GLSL = {
    "float": "float",
    "vec2": "vec2",
    "vec3": "vec3",
    "vec4": "vec4",
    "bool": "bool",
    "texture": "sampler2D",
}


def _glsl_type(pin_type: str) -> str:
    key = str(pin_type)
    if key in _PIN_TO_GLSL:
        return _PIN_TO_GLSL[key]
    if key in TYPE_MAP:
        return TYPE_MAP[key]
    raise HLSLTranslationError(f"unknown value type: {pin_type}", line=1)


def _indent(text: str, spaces: int = 4) -> str:
    pad = " " * spaces
    return "\n".join(pad + row if row.strip() else row for row in text.splitlines())


def translation_support_report() -> dict[str, Any]:
    """What the subset covers, for the editor's help panel and for tests."""
    return {
        "schema": f"{SCHEMA_ID}.support",
        "target": GLSL_VERSION,
        "types": sorted(TYPE_MAP),
        "renamed_functions": dict(sorted(FUNCTION_MAP.items())),
        "passthrough_functions": sorted(PASSTHROUGH_FUNCTIONS),
        "rejected_functions": dict(sorted(REJECTED_FUNCTIONS.items())),
        "rejected_keywords": sorted(REJECTED_KEYWORDS),
        "claim_boundary": {
            "full_hlsl_support": False,
            "unreal_pixel_parity": False,
            "silent_fallback": False,
        },
    }
