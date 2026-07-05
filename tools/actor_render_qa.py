"""Run Live2D/Spine corpus compatibility and render QA in one report."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.actor_compat_matrix import build_actor_compat_matrix, load_known_failures


PASS_STATUSES = {"pass"}


def _model_key(kind: str, path: Any) -> str:
    raw = str(path or "").replace("\\", "/")
    return f"{kind}:{raw.lower()}"


def _status_counts(results: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        status = str(result.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def _result_path(result: dict[str, Any]) -> str:
    return str(result.get("path") or result.get("source") or "")


def _render_recommendation(kind: str, result: dict[str, Any]) -> str:
    status = str(result.get("status") or "unknown")
    quality = _render_quality(kind, result)
    category = str(quality.get("category") or "")
    if category == "animation_sweep_blank":
        return "Base render passed but animation sweep produced blank frames; inspect animation duration, looping, skin/slot attachments, and pose sampling."
    if category == "animation_sweep_failed":
        return "Animation sweep failed after base render; reproduce the single model and inspect sweep error details."
    if category == "golden_mismatch":
        return "Golden-image comparison changed; inspect the saved actual image before accepting a new baseline."
    if status == "blank" and kind == "spine":
        return "Model rendered but produced no alpha pixels; inspect atlas page paths, skin selection, scale, and animation pose."
    if status == "blank" and kind == "live2d":
        return "Model loaded but produced no visible pixels; inspect normalized runtime path, texture placement, pose/motion setup, and offscreen GL support."
    if status == "render_none" and kind == "live2d":
        return "Live2D renderer returned no image; inspect runtime normalization, MOC support, offscreen GL context creation, and renderer stderr/log output."
    if status == "crash" and kind == "live2d":
        return "Open stderr_tail first; Live2D render QA isolates each model so the failing sample can be reproduced safely."
    if status == "unsupported":
        return "Keep the sample in the corpus but exclude it from render pass until the runtime supports this model format/version."
    if status == "timeout":
        return "Re-run the single model with a larger timeout and check whether initialization or texture upload is hanging."
    return "Inspect the raw render result, stderr_tail, and compatibility row for this model."


def _render_quality(kind: str, result: dict[str, Any]) -> dict[str, Any]:
    """Classify render result quality beyond the coarse renderer status.

    A base frame can pass while animation sweep or golden regression still
    fails.  Keeping this as a small taxonomy makes large corpus reports useful
    without manually opening every raw row.
    """
    status = str(result.get("status") or "unknown")
    if status not in PASS_STATUSES:
        error = str(result.get("error") or result.get("stderr_tail") or "").lower()
        if status == "blank":
            category = "blank_alpha"
        elif status == "render_none":
            category = "render_none"
        elif status == "timeout":
            category = "timeout"
        elif status == "crash":
            category = "runtime_crash"
        elif status == "unsupported":
            category = "unsupported_runtime"
        elif "atlas" in error or "texture" in error:
            category = "asset_texture_or_atlas"
        elif "motion" in error:
            category = "motion_load"
        elif "json" in error or "parse" in error:
            category = "parser_or_json"
        else:
            category = "render_failed"
        return {
            "ok": False,
            "status": status,
            "category": category,
            "severity": "high" if status in {"crash", "timeout"} else "medium",
        }

    sweep = result.get("animation_sweep")
    if isinstance(sweep, dict):
        sweep_status = str(sweep.get("status") or "")
        blank_frames = int(sweep.get("blank_frames", 0) or 0)
        if sweep_status in {"fail", "crash", "timeout"}:
            return {
                "ok": False,
                "status": "animation_sweep",
                "category": "animation_sweep_failed",
                "severity": "high",
            }
        if blank_frames > 0 or sweep_status == "blank":
            return {
                "ok": False,
                "status": "animation_sweep",
                "category": "animation_sweep_blank",
                "severity": "medium",
                "blank_frames": blank_frames,
            }

    golden = result.get("golden")
    if isinstance(golden, dict):
        golden_status = str(golden.get("status") or "")
        if golden_status == "mismatch":
            return {
                "ok": False,
                "status": "golden",
                "category": "golden_mismatch",
                "severity": "medium",
            }
        if golden_status == "render_failed":
            return {
                "ok": False,
                "status": "golden",
                "category": "golden_render_failed",
                "severity": "medium",
            }

    return {"ok": True, "status": status, "category": "pass", "severity": "none"}


def _render_result_ok(kind: str, result: dict[str, Any]) -> bool:
    return bool(_render_quality(kind, result).get("ok"))


def _annotate_render_quality(render: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    for kind, section in render.items():
        annotated: list[dict[str, Any]] = []
        for raw in section.get("results", []) or []:
            result = dict(raw)
            quality = _render_quality(str(kind), result)
            result["quality"] = quality
            if not quality.get("ok"):
                result["failure_category"] = str(quality.get("category") or "render_failed")
                result["failure_severity"] = str(quality.get("severity") or "medium")
            annotated.append(result)
        section["results"] = annotated
        section["ok"] = all(
            _render_result_ok(str(kind), result) or result.get("quarantined")
            for result in annotated
        )
    return render


def _failure_rows(kind: str, results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        status = str(result.get("status") or "unknown")
        if _render_result_ok(kind, result):
            continue
        if result.get("quarantined"):
            continue
        quality = _render_quality(kind, result)
        rows.append({
            "kind": kind,
            "status": status,
            "quality_status": str(quality.get("status") or status),
            "failure_category": str(quality.get("category") or "render_failed"),
            "failure_severity": str(quality.get("severity") or "medium"),
            "path": _result_path(result),
            "error": str(result.get("error") or ""),
            "runtime": str(result.get("runtime") or ""),
            "recommendation": _render_recommendation(kind, result),
        })
    return rows


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(Path(path).resolve()) if Path(path).exists() else str(Path(path))
        if key in seen:
            continue
        seen.add(key)
        out.append(Path(path))
    return out


def _apply_limit(paths: list[Path], limit: int) -> list[Path]:
    if int(limit or 0) <= 0:
        return paths
    return paths[: int(limit)]


def _top_risk_candidate_paths(
    compat: dict[str, Any],
    kind: str,
    *,
    limit: int = 0,
) -> list[Path]:
    rows = [
        row for row in compat.get("rows", []) or []
        if isinstance(row, dict)
        and str(row.get("kind") or "") == kind
        and bool(row.get("ok"))
        and int(row.get("risk_score", 0) or 0) > 0
    ]
    rows.sort(key=lambda row: (
        -int(row.get("risk_score", 0) or 0),
        str(row.get("family") or ""),
        str(row.get("model_name") or ""),
    ))
    if int(limit or 0) > 0:
        rows = rows[: int(limit)]
    return [Path(str(row.get("path"))) for row in rows if row.get("path")]


def _render_spine_roots(
    roots: Iterable[Path | str],
    *,
    limit: int = 0,
    width: int = 720,
    height: int = 720,
    explicit_candidates: Iterable[Path] | None = None,
    animation_sweep: bool = False,
    sweep_samples: int = 5,
    candidate_finder: Callable[[Path], list[Path]] | None = None,
    runner: Callable[[Path, int, int], dict[str, Any]] | None = None,
    sweep_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render-test Spine candidates and return compact counts plus rows."""
    if candidate_finder is None:
        from tools.test_spine_resources import _candidates as candidate_finder
    if runner is None:
        from tools.test_spine_resources import _test_one as runner
    if sweep_runner is None and animation_sweep:
        from tools.test_spine_resources import sweep_one as sweep_runner

    if explicit_candidates is not None:
        candidates = _dedupe_paths([Path(path) for path in explicit_candidates])
        candidates = _apply_limit(candidates, limit)
    else:
        candidates = []
        for root in roots:
            candidates.extend(candidate_finder(Path(root)))
        candidates = _apply_limit(_dedupe_paths(candidates), limit)

    results: list[dict[str, Any]] = []
    for path in candidates:
        result = dict(runner(path, int(width), int(height)))
        result.setdefault("path", str(path))
        result.setdefault("status", "unknown")
        if animation_sweep and sweep_runner is not None:
            try:
                result["animation_sweep"] = dict(
                    sweep_runner(
                        path,
                        int(width),
                        int(height),
                        samples=int(sweep_samples or 5),
                    )
                )
            except Exception as exc:
                result["animation_sweep"] = {
                    "path": str(path),
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        results.append(result)

    counts = _status_counts(results)
    return {
        "kind": "spine",
        "total": len(results),
        "counts": counts,
        "ok": all(status in PASS_STATUSES for status in counts),
        "results": results,
    }


def _render_live2d_roots(
    roots: Iterable[Path | str],
    *,
    limit: int = 0,
    width: int = 320,
    height: int = 240,
    timeout: int = 30,
    explicit_candidates: Iterable[Path] | None = None,
    animation_sweep: bool = False,
    sweep_samples: int = 5,
    discoverer: Callable[[Path], tuple[list[Path], list[Path]]] | None = None,
    runner: Callable[[Path, int, int, int], dict[str, Any]] | None = None,
    sweep_runner: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Render-test Live2D candidates with per-model crash isolation."""
    if discoverer is None:
        from tools.test_live2d_resources import discover_candidates as discoverer
    if runner is None:
        from tools.test_live2d_resources import run_one as runner
    if sweep_runner is None and animation_sweep:
        from tools.test_live2d_resources import run_one_sweep as sweep_runner

    bundles: list[Path] = []
    if explicit_candidates is not None:
        candidates = _apply_limit(_dedupe_paths([Path(path) for path in explicit_candidates]), limit)
    else:
        candidates: list[Path] = []
        for root in roots:
            found, raw_bundles = discoverer(Path(root))
            candidates.extend(found)
            bundles.extend(raw_bundles)
        candidates = _apply_limit(_dedupe_paths(candidates), limit)
        bundles = _dedupe_paths(bundles)

    results: list[dict[str, Any]] = []
    for path in candidates:
        try:
            result = dict(runner(path, int(width), int(height), int(timeout)))
        except subprocess.TimeoutExpired as exc:
            result = {
                "source": str(path),
                "status": "timeout",
                "error": f"timed out after {timeout}s",
                "stdout_tail": str(exc.output or ""),
                "stderr_tail": str(exc.stderr or ""),
            }
        result.setdefault("source", str(path))
        result.setdefault("status", "unknown")
        if animation_sweep and sweep_runner is not None:
            try:
                result["animation_sweep"] = dict(
                    sweep_runner(
                        path,
                        int(width),
                        int(height),
                        int(timeout),
                        samples=int(sweep_samples or 5),
                    )
                )
            except Exception as exc:
                result["animation_sweep"] = {
                    "source": str(path),
                    "status": "fail",
                    "error": f"{type(exc).__name__}: {exc}",
                }
        results.append(result)

    counts = _status_counts(results)
    return {
        "kind": "live2d",
        "total": len(results),
        "bundle_count": len(bundles),
        "bundles": [str(path) for path in bundles],
        "counts": counts,
        "ok": all(status in PASS_STATUSES for status in counts),
        "results": results,
    }


def _render_summary(render: dict[str, dict[str, Any]]) -> dict[str, Any]:
    total = 0
    failed = 0
    by_kind: dict[str, dict[str, int]] = {}
    top_failures: list[dict[str, Any]] = []
    for kind, section in render.items():
        results = list(section.get("results") or [])
        counts = _status_counts(results)
        total += len(results)
        failed += sum(
            1 for result in results
            if not _render_result_ok(str(kind), result)
            and not result.get("quarantined")
        )
        by_kind[kind] = counts
        top_failures.extend(_failure_rows(kind, results))
    failure_categories: dict[str, int] = {}
    for kind, section in render.items():
        for result in section.get("results", []) or []:
            if _render_result_ok(str(kind), result) or result.get("quarantined"):
                continue
            category = str(_render_quality(str(kind), result).get("category") or "render_failed")
            failure_categories[category] = failure_categories.get(category, 0) + 1
    top_failures.sort(key=lambda row: (str(row.get("kind")), str(row.get("path"))))
    return {
        "ok": failed == 0,
        "total": total,
        "failed": failed,
        "by_kind": by_kind,
        "failure_categories": dict(sorted(failure_categories.items())),
        "top_failures": top_failures[:20],
        "quarantined": sum(
            1
            for section in render.values()
            for result in section.get("results", []) or []
            if isinstance(result, dict) and result.get("quarantined")
        ),
    }


def _known_path_matches(row_path: str, expected: str) -> bool:
    row_path = str(row_path or "").replace("\\", "/").lower()
    expected = str(expected or "").replace("\\", "/").lower()
    return bool(expected and (row_path == expected or row_path.endswith(expected)))


def _render_known_failure_matches(
    kind: str,
    result: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    path = _result_path(result)
    status = str(result.get("status") or "")
    for entry in entries:
        area = str(entry.get("area") or "render")
        if area not in {"render", "actor_render", ""}:
            continue
        entry_kind = str(entry.get("kind") or "")
        if entry_kind and entry_kind != kind:
            continue
        expected_path = str(entry.get("path") or entry.get("path_suffix") or "")
        if expected_path and not _known_path_matches(path, expected_path):
            continue
        statuses = {str(item) for item in entry.get("statuses") or entry.get("status") or []}
        if isinstance(entry.get("status"), str):
            statuses = {str(entry.get("status"))}
        if statuses and status not in statuses:
            continue
        categories = {str(item) for item in entry.get("failure_categories") or entry.get("categories") or []}
        if isinstance(entry.get("failure_category"), str):
            categories = {str(entry.get("failure_category"))}
        if categories:
            quality = _render_quality(kind, result)
            if str(quality.get("category") or "") not in categories:
                continue
        return entry
    return None


def _apply_render_known_failures(
    render: dict[str, dict[str, Any]],
    entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not entries:
        return render
    for kind, section in render.items():
        results = []
        for result in section.get("results", []) or []:
            result = dict(result)
            if not _render_result_ok(str(kind), result):
                match = _render_known_failure_matches(str(kind), result, entries)
                if match is not None:
                    result["quarantined"] = True
                    result["known_failure"] = {
                        "id": str(match.get("id") or ""),
                        "reason": str(match.get("reason") or ""),
                        "expires": str(match.get("expires") or ""),
                    }
            results.append(result)
        section["results"] = results
        section["counts"] = _status_counts(results)
        section["ok"] = all(
            _render_result_ok(str(kind), result) or result.get("quarantined")
            for result in results
        )
    return render


def _golden_name(kind: str, path: str) -> str:
    digest = hashlib.sha1(str(path).replace("\\", "/").encode("utf-8", errors="replace")).hexdigest()[:16]
    stem = Path(str(path)).stem.replace(" ", "_")[:40] or "actor"
    return f"{kind}_{stem}_{digest}.png"


def _render_spine_golden(path: Path, width: int, height: int, output: Path) -> dict[str, Any]:
    from app.spine_editor.actor_track import SpineActorClip
    from app.spine_editor.spine_json_parser import load_spine_file
    from tools.test_spine_resources import _find_atlas, _pick_animation

    skel = load_spine_file(str(path))
    anim = _pick_animation(skel)
    atlas = _find_atlas(path)
    clip = SpineActorClip(
        skel_path=str(path),
        atlas_path=str(atlas) if atlas else "",
        anim_name=anim,
        start_ms=0,
        duration_ms=3000,
    )
    img = clip.render_frame(width, height, 0)
    if img is None:
        return {"status": "render_none", "error": "no image"}
    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output)
    return {"status": "pass", "path": str(output)}


def _render_live2d_golden(path: Path, width: int, height: int, output: Path, timeout: int) -> dict[str, Any]:
    from tools.test_live2d_resources import run_one

    output.parent.mkdir(parents=True, exist_ok=True)
    result = run_one(path, width, height, timeout, image_out=output)
    if not output.exists():
        return {"status": str(result.get("status") or "unknown"), "error": str(result.get("error") or "")}
    return {"status": "pass", "path": str(output)}


def _image_diff_score(a: Path, b: Path) -> dict[str, Any]:
    from PIL import Image, ImageChops, ImageStat

    left = Image.open(a).convert("RGBA")
    right = Image.open(b).convert("RGBA")
    if left.size != right.size:
        return {"score": 999.0, "max": 255, "size_mismatch": [list(left.size), list(right.size)]}
    diff = ImageChops.difference(left, right)
    stat = ImageStat.Stat(diff)
    mean = max(float(value) for value in stat.mean)
    extrema = diff.getextrema()
    max_value = max(int(channel[1]) for channel in extrema)
    return {"score": round(mean, 4), "max": max_value}


def _default_golden_evaluator(
    *,
    kind: str,
    path: Path,
    width: int,
    height: int,
    live2d_timeout: int,
    golden_dir: Path,
    update: bool,
    threshold: float,
) -> dict[str, Any]:
    baseline = golden_dir / _golden_name(kind, str(path))
    actual = golden_dir / "_actual" / _golden_name(kind, str(path))
    if kind == "spine":
        rendered = _render_spine_golden(path, width, height, actual)
    else:
        rendered = _render_live2d_golden(path, width, height, actual, live2d_timeout)
    if rendered.get("status") != "pass":
        return {"status": "render_failed", "path": str(path), "error": rendered.get("error", "")}
    if update or not baseline.exists():
        existed = baseline.exists()
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_bytes(actual.read_bytes())
        return {"status": "updated" if existed else "created", "baseline": str(baseline)}
    diff = _image_diff_score(baseline, actual)
    status = "pass" if float(diff.get("score", 999.0)) <= float(threshold) else "mismatch"
    return {
        "status": status,
        "baseline": str(baseline),
        "actual": str(actual),
        "threshold": float(threshold),
        "diff": diff,
    }


def _evaluate_golden_images(
    render: dict[str, dict[str, Any]],
    *,
    golden_dir: Path | None,
    update: bool,
    threshold: float,
    width: int,
    height: int,
    live2d_width: int,
    live2d_height: int,
    live2d_timeout: int,
    evaluator: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if golden_dir is None:
        return {"enabled": False, "counts": {}}
    evaluator = evaluator or _default_golden_evaluator
    counts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for kind, section in render.items():
        for result in section.get("results", []) or []:
            if str(result.get("status") or "") not in PASS_STATUSES:
                continue
            path = Path(_result_path(result))
            if not path:
                continue
            row = evaluator(
                kind=str(kind),
                path=path,
                width=live2d_width if kind == "live2d" else width,
                height=live2d_height if kind == "live2d" else height,
                live2d_timeout=live2d_timeout,
                golden_dir=golden_dir,
                update=update,
                threshold=float(threshold),
            )
            row = dict(row)
            row.setdefault("kind", kind)
            row.setdefault("path", str(path))
            status = str(row.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
            result["golden"] = row
            rows.append(row)
    return {
        "enabled": True,
        "ok": not counts.get("mismatch") and not counts.get("render_failed"),
        "counts": dict(sorted(counts.items())),
        "rows": rows[:50],
    }


def _compat_risk_summary(compat: dict[str, Any]) -> dict[str, Any]:
    summary = compat.get("summary", {}) if isinstance(compat, dict) else {}
    rows = list(compat.get("rows") or []) if isinstance(compat, dict) else []
    risky = [
        row for row in rows
        if isinstance(row, dict) and int(row.get("risk_score", 0) or 0) > 0
    ]
    high = sum(1 for row in risky if str(row.get("risk_severity") or "") == "high")
    medium = sum(1 for row in risky if str(row.get("risk_severity") or "") == "medium")
    return {
        "risk_model_count": len(risky),
        "high_risk_models": high,
        "medium_risk_models": medium,
        "risk_counts": dict(summary.get("risk_counts", {}) or {}),
        "feature_counts": dict(summary.get("feature_counts", {}) or {}),
        "stress_tiers": dict(summary.get("stress_tiers", {}) or {}),
        "top_risks": list(summary.get("top_risks", []) or [])[:20],
    }


def _compat_rows_by_key(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in (report.get("compatibility", {}).get("rows") or report.get("rows") or []):
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "")
        path = row.get("path") or row.get("model_path") or row.get("source") or row.get("name")
        if not kind or not path:
            continue
        rows[_model_key(kind, path)] = row
    return rows


def _render_rows_by_key(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    render = report.get("render") or {}
    for kind, section in render.items():
        if not isinstance(section, dict):
            continue
        for result in section.get("results") or []:
            if not isinstance(result, dict):
                continue
            path = _result_path(result)
            if not path:
                continue
            rows[_model_key(str(kind), path)] = result
    return rows


def _row_path(row: dict[str, Any]) -> str:
    return str(row.get("path") or row.get("model_path") or row.get("source") or "")


def _compat_regression_row(
    key: str,
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    return {
        "area": "compatibility",
        "kind": str(current.get("kind") or baseline.get("kind") or key.split(":", 1)[0]),
        "path": _row_path(current) or _row_path(baseline),
        "before": {
            "ok": bool(baseline.get("ok")),
            "severity": str(baseline.get("severity") or ""),
            "issue_codes": list(baseline.get("issue_codes") or []),
        },
        "after": {
            "ok": bool(current.get("ok")),
            "severity": str(current.get("severity") or ""),
            "issue_codes": list(current.get("issue_codes") or []),
        },
        "recommendation": str(current.get("recommendation") or "Open the compatibility row and restore missing actor dependencies or parser support."),
    }


def _render_regression_row(
    key: str,
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    kind = key.split(":", 1)[0]
    quality = _render_quality(kind, current)
    return {
        "area": "render",
        "kind": kind,
        "path": _result_path(current) or _result_path(baseline),
        "before": {"status": str(baseline.get("status") or "unknown")},
        "after": {
            "status": str(current.get("status") or "unknown"),
            "quality_status": str(quality.get("status") or ""),
            "failure_category": str(quality.get("category") or ""),
        },
        "recommendation": _render_recommendation(kind, current),
    }


def compare_actor_render_qa_reports(
    current: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """Compare a current actor QA report with a previous baseline.

    The comparison intentionally focuses on product risk: models that were
    previously compatible/rendering and are now broken are regressions. Models
    that recover from a previous failure are improvements.
    """
    compat_current = _compat_rows_by_key(current)
    compat_baseline = _compat_rows_by_key(baseline)
    render_current = _render_rows_by_key(current)
    render_baseline = _render_rows_by_key(baseline)
    regressions: list[dict[str, Any]] = []
    improvements: list[dict[str, Any]] = []
    missing_from_current: list[dict[str, Any]] = []
    new_models: list[dict[str, Any]] = []

    for key, old in compat_baseline.items():
        new = compat_current.get(key)
        if new is None:
            missing_from_current.append({
                "area": "compatibility",
                "kind": str(old.get("kind") or key.split(":", 1)[0]),
                "path": _row_path(old),
            })
            continue
        old_ok = bool(old.get("ok"))
        new_ok = bool(new.get("ok"))
        if old_ok and not new_ok:
            regressions.append(_compat_regression_row(key, old, new))
        elif not old_ok and new_ok:
            improvements.append({
                "area": "compatibility",
                "kind": str(new.get("kind") or old.get("kind") or key.split(":", 1)[0]),
                "path": _row_path(new) or _row_path(old),
                "before": {"ok": old_ok},
                "after": {"ok": new_ok},
            })

    for key, new in compat_current.items():
        if key not in compat_baseline:
            new_models.append({
                "area": "compatibility",
                "kind": str(new.get("kind") or key.split(":", 1)[0]),
                "path": _row_path(new),
            })

    for key, old in render_baseline.items():
        new = render_current.get(key)
        if new is None:
            missing_from_current.append({
                "area": "render",
                "kind": key.split(":", 1)[0],
                "path": _result_path(old),
            })
            continue
        old_pass = _render_result_ok(key.split(":", 1)[0], old)
        new_pass = _render_result_ok(key.split(":", 1)[0], new)
        if old_pass and not new_pass:
            regressions.append(_render_regression_row(key, old, new))
        elif not old_pass and new_pass:
            improvements.append({
                "area": "render",
                "kind": key.split(":", 1)[0],
                "path": _result_path(new) or _result_path(old),
                "before": {"status": str(old.get("status") or "unknown")},
                "after": {"status": str(new.get("status") or "unknown")},
            })

    for key, new in render_current.items():
        if key not in render_baseline:
            new_models.append({
                "area": "render",
                "kind": key.split(":", 1)[0],
                "path": _result_path(new),
            })

    regressions.sort(key=lambda row: (str(row.get("area")), str(row.get("kind")), str(row.get("path"))))
    improvements.sort(key=lambda row: (str(row.get("area")), str(row.get("kind")), str(row.get("path"))))
    missing_from_current.sort(key=lambda row: (str(row.get("area")), str(row.get("kind")), str(row.get("path"))))
    new_models.sort(key=lambda row: (str(row.get("area")), str(row.get("kind")), str(row.get("path"))))
    return {
        "ok": not regressions,
        "summary": {
            "regressions": len(regressions),
            "improvements": len(improvements),
            "missing_from_current": len(missing_from_current),
            "new_models": len(new_models),
        },
        "regressions": regressions[:50],
        "improvements": improvements[:50],
        "missing_from_current": missing_from_current[:50],
        "new_models": new_models[:50],
    }


def build_actor_render_qa_report(
    roots: Iterable[Path | str],
    *,
    parse_spine: bool = False,
    limit: int = 0,
    render_limit: int | None = None,
    width: int = 720,
    height: int = 720,
    live2d_width: int = 320,
    live2d_height: int = 240,
    live2d_timeout: int = 30,
    render: bool = True,
    render_spine: bool = True,
    render_live2d: bool = True,
    render_top_risks: bool = False,
    top_risk_limit: int = 20,
    animation_sweep: bool = False,
    sweep_samples: int = 5,
    known_failures: list[dict[str, Any]] | None = None,
    golden_dir: Path | None = None,
    update_golden: bool = False,
    golden_threshold: float = 2.0,
    compat_builder: Callable[..., dict[str, Any]] = build_actor_compat_matrix,
    spine_candidate_finder: Callable[[Path], list[Path]] | None = None,
    spine_runner: Callable[[Path, int, int], dict[str, Any]] | None = None,
    spine_sweep_runner: Callable[..., dict[str, Any]] | None = None,
    live2d_discoverer: Callable[[Path], tuple[list[Path], list[Path]]] | None = None,
    live2d_runner: Callable[[Path, int, int, int], dict[str, Any]] | None = None,
    live2d_sweep_runner: Callable[..., dict[str, Any]] | None = None,
    golden_evaluator: Callable[..., dict[str, Any]] | None = None,
    baseline_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a combined actor QA report.

    Compatibility QA is fast and dependency-oriented. Render QA is slower and
    verifies the actual app render path, including Spine nonblank alpha output
    and Live2D child-process crash isolation.
    """
    root_paths = [Path(root) for root in roots] or [Path("resources")]
    try:
        compat = compat_builder(
            root_paths,
            parse_spine=parse_spine,
            limit=int(limit or 0),
            known_failures=list(known_failures or []),
        )
    except TypeError:
        compat = compat_builder(root_paths, parse_spine=parse_spine, limit=int(limit or 0))
    actual_render_limit = int(limit if render_limit is None else render_limit or 0)

    render_sections: dict[str, dict[str, Any]] = {}
    if render:
        explicit_spine = None
        explicit_live2d = None
        if render_top_risks:
            risk_limit = int(top_risk_limit or 0)
            explicit_spine = _top_risk_candidate_paths(compat, "spine", limit=risk_limit)
            explicit_live2d = _top_risk_candidate_paths(compat, "live2d", limit=risk_limit)
        if render_spine:
            render_sections["spine"] = _render_spine_roots(
                root_paths,
                limit=actual_render_limit,
                width=width,
                height=height,
                explicit_candidates=explicit_spine,
                animation_sweep=animation_sweep,
                sweep_samples=sweep_samples,
                candidate_finder=spine_candidate_finder,
                runner=spine_runner,
                sweep_runner=spine_sweep_runner,
            )
        if render_live2d:
            render_sections["live2d"] = _render_live2d_roots(
                root_paths,
                limit=actual_render_limit,
                width=live2d_width,
                height=live2d_height,
                timeout=live2d_timeout,
                explicit_candidates=explicit_live2d,
                animation_sweep=animation_sweep,
                sweep_samples=sweep_samples,
                discoverer=live2d_discoverer,
                runner=live2d_runner,
                sweep_runner=live2d_sweep_runner,
            )
    render_sections = _apply_render_known_failures(render_sections, list(known_failures or []))
    golden_summary = _evaluate_golden_images(
        render_sections,
        golden_dir=golden_dir,
        update=bool(update_golden),
        threshold=float(golden_threshold),
        width=width,
        height=height,
        live2d_width=live2d_width,
        live2d_height=live2d_height,
        live2d_timeout=live2d_timeout,
        evaluator=golden_evaluator,
    )
    render_sections = _annotate_render_quality(render_sections)
    render_summary = _render_summary(render_sections)
    ok = bool(compat.get("ok")) and bool(render_summary.get("ok"))
    if golden_summary.get("enabled"):
        ok = ok and bool(golden_summary.get("ok", False))
    report = {
        "ok": ok,
        "roots": [str(path) for path in root_paths],
        "limits": {
            "compat": int(limit or 0),
            "render": actual_render_limit,
            "render_top_risks": bool(render_top_risks),
            "top_risk_limit": int(top_risk_limit or 0),
        },
        "compatibility": compat,
        "render": render_sections,
        "golden": golden_summary,
        "summary": {
            "compatibility": compat.get("summary", {}),
            "render": render_summary,
            "compatibility_risk": _compat_risk_summary(compat),
            "golden": golden_summary,
        },
    }
    if baseline_report is not None:
        comparison = compare_actor_render_qa_reports(report, baseline_report)
        report["baseline_comparison"] = comparison
        report["ok"] = bool(report["ok"]) and bool(comparison.get("ok"))
    return report


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Run Live2D/Spine compatibility plus render/nonblank QA."
    )
    parser.add_argument("roots", nargs="*", type=Path, default=[Path("resources")])
    parser.add_argument("--parse-spine", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Compatibility candidate limit.")
    parser.add_argument(
        "--render-limit",
        type=int,
        default=-1,
        help="Render candidate limit. Defaults to --limit; 0 means no limit.",
    )
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--live2d-width", type=int, default=320)
    parser.add_argument("--live2d-height", type=int, default=240)
    parser.add_argument("--live2d-timeout", type=int, default=30)
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--no-spine-render", action="store_true")
    parser.add_argument("--no-live2d-render", action="store_true")
    parser.add_argument(
        "--render-top-risks",
        action="store_true",
        help="Render only passing compatibility rows with the highest actor risk scores.",
    )
    parser.add_argument("--top-risk-limit", type=int, default=20)
    parser.add_argument("--animation-sweep", action="store_true")
    parser.add_argument("--sweep-samples", type=int, default=5)
    parser.add_argument("--known-failures", type=Path, default=None)
    parser.add_argument("--golden-dir", type=Path, default=None)
    parser.add_argument("--update-golden", action="store_true")
    parser.add_argument("--golden-threshold", type=float, default=2.0)
    parser.add_argument("--summary-only", action="store_true")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Previous actor_render_qa JSON report to compare for regressions.",
    )
    parser.add_argument("--out", type=Path, default=Path("debugCapture/actor_render_qa.json"))
    args = parser.parse_args()

    render_limit = args.limit if args.render_limit < 0 else args.render_limit
    baseline_report = None
    if args.baseline is not None and args.baseline.exists():
        try:
            baseline_report = json.loads(args.baseline.read_text(encoding="utf-8"))
        except Exception as exc:
            baseline_report = {
                "compatibility": {"rows": []},
                "render": {},
                "baseline_load_error": str(exc),
            }
    known_failures = load_known_failures(args.known_failures)
    report = build_actor_render_qa_report(
        args.roots,
        parse_spine=args.parse_spine,
        limit=args.limit,
        render_limit=render_limit,
        width=args.width,
        height=args.height,
        live2d_width=args.live2d_width,
        live2d_height=args.live2d_height,
        live2d_timeout=args.live2d_timeout,
        render=not args.no_render,
        render_spine=not args.no_spine_render,
        render_live2d=not args.no_live2d_render,
        render_top_risks=args.render_top_risks,
        top_risk_limit=args.top_risk_limit,
        animation_sweep=args.animation_sweep,
        sweep_samples=args.sweep_samples,
        known_failures=known_failures,
        golden_dir=args.golden_dir,
        update_golden=args.update_golden,
        golden_threshold=args.golden_threshold,
        baseline_report=baseline_report,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    payload: dict[str, Any]
    if args.summary_only:
        payload = {
            "ok": report.get("ok"),
            "roots": report.get("roots"),
            "limits": report.get("limits"),
            "summary": report.get("summary"),
        }
    else:
        payload = report
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
