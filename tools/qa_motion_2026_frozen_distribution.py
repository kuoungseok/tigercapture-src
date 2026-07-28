from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.trend_distribution_qa import evaluate_frozen_distribution


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a real frozen Tiger Studio Motion runtime report while "
            "keeping bundle stability separate from realtime readiness."
        )
    )
    parser.add_argument(
        "--studio-exe",
        type=Path,
        default=ROOT / "dist" / "TigerCapture" / "TigerStudio.exe",
    )
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "debugCapture"
            / "motion_2026_frozen_distribution"
            / "report.json"
        ),
    )
    parser.add_argument("--minimum-runtime-seconds", type=float, default=60.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runtime_report_path = args.runtime_report.expanduser().resolve(strict=False)
    runtime_report = json.loads(runtime_report_path.read_text(encoding="utf-8"))
    result = evaluate_frozen_distribution(
        studio_exe=args.studio_exe,
        runtime_report_path=runtime_report_path,
        runtime_report=runtime_report,
        minimum_runtime_seconds=args.minimum_runtime_seconds,
    )
    output = args.output.expanduser().resolve(strict=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))
    # A stable frozen bundle is useful evidence even while M22 blocks realtime.
    return 0 if result["frozen_bundle_smoke_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
