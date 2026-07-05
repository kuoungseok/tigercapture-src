"""Optional OCIO/ACES transform bridge.

The editor can run without OpenColorIO installed, but commercial color
workflows need a real place to plug OCIO into preview/export.  This module is
pure Python and defensive: it reports what would happen, applies transforms
only when PyOpenColorIO and a valid config are available, and otherwise returns
the input frame unchanged with diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.color_management import ColorManagementSettings


OCIO_COLORSPACE_CANDIDATES = {
    "rec709": ("Rec.709", "Output - Rec.709", "Utility - Rec.709 - Texture", "sRGB - Display"),
    "srgb": ("sRGB", "Utility - sRGB - Texture", "Output - sRGB", "sRGB - Display"),
    "rec2020": ("Rec.2020", "Output - Rec.2020", "Utility - Rec.2020 - Texture"),
    "p3-d65": ("P3-D65", "Display P3", "Output - P3-D65"),
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


def _candidate_name(config: Any, key: str) -> str:
    candidates = OCIO_COLORSPACE_CANDIDATES.get(key, (key,))
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
    if not Path(cm.ocio_config_path).is_file():
        warnings.append("OCIO config path does not exist.")
        return OcioPlan(True, False, cm.ocio_config_path, source or cm.input_space, destination or cm.working_space, tuple(warnings))
    try:
        config = ocio.Config.CreateFromFile(cm.ocio_config_path)
        src = source or _candidate_name(config, cm.input_space)
        dst = destination or _candidate_name(config, cm.working_space)
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
        config = ocio.Config.CreateFromFile(plan.config_path)
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
