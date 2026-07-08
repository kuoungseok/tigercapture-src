"""TigerCapture Project I/O — save and load .tgp files.

A ``.tgp`` file is a plain JSON document that captures every piece of
editor state so sessions can be resumed.  The format is intentionally
human-readable: paths are absolute, numeric values are plain numbers,
and nothing is binary-encoded.

What IS saved
~~~~~~~~~~~~~
- Video tracks: source path, clip list (trim / timeline positions),
  cuts, fades, zoom actors, speed segments, typography actors,
  node-graph layout + connections + blur params + masks.
- Audio tracks: source path, clip list (offsets / trims / fades /
  volume envelope / sound-editor effects), master volume.
- Subtitles, global IN/OUT markers, timeline px-per-sec, playhead ms.

What is NOT saved (regenerated on load)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- Thumbnails / waveform peaks  — extracted asynchronously after load.
- Node-level ColorGrade       — always starts at identity each session
  (intentional: prevents stale wheel-drag values from silently
  polluting the next session; see ``feedback_nodegraph_grade_persistence``).
- OpenGL / player caches      — rebuilt automatically.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# File extension / version
# ---------------------------------------------------------------------------

EXTENSION = ".tgp"
FORMAT_VERSION = "1.1"

# QSettings key under the shared TigerCapture / TigerCapture
# organisation/app pair used by app/i18n.py. Keeps "last project" in
# the same place the language preference already lives.
_LAST_PROJECT_KEY = "video_editor/last_project_path"
_RECENT_PROJECTS_KEY = "video_editor/recent_project_paths"
_RECENT_PROJECT_LIMIT = 12
_PROJECT_LOAD_HDR_PROBE_ENV = "TIGERCAPTURE_PROJECT_LOAD_HDR_PROBE"


def _project_load_hdr_probe_enabled() -> bool:
    value = str(os.environ.get(_PROJECT_LOAD_HDR_PROBE_ENV, "")).strip().lower()
    return value in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------------------
# Last-project memory (used by the title screen's "resume?" prompt)
# ---------------------------------------------------------------------------

def remember_last_project(path: Path | str | None) -> None:
    """Stash the most recently saved / autosaved project path in
    QSettings so the next launch can offer to resume it. Passing
    ``None`` clears the memory (e.g. after a New Project)."""
    from PySide6.QtCore import QSettings

    settings = QSettings("TigerCapture", "TigerCapture")
    if path is None:
        settings.remove(_LAST_PROJECT_KEY)
    else:
        resolved = str(Path(path).resolve())
        settings.setValue(_LAST_PROJECT_KEY, resolved)
        _store_recent_project(settings, resolved)
    settings.sync()


def _settings_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    return []


def _store_recent_project(settings, path: str) -> None:
    recent = _settings_string_list(settings.value(_RECENT_PROJECTS_KEY, []))
    recent = [item for item in recent if item != path]
    recent.insert(0, path)
    settings.setValue(_RECENT_PROJECTS_KEY, recent[:_RECENT_PROJECT_LIMIT])


def load_last_project_path() -> Path | None:
    """Return the previously-remembered project path, or ``None`` if
    there isn't one or the file no longer exists on disk."""
    from PySide6.QtCore import QSettings

    settings = QSettings("TigerCapture", "TigerCapture")
    value = settings.value(_LAST_PROJECT_KEY, None)
    if not isinstance(value, str) or not value:
        return None
    p = Path(value)
    return p if p.is_file() else None


def load_recent_project_paths(limit: int = 5) -> list[Path]:
    """Return existing projects remembered through save/open/autosave.

    Missing files are filtered out so the launcher never shows dead cards.
    """
    from PySide6.QtCore import QSettings

    settings = QSettings("TigerCapture", "TigerCapture")
    paths = _settings_string_list(settings.value(_RECENT_PROJECTS_KEY, []))
    out: list[Path] = []
    seen: set[str] = set()
    for raw in paths:
        p = Path(raw)
        key = str(p)
        if "~autosave" in p.stem or p.parent.name == ".tigercapture_recovery":
            continue
        if key in seen or not p.is_file():
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= max(0, int(limit)):
            break
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _p(path) -> str | None:
    """Serialise a Path (or None/string) to an absolute string."""
    if path is None:
        return None
    try:
        return str(Path(path).resolve())
    except Exception:
        return str(path)


def _fade_to_dict(fade) -> dict:
    return {
        "start_ms": int(fade.start_ms),
        "end_ms": int(fade.end_ms),
        "kind": getattr(fade, "kind", "both"),
    }


def _zoom_actor_to_dict(z) -> dict:
    return {
        "id": int(z.id),
        "start_ms": int(z.start_ms),
        "end_ms": int(z.end_ms),
        "zoom_in_ms": int(z.zoom_in_ms),
        "zoom_out_ms": int(z.zoom_out_ms),
        "target_x": float(getattr(z, "target_x", 0.5)),
        "target_y": float(getattr(z, "target_y", 0.5)),
        "target_w": float(getattr(z, "target_w", 0.5)),
        "target_h": float(getattr(z, "target_h", 0.5)),
        "easing": str(getattr(z, "easing", "smooth_pop") or "smooth_pop"),
        "motion_blur": float(getattr(z, "motion_blur", 0.0) or 0.0),
    }


def _speed_segment_to_dict(s) -> dict:
    # Use to_dict() if available (SpeedSegment now carries ease_in/ease_out);
    # fall back to a plain dict for any legacy-style object.
    if hasattr(s, "to_dict"):
        return s.to_dict()
    return {
        "start_ms": int(s.start_ms),
        "end_ms": int(s.end_ms),
        "speed": float(s.speed),
    }


def _typo_actor_to_dict(a) -> dict:
    return {
        "start_ms": int(getattr(a, "start_ms", 0)),
        "end_ms": int(getattr(a, "end_ms", 0)),
        "text": str(getattr(a, "text", "")),
        "font_size": int(getattr(a, "font_size", 48)),
        "color": str(getattr(a, "color", "#ffffff")),
        "bg_color": str(getattr(a, "bg_color", "")),
        "x_norm": float(getattr(a, "x_norm", 0.5)),
        "y_norm": float(getattr(a, "y_norm", 0.5)),
        "preset_id": str(getattr(a, "preset_id", "")),
    }


def _effect_param_to_dict(value) -> dict | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            return None
    return None


def _video_clip_to_dict(c) -> dict:
    masks_data: list = []
    for m in getattr(c, "masks", []) or []:
        try:
            masks_data.append(m.to_dict())
        except Exception:
            pass
    node_graph = None
    ng = getattr(c, "node_graph", None)
    if ng is not None:
        try:
            node_graph = {
                "color": {
                    "grade": ng.color.grade.to_dict()
                    if ng.color and ng.color.grade else None,
                }
            }
        except Exception:
            pass
    return {
        "id": int(c.id),
        "source_path": _p(c.source_path),
        "performance_source": bool(getattr(c, "performance_source", False)),
        "vtuber_performance_source": bool(getattr(c, "vtuber_performance_source", False)),
        "track_type": str(getattr(c, "track_type", "") or ""),
        "program_output": bool(getattr(c, "program_output", True)),
        "source_duration_ms": int(getattr(c, "source_duration_ms", 0)),
        "timeline_in_ms": int(c.timeline_in_ms),
        "source_in_ms": int(getattr(c, "source_in_ms", 0)),
        "source_out_ms": int(getattr(c, "source_out_ms", 0)),
        "fades": [_fade_to_dict(f) for f in getattr(c, "fades", [])],
        "zoom_actors": [_zoom_actor_to_dict(z) for z in getattr(c, "zoom_actors", [])],
        "typography_actors": [_typo_actor_to_dict(a) for a in getattr(c, "typography_actors", [])],
        "speed_segments": [_speed_segment_to_dict(s) for s in getattr(c, "speed_segments", [])],
        "masks": masks_data,
        "node_graph": node_graph,
        "transition_out_type": str(getattr(c, "transition_out_type", "")),
        "transition_out_ms": int(getattr(c, "transition_out_ms", 500)),
        "transition_preset_meta": dict(getattr(c, "transition_preset_meta", {}) or {}),
        "cursor_events": list(getattr(c, "cursor_events", []) or []),
        "screenstudio_polish": dict(getattr(c, "screenstudio_polish", {}) or {}),
        "video_filters": _effect_param_to_dict(getattr(c, "video_filters", None)),
        "chroma_key": _effect_param_to_dict(getattr(c, "chroma_key", None)),
        "stabilizer": (
            getattr(c, "stabilizer", None).to_dict()
            if getattr(c, "stabilizer", None) is not None else None
        ),
        "bg_removal": _effect_param_to_dict(getattr(c, "bg_removal", None)),
        "disabled_video_filters": _effect_param_to_dict(getattr(c, "disabled_video_filters", None)),
        "disabled_chroma_key": _effect_param_to_dict(getattr(c, "disabled_chroma_key", None)),
        "disabled_bg_removal": _effect_param_to_dict(getattr(c, "disabled_bg_removal", None)),
        "linked_audio_id": getattr(c, "linked_audio_id", None),
        "compound_group_id": getattr(c, "compound_group_id", None),
        "timecode_ms": getattr(c, "timecode_ms", None),
        "waveform_sync_peak_ms": getattr(c, "waveform_sync_peak_ms", None),
        "audio_sync_offset_ms": getattr(c, "audio_sync_offset_ms", None),
        "compound_group_name": str(getattr(c, "compound_group_name", "") or ""),
        "connected_parent_track_id": getattr(c, "connected_parent_track_id", None),
        "connected_parent_clip_id": getattr(c, "connected_parent_clip_id", None),
        "connected_offset_ms": int(getattr(c, "connected_offset_ms", 0) or 0),
        "clip_role": str(getattr(c, "clip_role", "") or ""),
        "role_color": str(getattr(c, "role_color", "") or ""),
        "audition_group_id": getattr(c, "audition_group_id", None),
        "audition_name": str(getattr(c, "audition_name", "") or ""),
        "audition_active_take_id": str(getattr(c, "audition_active_take_id", "") or ""),
        "audition_takes": [
            dict(take)
            for take in (getattr(c, "audition_takes", None) or [])
            if isinstance(take, dict)
        ],
        "nested_sequence_id": getattr(c, "nested_sequence_id", None),
        "nested_sequence_name": str(getattr(c, "nested_sequence_name", "") or ""),
        "nested_child_clips": [
            _video_clip_to_dict(child)
            for child in (getattr(c, "nested_child_clips", None) or [])
        ],
        "nested_child_tracks": [
            [_video_clip_to_dict(child) for child in child_track]
            for child_track in (getattr(c, "nested_child_tracks", None) or [])
        ],
        "nested_audio_tracks": [
            [_audio_clip_to_dict(child) for child in child_track]
            for child_track in (getattr(c, "nested_audio_tracks", None) or [])
        ],
        "nested_spine_actor_tracks": [
            _actor_track_to_dict(track)
            for track in (getattr(c, "nested_spine_actor_tracks", None) or [])
        ],
        "nested_live2d_actor_tracks": [
            _actor_track_to_dict(track)
            for track in (getattr(c, "nested_live2d_actor_tracks", None) or [])
        ],
    }


def _audio_clip_to_dict(c) -> dict:
    fades_data = [_fade_to_dict(f) for f in getattr(c, "fades", [])]
    return {
        "id": int(c.id),
        "source_path": _p(c.source_path),
        "duration_ms": int(getattr(c, "duration_ms", 0)),
        "offset_ms": int(c.offset_ms),
        "trim_start_ms": int(c.trim_start_ms),
        "trim_end_ms": int(c.trim_end_ms),
        "fade_in_ms": int(c.fade_in_ms),
        "fade_out_ms": int(c.fade_out_ms),
        "fades": fades_data,
        "volume_points": list(getattr(c, "volume_points", None) or []),
        "effects": dict(getattr(c, "effects", {}) or {}),
        "gain": float(getattr(c, "gain", 1.0)),
    }


def _audio_clip_from_dict(cd: dict):
    from app.audio_tracks import AudioClip, default_effects_state

    src = cd.get("source_path")
    if not src:
        return None
    src_path = Path(src)
    if not src_path.exists():
        return None
    clip = AudioClip(
        id=int(cd.get("id", 1)),
        source_path=src_path,
        duration_ms=int(cd.get("duration_ms", 0)),
        offset_ms=int(cd.get("offset_ms", 0)),
        trim_start_ms=int(cd.get("trim_start_ms", 0)),
        trim_end_ms=int(cd.get("trim_end_ms", 0)),
        fade_in_ms=int(cd.get("fade_in_ms", 0)),
        fade_out_ms=int(cd.get("fade_out_ms", 0)),
    )
    try:
        from app.timeline_model import FadeSegment
        for fd in cd.get("fades", []) or []:
            fade = FadeSegment(int(fd["start_ms"]), int(fd["end_ms"]))
            fade.kind = str(fd.get("kind", "both"))
            clip.fades.append(fade)
    except Exception:
        pass
    clip.volume_points = list(cd.get("volume_points", []) or [])
    clip.effects = dict(cd.get("effects", {}) or default_effects_state())
    clip.gain = float(cd.get("gain", 1.0))
    if clip.duration_ms <= 0:
        try:
            from app.audio_tracks import probe_audio_duration_ms
            clip.duration_ms = probe_audio_duration_ms(src_path)
        except Exception:
            pass
    return clip


def _clean_dataclass_payload(v):
    if isinstance(v, dict):
        return {
            k: _clean_dataclass_payload(x)
            for k, x in v.items()
            if not str(k).startswith("_")
        }
    if isinstance(v, list):
        return [_clean_dataclass_payload(x) for x in v]
    return v


def _actor_track_to_dict(track) -> dict:
    from dataclasses import asdict

    return _clean_dataclass_payload(asdict(track))


def _spine_actor_track_from_dict(data: dict):
    from app.spine_editor.actor_track import SpineActorClip, SpineActorTrack

    td = dict(data or {})
    clips_data = td.pop("clips", []) or []
    track = SpineActorTrack(**td)
    track.clips = [SpineActorClip(**dict(cd)) for cd in clips_data]
    return track


def _live2d_actor_track_from_dict(data: dict):
    from app.live2d.actor_track import (
        Live2DActorClip,
        Live2DActorTrack,
        Live2DBlend,
        Live2DKeyframe,
    )

    td = dict(data or {})
    clips_data = td.pop("clips", []) or []
    blends_data = td.pop("blends", []) or []
    track = Live2DActorTrack(**td)
    for raw_cd in clips_data:
        cd = dict(raw_cd or {})
        kfs = {
            kf_name: [Live2DKeyframe(**dict(k)) for k in cd.pop(kf_name, []) or []]
            for kf_name in ("kf_pos_x", "kf_pos_y", "kf_scale", "kf_opacity")
        }
        clip = Live2DActorClip(**cd)
        clip.kf_pos_x = kfs["kf_pos_x"]
        clip.kf_pos_y = kfs["kf_pos_y"]
        clip.kf_scale = kfs["kf_scale"]
        clip.kf_opacity = kfs["kf_opacity"]
        track.clips.append(clip)
    track.blends = [Live2DBlend(**dict(bd)) for bd in blends_data]
    return track


def _subtitle_to_dict(s) -> dict:
    return {
        "text": str(s.text),
        "start_ms": int(s.start_ms),
        "end_ms": int(s.end_ms),
        "show_box": bool(getattr(s, "show_box", True)),
        "style": dict(getattr(s, "style", {}) or {}),
    }


# ---------------------------------------------------------------------------
# SAVE
# ---------------------------------------------------------------------------

def save_project(editor, path: str | Path) -> None:
    """Serialise the full editor state to ``path`` as JSON."""
    path = Path(path)
    if path.suffix.lower() != EXTENSION:
        path = path.with_suffix(EXTENSION)
    project_settings = dict(getattr(editor, "_project_settings", {}))
    if "color_management" not in project_settings:
        try:
            from app.color_management import default_color_management

            project_settings["color_management"] = default_color_management().to_dict()
        except Exception:
            pass

    doc: dict[str, Any] = {
        "version": FORMAT_VERSION,
        "app": "TigerCapture",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "px_per_sec": float(getattr(editor, "_px_per_sec", 40.0)),
        "playhead_ms": int(editor._player.position()),
        "global_in_ms": int(getattr(editor, "_global_in_ms", -1)),
        "global_out_ms": int(getattr(editor, "_global_out_ms", -1)),
        "project_settings": project_settings,
        "video_tracks": [],
        "audio_tracks": [],
        "subtitles": [],
    }

    # ---- Video tracks ----
    for track in getattr(editor, "_tracks", []):
        vt: dict = {
            "id": int(track.id),
            "source_path": _p(track.source_path),
            "label": str(getattr(track, "label", "") or ""),
            "track_type": str(getattr(track, "track_type", "") or ""),
            "performance_source": bool(getattr(track, "performance_source", False)),
            "vtuber_performance_source": bool(getattr(track, "vtuber_performance_source", False)),
            "program_output": bool(getattr(track, "program_output", True)),
            "display_name": str(getattr(track, "display_name", "")),
            "offset_ms": int(getattr(track, "offset_ms", 0)),
            "clips": [_video_clip_to_dict(c) for c in (getattr(track, "clips", None) or [])],
            "fades": [_fade_to_dict(f) for f in getattr(track, "fades", [])],
            "zoom_actors": [_zoom_actor_to_dict(z) for z in getattr(track, "zoom_actors", [])],
            "speed_segments": [_speed_segment_to_dict(s) for s in getattr(track, "speed_segments", [])],
            "typography_actors": [_typo_actor_to_dict(a) for a in getattr(track, "typography_actors", [])],
            "node_graph_view_data": dict(getattr(track, "node_graph_view_data", None) or {}),
            "preview_color_compare_mode": str(getattr(track, "preview_color_compare_mode", "") or ""),
            "preview_compare_labels_enabled": bool(getattr(track, "preview_compare_labels_enabled", True)),
            "cursor_events": list(getattr(track, "cursor_events", []) or []),
            "screenstudio_polish": dict(getattr(track, "screenstudio_polish", {}) or {}),
            # PIP compositing state.
            "pip_enabled": bool(getattr(track, "pip_enabled", False)),
            "pip_x": float(getattr(track, "pip_x", 0.5)),
            "pip_y": float(getattr(track, "pip_y", 0.5)),
            "pip_scale": float(getattr(track, "pip_scale", 0.3)),
            "pip_opacity": float(getattr(track, "pip_opacity", 1.0)),
            "pip_keyframes": list(getattr(track, "pip_keyframes", [])),
        }
        doc["video_tracks"].append(vt)

    # ---- Audio tracks ----
    for atrack in getattr(editor, "_audio_tracks", []):
        at: dict = {
            "id": int(atrack.id),
            "display_name": str(getattr(atrack, "display_name", "") or ""),
            "volume": float(getattr(atrack, "volume", 1.0)),
            "pan": float(getattr(atrack, "pan", 0.0)),
            "muted": bool(getattr(atrack, "muted", False)),
            "solo": bool(getattr(atrack, "solo", False)),
            "label": str(getattr(atrack, "label", "") or ""),
            "bus_id": str(getattr(atrack, "bus_id", "master") or "master"),
            "track_type": str(getattr(atrack, "track_type", "") or ""),
            "insert_slots": list(getattr(atrack, "insert_slots", None) or []),
            "sends": dict(getattr(atrack, "sends", None) or {}),
            "automation_read": bool(getattr(atrack, "automation_read", True)),
            "automation_write": bool(getattr(atrack, "automation_write", False)),
            "automation_points": list(getattr(atrack, "automation_points", None) or []),
            "automation_lanes": dict(getattr(atrack, "automation_lanes", None) or {}),
            "clips": [_audio_clip_to_dict(c) for c in (atrack.clips or [])],
        }
        doc["audio_tracks"].append(at)
    try:
        doc["audio_mixer_snapshots"] = list(getattr(editor, "_audio_mixer_snapshots", None) or [])
    except Exception:
        doc["audio_mixer_snapshots"] = []

    # ---- Subtitles ----
    try:
        sub_panel = editor._subtitle_panel
        for sub in sub_panel.layer.items():
            doc["subtitles"].append(_subtitle_to_dict(sub))
    except Exception:
        pass

    # ---- Media pool ---- (just the list of registered file paths;
    # thumbnails / duration badges are re-derived on load).
    try:
        pool = getattr(editor, "_media_pool", None)
        if pool is not None and hasattr(pool, "items"):
            doc["media_pool"] = [
                str(p) for p in pool.items()
                if isinstance(p, str) and p
            ]
            metadata = getattr(pool, "media_pool_metadata", None)
            if callable(metadata):
                doc["media_pool_metadata"] = list(metadata())
    except Exception:
        pass

    # ---- Paint strokes / speech bubbles / stickers / markers ----
    # These are the "user-created overlays" — easy to lose, impossible
    # to recreate without saved state.
    from dataclasses import asdict as _asdict
    try:
        doc["strokes"] = [_asdict(s) for s in (getattr(editor, "_strokes", None) or [])]
    except Exception:
        doc["strokes"] = []
    try:
        doc["bubbles"] = [_asdict(b) for b in (getattr(editor, "_bubbles", None) or [])]
    except Exception:
        doc["bubbles"] = []
    try:
        doc["stickers"] = [_asdict(s) for s in (getattr(editor, "_stickers", None) or [])]
    except Exception:
        doc["stickers"] = []
    try:
        doc["timeline_markers"] = list(getattr(editor, "_timeline_markers", None) or [])
    except Exception:
        doc["timeline_markers"] = []
    try:
        doc["creator_assist_bundle"] = dict(getattr(editor, "_creator_assist_bundle", None) or {})
    except Exception:
        doc["creator_assist_bundle"] = {}
    try:
        doc["capcut_creator_package"] = dict(getattr(editor, "_capcut_creator_package", None) or {})
    except Exception:
        doc["capcut_creator_package"] = {}
    try:
        doc["capcut_short_ranges"] = list(getattr(editor, "_capcut_short_ranges", None) or [])
    except Exception:
        doc["capcut_short_ranges"] = []
    try:
        doc["render_queue_jobs"] = list(getattr(editor, "_capcut_render_queue_jobs", None) or [])
    except Exception:
        doc["render_queue_jobs"] = []

    # ---- LUT + export / proxy settings ----
    doc["lut"] = {
        "path": str(getattr(editor, "_lut_path", "") or ""),
        "strength": float(getattr(editor, "_lut_strength", 1.0)),
    }
    _exp_res = getattr(editor, "_export_resolution", None)
    doc["export"] = {
        "quality_id":       str(getattr(editor, "_export_quality_id", "") or ""),
        "format_id":        str(getattr(editor, "_export_format_id", "") or ""),
        "audio_quality_id": str(getattr(editor, "_audio_export_quality_id", "") or ""),
        "resolution":       list(_exp_res) if _exp_res else None,
        "fps":              float(getattr(editor, "_export_fps", 0.0) or 0.0),
    }
    doc["proxy"] = {
        "enabled": bool(getattr(editor, "_proxy_mode", False)),
        "dir":     _p(getattr(editor, "_proxy_dir", None)),
    }

    # ---- Spine / Live2D actor tracks ----
    try:
        doc["spine_actor_tracks"] = [
            _actor_track_to_dict(t)
            for t in getattr(editor, "_spine_actor_tracks", None) or []
        ]
    except Exception:
        doc["spine_actor_tracks"] = []
    try:
        doc["live2d_actor_tracks"] = [
            _actor_track_to_dict(t)
            for t in getattr(editor, "_live2d_actor_tracks", None) or []
        ]
    except Exception:
        doc["live2d_actor_tracks"] = []
    try:
        from app.ar_pbr.schema import normalize_ar_tracks

        doc["ar_pbr_tracks"] = normalize_ar_tracks(
            getattr(editor, "_ar_pbr_tracks", None) or []
        )
    except Exception:
        doc["ar_pbr_tracks"] = []
    try:
        from app.mmd.schema import normalize_mmd_tracks

        doc["mmd_tracks"] = normalize_mmd_tracks(
            getattr(editor, "_mmd_tracks", None) or []
        )
    except Exception:
        doc["mmd_tracks"] = []
    try:
        doc["next_actor_id"]   = int(getattr(editor, "_next_actor_id", 1))
        doc["next_live2d_id"]  = int(getattr(editor, "_next_live2d_id", 1))
        doc["next_ar_pbr_id"]  = int(getattr(editor, "_next_ar_pbr_id", 1))
        doc["next_mmd_id"]     = int(getattr(editor, "_next_mmd_id", 1))
    except Exception:
        pass

    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[project] saved → {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# LOAD
# ---------------------------------------------------------------------------

def load_project(editor, path: str | Path) -> None:
    """Restore editor state from a .tgp file.  Clears the current session
    first; any unsaved work is lost (callers should prompt first)."""
    import traceback
    path = Path(path)
    doc: dict = json.loads(path.read_text(encoding="utf-8"))
    version = doc.get("version", "1.0")

    # 1. Clear current session state.
    _clear_editor(editor)

    # 1a. Restore project settings (canvas ratio, resolution, fps).
    ps = doc.get("project_settings", {})
    if ps:
        if "color_management" not in ps:
            try:
                from app.color_management import default_color_management

                ps["color_management"] = default_color_management().to_dict()
            except Exception:
                pass
        editor._project_settings = dict(ps)
        if "fps" in ps:
            editor._player.REFERENCE_FPS = float(ps["fps"])
        if "canvas_width" in ps and "canvas_height" in ps:
            editor._export_resolution = (int(ps["canvas_width"]), int(ps["canvas_height"]))
        if "fps" in ps:
            editor._export_fps = float(ps["fps"])
        try:
            name = ps.get("name", "")
            ratio = ps.get("ratio_label", "")
            w = ps.get("canvas_width", "")
            h = ps.get("canvas_height", "")
            fps = ps.get("fps", "")
            if ratio:
                editor.setWindowTitle(
                    f"Tiger Studio — {name}  [{ratio}  {w}×{h}  {float(fps):.3g}fps]"
                )
        except Exception:
            pass

    # 2. Restore video tracks.
    max_vid_id = 0
    for vt_data in doc.get("video_tracks", []):
        src = vt_data.get("source_path")
        if not src and not vt_data.get("clips"):
            continue
        src_path = Path(src) if src else None
        if src_path is not None and not src_path.exists():
            print(f"[project] warning: source missing {src_path}", file=sys.stderr)
            continue
        _load_video_track(editor, vt_data, src_path)
        max_vid_id = max(max_vid_id, int(vt_data.get("id", 0)))

    if max_vid_id >= editor._next_track_id:
        editor._next_track_id = max_vid_id + 1

    # 3. Restore audio tracks.
    for at_data in doc.get("audio_tracks", []):
        _load_audio_track(editor, at_data)
    try:
        editor._audio_mixer_snapshots = list(doc.get("audio_mixer_snapshots", []) or [])
    except Exception:
        editor._audio_mixer_snapshots = []

    # 4. Restore subtitles.
    _load_subtitles(editor, doc.get("subtitles", []))

    # 5. Restore timeline state.
    px = float(doc.get("px_per_sec", 40.0))
    current = getattr(editor, "_px_per_sec", 40.0)
    if current > 0 and abs(px - current) > 0.1:
        editor._change_zoom(px / current)

    gin = int(doc.get("global_in_ms", -1))
    gout = int(doc.get("global_out_ms", -1))
    if gin >= 0:
        editor._set_global_in(gin)
    if gout >= 0:
        editor._set_global_out(gout)

    editor._refresh_player_tracks()

    # Backfill source_duration_ms for video clips that were saved as 0
    # (can happen when the clip was built before the cv2 cap was open).
    # After _refresh_player_tracks the cap is open and track.duration_ms
    # is set — copy it to each clip whose own duration is still 0.
    for track in editor._tracks:
        if track.duration_ms > 0:
            for clip in getattr(track, "clips", []) or []:
                if getattr(clip, "source_duration_ms", 0) == 0:
                    clip.source_duration_ms = track.duration_ms
                if getattr(clip, "source_out_ms", 0) == 0:
                    clip.source_out_ms = track.duration_ms

    # Force all video rows to recalculate widths and repaint so
    # thumbnails land in the right positions.
    for row in editor._track_rows.values():
        try:
            row._recalc_width()
            row.update()
        except Exception:
            pass
    # Audio rows too.
    for row in editor._audio_rows.values():
        try:
            row.update()
        except Exception:
            pass

    playhead = int(doc.get("playhead_ms", 0))
    editor._player.set_position(playhead)

    # ---- Media pool restore ---- (paths only; thumbnails / duration
    # badges are regenerated by ``add_path`` itself).
    pool = getattr(editor, "_media_pool", None)
    pool_paths = doc.get("media_pool") or []
    if pool is not None and pool_paths:
        for p in pool_paths:
            try:
                path_value = p.get("path") if isinstance(p, dict) else p
                pool.add_path(path_value)
            except Exception:
                pass
    if pool is not None:
        try:
            perf_paths = set()
            for row in doc.get("media_pool_metadata") or []:
                if not isinstance(row, dict):
                    continue
                if bool(row.get("performance_source")) and row.get("path"):
                    perf_paths.add(str(row.get("path")))
            for row in pool_paths:
                if isinstance(row, dict) and bool(row.get("performance_source")) and row.get("path"):
                    perf_paths.add(str(row.get("path")))
            setter = getattr(pool, "set_performance_source_path", None)
            if callable(setter):
                for p in sorted(perf_paths):
                    setter(p, True)
        except Exception:
            pass

    # ---- Overlays: strokes / bubbles / stickers / markers ----
    from app.drawing import SpeechBubble, Sticker, Stroke
    if hasattr(editor, "_strokes"):
        editor._strokes = []
        for sd in doc.get("strokes") or []:
            try:
                editor._strokes.append(Stroke(
                    points=[tuple(p) for p in sd.get("points") or []],
                    color=tuple(sd.get("color") or (255, 50, 50)),
                    opacity=int(sd.get("opacity", 255)),
                    width_px=float(sd.get("width_px", 4.0)),
                    start_ms=int(sd.get("start_ms", 0)),
                    end_ms=sd.get("end_ms"),
                ))
            except Exception:
                pass
        try:
            editor._drawing_canvas.update()
        except Exception:
            pass

    if hasattr(editor, "_bubbles"):
        editor._bubbles = []
        for bd in doc.get("bubbles") or []:
            try:
                editor._bubbles.append(SpeechBubble(**bd))
            except Exception:
                pass

    if hasattr(editor, "_stickers"):
        editor._stickers = []
        for sd in doc.get("stickers") or []:
            try:
                editor._stickers.append(Sticker(**sd))
            except Exception:
                pass

    # Spawn the interactive widgets for bubbles + stickers (strokes
    # render via DrawingCanvas paintEvent directly, so no widgets to
    # spawn for those).
    try:
        if hasattr(editor, "_spawn_bubble_item"):
            for bubble in getattr(editor, "_bubbles", None) or []:
                editor._spawn_bubble_item(bubble)
        if hasattr(editor, "_spawn_sticker_item"):
            for sticker in getattr(editor, "_stickers", None) or []:
                editor._spawn_sticker_item(sticker)
    except Exception:
        pass

    # Timeline markers (list of {"ms", "color", "label"}).
    if hasattr(editor, "_timeline_markers"):
        editor._timeline_markers = list(doc.get("timeline_markers") or [])
        try:
            editor._sync_markers_to_ruler()
        except Exception:
            pass
    if hasattr(editor, "_creator_assist_bundle"):
        editor._creator_assist_bundle = dict(doc.get("creator_assist_bundle") or {})
    if hasattr(editor, "_capcut_creator_package"):
        editor._capcut_creator_package = dict(doc.get("capcut_creator_package") or {})
    if hasattr(editor, "_capcut_short_ranges"):
        editor._capcut_short_ranges = list(doc.get("capcut_short_ranges") or [])
    if hasattr(editor, "_capcut_render_queue_jobs"):
        editor._capcut_render_queue_jobs = list(doc.get("render_queue_jobs") or [])
    panel = getattr(editor, "_creator_assist_panel", None)
    if panel is not None and hasattr(panel, "set_bundle"):
        try:
            panel.set_bundle(dict(doc.get("creator_assist_bundle") or {}))
        except Exception:
            pass

    # ---- LUT restore (path + strength → reload via helper) ----
    lut_state = doc.get("lut") or {}
    lut_path = lut_state.get("path") or ""
    lut_strength = float(lut_state.get("strength", 1.0))
    if hasattr(editor, "_lut_strength"):
        editor._lut_strength = lut_strength
    if lut_path and hasattr(editor, "_load_lut_from_path"):
        try:
            if Path(lut_path).is_file():
                editor._load_lut_from_path(lut_path)
        except Exception:
            pass

    # ---- Export settings ----
    exp = doc.get("export") or {}
    qid = exp.get("quality_id")
    fid = exp.get("format_id")
    aqid = exp.get("audio_quality_id")
    if qid and hasattr(editor, "_export_quality_id"):
        editor._export_quality_id = qid
        try:
            editor._refresh_quality_btn_label()
            editor._build_quality_menu()
        except Exception:
            pass
    if fid and hasattr(editor, "_export_format_id"):
        editor._export_format_id = fid
        try:
            editor._refresh_format_btn_label()
            editor._build_format_menu()
        except Exception:
            pass
    if aqid and hasattr(editor, "_audio_export_quality_id"):
        editor._audio_export_quality_id = aqid
    if exp.get("resolution") and hasattr(editor, "_export_resolution"):
        try:
            r = exp["resolution"]
            editor._export_resolution = (int(r[0]), int(r[1]))
            if hasattr(editor, "_refresh_resolution_btn_label"):
                editor._refresh_resolution_btn_label()
        except Exception:
            pass
    if exp.get("fps") and hasattr(editor, "_export_fps"):
        try:
            editor._export_fps = float(exp["fps"])
        except Exception:
            pass

    # ---- Proxy settings ----
    prx = doc.get("proxy") or {}
    if hasattr(editor, "_proxy_mode"):
        editor._proxy_mode = bool(prx.get("enabled", False))
    if prx.get("dir") and hasattr(editor, "_proxy_dir"):
        try:
            editor._proxy_dir = Path(prx["dir"])
        except Exception:
            pass

    # ---- Spine actor tracks ----
    spine_payload = doc.get("spine_actor_tracks") or []
    if spine_payload and hasattr(editor, "_spine_actor_tracks"):
        try:
            for td in spine_payload:
                editor._spine_actor_tracks.append(_spine_actor_track_from_dict(td))
        except Exception:
            pass
        editor._next_actor_id = max(
            int(doc.get("next_actor_id", 1)),
            int(getattr(editor, "_next_actor_id", 1)),
        )
        try:
            if hasattr(editor, "_rebuild_spine_actor_lanes"):
                editor._rebuild_spine_actor_lanes()
        except Exception:
            pass

    # ---- Live2D actor tracks ----
    l2d_payload = doc.get("live2d_actor_tracks") or []
    if l2d_payload and hasattr(editor, "_live2d_actor_tracks"):
        try:
            for td in l2d_payload:
                editor._live2d_actor_tracks.append(_live2d_actor_track_from_dict(td))
        except Exception:
            pass
        editor._next_live2d_id = max(
            int(doc.get("next_live2d_id", 1)),
            int(getattr(editor, "_next_live2d_id", 1)),
        )
        try:
            if hasattr(editor, "_rebuild_live2d_actor_lanes"):
                editor._rebuild_live2d_actor_lanes()
        except Exception:
            pass

    # ---- AR/PBR object tracks ----
    ar_pbr_payload = doc.get("ar_pbr_tracks") or []
    if hasattr(editor, "_ar_pbr_tracks"):
        try:
            from app.ar_pbr.schema import normalize_ar_tracks

            editor._ar_pbr_tracks = normalize_ar_tracks(ar_pbr_payload)
            editor._next_ar_pbr_id = max(
                int(doc.get("next_ar_pbr_id", 1)),
                int(getattr(editor, "_next_ar_pbr_id", 1)),
            )
            if hasattr(editor, "_sync_ar_pbr_tracks_to_player"):
                editor._sync_ar_pbr_tracks_to_player()
            if hasattr(editor, "_rebuild_ar_pbr_actor_lanes"):
                editor._rebuild_ar_pbr_actor_lanes()
        except Exception:
            pass

    # ---- MMD model tracks ----
    mmd_payload = doc.get("mmd_tracks") or []
    if hasattr(editor, "_mmd_tracks"):
        try:
            from app.mmd.schema import normalize_mmd_tracks

            editor._mmd_tracks = normalize_mmd_tracks(mmd_payload)
            editor._next_mmd_id = max(
                int(doc.get("next_mmd_id", 1)),
                int(getattr(editor, "_next_mmd_id", 1)),
            )
            if hasattr(editor, "_sync_mmd_tracks_to_player"):
                editor._sync_mmd_tracks_to_player()
            else:
                player = getattr(editor, "_player", None)
                if player is not None and hasattr(player, "set_mmd_tracks"):
                    player.set_mmd_tracks(editor._mmd_tracks)
            if hasattr(editor, "_rebuild_mmd_actor_lanes"):
                editor._rebuild_mmd_actor_lanes()
        except Exception:
            pass

    try:
        editor._refresh_player_tracks()
        if hasattr(editor, "_update_tracks_host_width"):
            editor._update_tracks_host_width()
        editor._player.set_position(playhead)
    except Exception:
        pass

    # Rebuild node-effect chains after a short delay so the node graph
    # widgets are fully initialised before we walk the connections.
    # Without this, blur/effect nodes loaded from .tgp only become active
    # after the user clicks a node (because the first _rebuild call happens
    # before the port connections are wired up).
    from PySide6.QtCore import QTimer
    QTimer.singleShot(200, lambda: (
        hasattr(editor, "_rebuild_active_chain") and editor._rebuild_active_chain()
    ))

    print(f"[project] loaded ← {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Clear helpers
# ---------------------------------------------------------------------------

def _clear_editor(editor) -> None:
    """Remove all tracks and reset state to a blank session."""
    # Pause playback if running.
    try:
        editor._player.pause()
    except Exception:
        pass

    # Remove video track rows — remove widgets from layout first to
    # avoid Qt dangling-pointer issues, then clear the data structures.
    for row in list(getattr(editor, "_track_rows", {}).values()):
        try:
            editor._tracks_layout.removeWidget(row)
            row.setParent(None)
        except Exception:
            pass
    editor._tracks = []
    editor._track_rows = {}
    editor._next_track_id = 1

    # Remove audio track rows.
    for row in list(getattr(editor, "_audio_rows", {}).values()):
        try:
            editor._tracks_layout.removeWidget(row)
            row.setParent(None)
        except Exception:
            pass
    editor._audio_tracks = []
    editor._audio_rows = {}
    if not hasattr(editor, "_next_audio_track_id"):
        editor._next_audio_track_id = 1
    else:
        editor._next_audio_track_id = 1
    editor._audio_mixer_snapshots = []

    # Clear subtitles.
    try:
        editor._subtitle_panel.layer.items().clear()
    except Exception:
        pass

    # Reset markers.
    try:
        editor._clear_global_markers()
    except Exception:
        pass
    if hasattr(editor, "_creator_assist_bundle"):
        editor._creator_assist_bundle = {}
    if hasattr(editor, "_capcut_creator_package"):
        editor._capcut_creator_package = {}
    if hasattr(editor, "_capcut_short_ranges"):
        editor._capcut_short_ranges = []
    if hasattr(editor, "_capcut_render_queue_jobs"):
        editor._capcut_render_queue_jobs = []
    panel = getattr(editor, "_creator_assist_panel", None)
    if panel is not None and hasattr(panel, "set_bundle"):
        try:
            panel.set_bundle({})
        except Exception:
            pass

    # Wipe media pool — load_project re-populates from the .tgp.
    try:
        pool = getattr(editor, "_media_pool", None)
        if pool is not None and hasattr(pool, "clear"):
            pool.clear()
    except Exception:
        pass

    # Wipe paint strokes (DrawingCanvas reads from this list every
    # paintEvent, so clearing the list is enough — repaint follows).
    if hasattr(editor, "_strokes"):
        editor._strokes = []
        try:
            editor._drawing_canvas.update()
        except Exception:
            pass

    # Wipe speech bubbles + their widgets.
    for item in list(getattr(editor, "_bubble_items", []) or []):
        try:
            item.deleteLater()
        except Exception:
            pass
    if hasattr(editor, "_bubble_items"):
        editor._bubble_items = []
    if hasattr(editor, "_bubbles"):
        editor._bubbles = []

    # Wipe stickers + their widgets.
    for item in list(getattr(editor, "_sticker_items", []) or []):
        try:
            item.deleteLater()
        except Exception:
            pass
    if hasattr(editor, "_sticker_items"):
        editor._sticker_items = []
    if hasattr(editor, "_stickers"):
        editor._stickers = []

    # Wipe timeline markers.
    if hasattr(editor, "_timeline_markers"):
        editor._timeline_markers = []
        try:
            editor._sync_markers_to_ruler()
        except Exception:
            pass

    # Clear LUT state. (_clear_lut handles _lut_data + _lut_path +
    # _lut_strength + the UI badge in one shot.)
    if hasattr(editor, "_clear_lut"):
        try:
            editor._clear_lut()
        except Exception:
            pass

    # Reset proxy state. Export-quality/format/resolution/fps stay as
    # they are — they're per-project defaults, not session data, and
    # the load path re-applies them from the .tgp.
    if hasattr(editor, "_proxy_mode"):
        editor._proxy_mode = False
    if hasattr(editor, "_proxy_dir"):
        editor._proxy_dir = None

    # Wipe Spine / Live2D actor tracks (just data — the lane-row
    # widgets are currently hidden in the toolbar so they don't sit
    # in a layout; if reactivated later, the next session re-creates
    # rows on demand).
    for row in list(getattr(editor, "_actor_lane_rows", []) or []):
        try:
            editor._tracks_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        except Exception:
            pass
    if hasattr(editor, "_actor_lane_rows"):
        editor._actor_lane_rows = []
    for row in list(getattr(editor, "_live2d_lane_rows", []) or []):
        try:
            editor._tracks_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        except Exception:
            pass
    if hasattr(editor, "_live2d_lane_rows"):
        editor._live2d_lane_rows = []
    for row in list(getattr(editor, "_ar_pbr_lane_rows", []) or []):
        try:
            editor._tracks_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        except Exception:
            pass
    if hasattr(editor, "_ar_pbr_lane_rows"):
        editor._ar_pbr_lane_rows = []
    for row in list(getattr(editor, "_mmd_lane_rows", []) or []):
        try:
            editor._tracks_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        except Exception:
            pass
    if hasattr(editor, "_mmd_lane_rows"):
        editor._mmd_lane_rows = []
    if hasattr(editor, "_spine_actor_tracks"):
        editor._spine_actor_tracks = []
    if hasattr(editor, "_live2d_actor_tracks"):
        editor._live2d_actor_tracks = []
    if hasattr(editor, "_ar_pbr_tracks"):
        editor._ar_pbr_tracks = []
    if hasattr(editor, "_next_ar_pbr_id"):
        editor._next_ar_pbr_id = 1
    if hasattr(editor, "_mmd_tracks"):
        editor._mmd_tracks = []
    if hasattr(editor, "_next_mmd_id"):
        editor._next_mmd_id = 1
    try:
        editor._player.set_spine_actor_tracks([])
        editor._player.set_live2d_actor_tracks([])
        if hasattr(editor._player, "set_ar_pbr_tracks"):
            editor._player.set_ar_pbr_tracks([])
        if hasattr(editor._player, "set_mmd_tracks"):
            editor._player.set_mmd_tracks([])
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Video track restore
# ---------------------------------------------------------------------------

def _restore_clip_effect_param(kind: str, data):
    if data is None:
        return None
    try:
        if kind == "video_filters":
            from app.video_filters import VideoFilterParams
            return VideoFilterParams.from_dict(data)
        if kind == "chroma_key":
            from app.chroma_key import ChromaKeyParams
            return ChromaKeyParams.from_dict(data)
        if kind == "bg_removal":
            from app.background_removal import BackgroundRemovalParams
            return BackgroundRemovalParams.from_dict(data)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _video_clip_from_dict(cd: dict, fallback_src_path: Path | None):
    from app.timeline_model import VideoClip

    src_raw = cd.get("source_path")
    clip_src = Path(src_raw) if src_raw else fallback_src_path
    clip = VideoClip(
        id=int(cd.get("id", 1)),
        source_path=clip_src,
        source_duration_ms=int(cd.get("source_duration_ms", 0)),
        timeline_in_ms=int(cd.get("timeline_in_ms", 0)),
        source_in_ms=int(cd.get("source_in_ms", 0)),
        source_out_ms=int(cd.get("source_out_ms", 0)),
    )
    if bool(cd.get("performance_source") or cd.get("vtuber_performance_source")) or (
        str(cd.get("track_type") or "").casefold() == "vtuber_performance_source"
    ):
        try:
            from app.vtuber.performance_source import mark_performance_source_object

            mark_performance_source_object(clip)
        except Exception:
            clip.performance_source = True
            clip.vtuber_performance_source = True
            clip.track_type = "vtuber_performance_source"
            clip.program_output = False

    try:
        ng_data = cd.get("node_graph") or {}
        grade_data = ((ng_data.get("color") or {}).get("grade"))
        if grade_data:
            from app.color_grading import ColorGrade
            clip.node_graph.color.grade = ColorGrade.from_dict(grade_data)
    except Exception:
        pass

    try:
        from app.node_mask import mask_from_dict
        for md in cd.get("masks", []):
            m = mask_from_dict(md)
            if m is not None:
                clip.masks = getattr(clip, "masks", []) or []
                clip.masks.append(m)
    except Exception:
        pass

    try:
        from app.timeline_model import FadeSegment, SpeedSegment, ZoomActor
        for fd in cd.get("fades", []):
            clip.fades.append(FadeSegment(int(fd["start_ms"]), int(fd["end_ms"])))
        for sd in cd.get("speed_segments", []):
            clip.speed_segments.append(SpeedSegment.from_dict(sd))
        for zd in cd.get("zoom_actors", []):
            clip.zoom_actors.append(ZoomActor(
                id=int(zd.get("id", 0)),
                start_ms=int(zd.get("start_ms", 0)),
                end_ms=int(zd.get("end_ms", 0)),
                target_x=int(zd.get("target_x", 0)),
                target_y=int(zd.get("target_y", 0)),
                target_w=int(zd.get("target_w", 0)),
                target_h=int(zd.get("target_h", 0)),
                zoom_in_ms=int(zd.get("zoom_in_ms", 500)),
                zoom_out_ms=int(zd.get("zoom_out_ms", 500)),
                easing=str(zd.get("easing", "smooth_pop") or "smooth_pop"),
                motion_blur=float(zd.get("motion_blur", 0.0) or 0.0),
            ))
    except Exception:
        pass

    clip.transition_out_type = str(cd.get("transition_out_type", ""))
    clip.transition_out_ms = int(cd.get("transition_out_ms", 500))
    clip.transition_preset_meta = dict(cd.get("transition_preset_meta", {}) or {})
    clip.cursor_events = list(cd.get("cursor_events", []) or [])
    clip.screenstudio_polish = dict(cd.get("screenstudio_polish", {}) or {})

    clip.video_filters = _restore_clip_effect_param("video_filters", cd.get("video_filters", None))
    clip.chroma_key = _restore_clip_effect_param("chroma_key", cd.get("chroma_key", None))
    stab_data = cd.get("stabilizer", None)
    if stab_data is not None:
        try:
            from app.video_stabilizer import StabilizerParams
            clip.stabilizer = StabilizerParams.from_dict(stab_data)
        except Exception:
            pass
    clip.bg_removal = _restore_clip_effect_param("bg_removal", cd.get("bg_removal", None))
    clip.disabled_video_filters = _restore_clip_effect_param(
        "video_filters",
        cd.get("disabled_video_filters", None),
    )
    clip.disabled_chroma_key = _restore_clip_effect_param(
        "chroma_key",
        cd.get("disabled_chroma_key", None),
    )
    clip.disabled_bg_removal = _restore_clip_effect_param(
        "bg_removal",
        cd.get("disabled_bg_removal", None),
    )

    for attr in ("timecode_ms", "waveform_sync_peak_ms", "audio_sync_offset_ms"):
        value = cd.get(attr, None)
        if value is not None:
            try:
                setattr(clip, attr, int(value))
            except Exception:
                setattr(clip, attr, None)

    linked_aid = cd.get("linked_audio_id", None)
    if linked_aid is not None:
        clip.linked_audio_id = int(linked_aid)
    group_id = cd.get("compound_group_id", None)
    if group_id is not None:
        clip.compound_group_id = int(group_id)
        clip.compound_group_name = str(cd.get("compound_group_name", "") or "")
    parent_tid = cd.get("connected_parent_track_id", None)
    if parent_tid is not None:
        clip.connected_parent_track_id = int(parent_tid)
    parent_cid = cd.get("connected_parent_clip_id", None)
    if parent_cid is not None:
        clip.connected_parent_clip_id = int(parent_cid)
    clip.connected_offset_ms = int(cd.get("connected_offset_ms", 0) or 0)
    clip.clip_role = str(cd.get("clip_role", "") or "")
    clip.role_color = str(cd.get("role_color", "") or "")
    audition_id = cd.get("audition_group_id", None)
    if audition_id is not None:
        clip.audition_group_id = int(audition_id)
    clip.audition_name = str(cd.get("audition_name", "") or "")
    clip.audition_active_take_id = str(cd.get("audition_active_take_id", "") or "")
    clip.audition_takes = [
        dict(take)
        for take in (cd.get("audition_takes", []) or [])
        if isinstance(take, dict)
    ]

    nested_id = cd.get("nested_sequence_id", None)
    if nested_id is not None:
        clip.nested_sequence_id = int(nested_id)
    clip.nested_sequence_name = str(cd.get("nested_sequence_name", "") or "")
    for child_data in cd.get("nested_child_clips", []) or []:
        clip.nested_child_clips.append(_video_clip_from_dict(child_data, clip_src))
    for track_data in cd.get("nested_child_tracks", []) or []:
        child_track = []
        for child_data in track_data or []:
            child_track.append(_video_clip_from_dict(child_data, clip_src))
        if child_track:
            clip.nested_child_tracks.append(child_track)
    if clip.nested_child_tracks and not clip.nested_child_clips:
        clip.nested_child_clips = list(clip.nested_child_tracks[0])
    for track_data in cd.get("nested_audio_tracks", []) or []:
        audio_track = []
        for child_data in track_data or []:
            audio_clip = _audio_clip_from_dict(child_data)
            if audio_clip is not None:
                audio_track.append(audio_clip)
        if audio_track:
            clip.nested_audio_tracks.append(audio_track)
    for track_data in cd.get("nested_spine_actor_tracks", []) or []:
        try:
            track_obj = _spine_actor_track_from_dict(track_data)
            if getattr(track_obj, "clips", None):
                clip.nested_spine_actor_tracks.append(track_obj)
        except Exception:
            pass
    for track_data in cd.get("nested_live2d_actor_tracks", []) or []:
        try:
            track_obj = _live2d_actor_track_from_dict(track_data)
            if getattr(track_obj, "clips", None):
                clip.nested_live2d_actor_tracks.append(track_obj)
        except Exception:
            pass
    return clip


def _load_video_track(editor, vt_data: dict, src_path: Path | None) -> None:
    # Use the editor's legacy VideoTrack, not timeline_model.VideoTrack.
    from app.video_track_legacy import VideoTrack, _ensure_video_clips
    from app.timeline_model import VideoClip

    tid = int(vt_data.get("id", editor._next_track_id))
    track = VideoTrack(id=tid, source_path=src_path)
    track.label = str(vt_data.get("label", "") or "")
    track.track_type = str(vt_data.get("track_type", "") or getattr(track, "track_type", "video"))
    track.performance_source = bool(vt_data.get("performance_source", False))
    track.vtuber_performance_source = bool(vt_data.get("vtuber_performance_source", False))
    track.program_output = bool(vt_data.get("program_output", True))
    if bool(track.performance_source or track.vtuber_performance_source) or (
        str(track.track_type or "").casefold() == "vtuber_performance_source"
    ):
        try:
            from app.vtuber.performance_source import mark_performance_source_object

            mark_performance_source_object(track)
        except Exception:
            track.track_type = "vtuber_performance_source"
            track.program_output = False
    # display_name is a read-only property derived from source_path — skip

    # HDR probe is opt-in during project load. Opening a project can
    # restore many tracks at once, and probing every video immediately
    # spawns ffmpeg repeatedly right when the editor window is appearing.
    # Export and explicit media diagnostics still run authoritative
    # colour probes when needed.
    track.hdr_info = None
    if src_path is not None and _project_load_hdr_probe_enabled():
        try:
            from app.hdr_probe import probe_hdr
            track.hdr_info = probe_hdr(src_path)
        except Exception:
            track.hdr_info = None

    # Restore clips.
    clips_data = vt_data.get("clips", [])
    if clips_data:
        restored: list[VideoClip] = []
        for cd in clips_data:
            restored.append(_video_clip_from_dict(cd, src_path))
        track.clips = restored
    else:
        track.clips = []
    # Loaded from saved data → clips list is authoritative (don't let
    # refresh_tracks rebuild it from source via _build_clips_view).
    track.clips_explicit = True
    if bool(track.performance_source or track.vtuber_performance_source) or (
        str(track.track_type or "").casefold() == "vtuber_performance_source"
    ):
        try:
            from app.vtuber.performance_source import mark_performance_source_object

            for clip in track.clips:
                mark_performance_source_object(clip)
        except Exception:
            for clip in track.clips:
                clip.performance_source = True
                clip.vtuber_performance_source = True
                clip.track_type = "vtuber_performance_source"
                clip.program_output = False

    # Restore track-level fields.
    track.offset_ms = int(vt_data.get("offset_ms", 0))
    track.preview_color_compare_mode = str(vt_data.get("preview_color_compare_mode", "") or "")
    track.preview_compare_labels_enabled = bool(vt_data.get("preview_compare_labels_enabled", True))
    from app.timeline_model import FadeSegment, SpeedSegment
    for fd in vt_data.get("fades", []):
        track.fades.append(FadeSegment(int(fd["start_ms"]), int(fd["end_ms"])))
    for sd in vt_data.get("speed_segments", []):
        track.speed_segments.append(SpeedSegment.from_dict(sd))

    # Restore zoom actors.
    from app.timeline_model import ZoomActor
    for zd in vt_data.get("zoom_actors", []):
        track.zoom_actors.append(ZoomActor(
            id=int(zd["id"]),
            start_ms=int(zd["start_ms"]), end_ms=int(zd["end_ms"]),
            target_x=int(zd.get("target_x", 0)),
            target_y=int(zd.get("target_y", 0)),
            target_w=int(zd.get("target_w", 0)),
            target_h=int(zd.get("target_h", 0)),
            zoom_in_ms=int(zd.get("zoom_in_ms", 0)),
            zoom_out_ms=int(zd.get("zoom_out_ms", 0)),
            easing=str(zd.get("easing", "smooth_pop") or "smooth_pop"),
            motion_blur=float(zd.get("motion_blur", 0.0) or 0.0),
        ))
    track.cursor_events = list(vt_data.get("cursor_events", []) or [])
    track.screenstudio_polish = dict(vt_data.get("screenstudio_polish", {}) or {})

    # Restore typography actors.
    from app.typography import TextClip
    for ad in vt_data.get("typography_actors", []):
        actor = TextClip(
            start_ms=int(ad.get("start_ms", 0)),
            end_ms=int(ad.get("end_ms", 0)),
        )
        actor.text = str(ad.get("text", ""))
        track.typography_actors.append(actor)

    # Restore node graph.
    ng_data = vt_data.get("node_graph_view_data")
    if ng_data:
        track.node_graph_view_data = ng_data

    # Restore PIP compositing fields.
    track.pip_enabled = bool(vt_data.get("pip_enabled", False))
    track.pip_x = float(vt_data.get("pip_x", 0.5))
    track.pip_y = float(vt_data.get("pip_y", 0.5))
    track.pip_scale = float(vt_data.get("pip_scale", 0.3))
    track.pip_opacity = float(vt_data.get("pip_opacity", 1.0))
    track.pip_keyframes = list(vt_data.get("pip_keyframes", []))

    # Insert into editor.
    editor._tracks.append(track)
    editor._insert_track_widget(track)
    editor._start_thumbnail_extraction(track)
    editor._set_active_track(tid)

    # Ensure clips are populated.
    if not track.clips:
        _ensure_video_clips(track)


# ---------------------------------------------------------------------------
# Audio track restore
# ---------------------------------------------------------------------------

def _load_audio_track(editor, at_data: dict) -> None:
    from app.audio_tracks import AudioTrack, default_track_insert_slots, default_track_sends

    tid = int(at_data.get("id", getattr(editor, "_next_audio_track_id", 1)))
    new_track = AudioTrack(id=tid)
    # display_name is a read-only property on AudioTrack — skip
    new_track.volume = float(at_data.get("volume", 1.0))
    new_track.pan = float(at_data.get("pan", 0.0))
    new_track.muted = bool(at_data.get("muted", False))
    new_track.solo = bool(at_data.get("solo", False))
    new_track.label = str(at_data.get("label", "") or "")
    new_track.bus_id = str(at_data.get("bus_id", "master") or "master")
    new_track.track_type = str(at_data.get("track_type", "") or "")
    new_track.insert_slots = list(at_data.get("insert_slots", []) or default_track_insert_slots())
    new_track.sends = dict(at_data.get("sends", {}) or default_track_sends())
    new_track.automation_read = bool(at_data.get("automation_read", True))
    new_track.automation_write = bool(at_data.get("automation_write", False))
    new_track.automation_points = list(at_data.get("automation_points", []) or [])
    new_track.automation_lanes = dict(at_data.get("automation_lanes", {}) or {})

    for cd in at_data.get("clips", []):
        clip = _audio_clip_from_dict(cd)
        if clip is not None:
            new_track.clips.append(clip)

    editor._audio_tracks.append(new_track)
    editor._insert_audio_track_widget(new_track)
    if hasattr(editor, "_next_audio_track_id"):
        editor._next_audio_track_id = max(
            editor._next_audio_track_id, tid + 1,
        )
    # Keep the clip-id counter ahead of all loaded clip ids so newly
    # created clips get unique IDs and _on_waveform_ready routes correctly.
    max_clip_id = max((c.id for c in new_track.clips), default=0)
    editor._next_audio_clip_id = max(
        getattr(editor, "_next_audio_clip_id", 1), max_clip_id + 1
    )

    # Start waveform extraction.
    for clip in new_track.clips:
        try:
            editor._start_waveform_extraction(clip)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Subtitle restore
# ---------------------------------------------------------------------------

def _load_subtitles(editor, subtitles_data: list) -> None:
    try:
        from app.subtitles import Subtitle
        layer = editor._subtitle_panel.layer
        restored = []
        for sd in subtitles_data:
            s = Subtitle(
                text=str(sd.get("text", "")),
                start_ms=int(sd.get("start_ms", 0)),
                end_ms=int(sd.get("end_ms", 0)),
                show_box=bool(sd.get("show_box", True)),
                style=dict(sd.get("style", {}) or {}),
            )
            restored.append(s)
        if hasattr(layer, "replace_all"):
            layer.replace_all(restored)
        else:
            items = layer.items()
            items.clear()
            items.extend(restored)
            if layer.on_change:
                try:
                    layer.on_change()
                except Exception:
                    pass
    except Exception as e:
        print(f"[project] subtitle restore failed: {e}", file=sys.stderr)
