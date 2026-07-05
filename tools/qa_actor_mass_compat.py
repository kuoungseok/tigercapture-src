"""Product smoke QA for large Live2D/Spine compatibility coverage."""
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


def run_actor_mass_compat_qa(
    *,
    status_path: Path = ROOT / "debugCapture" / "actor_corpus_status.json",
    manifest_path: Path = ROOT / "qa_corpus" / "actor_corpus_manifest.json",
) -> dict[str, Any]:
    status = _load_json(status_path)
    manifest = _load_json(manifest_path)
    targets = manifest.get("coverage_targets", {}) if isinstance(manifest, dict) else {}
    coverage = status.get("coverage", {}) if isinstance(status, dict) else {}
    golden = status.get("golden_baselines", {}) if isinstance(status, dict) else {}
    total = int(coverage.get("total", 0) or 0)
    spine = int(coverage.get("spine", 0) or 0)
    live2d = int(coverage.get("live2d", 0) or 0)
    stress = int(coverage.get("stress", 0) or 0)
    quarantined = int(coverage.get("quarantined", 0) or 0)
    golden_count = int(golden.get("baseline_count", 0) or (coverage.get("golden", {}) or {}).get("pass", 0) or 0)
    issues = list(status.get("issues", []) or [])
    high_issues = [row for row in issues if isinstance(row, dict) and row.get("severity") == "high"]
    checks = {
        "status_report_exists": status_path.exists(),
        "manifest_exists": manifest_path.exists(),
        "total_target_met": total >= int(targets.get("min_total", 50) or 50),
        "spine_target_met": spine >= int(targets.get("min_spine", 10) or 10),
        "live2d_target_met": live2d >= int(targets.get("min_live2d", 5) or 5),
        "stress_target_met": stress >= int(targets.get("min_stress", 5) or 5),
        "golden_baselines_seeded": golden_count >= 20,
        "no_high_issues": not high_issues,
        "known_failure_quarantine_present": quarantined >= 1,
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "summary": {
            "total": total,
            "spine": spine,
            "live2d": live2d,
            "stress": stress,
            "quarantined": quarantined,
            "golden_baselines": golden_count,
            "high_issues": len(high_issues),
        },
        "checks": checks,
        "failures": failures,
        "status_path": str(status_path),
        "manifest_path": str(manifest_path),
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Run actor mass compatibility smoke QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/actor_mass_compat_qa.json"))
    parser.add_argument("--status", type=Path, default=ROOT / "debugCapture" / "actor_corpus_status.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "qa_corpus" / "actor_corpus_manifest.json")
    args = parser.parse_args()
    report = run_actor_mass_compat_qa(status_path=args.status, manifest_path=args.manifest)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
