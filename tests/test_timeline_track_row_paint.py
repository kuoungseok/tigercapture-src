from __future__ import annotations

from PySide6.QtCore import QRect

from app.timeline_track_row_paint import (
    _timeline_thumb_blend_width,
    _timeline_thumb_tile_rects,
)


def test_timeline_thumb_tiles_cover_long_clip_with_overlap():
    preview = QRect(100, 12, 920, 44)
    blend = _timeline_thumb_blend_width(240, preview.height())

    rects = _timeline_thumb_tile_rects(preview, 240, blend)

    assert len(rects) > 1
    assert rects[0].left() == preview.left()
    assert rects[-1].right() >= preview.right()
    for prev, nxt in zip(rects, rects[1:]):
        assert prev.right() - nxt.left() + 1 >= blend - 1


def test_timeline_thumb_blend_is_strong_but_never_consumes_tile():
    blend = _timeline_thumb_blend_width(180, 48)

    assert blend >= 48
    assert blend < 180


def test_timeline_thumb_tiles_handle_short_visible_clip():
    preview = QRect(40, 10, 36, 30)
    blend = _timeline_thumb_blend_width(80, preview.height())

    rects = _timeline_thumb_tile_rects(preview, 80, blend)

    assert len(rects) == 1
    assert rects[0].left() == preview.left()
    assert rects[0].right() >= preview.right()
