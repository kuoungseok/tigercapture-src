import numpy as np
import pytest


def test_stabilizer_preview_fast_path_preserves_frame_shape(monkeypatch):
    pytest.importorskip("cv2")
    from app.video_stabilizer import FrameStabilizer, StabilizerParams

    monkeypatch.setenv("TIGERCAPTURE_STABILIZER_PREVIEW_SCALE", "0.5")
    params = StabilizerParams(enabled=True, smoothing_radius=3, crop_ratio=0.02)
    stabilizer = FrameStabilizer(params)
    frame = np.zeros((96, 160, 3), dtype=np.uint8)
    frame[28:68, 48:98] = [220, 80, 40]
    shifted = np.roll(frame, 4, axis=1)

    first = stabilizer.apply_preview(frame)
    second = stabilizer.apply_preview(shifted)

    assert first.shape == frame.shape
    assert second.shape == frame.shape
    assert first.dtype == frame.dtype
    assert second.dtype == frame.dtype
    assert len(stabilizer._transforms) == 2


def test_stabilizer_preview_scale_is_clamped(monkeypatch):
    pytest.importorskip("cv2")
    from app.video_stabilizer import FrameStabilizer, StabilizerParams

    stabilizer = FrameStabilizer(StabilizerParams(enabled=True))
    monkeypatch.setenv("TIGERCAPTURE_STABILIZER_PREVIEW_SCALE", "not-a-number")
    assert stabilizer._preview_scale() == 0.5
    monkeypatch.setenv("TIGERCAPTURE_STABILIZER_PREVIEW_SCALE", "0.01")
    assert stabilizer._preview_scale() == 0.25
    monkeypatch.setenv("TIGERCAPTURE_STABILIZER_PREVIEW_SCALE", "2.0")
    assert stabilizer._preview_scale() == 1.0
