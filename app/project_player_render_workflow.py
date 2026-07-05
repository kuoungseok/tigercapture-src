from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtGui import QImage


def _apply_node_chain_preview_compare(*args, **kwargs):
    from app.project_player import _apply_node_chain_preview_compare as _impl

    return _impl(*args, **kwargs)


def _apply_node_effect_player(*args, **kwargs):
    from app.project_player import _apply_node_effect_player as _impl

    return _impl(*args, **kwargs)


def _screenstudio_owner_for_preview(*args, **kwargs):
    from app.project_player import _screenstudio_owner_for_preview as _impl

    return _impl(*args, **kwargs)


def _emit_rgb_frame(
    self,
    rgb: np.ndarray,
    grade,
    detail: str,
    threshold_ms: float,
    gpu_meta: dict | None = None,
    cache_key: tuple | None = None,
) -> None:
    """Emit a final preview RGB frame to GPU and optional QImage paths."""
    from app.perf_monitor import perf_span

    if rgb is None:
        return
    rgb_out = np.ascontiguousarray(rgb)
    h, w = rgb_out.shape[:2]
    gpu_payload = grade
    if gpu_meta:
        gpu_payload = dict(gpu_meta)
        if grade is not None or "grade" not in gpu_payload:
            gpu_payload["grade"] = grade
    with perf_span("preview.stage.emit_gpu", detail=detail, threshold_ms=threshold_ms):
        self.gpu_frame_ready.emit(rgb_out, gpu_payload)
    if not self.qimage_frame_enabled():
        if cache_key is not None:
            self._last_preview_frame_cache = {
                "key": cache_key,
                "rgb": rgb_out.copy(),
                "grade": grade,
                "gpu_meta": dict(gpu_meta) if isinstance(gpu_meta, dict) else gpu_meta,
            }
        return
    with perf_span("preview.stage.qimage", detail=detail, threshold_ms=threshold_ms):
        qimg = QImage(
            rgb_out.data, w, h, rgb_out.strides[0], QImage.Format.Format_RGB888
        ).copy()
    self.frame_ready.emit(qimg)
    if cache_key is not None:
        self._last_preview_frame_cache = {
            "key": cache_key,
            "rgb": rgb_out.copy(),
            "grade": grade,
            "gpu_meta": dict(gpu_meta) if isinstance(gpu_meta, dict) else gpu_meta,
        }


def _decode_clip_rgb_for_nested(self, clip, nested_pos_ms: int):
    from app.perf_monitor import perf_span, stage_threshold_ms

    _perf_stage_ms = stage_threshold_ms()
    _perf_detail = f"nested_pos={nested_pos_ms}"
    sp = getattr(clip, "source_path", None)
    if sp is None:
        return None, 0
    sp = Path(sp)
    decoder = self._path_caps.get(sp)
    fps = float(self._path_fps.get(sp, 30.0))
    if decoder is None or fps <= 0:
        return None, 0
    source_ms = int(getattr(clip, "source_in_ms", 0)) + (
        int(nested_pos_ms) - int(getattr(clip, "timeline_in_ms", 0))
    )
    frame_idx = max(0, int(source_ms / 1000.0 * fps))
    with perf_span(
        "preview.stage.nested_decode",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        try:
            decoder.seek_to_frame(frame_idx)
            rgb = decoder.read_rgb()
        except Exception:
            rgb = None
    if rgb is None:
        return None, frame_idx
    try:
        params = getattr(clip, "stabilizer", None)
        if params is not None and not params.is_identity():
            from app.video_stabilizer import FrameStabilizer
            key = ("nested", id(clip))
            stabilizer = self._stabilizers.get(key)
            if stabilizer is None:
                stabilizer = FrameStabilizer(params)
                self._stabilizers[key] = stabilizer
            with perf_span(
                "preview.stage.nested_stabilizer",
                detail=f"{_perf_detail} frame={frame_idx}",
                threshold_ms=_perf_stage_ms,
            ):
                apply_preview = getattr(stabilizer, "apply_preview", None)
                rgb = apply_preview(rgb) if callable(apply_preview) else stabilizer.apply(rgb)
    except Exception:
        pass
    video_filters = getattr(clip, "video_filters", None)
    chroma_key = getattr(clip, "chroma_key", None)
    batched_effects = False
    try:
        from app.preview_effects import apply_filter_chroma_preview_batch
        with perf_span(
            "preview.stage.nested_filter_chroma_batch",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb, _alpha, batched_effects = apply_filter_chroma_preview_batch(
                rgb,
                video_filters,
                chroma_key,
            )
    except Exception:
        batched_effects = False
    if not batched_effects:
        try:
            params = video_filters
            if params is not None and not params.is_identity():
                apply_preview = getattr(params, "apply_preview", None)
                with perf_span(
                    "preview.stage.nested_video_filters",
                    detail=f"{_perf_detail} frame={frame_idx}",
                    threshold_ms=_perf_stage_ms,
                ):
                    rgb = apply_preview(rgb) if callable(apply_preview) else params.apply(rgb)
        except Exception:
            pass
        try:
            params = chroma_key
            if params is not None and not params.is_identity():
                apply_preview = getattr(params, "apply_preview", None)
                with perf_span(
                    "preview.stage.nested_chroma_key",
                    detail=f"{_perf_detail} frame={frame_idx}",
                    threshold_ms=_perf_stage_ms,
                ):
                    rgb, _alpha = apply_preview(rgb) if callable(apply_preview) else params.apply(rgb)
        except Exception:
            pass
    try:
        params = getattr(clip, "bg_removal", None)
        if params is not None and not params.is_identity():
            with perf_span(
                "preview.stage.nested_background_removal",
                detail=f"{_perf_detail} frame={frame_idx}",
                threshold_ms=_perf_stage_ms,
            ):
                rgb = params.apply(rgb)
    except Exception:
        pass
    try:
        ng = getattr(clip, "node_graph", None)
        color_node = getattr(ng, "color", None)
        grade = getattr(color_node, "grade", None)
        if grade is not None and not grade.is_identity():
            from app.color_grading import apply_to_rgb
            with perf_span(
                "preview.stage.nested_color_grade",
                detail=f"{_perf_detail} frame={frame_idx}",
                threshold_ms=_perf_stage_ms,
            ):
                rgb = apply_to_rgb(rgb, grade)
    except Exception:
        pass
    try:
        actors = [
            actor for actor in getattr(clip, "typography_actors", []) or []
            if int(getattr(actor, "start_ms", 0)) <= source_ms < int(getattr(actor, "end_ms", 0))
        ]
        if actors:
            from app.typo_render import render_clip_frame
            with perf_span(
                "preview.stage.nested_typography",
                detail=f"{_perf_detail} frame={frame_idx}",
                threshold_ms=_perf_stage_ms,
            ):
                h, w = rgb.shape[:2]
                base = rgb.astype(np.float32)
                for actor in actors:
                    local_s = max(0.0, (source_ms - int(getattr(actor, "start_ms", 0))) / 1000.0)
                    img = render_clip_frame(actor, local_s, w, h).convertToFormat(
                        QImage.Format.Format_RGBA8888
                    )
                    bpl = int(img.bytesPerLine())
                    arr = np.frombuffer(img.bits(), dtype=np.uint8).reshape((h, bpl))[:, :w * 4]
                    rgba = arr.reshape((h, w, 4)).astype(np.float32)
                    alpha = rgba[:, :, 3:4] / 255.0
                    base = rgba[:, :, :3] * alpha + base * (1.0 - alpha)
                rgb = np.clip(base, 0, 255).astype(np.uint8)
    except Exception:
        pass
    return rgb, frame_idx


def _render_nested_clip_content_rgb(self, clip, nested_pos_ms: int):
    if bool(getattr(clip, "is_nested_sequence", False)):
        return self._render_nested_sequence_rgb(clip, nested_pos_ms)
    rgb, _frame_idx = self._decode_clip_rgb_for_nested(clip, nested_pos_ms)
    return rgb


def _apply_nested_clip_fades(self, rgb: np.ndarray, clip, nested_pos_ms: int) -> np.ndarray:
    fades = list(getattr(clip, "fades", []) or [])
    if not fades:
        return rgb
    source_ms = int(getattr(clip, "source_in_ms", 0)) + (
        int(nested_pos_ms) - int(getattr(clip, "timeline_in_ms", 0))
    )
    scale = 1.0
    for fade in fades:
        if not fade.contains(source_ms):
            continue
        span = max(1, int(getattr(fade, "duration_ms", 0)))
        t = (source_ms - int(getattr(fade, "start_ms", 0))) / span
        kind = getattr(fade, "kind", "both")
        if kind == "in":
            scale *= max(0.0, min(1.0, t))
        elif kind == "out":
            scale *= max(0.0, min(1.0, 1.0 - t))
        else:
            if t < 0.5:
                scale *= max(0.0, min(1.0, 1.0 - t * 2.0))
            else:
                scale *= max(0.0, min(1.0, (t - 0.5) * 2.0))
    if scale >= 0.999:
        return rgb
    return np.clip(rgb.astype(np.float32) * float(scale), 0, 255).astype(np.uint8)


def _apply_nested_transition_blend(
    self,
    rgb: np.ndarray,
    clip,
    child_track: list,
    nested_pos_ms: int,
) -> np.ndarray:
    ttype = str(getattr(clip, "transition_out_type", "") or "")
    if not ttype:
        return rgb
    t_ms = max(1, int(getattr(clip, "transition_out_ms", 500)))
    clip_out_ms = int(getattr(clip, "timeline_out_ms", 0))
    t_start_ms = clip_out_ms - t_ms
    if int(nested_pos_ms) < t_start_ms:
        return rgb
    alpha = min(1.0, max(0.0, (int(nested_pos_ms) - t_start_ms) / max(1, t_ms)))
    if ttype == "fade_black":
        return np.clip(rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
    if ttype == "fade_white":
        white = np.full_like(rgb, 255, dtype=np.float32)
        return np.clip(rgb.astype(np.float32) * (1.0 - alpha) + white * alpha, 0, 255).astype(np.uint8)
    if ttype != "dissolve":
        return rgb
    next_clip = None
    for candidate in sorted(child_track, key=lambda c: int(getattr(c, "timeline_in_ms", 0))):
        if int(getattr(candidate, "timeline_in_ms", 0)) >= clip_out_ms:
            next_clip = candidate
            break
    if next_clip is None:
        return np.clip(rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
    next_pos = int(getattr(next_clip, "timeline_in_ms", 0)) + max(0, int(nested_pos_ms) - t_start_ms)
    rgb_next = self._render_nested_clip_content_rgb(next_clip, next_pos)
    if rgb_next is None:
        return np.clip(rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
    try:
        import cv2
        h, w = rgb.shape[:2]
        if rgb_next.shape[:2] != (h, w):
            rgb_next = cv2.resize(rgb_next, (w, h), interpolation=cv2.INTER_LINEAR)
        return cv2.addWeighted(rgb, float(1.0 - alpha), rgb_next, float(alpha), 0.0)
    except Exception:
        return rgb


def _render_nested_tracks_rgb(self, tracks: list[list], nested_pos_ms: int):
    # Nested child video tracks are currently opaque replacement layers:
    # the later active track overwrites earlier tracks instead of alpha
    # compositing. Walk top-down so hidden lower tracks are not decoded.
    for child_track in reversed(list(tracks or [])):
        active = None
        for child in sorted(child_track, key=lambda c: int(getattr(c, "timeline_in_ms", 0))):
            if child.contains_timeline_ms(nested_pos_ms):
                active = child
        if active is None:
            continue
        rgb = self._render_nested_clip_content_rgb(active, nested_pos_ms)
        if rgb is None:
            continue
        rgb = self._apply_nested_clip_fades(rgb, active, nested_pos_ms)
        rgb = self._apply_nested_transition_blend(rgb, active, child_track, nested_pos_ms)
        return rgb.copy()
    return None


def _composite_nested_spine_actors(self, rgb: np.ndarray, tracks: list, nested_pos_ms: int) -> np.ndarray:
    if not tracks:
        return rgb
    h, w = rgb.shape[:2]
    rw, rh = self._spine_preview_render_size(w, h)
    result = rgb
    use_array = self._spine_preview_use_array_compositor()
    for actor_track in tracks:
        for actor_clip in getattr(actor_track, "clips", []) or []:
            if not (int(getattr(actor_clip, "start_ms", 0)) <= nested_pos_ms < int(getattr(actor_clip, "end_ms", 0))):
                continue
            try:
                if use_array and hasattr(actor_clip, "render_frame_rgba"):
                    rgba = actor_clip.render_frame_rgba(
                        rw,
                        rh,
                        nested_pos_ms,
                        animated=True,
                        fast_preview=True,
                        use_gl=self._spine_preview_use_gl(),
                    )
                else:
                    pil_frame = actor_clip.render_frame(
                        rw,
                        rh,
                        nested_pos_ms,
                        animated=True,
                        fast_preview=True,
                        use_gl=self._spine_preview_use_gl(),
                    )
                    if not use_array:
                        pil_frame = self._resize_rgba_pil(pil_frame, w, h)
                        result = self._alpha_composite_rgba_pil(result, pil_frame)
                        continue
                    rgba = None if pil_frame is None else np.asarray(
                        pil_frame.convert("RGBA"),
                        dtype=np.uint8,
                    ).copy()
                if use_array:
                    rgba = self._resize_rgba_array(rgba, w, h)
                    result = self._alpha_composite_rgba_array(result, rgba)
            except Exception:
                pass
    return result


def _composite_nested_live2d_actors(self, rgb: np.ndarray, tracks: list, nested_pos_ms: int) -> np.ndarray:
    if not tracks:
        return rgb
    result = rgb
    h, w = rgb.shape[:2]
    for actor_track in tracks:
        try:
            pil_frame = actor_track.render_at(nested_pos_ms, w, h)
            result = self._alpha_composite_rgba_pil(result, pil_frame)
        except Exception:
            pass
    return result


def _render_nested_sequence_rgb(self, clip, pos_ms: int):
    from app.perf_monitor import perf_span, stage_threshold_ms

    tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
    spine_tracks = list(getattr(clip, "nested_spine_actor_tracks", []) or [])
    live2d_tracks = list(getattr(clip, "nested_live2d_actor_tracks", []) or [])
    if not tracks and not spine_tracks and not live2d_tracks:
        return None
    nested_pos_ms = int(pos_ms) - int(getattr(clip, "timeline_in_ms", 0))
    _perf_stage_ms = stage_threshold_ms()
    _perf_detail = f"pos={pos_ms} nested_pos={nested_pos_ms}"
    if tracks:
        with perf_span(
            "preview.stage.nested_tracks",
            detail=_perf_detail,
            threshold_ms=_perf_stage_ms,
        ):
            rgb = self._render_nested_tracks_rgb(tracks, nested_pos_ms)
    else:
        rgb = None
    if rgb is None and (spine_tracks or live2d_tracks):
        rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    if rgb is None:
        return None
    with perf_span(
        "preview.stage.nested_spine_overlay",
        detail=_perf_detail,
        threshold_ms=_perf_stage_ms,
    ):
        rgb = self._composite_nested_spine_actors(rgb, spine_tracks, nested_pos_ms)
    with perf_span(
        "preview.stage.nested_live2d_overlay",
        detail=_perf_detail,
        threshold_ms=_perf_stage_ms,
    ):
        rgb = self._composite_nested_live2d_actors(rgb, live2d_tracks, nested_pos_ms)
    return rgb


def _emit_nested_sequence_frame(self, rgb: np.ndarray, pos_ms: int) -> None:
    from app.perf_monitor import perf_span, stage_threshold_ms

    _perf_stage_ms = stage_threshold_ms()
    _perf_detail = f"pos={pos_ms} nested=1"
    gpu_meta = None
    with perf_span("preview.stage.pip_overlay", detail=_perf_detail, threshold_ms=_perf_stage_ms):
        rgb = self._render_pip_overlays(rgb, pos_ms)
    rgb, gpu_meta = self._apply_or_defer_spine_overlay(
        rgb,
        pos_ms,
        True,
        _perf_detail,
        _perf_stage_ms,
    )
    with perf_span("preview.stage.live2d_overlay", detail=_perf_detail, threshold_ms=_perf_stage_ms):
        rgb = self._composite_live2d_actors(rgb, pos_ms)
    with perf_span("preview.stage.ar_pbr_overlay", detail=_perf_detail, threshold_ms=_perf_stage_ms):
        rgb, ar_gpu_meta = self._apply_or_defer_ar_pbr_overlay(rgb, pos_ms)
        gpu_meta = self._merge_gpu_meta(gpu_meta, ar_gpu_meta)
    with perf_span("preview.stage.mmd_overlay", detail=_perf_detail, threshold_ms=_perf_stage_ms):
        rgb, mmd_gpu_meta = self._apply_or_defer_mmd_overlay(rgb, pos_ms, True)
        gpu_meta = self._merge_gpu_meta(gpu_meta, mmd_gpu_meta)
    self._emit_rgb_frame(rgb, None, _perf_detail, _perf_stage_ms, gpu_meta=gpu_meta)


def _render_frame_at(self, pos_ms: int, force_seek: bool = False, allow_cached: bool = False) -> None:
    from app.perf_monitor import perf_span, stage_threshold_ms

    _perf_stage_ms = stage_threshold_ms()
    _perf_detail = f"pos={pos_ms}"
    # Phase 1.5b: render via the (track, clip) pair so the seek
    # frame index comes from the clip's source-ms window. For
    # single-source legacy tracks this lands on exactly the same
    # frame as the old ``pos_ms - offset_ms`` math; for tracks
    # with cuts the clip view already partitioned the source so
    # cut regions resolve to "no clip → fall through".
    # HDR Phase 1: ``decoder`` is now a ``VideoDecoder`` (cv2 for
    # SDR, ffmpeg+tonemap for HDR) — same surface either way.
    with perf_span("preview.stage.active_clip", detail=_perf_detail, threshold_ms=_perf_stage_ms):
        pair = self._active_clip_at(pos_ms)
    if pair is None:
        # No video clip — but Live2D tracks may still have content.
        # Composite them over a black frame instead of showing blank.
        if self._spine_actor_tracks or self._live2d_actor_tracks or self._ar_pbr_tracks or self._mmd_tracks:
            self._render_actor_only(pos_ms)
        else:
            self._emit_blank()
        self._last_rendered_track_id = None
        self._last_rendered_clip_path = None
        return
    track, clip = pair
    if bool(getattr(clip, "is_nested_sequence", False)):
        rgb = self._render_nested_sequence_rgb(clip, pos_ms)
        if rgb is None:
            self._emit_blank()
            return
        self._last_rendered_track_id = None
        self._last_rendered_clip_path = None
        self._last_rendered_frame_idx = -1
        self._emit_nested_sequence_frame(rgb, pos_ms)
        return
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
    cache_key = self._preview_frame_cache_key(pos_ms, track, clip, clip_sp, frame_idx)
    if allow_cached and self._emit_cached_preview_frame(
        cache_key,
        f"{_perf_detail} frame={frame_idx}",
        _perf_stage_ms,
    ):
        return
    # Sequential read optimization: only seek when necessary.
    # The sequential key is now (track_id, clip_source_path) so switching
    # between clips with different source files always seeks.
    need_seek = (
        force_seek
        or track.id != self._last_rendered_track_id
        or clip_sp != self._last_rendered_clip_path
        or frame_idx != self._last_rendered_frame_idx + 1
    )
    with perf_span(
        "preview.stage.decode",
        detail=f"{_perf_detail} frame={frame_idx} seek={int(need_seek)}",
        threshold_ms=_perf_stage_ms,
    ):
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
            with perf_span(
                "preview.stage.frame_blend",
                detail=f"{_perf_detail} frame={frame_idx} mode={blend_mode}",
                threshold_ms=_perf_stage_ms,
            ):
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
        with perf_span(
            "preview.stage.stabilizer",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            stabilizer = self._stabilizers[_stab_key]
            apply_preview = getattr(stabilizer, "apply_preview", None)
            rgb = apply_preview(rgb) if callable(apply_preview) else stabilizer.apply(rgb)

    # Zoom actor — applied BEFORE colour grading so the grade
    # operates on the cropped+rescaled pixels the user actually
    # sees. The look is identical either way at full strength but
    # this order gives smoother shadow/midtone masks during ramps.
    try:
        from app.timeline_model import find_active_zoom, zoom_motion_blur_amount, zoom_window_at
        zactor = find_active_zoom(clip, local_ms) or find_active_zoom(track, local_ms)
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
            with perf_span(
                "preview.stage.zoom",
                detail=f"{_perf_detail} frame={frame_idx}",
                threshold_ms=_perf_stage_ms,
            ):
                rgb = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
                blur_amount = 0.0
                try:
                    blur_amount = float(zoom_motion_blur_amount(zactor, local_ms))
                except Exception:
                    blur_amount = 0.0
                if blur_amount > 0.001:
                    kernel = max(3, int(round(3 + blur_amount * 12)))
                    if kernel % 2 == 0:
                        kernel += 1
                    softened = cv2.GaussianBlur(rgb, (kernel, kernel), 0)
                    alpha = min(0.42, 0.12 + blur_amount * 0.42)
                    rgb = cv2.addWeighted(rgb, 1.0 - alpha, softened, alpha, 0)
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
    prerender_cache_hit = False
    if node_item_chain is not None:
        source_for_cache = clip_sp if clip_sp is not None else getattr(track, "source_path", None)
        stabilizer_active = _stab_params is not None and not _stab_params.is_identity()
        frame_blend_active = (
            active_seg is not None
            and getattr(active_seg, "frame_blend", False)
            and active_seg.speed < 1.0
        )
        color_grade_in_chain = any(
            (getattr(node_item, "color_grade", None) is not None)
            and not getattr(node_item, "color_grade").is_identity()
            for node_item, _masks in node_item_chain
        )
        if (
            not frame_blend_active
            and not stabilizer_active
            and not color_grade_in_chain
            and zactor is None
            and source_for_cache is not None
        ):
            cached_rgb = self._preview_prerender_cache_get(
                track.id, source_for_cache, frame_idx
            )
            if cached_rgb is not None and cached_rgb.shape == rgb.shape:
                rgb = cached_rgb.copy()
                prerender_cache_hit = True

    if prerender_cache_hit:
        chain = []
        mask_chain = []
    elif node_item_chain is not None:
        compare_rgb = _apply_node_chain_preview_compare(
            rgb,
            node_item_chain,
            frame_idx,
            getattr(track, "preview_color_compare_mode", ""),
        )
        if compare_rgb is not None:
            rgb = compare_rgb
            chain = []
            mask_chain = []
        else:
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
                        _has_workflow = bool(getattr(_g, "color_workflow", None))
                        _has_hue = any(abs(d) > 0.5 for _, d in getattr(_g, "hue_vs_hue", ()))
                        _has_lum = any(
                            getattr(_g, f"{r}_l", 0) != 0
                            for r in ("shadows", "midtones", "highlights", "offset")
                        )
                        if not _has_workflow and not _has_hue and not _has_lum:
                            _defer_grade_idx = _ci   # keep updating → last one wins

            for _ci, (node_item, masks) in enumerate(node_item_chain):
                if _ci == _defer_grade_idx:
                    last_grade = getattr(node_item, "color_grade", None)
                    continue   # shader will apply this grade
                try:
                    node_kind = getattr(node_item, "NODE_KIND", "serial")
                    with perf_span(
                        "preview.stage.node_effect",
                        detail=f"{_perf_detail} frame={frame_idx} index={_ci} kind={node_kind}",
                        threshold_ms=_perf_stage_ms,
                    ):
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
            with perf_span(
                "preview.stage.legacy_mask_grade",
                detail=f"{_perf_detail} frame={frame_idx} masks={len(masked_indices)}",
                threshold_ms=_perf_stage_ms,
            ):
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
        with perf_span(
            "preview.stage.cpu_grade_chain",
            detail=f"{_perf_detail} frame={frame_idx} grades={len(chain) - 1}",
            threshold_ms=_perf_stage_ms,
        ):
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
        has_workflow = bool(getattr(last_grade, "color_workflow", None))
        if has_workflow or has_hue or has_luma:
            with perf_span(
                "preview.stage.cpu_grade",
                detail=f"{_perf_detail} frame={frame_idx} hue_luma_workflow=1",
                threshold_ms=_perf_stage_ms,
            ):
                rgb = apply_to_rgb(rgb, last_grade)
            needs_cpu_pregrade = True
    elif len(chain) == 1:
        last_grade = chain[0]
        has_hue = any(abs(d) > 0.5 for _h, d in last_grade.hue_vs_hue)
        has_luma = any(
            getattr(last_grade, f"{r}_l", 0) != 0
            for r in ("shadows", "midtones", "highlights", "offset")
        )
        has_workflow = bool(getattr(last_grade, "color_workflow", None))
        if has_workflow or has_hue or has_luma:
            from app.color_grading import apply_to_rgb
            with perf_span(
                "preview.stage.cpu_grade",
                detail=f"{_perf_detail} frame={frame_idx} hue_luma_workflow=1",
                threshold_ms=_perf_stage_ms,
            ):
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
    # Video filters / chroma key. When both can use monitoring-resolution
    # preview, run them through one downsample/upsample pass.
    _vf = getattr(clip, "video_filters", None)
    _ck = getattr(clip, "chroma_key", None)
    _bgr = getattr(clip, "bg_removal", None)
    _batched_clip_fx = False
    _clip_fx_meta = self._clip_effects_shader_available(
        clip,
        _vf,
        _ck,
        _bgr,
        pos_ms,
        bool(getattr(locals(), 'masked_indices', None)),
    )
    if _clip_fx_meta is not None:
        with perf_span(
            "preview.stage.shader_clip_fx_state",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            _clip_fx_meta = {"clip_effects": _clip_fx_meta}

    if (_clip_fx_meta is None
            and _vf is not None and not _vf.is_identity()
            and _ck is not None and not _ck.is_identity()):
        with perf_span(
            "preview.stage.filter_chroma_batch",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            try:
                from app.preview_effects import apply_filter_chroma_preview_batch
                rgb, _, _batched_clip_fx = apply_filter_chroma_preview_batch(
                    rgb,
                    _vf,
                    _ck,
                )
            except Exception:
                _batched_clip_fx = False

    if (_clip_fx_meta is None
            and not _batched_clip_fx
            and _vf is not None and not _vf.is_identity()):
        with perf_span(
            "preview.stage.video_filters",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            apply_preview = getattr(_vf, "apply_preview", None)
            rgb = apply_preview(rgb) if callable(apply_preview) else _vf.apply(rgb)

    if (_clip_fx_meta is None
            and not _batched_clip_fx
            and _ck is not None and not _ck.is_identity()):
        with perf_span(
            "preview.stage.chroma_key",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            apply_preview = getattr(_ck, "apply_preview", None)
            rgb, _ = apply_preview(rgb) if callable(apply_preview) else _ck.apply(rgb)

    # Background removal
    if _bgr is not None and not _bgr.is_identity():
        with perf_span(
            "preview.stage.background_removal",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb = _bgr.apply(rgb)

    if getattr(locals(), 'masked_indices', None) and not chain:
        # All work done CPU-side; skip GL, go straight to QImage.
        with perf_span(
            "preview.stage.transition",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb = self._apply_transition_blend(rgb, track, clip, pos_ms, force_seek)
        # PIP overlay — composite any PIP-enabled tracks on top of the base.
        with perf_span(
            "preview.stage.pip_overlay",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb = self._render_pip_overlays(rgb, pos_ms)
        rgb, gpu_meta = self._apply_or_defer_spine_overlay(
            rgb,
            pos_ms,
            True,
            f"{_perf_detail} frame={frame_idx}",
            _perf_stage_ms,
        )
        with perf_span(
            "preview.stage.live2d_overlay",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb = self._composite_live2d_actors(rgb, pos_ms)
        with perf_span(
            "preview.stage.ar_pbr_overlay",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb, ar_gpu_meta = self._apply_or_defer_ar_pbr_overlay(rgb, pos_ms)
            gpu_meta = self._merge_gpu_meta(gpu_meta, ar_gpu_meta)
        with perf_span(
            "preview.stage.mmd_overlay",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb, mmd_gpu_meta = self._apply_or_defer_mmd_overlay(rgb, pos_ms, True)
            gpu_meta = self._merge_gpu_meta(gpu_meta, mmd_gpu_meta)
        with perf_span(
            "preview.stage.screenstudio_fx",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            try:
                from app.screenstudio_polish import apply_screenstudio_fx_rgb
                rgb = apply_screenstudio_fx_rgb(
                    rgb,
                    local_ms,
                    owner=_screenstudio_owner_for_preview(clip, track),
                    project_settings=getattr(self, "_project_settings", {}) or {},
                )
            except Exception:
                pass
        self._emit_rgb_frame(
            rgb,
            None,
            f"{_perf_detail} frame={frame_idx}",
            _perf_stage_ms,
            gpu_meta=self._merge_gpu_meta(_clip_fx_meta, gpu_meta),
            cache_key=cache_key,
        )
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
    # Composite overlays first, THEN apply color grade so that
    # Live2D / Spine actors are included in the grade.
    with perf_span(
        "preview.stage.transition",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        rgb = self._apply_transition_blend(rgb, track, clip, pos_ms, force_seek)
    with perf_span(
        "preview.stage.pip_overlay",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        rgb = self._render_pip_overlays(rgb, pos_ms)
    rgb, gpu_meta = self._apply_or_defer_spine_overlay(
        rgb,
        pos_ms,
        True,
        f"{_perf_detail} frame={frame_idx}",
        _perf_stage_ms,
    )
    with perf_span(
        "preview.stage.live2d_overlay",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        rgb = self._composite_live2d_actors(rgb, pos_ms)
    with perf_span(
        "preview.stage.ar_pbr_overlay",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        rgb, ar_gpu_meta = self._apply_or_defer_ar_pbr_overlay(rgb, pos_ms)
        gpu_meta = self._merge_gpu_meta(gpu_meta, ar_gpu_meta)
    with perf_span(
        "preview.stage.mmd_overlay",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        rgb, mmd_gpu_meta = self._apply_or_defer_mmd_overlay(rgb, pos_ms, True)
        gpu_meta = self._merge_gpu_meta(gpu_meta, mmd_gpu_meta)

    if (last_grade is not None
            and not last_grade.is_identity()
            and not needs_cpu_pregrade):
        from app.color_grading import apply_to_rgb
        with perf_span(
            "preview.stage.final_grade",
            detail=f"{_perf_detail} frame={frame_idx}",
            threshold_ms=_perf_stage_ms,
        ):
            rgb = apply_to_rgb(rgb, last_grade)

    with perf_span(
        "preview.stage.screenstudio_fx",
        detail=f"{_perf_detail} frame={frame_idx}",
        threshold_ms=_perf_stage_ms,
    ):
        try:
            from app.screenstudio_polish import apply_screenstudio_fx_rgb
            rgb = apply_screenstudio_fx_rgb(
                rgb,
                local_ms,
                owner=_screenstudio_owner_for_preview(clip, track),
                project_settings=getattr(self, "_project_settings", {}) or {},
            )
        except Exception:
            pass

    self._emit_rgb_frame(
        rgb,
        None,  # GL blits the already-graded/composited frame.
        f"{_perf_detail} frame={frame_idx}",
        _perf_stage_ms,
        gpu_meta=self._merge_gpu_meta(_clip_fx_meta, gpu_meta),
        cache_key=cache_key,
    )


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
