from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.collage import (
    COLLAGE_CONTRACT,
    collage_boards,
    create_collage_board,
    preflight_collage,
    reorder_collage_item,
    replace_collage_item_source,
    set_collage_attachment,
    set_collage_edge,
    set_collage_painter_link,
    set_collage_scan_cleanup,
)
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.unreal_umg_document import motion_composition_to_umg_document


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _shape(name: str, color: str, x: float) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": 100,
                "height": 80,
                "fill": color,
                "stroke_width": 0,
            },
        ),
        in_ms=125,
        out_ms=2400,
        parent_id="host",
    )
    layer.transform.position.default = [x, 70.0]
    layer.transform.anchor.default = [0.35, 0.65]
    return layer


def _composition() -> MotionComposition:
    return MotionComposition(
        width=320,
        height=180,
        duration_ms=3000,
        layers=[
            _shape("Red", "#e74c3c", 70.0),
            _shape("Blue", "#2878d0", 160.0),
            _shape("Gold", "#e3ad35", 250.0),
        ],
    )


def test_collage_contract_round_trip_and_layout_are_deterministic() -> None:
    composition = _composition()
    board = create_collage_board(
        composition,
        [layer.id for layer in composition.layers],
        name="Editorial",
        layout="scatter",
        seed=23,
    )
    assert board["schema"] == COLLAGE_CONTRACT
    assert len(board["items"]) == 3
    assert len({item["id"] for item in board["items"]}) == 3
    positions = [list(layer.transform.position.default) for layer in composition.layers]

    restored = MotionComposition.from_dict(composition.to_dict())
    assert collage_boards(restored) == collage_boards(composition)
    assert [list(layer.transform.position.default) for layer in restored.layers] == positions
    assert preflight_collage(restored, board["id"])["ok"]


def test_collage_project_file_round_trip_preserves_ids(tmp_path: Path) -> None:
    from app.motion_designer.project_io import (
        load_motion_project,
        save_motion_project,
    )

    composition = _composition()
    for layer in composition.layers:
        layer.parent_id = ""
    board = create_collage_board(
        composition,
        [layer.id for layer in composition.layers[:2]],
        layout="education",
        seed=101,
    )
    set_collage_painter_link(
        composition,
        board["id"],
        board["items"][0]["id"],
        document_id="paint-doc",
        object_id="paint-object",
        revision=3,
    )
    path = save_motion_project(composition, tmp_path / "collage.tgmotion")
    restored = load_motion_project(path)
    restored_board = collage_boards(restored)[0]
    assert restored.id == composition.id
    assert restored_board["id"] == board["id"]
    assert [row["id"] for row in restored_board["items"]] == [
        row["id"] for row in board["items"]
    ]
    assert [row["layer_id"] for row in restored_board["items"]] == [
        row["layer_id"] for row in board["items"]
    ]
    assert preflight_collage(restored, board["id"])["ok"]


def test_torn_edge_and_tape_attachment_are_editable_and_rendered() -> None:
    _app()
    composition = _composition()
    source = composition.layers[0]
    source.parent_id = ""
    board = create_collage_board(composition, [source.id])
    item = board["items"][0]
    edge = set_collage_edge(
        composition,
        board["id"],
        item["id"],
        mode="torn",
        roughness=0.9,
        seed=41,
    )
    attachment = set_collage_attachment(
        composition,
        board["id"],
        item["id"],
        kind="tape",
        strength=0.55,
        angle=-7.0,
    )
    assert edge["mode"] == "torn"
    assert source.masks[0].metadata["collage_edge_mask"] is True
    assert attachment["kind"] == "tape"
    assert any(
        layer.metadata.get("collage_attachment_kind") == "tape"
        for layer in composition.layers
    )

    image = MotionExportRenderer().render_rgba_array(
        composition,
        500,
    )
    visible = int((image[..., 3] > 0).sum())
    assert 0 < visible < composition.width * composition.height


def test_source_replace_preserves_layer_transform_parent_and_timing() -> None:
    composition = _composition()
    layer = composition.layers[0]
    board = create_collage_board(composition, [layer.id])
    item = board["items"][0]
    before_transform = layer.transform.to_dict()
    result = replace_collage_item_source(
        composition,
        board["id"],
        item["id"],
        {
            "kind": "image",
            "uri": "replacement.png",
            "params": {"width": 640, "height": 360, "fit": "cover"},
            "layer_type": "image",
        },
    )
    assert layer.id == result["preserved"]["layer_id"]
    assert layer.parent_id == "host"
    assert layer.in_ms == 125 and layer.out_ms == 2400
    assert layer.transform.to_dict() == before_transform
    assert board["items"][0]["id"] == item["id"]
    assert board["items"][0]["layer_id"] == layer.id


def test_z_reorder_moves_attachment_units_with_their_source() -> None:
    composition = _composition()
    for layer in composition.layers:
        layer.parent_id = ""
    board = create_collage_board(
        composition,
        [composition.layers[0].id, composition.layers[1].id],
    )
    first, second = board["items"]
    set_collage_attachment(
        composition,
        board["id"],
        first["id"],
        kind="glue",
    )
    set_collage_attachment(
        composition,
        board["id"],
        second["id"],
        kind="tape",
    )
    reorder_collage_item(
        composition,
        board["id"],
        first["id"],
        1,
    )
    source_order = [
        layer.id
        for layer in composition.layers
        if layer.id in {first["layer_id"], second["layer_id"]}
    ]
    assert source_order == [second["layer_id"], first["layer_id"]]
    for layer in composition.layers:
        if layer.metadata.get("collage_attachment"):
            assert layer.parent_id in {first["layer_id"], second["layer_id"]}


def test_painter_refresh_contract_keeps_motion_layer_id() -> None:
    composition = _composition()
    board = create_collage_board(composition, [composition.layers[0].id])
    item = board["items"][0]
    link = set_collage_painter_link(
        composition,
        board["id"],
        item["id"],
        document_id="paint-doc-1",
        object_id="paint-object-7",
        revision=4,
    )
    assert link["motion_layer_id"] == composition.layers[0].id
    assert preflight_collage(composition, board["id"])["ok"]


def test_scan_cleanup_neutralizes_paper_and_preserves_dark_ink() -> None:
    _app()
    composition = _composition()
    layer = composition.layers[0]
    layer.parent_id = ""
    layer.source.params["fill"] = "#e2cfa8"
    board = create_collage_board(composition, [layer.id])
    item = board["items"][0]
    settings = set_collage_scan_cleanup(
        composition,
        board["id"],
        item["id"],
        white_balance=1.0,
        paper_remove=0.65,
        ink_preserve=1.0,
        threshold=0.75,
    )
    assert settings["paper_remove"] == 0.65
    assert layer.effects[-1].kind == "scan_cleanup"
    rendered = MotionExportRenderer().render_rgba_array(composition, 500)
    visible = rendered[..., 3] > 0
    assert visible.any()
    pixels = rendered[..., :3][visible]
    assert float(pixels[:, 0].mean()) >= float(pixels[:, 2].mean())


class _Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def test_collage_actions_create_style_replace_and_refresh_without_id_loss() -> None:
    owner = _Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {
            "name": "Collage",
            "width": 320,
            "height": 180,
            "duration_ms": 3000,
        },
    )
    composition_id = created.result["payload"]["composition"]["id"]
    action_layer = _shape("Card", "#ffffff", 100)
    action_layer.parent_id = ""
    added = registry.execute(
        "motion.layer.add",
        {
            "composition_id": composition_id,
            "layer": action_layer.to_dict(),
        },
    )
    assert added.ok
    layer_id = owner._motion_compositions[composition_id].layers[0].id
    result = registry.execute(
        "motion.collage.create",
        {
            "composition_id": composition_id,
            "layer_ids": [layer_id],
            "layout": "editorial",
            "seed": 5,
        },
    )
    assert result.ok
    board = result.result["board"]
    item = board["items"][0]
    assert registry.execute(
        "motion.collage.edge.set",
        {
            "composition_id": composition_id,
            "board_id": board["id"],
            "item_id": item["id"],
            "mode": "fiber",
            "roughness": 0.7,
        },
    ).ok
    assert registry.execute(
        "motion.collage.paint.send",
        {
            "composition_id": composition_id,
            "board_id": board["id"],
            "item_id": item["id"],
            "document_id": "paint-doc",
            "object_id": "paint-object",
        },
    ).ok
    refreshed = registry.execute(
        "motion.collage.paint.refresh",
        {
            "composition_id": composition_id,
            "board_id": board["id"],
            "item_id": item["id"],
            "revision": 2,
            "source": {
                "kind": "shape",
                "params": {
                    "width": 120,
                    "height": 90,
                    "fill": "#f0e4cd",
                },
            },
        },
    )
    assert refreshed.ok
    assert refreshed.result["painter_link"]["motion_layer_id"] == layer_id
    assert registry.execute(
        "motion.collage.preflight",
        {
            "composition_id": composition_id,
            "board_id": board["id"],
        },
    ).result["ok"]
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.collage.create",
        "motion.collage.item.add",
        "motion.collage.item.update",
        "motion.collage.item.reorder",
        "motion.collage.edge.set",
        "motion.collage.attachment.set",
        "motion.collage.scan.set",
        "motion.collage.paint.send",
        "motion.collage.paint.refresh",
        "motion.collage.preflight",
    } <= action_ids


def test_umg_never_silently_omits_collage_semantics() -> None:
    composition = _composition()
    composition.layers[0].parent_id = ""
    board = create_collage_board(composition, [composition.layers[0].id])
    document = motion_composition_to_umg_document(composition)
    first = next(
        row for row in document["Layers"]
        if row["Id"] == composition.layers[0].id
    )
    import json

    payload = json.loads(first["PayloadJson"])
    assert "motion_feature_requires_bake:collage_item" in payload["umg_block_reasons"]
    assert preflight_collage(composition, board["id"])["umg_disposition"] == "deterministic_bake"
