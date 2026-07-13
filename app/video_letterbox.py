"""Detect encoded letterbox/pillarbox matte areas in video frames."""
from __future__ import annotations

from typing import Any, Mapping


LETTERBOX_DETECTION_SCHEMA = "tigerstudio.video.letterbox_detection.v1"


def detect_letterbox_bands(frame: Any, *, settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Detect uniform edge mattes and return the visible content rectangle.

    The detector is intentionally conservative: it looks for low-variance dark
    or bright bands at the frame edges, then rejects the result when the
    remaining center does not look meaningfully different from the matte.
    """
    settings = settings or {}
    rgb = _frame_to_rgb_u8(frame)
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError("frame must be RGB-like")
    h, w = rgb.shape[:2]
    if h <= 1 or w <= 1:
        return _empty_detection(w, h, reason="too_small")

    luma = _luma01(rgb)
    scan_fraction = _setting_float(settings, "letterbox_scan_fraction", 0.35, 0.02, 0.48)
    max_rows = max(1, int(round(h * scan_fraction)))
    max_cols = max(1, int(round(w * scan_fraction)))

    def row_is_matte(y: int) -> bool:
        return _band_is_matte(luma[y, :], settings)

    def col_is_matte(x: int) -> bool:
        return _band_is_matte(luma[:, x], settings)

    top = 0
    while top < max_rows and row_is_matte(top):
        top += 1

    bottom_index = h
    while bottom_index > h - max_rows and bottom_index > top and row_is_matte(bottom_index - 1):
        bottom_index -= 1

    left = 0
    while left < max_cols and col_is_matte(left):
        left += 1

    right_index = w
    while right_index > w - max_cols and right_index > left and col_is_matte(right_index - 1):
        right_index -= 1

    bottom = h - bottom_index
    right = w - right_index
    if not _matte_geometry_is_plausible(h, w, top, bottom, left, right, settings):
        return _empty_detection(w, h, reason="implausible_matte_geometry")
    if not _content_rect_is_plausible(luma, top, bottom, left, right, settings):
        return _empty_detection(w, h, reason="no_reliable_content_contrast")

    content_rect = [int(left), int(top), int(max(0, w - left - right)), int(max(0, h - top - bottom))]
    kind = "none"
    if (top > 0 or bottom > 0) and (left > 0 or right > 0):
        kind = "windowbox"
    elif top > 0 or bottom > 0:
        kind = "letterbox"
    elif left > 0 or right > 0:
        kind = "pillarbox"
    matte_pixels = int((top + bottom) * w + (left + right) * max(0, h - top - bottom))
    return {
        "schema": LETTERBOX_DETECTION_SCHEMA,
        "ok": kind != "none",
        "kind": kind,
        "width": int(w),
        "height": int(h),
        "top": int(top),
        "bottom": int(bottom),
        "left": int(left),
        "right": int(right),
        "content_rect": content_rect,
        "matte_pixel_count": int(matte_pixels),
        "matte_fraction": float(matte_pixels / max(1, w * h)),
    }


def letterbox_mask_from_detection(detection: Mapping[str, Any], shape: tuple[int, int]) -> Any:
    """Return a boolean mask for the detected matte area."""
    import numpy as np

    h, w = int(shape[0]), int(shape[1])
    mask = np.zeros((h, w), dtype=bool)
    if not bool(detection.get("ok")):
        return mask
    top = max(0, min(h, int(detection.get("top", 0) or 0)))
    bottom = max(0, min(h, int(detection.get("bottom", 0) or 0)))
    left = max(0, min(w, int(detection.get("left", 0) or 0)))
    right = max(0, min(w, int(detection.get("right", 0) or 0)))
    if top:
        mask[:top, :] = True
    if bottom:
        mask[h - bottom :, :] = True
    if left:
        mask[:, :left] = True
    if right:
        mask[:, w - right :] = True
    return mask


def preserve_letterbox_matte(source_rgb: Any, processed_rgb: Any, *, settings: Mapping[str, Any] | None = None) -> Any:
    """Restore detected encoded matte pixels from ``source_rgb`` into output.

    This is for render/effect paths where the black/white edge matte is not
    artistic content. It leaves frames untouched when no reliable matte is
    detected.
    """
    import numpy as np

    src = np.asarray(source_rgb)
    out = np.asarray(processed_rgb)
    if src.shape[:2] != out.shape[:2] or src.ndim < 2 or out.ndim < 2:
        return processed_rgb
    try:
        detection = detect_letterbox_bands(src, settings=settings)
    except Exception:
        return processed_rgb
    if not bool(detection.get("ok")):
        return processed_rgb
    mask = letterbox_mask_from_detection(detection, out.shape[:2])
    if not bool(mask.any()):
        return processed_rgb
    restored = out.copy()
    if restored.ndim == 2:
        restored[mask] = src[..., 0][mask] if src.ndim == 3 else src[mask]
    else:
        restored[mask, : min(restored.shape[2], src.shape[2] if src.ndim == 3 else 1)] = (
            src[mask, : min(restored.shape[2], src.shape[2])] if src.ndim == 3 else src[mask, None]
        )
    return restored


def _frame_to_rgb_u8(frame: Any) -> Any:
    import numpy as np

    try:
        from PIL import Image

        if isinstance(frame, Image.Image):
            return np.asarray(frame.convert("RGB"), dtype=np.uint8)
    except Exception:
        pass
    arr = np.asarray(frame)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("frame must be grayscale or RGB-like")
    arr = arr[:, :, :3]
    if arr.dtype == np.uint8:
        return arr
    f = arr.astype(np.float32)
    if float(np.nanmax(f)) <= 1.5:
        f = f * 255.0
    return np.clip(np.nan_to_num(f, nan=0.0, posinf=255.0, neginf=0.0), 0, 255).astype(np.uint8)


def _luma01(rgb: Any) -> Any:
    import numpy as np

    arr = np.asarray(rgb, dtype=np.float32)
    if arr.max(initial=0.0) > 1.5:
        arr = arr / 255.0
    return arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722


def _band_is_matte(values: Any, settings: Mapping[str, Any]) -> bool:
    import numpy as np

    mean = float(np.mean(values))
    std = float(np.std(values))
    dark_max = _setting_float(settings, "letterbox_dark_luma_max", 0.075, 0.0, 0.35)
    bright_min = _setting_float(settings, "letterbox_bright_luma_min", 0.965, 0.65, 1.0)
    std_max = _setting_float(settings, "letterbox_std_max", 0.018, 0.0, 0.12)
    detect_bright = _setting_bool(settings, "letterbox_detect_bright_matte", True)
    if std > std_max:
        return False
    return mean <= dark_max or (detect_bright and mean >= bright_min)


def _content_rect_is_plausible(
    luma: Any,
    top: int,
    bottom: int,
    left: int,
    right: int,
    settings: Mapping[str, Any],
) -> bool:
    import numpy as np

    h, w = luma.shape[:2]
    if top <= 0 and bottom <= 0 and left <= 0 and right <= 0:
        return True
    content_h = h - top - bottom
    content_w = w - left - right
    min_fraction = _setting_float(settings, "letterbox_min_content_fraction", 0.25, 0.05, 0.95)
    if content_h <= 1 or content_w <= 1:
        return False
    if (content_h * content_w) / max(1, h * w) < min_fraction:
        return False
    center = luma[top : h - bottom if bottom else h, left : w - right if right else w]
    matte_values = []
    if top:
        matte_values.append(luma[:top, :])
    if bottom:
        matte_values.append(luma[h - bottom :, :])
    if left:
        matte_values.append(luma[:, :left])
    if right:
        matte_values.append(luma[:, w - right :])
    matte = np.concatenate([item.reshape(-1) for item in matte_values]) if matte_values else np.asarray([], dtype=np.float32)
    content_std = float(np.std(center))
    contrast = abs(float(np.mean(center)) - float(np.mean(matte))) if matte.size else 0.0
    min_content_std = _setting_float(settings, "letterbox_min_content_std", 0.012, 0.0, 0.08)
    min_contrast = _setting_float(settings, "letterbox_min_content_contrast", 0.035, 0.0, 0.3)
    if (
        _setting_bool(settings, "letterbox_reject_floating_subject_matte", True)
        and matte.size
        and _content_rect_edges_match_matte(center, matte, settings)
    ):
        return False
    return content_std >= min_content_std or contrast >= min_contrast


def _content_rect_edges_match_matte(center: Any, matte: Any, settings: Mapping[str, Any]) -> bool:
    """Reject centered objects on dark/bright scene backgrounds.

    Encoded letterbox/pillarbox content normally begins immediately after the
    matte band. If the detected content rectangle still has matte-colored
    strips on multiple sides, the detector probably found the empty background
    around a subject instead of an encoded video matte.
    """
    import numpy as np

    h, w = center.shape[:2]
    if h <= 4 or w <= 4:
        return False
    matte_mean = float(np.mean(matte))
    matte_std = float(np.std(matte))
    dark_max = _setting_float(settings, "letterbox_dark_luma_max", 0.075, 0.0, 0.35)
    bright_min = _setting_float(settings, "letterbox_bright_luma_min", 0.965, 0.65, 1.0)
    if matte_mean > dark_max and matte_mean < bright_min:
        return False
    if matte_std > _setting_float(settings, "letterbox_std_max", 0.018, 0.0, 0.12) * 2.5:
        return False

    strip_fraction = _setting_float(settings, "letterbox_content_edge_probe_fraction", 0.07, 0.01, 0.18)
    sy = max(1, min(h // 4, int(round(h * strip_fraction))))
    sx = max(1, min(w // 4, int(round(w * strip_fraction))))
    strips = (
        center[:sy, :],
        center[h - sy :, :],
        center[:, :sx],
        center[:, w - sx :],
    )
    pixel_tol = _setting_float(settings, "letterbox_content_edge_matte_pixel_tolerance", 0.045, 0.005, 0.20)
    fraction_min = _setting_float(settings, "letterbox_content_edge_matte_fraction_min", 0.58, 0.10, 0.95)
    matching = 0
    for strip in strips:
        matte_like_fraction = float(np.mean(np.abs(strip - matte_mean) <= pixel_tol))
        if matte_like_fraction >= fraction_min:
            matching += 1
    return matching >= _setting_float(settings, "letterbox_content_edge_matte_match_count", 2, 1, 4)


def _matte_geometry_is_plausible(
    height: int,
    width: int,
    top: int,
    bottom: int,
    left: int,
    right: int,
    settings: Mapping[str, Any],
) -> bool:
    """Reject matte detections that look like dark scene content.

    Uniform dark scenes can make the edge scanner walk deep into real picture
    content, especially in low-key footage.  True encoded mattes are usually
    thin and paired with the opposite edge; a very large one-sided detection is
    more likely a dark floor/car/body region than letterbox.
    """
    h = max(1, int(height))
    w = max(1, int(width))
    max_edge_fraction = _setting_float(settings, "letterbox_max_single_edge_fraction", 0.30, 0.02, 0.49)
    max_one_sided_fraction = _setting_float(settings, "letterbox_max_one_sided_fraction", 0.12, 0.0, 0.49)
    max_pair_imbalance = _setting_float(settings, "letterbox_max_pair_imbalance", 6.0, 1.0, 99.0)
    max_matte_fraction = _setting_float(settings, "letterbox_max_matte_fraction", 0.62, 0.05, 0.95)
    matte_pixels = int((max(0, top) + max(0, bottom)) * w + (max(0, left) + max(0, right)) * max(0, h - max(0, top) - max(0, bottom)))
    if matte_pixels / max(1, h * w) > max_matte_fraction:
        return False

    def _axis_ok(a: int, b: int, span: int) -> bool:
        a = max(0, int(a))
        b = max(0, int(b))
        if a <= 0 and b <= 0:
            return True
        if a / span > max_edge_fraction or b / span > max_edge_fraction:
            return False
        if (a <= 0) != (b <= 0):
            return max(a, b) / span <= max_one_sided_fraction
        small = max(1, min(a, b))
        large = max(a, b)
        if large / span > max_one_sided_fraction and large / small > max_pair_imbalance:
            return False
        return True

    return _axis_ok(top, bottom, h) and _axis_ok(left, right, w)


def _empty_detection(width: int, height: int, *, reason: str = "none") -> dict[str, Any]:
    return {
        "schema": LETTERBOX_DETECTION_SCHEMA,
        "ok": False,
        "reason": reason,
        "kind": "none",
        "width": int(width),
        "height": int(height),
        "top": 0,
        "bottom": 0,
        "left": 0,
        "right": 0,
        "content_rect": [0, 0, int(width), int(height)],
        "matte_pixel_count": 0,
        "matte_fraction": 0.0,
    }


def _setting_float(settings: Mapping[str, Any], key: str, default: float, lo: float, hi: float) -> float:
    try:
        value = float(settings.get(key, default))
    except Exception:
        value = float(default)
    return max(float(lo), min(float(hi), value))


def _setting_bool(settings: Mapping[str, Any], key: str, default: bool) -> bool:
    value = settings.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


__all__ = [
    "LETTERBOX_DETECTION_SCHEMA",
    "detect_letterbox_bands",
    "letterbox_mask_from_detection",
    "preserve_letterbox_matte",
]
