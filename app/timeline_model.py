"""Timeline data model — Phase 1.

Single source of truth for the editor's clip / track / timeline
dataclasses. The legacy ``VideoTrack`` in ``video_track_legacy.py``
held one source per track plus a ``cuts`` list and an inline
``color_grade``; this module defines the new clip-list model that
mirrors how ``AudioTrack`` already works:

    Timeline
    ├── video_tracks: list[VideoTrack]
    │   └── clips: list[VideoClip]   ← multiple clips per lane
    └── audio_tracks: list[AudioTrack]    (re-exported from audio_tracks)

``VideoClip`` carries its own ``timeline_in_ms`` plus ``source_in_ms``
/ ``source_out_ms`` window into the underlying file, so split / trim /
move all reduce to plain field updates without dragging a global
``cuts`` list along. The per-clip ``node_graph`` is a thin stub for
Phase 2 — for now it just wraps a ``ColorGrade`` so existing callers
keep working.

The legacy renderer still uses ``video_track_legacy.VideoTrack``;
this module exists alongside it. ``migrate_legacy_video_track`` builds
a new-style ``VideoTrack`` from a legacy one. Phase 1.5 will rewire
``TrackRow`` / ``_compose_frame_at`` to consume the new model; until
then the existing UI keeps working untouched.

Pure-Python only: no Qt imports, so this can be unit-tested headless.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Optional


# ---------------------------------------------------------------------------
#  Time-range dataclasses (extracted from video_editor_window.py)
# ---------------------------------------------------------------------------


@dataclass
class SpeedSegment:
    """A speed override on a clip's source-time range. ``speed > 1``
    plays faster (output shorter); ``speed < 1`` plays slower.

    ``frame_blend`` enables sub-frame interpolation for slow-motion
    (``speed < 1``).  ``blend_mode`` selects the algorithm:
    ``"linear"`` — simple weighted average of adjacent frames (fast,
    good for most content); ``"optical_flow"`` — motion-compensated
    warp via Farneback optical flow (smoother on motion-heavy shots,
    falls back to linear on error)."""

    start_ms: int
    end_ms: int
    speed: float
    frame_blend: bool = False
    blend_mode: str = "linear"   # "linear" | "optical_flow"
    ease_in: float = 0.0         # 0=no easing, 1=full S-curve at start
    ease_out: float = 0.0        # 0=no easing, 1=full S-curve at end

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms

    def overlaps(self, other_start: int, other_end: int) -> bool:
        return not (self.end_ms <= other_start or other_end <= self.start_ms)

    def to_dict(self) -> dict:
        return {
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
            "speed": float(self.speed),
            "frame_blend": bool(self.frame_blend),
            "blend_mode": str(self.blend_mode),
            "ease_in": float(self.ease_in),
            "ease_out": float(self.ease_out),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SpeedSegment":
        return cls(
            start_ms=int(d["start_ms"]),
            end_ms=int(d["end_ms"]),
            speed=float(d.get("speed", 1.0)),
            frame_blend=bool(d.get("frame_blend", False)),
            blend_mode=str(d.get("blend_mode", "linear")),
            ease_in=float(d.get("ease_in", 0.0)),
            ease_out=float(d.get("ease_out", 0.0)),
        )


@dataclass
class CutSegment:
    """Legacy cut-out range on a single-source ``VideoTrack``. Kept for
    migration round-trips; new code expresses cuts by splitting a
    ``VideoClip`` into two clips with a gap."""

    start_ms: int
    end_ms: int
    fade_ms: int = 0  # legacy field (no longer used by exporter)

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms


# ---------------------------------------------------------------------------
#  Speed interpolation helper
# ---------------------------------------------------------------------------


def interpolate_speed_at(track, track_local_ms: int) -> float:
    """Return the effective speed at track_local_ms, with Bezier easing
    between adjacent SpeedSegments."""
    segs = sorted(getattr(track, 'speed_segments', []), key=lambda s: s.start_ms)
    if not segs:
        return 1.0
    # Find active segment
    for i, seg in enumerate(segs):
        if seg.start_ms <= track_local_ms < seg.end_ms:
            base_speed = seg.speed
            seg_dur = max(1, seg.end_ms - seg.start_ms)
            t = (track_local_ms - seg.start_ms) / seg_dur  # 0..1

            # Ease-in: blend from previous segment's speed (or 1.0)
            if seg.ease_in > 0 and t < 0.5:
                prev_speed = segs[i-1].speed if i > 0 else 1.0
                # Cubic ease: t_in goes 0→1 over first half of ease zone
                t_in = min(1.0, t / max(0.001, seg.ease_in * 0.5))
                t_smooth = t_in * t_in * (3 - 2 * t_in)  # smoothstep
                base_speed = prev_speed + (seg.speed - prev_speed) * t_smooth

            # Ease-out: blend toward next segment's speed (or 1.0)
            if seg.ease_out > 0 and t > 0.5:
                next_speed = segs[i+1].speed if i+1 < len(segs) else 1.0
                t_out = max(0.0, (t - (1.0 - seg.ease_out * 0.5)) / max(0.001, seg.ease_out * 0.5))
                t_out = min(1.0, t_out)
                t_smooth = t_out * t_out * (3 - 2 * t_out)
                base_speed = seg.speed + (next_speed - seg.speed) * t_smooth

            return max(0.1, base_speed)
    # Before first / after last
    if track_local_ms < segs[0].start_ms:
        return 1.0
    return segs[-1].speed


@dataclass
class FadeSegment:
    """A draggable fade transition placed on the clip.

    ``kind``:
      - ``both``: fade-out during first half, fade-in during second half
      - ``in``:   fade-in (black → content) across the whole span
      - ``out``:  fade-out (content → black) across the whole span

    Width of the actor = full duration of the effect. Times are
    source-file ms (same coordinate system as the underlying video
    frames), not clip-relative — that way splitting a clip just
    filters fades by source-ms without any rebasing."""

    start_ms: int
    end_ms: int
    kind: str = "both"

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms


@dataclass
class ZoomActor:
    """A draggable zoom-in actor placed on a video clip. Times are
    clip-local source-ms. ``target_*`` is in source-pixel coords;
    ``target_w == 0`` means "no rectangle picked yet" (no-op)."""

    id: int
    start_ms: int
    end_ms: int
    target_x: int = 0
    target_y: int = 0
    target_w: int = 0
    target_h: int = 0
    zoom_in_ms: int = 500
    zoom_out_ms: int = 500
    easing: str = "smooth_pop"
    motion_blur: float = 0.0

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)

    def contains(self, ms: int) -> bool:
        return self.start_ms <= ms < self.end_ms

    def is_configured(self) -> bool:
        return self.target_w > 0 and self.target_h > 0


# ---------------------------------------------------------------------------
#  Zoom helpers (extracted from video_editor_window.py)
# ---------------------------------------------------------------------------


def zoom_ease_value(t: float, easing: str = "smooth_pop") -> float:
    """Return a Screen Studio-style zoom progress value.

    ``smooth_pop`` intentionally overshoots by a hair during the ramp, which
    makes generated Auto Polish zooms feel less mechanical without changing
    the hold/end points.  Legacy callers can use ``cubic`` for the previous
    strict cubic-in-out curve.
    """
    t = max(0.0, min(1.0, t))
    easing = str(easing or "smooth_pop").strip().lower()
    if easing in {"linear", "none"}:
        return t
    if easing in {"snappy", "ease_out"}:
        return max(0.0, min(1.0, 1.0 - (1.0 - t) ** 3))
    if easing in {"cinematic", "smoother", "smootherstep"}:
        return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    if t < 0.5:
        base = 4.0 * t * t * t
    else:
        p = -2.0 * t + 2.0
        base = 1.0 - (p * p * p) / 2.0
    if easing in {"smooth_pop", "screenstudio", "pop"}:
        base += 0.018 * (math.sin(math.pi * t) ** 2)
        return max(0.0, min(1.025, base))
    return max(0.0, min(1.0, base))


def _zoom_ease(t: float) -> float:
    """Backward-compatible cubic-in-out easing 0..1."""
    return zoom_ease_value(t, "cubic")


def zoom_motion_blur_amount(actor: ZoomActor, source_ms: int) -> float:
    """Return 0..1 blur strength for zoom transition frames."""
    strength = max(0.0, min(1.0, float(getattr(actor, "motion_blur", 0.0) or 0.0)))
    if strength <= 0.0 or not actor.contains(source_ms):
        return 0.0
    span = actor.duration_ms
    if span <= 0:
        return 0.0
    ri = min(actor.zoom_in_ms, span)
    ro = min(actor.zoom_out_ms, span - ri)
    t_in = source_ms - actor.start_ms
    ramp_t = None
    if t_in < ri and ri > 0:
        ramp_t = t_in / ri
    elif t_in > span - ro and ro > 0:
        ramp_t = (span - t_in) / ro
    if ramp_t is None:
        return 0.0
    return strength * (math.sin(math.pi * max(0.0, min(1.0, ramp_t))) ** 0.7)


def zoom_window_at(
    actor: ZoomActor, source_ms: int, frame_w: int, frame_h: int,
) -> tuple[float, float, float, float] | None:
    """Compute the crop window ``(cx, cy, cw, ch)`` (top-left + size, in
    source-frame pixels) that should be cropped + scaled to fill the
    output for ``actor`` at the given ``source_ms``.

    Returns ``None`` when the actor isn't active at this time, or when
    the actor's target rectangle hasn't been picked yet."""
    if not actor.is_configured():
        return None
    if not actor.contains(source_ms):
        return None
    span = actor.duration_ms
    if span <= 0:
        return None
    ri = min(actor.zoom_in_ms, span)
    ro = min(actor.zoom_out_ms, span - ri)
    t_in = source_ms - actor.start_ms
    if t_in < ri and ri > 0:
        progress = zoom_ease_value(t_in / ri, getattr(actor, "easing", "smooth_pop"))
    elif t_in > span - ro and ro > 0:
        progress = zoom_ease_value((span - t_in) / ro, getattr(actor, "easing", "smooth_pop"))
    else:
        progress = 1.0
    tw = float(actor.target_w)
    th = float(actor.target_h)
    cw = frame_w + (tw - frame_w) * progress
    ch = frame_h + (th - frame_h) * progress
    cw = max(2.0, min(float(frame_w), cw))
    ch = max(2.0, min(float(frame_h), ch))
    target_cx = actor.target_x + tw / 2.0
    target_cy = actor.target_y + th / 2.0
    ccx = frame_w / 2.0 + (target_cx - frame_w / 2.0) * progress
    ccy = frame_h / 2.0 + (target_cy - frame_h / 2.0) * progress
    cx = ccx - cw / 2.0
    cy = ccy - ch / 2.0
    cx = max(0.0, min(float(frame_w) - cw, cx))
    cy = max(0.0, min(float(frame_h) - ch, cy))
    return cx, cy, cw, ch


def find_active_zoom(track, source_ms: int) -> ZoomActor | None:
    """Return the first zoom actor on ``track`` whose window contains
    ``source_ms``, or ``None``. Duck-typed on ``track.zoom_actors`` so
    it works with both legacy single-source ``VideoTrack`` and the new
    clip-list track (when callers pass a clip)."""
    for z in getattr(track, "zoom_actors", []):
        if z.contains(source_ms):
            return z
    return None


def _map_source_to_output_seconds(
    source_ms: int, segments: list[tuple[int, int, float]],
) -> float:
    """Convert a source-ms timestamp to output seconds, walking the
    same segment list ``build_filter_graph`` uses (cuts removed, speed
    applied). Returns -1 when ``source_ms`` falls inside a cut."""
    out_ms = 0.0
    for s_ms, e_ms, speed in segments:
        if source_ms < s_ms:
            return -1.0
        if source_ms < e_ms:
            return (out_ms + (source_ms - s_ms) / max(0.001, speed)) / 1000.0
        out_ms += (e_ms - s_ms) / max(0.001, speed)
    return out_ms / 1000.0


def build_zoom_ffmpeg_filter(
    actors: list[ZoomActor],
    segments: list[tuple[int, int, float]],
    frame_w: int,
    frame_h: int,
) -> str | None:
    """Build a single ``crop=...,scale=W:H`` ffmpeg filter expression
    that handles every supplied zoom actor with time-varying parameters.

    The crop window stays full-frame outside any actor's output-time
    window; inside, it ramps in cubic-in-out from full frame to the
    actor's target rect, holds, then ramps back out. Multiple actors
    are stacked as nested ``if(between(t, s, e), ...)`` branches.

    Returns ``None`` when the list is empty or every actor lacks a
    target rectangle (so the caller can skip insertion)."""
    if not actors or frame_w <= 0 or frame_h <= 0:
        return None

    plans: list[tuple[float, float, float, float, ZoomActor]] = []
    for a in actors:
        if not a.is_configured():
            continue
        out_start = _map_source_to_output_seconds(a.start_ms, segments)
        out_end = _map_source_to_output_seconds(a.end_ms, segments)
        if out_end <= out_start:
            continue
        span_src = max(1, a.duration_ms)
        ramp_in = (out_end - out_start) * (a.zoom_in_ms / span_src)
        ramp_out = (out_end - out_start) * (a.zoom_out_ms / span_src)
        plans.append((out_start, out_end, ramp_in, ramp_out, a))
    if not plans:
        return None

    iw = float(frame_w)
    ih = float(frame_h)

    def ease_expr(u: str, easing: str) -> str:
        kind = str(easing or "smooth_pop").strip().lower()
        if kind in {"linear", "none"}:
            return u
        if kind in {"snappy", "ease_out"}:
            return f"(1-pow(1-{u},3))"
        if kind in {"cinematic", "smoother", "smootherstep"}:
            return f"(pow({u},3)*({u}*({u}*6-15)+10))"
        cubic = (
            f"if(lt({u},0.5),"
            f"4*pow({u},3),"
            f"1-pow(-2*{u}+2,3)/2)"
        )
        if kind in {"smooth_pop", "screenstudio", "pop"}:
            return f"min(1.025,({cubic}+0.018*pow(sin(3.14159265*{u}),2)))"
        return cubic

    def progress_expr(out_start: float, out_end: float,
                      ramp_in: float, ramp_out: float, actor: ZoomActor) -> str:
        s = f"{out_start:.6f}"
        e = f"{out_end:.6f}"
        ri = max(ramp_in, 1e-6)
        ro = max(ramp_out, 1e-6)
        u_in = f"((t-{s})/{ri:.6f})"
        u_out = f"(({e}-t)/{ro:.6f})"
        easing = getattr(actor, "easing", "smooth_pop")
        return (
            f"if(lt(t,{s}),0,"
            f"if(lt(t,{s}+{ri:.6f}),{ease_expr(u_in, easing)},"
            f"if(lt(t,{e}-{ro:.6f}),1,"
            f"if(lt(t,{e}),{ease_expr(u_out, easing)},0))))"
        )

    def crop_param(component: str) -> str:
        expr = (
            "iw" if component == "cw"
            else "ih" if component == "ch"
            else "0"
        )
        for out_start, out_end, ramp_in, ramp_out, a in reversed(plans):
            p = progress_expr(out_start, out_end, ramp_in, ramp_out, a)
            tw = float(a.target_w)
            th = float(a.target_h)
            tcx = a.target_x + tw / 2.0
            tcy = a.target_y + th / 2.0
            if component == "cw":
                inner = f"({iw}+({tw}-{iw})*{p})"
            elif component == "ch":
                inner = f"({ih}+({th}-{ih})*{p})"
            elif component == "cx":
                cw = f"({iw}+({tw}-{iw})*{p})"
                ccx = f"({iw / 2.0}+({tcx}-{iw / 2.0})*{p})"
                inner = f"({ccx}-{cw}/2)"
            else:
                ch = f"({ih}+({th}-{ih})*{p})"
                ccy = f"({ih / 2.0}+({tcy}-{ih / 2.0})*{p})"
                inner = f"({ccy}-{ch}/2)"
            expr = f"if(between(t,{out_start:.6f},{out_end:.6f}),{inner},{expr})"
        return expr

    cw = crop_param("cw")
    ch = crop_param("ch")
    cx = crop_param("cx")
    cy = crop_param("cy")
    return (
        f"crop=w='{cw}':h='{ch}':x='{cx}':y='{cy}',"
        f"scale={frame_w}:{frame_h}"
    )


# ---------------------------------------------------------------------------
#  Node graph (Phase 2 stub)
# ---------------------------------------------------------------------------


@dataclass
class ColorNode:
    """A wrapper around ``ColorGrade`` so Phase 2 can replace it with
    a chain (parallel curves, LUTs, etc.) without touching the call
    sites. Today the wrapper is transparent — ``node.grade`` is the
    same instance the legacy code has been mutating directly."""

    grade: Any  # ColorGrade — typed as Any to avoid the import cycle

    def is_identity(self) -> bool:
        try:
            return self.grade.is_identity()
        except Exception:
            return False


@dataclass
class NodeGraph:
    """Per-clip effects graph. Phase 1 only owns the color node so the
    renderer has a single place to look up the grade for a clip; Phase
    2 will add effect nodes (blur, denoise, custom LUT) and a real
    DAG. Keeping the field name stable means callers won't churn."""

    color: ColorNode

    @classmethod
    def default(cls) -> "NodeGraph":
        # Lazy import — color_grading is allowed to import this module
        # in Phase 2, so we avoid a top-level cycle.
        from app.color_grading import ColorGrade
        return cls(color=ColorNode(grade=ColorGrade()))

    def is_identity(self) -> bool:
        return self.color.is_identity()


# ---------------------------------------------------------------------------
#  Video clip / track / timeline
# ---------------------------------------------------------------------------


@dataclass
class VideoClip:
    """A single video clip placed on a ``VideoTrack`` lane.

    Mirrors ``AudioClip`` so the two media types can share the same
    timeline operations:

    - ``timeline_in_ms``: where this clip begins on the project
      timeline (was ``track.offset_ms`` in the legacy model).
    - ``source_in_ms`` / ``source_out_ms``: the window into the
      underlying source file. ``source_out_ms == 0`` means "use the
      full duration after ``source_in_ms``" — same convention as
      ``AudioClip.trim_end_ms``.

    Per-clip effects (color grade, fades, zoom actors, typography)
    travel with the clip so split / trim / move operations don't have
    to re-parent globals.
    """

    id: int
    source_path: Optional[Path] = None
    source_duration_ms: int = 0          # natural duration of the file
    timeline_in_ms: int = 0              # where this clip starts on the project
    source_in_ms: int = 0                # take source[in : out]
    source_out_ms: int = 0               # 0 → use source_duration_ms
    speed_segments: list[SpeedSegment] = field(default_factory=list)
    fades: list[FadeSegment] = field(default_factory=list)
    zoom_actors: list[ZoomActor] = field(default_factory=list)
    typography_actors: list = field(default_factory=list)  # list[TextClip]
    node_graph: NodeGraph = field(default_factory=lambda: NodeGraph.default())
    thumbnails: list = field(default_factory=list)  # list[QPixmap], lazy-filled
    selection_start_ms: int = -1
    selection_end_ms: int = -1
    # Transition at the OUT end of this clip.
    # transition_out_type: "" (none), "dissolve", "fade_black", "fade_white"
    transition_out_type: str = ""
    transition_out_ms: int = 500
    transition_preset_meta: dict = field(default_factory=dict)
    # Optional clip-level filter effects (sharpen, vignette, denoise, etc.)
    video_filters: "Optional[Any]" = None  # VideoFilterParams | None
    # Optional chroma key (green/blue screen) params.
    chroma_key: "Optional[Any]" = None   # ChromaKeyParams | None
    # Optional video stabilization params.
    stabilizer: "Optional[Any]" = None   # StabilizerParams | None
    # Optional AI background removal params.
    bg_removal: "Optional[Any]" = None   # BackgroundRemovalParams | None
    # Screen Studio-style screen-recording polish. ``cursor_events`` is
    # optional capture metadata; ``screenstudio_polish`` stores generated
    # auto-zoom actor ids plus cursor/background style settings.
    cursor_events: list[dict] = field(default_factory=list)
    screenstudio_polish: dict = field(default_factory=dict)
    # Temporarily disabled clip-level FX. These preserve the exact params
    # behind an Inspector "Disable Clip FX" action without deleting the stack.
    disabled_video_filters: "Optional[Any]" = None
    disabled_chroma_key: "Optional[Any]" = None
    disabled_bg_removal: "Optional[Any]" = None
    # ID of a linked AudioClip on an audio track; when set, moving this
    # video clip also moves the linked audio clip by the same delta.
    linked_audio_id: Optional[int] = None
    # Lightweight nested/compound timeline MVP. Clips with the same
    # non-null group id select and move together while remaining as normal
    # clips for preview/export.
    compound_group_id: Optional[int] = None
    compound_group_name: str = ""
    # True nested sequence parent support. A parent clip has no direct
    # source_path; it owns child clips whose timeline_in_ms values are
    # relative to the parent clip start.
    nested_sequence_id: Optional[int] = None
    nested_sequence_name: str = ""
    nested_child_clips: list["VideoClip"] = field(default_factory=list)
    nested_child_tracks: list[list["VideoClip"]] = field(default_factory=list)
    nested_audio_tracks: list[list[Any]] = field(default_factory=list)
    nested_spine_actor_tracks: list[Any] = field(default_factory=list)
    nested_live2d_actor_tracks: list[Any] = field(default_factory=list)

    # ---- derived ----

    def nested_tracks(self) -> list[list["VideoClip"]]:
        if self.nested_child_tracks:
            return [list(track) for track in self.nested_child_tracks]
        if self.nested_child_clips:
            return [list(self.nested_child_clips)]
        return []

    @property
    def is_nested_sequence(self) -> bool:
        return bool(
            self.nested_tracks()
            or self.nested_audio_tracks
            or self.nested_spine_actor_tracks
            or self.nested_live2d_actor_tracks
        )

    @property
    def nested_duration_ms(self) -> int:
        tracks = self.nested_tracks()
        video_end = max(
            (int(c.timeline_out_ms) for track in tracks for c in track),
            default=0,
        )
        audio_end = max(
            (
                int(getattr(c, "offset_ms", 0))
                + int(getattr(c, "effective_length_ms", 0))
                for track in (self.nested_audio_tracks or [])
                for c in track
            ),
            default=0,
        )
        spine_end = max(
            (
                int(getattr(c, "end_ms", 0))
                for track in (self.nested_spine_actor_tracks or [])
                for c in getattr(track, "clips", []) or []
            ),
            default=0,
        )
        live2d_end = max(
            (
                int(getattr(c, "end_ms", 0))
                for track in (self.nested_live2d_actor_tracks or [])
                for c in getattr(track, "clips", []) or []
            ),
            default=0,
        )
        return max(video_end, audio_end, spine_end, live2d_end)

    @property
    def effective_source_out_ms(self) -> int:
        if self.is_nested_sequence:
            return self.nested_duration_ms
        if self.source_out_ms > 0:
            return min(self.source_out_ms, self.source_duration_ms)
        return self.source_duration_ms

    @property
    def effective_length_ms(self) -> int:
        """Output duration on the project timeline (ignoring speed
        segments — Phase 1 keeps the simple linear case)."""
        return max(0, self.effective_source_out_ms - self.source_in_ms)

    @property
    def timeline_out_ms(self) -> int:
        return self.timeline_in_ms + self.effective_length_ms

    @property
    def display_name(self) -> str:
        if self.is_nested_sequence:
            return self.nested_sequence_name or self.compound_group_name or "Nested sequence"
        if self.source_path is None:
            return ""
        return self.source_path.name

    def contains_timeline_ms(self, t_ms: int) -> bool:
        return self.timeline_in_ms <= t_ms < self.timeline_out_ms

    def timeline_to_source_ms(self, t_ms: int) -> int:
        """Map a project-timeline ms onto the underlying source file."""
        return self.source_in_ms + (t_ms - self.timeline_in_ms)


def expanded_timeline_clips(clips: list[VideoClip]) -> list[VideoClip]:
    """Flatten nested sequence parents into renderable child clips.

    Child clips inside a nested parent store times relative to the parent.
    This returns shallow copies with project-timeline positions so preview,
    export segment building, and decoder setup can keep using the normal
    flat clip-list contract.
    """
    out: list[VideoClip] = []
    for clip in clips or []:
        tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
        if not tracks:
            out.append(clip)
            continue
        parent_start = int(getattr(clip, "timeline_in_ms", 0) or 0)
        for child_track in tracks:
            for child in expanded_timeline_clips(child_track):
                out.append(
                    replace(
                        child,
                        timeline_in_ms=parent_start + int(child.timeline_in_ms),
                        compound_group_id=getattr(clip, "compound_group_id", None),
                        compound_group_name=getattr(clip, "compound_group_name", ""),
                    )
                )
    out.sort(key=lambda c: int(c.timeline_in_ms))
    return out


def renderable_source_clips(clips: list[VideoClip]) -> list[VideoClip]:
    """Return concrete source-backed clips reachable from nested parents."""
    out: list[VideoClip] = []
    for clip in clips or []:
        tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
        if tracks:
            for child_track in tracks:
                out.extend(renderable_source_clips(child_track))
        elif getattr(clip, "source_path", None) is not None:
            out.append(clip)
    return out


@dataclass
class VideoTrack:
    """A timeline lane holding zero or more ``VideoClip``s. Replaces
    the single-source ``VideoTrack`` in ``video_editor_window.py``
    (which is kept for now and migrated lazily — see
    ``migrate_legacy_video_track``)."""

    id: int
    locked: bool = False
    muted: bool = False
    clips: list[VideoClip] = field(default_factory=list)
    # PIP compositing — when True this track is rendered as a picture-
    # in-picture overlay on top of the track below it instead of
    # replacing the view completely.
    pip_enabled: bool = False
    pip_x: float = 0.5        # centre x, normalised 0-1 (0.5 = centre)
    pip_y: float = 0.5        # centre y, normalised 0-1 (0.5 = centre)
    pip_scale: float = 0.3    # scale factor (0.3 = 30 % of screen width)
    pip_opacity: float = 1.0  # opacity 0-1
    pip_keyframes: list = field(default_factory=list)
    # Each keyframe dict: {"ms": int, "x": float, "y": float, "scale": float, "opacity": float}
    cursor_events: list[dict] = field(default_factory=list)
    screenstudio_polish: dict = field(default_factory=dict)

    # ---- derived ----

    @property
    def is_loaded(self) -> bool:
        return any(c.source_path is not None for c in self.clips)

    @property
    def first_clip(self) -> Optional[VideoClip]:
        for c in self.clips:
            if c.source_path is not None:
                return c
        return self.clips[0] if self.clips else None

    @property
    def display_name(self) -> str:
        custom = str(getattr(self, "label", "") or getattr(self, "name", "") or "")
        if custom:
            return custom
        names = {c.source_path.stem for c in self.clips if c.source_path is not None}
        if not names:
            return ""
        if len(names) == 1:
            return next(iter(names))
        return f"{len(self.clips)} clips"

    @property
    def duration_ms(self) -> int:
        if not self.clips:
            return 0
        return max(c.timeline_out_ms for c in self.clips)

    # ---- query ----

    def clip_at(self, t_ms: int) -> Optional[VideoClip]:
        for c in self.clips:
            if c.contains_timeline_ms(t_ms):
                return c
        return None

    def clip_index(self, clip: VideoClip) -> int:
        for i, c in enumerate(self.clips):
            if c is clip:
                return i
        raise ValueError("clip not on this track")

    # ---- edit operations ----

    def split_at(self, t_ms: int) -> tuple[VideoClip, VideoClip]:
        """Cut the clip at project time ``t_ms`` into two independent
        clips. Both halves play the same source frames they did before
        the split — only the ``source_in/out`` window changes. Per-clip
        actors / fades / node_graph are deep-copied (independent edits
        afterward don't bleed across the cut). Raises ``ValueError`` if
        ``t_ms`` is not strictly inside any clip on this track."""
        clip = self.clip_at(t_ms)
        if clip is None:
            raise ValueError(f"no clip at timeline_ms={t_ms}")
        if t_ms <= clip.timeline_in_ms or t_ms >= clip.timeline_out_ms:
            raise ValueError("split point must be strictly inside the clip")
        split_source_ms = clip.timeline_to_source_ms(t_ms)
        right = _split_clip_right(clip, split_source_ms, t_ms)
        # Mutate the left half in place so the renderer / inspector
        # references stay valid.
        clip.source_out_ms = split_source_ms
        clip.fades = [f for f in clip.fades if f.start_ms < split_source_ms]
        clip.zoom_actors = [
            z for z in clip.zoom_actors if z.start_ms < split_source_ms
        ]
        clip.typography_actors = [
            a for a in clip.typography_actors
            if getattr(a, "start_ms", 0) < split_source_ms
        ]
        # Insert the new clip directly after the original.
        idx = self.clip_index(clip)
        self.clips.insert(idx + 1, right)
        return clip, right

    def trim_left(self, clip: VideoClip, delta_ms: int) -> None:
        """Move the in-point of ``clip`` later by ``delta_ms`` (positive)
        or earlier (negative). Clamped so the clip never inverts and
        never crosses ``source_in_ms == 0``."""
        new_in = max(0, clip.source_in_ms + int(delta_ms))
        new_in = min(new_in, clip.effective_source_out_ms - 1)
        actual_delta = new_in - clip.source_in_ms
        clip.source_in_ms = new_in
        # The clip's project-timeline position shifts so the right edge
        # stays put — same UX as DaVinci's ripple-disabled trim.
        clip.timeline_in_ms += actual_delta

    def trim_right(self, clip: VideoClip, delta_ms: int) -> None:
        """Move the out-point of ``clip`` later (positive) or earlier
        (negative). Clamped to ``[source_in_ms + 1, source_duration_ms]``."""
        cur_out = clip.effective_source_out_ms
        new_out = max(clip.source_in_ms + 1, cur_out + int(delta_ms))
        new_out = min(new_out, clip.source_duration_ms or new_out)
        clip.source_out_ms = new_out

    def move_clip(self, clip: VideoClip, new_timeline_in_ms: int) -> bool:
        """Move ``clip`` so it begins at ``new_timeline_in_ms`` on the
        project timeline. Rejects (returns False, leaves clip in place)
        if the target window collides with another clip on the same
        track. Returns True on success."""
        new_in = max(0, int(new_timeline_in_ms))
        new_out = new_in + clip.effective_length_ms
        for other in self.clips:
            if other is clip:
                continue
            if other.timeline_in_ms < new_out and new_in < other.timeline_out_ms:
                return False
        clip.timeline_in_ms = new_in
        # Keep clips ordered by start time so iteration is meaningful.
        self.clips.sort(key=lambda c: c.timeline_in_ms)
        return True

    def delete_clip(self, clip: VideoClip) -> None:
        idx = self.clip_index(clip)
        self.clips.pop(idx)


def _split_clip_right(
    clip: VideoClip, split_source_ms: int, split_timeline_ms: int,
) -> VideoClip:
    """Build the right-half clip produced by splitting ``clip`` at
    ``split_source_ms``. Deep-copies per-clip state so mutations on
    the right half don't leak into the left."""
    import copy as _copy
    right_fades = [
        FadeSegment(
            start_ms=f.start_ms, end_ms=f.end_ms, kind=f.kind,
        )
        for f in clip.fades
        if f.end_ms > split_source_ms
    ]
    right_zoom = [
        _copy.deepcopy(z) for z in clip.zoom_actors
        if z.end_ms > split_source_ms
    ]
    right_typo = [
        _copy.deepcopy(a) for a in clip.typography_actors
        if getattr(a, "end_ms", 0) > split_source_ms
    ]
    return VideoClip(
        id=_next_clip_id(),
        source_path=clip.source_path,
        source_duration_ms=clip.source_duration_ms,
        timeline_in_ms=split_timeline_ms,
        source_in_ms=split_source_ms,
        source_out_ms=clip.effective_source_out_ms,
        speed_segments=[
            SpeedSegment(s.start_ms, s.end_ms, s.speed)
            for s in clip.speed_segments
            if s.end_ms > split_source_ms
        ],
        fades=right_fades,
        zoom_actors=right_zoom,
        cursor_events=list(getattr(clip, "cursor_events", []) or []),
        screenstudio_polish=dict(getattr(clip, "screenstudio_polish", {}) or {}),
        typography_actors=right_typo,
        node_graph=_copy.deepcopy(clip.node_graph),
        selection_start_ms=-1,
        selection_end_ms=-1,
    )


# ---------------------------------------------------------------------------
#  Top-level Timeline + ID allocator
# ---------------------------------------------------------------------------


_clip_id_counter: int = 1_000_000


def _next_clip_id() -> int:
    """Module-local clip-id source. Starts at 1_000_000 so it can't
    collide with the legacy track-id space (0-based, monotonic)."""
    global _clip_id_counter
    _clip_id_counter += 1
    return _clip_id_counter


@dataclass
class Timeline:
    """Top-level container — one per editor window / project."""

    video_tracks: list[VideoTrack] = field(default_factory=list)
    audio_tracks: list = field(default_factory=list)  # list[AudioTrack]
    # Phase 5 stubs: subtitle / typography overlay lanes that float
    # above all video tracks. Empty for now.
    subtitle_layer: list = field(default_factory=list)
    typography_layer: list = field(default_factory=list)
    schema_version: int = 2

    @property
    def duration_ms(self) -> int:
        v = max((t.duration_ms for t in self.video_tracks), default=0)
        a = 0
        for t in self.audio_tracks:
            for c in getattr(t, "clips", []):
                a = max(a, getattr(c, "offset_ms", 0)
                          + getattr(c, "effective_length_ms", 0))
        return max(v, a)


# ---------------------------------------------------------------------------
#  Phase 1.5: gap-preserving runtime view of a legacy single-source track
# ---------------------------------------------------------------------------


def build_legacy_clips_view(track) -> list[VideoClip]:
    """Synthesise a gap-preserving clip-list view of a legacy single-
    source ``VideoTrack``.

    Splits the track's ``source_path`` window by ``cuts`` into one
    ``VideoClip`` per surviving range. Each clip's ``timeline_in_ms``
    is ``track.offset_ms + range_start`` — i.e. cut regions leave
    *empty project time* between clips, exactly mirroring the legacy
    "skip frames during cut" renderer (no ripple-delete). The
    different rule used by ``migrate_legacy_video_track`` (which packs
    clips tight) is intentional — that one is for *real project
    migration*, this one is the runtime view that has to render byte-
    equivalent to today.

    Empty when ``track`` has no source. Used by:
    - ``ProjectPlayer`` to cache per-track clip views for ``_render_frame_at``
    - ``VideoTrack.clips`` property so paintEvent / drag handlers can
      iterate clips uniformly with future real multi-clip tracks.
    """
    src = getattr(track, "source_path", None)
    duration_ms = int(getattr(track, "duration_ms", 0) or 0)
    if src is None or duration_ms <= 0:
        return []
    cuts = sorted(
        getattr(track, "cuts", []),
        key=lambda c: getattr(c, "start_ms", 0),
    )
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for cut in cuts:
        cs = max(cursor, int(getattr(cut, "start_ms", 0)))
        ce = min(duration_ms, int(getattr(cut, "end_ms", 0)))
        if cs > cursor:
            ranges.append((cursor, cs))
        cursor = max(cursor, ce)
    if cursor < duration_ms:
        ranges.append((cursor, duration_ms))
    if not ranges:
        return []
    offset_ms = int(getattr(track, "offset_ms", 0) or 0)
    track_id = int(getattr(track, "id", 0) or 0)
    return [
        VideoClip(
            id=track_id * 1000 + i,
            source_path=src,
            source_duration_ms=duration_ms,
            timeline_in_ms=offset_ms + s,
            source_in_ms=s,
            source_out_ms=e,
        )
        for i, (s, e) in enumerate(ranges)
    ]


# ---------------------------------------------------------------------------
#  Option C migration: blade-at-playhead + ripple-delete
# ---------------------------------------------------------------------------


def split_clips_at_project_ms(
    clips: list, project_ms: int,
) -> list:
    """Industry-standard blade / razor: split the clip whose project
    window contains ``project_ms`` into two contiguous clips. Returns
    a *new* sorted list — the input is left untouched.

    Splitting *at* a clip boundary is a no-op (the strict-inside
    check matches DaVinci / Premiere / FCP behaviour). Per-clip
    actors (fades / zoom / typography) are partitioned by source-ms
    so each half keeps the actors that fall inside its window —
    same logic as ``cut_clip_window``."""
    p = int(project_ms)
    out: list = []
    for clip in clips:
        ti = int(clip.timeline_in_ms)
        to = int(clip.timeline_out_ms)
        if ti < p < to:
            split_source_ms = clip.timeline_to_source_ms(p)
            cs = int(clip.source_in_ms)
            ce = int(clip.effective_source_out_ms)
            left = VideoClip(
                id=clip.id,
                source_path=clip.source_path,
                source_duration_ms=clip.source_duration_ms,
                timeline_in_ms=ti,
                source_in_ms=cs,
                source_out_ms=split_source_ms,
                speed_segments=list(clip.speed_segments),
                fades=[
                    f for f in clip.fades if f.start_ms < split_source_ms
                ],
                zoom_actors=[
                    z for z in clip.zoom_actors if z.start_ms < split_source_ms
                ],
                typography_actors=[
                    a for a in clip.typography_actors
                    if getattr(a, "start_ms", 0) < split_source_ms
                ],
                node_graph=clip.node_graph,
            )
            right = VideoClip(
                id=clip.id + 1,
                source_path=clip.source_path,
                source_duration_ms=clip.source_duration_ms,
                timeline_in_ms=p,
                source_in_ms=split_source_ms,
                source_out_ms=ce,
                speed_segments=list(clip.speed_segments),
                fades=[
                    f for f in clip.fades if f.end_ms > split_source_ms
                ],
                zoom_actors=[
                    z for z in clip.zoom_actors if z.end_ms > split_source_ms
                ],
                typography_actors=[
                    a for a in clip.typography_actors
                    if getattr(a, "end_ms", 0) > split_source_ms
                ],
                node_graph=clip.node_graph,
            )
            out.append(left)
            out.append(right)
        else:
            out.append(clip)
    out.sort(key=lambda c: c.timeline_in_ms)
    return out


def ripple_delete_clips(clips: list, target_clip_ids: set) -> list:
    """Delete every clip whose id is in ``target_clip_ids`` and
    *ripple* the rest left so the timeline stays gap-free where the
    deleted clips used to live. Returns a new sorted list.

    Targets are processed in left-to-right order — each deletion's
    gap closes before the next deletion is computed, which matches
    Premiere's "Ripple Delete" semantics for a multi-clip selection.
    """
    if not target_clip_ids:
        return list(clips)
    # Operate on a sorted copy so ripple offsets accumulate left → right.
    remaining = sorted(clips, key=lambda c: c.timeline_in_ms)
    targets = sorted(
        [c for c in remaining if c.id in target_clip_ids],
        key=lambda c: c.timeline_in_ms,
    )
    for target in targets:
        gap = int(target.effective_length_ms)
        target_in = int(target.timeline_in_ms)
        new_remaining: list = []
        for c in remaining:
            if c.id == target.id:
                continue
            if int(c.timeline_in_ms) >= target_in:
                # Shift left by the gap. ``dataclasses.replace`` keeps
                # everything else identical (id, source ranges, actors).
                import dataclasses
                new_remaining.append(
                    dataclasses.replace(
                        c, timeline_in_ms=int(c.timeline_in_ms) - gap,
                    )
                )
            else:
                new_remaining.append(c)
        remaining = new_remaining
    remaining.sort(key=lambda c: c.timeline_in_ms)
    return remaining


def detect_timeline_edge_issues(
    clips: list[VideoClip],
    *,
    frame_ms: int = 33,
) -> list[dict[str, int | str]]:
    """Return adjacent same-lane gap/overlap diagnostics.

    A one-frame positive gap or overlap is usually accidental in NLE work.  The
    helper labels those as micro issues while still reporting larger gaps and
    overlaps without assuming they should be changed.
    """
    frame_ms = max(1, int(frame_ms))
    rows: list[dict[str, int | str]] = []
    ordered = sorted(list(clips or []), key=lambda c: (int(c.timeline_in_ms), int(c.id)))
    for left, right in zip(ordered, ordered[1:]):
        left_end = int(left.timeline_out_ms)
        right_start = int(right.timeline_in_ms)
        gap = right_start - left_end
        if gap == 0:
            continue
        if gap > 0:
            rows.append({
                "kind": "micro_gap" if gap <= frame_ms else "gap",
                "left_clip_id": int(left.id),
                "right_clip_id": int(right.id),
                "start_ms": left_end,
                "end_ms": right_start,
                "duration_ms": int(gap),
                "auto_fixable": int(gap <= frame_ms),
            })
        else:
            overlap = -gap
            rows.append({
                "kind": "micro_overlap" if overlap <= frame_ms else "overlap",
                "left_clip_id": int(left.id),
                "right_clip_id": int(right.id),
                "start_ms": right_start,
                "end_ms": left_end,
                "duration_ms": int(overlap),
                "auto_fixable": int(overlap <= frame_ms),
            })
    return rows


def cleanup_timeline_micro_edges(
    clips: list[VideoClip],
    *,
    frame_ms: int = 33,
    close_gaps: bool = True,
    trim_overlaps: bool = True,
) -> tuple[list[VideoClip], list[dict[str, int | str]]]:
    """Return a cleaned clip list plus actions for one-frame edit mistakes.

    Tiny gaps ripple the right-hand clip and following clips left. Tiny overlaps
    trim the left clip's out edge. Larger edge differences are left alone so an
    intentional pause or overlap is not silently destroyed. The input list and
    clip objects are never mutated.
    """
    frame_ms = max(1, int(frame_ms))
    out = _copy_clip_list(sorted(list(clips or []), key=lambda c: (int(c.timeline_in_ms), int(c.id))))
    actions: list[dict[str, int | str]] = []
    idx = 0
    while idx < len(out) - 1:
        left = out[idx]
        right = out[idx + 1]
        left_end = int(left.timeline_out_ms)
        right_start = int(right.timeline_in_ms)
        gap = right_start - left_end
        if close_gaps and 0 < gap <= frame_ms:
            for later in out[idx + 1:]:
                later.timeline_in_ms = max(0, int(later.timeline_in_ms) - gap)
            actions.append({
                "kind": "close_micro_gap",
                "left_clip_id": int(left.id),
                "right_clip_id": int(right.id),
                "duration_ms": int(gap),
                "delta_ms": int(-gap),
            })
            idx += 1
            continue
        if trim_overlaps and -frame_ms <= gap < 0:
            overlap = -gap
            current_out = int(left.effective_source_out_ms)
            new_out = max(int(left.source_in_ms) + 1, current_out - overlap)
            actual = current_out - new_out
            if actual > 0:
                left.source_out_ms = int(new_out)
                actions.append({
                    "kind": "trim_micro_overlap",
                    "left_clip_id": int(left.id),
                    "right_clip_id": int(right.id),
                    "duration_ms": int(actual),
                    "delta_ms": int(-actual),
                })
        idx += 1
    out.sort(key=lambda c: (int(c.timeline_in_ms), int(c.id)))
    return out, actions


def slip_clip_source_window(clip: VideoClip, delta_ms: int) -> VideoClip:
    """Return a copy of ``clip`` with its source window slipped.

    Slip editing keeps the clip fixed on the project timeline while changing
    which source frames play inside that fixed window. The source window is
    clamped to the available media duration, and the input clip is not mutated.
    """
    import copy as _copy

    out = _copy.deepcopy(clip)
    if out.is_nested_sequence:
        return out
    duration = int(out.effective_length_ms)
    source_duration = int(out.source_duration_ms or out.effective_source_out_ms)
    if duration <= 0 or source_duration <= 0 or duration >= source_duration:
        return out
    max_in = max(0, source_duration - duration)
    new_in = max(0, min(max_in, int(out.source_in_ms) + int(delta_ms)))
    out.source_in_ms = new_in
    out.source_out_ms = new_in + duration
    return out


def _copy_clip_list(clips: list[VideoClip]) -> list[VideoClip]:
    import copy as _copy

    return [_copy.deepcopy(c) for c in clips]


def _find_clip_index_by_id(clips: list[VideoClip], clip_id: int) -> int:
    for idx, clip in enumerate(clips):
        if int(clip.id) == int(clip_id):
            return idx
    raise ValueError(f"clip id {clip_id} not found")


def _clamp_delta(delta_ms: int, lower: int, upper: int) -> int:
    if lower > upper:
        return 0
    return max(lower, min(upper, int(delta_ms)))


def roll_edit_adjacent(
    clips: list[VideoClip],
    left_clip_id: int,
    right_clip_id: int,
    delta_ms: int,
) -> list[VideoClip]:
    """Roll the edit point between two adjacent clips.

    The outgoing clip's out-point and incoming clip's in-point both move by
    ``delta_ms``. Overall timeline duration remains unchanged. If the requested
    delta would invert either clip or run past source bounds, it is clamped to
    the closest valid edit. The input list and clips are left untouched.
    """
    out = _copy_clip_list(clips)
    left_idx = _find_clip_index_by_id(out, left_clip_id)
    right_idx = _find_clip_index_by_id(out, right_clip_id)
    left = out[left_idx]
    right = out[right_idx]
    if int(left.timeline_out_ms) != int(right.timeline_in_ms):
        raise ValueError("roll edit requires adjacent clips with no gap")

    boundary = int(left.timeline_out_ms)
    left_out = int(left.effective_source_out_ms)
    right_in = int(right.source_in_ms)
    right_out = int(right.effective_source_out_ms)
    left_source_limit = int(left.source_duration_ms or left_out)

    lower = max(
        int(left.source_in_ms) + 1 - left_out,
        -right_in,
        int(left.timeline_in_ms) + 1 - boundary,
    )
    upper = min(
        left_source_limit - left_out,
        right_out - 1 - right_in,
        int(right.timeline_out_ms) - 1 - boundary,
    )
    applied = _clamp_delta(delta_ms, lower, upper)
    if applied == 0:
        return sorted(out, key=lambda c: int(c.timeline_in_ms))

    left.source_out_ms = left_out + applied
    right.source_in_ms = right_in + applied
    right.timeline_in_ms = int(right.timeline_in_ms) + applied
    return sorted(out, key=lambda c: int(c.timeline_in_ms))


def slide_clip_between_neighbors(
    clips: list[VideoClip],
    clip_id: int,
    delta_ms: int,
) -> list[VideoClip]:
    """Slide a clip between its adjacent neighbours.

    Slide editing moves the selected clip on the timeline while trimming the
    previous and next clips so the three-clip block keeps the same outer span.
    It is valid only for a contiguous ``prev | selected | next`` block. The
    selected clip's source window is unchanged; only its timeline position
    moves. The input list and clips are not mutated.
    """
    out = _copy_clip_list(sorted(clips, key=lambda c: int(c.timeline_in_ms)))
    idx = _find_clip_index_by_id(out, clip_id)
    if idx <= 0 or idx >= len(out) - 1:
        raise ValueError("slide edit requires previous and next clips")
    prev_clip = out[idx - 1]
    clip = out[idx]
    next_clip = out[idx + 1]
    if (
        int(prev_clip.timeline_out_ms) != int(clip.timeline_in_ms)
        or int(clip.timeline_out_ms) != int(next_clip.timeline_in_ms)
    ):
        raise ValueError("slide edit requires a contiguous three-clip block")

    prev_out = int(prev_clip.effective_source_out_ms)
    next_in = int(next_clip.source_in_ms)
    next_out = int(next_clip.effective_source_out_ms)
    prev_source_limit = int(prev_clip.source_duration_ms or prev_out)
    clip_len = int(clip.effective_length_ms)

    lower = max(
        -int(clip.timeline_in_ms),
        int(prev_clip.source_in_ms) + 1 - prev_out,
        -next_in,
        int(prev_clip.timeline_in_ms) + 1 - int(clip.timeline_in_ms),
    )
    upper = min(
        prev_source_limit - prev_out,
        next_out - 1 - next_in,
        int(next_clip.timeline_out_ms) - clip_len - 1 - int(clip.timeline_in_ms),
    )
    applied = _clamp_delta(delta_ms, lower, upper)
    if applied == 0:
        return sorted(out, key=lambda c: int(c.timeline_in_ms))

    prev_clip.source_out_ms = prev_out + applied
    clip.timeline_in_ms = int(clip.timeline_in_ms) + applied
    next_clip.source_in_ms = next_in + applied
    next_clip.timeline_in_ms = int(next_clip.timeline_in_ms) + applied
    return sorted(out, key=lambda c: int(c.timeline_in_ms))


@dataclass
class LinkedTimelineMovePlan:
    """Validated move plan for video clips plus their linked audio clips."""

    video_starts: dict[tuple[int, int], int] = field(default_factory=dict)
    audio_offsets: dict[tuple[int, int], int] = field(default_factory=dict)
    blocked_reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.blocked_reason == ""


def _blocked_linked_move(reason: str, **details: Any) -> LinkedTimelineMovePlan:
    return LinkedTimelineMovePlan(
        blocked_reason=reason,
        details={key: value for key, value in details.items() if value is not None},
    )


def _time_windows_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return not (int(a_end) <= int(b_start) or int(b_end) <= int(a_start))


def plan_linked_timeline_move(
    video_tracks: Iterable[Any],
    audio_tracks: Iterable[Any],
    selected_video_keys: Iterable[tuple[int, int]],
    delta_ms: int,
    *,
    strict_links: bool = True,
    strict_selection: bool = False,
) -> LinkedTimelineMovePlan:
    """Return a validated move plan for selected video clips and linked audio.

    ``selected_video_keys`` contains ``(video_track_id, video_clip_id)`` pairs.
    The function validates three commercial-editor invariants before the UI
    mutates anything:

    - selected video clips cannot move before project start;
    - selected video clips cannot overlap unselected clips on their own lane;
    - linked audio clips move by the same delta and cannot overlap unselected
      audio clips on their audio lane.

    The input tracks and clips are not mutated.
    """
    delta = int(delta_ms)
    if delta == 0:
        return LinkedTimelineMovePlan()

    selected = {
        (int(track_id), int(clip_id))
        for track_id, clip_id in (selected_video_keys or [])
    }
    if not selected:
        return LinkedTimelineMovePlan()

    video_lanes: dict[int, list[Any]] = {}
    selected_clips: list[tuple[int, Any]] = []
    found_selected: set[tuple[int, int]] = set()
    for track in video_tracks or []:
        try:
            track_id = int(getattr(track, "id"))
        except Exception:
            continue
        clips = list(getattr(track, "clips", []) or [])
        video_lanes[track_id] = clips
        for clip in clips:
            try:
                clip_id = int(getattr(clip, "id"))
            except Exception:
                continue
            if (track_id, clip_id) in selected:
                found_selected.add((track_id, clip_id))
                if bool(getattr(track, "locked", False)):
                    return _blocked_linked_move(
                        "locked_track",
                        kind="video",
                        track_id=track_id,
                        clip_id=clip_id,
                        delta_ms=delta,
                    )
                selected_clips.append((track_id, clip))

    if strict_selection and found_selected != selected:
        missing = sorted(selected - found_selected)
        missing_track_id = missing[0][0] if missing else None
        missing_clip_id = missing[0][1] if missing else None
        return _blocked_linked_move(
            "missing_video_clip",
            kind="video",
            track_id=missing_track_id,
            clip_id=missing_clip_id,
            missing_selection=missing,
            delta_ms=delta,
        )

    if not selected_clips:
        return LinkedTimelineMovePlan()

    audio_lanes: dict[int, list[Any]] = {}
    audio_by_id: dict[int, list[tuple[int, Any]]] = {}
    for track in audio_tracks or []:
        try:
            track_id = int(getattr(track, "id"))
        except Exception:
            continue
        clips = list(getattr(track, "clips", []) or [])
        audio_lanes[track_id] = clips
        for clip in clips:
            try:
                clip_id = int(getattr(clip, "id"))
            except Exception:
                continue
            audio_by_id.setdefault(clip_id, []).append((track_id, clip))

    plan = LinkedTimelineMovePlan()
    moved_audio: set[tuple[int, int]] = set()

    for track_id, clip in selected_clips:
        clip_id = int(getattr(clip, "id"))
        new_start = int(getattr(clip, "timeline_in_ms", 0)) + delta
        if new_start < 0:
            return _blocked_linked_move(
                "timeline_start",
                kind="video",
                track_id=track_id,
                clip_id=clip_id,
                attempted_start_ms=new_start,
                delta_ms=delta,
            )
        plan.video_starts[(track_id, clip_id)] = new_start

        linked_audio_id = getattr(clip, "linked_audio_id", None)
        if linked_audio_id is None:
            continue
        try:
            linked_audio_id = int(linked_audio_id)
        except Exception:
            if strict_links:
                return _blocked_linked_move(
                    "missing_linked_audio",
                    kind="audio",
                    video_track_id=track_id,
                    video_clip_id=clip_id,
                    linked_audio_id=str(getattr(clip, "linked_audio_id", "")),
                )
            continue
        matches = audio_by_id.get(linked_audio_id, [])
        if not matches:
            if strict_links:
                return _blocked_linked_move(
                    "missing_linked_audio",
                    kind="audio",
                    video_track_id=track_id,
                    video_clip_id=clip_id,
                    linked_audio_id=linked_audio_id,
                )
            continue
        if len(matches) > 1:
            return _blocked_linked_move(
                "duplicate_linked_audio",
                kind="audio",
                video_track_id=track_id,
                video_clip_id=clip_id,
                linked_audio_id=linked_audio_id,
                candidate_tracks=[int(tid) for tid, _clip in matches],
            )
        audio_track_id, audio_clip = matches[0]
        audio_key = (int(audio_track_id), int(linked_audio_id))
        if audio_key in moved_audio:
            return _blocked_linked_move(
                "shared_linked_audio",
                kind="audio",
                video_track_id=track_id,
                video_clip_id=clip_id,
                linked_audio_id=linked_audio_id,
                track_id=audio_track_id,
                clip_id=linked_audio_id,
            )
        moved_audio.add(audio_key)
        new_offset = int(getattr(audio_clip, "offset_ms", 0)) + delta
        if new_offset < 0:
            return _blocked_linked_move(
                "timeline_start",
                kind="audio",
                track_id=audio_track_id,
                clip_id=linked_audio_id,
                attempted_start_ms=new_offset,
                delta_ms=delta,
            )
        plan.audio_offsets[audio_key] = new_offset

    # Validate video collisions lane-by-lane. Selected clips move together, so
    # only unselected clips on the same lane can newly block the operation.
    for track_id, clips in video_lanes.items():
        selected_ids = {
            clip_id for tid, clip_id in plan.video_starts
            if int(tid) == int(track_id)
        }
        if not selected_ids:
            continue
        for clip in clips:
            clip_id = int(getattr(clip, "id", -1))
            if clip_id not in selected_ids:
                continue
            start = int(plan.video_starts[(track_id, clip_id)])
            end = start + int(getattr(clip, "effective_length_ms", 0) or 0)
            for other in clips:
                other_id = int(getattr(other, "id", -1))
                if other_id in selected_ids:
                    continue
                other_start = int(getattr(other, "timeline_in_ms", 0))
                other_end = int(getattr(other, "timeline_out_ms", other_start))
                if _time_windows_overlap(start, end, other_start, other_end):
                    return _blocked_linked_move(
                        "video_collision",
                        kind="video",
                        track_id=track_id,
                        clip_id=clip_id,
                        other_clip_id=other_id,
                        attempted_start_ms=start,
                        attempted_end_ms=end,
                        other_start_ms=other_start,
                        other_end_ms=other_end,
                        delta_ms=delta,
                    )

    # Validate linked audio collisions on each audio lane.
    for track_id, clips in audio_lanes.items():
        moved_ids = {
            clip_id for tid, clip_id in plan.audio_offsets
            if int(tid) == int(track_id)
        }
        if not moved_ids:
            continue
        for clip in clips:
            clip_id = int(getattr(clip, "id", -1))
            if clip_id not in moved_ids:
                continue
            start = int(plan.audio_offsets[(track_id, clip_id)])
            end = start + int(getattr(clip, "effective_length_ms", 0) or 0)
            for other in clips:
                other_id = int(getattr(other, "id", -1))
                if other_id in moved_ids:
                    continue
                other_start = int(getattr(other, "offset_ms", 0))
                other_end = other_start + int(getattr(other, "effective_length_ms", 0) or 0)
                if _time_windows_overlap(start, end, other_start, other_end):
                    return _blocked_linked_move(
                        "audio_collision",
                        kind="audio",
                        track_id=track_id,
                        clip_id=clip_id,
                        other_clip_id=other_id,
                        attempted_start_ms=start,
                        attempted_end_ms=end,
                        other_start_ms=other_start,
                        other_end_ms=other_end,
                        delta_ms=delta,
                    )

    plan.details.update({
        "delta_ms": delta,
        "selected_video_count": len(selected_clips),
        "linked_audio_count": len(plan.audio_offsets),
    })
    return plan


# ---------------------------------------------------------------------------
#  Phase 1.5d post-work: drag constraints (snap + collision)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DragConstraintResult:
    """Explains how a clip drag was resolved.

    ``apply_drag_constraints`` intentionally stays as the old integer-returning
    API.  The editor uses this richer result so the timeline can show why a drag
    jumped, snapped, or clamped instead of leaving the user guessing.
    """

    timeline_in_ms: int
    requested_timeline_in_ms: int
    snapped: bool = False
    snap_target_ms: Optional[int] = None
    snap_edge: str = ""
    snap_source: str = ""
    collided: bool = False
    clamped: bool = False
    clamp_target_ms: Optional[int] = None


def apply_drag_constraints_detail(
    clips: list,
    dragged_clip,
    desired_timeline_in_ms: int,
    *,
    snap_ms: int = 200,
    extra_snap_targets: list[int] | tuple[int, ...] | None = None,
) -> DragConstraintResult:
    """Detailed form of :func:`apply_drag_constraints`.

    The returned metadata is deliberately UI-neutral: no Qt objects, no pixels,
    only project-time values and reasons.  That keeps the drag policy testable
    while giving the editor enough information to paint snap/collision feedback.
    """
    requested = max(0, int(desired_timeline_in_ms))
    desired = requested
    length = int(getattr(dragged_clip, "effective_length_ms", 0) or 0)
    others = [c for c in clips if c is not dragged_clip]

    cur_in = int(getattr(dragged_clip, "timeline_in_ms", 0))
    cur_out = cur_in + length
    blocked = {cur_in, cur_out}
    edge_targets: list[tuple[int, str]] = []
    if 0 not in blocked:
        edge_targets.append((0, "project start"))
    for target in extra_snap_targets or ():
        try:
            target_ms = int(target)
        except Exception:
            continue
        if target_ms >= 0 and target_ms not in blocked:
            edge_targets.append((target_ms, "marker/playhead"))
    for o in others:
        ti = int(o.timeline_in_ms)
        to = int(o.timeline_out_ms)
        if ti not in blocked:
            edge_targets.append((ti, "clip edge"))
        if to not in blocked:
            edge_targets.append((to, "clip edge"))

    best_delta = int(snap_ms) + 1
    best_pos: int | None = None
    best_target: int | None = None
    best_edge = ""
    best_source = ""
    desired_out = desired + length
    for target_ms, source in edge_targets:
        d_in = abs(int(target_ms) - desired)
        if d_in < best_delta:
            best_delta = d_in
            best_pos = int(target_ms)
            best_target = int(target_ms)
            best_edge = "in"
            best_source = source
        d_out = abs(int(target_ms) - desired_out)
        if d_out < best_delta:
            best_delta = d_out
            best_pos = max(0, int(target_ms) - length)
            best_target = int(target_ms)
            best_edge = "out"
            best_source = source

    snapped = best_pos is not None and best_delta <= int(snap_ms)
    if snapped:
        desired = int(best_pos)

    def _collides(pos: int) -> bool:
        end = pos + length
        return any(
            not (o.timeline_out_ms <= pos or end <= o.timeline_in_ms)
            for o in others
        )

    collided = _collides(desired)
    clamped = False
    clamp_target: int | None = None
    if collided:
        candidates: list[int] = []
        for o in others:
            left = max(0, int(o.timeline_in_ms) - length)
            right = int(o.timeline_out_ms)
            for cand in (left, right):
                if not _collides(cand):
                    candidates.append(cand)
        if candidates:
            clamp_target = int(min(candidates, key=lambda c: abs(c - desired)))
            clamped = clamp_target != desired
            desired = clamp_target
        else:
            clamp_target = int(getattr(dragged_clip, "timeline_in_ms", 0))
            clamped = clamp_target != desired
            desired = clamp_target

    return DragConstraintResult(
        timeline_in_ms=max(0, int(desired)),
        requested_timeline_in_ms=requested,
        snapped=bool(snapped),
        snap_target_ms=best_target if snapped else None,
        snap_edge=best_edge if snapped else "",
        snap_source=best_source if snapped else "",
        collided=bool(collided),
        clamped=bool(clamped),
        clamp_target_ms=clamp_target,
    )


def apply_drag_constraints(
    clips: list,
    dragged_clip,
    desired_timeline_in_ms: int,
    *,
    snap_ms: int = 200,
    extra_snap_targets: list[int] | tuple[int, ...] | None = None,
) -> int:
    """Final ``timeline_in_ms`` for ``dragged_clip`` after applying:

    1. **Snap** — if ``desired_timeline_in_ms`` (or the dragged
       clip's resulting *out* edge) is within ``snap_ms`` of another
       clip's start/end, project ms 0, or an explicit external target
       such as the playhead/marker positions, snap exactly to that
       value. Snap targets are evaluated nearest-first; the closest
       wins.

    2. **Collision** — after snap, if the dragged window overlaps any
       other clip on the same track, clamp the position to the
       nearest non-overlapping spot (left or right of the obstacle,
       whichever is closer to the user's intent). If both sides have
       no room, fall back to the dragged clip's *current* position so
       the gesture becomes a no-op rather than corrupting the layout.

    The function is pure: ``clips`` and ``dragged_clip`` are not
    mutated. The caller writes the returned value to
    ``dragged_clip.timeline_in_ms`` (and its companion legacy
    ``track.offset_ms`` if it's a single-clip track).

    Why ``snap_ms`` is a default rather than pixels: keeping the
    helper Qt-free means callers translate their pixel tolerance to
    ms before invoking. The default 200 ms ≈ 8 px at the editor's
    default 40 px/sec zoom, which feels sticky-but-not-glued in
    manual testing.
    """
    return apply_drag_constraints_detail(
        clips,
        dragged_clip,
        desired_timeline_in_ms,
        snap_ms=snap_ms,
        extra_snap_targets=extra_snap_targets,
    ).timeline_in_ms


# ---------------------------------------------------------------------------
#  Migration from legacy single-source VideoTrack
# ---------------------------------------------------------------------------


def migrate_legacy_video_track(legacy) -> VideoTrack:
    """Build a new ``VideoTrack`` from a legacy
    ``video_track_legacy.VideoTrack`` (single ``source_path`` +
    ``cuts`` list).

    A legacy track with N cut segments produces (N + 1) clips spanning
    the un-cut regions; cuts that touch the start or end collapse into
    fewer clips. The legacy ``color_grade``, ``fades``, ``zoom_actors``
    and ``typography_actors`` are partitioned across the resulting
    clips by source-ms so each piece keeps the actors that fall inside
    its window.

    Pure function: ``legacy`` is read but never mutated, so callers can
    keep displaying it through Phase 1.5 while the renderer transitions.
    """
    new_track = VideoTrack(
        id=int(getattr(legacy, "id", 0)),
        clips=[],
    )
    src_path = getattr(legacy, "source_path", None)
    src_dur = int(getattr(legacy, "duration_ms", 0) or 0)
    if src_path is None or src_dur <= 0:
        # Empty track — keep the lane but with no clips.
        return new_track

    cuts = sorted(
        getattr(legacy, "cuts", []),
        key=lambda c: c.start_ms,
    )
    # Build the un-cut source-ms ranges by walking cuts in order.
    ranges: list[tuple[int, int]] = []
    cursor = 0
    for cut in cuts:
        s = max(cursor, int(cut.start_ms))
        e = min(src_dur, int(cut.end_ms))
        if s > cursor:
            ranges.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < src_dur:
        ranges.append((cursor, src_dur))
    if not ranges:
        # Track was fully cut — produce no clips, just an empty lane.
        return new_track

    legacy_offset = int(getattr(legacy, "offset_ms", 0) or 0)
    legacy_fades = list(getattr(legacy, "fades", []) or [])
    legacy_zooms = list(getattr(legacy, "zoom_actors", []) or [])
    legacy_typo = list(getattr(legacy, "typography_actors", []) or [])
    legacy_grade = getattr(legacy, "color_grade", None)

    # The legacy renderer maps source-ms → output-ms by skipping cuts,
    # so the i-th surviving range's project-time start is the sum of
    # earlier ranges' lengths plus ``legacy_offset``.
    out_cursor = legacy_offset
    for s, e in ranges:
        clip = VideoClip(
            id=_next_clip_id(),
            source_path=src_path,
            source_duration_ms=src_dur,
            timeline_in_ms=out_cursor,
            source_in_ms=s,
            source_out_ms=e,
            fades=[
                FadeSegment(
                    start_ms=f.start_ms, end_ms=f.end_ms,
                    kind=getattr(f, "kind", "both"),
                )
                for f in legacy_fades
                if f.end_ms > s and f.start_ms < e
            ],
            zoom_actors=[
                z for z in legacy_zooms
                if z.end_ms > s and z.start_ms < e
            ],
            typography_actors=[
                a for a in legacy_typo
                if getattr(a, "end_ms", 0) > s
                and getattr(a, "start_ms", 0) < e
            ],
        )
        if legacy_grade is not None:
            # Each split clip starts with its own copy of the global
            # grade so post-migration edits stay independent (matches
            # what the user expects after a real cut).
            import copy as _copy
            clip.node_graph = NodeGraph(
                color=ColorNode(grade=_copy.deepcopy(legacy_grade)),
            )
        new_track.clips.append(clip)
        out_cursor += (e - s)
    return new_track
