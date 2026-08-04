"""Wait for the active soak, run two more, then aggregate all three."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="", flush=True)
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed_report", type=Path)
    parser.add_argument("--additional-runs", type=int, default=2)
    parser.add_argument("--poll-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=43200.0)
    args = parser.parse_args()
    seed = args.seed_report.resolve(); started = time.monotonic()
    while not seed.is_file():
        if time.monotonic() - started >= args.timeout_seconds:
            return 2
        time.sleep(max(1.0, args.poll_seconds))
    reports = [seed]
    for _index in range(max(0, args.additional_runs)):
        completed = _run([
            sys.executable, str(ROOT / "tools" / "qa_painter_soak.py"),
            "--duration-seconds", "7200", "--sample-interval-seconds", "5",
            "--operation-interval-ms", "20", "--release-evidence",
        ])
        if completed.returncode:
            return completed.returncode
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        reports.append(Path(payload["report"]).resolve())
    accepted = _run([
        sys.executable, str(ROOT / "tools" / "qa_painter_soak_series_acceptance.py"),
        *(str(path) for path in reports),
    ])
    if accepted.returncode:
        return accepted.returncode
    return _run([sys.executable, str(ROOT / "tools" / "qa_painter_product_reapproval.py")]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
