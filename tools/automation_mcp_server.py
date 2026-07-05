"""Standalone stdio MCP wrapper for TigerCapture automation.

This process is intentionally owner-less: it exposes protocol/schema/list smoke
tests and safe commands that can run against a minimal snapshot. The in-app
editor can embed ``app.automation_mcp.AutomationMCPServer(owner)`` to expose the
same tools against the live project.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="TigerCapture automation MCP stdio server.")
    parser.add_argument("--stdio", action="store_true", help="Serve JSON-RPC lines over stdin/stdout.")
    parser.add_argument("--tools", action="store_true", help="Print MCP tools/list result and exit.")
    parser.add_argument("--initialize", action="store_true", help="Print MCP initialize result and exit.")
    args = parser.parse_args()

    from app.automation_mcp import AutomationMCPServer

    server = AutomationMCPServer(None)
    if args.stdio:
        return server.serve_json_lines(sys.stdin, sys.stdout)
    if args.tools:
        _print_json(server.handle_message({"jsonrpc": "2.0", "id": "tools", "method": "tools/list"}) or {})
        return 0
    if args.initialize:
        _print_json(server.handle_message({"jsonrpc": "2.0", "id": "init", "method": "initialize"}) or {})
        return 0
    _print_json(server.handle_message({"jsonrpc": "2.0", "id": "ping", "method": "ping"}) or {})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
