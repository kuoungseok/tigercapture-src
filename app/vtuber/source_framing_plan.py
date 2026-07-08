"""Build render-free source-video framing plans for VTuber previews."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from app.vtuber.source_framing_control import apply_framing_user_offset
from app.vtuber.source_framing import (
    classify_source_exposure_for_framing,
    normalize_source_exposure_type,
    solve_source_framing_sequence,
    vrm_visibility_policy_for_source_exposure,
)
from app.vtuber.source_subject import detect_subject_boxes_for_motion_frames
from app.vtuber.video_face_driver import FaceMotionFrame


SOURCE_FRAMING_PLAN_SCHEMA = "tigerstudio.vtuber.source_framing_plan.v1"
DEFAULT_SOURCE_FRAMING_SLOTS = ("neutral", "head", "mouth")
SUPPORTED_SOURCE_FRAMING_SLOTS = frozenset({"neutral", "head", "mouth", "blink"})


def build_source_framing_plan(
    frames: Sequence[FaceMotionFrame] | Iterable[FaceMotionFrame],
    frame_size: tuple[int, int],
    *,
    preset: str = "auto",
    video_path: str | Path | None = None,
    slots: Sequence[str] | str = DEFAULT_SOURCE_FRAMING_SLOTS,
    smoothing: float = 0.35,
    subject_detect_every: int = 3,
    subject_detect_scope: str = "selected",
    source_exposure: str = "",
    match_source_visibility: bool = True,
    allow_narrower_than_source: bool = False,
    user_offset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return camera/framing guidance without invoking the renderer.

    The result is suitable for UI preview setup, export planning, and QA logs.
    It intentionally keeps full detector frames in diagnostics while exposing a
    compact `selected_frames` list for normal UI consumers. `preset="auto"`
    means source-person exposure decides the minimum VRM visibility.
    """
    data = tuple(frames)
    normalized_slots = normalize_source_framing_slots(slots)
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    requested_preset = str(preset or "auto").strip().casefold().replace("-", "_")
    diagnostics: dict[str, Any] = {
        "frame_size": [width, height],
        "requested_preset": requested_preset or "auto",
        "slots": list(normalized_slots),
        "errors": [],
        "warnings": [],
    }
    if not data:
        exposure = _resolve_explicit_source_exposure(source_exposure)
        visibility_policy = vrm_visibility_policy_for_source_exposure(
            exposure or "unknown",
            requested_preset=requested_preset or "auto",
            allow_narrower=allow_narrower_than_source or not match_source_visibility,
            method="explicit" if exposure else "motion_frames_empty",
        )
        diagnostics["errors"].append("motion_frames_empty")
        return {
            "schema": SOURCE_FRAMING_PLAN_SCHEMA,
            "ok": False,
            "preset": visibility_policy["selected_framing_preset"],
            "requested_preset": requested_preset or "auto",
            "frame_count": 0,
            "selected_indices": [],
            "selected_frames": [],
            "source_subject": None,
            "source_exposure": {"source_exposure": exposure or "unknown", "method": "motion_frames_empty"},
            "visibility_policy": visibility_policy,
            "diagnostics": diagnostics,
        }

    selected = select_source_framing_indices(data, normalized_slots)
    exposure = _initial_source_exposure(
        data,
        (width, height),
        explicit_source_exposure=source_exposure,
    )
    visibility_policy = vrm_visibility_policy_for_source_exposure(
        exposure.get("source_exposure") or "unknown",
        requested_preset=requested_preset or "auto",
        allow_narrower=allow_narrower_than_source or not match_source_visibility,
        confidence=float(exposure.get("confidence", 0.0) or 0.0),
        method=str(exposure.get("method") or ""),
    )
    resolved_preset = str(visibility_policy["selected_framing_preset"])
    source_subject = None
    subject_boxes = None
    subject_sources = None
    if video_path:
        detect_scope = str(subject_detect_scope or "selected").strip().casefold()
        detect_indices = selected if detect_scope != "sequence" else None
        source_subject = detect_subject_boxes_for_motion_frames(
            Path(video_path),
            data,
            source_frame_size=(width, height),
            preset=resolved_preset,
            detect_every=max(1, int(subject_detect_every)),
            detect_indices=detect_indices,
        )
        subject_boxes = source_subject.subject_boxes
        subject_sources = tuple(frame.source for frame in source_subject.frames)
        data = _apply_source_subject_shoulder_roll(data, source_subject)
        exposure = _resolved_source_exposure(
            data,
            (width, height),
            subject_boxes=subject_boxes,
            explicit_source_exposure=source_exposure,
        )
        visibility_policy = vrm_visibility_policy_for_source_exposure(
            exposure.get("source_exposure") or "unknown",
            requested_preset=requested_preset or "auto",
            allow_narrower=allow_narrower_than_source or not match_source_visibility,
            confidence=float(exposure.get("confidence", 0.0) or 0.0),
            method=str(exposure.get("method") or ""),
        )
        resolved_preset = str(visibility_policy["selected_framing_preset"])

    solved = solve_source_framing_sequence(
        data,
        (width, height),
        preset=resolved_preset,
        smoothing=float(smoothing),
        subject_boxes=subject_boxes,
        subject_sources=subject_sources,
    )
    selected_frames = []
    for slot, index in zip(normalized_slots, selected):
        frame = data[index]
        solution = solved[index]
        controlled = apply_framing_user_offset(solution, user_offset)
        selected_frames.append(
            {
                "slot": slot,
                "index": int(index),
                "time_ms": int(frame.time_ms),
                "motion": {
                    "yaw_deg": float(frame.yaw_deg),
                    "pitch_deg": float(frame.pitch_deg),
                    "roll_deg": float(frame.roll_deg),
                    "shoulder_roll_deg": float(getattr(frame, "shoulder_roll_deg", 0.0)),
                    "mouth_open": float(frame.mouth_open),
                    "blink": float(max(frame.blink_l, frame.blink_r)),
                    "confidence": float(frame.confidence),
                },
                "framing": solution.to_dict(),
                "framing_control": controlled,
                "final_framing": controlled["final"],
                "visibility_policy": dict(visibility_policy),
            }
        )

    if source_subject is not None:
        subject_diag = dict(source_subject.diagnostics)
        if subject_diag.get("warnings"):
            diagnostics["warnings"].extend(subject_diag.get("warnings") or [])
    return {
        "schema": SOURCE_FRAMING_PLAN_SCHEMA,
        "ok": True,
        "preset": resolved_preset,
        "requested_preset": requested_preset or "auto",
        "frame_count": len(data),
        "selected_indices": [int(index) for index in selected],
        "selected_frames": selected_frames,
        "source_subject": _source_subject_summary(source_subject),
        "source_exposure": exposure,
        "visibility_policy": visibility_policy,
        "diagnostics": diagnostics,
    }


def normalize_source_framing_slots(slots: Sequence[str] | str) -> tuple[str, ...]:
    if isinstance(slots, str):
        raw_slots = slots.split(",")
    else:
        raw_slots = list(slots)
    out: list[str] = []
    for raw in raw_slots:
        slot = str(raw or "").strip().casefold()
        if slot in SUPPORTED_SOURCE_FRAMING_SLOTS and slot not in out:
            out.append(slot)
    return tuple(out or DEFAULT_SOURCE_FRAMING_SLOTS)


def select_source_framing_indices(frames: Sequence[FaceMotionFrame], slots: Sequence[str] | str) -> list[int]:
    if not frames:
        return []
    normalized = normalize_source_framing_slots(slots)
    candidates = {
        "neutral": 0,
        "head": max(range(len(frames)), key=lambda i: abs(frames[i].yaw_deg) + abs(frames[i].roll_deg) * 0.7),
        "mouth": max(range(len(frames)), key=lambda i: frames[i].mouth_open),
        "blink": max(range(len(frames)), key=lambda i: max(frames[i].blink_l, frames[i].blink_r)),
    }
    return [int(candidates[slot]) for slot in normalized]


def _source_subject_summary(source_subject: Any) -> dict[str, Any] | None:
    if source_subject is None:
        return None
    diagnostics = dict(source_subject.diagnostics)
    return {
        "schema": diagnostics.get("schema") or "tigerstudio.vtuber.source_subject.summary.v1",
        "ok": bool(source_subject.ok),
        "detected_frames": int(diagnostics.get("detected_frames") or 0),
        "held_frames": int(diagnostics.get("held_frames") or 0),
        "estimated_frames": int(diagnostics.get("estimated_frames") or 0),
        "missing_frames": int(diagnostics.get("missing_frames") or 0),
        "detectors": list(diagnostics.get("detectors") or []),
        "warnings": list(diagnostics.get("warnings") or []),
        "errors": list(diagnostics.get("errors") or []),
    }


def _resolve_explicit_source_exposure(value: str) -> str:
    text = str(value or "").strip()
    return normalize_source_exposure_type(text) if text else ""


def _initial_source_exposure(
    frames: tuple[FaceMotionFrame, ...],
    frame_size: tuple[int, int],
    *,
    explicit_source_exposure: str = "",
) -> dict[str, Any]:
    exposure = _resolve_explicit_source_exposure(explicit_source_exposure)
    if exposure:
        return {
            "schema": "tigerstudio.vtuber.source_exposure_classification.v1",
            "source_exposure": exposure,
            "confidence": 1.0,
            "method": "explicit_source_exposure",
            "frame_size": [int(frame_size[0]), int(frame_size[1])],
        }
    return classify_source_exposure_for_framing(frames, frame_size)


def _resolved_source_exposure(
    frames: tuple[FaceMotionFrame, ...],
    frame_size: tuple[int, int],
    *,
    subject_boxes: Sequence[tuple[int, int, int, int] | None] | None,
    explicit_source_exposure: str = "",
) -> dict[str, Any]:
    exposure = _resolve_explicit_source_exposure(explicit_source_exposure)
    if exposure:
        return {
            "schema": "tigerstudio.vtuber.source_exposure_classification.v1",
            "source_exposure": exposure,
            "confidence": 1.0,
            "method": "explicit_source_exposure",
            "frame_size": [int(frame_size[0]), int(frame_size[1])],
        }
    return classify_source_exposure_for_framing(frames, frame_size, subject_boxes=subject_boxes)


def _apply_source_subject_shoulder_roll(
    frames: tuple[FaceMotionFrame, ...],
    source_subject: Any,
) -> tuple[FaceMotionFrame, ...]:
    subject_frames = tuple(getattr(source_subject, "frames", ()) or ())
    if not subject_frames:
        return frames
    out: list[FaceMotionFrame] = []
    for index, frame in enumerate(frames):
        if index >= len(subject_frames):
            out.append(frame)
            continue
        roll = float(getattr(subject_frames[index], "shoulder_roll_deg", 0.0) or 0.0)
        out.append(replace(frame, shoulder_roll_deg=roll))
    return tuple(out)
