from __future__ import annotations


def test_ppt_history_stack_undo_redo_and_dedupes():
    from app.pptgen.history import PptHistoryStack, deck_from_history_snapshot
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec

    slide = SlideSpec(id="slide-001", title="History")
    slide.add_element(SlideElement.text_box("title", "Before", x=0.1, y=0.1, w=0.4, h=0.1))
    deck = DeckSpec(id="deck", title="Undoable", slides=[slide])
    history = PptHistoryStack(max_undo_steps=3)
    history.reset(deck)

    assert history.push(deck, "Same") is False
    slide.elements[0].text = "After"
    assert history.push(deck, "Text edit") is True

    restored = deck_from_history_snapshot(history.undo())
    assert restored.slides[0].elements[0].text == "Before"
    restored = deck_from_history_snapshot(history.redo())
    assert restored.slides[0].elements[0].text == "After"


def test_ppt_autosave_uses_project_sibling_or_recovery_root(tmp_path):
    import pytest

    from app.pptgen.autosave import (
        delete_ppt_recovery_file,
        list_ppt_recovery_candidates,
        save_ppt_autosave,
        ppt_autosave_path,
    )
    from app.pptgen.project_io import load_deck_project
    from app.pptgen.schema import DeckSpec, SlideSpec

    deck = DeckSpec(id="deck with spaces", title="Recovery", slides=[SlideSpec(id="slide-001")])
    project_path = tmp_path / "talk.tgppt"

    sibling = ppt_autosave_path(project_path=project_path, deck_id=deck.id)
    assert sibling == tmp_path / "talk.autosave.tgppt"

    recovery = save_ppt_autosave(deck, root=tmp_path)
    assert recovery == tmp_path / "deck_with_spaces.autosave.tgppt"
    assert load_deck_project(recovery).title == "Recovery"

    candidates = list_ppt_recovery_candidates(root=tmp_path)
    assert len(candidates) == 1
    assert candidates[0]["valid"] is True
    assert candidates[0]["title"] == "Recovery"
    assert candidates[0]["slide_count"] == 1

    deleted = delete_ppt_recovery_file(recovery)
    assert deleted["deleted"] is True
    assert not recovery.exists()
    with pytest.raises(ValueError):
        delete_ppt_recovery_file(tmp_path / "real_project.tgppt")
