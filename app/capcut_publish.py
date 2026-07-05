"""CapCut-style publish review and provider contracts.

The editor can prepare creator exports without pretending to be a cloud
publishing platform.  This module keeps that boundary explicit: local package,
clipboard, manual upload, and optional provider slots are modeled as reviewable
handoff contracts.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


PLATFORM_UPLOAD_URLS: dict[str, str] = {
    "tiktok": "https://www.tiktok.com/upload",
    "instagram": "https://www.instagram.com/",
    "reels": "https://www.instagram.com/",
    "x": "https://x.com/compose/post",
}


@dataclass(frozen=True)
class PublishProvider:
    id: str
    label: str
    kind: str
    configured: bool
    requires_network: bool
    supports: tuple[str, ...]
    description: str
    platform: str = ""
    setup_hint: str = ""


BUILTIN_PUBLISH_PROVIDERS: tuple[PublishProvider, ...] = (
    PublishProvider(
        "local_package",
        "Local publish package",
        "local_manifest",
        True,
        False,
        ("manifest", "render_queue", "copy", "thumbnail"),
        "Write a local handoff manifest next to exported files.",
    ),
    PublishProvider(
        "clipboard",
        "Clipboard copy",
        "clipboard",
        True,
        False,
        ("title", "description", "hashtags", "thumbnail_ms"),
        "Copy title, description, hashtags, and thumbnail timing for manual publishing.",
    ),
    PublishProvider(
        "manual_upload_tiktok",
        "TikTok manual upload",
        "manual_upload",
        True,
        False,
        ("video", "title", "description", "hashtags", "safe_zone"),
        "Prepare a TikTok-ready package for manual browser/mobile upload.",
    ),
    PublishProvider(
        "manual_upload_shorts",
        "YouTube Shorts manual upload",
        "manual_upload",
        True,
        False,
        ("video", "title", "description", "hashtags", "thumbnail"),
        "Prepare a Shorts-ready package for manual browser upload.",
    ),
    PublishProvider(
        "manual_upload_reels",
        "Reels manual upload",
        "manual_upload",
        True,
        False,
        ("video", "title", "description", "hashtags", "safe_zone"),
        "Prepare a Reels-ready package for manual upload.",
        "reels",
    ),
    PublishProvider(
        "quick_upload_tiktok",
        "TikTok quick upload",
        "browser_upload",
        True,
        False,
        ("open_upload_page", "video", "title", "hashtags", "privacy_checklist"),
        "Open TikTok upload with the export package and copy ready.",
        "tiktok",
    ),
    PublishProvider(
        "quick_upload_instagram",
        "Instagram/Reels quick upload",
        "browser_upload",
        True,
        False,
        ("open_upload_page", "video", "caption", "hashtags", "safe_zone"),
        "Open Instagram/Reels with the export package and caption ready.",
        "instagram",
    ),
    PublishProvider(
        "quick_upload_x",
        "X quick upload",
        "browser_upload",
        True,
        False,
        ("open_compose", "video", "post_text", "hashtags"),
        "Open X compose with the export package and post text ready.",
        "x",
    ),
    PublishProvider(
        "share_link_provider",
        "Optional share-link provider",
        "share_link",
        False,
        True,
        ("manifest", "share_url", "download_url"),
        "Reserved slot for a user-approved share-link integration.",
    ),
    PublishProvider(
        "api_upload_tiktok",
        "TikTok API upload",
        "api_upload",
        False,
        True,
        ("oauth", "video.publish", "file_upload", "publish_status"),
        "Reserved slot for TikTok Content Posting API direct post after app review and user authorization.",
        "tiktok",
        "Requires approved TikTok Content Posting API access and the user's video.publish authorization.",
    ),
    PublishProvider(
        "api_upload_instagram",
        "Instagram API upload",
        "api_upload",
        False,
        True,
        ("oauth", "content_publishing", "media_container", "publish_status"),
        "Reserved slot for Instagram Graph API publishing after Meta app/account setup.",
        "instagram",
        "Requires Meta app review, an eligible Instagram professional account, and publishing permissions.",
    ),
    PublishProvider(
        "api_upload_x",
        "X API upload",
        "api_upload",
        False,
        True,
        ("oauth", "media_upload", "post_create", "publish_status"),
        "Reserved slot for X media upload and post creation after API credentials are configured.",
        "x",
        "Requires X API access, OAuth, media upload, and post creation permissions.",
    ),
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_text(values: Iterable[Any]) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _safe_slug(value: Any, fallback: str = "publish-package") -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._ -]+", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip(".-")
    return text[:80] or fallback


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _publish_package(bundle_or_package: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_dict(bundle_or_package)
    return _as_dict(payload.get("publish_package")) if "publish_package" in payload else payload


def _publish_variants(bundle_or_package: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_dict(bundle_or_package)
    return _as_dict(payload.get("publish_variants"))


def _publish_handoff(bundle_or_package: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = _as_dict(bundle_or_package)
    handoff = _as_dict(payload.get("publish_handoff"))
    if handoff:
        return handoff
    package = _publish_package(payload)
    title = _first_text(_as_list(package.get("title_suggestions")))
    hashtags = [str(item).strip() for item in _as_list(package.get("hashtags")) if str(item).strip()]
    description_template = str(package.get("description_template") or "{title}\n\n{hashtags}")
    description = description_template.replace("{title}", title).replace("{hashtags}", " ".join(hashtags))
    thumbnail = _as_dict((_as_list(package.get("thumbnail_frames")) or [{}])[0])
    return {
        "ok": True,
        "ready": bool(title and hashtags and package.get("ready")),
        "clipboard_payloads": {
            "title": title,
            "description": description,
            "hashtags": " ".join(hashtags),
            "thumbnail_ms": int(thumbnail.get("ms", 0) or 0),
        },
        "thumbnail_frame": thumbnail,
        "actions": [],
    }


def _quick_upload_rows(
    variants: Iterable[Mapping[str, Any]],
    clipboard: Mapping[str, Any],
    export_paths: Iterable[str | Path] = (),
) -> list[dict[str, Any]]:
    platform_map = {"tiktok": "TikTok", "reels": "Instagram Reels", "instagram": "Instagram Reels", "x": "X"}
    available_exports = [str(Path(path)) for path in export_paths if str(path).strip()]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in variants:
        row = _as_dict(raw)
        platform = str(row.get("platform") or "").casefold()
        if platform == "shorts":
            continue
        if platform not in platform_map or platform in seen:
            continue
        seen.add(platform)
        title = str(row.get("title") or clipboard.get("title") or "").strip()
        hashtags = " ".join(str(item).strip() for item in _as_list(row.get("hashtags")) if str(item).strip())
        if not hashtags:
            hashtags = str(clipboard.get("hashtags") or "").strip()
        if platform in {"reels", "instagram"}:
            canonical = "instagram"
            post_text = "\n\n".join(part for part in (title, hashtags) if part)
        elif platform == "x":
            canonical = "x"
            post_text = " ".join(part for part in (title, hashtags) if part).strip()[:280]
        else:
            canonical = platform
            post_text = " ".join(part for part in (title, hashtags) if part).strip()
        rows.append(
            {
                "id": f"quick_upload_{canonical}",
                "platform": canonical,
                "label": platform_map[platform],
                "ready": bool(row.get("ready") and title),
                "upload_url": PLATFORM_UPLOAD_URLS.get(canonical, ""),
                "export_path": available_exports[0] if available_exports else "",
                "post_text": post_text,
                "title": title,
                "hashtags": hashtags,
                "mode": "browser_handoff",
                "api_upload_ready": False,
                "requires_manual_confirm": True,
            }
        )
    if "x" not in seen:
        title = str(clipboard.get("title") or "").strip()
        hashtags = str(clipboard.get("hashtags") or "").strip()
        rows.append(
            {
                "id": "quick_upload_x",
                "platform": "x",
                "label": "X",
                "ready": bool(title),
                "upload_url": PLATFORM_UPLOAD_URLS["x"],
                "export_path": available_exports[0] if available_exports else "",
                "post_text": " ".join(part for part in (title, hashtags) if part).strip()[:280],
                "title": title,
                "hashtags": hashtags,
                "mode": "browser_handoff",
                "api_upload_ready": False,
                "requires_manual_confirm": True,
            }
        )
    return rows


def publish_provider_contracts(
    configured: Iterable[str] | None = None,
    *,
    include_unconfigured: bool = True,
) -> list[dict[str, Any]]:
    configured_ids = {str(item) for item in configured or () if str(item).strip()}
    rows: list[dict[str, Any]] = []
    for provider in BUILTIN_PUBLISH_PROVIDERS:
        configured_value = provider.configured or provider.id in configured_ids
        if not include_unconfigured and not configured_value:
            continue
        rows.append({
            **asdict(provider),
            "configured": configured_value,
            "status": "ready" if configured_value else "needs_setup",
            "actions": _provider_actions(provider, configured_value),
        })
    return rows


def _provider_actions(provider: PublishProvider, configured: bool) -> list[dict[str, Any]]:
    if not configured:
        return [{"id": f"configure_{provider.id}", "label": "Configure provider", "enabled": True, "setup_hint": provider.setup_hint}]
    if provider.id == "local_package":
        return [{"id": "write_publish_manifest", "label": "Write local manifest", "enabled": True}]
    if provider.id == "clipboard":
        return [
            {"id": "copy_title", "label": "Copy title", "enabled": True},
            {"id": "copy_description", "label": "Copy description", "enabled": True},
            {"id": "copy_hashtags", "label": "Copy hashtags", "enabled": True},
        ]
    if provider.kind == "manual_upload":
        return [{"id": f"open_{provider.id}_checklist", "label": "Open manual upload checklist", "enabled": True}]
    if provider.kind == "browser_upload":
        return [
            {
                "id": f"open_{provider.id}",
                "label": "Open upload page",
                "enabled": True,
                "platform": provider.platform,
                "url": PLATFORM_UPLOAD_URLS.get(provider.platform, ""),
            }
        ]
    if provider.kind == "api_upload":
        return [{"id": f"dry_run_{provider.id}", "label": "Dry-run API upload", "enabled": True}]
    if provider.kind == "share_link":
        return [{"id": "create_share_link", "label": "Create share link", "enabled": True}]
    return [{"id": f"use_{provider.id}", "label": "Use provider", "enabled": True}]


def capcut_publish_review_model(
    bundle_or_package: Mapping[str, Any] | None = None,
    *,
    configured_providers: Iterable[str] | None = None,
    export_paths: Iterable[str | Path] = (),
) -> dict[str, Any]:
    """Build a UI-ready review model for social publish handoff."""
    payload = _as_dict(bundle_or_package)
    package = _publish_package(payload)
    variants = _publish_variants(payload)
    handoff = _publish_handoff(payload)
    clipboard = _as_dict(handoff.get("clipboard_payloads"))
    thumbnail = _as_dict(handoff.get("thumbnail_frame") or package.get("thumbnail_frame") or (_as_list(package.get("thumbnail_frames")) or [{}])[0])
    checklist = [_as_dict(row) for row in _as_list(package.get("checklist"))]
    failing_checks = [row for row in checklist if not bool(row.get("ok"))]
    variant_rows = [_as_dict(row) for row in _as_list(variants.get("variants"))]
    if not variant_rows and package.get("platform"):
        variant_rows = [{
            "platform": str(package.get("platform")),
            "label": str(package.get("platform")).title(),
            "ready": bool(package.get("ready")),
            "title": _first_text(_as_list(package.get("title_suggestions"))),
            "hashtags": list(_as_list(package.get("hashtags"))),
            "thumbnail_frame": thumbnail,
            "checklist": checklist,
        }]
    quick_upload_rows = _quick_upload_rows(variant_rows, clipboard, export_paths=export_paths)
    providers = publish_provider_contracts(configured_providers)
    ready_providers = [row for row in providers if row.get("configured")]
    api_upload_providers = [row for row in providers if row.get("kind") == "api_upload"]
    title = str(clipboard.get("title") or _first_text(_as_list(package.get("title_suggestions"))))
    description = str(clipboard.get("description") or "").strip()
    hashtags = str(clipboard.get("hashtags") or " ".join(str(item) for item in _as_list(package.get("hashtags")))).strip()
    cards = [
        {
            "id": "copy",
            "label": "Copy",
            "ready": bool(title and description and hashtags),
            "rows": [
                {"id": "title", "label": "Title", "value": title, "ready": bool(title)},
                {"id": "description", "label": "Description", "value": description, "ready": bool(description)},
                {"id": "hashtags", "label": "Hashtags", "value": hashtags, "ready": bool(hashtags)},
            ],
        },
        {
            "id": "thumbnail",
            "label": "Thumbnail",
            "ready": bool(thumbnail),
            "rows": [thumbnail],
        },
        {
            "id": "platforms",
            "label": "Platforms",
            "ready": any(bool(row.get("ready")) for row in variant_rows),
            "rows": variant_rows,
        },
        {
            "id": "checklist",
            "label": "Checklist",
            "ready": not failing_checks and bool(checklist),
            "rows": checklist,
        },
        {
            "id": "providers",
            "label": "Providers",
            "ready": bool(ready_providers),
            "rows": providers,
        },
        {
            "id": "quick_upload",
            "label": "Quick upload",
            "ready": any(bool(row.get("ready")) for row in quick_upload_rows),
            "rows": quick_upload_rows,
            "summary": f"{sum(1 for row in quick_upload_rows if row.get('ready'))}/{len(quick_upload_rows)} browser handoff(s) ready",
        },
    ]
    actions = [
        {"id": "copy_publish_copy", "label": "Copy publish copy", "enabled": bool(cards[0]["ready"])},
        {"id": "jump_thumbnail", "label": "Jump to thumbnail", "enabled": bool(thumbnail), "ms": int(thumbnail.get("ms", 0) or 0)},
        {"id": "queue_exports", "label": "Queue platform exports", "enabled": any(bool(row.get("ready")) for row in variant_rows)},
        {"id": "write_publish_manifest", "label": "Write local publish package", "enabled": True},
        *[
            {
                "id": f"open_{row.get('id')}",
                "label": f"Open {row.get('label')} upload",
                "enabled": bool(row.get("ready")),
                "url": row.get("upload_url"),
                "platform": row.get("platform"),
            }
            for row in quick_upload_rows
        ],
    ]
    warnings: list[str] = []
    if failing_checks:
        warnings.append(f"{len(failing_checks)} publish checklist item(s) need review.")
    if not any(row.get("id") == "share_link_provider" and row.get("configured") for row in providers):
        warnings.append("Share-link provider is a configured slot; no network upload is performed by default.")
    if not any(row.get("kind") == "api_upload" and row.get("configured") for row in providers):
        warnings.append("Direct X/Instagram/TikTok API upload stays disabled until OAuth/app-review providers are configured.")
    return {
        "ok": True,
        "ready": bool(package.get("ready") and cards[0]["ready"] and cards[2]["ready"]),
        "provider_ready": bool(ready_providers),
        "card_count": len(cards),
        "cards": cards,
        "actions": actions,
        "providers": providers,
        "provider_count": len(providers),
        "configured_provider_count": len(ready_providers),
        "quick_uploads": quick_upload_rows,
        "quick_upload_count": len(quick_upload_rows),
        "ready_quick_upload_count": sum(1 for row in quick_upload_rows if row.get("ready")),
        "api_upload_provider_count": len(api_upload_providers),
        "warnings": warnings,
        "summary": {
            "platforms": len(variant_rows),
            "ready_platforms": sum(1 for row in variant_rows if row.get("ready")),
            "checklist_items": len(checklist),
            "failing_checks": len(failing_checks),
            "providers": len(providers),
            "configured_providers": len(ready_providers),
            "quick_uploads": len(quick_upload_rows),
            "ready_quick_uploads": sum(1 for row in quick_upload_rows if row.get("ready")),
            "quick_upload_package_ready": any(bool(row.get("ready")) for row in quick_upload_rows),
            "api_upload_providers": len(api_upload_providers),
            "api_upload_configured": sum(1 for row in api_upload_providers if row.get("configured")),
            "copy_ready": bool(cards[0]["ready"]),
            "thumbnail_ms": int(thumbnail.get("ms", 0) or 0),
        },
        "clipboard_payloads": {
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "thumbnail_ms": int(thumbnail.get("ms", 0) or 0),
        },
    }


def capcut_publish_manifest(
    bundle_or_package: Mapping[str, Any] | None,
    *,
    export_paths: Iterable[str | Path] = (),
    configured_providers: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Return a serializable local publish handoff manifest."""
    review = capcut_publish_review_model(bundle_or_package, configured_providers=configured_providers, export_paths=export_paths)
    return {
        "kind": "capcut_publish_manifest",
        "version": 1,
        "ok": bool(review.get("ok")),
        "ready": bool(review.get("ready")),
        "export_paths": [str(Path(path)) for path in export_paths],
        "providers": review.get("providers", []),
        "clipboard_payloads": review.get("clipboard_payloads", {}),
        "summary": review.get("summary", {}),
        "quick_uploads": review.get("quick_uploads", []),
        "warnings": review.get("warnings", []),
    }


def _quick_upload_readme(review: Mapping[str, Any], manifest: Mapping[str, Any]) -> str:
    summary = _as_dict(review.get("summary"))
    return "\n".join(
        [
            "TigerCapture quick upload package",
            "",
            "This package prepares browser upload handoff for X, TikTok, and Instagram/Reels.",
            "TigerCapture did not upload anything, create posts, store tokens, or call platform APIs.",
            "",
            f"Ready quick uploads: {int(summary.get('ready_quick_uploads', 0) or 0)}",
            f"API upload providers configured: {int(summary.get('api_upload_configured', 0) or 0)}",
            f"Export files: {len(_as_list(manifest.get('export_paths')))}",
            "",
            "Use",
            "1. Open the platform upload URL from upload_links.json or the platform text file.",
            "2. Select the exported MP4 from the export path.",
            "3. Paste the prepared title/caption/hashtags.",
            "4. Confirm privacy, thumbnail, safe-zone, and platform policy manually before posting.",
            "",
            "Direct API upload remains disabled until OAuth/app-review providers are explicitly configured.",
        ]
    )


def capcut_write_quick_upload_package(
    bundle_or_package: Mapping[str, Any] | None,
    output_dir: str | Path,
    *,
    export_paths: Iterable[str | Path] = (),
    configured_providers: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Write local files that make X/TikTok/Instagram browser upload fast."""
    review = capcut_publish_review_model(
        bundle_or_package,
        configured_providers=configured_providers,
        export_paths=export_paths,
    )
    manifest = capcut_publish_manifest(
        bundle_or_package,
        export_paths=export_paths,
        configured_providers=configured_providers,
    )
    quick_uploads = [_as_dict(row) for row in _as_list(review.get("quick_uploads"))]
    ready_uploads = [row for row in quick_uploads if row.get("ready")]
    first_title = _safe_slug((_as_dict(review.get("clipboard_payloads"))).get("title"), fallback="quick-upload-package")
    package_dir = Path(output_dir) / first_title if Path(output_dir).suffix else Path(output_dir)
    if not ready_uploads:
        return {
            "kind": "capcut_quick_upload_package",
            "ok": False,
            "ready": False,
            "path": str(package_dir),
            "upload_attempted": False,
            "blocked_reason": "No quick upload rows are ready.",
            "files": [],
            "review": review,
        }

    clipboard = _as_dict(review.get("clipboard_payloads"))
    upload_links = {
        str(row.get("platform")): {
            "label": row.get("label"),
            "url": row.get("upload_url"),
            "export_path": row.get("export_path"),
            "manual_confirm": bool(row.get("requires_manual_confirm")),
        }
        for row in ready_uploads
    }
    payloads: dict[str, str] = {
        "publish_manifest.json": _json_text(manifest),
        "quick_uploads.json": _json_text({"quick_uploads": quick_uploads}),
        "upload_links.json": _json_text(upload_links),
        "provider_contracts.json": _json_text({"providers": _as_list(review.get("providers"))}),
        "title.txt": str(clipboard.get("title") or ""),
        "description.txt": str(clipboard.get("description") or ""),
        "hashtags.txt": str(clipboard.get("hashtags") or ""),
        "README.txt": _quick_upload_readme(review, manifest),
    }
    for row in ready_uploads:
        platform = _safe_slug(row.get("platform"), fallback="platform")
        payloads[f"{platform}_post.txt"] = "\n".join(
            [
                f"Platform: {row.get('label')}",
                f"Upload URL: {row.get('upload_url')}",
                f"Export path: {row.get('export_path')}",
                "",
                str(row.get("post_text") or ""),
            ]
        )

    package_index = {
        "kind": "capcut_quick_upload_package_index",
        "upload_attempted": False,
        "api_upload_enabled": False,
        "ready_quick_uploads": len(ready_uploads),
        "platforms": [row.get("platform") for row in ready_uploads],
        "files": [{"path": name, "size_bytes": len(text.encode("utf-8"))} for name, text in payloads.items()],
    }
    payloads["package_index.json"] = _json_text(package_index)

    package_dir.mkdir(parents=True, exist_ok=True)
    written: list[dict[str, Any]] = []
    for name, text in payloads.items():
        path = package_dir / name
        path.write_text(text, encoding="utf-8")
        written.append({"path": str(path), "name": name, "size_bytes": len(text.encode("utf-8"))})

    return {
        "kind": "capcut_quick_upload_package",
        "ok": True,
        "ready": True,
        "path": str(package_dir),
        "upload_attempted": False,
        "api_upload_enabled": False,
        "quick_upload_count": len(quick_uploads),
        "ready_quick_upload_count": len(ready_uploads),
        "file_count": len(written),
        "size_bytes": sum(int(row["size_bytes"]) for row in written),
        "files": written,
        "upload_links": upload_links,
        "warnings": list(_as_list(review.get("warnings"))),
    }
