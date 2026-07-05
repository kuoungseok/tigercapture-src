"""Register a real Tiger Studio project for NLE readiness corpus QA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Real .tgp/.json project to register.")
    parser.add_argument("--manifest", type=Path, default=Path("qa_corpus/nle_real_projects/manifest.json"))
    parser.add_argument("--label", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--allow-generated",
        action="store_true",
        help="Allow generated QA fixtures. This is useful for tool tests, but does not satisfy real corpus readiness.",
    )
    args = parser.parse_args(argv)

    from app.nle_real_corpus import register_real_project

    result = register_real_project(
        args.project,
        manifest_path=args.manifest,
        label=args.label,
        notes=args.notes,
        allow_generated=bool(args.allow_generated),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
