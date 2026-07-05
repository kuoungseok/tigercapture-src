"""Build the Descript-lite readiness QA report."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "descript_lite_readiness_qa.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Descript-lite readiness report.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero until Descript-lite claim is ready.")
    args = parser.parse_args()

    from app.descript_lite_readiness import build_descript_lite_readiness_report

    report = build_descript_lite_readiness_report(ROOT)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "descript_lite_claim_ready": bool(report.get("descript_lite_claim_ready")),
                "price_149_plus_defense_ready": bool(report.get("price_149_plus_defense_ready")),
                "score": report.get("score", 0),
                "report": str(out),
            },
            ensure_ascii=False,
        )
    )
    if args.strict and not bool(report.get("descript_lite_claim_ready")):
        return 2
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
