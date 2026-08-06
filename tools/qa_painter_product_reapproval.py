"""Aggregate current Painter R8 evidence and write an honest release gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _latest_crash_report() -> Path:
    rows = sorted((ROOT / "debugCapture" / "painter" / "crash_recovery").glob("*/report.json"))
    if not rows:
        raise FileNotFoundError("No native crash-recovery report found")
    return rows[-1]


def _latest_disk_full_report() -> Path:
    rows = sorted((ROOT / "debugCapture" / "painter" / "disk_full").glob("*/report.json"))
    if not rows:
        raise FileNotFoundError("No native disk-full report found")
    return rows[-1]


def _soak_evidence_report(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit.resolve()
    accepted = ROOT / "debugCapture" / "painter" / "soak" / "long_session_acceptance" / "report.json"
    if accepted.is_file():
        return accepted
    return ROOT / "debugCapture" / "painter" / "soak" / "calibration-baseline-20260804.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--soak", type=Path)
    parser.add_argument("--soak-series", type=Path)
    parser.add_argument("--independent-numeric-agent", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    from app.painter_product_reapproval import aggregate_product_reapproval

    base = ROOT / "debugCapture" / "painter"
    paths = {
        "audit": base / "evidence_audit" / "report.json",
        "m8": base / "painting_m8" / "report.json",
        "native": base / "native_environment" / "report.json",
        "crash": _latest_crash_report(),
        "disk_full": _latest_disk_full_report(),
        "soak": _soak_evidence_report(args.soak),
        "external": base / "external_interop" / "report.json",
        "large_4k": base / "large_canvas_runtime" / "4k_report.json",
        "large_8k": base / "large_canvas_runtime" / "8k_report.json",
        "independent_agent": base / "independent_r6_r7_qa" / "report.json",
        "independent_threshold_agent": base / "independent_threshold_qa" / "report.json",
        "independent_numeric_agent": (
            args.independent_numeric_agent.resolve()
            if args.independent_numeric_agent is not None
            else base / "independent_numeric_resource_qa_20260804" / "report.json"
        ),
    }
    soak_series = (
        args.soak_series.resolve()
        if args.soak_series is not None
        else base / "soak" / "three_run_envelope" / "report.json"
    )
    if soak_series.is_file():
        paths["soak_series"] = soak_series
    report = aggregate_product_reapproval(paths)
    output = (
        args.output.resolve()
        if args.output is not None
        else base / "product_reapproval" / "report.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(output.resolve()),
        "aggregation_valid": report["aggregation_valid"],
        "release_ready": report["release_ready"],
        "blockers": report["blockers"],
        "errors": report["errors"],
    }, ensure_ascii=False))
    return 0 if report["aggregation_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
