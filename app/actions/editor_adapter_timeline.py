"""Timeline, media, source/record, marker, and selection adapter methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return bool(default)


class TimelineAdapterMixin:
    """Registered timeline/media/source-monitor action adapter methods."""

    def timeline_summary(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        tracks: list[dict[str, Any]] = []
        for kind, key in (("video", "video_tracks"), ("audio", "audio_tracks")):
            for track in snapshot.get(key) or []:
                starts: list[int] = []
                ends: list[int] = []
                for clip in track.get("clips") or []:
                    starts.append(_int(clip.get("timeline_in_ms", clip.get("offset_ms", 0))))
                    ends.append(_int(clip.get("timeline_out_ms", clip.get("end_ms", 0))))
                tracks.append(
                    {
                        "kind": kind,
                        "id": track.get("id"),
                        "index": track.get("index"),
                        "locked": bool(track.get("locked")),
                        "muted": bool(track.get("muted")),
                        "clip_count": len(track.get("clips") or []),
                        "start_ms": min(starts) if starts else 0,
                        "end_ms": max(ends) if ends else 0,
                    }
                )
        return {
            "duration_ms": _int(snapshot.get("duration_ms", 0)),
            "current_position_ms": _int(snapshot.get("current_position_ms", 0)),
            "markers": list(snapshot.get("markers") or []),
            "summary": snapshot.get("summary", {}),
            "tracks": tracks,
            "snapshot_hash": snapshot.get("snapshot_hash", ""),
        }

    def preset_catalog(self, *, kind: str = "", query: str = "", limit: int = 120) -> dict[str, Any]:
        from app.preset_library import load_editor_presets, preset_library_summary, search_presets

        limit = max(1, min(500, int(limit or 120)))
        total_presets = load_editor_presets()
        if query:
            rows = [preset.to_dict() for preset in search_presets(query, kind=kind or None)[:limit]]
        else:
            presets = list(total_presets)
            if kind:
                presets = [preset for preset in presets if str(preset.kind) == str(kind)]
            rows = [preset.to_dict() for preset in presets[:limit]]
        total = len([preset for preset in total_presets if not kind or str(preset.kind) == str(kind)])
        return {
            "returned": len(rows),
            "total": total,
            "count": len(rows),
            "presets": rows,
            "summary": preset_library_summary(),
        }

    def selected_clip(self) -> dict[str, Any]:
        selection_state = self.selection_summary()
        snapshot = self.snapshot()
        selected = list(selection_state.get("selection") or [])
        if not selected:
            return {"selected": None, "selection": None, "selection_state": selection_state}
        first = selected[0]
        clip_id = _int(first.get("clip_id", -1), -1) if isinstance(first, Mapping) else -1
        wanted_kind = str(first.get("track_kind") or "video") if isinstance(first, Mapping) else "video"
        for key in ("video_tracks", "audio_tracks"):
            key_kind = "video" if key == "video_tracks" else "audio"
            if wanted_kind not in {"", key_kind}:
                continue
            for track in snapshot.get(key) or []:
                if _int(track.get("id", -1), -1) != _int(first.get("track_id", -2), -2):
                    continue
                for clip in track.get("clips") or []:
                    if _int(clip.get("id", -2), -2) == clip_id:
                        row = dict(clip)
                        row["track_id"] = track.get("id")
                        row["track_kind"] = key_kind
                        return {"selected": row, "selection": first, "selection_state": selection_state}
        return {"selected": None, "selection": first, "selection_state": selection_state}

    def import_media(self, path: str, *, target: str = "") -> dict[str, Any]:
        owner = self._require_owner()
        media_path = Path(str(path or "")).expanduser()
        if not media_path.is_file():
            raise ValueError(f"media path does not exist: {media_path}")
        pool = getattr(owner, "_media_pool", None)
        added = False
        if pool is not None and hasattr(pool, "add_path"):
            added = bool(pool.add_path(media_path))
        else:
            imported = list(getattr(owner, "_action_imported_media", []) or [])
            text = str(media_path.resolve())
            if text not in imported:
                imported.append(text)
                added = True
            setattr(owner, "_action_imported_media", imported)
        self._register_change("Import media")
        return {"path": str(media_path.resolve()), "target": str(target or ""), "added": bool(added)}

    def add_track(self, *, kind: str = "video", name: str = "", track_id: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        attr = "_tracks" if kind_text == "video" else "_audio_tracks"
        tracks = list(getattr(owner, attr, []) or [])
        new_id = int(track_id) if track_id is not None else self._next_track_id(tracks)
        if kind_text == "video":
            if self._owner_uses_legacy_video_editor_tracks():
                from app.video_track_legacy import VideoTrack
            else:
                from app.timeline_model import VideoTrack

            track = VideoTrack(id=new_id)
        else:
            from app.audio_tracks import AudioTrack

            track = AudioTrack(id=new_id, label=str(name or f"Audio {new_id}"))
        if name and not hasattr(track, "name"):
            setattr(track, "name", str(name))
        tracks.append(track)
        setattr(owner, attr, tracks)
        if kind_text == "video" and self._owner_uses_legacy_video_editor_tracks():
            insert = getattr(owner, "_insert_track_widget", None)
            if callable(insert):
                insert(track)
            set_active = getattr(owner, "_set_active_track", None)
            if callable(set_active):
                set_active(new_id)
        self._refresh_tracks()
        self._register_change(f"Add {kind_text} track")
        return {"kind": kind_text, "track_id": new_id, "track_count": len(tracks)}

    def remove_track(self, *, kind: str = "video", track_id: int, force: bool = False) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        target = _int(track_id)
        attr = "_tracks" if kind_text == "video" else "_audio_tracks"
        tracks = list(getattr(owner, attr, []) or [])
        track = next((row for row in tracks if _int(getattr(row, "id", -1), -1) == target), None)
        if track is None:
            raise ValueError(f"{kind_text} track not found: {target}")
        if kind_text == "video" and bool(getattr(track, "locked", False)) and not force:
            raise ValueError(f"video track is locked: {target}")

        before = len(tracks)
        removed_clip_count = len(getattr(track, "clips", []) or [])
        method_name = "_delete_track" if kind_text == "video" else "_delete_audio_track"
        method = getattr(owner, method_name, None)
        if callable(method):
            method(target)
        else:
            setattr(owner, attr, [row for row in tracks if _int(getattr(row, "id", -1), -1) != target])
            if kind_text == "audio":
                mixer = getattr(owner, "_audio_mixer", None)
                remove = getattr(mixer, "remove_track", None)
                if callable(remove):
                    remove(target)
                panel = getattr(owner, "_audio_mixer_panel", None)
                is_visible = getattr(panel, "isVisible", None)
                rebuild = getattr(panel, "rebuild", None)
                if callable(is_visible) and is_visible() and callable(rebuild):
                    rebuild(getattr(owner, "_audio_tracks", []) or [])
            self._refresh_tracks()
        self._register_change(f"Remove {kind_text} track")
        after = len(getattr(owner, attr, []) or [])
        return {
            "kind": kind_text,
            "track_id": target,
            "track_count_before": before,
            "track_count_after": after,
            "removed_clip_count": removed_clip_count,
            "force": bool(force),
        }

    def set_playhead(self, ms: int) -> dict[str, Any]:
        owner = self._require_owner()
        value = max(0, _int(ms))
        player = getattr(owner, "_player", None)
        if player is not None and hasattr(player, "setPosition"):
            player.setPosition(value)
        elif player is not None and hasattr(player, "set_position"):
            player.set_position(value)
        else:
            setattr(owner, "_action_playhead_ms", value)
            if player is not None and hasattr(player, "position_ms"):
                try:
                    setattr(player, "position_ms", value)
                except Exception:
                    pass
        callback = getattr(owner, "_on_position_changed", None)
        if callable(callback):
            try:
                callback(value)
            except Exception:
                pass
        return {"ms": value}

    def transport(self, command: str, *, rate: float | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        command_text = str(command or "").strip().lower()
        if command_text not in {"play", "pause", "stop", "shuttle"}:
            raise ValueError("transport command must be play, pause, stop, or shuttle")
        player = getattr(owner, "_player", None)
        if player is None:
            state = {"command": command_text, "rate": rate, "mode": "recorded_no_player"}
            setattr(owner, "_action_transport", state)
            return state

        if command_text == "shuttle":
            value = _float(rate, 1.0)
            set_rate = getattr(player, "set_shuttle_rate", None)
            if callable(set_rate):
                set_rate(value)
            elif hasattr(player, "_shuttle_rate"):
                setattr(player, "_shuttle_rate", value)
            if value > 0.0:
                play = getattr(player, "play", None)
                if callable(play):
                    play()
            else:
                pause = getattr(player, "pause", None)
                if callable(pause):
                    pause()
            return {"command": command_text, "rate": value, "mode": "player"}

        method = getattr(player, command_text, None)
        if not callable(method):
            raise ValueError(f"player does not support {command_text}")
        method()
        return {"command": command_text, "mode": "player"}

    def step_frames(self, frames: int, *, fps: float = 30.0) -> dict[str, Any]:
        count = _int(frames, 0)
        fps_value = max(1.0, _float(fps, 30.0))
        delta_ms = int(round((count * 1000.0) / fps_value))
        current = self._current_playhead_ms()
        target = max(0, current + delta_ms)
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        duration = 0
        if player is not None:
            duration_attr = getattr(player, "duration", None)
            if callable(duration_attr):
                try:
                    duration = max(0, _int(duration_attr()))
                except Exception:
                    duration = 0
            elif duration_attr is not None:
                duration = max(0, _int(duration_attr))
        if duration > 0:
            target = min(target, duration)
        if player is not None:
            pause = getattr(player, "pause", None)
            if callable(pause):
                try:
                    pause()
                except Exception:
                    pass
        self.set_playhead(target)
        return {
            "frames": count,
            "fps": fps_value,
            "from_ms": current,
            "target_ms": target,
            "delta_ms": target - current,
        }

    def edit_points(
        self,
        *,
        track_kind: str = "video",
        track_id: int | None = None,
        include_markers: bool = False,
    ) -> dict[str, Any]:
        points = self._timeline_edit_points(
            track_kind=track_kind,
            track_id=track_id,
            include_markers=include_markers,
        )
        return {"points": points, "count": len(points), "track_kind": str(track_kind or "video"), "track_id": track_id}

    def jump_edit_point(
        self,
        *,
        direction: str = "next",
        from_ms: int | None = None,
        track_kind: str = "video",
        track_id: int | None = None,
        include_markers: bool = False,
        tolerance_ms: int = 1,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        direction_text = str(direction or "next").strip().lower()
        if direction_text in {"prev", "previous", "back", "left"}:
            direction_text = "previous"
        elif direction_text in {"next", "forward", "right"}:
            direction_text = "next"
        else:
            raise ValueError("direction must be next or previous")
        current = self._current_playhead_ms() if from_ms is None else max(0, _int(from_ms))
        tolerance = max(0, _int(tolerance_ms, 1))
        points = self._timeline_edit_points(
            track_kind=track_kind,
            track_id=track_id,
            include_markers=include_markers,
        )
        if direction_text == "next":
            candidates = [point for point in points if point > current + tolerance]
            target = min(candidates) if candidates else current
        else:
            candidates = [point for point in points if point < current - tolerance]
            target = max(candidates) if candidates else current
        moved = target != current
        if moved and not dry_run:
            self.set_playhead(target)
        return {
            "direction": direction_text,
            "from_ms": current,
            "target_ms": target,
            "moved": bool(moved),
            "point_count": len(points),
            "track_kind": str(track_kind or "video"),
            "track_id": track_id,
            "include_markers": bool(include_markers),
            "dry_run": bool(dry_run),
        }

    def in_out_range(self) -> dict[str, Any]:
        owner = self._require_owner()
        in_ms = _int(getattr(owner, "_global_in_ms", -1), -1)
        out_ms = _int(getattr(owner, "_global_out_ms", -1), -1)
        valid = in_ms >= 0 and out_ms >= 0 and out_ms >= in_ms
        return {
            "in_ms": in_ms,
            "out_ms": out_ms,
            "has_in": in_ms >= 0,
            "has_out": out_ms >= 0,
            "valid": bool(valid),
            "duration_ms": max(0, out_ms - in_ms) if valid else 0,
        }

    def set_in_out(self, *, in_ms: int | None = None, out_ms: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        before = self.in_out_range()
        if in_ms is not None:
            value = max(0, _int(in_ms))
            method = getattr(owner, "_set_global_in", None)
            if callable(method):
                method(value)
            else:
                setattr(owner, "_global_in_ms", value)
        if out_ms is not None:
            value = max(0, _int(out_ms))
            method = getattr(owner, "_set_global_out", None)
            if callable(method):
                method(value)
            else:
                setattr(owner, "_global_out_ms", value)
        if not callable(getattr(owner, "_set_global_in", None)) and not callable(getattr(owner, "_set_global_out", None)):
            current_in = _int(getattr(owner, "_global_in_ms", -1), -1)
            current_out = _int(getattr(owner, "_global_out_ms", -1), -1)
            if 0 <= current_out < current_in:
                if out_ms is None:
                    setattr(owner, "_global_out_ms", current_in)
                else:
                    setattr(owner, "_global_in_ms", current_out)
            ruler = getattr(owner, "_timeline_ruler", None)
            set_markers = getattr(ruler, "set_global_markers", None)
            if callable(set_markers):
                set_markers(_int(getattr(owner, "_global_in_ms", -1), -1), _int(getattr(owner, "_global_out_ms", -1), -1))
        self._register_change("Set timeline In/Out")
        return {"before": before, "after": self.in_out_range()}

    def clear_in_out(self) -> dict[str, Any]:
        owner = self._require_owner()
        before = self.in_out_range()
        method = getattr(owner, "_clear_global_markers", None)
        if callable(method):
            method()
        else:
            setattr(owner, "_global_in_ms", -1)
            setattr(owner, "_global_out_ms", -1)
            ruler = getattr(owner, "_timeline_ruler", None)
            set_markers = getattr(ruler, "set_global_markers", None)
            if callable(set_markers):
                set_markers(-1, -1)
        self._register_change("Clear timeline In/Out")
        return {"before": before, "after": self.in_out_range()}

    def nle_status(self) -> dict[str, Any]:
        records = self._clipboard_records()
        try:
            gaps = self.timeline_gaps()
        except Exception:
            gaps = {"gap_count": 0, "tracks": []}
        try:
            selection = self.selection_summary()
        except Exception:
            selection = {"selection": [], "selected_count": 0}
        return {
            "playhead_ms": self._current_playhead_ms(),
            "in_out": self.in_out_range(),
            "source_monitor": self.source_monitor_state(),
            "record_monitor": self.record_monitor_state(),
            "track_targets": self.track_targets(),
            "snap": self.snap_settings(),
            "selection": selection,
            "markers": self.list_markers(),
            "gaps": {"gap_count": _int(gaps.get("gap_count"), 0), "tracks": list(gaps.get("tracks") or [])},
            "clipboard": {
                "kind": "video_clips" if records else "",
                "count": len(records),
                "base_ms": min((_int(row.get("timeline_in_ms"), 0) for row in records), default=0),
                "track_ids": sorted({_int(row.get("track_id"), 0) for row in records}),
            },
        }

    def creative_layer_readiness(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.creative_layer_readiness import (
            build_creative_layer_readiness_report,
            format_creative_layer_readiness_summary,
        )
        from app.preset_library import preset_library_summary

        report = build_creative_layer_readiness_report(
            self.snapshot(media_limit=500),
            action_ids=tuple(str(row) for row in (action_ids or ())),
            preset_summary=preset_library_summary(),
        )
        report["summary_text"] = format_creative_layer_readiness_summary(report)
        return report

    def source_monitor_state(self) -> dict[str, Any]:
        owner = self._require_owner()
        raw = getattr(owner, "_action_source_monitor", None)
        data = dict(raw or {}) if isinstance(raw, Mapping) else {}
        source_duration = max(0, _int(data.get("source_duration_ms", data.get("duration_ms", 0)), 0))
        source_in = max(0, min(source_duration if source_duration else 2**31 - 1, _int(data.get("source_in_ms", 0), 0)))
        source_out = _int(data.get("source_out_ms", source_duration), source_duration)
        if source_duration > 0:
            source_out = max(source_in, min(source_duration, source_out if source_out > 0 else source_duration))
        else:
            source_out = max(source_in, source_out)
        loaded = bool(data.get("loaded") or data.get("path") or data.get("media_id"))
        return {
            "loaded": loaded,
            "media_id": str(data.get("media_id") or ""),
            "path": str(data.get("path") or ""),
            "name": str(data.get("name") or Path(str(data.get("path") or "")).name),
            "kind": str(data.get("kind") or "video"),
            "source_duration_ms": source_duration,
            "source_in_ms": source_in,
            "source_out_ms": source_out,
            "duration_ms": max(0, source_out - source_in),
        }

    def load_source_monitor(
        self,
        *,
        path: str = "",
        media_id: str = "",
        name: str = "",
        kind: str = "video",
        duration_ms: int | None = None,
        source_in_ms: int = 0,
        source_out_ms: int | None = None,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        before = self.source_monitor_state()
        media_path = str(path or "").strip()
        media_key = str(media_id or "").strip()
        item: Mapping[str, Any] | None = None
        if not media_path and media_key:
            for row in self.media_summary(limit=1000).get("items") or []:
                if not isinstance(row, Mapping):
                    continue
                if str(row.get("id") or "") == media_key:
                    item = row
                    media_path = str(row.get("path") or "")
                    break
        if not media_path and item is None:
            raise ValueError("path or media_id is required")

        item_name = str(name or (item.get("name") if isinstance(item, Mapping) else "") or Path(media_path).name)
        item_kind = str(kind or (item.get("kind") if isinstance(item, Mapping) else "") or "video").strip().lower()
        if item_kind not in {"video", "audio", "image", "actor", "unknown"}:
            item_kind = "video"
        source_duration = max(0, _int(duration_ms, 0))
        if source_duration <= 0 and isinstance(item, Mapping):
            source_duration = max(0, _int(item.get("duration_ms"), 0))
        if source_duration <= 0:
            source_duration = 1000
        source_in = max(0, min(source_duration, _int(source_in_ms, 0)))
        source_out = source_duration if source_out_ms is None else max(0, _int(source_out_ms, source_duration))
        source_out = max(source_in + 1, min(source_duration, source_out))
        state = {
            "loaded": True,
            "media_id": media_key or (str(item.get("id") or "") if isinstance(item, Mapping) else ""),
            "path": media_path,
            "name": item_name,
            "kind": item_kind,
            "source_duration_ms": source_duration,
            "source_in_ms": source_in,
            "source_out_ms": source_out,
        }
        setattr(owner, "_action_source_monitor", state)
        self._register_change("Load source monitor")
        return {"before": before, "after": self.source_monitor_state()}

    def set_source_monitor_in_out(self, *, in_ms: int | None = None, out_ms: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        before = self.source_monitor_state()
        if not before.get("loaded"):
            raise ValueError("source monitor has no loaded media")
        duration = max(1, _int(before.get("source_duration_ms"), 1))
        source_in = _int(before.get("source_in_ms"), 0)
        source_out = _int(before.get("source_out_ms"), duration)
        if in_ms is not None:
            source_in = max(0, min(duration - 1, _int(in_ms, 0)))
            if source_out <= source_in:
                source_out = min(duration, source_in + 1)
        if out_ms is not None:
            source_out = max(source_in + 1, min(duration, _int(out_ms, duration)))
        state = dict(before)
        state["source_in_ms"] = source_in
        state["source_out_ms"] = source_out
        setattr(owner, "_action_source_monitor", state)
        self._register_change("Set source monitor In/Out")
        return {"before": before, "after": self.source_monitor_state()}

    def set_source_monitor_in(self, *, ms: int) -> dict[str, Any]:
        return self.set_source_monitor_in_out(in_ms=_int(ms, 0))

    def set_source_monitor_out(self, *, ms: int) -> dict[str, Any]:
        return self.set_source_monitor_in_out(out_ms=_int(ms, 0))

    def clear_source_monitor(self) -> dict[str, Any]:
        owner = self._require_owner()
        before = self.source_monitor_state()
        setattr(owner, "_action_source_monitor", {})
        self._register_change("Clear source monitor")
        return {"before": before, "after": self.source_monitor_state()}

    def record_monitor_state(self) -> dict[str, Any]:
        data = self.in_out_range()
        return {
            "in_ms": _int(data.get("in_ms"), -1),
            "out_ms": _int(data.get("out_ms"), -1),
            "has_in": bool(data.get("has_in")),
            "has_out": bool(data.get("has_out")),
            "valid": bool(data.get("valid")),
            "duration_ms": _int(data.get("duration_ms"), 0),
            "shared_with_timeline_in_out": True,
        }

    def set_record_monitor_in_out(self, *, in_ms: int | None = None, out_ms: int | None = None) -> dict[str, Any]:
        return self.set_in_out(in_ms=in_ms, out_ms=out_ms)

    def set_record_monitor_in(self, *, ms: int) -> dict[str, Any]:
        return self.set_record_monitor_in_out(in_ms=_int(ms, 0))

    def set_record_monitor_out(self, *, ms: int) -> dict[str, Any]:
        return self.set_record_monitor_in_out(out_ms=_int(ms, 0))

    def clear_record_monitor(self) -> dict[str, Any]:
        return self.clear_in_out()

    def three_point_edit(
        self,
        *,
        mode: str = "insert",
        at_ms: int | None = None,
        record_out_ms: int | None = None,
        target_track_id: int | None = None,
        source_in_ms: int | None = None,
        source_out_ms: int | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        edit_mode = str(mode or "insert").strip().lower()
        if edit_mode not in {"insert", "overwrite"}:
            raise ValueError("mode must be insert or overwrite")
        source = self.source_monitor_state()
        if not source.get("loaded"):
            raise ValueError("source monitor has no loaded media")
        if str(source.get("kind") or "video") != "video":
            raise ValueError("3-point edit currently supports video source media")

        source_duration = max(1, _int(source.get("source_duration_ms"), 1))
        src_in = _int(source_in_ms, _int(source.get("source_in_ms"), 0)) if source_in_ms is not None else _int(source.get("source_in_ms"), 0)
        src_out = _int(source_out_ms, _int(source.get("source_out_ms"), source_duration)) if source_out_ms is not None else _int(source.get("source_out_ms"), source_duration)
        src_in = max(0, min(source_duration - 1, src_in))
        src_out = max(src_in + 1, min(source_duration, src_out))

        record = self.record_monitor_state()
        if at_ms is not None:
            record_in = max(0, _int(at_ms, 0))
        elif bool(record.get("has_in")):
            record_in = max(0, _int(record.get("in_ms"), 0))
        else:
            record_in = self._current_playhead_ms()
        rec_out = _int(record_out_ms, -1) if record_out_ms is not None else (_int(record.get("out_ms"), -1) if bool(record.get("has_out")) else -1)
        if rec_out > record_in and source_out_ms is None and (src_out <= src_in):
            src_out = min(source_duration, src_in + (rec_out - record_in))
        duration = max(1, src_out - src_in)

        track = self._three_point_target_track(target_track_id)
        track_id = _int(getattr(track, "id", 0))
        existing = list(getattr(track, "clips", []) or [])
        would_shift = 0
        would_delete = 0
        if edit_mode == "insert":
            would_shift = sum(
                1
                for clip in existing
                if _int(getattr(clip, "timeline_in_ms", 0)) >= record_in
                or (
                    _int(getattr(clip, "timeline_in_ms", 0)) < record_in
                    < _int(getattr(clip, "timeline_out_ms", 0))
                )
            )
        else:
            preview = self.range_delete(
                start_ms=record_in,
                end_ms=record_in + duration,
                track_id=track_id,
                ripple=False,
                dry_run=True,
            )
            would_delete = _int(preview.get("deleted_clip_count"), 0)

        if dry_run:
            return {
                "mode": edit_mode,
                "source": source,
                "target_track_id": track_id,
                "record_in_ms": record_in,
                "record_out_ms": record_in + duration,
                "source_in_ms": src_in,
                "source_out_ms": src_out,
                "duration_ms": duration,
                "would_shift_clip_count": would_shift if edit_mode == "insert" else 0,
                "would_delete_clip_count": would_delete if edit_mode == "overwrite" else 0,
                "dry_run": True,
            }

        if edit_mode == "insert":
            from app.timeline_model import split_clips_at_project_ms

            track.clips = split_clips_at_project_ms(existing, record_in)
            for clip in getattr(track, "clips", []) or []:
                if _int(getattr(clip, "timeline_in_ms", 0)) >= record_in:
                    clip.timeline_in_ms = _int(getattr(clip, "timeline_in_ms", 0)) + duration
        else:
            self.range_delete(
                start_ms=record_in,
                end_ms=record_in + duration,
                track_id=track_id,
                ripple=False,
                dry_run=False,
            )

        from app.timeline_model import NodeGraph, VideoClip

        source_path_text = str(source.get("path") or "")
        clip = VideoClip(
            id=self._next_clip_id(track),
            source_path=Path(source_path_text) if source_path_text else None,
            source_duration_ms=source_duration,
            timeline_in_ms=record_in,
            source_in_ms=src_in,
            source_out_ms=src_out,
            node_graph=NodeGraph.default(),
        )
        clips = getattr(track, "clips", None)
        if not isinstance(clips, list):
            track.clips = []
            clips = track.clips
        clips.append(clip)
        clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        setattr(owner, "_selected_clips", [(track_id, _int(getattr(clip, "id", 0)))])
        self._broadcast_selection()
        self._after_timeline_mutation(f"Action {edit_mode} 3-point edit")
        return {
            "mode": edit_mode,
            "source": source,
            "target_track_id": track_id,
            "clip_id": _int(getattr(clip, "id", 0)),
            "record_in_ms": record_in,
            "record_out_ms": record_in + duration,
            "source_in_ms": src_in,
            "source_out_ms": src_out,
            "duration_ms": duration,
            "shifted_clip_count": would_shift if edit_mode == "insert" else 0,
            "deleted_clip_count": would_delete if edit_mode == "overwrite" else 0,
        }

    def set_in_out_from_selection(self) -> dict[str, Any]:
        span = self._selected_video_span()
        result = self.set_in_out(in_ms=_int(span.get("span_start_ms"), 0), out_ms=_int(span.get("span_end_ms"), 0))
        return {"selection": span, **result}

    def jump_in_out(self, *, edge: str = "in", dry_run: bool = False) -> dict[str, Any]:
        current = self.in_out_range()
        edge_text = str(edge or "in").strip().lower()
        if edge_text in {"out", "end", "right"}:
            key = "out_ms"
            normalized = "out"
        else:
            key = "in_ms"
            normalized = "in"
        target = _int(current.get(key), -1)
        if target < 0:
            raise ValueError(f"timeline {normalized.upper()} marker is not set")
        before = self._current_playhead_ms()
        if not dry_run:
            self.set_playhead(target)
        return {
            "edge": normalized,
            "from_ms": before,
            "target_ms": target,
            "moved": target != before,
            "range": current,
            "dry_run": bool(dry_run),
        }

    def track_targets(self) -> dict[str, Any]:
        owner = self._require_owner()
        raw = getattr(owner, "_timeline_track_targets", None)
        data = dict(raw or {}) if isinstance(raw, Mapping) else {}

        def _ids(kind: str) -> list[int]:
            return sorted({_int(value, -1) for value in list(data.get(kind) or []) if _int(value, -1) >= 0})

        return {
            "video": _ids("video"),
            "audio": _ids("audio"),
            "has_video_targets": bool(_ids("video")),
            "has_audio_targets": bool(_ids("audio")),
        }

    def set_track_target(
        self,
        *,
        kind: str = "video",
        track_id: int,
        enabled: bool = True,
        exclusive: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        target = _int(track_id, -1)
        if target < 0:
            raise ValueError("track_id is required")
        before = self.track_targets()
        next_data = {"video": set(before.get("video") or []), "audio": set(before.get("audio") or [])}
        if exclusive:
            next_data[kind_text] = set()
        if _bool(enabled, True):
            next_data[kind_text].add(target)
        else:
            next_data[kind_text].discard(target)
        stored = {key: sorted(values) for key, values in next_data.items()}
        setattr(owner, "_timeline_track_targets", stored)
        after = self.track_targets()
        changed = before != after
        if changed:
            self._register_change("Set timeline track target")
        return {"before": before, "after": after, "changed": bool(changed)}

    def clear_track_targets(self, *, kind: str = "all") -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "all").strip().lower()
        before = self.track_targets()
        next_data = {
            "video": set(before.get("video") or []),
            "audio": set(before.get("audio") or []),
        }
        if kind_text in {"video", "all", ""}:
            next_data["video"] = set()
        if kind_text in {"audio", "all", ""}:
            next_data["audio"] = set()
        if kind_text not in {"video", "audio", "all", ""}:
            raise ValueError("kind must be video, audio, or all")
        setattr(owner, "_timeline_track_targets", {key: sorted(values) for key, values in next_data.items()})
        after = self.track_targets()
        changed = before != after
        if changed:
            self._register_change("Clear timeline track targets")
        return {"before": before, "after": after, "changed": bool(changed)}

    def clip_audition_range(
        self,
        *,
        track_id: int | None = None,
        clip_id: int | None = None,
        at_ms: int | None = None,
    ) -> dict[str, Any]:
        if track_id is not None and clip_id is not None:
            _track, clip = self._video_track_and_clip(_int(track_id), _int(clip_id))
            start, end = self._video_clip_bounds(clip)
            current = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms))
            return {
                "start_ms": current if start <= current < end else start,
                "end_ms": end,
                "restore_ms": current,
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "source": "explicit_clip",
            }

        owner = self._require_owner()
        current = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms))
        for row in self._normalized_selection_entries():
            if row.get("track_kind") != "video":
                continue
            try:
                _track, clip = self._video_track_and_clip(_int(row.get("track_id")), _int(row.get("clip_id")))
                start, end = self._video_clip_bounds(clip)
            except Exception:
                continue
            return {
                "start_ms": current if start <= current < end else start,
                "end_ms": end,
                "restore_ms": current,
                "track_id": _int(row.get("track_id")),
                "clip_id": _int(row.get("clip_id")),
                "source": "selection",
            }

        for track in reversed(list(getattr(owner, "_tracks", []) or [])):
            if bool(getattr(track, "pip_enabled", False)):
                continue
            for clip in list(getattr(track, "clips", []) or []):
                start, end = self._video_clip_bounds(clip)
                if start <= current < end:
                    return {
                        "start_ms": current,
                        "end_ms": end,
                        "restore_ms": current,
                        "track_id": _int(getattr(track, "id", 0)),
                        "clip_id": _int(getattr(clip, "id", 0)),
                        "source": "under_playhead",
                    }
        raise ValueError("no playable clip range found")

    def play_range(
        self,
        *,
        start_ms: int,
        end_ms: int,
        return_to_ms: int | None = None,
        restore_playhead: bool = True,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        start = max(0, _int(start_ms))
        end = max(start + 1, _int(end_ms, start + 1))
        restore = self._current_playhead_ms() if return_to_ms is None else max(0, _int(return_to_ms))
        player = getattr(owner, "_player", None)
        if player is None:
            setattr(owner, "_action_play_range", {"start_ms": start, "end_ms": end, "return_to_ms": restore})
            return {"start_ms": start, "end_ms": end, "return_to_ms": restore, "mode": "recorded_no_player"}
        self.set_playhead(start)
        play_until = getattr(player, "play_until", None)
        if callable(play_until):
            play_until(end, return_to_ms=restore if restore_playhead else None)
            mode = "play_until"
        else:
            play = getattr(player, "play", None)
            if callable(play):
                play()
            mode = "play"
        return {
            "start_ms": start,
            "end_ms": end,
            "return_to_ms": restore if restore_playhead else None,
            "mode": mode,
        }

    def play_clip_range(
        self,
        *,
        track_id: int | None = None,
        clip_id: int | None = None,
        at_ms: int | None = None,
        restore_playhead: bool = True,
    ) -> dict[str, Any]:
        audition = self.clip_audition_range(track_id=track_id, clip_id=clip_id, at_ms=at_ms)
        playback = self.play_range(
            start_ms=_int(audition["start_ms"]),
            end_ms=_int(audition["end_ms"]),
            return_to_ms=_int(audition["restore_ms"]),
            restore_playhead=restore_playhead,
        )
        return {"audition": audition, "playback": playback}

    def set_zoom(self, px_per_sec: float) -> dict[str, Any]:
        owner = self._require_owner()
        value = max(1.0, _float(px_per_sec, 40.0))
        method = getattr(owner, "_set_timeline_zoom_px", None)
        changed = False
        if callable(method):
            changed = bool(method(value))
        else:
            before = _float(getattr(owner, "_px_per_sec", 0.0), 0.0)
            setattr(owner, "_px_per_sec", value)
            changed = abs(before - value) > 0.001
        if changed:
            self._register_change("Set timeline zoom")
        return {"px_per_sec": value, "changed": bool(changed)}

    def pan_timeline(
        self,
        *,
        delta_px: int | float | None = None,
        scroll_px: int | float | None = None,
    ) -> dict[str, Any]:
        from app.video_editor_timeline_pan import timeline_pan_by, timeline_pan_to

        owner = self._require_owner()
        if scroll_px is not None:
            result = timeline_pan_to(owner, scroll_px)
        else:
            result = timeline_pan_by(owner, _float(delta_px, 0.0))
        result["changed"] = bool(result.get("delta_px"))
        return result

    def fit_timeline(self, *, visible_width: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        before = _float(getattr(owner, "_px_per_sec", 0.0), 0.0)
        fit = getattr(owner, "_zoom_fit", None)
        if callable(fit):
            fit()
        else:
            duration = self._timeline_duration_ms()
            width = _int(visible_width, 0)
            if width <= 0:
                width = _int(getattr(owner, "_action_timeline_width", 0), 0)
            scroll = getattr(owner, "_tracks_scroll", None)
            viewport = getattr(scroll, "viewport", None)
            if callable(viewport):
                try:
                    width = max(width, _int(viewport().width(), 0))
                except Exception:
                    pass
            if duration <= 0:
                raise ValueError("timeline has no duration to fit")
            width = max(120, width or 1200)
            target_px = max(1.0, (width - 40) / max(0.001, duration / 1000.0))
            self.set_zoom(target_px)
        after = _float(getattr(owner, "_px_per_sec", before), before)
        changed = abs(after - before) > 0.001
        if changed:
            ensure = getattr(owner, "_ensure_playhead_visible", None)
            if callable(ensure):
                ensure()
            self._register_change("Fit timeline")
        return {"old_px_per_sec": before, "px_per_sec": after, "changed": bool(changed)}

    def snap_settings(self) -> dict[str, Any]:
        owner = self._require_owner()
        defaults = {
            "enabled": True,
            "snap_ms": 200,
            "include_clip_edges": True,
            "include_playhead": True,
            "include_markers": True,
            "include_edit_points": True,
        }
        raw = getattr(owner, "_timeline_snap_settings", None)
        if isinstance(raw, Mapping):
            defaults.update(dict(raw))
        defaults["enabled"] = _bool(defaults.get("enabled"), True)
        defaults["snap_ms"] = max(0, _int(defaults.get("snap_ms", 200), 200))
        for key in ("include_clip_edges", "include_playhead", "include_markers", "include_edit_points"):
            defaults[key] = _bool(defaults.get(key), True)
        return defaults

    def set_snap_settings(
        self,
        *,
        enabled: bool | None = None,
        snap_ms: int | None = None,
        include_clip_edges: bool | None = None,
        include_playhead: bool | None = None,
        include_markers: bool | None = None,
        include_edit_points: bool | None = None,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        before = self.snap_settings()
        after = dict(before)
        updates = {
            "enabled": enabled,
            "snap_ms": snap_ms,
            "include_clip_edges": include_clip_edges,
            "include_playhead": include_playhead,
            "include_markers": include_markers,
            "include_edit_points": include_edit_points,
        }
        for key, value in updates.items():
            if value is None:
                continue
            if key == "snap_ms":
                after[key] = max(0, _int(value, before["snap_ms"]))
            else:
                after[key] = _bool(value, bool(before.get(key)))
        setattr(owner, "_timeline_snap_settings", after)
        changed = after != before
        if changed:
            self._register_change("Set timeline snap")
        return {"settings": after, "old_settings": before, "changed": bool(changed)}

    def toggle_snap(self, *, enabled: bool | None = None) -> dict[str, Any]:
        current = self.snap_settings()
        value = (not bool(current.get("enabled", True))) if enabled is None else _bool(enabled, True)
        return self.set_snap_settings(enabled=value)

    def history_step(self, *, direction: str = "undo") -> dict[str, Any]:
        owner = self._require_owner()
        direction_text = str(direction or "undo").strip().lower()
        if direction_text not in {"undo", "redo"}:
            raise ValueError("direction must be undo or redo")
        history = getattr(owner, "_history", None)
        can_step = None
        label = ""
        if history is not None:
            can_method = getattr(history, f"can_{direction_text}", None)
            label_method = getattr(history, f"{direction_text}_label", None)
            if callable(can_method):
                try:
                    can_step = bool(can_method())
                except Exception:
                    can_step = None
            if callable(label_method):
                try:
                    label = str(label_method() or "")
                except Exception:
                    label = ""
        method = getattr(owner, f"_on_{direction_text}", None)
        if not callable(method):
            raise ValueError(f"editor does not expose {direction_text}")
        method()
        return {"direction": direction_text, "label": label, "available_before": can_step}

    def undo_history(self) -> dict[str, Any]:
        return self.history_step(direction="undo")

    def redo_history(self) -> dict[str, Any]:
        return self.history_step(direction="redo")

    def add_marker(self, *, ms: int, label: str = "", color: str = "#8A7CFF", marker_id: str = "") -> dict[str, Any]:
        owner = self._require_owner()
        value = max(0, _int(ms))
        markers = list(getattr(owner, "_timeline_markers", []) or [])
        marker = {
            "id": str(marker_id or f"action-marker-{value}-{len(markers) + 1}"),
            "ms": value,
            "label": str(label or ""),
            "color": str(color or "#8A7CFF"),
            "source": "python_action",
        }
        markers.append(marker)
        markers.sort(key=lambda row: _int(row.get("ms", 0)) if isinstance(row, Mapping) else 0)
        setattr(owner, "_timeline_markers", markers)
        sync = getattr(owner, "_sync_markers_to_ruler", None)
        if callable(sync):
            sync()
        self._register_change("Add marker")
        return {"marker": marker, "marker_count": len(markers)}

    def list_markers(self) -> dict[str, Any]:
        owner = self._require_owner()
        rows: list[dict[str, Any]] = []
        for index, marker in enumerate(getattr(owner, "_timeline_markers", []) or []):
            if isinstance(marker, Mapping):
                row = dict(marker)
            else:
                row = {
                    "ms": getattr(marker, "ms", getattr(marker, "time_ms", 0)),
                    "label": getattr(marker, "label", ""),
                    "color": getattr(marker, "color", ""),
                }
            row["index"] = index
            row["id"] = str(row.get("id") or f"marker-{index + 1}")
            row["ms"] = max(0, _int(row.get("ms", row.get("time_ms", row.get("t_ms", 0)))))
            row["label"] = str(row.get("label") or "")
            row["color"] = str(row.get("color") or "")
            rows.append(row)
        rows.sort(key=lambda row: (_int(row.get("ms", 0)), _int(row.get("index", 0))))
        return {"markers": rows, "marker_count": len(rows)}

    def remove_marker(
        self,
        *,
        id: str = "",
        marker_id: str = "",
        ms: int | None = None,
        index: int | None = None,
        label: str = "",
        tolerance_ms: int = 250,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        markers = list(getattr(owner, "_timeline_markers", []) or [])
        if not markers:
            raise ValueError("no timeline markers")

        match_index = self._find_marker_index(
            markers,
            id=id,
            marker_id=marker_id,
            ms=ms,
            index=index,
            label=label,
            tolerance_ms=tolerance_ms,
        )
        removed = markers.pop(match_index)
        setattr(owner, "_timeline_markers", markers)
        sync = getattr(owner, "_sync_markers_to_ruler", None)
        if callable(sync):
            sync()
        self._register_change("Remove marker")
        if isinstance(removed, Mapping):
            removed_row = dict(removed)
        else:
            removed_row = {
                "ms": getattr(removed, "ms", getattr(removed, "time_ms", 0)),
                "label": getattr(removed, "label", ""),
                "color": getattr(removed, "color", ""),
            }
        removed_row["index"] = match_index
        return {"removed": removed_row, "marker_count": len(markers)}

    def move_marker(
        self,
        *,
        new_ms: int,
        id: str = "",
        marker_id: str = "",
        ms: int | None = None,
        index: int | None = None,
        label: str = "",
        tolerance_ms: int = 250,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        markers = list(getattr(owner, "_timeline_markers", []) or [])
        if not markers:
            raise ValueError("no timeline markers")

        match_index = self._find_marker_index(
            markers,
            id=id,
            marker_id=marker_id,
            ms=ms,
            index=index,
            label=label,
            tolerance_ms=tolerance_ms,
        )
        target_ms = max(0, _int(new_ms))
        marker = markers[match_index]
        old_row = self._marker_row(marker, match_index)
        if isinstance(marker, Mapping):
            updated = dict(marker)
            updated["ms"] = target_ms
            markers[match_index] = updated
            marker = updated
        else:
            try:
                setattr(marker, "ms", target_ms)
            except Exception:
                setattr(marker, "time_ms", target_ms)
        markers.sort(key=lambda row: self._marker_ms(row))
        setattr(owner, "_timeline_markers", markers)
        sync = getattr(owner, "_sync_markers_to_ruler", None)
        if callable(sync):
            sync()
        self._register_change("Move marker")
        new_index = markers.index(marker) if marker in markers else self._find_marker_index(markers, ms=target_ms, tolerance_ms=0)
        return {
            "old_marker": old_row,
            "marker": self._marker_row(marker, new_index),
            "marker_count": len(markers),
        }

    def jump_marker(
        self,
        *,
        direction: str = "next",
        from_ms: int | None = None,
        id: str = "",
        marker_id: str = "",
        ms: int | None = None,
        index: int | None = None,
        label: str = "",
        tolerance_ms: int = 250,
    ) -> dict[str, Any]:
        markers = list(getattr(self._require_owner(), "_timeline_markers", []) or [])
        if not markers:
            raise ValueError("no timeline markers")
        selected = self._resolve_marker_row(
            markers,
            direction=direction,
            from_ms=from_ms,
            id=id,
            marker_id=marker_id,
            ms=ms,
            index=index,
            label=label,
            tolerance_ms=tolerance_ms,
        )
        has_direct_target = bool(id or marker_id or label or index is not None or ms is not None)
        target_ms = max(0, _int((selected or {}).get("ms", 0)))
        before_ms = self._current_playhead_ms()
        result = self.set_playhead(target_ms)
        return {
            "from_ms": before_ms,
            "ms": result.get("ms", target_ms),
            "direction": str(direction or "next"),
            "marker": selected or {},
            "wrapped": (not has_direct_target and str(direction or "next").strip().lower() not in {"nearest", "closest"} and (
                (str(direction or "next").strip().lower() in {"prev", "previous", "back", "backward"} and target_ms > before_ms)
                or (str(direction or "next").strip().lower() not in {"prev", "previous", "back", "backward"} and target_ms < before_ms)
            )),
        }

    def align_selection_to_time(
        self,
        *,
        target_ms: int,
        edge: str = "start",
        strict_links: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        span = self._selected_video_span()
        edge_text = str(edge or "start").strip().lower()
        anchor = span["span_end_ms"] if edge_text in {"end", "out", "right"} else span["span_start_ms"]
        target = max(0, _int(target_ms))
        delta = target - _int(anchor)
        move = self.move_selection(delta_ms=delta, strict_links=bool(strict_links), dry_run=bool(dry_run))
        return {
            "target_ms": target,
            "edge": "end" if edge_text in {"end", "out", "right"} else "start",
            "anchor_ms": _int(anchor),
            "delta_ms": delta,
            "span": span,
            "move": move,
            "dry_run": bool(dry_run),
        }

    def align_selection_to_playhead(
        self,
        *,
        edge: str = "start",
        strict_links: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        result = self.align_selection_to_time(
            target_ms=self._current_playhead_ms(),
            edge=edge,
            strict_links=bool(strict_links),
            dry_run=bool(dry_run),
        )
        result["target"] = "playhead"
        return result

    def align_selection_to_marker(
        self,
        *,
        direction: str = "nearest",
        from_ms: int | None = None,
        id: str = "",
        marker_id: str = "",
        ms: int | None = None,
        index: int | None = None,
        label: str = "",
        tolerance_ms: int = 250,
        edge: str = "start",
        strict_links: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        markers = list(getattr(self._require_owner(), "_timeline_markers", []) or [])
        if not markers:
            raise ValueError("no timeline markers")
        marker = self._resolve_marker_row(
            markers,
            direction=direction,
            from_ms=from_ms,
            id=id,
            marker_id=marker_id,
            ms=ms,
            index=index,
            label=label,
            tolerance_ms=tolerance_ms,
        )
        result = self.align_selection_to_time(
            target_ms=_int(marker.get("ms", 0)),
            edge=edge,
            strict_links=bool(strict_links),
            dry_run=bool(dry_run),
        )
        result["target"] = "marker"
        result["marker"] = marker
        result["direction"] = str(direction or "nearest")
        return result

    def snap_selection_to_nearest(
        self,
        *,
        edge: str = "start",
        from_ms: int | None = None,
        strict_links: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        settings = self.snap_settings()
        if not bool(settings.get("enabled", True)):
            raise ValueError("timeline snap is disabled")
        span = self._selected_video_span()
        edge_text = str(edge or "start").strip().lower()
        anchor = span["span_end_ms"] if edge_text in {"end", "out", "right"} else span["span_start_ms"]
        targets = self._timeline_snap_targets(
            include_playhead=bool(settings.get("include_playhead", True)),
            include_markers=bool(settings.get("include_markers", True)),
            include_edit_points=bool(settings.get("include_edit_points", True)),
        )
        if not targets:
            raise ValueError("no snap targets available")
        origin = _int(from_ms, anchor) if from_ms is not None else _int(anchor)
        target = min(targets, key=lambda value: abs(_int(value) - origin))
        result = self.align_selection_to_time(
            target_ms=target,
            edge=edge,
            strict_links=bool(strict_links),
            dry_run=bool(dry_run),
        )
        result["target"] = "nearest_snap"
        result["snap_settings"] = settings
        result["snap_targets"] = targets
        result["snap_distance_ms"] = abs(_int(target) - _int(origin))
        result["within_tolerance"] = result["snap_distance_ms"] <= _int(settings.get("snap_ms", 200))
        return result
