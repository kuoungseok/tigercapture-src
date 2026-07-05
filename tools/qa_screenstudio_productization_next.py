from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_screenstudio_productization_next_qa(*, out: str | Path | None = None) -> dict:
    from app.screenstudio_parity import screenstudio_productization_next_report

    report = screenstudio_productization_next_report()
    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate the next Screen Studio productization workbench.")
    parser.add_argument("--out", default="debugCapture/screenstudio_productization_next_qa.json")
    args = parser.parse_args()
    report = run_screenstudio_productization_next_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {Path(args.out).resolve()}")
    return 0 if report.get("implementation_ok", report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
