"""Final Cut-style storyline, connected clip, and role-lane adapter methods."""
from __future__ import annotations

from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class NleStorylineAdapterMixin:
    """Adapter methods for magnetic storyline, connected clips, and role lanes."""

    def magnetic_storyline_status(
        self,
        *,
        track_id: int | None = None,
        min_gap_ms: int = 1,
    ) -> dict[str, Any]:
        from app.nle_magnetic_storyline import build_magnetic_storyline_status

        return build_magnetic_storyline_status(
            getattr(self._require_owner(), "_tracks", []) or [],
            track_id=track_id,
            min_gap_ms=max(1, _int(min_gap_ms, 1)),
        )

    def apply_magnetic_storyline(
        self,
        *,
        track_id: int | None = None,
        min_gap_ms: int = 1,
        include_linked_audio: bool = True,
        pull_first_to_zero: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_magnetic_storyline import build_magnetic_storyline_plan

        owner = self._require_owner()
        plan = build_magnetic_storyline_plan(
            getattr(owner, "_tracks", []) or [],
            track_id=track_id,
            min_gap_ms=max(1, _int(min_gap_ms, 1)),
            pull_first_to_zero=bool(pull_first_to_zero),
        )
        moved_audio: list[dict[str, int]] = []
        audio_warnings: list[str] = []
        if not dry_run and int(plan.get("move_count", 0) or 0) > 0:
            tracks_by_id = {
                _int(getattr(track, "id", -1), -1): track
                for track in list(getattr(owner, "_tracks", []) or [])
            }
            for move in list(plan.get("moves") or []):
                tid = _int(move.get("track_id"), -1)
                cid = _int(move.get("clip_id"), -1)
                target = max(0, _int(move.get("to_ms"), 0))
                delta = _int(move.get("delta_ms"), 0)
                track = tracks_by_id.get(tid)
                if track is None:
                    continue
                clip = next(
                    (
                        row
                        for row in list(getattr(track, "clips", []) or [])
                        if _int(getattr(row, "id", -1), -1) == cid
                    ),
                    None,
                )
                if clip is None:
                    continue
                if include_linked_audio and delta != 0 and getattr(clip, "linked_audio_id", None) is not None:
                    try:
                        audio_track, audio_clip = self._linked_audio_track_and_clip(clip)
                        before = _int(getattr(audio_clip, "offset_ms", 0), 0)
                        audio_clip.offset_ms = max(0, before + delta)
                        self._update_audio_track(audio_track)
                        moved_audio.append(
                            {
                                "audio_track_id": _int(getattr(audio_track, "id", 0), 0),
                                "audio_clip_id": _int(getattr(audio_clip, "id", 0), 0),
                                "from_ms": before,
                                "to_ms": _int(getattr(audio_clip, "offset_ms", 0), 0),
                                "delta_ms": delta,
                            }
                        )
                    except Exception as exc:
                        audio_warnings.append(f"clip {cid}: {exc}")
                clip.timeline_in_ms = target
            for track in tracks_by_id.values():
                clips = getattr(track, "clips", None)
                if isinstance(clips, list):
                    clips.sort(key=lambda row: _int(getattr(row, "timeline_in_ms", 0), 0))
            self._after_timeline_mutation("Action magnetic storyline")
        status_after = None if dry_run else self.magnetic_storyline_status(track_id=track_id, min_gap_ms=min_gap_ms)
        return {
            "schema": "tigerstudio.nle.magnetic_storyline.apply.v1",
            "plan": plan,
            "changed": bool((not dry_run) and int(plan.get("move_count", 0) or 0) > 0),
            "dry_run": bool(dry_run),
            "include_linked_audio": bool(include_linked_audio),
            "moved_linked_audio": moved_audio,
            "linked_audio_warning_count": len(audio_warnings),
            "linked_audio_warnings": audio_warnings,
            "status_after": status_after,
        }

    def connected_clips_status(self) -> dict[str, Any]:
        from app.nle_connected_clips import build_connected_clip_status

        return build_connected_clip_status(getattr(self._require_owner(), "_tracks", []) or [])

    def role_colors_status(self) -> dict[str, Any]:
        from app.nle_connected_clips import build_role_color_status

        return build_role_color_status(getattr(self._require_owner(), "_tracks", []) or [])

    def role_lanes_status(self) -> dict[str, Any]:
        from app.nle_role_lanes import build_role_lane_status

        owner = self._require_owner()
        return build_role_lane_status(
            getattr(owner, "_tracks", []) or [],
            focused_role=str(getattr(owner, "_nle_role_lane_focus", "") or ""),
        )

    def set_role_lane_focus(self, *, role: str = "", clear: bool = False, dry_run: bool = False) -> dict[str, Any]:
        from app.nle_connected_clips import normalize_clip_role

        owner = self._require_owner()
        before = str(getattr(owner, "_nle_role_lane_focus", "") or "")
        target = "" if clear else normalize_clip_role(role, fallback="primary")
        payload = {
            "schema": "tigerstudio.nle.role_lanes.focus.v1",
            "from_role": before,
            "to_role": target,
            "cleared": bool(clear),
        }
        if not dry_run:
            setattr(owner, "_nle_role_lane_focus", target)
            rows = getattr(owner, "_track_rows", {}) or {}
            for row in list(rows.values()):
                setter = getattr(row, "set_focused_clip_role", None)
                if callable(setter):
                    setter(target)
            refresh_roles = getattr(owner, "_refresh_nle_role_filter_bar", None)
            if callable(refresh_roles):
                refresh_roles()
            anchor_overlay = getattr(owner, "_connected_anchor_overlay", None)
            refresh_anchor_overlay = getattr(anchor_overlay, "refresh", None)
            if callable(refresh_anchor_overlay):
                refresh_anchor_overlay()
            self._after_timeline_mutation("Action set role lane focus")
        return {
            **payload,
            "dry_run": bool(dry_run),
            "changed": bool((not dry_run) and before != target),
            "status_after": None if dry_run else self.role_lanes_status(),
        }

    def _find_video_track_and_clip(self, *, track_id: int, clip_id: int):
        owner = self._require_owner()
        for track in list(getattr(owner, "_tracks", []) or []):
            if _int(getattr(track, "id", -1), -1) != _int(track_id, -2):
                continue
            for clip in list(getattr(track, "clips", []) or []):
                if _int(getattr(clip, "id", -1), -1) == _int(clip_id, -2):
                    return track, clip
        raise ValueError(f"clip not found: track_id={track_id}, clip_id={clip_id}")

    def _find_storyline_parent_clip(
        self,
        *,
        child_track_id: int,
        child_clip_id: int,
        parent_track_id: int | None = None,
        parent_clip_id: int | None = None,
        at_ms: int | None = None,
    ):
        owner = self._require_owner()
        if parent_track_id is not None and parent_clip_id is not None:
            return self._find_video_track_and_clip(track_id=parent_track_id, clip_id=parent_clip_id)
        child_track, child_clip = self._find_video_track_and_clip(track_id=child_track_id, clip_id=child_clip_id)
        probe_ms = _int(at_ms, _int(getattr(child_clip, "timeline_in_ms", 0), 0))
        candidates = []
        for track in list(getattr(owner, "_tracks", []) or []):
            tid = _int(getattr(track, "id", -1), -1)
            if tid == _int(child_track_id, -2):
                continue
            if bool(getattr(track, "locked", False)):
                continue
            for clip in list(getattr(track, "clips", []) or []):
                start = _int(getattr(clip, "timeline_in_ms", 0), 0)
                end = _int(getattr(clip, "timeline_out_ms", start), start)
                if start <= probe_ms < end:
                    candidates.append((abs(tid - _int(child_track_id, tid)), tid, track, clip))
        if candidates:
            _distance, _tid, track, clip = sorted(candidates, key=lambda row: (row[0], row[1]))[0]
            return track, clip
        raise ValueError("No parent storyline clip found at the child clip time. Provide parent_track_id and parent_clip_id.")

    def connect_clip_to_storyline(
        self,
        *,
        child_track_id: int,
        child_clip_id: int,
        parent_track_id: int | None = None,
        parent_clip_id: int | None = None,
        at_ms: int | None = None,
        role: str = "b_roll",
        role_color: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_connected_clips import normalize_clip_role, role_color_for

        child_track, child_clip = self._find_video_track_and_clip(
            track_id=_int(child_track_id, -1),
            clip_id=_int(child_clip_id, -1),
        )
        parent_track, parent_clip = self._find_storyline_parent_clip(
            child_track_id=_int(child_track_id, -1),
            child_clip_id=_int(child_clip_id, -1),
            parent_track_id=parent_track_id,
            parent_clip_id=parent_clip_id,
            at_ms=at_ms,
        )
        parent_tid = _int(getattr(parent_track, "id", 0), 0)
        parent_cid = _int(getattr(parent_clip, "id", 0), 0)
        child_start = _int(getattr(child_clip, "timeline_in_ms", 0), 0)
        parent_start = _int(getattr(parent_clip, "timeline_in_ms", 0), 0)
        offset_ms = child_start - parent_start
        normalized_role = normalize_clip_role(role or "b_roll", fallback="b_roll")
        color = role_color_for(normalized_role, role_color)
        plan = {
            "schema": "tigerstudio.nle.connected_clip.connect.v1",
            "child_track_id": _int(getattr(child_track, "id", child_track_id), child_track_id),
            "child_clip_id": _int(getattr(child_clip, "id", child_clip_id), child_clip_id),
            "parent_track_id": parent_tid,
            "parent_clip_id": parent_cid,
            "connected_offset_ms": offset_ms,
            "role": normalized_role,
            "role_color": color,
        }
        if not dry_run:
            child_clip.connected_parent_track_id = parent_tid
            child_clip.connected_parent_clip_id = parent_cid
            child_clip.connected_offset_ms = offset_ms
            child_clip.clip_role = normalized_role
            child_clip.role_color = color
            self._after_timeline_mutation("Action connect clip to storyline")
            owner = self._require_owner()
            refresh_roles = getattr(owner, "_refresh_nle_role_filter_bar", None)
            if callable(refresh_roles):
                refresh_roles()
            anchor_overlay = getattr(owner, "_connected_anchor_overlay", None)
            refresh_anchor_overlay = getattr(anchor_overlay, "refresh", None)
            if callable(refresh_anchor_overlay):
                refresh_anchor_overlay()
        return {
            **plan,
            "dry_run": bool(dry_run),
            "changed": not bool(dry_run),
            "status_after": None if dry_run else self.connected_clips_status(),
        }

    def set_clip_role(
        self,
        *,
        track_id: int,
        clip_id: int,
        role: str,
        role_color: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_connected_clips import normalize_clip_role, role_color_for

        track, clip = self._find_video_track_and_clip(track_id=_int(track_id, -1), clip_id=_int(clip_id, -1))
        normalized_role = normalize_clip_role(role, fallback="primary")
        color = role_color_for(normalized_role, role_color)
        payload = {
            "schema": "tigerstudio.nle.clip_role.set.v1",
            "track_id": _int(getattr(track, "id", track_id), track_id),
            "clip_id": _int(getattr(clip, "id", clip_id), clip_id),
            "role": normalized_role,
            "role_color": color,
        }
        if not dry_run:
            clip.clip_role = normalized_role
            clip.role_color = color
            self._after_timeline_mutation("Action set clip role")
            owner = self._require_owner()
            refresh_roles = getattr(owner, "_refresh_nle_role_filter_bar", None)
            if callable(refresh_roles):
                refresh_roles()
            anchor_overlay = getattr(owner, "_connected_anchor_overlay", None)
            refresh_anchor_overlay = getattr(anchor_overlay, "refresh", None)
            if callable(refresh_anchor_overlay):
                refresh_anchor_overlay()
        return {
            **payload,
            "dry_run": bool(dry_run),
            "changed": not bool(dry_run),
            "role_colors": None if dry_run else self.role_colors_status(),
        }


__all__ = ["NleStorylineAdapterMixin"]
