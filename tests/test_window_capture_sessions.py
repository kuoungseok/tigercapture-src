from __future__ import annotations

import io
import time
from pathlib import Path

from PIL import Image


def _unreal_window_info():
    import app.window_capture as window_capture

    return window_capture.WindowInfo(
        hwnd=4242,
        title="Unreal Editor - Terrain",
        pid=101,
        process_name="UnrealEditor.exe",
        process_path="D:/UE/UnrealEditor.exe",
        rect=(0, 0, 640, 360),
        visible=True,
        minimized=False,
    )


def test_window_video_capture_session_start_status_stop(tmp_path, monkeypatch):
    import app.window_capture as window_capture

    with window_capture._window_video_sessions_lock:
        window_capture._window_video_sessions.clear()

    info = _unreal_window_info()

    def fake_find_capture_window(**_kwargs):
        return info

    def fake_record_window_video_frames(**kwargs):
        stop_event = kwargs["stop_event"]
        deadline = time.time() + 2.0
        while not stop_event.is_set() and time.time() < deadline:
            time.sleep(0.01)
        out = Path(kwargs["path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return {
            "schema": "tigerstudio.capture.window_video.v1",
            "path": str(out.resolve()),
            "backend": "visible_crop",
            "encoder": "ffmpeg_rawvideo_libx264",
            "duration_ms": 25,
            "requested_duration_ms": int(kwargs["duration_ms"]),
            "actual_duration_ms": 25,
            "fps": int(kwargs["fps"]),
            "frames": 3,
            "stopped_by": "request" if stop_event.is_set() else "duration",
            "session_id": kwargs["session_id"],
            "window": info.to_dict(),
        }

    monkeypatch.setattr(window_capture, "find_capture_window", fake_find_capture_window)
    monkeypatch.setattr(window_capture, "_record_window_video_frames", fake_record_window_video_frames)

    started = window_capture.start_window_video_capture(
        session_id="unreal-terrain",
        path=tmp_path / "terrain.mp4",
        hwnd=4242,
        max_duration_ms=600_000,
        fps=15,
        backend="visible",
    )
    assert started["session_id"] == "unreal-terrain"
    assert started["stop_policy"].startswith("call capture.window.video.stop")

    status = window_capture.window_video_capture_status(session_id="unreal-terrain")
    assert status["count"] == 1
    assert status["sessions"][0]["running"] is True

    stopped = window_capture.stop_window_video_capture(session_id="unreal-terrain", wait_ms=2000)
    row = stopped["sessions"][0]
    assert row["running"] is False
    assert row["status"] == "stopped"
    assert row["result"]["stopped_by"] == "request"
    assert Path(row["path"]).exists()


def test_window_video_capture_session_clamps_long_recording_cap(tmp_path, monkeypatch):
    import app.window_capture as window_capture

    with window_capture._window_video_sessions_lock:
        window_capture._window_video_sessions.clear()

    info = _unreal_window_info()

    def fake_find_capture_window(**_kwargs):
        return info

    def fake_record_window_video_frames(**kwargs):
        out = Path(kwargs["path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return {
            "schema": "tigerstudio.capture.window_video.v1",
            "path": str(out.resolve()),
            "backend": "wgc_window",
            "encoder": "ffmpeg_rawvideo_libx264",
            "duration_ms": 10,
            "requested_duration_ms": int(kwargs["duration_ms"]),
            "actual_duration_ms": 10,
            "fps": int(kwargs["fps"]),
            "frames": 1,
            "stopped_by": "duration",
            "session_id": kwargs["session_id"],
            "window": info.to_dict(),
        }

    monkeypatch.setattr(window_capture, "find_capture_window", fake_find_capture_window)
    monkeypatch.setattr(window_capture, "_record_window_video_frames", fake_record_window_video_frames)

    started = window_capture.start_window_video_capture(
        session_id="unreal-long-cap",
        path=tmp_path / "long_cap.mp4",
        hwnd=4242,
        max_duration_ms=99_999_999,
        fps=15,
        backend="auto",
    )

    assert started["max_duration_ms"] == 14_400_000

    deadline = time.time() + 2.0
    row = None
    while time.time() < deadline:
        row = window_capture.window_video_capture_status(session_id="unreal-long-cap")["sessions"][0]
        if row["running"] is False:
            break
        time.sleep(0.01)

    assert row is not None
    assert row["result"]["requested_duration_ms"] == 14_400_000


def test_unreal_auto_window_image_prefers_wgc_window(monkeypatch):
    import app.window_capture as window_capture

    info = _unreal_window_info()
    calls: list[str] = []

    monkeypatch.setattr(window_capture, "find_capture_window", lambda **_kwargs: info)

    def fake_wgc(hwnd):
        calls.append(f"wgc:{hwnd}")
        return Image.new("RGB", (32, 18), (10, 20, 30))

    def fake_visible(_rect):
        calls.append("visible")
        return Image.new("RGB", (32, 18), (40, 50, 60))

    monkeypatch.setattr(window_capture, "_capture_wgc_window_frame", fake_wgc)
    monkeypatch.setattr(window_capture, "_capture_visible_crop", fake_visible)

    image, backend = window_capture.capture_window_image(4242, backend="auto")

    assert backend == "wgc_window"
    assert image.size == (32, 18)
    assert calls == ["wgc:4242"]


def test_unreal_auto_window_image_falls_back_to_visible(monkeypatch):
    import app.window_capture as window_capture

    info = _unreal_window_info()
    calls: list[str] = []

    monkeypatch.setattr(window_capture, "find_capture_window", lambda **_kwargs: info)

    def fake_wgc(_hwnd):
        calls.append("wgc")
        raise RuntimeError("wgc unavailable")

    def fake_visible(_rect):
        calls.append("visible")
        return Image.new("RGB", (32, 18), (40, 50, 60))

    monkeypatch.setattr(window_capture, "_capture_wgc_window_frame", fake_wgc)
    monkeypatch.setattr(window_capture, "_capture_visible_crop", fake_visible)

    image, backend = window_capture.capture_window_image(4242, backend="auto")

    assert backend == "visible_crop"
    assert image.size == (32, 18)
    assert calls == ["wgc", "visible"]


def test_unreal_auto_video_uses_wgc_window(monkeypatch, tmp_path):
    import app.window_capture as window_capture

    info = _unreal_window_info()
    calls: list[dict] = []

    monkeypatch.setattr(window_capture, "find_capture_window", lambda **_kwargs: info)

    def fake_record_wgc(**kwargs):
        calls.append(dict(kwargs))
        out = Path(kwargs["path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"mp4")
        return {
            "schema": "tigerstudio.capture.window_video.v1",
            "path": str(out.resolve()),
            "backend": "wgc_window",
            "encoder": "ffmpeg_rawvideo_libx264",
            "duration_ms": 1000,
            "requested_duration_ms": 1000,
            "actual_duration_ms": 1000,
            "fps": int(kwargs["fps"]),
            "frames": 1,
            "width": 32,
            "height": 18,
            "stopped_by": "duration",
            "session_id": kwargs["session_id"],
            "window": info.to_dict(),
        }

    monkeypatch.setattr(window_capture, "_record_window_video_wgc", fake_record_wgc)

    result = window_capture.record_window_video(
        path=tmp_path / "unreal.mp4",
        hwnd=4242,
        duration_ms=1000,
        fps=15,
        backend="auto",
    )

    assert result["backend"] == "wgc_window"
    assert calls[0]["info"] == info


def test_wgc_window_video_reports_source_closed(monkeypatch, tmp_path):
    import app.window_capture as window_capture

    info = _unreal_window_info()

    class FakeWgcSource:
        def __init__(self, hwnd):
            self.hwnd = hwnd
            self.stopped = False

        def start(self):
            pass

        def wait_for_first_frame(self, timeout_s=3.0):
            return Image.new("RGB", (32, 18), (10, 20, 30))

        def latest_frame(self):
            return Image.new("RGB", (32, 18), (11, 21, 31))

        def is_closed(self):
            return True

        def error_message(self):
            return ""

        def stop(self):
            self.stopped = True

    class FakeProc:
        def __init__(self):
            self.stdin = io.BytesIO()
            self.stderr = io.BytesIO()

        def wait(self, timeout=None):
            return 0

    popen_calls: list[dict] = []

    def fake_popen(command, **kwargs):
        popen_calls.append({"command": list(command), **kwargs})
        return FakeProc()

    monkeypatch.setattr(window_capture, "_ffmpeg_exe", lambda: "ffmpeg")
    monkeypatch.setattr(window_capture, "_WgcWindowFrameSource", FakeWgcSource)
    monkeypatch.setattr(window_capture.subprocess, "Popen", fake_popen)

    result = window_capture._record_window_video_wgc(
        info=info,
        path=tmp_path / "closed.mp4",
        duration_ms=60_000,
        fps=30,
        max_duration_ms=60_000,
    )

    assert result["backend"] == "wgc_window"
    assert result["stopped_by"] == "source_closed"
    assert result["frames"] == 1
    assert popen_calls
    assert popen_calls[0]["stdout"] == window_capture.subprocess.DEVNULL


def test_window_video_session_reports_source_closed(tmp_path, monkeypatch):
    import app.window_capture as window_capture

    with window_capture._window_video_sessions_lock:
        window_capture._window_video_sessions.clear()

    info = _unreal_window_info()

    def fake_find_capture_window(**_kwargs):
        return info

    def fake_record_window_video_frames(**kwargs):
        out = Path(kwargs["path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"partial mp4")
        return {
            "schema": "tigerstudio.capture.window_video.v1",
            "path": str(out.resolve()),
            "backend": "wgc_window",
            "encoder": "ffmpeg_rawvideo_libx264",
            "duration_ms": 50,
            "requested_duration_ms": int(kwargs["duration_ms"]),
            "actual_duration_ms": 50,
            "fps": int(kwargs["fps"]),
            "frames": 1,
            "stopped_by": "source_closed",
            "session_id": kwargs["session_id"],
            "window": info.to_dict(),
        }

    monkeypatch.setattr(window_capture, "find_capture_window", fake_find_capture_window)
    monkeypatch.setattr(window_capture, "_record_window_video_frames", fake_record_window_video_frames)

    started = window_capture.start_window_video_capture(
        session_id="unreal-source-closed",
        path=tmp_path / "source_closed.mp4",
        hwnd=4242,
        max_duration_ms=600_000,
        fps=15,
        backend="auto",
    )
    assert started["session_id"] == "unreal-source-closed"

    deadline = time.time() + 2.0
    row = None
    while time.time() < deadline:
        row = window_capture.window_video_capture_status(session_id="unreal-source-closed")["sessions"][0]
        if row["running"] is False:
            break
        time.sleep(0.01)

    assert row is not None
    assert row["running"] is False
    assert row["status"] == "source_closed"
    assert row["result"]["stopped_by"] == "source_closed"
