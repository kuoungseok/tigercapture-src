"""Deterministic editable wet-canvas color exchange for Painter."""
from __future__ import annotations

import hashlib
import json
import math
import operator
from typing import Any, Callable, Mapping, Sequence

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter


WET_CANVAS_SCHEMA = "tigerstudio.painter.wet_canvas.v1"
WET_CANVAS_DRYING_MIN_SECONDS = 1.0
WET_CANVAS_DRYING_MAX_SECONDS = 86400.0
WET_CANVAS_DRYING_UI_MINUTES_MIN = 1
WET_CANVAS_DRYING_UI_MINUTES_MAX = 1440
SECONDS_PER_MINUTE = 60.0
WET_CANVAS_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "mixing": 0.42,
    "diffusion": 0.24,
    "pickup": 0.34,
    "drying_seconds": 900.0,
    "elapsed_seconds": 0.0,
}


def _value(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, Mapping):
        return row.get(name, default)
    return getattr(row, name, default)


def _clamp01(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return max(0.0, min(1.0, float(default)))


def normalize_wet_canvas_settings(value: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(value or {})
    try:
        drying_seconds = float(
            source.get("drying_seconds", WET_CANVAS_DEFAULTS["drying_seconds"])
        )
    except (TypeError, ValueError):
        drying_seconds = float(WET_CANVAS_DEFAULTS["drying_seconds"])
    try:
        elapsed_seconds = float(
            source.get("elapsed_seconds", WET_CANVAS_DEFAULTS["elapsed_seconds"])
        )
    except (TypeError, ValueError):
        elapsed_seconds = float(WET_CANVAS_DEFAULTS["elapsed_seconds"])
    return {
        "enabled": bool(source.get("enabled", WET_CANVAS_DEFAULTS["enabled"])),
        "mixing": _clamp01(source.get("mixing"), WET_CANVAS_DEFAULTS["mixing"]),
        "diffusion": _clamp01(
            source.get("diffusion"),
            WET_CANVAS_DEFAULTS["diffusion"],
        ),
        "pickup": _clamp01(source.get("pickup"), WET_CANVAS_DEFAULTS["pickup"]),
        "drying_seconds": max(
            WET_CANVAS_DRYING_MIN_SECONDS,
            min(WET_CANVAS_DRYING_MAX_SECONDS, drying_seconds),
        ),
        "elapsed_seconds": max(
            0.0,
            min(WET_CANVAS_DRYING_MAX_SECONDS, elapsed_seconds),
        ),
    }


def drying_seconds_to_ui_minutes(value: object) -> int:
    """Map serialized seconds to the full 1..1,440 minute edit domain.

    Positive half-minute ties round upward. Values below one minute remain
    representable by the one-minute UI endpoint without mutating serialized
    state until the user edits the control.
    """

    seconds = normalize_wet_canvas_settings({"drying_seconds": value})[
        "drying_seconds"
    ]
    rounded = int(math.floor(seconds / SECONDS_PER_MINUTE + 0.5))
    return max(
        WET_CANVAS_DRYING_UI_MINUTES_MIN,
        min(WET_CANVAS_DRYING_UI_MINUTES_MAX, rounded),
    )


def drying_ui_minutes_to_seconds(value: object) -> float:
    """Convert a UI minute value to serialized seconds without truncation."""

    if isinstance(value, bool):
        raise ValueError("drying minutes must be an integer")
    try:
        minutes = operator.index(value)
    except TypeError as exc:
        raise ValueError("drying minutes must be an integer") from exc
    if not WET_CANVAS_DRYING_UI_MINUTES_MIN <= minutes <= WET_CANVAS_DRYING_UI_MINUTES_MAX:
        raise ValueError("drying minutes are outside the 1..1440 edit domain")
    return float(minutes) * SECONDS_PER_MINUTE


def wet_canvas_remaining(value: Mapping[str, Any] | None) -> float:
    settings = normalize_wet_canvas_settings(value)
    if not settings["enabled"]:
        return 0.0
    return max(
        0.0,
        1.0 - settings["elapsed_seconds"] / max(1.0, settings["drying_seconds"]),
    )


def advance_wet_canvas(
    value: Mapping[str, Any] | None,
    seconds: float,
) -> dict[str, Any]:
    settings = normalize_wet_canvas_settings(value)
    settings["elapsed_seconds"] = min(
        settings["drying_seconds"],
        settings["elapsed_seconds"] + max(0.0, float(seconds)),
    )
    return settings


def dry_wet_canvas(value: Mapping[str, Any] | None) -> dict[str, Any]:
    settings = normalize_wet_canvas_settings(value)
    settings["elapsed_seconds"] = settings["drying_seconds"]
    return settings


def wet_canvas_signature(
    strokes: Sequence[Any],
    settings: Mapping[str, Any] | None,
    *,
    width: int,
    height: int,
    time_ms: int,
    opacity_scale: float = 1.0,
) -> str:
    rows = []
    for stroke in strokes:
        rows.append(
            {
                "points": list(_value(stroke, "points", []) or []),
                "color": list(_value(stroke, "color", (255, 255, 255)) or []),
                "opacity": int(_value(stroke, "opacity", 255) or 0),
                "width": float(_value(stroke, "width_px", 1.0) or 1.0),
                "style": str(_value(stroke, "brush_style", "round") or "round"),
                "pressure": list(_value(stroke, "point_pressure", []) or []),
                "tilt_x": list(_value(stroke, "point_tilt_x", []) or []),
                "tilt_y": list(_value(stroke, "point_tilt_y", []) or []),
                "wetness": float(_value(stroke, "material_wetness", 0.0) or 0.0),
                "start_ms": int(_value(stroke, "start_ms", 0) or 0),
                "end_ms": _value(stroke, "end_ms", None),
            }
        )
    payload = {
        "schema": WET_CANVAS_SCHEMA,
        "size": [max(1, int(width)), max(1, int(height))],
        "time_ms": int(time_ms),
        "opacity_scale": round(float(opacity_scale), 5),
        "settings": normalize_wet_canvas_settings(settings),
        "strokes": rows,
    }
    return hashlib.blake2b(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=16,
    ).hexdigest()


def _qimage_rgba(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(
        bytes(rgba.constBits()),
        dtype=np.uint8,
    ).reshape((rgba.height(), rgba.width(), 4))


def _rgba_qimage(values: np.ndarray) -> QImage:
    rgba = np.ascontiguousarray(np.clip(values, 0, 255).astype(np.uint8))
    height, width = rgba.shape[:2]
    return QImage(
        rgba.data,
        width,
        height,
        width * 4,
        QImage.Format.Format_RGBA8888,
    ).copy()


def render_wet_layer_qimage(
    strokes: Sequence[Any],
    *,
    settings: Mapping[str, Any] | None,
    width: int,
    height: int,
    time_ms: int,
    render_stroke: Callable[[QPainter, Any, int, int, float], None],
    opacity_scale: float = 1.0,
) -> tuple[QImage, dict[str, Any]]:
    """Render one material layer with deterministic RGB wet exchange.

    This is a shallow 2.5D color-state model, not spectral pigment chemistry or
    a Navier-Stokes fluid solver. Editable strokes remain the source of truth.
    """

    target_w = max(1, int(width))
    target_h = max(1, int(height))
    state = normalize_wet_canvas_settings(settings)
    remaining = wet_canvas_remaining(state)
    canvas_rgb = np.zeros((target_h, target_w, 3), dtype=np.float32)
    canvas_alpha = np.zeros((target_h, target_w), dtype=np.float32)
    wet_field = np.zeros((target_h, target_w), dtype=np.float32)
    rendered_count = 0

    for stroke in strokes:
        start_ms = int(_value(stroke, "start_ms", 0) or 0)
        end_ms = _value(stroke, "end_ms", None)
        if int(time_ms) < start_ms or (
            end_ms is not None and int(time_ms) >= int(end_ms)
        ):
            continue
        image = QImage(target_w, target_h, QImage.Format.Format_RGBA8888)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            render_stroke(
                painter,
                stroke,
                target_w,
                target_h,
                max(0.0, min(1.0, float(opacity_scale))),
            )
        finally:
            painter.end()
        rgba = _qimage_rgba(image).astype(np.float32) / 255.0
        incoming_alpha = rgba[..., 3]
        if float(np.max(incoming_alpha)) <= 0.0:
            continue
        incoming_rgb = rgba[..., :3]
        stroke_wetness = (
            _clamp01(_value(stroke, "material_wetness", 0.0)) * remaining
        )
        overlap = np.minimum(canvas_alpha, incoming_alpha) * wet_field
        exchange = np.clip(
            overlap * state["mixing"] * (0.55 + state["pickup"] * 0.45),
            0.0,
            0.92,
        )
        mixed_incoming = (
            incoming_rgb * (1.0 - exchange[..., None])
            + canvas_rgb * exchange[..., None]
        )
        out_alpha = incoming_alpha + canvas_alpha * (1.0 - incoming_alpha)
        premultiplied = (
            mixed_incoming * incoming_alpha[..., None]
            + canvas_rgb * canvas_alpha[..., None] * (1.0 - incoming_alpha[..., None])
        )
        canvas_rgb = np.divide(
            premultiplied,
            np.maximum(out_alpha[..., None], 1e-6),
            out=np.zeros_like(premultiplied),
            where=out_alpha[..., None] > 1e-6,
        )
        canvas_alpha = out_alpha
        pickup_loss = incoming_alpha * state["pickup"] * 0.18
        wet_field = np.maximum(
            wet_field * (1.0 - pickup_loss),
            incoming_alpha * stroke_wetness,
        )
        rendered_count += 1

    diffusion_applied = False
    diffusion_error = ""
    if rendered_count and remaining > 0.0 and state["diffusion"] > 0.0:
        try:
            import cv2

            sigma = 0.35 + state["diffusion"] * remaining * 2.65
            premultiplied = canvas_rgb * canvas_alpha[..., None]
            blurred_alpha = cv2.GaussianBlur(
                canvas_alpha,
                (0, 0),
                sigmaX=sigma,
                sigmaY=sigma,
            )
            blurred_premul = cv2.GaussianBlur(
                premultiplied,
                (0, 0),
                sigmaX=sigma,
                sigmaY=sigma,
            )
            blend = np.clip(
                wet_field * state["diffusion"] * remaining * 0.72,
                0.0,
                0.82,
            )
            canvas_alpha = canvas_alpha * (1.0 - blend) + blurred_alpha * blend
            original_premul = premultiplied
            mixed_premul = (
                original_premul * (1.0 - blend[..., None])
                + blurred_premul * blend[..., None]
            )
            canvas_rgb = np.divide(
                mixed_premul,
                np.maximum(canvas_alpha[..., None], 1e-6),
                out=np.zeros_like(mixed_premul),
                where=canvas_alpha[..., None] > 1e-6,
            )
            diffusion_applied = True
        except Exception as exc:
            diffusion_applied = False
            diffusion_error = f"{type(exc).__name__}: {exc}"

    output = np.zeros((target_h, target_w, 4), dtype=np.float32)
    output[..., :3] = np.clip(canvas_rgb, 0.0, 1.0) * 255.0
    output[..., 3] = np.clip(canvas_alpha, 0.0, 1.0) * 255.0
    return _rgba_qimage(output), {
        "schema": WET_CANVAS_SCHEMA,
        "enabled": bool(state["enabled"]),
        "remaining": float(remaining),
        "stroke_count": int(rendered_count),
        "mixing": float(state["mixing"]),
        "diffusion": float(state["diffusion"]),
        "pickup": float(state["pickup"]),
        "diffusion_applied": bool(diffusion_applied),
        "diffusion_error": diffusion_error,
        "model": "deterministic_rgb_shallow_wet_layer_v1",
        "physical_pigment_claim": False,
    }


__all__ = [
    "WET_CANVAS_DEFAULTS",
    "WET_CANVAS_DRYING_MAX_SECONDS",
    "WET_CANVAS_DRYING_MIN_SECONDS",
    "WET_CANVAS_DRYING_UI_MINUTES_MAX",
    "WET_CANVAS_DRYING_UI_MINUTES_MIN",
    "WET_CANVAS_SCHEMA",
    "advance_wet_canvas",
    "drying_seconds_to_ui_minutes",
    "drying_ui_minutes_to_seconds",
    "dry_wet_canvas",
    "normalize_wet_canvas_settings",
    "render_wet_layer_qimage",
    "wet_canvas_remaining",
    "wet_canvas_signature",
]
