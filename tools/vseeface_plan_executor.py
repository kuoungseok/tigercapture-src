"""Dry-run or explicitly execute a gated VSeeFace action plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.vtuber.vseeface_plan_executor import execute_vseeface_plan  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run or explicitly execute a VSeeFace action plan.")
    parser.add_argument("--plan", required=True, help="Action plan JSON, or a payload containing a top-level plan object.")
    parser.add_argument("--confirm", action="store_true", help="Required before any step may execute.")
    parser.add_argument("--execute", action="store_true", help="Actually run gated tool steps. Omit for dry-run.")
    parser.add_argument("--allow-admin", action="store_true", help="Allow admin-marked steps after external approval.")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--out", default="", help="Optional output JSON path.")
    args = parser.parse_args(argv)

    payload = _read_json(args.plan)
    plan = payload.get("plan") if isinstance(payload, dict) and isinstance(payload.get("plan"), dict) else payload
    result = execute_vseeface_plan(
        plan if isinstance(plan, dict) else {},
        confirm=bool(args.confirm),
        allow_admin=bool(args.allow_admin),
        execute=bool(args.execute),
        timeout_s=float(args.timeout),
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(json.dumps({
            "ok": result["ok"],
            "execute_requested": result["execute_requested"],
            "executed": result["executed"],
            "dry_run": result["dry_run"],
            "out": str(out),
        }, ensure_ascii=False))
    else:
        print(text)
    return 0 if result["ok"] else 2


def _read_json(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
