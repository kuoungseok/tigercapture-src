"""NLE/project-bin adapter methods for Python Actions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class NleAdapterMixin:
    """Source/Record, project-bin, readiness, and multicam adapter methods."""

    def source_record_workbench(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_workbench

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_workbench(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )

    def source_record_edit_decision_preview(self, *, mode: str = "insert") -> dict[str, Any]:
        from app.nle_source_record import build_source_record_edit_decision_preview

        return build_source_record_edit_decision_preview(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            mode=mode,
        )

    def source_record_patch_matrix(self) -> dict[str, Any]:
        from app.nle_source_record import build_source_record_patch_matrix

        try:
            edit_points_payload = self.edit_points(track_kind="video", include_markers=True)
            edit_points = list(edit_points_payload.get("points") or edit_points_payload.get("edit_points") or [])
        except Exception:
            edit_points = []
        return build_source_record_patch_matrix(
            source_monitor=self.source_monitor_state(),
            record_monitor=self.record_monitor_state(),
            track_targets=self.track_targets(),
            playhead_ms=self._current_playhead_ms(),
            edit_points=edit_points,
        )

    def project_bin_workbench(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_workbench

        return build_project_bin_workbench(self.snapshot(media_limit=1000))

    def project_bin_batch_plan(self, *, operation: str = "all") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_batch_plan

        return build_project_bin_batch_plan(self.snapshot(media_limit=1000), operation=operation)

    def project_bin_conform_report(self) -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_conform_report

        return build_project_bin_conform_report(self.snapshot(media_limit=1000))

    def project_bin_proxy_plan(self, *, target: str = "timeline") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_proxy_plan

        return build_project_bin_proxy_plan(self.snapshot(media_limit=1000), target=target)

    def project_bin_proxy_health(self, *, target: str = "timeline") -> dict[str, Any]:
        from app.nle_project_bin import build_project_bin_proxy_health_board

        return build_project_bin_proxy_health_board(self.snapshot(media_limit=1000), target=target)

    def nle_real_corpus_status(self, *, manifest_path: str = "") -> dict[str, Any]:
        from app.nle_real_corpus import build_nle_real_project_corpus_report

        return build_nle_real_project_corpus_report(manifest_path=manifest_path or None)

    def nle_timeline_stress_status(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_timeline_stress_report

        return build_nle_timeline_stress_report(report_path=report_path or None)

    def nle_undo_health(self, *, report_path: str = "") -> dict[str, Any]:
        from app.nle_timeline_stress import build_nle_undo_health_matrix

        return build_nle_undo_health_matrix(report_path=report_path or None)

    def nle_evidence(self, *, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
        from app.nle_evidence import build_nle_evidence_report

        snapshot = self.snapshot(media_limit=500)
        snapshot["nle_real_project_corpus"] = self.nle_real_corpus_status()
        snapshot["nle_timeline_stress"] = self.nle_timeline_stress_status()
        return build_nle_evidence_report(
            snapshot,
            action_ids=tuple(str(row) for row in (action_ids or ())),
            evidence_level="project_snapshot",
        )

    def professional_nle_readiness(
        self,
        *,
        action_count: int = 0,
        action_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        from app.nle_readiness import build_nle_readiness_report, format_nle_readiness_summary

        snapshot = self.snapshot(media_limit=500)
        snapshot["nle_evidence"] = self.nle_evidence(action_ids=action_ids)
        report = build_nle_readiness_report(snapshot, action_count=max(0, _int(action_count, 0)))
        report["summary_text"] = format_nle_readiness_summary(report)
        return report

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
