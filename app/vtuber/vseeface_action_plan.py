"""Safe action-plan helpers for the external VSeeFace bridge."""
from __future__ import annotations

from typing import Any, Mapping


ACTION_PREVIEW_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.action_preview.v1"
EXECUTION_GATE_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.execution_gate.v1"
ALLOWED_TOOL_PROGRAMS = frozenset({
    ".venv\\scripts\\python.exe",
})
ALLOWED_TOOL_SCRIPTS = frozenset({
    "tools\\configure_vseeface_sidecar.py",
    "tools\\install_vseeface_sidecar.py",
    "tools\\register_vseeface_camera.py",
    "tools\\verify_vseeface_post_install.py",
    "tools\\vseeface_capture_backend_preflight.py",
    "tools\\vseeface_live_check.py",
})


def select_vseeface_action(status: Mapping[str, Any], action_id: str | None = None) -> dict[str, Any] | None:
    """Return the requested action, or the primary action when no id is given."""
    actions = status.get("actions") if isinstance(status.get("actions"), list) else []
    if action_id:
        for item in actions:
            if isinstance(item, Mapping) and str(item.get("id") or "") == str(action_id):
                return dict(item)
        return None
    for item in actions:
        if isinstance(item, Mapping) and bool(item.get("primary", False)):
            return dict(item)
    for item in actions:
        if isinstance(item, Mapping):
            return dict(item)
    return None


def validate_vseeface_action_plan(plan: Mapping[str, Any] | None) -> dict[str, Any]:
    """Validate a declarative action plan without executing it."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(plan, Mapping):
        return {"ok": False, "errors": ["plan_missing"], "warnings": warnings}
    if bool(plan.get("auto_run", False)):
        errors.append("plan_must_not_auto_run")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("plan_steps_missing")
        steps = []
    requires_admin = bool(plan.get("requires_admin", False))
    has_admin_step = False
    for idx, step in enumerate(steps):
        if not isinstance(step, Mapping):
            errors.append(f"step_{idx}_invalid")
            continue
        if bool(step.get("auto_run", False)):
            errors.append(f"step_{idx}_must_not_auto_run")
        if bool(step.get("requires_admin", False)):
            has_admin_step = True
    if has_admin_step and not requires_admin:
        errors.append("admin_step_requires_admin_plan")
    if requires_admin:
        warnings.append("administrator_approval_required")
    if bool(plan.get("would_write_when_executed", False)):
        warnings.append("file_write_requires_user_confirmation")
    return {"ok": not errors, "errors": errors, "warnings": warnings}


def build_vseeface_action_preview(
    status: Mapping[str, Any],
    *,
    action_id: str | None = None,
    allow_admin: bool = False,
) -> dict[str, Any]:
    """Build a dry-run preview of a bridge action.

    This function never launches tools. It only tells the UI which steps would
    be manual, which tool commands would be available, and which steps require
    administrator approval.
    """
    action = select_vseeface_action(status, action_id)
    if action is None:
        return {
            "schema": ACTION_PREVIEW_SCHEMA,
            "ok": False,
            "action_id": str(action_id or ""),
            "errors": ["action_not_found"],
            "warnings": [],
            "requires_admin": False,
            "execute_allowed": False,
            "steps": [],
        }
    plan = action.get("plan") if isinstance(action.get("plan"), Mapping) else {}
    validation = validate_vseeface_action_plan(plan)
    requires_admin = bool(plan.get("requires_admin", False))
    execute_allowed = bool(validation.get("ok")) and (not requires_admin or bool(allow_admin))
    return {
        "schema": ACTION_PREVIEW_SCHEMA,
        "ok": bool(validation.get("ok")),
        "action_id": str(action.get("id") or ""),
        "label": str(action.get("label") or ""),
        "kind": str(action.get("kind") or ""),
        "requires_admin": requires_admin,
        "allow_admin": bool(allow_admin),
        "execute_allowed": execute_allowed,
        "auto_run": False,
        "errors": list(validation.get("errors") or []),
        "warnings": list(validation.get("warnings") or []),
        "steps": [_preview_step(item, allow_admin=allow_admin) for item in plan.get("steps", []) if isinstance(item, Mapping)],
    }


def _preview_step(step: Mapping[str, Any], *, allow_admin: bool) -> dict[str, Any]:
    kind = str(step.get("kind") or "")
    requires_admin = bool(step.get("requires_admin", False))
    if kind == "tool":
        state = "requires_admin_confirmation" if requires_admin and not allow_admin else "ready"
        return {
            "id": str(step.get("id") or ""),
            "kind": kind,
            "state": state,
            "program": str(step.get("program") or ""),
            "args": [str(item) for item in (step.get("args") or [])],
            "requires_admin": requires_admin,
            "auto_run": False,
        }
    if kind == "ui":
        payload = {
            "id": str(step.get("id") or ""),
            "kind": kind,
            "state": "ui_required",
            "control": str(step.get("control") or ""),
            "text": str(step.get("text") or ""),
            "requires_admin": requires_admin,
            "auto_run": False,
        }
        if step.get("registry_action"):
            payload["registry_action"] = str(step.get("registry_action") or "")
        if isinstance(step.get("form"), Mapping):
            payload["form"] = dict(step.get("form") or {})
        return payload
    return {
        "id": str(step.get("id") or ""),
        "kind": kind or "manual",
        "state": "manual_required",
        "text": str(step.get("text") or ""),
        "requires_admin": requires_admin,
        "auto_run": False,
    }


def build_vseeface_execution_gate(
    plan: Mapping[str, Any] | None,
    *,
    confirm: bool = False,
    allow_admin: bool = False,
) -> dict[str, Any]:
    """Validate whether a VSeeFace plan may be handed to an executor.

    This is intentionally still read-only. It does not run subprocesses; it only
    marks which steps are safe, blocked, or waiting for explicit confirmation.
    """
    validation = validate_vseeface_action_plan(plan)
    errors = [str(item) for item in validation.get("errors") or []]
    warnings = [str(item) for item in validation.get("warnings") or []]
    steps = plan.get("steps") if isinstance(plan, Mapping) and isinstance(plan.get("steps"), list) else []
    gated_steps: list[dict[str, Any]] = []
    tool_step_count = 0
    interactive_step_count = 0
    admin_step_count = 0

    for idx, step in enumerate(steps):
        if not isinstance(step, Mapping):
            continue
        kind = str(step.get("kind") or "")
        requires_admin = bool(step.get("requires_admin", False))
        if kind == "tool":
            tool_step_count += 1
            if requires_admin:
                admin_step_count += 1
            gated = _gate_tool_step(step, idx=idx, confirm=confirm, allow_admin=allow_admin)
            gated_steps.append(gated)
            for error in gated.get("errors") or []:
                _append_unique(errors, str(error))
            for warning in gated.get("warnings") or []:
                _append_unique(warnings, str(warning))
            continue
        interactive_step_count += 1
        _append_unique(warnings, f"step_{idx}_interactive_step_pending")
        gated_steps.append({
            "id": str(step.get("id") or ""),
            "kind": kind or "manual",
            "state": "ui_required" if kind == "ui" else "manual_required",
            "requires_admin": requires_admin,
            "auto_run": False,
            "errors": [],
            "warnings": ["interactive_step_pending"],
        })

    if tool_step_count == 0:
        _append_unique(errors, "tool_steps_missing")
    if interactive_step_count > 0:
        _append_unique(errors, "interactive_steps_pending")
    if not bool(confirm):
        _append_unique(warnings, "user_confirmation_required")
    if admin_step_count > 0 and not bool(allow_admin):
        _append_unique(warnings, "administrator_approval_required")

    execute_allowed = (
        not errors
        and bool(confirm)
        and tool_step_count > 0
        and interactive_step_count == 0
        and (admin_step_count == 0 or bool(allow_admin))
    )
    return {
        "schema": EXECUTION_GATE_SCHEMA,
        "ok": not errors,
        "execute_allowed": execute_allowed,
        "confirm": bool(confirm),
        "allow_admin": bool(allow_admin),
        "requires_confirmation": not bool(confirm),
        "requires_admin": admin_step_count > 0,
        "tool_step_count": tool_step_count,
        "interactive_step_count": interactive_step_count,
        "admin_step_count": admin_step_count,
        "errors": errors,
        "warnings": warnings,
        "steps": gated_steps,
    }


def _gate_tool_step(
    step: Mapping[str, Any],
    *,
    idx: int,
    confirm: bool,
    allow_admin: bool,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    program = str(step.get("program") or "")
    args = [str(item) for item in (step.get("args") or [])]
    requires_admin = bool(step.get("requires_admin", False))
    if not _is_allowed_tool_program(program):
        errors.append(f"step_{idx}_program_not_allowed")
    if not _is_allowed_tool_script(args):
        errors.append(f"step_{idx}_script_not_allowed")
    if requires_admin and not allow_admin:
        warnings.append("administrator_approval_required")
        state = "requires_admin_confirmation"
    elif not confirm:
        warnings.append("user_confirmation_required")
        state = "requires_user_confirmation"
    elif errors:
        state = "blocked"
    else:
        state = "ready"
    return {
        "id": str(step.get("id") or ""),
        "kind": "tool",
        "state": state,
        "program": program,
        "args": args,
        "requires_admin": requires_admin,
        "auto_run": False,
        "errors": errors,
        "warnings": warnings,
    }


def _is_allowed_tool_program(program: str) -> bool:
    normalized = _normalize_command_part(program).casefold()
    return normalized in ALLOWED_TOOL_PROGRAMS


def _is_allowed_tool_script(args: list[str]) -> bool:
    if not args:
        return False
    script = _normalize_command_part(args[0]).casefold()
    return script in ALLOWED_TOOL_SCRIPTS


def _normalize_command_part(value: str) -> str:
    text = str(value or "").strip().replace("/", "\\")
    while text.startswith(".\\"):
        text = text[2:]
    return text.casefold()


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
