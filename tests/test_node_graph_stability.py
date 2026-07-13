from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_node_graph_uses_noindex_for_dynamic_connection_geometry():
    _app()
    from PySide6.QtWidgets import QGraphicsScene

    from app.workbench.node_graph.scene import NodeGraphScene

    scene = NodeGraphScene()

    assert scene.itemIndexMethod() == QGraphicsScene.ItemIndexMethod.NoIndex


def test_node_graph_delete_selected_discards_live_connection_drag():
    _app()
    from PySide6.QtCore import QPointF

    from app.workbench.node_graph.scene import NodeGraphScene

    scene = NodeGraphScene()
    node = scene.add_serial_node(pos=QPointF(0, 0))
    scene.start_connection_drag(node.rgb_out, node.rgb_out.scenePos())
    scene.update_connection_drag(QPointF(120, 25))

    node.setSelected(True)
    scene.delete_selected()

    assert scene._dragging_connection is None
    assert node not in scene.items()
    assert node.rgb_out.connections == []


def test_node_graph_replacing_input_connection_detaches_old_connection():
    _app()
    from PySide6.QtCore import QPointF

    from app.workbench.node_graph.scene import NodeGraphScene

    scene = NodeGraphScene()
    first = scene.add_serial_node(pos=QPointF(0, 0))
    second = scene.add_serial_node(pos=QPointF(220, 0))
    out_input = scene._out_node.rgb_in

    scene.start_connection_drag(first.rgb_out, first.rgb_out.scenePos())
    scene.end_connection_drag(out_input)
    scene.start_connection_drag(second.rgb_out, second.rgb_out.scenePos())
    scene.end_connection_drag(out_input)

    assert len(scene._connections) == 1
    assert first.rgb_out.connections == []
    assert second.rgb_out.connections == scene._connections
    assert out_input.connections == scene._connections


def test_node_graph_load_discards_live_connection_drag():
    _app()
    from PySide6.QtCore import QPointF

    from app.workbench.node_graph.scene import NodeGraphScene

    scene = NodeGraphScene()
    node = scene.add_serial_node(pos=QPointF(0, 0))
    scene.start_connection_drag(node.rgb_out, node.rgb_out.scenePos())
    scene.update_connection_drag(QPointF(80, 10))

    scene.load_from_data({"nodes": [], "connections": [], "next_id": 1})

    assert scene._dragging_connection is None
    assert scene._connections == []


def test_node_graph_widget_workflow_preset_adds_connected_chain():
    _app()

    from app.workbench.node_graph.widget import NodeGraphWidget

    widget = NodeGraphWidget()
    try:
        widget.add_workflow_preset("color_polish")

        nodes = list(widget.scene._serial_nodes)
        assert [getattr(node, "NODE_KIND", "") for node in nodes] == [
            "whitebalance",
            "curves",
            "vignette",
        ]
        assert len(widget.scene._connections) == len(nodes) + 1
        assert nodes[-1].isSelected()
    finally:
        widget.deleteLater()


def test_node_graph_tracks_current_video_track_context_color():
    _app()

    from types import SimpleNamespace

    from app.timeline_track_colors import track_accent_color, track_context_label
    from app.workbench.node_graph.widget import NodeGraphWidget

    track = SimpleNamespace(id=2, node_graph_view_data=None)
    widget = NodeGraphWidget()
    try:
        widget.set_track(track)
        nodes = list(widget.scene._serial_nodes)

        assert nodes
        assert nodes[0].track_context_color == track_accent_color(track).name()
        assert nodes[0].track_context_label == track_context_label(track)
    finally:
        widget.deleteLater()


def test_node_graph_new_nodes_inherit_track_context_color():
    _app()

    from PySide6.QtGui import QColor

    from app.workbench.node_graph.scene import NodeGraphScene

    scene = NodeGraphScene()
    scene.set_track_context(QColor("#9ACB8C"), "V3")
    node = scene.add_serial_node()

    assert node.track_context_color == QColor("#9ACB8C").name()
    assert node.track_context_label == "V3"
