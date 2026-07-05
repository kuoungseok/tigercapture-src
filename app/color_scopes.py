"""Video scopes — Histogram / Parade / Waveform / Vectorscope.

Each ``compute_*`` function takes an RGB uint8 ndarray (the same image
shape used by :mod:`app.project_player`) and returns a uint8 RGB
ndarray sized to the requested ``out_w × out_h``. The renderer in
:class:`app.video_editor_window.ScopesPanel` flips that to a QImage.

The scope formulas mirror what DaVinci Resolve documents for its own
panels — the goal is "looks like Resolve, reads like Resolve" rather
than analytic perfection. They're a feedback aid, not a measurement
instrument.

Performance budget: every scope must run in <8 ms on a 1080p frame so
the preview thread can keep up with playback. We achieve that with
``np.histogram`` / ``np.add.at`` accumulators rather than per-pixel
loops, and we down-sample large frames before the heavy steps.
"""
from __future__ import annotations

from typing import Literal

import numpy as np


# Output canvas size for every scope. Wider scopes (parade, waveform)
# use the full width; histogram + vectorscope are square-ish and pad.
DEFAULT_OUT_W = 320
DEFAULT_OUT_H = 200


# Background colour shared across scopes — near-black with a faint blue
# tint so it reads as "monitor" rather than "void".
_BG = (10, 10, 10)


def _new_canvas(out_w: int, out_h: int) -> np.ndarray:
    """Allocate a fresh RGB canvas filled with the scope background."""
    canvas = np.empty((out_h, out_w, 3), dtype=np.uint8)
    canvas[..., 0] = _BG[0]
    canvas[..., 1] = _BG[1]
    canvas[..., 2] = _BG[2]
    return canvas


def _downsample(rgb: np.ndarray, max_pixels: int = 320 * 180) -> np.ndarray:
    """Strided down-sample so the heaviest scope never sees a full
    1080p frame. The visual look at 320×180 is identical for these
    distribution-style displays."""
    h, w = rgb.shape[:2]
    pix = h * w
    if pix <= max_pixels:
        return rgb
    factor = int(np.ceil(np.sqrt(pix / max_pixels)))
    return rgb[::factor, ::factor]


# ---------------------------------------------------------------------------
#  Histogram — 256-bin RGB triple-line plot
# ---------------------------------------------------------------------------


def compute_histogram(rgb: np.ndarray, out_w: int = DEFAULT_OUT_W,
                      out_h: int = DEFAULT_OUT_H) -> np.ndarray:
    """RGB histogram (3 overlaid line plots, each 256 bins).

    Y axis: log-ish frequency, normalised so the busiest bin sits at
    ~85% of the canvas height (leaves a top margin so peaks don't
    clip into the frame).
    """
    canvas = _new_canvas(out_w, out_h)
    src = _downsample(rgb)

    bins = 256
    # Per-channel hists (uint64 → fits any 4K frame easily)
    hr, _ = np.histogram(src[..., 0], bins=bins, range=(0, 256))
    hg, _ = np.histogram(src[..., 1], bins=bins, range=(0, 256))
    hb, _ = np.histogram(src[..., 2], bins=bins, range=(0, 256))

    # Log-scale + normalise so peaks reach ~85% of height.
    def _norm(h: np.ndarray) -> np.ndarray:
        h = np.log1p(h.astype(np.float32))
        peak = float(h.max()) if h.size else 0.0
        if peak <= 0:
            return np.zeros_like(h)
        return h / peak * (out_h * 0.85)

    nr = _norm(hr)
    ng = _norm(hg)
    nb = _norm(hb)

    # X axis maps bin (0..255) → out_w
    xs = np.linspace(0, out_w - 1, bins).astype(np.int32)

    # Render with additive blending so overlapping channels brighten
    # toward white — the canonical RGB hist look.
    accum = canvas.astype(np.uint16)
    _line_plot(accum, xs, nr, (240, 80, 80), out_h)     # red
    _line_plot(accum, xs, ng, (80, 220, 80), out_h)     # green
    _line_plot(accum, xs, nb, (80, 130, 240), out_h)    # blue

    np.clip(accum, 0, 255, out=accum)
    canvas[:] = accum.astype(np.uint8)
    return canvas


def _line_plot(canvas: np.ndarray, xs: np.ndarray, ys: np.ndarray,
               color: tuple[int, int, int], out_h: int) -> None:
    """Add a coloured line into ``canvas`` (uint16 in-place add).
    Each (xs[i], ys[i]) is a column where we light up the pixels from
    the bottom up to height ys[i]. We additively blend so overlapping
    channels converge to white."""
    yi = (out_h - 1 - ys).astype(np.int32)
    yi = np.clip(yi, 0, out_h - 1)
    # Columns: from yi[i] to bottom for each x.
    for i, xi in enumerate(xs):
        canvas[yi[i]:, xi, 0] += color[0] // 2
        canvas[yi[i]:, xi, 1] += color[1] // 2
        canvas[yi[i]:, xi, 2] += color[2] // 2


# ---------------------------------------------------------------------------
#  Parade — three vertical RGB columns, brightness vs x
# ---------------------------------------------------------------------------


def compute_parade(rgb: np.ndarray, out_w: int = DEFAULT_OUT_W,
                   out_h: int = DEFAULT_OUT_H) -> np.ndarray:
    """RGB parade — three side-by-side panels (R, G, B) where each
    column shows the distribution of brightness for that channel at
    the corresponding column of the source frame. Used for matching
    channel levels and white-balancing."""
    canvas = _new_canvas(out_w, out_h)
    src = _downsample(rgb)

    panel_w = out_w // 3
    for i, channel_color in enumerate((
        (255, 100, 100),    # R
        (100, 230, 100),    # G
        (100, 160, 240),    # B
    )):
        chan = src[..., i]                     # H × W
        _draw_column_dist(
            canvas, chan, channel_color,
            x_start=panel_w * i, x_end=panel_w * (i + 1),
            out_h=out_h,
        )
    return canvas


def _draw_column_dist(canvas: np.ndarray, chan: np.ndarray,
                      color: tuple[int, int, int],
                      x_start: int, x_end: int, out_h: int) -> None:
    """For each output column in [x_start, x_end), summarise the
    per-pixel distribution of ``chan`` at the corresponding source
    column band as a vertical brightness profile.

    Implementation: bin the (column, value) pairs into a 2D histogram
    of shape (panel_w, out_h), then write the log-scaled count back
    onto the canvas."""
    h, w = chan.shape
    panel_w = x_end - x_start
    if panel_w <= 0 or w == 0 or h == 0:
        return
    # Map each source column to a panel column.
    src_x_per_panel = w / panel_w

    # Collapse into a 2D hist: rows = value bins (out_h), cols = panel x.
    # We do this with np.add.at on a flat index — fast even for 4K.
    val_bins = out_h
    # For every source pixel (x, y), compute its panel column and value
    # bucket. Vectorise across the whole frame.
    yy, xx = np.indices(chan.shape, dtype=np.int32)
    panel_x = (xx / src_x_per_panel).astype(np.int32)
    panel_x = np.clip(panel_x, 0, panel_w - 1)
    val_bin = (chan.astype(np.int32) * (val_bins - 1) // 255)
    val_bin = val_bins - 1 - val_bin   # invert so 0 brightness = bottom row
    flat_idx = val_bin * panel_w + panel_x
    accum = np.bincount(flat_idx.ravel(),
                        minlength=panel_w * val_bins).reshape(val_bins, panel_w)
    accum = np.log1p(accum.astype(np.float32))
    peak = float(accum.max()) if accum.size else 0.0
    if peak > 0:
        accum = accum / peak

    # Apply the channel colour with intensity = accum.
    cr, cg, cb = color
    out = np.empty((val_bins, panel_w, 3), dtype=np.uint16)
    out[..., 0] = (cr * accum).astype(np.uint16) + _BG[0]
    out[..., 1] = (cg * accum).astype(np.uint16) + _BG[1]
    out[..., 2] = (cb * accum).astype(np.uint16) + _BG[2]
    np.clip(out, 0, 255, out=out)
    canvas[:val_bins, x_start:x_end] = out.astype(np.uint8)


# ---------------------------------------------------------------------------
#  Waveform — luminance distribution per output column
# ---------------------------------------------------------------------------


def compute_waveform(rgb: np.ndarray, out_w: int = DEFAULT_OUT_W,
                     out_h: int = DEFAULT_OUT_H) -> np.ndarray:
    """Luma-only waveform: one panel where each x maps to a column
    of the source frame, y maps to luminance, and intensity shows the
    pixel count at that (x, luma) bin. The exposure-monitoring scope."""
    canvas = _new_canvas(out_w, out_h)
    src = _downsample(rgb).astype(np.float32)
    luma = (0.2126 * src[..., 0]
            + 0.7152 * src[..., 1]
            + 0.0722 * src[..., 2]).astype(np.uint8)
    _draw_column_dist(canvas, luma, (235, 235, 240),
                      x_start=0, x_end=out_w, out_h=out_h)
    return canvas


# ---------------------------------------------------------------------------
#  Vectorscope — chroma distribution on a polar plot
# ---------------------------------------------------------------------------


def compute_vectorscope(rgb: np.ndarray, out_w: int = DEFAULT_OUT_W,
                        out_h: int = DEFAULT_OUT_H) -> np.ndarray:
    """Vectorscope — projects each pixel into the YUV (or YCbCr) chroma
    plane and accumulates a heat-map of where the colours land. Centre
    = grey; angle = hue; distance = saturation. Reference points for
    R/G/B/Y/Cy/Mg sit at 75 % saturation around the rim."""
    canvas = _new_canvas(out_w, out_h)
    src = _downsample(rgb).astype(np.float32) / 255.0
    R = src[..., 0]
    G = src[..., 1]
    B = src[..., 2]
    # Rec. 601 Y'CbCr (BT.601) — closest to what NTSC scopes display.
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cb = (B - Y) * 0.564
    Cr = (R - Y) * 0.713
    # Map (Cb, Cr) ∈ ~[-0.5, 0.5] to canvas centre + radius.
    side = min(out_w, out_h)
    cx = out_w / 2.0
    cy = out_h / 2.0
    radius = (side / 2.0) - 6.0
    px = (cx + Cb * 2.0 * radius).astype(np.int32)
    py = (cy - Cr * 2.0 * radius).astype(np.int32)
    px = np.clip(px, 0, out_w - 1)
    py = np.clip(py, 0, out_h - 1)
    # Accumulate a 2D hist via bincount.
    flat = py.ravel() * out_w + px.ravel()
    accum = np.bincount(flat, minlength=out_w * out_h).reshape(out_h, out_w)
    accum = np.log1p(accum.astype(np.float32))
    peak = float(accum.max()) if accum.size else 0.0
    if peak > 0:
        accum = accum / peak
    # Use a yellow-green tint that reads well on dark backgrounds.
    canvas_f = canvas.astype(np.float32)
    canvas_f[..., 0] += accum * 200
    canvas_f[..., 1] += accum * 230
    canvas_f[..., 2] += accum * 80
    np.clip(canvas_f, 0, 255, out=canvas_f)
    canvas[:] = canvas_f.astype(np.uint8)

    # Draw the rim circle so users get a frame of reference.
    yy, xx = np.indices((out_h, out_w))
    rim = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    on_rim = (rim >= radius - 1) & (rim <= radius + 1)
    canvas[on_rim] = (90, 90, 100)

    # Centre cross.
    cx_i = int(cx)
    cy_i = int(cy)
    canvas[cy_i, cx_i - 6:cx_i + 6] = (140, 140, 150)
    canvas[cy_i - 6:cy_i + 6, cx_i] = (140, 140, 150)
    return canvas


# ---------------------------------------------------------------------------
#  Dispatch
# ---------------------------------------------------------------------------


ScopeKind = Literal["histogram", "parade", "waveform", "vectorscope"]


def render_scope(kind: ScopeKind, rgb: np.ndarray,
                 out_w: int = DEFAULT_OUT_W,
                 out_h: int = DEFAULT_OUT_H) -> np.ndarray:
    if kind == "histogram":
        return compute_histogram(rgb, out_w, out_h)
    if kind == "parade":
        return compute_parade(rgb, out_w, out_h)
    if kind == "waveform":
        return compute_waveform(rgb, out_w, out_h)
    if kind == "vectorscope":
        return compute_vectorscope(rgb, out_w, out_h)
    return _new_canvas(out_w, out_h)


def scope_quality_diagnostics(rgb: np.ndarray, color_management: dict | None = None) -> dict:
    """Return numeric scope warnings for UI badges and export QA.

    This is intentionally compact: values map directly to what a colorist checks
    first in commercial scopes: luma range, clipping, chroma intensity, HDR
    peak estimate, and whether the frame is flirting with gamut/legal limits.
    """
    arr = rgb.astype(np.float32)
    if arr.size == 0:
        return {
            "ok": True,
            "warnings": [],
            "luma_ire_p01": 0.0,
            "luma_ire_p50": 0.0,
            "luma_ire_p99": 0.0,
            "channel_clip_ratio": 0.0,
            "saturation_mean": 0.0,
            "saturation_p95": 0.0,
        }
    f = np.clip(arr / 255.0, 0.0, 1.0)
    luma = 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]
    saturation = f.max(axis=2) - f.min(axis=2)
    channel_clip = np.mean((rgb <= 0) | (rgb >= 255))
    luma_ire = luma * 100.0
    warnings: list[str] = []
    p01 = float(np.percentile(luma_ire, 1))
    p50 = float(np.percentile(luma_ire, 50))
    p99 = float(np.percentile(luma_ire, 99))
    sat_mean = float(np.mean(saturation))
    sat_p95 = float(np.percentile(saturation, 95))
    if p01 <= 0.5:
        warnings.append("shadow clipping")
    if p99 >= 99.5:
        warnings.append("highlight clipping")
    if float(channel_clip) > 0.01:
        warnings.append("channel clipping")
    if sat_p95 > 0.92:
        warnings.append("high saturation / gamut risk")

    hdr = False
    if color_management:
        try:
            from app.color_management import ColorManagementSettings

            hdr = ColorManagementSettings.from_dict(color_management).is_hdr()
        except Exception:
            hdr = False
    nits_p99 = float(p99 / 100.0 * (1000.0 if hdr else 100.0))
    if hdr and nits_p99 > 900.0:
        warnings.append("HDR peak near 1000 nits")

    # YCbCr angle near the vectorscope skin-tone line. Useful as a QA hint,
    # not as an automatic grade.
    R, G, B = f[..., 0], f[..., 1], f[..., 2]
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    cb = (B - Y) * 0.564
    cr = (R - Y) * 0.713
    chroma_mask = saturation > 0.08
    if np.any(chroma_mask):
        skin_angle = float(np.degrees(np.arctan2(cr[chroma_mask].mean(), cb[chroma_mask].mean())))
    else:
        skin_angle = 0.0

    return {
        "ok": not warnings,
        "warnings": warnings,
        "luma_ire_p01": p01,
        "luma_ire_p50": p50,
        "luma_ire_p99": p99,
        "nits_p99": nits_p99,
        "channel_clip_ratio": float(channel_clip),
        "saturation_mean": sat_mean,
        "saturation_p95": sat_p95,
        "skin_tone_angle_deg": skin_angle,
    }
