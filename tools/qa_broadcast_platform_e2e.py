"""Build broadcast platform E2E evidence artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def run_broadcast_platform_e2e_qa(
    *,
    out: str | Path = "debugCapture/broadcast_platform_e2e_qa.json",
    skip_record_smoke: bool = False,
) -> dict:
    from app.broadcast_platform_e2e import build_broadcast_platform_e2e_report, preserve_registered_platform_evidence

    out_path = ROOT / Path(out)
    existing = {}
    if out_path.exists():
        try:
            existing_payload = json.loads(out_path.read_text(encoding="utf-8"))
            existing = existing_payload if isinstance(existing_payload, dict) else {}
        except Exception:
            existing = {}
    report = build_broadcast_platform_e2e_report(ROOT, run_record_smoke=not skip_record_smoke)
    if existing:
        report = preserve_registered_platform_evidence(report, existing)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Build broadcast platform E2E evidence artifact.")
    parser.add_argument("--out", default="debugCapture/broadcast_platform_e2e_qa.json")
    parser.add_argument("--skip-record-smoke", action="store_true")
    parser.add_argument(
        "--allow-pending-platform",
        action="store_true",
        help="Return 0 when local runtime checks pass but manual platform checks are still pending.",
    )
    args = parser.parse_args()
    report = run_broadcast_platform_e2e_qa(out=args.out, skip_record_smoke=bool(args.skip_record_smoke))
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {ROOT / Path(args.out)}")
    return 0 if report.get("real_platform_evidence") or (args.allow_pending_platform and report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
