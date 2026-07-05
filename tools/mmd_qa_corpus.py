"""Run deterministic QA diagnostics for the local MMD QA corpus manifest."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.mmd.qa_corpus import DEFAULT_MMD_QA_MANIFEST, format_mmd_qa_manifest_text, run_mmd_qa_manifest


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Run the local MMD QA corpus manifest")
    parser.add_argument("--manifest", default=str(DEFAULT_MMD_QA_MANIFEST), help="MMD QA corpus manifest path")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload")
    args = parser.parse_args()

    payload = run_mmd_qa_manifest(args.manifest)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_mmd_qa_manifest_text(payload))
    return 0 if bool(payload.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
