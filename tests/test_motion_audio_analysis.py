from __future__ import annotations

import math
from pathlib import Path
import wave

import numpy as np

from app.motion_designer.audio_analysis import (
    AudioAnalysisCancelled, analysis_is_current, analysis_value_at, analyze_audio,
)
import pytest


def _write_wav(path: Path, samples: np.ndarray, rate: int = 22050) -> None:
    pcm = np.clip(samples, -1.0, 1.0)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes((pcm * 32767.0).astype("<i2").tobytes())


def test_audio_analysis_extracts_bands_onsets_and_serializable_cache(tmp_path) -> None:
    rate = 22050
    seconds = 2.0
    t = np.arange(int(rate * seconds), dtype=np.float32) / rate
    audio = np.zeros_like(t)
    first = t < 1.0
    audio[first] = 0.45 * np.sin(2.0 * math.pi * 90.0 * t[first])
    audio[~first] = 0.45 * np.sin(2.0 * math.pi * 7000.0 * t[~first])
    for pulse_s in (0.25, 0.75, 1.25, 1.75):
        start = int(pulse_s * rate)
        audio[start:start + 180] += np.hanning(180).astype(np.float32) * 0.8
    path = tmp_path / "bands.wav"
    _write_wav(path, audio, rate)

    cache = analyze_audio(path, timeline_start_ms=500, hop_ms=20, source_revision="take-1")
    first_bass = np.mean([row.bass for row in cache.samples if 600 <= row.time_ms < 1400])
    first_treble = np.mean([row.treble for row in cache.samples if 600 <= row.time_ms < 1400])
    last_bass = np.mean([row.bass for row in cache.samples if 1600 <= row.time_ms < 2400])
    last_treble = np.mean([row.treble for row in cache.samples if 1600 <= row.time_ms < 2400])
    assert first_bass > first_treble * 4
    assert last_treble > last_bass * 4
    assert len(cache.beat_markers) >= 2
    assert analysis_value_at(cache, "amplitude", 1000) > 0.1
    restored = type(cache).from_dict(cache.to_dict())
    assert restored.source_signature == cache.source_signature
    assert analysis_is_current(restored, path, "take-1")
    assert not analysis_is_current(restored, path, "take-2")


def test_audio_analysis_respects_trim_duration_and_timeline_offset(tmp_path) -> None:
    rate = 16000
    t = np.arange(rate * 2, dtype=np.float32) / rate
    path = tmp_path / "trim.wav"
    _write_wav(path, 0.4 * np.sin(2 * math.pi * 440 * t), rate)
    cache = analyze_audio(path, trim_start_ms=500, duration_ms=600, timeline_start_ms=1200,
                          sample_rate=16000, hop_ms=25)
    assert 575 <= cache.duration_ms <= 625
    assert cache.samples[0].time_ms == 1200
    assert analysis_value_at(cache, "amplitude", 1199) == 0.0
    assert analysis_value_at(cache, "amplitude", 1400) > 0.5


def test_audio_analysis_can_be_cancelled_before_decode(tmp_path) -> None:
    path = tmp_path / "cancel.wav"
    _write_wav(path, np.zeros(1000, dtype=np.float32), 16000)
    with pytest.raises(AudioAnalysisCancelled):
        analyze_audio(path, cancelled=lambda: True)
