from __future__ import annotations

import math
import wave

import numpy as np


def test_audio_accuracy_reference_sine_hits_target_lufs():
    from app.audio_accuracy import audio_signal_diagnostics

    target = -14.0
    sample_rate = 48000
    t = np.arange(sample_rate, dtype=np.float32) / float(sample_rate)
    rms = 10.0 ** ((target + 0.691) / 20.0)
    amp = rms * math.sqrt(2.0)
    mono = amp * np.sin(2.0 * math.pi * 1000.0 * t)
    pcm = np.column_stack([mono, mono]).astype(np.float32)

    diag = audio_signal_diagnostics(pcm, target_lufs=target, true_peak_limit_db=-1.0)

    assert diag["ok"] is True
    assert abs(diag["integrated_lufs"] - target) <= 0.2
    assert diag["stereo_correlation"] > 0.99


def test_color_audio_accuracy_report_passes():
    from tools.qa_color_audio_accuracy import build_report

    report = build_report()

    assert report["ok"] is True
    assert report["summary"]["checks"] >= 10
    assert report["summary"]["failures"] == 0


def test_color_audio_accuracy_accepts_real_audio_sample(tmp_path):
    from tools.qa_color_audio_accuracy import build_report

    sample_rate = 48000
    t = np.arange(sample_rate // 4, dtype=np.float32) / float(sample_rate)
    mono = 0.1 * np.sin(2.0 * math.pi * 440.0 * t)
    stereo = np.column_stack([mono, mono])
    pcm16 = np.clip(stereo * 32767.0, -32768, 32767).astype("<i2")
    wav_path = tmp_path / "dialogue_sample.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16.tobytes())

    report = build_report(audio_samples=[wav_path])

    assert report["ok"] is True
    real = report["sections"]["real_samples"]
    assert len(real) == 1
    assert real[0]["name"].startswith("real.audio_diagnostics.dialogue_sample")
    assert real[0]["sample_rate"] == sample_rate
    assert real[0]["diagnostics"]["stereo_correlation"] > 0.99


def test_color_audio_accuracy_discovers_sample_corpus(tmp_path):
    from tools.qa_color_audio_accuracy import discover_color_audio_samples

    (tmp_path / "clip.mp4").write_bytes(b"fake")
    (tmp_path / "voice.wav").write_bytes(b"fake")
    (tmp_path / "ignore.txt").write_text("ignore", encoding="utf-8")

    samples = discover_color_audio_samples(tmp_path)

    assert tmp_path / "clip.mp4" in samples["video"]
    assert tmp_path / "clip.mp4" in samples["audio"]
    assert tmp_path / "voice.wav" in samples["audio"]
    assert all(path.suffix != ".txt" for rows in samples.values() for path in rows)


def test_color_audio_accuracy_no_audio_video_error_is_skippable():
    from tools.qa_color_audio_accuracy import _is_no_audio_stream_error

    assert _is_no_audio_stream_error(
        "[out#0/f32le] Output file does not contain any stream"
    )
    assert not _is_no_audio_stream_error("ffmpeg frame decode failed")
