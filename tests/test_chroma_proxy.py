import os
import sys
import time
from types import SimpleNamespace

import numpy as np


def test_chroma_key_open_cv_lut_masks_key_color():
    from app.chroma_key import ChromaKeyParams

    rgb = np.array(
        [
            [[0, 255, 0], [255, 0, 0]],
            [[0, 180, 0], [32, 32, 32]],
        ],
        dtype=np.uint8,
    )
    params = ChromaKeyParams(
        enabled=True,
        key_hue=60,
        hue_range=30,
        sat_min=40,
        val_min=40,
        spill_suppress=0.0,
    )

    result, alpha = params.apply(rgb)

    assert result.shape == rgb.shape
    assert alpha.dtype == np.uint8
    assert alpha[0, 0] < 8
    assert alpha[1, 0] < 8
    assert alpha[0, 1] == 255
    assert alpha[1, 1] == 255


def test_chroma_key_returns_opaque_when_no_pixels_match():
    from app.chroma_key import ChromaKeyParams

    rgb = np.full((3, 4, 3), [255, 0, 0], dtype=np.uint8)
    params = ChromaKeyParams(
        enabled=True,
        key_hue=60,
        hue_range=20,
        sat_min=40,
        val_min=40,
    )

    result, alpha = params.apply(rgb)

    np.testing.assert_array_equal(result, rgb)
    assert np.all(alpha == 255)


def test_proxy_state_tracks_missing_ready_stale_and_delete(tmp_path):
    from app.video_editor_window import (
        _delete_proxy_for_source,
        _proxy_path_for,
        _proxy_state_for,
    )

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")

    assert _proxy_state_for(source) == "missing"

    proxy = _proxy_path_for(source)
    proxy.parent.mkdir()
    proxy.write_bytes(b"proxy")
    now = time.time()
    os.utime(source, (now - 20, now - 20))
    os.utime(proxy, (now, now))
    assert _proxy_state_for(source) == "ready"

    os.utime(source, (now + 20, now + 20))
    os.utime(proxy, (now - 20, now - 20))
    assert _proxy_state_for(source) == "stale"

    assert _delete_proxy_for_source(source) is True
    assert _proxy_state_for(source) == "missing"


def test_video_filter_preview_fast_path_preserves_shape_and_dtype():
    from app.video_filters import VideoFilterParams

    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    rgb[:, :, 0] = 120
    rgb[:, :, 1] = 80
    rgb[:, :, 2] = 40
    params = VideoFilterParams(
        sharpen=0.6,
        vignette=0.35,
        vignette_feather=0.7,
        chroma_aberration=0.1,
    )

    out = params.apply_preview(rgb)

    assert out.shape == rgb.shape
    assert out.dtype == np.uint8


def test_chroma_key_preview_fast_path_preserves_shape_and_dtype(monkeypatch):
    from app.chroma_key import ChromaKeyParams

    monkeypatch.setenv("TIGERCAPTURE_CHROMA_PREVIEW_SCALE", "0.5")
    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    rgb[:, :, 1] = 255
    params = ChromaKeyParams(
        enabled=True,
        key_hue=60,
        hue_range=30,
        sat_min=40,
        val_min=40,
        spill_suppress=0.25,
    )

    out, alpha = params.apply_preview(rgb)

    assert out.shape == rgb.shape
    assert alpha.shape == rgb.shape[:2]
    assert out.dtype == np.uint8
    assert alpha.dtype == np.uint8


def test_filter_chroma_preview_batch_preserves_shape_and_dtype(monkeypatch):
    from app.chroma_key import ChromaKeyParams
    from app.preview_effects import apply_filter_chroma_preview_batch
    from app.video_filters import VideoFilterParams

    monkeypatch.delenv("TIGERCAPTURE_DISABLE_FILTER_CHROMA_BATCH", raising=False)
    rgb = np.zeros((720, 1280, 3), dtype=np.uint8)
    rgb[:, :, 1] = 255
    filters = VideoFilterParams(
        sharpen=0.4,
        vignette=0.3,
        vignette_feather=0.7,
        chroma_aberration=0.1,
    )
    chroma = ChromaKeyParams(
        enabled=True,
        key_hue=60,
        hue_range=30,
        sat_min=40,
        val_min=40,
    )

    out, alpha, used = apply_filter_chroma_preview_batch(rgb, filters, chroma)

    assert used is True
    assert out.shape == rgb.shape
    assert alpha.shape == rgb.shape[:2]
    assert out.dtype == np.uint8
    assert alpha.dtype == np.uint8


def test_shader_clip_effects_metadata_for_preview_safe_params(monkeypatch):
    from app.chroma_key import ChromaKeyParams
    from app.preview_effects import build_shader_clip_effects
    from app.video_filters import VideoFilterParams

    monkeypatch.delenv("TIGERCAPTURE_SHADER_CLIP_FX", raising=False)
    filters = VideoFilterParams(
        sharpen=0.4,
        vignette=0.3,
        vignette_feather=0.7,
        chroma_aberration=0.1,
    )
    chroma = ChromaKeyParams(
        enabled=True,
        key_hue=60,
        hue_range=30,
        sat_min=40,
        val_min=40,
        spill_suppress=0.25,
    )

    meta = build_shader_clip_effects(filters, chroma)

    assert meta is not None
    assert meta["filters"]["sharpen"] == 0.4
    assert meta["chroma"]["key_hue"] == 60.0
    assert meta["chroma"]["bg"] == (0.0, 0.0, 0.0)


def test_shader_clip_effects_rejects_temporal_or_random_filters():
    from app.preview_effects import build_shader_clip_effects
    from app.video_filters import VideoFilterParams

    assert build_shader_clip_effects(VideoFilterParams(denoise=0.2), None) is None
    assert build_shader_clip_effects(VideoFilterParams(glitch=0.2), None) is None


def test_opengl_clip_effect_uniforms_normalize_metadata():
    from app.opengl_preview import clip_effects_to_uniforms

    uniforms = clip_effects_to_uniforms({
        "enabled": True,
        "filters": {"sharpen": 0.5, "vignette": 0.25, "vignette_feather": 0.8},
        "chroma": {"key_hue": 60, "hue_range": 30, "sat_min": 40, "val_min": 50},
    })

    assert uniforms["enabled"] is True
    assert uniforms["sharpen"] == 0.5
    assert uniforms["vignette"] == 0.25
    assert uniforms["chroma_enabled"] is True


def test_open_decoder_uses_ffmpeg_frame_server_when_enabled(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (320, 180)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", "1")
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None, preview_height=360)

    assert isinstance(decoder, _FrameServer)
    assert decoder.path == source
    assert decoder.output_height == 360


def test_open_decoder_frame_server_uses_preview_height_hint(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (320, 180)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", "1")
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_HEIGHT", raising=False)
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None)

    assert isinstance(decoder, _FrameServer)
    assert decoder.output_height == 720


def test_open_decoder_frame_server_respects_preview_height_env(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (320, 180)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", "1")
    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_HEIGHT", "540")
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None)

    assert isinstance(decoder, _FrameServer)
    assert decoder.output_height == 540


def test_open_decoder_auto_can_select_ffmpeg_frame_server(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (320, 180)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    seen = {}

    def _choose(path, preview_height):
        seen["path"] = path
        seen["preview_height"] = preview_height
        return "ffmpeg_frame_server"

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_DECODER_AUTO", "1")
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", raising=False)
    monkeypatch.setattr(video_decoder, "_choose_preview_decoder_backend", _choose)
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None, preview_height=360)

    assert isinstance(decoder, _FrameServer)
    assert seen == {"path": source, "preview_height": 360}
    assert decoder.output_height == 360


def test_open_decoder_auto_uses_frame_server_height_hint(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (320, 180)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    seen = {}

    def _choose(path, preview_height):
        seen["path"] = path
        seen["preview_height"] = preview_height
        return "ffmpeg_frame_server"

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_DECODER_AUTO", "1")
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_HEIGHT", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", raising=False)
    monkeypatch.setattr(video_decoder, "_choose_preview_decoder_backend", _choose)
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None)

    assert isinstance(decoder, _FrameServer)
    assert seen == {"path": source, "preview_height": 720}
    assert decoder.output_height == 720


def test_open_decoder_high_res_policy_enables_auto_without_env(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (960, 540)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((540, 960, 3), dtype=np.uint8)

        def release(self):
            pass

    seen = {}

    def _choose(path, preview_height):
        seen["path"] = path
        seen["preview_height"] = preview_height
        return "ffmpeg_frame_server"

    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_DECODER_AUTO", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_HEIGHT", raising=False)
    monkeypatch.setattr(
        video_decoder,
        "_preview_performance_policy",
        lambda path, requested_preview_height=None: {
            "decoder_auto": True,
            "preview_height": 540,
            "reasons": ["high_resolution", "high_fps", "monitoring_scale:540p"],
        },
    )
    monkeypatch.setattr(video_decoder, "_choose_preview_decoder_backend", _choose)
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None)

    assert isinstance(decoder, _FrameServer)
    assert seen == {"path": source, "preview_height": 540}
    assert decoder.output_height == 540


def test_open_decoder_policy_keeps_explicit_preview_height(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _FrameServer:
        fps = 30.0
        total_frames = 10
        frame_size = (640, 360)

        def __init__(self, path, output_height=None):
            self.path = path
            self.output_height = output_height

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((360, 640, 3), dtype=np.uint8)

        def release(self):
            pass

    seen = {}

    def _choose(path, preview_height):
        seen["path"] = path
        seen["preview_height"] = preview_height
        return "ffmpeg_frame_server"

    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_DECODER_AUTO", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", raising=False)
    monkeypatch.setattr(
        video_decoder,
        "_preview_performance_policy",
        lambda path, requested_preview_height=None: {
            "decoder_auto": True,
            "preview_height": 540,
            "reasons": ["high_resolution", "high_fps", "monitoring_scale:540p"],
        },
    )
    monkeypatch.setattr(video_decoder, "_choose_preview_decoder_backend", _choose)
    monkeypatch.setattr(video_decoder, "FFmpegFrameServerDecoder", _FrameServer)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None, preview_height=360)

    assert isinstance(decoder, _FrameServer)
    assert seen == {"path": source, "preview_height": 360}
    assert decoder.output_height == 360


def test_open_decoder_auto_keeps_cv2_when_selected(monkeypatch, tmp_path):
    from app import video_decoder

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"placeholder")

    class _CV2:
        fps = 30.0
        total_frames = 10
        frame_size = (320, 180)

        def __init__(self, path):
            self.path = path

        def open(self):
            return True

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return np.zeros((180, 320, 3), dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setenv("TIGERCAPTURE_PREVIEW_DECODER_AUTO", "1")
    monkeypatch.delenv("TIGERCAPTURE_PREVIEW_FRAME_SERVER", raising=False)
    monkeypatch.setattr(video_decoder, "_choose_preview_decoder_backend", lambda path, preview_height: "cv2")
    monkeypatch.setattr(video_decoder, "CV2Decoder", _CV2)
    monkeypatch.setattr(
        video_decoder,
        "_wrap_for_preview_prefetch",
        lambda decoder, preview_height: decoder,
    )

    decoder = video_decoder.open_decoder(source, hdr_info=None, preview_height=360)

    assert isinstance(decoder, _CV2)
    assert decoder.path == source


def test_frame_cache_decoder_reuses_cached_frame():
    from app.video_decoder import FrameCacheDecoder

    class _Inner:
        fps = 30.0
        total_frames = 100
        frame_size = (2, 2)

        def __init__(self):
            self.seek_calls = []
            self.read_calls = 0
            self.current = 0

        def seek_to_frame(self, idx):
            self.seek_calls.append(int(idx))
            self.current = int(idx)

        def read_rgb(self):
            self.read_calls += 1
            value = self.current
            self.current += 1
            return np.full((2, 2, 3), value, dtype=np.uint8)

        def release(self):
            pass

    inner = _Inner()
    decoder = FrameCacheDecoder(inner, limit=4)

    decoder.seek_to_frame(7)
    first = decoder.read_rgb()
    decoder.seek_to_frame(7)
    second = decoder.read_rgb()

    assert inner.read_calls == 1
    assert inner.seek_calls == [7]
    np.testing.assert_array_equal(first, second)


def test_prefetch_decoder_keeps_buffer_for_near_future_seek():
    from app.video_decoder import PrefetchDecoder

    class _Inner:
        fps = 30.0
        total_frames = 100
        frame_size = (2, 2)

        def __init__(self):
            self.seek_calls = []
            self.current = 0

        def seek_to_frame(self, idx):
            self.seek_calls.append(int(idx))
            self.current = int(idx)

        def read_rgb(self):
            value = self.current
            self.current += 1
            return np.full((2, 2, 3), value, dtype=np.uint8)

        def release(self):
            pass

    inner = _Inner()
    decoder = PrefetchDecoder(inner, preview_height=0)
    try:
        deadline = time.time() + 1.0
        while time.time() < deadline:
            with decoder._cond:
                ready = [idx for idx, _rgb in decoder._buf]
            if 3 in ready:
                break
            time.sleep(0.01)

        decoder.seek_to_frame(3)
        frame = decoder.read_rgb()
        assert frame is not None
        assert int(frame[0, 0, 0]) == 3
        assert 3 not in inner.seek_calls
    finally:
        decoder.release()


def test_prefetch_decoder_uses_env_tuning(monkeypatch):
    from app.video_decoder import PrefetchDecoder

    class _Inner:
        fps = 30.0
        total_frames = 1
        frame_size = (2, 2)

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return None

        def release(self):
            pass

    monkeypatch.setenv("TIGERCAPTURE_PREFETCH_FRAMES", "7")
    monkeypatch.setenv("TIGERCAPTURE_PREFETCH_READ_TIMEOUT", "0.125")
    decoder = PrefetchDecoder(_Inner(), preview_height=0)
    try:
        assert decoder._buffer_size == 7
        assert decoder._read_timeout == 0.125
    finally:
        decoder.release()


def test_prefetch_decoder_defaults_to_small_forward_seek_window(monkeypatch):
    from app.video_decoder import PrefetchDecoder

    class _Inner:
        fps = 30.0
        total_frames = 1
        frame_size = (2, 2)

        def seek_to_frame(self, idx):
            pass

        def read_rgb(self):
            return None

        def release(self):
            pass

    monkeypatch.delenv("TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW", raising=False)
    decoder = PrefetchDecoder(_Inner(), preview_height=0)
    try:
        assert decoder._forward_seek_window == 12
    finally:
        decoder.release()


def test_prefetch_decoder_keeps_near_forward_seek_in_stream(monkeypatch):
    from app.video_decoder import PrefetchDecoder

    class _Inner:
        fps = 30.0
        total_frames = 100
        frame_size = (2, 2)

        def __init__(self):
            self.seek_calls = []
            self.current = 0

        def seek_to_frame(self, idx):
            self.seek_calls.append(int(idx))
            self.current = int(idx)

        def read_rgb(self):
            value = self.current
            self.current += 1
            return np.full((2, 2, 3), value, dtype=np.uint8)

        def release(self):
            pass

    monkeypatch.setenv("TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW", "8")
    inner = _Inner()
    decoder = PrefetchDecoder(inner, preview_height=0)
    try:
        deadline = time.time() + 1.0
        while time.time() < deadline:
            with decoder._cond:
                if decoder._next_bg >= 2:
                    break
            time.sleep(0.01)

        inner.seek_calls.clear()
        decoder.seek_to_frame(6)
        frame = decoder.read_rgb()
        assert frame is not None
        assert int(frame[0, 0, 0]) == 6
        assert inner.seek_calls == []
    finally:
        decoder.release()


def test_cv2_decoder_reads_forward_small_seek_without_reposition(monkeypatch):
    from app.video_decoder import CV2Decoder

    class _Cap:
        def __init__(self):
            self.current = 11
            self.set_calls = []

        def read(self):
            value = self.current
            self.current += 1
            bgr = np.full((2, 2, 3), value, dtype=np.uint8)
            return True, bgr

        def set(self, prop, value):
            self.set_calls.append((prop, int(value)))
            self.current = int(value)

    cap = _Cap()
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(CAP_PROP_POS_FRAMES=12))
    monkeypatch.setenv("TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW", "8")
    decoder = CV2Decoder("clip.mp4")
    decoder._cap = cap
    decoder._last_read_idx = 10

    decoder.seek_to_frame(14)
    frame = decoder.read_rgb()

    assert cap.set_calls == []
    assert int(frame[0, 0, 0]) == 14
    assert decoder._last_read_idx == 14


def test_cv2_decoder_uses_reposition_for_large_forward_seek(monkeypatch):
    from app.video_decoder import CV2Decoder

    class _Cap:
        def __init__(self):
            self.current = 11
            self.set_calls = []

        def read(self):
            value = self.current
            self.current += 1
            bgr = np.full((2, 2, 3), value, dtype=np.uint8)
            return True, bgr

        def set(self, prop, value):
            self.set_calls.append((prop, int(value)))
            self.current = int(value)

    cap = _Cap()
    monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace(CAP_PROP_POS_FRAMES=12))
    monkeypatch.setenv("TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW", "4")
    decoder = CV2Decoder("clip.mp4")
    decoder._cap = cap
    decoder._last_read_idx = 10

    decoder.seek_to_frame(20)
    frame = decoder.read_rgb()

    assert cap.set_calls == [(12, 20)]
    assert int(frame[0, 0, 0]) == 20
    assert decoder._last_read_idx == 20


def test_cv2_hw_decode_params_respects_env(monkeypatch):
    from app.video_decoder import _cv2_hw_decode_params

    class _CV2:
        CAP_PROP_HW_ACCELERATION = 50
        VIDEO_ACCELERATION_ANY = 1
        CAP_PROP_HW_DEVICE = 51

    monkeypatch.delenv("TIGERCAPTURE_DISABLE_HW_DECODE", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_ENABLE_HW_DECODE", raising=False)
    monkeypatch.setenv("TIGERCAPTURE_HW_DEVICE", "2")
    assert _cv2_hw_decode_params(_CV2) == []

    monkeypatch.setenv("TIGERCAPTURE_ENABLE_HW_DECODE", "1")
    assert _cv2_hw_decode_params(_CV2) == [50, 1, 51, 2]

    monkeypatch.setenv("TIGERCAPTURE_DISABLE_HW_DECODE", "1")
    assert _cv2_hw_decode_params(_CV2) == []
