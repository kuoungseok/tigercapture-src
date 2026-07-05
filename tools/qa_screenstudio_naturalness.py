from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qa_screenstudio_auto_polish import DEFAULT_MANIFEST, _load_manifest, _resolve  # noqa: E402


def _candidate_quality(candidate: dict[str, Any]) -> dict[str, Any]:
    frame_w = max(1, int(candidate.get("frame_w", 1) or 1))
    frame_h = max(1, int(candidate.get("frame_h", 1) or 1))
    x = int(candidate.get("target_x", 0) or 0)
    y = int(candidate.get("target_y", 0) or 0)
    w = max(1, int(candidate.get("target_w", frame_w) or frame_w))
    h = max(1, int(candidate.get("target_h", frame_h) or frame_h))
    px = float(candidate.get("x_norm", 0.5) or 0.5) * frame_w
    py = float(candidate.get("y_norm", 0.5) or 0.5) * frame_h
    rel_x = (px - x) / w
    rel_y = (py - y) / h
    start = int(candidate.get("start_ms", 0) or 0)
    end = int(candidate.get("end_ms", 0) or 0)
    span = max(0, end - start)
    inside = 0.0 <= rel_x <= 1.0 and 0.0 <= rel_y <= 1.0
    breathing = 0.045 <= rel_x <= 0.955 and 0.045 <= rel_y <= 0.955
    duration_ok = 700 <= span <= 2600
    crop_ok = 0 <= x < frame_w and 0 <= y < frame_h and x + w <= frame_w and y + h <= frame_h
    return {
        "kind": str(candidate.get("kind") or "action"),
        "point_ms": int(candidate.get("point_ms", 0) or 0),
        "span_ms": span,
        "relative_x": round(rel_x, 4),
        "relative_y": round(rel_y, 4),
        "inside": bool(inside),
        "breathing": bool(breathing),
        "duration_ok": bool(duration_ok),
        "crop_ok": bool(crop_ok),
        "ok": bool(inside and breathing and duration_ok and crop_ok),
    }


def _overlap_quality(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    enabled = [
        c for c in candidates
        if isinstance(c, dict) and c.get("enabled", True)
    ]
    windows = sorted(
        (
            int(c.get("start_ms", 0) or 0),
            int(c.get("end_ms", 0) or 0),
            str(c.get("kind") or "action"),
        )
        for c in enabled
    )
    overlaps = []
    for left, right in zip(windows, windows[1:]):
        if right[0] < left[1]:
            overlaps.append({
                "left_kind": left[2],
                "right_kind": right[2],
                "overlap_ms": int(left[1] - right[0]),
            })
    return {
        "window_count": len(windows),
        "overlap_count": len(overlaps),
        "overlaps": overlaps[:8],
        "ok": not overlaps,
    }


def _rhythm_quality(
    candidates: list[dict[str, Any]],
    *,
    duration_ms: int,
    timing_profile: dict[str, Any],
) -> dict[str, Any]:
    points = sorted(
        int(c.get("point_ms", c.get("start_ms", 0)) or 0)
        for c in candidates
        if isinstance(c, dict) and c.get("enabled", True)
    )
    if not points:
        return {"ok": False, "reason": "no_zoom_points", "point_count": 0}
    rhythm_gap = int((timing_profile or {}).get("rhythm_gap_ms", 0) or 0)
    loose_floor = max(900, int(rhythm_gap * 0.45))
    gaps = [right - left for left, right in zip(points, points[1:])]
    tight_gap_count = sum(1 for gap in gaps if gap < loose_floor)
    coverage_ok = True
    if duration_ms >= 30_000 and len(points) >= 3:
        coverage_ok = points[-1] >= int(duration_ms * 0.45)
    return {
        "ok": bool(tight_gap_count == 0 and coverage_ok),
        "point_count": len(points),
        "first_point_ms": points[0],
        "last_point_ms": points[-1],
        "min_gap_ms": min(gaps) if gaps else 0,
        "rhythm_gap_ms": rhythm_gap,
        "tight_gap_count": tight_gap_count,
        "coverage_ok": bool(coverage_ok),
    }


def _loop_quality(source: Path, duration_ms: int) -> dict[str, Any]:
    from app.screenstudio_polish import cursor_state_at, load_cursor_sidecar

    events = load_cursor_sidecar(source)
    if len(events) < 2:
        return {"ok": False, "reason": "not_enough_cursor_events"}
    first = next((ev for ev in events if ev.visible), events[0])
    probe_ms = max(0, int(duration_ms) - 80)
    state = cursor_state_at(
        events,
        probe_ms,
        smoothing=0.0,
        duration_ms=duration_ms,
        loop_cursor=True,
        loop_return_ms=920,
        hide_after_ms=max(10_000, int(duration_ms) + 1000),
    )
    if state is None:
        return {"ok": False, "reason": "no_cursor_state"}
    distance = abs(float(state["x_norm"]) - float(first.x_norm)) + abs(float(state["y_norm"]) - float(first.y_norm))
    return {
        "ok": bool(distance <= 0.14),
        "probe_ms": probe_ms,
        "distance": round(distance, 4),
        "x_norm": round(float(state["x_norm"]), 4),
        "y_norm": round(float(state["y_norm"]), 4),
    }


def _export_intent_rows() -> list[dict[str, Any]]:
    from app.screenstudio_polish import screenstudio_default_export_settings, screenstudio_starter_defaults

    scenarios = [
        ("screen-recording-demo", "web_demo", "mp4", "high", 60.0, 1920, 1080),
        ("vertical-shorts", "social_vertical", "mp4", "high", 60.0, 1080, 1920),
        ("product-demo", "product_web", "mp4", "high", 30.0, 1920, 1080),
        ("actor-showcase", "editor_roundtrip", "mov", "best", 24.0, 1920, 1080),
    ]
    rows: list[dict[str, Any]] = []
    for starter, intent, fmt, quality, fps, width, height in scenarios:
        settings = {
            "starter_template_id": starter,
            "canvas_width": width,
            "canvas_height": height,
            "fps": fps,
            "screenstudio_polish": screenstudio_starter_defaults(starter),
        }
        export = screenstudio_default_export_settings(settings)
        ok = (
            export.get("intent_id") == intent
            and export.get("format_id") == fmt
            and export.get("quality_id") == quality
            and tuple(export.get("resolution") or ()) == (width, height)
            and bool(export.get("share_package_ready")) is True
        )
        if starter in {"screen-recording-demo", "vertical-shorts"}:
            ok = ok and float(export.get("fps", 0.0) or 0.0) == 60.0
        if starter in {"screen-recording-demo", "vertical-shorts", "product-demo"}:
            ok = ok and bool(export.get("clipboard_ready")) is True
        if starter == "actor-showcase":
            ok = ok and bool(export.get("clipboard_ready")) is False
        rows.append({
            "starter": starter,
            "intent_id": export.get("intent_id"),
            "format_id": export.get("format_id"),
            "quality_id": export.get("quality_id"),
            "fps": export.get("fps"),
            "resolution": list(export.get("resolution") or []),
            "destinations": list(export.get("destinations") or []),
            "clipboard_ready": bool(export.get("clipboard_ready")),
            "share_package_ready": bool(export.get("share_package_ready")),
            "share_link_ready": bool(export.get("share_link_ready")),
            "handoff_label": str(export.get("handoff_label") or ""),
            "post_export_actions": list(export.get("post_export_actions") or []),
            "ok": bool(ok),
        })
    return rows


def _sample_row(sample: dict[str, Any]) -> dict[str, Any]:
    from app.screenstudio_polish import screenstudio_sidecar_report

    source = _resolve(str(sample.get("source") or ""))
    duration_ms = int(sample.get("duration_ms", 0) or 0)
    report = screenstudio_sidecar_report(
        source,
        duration_ms=duration_ms,
        frame_w=int(sample.get("frame_w", 1920) or 1920),
        frame_h=int(sample.get("frame_h", 1080) or 1080),
        include_parity=True,
    )
    candidates = [
        c for c in list(report.get("zoom_candidates") or [])
        if isinstance(c, dict) and c.get("enabled", True)
    ]
    candidate_rows = [_candidate_quality(c) for c in candidates]
    overlap = _overlap_quality(candidates)
    rhythm = _rhythm_quality(
        candidates,
        duration_ms=duration_ms,
        timing_profile=dict(report.get("zoom_timing_profile") or {}),
    )
    loop = _loop_quality(source, duration_ms)
    failures: list[str] = []
    if not candidates:
        failures.append("no_zoom_candidates")
    if any(not row.get("ok") for row in candidate_rows):
        failures.append("weak_zoom_candidate_framing")
    if not overlap.get("ok"):
        failures.append("overlapping_zoom_windows")
    if not rhythm.get("ok"):
        failures.append("zoom_rhythm_not_natural")
    if not loop.get("ok"):
        failures.append("cursor_loopback_not_natural")
    if not report.get("parity_ok"):
        failures.append("preview_export_parity_mismatch")
    score = 100
    score -= 18 * len(failures)
    if int(report.get("auto_zoom_count", 0) or 0) > 5:
        score -= 8
    return {
        "id": str(sample.get("id") or source.stem),
        "ok": not failures,
        "score": max(0, int(score)),
        "failures": failures,
        "auto_zoom_count": int(report.get("auto_zoom_count", 0) or 0),
        "candidate_quality": candidate_rows[:8],
        "overlap": overlap,
        "rhythm": rhythm,
        "loop": loop,
        "parity_ok": bool(report.get("parity_ok")),
        "zoom_timing_profile": dict(report.get("zoom_timing_profile") or {}),
    }


def run_screenstudio_naturalness_qa(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    samples = [
        _sample_row(sample)
        for sample in list(manifest.get("samples") or [])
        if isinstance(sample, dict)
    ]
    export_intents = _export_intent_rows()
    failures = [
        {"id": row["id"], "failures": row["failures"]}
        for row in samples
        if not row.get("ok")
    ]
    for row in export_intents:
        if not row.get("ok"):
            failures.append({"id": f"export:{row.get('starter')}", "failures": ["export_intent_mismatch"]})
    avg_score = round(sum(int(row.get("score", 0) or 0) for row in samples) / max(1, len(samples)), 2)
    long_samples = [
        row for row, sample in zip(samples, list(manifest.get("samples") or []))
        if int((sample or {}).get("duration_ms", 0) or 0) >= 60_000
    ]
    return {
        "ok": not failures and bool(samples),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "summary": {
            "samples": len(samples),
            "passing": sum(1 for row in samples if row.get("ok")),
            "failing": sum(1 for row in samples if not row.get("ok")),
            "avg_score": avg_score,
            "loopback_ok": sum(1 for row in samples if (row.get("loop") or {}).get("ok")),
            "rhythm_ok": sum(1 for row in samples if (row.get("rhythm") or {}).get("ok")),
            "edge_safe_candidates": sum(
                1
                for row in samples
                for candidate in list(row.get("candidate_quality") or [])
                if candidate.get("ok")
            ),
            "export_intents": sum(1 for row in export_intents if row.get("ok")),
            "handoff_ready": sum(1 for row in export_intents if row.get("share_package_ready")),
            "long_samples": len(long_samples),
            "long_rhythm_ok": sum(1 for row in long_samples if (row.get("rhythm") or {}).get("ok")),
            "long_coverage_ok": sum(1 for row in long_samples if (row.get("rhythm") or {}).get("coverage_ok")),
        },
        "samples": samples,
        "export_intents": export_intents,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Screen Studio naturalness QA.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/screenstudio_naturalness_qa.json"))
    args = parser.parse_args()
    report = run_screenstudio_naturalness_qa(args.manifest)
    out = args.out
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out)}, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
