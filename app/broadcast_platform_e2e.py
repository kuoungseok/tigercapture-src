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
                "discord_window_share",
                "Discord/video-call Program Output window-share test",
                "Join a test call and verify only Program Output is shared, not Performance Source.",
            ),
        ]
    )
    passed = len([row for row in checks if row.get("ok")])
    required = len(checks)
    real_platform_evidence = all(row.get("ok") for row in checks) and any(row.get("kind") == "real_platform" for row in checks)
    return {
        "schema": BROADCAST_PLATFORM_E2E_SCHEMA,
        "ok": all(row.get("ok") for row in checks if row.get("kind") == "local_runtime"),
        "real_platform_evidence": real_platform_evidence,
        "summary": {
            "passed": passed,
            "required": required,
            "pending": required - passed,
            "local_runtime_passed": len([row for row in checks if row.get("kind") == "local_runtime" and row.get("ok")]),
            "manual_platform_pending": len([row for row in checks if row.get("kind") == "manual_platform" and not row.get("ok")]),
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
    return {
        "schema": BROADCAST_PLATFORM_EVIDENCE_SCHEMA,
        "artifact": str(path),
        "check_id": target_id,
        "registered": True,
        "report": report,
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
            "manual_platform_required": len([row for row in items if row.get("kind") in {"manual_platform", "real_platform"}]),
        },
        "items": items,
        "pending_required": pending_required,
        "operator_focus": operator_focus or {},
        "actions": [str(row.get("action") or row.get("label") or row.get("id")) for row in pending_required],
        "status_text": _checklist_status_text(passed=passed, required=required, manual_pending=manual_pending, local_pending=local_pending),
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
        return f"Broadcast sale evidence complete: {passed}/{required} checks passed."
    pending_labels = [str(row.get("label") or row.get("id")) for row in manual_pending + local_pending]
    if pending_labels:
        return f"Broadcast sale evidence: {passed}/{required} passed. Pending: {', '.join(pending_labels[:3])}."
    return f"Broadcast sale evidence: {passed}/{required} passed."


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


def _manual_check(check_id: str, label: str, action: str) -> dict[str, Any]:
    platform_hint = "Discord" if check_id == "discord_window_share" else "YouTube/Twitch/Custom RTMP"
    return {
        "id": check_id,
        "label": label,
        "kind": "manual_platform",
        "ok": False,
        "required_for_sale": True,
        "action": action,
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


def _refresh_summary(report: dict[str, Any]) -> None:
    checks = [row for row in report.get("checks", []) if isinstance(row, Mapping)]
    passed = len([row for row in checks if row.get("ok")])
    required = len(checks)
    report["ok"] = all(row.get("ok") for row in checks if row.get("kind") == "local_runtime")
    report["real_platform_evidence"] = all(row.get("ok") for row in checks) and any(row.get("kind") == "real_platform" for row in checks)
    report["summary"] = {
        "passed": passed,
        "required": required,
        "pending": required - passed,
        "local_runtime_passed": len([row for row in checks if row.get("kind") == "local_runtime" and row.get("ok")]),
        "manual_platform_pending": len([row for row in checks if row.get("kind") == "manual_platform" and not row.get("ok")]),
    }


def _validate_evidence_payload(evidence: Mapping[str, Any]) -> None:
    if not str(evidence.get("platform") or "").strip():
        raise ValueError("platform is required")
    if not str(evidence.get("evidence_path") or evidence.get("notes") or "").strip():
        raise ValueError("evidence_path or notes is required")
    forbidden = {"stream_key", "key", "password", "secret", "token"}
    for key, value in evidence.items():
        key_text = str(key).lower()
        if key_text in forbidden:
            raise ValueError(f"secret-like evidence field is not allowed: {key}")
        value_text = str(value).lower()
        if "stream_key" in value_text or "password=" in value_text or "token=" in value_text:
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
