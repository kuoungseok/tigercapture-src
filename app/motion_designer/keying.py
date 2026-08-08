"""Deterministic chroma/luma/difference keying shared by preview and export."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


KEYER_KINDS = ("chroma_key", "luma_key", "difference_key")
KEYER_CONTRACT = "tigerstudio.motion.keyer.v1"


@dataclass(frozen=True, slots=True)
class KeyerResult:
    rgba: Any
    diagnostics: dict[str, Any]


def _smoothstep(low: float, high: float, value):
    import numpy as np

    span = max(1e-6, float(high) - float(low))
    amount = np.clip((value - float(low)) / span, 0.0, 1.0)
    return amount * amount * (3.0 - 2.0 * amount)


def _hex_rgb(value: Any) -> tuple[int, int, int]:
    text = str(value or "#00ff00").strip().lstrip("#")
    if len(text) == 8:
        text = text[-6:]
    if len(text) != 6:
        return 0, 255, 0
    try:
        return tuple(int(text[index:index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return 0, 255, 0


def _edge_cleanup(alpha, *, choke: float, feather: float):
    import cv2
    import numpy as np

    output = np.clip(alpha, 0.0, 1.0).astype(np.float32)
    radius = int(round(abs(float(choke))))
    if radius:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (radius * 2 + 1, radius * 2 + 1),
        )
        output = (
            cv2.erode(output, kernel)
            if choke > 0
            else cv2.dilate(output, kernel)
        )
    softness = max(0.0, float(feather))
    if softness > 0.01:
        output = cv2.GaussianBlur(
            output,
            (0, 0),
            sigmaX=softness,
            sigmaY=softness,
        )
    return np.clip(output, 0.0, 1.0)


def _chroma_alpha(rgb, params: Mapping[str, Any]):
    import cv2
    import numpy as np

    key = np.uint8([[_hex_rgb(params.get("key_color"))]])
    key_lab = cv2.cvtColor(key, cv2.COLOR_RGB2LAB).astype(np.float32)[0, 0]
    source_lab = cv2.cvtColor(
        np.clip(rgb, 0, 255).astype(np.uint8),
        cv2.COLOR_RGB2LAB,
    ).astype(np.float32)
    distance = np.linalg.norm(source_lab - key_lab[None, None, :], axis=2)
    similarity = max(0.0, min(1.0, float(params.get("similarity", 0.35))))
    softness = max(0.001, min(1.0, float(params.get("softness", 0.15))))
    threshold = 8.0 + similarity * 75.0
    return _smoothstep(threshold, threshold + 6.0 + softness * 70.0, distance)


def _luma_alpha(rgb, params: Mapping[str, Any]):
    luminance = (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    ) / 255.0
    threshold = max(0.0, min(1.0, float(params.get("threshold", 0.5))))
    softness = max(0.001, min(1.0, float(params.get("softness", 0.1))))
    if bool(params.get("key_bright", False)):
        return 1.0 - _smoothstep(
            threshold - softness,
            threshold + softness,
            luminance,
        )
    return _smoothstep(
        threshold - softness,
        threshold + softness,
        luminance,
    )


def _difference_alpha(rgb, reference_rgb, params: Mapping[str, Any]):
    import numpy as np

    if reference_rgb is None or reference_rgb.shape[:2] != rgb.shape[:2]:
        raise ValueError("difference key requires a same-size reference frame")
    difference = np.sqrt(np.mean(
        np.square(rgb.astype(np.float32) - reference_rgb.astype(np.float32)),
        axis=2,
    )) / 255.0
    threshold = max(0.0, min(1.0, float(params.get("threshold", 0.12))))
    softness = max(0.001, min(1.0, float(params.get("softness", 0.08))))
    return _smoothstep(threshold, threshold + softness, difference)


def _despill(rgb, alpha, params: Mapping[str, Any]):
    import numpy as np

    amount = max(0.0, min(1.0, float(params.get("despill", 0.0))))
    if amount <= 1e-6:
        return rgb
    key = _hex_rgb(params.get("key_color"))
    channel = int(np.argmax(key))
    others = [index for index in range(3) if index != channel]
    neutral = np.maximum(rgb[..., others[0]], rgb[..., others[1]])
    excess = np.maximum(0.0, rgb[..., channel] - neutral)
    # Key contamination remains visible on partially opaque hair and
    # motion-blurred edges. Keep despill active through that transition while
    # still tapering it on fully opaque foreground pixels.
    edge_weight = (1.0 - alpha * 0.65) * amount
    output = rgb.copy()
    output[..., channel] -= excess * edge_weight
    output[..., others[0]] += excess * edge_weight * 0.12
    output[..., others[1]] += excess * edge_weight * 0.12
    return np.clip(output, 0.0, 255.0)


def apply_keyer_rgba(
    rgba,
    kind: str,
    params: Mapping[str, Any],
    *,
    reference_rgb=None,
) -> KeyerResult:
    import cv2
    import numpy as np

    mode = str(kind or "").strip().lower()
    if mode not in KEYER_KINDS:
        raise ValueError(f"unsupported keyer kind: {kind}")
    source = np.asarray(rgba, dtype=np.float32).copy()
    rgb = source[..., :3]
    if mode == "chroma_key":
        matte = _chroma_alpha(rgb, params)
    elif mode == "luma_key":
        matte = _luma_alpha(rgb, params)
    else:
        matte = _difference_alpha(rgb, reference_rgb, params)
    if bool(params.get("inverted", False)):
        matte = 1.0 - matte
    matte = _edge_cleanup(
        matte,
        choke=float(params.get("choke", 0.0)),
        feather=float(params.get("feather", 0.0)),
    )
    source_alpha = source[..., 3] / 255.0
    output_alpha = np.clip(source_alpha * matte, 0.0, 1.0)
    if mode == "chroma_key":
        source[..., :3] = _despill(rgb, matte, params)
    source[..., 3] = output_alpha * 255.0
    edge = cv2.morphologyEx(
        np.where(output_alpha >= 0.5, 255, 0).astype(np.uint8),
        cv2.MORPH_GRADIENT,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    diagnostics = {
        "contract": KEYER_CONTRACT,
        "kind": mode,
        "transparent_ratio": float(np.mean(output_alpha <= 0.01)),
        "opaque_ratio": float(np.mean(output_alpha >= 0.99)),
        "soft_ratio": float(np.mean(
            (output_alpha > 0.01) & (output_alpha < 0.99),
        )),
        "edge_pixel_count": int(np.count_nonzero(edge)),
    }
    return KeyerResult(source, diagnostics)


__all__ = [
    "KEYER_CONTRACT",
    "KEYER_KINDS",
    "KeyerResult",
    "apply_keyer_rgba",
]
