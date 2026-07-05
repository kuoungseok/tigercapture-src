"""JSON bridge for safe TigerCapture automation commands and actions.

This module is the small protocol layer external assistants can wrap with MCP.
It intentionally exposes only registered commands/actions; it never evaluates
Python code, shells out, imports user scripts, or mutates the editor outside the
registered handlers.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any, TextIO

from app.automation_commands import (
    AUTOMATION_COMMAND_SCHEMA_VERSION,
    build_default_automation_registry,
)
from app.actions import ACTION_SCHEMA_VERSION, build_default_action_registry


AUTOMATION_BRIDGE_PROTOCOL_VERSION = 1
MAX_AUTOMATION_REQUEST_BYTES = 1_000_000


class AutomationBridge:
    """Handle JSON requests against a safe automation command registry."""

    def __init__(self, owner: Any | None = None, *, max_request_bytes: int = MAX_AUTOMATION_REQUEST_BYTES) -> None:
        self.owner = owner
        self.max_request_bytes = max(1024, int(max_request_bytes or MAX_AUTOMATION_REQUEST_BYTES))
        self._registry = build_default_automation_registry(owner)
        self._action_registry = build_default_action_registry(owner)

    def handle_json(self, text: str) -> dict[str, Any]:
        raw = str(text or "")
        if len(raw.encode("utf-8", errors="ignore")) > self.max_request_bytes:
            return self._error(None, "request_too_large")
        try:
            request = json.loads(raw)
        except Exception as exc:
            return self._error(None, f"invalid_json:{exc}")
        if not isinstance(request, Mapping):
            return self._error(None, "request_must_be_object")
        return self.handle_request(request)

    def handle_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = request.get("id")
        method = str(request.get("method") or request.get("type") or "").strip()
        if method in {"", "automation.ping", "ping"}:
            return self._ok(request_id, {"pong": True, "protocol_version": AUTOMATION_BRIDGE_PROTOCOL_VERSION})
        if method in {"automation.schema", "schema"}:
            return self._ok(request_id, self.schema())
        if method in {"automation.list_commands", "list_commands", "commands"}:
            return self._ok(request_id, {"commands": self._registry.specs()})
        if method in {"automation.list_actions", "list_actions", "actions"}:
            return self._ok(request_id, {"actions": self._action_registry.list_actions()})
        if method in {"automation.get_action_schema", "get_action_schema", "action_schema"}:
            params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
            action = str(params.get("action") or request.get("action") or "").strip()
            try:
                return self._ok(request_id, {"ok": True, "schema": self._action_registry.get_action_schema(action)})
            except Exception as exc:
                return self._ok(request_id, {"ok": False, "schema": {}, "error": str(exc)})
        if method in {"automation.preview_action", "preview_action"}:
            params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
            action = str(params.get("action") or request.get("action") or "").strip()
            action_params = params.get("params") if isinstance(params.get("params"), Mapping) else {}
            result = self._action_registry.preview_action(action, action_params).to_dict()
            return self._ok(request_id, result)
        if method in {"automation.execute_action", "execute_action"}:
            params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
            action = str(params.get("action") or request.get("action") or "").strip()
            action_params = params.get("params") if isinstance(params.get("params"), Mapping) else {}
            result = self._action_registry.execute_action(
                action,
                action_params,
                dry_run=bool(params.get("dry_run") or request.get("dry_run")),
                confirm_destructive=bool(params.get("confirm_destructive") or request.get("confirm_destructive")),
            ).to_dict()
            return self._ok(request_id, result)
        if method in {"automation.execute_sequence", "execute_sequence"}:
            params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
            steps = params.get("steps") if isinstance(params.get("steps"), list) else []
            result = self._action_registry.execute_sequence(
                steps,
                dry_run=bool(params.get("dry_run") or request.get("dry_run")),
                confirm_destructive=bool(params.get("confirm_destructive") or request.get("confirm_destructive")),
            )
            return self._ok(request_id, result)
        if method in {"automation.execute", "execute"}:
            params = request.get("params") if isinstance(request.get("params"), Mapping) else {}
            command = str(params.get("command") or request.get("command") or "").strip()
            command_params = params.get("params") if isinstance(params.get("params"), Mapping) else {}
            dry_run = bool(params.get("dry_run") or request.get("dry_run"))
            result = self._registry.execute(command, command_params, dry_run=dry_run).to_dict()
            return self._ok(request_id, result)
        return self._error(request_id, f"unknown_method:{method}")

    def schema(self) -> dict[str, Any]:
        return {
            "protocol_version": AUTOMATION_BRIDGE_PROTOCOL_VERSION,
            "command_schema_version": AUTOMATION_COMMAND_SCHEMA_VERSION,
            "action_schema_version": ACTION_SCHEMA_VERSION,
            "transport": "json-lines",
            "methods": [
                "automation.ping",
                "automation.schema",
                "automation.list_commands",
                "automation.list_actions",
                "automation.get_action_schema",
                "automation.preview_action",
                "automation.execute_action",
                "automation.execute_sequence",
                "automation.execute",
            ],
            "security": {
                "arbitrary_python": False,
                "arbitrary_shell": False,
                "registered_commands_only": True,
                "registered_actions_only": True,
                "max_request_bytes": self.max_request_bytes,
            },
            "execute_params": {
                "command": "registered automation command name",
                "params": "command-specific object",
                "dry_run": "optional bool",
            },
            "execute_action_params": {
                "action": "registered Python action id",
                "params": "action-specific object",
                "dry_run": "optional bool",
                "confirm_destructive": "optional bool for destructive actions",
            },
        }

    def serve_json_lines(self, input_stream: TextIO, output_stream: TextIO) -> int:
        for line in input_stream:
            if not line.strip():
                continue
            response = self.handle_json(line)
            output_stream.write(json.dumps(response, ensure_ascii=False, sort_keys=True, default=str) + "\n")
            output_stream.flush()
        return 0

    def _ok(self, request_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "id": request_id,
            "protocol_version": AUTOMATION_BRIDGE_PROTOCOL_VERSION,
            "result": dict(result or {}),
            "error": "",
        }

    def _error(self, request_id: Any, error: str) -> dict[str, Any]:
        return {
            "ok": False,
            "id": request_id,
            "protocol_version": AUTOMATION_BRIDGE_PROTOCOL_VERSION,
            "result": {},
            "error": str(error or "automation_bridge_error"),
        }


def handle_automation_bridge_request(owner: Any | None, request: Mapping[str, Any] | str) -> dict[str, Any]:
    bridge = AutomationBridge(owner)
    if isinstance(request, str):
        return bridge.handle_json(request)
    return bridge.handle_request(request)
