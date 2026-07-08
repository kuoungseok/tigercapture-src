from __future__ import annotations

import os
from pathlib import Path


def test_ppt_canvas_accepts_timeline_clip_drag_payload(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QMimeData
    from PySide6.QtWidgets import QApplication

    from app.pptgen.drag_payloads import PPT_TIMELINE_CLIP_MIME, set_json_payload
    from app.pptgen.schema import DeckSpec, SlideSpec
    from app.pptgen.ui.window import SlideCanvas

    app = QApplication.instance() or QApplication([])
    assert app is not None

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"fake")
    deck = DeckSpec(id="deck")
    slide = SlideSpec(id="slide-001", title="Drop")
    deck.slides.append(slide)
    canvas = SlideCanvas()
    canvas.resize(640, 360)
    canvas.set_slide(deck, slide)

    mime = QMimeData()
    set_json_payload(
        mime,
        PPT_TIMELINE_CLIP_MIME,
        {
            "schema": "tigercapture.ppt.timeline_clip_drag.v1",
            "track_id": 3,
            "clip_id": 9,
            "source_path": str(source),
            "timeline_in_ms": 1200,
            "duration_ms": 2400,
            "source_in_ms": 100,
            "source_out_ms": 2500,
        },
    )

    created = canvas._add_elements_from_mime(mime, 320, 180)

    assert len(created) == 1
    assert created[0].kind == "video_actor"
    assert created[0].source_path == str(source)
    assert created[0].metadata["source"] == "editor_timeline_drag"
    assert created[0].metadata["track_id"] == 3
    assert created[0].metadata["clip_id"] == 9


def test_ppt_canvas_accepts_typography_drag_payload():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import QMimeData
    from PySide6.QtWidgets import QApplication

    from app.pptgen.drag_payloads import PPT_TYPOGRAPHY_MIME, set_json_payload
    from app.pptgen.schema import DeckSpec, SlideSpec
    from app.pptgen.ui.window import SlideCanvas

    app = QApplication.instance() or QApplication([])
    assert app is not None

    deck = DeckSpec(id="deck")
    slide = SlideSpec(id="slide-001", title="Drop")
    deck.slides.append(slide)
    canvas = SlideCanvas()
    canvas.resize(640, 360)
    canvas.set_slide(deck, slide)

    mime = QMimeData()
    set_json_payload(
        mime,
        PPT_TYPOGRAPHY_MIME,
        {
            "schema": "tigercapture.ppt.typography_drag.v1",
            "text": "Dragged title",
            "duration_ms": 1800,
            "style": {"font_size": 48, "color": "#FF3366", "alignment": "right"},
            "animation": {"preset_id": "basic-fade"},
        },
    )

    created = canvas._add_elements_from_mime(mime, 320, 180)

    assert len(created) == 1
    assert created[0].kind == "typography_actor"
    assert created[0].text == "Dragged title"
    assert created[0].style.color == "#FF3366"
    assert created[0].style.align == "right"
    assert created[0].metadata["source"] == "editor_typography_drag"


def test_media_pool_vrm_drag_exposes_file_url():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QListWidgetItem

    from app.media_asset_routing import vrm_avatar_paths_from_mime
    from app.media_pool import VRM_AVATAR_MIME_TYPE, _MediaPoolList

    app = QApplication.instance() or QApplication([])
    assert app is not None

    item = QListWidgetItem("avatar.vrm")
    item.setData(Qt.ItemDataRole.UserRole, str(Path("E:/assets/avatar.vrm")))
    item.setData(Qt.ItemDataRole.UserRole + 2, "R")
    pool = _MediaPoolList()

    mime = pool.mimeData([item])

    assert mime.hasUrls()
    assert mime.hasFormat(VRM_AVATAR_MIME_TYPE)
    assert [str(path) for path in vrm_avatar_paths_from_mime(mime)] == ["E:\\assets\\avatar.vrm"]
