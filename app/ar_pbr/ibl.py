"""Shared image-based lighting helpers for AR/PBR render paths.

The packet exporter, model-view helper, and GL preview should agree on the
same IBL contract: scene-linear environment samples, diffuse irradiance,
roughness-prefiltered specular, and a split-sum BRDF LUT.  This module keeps
that CPU-side representation deterministic and cacheable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
from typing import Any

import numpy as np

from app.ar_pbr.hdr import load_radiance_hdr


IBL_SCHEMA = "tigerstudio.ar_pbr.ibl_probe.v1"
DEFAULT_FALLBACK_RGB = (0.26, 0.30, 0.38)

_IBL_PROBE_CACHE: dict[tuple[Any, ...], "IBLProbe"] = {}
_BRDF_LUT_CACHE: dict[tuple[int, int], np.ndarray] = {}


@dataclass(frozen=True)
class IBLProbe:
    path: str
    environment: np.ndarray
    irradiance_map: np.ndarray
    prefiltered_levels: tuple[np.ndarray, ...]
    brdf_lut: np.ndarray
    average_rgb: tuple[float, float, float]
    source_max_luminance: float

    @property
    def available(self) -> bool:
        return self.environment.size > 0 and len(self.prefiltered_levels) > 0

    @property
    def prefilter_level_count(self) -> int:
        return len(self.prefiltered_levels)

    def diagnostics(self) -> dict[str, Any]:
        env_h, env_w = self.environment.shape[:2]
        irr_h, irr_w = self.irradiance_map.shape[:2]
        lut_h, lut_w = self.brdf_lut.shape[:2]
        return {
            "schema": IBL_SCHEMA,
            "path": self.path,
            "available": self.available,
            "environment_resolution": [int(env_w), int(env_h)],
            "irradiance_resolution": [int(irr_w), int(irr_h)],
            "prefilter_level_count": int(self.prefilter_level_count),
            "brdf_lut_resolution": [int(lut_w), int(lut_h)],
            "source_max_luminance": float(self.source_max_luminance),
            "average_rgb": [float(v) for v in self.average_rgb],
        }

    def sample_irradiance(self, dx: Any, dy: Any, dz: Any):
        return sample_equirect(self.irradiance_map, dx, dy, dz)

    def sample_prefiltered(self, dx: Any, dy: Any, dz: Any, roughness: Any):
        return sample_prefilter_levels(self.prefiltered_levels, dx, dy, dz, roughness)

    def sample_brdf(self, ndotv: Any, roughness: Any):
        return sample_brdf_lut(self.brdf_lut, ndotv, roughness)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722


def tonemap_aces(rgb: Any) -> np.ndarray:
    arr = np.maximum(np.asarray(rgb, dtype=np.float32), 0.0)
    return np.clip((arr * (2.51 * arr + 0.03)) / (arr * (2.43 * arr + 0.59) + 0.14), 0.0, 1.0)


def direction_to_equirect_uv(dx: Any, dy: Any, dz: Any) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(dx, dtype=np.float32)
    y = np.asarray(dy, dtype=np.float32)
    z = np.asarray(dz, dtype=np.float32)
    length = np.maximum(np.sqrt(x * x + y * y + z * z), 1.0e-6)
    sx = x / length
    sy = y / length
    sz = z / length
    u = (np.arctan2(sz, sx) / (2.0 * np.pi) + 0.5) % 1.0
    v = np.arccos(np.clip(sy, -1.0, 1.0)) / np.pi
    return u, v


def sample_equirect(image: Any, dx: Any, dy: Any, dz: Any):
    arr = np.asarray(image, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] < 3 or arr.size <= 0:
        return None
    h, w = int(arr.shape[0]), int(arr.shape[1])
    if h <= 0 or w <= 0:
        return None
    u, v = direction_to_equirect_uv(dx, dy, dz)
    x = np.asarray(u, dtype=np.float32) * max(1, w - 1)
    y = np.asarray(v, dtype=np.float32) * max(1, h - 1)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, max(0, w - 1))
    y1 = np.clip(y0 + 1, 0, max(0, h - 1))
    x0 = np.clip(x0, 0, max(0, w - 1))
    y0 = np.clip(y0, 0, max(0, h - 1))
    tx = (x - x0)[..., None]
    ty = (y - y0)[..., None]
    c00 = arr[y0, x0, :3]
    c10 = arr[y0, x1, :3]
    c01 = arr[y1, x0, :3]
    c11 = arr[y1, x1, :3]
    top = c00 * (1.0 - tx) + c10 * tx
    bottom = c01 * (1.0 - tx) + c11 * tx
    return np.ascontiguousarray(top * (1.0 - ty) + bottom * ty, dtype=np.float32)


def _downsample_level(arr: np.ndarray) -> np.ndarray | None:
    src = np.asarray(arr, dtype=np.float32)
    if src.ndim != 3 or src.shape[2] < 3:
        return None
    h, w = int(src.shape[0]), int(src.shape[1])
    if h <= 1 and w <= 1:
        return None
    h2 = max(1, h // 2)
    w2 = max(1, w // 2)
    cropped = src[: h2 * 2, : w2 * 2, :3]
    if cropped.shape[0] < h2 * 2 or cropped.shape[1] < w2 * 2:
        pad_h = max(0, h2 * 2 - cropped.shape[0])
        pad_w = max(0, w2 * 2 - cropped.shape[1])
        cropped = np.pad(cropped, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
    return np.ascontiguousarray(cropped.reshape(h2, 2, w2, 2, 3).mean(axis=(1, 3)), dtype=np.float32)


def build_prefilter_levels(environment: np.ndarray, *, max_levels: int = 7) -> tuple[np.ndarray, ...]:
    base = np.ascontiguousarray(np.asarray(environment, dtype=np.float32)[:, :, :3], dtype=np.float32)
    levels = [base]
    current = base
    for _idx in range(1, max(1, int(max_levels))):
        next_level = _downsample_level(current)
        if next_level is None:
            break
        levels.append(next_level)
        current = next_level
        if int(current.shape[0]) <= 1 and int(current.shape[1]) <= 1:
            break
    return tuple(levels)


def sample_prefilter_levels(levels: Any, dx: Any, dy: Any, dz: Any, roughness: Any):
    try:
        rows = [np.asarray(level, dtype=np.float32) for level in levels if level is not None]
    except Exception:
        rows = []
    if not rows:
        return None
    rough = np.asarray(roughness, dtype=np.float32)
    if len(rows) == 1:
        return sample_equirect(rows[0], dx, dy, dz)
    level_float = np.clip(rough * rough, 0.0, 1.0) * float(len(rows) - 1)
    lo = np.clip(np.floor(level_float).astype(np.int32), 0, len(rows) - 1)
    hi = np.clip(lo + 1, 0, len(rows) - 1)
    mix = (level_float - lo)[..., None]
    unique_lo = np.unique(lo)
    unique_hi = np.unique(hi)
    low = np.zeros((*np.shape(level_float), 3), dtype=np.float32)
    high = np.zeros_like(low)
    for idx in unique_lo:
        sample = sample_equirect(rows[int(idx)], dx, dy, dz)
        low = np.where((lo == int(idx))[..., None], sample, low)
    for idx in unique_hi:
        sample = sample_equirect(rows[int(idx)], dx, dy, dz)
        high = np.where((hi == int(idx))[..., None], sample, high)
    return np.ascontiguousarray(low * (1.0 - mix) + high * mix, dtype=np.float32)


def _dir_from_equirect_pixel(x: int, y: int, width: int, height: int) -> np.ndarray:
    u = (float(x) + 0.5) / max(1.0, float(width))
    v = (float(y) + 0.5) / max(1.0, float(height))
    phi = (u - 0.5) * 2.0 * math.pi
    theta = v * math.pi
    sin_t = math.sin(theta)
    return np.asarray([math.cos(phi) * sin_t, math.cos(theta), math.sin(phi) * sin_t], dtype=np.float32)


def _basis_from_normal(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = np.asarray(normal, dtype=np.float32)
    up = np.asarray([0.0, 1.0, 0.0], dtype=np.float32)
    if abs(float(n[1])) > 0.92:
        up = np.asarray([1.0, 0.0, 0.0], dtype=np.float32)
    tangent = np.cross(up, n)
    tangent /= max(1.0e-6, float(np.linalg.norm(tangent)))
    bitangent = np.cross(n, tangent)
    bitangent /= max(1.0e-6, float(np.linalg.norm(bitangent)))
    return tangent, bitangent


def _cosine_hemisphere_samples(sample_count: int) -> np.ndarray:
    rows = []
    count = max(4, int(sample_count))
    for idx in range(count):
        u1 = (idx + 0.5) / count
        u2 = ((idx * 0.6180339887498949) % 1.0)
        radius = math.sqrt(u1)
        phi = 2.0 * math.pi * u2
        rows.append((radius * math.cos(phi), radius * math.sin(phi), math.sqrt(max(0.0, 1.0 - u1))))
    return np.asarray(rows, dtype=np.float32)


def build_irradiance_map(
    environment: np.ndarray,
    *,
    width: int = 32,
    height: int = 16,
    sample_count: int = 48,
) -> np.ndarray:
    env = np.asarray(environment, dtype=np.float32)
    w = max(4, int(width))
    h = max(2, int(height))
    samples = _cosine_hemisphere_samples(sample_count)
    out = np.zeros((h, w, 3), dtype=np.float32)
    for yy in range(h):
        for xx in range(w):
            normal = _dir_from_equirect_pixel(xx, yy, w, h)
            tangent, bitangent = _basis_from_normal(normal)
            dirs = (
                tangent[None, :] * samples[:, 0:1]
                + bitangent[None, :] * samples[:, 1:2]
                + normal[None, :] * samples[:, 2:3]
            )
            rgb = sample_equirect(env, dirs[:, 0], dirs[:, 1], dirs[:, 2])
            if rgb is not None:
                out[yy, xx] = np.asarray(rgb, dtype=np.float32).mean(axis=0)
    return np.ascontiguousarray(out, dtype=np.float32)


def _radical_inverse_vdc(bits: int) -> float:
    value = int(bits)
    value = (value << 16) | (value >> 16)
    value = ((value & 0x55555555) << 1) | ((value & 0xAAAAAAAA) >> 1)
    value = ((value & 0x33333333) << 2) | ((value & 0xCCCCCCCC) >> 2)
    value = ((value & 0x0F0F0F0F) << 4) | ((value & 0xF0F0F0F0) >> 4)
    value = ((value & 0x00FF00FF) << 8) | ((value & 0xFF00FF00) >> 8)
    return float(value) * 2.3283064365386963e-10


def _importance_sample_ggx(xi: tuple[float, float], roughness: float) -> np.ndarray:
    a = max(0.001, roughness * roughness)
    phi = 2.0 * math.pi * xi[0]
    cos_theta = math.sqrt((1.0 - xi[1]) / (1.0 + (a * a - 1.0) * xi[1]))
    sin_theta = math.sqrt(max(0.0, 1.0 - cos_theta * cos_theta))
    return np.asarray([math.cos(phi) * sin_theta, math.sin(phi) * sin_theta, cos_theta], dtype=np.float32)


def _geometry_schlick_ggx(ndotv: float, roughness: float) -> float:
    r = roughness + 1.0
    k = (r * r) / 8.0
    return ndotv / max(1.0e-6, ndotv * (1.0 - k) + k)


def _geometry_smith(ndotv: float, ndotl: float, roughness: float) -> float:
    return _geometry_schlick_ggx(ndotv, roughness) * _geometry_schlick_ggx(ndotl, roughness)


def build_brdf_lut(size: int = 32, *, sample_count: int = 32) -> np.ndarray:
    key = (max(4, int(size)), max(4, int(sample_count)))
    cached = _BRDF_LUT_CACHE.get(key)
    if cached is not None:
        return cached
    lut_size, samples = key
    lut = np.zeros((lut_size, lut_size, 2), dtype=np.float32)
    normal = np.asarray([0.0, 0.0, 1.0], dtype=np.float32)
    for y in range(lut_size):
        roughness = (float(y) + 0.5) / lut_size
        for x in range(lut_size):
            ndotv = (float(x) + 0.5) / lut_size
            view = np.asarray([math.sqrt(max(0.0, 1.0 - ndotv * ndotv)), 0.0, ndotv], dtype=np.float32)
            scale = 0.0
            bias = 0.0
            for idx in range(samples):
                xi = (float(idx) / samples, _radical_inverse_vdc(idx))
                half_vec = _importance_sample_ggx(xi, roughness)
                light = 2.0 * float(np.dot(view, half_vec)) * half_vec - view
                light /= max(1.0e-6, float(np.linalg.norm(light)))
                ndotl = max(float(light[2]), 0.0)
                ndoth = max(float(half_vec[2]), 0.0)
                vdoth = max(float(np.dot(view, half_vec)), 0.0)
                if ndotl <= 0.0:
                    continue
                geometry = _geometry_smith(ndotv, ndotl, roughness)
                g_vis = geometry * vdoth / max(1.0e-6, ndoth * ndotv)
                fc = (1.0 - vdoth) ** 5.0
                scale += (1.0 - fc) * g_vis
                bias += fc * g_vis
            lut[y, x, 0] = scale / samples
            lut[y, x, 1] = bias / samples
    _BRDF_LUT_CACHE[key] = np.ascontiguousarray(np.clip(lut, 0.0, 4.0), dtype=np.float32)
    return _BRDF_LUT_CACHE[key]


def sample_brdf_lut(lut: Any, ndotv: Any, roughness: Any):
    arr = np.asarray(lut, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] < 2:
        return None
    h, w = int(arr.shape[0]), int(arr.shape[1])
    x = np.clip(np.asarray(ndotv, dtype=np.float32), 0.0, 1.0) * max(1, w - 1)
    y = np.clip(np.asarray(roughness, dtype=np.float32), 0.0, 1.0) * max(1, h - 1)
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, max(0, w - 1))
    y1 = np.clip(y0 + 1, 0, max(0, h - 1))
    x0 = np.clip(x0, 0, max(0, w - 1))
    y0 = np.clip(y0, 0, max(0, h - 1))
    tx = (x - x0)[..., None]
    ty = (y - y0)[..., None]
    c00 = arr[y0, x0, :2]
    c10 = arr[y0, x1, :2]
    c01 = arr[y1, x0, :2]
    c11 = arr[y1, x1, :2]
    top = c00 * (1.0 - tx) + c10 * tx
    bottom = c01 * (1.0 - tx) + c11 * tx
    return np.ascontiguousarray(top * (1.0 - ty) + bottom * ty, dtype=np.float32)


def _cache_key(
    path: Path,
    *,
    max_luminance: float,
    max_prefilter_levels: int,
    irradiance_size: tuple[int, int],
    brdf_lut_size: int,
) -> tuple[Any, ...]:
    try:
        resolved = path.resolve()
        stat = resolved.stat()
        return (
            str(resolved),
            int(stat.st_size),
            int(stat.st_mtime_ns),
            float(max_luminance),
            int(max_prefilter_levels),
            tuple(int(v) for v in irradiance_size),
            int(brdf_lut_size),
        )
    except Exception:
        return (str(path), float(max_luminance), int(max_prefilter_levels), tuple(irradiance_size), int(brdf_lut_size))


def load_ibl_probe(
    path: str | Path,
    *,
    max_luminance: float = 16.0,
    max_prefilter_levels: int = 7,
    irradiance_size: tuple[int, int] = (32, 16),
    irradiance_samples: int = 48,
    brdf_lut_size: int = 32,
    brdf_samples: int = 32,
) -> IBLProbe | None:
    hdri_path = Path(str(path or ""))
    if not hdri_path.is_file():
        return None
    key = _cache_key(
        hdri_path,
        max_luminance=max_luminance,
        max_prefilter_levels=max_prefilter_levels,
        irradiance_size=irradiance_size,
        brdf_lut_size=brdf_lut_size,
    )
    cached = _IBL_PROBE_CACHE.get(key)
    if cached is not None:
        return cached
    image = load_radiance_hdr(hdri_path)
    env = np.asarray(image.pixels[:, :, :3], dtype=np.float32)
    env = np.nan_to_num(env, nan=0.0, posinf=float(max_luminance), neginf=0.0)
    env = np.ascontiguousarray(np.clip(env, 0.0, float(max_luminance)), dtype=np.float32)
    lum = _luminance(env)
    avg = tuple(float(v) for v in np.clip(env.reshape(-1, 3).mean(axis=0), 0.0, float(max_luminance)))
    probe = IBLProbe(
        path=str(hdri_path),
        environment=env,
        irradiance_map=build_irradiance_map(
            env,
            width=int(irradiance_size[0]),
            height=int(irradiance_size[1]),
            sample_count=int(irradiance_samples),
        ),
        prefiltered_levels=build_prefilter_levels(env, max_levels=int(max_prefilter_levels)),
        brdf_lut=build_brdf_lut(int(brdf_lut_size), sample_count=int(brdf_samples)),
        average_rgb=avg,
        source_max_luminance=float(lum.max(initial=0.0)),
    )
    _IBL_PROBE_CACHE[key] = probe
    return probe
