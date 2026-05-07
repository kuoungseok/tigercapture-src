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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# File extension / version
# ---------------------------------------------------------------------------

EXTENSION = ".tgp"
FORMAT_VERSION = "1.1"


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
        "video_filters": (
            getattr(c, "video_filters", None).to_dict()
            if getattr(c, "video_filters", None) is not None else None
        ),
        "chroma_key": (
            getattr(c, "chroma_key", None).to_dict()
            if getattr(c, "chroma_key", None) is not None else None
        ),
        "stabilizer": (
            getattr(c, "stabilizer", None).to_dict()
            if getattr(c, "stabilizer", None) is not None else None
        ),
        "bg_removal": (
            getattr(c, "bg_removal", None).to_dict()
            if getattr(c, "bg_removal", None) is not None else None
        ),
        "linked_audio_id": getattr(c, "linked_audio_id", None),
    }


def _audio_clip_to_dict(c) -> dict:
    fades_data = [_fade_to_dict(f) for f in getattr(c, "fades", [])]
    return {
        "id": int(c.id),
        "source_path": _p(c.source_path),
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


def _subtitle_to_dict(s) -> dict:
    return {
        "text": str(s.text),
        "start_ms": int(s.start_ms),
        "end_ms": int(s.end_ms),
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

    doc: dict[str, Any] = {
        "version": FORMAT_VERSION,
        "app": "TigerCapture",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "px_per_sec": float(getattr(editor, "_px_per_sec", 40.0)),
        "playhead_ms": int(editor._player.position()),
        "global_in_ms": int(getattr(editor, "_global_in_ms", -1)),
        "global_out_ms": int(getattr(editor, "_global_out_ms", -1)),
        "project_settings": dict(getattr(editor, "_project_settings", {})),
        "video_tracks": [],
        "audio_tracks": [],
        "subtitles": [],
    }

    # ---- Video tracks ----
    for track in getattr(editor, "_tracks", []):
        vt: dict = {
            "id": int(track.id),
            "source_path": _p(track.source_path),
            "display_name": str(getattr(track, "display_name", "")),
            "offset_ms": int(getattr(track, "offset_ms", 0)),
            "clips": [_video_clip_to_dict(c) for c in (getattr(track, "clips", None) or [])],
            "fades": [_fade_to_dict(f) for f in getattr(track, "fades", [])],
            "zoom_actors": [_zoom_actor_to_dict(z) for z in getattr(track, "zoom_actors", [])],
            "speed_segments": [_speed_segment_to_dict(s) for s in getattr(track, "speed_segments", [])],
            "typography_actors": [_typo_actor_to_dict(a) for a in getattr(track, "typography_actors", [])],
            "node_graph_view_data": dict(getattr(track, "node_graph_view_data", None) or {}),
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
            "clips": [_audio_clip_to_dict(c) for c in (atrack.clips or [])],
        }
        doc["audio_tracks"].append(at)

    # ---- Subtitles ----
    try:
        sub_panel = editor._subtitle_panel
        for sub in sub_panel.layer.items():
            doc["subtitles"].append(_subtitle_to_dict(sub))
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
                    f"TigerCapture — {name}  [{ratio}  {w}×{h}  {float(fps):.3g}fps]"
                )
        except Exception:
            pass

    # 2. Restore video tracks.
    max_vid_id = 0
    for vt_data in doc.get("video_tracks", []):
        src = vt_data.get("source_path")
        if not src:
            continue
        src_path = Path(src)
        if not src_path.exists():
            print(f"[project] warning: source missing {src_path}", file=sys.stderr)
            continue
        _load_video_track(editor, vt_data, src_path)
        max_vid_id = max(max_vid_id, int(vt_data.get("id", 0)))

    if max_vid_id >= editor._next_track_id:
        editor._next_track_id = max_vid_id + 1

    # 3. Restore audio tracks.
    for at_data in doc.get("audio_tracks", []):
        _load_audio_track(editor, at_data)

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


# ---------------------------------------------------------------------------
# Video track restore
# ---------------------------------------------------------------------------

def _load_video_track(editor, vt_data: dict, src_path: Path) -> None:
    # Use the editor's own VideoTrack (video_editor_window.VideoTrack),
    # not timeline_model.VideoTrack — they are different classes.
    from app.video_editor_window import VideoTrack, _ensure_video_clips
    from app.timeline_model import VideoClip

    tid = int(vt_data.get("id", editor._next_track_id))
    track = VideoTrack(id=tid, source_path=src_path)
    # display_name is a read-only property derived from source_path — skip

    # HDR probe.
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
            clip = VideoClip(
                id=int(cd.get("id", 1)),
                source_path=src_path,
                source_duration_ms=int(cd.get("source_duration_ms", 0)),
                timeline_in_ms=int(cd.get("timeline_in_ms", 0)),
                source_in_ms=int(cd.get("source_in_ms", 0)),
                source_out_ms=int(cd.get("source_out_ms", 0)),
            )
            # Restore masks on clip.
            from app.node_mask import mask_from_dict
            for md in cd.get("masks", []):
                m = mask_from_dict(md)
                if m is not None:
                    clip.masks = getattr(clip, "masks", []) or []
                    clip.masks.append(m)
            # Restore fades.
            from app.video_editor_window import FadeSegment
            for fd in cd.get("fades", []):
                clip.fades.append(FadeSegment(int(fd["start_ms"]), int(fd["end_ms"])))
            # Restore transition fields.
            clip.transition_out_type = str(cd.get("transition_out_type", ""))
            clip.transition_out_ms = int(cd.get("transition_out_ms", 500))
            # Restore video filters.
            vf_data = cd.get("video_filters", None)
            if vf_data is not None:
                try:
                    from app.video_filters import VideoFilterParams
                    clip.video_filters = VideoFilterParams.from_dict(vf_data)
                except Exception:
                    pass
            # Restore chroma key.
            ck_data = cd.get("chroma_key", None)
            if ck_data is not None:
                try:
                    from app.chroma_key import ChromaKeyParams
                    clip.chroma_key = ChromaKeyParams.from_dict(ck_data)
                except Exception:
                    pass
            # Restore stabilizer.
            stab_data = cd.get("stabilizer", None)
            if stab_data is not None:
                try:
                    from app.video_stabilizer import StabilizerParams
                    clip.stabilizer = StabilizerParams.from_dict(stab_data)
                except Exception:
                    pass
            # Restore background removal.
            bgr_data = cd.get("bg_removal", None)
            if bgr_data is not None:
                try:
                    from app.background_removal import BackgroundRemovalParams
                    clip.bg_removal = BackgroundRemovalParams.from_dict(bgr_data)
                except Exception:
                    pass
            # Restore linked audio id.
            linked_aid = cd.get("linked_audio_id", None)
            if linked_aid is not None:
                clip.linked_audio_id = int(linked_aid)
            restored.append(clip)
        track.clips = restored
    else:
        track.clips = []
    # Loaded from saved data → clips list is authoritative (don't let
    # refresh_tracks rebuild it from source via _build_clips_view).
    track.clips_explicit = True

    # Restore track-level fields.
    track.offset_ms = int(vt_data.get("offset_ms", 0))
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
            zoom_in_ms=int(zd.get("zoom_in_ms", 0)),
            zoom_out_ms=int(zd.get("zoom_out_ms", 0)),
        ))

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
    from app.audio_tracks import AudioTrack, AudioClip, default_effects_state

    tid = int(at_data.get("id", getattr(editor, "_next_audio_track_id", 1)))
    new_track = AudioTrack(id=tid)
    # display_name is a read-only property on AudioTrack — skip
    new_track.volume = float(at_data.get("volume", 1.0))

    for cd in at_data.get("clips", []):
        src = cd.get("source_path")
        if not src:
            continue
        src_path = Path(src)
        if not src_path.exists():
            continue
        clip = AudioClip(
            id=int(cd.get("id", 1)),
            source_path=src_path,
            offset_ms=int(cd.get("offset_ms", 0)),
            trim_start_ms=int(cd.get("trim_start_ms", 0)),
            trim_end_ms=int(cd.get("trim_end_ms", 0)),
            fade_in_ms=int(cd.get("fade_in_ms", 0)),
            fade_out_ms=int(cd.get("fade_out_ms", 0)),
        )
        clip.volume_points = list(cd.get("volume_points", []) or [])
        clip.effects = dict(cd.get("effects", {}) or default_effects_state())
        clip.gain = float(cd.get("gain", 1.0))
        # Restore duration via the source file.
        try:
            from app.audio_tracks import probe_audio_duration_ms
            clip.duration_ms = probe_audio_duration_ms(src_path)
        except Exception:
            pass
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
        items = layer.items()
        items.clear()
        for sd in subtitles_data:
            s = Subtitle(
                text=str(sd.get("text", "")),
                start_ms=int(sd.get("start_ms", 0)),
                end_ms=int(sd.get("end_ms", 0)),
            )
            items.append(s)
        if layer.on_change:
            try:
                layer.on_change()
            except Exception:
                pass
    except Exception as e:
        print(f"[project] subtitle restore failed: {e}", file=sys.stderr)
