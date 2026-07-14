"""Domain slice of editing action adapter methods."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import copy
from pathlib import Path
from typing import Any

from app.actions.editor_adapter_scalars import _bool, _float, _int



class EditingClipAdapterMixin:
    """Focused action adapter methods split from EditingAdapterMixin."""

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

    def list_frame_repairs(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
            _track, clip = self._video_track_and_clip(track_id, clip_id)
            from app.frame_repair import normalize_frame_repairs

            repairs = normalize_frame_repairs(getattr(clip, "frame_repairs", []) or [])
            clip.frame_repairs = repairs
            return {
                "track_id": _int(track_id),
                "clip_id": _int(clip_id),
                "repair_count": len(repairs),
                "frame_repairs": repairs,
            }

    def add_frame_repair(
            self,
            *,
            track_id: int,
            clip_id: int,
            source_start_ms: int,
            source_end_ms: int,
            method: str = "interpolate",
            algorithm: str = "optical_flow",
            label: str = "",
        ) -> dict[str, Any]:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            from app.frame_repair import make_frame_repair_range, normalize_frame_repairs

            clip_start = max(0, _int(getattr(clip, "source_in_ms", 0)))
            clip_end = _int(getattr(clip, "effective_source_out_ms", 0))
            if clip_end <= clip_start:
                clip_end = max(clip_start + 1, _int(getattr(clip, "source_duration_ms", clip_start + 1)))
            start = max(clip_start, _int(source_start_ms))
            end = min(clip_end, _int(source_end_ms))
            if end <= start:
                raise ValueError("frame repair range is outside the clip source window")
            before = normalize_frame_repairs(getattr(clip, "frame_repairs", []) or [])
            row = make_frame_repair_range(
                source_start_ms=start,
                source_end_ms=end,
                method=str(method or "interpolate"),
                algorithm=str(algorithm or "optical_flow"),
                label=str(label or ""),
            )
            clip.frame_repairs = normalize_frame_repairs([*before, row])
            self._after_timeline_mutation("Action add frame repair")
            player = getattr(self.owner, "_player", None)
            refresh = getattr(player, "refresh_current_frame", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    pass
            return {
                "track_id": _int(getattr(track, "id", track_id)),
                "clip_id": _int(getattr(clip, "id", clip_id)),
                "repair_id": row["id"],
                "source_start_ms": row["source_start_ms"],
                "source_end_ms": row["source_end_ms"],
                "method": row["method"],
                "algorithm": row["algorithm"],
                "repair_count_before": len(before),
                "repair_count_after": len(getattr(clip, "frame_repairs", []) or []),
            }

    def remove_frame_repair(
            self,
            *,
            track_id: int,
            clip_id: int,
            repair_id: str = "",
            source_start_ms: int | None = None,
            source_end_ms: int | None = None,
            clear_all: bool = False,
        ) -> dict[str, Any]:
            track, clip = self._video_track_and_clip(track_id, clip_id)
            from app.frame_repair import normalize_frame_repairs

            repairs = normalize_frame_repairs(getattr(clip, "frame_repairs", []) or [])
            before_count = len(repairs)
            if clear_all:
                kept: list[dict[str, Any]] = []
            elif str(repair_id or "").strip():
                target = str(repair_id or "").strip()
                kept = [row for row in repairs if str(row.get("id") or "") != target]
            elif source_start_ms is not None and source_end_ms is not None:
                start = _int(source_start_ms)
                end = max(start + 1, _int(source_end_ms))
                kept = [
                    row for row in repairs
                    if int(row["source_end_ms"]) <= start or int(row["source_start_ms"]) >= end
                ]
            else:
                raise ValueError("repair_id, source range, or clear_all is required")
            clip.frame_repairs = kept
            changed = len(kept) != before_count
            if changed:
                self._after_timeline_mutation("Action remove frame repair")
                player = getattr(self.owner, "_player", None)
                refresh = getattr(player, "refresh_current_frame", None)
                if callable(refresh):
                    try:
                        refresh()
                    except Exception:
                        pass
            return {
                "track_id": _int(getattr(track, "id", track_id)),
                "clip_id": _int(getattr(clip, "id", clip_id)),
                "repair_count_before": before_count,
                "repair_count_after": len(kept),
                "removed_count": max(0, before_count - len(kept)),
                "changed": changed,
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
                from app.image_media import is_image_path

                if is_audio_path(media_path):
                    kind_text = "audio"
                elif is_video_path(media_path):
                    kind_text = "video"
                elif is_image_path(media_path):
                    kind_text = "image"
                else:
                    raise ValueError(f"unsupported media extension: {media_path.suffix}")
            if kind_text == "image":
                from app.image_media import DEFAULT_IMAGE_DURATION_MS, is_image_path
                from app.video_editor_media_import_controller import (
                    add_image_track_with_source,
                    append_image_clip_to_track,
                )

                if not is_image_path(media_path):
                    raise ValueError(f"unsupported image extension: {media_path.suffix}")
                duration = max(100, _int(duration_ms, DEFAULT_IMAGE_DURATION_MS))
                start = max(0, _int(at_ms)) if at_ms is not None else self._current_playhead_ms()
                if track_id is not None:
                    track = self._video_track(track_id)
                    clip = append_image_clip_to_track(
                        owner,
                        track,
                        media_path,
                        start_ms=start if at_ms is not None else None,
                        duration_ms=duration,
                    )
                    if clip is None:
                        raise ValueError("image clip could not be added")
                else:
                    track = add_image_track_with_source(
                        owner,
                        media_path,
                        start_ms=start,
                        duration_ms=duration,
                    )
                    clips = list(getattr(track, "clips", []) or [])
                    clip = clips[0] if clips else None
                    if clip is None:
                        raise ValueError("image clip could not be added")
                self._after_timeline_mutation("Action import image to timeline")
                return {
                    "kind": "image",
                    "track_type": str(getattr(track, "track_type", "image") or "image"),
                    "path": str(media_path.resolve()),
                    "track_id": _int(getattr(track, "id", 0)),
                    "clip_id": _int(getattr(clip, "id", 0)),
                    "timeline_in_ms": _int(getattr(clip, "timeline_in_ms", start)),
                    "duration_ms": duration,
                    "program_output": bool(getattr(clip, "program_output", True)),
                }
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
            raise ValueError("kind must be video, audio, or image")

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
