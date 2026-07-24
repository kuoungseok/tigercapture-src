"""Local audio/video reference analysis for editable Motion choreography."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import AnimatedProperty, Keyframe, MotionLayer


REFERENCE_ANALYSIS_SCHEMA = "tigerstudio.motion.reference_analysis.v1"


def _reference_value(reference: Any, name: str, default: Any = None) -> Any:
    if isinstance(reference, Mapping):
        return reference.get(name, default)
    return getattr(reference, name, default)


def _source_signature(path: str | Path) -> tuple[str, int, int]:
    source = Path(path).expanduser().resolve()
    stat = source.stat()
    return str(source), int(stat.st_size), int(stat.st_mtime_ns)


@lru_cache(maxsize=64)
def _analyze_image_style_cached(
    source_path: str,
    source_size: int,
    source_mtime_ns: int,
) -> dict[str, Any]:
    del source_size, source_mtime_ns
    from PIL import Image, ImageStat

    with Image.open(source_path) as source:
        image = source.convert("RGB")
        image.thumbnail((160, 160), Image.Resampling.LANCZOS)
        quantized = image.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette() or []
        color_rows = sorted(
            quantized.getcolors(maxcolors=256) or [],
            reverse=True,
        )
        colors: list[str] = []
        for _count, index in color_rows[:6]:
            offset = int(index) * 3
            if offset + 2 >= len(palette):
                continue
            colors.append(
                f"#{palette[offset]:02x}{palette[offset + 1]:02x}"
                f"{palette[offset + 2]:02x}"
            )
        mean = [float(value) for value in ImageStat.Stat(image).mean[:3]]
        luminance = (
            mean[0] * 0.2126 + mean[1] * 0.7152 + mean[2] * 0.0722
        ) / 255.0
        return {
            "source_path": source_path,
            "provider": "pillow_palette",
            "palette": colors,
            "mean_rgb": mean,
            "luminance": max(0.0, min(1.0, luminance)),
            "orientation": (
                "portrait"
                if source.height > source.width
                else "landscape"
                if source.width > source.height
                else "square"
            ),
            "scope": "palette_and_tone_reference",
            "identity_transfer": False,
        }


@lru_cache(maxsize=48)
def _analyze_audio_cached(
    source_path: str,
    source_size: int,
    source_mtime_ns: int,
    duration_ms: int,
) -> dict[str, Any]:
    del source_size, source_mtime_ns
    from .audio_analysis import analyze_audio

    cache = analyze_audio(
        source_path,
        duration_ms=max(1, int(duration_ms)),
        hop_ms=24,
    )
    return {
        "source_path": source_path,
        "beat_markers_ms": [int(value) for value in cache.beat_markers],
        "estimated_bpm": float(cache.estimated_bpm),
        "duration_ms": int(cache.duration_ms),
        "provider": str(cache.metadata.get("decoder") or "wav_or_ffmpeg"),
    }


@lru_cache(maxsize=32)
def _analyze_video_cached(
    source_path: str,
    source_size: int,
    source_mtime_ns: int,
    duration_ms: int,
) -> dict[str, Any]:
    del source_size, source_mtime_ns
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(source_path)
    if not capture.isOpened():
        raise ValueError(f"video reference could not be opened: {source_path}")
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        source_duration_ms = (
            int(round(frame_count * 1000.0 / fps))
            if fps > 0.0 and frame_count > 0
            else max(1, int(duration_ms))
        )
        analysis_duration_ms = min(
            max(1, int(duration_ms)),
            max(1, source_duration_ms),
        )
        sample_count = max(8, min(40, int(round(analysis_duration_ms / 250.0))))
        sample_times = np.linspace(0, max(0, analysis_duration_ms - 1), sample_count)
        previous = None
        samples: list[dict[str, float]] = []
        cuts: list[int] = []
        for time_ms in sample_times:
            capture.set(cv2.CAP_PROP_POS_MSEC, float(time_ms))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            height, width = frame.shape[:2]
            target_width = min(320, max(64, width))
            target_height = max(36, int(round(height * target_width / max(1, width))))
            gray = cv2.cvtColor(
                cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA),
                cv2.COLOR_BGR2GRAY,
            )
            gray = gray.astype(np.float32) / 255.0
            if previous is not None:
                difference = float(np.mean(np.abs(gray - previous)))
                flow = cv2.calcOpticalFlowFarneback(
                    previous,
                    gray,
                    None,
                    0.5,
                    3,
                    15,
                    3,
                    5,
                    1.2,
                    0,
                )
                dx = float(np.median(flow[..., 0])) / max(1.0, float(target_width))
                dy = float(np.median(flow[..., 1])) / max(1.0, float(target_height))
                magnitude = float(np.percentile(np.linalg.norm(flow, axis=2), 70))
                samples.append({
                    "time_ratio": float(time_ms) / max(1.0, float(analysis_duration_ms)),
                    "dx": max(-0.08, min(0.08, dx)),
                    "dy": max(-0.08, min(0.08, dy)),
                    "intensity": max(0.0, min(1.0, magnitude / 8.0)),
                    "difference": max(0.0, min(1.0, difference)),
                })
                if difference >= 0.2:
                    cuts.append(int(round(float(time_ms))))
            previous = gray
        if not samples:
            samples = [{
                "time_ratio": 0.0,
                "dx": 0.0,
                "dy": 0.0,
                "intensity": 0.0,
                "difference": 0.0,
            }]
        return {
            "source_path": source_path,
            "provider": "opencv_farneback",
            "duration_ms": analysis_duration_ms,
            "source_duration_ms": source_duration_ms,
            "samples": samples,
            "cut_markers_ms": cuts,
            "mean_dx": float(np.mean([item["dx"] for item in samples])),
            "mean_dy": float(np.mean([item["dy"] for item in samples])),
            "mean_intensity": float(np.mean([item["intensity"] for item in samples])),
            "scope": "camera_and_layer_motion_reference",
            "pose_transfer": False,
        }
    finally:
        capture.release()


def analyze_motion_references(
    references: Iterable[Any],
    *,
    duration_ms: int,
) -> dict[str, Any]:
    audio_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    video_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for reference in references:
        kind = str(_reference_value(reference, "kind", "") or "").casefold()
        uri = str(_reference_value(reference, "uri", "") or "")
        if kind not in {"audio", "image", "video"} or not uri:
            continue
        try:
            signature = _source_signature(uri)
        except OSError as exc:
            warnings.append(f"Reference needs relink before analysis: {uri} ({exc})")
            continue
        if kind == "image":
            try:
                image_rows.append(_analyze_image_style_cached(*signature))
            except Exception as exc:
                warnings.append(f"Image style analysis failed for {uri}: {exc}")
            continue
        if kind == "audio":
            try:
                audio_rows.append(_analyze_audio_cached(
                    *signature,
                    max(1, int(duration_ms)),
                ))
            except Exception as exc:
                warnings.append(f"Audio reference analysis failed for {uri}: {exc}")
            continue
        try:
            video_rows.append(_analyze_video_cached(
                *signature,
                max(1, int(duration_ms)),
            ))
        except Exception as exc:
            warnings.append(f"Video motion analysis failed for {uri}: {exc}")
        try:
            audio_rows.append(_analyze_audio_cached(
                *signature,
                max(1, int(duration_ms)),
            ))
        except Exception:
            pass
    beat_markers = sorted({
        int(value)
        for row in audio_rows
        for value in row.get("beat_markers_ms", [])
        if 0 <= int(value) <= int(duration_ms)
    })
    cut_markers = sorted({
        int(value)
        for row in video_rows
        for value in row.get("cut_markers_ms", [])
        if 0 <= int(value) <= int(duration_ms)
    })
    return {
        "schema": REFERENCE_ANALYSIS_SCHEMA,
        "image_style": image_rows,
        "audio": audio_rows,
        "video": video_rows,
        "beat_markers_ms": beat_markers,
        "cut_markers_ms": cut_markers,
        "timing_markers_ms": sorted(set(beat_markers + cut_markers)),
        "warnings": warnings,
    }


def apply_video_motion_reference(
    layers: Iterable[MotionLayer],
    video_analysis: Mapping[str, Any] | None,
) -> int:
    """Transfer restrained video camera motion to editable image source curves."""
    if not isinstance(video_analysis, Mapping):
        return 0
    samples = [
        item
        for item in video_analysis.get("samples", [])
        if isinstance(item, Mapping)
    ]
    if not samples:
        return 0
    changed = 0
    for layer in layers:
        if layer.layer_type != "image":
            continue
        decomposition = layer.metadata.get("image_decomposition")
        if isinstance(decomposition, Mapping) and decomposition.get("role") == "background":
            continue
        duration_ms = max(1, int(layer.out_ms) - int(layer.in_ms))
        values_by_time: dict[int, tuple[float, float, float]] = {}
        for sample in samples[:12]:
            ratio = max(0.0, min(1.0, float(sample.get("time_ratio", 0.0) or 0.0)))
            time_ms = min(duration_ms - 1, max(0, int(round(ratio * duration_ms))))
            dx = float(sample.get("dx", 0.0) or 0.0)
            dy = float(sample.get("dy", 0.0) or 0.0)
            intensity = max(0.0, min(1.0, float(sample.get("intensity", 0.0) or 0.0)))
            values_by_time[time_ms] = (
                max(-8.0, min(8.0, -dy * 180.0)),
                max(-8.0, min(8.0, dx * 180.0)),
                2.6 + intensity * 0.45,
            )
        keyframes_x = [
            Keyframe(time_ms=time_ms, value=values[0], interpolation="bezier")
            for time_ms, values in sorted(values_by_time.items())
        ]
        keyframes_y = [
            Keyframe(time_ms=time_ms, value=values[1], interpolation="bezier")
            for time_ms, values in sorted(values_by_time.items())
        ]
        keyframes_perspective = [
            Keyframe(time_ms=time_ms, value=values[2], interpolation="bezier")
            for time_ms, values in sorted(values_by_time.items())
        ]
        layer.source.params["tilt_x"] = AnimatedProperty(
            default=0.0,
            keyframes=keyframes_x,
            metadata={"motion_reference": "video"},
        ).to_dict()
        layer.source.params["tilt_y"] = AnimatedProperty(
            default=0.0,
            keyframes=keyframes_y,
            metadata={"motion_reference": "video"},
        ).to_dict()
        layer.source.params["perspective"] = AnimatedProperty(
            default=2.6,
            keyframes=keyframes_perspective,
            metadata={"motion_reference": "video"},
        ).to_dict()
        layer.metadata["motion_reference"] = {
            "provider": str(video_analysis.get("provider") or ""),
            "source_path": str(video_analysis.get("source_path") or ""),
            "scope": str(video_analysis.get("scope") or ""),
            "pose_transfer": False,
        }
        changed += 1
    return changed


__all__ = [
    "REFERENCE_ANALYSIS_SCHEMA",
    "analyze_motion_references",
    "apply_video_motion_reference",
]
