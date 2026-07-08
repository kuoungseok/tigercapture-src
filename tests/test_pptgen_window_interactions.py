from __future__ import annotations

import os
import time


def test_window_delete_selected_element_removes_it():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    slide = SlideSpec(id="slide-001", title="Delete")
    first = SlideElement.text_box("el-1", "A", x=0.1, y=0.1, w=0.2, h=0.1)
    second = SlideElement.text_box("el-2", "B", x=0.3, y=0.1, w=0.2, h=0.1)
    slide.add_element(first)
    slide.add_element(second)
    deck = DeckSpec(id="deck", slides=[slide])
    window = PptGeneratorWindow(deck)
    window.selected_element_id = first.id
    window._refresh_selected()

    assert window._delete_selected_element() is True
    assert [element.id for element in slide.elements] == ["el-2"]
    assert window.selected_element_id == "el-2"


def test_window_loads_and_replaces_image_file(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PIL import Image
    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    image_path = tmp_path / "hero.png"
    Image.new("RGB", (80, 48), (220, 40, 80)).save(image_path)

    slide = SlideSpec(id="slide-001", title="Image")
    placeholder = SlideElement(
        id="image-slot",
        kind="image_placeholder",
        name="Image Slot",
        x=0.2,
        y=0.2,
        w=0.3,
        h=0.2,
        style=ElementStyle(fill="#F3F6FA", stroke="#2F6FED", stroke_width=1.0),
    )
    slide.add_element(placeholder)
    deck = DeckSpec(id="deck", slides=[slide])
    window = PptGeneratorWindow(deck)

    inserted = window.add_image_file_to_slide(image_path)
    assert inserted.kind == "image"
    assert inserted.source_path == str(image_path)
    assert inserted.id in {element.id for element in slide.elements}

    replaced = window.add_image_file_to_slide(image_path, replace_element_id="image-slot")
    assert replaced.id == "image-slot"
    assert replaced.kind == "image"
    assert replaced.x == 0.2
    assert replaced.w == 0.3


def test_window_previews_element_animation_from_timeline_playhead():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    slide = SlideSpec(id="slide-001", title="Animated", duration_ms=2000)
    element = SlideElement.text_box("title", "Animated", x=0.1, y=0.1, w=0.4, h=0.12)
    element.animation.in_animation = "fade_in"
    element.animation.start_ms = 300
    element.animation.duration_ms = 600
    slide.add_element(element)
    window = PptGeneratorWindow(DeckSpec(id="deck", slides=[slide]))

    window.timeline.playhead_ms = 0
    window._timeline_playhead_changed()
    before = window.canvas._animation_state(element)
    assert before["visible"] is False

    window.timeline.playhead_ms = 600
    window._timeline_playhead_changed()
    middle = window.canvas._animation_state(element)
    assert middle["visible"] is True
    assert 0.0 < float(middle["opacity"]) < 1.0

    window.timeline.playhead_ms = 1200
    window._timeline_playhead_changed()
    after = window.canvas._animation_state(element)
    assert after["visible"] is True
    assert float(after["opacity"]) == 1.0


def test_window_ppt_playback_advances_playhead():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    slide = SlideSpec(id="slide-001", title="Animated", duration_ms=2000)
    window = PptGeneratorWindow(DeckSpec(id="deck", slides=[slide]))
    window.timeline.playhead_ms = 100
    window._ppt_playing = True
    window._ppt_last_tick = time.monotonic() - 0.10

    window._advance_ppt_playback()
    window._ppt_play_timer.stop()

    assert window.timeline.playhead_ms > 100


def test_window_undo_redo_restores_deck_edits():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    slide = SlideSpec(id="slide-001", title="Undo")
    element = SlideElement.text_box("title", "Before", x=0.1, y=0.1, w=0.4, h=0.1)
    slide.add_element(element)
    window = PptGeneratorWindow(DeckSpec(id="deck", slides=[slide]))

    window.deck.slides[0].elements[0].text = "After"
    window._refresh_selected()
    assert window._history.can_undo() is True

    window._undo_ppt()
    assert window.deck.slides[0].elements[0].text == "Before"
    assert window._history.can_redo() is True

    window._redo_ppt()
    assert window.deck.slides[0].elements[0].text == "After"


def test_window_opens_recovery_copy_as_unsaved_dirty_deck(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.project_io import save_deck_project
    from app.pptgen.schema import DeckSpec, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    recovery = DeckSpec(id="recovered", title="Recovered Deck", slides=[SlideSpec(id="slide-001")])
    recovery_path = save_deck_project(recovery, tmp_path / "deck.autosave.tgppt")

    window = PptGeneratorWindow(DeckSpec(id="deck", slides=[SlideSpec(id="slide-old")]))
    result = window.open_recovery_copy(recovery_path)

    assert result["title"] == "Recovered Deck"
    assert window.deck.id == "recovered"
    assert window.project_path is None
    assert window._dirty is True
    assert window._autosave_path == recovery_path


def test_window_save_cleans_current_recovery_copy(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.autosave import save_ppt_autosave
    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    slide = SlideSpec(id="slide-001", title="Save")
    slide.add_element(SlideElement.text_box("title", "Before", x=0.1, y=0.1, w=0.4, h=0.1))
    deck = DeckSpec(id="deck", title="Save Deck", slides=[slide])
    window = PptGeneratorWindow(deck)
    window.project_path = tmp_path / "deck.tgppt"
    window.deck.slides[0].elements[0].text = "After"
    window._refresh_selected()
    recovery_path = save_ppt_autosave(window.deck, root=tmp_path)
    window._autosave_path = recovery_path

    assert recovery_path.exists()
    assert window._save_deck() is True
    assert window.project_path.exists()
    assert window._dirty is False
    assert window._autosave_path is None
    assert not recovery_path.exists()


def test_window_element_copy_paste_duplicate_layer_and_align():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication

    from app.pptgen.schema import DeckSpec, SlideElement, SlideSpec
    from app.pptgen.ui.window import PptGeneratorWindow

    app = QApplication.instance() or QApplication([])
    assert app is not None

    slide = SlideSpec(id="slide-001", title="Edit")
    first = SlideElement.text_box("title", "Title", x=0.1, y=0.1, w=0.4, h=0.1)
    second = SlideElement.text_box("body", "Body", x=0.2, y=0.3, w=0.3, h=0.1)
    slide.add_element(first)
    slide.add_element(second)
    window = PptGeneratorWindow(DeckSpec(id="deck", slides=[slide]))
    window.selected_element_id = "title"
    window._refresh_selected()

    assert window._copy_selected_element() is True
    pasted = window._paste_element()
    assert pasted is not None
    assert pasted.id != "title"
    assert len(window.deck.slides[0].elements) == 3

    duplicated = window._duplicate_selected_element()
    assert duplicated is not None
    assert len(window.deck.slides[0].elements) == 4

    aligned = window._align_selected_element(horizontal="center", vertical="bottom")
    assert aligned is not None
    assert round(aligned.x, 3) == round((1.0 - aligned.w) / 2.0, 3)
    assert round(aligned.y, 3) == round(1.0 - aligned.h, 3)

    layered = window._set_selected_z_order("back")
    assert layered is not None
    assert layered.z_index == 0
