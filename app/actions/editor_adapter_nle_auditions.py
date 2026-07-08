"""Final Cut-style audition adapter methods for Python Actions."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class NleAuditionAdapterMixin:
    """Adapter methods for hidden audition/take groups."""

    def auditions_status(self) -> dict[str, Any]:
        from app.nle_auditions import build_audition_status

        return build_audition_status(getattr(self._require_owner(), "_tracks", []) or [])

    def audition_compare(self, *, track_id: int, clip_id: int) -> dict[str, Any]:
        from app.nle_auditions import build_audition_compare_view

        track, clip = self._find_video_track_and_clip(track_id=_int(track_id, -1), clip_id=_int(clip_id, -1))
        return build_audition_compare_view(track_id=_int(getattr(track, "id", track_id), track_id), clip=clip)

    @staticmethod
    def _apply_audition_take_to_clip(clip: Any, take: Mapping[str, Any]) -> None:
        source_path = str(take.get("source_path") or "").strip()
        clip.source_path = Path(source_path) if source_path else None
        clip.source_duration_ms = _int(take.get("source_duration_ms", 0), 0)
        clip.source_in_ms = _int(take.get("source_in_ms", 0), 0)
        clip.source_out_ms = _int(take.get("source_out_ms", 0), 0)
        try:
            clip.speed = float(take.get("speed", getattr(clip, "speed", 1.0)) or 1.0)
        except Exception:
            pass

    @staticmethod
    def _sync_active_audition_take_from_clip(clip: Any, takes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        from app.nle_auditions import take_from_clip

        active = str(getattr(clip, "audition_active_take_id", "") or "").strip()
        if not active:
            return takes
        for idx, take in enumerate(takes):
            if str(take.get("id") or "") == active:
                label = str(take.get("label") or "")
                takes[idx] = take_from_clip(clip, take_id=active, label=label)
                break
        return takes

    def _ensure_audition_host(
        self,
        clip: Any,
        takes: list[dict[str, Any]],
        *,
        name: str = "",
    ) -> tuple[int, str, list[dict[str, Any]]]:
        from app.nle_auditions import take_from_clip

        group_id = getattr(clip, "audition_group_id", None)
        if group_id is None:
            group_id = _int(getattr(clip, "id", 0), 0)
        active = str(getattr(clip, "audition_active_take_id", "") or "").strip()
        if not takes:
            current = take_from_clip(clip, take_id="take_original", label="Original")
            takes = [current]
            active = current["id"]
        elif not active:
            active = str(takes[0].get("id") or "take_original")
        return int(group_id), active, takes

    def add_audition_take(
        self,
        *,
        host_track_id: int,
        host_clip_id: int,
        take_track_id: int | None = None,
        take_clip_id: int | None = None,
        take_id: str = "",
        label: str = "",
        source_path: str = "",
        source_duration_ms: int = 0,
        source_in_ms: int = 0,
        source_out_ms: int = 0,
        switch_to_take: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_auditions import next_take_id, normalize_take, take_from_clip

        _host_track, host_clip = self._find_video_track_and_clip(
            track_id=_int(host_track_id, -1),
            clip_id=_int(host_clip_id, -1),
        )
        existing = [
            normalize_take(take)
            for take in list(getattr(host_clip, "audition_takes", []) or [])
            if isinstance(take, Mapping)
        ]
        group_id, active, existing = self._ensure_audition_host(host_clip, existing, name=str(label or ""))
        if take_track_id is not None and take_clip_id is not None:
            _take_track, take_clip = self._find_video_track_and_clip(
                track_id=_int(take_track_id, -1),
                clip_id=_int(take_clip_id, -1),
            )
            new_take = take_from_clip(
                take_clip,
                take_id=str(take_id or f"take_clip_{_int(take_clip_id, 0)}"),
                label=label,
            )
        else:
            path = str(source_path or "").strip()
            if not path:
                raise ValueError("source_path or take_track_id/take_clip_id is required")
            generated_id = str(take_id or next_take_id(existing)).strip()
            new_take = normalize_take(
                {
                    "id": generated_id,
                    "label": label or Path(path).name,
                    "source_path": path,
                    "source_duration_ms": _int(source_duration_ms, 0),
                    "source_in_ms": _int(source_in_ms, 0),
                    "source_out_ms": _int(source_out_ms, 0),
                    "speed": 1.0,
                }
            )
        existing = self._sync_active_audition_take_from_clip(host_clip, list(existing))
        replaced = False
        for idx, take in enumerate(existing):
            if str(take.get("id") or "") == str(new_take.get("id") or ""):
                existing[idx] = new_take
                replaced = True
                break
        if not replaced:
            existing.append(new_take)
        target_active = str(new_take.get("id") or active) if switch_to_take else active
        payload = {
            "schema": "tigerstudio.nle.audition.add_take.v1",
            "host_track_id": _int(host_track_id, -1),
            "host_clip_id": _int(host_clip_id, -1),
            "audition_group_id": group_id,
            "active_take_id": target_active,
            "added_take": new_take,
            "take_count": len(existing),
            "replaced": replaced,
        }
        if not dry_run:
            host_clip.audition_group_id = group_id
            host_clip.audition_name = str(getattr(host_clip, "audition_name", "") or label or "Audition")
            host_clip.audition_takes = existing
            host_clip.audition_active_take_id = target_active
            if switch_to_take:
                self._apply_audition_take_to_clip(host_clip, new_take)
            self._after_timeline_mutation("Action add audition take")
        return {
            **payload,
            "dry_run": bool(dry_run),
            "changed": not bool(dry_run),
            "status_after": None if dry_run else self.auditions_status(),
        }

    def switch_audition_take(
        self,
        *,
        track_id: int,
        clip_id: int,
        take_id: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_auditions import normalize_take

        _track, clip = self._find_video_track_and_clip(track_id=_int(track_id, -1), clip_id=_int(clip_id, -1))
        takes = [
            normalize_take(take)
            for take in list(getattr(clip, "audition_takes", []) or [])
            if isinstance(take, Mapping)
        ]
        if not takes:
            raise ValueError("clip has no audition takes")
        target_id = str(take_id or "").strip()
        target = next((take for take in takes if str(take.get("id") or "") == target_id), None)
        if target is None:
            raise ValueError(f"audition take not found: {target_id}")
        updated_takes = self._sync_active_audition_take_from_clip(clip, list(takes))
        payload = {
            "schema": "tigerstudio.nle.audition.switch_take.v1",
            "track_id": _int(track_id, -1),
            "clip_id": _int(clip_id, -1),
            "from_take_id": str(getattr(clip, "audition_active_take_id", "") or ""),
            "to_take_id": target_id,
            "target_take": target,
        }
        if not dry_run:
            clip.audition_takes = updated_takes
            clip.audition_active_take_id = target_id
            self._apply_audition_take_to_clip(clip, target)
            self._after_timeline_mutation("Action switch audition take")
        return {
            **payload,
            "dry_run": bool(dry_run),
            "changed": not bool(dry_run),
            "status_after": None if dry_run else self.auditions_status(),
        }

    def rename_audition_take(
        self,
        *,
        track_id: int,
        clip_id: int,
        take_id: str,
        label: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_auditions import normalize_take

        _track, clip = self._find_video_track_and_clip(track_id=_int(track_id, -1), clip_id=_int(clip_id, -1))
        target_id = str(take_id or "").strip()
        new_label = str(label or "").strip()
        if not target_id:
            raise ValueError("take_id is required")
        if not new_label:
            raise ValueError("label is required")
        takes = [
            normalize_take(take)
            for take in list(getattr(clip, "audition_takes", []) or [])
            if isinstance(take, Mapping)
        ]
        if not takes:
            raise ValueError("clip has no audition takes")
        updated_takes = self._sync_active_audition_take_from_clip(clip, list(takes))
        old_label = ""
        found = False
        for take in updated_takes:
            if str(take.get("id") or "") == target_id:
                old_label = str(take.get("label") or "")
                take["label"] = new_label
                found = True
                break
        if not found:
            raise ValueError(f"audition take not found: {target_id}")
        payload = {
            "schema": "tigerstudio.nle.audition.rename_take.v1",
            "track_id": _int(track_id, -1),
            "clip_id": _int(clip_id, -1),
            "take_id": target_id,
            "old_label": old_label,
            "label": new_label,
        }
        if not dry_run:
            clip.audition_takes = updated_takes
            self._after_timeline_mutation("Action rename audition take")
        return {
            **payload,
            "dry_run": bool(dry_run),
            "changed": not bool(dry_run),
            "compare_after": None if dry_run else self.audition_compare(track_id=track_id, clip_id=clip_id),
        }

    def remove_audition_take(
        self,
        *,
        track_id: int,
        clip_id: int,
        take_id: str,
        switch_to_take_id: str = "",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        from app.nle_auditions import normalize_take

        _track, clip = self._find_video_track_and_clip(track_id=_int(track_id, -1), clip_id=_int(clip_id, -1))
        target_id = str(take_id or "").strip()
        if not target_id:
            raise ValueError("take_id is required")
        takes = [
            normalize_take(take)
            for take in list(getattr(clip, "audition_takes", []) or [])
            if isinstance(take, Mapping)
        ]
        if not takes:
            raise ValueError("clip has no audition takes")
        if len(takes) <= 1:
            raise ValueError("cannot remove the last audition take")
        updated_takes = self._sync_active_audition_take_from_clip(clip, list(takes))
        removed = next((take for take in updated_takes if str(take.get("id") or "") == target_id), None)
        if removed is None:
            raise ValueError(f"audition take not found: {target_id}")
        remaining = [take for take in updated_takes if str(take.get("id") or "") != target_id]
        active_before = str(getattr(clip, "audition_active_take_id", "") or "")
        active_after = active_before
        target_take = None
        if active_before == target_id:
            requested = str(switch_to_take_id or "").strip()
            target_take = next((take for take in remaining if str(take.get("id") or "") == requested), None) if requested else None
            if target_take is None:
                target_take = remaining[0]
            active_after = str(target_take.get("id") or "")
        payload = {
            "schema": "tigerstudio.nle.audition.remove_take.v1",
            "track_id": _int(track_id, -1),
            "clip_id": _int(clip_id, -1),
            "removed_take_id": target_id,
            "removed_take": removed,
            "active_take_id_before": active_before,
            "active_take_id_after": active_after,
            "take_count": len(remaining),
        }
        if not dry_run:
            clip.audition_takes = remaining
            clip.audition_active_take_id = active_after
            if target_take is not None:
                self._apply_audition_take_to_clip(clip, target_take)
            self._after_timeline_mutation("Action remove audition take")
        return {
            **payload,
            "dry_run": bool(dry_run),
            "changed": not bool(dry_run),
            "compare_after": None if dry_run else self.audition_compare(track_id=track_id, clip_id=clip_id),
        }


__all__ = ["NleAuditionAdapterMixin"]
