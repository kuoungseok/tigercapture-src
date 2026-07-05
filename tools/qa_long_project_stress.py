"""Lightweight long-project stress QA.

This verifies that the persistent QA corpus contains a large enough project to
exercise timeline scale, nested clips, proxy state, recovery candidates, and
media/relink surfaces without rendering hundreds of frames on every run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _walk_video_clips(clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for clip in clips or []:
        if not isinstance(clip, dict):
            continue
        rows.append(clip)
        for child in clip.get("nested_child_clips") or []:
            if isinstance(child, dict):
                rows.extend(_walk_video_clips([child]))
        for track in clip.get("nested_child_tracks") or []:
            rows.extend(_walk_video_clips([c for c in (track or []) if isinstance(c, dict)]))
    return rows


def _clip_end_ms(clip: dict[str, Any]) -> int:
    start = int(clip.get("timeline_in_ms", clip.get("offset_ms", 0)) or 0)
    if "source_out_ms" in clip:
        dur = int(clip.get("source_out_ms", 0) or 0) - int(clip.get("source_in_ms", 0) or 0)
    else:
        dur = int(clip.get("duration_ms", 0) or 0)
    return start + max(0, dur)


def _project_duration_ms(doc: dict[str, Any]) -> int:
    ends: list[int] = []
    for track in doc.get("video_tracks") or []:
        ends.extend(_clip_end_ms(clip) for clip in _walk_video_clips(track.get("clips") or []))
    for track in doc.get("audio_tracks") or []:
        ends.extend(_clip_end_ms(clip) for clip in (track.get("clips") or []) if isinstance(clip, dict))
    return max(ends or [0])


def _count_nested(doc: dict[str, Any]) -> int:
    count = 0
    for track in doc.get("video_tracks") or []:
        for clip in _walk_video_clips(track.get("clips") or []):
            if clip.get("nested_sequence_id") or clip.get("nested_child_tracks") or clip.get("nested_audio_tracks"):
                count += 1
    return count


def _ensure_fixtures() -> None:
    from tools.build_qa_corpus import build_corpus

    project = ROOT / "qa_corpus" / "projects" / "06_long_project_stress.tgp"
    recovery = ROOT / "qa_corpus" / "projects" / ".tigercapture_recovery" / "01_timeline_audio_basic~autosave.tgp"
    samples = ROOT / "qa_corpus" / "color_audio_samples"
    if not project.exists() or not recovery.exists() or not samples.exists():
        build_corpus(ROOT / "qa_corpus")


def run_long_project_stress_qa(
    project: Path | None = None,
    *,
    ensure_fixtures: bool = True,
) -> dict[str, Any]:
    if ensure_fixtures:
        _ensure_fixtures()
    project = project or ROOT / "qa_corpus" / "projects" / "06_long_project_stress.tgp"
    doc = _load_json(project)

    from tools.qa_project_audit import _actor_asset_audit, _collect_paths, _missing, _summarize
    from tools.repair_project import _candidate_paths_from_roots, audit_recovery_candidates, repair_project_doc

    fixed, repair = repair_project_doc(doc)
    summary = _summarize(fixed)
    paths = _collect_paths(fixed)
    missing = _missing(paths)
    missing_count = sum(len(v or []) for v in missing.values())
    actor_assets = _actor_asset_audit(fixed)
    actor_failed = sum(1 for row in actor_assets if not row.get("ok", False))
    duration_ms = _project_duration_ms(fixed)
    nested_count = _count_nested(fixed)
    proxy_enabled = bool((fixed.get("proxy") or {}).get("enabled"))
    manifest = _load_json(ROOT / "qa_corpus" / "qa_corpus_manifest.json")
    manifest_projects = {str(Path(p)) for p in manifest.get("projects", []) or []}
    in_manifest = str(project.resolve()) in manifest_projects
    recovery_report = audit_recovery_candidates(
        _candidate_paths_from_roots([ROOT / "qa_corpus" / "projects"])
    )
    best_health = ((recovery_report.get("product_summary") or {}).get("best_health") or {})
    checks = {
        "project_exists": project.exists(),
        "duration_at_least_5min": duration_ms >= 300_000,
        "video_clips_at_least_100": int(summary.get("video_clips", 0) or 0) >= 100,
        "audio_clips_at_least_120": int(summary.get("audio_clips", 0) or 0) >= 120,
        "nested_sequences_present": nested_count >= 2,
        "proxy_enabled": proxy_enabled,
        "no_missing_media": missing_count == 0,
        "actor_assets_ok": actor_failed == 0,
        "manifest_includes_project": in_manifest,
        "recovery_candidate_open_safe": best_health.get("level") == "open_safe",
        "repair_report_ok": bool(repair.get("ok")),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "project": str(project),
        "summary": {
            "duration_ms": duration_ms,
            "video_tracks": int(summary.get("video_tracks", 0) or 0),
            "video_clips": int(summary.get("video_clips", 0) or 0),
            "audio_tracks": int(summary.get("audio_tracks", 0) or 0),
            "audio_clips": int(summary.get("audio_clips", 0) or 0),
            "nested_sequences": nested_count,
            "missing_count": missing_count,
            "actor_failed": actor_failed,
            "recovery_level": best_health.get("level", ""),
        },
        "checks": checks,
        "failures": failures,
        "missing": missing,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run long-project stress QA.")
    parser.add_argument("--project", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=Path("debugCapture/long_project_stress_qa.json"))
    parser.add_argument("--no-ensure-fixtures", action="store_true")
    args = parser.parse_args()
    report = run_long_project_stress_qa(args.project, ensure_fixtures=not args.no_ensure_fixtures)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
