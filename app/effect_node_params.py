"""Effect node parameter dataclasses for the node graph.

Each class implements:
  apply(rgb: np.ndarray) -> np.ndarray   (uint8 H×W×3)
  is_identity() -> bool
  to_dict() -> dict
  from_dict(d) -> cls
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import numpy as np


# ── helpers ───────────────────────────────────────────────────────────────────

def _lut_from_points(pts: list[tuple[float, float]]) -> np.ndarray:
    """Build a 256-entry LUT from (x, y) control points via monotone cubic interp."""
    if len(pts) < 2:
        return np.arange(256, dtype=np.float32)
    pts = sorted(pts, key=lambda p: p[0])
    xs = np.array([p[0] for p in pts], dtype=np.float64)
    ys = np.array([p[1] for p in pts], dtype=np.float64)
    xi = np.linspace(0.0, 1.0, 256, dtype=np.float64)
    yi = np.interp(xi, xs, ys)
    return np.clip(yi * 255.0, 0, 255).astype(np.float32)


def _kelvin_to_rgb_scale(kelvin: int) -> tuple[float, float, float]:
    """Approximate Planckian locus as RGB multipliers (normalized to 1.0)."""
    k = max(1000, min(40000, kelvin)) / 100.0
    if k <= 66:
        r = 1.0
        g = max(0, min(1, (99.4708025861 * np.log(k) - 161.1195681661) / 255.0))
        b = 0.0 if k <= 19 else max(0, min(1, (138.5177312231 * np.log(k - 10) - 305.0447927307) / 255.0))
    else:
        r = max(0, min(1, 329.698727446 * (k - 60) ** -0.1332047592 / 255.0))
        g = max(0, min(1, 288.1221695283 * (k - 60) ** -0.0755148492 / 255.0))
        b = 1.0
    # Normalise to prevent any channel > 1
    m = max(r, g, b, 1e-6)
    return r / m, g / m, b / m


# ── Curves ────────────────────────────────────────────────────────────────────

@dataclass
class CurvesParams:
    master: list = field(default_factory=lambda: [[0.0, 0.0], [1.0, 1.0]])
    red:    list = field(default_factory=lambda: [[0.0, 0.0], [1.0, 1.0]])
    green:  list = field(default_factory=lambda: [[0.0, 0.0], [1.0, 1.0]])
    blue:   list = field(default_factory=lambda: [[0.0, 0.0], [1.0, 1.0]])

    def _is_identity_pts(self, pts: list) -> bool:
        return len(pts) == 2 and abs(pts[0][0]) < 1e-4 and abs(pts[0][1]) < 1e-4 \
               and abs(pts[1][0] - 1) < 1e-4 and abs(pts[1][1] - 1) < 1e-4

    def is_identity(self) -> bool:
        return all(self._is_identity_pts(p) for p in (self.master, self.red, self.green, self.blue))

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        m_lut = _lut_from_points(self.master)
        r_lut = _lut_from_points(self.red)
        g_lut = _lut_from_points(self.green)
        b_lut = _lut_from_points(self.blue)
        # Apply master to all channels, then per-channel
        idx = rgb.astype(np.uint8)
        out = np.empty_like(rgb)
        out[..., 0] = np.clip(r_lut[np.clip(m_lut[idx[..., 0]].astype(np.int32), 0, 255)], 0, 255)
        out[..., 1] = np.clip(g_lut[np.clip(m_lut[idx[..., 1]].astype(np.int32), 0, 255)], 0, 255)
        out[..., 2] = np.clip(b_lut[np.clip(m_lut[idx[..., 2]].astype(np.int32), 0, 255)], 0, 255)
        return out.astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "curves", "master": self.master,
                "red": self.red, "green": self.green, "blue": self.blue}

    @classmethod
    def from_dict(cls, d: dict) -> "CurvesParams":
        return cls(master=d.get("master", [[0,0],[1,1]]),
                   red=d.get("red", [[0,0],[1,1]]),
                   green=d.get("green", [[0,0],[1,1]]),
                   blue=d.get("blue", [[0,0],[1,1]]))


# ── Levels ────────────────────────────────────────────────────────────────────

@dataclass
class LevelsParams:
    in_black:  float = 0.0
    in_white:  float = 1.0
    gamma:     float = 1.0
    out_black: float = 0.0
    out_white: float = 1.0

    def is_identity(self) -> bool:
        return (abs(self.in_black) < 1e-4 and abs(self.in_white - 1) < 1e-4
                and abs(self.gamma - 1) < 1e-4
                and abs(self.out_black) < 1e-4 and abs(self.out_white - 1) < 1e-4)

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        f = rgb.astype(np.float32) / 255.0
        span = max(self.in_white - self.in_black, 1e-6)
        f = (f - self.in_black) / span
        f = np.clip(f, 0.0, 1.0)
        if abs(self.gamma - 1.0) > 1e-4:
            f = f ** (1.0 / max(self.gamma, 0.01))
        f = self.out_black + f * (self.out_white - self.out_black)
        return np.clip(f * 255.0, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "levels", "in_black": self.in_black, "in_white": self.in_white,
                "gamma": self.gamma, "out_black": self.out_black, "out_white": self.out_white}

    @classmethod
    def from_dict(cls, d: dict) -> "LevelsParams":
        return cls(in_black=float(d.get("in_black", 0)), in_white=float(d.get("in_white", 1)),
                   gamma=float(d.get("gamma", 1)), out_black=float(d.get("out_black", 0)),
                   out_white=float(d.get("out_white", 1)))


# ── Glow ──────────────────────────────────────────────────────────────────────

@dataclass
class GlowParams:
    threshold: float = 0.70   # 0-1, brightness threshold
    radius:    int   = 25     # blur radius in pixels
    intensity: float = 0.60   # 0-2, how much glow to add
    tint_r:    float = 1.0
    tint_g:    float = 1.0
    tint_b:    float = 1.0

    def is_identity(self) -> bool:
        return self.intensity <= 0.0

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        try:
            import cv2
        except ImportError:
            return rgb
        f = rgb.astype(np.float32) / 255.0
        lum = 0.2126 * f[..., 0] + 0.7152 * f[..., 1] + 0.0722 * f[..., 2]
        t = max(self.threshold, 0.01)
        mask = np.clip((lum - t) / (1.0 - t), 0.0, 1.0)[..., None]
        bright = f * mask
        ksize = max(3, self.radius * 2 + 1) | 1
        sigma = self.radius / 2.0
        blurred = cv2.GaussianBlur(bright, (ksize, ksize), sigma)
        if abs(self.tint_r - 1) > 0.01 or abs(self.tint_g - 1) > 0.01 or abs(self.tint_b - 1) > 0.01:
            blurred[..., 0] *= self.tint_r
            blurred[..., 1] *= self.tint_g
            blurred[..., 2] *= self.tint_b
        result = np.clip(f + blurred * self.intensity, 0.0, 1.0)
        return (result * 255.0).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "glow", "threshold": self.threshold, "radius": self.radius,
                "intensity": self.intensity, "tint_r": self.tint_r,
                "tint_g": self.tint_g, "tint_b": self.tint_b}

    @classmethod
    def from_dict(cls, d: dict) -> "GlowParams":
        return cls(threshold=float(d.get("threshold", 0.7)), radius=int(d.get("radius", 25)),
                   intensity=float(d.get("intensity", 0.6)),
                   tint_r=float(d.get("tint_r", 1)), tint_g=float(d.get("tint_g", 1)),
                   tint_b=float(d.get("tint_b", 1)))


# ── Film Grain ────────────────────────────────────────────────────────────────

@dataclass
class FilmGrainParams:
    amount:   float = 0.05    # 0-0.3, noise strength
    monochrome: bool = True   # True = grey grain, False = colour grain
    size:     float = 1.0     # grain scale multiplier

    def is_identity(self) -> bool:
        return self.amount <= 0.0

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        h, w = rgb.shape[:2]
        rng = np.random.default_rng()
        if self.monochrome:
            noise = rng.standard_normal((h, w, 1), dtype=np.float32 if hasattr(rng.standard_normal, '__call__') else None)
            if noise is None:
                noise = rng.standard_normal((h, w, 1)).astype(np.float32)
            noise = np.repeat(noise, 3, axis=2)
        else:
            noise = rng.standard_normal((h, w, 3)).astype(np.float32)
        if self.size > 1.1:
            try:
                import cv2
                s = max(3, int(self.size) * 2 + 1) | 1
                noise = cv2.GaussianBlur(noise, (s, s), self.size / 2)
            except Exception:
                pass
        result = rgb.astype(np.float32) + noise * (self.amount * 255.0)
        return np.clip(result, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "filmgrain", "amount": self.amount,
                "monochrome": self.monochrome, "size": self.size}

    @classmethod
    def from_dict(cls, d: dict) -> "FilmGrainParams":
        return cls(amount=float(d.get("amount", 0.05)),
                   monochrome=bool(d.get("monochrome", True)),
                   size=float(d.get("size", 1.0)))


# ── Vignette ──────────────────────────────────────────────────────────────────

@dataclass
class VignetteParams:
    amount:   float = 0.50    # 0-1, darkness at edge
    size:     float = 0.80    # 0-1, radius where vignette begins
    feather:  float = 0.60    # 0-1, softness of the falloff
    round:    float = 1.0     # 0=square, 1=circular

    def is_identity(self) -> bool:
        return self.amount <= 0.0

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        h, w = rgb.shape[:2]
        cy, cx = h / 2.0, w / 2.0
        y_idx = np.arange(h, dtype=np.float32)
        x_idx = np.arange(w, dtype=np.float32)
        yy, xx = np.meshgrid(y_idx, x_idx, indexing="ij")
        dy = (yy - cy) / (h / 2.0)
        dx = (xx - cx) / (w / 2.0)
        p = max(self.round * 2.0, 0.1)
        dist = (np.abs(dx) ** p + np.abs(dy) ** p) ** (1.0 / p)
        feather_range = max(1.0 - self.size, 1e-3)
        t = np.clip((dist - self.size) / feather_range, 0.0, 1.0)
        # Smoothstep
        t = t * t * (3.0 - 2.0 * t)
        vign = 1.0 - t * self.amount * self.feather
        return np.clip(rgb.astype(np.float32) * vign[..., None], 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "vignette", "amount": self.amount, "size": self.size,
                "feather": self.feather, "round": self.round}

    @classmethod
    def from_dict(cls, d: dict) -> "VignetteParams":
        return cls(amount=float(d.get("amount", 0.5)), size=float(d.get("size", 0.8)),
                   feather=float(d.get("feather", 0.6)), round=float(d.get("round", 1.0)))


# ── LUT ───────────────────────────────────────────────────────────────────────

@dataclass
class LUTParams:
    path:     str   = ""      # .cube file path
    strength: float = 1.0     # 0-1 blend with original

    def is_identity(self) -> bool:
        return not self.path or self.strength <= 0.0

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        try:
            lut3d, size = self._load_cube()
            if lut3d is None:
                return rgb
            result = self._apply_lut(rgb, lut3d, size)
            if self.strength < 1.0:
                a = self.strength
                result = np.clip(a * result.astype(np.float32) + (1 - a) * rgb.astype(np.float32), 0, 255).astype(np.uint8)
            return result
        except Exception:
            return rgb

    def _load_cube(self):
        import os
        if not os.path.exists(self.path):
            return None, 0
        size = 33
        data = []
        with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("LUT_3D_SIZE"):
                    size = int(line.split()[-1])
                elif line and not line.startswith("#") and not line[0].isalpha():
                    parts = line.split()
                    if len(parts) == 3:
                        data.append([float(x) for x in parts])
        if not data:
            return None, 0
        lut = np.array(data, dtype=np.float32).reshape(size, size, size, 3)
        return lut, size

    def _apply_lut(self, rgb: np.ndarray, lut3d, size: int) -> np.ndarray:
        f = np.clip(rgb.astype(np.float32) / 255.0, 0.0, 1.0)
        scale = (size - 1)
        ri = np.clip(f[..., 0] * scale, 0, size - 1)
        gi = np.clip(f[..., 1] * scale, 0, size - 1)
        bi = np.clip(f[..., 2] * scale, 0, size - 1)
        r0 = ri.astype(np.int32); r1 = np.minimum(r0 + 1, size - 1)
        g0 = gi.astype(np.int32); g1 = np.minimum(g0 + 1, size - 1)
        b0 = bi.astype(np.int32); b1 = np.minimum(b0 + 1, size - 1)
        fr = (ri - r0)[..., None]; fg = (gi - g0)[..., None]; fb = (bi - b0)[..., None]
        c000 = lut3d[r0, g0, b0]; c100 = lut3d[r1, g0, b0]
        c010 = lut3d[r0, g1, b0]; c110 = lut3d[r1, g1, b0]
        c001 = lut3d[r0, g0, b1]; c101 = lut3d[r1, g0, b1]
        c011 = lut3d[r0, g1, b1]; c111 = lut3d[r1, g1, b1]
        out = (c000*(1-fr)*(1-fg)*(1-fb) + c100*fr*(1-fg)*(1-fb) +
               c010*(1-fr)*fg*(1-fb)    + c110*fr*fg*(1-fb) +
               c001*(1-fr)*(1-fg)*fb    + c101*fr*(1-fg)*fb +
               c011*(1-fr)*fg*fb        + c111*fr*fg*fb)
        return np.clip(out * 255.0, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "lut", "path": self.path, "strength": self.strength}

    @classmethod
    def from_dict(cls, d: dict) -> "LUTParams":
        return cls(path=str(d.get("path", "")), strength=float(d.get("strength", 1.0)))


# ── White Balance ─────────────────────────────────────────────────────────────

@dataclass
class WhiteBalanceParams:
    temperature: int = 6500   # 2000-12000 Kelvin
    tint:        int = 0      # -100=green, +100=magenta

    def is_identity(self) -> bool:
        return abs(self.temperature - 6500) < 10 and abs(self.tint) < 1

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        sr, sg, sb = _kelvin_to_rgb_scale(self.temperature)
        # tint shifts green vs magenta
        tint_factor = self.tint / 100.0
        sg = sg * (1.0 - abs(tint_factor) * 0.3) if tint_factor > 0 else sg * (1.0 + abs(tint_factor) * 0.1)
        sr = sr * (1.0 + abs(tint_factor) * 0.1) if tint_factor > 0 else sr
        sb = sb * (1.0 + abs(tint_factor) * 0.1) if tint_factor > 0 else sb
        f = rgb.astype(np.float32)
        f[..., 0] = np.clip(f[..., 0] * sr, 0, 255)
        f[..., 1] = np.clip(f[..., 1] * sg, 0, 255)
        f[..., 2] = np.clip(f[..., 2] * sb, 0, 255)
        return f.astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "whitebalance", "temperature": self.temperature, "tint": self.tint}

    @classmethod
    def from_dict(cls, d: dict) -> "WhiteBalanceParams":
        return cls(temperature=int(d.get("temperature", 6500)), tint=int(d.get("tint", 0)))


# ── Unsharp Mask ──────────────────────────────────────────────────────────────

@dataclass
class UnsharpMaskParams:
    amount:    float = 0.80    # 0-3 sharpening strength
    radius:    int   = 5       # blur radius
    threshold: int   = 0       # 0-255, min edge difference

    def is_identity(self) -> bool:
        return self.amount <= 0.0

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        try:
            import cv2
            ksize = max(3, self.radius * 2 + 1) | 1
            blurred = cv2.GaussianBlur(rgb, (ksize, ksize), self.radius / 2.0)
        except ImportError:
            return rgb
        diff = rgb.astype(np.float32) - blurred.astype(np.float32)
        if self.threshold > 0:
            diff = np.where(np.abs(diff) >= self.threshold, diff, 0.0)
        sharpened = rgb.astype(np.float32) + diff * self.amount
        return np.clip(sharpened, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "unsharpmask", "amount": self.amount,
                "radius": self.radius, "threshold": self.threshold}

    @classmethod
    def from_dict(cls, d: dict) -> "UnsharpMaskParams":
        return cls(amount=float(d.get("amount", 0.8)), radius=int(d.get("radius", 5)),
                   threshold=int(d.get("threshold", 0)))


# ── Pixelate ──────────────────────────────────────────────────────────────────

@dataclass
class PixelateParams:
    block_size: int = 20      # pixel block size

    def is_identity(self) -> bool:
        return self.block_size <= 1

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        try:
            import cv2
            h, w = rgb.shape[:2]
            sw = max(1, w // self.block_size)
            sh = max(1, h // self.block_size)
            small = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_LINEAR)
            return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        except ImportError:
            return rgb

    def to_dict(self) -> dict:
        return {"kind": "pixelate", "block_size": self.block_size}

    @classmethod
    def from_dict(cls, d: dict) -> "PixelateParams":
        return cls(block_size=int(d.get("block_size", 20)))


# ── Channel Mixer ─────────────────────────────────────────────────────────────

@dataclass
class ChannelMixerParams:
    # Output channel = in_R*xx + in_G*xy + in_B*xz + constant*xc
    rr: float = 1.0; rg: float = 0.0; rb: float = 0.0; rc: float = 0.0
    gr: float = 0.0; gg: float = 1.0; gb: float = 0.0; gc: float = 0.0
    br: float = 0.0; bg: float = 0.0; bb: float = 1.0; bc: float = 0.0

    def is_identity(self) -> bool:
        eps = 1e-4
        return (abs(self.rr-1)<eps and abs(self.rg)<eps and abs(self.rb)<eps and abs(self.rc)<eps and
                abs(self.gr)<eps and abs(self.gg-1)<eps and abs(self.gb)<eps and abs(self.gc)<eps and
                abs(self.br)<eps and abs(self.bg)<eps and abs(self.bb-1)<eps and abs(self.bc)<eps)

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        if self.is_identity():
            return rgb
        f = rgb.astype(np.float32)
        R, G, B = f[..., 0], f[..., 1], f[..., 2]
        out = np.empty_like(f)
        out[..., 0] = R*self.rr + G*self.rg + B*self.rb + self.rc*255
        out[..., 1] = R*self.gr + G*self.gg + B*self.gb + self.gc*255
        out[..., 2] = R*self.br + G*self.bg + B*self.bb + self.bc*255
        return np.clip(out, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {"kind": "channelmixer",
                "rr": self.rr, "rg": self.rg, "rb": self.rb, "rc": self.rc,
                "gr": self.gr, "gg": self.gg, "gb": self.gb, "gc": self.gc,
                "br": self.br, "bg": self.bg, "bb": self.bb, "bc": self.bc}

    @classmethod
    def from_dict(cls, d: dict) -> "ChannelMixerParams":
        return cls(**{k: float(d.get(k, v)) for k, v in {
            "rr":1,"rg":0,"rb":0,"rc":0,"gr":0,"gg":1,"gb":0,"gc":0,"br":0,"bg":0,"bb":1,"bc":0}.items()})


# ── Registry ──────────────────────────────────────────────────────────────────

@dataclass
class SDRHDRUpmapParams:
    """Workbench job node for SDR -> HDR/EXR conversion."""

    peak_nits: int = 1000
    exposure_stops: float = 0.0
    highlight_boost: float = 1.35
    saturation_boost: float = 1.08
    curve_gamma: float = 0.85
    max_frames: int = 0
    output_pattern: str = "frame_%06d.exr"

    def is_identity(self) -> bool:
        return True

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        return rgb

    def to_profile_dict(self) -> dict:
        return {
            "mode": "local_inverse_tone_map",
            "target": "scene_linear_exr",
            "peak_nits": int(self.peak_nits),
            "exposure_stops": float(self.exposure_stops),
            "highlight_boost": float(self.highlight_boost),
            "saturation_boost": float(self.saturation_boost),
            "curve_gamma": float(self.curve_gamma),
            "max_frames": int(self.max_frames),
            "output_pattern": str(self.output_pattern),
        }

    def to_node_payload(self) -> dict:
        from app.sdr_hdr_upmap import ltx_hdr_provider_state

        return {
            "kind": "sdr_hdr_upmap",
            "label": "SDR -> HDR EXR",
            "profile": self.to_profile_dict(),
            "provider": ltx_hdr_provider_state(),
            "preview_behavior": "pass_through",
            "execution": "tools/convert_sdr_to_hdr_exr.py",
            "claim_level": "ltx_style_hdr_exr_foundation_not_neural_ltx_parity",
        }

    def to_dict(self) -> dict:
        out = self.to_profile_dict()
        out["kind"] = "sdr_hdr_upmap"
        return out

    @classmethod
    def from_dict(cls, d: dict) -> "SDRHDRUpmapParams":
        return cls(
            peak_nits=max(100, int(d.get("peak_nits", 1000) or 1000)),
            exposure_stops=float(d.get("exposure_stops", 0.0) or 0.0),
            highlight_boost=max(0.25, min(8.0, float(d.get("highlight_boost", 1.35) or 1.35))),
            saturation_boost=max(0.0, min(3.0, float(d.get("saturation_boost", 1.08) or 1.08))),
            curve_gamma=max(0.2, min(3.0, float(d.get("curve_gamma", 0.85) or 0.85))),
            max_frames=max(0, int(d.get("max_frames", 0) or 0)),
            output_pattern=str(d.get("output_pattern", "frame_%06d.exr") or "frame_%06d.exr"),
        )


_KIND_TO_CLASS = {
    "curves":       CurvesParams,
    "levels":       LevelsParams,
    "glow":         GlowParams,
    "filmgrain":    FilmGrainParams,
    "vignette":     VignetteParams,
    "lut":          LUTParams,
    "whitebalance": WhiteBalanceParams,
    "unsharpmask":  UnsharpMaskParams,
    "pixelate":     PixelateParams,
    "channelmixer": ChannelMixerParams,
    "sdr_hdr_upmap": SDRHDRUpmapParams,
}

_KIND_META = {
    #  kind            label           color     shortcut
    "curves":       ("커브",          "#4CAF50", "Alt+V"),
    "levels":       ("레벨",          "#8BC34A", "Alt+L"),
    "glow":         ("글로우",         "#FFC107", "Alt+G"),
    "filmgrain":    ("필름 그레인",    "#FF9800", None),
    "vignette":     ("비네팅",         "#FF5722", None),
    "lut":          ("LUT",            "#9C27B0", None),
    "whitebalance": ("화이트 밸런스",  "#03A9F4", None),
    "unsharpmask":  ("선명도",         "#009688", None),
    "pixelate":     ("픽셀화",         "#3F51B5", None),
    "channelmixer": ("채널 믹서",      "#E91E63", None),
}

_KIND_META["sdr_hdr_upmap"] = ("SDR -> HDR EXR", "#54D7FF", None)


def params_from_dict(d: dict):
    kind = d.get("kind", "")
    cls = _KIND_TO_CLASS.get(kind)
    return cls.from_dict(d) if cls else None
