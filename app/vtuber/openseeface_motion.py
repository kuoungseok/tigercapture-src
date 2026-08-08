"""Convert OpenSeeFace CSV tracking logs into TigerCapture motion frames."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from app.vtuber.video_face_driver import FaceMotionFrame
from app.vtuber.source_framing import frame_size_from_openseeface_rows


OPENSEEFACE_MOTION_SCHEMA = "tigerstudio.vtuber.openseeface_motion.v1"


@dataclass(frozen=True)
class OpenSeeFaceMotionTuning:
    # OpenSeeFace's raw Euler deltas are physically conservative. On a stylized
    # VRM head they read almost static in broadcast framing, so the default
    # bridge tuning keeps the sign intact but makes subtle face turns visible.
    pitch_scale: float = 2.75
    yaw_scale: float = 1.75
    roll_scale: float = 1.35
    shoulder_roll_scale: float = 1.0
    mouth_scale: float = 1.0
    neutral_frames: int = 3


def load_openseeface_motion_csv(
    path: str | Path,
    *,
    tuning: OpenSeeFaceMotionTuning | None = None,
    max_frames: int | None = None,
) -> tuple[FaceMotionFrame, ...]:
    """Load facetracker ``--log-data`` CSV rows as relative face motion."""
    csv_path = Path(path)
    if not csv_path.is_file():
        return ()
    cfg = tuning or OpenSeeFaceMotionTuning()
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if not row:
                continue
            rows.append(row)
            if max_frames is not None and len(rows) >= max(1, int(max_frames)):
                break
    return frames_from_openseeface_rows(rows, tuning=cfg)


def load_openseeface_frame_size_csv(path: str | Path) -> tuple[int, int] | None:
    """Return the tracked video frame size recorded by OpenSeeFace, if present."""
    csv_path = Path(path)
    if not csv_path.is_file():
        return None
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row:
                rows.append(row)
                break
    return frame_size_from_openseeface_rows(rows)


def frames_from_openseeface_rows(
    rows: Iterable[dict[str, Any]],
    *,
    tuning: OpenSeeFaceMotionTuning | None = None,
) -> tuple[FaceMotionFrame, ...]:
    data = [row for row in rows if _truthy(row.get("Success3D", True))]
    if not data:
        return ()
    cfg = tuning or OpenSeeFaceMotionTuning()
    neutral_count = max(1, min(len(data), int(cfg.neutral_frames)))
    base_pitch = _mean(_float(row.get("Euler.X")) for row in data[:neutral_count])
    base_yaw = _mean(_float(row.get("Euler.Y")) for row in data[:neutral_count])
    base_roll = _mean(_float(row.get("Euler.Z")) for row in data[:neutral_count])
    base_shoulder_roll = _mean(_optional_shoulder_roll(row, 0.0) for row in data[:neutral_count])
    first_time = _float(data[0].get("Time"))
    frames: list[FaceMotionFrame] = []
    for index, row in enumerate(data):
        time_ms = _relative_time_ms(row, index, first_time)
        pitch = _clamp(_angle_delta(_float(row.get("Euler.X")), base_pitch) * cfg.pitch_scale, -35.0, 35.0)
        yaw = _clamp(_angle_delta(_float(row.get("Euler.Y")), base_yaw) * cfg.yaw_scale, -45.0, 45.0)
        roll = _clamp(_angle_delta(_float(row.get("Euler.Z")), base_roll) * cfg.roll_scale, -30.0, 30.0)
        shoulder_roll = _clamp(
            _angle_delta(_optional_shoulder_roll(row, base_shoulder_roll), base_shoulder_roll) * cfg.shoulder_roll_scale,
            -25.0,
            25.0,
        )
        mouth = _clamp01(max(0.0, _float(row.get("mouth_open"))) * cfg.mouth_scale)
        blink_l = _clamp01(1.0 - _float(row.get("LeftOpen"), 1.0))
        blink_r = _clamp01(1.0 - _float(row.get("RightOpen"), 1.0))
        confidence = _clamp01(_float(row.get("AverageConfidence"), 0.0))
        frames.append(
            FaceMotionFrame(
                time_ms=time_ms,
                yaw_deg=yaw,
                pitch_deg=pitch,
                roll_deg=roll,
                shoulder_roll_deg=shoulder_roll,
                mouth_open=mouth,
                blink_l=blink_l,
                blink_r=blink_r,
                confidence=confidence,
                face_box=_face_box_from_landmarks(row),
                chin_offset_x_norm=_chin_offset_x_from_landmarks(row),
                source="openseeface_csv",
            )
        )
    return tuple(frames)


def summarize_openseeface_motion(frames: Iterable[FaceMotionFrame]) -> dict[str, Any]:
    data = tuple(frames)
    if not data:
        return {
            "schema": OPENSEEFACE_MOTION_SCHEMA,
            "ok": False,
            "frame_count": 0,
            "drives_vrm_pose": False,
            "driven_channels": [],
        }
    driven = []
    if _range(frame.yaw_deg for frame in data) >= 0.5 or _range(frame.pitch_deg for frame in data) >= 0.5 or _range(frame.roll_deg for frame in data) >= 0.5:
        driven.extend(["Head", "Neck", "Chest"])
    if _range(frame.shoulder_roll_deg for frame in data) >= 0.5:
        driven.extend(["Spine", "Chest", "UpperChest"])
    if max(frame.mouth_open for frame in data) > 0.05:
        driven.append("BlendShape:A")
    if max(max(frame.blink_l, frame.blink_r) for frame in data) > 0.05:
        driven.extend(["BlendShape:Blink_L", "BlendShape:Blink_R"])
    return {
        "schema": OPENSEEFACE_MOTION_SCHEMA,
        "ok": True,
        "frame_count": len(data),
        "time_min_ms": min(frame.time_ms for frame in data),
        "time_max_ms": max(frame.time_ms for frame in data),
        "drives_vrm_pose": bool(driven),
        "driven_channels": driven,
        "yaw_range": _range(frame.yaw_deg for frame in data),
        "pitch_range": _range(frame.pitch_deg for frame in data),
        "roll_range": _range(frame.roll_deg for frame in data),
        "shoulder_roll_range": _range(frame.shoulder_roll_deg for frame in data),
        "mouth_max": max(frame.mouth_open for frame in data),
        "blink_max": max(max(frame.blink_l, frame.blink_r) for frame in data),
        "confidence_mean": sum(frame.confidence for frame in data) / len(data),
        "chin_offset_x_norm_mean": sum(frame.chin_offset_x_norm for frame in data) / len(data),
        "chin_offset_x_norm_min": min(frame.chin_offset_x_norm for frame in data),
        "chin_offset_x_norm_max": max(frame.chin_offset_x_norm for frame in data),
        "chin_left_frames": sum(1 for frame in data if frame.chin_offset_x_norm < -0.05),
        "chin_right_frames": sum(1 for frame in data if frame.chin_offset_x_norm > 0.05),
    }


def _relative_time_ms(row: dict[str, Any], index: int, first_time: float) -> int:
    fps = _float(row.get("FPS"), 0.0)
    if fps > 0.0:
        frame_number = _float(row.get("Frame"), float(index + 1))
        return max(0, int(round((frame_number - 1.0) * 1000.0 / fps)))
    current_time = _float(row.get("Time"), first_time)
    return max(0, int(round((current_time - first_time) * 1000.0)))


def _face_box_from_landmarks(row: dict[str, Any]) -> tuple[int, int, int, int] | None:
    xs: list[float] = []
    ys: list[float] = []
    for index in range(66):
        x_key = f"Landmark[{index}].X"
        y_key = f"Landmark[{index}].Y"
        if x_key in row and y_key in row:
            xs.append(_float(row.get(x_key)))
            ys.append(_float(row.get(y_key)))
    if not xs or not ys:
        return None
    left, right = min(xs), max(xs)
    top, bottom = min(ys), max(ys)
    return (
        int(round(left)),
        int(round(top)),
        max(1, int(round(right - left))),
        max(1, int(round(bottom - top))),
    )


def _chin_offset_x_from_landmarks(row: dict[str, Any]) -> float:
    xs: list[float] = []
    for index in range(66):
        x_key = f"Landmark[{index}].X"
        if x_key in row:
            xs.append(_float(row.get(x_key)))
    if not xs:
        return 0.0
    chin_key = "Landmark[8].X"
    if chin_key not in row:
        return 0.0
    left, right = min(xs), max(xs)
    width = max(1.0, right - left)
    center_x = (left + right) * 0.5
    return _clamp((_float(row.get(chin_key)) - center_x) / width, -1.0, 1.0)


def _optional_shoulder_roll(row: dict[str, Any], default: float) -> float:
    for key in ("shoulder_roll_deg", "ShoulderRollDeg", "Shoulder.Roll", "torso_roll_deg", "TorsoRollDeg"):
        if key in row and str(row.get(key) or "").strip():
            return _float(row.get(key), default)
    return float(default)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() not in {"", "0", "false", "no", "none"}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _mean(values: Iterable[float]) -> float:
    data = list(values)
    return sum(data) / len(data) if data else 0.0


def _angle_delta(value: float, baseline: float) -> float:
    delta = float(value) - float(baseline)
    while delta > 180.0:
        delta -= 360.0
    while delta < -180.0:
        delta += 360.0
    return delta


def _range(values: Iterable[float]) -> float:
    data = list(values)
    return max(data) - min(data) if data else 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)
