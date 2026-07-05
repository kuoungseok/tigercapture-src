from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build release evidence automation readiness report.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out", type=Path, default=Path("debugCapture/release_evidence_automation_qa.json"))
    parser.add_argument("--work-dir", type=Path, default=Path("debugCapture/release_evidence_automation"))
    parser.add_argument("--write-files", action="store_true")
    args = parser.parse_args()

    from app.release_evidence_automation import build_release_evidence_automation_report

    root = Path(args.root).resolve()
    report = build_release_evidence_automation_report(
        root,
        out_dir=args.work_dir,
        write_files=bool(args.write_files),
    )
    out = args.out if args.out.is_absolute() else root / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
