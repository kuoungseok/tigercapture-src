from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from app.review_automation.dev_gate import require_review_automation_dev
from app.review_automation.paths import DEFAULT_REVIEW_QA_REPORT, DEFAULT_REVIEW_REPORT


def main() -> int:
    try:
        require_review_automation_dev(ROOT)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    from app.review_automation.qa import validate_review_automation_report

    parser = argparse.ArgumentParser(description="Validate TigerCapture review automation outputs.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REVIEW_REPORT)
    parser.add_argument("--out", type=Path, default=DEFAULT_REVIEW_QA_REPORT)
    args = parser.parse_args()

    result = validate_review_automation_report(args.report, project_root=ROOT)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
