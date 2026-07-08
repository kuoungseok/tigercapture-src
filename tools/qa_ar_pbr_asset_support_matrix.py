"""Build an AR/PBR asset support matrix over local sample assets."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ar_pbr.sample_assets import ar_pbr_support_matrix_samples

DEFAULT_CANDIDATES: tuple[dict[str, Any], ...] = ar_pbr_support_matrix_samples()


def run_asset_support_matrix(
    *,
    root: Path = ROOT,
    candidates: Iterable[Mapping[str, Any]] = DEFAULT_CANDIDATES,
    max_triangles_per_geometry: int = 2_000_000,
) -> dict[str, Any]:
    from app.ar_pbr.asset_support import classify_asset_support, summarize_asset_support
    from app.ar_pbr.importer import import_asset

    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    counts: dict[str, int] = {}
    for candidate in candidates:
        candidate_id = str(candidate.get("id") or candidate.get("path") or "asset")
        rel_path = Path(str(candidate.get("path") or ""))
        path = rel_path if rel_path.is_absolute() else root / rel_path
        expected_levels = {str(item) for item in candidate.get("expected_levels") or []}
        expected_features = {str(item) for item in candidate.get("expected_features") or []}
        expected_issues = {str(item) for item in candidate.get("expected_issues") or []}
        required = bool(candidate.get("required"))

        if not path.exists():
            row = {
                "id": candidate_id,
                "path": str(path),
                "exists": False,
                "pass": not required,
                "support_level": "missing",
                "summary": "sample asset is missing",
                "expected_levels": sorted(expected_levels),
            }
            rows.append(row)
            counts["missing"] = counts.get("missing", 0) + 1
            if required:
                blockers.append(f"{candidate_id}: sample asset missing")
            continue

        descriptor, diagnostics = import_asset(
            path,
            settings={
                "disable_descriptor_cache": True,
                "max_triangles_per_geometry": max_triangles_per_geometry,
                "placeholder_on_error": False,
            },
        )
        report = descriptor.get("support") if isinstance(descriptor.get("support"), Mapping) else None
        if not report:
            report = classify_asset_support(descriptor, diagnostics)
        level = str(report.get("support_level") or "unknown")
        features = {str(item) for item in report.get("feature_flags") or []}
        issues = {str(item) for item in report.get("issue_codes") or []}
        level_ok = not expected_levels or level in expected_levels
        feature_ok = expected_features.issubset(features)
        issue_ok = expected_issues.issubset(issues)
        row_pass = bool(level_ok and feature_ok and issue_ok)
        row = {
            "id": candidate_id,
            "path": str(path),
            "exists": True,
            "pass": row_pass,
            "support_level": level,
            "confidence": report.get("confidence"),
            "asset_kind": report.get("asset_kind"),
            "render_path": report.get("render_path"),
            "ok_for_preview": bool(report.get("ok_for_preview")),
            "ok_for_export": bool(report.get("ok_for_export")),
            "expected_levels": sorted(expected_levels),
            "missing_expected_features": sorted(expected_features - features),
            "missing_expected_issues": sorted(expected_issues - issues),
            "feature_flags": sorted(features),
            "issue_codes": sorted(issues),
            "metrics": report.get("metrics") or {},
            "import_backend": diagnostics.get("backend"),
            "imported": bool(diagnostics.get("imported")),
            "fallback": bool(diagnostics.get("fallback")),
            "summary": summarize_asset_support(report),
        }
        rows.append(row)
        counts[level] = counts.get(level, 0) + 1
        if required and not row_pass:
            blockers.append(f"{candidate_id}: expected {sorted(expected_levels)} got {level}")

    failed_existing = [row["id"] for row in rows if row.get("exists") and not row.get("pass")]
    status = "pass" if not blockers and not failed_existing else "review"
    return {
        "status": status,
        "summary": {
            "asset_count": len(rows),
            "existing_asset_count": sum(1 for row in rows if row.get("exists")),
            "pass_count": sum(1 for row in rows if row.get("pass")),
            "review_count": sum(1 for row in rows if row.get("exists") and not row.get("pass")),
            "counts_by_support_level": counts,
        },
        "blockers": blockers,
        "review_assets": failed_existing,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="debugCapture/ar_pbr_asset_support_matrix_qa.json")
    parser.add_argument("--max-triangles-per-geometry", type=int, default=2_000_000)
    args = parser.parse_args(argv)

    report = run_asset_support_matrix(max_triangles_per_geometry=args.max_triangles_per_geometry)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "summary": report["summary"],
        "blockers": report["blockers"],
        "out": str(out),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"pass", "review"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
