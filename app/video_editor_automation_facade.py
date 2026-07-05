"""Owner-bound automation facade helpers for VideoEditorWindow."""
from __future__ import annotations

from typing import Any


def _ensure_python_action_registry(owner: Any | None):
    registry = getattr(owner, "_python_action_registry", None) if owner is not None else None
    if registry is not None:
        return registry
    from app.actions import build_default_action_registry

    registry = build_default_action_registry(owner)
    if owner is not None:
        owner._python_action_registry = registry
    return registry


def _ensure_automation_registry(owner: Any | None):
    registry = getattr(owner, "_automation_command_registry", None) if owner is not None else None
    if registry is not None:
        return registry
    from app.automation_commands import build_default_automation_registry

    registry = build_default_automation_registry(owner)
    if owner is not None:
        owner._automation_command_registry = registry
    return registry


def automation_command_specs(owner: Any | None = None) -> list[dict[str, Any]]:
    return _ensure_automation_registry(owner).specs()


def automation_execute_command(
    owner: Any | None,
    command: str,
    params: dict | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    result = _ensure_automation_registry(owner).execute(command, params or {}, dry_run=dry_run)
    return result.to_dict()


def automation_bridge_handle(owner: Any | None, request: Any) -> dict[str, Any]:
    from app.automation_bridge import handle_automation_bridge_request

    return handle_automation_bridge_request(owner, request)


def automation_mcp_handle(owner: Any | None, message: Any) -> dict[str, Any] | None:
    server = getattr(owner, "_automation_mcp_server", None) if owner is not None else None
    if server is None:
        from app.automation_mcp import AutomationMCPServer

        server = AutomationMCPServer(owner)
        if owner is not None:
            owner._automation_mcp_server = server
    if isinstance(message, str):
        return server.handle_json(message)
    return server.handle_message(message)
