from __future__ import annotations

import copy

from app.i18n import tr
from app.audio_tracks import AudioClip, AudioTrack
from app.timeline_model import CutSegment, FadeSegment, SpeedSegment, VideoClip
from app.timeline_track_row import TrackRow
from app.video_editor_nested_sequence import cut_clip_window
from app.video_editor_transport_workflow import _timeline_frame_ms
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QGridLayout, QLabel, QSpinBox, QVBoxLayout


def _video_editor_window_cls():
    from app.video_editor_window import VideoEditorWindow

    return VideoEditorWindow


def _selected_locked_video_track_id(self, selected_pairs: list | None = None) -> int | None:
    selected_pairs = list(
        selected_pairs
        if selected_pairs is not None
        else getattr(self, "_selected_clips", []) or []
    )
    if not selected_pairs:
        return None
    find_track = getattr(self, "_find_track", None)
    tracks_by_id = {
        int(getattr(track, "id", -1)): track
        for track in getattr(self, "_tracks", []) or []
    }
    for tid, _cid in selected_pairs:
        tid = int(tid)
        track = find_track(tid) if callable(find_track) else tracks_by_id.get(tid)
        if track is not None and bool(getattr(track, "locked", False)):
            return tid
    return None


def _clear_selected_clip_transition(self) -> None:
    track, clip = self._selected_video_clip()
    if clip is None:
        track, clip = self._workflow_target_video_clip()
    if track is None or clip is None:
        self._flash_status(tr("veditor.clip_badge.status.select_transition_clip"))
        return
    if not str(getattr(clip, "transition_out_type", "") or ""):
        self._flash_status(tr("veditor.clip_badge.status.no_transition_clear"))
        return
    clear_fn = getattr(self, "_clear_clip_transition", None)
    if callable(clear_fn):
        clear_fn(track, clip)
        return
    clip.transition_out_type = ""
    clip.transition_out_ms = 0
    try:
        row = getattr(self, "_track_rows", {}).get(getattr(track, "id", None))
        if row is not None:
            row.update()
    except Exception:
        pass
    self._refresh_player_tracks()
    self._refresh_preview_soft(track)
    self._refresh_workbench()
    self._register_change("clear clip transition")
    self._flash_status(tr("veditor.clip_badge.status.transition_cleared"))


def _split_audio_clip(self, track: AudioTrack, clip: AudioClip) -> None:
    """Split ``clip`` into two clips on the SAME track at the clip's
    current selection [sel_start, sel_end] (clip-local ms). Leaves
    the track intact with two clips that can be moved independently."""
    sel_start = clip.selection_start_ms
    sel_end = clip.selection_end_ms
    if sel_start < 0 or sel_end <= sel_start:
        return

    a_trim_start = clip.trim_start_ms
    a_trim_end = clip.trim_start_ms + sel_start
    b_trim_start = clip.trim_start_ms + sel_end
    b_trim_end = clip.effective_trim_end_ms

    a_keeps = a_trim_end > a_trim_start
    b_keeps = b_trim_end > b_trim_start
    if not a_keeps and not b_keeps:
        # Entire clip cut out - drop it from the track.
        try:
            track.clips.remove(clip)
        except ValueError:
            pass
        self._remove_clip_from_waveform_jobs(clip)
        self._audio_mixer.update_track(track)
        self._refresh_player_tracks()
        self._audio_rows[track.id].update()
        return

    new_clip_b: AudioClip | None = None
    if b_keeps:
        new_clip_b = AudioClip(
            id=self._next_clip_id(),
            source_path=clip.source_path,
            duration_ms=clip.duration_ms,
            # Leave Piece B at the project-timeline position where
            # its source content used to play - there's now a real
            # gap where the cut was. User can drag either piece to
            # close the gap or move them freely.
            offset_ms=clip.offset_ms + sel_end,
            trim_start_ms=b_trim_start,
            trim_end_ms=b_trim_end,
            fade_in_ms=0,
            fade_out_ms=clip.fade_out_ms,
        )
        new_clip_b.waveform = clip.waveform  # shared source
        new_clip_b.fades = [
            FadeSegment(f.start_ms, f.end_ms, getattr(f, "kind", "both"))
            for f in clip.fades
            if f.start_ms >= b_trim_start
        ]
        new_clip_b.cuts = [
            CutSegment(
                max(0, c.start_ms - sel_end),
                max(0, c.end_ms - sel_end),
            )
            for c in clip.cuts
            if c.start_ms >= sel_end
        ]

    if a_keeps:
        clip.trim_end_ms = a_trim_end
        clip.fade_out_ms = 0  # tail fade belongs to piece B now
        clip.fades = [
            f for f in clip.fades if f.end_ms <= a_trim_end
        ]
        clip.cuts = [
            c for c in clip.cuts if c.end_ms <= sel_start
        ]
        clip.selection_start_ms = -1
        clip.selection_end_ms = -1
    else:
        # Piece A collapsed - remove it from the track.
        try:
            track.clips.remove(clip)
        except ValueError:
            pass

    if new_clip_b is not None:
        track.clips.append(new_clip_b)
        # Keep clips sorted by offset so the render order is stable.
        track.clips.sort(key=lambda c: c.offset_ms)

    row = self._audio_rows.get(track.id)
    if row is not None:
        row.refresh_from_track()
    self._audio_mixer.update_track(track)
    self._refresh_player_tracks()


def _open_nested_sequence_for_edit(self, track, clip) -> None:
    """Expand a nested sequence parent back into child clips for editing."""
    nested_tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
    nested_audio_tracks = list(getattr(clip, "nested_audio_tracks", []) or [])
    nested_spine_tracks = list(getattr(clip, "nested_spine_actor_tracks", []) or [])
    nested_live2d_tracks = list(getattr(clip, "nested_live2d_actor_tracks", []) or [])
    if not nested_tracks and not nested_audio_tracks and not nested_spine_tracks and not nested_live2d_tracks:
        return
    parent_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
    expanded = []
    used_ids = {
        int(getattr(c, "id", 0) or 0)
        for c in getattr(track, "clips", []) or []
        if c is not clip
    }
    next_id = max(used_ids, default=0) + 1
    for child_track in nested_tracks:
        for child in child_track:
            restored = copy.deepcopy(child)
            if int(getattr(restored, "id", 0) or 0) in used_ids:
                restored.id = next_id
                next_id += 1
            used_ids.add(int(restored.id))
            restored.timeline_in_ms = parent_start + int(getattr(restored, "timeline_in_ms", 0))
            restored.compound_group_id = None
            restored.compound_group_name = ""
            expanded.append(restored)
    track.clips = [
        c for c in getattr(track, "clips", []) or []
        if c is not clip and int(getattr(c, "id", -1)) != int(getattr(clip, "id", -2))
    ] + expanded
    track.clips.sort(key=lambda c: int(c.timeline_in_ms))
    track.clips_explicit = True
    self._selected_clips = [(int(track.id), int(c.id)) for c in expanded]
    row = self._track_rows.get(track.id)
    if row is not None:
        row._recalc_width()
        row.update()

    for audio_lane in nested_audio_tracks:
        new_track = AudioTrack(id=self._next_track_id)
        self._next_track_id += 1
        for audio_clip in audio_lane:
            restored = copy.deepcopy(audio_clip)
            restored.id = self._next_clip_id()
            restored.offset_ms = parent_start + int(getattr(restored, "offset_ms", 0))
            new_track.clips.append(restored)
        if new_track.clips:
            self._audio_tracks.append(new_track)
            self._insert_audio_track_widget(new_track)
            self._audio_mixer.add_track(new_track)
            for restored in new_track.clips:
                self._start_waveform_extraction(restored)

    for actor_track in nested_spine_tracks:
        restored_track = copy.deepcopy(actor_track)
        restored_track.id = self._next_actor_id
        self._next_actor_id += 1
        for actor_clip in getattr(restored_track, "clips", []) or []:
            actor_clip.start_ms = parent_start + int(getattr(actor_clip, "start_ms", 0))
        self._spine_actor_tracks.append(restored_track)

    for actor_track in nested_live2d_tracks:
        restored_track = copy.deepcopy(actor_track)
        restored_track.id = self._next_live2d_id
        self._next_live2d_id += 1
        for actor_clip in getattr(restored_track, "clips", []) or []:
            actor_clip.start_ms = parent_start + int(getattr(actor_clip, "start_ms", 0))
        for blend in getattr(restored_track, "blends", []) or []:
            blend.center_ms = parent_start + int(getattr(blend, "center_ms", 0))
        self._live2d_actor_tracks.append(restored_track)

    if nested_spine_tracks:
        self._rebuild_spine_actor_lanes()
    if nested_live2d_tracks:
        self._rebuild_live2d_actor_lanes()
    self._broadcast_clip_selection()
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    self._register_change("open nested sequence")
    self._flash_status("Nested sequence opened on timeline")


def _ripple_delete_selected(self, *, change_label: str = "ripple delete") -> bool:
    """Delete every selected clip and ripple subsequent clips
    left to close the gap (DaVinci / Premiere "Shift+Delete")."""
    # Don't fire when the user's deleting characters in a text
    # field - Delete is the universal "remove next character"
    # binding and a global shortcut would steal it.
    if self._is_text_focus():
        return False
    # If a typography actor is selected, delete it first.
    if getattr(self, "_selected_typo", None) is not None:
        self._delete_selected_typo_actor()
        return True
    if not self._selected_clips:
        return False
    locked_tid = _selected_locked_video_track_id(self)
    if locked_tid is not None:
        self._flash_status(f"Delete blocked: track {locked_tid} is locked")
        return False
    from app.timeline_model import ripple_delete_clips

    # Group by track so we run one ripple per track.
    by_track: dict[int, set[int]] = {}
    for tid, cid in self._selected_clips:
        by_track.setdefault(tid, set()).add(cid)
    any_change = False
    tracks_to_delete: list[int] = []
    for tid, ids in by_track.items():
        track = self._find_track(tid)
        if track is None or not getattr(track, "clips", None):
            continue
        new_clips = ripple_delete_clips(track.clips, ids)
        if len(new_clips) != len(track.clips):
            any_change = True
            if not new_clips:
                # Last clip deleted - remove the entire track (CapCut style)
                tracks_to_delete.append(tid)
            else:
                track.clips = new_clips
                track.clips_explicit = True
                row = self._track_rows.get(tid)
                if row is not None:
                    row.set_selected_clip_ids(set())
                    row.update()
    # Delete empty tracks (must keep at least 1 video track)
    for tid in tracks_to_delete:
        if len(self._tracks) > 1:
            self._delete_track(tid)
        else:
            # Only one video track: clear clips + source_path so it
            # shows the "drag video here" empty-slot state, not black.
            track = self._find_track(tid)
            if track is not None:
                track.clips = []
                track.clips_explicit = True
                track.source_path = None
                track.duration_ms = 0
                row = self._track_rows.get(tid)
                if row is not None:
                    row.set_selected_clip_ids(set())
                    row._recalc_width()
                    row.update()
                self._update_tracks_host_width()
    self._selected_clips.clear()
    self._update_timeline_status()
    if any_change:
        self._refresh_player_tracks()
        self._register_change(change_label)
    return bool(any_change)


def _cleanup_timeline_micro_edges(self, track_id: int | None = None) -> int:
    """Clean one-frame-ish gaps/overlaps on video tracks.

    Uses lightweight proxy clips for the pure timeline helper so rich UI
    payloads such as cached thumbnails stay attached to the existing clips.
    """
    from app.timeline_model import cleanup_timeline_micro_edges

    VideoEditorWindow = _video_editor_window_cls()
    frame_ms = VideoEditorWindow._timeline_frame_ms(getattr(self, "_project_settings", None))
    tracks = []
    for track in getattr(self, "_tracks", []) or []:
        try:
            tid = int(getattr(track, "id"))
        except Exception:
            continue
        if track_id is not None and tid != int(track_id):
            continue
        tracks.append(track)

    changed_actions = 0
    skipped_locked = 0
    skipped_linked_audio = 0
    linked_audio_moves = 0
    changed_audio_tracks: set[int] = set()
    for track in tracks:
        if bool(getattr(track, "locked", False)):
            summary = VideoEditorWindow._timeline_edge_issue_summary(
                [track],
                getattr(self, "_project_settings", None),
            )
            if int(summary.get("auto_fixable_count", 0) or 0) > 0:
                skipped_locked += 1
            continue

        original_by_id = {
            int(getattr(clip, "id")): clip
            for clip in getattr(track, "clips", []) or []
            if getattr(clip, "id", None) is not None
        }
        proxies = VideoEditorWindow._timeline_edge_proxy_clips(original_by_id.values())
        cleaned, actions = cleanup_timeline_micro_edges(proxies, frame_ms=frame_ms)
        if not actions:
            continue

        original_start_by_id = {
            int(clip_id): int(getattr(clip, "timeline_in_ms", 0) or 0)
            for clip_id, clip in original_by_id.items()
        }
        timeline_deltas = {
            int(cleaned_clip.id): int(cleaned_clip.timeline_in_ms) - int(original_start_by_id[int(cleaned_clip.id)])
            for cleaned_clip in cleaned
            if int(cleaned_clip.id) in original_start_by_id
            and int(cleaned_clip.timeline_in_ms) != int(original_start_by_id[int(cleaned_clip.id)])
        }
        audio_plan = {}
        audio_block_reason = ""
        moved_audio_ids: set[int] = set()
        for clip_id, delta in timeline_deltas.items():
            original = original_by_id.get(int(clip_id))
            linked_id = getattr(original, "linked_audio_id", None) if original is not None else None
            if linked_id is None:
                continue
            try:
                linked_id = int(linked_id)
            except Exception:
                audio_block_reason = "linked audio is missing"
                break
            if linked_id in moved_audio_ids:
                audio_block_reason = "linked audio is shared"
                break
            matches = []
            for atrack in getattr(self, "_audio_tracks", []) or []:
                for aclip in getattr(atrack, "clips", []) or []:
                    if int(getattr(aclip, "id", -1)) == linked_id:
                        matches.append((atrack, aclip))
            if len(matches) != 1:
                audio_block_reason = "linked audio is missing" if not matches else "linked audio is duplicated"
                break
            atrack, aclip = matches[0]
            new_offset = int(getattr(aclip, "offset_ms", 0) or 0) + int(delta)
            if new_offset < 0:
                audio_block_reason = "linked audio would move before start"
                break
            audio_key = (int(getattr(atrack, "id", -1)), int(linked_id))
            audio_plan[audio_key] = (atrack, aclip, new_offset)
            moved_audio_ids.add(int(linked_id))

        if not audio_block_reason and audio_plan:
            moving_by_track: dict[int, set[int]] = {}
            for (audio_track_id, audio_clip_id), _payload in audio_plan.items():
                moving_by_track.setdefault(int(audio_track_id), set()).add(int(audio_clip_id))
            for (audio_track_id, audio_clip_id), (_atrack, aclip, new_offset) in audio_plan.items():
                a_len = int(getattr(aclip, "effective_length_ms", 0) or 0)
                new_end = int(new_offset) + max(0, a_len)
                for other in getattr(_atrack, "clips", []) or []:
                    other_id = int(getattr(other, "id", -1))
                    if other_id in moving_by_track.get(int(audio_track_id), set()):
                        continue
                    other_start = int(getattr(other, "offset_ms", 0) or 0)
                    other_end = other_start + int(getattr(other, "effective_length_ms", 0) or 0)
                    if not (new_end <= other_start or other_end <= int(new_offset)):
                        audio_block_reason = "linked audio would overlap another clip"
                        break
                if audio_block_reason:
                    break

        if audio_block_reason:
            skipped_linked_audio += 1
            continue

        for cleaned_clip in cleaned:
            original = original_by_id.get(int(cleaned_clip.id))
            if original is None:
                continue
            original.timeline_in_ms = int(cleaned_clip.timeline_in_ms)
            original.source_in_ms = int(cleaned_clip.source_in_ms)
            original.source_out_ms = int(cleaned_clip.source_out_ms)
        for (audio_track_id, _audio_clip_id), (_atrack, aclip, new_offset) in audio_plan.items():
            aclip.offset_ms = int(new_offset)
            changed_audio_tracks.add(int(audio_track_id))
            linked_audio_moves += 1
        track.clips.sort(key=lambda c: int(getattr(c, "timeline_in_ms", 0) or 0))
        track.clips_explicit = True
        if len(getattr(track, "clips", []) or []) == 1:
            track.offset_ms = int(getattr(track.clips[0], "timeline_in_ms", 0) or 0)
        row = getattr(self, "_track_rows", {}).get(int(getattr(track, "id", -1)))
        if row is not None:
            if hasattr(row, "_recalc_width"):
                row._recalc_width()
            row.update()
        changed_actions += len(actions)

    flash = getattr(self, "_flash_status", None)
    if changed_actions <= 0:
        if skipped_locked:
            if callable(flash):
                flash("Timeline cleanup blocked: selected track is locked")
        elif skipped_linked_audio:
            if callable(flash):
                flash("Timeline cleanup blocked: linked audio would overlap or is missing")
        elif callable(flash):
            flash("No 1-frame timeline gaps/overlaps to clean")
        return 0

    for audio_track_id in changed_audio_tracks:
        atrack = next(
            (
                t for t in getattr(self, "_audio_tracks", []) or []
                if int(getattr(t, "id", -1)) == int(audio_track_id)
            ),
            None,
        )
        if atrack is None:
            continue
        atrack.clips.sort(key=lambda c: int(getattr(c, "offset_ms", 0) or 0))
        row = getattr(self, "_audio_rows", {}).get(int(audio_track_id))
        if row is not None:
            row.update()
        try:
            getattr(self, "_audio_mixer").update_track(atrack)
        except Exception:
            pass
    refresh = getattr(self, "_refresh_player_tracks", None)
    if callable(refresh):
        refresh()
    update_width = getattr(self, "_update_tracks_host_width", None)
    if callable(update_width):
        update_width()
    update_status = getattr(self, "_update_timeline_status", None)
    if callable(update_status):
        update_status()
    register = getattr(self, "_register_change", None)
    if callable(register):
        register("timeline micro-edge cleanup")
    if callable(flash):
        suffix_parts = []
        if linked_audio_moves:
            suffix_parts.append(f"linked audio {linked_audio_moves}")
        if skipped_locked:
            suffix_parts.append(f"skipped {skipped_locked} locked track(s)")
        if skipped_linked_audio:
            suffix_parts.append(f"skipped {skipped_linked_audio} linked-audio conflict(s)")
        suffix = f"; {'; '.join(suffix_parts)}" if suffix_parts else ""
        flash(f"Cleaned {changed_actions} timeline micro edge(s){suffix}")
    return changed_actions


def _create_nested_group_from_selection(self) -> None:
    if len(self._selected_clips) < 2:
        self._flash_status("Select at least two clips to nest")
        return
    self._refresh_nested_group_counter()
    gid = int(self._next_nested_group_id)
    self._next_nested_group_id += 1
    name = f"Nested {gid}"

    selected_by_track: dict[int, set[int]] = {}
    for tid, cid in self._selected_clips:
        selected_by_track.setdefault(int(tid), set()).add(int(cid))
    selected_tracks = [
        track for track in self._tracks
        if int(getattr(track, "id", -1)) in selected_by_track
    ]
    selected_pairs: list[tuple[object, object]] = []
    for track in selected_tracks:
        ids = selected_by_track.get(int(track.id), set())
        for clip in getattr(track, "clips", []) or []:
            if int(getattr(clip, "id", -1)) in ids:
                selected_pairs.append((track, clip))
    if len(selected_pairs) < 2:
        self._flash_status("Select at least two clips to nest")
        return

    base_ms = min(int(c.timeline_in_ms) for _t, c in selected_pairs)
    end_ms = max(int(c.timeline_out_ms) for _t, c in selected_pairs)
    duration_ms = max(0, end_ms - base_ms)
    target_track = self._find_track(self._active_track_id) if self._active_track_id is not None else None
    if target_track is None or int(target_track.id) not in selected_by_track:
        target_track = selected_tracks[-1] if selected_tracks else selected_pairs[0][0]

    nested_tracks: list[list] = []
    for track in selected_tracks:
        ids = selected_by_track.get(int(track.id), set())
        child_track = []
        for clip in sorted(getattr(track, "clips", []) or [], key=lambda c: int(c.timeline_in_ms)):
            if int(getattr(clip, "id", -1)) not in ids:
                continue
            child = copy.deepcopy(clip)
            child.timeline_in_ms = int(child.timeline_in_ms) - base_ms
            child.compound_group_id = None
            child.compound_group_name = ""
            child_track.append(child)
        if child_track:
            nested_tracks.append(child_track)

    existing_ids = [
        int(getattr(c, "id", 0) or 0)
        for c in getattr(target_track, "clips", []) or []
    ]
    parent_id = max(existing_ids, default=0) + 1
    parent = VideoClip(
        id=parent_id,
        source_path=None,
        source_duration_ms=duration_ms,
        timeline_in_ms=base_ms,
        source_in_ms=0,
        source_out_ms=duration_ms,
        nested_sequence_id=gid,
        nested_sequence_name=name,
        nested_child_clips=list(nested_tracks[0]) if nested_tracks else [],
        nested_child_tracks=nested_tracks,
        compound_group_id=gid,
        compound_group_name=name,
    )

    for tid, ids in selected_by_track.items():
        track = self._find_track(tid)
        if track is None:
            continue
        track.clips = [
            c for c in getattr(track, "clips", []) or []
            if int(getattr(c, "id", -1)) not in ids
        ]
        if int(track.id) == int(target_track.id):
            track.clips.append(parent)
        track.clips.sort(key=lambda c: int(c.timeline_in_ms))
        track.clips_explicit = True
        row = self._track_rows.get(track.id)
        if row is not None:
            row._recalc_width()
            row.update()

    self._selected_clips = [(int(target_track.id), int(parent.id))]
    self._broadcast_clip_selection()
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    self._register_change("nested sequence")
    self._flash_status(f"Created {name}")


def _paste_timeline_clipboard(self, at_ms: int | None = None) -> int:
    flash = getattr(self, "_flash_status", None)
    clipboard = getattr(self, "_timeline_clipboard", None) or {}
    records = list(clipboard.get("records", []) or [])
    if clipboard.get("kind") != "video_clips" or not records:
        if callable(flash):
            flash("No timeline clips copied")
        return 0

    tracks_by_id = {
        int(getattr(track, "id", -1)): track
        for track in getattr(self, "_tracks", []) or []
    }
    target_track_ids = {
        int(record.get("track_id", -1))
        for record in records
        if int(record.get("track_id", -1)) in tracks_by_id
    }
    if not target_track_ids:
        if callable(flash):
            flash("Paste blocked: target tracks are missing")
        return 0
    for tid in target_track_ids:
        if bool(getattr(tracks_by_id[tid], "locked", False)):
            if callable(flash):
                flash(f"Paste blocked: track {tid} is locked")
            return 0

    if at_ms is None:
        player = getattr(self, "_player", None)
        at_ms = int(player.position()) if player is not None and hasattr(player, "position") else 0
    VideoEditorWindow = _video_editor_window_cls()
    paste_base = _timeline_paste_group_base_ms(
        records,
        tracks_by_id,
        int(at_ms),
    )

    new_selection: list[tuple[int, int]] = []
    pasted_count = 0
    for record in records:
        tid = int(record.get("track_id", -1))
        track = tracks_by_id.get(tid)
        if track is None:
            continue
        src_clip = record.get("clip")
        if src_clip is None:
            continue
        dup = copy.deepcopy(src_clip)
        dup.id = self._next_clip_id()
        dup.timeline_in_ms = paste_base + int(record.get("rel_start_ms", 0) or 0)
        _prepare_pasted_timeline_clip(dup)
        getattr(track, "clips").append(dup)
        new_selection.append((tid, int(dup.id)))
        pasted_count += 1

    if not pasted_count:
        if callable(flash):
            flash("Paste blocked: target tracks are missing")
        return 0

    for tid in target_track_ids:
        track = tracks_by_id.get(tid)
        if track is None:
            continue
        track.clips.sort(key=lambda c: int(getattr(c, "timeline_in_ms", 0) or 0))
        track.clips_explicit = True
        row = getattr(self, "_track_rows", {}).get(tid)
        if row is not None:
            recalc = getattr(row, "_recalc_width", None)
            if callable(recalc):
                recalc()
            row.update()

    self._selected_clips = new_selection
    broadcast = getattr(self, "_broadcast_clip_selection", None)
    if callable(broadcast):
        broadcast()
    refresh = getattr(self, "_refresh_player_tracks", None)
    if callable(refresh):
        refresh()
    update_width = getattr(self, "_update_tracks_host_width", None)
    if callable(update_width):
        update_width()
    register = getattr(self, "_register_change", None)
    if callable(register):
        register("paste clips")
    if callable(flash):
        flash(f"Pasted {pasted_count} timeline clips")
    return pasted_count


def _duplicate_selected_timeline_clips(self) -> int:
    selected_pairs = list(getattr(self, "_selected_clips", []) or [])
    flash = getattr(self, "_flash_status", None)
    if not selected_pairs:
        if callable(flash):
            flash("Select clips to duplicate")
        return 0

    selected_by_track: dict[int, set[int]] = {}
    for tid, cid in selected_pairs:
        selected_by_track.setdefault(int(tid), set()).add(int(cid))

    tracks = list(getattr(self, "_tracks", []) or [])
    for track in tracks:
        tid = int(getattr(track, "id", -1))
        if tid in selected_by_track and bool(getattr(track, "locked", False)):
            if callable(flash):
                flash(f"Duplicate blocked: track {tid} is locked")
            return 0

    VideoEditorWindow = _video_editor_window_cls()
    new_selection: list[tuple[int, int]] = []
    duplicated_count = 0
    for track in tracks:
        tid = int(getattr(track, "id", -1))
        selected_ids = selected_by_track.get(tid)
        if not selected_ids:
            continue
        clips = list(getattr(track, "clips", []) or [])
        selected_clips = [
            clip for clip in clips
            if int(getattr(clip, "id", -1)) in selected_ids
        ]
        selected_clips.sort(key=lambda c: int(getattr(c, "timeline_in_ms", 0) or 0))
        if not selected_clips:
            continue
        group_start = min(int(getattr(c, "timeline_in_ms", 0) or 0) for c in selected_clips)
        group_end = max(
            int(getattr(c, "timeline_out_ms", getattr(c, "timeline_in_ms", 0)) or 0)
            for c in selected_clips
        )
        duplicate_start = _timeline_duplicate_group_start_ms(
            selected_clips,
            clips,
            set(selected_ids),
            group_end,
        )
        for clip in selected_clips:
            dup = copy.deepcopy(clip)
            dup.id = self._next_clip_id()
            dup.timeline_in_ms = duplicate_start + (
                int(getattr(clip, "timeline_in_ms", 0) or 0) - group_start
            )
            if hasattr(dup, "linked_audio_id"):
                dup.linked_audio_id = None
            if hasattr(dup, "compound_group_id"):
                dup.compound_group_id = None
            if hasattr(dup, "compound_group_name"):
                dup.compound_group_name = ""
            _prepare_pasted_timeline_clip(dup)
            getattr(track, "clips").append(dup)
            new_selection.append((tid, int(dup.id)))
            duplicated_count += 1
        track.clips.sort(key=lambda c: int(getattr(c, "timeline_in_ms", 0) or 0))
        track.clips_explicit = True
        row = getattr(self, "_track_rows", {}).get(tid)
        if row is not None:
            recalc = getattr(row, "_recalc_width", None)
            if callable(recalc):
                recalc()
            row.update()

    if not duplicated_count:
        if callable(flash):
            flash("No selected clips to duplicate")
        return 0

    self._selected_clips = new_selection
    broadcast = getattr(self, "_broadcast_clip_selection", None)
    if callable(broadcast):
        broadcast()
    refresh = getattr(self, "_refresh_player_tracks", None)
    if callable(refresh):
        refresh()
    update_width = getattr(self, "_update_tracks_host_width", None)
    if callable(update_width):
        update_width()
    register = getattr(self, "_register_change", None)
    if callable(register):
        register("duplicate clips")
    if callable(flash):
        flash(f"Duplicated {duplicated_count} timeline clips")
    return duplicated_count


def _nudge_selected_clips(self, delta_ms: int) -> None:
    if self._is_text_focus():
        return
    if not self._selected_clips:
        self._flash_status("Select clips to nudge")
        return
    from app.timeline_model import plan_linked_timeline_move

    plan = plan_linked_timeline_move(
        self._tracks,
        self._audio_tracks,
        self._selected_clips,
        int(delta_ms),
        strict_selection=True,
    )
    VideoEditorWindow = _video_editor_window_cls()
    if not plan.ok:
        self._flash_status(VideoEditorWindow._linked_move_block_message(self, "Nudge", plan))
        return
    if not plan.video_starts and not plan.audio_offsets:
        return

    changed_video_tracks: set[int] = set()
    changed_audio_tracks: set[int] = set()
    for (track_id, clip_id), new in plan.video_starts.items():
        track = self._find_track(track_id)
        if track is None:
            continue
        clip = next(
            (
                c for c in getattr(track, "clips", []) or []
                if int(getattr(c, "id", -1)) == int(clip_id)
            ),
            None,
        )
        if clip is None:
            continue
        clip.timeline_in_ms = int(new)
        if len(getattr(track, "clips", []) or []) <= 1:
            track.offset_ms = int(clip.timeline_in_ms)
        changed_video_tracks.add(int(track.id))

    for (track_id, clip_id), new in plan.audio_offsets.items():
        atrack = next(
            (
                t for t in getattr(self, "_audio_tracks", []) or []
                if int(getattr(t, "id", -1)) == int(track_id)
            ),
            None,
        )
        if atrack is None:
            continue
        aclip = next(
            (
                c for c in getattr(atrack, "clips", []) or []
                if int(getattr(c, "id", -1)) == int(clip_id)
            ),
            None,
        )
        if aclip is None:
            continue
        aclip.offset_ms = int(new)
        changed_audio_tracks.add(int(atrack.id))

    for track_id in changed_video_tracks:
        track = self._find_track(track_id)
        if track is None:
            continue
        track.clips.sort(key=lambda c: int(c.timeline_in_ms))
        row = self._track_rows.get(int(track.id))
        if row is not None:
            row._recalc_width()
            row.update()
    for track_id in changed_audio_tracks:
        atrack = next(
            (
                t for t in getattr(self, "_audio_tracks", []) or []
                if int(getattr(t, "id", -1)) == int(track_id)
            ),
            None,
        )
        if atrack is None:
            continue
        atrack.clips.sort(key=lambda c: int(getattr(c, "offset_ms", 0)))
        row = self._audio_rows.get(int(track_id))
        if row is not None:
            row.update()
        try:
            self._audio_mixer.update_track(atrack)
        except Exception:
            pass
    self._refresh_player_tracks()
    self._update_tracks_host_width()
    self._update_timeline_status()
    self._register_change("clip nudge")
    self._flash_status(
        VideoEditorWindow._format_nudge_status(
            int(delta_ms),
            len(plan.video_starts),
            len(plan.audio_offsets),
            getattr(self, "_project_settings", {}) or {},
        )
    )


def _clip_audition_range(self) -> tuple[int, int, int] | None:
        player = getattr(self, "_player", None)
        if player is None:
            return None
        try:
            current = int(player.position())
        except Exception:
            current = 0

        def _clip_bounds(clip) -> tuple[int, int] | None:
            try:
                start = int(getattr(clip, "timeline_in_ms", 0) or 0)
                end = int(getattr(clip, "timeline_out_ms", start) or start)
            except Exception:
                return None
            if end <= start:
                try:
                    end = start + int(getattr(clip, "effective_length_ms", 0) or 0)
                except Exception:
                    end = start
            if end <= start:
                return None
            return start, end

        def _is_video_clip(clip) -> bool:
            return (
                getattr(clip, "source_path", None) is not None
                or bool(getattr(clip, "is_nested_sequence", False))
            )

        for track_id, clip_id in list(getattr(self, "_selected_clips", []) or []):
            track = self._find_track(track_id)
            if track is None:
                continue
            for clip in list(getattr(track, "clips", []) or []):
                if int(getattr(clip, "id", -1)) != int(clip_id):
                    continue
                if not _is_video_clip(clip):
                    continue
                bounds = _clip_bounds(clip)
                if bounds is None:
                    continue
                start, end = bounds
                play_start = current if start <= current < end else start
                return play_start, end, current

        for track in reversed(list(getattr(self, "_tracks", []) or [])):
            if bool(getattr(track, "pip_enabled", False)):
                continue
            for clip in list(getattr(track, "clips", []) or []):
                if not _is_video_clip(clip):
                    continue
                bounds = _clip_bounds(clip)
                if bounds is None:
                    continue
                start, end = bounds
                if start <= current < end:
                    return current, end, current
        return None


def _open_precision_trim_dialog(self) -> None:
        track, clip = self._selected_video_clip()
        if track is None or clip is None:
            self._flash_status("Select one clip first")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Precision Trim")
        lay = QVBoxLayout(dlg)
        grid = QGridLayout()
        lay.addLayout(grid)

        timeline_in = QSpinBox()
        timeline_in.setRange(0, 24 * 60 * 60 * 1000)
        timeline_in.setValue(int(clip.timeline_in_ms))
        source_in = QSpinBox()
        source_in.setRange(0, max(0, int(clip.source_duration_ms)))
        source_in.setValue(int(clip.source_in_ms))
        source_out = QSpinBox()
        source_out.setRange(0, max(0, int(clip.source_duration_ms)))
        source_out.setValue(int(clip.effective_source_out_ms))
        for row, (label, spin) in enumerate((
            ("Timeline start ms", timeline_in),
            ("Source in ms", source_in),
            ("Source out ms", source_out),
        )):
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(spin, row, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_source_in = int(source_in.value())
        new_source_out = int(source_out.value())
        if new_source_out <= new_source_in + TrackRow.CLIP_MIN_DURATION_MS:
            new_source_out = new_source_in + TrackRow.CLIP_MIN_DURATION_MS
        if clip.source_duration_ms > 0:
            new_source_out = min(new_source_out, int(clip.source_duration_ms))
            new_source_in = min(new_source_in, new_source_out - TrackRow.CLIP_MIN_DURATION_MS)
            new_source_in = max(0, new_source_in)
        try:
            from app.actions.editor_adapter import EditorAdapter

            EditorAdapter(self).precision_trim_clip(
                track_id=int(track.id),
                clip_id=int(clip.id),
                timeline_in_ms=int(timeline_in.value()),
                source_in_ms=int(new_source_in),
                source_out_ms=int(new_source_out),
            )
        except Exception as exc:
            self._flash_status(f"Precision trim failed: {exc}")


# Extracted VideoEditorWindow timeline selection/clipboard helpers.
@staticmethod
def _timeline_edit_points_ms(
    video_tracks=None,
    audio_tracks=None,
    markers=None,
    spine_tracks=None,
    live2d_tracks=None,
) -> list[int]:
    points: set[int] = {0}

    def _add(value) -> None:
        try:
            ms = int(round(float(value)))
        except Exception:
            return
        if ms >= 0:
            points.add(ms)

    for track in video_tracks or []:
        for clip in getattr(track, "clips", []) or []:
            _add(getattr(clip, "timeline_in_ms", 0))
            _add(getattr(clip, "timeline_out_ms", 0))

    for track in audio_tracks or []:
        for clip in getattr(track, "clips", []) or []:
            start = int(getattr(clip, "offset_ms", 0) or 0)
            length = int(
                getattr(clip, "effective_length_ms", 0)
                or getattr(clip, "duration_ms", 0)
                or 0
            )
            _add(start)
            _add(start + max(0, length))

    for marker in markers or []:
        if isinstance(marker, dict):
            _add(marker.get("ms", 0))
        else:
            _add(getattr(marker, "ms", 0))

    for tracks in (spine_tracks or [], live2d_tracks or []):
        for track in tracks or []:
            for clip in getattr(track, "clips", []) or []:
                start = getattr(clip, "start_ms", None)
                end = getattr(clip, "end_ms", None)
                if end is None:
                    try:
                        end = int(start or 0) + int(getattr(clip, "duration_ms", 0) or 0)
                    except Exception:
                        end = None
                _add(start)
                _add(end)

    return sorted(points)


def _jump_to_timeline_edit_point(self, direction: int) -> None:
    points = VideoEditorWindow._timeline_edit_points_ms(
        getattr(self, "_tracks", []),
        getattr(self, "_audio_tracks", []),
        getattr(self, "_timeline_markers", []),
        getattr(self, "_spine_actor_tracks", []),
        getattr(self, "_live2d_actor_tracks", []),
    )
    current = self._player.position() if hasattr(self, "_player") else 0
    target = VideoEditorWindow._timeline_neighbor_edit_point(
        points,
        int(current),
        int(direction),
    )
    if target is None:
        self._flash_status(
            "No previous edit point" if int(direction) < 0 else "No next edit point"
        )
        return
    self._player.set_position(int(target))
    self._ensure_playhead_visible()
    self._flash_status(
        f"{'Previous' if int(direction) < 0 else 'Next'} edit: {_format_ms(int(target))}"
    )


def _clear_timeline_clip_selection(self) -> bool:
    selected = getattr(self, "_selected_clips", None)
    if not selected:
        return False
    selected.clear()
    broadcast = getattr(self, "_broadcast_clip_selection", None)
    if callable(broadcast):
        broadcast()
    return True


def _select_all_timeline_clips(self) -> int:
    selected: list[tuple[int, int]] = []
    for track in getattr(self, "_tracks", []) or []:
        tid = getattr(track, "id", None)
        if tid is None:
            continue
        for clip in getattr(track, "clips", []) or []:
            cid = getattr(clip, "id", None)
            if cid is None:
                continue
            selected.append((int(tid), int(cid)))

    self._selected_clips = selected
    broadcast = getattr(self, "_broadcast_clip_selection", None)
    if callable(broadcast):
        broadcast()

    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        if selected:
            flash(f"Selected {len(selected)} timeline clips")
        else:
            flash("No timeline clips to select")
    return len(selected)


@staticmethod
def _timeline_duplicate_group_start_ms(
    selected_clips: list,
    all_clips: list,
    selected_ids: set[int],
    desired_start_ms: int,
) -> int:
    if not selected_clips:
        return max(0, int(desired_start_ms))
    group_start = min(int(getattr(c, "timeline_in_ms", 0) or 0) for c in selected_clips)
    candidate = max(0, int(desired_start_ms))

    def _overlap_end(start_ms: int) -> int | None:
        for clip in selected_clips:
            src_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
            src_end = int(getattr(clip, "timeline_out_ms", src_start) or src_start)
            offset = src_start - group_start
            new_in = start_ms + offset
            new_out = new_in + max(0, src_end - src_start)
            for other in all_clips:
                try:
                    if int(getattr(other, "id", -1)) in selected_ids:
                        continue
                except Exception:
                    pass
                other_start = int(getattr(other, "timeline_in_ms", 0) or 0)
                other_end = int(getattr(other, "timeline_out_ms", other_start) or other_start)
                if not (other_end <= new_in or new_out <= other_start):
                    return other_end
        return None

    for _ in range(max(1, len(all_clips) + len(selected_clips) + 8)):
        blocking_end = _overlap_end(candidate)
        if blocking_end is None:
            return candidate
        candidate = max(candidate + 1, int(blocking_end))
    return candidate


@staticmethod
def _timeline_paste_group_base_ms(
    records: list[dict],
    tracks_by_id: dict[int, object],
    desired_base_ms: int,
) -> int:
    candidate = max(0, int(desired_base_ms))
    if not records:
        return candidate

    def _duration(record: dict) -> int:
        clip = record.get("clip")
        start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        end = int(getattr(clip, "timeline_out_ms", start) or start)
        return max(0, end - start)

    def _next_unblocked_base(base_ms: int) -> int | None:
        for record in records:
            tid = int(record.get("track_id", -1))
            track = tracks_by_id.get(tid)
            if track is None:
                continue
            rel_start = int(record.get("rel_start_ms", 0) or 0)
            new_in = int(base_ms) + rel_start
            new_out = new_in + _duration(record)
            for other in getattr(track, "clips", []) or []:
                other_start = int(getattr(other, "timeline_in_ms", 0) or 0)
                other_end = int(getattr(other, "timeline_out_ms", other_start) or other_start)
                if not (other_end <= new_in or new_out <= other_start):
                    return max(int(base_ms) + 1, other_end - rel_start)
        return None

    clip_count = sum(len(getattr(t, "clips", []) or []) for t in tracks_by_id.values())
    for _ in range(max(1, clip_count + len(records) + 12)):
        next_base = _next_unblocked_base(candidate)
        if next_base is None:
            return candidate
        candidate = max(candidate + 1, int(next_base))
    return candidate


@staticmethod
def _prepare_pasted_timeline_clip(clip) -> None:
    if hasattr(clip, "linked_audio_id"):
        clip.linked_audio_id = None
    if hasattr(clip, "compound_group_id"):
        clip.compound_group_id = None
    if hasattr(clip, "compound_group_name"):
        clip.compound_group_name = ""
    if hasattr(clip, "thumbnails"):
        clip.thumbnails = []


def _copy_selected_timeline_clips(self, *, show_status: bool = True) -> int:
    selected_pairs = list(getattr(self, "_selected_clips", []) or [])
    flash = getattr(self, "_flash_status", None)
    if not selected_pairs:
        if show_status and callable(flash):
            flash("Select clips to copy")
        return 0

    selected_by_track: dict[int, set[int]] = {}
    for tid, cid in selected_pairs:
        selected_by_track.setdefault(int(tid), set()).add(int(cid))

    import copy

    source_items: list[tuple[int, object]] = []
    for track in getattr(self, "_tracks", []) or []:
        tid = int(getattr(track, "id", -1))
        ids = selected_by_track.get(tid)
        if not ids:
            continue
        clips = [
            clip for clip in getattr(track, "clips", []) or []
            if int(getattr(clip, "id", -1)) in ids
        ]
        clips.sort(key=lambda c: int(getattr(c, "timeline_in_ms", 0) or 0))
        source_items.extend((tid, clip) for clip in clips)

    if not source_items:
        if show_status and callable(flash):
            flash("No selected clips to copy")
        return 0

    group_start = min(
        int(getattr(clip, "timeline_in_ms", 0) or 0)
        for _tid, clip in source_items
    )
    records: list[dict] = []
    for tid, clip in source_items:
        copied = copy.deepcopy(clip)
        if hasattr(copied, "thumbnails"):
            copied.thumbnails = []
        records.append({
            "track_id": int(tid),
            "rel_start_ms": int(getattr(clip, "timeline_in_ms", 0) or 0) - group_start,
            "clip": copied,
        })
    self._timeline_clipboard = {"kind": "video_clips", "records": records}
    if show_status and callable(flash):
        flash(f"Copied {len(records)} timeline clips")
    return len(records)


def _cut_selected_timeline_clips(self) -> int:
    selected_pairs = list(getattr(self, "_selected_clips", []) or [])
    flash = getattr(self, "_flash_status", None)
    if not selected_pairs:
        if callable(flash):
            flash("Select clips to cut")
        return 0
    locked_tid = _selected_locked_video_track_id(
        self,
        selected_pairs,
    )
    if locked_tid is not None:
        if callable(flash):
            flash(f"Cut blocked: track {locked_tid} is locked")
        return 0
    copied = _copy_selected_timeline_clips(
        self,
        show_status=False,
    )
    if copied <= 0:
        if callable(flash):
            flash("No selected clips to cut")
        return 0
    if not _ripple_delete_selected(
        self,
        change_label="cut clips",
    ):
        return 0
    if callable(flash):
        flash(f"Cut {copied} timeline clips")
    return copied

# Timeline edit command helpers moved out of VideoEditorWindow.
def _set_selection_end_at_playhead(self, in_point: bool) -> None:
    project_ms = self._player.position()
    candidates = self._candidate_tracks_at(project_ms)
    if not candidates:
        return
    changed = False
    for entry in candidates:
        kind = entry[0]
        if kind == "audio":
            _, track, clip = entry
            local = max(0, project_ms - clip.offset_ms)
            local = min(local, max(0, clip.effective_length_ms))
            if in_point:
                clip.selection_start_ms = local
                if clip.selection_end_ms < local:
                    clip.selection_end_ms = local
            else:
                clip.selection_end_ms = local
                if (
                    clip.selection_start_ms < 0
                    or clip.selection_start_ms > local
                ):
                    clip.selection_start_ms = local
            row = self._audio_rows.get(track.id)
            if row is not None:
                row.update()
        else:
            _, track = entry
            local = max(0, project_ms - getattr(track, "offset_ms", 0))
            local = min(local, max(0, track.duration_ms))
            if in_point:
                track.selection_start_ms = local
                if track.selection_end_ms < local:
                    track.selection_end_ms = local
            else:
                track.selection_end_ms = local
                if (
                    track.selection_start_ms < 0
                    or track.selection_start_ms > local
                ):
                    track.selection_start_ms = local
            row = self._track_rows.get(track.id)
            if row is not None:
                row.flash_timeline_burst("cut", int(project_ms))
                row.update()
        changed = True
    if changed:
        self._refresh_selection_row()


def _clear_clip_transition(self, track, clip, *, register: bool = True) -> bool:
    if track is None or clip is None:
        return False
    if not str(getattr(clip, "transition_out_type", "") or ""):
        return False
    clip.transition_out_type = ""
    clip.transition_out_ms = 0
    clip.transition_preset_meta = {}
    row = getattr(self, "_track_rows", {}).get(getattr(track, "id", None))
    if row is not None:
        row.update()
    self._refresh_player_tracks()
    self._refresh_preview_soft(track)
    self._refresh_workbench()
    if register:
        self._register_change("clear clip transition")
    self._flash_status("Cleared clip transition")
    return True


def _toggle_audio_link(self, track, clip) -> None:
    """Link or unlink the video clip to the nearest audio clip at the
    same timeline position. If already linked, clears ``linked_audio_id``."""
    if getattr(clip, "linked_audio_id", None) is not None:
        clip.linked_audio_id = None
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()
        return
    # Find the nearest audio clip whose offset_ms is closest to clip.timeline_in_ms.
    best_clip = None
    best_dist = None
    for atrack in self._audio_tracks:
        for aclip in atrack.clips:
            dist = abs(int(aclip.offset_ms) - int(clip.timeline_in_ms))
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_clip = aclip
    if best_clip is not None:
        clip.linked_audio_id = best_clip.id
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()


def _cut_selection_in_track(self, track_id: int) -> None:
    """Phase 1.5d Step C: cut becomes a real clip-list mutation.

    The selection is in *track-local source ms*; we map it to
    *project ms* via the FIRST clip whose source range covers the
    selection start (the user always selects within the visible
    clip body so this is unambiguous), then walk ``track.clips``
    and split / drop pieces that overlap the cut window. The
    legacy ``track.cuts`` list is still updated so the existing
    ffmpeg export path keeps working until video_exporter migrates
    to ``track.clips``.
    """
    track = self._find_track(track_id)
    if track is None:
        return
    s, e = track.selection_start_ms, track.selection_end_ms
    if s < 0 or e <= s:
        return

    # --- 1. Update the legacy cuts list (export path / migration) ---
    merged: list[CutSegment] = []
    new_start, new_end = s, e
    for c in track.cuts:
        overlaps = not (c.end_ms <= new_start or new_end <= c.start_ms)
        if overlaps:
            new_start = min(new_start, c.start_ms)
            new_end = max(new_end, c.end_ms)
        else:
            merged.append(c)
    track.speed_segments = [
        seg
        for seg in track.speed_segments
        if not seg.overlaps(new_start, new_end)
    ]
    merged.append(CutSegment(new_start, new_end))
    merged.sort(key=lambda c: c.start_ms)
    track.cuts = merged

    # --- 2. Mutate clips so the cut becomes two independent halves ---
    track.clips = cut_clip_window(
        track.clips, s, e, track_offset_ms=int(getattr(track, "offset_ms", 0) or 0),
    )
    track.clips_explicit = True

    track.selection_start_ms = -1
    track.selection_end_ms = -1
    self._refresh_player_tracks()
    row = self._track_rows.get(track_id)
    if row is not None:
        row.update()
    self._refresh_selection_row()
    self._register_change("cut")


def _apply_speed_to_selection(self, speed: float) -> None:
    track = self._active_track()
    if track is None:
        return
    s, e = track.selection_start_ms, track.selection_end_ms
    if s < 0 or e <= s:
        return

    kept = [seg for seg in track.speed_segments if not seg.overlaps(s, e)]
    # Split existing segments that straddle the boundaries
    for seg in track.speed_segments:
        if seg.overlaps(s, e):
            if seg.start_ms < s:
                kept.append(SpeedSegment(seg.start_ms, s, seg.speed))
            if seg.end_ms > e:
                kept.append(SpeedSegment(e, seg.end_ms, seg.speed))
    kept.append(SpeedSegment(s, e, speed))
    kept.sort(key=lambda seg: seg.start_ms)
    track.speed_segments = kept

    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()

    if track.id == self._active_track_id:
        pos = self._player.position()
        if s <= pos < e:
            self._current_segment_speed = speed
            self._player.set_speed(speed)
            self._set_transport_speed_label(speed)


def _track_has_blade_target(track, project_ms: int) -> bool:
    try:
        ms = int(project_ms)
    except Exception:
        ms = 0
    for clip in getattr(track, "clips", []) or []:
        start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        end = int(getattr(clip, "timeline_out_ms", start) or start)
        if start < ms < end:
            return True
    return False


def _blade_at_playhead(self, track_id: int | None = None) -> None:
    """DaVinci / Premiere style blade ??splits whichever video
    clips contain the playhead, across *every* video track. No-op
    when the playhead lands on a boundary or sits in a gap on
    every track. Shows a user-visible hint instead of failing
    silently when nothing splittable is under the playhead."""
    if self._is_text_focus():
        return
    if not self._tracks:
        self._flash_status(tr("veditor.blade.flash.no_tracks"))
        return
    from app.timeline_model import split_clips_at_project_ms
    playhead_ms = self._player.position()
    any_cut = False
    locked_blocked = False
    for track in self._tracks:
        clips = getattr(track, "clips", None)
        if not clips:
            continue
        if bool(getattr(track, "locked", False)):
            if _track_has_blade_target(track, playhead_ms):
                locked_blocked = True
            continue
        before = len(clips)
        track.clips = split_clips_at_project_ms(clips, playhead_ms)
        track.clips_explicit = True
        if len(track.clips) != before:
            any_cut = True
            row = self._track_rows.get(track.id)
            if row is not None:
                row.flash_timeline_burst("cut", int(project_ms))
                row.update()
    if not any_cut:
        if locked_blocked:
            self._flash_status("Blade blocked: locked track")
            return
        self._flash_status(tr("veditor.blade.flash.no_clip"))
        return
    self._refresh_player_tracks()
    self._register_change("blade")
    btn = getattr(self, "blade_btn", None)
    if btn is not None:
        self._pulse_icon_button(btn, base=18, peak=26, duration=230)
    if locked_blocked:
        self._flash_status("Blade skipped locked tracks")
    else:
        self._flash_status("Blade cut")


def _blade_track_at_ms(self, track_id: int, project_ms: int) -> None:
    if self._is_text_focus():
        return
    track = self._find_track(track_id)
    if track is None or not getattr(track, "clips", None):
        return
    if bool(getattr(track, "locked", False)):
        self._flash_status(f"Blade blocked: track {int(track_id)} is locked")
        return
    from app.timeline_model import split_clips_at_project_ms
    before = len(track.clips)
    track.clips = split_clips_at_project_ms(track.clips, int(project_ms))
    track.clips_explicit = True
    if len(track.clips) == before:
        self._flash_status(tr("veditor.blade.flash.no_clip"))
        return
    row = self._track_rows.get(track.id)
    if row is not None:
        row.flash_timeline_burst("cut", int(project_ms))
        row.update()
    self._refresh_player_tracks()
    self._register_change("blade")


def _format_nudge_status(
    delta_ms: int,
    video_count: int,
    audio_count: int = 0,
    settings: dict | None = None,
) -> str:
    delta = int(delta_ms)
    sign = "+" if delta > 0 else "-"
    amount_ms = abs(delta)
    frame_ms = _timeline_frame_ms(settings)
    frame_count = int(round(amount_ms / max(1, frame_ms)))
    if frame_count > 0 and abs(amount_ms - frame_count * frame_ms) <= 1:
        unit = "frame" if frame_count == 1 else "frames"
        amount = f"{frame_count} {unit} ({amount_ms} ms)"
    elif amount_ms % 1000 == 0:
        amount = f"{amount_ms // 1000}s"
    else:
        amount = f"{amount_ms} ms"
    clip_word = "clip" if int(video_count) == 1 else "clips"
    msg = f"Nudged {int(video_count)} {clip_word} {sign}{amount}"
    if int(audio_count) > 0:
        msg += f"; linked audio {int(audio_count)}"
    return msg


def _timeline_neighbor_edit_point(
    points,
    current_ms: int,
    direction: int,
    *,
    tolerance_ms: int = 2,
) -> int | None:
    current = int(current_ms)
    tol = max(0, int(tolerance_ms))
    clean: set[int] = set()
    for raw in points or []:
        try:
            point = int(raw)
        except Exception:
            continue
        if point >= 0:
            clean.add(point)
    ordered = sorted(clean)
    if int(direction) < 0:
        for point in reversed(ordered):
            if point < current - tol:
                return point
    else:
        for point in ordered:
            if point > current + tol:
                return point
    return None


def _apply_transition_to_selected(self, ttype: str, ms: int) -> None:
    """Apply a clip-boundary transition to all currently selected clips.
    Sets ``transition_out_type`` / ``transition_out_ms`` on each clip and
    triggers a repaint. Called by the Ctrl+T keyboard shortcut."""
    if not self._selected_clips:
        return
    any_change = False
    for tid, cid in self._selected_clips:
        track = self._find_track(tid)
        if track is None:
            continue
        for clip in getattr(track, "clips", []):
            if int(clip.id) == int(cid):
                clip.transition_out_type = ttype
                clip.transition_out_ms = max(50, int(ms))
                clip.transition_preset_meta = {
                    "id": str(ttype),
                    "name": str(ttype).replace("_", " ").title(),
                    "kind": "transition",
                }
                any_change = True
                row = self._track_rows.get(tid)
                if row is not None:
                    row.update()
                break
    if any_change:
        self._register_change("Ctrl+T transition")
