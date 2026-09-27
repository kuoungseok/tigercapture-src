"""Loopback TCP bridge exposing the owner-bound automation MCP server.

The registered ``tiger-studio`` MCP process (tools/automation_mcp_server.py)
runs owner-less in a separate process and cannot reach a live editor window
directly. When a VideoEditorWindow is running, it listens on this loopback
socket; the external MCP process proxies JSON-RPC lines to it so tool calls
execute against the real owner instead of returning "no editor owner".
"""
from __future__ import annotations

import json
import os
from typing import Any

from PySide6.QtNetwork import QHostAddress, QTcpServer

DEFAULT_PORT = 8765
PORT_ENV_VAR = "TIGER_STUDIO_AUTOMATION_PORT"
DISABLE_ENV_VAR = "TIGER_STUDIO_DISABLE_AUTOMATION_BRIDGE"


class AutomationBridgeTcpServer(QTcpServer):
    def __init__(self, owner: Any, parent=None) -> None:
        super().__init__(parent)
        self.owner = owner
        self._buffers: dict[int, bytes] = {}
        self.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self) -> None:
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            if socket is None:
                continue
            self._buffers[id(socket)] = b""
            socket.readyRead.connect(lambda s=socket: self._on_ready_read(s))
            socket.disconnected.connect(lambda s=socket: self._buffers.pop(id(s), None))

    def _on_ready_read(self, socket) -> None:
        buf = self._buffers.get(id(socket), b"") + bytes(socket.readAll())
        while b"\n" in buf:
            line, _, buf = buf.partition(b"\n")
            if line.strip():
                self._dispatch(socket, line.decode("utf-8", errors="replace"))
        self._buffers[id(socket)] = buf

    def _dispatch(self, socket, line: str) -> None:
        from app.video_editor_automation_facade import automation_mcp_handle

        response = automation_mcp_handle(self.owner, line)
        if response is None:
            return
        payload = json.dumps(response, ensure_ascii=False, sort_keys=True, default=str) + "\n"
        socket.write(payload.encode("utf-8"))
        socket.flush()


def start_automation_bridge_server(owner: Any) -> AutomationBridgeTcpServer | None:
    """Start the loopback automation bridge for ``owner``, or return None if disabled/unavailable."""
    if os.environ.get(DISABLE_ENV_VAR):
        return None
    try:
        port = int(os.environ.get(PORT_ENV_VAR, str(DEFAULT_PORT)))
    except ValueError:
        port = DEFAULT_PORT
    server = AutomationBridgeTcpServer(owner, owner)
    if not server.listen(QHostAddress.SpecialAddress.LocalHost, port):
        server.deleteLater()
        return None
    return server
