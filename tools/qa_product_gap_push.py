from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "product_gap_push_qa.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ordered 3,4,5,1,2,6 product-gap push gate.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero unless every area is claim-ready.")
    args = parser.parse_args()

    from app.product_gap_push import build_product_gap_push_report

    report = build_product_gap_push_report(ROOT)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "ok": bool(report.get("ok")),
        "implementation_ready": bool(report.get("implementation_ready")),
        "claim_ready": bool(report.get("claim_ready")),
        "score": report.get("score", 0),
        "report": str(out),
    }, ensure_ascii=False))
    if args.strict and not bool(report.get("claim_ready")):
        return 2
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
