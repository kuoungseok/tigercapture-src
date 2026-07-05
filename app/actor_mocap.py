"""Video/Webcam motion-capture helpers for actor tracks.

The first production slice is intentionally file-based: analyze a local video,
turn face motion into Live2D actor transform keyframes, and preserve richer
retargeting payloads for later parameter-level rendering.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Callable, Iterable, Mapping


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _soft_deadzone(value: float, radius: float) -> float:
    """Remove small detector jitter while preserving larger intentional motion."""
    v = float(value)
    r = max(0.0, float(radius))
    if abs(v) <= r:
        return 0.0
    return (abs(v) - r) * (1.0 if v >= 0.0 else -1.0)


def _optional_clamped(
    row: Mapping[str, Any],
    *names: str,
    low: float,
    high: float,
) -> float | None:
    for name in names:
        if name not in row:
            continue
        value = row.get(name)
        if value is None or value == "":
            return None
        try:
            return _clamp(float(value), low, high)
        except Exception:
            return None
    return None


def _smooth_series(
    values: list[tuple[int, float]],
    *,
    alpha: float,
    seed: float | None = None,
) -> list[tuple[int, float]]:
    """Simple one-pole smoothing for detector-derived scalar tracks."""
    if not values:
        return []
    a = _clamp(alpha, 0.01, 1.0)
    last = float(values[0][1] if seed is None else seed)
    out: list[tuple[int, float]] = []
    for t, v in values:
        last = last + (float(v) - last) * a
        out.append((int(t), float(last)))
    return out


@dataclass(frozen=True)
class MocapFrame:
    time_ms: int
    x_norm: float
    y_norm: float
    w_norm: float
    h_norm: float
    confidence: float = 1.0
    person_x_norm: float = 0.0
    person_y_norm: float = 0.0
    person_w_norm: float = 0.0
    person_h_norm: float = 0.0
    head_yaw: float | None = None
    head_pitch: float | None = None
    head_roll: float | None = None
    gaze_x: float | None = None
    gaze_y: float | None = None
    mouth_open: float | None = None
    mouth_form: float | None = None
    eye_l_open: float | None = None
    eye_r_open: float | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> "MocapFrame":
        return cls(
            time_ms=max(0, int(row.get("time_ms", row.get("t_ms", 0)) or 0)),
            x_norm=_clamp(float(row.get("x_norm", 0.5) or 0.5), 0.0, 1.0),
            y_norm=_clamp(float(row.get("y_norm", 0.5) or 0.5), 0.0, 1.0),
            w_norm=_clamp(float(row.get("w_norm", 0.0) or 0.0), 0.0, 1.0),
            h_norm=_clamp(float(row.get("h_norm", 0.0) or 0.0), 0.0, 1.0),
            confidence=_clamp(float(row.get("confidence", 1.0) or 1.0), 0.0, 1.0),
            person_x_norm=_clamp(
                float(row.get("person_x_norm", row.get("body_x_norm", 0.0)) or 0.0),
                0.0,
                1.0,
            ),
            person_y_norm=_clamp(
                float(row.get("person_y_norm", row.get("body_y_norm", 0.0)) or 0.0),
                0.0,
                1.0,
            ),
            person_w_norm=_clamp(
                float(row.get("person_w_norm", row.get("body_w_norm", 0.0)) or 0.0),
                0.0,
                1.0,
            ),
            person_h_norm=_clamp(
                float(row.get("person_h_norm", row.get("body_h_norm", 0.0)) or 0.0),
                0.0,
                1.0,
            ),
            head_yaw=_optional_clamped(row, "head_yaw", "yaw", low=-1.0, high=1.0),
            head_pitch=_optional_clamped(row, "head_pitch", "pitch", low=-1.0, high=1.0),
            head_roll=_optional_clamped(row, "head_roll", "roll", low=-1.0, high=1.0),
            gaze_x=_optional_clamped(row, "gaze_x", "eye_ball_x", low=-1.0, high=1.0),
            gaze_y=_optional_clamped(row, "gaze_y", "eye_ball_y", low=-1.0, high=1.0),
            mouth_open=_optional_clamped(row, "mouth_open", "mouth_open_y", low=0.0, high=1.0),
            mouth_form=_optional_clamped(row, "mouth_form", low=-1.0, high=1.0),
            eye_l_open=_optional_clamped(row, "eye_l_open", "left_eye_open", low=0.0, high=2.0),
            eye_r_open=_optional_clamped(row, "eye_r_open", "right_eye_open", low=0.0, high=2.0),
        )

    def to_dict(self) -> dict[str, Any]:
        row = {
            "time_ms": int(self.time_ms),
            "x_norm": round(float(self.x_norm), 5),
            "y_norm": round(float(self.y_norm), 5),
            "w_norm": round(float(self.w_norm), 5),
            "h_norm": round(float(self.h_norm), 5),
            "confidence": round(float(self.confidence), 4),
        }
        if self.person_w_norm > 0.0 and self.person_h_norm > 0.0:
            row.update(
                {
                    "person_x_norm": round(float(self.person_x_norm), 5),
                    "person_y_norm": round(float(self.person_y_norm), 5),
                    "person_w_norm": round(float(self.person_w_norm), 5),
                    "person_h_norm": round(float(self.person_h_norm), 5),
                }
            )
        for key in (
            "head_yaw",
            "head_pitch",
            "head_roll",
            "gaze_x",
            "gaze_y",
            "mouth_open",
            "mouth_form",
            "eye_l_open",
            "eye_r_open",
        ):
            value = getattr(self, key)
            if value is not None:
                row[key] = round(float(value), 5)
        return row


def _normalize_frames(frames: Iterable[MocapFrame | Mapping[str, Any]]) -> list[MocapFrame]:
    out: list[MocapFrame] = []
    for row in frames or []:
        if isinstance(row, MocapFrame):
            out.append(row)
        elif isinstance(row, Mapping):
            out.append(MocapFrame.from_mapping(row))
    out.sort(key=lambda frame: frame.time_ms)
    return out


def _reduce_keyframes(
    values: list[tuple[int, float]],
    *,
    epsilon: float,
    min_gap_ms: int = 90,
) -> list[dict[str, Any]]:
    """Keep enough scalar keys for smooth motion without overloading project IO."""
    if not values:
        return []
    reduced: list[tuple[int, float]] = [values[0]]
    last_t, last_v = values[0]
    for t, v in values[1:-1]:
        if abs(float(v) - float(last_v)) >= epsilon or int(t) - int(last_t) >= min_gap_ms * 3:
            reduced.append((int(t), float(v)))
            last_t, last_v = int(t), float(v)
    if values[-1][0] != reduced[-1][0]:
        reduced.append(values[-1])
    return [
        {"time_ms": int(t), "value": round(float(v), 5), "curve": "smoothstep"}
        for t, v in reduced
    ]


def _optional_track(
    frames: list[MocapFrame],
    attr: str,
    *,
    alpha: float,
) -> list[tuple[int, float]]:
    values: list[tuple[int, float]] = []
    for frame in frames:
        value = getattr(frame, attr, None)
        if value is not None:
            values.append((int(frame.time_ms), float(value)))
    if not values:
        return []
    return _smooth_series(values, alpha=alpha)


def _zero_deadzone_track(values: list[tuple[int, float]], *, radius: float) -> list[tuple[int, float]]:
    r = max(0.0, float(radius))
    if r <= 0.0:
        return [(int(t), float(v)) for t, v in values]
    return [(int(t), 0.0 if abs(float(v)) <= r else float(v)) for t, v in values]


def _track_by_time(values: list[tuple[int, float]]) -> dict[int, float]:
    return {int(t): float(v) for t, v in values}


def _average_tracks(
    left: list[tuple[int, float]],
    right: list[tuple[int, float]],
    *,
    fallback: float = 1.0,
) -> list[tuple[int, float]]:
    if not left and not right:
        return []
    lmap = _track_by_time(left)
    rmap = _track_by_time(right)
    times = sorted(set(lmap) | set(rmap))
    out: list[tuple[int, float]] = []
    last_l = float(left[0][1]) if left else float(fallback)
    last_r = float(right[0][1]) if right else float(fallback)
    for time_ms in times:
        if time_ms in lmap:
            last_l = lmap[time_ms]
        if time_ms in rmap:
            last_r = rmap[time_ms]
        out.append((int(time_ms), (float(last_l) + float(last_r)) * 0.5))
    return out


def _blink_from_eye_open(values: list[tuple[int, float]]) -> list[tuple[int, float]]:
    return [(int(t), _clamp(1.0 - _clamp(float(v), 0.0, 1.0), 0.0, 1.0)) for t, v in values]


def _breath_track(frames: list[MocapFrame], *, amplitude: float = 0.14, period_ms: int = 3200) -> list[tuple[int, float]]:
    if not frames:
        return []
    period = max(600.0, float(period_ms))
    amp = _clamp(float(amplitude), 0.0, 0.35)
    return [
        (
            int(frame.time_ms),
            _clamp(0.5 + math.sin((float(frame.time_ms) / period) * math.tau) * amp, 0.0, 1.0),
        )
        for frame in frames
    ]


def _classify_shot(frames: list[MocapFrame]) -> dict[str, Any]:
    """Classify framing from face and optional person boxes.

    Person boxes are preferred because they separate upper-body crop footage
    from true full-body footage. Face-box-only data remains a fallback for
    videos where the local OpenCV person detector cannot produce a stable box.
    """
    if not frames:
        return {
            "profile": "unknown",
            "confidence": 0.0,
            "face_width": 0.0,
            "face_height": 0.0,
            "face_area": 0.0,
            "person_width": 0.0,
            "person_height": 0.0,
            "person_bottom": 0.0,
            "face_to_person_height_ratio": 0.0,
            "method": "face_bbox_heuristic",
        }
    widths = [max(0.001, float(f.w_norm)) for f in frames]
    heights = [max(0.001, float(f.h_norm)) for f in frames]
    areas = [w * h for w, h in zip(widths, heights)]
    med_w = float(median(widths))
    med_h = float(median(heights))
    med_area = float(median(areas))
    person_frames = [f for f in frames if f.person_w_norm > 0.001 and f.person_h_norm > 0.001]
    med_person_w = 0.0
    med_person_h = 0.0
    med_person_bottom = 0.0
    face_to_person_h = 0.0
    person_coverage = len(person_frames) / max(1, len(frames))
    if person_frames:
        person_widths = [max(0.001, float(f.person_w_norm)) for f in person_frames]
        person_heights = [max(0.001, float(f.person_h_norm)) for f in person_frames]
        person_bottoms = [
            _clamp(float(f.person_y_norm) + float(f.person_h_norm) * 0.5, 0.0, 1.0)
            for f in person_frames
        ]
        ratios = [
            max(0.001, float(f.h_norm)) / max(0.001, float(f.person_h_norm))
            for f in person_frames
        ]
        med_person_w = float(median(person_widths))
        med_person_h = float(median(person_heights))
        med_person_bottom = float(median(person_bottoms))
        face_to_person_h = float(median(ratios))

    # Haar face boxes are conservative. These thresholds intentionally classify
    # a large talking-head box as close-up so actor transform jitter is locked.
    if med_h >= 0.30 or med_w >= 0.24 or med_area >= 0.070:
        profile = "face_closeup"
        confidence = _clamp((med_h - 0.24) / 0.18 + 0.55, 0.55, 0.98)
        method = "face_bbox_heuristic"
    elif (
        person_coverage >= 0.25
        and med_person_h >= 0.50
        and med_person_bottom >= 0.82
        and face_to_person_h <= 0.24
    ):
        profile = "full_body"
        confidence = _clamp(
            0.58 + person_coverage * 0.25 + (med_person_bottom - 0.82) * 0.60,
            0.58,
            0.94,
        )
        method = "face_person_bbox_heuristic"
    elif person_coverage >= 0.25 and (
        med_person_h >= 0.36
        or med_person_bottom < 0.82
        or face_to_person_h > 0.24
    ):
        profile = "upper_body"
        confidence = _clamp(0.54 + person_coverage * 0.25 + max(0.0, med_person_h - 0.36) * 0.35, 0.54, 0.92)
        method = "face_person_bbox_heuristic"
    elif med_h >= 0.17 or med_w >= 0.14 or med_area >= 0.030:
        profile = "upper_body"
        confidence = _clamp((med_h - 0.13) / 0.18 + 0.45, 0.45, 0.90)
        method = "face_bbox_heuristic"
    else:
        profile = "full_body_or_wide"
        confidence = _clamp((0.19 - med_h) / 0.16 + 0.42, 0.42, 0.88)
        method = "face_bbox_heuristic"

    return {
        "profile": profile,
        "confidence": round(float(confidence), 4),
        "face_width": round(med_w, 5),
        "face_height": round(med_h, 5),
        "face_area": round(med_area, 5),
        "person_width": round(float(med_person_w), 5),
        "person_height": round(float(med_person_h), 5),
        "person_bottom": round(float(med_person_bottom), 5),
        "face_to_person_height_ratio": round(float(face_to_person_h), 5),
        "person_coverage": round(float(person_coverage), 4),
        "method": method,
    }


def _landmark_xy(landmarks: list[Any], idx: int) -> tuple[float, float] | None:
    if idx < 0 or idx >= len(landmarks):
        return None
    pt = landmarks[idx]
    return float(getattr(pt, "x", 0.0)), float(getattr(pt, "y", 0.0))


def _dist(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float:
    if a is None or b is None:
        return 0.0
    return ((a[0] - b[0]) ** 2.0 + (a[1] - b[1]) ** 2.0) ** 0.5


def _mean_xy(landmarks: list[Any], ids: list[int]) -> tuple[float, float] | None:
    pts = [_landmark_xy(landmarks, idx) for idx in ids]
    pts = [pt for pt in pts if pt is not None]
    if not pts:
        return None
    return sum(pt[0] for pt in pts) / len(pts), sum(pt[1] for pt in pts) / len(pts)


def _extract_face_mesh_detail(frame: Any, cv2: Any, face_mesh: Any) -> dict[str, float] | None:
    """Return normalized Live2D mocap signals from MediaPipe FaceMesh, if present."""
    if face_mesh is None:
        return None
    try:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb)
    except Exception:
        return None
    faces = getattr(result, "multi_face_landmarks", None) or []
    if not faces:
        return None
    landmarks = list(getattr(faces[0], "landmark", []) or [])
    if not landmarks:
        return None
    xs = [_clamp(float(getattr(pt, "x", 0.0)), 0.0, 1.0) for pt in landmarks]
    ys = [_clamp(float(getattr(pt, "y", 0.0)), 0.0, 1.0) for pt in landmarks]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    face_w = max(0.001, max_x - min_x)
    face_h = max(0.001, max_y - min_y)
    left_eye_outer = _landmark_xy(landmarks, 33)
    left_eye_inner = _landmark_xy(landmarks, 133)
    right_eye_inner = _landmark_xy(landmarks, 362)
    right_eye_outer = _landmark_xy(landmarks, 263)
    eye_center = _mean_xy(landmarks, [33, 133, 362, 263])
    nose = _landmark_xy(landmarks, 1)
    mouth_l = _landmark_xy(landmarks, 78)
    mouth_r = _landmark_xy(landmarks, 308)
    mouth_top = _landmark_xy(landmarks, 13)
    mouth_bottom = _landmark_xy(landmarks, 14)

    detail: dict[str, float] = {
        "x_norm": _clamp((min_x + max_x) * 0.5, 0.0, 1.0),
        "y_norm": _clamp((min_y + max_y) * 0.5, 0.0, 1.0),
        "w_norm": _clamp(face_w, 0.0, 1.0),
        "h_norm": _clamp(face_h, 0.0, 1.0),
        "confidence": 0.92,
    }
    if nose is not None and eye_center is not None:
        detail["head_yaw"] = _clamp((nose[0] - eye_center[0]) / max(0.001, face_w * 0.18), -1.0, 1.0)
        detail["head_pitch"] = _clamp((nose[1] - eye_center[1] - face_h * 0.22) / max(0.001, face_h * 0.18), -1.0, 1.0)
    if left_eye_outer is not None and right_eye_outer is not None:
        detail["head_roll"] = _clamp(
            (right_eye_outer[1] - left_eye_outer[1]) / max(0.001, face_w * 0.30),
            -1.0,
            1.0,
        )

    if len(landmarks) >= 478:
        left_iris = _mean_xy(landmarks, [468, 469, 470, 471, 472])
        right_iris = _mean_xy(landmarks, [473, 474, 475, 476, 477])

        def _eye_gaze(
            iris: tuple[float, float] | None,
            corner_a: tuple[float, float] | None,
            corner_b: tuple[float, float] | None,
        ) -> tuple[float, float] | None:
            if iris is None or corner_a is None or corner_b is None:
                return None
            left_x, right_x = sorted([corner_a[0], corner_b[0]])
            top_y = min(corner_a[1], corner_b[1]) - face_h * 0.08
            bottom_y = max(corner_a[1], corner_b[1]) + face_h * 0.08
            eye_w = max(0.001, right_x - left_x)
            eye_h = max(0.001, bottom_y - top_y)
            gx = ((iris[0] - (left_x + right_x) * 0.5) / (eye_w * 0.5))
            gy = ((iris[1] - (top_y + bottom_y) * 0.5) / (eye_h * 0.5))
            return _clamp(gx, -1.0, 1.0), _clamp(gy, -1.0, 1.0)

        gaze_values = [
            gaze
            for gaze in (
                _eye_gaze(left_iris, left_eye_outer, left_eye_inner),
                _eye_gaze(right_iris, right_eye_inner, right_eye_outer),
            )
            if gaze is not None
        ]
        if gaze_values:
            detail["gaze_x"] = _clamp(sum(g[0] for g in gaze_values) / len(gaze_values), -1.0, 1.0)
            detail["gaze_y"] = _clamp(sum(g[1] for g in gaze_values) / len(gaze_values), -1.0, 1.0)

    left_eye_w = _dist(left_eye_outer, left_eye_inner)
    right_eye_w = _dist(right_eye_inner, right_eye_outer)
    left_eye_open = _dist(_landmark_xy(landmarks, 159), _landmark_xy(landmarks, 145))
    right_eye_open = _dist(_landmark_xy(landmarks, 386), _landmark_xy(landmarks, 374))
    if left_eye_w > 0.0:
        detail["eye_l_open"] = _clamp((left_eye_open / left_eye_w) * 5.2, 0.0, 2.0)
    if right_eye_w > 0.0:
        detail["eye_r_open"] = _clamp((right_eye_open / right_eye_w) * 5.2, 0.0, 2.0)
    mouth_w = _dist(mouth_l, mouth_r)
    mouth_h = _dist(mouth_top, mouth_bottom)
    if mouth_w > 0.0:
        detail["mouth_open"] = _clamp((mouth_h / mouth_w) * 3.2, 0.0, 1.0)
        detail["mouth_form"] = _clamp(((mouth_w / face_w) - 0.34) / 0.12, -1.0, 1.0)
    return detail


def _shot_movement_constraints(
    shot_profile: str,
    *,
    actor_motion_scale: float,
    actor_vertical_scale: float,
    actor_scale_gain: float,
    position_deadzone: float,
    scale_deadzone: float,
    scale_limit: float,
    body_angle_gain_x: float,
) -> dict[str, Any]:
    """Return effective Live2D transform constraints for a classified shot."""
    profile = str(shot_profile or "unknown")
    if profile == "face_closeup":
        return {
            "actor_transform_locked": True,
            "actor_motion_scale": 0.0,
            "actor_vertical_scale": 0.0,
            "actor_scale_gain": 0.0,
            "position_deadzone": max(float(position_deadzone), 0.10),
            "scale_deadzone": max(float(scale_deadzone), 0.20),
            "scale_limit": 0.0,
            "body_angle_gain_x": 0.0,
            "reason": "face_closeup_uses_face_parameters_only",
        }
    if profile == "upper_body":
        return {
            "actor_transform_locked": False,
            "actor_motion_scale": float(actor_motion_scale) * 0.35,
            "actor_vertical_scale": float(actor_vertical_scale) * 0.30,
            "actor_scale_gain": float(actor_scale_gain) * 0.25,
            "position_deadzone": max(float(position_deadzone), 0.06),
            "scale_deadzone": max(float(scale_deadzone), 0.12),
            "scale_limit": min(float(scale_limit), 0.02),
            "body_angle_gain_x": float(body_angle_gain_x) * 0.35,
            "reason": "upper_body_damps_actor_translation_and_zoom",
        }
    if profile == "full_body":
        return {
            "actor_transform_locked": False,
            "actor_motion_scale": float(actor_motion_scale),
            "actor_vertical_scale": float(actor_vertical_scale),
            "actor_scale_gain": float(actor_scale_gain),
            "position_deadzone": float(position_deadzone),
            "scale_deadzone": float(scale_deadzone),
            "scale_limit": float(scale_limit),
            "body_angle_gain_x": float(body_angle_gain_x),
            "reason": "full_body_allows_actor_translation_and_zoom",
        }
    return {
        "actor_transform_locked": False,
        "actor_motion_scale": float(actor_motion_scale),
        "actor_vertical_scale": float(actor_vertical_scale),
        "actor_scale_gain": float(actor_scale_gain),
        "position_deadzone": float(position_deadzone),
        "scale_deadzone": float(scale_deadzone),
        "scale_limit": float(scale_limit),
        "body_angle_gain_x": float(body_angle_gain_x),
        "reason": "wide_or_unknown_allows_actor_transform",
    }


def live2d_mocap_payload_from_frames(
    frames: Iterable[MocapFrame | Mapping[str, Any]],
    *,
    source_path: str | Path = "",
    duration_ms: int = 0,
    actor_motion_scale: float = 0.08,
    actor_vertical_scale: float = 0.05,
    actor_scale_gain: float = 0.05,
    position_deadzone: float = 0.04,
    scale_deadzone: float = 0.08,
    position_smoothing: float = 0.18,
    scale_smoothing: float = 0.10,
    scale_limit: float = 0.04,
    head_smoothing: float = 0.22,
    gaze_smoothing: float = 0.26,
    mouth_smoothing: float = 0.52,
    eye_open_smoothing: float = 0.42,
    head_deadzone: float = 0.012,
    gaze_deadzone: float = 0.035,
    breath_amount: float = 0.14,
    face_angle_gain_x: float = 38.0,
    face_angle_gain_y: float = 24.0,
    body_angle_gain_x: float = 6.0,
) -> dict[str, Any]:
    """Build a Live2D retarget payload from normalized face boxes.

    The exported video path is already closed by Live2D transform keyframes.
    Parameter-level keys are also preserved for the next renderer pass, where
    models that expose ParamAngleX/Y/Z, mouth, and eye parameters can consume
    them directly.
    """
    norm = _normalize_frames(frames)
    if not norm:
        return {
            "ok": False,
            "kind": "live2d_video_mocap",
            "source_path": str(source_path or ""),
            "duration_ms": max(0, int(duration_ms or 0)),
            "frames": [],
            "warning": "no_face_frames",
        }
    duration = max(int(duration_ms or 0), norm[-1].time_ms)
    shot = _classify_shot(norm)
    constraints = _shot_movement_constraints(
        str(shot.get("profile") or "unknown"),
        actor_motion_scale=actor_motion_scale,
        actor_vertical_scale=actor_vertical_scale,
        actor_scale_gain=actor_scale_gain,
        position_deadzone=position_deadzone,
        scale_deadzone=scale_deadzone,
        scale_limit=scale_limit,
        body_angle_gain_x=body_angle_gain_x,
    )
    sizes = [max(0.001, (f.w_norm + f.h_norm) * 0.5) for f in norm]
    base_size = max(0.001, float(median(sizes)))
    x_track = _smooth_series(
        [(frame.time_ms, frame.x_norm) for frame in norm],
        alpha=position_smoothing,
    )
    y_track = _smooth_series(
        [(frame.time_ms, frame.y_norm) for frame in norm],
        alpha=position_smoothing,
    )
    relative_size_track = _smooth_series(
        [(frame.time_ms, (size / base_size) - 1.0) for frame, size in zip(norm, sizes)],
        alpha=scale_smoothing,
        seed=0.0,
    )

    pos_x_values: list[tuple[int, float]] = []
    pos_y_values: list[tuple[int, float]] = []
    scale_values: list[tuple[int, float]] = []
    angle_x_values: list[tuple[int, float]] = []
    angle_y_values: list[tuple[int, float]] = []
    angle_z_values: list[tuple[int, float]] = []
    body_x_values: list[tuple[int, float]] = []
    body_y_values: list[tuple[int, float]] = []
    body_z_values: list[tuple[int, float]] = []

    head_yaw_track = _zero_deadzone_track(_optional_track(norm, "head_yaw", alpha=head_smoothing), radius=head_deadzone)
    head_pitch_track = _zero_deadzone_track(_optional_track(norm, "head_pitch", alpha=head_smoothing), radius=head_deadzone)
    head_roll_track = _zero_deadzone_track(_optional_track(norm, "head_roll", alpha=head_smoothing), radius=head_deadzone)
    gaze_x_track = _zero_deadzone_track(_optional_track(norm, "gaze_x", alpha=gaze_smoothing), radius=gaze_deadzone)
    gaze_y_track = _zero_deadzone_track(_optional_track(norm, "gaze_y", alpha=gaze_smoothing), radius=gaze_deadzone)
    mouth_open_track = _optional_track(norm, "mouth_open", alpha=mouth_smoothing)
    mouth_form_track = _optional_track(norm, "mouth_form", alpha=mouth_smoothing)
    eye_l_open_track = _optional_track(norm, "eye_l_open", alpha=eye_open_smoothing)
    eye_r_open_track = _optional_track(norm, "eye_r_open", alpha=eye_open_smoothing)
    head_yaw_by_time = _track_by_time(head_yaw_track)
    head_pitch_by_time = _track_by_time(head_pitch_track)
    head_roll_by_time = _track_by_time(head_roll_track)

    for frame, (_, x_norm), (_, y_norm), (_, relative_size) in zip(norm, x_track, y_track, relative_size_track):
        dx = _soft_deadzone(float(x_norm) - 0.5, float(constraints["position_deadzone"]))
        dy = _soft_deadzone(float(y_norm) - 0.5, float(constraints["position_deadzone"]))
        stable_relative_size = _clamp(
            _soft_deadzone(relative_size, float(constraints["scale_deadzone"])),
            -float(constraints["scale_limit"]),
            float(constraints["scale_limit"]),
        )
        if bool(constraints["actor_transform_locked"]):
            pos_x_values.append((frame.time_ms, 0.5))
            pos_y_values.append((frame.time_ms, 0.55))
            scale_values.append((frame.time_ms, 1.0))
        else:
            pos_x_values.append((frame.time_ms, _clamp(0.5 + dx * float(constraints["actor_motion_scale"]), 0.18, 0.82)))
            pos_y_values.append((frame.time_ms, _clamp(0.55 + dy * float(constraints["actor_vertical_scale"]), 0.18, 0.88)))
            scale_values.append((frame.time_ms, _clamp(1.0 + stable_relative_size * float(constraints["actor_scale_gain"]), 0.96, 1.04)))
        if frame.time_ms in head_yaw_by_time:
            angle_x_values.append((frame.time_ms, _clamp(float(head_yaw_by_time[frame.time_ms]) * 18.0, -18.0, 18.0)))
        else:
            angle_x_values.append((frame.time_ms, _clamp(dx * face_angle_gain_x, -18.0, 18.0)))
        if frame.time_ms in head_pitch_by_time:
            angle_y_values.append((frame.time_ms, _clamp(float(head_pitch_by_time[frame.time_ms]) * 12.0, -12.0, 12.0)))
        else:
            angle_y_values.append((frame.time_ms, _clamp(-dy * face_angle_gain_y, -12.0, 12.0)))
        if frame.time_ms in head_roll_by_time:
            angle_z_values.append((frame.time_ms, _clamp(float(head_roll_by_time[frame.time_ms]) * 18.0, -18.0, 18.0)))
        body_gain_x = float(constraints["body_angle_gain_x"])
        body_x_values.append((frame.time_ms, _clamp(dx * body_gain_x, -3.0, 3.0)))
        body_y_values.append((frame.time_ms, _clamp(-dy * body_gain_x * 0.65, -2.0, 2.0)))
        body_z_values.append((frame.time_ms, _clamp(stable_relative_size * body_gain_x * 0.75, -2.0, 2.0)))

    parameter_keyframes = {
        "ParamAngleX": _reduce_keyframes(angle_x_values, epsilon=1.2),
        "ParamAngleY": _reduce_keyframes(angle_y_values, epsilon=1.0),
        "ParamBodyAngleX": _reduce_keyframes(body_x_values, epsilon=0.8),
    }
    if angle_z_values:
        parameter_keyframes["ParamAngleZ"] = _reduce_keyframes(angle_z_values, epsilon=1.0)
    parameter_keyframes["ParamBodyAngleY"] = _reduce_keyframes(body_y_values, epsilon=0.7)
    parameter_keyframes["ParamBodyAngleZ"] = _reduce_keyframes(body_z_values, epsilon=0.7)
    parameter_keyframes["ParamBreath"] = _reduce_keyframes(_breath_track(norm, amplitude=breath_amount), epsilon=0.035, min_gap_ms=240)

    optional_params = [
        ("ParamEyeBallX", gaze_x_track, 0.05),
        ("ParamEyeBallY", gaze_y_track, 0.05),
        ("ParamMouthOpenY", mouth_open_track, 0.04),
        ("ParamMouthForm", mouth_form_track, 0.05),
        ("ParamEyeLOpen", eye_l_open_track, 0.05),
        ("ParamEyeROpen", eye_r_open_track, 0.05),
    ]
    for param_id, track, epsilon in optional_params:
        if track:
            parameter_keyframes[param_id] = _reduce_keyframes(track, epsilon=epsilon)
    eye_open_track = _average_tracks(eye_l_open_track, eye_r_open_track)
    if eye_open_track:
        parameter_keyframes["ParamEyeOpen"] = _reduce_keyframes(eye_open_track, epsilon=0.05)
        parameter_keyframes["ParamEyeBlink"] = _reduce_keyframes(_blink_from_eye_open(eye_open_track), epsilon=0.05)
    detail_parameter_ids = [
        param_id
        for param_id in (
            "ParamAngleZ",
            "ParamBodyAngleY",
            "ParamBodyAngleZ",
            "ParamBreath",
            "ParamEyeBallX",
            "ParamEyeBallY",
            "ParamMouthOpenY",
            "ParamMouthForm",
            "ParamEyeLOpen",
            "ParamEyeROpen",
            "ParamEyeOpen",
            "ParamEyeBlink",
        )
        if parameter_keyframes.get(param_id)
    ]
    mouth_eye_parameter_ids = [
        param_id
        for param_id in (
            "ParamEyeBallX",
            "ParamEyeBallY",
            "ParamMouthOpenY",
            "ParamMouthForm",
            "ParamEyeLOpen",
            "ParamEyeROpen",
            "ParamEyeOpen",
            "ParamEyeBlink",
        )
        if parameter_keyframes.get(param_id)
    ]
    transform_keyframes = {
        "pos_x": _reduce_keyframes(pos_x_values, epsilon=0.006),
        "pos_y": _reduce_keyframes(pos_y_values, epsilon=0.006),
        "scale": _reduce_keyframes(scale_values, epsilon=0.01),
    }
    return {
        "ok": True,
        "kind": "live2d_video_mocap",
        "source_path": str(source_path or ""),
        "duration_ms": int(duration),
        "sample_count": len(norm),
        "face_coverage": round(len(norm) / max(1, len(norm)), 4),
        "backend": "opencv_haar_face",
        "retargeting": {
            "profile": "talking_head_stabilized",
            "shot_profile": str(shot.get("profile") or "unknown"),
            "shot_confidence": round(float(shot.get("confidence", 0.0) or 0.0), 4),
            "shot_classification": shot,
            "movement_constraints": {
                "actor_transform_locked": bool(constraints["actor_transform_locked"]),
                "reason": str(constraints["reason"]),
            },
            "base_face_size": round(float(base_size), 5),
            "position_deadzone": round(float(constraints["position_deadzone"]), 5),
            "scale_deadzone": round(float(constraints["scale_deadzone"]), 5),
            "position_smoothing": round(float(position_smoothing), 5),
            "scale_smoothing": round(float(scale_smoothing), 5),
            "head_smoothing": round(float(head_smoothing), 5),
            "gaze_smoothing": round(float(gaze_smoothing), 5),
            "mouth_smoothing": round(float(mouth_smoothing), 5),
            "eye_open_smoothing": round(float(eye_open_smoothing), 5),
            "head_deadzone": round(float(head_deadzone), 5),
            "gaze_deadzone": round(float(gaze_deadzone), 5),
            "breath_amount": round(float(breath_amount), 5),
            "actor_motion_scale": round(float(constraints["actor_motion_scale"]), 5),
            "actor_vertical_scale": round(float(constraints["actor_vertical_scale"]), 5),
            "actor_scale_gain": round(float(constraints["actor_scale_gain"]), 5),
            "scale_limit": round(float(constraints["scale_limit"]), 5),
            "face_angle_gain_x": round(float(face_angle_gain_x), 5),
            "face_angle_gain_y": round(float(face_angle_gain_y), 5),
            "body_angle_gain_x": round(float(constraints["body_angle_gain_x"]), 5),
            "detail_parameter_tracks": detail_parameter_ids,
        },
        "capabilities": {
            "face_bbox": True,
            "person_bbox": any(frame.person_w_norm > 0.0 and frame.person_h_norm > 0.0 for frame in norm),
            "actor_transform": True,
            "live2d_parameter_payload": True,
            "hand_gesture": False,
            "mouth_eye_detail": bool(mouth_eye_parameter_ids),
            "webcam_realtime": False,
            "video_file_offline": True,
        },
        "frames": [frame.to_dict() for frame in norm[:900]],
        "transform_keyframes": transform_keyframes,
        "parameter_keyframes": parameter_keyframes,
        "events": [
            {
                "time_ms": int(norm[0].time_ms),
                "kind": "face_acquired",
                "confidence": round(float(norm[0].confidence), 4),
            },
            {
                "time_ms": int(norm[0].time_ms),
                "kind": "shot_profile_classified",
                "profile": str(shot.get("profile") or "unknown"),
                "confidence": round(float(shot.get("confidence", 0.0) or 0.0), 4),
            }
        ]
        + (
            [
                {
                    "time_ms": int(norm[0].time_ms),
                    "kind": "face_detail_parameters_acquired",
                    "parameters": mouth_eye_parameter_ids,
                }
            ]
            if mouth_eye_parameter_ids
            else []
        ),
        "warning": "",
    }


def apply_live2d_mocap_payload_to_clip(
    clip: Any,
    payload: Mapping[str, Any],
    *,
    fit_duration: bool = True,
) -> dict[str, Any]:
    """Apply a mocap payload to a Live2DActorClip.

    Current renderer support: transform keyframes are baked into preview/export,
    and ``mocap_parameter_keyframes`` are applied after authored motion updates
    so face/gesture retargeting can layer on top of a selected Live2D motion.
    """
    if clip is None:
        return {"ok": False, "reason": "missing_clip"}
    if not bool(payload.get("ok")):
        return {"ok": False, "reason": str(payload.get("warning") or "invalid_payload")}
    from app.live2d.actor_track import Live2DKeyframe

    transforms = dict(payload.get("transform_keyframes") or {})

    def _to_kfs(name: str) -> list[Live2DKeyframe]:
        out: list[Live2DKeyframe] = []
        for row in list(transforms.get(name) or []):
            if not isinstance(row, Mapping):
                continue
            out.append(
                Live2DKeyframe(
                    time_ms=max(0, int(row.get("time_ms", 0) or 0)),
                    value=float(row.get("value", 0.0) or 0.0),
                    curve=str(row.get("curve", "smoothstep") or "smoothstep"),
                )
            )
        return out

    clip.kf_pos_x = _to_kfs("pos_x")
    clip.kf_pos_y = _to_kfs("pos_y")
    clip.kf_scale = _to_kfs("scale")
    if fit_duration:
        duration = int(payload.get("duration_ms", 0) or 0)
        if duration > 0:
            clip.duration_ms = max(int(getattr(clip, "duration_ms", 0) or 0), duration)
    clip.mocap_source_path = str(payload.get("source_path") or "")
    clip.mocap_backend = str(payload.get("backend") or "")
    clip.mocap_payload = dict(payload)
    clip.mocap_parameter_keyframes = dict(payload.get("parameter_keyframes") or {})
    clip.mocap_events = list(payload.get("events") or [])
    retargeting = dict(payload.get("retargeting") or {})
    constraints = dict(retargeting.get("movement_constraints") or {})
    try:
        from app.live2d.performance_source_bridge import normalize_performance_subject_type

        clip.mocap_subject_type = normalize_performance_subject_type(retargeting.get("shot_profile")) or "unknown"
        clip.mocap_movement_constraints = constraints
    except Exception:
        try:
            clip.mocap_subject_type = str(retargeting.get("shot_profile") or "unknown")
            clip.mocap_movement_constraints = constraints
        except Exception:
            pass
    return {
        "ok": True,
        "duration_ms": int(getattr(clip, "duration_ms", 0) or 0),
        "sample_count": int(payload.get("sample_count", 0) or 0),
        "pos_keys": len(clip.kf_pos_x),
        "scale_keys": len(clip.kf_scale),
        "parameter_tracks": len(clip.mocap_parameter_keyframes),
        "shot_profile": str(retargeting.get("shot_profile") or "unknown"),
        "subject_type": str(getattr(clip, "mocap_subject_type", "") or "unknown"),
        "actor_transform_locked": bool(
            constraints.get("actor_transform_locked")
            if isinstance(constraints, Mapping)
            else False
        ),
    }


def live2d_mocap_user_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return an operator-facing diagnosis for a Live2D video mocap payload."""
    if not bool(payload.get("ok")):
        reason = str(payload.get("warning") or "invalid_payload")
        return {
            "ok": False,
            "status_line": f"Motion analysis failed: {reason}",
            "movement_mode": "unavailable",
            "warnings": [reason],
        }
    retargeting = dict(payload.get("retargeting") or {})
    constraints = dict(retargeting.get("movement_constraints") or {})
    profile = str(retargeting.get("shot_profile") or "unknown")
    locked = bool(constraints.get("actor_transform_locked"))
    parameter_keyframes = dict(payload.get("parameter_keyframes") or {})
    transform_keyframes = dict(payload.get("transform_keyframes") or {})
    detail_tracks = [str(item) for item in list(retargeting.get("detail_parameter_tracks") or [])]
    confidence = float(retargeting.get("shot_confidence", 0.0) or 0.0)

    has_head = bool(parameter_keyframes.get("ParamAngleX") or parameter_keyframes.get("ParamAngleY"))
    has_eye = bool(parameter_keyframes.get("ParamEyeBallX") or parameter_keyframes.get("ParamEyeBallY"))
    has_mouth = bool(parameter_keyframes.get("ParamMouthOpenY") or parameter_keyframes.get("ParamMouthForm"))
    has_blink = bool(
        parameter_keyframes.get("ParamEyeLOpen")
        or parameter_keyframes.get("ParamEyeROpen")
        or parameter_keyframes.get("ParamEyeOpen")
        or parameter_keyframes.get("ParamEyeBlink")
    )
    has_transform = bool(
        transform_keyframes.get("pos_x")
        or transform_keyframes.get("pos_y")
        or transform_keyframes.get("scale")
    )

    driven_channels: list[str] = []
    if has_transform and not locked:
        driven_channels.append("actor position/scale")
    if has_head:
        driven_channels.append("head angle")
    if has_eye:
        driven_channels.append("eye gaze")
    if has_mouth:
        driven_channels.append("mouth")
    if has_blink:
        driven_channels.append("eye open")

    warnings: list[str] = []
    if not has_mouth:
        warnings.append("mouth detail unavailable; lip motion uses head/face motion only")
    if not has_eye:
        warnings.append("eye gaze detail unavailable; gaze uses model defaults")

    if locked:
        movement_mode = "face_only_locked_transform"
        movement_label = "Face close-up: actor position/scale locked"
        movement_note = "Only head, eye, and mouth parameters are driven so talking-head footage does not make the actor drift or zoom."
    elif profile == "upper_body":
        movement_mode = "upper_body_damped_transform"
        movement_label = "Upper body: actor movement damped"
        movement_note = "Body translation and zoom are limited while face parameters stay active."
    elif profile == "full_body":
        movement_mode = "full_body_transform_enabled"
        movement_label = "Full body: actor movement enabled"
        movement_note = "Actor position and scale can follow the detected body framing."
    else:
        movement_mode = "unknown_transform_enabled"
        movement_label = "Unknown shot: conservative actor movement"
        movement_note = "Actor movement is allowed, but detector confidence should be reviewed."

    channel_text = ", ".join(driven_channels) if driven_channels else "no parameter tracks"
    return {
        "ok": True,
        "shot_profile": profile,
        "shot_confidence": round(confidence, 4),
        "movement_mode": movement_mode,
        "movement_label": movement_label,
        "movement_note": movement_note,
        "actor_transform_locked": locked,
        "driven_channels": driven_channels,
        "detail_tracks": detail_tracks,
        "parameter_track_count": len(parameter_keyframes),
        "sample_count": int(payload.get("sample_count", 0) or 0),
        "duration_ms": int(payload.get("duration_ms", 0) or 0),
        "warnings": warnings,
        "status_line": f"{movement_label}; drives {channel_text}",
    }


def analyze_video_file_for_live2d_mocap(
    source_path: str | Path,
    *,
    sample_fps: float = 12.0,
    max_samples: int = 1800,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Analyze a local video with OpenCV and return a Live2D mocap payload."""
    path = Path(source_path)
    if not path.exists():
        return {"ok": False, "kind": "live2d_video_mocap", "source_path": str(path), "warning": "missing_source"}
    try:
        import cv2  # type: ignore
    except Exception:
        return {"ok": False, "kind": "live2d_video_mocap", "source_path": str(path), "warning": "opencv_unavailable"}

    cap = cv2.VideoCapture(str(path))
    if not cap or not cap.isOpened():
        return {"ok": False, "kind": "live2d_video_mocap", "source_path": str(path), "warning": "video_open_failed"}
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_ms = int(round(frame_count / fps * 1000.0)) if frame_count > 0 else 0
        step = max(1, int(round(fps / max(1.0, float(sample_fps)))))
        total_samples = min(max_samples, max(1, frame_count // step if frame_count > 0 else max_samples))
        cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            return {"ok": False, "kind": "live2d_video_mocap", "source_path": str(path), "warning": "face_cascade_unavailable"}

        person_detector = None
        try:
            person_detector = cv2.HOGDescriptor()
            person_detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        except Exception:
            person_detector = None
        face_mesh = None
        face_detail_backend = ""
        try:
            import mediapipe as mp  # type: ignore

            face_mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            face_detail_backend = "mediapipe_face_mesh"
        except Exception:
            face_mesh = None
            face_detail_backend = ""

        frames: list[MocapFrame] = []
        idx = 0
        sampled = 0
        person_sample_stride = max(2, int(round(float(sample_fps) / 3.0)))
        last_person_box: tuple[int, int, int, int] | None = None
        last_person_age = person_sample_stride + 1
        person_detection_frames = 0
        face_detail_frames = 0
        while sampled < max_samples:
            ok = cap.grab()
            if not ok:
                break
            if idx % step != 0:
                idx += 1
                continue
            ok, frame = cap.retrieve()
            if not ok or frame is None:
                idx += 1
                continue
            h, w = frame.shape[:2]
            if w <= 0 or h <= 0:
                idx += 1
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(max(24, w // 40), max(24, h // 40)),
            )
            face_detail = _extract_face_mesh_detail(frame, cv2, face_mesh)
            if face_detail is not None:
                face_detail_frames += 1
            if face_detail is not None or len(faces) > 0:
                if face_detail is not None:
                    fw = max(1, int(round(float(face_detail.get("w_norm", 0.0)) * float(w))))
                    fh = max(1, int(round(float(face_detail.get("h_norm", 0.0)) * float(h))))
                    x = int(round((float(face_detail.get("x_norm", 0.5)) * float(w)) - fw * 0.5))
                    y = int(round((float(face_detail.get("y_norm", 0.5)) * float(h)) - fh * 0.5))
                    x = max(0, min(w - 1, x))
                    y = max(0, min(h - 1, y))
                    face_x_norm = _clamp(float(face_detail.get("x_norm", 0.5)), 0.0, 1.0)
                    face_y_norm = _clamp(float(face_detail.get("y_norm", 0.5)), 0.0, 1.0)
                    face_w_norm = _clamp(float(face_detail.get("w_norm", 0.0)), 0.0, 1.0)
                    face_h_norm = _clamp(float(face_detail.get("h_norm", 0.0)), 0.0, 1.0)
                    face_confidence = _clamp(float(face_detail.get("confidence", 0.92)), 0.0, 1.0)
                    detail_kwargs = {
                        key: float(value)
                        for key, value in face_detail.items()
                        if key
                        in {
                            "head_yaw",
                            "head_pitch",
                            "head_roll",
                            "gaze_x",
                            "gaze_y",
                            "mouth_open",
                            "mouth_form",
                            "eye_l_open",
                            "eye_r_open",
                        }
                    }
                else:
                    x, y, fw, fh = max(faces, key=lambda box: int(box[2]) * int(box[3]))
                    area_ratio = (float(fw) * float(fh)) / max(1.0, float(w) * float(h))
                    face_x_norm = _clamp((float(x) + float(fw) * 0.5) / float(w), 0.0, 1.0)
                    face_y_norm = _clamp((float(y) + float(fh) * 0.5) / float(h), 0.0, 1.0)
                    face_w_norm = _clamp(float(fw) / float(w), 0.0, 1.0)
                    face_h_norm = _clamp(float(fh) / float(h), 0.0, 1.0)
                    face_confidence = _clamp(0.55 + area_ratio * 12.0, 0.0, 1.0)
                    detail_kwargs = {}
                person_box: tuple[int, int, int, int] | None = None
                if person_detector is not None and sampled % person_sample_stride == 0:
                    detect_scale = 1.0
                    detect_frame = frame
                    if h > 360:
                        detect_scale = 360.0 / float(h)
                        detect_frame = cv2.resize(
                            frame,
                            (max(1, int(round(w * detect_scale))), 360),
                            interpolation=cv2.INTER_AREA,
                        )
                    try:
                        persons, weights = person_detector.detectMultiScale(
                            detect_frame,
                            winStride=(8, 8),
                            padding=(8, 8),
                            scale=1.05,
                        )
                    except Exception:
                        persons = []
                        weights = []
                    mapped_persons: list[tuple[int, int, int, int, float]] = []
                    for i, box in enumerate(persons):
                        px, py, pw, ph = [int(v) for v in box[:4]]
                        if detect_scale != 1.0:
                            inv = 1.0 / detect_scale
                            px = int(round(px * inv))
                            py = int(round(py * inv))
                            pw = int(round(pw * inv))
                            ph = int(round(ph * inv))
                        if pw <= 0 or ph <= 0:
                            continue
                        weight = float(weights[i]) if i < len(weights) else 0.0
                        mapped_persons.append((px, py, pw, ph, weight))
                    if mapped_persons:
                        face_cx = float(x) + float(fw) * 0.5
                        face_cy = float(y) + float(fh) * 0.5

                        def _person_score(row: tuple[int, int, int, int, float]) -> float:
                            px, py, pw, ph, weight = row
                            contains_x = float(px) - pw * 0.12 <= face_cx <= float(px + pw) + pw * 0.12
                            head_band = float(py) - ph * 0.05 <= face_cy <= float(py) + ph * 0.45
                            score = float(pw) * float(ph) / max(1.0, float(w) * float(h)) + weight * 0.02
                            if contains_x:
                                score += 0.20
                            if head_band:
                                score += 0.20
                            return score

                        bx, by, bw, bh, _ = max(mapped_persons, key=_person_score)
                        person_box = (
                            max(0, min(w - 1, int(bx))),
                            max(0, min(h - 1, int(by))),
                            max(1, min(w, int(bw))),
                            max(1, min(h, int(bh))),
                        )
                        last_person_box = person_box
                        last_person_age = 0
                    else:
                        last_person_box = None
                        last_person_age = person_sample_stride + 1
                elif last_person_box is not None and last_person_age <= person_sample_stride:
                    person_box = last_person_box
                    last_person_age += 1
                person_kwargs: dict[str, float] = {}
                if person_box is not None:
                    px, py, pw, ph = person_box
                    person_kwargs = {
                        "person_x_norm": _clamp((float(px) + float(pw) * 0.5) / float(w), 0.0, 1.0),
                        "person_y_norm": _clamp((float(py) + float(ph) * 0.5) / float(h), 0.0, 1.0),
                        "person_w_norm": _clamp(float(pw) / float(w), 0.0, 1.0),
                        "person_h_norm": _clamp(float(ph) / float(h), 0.0, 1.0),
                    }
                    person_detection_frames += 1
                frames.append(
                    MocapFrame(
                        time_ms=int(round(idx / fps * 1000.0)),
                        x_norm=face_x_norm,
                        y_norm=face_y_norm,
                        w_norm=face_w_norm,
                        h_norm=face_h_norm,
                        confidence=face_confidence,
                        **person_kwargs,
                        **detail_kwargs,
                    )
                )
            sampled += 1
            if callable(progress):
                progress(sampled, total_samples)
            idx += 1
    finally:
        try:
            cap.release()
        except Exception:
            pass
        try:
            if "face_mesh" in locals() and face_mesh is not None:
                face_mesh.close()
        except Exception:
            pass

    payload = live2d_mocap_payload_from_frames(frames, source_path=path, duration_ms=duration_ms)
    if "face_detail_frames" in locals() and int(face_detail_frames) > 0:
        payload["backend"] = "mediapipe_face_mesh+opencv"
    payload["video_probe"] = {
        "fps": round(float(fps), 4) if "fps" in locals() else 0.0,
        "frame_count": int(frame_count) if "frame_count" in locals() else 0,
        "sample_fps": float(sample_fps),
        "sampled_frames": int(sampled) if "sampled" in locals() else 0,
        "person_detector": "opencv_hog" if "person_detector" in locals() and person_detector is not None else "",
        "person_detection_frames": int(person_detection_frames) if "person_detection_frames" in locals() else 0,
        "face_detail_detector": str(face_detail_backend) if "face_detail_backend" in locals() else "",
        "face_detail_frames": int(face_detail_frames) if "face_detail_frames" in locals() else 0,
    }
    if not payload.get("ok") and frames == []:
        payload["warning"] = "no_face_detected"
    return payload
