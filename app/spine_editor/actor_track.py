"""Spine actor track data model for animated 2D characters."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field

from app.spine_editor.layout import compute_spine_screen_layout


def _animated_preview_cache_limit_default() -> int:
    try:
        import os
        return max(12, min(180, int(os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_CACHE_LIMIT", "72"))))
    except Exception:
        return 72


def _should_loop_anim(name: str, duration: float) -> bool:
    if duration <= 0:
        return False
    if duration < 0.5:
        return False
    return True


@dataclass
class SpineActorClip:
    """One Spine animation clip placed on the timeline."""

    skel_path: str = ""
    atlas_path: str = ""
    texture_path: str = ""
    anim_name: str = ""
    skin_name: str = "default"
    start_ms: int = 0
    duration_ms: int = 3000
    loop: bool = True
    pos_x: float = 0.5
    pos_y: float = 0.5
    scale: float = 1.0
    _renderer: object = field(default=None, repr=False, compare=False)
    _gl_renderer: object = field(default=None, repr=False, compare=False)
    _gl_failed: bool = field(default=False, repr=False, compare=False)
    _gl_pages: list | None = field(default=None, repr=False, compare=False)
    _pma: bool = field(default=False, repr=False, compare=False)
    _preview_cache_key: tuple | None = field(default=None, repr=False, compare=False)
    _preview_cache_image: object = field(default=None, repr=False, compare=False)
    _preview_layout_key: tuple | None = field(default=None, repr=False, compare=False)
    _preview_layout: tuple[float, float, float] | None = field(default=None, repr=False, compare=False)
    _animated_preview_cache: OrderedDict = field(default_factory=OrderedDict, repr=False, compare=False)
    _animated_preview_cache_limit: int = field(default_factory=_animated_preview_cache_limit_default, repr=False, compare=False)
    _preview_complexity_key: tuple | None = field(default=None, repr=False, compare=False)
    _preview_complexity_score: int = field(default=0, repr=False, compare=False)
    _resolved_skin_key: tuple | None = field(default=None, repr=False, compare=False)
    _resolved_skin_cache: str = field(default="", repr=False, compare=False)

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def invalidate_render_cache(self) -> None:
        self._preview_cache_key = None
        self._preview_cache_image = None
        self._preview_layout_key = None
        self._preview_layout = None
        self._animated_preview_cache.clear()
        self._preview_complexity_key = None
        self._preview_complexity_score = 0
        self._resolved_skin_key = None
        self._resolved_skin_cache = ""
        self._gl_renderer = None
        self._gl_failed = False

    def _resolved_skin_name(self, renderer) -> str:
        """Return the skin to render, falling back when default is visual-empty."""
        requested = str(self.skin_name or "default")
        skeleton = getattr(renderer, "skeleton", None)
        key = (id(skeleton), requested)
        if self._resolved_skin_key == key:
            return self._resolved_skin_cache or requested

        resolved = requested
        try:
            bounds = renderer.visual_bounds(requested)
        except Exception:
            bounds = None
        if bounds is None and requested in {"", "default"}:
            best_name = requested
            best_area = 0.0
            for skin_name in sorted(getattr(skeleton, "skins", {}) or {}):
                if skin_name == "default":
                    continue
                try:
                    candidate_bounds = renderer.visual_bounds(str(skin_name))
                except Exception:
                    candidate_bounds = None
                if not candidate_bounds:
                    continue
                min_x, min_y, max_x, max_y = candidate_bounds
                area = max(0.0, float(max_x) - float(min_x)) * max(
                    0.0,
                    float(max_y) - float(min_y),
                )
                if area > best_area:
                    best_area = area
                    best_name = str(skin_name)
            if best_area > 0:
                resolved = best_name

        self._resolved_skin_key = key
        self._resolved_skin_cache = resolved
        return resolved

    def preview_complexity_score(self) -> int:
        """Return a cheap score for choosing preview cache/readback cadence."""
        renderer = self.get_renderer()
        if renderer is None:
            return 0
        skeleton = getattr(renderer, "skeleton", None)
        if skeleton is None:
            return 0
        resolved_skin = self._resolved_skin_name(renderer)
        key = (id(skeleton), resolved_skin)
        if self._preview_complexity_key == key:
            return int(self._preview_complexity_score)

        try:
            from app.spine_editor.spine_data import RegionAttachment

            merged: dict = {}
            for slot_name, atts in getattr(skeleton, "skins", {}).get("default", {}).items():
                merged[slot_name] = dict(atts)
            for slot_name, atts in getattr(skeleton, "skins", {}).get(resolved_skin, {}).items():
                merged.setdefault(slot_name, {}).update(atts)

            score = len(getattr(skeleton, "bones", []) or [])
            score += len(getattr(skeleton, "slots", []) or []) * 2
            mesh_weight_fn = getattr(renderer, "_mesh_weights_for", None)
            for slot in getattr(skeleton, "slots", []) or []:
                if not getattr(slot, "attachment", None):
                    continue
                attach = merged.get(getattr(slot, "name", ""), {}).get(slot.attachment)
                if not isinstance(attach, RegionAttachment):
                    continue
                if getattr(attach, "_non_visual", False):
                    continue
                score += 12
                triangles = getattr(attach, "mesh_triangles", None) or []
                weights = []
                if callable(mesh_weight_fn):
                    try:
                        weights = mesh_weight_fn(slot.name, slot.attachment, attach) or []
                    except Exception:
                        weights = getattr(attach, "mesh_weights", None) or []
                else:
                    weights = getattr(attach, "mesh_weights", None) or []
                score += len(triangles)
                score += len(weights) * 3
        except Exception:
            score = 0

        self._preview_complexity_key = key
        self._preview_complexity_score = int(max(0, score))
        return int(self._preview_complexity_score)

    def get_renderer(self):
        """Lazy-load and cache the Spine renderer."""
        if self._renderer is not None:
            return self._renderer
        if not self.skel_path:
            return None
        try:
            import os

            from PIL import Image

            from app.spine_editor.spine_json_parser import (
                atlas_is_pma,
                load_atlas,
                load_atlas_pages,
                load_spine_file,
            )
            from app.spine_editor.spine_renderer import SpineRenderer

            skel = load_spine_file(self.skel_path)
            atlas = {}
            textures = []
            pma = False
            if self.atlas_path:
                atlas = load_atlas(self.atlas_path)
                pma = atlas_is_pma(self.atlas_path)
                base_dir = os.path.dirname(self.atlas_path)
                for page in load_atlas_pages(self.atlas_path):
                    page_path = os.path.join(base_dir, page)
                    textures.append(
                        Image.open(page_path).convert("RGBA")
                        if os.path.exists(page_path)
                        else None
                    )
            if not textures and self.texture_path:
                textures = [Image.open(self.texture_path).convert("RGBA")]
            self._gl_pages = textures
            self._pma = pma
            self._renderer = SpineRenderer(skel, atlas, textures, pma=pma)
        except Exception:
            self._renderer = None
        return self._renderer

    def get_gl_renderer(self):
        """Lazy-load the offscreen GL renderer when it is safe to do so."""
        if self._gl_failed:
            return None
        if self._gl_renderer is not None:
            return self._gl_renderer
        renderer = self.get_renderer()
        if renderer is None:
            return None
        try:
            from PySide6.QtCore import QThread
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None or QThread.currentThread() is not app.thread():
                return None

            from app.spine_editor.spine_offscreen_gl_renderer import (
                SpineOffscreenGLRenderer,
            )

            pages = self._gl_pages if self._gl_pages is not None else renderer.textures
            self._gl_renderer = SpineOffscreenGLRenderer(
                renderer.skeleton,
                renderer.atlas,
                pages,
                pma=self._pma,
            )
            return self._gl_renderer
        except Exception:
            self._gl_failed = True
            return None

    def _preview_key(self, width: int, height: int) -> tuple:
        return (
            int(width),
            int(height),
            self.skel_path,
            self.atlas_path,
            self.texture_path,
            self.anim_name,
            self.skin_name,
            round(float(self.pos_x), 4),
            round(float(self.pos_y), 4),
            round(float(self.scale), 4),
        )

    def preview_render_state(self, width: int, height: int, pos_ms: int,
                             animated: bool = True) -> dict | None:
        """Return renderer state for batch/offscreen preview compositors."""
        renderer = self.get_renderer()
        if renderer is None:
            return None
        resolved_skin = self._resolved_skin_name(renderer)

        anim_time = (pos_ms - self.start_ms) / 1000.0 if animated else 0.0
        dur = renderer.skeleton.animations.get(self.anim_name)
        if dur and dur.duration > 0:
            if self.loop and _should_loop_anim(self.anim_name, dur.duration):
                anim_time %= dur.duration
            else:
                anim_time = min(anim_time, dur.duration)

        cache_key = self._preview_key(width, height)
        if self._preview_layout_key == cache_key and self._preview_layout is not None:
            final_scale, offset_x, offset_y = self._preview_layout
        else:
            try:
                bounds = renderer.visual_bounds(resolved_skin)
            except Exception:
                bounds = None
            final_scale, offset_x, offset_y = compute_spine_screen_layout(
                bounds,
                width,
                height,
                self.pos_x,
                self.pos_y,
                self.scale,
            )
            self._preview_layout_key = cache_key
            self._preview_layout = (final_scale, offset_x, offset_y)

        return {
            "skeleton": renderer.skeleton,
            "atlas": renderer.atlas,
            "pil_pages": self._gl_pages if self._gl_pages is not None else renderer.textures,
            "pma": bool(self._pma),
            "anim_name": self.anim_name,
            "time": max(0.0, anim_time),
            "skin_name": resolved_skin,
            "scale": final_scale,
            "offset_x": offset_x,
            "offset_y": offset_y,
        }

    def render_frame(self, width: int, height: int, pos_ms: int,
                     animated: bool = True,
                     fast_preview: bool = False,
                     use_gl: bool = True):
        """Return an RGBA PIL image of the actor at pos_ms, or None."""
        return self._render_frame_output(
            width,
            height,
            pos_ms,
            animated=animated,
            fast_preview=fast_preview,
            use_gl=use_gl,
            output="pil",
        )

    def render_frame_rgba(self, width: int, height: int, pos_ms: int,
                          animated: bool = True,
                          fast_preview: bool = False,
                          use_gl: bool = True):
        """Return a tight RGBA uint8 ndarray for preview compositing."""
        return self._render_frame_output(
            width,
            height,
            pos_ms,
            animated=animated,
            fast_preview=fast_preview,
            use_gl=use_gl,
            output="rgba",
        )

    def _render_frame_output(self, width: int, height: int, pos_ms: int,
                             animated: bool,
                             fast_preview: bool,
                             use_gl: bool,
                             output: str):
        cache_key = self._preview_key(width, height)
        output = "rgba" if output == "rgba" else "pil"
        static_cache_key = (cache_key, output)
        if not animated and self._preview_cache_key == static_cache_key:
            return self._preview_cache_image

        renderer = self.get_renderer()
        if renderer is None:
            return None
        resolved_skin = self._resolved_skin_name(renderer)
        anim_time = (pos_ms - self.start_ms) / 1000.0 if animated else 0.0
        dur = renderer.skeleton.animations.get(self.anim_name)
        if dur and dur.duration > 0:
            if self.loop and _should_loop_anim(self.anim_name, dur.duration):
                anim_time %= dur.duration
            else:
                anim_time = min(anim_time, dur.duration)
        animated_cache_key = None
        if animated and fast_preview:
            try:
                import os
                preview_fps = float(os.environ.get("TIGERCAPTURE_SPINE_PREVIEW_FPS", "24"))
            except Exception:
                preview_fps = 24.0
            if preview_fps > 0:
                preview_fps = max(6.0, min(60.0, preview_fps))
                animated_cache_key = (
                    cache_key,
                    int(round(max(0.0, anim_time) * preview_fps)),
                    bool(use_gl),
                    output,
                )
                cached = self._animated_preview_cache.get(animated_cache_key)
                if cached is not None:
                    self._animated_preview_cache.move_to_end(animated_cache_key)
                    return cached
        if self._preview_layout_key == cache_key and self._preview_layout is not None:
            final_scale, offset_x, offset_y = self._preview_layout
        else:
            try:
                bounds = renderer.visual_bounds(resolved_skin)
            except Exception:
                bounds = None
            final_scale, offset_x, offset_y = compute_spine_screen_layout(
                bounds,
                width,
                height,
                self.pos_x,
                self.pos_y,
                self.scale,
            )
            self._preview_layout_key = cache_key
            self._preview_layout = (final_scale, offset_x, offset_y)
        try:
            if use_gl:
                gl_renderer = self.get_gl_renderer()
                if gl_renderer is not None:
                    kwargs = dict(
                        width=width,
                        height=height,
                        scale=final_scale,
                        anim_name=self.anim_name,
                        time=max(0.0, anim_time),
                        skin_name=resolved_skin,
                        offset_x=offset_x,
                        offset_y=offset_y,
                    )
                    if output == "rgba" and hasattr(gl_renderer, "render_array"):
                        image = gl_renderer.render_array(**kwargs)
                    else:
                        image = gl_renderer.render(**kwargs)
                    if image is not None:
                        if output == "rgba":
                            try:
                                import numpy as np
                                if not isinstance(image, np.ndarray):
                                    image = np.asarray(
                                        image.convert("RGBA"),
                                        dtype=np.uint8,
                                    ).copy()
                            except Exception:
                                return None
                        self._preview_cache_key = static_cache_key
                        self._preview_cache_image = image
                        if animated_cache_key is not None:
                            self._animated_preview_cache[animated_cache_key] = image
                            self._animated_preview_cache.move_to_end(animated_cache_key)
                            while len(self._animated_preview_cache) > self._animated_preview_cache_limit:
                                self._animated_preview_cache.popitem(last=False)
                        return image

            old_fast = getattr(renderer, "_fast_mesh_preview", False)
            renderer._fast_mesh_preview = bool(fast_preview)
            try:
                image = renderer.render(
                    width=width,
                    height=height,
                    scale=final_scale,
                    anim_name=self.anim_name,
                    time=max(0.0, anim_time),
                    skin_name=resolved_skin,
                    offset_x=offset_x,
                    offset_y=offset_y,
                )
            finally:
                renderer._fast_mesh_preview = old_fast
            if output == "rgba" and image is not None:
                try:
                    import numpy as np
                    image = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
                except Exception:
                    return None
            self._preview_cache_key = static_cache_key
            self._preview_cache_image = image
            if animated_cache_key is not None:
                self._animated_preview_cache[animated_cache_key] = image
                self._animated_preview_cache.move_to_end(animated_cache_key)
                while len(self._animated_preview_cache) > self._animated_preview_cache_limit:
                    self._animated_preview_cache.popitem(last=False)
            return image
        except Exception:
            return None


@dataclass
class SpineActorTrack:
    """A timeline track containing Spine actor clips."""

    id: int = 0
    label: str = "Spine"
    clips: list[SpineActorClip] = field(default_factory=list)

    def clips_at(self, pos_ms: int) -> list[SpineActorClip]:
        return [c for c in self.clips if c.start_ms <= pos_ms < c.end_ms]
