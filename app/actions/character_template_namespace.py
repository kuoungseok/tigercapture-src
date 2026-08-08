"""Character one-click template action registrations."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def register_character_template_actions(registry: Any) -> None:
    any_object = {"type": "object", "additionalProperties": True}
    common_schema = schema_object(
        {
            "template_id": {"type": "string"},
            "asset_record": any_object,
            "path": {"type": "string"},
            "kind": {"type": "string"},
            "start_ms": {"type": "integer", "minimum": 0},
            "duration_ms": {"type": "integer", "minimum": 1},
            "track_id": {"type": "integer"},
            "clip_id": {"type": "integer"},
            "include_decorations": {"type": "boolean"},
        },
        required=("template_id",),
        additional_properties=True,
    )
    registry.register(
        ActionSpec(
            "character.template.list",
            "List one-click character timeline templates.",
            "character",
            mutating=False,
            requires_owner=False,
        ),
        lambda params, dry: _character_template_list(params, dry),
    )
    registry.register(
        ActionSpec(
            "character.template.plan",
            "Build a one-click character timeline template plan.",
            "character",
            params_schema=common_schema,
            mutating=False,
            requires_owner=False,
        ),
        lambda params, dry: _character_template_plan(params, dry),
    )
    registry.register(
        ActionSpec(
            "character.template.apply",
            "Apply a one-click character timeline template through registered actions.",
            "character",
            params_schema=common_schema,
            mutating=True,
            requires_owner=True,
            undo_label="Apply character template",
        ),
        lambda params, dry: _character_template_apply(registry, params, dry),
    )


def _character_template_list(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    from app.character_one_click_templates import character_one_click_templates

    templates = character_one_click_templates()
    return ok_result(
        "character.template.list",
        {"templates": templates, "count": len(templates)},
        dry_run=bool(dry_run),
        changed=False,
    )


def _character_template_plan(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        plan = _build_plan(params)
    except Exception as exc:
        return error_result("character.template.plan", str(exc), dry_run=dry_run)
    return ok_result(
        "character.template.plan",
        plan,
        warnings=list(plan.get("warnings") or ()),
        dry_run=bool(dry_run),
        changed=False,
    )


def _character_template_apply(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        plan = _build_plan(params)
    except Exception as exc:
        return error_result("character.template.apply", str(exc), dry_run=dry_run)
    warnings = list(plan.get("warnings") or [])
    if dry_run:
        return ok_result(
            "character.template.apply",
            {"would_apply": True, "plan": plan},
            warnings=warnings,
            dry_run=True,
            changed=False,
        )

    results: list[dict[str, Any]] = []
    changed = False
    for step in list(plan.get("steps") or []):
        if not isinstance(step, Mapping):
            continue
        action = str(step.get("action") or "").strip()
        if not action:
            continue
        if not bool(step.get("executable", True)):
            if not bool(step.get("optional", False)):
                return error_result(
                    "character.template.apply",
                    str(step.get("reason") or "required character template step is not executable"),
                    result={"plan": plan, "results": results, "blocked_step": dict(step)},
                    warnings=warnings,
                    changed=changed,
                )
            results.append({"skipped": True, "reason": str(step.get("reason") or ""), "step": dict(step)})
            continue
        result = registry.execute_action(action, step.get("params") if isinstance(step.get("params"), Mapping) else {})
        data = result.to_dict()
        data["step"] = {
            "role": str(step.get("role") or ""),
            "label": str(step.get("label") or ""),
            "optional": bool(step.get("optional", False)),
        }
        results.append(data)
        warnings.extend(str(item) for item in data.get("warnings") or [])
        if bool(data.get("changed")):
            changed = True
        if not data.get("ok") and not bool(step.get("optional", False)):
            return error_result(
                "character.template.apply",
                str(data.get("error") or f"{action} failed"),
                result={"plan": plan, "results": results},
                warnings=warnings,
                changed=changed,
            )

    owner = getattr(registry, "owner", None)
    register = getattr(owner, "_register_change", None)
    if changed and callable(register):
        try:
            register(f"Character template: {plan.get('template', {}).get('name', '')}")
        except Exception:
            pass
    refresh = getattr(owner, "_refresh_player_tracks", None)
    if changed and callable(refresh):
        try:
            refresh()
        except Exception:
            pass
    return ok_result(
        "character.template.apply",
        {"plan": plan, "results": results, "applied_count": sum(1 for row in results if row.get("ok"))},
        warnings=warnings,
        changed=changed,
    )


def _build_plan(params: Mapping[str, Any]) -> dict[str, Any]:
    from app.character_one_click_templates import build_character_one_click_template_plan

    return build_character_one_click_template_plan(
        str(params.get("template_id") or ""),
        params.get("asset_record") if isinstance(params.get("asset_record"), Mapping) else {},
        path=str(params.get("path") or ""),
        kind=str(params.get("kind") or ""),
        start_ms=_as_int(params.get("start_ms"), 0),
        duration_ms=_as_int(params.get("duration_ms"), 0) or None,
        track_id=_optional_int(params.get("track_id")),
        clip_id=_optional_int(params.get("clip_id")),
        include_decorations=bool(params.get("include_decorations", True)),
    )


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except Exception:
        return None


__all__ = ["register_character_template_actions"]
