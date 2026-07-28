"""Deterministic CPU effects shared by Motion Designer preview and export."""
from __future__ import annotations

from typing import Any
import math
from functools import lru_cache
from pathlib import Path

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


@lru_cache(maxsize=24)
def _craft_texture(uri: str, width: int, height: int, revision: str):
    del revision
    image = QImage(str(uri))
    if image.isNull():
        return None
    scaled = image.scaled(width, height)
    return _rgba_array(scaled).astype("float32")


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
    loop_period = max(0.1, float(_value(effect, "loop_period", time_ms, 4.0)))
    loop_time = (float(time_ms) * 0.001) % loop_period

    weave_frequency = max(0.0, float(_value(effect, "weave_frequency", time_ms, 0.8)))
    phase = loop_time * weave_frequency
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
    flicker_sample = int(math.floor(loop_time * flicker_frequency))
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
        grain_sample = int(math.floor(loop_time * cadence))
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

    source_alpha = rgba[..., 3] / 255.0
    artifact_cadence = max(1, int(round(loop_period * 12.0)))
    artifact_sample = int(math.floor(loop_time / loop_period * artifact_cadence))
    artifact_rng = np.random.default_rng(seed + artifact_sample * 130363)

    dust_amount = max(0.0, min(1.0, float(
        _value(effect, "dust_amount", time_ms, 0.015)
    ))) * amount
    scratch_amount = max(0.0, min(1.0, float(
        _value(effect, "scratch_amount", time_ms, 0.008)
    ))) * amount
    if dust_amount > 1e-6 or scratch_amount > 1e-6:
        artifacts = np.zeros((height, width), dtype=np.float32)
        dust_count = int(round(dust_amount * width * height / 220.0))
        for _ in range(min(500, dust_count)):
            x = int(artifact_rng.integers(0, max(1, width)))
            y = int(artifact_rng.integers(0, max(1, height)))
            radius = int(artifact_rng.integers(1, max(2, int(min(width, height) * 0.012))))
            cv2.circle(artifacts, (x, y), radius, float(artifact_rng.uniform(0.25, 1.0)), -1)
        scratch_count = int(round(scratch_amount * width / 3.0))
        for _ in range(min(80, scratch_count)):
            x = int(artifact_rng.integers(0, max(1, width)))
            y = int(artifact_rng.integers(0, max(1, height)))
            length = int(artifact_rng.integers(max(2, height // 12), max(3, height // 2)))
            cv2.line(
                artifacts,
                (x, y),
                (x + int(artifact_rng.integers(-2, 3)), min(height - 1, y + length)),
                float(artifact_rng.uniform(0.3, 0.85)),
                1,
            )
        artifacts *= source_alpha
        artifact_color = np.where(
            artifact_rng.random((height, width)) > 0.25,
            255.0,
            22.0,
        ).astype(np.float32)
        rgba[..., :3] = (
            rgba[..., :3] * (1.0 - artifacts[..., None] * 0.45)
            + artifact_color[..., None] * artifacts[..., None] * 0.45
        )

    misregistration = max(0.0, min(20.0, float(
        _value(effect, "misregistration", time_ms, 0.25)
    ))) * amount
    if misregistration > 1e-4:
        registered = rgba[..., :3].copy()
        for channel, direction in ((0, 1.0), (2, -1.0)):
            registered[..., channel] = cv2.warpAffine(
                rgba[..., channel],
                np.asarray([[1.0, 0.0, direction * misregistration], [0.0, 1.0, 0.0]], dtype=np.float32),
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )
        rgba[..., :3] = registered

    halation_amount = max(0.0, min(1.0, float(
        _value(effect, "halation_amount", time_ms, 0.05)
    ))) * amount
    if halation_amount > 1e-6:
        radius = max(0.1, float(_value(effect, "halation_radius", time_ms, 5.0)))
        luminance = (
            rgba[..., 0] * 0.2126 + rgba[..., 1] * 0.7152 + rgba[..., 2] * 0.0722
        )
        highlights = np.clip((luminance - 145.0) / 110.0, 0.0, 1.0) * source_alpha
        halo = cv2.GaussianBlur(highlights, (0, 0), sigmaX=radius, sigmaY=radius)
        rgba[..., 0] += halo * 255.0 * halation_amount
        rgba[..., 1] += halo * 72.0 * halation_amount

    warmth = max(-1.0, min(1.0, float(
        _value(effect, "warmth", time_ms, 0.06)
    ))) * amount
    if abs(warmth) > 1e-6:
        rgba[..., 0] *= 1.0 + warmth * 0.18
        rgba[..., 1] *= 1.0 + warmth * 0.035
        rgba[..., 2] *= 1.0 - warmth * 0.16

    vhs_amount = max(0.0, min(1.0, float(
        _value(effect, "vhs_amount", time_ms, 0.0)
    ))) * amount
    if vhs_amount > 1e-6:
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        wobble = np.sin(yy * 0.12 + loop_time * math.tau * 3.0) * vhs_amount * 4.0
        rgba = cv2.remap(
            rgba,
            xx + wobble,
            yy,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        scan = 1.0 - ((np.arange(height) % 3) == 0).astype(np.float32) * vhs_amount * 0.18
        rgba[..., :3] *= scan[:, None, None]

    edge_roughness = max(0.0, min(1.0, float(
        _value(effect, "edge_roughness", time_ms, 0.0)
    ))) * amount
    if edge_roughness > 1e-6:
        rough = _fractal_noise(
            height,
            width,
            scale=max(3.0, min(width, height) * 0.035),
            octaves=3,
            seed=seed + 991,
            phase=float(artifact_sample),
        )
        alpha = rgba[..., 3] / 255.0
        edge = cv2.morphologyEx(alpha, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
        rgba[..., 3] = np.clip(
            alpha - edge * np.clip((rough - 0.42) * 3.0, 0.0, 1.0) * edge_roughness,
            0.0,
            1.0,
        ) * 255.0

    texture = effect.metadata.get("texture")
    if isinstance(texture, dict):
        uri = str(texture.get("uri") or "")
        if uri:
            try:
                revision = str(Path(uri).stat().st_mtime_ns)
            except OSError:
                revision = str(texture.get("revision") or "")
            texture_rgba = _craft_texture(uri, width, height, revision)
            if texture_rgba is not None:
                texture_opacity = max(0.0, min(1.0, float(
                    texture.get("opacity", 0.25)
                ))) * amount * (texture_rgba[..., 3:4] / 255.0)
                texture_rgb = texture_rgba[..., :3]
                base = rgba[..., :3]
                blend_mode = str(texture.get("blend_mode") or "multiply").lower()
                if blend_mode == "screen":
                    blended = 255.0 - (255.0 - base) * (255.0 - texture_rgb) / 255.0
                elif blend_mode == "overlay":
                    blended = np.where(
                        base <= 127.5,
                        2.0 * base * texture_rgb / 255.0,
                        255.0 - 2.0 * (255.0 - base) * (255.0 - texture_rgb) / 255.0,
                    )
                else:
                    blended = base * texture_rgb / 255.0
                rgba[..., :3] = base * (1.0 - texture_opacity) + blended * texture_opacity
    return rgba


def _apply_painterly_look(rgba, effect: MotionEffectRef, time_ms: float):
    """Apply a temporally stable post-render painterly treatment."""
    import cv2
    import numpy as np

    amount = max(0.0, min(1.0, float(
        _value(effect, "amount", time_ms, 1.0)
    )))
    if amount <= 1e-6:
        return rgba
    full_source = rgba.copy()
    full_height, full_width = rgba.shape[:2]
    working_limit = max(320, int(round(float(
        _value(effect, "working_limit", time_ms, 480.0)
    ))))
    working_scale = min(
        1.0,
        working_limit / max(1, full_width, full_height),
    )
    if working_scale < 0.999:
        rgba = cv2.resize(
            rgba,
            (
                max(1, int(round(full_width * working_scale))),
                max(1, int(round(full_height * working_scale))),
            ),
            interpolation=cv2.INTER_AREA,
        )
    source = rgba.copy()
    alpha = source[..., 3:4].copy()
    rgb = source[..., :3].copy()
    height, width = rgb.shape[:2]

    smoothing = max(0.0, min(1.0, float(
        _value(effect, "smoothing", time_ms, 0.15)
    )))
    if smoothing > 1e-6:
        diameter = 3 + int(round(smoothing * 8.0)) * 2
        smooth = cv2.bilateralFilter(
            rgb.astype(np.uint8),
            diameter,
            12.0 + smoothing * 72.0,
            8.0 + smoothing * 52.0,
        ).astype(np.float32)
        rgb = rgb * (1.0 - smoothing) + smooth * smoothing

    toon_amount = max(0.0, min(1.0, float(
        _value(effect, "toon_amount", time_ms, 0.0)
    )))
    if toon_amount > 1e-6:
        levels = max(2, int(round(float(
            _value(effect, "color_levels", time_ms, 8.0)
        ))))
        step = 255.0 / max(1, levels - 1)
        quantized = np.round(rgb / step) * step
        rgb = rgb * (1.0 - toon_amount) + quantized * toon_amount

    seed = max(0, int(_value(effect, "seed", time_ms, 20260729)))
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    brush_amount = max(0.0, min(1.0, float(
        _value(effect, "brush_amount", time_ms, 0.0)
    )))
    granulation = max(0.0, min(1.0, float(
        _value(effect, "granulation", time_ms, 0.0)
    )))
    paper_amount = max(0.0, min(1.0, float(
        _value(effect, "paper_amount", time_ms, 0.0)
    )))
    if brush_amount > 1e-6 or granulation > 1e-6 or paper_amount > 1e-6:
        brush_scale = max(2.0, float(
            _value(effect, "brush_scale", time_ms, 18.0)
        ))
        phase = (seed % 997) / 997.0 * math.tau
        strokes = (
            np.sin((xx * 0.83 + yy * 0.37) / brush_scale * math.tau + phase)
            + np.sin((xx * -0.21 + yy * 0.94) / (brush_scale * 1.73) * math.tau - phase)
        ) * 0.25
        noise = _fractal_noise(
            height,
            width,
            scale=max(3.0, brush_scale * 0.72),
            octaves=4,
            seed=seed + 401,
            phase=0.0,
        ) - 0.5
        texture = strokes * brush_amount + noise * (
            granulation * 1.3 + paper_amount * 0.7
        )
        rgb *= np.clip(1.0 + texture[..., None] * 0.25, 0.72, 1.24)
        if paper_amount > 1e-6:
            paper_color = _color(
                effect.metadata.get("paper_color"),
                "#f1ead9",
            )
            paper_mix = np.clip(
                (noise + 0.5)[..., None] * paper_amount * 0.18,
                0.0,
                0.22,
            )
            rgb = rgb * (1.0 - paper_mix) + paper_color * paper_mix

    luminance = (
        rgb[..., 0] * 0.2126
        + rgb[..., 1] * 0.7152
        + rgb[..., 2] * 0.0722
    )
    hatch_amount = max(0.0, min(1.0, float(
        _value(effect, "hatch_amount", time_ms, 0.0)
    )))
    if hatch_amount > 1e-6:
        spacing = max(2.0, float(
            _value(effect, "hatch_spacing", time_ms, 9.0)
        ))
        hatch_a = ((xx + yy * 0.62 + seed % 19) % spacing) < 1.2
        hatch_b = ((xx - yy * 0.62 + seed % 23) % (spacing * 1.17)) < 1.0
        shadow = np.clip((138.0 - luminance) / 138.0, 0.0, 1.0)
        hatch = (
            hatch_a.astype(np.float32)
            + hatch_b.astype(np.float32) * (shadow > 0.55)
        ) * shadow * hatch_amount
        line_color = _color(effect.metadata.get("line_color"), "#17202a")
        rgb = rgb * (1.0 - hatch[..., None] * 0.46) + (
            line_color * hatch[..., None] * 0.46
        )

    edge_strength = max(0.0, min(2.0, float(
        _value(effect, "edge_strength", time_ms, 0.0)
    )))
    if edge_strength > 1e-6:
        gray = luminance.astype(np.float32) / 255.0
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        gradient = np.sqrt(gx * gx + gy * gy)
        threshold = max(0.0, min(1.0, float(
            _value(effect, "edge_threshold", time_ms, 0.18)
        )))
        softness = max(0.001, min(1.0, float(
            _value(effect, "edge_softness", time_ms, 0.08)
        )))
        edge = np.clip((gradient - threshold) / softness, 0.0, 1.0)
        edge *= edge_strength * (alpha[..., 0] / 255.0)
        line_color = _color(effect.metadata.get("line_color"), "#17202a")
        rgb = rgb * (1.0 - edge[..., None]) + line_color * edge[..., None]

    projection = effect.metadata.get("projected_texture")
    if isinstance(projection, dict):
        uri = str(projection.get("uri") or "")
        if uri:
            try:
                revision = str(Path(uri).stat().st_mtime_ns)
            except OSError:
                revision = str(projection.get("revision") or "")
            texture = _craft_texture(uri, width, height, revision)
            if texture is not None:
                opacity = max(0.0, min(1.0, float(
                    projection.get("opacity", 0.25)
                )))
                texture_alpha = texture[..., 3:4] / 255.0 * opacity
                texture_rgb = texture[..., :3]
                mode = str(projection.get("blend_mode") or "multiply").lower()
                if mode == "screen":
                    blended = 255.0 - (255.0 - rgb) * (255.0 - texture_rgb) / 255.0
                elif mode == "overlay":
                    blended = np.where(
                        rgb <= 127.5,
                        2.0 * rgb * texture_rgb / 255.0,
                        255.0 - 2.0 * (255.0 - rgb) * (255.0 - texture_rgb) / 255.0,
                    )
                else:
                    blended = rgb * texture_rgb / 255.0
                rgb = rgb * (1.0 - texture_alpha) + blended * texture_alpha

    result_rgb = source[..., :3] * (1.0 - amount) + rgb * amount
    if working_scale < 0.999:
        result = full_source
        result[..., :3] = cv2.resize(
            result_rgb,
            (full_width, full_height),
            interpolation=cv2.INTER_LINEAR,
        )
        result[..., 3:4] = full_source[..., 3:4]
        return result
    rgba[..., :3] = result_rgb
    rgba[..., 3:4] = alpha
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
        elif kind == "painterly_look":
            rgba = _apply_painterly_look(rgba, effect, time_ms)
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
        elif kind == "scan_cleanup":
            white_balance = max(0.0, min(1.0, float(
                _value(effect, "white_balance", time_ms, 0.8)
            )))
            paper_remove = max(0.0, min(1.0, float(
                _value(effect, "paper_remove", time_ms, 0.0)
            )))
            ink_preserve = max(0.0, min(1.0, float(
                _value(effect, "ink_preserve", time_ms, 0.75)
            )))
            threshold = max(0.05, min(0.98, float(
                _value(effect, "threshold", time_ms, 0.72)
            )))
            luminance = (
                rgb[..., 0] * 0.2126
                + rgb[..., 1] * 0.7152
                + rgb[..., 2] * 0.0722
            )
            bright = luminance >= np.percentile(luminance, 78.0)
            if np.any(bright):
                paper_color = np.maximum(
                    np.median(rgb[bright], axis=0),
                    24.0,
                )
                balanced = np.clip(
                    rgb * (245.0 / paper_color)[None, None, :],
                    0.0,
                    255.0,
                )
                rgba[..., :3] = (
                    rgb * (1.0 - white_balance)
                    + balanced * white_balance
                )
            cleaned_rgb = rgba[..., :3]
            cleaned_luma = (
                cleaned_rgb[..., 0] * 0.2126
                + cleaned_rgb[..., 1] * 0.7152
                + cleaned_rgb[..., 2] * 0.0722
            ) / 255.0
            ink = np.clip(
                (threshold - cleaned_luma) / max(0.02, threshold * 0.55),
                0.0,
                1.0,
            )
            if ink_preserve > 0.0:
                rgba[..., :3] *= (
                    1.0 - ink[..., None] * ink_preserve * 0.18
                )
            if paper_remove > 0.0:
                source_alpha = rgba[..., 3] / 255.0
                retained = np.clip(
                    ink * (1.0 + ink_preserve * 0.7),
                    0.0,
                    1.0,
                )
                retained = cv2.GaussianBlur(
                    retained,
                    (0, 0),
                    sigmaX=0.55,
                    sigmaY=0.55,
                )
                rgba[..., 3] = (
                    source_alpha
                    * ((1.0 - paper_remove) + retained * paper_remove)
                    * 255.0
                )
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
