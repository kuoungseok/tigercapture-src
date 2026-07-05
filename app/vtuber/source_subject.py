"""Detect source-video subject boxes for VTuber camera framing."""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.vtuber.source_framing import estimate_upper_body_box_from_face_box
from app.vtuber.video_face_driver import FaceMotionFrame


SOURCE_SUBJECT_SCHEMA = "tigerstudio.vtuber.source_subject.v1"


@dataclass(frozen=True)
class SourceSubjectFrame:
    time_ms: int
    subject_box: tuple[int, int, int, int] | None
    source: str = "none"
    confidence: float = 0.0
    face_box: tuple[int, int, int, int] | None = None
    shoulder_roll_deg: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_ms": int(self.time_ms),
            "subject_box": list(self.subject_box) if self.subject_box else None,
            "source": self.source,
            "confidence": float(self.confidence),
            "face_box": list(self.face_box) if self.face_box else None,
            "shoulder_roll_deg": float(self.shoulder_roll_deg),
        }


@dataclass(frozen=True)
class SourceSubjectResult:
    ok: bool
    frames: tuple[SourceSubjectFrame, ...]
    diagnostics: dict[str, Any]

    @property
    def subject_boxes(self) -> tuple[tuple[int, int, int, int] | None, ...]:
        return tuple(frame.subject_box for frame in self.frames)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_SUBJECT_SCHEMA,
            "ok": bool(self.ok),
            "frame_count": len(self.frames),
            "frames": [frame.to_dict() for frame in self.frames],
            "diagnostics": dict(self.diagnostics),
        }


def detect_subject_boxes_for_motion_frames(
    video_path: str | Path,
    frames: Sequence[FaceMotionFrame] | Iterable[FaceMotionFrame],
    *,
    source_frame_size: tuple[int, int],
    preset: str = "bust_up",
    detect_every: int = 3,
    detect_indices: Iterable[int] | None = None,
) -> SourceSubjectResult:
    """Detect person/upper-body boxes at motion-frame timestamps."""
    data = tuple(frames)
    path = Path(video_path)
    diagnostics: dict[str, Any] = {
        "video_path": str(path),
        "video_exists": path.is_file(),
        "source_frame_size": [int(source_frame_size[0]), int(source_frame_size[1])],
        "preset": str(preset),
        "detect_every": max(1, int(detect_every)),
        "detect_indices": sorted({int(index) for index in detect_indices}) if detect_indices is not None else None,
        "detectors": [],
        "warnings": [],
        "errors": [],
    }
    if not data:
        diagnostics["errors"].append("motion_frames_empty")
        return SourceSubjectResult(False, (), diagnostics)
    if not path.is_file():
        diagnostics["errors"].append("video_missing")
        return SourceSubjectResult(False, _fallback_frames(data, source_frame_size, preset), diagnostics)
    cv2 = _import_cv2()
    if cv2 is None:
        diagnostics["errors"].append("opencv_unavailable")
        return SourceSubjectResult(False, _fallback_frames(data, source_frame_size, preset), diagnostics)

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        diagnostics["errors"].append("video_open_failed")
        return SourceSubjectResult(False, _fallback_frames(data, source_frame_size, preset), diagnostics)

    hog = _create_hog_detector(cv2)
    upper_cascade = _load_cascade(cv2, "haarcascade_upperbody.xml")
    full_cascade = _load_cascade(cv2, "haarcascade_fullbody.xml")
    if hog is not None:
        diagnostics["detectors"].append("opencv_hog_people")
    if upper_cascade is not None:
        diagnostics["detectors"].append("opencv_haar_upperbody")
    if full_cascade is not None:
        diagnostics["detectors"].append("opencv_haar_fullbody")
    diagnostics["detectors"].extend(["foreground_subject", "grabcut_subject"])

    src_w, src_h = max(1, int(source_frame_size[0])), max(1, int(source_frame_size[1]))
    video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or src_w)
    video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or src_h)
    diagnostics["video_frame_size"] = [video_w, video_h]
    out: list[SourceSubjectFrame] = []
    last_detected: tuple[int, int, int, int] | None = None
    last_shoulder_roll = 0.0
    stride = max(1, int(detect_every))
    detect_index_set = {int(index) for index in detect_indices} if detect_indices is not None else None
    try:
        for index, frame in enumerate(data):
            face_in_video = _scale_box(frame.face_box, (src_w, src_h), (video_w, video_h)) if frame.face_box else None
            detected: tuple[int, int, int, int] | None = None
            source = "estimated_from_face"
            confidence = 0.35
            shoulder_roll = 0.0
            should_detect = index in detect_index_set if detect_index_set is not None else index % stride == 0
            if should_detect:
                detected, source, confidence = _detect_subject_box_at_time(
                    cv2,
                    cap,
                    int(frame.time_ms),
                    face_in_video,
                    hog=hog,
                    upper_cascade=upper_cascade,
                    full_cascade=full_cascade,
                )
                if detected is not None:
                    last_detected = detected
                    estimated_roll = _estimate_shoulder_roll_at_time(cv2, cap, int(frame.time_ms), face_in_video, detected)
                    if estimated_roll is not None:
                        shoulder_roll = estimated_roll
                        last_shoulder_roll = shoulder_roll
            elif last_detected is not None:
                detected = last_detected
                source = "held_previous_detection"
                confidence = 0.50
                shoulder_roll = last_shoulder_roll
            if detected is None and face_in_video is not None:
                detected = estimate_upper_body_box_from_face_box((video_w, video_h), face_in_video, preset=preset)
                source = "estimated_from_face"
                confidence = 0.32
                if should_detect:
                    estimated_roll = _estimate_shoulder_roll_at_time(cv2, cap, int(frame.time_ms), face_in_video, detected)
                    if estimated_roll is not None:
                        shoulder_roll = estimated_roll
                        last_shoulder_roll = shoulder_roll
            mapped = _scale_box(detected, (video_w, video_h), (src_w, src_h)) if detected else None
            out.append(
                SourceSubjectFrame(
                    time_ms=int(frame.time_ms),
                    subject_box=mapped,
                    source=source if mapped else "none",
                    confidence=float(confidence if mapped else 0.0),
                    face_box=frame.face_box,
                    shoulder_roll_deg=float(shoulder_roll if mapped else 0.0),
                )
            )
    finally:
        cap.release()

    diagnostics["detected_frames"] = sum(
        1
        for frame in out
        if frame.source in {"opencv_hog_people", "opencv_haar_upperbody", "opencv_haar_fullbody", "foreground_subject", "grabcut_subject"}
    )
    diagnostics["held_frames"] = sum(1 for frame in out if frame.source == "held_previous_detection")
    diagnostics["estimated_frames"] = sum(1 for frame in out if frame.source == "estimated_from_face")
    diagnostics["missing_frames"] = sum(1 for frame in out if frame.subject_box is None)
    diagnostics["shoulder_roll_frames"] = sum(1 for frame in out if abs(float(frame.shoulder_roll_deg)) >= 0.25)
    diagnostics["shoulder_roll_range"] = _range(frame.shoulder_roll_deg for frame in out)
    ok = bool(out) and diagnostics["missing_frames"] < len(out)
    if diagnostics["detected_frames"] == 0:
        diagnostics["warnings"].append("no_cv_subject_detector_hits_used_face_estimate")
    return SourceSubjectResult(ok, tuple(out), diagnostics)


def choose_subject_candidate(
    candidates: Iterable[tuple[int, int, int, int, float, str]],
    frame_size: tuple[int, int],
    face_box: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int, float, str] | None:
    data = list(candidates)
    if not data:
        return None
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    return max(data, key=lambda row: _candidate_score(row, width, height, face_box))


def _detect_subject_box_at_time(
    cv2: Any,
    cap: Any,
    time_ms: int,
    face_box: tuple[int, int, int, int] | None,
    *,
    hog: Any,
    upper_cascade: Any,
    full_cascade: Any,
) -> tuple[tuple[int, int, int, int] | None, str, float]:
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, int(time_ms)))
    ok, frame = cap.read()
    if not ok or frame is None:
        return None, "none", 0.0
    height, width = frame.shape[:2]
    candidates: list[tuple[int, int, int, int, float, str]] = []
    detect_frame, scale = _resize_for_detection(cv2, frame)
    if hog is not None:
        try:
            persons, weights = hog.detectMultiScale(detect_frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
        except Exception:
            persons, weights = [], []
        candidates.extend(_map_detections(persons, weights, scale, "opencv_hog_people"))
    gray = cv2.cvtColor(detect_frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    for cascade, source in ((upper_cascade, "opencv_haar_upperbody"), (full_cascade, "opencv_haar_fullbody")):
        if cascade is None:
            continue
        try:
            boxes = cascade.detectMultiScale(
                gray,
                scaleFactor=1.08,
                minNeighbors=3,
                minSize=(max(32, detect_frame.shape[1] // 8), max(32, detect_frame.shape[0] // 7)),
            )
        except Exception:
            boxes = []
        candidates.extend(_map_detections(boxes, [], scale, source))
    foreground = _detect_foreground_subject_box(cv2, frame, face_box)
    if foreground is not None:
        candidates.append((*foreground, 0.62, "foreground_subject"))
    grabcut = _detect_grabcut_subject_box(cv2, frame, face_box)
    if grabcut is not None:
        candidates.append((*grabcut, 0.68, "grabcut_subject"))
    choice = choose_subject_candidate(candidates, (width, height), face_box)
    if choice is None:
        return None, "none", 0.0
    x, y, w, h, confidence, source = choice
    return _clip_box((x, y, w, h), width, height), source, confidence


def _fallback_frames(
    frames: Sequence[FaceMotionFrame],
    source_frame_size: tuple[int, int],
    preset: str,
) -> tuple[SourceSubjectFrame, ...]:
    return tuple(
        SourceSubjectFrame(
            time_ms=int(frame.time_ms),
            subject_box=estimate_upper_body_box_from_face_box(source_frame_size, frame.face_box, preset=preset) if frame.face_box else None,
            source="estimated_from_face" if frame.face_box else "none",
            confidence=0.32 if frame.face_box else 0.0,
            face_box=frame.face_box,
            shoulder_roll_deg=0.0,
        )
        for frame in frames
    )


def _estimate_shoulder_roll_at_time(
    cv2: Any,
    cap: Any,
    time_ms: int,
    face_box: tuple[int, int, int, int] | None,
    subject_box: tuple[int, int, int, int] | None,
) -> float | None:
    if face_box is None or subject_box is None:
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0, int(time_ms)))
    ok, frame = cap.read()
    if not ok or frame is None:
        return None
    return _estimate_shoulder_roll_from_frame(cv2, frame, face_box, subject_box)


def _estimate_shoulder_roll_from_frame(
    cv2: Any,
    frame: Any,
    face_box: tuple[int, int, int, int],
    subject_box: tuple[int, int, int, int],
) -> float | None:
    """Estimate screen-space shoulder/torso roll below the tracked face."""
    height, width = frame.shape[:2]
    if height <= 0 or width <= 0:
        return None
    fx, fy, fw, fh = [int(v) for v in face_box]
    sx, sy, sw, sh = _clip_box(subject_box, width, height)
    x0 = max(0, sx)
    x1 = min(width, sx + sw)
    y0 = max(0, int(round(fy + fh * 0.62)))
    y1 = min(height, sy + sh, int(round(fy + fh * 2.45)))
    if x1 - x0 < 24 or y1 - y0 < 18:
        return None
    import numpy as np

    roi = np.ascontiguousarray(frame[y0:y1, x0:x1])
    if roi.size <= 0:
        return None
    try:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(gray, 45, 120)
    except Exception:
        return None
    min_len = max(18, int((x1 - x0) * 0.08))
    try:
        lines = cv2.HoughLinesP(edges, 1, math.pi / 180.0, threshold=16, minLineLength=min_len, maxLineGap=18)
    except Exception:
        lines = None
    if lines is None:
        return None
    face_cx = (float(fx) + float(fw) * 0.5) - float(x0)
    band_h = max(1.0, float(y1 - y0))
    weighted: list[tuple[float, float]] = []
    for raw in lines.reshape(-1, 4):
        x_a, y_a, x_b, y_b = [float(v) for v in raw]
        dx = x_b - x_a
        dy = y_b - y_a
        length = math.hypot(dx, dy)
        if length < min_len:
            continue
        angle = math.degrees(math.atan2(dy, dx))
        while angle > 90.0:
            angle -= 180.0
        while angle < -90.0:
            angle += 180.0
        if abs(angle) > 28.0:
            continue
        mid_x = (x_a + x_b) * 0.5
        mid_y = (y_a + y_b) * 0.5
        center_weight = 1.0 - min(0.75, abs(mid_x - face_cx) / max(1.0, float(x1 - x0)))
        y_norm = mid_y / band_h
        band_weight = 1.0 - min(0.65, abs(y_norm - 0.36))
        weight = length * center_weight * band_weight
        if weight <= 0.0:
            continue
        weighted.append((angle, weight))
    if not weighted:
        return None
    total = sum(weight for _angle, weight in weighted)
    if total <= 0.0:
        return None
    return _clamp(sum(angle * weight for angle, weight in weighted) / total, -18.0, 18.0)


def _candidate_score(
    row: tuple[int, int, int, int, float, str],
    width: int,
    height: int,
    face_box: tuple[int, int, int, int] | None,
) -> float:
    x, y, w, h, confidence, source = row
    area = float(w) * float(h) / max(1.0, float(width) * float(height))
    score = area + float(confidence) * 0.035
    if source == "opencv_haar_upperbody":
        score += 0.12
    if source == "opencv_hog_people":
        score += 0.08
    if source == "foreground_subject":
        score += 0.10
    if source == "grabcut_subject":
        score += 0.16
    if face_box is not None:
        fx, fy, fw, fh = [float(v) for v in face_box]
        fcx = fx + fw * 0.5
        fcy = fy + fh * 0.5
        contains_x = float(x) - w * 0.18 <= fcx <= float(x + w) + w * 0.18
        head_band = float(y) - h * 0.08 <= fcy <= float(y) + h * 0.48
        if contains_x:
            score += 0.30
        if head_band:
            score += 0.24
    else:
        cx = float(x) + float(w) * 0.5
        score += (1.0 - min(0.85, abs(cx - width * 0.5) / max(1.0, width * 0.5))) * 0.12
    return score


def _detect_foreground_subject_box(
    cv2: Any,
    frame: Any,
    face_box: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    height, width = frame.shape[:2]
    if height <= 0 or width <= 0:
        return None
    import numpy as np

    border = max(6, min(width, height) // 42)
    samples = [
        frame[:border, :, :],
        frame[-border:, :, :],
        frame[:, :border, :],
        frame[:, -border:, :],
    ]
    bg = np.median(np.concatenate([sample.reshape(-1, 3) for sample in samples], axis=0), axis=0)
    diff = np.abs(frame.astype("float32") - bg.reshape(1, 1, 3)).mean(axis=2)
    mask = (diff > 18.0).astype("uint8") * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    if face_box is not None:
        fx, fy, fw, fh = [int(v) for v in face_box]
        x0 = max(0, fx - int(fw * 1.45))
        x1 = min(width, fx + fw + int(fw * 1.45))
        y0 = max(0, fy - int(fh * 0.85))
        y1 = min(height, fy + int(fh * 3.75))
        roi = np.zeros_like(mask)
        roi[y0:y1, x0:x1] = 255
        mask = cv2.bitwise_and(mask, roi)
    found = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = found[0] if len(found) == 2 else found[1]
    if not contours:
        return None
    frame_area = float(width * height)
    face_cx = None
    face_cy = None
    if face_box is not None:
        fx, fy, fw, fh = [float(v) for v in face_box]
        face_cx = fx + fw * 0.5
        face_cy = fy + fh * 0.5
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area_ratio = float(w * h) / max(1.0, frame_area)
        if area_ratio < 0.035 or area_ratio > 0.90:
            continue
        aspect = float(w) / max(1.0, float(h))
        if not 0.35 <= aspect <= 2.4:
            continue
        score = area_ratio
        if face_cx is not None and face_cy is not None:
            contains_x = float(x) - w * 0.20 <= face_cx <= float(x + w) + w * 0.20
            head_band = float(y) - h * 0.10 <= face_cy <= float(y) + h * 0.52
            if contains_x:
                score += 0.45
            if head_band:
                score += 0.35
        candidates.append((score, (int(x), int(y), int(w), int(h))))
    if not candidates:
        return None
    return _clip_box(max(candidates, key=lambda item: item[0])[1], width, height)


def _detect_grabcut_subject_box(
    cv2: Any,
    frame: Any,
    face_box: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    if face_box is None:
        return None
    height, width = frame.shape[:2]
    if height <= 0 or width <= 0:
        return None
    import numpy as np

    fx, fy, fw, fh = [int(v) for v in face_box]
    seed = _clip_box(
        (
            int(round(fx - fw * 0.55)),
            int(round(fy - fh * 0.45)),
            int(round(fw * 2.10)),
            int(round(fh * 3.15)),
        ),
        width,
        height,
    )
    x, y, w, h = seed
    x = max(1, x)
    y = max(1, y)
    w = min(width - x - 2, max(2, w))
    h = min(height - y - 2, max(2, h))
    if w <= 8 or h <= 8:
        return None
    mask = np.zeros((height, width), np.uint8)
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(frame, mask, (x, y, w, h), bgd, fgd, 3, cv2.GC_INIT_WITH_RECT)
    except Exception:
        return None
    fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=2)
    found = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = found[0] if len(found) == 2 else found[1]
    if not contours:
        return None
    face_cx = float(fx) + float(fw) * 0.5
    face_cy = float(fy) + float(fh) * 0.5
    frame_area = float(width * height)
    candidates: list[tuple[float, tuple[int, int, int, int]]] = []
    for contour in contours:
        bx, by, bw, bh = cv2.boundingRect(contour)
        area_ratio = float(bw * bh) / max(1.0, frame_area)
        if area_ratio < 0.025 or area_ratio > 0.85:
            continue
        contains_x = float(bx) - bw * 0.18 <= face_cx <= float(bx + bw) + bw * 0.18
        head_band = float(by) - bh * 0.12 <= face_cy <= float(by) + bh * 0.56
        if not (contains_x and head_band):
            continue
        score = area_ratio + 0.45
        candidates.append((score, (int(bx), int(by), int(bw), int(bh))))
    if not candidates:
        return None
    return _clip_box(max(candidates, key=lambda item: item[0])[1], width, height)


def _resize_for_detection(cv2: Any, frame: Any) -> tuple[Any, float]:
    height, width = frame.shape[:2]
    if height <= 480:
        return frame, 1.0
    scale = 480.0 / float(height)
    resized = cv2.resize(frame, (max(1, int(round(width * scale))), 480), interpolation=cv2.INTER_AREA)
    return resized, scale


def _map_detections(
    boxes: Any,
    weights: Any,
    scale: float,
    source: str,
) -> list[tuple[int, int, int, int, float, str]]:
    mapped: list[tuple[int, int, int, int, float, str]] = []
    inv = 1.0 / max(float(scale), 1e-6)
    for index, box in enumerate(boxes or []):
        x, y, w, h = [int(v) for v in box[:4]]
        if scale != 1.0:
            x = int(round(x * inv))
            y = int(round(y * inv))
            w = int(round(w * inv))
            h = int(round(h * inv))
        if w <= 0 or h <= 0:
            continue
        try:
            confidence = float(weights[index]) if index < len(weights) else 0.45
        except Exception:
            confidence = 0.45
        mapped.append((x, y, w, h, confidence, source))
    return mapped


def _scale_box(
    box: tuple[int, int, int, int] | None,
    source_size: tuple[int, int],
    target_size: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    if box is None:
        return None
    sw, sh = max(1, int(source_size[0])), max(1, int(source_size[1]))
    tw, th = max(1, int(target_size[0])), max(1, int(target_size[1]))
    sx = float(tw) / float(sw)
    sy = float(th) / float(sh)
    x, y, w, h = box
    return _clip_box((int(round(x * sx)), int(round(y * sy)), int(round(w * sx)), int(round(h * sy))), tw, th)


def _clip_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = [int(v) for v in box]
    x0 = max(0, min(max(0, int(width) - 1), x))
    y0 = max(0, min(max(0, int(height) - 1), y))
    x1 = max(x0 + 1, min(int(width), x + max(1, w)))
    y1 = max(y0 + 1, min(int(height), y + max(1, h)))
    return (x0, y0, max(1, x1 - x0), max(1, y1 - y0))


def _range(values: Iterable[float]) -> float:
    data = [float(value) for value in values]
    return max(data) - min(data) if data else 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _create_hog_detector(cv2: Any) -> Any:
    try:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        return hog
    except Exception:
        return None


def _load_cascade(cv2: Any, name: str) -> Any:
    cascade_path = Path(getattr(cv2.data, "haarcascades", "")) / name
    if not cascade_path.is_file():
        return None
    cascade = cv2.CascadeClassifier(str(cascade_path))
    return None if cascade.empty() else cascade


def _import_cv2() -> Any:
    try:
        import cv2  # type: ignore
    except Exception:
        return None
    return cv2
