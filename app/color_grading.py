"""Color grading data model + render helpers (Level 1).

Five user-facing sliders (brightness / contrast / saturation / temperature
/ tint) plus 8 named presets. Same values are consumed by:

* The preview pipeline in :mod:`app.project_player` — applies a numpy
  matrix transform per frame so slider drags feel real-time.
* The exporter in :mod:`app.video_exporter` — emits an ffmpeg
  ``eq + colorbalance`` filter pair, inserted into the filter graph
  right after the source concat so the grade lives under every overlay.

Slider ranges (matching the UI):

* ``brightness``   ``-100..100`` (0 = neutral). Maps linearly to ``eq=brightness``
  in ``-1..1`` for ffmpeg, and to ``+rgb`` offset for numpy.
* ``contrast``     ``-100..100`` (0 = neutral). ffmpeg ``contrast`` accepts
  ``-2..2`` where 1 = neutral; we map ``slider/100 + 1``.
* ``saturation``   ``-100..100`` (0 = neutral). ffmpeg ``saturation``
  accepts ``0..3`` (1 = neutral); ``1 + slider/100``.
* ``temperature``  ``-100..100`` (negative = cooler/blue, positive =
  warmer/orange). Drives ``colorbalance`` red↑/blue↓ at midtones.
* ``tint``         ``-100..100`` (negative = green, positive = magenta).
  Drives ``colorbalance`` green vs. magenta channel.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
#  Data model
# ---------------------------------------------------------------------------


@dataclass
class ColorGrade:
    """Per-track color grading state.

    Three master sliders (brightness / contrast / saturation) plus three
    color wheels (shadows / midtones / highlights) — each wheel stored
    as an ``(x, y)`` pair in ``-100..100`` describing the chromaticity
    shift applied to that tonal region.

    Wheel axes (matching the visual layout the editor draws):

    * ``+x`` → red / orange   (warm bias)
    * ``-x`` → cyan / blue    (cool bias)
    * ``+y`` → magenta / red  (warm-pink bias)
    * ``-y`` → green          (green bias)

    ``preset_id`` is UI bookkeeping; the actual values are what the
    preview and exporter read."""

    brightness: int = 0          # -100..100
    contrast: int = 0            # -100..100
    saturation: int = 0          # -100..100

    # Shadows wheel
    shadows_x: int = 0
    shadows_y: int = 0
    # Midtones wheel
    midtones_x: int = 0
    midtones_y: int = 0
    # Highlights wheel
    highlights_x: int = 0
    highlights_y: int = 0

    preset_id: str = "none"      # last-applied preset (or "custom")

    def is_identity(self) -> bool:
        return (
            self.brightness == 0 and self.contrast == 0 and self.saturation == 0
            and self.shadows_x == 0 and self.shadows_y == 0
            and self.midtones_x == 0 and self.midtones_y == 0
            and self.highlights_x == 0 and self.highlights_y == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "brightness": self.brightness, "contrast": self.contrast,
            "saturation": self.saturation,
            "shadows_x": self.shadows_x, "shadows_y": self.shadows_y,
            "midtones_x": self.midtones_x, "midtones_y": self.midtones_y,
            "highlights_x": self.highlights_x, "highlights_y": self.highlights_y,
            "preset_id": self.preset_id,
        }

    def reset(self) -> None:
        self.brightness = 0
        self.contrast = 0
        self.saturation = 0
        self.shadows_x = 0
        self.shadows_y = 0
        self.midtones_x = 0
        self.midtones_y = 0
        self.highlights_x = 0
        self.highlights_y = 0
        self.preset_id = "none"


# ---------------------------------------------------------------------------
#  Presets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ColorPreset:
    """One named preset row in the picker. ``feature_id`` is consulted
    by :mod:`app.tier` for Pro/Free gating. Shadows/Midtones/Highlights
    each carry an ``(x, y)`` chromaticity offset matching the ColorGrade
    wheel layout."""

    id: str
    name_key: str
    desc_key: str
    icon: str                    # short emoji / glyph for the tile
    feature_id: str
    brightness: int = 0
    contrast: int = 0
    saturation: int = 0
    shadows_x: int = 0
    shadows_y: int = 0
    midtones_x: int = 0
    midtones_y: int = 0
    highlights_x: int = 0
    highlights_y: int = 0


# Preset numbers — each preset paints one or two wheels per region to
# get the visual signature without going extreme. Users can nudge after
# applying. The coordinate convention matches ColorGrade above:
# +x = warm/red,  -x = cool/cyan,  +y = magenta,  -y = green.
COLOR_PRESETS: list[ColorPreset] = [
    ColorPreset(
        id="none", name_key="color.preset.none", desc_key="color.preset.none.desc",
        icon="∅", feature_id="color.preset.none",
    ),
    ColorPreset(
        id="cinematic", name_key="color.preset.cinematic",
        desc_key="color.preset.cinematic.desc",
        icon="🎬", feature_id="color.preset.cinematic",
        brightness=-5, contrast=25, saturation=-10,
        # Teal-and-orange — shadows cool, highlights warm.
        shadows_x=-30,    shadows_y=0,
        highlights_x=25,  highlights_y=10,
    ),
    ColorPreset(
        id="vintage", name_key="color.preset.vintage",
        desc_key="color.preset.vintage.desc",
        icon="📷", feature_id="color.preset.vintage",
        brightness=5, contrast=-10, saturation=-25,
        # Warm midtones, slightly green shadows — old film vibe.
        shadows_x=10,    shadows_y=-15,
        midtones_x=25,   midtones_y=-5,
    ),
    ColorPreset(
        id="cool", name_key="color.preset.cool",
        desc_key="color.preset.cool.desc",
        icon="❄", feature_id="color.preset.cool",
        brightness=0, contrast=10, saturation=0,
        midtones_x=-35,  midtones_y=0,
    ),
    ColorPreset(
        id="warm", name_key="color.preset.warm",
        desc_key="color.preset.warm.desc",
        icon="☀", feature_id="color.preset.warm",
        brightness=5, contrast=5, saturation=10,
        midtones_x=30,   midtones_y=0,
    ),
    ColorPreset(
        id="faded", name_key="color.preset.faded",
        desc_key="color.preset.faded.desc",
        icon="◐", feature_id="color.preset.faded",
        brightness=10, contrast=-25, saturation=-15,
        # Lifted shadows toward warm milky tone.
        shadows_x=15,    shadows_y=10,
    ),
    ColorPreset(
        id="bw", name_key="color.preset.bw",
        desc_key="color.preset.bw.desc",
        icon="◻", feature_id="color.preset.bw",
        brightness=0, contrast=15, saturation=-100,
    ),
    ColorPreset(
        id="punch", name_key="color.preset.punch",
        desc_key="color.preset.punch.desc",
        icon="✦", feature_id="color.preset.punch",
        brightness=5, contrast=30, saturation=25,
        # Slight warmth in midtones for "alive" look.
        midtones_x=8,    midtones_y=0,
    ),
    ColorPreset(
        id="mute", name_key="color.preset.mute",
        desc_key="color.preset.mute.desc",
        icon="◇", feature_id="color.preset.mute",
        brightness=0, contrast=-15, saturation=-30,
        midtones_x=-8,   midtones_y=0,
    ),
]


def get_preset(preset_id: str) -> ColorPreset:
    for p in COLOR_PRESETS:
        if p.id == preset_id:
            return p
    return COLOR_PRESETS[0]                 # "none"


def apply_preset(grade: ColorGrade, preset_id: str) -> None:
    p = get_preset(preset_id)
    grade.brightness = p.brightness
    grade.contrast = p.contrast
    grade.saturation = p.saturation
    grade.shadows_x = p.shadows_x
    grade.shadows_y = p.shadows_y
    grade.midtones_x = p.midtones_x
    grade.midtones_y = p.midtones_y
    grade.highlights_x = p.highlights_x
    grade.highlights_y = p.highlights_y
    grade.preset_id = p.id


# ---------------------------------------------------------------------------
#  Numpy preview transform
# ---------------------------------------------------------------------------


def _wheel_to_rgb_offset(x: int, y: int) -> tuple[float, float, float]:
    """Translate a wheel ``(x, y)`` in -100..100 to per-channel RGB
    offsets in -1..1. Coordinates use the same axis convention the UI
    paints: ``+x`` warm, ``-x`` cool, ``+y`` magenta, ``-y`` green.

    Returns ``(dR, dG, dB)`` at the wheel's full strength — callers
    multiply by a region weight (0..1) before adding to a pixel."""
    nx = x / 100.0          # -1..1
    ny = y / 100.0          # -1..1
    # Strength factor — keeps even max-pull wheels from blowing out.
    AMP = 0.20
    # Decompose along 2 axes:
    #   x axis  : warm  → (R+, G≈, B-)
    #   y axis  : magenta → (R+, G-, B+)  (negative y = green: G+, R-, B-)
    dR = AMP * (0.50 * nx + 0.30 * ny)
    dG = AMP * (-0.10 * nx - 0.40 * ny)
    dB = AMP * (-0.50 * nx + 0.30 * ny)
    return dR, dG, dB


def apply_to_rgb(rgb, grade: ColorGrade):
    """Apply the grade to a uint8 RGB ndarray.

    Returns a new uint8 ndarray. Float32 internally to avoid 8-bit
    banding. Tonal-region shifts (Shadows/Midtones/Highlights) are
    applied as RGB offsets weighted by per-pixel masks computed from
    Rec. 709 luma — that gives DaVinci-style 3-wheel grading without
    needing a colour-space round trip.
    """
    if grade.is_identity():
        return rgb
    import numpy as np

    f = rgb.astype(np.float32) / 255.0

    # ---- contrast (around 0.5 grey) + brightness ----
    if grade.contrast != 0:
        c = 1.0 + grade.contrast / 100.0       # -100..100 → 0..2
        f = (f - 0.5) * c + 0.5
    if grade.brightness != 0:
        f = f + grade.brightness / 100.0

    # ---- 3-way wheel shifts (S / M / H) ----
    has_wheels = (
        grade.shadows_x != 0 or grade.shadows_y != 0
        or grade.midtones_x != 0 or grade.midtones_y != 0
        or grade.highlights_x != 0 or grade.highlights_y != 0
    )
    if has_wheels:
        # Rec. 709 luma — used both for the saturation centre and for
        # the per-pixel region masks below.
        lum = (0.2126 * f[..., 0]
               + 0.7152 * f[..., 1]
               + 0.0722 * f[..., 2])
        # Soft triangular masks centred on 0 / 0.5 / 1 with width 0.5.
        # They sum to ~1 across the L range so a uniform shift across
        # all three wheels behaves like a global offset.
        s_mask = np.clip(1.0 - 2.0 * lum, 0.0, 1.0)
        h_mask = np.clip(2.0 * lum - 1.0, 0.0, 1.0)
        m_mask = 1.0 - s_mask - h_mask
        # Apply each wheel — broadcast (H, W, 1) mask × (3,) offset.
        for mask, (wx, wy) in (
            (s_mask, (grade.shadows_x, grade.shadows_y)),
            (m_mask, (grade.midtones_x, grade.midtones_y)),
            (h_mask, (grade.highlights_x, grade.highlights_y)),
        ):
            if wx == 0 and wy == 0:
                continue
            dR, dG, dB = _wheel_to_rgb_offset(wx, wy)
            mask3 = mask[..., None]
            f[..., 0] = f[..., 0] + dR * mask3[..., 0]
            f[..., 1] = f[..., 1] + dG * mask3[..., 0]
            f[..., 2] = f[..., 2] + dB * mask3[..., 0]

    # ---- saturation (toward luminance) ----
    if grade.saturation != 0:
        s = 1.0 + grade.saturation / 100.0
        # Re-compute luma after the wheel shifts so de-saturation
        # respects the graded look rather than the original pixels.
        lum = (0.2126 * f[..., 0]
               + 0.7152 * f[..., 1]
               + 0.0722 * f[..., 2])
        f[..., 0] = lum + (f[..., 0] - lum) * s
        f[..., 1] = lum + (f[..., 1] - lum) * s
        f[..., 2] = lum + (f[..., 2] - lum) * s

    np.clip(f, 0.0, 1.0, out=f)
    return (f * 255.0 + 0.5).astype(np.uint8)


# ---------------------------------------------------------------------------
#  ffmpeg filter string
# ---------------------------------------------------------------------------


def _wheel_to_colorbalance(x: int, y: int) -> tuple[float, float, float]:
    """Translate a wheel ``(x, y)`` to ffmpeg ``colorbalance`` channel
    offsets ``(r_, g_, b_)`` (each -1..1). Same axis convention as the
    numpy path: ``+x`` warm, ``+y`` magenta. Strength matches the
    preview's AMP factor so what users see in the editor matches the
    rendered file."""
    nx = x / 100.0
    ny = y / 100.0
    AMP = 0.40        # ffmpeg's colorbalance is gentler than raw add,
                      # so use a slightly higher factor than numpy AMP.
    r_ = AMP * (0.50 * nx + 0.30 * ny)
    g_ = AMP * (-0.10 * nx - 0.40 * ny)
    b_ = AMP * (-0.50 * nx + 0.30 * ny)
    return r_, g_, b_


def to_ffmpeg_filters(grade: ColorGrade) -> str | None:
    """Return the comma-joined ffmpeg filter expression for this grade,
    or ``None`` when the grade is identity.

    Layout:

    * ``eq``           brightness / contrast / saturation
    * ``colorbalance`` per-region wheels — ``rs/gs/bs`` (shadows),
      ``rm/gm/bm`` (midtones), ``rh/gh/bh`` (highlights). All in one
      filter call so ffmpeg only walks the frame once.
    """
    if grade.is_identity():
        return None
    parts: list[str] = []

    if grade.brightness != 0 or grade.contrast != 0 or grade.saturation != 0:
        b = grade.brightness / 100.0
        c = 1.0 + grade.contrast / 100.0
        s = 1.0 + grade.saturation / 100.0
        parts.append(
            f"eq=brightness={b:.4f}:contrast={c:.4f}:saturation={s:.4f}"
        )

    has_wheels = (
        grade.shadows_x != 0 or grade.shadows_y != 0
        or grade.midtones_x != 0 or grade.midtones_y != 0
        or grade.highlights_x != 0 or grade.highlights_y != 0
    )
    if has_wheels:
        rs, gs, bs = _wheel_to_colorbalance(grade.shadows_x, grade.shadows_y)
        rm, gm, bm = _wheel_to_colorbalance(grade.midtones_x, grade.midtones_y)
        rh, gh, bh = _wheel_to_colorbalance(grade.highlights_x, grade.highlights_y)
        parts.append(
            "colorbalance="
            f"rs={rs:.4f}:gs={gs:.4f}:bs={bs:.4f}:"
            f"rm={rm:.4f}:gm={gm:.4f}:bm={bm:.4f}:"
            f"rh={rh:.4f}:gh={gh:.4f}:bh={bh:.4f}"
        )

    return ",".join(parts) if parts else None
