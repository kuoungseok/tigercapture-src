"""Evidence helpers for conservative NLE readiness scoring."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _action_set(action_ids: Sequence[str] | None) -> set[str]:
    return {str(action_id) for action_id in (action_ids or ()) if str(action_id or "").strip()}


def _clips(snapshot: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for track in list(snapshot.get(key) or []):
        if not isinstance(track, Mapping):
            continue
        for clip in list(track.get("clips") or []):
            if isinstance(clip, Mapping):
                rows.append(clip)
    return rows


def _media_kind_counts(media_pool: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in media_pool:
        kind = str(item.get("kind") or "unknown")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def build_nle_evidence_report(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_ids: Sequence[str] | None = None,
    evidence_level: str = "project_snapshot",
) -> dict[str, Any]:
    """Return feature evidence without claiming Premiere/Resolve parity.

    The report can be generated from a real editor snapshot or from the
    synthetic validation corpus used by QA.  Synthetic evidence is useful for
    guarding action contracts, but it deliberately keeps the professional NLE
    claim blocked until real long projects are supplied.
    """

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), Mapping) else {}
    media_pool = [row for row in list(snapshot.get("media_pool") or []) if isinstance(row, Mapping)]
    video_clips = _clips(snapshot, "video_tracks")
    audio_clips = _clips(snapshot, "audio_tracks")
    action_set = _action_set(action_ids)

    duration_ms = _int(snapshot.get("duration_ms"), 0)
    video_count = _int(summary.get("video_clip_count"), len(video_clips))
    audio_count = _int(summary.get("audio_clip_count"), len(audio_clips))
    media_count = _int(summary.get("media_pool_count"), len(media_pool))
    kind_counts = _media_kind_counts(media_pool)
    proxy_ready = sum(1 for row in media_pool if str(row.get("proxy_state") or "").lower() in {"ready", "active", "fresh"})
    relink_candidates = sum(1 for row in media_pool if _int(row.get("relink_candidate_count"), 0) > 0)

    source_record_actions = {
        "source_record.workbench",
        "source_record.edit_decision_preview",
        "source_monitor.load_media",
        "source_monitor.set_in",
        "source_monitor.set_out",
        "record_monitor.set_in",
        "record_monitor.set_out",
        "source_record.patch_matrix",
        "timeline.three_point_insert",
        "timeline.three_point_overwrite",
    }
    edit_actions = {
        "timeline.split",
        "timeline.trim_to_playhead",
        "timeline.ripple_delete",
        "timeline.lift",
        "timeline.extract",
        "timeline.insert_clipboard",
        "timeline.overwrite_clipboard",
        "timeline.cleanup_edges",
        "timeline.undo_health",
    }
    multicam_actions = {
        "timeline.multicam.summary",
        "timeline.multicam.create_group",
        "timeline.multicam.sync_plan",
        "timeline.multicam.switch_plan",
        "timeline.multicam.angle_bins",
        "timeline.multicam.set_active_angle",
        "timeline.multicam.switcher_workbench",
        "timeline.multicam.export_handoff",
    }
    project_bin_actions = {
        "project_bin.workbench",
        "project_bin.batch_plan",
        "project_bin.conform_report",
        "project_bin.proxy_plan",
        "project_bin.proxy_health",
        "media.summary",
        "project.snapshot",
    }
    proxy_actions = {"project_bin.proxy_plan", "project_bin.proxy_health", "media.summary", "project.snapshot"}

    multicam_angles = {
        str(row.get("camera_id") or row.get("angle") or row.get("source_path") or row.get("name") or "")
        for row in video_clips
    }
    multicam_angles.discard("")
    try:
        from app.nle_multicam import multicam_contract_evidence

        multicam_contract = multicam_contract_evidence(snapshot, action_ids=tuple(action_set))
    except Exception:
        multicam_contract = {
            "ok": False,
            "required_actions": sorted(multicam_actions),
            "available_actions": sorted(multicam_actions & action_set),
            "angle_count": len(multicam_angles),
            "switch_count": 0,
            "sync_plan_ready": False,
            "sync_methods": [],
            "angle_bins_ready": False,
            "angle_bin_count": 0,
            "angle_gap_count": 0,
            "switcher_workbench_ready": False,
            "export_handoff_ready": False,
            "group_count": 0,
        }
    try:
        from app.nle_source_record import source_record_contract_evidence

        source_record_contract = source_record_contract_evidence(action_ids=tuple(action_set))
    except Exception:
        source_record_contract = {
            "ok": False,
            "required_actions": sorted(source_record_actions),
            "available_actions": sorted(source_record_actions & action_set),
            "edit_decision_preview_ready": False,
        }
    try:
        from app.nle_project_bin import (
            build_project_bin_proxy_health_board,
            build_project_bin_proxy_plan,
            project_bin_contract_evidence,
        )

        project_bin_contract = project_bin_contract_evidence(snapshot, action_ids=tuple(action_set))
        proxy_plan = build_project_bin_proxy_plan(snapshot)
        proxy_health = build_project_bin_proxy_health_board(snapshot)
    except Exception:
        project_bin_contract = {
            "ok": False,
            "required_actions": sorted(project_bin_actions),
            "available_actions": sorted(project_bin_actions & action_set),
            "media_count": media_count,
            "bin_count": 0,
            "offline_count": 0,
            "relink_candidate_count": relink_candidates,
            "batch_plan_ready": False,
            "batch_operation_count": 0,
            "batch_operation_counts": {},
            "conform_report_ready": False,
            "conform_report_summary": {},
        }
        proxy_plan = {
            "ready": False,
            "proxy_ready": False,
            "summary": {},
            "commands": {},
            "readiness": {},
        }
        proxy_health = {
            "ready": False,
            "summary": {},
            "commands": {},
            "readiness": {},
        }
    long_stress = snapshot.get("long_project_stress") if isinstance(snapshot.get("long_project_stress"), Mapping) else {}
    long_stress_summary = long_stress.get("summary") if isinstance(long_stress.get("summary"), Mapping) else {}
    long_stress_ok = bool(long_stress.get("ok"))
    timeline_stress = snapshot.get("nle_timeline_stress") if isinstance(snapshot.get("nle_timeline_stress"), Mapping) else {}
    timeline_stress_summary = timeline_stress.get("summary") if isinstance(timeline_stress.get("summary"), Mapping) else {}
    timeline_stress_ok = bool(timeline_stress.get("ok") or timeline_stress.get("claim_ready"))
    try:
        from app.nle_timeline_stress import build_nle_undo_health_matrix

        undo_health = build_nle_undo_health_matrix(timeline_stress)
    except Exception:
        undo_health = {"ready": False, "summary": {}, "blockers": []}
    real_corpus = snapshot.get("nle_real_project_corpus") if isinstance(snapshot.get("nle_real_project_corpus"), Mapping) else {}
    real_corpus_summary = real_corpus.get("summary") if isinstance(real_corpus.get("summary"), Mapping) else {}
    real_corpus_ready = bool(real_corpus.get("claim_ready") or real_corpus.get("real_world_corpus"))

    rows = {
        "source_record_monitor_3_point": {
            "ok": bool(source_record_contract.get("ok")),
            "evidence_level": evidence_level,
            "workbench_contract": True,
            "required_actions": list(source_record_contract.get("required_actions") or sorted(source_record_actions)),
            "available_actions": list(source_record_contract.get("available_actions") or sorted(source_record_actions & action_set)),
            "edit_decision_preview_ready": bool(source_record_contract.get("edit_decision_preview_ready")),
            "patch_matrix_ready": bool(source_record_contract.get("patch_matrix_ready")),
        },
        "multicam": {
            "ok": bool(multicam_contract.get("ok")),
            "evidence_level": evidence_level,
            "angle_count": len(multicam_angles),
            "contract_angle_count": _int(multicam_contract.get("angle_count"), 0),
            "switch_count": _int(multicam_contract.get("switch_count"), 0),
            "group_count": _int(multicam_contract.get("group_count"), 0),
            "sync_plan_ready": bool(multicam_contract.get("sync_plan_ready")),
            "sync_methods": list(multicam_contract.get("sync_methods") or []),
            "angle_bins_ready": bool(multicam_contract.get("angle_bins_ready")),
            "angle_bin_count": _int(multicam_contract.get("angle_bin_count"), 0),
            "angle_gap_count": _int(multicam_contract.get("angle_gap_count"), 0),
            "switcher_workbench_ready": bool(multicam_contract.get("switcher_workbench_ready")),
            "export_handoff_ready": bool(multicam_contract.get("export_handoff_ready")),
            "video_clip_count": video_count,
            "required_actions": list(multicam_contract.get("required_actions") or sorted(multicam_actions)),
            "available_actions": list(multicam_contract.get("available_actions") or sorted(multicam_actions & action_set)),
        },
        "proxy_media_management": {
            "ok": media_count >= 12 and proxy_ready >= 6 and bool(proxy_plan.get("proxy_ready")) and bool(proxy_health.get("ready")) and proxy_actions <= action_set,
            "evidence_level": evidence_level,
            "media_pool_count": media_count,
            "proxy_ready_count": proxy_ready,
            "kind_counts": kind_counts,
            "required_actions": sorted(proxy_actions),
            "available_actions": sorted(proxy_actions & action_set),
            "proxy_plan_ready": bool(proxy_plan.get("proxy_ready")),
            "proxy_plan_summary": dict(proxy_plan.get("summary") or {}),
            "proxy_plan_commands": dict(proxy_plan.get("commands") or {}),
            "proxy_health_ready": bool(proxy_health.get("ready")),
            "proxy_health_summary": dict(proxy_health.get("summary") or {}),
            "proxy_health_commands": dict(proxy_health.get("commands") or {}),
        },
        "conform_relink_project_bin": {
            "ok": bool(project_bin_contract.get("ok")) and (kind_counts.get("video", 0) >= 6 or relink_candidates >= 2),
            "evidence_level": evidence_level,
            "media_pool_count": media_count,
            "relink_candidate_count": relink_candidates,
            "kind_counts": kind_counts,
            "project_bin_workbench": True,
            "project_bin_contract": dict(project_bin_contract),
            "batch_plan_ready": bool(project_bin_contract.get("batch_plan_ready")),
            "batch_operation_count": _int(project_bin_contract.get("batch_operation_count"), 0),
            "conform_report_ready": bool(project_bin_contract.get("conform_report_ready")),
            "conform_report_summary": dict(project_bin_contract.get("conform_report_summary") or {}),
        },
        "undo_edge_case_qa": {
            "ok": edit_actions <= action_set,
            "evidence_level": evidence_level,
            "required_actions": sorted(edit_actions),
            "available_actions": sorted(edit_actions & action_set),
            "timeline_fuzzer_ready": timeline_stress_ok,
            "timeline_fuzzer_summary": dict(timeline_stress_summary),
            "timeline_fuzzer_blockers": list(timeline_stress.get("blockers") or []),
            "undo_health_ready": bool(undo_health.get("ready")),
            "undo_health_summary": dict(undo_health.get("summary") or {}),
            "undo_health_blockers": list(undo_health.get("blockers") or []),
        },
        "long_large_project_validation": {
            "ok": (duration_ms >= 30 * 60_000 and video_count >= 90 and audio_count >= 20) or long_stress_ok or real_corpus_ready,
            "evidence_level": evidence_level,
            "duration_ms": duration_ms,
            "video_clip_count": video_count,
            "audio_clip_count": audio_count,
            "long_project_stress_ok": long_stress_ok,
            "long_project_stress_summary": dict(long_stress_summary),
            "real_project_corpus_ready": real_corpus_ready,
            "real_project_corpus_summary": dict(real_corpus_summary),
            "real_project_corpus_blockers": list(real_corpus.get("blockers") or []),
        },
    }
    real_world_corpus = evidence_level == "real_project_corpus" or real_corpus_ready
    return {
        "schema": "tigerstudio.nle_evidence.v1",
        "evidence_level": evidence_level,
        "real_world_corpus": real_world_corpus,
        "rows": rows,
        "summary": {
            "checks": len(rows),
            "passing": sum(1 for row in rows.values() if bool(row.get("ok"))),
            "duration_ms": duration_ms,
            "video_clip_count": video_count,
            "audio_clip_count": audio_count,
            "media_pool_count": media_count,
            "registered_action_count": len(action_set),
            "long_project_stress_ok": long_stress_ok,
            "timeline_fuzzer_ready": timeline_stress_ok,
            "undo_health_ready": bool(undo_health.get("ready")),
            "real_project_corpus_ready": real_corpus_ready,
        },
    }


def build_synthetic_nle_validation_snapshot(*, action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    """Build a deterministic long-project contract corpus for QA.

    This is intentionally synthetic.  It raises implementation confidence for
    action contracts and data-model readiness, while the readiness report still
    blocks a full professional NLE claim until real footage projects are used.
    """

    duration_ms = 45 * 60_000
    media_pool: list[dict[str, Any]] = []
    for idx in range(36):
        kind = "video" if idx < 24 else "audio"
        media_pool.append(
            {
                "id": f"media_{idx + 1}",
                "path": f"qa_media/cam_{idx % 4 + 1:02d}_{idx + 1:03d}.{'mp4' if kind == 'video' else 'wav'}",
                "name": f"cam_{idx % 4 + 1:02d}_{idx + 1:03d}",
                "kind": kind,
                "proxy_state": "ready" if idx < 28 else "stale",
                "relink_candidate_count": 2 if idx in {3, 7, 15} else 0,
                "bin": "A-roll" if idx % 2 == 0 else "B-roll",
            }
        )

    video_tracks: list[dict[str, Any]] = []
    clip_id = 1
    for track_idx in range(4):
        clips: list[dict[str, Any]] = []
        for local_idx in range(30):
            start = local_idx * 90_000 + track_idx * 4_000
            end = min(duration_ms, start + 75_000)
            if end <= start:
                continue
            clips.append(
                {
                    "id": clip_id,
                    "index": local_idx,
                    "source_path": media_pool[(local_idx + track_idx) % 24]["path"],
                    "name": f"angle_{track_idx + 1}_{local_idx + 1}",
                    "camera_id": f"cam_{track_idx + 1}",
                    "timeline_in_ms": start,
                    "timeline_out_ms": end,
                    "duration_ms": end - start,
                    "source_in_ms": 0,
                    "source_out_ms": end - start,
                }
            )
            clip_id += 1
        video_tracks.append({"id": track_idx + 1, "index": track_idx, "locked": False, "muted": False, "clips": clips})

    audio_tracks: list[dict[str, Any]] = []
    audio_id = 1
    for track_idx in range(3):
        clips = []
        for local_idx in range(12):
            start = local_idx * 210_000 + track_idx * 18_000
            end = min(duration_ms, start + 180_000)
            if end <= start:
                continue
            clips.append(
                {
                    "id": audio_id,
                    "index": local_idx,
                    "source_path": media_pool[24 + ((local_idx + track_idx) % 12)]["path"],
                    "name": f"audio_{track_idx + 1}_{local_idx + 1}",
                    "offset_ms": start,
                    "end_ms": end,
                    "duration_ms": end - start,
                }
            )
            audio_id += 1
        audio_tracks.append({"id": track_idx + 1, "index": track_idx, "locked": False, "muted": False, "clips": clips})

    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "source": "Tiger Studio synthetic NLE validation corpus",
        "project_path": "debugCapture/nle_synthetic_validation.tgp",
        "duration_ms": duration_ms,
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "media_pool": media_pool,
        "markers": [{"id": "m_intro", "ms": 0, "label": "Intro"}, {"id": "m_outro", "ms": duration_ms - 30_000, "label": "Outro"}],
        "selected_clips": [],
    }
    snapshot["summary"] = {
        "video_track_count": len(video_tracks),
        "audio_track_count": len(audio_tracks),
        "video_clip_count": sum(len(track["clips"]) for track in video_tracks),
        "audio_clip_count": sum(len(track["clips"]) for track in audio_tracks),
        "media_pool_count": len(media_pool),
        "marker_count": len(snapshot["markers"]),
        "selected_clip_count": 0,
    }
    snapshot["nle_evidence"] = build_nle_evidence_report(
        snapshot,
        action_ids=action_ids,
        evidence_level="synthetic_contract_corpus",
    )
    return snapshot
