"""Typography animation registry (Phase 3a — basic, whole-text only).

Each animation is a function ``(progress: float) -> TextTransform``
where ``progress`` is the normalized phase position (0.0 → 1.0). For
IN animations: progress 0 = "just appeared / pre-state", progress 1 =
"fully on screen". For OUT animations: progress 0 = "fully on screen",
progress 1 = "fully gone". HOLD is identity for now (Phase 3b adds
loop/wave variants).

Per-glyph animations (Folding category — Paper Fold, Joint Break,
Angle Break, etc.) live in a follow-up phase: they need a richer
``GlyphTransform`` model and per-character iteration. The basics here
keep the editor usable while we ship the spec piece-by-piece.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
#  Transform
# ---------------------------------------------------------------------------


@dataclass
class TextTransform:
    """A simple affine + alpha transform applied to the whole text
    block. The preview composites these by translating to the text's
    geometric center, scaling, rotating, then translating back."""

    opacity: float = 1.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    offset_x: float = 0.0          # scene pixels, post-scale
    offset_y: float = 0.0
    rotation_deg: float = 0.0

    @classmethod
    def identity(cls) -> "TextTransform":
        return cls()


@dataclass
class GlyphTransform:
    """Per-character transform used by Folding-style animations. Each
    glyph can move/scale/rotate independently around its own pivot
    (expressed as fractions of the glyph's bounding rect: 0,0 = top-
    left, 1,1 = bottom-right). The renderer applies the transform
    around (glyph_x + glyph_w*pivot_x, glyph_baseline_y - asc*pivot_y)."""

    opacity: float = 1.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    rotation_deg: float = 0.0
    pivot_x: float = 0.5            # 0=left, 1=right
    pivot_y: float = 0.5            # 0=top, 1=bottom
    color_override: str | None = None

    @classmethod
    def identity(cls) -> "GlyphTransform":
        return cls()


@dataclass
class LayerTransform:
    """One render pass for a multi-layer (whole-text) animation.

    Used by glitch / RGB-split style effects: the renderer draws the
    full text once for each layer, applying the layer's color override
    and offset. Layers are drawn back-to-front."""

    color_override: str | None = None
    opacity: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    blend_screen: bool = False      # reserved (additive blending hint)


# ---------------------------------------------------------------------------
#  Easing helpers
# ---------------------------------------------------------------------------


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * t


def _ease_out_back(t: float) -> float:
    """Slight overshoot at the end — gives the 'pop' bounce."""
    t = max(0.0, min(1.0, t))
    c1 = 1.70158
    c3 = c1 + 1
    return 1.0 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def _ease_out_bounce(t: float) -> float:
    """Multi-bounce decay landing — Robert Penner classic."""
    t = max(0.0, min(1.0, t))
    n1, d1 = 7.5625, 2.75
    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


# ---------------------------------------------------------------------------
#  Compute functions per animation
# ---------------------------------------------------------------------------

# Tunables: how far slide-ins travel (in scene pixels at 1080p reference).
_SLIDE_DISTANCE_PX = 120.0


def _none(_p: float, _k: float = 1.0) -> TextTransform:
    return TextTransform.identity()


def _fade_in(p: float, _k: float = 1.0) -> TextTransform:
    # Fade is binary — intensity doesn't really apply (it's already
    # 0..1 opacity). We keep the parameter for signature symmetry.
    return TextTransform(opacity=_ease_out_cubic(p))


def _fade_out(p: float, _k: float = 1.0) -> TextTransform:
    return TextTransform(opacity=1.0 - _ease_in_cubic(p))


def _slide_up_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    return TextTransform(opacity=e, offset_y=(1 - e) * _SLIDE_DISTANCE_PX * k)


def _slide_up_out(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    return TextTransform(opacity=1 - e, offset_y=-e * _SLIDE_DISTANCE_PX * k)


def _slide_down_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    return TextTransform(opacity=e, offset_y=-(1 - e) * _SLIDE_DISTANCE_PX * k)


def _slide_down_out(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    return TextTransform(opacity=1 - e, offset_y=e * _SLIDE_DISTANCE_PX * k)


def _slide_left_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    return TextTransform(opacity=e, offset_x=(1 - e) * _SLIDE_DISTANCE_PX * k)


def _slide_left_out(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    return TextTransform(opacity=1 - e, offset_x=-e * _SLIDE_DISTANCE_PX * k)


def _slide_right_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    return TextTransform(opacity=e, offset_x=-(1 - e) * _SLIDE_DISTANCE_PX * k)


def _slide_right_out(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    return TextTransform(opacity=1 - e, offset_x=e * _SLIDE_DISTANCE_PX * k)


def _zoom_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    # Default zooms from 0.5 to 1.0; intensity scales the deviation.
    s = 1.0 - (1.0 - 0.5) * (1.0 - e) * k
    return TextTransform(opacity=e, scale_x=s, scale_y=s)


def _zoom_out(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    s = 1.0 - 0.4 * e * k
    return TextTransform(opacity=1 - e, scale_x=s, scale_y=s)


def _pop_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_back(p)
    op = max(0.0, min(1.0, p * 3.0))
    # Blend with identity by intensity: at k=0 → no scale change,
    # at k=1 → full bouncy pop.
    s = 1.0 + (e - 1.0) * k
    return TextTransform(opacity=op, scale_x=s, scale_y=s)


def _pop_out(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    s = 1.0 + 0.25 * e * k
    return TextTransform(opacity=1 - e, scale_x=s, scale_y=s)


# ---------------------------------------------------------------------------
#  Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Animation:
    """Three render modes:

    * Whole-text (``compute_whole``): one TextTransform applied to the
      whole text block — fastest, used by the Basic category.
    * Per-glyph (``compute_perglyph``): a list of GlyphTransform, one
      per character. Used by Folding / future per-char categories.
    * Multi-layer (``compute_layers``): a list of LayerTransform; the
      renderer draws the whole text once per layer (RGB split, etc.).
    """

    id: str
    name_key: str
    direction: str               # "in" / "out" / "hold" / "any"
    category: str
    icon: str = "•"
    # Loop period in seconds — only consulted when direction == "hold".
    # The renderer maps real time to progress = (t / loop_period) % 1
    # before calling the compute fn.
    loop_period: float = 2.0
    compute_whole: Callable[[float], TextTransform] | None = None
    compute_perglyph: Callable[[float, int], list[GlyphTransform]] | None = None
    compute_layers: Callable[[float, float], list[LayerTransform]] | None = None


def _make(id: str, name_key: str, direction: str,
          fn: Callable[[float], TextTransform],
          category: str = "basic", icon: str = "•") -> Animation:
    return Animation(id=id, name_key=name_key, direction=direction,
                     category=category, icon=icon, compute_whole=fn)


def _make_glyph(id: str, name_key: str, direction: str,
                fn: Callable[[float, int], list[GlyphTransform]],
                category: str = "folding", icon: str = "▭") -> Animation:
    return Animation(id=id, name_key=name_key, direction=direction,
                     category=category, icon=icon, compute_perglyph=fn)


def _make_layers(id: str, name_key: str, direction: str,
                 fn: Callable[[float], list[LayerTransform]],
                 category: str = "utaite", icon: str = "▣") -> Animation:
    return Animation(id=id, name_key=name_key, direction=direction,
                     category=category, icon=icon, compute_layers=fn)


def _make_hold(id: str, name_key: str,
               fn: Callable[[float, float], TextTransform],
               category: str = "hold", icon: str = "∞",
               loop_period: float = 2.0) -> Animation:
    return Animation(id=id, name_key=name_key, direction="hold",
                     category=category, icon=icon,
                     loop_period=loop_period, compute_whole=fn)


def _make_hold_glyph(id: str, name_key: str,
                     fn: Callable[[float, int, float], list[GlyphTransform]],
                     category: str = "hold", icon: str = "∞",
                     loop_period: float = 2.0) -> Animation:
    return Animation(id=id, name_key=name_key, direction="hold",
                     category=category, icon=icon,
                     loop_period=loop_period, compute_perglyph=fn)


# ---------------------------------------------------------------------------
#  Folding (per-glyph) animations — spec-driven
# ---------------------------------------------------------------------------


def _stagger_progress(global_p: float, n: int, idx: int,
                      band: float = 0.5) -> float:
    """Cascading per-char progress.

    Each char has its own normalized 0→1 progress that opens earlier
    for left chars and later for right chars. ``band`` is the share
    of the global timeline taken by a single char (relative to the
    total). With band=0.5, char 0 is fully done by progress=0.5 + 0.5/n
    and char (n-1) starts at progress=(n-1)/n."""
    if n <= 0:
        return 0.0
    span = max(1e-3, 1.0 - band)
    start = idx / n * span
    p = (global_p - start) / band
    return max(0.0, min(1.0, p))


def _folding_paper_fold(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.45)
        eased = _ease_out_cubic(pi)
        out.append(GlyphTransform(
            opacity=eased,
            rotation_deg=(1.0 - eased) * -90.0 * k,
            pivot_x=0.5,
            pivot_y=1.0,
        ))
    return out


def _folding_joint_break(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    angles = [-22, 18, -10, 14, -16, 12]
    pivots = [
        (1.0, 1.0), (0.0, 1.0), (1.0, 0.0), (0.0, 0.0),
    ]
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        eased = _ease_out_cubic(pi)
        ang = angles[i % len(angles)] * k
        px, py = pivots[i % len(pivots)]
        out.append(GlyphTransform(
            opacity=eased,
            rotation_deg=(1.0 - eased) * ang,
            pivot_x=px,
            pivot_y=py,
        ))
    return out


def _folding_3d_flip(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        eased = _ease_out_cubic(pi)
        # scale_x interpolated between (1 - k) and 1 — at k=0 no flip,
        # at k=1 full edge-on → flat fade.
        sx = (1.0 - k) + k * max(0.05, eased)
        out.append(GlyphTransform(
            opacity=min(1.0, eased * 2.0),
            scale_x=sx,
            pivot_x=0.5,
            pivot_y=0.5,
        ))
    return out


def _folding_flag_wave(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    out: list[GlyphTransform] = []
    eased = _ease_out_cubic(p)
    amp = (1.0 - eased) * 24.0 * k
    base_op = min(1.0, p * 2.5)
    for i in range(n):
        phase = i * 0.55
        y = math.sin(phase + p * math.pi * 4.0) * amp
        out.append(GlyphTransform(
            opacity=base_op,
            offset_y=y,
        ))
    return out


# ---------------------------------------------------------------------------
#  Kinetic / geometric animations (whole-text and per-glyph)
# ---------------------------------------------------------------------------


def _spin_in(p: float, k: float = 1.0) -> TextTransform:
    """360° rotation while zooming from 0.3 → 1.0 scale. Whole-text."""
    e = _ease_out_cubic(p)
    op = min(1.0, p * 3.0)
    s = 1.0 - (1.0 - 0.3) * (1.0 - e) * k
    rot = (1.0 - e) * 360.0 * k
    return TextTransform(opacity=op, scale_x=s, scale_y=s, rotation_deg=rot)


def _stretch_in(p: float, k: float = 1.0) -> TextTransform:
    """Tall-squashed start → ease to natural height. Whole-text."""
    e = _ease_out_cubic(p)
    op = min(1.0, p * 2.0)
    # Start with scale_y=3.0 + scale_x=0.4 (squashed wide-bottom shape),
    # ease both back to 1.0 along the eased curve.
    sy = 1.0 + (3.0 - 1.0) * (1.0 - e) * k
    sx = 1.0 + (0.4 - 1.0) * (1.0 - e) * k
    return TextTransform(opacity=op, scale_x=sx, scale_y=sy)


def _bounce_in_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each glyph drops from above (offset_y negative-large) and lands
    with a bounce. Cascading delay so chars arrive left-to-right."""
    out: list[GlyphTransform] = []
    drop_dist = 220.0 * k
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        eased = _ease_out_bounce(pi)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 3.0),
            offset_y=-(1.0 - eased) * drop_dist,
        ))
    return out


def _spiral_in_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each glyph spirals in: starts offset radially outward + rotated,
    eases to its final position with rotation winding back to 0."""
    out: list[GlyphTransform] = []
    radius = 320.0 * k
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        eased = _ease_out_cubic(pi)
        # Radial offset shrinks to 0 as eased rises to 1.
        # Phase per glyph so each spirals in from a different direction.
        import math as _m
        phase = i * (2.0 * _m.pi / max(1, n)) + p * 1.5
        ox = _m.cos(phase) * (1.0 - eased) * radius
        oy = _m.sin(phase) * (1.0 - eased) * radius
        # Wind rotation from -540° (1.5 turns) → 0°.
        rot = (1.0 - eased) * -540.0 * k
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 2.5),
            offset_x=ox,
            offset_y=oy,
            rotation_deg=rot,
        ))
    return out


def _wave_in_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Sinusoidal IN: each glyph rides a cresting wave that flattens
    out as p reaches 1. Different from Flag Wave (which is a HOLD-style
    continuous wave) — this lands all glyphs at zero offset."""
    import math as _m
    out: list[GlyphTransform] = []
    eased = _ease_out_cubic(p)
    amp_max = 60.0 * k
    amp = (1.0 - eased) * amp_max
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        phase = i * 0.7
        y = _m.sin(phase + p * _m.pi * 3.0) * amp
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 2.5),
            offset_y=y,
        ))
    return out


# --- whole-text additions ---


def _slide_tl_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * (1 - e)
    return TextTransform(opacity=e, offset_x=-d, offset_y=-d)


def _slide_tr_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * (1 - e)
    return TextTransform(opacity=e, offset_x=d, offset_y=-d)


def _slide_bl_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * (1 - e)
    return TextTransform(opacity=e, offset_x=-d, offset_y=d)


def _slide_br_in(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_out_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * (1 - e)
    return TextTransform(opacity=e, offset_x=d, offset_y=d)


def _roll_in(p: float, k: float = 1.0) -> TextTransform:
    """Slide left + 360° rotation. 'Rolling in' from off-screen."""
    e = _ease_out_cubic(p)
    return TextTransform(
        opacity=min(1.0, p * 2.5),
        offset_x=-_SLIDE_DISTANCE_PX * k * (1 - e),
        rotation_deg=(1.0 - e) * -360.0 * k,
    )


def _pendulum_in(p: float, k: float = 1.0) -> TextTransform:
    """Damped oscillation around 0° — like a pendulum settling."""
    decay = math.exp(-2.5 * p)
    rot = -45.0 * decay * math.cos(p * math.pi * 3.0) * k
    return TextTransform(opacity=min(1.0, p * 3.0), rotation_deg=rot)


def _pulse_in(p: float, k: float = 1.0) -> TextTransform:
    """Grow into place with two scale wobbles on the way."""
    e = _ease_out_cubic(p)
    base = 0.5 + 0.5 * e
    pulse = 0.05 * math.sin(p * math.pi * 6.0) * (1.0 - e) * k
    s = base + pulse
    return TextTransform(opacity=e, scale_x=s, scale_y=s)


def _wobble_in(p: float, k: float = 1.0) -> TextTransform:
    """Damped angular oscillation — a Jell-O wobble."""
    decay = math.exp(-3.0 * p)
    rot = 15.0 * decay * math.sin(p * math.pi * 8.0) * k
    return TextTransform(opacity=min(1.0, p * 2.5), rotation_deg=rot)


def _squash_in(p: float, k: float = 1.0) -> TextTransform:
    """Quick squash (wide & short) → ease to natural shape."""
    e = _ease_out_cubic(p)
    sx = 1.0 + (1.5 - 1.0) * (1.0 - e) * k
    sy = 1.0 + (0.5 - 1.0) * (1.0 - e) * k
    return TextTransform(opacity=e, scale_x=sx, scale_y=sy)


def _drill_in(p: float, k: float = 1.0) -> TextTransform:
    """Two-turn rotation while zooming from 0.1 to 1.0."""
    e = _ease_out_cubic(p)
    s = 1.0 - (1.0 - 0.1) * (1.0 - e) * k
    rot = (1.0 - e) * -720.0 * k
    return TextTransform(opacity=min(1.0, p * 2.0),
                         scale_x=s, scale_y=s, rotation_deg=rot)


# --- whole-text OUT ---


def _slide_out_br(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * e
    return TextTransform(opacity=1.0 - e, offset_x=d, offset_y=d)


def _squash_out(p: float, k: float = 1.0) -> TextTransform:
    """Vertical collapse — text squishes flat as it fades."""
    e = _ease_in_cubic(p)
    sy = 1.0 - 0.95 * e * k
    sx = 1.0 + 0.5 * e * k
    return TextTransform(opacity=1.0 - e, scale_x=max(0.05, sx), scale_y=max(0.05, sy))


def _roll_out(p: float, k: float = 1.0) -> TextTransform:
    """Slide right + 360° rotation. Mirror of roll-in."""
    e = _ease_in_cubic(p)
    return TextTransform(
        opacity=1.0 - e,
        offset_x=_SLIDE_DISTANCE_PX * k * e,
        rotation_deg=e * 360.0 * k,
    )


# --- per-glyph additions ---


def _typewriter_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char appears with a binary opacity step at p = i/n."""
    out: list[GlyphTransform] = []
    for i in range(n):
        threshold = i / max(1, n)
        on = p >= threshold
        out.append(GlyphTransform(opacity=1.0 if on else 0.0))
    return out


def _stamp_in_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char punches in big → settles small. Cascading delay."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        e = _ease_out_back(pi)
        s = 1.0 + (2.0 - 1.0) * (1.0 - e) * k
        s = max(0.05, s)
        out.append(GlyphTransform(opacity=min(1.0, pi * 4.0),
                                   scale_x=s, scale_y=s))
    return out


def _domino_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Sequential -90° → 0° rotation, pivoting on each glyph's bottom-
    left corner. Reads like a row of falling dominoes."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.3)
        e = _ease_out_back(pi)
        rot = (1.0 - e) * -90.0 * k
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 3.0),
            rotation_deg=rot,
            pivot_x=0.0,
            pivot_y=1.0,
        ))
    return out


def _rain_in_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Drops from above with per-char pseudo-random delay (deterministic
    via index hash so the same clip always renders the same way)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = (i * 0.137) % 1.0
        pi = max(0.0, min(1.0, (p - seed * 0.6) / 0.4))
        e = _ease_out_cubic(pi)
        height = 200.0 * k
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 4.0),
            offset_y=-(1.0 - e) * height,
        ))
    return out


def _scatter_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Chars start scattered in random directions, ease into final
    position. Scatter angle is per-char deterministic."""
    out: list[GlyphTransform] = []
    e = _ease_out_cubic(p)
    spread = 220.0 * k * (1.0 - e)
    for i in range(n):
        angle = (i * 2.4 + 0.3) * math.pi
        ox = math.cos(angle) * spread
        oy = math.sin(angle) * spread
        rot = (1.0 - e) * (90.0 if i % 2 else -90.0) * k
        out.append(GlyphTransform(
            opacity=min(1.0, p * 2.5),
            offset_x=ox, offset_y=oy, rotation_deg=rot,
        ))
    return out


def _magnet_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Chars start far apart along the text axis and contract together."""
    out: list[GlyphTransform] = []
    e = _ease_out_cubic(p)
    spread = 350.0 * k * (1.0 - e)
    half = max(1.0, (n - 1) / 2.0)
    for i in range(n):
        side = (i - (n - 1) / 2.0) / half  # -1 .. 1
        out.append(GlyphTransform(
            opacity=min(1.0, p * 2.5),
            offset_x=side * spread,
        ))
    return out


def _ripple_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Sequential scale wave — each char pulses 0 → 1.4 → 1.0."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        if pi < 0.4:
            s_raw = pi / 0.4 * 1.4
        else:
            s_raw = 1.4 - (pi - 0.4) / 0.6 * 0.4
        s = 1.0 + (s_raw - 1.0) * k
        s = max(0.05, s)
        out.append(GlyphTransform(opacity=min(1.0, pi * 3.0),
                                   scale_x=s, scale_y=s))
    return out


def _cascade_slide_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char slides up into place — cascading delay across chars."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        e = _ease_out_cubic(pi)
        out.append(GlyphTransform(
            opacity=e,
            offset_y=(1.0 - e) * 60.0 * k,
        ))
    return out


def _tornado_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Chaotic spiral — each char swirls in a tight orbit while
    spinning. More chaotic than Spiral In."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.6)
        e = _ease_out_cubic(pi)
        radius = 250.0 * k * (1.0 - e)
        phase = i * 1.5 + p * 8.0
        ox = math.cos(phase) * radius
        oy = math.sin(phase) * radius
        rot = (1.0 - e) * 720.0 * k
        s = 1.0 - (1.0 - 0.4) * (1.0 - e) * k
        s = max(0.05, s)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 2.0),
            offset_x=ox, offset_y=oy, rotation_deg=rot,
            scale_x=s, scale_y=s,
        ))
    return out


def _pop_sequential_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char pops independently (with overshoot) — quick cascade."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.3)
        e = _ease_out_back(pi)
        s = 1.0 + (e - 1.0) * k
        s = max(0.05, s)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 4.0),
            scale_x=s, scale_y=s,
        ))
    return out


# --- per-glyph OUT ---


def _disintegrate_out(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char fades + flies in a per-char pseudo-random direction.
    Different from Burst Out (which is regular radial)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = (i * 0.238) % 1.0
        local_p = max(0.0, min(1.0, (p - seed * 0.4) / 0.6))
        e = _ease_in_cubic(local_p)
        angle = (i * 1.7) % (2.0 * math.pi)
        ox = math.cos(angle) * 150.0 * e * k
        oy = math.sin(angle) * 150.0 * e * k
        out.append(GlyphTransform(
            opacity=1.0 - e,
            offset_x=ox, offset_y=oy,
            rotation_deg=e * 180.0 * k,
        ))
    return out


def _burst_out_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Radial explosion OUT: glyphs fly outward from the text centre
    while fading. Pair with any IN animation."""
    import math as _m
    out: list[GlyphTransform] = []
    e = _ease_in_cubic(p)
    distance = 380.0 * e * k
    for i in range(n):
        # Direction vector — alternating slight up/down for visual
        # variation, mostly horizontal outward push.
        # The glyph layout puts char i at x = (i - n/2) * advance,
        # so a positive offset_x for right-half chars and negative
        # for left-half pushes them outward.
        side = 1 if i >= n / 2 else -1
        # Vary vertical direction by char index parity
        vy = (-1 if (i % 2 == 0) else 1)
        # Add small angular spread
        angle = _m.atan2(vy, side) + (i * 0.2 - n * 0.1) * 0.05
        ox = _m.cos(angle) * distance
        oy = _m.sin(angle) * distance
        rot = e * 90.0 * side * k
        out.append(GlyphTransform(
            opacity=1.0 - e,
            offset_x=ox,
            offset_y=oy,
            rotation_deg=rot,
        ))
    return out


# ---------------------------------------------------------------------------
#  Kinetic — additional 50 (whole-text + per-glyph + extra OUTs)
# ---------------------------------------------------------------------------

# --- whole-text path-based IN ---


def _arc_in(p: float, k: float = 1.0) -> TextTransform:
    """Parabolic arc — comes in from the left and arcs over the top."""
    e = _ease_out_cubic(p)
    dx = (1.0 - e) * -200.0 * k
    # vertical arc using sin(p*pi)
    dy = -math.sin(p * math.pi) * 120.0 * k
    return TextTransform(opacity=min(1.0, p * 2.5), offset_x=dx, offset_y=dy)


def _zigzag_in(p: float, k: float = 1.0) -> TextTransform:
    """Snake-like zigzag horizontal entry."""
    e = _ease_out_cubic(p)
    dx = (1.0 - e) * -300.0 * k
    dy = math.sin(p * math.pi * 4.0) * 30.0 * (1.0 - e) * k
    return TextTransform(opacity=min(1.0, p * 2.5), offset_x=dx, offset_y=dy)


def _scurve_in(p: float, k: float = 1.0) -> TextTransform:
    """Smooth S-curve from off-screen-left."""
    e = _ease_out_cubic(p)
    dx = (1.0 - e) * -250.0 * k
    dy = math.sin(p * math.pi * 2.0) * 50.0 * (1.0 - e) * k
    return TextTransform(opacity=min(1.0, p * 2.5), offset_x=dx, offset_y=dy)


def _catapult_in(p: float, k: float = 1.0) -> TextTransform:
    """Slingshot motion — accelerating arrival from below-far-left."""
    e = _ease_in_cubic(p) if p < 0.65 else 1.0
    dx = (1.0 - e) * -350.0 * k
    dy = (1.0 - e) * 250.0 * k
    return TextTransform(opacity=min(1.0, p * 3.0), offset_x=dx, offset_y=dy)


def _boomerang_in(p: float, k: float = 1.0) -> TextTransform:
    """Goes past the target, then comes back — overshoot from right."""
    if p < 0.6:
        # Approach + overshoot
        e = _ease_out_cubic(p / 0.6)
        dx = (1.0 - e * 1.3) * 200.0 * k
    else:
        # Settle back
        local = (p - 0.6) / 0.4
        e = _ease_out_cubic(local)
        # From -60 (overshot) to 0
        dx = (-60.0 + 60.0 * e) * k
    return TextTransform(opacity=min(1.0, p * 2.5), offset_x=dx)


def _jump_in(p: float, k: float = 1.0) -> TextTransform:
    """Arc jump with a bounce landing."""
    if p < 0.65:
        local = p / 0.65
        dy = -math.sin(local * math.pi) * 180.0 * k
        dx = (1.0 - local) * -120.0 * k
    else:
        # Bounce on landing
        local = (p - 0.65) / 0.35
        e = _ease_out_bounce(local)
        dy = -(1.0 - e) * 30.0 * k
        dx = 0.0
    return TextTransform(opacity=min(1.0, p * 3.0), offset_x=dx, offset_y=dy)


def _train_in(p: float, k: float = 1.0) -> TextTransform:
    """Slow steady horizontal entrance (constant velocity, no easing)."""
    dx = (1.0 - p) * -260.0 * k
    return TextTransform(opacity=min(1.0, p * 1.5), offset_x=dx)


def _rocket_in(p: float, k: float = 1.0) -> TextTransform:
    """Rocket trail — flies up from below at speed, decelerates."""
    e = _ease_out_cubic(p)
    dy = (1.0 - e) * 280.0 * k
    s = 1.0 - 0.3 * (1.0 - e) * k
    return TextTransform(opacity=min(1.0, p * 3.0),
                         offset_y=dy, scale_x=s, scale_y=s)


# --- whole-text rotation variants ---


def _half_spin_in(p: float, k: float = 1.0) -> TextTransform:
    """180° rotation + zoom 0.6 → 1.0."""
    e = _ease_out_cubic(p)
    s = 1.0 - 0.4 * (1.0 - e) * k
    rot = (1.0 - e) * -180.0 * k
    return TextTransform(opacity=min(1.0, p * 2.5),
                         scale_x=s, scale_y=s, rotation_deg=rot)


def _multi_spin_in(p: float, k: float = 1.0) -> TextTransform:
    """Three full turns while easing into place."""
    e = _ease_out_cubic(p)
    s = 1.0 - 0.5 * (1.0 - e) * k
    rot = (1.0 - e) * -1080.0 * k
    return TextTransform(opacity=min(1.0, p * 2.0),
                         scale_x=s, scale_y=s, rotation_deg=rot)


def _slow_rotate_in(p: float, k: float = 1.0) -> TextTransform:
    """Subtle 15° rotation easing over the full IN duration."""
    e = _ease_out_cubic(p)
    rot = (1.0 - e) * 15.0 * k
    return TextTransform(opacity=e, rotation_deg=rot)


def _tilt_in(p: float, k: float = 1.0) -> TextTransform:
    """Lands at a slight permanent tilt (3°), comes from -8°."""
    e = _ease_out_cubic(p)
    rot = (1.0 - e) * -8.0 * k + 3.0 * e * k
    return TextTransform(opacity=e, rotation_deg=rot)


def _coin_flip_in(p: float, k: float = 1.0) -> TextTransform:
    """Y-axis flip simulated as scale_x 0 → 1 (one full half-turn)."""
    e = _ease_out_cubic(p)
    sx = max(0.05, e)
    op = min(1.0, p * 2.5)
    return TextTransform(opacity=op, scale_x=(1.0 - k) + k * sx, scale_y=1.0)


# --- whole-text scale variants ---


def _zoom_huge_in(p: float, k: float = 1.0) -> TextTransform:
    """Starts 5x size, eases to 1.0 (drama entrance)."""
    e = _ease_out_cubic(p)
    s = 1.0 + (5.0 - 1.0) * (1.0 - e) * k
    return TextTransform(opacity=min(1.0, p * 2.5), scale_x=s, scale_y=s)


def _tiny_grow_in(p: float, k: float = 1.0) -> TextTransform:
    """Starts at 0.05, slowly grows."""
    e = _ease_out_cubic(p)
    s = 1.0 - (1.0 - 0.05) * (1.0 - e) * k
    return TextTransform(opacity=e, scale_x=s, scale_y=s)


def _heartbeat_in(p: float, k: float = 1.0) -> TextTransform:
    """Double-beat scale on the way in."""
    e = _ease_out_cubic(p)
    base = 0.4 + 0.6 * e
    # Two beats at 30% and 70%
    beat = 0.0
    if 0.25 < p < 0.40:
        beat = 0.15 * math.sin((p - 0.25) / 0.15 * math.pi) * k
    elif 0.55 < p < 0.70:
        beat = 0.15 * math.sin((p - 0.55) / 0.15 * math.pi) * k
    s = base + beat
    return TextTransform(opacity=e, scale_x=s, scale_y=s)


def _inflate_in(p: float, k: float = 1.0) -> TextTransform:
    """Very slow scale up, ending bigger (1.0 + 0.1k overshoot)."""
    e = _ease_out_cubic(p)
    s = 0.6 + 0.4 * e
    s = 1.0 + (s - 1.0) * k
    return TextTransform(opacity=e, scale_x=s, scale_y=s)


def _trampoline_in(p: float, k: float = 1.0) -> TextTransform:
    """Lands then bounces — overshoot scale on landing."""
    if p < 0.5:
        e = _ease_out_cubic(p / 0.5)
        s = e
    else:
        local = (p - 0.5) / 0.5
        e = _ease_out_bounce(local)
        s = 1.0 + 0.4 * (1.0 - e) * k * (1.0 if k > 0 else 0.0)
    s = max(0.05, s)
    return TextTransform(opacity=min(1.0, p * 3.0), scale_x=s, scale_y=s)


# --- whole-text effects ---


def _vibrate_in(p: float, k: float = 1.0) -> TextTransform:
    """Heavy shake settling to zero."""
    e = _ease_out_cubic(p)
    amp = (1.0 - e) * 12.0 * k
    dx = math.sin(p * math.pi * 30.0) * amp
    dy = math.cos(p * math.pi * 32.0) * amp * 0.7
    return TextTransform(opacity=min(1.0, p * 2.5), offset_x=dx, offset_y=dy)


def _earthquake_in(p: float, k: float = 1.0) -> TextTransform:
    """Lower-frequency, larger-amplitude shake."""
    e = _ease_out_cubic(p)
    amp = (1.0 - e) * 24.0 * k
    dx = math.sin(p * math.pi * 12.0) * amp
    dy = math.sin(p * math.pi * 14.0 + 1.2) * amp * 0.8
    rot = math.sin(p * math.pi * 10.0) * (1.0 - e) * 4.0 * k
    return TextTransform(opacity=min(1.0, p * 2.5),
                         offset_x=dx, offset_y=dy, rotation_deg=rot)


def _float_in(p: float, k: float = 1.0) -> TextTransform:
    """Gentle vertical bob during fade-in (HOLD-style oscillation)."""
    e = _ease_out_cubic(p)
    bob = math.sin(p * math.pi * 2.5) * 12.0 * k
    return TextTransform(opacity=e, offset_y=bob * (1.0 - e * 0.3))


def _shimmer_in(p: float, k: float = 1.0) -> TextTransform:
    """Heat-haze shimmer — small wavy horizontal jitter."""
    e = _ease_out_cubic(p)
    amp = (1.0 - e) * 6.0 * k
    dx = math.sin(p * math.pi * 18.0) * amp
    dy = math.cos(p * math.pi * 22.0) * amp * 0.5
    return TextTransform(opacity=e, offset_x=dx, offset_y=dy)


def _strobe_in(p: float, k: float = 1.0) -> TextTransform:
    """Binary on/off flicker that resolves to solid as p → 1.

    The flicker frequency tapers off so by p=1 the text is fully on.
    Conscious of the photosensitivity warning system in Phase 4b3 —
    this is mild compared to the upcoming DEVILA strobe, but still
    flashes."""
    if p > 0.75:
        op = 1.0
    else:
        # ~3 Hz flicker, modulated by k (intensity)
        flick = ((p * 12.0) % 1.0) > 0.5
        op = (1.0 if flick else 0.2) * k + (1.0 - k) * 1.0
    return TextTransform(opacity=op)


# --- per-glyph cascading variants ---


def _typewriter_rev_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Right-to-left typewriter — last char appears first."""
    out: list[GlyphTransform] = []
    for i in range(n):
        threshold = (n - 1 - i) / max(1, n)
        on = p >= threshold
        out.append(GlyphTransform(opacity=1.0 if on else 0.0))
    return out


def _page_turn_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char flips in (scale_x 0 → 1) from left edge — book-style."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        e = _ease_out_cubic(pi)
        sx = (1.0 - k) + k * max(0.05, e)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 4.0),
            scale_x=sx,
            pivot_x=0.0,
            pivot_y=0.5,
        ))
    return out


def _wave_seq_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char rides a sine wave that travels across the text and
    settles. Different phase per char so motion reads as a wave."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        e = _ease_out_cubic(pi)
        amp = 50.0 * (1.0 - e) * k
        phase = i * 0.4 + p * math.pi * 2.0
        dy = math.sin(phase) * amp
        out.append(GlyphTransform(opacity=min(1.0, pi * 3.0), offset_y=dy))
    return out


def _cascade_up_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Cascade slide-in but bottom-to-top (last char first)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        rev_i = n - 1 - i
        pi = _stagger_progress(p, n, rev_i, band=0.4)
        e = _ease_out_cubic(pi)
        out.append(GlyphTransform(
            opacity=e,
            offset_y=-(1.0 - e) * 60.0 * k,
        ))
    return out


def _cascade_alt_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Alternating zigzag cascade — odd chars from above, even from below."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        e = _ease_out_cubic(pi)
        side = -1 if (i % 2 == 0) else 1
        out.append(GlyphTransform(
            opacity=e,
            offset_y=side * (1.0 - e) * 60.0 * k,
        ))
    return out


def _drumroll_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Rapid sequential pop — each char overshoots fast."""
    out: list[GlyphTransform] = []
    for i in range(n):
        # Tighter band → faster cascade
        pi = _stagger_progress(p, n, i, band=0.18)
        e = _ease_out_back(pi)
        s = 1.0 + (e - 1.0) * k
        s = max(0.05, s)
        out.append(GlyphTransform(opacity=min(1.0, pi * 5.0),
                                   scale_x=s, scale_y=s))
    return out


def _reveal_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char slides in from the left of its slot (curtain reveal)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        e = _ease_out_cubic(pi)
        out.append(GlyphTransform(
            opacity=e,
            offset_x=-(1.0 - e) * 40.0 * k,
        ))
    return out


def _flip_cards_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char flips card-style (Y-axis simulated via scale_x) with
    a pronounced cascading delay."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        e = _ease_out_back(pi)
        sx = (1.0 - k) + k * max(0.05, e)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 3.0),
            scale_x=sx,
            pivot_x=0.5,
            pivot_y=0.5,
        ))
    return out


def _confetti_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char drops with random rotation and per-char gravity."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = (i * 0.327 + 0.1) % 1.0
        pi = max(0.0, min(1.0, (p - seed * 0.5) / 0.5))
        e = _ease_out_cubic(pi)
        dy = -(1.0 - e) * (180.0 + seed * 60.0) * k
        rot = (1.0 - e) * (i * 47 % 360) * 1.0 * k
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 4.0),
            offset_y=dy,
            rotation_deg=rot,
        ))
    return out


def _snow_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Slow lateral drift while falling — gentler than rain."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = (i * 0.413) % 1.0
        pi = max(0.0, min(1.0, (p - seed * 0.4) / 0.6))
        e = _ease_out_cubic(pi)
        dy = -(1.0 - e) * 140.0 * k
        # Gentle horizontal drift
        dx = math.sin((p + seed) * math.pi * 1.5) * 18.0 * (1.0 - e) * k
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 3.0),
            offset_x=dx, offset_y=dy,
        ))
    return out


def _smoke_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Hazy entrance — opacity oscillates while offset settles."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.6)
        e = _ease_out_cubic(pi)
        # Per-char chaotic offset
        seed = i * 0.713
        dx = math.sin(seed + p * 4.0) * 18.0 * (1.0 - e) * k
        dy = math.cos(seed * 1.5 + p * 5.0) * 18.0 * (1.0 - e) * k
        # Opacity flickers in
        op_base = min(1.0, pi * 2.5)
        op = op_base * (0.6 + 0.4 * math.sin(p * math.pi * 6.0 + seed))
        op = max(0.0, min(op_base, op))
        out.append(GlyphTransform(opacity=op, offset_x=dx, offset_y=dy))
    return out


def _ghost_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Per-char ghost trail — slight per-glyph offset history feel
    via opacity + offset_x lag."""
    out: list[GlyphTransform] = []
    e = _ease_out_cubic(p)
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        ie = _ease_out_cubic(pi)
        # The "ghost" effect: chars come from slightly behind the previous one
        dx = (1.0 - ie) * -30.0 * (1 + i * 0.1) * k
        out.append(GlyphTransform(
            opacity=ie * 0.85 + 0.15 * e,
            offset_x=dx,
        ))
    return out


def _glitch_jump_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Per-char position jitter that resolves at p=1. Different from
    Eve Glitch (multi-layer); this is per-glyph chaos."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.6)
        e = _ease_out_cubic(pi)
        amp = (1.0 - e) * 22.0 * k
        # Per-char noise driven by position + time
        dx = math.sin((i + p * 30.0) * 7.3) * amp
        dy = math.cos((i + p * 25.0) * 5.1) * amp * 0.7
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 3.0),
            offset_x=dx, offset_y=dy,
        ))
    return out


def _pulse_seq_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char pulses (scale wave) sequentially — single beat per."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.4)
        # Bell curve scale: peak at pi=0.5
        bell = math.exp(-((pi - 0.5) ** 2) / 0.05)
        s_extra = bell * 0.5 * k
        s = max(0.05, 0.7 + 0.3 * pi + s_extra)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 4.0),
            scale_x=s, scale_y=s,
        ))
    return out


def _helix_in(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Spiral-like motion but with an axial component — chars trace
    a helix along the text axis as they fly in."""
    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.5)
        e = _ease_out_cubic(pi)
        radius = (1.0 - e) * 90.0 * k
        # Each char a different phase along the helix
        phase = i * 0.6 + p * math.pi * 3.0
        ox = 0.0
        oy = math.sin(phase) * radius
        # scale_x to simulate depth (cosine)
        sx = (1.0 - k) + k * (0.5 + 0.5 * math.cos(phase) * e + 0.5 * (1.0 - e))
        sx = max(0.05, sx)
        out.append(GlyphTransform(
            opacity=min(1.0, pi * 3.0),
            offset_y=oy, offset_x=ox,
            scale_x=sx,
            pivot_x=0.5, pivot_y=0.5,
        ))
    return out


# --- additional OUT animations ---


def _implode_out(p: float, k: float = 1.0) -> TextTransform:
    """Suck inward — scale to 0 with a small final spin."""
    e = _ease_in_cubic(p)
    s = 1.0 - e * k
    s = max(0.05, s)
    rot = e * 90.0 * k
    return TextTransform(opacity=1.0 - e, scale_x=s, scale_y=s, rotation_deg=rot)


def _vanish_out(p: float, k: float = 1.0) -> TextTransform:
    """Rapid exit — quick scale-up + alpha drop."""
    e = _ease_in_cubic(p)
    s = 1.0 + e * 0.6 * k
    return TextTransform(opacity=1.0 - e, scale_x=s, scale_y=s)


def _slide_out_tl(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * e
    return TextTransform(opacity=1.0 - e, offset_x=-d, offset_y=-d)


def _slide_out_tr(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * e
    return TextTransform(opacity=1.0 - e, offset_x=d, offset_y=-d)


def _slide_out_bl(p: float, k: float = 1.0) -> TextTransform:
    e = _ease_in_cubic(p)
    d = _SLIDE_DISTANCE_PX * k * e
    return TextTransform(opacity=1.0 - e, offset_x=-d, offset_y=d)


def _spiral_out(p: float, k: float = 1.0) -> TextTransform:
    """Whole-text spiral exit — scale down + spin out."""
    e = _ease_in_cubic(p)
    s = 1.0 - e * 0.9 * k
    s = max(0.05, s)
    rot = e * 540.0 * k
    return TextTransform(opacity=1.0 - e, scale_x=s, scale_y=s, rotation_deg=rot)


def _zoom_extreme_out(p: float, k: float = 1.0) -> TextTransform:
    """Extreme zoom-out — like flying away from camera."""
    e = _ease_in_cubic(p)
    s = 1.0 - e * 0.95 * k
    s = max(0.02, s)
    return TextTransform(opacity=1.0 - e, scale_x=s, scale_y=s)


def _fade_up_out(p: float, k: float = 1.0) -> TextTransform:
    """Slight upward drift while fading. Subtle — nice for subtitles."""
    e = _ease_in_cubic(p)
    return TextTransform(opacity=1.0 - e, offset_y=-e * 30.0 * k)


def _crumble_out_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char drops with rotation as the text crumbles down."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = (i * 0.197) % 1.0
        local_p = max(0.0, min(1.0, (p - seed * 0.3) / 0.7))
        e = _ease_in_cubic(local_p)
        dy = e * 240.0 * k
        rot = e * (45 + (i * 23) % 90) * (1 if i % 2 else -1) * k
        out.append(GlyphTransform(
            opacity=1.0 - e,
            offset_y=dy, rotation_deg=rot,
            pivot_x=0.5, pivot_y=1.0,
        ))
    return out


def _shatter_out_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Sharp radial fragmentation — faster + steeper than burst-out."""
    out: list[GlyphTransform] = []
    e = _ease_in_cubic(p)
    distance = 480.0 * e * k
    for i in range(n):
        # Per-char direction with strong vertical component
        seed = (i * 0.673)
        angle = seed + (i * 1.1)
        ox = math.cos(angle) * distance
        oy = math.sin(angle) * distance - e * 80.0 * k  # gravity tug
        rot = e * (180 + i * 17) * (1 if i % 2 else -1) * k
        s = 1.0 - e * 0.4 * k
        s = max(0.05, s)
        out.append(GlyphTransform(
            opacity=1.0 - e,
            offset_x=ox, offset_y=oy, rotation_deg=rot,
            scale_x=s, scale_y=s,
        ))
    return out


def _dissolve_out_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Each char fades at a per-char-random pace (stays in place)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = (i * 0.291 + 0.05) % 1.0
        local_p = max(0.0, min(1.0, (p - seed * 0.5) / 0.5))
        e = _ease_in_cubic(local_p)
        out.append(GlyphTransform(opacity=1.0 - e))
    return out


def _wave_out_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Sine wave + fade-out — different from burst-out (which is radial)."""
    out: list[GlyphTransform] = []
    e = _ease_in_cubic(p)
    amp = e * 80.0 * k
    for i in range(n):
        phase = i * 0.6 + p * math.pi * 2.0
        out.append(GlyphTransform(
            opacity=1.0 - e,
            offset_y=math.sin(phase) * amp,
        ))
    return out


# ---------------------------------------------------------------------------
#  HOLD-phase animations (loopable — receive progress 0..1 within one
#  loop period; sin/cos based so frame 0 == frame 1 for seamless loops)
# ---------------------------------------------------------------------------


def _hold_bob(p: float, k: float = 1.0) -> TextTransform:
    """Gentle vertical bob — most subtle HOLD animation."""
    return TextTransform(offset_y=math.sin(p * math.pi * 2.0) * 8.0 * k)


def _hold_sway(p: float, k: float = 1.0) -> TextTransform:
    """Small angular wobble — like text on a slow swing."""
    return TextTransform(rotation_deg=math.sin(p * math.pi * 2.0) * 4.0 * k)


def _hold_breathe(p: float, k: float = 1.0) -> TextTransform:
    """Slow scale pulse — calm, breathing rhythm."""
    s = 1.0 + math.sin(p * math.pi * 2.0) * 0.05 * k
    return TextTransform(scale_x=s, scale_y=s)


def _hold_slow_rotate(p: float, k: float = 1.0) -> TextTransform:
    """Continuous full-circle rotation — one revolution per loop period."""
    return TextTransform(rotation_deg=p * 360.0 * k)


def _hold_pulse(p: float, k: float = 1.0) -> TextTransform:
    """Heartbeat-style double-beat scale loop."""
    s = 1.0 + math.sin(p * math.pi * 4.0) * 0.08 * k
    return TextTransform(scale_x=s, scale_y=s)


def _hold_shake(p: float, k: float = 1.0) -> TextTransform:
    """Continuous shake — high frequency."""
    amp = 4.0 * k
    return TextTransform(
        offset_x=math.sin(p * math.pi * 20.0) * amp,
        offset_y=math.cos(p * math.pi * 22.0) * amp * 0.7,
    )


def _hold_shimmer(p: float, k: float = 1.0) -> TextTransform:
    """Heat-haze loop — small wavy jitter."""
    amp = 5.0 * k
    return TextTransform(
        offset_x=math.sin(p * math.pi * 12.0) * amp,
        offset_y=math.cos(p * math.pi * 14.0) * amp * 0.6,
    )


def _hold_glow_flicker(p: float, k: float = 1.0) -> TextTransform:
    """Subtle opacity flicker — like a flickering neon sign."""
    op = 1.0 - 0.18 * (math.sin(p * math.pi * 6.0) ** 2) * k
    return TextTransform(opacity=op)


def _hold_wave_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Per-glyph traveling wave — left-to-right ripple loop."""
    out: list[GlyphTransform] = []
    for i in range(n):
        phase = i * 0.5 + p * math.pi * 2.0
        out.append(GlyphTransform(offset_y=math.sin(phase) * 8.0 * k))
    return out


def _hold_glitch_perglyph(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    """Per-glyph chaotic jitter — occasional bursts (like frozen Eve)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        seed = i * 3.7
        # Burst gating — only displace ~20% of the time per char.
        burst = 1.0 if math.sin(p * math.pi * 10.0 + seed) > 0.7 else 0.0
        amp = 8.0 * k * burst
        dx = math.sin(seed + p * 30.0) * amp
        dy = math.cos(seed + p * 25.0) * amp * 0.7
        out.append(GlyphTransform(offset_x=dx, offset_y=dy))
    return out


# ---------------------------------------------------------------------------
#  Multi-layer animations (RGB split / glitch)
# ---------------------------------------------------------------------------


def _eve_glitch_layers(p: float, k: float = 1.0) -> list[LayerTransform]:
    """Eve-style RGB split. Three coloured layers (cyan, magenta,
    white) drawn on top of each other. During short "glitch" bursts
    the cyan/magenta layers offset horizontally so the text reads as
    chromatic-aberrated; during the rest of the loop they sit close
    to the white centre.

    The "p" parameter spans the full IN→HOLD→OUT phase progress, but
    we treat it as a pseudo-continuous time so the glitch flashes
    happen at predictable points across the clip."""
    # Burst pattern: glitch active in 0.0–0.15 and 0.45–0.55 of progress.
    in_burst = (p < 0.15) or (0.45 < p < 0.55) or (0.75 < p < 0.82)
    # Smooth fade for the IN tail so the layers "land" together.
    base_op = min(1.0, p * 4.0)

    if in_burst:
        cyan_off = 14.0 * k
        mag_off = -10.0 * k
    else:
        cyan_off = 1.5 * k
        mag_off = -1.5 * k

    return [
        # Cyan behind
        LayerTransform(
            color_override="#00FFFF",
            opacity=base_op * 0.85,
            offset_x=cyan_off,
            offset_y=0.0,
        ),
        # Magenta behind (slight vertical shift for depth)
        LayerTransform(
            color_override="#FF00FF",
            opacity=base_op * 0.85,
            offset_x=mag_off,
            offset_y=2.0 if in_burst else 0.0,
        ),
        # White on top — main readable layer
        LayerTransform(
            color_override=None,         # honor style.color
            opacity=base_op,
            offset_x=0.0,
            offset_y=0.0,
        ),
    ]


def _folding_angle_break(p: float, n: int, k: float = 1.0) -> list[GlyphTransform]:
    rot_keys = [(0.0, 0.0), (0.15, -25.0), (0.30, 15.0),
                (0.45, -8.0), (0.60, 0.0), (1.0, 0.0)]
    color_keys = [(0.0, "#FFFFFF"), (0.15, "#FF006E"),
                  (0.45, "#FFDE00"), (0.60, "#FFFFFF"), (1.0, "#FFFFFF")]

    pivots = [
        (1.0, 1.0), (0.0, 1.0), (1.0, 0.0), (0.0, 0.0), (0.5, 0.5),
    ]

    def _interp(keys, t):
        for (t0, v0), (t1, v1) in zip(keys[:-1], keys[1:]):
            if t0 <= t <= t1:
                if isinstance(v0, str):
                    return v0
                span = max(1e-6, t1 - t0)
                kk = (t - t0) / span
                return v0 + (v1 - v0) * kk
        return keys[-1][1]

    out: list[GlyphTransform] = []
    for i in range(n):
        pi = _stagger_progress(p, n, i, band=0.7)
        rot = _interp(rot_keys, pi) * k
        col = _interp(color_keys, pi)
        op = min(1.0, pi * 3.0)
        px, py = pivots[i % len(pivots)]
        out.append(GlyphTransform(
            opacity=op,
            rotation_deg=rot,
            color_override=col if col != "#FFFFFF" else None,
            pivot_x=px,
            pivot_y=py,
        ))
    return out


REGISTRY: dict[str, Animation] = {
    "none":           _make("none",           "anim.none",        "any", _none, "basic", icon="⊘"),
    "fade-in":        _make("fade-in",        "anim.fade",        "in",  _fade_in,  icon="●"),
    "fade-out":       _make("fade-out",       "anim.fade",        "out", _fade_out, icon="○"),
    "slide-up-in":    _make("slide-up-in",    "anim.slide_up",    "in",  _slide_up_in,    icon="↑"),
    "slide-up-out":   _make("slide-up-out",   "anim.slide_up",    "out", _slide_up_out,   icon="↑"),
    "slide-down-in":  _make("slide-down-in",  "anim.slide_down",  "in",  _slide_down_in,  icon="↓"),
    "slide-down-out": _make("slide-down-out", "anim.slide_down",  "out", _slide_down_out, icon="↓"),
    "slide-left-in":  _make("slide-left-in",  "anim.slide_left",  "in",  _slide_left_in,  icon="←"),
    "slide-left-out": _make("slide-left-out", "anim.slide_left",  "out", _slide_left_out, icon="←"),
    "slide-right-in": _make("slide-right-in", "anim.slide_right", "in",  _slide_right_in, icon="→"),
    "slide-right-out":_make("slide-right-out","anim.slide_right", "out", _slide_right_out,icon="→"),
    "zoom-in":        _make("zoom-in",        "anim.zoom",        "in",  _zoom_in,  icon="⊕"),
    "zoom-out":       _make("zoom-out",       "anim.zoom",        "out", _zoom_out, icon="⊖"),
    "pop-in":         _make("pop-in",         "anim.pop",         "in",  _pop_in,   icon="✦"),
    "pop-out":        _make("pop-out",        "anim.pop",         "out", _pop_out,  icon="✦"),
    # Folding (per-glyph) — IN only for now; pair with a Basic OUT.
    "fold-paper-in":   _make_glyph("fold-paper-in",  "anim.fold_paper",  "in", _folding_paper_fold,  icon="▭"),
    "fold-joint-in":   _make_glyph("fold-joint-in",  "anim.fold_joint",  "in", _folding_joint_break, icon="⤲"),
    "fold-3dflip-in":  _make_glyph("fold-3dflip-in", "anim.fold_3dflip", "in", _folding_3d_flip,     icon="⟲"),
    "fold-flag-in":    _make_glyph("fold-flag-in",   "anim.fold_flag",   "in", _folding_flag_wave,   icon="〰"),
    "fold-angle-in":   _make_glyph("fold-angle-in",  "anim.fold_angle",  "in", _folding_angle_break, icon="⤴"),
    # === Kinetic / geometric category (30 total) ===
    # whole-text IN
    "spin-in":         _make("spin-in",       "anim.spin",        "in",  _spin_in,    category="kinetic", icon="⟳"),
    "stretch-in":      _make("stretch-in",    "anim.stretch",     "in",  _stretch_in, category="kinetic", icon="↕"),
    "slide-tl-in":     _make("slide-tl-in",   "anim.slide_tl",    "in",  _slide_tl_in, category="kinetic", icon="↘"),
    "slide-tr-in":     _make("slide-tr-in",   "anim.slide_tr",    "in",  _slide_tr_in, category="kinetic", icon="↙"),
    "slide-bl-in":     _make("slide-bl-in",   "anim.slide_bl",    "in",  _slide_bl_in, category="kinetic", icon="↗"),
    "slide-br-in":     _make("slide-br-in",   "anim.slide_br",    "in",  _slide_br_in, category="kinetic", icon="↖"),
    "roll-in":         _make("roll-in",       "anim.roll",        "in",  _roll_in,     category="kinetic", icon="↻"),
    "pendulum-in":     _make("pendulum-in",   "anim.pendulum",    "in",  _pendulum_in, category="kinetic", icon="⌒"),
    "pulse-in":        _make("pulse-in",      "anim.pulse",       "in",  _pulse_in,    category="kinetic", icon="◯"),
    "wobble-in":       _make("wobble-in",     "anim.wobble",      "in",  _wobble_in,   category="kinetic", icon="⌢"),
    "squash-in":       _make("squash-in",     "anim.squash",      "in",  _squash_in,   category="kinetic", icon="⫝"),
    "drill-in":        _make("drill-in",      "anim.drill",       "in",  _drill_in,    category="kinetic", icon="⊘"),
    # whole-text OUT
    "slide-out-br":    _make("slide-out-br",  "anim.slide_out_br","out", _slide_out_br, category="kinetic", icon="↘"),
    "squash-out":      _make("squash-out",    "anim.squash_out",  "out", _squash_out,   category="kinetic", icon="⥥"),
    "roll-out":        _make("roll-out",      "anim.roll_out",    "out", _roll_out,     category="kinetic", icon="↺"),
    # per-glyph IN
    "bounce-in":       _make_glyph("bounce-in",  "anim.bounce",   "in",  _bounce_in_perglyph,  category="kinetic", icon="⤓"),
    "spiral-in":       _make_glyph("spiral-in",  "anim.spiral",   "in",  _spiral_in_perglyph,  category="kinetic", icon="🌀"),
    "wave-in":         _make_glyph("wave-in",    "anim.wave",     "in",  _wave_in_perglyph,    category="kinetic", icon="∿"),
    "typewriter-in":   _make_glyph("typewriter-in", "anim.typewriter", "in", _typewriter_in,   category="kinetic", icon="⌨"),
    "stamp-in":        _make_glyph("stamp-in",   "anim.stamp",    "in",  _stamp_in_perglyph,   category="kinetic", icon="◉"),
    "domino-in":       _make_glyph("domino-in",  "anim.domino",   "in",  _domino_in,           category="kinetic", icon="⊟"),
    "rain-in":         _make_glyph("rain-in",    "anim.rain",     "in",  _rain_in_perglyph,    category="kinetic", icon="☂"),
    "scatter-in":      _make_glyph("scatter-in", "anim.scatter",  "in",  _scatter_in,          category="kinetic", icon="⁂"),
    "magnet-in":       _make_glyph("magnet-in",  "anim.magnet",   "in",  _magnet_in,           category="kinetic", icon="⤄"),
    "ripple-in":       _make_glyph("ripple-in",  "anim.ripple",   "in",  _ripple_in,           category="kinetic", icon="◎"),
    "cascade-in":      _make_glyph("cascade-in", "anim.cascade",  "in",  _cascade_slide_in,    category="kinetic", icon="≡"),
    "tornado-in":      _make_glyph("tornado-in", "anim.tornado",  "in",  _tornado_in,          category="kinetic", icon="🌪"),
    "pop-seq-in":      _make_glyph("pop-seq-in", "anim.pop_seq",  "in",  _pop_sequential_in,   category="kinetic", icon="✷"),
    # per-glyph OUT
    "burst-out":       _make_glyph("burst-out",  "anim.burst",    "out", _burst_out_perglyph,  category="kinetic", icon="✺"),
    "disintegrate-out":_make_glyph("disintegrate-out", "anim.disintegrate", "out", _disintegrate_out, category="kinetic", icon="⚝"),
    # === Phase 4b4: 50 more kinetic animations ===
    # whole-text path-based IN
    "arc-in":          _make("arc-in",        "anim.arc",         "in",  _arc_in,        category="kinetic", icon="⌒"),
    "zigzag-in":       _make("zigzag-in",     "anim.zigzag",      "in",  _zigzag_in,     category="kinetic", icon="⤴"),
    "scurve-in":       _make("scurve-in",     "anim.scurve",      "in",  _scurve_in,     category="kinetic", icon="∽"),
    "catapult-in":     _make("catapult-in",   "anim.catapult",    "in",  _catapult_in,   category="kinetic", icon="⊿"),
    "boomerang-in":    _make("boomerang-in",  "anim.boomerang",   "in",  _boomerang_in,  category="kinetic", icon="⟲"),
    "jump-in":         _make("jump-in",       "anim.jump",        "in",  _jump_in,       category="kinetic", icon="⌣"),
    "train-in":        _make("train-in",      "anim.train",       "in",  _train_in,      category="kinetic", icon="→"),
    "rocket-in":       _make("rocket-in",     "anim.rocket",      "in",  _rocket_in,     category="kinetic", icon="🚀"),
    # whole-text rotation
    "half-spin-in":    _make("half-spin-in",  "anim.half_spin",   "in",  _half_spin_in,  category="kinetic", icon="⥀"),
    "multi-spin-in":   _make("multi-spin-in", "anim.multi_spin",  "in",  _multi_spin_in, category="kinetic", icon="⟳"),
    "slow-rotate-in":  _make("slow-rotate-in","anim.slow_rotate", "in",  _slow_rotate_in,category="kinetic", icon="◜"),
    "tilt-in":         _make("tilt-in",       "anim.tilt",        "in",  _tilt_in,       category="kinetic", icon="∠"),
    "coin-flip-in":    _make("coin-flip-in",  "anim.coin_flip",   "in",  _coin_flip_in,  category="kinetic", icon="◐"),
    # whole-text scale
    "zoom-huge-in":    _make("zoom-huge-in",  "anim.zoom_huge",   "in",  _zoom_huge_in,  category="kinetic", icon="⊕"),
    "tiny-grow-in":    _make("tiny-grow-in",  "anim.tiny_grow",   "in",  _tiny_grow_in,  category="kinetic", icon="•"),
    "heartbeat-in":    _make("heartbeat-in",  "anim.heartbeat",   "in",  _heartbeat_in,  category="kinetic", icon="♥"),
    "inflate-in":      _make("inflate-in",    "anim.inflate",     "in",  _inflate_in,    category="kinetic", icon="◯"),
    "trampoline-in":   _make("trampoline-in", "anim.trampoline",  "in",  _trampoline_in, category="kinetic", icon="⊜"),
    # whole-text effects
    "vibrate-in":      _make("vibrate-in",    "anim.vibrate",     "in",  _vibrate_in,    category="kinetic", icon="≋"),
    "earthquake-in":   _make("earthquake-in", "anim.earthquake",  "in",  _earthquake_in, category="kinetic", icon="≈"),
    "float-in":        _make("float-in",      "anim.float",       "in",  _float_in,      category="kinetic", icon="☁"),
    "shimmer-in":      _make("shimmer-in",    "anim.shimmer",     "in",  _shimmer_in,    category="kinetic", icon="✧"),
    "strobe-in":       _make("strobe-in",     "anim.strobe",      "in",  _strobe_in,     category="kinetic", icon="⚡"),
    # per-glyph cascading
    "typewriter-rev-in":_make_glyph("typewriter-rev-in","anim.typewriter_rev","in",_typewriter_rev_in,category="kinetic", icon="⌫"),
    "page-turn-in":    _make_glyph("page-turn-in", "anim.page_turn", "in", _page_turn_in,    category="kinetic", icon="📖"),
    "wave-seq-in":     _make_glyph("wave-seq-in",  "anim.wave_seq",  "in", _wave_seq_in,     category="kinetic", icon="〜"),
    "cascade-up-in":   _make_glyph("cascade-up-in","anim.cascade_up","in", _cascade_up_in,   category="kinetic", icon="↥"),
    "cascade-alt-in":  _make_glyph("cascade-alt-in","anim.cascade_alt","in",_cascade_alt_in, category="kinetic", icon="⇕"),
    "drumroll-in":     _make_glyph("drumroll-in",  "anim.drumroll",  "in", _drumroll_in,     category="kinetic", icon="⚆"),
    "reveal-in":       _make_glyph("reveal-in",    "anim.reveal",    "in", _reveal_in,       category="kinetic", icon="▸"),
    "flip-cards-in":   _make_glyph("flip-cards-in","anim.flip_cards","in", _flip_cards_in,   category="kinetic", icon="🃏"),
    "confetti-in":     _make_glyph("confetti-in",  "anim.confetti",  "in", _confetti_in,     category="kinetic", icon="🎉"),
    "snow-in":         _make_glyph("snow-in",      "anim.snow",      "in", _snow_in,         category="kinetic", icon="❄"),
    "smoke-in":        _make_glyph("smoke-in",     "anim.smoke",     "in", _smoke_in,        category="kinetic", icon="☁"),
    "ghost-in":        _make_glyph("ghost-in",     "anim.ghost",     "in", _ghost_in,        category="kinetic", icon="◌"),
    "glitch-jump-in":  _make_glyph("glitch-jump-in","anim.glitch_jump","in",_glitch_jump_in, category="kinetic", icon="⌇"),
    "pulse-seq-in":    _make_glyph("pulse-seq-in", "anim.pulse_seq", "in", _pulse_seq_in,    category="kinetic", icon="◉"),
    "helix-in":        _make_glyph("helix-in",     "anim.helix",     "in", _helix_in,        category="kinetic", icon="🧬"),
    # whole-text OUT additions
    "implode-out":     _make("implode-out",   "anim.implode",     "out", _implode_out,   category="kinetic", icon="⊙"),
    "vanish-out":      _make("vanish-out",    "anim.vanish",      "out", _vanish_out,    category="kinetic", icon="✶"),
    "slide-out-tl":    _make("slide-out-tl",  "anim.slide_out_tl","out", _slide_out_tl,  category="kinetic", icon="↖"),
    "slide-out-tr":    _make("slide-out-tr",  "anim.slide_out_tr","out", _slide_out_tr,  category="kinetic", icon="↗"),
    "slide-out-bl":    _make("slide-out-bl",  "anim.slide_out_bl","out", _slide_out_bl,  category="kinetic", icon="↙"),
    "spiral-out":      _make("spiral-out",    "anim.spiral_out",  "out", _spiral_out,    category="kinetic", icon="🌀"),
    "zoom-extreme-out":_make("zoom-extreme-out","anim.zoom_extreme_out","out",_zoom_extreme_out,category="kinetic", icon="⊖"),
    "fade-up-out":     _make("fade-up-out",   "anim.fade_up_out", "out", _fade_up_out,   category="kinetic", icon="↑"),
    # per-glyph OUT additions
    "crumble-out":     _make_glyph("crumble-out",  "anim.crumble",   "out", _crumble_out_perglyph,   category="kinetic", icon="⤓"),
    "shatter-out":     _make_glyph("shatter-out",  "anim.shatter",   "out", _shatter_out_perglyph,   category="kinetic", icon="✸"),
    "dissolve-out":    _make_glyph("dissolve-out", "anim.dissolve",  "out", _dissolve_out_perglyph,  category="kinetic", icon="⋯"),
    "wave-out":        _make_glyph("wave-out",     "anim.wave_out",  "out", _wave_out_perglyph,      category="kinetic", icon="〰"),
    # Multi-layer (RGB split / glitch)
    "eve-glitch-in":   _make_layers("eve-glitch-in", "anim.eve_glitch",  "in", _eve_glitch_layers,
                                    category="utaite", icon="⚡"),
    # === HOLD-phase animations (loopable) ===
    "hold-bob":          _make_hold("hold-bob",           "anim.hold_bob",          _hold_bob,           icon="↕"),
    "hold-sway":         _make_hold("hold-sway",          "anim.hold_sway",         _hold_sway,          icon="⌒"),
    "hold-breathe":      _make_hold("hold-breathe",       "anim.hold_breathe",      _hold_breathe,       icon="◯"),
    "hold-slow-rotate":  _make_hold("hold-slow-rotate",   "anim.hold_slow_rotate",  _hold_slow_rotate,   icon="↻", loop_period=4.0),
    "hold-pulse":        _make_hold("hold-pulse",         "anim.hold_pulse",        _hold_pulse,         icon="♥"),
    "hold-shake":        _make_hold("hold-shake",         "anim.hold_shake",        _hold_shake,         icon="≋"),
    "hold-shimmer":      _make_hold("hold-shimmer",       "anim.hold_shimmer",      _hold_shimmer,       icon="✧"),
    "hold-glow-flicker": _make_hold("hold-glow-flicker",  "anim.hold_glow_flicker", _hold_glow_flicker,  icon="⚡"),
    "hold-wave":         _make_hold_glyph("hold-wave",    "anim.hold_wave",         _hold_wave_perglyph, icon="〰"),
    "hold-glitch":       _make_hold_glyph("hold-glitch",  "anim.hold_glitch",       _hold_glitch_perglyph, icon="⌇"),
}


def get_animation(id: str) -> Animation:
    """Lookup with safe fallback to identity ('none')."""
    return REGISTRY.get(id, REGISTRY["none"])


def list_for_direction(direction: str) -> list[Animation]:
    """Animations applicable for IN or OUT pickers, plus 'none'."""
    out: list[Animation] = [REGISTRY["none"]]
    for anim in REGISTRY.values():
        if anim.id == "none":
            continue
        if anim.direction == direction:
            out.append(anim)
    return out


# ---------------------------------------------------------------------------
#  Per-clip frame computation
# ---------------------------------------------------------------------------


def _resolve_phase(clip, time_s: float):
    """Internal: classify the current play time into a phase + per-
    phase progress + the relevant animation id + intensity multiplier.

    Returns ``(animation_id, progress, intensity)`` for the *primary*
    animation in the active phase. HOLD returns ``("none", 1.0, 1.0)``
    when no hold animation is configured.

    For composition (extras list), use :func:`_resolve_phase_stack`."""
    duration = clip.duration_s
    in_dur = max(0.0, float(clip.animation.in_duration))
    out_dur = max(0.0, float(clip.animation.out_duration))
    t = max(0.0, min(duration, float(time_s)))

    if in_dur + out_dur > duration > 0:
        scale = duration / (in_dur + out_dur)
        in_dur *= scale
        out_dur *= scale

    if t < in_dur:
        k = float(getattr(clip.animation, "in_intensity", 100.0)) / 100.0
        return clip.animation.in_animation, t / max(1e-3, in_dur), max(0.0, k)
    if t < duration - out_dur:
        hold_anim_id = getattr(clip.animation, "hold_animation", "none")
        if hold_anim_id and hold_anim_id != "none":
            anim = get_animation(hold_anim_id)
            if anim.compute_whole or anim.compute_perglyph:
                local_t = t - in_dur
                period = max(0.1, float(anim.loop_period))
                progress = (local_t / period) % 1.0
                k = float(getattr(clip.animation, "hold_intensity", 100.0)) / 100.0
                return hold_anim_id, progress, max(0.0, k)
        return "none", 1.0, 1.0
    k = float(getattr(clip.animation, "out_intensity", 100.0)) / 100.0
    return (
        clip.animation.out_animation,
        (t - (duration - out_dur)) / max(1e-3, out_dur),
        max(0.0, k),
    )


def _phase_progress_for(anim_id: str, phase: str, t_local: float,
                        phase_dur: float, k: float):
    """Map ``t_local`` (seconds inside the phase) → progress for one
    animation. IN/OUT progress is t/duration. HOLD wraps at the
    animation's loop_period."""
    if phase == "hold":
        if not anim_id or anim_id == "none":
            return None
        anim = get_animation(anim_id)
        if anim.compute_whole is None and anim.compute_perglyph is None:
            return None
        period = max(0.1, float(anim.loop_period))
        return (anim_id, (t_local / period) % 1.0, max(0.0, k))
    # in / out
    if not anim_id:
        return None
    return (anim_id, t_local / max(1e-3, phase_dur), max(0.0, k))


def _resolve_phase_stack(clip, time_s: float) -> list[tuple]:
    """Return the full list of ``(anim_id, progress, intensity)`` tuples
    contributing at ``time_s`` — primary first, then extras in order.

    Empty list means render identity (fully-composed no-op)."""
    duration = clip.duration_s
    in_dur = max(0.0, float(clip.animation.in_duration))
    out_dur = max(0.0, float(clip.animation.out_duration))
    t = max(0.0, min(duration, float(time_s)))

    if in_dur + out_dur > duration > 0:
        scale = duration / (in_dur + out_dur)
        in_dur *= scale
        out_dur *= scale

    cfg = clip.animation
    if t < in_dur:
        phase = "in"
        primary = cfg.in_animation
        extras = list(getattr(cfg, "in_extras", []) or [])
        k = float(getattr(cfg, "in_intensity", 100.0)) / 100.0
        t_local = t
        phase_dur = in_dur
    elif t < duration - out_dur:
        phase = "hold"
        primary = getattr(cfg, "hold_animation", "none")
        extras = list(getattr(cfg, "hold_extras", []) or [])
        k = float(getattr(cfg, "hold_intensity", 100.0)) / 100.0
        t_local = t - in_dur
        phase_dur = max(0.0, duration - in_dur - out_dur)
    else:
        phase = "out"
        primary = cfg.out_animation
        extras = list(getattr(cfg, "out_extras", []) or [])
        k = float(getattr(cfg, "out_intensity", 100.0)) / 100.0
        t_local = t - (duration - out_dur)
        phase_dur = out_dur

    out: list[tuple] = []
    primary_entry = _phase_progress_for(primary, phase, t_local, phase_dur, k)
    if primary_entry is not None:
        out.append(primary_entry)
    for aid in extras:
        entry = _phase_progress_for(aid, phase, t_local, phase_dur, k)
        if entry is not None:
            out.append(entry)
    return out


def _compose_text_transforms(xfs: list[TextTransform]) -> TextTransform:
    """Combine multiple whole-text transforms: offsets/rotations add,
    scale/opacity multiply. Identity when the list is empty."""
    if not xfs:
        return TextTransform.identity()
    ox = oy = rot = 0.0
    sx = sy = op = 1.0
    for x in xfs:
        ox += x.offset_x
        oy += x.offset_y
        rot += x.rotation_deg
        sx *= x.scale_x
        sy *= x.scale_y
        op *= x.opacity
    return TextTransform(
        opacity=max(0.0, min(1.0, op)),
        scale_x=sx, scale_y=sy,
        offset_x=ox, offset_y=oy,
        rotation_deg=rot,
    )


def _lift_text_to_glyphs(xf: TextTransform, n: int) -> list[GlyphTransform]:
    """Broadcast a whole-text transform onto N glyph transforms so
    whole-text and per-glyph animations can compose. The whole-text
    rotation/scale is applied around each glyph's own pivot — that's
    a deliberate simplification (true rotation around the text center
    needs a layout-aware pre-pass), but visually it gives every glyph
    the same wobble while letting per-glyph animations still fan out
    independently."""
    return [
        GlyphTransform(
            opacity=xf.opacity,
            scale_x=xf.scale_x, scale_y=xf.scale_y,
            offset_x=xf.offset_x, offset_y=xf.offset_y,
            rotation_deg=xf.rotation_deg,
        )
        for _ in range(n)
    ]


def _compose_glyph_lists(stacks: list[list[GlyphTransform]],
                         n: int) -> list[GlyphTransform]:
    """Element-wise compose N-length glyph transform lists. The first
    color_override that's set wins (primary's color usually)."""
    out: list[GlyphTransform] = []
    for i in range(n):
        ox = oy = rot = 0.0
        sx = sy = op = 1.0
        pivot_x = 0.5
        pivot_y = 0.5
        color: str | None = None
        for stack in stacks:
            if i >= len(stack):
                continue
            g = stack[i]
            ox += g.offset_x
            oy += g.offset_y
            rot += g.rotation_deg
            sx *= g.scale_x
            sy *= g.scale_y
            op *= g.opacity
            # The first non-default pivot wins — most per-glyph anims
            # use 0.5/0.5 anyway, so this rarely matters.
            if g.pivot_x != 0.5 or g.pivot_y != 0.5:
                pivot_x, pivot_y = g.pivot_x, g.pivot_y
            if color is None and g.color_override is not None:
                color = g.color_override
        out.append(GlyphTransform(
            opacity=max(0.0, min(1.0, op)),
            scale_x=sx, scale_y=sy,
            offset_x=ox, offset_y=oy,
            rotation_deg=rot,
            pivot_x=pivot_x, pivot_y=pivot_y,
            color_override=color,
        ))
    return out


def _stack_has_perglyph(stack: list[tuple]) -> bool:
    for anim_id, _p, _k in stack:
        if get_animation(anim_id).compute_perglyph is not None:
            return True
    return False


def _stack_layers_anim(stack: list[tuple]):
    """First (anim, progress, k) in the stack with compute_layers, or None.
    Layers anims are exclusive — only one can render layers, but other
    extras still compose into each layer's transform."""
    for anim_id, p, k in stack:
        anim = get_animation(anim_id)
        if anim.compute_layers is not None:
            return anim, p, k
    return None


def compute_clip_transform(clip, time_s: float) -> TextTransform | None:
    """Whole-text transform composed across the primary + extras.
    Returns ``None`` when any animation in the stack is per-glyph
    (caller should ask for glyph transforms instead) or layers
    (caller should ask for layers)."""
    stack = _resolve_phase_stack(clip, time_s)
    if not stack:
        return None
    if _stack_layers_anim(stack) is not None:
        return None
    if _stack_has_perglyph(stack):
        return None
    parts: list[TextTransform] = []
    for anim_id, progress, k in stack:
        anim = get_animation(anim_id)
        if anim.compute_whole is not None:
            parts.append(anim.compute_whole(progress, k))
    return _compose_text_transforms(parts)


def compute_clip_glyph_transforms(
    clip, time_s: float, num_chars: int,
) -> list[GlyphTransform] | None:
    """Per-glyph composed transforms. Returns ``None`` when the stack
    is empty, contains a layers anim, or has no per-glyph contributors
    (caller falls back to whole-text)."""
    if num_chars <= 0:
        return None
    stack = _resolve_phase_stack(clip, time_s)
    if not stack:
        return None
    if _stack_layers_anim(stack) is not None:
        return None
    if not _stack_has_perglyph(stack):
        return None
    glyph_stacks: list[list[GlyphTransform]] = []
    for anim_id, progress, k in stack:
        anim = get_animation(anim_id)
        if anim.compute_perglyph is not None:
            glyph_stacks.append(anim.compute_perglyph(progress, num_chars, k))
        elif anim.compute_whole is not None:
            xf = anim.compute_whole(progress, k)
            glyph_stacks.append(_lift_text_to_glyphs(xf, num_chars))
    return _compose_glyph_lists(glyph_stacks, num_chars)


def compute_clip_layers(clip, time_s: float) -> list[LayerTransform] | None:
    """Multi-layer transforms with extras composed into every layer.
    Returns ``None`` when no layers anim is in the stack."""
    stack = _resolve_phase_stack(clip, time_s)
    if not stack:
        return None
    layers_entry = _stack_layers_anim(stack)
    if layers_entry is None:
        return None
    layers_anim, layers_p, layers_k = layers_entry
    base_layers = layers_anim.compute_layers(layers_p, layers_k)

    extras_xfs: list[TextTransform] = []
    for anim_id, progress, k in stack:
        anim = get_animation(anim_id)
        if anim is layers_anim:
            continue
        if anim.compute_whole is not None:
            extras_xfs.append(anim.compute_whole(progress, k))
    if not extras_xfs:
        return base_layers

    extra = _compose_text_transforms(extras_xfs)
    composed: list[LayerTransform] = []
    for layer in base_layers:
        composed.append(LayerTransform(
            color_override=layer.color_override,
            opacity=max(0.0, min(1.0, layer.opacity * extra.opacity)),
            offset_x=layer.offset_x + extra.offset_x,
            offset_y=layer.offset_y + extra.offset_y,
            blend_screen=layer.blend_screen,
        ))
    return composed


def is_perglyph_animation(animation_id: str) -> bool:
    return get_animation(animation_id).compute_perglyph is not None


def is_layered_animation(animation_id: str) -> bool:
    return get_animation(animation_id).compute_layers is not None
