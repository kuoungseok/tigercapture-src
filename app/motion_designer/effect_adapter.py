"""Deterministic CPU effects shared by Motion Designer preview and export."""
from __future__ import annotations

from typing import Any
import math

from PySide6.QtGui import QImage

from .keyframes import evaluate_property
from .schema import MotionEffectRef


def _value(effect: MotionEffectRef, key: str, time_ms: float, default: Any) -> Any:
    prop = effect.params.get(key)
    return evaluate_property(prop, time_ms) if prop is not None else default


def _rgba_array(image: QImage):
    import numpy as np

    straight = image.convertToFormat(QImage.Format_RGBA8888)
    array = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(straight.height(), straight.bytesPerLine())
    return array[:, : straight.width() * 4].reshape(straight.height(), straight.width(), 4).copy()


def _qimage(array) -> QImage:
    import numpy as np

    rgba = np.ascontiguousarray(np.clip(array, 0, 255).astype(np.uint8))
    height, width = rgba.shape[:2]
    straight = QImage(rgba.data, width, height, rgba.strides[0], QImage.Format_RGBA8888).copy()
    return straight.convertToFormat(QImage.Format_RGBA8888_Premultiplied)


def _color(value: Any, default: str = "#ffffff"):
    import numpy as np

    text = str(value or default).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    try:
        values = [int(text[index:index + 2], 16) for index in (0, 2, 4)]
    except (TypeError, ValueError):
        values = [255, 255, 255]
    return np.asarray(values, dtype=np.float32)


def _fractal_noise(
    height: int,
    width: int,
    *,
    scale: float,
    octaves: int,
    seed: int,
    phase: float,
):
    import cv2
    import numpy as np

    left_seed = int(seed) + int(np.floor(phase)) * 7919
    blend = float(phase - np.floor(phase))

    def sample(sample_seed: int):
        total = np.zeros((height, width), dtype=np.float32)
        weight_total = 0.0
        frequency = 1.0
        amplitude = 1.0
        for octave in range(max(1, min(8, int(octaves)))):
            cell = max(2.0, float(scale) / frequency)
            rows = max(2, int(np.ceil(height / cell)) + 2)
            columns = max(2, int(np.ceil(width / cell)) + 2)
            rng = np.random.default_rng(sample_seed + octave * 104729)
            coarse = rng.random((rows, columns), dtype=np.float32)
            total += cv2.resize(
                coarse,
                (width, height),
                interpolation=cv2.INTER_CUBIC,
            ) * amplitude
            weight_total += amplitude
            frequency *= 2.0
            amplitude *= 0.5
        return total / max(1e-6, weight_total)

    left = sample(left_seed)
    if blend <= 1e-6:
        return left
    right = sample(left_seed + 7919)
    return left * (1.0 - blend) + right * blend


def _temporal_noise(seed: int, sample: int) -> float:
    value = math.sin((int(seed) * 12.9898 + int(sample) * 78.233) * 0.017453292519943295)
    return (value * 43758.5453) % 1.0


def _apply_craft_style(rgba, effect: MotionEffectRef, time_ms: float):
    import cv2
    import numpy as np

    amount = max(0.0, min(1.0, float(_value(effect, "amount", time_ms, 1.0))))
    seed = max(0, int(_value(effect, "seed", time_ms, 1)))
    height, width = rgba.shape[:2]

    weave_frequency = max(0.0, float(_value(effect, "weave_frequency", time_ms, 0.8)))
    phase = float(time_ms) * 0.001 * weave_frequency
    drift_x = float(_value(effect, "weave_x", time_ms, 0.8))
    drift_y = float(_value(effect, "weave_y", time_ms, 0.55))
    rotation = float(_value(effect, "weave_rotation", time_ms, 0.05))
    seed_phase = _temporal_noise(seed, 0) * math.tau
    offset_x = math.sin(phase * math.tau + seed_phase) * drift_x * amount
    offset_y = math.sin(phase * math.tau * 0.73 + seed_phase * 1.7) * drift_y * amount
    angle = math.sin(phase * math.tau * 0.41 + seed_phase * 0.6) * rotation * amount
    if abs(offset_x) > 1e-4 or abs(offset_y) > 1e-4 or abs(angle) > 1e-5:
        matrix = cv2.getRotationMatrix2D((width * 0.5, height * 0.5), angle, 1.0)
        matrix[0, 2] += offset_x
        matrix[1, 2] += offset_y
        rgba = cv2.warpAffine(
            rgba,
            matrix,
            (width, height),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )

    flicker_amount = max(0.0, min(1.0, float(
        _value(effect, "flicker_amount", time_ms, 0.018)
    ))) * amount
    flicker_frequency = max(0.0, float(
        _value(effect, "flicker_frequency", time_ms, 7.0)
    ))
    flicker_sample = int(math.floor(float(time_ms) * 0.001 * flicker_frequency))
    flicker = (_temporal_noise(seed + 19, flicker_sample) * 2.0 - 1.0) * flicker_amount
    warmth = max(-1.0, min(1.0, float(
        _value(effect, "flicker_warmth", time_ms, 0.08)
    )))
    gains = np.asarray(
        [1.0 + flicker * (1.0 + warmth), 1.0 + flicker, 1.0 + flicker * (1.0 - warmth)],
        dtype=np.float32,
    )
    rgba[..., :3] *= gains

    grain_amount = max(0.0, min(1.0, float(
        _value(effect, "grain_amount", time_ms, 0.10)
    ))) * amount
    if grain_amount > 1e-6:
        cadence = max(0.1, float(_value(effect, "grain_cadence", time_ms, 12.0)))
        grain_sample = int(math.floor(float(time_ms) * 0.001 * cadence))
        grain_size = max(1.0, min(12.0, float(
            _value(effect, "grain_size", time_ms, 1.4)
        )))
        grain_height = max(2, int(round(height / grain_size)))
        grain_width = max(2, int(round(width / grain_size)))
        rng = np.random.default_rng(seed + grain_sample * 104729)
        grain = rng.normal(0.0, 1.0, (grain_height, grain_width)).astype(np.float32)
        grain = cv2.resize(grain, (width, height), interpolation=cv2.INTER_LINEAR)
        luminance = (
            rgba[..., 0] * 0.2126 + rgba[..., 1] * 0.7152 + rgba[..., 2] * 0.0722
        ) / 255.0
        response = np.clip(1.0 - np.abs(luminance - 0.5) * 1.4, 0.25, 1.0)
        rgba[..., :3] += grain[..., None] * response[..., None] * grain_amount * 42.0
    return rgba


def apply_effects(image: QImage, effects: list[MotionEffectRef], time_ms: float) -> QImage:
    if not effects:
        return image
    import cv2
    import numpy as np

    rgba = _rgba_array(image).astype(np.float32)
    for effect in effects:
        if not effect.enabled:
            continue
        kind = effect.kind.lower().strip()
        rgb = rgba[..., :3]
        if kind == "brightness_contrast":
            brightness = float(_value(effect, "brightness", time_ms, 0.0))
            contrast = max(0.0, float(_value(effect, "contrast", time_ms, 1.0)))
            rgba[..., :3] = (rgb - 127.5) * contrast + 127.5 + brightness * 255.0
        elif kind == "saturation":
            amount = max(0.0, float(_value(effect, "amount", time_ms, 1.0)))
            luminance = rgb[..., 0:1] * .2126 + rgb[..., 1:2] * .7152 + rgb[..., 2:3] * .0722
            rgba[..., :3] = luminance + (rgb - luminance) * amount
        elif kind in {"blur", "gaussian_blur"}:
            radius = max(0.0, float(_value(effect, "radius", time_ms, 4.0)))
            if radius > 0.01:
                rgba = cv2.GaussianBlur(rgba, (0, 0), sigmaX=radius, sigmaY=radius)
        elif kind == "unsharp_mask":
            radius = max(.01, float(_value(effect, "radius", time_ms, 2.0)))
            amount = max(0.0, float(_value(effect, "amount", time_ms, .75)))
            blurred = cv2.GaussianBlur(rgb, (0, 0), sigmaX=radius, sigmaY=radius)
            rgba[..., :3] = rgb + (rgb - blurred) * amount
        elif kind == "glow":
            threshold = max(0.0, min(1.0, float(_value(effect, "threshold", time_ms, .7)))) * 255.0
            radius = max(.01, float(_value(effect, "radius", time_ms, 8.0)))
            intensity = max(0.0, float(_value(effect, "intensity", time_ms, .7)))
            source_alpha = rgba[..., 3] / 255.0
            selected = (np.max(rgb, axis=2) >= threshold).astype(np.float32) * source_alpha
            bright = rgb * selected[..., None]
            halo_rgb = cv2.GaussianBlur(bright, (0, 0), sigmaX=radius, sigmaY=radius) * intensity
            halo_alpha = cv2.GaussianBlur(selected, (0, 0), sigmaX=radius, sigmaY=radius) * min(1.0, intensity)
            output_alpha = np.clip(source_alpha + halo_alpha * (1.0 - source_alpha), 0.0, 1.0)
            premultiplied = rgb * source_alpha[..., None] + halo_rgb * (1.0 - source_alpha[..., None])
            rgba[..., :3] = np.divide(
                premultiplied, output_alpha[..., None],
                out=np.zeros_like(premultiplied), where=output_alpha[..., None] > 1e-6,
            )
            rgba[..., 3] = output_alpha * 255.0
        elif kind == "vignette":
            amount = max(0.0, min(1.0, float(_value(effect, "amount", time_ms, .35))))
            softness = max(.05, float(_value(effect, "softness", time_ms, .65)))
            height, width = rgba.shape[:2]
            yy, xx = np.ogrid[-1:1:complex(height), -1:1:complex(width)]
            radius = np.sqrt(xx * xx + yy * yy)
            shade = 1.0 - amount * np.clip((radius - (1.0 - softness)) / softness, 0.0, 1.0)
            rgba[..., :3] = rgb * shade[..., None]
        elif kind == "drop_shadow":
            offset_x = float(_value(effect, "offset_x", time_ms, 12.0))
            offset_y = float(_value(effect, "offset_y", time_ms, 12.0))
            radius = max(0.0, min(100.0, float(_value(effect, "radius", time_ms, 10.0))))
            opacity = max(0.0, min(1.0, float(_value(effect, "opacity", time_ms, 0.65))))
            shadow_color = _color(_value(effect, "color", time_ms, "#000000"), "#000000")
            source_alpha = rgba[..., 3] / 255.0
            shadow_alpha = source_alpha
            if radius > 0.01:
                shadow_alpha = cv2.GaussianBlur(
                    shadow_alpha,
                    (0, 0),
                    sigmaX=radius,
                    sigmaY=radius,
                )
            height, width = rgba.shape[:2]
            shadow_alpha = cv2.warpAffine(
                shadow_alpha,
                np.asarray(
                    [[1.0, 0.0, offset_x], [0.0, 1.0, offset_y]],
                    dtype=np.float32,
                ),
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0,
            ) * opacity
            output_alpha = source_alpha + shadow_alpha * (1.0 - source_alpha)
            premultiplied = (
                rgb * source_alpha[..., None]
                + shadow_color * shadow_alpha[..., None] * (1.0 - source_alpha[..., None])
            )
            rgba[..., :3] = np.divide(
                premultiplied,
                output_alpha[..., None],
                out=np.zeros_like(premultiplied),
                where=output_alpha[..., None] > 1e-6,
            )
            rgba[..., 3] = output_alpha * 255.0
        elif kind == "light_sweep":
            center_x = float(_value(effect, "center_x", time_ms, 0.5))
            center_y = float(_value(effect, "center_y", time_ms, 0.5))
            angle = np.deg2rad(float(_value(effect, "angle", time_ms, -24.0)))
            band_width = max(0.005, min(1.0, float(_value(effect, "width", time_ms, 0.16))))
            softness = max(0.01, min(1.0, float(_value(effect, "softness", time_ms, 0.45))))
            intensity = max(0.0, min(8.0, float(_value(effect, "intensity", time_ms, 1.2))))
            sweep_color = _color(_value(effect, "color", time_ms, "#ffffff"))
            height, width = rgba.shape[:2]
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            nx = xx / max(1, width - 1) - center_x
            ny = yy / max(1, height - 1) - center_y
            distance = np.abs(nx * np.cos(angle) + ny * np.sin(angle))
            inner = band_width * max(0.0, 1.0 - softness)
            sweep = 1.0 - np.clip(
                (distance - inner) / max(1e-6, band_width - inner),
                0.0,
                1.0,
            )
            sweep *= rgba[..., 3] / 255.0
            rgba[..., :3] = rgb + sweep[..., None] * sweep_color * intensity
        elif kind == "fractal_noise":
            amount = max(0.0, min(1.0, float(_value(effect, "amount", time_ms, 0.35))))
            scale = max(2.0, min(1000.0, float(_value(effect, "scale", time_ms, 120.0))))
            octaves = max(1, min(8, int(_value(effect, "octaves", time_ms, 4))))
            contrast = max(0.0, min(8.0, float(_value(effect, "contrast", time_ms, 1.4))))
            evolution = float(_value(effect, "evolution", time_ms, 0.0))
            speed = float(_value(effect, "speed", time_ms, 0.0))
            seed = int(_value(effect, "seed", time_ms, 1))
            height, width = rgba.shape[:2]
            noise = _fractal_noise(
                height,
                width,
                scale=scale,
                octaves=octaves,
                seed=seed,
                phase=evolution + float(time_ms) * 0.001 * speed,
            )
            noise = np.clip((noise - 0.5) * contrast + 0.5, 0.0, 1.0) * 255.0
            rgba[..., :3] = rgb * (1.0 - amount) + noise[..., None] * amount
        elif kind == "craft_style":
            rgba = _apply_craft_style(rgba, effect, time_ms)
        elif kind == "posterize":
            levels = max(2, min(64, int(round(float(_value(effect, "levels", time_ms, 8))))))
            amount = max(0.0, min(1.0, float(_value(effect, "amount", time_ms, 1.0))))
            quantized = np.rint(rgb / 255.0 * (levels - 1)) / (levels - 1) * 255.0
            rgba[..., :3] = rgb * (1.0 - amount) + quantized * amount
        elif kind == "directional_blur":
            length = max(0.0, min(200.0, float(_value(effect, "length", time_ms, 12.0))))
            angle = float(_value(effect, "angle", time_ms, 0.0))
            samples = max(2, min(32, int(_value(effect, "samples", time_ms, 8))))
            if length > 0.05:
                radians = np.deg2rad(angle)
                dx, dy = np.cos(radians) * length, np.sin(radians) * length
                accumulated = np.zeros_like(rgba)
                height, width = rgba.shape[:2]
                for index in range(samples):
                    amount = index / max(1, samples - 1) - 0.5
                    matrix = np.array(
                        [[1.0, 0.0, dx * amount], [0.0, 1.0, dy * amount]],
                        dtype=np.float32,
                    )
                    accumulated += cv2.warpAffine(
                        rgba, matrix, (width, height), flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
                    )
                rgba = accumulated / samples
        elif kind == "displacement":
            strength = max(0.0, min(300.0, float(_value(effect, "strength", time_ms, 16.0))))
            scale = max(2.0, min(1000.0, float(_value(effect, "scale", time_ms, 120.0))))
            speed = float(_value(effect, "speed", time_ms, 0.0))
            height, width = rgba.shape[:2]
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            phase = float(time_ms) * 0.001 * speed
            map_x = xx + np.sin(yy / scale * np.pi * 2.0 + phase) * strength
            map_y = yy + np.cos(xx / scale * np.pi * 2.0 - phase * 0.73) * strength
            rgba = cv2.remap(
                rgba, map_x, map_y, cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
            )
        elif kind == "corner_pin":
            height, width = rgba.shape[:2]
            amount = max(0.0, min(1.0, float(_value(effect, "amount", time_ms, 1.0))))
            offsets = []
            for name in ("top_left", "top_right", "bottom_right", "bottom_left"):
                value = _value(effect, name, time_ms, [0.0, 0.0])
                pair = list(value) if isinstance(value, (list, tuple)) else [0.0, 0.0]
                pair.extend([0.0, 0.0])
                offsets.append([float(pair[0]) * amount, float(pair[1]) * amount])
            source = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
            target = source + np.float32(offsets)
            matrix = cv2.getPerspectiveTransform(source, target)
            rgba = cv2.warpPerspective(
                rgba, matrix, (width, height), flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
            )
        elif kind == "mesh_warp":
            amplitude_x = max(-300.0, min(300.0, float(_value(effect, "amplitude_x", time_ms, 12.0))))
            amplitude_y = max(-300.0, min(300.0, float(_value(effect, "amplitude_y", time_ms, 8.0))))
            frequency_x = max(0.1, min(20.0, float(_value(effect, "frequency_x", time_ms, 1.0))))
            frequency_y = max(0.1, min(20.0, float(_value(effect, "frequency_y", time_ms, 1.0))))
            phase = float(_value(effect, "phase", time_ms, 0.0))
            height, width = rgba.shape[:2]
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            map_x = xx + np.sin((yy / max(1, height)) * np.pi * 2.0 * frequency_y + phase) * amplitude_x
            map_y = yy + np.sin((xx / max(1, width)) * np.pi * 2.0 * frequency_x + phase) * amplitude_y
            rgba = cv2.remap(
                rgba, map_x, map_y, cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
            )
        elif kind == "paper_fold":
            strength = max(0.0, min(1.0, float(_value(effect, "strength", time_ms, 0.35))))
            angle = np.deg2rad(float(_value(effect, "angle", time_ms, -18.0)))
            width_px = max(2.0, float(_value(effect, "width", time_ms, 38.0)))
            height, width = rgba.shape[:2]
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            centered = (xx - width * 0.5) * np.cos(angle) + (yy - height * 0.5) * np.sin(angle)
            ridge = np.exp(-np.square(centered / width_px))
            highlight = np.clip(centered / width_px, -1.0, 1.0) * ridge
            shade = 1.0 + highlight * strength
            rgba[..., :3] = rgb * shade[..., None]
        elif kind in {"chroma_key", "luma_key", "difference_key"}:
            from .keying import apply_keyer_rgba

            params = {
                key: _value(effect, key, time_ms, default)
                for key, default in {
                    "key_color": "#00ff00",
                    "similarity": 0.35,
                    "threshold": 0.5 if kind == "luma_key" else 0.12,
                    "softness": 0.1,
                    "choke": 0.0,
                    "feather": 0.0,
                    "despill": 0.5,
                    "key_bright": False,
                    "inverted": False,
                }.items()
            }
            reference_rgb = None
            if kind == "difference_key":
                reference_uri = str(_value(
                    effect,
                    "reference_uri",
                    time_ms,
                    "",
                ) or "")
                reference = QImage(reference_uri)
                if not reference.isNull():
                    reference_rgb = _rgba_array(reference)[..., :3]
                if reference_rgb is None:
                    continue
            rgba = apply_keyer_rgba(
                rgba,
                kind,
                params,
                reference_rgb=reference_rgb,
            ).rgba
        rgba = np.clip(rgba, 0, 255)
    return _qimage(rgba)
