"""Bridge from the video editor timeline into a user PPT deck."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec


_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".gif"}


@dataclass(frozen=True)
class TimelineClipSummary:
    track_id: int
    clip_id: int
    source_path: str
    timeline_in_ms: int
    duration_ms: int
    source_in_ms: int = 0
    source_out_ms: int = 0
    label: str = ""

    @property
    def source_name(self) -> str:
        return Path(self.source_path).name if self.source_path else (self.label or f"Clip {self.clip_id}")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _clip_duration_ms(clip: Any) -> int:
    duration = getattr(clip, "duration_ms", None)
    if duration is not None:
        return max(0, _as_int(duration))
    effective = getattr(clip, "effective_duration_ms", None)
    if callable(effective):
        try:
            return max(0, _as_int(effective()))
        except Exception:
            pass
    source_in = _as_int(getattr(clip, "source_in_ms", 0))
    source_out = _as_int(getattr(clip, "source_out_ms", 0))
    if source_out > source_in:
        return max(0, source_out - source_in)
    return max(0, _as_int(getattr(clip, "source_duration_ms", 0)))


def _track_clip_summaries(track: Any) -> list[TimelineClipSummary]:
    track_id = _as_int(getattr(track, "id", 0))
    clips = list(getattr(track, "clips", []) or [])
    rows: list[TimelineClipSummary] = []
    for index, clip in enumerate(clips, start=1):
        source = getattr(clip, "source_path", None)
        source_path = str(source or "")
        duration = _clip_duration_ms(clip)
        if not source_path and duration <= 0:
            continue
        rows.append(
            TimelineClipSummary(
                track_id=track_id,
                clip_id=_as_int(getattr(clip, "id", index), index),
                source_path=source_path,
                timeline_in_ms=_as_int(getattr(clip, "timeline_in_ms", 0)),
                duration_ms=duration,
                source_in_ms=_as_int(getattr(clip, "source_in_ms", 0)),
                source_out_ms=_as_int(getattr(clip, "source_out_ms", 0)),
                label=str(getattr(clip, "label", "") or ""),
            )
        )
    if rows:
        return sorted(rows, key=lambda row: (row.timeline_in_ms, row.track_id, row.clip_id))

    source = getattr(track, "source_path", None)
    duration = max(0, _as_int(getattr(track, "duration_ms", 0)))
    if source is not None or duration > 0:
        return [
            TimelineClipSummary(
                track_id=track_id,
                clip_id=1,
                source_path=str(source or ""),
                timeline_in_ms=max(0, _as_int(getattr(track, "offset_ms", 0))),
                duration_ms=duration,
                source_in_ms=0,
                source_out_ms=duration,
                label=str(getattr(track, "label", "") or ""),
            )
        ]
    return []


def timeline_clip_summaries(owner: Any, *, max_clips: int = 48) -> list[TimelineClipSummary]:
    rows: list[TimelineClipSummary] = []
    for track in list(getattr(owner, "_tracks", []) or []):
        rows.extend(_track_clip_summaries(track))
    rows.sort(key=lambda row: (row.timeline_in_ms, row.track_id, row.clip_id))
    return rows[: max(0, int(max_clips or 48))]


def deck_from_editor_timeline(
    owner: Any,
    *,
    title: str = "Timeline Presentation",
    max_slides: int = 24,
) -> DeckSpec:
    title = str(title or "Timeline Presentation").strip() or "Timeline Presentation"
    clips = timeline_clip_summaries(owner, max_clips=max(1, int(max_slides or 24)))
    deck = DeckSpec(id="editor-timeline-ppt", title=title, purpose="user_presentation", language="ko")
    deck.metadata["source"] = "editor_timeline"
    deck.metadata["clip_count"] = len(clips)

    if not clips:
        slide = SlideSpec(id="slide-001", title="Empty timeline", layout_id="empty", duration_ms=5000)
        slide.add_element(
            SlideElement.text_box(
                "el-title",
                title,
                x=0.07,
                y=0.10,
                w=0.76,
                h=0.12,
                font_size=42,
                bold=True,
            )
        )
        slide.add_element(
            SlideElement.text_box(
                "el-body",
                "No video clips are on the editor timeline yet.",
                x=0.08,
                y=0.30,
                w=0.72,
                h=0.16,
                font_size=26,
                color="#5E6A7D",
            )
        )
        deck.slides.append(slide)
        return deck

    cover = SlideSpec(id="slide-001", title=title, layout_id="cover", duration_ms=5000)
    cover.add_element(
        SlideElement.text_box(
            "el-cover-title",
            title,
            x=0.07,
            y=0.12,
            w=0.66,
            h=0.18,
            font_size=46,
            bold=True,
        )
    )
    cover.add_element(
        SlideElement.text_box(
            "el-cover-subtitle",
            f"{len(clips)} timeline clip(s) converted into slide drafts.",
            x=0.08,
            y=0.38,
            w=0.64,
            h=0.12,
            font_size=24,
            color="#5E6A7D",
        )
    )
    cover.add_element(
        SlideElement(
            id="el-cover-panel",
            kind="shape",
            name="Timeline source",
            x=0.72,
            y=0.15,
            w=0.20,
            h=0.46,
            style=ElementStyle(fill="#F3F6FA", stroke="#2F6FED", stroke_width=1.2),
        )
    )
    deck.slides.append(cover)

    for index, clip in enumerate(clips, start=2):
        slide = SlideSpec(
            id=f"slide-{index:03d}",
            title=clip.source_name,
            layout_id="timeline-clip",
            duration_ms=max(2000, min(12000, clip.duration_ms or 5000)),
            metadata={
                "track_id": clip.track_id,
                "clip_id": clip.clip_id,
                "source_path": clip.source_path,
                "timeline_in_ms": clip.timeline_in_ms,
                "source_in_ms": clip.source_in_ms,
                "source_out_ms": clip.source_out_ms,
            },
        )
        slide.add_element(
            SlideElement.text_box(
                f"el-{index}-title",
                clip.source_name,
                x=0.06,
                y=0.07,
                w=0.78,
                h=0.10,
                font_size=34,
                bold=True,
            )
        )
        detail = (
            f"Track {clip.track_id}  |  Clip {clip.clip_id}\n"
            f"Timeline: {clip.timeline_in_ms / 1000:.2f}s  |  Duration: {clip.duration_ms / 1000:.2f}s"
        )
        slide.add_element(
            SlideElement.text_box(
                f"el-{index}-detail",
                detail,
                x=0.07,
                y=0.80,
                w=0.72,
                h=0.10,
                font_size=19,
                color="#5E6A7D",
            )
        )
        source_path = Path(clip.source_path) if clip.source_path else None
        if source_path and source_path.suffix.lower() in _IMAGE_SUFFIXES and source_path.exists():
            slide.add_element(
                SlideElement.image(
                    f"el-{index}-image",
                    source_path,
                    x=0.08,
                    y=0.22,
                    w=0.62,
                    h=0.50,
                    kind="screen_capture",
                    name=clip.source_name,
                )
            )
        else:
            slide.add_element(
                SlideElement(
                    id=f"el-{index}-media",
                    kind="timeline_moment",
                    name="Timeline clip",
                    x=0.08,
                    y=0.22,
                    w=0.62,
                    h=0.50,
                    style=ElementStyle(fill="#F3F6FA", stroke="#2F6FED", stroke_width=1.0),
                    metadata={"source_path": clip.source_path},
                )
            )
        slide.add_element(
            SlideElement.text_box(
                f"el-{index}-path",
                clip.source_path or "No source path",
                x=0.73,
                y=0.24,
                w=0.20,
                h=0.34,
                font_size=16,
                color="#354052",
            )
        )
        deck.slides.append(slide)
    return deck


__all__ = ["TimelineClipSummary", "deck_from_editor_timeline", "timeline_clip_summaries"]
