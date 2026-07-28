"""Shared Motion Designer preview/export color pipeline."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.color_management import LutSlot
from app.color_runtime import apply_project_display_transform_rgb, display_transform_required

from .color_management import MotionColorSettings


@dataclass(frozen=True, slots=True)
class CubeLut:
    size: int
    values: np.ndarray
    domain_min: np.ndarray
    domain_max: np.ndarray


@lru_cache(maxsize=12)
def _load_cube_cached(path: str, size_bytes: int, mtime_ns: int) -> CubeLut:
    del size_bytes, mtime_ns
    lut_size = 0
    domain_min = np.zeros(3, dtype=np.float32)
    domain_max = np.ones(3, dtype=np.float32)
    samples: list[list[float]] = []
    for raw_line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.upper().startswith("TITLE"):
            continue
        parts = line.split()
        keyword = parts[0].upper()
        if keyword == "LUT_3D_SIZE":
            lut_size = int(parts[-1])
            continue
        if keyword == "LUT_1D_SIZE":
            raise ValueError("1D .cube LUTs are not supported by the Motion color pipeline")
        if keyword == "DOMAIN_MIN":
            domain_min = np.asarray(parts[1:4], dtype=np.float32)
            continue
        if keyword == "DOMAIN_MAX":
            domain_max = np.asarray(parts[1:4], dtype=np.float32)
            continue
        if len(parts) == 3:
            try:
                samples.append([float(value) for value in parts])
            except ValueError:
                continue
    if lut_size < 2:
        raise ValueError("LUT_3D_SIZE is missing or invalid")
    expected = lut_size ** 3
    if len(samples) != expected:
        raise ValueError(f"Expected {expected} LUT samples, found {len(samples)}")
    if np.any(domain_max <= domain_min):
        raise ValueError("LUT domain maximum must be greater than its minimum")
    # .cube files enumerate red fastest, then green, then blue.
    values = np.asarray(samples, dtype=np.float32).reshape(lut_size, lut_size, lut_size, 3)
    return CubeLut(lut_size, values, domain_min, domain_max)


def load_cube_lut(path: str | Path) -> CubeLut:
    candidate = Path(path).expanduser().resolve()
    stat = candidate.stat()
    return _load_cube_cached(str(candidate), int(stat.st_size), int(stat.st_mtime_ns))


def apply_cube_lut_rgb(rgb: np.ndarray, slot: LutSlot) -> np.ndarray:
    source = np.asarray(rgb, dtype=np.uint8)
    if not slot.is_active():
        return source
    lut = load_cube_lut(slot.path)
    normalized = source.astype(np.float32) / 255.0
    normalized = np.clip(
        (normalized - lut.domain_min) / (lut.domain_max - lut.domain_min),
        0.0,
        1.0,
    )
    coords = normalized * float(lut.size - 1)
    lower = np.floor(coords).astype(np.int32)
    upper = np.minimum(lower + 1, lut.size - 1)
    fraction = coords - lower
    red0, green0, blue0 = lower[..., 0], lower[..., 1], lower[..., 2]
    red1, green1, blue1 = upper[..., 0], upper[..., 1], upper[..., 2]
    fr, fg, fb = (fraction[..., index:index + 1] for index in range(3))
    values = lut.values
    c000 = values[blue0, green0, red0]
    c100 = values[blue0, green0, red1]
    c010 = values[blue0, green1, red0]
    c110 = values[blue0, green1, red1]
    c001 = values[blue1, green0, red0]
    c101 = values[blue1, green0, red1]
    c011 = values[blue1, green1, red0]
    c111 = values[blue1, green1, red1]
    transformed = (
        c000 * (1 - fr) * (1 - fg) * (1 - fb)
        + c100 * fr * (1 - fg) * (1 - fb)
        + c010 * (1 - fr) * fg * (1 - fb)
        + c110 * fr * fg * (1 - fb)
        + c001 * (1 - fr) * (1 - fg) * fb
        + c101 * fr * (1 - fg) * fb
        + c011 * (1 - fr) * fg * fb
        + c111 * fr * fg * fb
    )
    transformed_u8 = np.rint(np.clip(transformed, 0.0, 1.0) * 255.0).astype(np.uint8)
    strength = max(0.0, min(1.0, float(slot.strength)))
    if strength >= 0.999999:
        return np.ascontiguousarray(transformed_u8)
    blended = source.astype(np.float32) * (1.0 - strength) + transformed_u8 * strength
    return np.ascontiguousarray(np.rint(blended).clip(0, 255).astype(np.uint8))


def apply_motion_tone_map_rgb(rgb: np.ndarray, tone_map: str) -> np.ndarray:
    source = np.asarray(rgb, dtype=np.uint8)
    mode = str(tone_map or "none").strip().lower().replace("_", "-")
    if mode == "none":
        return source
    encoded = source.astype(np.float32) / 255.0
    linear = np.where(
        encoded <= 0.04045,
        encoded / 12.92,
        ((encoded + 0.055) / 1.055) ** 2.4,
    )
    if mode == "reinhard":
        mapped = linear / (1.0 + linear)
    elif mode == "aces-fitted":
        mapped = linear * (2.51 * linear + 0.03) / (
            linear * (2.43 * linear + 0.59) + 0.14
        )
    else:
        raise ValueError(f"Unsupported Motion tone map: {tone_map}")
    mapped = np.clip(mapped, 0.0, 1.0)
    display = np.where(
        mapped <= 0.0031308,
        mapped * 12.92,
        1.055 * np.power(mapped, 1.0 / 2.4) - 0.055,
    )
    return np.ascontiguousarray(np.rint(display * 255.0).clip(0, 255).astype(np.uint8))


def motion_color_transform_required(settings: MotionColorSettings) -> bool:
    return bool(
        settings.tone_map != "none"
        or settings.project.active_luts()
        or display_transform_required(settings.project)
    )


def apply_motion_color_pipeline_rgb(
    rgb: np.ndarray,
    settings: MotionColorSettings,
) -> tuple[np.ndarray, dict[str, Any]]:
    output = np.asarray(rgb, dtype=np.uint8)
    stages: list[dict[str, Any]] = []
    project = settings.project
    for name, slot in (
        ("input_lut", project.input_lut),
        ("tone_map", settings.tone_map),
        ("creative_lut", project.creative_lut),
    ):
        if name == "tone_map":
            if slot != "none":
                output = apply_motion_tone_map_rgb(output, str(slot))
                stages.append({"stage": name, "mode": str(slot)})
        elif slot.is_active():
            output = apply_cube_lut_rgb(output, slot)
            stages.append({"stage": name, "path": slot.path, "strength": slot.strength})
    output, display_report = apply_project_display_transform_rgb(output, project)
    if display_report.get("applied"):
        stages.append({
            "stage": "display_transform",
            "engine": display_report.get("engine", "unknown"),
        })
    if project.output_lut.is_active():
        output = apply_cube_lut_rgb(output, project.output_lut)
        stages.append({
            "stage": "output_lut",
            "path": project.output_lut.path,
            "strength": project.output_lut.strength,
        })
    return np.ascontiguousarray(output), {
        "schema": "tigerstudio.motion.color.runtime.v1",
        "applied": bool(stages),
        "stages": stages,
        "display": display_report,
    }


def apply_motion_color_pipeline_premultiplied_rgba(
    rgba: np.ndarray,
    settings: MotionColorSettings,
) -> tuple[np.ndarray, dict[str, Any]]:
    source = np.asarray(rgba, dtype=np.uint8)
    if source.ndim != 3 or source.shape[-1] != 4:
        raise ValueError("rgba must have shape (height, width, 4)")
    if not motion_color_transform_required(settings):
        return source, {
            "schema": "tigerstudio.motion.color.runtime.v1",
            "applied": False,
            "stages": [],
        }
    alpha = source[..., 3:4].astype(np.float32) / 255.0
    straight = np.divide(
        source[..., :3].astype(np.float32),
        alpha,
        out=np.zeros_like(source[..., :3], dtype=np.float32),
        where=alpha > 1e-8,
    )
    transformed, report = apply_motion_color_pipeline_rgb(
        np.rint(straight).clip(0, 255).astype(np.uint8),
        settings,
    )
    output = source.copy()
    output[..., :3] = np.rint(transformed.astype(np.float32) * alpha).clip(0, 255).astype(np.uint8)
    return np.ascontiguousarray(output), report


__all__ = [
    "CubeLut",
    "apply_cube_lut_rgb",
    "apply_motion_color_pipeline_premultiplied_rgba",
    "apply_motion_color_pipeline_rgb",
    "apply_motion_tone_map_rgb",
    "load_cube_lut",
    "motion_color_transform_required",
]
