from __future__ import annotations


def _on_cross_track_group_drag_delta(
    self, origin_track_id: int, origin_clip_id: int, delta_ms: int
) -> None:
    """Move selected video clips on other tracks with the dragged clip."""
    delta = int(delta_ms)
    if delta == 0 or not getattr(self, "_selected_clips", None):
        return
    by_track: dict[int, list[int]] = {}
    for tid, cid in list(self._selected_clips):
        tid = int(tid)
        cid = int(cid)
        if tid == int(origin_track_id):
            continue
        by_track.setdefault(tid, []).append(cid)

    any_change = False
    for tid, clip_ids in by_track.items():
        track = self._find_track(tid)
        if track is None or bool(getattr(track, "locked", False)):
            continue
        clips = list(getattr(track, "clips", []) or [])
        selected_ids = set(int(c) for c in clip_ids)
        selected = [c for c in clips if int(getattr(c, "id", -1)) in selected_ids]
        if not selected:
            continue

        proposals: list[tuple[object, int, int]] = []
        blocked = False
        for clip in selected:
            new_start = int(getattr(clip, "timeline_in_ms", 0)) + delta
            new_end = new_start + int(getattr(clip, "effective_length_ms", 0))
            if new_start < 0:
                blocked = True
                break
            proposals.append((clip, new_start, new_end))
        if blocked:
            continue

        for clip, start, end in proposals:
            for other in clips:
                if int(getattr(other, "id", -1)) in selected_ids:
                    continue
                other_start = int(getattr(other, "timeline_in_ms", 0))
                other_end = int(getattr(other, "timeline_out_ms", 0))
                if not (other_end <= start or end <= other_start):
                    blocked = True
                    break
            if blocked:
                break
        if blocked:
            continue

        track_changed = False
        for clip, start, _end in proposals:
            old_start = int(getattr(clip, "timeline_in_ms", 0))
            if old_start == start:
                continue
            clip.timeline_in_ms = int(start)
            if len(clips) <= 1:
                track.offset_ms = int(start)
            if getattr(clip, "linked_audio_id", None) is not None:
                self._on_clip_drag_delta(tid, int(clip.id), int(start), int(start - old_start))
            track_changed = True
        if track_changed:
            any_change = True
            track.clips.sort(key=lambda c: int(c.timeline_in_ms))
            row = self._track_rows.get(tid)
            if row is not None:
                row._recalc_width()
                row.update()

    if any_change:
        self._update_tracks_host_width()


def _linked_move_block_message(self, action: str, plan) -> str:
    details = getattr(plan, "details", {}) or {}
    base = {
        "timeline_start": f"{action} blocked at timeline start",
        "video_collision": f"{action} blocked by another video clip",
        "audio_collision": f"{action} blocked by linked audio",
        "missing_linked_audio": f"{action} blocked: linked audio is missing",
        "duplicate_linked_audio": f"{action} blocked: duplicate linked audio id",
        "shared_linked_audio": f"{action} blocked: linked audio is shared",
        "missing_video_clip": f"{action} blocked: selected clip is missing",
        "locked_track": f"{action} blocked: track is locked",
    }.get(getattr(plan, "blocked_reason", ""), f"{action} blocked")
    reason = getattr(plan, "blocked_reason", "")
    if reason == "locked_track":
        track_id = details.get("track_id")
        clip_id = details.get("clip_id")
        if track_id is not None and clip_id is not None:
            return f"{base}: clip {clip_id} on track {track_id}"
    if reason in {"video_collision", "audio_collision"}:
        clip_id = details.get("clip_id")
        other_id = details.get("other_clip_id")
        track_id = details.get("track_id")
        if clip_id is not None and other_id is not None:
            lane = f" on track {track_id}" if track_id is not None else ""
            return f"{base}: clip {clip_id} overlaps clip {other_id}{lane}"
    if reason == "shared_linked_audio":
        linked_id = details.get("linked_audio_id") or details.get("clip_id")
        video_id = details.get("video_clip_id")
        if linked_id is not None and video_id is not None:
            return f"{base}: video clip {video_id} also links audio clip {linked_id}"
    if reason == "missing_video_clip":
        track_id = details.get("track_id")
        clip_id = details.get("clip_id")
        if track_id is not None and clip_id is not None:
            return f"{base}: clip {clip_id} on track {track_id}"
    if reason == "timeline_start":
        attempted = details.get("attempted_start_ms")
        if attempted is not None:
            return f"{base}: attempted {int(attempted)} ms"
    return base


def _validate_clip_drag_delta(
    self, origin_track_id: int, origin_clip_ids: set[int], delta_ms: int
):
    """Preflight clip drags before TrackRow mutates video/audio lanes."""
    delta = int(delta_ms)
    if delta == 0:
        return {"ok": True}
    origin_keys = [
        (int(origin_track_id), int(clip_id))
        for clip_id in (origin_clip_ids or set())
    ]
    selected = list(getattr(self, "_selected_clips", []) or [])
    if not any(key in selected for key in origin_keys):
        selected = origin_keys
    if not selected:
        return {"ok": True}
    try:
        from app.timeline_model import plan_linked_timeline_move

        plan = plan_linked_timeline_move(
            self._tracks,
            self._audio_tracks,
            selected,
            delta,
            strict_selection=True,
        )
    except Exception:
        return {"ok": True}
    if plan.ok:
        return {"ok": True}
    message = _linked_move_block_message(self, "Drag", plan)
    self._flash_status(message)
    return {
        "ok": False,
        "reason": str(getattr(plan, "blocked_reason", "") or ""),
        "message": message,
        "details": getattr(plan, "details", {}) or {},
    }


def _on_clip_drag_delta(
    self, track_id: int, clip_id: int, new_timeline_in_ms: int, delta_ms: int
) -> None:
    """When a VideoClip with ``linked_audio_id`` is dragged, move the
    linked AudioClip by the same delta so they stay in sync."""
    if delta_ms == 0:
        return
    track = self._find_track(track_id)
    if track is None:
        return
    clip = next((c for c in getattr(track, "clips", []) if c.id == clip_id), None)
    if clip is None:
        return
    linked_id = getattr(clip, "linked_audio_id", None)
    if linked_id is None:
        return
    # Find the audio clip with that id across all audio tracks.
    for atrack in self._audio_tracks:
        for aclip in atrack.clips:
            if aclip.id == linked_id:
                new_offset = max(0, int(aclip.offset_ms) + delta_ms)
                aclip.offset_ms = new_offset
                row = self._audio_rows.get(atrack.id)
                if row is not None:
                    row.update()
                try:
                    self._audio_mixer.update_track(atrack)
                except Exception:
                    pass
                self._update_tracks_host_width()
                return

