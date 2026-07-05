"""MMD action adapter helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST, run_mmd_qa_manifest
from app.mmd.editor_composite_qa import (
    DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
    DEFAULT_MMD_EDITOR_COMPOSITE_QA_OUT_DIR,
    DEFAULT_MMD_EDITOR_COMPOSITE_QA_REPORT,
    run_mmd_editor_composite_qa,
)
from app.mmd.timeline_qa import (
    DEFAULT_MMD_TIMELINE_ENTRY_ID,
    DEFAULT_MMD_TIMELINE_QA_OUT_DIR,
    DEFAULT_MMD_TIMELINE_QA_REPORT,
    run_mmd_timeline_qa,
)
from app.mmd.segment_timing_qa import (
    DEFAULT_MMD_SEGMENT_TIMING_ENTRY_ID,
    DEFAULT_MMD_SEGMENT_TIMING_QA_OUT_DIR,
    DEFAULT_MMD_SEGMENT_TIMING_QA_REPORT,
    run_mmd_segment_timing_qa,
)
from app.mmd.render_queue_qa import (
    DEFAULT_MMD_LONG_PROJECT_EXPORT_QA_REPORT,
    DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
    DEFAULT_MMD_RENDER_QUEUE_EXPORT_QA_REPORT,
    DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
    DEFAULT_MMD_RENDER_QUEUE_QA_REPORT,
    run_mmd_long_project_export_qa,
    run_mmd_render_queue_export_qa,
    run_mmd_render_queue_wiring_qa,
)


def _mmd_qa_entries_summary(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source_rows = list(payload.get("entries") or payload.get("results") or [])
    for entry in source_rows:
        if not isinstance(entry, Mapping) or bool(entry.get("skipped")):
            continue
        report = entry.get("report")
        risk_codes: list[str] = []
        feature_flags: list[str] = []
        screenshot = ""
        if isinstance(report, Mapping):
            risk_codes = [str(value) for value in list(report.get("risk_codes") or [])]
            feature_flags = [str(value) for value in list(report.get("feature_flags") or [])]
        visual_metrics = entry.get("visual_metrics") if isinstance(entry.get("visual_metrics"), Mapping) else {}
        if "screenshot" in entry:
            screenshot = str(entry.get("screenshot") or "")
        row = {
            "id": str(entry.get("id") or ""),
            "status": str(entry.get("status") or ""),
            "ok": bool(entry.get("ok")),
            "risk_codes": risk_codes,
            "feature_flags": feature_flags,
        }
        if screenshot:
            row["screenshot"] = screenshot
        if visual_metrics:
            row["visual_metrics"] = dict(visual_metrics)
        if entry.get("error"):
            row["error"] = str(entry.get("error") or "")
        rows.append(row)
    return rows


def _mmd_qa_result(payload: Mapping[str, Any], *, include_reports: bool = False) -> dict[str, Any]:
    result = {
        "ok": bool(payload.get("ok")),
        "manifest": str(payload.get("manifest") or ""),
        "run_count": int(payload.get("run_count", 0) or 0),
        "entry_count": int(payload.get("entry_count", 0) or 0),
        "blocked_count": int(payload.get("blocked_count", 0) or 0),
        "entries": _mmd_qa_entries_summary(payload),
        "blocked_entries": [dict(row) for row in list(payload.get("blocked_entries") or []) if isinstance(row, Mapping)],
    }
    for key in ("out_dir", "contact_sheet", "report", "width", "height", "gpu_skinning_requested"):
        if key in payload:
            result[key] = payload.get(key)
    if include_reports:
        result["raw"] = dict(payload)
    return result


class MmdAdapterMixin:
    def _mmd_tracks(self) -> list[dict[str, Any]]:
        owner = self.owner
        tracks = getattr(owner, "_mmd_tracks", None) if owner is not None else None
        if tracks is None and owner is not None:
            tracks = []
            setattr(owner, "_mmd_tracks", tracks)
        return tracks if isinstance(tracks, list) else []

    def _mmd_find_track(self, track_id: str) -> dict[str, Any] | None:
        for track in self._mmd_tracks():
            if isinstance(track, dict) and str(track.get("id") or "") == str(track_id):
                return track
        return None

    def _mmd_refresh_owner(self, track: dict[str, Any] | None = None, *, label: str = "mmd action") -> None:
        owner = self.owner
        if owner is None:
            return
        refresh = getattr(owner, "_refresh_mmd_track_after_editor_change", None)
        if callable(refresh) and isinstance(track, dict):
            refresh(track, register=True, label=label)
            return
        sync = getattr(owner, "_sync_mmd_tracks_to_player", None)
        if callable(sync):
            sync()
        refresh_tracks = getattr(owner, "_refresh_player_tracks", None)
        if callable(refresh_tracks):
            refresh_tracks()
        player = getattr(owner, "_player", None)
        if player is not None and hasattr(player, "refresh_current_frame"):
            try:
                player.refresh_current_frame()
            except Exception:
                pass
        register = getattr(owner, "_register_change", None)
        if callable(register):
            register(label)

    def mmd_summary(self, *, limit: int = 100) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for track in self._mmd_tracks()[: max(0, int(limit or 100))]:
            if not isinstance(track, dict):
                continue
            rows.append(
                {
                    "id": str(track.get("id") or ""),
                    "model_path": str(track.get("model_path") or ""),
                    "motion_path": str(track.get("motion_path") or ""),
                    "start_ms": int(track.get("start_ms", 0) or 0),
                    "end_ms": int(track.get("end_ms", 0) or 0),
                    "playback": dict(track.get("playback") or {}),
                    "render": dict(track.get("render") or {}),
                }
            )
        return {"track_count": len(self._mmd_tracks()), "tracks": rows}

    def mmd_diagnostics(
        self,
        *,
        track_id: str = "",
        pos_ms: int | None = None,
        include_materials: bool = True,
        animate: bool = False,
    ) -> dict[str, Any]:
        owner = self.owner
        player = getattr(owner, "_player", None) if owner is not None else None
        if player is not None and hasattr(player, "mmd_diagnostics"):
            data = dict(
                player.mmd_diagnostics(
                    pos_ms=pos_ms,
                    include_materials=bool(include_materials),
                    animate=bool(animate),
                )
                or {}
            )
        else:
            if pos_ms is None and player is not None and hasattr(player, "position"):
                try:
                    pos_ms = int(player.position())
                except Exception:
                    pos_ms = 0
            position = int(pos_ms or 0)
            rows: list[dict[str, Any]] = []
            for index, track in enumerate(self._mmd_tracks()):
                if not isinstance(track, dict):
                    continue
                current_id = str(track.get("id") or f"mmd_{index + 1:03d}")
                active = int(track.get("start_ms", 0) or 0) <= position < int(track.get("end_ms", 0) or 0)
                rows.append(
                    {
                        "id": current_id,
                        "active": bool(active),
                        "model_path": str(track.get("model_path") or ""),
                        "motion_path": str(track.get("motion_path") or ""),
                        "start_ms": int(track.get("start_ms", 0) or 0),
                        "end_ms": int(track.get("end_ms", 0) or 0),
                        "duration_ms": int(track.get("duration_ms", 0) or 0),
                        "playback": dict(track.get("playback") or {}),
                        "render": dict(track.get("render") or {}),
                        "diagnostics": {},
                        "material_bucket_counts": {},
                        "material_class_counts": {},
                        "material_bucket_rows": [],
                    }
                )
            data = {
                "position_ms": int(position),
                "track_count": int(len(rows)),
                "active_track_count": int(sum(1 for row in rows if row.get("active"))),
                "include_materials": False,
                "animated_sample": False,
                "tracks": rows,
                "last_error": {},
            }
        if track_id:
            wanted = str(track_id)
            tracks = [row for row in list(data.get("tracks") or []) if str(row.get("id") or "") == wanted]
            data["tracks"] = tracks
            data["track_count"] = len(tracks)
            data["active_track_count"] = int(sum(1 for row in tracks if row.get("active")))
        return data

    def mmd_qa_run(self, *, manifest: str = "", include_reports: bool = False) -> dict[str, Any]:
        payload = run_mmd_qa_manifest(manifest or DEFAULT_MMD_QA_MANIFEST)
        return _mmd_qa_result(payload, include_reports=bool(include_reports))

    def mmd_qa_visual_run(
        self,
        *,
        manifest: str = "",
        out_dir: str = "",
        width: int = 960,
        height: int = 540,
        cpu_skinning: bool = False,
        include_reports: bool = False,
    ) -> dict[str, Any]:
        from tools.mmd_qa_visual_corpus import DEFAULT_OUT_DIR, run_visual_corpus

        payload = run_visual_corpus(
            Path(manifest).expanduser().resolve() if manifest else DEFAULT_MMD_QA_MANIFEST,
            Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_OUT_DIR,
            width=max(160, int(width or 960)),
            height=max(120, int(height or 540)),
            use_gpu_skinning=not bool(cpu_skinning),
        )
        return _mmd_qa_result(payload, include_reports=bool(include_reports))

    def mmd_qa_composite_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
        out_dir: str = "",
        report_path: str = "",
        width: int = 320,
        height: int = 180,
        duration_ms: int = 1000,
        fps: int = 12,
        sample_time_ms: int | None = None,
        include_reports: bool = False,
    ) -> dict[str, Any]:
        payload = run_mmd_editor_composite_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_EDITOR_COMPOSITE_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_EDITOR_COMPOSITE_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_EDITOR_COMPOSITE_QA_REPORT,
            width=max(160, int(width or 320)),
            height=max(120, int(height or 180)),
            duration_ms=max(500, int(duration_ms or 1000)),
            fps=max(4, int(fps or 12)),
            sample_time_ms=sample_time_ms,
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_qa_timeline_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = DEFAULT_MMD_TIMELINE_ENTRY_ID,
        out_dir: str = "",
        report_path: str = "",
        width: int = 360,
        height: int = 202,
        duration_ms: int = 2200,
        fps: int = 12,
        include_reports: bool = False,
    ) -> dict[str, Any]:
        payload = run_mmd_timeline_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_TIMELINE_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_TIMELINE_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_TIMELINE_QA_REPORT,
            width=max(240, int(width or 360)),
            height=max(135, int(height or 202)),
            duration_ms=max(2000, int(duration_ms or 2200)),
            fps=max(4, int(fps or 12)),
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "samples": [
                {
                    "ok": bool(row.get("ok")),
                    "output_ms": int(row.get("output_ms", 0) or 0),
                    "project_ms": int(row.get("project_ms", 0) or 0),
                    "expected_active_track_ids": list(row.get("expected_active_track_ids") or []),
                    "render_item_track_ids": list(row.get("render_item_track_ids") or []),
                    "export_delta": dict(row.get("export_delta") or {}),
                    "preview_frame": str(row.get("preview_frame") or ""),
                    "export_frame": str(row.get("export_frame") or ""),
                }
                for row in list(payload.get("samples") or [])
                if isinstance(row, Mapping)
            ],
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_qa_segment_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = DEFAULT_MMD_SEGMENT_TIMING_ENTRY_ID,
        out_dir: str = "",
        report_path: str = "",
        width: int = 360,
        height: int = 202,
        duration_ms: int = 3000,
        fps: int = 12,
        include_reports: bool = False,
    ) -> dict[str, Any]:
        payload = run_mmd_segment_timing_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_SEGMENT_TIMING_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_SEGMENT_TIMING_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_SEGMENT_TIMING_QA_REPORT,
            width=max(240, int(width or 360)),
            height=max(135, int(height or 202)),
            duration_ms=max(2600, int(duration_ms or 3000)),
            fps=max(4, int(fps or 12)),
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "samples": [
                {
                    "ok": bool(row.get("ok")),
                    "output_ms": int(row.get("output_ms", 0) or 0),
                    "project_ms": int(row.get("project_ms", 0) or 0),
                    "expected_active_track_ids": list(row.get("expected_active_track_ids") or []),
                    "render_item_track_ids": list(row.get("render_item_track_ids") or []),
                    "export_delta": dict(row.get("export_delta") or {}),
                    "preview_frame": str(row.get("preview_frame") or ""),
                    "export_frame": str(row.get("export_frame") or ""),
                }
                for row in list(payload.get("samples") or [])
                if isinstance(row, Mapping)
            ],
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_qa_render_queue_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
        out_dir: str = "",
        report_path: str = "",
        include_reports: bool = False,
    ) -> dict[str, Any]:
        payload = run_mmd_render_queue_wiring_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_RENDER_QUEUE_QA_REPORT,
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_qa_render_queue_export_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
        out_dir: str = "",
        report_path: str = "",
        width: int = 640,
        height: int = 360,
        duration_ms: int = 2400,
        fps: int = 24,
        include_reports: bool = False,
    ) -> dict[str, Any]:
        payload = run_mmd_render_queue_export_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_RENDER_QUEUE_EXPORT_QA_REPORT,
            width=max(320, int(width or 640)),
            height=max(180, int(height or 360)),
            duration_ms=max(1800, int(duration_ms or 2400)),
            fps=max(8, int(fps or 24)),
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_qa_long_project_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
        out_dir: str = "",
        report_path: str = "",
        width: int = 480,
        height: int = 270,
        duration_ms: int = 10000,
        fps: int = 12,
        include_reports: bool = False,
    ) -> dict[str, Any]:
        payload = run_mmd_long_project_export_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_RENDER_QUEUE_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_RENDER_QUEUE_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_LONG_PROJECT_EXPORT_QA_REPORT,
            width=max(320, int(width or 480)),
            height=max(180, int(height or 270)),
            duration_ms=max(8000, int(duration_ms or 10000)),
            fps=max(6, int(fps or 12)),
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "samples": [
                {
                    "ok": bool(row.get("ok")),
                    "output_ms": int(row.get("output_ms", 0) or 0),
                    "project_ms": int(row.get("project_ms", 0) or 0),
                    "expected_active_track_ids": list(row.get("expected_active_track_ids") or []),
                    "render_item_track_ids": list(row.get("render_item_track_ids") or []),
                    "export_delta": dict(row.get("export_delta") or {}),
                    "baseline_frame": str(row.get("baseline_frame") or ""),
                    "export_frame": str(row.get("export_frame") or ""),
                }
                for row in list(payload.get("samples") or [])
                if isinstance(row, Mapping)
            ],
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_qa_workflow_run(
        self,
        *,
        manifest: str = "",
        entry_id: str = "",
        out_dir: str = "",
        report_path: str = "",
        include_reports: bool = False,
    ) -> dict[str, Any]:
        from app.mmd.workflow_qa import (
            DEFAULT_MMD_WORKFLOW_ENTRY_ID,
            DEFAULT_MMD_WORKFLOW_QA_OUT_DIR,
            DEFAULT_MMD_WORKFLOW_QA_REPORT,
            run_mmd_workflow_qa,
        )

        payload = run_mmd_workflow_qa(
            manifest=manifest or DEFAULT_MMD_QA_MANIFEST,
            entry_id=entry_id or DEFAULT_MMD_WORKFLOW_ENTRY_ID,
            out_dir=Path(out_dir).expanduser().resolve() if out_dir else DEFAULT_MMD_WORKFLOW_QA_OUT_DIR,
            report_path=Path(report_path).expanduser().resolve() if report_path else DEFAULT_MMD_WORKFLOW_QA_REPORT,
        )
        result = {
            "ok": bool(payload.get("ok")),
            "entry_id": str(payload.get("entry_id") or ""),
            "manifest": str(payload.get("manifest") or ""),
            "report": str(payload.get("report") or ""),
            "outputs": dict(payload.get("outputs") or {}),
            "summary": dict(payload.get("summary") or {}),
            "checks": dict(payload.get("checks") or {}),
            "failures": [dict(row) for row in list(payload.get("failures") or []) if isinstance(row, Mapping)],
        }
        if include_reports:
            result["raw"] = dict(payload)
        return result

    def mmd_add_actor(
        self,
        *,
        path: str,
        start_ms: int = 0,
        duration_ms: int = 10000,
        motion_path: str = "",
        track_id: str = "",
    ) -> dict[str, Any]:
        owner = self.owner
        model_path = Path(path).expanduser().resolve()
        if owner is not None:
            add = getattr(owner, "_add_mmd_asset_to_timeline", None)
            if callable(add) and not track_id:
                payload = [model_path]
                if motion_path:
                    payload.append(Path(motion_path).expanduser().resolve())
                track = add(payload, start_ms=int(start_ms or 0))
                return {"track": dict(track or {}), "track_id": str((track or {}).get("id") or "")}
        from app.mmd.project_tracks import create_preview_mmd_track

        if not track_id:
            track_id = f"mmd_{len(self._mmd_tracks()) + 1:03d}"
        track = create_preview_mmd_track(
            model_path,
            track_id=str(track_id),
            start_ms=max(0, int(start_ms or 0)),
            duration_ms=max(1, int(duration_ms or 10000)),
            motion_path=motion_path or None,
        )
        self._mmd_tracks().append(track)
        self._mmd_refresh_owner(track, label="add mmd actor")
        return {"track": dict(track), "track_id": str(track.get("id") or "")}

    def mmd_delete_actor(self, *, track_id: str) -> dict[str, Any]:
        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        owner = self.owner
        delete = getattr(owner, "_delete_mmd_track", None) if owner is not None else None
        if callable(delete):
            return dict(delete(track, register=True) or {})
        try:
            self._mmd_tracks().remove(track)
        except ValueError:
            pass
        self._mmd_refresh_owner(None, label="delete mmd actor")
        return {"deleted": True, "track_id": str(track_id)}

    def mmd_duplicate_actor(
        self,
        *,
        track_id: str,
        start_ms: int | None = None,
        new_track_id: str = "",
    ) -> dict[str, Any]:
        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        owner = self.owner
        duplicate = getattr(owner, "_duplicate_mmd_track", None) if owner is not None else None
        if callable(duplicate):
            clone = duplicate(track, start_ms=start_ms, track_id=new_track_id, register=True)
            return {"track": dict(clone or {}), "track_id": str((clone or {}).get("id") or "")}

        from app.mmd.project_tracks import duplicate_mmd_track, next_mmd_track_id

        clone_id = str(new_track_id or next_mmd_track_id(self._mmd_tracks()))
        clone = duplicate_mmd_track(track, track_id=clone_id, start_ms=start_ms)
        self._mmd_tracks().append(clone)
        self._mmd_refresh_owner(clone, label="duplicate mmd actor")
        return {"track": dict(clone), "track_id": str(clone.get("id") or "")}

    def mmd_motion_list(self, *, track_id: str = "", model_path: str = "") -> dict[str, Any]:
        from app.mmd.editor_workflow import mmd_motion_library_for_track

        track = self._mmd_find_track(track_id) if track_id else None
        model = model_path or (str(track.get("model_path") or "") if isinstance(track, dict) else "")
        rows = mmd_motion_library_for_track(track, model_path=model)
        return {"track_id": track_id, "model_path": model, "motions": rows}

    def mmd_apply_motion(self, *, track_id: str, motion_path: str) -> dict[str, Any]:
        from app.mmd.editor_workflow import apply_mmd_motion_to_track

        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        apply_mmd_motion_to_track(track, motion_path)
        self._mmd_refresh_owner(track, label="apply mmd motion")
        return {"track_id": str(track.get("id") or ""), "motion_path": str(track.get("motion_path") or "")}

    def mmd_add_motion(self, *, track_id: str, motion_path: str) -> dict[str, Any]:
        from app.mmd.editor_workflow import add_mmd_motion_to_library, mmd_motion_library_for_track

        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        added_path = add_mmd_motion_to_library(track, motion_path)
        self._mmd_refresh_owner(track, label="add mmd motion")
        return {
            "track_id": str(track.get("id") or ""),
            "motion_path": str(added_path),
            "motions": mmd_motion_library_for_track(track),
        }

    def mmd_move_track(
        self,
        *,
        track_id: str,
        start_ms: int | None = None,
        delta_ms: int = 0,
    ) -> dict[str, Any]:
        from app.mmd.project_tracks import mmd_track_duration_ms, mmd_track_start_ms, set_mmd_track_range

        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        current_start = mmd_track_start_ms(track)
        duration = mmd_track_duration_ms(track)
        next_start = max(0, int(start_ms)) if start_ms is not None else max(0, current_start + int(delta_ms or 0))
        set_mmd_track_range(track, next_start, next_start + duration)
        self._mmd_refresh_owner(track, label="move mmd actor")
        return {
            "track_id": str(track.get("id") or ""),
            "start_ms": int(track.get("start_ms", 0) or 0),
            "end_ms": int(track.get("end_ms", 0) or 0),
        }

    def mmd_trim_track(
        self,
        *,
        track_id: str,
        start_ms: int | None = None,
        end_ms: int | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, Any]:
        from app.mmd.project_tracks import mmd_track_end_ms, mmd_track_start_ms, set_mmd_track_range

        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        start = mmd_track_start_ms(track) if start_ms is None else max(0, int(start_ms))
        if duration_ms is not None:
            end = start + max(1, int(duration_ms))
        else:
            end = mmd_track_end_ms(track) if end_ms is None else max(0, int(end_ms))
        set_mmd_track_range(track, start, end)
        self._mmd_refresh_owner(track, label="trim mmd actor")
        return {
            "track_id": str(track.get("id") or ""),
            "start_ms": int(track.get("start_ms", 0) or 0),
            "end_ms": int(track.get("end_ms", 0) or 0),
            "duration_ms": int(track.get("duration_ms", 0) or 0),
        }

    def mmd_apply_settings(
        self,
        *,
        track_id: str,
        playback: Mapping[str, Any] | None = None,
        render: Mapping[str, Any] | None = None,
        material: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.mmd.editor_workflow import apply_mmd_settings_to_track

        track = self._mmd_find_track(track_id)
        if track is None:
            raise ValueError(f"MMD track not found: {track_id}")
        apply_mmd_settings_to_track(track, playback=playback, render=render, material=material)
        self._mmd_refresh_owner(track, label="apply mmd settings")
        return {
            "track_id": str(track.get("id") or ""),
            "playback": dict(track.get("playback") or {}),
            "render": dict(track.get("render") or {}),
        }

    def mmd_open_editor(self, *, track_id: str) -> dict[str, Any]:
        owner = self.owner
        if owner is None:
            return {"opened": False, "reason": "no_owner"}
        method = getattr(owner, "_open_mmd_actor_editor", None)
        if not callable(method):
            return {"opened": False, "reason": "editor_not_available"}
        return dict(method(track_id) or {})
