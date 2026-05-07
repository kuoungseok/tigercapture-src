"""Timeline data model — Phase 1.

Single source of truth for the editor's clip / track / timeline
dataclasses. The legacy ``VideoTrack`` in ``video_editor_window.py``
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

The legacy renderer still uses ``video_editor_window.VideoTrack``;
this module exists alongside it. ``migrate_legacy_video_track`` builds
a new-style ``VideoTrack`` from a legacy one. Phase 1.5 will rewire
``TrackRow`` / ``_compose_frame_at`` to consume the new model; until
then the existing UI keeps working untouched.

Pure-Python only: no Qt imports, so this can be unit-tested headless.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


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


def _zoom_ease(t: float) -> float:
    """Cubic-in-out easing 0..1. Smooth at both ends, fast in the middle."""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    p = -2.0 * t + 2.0
    return 1.0 - (p * p * p) / 2.0


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
        progress = _zoom_ease(t_in / ri)
    elif t_in > span - ro and ro > 0:
        progress = _zoom_ease((span - t_in) / ro)
    else:
        progress = 1.0
    tw = float(actor.target_w)
    th = float(actor.target_h)
    cw = frame_w + (tw - frame_w) * progress
    ch = frame_h + (th - frame_h) * progress
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

    def ease_expr(u: str) -> str:
        return (
            f"if(lt({u},0.5),"
            f"4*pow({u},3),"
            f"1-pow(-2*{u}+2,3)/2)"
        )

    def progress_expr(out_start: float, out_end: float,
                      ramp_in: float, ramp_out: float) -> str:
        s = f"{out_start:.6f}"
        e = f"{out_end:.6f}"
        ri = max(ramp_in, 1e-6)
        ro = max(ramp_out, 1e-6)
        u_in = f"((t-{s})/{ri:.6f})"
        u_out = f"(({e}-t)/{ro:.6f})"
        return (
            f"if(lt(t,{s}),0,"
            f"if(lt(t,{s}+{ri:.6f}),{ease_expr(u_in)},"
            f"if(lt(t,{e}-{ro:.6f}),1,"
            f"if(lt(t,{e}),{ease_expr(u_out)},0))))"
        )

    def crop_param(component: str) -> str:
        expr = (
            "iw" if component == "cw"
            else "ih" if component == "ch"
            else "0"
        )
        for out_start, out_end, ramp_in, ramp_out, a in reversed(plans):
            p = progress_expr(out_start, out_end, ramp_in, ramp_out)
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
    # Optional clip-level filter effects (sharpen, vignette, denoise, etc.)
    video_filters: "Optional[Any]" = None  # VideoFilterParams | None
    # Optional chroma key (green/blue screen) params.
    chroma_key: "Optional[Any]" = None   # ChromaKeyParams | None
    # Optional video stabilization params.
    stabilizer: "Optional[Any]" = None   # StabilizerParams | None
    # Optional AI background removal params.
    bg_removal: "Optional[Any]" = None   # BackgroundRemovalParams | None
    # ID of a linked AudioClip on an audio track; when set, moving this
    # video clip also moves the linked audio clip by the same delta.
    linked_audio_id: Optional[int] = None

    # ---- derived ----

    @property
    def effective_source_out_ms(self) -> int:
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
        if self.source_path is None:
            return ""
        return self.source_path.name

    def contains_timeline_ms(self, t_ms: int) -> bool:
        return self.timeline_in_ms <= t_ms < self.timeline_out_ms

    def timeline_to_source_ms(self, t_ms: int) -> int:
        """Map a project-timeline ms onto the underlying source file."""
        return self.source_in_ms + (t_ms - self.timeline_in_ms)


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


# ---------------------------------------------------------------------------
#  Phase 1.5d post-work: drag constraints (snap + collision)
# ---------------------------------------------------------------------------


def apply_drag_constraints(
    clips: list,
    dragged_clip,
    desired_timeline_in_ms: int,
    *,
    snap_ms: int = 200,
) -> int:
    """Final ``timeline_in_ms`` for ``dragged_clip`` after applying:

    1. **Snap** — if ``desired_timeline_in_ms`` (or the dragged
       clip's resulting *out* edge) is within ``snap_ms`` of another
       clip's start/end, or of project ms 0, snap exactly to that
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
    desired = max(0, int(desired_timeline_in_ms))
    length = int(getattr(dragged_clip, "effective_length_ms", 0) or 0)
    others = [c for c in clips if c is not dragged_clip]

    # 1. SNAP — collect candidate target ms for both edges of the
    # dragged clip and pick the closest one within tolerance.
    # IMPORTANT: exclude targets that match the dragged clip's
    # *current* edges. Otherwise a clip that was just split-out
    # (sharing a boundary with its neighbour) immediately snaps back
    # to that shared edge on every micro-drag, making it feel
    # immovable. Users escape this by dragging >snap_ms in one
    # gesture, but the perception of "stuck" is worse than the
    # convenience of the snap.
    cur_in = int(getattr(dragged_clip, "timeline_in_ms", 0))
    cur_out = cur_in + length
    blocked = {cur_in, cur_out}
    edge_targets: list[int] = []
    if 0 not in blocked:
        edge_targets.append(0)  # project start
    for o in others:
        ti = int(o.timeline_in_ms)
        to = int(o.timeline_out_ms)
        if ti not in blocked:
            edge_targets.append(ti)
        if to not in blocked:
            edge_targets.append(to)

    desired_out = desired + length
    best_delta = snap_ms + 1
    best_pos: int | None = None
    for t in edge_targets:
        # Snap if either edge of the dragged clip lands close to a
        # target. We try the *in* edge first (mouse follows the in
        # edge for left-anchored drags), then the *out* edge.
        d_in = abs(t - desired)
        if d_in < best_delta:
            best_delta = d_in
            best_pos = t
        d_out = abs(t - desired_out)
        if d_out < best_delta:
            best_delta = d_out
            # If the OUT edge snaps to ``t``, the IN edge moves to
            # ``t - length`` (clamped at 0).
            best_pos = max(0, t - length)
    if best_pos is not None:
        desired = best_pos
        desired_out = desired + length

    # 2. COLLISION — find any clip whose timeline window overlaps the
    # candidate position and clamp away.
    def _collides(pos: int) -> bool:
        end = pos + length
        return any(
            not (o.timeline_out_ms <= pos or end <= o.timeline_in_ms)
            for o in others
        )

    if _collides(desired):
        # Walk the obstacle list; for each overlapping clip, compute
        # the clamp positions on either side and pick the closer one
        # to ``desired``.
        candidates: list[int] = []
        for o in others:
            # Park the dragged clip flush LEFT of o (out-edge meets o.in)
            left = max(0, int(o.timeline_in_ms) - length)
            # Park flush RIGHT of o (in-edge meets o.out)
            right = int(o.timeline_out_ms)
            for cand in (left, right):
                if not _collides(cand):
                    candidates.append(cand)
        if candidates:
            # Pick the candidate closest to the user's desired position.
            desired = min(candidates, key=lambda c: abs(c - desired))
        else:
            # Nowhere fits — keep the dragged clip's current position.
            desired = int(dragged_clip.timeline_in_ms)

    return max(0, desired)


# ---------------------------------------------------------------------------
#  Migration from legacy single-source VideoTrack
# ---------------------------------------------------------------------------


def migrate_legacy_video_track(legacy) -> VideoTrack:
    """Build a new ``VideoTrack`` from a legacy
    ``video_editor_window.VideoTrack`` (single ``source_path`` +
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
