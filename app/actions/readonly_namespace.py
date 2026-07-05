"""Read-only status and summary action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def register_readonly_actions(registry: Any) -> None:
    """Register read-only app, project, media, timeline, and selection summaries."""
    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "app.status",
            "Return app and action-system status.",
            "app",
            result_schema=schema_object({"project_summary": {"type": "object"}}),
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("app.status", adapter.app_status()),
    )
    registry.register(
        ActionSpec(
            "project.snapshot",
            "Return a read-only project snapshot.",
            "project",
            params_schema=schema_object({"media_limit": {"type": "integer", "minimum": 0}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "project.snapshot",
            adapter.snapshot(media_limit=_as_int(params.get("media_limit", 200), 200)),
        ),
    )
    registry.register(
        ActionSpec(
            "media.summary",
            "Return media pool items and kind counts.",
            "media",
            params_schema=schema_object({"limit": {"type": "integer", "minimum": 0}}),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "media.summary",
            adapter.media_summary(limit=_as_int(params.get("limit", 200), 200)),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.summary",
            "Return timeline tracks, duration, markers, and selection summary.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.summary", adapter.timeline_summary()),
    )
    registry.register(
        ActionSpec(
            "timeline.nle_status",
            "Return the current NLE edit context: playhead, In/Out, targets, snap, selection, gaps, markers, and clipboard.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.nle_status", adapter.nle_status()),
    )
    registry.register(
        ActionSpec(
            "timeline.range",
            "Return the current global In/Out range.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.range", adapter.in_out_range()),
    )
    registry.register(
        ActionSpec(
            "timeline.edit_points",
            "Return timeline edit points from clip boundaries and optionally markers.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_kind": {"type": "string", "enum": ["video", "audio", "all"]},
                    "track_id": {"type": "integer"},
                    "include_markers": {"type": "boolean"},
                }
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.edit_points",
            adapter.edit_points(
                track_kind=str(params.get("track_kind") or "video"),
                track_id=_as_int(params.get("track_id")) if "track_id" in params else None,
                include_markers=bool(params.get("include_markers", False)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "selected.clip",
            "Return the currently selected clip, if any.",
            "selected",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("selected.clip", adapter.selected_clip()),
    )
    registry.register(
        ActionSpec(
            "selection.summary",
            "Return normalized timeline selection state.",
            "selection",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("selection.summary", adapter.selection_summary()),
    )
