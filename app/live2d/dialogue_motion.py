"""Natural Live2D motion defaults for generated dialogue takes.

AI dialogue generation should not leave a character frozen in a static rig
pose.  This module adds a light, deterministic acting layer that works even
when a model has no authored idle motion, while preferring real model motions
when they are available.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
import copy
import json
import math


DIALOGUE_MOTION_SCHEMA = "tigerstudio.live2d.dialogue_motion.v1"
AUTHORED_DIALOGUE_MOTION_STORYBOARD_SCHEMA = "tigerstudio.live2d.authored_dialogue_motion_storyboard.v1"


BODY_MOTION_PARAMS: tuple[str, ...] = (
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamBodyAngleX",
    "ParamBodyAngleY",
    "ParamBodyAngleZ",
    "ParamBodyUpper",
    "ParamBustY",
    "ParamBreath",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamArmLA",
    "ParamArmRA",
    "ParamArmLB",
    "ParamArmRB",
    "ParamHandAngleL",
    "ParamHandAngleR",
    "ParamHandChangeR",
    "ParamHandDhangeL",
    "ParamFaceForm",
    "ParamBrowLForm",
    "ParamBrowRForm",
    "ParamBrowLAngle",
    "ParamBrowRAngle",
    "ParamEyeLSmile",
    "ParamEyeRSmile",
)


GESTURE_PRESETS: tuple[dict[str, Any], ...] = (
    {
        "id": "greet",
        "label": "Greet",
        "params": {
            "ParamArmRA": 7.2,
            "ParamArmRB": 6.0,
            "ParamHandAngleR": 5.5,
            "ParamHandChangeR": 1.0,
            "ParamBodyAngleX": -2.4,
            "ParamAngleX": -7.2,
            "ParamFaceForm": 0.35,
            "ParamEyeLSmile": 0.45,
            "ParamEyeRSmile": 0.45,
        },
    },
    {
        "id": "explain",
        "label": "Explain",
        "params": {
            "ParamArmLA": 5.8,
            "ParamArmRA": 5.0,
            "ParamArmLB": 4.8,
            "ParamArmRB": 3.6,
            "ParamHandAngleL": 3.6,
            "ParamHandAngleR": 2.4,
            "ParamBodyUpper": 4.8,
            "ParamAngleX": 4.2,
            "ParamAngleY": 4.0,
            "ParamBrowLForm": 0.35,
            "ParamBrowRForm": 0.35,
        },
    },
    {
        "id": "emphasize",
        "label": "Emphasize",
        "params": {
            "ParamArmLA": 7.0,
            "ParamArmRA": 7.4,
            "ParamArmLB": 6.4,
            "ParamArmRB": 5.8,
            "ParamHandAngleL": -0.6,
            "ParamHandAngleR": -0.4,
            "ParamBodyUpper": 5.8,
            "ParamBodyAngleY": 2.2,
            "ParamAngleX": -4.6,
            "ParamAngleY": 5.5,
            "ParamBrowLAngle": 0.6,
            "ParamBrowRAngle": 0.6,
        },
    },
    {
        "id": "nod",
        "label": "Nod",
        "params": {
            "ParamAngleY": -6.0,
            "ParamAngleZ": 2.8,
            "ParamBodyAngleZ": -1.8,
            "ParamBodyUpper": 3.2,
            "ParamArmLA": 3.8,
            "ParamArmRA": 4.0,
            "ParamBrowLForm": -0.25,
            "ParamBrowRForm": -0.25,
        },
    },
    {
        "id": "settle",
        "label": "Settle",
        "params": {
            "ParamArmLA": 2.4,
            "ParamArmRA": 2.6,
            "ParamArmLB": 2.4,
            "ParamArmRB": 2.6,
            "ParamHandAngleL": 0.0,
            "ParamHandAngleR": 0.0,
            "ParamBodyUpper": 2.0,
            "ParamAngleX": 0.0,
            "ParamAngleY": 0.0,
            "ParamFaceForm": 0.15,
        },
    },
)


MOTION_INTENT_HINTS: dict[str, tuple[str, ...]] = {
    "greet": ("greet", "hello", "hi", "wave", "hand", "tapbody", "tap_body", "tap"),
    "explain": ("explain", "talk", "speak", "body", "gesture", "tapbody", "tap_body", "tap"),
    "emphasize": ("emphasis", "emphasize", "happy", "smile", "joy", "surprise", "angry", "tap"),
    "question": ("question", "think", "tilt", "nod", "yes"),
    "settle": ("idle", "normal", "wait", "breath", "loop"),
}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _row_start_duration(row: Mapping[str, Any]) -> tuple[int, int]:
    start = _int(row.get("timeline_in_ms", row.get("start_ms", row.get("offset_ms", 0))), 0)
    duration = _int(row.get("duration_ms", 0), 0)
    if duration <= 0:
        end = _int(row.get("end_ms", start), start)
        duration = max(1, end - start)
    return max(0, start), max(1, duration)


def _text_seed(rows: Iterable[Mapping[str, Any]]) -> int:
    seed = 2166136261
    for row in rows or []:
        if not isinstance(row, Mapping):
            continue
        start, duration = _row_start_duration(row)
        text = str(row.get("text") or row.get("subtitle_text") or "")
        for ch in f"{start}:{duration}:{text}":
            seed ^= ord(ch)
            seed = (seed * 16777619) & 0xFFFFFFFF
    return seed or 1


def live2d_motion_choices(model_path: str | Path) -> list[dict[str, Any]]:
    """Return usable motion entries from a model3 file, idle-first when possible."""
    path = Path(str(model_path or "")).expanduser()
    if not path.is_file():
        return []
    try:
        from app.live2d.compat import normalize_live2d_model_path

        normalized = normalize_live2d_model_path(path) or str(path)
        meta_path = Path(normalized)
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    refs = data.get("FileReferences") if isinstance(data, Mapping) else {}
    motions = refs.get("Motions") if isinstance(refs, Mapping) else {}
    if not isinstance(motions, Mapping):
        return []
    choices: list[dict[str, Any]] = []
    for group, items in motions.items():
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, Mapping):
                continue
            file_ref = str(item.get("File") or "")
            if not file_ref.lower().replace("\\", "/").endswith(".motion3.json"):
                continue
            label = f"{group}/{Path(file_ref).name.replace('.motion3.json', '')}" if group else Path(file_ref).stem
            choices.append(
                {
                    "group": str(group or ""),
                    "index": index,
                    "label": label,
                    "file": file_ref,
                    "idle": "idle" in str(group).casefold() or "idle" in file_ref.casefold(),
                }
            )
    choices.sort(key=lambda row: (not bool(row.get("idle")), str(row.get("label") or "").casefold()))
    return choices


def _motion_label_text(choice: Mapping[str, Any]) -> str:
    return " ".join(
        str(choice.get(key) or "")
        for key in ("group", "label", "file")
    ).casefold().replace("-", "_").replace(" ", "_")


def _motion_matches_intent(choice: Mapping[str, Any], intent: str) -> bool:
    label = _motion_label_text(choice)
    return any(token in label for token in MOTION_INTENT_HINTS.get(intent, ()))


def _dialogue_motion_intent(row: Mapping[str, Any], *, index: int, total: int) -> str:
    text = f"{row.get('text') or ''} {row.get('subtitle_text') or ''} {row.get('display_text') or ''}".casefold()
    if index == 0:
        return "greet"
    if index >= max(0, total - 1):
        return "settle"
    if "?" in text or "\uff1f" in text:
        return "question"
    if "!" in text or "\uff01" in text:
        return "emphasize"
    return "explain"


def _select_authored_motion(
    choices: list[dict[str, Any]],
    row: Mapping[str, Any],
    *,
    index: int,
    total: int,
    seed: int,
) -> dict[str, Any]:
    if not choices:
        return {}
    idle = [choice for choice in choices if bool(choice.get("idle"))]
    non_idle = [choice for choice in choices if not bool(choice.get("idle"))]
    intent = _dialogue_motion_intent(row, index=index, total=total)
    search_pool = non_idle or choices
    intent_order = [intent]
    if intent == "settle":
        intent_order.extend(["explain", "greet"])
    elif intent != "explain":
        intent_order.append("explain")
    intent_order.append("greet")
    for candidate_intent in intent_order:
        for choice in search_pool:
            if _motion_matches_intent(choice, candidate_intent):
                selected = dict(choice)
                selected["intent"] = intent
                selected["selection_reason"] = f"label_matches_{candidate_intent}"
                return selected
    pool = search_pool or idle or choices
    selected = dict(pool[(index + seed) % len(pool)])
    selected["intent"] = intent
    selected["selection_reason"] = "deterministic_cycle"
    return selected


def _row_infos_for_storyboard(
    rows: list[Mapping[str, Any]],
    *,
    actor_start_ms: int,
    actor_duration_ms: int,
) -> list[dict[str, Any]]:
    actor_start = max(0, int(actor_start_ms))
    actor_end = actor_start + max(1, int(actor_duration_ms))
    infos: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        start, duration = _row_start_duration(row)
        end = start + duration
        if end <= actor_start or start >= actor_end:
            continue
        infos.append(
            {
                "index": index,
                "start_ms": max(actor_start, start),
                "end_ms": min(actor_end, end),
                "duration_ms": max(1, min(actor_end, end) - max(actor_start, start)),
                "row": dict(row),
            }
        )
    infos.sort(key=lambda item: (int(item["start_ms"]), int(item["index"])))
    return infos


def _dialogue_storyboard_segments(
    rows: list[Mapping[str, Any]],
    *,
    actor_start_ms: int,
    actor_duration_ms: int,
) -> list[dict[str, Any]]:
    actor_start = max(0, int(actor_start_ms))
    actor_end = actor_start + max(1, int(actor_duration_ms))
    infos = _row_infos_for_storyboard(rows, actor_start_ms=actor_start, actor_duration_ms=actor_duration_ms)
    if not infos:
        return [
            {
                "index": 0,
                "start_ms": actor_start,
                "end_ms": actor_end,
                "duration_ms": actor_end - actor_start,
                "row": {},
            }
        ]
    segments: list[dict[str, Any]] = []
    cursor = actor_start
    for pos, info in enumerate(infos):
        next_info = infos[pos + 1] if pos + 1 < len(infos) else None
        if next_info is not None:
            boundary = int((int(info["end_ms"]) + int(next_info["start_ms"])) / 2)
            boundary = max(int(info["start_ms"]) + 1, min(actor_end, boundary))
        else:
            boundary = actor_end
        start = max(actor_start, min(cursor, actor_end - 1))
        end = max(start + 1, min(actor_end, boundary))
        segments.append(
            {
                "index": int(info["index"]),
                "start_ms": start,
                "end_ms": end,
                "duration_ms": end - start,
                "row": dict(info["row"]),
            }
        )
        cursor = end
    if segments and int(segments[-1]["end_ms"]) < actor_end:
        segments[-1]["end_ms"] = actor_end
        segments[-1]["duration_ms"] = actor_end - int(segments[-1]["start_ms"])
    return segments


def build_authored_dialogue_motion_storyboard(
    model_path: str | Path,
    rows: Iterable[Mapping[str, Any]] | None,
    *,
    actor_start_ms: int = 0,
    actor_duration_ms: int = 3000,
) -> dict[str, Any]:
    """Plan authored Live2D motions for dialogue-line ranges."""
    input_rows = [dict(row) for row in (rows or []) if isinstance(row, Mapping)]
    choices = live2d_motion_choices(model_path)
    idle = [choice for choice in choices if bool(choice.get("idle"))]
    base_motion = dict(idle[0] if idle else choices[0]) if choices else {}
    seed = _text_seed(input_rows)
    segments = _dialogue_storyboard_segments(
        input_rows,
        actor_start_ms=actor_start_ms,
        actor_duration_ms=actor_duration_ms,
    )
    line_motions: list[dict[str, Any]] = []
    for segment_index, segment in enumerate(segments):
        selected = _select_authored_motion(
            choices,
            dict(segment.get("row") or {}),
            index=segment_index,
            total=len(segments),
            seed=seed,
        )
        if not selected:
            continue
        line_motions.append(
            {
                "segment_index": segment_index,
                "source_row_index": int(segment.get("index", segment_index) or segment_index),
                "start_ms": int(segment.get("start_ms", 0) or 0),
                "end_ms": int(segment.get("end_ms", 0) or 0),
                "duration_ms": int(segment.get("duration_ms", 0) or 0),
                "motion_group": str(selected.get("group") or ""),
                "motion_idx": _int(selected.get("index"), 0),
                "motion_label": str(selected.get("label") or ""),
                "motion_file": str(selected.get("file") or ""),
                "intent": str(selected.get("intent") or ""),
                "selection_reason": str(selected.get("selection_reason") or ""),
            }
        )
    return {
        "schema": AUTHORED_DIALOGUE_MOTION_STORYBOARD_SCHEMA,
        "available": bool(choices),
        "model_path": str(model_path or ""),
        "seed": seed,
        "motion_count": len(choices),
        "base_motion": base_motion,
        "line_motion_count": len(line_motions),
        "line_motions": line_motions,
        "unique_motions_used": len({(row["motion_group"], row["motion_idx"]) for row in line_motions}),
        "strategy": "idle_base_plus_dialogue_line_authored_motions",
    }


def _keyframe_time_ms(key: Any) -> int:
    if isinstance(key, Mapping):
        return _int(key.get("time_ms"), 0)
    return _int(getattr(key, "time_ms", 0), 0)


def _copy_keyframe_at_time(key: Any, time_ms: int) -> Any:
    copied = copy.deepcopy(key)
    if isinstance(copied, dict):
        copied["time_ms"] = max(0, int(time_ms))
    else:
        try:
            copied.time_ms = max(0, int(time_ms))
        except Exception:
            pass
    return copied


def _slice_keyframes_for_segment(keys: Iterable[Any], source_clip: Any, start_ms: int, duration_ms: int) -> list[Any]:
    source_start = _int(getattr(source_clip, "start_ms", 0), 0)
    rel_start = max(0, int(start_ms) - source_start)
    rel_end = rel_start + max(1, int(duration_ms))
    sliced: list[Any] = []
    for key in keys or []:
        time = _keyframe_time_ms(key)
        if rel_start <= time <= rel_end:
            sliced.append(_copy_keyframe_at_time(key, time - rel_start))
    return sliced


def _slice_parameter_tracks_for_segment(
    tracks: Mapping[str, Any] | None,
    source_clip: Any,
    start_ms: int,
    duration_ms: int,
) -> dict[str, list[Any]]:
    out: dict[str, list[Any]] = {}
    if not isinstance(tracks, Mapping):
        return out
    for raw_param_id, raw_keys in tracks.items():
        param_id = str(raw_param_id or "").strip()
        if not param_id:
            continue
        if isinstance(raw_keys, Mapping):
            key_rows = raw_keys.get("keyframes") or raw_keys.get("keys") or []
        else:
            key_rows = raw_keys or []
        sliced = _slice_keyframes_for_segment(key_rows, source_clip, start_ms, duration_ms)
        if sliced:
            out[param_id] = sliced
    return out


def _clone_dialogue_motion_segment(source_clip: Any, segment: Mapping[str, Any], *, total: int) -> Any:
    clip = copy.deepcopy(source_clip)
    start_ms = int(segment.get("start_ms", getattr(source_clip, "start_ms", 0)) or 0)
    duration_ms = max(1, int(segment.get("duration_ms", getattr(source_clip, "duration_ms", 1)) or 1))
    clip.start_ms = start_ms
    clip.duration_ms = duration_ms
    clip.motion_group = str(segment.get("motion_group") or getattr(source_clip, "motion_group", "") or "")
    clip.motion_idx = _int(segment.get("motion_idx"), _int(getattr(source_clip, "motion_idx", 0), 0))
    clip.loop = False
    clip.kf_pos_x = _slice_keyframes_for_segment(getattr(source_clip, "kf_pos_x", []), source_clip, start_ms, duration_ms)
    clip.kf_pos_y = _slice_keyframes_for_segment(getattr(source_clip, "kf_pos_y", []), source_clip, start_ms, duration_ms)
    clip.kf_scale = _slice_keyframes_for_segment(getattr(source_clip, "kf_scale", []), source_clip, start_ms, duration_ms)
    clip.kf_opacity = _slice_keyframes_for_segment(getattr(source_clip, "kf_opacity", []), source_clip, start_ms, duration_ms)
    if hasattr(clip, "parameter_keyframes"):
        clip.parameter_keyframes = _slice_parameter_tracks_for_segment(
            getattr(source_clip, "parameter_keyframes", {}),
            source_clip,
            start_ms,
            duration_ms,
        )
    if hasattr(clip, "mocap_parameter_keyframes"):
        clip.mocap_parameter_keyframes = _slice_parameter_tracks_for_segment(
            getattr(source_clip, "mocap_parameter_keyframes", {}),
            source_clip,
            start_ms,
            duration_ms,
        )
    segment_payload = {
        "schema": AUTHORED_DIALOGUE_MOTION_STORYBOARD_SCHEMA,
        "source": "tts_dialogue_take",
        "segment_index": int(segment.get("segment_index", 0) or 0),
        "segment_count": int(total),
        "motion_group": clip.motion_group,
        "motion_idx": clip.motion_idx,
        "motion_label": str(segment.get("motion_label") or ""),
        "intent": str(segment.get("intent") or ""),
        "start_ms": start_ms,
        "duration_ms": duration_ms,
    }
    clip.motion_storyboard_payload = {
        "kind": "live2d_dialogue_motion_storyboard",
        **segment_payload,
    }
    payload = dict(getattr(clip, "dialogue_motion_payload", {}) or {})
    payload["authored_motion_storyboard_segment"] = segment_payload
    clip.dialogue_motion_payload = payload
    reset = getattr(clip, "reset", None)
    if callable(reset):
        try:
            reset()
        except Exception:
            pass
    return clip


def apply_authored_dialogue_motion_storyboard_to_track(
    actor_track: Any,
    source_clip: Any,
    rows: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Replace one Live2D clip with dialogue-line clips using authored motions."""
    if actor_track is None or source_clip is None:
        return {"applied": False, "reason": "missing_track_or_clip"}
    actor_start = max(0, _int(getattr(source_clip, "start_ms", 0), 0))
    actor_duration = max(1, _int(getattr(source_clip, "duration_ms", 3000), 3000))
    plan = build_authored_dialogue_motion_storyboard(
        str(getattr(source_clip, "model_path", "") or ""),
        rows,
        actor_start_ms=actor_start,
        actor_duration_ms=actor_duration,
    )
    if not bool(plan.get("available")):
        return {"applied": False, "reason": "no_authored_motions", "plan": plan}
    line_motions = [dict(row) for row in plan.get("line_motions", []) if isinstance(row, Mapping)]
    if len(line_motions) <= 1:
        base_motion = dict(plan.get("base_motion") or {})
        try:
            source_clip.motion_group = str(base_motion.get("group") or getattr(source_clip, "motion_group", "") or "")
            source_clip.motion_idx = _int(base_motion.get("index"), _int(getattr(source_clip, "motion_idx", 0), 0))
        except Exception:
            pass
        payload = dict(getattr(source_clip, "dialogue_motion_payload", {}) or {})
        payload["authored_motion_storyboard"] = plan
        source_clip.dialogue_motion_payload = payload
        return {"applied": False, "reason": "single_motion_segment", "plan": plan}
    new_clips = [
        _clone_dialogue_motion_segment(source_clip, segment, total=len(line_motions))
        for segment in line_motions
    ]
    existing = list(getattr(actor_track, "clips", []) or [])
    replaced = 0
    kept = []
    for clip in existing:
        if clip is source_clip:
            replaced += 1
            continue
        kept.append(clip)
    if replaced <= 0:
        return {"applied": False, "reason": "source_clip_not_in_track", "plan": plan}
    actor_track.clips = sorted(kept + new_clips, key=lambda item: _int(getattr(item, "start_ms", 0), 0))
    return {
        "applied": True,
        "schema": AUTHORED_DIALOGUE_MOTION_STORYBOARD_SCHEMA,
        "created": len(new_clips),
        "replaced": replaced,
        "motion_count": int(plan.get("motion_count", 0) or 0),
        "unique_motions_used": int(plan.get("unique_motions_used", 0) or 0),
        "motions_used": [str(row.get("motion_label") or "") for row in line_motions],
        "plan": plan,
    }


def _natural_value(param_id: str, t: float, *, seed: int, speech: float) -> float:
    phase = (seed % 997) / 997.0 * math.tau
    slow = math.sin(t * 0.78 + phase)
    mid = math.sin(t * 1.37 + phase * 0.37)
    tiny = math.sin(t * 2.11 + phase * 0.19)
    speaking = _clamp(speech, 0.0, 1.0)
    if param_id == "ParamAngleX":
        return slow * 7.0 + mid * 0.75
    if param_id == "ParamAngleY":
        return -1.1 + mid * 2.35 + speaking * 0.85
    if param_id == "ParamAngleZ":
        return slow * -2.8 + tiny * 0.45
    if param_id == "ParamBodyAngleX":
        return slow * 2.0
    if param_id == "ParamBodyAngleY":
        return mid * 1.3 + speaking * 0.35
    if param_id == "ParamBodyAngleZ":
        return slow * -1.2
    if param_id == "ParamBodyUpper":
        return _clamp(2.2 + slow * 1.2 + speaking * 1.4, -7.0, 10.0)
    if param_id == "ParamBustY":
        return _clamp(3.0 + math.sin(t * 2.35 + phase) * 1.1 + speaking * 0.8, 0.0, 10.0)
    if param_id == "ParamBreath":
        return _clamp(0.55 + math.sin(t * 2.35 + phase) * 0.28, 0.15, 1.0)
    if param_id == "ParamEyeBallX":
        return _clamp(slow * 0.24 + speaking * 0.08, -1.0, 1.0)
    if param_id == "ParamEyeBallY":
        return _clamp(mid * 0.16 - 0.05, -1.0, 1.0)
    if param_id in {"ParamArmLA", "ParamArmRB"}:
        return _clamp(3.2 + slow * 1.4 + speaking * 1.3, 0.0, 10.0)
    if param_id in {"ParamArmRA", "ParamArmLB"}:
        return _clamp(2.8 + mid * 1.3 + speaking * 1.1, 0.0, 10.0)
    if param_id == "ParamHandAngleL":
        return _clamp(1.2 + slow * 2.4 + speaking * 1.6, -1.0, 10.0)
    if param_id == "ParamHandAngleR":
        return _clamp(1.0 + mid * 2.2 + speaking * 1.5, -1.0, 10.0)
    if param_id == "ParamHandChangeR":
        return 1.0 if speaking > 0.4 and mid > 0.15 else 0.0
    if param_id == "ParamHandDhangeL":
        return 1.0 if speaking > 0.4 and slow < -0.10 else 0.0
    if param_id == "ParamFaceForm":
        return _clamp(0.12 + speaking * 0.16 + mid * 0.08, -1.0, 1.0)
    if param_id in {"ParamBrowLForm", "ParamBrowRForm"}:
        return _clamp(speaking * 0.18 + slow * 0.08, -1.0, 1.0)
    if param_id in {"ParamBrowLAngle", "ParamBrowRAngle"}:
        return _clamp(mid * 0.22 + speaking * 0.10, -1.0, 1.0)
    if param_id in {"ParamEyeLSmile", "ParamEyeRSmile"}:
        return _clamp(speaking * 0.20 + slow * 0.06, 0.0, 1.0)
    return 0.0


def _speech_activity_at(rows: list[Mapping[str, Any]], timeline_ms: int) -> float:
    for row in rows:
        start, duration = _row_start_duration(row)
        end = start + duration
        if start - 120 <= timeline_ms <= end + 180:
            if timeline_ms < start:
                return _clamp((timeline_ms - (start - 120)) / 120.0, 0.0, 1.0)
            if timeline_ms > end:
                return _clamp(1.0 - (timeline_ms - end) / 180.0, 0.0, 1.0)
            return 1.0
    return 0.0


def _append_param_key(keys: list[dict[str, Any]], time_ms: int, value: float, *, curve: str = "smoothstep") -> None:
    keys.append({"time_ms": max(0, int(time_ms)), "value": round(float(value), 5), "curve": curve})


def _sorted_compact_keys(keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = sorted(keys, key=lambda row: (_int(row.get("time_ms"), 0), str(row.get("curve") or "")))
    compact: list[dict[str, Any]] = []
    for row in rows:
        time = _int(row.get("time_ms"), 0)
        value = _float(row.get("value"), 0.0)
        curve = str(row.get("curve") or "smoothstep")
        if compact and _int(compact[-1].get("time_ms"), 0) == time:
            compact[-1] = {"time_ms": time, "value": round(value, 5), "curve": curve}
            continue
        compact.append({"time_ms": time, "value": round(value, 5), "curve": curve})
    return compact


def _apply_gesture_beats(
    parameter_keyframes: dict[str, list[dict[str, Any]]],
    rows: list[Mapping[str, Any]],
    *,
    actor_start_ms: int,
    seed: int,
) -> list[dict[str, Any]]:
    beats: list[dict[str, Any]] = []
    if not rows:
        return beats
    preset_count = len(GESTURE_PRESETS)
    for index, row in enumerate(rows):
        start, duration = _row_start_duration(row)
        local_start = max(0, start - actor_start_ms)
        local_end = max(local_start + 1, local_start + duration)
        attack = min(520, max(180, duration // 5))
        hold = min(duration - 1, max(attack + 1, int(duration * 0.48)))
        release_start = min(local_end - 1, local_start + max(hold, int(duration * 0.72)))
        if index == 0:
            preset = GESTURE_PRESETS[0]
        elif index == len(rows) - 1:
            preset = GESTURE_PRESETS[-1]
        else:
            preset = GESTURE_PRESETS[1 + ((index + seed) % max(1, preset_count - 2))]
        params = dict(preset.get("params") or {})
        for param_id, target_value in params.items():
            keys = parameter_keyframes.setdefault(str(param_id), [])
            base_before = _natural_value(str(param_id), max(0, local_start - 120) / 1000.0, seed=seed, speech=0.0)
            base_after = _natural_value(str(param_id), local_end / 1000.0, seed=seed, speech=0.0)
            _append_param_key(keys, max(0, local_start - 120), base_before)
            _append_param_key(keys, local_start + attack, _float(target_value, 0.0))
            _append_param_key(keys, release_start, _float(target_value, 0.0))
            _append_param_key(keys, local_end, base_after)
        beats.append(
            {
                "index": index,
                "gesture_id": str(preset.get("id") or ""),
                "label": str(preset.get("label") or ""),
                "start_ms": start,
                "duration_ms": duration,
                "parameter_count": len(params),
            }
        )
    for param_id, keys in list(parameter_keyframes.items()):
        parameter_keyframes[param_id] = _sorted_compact_keys(keys)
    return beats


def build_natural_dialogue_motion_payload(
    rows: Iterable[Mapping[str, Any]] | None,
    *,
    actor_start_ms: int = 0,
    actor_duration_ms: int = 3000,
    interval_ms: int = 700,
    style: str = "natural_dialogue",
) -> dict[str, Any]:
    """Build deterministic head/body/breath keys for a dialogue actor clip."""
    input_rows = [dict(row) for row in (rows or []) if isinstance(row, Mapping)]
    start_base = max(0, _int(actor_start_ms, 0))
    duration = max(1, _int(actor_duration_ms, 3000))
    step = max(180, min(1200, _int(interval_ms, 700)))
    seed = _text_seed(input_rows)
    times = list(range(0, duration + 1, step))
    if times[-1] != duration:
        times.append(duration)
    parameter_keyframes: dict[str, list[dict[str, Any]]] = {}
    for param_id in BODY_MOTION_PARAMS:
        keys: list[dict[str, Any]] = []
        for local_ms in times:
            timeline_ms = start_base + local_ms
            speech = _speech_activity_at(input_rows, timeline_ms)
            value = _natural_value(param_id, local_ms / 1000.0, seed=seed, speech=speech)
            keys.append({"time_ms": int(local_ms), "value": round(value, 5), "curve": "smoothstep"})
        parameter_keyframes[param_id] = keys
    beats = _apply_gesture_beats(parameter_keyframes, input_rows, actor_start_ms=start_base, seed=seed)
    return {
        "schema": DIALOGUE_MOTION_SCHEMA,
        "style": str(style or "natural_dialogue"),
        "duration_ms": duration,
        "interval_ms": step,
        "seed": seed,
        "parameter_keyframes": parameter_keyframes,
        "parameter_tracks": list(parameter_keyframes.keys()),
        "gesture_beats": beats,
    }


def apply_natural_dialogue_motion_to_clip(
    clip: Any,
    rows: Iterable[Mapping[str, Any]] | None = None,
    *,
    replace_existing: bool = True,
    prefer_authored_motion: bool = True,
    interval_ms: int = 700,
    style: str = "natural_dialogue",
) -> dict[str, Any]:
    """Apply natural dialogue motion keys and choose an authored idle motion."""
    actor_start = max(0, _int(getattr(clip, "start_ms", 0), 0))
    actor_duration = max(1, _int(getattr(clip, "duration_ms", 3000), 3000))
    choices = live2d_motion_choices(str(getattr(clip, "model_path", "") or ""))
    selected_motion: dict[str, Any] = {}
    if bool(prefer_authored_motion) and choices:
        current_group = str(getattr(clip, "motion_group", "") or "")
        current_idx = _int(getattr(clip, "motion_idx", 0), 0)
        current_ok = any(str(row.get("group") or "") == current_group and _int(row.get("index"), 0) == current_idx for row in choices)
        if not current_ok:
            selected_motion = dict(choices[0])
            try:
                clip.motion_group = str(selected_motion.get("group") or "")
                clip.motion_idx = _int(selected_motion.get("index"), 0)
                clip.loop = True
            except Exception:
                pass
        else:
            selected_motion = {"group": current_group, "index": current_idx, "kept_existing": True}

    payload = build_natural_dialogue_motion_payload(
        rows,
        actor_start_ms=actor_start,
        actor_duration_ms=actor_duration,
        interval_ms=interval_ms,
        style=style,
    )
    existing = dict(getattr(clip, "parameter_keyframes", {}) or {})
    generated = dict(payload.get("parameter_keyframes") or {})
    for param_id, keys in generated.items():
        if bool(replace_existing):
            existing[str(param_id)] = [dict(row) for row in keys or []]
        else:
            current = list(existing.get(str(param_id)) or [])
            current.extend(dict(row) for row in keys or [])
            current.sort(key=lambda row: _int(row.get("time_ms"), 0) if isinstance(row, Mapping) else 0)
            existing[str(param_id)] = current
    clip.parameter_keyframes = existing
    payload["authored_motion_choices"] = choices
    payload["authored_motion"] = selected_motion
    try:
        clip.dialogue_motion_payload = dict(payload)
    except Exception:
        pass
    reset = getattr(clip, "reset", None)
    if callable(reset):
        try:
            reset()
        except Exception:
            pass
    return payload


__all__ = [
    "AUTHORED_DIALOGUE_MOTION_STORYBOARD_SCHEMA",
    "BODY_MOTION_PARAMS",
    "DIALOGUE_MOTION_SCHEMA",
    "apply_authored_dialogue_motion_storyboard_to_track",
    "apply_natural_dialogue_motion_to_clip",
    "build_authored_dialogue_motion_storyboard",
    "build_natural_dialogue_motion_payload",
    "live2d_motion_choices",
]
