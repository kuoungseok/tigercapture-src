"""Contract for HLSL authoring and its GLSL 120 backend."""
from __future__ import annotations

import pytest


def test_support_report_refuses_to_claim_full_hlsl() -> None:
    from app.material_graph.hlsl_to_glsl import translation_support_report

    report = translation_support_report()
    assert report["target"] == "#version 120"
    assert report["claim_boundary"]["full_hlsl_support"] is False
    assert report["claim_boundary"]["unreal_pixel_parity"] is False
    assert report["claim_boundary"]["silent_fallback"] is False
    assert "mul" in report["rejected_functions"]


@pytest.mark.parametrize(
    "hlsl, expected",
    [
        ("float3 c = 1.0f;", "vec3 c = 1.0;"),
        ("float4 c = float4(1, 0, 0, 1);", "vec4 c = vec4(1, 0, 0, 1);"),
        ("float x = saturate(y);", "float x = _hlsl_saturate(y);"),
        ("float x = lerp(a, b, t);", "float x = mix(a, b, t);"),
        ("float x = frac(y);", "float x = fract(y);"),
        ("float x = rsqrt(y);", "float x = inversesqrt(y);"),
        ("float x = atan2(y, z);", "float x = atan(y, z);"),
        ("float4 t = tex2D(s, uv);", "vec4 t = texture2D(s, uv);"),
        ("half3 c = 2.5h;", "vec3 c = 2.5;"),
        ("static const float k = 3;", " const float k = 3;"),
        ("float3x3 m;", "mat3 m;"),
    ],
)
def test_supported_constructs_translate(hlsl: str, expected: str) -> None:
    from app.material_graph.hlsl_to_glsl import translate_hlsl_expression

    assert translate_hlsl_expression(hlsl)["glsl"].strip() == expected.strip()


def test_translation_leaves_comments_and_strings_alone() -> None:
    from app.material_graph.hlsl_to_glsl import translate_hlsl_expression

    source = '// lerp float4 saturate\nfloat x = 1.0f; /* float3 */'
    glsl = translate_hlsl_expression(source)["glsl"]
    assert "// lerp float4 saturate" in glsl
    assert "/* float3 */" in glsl
    assert "float x = 1.0;" in glsl


@pytest.mark.parametrize(
    "hlsl, fragment",
    [
        ("return mul(M, v);", "mul()"),
        ("Texture2D albedo; return 0;", "texture inputs as node pins"),
        ("SamplerState s; return 0;", "samplers come from"),
        ("cbuffer Globals { float x; }; return 0;", "constant buffers"),
        ("clip(x); return 0;", "discard"),
        ("return asfloat(bits);", "bit reinterpretation"),
    ],
)
def test_unsupported_constructs_are_refused_with_the_line(
    hlsl: str,
    fragment: str,
) -> None:
    from app.material_graph.hlsl_to_glsl import (
        HLSLTranslationError,
        translate_hlsl_expression,
    )

    with pytest.raises(HLSLTranslationError) as error:
        translate_hlsl_expression(hlsl)
    assert fragment in str(error.value)
    assert str(error.value).startswith("line ")


def test_fmod_translation_admits_the_sign_difference() -> None:
    from app.material_graph.hlsl_to_glsl import translate_hlsl_expression

    result = translate_hlsl_expression("float x = fmod(a, b);")
    assert "mod(a, b)" in result["glsl"]
    assert any("sign" in note for note in result["notes"])


def test_custom_node_becomes_a_callable_glsl_function() -> None:
    from app.material_graph.hlsl_to_glsl import translate_custom_node

    result = translate_custom_node(
        "float3 c = lerp(A.rgb, B.rgb, saturate(T));\nreturn float4(c, A.a);",
        inputs=[
            {"name": "A", "type": "vec4"},
            {"name": "B", "type": "vec4"},
            {"name": "T", "type": "float"},
        ],
        output_type="vec4",
        function_name="Custom_1",
    )
    assert result["signature"] == "vec4 Custom_1(vec4 A, vec4 B, float T)"
    assert "mix(A.rgb, B.rgb, _hlsl_saturate(T))" in result["glsl"]
    assert result["helpers"]


def test_custom_node_without_a_return_is_refused() -> None:
    from app.material_graph.hlsl_to_glsl import (
        HLSLTranslationError,
        translate_custom_node,
    )

    with pytest.raises(HLSLTranslationError):
        translate_custom_node("float x = 1.0f;", output_type="float")


def test_custom_node_pins_follow_what_the_node_declares() -> None:
    from app.material_graph import document
    from app.material_graph.registry import node_pins

    graph = document.create_graph("ui")
    graph, custom = document.add_node(graph, "CustomHLSL", position=(0, 0))
    graph = document.set_node_param(
        graph,
        custom["id"],
        "Inputs",
        [
            {"name": "Base", "type": "vec4"},
            {"name": "9bad", "type": "float"},
            {"name": "Base", "type": "float"},
            {"name": "Mask", "type": "float"},
        ],
    )
    node = document.node_by_id(graph, custom["id"])
    inputs, outputs = node_pins(node)
    # Invalid and duplicate names drop out; the rest keep their declared type.
    assert [row["name"] for row in inputs] == ["Base", "Mask"]
    assert [row["type"] for row in inputs] == ["vec4", "float"]
    assert outputs == [{"name": "Result", "type": "vec4"}]


def test_graph_compiles_to_a_shader_that_uses_every_reachable_node() -> None:
    from app.material_graph import document
    from app.material_graph.compile_glsl import compile_graph_glsl

    graph = document.create_graph("ui")
    graph, uv = document.add_node(graph, "TextureCoordinate", position=(-400, 0))
    graph, gradient = document.add_node(graph, "LinearGradient", position=(-160, 0))
    graph, custom = document.add_node(graph, "CustomHLSL", position=(80, 0))
    graph, orphan = document.add_node(graph, "Multiply", position=(80, 300))
    graph = document.set_node_param(
        graph,
        custom["id"],
        "Inputs",
        [{"name": "Base", "type": "vec4"}, {"name": "UV", "type": "vec2"}],
    )
    graph = document.set_node_param(
        graph,
        custom["id"],
        "Code",
        "float v = 1.0f - saturate(distance(UV, float2(0.5f, 0.5f)));\n"
        "return float4(Base.rgb * v, Base.a);",
    )
    graph = document.connect(graph, uv["id"], "UV", gradient["id"], "UV")
    graph = document.connect(graph, gradient["id"], "Color", custom["id"], "Base")
    graph = document.connect(graph, uv["id"], "UV", custom["id"], "UV")
    graph = document.connect(graph, custom["id"], "Result", "output", "Final Color")

    result = compile_graph_glsl(graph)
    glsl = result["glsl"]
    assert glsl.startswith("#version 120")
    assert "gl_FragColor" in glsl
    assert "_hlsl_saturate" in glsl
    assert f"custom_{custom['id']}" in glsl
    assert orphan["id"] in result["skipped_node_ids"]
    assert custom["id"] in result["emitted_node_ids"]
    # Every per-node symbol main() reads has been declared by an earlier line,
    # which is what the topological emission order is for.
    import re

    body = glsl.split("void main() {", 1)[1]
    declared: set[str] = set()
    for line in body.splitlines():
        used = set(re.findall(r"\bn_[A-Za-z0-9_]+\b", line))
        match = re.match(r"\s*\w+\s+(n_[A-Za-z0-9_]+)\s*=", line)
        introduced = {match.group(1)} if match else set()
        assert not (used - introduced - declared), line
        declared |= introduced


def test_unconnected_outputs_fall_back_to_their_declared_defaults() -> None:
    from app.material_graph import document
    from app.material_graph.compile_glsl import compile_graph_glsl

    ui = compile_graph_glsl(document.create_graph("ui"))["glsl"]
    assert "_final_opacity = 1" in ui
    pbr = compile_graph_glsl(document.create_graph("pbr"))["glsl"]
    assert "_base_color = vec3(0.5, 0.5, 0.5)" in pbr


def test_a_refused_snippet_names_the_node_that_holds_it() -> None:
    from app.material_graph import document
    from app.material_graph.compile_glsl import GraphCompileError, compile_graph_glsl

    graph = document.create_graph("ui")
    graph, custom = document.add_node(graph, "CustomHLSL", position=(0, 0))
    graph = document.set_node_param(graph, custom["id"], "Code", "return mul(M, A);")
    graph = document.connect(graph, custom["id"], "Result", "output", "Final Color")
    with pytest.raises(GraphCompileError) as error:
        compile_graph_glsl(graph)
    assert error.value.node_id == custom["id"]
    assert "mul()" in str(error.value)


def test_preview_reports_why_it_cannot_render_instead_of_going_blank() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.material_graph import document
    from app.material_graph.preview import (
        preview_backend_status,
        render_graph_preview,
    )

    status = preview_backend_status()
    assert status["target"] == "#version 120"

    graph = document.create_graph("ui")
    result = render_graph_preview(graph, width=32, height=32)
    assert result["glsl"].startswith("#version 120")
    if status["available"]:
        assert result["compiled"] is True, result["reason"]
        assert result["rendered"] is True, result["reason"]
        assert result["image"] is not None
    else:
        # No context here: the report has to say so rather than pretend.
        assert result["rendered"] is False
        assert result["reason"]


def test_preview_reports_a_rejected_snippet_without_touching_gl() -> None:
    from app.material_graph import document
    from app.material_graph.preview import render_graph_preview

    graph = document.create_graph("ui")
    graph, custom = document.add_node(graph, "CustomHLSL", position=(0, 0))
    graph = document.set_node_param(graph, custom["id"], "Code", "return mul(M, A);")
    graph = document.connect(graph, custom["id"], "Result", "output", "Final Color")
    result = render_graph_preview(graph)
    assert result["compiled"] is False
    assert result["failed_node_id"] == custom["id"]
    assert "mul()" in result["reason"]
