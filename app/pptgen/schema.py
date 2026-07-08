"""Qt-free data model for the user PPT generator."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DECK_SCHEMA_VERSION = 1


def _clamp01(value: float, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        number = float(default)
    return max(0.0, min(1.0, number))


@dataclass
class ThemeSpec:
    id: str = "tc-white-document"
    name: str = "TigerCapture White Document"
    background: str = "#FFFFFF"
    surface: str = "#F3F6FA"
    accent: str = "#2F6FED"
    ink: str = "#182033"
    muted: str = "#5E6A7D"
    font_family: str = "Noto Sans KR"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ThemeSpec":
        if not isinstance(data, dict):
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: data[key] for key in allowed if key in data})


@dataclass
class ElementStyle:
    fill: str | None = None
    stroke: str | None = None
    stroke_width: float = 0.0
    color: str = "#182033"
    font_family: str = "Noto Sans KR"
    font_size: int = 34
    bold: bool = False
    italic: bool = False
    underline: bool = False
    align: str = "left"
    line_height: float = 1.2
    letter_spacing: float = 0.0
    radius: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ElementStyle":
        if not isinstance(data, dict):
            return cls()
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: data[key] for key in allowed if key in data})


@dataclass
class AnimationSpec:
    in_animation: str = "none"
    out_animation: str = "none"
    start_ms: int = 0
    end_ms: int = 0
    duration_ms: int = 450
    trigger: str = "on_slide_start"
    click_index: int = 0
    easing: str = "ease_out"
    motion_x: float = 0.0
    motion_y: float = 0.0
    scale: float = 1.0

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AnimationSpec":
        if not isinstance(data, dict):
            return cls()
        payload = dict(data)
        if "duration_ms" not in payload:
            try:
                start = int(payload.get("start_ms") or 0)
                end = int(payload.get("end_ms") or 0)
                if end > start:
                    payload["duration_ms"] = end - start
            except Exception:
                pass
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: payload[key] for key in allowed if key in payload})


@dataclass
class SlideElement:
    id: str
    kind: str
    name: str = ""
    x: float = 0.1
    y: float = 0.1
    w: float = 0.8
    h: float = 0.2
    rotation: float = 0.0
    z_index: int = 0
    opacity: float = 1.0
    text: str = ""
    source_path: str = ""
    visible: bool = True
    locked: bool = False
    style: ElementStyle = field(default_factory=ElementStyle)
    animation: AnimationSpec = field(default_factory=AnimationSpec)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.x = _clamp01(self.x)
        self.y = _clamp01(self.y)
        self.w = _clamp01(self.w, 0.1)
        self.h = _clamp01(self.h, 0.1)
        self.opacity = _clamp01(self.opacity, 1.0)
        if not self.name:
            self.name = self.kind.replace("_", " ").title()

    @classmethod
    def text_box(
        cls,
        element_id: str,
        text: str,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        font_size: int = 34,
        font_family: str = "Noto Sans KR",
        bold: bool = False,
        italic: bool = False,
        underline: bool = False,
        color: str = "#182033",
        align: str = "left",
        line_height: float = 1.2,
        letter_spacing: float = 0.0,
    ) -> "SlideElement":
        return cls(
            id=element_id,
            kind="text",
            text=text,
            x=x,
            y=y,
            w=w,
            h=h,
            style=ElementStyle(
                font_family=font_family,
                font_size=int(font_size),
                bold=bool(bold),
                italic=bool(italic),
                underline=bool(underline),
                color=color,
                align=align,
                line_height=float(line_height),
                letter_spacing=float(letter_spacing),
            ),
        )

    @classmethod
    def image(
        cls,
        element_id: str,
        source_path: str | Path,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        kind: str = "image",
        name: str = "",
    ) -> "SlideElement":
        return cls(
            id=element_id,
            kind=kind,
            name=name or Path(source_path).stem,
            source_path=str(source_path),
            x=x,
            y=y,
            w=w,
            h=h,
        )

    @classmethod
    def table(
        cls,
        element_id: str,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        rows: int = 3,
        cols: int = 3,
        header: bool = True,
    ) -> "SlideElement":
        row_count = max(1, int(rows or 3))
        col_count = max(1, int(cols or 3))
        cells = [
            [
                f"{'Header' if header and r == 0 else 'Cell'} {r + 1}-{c + 1}"
                for c in range(col_count)
            ]
            for r in range(row_count)
        ]
        return cls(
            id=element_id,
            kind="table",
            name="Table",
            x=x,
            y=y,
            w=w,
            h=h,
            style=ElementStyle(fill="#FFFFFF", stroke="#B8C2D6", stroke_width=1.0, color="#182033", font_size=16),
            metadata={
                "rows": row_count,
                "cols": col_count,
                "header": bool(header),
                "cells": cells,
                "header_fill": "#EAF1FF",
                "body_fill": "#FFFFFF",
                "grid_color": "#B8C2D6",
            },
        )

    @classmethod
    def chart(
        cls,
        element_id: str,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> "SlideElement":
        return cls(
            id=element_id,
            kind="chart",
            name="Chart",
            x=x,
            y=y,
            w=w,
            h=h,
            style=ElementStyle(fill="#F7F9FC", stroke="#2F6FED", stroke_width=1.0, color="#182033", font_size=16),
            metadata={
                "chart_type": "bar",
                "labels": ["A", "B", "C", "D"],
                "values": [32, 58, 44, 72],
            },
        )

    @classmethod
    def line(
        cls,
        element_id: str,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> "SlideElement":
        return cls(
            id=element_id,
            kind="line",
            name="Line",
            x=x,
            y=y,
            w=w,
            h=h,
            style=ElementStyle(fill=None, stroke="#2F6FED", stroke_width=2.0, color="#2F6FED"),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlideElement":
        payload = dict(data)
        payload["style"] = ElementStyle.from_dict(payload.get("style"))
        payload["animation"] = AnimationSpec.from_dict(payload.get("animation"))
        return cls(**payload)


@dataclass
class SlideSpec:
    id: str
    title: str = ""
    layout_id: str = "blank"
    section_id: str = ""
    background: str = ""
    duration_ms: int = 5000
    transition: str = "fade"
    speaker_notes: str = ""
    tags: list[str] = field(default_factory=list)
    elements: list[SlideElement] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_element(self, element: SlideElement) -> None:
        self.elements.append(element)
        self.elements.sort(key=lambda row: int(row.z_index))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlideSpec":
        payload = dict(data)
        payload["elements"] = [
            SlideElement.from_dict(row)
            for row in payload.get("elements", [])
            if isinstance(row, dict)
        ]
        return cls(**payload)


@dataclass
class DeckSpec:
    id: str
    title: str = "Untitled Presentation"
    purpose: str = "user_presentation"
    language: str = "ko"
    aspect_ratio: str = "16:9"
    theme: ThemeSpec = field(default_factory=ThemeSpec)
    slides: list[SlideSpec] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    assets: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = DECK_SCHEMA_VERSION

    def slide_by_id(self, slide_id: str) -> SlideSpec | None:
        for slide in self.slides:
            if slide.id == slide_id:
                return slide
        return None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeckSpec":
        payload = dict(data)
        payload["theme"] = ThemeSpec.from_dict(payload.get("theme"))
        payload["slides"] = [
            SlideSpec.from_dict(row)
            for row in payload.get("slides", [])
            if isinstance(row, dict)
        ]
        return cls(**payload)

    @classmethod
    def from_json(cls, text: str) -> "DeckSpec":
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Deck JSON must be an object")
        return cls.from_dict(data)

    @classmethod
    def sample(cls) -> "DeckSpec":
        deck = cls(id="ppt-sample", title="TigerCapture PPT Generator")
        slide1 = SlideSpec(id="slide-001", title="Timeline-native presentations", layout_id="cover", duration_ms=6000)
        slide1.add_element(
            SlideElement.text_box(
                "el-title",
                "Timeline-native\nPPT Studio",
                x=0.07,
                y=0.12,
                w=0.58,
                h=0.28,
                font_size=52,
                bold=True,
            )
        )
        slide1.add_element(
            SlideElement.text_box(
                "el-subtitle",
                "Slides become clips. TigerCapture renders rich media, then exports PPTX.",
                x=0.08,
                y=0.48,
                w=0.55,
                h=0.13,
                font_size=23,
                color="#5E6A7D",
            )
        )
        slide1.add_element(
            SlideElement(
                id="el-hero",
                kind="ar_pbr_render",
                name="AR/PBR render placeholder",
                x=0.68,
                y=0.15,
                w=0.25,
                h=0.56,
                z_index=1,
                style=ElementStyle(fill="#F3F6FA", stroke="#2F6FED", stroke_width=1.2),
                metadata={"render_intent": "3d beauty still"},
            )
        )
        slide2 = SlideSpec(id="slide-002", title="Asset pipeline", layout_id="three-card", duration_ms=5000)
        slide2.add_element(SlideElement.text_box("el-2-title", "Bring more than images", x=0.07, y=0.08, w=0.72, h=0.1, font_size=38, bold=True))
        for idx, (label, body, color) in enumerate(
            [
                ("3D", "AR/PBR renders become premium slide assets.", "#2F6FED"),
                ("Actors", "MMD, Live2D, and Spine can be baked with alpha.", "#D88716"),
                ("Timeline", "Markers, clips, titles, and grades become slide moments.", "#3A8F5A"),
            ]
        ):
            slide2.add_element(
                SlideElement(
                    id=f"el-card-{idx}",
                    kind="shape",
                    name=label,
                    x=0.07 + idx * 0.30,
                    y=0.28,
                    w=0.25,
                    h=0.42,
                    z_index=0,
                    style=ElementStyle(fill="#F7F9FC", stroke=color, stroke_width=1.0),
                )
            )
            slide2.add_element(
                SlideElement.text_box(
                    f"el-card-text-{idx}",
                    f"{label}\n{body}",
                    x=0.095 + idx * 0.30,
                    y=0.33,
                    w=0.20,
                    h=0.28,
                    font_size=22,
                    bold=False,
                    color="#182033",
                )
            )
        slide3 = SlideSpec(id="slide-003", title="Implementation scope", layout_id="body", duration_ms=4500)
        slide3.add_element(SlideElement.text_box("el-3-title", "Implementation scope", x=0.07, y=0.08, w=0.65, h=0.1, font_size=40, bold=True))
        slide3.add_element(
            SlideElement.text_box(
                "el-3-body",
                "This implementation includes a DeckSpec model, slide timeline, validation, PNG preview, PPTX export, and a standalone PySide window.",
                x=0.08,
                y=0.26,
                w=0.78,
                h=0.32,
                font_size=27,
                color="#354052",
            )
        )
        deck.slides.extend([slide1, slide2, slide3])
        return deck


__all__ = [
    "AnimationSpec",
    "DeckSpec",
    "ElementStyle",
    "SlideElement",
    "SlideSpec",
    "ThemeSpec",
]
