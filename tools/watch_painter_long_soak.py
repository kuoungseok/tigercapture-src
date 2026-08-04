"""Wait for a named long-soak report, then run acceptance and R8 aggregation."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_report", type=Path)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=14400.0)
    args = parser.parse_args()
    raw_report = args.raw_report.resolve()
    started = time.monotonic()
    while not raw_report.is_file():
        if time.monotonic() - started >= max(1.0, args.timeout_seconds):
            print(json.dumps({"status": "timeout", "raw_report": str(raw_report)}), flush=True)
            return 2
        time.sleep(max(1.0, args.poll_seconds))

    acceptance = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "qa_painter_long_soak_acceptance.py"), str(raw_report)],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    print(acceptance.stdout, end="", flush=True)
    if acceptance.stderr:
        print(acceptance.stderr, file=sys.stderr, end="", flush=True)
    if acceptance.returncode != 0:
        return acceptance.returncode

    reapproval = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "qa_painter_product_reapproval.py")],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    print(reapproval.stdout, end="", flush=True)
    if reapproval.stderr:
        print(reapproval.stderr, file=sys.stderr, end="", flush=True)
    return reapproval.returncode


if __name__ == "__main__":
    raise SystemExit(main())
