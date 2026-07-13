from __future__ import annotations

from pathlib import Path

import numpy as np


def _interpolate_pip_params(*args, **kwargs):
    from app.project_player import _interpolate_pip_params as _impl

    return _impl(*args, **kwargs)

def _spine_preview_use_zero_readback() -> bool:
    try:
        import os
        mode = os.environ.get("TIGERCAPTURE_SPINE_ZERO_READBACK", "1").strip().lower()
    except Exception:
        mode = "1"
    return mode not in {"0", "false", "no", "off", "disabled"}

def _spine_direct_with_live2d() -> bool:
    try:
        import os
        mode = os.environ.get("TIGERCAPTURE_SPINE_DIRECT_WITH_LIVE2D", "1").strip().lower()
    except Exception:
        mode = "1"
    return mode not in {"0", "false", "no", "off", "disabled"}

def _has_active_live2d_actors(self, pos_ms: int) -> bool:
    for actor_track in getattr(self, "_live2d_actor_tracks", []) or []:
        for clip in getattr(actor_track, "clips", []) or []:
            try:
                if int(getattr(clip, "start_ms", 0)) <= int(pos_ms) < int(getattr(clip, "end_ms", 0)):
                    return True
            except Exception:
                continue
    return False

def _spine_direct_overlay_items(
    self,
    width: int,
    height: int,
    pos_ms: int,
    animate: bool,
) -> list[dict]:
    active = self._active_spine_clips(pos_ms)
    if not active:
        return []
    render_pos_ms = self._spine_preview_cache_pos_ms_for_active(
        pos_ms,
        animate,
        active,
    )
    key = (
        int(width),
        int(height),
        int(render_pos_ms),
        bool(animate),
        tuple(self._spine_clip_signature(clip) for clip in active),
    )
    cached = self._spine_direct_state_cache.get(key)
    if cached is not None:
        self._spine_direct_state_cache.move_to_end(key)
        return cached
    items: list[dict] = []
    for clip in active:
        try:
            state_fn = getattr(clip, "preview_render_state", None)
            state = state_fn(
                int(width),
                int(height),
                int(render_pos_ms),
                animated=animate,
            ) if callable(state_fn) else None
            if state is not None:
                items.append(state)
        except Exception:
            continue
    if items:
        self._spine_direct_state_cache[key] = items
        self._spine_direct_state_cache.move_to_end(key)
        while len(self._spine_direct_state_cache) > self._spine_overlay_cache_limit:
            self._spine_direct_state_cache.popitem(last=False)
    return items

def _spine_direct_overlay_available(self, pos_ms: int) -> bool:
    return (
        self.spine_gpu_overlay_enabled()
        and self._spine_preview_use_zero_readback()
        and self._spine_preview_use_gl()
        and not self.qimage_frame_enabled()
        and (
            self._spine_direct_with_live2d()
            or not self._has_active_live2d_actors(pos_ms)
        )
    )

def _has_active_pip_overlays(self, pos_ms: int) -> bool:
    for track in getattr(self, "_tracks", []) or []:
        if not getattr(track, "pip_enabled", False):
            continue
        for clip in self._clips_view.get(getattr(track, "id", -1), ()) or ():
            try:
                if getattr(clip, "source_path", None) is not None and clip.contains_timeline_ms(pos_ms):
                    return True
            except Exception:
                continue
    return False

def _apply_or_defer_spine_overlay(
    self,
    rgb: np.ndarray,
    pos_ms: int,
    animate: bool,
    detail: str,
    threshold_ms: float,
) -> tuple[np.ndarray, dict | None]:
    from app.perf_monitor import perf_span

    if not self._spine_actor_tracks:
        return rgb, None
    if self._spine_direct_overlay_available(pos_ms):
        h, w = rgb.shape[:2]
        with perf_span(
            "preview.stage.spine_overlay_state",
            detail=detail,
            threshold_ms=threshold_ms,
        ):
            items = self._spine_direct_overlay_items(w, h, pos_ms, animate)
        if items:
            return rgb, {"spine_items": items}
    with perf_span(
        "preview.stage.spine_overlay",
        detail=detail,
        threshold_ms=threshold_ms,
    ):
        return self._composite_spine_actors(rgb, pos_ms, animate=animate), None

def _prewarm_spine_actor_renderers(self) -> None:
    if not self._spine_actor_tracks:
        return
    try:
        import os
        if os.environ.get("TIGERCAPTURE_DISABLE_SPINE_PREWARM", "").strip() in {"1", "true", "TRUE"}:
            return
    except Exception:
        pass
    warmed = 0
    for actor_track in self._spine_actor_tracks:
        for clip in getattr(actor_track, "clips", []) or []:
            try:
                if hasattr(clip, "get_renderer"):
                    clip.get_renderer()
                if hasattr(clip, "render_frame"):
                    rw, rh = self._spine_preview_render_size(1280, 720)
                    warm_pos = int(getattr(clip, "start_ms", 0)) + 1
                    clip.render_frame(
                        rw,
                        rh,
                        warm_pos,
                        animated=True,
                        fast_preview=True,
                        use_gl=self._spine_preview_use_gl(),
                    )
                    warmed += 1
            except Exception:
                pass
            if warmed >= 8:
                return

def _live2d_preview_prewarm_enabled() -> bool:
    try:
        import os

        mode = os.environ.get("TIGERCAPTURE_DISABLE_LIVE2D_PREWARM", "").strip().lower()
    except Exception:
        mode = ""
    return mode not in {"1", "true", "yes", "on", "disabled"}

def _live2d_preview_prewarm_size() -> tuple[int, int]:
    try:
        import os

        raw = os.environ.get("TIGERCAPTURE_LIVE2D_PREWARM_SIZE", "1280x720").strip().lower()
        if "x" in raw:
            w_raw, h_raw = raw.split("x", 1)
            width = max(64, min(3840, int(w_raw)))
            height = max(64, min(2160, int(h_raw)))
            return width, height
    except Exception:
        pass
    return 1280, 720

def _prewarm_live2d_actor_renderers(self) -> None:
    if not self._live2d_actor_tracks or not self._live2d_preview_prewarm_enabled():
        return
    try:
        from app.live2d.warmup import warm_live2d_runtime

        warm_live2d_runtime()
    except Exception:
        pass
    width, height = self._live2d_preview_prewarm_size()
    warmed = 0
    for actor_track in self._live2d_actor_tracks:
        for clip in getattr(actor_track, "clips", []) or []:
            if not str(getattr(clip, "model_path", "") or ""):
                continue
            try:
                start_ms = int(getattr(clip, "start_ms", 0) or 0)
                end_ms = start_ms + max(1, int(getattr(clip, "duration_ms", 1) or 1))
                warm_pos = max(start_ms, min(end_ms - 1, start_ms + 1))
                render = getattr(clip, "render_frame", None)
                if callable(render):
                    render(width, height, warm_pos)
                reset = getattr(clip, "reset", None)
                if callable(reset):
                    reset()
                warmed += 1
            except Exception:
                pass
            if warmed >= 8:
                return

def _spine_preview_render_size(width: int, height: int) -> tuple[int, int]:
    """Return the internal Spine preview render size.

    Spine software mesh rendering is the slowest preview overlay path.
    Rendering the actor layer at half resolution and upscaling it keeps
    timeline playback responsive while export keeps using the full-quality
    renderer in ``video_exporter``.
    """
    try:
        import os
        scale = float(os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_SCALE", "0.5"))
    except Exception:
        scale = 0.5
    scale = max(0.25, min(1.0, scale))
    if scale >= 0.999:
        return int(width), int(height)
    return max(1, int(width * scale)), max(1, int(height * scale))

def _spine_preview_complex_scale() -> float:
    try:
        import os
        scale = float(os.environ.get("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_SCALE", "0.25"))
    except Exception:
        scale = 0.25
    return max(0.25, min(1.0, scale))

def _spine_preview_playback_scale() -> float:
    try:
        import os
        scale = float(os.environ.get("TIGERCAPTURE_SPINE_PLAYBACK_PREVIEW_SCALE", "0.375"))
    except Exception:
        scale = 0.375
    return max(0.25, min(1.0, scale))

def _spine_preview_render_size_for_active(
    self,
    width: int,
    height: int,
    pos_ms: int,
    active: list,
    animate: bool = True,
) -> tuple[int, int]:
    base_w, base_h = self._spine_preview_render_size(width, height)
    if not active:
        return base_w, base_h
    if not animate:
        return base_w, base_h
    playback_scale = self._spine_preview_playback_scale()
    if playback_scale < 0.999:
        base_w = max(1, int(width * playback_scale))
        base_h = max(1, int(height * playback_scale))
    use_complex_scale = self._has_active_live2d_actors(pos_ms)
    if not use_complex_scale:
        threshold = self._spine_complex_preview_threshold()
        for clip in active:
            try:
                score_fn = getattr(clip, "preview_complexity_score", None)
                score = int(score_fn()) if callable(score_fn) else 0
            except Exception:
                score = 0
            if threshold > 0 and score >= threshold:
                use_complex_scale = True
                break
    if not use_complex_scale:
        return base_w, base_h
    complex_scale = self._spine_preview_complex_scale()
    try:
        import os
        base_scale = float(os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_SCALE", "0.5"))
    except Exception:
        base_scale = 0.5
    scale = min(max(0.25, min(1.0, base_scale)), complex_scale)
    return max(1, int(width * scale)), max(1, int(height * scale))

def _spine_preview_use_gl() -> bool:
    try:
        import os
        mode = os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_RENDERER", "gl").strip().lower()
    except Exception:
        mode = "gl"
    return mode not in {"cpu", "software", "0", "false"}

def _spine_preview_use_array_compositor() -> bool:
    try:
        import os
        mode = os.environ.get("TIGERCAPTURE_SPINE_ARRAY_COMPOSITOR", "").strip().lower()
    except Exception:
        mode = ""
    return mode in {"1", "true", "yes", "on"}

def _spine_preview_use_gl_compositor() -> bool:
    try:
        import os
        mode = os.environ.get("TIGERCAPTURE_SPINE_GL_COMPOSITOR", "1").strip().lower()
    except Exception:
        mode = "1"
    return mode not in {"0", "false", "no", "off", "disabled"}

def _spine_preview_base_fps() -> float:
    try:
        import os
        fps = float(os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_FPS", "24"))
    except Exception:
        fps = 24.0
    return float(fps)

def _spine_complex_preview_fps() -> float:
    try:
        import os
        fps = float(os.environ.get("TIGERCAPTURE_SPINE_COMPLEX_PREVIEW_FPS", "12"))
    except Exception:
        fps = 12.0
    return float(fps)

def _spine_complex_preview_threshold() -> int:
    try:
        import os
        return max(0, int(os.environ.get("TIGERCAPTURE_SPINE_COMPLEX_THRESHOLD", "900")))
    except Exception:
        return 900

def _spine_quantized_preview_pos_ms(pos_ms: int, animate: bool, fps: float) -> int:
    if not animate:
        return int(pos_ms)
    if fps <= 0:
        return int(pos_ms)
    fps = max(6.0, min(60.0, fps))
    step = max(1, int(round(1000.0 / fps)))
    return int(round(int(pos_ms) / step) * step)

def _spine_preview_cache_pos_ms(pos_ms: int, animate: bool) -> int:
    """Quantize animated Spine preview time so playback can reuse frames."""
    return _spine_quantized_preview_pos_ms(
        pos_ms,
        animate,
        _spine_preview_base_fps(),
    )

def _spine_preview_cache_pos_ms_for_active(
    self,
    pos_ms: int,
    animate: bool,
    active: list,
) -> int:
    fps = self._spine_preview_base_fps()
    if animate and fps > 0 and active:
        threshold = self._spine_complex_preview_threshold()
        complex_fps = self._spine_complex_preview_fps()
        if threshold > 0 and complex_fps > 0:
            for clip in active:
                try:
                    score_fn = getattr(clip, "preview_complexity_score", None)
                    score = int(score_fn()) if callable(score_fn) else 0
                except Exception:
                    score = 0
                if score >= threshold:
                    fps = min(fps, complex_fps)
                    break
    return self._spine_quantized_preview_pos_ms(pos_ms, animate, fps)

def _spine_clip_signature(clip) -> tuple:
    return (
        id(clip),
        str(getattr(clip, "skel_path", "") or ""),
        str(getattr(clip, "atlas_path", "") or ""),
        str(getattr(clip, "texture_path", "") or ""),
        str(getattr(clip, "anim_name", "") or ""),
        str(getattr(clip, "skin_name", "") or ""),
        int(getattr(clip, "start_ms", 0) or 0),
        int(getattr(clip, "duration_ms", 0) or 0),
        bool(getattr(clip, "loop", True)),
        round(float(getattr(clip, "pos_x", 0.5) or 0.5), 4),
        round(float(getattr(clip, "pos_y", 0.5) or 0.5), 4),
        round(float(getattr(clip, "scale", 1.0) or 1.0), 4),
    )

def _active_spine_clips(self, pos_ms: int) -> list:
    active: list = []
    for actor_track in self._spine_actor_tracks:
        for clip in actor_track.clips_at(pos_ms):
            active.append(clip)
    return active

def _actor_clip_prerender_cache_safe(clip) -> bool:
    """Only reuse actor prerenders when transform state matches cache defaults."""
    try:
        if abs(float(getattr(clip, "pos_x", 0.5) or 0.5) - 0.5) > 0.0001:
            return False
        if abs(float(getattr(clip, "pos_y", 0.5) or 0.5) - 0.5) > 0.0001:
            return False
        if abs(float(getattr(clip, "scale", 1.0) or 1.0) - 1.0) > 0.0001:
            return False
        if abs(float(getattr(clip, "opacity", 1.0) or 1.0) - 1.0) > 0.0001:
            return False
        for attr in ("kf_pos_x", "kf_pos_y", "kf_scale", "kf_opacity"):
            if getattr(clip, attr, None):
                return False
    except Exception:
        return False
    return True

def _cached_actor_prerender_frame(
    self,
    kind: str,
    path: str,
    clip,
    width: int,
    height: int,
    pos_ms: int,
):
    if not path or not self._actor_clip_prerender_cache_safe(clip):
        return None
    try:
        from app.actor_prerender_cache import cached_actor_preview_frame

        local_ms = max(0, int(pos_ms) - int(getattr(clip, "start_ms", 0) or 0))
        return cached_actor_preview_frame(
            kind,
            path,
            width=int(width),
            height=int(height),
            local_ms=local_ms,
            duration_ms=int(getattr(clip, "duration_ms", 1000) or 1000),
        )
    except Exception:
        return None

def _spine_overlay_gl_composited(
    self,
    active: list,
    width: int,
    height: int,
    render_width: int,
    render_height: int,
    pos_ms: int,
    animate: bool,
    output: str,
):
    if not active or not self._spine_preview_use_gl() or self._spine_gl_compositor_failed:
        return None
    if not self._spine_preview_use_gl_compositor():
        return None
    render_pos_ms = self._spine_preview_cache_pos_ms_for_active(
        pos_ms,
        animate,
        active,
    )
    output = "rgba" if output == "rgba" else "pil"
    key = (
        f"gl_batch_{output}",
        int(width),
        int(height),
        int(render_width),
        int(render_height),
        int(render_pos_ms),
        bool(animate),
        tuple(self._spine_clip_signature(clip) for clip in active),
    )
    cached = self._spine_overlay_cache.get(key)
    if cached is not None:
        self._spine_overlay_cache.move_to_end(key)
        return cached

    items: list[dict] = []
    for clip in active:
        try:
            state_fn = getattr(clip, "preview_render_state", None)
            state = state_fn(
                render_width,
                render_height,
                render_pos_ms,
                animated=animate,
            ) if callable(state_fn) else None
            if state is not None:
                items.append(state)
        except Exception:
            continue
    if not items:
        return None

    try:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None or QThread.currentThread() is not app.thread():
            return None
        if self._spine_gl_compositor is None:
            from app.spine_editor.spine_offscreen_gl_renderer import (
                SpineOverlayGLCompositor,
            )
            self._spine_gl_compositor = SpineOverlayGLCompositor()
        if output == "rgba":
            overlay = self._spine_gl_compositor.render_array(
                items,
                render_width,
                render_height,
            )
            overlay = self._resize_rgba_array(overlay, width, height)
        else:
            overlay = self._spine_gl_compositor.render(
                items,
                render_width,
                render_height,
            )
            overlay = self._resize_rgba_pil(overlay, width, height)
        if overlay is None:
            return None
        self._spine_overlay_cache[key] = overlay
        self._spine_overlay_cache.move_to_end(key)
        while len(self._spine_overlay_cache) > self._spine_overlay_cache_limit:
            self._spine_overlay_cache.popitem(last=False)
        return overlay
    except Exception:
        self._spine_gl_compositor_failed = True
        return None

def _spine_overlay_image(
    self,
    width: int,
    height: int,
    render_width: int,
    render_height: int,
    pos_ms: int,
    animate: bool,
):
    active = self._active_spine_clips(pos_ms)
    if not active:
        return None

    use_gl = self._spine_preview_use_gl()
    render_pos_ms = self._spine_preview_cache_pos_ms_for_active(
        pos_ms,
        animate,
        active,
    )
    key = (
        int(width),
        int(height),
        int(render_width),
        int(render_height),
        int(render_pos_ms),
        bool(animate),
        bool(use_gl),
        tuple(self._spine_clip_signature(clip) for clip in active),
    )
    cached = self._spine_overlay_cache.get(key)
    if cached is not None:
        self._spine_overlay_cache.move_to_end(key)
        return cached

    gl_overlay = self._spine_overlay_gl_composited(
        active,
        width,
        height,
        render_width,
        render_height,
        pos_ms,
        animate,
        "pil",
    )
    if gl_overlay is not None:
        return gl_overlay

    try:
        from PIL import Image
        overlay = Image.new("RGBA", (int(width), int(height)), (0, 0, 0, 0))
    except Exception:
        return None
    has_pixels = False
    for clip in active:
        try:
            pil_frame = self._cached_actor_prerender_frame(
                "spine",
                str(getattr(clip, "skel_path", "") or ""),
                clip,
                render_width,
                render_height,
                render_pos_ms,
            )
            if pil_frame is None:
                pil_frame = clip.render_frame(
                    render_width,
                    render_height,
                    render_pos_ms,
                    animated=animate,
                    fast_preview=True,
                    use_gl=use_gl,
                )
            if pil_frame is None:
                continue
            pil_frame = self._resize_rgba_pil(pil_frame, width, height)
            if pil_frame is None or not pil_frame.getbbox():
                continue
            overlay.alpha_composite(pil_frame)
            has_pixels = True
        except Exception:
            pass
    if not has_pixels:
        return None
    self._spine_overlay_cache[key] = overlay
    self._spine_overlay_cache.move_to_end(key)
    while len(self._spine_overlay_cache) > self._spine_overlay_cache_limit:
        self._spine_overlay_cache.popitem(last=False)
    return overlay

def _spine_overlay_rgba(
    self,
    width: int,
    height: int,
    render_width: int,
    render_height: int,
    pos_ms: int,
    animate: bool,
):
    active = self._active_spine_clips(pos_ms)
    if not active:
        return None

    use_gl = self._spine_preview_use_gl()
    render_pos_ms = self._spine_preview_cache_pos_ms_for_active(
        pos_ms,
        animate,
        active,
    )
    key = (
        "rgba",
        int(width),
        int(height),
        int(render_width),
        int(render_height),
        int(render_pos_ms),
        bool(animate),
        bool(use_gl),
        tuple(self._spine_clip_signature(clip) for clip in active),
    )
    cached = self._spine_overlay_cache.get(key)
    if cached is not None:
        self._spine_overlay_cache.move_to_end(key)
        return cached

    gl_overlay = self._spine_overlay_gl_composited(
        active,
        width,
        height,
        render_width,
        render_height,
        pos_ms,
        animate,
        "rgba",
    )
    if gl_overlay is not None:
        return gl_overlay

    overlay = None
    has_pixels = False
    for clip in active:
        try:
            cached_frame = self._cached_actor_prerender_frame(
                "spine",
                str(getattr(clip, "skel_path", "") or ""),
                clip,
                render_width,
                render_height,
                render_pos_ms,
            )
            if cached_frame is not None:
                rgba = np.asarray(cached_frame.convert("RGBA"), dtype=np.uint8).copy()
            elif hasattr(clip, "render_frame_rgba"):
                rgba = clip.render_frame_rgba(
                    render_width,
                    render_height,
                    render_pos_ms,
                    animated=animate,
                    fast_preview=True,
                    use_gl=use_gl,
                )
            else:
                pil_frame = clip.render_frame(
                    render_width,
                    render_height,
                    render_pos_ms,
                    animated=animate,
                    fast_preview=True,
                    use_gl=use_gl,
                )
                rgba = None if pil_frame is None else np.asarray(
                    pil_frame.convert("RGBA"),
                    dtype=np.uint8,
                ).copy()
            if rgba is None:
                continue
            rgba = self._resize_rgba_array(rgba, width, height)
            if rgba is None:
                continue
            if self._rgba_array_bbox(rgba) is None:
                continue
            if overlay is None:
                overlay = np.ascontiguousarray(rgba.copy())
                has_pixels = True
                continue
            has_pixels = (
                self._alpha_composite_rgba_overlay_inplace(overlay, rgba)
                or has_pixels
            )
        except Exception:
            pass
    if not has_pixels or overlay is None:
        return None
    self._spine_overlay_cache[key] = overlay
    self._spine_overlay_cache.move_to_end(key)
    while len(self._spine_overlay_cache) > self._spine_overlay_cache_limit:
        self._spine_overlay_cache.popitem(last=False)
    return overlay

def _composite_spine_actors(self, rgb: np.ndarray, pos_ms: int,
                            animate: bool = True) -> np.ndarray:
    """Alpha-composite active Spine actor clips over the RGB frame."""
    if not self._spine_actor_tracks:
        return rgb
    h, w = rgb.shape[:2]
    active = self._active_spine_clips(pos_ms)
    if not active:
        return rgb
    rw, rh = self._spine_preview_render_size_for_active(w, h, pos_ms, active, animate)
    if self._spine_preview_use_array_compositor():
        overlay = self._spine_overlay_rgba(w, h, rw, rh, pos_ms, animate)
        return self._alpha_composite_rgba_array(rgb, overlay)
    overlay = self._spine_overlay_image(w, h, rw, rh, pos_ms, animate)
    return self._alpha_composite_rgba_pil(rgb, overlay)

def _composite_live2d_actors(self, rgb: np.ndarray, pos_ms: int) -> np.ndarray:
    """Alpha-composite active Live2D actor clips over the RGB frame.

    Uses _OffscreenRenderer which maintains its own QOffscreenSurface +
    QOpenGLContext, independent from the preview GL context.  Must be
    called from the main thread (QTimer-driven _tick satisfies this).
    """
    if not self._live2d_actor_tracks:
        return rgb
    h, w = rgb.shape[:2]
    result = rgb
    for track in self._live2d_actor_tracks:
        try:
            pil_frame = None
            try:
                weighted = track.weighted_clips_at(pos_ms)
            except Exception:
                weighted = []
            if len(weighted) == 1 and float(getattr(weighted[0], "weight", 1.0)) >= 0.999:
                clip = weighted[0].clip
                pil_frame = self._cached_actor_prerender_frame(
                    "live2d",
                    str(getattr(clip, "model_path", "") or ""),
                    clip,
                    w,
                    h,
                    pos_ms,
                )
            if pil_frame is None:
                pil_frame = track.render_at(pos_ms, w, h)
            if pil_frame is None:
                continue
            result = self._alpha_composite_rgba_pil(result, pil_frame)
        except Exception as e:
            import sys
            print(f"[live2d composite] {e}", file=sys.stderr)
    return result

def _render_actor_only(self, pos_ms: int) -> None:
    """Render actor overlays onto black when no Program clip is active."""
    import numpy as _np
    from app.perf_monitor import perf_span, stage_threshold_ms

    _perf_stage_ms = stage_threshold_ms()
    _perf_detail = f"pos={pos_ms} actor_only=1"
    # Use a sensible default preview size (1280×720)
    w, h = 1280, 720
    rgb = _np.zeros((h, w, 3), dtype=_np.uint8)
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

def _render_live2d_only(self, pos_ms: int) -> None:
    """Compatibility wrapper for older call sites."""
    self._render_actor_only(pos_ms)

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
