"""Media import and basic track action registrations."""
from __future__ import annotations

from typing import Any, Mapping

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def register_media_track_actions(registry: Any) -> None:
    """Register media pool import and base track add/remove actions."""
    registry.register_adapter_action(
        "media.import_to_timeline",
        "Import media and place it on a timeline track.",
        "media",
        "import_to_timeline",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "kind": {"type": "string", "enum": ["video", "audio", ""]},
                "track_id": {"type": "integer"},
                "at_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
                "name": {"type": "string"},
            },
            required=("path",),
        ),
        required=("path",),
        undo_label="Import media to timeline",
        async_kind="media_import",
        dry_summary="media file would be imported and placed on the timeline",
    )
    registry.register(
        ActionSpec(
            "media.import",
            "Import one media file into the media pool.",
            "media",
            params_schema=schema_object(
                {"path": {"type": "string"}, "target": {"type": "string"}},
                required=("path",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Import media",
            async_kind="media_import",
        ),
        lambda params, dry: _media_import(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "track.add",
            "Add a video or audio track.",
            "track",
            params_schema=schema_object(
                {
                    "kind": {"type": "string", "enum": ["video", "audio"]},
                    "name": {"type": "string"},
                    "track_id": {"type": "integer"},
                }
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Add track",
        ),
        lambda params, dry: _track_add(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "track.remove",
            "Remove a video or audio track.",
            "track",
            params_schema=schema_object(
                {
                    "kind": {"type": "string", "enum": ["video", "audio"]},
                    "track_id": {"type": "integer"},
                    "force": {"type": "boolean"},
                },
                required=("track_id",),
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Remove track",
        ),
        lambda params, dry: _track_remove(registry, params, dry),
    )


def _media_import(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if not str(params.get("path") or "").strip():
        return error_result("media.import", "path is required", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("media.import", params, "media file would be imported")
    return ok_result(
        "media.import",
        registry.adapter.import_media(str(params.get("path")), target=str(params.get("target") or "")),
        changed=True,
    )


def _track_add(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    kind = str(params.get("kind") or "video").strip().lower()
    if kind not in {"video", "audio"}:
        return error_result("track.add", "kind must be video or audio", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("track.add", params, f"{kind} track would be added")
    track_id = params.get("track_id") if "track_id" in params else None
    return ok_result(
        "track.add",
        registry.adapter.add_track(kind=kind, name=str(params.get("name") or ""), track_id=track_id),
        changed=True,
    )


def _track_remove(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "track_id" not in params:
        return error_result("track.remove", "track_id is required", dry_run=dry_run)
    kind = str(params.get("kind") or "video").strip().lower()
    if kind not in {"video", "audio"}:
        return error_result("track.remove", "kind must be video or audio", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("track.remove", params, f"{kind} track would be removed")
    return ok_result(
        "track.remove",
        registry.adapter.remove_track(
            kind=kind,
            track_id=_as_int(params.get("track_id")),
            force=bool(params.get("force", False)),
        ),
        changed=True,
    )
