from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from app import video_editor_preview_recovery as recovery


class FakeImage:
    def __init__(self, width: int, height: int, color: tuple[int, int, int]):
        self._width = int(width)
        self._height = int(height)
        self._color = tuple(int(c) for c in color)

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def bytesPerLine(self) -> int:
        return self._width * 3

    def bits(self) -> bytes:
        pixel = bytes(self._color)
        row = pixel * self._width
        return row * self._height

    def convertToFormat(self, _format):
        return self

    def scaled(self, width: int, height: int, *_args):
        return FakeImage(width, height, self._color)


class FakePixmap:
    def __init__(
        self,
        width_or_pixmap=None,
        height: int | None = None,
        color: tuple[int, int, int] = (0, 0, 0),
        *,
        null: bool = False,
    ):
        if isinstance(width_or_pixmap, FakePixmap):
            other = width_or_pixmap
            self._width = other._width
            self._height = other._height
            self._color = other._color
            self._null = other._null
            self.copied_from = other
            return
        self._width = int(width_or_pixmap or 0)
        self._height = int(height or 0)
        self._color = tuple(int(c) for c in color)
        self._null = bool(null)
        self.copied_from = None

    def isNull(self) -> bool:
        return self._null

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def toImage(self) -> FakeImage:
        return FakeImage(self._width, self._height, self._color)

    def copy(self):
        return FakePixmap(self)


class UnreadableImage:
    def width(self) -> int:
        return 1280

    def height(self) -> int:
        return 720

    def bytesPerLine(self) -> int:
        return 1280 * 3

    def bits(self):
        raise RuntimeError("pixel buffer unavailable")

    def convertToFormat(self, _format):
        return self

    def scaled(self, width: int, height: int, *_args):
        return self


class UnreadablePixmap(FakePixmap):
    def __init__(self):
        super().__init__(1280, 720, (0, 0, 0))

    def toImage(self):
        return UnreadableImage()


class FakeOwner:
    def __init__(
        self,
        *,
        current: FakePixmap | None = None,
        last_good: FakePixmap | None = None,
        tab_guard: bool = True,
        black_guard: bool = False,
        renderable: bool = True,
    ):
        self._preview_pixmap = current
        self._last_good_preview_pixmap = last_good
        self.tab_guard = tab_guard
        self.black_guard = black_guard
        self.renderable = renderable
        self.scale_calls = 0
        self._preview_popout = None

    def _preview_tab_guard_active(self) -> bool:
        return self.tab_guard

    def _preview_black_recovery_active(self) -> bool:
        return self.black_guard

    def _active_renderable_clip_at_current_position(self) -> bool:
        return self.renderable

    def _scale_preview_to_fit(self) -> None:
        self.scale_calls += 1


def test_blank_preview_contract_only_matches_tiny_placeholder_pixmaps():
    assert recovery.pixmap_looks_like_blank_preview(None)
    assert recovery.pixmap_looks_like_blank_preview(FakePixmap(null=True))
    assert recovery.pixmap_looks_like_blank_preview(FakePixmap(16, 9))

    actual_black_scene = FakePixmap(1280, 720, (0, 0, 0))

    assert not recovery.pixmap_looks_like_blank_preview(actual_black_scene)


def test_black_frame_contract_requires_near_zero_sampled_pixels():
    assert recovery.pixmap_looks_like_black_frame(FakePixmap(1280, 720, (0, 0, 0)))

    nearly_black_but_visible = FakePixmap(1280, 720, (4, 0, 0))
    colored_frame = FakePixmap(1280, 720, (24, 12, 8))

    assert not recovery.pixmap_looks_like_black_frame(nearly_black_but_visible)
    assert not recovery.pixmap_looks_like_black_frame(colored_frame)


def test_black_frame_contract_does_not_guess_black_when_pixels_are_unreadable():
    assert not recovery.pixmap_looks_like_black_frame(UnreadablePixmap())


def test_restore_guard_recovers_blank_preview_from_last_good_pixmap():
    blank = FakePixmap(16, 9, (0, 0, 0))
    good = FakePixmap(96, 54, (255, 128, 87))
    popout = SimpleNamespace(frames=[])
    popout.update_frame = lambda image: popout.frames.append(image)
    owner = FakeOwner(current=blank, last_good=good)
    owner._preview_popout = popout

    restored = recovery.restore_preview_if_tab_switch_blank(owner)

    assert restored is True
    assert owner._preview_pixmap is not good
    assert owner._preview_pixmap.copied_from is good
    assert owner._preview_pixmap.width() == 96
    assert owner._preview_pixmap.height() == 54
    assert owner.scale_calls == 1
    assert len(popout.frames) == 1


def test_restore_guard_does_not_replace_large_black_scene_without_black_guard():
    actual_black_scene = FakePixmap(1280, 720, (0, 0, 0))
    good = FakePixmap(96, 54, (255, 128, 87))
    owner = FakeOwner(
        current=actual_black_scene,
        last_good=good,
        tab_guard=True,
        black_guard=False,
    )

    restored = recovery.restore_preview_if_tab_switch_blank(owner)

    assert restored is False
    assert owner._preview_pixmap is actual_black_scene
    assert owner.scale_calls == 0


def test_restore_guard_replaces_black_frame_only_during_black_recovery_window():
    transient_black = FakePixmap(1280, 720, (0, 0, 0))
    good = FakePixmap(96, 54, (255, 128, 87))
    owner = FakeOwner(
        current=transient_black,
        last_good=good,
        tab_guard=True,
        black_guard=True,
    )

    restored = recovery.restore_preview_if_tab_switch_blank(owner)

    assert restored is True
    assert owner._preview_pixmap.copied_from is good
    assert owner._preview_pixmap.width() == 96
    assert owner.scale_calls == 1


def test_restore_guard_requires_tab_guard_and_renderable_content():
    blank = FakePixmap(16, 9)
    good = FakePixmap(96, 54, (255, 128, 87))

    inactive_guard = FakeOwner(current=blank, last_good=good, tab_guard=False)
    unrenderable = FakeOwner(current=blank, last_good=good, renderable=False)

    assert not recovery.restore_preview_if_tab_switch_blank(inactive_guard)
    assert not recovery.restore_preview_if_tab_switch_blank(unrenderable)
    assert inactive_guard._preview_pixmap is blank
    assert unrenderable._preview_pixmap is blank


def test_preview_recovery_source_prefers_current_nonblank_then_last_good():
    current = FakePixmap(640, 360, (24, 12, 8))
    last_good = FakePixmap(96, 54, (255, 128, 87))
    owner = FakeOwner(current=current, last_good=last_good)

    source = recovery.preview_recovery_source(owner)

    assert source is not current
    assert source.copied_from is current

    owner._preview_pixmap = FakePixmap(16, 9)
    source = recovery.preview_recovery_source(owner)

    assert source is not last_good
    assert source.copied_from is last_good


def test_remember_good_preview_pixmap_skips_blank_and_unrenderable_frames():
    good = FakePixmap(96, 54, (255, 128, 87))
    blank_owner = FakeOwner(current=FakePixmap(16, 9), last_good=None)
    unrenderable_owner = FakeOwner(current=good, last_good=None, renderable=False)
    owner = FakeOwner(current=good, last_good=None, renderable=True)

    assert not recovery.remember_good_preview_pixmap(blank_owner)
    assert not recovery.remember_good_preview_pixmap(unrenderable_owner)
    assert recovery.remember_good_preview_pixmap(owner)
    assert owner._last_good_preview_pixmap is not good
    assert owner._last_good_preview_pixmap.copied_from is good


def test_preview_recovery_rgb_skips_tiny_placeholder_and_copies_good_rgb():
    owner = SimpleNamespace(
        _last_good_preview_rgb=np.zeros((9, 16, 3), dtype=np.uint8)
    )

    assert recovery.preview_recovery_rgb(owner) is None

    rgb = np.ones((40, 64, 3), dtype=np.uint8)
    owner._last_good_preview_rgb = rgb

    recovered = recovery.preview_recovery_rgb(owner)
    rgb[0, 0, 0] = 99

    assert recovered.shape == (40, 64, 3)
    assert recovered.flags["C_CONTIGUOUS"]
    assert recovered[0, 0, 0] == 1
