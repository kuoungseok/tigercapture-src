"""Minimal stdio MCP wrapper around TigerCapture's safe automation bridge.

The MCP layer is intentionally boring: it translates common JSON-RPC MCP
methods into AutomationBridge calls and exposes no editor internals. A running
editor can embed this class with an owner; the standalone CLI uses a minimal
owner-less bridge for schema/list smoke tests.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, TextIO

from app.automation_bridge import AutomationBridge


MCP_SERVER_NAME = "tigercapture-automation"
MCP_SERVER_VERSION = "0.1.0"
MCP_PROTOCOL_VERSION = "2024-11-05"


def _json_text(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload or {}), ensure_ascii=False, sort_keys=True, default=str)


class AutomationMCPServer:
    """Small JSON-RPC server exposing TigerCapture automation as MCP tools."""

    def __init__(self, owner: Any | None = None, *, bridge: AutomationBridge | None = None) -> None:
        self.bridge = bridge or AutomationBridge(owner)
        self.owner = owner

    def handle_json(self, text: str) -> dict[str, Any] | None:
        try:
            message = json.loads(str(text or ""))
        except Exception as exc:
            return self._error(None, -32700, f"parse error: {exc}")
        if not isinstance(message, Mapping):
            return self._error(None, -32600, "invalid request")
        return self.handle_message(message)

    def handle_message(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        method = str(message.get("method") or "").strip()
        request_id = message.get("id")
        if method.startswith("notifications/"):
            return None
        if method == "initialize":
            return self._result(request_id, self.initialize_result())
        if method == "ping":
            return self._result(request_id, {})
        if method == "tools/list":
            return self._result(request_id, {"tools": self.tools()})
        if method == "tools/call":
            params = message.get("params") if isinstance(message.get("params"), Mapping) else {}
            return self._handle_tool_call(request_id, params)
        if method == "resources/list":
            return self._result(request_id, {"resources": []})
        if method == "prompts/list":
            return self._result(request_id, {"prompts": []})
        return self._error(request_id, -32601, f"method not found: {method}")

    def initialize_result(self) -> dict[str, Any]:
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {"name": MCP_SERVER_NAME, "version": MCP_SERVER_VERSION},
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {},
                "prompts": {},
            },
        }

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "tigercapture_ping",
                "description": "Check that the TigerCapture automation MCP server is alive.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "tigercapture_schema",
                "description": "Return the safe automation bridge protocol and security schema.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "tigercapture_list_commands",
                "description": "List registered TigerCapture automation commands.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "tigercapture_execute_command",
                "description": "Execute one registered TigerCapture automation command through the safe bridge.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Registered automation command name."},
                        "params": {"type": "object", "description": "Command-specific parameters."},
                        "dry_run": {"type": "boolean", "description": "Preview mutation without applying it."},
                    },
                    "required": ["command"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "tigercapture_list_actions",
                "description": "List registered Tiger Studio Python actions.",
                "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "name": "tigercapture_get_action_schema",
                "description": "Return one registered action schema.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"action": {"type": "string"}},
                    "required": ["action"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "tigercapture_preview_action",
                "description": "Preview one registered action using dry-run semantics.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "params": {"type": "object"},
                    },
                    "required": ["action"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "tigercapture_execute_action",
                "description": "Execute one registered Python action through the safe registry.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "params": {"type": "object"},
                        "dry_run": {"type": "boolean"},
                        "confirm_destructive": {"type": "boolean"},
                    },
                    "required": ["action"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "tigercapture_execute_sequence",
                "description": "Execute a sequence of registered Python actions.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "steps": {"type": "array", "items": {"type": "object"}},
                        "dry_run": {"type": "boolean"},
                        "confirm_destructive": {"type": "boolean"},
                    },
                    "required": ["steps"],
                    "additionalProperties": False,
                },
            },
        ]

    def serve_json_lines(self, input_stream: TextIO, output_stream: TextIO) -> int:
        for line in input_stream:
            if not line.strip():
                continue
            response = self.handle_json(line)
            if response is None:
                continue
            output_stream.write(json.dumps(response, ensure_ascii=False, sort_keys=True, default=str) + "\n")
            output_stream.flush()
        return 0

    def _handle_tool_call(self, request_id: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        name = str(params.get("name") or "").strip()
        arguments = params.get("arguments") if isinstance(params.get("arguments"), Mapping) else {}
        if name == "tigercapture_ping":
            payload = self.bridge.handle_request({"id": "mcp_ping", "method": "automation.ping"})
            return self._tool_result(request_id, payload)
        if name == "tigercapture_schema":
            payload = self.bridge.handle_request({"id": "mcp_schema", "method": "automation.schema"})
            return self._tool_result(request_id, payload)
        if name == "tigercapture_list_commands":
            payload = self.bridge.handle_request({"id": "mcp_commands", "method": "automation.list_commands"})
            return self._tool_result(request_id, payload)
        if name == "tigercapture_execute_command":
            command = str(arguments.get("command") or "").strip()
            if not command:
                return self._tool_result(request_id, {"ok": False, "error": "command is required"}, is_error=True)
            command_params = arguments.get("params") if isinstance(arguments.get("params"), Mapping) else {}
            payload = self.bridge.handle_request(
                {
                    "id": "mcp_execute",
                    "method": "automation.execute",
                    "params": {
                        "command": command,
                        "params": dict(command_params or {}),
                        "dry_run": bool(arguments.get("dry_run", False)),
                    },
                }
            )
            nested_ok = bool(payload.get("ok")) and bool(payload.get("result", {}).get("ok", True))
            return self._tool_result(request_id, payload, is_error=not nested_ok)
        if name in {
            "tigercapture_list_actions",
            "tigercapture_get_action_schema",
            "tigercapture_preview_action",
            "tigercapture_execute_action",
            "tigercapture_execute_sequence",
        }:
            return self._handle_action_tool_call(request_id, name, arguments)
        return self._error(request_id, -32602, f"unknown tool: {name}")

    def _action_registry(self):
        from app.actions import build_default_action_registry

        return build_default_action_registry(self.owner)

    def _handle_action_tool_call(self, request_id: Any, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        registry = self._action_registry()
        try:
            if name == "tigercapture_list_actions":
                payload = {"ok": True, "actions": registry.list_actions()}
                return self._tool_result(request_id, payload)
            if name == "tigercapture_get_action_schema":
                action = str(arguments.get("action") or "").strip()
                payload = {"ok": True, "schema": registry.get_action_schema(action)}
                return self._tool_result(request_id, payload)
            if name == "tigercapture_preview_action":
                action = str(arguments.get("action") or "").strip()
                params = arguments.get("params") if isinstance(arguments.get("params"), Mapping) else {}
                result = registry.preview_action(action, params).to_dict()
                return self._tool_result(request_id, result, is_error=not bool(result.get("ok")))
            if name == "tigercapture_execute_action":
                action = str(arguments.get("action") or "").strip()
                params = arguments.get("params") if isinstance(arguments.get("params"), Mapping) else {}
                result = registry.execute_action(
                    action,
                    params,
                    dry_run=bool(arguments.get("dry_run", False)),
                    confirm_destructive=bool(arguments.get("confirm_destructive", False)),
                ).to_dict()
                return self._tool_result(request_id, result, is_error=not bool(result.get("ok")))
            if name == "tigercapture_execute_sequence":
                steps = arguments.get("steps") if isinstance(arguments.get("steps"), list) else []
                payload = registry.execute_sequence(
                    steps,
                    dry_run=bool(arguments.get("dry_run", False)),
                    confirm_destructive=bool(arguments.get("confirm_destructive", False)),
                )
                return self._tool_result(request_id, payload, is_error=not bool(payload.get("ok")))
        except Exception as exc:
            return self._tool_result(request_id, {"ok": False, "error": str(exc)}, is_error=True)
        return self._error(request_id, -32602, f"unknown tool: {name}")

    def _tool_result(self, request_id: Any, payload: Mapping[str, Any], *, is_error: bool = False) -> dict[str, Any]:
        return self._result(
            request_id,
            {
                "content": [{"type": "text", "text": _json_text(payload)}],
                "isError": bool(is_error),
            },
        )

    def _result(self, request_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": dict(result or {})}

    def _error(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": int(code), "message": str(message)}}
