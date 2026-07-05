"""Optional cloud/share provider handoff contracts for CapCut-style projects.

The core app remains local-first.  This module does not upload files, store
tokens, or contact provider APIs.  It builds the explicit safety contract needed
before Google Drive, OneDrive, Dropbox, WebDAV, or another user-approved
provider can be wired in later.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_slug(value: Any, fallback: str = "tigercapture-cloud-package") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._ -]+", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip(".-")
    return text[:80] or fallback


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _contains_sensitive_key(value: Any) -> bool:
    sensitive = ("token", "secret", "password", "credential", "refresh")
    safe_keys = {"token_storage", "no_tokens_in_manifest"}
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text not in safe_keys and any(part in key_text for part in sensitive):
                return True
            if _contains_sensitive_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _package_readme(plan: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    share = _as_dict(plan.get("share_policy"))
    privacy = _as_dict(plan.get("privacy_gate"))
    relink = _as_dict(manifest.get("relink_manifest"))
    return "\n".join(
        [
            "TigerCapture cloud-ready review package",
            "",
            "This folder is local-first. TigerCapture did not upload files, create public links, or store provider tokens.",
            "Put this folder inside a Google Drive, OneDrive, Dropbox, WebDAV, or other sync folder only after the user approves sharing.",
            "",
            f"Link mode: {share.get('link_mode', 'private')}",
            f"Public link allowed: {bool(share.get('public_link_allowed', False))}",
            f"Original media included: {bool(privacy.get('include_original_media', False))}",
            f"Expected media files: {int(relink.get('media_count', 0) or 0)}",
            "",
            "Files",
            "- manifest.json: project snapshot, relink manifest, review notes, and publish handoff.",
            "- cloud_handoff_plan.json: provider, privacy, conflict, and share-link readiness contract.",
            "- review_notes.json: editor-facing review notes and handoff beats.",
            "- relink_manifest.json: media paths and filename keys for repair/relink.",
            "- provider_contracts.json: available share provider contracts; no secrets are stored here.",
            "",
            "Reviewers should relink media from their own disk or approved sync storage before rendering.",
        ]
    )


@dataclass(frozen=True)
class CloudHandoffProvider:
    id: str
    label: str
    kind: str
    configured: bool
    requires_network: bool
    supports: tuple[str, ...]
    description: str
    setup_hint: str = ""


CLOUD_HANDOFF_PROVIDERS: tuple[CloudHandoffProvider, ...] = (
    CloudHandoffProvider(
        "local_sync_folder",
        "Local sync folder",
        "folder",
        True,
        False,
        ("manifest", "review_package", "manual_copy", "watch_folder"),
        "Write a cloud-ready package into a local folder that the user can sync with Drive/OneDrive/Dropbox.",
    ),
    CloudHandoffProvider(
        "google_drive",
        "Google Drive",
        "oauth_drive",
        False,
        True,
        ("project_package", "proxy_media", "review_link", "comment_url"),
        "Reserved provider contract for Google Drive upload/share integration.",
        "Connect Google Drive and approve upload scope before creating links.",
    ),
    CloudHandoffProvider(
        "microsoft_onedrive",
        "OneDrive",
        "oauth_drive",
        False,
        True,
        ("project_package", "proxy_media", "review_link", "tenant_policy"),
        "Reserved provider contract for OneDrive upload/share integration.",
        "Connect OneDrive and approve upload scope before creating links.",
    ),
    CloudHandoffProvider(
        "dropbox",
        "Dropbox",
        "oauth_drive",
        False,
        True,
        ("project_package", "proxy_media", "shared_link"),
        "Reserved provider contract for Dropbox upload/share integration.",
        "Connect Dropbox and approve upload scope before creating links.",
    ),
    CloudHandoffProvider(
        "webdav",
        "WebDAV",
        "webdav",
        False,
        True,
        ("project_package", "manifest_json", "basic_or_token_auth"),
        "Reserved provider contract for self-hosted WebDAV storage.",
        "Configure a WebDAV endpoint and credential profile before upload.",
    ),
    CloudHandoffProvider(
        "s3_compatible",
        "S3-compatible storage",
        "object_storage",
        False,
        True,
        ("project_package", "manifest_json", "signed_url"),
        "Reserved provider contract for S3-compatible object storage.",
        "Configure a bucket, region, and credential profile before upload.",
    ),
    CloudHandoffProvider(
        "custom_share_provider",
        "Custom share provider",
        "custom",
        False,
        True,
        ("manifest_json", "provider_template", "external_automation"),
        "Reserved slot for a user-supplied share-link or automation provider.",
        "Register a custom provider template before creating share links.",
    ),
)


def capcut_cloud_provider_contracts(
    configured: Iterable[str] | None = None,
    *,
    destinations: Mapping[str, str] | None = None,
    include_unconfigured: bool = True,
) -> list[dict[str, Any]]:
    configured_ids = {str(item) for item in configured or () if str(item).strip()}
    destination_map = {str(key): str(value) for key, value in dict(destinations or {}).items() if str(value).strip()}
    rows: list[dict[str, Any]] = []
    for provider in CLOUD_HANDOFF_PROVIDERS:
        is_configured = provider.configured or provider.id in configured_ids
        if not include_unconfigured and not is_configured:
            continue
        row = asdict(provider)
        row["configured"] = is_configured
        row["destination"] = destination_map.get(provider.id, "")
        row["status"] = "ready" if is_configured else "needs_setup"
        row["actions"] = _cloud_provider_actions(provider, is_configured)
        if not is_configured:
            row["warning"] = provider.setup_hint or "Provider is not configured."
        rows.append(row)
    return rows


def _cloud_provider_actions(provider: CloudHandoffProvider, configured: bool) -> list[dict[str, Any]]:
    if not configured:
        return [{"id": f"configure_{provider.id}", "label": "Configure provider", "enabled": True}]
    if provider.id == "local_sync_folder":
        return [
            {"id": "write_cloud_ready_package", "label": "Write package", "enabled": True},
            {"id": "reveal_sync_folder", "label": "Reveal sync folder", "enabled": True},
        ]
    return [
        {"id": f"dry_run_{provider.id}", "label": "Dry-run upload plan", "enabled": True},
        {"id": f"create_{provider.id}_private_link", "label": "Create private link", "enabled": False, "requires_consent": True},
    ]


def capcut_cloud_handoff_plan(
    collab_manifest: Mapping[str, Any] | None = None,
    *,
    configured_providers: Iterable[str] | None = None,
    destinations: Mapping[str, str] | None = None,
    user_consent: bool = False,
    include_original_media: bool = False,
) -> dict[str, Any]:
    manifest = _as_dict(collab_manifest)
    providers = capcut_cloud_provider_contracts(configured_providers, destinations=destinations)
    configured = [row for row in providers if row.get("configured")]
    cloud_configured = [row for row in configured if row.get("requires_network")]
    package = _as_dict(manifest.get("package"))
    relink = _as_dict(manifest.get("relink_manifest"))
    project_snapshot = _as_dict(manifest.get("project_snapshot"))
    review_notes = _as_list(manifest.get("review_notes"))
    publish_handoff = _as_dict(manifest.get("publish_handoff"))
    package_ready = bool(manifest.get("ready") and package.get("manifest_json_ready"))
    cloud_enabled = bool(cloud_configured)
    consent_ok = bool(user_consent)
    upload_ready = bool(package_ready and cloud_enabled and consent_ok)
    package_items = [
        {"id": "project_snapshot", "ready": bool(project_snapshot), "sensitivity": "project_metadata"},
        {"id": "relink_manifest", "ready": bool(relink.get("ok")), "sensitivity": "file_names"},
        {"id": "review_notes", "ready": bool(review_notes), "sensitivity": "timeline_notes"},
        {"id": "publish_handoff", "ready": bool(publish_handoff), "sensitivity": "public_copy"},
        {"id": "provider_contracts", "ready": bool(providers), "sensitivity": "provider_metadata"},
    ]
    if include_original_media:
        package_items.append({
            "id": "original_media",
            "ready": bool(relink.get("media_count", 0)),
            "sensitivity": "original_media",
            "warning": "Original media may contain private content and requires explicit user consent.",
        })
    else:
        package_items.append({
            "id": "proxy_or_relink_only",
            "ready": True,
            "sensitivity": "low",
            "note": "Default package stores relink metadata and review payloads, not original media uploads.",
        })
    privacy_gate = {
        "requires_user_consent": True,
        "user_consent": consent_ok,
        "include_original_media": bool(include_original_media),
        "private_link_default": True,
        "public_link_allowed": False,
        "token_storage": "external_provider_only",
        "no_tokens_in_manifest": True,
        "ready": bool((not cloud_enabled) or consent_ok),
    }
    conflict_policy = {
        "duplicate_filename": "warn_and_keep_both",
        "remote_existing_project": "create_revision_folder",
        "overwrite": "never_without_user_confirmation",
        "missing_media": "keep_relink_manifest",
        "ready": True,
    }
    share_policy = {
        "link_mode": "private",
        "link_ready": upload_ready,
        "default_expiry_days": 7,
        "comments_enabled": False,
        "approval_required": True,
        "provider_ids": [str(row.get("id")) for row in cloud_configured],
    }
    return {
        "kind": "capcut_cloud_handoff_plan",
        "ok": bool(providers and package_items and privacy_gate["no_tokens_in_manifest"]),
        "ready": upload_ready,
        "local_first": True,
        "cloud_enabled": cloud_enabled,
        "upload_attempted": False,
        "safe_by_default": not cloud_enabled and not upload_ready,
        "provider_count": len(providers),
        "configured_provider_count": len(configured),
        "cloud_provider_count": len(cloud_configured),
        "providers": providers,
        "package_ready": package_ready,
        "package_items": package_items,
        "privacy_gate": privacy_gate,
        "conflict_policy": conflict_policy,
        "share_policy": share_policy,
        "actions": [
            {"id": "write_cloud_ready_package", "label": "Write cloud-ready package", "enabled": package_ready},
            {"id": "configure_cloud_provider", "label": "Configure cloud provider", "enabled": True},
            {"id": "dry_run_upload", "label": "Dry-run upload", "enabled": bool(package_ready and cloud_enabled)},
            {"id": "create_private_share_link", "label": "Create private share link", "enabled": upload_ready},
        ],
        "warnings": [
            warning
            for warning in [
                "No cloud provider is configured; package stays local." if not cloud_enabled else "",
                "User consent is required before upload/share-link creation." if cloud_enabled and not consent_ok else "",
                "Original media upload is disabled by default." if not include_original_media else "",
            ]
            if warning
        ],
    }


def capcut_write_cloud_ready_package(
    collab_manifest: Mapping[str, Any] | None,
    output_dir: str | Path,
    *,
    configured_providers: Iterable[str] | None = None,
    destinations: Mapping[str, str] | None = None,
    user_consent: bool = False,
    include_original_media: bool = False,
) -> dict[str, Any]:
    """Write a local cloud-ready review package without uploading anything."""
    manifest = _as_dict(collab_manifest)
    plan = capcut_cloud_handoff_plan(
        manifest,
        configured_providers=configured_providers,
        destinations=destinations,
        user_consent=user_consent,
        include_original_media=include_original_media,
    )
    package_ready = bool(plan.get("package_ready"))
    target = Path(output_dir)
    project_snapshot = _as_dict(manifest.get("project_snapshot"))
    project_name = (
        project_snapshot.get("project_path")
        or _as_dict(project_snapshot.get("project_settings_patch")).get("starter_template_id")
        or "tigercapture-cloud-package"
    )
    package_id = _safe_slug(project_name)
    package_dir = target / package_id if target.suffix else target
    blocked_reason = ""
    if not package_ready:
        blocked_reason = "Collaboration manifest is not package-ready."
    elif _contains_sensitive_key(manifest) or _contains_sensitive_key(plan):
        blocked_reason = "Package payload contains a sensitive key such as token, secret, password, or credential."
    if blocked_reason:
        return {
            "kind": "capcut_cloud_ready_package",
            "ok": False,
            "ready": False,
            "path": str(package_dir),
            "upload_attempted": False,
            "blocked_reason": blocked_reason,
            "plan": plan,
            "files": [],
        }

    review_notes = {"review_notes": _as_list(manifest.get("review_notes"))}
    relink_manifest = _as_dict(manifest.get("relink_manifest"))
    provider_contracts = {
        "providers": _as_list(plan.get("providers")),
        "configured_provider_count": int(plan.get("configured_provider_count", 0) or 0),
        "cloud_provider_count": int(plan.get("cloud_provider_count", 0) or 0),
    }
    payloads: dict[str, bytes] = {
        "manifest.json": _json_bytes(manifest),
        "cloud_handoff_plan.json": _json_bytes(plan),
        "review_notes.json": _json_bytes(review_notes),
        "relink_manifest.json": _json_bytes(relink_manifest),
        "provider_contracts.json": _json_bytes(provider_contracts),
        "README.txt": _package_readme(plan, manifest).encode("utf-8"),
    }
    index = {
        "kind": "capcut_cloud_ready_package_index",
        "package_id": package_id,
        "local_first": True,
        "upload_attempted": False,
        "includes_original_media": bool(include_original_media),
        "file_count": len(payloads) + 1,
        "files": [{"path": name, "size_bytes": len(data)} for name, data in payloads.items()],
        "privacy_gate": _as_dict(plan.get("privacy_gate")),
        "share_policy": _as_dict(plan.get("share_policy")),
    }
    payloads["package_index.json"] = _json_bytes(index)

    package_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for name, data in payloads.items():
        path = package_dir / name
        path.write_bytes(data)
        written.append({"path": str(path), "name": name, "size_bytes": len(data)})

    return {
        "kind": "capcut_cloud_ready_package",
        "ok": True,
        "ready": True,
        "path": str(package_dir),
        "upload_attempted": False,
        "safe_by_default": bool(plan.get("safe_by_default")),
        "includes_original_media": bool(include_original_media),
        "file_count": len(written),
        "size_bytes": sum(int(row["size_bytes"]) for row in written),
        "files": written,
        "plan": plan,
        "warnings": list(_as_list(plan.get("warnings"))),
    }


def capcut_cloud_handoff_report(collab_manifest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    default_plan = capcut_cloud_handoff_plan(collab_manifest)
    configured_plan = capcut_cloud_handoff_plan(
        collab_manifest,
        configured_providers=("google_drive",),
        destinations={"google_drive": "TigerCapture Reviews/Product Demo"},
        user_consent=True,
    )
    checks = {
        "provider_contracts_present": int(default_plan.get("provider_count", 0) or 0) >= 7,
        "drive_providers_present": all(
            any(row.get("id") == provider_id for row in _as_list(default_plan.get("providers")))
            for provider_id in ("google_drive", "microsoft_onedrive", "dropbox", "webdav")
        ),
        "default_no_cloud_upload": bool(default_plan.get("safe_by_default")),
        "privacy_gate_requires_consent": bool((_as_dict(default_plan.get("privacy_gate"))).get("requires_user_consent")),
        "private_link_default": bool((_as_dict(default_plan.get("privacy_gate"))).get("private_link_default")),
        "no_tokens_in_manifest": bool((_as_dict(default_plan.get("privacy_gate"))).get("no_tokens_in_manifest")),
        "conflict_policy_safe": bool((_as_dict(default_plan.get("conflict_policy"))).get("ready"))
        and _as_dict(default_plan.get("conflict_policy")).get("overwrite") == "never_without_user_confirmation",
        "configured_provider_dry_run_ready": bool(configured_plan.get("ready")),
        "share_link_not_ready_without_provider": not bool((_as_dict(default_plan.get("share_policy"))).get("link_ready")),
        "package_contains_relink_manifest": any(row.get("id") == "relink_manifest" and row.get("ready") for row in _as_list(default_plan.get("package_items"))),
        "local_package_writer_contract_ready": bool(default_plan.get("package_ready") and default_plan.get("local_first")),
    }
    return {
        "kind": "capcut_cloud_handoff",
        "ok": all(checks.values()),
        "score": round(100 * sum(1 for value in checks.values() if value) / max(1, len(checks)), 2),
        "checks": checks,
        "summary": {
            "provider_count": int(default_plan.get("provider_count", 0) or 0),
            "configured_provider_count": int(default_plan.get("configured_provider_count", 0) or 0),
            "cloud_provider_count": int(default_plan.get("cloud_provider_count", 0) or 0),
            "configured_dry_run_ready": bool(configured_plan.get("ready")),
            "default_safe_by_default": bool(default_plan.get("safe_by_default")),
            "package_ready": bool(default_plan.get("package_ready")),
            "local_package_writer_contract_ready": bool(checks["local_package_writer_contract_ready"]),
        },
        "default_plan": default_plan,
        "configured_simulation": configured_plan,
    }
