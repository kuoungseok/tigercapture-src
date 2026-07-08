"""Animation timing lane helpers for PPT slides."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.pptgen.animations import animation_is_active, animation_payload
from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec


@dataclass(frozen=True)
class AnimationLaneRow:
    slide_id: str
    element_id: str
    element_name: str
    element_kind: str
    effect: str
    trigger: str
    click_index: int
    start_ms: int
    duration_ms: int
    end_ms: int
    z_index: int
    lane_index: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "element_id": self.element_id,
            "element_name": self.element_name,
            "element_kind": self.element_kind,
            "effect": self.effect,
            "trigger": self.trigger,
            "click_index": self.click_index,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "end_ms": self.end_ms,
            "z_index": self.z_index,
            "lane_index": self.lane_index,
        }


def clamp_animation_timing(
    start_ms: int,
    duration_ms: int,
    slide_duration_ms: int,
    *,
    min_duration_ms: int = 50,
) -> tuple[int, int]:
    slide_duration = max(1, int(slide_duration_ms or 1))
    min_duration = max(1, min(int(min_duration_ms or 1), slide_duration))
    duration = max(min_duration, min(slide_duration, int(duration_ms or min_duration)))
    start = max(0, min(slide_duration - duration, int(start_ms or 0)))
    return start, duration


def adjust_animation_timing(
    row: AnimationLaneRow,
    delta_ms: int,
    mode: str,
    slide_duration_ms: int,
    *,
    min_duration_ms: int = 50,
) -> tuple[int, int]:
    slide_duration = max(1, int(slide_duration_ms or 1))
    min_duration = max(1, min(int(min_duration_ms or 1), slide_duration))
    delta = int(delta_ms or 0)
    current_start, current_duration = clamp_animation_timing(
        row.start_ms,
        row.duration_ms,
        slide_duration,
        min_duration_ms=min_duration,
    )
    current_end = current_start + current_duration
    normalized_mode = str(mode or "move").strip().lower()
    if normalized_mode == "trim_start":
        new_start = max(0, min(current_end - min_duration, current_start + delta))
        return new_start, current_end - new_start
    if normalized_mode == "trim_end":
        new_end = max(current_start + min_duration, min(slide_duration, current_end + delta))
        return current_start, new_end - current_start
    return clamp_animation_timing(
        current_start + delta,
        current_duration,
        slide_duration,
        min_duration_ms=min_duration,
    )


def _label_for_element(element: SlideElement) -> str:
    raw = str(element.name or element.text or element.kind or element.id).replace("\n", " ").strip()
    return raw[:48] or element.id


def animation_lane_rows_for_slide(slide: SlideSpec | None) -> list[AnimationLaneRow]:
    if slide is None:
        return []
    rows: list[AnimationLaneRow] = []
    for element in slide.elements:
        if not animation_is_active(element.animation):
            continue
        payload = animation_payload(element.animation)
        effect = str(payload.get("in_animation") or "none")
        if effect == "none":
            effect = str(payload.get("out_animation") or "none")
        if effect == "none":
            continue
        rows.append(
            AnimationLaneRow(
                slide_id=slide.id,
                element_id=element.id,
                element_name=_label_for_element(element),
                element_kind=str(element.kind or ""),
                effect=effect,
                trigger=str(payload.get("trigger") or "on_slide_start"),
                click_index=max(0, int(payload.get("click_index") or 0)),
                start_ms=max(0, int(payload.get("start_ms") or 0)),
                duration_ms=max(1, int(payload.get("duration_ms") or 1)),
                end_ms=max(1, int(payload.get("end_ms") or 1)),
                z_index=int(element.z_index),
                lane_index=0,
            )
        )
    sorted_rows = sorted(
        rows,
        key=lambda row: (
            0 if row.trigger == "on_click" else 1,
            row.click_index if row.trigger == "on_click" and row.click_index > 0 else 9999,
            row.start_ms,
            row.end_ms,
            row.z_index,
            row.element_id,
        ),
    )
    assigned_rows: list[AnimationLaneRow] = []
    next_click = 1
    for row in sorted_rows:
        click_index = row.click_index
        if row.trigger == "on_click":
            if click_index <= 0:
                click_index = next_click
            next_click = max(next_click, click_index + 1)
        assigned_rows.append(
            AnimationLaneRow(
                slide_id=row.slide_id,
                element_id=row.element_id,
                element_name=row.element_name,
                element_kind=row.element_kind,
                effect=row.effect,
                trigger=row.trigger,
                click_index=click_index,
                start_ms=row.start_ms,
                duration_ms=row.duration_ms,
                end_ms=row.end_ms,
                z_index=row.z_index,
                lane_index=row.lane_index,
            )
        )
    return [
        AnimationLaneRow(
            slide_id=row.slide_id,
            element_id=row.element_id,
            element_name=row.element_name,
            element_kind=row.element_kind,
            effect=row.effect,
            trigger=row.trigger,
            click_index=row.click_index,
            start_ms=row.start_ms,
            duration_ms=row.duration_ms,
            end_ms=row.end_ms,
            z_index=row.z_index,
            lane_index=index,
        )
        for index, row in enumerate(assigned_rows)
    ]


def animation_lane_rows(deck: DeckSpec, slide_id: str) -> list[AnimationLaneRow]:
    slide = deck.slide_by_id(slide_id)
    return animation_lane_rows_for_slide(slide)


__all__ = [
    "AnimationLaneRow",
    "adjust_animation_timing",
    "animation_lane_rows",
    "animation_lane_rows_for_slide",
    "clamp_animation_timing",
]
