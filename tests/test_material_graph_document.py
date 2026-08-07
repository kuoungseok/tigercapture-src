"""Contract for the authored material/texture graph shared by UMG and PBR."""
from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_registry_keeps_surfaces_separate_and_claims_nothing() -> None:
    from app.material_graph.registry import (
        node_types_for_surface,
        registry_report,
    )

    report = registry_report()
    assert report["claim_boundary"]["unreal_source_derived"] is False
    assert report["claim_boundary"]["unreal_pixel_parity"] is False

    ui_types = {row["type"] for row in node_types_for_surface("ui")}
    pbr_types = {row["type"] for row in node_types_for_surface("pbr")}
    # Each surface sees exactly one output, and only its own.
    assert "UIOutput" in ui_types and "UIOutput" not in pbr_types
    assert "PBROutput" in pbr_types and "PBROutput" not in ui_types
    # The shared vocabulary really is shared.
    assert {"Multiply", "Lerp", "TextureSample"} <= (ui_types & pbr_types)


def test_pin_types_promote_scalars_but_not_the_reverse() -> None:
    from app.material_graph.registry import pins_are_compatible

    assert pins_are_compatible("float", "vec3") is True
    assert pins_are_compatible("vec3", "vec4") is True
    assert pins_are_compatible("vec3", "float") is False
    assert pins_are_compatible("texture", "vec3") is False


def test_new_graph_starts_with_only_its_output() -> None:
    from app.material_graph import document

    for surface, output_type in (("ui", "UIOutput"), ("pbr", "PBROutput")):
        graph = document.create_graph(surface)
        assert [row["type"] for row in graph["nodes"]] == [output_type]
        report = document.graph_report(graph)
        assert report["driven_outputs"] == []
        assert report["missing_outputs"]


def test_editing_a_graph_reports_what_still_drives_nothing() -> None:
    from app.material_graph import document

    graph = document.create_graph("pbr")
    graph, source = document.add_node(graph, "SourceImage", position=(0, 0))
    graph, normal = document.add_node(
        graph,
        "NormalFromHeight",
        position=(200, 60),
    )
    graph = document.connect(graph, source["id"], "Luminance", normal["id"], "Height")
    graph = document.connect(graph, normal["id"], "Normal", "output", "Normal")
    graph = document.connect(graph, source["id"], "RGB", "output", "Base Color")

    report = document.graph_report(graph)
    assert report["driven_outputs"] == ["Base Color", "Normal"]
    assert "Roughness" in report["missing_outputs"]
    assert report["unreachable_node_ids"] == []
    order = report["evaluation_order"]
    assert order.index(source["id"]) < order.index(normal["id"])
    assert order.index(normal["id"]) < order.index("output")


def test_illegal_wires_are_refused_with_a_reason() -> None:
    from app.material_graph import document

    graph = document.create_graph("pbr")
    graph, source = document.add_node(graph, "SourceImage", position=(0, 0))
    graph, normal = document.add_node(graph, "NormalFromHeight", position=(200, 0))

    # vec3 into a float pin.
    with pytest.raises(document.MaterialGraphError):
        document.connect(graph, source["id"], "RGB", normal["id"], "Height")
    # Pin that does not exist.
    with pytest.raises(document.MaterialGraphError):
        document.connect(graph, source["id"], "Nope", normal["id"], "Height")
    # Node type the surface does not offer.
    with pytest.raises(document.MaterialGraphError):
        document.add_node(graph, "UIOutput")


def test_a_wire_that_would_loop_is_refused() -> None:
    from app.material_graph import document

    graph = document.create_graph("pbr")
    graph, first = document.add_node(graph, "Multiply", position=(0, 0))
    graph, second = document.add_node(graph, "Add", position=(200, 0))
    graph = document.connect(graph, first["id"], "Result", second["id"], "A")
    with pytest.raises(document.MaterialGraphError) as error:
        document.connect(graph, second["id"], "Result", first["id"], "A")
    assert "loop" in str(error.value)


def test_an_input_pin_holds_one_wire() -> None:
    from app.material_graph import document

    graph = document.create_graph("pbr")
    graph, first = document.add_node(graph, "ScalarParameter", position=(0, 0))
    graph, second = document.add_node(graph, "ScalarParameter", position=(0, 90))
    graph, target = document.add_node(graph, "Multiply", position=(200, 40))
    graph = document.connect(graph, first["id"], "Value", target["id"], "A")
    graph = document.connect(graph, second["id"], "Value", target["id"], "A")
    links = [row for row in graph["links"] if row["to_node"] == target["id"]]
    assert len(links) == 1
    assert links[0]["from_node"] == second["id"]


def test_the_output_node_cannot_be_deleted() -> None:
    from app.material_graph import document

    graph = document.create_graph("ui")
    graph, extra = document.add_node(graph, "Multiply", position=(0, 0))
    revised = document.remove_nodes(graph, [extra["id"], "output"])
    assert [row["type"] for row in revised["nodes"]] == ["UIOutput"]


def test_normalize_drops_unknown_nodes_and_dangling_links() -> None:
    from app.material_graph import document

    graph = document.normalize_graph(
        {
            "surface": "ui",
            "nodes": [
                {"id": "a", "type": "Multiply", "position": [0, 0]},
                {"id": "b", "type": "NotARealNode"},
                {"id": "a", "type": "Add", "position": [10, 10]},
            ],
            "links": [
                {"from_node": "a", "from_pin": "Result", "to_node": "gone", "to_pin": "A"},
                {"from_node": "b", "from_pin": "x", "to_node": "a", "to_pin": "A"},
            ],
        }
    )
    ids = [row["id"] for row in graph["nodes"]]
    assert len(ids) == len(set(ids)) == 2
    assert graph["links"] == []


def test_parameters_fall_back_to_their_declared_defaults() -> None:
    from app.material_graph import document

    graph = document.create_graph("pbr")
    graph, node = document.add_node(graph, "NormalFromHeight", position=(0, 0))
    assert document.node_by_id(graph, node["id"])["params"]["Strength"] == 1.0
    graph = document.set_node_param(graph, node["id"], "Strength", 2.5)
    assert document.node_by_id(graph, node["id"])["params"]["Strength"] == 2.5
    with pytest.raises(document.MaterialGraphError):
        document.set_node_param(graph, node["id"], "Nope", 1.0)


def test_widget_renders_every_node_with_a_title_and_named_pins() -> None:
    _app()
    from PySide6.QtGui import QImage

    from app.material_graph import document
    from app.material_graph.view import MaterialGraphView, node_layout

    graph = document.create_graph("ui")
    graph, gradient = document.add_node(
        graph,
        "LinearGradient",
        position=(0, 0),
    )
    graph, uv = document.add_node(graph, "TextureCoordinate", position=(-240, 0))
    graph = document.connect(graph, uv["id"], "UV", gradient["id"], "UV")

    layout = node_layout(document.node_by_id(graph, gradient["id"]))
    assert layout["title"] == "Linear Gradient"
    assert [pin["name"] for pin in layout["pins"] if pin["is_input"]] == ["UV"]
    assert [pin["name"] for pin in layout["pins"] if not pin["is_input"]] == [
        "Color"
    ]
    # The body has to be tall enough that every pin it advertises sits inside
    # it, however many rows that takes.
    assert all(0.0 < pin["pos"].y() < layout["height"] for pin in layout["pins"])
    tall = node_layout(document.node_by_id(graph, "output"))
    assert tall["height"] > layout["height"]
    assert all(0.0 < pin["pos"].y() < tall["height"] for pin in tall["pins"])

    view = MaterialGraphView("ui")
    view.resize(640, 400)
    view.set_graph(graph)
    frame = QImage(view.size(), QImage.Format.Format_ARGB32_Premultiplied)
    frame.fill(0)
    view.render(frame)
    painted = sum(
        1
        for y in range(0, frame.height(), 4)
        for x in range(0, frame.width(), 4)
        if frame.pixel(x, y) & 0xFFFFFF
    )
    assert painted > 0
    view.close()
    view.deleteLater()


def test_widget_edits_go_through_the_document_and_report_once() -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.material_graph.view import MaterialGraphView

    view = MaterialGraphView("pbr")
    changes: list[dict] = []
    messages: list[str] = []
    view.graph_changed.connect(changes.append)
    view.status_message.connect(messages.append)

    view.add_node("SourceImage", QPointF(-200.0, 0.0))
    assert len(changes) == 1
    source_id = [
        row["id"] for row in view.graph()["nodes"] if row["type"] == "SourceImage"
    ][0]

    view.connect_pins(source_id, "RGB", "output", "Base Color")
    assert len(changes) == 2
    assert view.graph()["links"][0]["to_pin"] == "Base Color"

    # A refused edit reports instead of changing the document.
    view.connect_pins(source_id, "RGB", "output", "Roughness")
    assert len(changes) == 2
    assert messages

    view.disconnect_pin("output", "Base Color")
    assert view.graph()["links"] == []
    view.close()
    view.deleteLater()
