"""Safe MVP apply helpers for AI Script Edit plans.

This module does not call AI providers, execute code, or mutate timelines by
itself. It converts validated :class:`EditPlan` operations into deterministic
payloads that editor adapters can review and apply through normal project APIs.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any

from app.ai_edit_plan import EditOperation, EditPlan


AI_SCRIPT_SOURCE = "ai_script_edit"
AI_SCRIPT_DESTRUCTIVE_CUT_TYPES = {
    "delete_time_range",
    "ripple_cut_text_range",
    "remove_silence",
}


@dataclass
class AIScriptApplyResult:
    ok: bool
    payload: dict[str, Any]
    operations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    applied: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": bool(self.ok),
            "payload": deepcopy(self.payload),
            "operations": list(self.operations),
            "warnings": list(self.warnings),
            "counts": dict(self.counts),
            "applied": dict(self.applied),
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else []


def _int_ms(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return max(0, int(fallback))


def _operation_selection(plan: EditPlan, operation_ids: Sequence[str] | None) -> tuple[list[EditOperation], list[str]]:
    if operation_ids is None:
        return list(plan.operations), []
    wanted = {str(item) for item in operation_ids}
    operations = [operation for operation in plan.operations if operation.id in wanted]
    missing = sorted(wanted - {operation.id for operation in plan.operations})
    warnings = [f"unknown_operation_id:{item}" for item in missing]
    if not operations:
        warnings.append("no_selected_operations")
    return operations, warnings


def operation_ids_for_review_cards(plan: EditPlan, card_ids: Sequence[str] | None) -> list[str]:
    """Resolve review-card ids to operation ids in stable plan order."""
    if not card_ids:
        return []
    wanted_cards = {str(item) for item in card_ids}
    wanted_ops: set[str] = set()
    for card in plan.review_cards:
        if card.id in wanted_cards:
            wanted_ops.update(card.operation_ids)
    return [operation.id for operation in plan.operations if operation.id in wanted_ops]


def _subtitle_rows_from_operation(plan: EditPlan, operation: EditOperation) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in _as_list(operation.params.get("rows")):
        row = _as_dict(raw)
        text = " ".join(str(row.get("text") or "").split())
        if not text:
            continue
        start_ms = _int_ms(row.get("start_ms"))
        end_ms = max(start_ms + 500, _int_ms(row.get("end_ms"), start_ms + 1800))
        style = _as_dict(row.get("style"))
        style_preset_id = str(
            row.get("style_preset_id")
            or operation.style_preset_id
            or style.get("preset_id")
            or "caption-capcut-word-pop"
        )
        style["preset_id"] = style_preset_id
        style.setdefault("source", AI_SCRIPT_SOURCE)
        style["ai_edit_plan_id"] = plan.id
        style["ai_edit_operation_id"] = operation.id
        if row.get("segment_id"):
            style["transcript_segment_id"] = str(row.get("segment_id"))
        rows.append(
            {
                "text": text,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "show_box": bool(row.get("show_box", operation.params.get("show_box", True))),
                "style": style,
                "style_preset_id": style_preset_id,
                "source": AI_SCRIPT_SOURCE,
                "operation_id": operation.id,
                "plan_id": plan.id,
                "metadata": _as_dict(row.get("metadata")),
            }
        )
    return rows


def _marker_payload(
    plan: EditPlan,
    operation: EditOperation,
    *,
    start_ms: int,
    end_ms: int | None = None,
    label: str = "",
    color: str = "#8A7CFF",
    marker_id: str = "",
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    marker = {
        "ms": _int_ms(start_ms),
        "color": str(color or "#8A7CFF"),
        "label": str(label or operation.text or operation.reason or operation.id),
        "id": str(marker_id or f"ai-script-{operation.id}"),
        "source": AI_SCRIPT_SOURCE,
        "operation_id": operation.id,
        "plan_id": plan.id,
    }
    if end_ms is not None:
        marker["end_ms"] = max(marker["ms"] + 1, _int_ms(end_ms, marker["ms"] + 1000))
    if operation.quality_score is not None:
        marker["score"] = int(operation.quality_score)
    if operation.reason:
        marker["reason"] = operation.reason
    marker.update(dict(extra or {}))
    return marker


def _markers_from_add_marker(plan: EditPlan, operation: EditOperation) -> list[dict[str, Any]]:
    params = _as_dict(operation.params)
    start_ms = _int_ms(params.get("ms", params.get("start_ms", operation.start_ms)))
    end_ms = params.get("end_ms", operation.end_ms)
    label = str(operation.text or params.get("label") or params.get("title") or operation.reason or "Marker")
    return [
        _marker_payload(
            plan,
            operation,
            start_ms=start_ms,
            end_ms=None if end_ms is None else _int_ms(end_ms, start_ms + 1),
            label=label,
            color=str(params.get("color") or "#8A7CFF"),
            marker_id=str(params.get("id") or f"ai-script-marker-{operation.id}"),
        )
    ]


def _markers_from_chapter_operation(plan: EditPlan, operation: EditOperation) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    params = _as_dict(operation.params)
    chapters = [_as_dict(row) for row in _as_list(params.get("chapters")) if isinstance(row, Mapping)]
    markers: list[dict[str, Any]] = []
    for idx, chapter in enumerate(chapters, start=1):
        start_ms = _int_ms(chapter.get("start_ms", chapter.get("ms", chapter.get("time_ms", 0))))
        title = str(chapter.get("title") or chapter.get("label") or f"Chapter {idx}")
        markers.append(
            _marker_payload(
                plan,
                operation,
                start_ms=start_ms,
                label=title,
                color=str(chapter.get("color") or params.get("color") or "#44C2FF"),
                marker_id=str(chapter.get("id") or f"ai-script-chapter-{idx:02d}-{operation.id}"),
                extra={"chapter_index": idx},
            )
        )
    if markers:
        return markers, []
    return [], [
        {
            "operation_id": operation.id,
            "plan_id": plan.id,
            "type": "chapter_marker_request",
            "params": deepcopy(params),
            "reason": operation.reason,
            "source": AI_SCRIPT_SOURCE,
        }
    ]


def _short_candidate_payload(plan: EditPlan, operation: EditOperation) -> tuple[dict[str, Any], dict[str, Any]]:
    params = _as_dict(operation.params)
    index = int(params.get("candidate_index", 0) or 0)
    start_ms = _int_ms(operation.start_ms)
    end_ms = max(start_ms + 1, _int_ms(operation.end_ms, start_ms + 1000))
    label = str(operation.text or params.get("label") or f"Short candidate {index or 1}")
    marker = _marker_payload(
        plan,
        operation,
        start_ms=start_ms,
        end_ms=end_ms,
        label=label,
        color=str(params.get("color") or "#FF6F61"),
        marker_id=str(params.get("id") or f"ai-script-short-{index or operation.id}"),
        extra={"candidate_index": index},
    )
    candidate = {
        "id": marker["id"],
        "operation_id": operation.id,
        "plan_id": plan.id,
        "label": label,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text": operation.text or "",
        "score": int(operation.quality_score or 0),
        "reason": operation.reason,
        "params": deepcopy(params),
        "source": AI_SCRIPT_SOURCE,
    }
    return marker, candidate


def _cut_intent_from_operation(plan: EditPlan, operation: EditOperation) -> dict[str, Any]:
    start_ms = _int_ms(operation.start_ms)
    end_ms = max(start_ms + 1, _int_ms(operation.end_ms, start_ms + 1))
    return {
        "id": f"ai-script-cut-{operation.id}",
        "operation_id": operation.id,
        "plan_id": plan.id,
        "type": operation.type,
        "target": operation.target,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "text": operation.text or "",
        "reason": operation.reason,
        "params": deepcopy(_as_dict(operation.params)),
        "source": AI_SCRIPT_SOURCE,
        "requires_review": True,
    }


def _render_job_from_operation(plan: EditPlan, operation: EditOperation) -> tuple[dict[str, Any], str | None]:
    params = _as_dict(operation.params)
    create_kwargs = _as_dict(params.get("create_kwargs"))
    start_ms = _int_ms(operation.start_ms, _int_ms(params.get("in_ms")))
    end_ms = max(start_ms + 1, _int_ms(operation.end_ms, _int_ms(params.get("out_ms"), start_ms + 1000)))
    create_kwargs.setdefault("label", str(params.get("label") or operation.text or params.get("variant") or "AI Script Edit"))
    create_kwargs.setdefault("in_ms", start_ms)
    create_kwargs.setdefault("out_ms", end_ms)
    create_kwargs.setdefault("format_id", str(params.get("format_id") or params.get("format") or "mp4"))
    create_kwargs.setdefault("quality_id", str(params.get("quality_id") or "high"))
    if params.get("out_path"):
        create_kwargs.setdefault("out_path", str(params.get("out_path")))
    if params.get("project_path"):
        create_kwargs.setdefault("project_path", str(params.get("project_path")))
    if params.get("source_path"):
        create_kwargs.setdefault("source_path", str(params.get("source_path")))
    job = {
        "source": AI_SCRIPT_SOURCE,
        "operation_id": operation.id,
        "plan_id": plan.id,
        "variant": str(params.get("variant") or create_kwargs.get("label") or "ai_script_edit"),
        "create_kwargs": create_kwargs,
        "ai_script": {
            "plan_id": plan.id,
            "operation_id": operation.id,
            "reason": operation.reason,
        },
    }
    warning = None
    if not str(create_kwargs.get("out_path") or "").strip():
        warning = f"render_queue_job_sidecar_only:{operation.id}:missing_out_path"
    return job, warning


def build_ai_script_apply_payload(
    plan: EditPlan,
    *,
    operation_ids: Sequence[str] | None = None,
) -> AIScriptApplyResult:
    """Convert selected plan operations to safe editor payloads.

    Destructive timeline edits are returned as ``cut_intents`` only. They are
    not applied here and must be reviewed by an editor-specific adapter.
    """
    operations, selection_warnings = _operation_selection(plan, operation_ids)
    warnings: list[str] = list(selection_warnings)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "source": AI_SCRIPT_SOURCE,
        "plan_id": plan.id,
        "plan_provider": str(getattr(plan, "provider", "rule_based") or "rule_based"),
        "plan_intent": plan.intent,
        "plan_summary": plan.summary,
        "subtitle_rows": [],
        "timeline_markers": [],
        "short_candidates": [],
        "cut_intents": [],
        "render_queue_jobs": [],
        "sidecars": [],
        "operation_ids": [operation.id for operation in operations],
    }
    operations_done: list[str] = []

    for operation in operations:
        if operation.type == "create_subtitles":
            rows = _subtitle_rows_from_operation(plan, operation)
            payload["subtitle_rows"].extend(rows)
            operations_done.append(f"prepared {len(rows)} subtitle row(s) from {operation.id}")
        elif operation.type == "add_marker":
            markers = _markers_from_add_marker(plan, operation)
            payload["timeline_markers"].extend(markers)
            operations_done.append(f"prepared {len(markers)} marker(s) from {operation.id}")
        elif operation.type == "add_chapter_markers":
            markers, sidecars = _markers_from_chapter_operation(plan, operation)
            payload["timeline_markers"].extend(markers)
            payload["sidecars"].extend(sidecars)
            operations_done.append(f"prepared {len(markers)} chapter marker(s) from {operation.id}")
            if sidecars:
                warnings.append(f"chapter_markers_sidecar_only:{operation.id}")
        elif operation.type == "create_short_candidate":
            marker, candidate = _short_candidate_payload(plan, operation)
            payload["timeline_markers"].append(marker)
            payload["short_candidates"].append(candidate)
            operations_done.append(f"prepared short candidate from {operation.id}")
        elif operation.type in {"delete_time_range", "ripple_cut_text_range", "remove_silence", "keep_time_range"}:
            payload["cut_intents"].append(_cut_intent_from_operation(plan, operation))
            warnings.append(f"timeline_cut_review_only:{operation.id}")
            operations_done.append(f"staged review-only cut intent from {operation.id}")
        elif operation.type == "add_render_queue_job":
            job, warning = _render_job_from_operation(plan, operation)
            payload["render_queue_jobs"].append(job)
            if warning:
                warnings.append(warning)
            operations_done.append(f"prepared render queue job from {operation.id}")
        else:
            payload["sidecars"].append(
                {
                    "operation_id": operation.id,
                    "plan_id": plan.id,
                    "type": operation.type,
                    "target": operation.target,
                    "start_ms": operation.start_ms,
                    "end_ms": operation.end_ms,
                    "text": operation.text,
                    "params": deepcopy(_as_dict(operation.params)),
                    "metadata": deepcopy(_as_dict(operation.metadata)),
                    "reason": operation.reason,
                    "source": AI_SCRIPT_SOURCE,
                    "requires_review": True,
                }
            )
            warnings.append(f"operation_sidecar_only:{operation.id}:{operation.type}")
            operations_done.append(f"stored sidecar for {operation.id}")

    counts = {
        "subtitle_rows": len(payload["subtitle_rows"]),
        "timeline_markers": len(payload["timeline_markers"]),
        "short_candidates": len(payload["short_candidates"]),
        "cut_intents": len(payload["cut_intents"]),
        "render_queue_jobs": len(payload["render_queue_jobs"]),
        "sidecars": len(payload["sidecars"]),
    }
    ok = any(counts.values()) and not ("no_selected_operations" in warnings and len(operations) == 0)
    return AIScriptApplyResult(
        ok=ok,
        payload=payload,
        operations=operations_done,
        warnings=warnings,
        counts=counts,
    )


def apply_ai_script_plan_to_adapter(
    plan: EditPlan,
    adapter: Any,
    *,
    operation_ids: Sequence[str] | None = None,
) -> AIScriptApplyResult:
    """Apply safe payload sections to an explicit editor adapter.

    Supported adapter methods are optional and narrow:
    ``add_subtitle_rows(rows)``, ``add_timeline_markers(markers)``,
    ``stage_render_queue_jobs(jobs)``, and ``store_ai_script_sidecar(payload)``.
    Cut intents are only passed to ``stage_cut_intents(intents)`` when present.
    """
    result = build_ai_script_apply_payload(plan, operation_ids=operation_ids)
    payload = result.payload
    applied = {
        "subtitle_rows": 0,
        "timeline_markers": 0,
        "cut_intents": 0,
        "render_queue_jobs": 0,
        "sidecars": 0,
    }
    calls = (
        ("subtitle_rows", "add_subtitle_rows"),
        ("timeline_markers", "add_timeline_markers"),
        ("cut_intents", "stage_cut_intents"),
        ("render_queue_jobs", "stage_render_queue_jobs"),
    )
    for key, method_name in calls:
        rows = list(payload.get(key) or [])
        if not rows:
            continue
        method = getattr(adapter, method_name, None)
        if not callable(method):
            result.warnings.append(f"adapter_missing:{method_name}")
            continue
        count = method(rows)
        try:
            applied[key] = int(count)
        except Exception:
            applied[key] = len(rows)
    sidecar_method = getattr(adapter, "store_ai_script_sidecar", None)
    if callable(sidecar_method):
        sidecar_method(payload)
        applied["sidecars"] = len(payload.get("sidecars") or [])
    elif payload.get("sidecars") or payload.get("short_candidates") or payload.get("cut_intents"):
        result.warnings.append("adapter_missing:store_ai_script_sidecar")
    result.applied = applied
    result.ok = result.ok or any(value > 0 for value in applied.values())
    return result


def _cut_ranges_from_intents(cut_intents: Sequence[Mapping[str, Any]]) -> tuple[list[tuple[int, int, str]], list[str]]:
    ranges: list[tuple[int, int, str]] = []
    warnings: list[str] = []
    for idx, raw in enumerate(cut_intents or []):
        intent = _as_dict(raw)
        op_type = str(intent.get("type") or "").strip()
        if op_type and op_type not in AI_SCRIPT_DESTRUCTIVE_CUT_TYPES:
            warnings.append(f"unsupported_cut_intent:{intent.get('id') or idx}:{op_type}")
            continue
        start_ms = _int_ms(intent.get("start_ms"))
        end_ms = _int_ms(intent.get("end_ms"), start_ms + 1)
        if end_ms <= start_ms:
            warnings.append(f"invalid_cut_range:{intent.get('id') or idx}")
            continue
        ranges.append((start_ms, end_ms, str(intent.get("id") or idx)))
    ranges.sort(key=lambda item: (item[0], item[1]))
    merged: list[tuple[int, int, str]] = []
    for start_ms, end_ms, cut_id in ranges:
        if not merged or start_ms > merged[-1][1]:
            merged.append((start_ms, end_ms, cut_id))
            continue
        prev_start, prev_end, prev_id = merged[-1]
        merged[-1] = (prev_start, max(prev_end, end_ms), f"{prev_id}+{cut_id}")
    return merged, warnings


def _video_track_range_affects(clips: Sequence[Any], start_ms: int, end_ms: int) -> bool:
    for clip in clips or []:
        try:
            clip_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
            clip_end = int(getattr(clip, "timeline_out_ms", clip_start) or clip_start)
        except Exception:
            continue
        if clip_end > start_ms and clip_start < end_ms:
            return True
        if clip_start >= end_ms:
            return True
    return False


def _audio_track_range_affects(clips: Sequence[Any], start_ms: int, end_ms: int) -> bool:
    for clip in clips or []:
        try:
            clip_start = int(getattr(clip, "offset_ms", 0) or 0)
            clip_end = clip_start + int(getattr(clip, "effective_length_ms", 0) or 0)
        except Exception:
            continue
        if clip_end > start_ms and clip_start < end_ms:
            return True
        if clip_start >= end_ms:
            return True
    return False


def _delete_time_range_from_video_clips(clips: Sequence[Any], start_ms: int, end_ms: int) -> tuple[list[Any], bool, int]:
    from app.timeline_model import split_clips_at_project_ms

    start_ms = max(0, int(start_ms))
    end_ms = max(start_ms + 1, int(end_ms))
    duration_ms = end_ms - start_ms
    split = split_clips_at_project_ms(list(clips or []), start_ms)
    split = split_clips_at_project_ms(split, end_ms)
    changed = False
    out: list[Any] = []
    removed = 0
    for clip in split:
        clip_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        clip_end = int(getattr(clip, "timeline_out_ms", clip_start) or clip_start)
        if clip_start >= start_ms and clip_end <= end_ms:
            removed += 1
            changed = True
            continue
        if clip_start >= end_ms:
            out.append(replace(clip, timeline_in_ms=clip_start - duration_ms))
            changed = True
        else:
            out.append(clip)
    out.sort(key=lambda clip: int(getattr(clip, "timeline_in_ms", 0) or 0))
    return out, changed, removed


def _split_audio_clips_at_project_ms(clips: Sequence[Any], project_ms: int) -> list[Any]:
    project_ms = max(0, int(project_ms))
    source = list(clips or [])
    next_id = max((int(getattr(clip, "id", 0) or 0) for clip in source), default=0) + 1
    out: list[Any] = []
    for clip in source:
        clip_start = int(getattr(clip, "offset_ms", 0) or 0)
        length = int(getattr(clip, "effective_length_ms", 0) or 0)
        clip_end = clip_start + length
        if clip_start < project_ms < clip_end:
            split_source = int(getattr(clip, "trim_start_ms", 0) or 0) + (project_ms - clip_start)
            source_end = int(getattr(clip, "effective_trim_end_ms", split_source) or split_source)
            left = replace(clip, trim_end_ms=split_source)
            right = replace(
                clip,
                id=next_id,
                offset_ms=project_ms,
                trim_start_ms=split_source,
                trim_end_ms=source_end,
                fade_in_ms=0,
            )
            next_id += 1
            if int(getattr(left, "effective_length_ms", 0) or 0) > 0:
                out.append(left)
            if int(getattr(right, "effective_length_ms", 0) or 0) > 0:
                out.append(right)
        else:
            out.append(clip)
    out.sort(key=lambda clip: int(getattr(clip, "offset_ms", 0) or 0))
    return out


def _delete_time_range_from_audio_clips(clips: Sequence[Any], start_ms: int, end_ms: int) -> tuple[list[Any], bool, int]:
    start_ms = max(0, int(start_ms))
    end_ms = max(start_ms + 1, int(end_ms))
    duration_ms = end_ms - start_ms
    split = _split_audio_clips_at_project_ms(clips, start_ms)
    split = _split_audio_clips_at_project_ms(split, end_ms)
    changed = False
    removed = 0
    out: list[Any] = []
    for clip in split:
        clip_start = int(getattr(clip, "offset_ms", 0) or 0)
        clip_end = clip_start + int(getattr(clip, "effective_length_ms", 0) or 0)
        if clip_start >= start_ms and clip_end <= end_ms:
            removed += 1
            changed = True
            continue
        if clip_start >= end_ms:
            out.append(replace(clip, offset_ms=clip_start - duration_ms))
            changed = True
        else:
            out.append(clip)
    out.sort(key=lambda clip: int(getattr(clip, "offset_ms", 0) or 0))
    return out, changed, removed


def apply_ai_script_cut_intents_to_tracks(
    video_tracks: Sequence[Any],
    audio_tracks: Sequence[Any] | None,
    cut_intents: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Apply reviewed AI Script cut ranges as global ripple deletes.

    The source plan remains review-only. This helper is the explicit materialize
    step used by the editor after the user clicks the destructive apply button.
    Each original intent time is adjusted by the cumulative duration already
    removed, so multiple cuts from one plan stay aligned to the original
    transcript timing.
    """
    ranges, warnings = _cut_ranges_from_intents(cut_intents)
    video_changed = 0
    audio_changed = 0
    video_segments_removed = 0
    audio_segments_removed = 0
    applied_ranges: list[dict[str, Any]] = []
    cumulative_removed = 0
    vtracks = list(video_tracks or [])
    atracks = list(audio_tracks or [])
    for original_start, original_end, cut_id in ranges:
        start_ms = max(0, original_start - cumulative_removed)
        end_ms = max(start_ms + 1, original_end - cumulative_removed)
        affects = any(
            _video_track_range_affects(getattr(track, "clips", []) or [], start_ms, end_ms)
            for track in vtracks
        ) or any(
            _audio_track_range_affects(getattr(track, "clips", []) or [], start_ms, end_ms)
            for track in atracks
        )
        if not affects:
            warnings.append(f"cut_range_no_timeline_overlap:{cut_id}")
            continue
        for track in vtracks:
            clips = list(getattr(track, "clips", []) or [])
            new_clips, changed, removed = _delete_time_range_from_video_clips(clips, start_ms, end_ms)
            if changed:
                track.clips = new_clips
                try:
                    track.clips_explicit = True
                except Exception:
                    pass
                video_changed += 1
                video_segments_removed += int(removed)
        for track in atracks:
            clips = list(getattr(track, "clips", []) or [])
            new_clips, changed, removed = _delete_time_range_from_audio_clips(clips, start_ms, end_ms)
            if changed:
                track.clips = new_clips
                audio_changed += 1
                audio_segments_removed += int(removed)
        removed_ms = end_ms - start_ms
        cumulative_removed += removed_ms
        applied_ranges.append(
            {
                "id": cut_id,
                "original_start_ms": original_start,
                "original_end_ms": original_end,
                "applied_start_ms": start_ms,
                "applied_end_ms": end_ms,
                "removed_ms": removed_ms,
            }
        )
    return {
        "ok": bool(applied_ranges),
        "applied_ranges": applied_ranges,
        "warnings": warnings,
        "video_tracks_changed": video_changed,
        "audio_tracks_changed": audio_changed,
        "video_segments_removed": video_segments_removed,
        "audio_segments_removed": audio_segments_removed,
        "removed_ms": sum(int(row.get("removed_ms", 0) or 0) for row in applied_ranges),
    }
