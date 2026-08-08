"""Pure helpers for timeline drop-guide labels, widths, and segments."""
from __future__ import annotations

import json
from typing import Any

from app.effect_cards import FADE_MIME_TYPE, SPEED_MIME_TYPE, ZOOM_MIME_TYPE
from app.media_asset_routing import (
    ar_pbr_paths_from_mime,
    mmd_paths_from_mime,
    motion_project_paths_from_mime,
    timeline_media_paths_from_mime,
)
from app.typography import TEXT_CLIP_MIME
from app.video_editor_preset_cards import (
    EDITOR_PRESET_MIME_TYPE,
    EFFECT_PRESET_MIME_TYPE,
    TITLE_PRESET_MIME_TYPE,
    TRANSITION_MIME_TYPE,
)


DROP_GUIDE_PALETTE = {
    "effect": "#8A8F98",
    "transition": "#A8A08E",
    "title": "#A692A8",
    "caption_style": "#938BA8",
    "sticker": "#85A098",
    "motion": "#849BAD",
    "audio": "#8EA28F",
    "color": "#AAA184",
    "template": "#9093A6",
    "media": "#8B97AE",
    "fade": "#A08F86",
    "speed": "#A79A85",
    "zoom": "#8D90A6",
    "3d": "#5B8CFF",
    "motion_actor": "#27C2A0",
}


def _has(mime: Any, mime_type: str) -> bool:
    try:
        return bool(mime is not None and mime.hasFormat(mime_type))
    except Exception:
        return False


def _has_urls(mime: Any) -> bool:
    try:
        return bool(mime is not None and mime.hasUrls())
    except Exception:
        return False


def _has_timeline_media(mime: Any) -> bool:
    return bool(timeline_media_paths_from_mime(mime) or _has_urls(mime))


def _data_text(mime: Any, mime_type: str) -> str:
    try:
        return bytes(mime.data(mime_type)).decode("utf-8")
    except Exception:
        return ""


def _data_json(mime: Any, mime_type: str) -> dict[str, Any]:
    try:
        value = json.loads(_data_text(mime, mime_type))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _entry(kind: str, label: str, start_ms: int, duration_ms: int, color: str) -> dict:
    return {
        "kind": str(kind or "preset"),
        "label": str(label or kind or "Preset"),
        "start_ms": max(0, int(start_ms or 0)),
        "duration_ms": max(120, int(duration_ms or 900)),
        "color": str(color or "#7E6FFF"),
    }


def _motion_project_duration_ms(mime: Any) -> int:
    paths = motion_project_paths_from_mime(mime)
    if not paths:
        return 0
    try:
        from app.motion_designer.project_io import load_motion_project

        return max(1, int(load_motion_project(paths[0]).duration_ms))
    except Exception:
        return 5_000


def drop_guide_text(mime: Any) -> str:
    if motion_project_paths_from_mime(mime):
        return "Motion Actor"
    if mmd_paths_from_mime(mime):
        return "MMD"
    if ar_pbr_paths_from_mime(mime):
        return "3D"
    if _has(mime, FADE_MIME_TYPE):
        return "Fade"
    if _has(mime, TRANSITION_MIME_TYPE):
        return "Cut"
    if _has(mime, TEXT_CLIP_MIME) or _has(mime, TITLE_PRESET_MIME_TYPE):
        return "Title"
    if _has(mime, SPEED_MIME_TYPE):
        return "Speed"
    if _has(mime, ZOOM_MIME_TYPE):
        return "Zoom"
    if _has(mime, EFFECT_PRESET_MIME_TYPE):
        return "FX"
    if _has(mime, EDITOR_PRESET_MIME_TYPE):
        return "Preset"
    if _has_timeline_media(mime):
        return "Media"
    return "Drop"


def drop_guide_width_for_mime(mime: Any, *, px_per_sec: float = 40.0) -> int:
    def _ms_to_px(duration_ms: int, *, minimum: int = 42, maximum: int = 360) -> int:
        px = int(max(1, duration_ms) / 1000.0 * float(px_per_sec))
        return max(minimum, min(maximum, px))

    if _has(mime, FADE_MIME_TYPE):
        try:
            return _ms_to_px(int(_data_text(mime, FADE_MIME_TYPE)), minimum=46)
        except Exception:
            return _ms_to_px(400, minimum=46)
    if _has(mime, SPEED_MIME_TYPE):
        try:
            return _ms_to_px(int(_data_text(mime, SPEED_MIME_TYPE).split("|")[1]), minimum=64)
        except Exception:
            return _ms_to_px(1800, minimum=64)
    if _has(mime, ZOOM_MIME_TYPE):
        try:
            return _ms_to_px(int(_data_text(mime, ZOOM_MIME_TYPE)), minimum=72)
        except Exception:
            return _ms_to_px(2200, minimum=72)
    if _has(mime, TRANSITION_MIME_TYPE):
        payload = _data_json(mime, TRANSITION_MIME_TYPE)
        return _ms_to_px(int(payload.get("ms", 500) or 500), minimum=58)
    if _has(mime, TITLE_PRESET_MIME_TYPE):
        payload = _data_json(mime, TITLE_PRESET_MIME_TYPE)
        return _ms_to_px(int(payload.get("duration_ms", 3000) or 3000), minimum=88)
    if _has(mime, EDITOR_PRESET_MIME_TYPE):
        payload = _data_json(mime, EDITOR_PRESET_MIME_TYPE)
        preset_payload = dict(payload.get("payload") or {})
        try:
            if preset_payload.get("duration_ms"):
                return _ms_to_px(int(preset_payload.get("duration_ms")), minimum=96)
            sequence = preset_payload.get("sequence")
            if isinstance(sequence, list):
                max_at = max(
                    (int(item.get("at_ms", 0) or 0) for item in sequence if isinstance(item, dict)),
                    default=0,
                )
                return _ms_to_px(max(2200, max_at + 1800), minimum=120, maximum=420)
        except Exception:
            pass
        return 128
    if _has(mime, EFFECT_PRESET_MIME_TYPE):
        return 92
    if motion_project_paths_from_mime(mime):
        return _ms_to_px(_motion_project_duration_ms(mime), minimum=96, maximum=420)
    if mmd_paths_from_mime(mime):
        return _ms_to_px(10_000, minimum=96)
    if ar_pbr_paths_from_mime(mime):
        return _ms_to_px(10_000, minimum=96)
    if _has_timeline_media(mime):
        return 160
    return 68


def drop_guide_segments_for_mime(mime: Any) -> list[dict]:
    palette = DROP_GUIDE_PALETTE
    if motion_project_paths_from_mime(mime):
        return [
            _entry(
                "motion_actor",
                "Motion Actor",
                0,
                _motion_project_duration_ms(mime),
                palette["motion_actor"],
            )
        ]
    if ar_pbr_paths_from_mime(mime):
        return [_entry("3d", "3D", 0, 10_000, palette["3d"])]
    if _has(mime, FADE_MIME_TYPE):
        try:
            dur = int(_data_text(mime, FADE_MIME_TYPE))
        except Exception:
            dur = 400
        return [_entry("fade", "Fade", 0, dur, palette["fade"])]
    if _has(mime, SPEED_MIME_TYPE):
        try:
            dur = int(_data_text(mime, SPEED_MIME_TYPE).split("|")[1])
        except Exception:
            dur = 1800
        return [_entry("speed", "Speed", 0, dur, palette["speed"])]
    if _has(mime, ZOOM_MIME_TYPE):
        try:
            dur = int(_data_text(mime, ZOOM_MIME_TYPE))
        except Exception:
            dur = 2200
        return [_entry("motion", "Zoom", 0, dur, palette["zoom"])]
    if _has(mime, TRANSITION_MIME_TYPE):
        payload = _data_json(mime, TRANSITION_MIME_TYPE)
        ttype = str(payload.get("type", "transition") or "transition")
        dur = int(payload.get("ms", 500) or 500)
        label = str(payload.get("name") or payload.get("preset_name") or ttype).replace("_", " ").title()
        return [_entry("transition", label, 0, dur, palette["transition"])]
    if _has(mime, TITLE_PRESET_MIME_TYPE):
        payload = _data_json(mime, TITLE_PRESET_MIME_TYPE)
        dur = int(payload.get("duration_ms", 3000) or 3000)
        label = str(payload.get("name", "Title") or "Title")
        return [_entry("title", label, 0, dur, palette["title"])]
    if _has(mime, EDITOR_PRESET_MIME_TYPE):
        payload = _data_json(mime, EDITOR_PRESET_MIME_TYPE)
        preset_payload = dict(payload.get("payload") or {})
        kind = str(payload.get("kind", "preset") or "preset")
        sequence = preset_payload.get("sequence")
        if isinstance(sequence, list) and sequence:
            segments: list[dict] = []
            for item in sequence:
                if not isinstance(item, dict):
                    continue
                child_kind = str(item.get("kind", "preset") or "preset")
                at_ms = int(item.get("at_ms", 0) or 0)
                dur = int(item.get("duration_ms", 1100) or 1100)
                label = str(item.get("preset_id", child_kind) or child_kind)
                segments.append(_entry(
                    child_kind,
                    label.replace("-", " ").title(),
                    at_ms,
                    dur,
                    palette.get(child_kind, "#7E6FFF"),
                ))
            if segments:
                return segments[:12]
        dur = int(preset_payload.get("duration_ms", 1800) or 1800)
        return [_entry(kind, str(payload.get("name", kind) or kind), 0, dur, palette.get(kind, "#7E6FFF"))]
    if _has(mime, EFFECT_PRESET_MIME_TYPE):
        return [_entry("effect", "FX", 0, 1200, palette["effect"])]
    if _has_timeline_media(mime):
        return [_entry("media", "Media", 0, 2500, palette["media"])]
    return []


def effect_preset_drag_label(mime: Any, *, default: str = "Effect") -> str:
    if not _has(mime, EFFECT_PRESET_MIME_TYPE):
        return ""
    payload = _data_json(mime, EFFECT_PRESET_MIME_TYPE)
    meta = payload.get("__preset_meta")
    if isinstance(meta, dict):
        name = str(meta.get("name") or meta.get("id") or "").strip()
        if name:
            return name[:48]
    name = str(payload.get("name") or payload.get("preset_name") or "").strip()
    if name:
        return name[:48]
    return str(default)


def drop_guide_detail_for_mime(mime: Any, *, effect_default_label: str = "Effect") -> str:
    segments = drop_guide_segments_for_mime(mime)
    if not segments:
        return ""
    if _has(mime, EFFECT_PRESET_MIME_TYPE):
        label = effect_preset_drag_label(mime, default=effect_default_label)
        return f"clip FX / {label}" if label else "clip FX / drop on clip"
    if _has(mime, TRANSITION_MIME_TYPE):
        return "cut edge / transition"
    if len(segments) == 1:
        seg = segments[0]
        dur = int(seg.get("duration_ms", 0) or 0)
        return f"{seg.get('kind', 'item')} / {max(1, round(dur / 1000.0, 1))}s"
    end_ms = max(
        (
            int(seg.get("start_ms", 0) or 0)
            + int(seg.get("duration_ms", 0) or 0)
        )
        for seg in segments
    )
    kinds = []
    for seg in segments:
        kind = str(seg.get("kind", "preset") or "preset")
        if kind not in kinds:
            kinds.append(kind)
    kinds_text = ", ".join(kinds[:4])
    if len(kinds) > 4:
        kinds_text += f" +{len(kinds) - 4}"
    return f"{len(segments)} steps / {max(1, round(end_ms / 1000.0, 1))}s / {kinds_text}"
