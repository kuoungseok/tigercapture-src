from __future__ import annotations

from app.motion_designer.craft_style import make_craft_style_effect
from app.motion_designer.glass_gpu_renderer import MotionGlassGpuRenderer
from app.motion_designer.painterly_look import make_painterly_look_effect
from app.motion_designer.render_graph import build_render_graph
from app.motion_designer.schema import (
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    SourceRef,
)


def _composition(effect: MotionEffectRef) -> MotionComposition:
    return MotionComposition(
        id="style_gpu",
        name="Style GPU",
        width=320,
        height=180,
        duration_ms=2000,
        layers=[
            MotionLayer(
                id="background",
                name="Background",
                layer_type="shape",
                source=SourceRef(
                    kind="shape",
                    params={
                        "width": 320,
                        "height": 180,
                        "fill": "#246777",
                    },
                ),
            ),
            MotionLayer(
                id="styled",
                name="Styled",
                layer_type="shape",
                source=SourceRef(
                    kind="shape",
                    params={
                        "width": 180,
                        "height": 100,
                        "fill": "#e7644a",
                    },
                ),
                effects=[effect],
            ),
        ],
    )


def test_craft_style_is_eligible_for_common_gpu_compositor() -> None:
    graph = build_render_graph(
        _composition(make_craft_style_effect(preset="archive_print")),
        500,
        render_quality="preview",
    )
    assert MotionGlassGpuRenderer.can_draw(graph) == (True, "")


def test_painterly_style_is_eligible_for_common_gpu_compositor() -> None:
    graph = build_render_graph(
        _composition(make_painterly_look_effect(preset="ink")),
        500,
        render_quality="preview",
    )
    assert MotionGlassGpuRenderer.can_draw(graph) == (True, "")


def test_style_gpu_rejects_unsupported_and_stacked_effects() -> None:
    composition = _composition(make_craft_style_effect())
    composition.layers[-1].effects.append(MotionEffectRef(kind="glow"))
    graph = build_render_graph(composition, 500, render_quality="preview")
    assert MotionGlassGpuRenderer.can_draw(graph) == (
        False,
        "unsupported_effect_requires_raster",
    )

    composition.layers[-1].effects = [
        make_craft_style_effect(),
        make_painterly_look_effect(preset="toon"),
    ]
    graph = build_render_graph(composition, 500, render_quality="preview")
    assert MotionGlassGpuRenderer.can_draw(graph) == (
        False,
        "stacked_style_effects_require_raster",
    )


def test_style_gpu_accepts_motion_blur_for_shared_gpu_sampling() -> None:
    composition = _composition(make_craft_style_effect())
    composition.layers[-1].metadata["motion_blur"] = {
        "enabled": True,
        "samples": 8,
        "shutter": 0.65,
    }
    graph = build_render_graph(composition, 500, render_quality="preview")
    assert MotionGlassGpuRenderer.can_draw(graph) == (True, "")


def test_style_gpu_accepts_common_compositing_blend_modes() -> None:
    for blend_mode in ("multiply", "screen", "add", "overlay"):
        composition = _composition(make_craft_style_effect())
        composition.layers[-1].blend_mode = blend_mode
        graph = build_render_graph(composition, 500, render_quality="preview")
        assert MotionGlassGpuRenderer.can_draw(graph) == (True, "")


def test_style_gpu_rejects_unknown_compositing_blend_mode() -> None:
    composition = _composition(make_craft_style_effect())
    composition.layers[-1].blend_mode = "color_dodge"
    graph = build_render_graph(composition, 500, render_quality="preview")
    assert MotionGlassGpuRenderer.can_draw(graph) == (
        False,
        "blend_mode:color_dodge",
    )


def test_common_gpu_compositor_accepts_alpha_and_luma_track_mattes() -> None:
    for matte_mode in ("alpha", "luma", "alpha_inverted", "luma_inverted"):
        composition = _composition(make_craft_style_effect())
        matte = MotionLayer(
            id="matte",
            name="Matte",
            layer_type="shape",
            source=SourceRef(
                kind="shape",
                params={
                    "width": 120,
                    "height": 120,
                    "fill": "#ffffff",
                },
            ),
        )
        composition.layers.insert(1, matte)
        composition.layers[-1].metadata["matte_layer_id"] = matte.id
        composition.layers[-1].metadata["matte_mode"] = matte_mode
        graph = build_render_graph(composition, 500, render_quality="preview")
        assert MotionGlassGpuRenderer.can_draw(graph) == (True, "")


def test_style_gpu_fails_closed_for_unimplemented_texture_inputs() -> None:
    craft = make_craft_style_effect()
    craft.metadata["texture"] = {"uri": "paper.png"}
    graph = build_render_graph(
        _composition(craft),
        500,
        render_quality="preview",
    )
    assert MotionGlassGpuRenderer.can_draw(graph) == (
        False,
        "craft_texture_requires_raster",
    )

    painterly = make_painterly_look_effect(preset="paper")
    painterly.metadata["projected_texture"] = {"uri": "fiber.png"}
    graph = build_render_graph(
        _composition(painterly),
        500,
        render_quality="preview",
    )
    assert MotionGlassGpuRenderer.can_draw(graph) == (
        False,
        "painterly_texture_requires_raster",
    )
