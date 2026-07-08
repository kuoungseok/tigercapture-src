"""Domain slice of editing action adapter methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
from typing import Any

from app.actions.editor_adapter_scalars import _bool, _float, _int



class EditingCreativeActorAdapterMixin:
    """Focused action adapter methods split from EditingAdapterMixin."""

    def set_clip_filter(self, *, track_id: int, clip_id: int, params: Mapping[str, Any] | None = None, merge: bool = True) -> dict[str, Any]:
            _track, clip = self._video_track_and_clip(track_id, clip_id)
            payload = dict(params or {})
            if merge and getattr(clip, "video_filters", None) is not None:
                existing = getattr(clip.video_filters, "to_dict", lambda: dict(clip.video_filters))()
                existing.update(payload)
                payload = existing
            payload.setdefault("enabled", True)
            from app.video_filters import VideoFilterParams

            clip.video_filters = VideoFilterParams.from_dict(payload)
            self._after_timeline_mutation("Action set clip filter")
            return {"track_id": _int(track_id), "clip_id": _int(clip_id), "video_filters": clip.video_filters.to_dict()}

    def set_clip_color_grade(self, *, track_id: int, clip_id: int, grade: Mapping[str, Any] | None = None, merge: bool = True) -> dict[str, Any]:
            _track, clip = self._video_track_and_clip(track_id, clip_id)
            from app.color_grading import ColorGrade
            from app.timeline_model import ColorNode, NodeGraph

            current = {}
            ng = getattr(clip, "node_graph", None)
            if merge and ng is not None and getattr(getattr(ng, "color", None), "grade", None) is not None:
                current = ng.color.grade.to_dict()
            current.update(dict(grade or {}))
            new_grade = ColorGrade.from_dict(current)
            if ng is None or getattr(ng, "color", None) is None:
                clip.node_graph = NodeGraph(color=ColorNode(grade=new_grade))
            else:
                ng.color.grade = new_grade
            self._after_timeline_mutation("Action set clip color grade")
            return {"track_id": _int(track_id), "clip_id": _int(clip_id), "grade": new_grade.to_dict()}

    def set_clip_transition(
            self,
            *,
            track_id: int,
            clip_id: int,
            preset_id: str = "",
            transition_type: str = "",
            duration_ms: int = 500,
            side: str = "out",
        ) -> dict[str, Any]:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            self._assert_video_track_editable(track)
            side_text = str(side or "out").strip().lower()
            if side_text not in {"out", "end"}:
                raise ValueError("only out/end clip transitions are supported")

            old = {
                "transition_out_type": str(getattr(clip, "transition_out_type", "") or ""),
                "transition_out_ms": _int(getattr(clip, "transition_out_ms", 0), 0),
                "transition_preset_meta": dict(getattr(clip, "transition_preset_meta", {}) or {}),
            }
            transition_kind = str(transition_type or "").strip().lower()
            duration = max(1, _int(duration_ms, 500))
            preset_meta: dict[str, Any] = {}
            if preset_id:
                from app.preset_library import load_editor_presets

                preset = next(
                    (
                        row
                        for row in load_editor_presets()
                        if str(getattr(row, "id", "")) == str(preset_id) and str(getattr(row, "kind", "")) == "transition"
                    ),
                    None,
                )
                if preset is None:
                    raise ValueError(f"transition preset not found: {preset_id}")
                payload = dict(getattr(preset, "payload", {}) or {})
                transition_kind = str(payload.get("transition_out_type") or transition_kind or "dissolve").strip().lower()
                duration = max(1, _int(payload.get("transition_out_ms", duration), duration))
                preset_meta = {"preset_id": preset.id, "name": preset.name, "source": "python_action"}

            transition_kind = transition_kind or "dissolve"
            if transition_kind not in {"dissolve", "fade_black", "fade_white"}:
                raise ValueError(f"unsupported transition type: {transition_kind}")

            clip.transition_out_type = transition_kind
            clip.transition_out_ms = duration
            clip.transition_preset_meta = preset_meta or {
                "preset_id": "",
                "name": transition_kind.replace("_", " ").title(),
                "source": "python_action",
            }
            self._after_timeline_mutation("Action set clip transition")
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "side": "out",
                "before": old,
                "after": {
                    "transition_out_type": str(getattr(clip, "transition_out_type", "") or ""),
                    "transition_out_ms": _int(getattr(clip, "transition_out_ms", 0), 0),
                    "transition_preset_meta": dict(getattr(clip, "transition_preset_meta", {}) or {}),
                },
            }

    def clear_clip_transition(self, *, track_id: int, clip_id: int, side: str = "out") -> dict[str, Any]:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            self._assert_video_track_editable(track)
            side_text = str(side or "out").strip().lower()
            if side_text not in {"out", "end"}:
                raise ValueError("only out/end clip transitions are supported")
            old = {
                "transition_out_type": str(getattr(clip, "transition_out_type", "") or ""),
                "transition_out_ms": _int(getattr(clip, "transition_out_ms", 0), 0),
                "transition_preset_meta": dict(getattr(clip, "transition_preset_meta", {}) or {}),
            }
            clip.transition_out_type = ""
            clip.transition_out_ms = 0
            clip.transition_preset_meta = {}
            self._after_timeline_mutation("Action clear clip transition")
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "side": "out",
                "before": old,
                "after": {
                    "transition_out_type": "",
                    "transition_out_ms": 0,
                    "transition_preset_meta": {},
                },
            }

    def set_node_graph(self, *, track_id: int, graph: Mapping[str, Any] | None = None) -> dict[str, Any]:
            track = self._video_track(track_id)
            track.node_graph_view_data = dict(graph or self._default_node_graph_data())
            self._refresh_bound_node_graph_widget(track)
            self._after_timeline_mutation("Action set node graph")
            return {"track_id": _int(track_id), "node_count": len(track.node_graph_view_data.get("nodes", []) or [])}

    def add_node(
            self,
            *,
            track_id: int,
            kind: str = "serial",
            label: str = "",
            node_id: str = "",
            x: float | None = None,
            y: float | None = None,
            params: Mapping[str, Any] | None = None,
            auto_connect: bool = True,
        ) -> dict[str, Any]:
            track = self._video_track(track_id)
            graph = self._node_graph_data(track)
            nodes = list(graph.get("nodes") or [])
            next_id = max(1, _int(graph.get("next_id", 1), 1))
            prefix = {"blur": "B", "parallel": "P"}.get(str(kind or "serial"), "E" if str(kind or "") not in {"serial", "parallel", "blur"} else "N")
            nid = str(node_id or f"{prefix}{next_id}")
            graph["next_id"] = next_id + 1
            node = {
                "id": nid,
                "kind": str(kind or "serial"),
                "label": str(label or kind or "Node"),
                "x": _float(x, 0.0),
                "y": _float(y, 0.0),
                "bypassed": False,
                "user_color": None,
                "masks": [],
            }
            if params:
                if node["kind"] == "blur":
                    node["blur_params"] = dict(params)
                else:
                    payload = dict(params)
                    payload.setdefault("kind", node["kind"])
                    node["effect_params"] = payload
            nodes.append(node)
            graph["nodes"] = nodes
            if auto_connect:
                self._auto_connect_node(graph, nid)
            track.node_graph_view_data = graph
            self._refresh_bound_node_graph_widget(track)
            self._after_timeline_mutation("Action add node")
            return {"track_id": _int(track_id), "node_id": nid, "kind": node["kind"], "node_count": len(nodes)}

    def connect_node(
            self,
            *,
            track_id: int,
            src_node: str,
            dst_node: str,
            src_port: str = "rgb_out",
            dst_port: str = "rgb_in",
        ) -> dict[str, Any]:
            track = self._video_track(track_id)
            graph = self._node_graph_data(track)
            conns = [
                row for row in list(graph.get("connections") or [])
                if not (str(row.get("dst_node")) == str(dst_node) and str(row.get("dst_port")) == str(dst_port))
            ]
            conns.append({
                "src_node": str(src_node),
                "src_port": str(src_port or "rgb_out"),
                "dst_node": str(dst_node),
                "dst_port": str(dst_port or "rgb_in"),
            })
            graph["connections"] = conns
            track.node_graph_view_data = graph
            self._refresh_bound_node_graph_widget(track)
            self._after_timeline_mutation("Action connect node")
            return {"track_id": _int(track_id), "connection_count": len(conns)}

    def set_node_param(self, *, track_id: int, node_id: str, params: Mapping[str, Any] | None = None, merge: bool = True) -> dict[str, Any]:
            track = self._video_track(track_id)
            graph = self._node_graph_data(track)
            created = False
            try:
                node = self._node_in_graph(graph, node_id)
            except ValueError:
                if not self._owner_uses_legacy_video_editor_tracks():
                    raise
                node = {
                    "id": str(node_id),
                    "kind": str((params or {}).get("kind") or "serial"),
                    "label": str((params or {}).get("label") or node_id or "Node"),
                    "x": _float((params or {}).get("x"), 0.0),
                    "y": _float((params or {}).get("y"), 0.0),
                    "bypassed": False,
                    "user_color": None,
                    "masks": [],
                }
                nodes = list(graph.get("nodes") or [])
                nodes.append(node)
                graph["nodes"] = nodes
                self._auto_connect_node(graph, str(node_id))
                created = True
            key = "blur_params" if str(node.get("kind")) == "blur" else "effect_params"
            payload = dict(node.get(key) or {}) if merge else {}
            payload.update(dict(params or {}))
            if key == "effect_params":
                payload.setdefault("kind", str(node.get("kind") or "serial"))
            node[key] = payload
            track.node_graph_view_data = graph
            self._refresh_bound_node_graph_widget(track)
            self._after_timeline_mutation("Action set node param")
            return {"track_id": _int(track_id), "node_id": str(node_id), "params": payload, "created": created}

    def delete_node(self, *, track_id: int, node_id: str, reconnect: bool = True) -> dict[str, Any]:
            track = self._video_track(track_id)
            graph = self._node_graph_data(track)
            nodes = list(graph.get("nodes") or [])
            before = len(nodes)
            graph["nodes"] = [row for row in nodes if str(row.get("id")) != str(node_id)]
            graph["connections"] = [
                row for row in list(graph.get("connections") or [])
                if str(row.get("src_node")) != str(node_id) and str(row.get("dst_node")) != str(node_id)
            ]
            if reconnect and not graph["connections"]:
                graph["connections"] = [self._default_connection()]
            track.node_graph_view_data = graph
            self._refresh_bound_node_graph_widget(track)
            self._after_timeline_mutation("Action delete node")
            return {"track_id": _int(track_id), "node_id": str(node_id), "node_count_before": before, "node_count_after": len(graph["nodes"])}

    def add_text(
            self,
            *,
            track_id: int,
            clip_id: int,
            text: str,
            start_ms: int = 0,
            end_ms: int = 2000,
            style: Mapping[str, Any] | None = None,
            animation: Mapping[str, Any] | None = None,
        ) -> dict[str, Any]:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            from app.typography import AnimationConfig, TextClip, TextStyle

            style_obj = TextStyle()
            for key, value in dict(style or {}).items():
                if hasattr(style_obj, key):
                    setattr(style_obj, key, value)
            anim_obj = AnimationConfig()
            for key, value in dict(animation or {}).items():
                if hasattr(anim_obj, key):
                    setattr(anim_obj, key, value)
            start = max(0, _int(start_ms))
            end = max(start + 1, _int(end_ms, start + 2000))
            actor = TextClip(start_ms=start, end_ms=end, text=str(text or ""), style=style_obj, animation=anim_obj)
            actors = list(getattr(clip, "typography_actors", []) or [])
            actors.append(actor)
            actors.sort(key=lambda row: _int(getattr(row, "start_ms", 0)))
            clip.typography_actors = actors
            track_actors = list(getattr(track, "typography_actors", []) or [])
            actor_id = _int(getattr(actor, "id", -2), -2)
            if not any(_int(getattr(row, "id", -1), -1) == actor_id for row in track_actors):
                track_actors.append(actor)
                track_actors.sort(key=lambda row: _int(getattr(row, "start_ms", 0)))
                try:
                    track.typography_actors = track_actors
                except Exception:
                    pass
            owner = self._require_owner()
            rows = getattr(owner, "_track_rows", {}) if hasattr(owner, "_track_rows") else {}
            row = rows.get(_int(getattr(track, "id", track_id), track_id))
            if row is not None and hasattr(row, "update"):
                row.update()
            overlay = getattr(owner, "_update_text_clip_overlay", None)
            player = getattr(owner, "_player", None)
            position = getattr(player, "position", None)
            if callable(overlay):
                try:
                    overlay(_int(position() if callable(position) else 0))
                except Exception:
                    pass
            self._after_timeline_mutation("Action add text")
            return {"track_id": _int(track_id), "clip_id": _int(clip_id), "text_id": _int(getattr(actor, "id", 0)), "start_ms": start, "end_ms": end}

    def set_text_keyframes(self, *, track_id: int, clip_id: int, text_id: int, keyframes: Mapping[str, Any] | None = None) -> dict[str, Any]:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            actor = self._text_actor(clip, text_id)
            payload = dict(keyframes or {})
            setattr(actor, "keyframes", payload)
            animation = getattr(actor, "animation", None)
            if animation is not None and hasattr(animation, "custom_params"):
                custom = dict(getattr(animation, "custom_params", {}) or {})
                custom["action_keyframes"] = payload
                animation.custom_params = custom
            owner = self._require_owner()
            rows = getattr(owner, "_track_rows", {}) if hasattr(owner, "_track_rows") else {}
            row = rows.get(_int(getattr(track, "id", track_id), track_id))
            if row is not None and hasattr(row, "update"):
                row.update()
            overlay = getattr(owner, "_update_text_clip_overlay", None)
            player = getattr(owner, "_player", None)
            position = getattr(player, "position", None)
            if callable(overlay):
                try:
                    overlay(_int(position() if callable(position) else 0))
                except Exception:
                    pass
            self._after_timeline_mutation("Action set text keyframes")
            return {"track_id": _int(track_id), "clip_id": _int(clip_id), "text_id": _int(text_id), "keyframes": payload}

    def add_actor(self, *, kind: str, path: str, track_id: int | None = None, **params: Any) -> dict[str, Any]:
            owner = self._require_owner()
            kind_text = str(kind or "").strip().lower()
            if kind_text not in {"live2d", "spine"}:
                raise ValueError("kind must be live2d or spine")
            media_path = Path(str(path or "")).expanduser()
            if not media_path.is_file():
                raise ValueError(f"actor path does not exist: {media_path}")
            attr = "_live2d_actor_tracks" if kind_text == "live2d" else "_spine_actor_tracks"
            tracks = list(getattr(owner, attr, []) or [])
            track = next((row for row in tracks if _int(getattr(row, "id", -1), -1) == _int(track_id, -2)), None) if track_id is not None else (tracks[0] if tracks else None)
            if track is None:
                if kind_text == "live2d":
                    from app.live2d.actor_track import Live2DActorTrack

                    track = Live2DActorTrack(id=self._next_track_id(tracks), label=str(params.get("label") or "Live2D"))
                else:
                    from app.spine_editor.actor_track import SpineActorTrack

                    track = SpineActorTrack(id=self._next_track_id(tracks), label=str(params.get("label") or "Spine"))
                tracks.append(track)
                setattr(owner, attr, tracks)
                insert = getattr(owner, "_insert_live2d_actor_lane" if kind_text == "live2d" else "_insert_spine_actor_lane", None)
                if callable(insert):
                    insert(track)
            start = max(0, _int(params.get("start_ms", 0)))
            duration = max(1, _int(params.get("duration_ms", 3000), 3000))
            if kind_text == "live2d":
                from app.live2d.actor_track import Live2DActorClip

                clip = Live2DActorClip(
                    model_path=str(media_path.resolve()),
                    start_ms=start,
                    duration_ms=duration,
                    pos_x=_float(params.get("pos_x", 0.5), 0.5),
                    pos_y=_float(params.get("pos_y", 0.5), 0.5),
                    scale=_float(params.get("scale", 1.0), 1.0),
                    opacity=_float(params.get("opacity", 1.0), 1.0),
                )
            else:
                from app.spine_editor.actor_track import SpineActorClip

                clip = SpineActorClip(
                    skel_path=str(media_path.resolve()),
                    atlas_path=str(params.get("atlas_path") or ""),
                    texture_path=str(params.get("texture_path") or ""),
                    anim_name=str(params.get("anim_name") or ""),
                    skin_name=str(params.get("skin_name") or "default"),
                    start_ms=start,
                    duration_ms=duration,
                    pos_x=_float(params.get("pos_x", 0.5), 0.5),
                    pos_y=_float(params.get("pos_y", 0.5), 0.5),
                    scale=_float(params.get("scale", 1.0), 1.0),
                )
            track.clips.append(clip)
            track.clips.sort(key=lambda row: _int(getattr(row, "start_ms", 0)))
            self._sync_actor_tracks(kind_text)
            self._after_timeline_mutation(f"Action add {kind_text} actor")
            return {"kind": kind_text, "track_id": _int(getattr(track, "id", 0)), "clip_index": track.clips.index(clip), "start_ms": start, "duration_ms": duration}

    def set_actor_transform(self, *, kind: str, track_id: int, clip_index: int = 0, **params: Any) -> dict[str, Any]:
            kind_text = str(kind or "").strip().lower()
            track, clip = self._actor_track_and_clip(kind_text, track_id, clip_index)
            changed: dict[str, Any] = {}
            for key in ("start_ms", "duration_ms", "pos_x", "pos_y", "scale", "opacity"):
                if key not in params or not hasattr(clip, key):
                    continue
                value = _int(params[key]) if key in {"start_ms", "duration_ms"} else _float(params[key], _float(getattr(clip, key, 0.0)))
                if key == "duration_ms":
                    value = max(1, value)
                setattr(clip, key, value)
                changed[key] = value
            track.clips.sort(key=lambda row: _int(getattr(row, "start_ms", 0)))
            self._sync_actor_tracks(kind_text)
            self._after_timeline_mutation(f"Action set {kind_text} actor transform")
            return {"kind": kind_text, "track_id": _int(track_id), "clip_index": _int(clip_index), "changed": changed}

    def set_actor_keyframes(self, *, kind: str, track_id: int, clip_index: int = 0, keyframes: Mapping[str, Any] | None = None) -> dict[str, Any]:
            kind_text = str(kind or "").strip().lower()
            _track, clip = self._actor_track_and_clip(kind_text, track_id, clip_index)
            payload = dict(keyframes or {})
            if kind_text == "live2d":
                from app.live2d.actor_track import Live2DKeyframe

                mapping = {"pos_x": "kf_pos_x", "pos_y": "kf_pos_y", "scale": "kf_scale", "opacity": "kf_opacity"}
                for prop, attr in mapping.items():
                    if prop not in payload:
                        continue
                    setattr(
                        clip,
                        attr,
                        [
                            Live2DKeyframe(
                                time_ms=max(0, _int(row.get("time_ms", row.get("ms", 0)) if isinstance(row, Mapping) else 0)),
                                value=_float(row.get("value", 0.0) if isinstance(row, Mapping) else 0.0),
                                curve=str(row.get("curve", "linear") if isinstance(row, Mapping) else "linear"),
                            )
                            for row in list(payload.get(prop) or [])
                        ],
                    )
            setattr(clip, "action_keyframes", payload)
            self._sync_actor_tracks(kind_text)
            self._after_timeline_mutation(f"Action set {kind_text} actor keyframes")
            return {"kind": kind_text, "track_id": _int(track_id), "clip_index": _int(clip_index), "keyframes": payload}

    def apply_live2d_performance_source(
            self,
            *,
            track_id: int,
            clip_index: int = 0,
            time_ms: int | None = None,
            source_path: str = "",
            mocap_frames: Sequence[Any] | None = None,
            mocap_payload: Mapping[str, Any] | None = None,
            framing_payload: Mapping[str, Any] | None = None,
            framing_control: Mapping[str, Any] | None = None,
            preset: str = "bust_up",
            analyze_video: bool = True,
            sample_fps: float = 12.0,
            max_samples: int = 1800,
            fit_duration: bool = True,
            apply_mocap: bool = True,
            apply_framing: bool = True,
            replace_transform: bool = True,
        ) -> dict[str, Any]:
            """Apply an input-only Performance Source to a Live2D actor clip.

            The performance source may be a webcam/video/capture track used only for
            tracking. This action never makes that source a Program Output layer.
            """
            owner = self._require_owner()
            _track, clip = self._actor_track_and_clip("live2d", track_id, clip_index)
            target_ms = (
                max(0, _int(time_ms))
                if time_ms is not None
                else max(0, _int(getattr(clip, "start_ms", 0), 0) or self._current_playhead_ms())
            )
            active_source: dict[str, Any] = {}
            try:
                from app.vtuber.performance_source import active_performance_source_at

                active_source = active_performance_source_at(getattr(owner, "_tracks", []) or [], target_ms)
            except Exception:
                active_source = {"active": False, "source_path": "", "clip": None, "program_output": False}

            source_clip = active_source.get("clip") if isinstance(active_source, Mapping) else None
            resolved_source = str(source_path or "")
            if not resolved_source and isinstance(active_source, Mapping):
                resolved_source = str(active_source.get("source_path") or "")

            resolved_mocap_payload: Mapping[str, Any] | None = dict(mocap_payload or {}) if isinstance(mocap_payload, Mapping) else None
            if resolved_mocap_payload is None:
                resolved_mocap_payload = self._first_mapping_from_object(
                    source_clip,
                    ("live2d_mocap_payload", "mocap_payload", "tracking_mocap_payload"),
                )
            resolved_framing_payload: Mapping[str, Any] | None = (
                dict(framing_payload or {})
                if isinstance(framing_payload, Mapping)
                else (dict(framing_control or {}) if isinstance(framing_control, Mapping) else None)
            )
            if resolved_framing_payload is None:
                resolved_framing_payload = self._first_mapping_from_object(
                    source_clip,
                    (
                        "source_framing_payload",
                        "source_framing_control",
                        "performance_source_framing_payload",
                        "framing_payload",
                        "framing_control",
                    ),
                )

            mocap_result: dict[str, Any] = {"ok": False, "skipped": True}
            framing_result: dict[str, Any] = {"ok": False, "skipped": True}
            alias_result: dict[str, Any] = {"ok": False, "skipped": True}
            subject_type = ""
            warnings: list[str] = []

            if bool(apply_mocap):
                if resolved_mocap_payload is None and isinstance(mocap_frames, Sequence) and not isinstance(mocap_frames, (str, bytes, bytearray)):
                    from app.actor_mocap import live2d_mocap_payload_from_frames

                    resolved_mocap_payload = live2d_mocap_payload_from_frames(
                        list(mocap_frames),
                        source_path=resolved_source,
                        duration_ms=max(1, _int(getattr(clip, "duration_ms", 0), 3000)),
                    )
                if resolved_mocap_payload is None and bool(analyze_video) and resolved_source:
                    path = Path(resolved_source).expanduser()
                    if path.is_file():
                        from app.actor_mocap import analyze_video_file_for_live2d_mocap

                        resolved_mocap_payload = analyze_video_file_for_live2d_mocap(
                            path,
                            sample_fps=max(1.0, _float(sample_fps, 12.0)),
                            max_samples=max(1, _int(max_samples, 1800)),
                        )
                    else:
                        warnings.append(f"performance source video not found: {path}")
                if resolved_mocap_payload is not None:
                    from app.actor_mocap import apply_live2d_mocap_payload_to_clip
                    from app.live2d.performance_source_bridge import (
                        apply_live2d_parameter_aliases_to_clip,
                        normalize_performance_subject_type,
                    )

                    mocap_result = apply_live2d_mocap_payload_to_clip(
                        clip,
                        resolved_mocap_payload,
                        fit_duration=bool(fit_duration),
                    )
                    retargeting = dict(resolved_mocap_payload.get("retargeting") or {})
                    constraints = dict(retargeting.get("movement_constraints") or {})
                    subject_type = (
                        normalize_performance_subject_type(mocap_result.get("shot_profile"))
                        or normalize_performance_subject_type(retargeting.get("shot_profile"))
                        or normalize_performance_subject_type(resolved_mocap_payload.get("subject_type"))
                        or "unknown"
                    )
                    try:
                        clip.mocap_subject_type = subject_type
                        clip.mocap_movement_constraints = constraints
                    except Exception:
                        pass
                    if bool(mocap_result.get("ok")):
                        alias_result = apply_live2d_parameter_aliases_to_clip(clip)
                        mocap_result["subject_type"] = subject_type
                        mocap_result["movement_constraints"] = constraints
                        mocap_result["parameter_aliases"] = {
                            "aliases_added": dict(alias_result.get("aliases_added") or {}),
                            "alias_count": int(alias_result.get("alias_count", 0) or 0),
                        }
                    if not bool(mocap_result.get("ok")):
                        warnings.append(f"mocap not applied: {mocap_result.get('reason') or 'invalid payload'}")

            if bool(apply_framing) and resolved_framing_payload is not None:
                from app.live2d.performance_source_bridge import (
                    apply_performance_source_framing_to_clip,
                    normalize_performance_subject_type,
                )

                framing_subject_type = (
                    (normalize_performance_subject_type(subject_type) if subject_type else "")
                    or normalize_performance_subject_type(resolved_framing_payload.get("subject_type"))
                    or "unknown"
                )

                framing_result = apply_performance_source_framing_to_clip(
                    clip,
                    resolved_framing_payload,
                    source_path=resolved_source,
                    preset=str(preset or "bust_up"),
                    replace_transform=bool(replace_transform),
                    subject_type=framing_subject_type,
                )
                if not bool(framing_result.get("ok")):
                    warnings.append(f"framing not applied: {framing_result.get('reason') or 'invalid payload'}")

            changed = bool(mocap_result.get("ok") or framing_result.get("ok"))
            if not changed:
                raise ValueError("no Live2D mocap or framing payload could be applied")

            self._sync_actor_tracks("live2d")
            self._after_timeline_mutation("Apply Live2D Performance Source")
            return {
                "kind": "live2d",
                "track_id": _int(track_id),
                "clip_index": _int(clip_index),
                "time_ms": target_ms,
                "source_path": resolved_source,
                "active_performance_source": {
                    "active": bool(active_source.get("active")) if isinstance(active_source, Mapping) else False,
                    "program_output": False,
                },
                "program_output": False,
                "mocap": mocap_result,
                "framing": framing_result,
                "parameter_aliases": alias_result,
                "subject_type": subject_type or str(framing_result.get("subject_type") or "unknown"),
                "warnings": warnings,
            }
