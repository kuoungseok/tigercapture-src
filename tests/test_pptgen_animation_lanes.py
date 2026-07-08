from __future__ import annotations


def test_animation_lane_rows_sort_by_start_and_expose_payload():
    from app.pptgen.animation_lanes import animation_lane_rows
    from app.pptgen.animations import set_element_animation
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec

    deck = DeckSpec(id="deck")
    slide = SlideSpec(id="slide-001")
    first = SlideElement.text_box("title", "Title", x=0.1, y=0.1, w=0.4, h=0.1)
    second = SlideElement.text_box("badge", "Badge", x=0.1, y=0.3, w=0.2, h=0.1)
    slide.add_element(first)
    slide.add_element(second)
    deck.slides.append(slide)

    set_element_animation(deck, "badge", slide_id=slide.id, in_animation="scale", start_ms=900, duration_ms=300)
    set_element_animation(deck, "title", slide_id=slide.id, in_animation="fade_in", start_ms=100, duration_ms=700)

    rows = animation_lane_rows(deck, slide.id)

    assert [row.element_id for row in rows] == ["title", "badge"]
    assert rows[0].effect == "fade_in"
    assert rows[0].start_ms == 100
    assert rows[0].duration_ms == 700
    assert rows[0].lane_index == 0
    assert rows[1].lane_index == 1
    assert rows[1].to_dict()["trigger"] == "on_slide_start"


def test_animation_lane_rows_skip_non_animated_elements():
    from app.pptgen.animation_lanes import animation_lane_rows_for_slide
    from app.pptgen.schema import SlideElement, SlideSpec

    slide = SlideSpec(id="slide-001")
    slide.add_element(SlideElement.text_box("body", "Body", x=0.1, y=0.1, w=0.4, h=0.1))

    assert animation_lane_rows_for_slide(slide) == []


def test_adjust_animation_timing_move_and_trim_are_clamped():
    from app.pptgen.animation_lanes import AnimationLaneRow, adjust_animation_timing, clamp_animation_timing

    row = AnimationLaneRow(
        slide_id="slide-001",
        element_id="title",
        element_name="Title",
        element_kind="text",
        effect="fade_in",
        trigger="on_slide_start",
        click_index=0,
        start_ms=1000,
        duration_ms=700,
        end_ms=1700,
        z_index=0,
        lane_index=0,
    )

    assert adjust_animation_timing(row, 5000, "move", 3000) == (2300, 700)
    assert adjust_animation_timing(row, -2000, "move", 3000) == (0, 700)
    assert adjust_animation_timing(row, 400, "trim_start", 3000) == (1400, 300)
    assert adjust_animation_timing(row, -2000, "trim_start", 3000) == (0, 1700)
    assert adjust_animation_timing(row, 900, "trim_end", 2200) == (1000, 1200)
    assert adjust_animation_timing(row, -2000, "trim_end", 3000) == (1000, 50)
    assert clamp_animation_timing(2900, 900, 3000) == (2100, 900)


def test_on_click_lane_rows_use_click_index_before_timing_order():
    from app.pptgen.animation_lanes import animation_lane_rows
    from app.pptgen.animations import set_element_animation
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec

    deck = DeckSpec(id="deck")
    slide = SlideSpec(id="slide-001")
    for element_id in ("first", "second", "auto"):
        slide.add_element(SlideElement.text_box(element_id, element_id, x=0.1, y=0.1, w=0.2, h=0.1))
    deck.slides.append(slide)

    set_element_animation(deck, "first", slide_id=slide.id, in_animation="appear", trigger="on_click", click_index=2, start_ms=900)
    set_element_animation(deck, "second", slide_id=slide.id, in_animation="fade_in", trigger="on_click", click_index=1, start_ms=1200)
    set_element_animation(deck, "auto", slide_id=slide.id, in_animation="scale", trigger="on_click", start_ms=100)

    rows = animation_lane_rows(deck, slide.id)

    assert [row.element_id for row in rows] == ["second", "first", "auto"]
    assert [row.click_index for row in rows] == [1, 2, 3]
    assert rows[0].to_dict()["click_index"] == 1
