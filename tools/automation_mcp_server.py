"""Standalone stdio MCP wrapper for TigerCapture automation.

When a TigerCapture editor window is running, it listens on a loopback
automation bridge (app.automation_bridge_server); this process proxies
stdio JSON-RPC to that socket so tools execute against the live, owner-bound
project. If no editor is running, it falls back to an owner-less bridge that
only exposes protocol/schema/list smoke tests and safe read-only commands.
"""
from __future__ import annotations

import argparse
import json
import os
import socket as socket_lib
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BRIDGE_PORT_ENV_VAR = "TIGER_STUDIO_AUTOMATION_PORT"
BRIDGE_DEFAULT_PORT = 8765
BRIDGE_CONNECT_TIMEOUT = 0.3


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str))


def _connect_live_bridge() -> socket_lib.socket | None:
    try:
        port = int(os.environ.get(BRIDGE_PORT_ENV_VAR, str(BRIDGE_DEFAULT_PORT)))
    except ValueError:
        port = BRIDGE_DEFAULT_PORT
    try:
        sock = socket_lib.create_connection(("127.0.0.1", port), timeout=BRIDGE_CONNECT_TIMEOUT)
    except OSError:
        return None
    sock.settimeout(None)
    return sock


def _pump_socket_to_stream(sock_reader, output_stream) -> None:
    for line in sock_reader:
        if not line.strip():
            continue
        output_stream.write(line if line.endswith("\n") else line + "\n")
        output_stream.flush()


def _serve_stdio_via_live_bridge(sock: socket_lib.socket, input_stream, output_stream) -> int:
    sock_writer = sock.makefile("w", encoding="utf-8", newline="\n")
    sock_reader = sock.makefile("r", encoding="utf-8", newline="\n")
    reader_thread = threading.Thread(
        target=_pump_socket_to_stream, args=(sock_reader, output_stream), daemon=True
    )
    reader_thread.start()
    for line in input_stream:
        if not line.strip():
            continue
        try:
            sock_writer.write(line if line.endswith("\n") else line + "\n")
            sock_writer.flush()
        except OSError:
            break
    try:
        sock.shutdown(socket_lib.SHUT_WR)
    except OSError:
        pass
    reader_thread.join(timeout=2.0)
    return 0


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

    if args.stdio:
        live_bridge = _connect_live_bridge()
        if live_bridge is not None:
            return _serve_stdio_via_live_bridge(live_bridge, sys.stdin, sys.stdout)
        server = AutomationMCPServer(None)
        return server.serve_json_lines(sys.stdin, sys.stdout)

    server = AutomationMCPServer(None)
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
