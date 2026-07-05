"""Build AI voice replacement QA evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_REPORT = ROOT / "debugCapture" / "ai_voice_replacement_qa.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build AI voice replacement QA evidence.")
    parser.add_argument("--out", default=str(DEFAULT_REPORT), help="Output JSON report path.")
    args = parser.parse_args()

    from app.ai_voice_replacement import ai_voice_replacement_readiness_report

    report = ai_voice_replacement_readiness_report()
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": bool(report.get("ok")),
                "ai_voice_replacement_contract_ready": bool(report.get("ai_voice_replacement_contract_ready")),
                "report": str(out),
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
