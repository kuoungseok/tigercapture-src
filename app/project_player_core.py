from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping
import time

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage

from app.simple_video_player import PlayerState
from app.timeline_model import VideoClip, build_legacy_clips_view
from app.mmd.physics import SECONDARY_ROTATION_HINT_SCALE, SPRING_PHYSICS_RESPONSE, mmd_physics_backend_diagnostics


AR_PBR_PREVIEW_TRIANGLE_LIMIT = 120_000
AR_PBR_PLAYBACK_TRIANGLE_LIMIT = 1_000
AR_PBR_RUNTIME_ANCHOR_CACHE_MS = 160
MMD_PREVIEW_IK_ITERATIONS = 12
MMD_PLAYBACK_IK_ITERATIONS = 2
MMD_PHYSICS_UPDATE_INTERVAL_FRAMES = 2.0
MMD_PHYSICS_SMOOTHING_RESPONSE = 0.88
MMD_PHYSICS_ROTATION_HINT_SCALE = SECONDARY_ROTATION_HINT_SCALE
MMD_PHYSICS_SPRING_RESPONSE = SPRING_PHYSICS_RESPONSE
MMD_GPU_MORPH_SLOTS = 2


def _screenstudio_owner_for_preview(clip, track):
    """Merge clip and track Screen Studio metadata for preview rendering."""
    clip_events = list(getattr(clip, "cursor_events", []) or [])
    track_events = list(getattr(track, "cursor_events", []) or [])
    clip_polish = dict(getattr(clip, "screenstudio_polish", {}) or {})
    track_polish = dict(getattr(track, "screenstudio_polish", {}) or {})
    if clip_events and clip_polish:
        return clip
    events = clip_events or track_events
    polish = clip_polish or track_polish
    if not events and not polish:
        return clip
    return SimpleNamespace(
        cursor_events=events,
        screenstudio_polish=polish,
        source_path=getattr(clip, "source_path", None),
        source_duration_ms=getattr(clip, "source_duration_ms", 0),
        source_in_ms=getattr(clip, "source_in_ms", 0),
        source_out_ms=getattr(clip, "source_out_ms", 0),
        effective_source_out_ms=getattr(clip, "effective_source_out_ms", 0),
        effective_length_ms=getattr(clip, "effective_length_ms", 0),
    )


def _interpolate_pip_params(keyframes: list, pos_ms: int, track) -> tuple:
    """Return (x, y, scale, opacity) at pos_ms by linearly interpolating keyframes.
    Falls back to track's static values if keyframes list is empty."""
    if not keyframes:
        return (
            float(getattr(track, "pip_x", 0.5)),
            float(getattr(track, "pip_y", 0.5)),
            float(getattr(track, "pip_scale", 0.3)),
            float(getattr(track, "pip_opacity", 1.0)),
        )
    sorted_kf = sorted(keyframes, key=lambda k: k["ms"])
    # Before first keyframe
    if pos_ms <= sorted_kf[0]["ms"]:
        k = sorted_kf[0]
        return k["x"], k["y"], k["scale"], k["opacity"]
    # After last keyframe
    if pos_ms >= sorted_kf[-1]["ms"]:
        k = sorted_kf[-1]
        return k["x"], k["y"], k["scale"], k["opacity"]
    # Between keyframes
    for i in range(len(sorted_kf) - 1):
        k0, k1 = sorted_kf[i], sorted_kf[i + 1]
        if k0["ms"] <= pos_ms <= k1["ms"]:
            t = (pos_ms - k0["ms"]) / max(1, k1["ms"] - k0["ms"])
            return (
                k0["x"] + (k1["x"] - k0["x"]) * t,
                k0["y"] + (k1["y"] - k0["y"]) * t,
                k0["scale"] + (k1["scale"] - k0["scale"]) * t,
                k0["opacity"] + (k1["opacity"] - k0["opacity"]) * t,
            )
    return (
        float(getattr(track, "pip_x", 0.5)),
        float(getattr(track, "pip_y", 0.5)),
        float(getattr(track, "pip_scale", 0.3)),
        float(getattr(track, "pip_opacity", 1.0)),
    )


def _apply_node_effect_player(node_item, rgb: np.ndarray, masks: list, frame_idx: int) -> np.ndarray:
    """Apply a node's effect in the render pipeline.  Shared between
    the player and the editor's ``_apply_node_effect`` staticmethod so
    both code paths use identical logic."""
    kind = getattr(node_item, "NODE_KIND", "serial")
    if getattr(node_item, "bypassed", False):
        return rgb
    if kind == "blur":
        bp = getattr(node_item, "blur_params", None)
        if bp is None or bp.is_identity():
            return rgb
        from app.node_mask import evaluate_node_masks
        mask = evaluate_node_masks(masks, rgb, frame_idx) if masks else None
        invert = bool(getattr(node_item, "blur_invert_mask", True))
        return _preserve_encoded_matte(rgb, bp.apply_with_mask(rgb, mask, invert_mask=invert))
    ep = getattr(node_item, "effect_params", None)
    if ep is not None:
        if ep.is_identity():
            return rgb
        result = ep.apply(rgb)
        if masks:
            from app.node_mask import evaluate_node_masks
            mask = evaluate_node_masks(masks, rgb, frame_idx)
            if mask is not None:
                mf = mask[..., None]
                result = np.clip(mf * result.astype(np.float32) +
                                 (1.0 - mf) * rgb.astype(np.float32), 0, 255).astype(np.uint8)
        return _preserve_encoded_matte(rgb, result)
    grade = getattr(node_item, "color_grade", None)
    if grade is None or grade.is_identity():
        return rgb
    from app.color_grading import apply_to_rgb
    from app.node_mask import evaluate_node_masks
    if masks:
        mask = evaluate_node_masks(masks, rgb, frame_idx)
        if mask is not None:
            graded = apply_to_rgb(rgb, grade).astype(np.float32)
            mf = mask[..., None]
            blended = mf * graded + (1.0 - mf) * rgb.astype(np.float32)
            return _preserve_encoded_matte(rgb, np.clip(blended, 0, 255).astype(np.uint8))
    return _preserve_encoded_matte(rgb, apply_to_rgb(rgb, grade))


def _preserve_encoded_matte(source_rgb: np.ndarray, processed_rgb: np.ndarray) -> np.ndarray:
    try:
        from app.video_letterbox import preserve_letterbox_matte

        return preserve_letterbox_matte(source_rgb, processed_rgb)
    except Exception:
        return processed_rgb


def _is_preview_color_grade_node(node_item) -> bool:
    """Return True for nodes that should disappear in Before preview."""
    if getattr(node_item, "bypassed", False):
        return False
    kind = getattr(node_item, "NODE_KIND", "serial")
    if kind == "blur":
        blur_params = getattr(node_item, "blur_params", None)
        if blur_params is None:
            return False
        try:
            return not blur_params.is_identity()
        except Exception:
            return True
    if getattr(node_item, "effect_params", None) is not None:
        effect_params = getattr(node_item, "effect_params", None)
        try:
            return not effect_params.is_identity()
        except Exception:
            return True
    grade = getattr(node_item, "color_grade", None)
    return grade is not None and not grade.is_identity()


def _preview_compare_content_bounds(rgb: np.ndarray) -> tuple[int, int, int, int]:
    """Return the non-letterbox content bounds for preview comparison.

    The compare renderer is preview-only. If the source frame contains encoded
    letterbox/pillarbox matte, grading the whole right half makes the matte
    look like it changed too. Detect only very dark, low-variance edge strips
    and keep them outside the Before/After replacement area.
    """
    try:
        arr = np.asarray(rgb)
        h, w = arr.shape[:2]
        from app.video_letterbox import detect_letterbox_bands

        detection = detect_letterbox_bands(
            arr,
            settings={
                "letterbox_max_matte_fraction": 0.82,
                "letterbox_max_edge_fraction": 0.48,
                "letterbox_max_one_sided_fraction": 0.20,
            },
        )
        if bool(detection.get("ok")):
            x, y, cw, ch = detection.get("content_rect") or [0, 0, w, h]
            return int(y), int(y + ch), int(x), int(x + cw)
        return 0, h, 0, w
    except Exception:
        return 0, 0, 0, 0


def _apply_node_chain_preview_compare(
    rgb: np.ndarray,
    node_item_chain: list | None,
    frame_idx: int,
    mode: str,
) -> np.ndarray | None:
    """Preview-only color compare renderer.

    ``before`` keeps non-color node effects but skips active ColorGrade nodes.
    ``split`` composites the color-skipped result on the left and the normal
    result on the right without baking a colored separator into the frame.
    Export never calls this path.
    """
    compare_mode = str(mode or "").casefold()
    if compare_mode not in {"before", "split"} or node_item_chain is None:
        return None

    def _render(include_color: bool) -> np.ndarray:
        out = rgb.copy()
        for node_item, masks in list(node_item_chain or []):
            if not include_color and _is_preview_color_grade_node(node_item):
                continue
            try:
                out = _apply_node_effect_player(node_item, out, masks or [], int(frame_idx))
            except Exception:
                pass
        return out

    before = _render(include_color=False)
    if compare_mode == "before":
        return before

    after = _render(include_color=True)
    try:
        h, w = after.shape[:2]
        if h <= 0 or w <= 2:
            return after
        y0, y1, x0, x1 = _preview_compare_content_bounds(before)
        split_x = max(x0 + 1, min(x1 - 1, (x0 + x1) // 2))
        mixed = before.copy()
        if y1 > y0 and x1 > split_x:
            mixed[y0:y1, split_x:x1] = after[y0:y1, split_x:x1]
        return mixed
    except Exception:
        return after


# Phase 1.5b kept this helper here while ``timeline_model`` only had
# the migration variant. Phase 1.5c moved the gap-preserving builder
# into ``timeline_model`` so paintEvent + drag handlers + the player
# all use the same one. This alias stays for the existing player
# call sites + tests.
def _build_clips_view(track) -> list[VideoClip]:
    return build_legacy_clips_view(track)


def _expanded_clips_for_track(track) -> list[VideoClip]:
    from app.timeline_model import expanded_timeline_clips
    clips = list(getattr(track, "clips", []) or [])
    return expanded_timeline_clips(clips)


def _source_clips_for_track(track) -> list[VideoClip]:
    from app.timeline_model import renderable_source_clips
    return renderable_source_clips(list(getattr(track, "clips", []) or []))


def _clip_view_for_track(track) -> list[VideoClip]:
    return list(getattr(track, "clips", []) or [])


class ProjectPlayer(QObject):
    """Multi-track player with layered fall-through playback.

    Tracks are ordered from **first-added (bottom)** to **last-added (top)**.
    At any time ``t`` the topmost track that has a source, where ``t`` is
    within its duration and not inside a cut segment, is the one we render.
    This means cuts in the top track "reveal" whatever is below; tracks that
    end early leave the underlying track visible through the remainder.

    Speed segments apply to whichever track is currently being rendered.
    Project duration = max of all tracks' durations.
    """

    frame_ready = Signal(QImage)
    # GPU preview path: raw zoomed RGB ndarray + ColorGrade snapshot.
    # Emitted alongside ``frame_ready`` for OpenGLPreviewWidget consumers
    # so the shader can do the colour-grade work instead of numpy. The
    # legacy QImage signal can still fire so scopes/popout keep working.
    gpu_frame_ready = Signal(object, object)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(object)
    error_occurred = Signal(str)
    ar_pbr_asset_import_ready = Signal(str)

    REFERENCE_FPS = 30.0

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tracks: list = []  # list of VideoTrack (first-added first)
        self._caps: dict = {}       # track_id → decoder (legacy single-source path)
        self._fps: dict = {}        # track_id → fps (legacy)
        self._total_frames: dict = {}
        # Multi-source: per-path decoders shared across clips.
        # Keyed by resolved Path so two clips pointing at the same file
        # reuse the same decoder object.
        self._path_caps: dict = {}   # Path → decoder
        self._path_fps: dict = {}    # Path → float
        # Phase 1.5b: per-track ``VideoClip`` view rebuilt by
        # ``refresh_tracks``. Each entry is a list of clips that re-
        # express the legacy track (single source + cuts + offset) in
        # the new clip-list form *while preserving cut gaps* — a cut
        # in the middle produces two clips with empty project-time
        # space between them, matching the legacy renderer's
        # "skip frames during cut" behaviour. When real per-track
        # ``clips`` lists land in Phase 1.5c, this cache is replaced
        # by the track's own ``clips`` list.
        self._clips_view: dict[int, list[VideoClip]] = {}
        self._last_rendered_track_id: int | None = None
        self._last_rendered_frame_idx: int = -1
        self._last_rendered_clip_path: "Path | None" = None
        self._last_preview_frame_cache: dict | None = None
        self._position_ms: int = 0
        self._seek_retry_serial: int = 0
        self._duration_ms: int = 0
        self._state: PlayerState = PlayerState.STOPPED
        self._current_segment_speed: float = 1.0
        self._bounded_play_end_ms: int | None = None
        self._bounded_play_return_ms: int | None = None
        self._last_playback_wall_s: float | None = None
        self._playback_fractional_ms: float = 0.0
        self._preview_quality_mode: str = "auto"
        self._preview_frame_drop_allowed: bool = True
        self._preview_frame_drop_count: int = 0
        self._last_tick_advance_ms: int = 0
        # Phase 7: shuttle gear set by the Sony jog/shuttle dial.
        # Multiplied INTO the per-segment speed so e.g. a 4× shuttle
        # over a 2× speed segment plays at 8×. ``1.0`` is the neutral
        # state matching the dial's centre detent.
        self._shuttle_rate: float = 1.0

        # Per-clip video stabilizers keyed by id(clip).
        self._stabilizers: dict = {}

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)
        self._window_move_guard_active: bool = False
        self._window_move_guard_prior_interval: int | None = None
        self._window_move_guard_prior_timer_type = Qt.TimerType.PreciseTimer
        self._qimage_frame_enabled: bool = True

        # Spine actor tracks — composited over video frames
        self._spine_actor_tracks: list = []  # list[SpineActorTrack]
        # Live2D actor tracks
        self._live2d_actor_tracks: list = []  # list[Live2DActorTrack]
        self._ar_pbr_tracks: list[dict] = []
        self._mmd_tracks: list[dict] = []
        self._mmd_model_cache: dict[str, object] = {}
        self._mmd_motion_cache: dict[str, object | None] = {}
        self._mmd_physics_cache: dict[str, object] = {}
        self._mmd_last_frame_by_track: dict[str, float] = {}
        self._mmd_last_diagnostics: dict = {}
        self._ar_pbr_asset_descriptor_cache: dict[str, dict] = {}
        self._ar_pbr_asset_error_cache: dict[str, str] = {}
        self._ar_pbr_asset_import_futures: dict[str, object] = {}
        self._ar_pbr_asset_import_executor: ThreadPoolExecutor | None = None
        self._ar_pbr_runtime_anchor_cache: dict[str, dict] = {}
        self._ar_pbr_gpu_packet_cache: OrderedDict[tuple, tuple[list[dict], dict]] = OrderedDict()
        self._ar_pbr_last_diagnostics: dict = {}
        self._preview_prerender_cache: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        self._preview_prerender_generation: int = 0
        self._preview_prerender_limit: int = 90
        self._spine_overlay_cache: "OrderedDict[tuple, object]" = OrderedDict()
        self._spine_direct_state_cache: "OrderedDict[tuple, list[dict]]" = OrderedDict()
        self._spine_gl_compositor = None
        self._spine_gl_compositor_failed = False
        self._spine_gpu_overlay_enabled = True
        self._project_settings: dict = {}
        try:
            import os
            self._spine_overlay_cache_limit = max(
                8,
                min(120, int(os.environ.get("TIGERCAPTURE_SPINE_OVERLAY_CACHE_LIMIT", "48"))),
            )
        except Exception:
            self._spine_overlay_cache_limit = 48
        self.ar_pbr_asset_import_ready.connect(self._on_ar_pbr_asset_import_ready)

    def set_qimage_frame_enabled(self, enabled: bool) -> None:
        """Enable or disable the legacy CPU QImage preview signal."""
        self._qimage_frame_enabled = bool(enabled)

    def qimage_frame_enabled(self) -> bool:
        return bool(getattr(self, "_qimage_frame_enabled", True))

    def set_project_settings(self, settings: dict | None) -> None:
        self._project_settings = dict(settings or {})
        self._preview_quality_mode = self._preview_quality_mode_from_settings(
            self._project_settings
        )
        self._preview_frame_drop_allowed = self._preview_frame_drop_allowed_from_settings(
            self._project_settings
        )
        self._last_preview_frame_cache = None

    @staticmethod
    def _preview_quality_mode_from_settings(settings: dict | None) -> str:
        try:
            from app.preview_performance_policy import normalize_preview_quality_mode
        except Exception:
            normalize_preview_quality_mode = lambda value: "auto"
        if not isinstance(settings, dict):
            return "auto"
        preview = settings.get("preview")
        raw = None
        if isinstance(preview, dict):
            raw = preview.get("quality_mode") or preview.get("mode")
        if raw is None:
            raw = settings.get("preview_quality_mode")
        return normalize_preview_quality_mode(raw)

    @classmethod
    def _preview_frame_drop_allowed_from_settings(cls, settings: dict | None) -> bool:
        if not isinstance(settings, dict):
            return True
        preview = settings.get("preview")
        raw = None
        if isinstance(preview, dict):
            raw = preview.get("frame_drop_allowed")
        if raw is None:
            raw = settings.get("preview_frame_drop_allowed")
        if raw is not None:
            return bool(raw)
        return cls._preview_quality_mode_from_settings(settings) != "quality"

    @staticmethod
    def _preview_decode_height_from_settings(settings: dict | None) -> int | None:
        """Optional per-project preview decode height.

        ``None`` keeps the decoder factory's source-aware defaults. Supplying a
        project setting lets low-power or heavy compositing projects cap decode
        earlier, and also gives the FFmpeg frame-server/auto paths a fair scale
        hint before they open.
        """
        if not isinstance(settings, dict):
            return None
        mode = ProjectPlayer._preview_quality_mode_from_settings(settings)
        candidates: list[object] = [
            settings.get("preview_decode_height"),
            settings.get("preview_height"),
            settings.get("monitoring_preview_height"),
        ]
        preview = settings.get("preview")
        if isinstance(preview, dict):
            candidates.extend([
                preview.get("decode_height"),
                preview.get("height"),
            ])
        for raw in candidates:
            if raw is None or raw == "":
                continue
            try:
                value = int(raw)
            except Exception:
                continue
            if value <= 0:
                return 0
            return max(240, min(2160, value))
        if mode == "quality":
            return 0
        if mode == "performance":
            return 540
        return None

    def preview_playback_diagnostics(self) -> dict[str, object]:
        return {
            "quality_mode": str(getattr(self, "_preview_quality_mode", "auto")),
            "frame_drop_allowed": bool(getattr(self, "_preview_frame_drop_allowed", True)),
            "frame_drop_count": int(getattr(self, "_preview_frame_drop_count", 0) or 0),
            "last_tick_advance_ms": int(getattr(self, "_last_tick_advance_ms", 0) or 0),
            "preview_decode_height": self._preview_decode_height_hint(),
        }

    def _preview_decode_height_hint(self) -> int | None:
        return self._preview_decode_height_from_settings(
            getattr(self, "_project_settings", {}) or {}
        )

    def _open_preview_decoder(self, open_decoder, path, *, hdr_info=None):
        preview_height = self._preview_decode_height_hint()
        if preview_height is None:
            return open_decoder(path, hdr_info=hdr_info)
        return open_decoder(path, hdr_info=hdr_info, preview_height=preview_height)



    def _preview_frame_cache_key(self, pos_ms: int, track, clip, clip_sp, frame_idx: int) -> tuple:
        return (
            int(getattr(self, "_preview_prerender_generation", 0)),
            int(pos_ms),
            int(getattr(track, "id", -1)),
            id(clip),
            str(clip_sp or ""),
            int(frame_idx),
        )

    def _emit_cached_preview_frame(self, cache_key: tuple, detail: str, threshold_ms: float) -> bool:
        cache = self._last_preview_frame_cache
        if not isinstance(cache, dict) or cache.get("key") != cache_key:
            return False
        rgb = cache.get("rgb")
        if rgb is None:
            return False
        self._emit_rgb_frame(
            rgb,
            cache.get("grade"),
            f"{detail} cache=1",
            threshold_ms,
            gpu_meta=cache.get("gpu_meta"),
        )
        return True

    # ---------------- tracks ----------------

    def refresh_tracks(
        self,
        tracks: list,
        extra_duration_ms: int = 0,
        *,
        render_immediately: bool = True,
    ) -> None:
        """Rebuild decoders based on the given ordered track list.
        Preserves decoders for tracks whose source hasn't changed.
        Recomputes duration for each track from its video file.

        ``extra_duration_ms`` lets the caller extend the project timeline
        beyond what the video tracks alone would produce — used by the
        editor when audio tracks run past the last video frame, so
        playback continues (showing blank) until the audio ends.
        """
        from app.video_decoder import open_decoder

        def _sync_track_decoder_metadata(track, decoder) -> None:
            fps = float(getattr(decoder, "fps", 0.0) or 0.0)
            total_frames = int(getattr(decoder, "total_frames", 0) or 0)
            self._fps[track.id] = fps or 30.0
            self._total_frames[track.id] = total_frames
            if fps > 0.0 and total_frames > 0:
                track.duration_ms = int(total_frames / fps * 1000)

        new_ids = {t.id for t in tracks}
        # Release removed tracks (legacy per-track caps)
        for tid in list(self._caps.keys()):
            if tid not in new_ids:
                self._release_cap(tid)

        # Collect all source paths still in use across all clip lists.
        # Primary single-source track paths are opened in the per-track
        # pass below so duration/HDR metadata is synced before clip
        # views are built. Clip-only paths are eagerly opened here for
        # multi-source/appended clips.
        active_paths: set = set()
        eager_clip_paths: set = set()
        for t in tracks:
            track_source = (
                Path(t.source_path)
                if getattr(t, "source_path", None) is not None
                else None
            )
            for clip in _source_clips_for_track(t):
                sp = getattr(clip, "source_path", None)
                if sp is not None:
                    clip_path = Path(sp)
                    active_paths.add(clip_path)
                    if track_source is None or clip_path != track_source:
                        eager_clip_paths.add(clip_path)
            if track_source is not None:
                active_paths.add(track_source)
        # Release per-path decoders whose source is no longer referenced.
        for p in list(self._path_caps.keys()):
            if p not in active_paths:
                dec = self._path_caps.pop(p, None)
                self._path_fps.pop(p, None)
                if dec is not None:
                    try:
                        dec.release()
                    except Exception:
                        pass

        for p in sorted(eager_clip_paths, key=lambda v: str(v)):
            if p in self._path_caps:
                continue
            decoder = self._open_preview_decoder(open_decoder, p, hdr_info=None)
            if decoder is None:
                self.error_occurred.emit(f"Cannot open {p}")
                continue
            self._path_caps[p] = decoder
            self._path_fps[p] = float(decoder.fps or 30.0)

        for t in tracks:
            if t.source_path is None:
                # Multi-source track: open decoders for each clip source.
                track_clips = _source_clips_for_track(t)
                if not track_clips:
                    self._release_cap(t.id)
                    t.duration_ms = 0
                    continue
                for clip in track_clips:
                    sp = getattr(clip, "source_path", None)
                    if sp is None:
                        continue
                    sp = Path(sp)
                    if sp in self._path_caps:
                        continue  # already open
                    hdr_info = getattr(t, "hdr_info", None)
                    decoder = self._open_preview_decoder(open_decoder, sp, hdr_info=hdr_info)
                    if decoder is None:
                        self.error_occurred.emit(f"Cannot open {sp}")
                        continue
                    self._path_caps[sp] = decoder
                    self._path_fps[sp] = float(decoder.fps or 30.0)
                # duration from clip list (timeline_model VideoTrack already computes this)
                clip_dur = max(
                    (int(getattr(c, "timeline_out_ms", 0)) for c in track_clips),
                    default=0,
                )
                t.duration_ms = clip_dur
                continue
            # If a decoder already exists for this track id, keep it.
            # Callers re-call ``refresh_tracks`` after any change that
            # would invalidate the decoder.
            sp = Path(t.source_path)
            if sp in self._path_caps and self._caps.get(t.id) is None:
                decoder = self._path_caps[sp]
                self._caps[t.id] = decoder
                _sync_track_decoder_metadata(t, decoder)
                self._path_fps[sp] = self._fps.get(t.id, 30.0)
                continue
            if self._caps.get(t.id) is not None:
                decoder = self._caps[t.id]
                _sync_track_decoder_metadata(t, decoder)
                # Ensure the path → decoder mapping is populated even if
                # this track was registered before path_caps existed.
                if sp not in self._path_caps:
                    self._path_caps[sp] = decoder
                    self._path_fps[sp] = self._fps.get(t.id, 30.0)
                continue
            # HDR Phase 1: pick the right backend. ``hdr_info`` lives on
            # the track if the Media Pool already probed the source
            # (Phase 0); otherwise the factory falls back to cv2.
            hdr_info = getattr(t, "hdr_info", None)
            decoder = self._open_preview_decoder(open_decoder, t.source_path, hdr_info=hdr_info)
            if decoder is None:
                self.error_occurred.emit(f"Cannot open {t.source_path}")
                continue
            self._caps[t.id] = decoder
            _sync_track_decoder_metadata(t, decoder)
            # Also register in path_caps so multi-source lookup works
            # even for tracks that still have a track-level source_path.
            sp = Path(t.source_path)
            if sp not in self._path_caps:
                self._path_caps[sp] = decoder
                self._path_fps[sp] = self._fps[t.id]

        self._tracks = list(tracks)
        self.clear_preview_prerender_cache()
        # Phase 1.5d Step A: prefer the track's stored ``clips`` list
        # (the new source of truth) over a freshly-derived view. Falls
        # back to ``_build_clips_view`` ONLY for tracks that haven't been
        # through ``_ensure_video_clips`` yet (``clips_explicit`` is False).
        # When ``clips_explicit`` is True, the empty list is intentional
        # (user deleted all clips) and the fallback must NOT override it —
        # otherwise the player silently keeps rendering from the source
        # while the track row shows an empty state, confusing the user.
        self._clips_view = {
            t.id: (
                _clip_view_for_track(t) if (getattr(t, "clips", None) or getattr(t, "clips_explicit", False))
                else _build_clips_view(t)
            )
            for t in tracks
        }
        new_duration = max(
            (
                max(
                    int(getattr(t, "offset_ms", 0)) + int(getattr(t, "duration_ms", 0)),
                    max(
                        (int(getattr(c, "timeline_out_ms", 0)) for c in self._clips_view.get(t.id, ())),
                        default=0,
                    ),
                )
                for t in tracks
                if t.source_path is not None or getattr(t, "clips", None)
            ),
            default=0,
        )
        new_duration = max(new_duration, int(extra_duration_ms))
        self._duration_ms = new_duration
        self.duration_changed.emit(self._duration_ms)
        # Clamp position
        if self._position_ms > self._duration_ms:
            self._position_ms = self._duration_ms
        if not render_immediately:
            return
        if __debug__:
            from app.perf_monitor import perf_span
            with perf_span("preview.refresh.render", detail=f"pos={self._position_ms}"):
                self._render_frame_at(self._position_ms, force_seek=True)
        else:
            self._render_frame_at(self._position_ms, force_seek=True)

    def _release_cap(self, track_id: int) -> None:
        cap = self._caps.pop(track_id, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self._fps.pop(track_id, None)
        self._total_frames.pop(track_id, None)

    # ---------------- active track cascade ----------------

    def _active_track_at(self, pos_ms: int):
        """Return topmost track that should render at ``pos_ms``,
        cascading past cuts / past-end / before-start. None if all
        layers are empty at this time. ``pos_ms`` is project timeline
        time. Phase 1.5b: thin wrapper over ``_active_clip_at`` so
        legacy callers that only need the track keep working."""
        pair = self._active_clip_at(pos_ms)
        return pair[0] if pair else None

    def _active_clip_at(self, pos_ms: int):
        """Return the topmost ``(track, VideoClip)`` pair whose timeline
        window contains ``pos_ms``.

        Supports two track models:
        - Legacy single-source: ``t.source_path`` set, decoder in ``self._caps[t.id]``
        - Multi-source: ``t.source_path is None``, each clip has its own
          ``source_path`` with a decoder in ``self._path_caps``.

        Returns ``None`` when every layer is in a cut / before-start / past-end."""
        from app.vtuber.performance_source import (
            is_performance_source_clip,
            is_performance_source_track,
        )

        for t in reversed(self._tracks):
            # PIP tracks are overlay-only — skip them for the base render.
            if getattr(t, "pip_enabled", False):
                continue
            if is_performance_source_track(t):
                continue
            track_clips = self._clips_view.get(t.id, ())
            if t.source_path is None:
                # Multi-source track: only active if it has clips with decoders.
                if not any(
                    getattr(c, "source_path", None) is not None
                    and Path(c.source_path) in self._path_caps
                    for c in _source_clips_for_track(t)
                ):
                    continue
            else:
                # Legacy single-source: decoder may be in _caps or _path_caps.
                if t.id not in self._caps and not (
                    t.source_path is not None
                    and Path(t.source_path) in self._path_caps
                ):
                    continue
            for clip in track_clips:
                if clip.contains_timeline_ms(pos_ms):
                    if is_performance_source_clip(clip):
                        continue
                    if bool(getattr(clip, "is_nested_sequence", False)):
                        return t, clip
                    # For multi-source clips, also verify a decoder exists.
                    sp = getattr(clip, "source_path", None)
                    if sp is not None and Path(sp) not in self._path_caps:
                        continue
                    return t, clip
        return None

    @staticmethod
    def _speed_at(track, pos_ms: int) -> float:
        """``pos_ms`` is project time; speed segments are stored track-local."""
        local = pos_ms - getattr(track, "offset_ms", 0)
        from app.timeline_model import interpolate_speed_at
        return interpolate_speed_at(track, local)

    # ---------------- playback ----------------

    def play(self) -> None:
        # Allow playback as long as SOMETHING has duration — an audio-
        # only project (no video tracks, just AudioTracks via the
        # editor's ``extra_duration_ms``) still needs ticks so the
        # AudioMixer receives position_changed and actually plays.
        if self._duration_ms <= 0:
            return
        if self._shuttle_rate <= 0.0:
            self._shuttle_rate = 1.0
        self._last_playback_wall_s = time.monotonic()
        self._playback_fractional_ms = 0.0
        self._update_interval()
        self._timer.start()
        self._set_state(PlayerState.PLAYING)

    def play_until(self, end_ms: int, *, return_to_ms: int | None = None) -> None:
        """Play to ``end_ms`` and optionally restore the playhead afterward."""
        if self._duration_ms <= 0:
            return
        start_ms = int(self._position_ms)
        end = max(start_ms + 1, min(int(end_ms), int(self._duration_ms)))
        self._bounded_play_end_ms = end
        self._bounded_play_return_ms = (
            None
            if return_to_ms is None
            else max(0, min(int(return_to_ms), int(self._duration_ms)))
        )
        self.play()

    def pause(self) -> None:
        self._timer.stop()
        self._last_playback_wall_s = None
        self._playback_fractional_ms = 0.0
        self._bounded_play_end_ms = None
        self._bounded_play_return_ms = None
        self._set_state(PlayerState.PAUSED)

    def toggle(self) -> None:
        if self._state is PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        self._timer.stop()
        self._last_playback_wall_s = None
        self._playback_fractional_ms = 0.0
        self._set_state(PlayerState.STOPPED)

    def release(self) -> None:
        self._timer.stop()
        self._last_playback_wall_s = None
        self._playback_fractional_ms = 0.0
        for tid in list(self._caps.keys()):
            self._release_cap(tid)
        executor = getattr(self, "_ar_pbr_asset_import_executor", None)
        if executor is not None:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except TypeError:
                executor.shutdown(wait=False)
            except Exception:
                pass
            self._ar_pbr_asset_import_executor = None

    def _set_state(self, state: PlayerState) -> None:
        if state is not self._state:
            self._state = state
            self.state_changed.emit(state)

    def _update_interval(self) -> None:
        track = self._active_track_at(self._position_ms)
        speed = self._speed_at(track, self._position_ms) if track else 1.0
        effective = speed * max(0.0, self._shuttle_rate)
        self._current_segment_speed = speed
        interval = 1000.0 / (self.REFERENCE_FPS * max(0.05, effective))
        interval_ms = max(1, int(round(interval)))
        if self._window_move_guard_active:
            self._timer.setTimerType(Qt.TimerType.CoarseTimer)
            self._timer.setInterval(max(100, interval_ms))
            return
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(interval_ms)

    def set_window_move_guard(self, active: bool) -> None:
        """Relax playback ticks while Windows is moving the editor window."""
        active = bool(active)
        if active == self._window_move_guard_active:
            return
        self._window_move_guard_active = active
        if active:
            self._window_move_guard_prior_interval = int(self._timer.interval())
            self._window_move_guard_prior_timer_type = self._timer.timerType()
            self._timer.setTimerType(Qt.TimerType.CoarseTimer)
            self._timer.setInterval(max(100, int(self._timer.interval() or 0)))
            return
        self._timer.setTimerType(
            self._window_move_guard_prior_timer_type or Qt.TimerType.PreciseTimer
        )
        if self._state is PlayerState.PLAYING:
            self._update_interval()
        elif self._window_move_guard_prior_interval is not None:
            self._timer.setInterval(max(1, int(self._window_move_guard_prior_interval)))
        self._window_move_guard_prior_interval = None
        self._window_move_guard_prior_timer_type = Qt.TimerType.PreciseTimer

    def set_shuttle_rate(self, rate: float) -> None:
        """Phase 7: shuttle gear from the jog/shuttle dial. ``rate``
        multiplies the active segment speed; pass ``0.0`` to pause.
        Negative rates aren't supported by the timer-driven driver
        today (it doesn't run frames backward) — callers should map
        a reverse shuttle to ``pause`` until reverse playback lands."""
        if rate < 0.0:
            self._shuttle_rate = 0.0
            self.pause()
            return
        self._shuttle_rate = float(rate)
        if self._state is PlayerState.PLAYING:
            self._last_playback_wall_s = time.monotonic()
            self._playback_fractional_ms = 0.0
            self._update_interval()

    def set_speed(self, speed: float) -> None:
        """Refresh playback timing after the editor changes a speed segment."""
        try:
            self._current_segment_speed = max(0.1, float(speed))
        except Exception:
            self._current_segment_speed = 1.0
        if self._state is PlayerState.PLAYING:
            self._last_playback_wall_s = time.monotonic()
            self._playback_fractional_ms = 0.0
            self._update_interval()

    def _playback_advance_ms(self) -> int:
        """Return wall-clock playback advance for one preview tick.

        Video rendering can be slower than the timer interval for heavy sources
        such as 1080p AV1.  Project time must follow elapsed wall time so audio
        keeps playing continuously and late video frames are skipped instead of
        forcing repeated audio seeks.  Direct unit-test calls that happen
        earlier than the nominal frame interval still advance by one reference
        frame to preserve deterministic tick semantics.
        """
        reference_ms = 1000.0 / self.REFERENCE_FPS
        now = time.monotonic()
        last = self._last_playback_wall_s
        self._last_playback_wall_s = now
        elapsed_ms = reference_ms if last is None else max(reference_ms, (now - last) * 1000.0)
        elapsed_ms = min(elapsed_ms, 1000.0)
        if not bool(getattr(self, "_preview_frame_drop_allowed", True)):
            elapsed_ms = min(elapsed_ms, reference_ms)
        effective = max(0.0, float(self._current_segment_speed) * max(0.0, float(self._shuttle_rate)))
        advance = elapsed_ms * max(0.05, effective) + float(self._playback_fractional_ms)
        whole = max(1, int(advance))
        self._playback_fractional_ms = max(0.0, advance - whole)
        self._last_tick_advance_ms = whole
        return whole

    def _record_playback_frame_drop(self, advance_ms: int) -> None:
        if not bool(getattr(self, "_preview_frame_drop_allowed", True)):
            return
        reference_ms = 1000.0 / self.REFERENCE_FPS
        if float(advance_ms) < reference_ms * 1.5:
            return
        dropped = max(1, int(round(float(advance_ms) / max(1.0, reference_ms))) - 1)
        self._preview_frame_drop_count += dropped
        count = int(getattr(self, "_preview_frame_drop_count", 0) or 0)
        if count != dropped and count % 30 != 0:
            return
        try:
            from app.loading_performance import record_loading_event

            record_loading_event(
                "preview.playback",
                "frame_drop",
                status="ok",
                detail=f"advance_ms={int(advance_ms)}",
                metadata={
                    "advance_ms": int(advance_ms),
                    "dropped_frames": dropped,
                    "total_dropped_frames": count,
                    "quality_mode": str(getattr(self, "_preview_quality_mode", "auto")),
                },
            )
        except Exception:
            pass

    def _tick(self) -> None:
        if self._duration_ms <= 0:
            self.pause()
            return
        advance_ms = self._playback_advance_ms()
        self._record_playback_frame_drop(advance_ms)
        new_pos = self._position_ms + advance_ms
        bounded_end = self._bounded_play_end_ms
        playback_end = self._duration_ms if bounded_end is None else min(int(bounded_end), int(self._duration_ms))
        if new_pos >= playback_end:
            self._position_ms = playback_end
            if __debug__:
                from app.perf_monitor import perf_span
                with perf_span("preview.tick.render", detail=f"pos={playback_end}"):
                    self._render_frame_at(playback_end)
            else:
                self._render_frame_at(playback_end)
            self.position_changed.emit(self._position_ms)
            return_to = self._bounded_play_return_ms
            self._timer.stop()
            self._bounded_play_end_ms = None
            self._bounded_play_return_ms = None
            self._set_state(PlayerState.PAUSED)
            if return_to is not None:
                self.set_position(return_to)
            return
        self._position_ms = new_pos
        # Check if segment speed changed
        track = self._active_track_at(new_pos)
        new_speed = self._speed_at(track, new_pos) if track else 1.0
        if abs(new_speed - self._current_segment_speed) > 1e-4:
            self._current_segment_speed = new_speed
            self._update_interval()
        if __debug__:
            from app.perf_monitor import perf_span
            with perf_span("preview.tick.render", detail=f"pos={new_pos}"):
                self._render_frame_at(new_pos)
        else:
            self._render_frame_at(new_pos)
        self.position_changed.emit(new_pos)

    # ---------------- seek / rendering ----------------

    def set_position(self, ms: int) -> None:
        ms = max(0, min(int(ms), self._duration_ms))
        same_position = ms == self._position_ms
        self._position_ms = ms
        if self._state is PlayerState.PLAYING:
            self._last_playback_wall_s = time.monotonic()
            self._playback_fractional_ms = 0.0
        self._seek_retry_serial += 1
        retry_serial = self._seek_retry_serial
        if __debug__:
            from app.perf_monitor import perf_span
            with perf_span("preview.seek.render", detail=f"pos={ms}"):
                rendered = self._render_frame_at(
                    ms,
                    force_seek=not same_position,
                    allow_cached=same_position,
                )
        else:
            rendered = self._render_frame_at(
                ms,
                force_seek=not same_position,
                allow_cached=same_position,
            )
        self.position_changed.emit(ms)
        if not rendered:
            self._schedule_seek_render_retry(ms, retry_serial, attempt=0)

    def _schedule_seek_render_retry(self, ms: int, serial: int, *, attempt: int) -> None:
        delays = (45, 120, 260, 520)
        if attempt >= len(delays):
            return
        delay_ms = delays[attempt]

        def _retry() -> None:
            if serial != self._seek_retry_serial:
                return
            if int(ms) != int(self._position_ms):
                return
            rendered = self._render_frame_at(int(ms), force_seek=True, allow_cached=True)
            if not rendered:
                self._schedule_seek_render_retry(int(ms), serial, attempt=attempt + 1)

        QTimer.singleShot(delay_ms, _retry)

    def refresh_current_frame(self) -> None:
        """Re-render at the current playhead — used when the grade
        chain or track state changes without a position change so the
        preview reflects the new colour pipeline immediately."""
        self._render_frame_at(self._position_ms, force_seek=True)

    def clear_preview_prerender_cache(self) -> int:
        self._preview_prerender_generation += 1
        self._preview_prerender_cache.clear()
        self._last_preview_frame_cache = None
        return self._preview_prerender_generation

    def preview_prerender_generation(self) -> int:
        return int(self._preview_prerender_generation)

    def put_preview_prerender_frame(
        self,
        track_id: int,
        source_path: Path | str,
        frame_idx: int,
        generation: int,
        rgb,
    ) -> None:
        if int(generation) != self._preview_prerender_generation:
            return
        try:
            arr = np.ascontiguousarray(rgb).copy()
        except Exception:
            return
        key = (
            int(generation),
            int(track_id),
            str(Path(source_path)),
            int(frame_idx),
        )
        self._preview_prerender_cache[key] = arr
        self._preview_prerender_cache.move_to_end(key)
        while len(self._preview_prerender_cache) > self._preview_prerender_limit:
            self._preview_prerender_cache.popitem(last=False)

    def _preview_prerender_cache_get(
        self,
        track_id: int,
        source_path: Path | str | None,
        frame_idx: int,
    ):
        if source_path is None:
            return None
        key = (
            int(self._preview_prerender_generation),
            int(track_id),
            str(Path(source_path)),
            int(frame_idx),
        )
        value = self._preview_prerender_cache.get(key)
        if value is None:
            return None
        self._preview_prerender_cache.move_to_end(key)
        return value





















    # ---------------- frame blending helpers ----------------

    # ---------------- PIP compositing ----------------

    @staticmethod
    def _composite_pip(
        base_rgb: np.ndarray,
        pip_rgb: np.ndarray,
        track,
        x: float | None = None,
        y: float | None = None,
        scale: float | None = None,
        opacity: float | None = None,
    ) -> np.ndarray:
        """Composite ``pip_rgb`` onto ``base_rgb`` using the given PIP
        parameters.  Explicit ``x``, ``y``, ``scale``, ``opacity`` take
        priority; falls back to the track's static fields when omitted.

        ``x`` / ``y`` are the *centre* position in normalised 0–1
        coordinates.  ``scale`` is the PIP width as a fraction of the
        base frame width; height is scaled proportionally."""
        import cv2
        bh, bw = base_rgb.shape[:2]
        ph, pw = pip_rgb.shape[:2]

        # Resolve params — prefer explicit args, fall back to track fields.
        pip_scale_v = scale if scale is not None else float(getattr(track, "pip_scale", 0.3))
        pip_x_v     = x     if x     is not None else float(getattr(track, "pip_x", 0.5))
        pip_y_v     = y     if y     is not None else float(getattr(track, "pip_y", 0.5))
        pip_alpha_v = opacity if opacity is not None else float(getattr(track, "pip_opacity", 1.0))

        # Scale the PIP video to pip_scale * base width.
        new_w = max(1, int(bw * pip_scale_v))
        new_h = max(1, int(ph * (new_w / max(1, pw))))
        pip_scaled = cv2.resize(pip_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        pip_scaled = np.ascontiguousarray(pip_scaled)

        # Centre position in pixels.
        cx = int(pip_x_v * bw)
        cy = int(pip_y_v * bh)
        x1 = cx - new_w // 2
        y1 = cy - new_h // 2
        x2 = x1 + new_w
        y2 = y1 + new_h

        # Clamp to the base frame bounds.
        src_x1 = max(0, -x1);  src_y1 = max(0, -y1)
        dst_x1 = max(0, x1);   dst_y1 = max(0, y1)
        dst_x2 = min(bw, x2);  dst_y2 = min(bh, y2)
        src_x2 = src_x1 + (dst_x2 - dst_x1)
        src_y2 = src_y1 + (dst_y2 - dst_y1)

        if dst_x2 <= dst_x1 or dst_y2 <= dst_y1:
            return base_rgb

        result = base_rgb.copy()
        alpha = float(max(0.0, min(1.0, pip_alpha_v)))
        region = result[dst_y1:dst_y2, dst_x1:dst_x2].astype(np.float32)
        pip_region = pip_scaled[src_y1:src_y2, src_x1:src_x2].astype(np.float32)
        blended = region * (1.0 - alpha) + pip_region * alpha
        result[dst_y1:dst_y2, dst_x1:dst_x2] = np.clip(blended, 0, 255).astype(np.uint8)
        return result

    def set_spine_actor_tracks(self, tracks: list) -> None:
        """Set the list of SpineActorTrack objects to composite over video."""
        self._spine_actor_tracks = tracks
        self._last_preview_frame_cache = None
        self._spine_overlay_cache.clear()
        self._spine_direct_state_cache.clear()
        self._prewarm_spine_actor_renderers()

    def set_spine_gpu_overlay_enabled(self, enabled: bool) -> None:
        self._spine_gpu_overlay_enabled = bool(enabled)

    def spine_gpu_overlay_enabled(self) -> bool:
        return bool(getattr(self, "_spine_gpu_overlay_enabled", True))







    def _clip_effects_shader_available(
        self,
        clip,
        video_filters,
        chroma_key,
        bg_removal,
        pos_ms: int,
        has_masked_indices: bool,
    ) -> dict | None:
        if self.qimage_frame_enabled():
            return None
        if has_masked_indices:
            return None
        if bg_removal is not None and not bg_removal.is_identity():
            return None
        try:
            transition_ms = int(getattr(clip, "transition_out_ms", 0) or 0)
            transition_type = str(getattr(clip, "transition_out_type", "") or "")
            if transition_ms > 0 and transition_type:
                clip_out_ms = int(getattr(clip, "timeline_out_ms", 0) or 0)
                if int(pos_ms) >= clip_out_ms - transition_ms:
                    return None
        except Exception:
            pass
        if self._has_active_pip_overlays(pos_ms):
            return None
        if self._has_active_live2d_actors(pos_ms):
            return None
        if self._active_spine_clips(pos_ms) and not self._spine_direct_overlay_available(pos_ms):
            return None
        try:
            from app.preview_effects import build_shader_clip_effects
            return build_shader_clip_effects(video_filters, chroma_key)
        except Exception:
            return None

    @staticmethod
    def _merge_gpu_meta(*metas: dict | None) -> dict | None:
        merged: dict = {}
        for meta in metas:
            if meta:
                merged.update(meta)
        return merged or None



    def set_live2d_actor_tracks(self, tracks: list) -> None:
        """Set the list of Live2DActorTrack objects to composite over video."""
        self._live2d_actor_tracks = tracks
        self._last_preview_frame_cache = None
        self._prewarm_live2d_actor_renderers()




    def set_ar_pbr_tracks(self, tracks: list[dict] | None) -> None:
        """Set AR/PBR object tracks composited over the preview frame."""
        try:
            from app.ar_pbr.schema import normalize_ar_tracks

            self._ar_pbr_tracks = normalize_ar_tracks(list(tracks or []))
        except Exception:
            self._ar_pbr_tracks = list(tracks or [])
        self._ar_pbr_prewarm_asset_imports(self._ar_pbr_tracks)
        self._last_preview_frame_cache = None
        self._ar_pbr_gpu_packet_cache.clear()

    def ar_pbr_tracks(self) -> list[dict]:
        return list(getattr(self, "_ar_pbr_tracks", []) or [])

    def set_mmd_tracks(self, tracks: list[dict] | None) -> None:
        """Set MMD model tracks that are drawn by the editor OpenGL preview."""
        try:
            from app.mmd.schema import normalize_mmd_tracks

            self._mmd_tracks = normalize_mmd_tracks(list(tracks or []))
        except Exception:
            self._mmd_tracks = list(tracks or [])
        self._last_preview_frame_cache = None
        self._mmd_physics_cache.clear()
        self._mmd_last_frame_by_track.clear()

    def mmd_tracks(self) -> list[dict]:
        return list(getattr(self, "_mmd_tracks", []) or [])
















    def _on_ar_pbr_asset_import_ready(self, cache_key: str) -> None:
        if not self._ar_pbr_collect_asset_import(str(cache_key or "")):
            return
        try:
            self.refresh_current_frame()
        except Exception:
            pass




    @staticmethod
    def _default_ar_pbr_camera_solution(width: int, height: int) -> dict:
        focal = float(max(1, min(width, height))) * 1.15
        return {
            "id": "preview_default_camera",
            "frame_size": [int(width), int(height)],
            "intrinsics": {
                "fx": focal,
                "fy": focal,
                "cx": float(width) * 0.5,
                "cy": float(height) * 0.5,
            },
        }






















    @staticmethod
    def _alpha_composite_rgba_pil(base_rgb: np.ndarray, overlay) -> np.ndarray:
        """Composite an RGBA PIL image over an RGB ndarray."""
        if overlay is None:
            return base_rgb
        bbox = overlay.getbbox()
        if not bbox:
            return base_rgb

        h, w = base_rgb.shape[:2]
        x0, y0, x1, y1 = bbox
        x0 = max(0, min(w, x0)); x1 = max(0, min(w, x1))
        y0 = max(0, min(h, y0)); y1 = max(0, min(h, y1))
        if x1 <= x0 or y1 <= y0:
            return base_rgb

        result = base_rgb.copy()
        arr = np.asarray(overlay.crop((x0, y0, x1, y1)), dtype=np.uint16)
        if arr.ndim != 3 or arr.shape[2] < 4:
            return base_rgb

        alpha = arr[:, :, 3:4]
        if not np.any(alpha):
            return base_rgb
        dst = result[y0:y1, x0:x1].astype(np.uint16)
        result[y0:y1, x0:x1] = (
            (arr[:, :, :3] * alpha + dst * (255 - alpha) + 127) // 255
        ).astype(np.uint8)
        return result

    @staticmethod
    def _rgba_array_bbox(overlay: np.ndarray):
        if overlay is None or overlay.ndim != 3 or overlay.shape[2] < 4:
            return None
        alpha = overlay[:, :, 3]
        if not np.any(alpha):
            return None
        ys, xs = np.nonzero(alpha)
        return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1

    @staticmethod
    def _alpha_composite_rgba_array(base_rgb: np.ndarray, overlay: np.ndarray) -> np.ndarray:
        """Composite a straight-alpha RGBA ndarray over an RGB ndarray."""
        if overlay is None:
            return base_rgb
        if not isinstance(overlay, np.ndarray):
            return ProjectPlayer._alpha_composite_rgba_pil(base_rgb, overlay)
        bbox = ProjectPlayer._rgba_array_bbox(overlay)
        if not bbox:
            return base_rgb
        h, w = base_rgb.shape[:2]
        x0, y0, x1, y1 = bbox
        x0 = max(0, min(w, x0)); x1 = max(0, min(w, x1))
        y0 = max(0, min(h, y0)); y1 = max(0, min(h, y1))
        if x1 <= x0 or y1 <= y0:
            return base_rgb

        result = base_rgb.copy()
        ov = overlay[y0:y1, x0:x1, :4].astype(np.uint16)
        alpha = ov[:, :, 3:4]
        if not np.any(alpha):
            return base_rgb
        dst = result[y0:y1, x0:x1].astype(np.uint16)
        if np.all(alpha == 255):
            result[y0:y1, x0:x1] = ov[:, :, :3].astype(np.uint8)
            return result
        result[y0:y1, x0:x1] = (
            (ov[:, :, :3] * alpha + dst * (255 - alpha) + 127) // 255
        ).astype(np.uint8)
        return result

    @staticmethod
    def _alpha_composite_rgba_overlay_inplace(dst_rgba: np.ndarray, src_rgba: np.ndarray) -> bool:
        """Source-over composite one RGBA overlay into another in-place."""
        bbox = ProjectPlayer._rgba_array_bbox(src_rgba)
        if not bbox:
            return False
        h, w = dst_rgba.shape[:2]
        x0, y0, x1, y1 = bbox
        x0 = max(0, min(w, x0)); x1 = max(0, min(w, x1))
        y0 = max(0, min(h, y0)); y1 = max(0, min(h, y1))
        if x1 <= x0 or y1 <= y0:
            return False

        dst_roi = dst_rgba[y0:y1, x0:x1, :4]
        if not np.any(dst_roi[:, :, 3]):
            dst_roi[:] = src_rgba[y0:y1, x0:x1, :4]
            return True

        src = src_rgba[y0:y1, x0:x1, :4].astype(np.uint32)
        dst = dst_roi.astype(np.uint32)
        sa = src[:, :, 3:4]
        da = dst[:, :, 3:4]
        inv_sa = 255 - sa
        out_a = sa + (da * inv_sa + 127) // 255
        out_pm = src[:, :, :3] * sa + (dst[:, :, :3] * da * inv_sa + 127) // 255
        out_rgb = np.zeros_like(dst[:, :, :3])
        mask = out_a[:, :, 0] > 0
        if np.any(mask):
            denom = out_a[:, :, 0][mask][:, None]
            out_rgb[mask] = ((out_pm[mask] * 255 + denom // 2) // denom).clip(0, 255)
        dst_rgba[y0:y1, x0:x1, :3] = out_rgb.astype(np.uint8)
        dst_rgba[y0:y1, x0:x1, 3] = out_a[:, :, 0].clip(0, 255).astype(np.uint8)
        return True














    @staticmethod
    def _resize_rgba_pil(image, width: int, height: int):
        if image is None or (image.width == width and image.height == height):
            return image
        try:
            from PIL import Image
            return image.resize((int(width), int(height)), Image.Resampling.BILINEAR)
        except Exception:
            return image

    @staticmethod
    def _resize_rgba_array(image: np.ndarray, width: int, height: int):
        if image is None:
            return None
        if image.shape[1] == int(width) and image.shape[0] == int(height):
            return image
        try:
            import cv2
            resized = cv2.resize(
                image,
                (int(width), int(height)),
                interpolation=cv2.INTER_LINEAR,
            )
            return np.ascontiguousarray(resized.astype(np.uint8, copy=False))
        except Exception:
            try:
                from PIL import Image
                pil = Image.fromarray(image.astype(np.uint8, copy=False), "RGBA")
                pil = pil.resize((int(width), int(height)), Image.Resampling.BILINEAR)
                return np.asarray(pil, dtype=np.uint8).copy()
            except Exception:
                return None















    def _emit_blank(self) -> None:
        from app.perf_monitor import stage_threshold_ms

        rgb = np.zeros((9, 16, 3), dtype=np.uint8)
        detail = f"pos={self._position_ms} blank_black=1"
        self._emit_rgb_frame(rgb, None, detail, stage_threshold_ms())



    # ---------------- getters ----------------

    def position(self) -> int:
        return self._position_ms

    def duration(self) -> int:
        return self._duration_ms

    def state(self) -> PlayerState:
        return self._state

from app import project_player_mmd_workflow as _project_player_mmd_workflow

ProjectPlayer.mmd_diagnostics = _project_player_mmd_workflow.mmd_diagnostics
ProjectPlayer._active_mmd_tracks = _project_player_mmd_workflow._active_mmd_tracks
ProjectPlayer._mmd_model_for_path = _project_player_mmd_workflow._mmd_model_for_path
ProjectPlayer._mmd_motion_for_path = _project_player_mmd_workflow._mmd_motion_for_path
ProjectPlayer._mmd_motion_duration_ms = staticmethod(_project_player_mmd_workflow._mmd_motion_duration_ms)
ProjectPlayer._mmd_frame_for_track = _project_player_mmd_workflow._mmd_frame_for_track
ProjectPlayer._mmd_physics_backend_for_track = _project_player_mmd_workflow._mmd_physics_backend_for_track
ProjectPlayer._mmd_overlay_items = _project_player_mmd_workflow._mmd_overlay_items
ProjectPlayer._apply_or_defer_mmd_overlay = _project_player_mmd_workflow._apply_or_defer_mmd_overlay

from app import project_player_ar_pbr_workflow as _project_player_ar_pbr_workflow

ProjectPlayer._ar_pbr_pending_descriptor_for_path = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_pending_descriptor_for_path)
ProjectPlayer._ar_pbr_prepare_descriptor_support = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_prepare_descriptor_support)
ProjectPlayer._ar_pbr_import_asset_descriptor = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_import_asset_descriptor)
ProjectPlayer._ar_pbr_start_asset_import = _project_player_ar_pbr_workflow._ar_pbr_start_asset_import
ProjectPlayer._ar_pbr_prewarm_asset_imports = _project_player_ar_pbr_workflow._ar_pbr_prewarm_asset_imports
ProjectPlayer._ar_pbr_collect_asset_import = _project_player_ar_pbr_workflow._ar_pbr_collect_asset_import
ProjectPlayer._ar_pbr_descriptor_for_track = _project_player_ar_pbr_workflow._ar_pbr_descriptor_for_track
ProjectPlayer._ar_pbr_asset_descriptors = _project_player_ar_pbr_workflow._ar_pbr_asset_descriptors
ProjectPlayer._ar_pbr_public_asset_support_rows = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_public_asset_support_rows)
ProjectPlayer._ar_pbr_runtime_anchor_signature = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_runtime_anchor_signature)
ProjectPlayer._ar_pbr_track_cache_key = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_track_cache_key)
ProjectPlayer._ar_pbr_apply_cached_runtime_anchor = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_apply_cached_runtime_anchor)
ProjectPlayer._ar_pbr_runtime_tracks_for_frame = _project_player_ar_pbr_workflow._ar_pbr_runtime_tracks_for_frame
ProjectPlayer._ar_pbr_camera_solution_for_tracks = _project_player_ar_pbr_workflow._ar_pbr_camera_solution_for_tracks
ProjectPlayer._ar_pbr_depth_frame_for_tracks = _project_player_ar_pbr_workflow._ar_pbr_depth_frame_for_tracks
ProjectPlayer._ar_pbr_depth_view_context_for_frame = _project_player_ar_pbr_workflow._ar_pbr_depth_view_context_for_frame
ProjectPlayer._ar_pbr_gpu_preview_enabled = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_gpu_preview_enabled)
ProjectPlayer._ar_pbr_preview_renderer_mode = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_preview_renderer_mode)
ProjectPlayer._ar_pbr_should_use_full_gpu_preview = _project_player_ar_pbr_workflow._ar_pbr_should_use_full_gpu_preview
ProjectPlayer._ar_pbr_realtime_scene_anchor_enabled = _project_player_ar_pbr_workflow._ar_pbr_realtime_scene_anchor_enabled
ProjectPlayer._ar_pbr_realtime_depth_enabled = _project_player_ar_pbr_workflow._ar_pbr_realtime_depth_enabled
ProjectPlayer._ar_pbr_gpu_preview_triangle_limit = _project_player_ar_pbr_workflow._ar_pbr_gpu_preview_triangle_limit
ProjectPlayer._ar_pbr_depth_view_mode = _project_player_ar_pbr_workflow._ar_pbr_depth_view_mode
ProjectPlayer.set_ar_pbr_depth_view_mode = _project_player_ar_pbr_workflow.set_ar_pbr_depth_view_mode
ProjectPlayer.ar_pbr_depth_view_mode = _project_player_ar_pbr_workflow.ar_pbr_depth_view_mode
ProjectPlayer._ar_pbr_preview_context = _project_player_ar_pbr_workflow._ar_pbr_preview_context
ProjectPlayer._ar_pbr_depth_view_frame = _project_player_ar_pbr_workflow._ar_pbr_depth_view_frame
ProjectPlayer._ar_pbr_software_settings = _project_player_ar_pbr_workflow._ar_pbr_software_settings
ProjectPlayer._ar_pbr_cache_digest = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_cache_digest)
ProjectPlayer._ar_pbr_descriptor_fingerprint = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_descriptor_fingerprint)
ProjectPlayer._ar_pbr_descriptor_has_playing_animation = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_descriptor_has_playing_animation)
ProjectPlayer._ar_pbr_gpu_packet_cache_key = _project_player_ar_pbr_workflow._ar_pbr_gpu_packet_cache_key
ProjectPlayer._ar_pbr_tag_gpu_packet_items = staticmethod(_project_player_ar_pbr_workflow._ar_pbr_tag_gpu_packet_items)
ProjectPlayer._composite_ar_pbr_tracks = _project_player_ar_pbr_workflow._composite_ar_pbr_tracks
ProjectPlayer._apply_or_defer_ar_pbr_overlay = _project_player_ar_pbr_workflow._apply_or_defer_ar_pbr_overlay

from app import project_player_actor_workflow as _project_player_actor_workflow

ProjectPlayer._spine_preview_use_zero_readback = staticmethod(_project_player_actor_workflow._spine_preview_use_zero_readback)
ProjectPlayer._spine_direct_with_live2d = staticmethod(_project_player_actor_workflow._spine_direct_with_live2d)
ProjectPlayer._has_active_live2d_actors = _project_player_actor_workflow._has_active_live2d_actors
ProjectPlayer._spine_direct_overlay_items = _project_player_actor_workflow._spine_direct_overlay_items
ProjectPlayer._spine_direct_overlay_available = _project_player_actor_workflow._spine_direct_overlay_available
ProjectPlayer._has_active_pip_overlays = _project_player_actor_workflow._has_active_pip_overlays
ProjectPlayer._apply_or_defer_spine_overlay = _project_player_actor_workflow._apply_or_defer_spine_overlay
ProjectPlayer._prewarm_spine_actor_renderers = _project_player_actor_workflow._prewarm_spine_actor_renderers
ProjectPlayer._live2d_preview_prewarm_enabled = staticmethod(_project_player_actor_workflow._live2d_preview_prewarm_enabled)
ProjectPlayer._live2d_preview_prewarm_size = staticmethod(_project_player_actor_workflow._live2d_preview_prewarm_size)
ProjectPlayer._prewarm_live2d_actor_renderers = _project_player_actor_workflow._prewarm_live2d_actor_renderers
ProjectPlayer._spine_preview_render_size = staticmethod(_project_player_actor_workflow._spine_preview_render_size)
ProjectPlayer._spine_preview_complex_scale = staticmethod(_project_player_actor_workflow._spine_preview_complex_scale)
ProjectPlayer._spine_preview_playback_scale = staticmethod(_project_player_actor_workflow._spine_preview_playback_scale)
ProjectPlayer._spine_preview_render_size_for_active = _project_player_actor_workflow._spine_preview_render_size_for_active
ProjectPlayer._spine_preview_use_gl = staticmethod(_project_player_actor_workflow._spine_preview_use_gl)
ProjectPlayer._spine_preview_use_array_compositor = staticmethod(_project_player_actor_workflow._spine_preview_use_array_compositor)
ProjectPlayer._spine_preview_use_gl_compositor = staticmethod(_project_player_actor_workflow._spine_preview_use_gl_compositor)
ProjectPlayer._spine_preview_base_fps = staticmethod(_project_player_actor_workflow._spine_preview_base_fps)
ProjectPlayer._spine_complex_preview_fps = staticmethod(_project_player_actor_workflow._spine_complex_preview_fps)
ProjectPlayer._spine_complex_preview_threshold = staticmethod(_project_player_actor_workflow._spine_complex_preview_threshold)
ProjectPlayer._spine_quantized_preview_pos_ms = staticmethod(_project_player_actor_workflow._spine_quantized_preview_pos_ms)
ProjectPlayer._spine_preview_cache_pos_ms = staticmethod(_project_player_actor_workflow._spine_preview_cache_pos_ms)
ProjectPlayer._spine_preview_cache_pos_ms_for_active = _project_player_actor_workflow._spine_preview_cache_pos_ms_for_active
ProjectPlayer._spine_clip_signature = staticmethod(_project_player_actor_workflow._spine_clip_signature)
ProjectPlayer._active_spine_clips = _project_player_actor_workflow._active_spine_clips
ProjectPlayer._actor_clip_prerender_cache_safe = staticmethod(_project_player_actor_workflow._actor_clip_prerender_cache_safe)
ProjectPlayer._cached_actor_prerender_frame = _project_player_actor_workflow._cached_actor_prerender_frame
ProjectPlayer._spine_overlay_gl_composited = _project_player_actor_workflow._spine_overlay_gl_composited
ProjectPlayer._spine_overlay_image = _project_player_actor_workflow._spine_overlay_image
ProjectPlayer._spine_overlay_rgba = _project_player_actor_workflow._spine_overlay_rgba
ProjectPlayer._composite_spine_actors = _project_player_actor_workflow._composite_spine_actors
ProjectPlayer._composite_live2d_actors = _project_player_actor_workflow._composite_live2d_actors
ProjectPlayer._render_actor_only = _project_player_actor_workflow._render_actor_only
ProjectPlayer._render_live2d_only = _project_player_actor_workflow._render_live2d_only
ProjectPlayer._render_pip_overlays = _project_player_actor_workflow._render_pip_overlays

from app import project_player_render_workflow as _project_player_render_workflow

ProjectPlayer._emit_rgb_frame = _project_player_render_workflow._emit_rgb_frame
ProjectPlayer._decode_clip_rgb_for_nested = _project_player_render_workflow._decode_clip_rgb_for_nested
ProjectPlayer._render_nested_clip_content_rgb = _project_player_render_workflow._render_nested_clip_content_rgb
ProjectPlayer._apply_nested_clip_fades = _project_player_render_workflow._apply_nested_clip_fades
ProjectPlayer._apply_nested_transition_blend = _project_player_render_workflow._apply_nested_transition_blend
ProjectPlayer._render_nested_tracks_rgb = _project_player_render_workflow._render_nested_tracks_rgb
ProjectPlayer._composite_nested_spine_actors = _project_player_render_workflow._composite_nested_spine_actors
ProjectPlayer._composite_nested_live2d_actors = _project_player_render_workflow._composite_nested_live2d_actors
ProjectPlayer._render_nested_sequence_rgb = _project_player_render_workflow._render_nested_sequence_rgb
ProjectPlayer._emit_nested_sequence_frame = _project_player_render_workflow._emit_nested_sequence_frame
ProjectPlayer._render_frame_at = _project_player_render_workflow._render_frame_at
ProjectPlayer._blend_frames = staticmethod(_project_player_render_workflow._blend_frames)
ProjectPlayer._apply_transition_blend = _project_player_render_workflow._apply_transition_blend
