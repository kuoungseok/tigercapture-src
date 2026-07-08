"""End-to-end evidence builder for broadcast output."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Mapping

import numpy as np


BROADCAST_PLATFORM_E2E_SCHEMA = "tigerstudio.broadcast.platform_e2e.v1"
BROADCAST_PLATFORM_EVIDENCE_SCHEMA = "tigerstudio.broadcast.platform_evidence_register.v1"
BROADCAST_PLATFORM_CHECKLIST_SCHEMA = "tigerstudio.broadcast.platform_evidence_checklist.v1"
BROADCAST_YOUTUBE_QUICKSTART_SCHEMA = "tigerstudio.broadcast.youtube_evidence_quickstart.v1"

RecordSmokeRunner = Callable[[Path], dict[str, Any]]


def build_broadcast_platform_e2e_report(
    root: str | Path = ".",
    *,
    run_record_smoke: bool = True,
    record_smoke_runner: RecordSmokeRunner | None = None,
    live2d_record_smoke_runner: RecordSmokeRunner | None = None,
) -> dict[str, Any]:
    """Build local and manual evidence rows for sale-readiness review."""
    root_path = Path(root).resolve()
    checks: list[dict[str, Any]] = []

    if run_record_smoke:
        runner = record_smoke_runner or run_record_file_smoke
        record = runner(root_path)
    else:
        record = {
            "ok": False,
            "skipped": True,
            "reason": "record smoke was not requested",
        }
    checks.append(
        {
            "id": "record_file_local",
            "label": "Record Program Output to local MP4",
            "kind": "local_runtime",
            "ok": bool(record.get("ok")),
            "required_for_sale": True,
            "evidence": record,
        }
    )

    if run_record_smoke:
        live2d_runner = live2d_record_smoke_runner or run_live2d_record_file_smoke
        live2d_record = live2d_runner(root_path)
    else:
        live2d_record = {
            "ok": False,
            "skipped": True,
            "reason": "record smoke was not requested",
        }
    checks.append(
        {
            "id": "live2d_record_file_local",
            "label": "Record Live2D Program Output to local MP4",
            "kind": "local_runtime",
            "ok": bool(live2d_record.get("ok")),
            "required_for_sale": True,
            "evidence": live2d_record,
        }
    )

    capture = _run_synthetic_capture_composite_smoke()
    checks.append(
        {
            "id": "capture_composite_local",
            "label": "Resolve capture source and composite Program Output",
            "kind": "local_runtime",
            "ok": bool(capture.get("ok")),
            "required_for_sale": True,
            "evidence": capture,
        }
    )

    checks.extend(
        [
            _manual_check(
                "private_rtmp_ingest",
                "Private/unlisted RTMP ingest test",
                "Run YouTube, Twitch, or Custom RTMP with redacted stream key evidence.",
            ),
            _manual_check(
                "youtube_unlisted_viewer_playback",
                "YouTube private/unlisted viewer playback test",
                "Open the private/unlisted YouTube watch or preview page and verify Program Output playback.",
            ),
            _manual_check(
                "discord_window_share",
                "Discord/video-call Program Output window-share test",
                "Join a test call and verify only Program Output is shared, not Performance Source.",
                required_for_sale=False,
            ),
        ]
    )
    required_checks = [row for row in checks if row.get("required_for_sale", True)]
    passed = len([row for row in required_checks if row.get("ok")])
    required = len(required_checks)
    real_platform_evidence = all(row.get("ok") for row in required_checks) and any(row.get("kind") == "real_platform" for row in required_checks)
    return {
        "schema": BROADCAST_PLATFORM_E2E_SCHEMA,
        "ok": all(row.get("ok") for row in checks if row.get("kind") == "local_runtime"),
        "real_platform_evidence": real_platform_evidence,
        "summary": {
            "passed": passed,
            "required": required,
            "pending": required - passed,
            "local_runtime_passed": len([row for row in checks if row.get("kind") == "local_runtime" and row.get("ok")]),
            "manual_platform_pending": len([row for row in required_checks if row.get("kind") == "manual_platform" and not row.get("ok")]),
        },
        "checks": checks,
        "generated_at": time.time(),
    }


def register_manual_platform_evidence(
    root: str | Path,
    *,
    check_id: str,
    platform: str,
    evidence_path: str = "",
    notes: str = "",
    confirm_redacted: bool = False,
    artifact_path: str | Path = "debugCapture/broadcast_platform_e2e_qa.json",
    refresh_readiness: bool = True,
) -> dict[str, Any]:
    """Mark a manual platform check complete after the operator supplies evidence."""
    if not confirm_redacted:
        raise ValueError("confirm_redacted is required before registering platform evidence")
    evidence = {
        "platform": str(platform or "").strip(),
        "evidence_path": str(evidence_path or "").strip(),
        "notes": str(notes or "").strip(),
        "redacted": True,
        "registered_at": time.time(),
    }
    _validate_evidence_payload(evidence)
    root_path = Path(root).resolve()
    path = root_path / Path(artifact_path)
    if path.exists():
        report = _load_report(path)
    else:
        report = build_broadcast_platform_e2e_report(root_path, run_record_smoke=False)
    report = _ensure_current_manual_checks(report)
    checks = list(report.get("checks") or [])
    target_id = str(check_id or "").strip()
    updated = False
    for idx, row in enumerate(checks):
        if not isinstance(row, Mapping) or str(row.get("id") or "") != target_id:
            continue
        if row.get("kind") not in {"manual_platform", "real_platform"}:
            raise ValueError(f"check is not a manual platform evidence slot: {target_id}")
        merged = dict(row)
        merged["kind"] = "real_platform"
        merged["ok"] = True
        merged["evidence"] = evidence
        checks[idx] = merged
        updated = True
        break
    if not updated:
        raise ValueError(f"platform evidence check not found: {target_id}")
    report["checks"] = checks
    _refresh_summary(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    readiness_refresh: dict[str, Any] = {"ok": False, "skipped": True}
    if refresh_readiness:
        try:
            from app.broadcast_evidence_refresh import refresh_broadcast_evidence_readiness_artifacts

            readiness_refresh = refresh_broadcast_evidence_readiness_artifacts(root_path)
        except Exception as exc:
            readiness_refresh = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "broadcast_artifact": str(root_path / "debugCapture" / "broadcast_release_readiness_qa.json"),
                "final_artifact": str(root_path / "debugCapture" / "final_product_readiness_qa.json"),
            }
    return {
        "schema": BROADCAST_PLATFORM_EVIDENCE_SCHEMA,
        "artifact": str(path),
        "check_id": target_id,
        "registered": True,
        "report": report,
        "readiness_refresh": readiness_refresh,
    }


def preserve_registered_platform_evidence(
    report: Mapping[str, Any],
    existing_report: Mapping[str, Any],
) -> dict[str, Any]:
    """Copy already registered real platform rows into a freshly built report."""

    merged = dict(report or {})
    checks = [dict(row) for row in list(merged.get("checks") or []) if isinstance(row, Mapping)]
    existing_checks = {
        str(row.get("id") or ""): dict(row)
        for row in list(existing_report.get("checks") or [])
        if isinstance(row, Mapping)
    }
    changed = False
    for idx, row in enumerate(checks):
        check_id = str(row.get("id") or "")
        prior = existing_checks.get(check_id)
        if not prior:
            continue
        if prior.get("kind") != "real_platform" or not prior.get("ok"):
            continue
        evidence = prior.get("evidence")
        if not isinstance(evidence, Mapping) or not evidence.get("redacted"):
            continue
        preserved = dict(row)
        preserved["kind"] = "real_platform"
        preserved["ok"] = True
        preserved["evidence"] = dict(evidence)
        checks[idx] = preserved
        changed = True
    merged["checks"] = checks
    if changed:
        _refresh_summary(merged)
    return merged


def build_broadcast_platform_evidence_checklist(
    root: str | Path = ".",
    *,
    artifact_path: str | Path = "debugCapture/broadcast_platform_e2e_qa.json",
) -> dict[str, Any]:
    """Return an operator-facing checklist for sale-blocking platform evidence.

    This is intentionally read-only and does not run FFmpeg or start streams.
    The Studio UI can call it often without triggering expensive checks.
    """
    root_path = Path(root).resolve()
    path = root_path / Path(artifact_path)
    artifact_present = path.exists()
    report = _load_report(path) if artifact_present else build_broadcast_platform_e2e_report(root_path, run_record_smoke=False)
    report = _ensure_current_manual_checks(report)
    checks = [dict(row) for row in list(report.get("checks") or []) if isinstance(row, Mapping)]
    items = [_checklist_item(row) for row in checks]
    required_items = [row for row in items if row.get("required_for_sale")]
    pending_required = [row for row in required_items if not row.get("ok")]
    manual_pending = [row for row in pending_required if row.get("kind") == "manual_platform"]
    local_pending = [row for row in pending_required if row.get("kind") == "local_runtime"]
    passed = len([row for row in required_items if row.get("ok")])
    required = len(required_items)
    operator_focus = manual_pending[0] if manual_pending else (local_pending[0] if local_pending else None)
    sale_ready = bool(report.get("real_platform_evidence") and required > 0 and passed >= required)
    next_actions = [_checklist_action(row) for row in pending_required]
    youtube_flow = _youtube_only_flow(items, operator_focus=operator_focus or {})
    return {
        "schema": BROADCAST_PLATFORM_CHECKLIST_SCHEMA,
        "artifact": str(path),
        "artifact_present": artifact_present,
        "ok": bool(report.get("ok")),
        "sale_ready": sale_ready,
        "commercial_ready": sale_ready,
        "real_platform_evidence": bool(report.get("real_platform_evidence")),
        "summary": {
            "passed": passed,
            "required": required,
            "pending": max(0, required - passed),
            "local_runtime_passed": len([row for row in items if row.get("kind") == "local_runtime" and row.get("ok")]),
            "local_runtime_required": len([row for row in items if row.get("kind") == "local_runtime"]),
            "manual_platform_pending": len(manual_pending),
            "manual_platform_required": len([row for row in items if row.get("kind") in {"manual_platform", "real_platform"} and row.get("required_for_sale")]),
        },
        "items": items,
        "pending_required": pending_required,
        "operator_focus": operator_focus or {},
        "youtube_only_flow": youtube_flow,
        "actions": next_actions,
        "operator_summary": _checklist_operator_summary(
            sale_ready=sale_ready,
            passed=passed,
            required=required,
            manual_pending=manual_pending,
            local_pending=local_pending,
        ),
        "status_text": _checklist_status_text(passed=passed, required=required, manual_pending=manual_pending, local_pending=local_pending),
    }


def build_youtube_broadcast_evidence_quickstart(
    root: str | Path = ".",
    *,
    artifact_path: str | Path = "debugCapture/broadcast_platform_e2e_qa.json",
) -> dict[str, Any]:
    """Return a YouTube-only operator plan for commercial broadcast evidence."""
    checklist = build_broadcast_platform_evidence_checklist(root, artifact_path=artifact_path)
    youtube_flow = dict(checklist.get("youtube_only_flow") if isinstance(checklist.get("youtube_only_flow"), Mapping) else {})
    next_required = dict(youtube_flow.get("next_required_check") if isinstance(youtube_flow.get("next_required_check"), Mapping) else {})
    return {
        "schema": BROADCAST_YOUTUBE_QUICKSTART_SCHEMA,
        "available": True,
        "complete": bool(youtube_flow.get("complete")),
        "sale_ready": bool(checklist.get("sale_ready") or checklist.get("commercial_ready")),
        "status_text": str(checklist.get("status_text") or ""),
        "next_required_check_id": str(next_required.get("id") or ""),
        "next_required_cta": str(next_required.get("primary_cta") or ""),
        "youtube_studio_url": "https://studio.youtube.com",
        "live_target_id": "youtube_live",
        "required_evidence": [
            {
                "check_id": "private_rtmp_ingest",
                "label": "Register RTMP",
                "button": "Register RTMP",
                "proof": "Redacted note/screenshot/log that YouTube received the private/unlisted RTMP ingest.",
            },
            {
                "check_id": "youtube_unlisted_viewer_playback",
                "label": "Register YouTube View",
                "button": "Register YouTube View",
                "proof": "Redacted note/screenshot/log that the YouTube preview/watch page plays Program Output.",
            },
        ],
        "operator_steps": list(youtube_flow.get("operator_steps") or []),
        "safe_evidence": str(youtube_flow.get("safe_evidence") or _default_safe_registration_hint("youtube_unlisted_viewer_playback")),
        "do_not_include": [
            "stream keys",
            "YouTube watch/preview URLs",
            "signed/private URLs",
            "account identifiers",
            "analytics",
            "private chat",
            "raw Performance Source frames",
        ],
        "optional_evidence": [
            {
                "check_id": "discord_window_share",
                "label": "Optional video-call/window-share evidence",
                "required_for_sale": False,
            }
        ],
    }


def _ensure_current_manual_checks(report: Mapping[str, Any]) -> dict[str, Any]:
    """Keep older evidence artifacts compatible with current manual check slots."""
    merged = dict(report or {})
    checks = [dict(row) for row in list(merged.get("checks") or []) if isinstance(row, Mapping)]
    existing = {str(row.get("id") or "") for row in checks}
    current_manual = [
        _manual_check(
            "private_rtmp_ingest",
            "Private/unlisted RTMP ingest test",
            "Run YouTube, Twitch, or Custom RTMP with redacted stream key evidence.",
        ),
        _manual_check(
            "youtube_unlisted_viewer_playback",
            "YouTube private/unlisted viewer playback test",
            "Open the private/unlisted YouTube watch or preview page and verify Program Output playback.",
        ),
        _manual_check(
            "discord_window_share",
            "Discord/video-call Program Output window-share test",
            "Join a test call and verify only Program Output is shared, not Performance Source.",
            required_for_sale=False,
        ),
    ]
    changed = False
    for row in current_manual:
        if str(row.get("id") or "") in existing:
            continue
        checks.append(row)
        changed = True
    if changed:
        merged["checks"] = checks
        _refresh_summary(merged)
    return merged


def _youtube_only_flow(items: list[dict[str, Any]], *, operator_focus: Mapping[str, Any]) -> dict[str, Any]:
    by_id = {str(row.get("id") or ""): row for row in items}
    required_ids = ["private_rtmp_ingest", "youtube_unlisted_viewer_playback"]
    required = [dict(by_id.get(check_id) or {}) for check_id in required_ids]
    ready_ids = [str(row.get("id") or "") for row in required if row.get("ok")]
    pending = [row for row in required if not row.get("ok")]
    next_required = pending[0] if pending else {}
    focus_id = str(operator_focus.get("id") or "")
    if focus_id in required_ids and operator_focus:
        next_required = dict(operator_focus)
    return {
        "schema": "tigerstudio.broadcast.youtube_only_evidence_flow.v1",
        "available": True,
        "label": "YouTube-only broadcast evidence",
        "summary": (
            "A YouTube account is enough: complete RTMP ingest evidence, then verify "
            "the private/unlisted YouTube viewer or preview page."
        ),
        "required_check_ids": required_ids,
        "optional_check_ids": ["discord_window_share"],
        "ready_check_ids": ready_ids,
        "pending_check_ids": [str(row.get("id") or "") for row in pending],
        "complete": len(pending) == 0 and len(ready_ids) == len(required_ids),
        "next_required_check": next_required,
        "operator_steps": [
            "Create or open a private/unlisted YouTube live event.",
            "Use Tiger Studio's YouTube/RTMP Live Target and keep the stream key session-only.",
            "Register redacted RTMP ingest evidence with Register RTMP.",
            "Open the same YouTube preview/watch page and verify Program Output playback.",
            "Register redacted viewer/playback evidence with Register YouTube View.",
        ],
        "safe_evidence": (
            "Use redacted notes, screenshots, or logs. Never include stream keys, "
            "YouTube watch/preview URLs, signed/private URLs, account IDs, analytics, "
            "chat, or raw Performance Source frames."
        ),
    }


def _checklist_item(row: Mapping[str, Any]) -> dict[str, Any]:
    ok = bool(row.get("ok"))
    kind = str(row.get("kind") or "")
    evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
    return {
        "id": str(row.get("id") or ""),
        "label": str(row.get("label") or row.get("id") or "Evidence check"),
        "kind": kind,
        "status": "passed" if ok else "pending",
        "ok": ok,
        "required_for_sale": bool(row.get("required_for_sale")),
        "action": str(row.get("action") or ""),
        "primary_cta": str(row.get("primary_cta") or _default_primary_cta(str(row.get("id") or ""))),
        "why_required": str(row.get("why_required") or _default_why_required(str(row.get("id") or ""))),
        "safe_registration_hint": str(row.get("safe_registration_hint") or _default_safe_registration_hint(str(row.get("id") or ""))),
        "operator_steps": [str(step) for step in list(row.get("operator_steps") or []) if str(step)],
        "registration": dict(row.get("registration") if isinstance(row.get("registration"), Mapping) else {}),
        "evidence_summary": _evidence_summary(evidence),
    }


def _evidence_summary(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not evidence:
        return {}
    summary = {
        "output_path": str(evidence.get("output_path") or evidence.get("evidence_path") or ""),
        "bytes": int(evidence.get("bytes") or 0),
        "frames_written": int(evidence.get("frames_written") or 0),
        "platform": str(evidence.get("platform") or ""),
        "redacted": bool(evidence.get("redacted", False)),
        "performance_source_direct_output": evidence.get("performance_source_direct_output"),
        "program_output_composited": evidence.get("program_output_composited"),
    }
    return {key: value for key, value in summary.items() if value not in {"", None, 0}}


def _checklist_status_text(
    *,
    passed: int,
    required: int,
    manual_pending: list[dict[str, Any]],
    local_pending: list[dict[str, Any]],
) -> str:
    if required <= 0:
        return "Broadcast evidence is not initialized."
    if passed >= required:
        return f"Broadcast sale evidence complete: {passed}/{required} checks passed. Commercial broadcast claim is now unblocked."
    pending_labels = [str(row.get("label") or row.get("id")) for row in manual_pending + local_pending]
    if pending_labels:
        return f"Broadcast sale evidence: {passed}/{required} passed. Next required: {pending_labels[0]}."
    return f"Broadcast sale evidence: {passed}/{required} passed."


def _checklist_action(row: Mapping[str, Any]) -> str:
    cta = str(row.get("primary_cta") or _default_primary_cta(str(row.get("id") or ""))).strip()
    label = str(row.get("label") or row.get("id") or "evidence check").strip()
    if cta:
        return cta
    return f"Complete and register: {label}."


def _checklist_operator_summary(
    *,
    sale_ready: bool,
    passed: int,
    required: int,
    manual_pending: list[dict[str, Any]],
    local_pending: list[dict[str, Any]],
) -> str:
    if sale_ready:
        return "Broadcast commercial evidence is complete. Program Output broadcast/window-share claims can be evaluated from the registered artifact."
    if manual_pending:
        focus = manual_pending[0]
        return (
            f"Commercial broadcast claims are blocked by real-platform evidence. "
            f"Next: {focus.get('primary_cta') or focus.get('label') or focus.get('id')}"
        )
    if local_pending:
        focus = local_pending[0]
        return (
            f"Commercial broadcast claims are blocked by local runtime evidence. "
            f"Next: {focus.get('label') or focus.get('id')}"
        )
    return f"Broadcast evidence is incomplete: {passed}/{required} checks passed."


def run_record_file_smoke(root: str | Path = ".") -> dict[str, Any]:
    """Write a short synthetic Program Output clip through BroadcastOutputSession."""
    from app.broadcast_output_session import BroadcastOutputSession

    root_path = Path(root).resolve()
    out_dir = root_path / "debugCapture"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "broadcast_record_smoke.mp4"
    if output.exists():
        try:
            output.unlink()
        except Exception:
            pass
    width, height, fps, frames = 160, 90, 10, 12
    session = BroadcastOutputSession(
        {
            "target_id": "record_file",
            "output_path": str(output),
            "video_bitrate_kbps": 1000,
            "include_audio": False,
        },
        {"width": width, "height": height, "fps": fps},
    )
    started = session.start()
    if started.get("state") != "running":
        return {
            "ok": False,
            "output_path": str(output),
            "state": started.get("state"),
            "error": started.get("last_error") or "; ".join(started.get("errors", []) or []),
        }
    last = started
    for idx in range(frames):
        last = session.write_frame(_synthetic_program_frame(width, height, idx, frames))
        if last.get("state") == "error":
            break
    stopped = session.stop()
    size = output.stat().st_size if output.exists() else 0
    return {
        "ok": bool(size > 1000 and int(last.get("frames_written", 0) or 0) >= frames),
        "output_path": str(output),
        "bytes": int(size),
        "frames_requested": frames,
        "frames_written": int(last.get("frames_written", 0) or 0),
        "start_state": started.get("state"),
        "stop_state": stopped.get("state"),
        "health": stopped.get("health"),
        "last_error": stopped.get("last_error", ""),
    }


def run_live2d_record_file_smoke(root: str | Path = ".") -> dict[str, Any]:
    """Write a short Live2D-like Program Output clip through the same session."""
    from app.broadcast_output_session import BroadcastOutputSession

    root_path = Path(root).resolve()
    out_dir = root_path / "debugCapture"
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "broadcast_live2d_record_smoke.mp4"
    if output.exists():
        try:
            output.unlink()
        except Exception:
            pass
    width, height, fps, frames = 160, 90, 10, 12
    session = BroadcastOutputSession(
        {
            "target_id": "record_file",
            "output_path": str(output),
            "video_bitrate_kbps": 1000,
            "include_audio": False,
        },
        {"width": width, "height": height, "fps": fps},
    )
    started = session.start()
    if started.get("state") != "running":
        return {
            "ok": False,
            "output_path": str(output),
            "state": started.get("state"),
            "error": started.get("last_error") or "; ".join(started.get("errors", []) or []),
            "avatar_target_kind": "live2d_actor_clip",
            "performance_source_direct_output": False,
        }
    last = started
    for idx in range(frames):
        last = session.write_frame(_synthetic_live2d_program_frame(width, height, idx, frames))
        if last.get("state") == "error":
            break
    stopped = session.stop()
    size = output.stat().st_size if output.exists() else 0
    return {
        "ok": bool(size > 1000 and int(last.get("frames_written", 0) or 0) >= frames),
        "output_path": str(output),
        "bytes": int(size),
        "frames_requested": frames,
        "frames_written": int(last.get("frames_written", 0) or 0),
        "start_state": started.get("state"),
        "stop_state": stopped.get("state"),
        "health": stopped.get("health"),
        "last_error": stopped.get("last_error", ""),
        "avatar_target_kind": "live2d_actor_clip",
        "program_output_composited": True,
        "performance_source_direct_output": False,
    }


def _run_synthetic_capture_composite_smoke() -> dict[str, Any]:
    from app.broadcast_capture_backend import composite_broadcast_frame_with_captures

    screen = np.zeros((4, 6, 3), dtype=np.uint8)
    screen[:, :] = [18, 96, 210]
    scene = {
        "canvas": {"width": 6, "height": 4, "background": [0, 0, 0, 255]},
        "sources": [
            {
                "id": "screen",
                "type": "display_capture",
                "settings": {"region": {"left": 0, "top": 0, "width": 6, "height": 4}},
                "transform": {"x": 0, "y": 0, "width": 6, "height": 4},
            }
        ],
    }
    out, diag = composite_broadcast_frame_with_captures(scene, screen_grabber=lambda _region: screen)
    return {
        "ok": bool(diag.get("ok") and out.shape == (4, 6, 3) and out[0, 0].tolist() == [18, 96, 210]),
        "capture_ok": bool(diag.get("capture", {}).get("ok")),
        "composite_ok": bool(diag.get("composite", {}).get("rendered_source_count") == 1),
    }


def _manual_check(check_id: str, label: str, action: str, *, required_for_sale: bool = True) -> dict[str, Any]:
    if check_id == "discord_window_share":
        platform_hint = "Discord/Google Meet/Zoom"
    elif check_id == "youtube_unlisted_viewer_playback":
        platform_hint = "YouTube"
    else:
        platform_hint = "YouTube/Twitch/Custom RTMP"
    return {
        "id": check_id,
        "label": label,
        "kind": "manual_platform",
        "ok": False,
        "required_for_sale": bool(required_for_sale),
        "action": action,
        "primary_cta": _default_primary_cta(check_id),
        "why_required": _default_why_required(check_id),
        "safe_registration_hint": _default_safe_registration_hint(check_id),
        "operator_steps": _manual_operator_steps(check_id),
        "registration": {
            "tool": "tools/register_broadcast_platform_evidence.py",
            "command_template": (
                "python tools/register_broadcast_platform_evidence.py "
                f"--check-id {check_id} --platform \"{platform_hint}\" "
                "--notes \"<redacted result>\" --confirm-redacted"
            ),
            "redaction_required": True,
        },
    }


def _manual_operator_steps(check_id: str) -> list[str]:
    if check_id == "youtube_unlisted_viewer_playback":
        return [
            "Open YouTube Studio for the same private/unlisted live event.",
            "Start the Tiger Studio YouTube/RTMP Live Target and wait for YouTube to show preview/playback.",
            "Open the private/unlisted watch or preview page and confirm Program Output is playing.",
            "Confirm raw Performance Source/tracking input is not visible in the public-facing picture.",
            "Register redacted notes or a redacted screenshot/log path with the evidence tool.",
        ]
    if check_id == "discord_window_share":
        return [
            "Open the shared VTuber Studio and choose Discord / Video Call Output.",
            "Start or prepare the Live Target so the Program Output window is available.",
            "Join a private test call and share only the Program Output window.",
            "Confirm the Performance Source video is not visible in the shared output.",
            "Register redacted notes or a redacted screenshot path with the evidence tool.",
        ]
    if check_id == "private_rtmp_ingest":
        return [
            "Open the shared VTuber Studio and choose YouTube, Twitch, or Custom RTMP.",
            "Use a private/unlisted event and paste the stream key only into the session UI.",
            "Start the Live Target and confirm the platform receives Program Output frames.",
            "Redact stream keys, URLs with tokens, account identifiers, and private chat data.",
            "Register redacted notes or a redacted screenshot/log path with the evidence tool.",
        ]
    return [
        "Run the platform check.",
        "Redact secrets and private account data.",
        "Register the result with the evidence tool.",
    ]


def _default_primary_cta(check_id: str) -> str:
    if check_id == "private_rtmp_ingest":
        return "Run a private/unlisted RTMP ingest test, then click Register RTMP in VTuber Studio."
    if check_id == "youtube_unlisted_viewer_playback":
        return "Open the private/unlisted YouTube viewer or preview page, then click Register YouTube View."
    if check_id == "discord_window_share":
        return "Optional: share only the Program Output window in a private video-call test, then register the result."
    if check_id == "record_file_local":
        return "Run the local Program Output MP4 smoke check."
    if check_id == "live2d_record_file_local":
        return "Run the Live2D Program Output MP4 smoke check."
    if check_id == "capture_composite_local":
        return "Run the capture/composite Program Output smoke check."
    return "Complete this broadcast evidence check."


def _default_why_required(check_id: str) -> str:
    if check_id == "private_rtmp_ingest":
        return "This proves Program Output can reach a real RTMP service without exposing stream keys or raw Performance Source video."
    if check_id == "youtube_unlisted_viewer_playback":
        return "This proves a real YouTube viewer/preview page receives the final Program Output picture, not the raw Performance Source."
    if check_id == "discord_window_share":
        return "This optional evidence proves the user can share the final Program Output window in a call while keeping Performance Source private."
    if check_id == "record_file_local":
        return "This proves the local recording path can encode Program Output to MP4."
    if check_id == "live2d_record_file_local":
        return "This proves Live2D Program Output can be recorded through the same output path."
    if check_id == "capture_composite_local":
        return "This proves capture sources can be resolved and composited into Program Output."
    return "This check is required before commercial broadcast claims."


def _default_safe_registration_hint(check_id: str) -> str:
    if check_id == "private_rtmp_ingest":
        return "Allowed evidence: redacted screenshot/log/notes showing ingest success. Never include stream keys, signed URLs, tokens, account IDs, or private chat."
    if check_id == "youtube_unlisted_viewer_playback":
        return "Allowed evidence: redacted screenshot/log/notes showing YouTube preview or watch-page playback. Never include stream keys, YouTube watch/preview URLs, signed/private URLs, account IDs, analytics, or chat."
    if check_id == "discord_window_share":
        return "Allowed evidence: redacted screenshot/notes showing Program Output shared. Never include private user names, chat content, or the Performance Source frame."
    return "Register only redacted evidence. Do not include tokens, passwords, stream keys, signed URLs, or private account data."


def _refresh_summary(report: dict[str, Any]) -> None:
    checks = [row for row in report.get("checks", []) if isinstance(row, Mapping)]
    required_checks = [row for row in checks if row.get("required_for_sale", True)]
    passed = len([row for row in required_checks if row.get("ok")])
    required = len(required_checks)
    report["ok"] = all(row.get("ok") for row in checks if row.get("kind") == "local_runtime")
    report["real_platform_evidence"] = all(row.get("ok") for row in required_checks) and any(row.get("kind") == "real_platform" for row in required_checks)
    report["summary"] = {
        "passed": passed,
        "required": required,
        "pending": required - passed,
        "local_runtime_passed": len([row for row in checks if row.get("kind") == "local_runtime" and row.get("ok")]),
        "manual_platform_pending": len([row for row in required_checks if row.get("kind") == "manual_platform" and not row.get("ok")]),
    }


def _validate_evidence_payload(evidence: Mapping[str, Any]) -> None:
    if not str(evidence.get("platform") or "").strip():
        raise ValueError("platform is required")
    if not str(evidence.get("evidence_path") or evidence.get("notes") or "").strip():
        raise ValueError("evidence_path or notes is required")
    forbidden = {"stream_key", "key", "password", "secret", "token"}
    forbidden_fragments = (
        "stream_key",
        "password=",
        "token=",
        "access_token",
        "secret=",
        "key=",
        "rtmp://live.twitch.tv/app/",
        "rtmps://live-api-s.facebook.com:",
        "rtmp://a.rtmp.youtube.com/live2/",
        "rtmps://a.rtmps.youtube.com/live2/",
        "youtube.com/watch",
        "youtu.be/",
        "youtube.com/live/",
        "studio.youtube.com/video/",
        "studio.youtube.com/live",
    )
    for key, value in evidence.items():
        key_text = str(key).lower()
        if key_text in forbidden:
            raise ValueError(f"secret-like evidence field is not allowed: {key}")
        value_text = str(value).lower()
        if any(fragment in value_text for fragment in forbidden_fragments):
            raise ValueError("evidence appears to contain an unredacted secret")


def _load_report(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _synthetic_program_frame(width: int, height: int, index: int, total: int) -> np.ndarray:
    x = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
    y = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = (x + index * 11) % 255
    frame[:, :, 1] = (y + index * 17) % 255
    frame[:, :, 2] = int(64 + 128 * (index / max(1, total - 1)))
    return frame


def _synthetic_live2d_program_frame(width: int, height: int, index: int, total: int) -> np.ndarray:
    """Program Output frame with chroma background and a composited avatar shape."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = [0, 255, 0]
    yy, xx = np.ogrid[:height, :width]
    cx = width // 2 + int(np.sin(index / max(1, total - 1) * np.pi * 2.0) * width * 0.04)
    head_cy = int(height * 0.34)
    head_rx = max(8, width // 9)
    head_ry = max(10, height // 6)
    head = ((xx - cx) / head_rx) ** 2 + ((yy - head_cy) / head_ry) ** 2 <= 1.0
    torso_top = int(height * 0.52)
    torso_bottom = int(height * 0.96)
    torso_w = max(24, width // 4)
    torso = (yy >= torso_top) & (yy < torso_bottom) & (np.abs(xx - cx) < torso_w)
    hair = head & (yy < head_cy)
    face = head & ~hair
    frame[torso] = [82, 72, 190]
    frame[hair] = [54, 36, 76]
    frame[face] = [244, 196, 178]
    eye_y = head_cy - max(1, head_ry // 5)
    eye_rx = max(2, head_rx // 7)
    eye_ry = max(1, head_ry // 10)
    left_eye = ((xx - (cx - head_rx // 3)) / eye_rx) ** 2 + ((yy - eye_y) / eye_ry) ** 2 <= 1.0
    right_eye = ((xx - (cx + head_rx // 3)) / eye_rx) ** 2 + ((yy - eye_y) / eye_ry) ** 2 <= 1.0
    mouth_open = max(1, int(2 + 3 * abs(np.sin(index * 0.9))))
    mouth = (
        (np.abs(xx - cx) <= max(3, head_rx // 4))
        & (yy >= head_cy + head_ry // 3)
        & (yy <= head_cy + head_ry // 3 + mouth_open)
    )
    frame[left_eye | right_eye] = [34, 42, 72]
    frame[mouth] = [118, 44, 68]
    return frame
