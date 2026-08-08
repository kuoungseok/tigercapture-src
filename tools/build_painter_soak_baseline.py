from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate repeated native Painter soak measurements")
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    from app.painter_soak_baseline import build_soak_baseline

    reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.reports]
    baseline = build_soak_baseline(reports)
    output = args.output or (ROOT / "debugCapture" / "painter" / "soak" / "baseline.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "baseline": str(output.resolve()),
        "run_count": baseline["run_count"],
        "classification": baseline["classification"],
        "release_claim_passed": baseline["release_claim_passed"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
