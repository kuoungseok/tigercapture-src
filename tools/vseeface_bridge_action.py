"""Dry-run a VSeeFace bridge action plan from a status report."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_action_plan import build_vseeface_action_preview  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview a VSeeFace bridge action plan without executing it.")
    parser.add_argument("--status-report", required=True)
    parser.add_argument("--action-id", default="", help="Optional action id. Defaults to the primary action.")
    parser.add_argument("--allow-admin", action="store_true", help="Mark admin steps as allowed in the preview only.")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    status = json.loads(Path(args.status_report).read_text(encoding="utf-8"))
    preview = build_vseeface_action_preview(
        status,
        action_id=str(args.action_id or "") or None,
        allow_admin=bool(args.allow_admin),
    )
    text = json.dumps(preview, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(json.dumps({
            "ok": preview["ok"],
            "action_id": preview["action_id"],
            "requires_admin": preview["requires_admin"],
            "execute_allowed": preview["execute_allowed"],
            "out": str(out),
        }, ensure_ascii=False))
    else:
        print(text)
    return 0 if preview["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
