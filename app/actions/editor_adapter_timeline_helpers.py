"""Private timeline, selection, clipboard, and linked-edit helper methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class TimelineHelperMixin:
    """Private helpers for timeline-style action adapter operations."""

    def _video_track(self, track_id: int) -> Any:
        owner = self._require_owner()
        target = _int(track_id)
        for track in getattr(owner, "_tracks", []) or []:
            if _int(getattr(track, "id", -1), -1) == target:
                return track
        raise ValueError(f"video track not found: {target}")

    def _three_point_target_track(self, track_id: int | None = None) -> Any:
        owner = self._require_owner()
        if track_id is not None:
            return self._video_track(_int(track_id))
        targets = list(self.track_targets().get("video") or [])
        if targets:
            return self._video_track(_int(targets[0]))
        tracks = list(getattr(owner, "_tracks", []) or [])
        if tracks:
            return tracks[0]
        if self._owner_uses_legacy_video_editor_tracks():
            from app.video_track_legacy import VideoTrack
        else:
            from app.timeline_model import VideoTrack

        track = VideoTrack(id=1)
        setattr(owner, "_tracks", [track])
        if self._owner_uses_legacy_video_editor_tracks():
            insert = getattr(owner, "_insert_track_widget", None)
            if callable(insert):
                insert(track)
        return track

    def _video_track_and_clip(self, track_id: int, clip_id: int) -> tuple[Any, Any]:
        track = self._video_track(track_id)
        target = _int(clip_id)
        for clip in getattr(track, "clips", []) or []:
            if _int(getattr(clip, "id", -1), -1) == target:
                return track, clip
        raise ValueError(f"clip not found: {target}")

    def _audio_track(self, track_id: int) -> Any:
        owner = self._require_owner()
        target = _int(track_id)
        for track in getattr(owner, "_audio_tracks", []) or []:
            if _int(getattr(track, "id", -1), -1) == target:
                return track
        raise ValueError(f"audio track not found: {target}")

    def _audio_track_and_clip(self, track_id: int, clip_id: int) -> tuple[Any, Any]:
        track = self._audio_track(track_id)
        target = _int(clip_id)
        for clip in getattr(track, "clips", []) or []:
            if _int(getattr(clip, "id", -1), -1) == target:
                return track, clip
        raise ValueError(f"audio clip not found: {target}")

    def _assert_video_track_editable(self, track: Any) -> None:
        if bool(getattr(track, "locked", False)):
            raise ValueError(f"video track is locked: {_int(getattr(track, 'id', 0))}")

    def _current_playhead_ms(self) -> int:
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        if player is not None:
            position = getattr(player, "position", None)
            if callable(position):
                try:
                    return max(0, _int(position()))
                except Exception:
                    pass
            elif position is not None:
                return max(0, _int(position))
            if hasattr(player, "position_ms"):
                return max(0, _int(getattr(player, "position_ms", 0)))
        return max(0, _int(getattr(owner, "_action_playhead_ms", 0)))

    @staticmethod
    def _marker_ms(marker: Any) -> int:
        if isinstance(marker, Mapping):
            return max(0, _int(marker.get("ms", marker.get("time_ms", marker.get("t_ms", 0)))))
        return max(0, _int(getattr(marker, "ms", getattr(marker, "time_ms", 0))))

    def _marker_row(self, marker: Any, index: int) -> dict[str, Any]:
        if isinstance(marker, Mapping):
            row = dict(marker)
        else:
            row = {
                "id": getattr(marker, "id", ""),
                "ms": getattr(marker, "ms", getattr(marker, "time_ms", 0)),
                "label": getattr(marker, "label", ""),
                "color": getattr(marker, "color", ""),
            }
        row["index"] = index
        row["id"] = str(row.get("id") or f"marker-{index + 1}")
        row["ms"] = self._marker_ms(row)
        row["label"] = str(row.get("label") or "")
        row["color"] = str(row.get("color") or "")
        return row

    def _find_marker_index(
        self,
        markers: Sequence[Any],
        *,
        id: str = "",
        marker_id: str = "",
        ms: int | None = None,
        index: int | None = None,
        label: str = "",
        tolerance_ms: int = 250,
    ) -> int:
        wanted_id = str(marker_id or id or "").strip()
        wanted_label = str(label or "").strip().lower()
        wanted_index = _int(index, -1) if index is not None else -1
        wanted_ms = max(0, _int(ms, -1)) if ms is not None else -1
        tolerance = max(0, _int(tolerance_ms, 250))

        if wanted_id:
            for i, marker in enumerate(markers):
                current_id = str(marker.get("id", "") if isinstance(marker, Mapping) else getattr(marker, "id", ""))
                if current_id == wanted_id:
                    return i
        if 0 <= wanted_index < len(markers):
            return wanted_index
        if wanted_label:
            for i, marker in enumerate(markers):
                current_label = str(marker.get("label", "") if isinstance(marker, Mapping) else getattr(marker, "label", ""))
                if current_label.strip().lower() == wanted_label:
                    return i
        if wanted_ms >= 0:
            candidates: list[tuple[int, int]] = []
            for i, marker in enumerate(markers):
                distance = abs(self._marker_ms(marker) - wanted_ms)
                if distance <= tolerance:
                    candidates.append((distance, i))
            if candidates:
                candidates.sort()
                return candidates[0][1]
        raise ValueError("timeline marker not found")

    def _resolve_marker_row(
        self,
        markers: Sequence[Any],
        *,
        direction: str = "nearest",
        from_ms: int | None = None,
        id: str = "",
        marker_id: str = "",
        ms: int | None = None,
        index: int | None = None,
        label: str = "",
        tolerance_ms: int = 250,
    ) -> dict[str, Any]:
        has_direct_target = bool(id or marker_id or label or index is not None or ms is not None)
        if has_direct_target:
            match_index = self._find_marker_index(
                markers,
                id=id,
                marker_id=marker_id,
                ms=ms,
                index=index,
                label=label,
                tolerance_ms=tolerance_ms,
            )
            return self._marker_row(markers[match_index], match_index)
        rows = [self._marker_row(marker, i) for i, marker in enumerate(markers)]
        rows.sort(key=lambda row: (_int(row.get("ms", 0)), _int(row.get("index", 0))))
        if not rows:
            raise ValueError("no timeline markers")
        current = max(0, _int(from_ms, self._current_playhead_ms())) if from_ms is not None else self._current_playhead_ms()
        direction_text = str(direction or "nearest").strip().lower()
        if direction_text in {"prev", "previous", "back", "backward"}:
            candidates = [row for row in rows if _int(row.get("ms", 0)) < current]
            return candidates[-1] if candidates else rows[-1]
        if direction_text in {"next", "forward"}:
            candidates = [row for row in rows if _int(row.get("ms", 0)) > current]
            return candidates[0] if candidates else rows[0]
        return min(rows, key=lambda row: abs(_int(row.get("ms", 0)) - current))

    def _timeline_duration_ms(self) -> int:
        owner = self._require_owner()
        values: list[int] = []
        for track in getattr(owner, "_tracks", []) or []:
            values.append(_int(getattr(track, "offset_ms", 0)) + _int(getattr(track, "duration_ms", 0)))
            for clip in getattr(track, "clips", []) or []:
                try:
                    values.append(self._video_clip_bounds(clip)[1])
                except Exception:
                    values.append(
                        _int(getattr(clip, "timeline_out_ms", 0))
                        or _int(getattr(clip, "timeline_in_ms", 0))
                        + _int(getattr(clip, "duration_ms", getattr(clip, "source_duration_ms", 0)))
                    )
        for track in getattr(owner, "_audio_tracks", []) or []:
            extent = getattr(track, "extent_ms", None)
            if callable(extent):
                try:
                    values.append(_int(extent()))
                    continue
                except Exception:
                    pass
            for clip in getattr(track, "clips", []) or []:
                values.append(
                    _int(getattr(clip, "offset_ms", getattr(clip, "timeline_in_ms", 0)))
                    + _int(getattr(clip, "effective_length_ms", getattr(clip, "duration_ms", 0)))
                )
        for attr in ("_spine_actor_tracks", "_live2d_actor_tracks"):
            for track in getattr(owner, attr, []) or []:
                for clip in getattr(track, "clips", []) or []:
                    values.append(_int(getattr(clip, "end_ms", 0)))
        return max(values, default=0)

    def _video_clip_bounds(self, clip: Any) -> tuple[int, int]:
        start = _int(getattr(clip, "timeline_in_ms", 0), 0)
        explicit_end = _int(getattr(clip, "timeline_out_ms", -1), -1)
        if explicit_end > start:
            return start, explicit_end
        source_in = _int(getattr(clip, "source_in_ms", 0), 0)
        source_out = _int(
            getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0)),
            0,
        )
        if source_out > source_in:
            return start, start + (source_out - source_in)
        duration = _int(getattr(clip, "source_duration_ms", getattr(clip, "duration_ms", 0)), 0)
        end = start + max(0, duration)
        if end <= start:
            raise ValueError("clip has no playable duration")
        return start, end

    def _timeline_edit_points(
        self,
        *,
        track_kind: str = "video",
        track_id: int | None = None,
        include_markers: bool = False,
    ) -> list[int]:
        owner = self._require_owner()
        kind = str(track_kind or "video").strip().lower()
        if kind == "any":
            kind = "all"
        target_track_id = _int(track_id, -1) if track_id is not None else None
        points: set[int] = set()

        def _add(value: Any) -> None:
            ms = _int(value, -1)
            if ms >= 0:
                points.add(ms)

        if kind in {"video", "all", ""}:
            for track in getattr(owner, "_tracks", []) or []:
                current_track_id = _int(getattr(track, "id", -1), -1)
                if target_track_id is not None and current_track_id != target_track_id:
                    continue
                for clip in getattr(track, "clips", []) or []:
                    start = _int(getattr(clip, "timeline_in_ms", 0), 0)
                    _add(start)
                    try:
                        _add(self._video_clip_bounds(clip)[1])
                    except Exception:
                        pass

        if kind in {"audio", "all"}:
            for track in getattr(owner, "_audio_tracks", []) or []:
                current_track_id = _int(getattr(track, "id", -1), -1)
                if target_track_id is not None and current_track_id != target_track_id:
                    continue
                for clip in getattr(track, "clips", []) or []:
                    start = _int(getattr(clip, "offset_ms", getattr(clip, "timeline_in_ms", 0)), 0)
                    duration = _int(
                        getattr(
                            clip,
                            "effective_length_ms",
                            getattr(clip, "duration_ms", getattr(clip, "source_duration_ms", 0)),
                        ),
                        0,
                    )
                    _add(start)
                    _add(start + max(0, duration))

        if include_markers:
            for marker in getattr(owner, "_timeline_markers", []) or []:
                if isinstance(marker, Mapping):
                    _add(marker.get("ms", marker.get("time_ms", marker.get("t_ms", 0))))
                else:
                    _add(getattr(marker, "ms", getattr(marker, "time_ms", 0)))

        return sorted(points)

    def _timeline_snap_targets(
        self,
        *,
        include_playhead: bool = True,
        include_markers: bool = True,
        include_edit_points: bool = False,
        extra_snap_targets: list[int] | tuple[int, ...] | None = None,
    ) -> list[int]:
        owner = self._require_owner()
        targets: list[int] = []

        def _append(value: Any) -> None:
            try:
                ms = int(round(float(value)))
            except Exception:
                return
            if ms >= 0 and ms not in targets:
                targets.append(ms)

        if include_playhead:
            player = getattr(owner, "_player", None)
            position = getattr(player, "position", None)
            if callable(position):
                try:
                    _append(position())
                except Exception:
                    pass
            elif hasattr(player, "position"):
                _append(getattr(player, "position"))
            else:
                _append(getattr(owner, "_action_playhead_ms", 0))

        if include_markers:
            for marker in getattr(owner, "_timeline_markers", []) or []:
                if isinstance(marker, Mapping):
                    _append(marker.get("ms", marker.get("time_ms", marker.get("t_ms", 0))))
                else:
                    _append(getattr(marker, "ms", getattr(marker, "time_ms", 0)))

        if include_edit_points:
            for target in self._timeline_edit_points(track_kind="all", include_markers=False):
                _append(target)

        for target in extra_snap_targets or ():
            _append(target)

        targets.sort()
        return targets

    def _selected_video_span(self) -> dict[str, Any]:
        selected = self._selected_video_keys()
        if not selected:
            raise ValueError("no selected video clips")
        starts: list[int] = []
        ends: list[int] = []
        rows: list[dict[str, int]] = []
        for track_id, clip_id in selected:
            _track, clip = self._video_track_and_clip(track_id, clip_id)
            start, end = self._video_clip_bounds(clip)
            starts.append(start)
            ends.append(end)
            rows.append({"track_id": _int(track_id), "clip_id": _int(clip_id), "start_ms": start, "end_ms": end})
        span_start = min(starts)
        span_end = max(ends)
        return {
            "selection": rows,
            "selected_count": len(rows),
            "span_start_ms": span_start,
            "span_end_ms": span_end,
            "duration_ms": max(0, span_end - span_start),
        }

    def _video_clip_key_at_time(self, ms: int) -> tuple[int, int] | None:
        target = max(0, _int(ms))
        for track in getattr(self._require_owner(), "_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            for clip in getattr(track, "clips", []) or []:
                try:
                    start, end = self._video_clip_bounds(clip)
                except Exception:
                    continue
                if start <= target < end:
                    return (track_id, _int(getattr(clip, "id", -1), -1))
        return None

    def _resolve_edit_range(self, *, start_ms: int | None = None, end_ms: int | None = None) -> tuple[int, int]:
        if start_ms is None or end_ms is None:
            current = self.in_out_range()
            if start_ms is None:
                start_ms = _int(current.get("in_ms"), -1)
            if end_ms is None:
                end_ms = _int(current.get("out_ms"), -1)
        raw_start = _int(start_ms, -1)
        raw_end = _int(end_ms, -1)
        if raw_start < 0 or raw_end < 0 or raw_end <= raw_start:
            raise ValueError("valid start_ms/end_ms or timeline In/Out range is required")
        return max(0, raw_start), max(0, raw_end)

    def _targeted_video_track_ids(self, *, track_id: int | None = None) -> list[int]:
        if track_id is not None:
            return [_int(track_id)]
        targets = list(self.track_targets().get("video") or [])
        if targets:
            return sorted({_int(value) for value in targets})
        return sorted(
            {
                _int(getattr(track, "id", -1), -1)
                for track in getattr(self._require_owner(), "_tracks", []) or []
                if _int(getattr(track, "id", -1), -1) >= 0
            }
        )

    def _gap_target_track(self, *, track_id: int | None = None) -> Any:
        if track_id is not None:
            return self._video_track(_int(track_id))
        targets = list(self.track_targets().get("video") or [])
        if targets:
            return self._video_track(_int(targets[0]))
        selected = self.selected_clip().get("selection")
        if isinstance(selected, Mapping) and str(selected.get("track_kind") or "video") == "video":
            tid = _int(selected.get("track_id"), -1)
            if tid >= 0:
                return self._video_track(tid)
        tracks = list(getattr(self._require_owner(), "_tracks", []) or [])
        if not tracks:
            raise ValueError("no video tracks")
        return tracks[0]

    def _track_gaps(self, track: Any, *, min_gap_ms: int = 1) -> list[dict[str, int]]:
        threshold = max(1, _int(min_gap_ms, 1))
        clips = sorted(list(getattr(track, "clips", []) or []), key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        native_rows: list[dict[str, int]] = []
        for index, clip in enumerate(clips):
            start = _int(getattr(clip, "timeline_in_ms", 0))
            end = _int(getattr(clip, "timeline_out_ms", start))
            native_rows.append(
                {
                    "id": _int(getattr(clip, "id", index), index),
                    "timeline_in_ms": start,
                    "timeline_out_ms": end,
                    "effective_length_ms": max(0, end - start),
                }
            )
        if native_rows:
            try:
                from app.native_worker import native_timeline_gaps

                native = native_timeline_gaps(native_rows, min_gap_ms=threshold)
                raw_gaps = native.get("gaps") if isinstance(native, Mapping) else None
                if isinstance(raw_gaps, list):
                    gaps: list[dict[str, int]] = []
                    for raw in raw_gaps:
                        if not isinstance(raw, Mapping):
                            continue
                        gaps.append(
                            {
                                "index": _int(raw.get("index"), len(gaps)),
                                "start_ms": _int(raw.get("start_ms"), 0),
                                "end_ms": _int(raw.get("end_ms"), 0),
                                "duration_ms": _int(raw.get("duration_ms"), 0),
                                "next_clip_id": _int(raw.get("next_clip_id"), 0),
                            }
                        )
                    return gaps
            except Exception:
                pass
        gaps: list[dict[str, int]] = []
        previous_end: int | None = None
        for clip in clips:
            start, end = self._video_clip_bounds(clip)
            if previous_end is not None and start - previous_end >= threshold:
                gaps.append(
                    {
                        "index": len(gaps),
                        "start_ms": previous_end,
                        "end_ms": start,
                        "duration_ms": start - previous_end,
                        "next_clip_id": _int(getattr(clip, "id", 0)),
                    }
                )
            previous_end = max(previous_end if previous_end is not None else end, end)
        return gaps

    def _select_gap(
        self,
        gaps: Sequence[Mapping[str, Any]],
        *,
        at_ms: int | None = None,
        gap_index: int | None = None,
    ) -> dict[str, int]:
        if gap_index is not None:
            wanted = _int(gap_index, -1)
            for gap in gaps:
                if _int(gap.get("index"), -1) == wanted:
                    return {key: _int(value) for key, value in gap.items()}
            raise ValueError("gap_index was not found")
        target = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms))
        containing = [
            gap
            for gap in gaps
            if _int(gap.get("start_ms"), 0) <= target <= _int(gap.get("end_ms"), 0)
        ]
        if containing:
            return {key: _int(value) for key, value in containing[0].items()}
        after = [gap for gap in gaps if _int(gap.get("start_ms"), 0) >= target]
        if after:
            return {key: _int(value) for key, value in after[0].items()}
        return {key: _int(value) for key, value in gaps[-1].items()}

    def _plan_audio_ripple_delete(self, track: Any, target_clip_ids: set[int]) -> dict[str, Any]:
        track_id = _int(getattr(track, "id", -1), -1)
        clips = sorted(list(getattr(track, "clips", []) or []), key=lambda row: _int(getattr(row, "offset_ms", 0)))
        target_ids = {_int(value, -1) for value in target_clip_ids}
        remaining = [
            {
                "clip": clip,
                "clip_id": _int(getattr(clip, "id", -1), -1),
                "offset_ms": _int(getattr(clip, "offset_ms", 0)),
            }
            for clip in clips
        ]
        deleted: list[dict[str, int]] = []
        for target in [row for row in remaining if row["clip_id"] in target_ids]:
            gap = max(1, _int(getattr(target["clip"], "effective_length_ms", getattr(target["clip"], "duration_ms", 0)), 1))
            target_in = _int(target["offset_ms"])
            deleted.append({"clip_id": target["clip_id"], "offset_ms": target_in, "duration_ms": gap})
            next_remaining: list[dict[str, Any]] = []
            for row in remaining:
                if row["clip_id"] == target["clip_id"]:
                    continue
                next_row = dict(row)
                if _int(row["offset_ms"]) >= target_in:
                    next_row["offset_ms"] = max(0, _int(row["offset_ms"]) - gap)
                next_remaining.append(next_row)
            remaining = next_remaining
        return {
            "track_id": track_id,
            "deleted_clip_ids": [row["clip_id"] for row in deleted],
            "deleted": deleted,
            "remaining": [
                {"clip_id": row["clip_id"], "offset_ms": _int(row["offset_ms"])}
                for row in sorted(remaining, key=lambda row: (_int(row["offset_ms"]), _int(row["clip_id"])))
            ],
        }

    def _apply_audio_ripple_delete(self, track: Any, plan: Mapping[str, Any]) -> None:
        remaining_offsets = {
            _int(row.get("clip_id"), -1): _int(row.get("offset_ms"), 0)
            for row in list(plan.get("remaining") or [])
            if isinstance(row, Mapping)
        }
        deleted_ids = {_int(value, -1) for value in list(plan.get("deleted_clip_ids") or [])}
        next_clips = []
        for clip in list(getattr(track, "clips", []) or []):
            clip_id = _int(getattr(clip, "id", -1), -1)
            if clip_id in deleted_ids:
                continue
            if clip_id in remaining_offsets:
                clip.offset_ms = remaining_offsets[clip_id]
            next_clips.append(clip)
        next_clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
        track.clips = next_clips
        self._update_audio_track(track)

    def _selected_video_keys(self) -> list[tuple[int, int]]:
        keys: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for row in self._normalized_selection_entries():
            if row.get("track_kind") != "video":
                continue
            key = (_int(row.get("track_id"), -1), _int(row.get("clip_id"), -1))
            if key[0] < 0 or key[1] < 0 or key in seen:
                continue
            seen.add(key)
            keys.append(key)
        return keys

    def _clipboard_records_from_request(
        self,
        *,
        clips: Sequence[Mapping[str, Any]] | None = None,
        use_selection: bool = True,
        include_linked_audio: bool = True,
    ) -> list[dict[str, Any]]:
        keys: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        if clips:
            for row in clips:
                key = (_int(row.get("track_id"), -1), _int(row.get("clip_id"), -1))
                if key[0] < 0 or key[1] < 0 or key in seen:
                    continue
                seen.add(key)
                keys.append(key)
        if use_selection:
            for key in self._selected_video_keys():
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
        if use_selection and not keys:
            selected = self.selected_clip().get("selection")
            if isinstance(selected, Mapping) and str(selected.get("track_kind") or "video") == "video":
                key = (_int(selected.get("track_id"), -1), _int(selected.get("clip_id"), -1))
                if key[0] >= 0 and key[1] >= 0 and key not in seen:
                    keys.append(key)
        if not keys:
            raise ValueError("no selected clips to copy")

        records: list[dict[str, Any]] = []
        for track_id, clip_id in keys:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            record: dict[str, Any] = {
                "track_id": _int(getattr(track, "id", track_id)),
                "clip_id": _int(getattr(clip, "id", clip_id)),
                "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
                "timeline_out_ms": _int(getattr(clip, "timeline_out_ms", 0)),
                "clip": copy.deepcopy(clip),
            }
            if include_linked_audio and getattr(clip, "linked_audio_id", None) is not None:
                try:
                    audio_track, audio_clip = self._linked_audio_track_and_clip(clip)
                    record["linked_audio"] = {
                        "track_id": _int(getattr(audio_track, "id", 0)),
                        "clip_id": _int(getattr(audio_clip, "id", 0)),
                        "offset_ms": _int(getattr(audio_clip, "offset_ms", 0)),
                        "clip": copy.deepcopy(audio_clip),
                    }
                except Exception as exc:
                    record["linked_audio_error"] = str(exc)
            records.append(record)
        records.sort(key=lambda row: (_int(row.get("timeline_in_ms"), 0), _int(row.get("track_id"), 0), _int(row.get("clip_id"), 0)))
        return records

    def _clipboard_records(self) -> list[dict[str, Any]]:
        owner = self._require_owner()
        clipboard = getattr(owner, "_action_clipboard", None) or getattr(owner, "_timeline_clipboard", None) or {}
        if not isinstance(clipboard, Mapping) or clipboard.get("kind") != "video_clips":
            return []
        records = [dict(row) for row in list(clipboard.get("records") or []) if isinstance(row, Mapping)]
        return records

    def _clipboard_record_span(self, records: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
        starts: list[int] = []
        ends: list[int] = []
        for row in records:
            start = _int(row.get("timeline_in_ms"), 0)
            end = _int(row.get("timeline_out_ms"), 0)
            clip = row.get("clip")
            if end <= start and clip is not None:
                end = start + max(1, _int(getattr(clip, "duration_ms", 0), 0))
            if end <= start:
                end = start + 1
            starts.append(start)
            ends.append(end)
        base = min(starts, default=0)
        return base, max(max(ends, default=base + 1), base + 1)

    def _clipboard_target_track_ids(
        self,
        records: Sequence[Mapping[str, Any]],
        *,
        target_track_id: int | None = None,
    ) -> list[int]:
        if target_track_id is not None:
            return [_int(target_track_id)]
        explicit = list(self.track_targets().get("video") or [])
        if explicit:
            return sorted({_int(value) for value in explicit if _int(value, -1) >= 0})
        return sorted({_int(row.get("track_id"), 0) for row in records})

    def _paste_linked_audio_record(
        self,
        linked_audio: Any,
        *,
        original_video_in: int,
        new_video_in: int,
    ) -> dict[str, Any] | None:
        if not isinstance(linked_audio, Mapping):
            return None
        source_audio = copy.deepcopy(linked_audio.get("clip"))
        if source_audio is None:
            return None
        audio_track = self._audio_track(_int(linked_audio.get("track_id"), 0))
        original_audio_offset = _int(linked_audio.get("offset_ms", getattr(source_audio, "offset_ms", 0)))
        sync_offset = original_audio_offset - _int(original_video_in)
        new_offset = max(0, _int(new_video_in) + sync_offset)
        source_audio.id = self._next_audio_clip_id()
        source_audio.offset_ms = new_offset
        self._assert_audio_offset_available(audio_track, source_audio, new_offset)
        clips = getattr(audio_track, "clips", None)
        if not isinstance(clips, list):
            audio_track.clips = []
            clips = audio_track.clips
        clips.append(source_audio)
        clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
        self._update_audio_track(audio_track)
        return {
            "track_id": _int(getattr(audio_track, "id", 0)),
            "clip_id": _int(getattr(source_audio, "id", 0)),
            "offset_ms": _int(getattr(source_audio, "offset_ms", 0)),
            "sync_offset_ms": sync_offset,
        }

    def _selection_key(self, row: Mapping[str, Any]) -> tuple[str, int, int]:
        return (
            str(row.get("track_kind") or row.get("kind") or "video").strip().lower(),
            _int(row.get("track_id"), -1),
            _int(row.get("clip_id"), -1),
        )

    def _normalized_selection_entries(self) -> list[dict[str, Any]]:
        if self.owner is None:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[tuple[str, int, int]] = set()

        def _append(kind: str, track_id: Any, clip_id: Any) -> None:
            row = {
                "track_kind": str(kind or "video").strip().lower(),
                "track_id": _int(track_id, -1),
                "clip_id": _int(clip_id, -1),
            }
            key = self._selection_key(row)
            if key[0] not in {"video", "audio"} or key[1] < 0 or key[2] < 0 or key in seen:
                return
            seen.add(key)
            rows.append(row)

        for raw in list(getattr(self.owner, "_selected_clips", []) or []):
            if isinstance(raw, Mapping):
                _append(raw.get("track_kind") or raw.get("kind") or "video", raw.get("track_id"), raw.get("clip_id"))
            elif isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)) and len(raw) >= 2:
                _append("video", raw[0], raw[1])

        audio_clip_id = getattr(self.owner, "_selected_audio_clip_id", None)
        audio_track_id = getattr(self.owner, "_active_audio_track_id", None)
        if audio_clip_id is not None:
            if audio_track_id is None:
                try:
                    audio_track_id = self._find_audio_track_id_for_clip(_int(audio_clip_id))
                except Exception:
                    audio_track_id = None
            if audio_track_id is not None:
                _append("audio", audio_track_id, audio_clip_id)
        return rows

    def _linked_move_result(self, plan: Any) -> dict[str, Any]:
        video = [
            {"track_id": _int(track_id), "clip_id": _int(clip_id), "timeline_in_ms": _int(start)}
            for (track_id, clip_id), start in sorted((getattr(plan, "video_starts", {}) or {}).items())
        ]
        audio = [
            {"track_id": _int(track_id), "clip_id": _int(clip_id), "offset_ms": _int(offset)}
            for (track_id, clip_id), offset in sorted((getattr(plan, "audio_offsets", {}) or {}).items())
        ]
        return {
            "ok": bool(getattr(plan, "ok", False)),
            "blocked_reason": str(getattr(plan, "blocked_reason", "") or ""),
            "details": dict(getattr(plan, "details", {}) or {}),
            "video_moves": video,
            "audio_moves": audio,
            "video_move_count": len(video),
            "linked_audio_count": len(audio),
        }

    def _apply_linked_move_plan(self, plan: Any) -> None:
        video_starts = dict(getattr(plan, "video_starts", {}) or {})
        audio_offsets = dict(getattr(plan, "audio_offsets", {}) or {})
        for track in getattr(self._require_owner(), "_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            changed = False
            for clip in getattr(track, "clips", []) or []:
                key = (track_id, _int(getattr(clip, "id", -1), -1))
                if key in video_starts:
                    clip.timeline_in_ms = _int(video_starts[key])
                    changed = True
            if changed and isinstance(getattr(track, "clips", None), list):
                track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            changed = False
            for clip in getattr(track, "clips", []) or []:
                key = (track_id, _int(getattr(clip, "id", -1), -1))
                if key in audio_offsets:
                    clip.offset_ms = _int(audio_offsets[key])
                    changed = True
            if changed:
                if isinstance(getattr(track, "clips", None), list):
                    track.clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
                self._update_audio_track(track)

    def _linked_audio_offsets_for_video_starts(
        self,
        video_starts: Mapping[tuple[int, int], int],
        delta_ms: int,
    ) -> dict[tuple[int, int], int]:
        if not video_starts:
            return {}
        moved_video_ids = {(int(tid), int(cid)) for tid, cid in video_starts}
        audio_by_id: dict[int, list[tuple[int, Any]]] = {}
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            for clip in getattr(track, "clips", []) or []:
                audio_by_id.setdefault(_int(getattr(clip, "id", -1), -1), []).append((track_id, clip))

        offsets: dict[tuple[int, int], int] = {}
        for track in getattr(self._require_owner(), "_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            for clip in getattr(track, "clips", []) or []:
                clip_id = _int(getattr(clip, "id", -1), -1)
                if (track_id, clip_id) not in moved_video_ids:
                    continue
                linked_id = getattr(clip, "linked_audio_id", None)
                if linked_id is None:
                    continue
                linked_id = _int(linked_id, -1)
                matches = audio_by_id.get(linked_id, [])
                if not matches:
                    raise ValueError(f"linked audio clip not found: {linked_id}")
                if len(matches) > 1:
                    raise ValueError(f"duplicate linked audio clip id: {linked_id}")
                audio_track_id, audio_clip = matches[0]
                new_offset = _int(getattr(audio_clip, "offset_ms", 0)) + _int(delta_ms)
                if new_offset < 0:
                    raise ValueError("linked audio would move before project start")
                key = (audio_track_id, linked_id)
                if key in offsets:
                    raise ValueError(f"linked audio clip would move twice: {linked_id}")
                offsets[key] = new_offset
        return offsets

    def _validate_ripple_trim_video_windows(
        self,
        track: Any,
        selected_clip: Any,
        video_starts: Mapping[tuple[int, int], int],
        *,
        selected_timeline_in: int | None = None,
        selected_source_in: int,
        selected_source_out: int,
        message_prefix: str = "ripple trim",
    ) -> None:
        track_id = _int(getattr(track, "id", -1), -1)
        rows: list[tuple[int, int, int]] = []
        selected_id = _int(getattr(selected_clip, "id", -1), -1)
        for clip in getattr(track, "clips", []) or []:
            clip_id = _int(getattr(clip, "id", -1), -1)
            start = _int(video_starts.get((track_id, clip_id), getattr(clip, "timeline_in_ms", 0)))
            if clip_id == selected_id:
                start = _int(selected_timeline_in, _int(getattr(selected_clip, "timeline_in_ms", 0)))
                length = max(1, _int(selected_source_out) - _int(selected_source_in))
            else:
                length = max(1, _int(getattr(clip, "effective_length_ms", 0), 1))
            if start < 0:
                raise ValueError(f"{message_prefix} would move a clip before project start")
            rows.append((start, start + length, clip_id))
        rows.sort(key=lambda row: (row[0], row[2]))
        for left, right in zip(rows, rows[1:]):
            if left[1] > right[0]:
                raise ValueError(f"{message_prefix} would overlap clips: {left[2]} and {right[2]}")

    def _validate_audio_offsets(self, audio_offsets: Mapping[tuple[int, int], int], *, message_prefix: str = "ripple trim") -> None:
        if not audio_offsets:
            return
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            rows: list[tuple[int, int, int]] = []
            for clip in getattr(track, "clips", []) or []:
                clip_id = _int(getattr(clip, "id", -1), -1)
                start = _int(audio_offsets.get((track_id, clip_id), getattr(clip, "offset_ms", 0)))
                length = max(1, _int(getattr(clip, "effective_length_ms", 0), 1))
                if start < 0:
                    raise ValueError(f"{message_prefix} would move linked audio before project start")
                rows.append((start, start + length, clip_id))
            rows.sort(key=lambda row: (row[0], row[2]))
            for left, right in zip(rows, rows[1:]):
                if left[1] > right[0]:
                    raise ValueError(f"{message_prefix} would overlap audio clips: {left[2]} and {right[2]}")

    def _apply_audio_offsets(self, audio_offsets: Mapping[tuple[int, int], int]) -> None:
        if not audio_offsets:
            return
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            changed = False
            for clip in getattr(track, "clips", []) or []:
                key = (track_id, _int(getattr(clip, "id", -1), -1))
                if key in audio_offsets:
                    clip.offset_ms = _int(audio_offsets[key])
                    changed = True
            if changed:
                if isinstance(getattr(track, "clips", None), list):
                    track.clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
                self._update_audio_track(track)

    def _nearest_audio_clip(self, video_clip: Any, *, audio_track_id: int | None = None) -> tuple[Any, Any, int]:
        best: tuple[int, Any, Any] | None = None
        video_start = _int(getattr(video_clip, "timeline_in_ms", 0))
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            if audio_track_id is not None and _int(getattr(track, "id", -1), -1) != _int(audio_track_id):
                continue
            for clip in getattr(track, "clips", []) or []:
                distance = abs(_int(getattr(clip, "offset_ms", 0)) - video_start)
                if best is None or distance < best[0]:
                    best = (distance, track, clip)
        if best is None:
            raise ValueError("no audio clip available to link")
        return best[1], best[2], best[0]

    def _find_audio_track_id_for_clip(self, audio_clip_id: int) -> int:
        target = _int(audio_clip_id)
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            for clip in getattr(track, "clips", []) or []:
                if _int(getattr(clip, "id", -1), -1) == target:
                    return _int(getattr(track, "id", 0))
        raise ValueError(f"audio clip not found: {target}")

    def _linked_audio_track_and_clip(self, video_clip: Any) -> tuple[Any, Any]:
        linked_id = getattr(video_clip, "linked_audio_id", None)
        if linked_id is None:
            raise ValueError("video clip has no linked audio")
        matches: list[tuple[Any, Any]] = []
        target = _int(linked_id)
        for track in getattr(self._require_owner(), "_audio_tracks", []) or []:
            for clip in getattr(track, "clips", []) or []:
                if _int(getattr(clip, "id", -1), -1) == target:
                    matches.append((track, clip))
        if not matches:
            raise ValueError(f"linked audio clip not found: {target}")
        if len(matches) > 1:
            raise ValueError(f"duplicate linked audio clip id: {target}")
        return matches[0]

    def _audio_clip_edit_state(self, clip: Any) -> dict[str, int]:
        trim_start = _int(getattr(clip, "trim_start_ms", 0))
        trim_end = _int(getattr(clip, "effective_trim_end_ms", getattr(clip, "trim_end_ms", 0)))
        return {
            "id": _int(getattr(clip, "id", 0)),
            "offset_ms": _int(getattr(clip, "offset_ms", 0)),
            "trim_start_ms": trim_start,
            "trim_end_ms": trim_end,
            "timeline_out_ms": _int(getattr(clip, "offset_ms", 0)) + max(0, trim_end - trim_start),
        }

    def _assert_audio_offset_available(self, track: Any, clip: Any, offset_ms: int) -> None:
        self._assert_audio_window_available(
            track,
            clip,
            _int(offset_ms),
            _int(getattr(clip, "effective_length_ms", 0)),
        )

    def _assert_audio_window_available(self, track: Any, clip: Any, offset_ms: int, length_ms: int) -> None:
        start = max(0, _int(offset_ms))
        end = start + max(1, _int(length_ms, 1))
        for other in getattr(track, "clips", []) or []:
            if other is clip:
                continue
            other_start = _int(getattr(other, "offset_ms", 0))
            other_end = other_start + max(0, _int(getattr(other, "effective_length_ms", 0)))
            if not (end <= other_start or other_end <= start):
                raise ValueError("audio edit would overlap another audio clip")

    def _clip_edit_state(self, clip: Any) -> dict[str, int]:
        return {
            "id": _int(getattr(clip, "id", 0)),
            "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
            "timeline_out_ms": _int(getattr(clip, "timeline_out_ms", 0)),
            "source_in_ms": _int(getattr(clip, "source_in_ms", 0)),
            "source_out_ms": _int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0))),
        }

    def _clip_states_by_id(self, clips: list[Any], clip_ids: list[int] | tuple[int, ...]) -> dict[str, dict[str, int]]:
        wanted = {_int(value) for value in clip_ids}
        rows: dict[str, dict[str, int]] = {}
        for clip in clips or []:
            cid = _int(getattr(clip, "id", -1), -1)
            if cid in wanted:
                rows[str(cid)] = self._clip_edit_state(clip)
        missing = [str(cid) for cid in sorted(wanted) if str(cid) not in rows]
        if missing:
            raise ValueError(f"clip not found: {', '.join(missing)}")
        return rows

    def _slide_neighbor_ids(self, clips: list[Any], clip_id: int) -> tuple[int, int, int]:
        ordered = sorted(list(clips or []), key=lambda clip: _int(getattr(clip, "timeline_in_ms", 0)))
        target = _int(clip_id)
        for index, clip in enumerate(ordered):
            if _int(getattr(clip, "id", -1), -1) == target:
                if index <= 0 or index >= len(ordered) - 1:
                    raise ValueError("slide edit requires previous and next clips")
                return (
                    _int(getattr(ordered[index - 1], "id", 0)),
                    target,
                    _int(getattr(ordered[index + 1], "id", 0)),
                )
        raise ValueError(f"clip not found: {target}")

