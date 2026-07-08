"""Multicam adapter methods for Python Actions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class NleMulticamAdapterMixin:
    """Adapter methods for multicam grouping, switching, and export handoff."""

    def multicam_summary(self) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_groups

        owner = self._require_owner()
        return build_multicam_groups(
            self.snapshot(media_limit=500),
            stored_groups=getattr(owner, "_nle_multicam_groups", []) or [],
        )

    def create_multicam_group(
        self,
        *,
        group_id: str = "",
        name: str = "",
        track_ids: Sequence[int] | None = None,
    ) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_groups

        owner = self._require_owner()
        before = build_multicam_groups(
            self.snapshot(media_limit=500),
            stored_groups=getattr(owner, "_nle_multicam_groups", []) or [],
        )
        generated = build_multicam_groups(self.snapshot(media_limit=500))
        base = dict((generated.get("groups") or [{}])[0]) if generated.get("groups") else {}
        if not base:
            raise ValueError("at least two video angles are required for a multicam group")
        wanted_tracks = sorted({_int(value, 0) for value in list(track_ids or []) if _int(value, 0) > 0})
        if wanted_tracks:
            angles = []
            for angle in list(base.get("angles") or []):
                if not isinstance(angle, Mapping):
                    continue
                angle_tracks = {_int(value, 0) for value in list(angle.get("track_ids") or [])}
                if angle_tracks & set(wanted_tracks):
                    angles.append(dict(angle))
            base["angles"] = angles
            base["angle_count"] = len(angles)
        base["id"] = str(group_id or base.get("id") or "multicam_group_1")
        base["name"] = str(name or base.get("name") or "Multicam Group")
        base["source"] = "project"
        groups = [dict(row) for row in list(getattr(owner, "_nle_multicam_groups", []) or []) if isinstance(row, Mapping)]
        groups = [row for row in groups if str(row.get("id") or "") != base["id"]]
        groups.append(base)
        setattr(owner, "_nle_multicam_groups", groups)
        self._register_change("Create multicam group")
        after = build_multicam_groups(self.snapshot(media_limit=500), stored_groups=groups)
        return {"before": before, "after": after, "group": base}

    def multicam_switch_plan(
        self,
        *,
        group_id: str = "",
        strategy: str = "round_robin",
        max_segments: int = 240,
    ) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_switch_plan

        return build_multicam_switch_plan(
            self.snapshot(media_limit=500),
            group_id=str(group_id or ""),
            strategy=str(strategy or "round_robin"),
            max_segments=max(1, _int(max_segments, 240)),
        )

    def multicam_sync_plan(self, *, group_id: str = "", strategy: str = "hybrid") -> dict[str, Any]:
        from app.nle_multicam import build_multicam_sync_plan

        return build_multicam_sync_plan(
            self.snapshot(media_limit=500),
            group_id=str(group_id or ""),
            strategy=str(strategy or "hybrid"),
        )

    def multicam_sync_quality_board(self, *, group_id: str = "", strategy: str = "hybrid") -> dict[str, Any]:
        from app.nle_multicam import build_multicam_sync_quality_board

        return build_multicam_sync_quality_board(
            self.snapshot(media_limit=500),
            group_id=str(group_id or ""),
            strategy=str(strategy or "hybrid"),
        )

    def multicam_waveform_sync_board(self, *, group_id: str = "", strategy: str = "waveform") -> dict[str, Any]:
        from app.nle_multicam import build_multicam_waveform_sync_board

        return build_multicam_waveform_sync_board(
            self.snapshot(media_limit=500),
            group_id=str(group_id or ""),
            strategy=str(strategy or "waveform"),
        )

    def multicam_angle_bins(self, *, group_id: str = "") -> dict[str, Any]:
        from app.nle_multicam import build_multicam_angle_bins

        owner = self._require_owner()
        return build_multicam_angle_bins(
            self.snapshot(media_limit=500),
            group_id=str(group_id or ""),
            stored_groups=getattr(owner, "_nle_multicam_groups", []) or [],
        )

    def multicam_switcher_workbench(
        self,
        *,
        group_id: str = "",
        strategy: str = "round_robin",
    ) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_switcher_workbench

        owner = self._require_owner()
        gid = str(group_id or "multicam_auto_1")
        switches = [
            dict(row)
            for row in list(getattr(owner, "_nle_multicam_switches", []) or [])
            if isinstance(row, Mapping) and str(row.get("group_id") or gid) == gid
        ]
        return build_multicam_switcher_workbench(
            self.snapshot(media_limit=500),
            group_id=gid,
            switches=switches,
            playhead_ms=self._current_playhead_ms(),
            strategy=str(strategy or "round_robin"),
        )

    def multicam_switcher_tile_board(
        self,
        *,
        group_id: str = "",
        strategy: str = "round_robin",
    ) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_switcher_tile_board

        owner = self._require_owner()
        gid = str(group_id or "multicam_auto_1")
        switches = [
            dict(row)
            for row in list(getattr(owner, "_nle_multicam_switches", []) or [])
            if isinstance(row, Mapping) and str(row.get("group_id") or gid) == gid
        ]
        return build_multicam_switcher_tile_board(
            self.snapshot(media_limit=500),
            group_id=gid,
            switches=switches,
            playhead_ms=self._current_playhead_ms(),
            strategy=str(strategy or "round_robin"),
        )

    def multicam_switch_review_board(
        self,
        *,
        group_id: str = "",
        strategy: str = "round_robin",
    ) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_switch_review_board

        owner = self._require_owner()
        gid = str(group_id or "multicam_auto_1")
        switches = [
            dict(row)
            for row in list(getattr(owner, "_nle_multicam_switches", []) or [])
            if isinstance(row, Mapping) and str(row.get("group_id") or gid) == gid
        ]
        return build_multicam_switch_review_board(
            self.snapshot(media_limit=500),
            group_id=gid,
            switches=switches,
            playhead_ms=self._current_playhead_ms(),
            strategy=str(strategy or "round_robin"),
        )

    def multicam_live_switch_dashboard(
        self,
        *,
        group_id: str = "",
        strategy: str = "round_robin",
    ) -> dict[str, Any]:
        from app.nle_multicam import build_multicam_live_switch_dashboard

        owner = self._require_owner()
        gid = str(group_id or "multicam_auto_1")
        switches = [
            dict(row)
            for row in list(getattr(owner, "_nle_multicam_switches", []) or [])
            if isinstance(row, Mapping) and str(row.get("group_id") or gid) == gid
        ]
        return build_multicam_live_switch_dashboard(
            self.snapshot(media_limit=500),
            group_id=gid,
            switches=switches,
            playhead_ms=self._current_playhead_ms(),
            strategy=str(strategy or "round_robin"),
        )

    def set_multicam_active_angle(
        self,
        *,
        group_id: str = "",
        angle_id: str,
        at_ms: int | None = None,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        target_ms = self._current_playhead_ms() if at_ms is None else max(0, _int(at_ms, 0))
        gid = str(group_id or "multicam_auto_1")
        switch = {
            "group_id": gid,
            "timeline_in_ms": target_ms,
            "angle_id": str(angle_id or ""),
        }
        if not switch["angle_id"]:
            raise ValueError("angle_id is required")
        rows = [dict(row) for row in list(getattr(owner, "_nle_multicam_switches", []) or []) if isinstance(row, Mapping)]
        rows = [
            row
            for row in rows
            if not (str(row.get("group_id") or "") == gid and _int(row.get("timeline_in_ms"), 0) == target_ms)
        ]
        rows.append(switch)
        rows.sort(key=lambda row: (str(row.get("group_id") or ""), _int(row.get("timeline_in_ms"), 0)))
        setattr(owner, "_nle_multicam_switches", rows)
        self._register_change("Set multicam active angle")
        return {"switch": switch, "switch_count": len(rows), "switches": rows}

    def multicam_export_handoff(self, *, group_id: str = "") -> dict[str, Any]:
        from app.nle_multicam import build_multicam_export_handoff, build_multicam_switch_plan

        owner = self._require_owner()
        snapshot = self.snapshot(media_limit=500)
        gid = str(group_id or "multicam_auto_1")
        stored = [
            dict(row)
            for row in list(getattr(owner, "_nle_multicam_switches", []) or [])
            if isinstance(row, Mapping) and str(row.get("group_id") or gid) == gid
        ]
        if stored:
            plan = build_multicam_switch_plan(snapshot, group_id=gid)
            segments = list(plan.get("segments") or [])
            enriched: list[dict[str, Any]] = []
            ordered = sorted(stored, key=lambda row: _int(row.get("timeline_in_ms"), 0))
            for index, switch in enumerate(ordered):
                start = _int(switch.get("timeline_in_ms"), 0)
                next_start = _int(ordered[index + 1].get("timeline_in_ms"), 0) if index + 1 < len(ordered) else None
                candidates = [
                    row
                    for row in segments
                    if str(row.get("angle_id") or "") == str(switch.get("angle_id") or "")
                    and _int(row.get("timeline_out_ms"), 0) > start
                    and (next_start is None or _int(row.get("timeline_in_ms"), 0) < next_start)
                ]
                enriched.extend(dict(row) for row in candidates)
            stored = enriched or stored
        return build_multicam_export_handoff(snapshot, group_id=gid, switches=stored)


__all__ = ["NleMulticamAdapterMixin"]
