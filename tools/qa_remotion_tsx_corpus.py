"""Inspect a Remotion-style TSX corpus without executing source files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.motion_designer.remotion_tsx import inspect_remotion_tsx


def inspect_corpus(path: str | Path) -> dict[str, object]:
    root = Path(path).expanduser().resolve(strict=True)
    files = sorted({*root.rglob("*.tsx"), *root.rglob("*.jsx")})
    rows = [inspect_remotion_tsx(source).to_dict() for source in files]
    return {
        "schema": "tigerstudio.motion.remotion_tsx.corpus_qa.v1",
        "root": str(root),
        "count": len(rows),
        "compatible": sum(1 for row in rows if row["ok"]),
        "incompatible": sum(1 for row in rows if not row["ok"]),
        "ok": bool(rows) and all(row["ok"] for row in rows),
        "sources": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    report = inspect_corpus(args.path)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output).expanduser().resolve(strict=False)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(json.dumps({
        key: report[key] for key in ("ok", "count", "compatible", "incompatible")
    }, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
