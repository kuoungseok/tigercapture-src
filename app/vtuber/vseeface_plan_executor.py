"""Explicit executor wrapper for gated VSeeFace action plans.

The bridge is still external-sidecar only. This module exists so future UI code
has one narrow place to execute a previously reviewed plan, instead of calling
subprocesses directly from view code.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping

from app.subprocess_utils import merge_hidden_subprocess_kwargs
from app.vtuber.vseeface_action_plan import build_vseeface_execution_gate


PLAN_EXECUTOR_SCHEMA = "tigerstudio.vtuber.vseeface_bridge.plan_executor.v1"
CommandRunner = Callable[..., Any]


def execute_vseeface_plan(
    plan: Mapping[str, Any] | None,
    *,
    confirm: bool = False,
    allow_admin: bool = False,
    execute: bool = False,
    timeout_s: float = 120.0,
    runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Run a gated VSeeFace plan only when explicitly requested.

    `execute=False` is the default and returns only a dry-run report. A caller
    must pass both `confirm=True` and `execute=True` before subprocesses can run.
    """
    gate = build_vseeface_execution_gate(
        plan,
        confirm=bool(confirm),
        allow_admin=bool(allow_admin),
    )
    execute_requested = bool(execute)
    if not execute_requested:
        return {
            "schema": PLAN_EXECUTOR_SCHEMA,
            "ok": bool(gate.get("ok")),
            "execute_requested": False,
            "executed": False,
            "dry_run": True,
            "gate": gate,
            "steps": [_dry_run_step(step) for step in gate.get("steps", []) if isinstance(step, Mapping)],
            "errors": [],
            "warnings": list(gate.get("warnings") or []),
        }
    if not bool(gate.get("execute_allowed", False)):
        return {
            "schema": PLAN_EXECUTOR_SCHEMA,
            "ok": False,
            "execute_requested": True,
            "executed": False,
            "dry_run": False,
            "gate": gate,
            "steps": [_dry_run_step(step) for step in gate.get("steps", []) if isinstance(step, Mapping)],
            "errors": ["execution_gate_blocked"],
            "warnings": list(gate.get("warnings") or []),
        }

    active_runner = runner or _subprocess_runner
    step_results: list[dict[str, Any]] = []
    errors: list[str] = []
    for step in gate.get("steps", []):
        if not isinstance(step, Mapping) or str(step.get("kind") or "") != "tool":
            continue
        result = _run_tool_step(step, runner=active_runner, timeout_s=max(1.0, float(timeout_s or 120.0)))
        step_results.append(result)
        if not bool(result.get("ok", False)):
            errors.append(f"step_failed:{result.get('id')}")
            break

    return {
        "schema": PLAN_EXECUTOR_SCHEMA,
        "ok": not errors,
        "execute_requested": True,
        "executed": bool(step_results),
        "dry_run": False,
        "gate": gate,
        "steps": step_results,
        "errors": errors,
        "warnings": list(gate.get("warnings") or []),
    }


def _dry_run_step(step: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(step.get("id") or ""),
        "kind": str(step.get("kind") or ""),
        "state": str(step.get("state") or ""),
        "program": str(step.get("program") or ""),
        "args": [str(item) for item in (step.get("args") or [])],
        "would_run": str(step.get("kind") or "") == "tool" and str(step.get("state") or "") == "ready",
        "executed": False,
        "ok": None,
    }


def _run_tool_step(step: Mapping[str, Any], *, runner: CommandRunner, timeout_s: float) -> dict[str, Any]:
    program = str(step.get("program") or "")
    args = [str(item) for item in (step.get("args") or [])]
    command = [program] + args
    try:
        completed = runner(
            command,
            timeout=timeout_s,
            text=True,
            capture_output=True,
            **merge_hidden_subprocess_kwargs(),
        )
        returncode = int(getattr(completed, "returncode", 1))
        return {
            "id": str(step.get("id") or ""),
            "kind": "tool",
            "command": command,
            "executed": True,
            "ok": returncode == 0,
            "returncode": returncode,
            "stdout": str(getattr(completed, "stdout", "") or ""),
            "stderr": str(getattr(completed, "stderr", "") or ""),
        }
    except Exception as exc:
        return {
            "id": str(step.get("id") or ""),
            "kind": "tool",
            "command": command,
            "executed": True,
            "ok": False,
            "returncode": -1,
            "stdout": "",
            "stderr": str(exc),
        }


def _subprocess_runner(command: list[str], **kwargs: Any) -> Any:
    import subprocess

    return subprocess.run(command, **kwargs)
