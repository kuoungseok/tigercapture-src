from pathlib import Path


class _FakeStream:
    def __init__(self, lines=None, text=""):
        self._lines = list(lines or [])
        self._text = text

    def readline(self):
        if self._lines:
            return self._lines.pop(0)
        return ""

    def read(self):
        return self._text


class _ProgressProcess:
    def __init__(self, lines=None, returncode=0):
        self.stdout = _FakeStream(lines)
        self.stderr = _FakeStream(text="")
        self.returncode = None
        self._final_returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self):
        if self.stdout._lines:
            return None
        self.returncode = self._final_returncode
        return self.returncode

    def wait(self, timeout=None):
        self.returncode = self._final_returncode
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15

    def kill(self):
        self.killed = True
        self.returncode = -9


def test_project_audio_bus_mixdown_uses_export_audio_filter(tmp_path):
    from app.audio_tracks import AudioClip, AudioTrack
    from app.broadcast_audio_mix import build_project_audio_bus_mixdown_plan

    clip = AudioClip(
        id=1,
        source_path=Path("voice.wav"),
        duration_ms=2000,
        offset_ms=500,
        trim_start_ms=100,
        trim_end_ms=1600,
        gain=0.8,
    )
    track = AudioTrack(id=1, volume=0.5, clips=[clip], pan=-0.25)

    plan = build_project_audio_bus_mixdown_plan(
        [track],
        tmp_path / "bus.wav",
        duration_ms=3000,
        ffmpeg_exe="ffmpeg-test",
    )

    assert plan.silent is False
    assert plan.audio_input_count == 1
    assert plan.command[0] == "ffmpeg-test"
    assert ["-i", "voice.wav"] == plan.command[2:4]
    graph = plan.command[plan.command.index("-filter_complex") + 1]
    assert "atrim=0.100:1.600" in graph
    assert "adelay=500:all=1" in graph
    assert "volume=0.400" in graph
    assert "apan=stereo" in graph
    assert plan.command[-1].endswith("bus.wav")


def test_project_audio_bus_mixdown_falls_back_to_silence(tmp_path):
    from app.broadcast_audio_mix import build_project_audio_bus_mixdown_plan

    plan = build_project_audio_bus_mixdown_plan(
        [],
        tmp_path / "silent.wav",
        duration_ms=1200,
        ffmpeg_exe="ffmpeg-test",
    )

    assert plan.silent is True
    assert plan.audio_input_count == 0
    assert ["-f", "lavfi"] == plan.command[2:4]
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in plan.command
    assert "-t" in plan.command


def test_project_audio_bus_render_returns_runner_diagnostics(tmp_path):
    from app.broadcast_audio_mix import render_project_audio_bus_mixdown

    calls = []

    class _Result:
        returncode = 0
        stderr = b""

    def _runner(command, **kwargs):
        calls.append((command, kwargs))
        return _Result()

    diag = render_project_audio_bus_mixdown(
        [],
        tmp_path / "silent.wav",
        duration_ms=1000,
        ffmpeg_exe="ffmpeg-test",
        runner=_runner,
    )

    assert diag["ok"] is True
    assert diag["silent"] is True
    assert calls[0][0][0] == "ffmpeg-test"


def test_project_audio_bus_progressive_render_reports_progress(tmp_path):
    from app.broadcast_audio_mix import render_project_audio_bus_mixdown_progressive

    events = []
    processes = []

    def _popen(command, **kwargs):
        processes.append((command, kwargs))
        return _ProgressProcess(
            [
                "out_time_ms=500000\n",
                "progress=continue\n",
                "out_time_ms=1000000\n",
                "progress=end\n",
            ],
            returncode=0,
        )

    diag = render_project_audio_bus_mixdown_progressive(
        [],
        tmp_path / "silent.wav",
        duration_ms=1000,
        ffmpeg_exe="ffmpeg-test",
        popen_factory=_popen,
        progress_callback=lambda event: events.append(event),
    )

    assert diag["ok"] is True
    assert diag["progress"] == 1.0
    assert processes[0][0][1:4] == ["-nostats", "-progress", "pipe:1"]
    assert any(event.get("progress") == 0.5 for event in events)
    assert events[-1]["state"] == "done"


def test_project_audio_bus_progressive_render_can_cancel(tmp_path):
    from app.broadcast_audio_mix import render_project_audio_bus_mixdown_progressive

    proc = _ProgressProcess(["out_time_ms=100000\n"], returncode=0)

    diag = render_project_audio_bus_mixdown_progressive(
        [],
        tmp_path / "silent.wav",
        duration_ms=1000,
        ffmpeg_exe="ffmpeg-test",
        popen_factory=lambda *_args, **_kwargs: proc,
        cancel_requested=lambda: True,
    )

    assert diag["ok"] is False
    assert diag["cancelled"] is True
    assert proc.terminated is True
