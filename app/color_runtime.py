"""Shared project display/output color transforms.

Preview stays an 8-bit display surface, while export conversion is expressed as
an FFmpeg filter graph. The default Rec.709/sRGB path is deliberately a no-op.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from app.color_management import ColorManagementSettings, ffmpeg_filter_path


def _settings(value: ColorManagementSettings | dict[str, Any] | None) -> ColorManagementSettings:
    return value if isinstance(value, ColorManagementSettings) else ColorManagementSettings.from_dict(value)


def _srgb_to_linear(value: np.ndarray) -> np.ndarray:
    encoded = np.clip(value, 0.0, 1.0)
    return np.where(
        encoded <= 0.04045,
        encoded / 12.92,
        ((encoded + 0.055) / 1.055) ** 2.4,
    )


def _linear_to_srgb(value: np.ndarray) -> np.ndarray:
    linear = np.clip(value, 0.0, 1.0)
    return np.where(
        linear <= 0.0031308,
        linear * 12.92,
        1.055 * np.power(linear, 1.0 / 2.4) - 0.055,
    )


def _aces_fitted(value: np.ndarray) -> np.ndarray:
    linear = _srgb_to_linear(value)
    mapped = linear * (2.51 * linear + 0.03) / (
        linear * (2.43 * linear + 0.59) + 0.14
    )
    return _linear_to_srgb(np.clip(mapped, 0.0, 1.0))


def display_transform_required(
    settings: ColorManagementSettings | dict[str, Any] | None,
) -> bool:
    cm = _settings(settings)
    if not cm.preview_transform_enabled:
        return False
    return bool(
        cm.ocio_config_path
        or cm.view_transform == "aces-1.3"
        or cm.working_space in {"acescg", "acescct"}
    )


def apply_project_display_transform_rgb(
    rgb: np.ndarray,
    settings: ColorManagementSettings | dict[str, Any] | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Transform uint8 RGB into the application's SDR preview display space."""
    cm = _settings(settings)
    report: dict[str, Any] = {
        "schema": "tigerstudio.color.runtime.v2",
        "applied": False,
        "engine": "identity",
        "view_transform": cm.view_transform,
        "working_space": cm.working_space,
        "output_space": cm.output_space,
        "output_transfer": cm.output_transfer,
        "hdr_preview": "sdr_display_transform" if cm.is_hdr() else "sdr",
        "warnings": [],
    }
    source = np.asarray(rgb, dtype=np.uint8)
    if not display_transform_required(cm):
        return source, report

    if cm.ocio_config_path:
        try:
            from app.color_ocio import apply_ocio_transform_rgb

            transformed, ocio_report = apply_ocio_transform_rgb(
                source,
                cm,
                source=cm.input_space,
                destination=cm.output_space if not cm.is_hdr() else "rec709",
            )
            report["ocio"] = ocio_report
            if ocio_report.get("applied"):
                report["applied"] = True
                report["engine"] = "ocio"
                return np.ascontiguousarray(transformed), report
            report["warnings"].extend(ocio_report.get("warnings", []))
        except Exception as exc:
            report["warnings"].append(f"OCIO preview transform failed: {exc}")

    if cm.view_transform == "aces-1.3" or cm.working_space in {"acescg", "acescct"}:
        values = source.astype(np.float32) / 255.0
        output = np.rint(_aces_fitted(values) * 255.0).clip(0, 255).astype(np.uint8)
        report["applied"] = True
        report["engine"] = "aces_fitted_fallback"
        if cm.ocio_config_path:
            report["warnings"].append("Using ACES-fitted fallback because OCIO is unavailable.")
        return np.ascontiguousarray(output), report
    return source, report


def apply_project_display_transform_premultiplied_rgba(
    rgba: np.ndarray,
    settings: ColorManagementSettings | dict[str, Any] | None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply the display transform without damaging translucent edge colors."""
    source = np.asarray(rgba, dtype=np.uint8)
    if source.ndim != 3 or source.shape[-1] != 4:
        raise ValueError("rgba must have shape (height, width, 4)")
    alpha = source[..., 3:4].astype(np.float32) / 255.0
    straight = np.divide(
        source[..., :3].astype(np.float32),
        alpha,
        out=np.zeros_like(source[..., :3], dtype=np.float32),
        where=alpha > 1e-8,
    )
    straight_u8 = np.rint(straight).clip(0, 255).astype(np.uint8)
    transformed, report = apply_project_display_transform_rgb(straight_u8, settings)
    output = source.copy()
    output[..., :3] = np.rint(
        transformed.astype(np.float32) * alpha
    ).clip(0, 255).astype(np.uint8)
    return output, report


def _display_lut_cache_path(cm: ColorManagementSettings, size: int) -> Path:
    ocio_signature: dict[str, Any] = {}
    if cm.ocio_config_path:
        if cm.ocio_config_path.startswith("ocio://"):
            ocio_signature = {"builtin": cm.ocio_config_path}
        else:
            try:
                stat = Path(cm.ocio_config_path).stat()
                ocio_signature = {
                    "size": int(stat.st_size),
                    "mtime_ns": int(stat.st_mtime_ns),
                }
            except OSError:
                ocio_signature = {"missing": True}
    payload = {
        "schema": "tigerstudio.color.runtime.v2",
        "size": int(size),
        "input_space": cm.input_space,
        "working_space": cm.working_space,
        "output_space": cm.output_space,
        "view_transform": cm.view_transform,
        "ocio_config_path": cm.ocio_config_path,
        "ocio_signature": ocio_signature,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    root = Path(tempfile.gettempdir()) / "TigerStudioColorCache"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"display_{digest}_{int(size)}.cube"


def ensure_display_lut(
    settings: ColorManagementSettings | dict[str, Any] | None,
    *,
    size: int = 33,
) -> tuple[str, dict[str, Any]]:
    """Bake the preview display transform into a deterministic 3D LUT."""
    cm = _settings(settings)
    if not display_transform_required(cm):
        return "", {"applied": False, "engine": "identity", "warnings": []}
    size = max(2, min(65, int(size)))
    path = _display_lut_cache_path(cm, size)
    if path.is_file() and path.stat().st_size > 128:
        _sample, report = apply_project_display_transform_rgb(
            np.zeros((1, 1, 3), dtype=np.uint8),
            cm,
        )
        report["cache_hit"] = True
        report["lut_engine"] = "cached_3d_lut"
        return str(path), report
    axis = np.linspace(0, 255, size, dtype=np.uint8)
    samples = np.asarray(
        [[red, green, blue] for blue in axis for green in axis for red in axis],
        dtype=np.uint8,
    ).reshape(-1, 1, 3)
    transformed, report = apply_project_display_transform_rgb(samples, cm)
    values = transformed.reshape(-1, 3).astype(np.float32) / 255.0
    lines = [
        'TITLE "Tiger Studio display transform"',
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    lines.extend(f"{row[0]:.8f} {row[1]:.8f} {row[2]:.8f}" for row in values)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    report["cache_hit"] = False
    report["lut_engine"] = "generated_3d_lut"
    return str(path), report


def append_project_output_transform_graph(
    graph: str,
    input_label: str,
    settings: ColorManagementSettings | dict[str, Any] | None,
    *,
    output_prefix: str = "outv_color",
) -> tuple[str, str, dict[str, Any]]:
    """Append ACES/OCIO display LUT and Rec.2020 PQ/HLG encoding filters."""
    cm = _settings(settings)
    parts = [graph] if graph else []
    current = input_label
    report: dict[str, Any] = {
        "display_lut": "",
        "hdr_transfer": "",
        "warnings": [],
    }
    if display_transform_required(cm):
        lut_path, lut_report = ensure_display_lut(cm)
        report["warnings"].extend(lut_report.get("warnings", []))
        if lut_path:
            next_label = f"{output_prefix}_view"
            parts.append(
                f"[{current}]lut3d=file='{ffmpeg_filter_path(lut_path)}':"
                f"interp=tetrahedral[{next_label}]"
            )
            current = next_label
            report["display_lut"] = lut_path
    if cm.output_space == "rec2020" and cm.output_transfer in {"pq", "hlg"}:
        transfer = "smpte2084" if cm.output_transfer == "pq" else "arib-std-b67"
        next_label = f"{output_prefix}_hdr"
        parts.append(
            f"[{current}]zscale=pin=bt709:tin=bt709:min=bt709:"
            f"p=bt2020:t={transfer}:m=bt2020nc,format=yuv420p10le[{next_label}]"
        )
        current = next_label
        report["hdr_transfer"] = cm.output_transfer
    return ";".join(parts), current, report


__all__ = [
    "append_project_output_transform_graph",
    "apply_project_display_transform_rgb",
    "apply_project_display_transform_premultiplied_rgba",
    "display_transform_required",
    "ensure_display_lut",
]
