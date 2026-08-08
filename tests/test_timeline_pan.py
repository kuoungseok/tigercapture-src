from __future__ import annotations


class _FakeBar:
    def __init__(self, value: int = 0, maximum: int = 1000) -> None:
        self._value = int(value)
        self._maximum = int(maximum)

    def value(self) -> int:
        return self._value

    def maximum(self) -> int:
        return self._maximum

    def setValue(self, value: int) -> None:
        self._value = int(value)


class _FakeScroll:
    def __init__(self, bar: _FakeBar) -> None:
        self._bar = bar

    def horizontalScrollBar(self) -> _FakeBar:
        return self._bar


class _FakeOwner:
    def __init__(self, bar: _FakeBar) -> None:
        self._tracks_scroll = _FakeScroll(bar)


def test_timeline_pan_by_clamps_to_scrollbar_range():
    from app.video_editor_timeline_pan import timeline_pan_by

    bar = _FakeBar(value=40, maximum=100)
    owner = _FakeOwner(bar)

    moved = timeline_pan_by(owner, 75)
    assert moved["old_scroll"] == 40
    assert moved["scroll"] == 100
    assert moved["delta_px"] == 60

    moved_back = timeline_pan_by(owner, -500)
    assert moved_back["scroll"] == 0
    assert moved_back["delta_px"] == -100


def test_timeline_pan_to_clamps_absolute_scroll():
    from app.video_editor_timeline_pan import timeline_pan_to

    bar = _FakeBar(value=25, maximum=80)
    owner = _FakeOwner(bar)

    result = timeline_pan_to(owner, 999)
    assert result["old_scroll"] == 25
    assert result["scroll"] == 80
    assert result["delta_px"] == 55


def test_timeline_pan_surface_accepts_track_rows():
    from app.video_editor_timeline_pan import _is_timeline_pan_surface

    row = object()
    owner = type(
        "Owner",
        (),
        {
            "_tracks_scroll": None,
            "_tracks_host": object(),
            "_timeline_ruler": object(),
            "_track_rows": {1: row},
            "_audio_rows": {},
        },
    )()

    assert _is_timeline_pan_surface(owner, row) is True
