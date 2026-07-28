from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.interchange import export_interchange, preflight_interchange
from app.motion_designer.schema import (
    MotionBehaviorRef, MotionComposition, MotionEffectRef, MotionLayer, SourceRef,
)


def _shape_text_composition() -> MotionComposition:
    shape = MotionLayer(
        name="Accent", layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "rectangle", "width": 320, "height": 80,
            "fill": "#24677f", "stroke": "#ffffff", "stroke_width": 2,
        }), out_ms=2000,
    )
    shape.transform.position.default = [400, 300]
    text = MotionLayer(
        name="Title", layer_type="text",
        source=SourceRef(kind="text", params={
            "text": "Tiger Studio", "font_family": "Segoe UI", "font_size": 64,
            "fill": "#ffffff", "width": 500, "height": 100,
        }), out_ms=2000,
    )
    text.transform.position.default = [400, 300]
    return MotionComposition(width=800, height=600, fps=30, duration_ms=2000, layers=[shape, text])


def test_lottie_and_svg_subset_write_real_documents(tmp_path: Path) -> None:
    composition = _shape_text_composition()
    lottie_path = tmp_path / "motion.json"
    svg_path = tmp_path / "motion.svg"
    export_interchange(composition, "lottie", lottie_path)
    export_interchange(composition, "svg", svg_path, time_ms=500)
    lottie = json.loads(lottie_path.read_text(encoding="utf-8"))
    svg = svg_path.read_text(encoding="utf-8")
    assert lottie["v"] == "5.12.2" and {layer["ty"] for layer in lottie["layers"]} == {4, 5}
    assert "Tiger Studio" in svg and "<path" in svg and "<text" in svg


def test_lottie_includes_layers_that_enter_after_zero(tmp_path: Path) -> None:
    composition = _shape_text_composition()
    composition.layers[1].in_ms = 1000
    output = tmp_path / "motion.json"

    export_interchange(composition, "lottie", output)

    lottie = json.loads(output.read_text(encoding="utf-8"))
    rows = {row["nm"]: row for row in lottie["layers"]}
    assert set(rows) == {"Accent", "Title"}
    assert rows["Title"]["ip"] == 30.0


def test_lottie_preflight_blocks_silent_effect_loss_and_requires_bake() -> None:
    composition = _shape_text_composition()
    composition.layers[0].effects.append(MotionEffectRef(kind="blur"))
    composition.layers[1].behaviors.append(MotionBehaviorRef(kind="wiggle"))
    report = preflight_interchange(composition, "lottie")
    assert report["ok"] is False
    assert report["blockers"][0]["layer_id"] == composition.layers[0].id
    assert any(row["layer_id"] == composition.layers[1].id for row in report["bake_required"])


def test_svg_preflight_reports_advanced_vector_and_text_bake_requirements() -> None:
    composition = _shape_text_composition()
    composition.layers[0].source.params["offset_path"] = {
        "amount": 12.0,
        "join": "round",
    }
    composition.layers[0].source.params["stroke_taper"] = {
        "start": 0.2,
        "end": 0.8,
    }
    composition.layers[1].source.params["text_animators"] = {
        "animators": [{
            "id": "reveal",
            "selector": {"unit": "character", "start": 0.0, "end": 1.0},
            "properties": {"opacity": 0.0, "tracking": 8.0},
        }],
    }

    report = preflight_interchange(composition, "svg", time_ms=500)

    assert report["ok"] is False
    reasons = {row["reason"] for row in report["bake_required"]}
    assert "Feature 'Offset Paths' is outside the editable SVG still subset." in reasons
    assert "Feature 'Variable-width/tapered strokes' is outside the editable SVG still subset." in reasons
    assert "Feature 'Text Animator stacks' is outside the editable SVG still subset." in reasons


def test_otio_exports_only_explicit_media_timing_references(tmp_path: Path) -> None:
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"media-reference")
    layer = MotionLayer(name="Clip", layer_type="video", source=SourceRef(kind="video", uri=str(media)),
                        in_ms=1000, out_ms=3000, source_in_ms=500)
    composition = MotionComposition(fps=25, duration_ms=4000, layers=[layer, MotionLayer(name="Generated")])
    output = tmp_path / "timing.otio"
    result = export_interchange(composition, "otio_timing", output)
    data = json.loads(output.read_text(encoding="utf-8"))
    track_children = data["tracks"]["children"][0]["children"]
    gap, clip = track_children
    assert result["preflight"]["scope"] == "limited"
    assert clip["media_reference"]["target_url"].startswith("file:")
    assert clip["source_range"]["duration"]["value"] == 50.0
    assert gap["source_range"]["duration"]["value"] == 25.0


def test_gltf_passthrough_copies_external_dependencies(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "mesh.bin").write_bytes(b"1234")
    source = source_dir / "scene.gltf"
    source.write_text(json.dumps({"asset": {"version": "2.0"}, "buffers": [{"uri": "mesh.bin", "byteLength": 4}]}), encoding="utf-8")
    layer = MotionLayer(name="3D", layer_type="ar_pbr", source=SourceRef(kind="ar_pbr", uri=str(source)), out_ms=1000)
    composition = MotionComposition(duration_ms=1000, layers=[layer])
    output = tmp_path / "delivery" / "scene.gltf"
    result = export_interchange(composition, "gltf_subscene", output)
    exported = json.loads(output.read_text(encoding="utf-8"))
    dependency = output.parent / exported["buffers"][0]["uri"]
    assert len(result["paths"]) == 2 and dependency.read_bytes() == b"1234"


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_interchange_actions_expose_scope_and_export(tmp_path: Path) -> None:
    composition = _shape_text_composition()
    registry = ActionRegistry(_Owner(composition))
    listed = registry.execute("motion.interchange.list", {})
    assert listed.ok and listed.result["count"] == 4
    output = tmp_path / "motion.svg"
    rendered = registry.execute("motion.interchange.export", {
        "composition_id": composition.id, "format_id": "svg", "output_path": str(output),
    })
    assert rendered.ok and output.is_file()
