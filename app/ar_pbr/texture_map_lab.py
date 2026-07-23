"""Image-to-PBR texture map lab for AR/PBR and Unreal exports.

The functions in this module are deliberately UI-free.  The editor window,
Python Actions, tests, and future MCP tools can all call the same deterministic
map generator and export code.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import math
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

from app.ar_pbr.pbr_math import material_f0


SCHEMA_ID = "tigerstudio.ar_pbr.texture_map_lab.v1"
DEFAULT_SEPARATE_MAPS: tuple[str, ...] = (
    "base_color",
    "normal",
    "ao",
    "roughness",
    "metallic",
    "height",
    "cavity",
)
DEFAULT_PACKED_LAYOUTS: tuple[str, ...] = ("unreal_orm", "gltf_mr")
PREVIEW_MODES: tuple[str, ...] = (
    "material",
    "base_color",
    "normal",
    "ao",
    "roughness",
    "metallic",
    "height",
    "cavity",
    "unreal_orm",
    "arm",
    "gltf_mr",
)
PACKED_LAYOUTS: tuple[str, ...] = ("unreal_orm", "orm", "arm", "rma", "gltf_mr")
NORMAL_FORMATS: tuple[str, ...] = ("unreal_directx", "directx", "opengl")
UNREAL_TEXTURE_IMPORT_SETTINGS: dict[str, dict[str, Any]] = {
    "base_color": {"sRGB": True, "compression": "Default"},
    "normal": {"sRGB": False, "compression": "TC_Normalmap"},
    "ao": {"sRGB": False, "compression": "TC_Alpha or TC_Masks"},
    "roughness": {"sRGB": False, "compression": "TC_Alpha or TC_Masks"},
    "metallic": {"sRGB": False, "compression": "TC_Alpha or TC_Masks"},
    "height": {"sRGB": False, "compression": "Grayscale"},
    "cavity": {"sRGB": False, "compression": "Grayscale"},
    "unreal_orm": {"sRGB": False, "compression": "TC_Masks", "channels": "R=AO, G=Roughness, B=Metallic"},
    "orm": {"sRGB": False, "compression": "TC_Masks", "channels": "R=AO, G=Roughness, B=Metallic"},
    "arm": {"sRGB": False, "compression": "TC_Masks", "channels": "R=AO, G=Roughness, B=Metallic"},
    "rma": {"sRGB": False, "compression": "TC_Masks", "channels": "R=Roughness, G=Metallic, B=AO"},
    "gltf_mr": {"sRGB": False, "compression": "TC_Masks", "channels": "R=Unused, G=Roughness, B=Metallic"},
}


@dataclass(frozen=True)
class TextureMapLabSettings:
    schema_id: str = SCHEMA_ID
    normal_strength: float = 2.4
    normal_radius_px: float = 1.8
    normal_format: str = "unreal_directx"
    height_invert: bool = False
    height_contrast: float = 1.1
    height_blur_px: float = 0.35
    ao_strength: float = 0.82
    ao_radius_px: float = 8.0
    cavity_strength: float = 0.5
    roughness_bias: float = 0.55
    roughness_contrast: float = 0.95
    roughness_detail: float = 0.34
    metallic_value: float = 0.0
    metallic_threshold: float = 1.1
    metallic_softness: float = 0.08
    base_color_exposure: float = 0.0
    base_color_contrast: float = 1.0
    preview_light_azimuth: float = 38.0
    preview_light_elevation: float = 48.0
    preview_environment: float = 0.42


def clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    if math.isnan(number) or math.isinf(number):
        number = float(default)
    return max(float(minimum), min(float(maximum), number))


def normalize_texture_map_settings(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(settings or {})
    defaults = TextureMapLabSettings()
    normal_format = str(raw.get("normal_format", defaults.normal_format) or defaults.normal_format).strip().lower()
    if normal_format not in NORMAL_FORMATS:
        normal_format = defaults.normal_format
    return {
        "schema_id": SCHEMA_ID,
        "normal_strength": clamp_float(raw.get("normal_strength"), 0.0, 12.0, defaults.normal_strength),
        "normal_radius_px": clamp_float(raw.get("normal_radius_px"), 0.0, 24.0, defaults.normal_radius_px),
        "normal_format": normal_format,
        "height_invert": bool(raw.get("height_invert", defaults.height_invert)),
        "height_contrast": clamp_float(raw.get("height_contrast"), 0.1, 4.0, defaults.height_contrast),
        "height_blur_px": clamp_float(raw.get("height_blur_px"), 0.0, 8.0, defaults.height_blur_px),
        "ao_strength": clamp_float(raw.get("ao_strength"), 0.0, 3.0, defaults.ao_strength),
        "ao_radius_px": clamp_float(raw.get("ao_radius_px"), 0.0, 64.0, defaults.ao_radius_px),
        "cavity_strength": clamp_float(raw.get("cavity_strength"), 0.0, 2.0, defaults.cavity_strength),
        "roughness_bias": clamp_float(raw.get("roughness_bias"), 0.0, 1.0, defaults.roughness_bias),
        "roughness_contrast": clamp_float(raw.get("roughness_contrast"), 0.1, 3.0, defaults.roughness_contrast),
        "roughness_detail": clamp_float(raw.get("roughness_detail"), 0.0, 1.0, defaults.roughness_detail),
        "metallic_value": clamp_float(raw.get("metallic_value"), 0.0, 1.0, defaults.metallic_value),
        "metallic_threshold": clamp_float(raw.get("metallic_threshold"), 0.0, 1.5, defaults.metallic_threshold),
        "metallic_softness": clamp_float(raw.get("metallic_softness"), 0.001, 0.5, defaults.metallic_softness),
        "base_color_exposure": clamp_float(raw.get("base_color_exposure"), -3.0, 3.0, defaults.base_color_exposure),
        "base_color_contrast": clamp_float(raw.get("base_color_contrast"), 0.1, 3.0, defaults.base_color_contrast),
        "preview_light_azimuth": clamp_float(
            raw.get("preview_light_azimuth"),
            -360.0,
            360.0,
            defaults.preview_light_azimuth,
        ),
        "preview_light_elevation": clamp_float(
            raw.get("preview_light_elevation"),
            3.0,
            89.0,
            defaults.preview_light_elevation,
        ),
        "preview_environment": clamp_float(raw.get("preview_environment"), 0.0, 1.5, defaults.preview_environment),
    }


def default_texture_map_settings() -> dict[str, Any]:
    return asdict(TextureMapLabSettings())


def _as_float_image(image: Image.Image) -> np.ndarray:
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    return np.clip(arr, 0.0, 1.0).astype(np.float32)


def _to_u8(array: Any) -> np.ndarray:
    return np.clip(np.asarray(array, dtype=np.float32) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _to_rgb_image(array: Any) -> Image.Image:
    arr = np.asarray(array)
    if arr.ndim == 2:
        arr = np.dstack([arr, arr, arr])
    return Image.fromarray(_to_u8(arr[..., :3]), mode="RGB")


def _to_l_image(array: Any) -> Image.Image:
    return Image.fromarray(_to_u8(array), mode="L")


def _array_from_l(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("L"), dtype=np.float32) / 255.0


def _resize_for_max_size(image: Image.Image, max_size: int | None) -> Image.Image:
    if not max_size:
        return image
    size = max(8, int(max_size))
    w, h = image.size
    longest = max(w, h)
    if longest <= size:
        return image
    scale = size / float(longest)
    new_size = (max(8, int(round(w * scale))), max(8, int(round(h * scale))))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def _blur_float(array: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0.001:
        return np.asarray(array, dtype=np.float32)
    return _array_from_l(_to_l_image(array).filter(ImageFilter.GaussianBlur(float(radius))))


def _contrast_gray(array: np.ndarray, contrast: float, midpoint: float = 0.5) -> np.ndarray:
    return np.clip((np.asarray(array, dtype=np.float32) - midpoint) * float(contrast) + midpoint, 0.0, 1.0)


def _gradient_from_height(height: np.ndarray, radius_px: float) -> tuple[np.ndarray, np.ndarray]:
    radius = max(1, int(round(radius_px)))
    if radius <= 1:
        dy, dx = np.gradient(height.astype(np.float32))
        return dx, dy
    right = np.roll(height, -radius, axis=1)
    left = np.roll(height, radius, axis=1)
    down = np.roll(height, -radius, axis=0)
    up = np.roll(height, radius, axis=0)
    denom = max(1.0, float(radius * 2))
    return (right - left) / denom, (down - up) / denom


def _height_from_source(rgb: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    height = _contrast_gray(luma, float(settings["height_contrast"]))
    blur = float(settings["height_blur_px"])
    if blur > 0.001:
        height = _blur_float(height, blur)
    if bool(settings["height_invert"]):
        height = 1.0 - height
    return np.clip(height, 0.0, 1.0).astype(np.float32)


def _normal_from_height(height: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    dx, dy = _gradient_from_height(height, float(settings["normal_radius_px"]))
    strength = float(settings["normal_strength"])
    nx = -dx * strength
    ny = -dy * strength
    if str(settings["normal_format"]) in {"unreal_directx", "directx"}:
        ny = -ny
    nz = np.ones_like(height, dtype=np.float32)
    n = np.dstack([nx, ny, nz]).astype(np.float32)
    length = np.linalg.norm(n, axis=2, keepdims=True)
    n = n / np.maximum(length, 1.0e-6)
    return np.clip(n * 0.5 + 0.5, 0.0, 1.0).astype(np.float32)


def _ao_from_height(height: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    radius = float(settings["ao_radius_px"])
    if radius <= 0.001:
        return np.ones_like(height, dtype=np.float32)
    local = _blur_float(height, radius)
    shadow = np.clip(local - height, 0.0, 1.0)
    ao = 1.0 - shadow * float(settings["ao_strength"]) * 2.2
    return np.clip(ao, 0.0, 1.0).astype(np.float32)


def _cavity_from_height(height: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    local = _blur_float(height, max(1.0, float(settings["normal_radius_px"]) * 1.6))
    detail = np.abs(height - local)
    cavity = 1.0 - np.clip(detail * 3.0 * float(settings["cavity_strength"]), 0.0, 1.0)
    return np.clip(cavity, 0.0, 1.0).astype(np.float32)


def _roughness_from_source(rgb: np.ndarray, height: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    local = _blur_float(luma, max(1.0, float(settings["normal_radius_px"]) * 2.5))
    detail = np.abs(luma - local)
    rough = float(settings["roughness_bias"]) + (0.5 - height) * 0.22
    rough += detail * float(settings["roughness_detail"]) * 1.3
    rough = _contrast_gray(rough, float(settings["roughness_contrast"]), midpoint=float(settings["roughness_bias"]))
    return np.clip(rough, 0.04, 1.0).astype(np.float32)


def _metallic_from_source(rgb: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    base = np.full(rgb.shape[:2], float(settings["metallic_value"]), dtype=np.float32)
    threshold = float(settings["metallic_threshold"])
    if threshold >= 1.0:
        return np.clip(base, 0.0, 1.0)
    saturation = np.max(rgb, axis=2) - np.min(rgb, axis=2)
    brightness = np.max(rgb, axis=2)
    metal_signal = np.clip((brightness - threshold) / float(settings["metallic_softness"]), 0.0, 1.0)
    metal_signal *= np.clip((0.32 - saturation) / 0.32, 0.0, 1.0)
    return np.clip(np.maximum(base, metal_signal), 0.0, 1.0).astype(np.float32)


def _base_color_from_source(image: Image.Image, settings: Mapping[str, Any]) -> np.ndarray:
    exposure = float(settings["base_color_exposure"])
    contrast = float(settings["base_color_contrast"])
    adjusted = ImageEnhance.Brightness(image.convert("RGB")).enhance(2.0**exposure)
    adjusted = ImageEnhance.Contrast(adjusted).enhance(contrast)
    return _as_float_image(adjusted)


def generate_texture_maps(
    image_path: str | Path,
    settings: Mapping[str, Any] | None = None,
    *,
    max_size: int | None = None,
) -> dict[str, Any]:
    """Generate base, scalar, normal, and packed-ready PBR maps from an image."""
    path = Path(image_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(str(path))
    normalized = normalize_texture_map_settings(settings)
    image = _resize_for_max_size(Image.open(path).convert("RGB"), max_size)
    base_color = _base_color_from_source(image, normalized)
    height = _height_from_source(base_color, normalized)
    normal = _normal_from_height(height, normalized)
    ao = _ao_from_height(height, normalized)
    cavity = _cavity_from_height(height, normalized)
    roughness = _roughness_from_source(base_color, height, normalized)
    metallic = _metallic_from_source(base_color, normalized)
    maps = {
        "base_color": base_color,
        "height": height,
        "normal": normal,
        "ao": ao,
        "roughness": roughness,
        "metallic": metallic,
        "cavity": cavity,
    }
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(path),
        "settings": normalized,
        "size": [int(image.size[0]), int(image.size[1])],
        "maps": maps,
        "diagnostics": _map_diagnostics(maps),
    }


def _map_diagnostics(maps: Mapping[str, np.ndarray]) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for key, value in maps.items():
        arr = np.asarray(value, dtype=np.float32)
        rows[key] = {
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
        }
    return rows


def pack_texture_channels(maps: Mapping[str, np.ndarray], layout: str) -> np.ndarray:
    """Return an RGB packed texture in floating point 0..1 form."""
    name = str(layout or "unreal_orm").strip().lower()
    if name not in PACKED_LAYOUTS:
        raise ValueError(f"unknown packed texture layout: {layout}")
    ao = np.asarray(maps["ao"], dtype=np.float32)
    roughness = np.asarray(maps["roughness"], dtype=np.float32)
    metallic = np.asarray(maps["metallic"], dtype=np.float32)
    unused = np.ones_like(roughness, dtype=np.float32)
    if name in {"unreal_orm", "orm", "arm"}:
        return np.dstack([ao, roughness, metallic]).astype(np.float32)
    if name == "rma":
        return np.dstack([roughness, metallic, ao]).astype(np.float32)
    return np.dstack([unused, roughness, metallic]).astype(np.float32)


def texture_map_to_image(map_name: str, value: np.ndarray) -> Image.Image:
    if map_name == "normal":
        return _to_rgb_image(value)
    if np.asarray(value).ndim == 3:
        return _to_rgb_image(value)
    return _to_l_image(value)


def packed_layout_metadata(layout: str) -> dict[str, Any]:
    name = str(layout or "unreal_orm").strip().lower()
    if name not in PACKED_LAYOUTS:
        raise ValueError(f"unknown packed texture layout: {layout}")
    channels = {
        "unreal_orm": {"R": "ambient_occlusion", "G": "roughness", "B": "metallic"},
        "orm": {"R": "ambient_occlusion", "G": "roughness", "B": "metallic"},
        "arm": {"R": "ambient_occlusion", "G": "roughness", "B": "metallic"},
        "rma": {"R": "roughness", "G": "metallic", "B": "ambient_occlusion"},
        "gltf_mr": {"R": "unused_white", "G": "roughness", "B": "metallic"},
    }[name]
    return {
        "layout": name,
        "channels": channels,
        "unreal_import": dict(UNREAL_TEXTURE_IMPORT_SETTINGS[name]),
    }


def substrate_export_plan(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_texture_map_settings(settings)
    directx_normal = str(normalized["normal_format"]) in {"unreal_directx", "directx"}
    return {
        "schema_id": f"{SCHEMA_ID}.unreal_substrate",
        "target": "Unreal Engine Substrate Slab BSDF",
        "legacy_pbr_compatibility": True,
        "normal": {
            "format": normalized["normal_format"],
            "unreal_default": directx_normal,
            "flip_green_channel_for_unreal": not directx_normal,
            "texture_compression": "TC_Normalmap",
        },
        "base_color_workflow": {
            "legacy_default_lit": {
                "base_color": "base_color",
                "metallic": "metallic or packed.B",
                "roughness": "roughness or packed.G",
                "normal": "normal",
                "ambient_occlusion": "ao or packed.R",
            },
            "substrate": {
                "helper": "Substrate Metalness-To-DiffuseAlbedo-F0",
                "helper_inputs": {
                    "BaseColor": "base_color",
                    "Specular": 0.5,
                    "Metallic": "metallic or packed.B",
                },
                "slab_inputs": {
                    "DiffuseAlbedo": "helper.DiffuseAlbedo",
                    "F0": "helper.F0",
                    "Roughness": "roughness or packed.G",
                    "Normal": "normal",
                },
                "root_or_material_inputs": {
                    "AmbientOcclusion": "ao or packed.R",
                },
            },
        },
        "packed_layouts": {
            name: packed_layout_metadata(name) for name in ("unreal_orm", "arm", "gltf_mr", "rma")
        },
        "future_substrate_optional_maps": {
            "F90": "edge-color/grazing response map, not generated by the base image lab",
            "SecondRoughness": "dual-lobe surface map for complex coatings",
            "Anisotropy": "anisotropy scalar plus tangent direction map",
            "Fuzz": "cloth/fiber fuzz amount, color, and roughness",
            "Glint": "sparkle/glint mask for microfacets",
        },
    }


def render_plane_preview(
    image_path: str | Path,
    settings: Mapping[str, Any] | None = None,
    *,
    preview_mode: str = "material",
    output_path: str | Path | None = None,
    width: int = 768,
    height: int | None = None,
) -> dict[str, Any]:
    mode = str(preview_mode or "material").strip().lower()
    if mode not in PREVIEW_MODES:
        raise ValueError(f"unknown preview mode: {preview_mode}")
    w = max(64, int(width or 768))
    if height is not None:
        h = max(64, int(height))
    else:
        h = 0
    result = generate_texture_maps(image_path, settings, max_size=w)
    maps = result["maps"]
    preview = _preview_array_for_mode(maps, result["settings"], mode)
    preview_img = _to_rgb_image(preview)
    target_w = w
    target_h = h if h else max(64, int(round(preview_img.height * (target_w / max(1, preview_img.width)))))
    if preview_img.size != (target_w, target_h):
        preview_img = preview_img.resize((target_w, target_h), Image.Resampling.BICUBIC)
    if output_path is None:
        out = Path(image_path).expanduser().with_name(f"{Path(image_path).stem}_pbr_plane_preview_{mode}.png")
    else:
        out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    preview_img.save(out)
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(Path(image_path).expanduser()),
        "preview_path": str(out),
        "preview_mode": mode,
        "size": [int(preview_img.size[0]), int(preview_img.size[1])],
        "settings": result["settings"],
        "diagnostics": result["diagnostics"],
        "substrate": substrate_export_plan(result["settings"]),
    }


def _preview_array_for_mode(maps: Mapping[str, np.ndarray], settings: Mapping[str, Any], mode: str) -> np.ndarray:
    if mode in maps:
        value = np.asarray(maps[mode], dtype=np.float32)
        if value.ndim == 2:
            return np.dstack([value, value, value]).astype(np.float32)
        return value.astype(np.float32)
    if mode in PACKED_LAYOUTS:
        return pack_texture_channels(maps, mode)
    base = np.asarray(maps["base_color"], dtype=np.float32)
    normal_tex = np.asarray(maps["normal"], dtype=np.float32)
    normal = normal_tex * 2.0 - 1.0
    normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1.0e-6)
    az = math.radians(float(settings["preview_light_azimuth"]))
    el = math.radians(float(settings["preview_light_elevation"]))
    light = np.array([math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)], dtype=np.float32)
    light /= max(float(np.linalg.norm(light)), 1.0e-6)
    view = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    half_vec = light + view
    half_vec /= max(float(np.linalg.norm(half_vec)), 1.0e-6)
    ndotl = np.clip(np.sum(normal * light[None, None, :], axis=2), 0.0, 1.0)
    ndotv = np.clip(normal[..., 2], 0.0, 1.0)
    ndoth = np.clip(np.sum(normal * half_vec[None, None, :], axis=2), 0.0, 1.0)
    vdoth = float(np.clip(np.dot(view, half_vec), 0.0, 1.0))
    roughness = np.asarray(maps["roughness"], dtype=np.float32)
    metallic = np.asarray(maps["metallic"], dtype=np.float32)
    ao = np.asarray(maps["ao"], dtype=np.float32)
    f0 = material_f0(base, metallic, 0.5)
    # Inline a simplified preview BRDF so the plane render remains responsive.
    alpha = np.maximum(roughness * roughness, 0.001)
    alpha2 = alpha * alpha
    denom = np.maximum(ndoth * ndoth * (alpha2 - 1.0) + 1.0, 1.0e-5)
    d = alpha2 / np.maximum(np.pi * denom * denom, 1.0e-5)
    k = ((roughness + 1.0) * (roughness + 1.0)) / 8.0
    gv = ndotv / np.maximum(ndotv * (1.0 - k) + k, 1.0e-5)
    gl = ndotl / np.maximum(ndotl * (1.0 - k) + k, 1.0e-5)
    fresnel = f0 + (1.0 - f0) * ((1.0 - vdoth) ** 5.0)
    diffuse = (1.0 - fresnel) * (1.0 - metallic[..., None]) * base / np.pi
    specular = (d[..., None] * gv[..., None] * gl[..., None] * fresnel) / np.maximum(
        4.0 * ndotv[..., None] * ndotl[..., None],
        1.0e-5,
    )
    lit = (diffuse + specular) * ndotl[..., None] * 2.2
    env = base * float(settings["preview_environment"]) * ao[..., None]
    preview = env + lit * ao[..., None]
    return np.clip(preview, 0.0, 1.0).astype(np.float32)


def export_texture_maps(
    image_path: str | Path,
    output_dir: str | Path | None = None,
    settings: Mapping[str, Any] | None = None,
    *,
    maps: Sequence[str] | None = None,
    packed_layouts: Sequence[str] | None = None,
    max_size: int | None = None,
) -> dict[str, Any]:
    path = Path(image_path).expanduser()
    if output_dir is None:
        out_dir = path.with_name(f"{path.stem}_pbr_maps")
    else:
        out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = generate_texture_maps(path, settings, max_size=max_size)
    map_names = _normalize_name_list(maps, DEFAULT_SEPARATE_MAPS)
    layout_names = _normalize_name_list(packed_layouts, DEFAULT_PACKED_LAYOUTS)
    files: dict[str, str] = {}
    for name in map_names:
        if name not in generated["maps"]:
            raise ValueError(f"unknown texture map: {name}")
        file_path = out_dir / f"{path.stem}_{name}.png"
        texture_map_to_image(name, generated["maps"][name]).save(file_path)
        files[name] = str(file_path)
    packed_files: dict[str, str] = {}
    packed_meta: dict[str, Any] = {}
    for layout in layout_names:
        packed = pack_texture_channels(generated["maps"], layout)
        file_path = out_dir / f"{path.stem}_{layout}.png"
        _to_rgb_image(packed).save(file_path)
        packed_files[layout] = str(file_path)
        packed_meta[layout] = packed_layout_metadata(layout)
    manifest = {
        "schema_id": SCHEMA_ID,
        "source_path": str(path),
        "output_dir": str(out_dir),
        "size": generated["size"],
        "settings": generated["settings"],
        "files": files,
        "packed_files": packed_files,
        "packed_layouts": packed_meta,
        "unreal_texture_import_settings": {
            name: UNREAL_TEXTURE_IMPORT_SETTINGS[name] for name in files if name in UNREAL_TEXTURE_IMPORT_SETTINGS
        },
        "substrate": substrate_export_plan(generated["settings"]),
        "diagnostics": generated["diagnostics"],
    }
    manifest_path = out_dir / f"{path.stem}_pbr_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(path),
        "output_dir": str(out_dir),
        "manifest_path": str(manifest_path),
        "files": files,
        "packed_files": packed_files,
        "size": generated["size"],
        "settings": generated["settings"],
        "substrate": manifest["substrate"],
        "diagnostics": generated["diagnostics"],
    }


def _normalize_name_list(values: Sequence[str] | None, defaults: Sequence[str]) -> list[str]:
    rows = list(values or defaults)
    out: list[str] = []
    for row in rows:
        name = str(row or "").strip().lower()
        if name and name not in out:
            out.append(name)
    return out
