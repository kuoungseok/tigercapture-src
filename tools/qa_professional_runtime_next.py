from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def run_professional_runtime_next_qa(*, out: str | Path | None = None) -> dict[str, Any]:
    from app.professional_runtime import professional_runtime_verification_report

    report = professional_runtime_verification_report(out_dir=Path("debugCapture"))
    if out is not None:
        _write_json(Path(out), report)
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Validate concrete runtime checks for professional workflow payloads.")
    parser.add_argument("--out", default="debugCapture/professional_runtime_next_qa.json")
    args = parser.parse_args()
    report = run_professional_runtime_next_qa(out=args.out)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {Path(args.out).resolve()}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
