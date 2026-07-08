"""Broadcast readiness and platform-evidence action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def _platform_evidence_schema() -> dict[str, Any]:
    return {
        "check_id": {
            "type": "string",
            "enum": ["private_rtmp_ingest", "youtube_unlisted_viewer_playback", "discord_window_share"],
        },
        "platform": {"type": "string"},
        "evidence_path": {"type": "string"},
        "notes": {"type": "string"},
        "confirm_redacted": {"type": "boolean"},
    }


def register_broadcast_evidence_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "broadcast.release_readiness",
        "Return VTuber/broadcast alpha and commercial readiness diagnostics.",
        "broadcast",
        "broadcast_release_readiness",
        params_schema=schema_object({"root": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="broadcast commercial-readiness diagnostics would be returned",
    )
    registry.register_adapter_action(
        "broadcast.platform_evidence_checklist",
        "Return operator checklist for remaining broadcast platform evidence.",
        "broadcast",
        "broadcast_platform_evidence_checklist",
        params_schema=schema_object({"root": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="broadcast platform evidence checklist would be returned",
    )
    registry.register_adapter_action(
        "broadcast.youtube_evidence_quickstart",
        "Return a YouTube-only quickstart for the required broadcast evidence checks.",
        "broadcast",
        "broadcast_youtube_evidence_quickstart",
        params_schema=schema_object(
            {
                "root": {"type": "string"},
                "artifact_path": {"type": "string"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="YouTube-only broadcast evidence quickstart would be returned",
    )
    registry.register_adapter_action(
        "broadcast.evidence_readiness.refresh",
        "Refresh broadcast and final product readiness artifacts after evidence changes.",
        "broadcast",
        "refresh_broadcast_evidence_readiness",
        params_schema=schema_object(
            {
                "root": {"type": "string"},
                "broadcast_out": {"type": "string"},
                "final_out": {"type": "string"},
            }
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="broadcast/final readiness artifacts would be refreshed",
    )
    evidence_schema = _platform_evidence_schema()
    registry.register_adapter_action(
        "broadcast.platform_evidence.preflight",
        "Validate redacted broadcast platform evidence text before registering it.",
        "broadcast",
        "preflight_broadcast_platform_evidence",
        params_schema=schema_object(
            evidence_schema,
            required=("check_id", "platform", "confirm_redacted"),
        ),
        required=("check_id", "platform", "confirm_redacted"),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="broadcast platform evidence would be preflight-validated",
    )
    registry.register_adapter_action(
        "broadcast.platform_evidence.register",
        "Register redacted manual broadcast platform evidence after a real check.",
        "broadcast",
        "register_broadcast_platform_evidence",
        params_schema=schema_object(
            {
                **evidence_schema,
                "root": {"type": "string"},
                "artifact_path": {"type": "string"},
            },
            required=("check_id", "platform", "confirm_redacted"),
        ),
        required=("check_id", "platform", "confirm_redacted"),
        mutating=True,
        requires_owner=False,
        requires_review=True,
        async_kind="broadcast",
        dry_summary="redacted broadcast platform evidence would be registered",
    )
