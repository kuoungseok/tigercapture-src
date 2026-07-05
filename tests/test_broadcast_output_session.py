import numpy as np


class _FakeStdin:
    def __init__(self):
        self.payloads = []
        self.closed = False

    def write(self, payload):
        self.payloads.append(bytes(payload))

    def close(self):
        self.closed = True


class _FakeProcess:
    def __init__(self):
        self.stdin = _FakeStdin()
        self.returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self):
        self.terminated = True
        self.returncode = 1

    def kill(self):
        self.killed = True
        self.returncode = 1


class _FailingStdin:
    def write(self, _payload):
        raise BrokenPipeError("closed pipe")

    def close(self):
        pass


class _ReadOnlyStderr:
    def __init__(self, text):
        self._text = text

    def readline(self):
        return ""

    def read(self):
        text = self._text
        self._text = ""
        return text


class _HangingProcess(_FakeProcess):
    def wait(self, timeout=None):
        raise TimeoutError("still running")


def test_broadcast_output_session_starts_writes_and_stops_rtmp():
    from app.broadcast_output_session import BroadcastOutputSession

    calls = []
    fake = _FakeProcess()

    def _popen(command, **kwargs):
        calls.append((command, kwargs))
        return fake

    session = BroadcastOutputSession(
        {"target_id": "youtube_live", "stream_key": "SECRET"},
        {"width": 4, "height": 2, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=_popen,
    )

    started = session.start()
    written = session.write_frame(np.zeros((2, 4, 3), dtype=np.uint8))
    stopped = session.stop()

    assert started["state"] == "running"
    assert calls[0][0][-1].endswith("/SECRET")
    assert "SECRET" not in " ".join(str(part) for part in started["command"])
    assert written["frames_written"] == 1
    assert written["bytes_written"] == 4 * 2 * 3
    assert "estimated_fps" in written
    assert "last_write_ms" in written
    assert "backpressure_count" in written
    assert len(fake.stdin.payloads) == 1
    assert fake.stdin.closed is True
    assert stopped["state"] == "stopped"


def test_broadcast_output_session_records_live2d_composited_program_frame(tmp_path):
    from app.broadcast_output_session import BroadcastOutputSession

    calls = []
    fake = _FakeProcess()

    def _popen(command, **kwargs):
        calls.append((command, kwargs))
        return fake

    frame = np.zeros((4, 4, 3), dtype=np.uint8)
    frame[:, :] = [0, 255, 0]
    frame[1:3, 1:3] = [255, 80, 180]

    session = BroadcastOutputSession(
        {
            "target_id": "record_file",
            "output_path": str(tmp_path / "live2d_program_output.mp4"),
        },
        {"width": 4, "height": 4, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=_popen,
    )

    started = session.start()
    written = session.write_frame(frame)
    stopped = session.stop()

    assert started["state"] == "running"
    assert started["output_kind"] == "recording"
    assert any("live2d_program_output.mp4" in str(part) for part in calls[0][0])
    assert written["frames_written"] == 1
    assert written["bytes_written"] == 4 * 4 * 3
    assert fake.stdin.payloads[0] == frame.tobytes()
    assert stopped["state"] == "stopped"


def test_broadcast_output_session_rejects_missing_stream_key():
    from app.broadcast_output_session import BroadcastOutputSession

    session = BroadcastOutputSession(
        {"target_id": "twitch"},
        {"width": 4, "height": 2, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=lambda *_args, **_kwargs: _FakeProcess(),
    )

    status = session.start()

    assert status["state"] == "error"
    assert "stream key" in status["last_error"]


def test_broadcast_output_session_discord_is_manual_output_without_process():
    from app.broadcast_output_session import BroadcastOutputSession

    calls = []
    session = BroadcastOutputSession(
        {"target_id": "discord_video_call"},
        {"width": 4, "height": 2, "fps": 30},
        popen_factory=lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    status = session.start()

    assert status["state"] == "manual_output"
    assert status["manual_output"] is True
    assert calls == []


def test_rgb24_frame_bytes_resizes_rgba_array_to_canvas():
    from app.broadcast_output_session import rgb24_frame_bytes

    rgba = np.zeros((2, 2, 4), dtype=np.uint8)
    rgba[:, :] = [255, 0, 0, 128]

    payload = rgb24_frame_bytes(rgba, width=4, height=2)

    assert len(payload) == 4 * 2 * 3


def test_broadcast_output_session_reconnects_rtmp_after_process_exit():
    from app.broadcast_output_session import BroadcastOutputSession

    calls = []
    first = _HangingProcess()
    second = _FakeProcess()

    def _popen(command, **kwargs):
        calls.append((command, kwargs))
        return first if len(calls) == 1 else second

    session = BroadcastOutputSession(
        {"target_id": "youtube_live", "stream_key": "SECRET", "max_retries": 2},
        {"width": 4, "height": 2, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=_popen,
    )

    started = session.start()
    first.returncode = 1
    status = session.write_frame(np.zeros((2, 4, 3), dtype=np.uint8))

    assert started["auto_reconnect"] is True
    assert status["state"] == "running"
    assert status["retry_count"] == 1
    assert status["last_exit_code"] == 1
    assert status["recovery_action"] == "reconnected"
    assert status["health"] == "degraded"
    assert len(calls) == 2
    assert len(second.stdin.payloads) == 1


def test_broadcast_output_session_reports_retry_limit():
    from app.broadcast_output_session import BroadcastOutputSession

    fake = _FakeProcess()

    session = BroadcastOutputSession(
        {"target_id": "youtube_live", "stream_key": "SECRET", "max_retries": 0},
        {"width": 4, "height": 2, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=lambda *_args, **_kwargs: fake,
    )

    session.start()
    fake.returncode = 1
    status = session.write_frame(np.zeros((2, 4, 3), dtype=np.uint8))

    assert status["state"] == "error"
    assert status["retry_count"] == 0
    assert status["recovery_action"] == "retry_limit_reached"
    assert status["health"] == "error"


def test_broadcast_output_session_reconnects_after_write_failure():
    from app.broadcast_output_session import BroadcastOutputSession

    calls = []
    first = _HangingProcess()
    first.stdin = _FailingStdin()
    second = _FakeProcess()

    def _popen(command, **kwargs):
        calls.append((command, kwargs))
        return first if len(calls) == 1 else second

    session = BroadcastOutputSession(
        {"target_id": "youtube_live", "stream_key": "SECRET", "max_retries": 1},
        {"width": 4, "height": 2, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=_popen,
    )

    session.start()
    status = session.write_frame(np.zeros((2, 4, 3), dtype=np.uint8))

    assert status["state"] == "running"
    assert status["write_error_count"] == 1
    assert status["retry_count"] == 1
    assert first.terminated is True
    assert len(second.stdin.payloads) == 1


def test_broadcast_ffmpeg_error_classifier_maps_platform_auth():
    from app.broadcast_output_session import classify_broadcast_ffmpeg_error

    kind, message = classify_broadcast_ffmpeg_error(
        "[rtmp @ 000] Server returned 403 Forbidden (auth failed)"
    )

    assert kind == "platform_auth"
    assert "stream key" in message


def test_broadcast_output_session_includes_platform_error_from_stderr():
    from app.broadcast_output_session import BroadcastOutputSession

    fake = _FakeProcess()
    fake.stderr = _ReadOnlyStderr("[rtmp @ 000] Server returned 403 Forbidden for SECRET\n")

    session = BroadcastOutputSession(
        {"target_id": "youtube_live", "stream_key": "SECRET", "max_retries": 0},
        {"width": 4, "height": 2, "fps": 30},
        ffmpeg_exe="ffmpeg-test",
        popen_factory=lambda *_args, **_kwargs: fake,
    )

    session.start()
    fake.returncode = 1
    status = session.write_frame(np.zeros((2, 4, 3), dtype=np.uint8))

    assert status["state"] == "error"
    assert status["platform_error_kind"] == "platform_auth"
    assert "stream key" in status["platform_error_message"]
    assert "403 Forbidden" in status["stderr_tail"]
    assert "SECRET" not in status["stderr_tail"]
    assert status["troubleshooting"]["primary_action"] == "refresh_stream_key"
    assert any("YouTube" in step for step in status["troubleshooting"]["checks"])
