"""TTS-to-actor lip-sync helpers.

The first pass deliberately uses subtitle/TTS clip timing rather than a heavy
phoneme analyzer.  It produces renderable Live2D parameter keyframes that can
be replaced later by audio-energy or phoneme tracks without changing the action
contract.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


TTS_ACTOR_LIPSYNC_SCHEMA = "tigercapture.tts_actor_lipsync.v1"


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
        end_ms = _int(row.get("end_ms", start), start)
        duration = max(1, end_ms - start)
    return max(0, start), max(1, duration)


def _text_activity(text: str) -> float:
    cleaned = str(text or "").strip()
    if not cleaned:
        return 0.62
    alpha_count = sum(1 for ch in cleaned if ch.isalnum())
    punctuation = sum(1 for ch in cleaned if ch in "!?.,;:")
    return _clamp(0.58 + min(alpha_count, 42) / 120.0 - punctuation * 0.025, 0.48, 0.9)


def _form_value(text: str) -> float:
    lowered = str(text or "").casefold()
    if any(ch in lowered for ch in ("o", "u", "오", "우", "요")):
        return -0.18
    if any(ch in lowered for ch in ("i", "e", "이", "에", "애")):
        return 0.22
    return 0.0


def _append_key(keys: list[dict[str, Any]], time_ms: int, value: float, curve: str) -> None:
    time = max(0, int(time_ms))
    val = round(_clamp(float(value), 0.0, 1.0), 5)
    if keys and int(keys[-1]["time_ms"]) == time:
        keys[-1]["value"] = max(float(keys[-1]["value"]), val)
        keys[-1]["curve"] = curve
        return
    keys.append({"time_ms": time, "value": val, "curve": curve})


def _append_form_key(keys: list[dict[str, Any]], time_ms: int, value: float, curve: str) -> None:
    time = max(0, int(time_ms))
    val = round(_clamp(float(value), -1.0, 1.0), 5)
    if keys and int(keys[-1]["time_ms"]) == time:
        keys[-1]["value"] = val
        keys[-1]["curve"] = curve
        return
    keys.append({"time_ms": time, "value": val, "curve": curve})


def _dedupe_sorted_keys(keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[int, dict[str, Any]] = {}
    for row in sorted(keys, key=lambda item: int(item.get("time_ms", 0) or 0)):
        time = max(0, _int(row.get("time_ms"), 0))
        if time in merged:
            current = merged[time]
            current["value"] = max(_float(current.get("value"), 0.0), _float(row.get("value"), 0.0))
            current["curve"] = str(row.get("curve") or current.get("curve") or "smoothstep")
        else:
            merged[time] = {
                "time_ms": time,
                "value": round(_float(row.get("value"), 0.0), 5),
                "curve": str(row.get("curve") or "smoothstep"),
            }
    out = list(merged.values())
    compact: list[dict[str, Any]] = []
    for row in out:
        if compact and abs(_float(compact[-1].get("value"), 0.0) - _float(row.get("value"), 0.0)) < 0.0001:
            if int(row["time_ms"]) - int(compact[-1]["time_ms"]) < 70:
                continue
        compact.append(row)
    return compact


def build_tts_actor_lipsync_payload(
    rows: Iterable[Mapping[str, Any]],
    *,
    actor_start_ms: int = 0,
    actor_duration_ms: int | None = None,
    mouth_param_id: str = "ParamMouthOpenY",
    mouth_form_param_id: str = "ParamMouthForm",
    open_value: float = 0.82,
    closed_value: float = 0.0,
    curve: str = "smoothstep",
) -> dict[str, Any]:
    """Build Live2D parameter keyframes from TTS/subtitle timeline rows."""
    start_base = max(0, _int(actor_start_ms, 0))
    clip_duration = None if actor_duration_ms is None else max(1, _int(actor_duration_ms, 1))
    mouth_param = str(mouth_param_id or "ParamMouthOpenY").strip() or "ParamMouthOpenY"
    form_param = str(mouth_form_param_id or "ParamMouthForm").strip()
    open_peak = _clamp(_float(open_value, 0.82), 0.05, 1.0)
    closed = _clamp(_float(closed_value, 0.0), 0.0, 0.2)
    curve_name = str(curve or "smoothstep")

    mouth_keys: list[dict[str, Any]] = []
    form_keys: list[dict[str, Any]] = []
    used_rows: list[dict[str, Any]] = []
    for index, raw in enumerate(rows or []):
        if not isinstance(raw, Mapping):
            continue
        start, duration = _row_start_duration(raw)
        local_start = start - start_base
        local_end = local_start + duration
        if clip_duration is not None and (local_end < 0 or local_start > clip_duration):
            continue
        local_start = max(0, local_start)
        local_end = min(clip_duration, local_end) if clip_duration is not None else local_end
        if local_end <= local_start:
            continue

        text = str(raw.get("text") or raw.get("subtitle_text") or "")
        activity = _text_activity(text)
        peak = _clamp(open_peak * activity, 0.12, 1.0)
        form = _form_value(text)
        attack = min(90, max(35, duration // 7))
        release = min(120, max(45, duration // 6))
        active_start = local_start + attack
        active_end = max(active_start + 1, local_end - release)
        _append_key(mouth_keys, max(0, local_start - 34), closed, curve_name)
        _append_key(mouth_keys, active_start, peak, curve_name)
        if duration >= 420:
            pulse_count = min(8, max(1, duration // 260))
            span = max(1, active_end - active_start)
            for pulse in range(1, pulse_count):
                t = active_start + int(round(span * pulse / pulse_count))
                dip = peak * (0.56 if pulse % 2 else 0.72)
                _append_key(mouth_keys, t, dip, curve_name)
                _append_key(mouth_keys, min(active_end, t + min(90, span // max(2, pulse_count))), peak, curve_name)
        _append_key(mouth_keys, local_end, closed, curve_name)
        if form_param:
            _append_form_key(form_keys, local_start, form, curve_name)
            _append_form_key(form_keys, local_end, 0.0, curve_name)
        used_rows.append(
            {
                "index": _int(raw.get("subtitle_index", raw.get("index", index)), index),
                "start_ms": start,
                "duration_ms": duration,
                "local_start_ms": local_start,
                "local_end_ms": local_end,
                "text": text,
            }
        )

    parameter_keyframes: dict[str, list[dict[str, Any]]] = {}
    mouth_keys = _dedupe_sorted_keys(mouth_keys)
    if mouth_keys:
        parameter_keyframes[mouth_param] = mouth_keys
    if form_param and form_keys:
        parameter_keyframes[form_param] = _dedupe_sorted_keys(form_keys)
    return {
        "schema": TTS_ACTOR_LIPSYNC_SCHEMA,
        "ok": bool(mouth_keys),
        "mouth_param_id": mouth_param,
        "mouth_form_param_id": form_param,
        "row_count": len(used_rows),
        "parameter_keyframes": parameter_keyframes,
        "rows": used_rows,
        "duration_ms": clip_duration if clip_duration is not None else (max((row["local_end_ms"] for row in used_rows), default=0)),
    }


__all__ = [
    "TTS_ACTOR_LIPSYNC_SCHEMA",
    "build_tts_actor_lipsync_payload",
]
