"""Shared display transform controls for AR/PBR render paths."""
from __future__ import annotations

from typing import Any, Mapping

import numpy as np


DEFAULT_TONE_MAPPING = "aces"
DEFAULT_TONE_EXPOSURE = 0.0
DEFAULT_TONE_WHITE_BALANCE = 6500.0
DEFAULT_TONE_GAMMA = 2.2

TONE_MAPPING_MODES = {
    "aces": 0,
    "agx": 1,
    "reinhard": 2,
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def normalize_tone_mapping_mode(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "": DEFAULT_TONE_MAPPING,
        "default": DEFAULT_TONE_MAPPING,
        "filmic": DEFAULT_TONE_MAPPING,
        "aces_fitted": "aces",
        "acescg": "aces",
        "agx_filmic": "agx",
        "reinhard_extended": "reinhard",
        "rh": "reinhard",
    }
    text = aliases.get(text, text)
    return text if text in TONE_MAPPING_MODES else DEFAULT_TONE_MAPPING


def _kelvin_to_rgb(kelvin: float) -> np.ndarray:
    temperature = _clamp(kelvin, 1000.0, 40000.0) / 100.0
    if temperature <= 66.0:
        red = 255.0
        green = 99.4708025861 * np.log(max(temperature, 1.0)) - 161.1195681661
        blue = 0.0 if temperature <= 19.0 else 138.5177312231 * np.log(max(temperature - 10.0, 1.0)) - 305.0447927307
    else:
        red = 329.698727446 * np.power(max(temperature - 60.0, 1.0), -0.1332047592)
        green = 288.1221695283 * np.power(max(temperature - 60.0, 1.0), -0.0755148492)
        blue = 255.0
    return np.clip(np.asarray([red, green, blue], dtype=np.float32) / 255.0, 0.0, 1.0)


def white_balance_rgb(kelvin: float) -> tuple[float, float, float]:
    d65 = _kelvin_to_rgb(DEFAULT_TONE_WHITE_BALANCE)
    target = _kelvin_to_rgb(kelvin)
    gain = target / np.maximum(d65, 1.0e-6)
    gain = gain / max(float(np.mean(gain)), 1.0e-6)
    return tuple(float(v) for v in np.clip(gain, 0.25, 4.0))


def normalize_color_management_settings(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    tone_mapping = normalize_tone_mapping_mode(data.get("tone_mapping", data.get("tone_map", data.get("view_transform"))))
    exposure = _clamp(
        _float(data.get("tone_exposure", data.get("output_exposure", data.get("exposure_compensation"))), DEFAULT_TONE_EXPOSURE),
        -8.0,
        8.0,
    )
    white_balance = _clamp(
        _float(data.get("tone_white_balance", data.get("white_balance", data.get("output_white_balance"))), DEFAULT_TONE_WHITE_BALANCE),
        1000.0,
        40000.0,
    )
    gamma = _clamp(
        _float(data.get("tone_gamma", data.get("output_gamma", data.get("gamma"))), DEFAULT_TONE_GAMMA),
        0.1,
        4.0,
    )
    return {
        "schema": "tigerstudio.ar_pbr.color_management.v1",
        "tone_mapping": tone_mapping,
        "tone_mapping_mode": int(TONE_MAPPING_MODES[tone_mapping]),
        "tone_exposure": float(exposure),
        "tone_white_balance": float(white_balance),
        "tone_white_balance_rgb": list(white_balance_rgb(white_balance)),
        "tone_gamma": float(gamma),
        "working_space": "scene_linear_srgb",
        "display_space": "display_referred_srgb",
        "render_pass_safe": True,
        "alpha_policy": "preserve_linear_alpha",
    }


def flatten_color_management_settings(value: Any) -> dict[str, Any]:
    settings = normalize_color_management_settings(value)
    return {
        "tone_mapping": str(settings["tone_mapping"]),
        "tone_exposure": float(settings["tone_exposure"]),
        "tone_white_balance": float(settings["tone_white_balance"]),
        "tone_gamma": float(settings["tone_gamma"]),
    }


def tonemap_aces(rgb: Any) -> np.ndarray:
    x = np.maximum(np.asarray(rgb, dtype=np.float32), 0.0)
    return np.clip((x * (2.51 * x + 0.03)) / np.maximum(x * (2.43 * x + 0.59) + 0.14, 1.0e-6), 0.0, 1.0)


def tonemap_reinhard(rgb: Any) -> np.ndarray:
    x = np.maximum(np.asarray(rgb, dtype=np.float32), 0.0)
    return np.clip(x / (1.0 + x), 0.0, 1.0)


def tonemap_agx(rgb: Any) -> np.ndarray:
    x = np.maximum(np.asarray(rgb, dtype=np.float32), 0.0)
    # AgX-style log encoding and sigmoid contrast approximation. This keeps the
    # transform deterministic across CPU and shader paths without requiring OCIO.
    x = np.log2(np.maximum(x, 1.0e-6))
    x = np.clip((x + 12.47393) / (16.5), 0.0, 1.0)
    return np.clip(x * x * (3.0 - 2.0 * x), 0.0, 1.0)


def apply_display_transform(rgb: Any, settings: Mapping[str, Any] | None = None) -> np.ndarray:
    cfg = normalize_color_management_settings(settings or {})
    x = np.asarray(rgb, dtype=np.float32)
    wb = np.asarray(cfg["tone_white_balance_rgb"], dtype=np.float32)
    x = np.maximum(x, 0.0) * float(np.power(2.0, float(cfg["tone_exposure"]))) * wb
    mode = str(cfg["tone_mapping"])
    if mode == "agx":
        mapped = tonemap_agx(x)
    elif mode == "reinhard":
        mapped = tonemap_reinhard(x)
    else:
        mapped = tonemap_aces(x)
    gamma = max(0.1, float(cfg["tone_gamma"]))
    return np.power(np.clip(mapped, 0.0, 1.0), 1.0 / gamma).astype(np.float32)

