"""Built-in slide templates for the user PPT generator."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable

from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec
from app.pptgen.timeline import PptTimeline


@dataclass(frozen=True)
class PptTemplateSpec:
    id: str
    name: str
    category: str
    description: str
    layout_id: str
    tags: tuple[str, ...] = field(default_factory=tuple)


TemplateBuilder = Callable[[str, str], SlideSpec]


def _text(
    element_id: str,
    text: str,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    font_size: int,
    bold: bool = False,
    color: str = "#182033",
    align: str = "left",
    slot: str = "",
) -> SlideElement:
    element = SlideElement.text_box(
        element_id,
        text,
        x=x,
        y=y,
        w=w,
        h=h,
        font_size=font_size,
        bold=bold,
        color=color,
        align=align,
    )
    if slot:
        element.metadata["slot"] = slot
    return element


def _shape(
    element_id: str,
    name: str,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = "#F7F9FC",
    stroke: str = "#B8C2D6",
    slot: str = "",
) -> SlideElement:
    element = SlideElement(
        id=element_id,
        kind="shape",
        name=name,
        x=x,
        y=y,
        w=w,
        h=h,
        style=ElementStyle(fill=fill, stroke=stroke, stroke_width=1.0),
    )
    if slot:
        element.metadata["slot"] = slot
    return element


def _actor(
    element_id: str,
    kind: str,
    name: str,
    *,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    stroke: str,
    color: str = "#182033",
    slot: str = "",
) -> SlideElement:
    element = SlideElement(
        id=element_id,
        kind=kind,
        name=name,
        x=x,
        y=y,
        w=w,
        h=h,
        style=ElementStyle(fill=fill, stroke=stroke, stroke_width=1.4, color=color, font_size=18, bold=True),
        metadata={"editable_actor": True, "slot": slot or kind},
    )
    return element


def _slide(slide_id: str, title: str, layout_id: str, *, duration_ms: int = 5000) -> SlideSpec:
    return SlideSpec(
        id=slide_id,
        title=title,
        layout_id=layout_id,
        duration_ms=duration_ms,
        metadata={"template_id": layout_id},
    )


def _blank(slide_id: str, title: str) -> SlideSpec:
    return _slide(slide_id, title or "Blank", "blank")


def _title(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Title", "title")
    slide.add_element(_text("el-title", "Presentation Title", x=0.09, y=0.30, w=0.72, h=0.14, font_size=50, bold=True, slot="title"))
    slide.add_element(_text("el-subtitle", "Subtitle or short description", x=0.10, y=0.50, w=0.62, h=0.08, font_size=24, color="#5E6A7D", slot="subtitle"))
    return slide


def _title_body(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Title + Body", "title_body")
    slide.add_element(_text("el-title", "Slide Title", x=0.07, y=0.08, w=0.78, h=0.10, font_size=40, bold=True, slot="title"))
    slide.add_element(_text("el-body", "Add body text, bullets, or presenter notes here.", x=0.09, y=0.27, w=0.76, h=0.40, font_size=28, color="#354052", slot="body"))
    return slide


def _two_column(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Two Column", "two_column")
    slide.add_element(_text("el-title", "Compare Two Ideas", x=0.07, y=0.07, w=0.78, h=0.09, font_size=38, bold=True, slot="title"))
    slide.add_element(_shape("el-left-box", "Left Content", x=0.07, y=0.23, w=0.39, h=0.48, fill="#F7F9FC", stroke="#2F6FED", slot="left_content"))
    slide.add_element(_shape("el-right-box", "Right Content", x=0.54, y=0.23, w=0.39, h=0.48, fill="#FFF7E8", stroke="#D88716", slot="right_content"))
    return slide


def _image_video_hero(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Image / Video Hero", "image_video_hero")
    slide.add_element(_actor("el-media", "video_actor", "Video / Image", x=0.06, y=0.14, w=0.54, h=0.58, fill="#101722", stroke="#2F6FED", color="#EAF2FF", slot="hero_media"))
    slide.add_element(_text("el-title", "Media Story", x=0.66, y=0.18, w=0.26, h=0.15, font_size=36, bold=True, slot="title"))
    slide.add_element(_text("el-body", "Drop media onto the slot.", x=0.67, y=0.40, w=0.24, h=0.22, font_size=20, color="#5E6A7D", slot="body"))
    return slide


def _showcase_3d(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "3D Object Showcase", "3d_showcase")
    slide.add_element(_text("el-title", "3D / AR-PBR Showcase", x=0.07, y=0.07, w=0.70, h=0.09, font_size=38, bold=True, slot="title"))
    slide.add_element(_actor("el-3d", "ar_pbr_actor", "3D Object", x=0.49, y=0.19, w=0.38, h=0.56, fill="#F3F6FA", stroke="#3A8F5A", slot="ar_pbr_asset"))
    slide.add_element(_shape("el-details", "Details", x=0.08, y=0.24, w=0.32, h=0.36, fill="#F7F9FC", stroke="#B8C2D6", slot="details"))
    slide.add_element(_text("el-caption", "Drop a 3D asset here.", x=0.10, y=0.64, w=0.30, h=0.10, font_size=18, color="#5E6A7D", slot="caption"))
    return slide


def _timeline_recap(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Timeline Recap", "timeline_recap")
    slide.add_element(_text("el-title", "Timeline Recap", x=0.07, y=0.07, w=0.78, h=0.09, font_size=38, bold=True, slot="title"))
    for idx in range(3):
        x = 0.08 + idx * 0.30
        slide.add_element(_actor(f"el-moment-{idx + 1}", "video_actor", f"Moment {idx + 1}", x=x, y=0.25, w=0.24, h=0.28, fill="#101722", stroke="#2F6FED", color="#EAF2FF", slot=f"timeline_moment_{idx + 1}"))
        slide.add_element(_text(f"el-label-{idx + 1}", f"{idx + 1}. Key moment", x=x, y=0.58, w=0.24, h=0.07, font_size=17, color="#354052", align="center", slot=f"moment_label_{idx + 1}"))
    return slide


def _table_chart(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Table / Chart Report", "table_chart_report")
    slide.add_element(_text("el-title", "Report Summary", x=0.07, y=0.07, w=0.78, h=0.09, font_size=38, bold=True, slot="title"))
    table = SlideElement.table("el-table", x=0.07, y=0.22, w=0.38, h=0.42, rows=4, cols=3)
    table.metadata["slot"] = "table_data"
    slide.add_element(table)
    chart = SlideElement.chart("el-chart", x=0.54, y=0.22, w=0.36, h=0.42)
    chart.metadata["slot"] = "chart_data"
    slide.add_element(chart)
    return slide


def _typography_title(slide_id: str, title: str) -> SlideSpec:
    slide = _slide(slide_id, title or "Typography Title", "typography_title")
    element = _text("el-typo", "Bold Typography", x=0.11, y=0.32, w=0.78, h=0.18, font_size=56, bold=True, color="#2F6FED", align="center", slot="typography")
    element.kind = "typography_actor"
    element.name = "Typography Title"
    element.metadata["editable_actor"] = True
    slide.add_element(element)
    slide.add_element(_text("el-subtitle", "Use TigerCapture typography presets on presentation pages.", x=0.20, y=0.54, w=0.60, h=0.08, font_size=21, color="#5E6A7D", align="center", slot="subtitle"))
    return slide


_BUILDERS: dict[str, TemplateBuilder] = {
    "blank": _blank,
    "title": _title,
    "title_body": _title_body,
    "two_column": _two_column,
    "image_video_hero": _image_video_hero,
    "3d_showcase": _showcase_3d,
    "timeline_recap": _timeline_recap,
    "table_chart_report": _table_chart,
    "typography_title": _typography_title,
}


_TEMPLATES: tuple[PptTemplateSpec, ...] = (
    PptTemplateSpec("blank", "Blank", "basic", "Empty white slide.", "blank"),
    PptTemplateSpec("title", "Title", "basic", "Large title and subtitle.", "title"),
    PptTemplateSpec("title_body", "Title + Body", "basic", "Title with a large body text area.", "title_body"),
    PptTemplateSpec("two_column", "Two Column", "basic", "Side-by-side content panels.", "two_column"),
    PptTemplateSpec("image_video_hero", "Image / Video Hero", "media", "Large media slot with supporting copy.", "image_video_hero", ("video", "image", "media")),
    PptTemplateSpec("3d_showcase", "3D Object Showcase", "media", "AR/PBR object slot with details panel.", "3d_showcase", ("3d", "ar-pbr")),
    PptTemplateSpec("timeline_recap", "Timeline Recap", "editor", "Three timeline moments as slide media actors.", "timeline_recap", ("timeline", "video")),
    PptTemplateSpec("table_chart_report", "Table / Chart Report", "report", "Editable table next to a chart.", "table_chart_report", ("table", "chart")),
    PptTemplateSpec("typography_title", "Typography Title", "typography", "Large typography actor title page.", "typography_title", ("typography", "title")),
)


def list_templates() -> list[PptTemplateSpec]:
    return list(_TEMPLATES)


def template_by_id(template_id: str) -> PptTemplateSpec | None:
    wanted = str(template_id or "").strip()
    for template in _TEMPLATES:
        if template.id == wanted:
            return template
    return None


def slide_from_template(template_id: str, *, slide_id: str = "slide-001", title: str = "") -> SlideSpec:
    template = template_by_id(template_id)
    if template is None:
        raise KeyError(f"Unknown PPT template: {template_id}")
    builder = _BUILDERS[template.id]
    slide = builder(slide_id, title or template.name)
    slide.metadata["template_id"] = template.id
    slide.metadata["template_name"] = template.name
    return slide


def deck_from_template(template_id: str, *, deck_id: str = "template-deck", title: str = "") -> DeckSpec:
    template = template_by_id(template_id)
    if template is None:
        raise KeyError(f"Unknown PPT template: {template_id}")
    deck = DeckSpec(id=deck_id, title=title or template.name)
    deck.metadata["template_id"] = template.id
    deck.metadata["template_name"] = template.name
    deck.slides.append(slide_from_template(template.id, slide_id="slide-001", title=template.name))
    return deck


def apply_template_to_slide(slide: SlideSpec, template_id: str, *, title: str = "") -> SlideSpec:
    replacement = slide_from_template(template_id, slide_id=slide.id, title=title or slide.title)
    slide.title = replacement.title
    slide.layout_id = replacement.layout_id
    slide.background = replacement.background
    slide.duration_ms = replacement.duration_ms
    slide.transition = replacement.transition
    slide.elements = [copy.deepcopy(element) for element in replacement.elements]
    slide.metadata.update(replacement.metadata)
    return slide


def rebuild_timeline(deck: DeckSpec) -> PptTimeline:
    return PptTimeline.from_deck(deck)


__all__ = [
    "PptTemplateSpec",
    "apply_template_to_slide",
    "deck_from_template",
    "list_templates",
    "rebuild_timeline",
    "slide_from_template",
    "template_by_id",
]
