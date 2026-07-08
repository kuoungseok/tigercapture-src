"""UI-neutral helpers for broadcast evidence status and registration forms."""
from __future__ import annotations

from typing import Any, Mapping


BROADCAST_EVIDENCE_UI_SCHEMA = "tigerstudio.broadcast.evidence_ui.v1"

_FORBIDDEN_EVIDENCE_TEXT = (
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


def broadcast_evidence_status_lines(checklist: Mapping[str, Any] | None) -> list[str]:
    """Return concise Studio UI lines for a platform evidence checklist."""
    data = dict(checklist or {})
    summary = dict(data.get("summary") if isinstance(data.get("summary"), Mapping) else {})
    focus = dict(data.get("operator_focus") if isinstance(data.get("operator_focus"), Mapping) else {})
    lines = [
        str(data.get("status_text") or "Broadcast evidence is not initialized."),
        f"Local checks: {int(summary.get('local_runtime_passed') or 0)}/{int(summary.get('local_runtime_required') or 0)} passed.",
    ]
    operator_summary = str(data.get("operator_summary") or "").strip()
    if operator_summary:
        lines.append(operator_summary)
    youtube_flow = dict(data.get("youtube_only_flow") if isinstance(data.get("youtube_only_flow"), Mapping) else {})
    if youtube_flow:
        if youtube_flow.get("complete"):
            lines.append("YouTube-only path is complete. Discord/video-call evidence is optional.")
        else:
            lines.append("YouTube-only path: Register RTMP, then Register YouTube View. Discord/video-call is optional.")
    manual_pending = int(summary.get("manual_platform_pending") or 0)
    if manual_pending > 0:
        lines.append(f"Manual platform checks left: {manual_pending}.")
    else:
        lines.append("Manual platform evidence is complete.")
    if focus:
        lines.append(f"Next: {focus.get('primary_cta') or focus.get('label') or focus.get('id')}")
        why = str(focus.get("why_required") or "").strip()
        if why:
            lines.append(f"Why: {why}")
        hint = str(focus.get("safe_registration_hint") or "").strip()
        if hint:
            lines.append(f"Safe evidence: {hint}")
        steps = [str(step) for step in list(focus.get("operator_steps") or []) if str(step)]
        if steps:
            lines.append(steps[0])
    return lines


def broadcast_evidence_wizard_steps(checklist: Mapping[str, Any] | None) -> list[dict[str, object]]:
    """Return ordered user-facing steps for the Broadcast Evidence wizard."""
    data = dict(checklist or {})
    items = [dict(row) for row in list(data.get("items") or []) if isinstance(row, Mapping)]
    by_id = {str(row.get("id") or ""): row for row in items}
    order = [
        "record_file_local",
        "live2d_record_file_local",
        "capture_composite_local",
        "private_rtmp_ingest",
        "youtube_unlisted_viewer_playback",
        "discord_window_share",
    ]
    steps: list[dict[str, object]] = []
    for index, check_id in enumerate(order, start=1):
        item = dict(by_id.get(check_id) or {})
        if not item:
            item = {
                "id": check_id,
                "label": _wizard_default_label(check_id),
                "ok": False,
                "status": "pending",
                "kind": "manual_platform" if check_id in {"private_rtmp_ingest", "youtube_unlisted_viewer_playback", "discord_window_share"} else "local_runtime",
                "required_for_sale": check_id != "discord_window_share",
            }
        steps.append(
            {
                "index": index,
                "id": check_id,
                "label": str(item.get("label") or _wizard_default_label(check_id)),
                "status": "done" if item.get("ok") else "pending",
                "ok": bool(item.get("ok")),
                "required_for_sale": bool(item.get("required_for_sale", check_id != "discord_window_share")),
                "kind": str(item.get("kind") or ""),
                "primary_cta": str(item.get("primary_cta") or _wizard_default_cta(check_id)),
                "why_required": str(item.get("why_required") or _wizard_default_why(check_id)),
                "safe_registration_hint": str(item.get("safe_registration_hint") or _wizard_default_safe_hint(check_id)),
                "operator_steps": [str(step) for step in list(item.get("operator_steps") or []) if str(step).strip()],
                "registration": dict(item.get("registration") if isinstance(item.get("registration"), Mapping) else {}),
                "evidence_summary": dict(item.get("evidence_summary") if isinstance(item.get("evidence_summary"), Mapping) else {}),
            }
        )
    return steps


def broadcast_evidence_wizard_summary(checklist: Mapping[str, Any] | None) -> dict[str, object]:
    """Return compact progress and next-step copy for the evidence wizard."""
    data = dict(checklist or {})
    summary = dict(data.get("summary") if isinstance(data.get("summary"), Mapping) else {})
    youtube_flow = dict(data.get("youtube_only_flow") if isinstance(data.get("youtube_only_flow"), Mapping) else {})
    steps = broadcast_evidence_wizard_steps(data)
    pending = [step for step in steps if not step.get("ok") and step.get("required_for_sale", True)]
    next_step = dict(pending[0]) if pending else {}
    passed = int(summary.get("passed") or len([step for step in steps if step.get("ok")]))
    required = int(summary.get("required") or len(steps))
    return {
        "schema": BROADCAST_EVIDENCE_UI_SCHEMA,
        "sale_ready": bool(data.get("sale_ready") or data.get("commercial_ready")),
        "passed": passed,
        "required": required,
        "pending": max(0, required - passed),
        "status_text": str(data.get("status_text") or ""),
        "operator_summary": str(data.get("operator_summary") or ""),
        "youtube_only_flow": youtube_flow,
        "next_step": next_step,
        "steps": steps,
    }


def _wizard_default_label(check_id: str) -> str:
    labels = {
        "record_file_local": "Record Program Output to local MP4",
        "live2d_record_file_local": "Record Live2D Program Output to local MP4",
        "capture_composite_local": "Resolve capture source and composite Program Output",
        "private_rtmp_ingest": "Private/unlisted RTMP ingest test",
        "youtube_unlisted_viewer_playback": "YouTube private/unlisted viewer playback test",
        "discord_window_share": "Discord/video-call Program Output window-share test",
    }
    return labels.get(check_id, check_id or "Evidence check")


def _wizard_default_cta(check_id: str) -> str:
    if check_id == "private_rtmp_ingest":
        return "Run a private/unlisted RTMP ingest test, then click Register RTMP."
    if check_id == "youtube_unlisted_viewer_playback":
        return "Open the private/unlisted YouTube viewer or preview page, then click Register YouTube View."
    if check_id == "discord_window_share":
        return "Optional: share only Program Output in a private video call, then register the result."
    return "Run broadcast evidence QA to refresh this check."


def _wizard_default_why(check_id: str) -> str:
    if check_id == "private_rtmp_ingest":
        return "Commercial RTMP claims need one real platform ingest proof."
    if check_id == "youtube_unlisted_viewer_playback":
        return "Commercial YouTube broadcast claims need proof that the viewer/preview page receives Program Output."
    if check_id == "discord_window_share":
        return "Optional video-call claims need proof that only Program Output is shared."
    return "This local check proves the Program Output path works before platform evidence is registered."


def _wizard_default_safe_hint(check_id: str) -> str:
    if check_id in {"private_rtmp_ingest", "youtube_unlisted_viewer_playback", "discord_window_share"}:
        return "Use redacted notes/screenshots/logs. Never include stream keys, tokens, YouTube watch/preview URLs, signed URLs, account names, private chat, or Performance Source frames."
    return "This check is generated by local QA and does not need private platform data."


def broadcast_evidence_register_defaults(check_id: str) -> dict[str, str]:
    """Return dialog copy/defaults for a manual evidence check."""
    check = str(check_id or "").strip()
    rows = {
        "private_rtmp_ingest": {
            "title": "Register RTMP Evidence",
            "platform": "YouTube/Twitch/Custom RTMP",
            "notes_placeholder": "Example: Private ingest reached excellent status. Stream key and account details are redacted.",
            "safe_note_template": "Private/unlisted RTMP ingest reached the platform successfully. Stream key, server URL, account name, and dashboard details are redacted.",
        },
        "youtube_unlisted_viewer_playback": {
            "title": "Register YouTube Viewer Evidence",
            "platform": "YouTube",
            "notes_placeholder": "Example: Private/unlisted YouTube preview page played Program Output. Stream key, URL, account, and chat details are redacted.",
            "safe_note_template": "Private/unlisted YouTube viewer or preview page played Tiger Studio Program Output successfully. Watch/preview URL, account name, analytics, and chat details are redacted.",
        },
        "discord_window_share": {
            "title": "Register Optional Video-Call Evidence",
            "platform": "Discord/Google Meet/Zoom",
            "notes_placeholder": "Example: Program Output window shared in a private call. Performance Source was not visible.",
            "safe_note_template": "Program Output window was shared in a private video call. Performance Source was not visible. Participant names and chat details are redacted.",
        },
    }
    data = dict(rows.get(check) or {})
    return {
        "schema": BROADCAST_EVIDENCE_UI_SCHEMA,
        "check_id": check,
        "title": data.get("title", "Register Broadcast Evidence"),
        "platform": data.get("platform", ""),
        "description": (
            "Register this only after a real platform check. Use redacted notes, "
            "screenshots, or logs. Do not paste stream keys, tokens, passwords, "
            "YouTube watch/preview URLs, signed/private URLs, account names, or "
            "private chat."
        ),
        "evidence_placeholder": "Optional path to a redacted screenshot/log/video. Detailed redacted notes are also acceptable.",
        "notes_placeholder": data.get("notes_placeholder", "Example: Redacted platform check result."),
        "safe_note_template": data.get("safe_note_template", "Redacted platform check completed successfully. Private URLs, account details, chat, and secrets are redacted."),
        "confirm_label": (
            "I confirm this evidence is redacted and contains no stream keys, "
            "tokens, passwords, YouTube watch/preview URLs, signed URLs, account "
            "secrets, or private chat."
        ),
    }


def build_broadcast_evidence_registration_payload(
    *,
    check_id: str,
    platform: str,
    evidence_path: str = "",
    notes: str = "",
    confirm_redacted: bool = False,
) -> dict[str, object]:
    """Normalize evidence registration form input before calling the action layer."""
    return {
        "check_id": str(check_id or "").strip(),
        "platform": str(platform or "").strip(),
        "evidence_path": str(evidence_path or "").strip(),
        "notes": str(notes or "").strip(),
        "confirm_redacted": bool(confirm_redacted),
    }


def broadcast_evidence_registration_warning(payload: Mapping[str, object]) -> str:
    """Return a user-facing warning before attempting evidence registration."""
    data = dict(payload or {})
    if not bool(data.get("confirm_redacted")):
        return "Check the redaction confirmation before registering evidence."
    if not str(data.get("platform") or "").strip():
        return "Choose or enter the platform first."
    if not str(data.get("evidence_path") or data.get("notes") or "").strip():
        return "Add a redacted note or a redacted evidence file path before registering."
    joined = "\n".join(str(data.get(key) or "") for key in ("platform", "evidence_path", "notes")).lower()
    if any(fragment in joined for fragment in _FORBIDDEN_EVIDENCE_TEXT):
        return (
            "This looks like it contains a private URL, stream key, token, or account data. "
            "Remove YouTube watch/preview links and secrets, then describe the result in "
            "redacted notes or use a redacted screenshot/log path."
        )
    return ""
