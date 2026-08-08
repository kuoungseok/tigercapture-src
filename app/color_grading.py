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
    # Offset wheel — uniform RGB shift across every tonal region
    # (DaVinci's "Offset" / "Master"). Useful for fixing a global
    # colour cast without touching the lift/gamma/gain curve.
    offset_x: int = 0
    offset_y: int = 0

    # Per-wheel luma sliders — DaVinci's "Lift / Gamma / Gain / Offset"
    # vertical bars sitting next to each colour wheel. They lift or
    # press the brightness inside the wheel's tonal region only, so
    # users can darken shadows without touching highlights, etc.
    # Range -100..100, 0 = no change.
    shadows_l: int = 0
    midtones_l: int = 0
    highlights_l: int = 0
    offset_l: int = 0

    # Hue vs Hue curve — list of (input_hue 0..360, hue_delta
    # -180..+180) control points. Empty list means identity (no
    # rotation). The renderer interpolates linearly between adjacent
    # control points around the wrap-around hue circle.
    hue_vs_hue: list[tuple[float, float]] = field(default_factory=list)

    # Optional professional node workflow payload from app.color_workflow:
    # qualifier/window/curves/opacity. Renderers that do not understand it
    # safely ignore the field; project/node serialization can still preserve it.
    color_workflow: dict[str, Any] = field(default_factory=dict)

    # Optional advanced Resolve-style toolset payload from app.color_workflow:
    # HDR zones, log wheels, Hue vs Hue/Sat/Luma, Color Warper, gallery/shot
    # match metadata. Preview/export apply the implemented RGB transforms and
    # preserve the rest for UI/QA.
    advanced_color_toolset: dict[str, Any] = field(default_factory=dict)

    # Grade-local LUT slots. Project-level color management owns the global
    # input/creative/output LUT intent; these slots let clip/node grades carry
    # a matching payload for preview/export parity and preset workflows.
    input_lut_path: str = ""
    input_lut_strength: float = 1.0
    creative_lut_path: str = ""
    creative_lut_strength: float = 1.0
    output_lut_path: str = ""
    output_lut_strength: float = 1.0

    preset_id: str = "none"      # last-applied preset (or "custom")

    def is_identity(self) -> bool:
        # Hue-vs-hue identity = no control points OR every point has
        # delta == 0. Treat both as no-op.
        hue_active = any(abs(d) > 0.5 for _, d in self.hue_vs_hue)
        workflow_active = bool(
            self.color_workflow
            and bool(self.color_workflow.get("enabled", True))
        )
        advanced_active = bool(
            self.advanced_color_toolset
            and bool(self.advanced_color_toolset.get("enabled", True))
        )
        lut_active = (
            (bool(self.input_lut_path) and self.input_lut_strength > 0.0)
            or (bool(self.creative_lut_path) and self.creative_lut_strength > 0.0)
            or (bool(self.output_lut_path) and self.output_lut_strength > 0.0)
        )
        return (
            self.brightness == 0 and self.contrast == 0 and self.saturation == 0
            and self.shadows_x == 0 and self.shadows_y == 0
            and self.midtones_x == 0 and self.midtones_y == 0
            and self.highlights_x == 0 and self.highlights_y == 0
            and self.offset_x == 0 and self.offset_y == 0
            and self.shadows_l == 0 and self.midtones_l == 0
            and self.highlights_l == 0 and self.offset_l == 0
            and not hue_active
            and not workflow_active
            and not advanced_active
            and not lut_active
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "brightness": self.brightness, "contrast": self.contrast,
            "saturation": self.saturation,
            "shadows_x": self.shadows_x, "shadows_y": self.shadows_y,
            "midtones_x": self.midtones_x, "midtones_y": self.midtones_y,
            "highlights_x": self.highlights_x, "highlights_y": self.highlights_y,
            "offset_x": self.offset_x, "offset_y": self.offset_y,
            "shadows_l": self.shadows_l, "midtones_l": self.midtones_l,
            "highlights_l": self.highlights_l, "offset_l": self.offset_l,
            "hue_vs_hue": list(self.hue_vs_hue),
            "color_workflow": dict(self.color_workflow or {}),
            "advanced_color_toolset": dict(self.advanced_color_toolset or {}),
            "input_lut_path": self.input_lut_path,
            "input_lut_strength": float(self.input_lut_strength),
            "creative_lut_path": self.creative_lut_path,
            "creative_lut_strength": float(self.creative_lut_strength),
            "output_lut_path": self.output_lut_path,
            "output_lut_strength": float(self.output_lut_strength),
            "preset_id": self.preset_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ColorGrade":
        """Round-trip restore from to_dict — used for per-node grade
        persistence in node_graph_view_data."""
        g = cls()
        for k in (
            "brightness", "contrast", "saturation",
            "shadows_x", "shadows_y", "midtones_x", "midtones_y",
            "highlights_x", "highlights_y", "offset_x", "offset_y",
            "shadows_l", "midtones_l", "highlights_l", "offset_l",
        ):
            if k in d:
                setattr(g, k, int(d[k]))
        if "hue_vs_hue" in d:
            try:
                g.hue_vs_hue = [
                    (float(h), float(v)) for h, v in d["hue_vs_hue"]
                ]
            except Exception:
                g.hue_vs_hue = []
        if "preset_id" in d:
            g.preset_id = str(d["preset_id"])
        if isinstance(d.get("color_workflow"), dict):
            g.color_workflow = dict(d["color_workflow"])
        if isinstance(d.get("advanced_color_toolset"), dict):
            g.advanced_color_toolset = dict(d["advanced_color_toolset"])
        for k in ("input_lut_path", "creative_lut_path", "output_lut_path"):
            if k in d:
                setattr(g, k, str(d.get(k) or ""))
        for k in ("input_lut_strength", "creative_lut_strength", "output_lut_strength"):
            if k in d:
                try:
                    setattr(g, k, max(0.0, min(1.0, float(d[k]))))
                except Exception:
                    pass
        return g

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
        self.offset_x = 0
        self.offset_y = 0
        self.shadows_l = 0
        self.midtones_l = 0
        self.highlights_l = 0
        self.offset_l = 0
        self.hue_vs_hue = []
        self.color_workflow = {}
        self.advanced_color_toolset = {}
        self.input_lut_path = ""
        self.input_lut_strength = 1.0
        self.creative_lut_path = ""
        self.creative_lut_strength = 1.0
        self.output_lut_path = ""
        self.output_lut_strength = 1.0
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
    # Presets pre-1.4 didn't ship Offset values; default them to 0
    # explicitly so re-applying a preset clears any custom Offset the
    # user dialed in.
    grade.offset_x = getattr(p, "offset_x", 0)
    grade.offset_y = getattr(p, "offset_y", 0)
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

    base_rgb = rgb
    if getattr(grade, "input_lut_path", "") and getattr(grade, "input_lut_strength", 1.0) > 0.0:
        base_rgb = _apply_lut_slot(
            base_rgb,
            str(getattr(grade, "input_lut_path", "")),
            float(getattr(grade, "input_lut_strength", 1.0)),
        )

    f = base_rgb.astype(np.float32) / 255.0

    # ---- contrast (around 0.5 grey) + brightness ----
    if grade.contrast != 0:
        c = 1.0 + grade.contrast / 100.0       # -100..100 → 0..2
        f = (f - 0.5) * c + 0.5
    if grade.brightness != 0:
        f = f + grade.brightness / 100.0

    # ---- Offset (uniform RGB shift across the whole image) ----
    if grade.offset_x != 0 or grade.offset_y != 0:
        odR, odG, odB = _wheel_to_rgb_offset(grade.offset_x, grade.offset_y)
        f[..., 0] = f[..., 0] + odR
        f[..., 1] = f[..., 1] + odG
        f[..., 2] = f[..., 2] + odB

    # ---- 3-way wheel shifts (S / M / H) + per-region luma sliders ----
    has_wheels = (
        grade.shadows_x != 0 or grade.shadows_y != 0
        or grade.midtones_x != 0 or grade.midtones_y != 0
        or grade.highlights_x != 0 or grade.highlights_y != 0
    )
    has_luma = (
        grade.shadows_l != 0 or grade.midtones_l != 0
        or grade.highlights_l != 0
    )
    if has_wheels or has_luma:
        # Rec. 709 luma — used for both the saturation centre and
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
        # Chromaticity offsets — wheel ``(x, y)`` → RGB triplet.
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
        # Per-region luma — DaVinci's "lift / gamma / gain" knobs.
        # ``LUMA_AMP`` caps full-strength (±100) at ±0.30 in 0..1
        # space so the slider remains useful at full extent without
        # clipping the image immediately.
        LUMA_AMP = 0.30
        for mask, lv in (
            (s_mask, grade.shadows_l),
            (m_mask, grade.midtones_l),
            (h_mask, grade.highlights_l),
        ):
            if lv == 0:
                continue
            shift = (lv / 100.0) * LUMA_AMP
            f[..., 0] = f[..., 0] + shift * mask
            f[..., 1] = f[..., 1] + shift * mask
            f[..., 2] = f[..., 2] + shift * mask

    # ---- Offset luma (uniform brightness shift) ----
    if grade.offset_l != 0:
        # Same amplitude scale as the per-region sliders, but
        # uniformly applied — the offset luma equivalent of the
        # offset wheel for chroma.
        f = f + (grade.offset_l / 100.0) * 0.30

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

    # ---- Hue vs Hue curve (rotate specific hues) ----
    # Run AFTER the offsets/wheels/sat so the curve operates on the
    # already-graded image — picking the colour the user sees.
    if any(abs(d) > 0.5 for _, d in grade.hue_vs_hue):
        f = _apply_hue_vs_hue(f, grade.hue_vs_hue)

    np.clip(f, 0.0, 1.0, out=f)
    out = (f * 255.0 + 0.5).astype(np.uint8)

    if getattr(grade, "creative_lut_path", "") and getattr(grade, "creative_lut_strength", 1.0) > 0.0:
        out = _apply_lut_slot(
            out,
            str(getattr(grade, "creative_lut_path", "")),
            float(getattr(grade, "creative_lut_strength", 1.0)),
        )

    workflow = getattr(grade, "color_workflow", None) or {}
    if isinstance(workflow, dict) and workflow.get("enabled", True):
        try:
            from app.color_workflow import ColorNodeWorkflow, apply_curves, combined_node_mask

            node = ColorNodeWorkflow.from_dict(workflow)
            curved = apply_curves(out, node.curves)
            mask = combined_node_mask(base_rgb, node)
            if mask.shape == out.shape[:2]:
                if np.all(mask >= 0.999):
                    out = curved
                else:
                    mf = mask[..., None]
                    out = np.clip(
                        mf * curved.astype(np.float32)
                        + (1.0 - mf) * base_rgb.astype(np.float32),
                        0,
                        255,
                    ).astype(np.uint8)
        except Exception:
            pass
    advanced = getattr(grade, "advanced_color_toolset", None) or {}
    if isinstance(advanced, dict) and advanced.get("enabled", True):
        try:
            from app.color_workflow import apply_advanced_color_toolset

            out = apply_advanced_color_toolset(out, advanced)
        except Exception:
            pass
    if getattr(grade, "output_lut_path", "") and getattr(grade, "output_lut_strength", 1.0) > 0.0:
        out = _apply_lut_slot(
            out,
            str(getattr(grade, "output_lut_path", "")),
            float(getattr(grade, "output_lut_strength", 1.0)),
        )
    try:
        from app.video_letterbox import preserve_letterbox_matte

        out = preserve_letterbox_matte(rgb, out)
    except Exception:
        pass
    return out


def _apply_lut_slot(rgb, path: str, strength: float):
    if not path or strength <= 0.0:
        return rgb
    try:
        from app.effect_node_params import LUTParams

        return LUTParams(path=path, strength=max(0.0, min(1.0, float(strength)))).apply(rgb)
    except Exception:
        return rgb


def apply_grade_stack(rgb, grades: list[ColorGrade | dict[str, Any] | None]):
    """Apply clip/group/timeline grades in order.

    The hierarchy is intentionally explicit: callers pass `[clip, group,
    timeline]` or any subset.  This keeps the color-page stack predictable and
    lets export QA verify the same order as preview.
    """
    out = rgb
    for raw in grades or []:
        if raw is None:
            continue
        grade = ColorGrade.from_dict(raw) if isinstance(raw, dict) else raw
        if isinstance(grade, ColorGrade):
            out = apply_to_rgb(out, grade)
    return out


def suggest_shot_match_grade(reference_rgb, target_rgb) -> ColorGrade:
    """Return a conservative grade that nudges target statistics to reference.

    This is not a full color-match engine, but it provides a deterministic core
    for a future UI button: exposure, contrast, and saturation are estimated
    from Rec.709 luma and chroma spread, then clamped to slider-safe ranges.
    """
    import numpy as np

    ref = reference_rgb.astype(np.float32) / 255.0
    tgt = target_rgb.astype(np.float32) / 255.0

    def stats(arr):
        luma = 0.2126 * arr[..., 0] + 0.7152 * arr[..., 1] + 0.0722 * arr[..., 2]
        sat = arr.max(axis=2) - arr.min(axis=2)
        return float(luma.mean()), float(luma.std()), float(sat.mean())

    ref_mean, ref_std, ref_sat = stats(ref)
    tgt_mean, tgt_std, tgt_sat = stats(tgt)
    brightness = int(round((ref_mean - tgt_mean) * 100.0))
    contrast = 0
    if tgt_std > 1e-4:
        contrast = int(round(((ref_std / tgt_std) - 1.0) * 100.0))
    saturation = 0
    if tgt_sat > 1e-4:
        saturation = int(round(((ref_sat / tgt_sat) - 1.0) * 100.0))
    return ColorGrade(
        brightness=max(-50, min(50, brightness)),
        contrast=max(-50, min(50, contrast)),
        saturation=max(-50, min(50, saturation)),
        preset_id="shot_match",
    )


def _apply_hue_vs_hue(f, points: list[tuple[float, float]]):
    """Rotate hues per the Hue-vs-Hue curve. ``f`` is a float32 RGB
    array in [0, 1]; ``points`` is a list of (input_hue 0..360,
    delta_hue -180..+180) control points. Linear interpolation
    around the wrap-around hue circle; if ``points`` is empty the
    function leaves ``f`` untouched."""
    import numpy as np
    if not points:
        return f
    # Convert RGB → HSV (vectorised — same algo Pillow uses).
    r = f[..., 0]; g = f[..., 1]; b = f[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin
    # Hue (0..360)
    h = np.zeros_like(cmax)
    mask = delta > 1e-6
    rmask = mask & (cmax == r)
    gmask = mask & (cmax == g) & ~rmask
    bmask = mask & (cmax == b) & ~rmask & ~gmask
    h[rmask] = ((g[rmask] - b[rmask]) / delta[rmask]) % 6.0
    h[gmask] = (b[gmask] - r[gmask]) / delta[gmask] + 2.0
    h[bmask] = (r[bmask] - g[bmask]) / delta[bmask] + 4.0
    h = h * 60.0   # 0..360
    s = np.where(cmax > 0, delta / np.maximum(cmax, 1e-6), 0.0)
    v = cmax

    # Build a 360-bin lookup of hue deltas. Sort points + add wrap.
    pts = sorted(points, key=lambda p: p[0])
    if len(pts) == 1:
        delta_arr = np.full(360, pts[0][1], dtype=np.float32)
    else:
        # Wrap: append (first.x + 360, first.y) for circular interp.
        ext = pts + [(pts[0][0] + 360.0, pts[0][1])]
        xs = np.array([p[0] for p in ext], dtype=np.float32)
        ys = np.array([p[1] for p in ext], dtype=np.float32)
        # Sample at 0..359 with wrap-aware linear interp.
        sample = np.arange(360, dtype=np.float32)
        # If sample < pts[0].x, shift it up by 360 so it falls into
        # the [pts[-1].x, pts[0].x+360] segment.
        sample_shifted = np.where(sample < pts[0][0], sample + 360.0, sample)
        delta_arr = np.interp(sample_shifted, xs, ys).astype(np.float32)

    # Apply per-pixel hue delta via lookup.
    h_idx = np.clip(h.astype(np.int32), 0, 359)
    h_new = (h + delta_arr[h_idx]) % 360.0

    # HSV → RGB (vectorised).
    h6 = h_new / 60.0
    i = np.floor(h6).astype(np.int32) % 6
    fpart = h6 - np.floor(h6)
    p = v * (1.0 - s)
    q = v * (1.0 - s * fpart)
    t = v * (1.0 - s * (1.0 - fpart))
    out = np.empty_like(f)
    # Stack by sector i.
    for sector in range(6):
        m = (i == sector)
        if not np.any(m):
            continue
        if sector == 0:
            out[..., 0][m] = v[m]; out[..., 1][m] = t[m]; out[..., 2][m] = p[m]
        elif sector == 1:
            out[..., 0][m] = q[m]; out[..., 1][m] = v[m]; out[..., 2][m] = p[m]
        elif sector == 2:
            out[..., 0][m] = p[m]; out[..., 1][m] = v[m]; out[..., 2][m] = t[m]
        elif sector == 3:
            out[..., 0][m] = p[m]; out[..., 1][m] = q[m]; out[..., 2][m] = v[m]
        elif sector == 4:
            out[..., 0][m] = t[m]; out[..., 1][m] = p[m]; out[..., 2][m] = v[m]
        else:
            out[..., 0][m] = v[m]; out[..., 1][m] = p[m]; out[..., 2][m] = q[m]
    return out


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
        or grade.offset_x != 0 or grade.offset_y != 0
    )
    if has_wheels:
        rs, gs, bs = _wheel_to_colorbalance(grade.shadows_x, grade.shadows_y)
        rm, gm, bm = _wheel_to_colorbalance(grade.midtones_x, grade.midtones_y)
        rh, gh, bh = _wheel_to_colorbalance(grade.highlights_x, grade.highlights_y)
        # Offset is a uniform shift — ffmpeg's colorbalance has no
        # global slot, so we add it into every tonal region. Visually
        # equivalent because the per-region masks sum to 1 across the
        # tonal range.
        ox, oy, oz = _wheel_to_colorbalance(grade.offset_x, grade.offset_y)
        rs += ox; gs += oy; bs += oz
        rm += ox; gm += oy; bm += oz
        rh += ox; gh += oy; bh += oz
        parts.append(
            "colorbalance="
            f"rs={rs:.4f}:gs={gs:.4f}:bs={bs:.4f}:"
            f"rm={rm:.4f}:gm={gm:.4f}:bm={bm:.4f}:"
            f"rh={rh:.4f}:gh={gh:.4f}:bh={bh:.4f}"
        )

    return ",".join(parts) if parts else None
