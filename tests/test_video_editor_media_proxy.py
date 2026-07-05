from __future__ import annotations

import os
import sys
from types import SimpleNamespace


def test_proxy_state_tracks_missing_ready_stale_and_delete(tmp_path):
    from app.video_editor_media_proxy import (
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
    now = 1_700_000_000
    os.utime(source, (now - 20, now - 20))
    os.utime(proxy, (now, now))
    assert _proxy_state_for(source) == "ready"

    os.utime(source, (now + 20, now + 20))
    os.utime(proxy, (now - 20, now - 20))
    assert _proxy_state_for(source) == "stale"

    assert _delete_proxy_for_source(source) is True
    assert _proxy_state_for(source) == "missing"


def test_generate_proxy_uses_540p_ffmpeg_command_without_running_real_ffmpeg(tmp_path, monkeypatch):
    import app.video_editor_media_proxy as proxy_mod

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    calls = []

    monkeypatch.setitem(
        sys.modules,
        "imageio_ffmpeg",
        SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg-test"),
    )

    def fake_run(cmd, capture_output, **kwargs):
        calls.append((cmd, capture_output, kwargs))
        output = proxy_mod._proxy_path_for(source)
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(b"proxy")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(proxy_mod.subprocess, "run", fake_run)

    generated = proxy_mod._generate_proxy(source)

    assert generated == proxy_mod._proxy_path_for(source)
    assert calls
    cmd = calls[0][0]
    assert cmd[0] == "ffmpeg-test"
    assert "-vf" in cmd
    assert "scale=-2:540" in cmd
    assert str(generated) == cmd[-1]


def test_generate_proxy_reuses_ready_proxy_without_ffmpeg(tmp_path, monkeypatch):
    import app.video_editor_media_proxy as proxy_mod

    source = tmp_path / "clip.mp4"
    source.write_bytes(b"source")
    existing = proxy_mod._proxy_path_for(source)
    existing.parent.mkdir()
    existing.write_bytes(b"proxy")
    now = 1_700_000_000
    os.utime(source, (now - 20, now - 20))
    os.utime(existing, (now, now))

    monkeypatch.setitem(
        sys.modules,
        "imageio_ffmpeg",
        SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg-test"),
    )
    monkeypatch.setattr(
        proxy_mod.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ffmpeg should not run")),
    )

    assert proxy_mod._generate_proxy(source, force=False) == existing


def test_is_high_resolution_returns_true_for_large_file(tmp_path):
    from app.video_editor_media_proxy import _is_high_resolution

    source = tmp_path / "large.mp4"
    with source.open("wb") as fh:
        fh.seek((501 * 1024 * 1024) - 1)
        fh.write(b"\0")

    assert _is_high_resolution(source) is True


def test_probe_video_dimensions_returns_zero_tuple_when_probe_fails(tmp_path, monkeypatch):
    import app.video_editor_media_proxy as proxy_mod

    source = tmp_path / "broken.mp4"
    source.write_bytes(b"not a video")
    monkeypatch.setitem(
        sys.modules,
        "imageio_ffmpeg",
        SimpleNamespace(get_ffmpeg_exe=lambda: "ffmpeg-test"),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.native_worker",
        SimpleNamespace(native_media_probe=lambda *args, **kwargs: None),
    )
    monkeypatch.setitem(
        sys.modules,
        "cv2",
        SimpleNamespace(VideoCapture=lambda path: SimpleNamespace(isOpened=lambda: False)),
    )

    assert proxy_mod._probe_video_dimensions(source) == (0, 0)
