"""Operator troubleshooting guidance for live broadcast targets."""
from __future__ import annotations

from typing import Any, Mapping

from app.broadcast_output import (
    LIVE_TARGET_CUSTOM_RTMP,
    LIVE_TARGET_DISCORD,
    LIVE_TARGET_INSTAGRAM,
    LIVE_TARGET_TIKTOK,
    LIVE_TARGET_TWITCH,
    LIVE_TARGET_X,
    LIVE_TARGET_YOUTUBE,
    LiveTargetProfile,
    live_target_preset,
)


TROUBLESHOOTING_SCHEMA = "tigerstudio.broadcast.live_target_troubleshooting.v1"
TROUBLESHOOTING_PANEL_SCHEMA = "tigerstudio.broadcast.live_target_troubleshooting_panel.v1"


def build_live_target_troubleshooting(
    target: LiveTargetProfile | Mapping[str, Any] | None = None,
    status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build platform-aware next steps from live output diagnostics."""
    status_data = dict(status or {})
    profile = target if isinstance(target, LiveTargetProfile) else LiveTargetProfile.from_mapping(target or status_data)
    preset = live_target_preset(profile.target_id)
    kind = str(status_data.get("platform_error_kind") or "unknown")
    state = str(status_data.get("state") or "")
    severity = "error" if state == "error" or kind not in {"", "none", "unknown"} else "info"
    if profile.target_id == LIVE_TARGET_DISCORD:
        return _discord_plan(profile, status_data)
    platform = _platform_context(profile.target_id)
    base_steps = _base_steps(kind)
    platform_steps = _platform_steps(profile.target_id, kind)
    checks = [*base_steps, *platform_steps]
    if not checks:
        checks = [
            "Run Check again and confirm the FFmpeg command is ready.",
            "Verify the platform dashboard is accepting live input.",
            "Try recording to file first to confirm Program Output is rendering correctly.",
        ]
    title = _title_for_kind(kind, platform["label"])
    summary = str(status_data.get("platform_error_message") or status_data.get("last_error") or title)
    primary_action = _primary_action(kind)
    check_items = _check_items(profile.target_id, kind, checks, platform)
    return {
        "schema": TROUBLESHOOTING_SCHEMA,
        "target_id": profile.target_id,
        "target_label": preset.label,
        "platform": platform,
        "state": state,
        "severity": severity,
        "error_kind": kind,
        "title": title,
        "summary": summary,
        "checks": checks,
        "check_items": check_items,
        "primary_action": primary_action,
        "panel": _panel_payload(
            target_id=profile.target_id,
            title=title,
            summary=summary,
            severity=severity,
            primary_action=primary_action,
            check_items=check_items,
            platform=platform,
        ),
        "safe_to_retry": kind in {"network", "stream_closed", "connection_refused", "unknown", "ffmpeg"},
        "redacted_stderr_tail": str(status_data.get("stderr_tail") or "")[-1200:],
    }


def _discord_plan(profile: LiveTargetProfile, status_data: Mapping[str, Any]) -> dict[str, Any]:
    platform = _platform_context(profile.target_id)
    checks = [
        "Open the video-call app's screen-share picker and choose Tiger Studio Program Output.",
        "If using OBS Virtual Camera, add Tiger Studio Program Output as a Window Capture source in OBS first.",
        "Keep Performance Source hidden from Program Output; it should only appear in Source Tracking.",
    ]
    primary_action = "share_program_output"
    check_items = _check_items(profile.target_id, "window_share", checks, platform)
    title = "Discord uses Program Output window sharing or an installed virtual-camera backend."
    summary = "No RTMP stream key is needed for Discord/video-call targets."
    return {
        "schema": TROUBLESHOOTING_SCHEMA,
        "target_id": profile.target_id,
        "target_label": live_target_preset(profile.target_id).label,
        "platform": platform,
        "state": str(status_data.get("state") or ""),
        "severity": "info",
        "error_kind": str(status_data.get("platform_error_kind") or "window_share"),
        "title": title,
        "summary": summary,
        "checks": checks,
        "check_items": check_items,
        "primary_action": primary_action,
        "panel": _panel_payload(
            target_id=profile.target_id,
            title=title,
            summary=summary,
            severity="info",
            primary_action=primary_action,
            check_items=check_items,
            platform=platform,
        ),
        "safe_to_retry": True,
        "redacted_stderr_tail": "",
    }


def _platform_context(target_id: str) -> dict[str, Any]:
    if target_id == LIVE_TARGET_YOUTUBE:
        return {
            "id": target_id,
            "label": "YouTube Live",
            "dashboard": "YouTube Live Control Room",
            "dashboard_url": "https://studio.youtube.com",
            "expects": "RTMPS server URL plus stream key",
        }
    if target_id == LIVE_TARGET_TWITCH:
        return {
            "id": target_id,
            "label": "Twitch",
            "dashboard": "Twitch Creator Dashboard",
            "dashboard_url": "https://dashboard.twitch.tv",
            "expects": "Twitch ingest server plus stream key",
        }
    if target_id == LIVE_TARGET_CUSTOM_RTMP:
        return {
            "id": target_id,
            "label": "Custom RTMP / RTMPS",
            "dashboard": "the target service dashboard",
            "expects": "service-issued RTMP/RTMPS URL and optional key",
        }
    if target_id == LIVE_TARGET_TIKTOK:
        return {
            "id": target_id,
            "label": "TikTok Live",
            "dashboard": "TikTok Live Center / Live Studio",
            "expects": "account-enabled RTMP access, server URL, and key",
            "experimental": True,
        }
    if target_id == LIVE_TARGET_INSTAGRAM:
        return {
            "id": target_id,
            "label": "Instagram Live",
            "dashboard": "Instagram Live Producer",
            "expects": "Live Producer URL/key and vertical output",
            "experimental": True,
        }
    if target_id == LIVE_TARGET_X:
        return {
            "id": target_id,
            "label": "X Live",
            "dashboard": "X producer/live dashboard",
            "expects": "account-enabled producer access, server URL, and key",
            "experimental": True,
        }
    if target_id == LIVE_TARGET_DISCORD:
        return {
            "id": target_id,
            "label": "Discord / Video Call Output",
            "dashboard": "the video-call app",
            "dashboard_url": "https://discord.com/app",
            "expects": "Program Output window share or installed virtual-camera backend",
        }
    return {
        "id": target_id,
        "label": live_target_preset(target_id).label,
        "dashboard": "the platform dashboard",
        "expects": "platform-issued output settings",
    }


def _base_steps(kind: str) -> list[str]:
    if kind in {"platform_auth", "stream_key"}:
        return [
            "Open the platform live dashboard and confirm the event is active or waiting for input.",
            "Copy a fresh stream key from the platform and paste it into the session-only Stream Key field.",
            "Check whether the account has permission to go live or use external encoder/RTMP access.",
        ]
    if kind == "server_url":
        return [
            "Paste the platform-issued RTMP/RTMPS server URL exactly as shown.",
            "Do not mix a YouTube/Twitch preset with a custom server from another platform.",
            "If the service gives a combined URL/key, use Custom RTMP / RTMPS and keep the key in the Stream Key field when possible.",
        ]
    if kind == "connection_refused":
        return [
            "Confirm the ingest server URL is correct and currently accepting connections.",
            "Switch to another ingest region if the platform provides one.",
            "Check firewall/VPN rules that may block RTMP/RTMPS outbound connections.",
        ]
    if kind == "network":
        return [
            "Check network stability and outbound RTMP/RTMPS access.",
            "Lower bitrate and retry if the connection is unstable.",
            "Try a nearby ingest server or disable VPN/proxy temporarily.",
        ]
    if kind == "stream_closed":
        return [
            "Open the platform dashboard and read the live event error.",
            "Confirm the stream key was not reset or already in use elsewhere.",
            "Lower bitrate or retry after the platform returns to waiting-for-input state.",
        ]
    if kind == "ffmpeg_config":
        return [
            "Check encoder, bitrate, and keyframe interval settings.",
            "Switch audio to Silent stereo or No audio to isolate audio-device problems.",
            "Record to file first to verify Program Output frames are valid.",
        ]
    return []


def _platform_steps(target_id: str, kind: str) -> list[str]:
    if target_id == LIVE_TARGET_YOUTUBE:
        return [
            "In YouTube Live Control Room, verify the stream is created and not ended.",
            "Use the YouTube RTMPS server with the matching stream key from the same stream event.",
        ]
    if target_id == LIVE_TARGET_TWITCH:
        return [
            "In Twitch Creator Dashboard, verify the stream key was copied from the current account.",
            "Use Twitch's closest ingest server if the default server is unstable.",
        ]
    if target_id in {LIVE_TARGET_TIKTOK, LIVE_TARGET_INSTAGRAM, LIVE_TARGET_X}:
        return [
            "Confirm this account has external encoder or producer access; not every account has RTMP keys.",
            "Use the platform-issued URL/key for the current live session; these may expire.",
            "Keep the vertical canvas recommendation unless the platform explicitly requests horizontal output.",
        ]
    if target_id == LIVE_TARGET_CUSTOM_RTMP:
        return [
            "Check whether the service wants the key appended to the URL or sent separately.",
            "If the endpoint is RTMPS-only, do not use an rtmp:// URL.",
        ]
    return []


def _title_for_kind(kind: str, platform_label: str) -> str:
    if kind in {"platform_auth", "stream_key"}:
        return f"{platform_label} rejected authentication."
    if kind == "server_url":
        return f"{platform_label} server URL needs attention."
    if kind == "connection_refused":
        return f"{platform_label} refused the connection."
    if kind == "network":
        return f"{platform_label} network connection failed."
    if kind == "stream_closed":
        return f"{platform_label} closed the stream."
    if kind == "ffmpeg_config":
        return "FFmpeg output settings need attention."
    return f"{platform_label} live output needs attention."


def _primary_action(kind: str) -> str:
    if kind in {"platform_auth", "stream_key"}:
        return "refresh_stream_key"
    if kind == "server_url":
        return "check_server_url"
    if kind in {"connection_refused", "network"}:
        return "check_network_or_ingest"
    if kind == "stream_closed":
        return "check_platform_dashboard"
    if kind == "ffmpeg_config":
        return "check_output_settings"
    return "run_preflight_check"


def _check_items(target_id: str, kind: str, checks: list[str], platform: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, label in enumerate(checks, start=1):
        action = _check_action(target_id, kind, label, platform)
        rows.append(
            {
                "id": f"{target_id}:{kind}:check_{index}",
                "label": label,
                "status": "pending",
                "completed": False,
                "action": action,
            }
        )
    return rows


def _panel_payload(
    *,
    target_id: str,
    title: str,
    summary: str,
    severity: str,
    primary_action: str,
    check_items: list[dict[str, Any]],
    platform: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": TROUBLESHOOTING_PANEL_SCHEMA,
        "target_id": target_id,
        "title": title,
        "summary": summary,
        "severity": severity,
        "primary": _primary_panel_action(primary_action, platform),
        "items": check_items,
        "completion": {
            "total": len(check_items),
            "completed": 0,
            "status": "pending" if check_items else "empty",
        },
    }


def _primary_panel_action(primary_action: str, platform: Mapping[str, Any]) -> dict[str, Any]:
    if primary_action in {"refresh_stream_key", "check_platform_dashboard"}:
        return _open_dashboard_action(platform, fallback_id=primary_action)
    if primary_action == "check_server_url":
        return {
            "id": "check_server_url",
            "label": "Check server URL",
            "kind": "open_live_target_settings",
            "enabled": True,
        }
    if primary_action == "check_network_or_ingest":
        return {
            "id": "check_network_or_ingest",
            "label": "Check network / ingest",
            "kind": "open_troubleshooting_panel",
            "enabled": True,
        }
    if primary_action == "check_output_settings":
        return {
            "id": "check_output_settings",
            "label": "Open output settings",
            "kind": "open_live_target_settings",
            "enabled": True,
        }
    if primary_action == "share_program_output":
        return {
            "id": "share_program_output",
            "label": "Share Program Output",
            "kind": "show_window_share_steps",
            "enabled": True,
        }
    return {
        "id": "run_preflight_check",
        "label": "Run check",
        "kind": "run_action",
        "action_id": "broadcast.live_target.summary",
        "enabled": True,
    }


def _check_action(target_id: str, kind: str, label: str, platform: Mapping[str, Any]) -> dict[str, Any]:
    text = label.lower()
    if "dashboard" in text or "control room" in text or "creator dashboard" in text:
        return _open_dashboard_action(platform, fallback_id="open_platform_dashboard")
    if "stream key" in text:
        return _open_dashboard_action(platform, fallback_id="refresh_stream_key")
    if "rtmp" in text or "rtmps" in text or "server url" in text:
        return {
            "id": "edit_server_url",
            "label": "Edit Live Target URL/key",
            "kind": "open_live_target_settings",
            "target_id": target_id,
            "error_kind": kind,
            "enabled": True,
        }
    if "bitrate" in text or "keyframe" in text or "encoder" in text:
        return {
            "id": "open_output_settings",
            "label": "Open output settings",
            "kind": "open_live_target_settings",
            "target_id": target_id,
            "enabled": True,
        }
    if "record to file" in text:
        return {
            "id": "test_record_file",
            "label": "Test record to file",
            "kind": "run_action",
            "action_id": "broadcast.live_target.summary",
            "params": {"target_id": "record_file"},
            "enabled": True,
        }
    if "obs virtual camera" in text or "window capture" in text:
        return {
            "id": "open_obs_bridge_plan",
            "label": "Open OBS bridge plan",
            "kind": "run_action",
            "action_id": "broadcast.virtual_camera.obs_bridge_plan",
            "enabled": True,
        }
    if "program output" in text and "screen-share" in text or "screen-share picker" in text:
        return {
            "id": "share_program_output",
            "label": "Show window-share steps",
            "kind": "show_window_share_steps",
            "enabled": True,
        }
    return {
        "id": "manual_check",
        "label": "Mark after checking",
        "kind": "manual_completion",
        "enabled": True,
    }


def _open_dashboard_action(platform: Mapping[str, Any], *, fallback_id: str) -> dict[str, Any]:
    url = str(platform.get("dashboard_url") or "").strip()
    return {
        "id": fallback_id,
        "label": f"Open {platform.get('dashboard') or 'platform dashboard'}",
        "kind": "open_url" if url else "manual_completion",
        "url": url,
        "enabled": bool(url),
    }
