"""Validate a VSeeFace action plan before any executor runs it."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a VSeeFace action plan without executing it.")
    parser.add_argument("--plan", required=True, help="Action plan JSON, or a payload containing a top-level plan object.")
    parser.add_argument("--confirm", action="store_true", help="Mark user confirmation as present for gate evaluation only.")
    parser.add_argument("--allow-admin", action="store_true", help="Mark administrator approval as present for gate evaluation only.")
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    args = parser.parse_args(argv)

    payload = _read_json(args.plan)
    plan = payload.get("plan") if isinstance(payload, dict) and isinstance(payload.get("plan"), dict) else payload
    gate = build_vseeface_execution_gate(
        plan if isinstance(plan, dict) else {},
        confirm=bool(args.confirm),
        allow_admin=bool(args.allow_admin),
    )
    text = json.dumps(gate, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(json.dumps({
            "ok": gate["ok"],
            "execute_allowed": gate["execute_allowed"],
            "requires_confirmation": gate["requires_confirmation"],
            "requires_admin": gate["requires_admin"],
            "out": str(out),
        }, ensure_ascii=False))
    else:
        print(text)
    return 0 if gate["ok"] else 2


def _read_json(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
