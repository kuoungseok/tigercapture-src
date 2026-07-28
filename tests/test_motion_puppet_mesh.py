from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.puppet_gpu_renderer import MotionPuppetGpuRenderer
from app.motion_designer.render_graph import build_render_graph
from app.motion_designer.puppet_mesh import (
    PUPPET_SCHEMA,
    add_puppet_pin,
    bind_puppet_pin_to_rig,
    configure_puppet_tear_repair,
    create_alpha_adaptive_puppet_mesh,
    create_grid_puppet_mesh,
    evaluate_puppet_depths,
    evaluate_puppet_vertices,
    layer_puppet_mesh,
    puppet_mesh_diagnostics,
    repair_puppet_vertices,
    stabilize_puppet_vertices,
)
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.schema import Keyframe, SourceRef
from app.motion_designer.rigging import create_rig, update_bone
from app.motion_designer.validation import validate_composition


def _composition() -> tuple[MotionComposition, MotionLayer]:
    layer = MotionLayer(
        id="image",
        name="Puppet",
        layer_type="image",
        out_ms=2000,
    )
    return MotionComposition(
        id="puppet",
        width=640,
        height=360,
        duration_ms=2000,
        layers=[layer],
    ), layer


def test_grid_mesh_roundtrip_and_topology() -> None:
    composition, layer = _composition()
    mesh = create_grid_puppet_mesh(layer, columns=4, rows=3)
    assert len(mesh.vertices) == 20
    assert len(mesh.triangles) == 24
    assert mesh.to_dict()["schema"] == PUPPET_SCHEMA
    assert validate_composition(composition).ok
    restored = MotionComposition.from_dict(composition.to_dict())
    restored_mesh = layer_puppet_mesh(restored.layers[0])
    assert restored_mesh is not None
    assert len(restored_mesh.vertices) == 20
    assert puppet_mesh_diagnostics(restored_mesh)["valid"] is True


def test_alpha_adaptive_mesh_discards_transparent_background(tmp_path) -> None:
    source_path = tmp_path / "alpha_subject.png"
    image = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((24, 12, 72, 88), fill=(255, 255, 255, 255))
    image.save(source_path)
    layer = MotionLayer(
        id="alpha",
        name="Alpha Subject",
        layer_type="image",
        source=SourceRef(kind="image", uri=str(source_path)),
        out_ms=1000,
    )
    mesh = create_alpha_adaptive_puppet_mesh(
        layer,
        columns=12,
        rows=12,
    )
    assert 0 < len(mesh.triangles) < (12 * 2) * (12 * 2) * 2
    assert mesh.metadata["generator"] == "alpha_boundary_delaunay_v2"
    assert mesh.metadata["boundary_refined_cell_count"] > 0
    assert mesh.metadata["refined_vertex_count"] > mesh.metadata["base_vertex_count"]
    assert validate_composition(MotionComposition(
        id="alpha_mesh",
        duration_ms=1000,
        layers=[layer],
    )).ok


def test_position_bend_and_starch_pins_deform_vertices_deterministically() -> None:
    composition, layer = _composition()
    mesh = create_grid_puppet_mesh(layer, columns=6, rows=6)
    position = add_puppet_pin(
        layer,
        kind="position",
        position=[0.5, 0.5],
        radius=0.4,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    position = next(pin for pin in mesh.pins if pin.id == position.id)
    position.position.default = [0.65, 0.45]
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    bend = add_puppet_pin(
        layer,
        kind="bend",
        position=[0.25, 0.5],
        radius=0.3,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    bend = next(pin for pin in mesh.pins if pin.id == bend.id)
    bend.rotation.default = 18.0
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    add_puppet_pin(
        layer,
        kind="starch",
        position=[0.85, 0.5],
        radius=0.25,
        strength=1.5,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    # Persist edits made to the parsed pin objects.
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    points_a = evaluate_puppet_vertices(mesh, 0)
    points_b = evaluate_puppet_vertices(mesh, 0)
    assert points_a == points_b
    assert points_a != [vertex.uv for vertex in mesh.vertices]
    assert validate_composition(composition).ok


def test_validation_rejects_bad_triangle_reference() -> None:
    composition, layer = _composition()
    mesh = create_grid_puppet_mesh(layer, columns=2, rows=2)
    mesh.triangles.append((0, 1, 999))
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    codes = {issue.code for issue in validate_composition(composition).issues}
    assert "invalid_puppet_triangles" in codes


def test_preview_export_graph_warps_real_image_pixels(tmp_path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    source_path = tmp_path / "subject.png"
    image = Image.new("RGBA", (160, 120), (0, 0, 0, 0))
    ImageDraw.Draw(image).ellipse((50, 25, 110, 95), fill=(235, 70, 90, 255))
    image.save(source_path)
    layer = MotionLayer(
        id="subject",
        name="Subject",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(source_path),
            params={"width": 160, "height": 120, "fit": "stretch"},
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [80, 60]
    composition = MotionComposition(
        id="puppet_render",
        width=160,
        height=120,
        duration_ms=1000,
        layers=[layer],
    )
    create_grid_puppet_mesh(layer, columns=8, rows=6)
    pin = add_puppet_pin(
        layer,
        kind="position",
        position=[0.5, 0.5],
        radius=0.35,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    pin = next(row for row in mesh.pins if row.id == pin.id)
    pin.position.keyframes = [
        Keyframe(time_ms=0, value=[0.5, 0.5]),
        Keyframe(time_ms=1000, value=[0.72, 0.42]),
    ]
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    renderer = MotionExportRenderer()
    before = renderer.render_rgba_array(composition, 0)
    after = renderer.render_rgba_array(composition, 999)

    def centroid(frame):
        visible = frame[:, :, 3] > 32
        ys, xs = np.nonzero(visible)
        return float(xs.mean()), float(ys.mean())

    before_center = centroid(before)
    after_center = centroid(after)
    assert after_center[0] > before_center[0] + 4
    assert after_center[1] < before_center[1] - 2


def test_gpu_preview_packet_contains_animated_textured_mesh(tmp_path) -> None:
    source_path = tmp_path / "gpu_subject.png"
    image = Image.new("RGBA", (96, 64), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((12, 8, 84, 58), fill=(40, 190, 230, 255))
    image.save(source_path)
    layer = MotionLayer(
        id="gpu_subject",
        name="GPU Subject",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(source_path),
            params={"width": 96, "height": 64},
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [48, 32]
    composition = MotionComposition(
        id="gpu_puppet",
        width=96,
        height=64,
        duration_ms=1000,
        layers=[layer],
    )
    create_grid_puppet_mesh(layer, columns=4, rows=3)
    pin = add_puppet_pin(
        layer,
        kind="position",
        position=[0.5, 0.5],
        radius=0.45,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    animated = next(row for row in mesh.pins if row.id == pin.id)
    animated.position.default = [0.62, 0.42]
    layer.metadata["puppet_mesh"] = mesh.to_dict()

    graph = build_render_graph(composition, 500, include_vector_gpu=True)
    assert graph.diagnostics["puppet_gpu_packet_count"] == 1
    packet = graph.nodes[0].puppet_gpu_packet
    assert packet is not None
    assert packet.triangle_count == len(mesh.triangles)
    assert len(packet.vertices) == packet.triangle_count * 3 * 4
    assert packet.image.width() == 96
    assert packet.image.height() == 64
    assert graph.nodes[0].image is None
    assert MotionPuppetGpuRenderer.can_draw(graph) == (True, "")


def test_real_spine_character_part_alpha_mesh_renders_three_deformed_frames() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    source_path = (
        Path(__file__).parents[1]
        / "resources"
        / "spine_samples"
        / "celestial-circus"
        / "images"
        / "wing-front.png"
    )
    assert source_path.is_file()
    layer = MotionLayer(
        id="real_wing",
        name="Celestial Circus Wing",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(source_path),
            params={"width": 380, "height": 310, "fit": "stretch"},
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [190, 155]
    composition = MotionComposition(
        id="real_puppet_qa",
        width=380,
        height=310,
        duration_ms=1000,
        layers=[layer],
    )
    mesh = create_alpha_adaptive_puppet_mesh(
        layer,
        columns=16,
        rows=14,
    )
    assert 0 < len(mesh.triangles) < (16 * 2) * (14 * 2) * 2
    assert mesh.metadata["boundary_refined_cell_count"] > 0
    pin = add_puppet_pin(
        layer,
        kind="bend",
        position=[0.28, 0.55],
        radius=0.45,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    pin = next(row for row in mesh.pins if row.id == pin.id)
    pin.rotation.keyframes = [
        Keyframe(time_ms=0, value=-18.0),
        Keyframe(time_ms=500, value=22.0),
        Keyframe(time_ms=999, value=-8.0),
    ]
    layer.metadata["puppet_mesh"] = mesh.to_dict()
    renderer = MotionExportRenderer()
    frames = [
        renderer.render_rgba_array(composition, time_ms)
        for time_ms in (0, 500, 999)
    ]
    alpha_sums = [int(frame[:, :, 3].sum()) for frame in frames]
    assert min(alpha_sums) > 1_000_000
    assert not np.array_equal(frames[0], frames[1])
    assert not np.array_equal(frames[1], frames[2])
    assert puppet_mesh_diagnostics(mesh, 500)["degenerate_triangle_count"] == 0


def test_twenty_thousand_triangle_hundred_pin_stress_contract() -> None:
    _composition_value, layer = _composition()
    mesh = create_grid_puppet_mesh(layer, columns=100, rows=100)
    assert len(mesh.triangles) == 20_000
    for index in range(100):
        add_puppet_pin(
            layer,
            kind=("position", "bend", "starch", "overlap")[index % 4],
            position=[(index % 10 + 0.5) / 10.0, (index // 10 + 0.5) / 10.0],
            radius=0.08,
        )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    assert len(mesh.pins) == 100
    assert len(evaluate_puppet_vertices(mesh, 500)) == 10_201
    assert puppet_mesh_diagnostics(mesh, 500)["triangle_count"] == 20_000


def test_puppet_actions_create_edit_inspect_and_delete() -> None:
    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"name": "Puppet Action", "duration_ms": 2000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute(
        "motion.layer.add",
        {
            "composition_id": composition_id,
            "layer": {
                "id": "subject",
                "name": "Subject",
                "layer_type": "image",
                "out_ms": 2000,
            },
        },
    )
    assert added.ok
    assert registry.execute(
        "motion.puppet.mesh.create",
        {
            "composition_id": composition_id,
            "layer_id": "subject",
            "columns": 5,
            "rows": 4,
        },
    ).ok
    repair_config = registry.execute(
        "motion.puppet.repair.configure",
        {
            "composition_id": composition_id,
            "layer_id": "subject",
            "enabled": True,
            "max_edge_stretch": 4.5,
        },
    )
    assert repair_config.ok
    assert repair_config.result["payload"]["tear_repair"] == {
        "enabled": True,
        "mode": "local",
        "max_edge_stretch": 4.5,
    }
    pin = registry.execute(
        "motion.puppet.pin.add",
        {
            "composition_id": composition_id,
            "layer_id": "subject",
            "kind": "bend",
            "position": [0.5, 0.5],
        },
    )
    assert pin.ok
    pin_id = pin.result["payload"]["pin"]["id"]
    assert registry.execute(
        "motion.puppet.pin.update",
        {
            "composition_id": composition_id,
            "layer_id": "subject",
            "pin_id": pin_id,
            "changes": {"rotation": 20.0, "radius": 0.5},
        },
    ).ok
    inspected = registry.execute(
        "motion.puppet.inspect",
        {"composition_id": composition_id, "layer_id": "subject"},
    )
    assert inspected.ok
    assert inspected.result["diagnostics"]["triangle_count"] == 40
    assert registry.execute(
        "motion.puppet.pin.delete",
        {
            "composition_id": composition_id,
            "layer_id": "subject",
            "pin_id": pin_id,
        },
        confirm_destructive=True,
    ).ok


def test_puppet_pin_can_use_rig_bone_as_bend_driver() -> None:
    composition, layer = _composition()
    create_grid_puppet_mesh(layer, columns=4, rows=4)
    pin = add_puppet_pin(
        layer,
        kind="bend",
        position=[0.5, 0.5],
        radius=0.5,
    )
    rig = create_rig(
        composition,
        bones=[
            {
                "id": "driver",
                "name": "Driver",
                "role": "root",
                "rest_position": [320, 180],
            },
        ],
    )
    bind_puppet_pin_to_rig(
        layer,
        pin.id,
        rig_id=rig.id,
        bone_id="driver",
    )
    update_bone(composition, rig.id, "driver", {"rotation": 30.0})
    restored = layer_puppet_mesh(layer)
    assert restored is not None
    driver = restored.pins[0].metadata["rig_driver"]
    assert driver == {"rig_id": rig.id, "bone_id": "driver"}
    assert validate_composition(composition).ok


def test_overlap_depth_and_flip_stabilizer_are_deterministic() -> None:
    _composition_value, layer = _composition()
    mesh = create_grid_puppet_mesh(layer, columns=2, rows=2)
    overlap = add_puppet_pin(
        layer,
        kind="overlap",
        position=[0.75, 0.5],
        radius=0.5,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    overlap = next(row for row in mesh.pins if row.id == overlap.id)
    overlap.depth = 2.0
    depths = evaluate_puppet_depths(mesh)
    assert depths[-1] > depths[0]
    folded = [vertex.uv for vertex in mesh.vertices]
    folded[-1] = (-1.0, -1.0)
    repaired, amount = stabilize_puppet_vertices(mesh, folded)
    assert 0.0 <= amount < 1.0
    assert repaired != folded
    local, report = repair_puppet_vertices(mesh, folded, max_edge_stretch=4.0)
    assert report["mode"] in {"local", "global_fallback"}
    assert report["repaired_vertex_count"] < len(mesh.vertices)
    assert report["render_safe"] is True
    assert local != folded


def test_explicit_tear_repair_clamps_excessive_local_edge_stretch() -> None:
    _composition_value, layer = _composition()
    mesh = create_grid_puppet_mesh(layer, columns=4, rows=4)
    configure_puppet_tear_repair(
        layer,
        enabled=True,
        max_edge_stretch=2.0,
    )
    mesh = layer_puppet_mesh(layer)
    assert mesh is not None
    torn = [vertex.uv for vertex in mesh.vertices]
    torn[12] = (4.0, 0.5)
    repaired, report = repair_puppet_vertices(
        mesh,
        torn,
        max_edge_stretch=2.0,
    )
    assert report["torn_triangle_count"] > 0
    assert report["render_safe"] is True
    assert repaired[0] == torn[0]
    assert repaired[12] != torn[12]
