"""NodeGraphScene — owns IN / OUT anchors, Serial / Parallel nodes,
and all ConnectionItems between them.

Phase 2B: connection drag + compatibility check.
Phase 2C: delete selected (nodes + their connections, or
          stand-alone connections), bypass toggle, ``graph_mutated``
          signal so the workbench panel can persist scene state to
          ``track.node_graph_view_data``.
Phase 2D: ``to_data()`` / ``load_from_data()`` round-trip the scene
          through a plain dict — call sites stash that dict on the
          legacy ``VideoTrack`` so the graph survives selection
          changes (and, eventually, project save / load).
Phase 2E: Parallel Mixer (purple diamond, multi-input collector).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPointF, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsScene

from app.workbench.node_graph.items.connection_item import ConnectionItem
from app.workbench.node_graph.items.io_node import IONodeItem
from app.workbench.node_graph.items.node_item import NodeItem
from app.workbench.node_graph.items.port_item import PortItem
from app.workbench.node_graph.theme import (
    NODE_GRAPH_COLORS as C,
    NODE_GRAPH_SIZES as S,
)


class NodeGraphScene(QGraphicsScene):

    selection_changed_label = Signal(str)
    graph_mutated = Signal()         # Phase 2C — persistence trigger

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        size = S["canvas_size"]
        self.setSceneRect(-size / 2, -size / 2, size, size)
        self.setBackgroundBrush(QColor(C["canvas_bg"]))
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)

        self._build_io_anchors()
        self._next_id_counter: int = 1
        self._serial_nodes: list[NodeItem] = []
        self._connections: list[ConnectionItem] = []
        self._dragging_connection: Optional[ConnectionItem] = None

        self.selectionChanged.connect(self._emit_selection_label)

    def _build_io_anchors(self) -> None:
        self._in_node = IONodeItem("IN")
        self._in_node.setPos(-400, -S["io_height"] / 2)
        self.addItem(self._in_node)
        self._out_node = IONodeItem("OUT")
        self._out_node.setPos(300, -S["io_height"] / 2)
        self.addItem(self._out_node)

    # ---- node creation ----

    def add_serial_node(
        self, label: str = "Serial", pos: QPointF | None = None,
    ) -> NodeItem:
        nid = self._generate_node_id()
        if pos is None:
            pos = self._next_position()
        node = NodeItem(node_id=nid, label=label)
        node.setPos(pos)
        self.addItem(node)
        self._serial_nodes.append(node)
        self.graph_mutated.emit()
        return node

    def add_blur_node(
        self, label: str = "Blur", pos: QPointF | None = None,
        auto_connect: bool = True,
    ) -> "BlurNodeItem":
        """Add a BlurNodeItem and optionally auto-insert it into the
        existing IN→...→OUT chain so the effect is immediately active."""
        from app.workbench.node_graph.items.blur_node_item import BlurNodeItem
        nid = self._generate_node_id(prefix="B")
        if pos is None:
            pos = self._next_position()
        node = BlurNodeItem(node_id=nid, label=label)
        node.setPos(pos)
        self.addItem(node)
        self._serial_nodes.append(node)
        if auto_connect:
            self._auto_insert_node(node)
        self.graph_mutated.emit()
        return node

    def _auto_insert_node(self, new_node) -> None:
        """Insert ``new_node`` before OUT in the connected chain."""
        try:
            out_in_port = getattr(self._out_node, "rgb_in", None)
            new_in_port = getattr(new_node, "rgb_in", None)
            new_out_port = getattr(new_node, "rgb_out", None)
            if out_in_port is None:
                return
            prev_out_port = None
            if out_in_port.connections:
                existing_conn = out_in_port.connections[0]
                prev_out_port = existing_conn.source
                self.remove_connection(existing_conn)
            if prev_out_port is not None and new_in_port is not None:
                self._wire(prev_out_port, new_in_port)
            if new_out_port is not None:
                self._wire(new_out_port, out_in_port)
        except Exception as e:
            import sys
            print(f"[scene] auto_insert_node failed: {e}", file=sys.stderr)

    def add_parallel_mixer(self, pos: QPointF | None = None) -> "ParallelMixerItem":
        from app.workbench.node_graph.items.parallel_mixer import ParallelMixerItem
        nid = self._generate_node_id(prefix="P")
        if pos is None:
            pos = self._next_position()
        node = ParallelMixerItem(node_id=nid)
        node.setPos(pos)
        self.addItem(node)
        self._serial_nodes.append(node)
        self.graph_mutated.emit()
        return node

    def node_count(self) -> int:
        return len(self._serial_nodes)

    def _generate_node_id(self, prefix: str = "N") -> str:
        nid = f"{prefix}{self._next_id_counter}"
        self._next_id_counter += 1
        return nid

    def _next_position(self) -> QPointF:
        if not self._serial_nodes:
            base_x = self._in_node.scenePos().x() + S["io_width"] + 60
            return QPointF(base_x, -S["node_height"] / 2)
        rightmost = max(self._serial_nodes, key=lambda n: n.scenePos().x())
        offset_y = 12 if (len(self._serial_nodes) % 2 == 0) else -12
        return QPointF(
            rightmost.scenePos().x() + S["node_width"] + 40,
            rightmost.scenePos().y() + offset_y,
        )

    # ---- connection drag ----

    def start_connection_drag(self, source_port: PortItem, mouse_pos: QPointF) -> None:
        self._dragging_connection = ConnectionItem(source_port)
        self._dragging_connection.update_temp_target(mouse_pos)
        self.addItem(self._dragging_connection)

    def update_connection_drag(self, mouse_pos: QPointF) -> None:
        if self._dragging_connection is not None:
            self._dragging_connection.update_temp_target(mouse_pos)

    def end_connection_drag(self, target_port: Optional[PortItem]) -> None:
        if self._dragging_connection is None:
            return
        source = self._dragging_connection.source
        if (
            target_port is not None
            and source.is_compatible_with(target_port)
            and not self._would_create_cycle(source, target_port)
        ):
            # Drop any existing connection feeding the same input port
            # — input ports take exactly one source.
            for existing in list(target_port.connections):
                self.remove_connection(existing)
            self._dragging_connection.target = target_port
            target_port.connections.append(self._dragging_connection)
            source.connections.append(self._dragging_connection)
            self._connections.append(self._dragging_connection)
            self._dragging_connection.update_endpoints()
            self.graph_mutated.emit()
        else:
            self.removeItem(self._dragging_connection)
        self._dragging_connection = None

    def _would_create_cycle(
        self, source_port: PortItem, target_port: PortItem,
    ) -> bool:
        """Walk back from ``source_port``'s node — if we reach
        ``target_port``'s node, this connection would close a loop."""
        target_node = target_port.parentItem()
        # BFS over nodes upstream of source.
        seen = set()
        frontier = [source_port.parentItem()]
        while frontier:
            node = frontier.pop(0)
            if node is None or id(node) in seen:
                continue
            seen.add(id(node))
            if node is target_node:
                return True
            for port in getattr(node, "all_ports", lambda: [])():
                if not port.is_input:
                    continue
                for conn in port.connections:
                    upstream = conn.source.parentItem()
                    frontier.append(upstream)
        return False

    # ---- delete ----

    def remove_connection(self, conn: ConnectionItem) -> None:
        if conn in self._connections:
            self._connections.remove(conn)
        conn.detach()
        self.removeItem(conn)
        self.graph_mutated.emit()

    def delete_selected(self) -> None:
        items = list(self.selectedItems())
        if not items:
            return
        # Connections first.
        for it in items:
            if isinstance(it, ConnectionItem):
                self.remove_connection(it)
        # Then nodes (skipping IN / OUT, which are anchored).
        for it in items:
            if isinstance(it, NodeItem):
                # Drop every connection touching this node.
                for port in it.all_ports():
                    for conn in list(port.connections):
                        self.remove_connection(conn)
                if it in self._serial_nodes:
                    self._serial_nodes.remove(it)
                self.removeItem(it)
        self.graph_mutated.emit()

    # ---- selection ----

    def _emit_selection_label(self) -> None:
        items = self.selectedItems()
        if items and isinstance(items[0], NodeItem):
            n = items[0]
            self.selection_changed_label.emit(f"{n.node_id} ({n.label})")
        elif items and isinstance(items[0], IONodeItem):
            self.selection_changed_label.emit(items[0].kind)
        elif items and isinstance(items[0], ConnectionItem):
            kind = items[0].source.port_type.upper()
            self.selection_changed_label.emit(f"{kind} link")
        else:
            self.selection_changed_label.emit("")

    # ---- persistence (Phase 2D) ----

    def to_data(self) -> dict:
        """Serialise the scene into a JSON-safe dict. Stored on the
        active VideoTrack so selecting back to it restores the graph."""
        nodes_data: list[dict] = []
        for n in self._serial_nodes:
            masks = getattr(n, "masks", None) or []
            entry: dict = {
                "id": n.node_id,
                "kind": getattr(n, "NODE_KIND", "serial"),
                "label": n.label,
                "x": float(n.scenePos().x()),
                "y": float(n.scenePos().y()),
                "bypassed": bool(getattr(n, "bypassed", False)),
                "user_color": getattr(n, "user_color", None),
                # Grade NOT persisted (starts fresh each session).
                # Masks ARE persisted (user effort to draw).
                "masks": [m.to_dict() for m in masks],
            }
            # Blur params ARE persisted (user set them intentionally).
            bp = getattr(n, "blur_params", None)
            if bp is not None:
                entry["blur_params"] = bp.to_dict()
                entry["blur_invert_mask"] = bool(getattr(n, "blur_invert_mask", True))
            nodes_data.append(entry)
        conns_data: list[dict] = []
        for c in self._connections:
            sn = c.source.parentItem()
            tn = c.target.parentItem()
            conns_data.append({
                "src_node": _node_identity(sn),
                "src_port": c.source.port_id,
                "dst_node": _node_identity(tn),
                "dst_port": c.target.port_id,
            })
        return {
            "nodes": nodes_data,
            "connections": conns_data,
            "next_id": self._next_id_counter,
        }

    def load_from_data(self, data: dict) -> None:
        """Restore from a previous ``to_data`` snapshot. Clears any
        existing user-added nodes (IN / OUT stay)."""
        # Wipe current nodes + connections (but keep IN / OUT).
        for c in list(self._connections):
            self.remove_connection(c)
        for n in list(self._serial_nodes):
            self.removeItem(n)
        self._serial_nodes.clear()
        self._connections.clear()
        self._next_id_counter = int(data.get("next_id", 1))

        # Recreate nodes.
        id_map: dict[str, NodeItem | IONodeItem] = {
            "IN": self._in_node, "OUT": self._out_node,
        }
        for nd in data.get("nodes", []):
            kind = nd.get("kind", "serial")
            pos = QPointF(float(nd.get("x", 0.0)), float(nd.get("y", 0.0)))
            if kind == "parallel":
                node = self.add_parallel_mixer(pos=pos)
                node.node_id = nd["id"]
            elif kind == "blur":
                from app.workbench.node_graph.items.blur_node_item import BlurNodeItem
                node = BlurNodeItem(node_id=nd["id"], label=nd.get("label", "Blur"))
                node.setPos(pos)
                self.addItem(node)
                self._serial_nodes.append(node)
                # Restore blur params
                bp_data = nd.get("blur_params")
                if bp_data:
                    from app.blur_params import BlurParams
                    try:
                        node.blur_params = BlurParams.from_dict(bp_data)
                    except Exception:
                        pass
                node.blur_invert_mask = bool(nd.get("blur_invert_mask", True))
            else:
                node = NodeItem(node_id=nd["id"], label=nd.get("label", "Serial"))
                node.setPos(pos)
                self.addItem(node)
                self._serial_nodes.append(node)
            node.bypassed = bool(nd.get("bypassed", False))
            node.user_color = nd.get("user_color")
            # Grade is not persisted — node always starts at identity.
            # (Older snapshots that have "grade" data are silently
            # ignored so sessions aren't poisoned by stale values.)
            # Restore masks (Power Window / Qualifier / Magic Mask /
            # Tracker). Older snapshots without "masks" keep an empty
            # list so the node behaves like an unmasked one.
            mask_data = nd.get("masks") or []
            if mask_data:
                from app.node_mask import mask_from_dict
                restored: list = []
                for md in mask_data:
                    m = mask_from_dict(md)
                    if m is not None:
                        restored.append(m)
                node.masks = restored
            node.update()
            id_map[node.node_id] = node

        # Recreate connections.
        for cd in data.get("connections", []):
            src = id_map.get(cd["src_node"])
            dst = id_map.get(cd["dst_node"])
            if src is None or dst is None:
                continue
            sport = getattr(src, cd["src_port"], None)
            dport = getattr(dst, cd["dst_port"], None)
            if sport is None or dport is None:
                continue
            self._wire(sport, dport)
        # Don't re-emit graph_mutated for a load — that would mark
        # the loaded state as a new edit on the editor's history.

    def _wire(self, source_port: PortItem, target_port: PortItem) -> None:
        conn = ConnectionItem(source_port, target_port)
        source_port.connections.append(conn)
        target_port.connections.append(conn)
        self._connections.append(conn)
        self.addItem(conn)

    # ---- DaVinci chain evaluation ----

    def evaluate_chain_to(self, target) -> list:
        """Walk the connected RGB IN→target path and collect each
        upstream node's ColorGrade in IN→target order.

        Returns a list of ``ColorGrade`` instances ready to apply in
        sequence. The target node's own grade is included at the end
        — that's the point of the per-node thumbnail (it shows the
        cumulative result *up to and including* this node).

        For the OUT IO node, returns the chain leading to OUT, which
        is the full project pipeline.

        Bypassed nodes contribute identity (skipped).

        For now this assumes a linear Serial chain with a single
        rgb_in / rgb_out path. Parallel mixers and disconnected nodes
        return their own grade only — proper Parallel-mixing is
        Phase E follow-up.
        """
        if target is None:
            return []
        from app.workbench.node_graph.items.node_item import NodeItem
        from app.workbench.node_graph.items.parallel_mixer import (
            ParallelMixerItem,
        )

        # Walk back from target via its rgb_in connection.
        chain_nodes: list = []
        cur = target
        seen: set[int] = set()
        while True:
            if cur is None or id(cur) in seen:
                break
            seen.add(id(cur))
            # IN node — terminate. Anything before this is the source.
            if isinstance(cur, IONodeItem) and cur.kind == "IN":
                break
            chain_nodes.append(cur)
            # Walk back through rgb_in port.
            in_port = getattr(cur, "rgb_in", None)
            if in_port is None or not in_port.connections:
                break
            up_conn = in_port.connections[0]
            cur = up_conn.source.parentItem()

        chain_nodes.reverse()  # IN→target order
        grades: list = []
        for n in chain_nodes:
            if not isinstance(n, (NodeItem, ParallelMixerItem)):
                continue
            if getattr(n, "bypassed", False):
                continue
            g = getattr(n, "color_grade", None)
            if g is not None and not g.is_identity():
                grades.append(g)
        return grades


def _node_identity(node) -> str:
    """Return ``IN`` / ``OUT`` / node_id depending on the node kind."""
    if isinstance(node, IONodeItem):
        return node.kind
    return getattr(node, "node_id", "?")
