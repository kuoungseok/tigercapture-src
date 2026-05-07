from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage

from app.simple_video_player import PlayerState
from app.timeline_model import VideoClip, build_legacy_clips_view


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
        return bp.apply_with_mask(rgb, mask, invert_mask=invert)
    else:
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
                return np.clip(blended, 0, 255).astype(np.uint8)
        return apply_to_rgb(rgb, grade)


# Phase 1.5b kept this helper here while ``timeline_model`` only had
# the migration variant. Phase 1.5c moved the gap-preserving builder
# into ``timeline_model`` so paintEvent + drag handlers + the player
# all use the same one. This alias stays for the existing player
# call sites + tests.
def _build_clips_view(track) -> list[VideoClip]:
    return build_legacy_clips_view(track)


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
    # legacy QImage signal still fires so scopes/popout keep working.
    gpu_frame_ready = Signal(object, object)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(object)
    error_occurred = Signal(str)

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
        self._position_ms: int = 0
        self._duration_ms: int = 0
        self._state: PlayerState = PlayerState.STOPPED
        self._current_segment_speed: float = 1.0
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

    # ---------------- tracks ----------------

    def refresh_tracks(self, tracks: list, extra_duration_ms: int = 0) -> None:
        """Rebuild decoders based on the given ordered track list.
        Preserves decoders for tracks whose source hasn't changed.
        Recomputes duration for each track from its video file.

        ``extra_duration_ms`` lets the caller extend the project timeline
        beyond what the video tracks alone would produce — used by the
        editor when audio tracks run past the last video frame, so
        playback continues (showing blank) until the audio ends.
        """
        from app.video_decoder import open_decoder

        new_ids = {t.id for t in tracks}
        # Release removed tracks (legacy per-track caps)
        for tid in list(self._caps.keys()):
            if tid not in new_ids:
                self._release_cap(tid)

        # Collect all source paths still in use across all clip lists.
        active_paths: set = set()
        for t in tracks:
            for clip in getattr(t, "clips", []):
                sp = getattr(clip, "source_path", None)
                if sp is not None:
                    active_paths.add(Path(sp))
            sp = getattr(t, "source_path", None)
            if sp is not None:
                active_paths.add(Path(sp))
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

        for t in tracks:
            if t.source_path is None:
                # Multi-source track: open decoders for each clip source.
                track_clips = getattr(t, "clips", [])
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
                    decoder = open_decoder(sp, hdr_info=hdr_info)
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
            if self._caps.get(t.id) is not None:
                # Ensure the path → decoder mapping is populated even if
                # this track was registered before path_caps existed.
                sp = Path(t.source_path)
                if sp not in self._path_caps:
                    self._path_caps[sp] = self._caps[t.id]
                    self._path_fps[sp] = self._fps.get(t.id, 30.0)
                continue
            # HDR Phase 1: pick the right backend. ``hdr_info`` lives on
            # the track if the Media Pool already probed the source
            # (Phase 0); otherwise the factory falls back to cv2.
            hdr_info = getattr(t, "hdr_info", None)
            decoder = open_decoder(t.source_path, hdr_info=hdr_info)
            if decoder is None:
                self.error_occurred.emit(f"Cannot open {t.source_path}")
                continue
            self._caps[t.id] = decoder
            self._fps[t.id] = float(decoder.fps or 30.0)
            self._total_frames[t.id] = int(decoder.total_frames or 0)
            if decoder.fps > 0 and decoder.total_frames > 0:
                t.duration_ms = int(decoder.total_frames / decoder.fps * 1000)
            # Also register in path_caps so multi-source lookup works
            # even for tracks that still have a track-level source_path.
            sp = Path(t.source_path)
            if sp not in self._path_caps:
                self._path_caps[sp] = decoder
                self._path_fps[sp] = self._fps[t.id]

        self._tracks = list(tracks)
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
                list(t.clips) if (getattr(t, "clips", None) or getattr(t, "clips_explicit", False))
                else _build_clips_view(t)
            )
            for t in tracks
        }
        new_duration = max(
            (
                getattr(t, "offset_ms", 0) + t.duration_ms
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
        for t in reversed(self._tracks):
            # PIP tracks are overlay-only — skip them for the base render.
            if getattr(t, "pip_enabled", False):
                continue
            track_clips = self._clips_view.get(t.id, ())
            if t.source_path is None:
                # Multi-source track: only active if it has clips with decoders.
                if not any(
                    getattr(c, "source_path", None) is not None
                    and Path(c.source_path) in self._path_caps
                    for c in track_clips
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
        self._update_interval()
        self._timer.start()
        self._set_state(PlayerState.PLAYING)

    def pause(self) -> None:
        self._timer.stop()
        self._set_state(PlayerState.PAUSED)

    def toggle(self) -> None:
        if self._state is PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        self._timer.stop()
        self._set_state(PlayerState.STOPPED)

    def release(self) -> None:
        self._timer.stop()
        for tid in list(self._caps.keys()):
            self._release_cap(tid)

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
        self._timer.setInterval(max(1, int(round(interval))))

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
            self._update_interval()

    def _tick(self) -> None:
        if self._duration_ms <= 0:
            self.pause()
            return
        advance_ms = int(round(1000.0 / self.REFERENCE_FPS))
        new_pos = self._position_ms + advance_ms
        if new_pos >= self._duration_ms:
            self._position_ms = self._duration_ms
            self.position_changed.emit(self._position_ms)
            self.pause()
            return
        self._position_ms = new_pos
        # Check if segment speed changed
        track = self._active_track_at(new_pos)
        new_speed = self._speed_at(track, new_pos) if track else 1.0
        if abs(new_speed - self._current_segment_speed) > 1e-4:
            self._current_segment_speed = new_speed
            self._update_interval()
        self._render_frame_at(new_pos)
        self.position_changed.emit(new_pos)

    # ---------------- seek / rendering ----------------

    def set_position(self, ms: int) -> None:
        ms = max(0, min(int(ms), self._duration_ms))
        self._position_ms = ms
        self._render_frame_at(ms, force_seek=True)
        self.position_changed.emit(ms)

    def refresh_current_frame(self) -> None:
        """Re-render at the current playhead — used when the grade
        chain or track state changes without a position change so the
        preview reflects the new colour pipeline immediately."""
        self._render_frame_at(self._position_ms, force_seek=True)

    def _render_frame_at(self, pos_ms: int, force_seek: bool = False) -> None:
        # Phase 1.5b: render via the (track, clip) pair so the seek
        # frame index comes from the clip's source-ms window. For
        # single-source legacy tracks this lands on exactly the same
        # frame as the old ``pos_ms - offset_ms`` math; for tracks
        # with cuts the clip view already partitioned the source so
        # cut regions resolve to "no clip → fall through".
        # HDR Phase 1: ``decoder`` is now a ``VideoDecoder`` (cv2 for
        # SDR, ffmpeg+tonemap for HDR) — same surface either way.
        pair = self._active_clip_at(pos_ms)
        if pair is None:
            self._emit_blank()
            self._last_rendered_track_id = None
            self._last_rendered_clip_path = None
            return
        track, clip = pair
        # Resolve decoder and fps: prefer per-clip source_path (multi-source),
        # fall back to per-track decoder (legacy single-source).
        clip_sp = getattr(clip, "source_path", None)
        if clip_sp is not None:
            clip_sp = Path(clip_sp)
        if clip_sp is not None and clip_sp in self._path_caps:
            decoder = self._path_caps[clip_sp]
            fps = self._path_fps.get(clip_sp, 30.0)
        else:
            decoder = self._caps.get(track.id)
            fps = self._fps.get(track.id, 30.0)
            clip_sp = None  # fall back path: use track-level sequential opt
        if decoder is None or fps <= 0:
            return
        local_ms = clip.timeline_to_source_ms(pos_ms)
        frame_idx = int(local_ms / 1000.0 * fps)
        # Sequential read optimization: only seek when necessary.
        # The sequential key is now (track_id, clip_source_path) so switching
        # between clips with different source files always seeks.
        need_seek = (
            force_seek
            or track.id != self._last_rendered_track_id
            or clip_sp != self._last_rendered_clip_path
            or frame_idx != self._last_rendered_frame_idx + 1
        )
        if need_seek:
            decoder.seek_to_frame(frame_idx)
        rgb = decoder.read_rgb()
        if rgb is None:
            return
        self._last_rendered_track_id = track.id
        self._last_rendered_clip_path = clip_sp
        self._last_rendered_frame_idx = frame_idx

        # Slow-motion frame blending: when a SpeedSegment with
        # frame_blend=True covers this position and speed < 1.0, blend
        # adjacent source frames to eliminate the choppy "skip" look.
        local_offset_ms = getattr(track, "offset_ms", 0)
        track_local_ms = pos_ms - local_offset_ms
        active_seg = None
        for seg in getattr(track, "speed_segments", []):
            if seg.start_ms <= track_local_ms < seg.end_ms:
                active_seg = seg
                break
        if (
            active_seg is not None
            and getattr(active_seg, "frame_blend", False)
            and active_seg.speed < 1.0
        ):
            # Fractional position within this source frame (0.0–1.0)
            exact_frame = local_ms / 1000.0 * fps
            frac = exact_frame - frame_idx
            if frac > 1e-4:
                blend_mode = getattr(active_seg, "blend_mode", "linear")
                rgb = self._blend_frames(
                    rgb, decoder, frame_idx, frac, blend_mode
                )
                # After seeking to frame_idx+1 inside _blend_frames the
                # sequential-read state is stale — invalidate it.
                self._last_rendered_frame_idx = -1

        h, w = rgb.shape[:2]

        # Stabilizer (per clip, keyed by clip identity)
        _stab_params = getattr(clip, "stabilizer", None)
        if _stab_params is not None and not _stab_params.is_identity():
            _stab_key = id(clip)
            if _stab_key not in self._stabilizers or force_seek:
                from app.video_stabilizer import FrameStabilizer
                _s = FrameStabilizer(_stab_params)
                if force_seek:
                    _s.reset()
                self._stabilizers[_stab_key] = _s
            rgb = self._stabilizers[_stab_key].apply(rgb)

        # Zoom actor — applied BEFORE colour grading so the grade
        # operates on the cropped+rescaled pixels the user actually
        # sees. The look is identical either way at full strength but
        # this order gives smoother shadow/midtone masks during ramps.
        try:
            from app.video_editor_window import find_active_zoom, zoom_window_at
            zactor = find_active_zoom(track, local_ms)
        except Exception:
            zactor = None
        if zactor is not None:
            window = zoom_window_at(zactor, local_ms, w, h)
            if window is not None:
                cx, cy, cw, ch = window
                # Crop integer-aligned region then resize back to full
                # frame using OpenCV (cv2.resize is faster than PIL for
                # this size). Use INTER_LINEAR — INTER_CUBIC's halo on
                # high-contrast edges is more annoying than useful here.
                import cv2
                cx_i = max(0, int(round(cx)))
                cy_i = max(0, int(round(cy)))
                cw_i = max(1, int(round(cw)))
                ch_i = max(1, int(round(ch)))
                cx_i = min(cx_i, w - cw_i)
                cy_i = min(cy_i, h - ch_i)
                cropped = rgb[cy_i:cy_i + ch_i, cx_i:cx_i + cw_i]
                rgb = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
                rgb = np.ascontiguousarray(rgb)

        # DaVinci-style node-chain grading. ``color_grade_chain`` is a
        # live list of ``ColorGrade`` references owned by the
        # workbench's NodeItems — the editor rebuilds it when the
        # graph topology changes (graph_mutated signal). When there's
        # no chain (audio clip selected, project just loaded, etc.)
        # Unified node effect chain (Phase Blur): ``node_item_chain``
        # stores ``(node_item, masks)`` pairs in IN→OUT order and handles
        # BOTH color-grade nodes and blur nodes in sequence.  Falls back
        # to the legacy ``color_grade_chain`` when the chain hasn't been
        # migrated yet (e.g. audio clip active, project just loaded).
        node_item_chain = getattr(track, "node_item_chain", None)
        masked_indices = []  # must be defined before the check below
        # Pre-initialise so the GL-shader block below always finds these names.
        last_grade = None
        needs_cpu_pregrade = False
        if node_item_chain is not None:
            # Detect whether the last pure-colour-grade node in the chain
            # can be deferred to the GL fragment shader.  Conditions:
            #   • not a blur node  • no masks  • not bypassed
            #   • no hue-vs-hue or per-region-luma (not in shader)
            # When deferrable, skip it in the CPU loop and return it as
            # ``last_grade`` so the shader path handles it below.
            _defer_grade_idx = -1
            for _ci, (_ni, _mi) in enumerate(node_item_chain):
                if (getattr(_ni, "NODE_KIND", "") != "blur"
                        and not _mi
                        and not getattr(_ni, "bypassed", False)):
                    _g = getattr(_ni, "color_grade", None)
                    if _g is not None and not _g.is_identity():
                        _has_hue = any(abs(d) > 0.5 for _, d in getattr(_g, "hue_vs_hue", ()))
                        _has_lum = any(
                            getattr(_g, f"{r}_l", 0) != 0
                            for r in ("shadows", "midtones", "highlights", "offset")
                        )
                        if not _has_hue and not _has_lum:
                            _defer_grade_idx = _ci   # keep updating → last one wins

            for _ci, (node_item, masks) in enumerate(node_item_chain):
                if _ci == _defer_grade_idx:
                    last_grade = getattr(node_item, "color_grade", None)
                    continue   # shader will apply this grade
                try:
                    rgb = _apply_node_effect_player(node_item, rgb, masks or [], frame_idx)
                except Exception:
                    pass
            chain = []   # all other effects already baked
            mask_chain = []
        else:
            # Legacy colour-grade-only path.
            chain = getattr(track, "color_grade_chain", None)
            mask_chain = getattr(track, "node_mask_chain", None)
            if chain is None:
                single = getattr(track, "color_grade", None)
                chain = [single] if single is not None else []
                mask_chain = [None] * len(chain)
            if mask_chain is None or len(mask_chain) != len(chain):
                mask_chain = [None] * len(chain)
            paired = [
                (g, m) for g, m in zip(chain, mask_chain)
                if g is not None and not g.is_identity()
            ]
            chain = [g for g, _ in paired]
            mask_chain = [m for _, m in paired]
            from app.color_grading import apply_to_rgb
            from app.node_mask import evaluate_node_masks
            masked_indices = [i for i, m in enumerate(mask_chain) if m]
            if masked_indices:
                rgb_f = rgb.astype(np.float32)
                for i in masked_indices:
                    grade = chain[i]
                    mask_list = mask_chain[i]
                    mask = evaluate_node_masks(mask_list, rgb, frame_idx)
                    if mask is None:
                        continue
                    mh, mw = mask.shape[:2]
                    fh, fw = rgb.shape[:2]
                    if mh != fh or mw != fw:
                        continue
                    graded = apply_to_rgb(rgb, grade).astype(np.float32)
                    mf = mask[..., None]
                    np.add(mf * graded, (1.0 - mf) * rgb_f, out=rgb_f)
                rgb = np.clip(rgb_f, 0, 255).astype(np.uint8)
            chain = [g for i, g in enumerate(chain) if i not in masked_indices]

        # GL shader handles a single grade's brightness/contrast/
        # saturation/wheels/offset path. With multiple grades in the
        # chain the shader can't represent them all, so CPU-pregrade
        # everything but the LAST one and pass the last to the GL
        # path so live slider drags still feel snappy. With zero or
        # one grade we keep the existing fast path.
        # NOTE: last_grade / needs_cpu_pregrade are pre-initialised
        # before the node_item_chain block above (they must survive
        # the defer path where chain is left empty).  Do NOT reset
        # them here; let the chain-length checks below overwrite only
        # when the legacy path populated ``chain``.
        if len(chain) >= 2:
            from app.color_grading import apply_to_rgb
            for g in chain[:-1]:
                rgb = apply_to_rgb(rgb, g)
            last_grade = chain[-1]
            # The last grade may itself need CPU pre-grade (hue or
            # per-region luma) — same check as the legacy path.
            has_hue = any(abs(d) > 0.5 for _h, d in last_grade.hue_vs_hue)
            has_luma = any(
                getattr(last_grade, f"{r}_l", 0) != 0
                for r in ("shadows", "midtones", "highlights", "offset")
            )
            if has_hue or has_luma:
                rgb = apply_to_rgb(rgb, last_grade)
                needs_cpu_pregrade = True
        elif len(chain) == 1:
            last_grade = chain[0]
            has_hue = any(abs(d) > 0.5 for _h, d in last_grade.hue_vs_hue)
            has_luma = any(
                getattr(last_grade, f"{r}_l", 0) != 0
                for r in ("shadows", "midtones", "highlights", "offset")
            )
            if has_hue or has_luma:
                from app.color_grading import apply_to_rgb
                rgb = apply_to_rgb(rgb, last_grade)
                needs_cpu_pregrade = True

        # When all grades were consumed by mask compositing (chain=[]),
        # the GL shader has nothing left to do.  Emitting gpu_frame_ready
        # with grade=None *should* pass through the already-composited
        # texture — but in practice the GL surface and the QLabel can
        # race/interleave, occasionally showing a stale gray frame.
        # Sending the fully-composited frame only through the QImage path
        # sidesteps the issue: the QLabel always wins and no GL state
        # confusion arises.
        # Video filters (sharpen, vignette, denoise, chromatic aberration, glitch)
        _vf = getattr(clip, "video_filters", None)
        if _vf is not None and not _vf.is_identity():
            rgb = _vf.apply(rgb)

        # Chroma key
        _ck = getattr(clip, "chroma_key", None)
        if _ck is not None and not _ck.is_identity():
            rgb, _ = _ck.apply(rgb)

        # Background removal
        _bgr = getattr(clip, "bg_removal", None)
        if _bgr is not None and not _bgr.is_identity():
            rgb = _bgr.apply(rgb)

        if getattr(locals(), 'masked_indices', None) and not chain:
            # All work done CPU-side; skip GL, go straight to QImage.
            rgb = self._apply_transition_blend(rgb, track, clip, pos_ms, force_seek)
            # PIP overlay — composite any PIP-enabled tracks on top of the base.
            rgb = self._render_pip_overlays(rgb, pos_ms)
            qimg = QImage(
                rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888,
            ).copy()
            self.frame_ready.emit(qimg)
            return

        # Determine whether the GL fragment shader can handle this grade.
        # Simple grades (brightness/contrast/saturation/3-way wheels) are
        # fully supported by the shader.  Hue-vs-Hue and per-region luma
        # corrections are NOT in the shader — they were applied CPU-side
        # above (needs_cpu_pregrade) so the GL path receives a pre-graded
        # frame and the shader runs identity.
        # Apply grade CPU-side — GL shader path causes gray-preview race
        # condition (uniforms arrive in wrong order). CPU apply_to_rgb is
        # reliable and fast enough on 720p frames. Emit GL with grade=None
        # so the shader just blits the already-graded texture.
        if (last_grade is not None
                and not last_grade.is_identity()
                and not needs_cpu_pregrade):
            from app.color_grading import apply_to_rgb
            rgb = apply_to_rgb(rgb, last_grade)

        rgb = self._apply_transition_blend(rgb, track, clip, pos_ms, force_seek)
        rgb = self._render_pip_overlays(rgb, pos_ms)

        self.gpu_frame_ready.emit(rgb, None)   # GL blits pre-graded frame
        rgb_out = rgb   # CPU path already applied grade
        qimg = QImage(
            rgb_out.data, w, h, rgb_out.strides[0], QImage.Format.Format_RGB888
        ).copy()
        self.frame_ready.emit(qimg)

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

    def _render_pip_overlays(self, base_rgb: np.ndarray, pos_ms: int) -> np.ndarray:
        """Composite any PIP-enabled tracks onto ``base_rgb`` at ``pos_ms``.

        Iterates ``self._tracks`` from bottom to top and applies each track
        whose ``pip_enabled`` flag is True and that has a frame available at
        ``pos_ms``.  The base-track frame is passed in and returned (possibly
        modified)."""
        for track in self._tracks:
            if not getattr(track, "pip_enabled", False):
                continue
            # Find this track's clip at pos_ms.
            track_clips = self._clips_view.get(track.id, ())
            pip_clip = None
            for c in track_clips:
                if c.contains_timeline_ms(pos_ms):
                    sp = getattr(c, "source_path", None)
                    if sp is not None and Path(sp) in self._path_caps:
                        pip_clip = c
                        break
            if pip_clip is None:
                # Legacy single-source fallback.
                if track.id in self._caps:
                    # Build a dummy clip so we can compute source_ms.
                    sp = getattr(track, "source_path", None)
                    if sp is None:
                        continue
                    sp = Path(sp)
                    decoder = self._caps[track.id]
                    fps = self._fps.get(track.id, 30.0)
                    local_ms = pos_ms - getattr(track, "offset_ms", 0)
                    if local_ms < 0 or local_ms > getattr(track, "duration_ms", 0):
                        continue
                    frame_idx = int(local_ms / 1000.0 * fps)
                    try:
                        decoder.seek_to_frame(frame_idx)
                        pip_rgb = decoder.read_rgb()
                    except Exception:
                        pip_rgb = None
                    if pip_rgb is None:
                        continue
                    kfs = getattr(track, "pip_keyframes", [])
                    pip_x, pip_y, pip_scale, pip_opacity = _interpolate_pip_params(kfs, pos_ms, track)
                    base_rgb = self._composite_pip(base_rgb, pip_rgb, track,
                                                   x=pip_x, y=pip_y, scale=pip_scale, opacity=pip_opacity)
                continue
            # Multi-source / clip-list path.
            sp = Path(pip_clip.source_path)
            decoder = self._path_caps.get(sp)
            fps = self._path_fps.get(sp, 30.0)
            if decoder is None or fps <= 0:
                continue
            local_ms = pip_clip.timeline_to_source_ms(pos_ms)
            frame_idx = int(local_ms / 1000.0 * fps)
            try:
                decoder.seek_to_frame(frame_idx)
                pip_rgb = decoder.read_rgb()
            except Exception:
                pip_rgb = None
            if pip_rgb is None:
                continue
            kfs = getattr(track, "pip_keyframes", [])
            pip_x, pip_y, pip_scale, pip_opacity = _interpolate_pip_params(kfs, pos_ms, track)
            base_rgb = self._composite_pip(base_rgb, pip_rgb, track,
                                           x=pip_x, y=pip_y, scale=pip_scale, opacity=pip_opacity)
        return base_rgb

    @staticmethod
    def _blend_frames(
        frame_n: np.ndarray,
        decoder,
        frame_idx: int,
        frac: float,
        blend_mode: str,
    ) -> np.ndarray:
        """Blend ``frame_n`` (frame at index ``frame_idx``) with the next
        source frame using ``frac`` as the mix weight toward the next frame.

        ``blend_mode`` selects the algorithm:
        - ``"linear"``:        simple weighted average (fast, robust)
        - ``"optical_flow"``:  Farneback motion-compensated warp for smoother
                               motion, falls back to linear on any error.

        Returns a blended RGB uint8 ndarray of the same shape as ``frame_n``.
        """
        # Fetch next frame — always needs a seek since we just read frame_n.
        try:
            decoder.seek_to_frame(frame_idx + 1)
            frame_n1 = decoder.read_rgb()
        except Exception:
            frame_n1 = None
        if frame_n1 is None:
            return frame_n

        h, w = frame_n.shape[:2]
        nh, nw = frame_n1.shape[:2]
        if nh != h or nw != w:
            # Dimension mismatch (shouldn't happen within one clip) — skip blend
            return frame_n

        # --- Optical flow path (computed at 1/4 res for speed) ---
        if blend_mode == "optical_flow":
            try:
                import cv2
                # Downscale to ~480p for optical flow computation
                scale = min(1.0, 480.0 / max(h, 1))
                sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
                small_n = cv2.resize(frame_n, (sw, sh), interpolation=cv2.INTER_LINEAR)
                small_n1 = cv2.resize(frame_n1, (sw, sh), interpolation=cv2.INTER_LINEAR)
                gray_n = cv2.cvtColor(small_n, cv2.COLOR_RGB2GRAY)
                gray_n1 = cv2.cvtColor(small_n1, cv2.COLOR_RGB2GRAY)
                flow_small = cv2.calcOpticalFlowFarneback(
                    gray_n, gray_n1, None,
                    pyr_scale=0.5, levels=2, winsize=11,
                    iterations=2, poly_n=5, poly_sigma=1.1, flags=0,
                )
                # Upscale flow to original resolution
                flow = cv2.resize(flow_small, (w, h)) / scale
                xs = np.arange(w, dtype=np.float32)
                ys = np.arange(h, dtype=np.float32)
                map_x, map_y = np.meshgrid(xs, ys)
                map_x = map_x + flow[:, :, 0] * float(frac)
                map_y = map_y + flow[:, :, 1] * float(frac)
                warped = cv2.remap(
                    frame_n, map_x, map_y, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE,
                )
                blended = cv2.addWeighted(
                    warped, float(1.0 - frac),
                    frame_n1, float(frac), 0.0,
                )
                return blended
            except Exception:
                pass  # fall through to linear

        # --- Linear blend (default / fallback) ---
        a = float(1.0 - frac)
        b = float(frac)
        blended = np.clip(
            frame_n.astype(np.float32) * a + frame_n1.astype(np.float32) * b,
            0, 255,
        ).astype(np.uint8)
        return blended

    def _emit_blank(self) -> None:
        # Small dark image to indicate "all tracks transparent/ended here"
        qimg = QImage(16, 9, QImage.Format.Format_RGB888)
        qimg.fill(Qt.GlobalColor.black)
        self.frame_ready.emit(qimg)

    def _apply_transition_blend(
        self, rgb: np.ndarray, track, clip, pos_ms: int, force_seek: bool
    ) -> np.ndarray:
        """Apply clip transition-out blending when pos_ms is inside the
        transition zone (last transition_out_ms ms of the clip).

        Supported types:
          fade_black  — multiply current frame toward black
          fade_white  — blend toward solid white
          dissolve    — cross-fade to the next clip on the same track
        Returns the (possibly modified) rgb ndarray."""
        ttype = str(getattr(clip, "transition_out_type", ""))
        if not ttype:
            return rgb
        t_ms = max(1, int(getattr(clip, "transition_out_ms", 500)))
        clip_out_ms = int(clip.timeline_out_ms)
        t_start_ms = clip_out_ms - t_ms
        if pos_ms < t_start_ms:
            return rgb
        # alpha = 0.0 at start of transition → 1.0 at end (= fully transitioned)
        alpha = min(1.0, max(0.0, (pos_ms - t_start_ms) / max(1, t_ms)))

        import cv2
        if ttype == "fade_black":
            # Multiply toward black: frame * (1 - alpha)
            scale = float(1.0 - alpha)
            return np.clip(
                (rgb.astype(np.float32) * scale), 0, 255
            ).astype(np.uint8)

        if ttype == "fade_white":
            # Blend toward white: frame*(1-alpha) + 255*alpha
            scale = float(1.0 - alpha)
            white = np.full_like(rgb, 255, dtype=np.float32)
            blended = rgb.astype(np.float32) * scale + white * alpha
            return np.clip(blended, 0, 255).astype(np.uint8)

        # Helper: fetch the next clip's frame (used by dissolve / slide / wipe).
        def _fetch_next_frame():
            clips_on_track = self._clips_view.get(track.id, [])
            sorted_clips = sorted(clips_on_track, key=lambda c: int(c.timeline_in_ms))
            next_clip = None
            for sc in sorted_clips:
                if int(sc.timeline_in_ms) >= clip_out_ms:
                    next_clip = sc
                    break
            if next_clip is None:
                return None
            next_sp = getattr(next_clip, "source_path", None)
            if next_sp is not None:
                next_sp = Path(next_sp)
            if next_sp is not None and next_sp in self._path_caps:
                next_decoder = self._path_caps[next_sp]
                fps = self._path_fps.get(next_sp, 30.0)
            elif track.id in self._caps:
                next_decoder = self._caps[track.id]
                fps = self._fps.get(track.id, 30.0)
            else:
                return None
            next_offset_ms = pos_ms - t_start_ms
            next_source_ms = int(next_clip.source_in_ms) + next_offset_ms
            next_frame_idx = int(next_source_ms / 1000.0 * fps)
            try:
                next_decoder.seek_to_frame(next_frame_idx)
                rgb_n = next_decoder.read_rgb()
                self._last_rendered_frame_idx = -1
                self._last_rendered_clip_path = None
                return rgb_n
            except Exception:
                return None

        if ttype == "dissolve":
            # Cross-dissolve: fade out current clip (alpha→0) while fading in
            # the NEXT clip on the same track (alpha→1).
            rgb_next = _fetch_next_frame()
            if rgb_next is None:
                # No next clip — just fade to black as fallback
                scale = float(1.0 - alpha)
                return np.clip(
                    rgb.astype(np.float32) * scale, 0, 255
                ).astype(np.uint8)
            h, w = rgb.shape[:2]
            nh, nw = rgb_next.shape[:2]
            if nh != h or nw != w:
                rgb_next = cv2.resize(rgb_next, (w, h), interpolation=cv2.INTER_LINEAR)
                rgb_next = np.ascontiguousarray(rgb_next)
            # current clip fades out (1-alpha), next clip fades in (alpha)
            blended = cv2.addWeighted(
                rgb, float(1.0 - alpha), rgb_next, float(alpha), 0.0
            )
            return blended

        if ttype == "slide_left":
            # Current clip slides out to the left; next clip enters from the right.
            rgb_next = _fetch_next_frame()
            h, w = rgb.shape[:2]
            offset = int(alpha * w)
            canvas = np.zeros_like(rgb)
            # Current clip shifted left by offset
            if offset < w:
                canvas[:, 0:w - offset] = rgb[:, offset:w]
            # Next clip slides in from the right
            if rgb_next is not None:
                nh, nw = rgb_next.shape[:2]
                if nh != h or nw != w:
                    rgb_next = cv2.resize(rgb_next, (w, h), interpolation=cv2.INTER_LINEAR)
                    rgb_next = np.ascontiguousarray(rgb_next)
                right_start = w - offset
                if right_start < w:
                    canvas[:, right_start:w] = rgb_next[:, 0:offset]
            return canvas

        if ttype == "wipe_left":
            # Left-to-right wipe reveal: columns 0..reveal show next clip.
            rgb_next = _fetch_next_frame()
            h, w = rgb.shape[:2]
            reveal = int(alpha * w)
            canvas = rgb.copy()
            if rgb_next is not None:
                nh, nw = rgb_next.shape[:2]
                if nh != h or nw != w:
                    rgb_next = cv2.resize(rgb_next, (w, h), interpolation=cv2.INTER_LINEAR)
                    rgb_next = np.ascontiguousarray(rgb_next)
                if reveal > 0:
                    canvas[:, 0:reveal] = rgb_next[:, 0:reveal]
            return canvas

        if ttype == "zoom_in":
            # Current clip scales up (zooms in) while fading out.
            h, w = rgb.shape[:2]
            scale_factor = 1.0 + alpha * 0.5   # 1.0 → 1.5
            fade = float(1.0 - alpha)
            new_w = int(w * scale_factor)
            new_h = int(h * scale_factor)
            zoomed = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            x0 = (new_w - w) // 2
            y0 = (new_h - h) // 2
            cropped = zoomed[y0:y0 + h, x0:x0 + w]
            result = np.clip(cropped.astype(np.float32) * fade, 0, 255).astype(np.uint8)
            return result

        if ttype == "zoom_out":
            # Current clip scales down (zooms out) while fading out.
            h, w = rgb.shape[:2]
            scale_factor = 1.0 - alpha * 0.4   # 1.0 → 0.6
            scale_factor = max(0.05, scale_factor)
            fade = float(1.0 - alpha)
            new_w = max(1, int(w * scale_factor))
            new_h = max(1, int(h * scale_factor))
            small = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            canvas = np.zeros_like(rgb)
            x0 = (w - new_w) // 2
            y0 = (h - new_h) // 2
            canvas[y0:y0 + new_h, x0:x0 + new_w] = small
            result = np.clip(canvas.astype(np.float32) * fade, 0, 255).astype(np.uint8)
            return result

        return rgb

    # ---------------- getters ----------------

    def position(self) -> int:
        return self._position_ms

    def duration(self) -> int:
        return self._duration_ms

    def state(self) -> PlayerState:
        return self._state
