"""Run operational Live2D/Spine corpus regression QA from a manifest.

This wraps ``tools.actor_render_qa`` with product-level defaults: known-failure
quarantine, top-risk render sampling, animation sweep, golden-image regression,
baseline comparison, and a compact status artifact that UI/Health views can
read without loading the full report.
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

from tools.actor_compat_matrix import load_known_failures
from tools.actor_render_qa import build_actor_render_qa_report


DEFAULT_MANIFEST = {
    "version": 1,
    "roots": [
        "resources/spine_samples",
        "resources/live2d_samples",
        "resources/test_spine",
    ],
    "optional_roots": [],
    "known_failures": "qa_corpus/actor_known_failures.json",
    "golden_dir": "qa_corpus/actor_golden",
    "parse_spine": True,
    "render": True,
    "render_top_risks": True,
    "top_risk_limit": 20,
    "animation_sweep": True,
    "sweep_samples": 5,
    "coverage_targets": {
        "enforce": False,
        "min_total": 50,
        "min_spine": 10,
        "min_live2d": 5,
        "min_stress": 5,
        "required_risk_codes": [
            "spine_weighted_mesh",
            "spine_constraints",
            "live2d_many_motions",
        ],
    },
}


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def load_actor_corpus_manifest(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return dict(DEFAULT_MANIFEST)
    payload = _load_json(path) or {}
    manifest = dict(DEFAULT_MANIFEST)
    manifest.update(payload)
    if isinstance(payload.get("coverage_targets"), dict):
        targets = dict(DEFAULT_MANIFEST["coverage_targets"])
        targets.update(payload["coverage_targets"])
        manifest["coverage_targets"] = targets
    return manifest


def _resolve_path(value: Any) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else ROOT / path


def _kind_total(summary: dict[str, Any], kind: str) -> int:
    by_kind = summary.get("by_kind", {}) if isinstance(summary, dict) else {}
    row = by_kind.get(kind, {}) if isinstance(by_kind, dict) else {}
    return int(row.get("total", 0) or 0) if isinstance(row, dict) else 0


def _norm_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lower()


def _row_path(row: dict[str, Any]) -> str:
    return str(row.get("path") or row.get("source") or row.get("model_path") or "")


def _model_status_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_key: dict[str, dict[str, Any]] = {}
    compatibility = report.get("compatibility", {}) if isinstance(report, dict) else {}
    for row in compatibility.get("rows", []) or []:
        if not isinstance(row, dict):
            continue
        path = _row_path(row)
        kind = str(row.get("kind") or "")
        if not path or not kind:
            continue
        key = f"{kind}:{_norm_path(path)}"
        status = "pass"
        if row.get("quarantined"):
            status = "quarantined"
        elif not row.get("ok", False):
            status = "fail"
        elif int(row.get("risk_score", 0) or 0) > 0:
            status = "risk"
        rows_by_key[key] = {
            "kind": kind,
            "path": path,
            "status": status,
            "compatibility_ok": bool(row.get("ok", False)),
            "quarantined": bool(row.get("quarantined", False)),
            "risk_score": int(row.get("risk_score", 0) or 0),
            "stress_tier": str(row.get("stress_tier") or "standard"),
            "issue_codes": list(row.get("issue_codes") or []),
            "risk_codes": list(row.get("risk_codes") or []),
            "known_failure": row.get("known_failure"),
        }
    for kind, section in (report.get("render", {}) or {}).items():
        if not isinstance(section, dict):
            continue
        for result in section.get("results", []) or []:
            if not isinstance(result, dict):
                continue
            path = _row_path(result)
            if not path:
                continue
            key = f"{kind}:{_norm_path(path)}"
            row = rows_by_key.setdefault(key, {
                "kind": str(kind),
                "path": path,
                "status": "pass",
                "compatibility_ok": True,
                "quarantined": False,
                "risk_score": 0,
                "stress_tier": "standard",
                "issue_codes": [],
                "risk_codes": [],
            })
            quality = result.get("quality") if isinstance(result.get("quality"), dict) else {}
            row["render_status"] = str(result.get("status") or "unknown")
            row["failure_category"] = str(
                result.get("failure_category") or quality.get("category") or ""
            )
            row["golden_status"] = str((result.get("golden") or {}).get("status") or "")
            if result.get("quarantined"):
                row["status"] = "quarantined"
                row["quarantined"] = True
                row["known_failure"] = result.get("known_failure")
            elif quality and not quality.get("ok", True):
                row["status"] = "fail"
            elif row.get("status") == "pass" and row.get("risk_score", 0):
                row["status"] = "risk"
    return sorted(rows_by_key.values(), key=lambda row: (str(row.get("kind")), str(row.get("path"))))


def actor_corpus_status(
    report: dict[str, Any],
    *,
    coverage_targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    targets = coverage_targets or {}
    compatibility = report.get("summary", {}).get("compatibility", {}) or {}
    render = report.get("summary", {}).get("render", {}) or {}
    golden = report.get("summary", {}).get("golden", {}) or {}
    risk = report.get("summary", {}).get("compatibility_risk", {}) or {}
    issues: list[dict[str, Any]] = []

    def add_issue(code: str, message: str, *, severity: str = "medium", **extra: Any) -> None:
        row = {"code": code, "severity": severity, "message": message}
        row.update(extra)
        issues.append(row)

    total = int(compatibility.get("total", 0) or 0)
    spine_total = _kind_total(compatibility, "spine")
    live2d_total = _kind_total(compatibility, "live2d")
    stress_tiers = compatibility.get("stress_tiers", {}) if isinstance(compatibility, dict) else {}
    stress_total = int((stress_tiers or {}).get("stress", 0) or 0)
    risk_counts = compatibility.get("risk_counts", {}) if isinstance(compatibility, dict) else {}
    model_rows = _model_status_rows(report)
    status_counts: dict[str, int] = {}
    for row in model_rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    for key, actual, label in (
        ("min_total", total, "total actor models"),
        ("min_spine", spine_total, "Spine models"),
        ("min_live2d", live2d_total, "Live2D models"),
        ("min_stress", stress_total, "stress-tier models"),
    ):
        expected = int(targets.get(key, 0) or 0)
        if expected and actual < expected:
            add_issue(
                key,
                f"Corpus has {actual} {label}; target is {expected}.",
                severity="low",
                actual=actual,
                expected=expected,
            )
    for code in targets.get("required_risk_codes", []) or []:
        if int((risk_counts or {}).get(str(code), 0) or 0) <= 0:
            add_issue(
                "missing_risk_code",
                f"Corpus has no model covering risk code {code}.",
                severity="low",
                risk_code=str(code),
            )

    if int(compatibility.get("failed", 0) or 0) > 0:
        add_issue(
            "compatibility_failures",
            "Compatibility matrix has hard failures.",
            severity="high",
            failed=int(compatibility.get("failed", 0) or 0),
        )
    if int(render.get("failed", 0) or 0) > 0:
        add_issue(
            "render_failures",
            "Actor render QA has hard failures.",
            severity="high",
            failed=int(render.get("failed", 0) or 0),
        )
    if golden.get("enabled") and not golden.get("ok", True):
        add_issue(
            "golden_regression",
            "Golden-image regression check failed.",
            severity="high",
            counts=golden.get("counts", {}),
        )

    enforce = bool(targets.get("enforce", False))
    blocking = [issue for issue in issues if issue.get("severity") == "high" or enforce]
    return {
        "ok": bool(report.get("ok", False)) and not blocking,
        "enforce_coverage": enforce,
        "coverage": {
            "total": total,
            "spine": spine_total,
            "live2d": live2d_total,
            "stress": stress_total,
            "risk_model_count": int(risk.get("risk_model_count", 0) or 0),
            "quarantined": int(compatibility.get("quarantined", 0) or 0)
            + int(render.get("quarantined", 0) or 0),
            "golden": golden.get("counts", {}),
            "render_failure_categories": render.get("failure_categories", {}),
            "model_status_counts": dict(sorted(status_counts.items())),
        },
        "models": model_rows[:1000],
        "issues": issues,
        "top_actions": [
            "Add more real Live2D/Spine models for missing risk-code coverage."
            if issue.get("code") == "missing_risk_code"
            else "Inspect actor render QA top_failures and fix or quarantine expected failures."
            if issue.get("severity") == "high"
            else str(issue.get("message") or "")
            for issue in issues[:8]
        ],
    }


def build_actor_corpus_regression(
    manifest: dict[str, Any],
    *,
    render_override: bool | None = None,
    update_golden: bool | None = None,
    baseline_override: Path | None = None,
) -> dict[str, Any]:
    roots = [_resolve_path(root) for root in manifest.get("roots", [])]
    for root in manifest.get("optional_roots", []) or []:
        resolved = _resolve_path(root)
        if resolved is not None and resolved.exists():
            roots.append(resolved)
    roots = [root for root in roots if root is not None]
    known_failure_path = _resolve_path(manifest.get("known_failures"))
    golden_dir = _resolve_path(manifest.get("golden_dir"))
    baseline_path = baseline_override or _resolve_path(manifest.get("baseline"))
    baseline_report = _load_json(baseline_path)
    known_failures = load_known_failures(known_failure_path)
    render = bool(manifest.get("render", True)) if render_override is None else bool(render_override)
    report = build_actor_render_qa_report(
        roots,
        parse_spine=bool(manifest.get("parse_spine", False)),
        limit=int(manifest.get("limit", 0) or 0),
        render_limit=int(manifest.get("render_limit", manifest.get("limit", 0)) or 0),
        width=int(manifest.get("width", 720) or 720),
        height=int(manifest.get("height", 720) or 720),
        live2d_width=int(manifest.get("live2d_width", 320) or 320),
        live2d_height=int(manifest.get("live2d_height", 240) or 240),
        live2d_timeout=int(manifest.get("live2d_timeout", 30) or 30),
        render=render,
        render_spine=bool(manifest.get("render_spine", True)),
        render_live2d=bool(manifest.get("render_live2d", True)),
        render_top_risks=bool(manifest.get("render_top_risks", True)),
        top_risk_limit=int(manifest.get("top_risk_limit", 20) or 20),
        animation_sweep=bool(manifest.get("animation_sweep", True)),
        sweep_samples=int(manifest.get("sweep_samples", 5) or 5),
        known_failures=known_failures,
        golden_dir=golden_dir if render and manifest.get("golden_dir") else None,
        update_golden=bool(manifest.get("update_golden", False) if update_golden is None else update_golden),
        golden_threshold=float(manifest.get("golden_threshold", 2.0) or 2.0),
        baseline_report=baseline_report,
    )
    status = actor_corpus_status(
        report,
        coverage_targets=manifest.get("coverage_targets", {}),
    )
    try:
        from tools.actor_golden_manager import actor_golden_status

        if golden_dir is not None:
            status["golden_baselines"] = actor_golden_status(golden_dir)
    except Exception:
        pass
    report["actor_corpus_status"] = status
    report["ok"] = bool(report.get("ok", False) and status.get("ok", False))
    return report


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run manifest-driven actor corpus regression QA.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/actor_corpus_manifest.json"))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/actor_corpus_regression.json"))
    parser.add_argument("--status-out", type=Path, default=Path("debugCapture/actor_corpus_status.json"))
    parser.add_argument("--baseline", type=Path, default=None)
    parser.add_argument("--render", dest="render", action="store_true", default=None)
    parser.add_argument("--no-render", dest="render", action="store_false")
    parser.add_argument("--update-golden", action="store_true")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    manifest = load_actor_corpus_manifest(args.manifest)
    report = build_actor_corpus_regression(
        manifest,
        render_override=args.render,
        update_golden=args.update_golden or None,
        baseline_override=args.baseline,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.status_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.status_out.write_text(
        json.dumps(report.get("actor_corpus_status", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    payload = report.get("actor_corpus_status", {}) if args.summary_only else report
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    print(f"status: {args.status_out}")
    return 0 if report.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
