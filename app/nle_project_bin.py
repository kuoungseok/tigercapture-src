"""Project bin / conform / relink workbench contracts for NLE workflows."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


PROJECT_BIN_SCHEMA = "tigerstudio.nle.project_bin_workbench.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _media_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(list(snapshot.get("media_pool") or [])):
        if not isinstance(item, Mapping):
            continue
        path = _text(item.get("path"))
        row = dict(item)
        row.setdefault("id", f"media_{index + 1}")
        row.setdefault("name", Path(path).name if path else _text(item.get("name"), f"Media {index + 1}"))
        row.setdefault("kind", "unknown")
        row.setdefault("bin", "All Media")
        if "offline" in item:
            row["offline"] = bool(item.get("offline"))
        else:
            row["offline"] = bool(path and not Path(path).exists())
        row["proxy_state"] = _text(item.get("proxy_state"), "unknown")
        row["relink_candidate_count"] = _int(item.get("relink_candidate_count"), 0)
        rows.append(row)
    return rows


def _path_key(value: Any) -> str:
    text = _text(value).replace("\\", "/").lower()
    return text.rstrip("/")


def _name_key(value: Any) -> str:
    return Path(_text(value)).name.lower()


def _clip_source_path(track: Mapping[str, Any], clip: Mapping[str, Any]) -> str:
    for key in ("source_path", "path", "media_path", "file", "audio_path"):
        text = _text(clip.get(key))
        if text:
            return text
    return _text(track.get("source_path"))


def _timeline_clip_rows(snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, track_key in (("video", "video_tracks"), ("audio", "audio_tracks")):
        for track_index, track in enumerate(list(snapshot.get(track_key) or [])):
            if not isinstance(track, Mapping):
                continue
            track_id = _int(track.get("id", track_index + 1), track_index + 1)
            for clip_index, clip in enumerate(list(track.get("clips") or [])):
                if not isinstance(clip, Mapping):
                    continue
                source_path = _clip_source_path(track, clip)
                rows.append(
                    {
                        "kind": kind,
                        "track_id": track_id,
                        "clip_id": str(clip.get("id") or f"{kind}_{track_id}_{clip_index + 1}"),
                        "clip_name": _text(clip.get("name"), Path(source_path).name if source_path else f"Clip {clip_index + 1}"),
                        "source_path": source_path,
                        "timeline_in_ms": _int(clip.get("timeline_in_ms", clip.get("offset_ms", 0)), 0),
                        "timeline_out_ms": _int(clip.get("timeline_out_ms", clip.get("end_ms", 0)), 0),
                        "duration_ms": _int(clip.get("duration_ms"), 0),
                    }
                )
    return rows


def build_project_bin_workbench(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    rows = _media_rows(snapshot)
    bins: dict[str, dict[str, Any]] = {}
    kind_counts: dict[str, int] = {}
    proxy_counts: dict[str, int] = {}
    offline_count = 0
    relink_candidate_count = 0
    for row in rows:
        bin_name = _text(row.get("bin"), "All Media")
        kind = _text(row.get("kind"), "unknown")
        proxy_state = _text(row.get("proxy_state"), "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        proxy_counts[proxy_state] = proxy_counts.get(proxy_state, 0) + 1
        offline_count += 1 if row.get("offline") else 0
        relink_candidate_count += _int(row.get("relink_candidate_count"), 0)
        bucket = bins.setdefault(
            bin_name,
            {
                "name": bin_name,
                "count": 0,
                "kind_counts": {},
                "offline_count": 0,
                "proxy_counts": {},
            },
        )
        bucket["count"] = _int(bucket.get("count"), 0) + 1
        bucket["kind_counts"][kind] = _int(bucket["kind_counts"].get(kind), 0) + 1
        bucket["proxy_counts"][proxy_state] = _int(bucket["proxy_counts"].get(proxy_state), 0) + 1
        if row.get("offline"):
            bucket["offline_count"] = _int(bucket.get("offline_count"), 0) + 1
    visible_rows = [
        {
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "path": str(row.get("path") or ""),
            "kind": str(row.get("kind") or "unknown"),
            "bin": str(row.get("bin") or "All Media"),
            "offline": bool(row.get("offline")),
            "proxy_state": str(row.get("proxy_state") or "unknown"),
            "relink_candidate_count": _int(row.get("relink_candidate_count"), 0),
        }
        for row in rows[:500]
    ]
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "summary": {
            "media_count": len(rows),
            "bin_count": len(bins),
            "kind_counts": kind_counts,
            "proxy_counts": proxy_counts,
            "offline_count": offline_count,
            "relink_candidate_count": relink_candidate_count,
        },
        "bins": sorted(bins.values(), key=lambda row: str(row.get("name") or "")),
        "rows": visible_rows,
        "metadata_columns": [
            "name",
            "kind",
            "bin",
            "path",
            "proxy_state",
            "offline",
            "relink_candidate_count",
        ],
        "commands": {
            "relink_enabled": offline_count > 0 or relink_candidate_count > 0,
            "proxy_refresh_enabled": bool(rows),
            "metadata_search_enabled": True,
            "conform_report_enabled": bool(rows),
        },
        "readiness": {
            "bin_workflow_ready": len(rows) >= 1,
            "long_project_ready": len(rows) >= 12,
            "needs_offline_browser": offline_count > 0,
            "needs_proxy_refresh": bool(proxy_counts.get("stale") or proxy_counts.get("missing")),
        },
    }


def build_project_bin_conform_report(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return timeline-to-media-pool conform diagnostics.

    The report is deliberately read-only.  It gives UI, QA, and AI automation a
    shared view of which timeline clips are resolved by path, only by filename,
    or not found in the current Media Pool.
    """

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    media = _media_rows(snapshot)
    clips = _timeline_clip_rows(snapshot)
    by_path: dict[str, dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in media:
        path_key = _path_key(row.get("path"))
        if path_key:
            by_path[path_key] = row
        by_name.setdefault(_name_key(row.get("name") or row.get("path")), []).append(row)
    matched = 0
    name_only = 0
    unmatched = 0
    offline = 0
    duplicate_name = 0
    rows: list[dict[str, Any]] = []
    for clip in clips:
        source = str(clip.get("source_path") or "")
        media_row = by_path.get(_path_key(source))
        match_method = "path" if media_row else ""
        candidates = by_name.get(_name_key(source or clip.get("clip_name")), [])
        if not media_row and len(candidates) == 1:
            media_row = candidates[0]
            match_method = "name"
            name_only += 1
        elif not media_row and len(candidates) > 1:
            duplicate_name += 1
            match_method = "ambiguous_name"
        if media_row:
            matched += 1
            offline += 1 if media_row.get("offline") else 0
        else:
            unmatched += 1
        rows.append(
            {
                "clip_id": str(clip.get("clip_id") or ""),
                "track_id": _int(clip.get("track_id"), 0),
                "kind": str(clip.get("kind") or ""),
                "clip_name": str(clip.get("clip_name") or ""),
                "source_path": source,
                "media_id": str((media_row or {}).get("id") or ""),
                "media_name": str((media_row or {}).get("name") or ""),
                "match_method": match_method or "missing",
                "candidate_count": len(candidates),
                "candidates": [
                    {
                        "media_id": str(candidate.get("id") or ""),
                        "name": str(candidate.get("name") or ""),
                        "path": str(candidate.get("path") or ""),
                        "offline": bool(candidate.get("offline")),
                        "proxy_state": str(candidate.get("proxy_state") or "unknown"),
                    }
                    for candidate in candidates[:12]
                ],
                "offline": bool((media_row or {}).get("offline")),
                "needs_review": bool(not media_row or match_method in {"name", "ambiguous_name"} or (media_row or {}).get("offline")),
            }
        )
    total = len(clips)
    matched_ratio = round(matched / total, 4) if total else 0.0
    checks = {
        "has_media_pool": bool(media),
        "has_timeline_clips": bool(clips),
        "all_clips_resolved": total > 0 and unmatched == 0,
        "no_offline_matches": offline == 0,
        "no_ambiguous_names": duplicate_name == 0,
    }
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_conform_report",
        "ready": bool(media and clips),
        "conform_ready": bool(media and clips and unmatched == 0),
        "summary": {
            "media_count": len(media),
            "timeline_clip_count": total,
            "matched_count": matched,
            "matched_ratio": matched_ratio,
            "name_only_match_count": name_only,
            "unmatched_count": unmatched,
            "offline_match_count": offline,
            "ambiguous_name_count": duplicate_name,
        },
        "checks": checks,
        "rows": rows[:1000],
        "commands": {
            "open_offline_browser_enabled": offline > 0 or unmatched > 0,
            "review_name_matches_enabled": name_only > 0 or duplicate_name > 0,
            "generate_relink_plan_enabled": unmatched > 0 or offline > 0,
        },
        "readiness": {
            "timeline_media_conform_ready": bool(media and clips and unmatched == 0),
            "needs_relink_review": unmatched > 0 or offline > 0,
            "needs_name_match_review": name_only > 0 or duplicate_name > 0,
        },
    }


def build_project_bin_batch_plan(
    snapshot: Mapping[str, Any] | None = None,
    *,
    operation: str = "all",
) -> dict[str, Any]:
    """Return read-only batch relink/proxy/conform operations for UI review."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    rows = _media_rows(snapshot)
    normalized_operation = _text(operation, "all").lower()
    operations: list[dict[str, Any]] = []
    seen_names: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        seen_names.setdefault(str(row.get("name") or "").lower(), []).append(row)
    for row in rows:
        media_id = str(row.get("id") or "")
        name = str(row.get("name") or "")
        path = str(row.get("path") or "")
        proxy_state = str(row.get("proxy_state") or "unknown").lower()
        duplicates = [item for item in seen_names.get(name.lower(), []) if str(item.get("id") or "") != media_id]
        if row.get("offline") and normalized_operation in {"all", "relink", "offline"}:
            operations.append(
                {
                    "id": f"relink_{media_id}",
                    "media_id": media_id,
                    "operation": "relink",
                    "name": name,
                    "path": path,
                    "reason": "offline_media",
                    "candidate_count": _int(row.get("relink_candidate_count"), 0),
                    "safe_to_auto_apply": _int(row.get("relink_candidate_count"), 0) == 1,
                }
            )
        if proxy_state in {"missing", "stale", "unknown"} and normalized_operation in {"all", "proxy", "proxy_refresh"}:
            operations.append(
                {
                    "id": f"proxy_{media_id}",
                    "media_id": media_id,
                    "operation": "proxy_refresh",
                    "name": name,
                    "path": path,
                    "reason": f"proxy_{proxy_state}",
                    "candidate_count": 0,
                    "safe_to_auto_apply": True,
                }
            )
        if duplicates and normalized_operation in {"all", "conform", "duplicates"}:
            operations.append(
                {
                    "id": f"conform_{media_id}",
                    "media_id": media_id,
                    "operation": "conform_check",
                    "name": name,
                    "path": path,
                    "reason": "duplicate_name",
                    "candidate_count": len(duplicates),
                    "safe_to_auto_apply": False,
                }
            )
    operation_counts: dict[str, int] = {}
    for op in operations:
        key = str(op.get("operation") or "unknown")
        operation_counts[key] = operation_counts.get(key, 0) + 1
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_batch_plan",
        "operation": normalized_operation,
        "ready": bool(rows),
        "operation_count": len(operations),
        "operation_counts": operation_counts,
        "operations": operations[:1000],
        "review_required": any(not bool(row.get("safe_to_auto_apply")) for row in operations),
        "commands": {
            "relink_all_enabled": any(row.get("operation") == "relink" for row in operations),
            "proxy_refresh_enabled": any(row.get("operation") == "proxy_refresh" for row in operations),
            "conform_check_enabled": any(row.get("operation") == "conform_check" for row in operations),
        },
    }


def build_project_bin_proxy_plan(
    snapshot: Mapping[str, Any] | None = None,
    *,
    target: str = "timeline",
) -> dict[str, Any]:
    """Return UI-ready proxy state and regeneration queue.

    This is read-only.  It tells the editor which media should use existing
    proxies, which proxies are stale/missing, and which batch operations need
    review before background workers regenerate files.
    """

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    rows = _media_rows(snapshot)
    normalized_target = _text(target, "timeline").lower()
    proxy_counts: dict[str, int] = {}
    kind_counts: dict[str, int] = {}
    queue: list[dict[str, Any]] = []
    usable: list[dict[str, Any]] = []
    for row in rows:
        kind = str(row.get("kind") or "unknown").lower()
        state = str(row.get("proxy_state") or "unknown").lower()
        proxy_counts[state] = proxy_counts.get(state, 0) + 1
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        media_id = str(row.get("id") or "")
        if state in {"ready", "active", "fresh"}:
            usable.append(
                {
                    "media_id": media_id,
                    "name": str(row.get("name") or ""),
                    "path": str(row.get("path") or ""),
                    "kind": kind,
                    "proxy_state": state,
                    "use_proxy": kind in {"video", "image", "actor", "3d"},
                }
            )
        elif kind in {"video", "image", "actor", "3d", "unknown"}:
            queue.append(
                {
                    "id": f"proxy_refresh_{media_id}",
                    "media_id": media_id,
                    "name": str(row.get("name") or ""),
                    "path": str(row.get("path") or ""),
                    "kind": kind,
                    "proxy_state": state,
                    "reason": f"proxy_{state}",
                    "priority": "high" if state in {"missing", "unknown"} else "normal",
                    "safe_to_background": not bool(row.get("offline")),
                }
            )
    media_count = len(rows)
    ready_count = len(usable)
    queue_count = len(queue)
    ready_ratio = round(ready_count / media_count, 4) if media_count else 0.0
    preview_policy = {
        "prefer_proxy_for_preview": ready_count > 0,
        "prefer_original_for_export": True,
        "auto_switch_when_proxy_fresh": True,
        "target": normalized_target,
    }
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_proxy_plan",
        "ready": bool(rows),
        "proxy_ready": media_count > 0 and (ready_count >= 1 or queue_count >= 1),
        "summary": {
            "media_count": media_count,
            "ready_count": ready_count,
            "queue_count": queue_count,
            "ready_ratio": ready_ratio,
            "proxy_counts": proxy_counts,
            "kind_counts": kind_counts,
        },
        "preview_policy": preview_policy,
        "usable_proxies": usable[:500],
        "regeneration_queue": queue[:500],
        "commands": {
            "use_available_proxies_enabled": ready_count > 0,
            "regenerate_stale_enabled": any(row.get("proxy_state") == "stale" for row in queue),
            "regenerate_missing_enabled": any(row.get("proxy_state") in {"missing", "unknown"} for row in queue),
            "batch_proxy_refresh_enabled": queue_count > 0,
        },
        "readiness": {
            "long_project_proxy_ready": media_count >= 12 and ready_count >= 6,
            "needs_regeneration": queue_count > 0,
            "all_media_have_proxy": media_count > 0 and queue_count == 0,
        },
    }


def build_project_bin_proxy_health_board(
    snapshot: Mapping[str, Any] | None = None,
    *,
    target: str = "timeline",
) -> dict[str, Any]:
    """Return product-facing proxy health cards and reviewed queue state."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    rows = _media_rows(snapshot)
    plan = build_project_bin_proxy_plan(snapshot, target=target)
    state_buckets: dict[str, list[dict[str, Any]]] = {}
    offline_count = 0
    for row in rows:
        state = str(row.get("proxy_state") or "unknown").lower()
        kind = str(row.get("kind") or "unknown").lower()
        offline = bool(row.get("offline"))
        offline_count += 1 if offline else 0
        state_buckets.setdefault(state, []).append(
            {
                "media_id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "path": str(row.get("path") or ""),
                "kind": kind,
                "offline": offline,
                "proxy_state": state,
                "needs_attention": offline or state in {"missing", "stale", "unknown"},
            }
        )

    summary = plan.get("summary") if isinstance(plan.get("summary"), Mapping) else {}
    media_count = _int(summary.get("media_count"), len(rows))
    ready_count = _int(summary.get("ready_count"), 0)
    queue_count = _int(summary.get("queue_count"), 0)
    state_cards: list[dict[str, Any]] = []
    for state in ("ready", "active", "fresh", "stale", "missing", "unknown"):
        items = state_buckets.get(state, [])
        if not items and state not in {"ready", "stale", "missing", "unknown"}:
            continue
        severity = "ok" if state in {"ready", "active", "fresh"} else ("warning" if state == "stale" else "blocking")
        state_cards.append(
            {
                "state": state,
                "label": state.replace("_", " ").title(),
                "count": len(items),
                "severity": severity,
                "sample": items[:8],
            }
        )

    queue = [dict(row) for row in list(plan.get("regeneration_queue") or []) if isinstance(row, Mapping)]
    safe_queue_count = sum(1 for row in queue if bool(row.get("safe_to_background")))
    ready_ratio = round(ready_count / media_count, 4) if media_count else 0.0
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_proxy_health_board",
        "ready": bool(media_count),
        "target": str((plan.get("preview_policy") or {}).get("target") or _text(target, "timeline").lower()),
        "summary": {
            "media_count": media_count,
            "ready_count": ready_count,
            "queue_count": queue_count,
            "safe_queue_count": safe_queue_count,
            "offline_count": offline_count,
            "ready_ratio": ready_ratio,
        },
        "state_cards": state_cards,
        "priority_queue": queue[:200],
        "preview_policy": dict(plan.get("preview_policy") or {}),
        "commands": {
            "use_available_proxies_enabled": ready_count > 0,
            "open_regeneration_review_enabled": queue_count > 0,
            "background_regenerate_safe_enabled": safe_queue_count > 0,
            "show_offline_media_enabled": offline_count > 0,
        },
        "readiness": {
            "proxy_health_board_ready": media_count >= 1,
            "long_project_proxy_ready": media_count >= 12 and ready_count >= 6,
            "needs_user_review": offline_count > 0 or queue_count > safe_queue_count,
            "all_media_ready": media_count > 0 and queue_count == 0 and offline_count == 0,
        },
    }


def build_project_bin_offline_browser(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return a product-facing offline/missing media browser contract."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    workbench = build_project_bin_workbench(snapshot)
    conform = build_project_bin_conform_report(snapshot)
    media_rows = [dict(row) for row in list(workbench.get("rows") or []) if isinstance(row, Mapping)]
    conform_rows = [dict(row) for row in list(conform.get("rows") or []) if isinstance(row, Mapping)]
    offline_media = [row for row in media_rows if bool(row.get("offline"))]
    missing_clips = [row for row in conform_rows if str(row.get("match_method") or "") == "missing"]
    ambiguous = [row for row in conform_rows if str(row.get("match_method") or "") == "ambiguous_name"]
    name_only = [row for row in conform_rows if str(row.get("match_method") or "") == "name"]
    relink_queue: list[dict[str, Any]] = []
    for row in offline_media:
        relink_queue.append(
            {
                "id": f"media_{row.get('id')}",
                "kind": "offline_media",
                "media_id": str(row.get("id") or ""),
                "name": str(row.get("name") or ""),
                "path": str(row.get("path") or ""),
                "candidate_count": _int(row.get("relink_candidate_count"), 0),
                "safe_to_auto_apply": _int(row.get("relink_candidate_count"), 0) == 1,
            }
        )
    for row in missing_clips:
        relink_queue.append(
            {
                "id": f"clip_{row.get('track_id')}_{row.get('clip_id')}",
                "kind": "missing_clip_source",
                "clip_id": str(row.get("clip_id") or ""),
                "track_id": _int(row.get("track_id"), 0),
                "name": str(row.get("clip_name") or ""),
                "path": str(row.get("source_path") or ""),
                "candidate_count": _int(row.get("candidate_count"), 0),
                "safe_to_auto_apply": False,
            }
        )
    warnings: list[str] = []
    if ambiguous:
        warnings.append("ambiguous_name_matches")
    if name_only:
        warnings.append("name_only_matches_need_review")
    if offline_media or missing_clips:
        warnings.append("offline_or_missing_media_present")
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_offline_browser",
        "ready": bool(media_rows or conform_rows),
        "summary": {
            "offline_media_count": len(offline_media),
            "missing_clip_count": len(missing_clips),
            "ambiguous_name_count": len(ambiguous),
            "name_only_match_count": len(name_only),
            "relink_queue_count": len(relink_queue),
            "safe_auto_relink_count": sum(1 for row in relink_queue if bool(row.get("safe_to_auto_apply"))),
        },
        "sections": [
            {"id": "offline_media", "title": "Offline Media", "rows": offline_media[:100]},
            {"id": "missing_clips", "title": "Missing Timeline Sources", "rows": missing_clips[:100]},
            {"id": "ambiguous", "title": "Ambiguous Name Matches", "rows": ambiguous[:100]},
            {"id": "name_only", "title": "Name-Only Matches", "rows": name_only[:100]},
        ],
        "relink_queue": relink_queue[:200],
        "warnings": warnings,
        "commands": {
            "browse_search_roots_enabled": True,
            "register_search_root_enabled": True,
            "apply_single_candidate_enabled": any(bool(row.get("safe_to_auto_apply")) for row in relink_queue),
            "manual_relink_enabled": bool(relink_queue),
            "accept_name_only_matches_enabled": bool(name_only),
        },
        "readiness": {
            "offline_browser_ready": True,
            "has_relink_work": bool(relink_queue),
            "requires_manual_review": bool(ambiguous or name_only or any(not bool(row.get("safe_to_auto_apply")) for row in relink_queue)),
        },
    }


def build_project_bin_relink_candidate_board(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return file-by-file relink candidate choices for conform review."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    conform = build_project_bin_conform_report(snapshot)
    rows = [dict(row) for row in list(conform.get("rows") or []) if isinstance(row, Mapping)]
    exact = [row for row in rows if str(row.get("match_method") or "") == "path"]
    name_only = [row for row in rows if str(row.get("match_method") or "") == "name"]
    ambiguous = [row for row in rows if str(row.get("match_method") or "") == "ambiguous_name"]
    missing = [row for row in rows if str(row.get("match_method") or "") == "missing"]
    offline = [row for row in rows if bool(row.get("offline"))]
    choices: list[dict[str, Any]] = []
    for row in rows:
        candidates = [dict(candidate) for candidate in list(row.get("candidates") or []) if isinstance(candidate, Mapping)]
        match_method = str(row.get("match_method") or "missing")
        choices.append(
            {
                "id": f"clip_{row.get('track_id')}_{row.get('clip_id')}",
                "clip_id": str(row.get("clip_id") or ""),
                "track_id": _int(row.get("track_id"), 0),
                "clip_name": str(row.get("clip_name") or ""),
                "source_path": str(row.get("source_path") or ""),
                "match_method": match_method,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "recommended_media_id": str(row.get("media_id") or (candidates[0].get("media_id") if len(candidates) == 1 else "")),
                "safe_to_auto_apply": match_method == "path" and not bool(row.get("offline")),
                "requires_user_choice": match_method in {"name", "ambiguous_name", "missing"} or bool(row.get("offline")),
            }
        )
    review_choices = [row for row in choices if bool(row.get("requires_user_choice"))]
    safe_choices = [row for row in choices if bool(row.get("safe_to_auto_apply"))]
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_relink_candidate_board",
        "ready": bool(rows),
        "summary": {
            "clip_count": len(rows),
            "safe_choice_count": len(safe_choices),
            "review_choice_count": len(review_choices),
            "name_only_count": len(name_only),
            "ambiguous_count": len(ambiguous),
            "missing_count": len(missing),
            "offline_count": len(offline),
        },
        "sections": [
            {"id": "safe", "title": "Safe Path Matches", "rows": safe_choices[:120]},
            {"id": "name_only", "title": "Name Matches", "rows": name_only[:120]},
            {"id": "ambiguous", "title": "Ambiguous Candidates", "rows": ambiguous[:120]},
            {"id": "missing", "title": "Missing Sources", "rows": missing[:120]},
            {"id": "offline", "title": "Offline Matches", "rows": offline[:120]},
        ],
        "choices": choices[:500],
        "commands": {
            "apply_safe_matches_enabled": bool(safe_choices),
            "apply_selected_candidates_enabled": bool(review_choices),
            "open_offline_browser_enabled": bool(offline or missing),
            "register_search_root_enabled": bool(review_choices),
        },
        "readiness": {
            "relink_candidate_board_ready": True,
            "file_by_file_choice_ready": bool(choices),
            "ambiguous_candidate_review_ready": True,
            "safe_auto_apply_ready": bool(safe_choices),
        },
    }


def build_project_bin_proxy_regeneration_board(
    snapshot: Mapping[str, Any] | None = None,
    *,
    target: str = "timeline",
) -> dict[str, Any]:
    """Return a reviewed proxy regeneration queue for long-project workflows."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    proxy = build_project_bin_proxy_plan(snapshot, target=target)
    health = build_project_bin_proxy_health_board(snapshot, target=target)
    queue = [dict(row) for row in list(proxy.get("regeneration_queue") or []) if isinstance(row, Mapping)]
    high_priority = [row for row in queue if str(row.get("priority") or "") == "high"]
    normal_priority = [row for row in queue if str(row.get("priority") or "") != "high"]
    blocked = [row for row in queue if not bool(row.get("safe_to_background"))]
    safe = [row for row in queue if bool(row.get("safe_to_background"))]
    operations = [
        {
            "id": str(row.get("id") or f"proxy_{index + 1}"),
            "media_id": str(row.get("media_id") or ""),
            "name": str(row.get("name") or ""),
            "path": str(row.get("path") or ""),
            "priority": str(row.get("priority") or "normal"),
            "reason": str(row.get("reason") or ""),
            "safe_to_background": bool(row.get("safe_to_background")),
            "estimated_cost": "background" if bool(row.get("safe_to_background")) else "blocked_until_relink",
        }
        for index, row in enumerate(queue)
    ]
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_proxy_regeneration_board",
        "ready": bool((health.get("readiness") or {}).get("proxy_health_board_ready")),
        "target": str((proxy.get("preview_policy") or {}).get("target") or _text(target, "timeline").lower()),
        "summary": {
            "queue_count": len(queue),
            "safe_queue_count": len(safe),
            "blocked_queue_count": len(blocked),
            "high_priority_count": len(high_priority),
            "normal_priority_count": len(normal_priority),
            "ready_count": _int((proxy.get("summary") or {}).get("ready_count"), 0),
            "media_count": _int((proxy.get("summary") or {}).get("media_count"), 0),
        },
        "sections": [
            {"id": "high_priority", "title": "High Priority", "rows": high_priority[:100]},
            {"id": "normal_priority", "title": "Normal Priority", "rows": normal_priority[:100]},
            {"id": "blocked", "title": "Blocked Until Relink", "rows": blocked[:100]},
            {"id": "ready", "title": "Ready Proxies", "rows": list(proxy.get("usable_proxies") or [])[:100]},
        ],
        "operations": operations[:250],
        "commands": {
            "start_safe_background_jobs_enabled": bool(safe),
            "open_proxy_settings_enabled": True,
            "show_blocked_offline_enabled": bool(blocked),
            "prefer_proxy_for_preview_enabled": bool((proxy.get("preview_policy") or {}).get("prefer_proxy_for_preview")),
        },
        "readiness": {
            "proxy_regeneration_board_ready": True,
            "safe_background_regeneration_ready": bool(safe),
            "requires_relink_first": bool(blocked),
            "all_proxy_work_complete": bool((health.get("readiness") or {}).get("all_media_ready")),
        },
    }


def build_project_bin_proxy_conflict_board(
    snapshot: Mapping[str, Any] | None = None,
    *,
    target: str = "timeline",
) -> dict[str, Any]:
    """Return proxy regeneration conflicts separated from safe background jobs."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    proxy = build_project_bin_proxy_plan(snapshot, target=target)
    health = build_project_bin_proxy_health_board(snapshot, target=target)
    rows = _media_rows(snapshot)
    queue = [dict(row) for row in list(proxy.get("regeneration_queue") or []) if isinstance(row, Mapping)]
    safe_jobs = [row for row in queue if bool(row.get("safe_to_background"))]
    blocked_jobs = [row for row in queue if not bool(row.get("safe_to_background"))]
    duplicate_paths: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        path_key = _path_key(row.get("path"))
        if path_key:
            duplicate_paths.setdefault(path_key, []).append(row)
    duplicate_media = [
        {
            "path": str(group[0].get("path") or ""),
            "count": len(group),
            "media_ids": [str(item.get("id") or "") for item in group[:12]],
            "names": [str(item.get("name") or "") for item in group[:12]],
        }
        for group in duplicate_paths.values()
        if len(group) > 1
    ]
    offline_media = [
        {
            "media_id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "path": str(row.get("path") or ""),
            "kind": str(row.get("kind") or "unknown"),
            "proxy_state": str(row.get("proxy_state") or "unknown"),
        }
        for row in rows
        if bool(row.get("offline"))
    ]
    conflicts = []
    if blocked_jobs:
        conflicts.append("blocked_offline_proxy_jobs")
    if duplicate_media:
        conflicts.append("duplicate_media_paths")
    if offline_media:
        conflicts.append("offline_media_before_proxy")
    safe_background_ready = bool(safe_jobs)
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_proxy_conflict_board",
        "ready": bool((health.get("readiness") or {}).get("proxy_health_board_ready")),
        "target": str((proxy.get("preview_policy") or {}).get("target") or _text(target, "timeline").lower()),
        "summary": {
            "safe_job_count": len(safe_jobs),
            "blocked_job_count": len(blocked_jobs),
            "duplicate_path_count": len(duplicate_media),
            "offline_media_count": len(offline_media),
            "conflict_count": len(conflicts),
        },
        "sections": [
            {"id": "safe_background_jobs", "title": "Safe Background Jobs", "rows": safe_jobs[:120]},
            {"id": "blocked_jobs", "title": "Blocked Proxy Jobs", "rows": blocked_jobs[:120]},
            {"id": "duplicate_paths", "title": "Duplicate Media Paths", "rows": duplicate_media[:120]},
            {"id": "offline_media", "title": "Offline Media", "rows": offline_media[:120]},
        ],
        "conflicts": conflicts,
        "commands": {
            "start_safe_background_jobs_enabled": safe_background_ready,
            "review_blocked_jobs_enabled": bool(blocked_jobs),
            "open_offline_browser_enabled": bool(offline_media),
            "open_duplicate_path_review_enabled": bool(duplicate_media),
            "prefer_proxy_for_preview_enabled": bool((proxy.get("preview_policy") or {}).get("prefer_proxy_for_preview")),
        },
        "readiness": {
            "proxy_conflict_board_ready": True,
            "safe_background_regeneration_ready": safe_background_ready,
            "blocked_proxy_review_ready": True,
            "duplicate_path_review_ready": True,
            "all_proxy_conflicts_clear": not bool(conflicts),
        },
    }


def build_project_bin_search_filter_model(
    snapshot: Mapping[str, Any] | None = None,
    *,
    query: str = "",
    kind: str = "all",
    bin_name: str = "",
    proxy_state: str = "all",
    offline: str = "all",
) -> dict[str, Any]:
    """Return a UI-ready media-bin search/filter/column model."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    workbench = build_project_bin_workbench(snapshot)
    rows = [dict(row) for row in list(workbench.get("rows") or []) if isinstance(row, Mapping)]
    q = _text(query).lower()
    wanted_kind = _text(kind, "all").lower()
    wanted_bin = _text(bin_name)
    wanted_proxy = _text(proxy_state, "all").lower()
    wanted_offline = _text(offline, "all").lower()

    def keep(row: Mapping[str, Any]) -> bool:
        if q and q not in " ".join(str(row.get(key) or "").lower() for key in ("name", "path", "kind", "bin")):
            return False
        if wanted_kind not in {"", "all"} and str(row.get("kind") or "").lower() != wanted_kind:
            return False
        if wanted_bin and str(row.get("bin") or "") != wanted_bin:
            return False
        if wanted_proxy not in {"", "all"} and str(row.get("proxy_state") or "").lower() != wanted_proxy:
            return False
        if wanted_offline == "offline" and not bool(row.get("offline")):
            return False
        if wanted_offline == "online" and bool(row.get("offline")):
            return False
        return True

    filtered = [row for row in rows if keep(row)]
    kind_counts: dict[str, int] = {}
    bin_counts: dict[str, int] = {}
    proxy_counts: dict[str, int] = {}
    for row in rows:
        kind_key = str(row.get("kind") or "unknown")
        bin_key = str(row.get("bin") or "All Media")
        proxy_key = str(row.get("proxy_state") or "unknown")
        kind_counts[kind_key] = kind_counts.get(kind_key, 0) + 1
        bin_counts[bin_key] = bin_counts.get(bin_key, 0) + 1
        proxy_counts[proxy_key] = proxy_counts.get(proxy_key, 0) + 1
    columns = [
        {"id": "name", "label": "Name", "visible": True, "width": 220, "sortable": True},
        {"id": "kind", "label": "Kind", "visible": True, "width": 80, "sortable": True},
        {"id": "bin", "label": "Bin", "visible": True, "width": 120, "sortable": True},
        {"id": "proxy_state", "label": "Proxy", "visible": True, "width": 90, "sortable": True},
        {"id": "offline", "label": "Offline", "visible": True, "width": 80, "sortable": True},
        {"id": "relink_candidate_count", "label": "Relink", "visible": True, "width": 80, "sortable": True},
        {"id": "path", "label": "Path", "visible": False, "width": 360, "sortable": True},
    ]
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_search_filter_model",
        "ready": True,
        "query": query,
        "filters": {
            "kind": wanted_kind,
            "bin": wanted_bin,
            "proxy_state": wanted_proxy,
            "offline": wanted_offline,
        },
        "summary": {
            "media_count": len(rows),
            "filtered_count": len(filtered),
            "matched_count": len(filtered),
            "kind_counts": kind_counts,
            "bin_counts": bin_counts,
            "proxy_counts": proxy_counts,
            "offline_count": sum(1 for row in rows if bool(row.get("offline"))),
        },
        "filter_chips": [
            {"id": "kind", "label": "Kind", "options": ["all"] + sorted(kind_counts)},
            {"id": "bin", "label": "Bin", "options": [""] + sorted(bin_counts)},
            {"id": "proxy_state", "label": "Proxy", "options": ["all"] + sorted(proxy_counts)},
            {"id": "offline", "label": "Offline", "options": ["all", "online", "offline"]},
        ],
        "columns": columns,
        "rows": filtered[:500],
        "commands": {
            "search_enabled": True,
            "filter_enabled": True,
            "column_customize_enabled": True,
            "save_view_enabled": True,
            "show_offline_only_enabled": any(bool(row.get("offline")) for row in rows),
        },
        "readiness": {
            "search_filter_model_ready": True,
            "metadata_columns_ready": bool(columns),
            "large_bin_navigation_ready": len(rows) >= 12,
        },
    }


def build_project_bin_review_board(snapshot: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return one UI-ready board for bin, conform, proxy, and relink review."""

    snapshot = snapshot if isinstance(snapshot, Mapping) else {}
    workbench = build_project_bin_workbench(snapshot)
    batch = build_project_bin_batch_plan(snapshot)
    conform = build_project_bin_conform_report(snapshot)
    proxy = build_project_bin_proxy_plan(snapshot)
    proxy_health = build_project_bin_proxy_health_board(snapshot)
    offline_browser = build_project_bin_offline_browser(snapshot)
    relink_candidates = build_project_bin_relink_candidate_board(snapshot)
    proxy_regen = build_project_bin_proxy_regeneration_board(snapshot)
    proxy_conflicts = build_project_bin_proxy_conflict_board(snapshot)
    search_filter = build_project_bin_search_filter_model(snapshot)
    workbench_summary = workbench.get("summary") if isinstance(workbench.get("summary"), Mapping) else {}
    conform_summary = conform.get("summary") if isinstance(conform.get("summary"), Mapping) else {}
    proxy_summary = proxy_health.get("summary") if isinstance(proxy_health.get("summary"), Mapping) else {}
    operations = [dict(row) for row in list(batch.get("operations") or []) if isinstance(row, Mapping)]
    review_rows = [dict(row) for row in list(conform.get("rows") or []) if isinstance(row, Mapping) and bool(row.get("needs_review"))]
    sections = [
        {
            "id": "bins",
            "title": "Project Bins",
            "count": _int(workbench_summary.get("bin_count"), 0),
            "tone": "ok" if _int(workbench_summary.get("media_count"), 0) else "empty",
            "rows": list(workbench.get("bins") or [])[:24],
        },
        {
            "id": "proxy",
            "title": "Proxy Queue",
            "count": _int(proxy_summary.get("queue_count"), 0),
            "tone": "warning" if _int(proxy_summary.get("queue_count"), 0) else "ok",
            "rows": list(proxy_health.get("priority_queue") or [])[:48],
        },
        {
            "id": "conform",
            "title": "Conform Review",
            "count": len(review_rows),
            "tone": "warning" if review_rows else "ok",
            "rows": review_rows[:48],
        },
        {
            "id": "batch",
            "title": "Batch Operations",
            "count": len(operations),
            "tone": "warning" if bool(batch.get("review_required")) else "ok",
            "rows": operations[:48],
        },
    ]
    return {
        "schema": PROJECT_BIN_SCHEMA,
        "kind": "project_bin_review_board",
        "ready": bool((workbench.get("readiness") or {}).get("bin_workflow_ready")),
        "summary": {
            "media_count": _int(workbench_summary.get("media_count"), 0),
            "bin_count": _int(workbench_summary.get("bin_count"), 0),
            "offline_count": _int(workbench_summary.get("offline_count"), 0),
            "proxy_queue_count": _int(proxy_summary.get("queue_count"), 0),
            "safe_proxy_queue_count": _int(proxy_summary.get("safe_queue_count"), 0),
            "proxy_conflict_count": _int((proxy_conflicts.get("summary") or {}).get("conflict_count"), 0),
            "conform_review_count": len(review_rows),
            "relink_review_choice_count": _int((relink_candidates.get("summary") or {}).get("review_choice_count"), 0),
            "matched_ratio": conform_summary.get("matched_ratio", 0.0),
            "batch_operation_count": len(operations),
        },
        "sections": sections,
        "commands": {
            "open_offline_browser_enabled": bool((conform.get("commands") or {}).get("open_offline_browser_enabled")),
            "open_relink_candidate_board_enabled": True,
            "review_name_matches_enabled": bool((conform.get("commands") or {}).get("review_name_matches_enabled")),
            "background_regenerate_safe_enabled": bool((proxy_health.get("commands") or {}).get("background_regenerate_safe_enabled")),
            "batch_proxy_refresh_enabled": bool((proxy.get("commands") or {}).get("batch_proxy_refresh_enabled")),
            "metadata_search_enabled": bool((workbench.get("commands") or {}).get("metadata_search_enabled")),
            "open_proxy_regeneration_board_enabled": True,
            "open_proxy_conflict_board_enabled": True,
            "open_search_filter_enabled": True,
        },
        "readiness": {
            "review_board_ready": bool((workbench.get("readiness") or {}).get("bin_workflow_ready")),
            "proxy_review_ready": bool((proxy_health.get("readiness") or {}).get("proxy_health_board_ready")),
            "proxy_regeneration_board_ready": bool((proxy_regen.get("readiness") or {}).get("proxy_regeneration_board_ready")),
            "proxy_conflict_board_ready": bool((proxy_conflicts.get("readiness") or {}).get("proxy_conflict_board_ready")),
            "conform_review_ready": bool(conform.get("ready")),
            "offline_browser_ready": bool((offline_browser.get("readiness") or {}).get("offline_browser_ready")),
            "relink_candidate_board_ready": bool((relink_candidates.get("readiness") or {}).get("relink_candidate_board_ready")),
            "safe_background_regeneration_ready": bool(
                (proxy_conflicts.get("readiness") or {}).get("safe_background_regeneration_ready")
            ),
            "search_filter_model_ready": bool((search_filter.get("readiness") or {}).get("search_filter_model_ready")),
        },
    }


def project_bin_contract_evidence(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    actions = {str(row) for row in list(action_ids or [])}
    required = {
        "project_bin.workbench",
        "project_bin.batch_plan",
        "project_bin.conform_report",
        "project_bin.review_board",
        "project_bin.offline_browser",
        "project_bin.relink_candidate_board",
        "project_bin.proxy_regeneration_board",
        "project_bin.proxy_conflict_board",
        "project_bin.search_filter_model",
        "media.summary",
        "project.snapshot",
    }
    workbench = build_project_bin_workbench(snapshot)
    batch_plan = build_project_bin_batch_plan(snapshot)
    conform_report = build_project_bin_conform_report(snapshot)
    review_board = build_project_bin_review_board(snapshot)
    offline_browser = build_project_bin_offline_browser(snapshot)
    relink_candidates = build_project_bin_relink_candidate_board(snapshot)
    proxy_regen = build_project_bin_proxy_regeneration_board(snapshot)
    proxy_conflicts = build_project_bin_proxy_conflict_board(snapshot)
    search_filter = build_project_bin_search_filter_model(snapshot)
    summary = workbench.get("summary") if isinstance(workbench.get("summary"), Mapping) else {}
    ok = required <= actions and _int(summary.get("media_count"), 0) >= 12 and _int(summary.get("bin_count"), 0) >= 1
    return {
        "ok": ok,
        "required_actions": sorted(required),
        "available_actions": sorted(required & actions),
        "media_count": _int(summary.get("media_count"), 0),
        "bin_count": _int(summary.get("bin_count"), 0),
        "offline_count": _int(summary.get("offline_count"), 0),
        "relink_candidate_count": _int(summary.get("relink_candidate_count"), 0),
        "batch_plan_ready": bool(batch_plan.get("ready")),
        "batch_operation_count": _int(batch_plan.get("operation_count"), 0),
        "batch_operation_counts": dict(batch_plan.get("operation_counts") or {}),
        "conform_report_ready": bool(conform_report.get("conform_ready")),
        "conform_report_summary": dict(conform_report.get("summary") or {}),
        "review_board_ready": bool(review_board.get("ready")) and "project_bin.review_board" in actions,
        "proxy_review_ready": bool((review_board.get("readiness") or {}).get("proxy_review_ready")) and "project_bin.review_board" in actions,
        "offline_browser_ready": bool((offline_browser.get("readiness") or {}).get("offline_browser_ready")) and "project_bin.offline_browser" in actions,
        "relink_candidate_board_ready": bool((relink_candidates.get("readiness") or {}).get("relink_candidate_board_ready"))
        and "project_bin.relink_candidate_board" in actions,
        "proxy_regeneration_board_ready": bool((proxy_regen.get("readiness") or {}).get("proxy_regeneration_board_ready")) and "project_bin.proxy_regeneration_board" in actions,
        "proxy_conflict_board_ready": bool((proxy_conflicts.get("readiness") or {}).get("proxy_conflict_board_ready"))
        and "project_bin.proxy_conflict_board" in actions,
        "safe_background_regeneration_ready": bool((proxy_conflicts.get("readiness") or {}).get("safe_background_regeneration_ready")),
        "search_filter_model_ready": bool((search_filter.get("readiness") or {}).get("search_filter_model_ready"))
        and "project_bin.search_filter_model" in actions,
        "metadata_columns_ready": bool((search_filter.get("readiness") or {}).get("metadata_columns_ready"))
        and "project_bin.search_filter_model" in actions,
    }
