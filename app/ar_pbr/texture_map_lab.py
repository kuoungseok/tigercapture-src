"""Image-to-PBR texture map lab for AR/PBR and Unreal exports.

The functions in this module are deliberately UI-free.  The editor window,
Python Actions, tests, and future MCP tools can all call the same deterministic
map generator and export code.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import importlib.util
from pathlib import Path
import json
import math
import os
import sys
from typing import Any, Mapping, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from app.ar_pbr.pbr_math import (
    fresnel_schlick_f90,
    material_f0,
    substrate_f90,
    substrate_metalness_to_diffuse_albedo_f0,
)


SCHEMA_ID = "tigerstudio.ar_pbr.texture_map_lab.v1"
DEFAULT_SEPARATE_MAPS: tuple[str, ...] = (
    "base_color",
    "normal",
    "ao",
    "roughness",
    "metallic",
    "height",
    "cavity",
    "curvature",
)
ANALYSIS_MAPS: tuple[str, ...] = (
    "base_color_source",
    "irradiance",
    "delight_shading",
)
OPTIONAL_SUBSTRATE_MAPS: tuple[str, ...] = (
    "f0",
    "f90_mask",
)
SEPARATE_MAPS: tuple[str, ...] = DEFAULT_SEPARATE_MAPS + OPTIONAL_SUBSTRATE_MAPS + ANALYSIS_MAPS
DEFAULT_PACKED_LAYOUTS: tuple[str, ...] = ("unreal_orm", "gltf_mr")
PREVIEW_MODES: tuple[str, ...] = (
    "material",
    "intrinsic_channels",
    "albedo",
    "delight_compare",
    "base_color_source",
    "base_color",
    "normal",
    "ao",
    "roughness",
    "metallic",
    "irradiance",
    "delight_shading",
    "height",
    "cavity",
    "curvature",
    "f0",
    "f90_mask",
    "unreal_orm",
    "arm",
    "gltf_mr",
)
PREVIEW_SHAPES: tuple[str, ...] = ("plane", "sphere")
PACKED_LAYOUTS: tuple[str, ...] = ("unreal_orm", "orm", "arm", "rma", "gltf_mr")
NORMAL_FORMATS: tuple[str, ...] = ("unreal_directx", "directx", "opengl")
AO_ALGORITHMS: tuple[str, ...] = ("heightfield_horizon", "legacy_blur")
TEXTURE_MAP_BACKENDS: tuple[str, ...] = ("auto", "cpu", "torch_cuda", "cupy", "opencv_cuda")
TORCH_CUDA_WHEEL_INDEX_URL = "https://download.pytorch.org/whl/cu128"
PREVIEW_ONLY_SETTING_KEYS = frozenset(
    {
        "preview_light_azimuth",
        "preview_light_elevation",
        "preview_environment",
        "preview_animate_light",
    }
)


class TextureMapGpuRequiredError(RuntimeError):
    """Raised when Texture Lab is asked to render without a GPU backend."""
UNREAL_TEXTURE_IMPORT_SETTINGS: dict[str, dict[str, Any]] = {
    "base_color": {"sRGB": True, "compression": "Default"},
    "normal": {"sRGB": False, "compression": "TC_Normalmap"},
    "ao": {"sRGB": False, "compression": "TC_Alpha or TC_Masks"},
    "roughness": {"sRGB": False, "compression": "TC_Alpha or TC_Masks"},
    "metallic": {"sRGB": False, "compression": "TC_Alpha or TC_Masks"},
    "height": {"sRGB": False, "compression": "Grayscale"},
    "cavity": {"sRGB": False, "compression": "Grayscale"},
    "curvature": {"sRGB": False, "compression": "Grayscale"},
    "f0": {"sRGB": False, "compression": "Default", "usage": "Optional Substrate direct F0 override"},
    "f90_mask": {"sRGB": False, "compression": "Grayscale", "usage": "Optional Substrate grazing/F90 mask"},
    "base_color_source": {
        "sRGB": True,
        "compression": "Default",
        "usage": "Diagnostic source BaseColor before de-light/albedo recovery",
    },
    "irradiance": {
        "sRGB": False,
        "compression": "Grayscale",
        "usage": "Diagnostic estimated low-frequency irradiance / baked lighting field",
    },
    "delight_shading": {
        "sRGB": False,
        "compression": "Grayscale",
        "usage": "Diagnostic estimated illumination removed from BaseColor",
    },
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
    edge_aware_smoothing: bool = True
    edge_aware_sensitivity: float = 9.0
    normal_filter: str = "sobel"
    ao_strength: float = 0.82
    ao_radius_px: float = 8.0
    ao_algorithm: str = "heightfield_horizon"
    ao_samples: int = 8
    ao_steps: int = 8
    ao_height_scale: float = 14.0
    ao_multiscale: bool = True
    cavity_strength: float = 0.5
    cavity_radius_px: float = 2.2
    curvature_strength: float = 1.25
    roughness_bias: float = 0.55
    roughness_contrast: float = 0.95
    roughness_detail: float = 0.34
    metallic_value: float = 0.0
    metallic_threshold: float = 1.1
    metallic_softness: float = 0.08
    delight_enabled: bool = False
    delight_strength: float = 0.65
    delight_radius_px: float = 42.0
    delight_contrast_preservation: float = 0.25
    substrate_enabled: bool = False
    substrate_mode: str = "off"
    substrate_reflectance: float = 0.5
    f90_mask_strength: float = 0.45
    base_color_exposure: float = 0.0
    base_color_contrast: float = 1.0
    preview_light_azimuth: float = -45.0
    preview_light_elevation: float = 45.0
    preview_environment: float = 0.32
    preview_animate_light: bool = False


def clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    if math.isnan(number) or math.isinf(number):
        number = float(default)
    return max(float(minimum), min(float(maximum), number))


def bool_setting(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "enable", "substrate", "slab"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable", "none"}:
        return False
    return bool(default)


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _format_command_for_display(program: str, args: Sequence[str]) -> str:
    parts = [str(program), *[str(arg) for arg in args]]

    def quote(value: str) -> str:
        if not value:
            return '""'
        if any(char.isspace() for char in value) or any(char in value for char in ('"', "'")):
            return '"' + value.replace('"', '\\"') + '"'
        return value

    return " ".join(quote(part) for part in parts)


def texture_lab_gpu_install_plan(python_executable: str | None = None) -> dict[str, Any]:
    """Return the first-use install contract for Texture Lab CUDA map generation."""
    program = str(python_executable or sys.executable or ".\\.venv\\Scripts\\python.exe")
    install_args = [
        "-m",
        "pip",
        "install",
        "torch",
        "torchvision",
        "--index-url",
        TORCH_CUDA_WHEEL_INDEX_URL,
    ]
    verify_script = (
        "import json, torch; "
        "ok=bool(torch.cuda.is_available()); "
        "payload={'torch': torch.__version__, 'cuda_available': ok, "
        "'device': torch.cuda.get_device_name(0) if ok else 'cpu'}; "
        "print(json.dumps(payload, ensure_ascii=False)); "
        "raise SystemExit(0 if ok else 3)"
    )
    verify_args = ["-c", verify_script]
    return {
        "schema_id": f"{SCHEMA_ID}.gpu_install_plan",
        "backend": "torch_cuda",
        "install_program": program,
        "install_args": install_args,
        "install_command": _format_command_for_display(program, install_args),
        "verify_program": program,
        "verify_args": verify_args,
        "verify_command": _format_command_for_display(program, verify_args),
        "env_override": "$env:TIGERCAPTURE_TEXTURE_LAB_BACKEND='torch_cuda'",
        "wheel_index_url": TORCH_CUDA_WHEEL_INDEX_URL,
    }


def texture_map_backend_status() -> dict[str, Any]:
    """Return optional accelerator availability without importing heavy modules at startup."""
    torch_available = _module_available("torch")
    torch_cuda_available = False
    torch_device = ""
    if torch_available:
        try:
            import torch  # type: ignore

            torch_cuda_available = bool(torch.cuda.is_available())
            if torch_cuda_available:
                torch_device = str(torch.cuda.get_device_name(0))
        except Exception as exc:
            torch_device = f"torch probe failed: {type(exc).__name__}"

    cupy_available = _module_available("cupy")
    cupy_cuda_available = False
    cupy_device = ""
    if cupy_available:
        try:
            import cupy  # type: ignore

            device_count = int(cupy.cuda.runtime.getDeviceCount())
            cupy_cuda_available = device_count > 0
            if cupy_cuda_available:
                props = cupy.cuda.runtime.getDeviceProperties(0)
                raw_name = props.get("name", b"")
                cupy_device = raw_name.decode("utf-8", "ignore") if isinstance(raw_name, bytes) else str(raw_name)
        except Exception as exc:
            cupy_device = f"cupy probe failed: {type(exc).__name__}"

    opencv_available = _module_available("cv2")
    opencv_cuda_devices = 0
    if opencv_available:
        try:
            import cv2  # type: ignore

            if hasattr(cv2, "cuda"):
                opencv_cuda_devices = int(cv2.cuda.getCudaEnabledDeviceCount())
        except Exception:
            opencv_cuda_devices = 0

    install_plan = texture_lab_gpu_install_plan()
    install_guidance = {
        "recommended_backend": "torch_cuda",
        "summary": (
            "Texture Lab map generation/export requires a CUDA tensor backend inside the "
            "TigerCapture virtual environment. An RTX GPU and the AR/PBR OpenGL viewer can "
            "work while PyTorch CUDA is still missing."
        ),
        "why_this_can_happen": (
            "AR/PBR model preview uses OpenGL. Texture Lab map generation uses PyTorch CUDA "
            "kernels, so it also needs a CUDA-enabled torch package installed in this venv."
        ),
        "pip_command": str(install_plan["install_command"]),
        "verify_command": str(install_plan["verify_command"]),
        "env_override": str(install_plan["env_override"]),
        "auto_install": install_plan,
        "notes": [
            "Install must be done in the TigerCapture virtual environment.",
            "NVIDIA drivers or a working OpenGL AR/PBR viewer do not automatically install PyTorch.",
            "The CUDA wheel index may need to change if the local driver/toolchain policy changes.",
            "If install fails or torch.cuda.is_available() is false, product UI/actions stay GPU-required.",
            "CPU fallback is diagnostic-only via allow_cpu=true or TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU=1.",
        ],
        "runtime_requirements": {
            "hardware_gpu": "NVIDIA GPU and driver",
            "preview_renderer": "OpenGL renderer for visual material preview",
            "map_generation_backend": "torch with CUDA available from .venv",
        },
    }
    try:
        from app.ar_pbr.texture_map_gpu_preview import texture_lab_gpu_preview_status

        preview_renderer = texture_lab_gpu_preview_status()
    except Exception as exc:
        preview_renderer = {
            "renderer": "opengl_offscreen_texture_lab",
            "available": False,
            "error": str(exc),
            "cpu_preview": False,
        }
    return {
        "schema_id": f"{SCHEMA_ID}.backend_status",
        "env_backend": str(os.environ.get("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "auto") or "auto"),
        "implemented_backends": ["cpu", "torch_cuda"],
        "planned_gpu_backends": ["torch_cuda", "cupy", "opencv_cuda"],
        "install_guidance": install_guidance,
        "preview_renderer": preview_renderer,
        "backends": {
            "cpu": {"available": True, "implemented": True},
            "torch_cuda": {
                "available": torch_cuda_available,
                "implemented": True,
                "module_installed": torch_available,
                "device": torch_device,
                "note": (
                    "Uses PyTorch CUDA tensor kernels for map generation. This is separate from "
                    "the OpenGL AR/PBR viewer, so GPU hardware alone is not enough."
                ),
            },
            "cupy": {
                "available": cupy_cuda_available,
                "implemented": False,
                "module_installed": cupy_available,
                "device": cupy_device,
                "note": "CuPy is a planned NumPy-like GPU backend; current build uses CPU maps.",
            },
            "opencv_cuda": {
                "available": opencv_cuda_devices > 0,
                "implemented": False,
                "module_installed": opencv_available,
                "cuda_devices": opencv_cuda_devices,
                "note": "OpenCV CUDA requires a CUDA-enabled OpenCV build and mapped kernels.",
            },
        },
    }


def texture_lab_cpu_fallback_allowed(default: bool = False) -> bool:
    raw = os.environ.get("TIGERCAPTURE_TEXTURE_LAB_ALLOW_CPU")
    if raw is None:
        return bool(default)
    return str(raw).strip().casefold() in {"1", "true", "yes", "on", "allow", "allowed"}


def select_texture_map_backend(requested: str | None = None, *, allow_cpu: bool = True) -> dict[str, Any]:
    requested_name = str(requested or os.environ.get("TIGERCAPTURE_TEXTURE_LAB_BACKEND", "auto") or "auto").strip().lower()
    if requested_name not in TEXTURE_MAP_BACKENDS:
        requested_name = "auto"
    status = texture_map_backend_status()
    cpu_allowed = bool(allow_cpu)
    active = "unavailable"
    reason = "gpu_backend_required"
    if requested_name == "cpu":
        if cpu_allowed:
            active = "cpu"
            reason = "requested_cpu_backend_selected"
        else:
            reason = "cpu_backend_disabled_by_policy"
    elif requested_name in {"torch_cuda", "cupy", "opencv_cuda"}:
        backend = status["backends"].get(requested_name, {})
        if not backend.get("available"):
            reason = f"{requested_name}_not_available"
        elif not backend.get("implemented"):
            reason = f"{requested_name}_not_implemented_yet"
        else:
            active = requested_name
            reason = "requested_backend_selected"
        if active == "unavailable" and cpu_allowed:
            active = "cpu"
            reason = f"{reason}_cpu_fallback"
    elif requested_name == "auto":
        for candidate in ("torch_cuda", "cupy", "opencv_cuda"):
            backend = status["backends"].get(candidate, {})
            if backend.get("available") and backend.get("implemented"):
                active = candidate
                reason = "auto_gpu_backend_selected"
                break
        if active == "unavailable" and cpu_allowed:
            active = "cpu"
            reason = "auto_cpu_fallback_allowed"
    return {
        "requested": requested_name,
        "active": active,
        "fallback": active != requested_name and requested_name != "auto",
        "reason": reason,
        "allow_cpu": cpu_allowed,
        "gpu_required": active == "unavailable",
        "status": status,
    }


def texture_map_generation_settings(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_texture_map_settings(settings)
    return {key: value for key, value in normalized.items() if key not in PREVIEW_ONLY_SETTING_KEYS}


def texture_map_settings_fingerprint(settings: Mapping[str, Any] | None = None, *, generation_only: bool = True) -> str:
    payload = texture_map_generation_settings(settings) if generation_only else normalize_texture_map_settings(settings)
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.blake2b(raw, digest_size=12).hexdigest()


def texture_source_fingerprint(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    digest = hashlib.blake2b(digest_size=16)
    digest.update(str(rgb.size).encode("ascii"))
    digest.update(rgb.tobytes())
    return digest.hexdigest()


def normalize_texture_map_settings(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(settings or {})
    defaults = TextureMapLabSettings()
    normal_format = str(raw.get("normal_format", defaults.normal_format) or defaults.normal_format).strip().lower()
    if normal_format not in NORMAL_FORMATS:
        normal_format = defaults.normal_format
    ao_algorithm = str(raw.get("ao_algorithm", defaults.ao_algorithm) or defaults.ao_algorithm).strip().lower()
    if ao_algorithm not in AO_ALGORITHMS:
        ao_algorithm = defaults.ao_algorithm
    normal_filter = str(raw.get("normal_filter", defaults.normal_filter) or defaults.normal_filter).strip().lower()
    if normal_filter not in {"sobel", "central_difference"}:
        normal_filter = defaults.normal_filter
    substrate_mode = str(raw.get("substrate_mode", defaults.substrate_mode) or defaults.substrate_mode).strip().lower()
    if substrate_mode in {"substrate", "substrate_slab", "bsdf_slab"}:
        substrate_mode = "slab"
    if substrate_mode not in {"off", "slab"}:
        substrate_mode = defaults.substrate_mode
    substrate_enabled = bool_setting(
        raw.get("substrate_enabled", raw.get("use_substrate")),
        substrate_mode == "slab" or defaults.substrate_enabled,
    )
    if substrate_enabled:
        substrate_mode = "slab"
    else:
        substrate_mode = "off"
    return {
        "schema_id": SCHEMA_ID,
        "normal_strength": clamp_float(raw.get("normal_strength"), 0.0, 12.0, defaults.normal_strength),
        "normal_radius_px": clamp_float(raw.get("normal_radius_px"), 0.0, 24.0, defaults.normal_radius_px),
        "normal_format": normal_format,
        "normal_filter": normal_filter,
        "height_invert": bool(raw.get("height_invert", defaults.height_invert)),
        "height_contrast": clamp_float(raw.get("height_contrast"), 0.1, 4.0, defaults.height_contrast),
        "height_blur_px": clamp_float(raw.get("height_blur_px"), 0.0, 8.0, defaults.height_blur_px),
        "edge_aware_smoothing": bool(raw.get("edge_aware_smoothing", defaults.edge_aware_smoothing)),
        "edge_aware_sensitivity": clamp_float(
            raw.get("edge_aware_sensitivity"),
            0.0,
            32.0,
            defaults.edge_aware_sensitivity,
        ),
        "ao_strength": clamp_float(raw.get("ao_strength"), 0.0, 3.0, defaults.ao_strength),
        "ao_radius_px": clamp_float(raw.get("ao_radius_px"), 0.0, 64.0, defaults.ao_radius_px),
        "ao_algorithm": ao_algorithm,
        "ao_samples": int(round(clamp_float(raw.get("ao_samples"), 4.0, 32.0, float(defaults.ao_samples)))),
        "ao_steps": int(round(clamp_float(raw.get("ao_steps"), 2.0, 24.0, float(defaults.ao_steps)))),
        "ao_height_scale": clamp_float(raw.get("ao_height_scale"), 0.1, 64.0, defaults.ao_height_scale),
        "ao_multiscale": bool(raw.get("ao_multiscale", defaults.ao_multiscale)),
        "cavity_strength": clamp_float(raw.get("cavity_strength"), 0.0, 2.0, defaults.cavity_strength),
        "cavity_radius_px": clamp_float(raw.get("cavity_radius_px"), 0.2, 32.0, defaults.cavity_radius_px),
        "curvature_strength": clamp_float(raw.get("curvature_strength"), 0.0, 8.0, defaults.curvature_strength),
        "roughness_bias": clamp_float(raw.get("roughness_bias"), 0.0, 1.0, defaults.roughness_bias),
        "roughness_contrast": clamp_float(raw.get("roughness_contrast"), 0.1, 3.0, defaults.roughness_contrast),
        "roughness_detail": clamp_float(raw.get("roughness_detail"), 0.0, 1.0, defaults.roughness_detail),
        "metallic_value": clamp_float(raw.get("metallic_value"), 0.0, 1.0, defaults.metallic_value),
        "metallic_threshold": clamp_float(raw.get("metallic_threshold"), 0.0, 1.5, defaults.metallic_threshold),
        "metallic_softness": clamp_float(raw.get("metallic_softness"), 0.001, 0.5, defaults.metallic_softness),
        "delight_enabled": bool_setting(raw.get("delight_enabled"), defaults.delight_enabled),
        "delight_strength": clamp_float(raw.get("delight_strength"), 0.0, 1.0, defaults.delight_strength),
        "delight_radius_px": clamp_float(raw.get("delight_radius_px"), 1.0, 256.0, defaults.delight_radius_px),
        "delight_contrast_preservation": clamp_float(
            raw.get("delight_contrast_preservation"),
            0.0,
            1.0,
            defaults.delight_contrast_preservation,
        ),
        "substrate_enabled": substrate_enabled,
        "substrate_mode": substrate_mode,
        "substrate_reflectance": clamp_float(
            raw.get("substrate_reflectance"),
            0.0,
            1.0,
            defaults.substrate_reflectance,
        ),
        "f90_mask_strength": clamp_float(raw.get("f90_mask_strength"), 0.0, 1.0, defaults.f90_mask_strength),
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
        "preview_animate_light": bool_setting(
            raw.get("preview_animate_light"),
            defaults.preview_animate_light,
        ),
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


def _edge_aware_blur_float(
    array: np.ndarray,
    guide: np.ndarray | None,
    radius: float,
    *,
    sensitivity: float = 9.0,
) -> np.ndarray:
    source = np.asarray(array, dtype=np.float32)
    blurred = _blur_float(source, radius)
    if guide is None or sensitivity <= 0.001 or radius <= 0.001:
        return blurred
    guide_arr = np.asarray(guide, dtype=np.float32)
    guide_blur = _blur_float(guide_arr, radius)
    edge_delta = np.abs(guide_arr - guide_blur)
    blur_weight = np.exp(-edge_delta * float(sensitivity)).astype(np.float32)
    return np.clip(source * (1.0 - blur_weight) + blurred * blur_weight, 0.0, 1.0).astype(np.float32)


def _contrast_gray(array: np.ndarray, contrast: float, midpoint: float = 0.5) -> np.ndarray:
    return np.clip((np.asarray(array, dtype=np.float32) - midpoint) * float(contrast) + midpoint, 0.0, 1.0)


def _shift_clamped(array: np.ndarray, dy: int, dx: int) -> np.ndarray:
    src = np.asarray(array, dtype=np.float32)
    pad_y = abs(int(dy))
    pad_x = abs(int(dx))
    if pad_y == 0 and pad_x == 0:
        return src
    padded = np.pad(src, ((pad_y, pad_y), (pad_x, pad_x)), mode="edge")
    y0 = pad_y + int(dy)
    x0 = pad_x + int(dx)
    return padded[y0:y0 + src.shape[0], x0:x0 + src.shape[1]].astype(np.float32)


def _sobel_gradient_from_height(height: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h = np.asarray(height, dtype=np.float32)
    tl = _shift_clamped(h, -1, -1)
    tc = _shift_clamped(h, -1, 0)
    tr = _shift_clamped(h, -1, 1)
    ml = _shift_clamped(h, 0, -1)
    mr = _shift_clamped(h, 0, 1)
    bl = _shift_clamped(h, 1, -1)
    bc = _shift_clamped(h, 1, 0)
    br = _shift_clamped(h, 1, 1)
    dx = ((tr + 2.0 * mr + br) - (tl + 2.0 * ml + bl)) / 8.0
    dy = ((bl + 2.0 * bc + br) - (tl + 2.0 * tc + tr)) / 8.0
    return dx.astype(np.float32), dy.astype(np.float32)


def _gradient_from_height(height: np.ndarray, radius_px: float) -> tuple[np.ndarray, np.ndarray]:
    radius = max(1, int(round(radius_px)))
    if radius <= 1:
        return _sobel_gradient_from_height(height)
    right = _shift_clamped(height, 0, radius)
    left = _shift_clamped(height, 0, -radius)
    down = _shift_clamped(height, radius, 0)
    up = _shift_clamped(height, -radius, 0)
    denom = max(1.0, float(radius * 2))
    return (right - left) / denom, (down - up) / denom


def _height_from_source(rgb: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    height = _contrast_gray(luma, float(settings["height_contrast"]))
    blur = float(settings["height_blur_px"])
    if blur > 0.001:
        if bool(settings.get("edge_aware_smoothing", True)):
            height = _edge_aware_blur_float(
                height,
                luma,
                blur,
                sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)),
            )
        else:
            height = _blur_float(height, blur)
    if bool(settings["height_invert"]):
        height = 1.0 - height
    return np.clip(height, 0.0, 1.0).astype(np.float32)


def _normal_from_height(height: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    radius = float(settings["normal_radius_px"])
    source = np.asarray(height, dtype=np.float32)
    if radius > 1.25 and bool(settings.get("edge_aware_smoothing", True)):
        source = _edge_aware_blur_float(
            source,
            source,
            radius * 0.35,
            sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)),
        )
    if str(settings.get("normal_filter", "sobel")) == "central_difference":
        dx, dy = _gradient_from_height(source, radius)
    elif radius > 1.25:
        dx, dy = _gradient_from_height(source, radius)
    else:
        dx, dy = _sobel_gradient_from_height(source)
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


def _heightfield_horizon_occlusion(
    height: np.ndarray,
    *,
    radius_px: float,
    samples: int,
    steps: int,
    height_scale: float,
) -> np.ndarray:
    radius = max(0.0, float(radius_px))
    if radius <= 0.001:
        return np.zeros_like(height, dtype=np.float32)
    h = np.asarray(height, dtype=np.float32)
    sample_count = max(4, int(samples))
    step_count = max(2, int(steps))
    occlusion = np.zeros_like(h, dtype=np.float32)
    for sample_index in range(sample_count):
        angle = (math.tau * float(sample_index)) / float(sample_count)
        ux = math.cos(angle)
        uy = math.sin(angle)
        horizon = np.zeros_like(h, dtype=np.float32)
        seen_offsets: set[tuple[int, int]] = set()
        for step_index in range(1, step_count + 1):
            dist = max(1.0, radius * float(step_index) / float(step_count))
            dx_i = int(round(ux * dist))
            dy_i = int(round(uy * dist))
            if dx_i == 0 and dy_i == 0:
                continue
            offset = (dy_i, dx_i)
            if offset in seen_offsets:
                continue
            seen_offsets.add(offset)
            actual_dist = max(1.0, math.hypot(float(dx_i), float(dy_i)))
            sample = _shift_clamped(h, dy_i, dx_i)
            slope = np.maximum((sample - h) * float(height_scale) / actual_dist, 0.0)
            horizon = np.maximum(horizon, slope)
        occlusion += horizon / np.sqrt(horizon * horizon + 1.0)
    return np.clip(occlusion / float(sample_count), 0.0, 1.0).astype(np.float32)


def _curvature_from_height(height: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    h = np.asarray(height, dtype=np.float32)
    radius = max(1, int(round(float(settings.get("cavity_radius_px", 2.2)))))
    left = _shift_clamped(h, 0, -radius)
    right = _shift_clamped(h, 0, radius)
    up = _shift_clamped(h, -radius, 0)
    down = _shift_clamped(h, radius, 0)
    laplacian = ((left + right + up + down) * 0.25 - h) / float(radius)
    strength = float(settings.get("curvature_strength", 1.25))
    # 0.5 is neutral; convex ridges move brighter and concave creases move darker.
    return np.clip(0.5 - laplacian * strength * 3.0, 0.0, 1.0).astype(np.float32)


def _legacy_ao_from_height(height: np.ndarray, settings: Mapping[str, Any], guide: np.ndarray | None = None) -> np.ndarray:
    radius = float(settings["ao_radius_px"])
    if radius <= 0.001:
        return np.ones_like(height, dtype=np.float32)
    if bool(settings.get("edge_aware_smoothing", True)):
        local = _edge_aware_blur_float(
            height,
            guide if guide is not None else height,
            radius,
            sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)),
        )
    else:
        local = _blur_float(height, radius)
    shadow = np.clip(local - height, 0.0, 1.0)
    ao = 1.0 - shadow * float(settings["ao_strength"]) * 2.2
    return np.clip(ao, 0.0, 1.0).astype(np.float32)


def _ao_from_height(height: np.ndarray, settings: Mapping[str, Any], guide: np.ndarray | None = None) -> np.ndarray:
    if str(settings.get("ao_algorithm", "heightfield_horizon")) == "legacy_blur":
        return _legacy_ao_from_height(height, settings, guide)
    radius = float(settings["ao_radius_px"])
    strength = float(settings["ao_strength"])
    if radius <= 0.001 or strength <= 0.001:
        return np.ones_like(height, dtype=np.float32)
    samples = int(settings.get("ao_samples", 8))
    steps = int(settings.get("ao_steps", 8))
    height_scale = float(settings.get("ao_height_scale", 14.0))
    if bool(settings.get("ao_multiscale", True)):
        radii = (
            max(1.0, radius * 0.45),
            max(1.0, radius),
            max(1.0, radius * 1.9),
        )
        weights = (0.42, 0.40, 0.18)
    else:
        radii = (max(1.0, radius),)
        weights = (1.0,)
    horizon = np.zeros_like(height, dtype=np.float32)
    for radius_value, weight in zip(radii, weights):
        scale = height_scale * (radius_value / max(1.0, radius)) ** 0.35
        step_count = max(2, int(round(steps * min(1.4, radius_value / max(1.0, radius)))))
        horizon += _heightfield_horizon_occlusion(
            height,
            radius_px=radius_value,
            samples=samples,
            steps=step_count,
            height_scale=scale,
        ) * float(weight)
    if bool(settings.get("edge_aware_smoothing", True)):
        macro = _edge_aware_blur_float(
            height,
            guide if guide is not None else height,
            radius,
            sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)),
        )
    else:
        macro = _blur_float(height, radius)
    broad_shadow = np.clip((macro - height) * height_scale * 0.18, 0.0, 1.0)
    curvature = _curvature_from_height(height, settings)
    concave_shadow = np.clip((0.5 - curvature) * 2.0, 0.0, 1.0)
    occlusion = np.clip(horizon * 0.78 + broad_shadow * 0.14 + concave_shadow * 0.08, 0.0, 1.0)
    ao = 1.0 - occlusion * strength
    return np.clip(ao, 0.0, 1.0).astype(np.float32)


def _cavity_from_height(height: np.ndarray, settings: Mapping[str, Any], guide: np.ndarray | None = None) -> np.ndarray:
    strength = float(settings["cavity_strength"])
    if strength <= 0.001:
        return np.ones_like(height, dtype=np.float32)
    base_radius = float(settings.get("cavity_radius_px", 2.2))
    if bool(settings.get("ao_multiscale", True)):
        radii = (max(0.5, base_radius * 0.55), max(1.0, base_radius * 1.4), max(1.0, base_radius * 3.0))
        weights = (0.52, 0.32, 0.16)
    else:
        radii = (max(1.0, base_radius),)
        weights = (1.0,)
    cavity_signal = np.zeros_like(height, dtype=np.float32)
    for radius, weight in zip(radii, weights):
        if bool(settings.get("edge_aware_smoothing", True)):
            local = _edge_aware_blur_float(
                height,
                guide if guide is not None else height,
                radius,
                sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)),
            )
        else:
            local = _blur_float(height, radius)
        concavity = np.clip(local - height, 0.0, 1.0)
        detail = np.abs(height - local) * 0.35
        cavity_signal += (concavity * 1.45 + detail) * float(weight)
    curvature = _curvature_from_height(height, settings)
    cavity_signal += np.clip((0.5 - curvature) * 2.0, 0.0, 1.0) * 0.38
    cavity = 1.0 - np.clip(cavity_signal * 3.0 * strength, 0.0, 1.0)
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


def _f0_from_material_maps(base_color: np.ndarray, metallic: np.ndarray, settings: Mapping[str, Any]) -> np.ndarray:
    reflectance = float(settings.get("substrate_reflectance", 0.5))
    return np.clip(material_f0(base_color, metallic, reflectance), 0.0, 1.0).astype(np.float32)


def _f90_mask_from_material_maps(
    base_color: np.ndarray,
    height: np.ndarray,
    roughness: np.ndarray,
    curvature: np.ndarray,
    ao: np.ndarray,
    settings: Mapping[str, Any],
) -> np.ndarray:
    strength = float(settings.get("f90_mask_strength", 0.45))
    if strength <= 0.001:
        return np.zeros_like(height, dtype=np.float32)
    luma = base_color[..., 0] * 0.2126 + base_color[..., 1] * 0.7152 + base_color[..., 2] * 0.0722
    radius = max(1.0, float(settings.get("cavity_radius_px", 2.2)) * 1.5)
    local = _edge_aware_blur_float(
        height,
        luma,
        radius,
        sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)),
    )
    relief_edge = np.clip(np.abs(height - local) * 4.0, 0.0, 1.0)
    convex_edge = np.clip((curvature - 0.5) * 2.0, 0.0, 1.0)
    smooth_surface = np.clip(1.0 - roughness, 0.0, 1.0)
    occluded_relief = np.clip(1.0 - ao, 0.0, 1.0)
    mask = relief_edge * 0.36 + convex_edge * 0.34 + smooth_surface * 0.20 + occluded_relief * 0.10
    return np.clip(mask * strength, 0.0, 1.0).astype(np.float32)


def _delight_base_color(rgb: np.ndarray, settings: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Estimate broad illumination and remove it from a photographic base map.

    The goal is a production-friendly de-light, not a perfect intrinsic-image
    solve.  It removes low-frequency light/shadow gradients while keeping the
    high-frequency material detail that should stay in BaseColor.
    """
    if not bool(settings.get("delight_enabled", False)):
        return np.clip(rgb, 0.0, 1.0).astype(np.float32), np.ones(rgb.shape[:2], dtype=np.float32)
    strength = float(settings.get("delight_strength", 0.65))
    if strength <= 0.001:
        return np.clip(rgb, 0.0, 1.0).astype(np.float32), np.ones(rgb.shape[:2], dtype=np.float32)
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    radius = float(settings.get("delight_radius_px", 42.0))
    macro_radius = max(1.0, radius)
    broad_radius = max(macro_radius * 2.35, macro_radius + 8.0)
    macro = _blur_float(luma, macro_radius)
    broad = _blur_float(luma, broad_radius)
    illumination = broad * 0.72 + macro * 0.28
    if bool(settings.get("edge_aware_smoothing", True)):
        edge_aware = _edge_aware_blur_float(
            luma,
            luma,
            macro_radius,
            sensitivity=float(settings.get("edge_aware_sensitivity", 9.0)) * 0.18,
        )
        illumination = illumination * 0.86 + edge_aware * 0.14
    illumination = np.clip(illumination, 0.025, 1.0).astype(np.float32)
    neutral = float(np.median(illumination))
    neutral = max(0.05, min(0.95, neutral))
    correction = np.clip(neutral / illumination, 0.32, 3.10)
    corrected = np.clip(rgb * np.power(correction[:, :, None], strength), 0.0, 1.0)
    preserve = float(settings.get("delight_contrast_preservation", 0.25))
    if preserve > 0.001:
        corrected_luma = corrected[..., 0] * 0.2126 + corrected[..., 1] * 0.7152 + corrected[..., 2] * 0.0722
        original_detail = luma - _blur_float(luma, max(1.0, radius * 0.18))
        detail_gain = 1.0 + original_detail[:, :, None] * preserve
        corrected = np.clip(corrected * detail_gain, 0.0, 1.0)
        target_median = float(np.median(luma))
        corrected_median = float(np.median(corrected_luma))
        if corrected_median > 1.0e-4:
            corrected = np.clip(corrected * ((target_median / corrected_median) ** 0.20), 0.0, 1.0)
    low = float(np.percentile(illumination, 2.0))
    high = float(np.percentile(illumination, 98.0))
    if high > low + 1.0e-4:
        shading_display = np.clip((illumination - low) / (high - low), 0.0, 1.0)
    else:
        shading_display = np.clip(illumination / max(0.05, float(np.percentile(illumination, 95.0))), 0.0, 1.0)
    return corrected.astype(np.float32), shading_display.astype(np.float32)


def _base_color_from_source(image: Image.Image, settings: Mapping[str, Any]) -> np.ndarray:
    exposure = float(settings["base_color_exposure"])
    contrast = float(settings["base_color_contrast"])
    adjusted = ImageEnhance.Brightness(image.convert("RGB")).enhance(2.0**exposure)
    adjusted = ImageEnhance.Contrast(adjusted).enhance(contrast)
    return _as_float_image(adjusted)


def _torch_gaussian_blur_2d(value: Any, radius: float, torch: Any) -> Any:
    if radius <= 0.001:
        return value
    import torch.nn.functional as F  # type: ignore

    sigma = max(0.15, float(radius))
    kernel_radius = max(1, int(math.ceil(sigma * 3.0)))
    coords = torch.arange(-kernel_radius, kernel_radius + 1, device=value.device, dtype=value.dtype)
    kernel = torch.exp(-(coords * coords) / (2.0 * sigma * sigma))
    kernel = kernel / torch.clamp(kernel.sum(), min=1.0e-6)
    source = value[None, None, :, :]
    padded = F.pad(source, (kernel_radius, kernel_radius, 0, 0), mode="replicate")
    blurred = F.conv2d(padded, kernel.view(1, 1, 1, -1))
    padded = F.pad(blurred, (0, 0, kernel_radius, kernel_radius), mode="replicate")
    blurred = F.conv2d(padded, kernel.view(1, 1, -1, 1))
    return blurred[0, 0]


def _torch_edge_aware_blur(value: Any, guide: Any | None, radius: float, sensitivity: float, torch: Any) -> Any:
    blurred = _torch_gaussian_blur_2d(value, radius, torch)
    if guide is None or sensitivity <= 0.001 or radius <= 0.001:
        return blurred
    guide_blur = _torch_gaussian_blur_2d(guide, radius, torch)
    edge_delta = torch.abs(guide - guide_blur)
    weight = torch.exp(-edge_delta * float(sensitivity))
    return torch.clamp(value * (1.0 - weight) + blurred * weight, 0.0, 1.0)


def _torch_delight_base_color(base: Any, settings: Mapping[str, Any], torch: Any) -> tuple[Any, Any]:
    if not bool(settings.get("delight_enabled", False)):
        return torch.clamp(base, 0.0, 1.0), torch.ones_like(base[..., 0])
    strength = float(settings.get("delight_strength", 0.65))
    if strength <= 0.001:
        return torch.clamp(base, 0.0, 1.0), torch.ones_like(base[..., 0])
    luma = base[..., 0] * 0.2126 + base[..., 1] * 0.7152 + base[..., 2] * 0.0722
    radius = float(settings.get("delight_radius_px", 42.0))
    macro_radius = max(1.0, radius)
    broad_radius = max(macro_radius * 2.35, macro_radius + 8.0)
    macro = _torch_gaussian_blur_2d(luma, macro_radius, torch)
    broad = _torch_gaussian_blur_2d(luma, broad_radius, torch)
    illumination = broad * 0.72 + macro * 0.28
    if bool(settings.get("edge_aware_smoothing", True)):
        edge_aware = _torch_edge_aware_blur(
            luma,
            luma,
            macro_radius,
            float(settings.get("edge_aware_sensitivity", 9.0)) * 0.18,
            torch,
        )
        illumination = illumination * 0.86 + edge_aware * 0.14
    illumination = torch.clamp(illumination, 0.025, 1.0)
    neutral = torch.quantile(illumination.reshape(-1), 0.50)
    neutral = torch.clamp(neutral, 0.05, 0.95)
    correction = torch.clamp(neutral / illumination, 0.32, 3.10)
    corrected = torch.clamp(base * torch.pow(correction[..., None], strength), 0.0, 1.0)
    preserve = float(settings.get("delight_contrast_preservation", 0.25))
    if preserve > 0.001:
        local = _torch_gaussian_blur_2d(luma, max(1.0, radius * 0.18), torch)
        detail_gain = 1.0 + (luma - local)[..., None] * preserve
        corrected = torch.clamp(corrected * detail_gain, 0.0, 1.0)
        corrected_luma = corrected[..., 0] * 0.2126 + corrected[..., 1] * 0.7152 + corrected[..., 2] * 0.0722
        target_mean = torch.clamp(torch.mean(luma), min=1.0e-4)
        corrected_mean = torch.clamp(torch.mean(corrected_luma), min=1.0e-4)
        corrected = torch.clamp(corrected * torch.pow(target_mean / corrected_mean, 0.20), 0.0, 1.0)
    low = torch.quantile(illumination.reshape(-1), 0.02)
    high = torch.quantile(illumination.reshape(-1), 0.98)
    if bool((high > low + 1.0e-4).item()):
        shading_display = torch.clamp((illumination - low) / (high - low), 0.0, 1.0)
    else:
        high = torch.clamp(torch.quantile(illumination.reshape(-1), 0.95), min=0.05)
        shading_display = torch.clamp(illumination / high, 0.0, 1.0)
    return corrected, shading_display


def _torch_shift_clamped(value: Any, dy: int, dx: int) -> Any:
    import torch.nn.functional as F  # type: ignore

    pad_y = abs(int(dy))
    pad_x = abs(int(dx))
    if pad_y == 0 and pad_x == 0:
        return value
    padded = F.pad(value[None, None, :, :], (pad_x, pad_x, pad_y, pad_y), mode="replicate")[0, 0]
    y0 = pad_y + int(dy)
    x0 = pad_x + int(dx)
    return padded[y0:y0 + value.shape[0], x0:x0 + value.shape[1]]


def _torch_gradient_from_height(height: Any, radius_px: float, torch: Any) -> tuple[Any, Any]:
    radius = max(1, int(round(float(radius_px))))
    if radius <= 1:
        tl = _torch_shift_clamped(height, -1, -1)
        tc = _torch_shift_clamped(height, -1, 0)
        tr = _torch_shift_clamped(height, -1, 1)
        ml = _torch_shift_clamped(height, 0, -1)
        mr = _torch_shift_clamped(height, 0, 1)
        bl = _torch_shift_clamped(height, 1, -1)
        bc = _torch_shift_clamped(height, 1, 0)
        br = _torch_shift_clamped(height, 1, 1)
        dx = ((tr + 2.0 * mr + br) - (tl + 2.0 * ml + bl)) / 8.0
        dy = ((bl + 2.0 * bc + br) - (tl + 2.0 * tc + tr)) / 8.0
        return dx, dy
    right = _torch_shift_clamped(height, 0, radius)
    left = _torch_shift_clamped(height, 0, -radius)
    down = _torch_shift_clamped(height, radius, 0)
    up = _torch_shift_clamped(height, -radius, 0)
    denom = max(1.0, float(radius * 2))
    return (right - left) / denom, (down - up) / denom


def _generate_texture_maps_torch_cuda(
    image: Image.Image,
    normalized: Mapping[str, Any],
    *,
    source_path: str = "",
) -> dict[str, Any]:
    import torch  # type: ignore

    if not torch.cuda.is_available():
        raise RuntimeError("torch CUDA is not available")
    device = torch.device("cuda")
    arr = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    base = torch.from_numpy(arr).to(device=device, dtype=torch.float32)
    exposure = float(normalized["base_color_exposure"])
    contrast = float(normalized["base_color_contrast"])
    base = torch.clamp(((base * (2.0 ** exposure)) - 0.5) * contrast + 0.5, 0.0, 1.0)
    base_source = torch.clamp(base, 0.0, 1.0)
    guide_luma = base[..., 0] * 0.2126 + base[..., 1] * 0.7152 + base[..., 2] * 0.0722
    base, delight_shading = _torch_delight_base_color(base, normalized, torch)
    guide_luma = base[..., 0] * 0.2126 + base[..., 1] * 0.7152 + base[..., 2] * 0.0722
    height = torch.clamp((guide_luma - 0.5) * float(normalized["height_contrast"]) + 0.5, 0.0, 1.0)
    height_blur = float(normalized["height_blur_px"])
    if height_blur > 0.001:
        if bool(normalized.get("edge_aware_smoothing", True)):
            height = _torch_edge_aware_blur(
                height,
                guide_luma,
                height_blur,
                float(normalized.get("edge_aware_sensitivity", 9.0)),
                torch,
            )
        else:
            height = _torch_gaussian_blur_2d(height, height_blur, torch)
    if bool(normalized["height_invert"]):
        height = 1.0 - height
    height = torch.clamp(height, 0.0, 1.0)

    normal_source = height
    normal_radius = float(normalized["normal_radius_px"])
    if normal_radius > 1.25 and bool(normalized.get("edge_aware_smoothing", True)):
        normal_source = _torch_edge_aware_blur(
            normal_source,
            normal_source,
            normal_radius * 0.35,
            float(normalized.get("edge_aware_sensitivity", 9.0)),
            torch,
        )
    dx, dy = _torch_gradient_from_height(normal_source, normal_radius, torch)
    nx = -dx * float(normalized["normal_strength"])
    ny = -dy * float(normalized["normal_strength"])
    if str(normalized["normal_format"]) in {"unreal_directx", "directx"}:
        ny = -ny
    nz = torch.ones_like(height)
    normal_vec = torch.stack([nx, ny, nz], dim=-1)
    normal_vec = normal_vec / torch.clamp(torch.linalg.norm(normal_vec, dim=2, keepdim=True), min=1.0e-6)
    normal = torch.clamp(normal_vec * 0.5 + 0.5, 0.0, 1.0)

    curvature_radius = max(1, int(round(float(normalized.get("cavity_radius_px", 2.2)))))
    left = _torch_shift_clamped(height, 0, -curvature_radius)
    right = _torch_shift_clamped(height, 0, curvature_radius)
    up = _torch_shift_clamped(height, -curvature_radius, 0)
    down = _torch_shift_clamped(height, curvature_radius, 0)
    laplacian = ((left + right + up + down) * 0.25 - height) / float(curvature_radius)
    curvature = torch.clamp(
        0.5 - laplacian * float(normalized.get("curvature_strength", 1.25)) * 3.0,
        0.0,
        1.0,
    )

    if str(normalized.get("ao_algorithm", "heightfield_horizon")) == "legacy_blur":
        local = _torch_edge_aware_blur(
            height,
            guide_luma,
            float(normalized["ao_radius_px"]),
            float(normalized.get("edge_aware_sensitivity", 9.0)),
            torch,
        )
        shadow = torch.clamp(local - height, 0.0, 1.0)
        ao = torch.clamp(1.0 - shadow * float(normalized["ao_strength"]) * 2.2, 0.0, 1.0)
    else:
        radius = float(normalized["ao_radius_px"])
        strength = float(normalized["ao_strength"])
        if radius <= 0.001 or strength <= 0.001:
            ao = torch.ones_like(height)
        else:
            samples = max(4, int(normalized.get("ao_samples", 8)))
            steps = max(2, int(normalized.get("ao_steps", 8)))
            height_scale = float(normalized.get("ao_height_scale", 14.0))
            if bool(normalized.get("ao_multiscale", True)):
                radii = (max(1.0, radius * 0.45), max(1.0, radius), max(1.0, radius * 1.9))
                weights = (0.42, 0.40, 0.18)
            else:
                radii = (max(1.0, radius),)
                weights = (1.0,)
            horizon_total = torch.zeros_like(height)
            for radius_value, weight in zip(radii, weights):
                sample_scale = height_scale * (radius_value / max(1.0, radius)) ** 0.35
                step_count = max(2, int(round(steps * min(1.4, radius_value / max(1.0, radius)))))
                occlusion = torch.zeros_like(height)
                for sample_index in range(samples):
                    angle = (math.tau * float(sample_index)) / float(samples)
                    ux = math.cos(angle)
                    uy = math.sin(angle)
                    horizon = torch.zeros_like(height)
                    seen_offsets: set[tuple[int, int]] = set()
                    for step_index in range(1, step_count + 1):
                        dist = max(1.0, radius_value * float(step_index) / float(step_count))
                        dx_i = int(round(ux * dist))
                        dy_i = int(round(uy * dist))
                        if dx_i == 0 and dy_i == 0:
                            continue
                        offset = (dy_i, dx_i)
                        if offset in seen_offsets:
                            continue
                        seen_offsets.add(offset)
                        actual_dist = max(1.0, math.hypot(float(dx_i), float(dy_i)))
                        sample = _torch_shift_clamped(height, dy_i, dx_i)
                        slope = torch.clamp((sample - height) * sample_scale / actual_dist, min=0.0)
                        horizon = torch.maximum(horizon, slope)
                    occlusion += horizon / torch.sqrt(horizon * horizon + 1.0)
                horizon_total += torch.clamp(occlusion / float(samples), 0.0, 1.0) * float(weight)
            macro = _torch_edge_aware_blur(
                height,
                guide_luma,
                radius,
                float(normalized.get("edge_aware_sensitivity", 9.0)),
                torch,
            )
            broad_shadow = torch.clamp((macro - height) * height_scale * 0.18, 0.0, 1.0)
            concave_shadow = torch.clamp((0.5 - curvature) * 2.0, 0.0, 1.0)
            occlusion = torch.clamp(horizon_total * 0.78 + broad_shadow * 0.14 + concave_shadow * 0.08, 0.0, 1.0)
            ao = torch.clamp(1.0 - occlusion * strength, 0.0, 1.0)

    cavity_strength = float(normalized["cavity_strength"])
    if cavity_strength <= 0.001:
        cavity = torch.ones_like(height)
    else:
        base_radius = float(normalized.get("cavity_radius_px", 2.2))
        if bool(normalized.get("ao_multiscale", True)):
            radii = (max(0.5, base_radius * 0.55), max(1.0, base_radius * 1.4), max(1.0, base_radius * 3.0))
            weights = (0.52, 0.32, 0.16)
        else:
            radii = (max(1.0, base_radius),)
            weights = (1.0,)
        signal = torch.zeros_like(height)
        for radius_value, weight in zip(radii, weights):
            local = _torch_edge_aware_blur(
                height,
                guide_luma,
                radius_value,
                float(normalized.get("edge_aware_sensitivity", 9.0)),
                torch,
            )
            concavity = torch.clamp(local - height, 0.0, 1.0)
            detail = torch.abs(height - local) * 0.35
            signal += (concavity * 1.45 + detail) * float(weight)
        signal += torch.clamp((0.5 - curvature) * 2.0, 0.0, 1.0) * 0.38
        cavity = torch.clamp(1.0 - torch.clamp(signal * 3.0 * cavity_strength, 0.0, 1.0), 0.0, 1.0)

    local_luma = _torch_gaussian_blur_2d(guide_luma, max(1.0, float(normalized["normal_radius_px"]) * 2.5), torch)
    detail = torch.abs(guide_luma - local_luma)
    roughness = float(normalized["roughness_bias"]) + (0.5 - height) * 0.22
    roughness = roughness + detail * float(normalized["roughness_detail"]) * 1.3
    roughness = torch.clamp(
        (roughness - float(normalized["roughness_bias"])) * float(normalized["roughness_contrast"])
        + float(normalized["roughness_bias"]),
        0.04,
        1.0,
    )

    metallic = torch.full_like(height, float(normalized["metallic_value"]))
    threshold = float(normalized["metallic_threshold"])
    if threshold < 1.0:
        saturation = torch.max(base, dim=2).values - torch.min(base, dim=2).values
        brightness = torch.max(base, dim=2).values
        metal_signal = torch.clamp((brightness - threshold) / float(normalized["metallic_softness"]), 0.0, 1.0)
        metal_signal = metal_signal * torch.clamp((0.32 - saturation) / 0.32, 0.0, 1.0)
        metallic = torch.clamp(torch.maximum(metallic, metal_signal), 0.0, 1.0)

    reflectance = float(normalized.get("substrate_reflectance", 0.5))
    dielectric_f0 = 0.16 * reflectance * reflectance
    f0 = torch.clamp(dielectric_f0 * (1.0 - metallic[..., None]) + base * metallic[..., None], 0.0, 1.0)

    f90_strength = float(normalized.get("f90_mask_strength", 0.45))
    if f90_strength <= 0.001:
        f90_mask = torch.zeros_like(height)
    else:
        local = _torch_edge_aware_blur(
            height,
            guide_luma,
            max(1.0, float(normalized.get("cavity_radius_px", 2.2)) * 1.5),
            float(normalized.get("edge_aware_sensitivity", 9.0)),
            torch,
        )
        relief_edge = torch.clamp(torch.abs(height - local) * 4.0, 0.0, 1.0)
        convex_edge = torch.clamp((curvature - 0.5) * 2.0, 0.0, 1.0)
        smooth_surface = torch.clamp(1.0 - roughness, 0.0, 1.0)
        occluded_relief = torch.clamp(1.0 - ao, 0.0, 1.0)
        f90_mask = torch.clamp(
            (relief_edge * 0.36 + convex_edge * 0.34 + smooth_surface * 0.20 + occluded_relief * 0.10)
            * f90_strength,
            0.0,
            1.0,
        )

    def cpu(value: Any) -> np.ndarray:
        return value.detach().clamp(0.0, 1.0).cpu().numpy().astype(np.float32)

    maps = {
        "base_color_source": cpu(base_source),
        "base_color": cpu(base),
        "height": cpu(height),
        "normal": cpu(normal),
        "ao": cpu(ao),
        "roughness": cpu(roughness),
        "metallic": cpu(metallic),
        "irradiance": cpu(delight_shading),
        "delight_shading": cpu(delight_shading),
        "cavity": cpu(cavity),
        "curvature": cpu(curvature),
        "f0": cpu(f0),
        "f90_mask": cpu(f90_mask),
    }
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(source_path or ""),
        "settings": dict(normalized),
        "size": [int(image.size[0]), int(image.size[1])],
        "maps": maps,
        "algorithms": _algorithm_metadata(normalized),
        "diagnostics": _map_diagnostics(maps),
    }


def _generate_texture_maps_cpu(
    image: Image.Image,
    normalized: Mapping[str, Any],
    *,
    source_path: str = "",
) -> dict[str, Any]:
    image = image.convert("RGB")
    base_color_raw = _base_color_from_source(image, normalized)
    base_color, delight_shading = _delight_base_color(base_color_raw, normalized)
    guide_luma = base_color[..., 0] * 0.2126 + base_color[..., 1] * 0.7152 + base_color[..., 2] * 0.0722
    height = _height_from_source(base_color, normalized)
    normal = _normal_from_height(height, normalized)
    ao = _ao_from_height(height, normalized, guide_luma)
    cavity = _cavity_from_height(height, normalized, guide_luma)
    curvature = _curvature_from_height(height, normalized)
    roughness = _roughness_from_source(base_color, height, normalized)
    metallic = _metallic_from_source(base_color, normalized)
    f0 = _f0_from_material_maps(base_color, metallic, normalized)
    f90_mask = _f90_mask_from_material_maps(base_color, height, roughness, curvature, ao, normalized)
    maps = {
        "base_color_source": base_color_raw,
        "base_color": base_color,
        "height": height,
        "normal": normal,
        "ao": ao,
        "roughness": roughness,
        "metallic": metallic,
        "irradiance": delight_shading,
        "delight_shading": delight_shading,
        "cavity": cavity,
        "curvature": curvature,
        "f0": f0,
        "f90_mask": f90_mask,
    }
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(source_path or ""),
        "settings": dict(normalized),
        "size": [int(image.size[0]), int(image.size[1])],
        "maps": maps,
        "algorithms": _algorithm_metadata(normalized),
        "diagnostics": _map_diagnostics(maps),
    }


def generate_texture_maps_from_image(
    image: Image.Image,
    settings: Mapping[str, Any] | None = None,
    *,
    max_size: int | None = None,
    source_path: str = "",
    backend: str | None = None,
    allow_cpu: bool = True,
) -> dict[str, Any]:
    """Generate base, scalar, normal, and packed-ready PBR maps from an in-memory image."""
    normalized = normalize_texture_map_settings(settings)
    selected_backend = select_texture_map_backend(backend, allow_cpu=allow_cpu)
    if selected_backend["active"] == "unavailable":
        raise TextureMapGpuRequiredError(
            f"Texture Lab requires a GPU backend; CPU fallback is disabled ({selected_backend['reason']})."
        )
    resized = _resize_for_max_size(image.convert("RGB"), max_size)
    if selected_backend["active"] == "torch_cuda":
        try:
            result = _generate_texture_maps_torch_cuda(resized, normalized, source_path=source_path)
        except Exception as exc:
            if not allow_cpu:
                selected_backend = dict(selected_backend)
                selected_backend["reason"] = f"torch_cuda_failed:{type(exc).__name__}"
                selected_backend["gpu_required"] = True
                raise TextureMapGpuRequiredError(
                    f"Texture Lab GPU backend failed and CPU fallback is disabled: {type(exc).__name__}: {exc}"
                ) from exc
            fallback_backend = select_texture_map_backend("cpu")
            fallback_backend["requested"] = selected_backend.get("requested", "torch_cuda")
            fallback_backend["fallback"] = True
            fallback_backend["reason"] = f"torch_cuda_failed:{type(exc).__name__}"
            result = _generate_texture_maps_cpu(resized, normalized, source_path=source_path)
            selected_backend = fallback_backend
    else:
        result = _generate_texture_maps_cpu(resized, normalized, source_path=source_path)
    result["backend"] = selected_backend
    result["source_fingerprint"] = texture_source_fingerprint(resized)
    result["settings_fingerprint"] = texture_map_settings_fingerprint(normalized)
    return result


def generate_texture_maps(
    image_path: str | Path,
    settings: Mapping[str, Any] | None = None,
    *,
    max_size: int | None = None,
    backend: str | None = None,
    allow_cpu: bool = True,
) -> dict[str, Any]:
    """Generate base, scalar, normal, and packed-ready PBR maps from an image."""
    path = Path(image_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(str(path))
    with Image.open(path) as source:
        image = source.convert("RGB")
    return generate_texture_maps_from_image(
        image,
        settings,
        max_size=max_size,
        source_path=str(path),
        backend=backend,
        allow_cpu=allow_cpu,
    )


def _algorithm_metadata(settings: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "height": "luma_contrast_edge_aware_heightfield",
        "normal": {
            "method": str(settings.get("normal_filter", "sobel")),
            "source": "heightfield_gradient",
            "format": str(settings.get("normal_format", "unreal_directx")),
        },
        "ambient_occlusion": {
            "method": str(settings.get("ao_algorithm", "heightfield_horizon")),
            "source": "heightfield_horizon_search",
            "samples": int(settings.get("ao_samples", 8)),
            "steps": int(settings.get("ao_steps", 8)),
            "multiscale": bool(settings.get("ao_multiscale", True)),
        },
        "cavity": {
            "method": "multi_scale_concavity",
            "source": "heightfield_curvature_and_local_relief",
        },
        "curvature": {
            "method": "signed_heightfield_laplacian",
            "encoding": "0.5 neutral, brighter convex, darker concave",
        },
        "f0": {
            "method": "metalness_to_substrate_f0",
            "source": "base_color_metallic_reflectance",
            "reflectance": float(settings.get("substrate_reflectance", 0.5)),
            "active_workflow": bool(settings.get("substrate_enabled", False)),
        },
        "f90_mask": {
            "method": "heuristic_grazing_response_mask",
            "source": "heightfield_relief_curvature_smoothness_ao",
            "strength": float(settings.get("f90_mask_strength", 0.45)),
        },
        "delight": {
            "enabled": bool(settings.get("delight_enabled", False)),
            "method": "low_frequency_intrinsic_de_lighting",
            "source": "base_color_luminance_edge_aware_illumination_field",
            "strength": float(settings.get("delight_strength", 0.65)),
            "radius_px": float(settings.get("delight_radius_px", 42.0)),
            "contrast_preservation": float(settings.get("delight_contrast_preservation", 0.25)),
        },
        "substrate": {
            "enabled": bool(settings.get("substrate_enabled", False)),
            "mode": str(settings.get("substrate_mode", "off")),
            "metallic_direct_input": False if bool(settings.get("substrate_enabled", False)) else True,
            "metallic_policy": "helper_input_only_when_substrate_enabled",
        },
        "edge_aware": bool(settings.get("edge_aware_smoothing", True)),
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
        "enabled": bool(normalized.get("substrate_enabled", False)),
        "mode": str(normalized.get("substrate_mode", "off")),
        "legacy_pbr_compatibility": True,
        "metallic_policy": (
            "disabled_as_direct_substrate_input_helper_conversion_only"
            if bool(normalized.get("substrate_enabled", False))
            else "legacy_default_lit_direct_input"
        ),
        "generated_map_algorithms": _algorithm_metadata(normalized),
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
                    "Specular": normalized["substrate_reflectance"],
                    "Metallic": "metallic or packed.B",
                },
                "slab_inputs": {
                    "DiffuseAlbedo": "helper.DiffuseAlbedo",
                    "F0": "helper.F0 or optional f0 map",
                    "Roughness": "roughness or packed.G",
                    "Normal": "normal",
                },
                "root_or_material_inputs": {
                    "AmbientOcclusion": "ao or packed.R",
                },
            },
        },
        "optional_substrate_maps": {
            "f0": {
                "map": "f0",
                "default_export": False,
                "texture_import": dict(UNREAL_TEXTURE_IMPORT_SETTINGS["f0"]),
                "use": "Optional direct F0 override when the material graph needs per-pixel specular response.",
            },
            "f90_mask": {
                "map": "f90_mask",
                "default_export": False,
                "texture_import": dict(UNREAL_TEXTURE_IMPORT_SETTINGS["f90_mask"]),
                "use": "Optional mask for grazing-angle edge color/F90 response or layer coverage.",
            },
        },
        "packed_layouts": {
            name: packed_layout_metadata(name) for name in ("unreal_orm", "arm", "gltf_mr", "rma")
        },
        "future_substrate_optional_maps": {
            "SecondRoughness": "dual-lobe surface map for complex coatings",
            "Anisotropy": "anisotropy scalar plus tangent direction map",
            "Fuzz": "cloth/fiber fuzz amount, color, and roughness",
            "Glint": "sparkle/glint mask for microfacets",
        },
    }


def _normalize_preview_shape(value: Any) -> str:
    shape = str(value or "plane").strip().lower()
    if shape not in PREVIEW_SHAPES:
        raise ValueError(f"unknown preview shape: {value}")
    return shape


def _texture_lab_label_font(pixel_size: int) -> ImageFont.ImageFont:
    size = max(12, int(pixel_size))
    for name in (
        "malgunbd.ttf",
        "malgun.ttf",
        "segoeuib.ttf",
        "seguisb.ttf",
        "arialbd.ttf",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _sample_map_nearest(value: np.ndarray, x_index: np.ndarray, y_index: np.ndarray) -> np.ndarray:
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim < 2:
        arr = np.asarray(arr).reshape((1, 1))
    y = np.clip(y_index, 0, max(0, arr.shape[0] - 1)).astype(np.int32)
    x = np.clip(x_index, 0, max(0, arr.shape[1] - 1)).astype(np.int32)
    return arr[y, x]


def _sphere_material_preview_array(maps: Mapping[str, np.ndarray], settings: Mapping[str, Any]) -> np.ndarray:
    base_src = np.asarray(maps["base_color"], dtype=np.float32)
    tex_h, tex_w = base_src.shape[:2]
    out_h = max(96, tex_h)
    out_w = max(96, tex_w)
    yy, xx = np.mgrid[0:out_h, 0:out_w].astype(np.float32)
    radius = max(24.0, min(out_w, out_h) * 0.42)
    cx = (out_w - 1.0) * 0.5
    cy = (out_h - 1.0) * 0.50
    nx = (xx - cx) / radius
    ny = (cy - yy) / radius
    rr2 = nx * nx + ny * ny
    mask = rr2 <= 1.0
    nz = np.sqrt(np.clip(1.0 - rr2, 0.0, 1.0))

    u = np.clip(nx * 0.5 + 0.5, 0.0, 1.0)
    v = np.clip(0.5 - ny * 0.5, 0.0, 1.0)
    x_index = np.rint(u * max(1, tex_w - 1)).astype(np.int32)
    y_index = np.rint(v * max(1, tex_h - 1)).astype(np.int32)

    base = _sample_map_nearest(base_src, x_index, y_index)
    roughness = _sample_map_nearest(np.asarray(maps["roughness"], dtype=np.float32), x_index, y_index)
    metallic = _sample_map_nearest(np.asarray(maps["metallic"], dtype=np.float32), x_index, y_index)
    ao = _sample_map_nearest(np.asarray(maps["ao"], dtype=np.float32), x_index, y_index)
    detail = _sample_map_nearest(np.asarray(maps["normal"], dtype=np.float32), x_index, y_index) * 2.0 - 1.0

    geom_normal = np.dstack([nx, ny, nz]).astype(np.float32)
    normal = geom_normal.copy()
    if detail.ndim == 3 and detail.shape[-1] >= 3:
        normal[..., 0] += detail[..., 0] * 0.18
        normal[..., 1] += detail[..., 1] * 0.18
        normal[..., 2] += (detail[..., 2] - 1.0) * 0.08
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

    substrate_enabled = bool(settings.get("substrate_enabled", False))
    if substrate_enabled:
        f0_override = (
            _sample_map_nearest(np.asarray(maps["f0"], dtype=np.float32), x_index, y_index)
            if "f0" in maps
            else None
        )
        diffuse_albedo, f0 = substrate_metalness_to_diffuse_albedo_f0(
            albedo=base,
            metallic=metallic,
            reflectance=settings.get("substrate_reflectance", 0.5),
            f0_override=f0_override,
        )
        f90_mask = (
            _sample_map_nearest(np.asarray(maps["f90_mask"], dtype=np.float32), x_index, y_index)
            if "f90_mask" in maps
            else np.ones_like(metallic)
        )
        f90 = substrate_f90(
            f0=f0,
            f90_color=(1.0, 1.0, 1.0),
            f90_mask=f90_mask,
            strength=float(settings.get("f90_mask_strength", 0.45)),
        )
        fresnel = fresnel_schlick_f90(np.full_like(roughness, vdoth, dtype=np.float32), f0, f90)
    else:
        diffuse_albedo = base
        f0 = material_f0(base, metallic, settings.get("substrate_reflectance", 0.5))
        fresnel = f0 + (1.0 - f0) * ((1.0 - vdoth) ** 5.0)

    alpha = np.maximum(roughness * roughness, 0.001)
    alpha2 = alpha * alpha
    denom = np.maximum(ndoth * ndoth * (alpha2 - 1.0) + 1.0, 1.0e-5)
    d = alpha2 / np.maximum(np.pi * denom * denom, 1.0e-5)
    k = ((roughness + 1.0) * (roughness + 1.0)) / 8.0
    gv = ndotv / np.maximum(ndotv * (1.0 - k) + k, 1.0e-5)
    gl = ndotl / np.maximum(ndotl * (1.0 - k) + k, 1.0e-5)
    if substrate_enabled:
        diffuse = (1.0 - fresnel) * diffuse_albedo / np.pi
    else:
        diffuse = (1.0 - fresnel) * (1.0 - metallic[..., None]) * base / np.pi
    specular = (d[..., None] * gv[..., None] * gl[..., None] * fresnel) / np.maximum(
        4.0 * ndotv[..., None] * ndotl[..., None],
        1.0e-5,
    )
    lit = (diffuse + specular) * ndotl[..., None] * 2.3
    env = diffuse_albedo * float(settings["preview_environment"]) * ao[..., None]
    preview = np.clip(env + lit * ao[..., None], 0.0, 1.0)

    background = np.zeros((out_h, out_w, 3), dtype=np.float32)
    background[..., 0] = 0.030
    background[..., 1] = 0.034
    background[..., 2] = 0.045
    shadow = np.exp(
        -(
            ((xx - cx) / max(1.0, radius * 0.86)) ** 2
            + ((yy - (cy + radius * 0.82)) / max(1.0, radius * 0.18)) ** 2
        )
    )
    background *= 1.0 - shadow[..., None] * 0.38

    edge = np.clip((1.0 - rr2) / 0.10, 0.0, 1.0)
    edge = edge * edge * (3.0 - 2.0 * edge)
    rim = np.clip((1.0 - nz) ** 3.0, 0.0, 1.0) * 0.10
    sphere = np.clip(preview + rim[..., None], 0.0, 1.0)
    blend = (edge * mask.astype(np.float32))[..., None]
    out = background * (1.0 - blend) + sphere * blend
    return np.clip(out, 0.0, 1.0).astype(np.float32)


def render_plane_preview_from_generated(
    generated: Mapping[str, Any],
    settings: Mapping[str, Any] | None = None,
    *,
    preview_mode: str = "material",
    preview_shape: str = "plane",
    output_path: str | Path | None = None,
    width: int = 768,
    height: int | None = None,
    source_path: str | Path | None = None,
    allow_cpu_preview: bool = True,
) -> dict[str, Any]:
    if not allow_cpu_preview:
        from app.ar_pbr.texture_map_gpu_preview import render_texture_lab_gpu_preview_from_generated

        return render_texture_lab_gpu_preview_from_generated(
            generated,
            settings,
            preview_mode=preview_mode,
            preview_shape=preview_shape,
            output_path=output_path,
            width=width,
            height=height,
            source_path=source_path,
        )
    mode = str(preview_mode or "material").strip().lower()
    if mode not in PREVIEW_MODES:
        raise ValueError(f"unknown preview mode: {preview_mode}")
    requested_shape = _normalize_preview_shape(preview_shape)
    w = max(64, int(width or 768))
    if height is not None:
        h = max(64, int(height))
    else:
        h = 0
    maps = generated["maps"]
    preview_settings = dict(generated.get("settings") or {})
    if settings is not None:
        preview_settings.update(normalize_texture_map_settings(settings))
    effective_shape = requested_shape if mode == "material" else "plane"
    if effective_shape == "sphere":
        preview = _sphere_material_preview_array(maps, preview_settings)
    else:
        preview = _preview_array_for_mode(maps, preview_settings, mode)
    preview_img = _to_rgb_image(preview)
    target_w = w
    target_h = h if h else max(64, int(round(preview_img.height * (target_w / max(1, preview_img.width)))))
    if preview_img.size != (target_w, target_h):
        preview_img = preview_img.resize((target_w, target_h), Image.Resampling.BICUBIC)
    if output_path is None:
        source = Path(str(source_path or generated.get("source_path") or "texture_source.png")).expanduser()
        out = source.with_name(f"{source.stem}_pbr_{effective_shape}_preview_{mode}.png")
    else:
        out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    preview_img.save(out)
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(source_path or generated.get("source_path") or ""),
        "preview_path": str(out),
        "preview_mode": mode,
        "preview_shape": effective_shape,
        "requested_preview_shape": requested_shape,
        "size": [int(preview_img.size[0]), int(preview_img.size[1])],
        "settings": preview_settings,
        "algorithms": generated["algorithms"],
        "diagnostics": generated["diagnostics"],
        "backend": generated.get("backend", select_texture_map_backend("cpu")),
        "source_fingerprint": generated.get("source_fingerprint", ""),
        "settings_fingerprint": generated.get("settings_fingerprint", ""),
        "substrate": substrate_export_plan(preview_settings),
    }


def render_source_preview_image(
    image_path: str | Path,
    *,
    preview_shape: str = "plane",
    output_path: str | Path | None = None,
    width: int = 768,
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Render a lightweight source-only preview when full PBR maps are unavailable."""
    path = Path(image_path).expanduser()
    shape = _normalize_preview_shape(preview_shape)
    target_w = max(64, int(width or 768))
    image = Image.open(path).convert("RGB")
    ratio = target_w / max(1, image.width)
    target_h = max(64, int(round(image.height * ratio)))
    if image.size != (target_w, target_h):
        image = image.resize((target_w, target_h), Image.Resampling.BICUBIC)
    if shape == "sphere":
        base = (np.asarray(image, dtype=np.float32) / 255.0).astype(np.float32)
        h, w = base.shape[:2]
        maps = {
            "base_color": base,
            "roughness": np.full((h, w), 0.55, dtype=np.float32),
            "metallic": np.zeros((h, w), dtype=np.float32),
            "ao": np.ones((h, w), dtype=np.float32),
            "normal": np.dstack(
                [
                    np.full((h, w), 0.5, dtype=np.float32),
                    np.full((h, w), 0.5, dtype=np.float32),
                    np.ones((h, w), dtype=np.float32),
                ]
            ),
        }
        preview = _sphere_material_preview_array(maps, normalize_texture_map_settings(settings))
        preview_img = _to_rgb_image(preview)
    else:
        preview_img = image
    if output_path is None:
        out = path.with_name(f"{path.stem}_source_{shape}_preview.png")
    else:
        out = Path(output_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    preview_img.save(out)
    return {
        "schema_id": f"{SCHEMA_ID}.source_preview",
        "source_path": str(path),
        "preview_path": str(out),
        "preview_shape": shape,
        "size": [int(preview_img.width), int(preview_img.height)],
        "backend": {"active": "source_fallback", "preview_renderer": "source_only"},
    }


def render_plane_preview(
    image_path: str | Path,
    settings: Mapping[str, Any] | None = None,
    *,
    preview_mode: str = "material",
    preview_shape: str = "plane",
    output_path: str | Path | None = None,
    width: int = 768,
    height: int | None = None,
    backend: str | None = None,
    allow_cpu: bool = True,
    allow_cpu_preview: bool | None = None,
) -> dict[str, Any]:
    w = max(64, int(width or 768))
    generated = generate_texture_maps(image_path, settings, max_size=w, backend=backend, allow_cpu=allow_cpu)
    cpu_preview_allowed = allow_cpu if allow_cpu_preview is None else bool(allow_cpu_preview)
    return render_plane_preview_from_generated(
        generated,
        settings,
        preview_mode=preview_mode,
        preview_shape=preview_shape,
        output_path=output_path,
        width=width,
        height=height,
        source_path=image_path,
        allow_cpu_preview=cpu_preview_allowed,
    )


def _intrinsic_channels_preview_array(maps: Mapping[str, np.ndarray]) -> np.ndarray:
    base = np.asarray(maps["base_color"], dtype=np.float32)
    tile_w = max(1, int(base.shape[1]))
    tile_h = max(1, int(base.shape[0]))
    label_h = max(34, int(round(tile_h * 0.105)))
    label_font = _texture_lab_label_font(max(14, min(28, int(round(label_h * 0.50)))))
    gap = max(3, int(round(tile_w * 0.012)))
    panels: tuple[tuple[str, str], ...] = (
        ("Input", "base_color_source"),
        ("Albedo", "base_color"),
        ("Normal", "normal"),
        ("Roughness", "roughness"),
        ("Irradiance", "irradiance"),
    )
    canvas_w = tile_w * len(panels) + gap * (len(panels) - 1)
    canvas_h = label_h + tile_h
    canvas = Image.new("RGB", (canvas_w, canvas_h), "#08090C")
    draw = ImageDraw.Draw(canvas)
    x = 0
    for label, map_name in panels:
        value = maps.get(map_name)
        if value is None and map_name == "irradiance":
            value = maps.get("delight_shading")
        if value is None:
            value = np.zeros((tile_h, tile_w), dtype=np.float32)
        tile = texture_map_to_image(map_name, np.asarray(value, dtype=np.float32)).convert("RGB")
        if tile.size != (tile_w, tile_h):
            tile = tile.resize((tile_w, tile_h), Image.Resampling.BICUBIC)
        label_rect = (x, 0, x + tile_w, label_h)
        draw.rectangle(label_rect, fill="#11151D")
        text_bbox = draw.textbbox((0, 0), label, font=label_font)
        text_w = max(1, int(text_bbox[2] - text_bbox[0]))
        text_h = max(1, int(text_bbox[3] - text_bbox[1]))
        text_x = x + max(0, (tile_w - text_w) // 2)
        text_y = max(0, (label_h - text_h) // 2) - 1
        draw.text((text_x, text_y), label, fill="#E8ECF5", font=label_font)
        canvas.paste(tile, (x, label_h))
        x += tile_w + gap
    return (np.asarray(canvas, dtype=np.float32) / 255.0).astype(np.float32)


def _preview_array_for_mode(maps: Mapping[str, np.ndarray], settings: Mapping[str, Any], mode: str) -> np.ndarray:
    if mode == "intrinsic_channels":
        return _intrinsic_channels_preview_array(maps)
    if mode == "albedo":
        return np.asarray(maps["base_color"], dtype=np.float32)
    if mode == "delight_compare":
        source = np.asarray(maps.get("base_color_source", maps["base_color"]), dtype=np.float32)
        delighted = np.asarray(maps["base_color"], dtype=np.float32)
        diff = np.clip(np.abs(delighted - source) * 5.0, 0.0, 1.0)
        if diff.ndim == 2:
            diff = np.dstack([diff, diff, diff])
        divider = np.zeros((source.shape[0], max(1, source.shape[1] // 80), 3), dtype=np.float32)
        divider[..., 0] = 0.18
        divider[..., 1] = 0.24
        divider[..., 2] = 0.33
        return np.concatenate([source, divider, delighted, divider, diff], axis=1).astype(np.float32)
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
    substrate_enabled = bool(settings.get("substrate_enabled", False))
    if substrate_enabled:
        diffuse_albedo, f0 = substrate_metalness_to_diffuse_albedo_f0(
            albedo=base,
            metallic=metallic,
            reflectance=settings.get("substrate_reflectance", 0.5),
            f0_override=maps.get("f0"),
        )
        f90_mask = np.asarray(maps.get("f90_mask", np.ones_like(metallic)), dtype=np.float32)
        f90 = substrate_f90(
            f0=f0,
            f90_color=(1.0, 1.0, 1.0),
            f90_mask=f90_mask,
            strength=float(settings.get("f90_mask_strength", 0.45)),
        )
        fresnel = fresnel_schlick_f90(np.full_like(roughness, vdoth, dtype=np.float32), f0, f90)
    else:
        diffuse_albedo = base
        f0 = np.asarray(maps.get("f0", material_f0(base, metallic, settings.get("substrate_reflectance", 0.5))), dtype=np.float32)
        fresnel = f0 + (1.0 - f0) * ((1.0 - vdoth) ** 5.0)
    # Inline a simplified preview BRDF so the plane render remains responsive.
    alpha = np.maximum(roughness * roughness, 0.001)
    alpha2 = alpha * alpha
    denom = np.maximum(ndoth * ndoth * (alpha2 - 1.0) + 1.0, 1.0e-5)
    d = alpha2 / np.maximum(np.pi * denom * denom, 1.0e-5)
    k = ((roughness + 1.0) * (roughness + 1.0)) / 8.0
    gv = ndotv / np.maximum(ndotv * (1.0 - k) + k, 1.0e-5)
    gl = ndotl / np.maximum(ndotl * (1.0 - k) + k, 1.0e-5)
    if substrate_enabled:
        diffuse = (1.0 - fresnel) * diffuse_albedo / np.pi
    else:
        diffuse = (1.0 - fresnel) * (1.0 - metallic[..., None]) * base / np.pi
    specular = (d[..., None] * gv[..., None] * gl[..., None] * fresnel) / np.maximum(
        4.0 * ndotv[..., None] * ndotl[..., None],
        1.0e-5,
    )
    lit = (diffuse + specular) * ndotl[..., None] * 2.2
    env = diffuse_albedo * float(settings["preview_environment"]) * ao[..., None]
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
    backend: str | None = None,
    allow_cpu: bool = True,
) -> dict[str, Any]:
    path = Path(image_path).expanduser()
    if output_dir is None:
        out_dir = path.with_name(f"{path.stem}_pbr_maps")
    else:
        out_dir = Path(output_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = generate_texture_maps(path, settings, max_size=max_size, backend=backend, allow_cpu=allow_cpu)
    default_maps = (
        tuple(name for name in DEFAULT_SEPARATE_MAPS if name != "metallic") + OPTIONAL_SUBSTRATE_MAPS
        if bool(generated["settings"].get("substrate_enabled", False))
        else DEFAULT_SEPARATE_MAPS
    )
    map_names = _normalize_name_list(maps, default_maps)
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
        "backend": generated.get("backend", select_texture_map_backend("cpu")),
        "source_fingerprint": generated.get("source_fingerprint", ""),
        "settings_fingerprint": generated.get("settings_fingerprint", ""),
        "algorithms": generated["algorithms"],
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
        "algorithms": generated["algorithms"],
        "substrate": manifest["substrate"],
        "diagnostics": generated["diagnostics"],
    }


def _normalize_name_list(values: Sequence[str] | None, defaults: Sequence[str]) -> list[str]:
    rows = list(defaults if values is None else values)
    out: list[str] = []
    for row in rows:
        name = str(row or "").strip().lower()
        if name and name not in out:
            out.append(name)
    return out
