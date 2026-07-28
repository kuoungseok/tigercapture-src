from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.adapters.generator import render_generator
from app.motion_designer.advanced_motion import evaluate_replicator
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.generators import GENERATOR_KINDS, create_generator_layer
from app.motion_designer.project_io import load_motion_project, save_motion_project
from app.motion_designer.render_graph import build_render_graph
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDesignerWindow
from app.motion_designer.validation import validate_composition


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def test_all_procedural_generators_render_and_validate() -> None:
    _app()
    signatures: set[tuple[int, int, int]] = set()
    for kind in GENERATOR_KINDS:
        layer = create_generator_layer(kind, width=160, height=90, duration_ms=1200)
        image = render_generator(layer)
        assert image.width() == 160
        assert image.height() == 90
        rgba = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(), image.bytesPerLine(),
        )[:, : image.width() * 4]
        assert rgba[:, 3::4].max() == 255
        signatures.add((int(rgba[:, 0::4].mean()), int(rgba[:, 1::4].mean()), int(rgba[:, 2::4].mean())))
        assert validate_composition(
            MotionComposition(width=160, height=90, duration_ms=1200, layers=[layer])
        ).ok
    assert len(signatures) >= 4


def test_replicator_line_grid_and_radial_layouts() -> None:
    line = evaluate_replicator(
        {"enabled": True, "arrangement": "line", "count": 3, "offset": [20, 10]},
        0,
    )
    assert [(row["x"], row["y"]) for row in line] == [(0, 0), (20, 10), (40, 20)]

    grid = evaluate_replicator(
        {"enabled": True, "arrangement": "grid", "count": 5, "columns": 2, "offset": [20, 10]},
        0,
    )
    assert [(row["x"], row["y"]) for row in grid] == [
        (0, 0), (20, 0), (0, 10), (20, 10), (0, 20),
    ]

    radial = evaluate_replicator(
        {"enabled": True, "arrangement": "radial", "count": 4, "offset": [40, 0]},
        0,
    )
    assert radial[0]["x"] == pytest.approx(40)
    assert radial[1]["y"] == pytest.approx(40)
    assert radial[2]["x"] == pytest.approx(-40)


def test_radial_replicator_keeps_instance_offsets_in_composition_space() -> None:
    _app()
    layer = MotionLayer(
        name="Tile",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 20, "height": 20, "fill": "#ffffff", "stroke_width": 0,
        }),
        out_ms=1000,
    )
    layer.transform.position.default = [100.0, 100.0]
    layer.metadata["replicator"] = {
        "enabled": True,
        "arrangement": "radial",
        "count": 4,
        "offset": [50.0, 0.0],
        "rotation": 0.0,
        "scale": [1.0, 1.0],
        "opacity_start": 1.0,
        "opacity_end": 1.0,
    }
    composition = MotionComposition(
        width=200, height=200, duration_ms=1000, layers=[layer],
    )
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    assert all(rgba[y, x, 3] > 200 for x, y in (
        (150, 100), (100, 150), (50, 100), (100, 50),
    ))


def test_generator_and_replicator_round_trip_and_render_graph(tmp_path) -> None:
    _app()
    layer = create_generator_layer("checkerboard", width=320, height=180, duration_ms=2000)
    layer.metadata["replicator"] = {
        "enabled": True,
        "arrangement": "grid",
        "count": 6,
        "columns": 3,
        "offset": [40.0, 30.0],
        "rotation": 0.0,
        "scale": [1.0, 1.0],
        "opacity_start": 1.0,
        "opacity_end": 0.5,
        "jitter": [0.0, 0.0],
        "seed": 0,
    }
    composition = MotionComposition(
        width=320, height=180, duration_ms=2000, layers=[layer],
    )
    target = save_motion_project(composition, tmp_path / "generator.tgmotion")
    loaded = load_motion_project(target)
    assert loaded.layers[0].source.params["kind"] == "checkerboard"
    assert loaded.layers[0].metadata["replicator"]["arrangement"] == "grid"
    graph = build_render_graph(loaded, 0)
    assert graph.diagnostics["replicated_node_count"] == 1
    assert len(graph.nodes[0].replicator_instances) == 6


class _Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_generator_and_replicator_actions_are_automation_ready() -> None:
    owner = _Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "Procedural", "width": 320, "height": 180, "duration_ms": 2000,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute("motion.generator.create", {
        "composition_id": composition_id,
        "kind": "rays",
    })
    assert added.ok
    layer_id = added.result["layer"]["id"]
    assert registry.execute("motion.generator.update", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "changes": {"scale": 48.0, "angle": 15.0},
    }).ok
    repeated = registry.execute("motion.replicator.set", {
        "composition_id": composition_id,
        "layer_id": layer_id,
        "arrangement": "radial",
        "count": 8,
        "columns": 4,
        "offset": [100.0, 0.0],
    })
    assert repeated.ok
    layer = owner._motion_compositions[composition_id].layers[0]
    assert layer.source.params["scale"] == 48.0
    assert layer.metadata["replicator"]["arrangement"] == "radial"


def test_generator_and_replicator_have_independent_inspectors() -> None:
    _app()
    window = MotionDesignerWindow(
        MotionComposition(width=640, height=360, duration_ms=2000)
    )
    window._add_layer("generator:grid")
    assert window.inspector_tabs.currentWidget() is window.generator
    layer = window.controller.composition.layers[0]
    window._create_replicator()
    assert window.inspector_tabs.currentWidget() is window.replicator
    assert layer.id == window._selected_layer_id
    assert window.controller.composition.layers[0].metadata["replicator"]["enabled"]
    window.close()
