"""Commercial readiness gate for VTuber/broadcast output."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


BROADCAST_RELEASE_READINESS_SCHEMA = "tigerstudio.broadcast.release_readiness.v1"

AREA_SPECS: tuple[tuple[str, str], ...] = (
    ("program_output_compositor", "Program Output compositor"),
    ("live_targets", "Live target output"),
    ("obs_free_video_call", "OBS-free video-call path"),
    ("capture_backends", "Capture backends"),
    ("secrets_recovery_diagnostics", "Secrets, recovery, diagnostics"),
    ("studio_ui_contract", "Studio UI contract"),
    ("real_platform_evidence", "Real platform evidence"),
)


def build_broadcast_release_readiness_report(root: str | Path = ".") -> dict[str, Any]:
    """Return a conservative broadcast/VTuber commercial-readiness report."""
    root_path = Path(root).resolve()
    areas = [
        _program_output_compositor_area(),
        _live_targets_area(),
        _obs_free_video_call_area(),
        _capture_backends_area(),
        _secrets_recovery_diagnostics_area(),
        _studio_ui_contract_area(),
        _real_platform_evidence_area(root_path),
    ]
    sale_blocking = [row for row in areas if row.get("sale_blocking")]
    alpha_blocking = [row for row in areas if row.get("alpha_blocking")]
    score = int(round(sum(int(row["score"]) for row in areas) / max(1, len(areas))))
    alpha_ready = not alpha_blocking
    commercial_ready = not sale_blocking
    return {
        "schema": BROADCAST_RELEASE_READINESS_SCHEMA,
        "ok": True,
        "score": score,
        "alpha_ready": alpha_ready,
        "commercial_ready": commercial_ready,
        "sale_ready": commercial_ready,
        "summary": {
            "areas": len(areas),
            "ready": len([row for row in areas if row["score"] >= 90]),
            "attention": len([row for row in areas if 70 <= row["score"] < 90]),
            "blocked": len([row for row in areas if row["score"] < 70]),
            "alpha_blocking": len(alpha_blocking),
            "sale_blocking": len(sale_blocking),
        },
        "areas": areas,
        "sale_blockers": [_blocker(row) for row in sale_blocking],
        "next_actions": [action for row in sale_blocking for action in row.get("actions", [])][:12],
        "positioning": {
            "safe_claim": "OBS-free Program Output recording/RTMP streaming foundation with optional OBS bridge.",
            "blocked_claim": "Fully verified production live broadcast suite until real platform/device evidence is attached.",
        },
    }


def format_broadcast_release_readiness_summary(report: Mapping[str, Any]) -> str:
    """Return a compact operator-facing summary."""
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    state = "commercial-ready" if report.get("commercial_ready") else "not commercial-ready"
    alpha = "alpha-ready" if report.get("alpha_ready") else "alpha-blocked"
    return (
        f"Broadcast readiness {int(report.get('score', 0) or 0)}/100: {state}, {alpha}; "
        f"sale blockers={int(summary.get('sale_blocking', 0) or 0)}, "
        f"alpha blockers={int(summary.get('alpha_blocking', 0) or 0)}."
    )


def _program_output_compositor_area() -> dict[str, Any]:
    from app.broadcast_scene import composite_broadcast_frame

    try:
        import numpy as np

        frame = np.zeros((2, 2, 4), dtype=np.uint8)
        frame[:, :] = [255, 0, 0, 128]
        out, diag = composite_broadcast_frame(
            {
                "canvas": {"width": 2, "height": 2, "background": [0, 0, 255, 255]},
                "sources": [{"id": "avatar", "type": "frame"}],
            },
            {"avatar": frame},
        )
        ok = bool(out.shape == (2, 2, 3) and diag.get("rendered_source_count") == 1)
    except Exception:
        ok = False
    return _area(
        "program_output_compositor",
        score=100 if ok else 45,
        summary="CPU Program Output compositor is available." if ok else "Program Output compositor smoke failed.",
        actions=[] if ok else ["Fix app.broadcast_scene composite_broadcast_frame smoke path."],
        evidence={"smoke_ok": ok},
        sale_blocking=not ok,
        alpha_blocking=not ok,
    )


def _live_targets_area() -> dict[str, Any]:
    from app.broadcast_output import live_target_preflight

    record = live_target_preflight(
        {"target_id": "record_file", "output_path": "broadcast_smoke.mp4", "include_audio": True, "audio_source_kind": "silence"},
        {"width": 1280, "height": 720, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )
    youtube = live_target_preflight(
        {"target_id": "youtube_live", "stream_key": "SECRET", "include_audio": True, "audio_source_kind": "silence"},
        {"width": 1280, "height": 720, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
    )
    ok = bool(record.get("ok") and youtube.get("ok") and "<stream_key>" in " ".join(str(p) for p in youtube.get("command", [])))
    return _area(
        "live_targets",
        score=100 if ok else 60,
        summary="Record and RTMP live target preflight paths are available." if ok else "Record/RTMP preflight has blockers.",
        actions=[] if ok else ["Fix broadcast live_target_preflight for record and RTMP targets."],
        evidence={
            "record_ok": bool(record.get("ok")),
            "rtmp_ok": bool(youtube.get("ok")),
            "stream_key_redacted": "<stream_key>" in " ".join(str(p) for p in youtube.get("command", [])),
        },
        sale_blocking=not ok,
        alpha_blocking=not ok,
    )


def _obs_free_video_call_area() -> dict[str, Any]:
    from app.broadcast_virtual_camera import virtual_camera_output_plan

    plan = virtual_camera_output_plan(
        {},
        installed_backends={"obs_virtual_camera": {"available": True, "executable": "C:/OBS/obs64.exe"}},
    )
    ok = bool(plan.get("selected_backend") == "program_output_window_share" and plan.get("obs_optional") is True)
    return _area(
        "obs_free_video_call",
        score=100 if ok else 65,
        summary="Discord/video-call output defaults to OBS-free Program Output window sharing." if ok else "Video-call output may incorrectly prefer OBS.",
        actions=[] if ok else ["Keep Program Output window share as the default video-call target."],
        evidence={
            "selected_backend": plan.get("selected_backend"),
            "default_backend_policy": plan.get("default_backend_policy"),
            "obs_optional": bool(plan.get("obs_optional")),
        },
        sale_blocking=not ok,
        alpha_blocking=not ok,
    )


def _capture_backends_area() -> dict[str, Any]:
    from app.broadcast_capture_backend import broadcast_capture_backend_plan

    scene = {
        "sources": [
            {"id": "frame", "type": "frame"},
            {"id": "image", "type": "image", "settings": {"path": "logo.png"}},
            {"id": "camera", "type": "camera"},
            {"id": "display", "type": "display_capture", "settings": {"region": {"left": 0, "top": 0, "width": 16, "height": 16}}},
        ]
    }
    plan = broadcast_capture_backend_plan(
        scene,
        dependency_availability={"opencv": True, "mss": True, "pillow": True},
    )
    actual_backends = {row.get("backend") for row in plan.get("sources", [])}
    required = {"frame_map", "image_file", "opencv_camera", "screen_region"}
    ok = bool(plan.get("ok") and required.issubset(actual_backends))
    return _area(
        "capture_backends",
        score=92 if ok else 65,
        summary="Image, camera, explicit screen-region, and external frame-map capture contracts are implemented." if ok else "Capture backend contracts are incomplete.",
        actions=[] if ok else ["Complete image/camera/screen-region capture source resolution."],
        evidence={
            "plan_ok": bool(plan.get("ok")),
            "backends": sorted(str(item) for item in actual_backends),
            "obs_required": False,
        },
        sale_blocking=not ok,
        alpha_blocking=not ok,
    )


def _secrets_recovery_diagnostics_area() -> dict[str, Any]:
    from app.broadcast_output import LiveTargetProfile
    from app.broadcast_troubleshooting import build_live_target_troubleshooting

    settings = LiveTargetProfile.from_mapping({"target_id": "twitch", "stream_key": "SECRET"}).to_project_settings()
    troubleshooting = build_live_target_troubleshooting(
        {"target_id": "youtube_live"},
        {"state": "error", "platform_error_kind": "platform_auth", "stderr_tail": "403"},
    )
    ok = bool("stream_key" not in settings and troubleshooting.get("panel", {}).get("items"))
    return _area(
        "secrets_recovery_diagnostics",
        score=100 if ok else 62,
        summary="Stream keys stay session-only and troubleshooting exposes clickable panel data." if ok else "Secret storage or diagnostics contract is incomplete.",
        actions=[] if ok else ["Fix stream-key persistence and troubleshooting panel payloads."],
        evidence={
            "stream_key_saved": "stream_key" in settings,
            "panel_items": len(troubleshooting.get("panel", {}).get("items", []) or []),
        },
        sale_blocking=not ok,
        alpha_blocking=not ok,
    )


def _studio_ui_contract_area() -> dict[str, Any]:
    from app.vtuber.broadcast_studio_layout import build_vtuber_broadcast_studio_layout

    layout = build_vtuber_broadcast_studio_layout(
        source_name="performance.mp4",
        avatar_name="avatar.vrm",
        live_target={"target_id": "discord_video_call", "label": "Discord / Video Call Output", "output_kind": "window_share"},
    )
    live2d_layout = build_vtuber_broadcast_studio_layout(
        source_name="performance.mp4",
        avatar_name="character.model3.json",
        avatar_target={
            "id": "live2d:0:0",
            "kind": "live2d_actor_clip",
            "label": "Live2D Actor",
            "name": "character.model3.json",
            "direct_key_baking": True,
        },
        live_target={"target_id": "record_file", "label": "Local MP4", "output_kind": "recording"},
    )
    ok = bool(
        layout.get("program", {}).get("performance_source_direct_output") is False
        and layout.get("diagnostics", {}).get("live_target_program_output_only") is True
        and live2d_layout.get("avatar_target", {}).get("live_target_output") is True
        and live2d_layout.get("diagnostics", {}).get("live2d_live_target_supported") is True
    )
    return _area(
        "studio_ui_contract",
        score=95 if ok else 55,
        summary="Studio layout separates Program Output, Source Tracking, Avatar Mapping, controls, and Live Target for VRM/Live2D targets." if ok else "Studio layout may leak tracking source into output or miss a Live2D Live Target route.",
        actions=[] if ok else ["Fix VTuber Studio layout so Performance Source is input-only."],
        evidence={
            "performance_source_direct_output": layout.get("program", {}).get("performance_source_direct_output"),
            "live2d_live_target_supported": live2d_layout.get("diagnostics", {}).get("live2d_live_target_supported"),
            "live2d_live_target_output": live2d_layout.get("avatar_target", {}).get("live_target_output"),
            "region_count": len(layout.get("regions", []) or []),
        },
        sale_blocking=not ok,
        alpha_blocking=not ok,
    )


def _real_platform_evidence_area(root: Path) -> dict[str, Any]:
    artifact = _load_json(root / "debugCapture" / "broadcast_platform_e2e_qa.json")
    checklist: dict[str, Any] = {}
    try:
        from app.broadcast_platform_e2e import build_broadcast_platform_evidence_checklist

        checklist = build_broadcast_platform_evidence_checklist(root)
    except Exception:
        checklist = {}
    summary = checklist.get("summary") if isinstance(checklist.get("summary"), Mapping) else (
        artifact.get("summary") if isinstance(artifact.get("summary"), Mapping) else {}
    )
    passed = int(summary.get("passed", 0) or 0)
    required = int(summary.get("required", 4) or 4)
    real_evidence = bool(checklist.get("real_platform_evidence", artifact.get("real_platform_evidence")))
    ready = bool(checklist.get("sale_ready") or checklist.get("commercial_ready"))
    score = 100 if ready else 78 if artifact else 72
    actions = []
    if not ready:
        checklist_actions = [str(action) for action in list(checklist.get("actions") or []) if str(action).strip()]
        pending = [
            row
            for row in artifact.get("checks", [])
            if isinstance(row, Mapping) and row.get("required_for_sale") and not row.get("ok")
        ] if artifact else []
        if checklist_actions:
            actions.extend(checklist_actions)
        elif pending:
            actions.extend(str(row.get("primary_cta") or row.get("action") or row.get("label") or row.get("id")) for row in pending)
        else:
            actions.extend(
                [
                    "Run tools/qa_broadcast_platform_e2e.py --allow-pending-platform to generate local Program Output evidence.",
                    "Run a private/unlisted RTMP ingest test, then click Register RTMP in VTuber Studio.",
                    "Open the private/unlisted YouTube viewer or preview page, then click Register YouTube View.",
                ]
            )
    return _area(
        "real_platform_evidence",
        score=score,
        summary=(
            str(
                checklist.get("operator_summary")
                or (
                    f"real platform evidence passed {passed}/{required}."
                    if artifact
                    else "No real broadcast platform evidence artifact is attached yet."
                )
            )
        ),
        actions=actions,
        evidence={
            "artifact": str(root / "debugCapture" / "broadcast_platform_e2e_qa.json"),
            "artifact_present": bool(artifact),
            "real_platform_evidence": real_evidence,
            "passed": passed,
            "required": required,
            "checklist_status": str(checklist.get("status_text") or ""),
            "operator_focus": dict(checklist.get("operator_focus") or {}) if isinstance(checklist.get("operator_focus"), Mapping) else {},
        },
        sale_blocking=not ready,
        alpha_blocking=False,
    )


def _area(
    area_id: str,
    *,
    score: int,
    summary: str,
    actions: list[str],
    evidence: Mapping[str, Any],
    sale_blocking: bool,
    alpha_blocking: bool,
) -> dict[str, Any]:
    score = max(0, min(100, int(score)))
    if score >= 90:
        level = "ready"
    elif score >= 70:
        level = "attention"
    else:
        level = "blocked"
    return {
        "id": area_id,
        "label": dict(AREA_SPECS).get(area_id, area_id),
        "score": score,
        "level": level,
        "summary": summary,
        "actions": list(actions),
        "evidence": dict(evidence),
        "sale_blocking": bool(sale_blocking),
        "alpha_blocking": bool(alpha_blocking),
    }


def _blocker(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "area": row.get("id"),
        "label": row.get("label"),
        "summary": row.get("summary"),
        "actions": list(row.get("actions", []) or []),
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
