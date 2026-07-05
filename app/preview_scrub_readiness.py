"""Preview seek/scrub readiness gates.

Steady playback FPS is not enough for an editor. Users feel quality when they
drag the playhead, jump edit points, and scrub back and forth. This module
turns the existing preview performance report into product-facing scrub
readiness and release-claim blockers.
"""
from __future__ import annotations

from pathlib import Path
import json
from statistics import mean
from typing import Any, Mapping


DEFAULT_THRESHOLDS = {
    "playback_avg_ms": 16.7,
    "playback_p95_ms": 33.4,
    "scrub_avg_ms": 45.0,
    "scrub_p95_ms": 66.0,
    "scrub_max_ms": 120.0,
    "excellent_scrub_avg_ms": 16.7,
    "excellent_scrub_p95_ms": 33.4,
    "decode_seek_avg_ms": 20.0,
    "decode_seek_p95_ms": 40.0,
    "measurement_tolerance_ms": 1.0,
}


def _load_report(report: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(report, Mapping):
        return dict(report)
    path = Path(report)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return data if isinstance(data, dict) else {}


def _project_name(row: Mapping[str, Any]) -> str:
    raw = str(row.get("project") or row.get("path") or "")
    if not raw:
        return ""
    try:
        return Path(raw).name
    except Exception:
        return raw


def _context_stages(row: Mapping[str, Any], context: str) -> list[dict[str, Any]]:
    by_context = row.get("stage_summary_by_context")
    if isinstance(by_context, Mapping):
        stages = by_context.get(context)
        if isinstance(stages, list):
            return [dict(stage) for stage in stages if isinstance(stage, Mapping)]
    return []


def _stage_by_label(row: Mapping[str, Any], context: str, label: str) -> dict[str, Any]:
    for stage in _context_stages(row, context):
        if str(stage.get("label") or "") == label:
            return stage
    return {}


def _summary_value(summary: Mapping[str, Any], key: str) -> float:
    try:
        return float(summary.get(key, 0.0) or 0.0)
    except Exception:
        return 0.0


def _over_threshold(value: float, threshold: float, tolerance: float) -> bool:
    return float(value) > float(threshold) + max(0.0, float(tolerance))


def _near_threshold(value: float, threshold: float, tolerance: float) -> bool:
    return float(value) > float(threshold) and not _over_threshold(value, threshold, tolerance)


def _top_stages(stages: list[dict[str, Any]], *, limit: int = 4) -> list[dict[str, Any]]:
    filtered = [
        {
            "label": str(stage.get("label") or ""),
            "avg_ms": _summary_value(stage, "avg_ms"),
            "p95_ms": _summary_value(stage, "p95_ms"),
            "max_ms": _summary_value(stage, "max_ms"),
            "count": int(stage.get("count", 0) or 0),
        }
        for stage in stages
        if str(stage.get("label") or "").startswith("preview.stage.")
    ]
    filtered.sort(key=lambda item: (item["p95_ms"], item["avg_ms"]), reverse=True)
    return filtered[:limit]


def _coverage_from_row(row: Mapping[str, Any]) -> dict[str, bool]:
    name = _project_name(row).casefold()
    summary = row.get("summary") if isinstance(row.get("summary"), Mapping) else {}
    duration_ms = int(row.get("duration_ms", 0) or 0)
    return {
        "basic_video": int(summary.get("video_clips", 0) or 0) > 0,
        "mask_filter_tracking": any(
            int(summary.get(key, 0) or 0) > 0
            for key in ("clip_filters", "chroma_key", "background_removal", "stabilizer", "clip_masks", "tracked_masks")
        ),
        "nested_timeline": int(summary.get("nested_video_clips", 0) or 0) > 0,
        "actor_heavy": any(
            int(summary.get(key, 0) or 0) > 0
            for key in ("spine_tracks", "spine_clips", "live2d_tracks", "live2d_clips")
        ),
        "audio_heavy": int(summary.get("audio_tracks", 0) or 0) >= 2 or int(summary.get("audio_clips", 0) or 0) >= 2,
        "long_project": duration_ms >= 300_000 or int(summary.get("video_clips", 0) or 0) >= 50,
        "hires_4k": "4k" in name or "2160" in name or "3840" in name,
    }


def _classify_project(row: Mapping[str, Any], thresholds: Mapping[str, float]) -> dict[str, Any]:
    name = _project_name(row)
    seek_summary = _stage_by_label(row, "seek", "preview.seek.render")
    if not seek_summary:
        seek_summary = row.get("frame_summary") if isinstance(row.get("frame_summary"), Mapping) else {}
    playback_summary = row.get("playback_frame_summary") if isinstance(row.get("playback_frame_summary"), Mapping) else {}
    seek_stages = _context_stages(row, "seek")
    playback_stages = _context_stages(row, "playback")
    decode_seek = _stage_by_label(row, "seek", "preview.stage.decode")

    seek_avg = _summary_value(seek_summary, "avg_ms")
    seek_p95 = _summary_value(seek_summary, "p95_ms")
    seek_max = _summary_value(seek_summary, "max_ms")
    playback_avg = _summary_value(playback_summary, "avg_ms")
    playback_p95 = _summary_value(playback_summary, "p95_ms")
    tolerance_ms = float(thresholds.get("measurement_tolerance_ms", 0.0) or 0.0)

    warnings: list[str] = []
    blockers: list[str] = []
    if not row.get("ok", False):
        blockers.append("preview_render_failed")
    if seek_avg > float(thresholds["scrub_avg_ms"]):
        warnings.append("scrub_avg_above_target")
    if _over_threshold(seek_p95, float(thresholds["scrub_p95_ms"]), tolerance_ms):
        blockers.append("scrub_p95_above_target")
    elif _near_threshold(seek_p95, float(thresholds["scrub_p95_ms"]), tolerance_ms):
        warnings.append("scrub_p95_near_target")
    if _over_threshold(seek_max, float(thresholds["scrub_max_ms"]), tolerance_ms):
        blockers.append("scrub_max_stutter")
    elif _near_threshold(seek_max, float(thresholds["scrub_max_ms"]), tolerance_ms):
        warnings.append("scrub_max_near_target")
    if playback_avg > float(thresholds["playback_avg_ms"]):
        warnings.append("playback_avg_above_realtime_budget")
    if playback_p95 > float(thresholds["playback_p95_ms"]):
        blockers.append("playback_p95_above_realtime_budget")
    if decode_seek:
        if _summary_value(decode_seek, "avg_ms") > float(thresholds["decode_seek_avg_ms"]):
            warnings.append("decode_seek_avg_hotspot")
        if _summary_value(decode_seek, "p95_ms") > float(thresholds["decode_seek_p95_ms"]):
            warnings.append("decode_seek_p95_hotspot")

    excellent = (
        seek_avg <= float(thresholds["excellent_scrub_avg_ms"])
        and seek_p95 <= float(thresholds["excellent_scrub_p95_ms"])
        and playback_p95 <= float(thresholds["playback_avg_ms"])
    )
    scrub_ok = not blockers and seek_avg <= float(thresholds["scrub_avg_ms"])
    playback_ok = playback_avg <= float(thresholds["playback_avg_ms"]) and playback_p95 <= float(thresholds["playback_p95_ms"])
    score = 100
    score -= 22 * len(blockers)
    score -= 8 * len(warnings)
    if excellent:
        score += 5
    score = min(100, max(0, score))

    return {
        "project": name,
        "ok": bool(scrub_ok and playback_ok),
        "score": score,
        "tier": "excellent" if excellent else ("ready" if scrub_ok and playback_ok else "needs_work"),
        "warnings": warnings,
        "blockers": blockers,
        "coverage": _coverage_from_row(row),
        "metrics": {
            "seek_avg_ms": round(seek_avg, 2),
            "seek_p95_ms": round(seek_p95, 2),
            "seek_max_ms": round(seek_max, 2),
            "playback_avg_ms": round(playback_avg, 2),
            "playback_p95_ms": round(playback_p95, 2),
            "seek_samples": int(seek_summary.get("count", 0) or 0),
            "playback_samples": int(playback_summary.get("count", 0) or 0),
        },
        "top_seek_stages": _top_stages(seek_stages),
        "top_playback_stages": _top_stages(playback_stages),
    }


def build_preview_scrub_readiness_report(
    perf_report: str | Path | Mapping[str, Any] = "debugCapture/preview_perf_report.json",
    *,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Summarize preview perf data as scrub/seek product readiness."""
    data = _load_report(perf_report)
    merged_thresholds = {**DEFAULT_THRESHOLDS, **dict(thresholds or {})}
    rows = [
        _classify_project(row, merged_thresholds)
        for row in (data.get("preview_render") or [])
        if isinstance(row, Mapping)
    ]

    coverage: dict[str, bool] = {
        "basic_video": False,
        "mask_filter_tracking": False,
        "nested_timeline": False,
        "actor_heavy": False,
        "audio_heavy": False,
        "long_project": False,
        "hires_4k": False,
    }
    for row in rows:
        for key, value in (row.get("coverage") or {}).items():
            coverage[key] = bool(coverage.get(key, False) or value)

    required_release_coverage = [
        "basic_video",
        "mask_filter_tracking",
        "nested_timeline",
        "actor_heavy",
        "audio_heavy",
        "long_project",
        "hires_4k",
    ]
    missing_coverage = [key for key in required_release_coverage if not coverage.get(key)]
    blockers = [row for row in rows if row.get("blockers")]
    warnings = [row for row in rows if row.get("warnings")]
    scores = [int(row.get("score", 0) or 0) for row in rows]
    score = int(round(mean(scores))) if scores else 0
    current_corpus_scrub_ready = bool(rows) and not blockers and all(row.get("ok") for row in rows)
    release_scrub_claim_ready = bool(current_corpus_scrub_ready and not missing_coverage and score >= 85)
    release_blockers: list[str] = []
    if not rows:
        release_blockers.append("preview_perf_report_missing")
    if blockers:
        release_blockers.append("scrub_blockers_present")
    if missing_coverage:
        release_blockers.append("release_coverage_missing")
    if score < 85:
        release_blockers.append("score_below_release_threshold")

    worst_projects = sorted(rows, key=lambda row: (int(row.get("score", 0) or 0), row["metrics"]["seek_p95_ms"]))[:5]
    top_hotspots = []
    for row in rows:
        for stage in row.get("top_seek_stages", [])[:2]:
            top_hotspots.append({
                "project": row.get("project"),
                **stage,
            })
    top_hotspots.sort(key=lambda item: (float(item.get("p95_ms", 0.0)), float(item.get("avg_ms", 0.0))), reverse=True)

    return {
        "ok": current_corpus_scrub_ready,
        "score": score,
        "current_corpus_scrub_ready": current_corpus_scrub_ready,
        "release_scrub_claim_ready": release_scrub_claim_ready,
        "release_blockers": release_blockers,
        "thresholds": merged_thresholds,
        "summary": {
            "projects": len(rows),
            "ready_projects": sum(1 for row in rows if row.get("ok")),
            "warning_projects": len(warnings),
            "blocked_projects": len(blockers),
            "missing_release_coverage": missing_coverage,
        },
        "coverage": coverage,
        "worst_projects": worst_projects,
        "top_seek_hotspots": top_hotspots[:8],
        "projects": rows,
        "claim_guidance": {
            "safe": "steady playback and current-corpus scrub readiness can be reported separately",
            "unsafe_until_ready": "4K/long/actor-heavy scrubbing is always smooth",
            "reason": "Release scrub claims require coverage across basic, mask/filter, nested, actor, audio, long, and 4K projects.",
        },
    }
