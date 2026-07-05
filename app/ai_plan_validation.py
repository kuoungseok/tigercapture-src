"""Validation and dry-run helpers for AI edit plans."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.ai_edit_apply import AI_SCRIPT_DESTRUCTIVE_CUT_TYPES, build_ai_script_apply_payload
from app.ai_edit_plan import EditPlan


@dataclass(frozen=True)
class AIPlanValidationResult:
    ok: bool
    blocked: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "blocked": list(self.blocked),
            "warnings": list(self.warnings),
            "dry_run": dict(self.dry_run),
        }


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(fallback)


def _timeline_duration(snapshot: dict[str, Any] | None) -> int:
    if not snapshot:
        return 0
    return max(0, _int(snapshot.get("duration_ms", 0)))


def _locked_video_track_ids(snapshot: dict[str, Any] | None) -> set[int]:
    locks = (snapshot or {}).get("locks") or {}
    return {_int(row) for row in locks.get("locked_video_track_ids") or []}


def _has_any_timeline_media(snapshot: dict[str, Any] | None) -> bool:
    summary = (snapshot or {}).get("summary") or {}
    return bool(
        _int(summary.get("video_clip_count", 0))
        or _int(summary.get("audio_clip_count", 0))
        or (snapshot or {}).get("video_tracks")
        or (snapshot or {}).get("audio_tracks")
    )


def _operation_time_warnings(plan: EditPlan, snapshot: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    blocked: list[str] = []
    warnings: list[str] = []
    duration_ms = _timeline_duration(snapshot)
    has_media = _has_any_timeline_media(snapshot)
    for operation in plan.operations:
        if operation.start_ms is None or operation.end_ms is None:
            continue
        start = _int(operation.start_ms)
        end = _int(operation.end_ms)
        if end <= start:
            blocked.append(f"{operation.id}:invalid_time_range")
        if duration_ms and start > duration_ms:
            blocked.append(f"{operation.id}:starts_after_project_end")
        if duration_ms and end > duration_ms:
            warnings.append(f"{operation.id}:ends_after_project_end")
        if operation.type in AI_SCRIPT_DESTRUCTIVE_CUT_TYPES and not has_media:
            warnings.append(f"{operation.id}:cut_has_no_timeline_media")
    return blocked, warnings


def validate_edit_plan_for_snapshot(
    plan: EditPlan,
    snapshot: dict[str, Any] | None,
    *,
    operation_ids: Sequence[str] | None = None,
    destructive_apply: bool = False,
) -> AIPlanValidationResult:
    """Validate a plan against read-only project state.

    ``destructive_apply`` should be true only for explicit materialization such
    as "apply reviewed cuts". Normal apply can stage cut intents safely.
    """
    blocked: list[str] = []
    warnings: list[str] = []
    if int(getattr(plan, "schema_version", 1) or 1) != 1:
        blocked.append("unsupported_schema_version")
    if not getattr(plan, "operations", None):
        blocked.append("plan_has_no_operations")
    selected = set(str(item) for item in operation_ids) if operation_ids is not None else None
    selected_ops = [op for op in plan.operations if selected is None or op.id in selected]
    if selected is not None and not selected_ops:
        blocked.append("no_selected_operations")
    if selected is not None:
        missing = sorted(selected - {op.id for op in plan.operations})
        warnings.extend(f"unknown_operation_id:{op_id}" for op_id in missing)
    time_blocked, time_warnings = _operation_time_warnings(
        plan if selected is None else type(plan)(
            id=plan.id,
            intent=plan.intent,
            summary=plan.summary,
            operations=tuple(selected_ops),
            warnings=plan.warnings,
            requires_review=plan.requires_review,
            review_cards=(),
            quality_score=plan.quality_score,
            metadata=plan.metadata,
            schema_version=plan.schema_version,
            provider=plan.provider,
        ),
        snapshot,
    )
    blocked.extend(time_blocked)
    warnings.extend(time_warnings)

    destructive_ops = [op for op in selected_ops if op.type in AI_SCRIPT_DESTRUCTIVE_CUT_TYPES]
    if destructive_ops and destructive_apply:
        locked_tracks = _locked_video_track_ids(snapshot)
        if locked_tracks:
            blocked.append(f"locked_video_tracks:{','.join(str(i) for i in sorted(locked_tracks))}")
    elif destructive_ops:
        warnings.append("destructive_operations_are_review_only")

    payload_result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
    dry_run = {
        "plan_id": plan.id,
        "provider": getattr(plan, "provider", "rule_based"),
        "operation_count": len(selected_ops),
        "destructive_operation_count": len(destructive_ops),
        "payload_counts": dict(payload_result.counts),
        "payload_ok": bool(payload_result.ok),
        "snapshot_hash": str((snapshot or {}).get("snapshot_hash") or ""),
    }
    warnings.extend(payload_result.warnings)
    return AIPlanValidationResult(
        ok=not blocked,
        blocked=sorted(dict.fromkeys(blocked)),
        warnings=sorted(dict.fromkeys(warnings)),
        dry_run=dry_run,
    )
