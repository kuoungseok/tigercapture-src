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


def _record_node_action(event: str, **data) -> None:
    try:
        from app.crash_reporter import record_action
        record_action(f"node_graph.{event}", **data)
    except Exception:
        pass


class NodeGraphScene(QGraphicsScene):

    selection_changed_label = Signal(str)
    graph_mutated = Signal()         # Phase 2C — persistence trigger

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        size = S["canvas_size"]
        self.setSceneRect(-size / 2, -size / 2, size, size)
        self.setBackgroundBrush(QColor(C["canvas_bg"]))
        # This graph is highly dynamic: connection paths resize while users
        # drag ports/nodes and items are often removed during the same gesture.
        # NoIndex is more stable for that workload than Qt's BSP scene index.
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.NoIndex)

        self._build_io_anchors()
        self._next_id_counter: int = 1
        self._serial_nodes: list[NodeItem] = []
        self._connections: list[ConnectionItem] = []
        self._dragging_connection: Optional[ConnectionItem] = None

        self.selectionChanged.connect(self._emit_selection_label)

    def _build_io_anchors(self) -> None:
        self._in_node = IONodeItem("IN")
        self._in_node.setPos(-360, -S["io_height"] / 2)
        self.addItem(self._in_node)
        self._out_node = IONodeItem("OUT")
        self._out_node.setPos(320, -S["io_height"] / 2)
        self.addItem(self._out_node)

    # ---- node creation ----

    def add_serial_node(
        self,
        label: str = "Serial",
        pos: QPointF | None = None,
        auto_connect: bool = False,
    ) -> NodeItem:
        nid = self._generate_node_id()
        if pos is None:
            pos = self._next_position()
        node = NodeItem(node_id=nid, label=label)
        node.setPos(pos)
        self.addItem(node)
        self._serial_nodes.append(node)
        if auto_connect:
            self._auto_insert_node(node)
        _record_node_action("add_node", kind="serial", node_id=nid)
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
        _record_node_action("add_node", kind="blur", node_id=nid)
        self.graph_mutated.emit()
        return node

    def add_effect_node(
        self, effect_kind: str, label: str = "",
        pos: "QPointF | None" = None,
        auto_connect: bool = True,
    ):
        """Add an EffectNodeItem of the given kind (curves, glow, etc.)."""
        from app.workbench.node_graph.items.effect_node_item import EffectNodeItem
        from app.effect_node_params import _KIND_META
        meta = _KIND_META.get(effect_kind, (label or effect_kind, "#607D8B", None))
        nid = self._generate_node_id(prefix="E")
        if pos is None:
            pos = self._next_position()
        node = EffectNodeItem(effect_kind=effect_kind, node_id=nid, label=label or meta[0])
        node.setPos(pos)
        self.addItem(node)
        self._serial_nodes.append(node)
        if auto_connect:
            self._auto_insert_node(node)
        _record_node_action("add_node", kind=effect_kind, node_id=nid)
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
            else:
                prev_out_port = getattr(self._in_node, "rgb_out", None)
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
        _record_node_action("add_node", kind="parallel", node_id=nid)
        self.graph_mutated.emit()
        return node

    def node_count(self) -> int:
        return len(self._serial_nodes)

    def ensure_default_chain(self) -> bool:
        """Repair old/fresh graphs where serial nodes exist but OUT is unwired."""
        try:
            out_in_port = getattr(self._out_node, "rgb_in", None)
            in_out_port = getattr(self._in_node, "rgb_out", None)
            if out_in_port is None or in_out_port is None:
                return False
            if getattr(out_in_port, "connections", None):
                return False
            nodes = [
                n for n in list(self._serial_nodes)
                if getattr(n, "rgb_in", None) is not None
                and getattr(n, "rgb_out", None) is not None
            ]
            if not nodes:
                return False
            prev_out = in_out_port
            changed = False
            for node in nodes:
                node_in = getattr(node, "rgb_in", None)
                node_out = getattr(node, "rgb_out", None)
                if node_in is None or node_out is None:
                    continue
                if not getattr(node_in, "connections", None):
                    self._wire(prev_out, node_in)
                    changed = True
                prev_out = node_out
            if not getattr(out_in_port, "connections", None):
                self._wire(prev_out, out_in_port)
                changed = True
            return changed
        except Exception:
            return False

    def _generate_node_id(self, prefix: str = "N") -> str:
        nid = f"{prefix}{self._next_id_counter}"
        self._next_id_counter += 1
        return nid

    def _next_position(self) -> QPointF:
        if not self._serial_nodes:
            base_x = self._in_node.scenePos().x() + S["io_width"] + 54
            return QPointF(base_x, -S["node_height"] / 2)
        rightmost = max(self._serial_nodes, key=lambda n: n.scenePos().x())
        offset_y = 12 if (len(self._serial_nodes) % 2 == 0) else -12
        return QPointF(
            rightmost.scenePos().x() + S["node_width"] + 34,
            rightmost.scenePos().y() + offset_y,
        )

    # ---- connection drag ----

    def _discard_dragging_connection(self) -> None:
        conn = self._dragging_connection
        if conn is None:
            return
        self._dragging_connection = None
        try:
            conn.detach()
        except Exception:
            pass
        try:
            if conn.scene() is self:
                self.removeItem(conn)
        except RuntimeError:
            pass

    def start_connection_drag(self, source_port: PortItem, mouse_pos: QPointF) -> None:
        self._discard_dragging_connection()
        try:
            if source_port.scene() is not self:
                return
        except RuntimeError:
            return
        conn = ConnectionItem(source_port)
        conn.update_temp_target(mouse_pos)
        self._dragging_connection = conn
        self.addItem(conn)
        _record_node_action(
            "connection_drag_start",
            source_node=_node_identity(source_port.parentItem()),
            source_port=source_port.port_id,
        )

    def update_connection_drag(self, mouse_pos: QPointF) -> None:
        conn = self._dragging_connection
        if conn is None:
            return
        try:
            if conn.scene() is not self or conn.source.scene() is not self:
                self._discard_dragging_connection()
                return
            conn.update_temp_target(mouse_pos)
        except RuntimeError:
            self._discard_dragging_connection()

    def end_connection_drag(self, target_port: Optional[PortItem]) -> None:
        conn = self._dragging_connection
        if conn is None:
            return
        self._dragging_connection = None
        source = conn.source
        try:
            source_ok = source.scene() is self
            target_ok = target_port is not None and target_port.scene() is self
        except RuntimeError:
            self._discard_dragging_connection()
            return
        if (
            source_ok
            and target_ok
            and source.is_compatible_with(target_port)
            and not self._would_create_cycle(source, target_port)
        ):
            # Drop any existing connection feeding the same input port
            # — input ports take exactly one source.
            for existing in list(target_port.connections):
                self.remove_connection(existing)
            conn.target = target_port
            target_port.connections.append(conn)
            source.connections.append(conn)
            self._connections.append(conn)
            conn.update_endpoints()
            _record_node_action(
                "connection_created",
                source_node=_node_identity(source.parentItem()),
                source_port=source.port_id,
                target_node=_node_identity(target_port.parentItem()),
                target_port=target_port.port_id,
            )
            self.graph_mutated.emit()
        else:
            _record_node_action(
                "connection_rejected",
                source_node=_node_identity(source.parentItem()),
                source_port=source.port_id,
                target_node=_node_identity(target_port.parentItem()) if target_port is not None else "",
                target_port=getattr(target_port, "port_id", ""),
            )
            try:
                if conn.scene() is self:
                    self.removeItem(conn)
            except RuntimeError:
                pass

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
                for conn in list(port.connections):
                    try:
                        upstream = conn.source.parentItem()
                    except RuntimeError:
                        continue
                    frontier.append(upstream)
        return False

    # ---- delete ----

    def remove_connection(self, conn: ConnectionItem) -> None:
        if conn is self._dragging_connection:
            self._dragging_connection = None
        if conn in self._connections:
            self._connections.remove(conn)
        conn.detach()
        try:
            if conn.scene() is self:
                self.removeItem(conn)
        except RuntimeError:
            pass
        _record_node_action("connection_removed")
        self.graph_mutated.emit()

    def delete_selected(self) -> None:
        self._discard_dragging_connection()
        items = list(self.selectedItems())
        if not items:
            return
        _record_node_action(
            "delete_selected",
            items=len(items),
            nodes=sum(1 for it in items if isinstance(it, NodeItem)),
            connections=sum(1 for it in items if isinstance(it, ConnectionItem)),
        )
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
            ep = getattr(n, "effect_params", None)
            if ep is not None:
                entry["effect_params"] = ep.to_dict()
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
            # IN / OUT are not user-created so they don't live in
            # ``nodes_data``, but the user may have dragged them — save
            # their positions separately so they survive a reload.
            "io_positions": {
                "IN":  [float(self._in_node.scenePos().x()),
                        float(self._in_node.scenePos().y())],
                "OUT": [float(self._out_node.scenePos().x()),
                        float(self._out_node.scenePos().y())],
            },
        }

    def load_from_data(self, data: dict) -> None:
        """Restore from a previous ``to_data`` snapshot. Clears any
        existing user-added nodes (IN / OUT stay)."""
        _record_node_action(
            "load_from_data",
            nodes=len(data.get("nodes", []) or []),
            connections=len(data.get("connections", []) or []),
        )
        self._discard_dragging_connection()
        # Wipe current nodes + connections (but keep IN / OUT).
        for c in list(self._connections):
            self.remove_connection(c)
        for n in list(self._serial_nodes):
            self.removeItem(n)
        self._serial_nodes.clear()
        self._connections.clear()
        self._next_id_counter = int(data.get("next_id", 1))

        # Restore IN / OUT positions if the snapshot has them. Older
        # snapshots predate this field — fall back to the defaults set
        # in __init__.
        io_pos = data.get("io_positions") or {}
        if "IN" in io_pos:
            try:
                ix, iy = io_pos["IN"]
                self._in_node.setPos(float(ix), float(iy))
            except Exception:
                pass
        if "OUT" in io_pos:
            try:
                ox, oy = io_pos["OUT"]
                self._out_node.setPos(float(ox), float(oy))
            except Exception:
                pass

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
            elif _is_registered_effect_kind(kind):
                from app.workbench.node_graph.items.effect_node_item import EffectNodeItem
                from app.effect_node_params import params_from_dict
                node = EffectNodeItem(effect_kind=kind, node_id=nd["id"],
                                      label=nd.get("label", ""))
                node.setPos(pos)
                self.addItem(node)
                self._serial_nodes.append(node)
                ep_data = nd.get("effect_params")
                if ep_data:
                    try:
                        node.effect_params = params_from_dict(ep_data)
                    except Exception:
                        pass
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

    def evaluate_chain_nodes_to(self, target) -> list:
        """Walk the connected RGB IN→target path and return the upstream
        node items in IN→target order. ``target`` itself is excluded
        when it's the OUT IO node (OUT only exists to terminate the
        chain), and excluded when ``target is _in_node`` (no upstream).
        Otherwise ``target`` is included so a per-node thumbnail can
        show the cumulative result "up to and including this node".

        Bypassed nodes ARE returned — callers (specifically
        ``_apply_node_effect_player``) skip them themselves, which
        keeps the bypass semantics in one place.
        """
        if target is None:
            return []
        chain_nodes: list = []
        cur = target
        seen: set[int] = set()
        while True:
            if cur is None or id(cur) in seen:
                break
            seen.add(id(cur))
            if isinstance(cur, IONodeItem) and cur.kind == "IN":
                break
            # Drop the OUT IO node itself — it has no effect, it's
            # purely a terminator.
            if not (isinstance(cur, IONodeItem) and cur.kind == "OUT"):
                chain_nodes.append(cur)
            in_port = getattr(cur, "rgb_in", None)
            if in_port is None or not in_port.connections:
                break
            up_conn = in_port.connections[0]
            cur = up_conn.source.parentItem()
        chain_nodes.reverse()
        return chain_nodes

    def evaluate_chain_to(self, target) -> list:
        """Legacy: returns ``ColorGrade`` instances only (for callers
        that haven't been migrated to the full effect-aware
        ``evaluate_chain_nodes_to`` + ``_apply_node_effect_player``).
        New code should prefer the nodes-based variant — it also
        applies effect_params and blur, not just colour grading."""
        from app.workbench.node_graph.items.node_item import NodeItem
        from app.workbench.node_graph.items.parallel_mixer import (
            ParallelMixerItem,
        )
        grades: list = []
        for n in self.evaluate_chain_nodes_to(target):
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


def _is_registered_effect_kind(kind: str) -> bool:
    try:
        from app.effect_node_params import _KIND_TO_CLASS

        return str(kind) in _KIND_TO_CLASS
    except Exception:
        return False
