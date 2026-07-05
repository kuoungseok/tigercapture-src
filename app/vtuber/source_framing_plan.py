"""Build render-free source-video framing plans for VTuber previews."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from app.vtuber.source_framing_control import apply_framing_user_offset
from app.vtuber.source_framing import solve_source_framing_sequence
from app.vtuber.source_subject import detect_subject_boxes_for_motion_frames
from app.vtuber.video_face_driver import FaceMotionFrame


SOURCE_FRAMING_PLAN_SCHEMA = "tigerstudio.vtuber.source_framing_plan.v1"
DEFAULT_SOURCE_FRAMING_SLOTS = ("neutral", "head", "mouth")
SUPPORTED_SOURCE_FRAMING_SLOTS = frozenset({"neutral", "head", "mouth", "blink"})


def build_source_framing_plan(
    frames: Sequence[FaceMotionFrame] | Iterable[FaceMotionFrame],
    frame_size: tuple[int, int],
    *,
    preset: str = "bust_up",
    video_path: str | Path | None = None,
    slots: Sequence[str] | str = DEFAULT_SOURCE_FRAMING_SLOTS,
    smoothing: float = 0.35,
    subject_detect_every: int = 3,
    subject_detect_scope: str = "selected",
    user_offset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return camera/framing guidance without invoking the renderer.

    The result is suitable for UI preview setup, export planning, and QA logs.
    It intentionally keeps full detector frames in diagnostics while exposing a
    compact `selected_frames` list for normal UI consumers.
    """
    data = tuple(frames)
    normalized_slots = normalize_source_framing_slots(slots)
    width, height = max(1, int(frame_size[0])), max(1, int(frame_size[1]))
    diagnostics: dict[str, Any] = {
        "frame_size": [width, height],
        "preset": str(preset or "bust_up"),
        "slots": list(normalized_slots),
        "errors": [],
        "warnings": [],
    }
    if not data:
        diagnostics["errors"].append("motion_frames_empty")
        return {
            "schema": SOURCE_FRAMING_PLAN_SCHEMA,
            "ok": False,
            "preset": str(preset or "bust_up"),
            "frame_count": 0,
            "selected_indices": [],
            "selected_frames": [],
            "source_subject": None,
            "diagnostics": diagnostics,
        }

    selected = select_source_framing_indices(data, normalized_slots)
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
            preset=str(preset or "bust_up"),
            detect_every=max(1, int(subject_detect_every)),
            detect_indices=detect_indices,
        )
        subject_boxes = source_subject.subject_boxes
        subject_sources = tuple(frame.source for frame in source_subject.frames)
        data = _apply_source_subject_shoulder_roll(data, source_subject)

    solved = solve_source_framing_sequence(
        data,
        (width, height),
        preset=str(preset or "bust_up"),
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
            }
        )

    if source_subject is not None:
        subject_diag = dict(source_subject.diagnostics)
        if subject_diag.get("warnings"):
            diagnostics["warnings"].extend(subject_diag.get("warnings") or [])
    return {
        "schema": SOURCE_FRAMING_PLAN_SCHEMA,
        "ok": True,
        "preset": str(preset or "bust_up"),
        "frame_count": len(data),
        "selected_indices": [int(index) for index in selected],
        "selected_frames": selected_frames,
        "source_subject": _source_subject_summary(source_subject),
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
