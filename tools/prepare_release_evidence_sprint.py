"""Prepare scripts/templates for collecting release-blocking real evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Prepare a release evidence collection sprint.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--out", default="debugCapture/release_evidence_sprint_qa.json")
    parser.add_argument("--work-dir", default="debugCapture/release_evidence_sprint")
    parser.add_argument("--write-files", action="store_true")
    parser.add_argument("--max-screenstudio", type=int, default=20)
    parser.add_argument("--max-ai", type=int, default=20)
    parser.add_argument("--capture-duration-ms", type=int, default=60_000)
    args = parser.parse_args()

    from app.release_evidence_sprint import build_release_evidence_sprint

    root = Path(args.root)
    report = build_release_evidence_sprint(
        root,
        out_dir=args.work_dir,
        write_files=bool(args.write_files),
        max_screenstudio=max(0, int(args.max_screenstudio or 0)),
        max_ai=max(0, int(args.max_ai or 0)),
        capture_duration_ms=max(1000, int(args.capture_duration_ms or 60_000)),
    )
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = root / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

