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


def project_bin_contract_evidence(
    snapshot: Mapping[str, Any] | None = None,
    *,
    action_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    actions = {str(row) for row in list(action_ids or [])}
    required = {"project_bin.workbench", "project_bin.batch_plan", "project_bin.conform_report", "media.summary", "project.snapshot"}
    workbench = build_project_bin_workbench(snapshot)
    batch_plan = build_project_bin_batch_plan(snapshot)
    conform_report = build_project_bin_conform_report(snapshot)
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
    }
