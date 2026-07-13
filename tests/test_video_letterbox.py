import numpy as np

from app.video_letterbox import detect_letterbox_bands, letterbox_mask_from_detection, preserve_letterbox_matte


def test_detect_letterbox_bands_finds_top_and_bottom_matte():
    frame = np.full((80, 120, 3), 92, dtype=np.uint8)
    frame[10:68, :, 1] = np.linspace(48, 180, 58, dtype=np.uint8)[:, None]
    frame[:10, :] = 0
    frame[68:, :] = 2

    detection = detect_letterbox_bands(frame)

    assert detection["ok"] is True
    assert detection["kind"] == "letterbox"
    assert detection["top"] >= 10
    assert detection["bottom"] >= 12
    assert detection["content_rect"][1] >= 10


def test_detect_letterbox_bands_finds_pillarbox_matte():
    frame = np.full((72, 96, 3), 110, dtype=np.uint8)
    frame[:, 12:84, 0] = np.linspace(35, 220, 72, dtype=np.uint8)[:, None]
    frame[:, :12] = 1
    frame[:, 84:] = 1

    detection = detect_letterbox_bands(frame)

    assert detection["ok"] is True
    assert detection["kind"] == "pillarbox"
    assert detection["left"] >= 12
    assert detection["right"] >= 12


def test_detect_letterbox_bands_rejects_all_black_frame():
    frame = np.zeros((64, 64, 3), dtype=np.uint8)

    detection = detect_letterbox_bands(frame)

    assert detection["ok"] is False
    assert detection["kind"] == "none"
    assert detection["content_rect"] == [0, 0, 64, 64]


def test_detect_letterbox_bands_rejects_center_subject_on_black_background():
    h, w = 90, 120
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    subject = ((xx - 60.0) / 32.0) ** 2 + ((yy - 44.0) / 24.0) ** 2 < 1.0
    frame[subject] = [236, 186, 24]

    detection = detect_letterbox_bands(frame)

    assert detection["ok"] is False
    assert detection["kind"] == "none"
    assert detection["content_rect"] == [0, 0, w, h]


def test_detect_letterbox_bands_rejects_large_one_sided_dark_scene_content():
    frame = np.full((90, 140, 3), 92, dtype=np.uint8)
    frame[:55, :, 1] = np.linspace(64, 180, 55, dtype=np.uint8)[:, None]
    frame[55:, :] = np.array([8, 12, 16], dtype=np.uint8)

    detection = detect_letterbox_bands(frame)

    assert detection["ok"] is False
    assert detection["reason"] == "implausible_matte_geometry"
    assert detection["content_rect"] == [0, 0, 140, 90]


def test_detect_letterbox_bands_handles_float_zero_to_one_frames():
    frame = np.full((40, 60, 3), 0.35, dtype=np.float32)
    frame[6:34, :, 1] = np.linspace(0.2, 0.8, 28, dtype=np.float32)[:, None]
    frame[:6, :] = 0.0
    frame[34:, :] = 0.0

    detection = detect_letterbox_bands(frame)

    assert detection["ok"] is True
    assert detection["top"] >= 6
    assert detection["bottom"] >= 6


def test_letterbox_mask_from_detection_marks_only_matte_area():
    detection = {
        "ok": True,
        "top": 3,
        "bottom": 4,
        "left": 2,
        "right": 1,
    }

    mask = letterbox_mask_from_detection(detection, (20, 30))

    assert bool(mask[0, 10]) is True
    assert bool(mask[-1, 10]) is True
    assert bool(mask[10, 0]) is True
    assert bool(mask[10, -1]) is True
    assert bool(mask[10, 10]) is False


def test_preserve_letterbox_matte_restores_processed_matte_pixels():
    source = np.full((50, 70, 3), 90, dtype=np.uint8)
    source[8:42, :, 1] = np.linspace(40, 190, 34, dtype=np.uint8)[:, None]
    source[:8, :] = 0
    source[42:, :] = 0
    processed = np.clip(source.astype(np.int16) + 70, 0, 255).astype(np.uint8)

    restored = preserve_letterbox_matte(source, processed)

    np.testing.assert_array_equal(restored[:8], source[:8])
    np.testing.assert_array_equal(restored[42:], source[42:])
    assert not np.array_equal(restored[20], source[20])
