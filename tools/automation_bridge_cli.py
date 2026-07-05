"""Command-line JSON bridge smoke tool for TigerCapture automation.

This tool is intentionally narrow: it talks to the same safe command registry
that a future MCP adapter should wrap. Without a running editor owner it can
still expose schema, command specs, and commands that work against a minimal
snapshot.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _json_arg(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError("JSON argument must be an object")
    return data


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="TigerCapture safe automation JSON bridge.")
    parser.add_argument("--stdin", action="store_true", help="Serve JSON-lines requests from stdin.")
    parser.add_argument("--schema", action="store_true", help="Print the bridge protocol schema.")
    parser.add_argument("--list", action="store_true", help="List registered automation commands.")
    parser.add_argument("--execute", help="Execute one registered automation command.")
    parser.add_argument("--params", default="{}", help="JSON object passed to --execute.")
    parser.add_argument("--dry-run", action="store_true", help="Dry-run a mutating command.")
    args = parser.parse_args()

    from app.automation_bridge import AutomationBridge

    bridge = AutomationBridge(None)
    if args.stdin:
        return bridge.serve_json_lines(sys.stdin, sys.stdout)
    if args.schema:
        _print_json(bridge.handle_request({"id": "schema", "method": "automation.schema"}))
        return 0
    if args.list:
        _print_json(bridge.handle_request({"id": "commands", "method": "automation.list_commands"}))
        return 0
    if args.execute:
        params = _json_arg(args.params)
        response = bridge.handle_request(
            {
                "id": "execute",
                "method": "automation.execute",
                "params": {"command": args.execute, "params": params, "dry_run": bool(args.dry_run)},
            }
        )
        _print_json(response)
        return 0 if response.get("ok") and response.get("result", {}).get("ok", True) else 1

    _print_json(bridge.handle_request({"id": "ping", "method": "automation.ping"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
