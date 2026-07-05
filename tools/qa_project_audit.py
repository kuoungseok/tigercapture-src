"""Audit a real TigerCapture project for export parity and performance risk.

This script does not mutate the project. It answers three practical questions:

1. Are all media/model files referenced by the project still present?
2. Which preview/export parity paths does the project exercise?
3. Which media files should be profiled first for slow preview/export behavior?

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\qa_project_audit.py --project path\\to\\edit.tgp
    .venv\\Scripts\\python.exe tools\\qa_project_audit.py --project path\\to\\edit.tgp --preview-samples 8
    .venv\\Scripts\\python.exe tools\\qa_project_audit.py --synthetic
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_project(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_video_clips(clips: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for clip in clips or []:
        yield clip
        for child in clip.get("nested_child_clips") or []:
            yield from _walk_video_clips([child])
        for track in clip.get("nested_child_tracks") or []:
            yield from _walk_video_clips(track or [])


def _walk_audio_clips(clips: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for clip in clips or []:
        yield clip


def _walk_nested_audio(video_clips: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for clip in _walk_video_clips(video_clips):
        for lane in clip.get("nested_audio_tracks") or []:
            yield from _walk_audio_clips(lane or [])


def _walk_actor_tracks(doc: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for kind, key in (("spine", "spine_actor_tracks"), ("live2d", "live2d_actor_tracks")):
        for track in doc.get(key) or []:
            yield kind, track
    for vt in doc.get("video_tracks") or []:
        for clip in _walk_video_clips(vt.get("clips") or []):
            for track in clip.get("nested_spine_actor_tracks") or []:
                yield "nested_spine", track
            for track in clip.get("nested_live2d_actor_tracks") or []:
                yield "nested_live2d", track


def _collect_paths(doc: dict[str, Any]) -> dict[str, list[str]]:
    paths: dict[str, list[str]] = {
        "video": [],
        "audio": [],
        "media_pool": [],
        "spine": [],
        "live2d": [],
    }
    paths["media_pool"].extend(str(p) for p in doc.get("media_pool") or [] if p)
    for vt in doc.get("video_tracks") or []:
        if vt.get("source_path"):
            paths["video"].append(str(vt["source_path"]))
        for clip in _walk_video_clips(vt.get("clips") or []):
            if clip.get("source_path"):
                paths["video"].append(str(clip["source_path"]))
        for clip in _walk_nested_audio(vt.get("clips") or []):
            if clip.get("source_path"):
                paths["audio"].append(str(clip["source_path"]))
    for at in doc.get("audio_tracks") or []:
        for clip in _walk_audio_clips(at.get("clips") or []):
            if clip.get("source_path"):
                paths["audio"].append(str(clip["source_path"]))
    for kind, track in _walk_actor_tracks(doc):
        target = "spine" if "spine" in kind else "live2d"
        for clip in track.get("clips") or []:
            for key in ("skel_path", "atlas_path", "texture_path", "model_path", "motion_path"):
                if clip.get(key):
                    paths[target].append(str(clip[key]))
    return {key: sorted(set(value)) for key, value in paths.items()}


def _summarize(doc: dict[str, Any]) -> dict[str, Any]:
    counts = Counter()
    for vt in doc.get("video_tracks") or []:
        counts["video_tracks"] += 1
        clips = list(_walk_video_clips(vt.get("clips") or []))
        counts["video_clips"] += len(clips)
        counts["nested_video_clips"] += sum(1 for c in clips if c.get("nested_sequence_id"))
        counts["clip_filters"] += sum(1 for c in clips if c.get("video_filters"))
        counts["chroma_key"] += sum(1 for c in clips if c.get("chroma_key"))
        counts["background_removal"] += sum(1 for c in clips if c.get("bg_removal"))
        counts["stabilizer"] += sum(1 for c in clips if c.get("stabilizer"))
        counts["clip_masks"] += sum(len(c.get("masks") or []) for c in clips)
        counts["tracked_masks"] += sum(
            1
            for c in clips
            for m in c.get("masks") or []
            if m.get("track_object")
        )
    for at in doc.get("audio_tracks") or []:
        counts["audio_tracks"] += 1
        counts["audio_clips"] += len(at.get("clips") or [])
    for kind, track in _walk_actor_tracks(doc):
        counts[f"{kind}_tracks"] += 1
        counts[f"{kind}_clips"] += len(track.get("clips") or [])
    return dict(counts)


def _missing(paths: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        key: [p for p in values if not Path(p).exists()]
        for key, values in paths.items()
        if any(not Path(p).exists() for p in values)
    }


def _probe_media(paths: Iterable[str]) -> list[dict[str, Any]]:
    from app.native_worker import native_media_probe, native_media_probe_many
    from imageio_ffmpeg import get_ffmpeg_exe

    rows: list[dict[str, Any]] = []
    unique_paths = [Path(raw) for raw in sorted(set(paths))]
    ffmpeg_path = get_ffmpeg_exe()
    start = time.perf_counter()
    batch = native_media_probe_many(unique_paths, ffmpeg_path=ffmpeg_path)
    batch_elapsed_ms = (time.perf_counter() - start) * 1000.0
    if batch is not None:
        for path, probe in zip(unique_paths, batch):
            if probe is None:
                rows.append({
                    "path": str(path),
                    "exists": path.exists(),
                    "probe": "unavailable",
                    "batch_elapsed_ms": round(batch_elapsed_ms, 2),
                })
            else:
                rows.append({
                    "path": probe.path,
                    "exists": probe.exists,
                    "duration_ms": probe.duration_ms,
                    "has_video": probe.has_video,
                    "has_audio": probe.has_audio,
                    "width": probe.width,
                    "height": probe.height,
                    "fps": probe.fps,
                    "batch_elapsed_ms": round(batch_elapsed_ms, 2),
                })
        return rows

    for path in unique_paths:
        start = time.perf_counter()
        probe = native_media_probe(path, ffmpeg_path=ffmpeg_path)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if probe is None:
            rows.append({
                "path": str(path),
                "exists": path.exists(),
                "probe": "unavailable",
                "elapsed_ms": round(elapsed_ms, 2),
            })
        else:
            rows.append({
                "path": probe.path,
                "exists": probe.exists,
                "duration_ms": probe.duration_ms,
                "has_video": probe.has_video,
                "has_audio": probe.has_audio,
                "width": probe.width,
                "height": probe.height,
                "fps": probe.fps,
                "elapsed_ms": round(elapsed_ms, 2),
            })
    return rows


def _actor_asset_audit(doc: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, track in _walk_actor_tracks(doc):
        for idx, clip in enumerate(track.get("clips") or []):
            row: dict[str, Any] = {
                "kind": kind,
                "track_id": track.get("id"),
                "clip_index": idx,
                "start_ms": clip.get("start_ms", 0),
                "duration_ms": clip.get("duration_ms", 0),
                "ok": True,
                "issues": [],
            }
            if "spine" in kind:
                required = ("skel_path", "atlas_path")
                optional = ("texture_path",)
                if not clip.get("anim_name"):
                    row["ok"] = False
                    row["issues"].append("missing anim_name")
            else:
                required = ("model_path",)
                optional = ("motion_path",)
            for key in required:
                raw = str(clip.get(key) or "")
                exists = bool(raw and Path(raw).exists())
                row[key] = raw
                row[f"{key}_exists"] = exists
                if not exists:
                    row["ok"] = False
                    row["issues"].append(f"{key} missing")
            for key in optional:
                raw = str(clip.get(key) or "")
                row[key] = raw
                row[f"{key}_exists"] = bool(raw and Path(raw).exists())
            dependencies: list[dict[str, Any]] = []
            if "spine" in kind:
                dependencies.extend(_spine_dependency_rows(clip))
            else:
                dependencies.extend(_live2d_dependency_rows(clip))
            missing_dependencies = [
                dep for dep in dependencies if not bool(dep.get("exists", False))
            ]
            if missing_dependencies:
                row["ok"] = False
                row["issues"].append(
                    f"{len(missing_dependencies)} referenced asset(s) missing"
                )
            row["dependencies"] = dependencies
            if int(clip.get("duration_ms", 0) or 0) <= 0:
                row["ok"] = False
                row["issues"].append("duration_ms must be positive")
            rows.append(row)
    return rows


def _spine_dependency_rows(clip: dict[str, Any]) -> list[dict[str, Any]]:
    """Return texture dependencies referenced by a Spine atlas file."""
    atlas_raw = str(clip.get("atlas_path") or "")
    atlas = Path(atlas_raw) if atlas_raw else None
    if atlas is None or not atlas.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        from app.spine_editor.spine_json_parser import load_atlas_pages

        pages = load_atlas_pages(str(atlas))
    except Exception:
        pages = []
    for page_name in pages:
        texture = (atlas.parent / str(page_name)).resolve()
        rows.append({
            "kind": "spine_atlas_texture",
            "path": str(texture),
            "exists": texture.exists(),
        })
    explicit_texture = str(clip.get("texture_path") or "")
    if explicit_texture:
        texture = Path(explicit_texture)
        rows.append({
            "kind": "spine_texture_path",
            "path": str(texture),
            "exists": texture.exists(),
        })
    return rows


def _live2d_dependency_rows(clip: dict[str, Any]) -> list[dict[str, Any]]:
    """Return file dependencies referenced by a Live2D model3.json file."""
    model_raw = str(clip.get("model_path") or "")
    model = Path(model_raw) if model_raw else None
    if model is None or not model.exists():
        return []
    try:
        data = json.loads(model.read_text(encoding="utf-8"))
    except Exception:
        return []
    refs = data.get("FileReferences") if isinstance(data, dict) else {}
    if not isinstance(refs, dict):
        return []
    rows: list[dict[str, Any]] = []

    def _add(kind: str, raw: str) -> None:
        if not raw:
            return
        path = (model.parent / raw).resolve()
        rows.append({"kind": kind, "path": str(path), "exists": path.exists()})

    _add("live2d_moc", str(refs.get("Moc") or ""))
    for texture in refs.get("Textures") or []:
        _add("live2d_texture", str(texture or ""))
    motions = refs.get("Motions") or {}
    if isinstance(motions, dict):
        for group_rows in motions.values():
            for motion in group_rows or []:
                if isinstance(motion, dict):
                    _add("live2d_motion", str(motion.get("File") or ""))
    expressions = refs.get("Expressions") or []
    for expr in expressions:
        if isinstance(expr, dict):
            _add("live2d_expression", str(expr.get("File") or ""))
    return rows


def _actor_asset_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, dict[str, int]] = {}
    for row in rows:
        kind = str(row.get("kind") or "unknown")
        bucket = by_kind.setdefault(kind, {"total": 0, "ok": 0, "failed": 0})
        bucket["total"] += 1
        if row.get("ok", False):
            bucket["ok"] += 1
        else:
            bucket["failed"] += 1
    failed_rows = [row for row in rows if not row.get("ok", False)]
    return {
        "total": len(rows),
        "ok": len(rows) - len(failed_rows),
        "failed": len(failed_rows),
        "by_kind": by_kind,
    }


def _export_risk_summary(
    doc: dict[str, Any],
    media_probe: list[dict[str, Any]],
    actor_assets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Heuristic export bottleneck/risk candidates for real project QA."""
    summary = _summarize(doc)
    risks: list[dict[str, Any]] = []
    cpu_feature_count = sum(
        int(summary.get(key, 0) or 0)
        for key in (
            "clip_filters",
            "chroma_key",
            "background_removal",
            "stabilizer",
            "clip_masks",
            "tracked_masks",
        )
    )
    if cpu_feature_count:
        risks.append({
            "area": "preview/export CPU fallback",
            "severity": "high" if cpu_feature_count >= 4 else "medium",
            "count": cpu_feature_count,
            "reason": "Clip filters, keying, stabilizer, background removal, or masks can force preview-parity CPU baking.",
        })
    actor_count = sum(
        int(summary.get(key, 0) or 0)
        for key in summary
        if key.endswith("_clips") and ("spine" in key or "live2d" in key)
    )
    if actor_count:
        failed_assets = sum(1 for row in actor_assets if not row.get("ok", False))
        risks.append({
            "area": "Live2D/Spine actor baking",
            "severity": "high" if failed_assets else "medium",
            "count": actor_count,
            "reason": "Actor overlays require render/cache/export parity checks; missing dependencies can drop clips.",
            "failed_assets": failed_assets,
        })
    high_res = [
        row for row in media_probe
        if int(row.get("width", 0) or 0) * int(row.get("height", 0) or 0) >= 3840 * 2160
    ]
    if high_res:
        risks.append({
            "area": "decode/proxy",
            "severity": "high",
            "count": len(high_res),
            "reason": "4K or larger sources should use proxy or measured hardware/frame-server decode.",
        })
    nested = int(summary.get("nested_video_clips", 0) or 0)
    if nested:
        risks.append({
            "area": "nested timeline export",
            "severity": "medium",
            "count": nested,
            "reason": "Nested timelines increase preview/export composition work and should be included in smoke exports.",
        })
    return risks


def _run_synthetic() -> dict[str, Any]:
    cmd = [sys.executable, str(ROOT / "tools" / "verify_export_parity.py")]
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {
        "cmd": cmd,
        "ok": proc.returncode == 0,
        "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 2),
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def _measure_preview_render(project: Path, samples: int) -> dict[str, Any]:
    try:
        from tools.qa_preview_perf import _measure_preview_render as _measure

        return _measure(project, samples=max(1, int(samples)))
    except Exception as exc:
        return {
            "project": str(project),
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _preview_bottleneck_hints(preview_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        from tools.qa_preview_perf import _preview_bottleneck_hints as _hints

        return _hints(preview_rows)
    except Exception:
        return []


def _professional_readiness(doc: dict[str, Any]) -> dict[str, Any]:
    try:
        from app.professional_readiness import build_professional_readiness_report

        return build_professional_readiness_report(doc)
    except Exception as exc:
        return {
            "ok": False,
            "score": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _professional_readiness_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reports = [
        row.get("professional_readiness")
        for row in rows
        if isinstance(row.get("professional_readiness"), dict)
    ]
    if not reports:
        return {"count": 0, "avg_score": 0.0, "high_issues": 0, "medium_issues": 0, "resolve_parity": {}}
    scores = [float(report.get("score", 0.0) or 0.0) for report in reports]
    parity_sections = [
        ((report.get("sections") or {}).get("resolve_post_pipeline_parity") or {})
        for report in reports
        if isinstance((report.get("sections") or {}).get("resolve_post_pipeline_parity"), dict)
    ]
    parity_scores = [float(section.get("score", 0.0) or 0.0) for section in parity_sections]
    category_min_scores: dict[str, float] = {}
    for section in parity_sections:
        category_scores = section.get("category_scores", {}) or {}
        if not isinstance(category_scores, dict):
            continue
        for key, value in category_scores.items():
            try:
                score = float(value or 0.0)
            except Exception:
                continue
            current = category_min_scores.get(str(key))
            category_min_scores[str(key)] = score if current is None else min(current, score)
    return {
        "count": len(reports),
        "avg_score": round(sum(scores) / max(1, len(scores)), 2),
        "min_score": round(min(scores), 2),
        "high_issues": sum(int((r.get("issue_summary") or {}).get("high", 0) or 0) for r in reports),
        "medium_issues": sum(int((r.get("issue_summary") or {}).get("medium", 0) or 0) for r in reports),
        "resolve_parity": {
            "count": len(parity_scores),
            "avg_score": round(sum(parity_scores) / max(1, len(parity_scores)), 2) if parity_scores else 0.0,
            "min_score": round(min(parity_scores), 2) if parity_scores else 0.0,
            "category_min_scores": {key: round(value, 2) for key, value in sorted(category_min_scores.items())},
        },
    }


def _project_key(row: dict[str, Any]) -> str:
    raw = str(row.get("project") or "")
    if not raw:
        return ""
    try:
        return Path(raw).name
    except Exception:
        return raw


def _project_rows_by_key(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = report.get("projects")
    if not isinstance(rows, list):
        rows = [report] if report.get("project") else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = _project_key(row)
        if key:
            out[key] = row
    return out


def _missing_count(row: dict[str, Any]) -> int:
    missing = row.get("missing", {}) or {}
    if not isinstance(missing, dict):
        return 0
    return sum(len(values or []) for values in missing.values())


def _missing_by_kind(row: dict[str, Any]) -> dict[str, int]:
    missing = row.get("missing", {}) or {}
    if not isinstance(missing, dict):
        return {}
    return {
        str(kind): len(values or [])
        for kind, values in sorted(missing.items())
        if values
    }


def _actor_failed_count(row: dict[str, Any]) -> int:
    summary = row.get("actor_asset_summary", {}) or {}
    if isinstance(summary, dict) and "failed" in summary:
        try:
            return int(summary.get("failed", 0) or 0)
        except Exception:
            pass
    return sum(
        1
        for asset in row.get("actor_assets", []) or []
        if isinstance(asset, dict) and not asset.get("ok", False)
    )


def _risk_rows_by_area(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for risk in row.get("export_risks", []) or []:
        if not isinstance(risk, dict):
            continue
        area = str(risk.get("area") or "")
        if area:
            out[area] = risk
    return out


def _preview_perf_report_from_project_qa(report: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in _project_rows_by_key(report).values():
        preview = row.get("preview_render")
        if isinstance(preview, dict):
            rows.append(preview)
    return {"preview_render": rows}


def _append_project_delta(
    regressions: list[dict[str, Any]],
    improvements: list[dict[str, Any]],
    *,
    project: str,
    kind: str,
    metric: str,
    current: int,
    baseline: int,
    detail: dict[str, Any] | None = None,
) -> None:
    delta = int(current) - int(baseline)
    if delta == 0:
        return
    row = {
        "kind": kind,
        "project": project,
        "metric": metric,
        "baseline": int(baseline),
        "current": int(current),
        "delta": int(delta),
    }
    if detail:
        row.update(detail)
    if delta > 0:
        row["severity"] = "high" if delta >= 2 else "medium"
        regressions.append(row)
    else:
        row["severity"] = "improved"
        improvements.append(row)


def compare_project_qa_reports(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    preview_abs_threshold_ms: float = 5.0,
    preview_rel_threshold: float = 0.25,
) -> dict[str, Any]:
    """Compare real-project QA reports and flag product-facing regressions."""
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    current_rows = _project_rows_by_key(current)
    baseline_rows = _project_rows_by_key(baseline)

    for key in sorted(set(current_rows) & set(baseline_rows)):
        row = current_rows[key]
        old = baseline_rows[key]
        if old.get("ok", False) and not row.get("ok", False):
            regressions.append({
                "kind": "project_status",
                "project": key,
                "metric": "ok",
                "baseline": True,
                "current": False,
                "severity": "high",
                "missing_by_kind": _missing_by_kind(row),
                "actor_failed": _actor_failed_count(row),
            })
        elif row.get("ok", False) and not old.get("ok", False):
            improvements.append({
                "kind": "project_status",
                "project": key,
                "metric": "ok",
                "baseline": False,
                "current": True,
                "severity": "improved",
            })

        _append_project_delta(
            regressions,
            improvements,
            project=key,
            kind="missing_media",
            metric="missing_count",
            current=_missing_count(row),
            baseline=_missing_count(old),
            detail={"missing_by_kind": _missing_by_kind(row)},
        )
        _append_project_delta(
            regressions,
            improvements,
            project=key,
            kind="actor_assets",
            metric="failed_count",
            current=_actor_failed_count(row),
            baseline=_actor_failed_count(old),
        )

        current_risks = _risk_rows_by_area(row)
        baseline_risks = _risk_rows_by_area(old)
        for area in sorted(set(current_risks) | set(baseline_risks)):
            risk = current_risks.get(area, {})
            old_risk = baseline_risks.get(area, {})
            _append_project_delta(
                regressions,
                improvements,
                project=key,
                kind="export_risk",
                metric="count",
                current=int(risk.get("count", 0) or 0),
                baseline=int(old_risk.get("count", 0) or 0),
                detail={
                    "area": area,
                    "severity_after": str(risk.get("severity") or ""),
                    "reason": str(risk.get("reason") or old_risk.get("reason") or ""),
                },
            )
            _append_project_delta(
                regressions,
                improvements,
                project=key,
                kind="export_risk",
                metric="failed_assets",
                current=int(risk.get("failed_assets", 0) or 0),
                baseline=int(old_risk.get("failed_assets", 0) or 0),
                detail={
                    "area": area,
                    "severity_after": str(risk.get("severity") or ""),
                    "reason": str(risk.get("reason") or old_risk.get("reason") or ""),
                },
            )

    if baseline.get("synthetic_export_parity", {}).get("ok", True) and not current.get("synthetic_export_parity", {}).get("ok", True):
        regressions.append({
            "kind": "synthetic_export_parity",
            "project": "",
            "metric": "ok",
            "baseline": True,
            "current": False,
            "severity": "high",
        })
    elif current.get("synthetic_export_parity", {}).get("ok", True) and not baseline.get("synthetic_export_parity", {}).get("ok", True):
        improvements.append({
            "kind": "synthetic_export_parity",
            "project": "",
            "metric": "ok",
            "baseline": False,
            "current": True,
            "severity": "improved",
        })

    preview_comparison: dict[str, Any] = {}
    try:
        from tools.qa_preview_perf import compare_preview_perf_reports

        preview_comparison = compare_preview_perf_reports(
            _preview_perf_report_from_project_qa(current),
            _preview_perf_report_from_project_qa(baseline),
            abs_threshold_ms=preview_abs_threshold_ms,
            rel_threshold=preview_rel_threshold,
        )
    except Exception as exc:
        preview_comparison = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    regressions.sort(key=lambda row: (str(row.get("project") or ""), str(row.get("kind") or ""), str(row.get("metric") or "")))
    improvements.sort(key=lambda row: (str(row.get("project") or ""), str(row.get("kind") or ""), str(row.get("metric") or "")))
    new_projects = sorted(set(current_rows) - set(baseline_rows))
    missing_projects = sorted(set(baseline_rows) - set(current_rows))
    preview_regressions = int((preview_comparison.get("summary") or {}).get("regressions", 0) or 0)
    return {
        "ok": not regressions and preview_comparison.get("ok", True),
        "thresholds": {
            "preview_abs_threshold_ms": float(preview_abs_threshold_ms),
            "preview_rel_threshold": float(preview_rel_threshold),
        },
        "summary": {
            "regressions": len(regressions),
            "improvements": len(improvements),
            "preview_regressions": preview_regressions,
            "new_projects": len(new_projects),
            "missing_projects": len(missing_projects),
        },
        "regressions": regressions,
        "improvements": improvements,
        "new_projects": new_projects,
        "missing_projects": missing_projects,
        "preview_performance": preview_comparison,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, help="Path to a .tgp project.")
    parser.add_argument("--manifest", type=Path, help="Audit every project listed in a QA corpus manifest.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/project_qa_report.json"))
    parser.add_argument("--synthetic", action="store_true", help="Run synthetic export parity smoke tests too.")
    parser.add_argument("--preview-samples", type=int, default=0, help="Also sample ProjectPlayer preview renders per project.")
    parser.add_argument("--fail-on-missing", action="store_true", help="Exit non-zero when project files are missing.")
    parser.add_argument("--baseline", type=Path, help="Previous project QA JSON report to compare against.")
    parser.add_argument("--baseline-preview-abs-ms", type=float, default=5.0, help="Minimum preview ms delta for baseline regressions.")
    parser.add_argument("--baseline-preview-rel", type=float, default=0.25, help="Minimum preview relative delta for baseline regressions.")
    args = parser.parse_args()

    report: dict[str, Any] = {"ok": True}
    try:
        from app.preview_engine_status import preview_engine_status
        report["preview_engine"] = preview_engine_status()
    except Exception:
        report["preview_engine"] = {}
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        projects = [Path(p) for p in manifest.get("projects", [])]
        reports = []
        for project in projects:
            doc = _load_project(project)
            paths = _collect_paths(doc)
            missing = _missing(paths)
            media_paths = paths.get("video", []) + paths.get("audio", [])
            actor_assets = _actor_asset_audit(doc)
            preview_render = (
                _measure_preview_render(project, args.preview_samples)
                if args.preview_samples > 0
                else None
            )
            project_report = {
                "project": str(project),
                "summary": _summarize(doc),
                "paths": paths,
                "missing": missing,
                "actor_asset_summary": _actor_asset_summary(actor_assets),
                "actor_assets": actor_assets,
                "professional_readiness": _professional_readiness(doc),
                "ok": not missing and all(row.get("ok", False) for row in actor_assets),
            }
            project_report["media_probe"] = _probe_media([
                p for p in media_paths if Path(p).exists()
            ])
            project_report["export_risks"] = _export_risk_summary(
                doc,
                project_report["media_probe"],
                actor_assets,
            )
            if preview_render is not None:
                project_report["preview_render"] = preview_render
                project_report["ok"] = bool(
                    project_report["ok"] and preview_render.get("ok", False)
                )
            reports.append(project_report)
        report.update({
            "manifest": str(args.manifest),
            "project_count": len(projects),
            "projects": reports,
        })
        report["professional_readiness_summary"] = _professional_readiness_summary(reports)
        report["ok"] = all(item.get("ok", False) for item in reports)
        preview_rows = [
            item["preview_render"]
            for item in reports
            if isinstance(item.get("preview_render"), dict)
        ]
        if preview_rows:
            report["native_gpu_candidates"] = _preview_bottleneck_hints(preview_rows)
    if args.project:
        doc = _load_project(args.project)
        paths = _collect_paths(doc)
        missing = _missing(paths)
        media_paths = paths.get("video", []) + paths.get("audio", [])
        actor_assets = _actor_asset_audit(doc)
        preview_render = (
            _measure_preview_render(args.project, args.preview_samples)
            if args.preview_samples > 0
            else None
        )
        report.update({
            "project": str(args.project),
            "summary": _summarize(doc),
            "paths": paths,
            "missing": missing,
            "actor_asset_summary": _actor_asset_summary(actor_assets),
            "actor_assets": actor_assets,
            "professional_readiness": _professional_readiness(doc),
        })
        report["media_probe"] = _probe_media([
            p for p in media_paths if Path(p).exists()
        ])
        report["export_risks"] = _export_risk_summary(
            doc,
            report["media_probe"],
            actor_assets,
        )
        if preview_render is not None:
            report["preview_render"] = preview_render
            report["native_gpu_candidates"] = _preview_bottleneck_hints([preview_render])
        if missing or not all(row.get("ok", False) for row in actor_assets):
            report["ok"] = False
        if preview_render is not None and not preview_render.get("ok", False):
            report["ok"] = False
    if args.synthetic:
        synthetic = _run_synthetic()
        report["synthetic_export_parity"] = synthetic
        report["ok"] = bool(report["ok"] and synthetic["ok"])
    if args.baseline and args.baseline.exists():
        baseline_report = json.loads(args.baseline.read_text(encoding="utf-8"))
        comparison = compare_project_qa_reports(
            report,
            baseline_report,
            preview_abs_threshold_ms=args.baseline_preview_abs_ms,
            preview_rel_threshold=args.baseline_preview_rel,
        )
        report["baseline_comparison"] = comparison
        report["ok"] = bool(report.get("ok", False) and comparison.get("ok", False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")

    if args.fail_on_missing and not report["ok"]:
        return 1
    if args.baseline and report.get("baseline_comparison") and not report["baseline_comparison"].get("ok", True):
        return 1
    if args.synthetic and not report.get("synthetic_export_parity", {}).get("ok", False):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
