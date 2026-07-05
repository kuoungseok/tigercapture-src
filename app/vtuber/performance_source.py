"""VTuber performance-source contracts.

Performance sources drive avatar tracking only.  They are allowed in the
Source Tracking monitor, but must not become Program Output backgrounds.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping


PERFORMANCE_SOURCE_SCHEMA = "tigerstudio.vtuber.performance_source.v1"
PERFORMANCE_SOURCE_UI_SCHEMA = "tigerstudio.vtuber.performance_source_ui.v1"
PERFORMANCE_SOURCE_TRACK_TYPE = "vtuber_performance_source"
PERFORMANCE_SOURCE_TRACK_KIND = "performance_source_track"
PERFORMANCE_SOURCE_BADGE = "PERF"
PERFORMANCE_SOURCE_LABEL = "Performance Source"
PERFORMANCE_SOURCE_MIME_TYPE = "application/x-tigerstudio-performance-source"
PROGRAM_BACKGROUND_CAPTURE = "capture"
PROGRAM_BACKGROUND_MEDIA = "media"
PROGRAM_BACKGROUND_CHROMA = "green_chroma"
GREEN_CHROMA_RGBA = (0, 255, 0, 255)


def performance_source_ui_contract() -> dict[str, Any]:
    """Return the main-UI contract for input-only VTuber performance sources."""
    return {
        "schema": PERFORMANCE_SOURCE_UI_SCHEMA,
        "label": PERFORMANCE_SOURCE_LABEL,
        "badge": PERFORMANCE_SOURCE_BADGE,
            "legacy_terms": [],
        "media_pool": {
            "toggle_action": "vtuber.performance_source.mark_media",
            "badge": PERFORMANCE_SOURCE_BADGE,
            "drag_mime_type": PERFORMANCE_SOURCE_MIME_TYPE,
            "eligible_kinds": ["video"],
            "program_output": False,
            "tooltip": "Used for avatar tracking only; never a Program Output background.",
        },
        "timeline": {
            "track_type": PERFORMANCE_SOURCE_TRACK_TYPE,
            "track_kind": PERFORMANCE_SOURCE_TRACK_KIND,
            "create_action": "vtuber.performance_source.add_clip",
            "dedicated_track": True,
            "drop_behavior": "drop marked media onto the timeline to create or reuse the Performance Source track",
            "time_selection": "active clip at playhead drives tracking; clips may change over time",
            "program_output": False,
        },
        "studio": {
            "layout_builder": "app.vtuber.broadcast_studio_layout.build_vtuber_broadcast_studio_layout",
            "regions": ["program", "source_tracking", "avatar_mapping", "controls"],
            "program_output_background": ["capture", "media", "green_chroma"],
            "source_tracking_uses_performance_source": True,
        },
        "actions": [
            "vtuber.studio.open",
            "vtuber.avatar_target.summary",
            "vtuber.avatar_target.select",
            "vtuber.vrm.bridge_status",
            "vtuber.vrm.pose_stream_preview",
            "vtuber.performance_source.summary",
            "vtuber.performance_source.mark_media",
            "vtuber.performance_source.add_clip",
            "vtuber.program_output_contract",
            "actor.live2d.apply_performance_source",
        ],
        "rules": [
            "Performance Source is tracking input only.",
            "Program Output must resolve through program_output_contract().",
            "Performance Source clips are skipped as Program backgrounds.",
            "Use final_framing.model_view for avatar placement when available.",
        ],
    }


def mark_performance_source_metadata(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    data = dict(payload or {})
    data.update(
        {
            "schema": PERFORMANCE_SOURCE_SCHEMA,
            "vtuber_performance_source": True,
            "performance_source": True,
            "track_type": PERFORMANCE_SOURCE_TRACK_TYPE,
            "badge": PERFORMANCE_SOURCE_BADGE,
            "program_output": False,
        }
    )
    return data


def mark_performance_source_object(obj: Any) -> Any:
    """Stamp a track or clip object as an input-only VTuber performance source."""
    if obj is None:
        return obj
    values = {
        "vtuber_performance_source": True,
        "performance_source": True,
        "is_performance_source": True,
        "track_type": PERFORMANCE_SOURCE_TRACK_TYPE,
        "role": PERFORMANCE_SOURCE_TRACK_KIND,
        "badge": PERFORMANCE_SOURCE_BADGE,
        "program_output": False,
    }
    for key, value in values.items():
        try:
            setattr(obj, key, value)
        except Exception:
            pass
    try:
        meta = getattr(obj, "metadata", None)
        if isinstance(meta, Mapping):
            setattr(obj, "metadata", mark_performance_source_metadata(meta))
        elif meta is None:
            setattr(obj, "metadata", mark_performance_source_metadata())
    except Exception:
        pass
    return obj


def is_performance_source_payload(value: Any) -> bool:
    if isinstance(value, Mapping):
        if bool(value.get("vtuber_performance_source") or value.get("performance_source")):
            return True
        text = " ".join(
            str(value.get(key) or "")
            for key in ("schema", "track_type", "type", "kind", "role", "badge", "name", "label")
        ).casefold()
        return (
            PERFORMANCE_SOURCE_TRACK_TYPE in text
            or PERFORMANCE_SOURCE_TRACK_KIND in text
            or "performance source" in text
            or "퍼포먼스 소스" in text
        )
    text = str(value or "").casefold()
    return (
        PERFORMANCE_SOURCE_TRACK_TYPE in text
        or PERFORMANCE_SOURCE_TRACK_KIND in text
        or "performance source" in text
        or "퍼포먼스 소스" in text
    )


def is_performance_source_track(track: Any) -> bool:
    if track is None:
        return False
    if isinstance(track, Mapping):
        return is_performance_source_payload(track)
    if bool(
        getattr(track, "vtuber_performance_source", False)
        or getattr(track, "performance_source", False)
        or getattr(track, "is_performance_source", False)
    ):
        return True
    attrs = {
        "schema": getattr(track, "schema", ""),
        "track_type": getattr(track, "track_type", ""),
        "type": getattr(track, "type", ""),
        "kind": getattr(track, "kind", ""),
        "role": getattr(track, "role", ""),
        "name": getattr(track, "name", ""),
        "label": getattr(track, "label", ""),
    }
    return is_performance_source_payload(attrs)


def is_performance_source_clip(clip: Any) -> bool:
    if clip is None:
        return False
    if isinstance(clip, Mapping):
        return is_performance_source_payload(clip)
    if bool(
        getattr(clip, "vtuber_performance_source", False)
        or getattr(clip, "performance_source", False)
        or getattr(clip, "is_performance_source", False)
    ):
        return True
    meta = getattr(clip, "metadata", None)
    if is_performance_source_payload(meta):
        return True
    attrs = {
        "schema": getattr(clip, "schema", ""),
        "track_type": getattr(clip, "track_type", ""),
        "type": getattr(clip, "type", ""),
        "kind": getattr(clip, "kind", ""),
        "role": getattr(clip, "role", ""),
        "name": getattr(clip, "name", ""),
        "label": getattr(clip, "label", ""),
    }
    return is_performance_source_payload(attrs)


def is_capture_clip(clip: Any) -> bool:
    if clip is None:
        return False
    if isinstance(clip, Mapping):
        return _clip_kind_text(clip).find("capture") >= 0
    return any(
        "capture" in str(getattr(clip, attr, "") or "").casefold()
        for attr in ("source_kind", "media_kind", "clip_type", "type", "kind", "role", "label", "name")
    )


def active_clip_at(track: Any, time_ms: int) -> Any | None:
    clips = _track_clips(track)
    for clip in clips:
        if _clip_contains_time(clip, int(time_ms)):
            return clip
    return None


def active_performance_source_at(tracks: Iterable[Any], time_ms: int) -> dict[str, Any]:
    for track in reversed(list(tracks or [])):
        if not is_performance_source_track(track):
            continue
        clip = active_clip_at(track, time_ms)
        if clip is not None:
            return {
                "schema": PERFORMANCE_SOURCE_SCHEMA,
                "active": True,
                "track": track,
                "clip": clip,
                "source_path": _clip_path(clip),
                "badge": PERFORMANCE_SOURCE_BADGE,
                "program_output": False,
            }
    return {
        "schema": PERFORMANCE_SOURCE_SCHEMA,
        "active": False,
        "track": None,
        "clip": None,
        "source_path": "",
        "badge": PERFORMANCE_SOURCE_BADGE,
        "program_output": False,
    }


def choose_program_background_at(tracks: Iterable[Any], time_ms: int) -> dict[str, Any]:
    """Select the Program Output background without leaking performance sources."""
    active_rows: list[tuple[Any, Any]] = []
    skipped_performance: list[dict[str, Any]] = []
    for track in list(tracks or []):
        clip = active_clip_at(track, time_ms)
        if clip is None:
            continue
        if is_performance_source_track(track) or is_performance_source_clip(clip):
            skipped_performance.append(
                {
                    "track_label": _track_label(track),
                    "clip_label": _clip_label(clip),
                    "source_path": _clip_path(clip),
                }
            )
            continue
        active_rows.append((track, clip))

    for track, clip in reversed(active_rows):
        if is_capture_clip(clip) or _track_kind_text(track).find("capture") >= 0:
            return _background_row(
                PROGRAM_BACKGROUND_CAPTURE,
                track,
                clip,
                skipped_performance=skipped_performance,
            )
    for track, clip in reversed(active_rows):
        return _background_row(
            PROGRAM_BACKGROUND_MEDIA,
            track,
            clip,
            skipped_performance=skipped_performance,
        )
    return {
        "schema": PERFORMANCE_SOURCE_SCHEMA,
        "kind": PROGRAM_BACKGROUND_CHROMA,
        "source": "fallback",
        "track": None,
        "clip": None,
        "source_path": "",
        "color": list(GREEN_CHROMA_RGBA),
        "skipped_performance_sources": skipped_performance,
        "warnings": ["no program background clip; using green chroma"],
    }


def program_output_contract(tracks: Iterable[Any], time_ms: int) -> dict[str, Any]:
    background = choose_program_background_at(tracks, time_ms)
    performance = active_performance_source_at(tracks, time_ms)
    return {
        "schema": PERFORMANCE_SOURCE_SCHEMA,
        "time_ms": int(time_ms),
        "program_background": _public_background(background),
        "performance_source": _public_performance(performance),
        "rules": [
            "capture clips win as Program background",
            "normal video/image clips are fallback Program backgrounds",
            "green chroma is used when no Program background exists",
            "performance-source clips drive avatar tracking only",
        ],
        "safe_output": True,
    }


def _background_row(kind: str, track: Any, clip: Any, *, skipped_performance: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": PERFORMANCE_SOURCE_SCHEMA,
        "kind": kind,
        "source": "timeline",
        "track": track,
        "clip": clip,
        "track_label": _track_label(track),
        "clip_label": _clip_label(clip),
        "source_path": _clip_path(clip),
        "color": None,
        "skipped_performance_sources": list(skipped_performance),
        "warnings": [],
    }


def _public_background(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": str(row.get("kind") or ""),
        "source": str(row.get("source") or ""),
        "track_label": str(row.get("track_label") or ""),
        "clip_label": str(row.get("clip_label") or ""),
        "source_path": str(row.get("source_path") or ""),
        "color": row.get("color"),
        "skipped_performance_sources": list(row.get("skipped_performance_sources") or []),
        "warnings": list(row.get("warnings") or []),
    }


def _public_performance(row: Mapping[str, Any]) -> dict[str, Any]:
    clip = row.get("clip")
    track = row.get("track")
    return {
        "active": bool(row.get("active", False)),
        "track_label": _track_label(track),
        "clip_label": _clip_label(clip),
        "source_path": str(row.get("source_path") or ""),
        "badge": PERFORMANCE_SOURCE_BADGE,
        "program_output": False,
    }


def _track_clips(track: Any) -> list[Any]:
    if track is None:
        return []
    if isinstance(track, Mapping):
        value = track.get("clips") or track.get("items") or []
    else:
        value = getattr(track, "clips", None) or getattr(track, "items", None) or []
        if callable(value):
            value = value()
    return list(value or [])


def _clip_contains_time(clip: Any, time_ms: int) -> bool:
    contains = getattr(clip, "contains_timeline_ms", None)
    if callable(contains):
        try:
            return bool(contains(int(time_ms)))
        except Exception:
            pass
    start = _first_int(clip, ("timeline_in_ms", "offset_ms", "start_ms", "in_ms"), default=0)
    end = _first_int(clip, ("timeline_out_ms", "end_ms", "out_ms"), default=None)
    if end is None:
        duration = _first_int(clip, ("effective_length_ms", "duration_ms", "length_ms"), default=0)
        end = start + max(0, duration)
    return int(start) <= int(time_ms) < int(end)


def _first_int(obj: Any, keys: tuple[str, ...], *, default: int | None) -> int | None:
    for key in keys:
        value = obj.get(key) if isinstance(obj, Mapping) else getattr(obj, key, None)
        if value is None:
            continue
        if callable(value):
            try:
                value = value()
            except Exception:
                continue
        try:
            return int(value)
        except Exception:
            continue
    return default


def _clip_path(clip: Any) -> str:
    if clip is None:
        return ""
    value = clip.get("source_path") if isinstance(clip, Mapping) else getattr(clip, "source_path", "")
    if value is None:
        return ""
    try:
        return str(Path(value))
    except Exception:
        return str(value or "")


def _clip_label(clip: Any) -> str:
    if clip is None:
        return ""
    if isinstance(clip, Mapping):
        return str(clip.get("label") or clip.get("name") or Path(str(clip.get("source_path") or "")).name or "")
    return str(
        getattr(clip, "display_name", "")
        or getattr(clip, "label", "")
        or getattr(clip, "name", "")
        or Path(str(getattr(clip, "source_path", "") or "")).name
        or ""
    )


def _track_label(track: Any) -> str:
    if track is None:
        return ""
    if isinstance(track, Mapping):
        return str(track.get("label") or track.get("name") or track.get("id") or "")
    return str(getattr(track, "label", "") or getattr(track, "name", "") or getattr(track, "id", "") or "")


def _track_kind_text(track: Any) -> str:
    if isinstance(track, Mapping):
        return " ".join(str(track.get(key) or "") for key in ("type", "kind", "role", "track_type", "label", "name")).casefold()
    return " ".join(
        str(getattr(track, key, "") or "")
        for key in ("type", "kind", "role", "track_type", "label", "name")
    ).casefold()


def _clip_kind_text(clip: Mapping[str, Any]) -> str:
    return " ".join(str(clip.get(key) or "") for key in ("type", "kind", "role", "clip_type", "source_kind", "media_kind", "label", "name")).casefold()
