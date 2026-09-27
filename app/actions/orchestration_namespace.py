"""Multi-step plan execution: run several actions and return one verification snapshot.

Exists so an external planner (an AI agent driving the app through the automation
bridge) can submit an entire plan and get every step's result plus a post-plan
status snapshot in a single round trip, instead of chaining execute_action calls
one at a time and separately polling status.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def register_orchestration_actions(registry: Any) -> None:
    spec = ActionSpec(
        "orchestrate.execute_plan",
        "Execute a multi-step action plan and return per-step results plus an optional verification snapshot.",
        "orchestrate",
        params_schema=schema_object(
            {
                "steps": {
                    "type": "array",
                    "items": schema_object(
                        {
                            "action": {"type": "string"},
                            "params": {"type": "object", "additionalProperties": True},
                            "confirm_destructive": {"type": "boolean"},
                        },
                        required=("action",),
                    ),
                },
                "continue_on_error": {"type": "boolean"},
                "verify": schema_object(
                    {
                        "action": {"type": "string"},
                        "params": {"type": "object", "additionalProperties": True},
                    },
                ),
            },
            required=("steps",),
        ),
        mutating=True,
        destructive=False,
        requires_owner=True,
        supports_dry_run=False,
    )

    def _handler(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        steps = params.get("steps")
        if not isinstance(steps, list) or not steps:
            return error_result("orchestrate.execute_plan", "steps must be a non-empty array", dry_run=dry_run)
        continue_on_error = bool(params.get("continue_on_error", False))

        step_results: list[dict[str, Any]] = []
        any_step_failed = False
        for index, step in enumerate(steps):
            if not isinstance(step, Mapping) or not str(step.get("action") or "").strip():
                result = error_result("", f"step {index} missing action").to_dict()
            else:
                result = registry.execute_action(
                    str(step.get("action") or ""),
                    step.get("params") if isinstance(step.get("params"), Mapping) else {},
                    confirm_destructive=bool(step.get("confirm_destructive", False)),
                ).to_dict()
            step_results.append({"index": index, **result})
            if not result.get("ok"):
                any_step_failed = True
                if not continue_on_error:
                    break

        verification: dict[str, Any] = {}
        verify_spec = params.get("verify")
        if isinstance(verify_spec, Mapping) and str(verify_spec.get("action") or "").strip():
            verification = registry.execute_action(
                str(verify_spec.get("action") or ""),
                verify_spec.get("params") if isinstance(verify_spec.get("params"), Mapping) else {},
            ).to_dict()

        payload = {
            "steps_total": len(steps),
            "steps_run": len(step_results),
            "any_step_failed": any_step_failed,
            "results": step_results,
            "verification": verification,
        }
        return ok_result("orchestrate.execute_plan", payload, changed=True)

    registry.register(spec, _handler)


__all__ = ["register_orchestration_actions"]
