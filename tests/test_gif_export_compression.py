"""GIF export compression regression tests.

Before 1.4.3 the compression stage was a no-op in shipped builds: the encoder
delegated size reduction to gifsicle, which was never bundled, so the Lossy
control changed nothing about the output. These tests pin the behaviour that
replaced it — delta encoding has to actually shrink files, the Lossy control
has to actually do something, and neither may produce a file larger than
plain whole-frame encoding.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image, ImageSequence

from app.exporter import GifExportThread, lossy_to_tolerance


WIDTH, HEIGHT = 320, 180
FRAME_COUNT = 24


def _clip(noisy: bool, seed: int = 3) -> list[Image.Image]:
    """A screen-recording-shaped clip: static background, small moving block."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
    base = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    base[..., 0] = (xx * 3) % 256
    base[..., 1] = (yy * 5) % 256
    base[..., 2] = 128

    frames = []
    for i in range(FRAME_COUNT):
        frame = base.copy()
        if noisy:
            noise = rng.integers(-3, 4, frame.shape)
            frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        frame[60:90, 5 + i * 10 : 35 + i * 10] = (255, 0, 0)
        frames.append(Image.fromarray(frame))
    return frames


def _encode(frames, path, *, colors=256, lossy=60, whole=False) -> int:
    thread = GifExportThread(frames, path, fps=15, scale=1.0,
                             max_colors=colors, lossy=lossy)
    steps = len(frames) * 3
    if whole:
        thread._encode_whole_frames(frames, steps)
    else:
        thread._encode_with_pillow(frames, steps)
    return path.stat().st_size


def test_lossy_maps_onto_a_pixel_tolerance():
    assert lossy_to_tolerance(0) == 0
    assert lossy_to_tolerance(60) == 12
    # Monotonic across the values the editor offers.
    levels = [lossy_to_tolerance(v) for v in (0, 30, 60, 80, 120)]
    assert levels == sorted(levels)
    assert levels[0] < levels[-1]


def test_delta_encoding_beats_whole_frame_on_static_background(tmp_path):
    frames = _clip(noisy=False)
    delta = _encode(frames, tmp_path / "delta.gif")
    whole = _encode(frames, tmp_path / "whole.gif", whole=True)
    # Measured around 14x on this shape; assert a floor well under that so
    # the test pins the behaviour without pinning the exact encoder output.
    assert delta * 5 < whole


def test_lossy_setting_changes_the_output(tmp_path):
    """The original bug: Lossy was wired to a stage that never ran."""
    frames = _clip(noisy=True)
    lossless = _encode(frames, tmp_path / "l0.gif", lossy=0)
    lossy = _encode(frames, tmp_path / "l60.gif", lossy=60)
    assert lossy < lossless


def test_encoding_never_regresses_below_whole_frame(tmp_path):
    """Noisy content at zero tolerance must fall back, not bloat."""
    frames = _clip(noisy=True)
    auto = _encode(frames, tmp_path / "auto.gif", lossy=0)
    whole = _encode(frames, tmp_path / "whole.gif", lossy=0, whole=True)
    assert auto <= whole


@pytest.mark.parametrize("noisy", [False, True])
def test_output_preserves_every_frame_and_stays_faithful(tmp_path, noisy):
    frames = _clip(noisy=noisy)
    out = tmp_path / "out.gif"
    _encode(frames, out)

    decoded = [
        np.asarray(f.convert("RGB"), dtype=np.int16)
        for f in ImageSequence.Iterator(Image.open(out))
    ]
    assert len(decoded) == FRAME_COUNT

    # Per-frame mean error stays in normal palette-quantisation territory;
    # a broken delta pass shows up here as drift or smearing.
    for got, want in zip(decoded, frames):
        error = np.abs(got - np.asarray(want, dtype=np.int16)).mean()
        assert error < 12


def test_fewer_colors_produce_smaller_files(tmp_path):
    frames = _clip(noisy=False)
    big = _encode(frames, tmp_path / "c256.gif", colors=256)
    small = _encode(frames, tmp_path / "c64.gif", colors=64)
    assert small < big
