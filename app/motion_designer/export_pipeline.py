"""Profile-driven Motion file export using the shared renderer and FFmpeg."""
from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtGui import QImage

from app.color_management import ffmpeg_color_args
from app.subprocess_utils import hidden_subprocess_kwargs

from .color_management import (
    composite_premultiplied_srgb_over_srgb,
    premultiplied_srgb_to_linear_gbrap_f32_bytes,
    premultiplied_srgb_to_straight_rgba_u8,
    settings_from_composition_metadata,
)
from .color_runtime import apply_motion_color_pipeline_premultiplied_rgba
from .export_profiles import get_motion_export_profile, preflight_motion_export
from .schema import MotionComposition


def _qimage_from_rgb(rgb: np.ndarray) -> QImage:
    data = np.ascontiguousarray(rgb, dtype=np.uint8)
    height, width = data.shape[:2]
    return QImage(data.data, width, height, data.strides[0], QImage.Format_RGB888).copy()


def _qimage_from_premultiplied_rgba(rgba: np.ndarray) -> QImage:
    data = np.ascontiguousarray(rgba, dtype=np.uint8)
    height, width = data.shape[:2]
    return QImage(
        data.data,
        width,
        height,
        data.strides[0],
        QImage.Format_RGBA8888_Premultiplied,
    ).copy()


def _without_pixel_format(args: list[str]) -> list[str]:
    output: list[str] = []
    index = 0
    while index < len(args):
        if args[index] == "-pix_fmt":
            index += 2
            continue
        output.append(args[index])
        index += 1
    return output


class MotionProfileExporter:
    def __init__(self, renderer: Any | None = None, *, ffmpeg_path: str | Path | None = None,
                 cancel_check: Callable[[], bool] | None = None) -> None:
        if renderer is None:
            from .export_renderer import MotionExportRenderer

            renderer = MotionExportRenderer(cache_capacity=4)
        self.renderer = renderer
        self.ffmpeg_path = ffmpeg_path
        self.cancel_check = cancel_check or (lambda: False)

    def _check_cancelled(self) -> None:
        if self.cancel_check():
            raise MotionExportCancelled("Motion export cancelled")

    def export(self, composition: MotionComposition, profile_id: str, output_path: str | Path, *,
               fps: float | None = None, time_ms: float = 0.0,
               resume: bool = False) -> dict[str, Any]:
        profile = get_motion_export_profile(profile_id)
        output = Path(output_path).expanduser().resolve()
        report = preflight_motion_export(
            composition, profile.id, output_path=output, fps=fps, ffmpeg_path=self.ffmpeg_path,
        )
        if not report["ok"]:
            raise RuntimeError("Motion export preflight failed: " + "; ".join(report["errors"]))
        if profile.kind == "still":
            self._check_cancelled()
            return self._export_still(composition, profile.id, output, float(time_ms), report)
        if profile.id == "png_sequence":
            return self._export_png_sequence(composition, output, report, resume=resume)
        if resume and profile.kind == "sequence":
            raise ValueError(f"Resume is not supported for Motion profile: {profile.id}")
        return self._export_ffmpeg(composition, profile.id, output, report)

    def _export_png_sequence(self, composition: MotionComposition, output: Path,
                             report: dict[str, Any], *, resume: bool) -> dict[str, Any]:
        output.mkdir(parents=True, exist_ok=True)
        manifest_path = output / "manifest.json"
        manifest_path.unlink(missing_ok=True)
        if not resume:
            for stale in output.glob("frame_*.png"):
                stale.unlink(missing_ok=True)
        frames: list[Path] = []
        rendered_count = 0
        resumed_count = 0
        for index in range(int(report["frame_count"])):
            self._check_cancelled()
            path = output / f"frame_{index:06d}.png"
            if resume and self._is_valid_png(path):
                frames.append(path)
                resumed_count += 1
                continue
            rgba = self.renderer.render_rgba_array(
                composition,
                index * 1000.0 / float(report["fps"]),
            )
            color = settings_from_composition_metadata(composition.metadata)
            rgba, _color_report = apply_motion_color_pipeline_premultiplied_rgba(
                rgba,
                color,
            )
            if not _qimage_from_premultiplied_rgba(rgba).save(str(path), "PNG"):
                raise RuntimeError(f"Failed to save Motion PNG sequence frame: {path}")
            if not self._is_valid_png(path):
                raise RuntimeError(f"Motion PNG sequence frame is invalid: {path}")
            frames.append(path)
            rendered_count += 1
        result = self._finish_result(report, output, len(frames), [str(path) for path in frames])
        result.update({
            "resume_requested": bool(resume),
            "rendered_frame_count": rendered_count,
            "resumed_frame_count": resumed_count,
            "sequence_complete": len(frames) == int(report["frame_count"]),
        })
        manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["manifest_path"] = str(manifest_path)
        return result

    @staticmethod
    def _is_valid_png(path: str | Path) -> bool:
        candidate = Path(path)
        if not candidate.is_file() or candidate.stat().st_size <= 8:
            return False
        image = QImage(str(candidate))
        return not image.isNull() and image.width() > 0 and image.height() > 0

    def _export_still(self, composition: MotionComposition, profile_id: str, output: Path,
                      time_ms: float, report: dict[str, Any]) -> dict[str, Any]:
        output.parent.mkdir(parents=True, exist_ok=True)
        color = settings_from_composition_metadata(composition.metadata)
        rgba = self.renderer.render_rgba_array(composition, time_ms)
        rgba, _color_report = apply_motion_color_pipeline_premultiplied_rgba(
            rgba,
            color,
        )
        if profile_id in {"png_still", "webp_still"}:
            image = _qimage_from_premultiplied_rgba(rgba)
        else:
            black = np.zeros(rgba.shape[:2] + (3,), dtype=np.uint8)
            image = _qimage_from_rgb(composite_premultiplied_srgb_over_srgb(black, rgba))
        image_format = {"png_still": "PNG", "jpeg_still": "JPEG", "webp_still": "WEBP"}[profile_id]
        if not image.save(str(output), image_format):
            raise RuntimeError(f"Failed to save Motion still: {output}")
        return self._finish_result(report, output, 1, [str(output)])

    def _export_ffmpeg(self, composition: MotionComposition, profile_id: str, output: Path,
                       report: dict[str, Any]) -> dict[str, Any]:
        profile = get_motion_export_profile(profile_id)
        ffmpeg = str(report["ffmpeg"]["path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        is_sequence = profile.kind == "sequence"
        if is_sequence:
            output.mkdir(parents=True, exist_ok=True)
            (output / "manifest.json").unlink(missing_ok=True)
            for stale in output.glob(f"frame_*{profile.extension}"):
                stale.unlink(missing_ok=True)
            target = output / f"frame_%06d{profile.extension}"
            command = self._ffmpeg_command(ffmpeg, composition, profile_id, target, report)
            final_target = target
        else:
            temporary = output.with_name(output.name + ".partial")
            temporary.unlink(missing_ok=True)
            command = self._ffmpeg_command(ffmpeg, composition, profile_id, temporary, report)
            final_target = temporary
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            **hidden_subprocess_kwargs(),
        )
        try:
            assert process.stdin is not None
            for index in range(int(report["frame_count"])):
                self._check_cancelled()
                time_ms = index * 1000.0 / float(report["fps"])
                rgba = self.renderer.render_rgba_array(composition, time_ms)
                if profile_id == "openexr_sequence":
                    payload = premultiplied_srgb_to_linear_gbrap_f32_bytes(rgba)
                else:
                    color = settings_from_composition_metadata(composition.metadata)
                    rgba, _color_report = apply_motion_color_pipeline_premultiplied_rgba(
                        rgba,
                        color,
                    )
                    if profile.alpha:
                        payload = premultiplied_srgb_to_straight_rgba_u8(rgba).tobytes()
                    else:
                        black = np.zeros(rgba.shape[:2] + (3,), dtype=np.uint8)
                        payload = composite_premultiplied_srgb_over_srgb(black, rgba).tobytes()
                process.stdin.write(payload)
            process.stdin.close()
            stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
            return_code = process.wait(timeout=max(30, int(report["frame_count"] * 2)))
        except Exception:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except OSError:
                    pass
            process.kill()
            process.wait(timeout=5)
            if not is_sequence:
                final_target.unlink(missing_ok=True)
            raise
        if return_code != 0:
            if not is_sequence:
                final_target.unlink(missing_ok=True)
            raise RuntimeError(f"Motion FFmpeg export failed ({return_code}): {stderr.strip()}")
        if not is_sequence:
            final_target.replace(output)
            paths = [str(output)]
        else:
            paths = [str(path) for path in sorted(output.glob(f"frame_*{profile.extension}"))]
        exported_frame_count = len(paths) if is_sequence else int(report["frame_count"])
        result = self._finish_result(report, output, exported_frame_count, paths)
        result["artifact_count"] = len(paths)
        if is_sequence:
            manifest_path = output / "manifest.json"
            manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            result["manifest_path"] = str(manifest_path)
        return result

    @staticmethod
    def _ffmpeg_command(ffmpeg: str, composition: MotionComposition, profile_id: str,
                        target: Path, report: dict[str, Any]) -> list[str]:
        profile = get_motion_export_profile(profile_id)
        input_pixel_format = "gbrapf32le" if profile_id == "openexr_sequence" else ("rgba" if profile.alpha else "rgb24")
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-pixel_format", input_pixel_format,
            "-video_size", f"{composition.width}x{composition.height}",
            "-framerate", f"{float(report['fps']):.8g}", "-i", "pipe:0", "-an",
        ]
        project_color = settings_from_composition_metadata(composition.metadata).project
        color_args = _without_pixel_format(ffmpeg_color_args(project_color))
        hdr_output = (
            project_color.output_space == "rec2020"
            and project_color.output_transfer in {"pq", "hlg"}
        )
        if profile_id == "h264_mp4":
            if hdr_output:
                raise ValueError("Motion HDR output requires the H.265 profile")
            command += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", *color_args,
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-f", "mp4"]
        elif profile_id == "h265_mp4":
            if hdr_output:
                transfer = (
                    "smpte2084"
                    if project_color.output_transfer == "pq"
                    else "arib-std-b67"
                )
                command += [
                    "-vf",
                    "zscale=pin=bt709:tin=bt709:min=bt709:"
                    f"p=bt2020:t={transfer}:m=bt2020nc,format=yuv420p10le",
                ]
            command += ["-c:v", "libx265", "-preset", "medium", "-crf", "20", "-tag:v", "hvc1",
                        *color_args, "-pix_fmt", "yuv420p10le" if hdr_output else "yuv420p",
                        "-movflags", "+faststart", "-f", "mp4"]
        elif profile_id == "prores_4444_mov":
            command += ["-c:v", "prores_ks", "-profile:v", "4", "-pix_fmt", "yuva444p10le",
                        "-bits_per_mb", "8000", *color_args, "-f", "mov"]
        elif profile_id == "openexr_sequence":
            command += ["-c:v", "exr", "-compression", "zip16", "-format", "half", "-gamma", "1",
                        "-pix_fmt", "gbrapf32le", "-start_number", "0", "-f", "image2"]
        else:
            raise ValueError(f"Unsupported FFmpeg Motion profile: {profile_id}")
        command.append(str(target))
        return command

    @staticmethod
    def _finish_result(report: dict[str, Any], output: Path, frame_count: int,
                       paths: list[str]) -> dict[str, Any]:
        return {
            "ok": True,
            "profile": report["profile"],
            "output_path": str(output),
            "frame_count": int(frame_count),
            "paths": paths,
            "alpha_contract": report["alpha_contract"],
            "color": report["color"],
            "warnings": report["warnings"],
        }


class MotionExportCancelled(RuntimeError):
    pass


__all__ = ["MotionExportCancelled", "MotionProfileExporter"]
