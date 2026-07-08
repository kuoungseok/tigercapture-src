from __future__ import annotations


def test_programmatic_edit_helpers_update_delete_and_snapshot():
    from app.pptgen.editing import (
        align_element,
        deck_snapshot,
        delete_element,
        duplicate_element,
        set_chart_data,
        set_element_animation,
        set_element_z_order,
        set_table_data,
        update_element,
    )
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec

    slide = SlideSpec(id="slide-001", title="Editable")
    text = SlideElement.text_box("text-1", "Old", x=0.1, y=0.1, w=0.3, h=0.1)
    table = SlideElement.table("table-1", x=0.1, y=0.3, w=0.4, h=0.2)
    chart = SlideElement.chart("chart-1", x=0.55, y=0.3, w=0.3, h=0.2)
    slide.add_element(text)
    slide.add_element(table)
    slide.add_element(chart)
    deck = DeckSpec(id="deck", title="AI Editable", slides=[slide])

    _slide, updated = update_element(deck, "text-1", text="New", x=0.2, style={"font_size": 44})
    assert updated.text == "New"
    assert updated.x == 0.2
    assert updated.style.font_size == 44

    _slide, duplicated = duplicate_element(deck, "text-1")
    assert duplicated.id != "text-1"
    assert duplicated.text == "New"
    assert duplicated.x > updated.x

    _slide, aligned = align_element(deck, duplicated.id, horizontal="center", vertical="bottom")
    assert round(aligned.x, 3) == round((1.0 - aligned.w) / 2.0, 3)
    assert round(aligned.y, 3) == round(1.0 - aligned.h, 3)

    _slide, layered = set_element_z_order(deck, duplicated.id, mode="back")
    assert layered.id == duplicated.id
    assert layered.z_index == 0

    _slide, animated = set_element_animation(deck, "text-1", in_animation="fade_in", start_ms=300, duration_ms=700)
    assert animated.animation.in_animation == "fade_in"
    assert animated.animation.start_ms == 300
    assert animated.animation.duration_ms == 700

    _slide, updated_table = set_table_data(
        deck,
        "table-1",
        cells=[["Item", "A", "B"], ["Total", "12", "=B2*2"]],
        header=True,
    )
    assert updated_table.metadata["rows"] == 2
    assert updated_table.metadata["cols"] == 3
    assert updated_table.metadata["cells"][1][2] == "=B2*2"

    _slide, updated_chart = set_chart_data(deck, "chart-1", labels=["A", "B"], values=["12", "=SUM(10,20)"])
    assert updated_chart.metadata["labels"] == ["A", "B"]
    assert updated_chart.metadata["values"][1] == "=SUM(10,20)"

    snapshot = deck_snapshot(deck, selected_slide_id="slide-001")
    assert snapshot["slide_count"] == 1
    assert {row["id"] for row in snapshot["slides"][0]["elements"]} >= {"text-1", "table-1", "chart-1"}
    text_payload = next(row for row in snapshot["slides"][0]["elements"] if row["id"] == "text-1")
    assert text_payload["animation"]["in_animation"] == "fade_in"

    deleted = delete_element(deck, "text-1")
    assert deleted["element_id"] == "text-1"
    assert {element.id for element in slide.elements} == {duplicated.id, "table-1", "chart-1"}


def test_slide_edit_helpers_add_duplicate_move_update_delete():
    from app.pptgen.editing import add_deck_slide, delete_slide, duplicate_slide, move_deck_slide, update_slide
    from app.pptgen.schema import DeckSpec, SlideSpec

    deck = DeckSpec(id="slides")
    deck.slides.append(SlideSpec(id="slide-001", title="One", duration_ms=1000))

    added = add_deck_slide(deck, title="Two", layout_id="title", duration_ms=2500)
    assert added.id == "slide-002"
    assert added.layout_id == "title"

    clone = duplicate_slide(deck, "slide-001")
    assert clone.id == "slide-001-copy"
    assert deck.slides[1].id == clone.id

    moved = move_deck_slide(deck, added.id, index=0)
    assert moved.id == added.id
    assert deck.slides[0].id == added.id

    updated = update_slide(deck, added.id, title="Updated", duration_ms=3000, speaker_notes="Notes")
    assert updated.title == "Updated"
    assert updated.duration_ms == 3000
    assert updated.speaker_notes == "Notes"

    deleted = delete_slide(deck, clone.id)
    assert deleted["slide_id"] == clone.id
    assert deleted["slide_count"] == 2
