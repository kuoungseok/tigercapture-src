"""Face-video to VTuber motion extraction.

This module deliberately keeps the first implementation lightweight: OpenCV is
loaded lazily, and the public math helpers are pure so the bridge can be tested
without a camera or a live VSeeFace process.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
from pathlib import Path
from typing import Any


VIDEO_FACE_DRIVER_SCHEMA = "tigerstudio.vtuber.video_face_driver.v1"
DEFAULT_FACE_LANDMARKER_MODEL_NAMES = (
    "face_landmarker.task",
    "face_landmarker_v2_with_blendshapes.task",
)


@dataclass(frozen=True)
class FaceMotionFrame:
    time_ms: int = 0
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0
    shoulder_roll_deg: float = 0.0
    mouth_open: float = 0.0
    blink_l: float = 0.0
    blink_r: float = 0.0
    confidence: float = 0.0
    face_box: tuple[int, int, int, int] | None = None
    chin_offset_x_norm: float = 0.0
    source: str = "idle"

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_ms": int(self.time_ms),
            "yaw_deg": float(self.yaw_deg),
            "pitch_deg": float(self.pitch_deg),
            "roll_deg": float(self.roll_deg),
            "shoulder_roll_deg": float(self.shoulder_roll_deg),
            "mouth_open": float(self.mouth_open),
            "blink_l": float(self.blink_l),
            "blink_r": float(self.blink_r),
            "confidence": float(self.confidence),
            "face_box": list(self.face_box) if self.face_box else None,
            "chin_offset_x_norm": float(self.chin_offset_x_norm),
            "source": self.source,
        }


@dataclass(frozen=True)
class FaceMotionTuning:
    yaw_scale: float = 1.0
    pitch_scale: float = 1.0
    roll_scale: float = 1.0
    shoulder_roll_scale: float = 1.0
    mouth_scale: float = 1.0
    blink_scale: float = 1.0
    smoothing: float = 0.35
    calibrate_ms: int = 800
    calibrate_mouth: bool = False
    calibrate_blinks: bool = False
    mouth_deadzone: float = 0.0
    blink_deadzone: float = 0.03

    def to_dict(self) -> dict[str, Any]:
        return {
            "yaw_scale": float(self.yaw_scale),
            "pitch_scale": float(self.pitch_scale),
            "roll_scale": float(self.roll_scale),
            "shoulder_roll_scale": float(self.shoulder_roll_scale),
            "mouth_scale": float(self.mouth_scale),
            "blink_scale": float(self.blink_scale),
            "smoothing": float(self.smoothing),
            "calibrate_ms": int(self.calibrate_ms),
            "calibrate_mouth": bool(self.calibrate_mouth),
            "calibrate_blinks": bool(self.calibrate_blinks),
            "mouth_deadzone": float(self.mouth_deadzone),
            "blink_deadzone": float(self.blink_deadzone),
        }


@dataclass(frozen=True)
class VideoFaceMotionResult:
    ok: bool
    frames: tuple[FaceMotionFrame, ...]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": VIDEO_FACE_DRIVER_SCHEMA,
            "ok": bool(self.ok),
            "frame_count": len(self.frames),
            "frames": [frame.to_dict() for frame in self.frames],
            "diagnostics": dict(self.diagnostics),
        }


def motion_from_face_box(
    frame_size: tuple[int, int],
    face_box: tuple[int, int, int, int] | None,
    *,
    time_ms: int = 0,
    lower_motion: float = 0.0,
    eye_count: int = 2,
    roll_deg: float = 0.0,
    source: str = "face_box",
) -> FaceMotionFrame:
    """Estimate coarse head/expression motion from a detected face rectangle."""
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    if not face_box:
        return idle_motion_frame(time_ms)

    x, y, w, h = [int(v) for v in face_box]
    cx = x + w * 0.5
    cy = y + h * 0.5
    nx = (cx - width * 0.5) / max(1.0, width * 0.5)
    ny = (cy - height * 0.5) / max(1.0, height * 0.5)

    yaw = _clamp(nx * 30.0, -30.0, 30.0)
    pitch = _clamp(-ny * 18.0, -22.0, 22.0)
    mouth_open = _clamp01(lower_motion)
    blink = _blink_from_eye_count(eye_count)
    confidence = _clamp01(0.62 + min(0.2, (w * h) / max(1.0, width * height)))
    return FaceMotionFrame(
        time_ms=int(time_ms),
        yaw_deg=yaw,
        pitch_deg=pitch,
        roll_deg=_clamp(float(roll_deg), -25.0, 25.0),
        mouth_open=mouth_open,
        blink_l=blink,
        blink_r=blink,
        confidence=confidence,
        face_box=(x, y, w, h),
        source=source,
    )


def motion_from_face_landmarks(
    frame_size: tuple[int, int],
    landmarks: Any,
    *,
    time_ms: int = 0,
) -> FaceMotionFrame:
    """Estimate VTuber motion from MediaPipe FaceMesh-style landmarks."""
    points = _landmark_points(landmarks)
    if len(points) < 455:
        return idle_motion_frame(time_ms)

    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = max(0.0, min(xs)), min(1.0, max(xs))
    min_y, max_y = max(0.0, min(ys)), min(1.0, max(ys))
    face_w = max(0.001, max_x - min_x)
    face_h = max(0.001, max_y - min_y)
    face_cx = (min_x + max_x) * 0.5
    face_cy = (min_y + max_y) * 0.5

    nose = points[1]
    left_eye = points[33]
    right_eye = points[263]
    roll = math.degrees(math.atan2(right_eye[1] - left_eye[1], max(0.0001, right_eye[0] - left_eye[0])))
    yaw = _clamp(((nose[0] - face_cx) / face_w) * 42.0, -38.0, 38.0)
    pitch = _clamp(-((nose[1] - face_cy) / face_h) * 24.0, -28.0, 28.0)

    mouth_open = _clamp01((abs(points[14][1] - points[13][1]) / face_h - 0.012) * 14.0)
    left_open = abs(points[159][1] - points[145][1]) / face_h
    right_open = abs(points[386][1] - points[374][1]) / face_h
    blink_l = _clamp01((0.030 - left_open) / 0.020)
    blink_r = _clamp01((0.030 - right_open) / 0.020)
    face_box = (
        int(round(min_x * width)),
        int(round(min_y * height)),
        max(1, int(round(face_w * width))),
        max(1, int(round(face_h * height))),
    )
    return FaceMotionFrame(
        time_ms=int(time_ms),
        yaw_deg=yaw,
        pitch_deg=pitch,
        roll_deg=_clamp(roll, -25.0, 25.0),
        mouth_open=mouth_open,
        blink_l=blink_l,
        blink_r=blink_r,
        confidence=0.92,
        face_box=face_box,
        source="mediapipe_face_mesh",
    )


def motion_from_mediapipe_tasks_result(
    frame_size: tuple[int, int],
    result: Any,
    *,
    time_ms: int = 0,
) -> FaceMotionFrame | None:
    """Estimate VTuber motion from a MediaPipe Tasks FaceLandmarkerResult."""
    faces = getattr(result, "face_landmarks", None) or []
    if not faces:
        return None
    frame = motion_from_face_landmarks(frame_size, faces[0], time_ms=time_ms)
    blendshape_groups = getattr(result, "face_blendshapes", None) or []
    if blendshape_groups:
        values = _blendshape_scores(blendshape_groups[0])
        mouth_open = max(
            values.get("jawOpen", 0.0),
            values.get("mouthOpen", 0.0),
            values.get("mouthFunnel", 0.0) * 0.35,
        )
        blink_l = values.get("eyeBlinkLeft", frame.blink_l)
        blink_r = values.get("eyeBlinkRight", frame.blink_r)
        frame = replace(
            frame,
            mouth_open=_clamp01(mouth_open),
            blink_l=_clamp01(blink_l),
            blink_r=_clamp01(blink_r),
            source="mediapipe_tasks_face_landmarker",
            confidence=max(frame.confidence, 0.95),
        )
    else:
        frame = replace(frame, source="mediapipe_tasks_face_landmarker")
    return frame


def apply_motion_tuning(frames: tuple[FaceMotionFrame, ...] | list[FaceMotionFrame], tuning: FaceMotionTuning | None = None) -> tuple[FaceMotionFrame, ...]:
    """Apply neutral calibration, sensitivity scales, and exponential smoothing."""
    data = tuple(frames)
    if not data:
        return ()
    cfg = tuning or FaceMotionTuning()
    calibration = [frame for frame in data if frame.time_ms <= int(cfg.calibrate_ms)]
    if not calibration:
        calibration = [data[0]]
    base_yaw = sum(frame.yaw_deg for frame in calibration) / len(calibration)
    base_pitch = sum(frame.pitch_deg for frame in calibration) / len(calibration)
    base_roll = sum(frame.roll_deg for frame in calibration) / len(calibration)
    base_shoulder_roll = sum(frame.shoulder_roll_deg for frame in calibration) / len(calibration)
    base_mouth = sum(frame.mouth_open for frame in calibration) / len(calibration)
    base_blink_l = sum(frame.blink_l for frame in calibration) / len(calibration)
    base_blink_r = sum(frame.blink_r for frame in calibration) / len(calibration)
    alpha = _clamp(float(cfg.smoothing), 0.0, 0.95)
    previous: FaceMotionFrame | None = None
    tuned: list[FaceMotionFrame] = []
    for frame in data:
        mouth_open = frame.mouth_open
        blink_l = frame.blink_l
        blink_r = frame.blink_r
        if cfg.calibrate_mouth:
            mouth_open = _calibrated_expression(mouth_open, base_mouth, cfg.mouth_deadzone)
        if cfg.calibrate_blinks:
            blink_l = _calibrated_expression(blink_l, base_blink_l, cfg.blink_deadzone)
            blink_r = _calibrated_expression(blink_r, base_blink_r, cfg.blink_deadzone)
        raw = replace(
            frame,
            yaw_deg=_clamp((frame.yaw_deg - base_yaw) * float(cfg.yaw_scale), -45.0, 45.0),
            pitch_deg=_clamp((frame.pitch_deg - base_pitch) * float(cfg.pitch_scale), -35.0, 35.0),
            roll_deg=_clamp((frame.roll_deg - base_roll) * float(cfg.roll_scale), -30.0, 30.0),
            shoulder_roll_deg=_clamp(
                (frame.shoulder_roll_deg - base_shoulder_roll) * float(cfg.shoulder_roll_scale),
                -25.0,
                25.0,
            ),
            mouth_open=_clamp01(mouth_open * float(cfg.mouth_scale)),
            blink_l=_clamp01(blink_l * float(cfg.blink_scale)),
            blink_r=_clamp01(blink_r * float(cfg.blink_scale)),
        )
        if previous is None or alpha <= 0.0:
            current = raw
        else:
            current = replace(
                raw,
                yaw_deg=_lerp(raw.yaw_deg, previous.yaw_deg, alpha),
                pitch_deg=_lerp(raw.pitch_deg, previous.pitch_deg, alpha),
                roll_deg=_lerp(raw.roll_deg, previous.roll_deg, alpha),
                shoulder_roll_deg=_lerp(raw.shoulder_roll_deg, previous.shoulder_roll_deg, alpha),
                mouth_open=_lerp(raw.mouth_open, previous.mouth_open, alpha),
                blink_l=_lerp(raw.blink_l, previous.blink_l, alpha),
                blink_r=_lerp(raw.blink_r, previous.blink_r, alpha),
            )
        tuned.append(current)
        previous = current
    return tuple(tuned)


def idle_motion_frame(time_ms: int = 0) -> FaceMotionFrame:
    """Return a tiny idle motion used when a frame has no detectable face."""
    t = float(time_ms) / 1000.0
    blink = 1.0 if int(t * 10.0) % 37 == 0 else 0.0
    return FaceMotionFrame(
        time_ms=int(time_ms),
        yaw_deg=math.sin(t * 1.2) * 2.5,
        pitch_deg=math.sin(t * 0.9) * 1.2,
        roll_deg=math.sin(t * 0.7) * 1.0,
        mouth_open=0.0,
        blink_l=blink,
        blink_r=blink,
        confidence=0.0,
        face_box=None,
        source="idle_fallback",
    )


class VideoFaceMotionExtractor:
    """Extract coarse face motion from a video file."""

    def __init__(
        self,
        *,
        max_fps: float = 15.0,
        idle_on_missing: bool = True,
        backend: str = "auto",
        face_landmarker_model: str | Path | None = None,
    ) -> None:
        self.max_fps = max(1.0, float(max_fps or 15.0))
        self.idle_on_missing = bool(idle_on_missing)
        self.backend = _normalize_backend(backend)
        self.face_landmarker_model = Path(face_landmarker_model) if face_landmarker_model else None

    def extract(
        self,
        video_path: str | Path,
        *,
        max_frames: int | None = None,
        duration_seconds: float | None = None,
    ) -> VideoFaceMotionResult:
        p = Path(video_path)
        cv2 = _import_cv2()
        tasks_modules = _import_mediapipe_tasks() if self.backend in {"auto", "mediapipe_tasks"} else None
        task_model = _resolve_face_landmarker_model(self.face_landmarker_model, p.parent)
        mp_face_mesh = _import_mediapipe_face_mesh() if self.backend in {"auto", "mediapipe"} else None
        selected_backend = "opencv"
        if tasks_modules is not None and task_model is not None and self.backend in {"auto", "mediapipe_tasks"}:
            selected_backend = "mediapipe_tasks"
        elif mp_face_mesh is not None and self.backend in {"auto", "mediapipe"}:
            selected_backend = "mediapipe"
        diagnostics: dict[str, Any] = {
            "video_path": str(p),
            "video_exists": p.is_file(),
            "max_fps": self.max_fps,
            "requested_backend": self.backend,
            "selected_backend": selected_backend,
            "opencv_available": cv2 is not None,
            "mediapipe_tasks_available": tasks_modules is not None,
            "face_landmarker_model": str(task_model) if task_model is not None else "",
            "mediapipe_available": mp_face_mesh is not None,
            "errors": [],
            "warnings": [],
        }
        if self.backend in {"auto", "mediapipe_tasks"} and tasks_modules is not None and task_model is None:
            diagnostics["warnings"].append("mediapipe_tasks_model_missing")
        if cv2 is None:
            diagnostics["errors"].append("opencv_unavailable")
            diagnostics["install_hint"] = "Install opencv-python to extract face motion from video files."
            return VideoFaceMotionResult(False, (), diagnostics)
        if not p.is_file():
            diagnostics["errors"].append("video_missing")
            return VideoFaceMotionResult(False, (), diagnostics)

        face_cascade = _load_cascade(cv2, "haarcascade_frontalface_default.xml")
        eye_cascade = _load_cascade(cv2, "haarcascade_eye.xml")
        if selected_backend == "opencv" and self.backend == "mediapipe_tasks":
            diagnostics["errors"].append("mediapipe_tasks_unavailable_or_model_missing")
            return VideoFaceMotionResult(False, (), diagnostics)
        if selected_backend == "opencv" and self.backend == "mediapipe":
            diagnostics["errors"].append("mediapipe_unavailable")
            return VideoFaceMotionResult(False, (), diagnostics)
        if selected_backend == "opencv" and face_cascade is None:
            diagnostics["warnings"].append(
                "opencv_face_cascade_missing_using_foreground_fallback"
            )

        cap = cv2.VideoCapture(str(p))
        if not cap.isOpened():
            diagnostics["errors"].append("video_open_failed")
            return VideoFaceMotionResult(False, (), diagnostics)

        source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)
        sample_every = max(1, int(round(source_fps / self.max_fps)))
        frames: list[FaceMotionFrame] = []
        frame_index = 0
        prev_lower = None
        last_face: tuple[int, int, int, int] | None = None
        no_face_count = 0
        mesh_context = _create_mediapipe_context(mp_face_mesh) if selected_backend == "mediapipe" else None
        task_context = _create_mediapipe_tasks_context(tasks_modules, task_model) if selected_backend == "mediapipe_tasks" and task_model is not None else None
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_index % sample_every != 0:
                    frame_index += 1
                    continue

                time_ms = int(round((frame_index / max(1.0, source_fps)) * 1000.0))
                if duration_seconds is not None and time_ms > int(float(duration_seconds) * 1000.0):
                    break
                motion = None
                if task_context is not None:
                    motion = _extract_mediapipe_tasks_motion(cv2, task_context, frame, (frame_width, frame_height), time_ms)
                if mesh_context is not None:
                    motion = _extract_mediapipe_motion(cv2, mesh_context, frame, (frame_width, frame_height), time_ms)
                if motion is None:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    face = _detect_largest_face(cv2, face_cascade, gray) if face_cascade is not None else None
                    face_source = "haar_face"
                    if face is None:
                        face = _detect_foreground_face_box(cv2, frame)
                        face_source = "foreground_face_box" if face is not None else ""
                    roll = 0.0
                    eye_count = 2
                    lower_motion = 0.0
                    if face is not None:
                        no_face_count = 0
                        last_face = face
                        roll, eye_count = _estimate_eye_roll(cv2, eye_cascade, gray, face) if eye_cascade is not None else (0.0, 2)
                        if face_source == "foreground_face_box" and eye_count <= 0:
                            eye_count = 2
                        lower, lower_motion = _estimate_lower_face_motion(cv2, gray, face, prev_lower)
                        prev_lower = lower
                        motion = motion_from_face_box(
                            (frame_width, frame_height),
                            face,
                            time_ms=time_ms,
                            lower_motion=lower_motion,
                            eye_count=eye_count,
                            roll_deg=roll,
                            source=face_source,
                        )
                    else:
                        no_face_count += 1
                        if last_face is not None and no_face_count <= 4:
                            motion = motion_from_face_box((frame_width, frame_height), last_face, time_ms=time_ms, lower_motion=0.0, eye_count=2)
                            motion = replace(motion, source="last_face_hold")
                        elif self.idle_on_missing:
                            motion = idle_motion_frame(time_ms)
                if motion is not None:
                    frames.append(motion)
                if max_frames is not None and len(frames) >= int(max_frames):
                    break
                frame_index += 1
        finally:
            if task_context is not None:
                task_context.close()
            if mesh_context is not None:
                mesh_context.close()

        cap.release()
        diagnostics.update({
            "source_fps": source_fps,
            "sample_every": sample_every,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "sampled_frames": len(frames),
            "face_frames": sum(1 for item in frames if item.source in {"face_box", "haar_face", "foreground_face_box", "mediapipe_face_mesh", "mediapipe_tasks_face_landmarker", "last_face_hold"}),
            "mediapipe_tasks_frames": sum(1 for item in frames if item.source == "mediapipe_tasks_face_landmarker"),
            "mediapipe_frames": sum(1 for item in frames if item.source == "mediapipe_face_mesh"),
            "idle_frames": sum(1 for item in frames if item.source == "idle_fallback"),
        })
        if not frames:
            diagnostics["errors"].append("no_motion_frames")
        return VideoFaceMotionResult(bool(frames), tuple(frames), diagnostics)


def _import_cv2() -> Any:
    try:
        import cv2  # type: ignore
    except Exception:
        return None
    return cv2


def _import_mediapipe_face_mesh() -> Any:
    try:
        import mediapipe as mp  # type: ignore
    except Exception:
        return None
    solutions = getattr(mp, "solutions", None)
    return getattr(solutions, "face_mesh", None) if solutions is not None else None


def _import_mediapipe_tasks() -> tuple[Any, Any, Any, Any] | None:
    try:
        import mediapipe as mp  # type: ignore
        from mediapipe.tasks.python import BaseOptions, vision  # type: ignore
    except Exception:
        return None
    return mp, BaseOptions, vision, getattr(vision, "RunningMode", None)


def _resolve_face_landmarker_model(explicit_model: Path | None, video_dir: Path | None = None) -> Path | None:
    if explicit_model is not None:
        explicit = Path(explicit_model)
        return explicit if explicit.is_file() else None
    candidates: list[Path] = []
    roots = [
        Path.cwd() / "resources" / "mediapipe",
        Path.cwd() / "debugCapture" / "vtuber_assets" / "mediapipe",
        Path.cwd() / "debugCapture" / "mediapipe",
    ]
    if video_dir is not None:
        roots.insert(0, Path(video_dir))
    for root in roots:
        for name in DEFAULT_FACE_LANDMARKER_MODEL_NAMES:
            candidates.append(root / name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _create_mediapipe_tasks_context(tasks_modules: tuple[Any, Any, Any, Any], model_path: Path) -> Any:
    _mp, BaseOptions, vision, _running_mode = tasks_modules
    options = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.45,
        min_face_presence_confidence=0.45,
        min_tracking_confidence=0.45,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    return vision.FaceLandmarker.create_from_options(options)


def _extract_mediapipe_tasks_motion(
    cv2: Any,
    task_context: Any,
    frame: Any,
    frame_size: tuple[int, int],
    time_ms: int,
) -> FaceMotionFrame | None:
    import mediapipe as mp  # type: ignore

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = task_context.detect_for_video(image, int(time_ms))
    return motion_from_mediapipe_tasks_result(frame_size, result, time_ms=time_ms)


def _create_mediapipe_context(face_mesh_module: Any) -> Any:
    return face_mesh_module.FaceMesh(
        static_image_mode=False,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.45,
        min_tracking_confidence=0.45,
    )


def _extract_mediapipe_motion(
    cv2: Any,
    mesh_context: Any,
    frame: Any,
    frame_size: tuple[int, int],
    time_ms: int,
) -> FaceMotionFrame | None:
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = mesh_context.process(rgb)
    faces = getattr(result, "multi_face_landmarks", None) or []
    if not faces:
        return None
    return motion_from_face_landmarks(frame_size, faces[0].landmark, time_ms=time_ms)


def _landmark_points(landmarks: Any) -> list[tuple[float, float]]:
    source = getattr(landmarks, "landmark", landmarks)
    points: list[tuple[float, float]] = []
    try:
        iterator = iter(source)
    except TypeError:
        return points
    for item in iterator:
        try:
            points.append((float(getattr(item, "x")), float(getattr(item, "y"))))
        except (AttributeError, TypeError, ValueError):
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                points.append((float(item[0]), float(item[1])))
    return points


def _blendshape_scores(categories: Any) -> dict[str, float]:
    source = getattr(categories, "categories", categories)
    scores: dict[str, float] = {}
    try:
        iterator = iter(source)
    except TypeError:
        return scores
    for item in iterator:
        name = getattr(item, "category_name", None)
        score = getattr(item, "score", None)
        if name is None and isinstance(item, (tuple, list)) and len(item) >= 2:
            name, score = item[0], item[1]
        if name is None:
            continue
        try:
            scores[str(name)] = float(score)
        except (TypeError, ValueError):
            scores[str(name)] = 0.0
    return scores


def _normalize_backend(value: str) -> str:
    text = str(value or "auto").strip().casefold()
    aliases = {
        "mp": "mediapipe",
        "face_mesh": "mediapipe",
        "tasks": "mediapipe_tasks",
        "face_landmarker": "mediapipe_tasks",
        "mediapipe_task": "mediapipe_tasks",
    }
    text = aliases.get(text, text)
    return text if text in {"auto", "mediapipe_tasks", "mediapipe", "opencv"} else "auto"


def _load_cascade(cv2: Any, name: str) -> Any:
    cascade_path = Path(getattr(cv2.data, "haarcascades", "")) / name
    if not cascade_path.is_file():
        return None
    cascade = cv2.CascadeClassifier(str(cascade_path))
    return None if cascade.empty() else cascade


def _detect_largest_face(cv2: Any, face_cascade: Any, gray: Any) -> tuple[int, int, int, int] | None:
    min_size = (max(32, gray.shape[1] // 12), max(32, gray.shape[0] // 12))
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=min_size)
    if faces is None or len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda item: int(item[2]) * int(item[3]))
    return int(x), int(y), int(w), int(h)


def _detect_foreground_face_box(cv2: Any, frame: Any) -> tuple[int, int, int, int] | None:
    h, w = frame.shape[:2]
    if h <= 0 or w <= 0:
        return None
    border = 8
    samples = [
        frame[:border, :, :],
        frame[-border:, :, :],
        frame[:, :border, :],
        frame[:, -border:, :],
    ]
    import numpy as np

    bg = np.median(np.concatenate([sample.reshape(-1, 3) for sample in samples], axis=0), axis=0)
    diff = np.abs(frame.astype("float32") - bg.reshape(1, 1, 3)).mean(axis=2)
    mask = (diff > 22.0).astype("uint8") * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    found = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = found[0] if len(found) == 2 else found[1]
    if not contours:
        return None
    frame_area = float(w * h)
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        area = float(bw * bh)
        if area < frame_area * 0.015 or area > frame_area * 0.55:
            continue
        aspect = bw / max(1.0, float(bh))
        if not 0.45 <= aspect <= 1.7:
            continue
        center_bias = 1.0 - min(0.75, abs((x + bw * 0.5) - w * 0.5) / max(1.0, w * 0.5))
        candidates.append((area * center_bias, (int(x), int(y), int(bw), int(bh))))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def _estimate_eye_roll(cv2: Any, eye_cascade: Any, gray: Any, face_box: tuple[int, int, int, int]) -> tuple[float, int]:
    x, y, w, h = face_box
    upper = gray[y:y + max(1, int(h * 0.55)), x:x + w]
    eyes = eye_cascade.detectMultiScale(upper, scaleFactor=1.1, minNeighbors=5, minSize=(max(8, w // 10), max(8, h // 12)))
    if eyes is None or len(eyes) < 2:
        return 0.0, 0 if eyes is None else int(len(eyes))
    centers = sorted(((int(ex + ew * 0.5), int(ey + eh * 0.5)) for ex, ey, ew, eh in eyes), key=lambda item: item[0])[:2]
    left, right = centers[0], centers[1]
    roll = math.degrees(math.atan2(right[1] - left[1], max(1, right[0] - left[0])))
    return _clamp(roll, -18.0, 18.0), int(len(eyes))


def _estimate_lower_face_motion(cv2: Any, gray: Any, face_box: tuple[int, int, int, int], prev_lower: Any) -> tuple[Any, float]:
    x, y, w, h = face_box
    lower_y = y + int(h * 0.56)
    lower = gray[lower_y:y + h, x:x + w]
    if lower.size == 0:
        return lower, 0.0
    lower = cv2.resize(lower, (64, 32), interpolation=cv2.INTER_AREA)
    if prev_lower is None or getattr(prev_lower, "shape", None) != lower.shape:
        return lower, 0.0
    diff = cv2.absdiff(lower, prev_lower)
    mean_diff = float(diff.mean()) / 255.0
    dark_ratio = float((lower < 55).mean()) if hasattr(lower < 55, "mean") else 0.0
    return lower, _clamp01(mean_diff * 8.0 + max(0.0, dark_ratio - 0.08) * 1.8)


def _blink_from_eye_count(eye_count: int) -> float:
    if int(eye_count) <= 0:
        return 0.9
    if int(eye_count) == 1:
        return 0.35
    return 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _calibrated_expression(value: float, neutral: float, deadzone: float) -> float:
    dz = _clamp(float(deadzone), 0.0, 0.95)
    base = _clamp01(float(neutral))
    amount = max(0.0, float(value) - base - dz)
    return _clamp01(amount / max(0.0001, 1.0 - base - dz))


def _lerp(value: float, previous: float, alpha: float) -> float:
    return float(value) * (1.0 - float(alpha)) + float(previous) * float(alpha)
