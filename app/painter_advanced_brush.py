"""Deterministic document-level primitives for advanced Painter brushes.

The module implements explicit mathematical contracts. It does not claim
compatibility with any proprietary brush engine.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping

import numpy as np


def _finite_unit_array(value: Any, *, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.ndim != 2:
        raise ValueError(f"{name} must be a two-dimensional mask")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must contain only finite values")
    return np.clip(array, 0.0, 1.0)


def dual_brush_intersection(primary: Any, secondary: Any, *, enabled: bool) -> np.ndarray:
    """Combine primary and secondary tip opacity by intersection."""

    primary_mask = _finite_unit_array(primary, name="primary")
    if not enabled:
        return primary_mask.copy()
    secondary_mask = _finite_unit_array(secondary, name="secondary")
    if primary_mask.shape != secondary_mask.shape:
        raise ValueError("primary and secondary masks must have the same shape")
    return np.multiply(primary_mask, secondary_mask, dtype=np.float32)


def deterministic_noise_field(
    width: int,
    height: int,
    *,
    seed: int,
    scale: float,
) -> np.ndarray:
    """Create a replay-stable unit noise field from persisted inputs."""

    width = int(width)
    height = int(height)
    scale = float(scale)
    if width <= 0 or height <= 0:
        raise ValueError("noise dimensions must be positive")
    if not np.isfinite(scale) or scale < 0.0:
        raise ValueError("noise scale must be finite and non-negative")
    generator = np.random.Generator(np.random.PCG64(int(seed)))
    field = generator.random((height, width), dtype=np.float32)
    if scale == 0.0:
        return np.ones((height, width), dtype=np.float32)
    return np.clip(1.0 - (1.0 - field) * scale, 0.0, 1.0).astype(
        np.float32,
        copy=False,
    )


@dataclass
class WetEdgeState:
    pigment: np.ndarray
    water: np.ndarray

    @classmethod
    def blank(cls, *, width: int, height: int) -> "WetEdgeState":
        width = int(width)
        height = int(height)
        if width <= 0 or height <= 0:
            raise ValueError("wet-edge dimensions must be positive")
        shape = (height, width)
        return cls(
            pigment=np.zeros(shape, dtype=np.float32),
            water=np.zeros(shape, dtype=np.float32),
        )

    def _validate_state(self) -> None:
        self.pigment = _finite_unit_array(self.pigment, name="pigment")
        self.water = _finite_unit_array(self.water, name="water")
        if self.pigment.shape != self.water.shape:
            raise ValueError("pigment and water fields must have the same shape")

    def deposit(self, mask: Any, *, pigment: float, water: float) -> None:
        self._validate_state()
        mask_array = _finite_unit_array(mask, name="mask")
        if mask_array.shape != self.pigment.shape:
            raise ValueError("deposit mask must match the wet-edge state")
        pigment = float(pigment)
        water = float(water)
        if not np.isfinite(pigment) or not np.isfinite(water):
            raise ValueError("pigment and water deposits must be finite")
        self.pigment = np.maximum(
            self.pigment,
            mask_array * np.clip(pigment, 0.0, 1.0),
        ).astype(np.float32, copy=False)
        self.water = np.maximum(
            self.water,
            mask_array * np.clip(water, 0.0, 1.0),
        ).astype(np.float32, copy=False)

    def composite_alpha(self, *, pooling: float, enabled: bool) -> np.ndarray:
        self._validate_state()
        if not enabled:
            return self.pigment.copy()
        pooling = float(pooling)
        if not np.isfinite(pooling):
            raise ValueError("pooling must be finite")
        pooling = float(np.clip(pooling, 0.0, 1.0))
        padded = np.pad(self.water, 1, mode="edge")
        neighbour_min = np.minimum.reduce(
            (
                padded[:-2, 1:-1],
                padded[2:, 1:-1],
                padded[1:-1, :-2],
                padded[1:-1, 2:],
            )
        )
        edge = np.clip(self.water - neighbour_min, 0.0, 1.0)
        return np.clip(
            self.pigment + edge * pooling * (1.0 - self.pigment),
            0.0,
            1.0,
        ).astype(np.float32, copy=False)

    def dry(self, amount: float) -> None:
        self._validate_state()
        amount = float(amount)
        if not np.isfinite(amount):
            raise ValueError("dry amount must be finite")
        self.water = np.clip(
            self.water * (1.0 - np.clip(amount, 0.0, 1.0)),
            0.0,
            1.0,
        ).astype(np.float32, copy=False)


def resolve_texture_settings(
    preset: Mapping[str, Any],
    document_texture: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve Protect Texture without synthesizing missing settings."""

    source = (
        document_texture
        if bool(preset.get("protect_texture", False))
        else preset.get("texture")
    )
    if not isinstance(source, Mapping):
        raise ValueError("resolved texture settings must be a mapping")
    return dict(source)


def advanced_dab_alphas(
    base_alpha: Any,
    settings: Mapping[str, Any],
    *,
    stroke_seed: int,
) -> np.ndarray:
    """Apply persisted advanced-brush settings to a stroke's dab opacities.

    The one-row field is the ordered dab sequence.  This keeps replay bounded by
    dab count rather than document pixels while still making dual-brush,
    texture/noise, and wet-edge state part of the actual rendered stroke.
    Disabled features are byte-identical to the input float32 values.
    """

    try:
        normalized_stroke_seed = int(stroke_seed) & ((1 << 64) - 1)
    except (TypeError, ValueError, OverflowError):
        normalized_stroke_seed = 0
    alpha = np.asarray(base_alpha, dtype=np.float32)
    if alpha.ndim != 1:
        raise ValueError("base_alpha must be a one-dimensional dab sequence")
    if not bool(np.isfinite(alpha).all()):
        raise ValueError("base_alpha must contain only finite values")
    if alpha.size == 0:
        return alpha.copy()
    field = np.clip(alpha, 0.0, 1.0).reshape(1, -1)

    if bool(settings.get("dual_brush_enabled", False)):
        strength = _unit_percent(
            settings.get("dual_brush_strength", 100),
            name="dual_brush_strength",
        )
        secondary = deterministic_noise_field(
            field.shape[1],
            1,
            seed=int(settings.get("dual_brush_seed", 0) or normalized_stroke_seed)
            & ((1 << 64) - 1),
            scale=strength,
        )
        field = dual_brush_intersection(field, secondary, enabled=True)

    if bool(settings.get("noise_enabled", False)):
        noise = deterministic_noise_field(
            field.shape[1],
            1,
            seed=int(settings.get("noise_seed", 0) or normalized_stroke_seed)
            & ((1 << 64) - 1),
            scale=_unit_percent(
                settings.get("noise_scale", 100), name="noise_scale"
            ),
        )
        field = dual_brush_intersection(field, noise, enabled=True)

    texture_settings = settings.get("texture")
    document_texture = settings.get("document_texture")
    if (
        isinstance(texture_settings, Mapping)
        and bool(texture_settings)
    ) or bool(settings.get("protect_texture", False)):
        resolved = resolve_texture_settings(
            settings,
            document_texture if isinstance(document_texture, Mapping) else {},
        )
        texture_strength = _unit_percent(
            resolved.get(
                "strength", settings.get("texture_strength", 0)
            ),
            name="texture strength",
        )
        if texture_strength > 0.0:
            pattern_id = str(resolved.get("pattern_id") or "")
            stable_pattern_seed = int.from_bytes(
                hashlib.sha256(pattern_id.encode("utf-8")).digest()[:8],
                "big",
                signed=False,
            )
            texture_seed = (int(stroke_seed) ^ stable_pattern_seed) & ((1 << 63) - 1)
            texture = deterministic_noise_field(
                field.shape[1],
                1,
                seed=texture_seed,
                scale=texture_strength,
            )
            texture_scale = _positive_finite(
                resolved.get("scale", 1.0), name="texture scale"
            )
            offset = resolved.get("offset", (0.0, 0.0))
            if not isinstance(offset, (list, tuple)) or len(offset) < 2:
                raise ValueError("texture offset must contain two numbers")
            offset_x = _finite_number(offset[0], name="texture x offset")
            _finite_number(offset[1], name="texture y offset")
            if field.shape[1] > 1 and (
                texture_scale != 1.0 or offset_x != 0.0
            ):
                positions = (
                    np.arange(field.shape[1], dtype=np.float64) * texture_scale
                    + offset_x * field.shape[1]
                ) % field.shape[1]
                left = np.floor(positions).astype(np.int64)
                right = (left + 1) % field.shape[1]
                mix = (positions - left).astype(np.float32)
                texture = (
                    texture[:, left] * (1.0 - mix)
                    + texture[:, right] * mix
                ).astype(np.float32, copy=False)
            field = dual_brush_intersection(field, texture, enabled=True)

    if bool(settings.get("wet_edges_enabled", False)):
        state = WetEdgeState.blank(width=field.shape[1], height=1)
        state.deposit(
            field,
            pigment=_unit_percent(
                settings.get("wet_edge_pigment", 100),
                name="wet_edge_pigment",
            ),
            water=_unit_percent(
                settings.get("wet_edge_water", 100),
                name="wet_edge_water",
            ),
        )
        field = state.composite_alpha(
            pooling=_unit_percent(
                settings.get("wet_edge_pooling", 50),
                name="wet_edge_pooling",
            ),
            enabled=True,
        )

    return field.reshape(-1).astype(np.float32, copy=False)


def advanced_dab_alphas_prefix_stable(settings: Mapping[str, Any]) -> bool:
    """Whether ``advanced_dab_alphas`` leaves earlier dabs alone as more arrive.

    Every feature above builds its field from ``field.shape[1]`` - the total dab
    count - so switching one on makes the alpha of dab 3 depend on how many dabs
    follow it.  A live preview can only extend an image it already painted while
    they are all off.
    """

    if bool(settings.get("dual_brush_enabled", False)):
        return False
    if bool(settings.get("noise_enabled", False)):
        return False
    if bool(settings.get("wet_edges_enabled", False)):
        return False
    if bool(settings.get("protect_texture", False)):
        return False
    texture = settings.get("texture")
    if isinstance(texture, Mapping) and bool(texture):
        return False
    return True


def _unit_percent(value: Any, *, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return float(np.clip(number, 0.0, 100.0) / 100.0)


def _finite_number(value: Any, *, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not np.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _positive_finite(value: Any, *, name: str) -> float:
    number = _finite_number(value, name=name)
    if number <= 0.0:
        raise ValueError(f"{name} must be positive")
    return number


__all__ = [
    "WetEdgeState",
    "advanced_dab_alphas",
    "advanced_dab_alphas_prefix_stable",
    "deterministic_noise_field",
    "dual_brush_intersection",
    "resolve_texture_settings",
]
