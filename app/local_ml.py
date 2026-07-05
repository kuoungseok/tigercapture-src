"""Local-first ML helpers for creator workflows.

This module intentionally avoids cloud calls and automatic model downloads.
Heavy backends such as Whisper, SAM, Demucs, ONNX Runtime, or YOLO are detected
as optional local capabilities.  The always-available path is lightweight visual
analysis with OpenCV when installed, with a Pillow/numpy image fallback.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from app.subprocess_utils import hidden_subprocess_kwargs


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

LOCAL_ML_ENABLED_ENV = "TIGERCAPTURE_LOCAL_ML_ENABLED"
LOCAL_ML_DISABLED_ENV = "TIGERCAPTURE_LOCAL_ML_DISABLED"


def _truthy_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _falsey_env(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"0", "false", "no", "off", "disabled"}


def local_ml_temporarily_disabled() -> bool:
    """Global safety gate for optional local ML features.

    Local ML is enabled by default and remains local-only: no cloud calls and
    no automatic model downloads. Set ``TIGERCAPTURE_LOCAL_ML_DISABLED=1`` to
    turn it off for diagnostics.
    """
    enabled = os.environ.get(LOCAL_ML_ENABLED_ENV)
    if _truthy_env(enabled):
        return False
    if enabled is not None and _falsey_env(enabled):
        return True
    disabled = os.environ.get(LOCAL_ML_DISABLED_ENV)
    if disabled is not None:
        return not _falsey_env(disabled)
    try:
        from app.capcut_features import capcut_feature_enabled

        if capcut_feature_enabled("local_ml"):
            return False
    except Exception:
        pass
    return False


def _sealed_capabilities() -> dict[str, Any]:
    note = "Disabled by local feature gate; clear TIGERCAPTURE_LOCAL_ML_DISABLED or set TIGERCAPTURE_LOCAL_ML_ENABLED=1."
    return {
        "opencv_visual": {"available": False, "kind": "visual_detection", "note": note},
        "pillow_image_fallback": {"available": False, "kind": "visual_detection", "note": note},
        "whisper_transcription": {
            "available": False,
            "backend": "disabled",
            "model_path": "",
            "requires_local_model": False,
            "note": note,
        },
        "sam_segmentation": {"available": False, "kind": "object_segmentation", "note": note},
        "demucs_stem_separation": {"available": False, "method": "disabled", "note": note},
        "onnxruntime": {"available": False, "kind": "future_detector_runtime", "note": note},
        "ultralytics_yolo": {"available": False, "kind": "future_object_detector", "note": note},
    }


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _media_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in VIDEO_EXTS:
        return "video"
    if suffix in AUDIO_EXTS:
        return "audio"
    return "media"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _candidate_whisper_model_paths(model_size: str = "small") -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get("TIGERCAPTURE_LOCAL_WHISPER_MODEL", "").strip()
    if env:
        candidates.append(Path(env))
    try:
        from app.transcription_settings import local_whisper_model_candidates

        candidates.extend(local_whisper_model_candidates(model_size))
    except Exception:
        pass
    env_dir = os.environ.get("TIGERCAPTURE_LOCAL_MODEL_DIR", "").strip()
    if env_dir:
        base = Path(env_dir) / "whisper"
        candidates.extend([base / model_size, base / f"{model_size}.pt", base / f"{model_size}.bin"])
    base = Path.cwd() / "models" / "whisper"
    candidates.extend([base / model_size, base / f"{model_size}.pt", base / f"{model_size}.bin"])
    return candidates


def _first_existing_path(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        try:
            if path.exists():
                return path
        except Exception:
            continue
    return None


def local_ml_backend_status() -> dict[str, Any]:
    """Return local ML capability status without loading heavyweight models."""
    if local_ml_temporarily_disabled():
        return {
            "ok": True,
            "mode": "disabled",
            "disabled": True,
            "reason": "feature_gate_disabled",
            "cloud_enabled": False,
            "api_required": False,
            "local_visual_available": False,
            "capabilities": _sealed_capabilities(),
            "recommended_order": [],
            "actions": ["Clear TIGERCAPTURE_LOCAL_ML_DISABLED or set TIGERCAPTURE_LOCAL_ML_ENABLED=1 to enable local ML paths."],
        }

    whisper_backend = ""
    if _module_available("faster_whisper"):
        whisper_backend = "faster-whisper"
    elif _module_available("whisper"):
        whisper_backend = "openai-whisper"

    whisper_model = _first_existing_path(_candidate_whisper_model_paths())
    sam_available = False
    try:
        from app.sam_segment import is_sam_available

        sam_available = bool(is_sam_available())
    except Exception:
        sam_available = False
    try:
        from app.audio_separation import planned_separation_method

        separation_method = planned_separation_method(prefer_demucs=True)
    except Exception:
        separation_method = "unavailable"

    capabilities = {
        "opencv_visual": {
            "available": _module_available("cv2"),
            "kind": "visual_detection",
            "note": "Used for video frame sampling, foreground regions, and optional face probes.",
        },
        "pillow_image_fallback": {
            "available": _module_available("PIL"),
            "kind": "visual_detection",
            "note": "Used for image analysis when OpenCV is not available.",
        },
        "whisper_transcription": {
            "available": bool(whisper_backend and whisper_model),
            "backend": whisper_backend or "missing",
            "model_path": str(whisper_model) if whisper_model else "",
            "requires_local_model": whisper_model is None,
            "note": "No model download is attempted by the local backend.",
        },
        "sam_segmentation": {
            "available": sam_available,
            "kind": "object_segmentation",
            "note": "Requires segment_anything plus a local SAM checkpoint.",
        },
        "demucs_stem_separation": {
            "available": separation_method == "Demucs",
            "method": separation_method,
            "note": "Falls back to FFmpeg mid/side in the Sound Editor when Demucs is absent.",
        },
        "onnxruntime": {
            "available": _module_available("onnxruntime"),
            "kind": "future_detector_runtime",
        },
        "ultralytics_yolo": {
            "available": _module_available("ultralytics"),
            "kind": "future_object_detector",
        },
    }
    local_visual = bool(capabilities["opencv_visual"]["available"] or capabilities["pillow_image_fallback"]["available"])
    return {
        "ok": True,
        "mode": "local",
        "cloud_enabled": False,
        "api_required": False,
        "local_visual_available": local_visual,
        "capabilities": capabilities,
        "recommended_order": [
            "opencv_visual",
            "sam_segmentation",
            "whisper_transcription",
            "demucs_stem_separation",
            "onnxruntime",
            "ultralytics_yolo",
        ],
    }


def _read_image_rgb(path: Path) -> np.ndarray | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return np.asarray(image.convert("RGB"))
    except Exception:
        pass
    try:
        import cv2

        bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if bgr is None:
            return None
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    except Exception:
        return None


def _bbox_row(label: str, bbox: tuple[int, int, int, int], width: int, height: int, *, t_ms: int, frame_index: int, confidence: float, source: str) -> dict[str, Any]:
    x, y, w, h = bbox
    cx = (x + w * 0.5) / max(1, width)
    cy = (y + h * 0.5) / max(1, height)
    return {
        "label": label,
        "t_ms": int(t_ms),
        "frame_index": int(frame_index),
        "x_norm": round(_clamp01(cx), 4),
        "y_norm": round(_clamp01(cy), 4),
        "bbox_norm": [
            round(_clamp01(x / max(1, width)), 4),
            round(_clamp01(y / max(1, height)), 4),
            round(_clamp01(w / max(1, width)), 4),
            round(_clamp01(h / max(1, height)), 4),
        ],
        "confidence": round(_clamp01(confidence), 4),
        "source": source,
    }


def _foreground_regions(rgb: np.ndarray, *, t_ms: int, frame_index: int, max_regions: int = 3) -> list[dict[str, Any]]:
    if rgb is None or rgb.ndim != 3 or rgb.shape[0] < 4 or rgb.shape[1] < 4:
        return []
    height, width = rgb.shape[:2]
    arr = rgb.astype(np.float32)
    border = np.concatenate(
        [
            arr[: max(1, height // 16), :, :].reshape(-1, 3),
            arr[-max(1, height // 16) :, :, :].reshape(-1, 3),
            arr[:, : max(1, width // 16), :].reshape(-1, 3),
            arr[:, -max(1, width // 16) :, :].reshape(-1, 3),
        ],
        axis=0,
    )
    if len(border) > 6000:
        border = border[:: max(1, len(border) // 6000)]
    bg = np.median(border, axis=0)
    distance = np.linalg.norm(arr - bg.reshape(1, 1, 3), axis=2)
    threshold = max(18.0, min(82.0, float(np.percentile(distance, 76)) * 0.72))
    mask = distance > threshold
    ratio = float(mask.mean())
    if ratio < 0.004 or ratio > 0.92:
        gray = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114)
        lo = float(np.percentile(gray, 12))
        hi = float(np.percentile(gray, 88))
        if hi - lo > 18:
            mask = (gray > lo + (hi - lo) * 0.48)
            ratio = float(mask.mean())
    if ratio < 0.004 or ratio > 0.96:
        return []

    try:
        import cv2

        mask8 = np.where(mask, 255, 0).astype(np.uint8)
        k = max(3, int(round(min(width, height) / 96)))
        if k % 2 == 0:
            k += 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        mask8 = cv2.morphologyEx(mask8, cv2.MORPH_OPEN, kernel)
        mask8 = cv2.morphologyEx(mask8, cv2.MORPH_CLOSE, kernel)
        contours, _hierarchy = cv2.findContours(mask8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rows: list[tuple[float, dict[str, Any]]] = []
        min_area = max(16.0, width * height * 0.006)
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            bbox_area_ratio = (w * h) / max(1.0, width * height)
            confidence = min(0.95, 0.32 + bbox_area_ratio * 2.3 + min(0.22, area / max(1.0, width * height)))
            rows.append(
                (
                    area,
                    _bbox_row(
                        "foreground_region",
                        (x, y, w, h),
                        width,
                        height,
                        t_ms=t_ms,
                        frame_index=frame_index,
                        confidence=confidence,
                        source="opencv_foreground",
                    ),
                )
            )
        return [row for _area, row in sorted(rows, key=lambda item: item[0], reverse=True)[:max_regions]]
    except Exception:
        ys, xs = np.where(mask)
        if len(xs) == 0 or len(ys) == 0:
            return []
        x0, x1 = int(xs.min()), int(xs.max())
        y0, y1 = int(ys.min()), int(ys.max())
        area_ratio = ((x1 - x0 + 1) * (y1 - y0 + 1)) / max(1.0, width * height)
        return [
            _bbox_row(
                "foreground_region",
                (x0, y0, x1 - x0 + 1, y1 - y0 + 1),
                width,
                height,
                t_ms=t_ms,
                frame_index=frame_index,
                confidence=min(0.9, 0.28 + area_ratio * 2.2),
                source="numpy_foreground",
            )
        ]


def _face_regions(rgb: np.ndarray, *, t_ms: int, frame_index: int, max_regions: int = 3) -> list[dict[str, Any]]:
    try:
        import cv2

        height, width = rgb.shape[:2]
        cascade_path = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(str(cascade_path))
        if cascade.empty():
            return []
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        min_side = max(24, min(width, height) // 12)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(min_side, min_side))
        rows = []
        for x, y, w, h in list(faces)[:max_regions]:
            rows.append(
                _bbox_row(
                    "face",
                    (int(x), int(y), int(w), int(h)),
                    width,
                    height,
                    t_ms=t_ms,
                    frame_index=frame_index,
                    confidence=0.72,
                    source="opencv_haar",
                )
            )
        return rows
    except Exception:
        return []


def _gray_hist(rgb: np.ndarray) -> np.ndarray:
    arr = rgb.astype(np.float32)
    gray = (arr[:, :, 0] * 0.299 + arr[:, :, 1] * 0.587 + arr[:, :, 2] * 0.114).astype(np.uint8)
    hist, _bins = np.histogram(gray, bins=24, range=(0, 255), density=False)
    hist = hist.astype(np.float32)
    total = float(hist.sum()) or 1.0
    return hist / total


def _video_frames(path: Path, sample_count: int) -> tuple[list[tuple[np.ndarray, int, int]], dict[str, Any]]:
    try:
        import cv2
    except Exception:
        return [], {"available": False, "reason": "opencv_missing"}
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return [], {"available": False, "reason": "open_failed"}
    try:
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duration_s = frame_count / fps if frame_count > 0 and fps > 0 else 0.0
        count = max(1, min(32, int(sample_count or 8)))
        if frame_count > 1:
            targets = sorted(set(int(round(v)) for v in np.linspace(0, max(0, frame_count - 1), count)))
        else:
            targets = list(range(count))
        frames: list[tuple[np.ndarray, int, int]] = []
        for idx in targets:
            if frame_count > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, bgr = cap.read()
            if not ok or bgr is None:
                continue
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            t_ms = int(round((idx / fps) * 1000)) if fps > 0 else int(cap.get(cv2.CAP_PROP_POS_MSEC) or 0)
            frames.append((rgb, t_ms, idx))
        return frames, {
            "available": True,
            "frame_count": frame_count,
            "fps": fps,
            "width": width,
            "height": height,
            "duration_s": duration_s,
        }
    finally:
        try:
            cap.release()
        except Exception:
            pass


def _scene_ranges(frames: list[tuple[np.ndarray, int, int]], duration_s: float) -> list[dict[str, Any]]:
    if not frames:
        return []
    ranges: list[dict[str, Any]] = []
    last_ms = 0
    prev_hist: np.ndarray | None = None
    cuts: list[tuple[int, float]] = []
    for rgb, t_ms, _idx in frames:
        hist = _gray_hist(rgb)
        if prev_hist is not None:
            diff = float(np.abs(hist - prev_hist).sum()) * 0.5
            if diff >= 0.34:
                cuts.append((int(t_ms), min(1.0, diff)))
        prev_hist = hist
    for cut_ms, confidence in cuts[:12]:
        if cut_ms - last_ms < 500:
            continue
        ranges.append({"start_ms": last_ms, "end_ms": cut_ms, "reason": "visual_change", "confidence": round(confidence, 3)})
        last_ms = cut_ms
    end_ms = int(round(max(0.0, duration_s) * 1000))
    if end_ms <= 0 and frames:
        end_ms = max(t for _rgb, t, _idx in frames) + 1000
    ranges.append({"start_ms": last_ms, "end_ms": max(last_ms + 1000, end_ms), "reason": "tail", "confidence": 0.5})
    return ranges


def _video_visual_analysis(path: Path, sample_count: int) -> dict[str, Any]:
    frames, meta = _video_frames(path, sample_count)
    detections: list[dict[str, Any]] = []
    tags: set[str] = {"video"}
    for rgb, t_ms, frame_index in frames:
        frame_rows = _foreground_regions(rgb, t_ms=t_ms, frame_index=frame_index, max_regions=1)
        frame_rows.extend(_face_regions(rgb, t_ms=t_ms, frame_index=frame_index, max_regions=1))
        detections.extend(frame_rows)
        for row in frame_rows:
            label = str(row.get("label") or "")
            if label:
                tags.add(label)
    return {
        "ok": bool(frames),
        "metadata": meta,
        "sampled_frames": len(frames),
        "subject_detections": detections,
        "object_tags": sorted(tags),
        "scene_ranges": _scene_ranges(frames, float(meta.get("duration_s", 0.0) or 0.0)),
    }


def _image_visual_analysis(path: Path) -> dict[str, Any]:
    rgb = _read_image_rgb(path)
    if rgb is None:
        return {
            "ok": False,
            "metadata": {"available": False, "reason": "image_read_failed"},
            "sampled_frames": 0,
            "subject_detections": [],
            "object_tags": ["image"],
            "scene_ranges": [],
        }
    height, width = rgb.shape[:2]
    detections = _foreground_regions(rgb, t_ms=0, frame_index=0, max_regions=3)
    detections.extend(_face_regions(rgb, t_ms=0, frame_index=0, max_regions=2))
    tags = {"image"}
    for row in detections:
        label = str(row.get("label") or "")
        if label:
            tags.add(label)
    return {
        "ok": True,
        "metadata": {"available": True, "width": int(width), "height": int(height), "duration_s": 5.0},
        "sampled_frames": 1,
        "subject_detections": detections,
        "object_tags": sorted(tags),
        "scene_ranges": [{"start_ms": 0, "end_ms": 5000, "reason": "still_image", "confidence": 1.0}],
    }


def _ffmpeg_exe() -> str | None:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _audio_beat_analysis(path: Path, *, max_seconds: int = 180) -> dict[str, Any]:
    ffmpeg = _ffmpeg_exe()
    if not ffmpeg:
        return {"ok": False, "reason": "ffmpeg_unavailable", "beat_markers": []}
    with tempfile.TemporaryDirectory(prefix="tigercapture_local_ml_audio_") as tmp:
        wav_path = Path(tmp) / "analysis.wav"
        cmd = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-t",
            str(int(max_seconds)),
            str(wav_path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=45,
                check=False,
                **hidden_subprocess_kwargs(),
            )
        except Exception as exc:
            return {"ok": False, "reason": f"ffmpeg_failed: {exc}", "beat_markers": []}
        if proc.returncode != 0 or not wav_path.exists():
            return {"ok": False, "reason": "no_audio_or_decode_failed", "beat_markers": []}
        try:
            with wave.open(str(wav_path), "rb") as wf:
                rate = wf.getframerate()
                raw = wf.readframes(wf.getnframes())
            samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as exc:
            return {"ok": False, "reason": f"wav_read_failed: {exc}", "beat_markers": []}
    if samples.size < 1024:
        return {"ok": False, "reason": "too_short", "beat_markers": []}
    hop = max(512, int(rate * 0.20))
    env = []
    times = []
    for start in range(0, max(0, samples.size - hop), hop):
        chunk = samples[start : start + hop]
        env.append(float(np.sqrt(np.mean(chunk * chunk))))
        times.append(start / max(1, rate))
    if not env:
        return {"ok": False, "reason": "empty_envelope", "beat_markers": []}
    arr = np.asarray(env, dtype=np.float32)
    threshold = float(np.percentile(arr, 82))
    markers: list[dict[str, Any]] = []
    last_t = -999.0
    for idx in range(1, len(arr) - 1):
        if arr[idx] >= threshold and arr[idx] >= arr[idx - 1] and arr[idx] >= arr[idx + 1]:
            t = times[idx]
            if t - last_t >= 0.55:
                markers.append({"t_ms": int(round(t * 1000)), "strength": round(min(1.0, float(arr[idx] / (threshold or 1.0))), 3)})
                last_t = t
        if len(markers) >= 80:
            break
    return {"ok": True, "sample_rate": rate, "beat_markers": markers, "marker_count": len(markers)}


def local_ml_transcribe_media(
    media_path: str | Path,
    *,
    language: str = "",
    model_size: str = "small",
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Transcribe media only when a local Whisper model path is present."""
    path = Path(media_path)
    if local_ml_temporarily_disabled():
        return {
            "ok": False,
            "available": False,
            "segments": [],
            "backend": "disabled",
            "reason": "local_ml_temporarily_sealed",
        }
    if not path.exists():
        return {"ok": False, "available": False, "segments": [], "reason": "missing_media"}
    model_path = _first_existing_path(_candidate_whisper_model_paths(model_size))
    if model_path is None:
        return {
            "ok": False,
            "available": False,
            "segments": [],
            "backend": "none",
            "reason": "local_whisper_model_missing",
            "actions": [
                "Run tools/configure_local_whisper_model.py --model-path <local faster-whisper model directory>.",
                "Existing Systran faster-whisper models in the local Hugging Face cache are detected automatically.",
                "No network download or cloud transcription is attempted by this backend.",
            ],
        }
    if not _module_available("faster_whisper"):
        return {
            "ok": False,
            "available": False,
            "segments": [],
            "backend": "missing",
            "reason": "faster_whisper_missing",
            "actions": ["Install faster-whisper in the local Python environment."],
        }
    code = (
        "import json, sys\n"
        "from faster_whisper import WhisperModel\n"
        "model_path, media_path, language = sys.argv[1], sys.argv[2], sys.argv[3]\n"
        "model = WhisperModel(model_path, device='cpu', compute_type='int8', local_files_only=True)\n"
        "segments, info = model.transcribe(media_path, language=(language or None), vad_filter=True, word_timestamps=True)\n"
        "rows = []\n"
        "for seg in segments:\n"
        "    words = []\n"
        "    for word in (getattr(seg, 'words', None) or []):\n"
        "        raw = str(getattr(word, 'word', '') or '').strip()\n"
        "        if not raw:\n"
        "            continue\n"
        "        item = {'text': raw, 'start_ms': int(round(float(getattr(word, 'start', seg.start)) * 1000)), 'end_ms': int(round(float(getattr(word, 'end', seg.end)) * 1000))}\n"
        "        probability = getattr(word, 'probability', None)\n"
        "        if probability is not None:\n"
        "            item['confidence'] = float(probability)\n"
        "        words.append(item)\n"
        "    rows.append({'start_ms': int(round(seg.start * 1000)), 'end_ms': int(round(seg.end * 1000)), 'text': seg.text.strip(), 'words': words})\n"
        "print(json.dumps({'ok': True, 'language': getattr(info, 'language', ''), 'segments': rows}, ensure_ascii=False))\n"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, str(model_path), str(path), language],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(30, int(timeout_s)),
            check=False,
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return {"ok": False, "available": True, "segments": [], "backend": "faster-whisper", "reason": str(exc)}
    if proc.returncode != 0:
        return {
            "ok": False,
            "available": True,
            "segments": [],
            "backend": "faster-whisper",
            "reason": "transcribe_failed",
            "stderr_tail": proc.stderr[-1200:],
        }
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception as exc:
        return {"ok": False, "available": True, "segments": [], "backend": "faster-whisper", "reason": f"bad_output: {exc}"}
    payload["available"] = True
    payload["backend"] = "faster-whisper"
    payload["model_path"] = str(model_path)
    return payload


def local_ml_analyze_media(
    media_path: str | Path,
    *,
    transcribe: bool = False,
    visual: bool = True,
    audio_beats: bool = False,
    sample_count: int = 8,
) -> dict[str, Any]:
    """Analyze one media file with local-only backends."""
    path = Path(media_path)
    status = local_ml_backend_status()
    if local_ml_temporarily_disabled():
        kind = _media_kind(path)
        return {
            "ok": False,
            "mode": "disabled",
            "disabled": True,
            "cloud_enabled": False,
            "path": str(path),
            "name": path.name,
            "kind": kind,
            "duration_s": 5.0 if kind == "image" else 0.0,
            "metadata": {"available": False, "reason": "local_ml_temporarily_sealed"},
            "backend_status": status,
            "subject_detections": [],
            "object_tags": [kind],
            "scene_ranges": [],
            "sampled_frames": 0,
            "transcript_segments": [],
            "transcription": {
                "ok": False,
                "available": False,
                "segments": [],
                "backend": "disabled",
                "reason": "local_ml_temporarily_sealed",
            },
            "beat_markers": [],
            "audio_beats": {
                "ok": False,
                "beat_markers": [],
                "reason": "local_ml_temporarily_sealed",
            },
        }
    if not path.exists():
        return {
            "ok": False,
            "path": str(path),
            "kind": _media_kind(path),
            "backend_status": status,
            "error": "missing_media",
            "subject_detections": [],
            "object_tags": [],
            "scene_ranges": [],
            "transcript_segments": [],
            "beat_markers": [],
        }
    kind = _media_kind(path)
    visual_report = {
        "ok": False,
        "metadata": {"duration_s": 0.0},
        "subject_detections": [],
        "object_tags": [kind],
        "scene_ranges": [],
    }
    if visual and kind == "image":
        visual_report = _image_visual_analysis(path)
    elif visual and kind == "video":
        visual_report = _video_visual_analysis(path, sample_count)
    transcript = local_ml_transcribe_media(path) if transcribe and kind in {"video", "audio"} else {
        "ok": False,
        "available": False,
        "segments": [],
        "reason": "not_requested" if not transcribe else "unsupported_media_kind",
    }
    beats = _audio_beat_analysis(path) if audio_beats and kind in {"video", "audio"} else {
        "ok": False,
        "beat_markers": [],
        "reason": "not_requested" if not audio_beats else "unsupported_media_kind",
    }
    metadata = dict(visual_report.get("metadata") or {})
    duration_s = float(metadata.get("duration_s", 0.0) or 0.0)
    if kind == "image" and duration_s <= 0:
        duration_s = 5.0
    object_tags = sorted(set(str(tag) for tag in _as_list(visual_report.get("object_tags")) if tag))
    subject_detections = [dict(row) for row in _as_list(visual_report.get("subject_detections"))]
    scene_ranges = [dict(row) for row in _as_list(visual_report.get("scene_ranges"))]
    return {
        "ok": bool(visual_report.get("ok") or transcript.get("ok") or beats.get("ok")),
        "mode": "local",
        "cloud_enabled": False,
        "path": str(path),
        "name": path.name,
        "kind": kind,
        "duration_s": duration_s,
        "metadata": metadata,
        "backend_status": status,
        "subject_detections": subject_detections,
        "object_tags": object_tags,
        "scene_ranges": scene_ranges,
        "sampled_frames": int(visual_report.get("sampled_frames", 0) or 0),
        "transcript_segments": [dict(row) for row in _as_list(transcript.get("segments"))],
        "transcription": transcript,
        "beat_markers": [dict(row) for row in _as_list(beats.get("beat_markers"))],
        "audio_beats": beats,
    }


def local_ml_capcut_project_summary(
    media_path: str | Path,
    *,
    include_transcript: bool = False,
    sample_count: int = 8,
) -> dict[str, Any]:
    """Build a CapCut workflow summary from one local media file."""
    analysis = local_ml_analyze_media(
        media_path,
        transcribe=include_transcript,
        visual=True,
        audio_beats=False,
        sample_count=sample_count,
    )
    path = Path(media_path)
    kind = str(analysis.get("kind") or _media_kind(path))
    duration_s = float(analysis.get("duration_s", 0.0) or (5.0 if kind == "image" else 0.0))
    tags = [str(tag) for tag in _as_list(analysis.get("object_tags"))]
    transcript_segments = [dict(row) for row in _as_list(analysis.get("transcript_segments"))]
    dialogue = [str(row.get("text", "") or "") for row in transcript_segments if str(row.get("text", "") or "").strip()]
    lower_name = path.name.casefold()
    screen_recording = any(term in lower_name for term in ("screen", "capture", "record", "tutorial", "demo"))
    media_id = hashlib.sha1(str(path.resolve()).encode("utf-8", errors="ignore")).hexdigest()[:10]
    media_item = {
        "id": f"local-{media_id}",
        "name": path.name,
        "path": str(path),
        "kind": kind,
        "duration_s": duration_s,
        "object_tags": tags,
        "tags": ["local-ml", kind] + (["screen-recording"] if screen_recording else []),
        "dialogue": dialogue,
    }
    return {
        "source_path": str(path),
        "duration_s": duration_s,
        "video_count": 1 if kind in {"video", "image"} else 0,
        "audio_count": 1 if kind == "audio" else 0,
        "has_audio": kind in {"video", "audio"},
        "dialogue": bool(dialogue),
        "shortform": bool(duration_s and duration_s <= 90),
        "screen_recording": screen_recording,
        "media_items": [media_item],
        "subject_detections": [dict(row) for row in _as_list(analysis.get("subject_detections"))],
        "scene_ranges": [dict(row) for row in _as_list(analysis.get("scene_ranges"))],
        "transcript_segments": transcript_segments,
        "object_tags": tags,
        "local_ml_analysis": analysis,
        "local_ml_backend_status": analysis.get("backend_status") or local_ml_backend_status(),
    }
