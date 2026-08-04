from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.performance_gate import run_motion_performance_gate
from app.motion_designer.templates import instantiate_template


DEFAULT_OUTPUT = ROOT / "debugCapture" / "motion_designer" / "pg5_release_gate"
RATIO_CASES = (
    ("16_9", "16:9", 320, 180),
    ("9_16", "9:16", 180, 320),
    ("1_1", "1:1", 240, 240),
)


def _read_report(path: Path) -> dict:
    if not path.is_file():
        return {"ok": False, "reason": "missing", "path": str(path.resolve())}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "reason": str(exc), "path": str(path.resolve())}
    return value if isinstance(value, dict) else {"ok": False, "reason": "invalid_report"}


def run(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    QApplication.instance() or QApplication([])
    cases: list[dict] = []
    for name, variant, width, height in RATIO_CASES:
        composition = instantiate_template("product_callout", variant=variant)
        renderer = MotionExportRenderer(cache_capacity=4, cache_max_bytes=32 * 1024 * 1024)
        frame_path = output_dir / f"product_callout_{name}.png"
        renderer.save_png(composition, composition.duration_ms * 0.5, frame_path)
        gate = run_motion_performance_gate(
            composition,
            sample_times_ms=(0.0, composition.duration_ms * 0.5, composition.duration_ms - 1),
            iterations=3,
            width=width,
            height=height,
            cache_max_bytes=32 * 1024 * 1024,
            template_ids=("product_callout", "clean_lower_third", "logo_reveal"),
            template_switch_iterations=12,
        )
        cases.append({
            "name": name,
            "variant": variant,
            "width": width,
            "height": height,
            "frame_path": str(frame_path.resolve()),
            "frame_nonempty": frame_path.is_file() and frame_path.stat().st_size > 0,
            "gate": gate,
            "ok": gate["ok"] and frame_path.is_file() and frame_path.stat().st_size > 0,
        })
    long_run_path = ROOT / "debugCapture" / "motion_designer" / "long_run_30m" / "report.json"
    release_path = ROOT / "debugCapture" / "motion_designer" / "release_acceptance" / "report.json"
    long_run = _read_report(long_run_path)
    release = _read_report(release_path)
    evidence = release.get("evidence") if isinstance(release.get("evidence"), dict) else {}
    preview_export = evidence.get("gpu_preview_export_parity", {})
    installer = evidence.get("installer_smoke", {})
    checks = {
        "representative_ratios": all(case["ok"] for case in cases),
        "continuous_opengl_30m": bool(long_run.get("ok")),
        "gpu_preview_export_parity": str(preview_export.get("status") or "").lower() == "pass",
        "packaged_installer_smoke": str(installer.get("status") or "").lower() == "pass",
    }
    report = {
        "schema": "tigerstudio.motion.pg5_release_gate.v1",
        "ok": all(checks.values()),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "cases": cases,
        "continuous_run": {
            "report_path": str(long_run_path.resolve()),
            "elapsed_seconds": long_run.get("elapsed_seconds"),
            "average_frame_swaps_per_second": long_run.get("average_frame_swaps_per_second"),
            "memory_growth_bytes": long_run.get("memory_growth_bytes"),
            "software_renderer_used": long_run.get("software_renderer_used"),
        },
        "release_acceptance_report": str(release_path.resolve()),
        "evidence": {
            "gpu_preview_export_parity": preview_export,
            "installer_smoke": installer,
        },
    }
    (output_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Motion Designer PG5 product performance gate")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.output.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
