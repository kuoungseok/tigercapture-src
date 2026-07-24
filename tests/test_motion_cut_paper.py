from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.cut_paper import build_cut_paper_rig, jagged_oval_path
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _image_layer(path: Path, *, name: str = "Paper") -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(path),
            params={"width": 200, "height": 120, "fit": "cover"},
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [100, 60]
    return layer


def test_jagged_cut_path_is_deterministic_and_closed() -> None:
    first = jagged_oval_path(
        center_x=100,
        center_y=60,
        radius_x=45,
        radius_y=35,
        seed=21,
    )
    second = jagged_oval_path(
        center_x=100,
        center_y=60,
        radius_x=45,
        radius_y=35,
        seed=21,
    )
    assert first.closed
    assert len(first.points) == 48
    assert first.to_dict() == second.to_dict()


def test_cut_paper_rig_reveals_layer_below_after_piece_releases(tmp_path: Path) -> None:
    _app()
    paper_path = tmp_path / "paper.png"
    Image.new("RGB", (200, 120), "#eee7d8").save(paper_path)
    paper = _image_layer(paper_path)
    subject = MotionLayer(
        name="Subject",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": 200,
                "height": 120,
                "fill": "#1565c0",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    subject.transform.position.default = [100, 60]
    composition = MotionComposition(
        width=200,
        height=120,
        duration_ms=1000,
        layers=[paper, subject],
    )
    rig = build_cut_paper_rig(
        composition,
        paper,
        center_x=100,
        center_y=60,
        radius_x=48,
        radius_y=38,
        start_ms=100,
        cut_duration_ms=300,
        release_duration_ms=300,
    )
    composition.layers.extend(rig.layers)
    renderer = MotionExportRenderer()
    before = renderer.render_rgba_array(composition, 0)[60, 100]
    after = renderer.render_rgba_array(composition, 800)[60, 100]
    assert int(before[0]) > int(before[2])
    assert int(after[2]) > int(after[0])
    assert rig.overlay.masks[0].inverted
    assert rig.piece.masks[0].kind == "path"
    assert rig.paper_fiber.source.params["trim"]["keyframes"]


def test_cut_paper_action_creates_five_editable_layers(tmp_path: Path) -> None:
    paper_path = tmp_path / "paper.png"
    Image.new("RGB", (200, 120), "#eee7d8").save(paper_path)
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {"name": "Cut Paper", "width": 200, "height": 120, "duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute(
        "motion.layer.add",
        {
            "composition_id": composition_id,
            "layer": _image_layer(paper_path).to_dict(),
        },
    )
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]
    result = registry.execute(
        "motion.cut_paper.create",
        {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "center_x": 100,
            "center_y": 60,
            "radius_x": 48,
            "radius_y": 38,
            "start_ms": 100,
            "cut_duration_ms": 300,
            "release_duration_ms": 300,
        },
    )
    assert result.ok
    assert len(result.result["layer_ids"]) == 5
    assert len(owner._motion_compositions[composition_id].layers) == 6
    assert "motion.cut_paper.create" in {
        row["id"] for row in registry.list_actions()
    }
