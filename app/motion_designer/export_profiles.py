"""Qt-free standard output profiles and FFmpeg capability preflight."""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.subprocess_utils import hidden_subprocess_kwargs

from .color_management import settings_from_composition_metadata, validate_motion_color_settings


@dataclass(frozen=True, slots=True)
class MotionExportProfile:
    id: str
    label: str
    kind: str
    extension: str
    encoder: str = ""
    muxer: str = ""
    alpha: bool = False
    scene_linear: bool = False
    ffmpeg_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_PROFILES = (
    MotionExportProfile("h264_mp4", "H.264 MP4", "video", ".mp4", "libx264", "mp4", ffmpeg_required=True),
    MotionExportProfile("h265_mp4", "H.265 MP4", "video", ".mp4", "libx265", "mp4", ffmpeg_required=True),
    MotionExportProfile("prores_4444_mov", "ProRes 4444 MOV", "video", ".mov", "prores_ks", "mov", alpha=True, ffmpeg_required=True),
    MotionExportProfile("png_sequence", "PNG RGBA Sequence", "sequence", ".png", alpha=True),
    MotionExportProfile("openexr_sequence", "OpenEXR Scene-linear Sequence", "sequence", ".exr", "exr", "image2", alpha=True, scene_linear=True, ffmpeg_required=True),
    MotionExportProfile("png_still", "PNG RGBA Still", "still", ".png", alpha=True),
    MotionExportProfile("jpeg_still", "JPEG Still", "still", ".jpg"),
    MotionExportProfile("webp_still", "WebP RGBA Still", "still", ".webp", alpha=True),
)
MOTION_EXPORT_PROFILES = {profile.id: profile for profile in _PROFILES}


def list_motion_export_profiles() -> list[dict[str, Any]]:
    return [profile.to_dict() for profile in _PROFILES]


def get_motion_export_profile(profile_id: str) -> MotionExportProfile:
    try:
        return MOTION_EXPORT_PROFILES[str(profile_id)]
    except KeyError as exc:
        raise ValueError(f"Unknown Motion export profile: {profile_id}") from exc


def find_ffmpeg_executable(explicit: str | Path | None = None) -> str:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return str(path) if path.is_file() else ""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        bundled = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
        return str(bundled) if bundled.is_file() else ""
    except Exception:
        return ""


@lru_cache(maxsize=4)
def _probe_encoder_names(ffmpeg_path: str) -> frozenset[str]:
    if not ffmpeg_path:
        return frozenset()
    try:
        completed = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except Exception:
        return frozenset()
    names: set[str] = set()
    for line in completed.stdout.splitlines():
        match = re.match(r"^\s*[A-Z.]{6}\s+(\S+)", line)
        if match:
            names.add(match.group(1))
    return frozenset(names)


def ffmpeg_capabilities(ffmpeg_path: str | Path | None = None) -> dict[str, Any]:
    executable = find_ffmpeg_executable(ffmpeg_path)
    encoders = _probe_encoder_names(executable)
    required = sorted({profile.encoder for profile in _PROFILES if profile.encoder})
    return {
        "available": bool(executable),
        "path": executable,
        "encoders": sorted(encoders),
        "motion_encoders": {name: name in encoders for name in required},
    }


def preflight_motion_export(composition: Any, profile_id: str, *, output_path: str | Path = "",
                            fps: float | None = None, ffmpeg_path: str | Path | None = None) -> dict[str, Any]:
    profile = get_motion_export_profile(profile_id)
    errors: list[str] = []
    warnings: list[str] = []
    width = int(getattr(composition, "width", 0) or 0)
    height = int(getattr(composition, "height", 0) or 0)
    frame_rate = float(fps or getattr(composition, "fps", 0.0) or 0.0)
    duration_ms = int(getattr(composition, "duration_ms", 0) or 0)
    if width <= 0 or height <= 0:
        errors.append("Motion composition dimensions must be positive")
    if frame_rate <= 0 or frame_rate > 120:
        errors.append("Motion export fps must be in the range 0 < fps <= 120")
    if duration_ms <= 0:
        errors.append("Motion composition duration must be positive")
    if profile.id in {"h264_mp4", "h265_mp4"} and (width % 2 or height % 2):
        errors.append("H.264/H.265 4:2:0 output requires even dimensions")
    output = Path(output_path).expanduser() if output_path else None
    if output is not None and profile.kind != "sequence" and output.suffix.lower() != profile.extension:
        errors.append(f"Profile {profile.id} requires a {profile.extension} output path")
    capabilities = ffmpeg_capabilities(ffmpeg_path) if profile.ffmpeg_required else {
        "available": True, "path": "", "encoders": [], "motion_encoders": {},
    }
    if profile.ffmpeg_required and not capabilities["available"]:
        errors.append("FFmpeg is required but was not found")
    if profile.encoder and capabilities["available"] and profile.encoder not in capabilities["encoders"]:
        errors.append(f"FFmpeg encoder is unavailable: {profile.encoder}")
    color_settings = settings_from_composition_metadata(getattr(composition, "metadata", {}))
    color_report = validate_motion_color_settings(color_settings)
    errors.extend(color_report["errors"])
    warnings.extend(color_report["warnings"])
    if color_settings.project.is_hdr() and profile.id != "h265_mp4":
        errors.append("Motion HDR output currently requires the H.265 MP4 profile")
    if color_report["internal_layer_blend"] != "linear-srgb":
        warnings.append("Internal Motion layer blend modes still use the Qt display-space render graph")
    if profile.scene_linear and color_settings.blend_space != "linear-srgb":
        errors.append("OpenEXR scene-linear output requires a linear-sRGB Motion composition")
    if not profile.alpha:
        warnings.append("This profile discards alpha and composites Motion over opaque black")
    return {
        "ok": not errors,
        "profile": profile.to_dict(),
        "output_path": str(output.resolve()) if output is not None else "",
        "width": width,
        "height": height,
        "fps": frame_rate,
        "duration_ms": duration_ms,
        "frame_count": max(1, int((duration_ms / 1000.0 * frame_rate) + 0.999999)) if frame_rate > 0 else 0,
        "alpha_contract": {
            "storage": "straight" if profile.alpha else "discarded",
            "internal": "premultiplied",
            "premultiply_space": color_settings.premultiply_space,
        },
        "color": color_report,
        "ffmpeg": capabilities,
        "errors": errors,
        "warnings": warnings,
    }


__all__ = [
    "MOTION_EXPORT_PROFILES", "MotionExportProfile", "ffmpeg_capabilities",
    "find_ffmpeg_executable", "get_motion_export_profile", "list_motion_export_profiles",
    "preflight_motion_export",
]
