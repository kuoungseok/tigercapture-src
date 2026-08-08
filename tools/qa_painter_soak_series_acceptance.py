"""Build the claim-scoped envelope from three raw two-hour Painter reports."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "debugCapture" / "painter" / "soak" / "three_run_envelope" / "report.json")
    args = parser.parse_args()
    from app.painter_soak_series import evaluate_three_run_envelope

    rows = [(path.resolve(), json.loads(path.read_text(encoding="utf-8"))) for path in args.raw_reports]
    report = evaluate_three_run_envelope(rows)
    output = args.output.resolve(); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(output), "passed": report["passed"], "failures": report["failures"]}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
