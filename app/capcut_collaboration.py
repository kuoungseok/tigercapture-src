"""Local-first CapCut-style collaboration and share handoff contracts.

This is not a cloud sync implementation.  It creates the product-facing
package/review/relink/provider contract that a local desktop editor needs before
any optional cloud, mobile, or workspace integration can be safe.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


@dataclass(frozen=True)
class CollabProvider:
    id: str
    label: str
    kind: str
    configured: bool
    requires_network: bool
    supports: tuple[str, ...]
    description: str
    setup_hint: str = ""


BUILTIN_COLLAB_PROVIDERS: tuple[CollabProvider, ...] = (
    CollabProvider(
        "local_review_package",
        "Local review package",
        "local_manifest",
        True,
        False,
        ("manifest", "project_snapshot", "render_jobs", "review_notes"),
        "Create a portable local review package without network access.",
    ),
    CollabProvider(
        "project_snapshot",
        "Project snapshot",
        "snapshot",
        True,
        False,
        ("settings", "timeline_markers", "subtitles", "workflow_presets"),
        "Capture the edit state needed to reopen or repair a shared project.",
    ),
    CollabProvider(
        "media_relink_manifest",
        "Media relink manifest",
        "relink",
        True,
        False,
        ("expected_media", "search_roots", "filename_keys", "missing_state"),
        "Record media references and search roots so another machine can relink safely.",
    ),
    CollabProvider(
        "review_notes",
        "Review notes",
        "review",
        True,
        False,
        ("markers", "captions", "thumbnail_ms", "publish_copy"),
        "Bundle editor review notes, short ranges, caption beats, and publish handoff copy.",
    ),
    CollabProvider(
        "manual_archive",
        "Manual archive handoff",
        "archive",
        True,
        False,
        ("zip_ready", "manifest_json", "checksums", "readme"),
        "Prepare a deterministic folder/zip handoff for manual transfer.",
    ),
    CollabProvider(
        "workspace_sync_slot",
        "Workspace sync slot",
        "workspace_sync",
        False,
        True,
        ("project_sync", "comments", "timeline_lock"),
        "Reserved slot for a user-approved workspace/cloud collaboration provider.",
        "Configure an explicit workspace provider before uploading project data.",
    ),
    CollabProvider(
        "mobile_companion_slot",
        "Mobile companion slot",
        "mobile",
        False,
        True,
        ("mobile_review", "handoff_link", "proxy_package"),
        "Reserved slot for mobile review or companion app handoff.",
        "Configure a mobile/share provider before creating mobile links.",
    ),
    CollabProvider(
        "cloud_comment_slot",
        "Cloud comments slot",
        "comments",
        False,
        True,
        ("review_comments", "approval_state", "share_url"),
        "Reserved slot for hosted comments and approvals.",
        "Configure a comments provider before publishing review links.",
    ),
)


def _bundle_from_input(
    bundle_or_summary: Mapping[str, Any] | None,
    media_items: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    source = _as_dict(bundle_or_summary)
    if any(key in source for key in ("project_settings_patch", "subtitle_rows", "timeline_markers", "render_queue_jobs")):
        return dict(source)
    try:
        from app.capcut_workflow import capcut_creator_apply_bundle

        return capcut_creator_apply_bundle(
            source,
            list(media_items or _as_list(source.get("media_items"))),
            include_review_panel=False,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "summary": source,
            "subtitle_rows": [],
            "timeline_markers": [],
            "render_queue_jobs": [],
        }


def capcut_collab_provider_contracts(
    configured: Iterable[str] | None = None,
    *,
    include_unconfigured: bool = True,
) -> list[dict[str, Any]]:
    configured_ids = {str(item) for item in configured or () if str(item).strip()}
    rows: list[dict[str, Any]] = []
    for provider in BUILTIN_COLLAB_PROVIDERS:
        configured_value = provider.configured or provider.id in configured_ids
        if not include_unconfigured and not configured_value:
            continue
        row = asdict(provider)
        row["configured"] = configured_value
        row["status"] = "ready" if configured_value else "needs_setup"
        row["actions"] = _provider_actions(provider, configured_value)
        if not configured_value:
            row["warning"] = provider.setup_hint or "Provider is not configured."
        rows.append(row)
    return rows


def _provider_actions(provider: CollabProvider, configured: bool) -> list[dict[str, Any]]:
    if not configured:
        return [{"id": f"configure_{provider.id}", "label": "Configure provider", "enabled": True}]
    if provider.id == "local_review_package":
        return [{"id": "write_collab_manifest", "label": "Write review manifest", "enabled": True}]
    if provider.id == "media_relink_manifest":
        return [{"id": "open_relink_browser", "label": "Open missing media browser", "enabled": True}]
    if provider.id == "review_notes":
        return [{"id": "copy_review_notes", "label": "Copy review notes", "enabled": True}]
    if provider.id == "manual_archive":
        return [{"id": "reveal_archive_folder", "label": "Reveal package folder", "enabled": True}]
    return [{"id": f"use_{provider.id}", "label": f"Use {provider.label}", "enabled": True}]


def _media_rows(summary: Mapping[str, Any], media_items: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    source_rows = list(media_items or _as_list(summary.get("media_items")) or _as_list(summary.get("media")) or [])
    out: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows, start=1):
        item = _as_dict(row)
        path = str(item.get("path") or item.get("source_path") or item.get("file") or "")
        name = str(item.get("name") or (Path(path).name if path else f"media-{index}"))
        out.append({
            "id": str(item.get("id") or f"media-{index}"),
            "name": name,
            "path": path,
            "kind": str(item.get("kind") or "media"),
            "duration_s": float(item.get("duration_s", 0) or 0),
            "filename_key": Path(path or name).name.casefold(),
            "relink_required": not bool(path),
        })
    return out


def capcut_collab_handoff_manifest(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    project_path: str | Path = "",
    search_roots: Iterable[str | Path] = (),
    configured_providers: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Build a serializable local collaboration/review package manifest."""
    bundle = _bundle_from_input(bundle_or_summary, media_items)
    summary = _as_dict(bundle.get("summary") or bundle_or_summary)
    markers = [_as_dict(row) for row in _as_list(bundle.get("timeline_markers"))]
    subtitles = [_as_dict(row) for row in _as_list(bundle.get("subtitle_rows"))]
    render_jobs = [_as_dict(row) for row in _as_list(bundle.get("render_queue_jobs"))]
    publish_handoff = _as_dict(bundle.get("publish_handoff"))
    clipboard = _as_dict(publish_handoff.get("clipboard_payloads"))
    media = _media_rows(summary, media_items)
    roots = [str(Path(root)) for root in search_roots if str(root).strip()]
    providers = capcut_collab_provider_contracts(configured_providers)
    configured = [row for row in providers if row.get("configured")]
    network_defaults = [row for row in configured if row.get("requires_network")]
    relink_manifest = {
        "ok": True,
        "expected_media": media,
        "media_count": len(media),
        "missing_count": sum(1 for row in media if row.get("relink_required")),
        "search_roots": roots,
        "filename_keys": [row["filename_key"] for row in media],
        "conflict_policy": "warn_on_duplicate_filename",
    }
    review_notes = [
        {"id": "short_ranges", "label": "Short ranges", "count": len(markers), "ready": bool(markers)},
        {"id": "captions", "label": "Captions", "count": len(subtitles), "ready": bool(subtitles)},
        {"id": "render_jobs", "label": "Render jobs", "count": len(render_jobs), "ready": bool(render_jobs)},
        {"id": "publish_copy", "label": "Publish copy", "count": len([v for v in clipboard.values() if str(v).strip()]), "ready": bool(clipboard)},
    ]
    project_snapshot = {
        "project_path": str(Path(project_path)) if project_path else "",
        "duration_s": float(summary.get("duration_s", 0) or 0),
        "project_settings_patch": _as_dict(bundle.get("project_settings_patch")),
        "workflow_preset_ids": [str(item) for item in _as_list(bundle.get("workflow_preset_ids"))],
        "timeline_marker_count": len(markers),
        "subtitle_count": len(subtitles),
        "render_job_count": len(render_jobs),
    }
    package_ready = bool(markers and subtitles and render_jobs)
    return {
        "kind": "capcut_collab_handoff_manifest",
        "version": 1,
        "ok": True,
        "ready": package_ready,
        "local_first": True,
        "cloud_required": bool(network_defaults),
        "project_snapshot": project_snapshot,
        "relink_manifest": relink_manifest,
        "review_notes": review_notes,
        "publish_handoff": publish_handoff,
        "providers": providers,
        "provider_count": len(providers),
        "configured_provider_count": len(configured),
        "network_provider_count": len(network_defaults),
        "package": {
            "zip_ready": package_ready,
            "manifest_json_ready": True,
            "readme_ready": True,
            "contains": ["project_snapshot", "relink_manifest", "review_notes", "publish_handoff", "provider_contracts"],
        },
    }


def capcut_collab_review_model(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    project_path: str | Path = "",
    search_roots: Iterable[str | Path] = (),
    configured_providers: Iterable[str] | None = None,
) -> dict[str, Any]:
    manifest = capcut_collab_handoff_manifest(
        bundle_or_summary,
        media_items,
        project_path=project_path,
        search_roots=search_roots,
        configured_providers=configured_providers,
    )
    providers = _as_list(manifest.get("providers"))
    optional = [row for row in providers if not _as_dict(row).get("configured")]
    relink = _as_dict(manifest.get("relink_manifest"))
    package = _as_dict(manifest.get("package"))
    notes = _as_list(manifest.get("review_notes"))
    no_network_default = int(manifest.get("network_provider_count", 0) or 0) == 0
    try:
        from app.capcut_cloud_handoff import capcut_cloud_handoff_plan

        cloud_handoff = capcut_cloud_handoff_plan(manifest)
    except Exception as exc:
        cloud_handoff = {
            "ok": False,
            "ready": False,
            "error": str(exc),
            "provider_count": 0,
            "providers": [],
            "privacy_gate": {},
            "warnings": [],
        }
    checks = {
        "local_package_ready": bool(package.get("zip_ready") and package.get("manifest_json_ready")),
        "project_snapshot_ready": bool(_as_dict(manifest.get("project_snapshot")).get("project_settings_patch")),
        "relink_manifest_ready": bool(relink.get("ok")),
        "review_notes_ready": all(bool(_as_dict(row).get("ready")) for row in notes),
        "provider_contracts_present": len(providers) >= 8,
        "optional_cloud_slots_explicit": len(optional) >= 3 and all(bool(_as_dict(row).get("warning")) for row in optional),
        "no_network_upload_default": no_network_default,
        "cloud_handoff_contract_ready": bool(cloud_handoff.get("ok") and _as_dict(cloud_handoff.get("privacy_gate")).get("private_link_default")),
    }
    score = round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2)
    cards = [
        {
            "id": "local_package",
            "label": "Local package",
            "ready": checks["local_package_ready"],
            "accent": "#FFB454",
            "rows": [_as_dict(manifest.get("project_snapshot")), package],
        },
        {
            "id": "media_relink",
            "label": "Media relink",
            "ready": checks["relink_manifest_ready"],
            "accent": "#6EA8FF",
            "rows": _as_list(relink.get("expected_media")),
            "summary": f"{int(relink.get('media_count', 0) or 0)} media item(s), {int(relink.get('missing_count', 0) or 0)} missing",
        },
        {
            "id": "review_notes",
            "label": "Review notes",
            "ready": checks["review_notes_ready"],
            "accent": "#5BE7C4",
            "rows": notes,
        },
        {
            "id": "providers",
            "label": "Collaboration providers",
            "ready": checks["provider_contracts_present"],
            "accent": "#8A7CFF",
            "rows": providers,
        },
        {
            "id": "local_first_guard",
            "label": "Local-first guard",
            "ready": checks["no_network_upload_default"],
            "accent": "#FF6F61",
            "rows": [
                {"id": "network_provider_count", "value": int(manifest.get("network_provider_count", 0) or 0)},
                {"id": "optional_slots", "value": len(optional)},
            ],
        },
        {
            "id": "cloud_handoff",
            "label": "Cloud handoff",
            "ready": checks["cloud_handoff_contract_ready"],
            "accent": "#61D8FF",
            "summary": (
                f"{int(cloud_handoff.get('provider_count', 0) or 0)} provider contract(s), "
                f"cloud={'on' if cloud_handoff.get('cloud_enabled') else 'off'}"
            ),
            "rows": [
                _as_dict(cloud_handoff.get("privacy_gate")),
                _as_dict(cloud_handoff.get("conflict_policy")),
                _as_dict(cloud_handoff.get("share_policy")),
            ],
            "warnings": list(_as_list(cloud_handoff.get("warnings"))),
        },
    ]
    actions = [
        {"id": "write_collab_manifest", "label": "Write collaboration manifest", "enabled": bool(manifest.get("ready"))},
        {"id": "open_relink_browser", "label": "Open relink browser", "enabled": bool(relink.get("ok"))},
        {"id": "copy_review_notes", "label": "Copy review notes", "enabled": checks["review_notes_ready"]},
        {"id": "configure_workspace_provider", "label": "Configure workspace provider", "enabled": bool(optional), "count": len(optional)},
        {"id": "write_cloud_ready_package", "label": "Write cloud-ready package", "enabled": bool(cloud_handoff.get("package_ready"))},
    ]
    return {
        "kind": "capcut_collab_handoff",
        "ok": all(checks.values()),
        "ready": bool(score >= 85 and manifest.get("ready")),
        "score": score,
        "checks": checks,
        "cards": cards,
        "card_count": len(cards),
        "ready_card_count": sum(1 for card in cards if card.get("ready")),
        "actions": actions,
        "provider_count": len(providers),
        "configured_provider_count": int(manifest.get("configured_provider_count", 0) or 0),
        "cloud_handoff": cloud_handoff,
        "manifest": manifest,
        "summary": {
            "media_count": int(relink.get("media_count", 0) or 0),
            "missing_media": int(relink.get("missing_count", 0) or 0),
            "review_note_count": len(notes),
            "provider_count": len(providers),
            "configured_provider_count": int(manifest.get("configured_provider_count", 0) or 0),
            "optional_provider_count": len(optional),
            "network_provider_count": int(manifest.get("network_provider_count", 0) or 0),
            "cloud_provider_contracts": int(cloud_handoff.get("provider_count", 0) or 0),
            "cloud_handoff_ready": bool(cloud_handoff.get("ready")),
            "cloud_safe_by_default": bool(cloud_handoff.get("safe_by_default")),
            "package_ready": bool(package.get("zip_ready")),
        },
    }
