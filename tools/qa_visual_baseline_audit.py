"""Audit UI visual-regression baseline coverage."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_SIZES = {(1366, 768), (1920, 1080), (2560, 1080)}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _metric_sizes(payload: dict[str, Any]) -> set[tuple[int, int]]:
    sizes: set[tuple[int, int]] = set()
    for row in payload.get("metrics", []) or []:
        if not isinstance(row, dict):
            continue
        raw = row.get("size")
        if isinstance(raw, (list, tuple)) and len(raw) >= 2:
            try:
                sizes.add((int(raw[0]), int(raw[1])))
            except Exception:
                pass
    return sizes


def run_visual_baseline_audit(
    *,
    baseline_path: Path = ROOT / "debugCapture" / "visual_baseline" / "baseline.json",
    regression_report_path: Path = ROOT / "debugCapture" / "visual_regression" / "visual_regression_report.json",
    gui_flow_report_path: Path = ROOT / "debugCapture" / "screenstudio_gui_flow" / "screenstudio_gui_flow_report.json",
    export_handoff_report_path: Path = ROOT / "debugCapture" / "screenstudio_export_handoff_qa.json",
) -> dict[str, Any]:
    baseline = _load_json(baseline_path)
    report = _load_json(regression_report_path)
    gui_flow = _load_json(gui_flow_report_path)
    export_handoff = _load_json(export_handoff_report_path)
    approved_dir = baseline_path.parent / "approved"
    approved_manifest = approved_dir / "baseline_manifest.json"
    screenshots = baseline.get("screenshots", {}) if isinstance(baseline, dict) else {}
    approved = list(approved_dir.glob("*.png")) if approved_dir.exists() else []
    sizes = _metric_sizes(baseline)
    missing_sizes = sorted(DEFAULT_SIZES - sizes)
    checks = {
        "baseline_exists": baseline_path.exists(),
        "has_three_screenshots": len(screenshots) >= 3,
        "approved_images_exist": len(approved) >= 3,
        "approved_manifest_exists": approved_manifest.exists(),
        "default_sizes_covered": not missing_sizes,
        "latest_regression_report_exists": regression_report_path.exists(),
        "latest_regression_ok": bool(report.get("ok", True)) if report else regression_report_path.exists(),
        "screenstudio_gui_flow_report_exists": gui_flow_report_path.exists(),
        "screenstudio_gui_flow_ok": bool(gui_flow.get("ok")) if gui_flow else False,
        "screenstudio_export_handoff_report_exists": export_handoff_report_path.exists(),
        "screenstudio_export_handoff_ok": bool(export_handoff.get("ok")) if export_handoff else False,
        "screenstudio_default_export_ready": (
            int((export_handoff.get("summary") or {}).get("default_result_ready", 0) or 0) >= 1
            if export_handoff else False
        ),
        "screenstudio_default_beauty_ready": (
            int((export_handoff.get("summary") or {}).get("default_beauty_ready", 0) or 0) >= 1
            and int((export_handoff.get("summary") or {}).get("default_beauty_score", 0) or 0) >= 85
            if export_handoff else False
        ),
        "screenstudio_default_golden_video_ready": (
            int((export_handoff.get("summary") or {}).get("default_golden_video_ready", 0) or 0) >= 1
            if export_handoff else False
        ),
    }
    failures = [name for name, ok in checks.items() if not ok]
    return {
        "ok": not failures,
        "summary": {
            "screenshots": len(screenshots),
            "approved_images": len(approved),
            "sizes": sorted([list(size) for size in sizes]),
            "missing_sizes": [list(size) for size in missing_sizes],
            "regression_report": str(regression_report_path),
            "baseline": str(baseline_path),
            "approved_manifest": str(approved_manifest),
            "screenstudio_gui_flow": str(gui_flow_report_path),
            "screenstudio_export_handoff": str(export_handoff_report_path),
        },
        "checks": checks,
        "failures": failures,
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Audit visual baseline coverage.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/visual_baseline_audit.json"))
    parser.add_argument("--baseline", type=Path, default=ROOT / "debugCapture" / "visual_baseline" / "baseline.json")
    parser.add_argument("--regression-report", type=Path, default=ROOT / "debugCapture" / "visual_regression" / "visual_regression_report.json")
    args = parser.parse_args()
    report = run_visual_baseline_audit(
        baseline_path=args.baseline,
        regression_report_path=args.regression_report,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
