from __future__ import annotations

import os

from app.painter_ui_document import add_ui_object, normalize_ui_document
from app.painter_ui_vector_network import (
    add_vector_node,
    create_vector_network,
    join_vector_nodes,
    normalize_vector_network,
    remove_vector_node,
    set_vector_path_closed,
    set_vector_segment_kind,
    split_vector_segment,
    update_vector_node,
    vector_network_to_svg_path,
)


def test_vector_network_normalizes_stable_ids_and_drops_dangling_segments() -> None:
    network = normalize_vector_network(
        {
            "nodes": [
                {"id": "node-a", "x": 0, "y": 0},
                {"id": "node-a", "x": 1, "y": 1},
            ],
            "segments": [
                {
                    "id": "segment-a",
                    "start_node_id": "node-a",
                    "end_node_id": "missing",
                }
            ],
        }
    )

    assert [row["id"] for row in network["nodes"]] == ["node-a", "node-1"]
    assert network["segments"] == []


def test_bezier_split_preserves_curve_and_stable_segment_id() -> None:
    network = set_vector_segment_kind(
        create_vector_network(),
        "segment-1",
        "cubic",
    )
    network = update_vector_node(
        network,
        "node-1",
        {"out_handle": {"x": 0.2, "y": 0.0}},
    )
    network = update_vector_node(
        network,
        "node-2",
        {"in_handle": {"x": 0.8, "y": 1.0}},
    )

    split, node_id = split_vector_segment(
        network,
        "segment-1",
        position=0.5,
    )

    assert node_id == "node-3"
    assert [row["id"] for row in split["segments"]] == [
        "segment-1",
        "segment-2",
    ]
    assert all(row["kind"] == "cubic" for row in split["segments"])
    assert " C " in vector_network_to_svg_path(split)


def test_open_path_can_add_join_close_and_remove_nodes() -> None:
    network, node_id = add_vector_node(
        create_vector_network(),
        x=1.0,
        y=1.0,
        after_node_id="node-2",
    )
    assert node_id == "node-3"
    network = set_vector_path_closed(network, True)
    assert network["closed"] is True
    assert network["segments"][-1]["end_node_id"] == "node-1"

    network = set_vector_path_closed(network, False)
    network = join_vector_nodes(network, "node-3", "node-1", kind="cubic")
    assert network["segments"][-1]["kind"] == "cubic"

    network = remove_vector_node(network, "node-2")
    assert {row["id"] for row in network["nodes"]} == {"node-1", "node-3"}
    assert network["closed"] is False


def test_ui_document_round_trips_vector_network_and_derived_svg() -> None:
    document, row = add_ui_object(
        normalize_ui_document(None),
        kind="path",
        content={"vector_network": create_vector_network()},
    )

    normalized = normalize_ui_document(document)
    stored = next(item for item in normalized["objects"] if item["id"] == row["id"])
    assert stored["content"]["vector_network"]["nodes"][0]["id"] == "node-1"
    assert stored["content"]["vector_fill_geometry"][0]["path"].startswith("M ")
    assert stored["content"]["vector_paths"] == [
        stored["content"]["vector_fill_geometry"][0]["path"]
    ]


def test_vector_actions_share_document_mutation_and_one_step_undo() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(480, 320, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    registry.execute("paint.ui.workspace.set", {"mode": "ui_design"})
    added = registry.execute(
        "paint.ui.object.add",
        {
            "kind": "path",
            "content": {"vector_network": create_vector_network()},
        },
    ).to_dict()
    object_id = added["result"]["ui_design"]["document"]["selection"][
        "object_id"
    ]
    result = registry.execute(
        "paint.ui.vector.segment.set",
        {
            "object_id": object_id,
            "segment_id": "segment-1",
            "kind": "cubic",
        },
    ).to_dict()
    network = result["result"]["vector_edit"]["network"]
    assert network["segments"][0]["kind"] == "cubic"
    assert network["nodes"][0]["out_handle"] is not None

    registry.execute(
        "paint.ui.vector.segment.split",
        {
            "object_id": object_id,
            "segment_id": "segment-1",
            "position": 0.5,
        },
    )
    assert len(
        dialog._painter_ui_document["objects"][0]["content"][
            "vector_network"
        ]["nodes"]
    ) == 3

    dialog._undo()
    restored = dialog._painter_ui_document["objects"][0]["content"][
        "vector_network"
    ]
    assert len(restored["nodes"]) == 2
    assert restored["segments"][0]["kind"] == "cubic"
    dialog.close()
    app.processEvents()


def test_canvas_double_click_enters_vector_edit_and_drag_emits_content() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        normalize_ui_document(None, fallback_width=480, fallback_height=320),
        kind="path",
        x=80,
        y=80,
        width=240,
        height=120,
        style={
            "fill": "#00000000",
            "stroke": "#72A7FF",
            "stroke_width": 2,
        },
        content={"vector_network": create_vector_network()},
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 700)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    changed: list[tuple[str, dict]] = []
    vector_states: list[dict] = []
    overlay.object_changes_requested.connect(
        lambda object_id, changes: changed.append((object_id, changes))
    )
    overlay.vector_edit_changed.connect(
        lambda state: vector_states.append(dict(state or {}))
    )

    rect = overlay._object_rect(row)
    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=rect.center().toPoint(),
    )
    app.processEvents()
    assert overlay._vector_edit_object_id == row["id"]

    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=rect.center().toPoint(),
    )
    app.processEvents()
    assert overlay._vector_active_segment_id == "segment-1"
    assert vector_states[-1]["segment_id"] == "segment-1"

    nodes, _handles = overlay._vector_control_positions(
        overlay._selected_row()
    )
    start = nodes["node-1"].toPoint()
    target = QPoint(start.x() + 36, start.y() - 18)
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, target, delay=1)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()

    assert changed and changed[-1][0] == row["id"]
    network = changed[-1][1]["content"]["vector_network"]
    moved = next(item for item in network["nodes"] if item["id"] == "node-1")
    assert moved["x"] > 0.0
    assert moved["y"] < 0.5
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_vector_context_bar_emits_commands_and_updates_enablement() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QWidget

    app = QApplication.instance() or QApplication([])
    from app.painter_ui_vector_context_bar import PainterUIVectorContextBar

    parent = QWidget()
    parent.resize(640, 480)
    bar = PainterUIVectorContextBar(parent)
    commands: list[str] = []
    bar.command_requested.connect(commands.append)
    bar.set_state(
        {
            "object_id": "path-1",
            "node_id": "node-1",
            "segment_id": "segment-1",
            "node_count": 3,
            "closed": False,
        }
    )
    parent.show()
    app.processEvents()

    assert bar.isVisible()
    assert bar.curve_button.isEnabled()
    assert bar.delete_button.isEnabled()
    bar.curve_button.click()
    bar.split_button.click()
    bar.close_button.click()
    assert commands == ["curve", "split", "toggle_closed"]

    bar.set_state({})
    assert bar.isHidden()
    parent.close()
    parent.deleteLater()
    app.processEvents()


def test_vector_context_command_and_action_have_matching_undoable_mutation() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(480, 320, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row = add_ui_object(
        normalize_ui_document(None, fallback_width=480, fallback_height=320),
        kind="path",
        content={"vector_network": create_vector_network()},
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    dialog._painter_ui_overlay._vector_edit_object_id = row["id"]
    dialog._painter_ui_overlay._vector_active_node_id = "node-1"
    state = dialog._painter_ui_overlay._vector_edit_state()
    dialog._sync_painter_ui_vector_context(state)

    dialog._handle_painter_ui_vector_command("curve")

    updated = dialog._painter_ui_document["objects"][0]["content"][
        "vector_network"
    ]
    assert updated["segments"][0]["kind"] == "cubic"
    assert dialog._undo_labels[-1] == "Convert UI vector segment"
    dialog._undo()
    restored = dialog._painter_ui_document["objects"][0]["content"][
        "vector_network"
    ]
    assert restored["segments"][0]["kind"] == "line"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_vector_path_exports_as_editable_svg_not_baked_bitmap() -> None:
    from app.painter_ui_asset_export import _svg_for_artboard

    document, _row = add_ui_object(
        normalize_ui_document(None, fallback_width=400, fallback_height=300),
        kind="path",
        x=40,
        y=50,
        width=200,
        height=100,
        style={"fill": "#00000000", "stroke": "#72A7FF", "stroke_width": 2},
        content={"vector_network": create_vector_network()},
    )
    svg, blocked = _svg_for_artboard(document, document["artboards"][0])

    assert blocked == []
    assert '<path d="M 40 100 L 240 100"' in svg
    assert "data:image/png" not in svg
