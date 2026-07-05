"""UI-neutral helpers for broadcast evidence status and registration forms."""
from __future__ import annotations

from typing import Any, Mapping


BROADCAST_EVIDENCE_UI_SCHEMA = "tigerstudio.broadcast.evidence_ui.v1"


def broadcast_evidence_status_lines(checklist: Mapping[str, Any] | None) -> list[str]:
    """Return concise Studio UI lines for a platform evidence checklist."""
    data = dict(checklist or {})
    summary = dict(data.get("summary") if isinstance(data.get("summary"), Mapping) else {})
    focus = dict(data.get("operator_focus") if isinstance(data.get("operator_focus"), Mapping) else {})
    lines = [
        str(data.get("status_text") or "Broadcast evidence is not initialized."),
        f"Local checks: {int(summary.get('local_runtime_passed') or 0)}/{int(summary.get('local_runtime_required') or 0)} passed.",
    ]
    manual_pending = int(summary.get("manual_platform_pending") or 0)
    if manual_pending > 0:
        lines.append(f"Manual platform checks left: {manual_pending}.")
    else:
        lines.append("Manual platform evidence is complete.")
    if focus:
        lines.append(f"Next: {focus.get('label') or focus.get('id')}")
        steps = [str(step) for step in list(focus.get("operator_steps") or []) if str(step)]
        if steps:
            lines.append(steps[0])
    return lines


def broadcast_evidence_register_defaults(check_id: str) -> dict[str, str]:
    """Return dialog copy/defaults for a manual evidence check."""
    check = str(check_id or "").strip()
    rows = {
        "private_rtmp_ingest": {
            "title": "Register RTMP Evidence",
            "platform": "YouTube/Twitch/Custom RTMP",
            "notes_placeholder": "Example: Private ingest reached excellent status; stream key redacted.",
        },
        "discord_window_share": {
            "title": "Register Discord Evidence",
            "platform": "Discord",
            "notes_placeholder": "Example: Program Output window shared; Performance Source not visible.",
        },
    }
    data = dict(rows.get(check) or {})
    return {
        "schema": BROADCAST_EVIDENCE_UI_SCHEMA,
        "check_id": check,
        "title": data.get("title", "Register Broadcast Evidence"),
        "platform": data.get("platform", ""),
        "description": (
            "Register only real, redacted platform evidence. Do not paste stream "
            "keys, tokens, passwords, private URLs, or account secrets."
        ),
        "evidence_placeholder": "Path to redacted screenshot/log/video evidence, optional if notes are detailed",
        "notes_placeholder": data.get("notes_placeholder", "Example: Redacted platform check result."),
        "confirm_label": (
            "I confirm this evidence is redacted and contains no stream keys, "
            "tokens, passwords, or private account secrets."
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
