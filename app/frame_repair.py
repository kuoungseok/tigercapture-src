from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping
from uuid import uuid4

import numpy as np


RepairFrameReader = Callable[[int], np.ndarray | None]


@dataclass(frozen=True)
class FrameRepairRange:
    id: str
    source_start_ms: int
    source_end_ms: int
    method: str = "interpolate"
    algorithm: str = "optical_flow"
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_start_ms": self.source_start_ms,
            "source_end_ms": self.source_end_ms,
            "method": self.method,
            "algorithm": self.algorithm,
            "label": self.label,
        }


def normalize_frame_repair_range(row: Mapping[str, Any] | FrameRepairRange) -> dict[str, Any] | None:
    if isinstance(row, FrameRepairRange):
        return row.to_dict()
    if not isinstance(row, Mapping):
        return None
    try:
        start = max(0, int(row.get("source_start_ms", row.get("start_ms", 0)) or 0))
        end = max(start + 1, int(row.get("source_end_ms", row.get("end_ms", start + 1)) or start + 1))
    except Exception:
        return None
    method = str(row.get("method") or "interpolate").strip().casefold()
    if method not in {"interpolate", "hold_previous", "hold_next"}:
        method = "interpolate"
    algorithm = str(row.get("algorithm") or "optical_flow").strip().casefold()
    if algorithm not in {"optical_flow", "linear"}:
        algorithm = "optical_flow"
    return {
        "id": str(row.get("id") or f"repair_{uuid4().hex[:8]}"),
        "source_start_ms": start,
        "source_end_ms": end,
        "method": method,
        "algorithm": algorithm,
        "label": str(row.get("label") or ""),
    }


def normalize_frame_repairs(rows: Any) -> list[dict[str, Any]]:
    repairs: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return repairs
    for row in rows:
        normalized = normalize_frame_repair_range(row)
        if normalized is not None:
            repairs.append(normalized)
    repairs.sort(key=lambda item: (int(item["source_start_ms"]), int(item["source_end_ms"])))
    return repairs


def frame_repairs_for_source_window(
    rows: Any,
    source_start_ms: int,
    source_end_ms: int,
) -> list[dict[str, Any]]:
    start = max(0, int(source_start_ms))
    end = max(start, int(source_end_ms))
    if end <= start:
        return []
    out: list[dict[str, Any]] = []
    for row in normalize_frame_repairs(rows):
        repair_start = int(row["source_start_ms"])
        repair_end = int(row["source_end_ms"])
        if repair_end <= start or repair_start >= end:
            continue
        clipped = dict(row)
        clipped["source_start_ms"] = max(repair_start, start)
        clipped["source_end_ms"] = min(repair_end, end)
        if clipped["source_end_ms"] > clipped["source_start_ms"]:
            out.append(clipped)
    return out


def make_frame_repair_range(
    *,
    source_start_ms: int,
    source_end_ms: int,
    method: str = "interpolate",
    algorithm: str = "optical_flow",
    label: str = "",
) -> dict[str, Any]:
    row = FrameRepairRange(
        id=f"repair_{uuid4().hex[:8]}",
        source_start_ms=max(0, int(source_start_ms)),
        source_end_ms=max(int(source_start_ms) + 1, int(source_end_ms)),
        method=str(method or "interpolate"),
        algorithm=str(algorithm or "optical_flow"),
        label=str(label or ""),
    )
    normalized = normalize_frame_repair_range(row)
    assert normalized is not None
    return normalized


def active_frame_repair(clip: Any, source_ms: int) -> dict[str, Any] | None:
    repairs = normalize_frame_repairs(getattr(clip, "frame_repairs", []) or [])
    if repairs != list(getattr(clip, "frame_repairs", []) or []):
        try:
            clip.frame_repairs = repairs
        except Exception:
            pass
    t = int(source_ms)
    for row in repairs:
        if int(row["source_start_ms"]) <= t < int(row["source_end_ms"]):
            return row
    return None


def _frame_index(ms: int, fps: float) -> int:
    return max(0, int((max(0, int(ms)) / 1000.0) * max(1.0, float(fps))))


def _blend_linear(frame_a: np.ndarray, frame_b: np.ndarray, frac: float) -> np.ndarray:
    a = float(1.0 - frac)
    b = float(frac)
    return np.clip(frame_a.astype(np.float32) * a + frame_b.astype(np.float32) * b, 0, 255).astype(np.uint8)


def _blend_optical_flow(frame_a: np.ndarray, frame_b: np.ndarray, frac: float) -> np.ndarray:
    try:
        import cv2  # type: ignore

        h, w = frame_a.shape[:2]
        scale = min(1.0, 480.0 / max(h, 1))
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))
        small_a = cv2.resize(frame_a, (sw, sh), interpolation=cv2.INTER_LINEAR)
        small_b = cv2.resize(frame_b, (sw, sh), interpolation=cv2.INTER_LINEAR)
        gray_a = cv2.cvtColor(small_a, cv2.COLOR_RGB2GRAY)
        gray_b = cv2.cvtColor(small_b, cv2.COLOR_RGB2GRAY)
        flow_small = cv2.calcOpticalFlowFarneback(
            gray_a,
            gray_b,
            None,
            pyr_scale=0.5,
            levels=2,
            winsize=11,
            iterations=2,
            poly_n=5,
            poly_sigma=1.1,
            flags=0,
        )
        flow = cv2.resize(flow_small, (w, h)) / max(scale, 0.001)
        xs = np.arange(w, dtype=np.float32)
        ys = np.arange(h, dtype=np.float32)
        map_x, map_y = np.meshgrid(xs, ys)
        map_x = map_x + flow[:, :, 0] * float(frac)
        map_y = map_y + flow[:, :, 1] * float(frac)
        warped = cv2.remap(
            frame_a,
            map_x,
            map_y,
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return _blend_linear(warped, frame_b, frac)
    except Exception:
        return _blend_linear(frame_a, frame_b, frac)


def apply_frame_repair_rgb(
    rgb: np.ndarray,
    *,
    clip: Any,
    source_ms: int,
    fps: float,
    frame_reader: RepairFrameReader,
) -> tuple[np.ndarray, bool]:
    repair = active_frame_repair(clip, int(source_ms))
    if repair is None:
        return rgb, False

    start_ms = int(repair["source_start_ms"])
    end_ms = int(repair["source_end_ms"])
    current_idx = _frame_index(int(source_ms), fps)
    start_idx = _frame_index(start_ms, fps)
    end_idx = max(start_idx + 1, _frame_index(end_ms, fps))
    prev_idx = max(0, start_idx - 1)
    next_idx = max(prev_idx + 1, end_idx)

    method = str(repair.get("method") or "interpolate")
    if method == "hold_previous":
        previous = frame_reader(prev_idx)
        return (previous, True) if previous is not None else (rgb, False)
    if method == "hold_next":
        next_frame = frame_reader(next_idx)
        return (next_frame, True) if next_frame is not None else (rgb, False)

    previous = frame_reader(prev_idx)
    next_frame = frame_reader(next_idx)
    if previous is None or next_frame is None:
        return rgb, False
    if previous.shape != next_frame.shape:
        return rgb, False
    span = max(1, next_idx - prev_idx)
    frac = max(0.0, min(1.0, (current_idx - prev_idx) / float(span)))
    if str(repair.get("algorithm") or "optical_flow") == "linear":
        return _blend_linear(previous, next_frame, frac), True
    return _blend_optical_flow(previous, next_frame, frac), True


__all__ = [
    "FrameRepairRange",
    "active_frame_repair",
    "apply_frame_repair_rgb",
    "frame_repairs_for_source_window",
    "make_frame_repair_range",
    "normalize_frame_repair_range",
    "normalize_frame_repairs",
]
