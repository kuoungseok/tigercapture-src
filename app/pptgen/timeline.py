"""Timeline helpers for slide-clip based PPT authoring."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.pptgen.schema import DeckSpec, SlideSpec


@dataclass
class SlideClip:
    id: str
    slide_id: str
    start_ms: int
    duration_ms: int = 5000
    transition_in: str = "cut"
    transition_out: str = "fade"
    label_color: str = "#5DD7FF"
    collapsed: bool = False

    @property
    def end_ms(self) -> int:
        return int(self.start_ms) + max(1, int(self.duration_ms))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlideClip":
        return cls(**dict(data))


@dataclass
class PptTimeline:
    slide_clips: list[SlideClip] = field(default_factory=list)
    playhead_ms: int = 0
    selected_slide_id: str = ""
    markers: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_deck(cls, deck: DeckSpec) -> "PptTimeline":
        clips: list[SlideClip] = []
        cursor = 0
        for index, slide in enumerate(deck.slides, start=1):
            duration = max(1, int(slide.duration_ms or 5000))
            clips.append(
                SlideClip(
                    id=f"clip-{index:03d}",
                    slide_id=slide.id,
                    start_ms=cursor,
                    duration_ms=duration,
                    transition_out=str(slide.transition or "fade"),
                )
            )
            cursor += duration
        return cls(slide_clips=clips, selected_slide_id=deck.slides[0].id if deck.slides else "")

    def normalize(self, deck: DeckSpec | None = None) -> None:
        cursor = 0
        duration_by_slide = {slide.id: max(1, int(slide.duration_ms or 5000)) for slide in deck.slides} if deck else {}
        for clip in self.slide_clips:
            clip.start_ms = cursor
            if clip.slide_id in duration_by_slide:
                clip.duration_ms = duration_by_slide[clip.slide_id]
            clip.duration_ms = max(1, int(clip.duration_ms))
            cursor += clip.duration_ms

    def clip_at(self, time_ms: int) -> SlideClip | None:
        t = max(0, int(time_ms))
        for clip in self.slide_clips:
            if clip.start_ms <= t < clip.end_ms:
                return clip
        return self.slide_clips[-1] if self.slide_clips else None

    def select_slide(self, slide_id: str) -> bool:
        if any(clip.slide_id == slide_id for clip in self.slide_clips):
            self.selected_slide_id = str(slide_id)
            return True
        return False


def add_slide(deck: DeckSpec, slide: SlideSpec, *, index: int | None = None) -> PptTimeline:
    if index is None:
        deck.slides.append(slide)
    else:
        deck.slides.insert(max(0, min(len(deck.slides), int(index))), slide)
    return PptTimeline.from_deck(deck)


def move_slide(deck: DeckSpec, slide_id: str, new_index: int) -> PptTimeline:
    old_index = next((idx for idx, slide in enumerate(deck.slides) if slide.id == slide_id), None)
    if old_index is None:
        return PptTimeline.from_deck(deck)
    slide = deck.slides.pop(old_index)
    deck.slides.insert(max(0, min(len(deck.slides), int(new_index))), slide)
    return PptTimeline.from_deck(deck)


def remove_slide(deck: DeckSpec, slide_id: str) -> PptTimeline:
    deck.slides = [slide for slide in deck.slides if slide.id != slide_id]
    return PptTimeline.from_deck(deck)


__all__ = ["PptTimeline", "SlideClip", "add_slide", "move_slide", "remove_slide"]

