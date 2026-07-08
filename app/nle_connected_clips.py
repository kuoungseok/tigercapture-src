"""Final Cut-style connected clip and role-color helpers.

This module is deliberately pure: it reads track/clip-like objects and returns
JSON-friendly contracts that UI, QA, and Python Actions can share.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
import re


CONNECTED_CLIPS_SCHEMA = "tigerstudio.nle.connected_clips.v1"


ROLE_COLORS: dict[str, str] = {
    "primary": "#F6A72A",
    "b_roll": "#5EA2FF",
    "overlay": "#8D7CFF",
    "title": "#F35DB5",
    "dialog": "#65D6A6",
    "music": "#B885FF",
    "sfx": "#FF8A53",
    "actor": "#63D9E9",
    "ar_pbr": "#B6D94E",
    "performance": "#7A879B",
    "compound": "#9EA7B7",
}

ROLE_LABELS: dict[str, str] = {
    "primary": "Primary",
    "b_roll": "B-roll",
    "overlay": "Overlay",
    "title": "Title",
    "dialog": "Dialog",
    "music": "Music",
    "sfx": "SFX",
    "actor": "Actor",
    "ar_pbr": "AR/PBR",
    "performance": "Performance",
    "compound": "Compound",
}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _track_id(track: Any) -> int:
    return _int(_attr(track, "id", -1), -1)


def _clip_id(clip: Any) -> int:
    return _int(_attr(clip, "id", -1), -1)


def _clip_start(clip: Any) -> int:
    return _int(_attr(clip, "timeline_in_ms", 0), 0)


def _clip_end(clip: Any) -> int:
    explicit = _attr(clip, "timeline_out_ms", None)
    if explicit is not None:
        return _int(explicit, _clip_start(clip))
    source_out = _int(_attr(clip, "source_out_ms", 0), 0)
    source_in = _int(_attr(clip, "source_in_ms", 0), 0)
    duration = max(0, source_out - source_in)
    if duration <= 0:
        duration = _int(_attr(clip, "source_duration_ms", 0), 0)
    return _clip_start(clip) + duration


def _clips(track: Any) -> list[Any]:
    return [clip for clip in list(_attr(track, "clips", []) or []) if clip is not None]


def normalize_clip_role(role: str | None, *, fallback: str = "primary") -> str:
    text = str(role or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "broll": "b_roll",
        "b": "b_roll",
        "a_roll": "primary",
        "main": "primary",
        "video": "primary",
        "caption": "title",
        "subtitle": "title",
        "voice": "dialog",
        "voiceover": "dialog",
        "sound": "sfx",
        "fx": "sfx",
        "ar": "ar_pbr",
        "pbr": "ar_pbr",
        "vtuber": "actor",
        "live2d": "actor",
        "spine": "actor",
        "mmd": "actor",
        "perf": "performance",
        "performance_source": "performance",
    }
    text = aliases.get(text, text)
    if text in ROLE_COLORS:
        return text
    return normalize_clip_role(fallback, fallback="primary") if fallback != text else "primary"


def role_color_for(role: str | None, override: str | None = None) -> str:
    override_text = str(override or "").strip()
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", override_text):
        return override_text.upper()
    return ROLE_COLORS.get(normalize_clip_role(role), ROLE_COLORS["primary"])


def infer_clip_role(track: Any, clip: Any) -> str:
    explicit = str(_attr(clip, "clip_role", "") or "").strip()
    if explicit:
        return normalize_clip_role(explicit)
    track_type = str(_attr(clip, "track_type", "") or _attr(track, "track_type", "") or "").casefold()
    source_path = str(_attr(clip, "source_path", "") or "").casefold()
    if bool(_attr(clip, "performance_source", False)) or "performance" in track_type:
        return "performance"
    if bool(_attr(clip, "is_nested_sequence", False)) or _attr(clip, "compound_group_id", None) is not None:
        return "compound"
    if "actor" in track_type or any(token in source_path for token in (".model3.json", ".skel", ".vrm", ".pmx", ".pmd")):
        return "actor"
    if any(token in track_type for token in ("title", "text", "caption")):
        return "title"
    if _attr(clip, "connected_parent_clip_id", None) is not None:
        return "b_roll"
    return "primary"


def build_role_color_status(tracks: Sequence[Any]) -> dict[str, Any]:
    counts = {role: 0 for role in ROLE_COLORS}
    clips: list[dict[str, Any]] = []
    for track in tracks or []:
        tid = _track_id(track)
        for clip in _clips(track):
            role = infer_clip_role(track, clip)
            counts[role] = counts.get(role, 0) + 1
            clips.append(
                {
                    "track_id": tid,
                    "clip_id": _clip_id(clip),
                    "role": role,
                    "label": ROLE_LABELS.get(role, role),
                    "color": role_color_for(role, _attr(clip, "role_color", "")),
                }
            )
    return {
        "schema": "tigerstudio.nle.role_colors.v1",
        "ready": True,
        "palette": {
            role: {"label": ROLE_LABELS.get(role, role), "color": color}
            for role, color in ROLE_COLORS.items()
        },
        "role_counts": {role: count for role, count in counts.items() if count},
        "clip_count": len(clips),
        "clips": clips,
    }


def build_connected_clip_status(tracks: Sequence[Any]) -> dict[str, Any]:
    parent_index: dict[tuple[int, int], Any] = {}
    track_index: dict[int, Any] = {}
    for track in tracks or []:
        tid = _track_id(track)
        track_index[tid] = track
        for clip in _clips(track):
            parent_index[(tid, _clip_id(clip))] = clip

    connected: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for track in tracks or []:
        child_tid = _track_id(track)
        for clip in _clips(track):
            parent_clip_id = _attr(clip, "connected_parent_clip_id", None)
            parent_track_id = _attr(clip, "connected_parent_track_id", None)
            if parent_clip_id is None and parent_track_id is None:
                continue
            child_id = _clip_id(clip)
            parent_tid = _int(parent_track_id, -1)
            parent_id = _int(parent_clip_id, -1)
            parent = parent_index.get((parent_tid, parent_id))
            offset = _int(_attr(clip, "connected_offset_ms", 0), 0)
            current = _clip_start(clip)
            expected = _clip_start(parent) + offset if parent is not None else None
            missing = parent is None
            in_sync = (not missing) and expected == current
            row = {
                "child_track_id": child_tid,
                "child_clip_id": child_id,
                "parent_track_id": parent_tid,
                "parent_clip_id": parent_id,
                "connected_offset_ms": offset,
                "current_start_ms": current,
                "expected_start_ms": expected,
                "in_sync": bool(in_sync),
                "missing_parent": bool(missing),
                "role": infer_clip_role(track, clip),
                "role_color": role_color_for(infer_clip_role(track, clip), _attr(clip, "role_color", "")),
            }
            connected.append(row)
            if missing:
                issues.append({"type": "missing_parent", **row})
            elif not in_sync:
                issues.append({"type": "offset_mismatch", **row})

    return {
        "schema": CONNECTED_CLIPS_SCHEMA,
        "ready": True,
        "track_count": len(track_index),
        "connected_count": len(connected),
        "issue_count": len(issues),
        "connected": connected,
        "issues": issues,
        "role_colors": build_role_color_status(tracks),
    }


def connected_clip_contract_evidence(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    action_set = {str(action_id) for action_id in (action_ids or []) if str(action_id or "").strip()}
    required = {
        "timeline.connected_clips.status",
        "timeline.connected_clips.connect",
        "timeline.clip_role.set",
        "timeline.role_colors.status",
    }
    return {
        "schema": "tigerstudio.nle.connected_clip_contract.v1",
        "ok": required <= action_set,
        "required_actions": sorted(required),
        "available_actions": sorted(required & action_set),
        "palette": {
            role: {"label": ROLE_LABELS.get(role, role), "color": color}
            for role, color in ROLE_COLORS.items()
        },
    }
