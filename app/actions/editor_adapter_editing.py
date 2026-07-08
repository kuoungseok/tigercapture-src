"""Core editing, creative, actor, capture, and review adapter methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
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


class EditingAdapterMixin:
    """Registered editing action adapter methods backed by editor private helpers."""

    def split_clip(self, *, track_id: int, at_ms: int) -> dict[str, Any]:
        track = self._video_track(track_id)
        before = len(getattr(track, "clips", []) or [])
        split_at = max(0, _int(at_ms))
        split_method = getattr(track, "split_at", None)
        if callable(split_method):
            left, right = split_method(split_at)
        else:
            from app.timeline_model import split_clips_at_project_ms

            old_clips = list(getattr(track, "clips", []) or [])
            new_clips = split_clips_at_project_ms(old_clips, split_at)
            if len(new_clips) <= len(old_clips):
                raise ValueError(f"no clip at split time: {split_at}")
            track.clips = new_clips
            try:
                setattr(track, "clips_explicit", True)
            except Exception:
                pass
            left = next(
                (
                    clip
                    for clip in new_clips
                    if _int(getattr(clip, "timeline_in_ms", 0)) < split_at
                    and _int(getattr(clip, "timeline_out_ms", 0)) == split_at
                ),
                None,
            )
            right = next(
                (clip for clip in new_clips if _int(getattr(clip, "timeline_in_ms", 0)) == split_at),
                None,
            )
            if left is None or right is None:
                raise ValueError(f"split did not produce adjacent clips at: {split_at}")
        self._after_timeline_mutation("Action split clip")
        return {
            "track_id": _int(getattr(track, "id", track_id), track_id),
            "at_ms": split_at,
            "left_clip_id": _int(getattr(left, "id", 0)),
            "right_clip_id": _int(getattr(right, "id", 0)),
            "clip_count_before": before,
            "clip_count_after": len(getattr(track, "clips", []) or []),
        }

    def trim_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        source_in_ms: int | None = None,
        source_out_ms: int | None = None,
    ) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        old = {
            "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
            "source_in_ms": _int(getattr(clip, "source_in_ms", 0)),
            "source_out_ms": _int(getattr(clip, "effective_source_out_ms", 0)),
        }
        max_out = max(1, _int(getattr(clip, "source_duration_ms", 0)) or old["source_out_ms"])
        new_in = old["source_in_ms"] if source_in_ms is None else max(0, _int(source_in_ms))
        new_out = old["source_out_ms"] if source_out_ms is None else max(1, _int(source_out_ms))
        new_in = max(0, min(new_in, max_out - 1))
        new_out = max(new_in + 1, min(new_out, max_out))
        delta_in = new_in - old["source_in_ms"]
        clip.source_in_ms = new_in
        clip.source_out_ms = new_out
        clip.timeline_in_ms = max(0, old["timeline_in_ms"] + delta_in)
        clips = getattr(track, "clips", None)
        if isinstance(clips, list):
            clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        self._after_timeline_mutation("Action trim clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "old": old,
            "new": {
                "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
                "source_in_ms": _int(getattr(clip, "source_in_ms", 0)),
                "source_out_ms": _int(getattr(clip, "effective_source_out_ms", 0)),
            },
        }

    def _native_video_trim_plan(self, track: Any, clip: Any, *, mode: str, **params: Any) -> dict[str, Any] | None:
        rows: list[dict[str, Any]] = []
        selected_index = 0
        for index, row in enumerate(list(getattr(track, "clips", []) or [])):
            start = _int(getattr(row, "timeline_in_ms", 0))
            end = _int(getattr(row, "timeline_out_ms", start))
            source_in = _int(getattr(row, "source_in_ms", 0))
            source_out = _int(
                getattr(row, "effective_source_out_ms", getattr(row, "source_out_ms", source_in + max(0, end - start)))
            )
            source_duration = max(1, _int(getattr(row, "source_duration_ms", 0)) or source_out or max(1, end - start))
            rows.append(
                {
                    "id": _int(getattr(row, "id", index), index),
                    "timeline_in_ms": start,
                    "timeline_out_ms": end,
                    "effective_length_ms": max(0, end - start),
                    "source_in_ms": source_in,
                    "source_out_ms": source_out,
                    "source_duration_ms": source_duration,
                }
            )
            if row is clip:
                selected_index = index
        if not rows:
            return None
        try:
            from app.native_worker import native_timeline_trim_plan

            plan = native_timeline_trim_plan(rows, clip_index=selected_index, mode=mode, **params)
            return dict(plan) if isinstance(plan, dict) else None
        except Exception:
            return None

    def _native_shifted_video_starts(self, track_id_value: int, plan: Mapping[str, Any]) -> dict[tuple[int, int], int] | None:
        raw_rows = plan.get("shifted_clips")
        if not isinstance(raw_rows, list):
            return None
        starts: dict[tuple[int, int], int] = {}
        for row in raw_rows:
            if not isinstance(row, Mapping):
                return None
            cid = _int(row.get("clip_id"), -1)
            if cid < 0:
                return None
            tid = _int(row.get("track_id"), track_id_value)
            starts[(tid, cid)] = max(0, _int(row.get("timeline_in_ms"), 0))
        return starts

    def ripple_trim_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        edge: str = "right",
        delta_ms: int,
        ripple_linked_audio: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        self._assert_video_track_editable(track)
        edge_text = str(edge or "right").strip().lower()
        if edge_text in {"start", "in", "left", "l"}:
            edge_text = "left"
        elif edge_text in {"end", "out", "right", "r"}:
            edge_text = "right"
        else:
            raise ValueError("edge must be left or right")

        delta = _int(delta_ms)
        old = self._clip_edit_state(clip)
        source_in = _int(getattr(clip, "source_in_ms", 0))
        source_out = _int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0)))
        source_duration = max(source_out, _int(getattr(clip, "source_duration_ms", 0)) or source_out)
        track_clips = list(getattr(track, "clips", []) or [])
        old_start = _int(getattr(clip, "timeline_in_ms", 0))
        old_out = _int(getattr(clip, "timeline_out_ms", old_start))
        track_id_value = _int(getattr(track, "id", track_id), track_id)
        trim_backend = "python"

        native_plan = self._native_video_trim_plan(
            track,
            clip,
            mode="ripple_trim",
            edge=edge_text,
            delta_ms=delta,
        )
        native_new = native_plan.get("new") if isinstance(native_plan, Mapping) else None
        if isinstance(native_new, Mapping):
            new_start = max(0, _int(native_new.get("timeline_in_ms"), old_start))
            new_source_in = max(0, _int(native_new.get("source_in_ms"), source_in))
            new_source_out = max(new_source_in + 1, _int(native_new.get("source_out_ms"), source_out))
            new_out = max(new_start + 1, _int(native_new.get("timeline_out_ms"), new_start + new_source_out - new_source_in))
            ripple_delta = _int(native_plan.get("ripple_delta_ms"), new_out - old_out)
            video_starts = self._native_shifted_video_starts(track_id_value, native_plan) or {}
            trim_backend = str(native_plan.get("backend") or "rust_worker")
        else:
            new_start = old_start
            if edge_text == "right":
                new_source_in = source_in
                new_source_out = max(source_in + 1, min(source_duration, source_out + delta))
                ripple_delta = new_source_out - source_out
            else:
                new_source_out = source_out
                new_source_in = max(0, min(source_in + delta, source_out - 1))
                ripple_delta = -(new_source_in - source_in)
            new_out = old_start + max(0, new_source_out - new_source_in)
            video_starts = {}
            if ripple_delta != 0:
                for row in track_clips:
                    row_id = _int(getattr(row, "id", -1), -1)
                    if row is clip or row_id == _int(clip_id):
                        continue
                    if _int(getattr(row, "timeline_in_ms", 0)) >= old_out:
                        video_starts[(track_id_value, row_id)] = max(
                            0, _int(getattr(row, "timeline_in_ms", 0)) + ripple_delta
                        )

        audio_offsets = (
            self._linked_audio_offsets_for_video_starts(video_starts, ripple_delta)
            if ripple_linked_audio and ripple_delta != 0
            else {}
        )
        self._validate_ripple_trim_video_windows(
            track,
            clip,
            video_starts,
            selected_source_in=new_source_in,
            selected_source_out=new_source_out,
        )
        self._validate_audio_offsets(audio_offsets)

        result = {
            "track_id": track_id_value,
            "clip_id": _int(clip_id),
            "edge": edge_text,
            "requested_delta_ms": delta,
            "ripple_delta_ms": ripple_delta,
            "old": old,
            "new": {
                "id": _int(clip_id),
                "timeline_in_ms": new_start,
                "timeline_out_ms": new_out,
                "source_in_ms": new_source_in,
                "source_out_ms": new_source_out,
            },
            "trim_backend": trim_backend,
            "shifted_clips": [
                {"track_id": tid, "clip_id": cid, "timeline_in_ms": start}
                for (tid, cid), start in sorted(video_starts.items())
            ],
            "shifted_linked_audio": [
                {"track_id": tid, "clip_id": cid, "offset_ms": offset}
                for (tid, cid), offset in sorted(audio_offsets.items())
            ],
            "changed": bool(ripple_delta),
            "dry_run": bool(dry_run),
        }
        if dry_run:
            return result

        clip.timeline_in_ms = new_start
        clip.source_in_ms = new_source_in
        clip.source_out_ms = new_source_out
        for row in track_clips:
            key = (track_id_value, _int(getattr(row, "id", -1), -1))
            if key in video_starts:
                row.timeline_in_ms = _int(video_starts[key])
        if isinstance(getattr(track, "clips", None), list):
            track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        self._apply_audio_offsets(audio_offsets)
        self._after_timeline_mutation("Action ripple trim clip")
        return result

    def precision_trim_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        timeline_in_ms: int | None = None,
        source_in_ms: int | None = None,
        source_out_ms: int | None = None,
        left_delta_ms: int | None = None,
        right_delta_ms: int | None = None,
        slip_delta_ms: int | None = None,
        ripple: bool = False,
        ripple_linked_audio: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        self._assert_video_track_editable(track)
        old = self._clip_edit_state(clip)
        old_start = _int(getattr(clip, "timeline_in_ms", 0))
        old_out = _int(getattr(clip, "timeline_out_ms", old_start))
        source_duration = max(
            1,
            _int(getattr(clip, "source_duration_ms", 0))
            or _int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 1)), 1),
        )
        track_id_value = _int(getattr(track, "id", track_id), track_id)
        trim_backend = "python"

        native_plan = self._native_video_trim_plan(
            track,
            clip,
            mode="precision_trim",
            timeline_in_ms=timeline_in_ms,
            source_in_ms=source_in_ms,
            source_out_ms=source_out_ms,
            left_delta_ms=left_delta_ms,
            right_delta_ms=right_delta_ms,
            slip_delta_ms=slip_delta_ms,
            ripple=bool(ripple),
        )
        native_new = native_plan.get("new") if isinstance(native_plan, Mapping) else None
        if isinstance(native_new, Mapping):
            new_start = max(0, _int(native_new.get("timeline_in_ms"), old_start))
            new_source_in = max(0, _int(native_new.get("source_in_ms"), _int(getattr(clip, "source_in_ms", 0))))
            new_source_out = max(new_source_in + 1, _int(native_new.get("source_out_ms"), source_duration))
            new_out = max(new_start + 1, _int(native_new.get("timeline_out_ms"), new_start + new_source_out - new_source_in))
            ripple_delta = _int(native_plan.get("ripple_delta_ms"), new_out - old_out) if ripple else 0
            video_starts = self._native_shifted_video_starts(track_id_value, native_plan) if ripple else {}
            if video_starts is None:
                video_starts = {}
            trim_backend = str(native_plan.get("backend") or "rust_worker")
        else:
            new_start = old_start if timeline_in_ms is None else max(0, _int(timeline_in_ms))
            new_source_in = _int(getattr(clip, "source_in_ms", 0))
            new_source_out = _int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", source_duration)))

            if source_in_ms is not None:
                new_source_in = _int(source_in_ms)
            if source_out_ms is not None:
                new_source_out = _int(source_out_ms)
            if left_delta_ms is not None:
                new_source_in += _int(left_delta_ms)
                new_start = max(0, new_start + _int(left_delta_ms))
            if right_delta_ms is not None:
                new_source_out += _int(right_delta_ms)
            if slip_delta_ms is not None:
                length = max(1, new_source_out - new_source_in)
                max_in = max(0, source_duration - length)
                new_source_in = max(0, min(max_in, new_source_in + _int(slip_delta_ms)))
                new_source_out = new_source_in + length

            new_source_in = max(0, min(new_source_in, source_duration - 1))
            new_source_out = max(new_source_in + 1, min(new_source_out, source_duration))
            new_out = new_start + max(1, new_source_out - new_source_in)
            ripple_delta = new_out - old_out

            video_starts = {}
            if ripple and ripple_delta != 0:
                for row in list(getattr(track, "clips", []) or []):
                    row_id = _int(getattr(row, "id", -1), -1)
                    if row is clip or row_id == _int(clip_id):
                        continue
                    if _int(getattr(row, "timeline_in_ms", 0)) >= old_out:
                        video_starts[(track_id_value, row_id)] = max(
                            0, _int(getattr(row, "timeline_in_ms", 0)) + ripple_delta
                        )

        audio_offsets: dict[tuple[int, int], int] = {}
        selected_start_delta = new_start - old_start
        if selected_start_delta != 0 and getattr(clip, "linked_audio_id", None) is not None:
            audio_track, audio_clip = self._linked_audio_track_and_clip(clip)
            audio_key = (_int(getattr(audio_track, "id", 0)), _int(getattr(audio_clip, "id", 0)))
            audio_offsets[audio_key] = max(0, _int(getattr(audio_clip, "offset_ms", 0)) + selected_start_delta)
        if ripple_linked_audio and ripple and ripple_delta != 0:
            for key, value in self._linked_audio_offsets_for_video_starts(video_starts, ripple_delta).items():
                if key in audio_offsets:
                    raise ValueError(f"linked audio clip would move twice: {key[1]}")
                audio_offsets[key] = value

        self._validate_ripple_trim_video_windows(
            track,
            clip,
            video_starts,
            selected_timeline_in=new_start,
            selected_source_in=new_source_in,
            selected_source_out=new_source_out,
            message_prefix="precision trim",
        )
        self._validate_audio_offsets(audio_offsets, message_prefix="precision trim")

        result = {
            "track_id": track_id_value,
            "clip_id": _int(clip_id),
            "old": old,
            "new": {
                "id": _int(clip_id),
                "timeline_in_ms": new_start,
                "timeline_out_ms": new_out,
                "source_in_ms": new_source_in,
                "source_out_ms": new_source_out,
            },
            "timeline_delta_ms": selected_start_delta,
            "ripple": bool(ripple),
            "ripple_delta_ms": ripple_delta if ripple else 0,
            "trim_backend": trim_backend,
            "shifted_clips": [
                {"track_id": tid, "clip_id": cid, "timeline_in_ms": start}
                for (tid, cid), start in sorted(video_starts.items())
            ],
            "shifted_audio": [
                {"track_id": tid, "clip_id": cid, "offset_ms": offset}
                for (tid, cid), offset in sorted(audio_offsets.items())
            ],
            "changed": old
            != {
                "id": _int(clip_id),
                "timeline_in_ms": new_start,
                "timeline_out_ms": new_out,
                "source_in_ms": new_source_in,
                "source_out_ms": new_source_out,
            }
            or bool(video_starts)
            or bool(audio_offsets),
            "dry_run": bool(dry_run),
        }
        if dry_run:
            return result

        clip.timeline_in_ms = new_start
        clip.source_in_ms = new_source_in
        clip.source_out_ms = new_source_out
        for row in getattr(track, "clips", []) or []:
            key = (track_id_value, _int(getattr(row, "id", -1), -1))
            if key in video_starts:
                row.timeline_in_ms = _int(video_starts[key])
        if isinstance(getattr(track, "clips", None), list):
            track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        self._apply_audio_offsets(audio_offsets)
        self._after_timeline_mutation("Action precision trim")
        return result

    def trim_to_playhead(
        self,
        *,
        edge: str = "auto",
        track_id: int | None = None,
        clip_id: int | None = None,
        at_ms: int | None = None,
        ripple: bool = False,
        ripple_linked_audio: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        target = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms))
        if track_id is None or clip_id is None:
            selected = self._selected_video_keys()
            if selected:
                track_id, clip_id = selected[0]
            else:
                found = self._video_clip_key_at_time(target)
                if found is None:
                    raise ValueError("no selected clip or clip under playhead")
                track_id, clip_id = found
        track, clip = self._video_track_and_clip(_int(track_id), _int(clip_id))
        self._assert_video_track_editable(track)
        start, end = self._video_clip_bounds(clip)
        if target <= start and target >= end:
            raise ValueError("playhead is outside the trim range")
        edge_text = str(edge or "auto").strip().lower()
        if edge_text in {"auto", ""}:
            edge_text = "left" if abs(target - start) <= abs(end - target) else "right"
        elif edge_text in {"start", "in", "left", "l"}:
            edge_text = "left"
        elif edge_text in {"end", "out", "right", "r"}:
            edge_text = "right"
        else:
            raise ValueError("edge must be left, right, or auto")

        if edge_text == "left":
            if target >= end:
                raise ValueError("left trim target must be before the clip end")
            delta = target - start
            result = self.precision_trim_clip(
                track_id=_int(track_id),
                clip_id=_int(clip_id),
                left_delta_ms=delta,
                ripple=bool(ripple),
                ripple_linked_audio=bool(ripple_linked_audio),
                dry_run=bool(dry_run),
            )
        else:
            if target <= start:
                raise ValueError("right trim target must be after the clip start")
            delta = target - end
            result = self.precision_trim_clip(
                track_id=_int(track_id),
                clip_id=_int(clip_id),
                right_delta_ms=delta,
                ripple=bool(ripple),
                ripple_linked_audio=bool(ripple_linked_audio),
                dry_run=bool(dry_run),
            )
        result["target_ms"] = target
        result["edge"] = edge_text
        result["trim_delta_ms"] = delta
        return result

    def delete_clip(self, *, track_id: int, clip_id: int, ripple: bool = False) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        before = len(getattr(track, "clips", []) or [])
        if ripple:
            from app.timeline_model import ripple_delete_clips

            track.clips = ripple_delete_clips(list(getattr(track, "clips", []) or []), {_int(clip_id)})
        else:
            track.delete_clip(clip)
        self._after_timeline_mutation("Action ripple delete" if ripple else "Action delete clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "ripple": bool(ripple),
            "clip_count_before": before,
            "clip_count_after": len(getattr(track, "clips", []) or []),
        }

    def ripple_delete_selection(
        self,
        *,
        include_linked_audio: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        selected = self._selected_video_keys()
        if not selected:
            raise ValueError("no selected video clips")
        from app.timeline_model import ripple_delete_clips

        selected_by_track: dict[int, set[int]] = {}
        linked_audio_ids: set[int] = set()
        for track_id, clip_id in selected:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            self._assert_video_track_editable(track)
            selected_by_track.setdefault(_int(track_id), set()).add(_int(clip_id))
            linked_id = getattr(clip, "linked_audio_id", None)
            if include_linked_audio and linked_id is not None:
                linked_audio_ids.add(_int(linked_id, -1))

        video_results: list[dict[str, Any]] = []
        for track in getattr(self._require_owner(), "_tracks", []) or []:
            track_id = _int(getattr(track, "id", -1), -1)
            ids = selected_by_track.get(track_id)
            if not ids:
                continue
            before = list(getattr(track, "clips", []) or [])
            after = ripple_delete_clips(before, ids)
            video_results.append(
                {
                    "track_id": track_id,
                    "deleted_clip_ids": sorted(ids),
                    "clip_count_before": len(before),
                    "clip_count_after": len(after),
                    "remaining": [
                        {
                            "clip_id": _int(getattr(clip, "id", 0)),
                            "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
                            "timeline_out_ms": _int(getattr(clip, "timeline_out_ms", 0)),
                        }
                        for clip in after
                    ],
                }
            )
            if not dry_run:
                track.clips = after

        audio_results: list[dict[str, Any]] = []
        if include_linked_audio and linked_audio_ids:
            for audio_track in getattr(self._require_owner(), "_audio_tracks", []) or []:
                result = self._plan_audio_ripple_delete(audio_track, linked_audio_ids)
                if not result["deleted_clip_ids"]:
                    continue
                audio_results.append(result)
                if not dry_run:
                    self._apply_audio_ripple_delete(audio_track, result)

        if not dry_run:
            if hasattr(self._require_owner(), "_selected_clips"):
                setattr(self._require_owner(), "_selected_clips", [])
            self._after_timeline_mutation("Action ripple delete selection")
        return {
            "selection": [{"track_id": tid, "clip_id": cid} for tid, cid in selected],
            "deleted_video_count": sum(len(row["deleted_clip_ids"]) for row in video_results),
            "deleted_linked_audio_count": sum(len(row["deleted_clip_ids"]) for row in audio_results),
            "video_tracks": video_results,
            "audio_tracks": audio_results,
            "include_linked_audio": bool(include_linked_audio),
            "dry_run": bool(dry_run),
        }

    def timeline_edge_issues(self, *, track_id: int | None = None, frame_ms: int = 33) -> dict[str, Any]:
        owner = self._require_owner()
        from app.timeline_model import detect_timeline_edge_issues

        tracks: list[dict[str, Any]] = []
        total = 0
        target_track_id = _int(track_id, -1) if track_id is not None else None
        for track in getattr(owner, "_tracks", []) or []:
            tid = _int(getattr(track, "id", -1), -1)
            if target_track_id is not None and tid != target_track_id:
                continue
            issues = detect_timeline_edge_issues(list(getattr(track, "clips", []) or []), frame_ms=max(1, _int(frame_ms, 33)))
            total += len(issues)
            tracks.append({"track_id": tid, "issue_count": len(issues), "issues": issues})
        return {"track_count": len(tracks), "issue_count": total, "tracks": tracks, "frame_ms": max(1, _int(frame_ms, 33))}

    def cleanup_timeline_edges(
        self,
        *,
        track_id: int | None = None,
        frame_ms: int = 33,
        close_gaps: bool = True,
        trim_overlaps: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        from app.timeline_model import cleanup_timeline_micro_edges

        target_track_id = _int(track_id, -1) if track_id is not None else None
        tracks: list[dict[str, Any]] = []
        total_actions = 0
        for track in getattr(owner, "_tracks", []) or []:
            tid = _int(getattr(track, "id", -1), -1)
            if target_track_id is not None and tid != target_track_id:
                continue
            before = list(getattr(track, "clips", []) or [])
            cleaned, actions = cleanup_timeline_micro_edges(
                before,
                frame_ms=max(1, _int(frame_ms, 33)),
                close_gaps=bool(close_gaps),
                trim_overlaps=bool(trim_overlaps),
            )
            total_actions += len(actions)
            tracks.append(
                {
                    "track_id": tid,
                    "action_count": len(actions),
                    "actions": actions,
                    "clips": [
                        {
                            "clip_id": _int(getattr(clip, "id", 0)),
                            "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
                            "timeline_out_ms": _int(getattr(clip, "timeline_out_ms", 0)),
                            "source_in_ms": _int(getattr(clip, "source_in_ms", 0)),
                            "source_out_ms": _int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0))),
                        }
                        for clip in cleaned
                    ],
                }
            )
            if actions and not dry_run:
                track.clips = cleaned
        if total_actions and not dry_run:
            self._after_timeline_mutation("Action cleanup timeline edges")
        return {
            "track_count": len(tracks),
            "action_count": total_actions,
            "tracks": tracks,
            "frame_ms": max(1, _int(frame_ms, 33)),
            "close_gaps": bool(close_gaps),
            "trim_overlaps": bool(trim_overlaps),
            "dry_run": bool(dry_run),
        }

    def timeline_gaps(self, *, track_id: int | None = None, min_gap_ms: int = 1) -> dict[str, Any]:
        owner = self._require_owner()
        target_track_id = _int(track_id, -1) if track_id is not None else None
        threshold = max(1, _int(min_gap_ms, 1))
        tracks: list[dict[str, Any]] = []
        total = 0
        for track in getattr(owner, "_tracks", []) or []:
            tid = _int(getattr(track, "id", -1), -1)
            if target_track_id is not None and tid != target_track_id:
                continue
            gaps = self._track_gaps(track, min_gap_ms=threshold)
            total += len(gaps)
            tracks.append({"track_id": tid, "gap_count": len(gaps), "gaps": gaps})
        return {"track_count": len(tracks), "gap_count": total, "tracks": tracks, "min_gap_ms": threshold}

    def close_timeline_gap(
        self,
        *,
        track_id: int | None = None,
        at_ms: int | None = None,
        gap_index: int | None = None,
        min_gap_ms: int = 1,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        track = self._gap_target_track(track_id=track_id)
        gaps = self._track_gaps(track, min_gap_ms=max(1, _int(min_gap_ms, 1)))
        if not gaps:
            raise ValueError("no timeline gaps found")
        gap = self._select_gap(gaps, at_ms=at_ms, gap_index=gap_index)
        shift_count = 0
        for clip in getattr(track, "clips", []) or []:
            if _int(getattr(clip, "timeline_in_ms", 0)) >= _int(gap["end_ms"]):
                shift_count += 1
        if not dry_run:
            for clip in getattr(track, "clips", []) or []:
                if _int(getattr(clip, "timeline_in_ms", 0)) >= _int(gap["end_ms"]):
                    clip.timeline_in_ms = max(0, _int(getattr(clip, "timeline_in_ms", 0)) - _int(gap["duration_ms"]))
            track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            self._after_timeline_mutation("Action close timeline gap")
        return {
            "track_id": _int(getattr(track, "id", 0)),
            "gap": gap,
            "shifted_clip_count": shift_count,
            "dry_run": bool(dry_run),
        }

    def close_all_timeline_gaps(
        self,
        *,
        track_id: int | None = None,
        min_gap_ms: int = 1,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        target_ids = self._targeted_video_track_ids(track_id=track_id)
        threshold = max(1, _int(min_gap_ms, 1))
        tracks: list[dict[str, Any]] = []
        total_gaps = 0
        total_shifted = 0
        for track in getattr(self._require_owner(), "_tracks", []) or []:
            tid = _int(getattr(track, "id", -1), -1)
            if tid not in target_ids:
                continue
            clips = sorted(list(getattr(track, "clips", []) or []), key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            if not clips:
                tracks.append({"track_id": tid, "gap_count": 0, "shifted_clip_count": 0, "gaps": []})
                continue
            gaps = self._track_gaps(track, min_gap_ms=threshold)
            shifted = 0
            if gaps and not dry_run:
                cursor = _int(getattr(clips[0], "timeline_out_ms", 0))
                for clip in clips[1:]:
                    start, end = self._video_clip_bounds(clip)
                    if start - cursor >= threshold:
                        clip.timeline_in_ms = cursor
                        shifted += 1
                        cursor = cursor + max(0, end - start)
                    else:
                        cursor = max(cursor, end)
                track.clips = clips
                track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            elif gaps:
                shifted = sum(1 for gap in gaps for clip in clips if _int(getattr(clip, "timeline_in_ms", 0)) >= _int(gap["end_ms"]))
            total_gaps += len(gaps)
            total_shifted += shifted
            tracks.append({"track_id": tid, "gap_count": len(gaps), "shifted_clip_count": shifted, "gaps": gaps})
        if total_shifted and not dry_run:
            self._after_timeline_mutation("Action close all timeline gaps")
        return {
            "track_count": len(tracks),
            "gap_count": total_gaps,
            "shifted_clip_count": total_shifted,
            "tracks": tracks,
            "min_gap_ms": threshold,
            "dry_run": bool(dry_run),
        }

    def range_delete(
        self,
        *,
        start_ms: int | None = None,
        end_ms: int | None = None,
        track_id: int | None = None,
        ripple: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        start, end = self._resolve_edit_range(start_ms=start_ms, end_ms=end_ms)
        duration = max(0, end - start)
        target_ids = self._targeted_video_track_ids(track_id=track_id)
        from app.timeline_model import split_clips_at_project_ms

        tracks: list[dict[str, Any]] = []
        deleted_total = 0
        for track in getattr(self._require_owner(), "_tracks", []) or []:
            tid = _int(getattr(track, "id", -1), -1)
            if tid not in target_ids:
                continue
            before = copy.deepcopy(list(getattr(track, "clips", []) or []))
            split = split_clips_at_project_ms(split_clips_at_project_ms(before, start), end)
            kept: list[Any] = []
            deleted: list[dict[str, int]] = []
            for clip in split:
                clip_start, clip_end = self._video_clip_bounds(clip)
                if clip_start >= start and clip_end <= end:
                    deleted.append(
                        {
                            "clip_id": _int(getattr(clip, "id", 0)),
                            "timeline_in_ms": clip_start,
                            "timeline_out_ms": clip_end,
                        }
                    )
                    continue
                if ripple and clip_start >= end:
                    clip.timeline_in_ms = max(0, _int(getattr(clip, "timeline_in_ms", 0)) - duration)
                kept.append(clip)
            kept.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            deleted_total += len(deleted)
            tracks.append(
                {
                    "track_id": tid,
                    "deleted_clip_count": len(deleted),
                    "deleted": deleted,
                    "clips": [
                        {
                            "clip_id": _int(getattr(clip, "id", 0)),
                            "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", 0)),
                            "timeline_out_ms": _int(getattr(clip, "timeline_out_ms", 0)),
                            "source_in_ms": _int(getattr(clip, "source_in_ms", 0)),
                            "source_out_ms": _int(getattr(clip, "effective_source_out_ms", getattr(clip, "source_out_ms", 0))),
                        }
                        for clip in kept
                    ],
                }
            )
            if not dry_run:
                track.clips = kept
        if deleted_total and not dry_run:
            self._after_timeline_mutation("Action extract range" if ripple else "Action lift range")
        return {
            "start_ms": start,
            "end_ms": end,
            "duration_ms": duration,
            "ripple": bool(ripple),
            "target_track_ids": target_ids,
            "deleted_clip_count": deleted_total,
            "tracks": tracks,
            "dry_run": bool(dry_run),
        }

    def lift_range(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["ripple"] = False
        return self.range_delete(**kwargs)

    def extract_range(self, **kwargs: Any) -> dict[str, Any]:
        kwargs["ripple"] = True
        return self.range_delete(**kwargs)

    def duplicate_clip(self, *, track_id: int, clip_id: int, at_ms: int | None = None) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        duplicate = copy.deepcopy(clip)
        duplicate.id = self._next_clip_id(track)
        if at_ms is None:
            duplicate.timeline_in_ms = _int(getattr(clip, "timeline_out_ms", 0))
        else:
            duplicate.timeline_in_ms = max(0, _int(at_ms))
        track.clips.append(duplicate)
        track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        self._after_timeline_mutation("Action duplicate clip")
        return {
            "track_id": _int(track_id),
            "source_clip_id": _int(clip_id),
            "new_clip_id": _int(getattr(duplicate, "id", 0)),
            "timeline_in_ms": _int(getattr(duplicate, "timeline_in_ms", 0)),
        }

    def copy_clips(
        self,
        *,
        clips: Sequence[Mapping[str, Any]] | None = None,
        use_selection: bool = True,
        include_linked_audio: bool = True,
    ) -> dict[str, Any]:
        records = self._clipboard_records_from_request(
            clips=clips,
            use_selection=use_selection,
            include_linked_audio=include_linked_audio,
        )
        owner = self._require_owner()
        setattr(owner, "_action_clipboard", {"kind": "video_clips", "records": records})
        linked_audio_count = sum(1 for row in records if isinstance(row.get("linked_audio"), Mapping))
        return {
            "kind": "video_clips",
            "count": len(records),
            "linked_audio_count": linked_audio_count,
            "track_ids": sorted({_int(row.get("track_id"), 0) for row in records}),
            "base_ms": min((_int(row.get("timeline_in_ms"), 0) for row in records), default=0),
        }

    def cut_clips_to_clipboard(
        self,
        *,
        clips: Sequence[Mapping[str, Any]] | None = None,
        use_selection: bool = True,
        include_linked_audio: bool = True,
    ) -> dict[str, Any]:
        copied = self.copy_clips(clips=clips, use_selection=use_selection, include_linked_audio=include_linked_audio)
        delete_keys = [(_int(row.get("track_id")), _int(row.get("clip_id"))) for row in self._clipboard_records()]
        linked_audio_keys = []
        if include_linked_audio:
            for row in self._clipboard_records():
                linked = row.get("linked_audio")
                if isinstance(linked, Mapping):
                    key = (_int(linked.get("track_id"), -1), _int(linked.get("clip_id"), -1))
                    if key[0] >= 0 and key[1] >= 0 and key not in linked_audio_keys:
                        linked_audio_keys.append(key)
        deleted: list[dict[str, Any]] = []
        for track_id, clip_id in delete_keys:
            try:
                deleted.append(self.delete_clip(track_id=track_id, clip_id=clip_id, ripple=False))
            except Exception:
                continue
        deleted_audio: list[dict[str, Any]] = []
        for track_id, clip_id in linked_audio_keys:
            try:
                deleted_audio.append(self.delete_audio_clip(track_id=track_id, clip_id=clip_id))
            except Exception:
                continue
        self._after_timeline_mutation("Action cut clips to clipboard")
        return {
            **copied,
            "deleted_count": len(deleted),
            "deleted_audio_count": len(deleted_audio),
            "deleted": deleted,
            "deleted_audio": deleted_audio,
        }

    def paste_clips(
        self,
        *,
        at_ms: int | None = None,
        target_track_id: int | None = None,
        include_linked_audio: bool = True,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        records = self._clipboard_records()
        if not records:
            raise ValueError("clipboard is empty")
        base_ms = min(_int(row.get("timeline_in_ms"), 0) for row in records)
        paste_base = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms))
        target_track = None
        if target_track_id is not None:
            target_track = self._video_track(_int(target_track_id))
        pasted: list[dict[str, Any]] = []
        for record in records:
            source_clip = copy.deepcopy(record.get("clip"))
            if source_clip is None:
                continue
            track = target_track or self._video_track(_int(record.get("track_id"), 0))
            original_video_in = _int(record.get("timeline_in_ms"), base_ms)
            new_video_in = paste_base + max(0, original_video_in - base_ms)
            source_clip.id = self._next_clip_id(track)
            linked_audio_row = record.get("linked_audio") if include_linked_audio else None
            source_clip.linked_audio_id = None
            source_clip.timeline_in_ms = new_video_in
            new_audio_row = self._paste_linked_audio_record(linked_audio_row, original_video_in=original_video_in, new_video_in=new_video_in)
            if new_audio_row is not None:
                source_clip.linked_audio_id = _int(new_audio_row.get("clip_id"), 0)
            track.clips.append(source_clip)
            track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            row = {
                "track_id": _int(getattr(track, "id", 0)),
                "clip_id": _int(getattr(source_clip, "id", 0)),
                "timeline_in_ms": _int(getattr(source_clip, "timeline_in_ms", 0)),
            }
            if new_audio_row is not None:
                row["linked_audio"] = new_audio_row
            pasted.append(row)
        if not pasted:
            raise ValueError("clipboard had no pasteable clips")
        setattr(owner, "_selected_clips", [(row["track_id"], row["clip_id"]) for row in pasted])
        self._broadcast_selection()
        self._after_timeline_mutation("Action paste clips")
        return {
            "count": len(pasted),
            "linked_audio_count": sum(1 for row in pasted if isinstance(row.get("linked_audio"), Mapping)),
            "base_ms": paste_base,
            "pasted": pasted,
        }

    def paste_clipboard_edit(
        self,
        *,
        mode: str,
        at_ms: int | None = None,
        target_track_id: int | None = None,
        include_linked_audio: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        records = self._clipboard_records()
        if not records:
            raise ValueError("clipboard is empty")
        edit_mode = str(mode or "insert").strip().lower()
        if edit_mode not in {"insert", "overwrite"}:
            raise ValueError("mode must be insert or overwrite")
        paste_base = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms))
        source_base, source_end = self._clipboard_record_span(records)
        duration = max(1, source_end - source_base)
        target_track_ids = self._clipboard_target_track_ids(records, target_track_id=target_track_id)
        linked_count = sum(1 for row in records if include_linked_audio and isinstance(row.get("linked_audio"), Mapping))

        shift_count = 0
        delete_count = 0
        for tid in target_track_ids:
            track = self._video_track(tid)
            clips = list(getattr(track, "clips", []) or [])
            if edit_mode == "insert":
                shift_count += sum(
                    1
                    for clip in clips
                    if _int(getattr(clip, "timeline_in_ms", 0)) >= paste_base
                    or (
                        _int(getattr(clip, "timeline_in_ms", 0)) < paste_base
                        < _int(getattr(clip, "timeline_out_ms", 0))
                    )
                )
            else:
                preview = self.range_delete(
                    start_ms=paste_base,
                    end_ms=paste_base + duration,
                    track_id=tid,
                    ripple=False,
                    dry_run=True,
                )
                delete_count += _int(preview.get("deleted_clip_count"), 0)

        if dry_run:
            return {
                "mode": edit_mode,
                "count": len(records),
                "linked_audio_count": linked_count,
                "base_ms": paste_base,
                "duration_ms": duration,
                "target_track_ids": target_track_ids,
                "would_shift_clip_count": shift_count if edit_mode == "insert" else 0,
                "would_delete_clip_count": delete_count if edit_mode == "overwrite" else 0,
                "dry_run": True,
            }

        if edit_mode == "insert":
            from app.timeline_model import split_clips_at_project_ms

            for tid in target_track_ids:
                track = self._video_track(tid)
                track.clips = split_clips_at_project_ms(list(getattr(track, "clips", []) or []), paste_base)
                for clip in getattr(track, "clips", []) or []:
                    if _int(getattr(clip, "timeline_in_ms", 0)) >= paste_base:
                        clip.timeline_in_ms = _int(getattr(clip, "timeline_in_ms", 0)) + duration
                track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
        else:
            for tid in target_track_ids:
                self.range_delete(
                    start_ms=paste_base,
                    end_ms=paste_base + duration,
                    track_id=tid,
                    ripple=False,
                    dry_run=False,
                )

        pasted = self.paste_clips(
            at_ms=paste_base,
            target_track_id=_int(target_track_id) if target_track_id is not None else None,
            include_linked_audio=include_linked_audio,
        )
        self._after_timeline_mutation(f"Action {edit_mode} clipboard")
        return {
            "mode": edit_mode,
            "duration_ms": duration,
            "target_track_ids": target_track_ids,
            "shifted_clip_count": shift_count if edit_mode == "insert" else 0,
            "deleted_clip_count": delete_count if edit_mode == "overwrite" else 0,
            **pasted,
        }

    def set_clip_speed(self, *, track_id: int, clip_id: int, speed: float) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        speed_value = max(0.05, min(16.0, _float(speed, 1.0)))
        if abs(speed_value - 1.0) < 0.001:
            clip.speed_segments = []
        else:
            from app.timeline_model import SpeedSegment

            clip.speed_segments = [
                SpeedSegment(
                    start_ms=_int(getattr(clip, "source_in_ms", 0)),
                    end_ms=_int(getattr(clip, "effective_source_out_ms", 0)),
                    speed=speed_value,
                )
            ]
        self._after_timeline_mutation("Action set clip speed")
        return {"track_id": _int(track_id), "clip_id": _int(clip_id), "speed": speed_value}

    def set_clip_fade(
        self,
        *,
        track_id: int,
        clip_id: int,
        fade_in_ms: int = 0,
        fade_out_ms: int = 0,
        replace_existing: bool = True,
    ) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        from app.timeline_model import FadeSegment

        source_in = _int(getattr(clip, "source_in_ms", 0))
        source_out = _int(getattr(clip, "effective_source_out_ms", 0))
        duration = max(1, source_out - source_in)
        fades = [] if replace_existing else list(getattr(clip, "fades", []) or [])
        in_ms = max(0, min(_int(fade_in_ms), duration))
        out_ms = max(0, min(_int(fade_out_ms), duration))
        if in_ms > 0:
            fades.append(FadeSegment(source_in, min(source_out, source_in + in_ms), "in"))
        if out_ms > 0:
            fades.append(FadeSegment(max(source_in, source_out - out_ms), source_out, "out"))
        clip.fades = fades
        self._after_timeline_mutation("Action set clip fade")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "fade_in_ms": in_ms,
            "fade_out_ms": out_ms,
            "fade_count": len(fades),
        }

    def import_to_timeline(
        self,
        *,
        path: str,
        kind: str = "",
        track_id: int | None = None,
        at_ms: int | None = None,
        duration_ms: int | None = None,
        name: str = "",
    ) -> dict[str, Any]:
        owner = self._require_owner()
        media_path = Path(str(path or "")).expanduser()
        if not media_path.is_file():
            raise ValueError(f"media path does not exist: {media_path}")
        self._register_media_path(media_path)
        kind_text = str(kind or "").strip().lower()
        if not kind_text:
            from app.audio_tracks import is_audio_path, is_video_path

            if is_audio_path(media_path):
                kind_text = "audio"
            elif is_video_path(media_path):
                kind_text = "video"
            else:
                raise ValueError(f"unsupported media extension: {media_path.suffix}")
        if kind_text == "video":
            track = self._video_track(track_id) if track_id is not None else None
            duration = _int(duration_ms, 0)
            if duration <= 0:
                try:
                    from app.video_editor_window import probe_video_duration_ms

                    duration = _int(probe_video_duration_ms(media_path), 0)
                except Exception:
                    duration = 0
            duration = max(1, duration or 1000)
            start = max(0, _int(at_ms)) if at_ms is not None else 0
            if track is None and self._owner_uses_legacy_video_editor_tracks():
                track, clip = self._create_editor_video_track_from_media(
                    media_path,
                    start_ms=start,
                    duration_ms=duration,
                )
                self._after_timeline_mutation("Action import video to timeline")
                return {
                    "kind": "video",
                    "path": str(media_path.resolve()),
                    "track_id": _int(getattr(track, "id", 0)),
                    "clip_id": _int(getattr(clip, "id", 0)) if clip is not None else 0,
                    "timeline_in_ms": start,
                    "duration_ms": duration,
                }
            if track is None:
                from app.timeline_model import VideoTrack

                tracks = list(getattr(owner, "_tracks", []) or [])
                track = VideoTrack(id=self._next_track_id(tracks))
                tracks.append(track)
                setattr(owner, "_tracks", tracks)
            clips = getattr(track, "clips", None)
            if not isinstance(clips, list):
                track.clips = []
                clips = track.clips
            start = max(0, _int(at_ms)) if at_ms is not None else max(
                (_int(getattr(clip, "timeline_out_ms", 0)) for clip in clips),
                default=0,
            )
            from app.timeline_model import NodeGraph, VideoClip

            clip = VideoClip(
                id=self._next_clip_id(track),
                source_path=media_path.resolve(),
                source_duration_ms=duration,
                timeline_in_ms=start,
                source_in_ms=0,
                source_out_ms=duration,
                node_graph=NodeGraph.default(),
            )
            clips.append(clip)
            clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            try:
                setattr(track, "clips_explicit", True)
            except Exception:
                pass
            clip_thumb = getattr(owner, "_start_thumbnail_extraction_for_clip", None)
            if callable(clip_thumb):
                try:
                    clip_thumb(clip, _int(getattr(track, "id", 0)))
                except Exception:
                    pass
            self._after_timeline_mutation("Action import video to timeline")
            return {
                "kind": "video",
                "path": str(media_path.resolve()),
                "track_id": _int(getattr(track, "id", 0)),
                "clip_id": _int(getattr(clip, "id", 0)),
                "timeline_in_ms": start,
                "duration_ms": duration,
            }
        if kind_text == "audio":
            track = self._audio_track(track_id) if track_id is not None else None
            if track is None:
                from app.audio_tracks import AudioTrack

                tracks = list(getattr(owner, "_audio_tracks", []) or [])
                track = AudioTrack(id=self._next_track_id(tracks), label=str(name or ""))
                tracks.append(track)
                setattr(owner, "_audio_tracks", tracks)
            duration = _int(duration_ms, 0)
            if duration <= 0:
                try:
                    from app.audio_tracks import probe_audio_duration_ms

                    duration = _int(probe_audio_duration_ms(media_path), 0)
                except Exception:
                    duration = 0
            duration = max(1, duration or 1000)
            clips = getattr(track, "clips", None)
            if not isinstance(clips, list):
                track.clips = []
                clips = track.clips
            start = max(0, _int(at_ms)) if at_ms is not None else max(
                (
                    _int(getattr(clip, "offset_ms", 0))
                    + _int(getattr(clip, "effective_length_ms", 0))
                    for clip in clips
                ),
                default=0,
            )
            from app.audio_tracks import AudioClip

            clip = AudioClip(
                id=self._next_audio_clip_id(),
                source_path=media_path.resolve(),
                duration_ms=duration,
                offset_ms=start,
                trim_start_ms=0,
                trim_end_ms=duration,
            )
            clips.append(clip)
            clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
            self._update_audio_track(track)
            self._after_timeline_mutation("Action import audio to timeline")
            return {
                "kind": "audio",
                "path": str(media_path.resolve()),
                "track_id": _int(getattr(track, "id", 0)),
                "clip_id": _int(getattr(clip, "id", 0)),
                "timeline_in_ms": start,
                "duration_ms": duration,
            }
        raise ValueError("kind must be video or audio")

    def extract_audio_from_video(
        self,
        *,
        track_id: int | None = None,
        clip_id: int | None = None,
        audio_track_id: int | None = None,
        at_ms: int | None = None,
        link: bool = True,
        name: str = "",
    ) -> dict[str, Any]:
        owner = self._require_owner()
        video_track, video_clip = self._resolve_video_clip_for_audio_extract(
            track_id=track_id,
            clip_id=clip_id,
        )
        source = self._video_audio_source_path(video_track, video_clip)
        if source is None:
            raise ValueError("selected video clip has no source media")
        media_path = Path(source).expanduser()
        if not media_path.is_file():
            raise ValueError(f"media path does not exist: {media_path}")

        from app.audio_tracks import AudioClip, AudioTrack, probe_audio_duration_ms

        duration = max(0, _int(probe_audio_duration_ms(media_path), 0))
        if duration <= 0:
            raise ValueError("video source has no extractable audio stream")

        clip_start = max(0, _int(getattr(video_clip, "timeline_in_ms", getattr(video_track, "offset_ms", 0))))
        audio_start = max(0, _int(at_ms, clip_start)) if at_ms is not None else clip_start
        trim_start = max(0, _int(getattr(video_clip, "source_in_ms", 0), 0))
        trim_end = _int(getattr(video_clip, "effective_source_out_ms", 0), 0)
        if trim_end <= 0:
            trim_end = _int(getattr(video_clip, "source_out_ms", 0), 0)
        if trim_end <= 0:
            trim_end = duration
        trim_start = min(trim_start, duration)
        trim_end = max(trim_start + 1, min(trim_end, duration))

        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        created_track = False
        if audio_track_id is not None:
            audio_track = self._audio_track(_int(audio_track_id))
        else:
            audio_track = AudioTrack(
                id=self._next_track_id(tracks),
                label=str(name or "Extracted Audio"),
            )
            tracks.append(audio_track)
            setattr(owner, "_audio_tracks", tracks)
            created_track = True
            self._advance_owner_next_track_id(_int(getattr(audio_track, "id", 0)))

        clips = getattr(audio_track, "clips", None)
        if not isinstance(clips, list):
            audio_track.clips = []
            clips = audio_track.clips
        audio_clip = AudioClip(
            id=self._next_audio_clip_id(),
            source_path=media_path.resolve(),
            duration_ms=duration,
            offset_ms=audio_start,
            trim_start_ms=trim_start,
            trim_end_ms=trim_end,
        )
        clips.append(audio_clip)
        clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))

        if link and video_clip is not None:
            try:
                setattr(video_clip, "linked_audio_id", _int(getattr(audio_clip, "id", 0)))
            except Exception:
                pass

        self._sync_audio_track_ui(audio_track, created=created_track, clip=audio_clip)
        self._after_timeline_mutation("Action extract audio from video")
        return {
            "source_path": str(media_path.resolve()),
            "video_track_id": _int(getattr(video_track, "id", 0)),
            "video_clip_id": _int(getattr(video_clip, "id", 0)),
            "audio_track_id": _int(getattr(audio_track, "id", 0)),
            "audio_clip_id": _int(getattr(audio_clip, "id", 0)),
            "timeline_in_ms": audio_start,
            "duration_ms": duration,
            "trim_start_ms": trim_start,
            "trim_end_ms": trim_end,
            "created_track": created_track,
            "linked": bool(link and getattr(video_clip, "linked_audio_id", None) == getattr(audio_clip, "id", None)),
        }

    def move_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        at_ms: int,
        allow_overlap: bool = False,
    ) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        self._assert_video_track_editable(track)
        old = _int(getattr(clip, "timeline_in_ms", 0))
        target = max(0, _int(at_ms))
        if allow_overlap:
            clip.timeline_in_ms = target
            track.clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0)))
            moved = True
        else:
            moved = bool(track.move_clip(clip, target))
        if not moved:
            raise ValueError("clip move would overlap another clip")
        self._after_timeline_mutation("Action move clip")
        return {"track_id": _int(track_id), "clip_id": _int(clip_id), "old_ms": old, "new_ms": target}

    def move_clip_snapped(
        self,
        *,
        track_id: int,
        clip_id: int,
        at_ms: int,
        snap_ms: int = 200,
        include_playhead: bool = True,
        include_markers: bool = True,
        extra_snap_targets: list[int] | tuple[int, ...] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        track, clip = self._video_track_and_clip(track_id, clip_id)
        self._assert_video_track_editable(track)
        from app.timeline_model import apply_drag_constraints_detail

        old = _int(getattr(clip, "timeline_in_ms", 0))
        requested = max(0, _int(at_ms))
        targets = self._timeline_snap_targets(
            include_playhead=include_playhead,
            include_markers=include_markers,
            extra_snap_targets=extra_snap_targets,
        )
        clip_rows = []
        dragged_index = 0
        for idx, row in enumerate(list(getattr(track, "clips", []) or [])):
            row_start = _int(getattr(row, "timeline_in_ms", 0))
            row_end = _int(getattr(row, "timeline_out_ms", row_start))
            length = _int(getattr(row, "effective_length_ms", row_end - row_start), row_end - row_start)
            clip_rows.append(
                {
                    "id": _int(getattr(row, "id", idx), idx),
                    "timeline_in_ms": row_start,
                    "timeline_out_ms": row_end,
                    "effective_length_ms": max(0, length),
                }
            )
            if row is clip:
                dragged_index = idx
        detail_native = None
        try:
            from app.native_worker import native_timeline_drag_constraints

            detail_native = native_timeline_drag_constraints(
                clip_rows,
                dragged_index=dragged_index,
                desired_timeline_in_ms=requested,
                snap_ms=max(0, _int(snap_ms, 200)),
                extra_snap_targets=targets,
            )
        except Exception:
            detail_native = None
        if isinstance(detail_native, dict):
            new_ms = max(0, _int(detail_native.get("timeline_in_ms", requested), requested))
            snapped = bool(detail_native.get("snapped", False))
            snap_target_ms = detail_native.get("snap_target_ms")
            snap_edge = str(detail_native.get("snap_edge") or "")
            snap_source = str(detail_native.get("snap_source") or "")
            collided = bool(detail_native.get("collided", False))
            clamped = bool(detail_native.get("clamped", False))
            clamp_target_ms = detail_native.get("clamp_target_ms")
            constraint_backend = "rust_worker"
        else:
            detail = apply_drag_constraints_detail(
                list(getattr(track, "clips", []) or []),
                clip,
                requested,
                snap_ms=max(0, _int(snap_ms, 200)),
                extra_snap_targets=targets,
            )
            new_ms = max(0, _int(detail.timeline_in_ms))
            snapped = bool(detail.snapped)
            snap_target_ms = detail.snap_target_ms
            snap_edge = str(detail.snap_edge or "")
            snap_source = str(detail.snap_source or "")
            collided = bool(detail.collided)
            clamped = bool(detail.clamped)
            clamp_target_ms = detail.clamp_target_ms
            constraint_backend = "python"
        changed = new_ms != old
        if not dry_run:
            moved = bool(track.move_clip(clip, new_ms))
            if not moved:
                raise ValueError("snapped clip move would overlap another clip")
            self._after_timeline_mutation("Action snapped move clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "old_ms": old,
            "requested_ms": requested,
            "new_ms": new_ms,
            "changed": bool(changed),
            "snap_ms": max(0, _int(snap_ms, 200)),
            "snap_targets": targets,
            "snapped": snapped,
            "snap_target_ms": snap_target_ms,
            "snap_edge": snap_edge,
            "snap_source": snap_source,
            "collided": collided,
            "clamped": clamped,
            "clamp_target_ms": clamp_target_ms,
            "constraint_backend": constraint_backend,
            "dry_run": bool(dry_run),
            "owner": "editor" if owner is not None else "none",
        }

    def move_linked_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        delta_ms: int,
        strict_links: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        from app.timeline_model import plan_linked_timeline_move

        delta = _int(delta_ms)
        plan = plan_linked_timeline_move(
            getattr(owner, "_tracks", []) or [],
            getattr(owner, "_audio_tracks", []) or [],
            [(_int(track_id), _int(clip_id))],
            delta,
            strict_links=bool(strict_links),
            strict_selection=True,
        )
        result = self._linked_move_result(plan)
        result.update({"track_id": _int(track_id), "clip_id": _int(clip_id), "delta_ms": delta, "dry_run": bool(dry_run)})
        if not plan.ok:
            raise ValueError(f"linked move blocked: {plan.blocked_reason}")
        if not dry_run:
            self._apply_linked_move_plan(plan)
            self._after_timeline_mutation("Action linked clip move")
        return result

    def move_selection(
        self,
        *,
        delta_ms: int,
        strict_links: bool = True,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        selected = self._selected_video_keys()
        if not selected:
            raise ValueError("no selected video clips")
        from app.timeline_model import plan_linked_timeline_move

        delta = _int(delta_ms)
        plan = plan_linked_timeline_move(
            getattr(owner, "_tracks", []) or [],
            getattr(owner, "_audio_tracks", []) or [],
            selected,
            delta,
            strict_links=bool(strict_links),
            strict_selection=True,
        )
        result = self._linked_move_result(plan)
        result.update(
            {
                "selection": [{"track_id": tid, "clip_id": cid} for tid, cid in selected],
                "selected_count": len(selected),
                "delta_ms": delta,
                "dry_run": bool(dry_run),
            }
        )
        if not plan.ok:
            raise ValueError(f"selection move blocked: {plan.blocked_reason}")
        if not dry_run and (plan.video_starts or plan.audio_offsets):
            self._apply_linked_move_plan(plan)
            self._after_timeline_mutation("Action move selected clips")
        return result

    def nudge_clip(self, *, track_id: int, clip_id: int, delta_ms: int, allow_overlap: bool = False) -> dict[str, Any]:
        _track, clip = self._video_track_and_clip(track_id, clip_id)
        return self.move_clip(
            track_id=track_id,
            clip_id=clip_id,
            at_ms=_int(getattr(clip, "timeline_in_ms", 0)) + _int(delta_ms),
            allow_overlap=allow_overlap,
        )

    def slip_clip(self, *, track_id: int, clip_id: int, delta_ms: int, dry_run: bool = False) -> dict[str, Any]:
        track, clip = self._video_track_and_clip(track_id, clip_id)
        self._assert_video_track_editable(track)
        from app.timeline_model import slip_clip_source_window

        old = self._clip_edit_state(clip)
        slipped = slip_clip_source_window(clip, _int(delta_ms))
        new = self._clip_edit_state(slipped)
        changed = old != new
        if not dry_run and changed:
            clip.source_in_ms = _int(getattr(slipped, "source_in_ms", getattr(clip, "source_in_ms", 0)))
            clip.source_out_ms = _int(getattr(slipped, "source_out_ms", getattr(clip, "source_out_ms", 0)))
            self._after_timeline_mutation("Action slip clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "delta_ms": _int(delta_ms),
            "old": old,
            "new": new,
            "applied_delta_ms": _int(new.get("source_in_ms", 0)) - _int(old.get("source_in_ms", 0)),
            "changed": bool(changed),
            "dry_run": bool(dry_run),
        }

    def roll_edit(
        self,
        *,
        track_id: int,
        left_clip_id: int,
        right_clip_id: int,
        delta_ms: int,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        track = self._video_track(track_id)
        self._assert_video_track_editable(track)
        from app.timeline_model import roll_edit_adjacent

        clips = list(getattr(track, "clips", []) or [])
        old = self._clip_states_by_id(clips, (left_clip_id, right_clip_id))
        result = roll_edit_adjacent(clips, _int(left_clip_id), _int(right_clip_id), _int(delta_ms))
        new = self._clip_states_by_id(result, (left_clip_id, right_clip_id))
        changed = old != new
        if not dry_run and changed:
            track.clips = result
            self._after_timeline_mutation("Action roll edit")
        return {
            "track_id": _int(track_id),
            "left_clip_id": _int(left_clip_id),
            "right_clip_id": _int(right_clip_id),
            "delta_ms": _int(delta_ms),
            "old": old,
            "new": new,
            "applied_delta_ms": (
                _int(new[str(_int(left_clip_id))]["timeline_out_ms"])
                - _int(old[str(_int(left_clip_id))]["timeline_out_ms"])
            ),
            "changed": bool(changed),
            "dry_run": bool(dry_run),
        }

    def slide_clip(self, *, track_id: int, clip_id: int, delta_ms: int, dry_run: bool = False) -> dict[str, Any]:
        track = self._video_track(track_id)
        self._assert_video_track_editable(track)
        from app.timeline_model import slide_clip_between_neighbors

        clips = list(getattr(track, "clips", []) or [])
        old_clip_ids = self._slide_neighbor_ids(clips, clip_id)
        old = self._clip_states_by_id(clips, old_clip_ids)
        result = slide_clip_between_neighbors(clips, _int(clip_id), _int(delta_ms))
        new = self._clip_states_by_id(result, old_clip_ids)
        changed = old != new
        if not dry_run and changed:
            track.clips = result
            self._after_timeline_mutation("Action slide clip")
        clip_key = str(_int(clip_id))
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "delta_ms": _int(delta_ms),
            "old": old,
            "new": new,
            "applied_delta_ms": _int(new[clip_key]["timeline_in_ms"]) - _int(old[clip_key]["timeline_in_ms"]),
            "changed": bool(changed),
            "dry_run": bool(dry_run),
        }

    def link_audio_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        audio_track_id: int | None = None,
        audio_clip_id: int | None = None,
        nearest: bool = True,
    ) -> dict[str, Any]:
        _track, clip = self._video_track_and_clip(track_id, clip_id)
        old = getattr(clip, "linked_audio_id", None)
        if audio_clip_id is None:
            if not nearest:
                raise ValueError("audio_clip_id is required when nearest=false")
            audio_track, audio_clip, distance = self._nearest_audio_clip(clip, audio_track_id=audio_track_id)
        else:
            audio_track, audio_clip = self._audio_track_and_clip(
                audio_track_id if audio_track_id is not None else self._find_audio_track_id_for_clip(audio_clip_id),
                audio_clip_id,
            )
            distance = abs(_int(getattr(audio_clip, "offset_ms", 0)) - _int(getattr(clip, "timeline_in_ms", 0)))
        clip.linked_audio_id = _int(getattr(audio_clip, "id", 0))
        self._after_timeline_mutation("Action link audio")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "old_linked_audio_id": old,
            "linked_audio_id": _int(getattr(audio_clip, "id", 0)),
            "audio_track_id": _int(getattr(audio_track, "id", 0)),
            "sync_offset_ms": _int(getattr(audio_clip, "offset_ms", 0)) - _int(getattr(clip, "timeline_in_ms", 0)),
            "distance_ms": _int(distance),
        }

    def unlink_audio_clip(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
        _track, clip = self._video_track_and_clip(track_id, clip_id)
        old = getattr(clip, "linked_audio_id", None)
        clip.linked_audio_id = None
        self._after_timeline_mutation("Action unlink audio")
        return {"track_id": _int(track_id), "clip_id": _int(clip_id), "old_linked_audio_id": old, "linked_audio_id": None}

    def set_linked_clip_sync_offset(
        self,
        *,
        track_id: int,
        clip_id: int,
        sync_offset_ms: int,
    ) -> dict[str, Any]:
        _track, clip = self._video_track_and_clip(track_id, clip_id)
        audio_track, audio_clip = self._linked_audio_track_and_clip(clip)
        old = _int(getattr(audio_clip, "offset_ms", 0)) - _int(getattr(clip, "timeline_in_ms", 0))
        new_offset = max(0, _int(getattr(clip, "timeline_in_ms", 0)) + _int(sync_offset_ms))
        self._assert_audio_offset_available(audio_track, audio_clip, new_offset)
        audio_clip.offset_ms = new_offset
        self._update_audio_track(audio_track)
        self._after_timeline_mutation("Action set linked sync offset")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "audio_track_id": _int(getattr(audio_track, "id", 0)),
            "audio_clip_id": _int(getattr(audio_clip, "id", 0)),
            "old_sync_offset_ms": old,
            "sync_offset_ms": _int(sync_offset_ms),
            "audio_offset_ms": new_offset,
        }

    def j_cut_linked_clip(self, *, track_id: int, clip_id: int, extend_ms: int = 500) -> dict[str, Any]:
        _track, clip = self._video_track_and_clip(track_id, clip_id)
        audio_track, audio_clip = self._linked_audio_track_and_clip(clip)
        old = self._audio_clip_edit_state(audio_clip)
        amount = max(1, _int(extend_ms, 500))
        old_trim = _int(getattr(audio_clip, "trim_start_ms", 0))
        actual = min(amount, old_trim)
        if actual <= 0:
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "audio_track_id": _int(getattr(audio_track, "id", 0)),
                "audio_clip_id": _int(getattr(audio_clip, "id", 0)),
                "changed": False,
                "reason": "audio trim_start already at source start",
                "old": old,
                "new": old,
            }
        new_offset = max(0, _int(getattr(audio_clip, "offset_ms", 0)) - actual)
        self._assert_audio_offset_available(audio_track, audio_clip, new_offset)
        audio_clip.trim_start_ms = old_trim - actual
        audio_clip.offset_ms = new_offset
        self._update_audio_track(audio_track)
        self._after_timeline_mutation("Action J-cut linked clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "audio_track_id": _int(getattr(audio_track, "id", 0)),
            "audio_clip_id": _int(getattr(audio_clip, "id", 0)),
            "requested_extend_ms": amount,
            "applied_extend_ms": actual,
            "changed": True,
            "old": old,
            "new": self._audio_clip_edit_state(audio_clip),
        }

    def l_cut_linked_clip(self, *, track_id: int, clip_id: int, extend_ms: int = 500) -> dict[str, Any]:
        _track, clip = self._video_track_and_clip(track_id, clip_id)
        audio_track, audio_clip = self._linked_audio_track_and_clip(clip)
        old = self._audio_clip_edit_state(audio_clip)
        amount = max(1, _int(extend_ms, 500))
        duration = max(1, _int(getattr(audio_clip, "duration_ms", 0)) or _int(getattr(audio_clip, "effective_trim_end_ms", 0)))
        old_end = _int(getattr(audio_clip, "effective_trim_end_ms", getattr(audio_clip, "trim_end_ms", duration)), duration)
        actual = min(amount, max(0, duration - old_end))
        if actual <= 0:
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "audio_track_id": _int(getattr(audio_track, "id", 0)),
                "audio_clip_id": _int(getattr(audio_clip, "id", 0)),
                "changed": False,
                "reason": "audio trim_end already at source end",
                "old": old,
                "new": old,
            }
        new_end = old_end + actual
        self._assert_audio_window_available(audio_track, audio_clip, _int(getattr(audio_clip, "offset_ms", 0)), new_end - _int(getattr(audio_clip, "trim_start_ms", 0)))
        audio_clip.trim_end_ms = new_end
        self._update_audio_track(audio_track)
        self._after_timeline_mutation("Action L-cut linked clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "audio_track_id": _int(getattr(audio_track, "id", 0)),
            "audio_clip_id": _int(getattr(audio_clip, "id", 0)),
            "requested_extend_ms": amount,
            "applied_extend_ms": actual,
            "changed": True,
            "old": old,
            "new": self._audio_clip_edit_state(audio_clip),
        }

    def reorder_track(self, *, kind: str = "video", track_id: int, index: int) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        attr = "_tracks" if kind_text == "video" else "_audio_tracks"
        tracks = list(getattr(owner, attr, []) or [])
        target = _int(track_id)
        old_index = next((i for i, row in enumerate(tracks) if _int(getattr(row, "id", -1), -1) == target), -1)
        if old_index < 0:
            raise ValueError(f"{kind_text} track not found: {target}")
        new_index = max(0, min(len(tracks) - 1, _int(index)))
        if kind_text == "video":
            mover = getattr(owner, "_move_track", None)
            if callable(mover):
                direction = -1 if new_index < old_index else 1
                for _ in range(abs(new_index - old_index)):
                    mover(target, direction)
                self._register_change("Action reorder video track")
                return {"kind": kind_text, "track_id": target, "old_index": old_index, "new_index": new_index}
        track = tracks.pop(old_index)
        tracks.insert(new_index, track)
        setattr(owner, attr, tracks)
        self._after_timeline_mutation(f"Action reorder {kind_text} track")
        return {"kind": kind_text, "track_id": target, "old_index": old_index, "new_index": new_index}

    def set_track_state(self, *, kind: str = "video", track_id: int, **params: Any) -> dict[str, Any]:
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        track = self._video_track(track_id) if kind_text == "video" else self._audio_track(track_id)
        old: dict[str, Any] = {}
        changed: dict[str, Any] = {}
        allowed = {
            "video": ("locked", "muted", "pip_enabled", "pip_x", "pip_y", "pip_scale", "pip_opacity"),
            "audio": ("locked", "muted", "solo", "volume", "pan", "label", "bus_id", "track_type"),
        }[kind_text]
        for key in allowed:
            if key not in params:
                continue
            old[key] = getattr(track, key, None)
            value = params[key]
            if key in {"locked", "muted", "solo", "pip_enabled"}:
                value = _bool(value)
            elif key in {"volume", "pan", "pip_x", "pip_y", "pip_scale", "pip_opacity"}:
                value = _float(value, _float(old[key], 0.0))
                if key == "volume":
                    value = max(0.0, min(1.5, value))
                elif key == "pan":
                    value = max(-1.0, min(1.0, value))
                elif key == "pip_opacity":
                    value = max(0.0, min(1.0, value))
            elif key in {"label", "bus_id", "track_type"}:
                value = str(value or "")
            setattr(track, key, value)
            changed[key] = value
        if kind_text == "audio":
            self._update_audio_track(track)
        self._after_timeline_mutation(f"Action set {kind_text} track state")
        return {"kind": kind_text, "track_id": _int(track_id), "old": old, "new": changed}

    def set_track_lock(self, *, kind: str = "video", track_id: int, locked: bool = True) -> dict[str, Any]:
        return self.set_track_state(kind=kind, track_id=track_id, locked=_bool(locked))

    def set_track_mute(self, *, kind: str = "video", track_id: int, muted: bool = True) -> dict[str, Any]:
        kind_text = str(kind or "video").strip().lower()
        if kind_text == "audio":
            track = self._audio_track(track_id)
            old = {"muted": bool(getattr(track, "muted", False))}
            setattr(track, "muted", _bool(muted))
            self._update_audio_track(track)
            self._after_timeline_mutation("Action set audio track mute")
            return {"kind": kind_text, "track_id": _int(track_id), "old": old, "new": {"muted": bool(getattr(track, "muted", False))}}
        return self.set_track_state(kind=kind_text, track_id=track_id, muted=_bool(muted))

    def rename_track(self, *, kind: str = "video", track_id: int, name: str = "") -> dict[str, Any]:
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        track = self._video_track(track_id) if kind_text == "video" else self._audio_track(track_id)
        new_name = str(name or "").strip()
        old = {
            "label": getattr(track, "label", ""),
            "name": getattr(track, "name", ""),
        }
        setattr(track, "label", new_name)
        setattr(track, "name", new_name)
        if kind_text == "audio":
            self._update_audio_track(track)
        self._after_timeline_mutation(f"Action rename {kind_text} track")
        return {"kind": kind_text, "track_id": _int(track_id), "old": old, "new": {"label": new_name, "name": new_name}}

    def set_selection(
        self,
        *,
        kind: str = "video",
        track_id: int | None = None,
        clip_id: int | None = None,
        mode: str = "replace",
    ) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        mode_text = str(mode or "replace").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        if mode_text == "clear":
            setattr(owner, "_selected_clips", [])
            setattr(owner, "_selected_audio_clip_id", None)
            self._broadcast_selection()
            self._refresh_workbench()
            return self.selection_summary()
        if track_id is None:
            raise ValueError("track_id is required")
        if clip_id is None:
            clips = list(getattr(self._video_track(track_id) if kind_text == "video" else self._audio_track(track_id), "clips", []) or [])
            if not clips:
                raise ValueError(f"{kind_text} track has no clips")
            clip_id = _int(getattr(clips[0], "id", 0))
        if kind_text == "video":
            self._video_track_and_clip(_int(track_id), _int(clip_id))
        else:
            self._audio_track_and_clip(_int(track_id), _int(clip_id))
        current = self._normalized_selection_entries()
        selection = {"track_kind": kind_text, "track_id": _int(track_id), "clip_id": _int(clip_id)}
        key = self._selection_key(selection)
        if mode_text == "add":
            current_keys = {self._selection_key(row) for row in current}
            if key not in current_keys:
                current.append(selection)
            next_selection = current
        elif mode_text == "toggle":
            next_selection = [row for row in current if self._selection_key(row) != key]
            if len(next_selection) == len(current):
                next_selection.append(selection)
        elif mode_text == "remove":
            next_selection = [row for row in current if self._selection_key(row) != key]
        else:
            next_selection = [selection]
        setattr(owner, "_selected_clips", [(row["track_id"], row["clip_id"]) for row in next_selection if row["track_kind"] == "video"])
        setattr(owner, "_active_track_id", _int(track_id))
        audio_row = next((row for row in next_selection if row["track_kind"] == "audio"), None)
        if audio_row is not None:
            setattr(owner, "_active_audio_track_id", _int(audio_row["track_id"]))
            setattr(owner, "_selected_audio_clip_id", _int(audio_row["clip_id"]))
        else:
            setattr(owner, "_selected_audio_clip_id", None)
        self._broadcast_selection()
        self._refresh_workbench()
        return self.selection_summary()

    def select_clip(self, *, track_id: int, clip_id: int, kind: str = "video", mode: str = "replace") -> dict[str, Any]:
        return self.set_selection(kind=kind, track_id=track_id, clip_id=clip_id, mode=mode)

    def select_track(
        self,
        *,
        track_id: int,
        kind: str = "video",
        select_first_clip: bool = False,
        mode: str = "replace",
    ) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio"}:
            raise ValueError("kind must be video or audio")
        track = self._video_track(track_id) if kind_text == "video" else self._audio_track(track_id)
        if kind_text == "video":
            setattr(owner, "_active_track_id", _int(track_id))
        else:
            setattr(owner, "_active_audio_track_id", _int(track_id))
        if select_first_clip:
            clips = list(getattr(track, "clips", []) or [])
            if not clips:
                raise ValueError(f"{kind_text} track has no clips")
            return self.set_selection(
                kind=kind_text,
                track_id=_int(track_id),
                clip_id=_int(getattr(clips[0], "id", 0)),
                mode=mode,
            )
        self._broadcast_selection()
        self._refresh_workbench()
        return {
            "kind": kind_text,
            "track_id": _int(track_id),
            "active_track_id": _int(getattr(owner, "_active_track_id", 0)),
            "active_audio_track_id": _int(getattr(owner, "_active_audio_track_id", 0)),
            "selection": self.selection_summary(),
        }

    def select_all(self, *, kind: str = "video", track_id: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        kind_text = str(kind or "video").strip().lower()
        if kind_text in {"all", "both", "*"}:
            kinds = ("video", "audio")
        elif kind_text in {"video", "audio"}:
            kinds = (kind_text,)
        else:
            raise ValueError("kind must be video, audio, or all")
        rows: list[dict[str, int | str]] = []
        if "video" in kinds:
            for track in getattr(owner, "_tracks", []) or []:
                tid = _int(getattr(track, "id", -1), -1)
                if track_id is not None and tid != _int(track_id):
                    continue
                for clip in getattr(track, "clips", []) or []:
                    rows.append({"track_kind": "video", "track_id": tid, "clip_id": _int(getattr(clip, "id", 0))})
        if "audio" in kinds:
            for track in getattr(owner, "_audio_tracks", []) or []:
                tid = _int(getattr(track, "id", -1), -1)
                if track_id is not None and tid != _int(track_id):
                    continue
                for clip in getattr(track, "clips", []) or []:
                    rows.append({"track_kind": "audio", "track_id": tid, "clip_id": _int(getattr(clip, "id", 0))})
        if not rows:
            return self.clear_selection()
        setattr(owner, "_selected_clips", [(row["track_id"], row["clip_id"]) for row in rows if row["track_kind"] == "video"])
        audio_row = next((row for row in rows if row["track_kind"] == "audio"), None)
        if audio_row is not None:
            setattr(owner, "_active_audio_track_id", _int(audio_row["track_id"]))
            setattr(owner, "_selected_audio_clip_id", _int(audio_row["clip_id"]))
        else:
            setattr(owner, "_selected_audio_clip_id", None)
        first_video = next((row for row in rows if row["track_kind"] == "video"), None)
        if first_video is not None:
            setattr(owner, "_active_track_id", _int(first_video["track_id"]))
        self._broadcast_selection()
        self._refresh_workbench()
        return self.selection_summary()

    def clear_selection(self) -> dict[str, Any]:
        owner = self._require_owner()
        setattr(owner, "_selected_clips", [])
        setattr(owner, "_selected_audio_clip_id", None)
        self._broadcast_selection()
        self._refresh_workbench()
        return self.selection_summary()

    def selection_summary(self) -> dict[str, Any]:
        if self.owner is None:
            return {
                "selection": [],
                "selected_count": 0,
                "kind_counts": {},
                "span_start_ms": 0,
                "span_end_ms": 0,
                "active_track_id": 0,
                "active_audio_track_id": 0,
            }
        rows = self._normalized_selection_entries()
        resolved: list[dict[str, Any]] = []
        starts: list[int] = []
        ends: list[int] = []
        for row in rows:
            try:
                if row["track_kind"] == "audio":
                    _track, clip = self._audio_track_and_clip(row["track_id"], row["clip_id"])
                    start = _int(getattr(clip, "offset_ms", 0))
                    end = start + _int(getattr(clip, "effective_length_ms", 0))
                else:
                    _track, clip = self._video_track_and_clip(row["track_id"], row["clip_id"])
                    start = _int(getattr(clip, "timeline_in_ms", 0))
                    end = _int(getattr(clip, "timeline_out_ms", start))
            except Exception:
                continue
            starts.append(start)
            ends.append(end)
            resolved.append({**row, "timeline_in_ms": start, "timeline_out_ms": end})
        counts: dict[str, int] = {}
        for row in resolved:
            kind = str(row.get("track_kind") or "video")
            counts[kind] = counts.get(kind, 0) + 1
        return {
            "selection": resolved,
            "selected_count": len(resolved),
            "kind_counts": counts,
            "span_start_ms": min(starts) if starts else 0,
            "span_end_ms": max(ends) if ends else 0,
            "active_track_id": _int(getattr(self._require_owner(), "_active_track_id", 0)),
            "active_audio_track_id": _int(getattr(self._require_owner(), "_active_audio_track_id", 0)),
        }

    def select_range(
        self,
        *,
        start_ms: int,
        end_ms: int,
        track_id: int | None = None,
        mode: str = "replace",
        include_partial: bool = True,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        start = max(0, _int(start_ms))
        end = max(start + 1, _int(end_ms))
        matches: list[dict[str, int | str]] = []
        for track in getattr(owner, "_tracks", []) or []:
            tid = _int(getattr(track, "id", -1), -1)
            if track_id is not None and tid != _int(track_id):
                continue
            for clip in getattr(track, "clips", []) or []:
                clip_start = _int(getattr(clip, "timeline_in_ms", 0))
                clip_end = _int(getattr(clip, "timeline_out_ms", clip_start))
                overlaps = clip_start < end and start < clip_end
                contained = clip_start >= start and clip_end <= end
                if (include_partial and overlaps) or (not include_partial and contained):
                    matches.append({"track_kind": "video", "track_id": tid, "clip_id": _int(getattr(clip, "id", 0))})
        mode_text = str(mode or "replace").strip().lower()
        current = self._normalized_selection_entries()
        if mode_text == "add":
            next_selection = current
            current_keys = {self._selection_key(row) for row in current}
            for row in matches:
                if self._selection_key(row) not in current_keys:
                    next_selection.append(row)
                    current_keys.add(self._selection_key(row))
        elif mode_text == "toggle":
            toggled = list(current)
            for row in matches:
                key = self._selection_key(row)
                before = len(toggled)
                toggled = [item for item in toggled if self._selection_key(item) != key]
                if len(toggled) == before:
                    toggled.append(row)
            next_selection = toggled
        elif mode_text == "remove":
            remove_keys = {self._selection_key(row) for row in matches}
            next_selection = [row for row in current if self._selection_key(row) not in remove_keys]
        else:
            next_selection = matches
        setattr(owner, "_selected_clips", [(row["track_id"], row["clip_id"]) for row in next_selection if row["track_kind"] == "video"])
        if not any(row["track_kind"] == "audio" for row in next_selection):
            setattr(owner, "_selected_audio_clip_id", None)
        if next_selection:
            first_video = next((row for row in next_selection if row["track_kind"] == "video"), None)
            if first_video is not None:
                setattr(owner, "_active_track_id", _int(first_video["track_id"]))
        self._broadcast_selection()
        self._refresh_workbench()
        summary = self.selection_summary()
        summary.update({"range_start_ms": start, "range_end_ms": end, "matched_count": len(matches), "mode": mode_text})
        return summary

    def split_audio_clip(self, *, track_id: int, clip_id: int, at_ms: int) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        project_ms = max(0, _int(at_ms))
        start = _int(getattr(clip, "offset_ms", 0))
        end = start + _int(getattr(clip, "effective_length_ms", 0))
        if project_ms <= start or project_ms >= end:
            raise ValueError("split point must be strictly inside the audio clip")
        source_ms = _int(getattr(clip, "trim_start_ms", 0)) + (project_ms - start)
        right = copy.deepcopy(clip)
        right.id = self._next_audio_clip_id()
        right.offset_ms = project_ms
        right.trim_start_ms = source_ms
        right.trim_end_ms = _int(getattr(clip, "effective_trim_end_ms", 0))
        clip.trim_end_ms = source_ms
        track.clips.append(right)
        track.clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
        self._update_audio_track(track)
        self._after_timeline_mutation("Action split audio clip")
        return {
            "track_id": _int(track_id),
            "at_ms": project_ms,
            "left_clip_id": _int(clip_id),
            "right_clip_id": _int(getattr(right, "id", 0)),
            "clip_count_after": len(getattr(track, "clips", []) or []),
        }

    def trim_audio_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        trim_start_ms: int | None = None,
        trim_end_ms: int | None = None,
    ) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        old = {
            "offset_ms": _int(getattr(clip, "offset_ms", 0)),
            "trim_start_ms": _int(getattr(clip, "trim_start_ms", 0)),
            "trim_end_ms": _int(getattr(clip, "effective_trim_end_ms", 0)),
        }
        max_out = max(1, _int(getattr(clip, "duration_ms", 0)) or old["trim_end_ms"])
        new_start = old["trim_start_ms"] if trim_start_ms is None else max(0, _int(trim_start_ms))
        new_end = old["trim_end_ms"] if trim_end_ms is None else max(1, _int(trim_end_ms))
        new_start = max(0, min(new_start, max_out - 1))
        new_end = max(new_start + 1, min(new_end, max_out))
        delta = new_start - old["trim_start_ms"]
        clip.trim_start_ms = new_start
        clip.trim_end_ms = new_end
        clip.offset_ms = max(0, old["offset_ms"] + delta)
        track.clips.sort(key=lambda row: _int(getattr(row, "offset_ms", 0)))
        self._update_audio_track(track)
        self._after_timeline_mutation("Action trim audio clip")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "old": old,
            "new": {
                "offset_ms": _int(getattr(clip, "offset_ms", 0)),
                "trim_start_ms": _int(getattr(clip, "trim_start_ms", 0)),
                "trim_end_ms": _int(getattr(clip, "effective_trim_end_ms", 0)),
            },
        }

    def delete_audio_clip(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        before = len(getattr(track, "clips", []) or [])
        track.clips = [row for row in getattr(track, "clips", []) or [] if row is not clip]
        self._update_audio_track(track)
        self._after_timeline_mutation("Action delete audio clip")
        return {"track_id": _int(track_id), "clip_id": _int(clip_id), "clip_count_before": before, "clip_count_after": len(track.clips)}

    def set_audio_clip_gain(self, *, track_id: int, clip_id: int, gain: float) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        value = max(0.0, min(4.0, _float(gain, 1.0)))
        old = _float(getattr(clip, "gain", 1.0), 1.0)
        clip.gain = value
        self._update_audio_track(track)
        self._after_timeline_mutation("Action set audio clip gain")
        return {"track_id": _int(track_id), "clip_id": _int(clip_id), "old_gain": old, "gain": value}

    def set_audio_track_mix(self, *, track_id: int, volume: float | None = None, pan: float | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if volume is not None:
            params["volume"] = volume
        if pan is not None:
            params["pan"] = pan
        return self.set_track_state(kind="audio", track_id=track_id, **params)

    def set_audio_track_volume(self, *, track_id: int, volume: float) -> dict[str, Any]:
        return self.set_track_state(kind="audio", track_id=track_id, volume=volume)

    def set_audio_track_pan(self, *, track_id: int, pan: float) -> dict[str, Any]:
        return self.set_track_state(kind="audio", track_id=track_id, pan=pan)

    def set_audio_track_mute(self, *, track_id: int, muted: bool = True) -> dict[str, Any]:
        return self.set_track_mute(kind="audio", track_id=track_id, muted=muted)

    def set_audio_track_solo(self, *, track_id: int, solo: bool = True) -> dict[str, Any]:
        return self.set_track_state(kind="audio", track_id=track_id, solo=solo)

    def _normalize_audio_track_type(self, value: Any) -> str:
        text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "dialog": "dialogue",
            "voice": "dialogue",
            "vox": "dialogue",
            "music_stem": "music",
            "bgm": "music",
            "fx": "sfx",
            "sound_fx": "sfx",
            "amb": "ambience",
            "ambient": "ambience",
            "atmo": "ambience",
        }
        text = aliases.get(text, text)
        return text if text in {"dialogue", "music", "sfx", "ambience"} else text[:24]

    def _normalize_insert_slots(self, slots: Any) -> list[dict[str, Any]]:
        from app.audio_tracks import default_track_insert_slots

        defaults = {str(row["id"]): dict(row) for row in default_track_insert_slots()}
        rows: list[dict[str, Any]] = []
        for row in list(slots or []):
            if not isinstance(row, Mapping):
                continue
            sid = str(row.get("id") or row.get("slot") or "").strip().lower()
            if not sid:
                continue
            base = dict(defaults.get(sid, {"id": sid, "label": sid.upper(), "enabled": False, "bypassed": False}))
            base["enabled"] = _bool(row.get("enabled"), bool(base.get("enabled")))
            base["bypassed"] = _bool(row.get("bypassed"), bool(base.get("bypassed")))
            base["label"] = str(row.get("label") or base.get("label") or sid.upper())[:6]
            rows.append(base)
        seen = {str(row.get("id")) for row in rows}
        for sid, row in defaults.items():
            if sid not in seen:
                rows.append(dict(row))
        return rows

    def _normalize_sends(self, sends: Any) -> dict[str, float]:
        from app.audio_tracks import default_track_sends

        values = default_track_sends()
        if isinstance(sends, Mapping):
            for key, value in sends.items():
                sid = str(key or "").strip().lower()
                if not sid:
                    continue
                values[sid] = max(0.0, min(1.0, _float(value, 0.0)))
        return values

    def set_audio_track_type(self, *, track_id: int, track_type: str) -> dict[str, Any]:
        value = self._normalize_audio_track_type(track_type)
        return self.set_track_state(kind="audio", track_id=track_id, track_type=value)

    def set_audio_track_insert(
        self,
        *,
        track_id: int,
        slot: str,
        enabled: bool | None = None,
        bypassed: bool | None = None,
    ) -> dict[str, Any]:
        track = self._audio_track(track_id)
        slots = self._normalize_insert_slots(getattr(track, "insert_slots", None))
        target = str(slot or "").strip().lower()
        if target in {"dynamics", "dynamic"}:
            target = "dyn"
        if target not in {str(row.get("id")) for row in slots}:
            slots.append({"id": target, "label": target.upper()[:6], "enabled": False, "bypassed": False})
        old = copy.deepcopy(slots)
        for row in slots:
            if str(row.get("id")) != target:
                continue
            if enabled is not None:
                row["enabled"] = _bool(enabled)
            if bypassed is not None:
                row["bypassed"] = _bool(bypassed)
            if enabled is None and bypassed is None:
                row["enabled"] = not bool(row.get("enabled"))
        track.insert_slots = slots
        self._update_audio_track(track)
        self._after_timeline_mutation("Action set audio track insert")
        return {"track_id": _int(track_id), "slot": target, "old": old, "new": slots}

    def set_audio_track_send_level(self, *, track_id: int, send_id: str, level: float) -> dict[str, Any]:
        track = self._audio_track(track_id)
        sends = self._normalize_sends(getattr(track, "sends", None))
        sid = str(send_id or "").strip().lower()
        if sid in {"rev", "verb"}:
            sid = "reverb"
        if sid in {"dly"}:
            sid = "delay"
        old = dict(sends)
        sends[sid] = max(0.0, min(1.0, _float(level, 0.0)))
        track.sends = sends
        self._update_audio_track(track)
        self._after_timeline_mutation("Action set audio send level")
        return {"track_id": _int(track_id), "send_id": sid, "old": old, "new": dict(sends)}

    def route_audio_track_to_bus(self, *, track_id: int, bus_id: str) -> dict[str, Any]:
        return self.set_track_state(kind="audio", track_id=track_id, bus_id=str(bus_id or "master").strip() or "master")

    def _audio_track_meter_row(self, track: Any, index: int, *, solo_active: bool) -> dict[str, Any]:
        volume = max(0.0, min(1.5, _float(getattr(track, "volume", 1.0), 1.0)))
        pan = max(-1.0, min(1.0, _float(getattr(track, "pan", 0.0), 0.0)))
        audible = not bool(getattr(track, "muted", False)) and (not solo_active or bool(getattr(track, "solo", False)))
        level = 0.0 if not audible else min(1.0, max(0.03, volume * 0.62))
        left = min(1.0, level * (1.0 - max(0.0, pan) * 0.35))
        right = min(1.0, level * (1.0 + min(0.0, pan) * 0.35))
        peak = min(1.0, max(left, right) + (0.12 if volume > 0.82 else 0.06))
        clipped = bool(volume >= 1.18 and audible)
        return {
            "track_id": _int(getattr(track, "id", index + 1), index + 1),
            "level_l": round(left, 4),
            "level_r": round(right, 4),
            "peak_hold": round(peak, 4),
            "clip_led": clipped,
            "audible": audible,
        }

    def audio_track_meter_state(self, *, track_id: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        solo_active = any(bool(getattr(track, "solo", False)) for track in tracks)
        rows = [
            self._audio_track_meter_row(track, index, solo_active=solo_active)
            for index, track in enumerate(tracks)
            if track_id is None or _int(getattr(track, "id", -1), -1) == _int(track_id)
        ]
        return {
            "schema": "tigerstudio.audio.meter.v1",
            "track_count": len(rows),
            "tracks": rows,
        }

    def audio_automation_state(self, *, track_id: int | None = None) -> dict[str, Any]:
        owner = self._require_owner()
        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        rows: list[dict[str, Any]] = []
        for index, track in enumerate(tracks):
            tid = _int(getattr(track, "id", index + 1), index + 1)
            if track_id is not None and tid != _int(track_id):
                continue
            lanes = dict(getattr(track, "automation_lanes", {}) or {})
            if getattr(track, "automation_points", None):
                lanes.setdefault("volume", list(getattr(track, "automation_points", []) or []))
            rows.append(
                {
                    "track_id": tid,
                    "read": bool(getattr(track, "automation_read", True)),
                    "write": bool(getattr(track, "automation_write", False)),
                    "lanes": lanes,
                    "point_count": sum(len(list(points or [])) for points in lanes.values()),
                }
            )
        return {"schema": "tigerstudio.audio.automation.v1", "tracks": rows, "track_count": len(rows)}

    def write_audio_automation(
        self,
        *,
        track_id: int,
        parameter: str = "volume",
        time_ms: int | None = None,
        value: float | None = None,
        read: bool | None = None,
        write: bool | None = None,
    ) -> dict[str, Any]:
        track = self._audio_track(track_id)
        old = {
            "automation_read": bool(getattr(track, "automation_read", True)),
            "automation_write": bool(getattr(track, "automation_write", False)),
            "automation_points": copy.deepcopy(list(getattr(track, "automation_points", []) or [])),
            "automation_lanes": copy.deepcopy(dict(getattr(track, "automation_lanes", {}) or {})),
        }
        if read is not None:
            track.automation_read = _bool(read, True)
        if write is not None:
            track.automation_write = _bool(write, False)
        else:
            track.automation_write = True
        parameter_id = str(parameter or "volume").strip().lower()
        if value is not None:
            extent = max(1, _int(getattr(track, "extent_ms", lambda: 1)()))
            norm = max(0.0, min(1.0, _float(time_ms, 0.0) / float(extent)))
            point = [round(norm, 6), _float(value, 1.0)]
            lanes = dict(getattr(track, "automation_lanes", {}) or {})
            lane = list(lanes.get(parameter_id, []) or [])
            lane.append(point)
            lane.sort(key=lambda row: _float(row[0], 0.0))
            lanes[parameter_id] = lane
            track.automation_lanes = lanes
            if parameter_id == "volume":
                track.automation_points = lane
        self._update_audio_track(track)
        self._after_timeline_mutation("Action write audio automation")
        return {"track_id": _int(track_id), "parameter": parameter_id, "old": old, "new": self.audio_automation_state(track_id=track_id)["tracks"][0]}

    def clear_audio_automation(self, *, track_id: int, parameter: str | None = None) -> dict[str, Any]:
        track = self._audio_track(track_id)
        old = self.audio_automation_state(track_id=track_id)
        parameter_id = str(parameter or "").strip().lower()
        if parameter_id:
            lanes = dict(getattr(track, "automation_lanes", {}) or {})
            lanes.pop(parameter_id, None)
            track.automation_lanes = lanes
            if parameter_id == "volume":
                track.automation_points = []
        else:
            track.automation_lanes = {}
            track.automation_points = []
            track.automation_write = False
        self._update_audio_track(track)
        self._after_timeline_mutation("Action clear audio automation")
        return {"track_id": _int(track_id), "parameter": parameter_id or "all", "old": old, "new": self.audio_automation_state(track_id=track_id)}

    def _audio_mixer_snapshot_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, track in enumerate(list(getattr(self._require_owner(), "_audio_tracks", []) or [])):
            rows.append(
                {
                    "track_id": _int(getattr(track, "id", index + 1), index + 1),
                    "volume": _float(getattr(track, "volume", 1.0), 1.0),
                    "pan": _float(getattr(track, "pan", 0.0), 0.0),
                    "muted": bool(getattr(track, "muted", False)),
                    "solo": bool(getattr(track, "solo", False)),
                    "bus_id": str(getattr(track, "bus_id", "master") or "master"),
                    "track_type": str(getattr(track, "track_type", "") or ""),
                    "insert_slots": copy.deepcopy(list(getattr(track, "insert_slots", []) or [])),
                    "sends": copy.deepcopy(dict(getattr(track, "sends", {}) or {})),
                    "automation_read": bool(getattr(track, "automation_read", True)),
                    "automation_write": bool(getattr(track, "automation_write", False)),
                }
            )
        return rows

    def _audio_mixer_snapshots(self) -> list[dict[str, Any]]:
        owner = self._require_owner()
        snapshots = getattr(owner, "_audio_mixer_snapshots", None)
        if not isinstance(snapshots, list):
            snapshots = []
            owner._audio_mixer_snapshots = snapshots
        return snapshots

    def save_audio_mixer_snapshot(self, *, snapshot_id: str | None = None, name: str | None = None) -> dict[str, Any]:
        snapshots = self._audio_mixer_snapshots()
        sid = str(snapshot_id or "").strip() or f"mix_{len(snapshots) + 1}"
        row = {
            "id": sid,
            "name": str(name or sid),
            "schema": "tigerstudio.audio.mixer.snapshot.v1",
            "tracks": self._audio_mixer_snapshot_rows(),
        }
        before = len(snapshots)
        snapshots[:] = [snap for snap in snapshots if str(snap.get("id")) != sid]
        snapshots.append(row)
        self._after_timeline_mutation("Action save audio mixer snapshot")
        return {"snapshot": row, "snapshot_count_before": before, "snapshot_count": len(snapshots)}

    def _find_audio_mixer_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        sid = str(snapshot_id or "").strip()
        for row in self._audio_mixer_snapshots():
            if str(row.get("id")) == sid:
                return row
        raise ValueError(f"audio mixer snapshot not found: {sid}")

    def apply_audio_mixer_snapshot(self, *, snapshot_id: str) -> dict[str, Any]:
        snapshot = self._find_audio_mixer_snapshot(snapshot_id)
        tracks_by_id = {
            _int(getattr(track, "id", -1), -1): track
            for track in list(getattr(self._require_owner(), "_audio_tracks", []) or [])
        }
        applied: list[int] = []
        for row in list(snapshot.get("tracks") or []):
            track = tracks_by_id.get(_int(row.get("track_id"), -1))
            if track is None:
                continue
            for key in ("volume", "pan", "muted", "solo", "bus_id", "track_type", "insert_slots", "sends", "automation_read", "automation_write"):
                if key in row:
                    setattr(track, key, copy.deepcopy(row[key]))
            self._update_audio_track(track)
            applied.append(_int(getattr(track, "id", 0)))
        self._after_timeline_mutation("Action apply audio mixer snapshot")
        return {"snapshot_id": str(snapshot_id), "applied_track_ids": applied, "applied_count": len(applied)}

    def compare_audio_mixer_snapshot(self, *, snapshot_id: str) -> dict[str, Any]:
        snapshot = self._find_audio_mixer_snapshot(snapshot_id)
        current = {row["track_id"]: row for row in self._audio_mixer_snapshot_rows()}
        deltas: list[dict[str, Any]] = []
        for row in list(snapshot.get("tracks") or []):
            tid = _int(row.get("track_id"), -1)
            now = current.get(tid)
            if now is None:
                deltas.append({"track_id": tid, "status": "missing_current"})
                continue
            changes: dict[str, dict[str, Any]] = {}
            for key in ("volume", "pan", "muted", "solo", "bus_id", "track_type", "insert_slots", "sends", "automation_read", "automation_write"):
                if now.get(key) != row.get(key):
                    changes[key] = {"snapshot": row.get(key), "current": now.get(key)}
            if changes:
                deltas.append({"track_id": tid, "changes": changes})
        return {"snapshot_id": str(snapshot_id), "delta_count": len(deltas), "deltas": deltas}

    def audio_mixer_state(self) -> dict[str, Any]:
        owner = self._require_owner()
        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        panel = getattr(owner, "_audio_mixer_panel", None)
        payload = getattr(panel, "mixer_state_payload", None)
        if callable(payload):
            try:
                row = dict(payload(tracks) or {})
                row["snapshot_count"] = len(list(getattr(owner, "_audio_mixer_snapshots", []) or []))
                return row
            except Exception:
                pass
        solo_active = any(bool(getattr(track, "solo", False)) for track in tracks)
        rows: list[dict[str, Any]] = []
        for index, track in enumerate(tracks):
            meter = self._audio_track_meter_row(track, index, solo_active=solo_active)
            rows.append(
                {
                    "id": _int(getattr(track, "id", index + 1), index + 1),
                    "index": index,
                    "label": str(getattr(track, "display_name", "") or getattr(track, "label", "") or f"Audio {index + 1}"),
                    "volume": _float(getattr(track, "volume", 1.0), 1.0),
                    "pan": _float(getattr(track, "pan", 0.0), 0.0),
                    "muted": bool(getattr(track, "muted", False)),
                    "solo": bool(getattr(track, "solo", False)),
                    "audible": not bool(getattr(track, "muted", False)) and (not solo_active or bool(getattr(track, "solo", False))),
                    "bus_id": str(getattr(track, "bus_id", "master") or "master"),
                    "track_type": str(getattr(track, "track_type", "") or ""),
                    "insert_slots": self._normalize_insert_slots(getattr(track, "insert_slots", None)),
                    "sends": self._normalize_sends(getattr(track, "sends", None)),
                    "automation": {
                        "read": bool(getattr(track, "automation_read", True)),
                        "write": bool(getattr(track, "automation_write", False)),
                        "point_count": len(list(getattr(track, "automation_points", []) or [])),
                    },
                    "meter": meter,
                    "clip_count": len(list(getattr(track, "clips", []) or [])),
                    "loaded": bool(getattr(track, "is_loaded", False)),
                }
            )
        return {
            "schema": "tigerstudio.audio.mixer.v1",
            "track_count": len(rows),
            "solo_active": solo_active,
            "snapshot_count": len(list(getattr(owner, "_audio_mixer_snapshots", []) or [])),
            "tracks": rows,
        }

    def sound_editor_jog_shuttle_state(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        return self._sound_editor_jog_state(track, clip)

    def set_sound_editor_jog_shuttle(
        self,
        *,
        track_id: int,
        clip_id: int,
        position_ms: int | None = None,
        normalized_position: float | None = None,
        step_ms: int | None = None,
        playing: bool | None = None,
        focus_workbench: bool = True,
    ) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        duration = self._sound_editor_duration_ms(clip)
        old_position = self._sound_editor_position_ms(clip, duration)
        old_playing = bool(getattr(clip, "_se_jog_playing", False))
        next_position = old_position
        if step_ms is not None:
            next_position += _int(step_ms)
        if normalized_position is not None:
            ratio = max(0.0, min(1.0, _float(normalized_position, 0.0)))
            next_position = int(round(ratio * duration))
        if position_ms is not None:
            next_position = _int(position_ms)
        next_position = max(0, min(duration, next_position))

        setattr(clip, "_se_jog_ms", next_position)
        next_playing = old_playing if playing is None else _bool(playing, old_playing)
        setattr(clip, "_se_jog_playing", next_playing)

        ui_updated = self._focus_workbench_sound_editor(
            track,
            clip,
            focus_workbench=_bool(focus_workbench, True),
            position_ms=next_position,
            playing=next_playing,
        )
        state = self._sound_editor_jog_state(track, clip)
        state.update(
            {
                "old_position_ms": old_position,
                "old_playing": old_playing,
                "ui_updated": ui_updated,
                "changed": old_position != next_position or old_playing != next_playing,
            }
        )
        return state

    def sound_editor_advanced_lab_state(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        return self._sound_editor_advanced_lab_state(track, clip)

    def set_sound_editor_advanced_lab(
        self,
        *,
        track_id: int,
        clip_id: int,
        expanded: bool,
        focus_workbench: bool = True,
    ) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        old_expanded = bool(getattr(clip, "_se_advanced_lab_expanded", False))
        next_expanded = _bool(expanded, False)
        legacy_count_before = self._advanced_sound_lab_count()
        setattr(clip, "_se_advanced_lab_expanded", next_expanded)
        ui_updated = self._focus_workbench_sound_editor(
            track,
            clip,
            focus_workbench=_bool(focus_workbench, True),
            advanced_expanded=next_expanded,
        )
        legacy_count_after = self._advanced_sound_lab_count()
        state = self._sound_editor_advanced_lab_state(track, clip)
        state.update(
            {
                "old_expanded": old_expanded,
                "ui_updated": ui_updated,
                "legacy_lab_count_before": legacy_count_before,
                "legacy_lab_count_after": legacy_count_after,
                "opened_legacy_window": legacy_count_after > legacy_count_before,
                "changed": old_expanded != next_expanded,
            }
        )
        return state

    def apply_sound_editor_effects(
        self,
        *,
        track_id: int,
        clip_id: int,
        basic: Mapping[str, Any] | None = None,
        effects: Mapping[str, Any] | None = None,
        merge: bool = True,
        focus_workbench: bool = True,
    ) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        self._ensure_sound_editor_effects(clip, merge=bool(merge))
        if isinstance(basic, Mapping):
            self._apply_sound_editor_basic_values(track, clip, basic)
        if isinstance(effects, Mapping):
            self._merge_sound_editor_effects(clip.effects, effects)
        self._update_audio_track(track)
        ui_updated = self._focus_workbench_sound_editor(
            track,
            clip,
            focus_workbench=_bool(focus_workbench, True),
        )
        self._after_timeline_mutation("Action apply sound editor effects")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "basic": self._sound_editor_basic_state(track, clip),
            "effects": copy.deepcopy(getattr(clip, "effects", {}) or {}),
            "ui_updated": ui_updated,
        }

    def apply_sound_editor_ai_preset(
        self,
        *,
        track_id: int,
        clip_id: int,
        preset: str,
        focus_workbench: bool = True,
    ) -> dict[str, Any]:
        presets = {
            "Suno v3": {"air": 5.0, "clarity": 60.0, "warmth": 40.0, "width": 130.0, "punch": 50.0, "excite": 70.0},
            "Suno v4": {"air": 3.0, "clarity": 50.0, "warmth": 30.0, "width": 120.0, "punch": 40.0, "excite": 50.0},
            "Udio": {"air": 4.0, "clarity": 45.0, "warmth": 35.0, "width": 110.0, "punch": 55.0, "excite": 60.0},
            "ACE-Step": {"air": 6.0, "clarity": 55.0, "warmth": 50.0, "width": 140.0, "punch": 45.0, "excite": 75.0},
            "Generic AI": {"air": 4.0, "clarity": 50.0, "warmth": 40.0, "width": 120.0, "punch": 50.0, "excite": 60.0},
            "Custom": {"air": 0.0, "clarity": 0.0, "warmth": 0.0, "width": 100.0, "punch": 0.0, "excite": 0.0},
        }
        name = str(preset or "").strip()
        if name not in presets:
            raise ValueError(f"unknown AI preset: {name}")
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        self._ensure_sound_editor_effects(clip)
        ai = clip.effects.setdefault("ai_master", {})
        ai.update(presets[name])
        ai["preset"] = name
        ai["enabled"] = name != "Custom"
        self._update_audio_track(track)
        ui_updated = self._focus_workbench_sound_editor(
            track,
            clip,
            focus_workbench=_bool(focus_workbench, True),
        )
        self._after_timeline_mutation("Action apply sound editor AI preset")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "preset": name,
            "ai_master": copy.deepcopy(ai),
            "ui_updated": ui_updated,
        }

    def audio_loudness_report(
        self,
        *,
        track_id: int,
        clip_id: int,
        target_lufs: float | None = None,
        true_peak_limit_db: float | None = None,
        tolerance_lufs: float = 1.0,
    ) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        loudness = ((getattr(clip, "effects", {}) or {}).get("loudness") or {}) if isinstance(getattr(clip, "effects", None), dict) else {}
        target = _float(target_lufs, _float(loudness.get("target_i", -14.0), -14.0))
        peak_limit = _float(true_peak_limit_db, _float(loudness.get("true_peak", -1.0), -1.0))
        waveform = getattr(clip, "waveform", None)
        try:
            import numpy as np

            arr = np.asarray(waveform, dtype=np.float32)
            if arr.size <= 0:
                raise ValueError("waveform unavailable")
            if arr.ndim == 2 and arr.shape[0] <= 8:
                arr = arr.T
            from app.audio_accuracy import audio_signal_diagnostics

            report = audio_signal_diagnostics(
                arr,
                target_lufs=target,
                true_peak_limit_db=peak_limit,
                tolerance_lufs=_float(tolerance_lufs, 1.0),
            )
            available = True
        except Exception:
            report = {
                "ok": False,
                "integrated_lufs": None,
                "target_lufs": target,
                "true_peak_dbfs": None,
                "true_peak_limit_db": peak_limit,
                "stereo_correlation": None,
                "warnings": ["waveform unavailable"],
            }
            available = False
        report.update(
            {
                "schema": "tigerstudio.audio.loudness_report.v1",
                "track_id": _int(getattr(track, "id", track_id)),
                "clip_id": _int(getattr(clip, "id", clip_id)),
                "available": available,
                "source": "waveform_cache",
            }
        )
        return report

    def export_audio_clip(
        self,
        *,
        track_id: int,
        clip_id: int,
        out_path: str | None = None,
        format: str = "mp3",
        quality_id: str | None = None,
    ) -> dict[str, Any]:
        _track, clip = self._audio_track_and_clip(track_id, clip_id)
        from app.audio_tracks import (
            CLIP_EXPORT_FORMATS,
            DEFAULT_AUDIO_QUALITY_ID,
            build_single_clip_filter,
            get_audio_quality_preset,
        )

        fmt_key = str(format or "").strip().lower() or "mp3"
        if out_path:
            suffix = Path(out_path).suffix.lower()
            for key, spec in CLIP_EXPORT_FORMATS.items():
                if suffix and suffix == str(spec.get("ext", "")).lower():
                    fmt_key = key
                    break
        if fmt_key not in CLIP_EXPORT_FORMATS:
            raise ValueError(f"unknown audio export format: {fmt_key}")
        filter_graph, output_ms = build_single_clip_filter(clip)
        result = {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "format": fmt_key,
            "quality_id": str(quality_id or DEFAULT_AUDIO_QUALITY_ID),
            "output_ms": output_ms,
            "filter_graph": filter_graph,
            "exported": False,
        }
        if not out_path:
            return result
        if getattr(clip, "source_path", None) is None:
            raise ValueError("audio clip has no source file")
        if output_ms <= 0:
            raise ValueError("nothing to export")

        import subprocess
        from imageio_ffmpeg import get_ffmpeg_exe
        from app.subprocess_utils import hidden_subprocess_kwargs

        fmt = CLIP_EXPORT_FORMATS[fmt_key]
        output = Path(out_path)
        expected_ext = str(fmt.get("ext", ".mp3"))
        if output.suffix.lower() != expected_ext.lower():
            output = output.with_suffix(expected_ext)
        output.parent.mkdir(parents=True, exist_ok=True)
        quality = get_audio_quality_preset(str(quality_id or DEFAULT_AUDIO_QUALITY_ID))
        cmd = [
            get_ffmpeg_exe(),
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-i", str(getattr(clip, "source_path")),
            "-filter_complex", filter_graph,
            "-map", "[out]",
            "-vn",
            *fmt["codec"](quality),
            str(output),
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "")[-1500:] or f"ffmpeg exited {proc.returncode}")
        result.update({"exported": True, "out_path": str(output)})
        return result

    def separate_audio_stems(
        self,
        *,
        track_id: int,
        clip_id: int,
        output_root: str | None = None,
        prefer_demucs: bool = True,
        add_to_timeline: bool = True,
    ) -> dict[str, Any]:
        track, clip = self._audio_track_and_clip(track_id, clip_id)
        source = getattr(clip, "source_path", None)
        if source is None:
            raise ValueError("audio clip has no source file")
        from app.audio_separation import planned_separation_method, separate_audio_stems as _separate_audio_stems

        method_hint = planned_separation_method(prefer_demucs=_bool(prefer_demucs, True))
        result = _separate_audio_stems(
            source,
            Path(output_root) if output_root else None,
            prefer_demucs=_bool(prefer_demucs, True),
        )
        added = []
        if _bool(add_to_timeline, True):
            added = self._add_separated_stems_to_timeline(track, clip, result.vocals_path, result.instrumental_path)
            if added:
                self._after_timeline_mutation("Action separate audio stems")
        return {
            "track_id": _int(track_id),
            "clip_id": _int(clip_id),
            "method_hint": method_hint,
            "method": result.method,
            "note": result.note,
            "vocals_path": str(result.vocals_path),
            "instrumental_path": str(result.instrumental_path),
            "added_tracks": added,
        }

    def _ensure_sound_editor_effects(self, clip: Any, *, merge: bool = True) -> None:
        from app.audio_tracks import default_effects_state

        defaults = default_effects_state()
        if not isinstance(getattr(clip, "effects", None), dict) or not merge:
            clip.effects = copy.deepcopy(defaults)
            return
        for key, value in defaults.items():
            existing = clip.effects.setdefault(key, copy.deepcopy(value))
            if isinstance(existing, dict) and isinstance(value, dict):
                self._merge_missing_sound_defaults(existing, value)

    def _merge_missing_sound_defaults(self, target: dict[str, Any], defaults: Mapping[str, Any]) -> None:
        for key, value in defaults.items():
            if key not in target:
                target[key] = copy.deepcopy(value)
            elif isinstance(target.get(key), dict) and isinstance(value, Mapping):
                self._merge_missing_sound_defaults(target[key], value)

    def _merge_sound_editor_effects(self, target: dict[str, Any], payload: Mapping[str, Any]) -> None:
        from app.audio_tracks import default_effects_state

        defaults = default_effects_state()
        for key, value in payload.items():
            if isinstance(value, Mapping):
                section = target.setdefault(str(key), copy.deepcopy(defaults.get(str(key), {})))
                if isinstance(section, dict):
                    self._merge_sound_editor_effects(section, value)
                else:
                    target[str(key)] = copy.deepcopy(dict(value))
            else:
                target[str(key)] = copy.deepcopy(value)

    def _apply_sound_editor_basic_values(self, track: Any, clip: Any, basic: Mapping[str, Any]) -> None:
        if "gain" in basic:
            clip.gain = max(0.0, min(4.0, _float(basic.get("gain"), 1.0)))
        elif "gain_db" in basic or "volume_db" in basic:
            db = _float(basic.get("gain_db", basic.get("volume_db")), 0.0)
            clip.gain = max(0.0, min(4.0, 10.0 ** (db / 20.0)))
        if "track_volume_db" in basic:
            track.volume = max(0.0, min(4.0, 10.0 ** (_float(basic.get("track_volume_db"), 0.0) / 20.0)))
        if "fade_in_ms" in basic or "fade_in_s" in basic:
            clip.fade_in_ms = max(0, _int(basic.get("fade_in_ms", _float(basic.get("fade_in_s"), 0.0) * 1000.0)))
        if "fade_out_ms" in basic or "fade_out_s" in basic:
            clip.fade_out_ms = max(0, _int(basic.get("fade_out_ms", _float(basic.get("fade_out_s"), 0.0) * 1000.0)))
        if "speed" in basic:
            setattr(clip, "_se_speed", max(0.1, min(4.0, _float(basic.get("speed"), 1.0))))
        if "pitch" in basic or "pitch_st" in basic:
            setattr(clip, "_se_pitch", max(-24.0, min(24.0, _float(basic.get("pitch", basic.get("pitch_st")), 0.0))))
        if "reverse" in basic:
            setattr(clip, "_se_reverse", _bool(basic.get("reverse"), False))
        if "pan" in basic or "pan_percent" in basic:
            raw_pan = _float(basic.get("pan", basic.get("pan_percent")), 0.0)
            pan = raw_pan / 100.0 if abs(raw_pan) > 1.0 else raw_pan
            pan = max(-1.0, min(1.0, pan))
            setattr(clip, "_se_pan", pan)
            try:
                setattr(track, "pan", pan)
            except Exception:
                pass
        if "muted" in basic:
            muted = _bool(basic.get("muted"), False)
            setattr(clip, "_se_muted", muted)
            if muted:
                setattr(clip, "_se_pre_mute_gain", _float(getattr(clip, "gain", 1.0), 1.0))
                clip.gain = 0.0
            elif _float(getattr(clip, "gain", 1.0), 1.0) <= 0.001:
                clip.gain = max(0.01, _float(getattr(clip, "_se_pre_mute_gain", 1.0), 1.0))

    def _sound_editor_basic_state(self, track: Any, clip: Any) -> dict[str, Any]:
        return {
            "gain": _float(getattr(clip, "gain", 1.0), 1.0),
            "track_volume": _float(getattr(track, "volume", 1.0), 1.0),
            "pan": _float(getattr(clip, "_se_pan", getattr(track, "pan", 0.0)), 0.0),
            "fade_in_ms": _int(getattr(clip, "fade_in_ms", 0)),
            "fade_out_ms": _int(getattr(clip, "fade_out_ms", 0)),
            "speed": _float(getattr(clip, "_se_speed", 1.0), 1.0),
            "pitch": _float(getattr(clip, "_se_pitch", 0.0), 0.0),
            "reverse": bool(getattr(clip, "_se_reverse", False)),
            "muted": bool(getattr(clip, "_se_muted", False)) or _float(getattr(clip, "gain", 1.0), 1.0) <= 0.001,
        }

    def _add_separated_stems_to_timeline(
        self,
        source_track: Any,
        source_clip: Any,
        vocals_path: Path,
        instrumental_path: Path,
    ) -> list[dict[str, Any]]:
        owner = self._require_owner()
        from app.audio_tracks import AudioClip, AudioTrack, probe_audio_duration_ms

        tracks = list(getattr(owner, "_audio_tracks", []) or [])
        added: list[dict[str, Any]] = []
        next_clip_id = max(
            (
                _int(getattr(clip, "id", 0))
                for track in tracks
                for clip in getattr(track, "clips", []) or []
            ),
            default=0,
        ) + 1
        for path, label in ((instrumental_path, "Instrumental Stem"), (vocals_path, "Vocal Stem")):
            duration = _int(probe_audio_duration_ms(Path(path)), 0)
            if duration <= 0:
                duration = max(1, _int(getattr(source_clip, "effective_length_ms", 0) or getattr(source_clip, "duration_ms", 0) or 1))
            track = AudioTrack(id=self._next_track_id(tracks), label=label)
            clip = AudioClip(
                id=next_clip_id,
                source_path=Path(path),
                duration_ms=duration,
                offset_ms=_int(getattr(source_clip, "offset_ms", 0)),
                trim_start_ms=0,
                trim_end_ms=duration,
                fade_in_ms=_int(getattr(source_clip, "fade_in_ms", 0)),
                fade_out_ms=_int(getattr(source_clip, "fade_out_ms", 0)),
                fades=copy.deepcopy(getattr(source_clip, "fades", [])),
                cuts=copy.deepcopy(getattr(source_clip, "cuts", [])),
                gain=_float(getattr(source_clip, "gain", 1.0), 1.0),
            )
            next_clip_id += 1
            track.clips.append(clip)
            tracks.append(track)
            added.append({"track_id": _int(track.id), "clip_id": _int(clip.id), "label": label, "path": str(path)})
            insert = getattr(owner, "_insert_audio_track_widget", None)
            if callable(insert):
                try:
                    insert(track)
                except Exception:
                    pass
            mixer = getattr(owner, "_audio_mixer", None)
            add_track = getattr(mixer, "add_track", None)
            if callable(add_track):
                try:
                    add_track(track)
                except Exception:
                    pass
            waveform = getattr(owner, "_start_waveform_extraction", None)
            if callable(waveform):
                try:
                    waveform(clip)
                except Exception:
                    pass
        setattr(owner, "_audio_tracks", tracks)
        self._update_audio_track(source_track)
        return added

    def _sound_editor_duration_ms(self, clip: Any) -> int:
        return max(1, _int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 1))

    def _sound_editor_position_ms(self, clip: Any, duration_ms: int | None = None) -> int:
        duration = self._sound_editor_duration_ms(clip) if duration_ms is None else max(1, _int(duration_ms, 1))
        return max(0, min(duration, _int(getattr(clip, "_se_jog_ms", 0), 0)))

    def _sound_editor_level(self, clip: Any) -> float:
        waveform = getattr(clip, "waveform", None)
        try:
            if waveform is not None and int(getattr(waveform, "size", 0) or 0) > 0:
                return max(0.05, min(1.0, float(abs(waveform).max())))
        except Exception:
            pass
        return max(0.05, min(1.0, _float(getattr(clip, "gain", 1.0), 1.0) / 1.5))

    def _workbench_sound_editor_panel(self) -> Any | None:
        wb = getattr(self._require_owner(), "_workbench_panel", None)
        return getattr(wb, "_sound_editor_panel", None) if wb is not None else None

    def _focus_workbench_sound_editor(
        self,
        track: Any,
        clip: Any,
        *,
        focus_workbench: bool,
        position_ms: int | None = None,
        playing: bool | None = None,
        advanced_expanded: bool | None = None,
    ) -> bool:
        if not focus_workbench:
            return False
        owner = self._require_owner()
        updated = False
        try:
            setattr(owner, "_active_audio_track_id", _int(getattr(track, "id", 0)))
            setattr(owner, "_selected_audio_clip_id", _int(getattr(clip, "id", 0)))
        except Exception:
            pass

        wb = getattr(owner, "_workbench_panel", None)
        if wb is not None:
            set_audio_clip = getattr(wb, "set_audio_clip", None)
            if callable(set_audio_clip):
                try:
                    set_audio_clip(track, clip)
                    updated = True
                except Exception:
                    pass
            set_tab = getattr(wb, "_set_inspector_tab", None)
            if callable(set_tab):
                try:
                    set_tab("audio")
                    updated = True
                except Exception:
                    pass
            panel = getattr(wb, "_sound_editor_panel", None)
            updated = self._apply_sound_editor_panel_state(
                panel,
                clip,
                position_ms=position_ms,
                playing=playing,
                advanced_expanded=advanced_expanded,
            ) or updated

        refresh_audio = getattr(owner, "_refresh_audio_workspace_panel", None)
        if callable(refresh_audio):
            try:
                refresh_audio()
                updated = True
            except Exception:
                pass
        self._process_capture_events()
        return updated

    def _apply_sound_editor_panel_state(
        self,
        panel: Any | None,
        clip: Any,
        *,
        position_ms: int | None = None,
        playing: bool | None = None,
        advanced_expanded: bool | None = None,
    ) -> bool:
        if panel is None:
            return False
        updated = False
        jog = getattr(panel, "_jog_shuttle", None)
        if jog is not None:
            set_clip = getattr(jog, "set_clip", None)
            if callable(set_clip):
                try:
                    set_clip(clip)
                    updated = True
                except Exception:
                    pass
            if position_ms is not None:
                set_position = getattr(jog, "_set_position_ms", None)
                if callable(set_position):
                    try:
                        set_position(_int(position_ms), emit=False)
                    except TypeError:
                        try:
                            set_position(_int(position_ms))
                            updated = True
                        except Exception:
                            pass
                    except Exception:
                        pass
                    else:
                        updated = True
            if playing is not None:
                set_playing = getattr(jog, "_set_playing", None)
                if callable(set_playing):
                    try:
                        set_playing(bool(playing))
                        updated = True
                    except Exception:
                        pass
        if advanced_expanded is not None:
            set_advanced = getattr(panel, "_set_advanced_lab_expanded", None)
            if callable(set_advanced):
                try:
                    set_advanced(bool(advanced_expanded))
                    updated = True
                except Exception:
                    pass
        return updated

    def _sound_editor_jog_state(self, track: Any, clip: Any) -> dict[str, Any]:
        duration = self._sound_editor_duration_ms(clip)
        position = self._sound_editor_position_ms(clip, duration)
        ui = self._sound_editor_ui_state(clip)
        return {
            "schema": "tigerstudio.sound_editor.jog_shuttle.v1",
            "track_id": _int(getattr(track, "id", 0)),
            "clip_id": _int(getattr(clip, "id", 0)),
            "position_ms": position,
            "duration_ms": duration,
            "normalized_position": round(position / max(1, duration), 6),
            "playing": bool(getattr(clip, "_se_jog_playing", False)),
            "level": round(self._sound_editor_level(clip), 6),
            "waveform_available": bool(getattr(getattr(clip, "waveform", None), "size", 0)),
            "reference_design": "05",
            "graph_style": "workbench_sound_graph",
            "workbench": ui,
        }

    def _sound_editor_advanced_lab_state(self, track: Any, clip: Any) -> dict[str, Any]:
        ui = self._sound_editor_ui_state(clip)
        expanded = bool(getattr(clip, "_se_advanced_lab_expanded", False))
        if bool(ui.get("panel_matches_clip")):
            expanded = bool(ui.get("advanced_expanded", expanded))
        return {
            "schema": "tigerstudio.sound_editor.advanced_lab.v1",
            "track_id": _int(getattr(track, "id", 0)),
            "clip_id": _int(getattr(clip, "id", 0)),
            "expanded": expanded,
            "inline": True,
            "legacy_lab_count": self._advanced_sound_lab_count(),
            "workbench": ui,
        }

    def _sound_editor_ui_state(self, clip: Any) -> dict[str, Any]:
        panel = self._workbench_sound_editor_panel()
        if panel is None:
            return {
                "available": False,
                "panel_matches_clip": False,
                "visible": False,
                "jog_shuttle_visible": False,
                "advanced_expanded": bool(getattr(clip, "_se_advanced_lab_expanded", False)),
            }
        panel_clip = getattr(panel, "_clip", None)
        matches = panel_clip is clip
        is_visible = getattr(panel, "isVisible", None)
        jog = getattr(panel, "_jog_shuttle", None)
        jog_visible = getattr(jog, "isVisible", None)
        return {
            "available": True,
            "panel_matches_clip": matches,
            "visible": bool(is_visible()) if callable(is_visible) else True,
            "jog_shuttle_visible": bool(jog_visible()) if callable(jog_visible) else jog is not None,
            "advanced_expanded": bool(getattr(panel, "_advanced_expanded", getattr(clip, "_se_advanced_lab_expanded", False))),
        }

    def _advanced_sound_lab_count(self) -> int:
        try:
            return len(getattr(self._require_owner(), "_advanced_sound_labs", []) or [])
        except Exception:
            return 0

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

    def focus_ui_surface(
        self,
        *,
        surface: str = "timeline",
        kind: str = "video",
        track_id: int | None = None,
        clip_id: int | None = None,
        inspector_tab: str = "",
        show_audio_mixer: bool = False,
        show_audio_scopes: bool = False,
        open_aux_window: bool = False,
    ) -> dict[str, Any]:
        """Focus real editor UI surfaces before review/evidence capture.

        This is intentionally a thin bridge over existing editor widgets.  It
        does not draw demo UI or synthesize screenshots; it only selects real
        timeline items and reveals the corresponding dock/page that the live
        editor already owns.
        """

        owner = self._require_owner()
        surface_text = str(surface or "timeline").strip().lower().replace("-", "_")
        kind_text = str(kind or "video").strip().lower()
        if kind_text not in {"video", "audio", "live2d", "spine", "actor", ""}:
            raise ValueError("kind must be video, audio, live2d, spine, or actor")
        focused: list[str] = []

        if track_id is not None:
            try:
                if kind_text == "audio":
                    tid = _int(track_id)
                    cid = _int(clip_id) if clip_id is not None else None
                    if cid is None:
                        clips = list(getattr(self._audio_track(tid), "clips", []) or [])
                        if clips:
                            cid = _int(getattr(clips[0], "id", 0))
                    if cid is not None:
                        self.set_selection(kind="audio", track_id=tid, clip_id=cid, mode="replace")
                        selected = getattr(owner, "_on_audio_clip_selection_changed", None)
                        if callable(selected):
                            selected(tid, cid, 0, 0)
                        focused.append("audio_selection")
                    else:
                        self.select_track(kind="audio", track_id=tid)
                        focused.append("audio_track")
                elif kind_text in {"video", ""}:
                    tid = _int(track_id)
                    cid = _int(clip_id) if clip_id is not None else None
                    if cid is None:
                        clips = list(getattr(self._video_track(tid), "clips", []) or [])
                        if clips:
                            cid = _int(getattr(clips[0], "id", 0))
                    if cid is not None:
                        self.set_selection(kind="video", track_id=tid, clip_id=cid, mode="replace")
                        focused.append("video_selection")
                    else:
                        self.select_track(kind="video", track_id=tid)
                        focused.append("video_track")
            except Exception:
                # Review focus should not make a successful edit scenario fail.
                pass

        refresh = getattr(owner, "_refresh_workbench", None)
        if callable(refresh):
            try:
                refresh()
                focused.append("workbench")
            except Exception:
                pass

        if surface_text in {"color", "color_grade", "color_grading", "grading"}:
            show = getattr(owner, "_show_color_dock_page", None)
            if callable(show):
                try:
                    show()
                    focused.append("color_dock")
                except Exception:
                    pass
        elif surface_text not in {"color", "color_grade", "color_grading", "grading"}:
            switch = getattr(owner, "_switch_page", None)
            if callable(switch):
                try:
                    switch("edit")
                except Exception:
                    pass

        if surface_text in {"audio", "sound", "sound_editor", "audio_cleanup"} or show_audio_mixer:
            mixer = getattr(owner, "_on_audio_mixer_toggled", None)
            if callable(mixer):
                try:
                    mixer(True)
                    focused.append("audio_mixer")
                except Exception:
                    pass
        if surface_text in {"audio", "sound", "sound_editor", "audio_cleanup"} or show_audio_scopes:
            scopes = getattr(owner, "_on_audio_scopes_toggled", None)
            if callable(scopes):
                try:
                    scopes(True)
                    focused.append("audio_scopes")
                except Exception:
                    pass
            refresh_audio = getattr(owner, "_refresh_audio_workspace_panel", None)
            if callable(refresh_audio):
                try:
                    refresh_audio()
                    focused.append("audio_workspace")
                except Exception:
                    pass

        if surface_text in {"export", "render", "render_queue", "release"}:
            panels = getattr(owner, "_set_screenstudio_advanced_visible", None)
            if callable(panels):
                try:
                    panels(True, quiet=True)
                    focused.append("secondary_panels")
                except Exception:
                    pass
            set_open = getattr(owner, "_set_collapsible_host_open", None)
            host = getattr(owner, "_render_queue_section_host", None)
            if callable(set_open) and host is not None:
                try:
                    set_open(host, True)
                    focused.append("render_queue")
                except Exception:
                    pass
                for attr in (
                    "_creator_assist_section_host",
                    "_ai_script_edit_section_host",
                    "_audio_workspace_section_host",
                    "_subtitle_section_host",
                ):
                    sibling = getattr(owner, attr, None)
                    if sibling is None or sibling is host:
                        continue
                    try:
                        set_open(sibling, False)
                    except Exception:
                        pass
            scroll = getattr(owner, "_right_dock_scroll", None)
            ensure_visible = getattr(scroll, "ensureWidgetVisible", None)
            if callable(ensure_visible) and host is not None:
                try:
                    ensure_visible(host, 0, 8)
                    focused.append("right_dock_scroll")
                except Exception:
                    pass

        wb = getattr(owner, "_workbench_panel", None)
        tab = str(inspector_tab or "").strip().lower()
        if not tab:
            if surface_text in {"node", "nodes", "node_graph", "vfx", "ar_pbr"}:
                tab = "fx"
            elif surface_text in {"mask", "rotoscope", "chroma", "background_removal"}:
                tab = "mask"
            elif surface_text in {"audio", "sound", "sound_editor", "audio_cleanup"}:
                tab = "audio"
            elif surface_text in {"metadata", "export", "render", "release"}:
                tab = "meta"
        set_tab = getattr(wb, "_set_inspector_tab", None)
        if callable(set_tab) and tab:
            try:
                set_tab(tab)
                focused.append(f"inspector:{tab}")
            except Exception:
                pass

        if open_aux_window:
            if surface_text in {"live2d", "actor", "actors"} or kind_text == "live2d":
                opener = getattr(owner, "_open_live2d_viewer", None)
                if callable(opener):
                    try:
                        opener()
                        focused.append("live2d_viewer")
                    except Exception:
                        pass
            elif surface_text in {"spine"} or kind_text == "spine":
                opener = getattr(owner, "_open_spine_editor", None)
                if callable(opener):
                    try:
                        opener()
                        focused.append("spine_editor")
                    except Exception:
                        pass

        self._process_capture_events()
        return {
            "surface": surface_text,
            "kind": kind_text or "video",
            "track_id": _int(track_id, 0) if track_id is not None else None,
            "clip_id": _int(clip_id, 0) if clip_id is not None else None,
            "focused": focused,
        }

    def stage_render_queue_jobs(
        self,
        *,
        jobs: Sequence[Mapping[str, Any]] | None = None,
        render_queue_jobs: Sequence[Mapping[str, Any]] | None = None,
        open_panel: bool = True,
        **_unused: Any,
    ) -> dict[str, Any]:
        """Stage render queue jobs through the editor's real queue path."""

        owner = self._require_owner()
        rows = list(render_queue_jobs or jobs or [])
        payload = {"render_queue_jobs": [dict(row) for row in rows if isinstance(row, Mapping)]}
        if not payload["render_queue_jobs"]:
            raise ValueError("render.queue.stage requires jobs or render_queue_jobs")

        method = getattr(owner, "_stage_ai_script_render_jobs", None)
        if callable(method):
            result = dict(method(payload) or {})
        else:
            from app.capcut_apply import capcut_add_render_jobs_to_store
            from app.render_queue import RenderQueueStore

            panel = getattr(owner, "_render_queue_panel", None)
            store = getattr(panel, "_store", None) if panel is not None else None
            if store is None:
                store = RenderQueueStore()
            result = dict(capcut_add_render_jobs_to_store(store, payload) or {})
            if panel is not None:
                refresh = getattr(panel, "refresh_from_store", None)
                if callable(refresh):
                    refresh()

        if open_panel:
            try:
                owner._set_collapsible_host_open(getattr(owner, "_render_queue_section_host", None), True)
            except Exception:
                pass
        self._process_capture_events()
        return {
            "requested": len(payload["render_queue_jobs"]),
            "added": _int(result.get("added", 0), 0),
            "skipped": _int(result.get("skipped", 0), 0),
            "job_ids": list(result.get("job_ids") or []),
            "warnings": list(result.get("warnings") or []),
            "open_panel": bool(open_panel),
        }

    def capture_screenshot(self, *, path: str = "", target: str = "editor") -> dict[str, Any]:
        owner = self._require_owner()
        out = Path(str(path or "debugCapture/action_screenshot.png")).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        widget = self._capture_target_widget(owner, target)
        grab = getattr(widget, "grab", None)
        if not callable(grab):
            raise RuntimeError("capture.screenshot requires a Qt widget with grab()")
        pixmap = grab()
        if not pixmap.save(str(out)):
            raise RuntimeError(f"failed to save screenshot: {out}")
        return {"path": str(out.resolve()), "target": str(target or "editor")}

    def capture_gif(self, *, path: str = "", target: str = "editor", duration_ms: int = 3000, fps: int = 8) -> dict[str, Any]:
        owner = self._require_owner()
        method = getattr(owner, "_capture_action_gif", None)
        if not callable(method):
            return self._capture_gif_from_widget(path=path, target=target, duration_ms=duration_ms, fps=fps)
        out = method(path=str(path or ""), target=str(target or "editor"), duration_ms=max(1, _int(duration_ms, 3000)), fps=max(1, _int(fps, 8)))
        return {"path": str(out or path), "target": str(target or "editor"), "duration_ms": max(1, _int(duration_ms, 3000))}

    def run_review_scenario(self, *, scenario: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        owner = self.owner
        method = getattr(owner, "_run_review_scenario", None) if owner is not None else None
        if callable(method):
            result = method(str(scenario or ""), dict(params or {}))
            return dict(result or {})
        options = dict(params or {})
        from app.review_automation.deck_modes import normalize_deck_mode
        from app.review_automation.action_scenarios import run_action_review_scenario
        from app.review_automation.paths import (
            DEFAULT_REVIEW_OUTPUT_DIR,
            DEFAULT_REVIEW_REPORT,
            DEFAULT_REVIEW_SAMPLE_MANIFEST,
        )
        from app.review_automation.runner import build_review_automation_report

        scenario_text = str(scenario or "summary").strip() or "summary"
        deck_mode = normalize_deck_mode(str(options.pop("deck_mode", "") or scenario_text))
        project_root = Path(options.pop("project_root", Path.cwd()))
        out_dir = Path(options.pop("out_dir", DEFAULT_REVIEW_OUTPUT_DIR))
        report_path = Path(options.pop("report_path", DEFAULT_REVIEW_REPORT))
        sample_manifest = Path(options.pop("sample_manifest", DEFAULT_REVIEW_SAMPLE_MANIFEST))
        force = _bool(options.pop("force", False), False)
        run_action_scenario = _bool(options.pop("run_action_scenario", True), True)
        action_result: dict[str, Any] | None = None
        if run_action_scenario:
            action_result = run_action_review_scenario(
                project_root=project_root,
                out_dir=out_dir,
                sample_manifest=sample_manifest,
                scenario=scenario_text,
                force=force,
            )
        report = build_review_automation_report(
            project_root=project_root,
            out_dir=out_dir,
            report_path=report_path,
            sample_manifest=sample_manifest,
            write_html=_bool(options.pop("write_html", True), True),
            write_ppt=_bool(options.pop("write_ppt", False), False),
            deck_mode=deck_mode,
            force=force,
        )
        return {
            "scenario": scenario_text,
            "deck_mode": deck_mode,
            "executed": True,
            "ok": bool(report.get("ok")),
            "action_scenario": action_result or {},
            "report_path": str(report.get("report_path") or ""),
            "output_dir": str(report.get("output_dir") or ""),
            "summary": dict(report.get("summary") or {}),
            "warnings": list(report.get("warnings") or []),
            "ignored_params": options,
        }
