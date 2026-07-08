from __future__ import annotations

import pytest

from app.pptgen.schema import SlideElement, SlideSpec


def test_builtin_template_catalog_contains_media_and_document_layouts():
    from app.pptgen.templates import list_templates

    templates = {template.id: template for template in list_templates()}

    assert "3d_showcase" in templates
    assert "timeline_recap" in templates
    assert "table_chart_report" in templates
    assert templates["3d_showcase"].category == "media"
    assert "3d" in templates["3d_showcase"].tags


def test_slide_from_template_builds_editable_3d_actor_slot():
    from app.pptgen.templates import slide_from_template

    slide = slide_from_template("3d_showcase", slide_id="slide-a", title="Asset Review")
    kinds = {element.kind for element in slide.elements}
    actor = next(element for element in slide.elements if element.kind == "ar_pbr_actor")

    assert slide.id == "slide-a"
    assert slide.layout_id == "3d_showcase"
    assert slide.metadata["template_id"] == "3d_showcase"
    assert {"text", "shape", "ar_pbr_actor"}.issubset(kinds)
    assert actor.metadata["editable_actor"] is True
    assert actor.metadata["slot"] == "ar_pbr_asset"


def test_deck_from_template_can_create_table_chart_report():
    from app.pptgen.templates import deck_from_template

    deck = deck_from_template("table_chart_report", title="Report")
    kinds = {element.kind for element in deck.slides[0].elements}

    assert deck.title == "Report"
    assert deck.metadata["template_id"] == "table_chart_report"
    assert {"table", "chart"}.issubset(kinds)


def test_apply_template_to_slide_replaces_elements_but_keeps_slide_id():
    from app.pptgen.templates import apply_template_to_slide

    slide = SlideSpec(id="slide-original", title="Current")
    slide.add_element(SlideElement.text_box("old", "Old Text", x=0.1, y=0.1, w=0.4, h=0.2))

    updated = apply_template_to_slide(slide, "image_video_hero")

    assert updated is slide
    assert slide.id == "slide-original"
    assert slide.layout_id == "image_video_hero"
    assert slide.metadata["template_id"] == "image_video_hero"
    assert {element.kind for element in slide.elements} == {"text", "video_actor"}


def test_unknown_template_raises_key_error():
    from app.pptgen.templates import slide_from_template

    with pytest.raises(KeyError):
        slide_from_template("missing-template")
