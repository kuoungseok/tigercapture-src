from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from PIL import Image, ImageDraw

from app.actions.registry import ActionRegistry
from app.motion_designer.ai_generation import generate_motion_ai_proposal
from app.motion_designer.ai_workspace import MotionAIReference
from app.motion_designer.image_decomposition import (
    IMAGE_DECOMPOSITION_SCHEMA,
    compile_decomposition_layers,
    decompose_image,
)
from app.motion_designer.schema import MotionComposition
from app.motion_designer.render_graph import build_render_graph


def _source(path: Path) -> Path:
    image = Image.new("RGB", (320, 180), (226, 232, 238))
    painter = ImageDraw.Draw(image)
    painter.ellipse((96, 30, 224, 170), fill=(230, 72, 58))
    painter.rectangle((28, 48, 72, 96), fill=(38, 116, 202))
    image.save(path)
    return path


def test_decomposition_writes_regenerable_layers_and_reuses_cache(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.png")
    result = decompose_image(
        source,
        width=320,
        height=180,
        cache_root=tmp_path / "cache",
        include_depth=False,
        force=True,
    )
    assert result.schema == IMAGE_DECOMPOSITION_SCHEMA
    assert result.elements
    assert Path(result.background_path).is_file()
    assert all(Path(item.rgba_path).is_file() for item in result.elements if item.rgba_path)
    assert all(Path(item.mask_path).is_file() for item in result.elements if item.mask_path)
    assert result.diagnostics["component_count"] >= 1
    assert result.diagnostics["validation"]["ok"] is True
    assert result.diagnostics["validation"]["metrics"]["available"] is True

    cached = decompose_image(
        source,
        width=320,
        height=180,
        cache_root=tmp_path / "cache",
        include_depth=False,
    )
    assert cached.source_hash == result.source_hash
    assert cached.diagnostics["cache_hit"] is True


def test_decomposition_compiles_staggered_parallax_layers(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.png")
    result = decompose_image(
        source,
        width=320,
        height=180,
        cache_root=tmp_path / "cache",
        include_depth=False,
    )
    composition = MotionComposition(width=320, height=180, duration_ms=2400)
    layers = compile_decomposition_layers(
        composition,
        result,
        reference_id="ref_image",
        name="Product",
        in_ms=0,
        out_ms=2400,
        center=(160.0, 90.0),
        size=(320, 180),
        beat_id="beat_1",
    )
    assert layers[0].metadata["image_decomposition"]["role"] == "background"
    assert layers[0].metadata["image_motion_validation"]["ok"] is True
    preflight = layers[0].metadata["restoration_preflight"]
    assert preflight["schema"] == "tigerstudio.motion.restoration_preflight.v1"
    assert preflight["status"] != "blocked"
    contact_layers = [
        layer for layer in layers
        if layer.metadata.get("contact_composite_role") == "shadow"
    ]
    assert len(contact_layers) == 1
    assert Path(contact_layers[0].source.uri).is_file()
    subjects = [
        layer for layer in layers
        if layer.metadata["image_decomposition"]["role"] != "background"
        and layer.layer_type == "image"
    ]
    assert subjects
    assert all(len(layer.transform.position.keyframes) == 2 for layer in subjects)
    assert all(len(layer.transform.scale.keyframes) == 2 for layer in subjects)
    assert all(layer.behaviors[0].params["hold_before"] for layer in subjects)
    delays = [layer.behaviors[0].start_ms for layer in subjects]
    assert delays == sorted(delays)

    compiled = MotionComposition(width=320, height=180, duration_ms=2400)
    compiled.layers = layers
    preview_graph = build_render_graph(compiled, 600, render_quality="preview")
    export_graph = build_render_graph(compiled, 600, render_quality="export")
    preview_assets = {
        node.layer_id: node.source_layer.source.uri
        for node in preview_graph.nodes
        if node.source_layer is not None
    }
    export_assets = {
        node.layer_id: node.source_layer.source.uri
        for node in export_graph.nodes
        if node.source_layer is not None
    }
    assert preview_assets == export_assets


def test_sparse_primary_mask_is_motion_locked_to_preserve_rigid_objects(tmp_path: Path) -> None:
    source = Image.new("RGB", (320, 180), (12, 14, 18))
    painter = ImageDraw.Draw(source)
    painter.rectangle((102, 35, 218, 165), outline=(238, 188, 92), width=8)
    painter.rectangle((110, 142, 210, 157), fill=(138, 64, 20))
    source_path = tmp_path / "hollow_glass.png"
    source.save(source_path)

    result = decompose_image(
        source_path,
        width=320,
        height=180,
        cache_root=tmp_path / "cache",
        include_depth=False,
        force=True,
    )
    primary = next(item for item in result.elements if item.role == "primary_subject")
    assert primary.metadata["motion_lock_to_background"] is True
    assert result.diagnostics["motion_locked_component_count"] == 1

    layers = compile_decomposition_layers(
        MotionComposition(width=320, height=180, duration_ms=2400),
        result,
        reference_id="ref_glass",
        name="Glass",
        in_ms=0,
        out_ms=2400,
        center=(160.0, 90.0),
        size=(320, 180),
    )
    background = layers[0]
    subject = next(
        layer for layer in layers
        if layer.metadata["image_decomposition"]["role"] == "primary_subject"
    )
    assert [
        (item.time_ms, item.value) for item in subject.transform.position.keyframes
    ] == [
        (item.time_ms, item.value) for item in background.transform.position.keyframes
    ]
    assert [
        (item.time_ms, item.value) for item in subject.transform.scale.keyframes
    ] == [
        (item.time_ms, item.value) for item in background.transform.scale.keyframes
    ]
    assert subject.behaviors == []


def test_motion_ai_candidate_can_explode_or_preserve_the_source_image(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.png")
    composition = MotionComposition(width=320, height=180, duration_ms=2400)
    reference = MotionAIReference(
        id="reference_product",
        kind="image",
        name="Product",
        uri=str(source),
    )
    exploded = generate_motion_ai_proposal(
        composition,
        "active product reveal",
        [reference],
        provider_id="rule_based",
        decompose_images=True,
    )
    assert exploded.analysis["decomposed_reference_count"] == 1
    assert any(
        layer.metadata.get("image_decomposition", {}).get("role") == "primary_subject"
        for layer in exploded.layers
    )

    preserved = generate_motion_ai_proposal(
        composition,
        "active product reveal",
        [reference],
        provider_id="rule_based",
        decompose_images=False,
    )
    assert preserved.analysis["decomposed_reference_count"] == 0
    image_layers = [layer for layer in preserved.layers if layer.layer_type == "image"]
    assert image_layers
    assert all("image_decomposition" not in layer.metadata for layer in image_layers)


def test_motion_image_decomposition_action_is_registered_and_callable(tmp_path: Path) -> None:
    source = _source(tmp_path / "source.png")
    owner = SimpleNamespace()
    registry = ActionRegistry(owner)
    action_ids = {item["id"] for item in registry.list_actions()}
    expected = {
        "motion.ai.reference.decompose",
        "motion.ai.layer.analyze",
        "motion.ai.layer.segment",
        "motion.ai.layer.mask.refine",
        "motion.ai.layer.mask.replace",
        "motion.ai.layer.merge",
        "motion.ai.layer.split",
        "motion.ai.layer.lock",
        "motion.ai.layer.group",
        "motion.ai.layer.pivot",
        "motion.ai.layer.order",
        "motion.ai.background.inpaint",
        "motion.ai.background.replace",
        "motion.ai.text.reconstruct",
        "motion.ai.choreography.plan",
        "motion.ai.choreography.candidates",
        "motion.ai.choreography.candidate.apply",
        "motion.ai.choreography.apply",
        "motion.ai.candidate.preview",
        "motion.ai.cutout.quality.validate",
        "motion.ai.layer.readiness.inspect",
        "motion.ai.integrity.validate",
    }
    assert expected <= action_ids
    execution = registry.execute("motion.ai.reference.decompose", {
        "source_path": str(source),
        "width": 320,
        "height": 180,
        "max_elements": 3,
        "include_depth": False,
    })
    assert execution.ok
    assert execution.result["schema"] == IMAGE_DECOMPOSITION_SCHEMA
    assert execution.result["elements"]
    clean_plate = tmp_path / "clean_plate.png"
    Image.new("RGB", (320, 180), (20, 70, 110)).save(clean_plate)
    replacement = registry.execute("motion.ai.background.replace", {
        "decomposition": execution.result,
        "background_path": str(clean_plate),
        "provider": "test_reviewed_plate",
    })
    assert replacement.ok
    assert replacement.result["diagnostics"]["inpaint"]["provider"] == "test_reviewed_plate"
    assert Path(replacement.result["background_path"]).is_file()
    validation = registry.execute("motion.ai.integrity.validate", {
        "decomposition": execution.result,
    })
    assert validation.ok
    assert validation.result["ok"] is True
    quality = registry.execute("motion.ai.cutout.quality.validate", {
        "decomposition": execution.result,
    })
    assert quality.ok
    assert quality.result["schema"] == "tigerstudio.motion.cutout_quality.v1"
    assert quality.result["accepted"] is True
    readiness = registry.execute("motion.ai.layer.readiness.inspect", {
        "decomposition": execution.result,
    })
    assert readiness.ok
    assert readiness.result["schema"] == "tigerstudio.motion.layer_readiness.v1"
    assert readiness.result["status"] in {"ready", "review"}
    choreography = registry.execute("motion.ai.choreography.plan", {
        "decomposition": execution.result,
        "duration_ms": 2400,
        "variant": "dynamic",
        "prompt": "active product reveal",
    })
    assert choreography.ok
    assert choreography.result["variant"] == "dynamic"
    assert choreography.result["layers"]
    visual_id = next(
        item["id"]
        for item in execution.result["elements"]
        if item["role"] != "text"
    )
    locked = registry.execute("motion.ai.layer.lock", {
        "decomposition": execution.result,
        "element_ids": [visual_id],
        "locked": True,
    })
    assert locked.ok
    locked_element = next(
        item for item in locked.result["elements"] if item["id"] == visual_id
    )
    assert locked_element["metadata"]["motion_lock_to_background"] is True
    composition = MotionComposition(width=320, height=180, duration_ms=2400)
    owner._motion_compositions = {composition.id: composition}
    applied = registry.execute("motion.ai.choreography.apply", {
        "composition_id": composition.id,
        "decomposition": locked.result,
        "in_ms": 0,
        "out_ms": 2400,
        "variant": "dynamic",
        "base_revision": composition.revision,
    })
    assert applied.ok
    assert applied.result["added_layers"] >= 2
    assert owner._motion_compositions[composition.id].revision == composition.revision + 1

    candidates = registry.execute("motion.ai.choreography.candidates", {
        "decomposition": execution.result,
        "duration_ms": 2400,
        "prompt": "product orbit launch",
    })
    assert candidates.ok
    recommended = candidates.result["recommended_candidate_id"]
    selected = registry.execute("motion.ai.choreography.candidate.apply", {
        "composition_id": composition.id,
        "decomposition": execution.result,
        "director_plan": candidates.result,
        "candidate_id": recommended,
        "approved": True,
        "in_ms": 0,
        "out_ms": 2400,
        "base_revision": owner._motion_compositions[composition.id].revision,
    })
    assert selected.ok
    assert selected.result["director_selection"]["candidate_id"] == recommended
