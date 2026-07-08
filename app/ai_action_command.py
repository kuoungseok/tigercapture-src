"""Rule-based AI command routing into the Python Action Registry.

This module intentionally handles only clear editor-action prompts. Ambiguous
script, subtitle, and story prompts should keep falling through to Script Edit.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any


VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".gif"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma"}


@dataclass(frozen=True)
class AIActionCommandPlan:
    prompt: str
    summary: str
    steps: tuple[dict[str, Any], ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0
    source: str = "rule_based_action_router"

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt": self.prompt,
            "summary": self.summary,
            "steps": [dict(step) for step in self.steps],
            "warnings": list(self.warnings),
            "confidence": float(self.confidence),
            "source": self.source,
        }


def build_ai_action_command_plan(
    prompt: str,
    snapshot: Mapping[str, Any] | None = None,
) -> AIActionCommandPlan | None:
    """Translate a clear natural-language editor command into action steps."""

    raw_prompt = str(prompt or "").strip()
    if not raw_prompt:
        return None
    snapshot = snapshot or {}
    text = _normalize(raw_prompt)
    compact = text.replace(" ", "")
    warnings: list[str] = []

    music_plan = _build_music_lab_action_plan(raw_prompt, text, compact, snapshot)
    if music_plan is not None:
        return music_plan

    if _requests_import_to_timeline(text, compact):
        media = _first_media(snapshot, prefer_video=not _mentions_audio(text, compact))
        if media is None:
            return AIActionCommandPlan(
                raw_prompt,
                "미디어 풀에 올릴 수 있는 영상/오디오가 없습니다.",
                (),
                ("미디어 풀에 파일을 먼저 추가한 뒤 다시 요청하세요.",),
                confidence=0.7,
            )
        params: dict[str, Any] = {
            "path": media["path"],
            "kind": media["kind"],
            "track_id": _first_track_id(snapshot, kind=media["kind"]),
            "at_ms": _append_time_ms(snapshot, kind=media["kind"]),
            "name": media.get("name") or Path(media["path"]).name,
        }
        if media.get("duration_ms"):
            params["duration_ms"] = media["duration_ms"]
        return AIActionCommandPlan(
            raw_prompt,
            f"{media['kind']} 미디어를 타임라인에 배치합니다.",
            ({"action": "media.import_to_timeline", "params": params},),
            confidence=0.9,
        )

    if _requests_nle_status(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Show the current NLE edit context.",
            ({"action": "timeline.nle_status", "params": {}},),
            confidence=0.82,
        )

    if _requests_professional_nle_readiness(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Show conservative professional NLE readiness diagnostics.",
            ({"action": "timeline.professional_nle_readiness", "params": {}},),
            confidence=0.82,
        )

    if _requests_creative_layer_readiness(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Show creative layer readiness diagnostics for effects, transitions, typography, nodes, actors, and 3D compositing.",
            ({"action": "creative_layer.readiness", "params": {}},),
            confidence=0.82,
        )

    if _requests_source_monitor_state(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Show Source monitor state.",
            ({"action": "source_monitor.state", "params": {}},),
            confidence=0.82,
        )

    if _requests_record_monitor_state(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Show Record monitor state.",
            ({"action": "record_monitor.state", "params": {}},),
            confidence=0.82,
        )

    if _requests_source_monitor_load(text, compact):
        media = _first_media(snapshot, prefer_video=True)
        if media is None:
            return AIActionCommandPlan(
                raw_prompt,
                "No media is available for the Source monitor.",
                (),
                ("Import media into the Media Pool first.",),
                confidence=0.62,
            )
        params = {
            "path": media["path"],
            "kind": media["kind"],
            "name": media.get("name") or Path(media["path"]).name,
        }
        if media.get("duration_ms"):
            params["duration_ms"] = media["duration_ms"]
        return AIActionCommandPlan(
            raw_prompt,
            "Load the first Media Pool item into the Source monitor.",
            ({"action": "source_monitor.load_media", "params": params},),
            confidence=0.8,
        )

    sound_plan = _build_sound_editor_action_plan(raw_prompt, text, compact, snapshot)
    if sound_plan is not None:
        return sound_plan

    if _requests_add_track(text, compact):
        kind = "audio" if _mentions_audio(text, compact) else "video"
        return AIActionCommandPlan(
            raw_prompt,
            f"{'오디오' if kind == 'audio' else '비디오'} 트랙을 추가합니다.",
            ({"action": "track.add", "params": {"kind": kind}},),
            confidence=0.82,
        )

    if _requests_timeline_fit(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Fit the timeline to the visible width.",
            ({"action": "timeline.fit", "params": {}},),
            confidence=0.8,
        )

    if _requests_history_undo(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Undo the previous edit.",
            ({"action": "history.undo", "params": {}},),
            confidence=0.82,
        )

    if _requests_history_redo(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Redo the next edit.",
            ({"action": "history.redo", "params": {}},),
            confidence=0.82,
        )

    if _requests_track_rename(text, compact):
        kind = "audio" if _mentions_audio(text, compact) else "video"
        name = _renamed_track_text(raw_prompt)
        return AIActionCommandPlan(
            raw_prompt,
            f"Rename the active {kind} track to {name}.",
            (
                {
                    "action": "track.rename",
                    "params": {"kind": kind, "track_id": _first_track_id(snapshot, kind=kind), "name": name},
                },
            ),
            confidence=0.78,
        )

    if _requests_track_lock(text, compact):
        kind = "audio" if _mentions_audio(text, compact) else "video"
        locked = not _requests_track_unlock(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            f"{'Unlock' if not locked else 'Lock'} the active {kind} track.",
            (
                {
                    "action": "track.lock",
                    "params": {"kind": kind, "track_id": _first_track_id(snapshot, kind=kind), "locked": locked},
                },
            ),
            confidence=0.8,
        )

    if _requests_track_mute(text, compact):
        kind = "audio" if _mentions_audio(text, compact) else "video"
        muted = not _requests_track_unmute(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            f"{'Unmute' if not muted else 'Mute'} the active {kind} track.",
            (
                {
                    "action": "track.mute",
                    "params": {"kind": kind, "track_id": _first_track_id(snapshot, kind=kind), "muted": muted},
                },
            ),
            confidence=0.8,
        )

    if _requests_select_all_clips(text, compact):
        kind = "all" if "all" in text or ("video" in text and "audio" in text) else ("audio" if _mentions_audio(text, compact) else "video")
        return AIActionCommandPlan(
            raw_prompt,
            f"Select all {kind} clips.",
            ({"action": "timeline.select_all", "params": {"kind": kind}},),
            confidence=0.82,
        )

    if _requests_select_first_clip(text, compact):
        clip = _selected_or_first_video_clip(snapshot)
        if clip is None:
            return AIActionCommandPlan(
                raw_prompt,
                "No video clip is available to select.",
                (),
                ("Import or place a video clip first.",),
                confidence=0.55,
            )
        return AIActionCommandPlan(
            raw_prompt,
            "Select the first available video clip.",
            (
                {
                    "action": "clip.select",
                    "params": {
                        "kind": "video",
                        "track_id": _int(clip.get("track_id"), 1),
                        "clip_id": _int(clip.get("clip_id", clip.get("id")), 0),
                        "mode": "replace",
                    },
                },
            ),
            confidence=0.8,
        )

    if _requests_select_track(text, compact):
        kind = "audio" if _mentions_audio(text, compact) else "video"
        return AIActionCommandPlan(
            raw_prompt,
            f"Select the active {kind} track.",
            (
                {
                    "action": "track.select",
                    "params": {
                        "kind": kind,
                        "track_id": _first_track_id(snapshot, kind=kind),
                        "select_first_clip": False,
                    },
                },
            ),
            confidence=0.76,
        )

    if _requests_jump_edit_point(text, compact):
        direction = "previous" if _requests_previous_edit_point(text, compact) else "next"
        return AIActionCommandPlan(
            raw_prompt,
            f"Jump to the {direction} edit point.",
            (
                {
                    "action": "timeline.jump_edit_point",
                    "params": {
                        "direction": direction,
                        "track_kind": "video",
                        "include_markers": False,
                    },
                },
            ),
            confidence=0.82,
        )

    if _requests_clear_in_out(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Clear the timeline In/Out range.",
            ({"action": "timeline.clear_in_out", "params": {}},),
            confidence=0.82,
        )

    if _requests_set_in_out_from_selection(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Set timeline In/Out from the selected clips.",
            ({"action": "timeline.set_in_out_from_selection", "params": {}},),
            confidence=0.8,
        )

    if _requests_jump_in_out(text, compact):
        edge = "out" if _contains_any(text, ("out", "end")) else "in"
        return AIActionCommandPlan(
            raw_prompt,
            f"Jump to timeline {edge.upper()} marker.",
            ({"action": "timeline.jump_in_out", "params": {"edge": edge}},),
            confidence=0.78,
        )

    if _requests_mark_in(text, compact):
        at_ms = _current_position_ms(snapshot)
        return AIActionCommandPlan(
            raw_prompt,
            f"Set timeline In at {_format_ms(at_ms)}.",
            ({"action": "timeline.set_in", "params": {"ms": at_ms}},),
            confidence=0.84,
        )

    if _requests_mark_out(text, compact):
        at_ms = _current_position_ms(snapshot)
        return AIActionCommandPlan(
            raw_prompt,
            f"Set timeline Out at {_format_ms(at_ms)}.",
            ({"action": "timeline.set_out", "params": {"ms": at_ms}},),
            confidence=0.84,
        )

    if _requests_play_clip_range(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Play the selected or current clip range, then restore the playhead.",
            ({"action": "timeline.play_clip_range", "params": {"restore_playhead": True}},),
            confidence=0.82,
        )

    if _requests_step_frame(text, compact):
        frames = -1 if _requests_previous_frame(text, compact) else 1
        return AIActionCommandPlan(
            raw_prompt,
            "Step the playhead by one frame.",
            ({"action": "timeline.step_frames", "params": {"frames": frames, "fps": 30}},),
            confidence=0.82,
        )

    if _requests_transport_control(text, compact):
        action = _transport_action_from_prompt(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            f"{action.title()} timeline playback.",
            ({"action": f"timeline.{action}", "params": {}},),
            confidence=0.8,
        )

    if _requests_shuttle_rate(text, compact):
        rate = _first_number(text, default=1.0)
        return AIActionCommandPlan(
            raw_prompt,
            f"Set shuttle playback to {rate:g}x.",
            ({"action": "timeline.set_shuttle_rate", "params": {"rate": rate}},),
            confidence=0.78,
        )

    if _requests_three_point_insert(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Insert the Source monitor range into the Record monitor/playhead.",
            (
                {
                    "action": "timeline.three_point_insert",
                    "params": {"target_track_id": _first_track_id(snapshot, kind="video")},
                },
            ),
            confidence=0.8,
        )

    if _requests_three_point_overwrite(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Overwrite the Record monitor/playhead range with the Source monitor range.",
            (
                {
                    "action": "timeline.three_point_overwrite",
                    "params": {"target_track_id": _first_track_id(snapshot, kind="video")},
                },
            ),
            confidence=0.78,
        )

    if _requests_clipboard_insert(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Insert timeline clips from the internal clipboard at the playhead.",
            ({"action": "timeline.insert_clipboard", "params": {}},),
            confidence=0.79,
        )

    if _requests_clipboard_overwrite(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Overwrite timeline clips from the internal clipboard at the playhead.",
            ({"action": "timeline.overwrite_clipboard", "params": {}},),
            confidence=0.77,
        )

    if _requests_clip_paste(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Paste timeline clips from the internal clipboard at the playhead.",
            ({"action": "clip.paste", "params": {}},),
            confidence=0.8,
        )

    if _requests_clip_cut_to_clipboard(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Cut selected timeline clips to the internal clipboard.",
            ({"action": "clip.cut_to_clipboard", "params": {"use_selection": True}},),
            confidence=0.78,
        )

    if _requests_clip_copy(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Copy selected timeline clips to the internal clipboard.",
            ({"action": "clip.copy", "params": {"use_selection": True}},),
            confidence=0.8,
        )

    if _requests_split(text, compact):
        track_id = _target_track_id_for_clip_edit(snapshot)
        at_ms = _current_or_clip_midpoint_ms(snapshot)
        if track_id <= 0:
            return AIActionCommandPlan(
                raw_prompt,
                "자를 수 있는 비디오 클립을 찾지 못했습니다.",
                (),
                ("먼저 클립을 선택하거나 비디오 트랙에 클립을 올려주세요.",),
                confidence=0.7,
            )
        return AIActionCommandPlan(
            raw_prompt,
            f"{_format_ms(at_ms)} 위치에서 클립을 자릅니다.",
            ({"action": "timeline.split", "params": {"track_id": track_id, "at_ms": at_ms}},),
            confidence=0.88,
        )

    if _requests_marker_list(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "List timeline markers.",
            ({"action": "timeline.marker.list", "params": {}},),
            confidence=0.8,
        )

    if _requests_snap_toggle(text, compact):
        enabled = _snap_enabled_from_prompt(text, compact)
        params = {} if enabled is None else {"enabled": enabled}
        return AIActionCommandPlan(
            raw_prompt,
            "Toggle timeline snapping.",
            ({"action": "timeline.snap.toggle", "params": params},),
            confidence=0.76,
        )

    if _requests_marker_move(text, compact):
        times = _time_values_ms_from_prompt(text)
        current_ms = _current_position_ms(snapshot)
        source_ms = times[0] if len(times) >= 2 else current_ms
        target_ms = times[-1] if times else current_ms
        return AIActionCommandPlan(
            raw_prompt,
            f"Move a timeline marker to {_format_ms(target_ms)}.",
            (
                {
                    "action": "timeline.marker.move",
                    "params": {"ms": source_ms, "new_ms": target_ms, "tolerance_ms": 500},
                },
            ),
            confidence=0.76,
        )

    if _requests_marker_jump(text, compact):
        direction = _marker_jump_direction(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            f"Jump playhead to the {direction} timeline marker.",
            (
                {
                    "action": "timeline.marker.jump",
                    "params": {"direction": direction, "from_ms": _current_position_ms(snapshot)},
                },
            ),
            confidence=0.78,
        )

    if _requests_marker_remove(text, compact):
        at_ms = _current_position_ms(snapshot)
        return AIActionCommandPlan(
            raw_prompt,
            f"Remove a timeline marker near {_format_ms(at_ms)}.",
            ({"action": "timeline.marker.remove", "params": {"ms": at_ms, "tolerance_ms": 500}},),
            confidence=0.76,
        )

    if _requests_marker(text, compact):
        at_ms = _current_position_ms(snapshot)
        label = _marker_label(raw_prompt)
        return AIActionCommandPlan(
            raw_prompt,
            f"{_format_ms(at_ms)} 위치에 마커를 추가합니다.",
            (
                {
                    "action": "timeline.marker.add",
                    "params": {"ms": at_ms, "label": label, "color": "#8A7CFF"},
                },
            ),
            confidence=0.9,
        )

    selected = _selected_or_first_video_clip(snapshot)
    if _requests_clear_transition(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clip was found for clearing the transition.")
        return AIActionCommandPlan(
            raw_prompt,
            "Clear the selected clip transition.",
            (
                {
                    "action": "transition.clear",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "side": "out",
                    },
                },
            ),
            confidence=0.8,
        )

    if _requests_transition_apply(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clip was found for applying the transition.")
        params = _transition_params_from_prompt(text)
        params.update({"track_id": selected["track_id"], "clip_id": selected["clip_id"], "side": "out"})
        return AIActionCommandPlan(
            raw_prompt,
            "Apply a transition to the selected clip edge.",
            ({"action": "transition.apply", "params": params},),
            confidence=0.78,
        )

    if _requests_select_range(text, compact):
        times = _time_values_ms_from_prompt(text)
        if len(times) < 2:
            return AIActionCommandPlan(
                raw_prompt,
                "A selection range needs a start and end time.",
                (),
                ("Use a command like: select range 1s to 3s.",),
                confidence=0.55,
            )
        mode = "replace"
        if "toggle" in text:
            mode = "toggle"
        elif "remove" in text:
            mode = "remove"
        elif "add" in text:
            mode = "add"
        return AIActionCommandPlan(
            raw_prompt,
            "Select timeline clips in the requested time range.",
            (
                {
                    "action": "selection.select_range",
                    "params": {
                        "start_ms": min(times[0], times[1]),
                        "end_ms": max(times[0], times[1]),
                        "mode": mode,
                        "include_partial": True,
                    },
                },
            ),
            confidence=0.82,
        )

    if _requests_track_target_clear(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Clear timeline track targets.",
            ({"action": "timeline.track_target.clear", "params": {"kind": _track_target_kind_from_prompt(text)}},),
            confidence=0.75,
        )

    if _requests_track_target_set(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Set timeline track target.",
            (
                {
                    "action": "timeline.track_target.set",
                    "params": {
                        "kind": _track_target_kind_from_prompt(text),
                        "track_id": _track_target_id_from_prompt(text),
                        "enabled": not _contains_any(text, ("disable", "untarget", "off")),
                        "exclusive": _contains_any(text, ("only", "exclusive", "solo")),
                    },
                },
            ),
            confidence=0.74,
        )

    if _requests_lift_extract(text, compact):
        action = "timeline.extract" if _contains_any(text, ("extract", "close gap", "ripple")) else "timeline.lift"
        return AIActionCommandPlan(
            raw_prompt,
            "Apply the current In/Out range edit to targeted tracks.",
            ({"action": action, "params": {}},),
            confidence=0.76,
        )

    if _requests_selection_ripple_delete(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clips were found for ripple delete.")
        return AIActionCommandPlan(
            raw_prompt,
            "Ripple-delete selected timeline clips.",
            (
                {
                    "action": "selection.ripple_delete",
                    "params": {"include_linked_audio": True},
                },
            ),
            confidence=0.78,
        )

    if _requests_cleanup_edges(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Clean up micro gaps and overlaps on timeline clip edges.",
            (
                {
                    "action": "timeline.cleanup_edges",
                    "params": {"frame_ms": 33, "close_gaps": True, "trim_overlaps": True},
                },
            ),
            confidence=0.76,
        )

    if _requests_list_timeline_gaps(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "List timeline gaps between clips.",
            ({"action": "timeline.gaps", "params": {}},),
            confidence=0.75,
        )

    if _requests_close_all_timeline_gaps(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Close all timeline gaps on targeted tracks.",
            ({"action": "timeline.close_all_gaps", "params": {}},),
            confidence=0.76,
        )

    if _requests_close_timeline_gap(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Close the current or next timeline gap.",
            ({"action": "timeline.close_gap", "params": {}},),
            confidence=0.74,
        )

    if _requests_precision_trim(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clip was found for precision trim.")
        edge = "left" if _contains_any(text, ("left", "start", " in ")) else "right"
        delta = _edit_delta_ms_from_prompt(text, compact)
        if edge == "left" and delta < 0 and not re.search(r"-\s*\d", text):
            delta = abs(delta)
        params = {
            "track_id": selected["track_id"],
            "clip_id": selected["clip_id"],
            "ripple": False,
        }
        if edge == "left":
            params["left_delta_ms"] = delta
        else:
            params["right_delta_ms"] = delta
        return AIActionCommandPlan(
            raw_prompt,
            "Precision trim the selected clip.",
            ({"action": "timeline.precision_trim", "params": params},),
            confidence=0.8,
        )

    if _requests_ripple_trim(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clip was found for ripple trim.")
        edge = "left" if _contains_any(text, ("left", "start", " in ")) else "right"
        delta = _edit_delta_ms_from_prompt(text, compact)
        if edge == "left" and delta < 0 and not re.search(r"-\s*\d", text):
            delta = abs(delta)
        return AIActionCommandPlan(
            raw_prompt,
            "Ripple trim the selected clip and move following clips.",
            (
                {
                    "action": "clip.ripple_trim",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "edge": edge,
                        "delta_ms": delta,
                        "ripple_linked_audio": True,
                    },
                },
            ),
            confidence=0.8,
        )

    if _requests_trim_to_playhead(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clip was found for trim-to-playhead.")
        return AIActionCommandPlan(
            raw_prompt,
            "Trim the selected clip edge to the playhead.",
            (
                {
                    "action": "timeline.trim_to_playhead",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "at_ms": _current_position_ms(snapshot),
                        "edge": _trim_to_playhead_edge_from_prompt(text),
                        "ripple": "ripple" in text,
                        "ripple_linked_audio": True,
                    },
                },
            ),
            confidence=0.8,
        )

    if _requests_selection_align_to_playhead(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clips were found for alignment.")
        return AIActionCommandPlan(
            raw_prompt,
            "Align selected clips to the playhead.",
            (
                {
                    "action": "selection.align_to_playhead",
                    "params": {"edge": _alignment_edge_from_prompt(text), "strict_links": True},
                },
            ),
            confidence=0.78,
        )

    if _requests_selection_align_to_marker(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clips were found for marker alignment.")
        direction = _marker_jump_direction(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            f"Align selected clips to the {direction} marker.",
            (
                {
                    "action": "selection.align_to_marker",
                    "params": {
                        "direction": direction,
                        "from_ms": _current_position_ms(snapshot),
                        "edge": _alignment_edge_from_prompt(text),
                        "strict_links": True,
                    },
                },
            ),
            confidence=0.78,
        )

    if _requests_selection_snap_nearest(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clips were found for snapping.")
        return AIActionCommandPlan(
            raw_prompt,
            "Snap selected clips to the nearest timeline target.",
            (
                {
                    "action": "selection.snap_to_nearest",
                    "params": {"edge": _alignment_edge_from_prompt(text), "strict_links": True},
                },
            ),
            confidence=0.77,
        )

    if _requests_selection_move(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "No selected video clips were found for the group move.")
        action_id = "selection.move"
        if "nudge" in text:
            action_id = "timeline.nudge" if "timeline" in text else "selection.nudge"
        if "nudge" in text and _contains_any(text, ("frame", "frames", "프레임")):
            action_id = "timeline.nudge_frames" if "timeline" in text else "selection.nudge_frames"
            return AIActionCommandPlan(
                raw_prompt,
                "Nudge the selected timeline clips by whole frames.",
                (
                    {
                        "action": action_id,
                        "params": {
                            "frames": _frame_delta_from_prompt(text),
                            "fps": 30,
                            "strict_links": True,
                        },
                    },
                ),
                confidence=0.79,
            )
        return AIActionCommandPlan(
            raw_prompt,
            "Move the selected timeline clips together.",
            (
                {
                    "action": action_id,
                    "params": {
                        "delta_ms": _edit_delta_ms_from_prompt(text, compact),
                        "strict_links": True,
                    },
                },
            ),
            confidence=0.78,
        )

    if _requests_unlink_audio(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "오디오 링크를 해제할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립의 오디오 링크를 해제합니다.",
            (
                {
                    "action": "clip.unlink_audio",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                    },
                },
            ),
            confidence=0.82,
        )

    if _requests_link_audio(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "오디오와 연결할 비디오 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립을 가장 가까운 오디오와 연결합니다.",
            (
                {
                    "action": "clip.link_audio",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "nearest": True,
                    },
                },
            ),
            confidence=0.8,
        )

    if _requests_sync_offset(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "싱크 오프셋을 적용할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립의 연결 오디오 싱크 오프셋을 조정합니다.",
            (
                {
                    "action": "clip.set_sync_offset",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "sync_offset_ms": _edit_delta_ms_from_prompt(text, compact, default=0),
                    },
                },
            ),
            confidence=0.74,
        )

    if _requests_j_cut(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "J컷을 적용할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립에 J컷을 적용합니다.",
            (
                {
                    "action": "clip.j_cut",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "extend_ms": abs(_edit_delta_ms_from_prompt(text, compact, default=500)),
                    },
                },
            ),
            confidence=0.78,
        )

    if _requests_l_cut(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "L컷을 적용할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립에 L컷을 적용합니다.",
            (
                {
                    "action": "clip.l_cut",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "extend_ms": abs(_edit_delta_ms_from_prompt(text, compact, default=500)),
                    },
                },
            ),
            confidence=0.78,
        )

    if _requests_slip(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "슬립 편집할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립을 슬립 편집합니다.",
            (
                {
                    "action": "clip.slip",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "delta_ms": _edit_delta_ms_from_prompt(text, compact),
                    },
                },
            ),
            confidence=0.78,
        )

    if _requests_slide_edit(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "슬라이드 편집할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립을 슬라이드 편집합니다.",
            (
                {
                    "action": "clip.slide",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "delta_ms": _edit_delta_ms_from_prompt(text, compact),
                    },
                },
            ),
            confidence=0.76,
        )

    if _requests_roll_edit(text, compact):
        pair = _roll_pair_for_selected_clip(snapshot, selected)
        if pair is None:
            return _missing_clip_plan(raw_prompt, "롤 편집할 인접 클립 경계를 찾지 못했습니다.")
        track_id, left_clip_id, right_clip_id = pair
        return AIActionCommandPlan(
            raw_prompt,
            "선택 클립 주변의 인접 경계를 롤 편집합니다.",
            (
                {
                    "action": "clip.roll",
                    "params": {
                        "track_id": track_id,
                        "left_clip_id": left_clip_id,
                        "right_clip_id": right_clip_id,
                        "delta_ms": _edit_delta_ms_from_prompt(text, compact),
                    },
                },
            ),
            confidence=0.72,
        )

    if _requests_speed(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "속도를 바꿀 클립을 찾지 못했습니다.")
        speed = _speed_from_prompt(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            f"선택/첫 클립 속도를 {speed:g}x로 바꿉니다.",
            (
                {
                    "action": "clip.set_speed",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "speed": speed,
                    },
                },
            ),
            confidence=0.84,
        )

    if _requests_fade(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "페이드를 줄 클립을 찾지 못했습니다.")
        fade_in, fade_out = _fade_values(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립에 페이드를 설정합니다.",
            (
                {
                    "action": "clip.set_fade",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "fade_in_ms": fade_in,
                        "fade_out_ms": fade_out,
                        "replace_existing": True,
                    },
                },
            ),
            confidence=0.8,
        )

    if _requests_title_or_text(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "텍스트를 올릴 클립을 찾지 못했습니다.")
        start_ms = _relative_clip_start_ms(selected, snapshot)
        end_ms = max(start_ms + 1200, min(_int(selected.get("duration_ms"), 3000), start_ms + 3000))
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립에 기본 타이틀 텍스트를 추가합니다.",
            (
                {
                    "action": "text.add",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "text": _title_text(raw_prompt),
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                        "style": {"font_size": 46, "color": "#FFFFFF", "shadow": True},
                        "animation": {"preset": "soft_pop"},
                    },
                },
            ),
            confidence=0.76,
        )

    if _requests_color_grade(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "색보정을 적용할 클립을 찾지 못했습니다.")
        grade = _color_grade_from_prompt(text, compact)
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립에 기본 색보정을 적용합니다.",
            (
                {
                    "action": "clip.set_color_grade",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "grade": grade,
                        "merge": True,
                    },
                },
            ),
            confidence=0.78,
        )

    if _requests_filter(text, compact):
        if selected is None:
            return _missing_clip_plan(raw_prompt, "필터를 적용할 클립을 찾지 못했습니다.")
        return AIActionCommandPlan(
            raw_prompt,
            "선택/첫 클립에 기본 필터를 적용합니다.",
            (
                {
                    "action": "clip.set_filter",
                    "params": {
                        "track_id": selected["track_id"],
                        "clip_id": selected["clip_id"],
                        "params": _filter_params_from_prompt(text, compact),
                        "merge": True,
                    },
                },
            ),
            confidence=0.75,
        )

    if warnings:
        return AIActionCommandPlan(raw_prompt, "액션 후보를 만들지 못했습니다.", (), tuple(warnings), confidence=0.35)
    return None


def _normalize(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _format_ms(ms: int) -> str:
    seconds = max(0, int(ms)) / 1000.0
    return f"{seconds:.1f}s"


def _contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)


def _mentions_audio(text: str, compact: str) -> bool:
    return _contains_any(text, ("오디오", "소리", "음악", "audio", "sound", "music")) or "음성" in compact


def _requests_import_to_timeline(text: str, compact: str) -> bool:
    if not _contains_any(text, ("미디어", "media", "video", "영상", "동영상", "오디오", "audio")):
        return False
    if not (_contains_any(text, ("타임라인", "timeline", "트랙", "track")) or "미디어풀" in compact):
        return False
    return _contains_any(text, ("올려", "놓", "배치", "추가", "넣", "import", "place", "add", "insert"))


def _requests_nle_status(text: str, compact: str) -> bool:
    return _contains_any(text, ("nle status", "edit context", "timeline context", "editing status", "show edit status"))


def _requests_professional_nle_readiness(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "professional nle readiness",
            "nle readiness",
            "premiere parity",
            "resolve parity",
            "professional nle status",
        ),
    )


def _requests_creative_layer_readiness(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "creative layer readiness",
            "creative readiness",
            "effect readiness",
            "transition readiness",
            "actor readiness",
            "3d readiness",
            "창작 레이어",
            "이펙트 상태",
            "트랜지션 상태",
        ),
    )


def _requests_source_monitor_state(text: str, compact: str) -> bool:
    return _contains_any(text, ("source monitor state", "show source monitor", "source monitor status"))


def _requests_record_monitor_state(text: str, compact: str) -> bool:
    return _contains_any(text, ("record monitor state", "show record monitor", "record monitor status"))


def _requests_source_monitor_load(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "load source monitor",
            "load into source monitor",
            "open source monitor",
            "put media in source monitor",
        ),
    )


def _build_music_lab_action_plan(
    raw_prompt: str,
    text: str,
    compact: str,
    snapshot: Mapping[str, Any],
) -> AIActionCommandPlan | None:
    edit_plan = _build_music_lab_edit_action_plan(raw_prompt, text, compact, snapshot)
    if edit_plan is not None:
        return edit_plan
    if not _requests_music_generation(text, compact):
        return None
    genre, mood = _music_genre_mood_from_prompt(text, compact)
    params: dict[str, Any] = {
        "prompt": raw_prompt,
        "duration_ms": _music_duration_ms_from_prompt(text, compact),
        "genre": genre,
        "mood": mood,
        "include_fx": True,
        "at_ms": _music_insert_time_ms(text, compact, snapshot),
        "auto_balance": True,
        "update_existing": True,
    }
    bpm = _music_bpm_from_prompt(text)
    if bpm is not None:
        params["bpm"] = bpm
    key = _music_key_from_prompt(text)
    if key:
        params["key"] = key
    if _contains_any(text, ("single track", "one track", "mix only", "mixed track")) or _contains_any(
        compact,
        ("\ud55c\ud2b8\ub799", "\ud558\ub098\uc758\ud2b8\ub799", "\ubbf9\uc2a4\ub9cc"),
    ):
        params["create_mix"] = True
    return AIActionCommandPlan(
        raw_prompt,
        "Create a Music Lab arrangement, render draft/starter or configured production audio, place it on the timeline, and balance the mixer.",
        ({"action": "music.compose_to_timeline", "params": params},),
        confidence=0.86,
    )


def _build_music_lab_edit_action_plan(
    raw_prompt: str,
    text: str,
    compact: str,
    snapshot: Mapping[str, Any],
) -> AIActionCommandPlan | None:
    composition = _latest_music_composition_row(snapshot)
    if composition is None:
        return None
    composition_id = str(composition.get("id") or "").strip()
    if not composition_id:
        return None
    if _requests_music_midi_export(text, compact):
        return AIActionCommandPlan(
            raw_prompt,
            "Export the latest Music Lab composition as a MIDI file.",
            ({"action": "music.export_midi", "params": {"composition_id": composition_id}},),
            confidence=0.84,
        )
    role_steps = _music_role_mute_steps(text, compact, snapshot)
    if role_steps:
        return AIActionCommandPlan(
            raw_prompt,
            "Update Music Lab stem mute states on the timeline.",
            tuple(role_steps),
            confidence=0.80,
        )
    if not _mentions_existing_music_edit(text, compact, snapshot):
        return None
    section_name = _music_section_name_from_prompt(text, compact, snapshot)
    intensity = _music_intensity_from_prompt(text, compact)
    params: dict[str, Any] = {"composition_id": composition_id, "section_name": section_name}
    if intensity is not None:
        params["intensity"] = intensity
    genre, mood = _music_genre_mood_from_prompt(text, compact)
    if mood:
        params["mood"] = mood
    steps = (
        {"action": "music.regenerate_section", "params": params},
        {
            "action": "music.render_to_timeline",
            "params": {"composition_id": composition_id, "update_existing": True},
        },
        {"action": "music.mixer.auto_balance", "params": {"composition_id": composition_id}},
    )
    return AIActionCommandPlan(
        raw_prompt,
        "Regenerate a Music Lab section, update existing draft/starter or configured production audio, and rebalance the mixer.",
        steps,
        confidence=0.82,
    )


def _latest_music_composition_row(snapshot: Mapping[str, Any]) -> Mapping[str, Any] | None:
    rows = [row for row in list(snapshot.get("music_compositions") or []) if isinstance(row, Mapping)]
    if rows:
        return rows[-1]
    ids = [
        str(track.get("music_composition_id") or "").strip()
        for track in list(snapshot.get("audio_tracks") or [])
        if isinstance(track, Mapping) and str(track.get("music_composition_id") or "").strip()
    ]
    if ids:
        return {"id": ids[-1]}
    return None


def _music_lab_selection_row(snapshot: Mapping[str, Any]) -> Mapping[str, Any]:
    row = snapshot.get("music_lab_selection")
    return row if isinstance(row, Mapping) else {}


def _uses_music_lab_selection(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "selected",
            "selection",
            "current",
            "current section",
            "current block",
            "current track",
            "this section",
            "this block",
            "this track",
            "chosen",
        ),
    ) or _contains_any(
        compact,
        (
            "\uc120\ud0dd",
            "\ud604\uc7ac",
            "\uc774\uac70",
            "\uc774\uad6c\uac04",
            "\uc774\ubd80\ubd84",
            "\uc774\ube14\ub85d",
            "\uc774\ud2b8\ub799",
        ),
    )


def _music_selected_section_name(snapshot: Mapping[str, Any]) -> str:
    selection = _music_lab_selection_row(snapshot)
    return str(selection.get("section_name") or "").strip().lower()


def _music_selected_role(snapshot: Mapping[str, Any]) -> str:
    selection = _music_lab_selection_row(snapshot)
    role = str(selection.get("role") or "").strip().lower()
    if role == "pad":
        return "chords"
    return role


def _requests_music_midi_export(text: str, compact: str) -> bool:
    return (
        _contains_any(text, ("export midi", "midi export", "save midi", "write midi"))
        or ("midi" in text and _contains_any(text, ("export", "save", "render")))
        or ("midi" in compact and _contains_any(compact, ("\ub0b4\ubcf4\ub0b4", "\uc800\uc7a5", "\ucd94\ucd9c")))
    )


def _mentions_existing_music_edit(text: str, compact: str, snapshot: Mapping[str, Any] | None = None) -> bool:
    music_subject = _contains_any(text, ("music", "bgm", "soundtrack", "song", "section")) or _contains_any(
        compact,
        ("\uc74c\uc545", "\ube0c\uae08", "\uc791\uace1", "\uad6c\uac04", "\uc139\uc158"),
    )
    selection_subject = bool(snapshot and _music_lab_selection_row(snapshot)) and _uses_music_lab_selection(text, compact)
    edit_word = _contains_any(
        text,
        (
            "stronger",
            "weaker",
            "softer",
            "more intense",
            "less intense",
            "regenerate",
            "change",
            "update",
            "modify",
            "make the main",
            "make main",
        ),
    ) or _contains_any(
        compact,
        (
            "\uac15\ud558",
            "\uc138\uac8c",
            "\uc57d\ud558",
            "\uc904\uc5ec",
            "\ubc14\uafd4",
            "\uc218\uc815",
            "\uac31\uc2e0",
            "\uc7ac\uc0dd\uc131",
            "\ud0a4\uc6cc",
        ),
    )
    section_word = _contains_any(text, ("intro", "build", "main", "chorus", "outro")) or _contains_any(
        compact,
        ("\uc778\ud2b8\ub85c", "\ube4c\ub4dc", "\uba54\uc778", "\ud6c4\ub834", "\uc544\uc6c3\ud2b8\ub85c"),
    )
    return (music_subject or selection_subject) and (edit_word or section_word)


def _music_section_name_from_prompt(text: str, compact: str, snapshot: Mapping[str, Any] | None = None) -> str:
    if _contains_any(text, ("intro",)) or "\uc778\ud2b8\ub85c" in compact:
        return "intro"
    if _contains_any(text, ("build", "rise")) or "\ube4c\ub4dc" in compact:
        return "build"
    if _contains_any(text, ("outro", "ending")) or _contains_any(compact, ("\uc544\uc6c3\ud2b8\ub85c", "\uc5d4\ub529")):
        return "outro"
    if snapshot and _uses_music_lab_selection(text, compact):
        selected = _music_selected_section_name(snapshot)
        if selected:
            return selected
    return "main"


def _music_intensity_from_prompt(text: str, compact: str) -> float | None:
    if _contains_any(text, ("weaker", "softer", "less intense", "calmer")) or _contains_any(
        compact,
        ("\uc57d\ud558", "\uc904\uc5ec", "\uc794\uc794", "\ub354\uc791"),
    ):
        return 0.42
    if _contains_any(text, ("stronger", "more intense", "powerful", "bigger", "epic")) or _contains_any(
        compact,
        ("\uac15\ud558", "\uc138\uac8c", "\uc6c5\uc7a5", "\ud0a4\uc6cc", "\ub354\ud06c"),
    ):
        return 0.95
    return None


def _music_role_mute_steps(text: str, compact: str, snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    remove_word = _contains_any(text, ("remove", "without", "mute", "drop", "no ")) or _contains_any(
        compact,
        ("\ube7c", "\uc5c6", "\uc81c\uac70", "\ubba4\ud2b8", "\ub044"),
    )
    only_word = _contains_any(text, ("only", "solo")) or "\ub9cc" in compact
    role_aliases = {
        "drums": ("drums", "drum", "\ub4dc\ub7fc"),
        "bass": ("bass", "\ubca0\uc774\uc2a4"),
        "chords": ("pad", "pads", "chords", "\ud328\ub4dc", "\ucf54\ub4dc"),
        "melody": ("melody", "lead", "\uba5c\ub85c\ub514", "\ub9ac\ub4dc"),
        "fx": ("fx", "impact", "\uc774\ud399\ud2b8", "\ud6a8\uacfc"),
    }
    mentioned = {
        role
        for role, aliases in role_aliases.items()
        if any(str(alias).lower() in text or str(alias).lower() in compact for alias in aliases)
    }
    if not mentioned and (remove_word or only_word) and _uses_music_lab_selection(text, compact):
        selected_role = _music_selected_role(snapshot)
        if selected_role:
            mentioned = {selected_role}
    if not mentioned:
        return []
    tracks = [
        track
        for track in list(snapshot.get("audio_tracks") or [])
        if isinstance(track, Mapping) and str(track.get("music_role") or "").strip().lower()
    ]
    if not tracks:
        return []
    steps: list[dict[str, Any]] = []
    if only_word:
        keep = set(mentioned)
        if "chords" in keep:
            keep.add("pad")
        for track in tracks:
            role = str(track.get("music_role") or "").strip().lower()
            steps.append(
                {
                    "action": "audio.track.mute",
                    "params": {"track_id": int(track.get("id") or 0), "muted": role not in keep},
                }
            )
        return [step for step in steps if int(step["params"].get("track_id") or 0) > 0]
    if remove_word:
        for track in tracks:
            role = str(track.get("music_role") or "").strip().lower()
            if role in mentioned:
                steps.append(
                    {
                        "action": "audio.track.mute",
                        "params": {"track_id": int(track.get("id") or 0), "muted": True},
                    }
                )
        return [step for step in steps if int(step["params"].get("track_id") or 0) > 0]
    return []


def _requests_music_generation(text: str, compact: str) -> bool:
    has_subject = _contains_any(
        text,
        (
            "background music",
            "bgm",
            "music bed",
            "soundtrack",
            "theme music",
            "compose music",
            "make music",
            "create music",
            "generate music",
            "song",
        ),
    ) or _contains_any(
        compact,
        (
            "\uc74c\uc545",
            "\ubc30\uacbd\uc74c\uc545",
            "\ubc30\uacbd\uc74c",
            "\ube0c\uae08",
            "\uc791\uace1",
            "\uc0ac\uc6b4\ub4dc\ud2b8\ub799",
            "\ud14c\ub9c8\uace1",
        ),
    )
    has_action = _contains_any(
        text,
        ("make", "create", "generate", "compose", "write", "add", "insert", "place"),
    ) or _contains_any(
        compact,
        (
            "\ub9cc\ub4e4",
            "\uc0dd\uc131",
            "\uc791\uace1",
            "\ucd94\uac00",
            "\ub123\uc5b4",
            "\uae54\uc544",
            "\ubc30\uce58",
        ),
    )
    return has_subject and has_action


def _music_duration_ms_from_prompt(text: str, compact: str) -> int:
    for pattern, scale in (
        (r"(\d+(?:\.\d+)?)\s*(?:seconds?|secs?|sec|s|\ucd08)", 1000.0),
        (r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min|\ubd84)", 60000.0),
    ):
        match = re.search(pattern, text)
        if match:
            return max(4000, min(180000, int(round(float(match.group(1)) * scale))))
    match = re.search(r"(\d+(?:\.\d+)?)\s*\ucd08", compact)
    if match:
        return max(4000, min(180000, int(round(float(match.group(1)) * 1000.0))))
    return 30000


def _music_bpm_from_prompt(text: str) -> int | None:
    match = re.search(r"\b(\d{2,3})\s*bpm\b", text)
    if not match:
        return None
    return max(48, min(180, int(match.group(1))))


def _music_key_from_prompt(text: str) -> str:
    match = re.search(r"\b([A-G](?:#|b)?)(?:\s*(major|minor|maj|min|m))?\b", text, flags=re.IGNORECASE)
    if not match:
        return ""
    if not match.group(2):
        return ""
    root = match.group(1).capitalize()
    mode = str(match.group(2) or "").lower()
    if mode in {"m", "min"}:
        mode = "minor"
    if mode == "maj":
        mode = "major"
    return f"{root} {mode}".strip()


def _music_genre_mood_from_prompt(text: str, compact: str) -> tuple[str, str]:
    if _contains_any(text, ("lofi", "lo-fi", "chill")) or _contains_any(compact, ("\ub85c\ud30c\uc774", "\uc794\uc794")):
        return "lofi", "chill"
    if _contains_any(text, ("tech demo", "techno", "edm", "electronic")) or "\ud14c\ud06c\ub370\ubaa8" in compact:
        return "electronic", "confident"
    if _contains_any(text, ("cinematic", "trailer", "epic")) or _contains_any(compact, ("\uc2dc\ub124\ub9c8\ud2f1", "\uc6c5\uc7a5")):
        return "cinematic", "epic"
    if _contains_any(text, ("corporate", "tutorial", "explain")) or _contains_any(compact, ("\uc124\uba85", "\ud29c\ud1a0\ub9ac\uc5bc")):
        return "corporate electronic", "clear"
    if _contains_any(text, ("happy", "bright", "uplifting")) or _contains_any(compact, ("\ubc1d", "\uc2e0\ub098", "\ud65c\uae30")):
        return "pop electronic", "bright"
    if _contains_any(text, ("dark", "tense")) or _contains_any(compact, ("\uc5b4\ub450", "\uae34\uc7a5")):
        return "cinematic electronic", "tense"
    return "cinematic electronic", "confident"


def _music_insert_time_ms(text: str, compact: str, snapshot: Mapping[str, Any]) -> int:
    if _contains_any(text, ("here", "current position", "playhead")) or _contains_any(
        compact,
        ("\uc5ec\uae30", "\ud604\uc7ac", "\uc9c0\uae08", "\ud50c\ub808\uc774\ud5e4\ub4dc"),
    ):
        return _current_position_ms(snapshot)
    return 0


def _requests_add_track(text: str, compact: str) -> bool:
    return ("트랙" in compact or "track" in text) and _contains_any(text, ("추가", "add", "만들", "create"))


def _requests_split(text: str, compact: str) -> bool:
    if "자막" in compact:
        return False
    if _requests_j_cut(text, compact) or _requests_l_cut(text, compact):
        return False
    return _contains_any(text, ("잘라", "자르", "컷", "분할", "split", "blade", "cut"))


def _requests_marker(text: str, compact: str) -> bool:
    if _requests_selection_align_to_marker(text, compact):
        return False
    return _contains_any(text, ("마커", "marker", "북마크", "bookmark")) or "표시해" in compact


def _requests_jump_edit_point(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "next edit",
            "previous edit",
            "prev edit",
            "next cut",
            "previous cut",
            "prev cut",
            "jump edit",
            "go to edit",
            "edit point",
        ),
    )


def _requests_previous_edit_point(text: str, compact: str) -> bool:
    return _contains_any(text, ("previous edit", "prev edit", "previous cut", "prev cut", "last edit", "back edit"))


def _requests_set_in_out_from_selection(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "set in out from selection",
            "set in/out from selection",
            "mark selection range",
            "mark selected range",
            "set range from selection",
        ),
    )


def _requests_jump_in_out(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "jump to in",
            "jump to out",
            "go to in",
            "go to out",
            "goto in",
            "goto out",
        ),
    )


def _requests_mark_in(text: str, compact: str) -> bool:
    return _contains_any(text, ("mark in", "set in", "in point", "set in point"))


def _requests_mark_out(text: str, compact: str) -> bool:
    return _contains_any(text, ("mark out", "set out", "out point", "set out point"))


def _requests_clear_in_out(text: str, compact: str) -> bool:
    return _contains_any(text, ("clear in out", "clear in/out", "clear range", "clear marks", "clear in and out"))


def _requests_play_clip_range(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "play selected clip",
            "preview selected clip",
            "audition selected clip",
            "play current clip",
            "preview current clip",
            "audition clip",
            "play clip range",
        ),
    )


def _requests_step_frame(text: str, compact: str) -> bool:
    return _contains_any(text, ("next frame", "previous frame", "prev frame", "step frame", "frame step"))


def _requests_previous_frame(text: str, compact: str) -> bool:
    return _contains_any(text, ("previous frame", "prev frame", "back frame"))


def _requests_transport_control(text: str, compact: str) -> bool:
    stripped = text.strip().lower()
    return stripped in {"play", "pause", "stop"} or _contains_any(
        text,
        ("start playback", "pause playback", "stop playback", "resume playback"),
    )


def _transport_action_from_prompt(text: str, compact: str) -> str:
    if _contains_any(text, ("pause", "pause playback")):
        return "pause"
    if _contains_any(text, ("stop", "stop playback")):
        return "stop"
    return "play"


def _requests_shuttle_rate(text: str, compact: str) -> bool:
    return _contains_any(text, ("shuttle", "jog shuttle", "playback rate")) and bool(re.search(r"\d", text))


def _first_number(text: str, default: float = 0.0) -> float:
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", text)
    if not match:
        return float(default)
    try:
        return float(match.group(1))
    except Exception:
        return float(default)


def _requests_clip_copy(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "copy selected clip",
            "copy selected clips",
            "copy clips",
            "copy timeline clip",
            "copy timeline clips",
        ),
    )


def _requests_clip_cut_to_clipboard(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "cut selected clip",
            "cut selected clips",
            "cut clips to clipboard",
            "cut to clipboard",
            "cut timeline clip",
            "cut timeline clips",
        ),
    )


def _requests_clipboard_insert(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "insert clipboard",
            "insert paste",
            "insert clips",
            "insert selected paste",
            "insert timeline clips",
        ),
    )


def _requests_three_point_insert(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "three point insert",
            "3 point insert",
            "3-point insert",
            "insert source monitor",
            "source monitor insert",
        ),
    )


def _requests_three_point_overwrite(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "three point overwrite",
            "3 point overwrite",
            "3-point overwrite",
            "overwrite source monitor",
            "source monitor overwrite",
        ),
    )


def _requests_clipboard_overwrite(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "overwrite clipboard",
            "overwrite paste",
            "overwrite clips",
            "overwrite timeline clips",
            "replace with clipboard",
        ),
    )


def _requests_clip_paste(text: str, compact: str) -> bool:
    return _contains_any(text, ("paste clip", "paste clips", "paste timeline clip", "paste timeline clips"))


def _requests_select_all_clips(text: str, compact: str) -> bool:
    return _contains_any(text, ("select all clips", "select all video clips", "select all audio clips", "select every clip"))


def _requests_select_first_clip(text: str, compact: str) -> bool:
    return _contains_any(text, ("select first clip", "select first video clip", "select the first clip"))


def _requests_select_track(text: str, compact: str) -> bool:
    return _contains_any(text, ("select track", "select video track", "select audio track", "focus track", "focus video track", "focus audio track"))


def _requests_timeline_fit(text: str, compact: str) -> bool:
    return _contains_any(text, ("fit timeline", "timeline fit", "zoom fit", "fit to timeline", "fit view"))


def _requests_history_undo(text: str, compact: str) -> bool:
    stripped = text.strip().lower()
    return stripped in {"undo", "ctrl z", "ctrl+z"} or _contains_any(text, ("undo edit", "undo last", "revert last edit"))


def _requests_history_redo(text: str, compact: str) -> bool:
    stripped = text.strip().lower()
    return stripped in {"redo", "ctrl y", "ctrl+y"} or _contains_any(text, ("redo edit", "redo last"))


def _requests_track_lock(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "lock track",
            "lock video track",
            "lock audio track",
            "unlock track",
            "unlock video track",
            "unlock audio track",
            "track lock",
        ),
    )


def _requests_track_unlock(text: str, compact: str) -> bool:
    return _contains_any(text, ("unlock track", "unlock video track", "unlock audio track", "track unlock"))


def _requests_track_mute(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "mute track",
            "mute video track",
            "mute audio track",
            "unmute track",
            "unmute video track",
            "unmute audio track",
            "track mute",
        ),
    )


def _requests_track_unmute(text: str, compact: str) -> bool:
    return _contains_any(text, ("unmute track", "unmute video track", "unmute audio track", "track unmute"))


def _requests_track_rename(text: str, compact: str) -> bool:
    return _contains_any(text, ("rename track", "rename video track", "rename audio track", "name track", "set track name"))


def _requests_marker_list(text: str, compact: str) -> bool:
    return _contains_any(text, ("list markers", "show markers", "marker list", "timeline markers"))


def _requests_snap_toggle(text: str, compact: str) -> bool:
    return _contains_any(text, ("snap on", "snap off", "toggle snap", "snapping on", "snapping off", "enable snap", "disable snap"))


def _snap_enabled_from_prompt(text: str, compact: str) -> bool | None:
    if _contains_any(text, ("snap off", "snapping off", "disable snap")):
        return False
    if _contains_any(text, ("snap on", "snapping on", "enable snap")):
        return True
    return None


def _requests_marker_move(text: str, compact: str) -> bool:
    if _contains_any(text, ("remove marker", "delete marker", "clear marker", "remove timeline marker", "delete timeline marker")):
        return False
    return _contains_any(
        text,
        (
            "move marker",
            "shift marker",
            "nudge marker",
            "move timeline marker",
            "shift timeline marker",
            "marker move",
        ),
    )


def _requests_marker_jump(text: str, compact: str) -> bool:
    if _requests_selection_align_to_marker(text, compact):
        return False
    if not _contains_any(text, ("marker", "bookmark")):
        return False
    return _contains_any(
        text,
        (
            "next marker",
            "previous marker",
            "prev marker",
            "jump marker",
            "jump to marker",
            "go to marker",
            "nearest marker",
            "closest marker",
        ),
    )


def _marker_jump_direction(text: str, compact: str) -> str:
    if _contains_any(text, ("previous marker", "prev marker", "prior marker", "back marker")):
        return "previous"
    if _contains_any(text, ("nearest marker", "closest marker")):
        return "nearest"
    return "next"


def _requests_marker_remove(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "delete marker",
            "remove marker",
            "clear marker",
            "delete timeline marker",
            "remove timeline marker",
        ),
    )


def _requests_speed(text: str, compact: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:x|배속)", text)) or _contains_any(
        text,
        ("빠르게", "느리게", "속도", "speed", "slow", "fast"),
    )


def _requests_fade(text: str, compact: str) -> bool:
    return "페이드" in compact or "fade" in text


def _requests_title_or_text(text: str, compact: str) -> bool:
    if "자막" in compact or "subtitle" in text or "caption" in text:
        return False
    return _contains_any(text, ("타이틀", "제목", "텍스트", "글자", "title", "text")) and _contains_any(
        text,
        ("넣", "추가", "올려", "add", "insert", "create", "만들"),
    )


def _requests_color_grade(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        ("색보정", "컬러", "밝게", "어둡게", "대비", "채도", "따뜻", "차갑", "color", "grade", "brightness", "contrast"),
    )


def _requests_filter(text: str, compact: str) -> bool:
    return _contains_any(text, ("필터", "샤픈", "선명", "blur", "흐림", "vignette", "비네트", "filter"))


def _requests_clear_transition(text: str, compact: str) -> bool:
    if not _contains_any(text, ("transition", "트랜지션", "전환", "dissolve", "디졸브")):
        return False
    return _contains_any(text, ("clear", "remove", "delete", "지워", "삭제", "없애"))


def _requests_transition_apply(text: str, compact: str) -> bool:
    if _requests_clear_transition(text, compact):
        return False
    if _contains_any(text, ("cross dissolve", "dip white", "dip black", "fade white", "fade black")):
        return True
    if _contains_any(text, ("transition", "트랜지션", "전환", "dissolve", "디졸브")):
        return _contains_any(text, ("apply", "add", "put", "insert", "넣", "추가", "적용"))
    return False


def _transition_params_from_prompt(text: str) -> dict[str, Any]:
    lowered = str(text or "").casefold()
    times = _time_values_ms_from_prompt(lowered)
    duration_ms = abs(_int(times[0], 500)) if times else 500
    if "white" in lowered or "화이트" in lowered:
        return {"preset_id": "transition-dip-white", "duration_ms": duration_ms}
    if "black" in lowered or "블랙" in lowered or "검정" in lowered:
        return {"preset_id": "transition-dip-black", "duration_ms": duration_ms}
    if "beat" in lowered:
        return {"preset_id": "transition-beat-dissolve", "duration_ms": duration_ms}
    if "long" in lowered or "slow" in lowered:
        return {"preset_id": "transition-long-dissolve", "duration_ms": duration_ms}
    return {"preset_id": "transition-clean-dissolve", "transition_type": "dissolve", "duration_ms": duration_ms}


def _requests_unlink_audio(text: str, compact: str) -> bool:
    return _contains_any(text, ("unlink audio", "unlink")) or (
        "오디오" in compact and "링크" in compact and _contains_any(text, ("해제", "풀", "끊", "분리"))
    )


def _requests_link_audio(text: str, compact: str) -> bool:
    return _contains_any(text, ("link audio", "linked audio")) or (
        "오디오" in compact and "링크" in compact and not _requests_unlink_audio(text, compact)
    )


def _requests_sync_offset(text: str, compact: str) -> bool:
    return ("싱크" in compact or "sync" in text) and _contains_any(text, ("오프셋", "offset", "밀", "당겨", "조정"))


def _requests_j_cut(text: str, compact: str) -> bool:
    return "j컷" in compact or "j-cut" in text or "j cut" in text


def _requests_l_cut(text: str, compact: str) -> bool:
    return "l컷" in compact or "l-cut" in text or "l cut" in text


def _requests_ripple_trim(text: str, compact: str) -> bool:
    return "ripple trim" in text or ("ripple" in text and "trim" in text)


def _requests_precision_trim(text: str, compact: str) -> bool:
    return "precision trim" in text or "exact trim" in text


def _requests_trim_to_playhead(text: str, compact: str) -> bool:
    if "trim" in text and "playhead" in text:
        return True
    if "extend" in text and "playhead" in text:
        return True
    return _contains_any(
        text,
        (
            "trim to playhead",
            "trim selected to playhead",
            "trim selected clip to playhead",
            "trim left to playhead",
            "trim right to playhead",
            "trim start to playhead",
            "trim end to playhead",
            "extend to playhead",
        ),
    )


def _trim_to_playhead_edge_from_prompt(text: str) -> str:
    if _contains_any(text, ("left", "start", " in ")):
        return "left"
    if _contains_any(text, ("right", "end", " out ")):
        return "right"
    return "auto"


def _requests_select_range(text: str, compact: str) -> bool:
    return "select range" in text or "range select" in text or "select clips from" in text


def _requests_track_target_set(text: str, compact: str) -> bool:
    return _contains_any(text, ("target video track", "target audio track", "track target", "target track"))


def _requests_track_target_clear(text: str, compact: str) -> bool:
    return _contains_any(text, ("clear track targets", "clear track target", "untarget all tracks"))


def _track_target_kind_from_prompt(text: str) -> str:
    if "audio" in text:
        return "audio"
    if "clear" in text and "video" not in text:
        return "all"
    if "all" in text and "clear" in text:
        return "all"
    return "video"


def _track_target_id_from_prompt(text: str) -> int:
    match = re.search(r"(?:track|v|a)\s*(\d+)", text)
    if match:
        return max(0, _int(match.group(1), 1))
    match = re.search(r"\b(\d+)\b", text)
    if match:
        return max(0, _int(match.group(1), 1))
    return 1


def _requests_lift_extract(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "lift range",
            "lift in out",
            "lift in/out",
            "extract range",
            "extract in out",
            "extract in/out",
            "delete range and close gap",
        ),
    )


def _requests_selection_ripple_delete(text: str, compact: str) -> bool:
    has_selection = _contains_any(text, ("selection", "selected", "selected clips", "selected clip", "group"))
    has_delete = _contains_any(text, ("ripple delete", "delete and close gap", "close gap delete"))
    return has_selection and has_delete


def _requests_cleanup_edges(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "cleanup edges",
            "clean up edges",
            "cleanup timeline edges",
            "close micro gaps",
            "fix micro gaps",
            "fix tiny overlaps",
            "cleanup gaps",
        ),
    )


def _requests_list_timeline_gaps(text: str, compact: str) -> bool:
    return _contains_any(text, ("list gaps", "show gaps", "timeline gaps", "find gaps"))


def _requests_close_all_timeline_gaps(text: str, compact: str) -> bool:
    return _contains_any(text, ("close all gaps", "remove all gaps", "delete all gaps"))


def _requests_close_timeline_gap(text: str, compact: str) -> bool:
    if _requests_close_all_timeline_gaps(text, compact):
        return False
    return _contains_any(text, ("close gap", "remove gap", "delete gap"))


def _requests_selection_align_to_playhead(text: str, compact: str) -> bool:
    has_selection = _contains_any(text, ("selection", "selected", "selected clips", "selected clip", "group"))
    has_align = _contains_any(text, ("align", "snap", "match", "move"))
    return has_selection and has_align and _contains_any(text, ("playhead", "current time", "current position"))


def _requests_selection_align_to_marker(text: str, compact: str) -> bool:
    has_selection = _contains_any(text, ("selection", "selected", "selected clips", "selected clip", "group"))
    has_align = _contains_any(text, ("align", "snap", "match", "move"))
    return has_selection and has_align and _contains_any(text, ("marker", "bookmark"))


def _requests_selection_snap_nearest(text: str, compact: str) -> bool:
    has_selection = _contains_any(text, ("selection", "selected", "selected clips", "selected clip", "group"))
    return has_selection and _contains_any(
        text,
        ("snap nearest", "snap to nearest", "nearest snap", "snap selection", "snap selected", "to nearest"),
    )


def _alignment_edge_from_prompt(text: str) -> str:
    if _contains_any(text, ("end", "out", "right edge")):
        return "end"
    return "start"


def _requests_selection_move(text: str, compact: str) -> bool:
    has_selection = _contains_any(text, ("selection", "selected", "selected clips", "selected clip group", "multi-select", "group", "timeline"))
    has_move = _contains_any(text, ("move", "nudge", "shift", "offset"))
    has_delta = bool(re.search(r"[-+]?\d+(?:\.\d+)?\s*(?:ms|s|sec|seconds?|frame|frames|프레임)", text))
    return has_selection and has_move and has_delta


def _requests_slip(text: str, compact: str) -> bool:
    return "슬립" in compact or "slip" in text


def _requests_slide_edit(text: str, compact: str) -> bool:
    if "슬라이드" in compact:
        return _contains_any(text, ("편집", "이동", "클립", "edit", "move"))
    return "slide edit" in text or "slide clip" in text


def _requests_roll_edit(text: str, compact: str) -> bool:
    if "스크롤" in compact:
        return False
    return "roll edit" in text or ("롤" in compact and _contains_any(text, ("편집", "트림", "경계", "edit", "trim")))


def _build_sound_editor_action_plan(
    raw_prompt: str,
    text: str,
    compact: str,
    snapshot: Mapping[str, Any],
) -> AIActionCommandPlan | None:
    if not _sound_prompt_mentions_audio(text, compact):
        return None

    basic = _sound_basic_from_prompt(text, compact)
    effects = _sound_effects_from_prompt(text, compact)
    preset = _sound_ai_master_preset_from_prompt(text, compact)
    wants_loudness = _requests_audio_loudness_report(text, compact)
    wants_stems = _requests_audio_stem_separation(text, compact)
    if not any((basic, effects, preset, wants_loudness, wants_stems)):
        return None

    clip = _selected_or_first_audio_clip(snapshot)
    if clip is None:
        return AIActionCommandPlan(
            raw_prompt,
            "No timeline audio clip is available for AI sound control.",
            (),
            ("Extract or place an audio clip on the timeline first.",),
            confidence=0.62,
        )

    target = {"track_id": int(clip["track_id"]), "clip_id": int(clip["clip_id"])}
    if wants_loudness:
        return AIActionCommandPlan(
            raw_prompt,
            "Read a loudness report for the selected audio clip.",
            ({"action": "audio.loudness_report", "params": dict(target)},),
            confidence=0.84,
        )

    if wants_stems:
        params = dict(target)
        params.update({"prefer_demucs": True, "add_to_timeline": True})
        return AIActionCommandPlan(
            raw_prompt,
            "Separate the selected audio clip into vocal and instrumental stems.",
            ({"action": "audio.separate_stems", "params": params},),
            ("Stem separation can take time and may fall back when Demucs is unavailable.",),
            confidence=0.83,
        )

    if preset:
        params = dict(target)
        params.update({"preset": preset, "focus_workbench": True})
        return AIActionCommandPlan(
            raw_prompt,
            f"Apply the {preset} Sound Editor AI Master preset.",
            ({"action": "audio.sound_editor.apply_ai_preset", "params": params},),
            confidence=0.86,
        )

    params = dict(target)
    params.update({"merge": True, "focus_workbench": True})
    if basic:
        params["basic"] = basic
    if effects:
        params["effects"] = effects
    return AIActionCommandPlan(
        raw_prompt,
        "Apply Sound Editor controls to the selected audio clip.",
        ({"action": "audio.sound_editor.apply_effects", "params": params},),
        confidence=0.82,
    )


def _sound_prompt_mentions_audio(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        (
            "audio",
            "sound",
            "voice",
            "dialogue",
            "vocal",
            "music",
            "loudness",
            "lufs",
            "stem",
            "suno",
            "udio",
            "ace-step",
            "ace step",
            "ai master",
            "mastering",
        ),
    ) or _contains_any(
        compact,
        (
            "\uc624\ub514\uc624",
            "\uc0ac\uc6b4\ub4dc",
            "\uc18c\ub9ac",
            "\uc74c\uc131",
            "\uc74c\uc545",
            "\ubaa9\uc18c\ub9ac",
            "\ub300\ud654",
            "\ubcf4\uceec",
            "\ub77c\uc6b0\ub4dc\ub2c8\uc2a4",
            "\uc2a4\ud15c",
            "\ub9c8\uc2a4\ud130\ub9c1",
        ),
    )


def _requests_audio_loudness_report(text: str, compact: str) -> bool:
    return _contains_any(
        text,
        ("loudness", "lufs", "true peak", "audio report", "sound report"),
    ) or (
        _contains_any(compact, ("\ub77c\uc6b0\ub4dc\ub2c8\uc2a4", "\uc74c\ub7c9"))
        and _contains_any(compact, ("\ub9ac\ud3ec\ud2b8", "\ubd84\uc11d"))
    )


def _requests_audio_stem_separation(text: str, compact: str) -> bool:
    if _contains_any(
        text,
        (
            "separate stems",
            "stem separation",
            "separate vocal",
            "isolate vocal",
            "vocal isolate",
            "instrumental",
            "remove vocal",
        ),
    ):
        return True
    has_target = _contains_any(compact, ("\ubcf4\uceec", "\uc2a4\ud15c", "\ubc18\uc8fc"))
    has_action = _contains_any(compact, ("\ubd84\ub9ac", "\uc81c\uac70", "\ub9cc\ub4e4"))
    return has_target and has_action


def _sound_ai_master_preset_from_prompt(text: str, compact: str) -> str:
    squashed = compact.replace("-", "")
    if "suno v3" in text or "suno v 3" in text or "sunov3" in squashed or "suno3" in squashed:
        return "Suno v3"
    if "suno v4" in text or "suno v 4" in text or "sunov4" in squashed or "suno4" in squashed:
        return "Suno v4"
    if re.search(r"\budio\b", text):
        return "Udio"
    if "ace-step" in text or "ace step" in text or "acestep" in squashed:
        return "ACE-Step"
    if "generic ai" in text:
        return "Generic AI"
    if "custom" in text:
        return "Custom"
    wants_master = _contains_any(
        text,
        ("ai master", "ai mastering", "master audio", "audio master", "music master", "mastering"),
    ) or _contains_any(
        compact,
        ("\ub9c8\uc2a4\ud130", "\ub9c8\uc2a4\ud130\ub9c1", "\uc5d0\uc774\uc544\uc774\ub9c8\uc2a4\ud130"),
    )
    return "Generic AI" if wants_master else ""


def _sound_effects_from_prompt(text: str, compact: str) -> dict[str, Any]:
    cleanup = _contains_any(
        text,
        (
            "cleanup voice",
            "cleanup audio",
            "cleanup sound",
            "clean voice",
            "clean up voice",
            "clean up audio",
            "clean up sound",
            "clean dialogue",
            "dialogue cleanup",
            "voice cleanup",
            "noise reduction",
            "remove noise",
            "denoise",
            "de-reverb",
            "dereverb",
            "deesser",
            "de-esser",
            "podcast",
            "broadcast voice",
        ),
    ) or _contains_any(
        compact,
        (
            "\uc815\ub9ac",
            "\ub178\uc774\uc988",
            "\uc7a1\uc74c",
            "\uc81c\uac70",
            "\ud074\ub9b0",
            "\uae68\ub057",
            "\ub2e4\ub4ec",
            "\uce58\ucc30\uc74c",
            "\ud31f\uce90\uc2a4\ud2b8",
        ),
    )
    cleanup = cleanup or (
        _contains_any(text, ("clean", "cleanup", "clean up"))
        and _contains_any(text, ("voice", "audio", "sound", "dialogue", "vocal"))
    )
    broadcast = _contains_any(text, ("podcast", "broadcast", "radio voice", "voiceover")) or _contains_any(
        compact,
        ("\ud31f\uce90\uc2a4\ud2b8", "\ubc29\uc1a1", "\ub098\ub808\uc774\uc158"),
    )
    if not cleanup and not broadcast:
        return {}

    effects: dict[str, Any] = {
        "dialogue_cleanup": {
            "enabled": True,
            "strength": 0.75,
            "noise_reduction": 8.0,
            "de_reverb": 0.35,
            "presence_db": 2.0,
            "auto_level": True,
        },
        "deesser": {
            "enabled": True,
            "freq": 6000.0,
            "threshold": -32.0,
            "reduction": 35.0,
        },
        "loudness": {
            "enabled": True,
            "target_i": -14.0,
            "true_peak": -1.0,
            "lra": 11.0,
        },
    }
    if broadcast:
        effects["eq"] = {
            "enabled": True,
            "low": {"freq": 80.0, "gain": -3.0, "q": 0.7},
            "mid": {"freq": 1000.0, "gain": 2.0, "q": 1.0},
            "high": {"freq": 10000.0, "gain": 3.0, "q": 0.7},
        }
        effects["comp"] = {
            "enabled": True,
            "threshold": -18.0,
            "ratio": 4.0,
            "attack_ms": 5.0,
            "release_ms": 150.0,
            "makeup_db": 3.0,
            "knee_db": 3.0,
        }
    return effects


def _sound_basic_from_prompt(text: str, compact: str) -> dict[str, Any]:
    basic: dict[str, Any] = {}
    track_target = "track" in text and "clip" not in text
    if not track_target and (
        _contains_any(text, ("unmute", "restore sound"))
        or _contains_any(compact, ("\uc74c\uc18c\uac70\ud574\uc81c", "\uc18c\ub9ac\ucf1c"))
    ):
        basic["muted"] = False
    elif not track_target and (
        _contains_any(text, ("mute", "silence audio", "turn off sound"))
        or _contains_any(compact, ("\uc74c\uc18c\uac70", "\ubb34\uc74c"))
    ):
        basic["muted"] = True

    db = _sound_gain_db_from_prompt(text)
    if db is not None:
        basic["gain_db"] = db
    elif _contains_any(text, ("louder", "volume up", "boost volume", "raise volume", "increase volume")) or _contains_any(
        compact,
        ("\uc74c\ub7c9\uc62c", "\ubcfc\ub968\uc62c", "\uc18c\ub9ac\ud06c", "\ud0a4\uc6cc"),
    ):
        basic["gain_db"] = 3.0
    elif _contains_any(text, ("quieter", "volume down", "lower volume", "reduce volume")) or _contains_any(
        compact,
        ("\uc74c\ub7c9\ub0b4", "\ubcfc\ub968\ub0b4", "\uc18c\ub9ac\uc904"),
    ):
        basic["gain_db"] = -3.0

    if _contains_any(text, ("pan left", "left channel")) or _contains_any(compact, ("\uc67c\ucabd", "\uc88c\uce21")):
        basic["pan"] = -0.5
    elif _contains_any(text, ("pan right", "right channel")) or _contains_any(compact, ("\uc624\ub978\ucabd", "\uc6b0\uce21")):
        basic["pan"] = 0.5
    elif _contains_any(text, ("center pan", "pan center", "center audio")) or "\uac00\uc6b4\ub370" in compact:
        basic["pan"] = 0.0

    if _contains_any(text, ("fade in", "fade-in")) or "\ud398\uc774\ub4dc\uc778" in compact:
        basic["fade_in_ms"] = _sound_duration_ms_from_prompt(text, 1000)
    if _contains_any(text, ("fade out", "fade-out")) or "\ud398\uc774\ub4dc\uc544\uc6c3" in compact:
        basic["fade_out_ms"] = _sound_duration_ms_from_prompt(text, 1000)
    if ("fade" in text or "\ud398\uc774\ub4dc" in compact) and "fade_in_ms" not in basic and "fade_out_ms" not in basic:
        value = _sound_duration_ms_from_prompt(text, 1000)
        basic["fade_in_ms"] = value
        basic["fade_out_ms"] = value

    if "reverse" in text or "\ub4a4\uc9d1" in compact:
        basic["reverse"] = True

    if _contains_any(text, ("pitch up", "higher pitch")) or _contains_any(compact, ("\ud53c\uce58\uc62c", "\ub192\uac8c")):
        basic["pitch_st"] = 2.0
    elif _contains_any(text, ("pitch down", "lower pitch")) or _contains_any(compact, ("\ud53c\uce58\ub0b4", "\ub0ae\uac8c")):
        basic["pitch_st"] = -2.0
    else:
        match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(?:st|semitones?)", text)
        if match and "pitch" in text:
            basic["pitch_st"] = max(-24.0, min(24.0, float(match.group(1))))

    if re.search(r"\d+(?:\.\d+)?\s*x", text) and _contains_any(text, ("speed", "audio", "sound", "voice")):
        basic["speed"] = max(0.1, min(4.0, _speed_from_prompt(text, compact)))
    elif _contains_any(text, ("speed up audio", "faster audio", "faster sound")):
        basic["speed"] = 1.25
    elif _contains_any(text, ("slow audio", "slower audio", "slower sound")):
        basic["speed"] = 0.75
    return basic


def _sound_gain_db_from_prompt(text: str) -> float | None:
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*db", text)
    if not match:
        return None
    return max(-36.0, min(18.0, float(match.group(1))))


def _sound_duration_ms_from_prompt(text: str, default: int) -> int:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(ms|s|sec|seconds?)", text)
    if not match:
        return int(default)
    value = float(match.group(1))
    unit = str(match.group(2)).casefold()
    if unit == "ms":
        return max(0, min(60_000, int(round(value))))
    return max(0, min(60_000, int(round(value * 1000.0))))


def _selected_or_first_audio_clip(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    selected = list(snapshot.get("selected_clips") or [])
    for row in selected:
        if not isinstance(row, Mapping):
            continue
        kind = str(row.get("track_kind") or row.get("kind") or "").casefold()
        if kind and kind != "audio":
            continue
        clip_id = _int(row.get("clip_id"), -1)
        track_id = _int(row.get("track_id"), -1)
        if clip_id <= 0:
            continue
        clip = _find_audio_clip(snapshot, track_id=track_id, clip_id=clip_id)
        if clip:
            return clip

    for row in selected:
        if not isinstance(row, Mapping):
            continue
        clip_id = _int(row.get("clip_id"), -1)
        track_id = _int(row.get("track_id"), -1)
        if clip_id <= 0:
            continue
        clip = _find_audio_clip(snapshot, track_id=track_id, clip_id=clip_id)
        if clip:
            return clip

    for track in list(snapshot.get("audio_tracks") or []):
        if not isinstance(track, Mapping):
            continue
        track_id = _int(track.get("id"), 0)
        for clip in list(track.get("clips") or []):
            if isinstance(clip, Mapping):
                row = dict(clip)
                row["track_id"] = track_id
                row["clip_id"] = _int(row.get("id"), 0)
                return row
    return None


def _find_audio_clip(snapshot: Mapping[str, Any], *, track_id: int, clip_id: int) -> dict[str, Any] | None:
    for track in list(snapshot.get("audio_tracks") or []):
        if not isinstance(track, Mapping):
            continue
        current_track_id = _int(track.get("id"), 0)
        if track_id > 0 and current_track_id != track_id:
            continue
        for clip in list(track.get("clips") or []):
            if not isinstance(clip, Mapping):
                continue
            if _int(clip.get("id"), 0) == clip_id:
                row = dict(clip)
                row["track_id"] = current_track_id
                row["clip_id"] = clip_id
                return row
    return None


def _first_media(snapshot: Mapping[str, Any], *, prefer_video: bool = True) -> dict[str, Any] | None:
    rows = [row for row in list(snapshot.get("media_pool") or []) if isinstance(row, Mapping)]
    order = ("video", "audio") if prefer_video else ("audio", "video")
    for kind in order:
        for row in rows:
            media = _media_row(row)
            if media and media["kind"] == kind:
                return media
    return None


def _media_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    path = str(row.get("path") or row.get("source_path") or row.get("file") or "").strip()
    if not path:
        return None
    suffix = Path(path).suffix.casefold()
    kind = str(row.get("kind") or row.get("type") or "").casefold()
    if kind not in {"video", "audio"}:
        if suffix in VIDEO_EXTS:
            kind = "video"
        elif suffix in AUDIO_EXTS:
            kind = "audio"
    if kind not in {"video", "audio"}:
        return None
    duration = _int(row.get("duration_ms") or row.get("duration") or 0, 0)
    return {"path": path, "kind": kind, "name": str(row.get("name") or Path(path).name), "duration_ms": duration}


def _first_track_id(snapshot: Mapping[str, Any], *, kind: str = "video") -> int:
    key = "audio_tracks" if kind == "audio" else "video_tracks"
    for row in list(snapshot.get(key) or []):
        if isinstance(row, Mapping):
            value = _int(row.get("id"), 0)
            if value > 0:
                return value
    return 1


def _append_time_ms(snapshot: Mapping[str, Any], *, kind: str = "video") -> int:
    key = "audio_tracks" if kind == "audio" else "video_tracks"
    end = 0
    for track in list(snapshot.get(key) or []):
        if not isinstance(track, Mapping):
            continue
        for clip in list(track.get("clips") or []):
            if not isinstance(clip, Mapping):
                continue
            end = max(end, _int(clip.get("timeline_out_ms", clip.get("end_ms", 0))))
            start = _int(clip.get("timeline_in_ms", clip.get("offset_ms", 0)))
            end = max(end, start + _int(clip.get("duration_ms", 0)))
    return max(0, end)


def _current_position_ms(snapshot: Mapping[str, Any]) -> int:
    return max(0, _int(snapshot.get("current_position_ms"), 0))


def _selected_or_first_video_clip(snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    selected = list(snapshot.get("selected_clips") or [])
    for row in selected:
        if not isinstance(row, Mapping):
            continue
        clip_id = _int(row.get("clip_id"), -1)
        track_id = _int(row.get("track_id"), -1)
        if clip_id <= 0:
            continue
        clip = _find_video_clip(snapshot, track_id=track_id, clip_id=clip_id)
        if clip:
            return clip
    for track in list(snapshot.get("video_tracks") or []):
        if not isinstance(track, Mapping):
            continue
        track_id = _int(track.get("id"), 0)
        for clip in list(track.get("clips") or []):
            if isinstance(clip, Mapping):
                row = dict(clip)
                row["track_id"] = track_id
                row["clip_id"] = _int(row.get("id"), 0)
                return row
    return None


def _find_video_clip(snapshot: Mapping[str, Any], *, track_id: int, clip_id: int) -> dict[str, Any] | None:
    for track in list(snapshot.get("video_tracks") or []):
        if not isinstance(track, Mapping):
            continue
        current_track_id = _int(track.get("id"), 0)
        if track_id > 0 and current_track_id != track_id:
            continue
        for clip in list(track.get("clips") or []):
            if not isinstance(clip, Mapping):
                continue
            if _int(clip.get("id"), 0) == clip_id:
                row = dict(clip)
                row["track_id"] = current_track_id
                row["clip_id"] = clip_id
                return row
    return None


def _roll_pair_for_selected_clip(
    snapshot: Mapping[str, Any],
    selected: Mapping[str, Any] | None,
) -> tuple[int, int, int] | None:
    if selected is None:
        return None
    track_id = _int(selected.get("track_id"), 0)
    clip_id = _int(selected.get("clip_id"), 0)
    if track_id <= 0 or clip_id <= 0:
        return None
    for track in list(snapshot.get("video_tracks") or []):
        if not isinstance(track, Mapping) or _int(track.get("id"), 0) != track_id:
            continue
        clips = [
            clip for clip in list(track.get("clips") or [])
            if isinstance(clip, Mapping) and _int(clip.get("id"), 0) > 0
        ]
        clips.sort(key=lambda row: _int(row.get("timeline_in_ms"), 0))
        for index, clip in enumerate(clips):
            if _int(clip.get("id"), 0) != clip_id:
                continue
            if index < len(clips) - 1:
                right = clips[index + 1]
                if _int(clip.get("timeline_out_ms"), 0) == _int(right.get("timeline_in_ms"), -1):
                    return track_id, clip_id, _int(right.get("id"), 0)
            if index > 0:
                left = clips[index - 1]
                if _int(left.get("timeline_out_ms"), 0) == _int(clip.get("timeline_in_ms"), -1):
                    return track_id, _int(left.get("id"), 0), clip_id
    return None


def _time_values_ms_from_prompt(text: str) -> list[int]:
    values: list[int] = []
    for match in re.finditer(r"([-+]?\d+(?:\.\d+)?)\s*(ms|s|sec|seconds?)", text):
        number = float(match.group(1))
        unit = str(match.group(2) or "ms").casefold()
        if unit in {"s", "sec", "second", "seconds"}:
            values.append(max(0, int(round(number * 1000.0))))
        else:
            values.append(max(0, int(round(number))))
    return values


def _target_track_id_for_clip_edit(snapshot: Mapping[str, Any]) -> int:
    clip = _selected_or_first_video_clip(snapshot)
    if clip:
        return _int(clip.get("track_id"), 0)
    return _first_track_id(snapshot, kind="video")


def _current_or_clip_midpoint_ms(snapshot: Mapping[str, Any]) -> int:
    current = _current_position_ms(snapshot)
    clip = _selected_or_first_video_clip(snapshot)
    if clip:
        start = _int(clip.get("timeline_in_ms"), 0)
        end = _int(clip.get("timeline_out_ms"), 0) or start + _int(clip.get("duration_ms"), 0)
        if start < current < end:
            return current
        if end > start:
            return start + max(1, (end - start) // 2)
    return current


def _relative_clip_start_ms(clip: Mapping[str, Any], snapshot: Mapping[str, Any]) -> int:
    current = _current_position_ms(snapshot)
    timeline_start = _int(clip.get("timeline_in_ms"), 0)
    if current >= timeline_start:
        return max(0, current - timeline_start)
    return 0


def _missing_clip_plan(prompt: str, summary: str) -> AIActionCommandPlan:
    return AIActionCommandPlan(
        prompt,
        summary,
        (),
        ("먼저 비디오 클립을 선택하거나 타임라인에 클립을 올려주세요.",),
        confidence=0.62,
    )


def _marker_label(prompt: str) -> str:
    text = str(prompt or "").strip()
    return text[:32] if text else "AI marker"


def _speed_from_prompt(text: str, compact: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:x|배속)", text)
    if match:
        return max(0.05, min(16.0, float(match.group(1))))
    if _contains_any(text, ("느리게", "slow")):
        return 0.5
    if "4배" in compact:
        return 4.0
    if "3배" in compact:
        return 3.0
    if "2배" in compact or _contains_any(text, ("빠르게", "fast")):
        return 2.0
    return 1.5


def _fade_values(text: str, compact: str) -> tuple[int, int]:
    value = 500
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:초|s|sec)", text)
    if match:
        value = int(max(0.0, min(10.0, float(match.group(1)))) * 1000)
    if "인" in compact and "아웃" not in compact:
        return value, 0
    if "아웃" in compact and "인" not in compact:
        return 0, value
    return value, value


def _edit_delta_ms_from_prompt(text: str, compact: str, default: int = 500) -> int:
    value = int(default)
    match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(ms|밀리초|밀리|초|s|sec|frame|frames|프레임)?", text)
    if match:
        number = float(match.group(1))
        unit = str(match.group(2) or "ms").casefold()
        if unit in {"초", "s", "sec"}:
            value = int(round(number * 1000.0))
        elif unit in {"frame", "frames", "프레임"}:
            value = int(round(number * 33.0))
        else:
            value = int(round(number))
    if value > 0 and _contains_any(text, ("왼쪽", "앞으로", "이전", "earlier", "left", "back")):
        value = -value
    return max(-60_000, min(60_000, value))


def _frame_delta_from_prompt(text: str, default: int = 1) -> int:
    value = int(default)
    match = re.search(r"([-+]?\d+)\s*(?:frame|frames|프레임)", text)
    if match:
        value = int(match.group(1))
    if value > 0 and _contains_any(text, ("earlier", "left", "back", "previous")):
        value = -value
    return max(-10_000, min(10_000, value))


def _title_text(prompt: str) -> str:
    text = str(prompt or "").strip()
    match = re.search(r"['\"]([^'\"]+)['\"]", text)
    if match:
        return match.group(1).strip()[:80] or "Title"
    return "Title"


def _renamed_track_text(prompt: str) -> str:
    text = str(prompt or "").strip()
    match = re.search(r"['\"]([^'\"]+)['\"]", text)
    if match:
        return match.group(1).strip()[:64] or "Track"
    match = re.search(r"\bto\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()[:64] or "Track"
    match = re.search(r"\bas\s+(.+)$", text, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()[:64] or "Track"
    return "Track"


def _color_grade_from_prompt(text: str, compact: str) -> dict[str, int]:
    grade = {"brightness": 8, "contrast": 8, "saturation": 6}
    if _contains_any(text, ("밝게", "brightness")):
        grade["brightness"] = 16
    if "어둡" in text:
        grade["brightness"] = -12
    if _contains_any(text, ("대비", "contrast")):
        grade["contrast"] = 18
    if _contains_any(text, ("채도", "saturation")):
        grade["saturation"] = 18
    if _contains_any(text, ("따뜻", "warm")):
        grade["temperature"] = 16
    if _contains_any(text, ("차갑", "cool")):
        grade["temperature"] = -16
    return grade


def _filter_params_from_prompt(text: str, compact: str) -> dict[str, Any]:
    if _contains_any(text, ("샤픈", "선명", "sharp")):
        return {"sharpen": 0.35, "enabled": True}
    if _contains_any(text, ("흐림", "blur")):
        return {"blur": 0.35, "enabled": True}
    if _contains_any(text, ("비네트", "vignette")):
        return {"vignette": 0.28, "enabled": True}
    return {"enabled": True, "sharpen": 0.2}
