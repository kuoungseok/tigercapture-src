"""Optional OCIO/ACES transform bridge.

The editor can run without OpenColorIO installed, but commercial color
workflows need a real place to plug OCIO into preview/export.  This module is
pure Python and defensive: it reports what would happen, applies transforms
only when PyOpenColorIO and a valid config are available, and otherwise returns
the input frame unchanged with diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from app.color_management import ColorManagementSettings


BUILTIN_OCIO_PREFIX = "ocio://"
PREFERRED_ACES_STUDIO_CONFIG = "studio-config-v2.2.0_aces-v1.3_ocio-v2.4"

OCIO_INPUT_COLORSPACE_CANDIDATES = {
    "rec709": (
        "Camera Rec.709",
        "Gamma 2.4 Encoded Rec.709",
        "sRGB Encoded Rec.709 (sRGB)",
        "Utility - Rec.709 - Texture",
        "Rec.709",
    ),
    "srgb": (
        "sRGB Encoded Rec.709 (sRGB)",
        "sRGB - Texture",
        "Utility - sRGB - Texture",
        "sRGB",
    ),
    "rec2020": ("Linear Rec.2020", "Utility - Rec.2020 - Texture", "Rec.2020"),
    "p3-d65": ("sRGB Encoded P3-D65", "Linear P3-D65", "P3-D65"),
    "acescg": ("ACEScg", "ACES - ACEScg"),
    "acescct": ("ACEScct", "ACES - ACEScct"),
}

OCIO_OUTPUT_COLORSPACE_CANDIDATES = {
    "rec709": (
        "Rec.1886 Rec.709 - Display",
        "Output - Rec.709",
        "sRGB - Display",
        "Gamma 2.4 Encoded Rec.709",
        "Rec.709",
    ),
    "srgb": (
        "sRGB - Display",
        "Output - sRGB",
        "sRGB Encoded Rec.709 (sRGB)",
        "sRGB",
    ),
    "rec2020": (
        "Rec.2100-HLG - Display",
        "Output - Rec.2020",
        "Linear Rec.2020",
        "Rec.2020",
    ),
    "p3-d65": ("P3-D65 - Display", "Display P3 - Display", "Output - P3-D65", "P3-D65"),
    "acescg": ("ACEScg", "ACES - ACEScg"),
    "acescct": ("ACEScct", "ACES - ACEScct"),
}


@dataclass(frozen=True)
class OcioPlan:
    available: bool
    enabled: bool
    config_path: str
    source: str
    destination: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": bool(self.available),
            "enabled": bool(self.enabled),
            "config_path": self.config_path,
            "source": self.source,
            "destination": self.destination,
            "warnings": list(self.warnings),
        }


def _import_ocio():
    try:
        import PyOpenColorIO as ocio  # type: ignore

        return ocio
    except Exception:
        try:
            import OpenColorIO as ocio  # type: ignore

            return ocio
        except Exception:
            return None


def ocio_available() -> bool:
    return _import_ocio() is not None


def builtin_ocio_uri(name: str) -> str:
    return f"{BUILTIN_OCIO_PREFIX}{str(name or '').strip()}"


def list_builtin_ocio_configs() -> list[dict[str, Any]]:
    ocio = _import_ocio()
    if ocio is None:
        return []
    try:
        rows = []
        for name, description, is_default, is_recommended in ocio.BuiltinConfigRegistry().getBuiltinConfigs():
            rows.append({
                "name": str(name),
                "uri": builtin_ocio_uri(str(name)),
                "description": str(description),
                "default": bool(is_default),
                "recommended": bool(is_recommended),
                "studio": str(name).startswith("studio-config-"),
            })
        return rows
    except Exception:
        return []


def preferred_aces_ocio_uri() -> str:
    names = {row["name"] for row in list_builtin_ocio_configs()}
    if PREFERRED_ACES_STUDIO_CONFIG in names:
        return builtin_ocio_uri(PREFERRED_ACES_STUDIO_CONFIG)
    studio = [row for row in list_builtin_ocio_configs() if row["studio"]]
    if studio:
        recommended = next((row for row in studio if row["recommended"]), studio[-1])
        return str(recommended["uri"])
    return ""


def _builtin_config_name(spec: str) -> str:
    value = str(spec or "").strip()
    return value[len(BUILTIN_OCIO_PREFIX):] if value.startswith(BUILTIN_OCIO_PREFIX) else ""


@lru_cache(maxsize=12)
def _load_config(spec: str):
    ocio = _import_ocio()
    if ocio is None:
        raise RuntimeError("PyOpenColorIO is not installed.")
    builtin_name = _builtin_config_name(spec)
    if builtin_name:
        return ocio.Config.CreateFromBuiltinConfig(builtin_name)
    return ocio.Config.CreateFromFile(str(spec))


def ocio_config_exists(spec: str) -> bool:
    value = str(spec or "").strip()
    if not value:
        return False
    if value.startswith(BUILTIN_OCIO_PREFIX):
        name = _builtin_config_name(value)
        return any(row["name"] == name for row in list_builtin_ocio_configs())
    return Path(value).is_file()


def _candidate_name(config: Any, key: str, *, destination: bool) -> str:
    table = (
        OCIO_OUTPUT_COLORSPACE_CANDIDATES
        if destination
        else OCIO_INPUT_COLORSPACE_CANDIDATES
    )
    candidates = table.get(key, (key,))
    for name in candidates:
        try:
            if config.getColorSpace(name) is not None:
                return name
        except Exception:
            continue
    return candidates[0]


def build_ocio_plan(
    settings: ColorManagementSettings | dict[str, Any] | None,
    *,
    source: str | None = None,
    destination: str | None = None,
) -> OcioPlan:
    cm = ColorManagementSettings.from_dict(settings) if isinstance(settings, dict) or settings is None else settings
    warnings: list[str] = []
    ocio = _import_ocio()
    if ocio is None:
        warnings.append("PyOpenColorIO is not installed.")
        return OcioPlan(False, False, cm.ocio_config_path, source or cm.input_space, destination or cm.working_space, tuple(warnings))
    if not cm.ocio_config_path:
        warnings.append("No OCIO config path is configured.")
        return OcioPlan(True, False, "", source or cm.input_space, destination or cm.working_space, tuple(warnings))
    if not ocio_config_exists(cm.ocio_config_path):
        warnings.append("OCIO config is unavailable.")
        return OcioPlan(True, False, cm.ocio_config_path, source or cm.input_space, destination or cm.working_space, tuple(warnings))
    try:
        config = _load_config(cm.ocio_config_path)
        source_key = str(source or cm.input_space)
        destination_key = str(destination or cm.working_space)
        src = (
            _candidate_name(config, source_key, destination=False)
            if source_key in OCIO_INPUT_COLORSPACE_CANDIDATES
            else source_key
        )
        dst = (
            _candidate_name(config, destination_key, destination=True)
            if destination_key in OCIO_OUTPUT_COLORSPACE_CANDIDATES
            else destination_key
        )
        return OcioPlan(True, True, cm.ocio_config_path, src, dst, tuple(warnings))
    except Exception as exc:
        warnings.append(f"Could not load OCIO config: {exc}")
        return OcioPlan(True, False, cm.ocio_config_path, source or cm.input_space, destination or cm.working_space, tuple(warnings))


def apply_ocio_transform_rgb(
    rgb: np.ndarray,
    settings: ColorManagementSettings | dict[str, Any] | None,
    *,
    source: str | None = None,
    destination: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply an OCIO color-space transform when available.

    Returns `(frame, report)`.  On any unavailable/misconfigured path, `frame`
    is the original ndarray and `report["applied"]` is False.
    """
    plan = build_ocio_plan(settings, source=source, destination=destination)
    report = plan.to_dict()
    report["applied"] = False
    if not plan.enabled:
        return rgb, report
    ocio = _import_ocio()
    if ocio is None:
        return rgb, report
    try:
        config = _load_config(plan.config_path)
        processor = config.getProcessor(plan.source, plan.destination)
        cpu = processor.getDefaultCPUProcessor()
        arr = rgb.astype(np.float32) / 255.0
        flat = np.ascontiguousarray(arr.reshape(-1, 3))
        # PyOpenColorIO mutates packed RGB data in place.
        cpu.applyRGB(flat)
        out = np.clip(flat.reshape(arr.shape) * 255.0 + 0.5, 0, 255).astype(np.uint8)
        report["applied"] = True
        return out, report
    except Exception as exc:
        report.setdefault("warnings", []).append(f"OCIO transform failed: {exc}")
        return rgb, report


__all__ = [
    "BUILTIN_OCIO_PREFIX",
    "OcioPlan",
    "apply_ocio_transform_rgb",
    "build_ocio_plan",
    "builtin_ocio_uri",
    "list_builtin_ocio_configs",
    "ocio_available",
    "ocio_config_exists",
    "preferred_aces_ocio_uri",
]
