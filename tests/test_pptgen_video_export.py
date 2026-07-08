from __future__ import annotations


def test_render_slide_image_can_render_animation_playhead():
    from app.pptgen.preview import render_slide_image
    from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec

    slide = SlideSpec(id="slide-001", title="Video", duration_ms=1000)
    shape = SlideElement(
        id="shape-1",
        kind="shape",
        x=0.25,
        y=0.25,
        w=0.5,
        h=0.5,
        style=ElementStyle(fill="#FF0000"),
    )
    shape.animation.in_animation = "fade_in"
    shape.animation.start_ms = 500
    shape.animation.duration_ms = 250
    slide.add_element(shape)
    deck = DeckSpec(id="deck", slides=[slide])

    before = render_slide_image(deck, slide, size=(160, 90), playhead_ms=0)
    after = render_slide_image(deck, slide, size=(160, 90), playhead_ms=900)

    assert before.getpixel((80, 45)) == (255, 255, 255)
    assert after.getpixel((80, 45))[0] > 220
    assert after.getpixel((80, 45))[1] < 40


def test_export_deck_video_streams_frames_with_slide_local_time(monkeypatch, tmp_path):
    from PIL import Image

    import app.pptgen.video_export as video_export
    from app.pptgen.schema import DeckSpec, SlideSpec

    slide = SlideSpec(id="slide-001", title="Video", duration_ms=1000)
    deck = DeckSpec(id="deck", slides=[slide])
    calls: list[tuple[str, tuple[int, int], int | None]] = []
    popen_calls: list[list[str]] = []

    def fake_render(deck_arg, slide_arg, *, size, playhead_ms=None):
        calls.append((slide_arg.id, size, playhead_ms))
        return Image.new("RGB", size, (10, 20, 30))

    class _FakeStdin:
        def __init__(self) -> None:
            self.bytes_written = 0
            self.closed = False

        def write(self, data: bytes) -> int:
            self.bytes_written += len(data)
            return len(data)

        def close(self) -> None:
            self.closed = True

    class _FakeProc:
        def __init__(self, cmd, **_kwargs) -> None:
            popen_calls.append(list(cmd))
            self.stdin = _FakeStdin()
            self.returncode = 0

        def communicate(self):
            return b"", b""

        def kill(self) -> None:
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(video_export, "render_slide_image", fake_render)
    monkeypatch.setattr(video_export.subprocess, "Popen", _FakeProc)

    out = tmp_path / "deck.mp4"
    result = video_export.export_deck_video(deck, out, fps=2, size=(33, 17), ffmpeg_exe="ffmpeg-test")

    assert result["frames_written"] == 2
    assert result["size"] == [34, 18]
    assert result["transition_count"] == 0
    assert calls == [("slide-001", (34, 18), 0), ("slide-001", (34, 18), 500)]
    assert popen_calls[0][0] == "ffmpeg-test"
    assert "34x18" in popen_calls[0]


def test_build_ffmpeg_video_export_command_adds_audio_mux(tmp_path):
    from app.pptgen.video_export import build_ffmpeg_video_export_command

    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wave")

    silent = build_ffmpeg_video_export_command(
        ffmpeg="ffmpeg-test",
        output_path=tmp_path / "silent.mp4",
        size=(320, 180),
        fps=30,
    )
    muxed = build_ffmpeg_video_export_command(
        ffmpeg="ffmpeg-test",
        output_path=tmp_path / "muxed.mp4",
        size=(320, 180),
        fps=30,
        audio_path=audio,
    )

    assert "-an" in silent
    assert "-an" not in muxed
    assert muxed.count("-i") == 2
    assert str(audio) in muxed
    assert "-c:a" in muxed
    assert "aac" in muxed
    assert "-af" in muxed
    assert "apad" in muxed
    assert "-shortest" in muxed


def test_export_deck_video_accepts_audio_path(monkeypatch, tmp_path):
    from PIL import Image

    import app.pptgen.video_export as video_export
    from app.pptgen.schema import DeckSpec, SlideSpec

    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"fake-wave")
    deck = DeckSpec(id="deck", slides=[SlideSpec(id="slide-001", title="Video", duration_ms=500)])
    popen_calls: list[list[str]] = []

    def fake_render(deck_arg, slide_arg, *, size, playhead_ms=None):
        return Image.new("RGB", size, (10, 20, 30))

    class _FakeStdin:
        def write(self, data: bytes) -> int:
            return len(data)

        def close(self) -> None:
            pass

    class _FakeProc:
        def __init__(self, cmd, **_kwargs) -> None:
            popen_calls.append(list(cmd))
            self.stdin = _FakeStdin()
            self.returncode = 0

        def communicate(self):
            return b"", b""

        def kill(self) -> None:
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(video_export, "render_slide_image", fake_render)
    monkeypatch.setattr(video_export.subprocess, "Popen", _FakeProc)

    result = video_export.export_deck_video(deck, tmp_path / "deck.mp4", fps=2, size=(32, 18), ffmpeg_exe="ffmpeg-test", audio_path=audio)

    assert result["audio_muxed"] is True
    assert result["audio_path"] == str(audio)
    assert str(audio) in popen_calls[0]
    assert "-an" not in popen_calls[0]


def test_export_deck_video_can_be_cancelled(monkeypatch, tmp_path):
    from PIL import Image
    import pytest

    import app.pptgen.video_export as video_export
    from app.pptgen.schema import DeckSpec, SlideSpec

    deck = DeckSpec(id="deck", slides=[SlideSpec(id="slide-001", title="Video", duration_ms=1500)])
    state = {"rendered": 0, "killed": False}

    def fake_render(deck_arg, slide_arg, *, size, playhead_ms=None):
        state["rendered"] += 1
        return Image.new("RGB", size, (10, 20, 30))

    class _FakeStdin:
        def write(self, data: bytes) -> int:
            return len(data)

        def close(self) -> None:
            pass

    class _FakeProc:
        def __init__(self, cmd, **_kwargs) -> None:
            self.stdin = _FakeStdin()
            self.returncode = 0

        def communicate(self):
            return b"", b""

        def kill(self) -> None:
            state["killed"] = True
            self.returncode = -9

        def wait(self, timeout=None):
            return self.returncode

    monkeypatch.setattr(video_export, "render_slide_image", fake_render)
    monkeypatch.setattr(video_export.subprocess, "Popen", _FakeProc)

    with pytest.raises(video_export.PptVideoExportCancelled):
        video_export.export_deck_video(
            deck,
            tmp_path / "deck.mp4",
            fps=2,
            size=(32, 18),
            ffmpeg_exe="ffmpeg-test",
            cancel_requested=lambda: state["rendered"] >= 1,
        )

    assert state["rendered"] == 1
    assert state["killed"] is True


def test_video_transition_frame_blends_current_and_next_slide():
    from app.pptgen.schema import DeckSpec, SlideSpec
    from app.pptgen.video_export import _render_video_frame

    current = SlideSpec(id="slide-001", title="Red", background="#FF0000")
    next_slide = SlideSpec(id="slide-002", title="Blue", background="#0000FF")
    deck = DeckSpec(id="deck", slides=[current, next_slide])

    cut = _render_video_frame(deck, current, size=(40, 24), local_ms=0, next_slide=next_slide, transition="cut", transition_alpha=0.5)
    fade = _render_video_frame(deck, current, size=(40, 24), local_ms=0, next_slide=next_slide, transition="fade", transition_alpha=0.5)

    assert cut.getpixel((20, 12)) == (255, 0, 0)
    blended = fade.getpixel((20, 12))
    assert 120 <= blended[0] <= 135
    assert blended[1] == 0
    assert 120 <= blended[2] <= 135


def test_transition_duration_uses_fade_only_when_next_clip_exists():
    from app.pptgen.timeline import SlideClip
    from app.pptgen.video_export import normalize_transition, transition_duration_ms

    current = SlideClip(id="clip-1", slide_id="slide-001", start_ms=0, duration_ms=1000, transition_out="dissolve")
    next_clip = SlideClip(id="clip-2", slide_id="slide-002", start_ms=1000, duration_ms=1200, transition_out="cut")

    assert normalize_transition("dissolve") == "fade"
    assert transition_duration_ms(current, next_clip) == 500
    assert transition_duration_ms(current, None) == 0
    current.transition_out = "cut"
    assert transition_duration_ms(current, next_clip) == 0
