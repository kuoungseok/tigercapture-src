"""Map source face framing to VRM preview camera framing."""
from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from app.vtuber.video_face_driver import FaceMotionFrame


SOURCE_FRAMING_SCHEMA = "tigerstudio.vtuber.source_framing.v1"
SOURCE_TO_VRM_VISIBILITY_POLICY_SCHEMA = "tigerstudio.vtuber.source_to_vrm_visibility_policy.v1"
SOURCE_EXPOSURE_SCHEMA = "tigerstudio.vtuber.source_exposure_classification.v1"
SOURCE_EXPOSURE_TYPES = frozenset({"face_only", "chest_up", "upper_body", "full_body", "unknown"})
PRESET_ORDER = {"bust_up": 0, "half_body": 1, "full_body": 2}
PRESET_VISIBILITY = {
    "bust_up": "head_to_mid_chest",
    "half_body": "head_to_waist",
    "full_body": "head_to_toe",
}


@dataclass(frozen=True)
class SourceFramingPreset:
    name: str = "bust_up"
    reference_face_height: float = 0.285
    reference_face_center_y: float = 0.39
    base_zoom: float = 7.1
    base_camera_z: float = 3.25
    base_pan_y: float = -1.7
    base_camera_pitch_deg: float = -5.0
    reference_subject_height: float = 0.72
    horizontal_pan_scale: float = 2.05
    vertical_pan_scale: float = 2.05
    zoom_power: float = 0.88
    subject_tracking_weight: float = 0.16
    shoulder_width_scale: float = 2.75
    upper_body_height_scale: float = 2.45
    upper_body_top_face_scale: float = 0.52
    lower_occlusion_y: float = 0.68
    min_zoom: float = 1.2
    max_zoom: float = 10.0
    min_camera_pitch_deg: float = -10.0
    max_camera_pitch_deg: float = 6.0


@dataclass(frozen=True)
class SourceFramingSolution:
    ok: bool
    time_ms: int = 0
    preset: str = "bust_up"
    model_view: Mapping[str, float | bool] | None = None
    track_rotation: tuple[float, float, float] = (-4.0, 180.0, 0.0)
    source_face_center: tuple[float, float] | None = None
    source_face_size: tuple[float, float] | None = None
    source_subject_center: tuple[float, float] | None = None
    source_subject_size: tuple[float, float] | None = None
    diagnostics: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_FRAMING_SCHEMA,
            "ok": bool(self.ok),
            "time_ms": int(self.time_ms),
            "preset": self.preset,
            "model_view": dict(self.model_view or {}),
            "track_rotation": [float(v) for v in self.track_rotation],
            "source_face_center": list(self.source_face_center) if self.source_face_center else None,
            "source_face_size": list(self.source_face_size) if self.source_face_size else None,
            "source_subject_center": list(self.source_subject_center) if self.source_subject_center else None,
            "source_subject_size": list(self.source_subject_size) if self.source_subject_size else None,
            "diagnostics": dict(self.diagnostics or {}),
        }


PRESETS: dict[str, SourceFramingPreset] = {
    "bust_up": SourceFramingPreset(),
    "half_body": SourceFramingPreset(
        name="half_body",
        reference_face_height=0.205,
        reference_face_center_y=0.33,
        reference_subject_height=0.90,
        base_zoom=3.15,
        base_pan_y=-0.82,
        base_camera_pitch_deg=-3.5,
        subject_tracking_weight=0.38,
        upper_body_height_scale=3.75,
        lower_occlusion_y=0.88,
        min_zoom=0.9,
        max_zoom=5.4,
    ),
    "full_body": SourceFramingPreset(
        name="full_body",
        reference_face_height=0.115,
        reference_face_center_y=0.24,
        reference_subject_height=0.96,
        base_zoom=1.75,
        base_pan_y=-0.20,
        base_camera_pitch_deg=-2.0,
        subject_tracking_weight=0.50,
        upper_body_height_scale=6.8,
        lower_occlusion_y=1.0,
        min_zoom=0.55,
        max_zoom=3.5,
    ),
}


def normalize_source_exposure_type(value: Any = "", payload: Mapping[str, Any] | None = None) -> str:
    """Normalize detector/AI labels into the public source exposure contract."""
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if not text and isinstance(payload, Mapping):
        for key in (
            "source_exposure",
            "source_exposure_type",
            "subject_type",
            "shot_profile",
            "profile",
            "framing",
            "framing_preset",
        ):
            if payload.get(key):
                text = str(payload.get(key) or "").strip().casefold().replace("-", "_").replace(" ", "_")
                break
    aliases = {
        "face": "face_only",
        "face_only": "face_only",
        "face_closeup": "face_only",
        "closeup": "face_only",
        "close_up": "face_only",
        "talking_head": "face_only",
        "head": "face_only",
        "head_only": "face_only",
        "bust": "chest_up",
        "bust_up": "chest_up",
        "chest": "chest_up",
        "chest_up": "chest_up",
        "mid_chest": "chest_up",
        "head_and_shoulders": "chest_up",
        "upper": "upper_body",
        "upper_body": "upper_body",
        "half": "upper_body",
        "half_body": "upper_body",
        "seated": "upper_body",
        "torso": "upper_body",
        "waist": "upper_body",
        "waist_up": "upper_body",
        "full": "full_body",
        "fullbody": "full_body",
        "full_body": "full_body",
        "standing": "full_body",
        "whole_body": "full_body",
        "body": "full_body",
        "unknown": "unknown",
        "full_body_or_wide": "unknown",
        "wide": "unknown",
        "wide_shot": "unknown",
        "none": "unknown",
    }
    return aliases.get(text, text if text in SOURCE_EXPOSURE_TYPES else "unknown")


def vrm_visibility_policy_for_source_exposure(
    source_exposure: Any = "",
    *,
    requested_preset: str = "auto",
    allow_narrower: bool = False,
    confidence: float = 0.0,
    method: str = "",
) -> dict[str, Any]:
    """Return the minimum VRM framing needed to match the source person exposure."""
    exposure = normalize_source_exposure_type(source_exposure)
    minimum = {
        "face_only": "bust_up",
        "chest_up": "bust_up",
        "upper_body": "half_body",
        "full_body": "full_body",
        "unknown": "bust_up",
    }.get(exposure, "bust_up")
    requested = normalize_vrm_framing_preset(requested_preset)
    selected = requested if requested else minimum
    upgraded = False
    if not selected or PRESET_ORDER.get(selected, 0) < PRESET_ORDER.get(minimum, 0):
        selected = minimum
        upgraded = True
    if allow_narrower and requested:
        selected = requested
        upgraded = False
    return {
        "schema": SOURCE_TO_VRM_VISIBILITY_POLICY_SCHEMA,
        "ai_rule": "match_source_person_exposure_to_vrm_visibility",
        "source_exposure": exposure,
        "source_exposure_confidence": round(float(confidence or 0.0), 4),
        "source_exposure_method": str(method or ""),
        "requested_framing_preset": requested or "auto",
        "minimum_framing_preset": minimum,
        "selected_framing_preset": selected,
        "upgraded_from_requested": bool(upgraded),
        "allow_narrower_than_source": bool(allow_narrower),
        "minimum_avatar_visibility": PRESET_VISIBILITY.get(minimum, "head_to_mid_chest"),
        "selected_avatar_visibility": PRESET_VISIBILITY.get(selected, "head_to_mid_chest"),
        "lower_occlusion_policy": "disabled_or_low" if selected == "full_body" else ("waist_line" if selected == "half_body" else "desk_or_chest_line"),
        "reason": _visibility_policy_reason(exposure, minimum, selected, requested or "auto", upgraded),
    }


def normalize_vrm_framing_preset(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "auto": "",
        "match_source": "",
        "match_source_visibility": "",
        "source": "",
        "source_exposure": "",
        "bust": "bust_up",
        "bustup": "bust_up",
        "chest": "bust_up",
        "chest_up": "bust_up",
        "mid_chest": "bust_up",
        "head_and_shoulders": "bust_up",
        "close": "bust_up",
        "close_up": "bust_up",
        "face": "bust_up",
        "face_only": "bust_up",
        "head": "bust_up",
        "head_only": "bust_up",
        "upper": "half_body",
        "upper_body": "half_body",
        "half": "half_body",
        "waist": "half_body",
        "waist_up": "half_body",
        "full": "full_body",
        "fullbody": "full_body",
        "standing": "full_body",
    }
    text = aliases.get(text, text)
    return text if text in PRESETS else ""


def classify_source_exposure_for_framing(
    frames: Sequence[FaceMotionFrame] | Iterable[FaceMotionFrame],
    frame_size: tuple[int, int],
    *,
    subject_boxes: Sequence[tuple[int, int, int, int] | None] | None = None,
) -> dict[str, Any]:
    """Classify how much of the source person is visible for VRM framing."""
    data = tuple(frames)
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    face_rows: list[tuple[float, float, float]] = []
    subject_rows: list[tuple[float, float, float]] = []
    for index, frame in enumerate(data):
        if not frame.face_box:
            continue
        _x, _y, w, h = [float(v) for v in frame.face_box]
        face_w = _clamp(w / float(width), 0.001, 1.0)
        face_h = _clamp(h / float(height), 0.001, 1.0)
        face_rows.append((face_w, face_h, face_w * face_h))
        box = subject_boxes[index] if subject_boxes is not None and index < len(subject_boxes) else None
        if not box:
            continue
        sx, sy, sw, sh = [float(v) for v in box]
        subject_h = _clamp(sh / float(height), 0.001, 1.0)
        subject_bottom = _clamp((sy + sh) / float(height), 0.0, 1.0)
        subject_rows.append((subject_h, subject_bottom, face_h / max(0.001, subject_h)))
    if not face_rows:
        return _source_exposure_result("unknown", 0.0, "face_box_missing", width, height)
    med_w = float(median(row[0] for row in face_rows))
    med_h = float(median(row[1] for row in face_rows))
    med_area = float(median(row[2] for row in face_rows))
    subject_coverage = len(subject_rows) / max(1, len(face_rows))
    med_subject_h = float(median(row[0] for row in subject_rows)) if subject_rows else 0.0
    med_subject_bottom = float(median(row[1] for row in subject_rows)) if subject_rows else 0.0
    face_to_subject_h = float(median(row[2] for row in subject_rows)) if subject_rows else 0.0
    if med_h >= 0.30 or med_w >= 0.24 or med_area >= 0.070:
        profile = "face_closeup"
        exposure = "face_only"
        confidence = _clamp((med_h - 0.24) / 0.18 + 0.55, 0.55, 0.98)
        method = "face_bbox_heuristic"
    elif subject_coverage >= 0.25 and med_subject_h >= 0.50 and med_subject_bottom >= 0.82 and face_to_subject_h <= 0.24:
        profile = "full_body"
        exposure = "full_body"
        confidence = _clamp(0.58 + subject_coverage * 0.25 + (med_subject_bottom - 0.82) * 0.60, 0.58, 0.94)
        method = "face_subject_bbox_heuristic"
    elif subject_coverage >= 0.25 and (med_subject_h >= 0.36 or med_subject_bottom < 0.82 or face_to_subject_h > 0.24):
        profile = "upper_body"
        exposure = "upper_body"
        confidence = _clamp(0.54 + subject_coverage * 0.25 + max(0.0, med_subject_h - 0.36) * 0.35, 0.54, 0.92)
        method = "face_subject_bbox_heuristic"
    elif med_h >= 0.17 or med_w >= 0.14 or med_area >= 0.030:
        profile = "chest_up"
        exposure = "chest_up"
        confidence = _clamp((med_h - 0.13) / 0.18 + 0.45, 0.45, 0.90)
        method = "face_bbox_heuristic"
    else:
        profile = "full_body_or_wide"
        exposure = "unknown"
        confidence = _clamp((0.19 - med_h) / 0.16 + 0.42, 0.42, 0.88)
        method = "face_bbox_heuristic"
    result = _source_exposure_result(exposure, confidence, method, width, height)
    result.update(
        {
            "raw_profile": profile,
            "face_width": round(med_w, 5),
            "face_height": round(med_h, 5),
            "face_area": round(med_area, 5),
            "subject_coverage": round(subject_coverage, 4),
            "subject_height": round(med_subject_h, 5),
            "subject_bottom": round(med_subject_bottom, 5),
            "face_to_subject_height_ratio": round(face_to_subject_h, 5),
        }
    )
    return result


def preset_for_name(name: str | None) -> SourceFramingPreset:
    key = normalize_vrm_framing_preset(name) or "bust_up"
    return PRESETS.get(key, PRESETS["bust_up"])


def solve_source_framing(
    frame: FaceMotionFrame,
    frame_size: tuple[int, int],
    *,
    preset: str | SourceFramingPreset = "bust_up",
    subject_box: tuple[int, int, int, int] | None = None,
    subject_source: str | None = None,
) -> SourceFramingSolution:
    cfg = preset_for_name(preset) if isinstance(preset, str) else preset
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    if not frame.face_box:
        return SourceFramingSolution(
            ok=False,
            time_ms=int(frame.time_ms),
            preset=cfg.name,
            model_view=_fallback_model_view(cfg),
            track_rotation=(cfg.base_camera_pitch_deg, 180.0, 0.0),
            diagnostics={"reason": "face_box_missing", "frame_size": [width, height]},
        )

    x, y, w, h = [float(v) for v in frame.face_box]
    face_w = _clamp(w / float(width), 0.02, 1.0)
    face_h = _clamp(h / float(height), 0.02, 1.0)
    cx = _clamp((x + w * 0.5) / float(width), 0.0, 1.0)
    cy = _clamp((y + h * 0.5) / float(height), 0.0, 1.0)
    resolved_subject_box, subject_source = _resolve_subject_box(
        frame_size=(width, height),
        face_box=(int(round(x)), int(round(y)), int(round(w)), int(round(h))),
        subject_box=subject_box,
        subject_source=subject_source,
        preset=cfg,
    )
    sx, sy, sw, sh = [float(v) for v in resolved_subject_box]
    subject_h = _clamp(sh / float(height), 0.02, 1.0)
    subject_cx = _clamp((sx + sw * 0.5) / float(width), 0.0, 1.0)
    subject_cy = _clamp((sy + sh * 0.5) / float(height), 0.0, 1.0)

    zoom_ratio = face_h / max(0.001, cfg.reference_face_height)
    subject_ratio = subject_h / max(0.001, cfg.reference_subject_height)
    face_zoom = cfg.base_zoom * (zoom_ratio ** cfg.zoom_power)
    subject_zoom = cfg.base_zoom * (subject_ratio ** cfg.zoom_power)
    weight = _clamp(float(cfg.subject_tracking_weight), 0.0, 1.0)
    zoom = face_zoom * (1.0 - weight) + subject_zoom * weight
    zoom = _clamp(zoom, cfg.min_zoom, cfg.max_zoom)
    center_x = cx * (1.0 - weight) + subject_cx * weight
    center_y = cy * (1.0 - weight * 0.45) + subject_cy * (weight * 0.45)
    pan_x = _clamp((center_x - 0.5) * cfg.horizontal_pan_scale, -0.55, 0.55)
    pan_y = cfg.base_pan_y + (cfg.reference_face_center_y - center_y) * cfg.vertical_pan_scale
    pan_y = _clamp(pan_y, -1.7, 0.45)
    camera_pitch = cfg.base_camera_pitch_deg + (cfg.reference_face_center_y - center_y) * 10.0
    camera_pitch = _clamp(camera_pitch, cfg.min_camera_pitch_deg, cfg.max_camera_pitch_deg)

    model_view = {
        "auto_fit": False,
        "zoom": float(zoom),
        "camera_z": float(cfg.base_camera_z),
        "pan_x": float(pan_x),
        "pan_y": float(pan_y),
        "pan_z": 0.0,
        "source_face_height": float(face_h),
        "source_face_center_x": float(cx),
        "source_face_center_y": float(cy),
        "source_subject_height": float(subject_h),
        "source_subject_center_x": float(subject_cx),
        "source_subject_center_y": float(subject_cy),
        "lower_occlusion_y": float(cfg.lower_occlusion_y),
    }
    return SourceFramingSolution(
        ok=True,
        time_ms=int(frame.time_ms),
        preset=cfg.name,
        model_view=model_view,
        track_rotation=(float(camera_pitch), 180.0, 0.0),
        source_face_center=(float(cx), float(cy)),
        source_face_size=(float(face_w), float(face_h)),
        source_subject_center=(float(subject_cx), float(subject_cy)),
        source_subject_size=(float(sw / float(width)), float(subject_h)),
        diagnostics={
            "frame_size": [width, height],
            "face_box": [int(round(x)), int(round(y)), int(round(w)), int(round(h))],
            "subject_box": [int(round(sx)), int(round(sy)), int(round(sw)), int(round(sh))],
            "subject_source": subject_source,
            "zoom_ratio": float(zoom_ratio),
            "subject_ratio": float(subject_ratio),
            "method": "face_and_subject_box_to_vrm_model_view",
        },
    )


def solve_source_framing_sequence(
    frames: Sequence[FaceMotionFrame] | Iterable[FaceMotionFrame],
    frame_size: tuple[int, int],
    *,
    preset: str | SourceFramingPreset = "bust_up",
    smoothing: float = 0.35,
    subject_boxes: Sequence[tuple[int, int, int, int] | None] | None = None,
    subject_sources: Sequence[str | None] | None = None,
) -> tuple[SourceFramingSolution, ...]:
    cfg = preset_for_name(preset) if isinstance(preset, str) else preset
    alpha = _clamp(float(smoothing), 0.0, 0.95)
    out: list[SourceFramingSolution] = []
    previous: SourceFramingSolution | None = None
    data = tuple(frames)
    for index, frame in enumerate(data):
        subject_box = subject_boxes[index] if subject_boxes is not None and index < len(subject_boxes) else None
        subject_source = subject_sources[index] if subject_sources is not None and index < len(subject_sources) else None
        solved = solve_source_framing(
            frame,
            frame_size,
            preset=cfg,
            subject_box=subject_box,
            subject_source=subject_source,
        )
        if previous is not None and solved.ok and previous.model_view:
            solved = _smooth_solution(previous, solved, alpha)
        out.append(solved)
        previous = solved
    return tuple(out)


def estimate_upper_body_box_from_face_box(
    frame_size: tuple[int, int],
    face_box: tuple[int, int, int, int],
    *,
    preset: str | SourceFramingPreset = "bust_up",
) -> tuple[int, int, int, int]:
    cfg = preset_for_name(preset) if isinstance(preset, str) else preset
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    x, y, w, h = [float(v) for v in face_box]
    cx = x + w * 0.5
    top = y - h * float(cfg.upper_body_top_face_scale)
    box_w = w * float(cfg.shoulder_width_scale)
    box_h = h * float(cfg.upper_body_height_scale)
    return _clip_box(
        (
            int(round(cx - box_w * 0.5)),
            int(round(top)),
            int(round(box_w)),
            int(round(box_h)),
        ),
        width,
        height,
    )


def frame_size_from_openseeface_rows(rows: Iterable[Mapping[str, Any]]) -> tuple[int, int] | None:
    for row in rows:
        width = _int(row.get("Width"), 0)
        height = _int(row.get("Height"), 0)
        if width > 0 and height > 0:
            return (width, height)
    return None


def _resolve_subject_box(
    *,
    frame_size: tuple[int, int],
    face_box: tuple[int, int, int, int],
    subject_box: tuple[int, int, int, int] | None,
    subject_source: str | None,
    preset: SourceFramingPreset,
) -> tuple[tuple[int, int, int, int], str]:
    width, height = frame_size
    if subject_box:
        source = str(subject_source or "").strip() or "provided"
        return _clip_box(subject_box, width, height), source
    return estimate_upper_body_box_from_face_box(frame_size, face_box, preset=preset), "estimated_from_face"


def _source_exposure_result(exposure: str, confidence: float, method: str, width: int, height: int) -> dict[str, Any]:
    return {
        "schema": SOURCE_EXPOSURE_SCHEMA,
        "source_exposure": normalize_source_exposure_type(exposure),
        "confidence": round(float(confidence or 0.0), 4),
        "method": str(method or ""),
        "frame_size": [int(width), int(height)],
    }


def _visibility_policy_reason(
    exposure: str,
    minimum: str,
    selected: str,
    requested: str,
    upgraded: bool,
) -> str:
    if upgraded:
        return f"{exposure}_source_requires_at_least_{minimum}; requested_{requested}_was_too_narrow"
    if exposure == "full_body":
        return "full_body_source_keeps_vrm_head_to_toe"
    if exposure == "upper_body":
        return "upper_body_source_keeps_vrm_head_to_waist_or_wider"
    if exposure == "chest_up":
        return "chest_up_source_keeps_vrm_head_to_mid_chest"
    if exposure == "face_only":
        return "face_only_source_allows_bust_up_but_not_head_only_thumbnail"
    return f"unknown_source_exposure_uses_conservative_{selected}_framing"


def _clip_box(box: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x, y, w, h = [int(v) for v in box]
    x0 = max(0, min(max(0, width - 1), x))
    y0 = max(0, min(max(0, height - 1), y))
    x1 = max(x0 + 1, min(width, x + max(1, w)))
    y1 = max(y0 + 1, min(height, y + max(1, h)))
    return (x0, y0, max(1, x1 - x0), max(1, y1 - y0))


def _fallback_model_view(cfg: SourceFramingPreset) -> dict[str, float | bool]:
    return {
        "auto_fit": False,
        "zoom": float(cfg.base_zoom),
        "camera_z": float(cfg.base_camera_z),
        "pan_x": 0.0,
        "pan_y": float(cfg.base_pan_y),
        "pan_z": 0.0,
        "lower_occlusion_y": float(cfg.lower_occlusion_y),
    }


def _smooth_solution(previous: SourceFramingSolution, current: SourceFramingSolution, alpha: float) -> SourceFramingSolution:
    prev_view = dict(previous.model_view or {})
    cur_view = dict(current.model_view or {})
    for key in ("zoom", "camera_z", "pan_x", "pan_y", "pan_z"):
        cur_view[key] = _lerp(float(cur_view.get(key, 0.0)), float(prev_view.get(key, cur_view.get(key, 0.0))), alpha)
    prev_pitch = float(previous.track_rotation[0])
    cur_pitch = _lerp(float(current.track_rotation[0]), prev_pitch, alpha)
    diag = dict(current.diagnostics or {})
    diag["smoothing"] = float(alpha)
    return replace(
        current,
        model_view=cur_view,
        track_rotation=(cur_pitch, current.track_rotation[1], current.track_rotation[2]),
        diagnostics=diag,
    )


def _lerp(value: float, previous: float, alpha: float) -> float:
    return previous * alpha + value * (1.0 - alpha)


def _int(value: Any, default: int) -> int:
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))
