"""Private actor, text, node-graph, and editor refresh helper methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class ObjectHelperMixin:
    """Private helpers for creative objects and editor refresh operations."""

    def _text_actor(self, clip: Any, text_id: int) -> Any:
        target = _int(text_id)
        for actor in getattr(clip, "typography_actors", []) or []:
            if _int(getattr(actor, "id", -1), -1) == target:
                return actor
        raise ValueError(f"text actor not found: {target}")

    def _first_mapping_from_object(self, obj: Any, names: Sequence[str]) -> dict[str, Any] | None:
        if obj is None:
            return None
        for name in names:
            value = obj.get(name) if isinstance(obj, Mapping) else getattr(obj, name, None)
            if isinstance(value, Mapping) and value:
                return dict(value)
        return None

    def _actor_track_and_clip(self, kind: str, track_id: int, clip_index: int = 0) -> tuple[Any, Any]:
        if kind not in {"live2d", "spine"}:
            raise ValueError("kind must be live2d or spine")
        attr = "_live2d_actor_tracks" if kind == "live2d" else "_spine_actor_tracks"
        target = _int(track_id)
        for track in getattr(self._require_owner(), attr, []) or []:
            if _int(getattr(track, "id", -1), -1) != target:
                continue
            clips = list(getattr(track, "clips", []) or [])
            idx = max(0, _int(clip_index))
            if idx >= len(clips):
                raise ValueError(f"actor clip index out of range: {idx}")
            return track, clips[idx]
        raise ValueError(f"{kind} actor track not found: {target}")

    def _next_clip_id(self, track: Any) -> int:
        owner = self._require_owner()
        ids: list[int] = []
        for lane in getattr(owner, "_tracks", []) or []:
            for clip in getattr(lane, "clips", []) or []:
                ids.append(_int(getattr(clip, "id", 0)))
        for clip in getattr(track, "clips", []) or []:
            ids.append(_int(getattr(clip, "id", 0)))
        return max(ids, default=0) + 1

    def _next_audio_clip_id(self) -> int:
        owner = self._require_owner()
        method = getattr(owner, "_next_clip_id", None)
        if callable(method):
            try:
                return _int(method())
            except Exception:
                pass
        ids: list[int] = []
        for lane in getattr(owner, "_audio_tracks", []) or []:
            for clip in getattr(lane, "clips", []) or []:
                ids.append(_int(getattr(clip, "id", 0)))
        return max(ids, default=0) + 1

    def _next_track_id(self, tracks: list[Any]) -> int:
        ids = [_int(getattr(track, "id", 0)) for track in tracks]
        owner_next = _int(getattr(self.owner, "_next_track_id", 0), 0)
        max_existing = max(ids, default=0)
        if owner_next > max_existing:
            return owner_next
        return max_existing + 1

    def _update_audio_track(self, track: Any) -> None:
        mixer = getattr(self.owner, "_audio_mixer", None)
        update = getattr(mixer, "update_track", None)
        if callable(update):
            update(track)
        tid = getattr(track, "id", None)
        panel = getattr(self.owner, "_audio_mixer_panel", None)
        if panel is not None:
            for name, value in (
                ("sync_track_volume", getattr(track, "volume", 1.0)),
                ("sync_track_pan", getattr(track, "pan", 0.0)),
                ("sync_track_mute", bool(getattr(track, "muted", False))),
                ("sync_track_solo", bool(getattr(track, "solo", False))),
            ):
                method = getattr(panel, name, None)
                if callable(method):
                    try:
                        method(tid, value)
                    except Exception:
                        pass
        rows = getattr(self.owner, "_audio_rows", None)
        row = rows.get(tid) if isinstance(rows, dict) else None
        refresh = getattr(row, "refresh_from_track", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass

    def _sync_actor_tracks(self, kind: str) -> None:
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        if player is None:
            return
        if kind == "live2d":
            method = getattr(player, "set_live2d_actor_tracks", None)
            tracks = getattr(owner, "_live2d_actor_tracks", []) or []
        else:
            method = getattr(player, "set_spine_actor_tracks", None)
            tracks = getattr(owner, "_spine_actor_tracks", []) or []
        if callable(method):
            method(tracks)

    def _refresh_workbench(self) -> None:
        method = getattr(self.owner, "_refresh_workbench", None)
        if callable(method):
            method()

    def _refresh_bound_node_graph_widget(self, track: Any) -> None:
        owner = self.owner
        if owner is None or track is None:
            return
        panel = getattr(owner, "_workbench_panel", None)
        graph_widget = None
        expose = getattr(panel, "expose_node_graph_widget", None)
        if callable(expose):
            try:
                graph_widget = expose()
            except Exception:
                graph_widget = None
        if graph_widget is None or getattr(graph_widget, "_track", None) is not track:
            return
        scene = getattr(graph_widget, "scene", None)
        loader = getattr(scene, "load_from_data", None)
        if not callable(loader):
            return
        old_suspend = bool(getattr(graph_widget, "_suspend_persist", False))
        try:
            graph_widget._suspend_persist = True
            loader(getattr(track, "node_graph_view_data", None) or self._default_node_graph_data())
        finally:
            graph_widget._suspend_persist = old_suspend
        refresh_count = getattr(graph_widget, "_refresh_count", None)
        if callable(refresh_count):
            try:
                refresh_count()
            except Exception:
                pass
        minimap = getattr(graph_widget, "minimap", None)
        refresh_minimap = getattr(minimap, "refresh", None)
        if callable(refresh_minimap):
            try:
                refresh_minimap()
            except Exception:
                pass

    def _default_connection(self) -> dict[str, str]:
        return {"src_node": "IN", "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"}

    def _default_node_graph_data(self) -> dict[str, Any]:
        return {
            "nodes": [],
            "connections": [self._default_connection()],
            "next_id": 1,
            "io_positions": {"IN": [-320.0, -18.0], "OUT": [320.0, -18.0]},
        }

    def _node_graph_data(self, track: Any) -> dict[str, Any]:
        data = getattr(track, "node_graph_view_data", None)
        if not isinstance(data, Mapping):
            return self._default_node_graph_data()
        out = dict(data)
        out["nodes"] = [dict(row) for row in list(out.get("nodes") or []) if isinstance(row, Mapping)]
        out["connections"] = [
            dict(row) for row in list(out.get("connections") or []) if isinstance(row, Mapping)
        ] or [self._default_connection()]
        out["next_id"] = max(1, _int(out.get("next_id", 1), 1))
        out.setdefault("io_positions", {"IN": [-320.0, -18.0], "OUT": [320.0, -18.0]})
        return out

    def _node_in_graph(self, graph: dict[str, Any], node_id: str) -> dict[str, Any]:
        target = str(node_id)
        for node in graph.get("nodes", []) or []:
            if str(node.get("id")) == target:
                return node
        raise ValueError(f"node not found: {target}")

    def _auto_connect_node(self, graph: dict[str, Any], node_id: str) -> None:
        conns = [dict(row) for row in list(graph.get("connections") or []) if isinstance(row, Mapping)]
        if not conns:
            graph["connections"] = [
                {"src_node": "IN", "src_port": "rgb_out", "dst_node": node_id, "dst_port": "rgb_in"},
                {"src_node": node_id, "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"},
            ]
            return
        out_conn = next((row for row in conns if str(row.get("dst_node")) == "OUT"), None)
        if out_conn is None:
            conns.append({"src_node": node_id, "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"})
        else:
            conns.remove(out_conn)
            conns.append({
                "src_node": str(out_conn.get("src_node", "IN")),
                "src_port": str(out_conn.get("src_port", "rgb_out")),
                "dst_node": node_id,
                "dst_port": "rgb_in",
            })
            conns.append({"src_node": node_id, "src_port": "rgb_out", "dst_node": "OUT", "dst_port": "rgb_in"})
        graph["connections"] = conns

    def _after_timeline_mutation(self, label: str) -> None:
        self._refresh_tracks()
        self._register_change(label)

    def _register_change(self, label: str) -> None:
        method = getattr(self.owner, "_register_change", None)
        if callable(method):
            method(str(label or "Python action"))

    def _refresh_tracks(self) -> None:
        method = getattr(self.owner, "_refresh_player_tracks", None)
        if callable(method):
            method()
        width = getattr(self.owner, "_update_tracks_host_width", None)
        if callable(width):
            width()
