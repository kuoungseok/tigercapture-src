"""Final Cut-style audition/take helpers.

An audition is stored as alternate source metadata on a normal VideoClip. Only
the active take is copied onto the clip's render-facing source fields, so
preview/export can keep using the existing clip path without a second hidden
timeline lane.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


AUDITIONS_SCHEMA = "tigerstudio.nle.auditions.v1"
AUDITION_COMPARE_SCHEMA = "tigerstudio.nle.audition_compare.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clips(track: Any) -> list[Any]:
    return [clip for clip in list(_attr(track, "clips", []) or []) if clip is not None]


def _path_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(Path(value))
    except Exception:
        return str(value)


def take_from_clip(clip: Any, *, take_id: str = "", label: str = "") -> dict[str, Any]:
    source_path = _path_text(_attr(clip, "source_path", ""))
    source_duration_ms = _int(_attr(clip, "source_duration_ms", 0), 0)
    source_in_ms = _int(_attr(clip, "source_in_ms", 0), 0)
    source_out_ms = _int(_attr(clip, "source_out_ms", 0), 0)
    if source_out_ms <= 0:
        source_out_ms = source_duration_ms
    generated_id = take_id or f"take_clip_{_int(_attr(clip, 'id', 0), 0)}"
    display = label or str(_attr(clip, "display_name", "") or Path(source_path).name or generated_id)
    return normalize_take(
        {
            "id": generated_id,
            "label": display,
            "source_path": source_path,
            "source_duration_ms": source_duration_ms,
            "source_in_ms": source_in_ms,
            "source_out_ms": source_out_ms,
            "speed": float(_attr(clip, "speed", 1.0) or 1.0),
        }
    )


def normalize_take(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = raw if isinstance(raw, Mapping) else {}
    take_id = str(raw.get("id") or raw.get("take_id") or "").strip() or "take"
    source_path = _path_text(raw.get("source_path", ""))
    duration = max(0, _int(raw.get("source_duration_ms", raw.get("duration_ms", 0)), 0))
    source_in = max(0, _int(raw.get("source_in_ms", 0), 0))
    source_out = max(0, _int(raw.get("source_out_ms", 0), 0))
    if source_out <= 0:
        source_out = duration
    if duration <= 0:
        duration = max(source_out, source_in)
    if source_out < source_in:
        source_out = source_in
    label = str(raw.get("label") or Path(source_path).name or take_id).strip()
    return {
        "id": take_id,
        "label": label,
        "source_path": source_path,
        "source_duration_ms": duration,
        "source_in_ms": source_in,
        "source_out_ms": source_out,
        "speed": float(raw.get("speed", 1.0) or 1.0),
    }


def next_take_id(existing: Sequence[Mapping[str, Any]] | None, *, prefix: str = "take") -> str:
    used = {str(row.get("id") or "") for row in (existing or []) if isinstance(row, Mapping)}
    idx = 1
    while f"{prefix}_{idx}" in used:
        idx += 1
    return f"{prefix}_{idx}"


def build_audition_status(tracks: Sequence[Any]) -> dict[str, Any]:
    auditions: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for track in tracks or []:
        tid = _int(_attr(track, "id", -1), -1)
        for clip in _clips(track):
            takes = [normalize_take(row) for row in list(_attr(clip, "audition_takes", []) or [])]
            if not takes and _attr(clip, "audition_group_id", None) is None:
                continue
            active = str(_attr(clip, "audition_active_take_id", "") or "").strip()
            take_ids = [str(row.get("id") or "") for row in takes]
            active_missing = bool(takes and active and active not in take_ids)
            if active_missing:
                issues.append(
                    {
                        "type": "active_take_missing",
                        "track_id": tid,
                        "clip_id": _int(_attr(clip, "id", 0), 0),
                        "active_take_id": active,
                    }
                )
            auditions.append(
                {
                    "track_id": tid,
                    "clip_id": _int(_attr(clip, "id", 0), 0),
                    "audition_group_id": _attr(clip, "audition_group_id", None),
                    "audition_name": str(_attr(clip, "audition_name", "") or ""),
                    "active_take_id": active,
                    "take_count": len(takes),
                    "take_ids": take_ids,
                    "active_take_missing": active_missing,
                    "takes": takes,
                }
            )
    return {
        "schema": AUDITIONS_SCHEMA,
        "ready": True,
        "audition_count": len(auditions),
        "take_count": sum(_int(row.get("take_count"), 0) for row in auditions),
        "issue_count": len(issues),
        "auditions": auditions,
        "issues": issues,
    }


def build_audition_compare_view(*, track_id: int, clip: Any) -> dict[str, Any]:
    takes = [normalize_take(row) for row in list(_attr(clip, "audition_takes", []) or [])]
    active = str(_attr(clip, "audition_active_take_id", "") or "").strip()
    take_ids = [str(row.get("id") or "") for row in takes]
    active_missing = bool(takes and active and active not in take_ids)
    clip_id = _int(_attr(clip, "id", 0), 0)
    clip_timeline_in = _int(_attr(clip, "timeline_in_ms", 0), 0)
    clip_duration = max(0, _int(_attr(clip, "source_out_ms", 0), 0) - _int(_attr(clip, "source_in_ms", 0), 0))
    rows: list[dict[str, Any]] = []
    for idx, take in enumerate(takes):
        take_id = str(take.get("id") or "")
        source_path = str(take.get("source_path") or "")
        take_duration = max(0, _int(take.get("source_out_ms"), 0) - _int(take.get("source_in_ms"), 0))
        rows.append(
            {
                "index": idx,
                "id": take_id,
                "label": str(take.get("label") or take_id),
                "source_name": Path(source_path).name if source_path else "",
                "source_path": source_path,
                "source_in_ms": _int(take.get("source_in_ms"), 0),
                "source_out_ms": _int(take.get("source_out_ms"), 0),
                "source_duration_ms": _int(take.get("source_duration_ms"), 0),
                "take_duration_ms": take_duration,
                "timeline_duration_delta_ms": take_duration - clip_duration,
                "speed": float(take.get("speed", 1.0) or 1.0),
                "active": take_id == active,
                "safe_to_switch": bool(take_id),
                "commands": {
                    "switch_action": "timeline.audition.switch_take",
                    "rename_action": "timeline.audition.rename_take",
                    "remove_action": "timeline.audition.remove_take",
                    "params": {"track_id": int(track_id), "clip_id": clip_id, "take_id": take_id},
                },
            }
        )
    return {
        "schema": AUDITION_COMPARE_SCHEMA,
        "ready": bool(takes),
        "track_id": int(track_id),
        "clip_id": clip_id,
        "timeline_in_ms": clip_timeline_in,
        "audition_group_id": _attr(clip, "audition_group_id", None),
        "audition_name": str(_attr(clip, "audition_name", "") or ""),
        "active_take_id": active,
        "active_take_missing": active_missing,
        "take_count": len(rows),
        "can_switch": len(rows) > 0,
        "can_rename": len(rows) > 0,
        "can_remove": len(rows) > 1,
        "takes": rows,
        "commands": {
            "status_action": "timeline.auditions.status",
            "compare_action": "timeline.audition.compare",
            "add_action": "timeline.audition.add_take",
        },
    }


def audition_contract_evidence(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    action_set = {str(action_id) for action_id in (action_ids or []) if str(action_id or "").strip()}
    required = {
        "timeline.auditions.status",
        "timeline.audition.compare",
        "timeline.audition.add_take",
        "timeline.audition.switch_take",
        "timeline.audition.rename_take",
        "timeline.audition.remove_take",
    }
    return {
        "schema": "tigerstudio.nle.audition_contract.v1",
        "ok": required <= action_set,
        "required_actions": sorted(required),
        "available_actions": sorted(required & action_set),
    }
