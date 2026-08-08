from __future__ import annotations

import wave
from pathlib import Path

import numpy as np


def _write_test_wav(path: Path, samples: np.ndarray, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -0.999, 0.999) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(samples.shape[1])
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm.tobytes())


def test_music_audio_glitch_probe_detects_and_repairs_short_faults(tmp_path: Path) -> None:
    from tools.music_audio_glitch_probe import analyze_wav, repair_wav

    sample_rate = 44100
    length = sample_rate * 2
    t = np.arange(length, dtype=np.float32) / float(sample_rate)
    base = np.sin(2.0 * np.pi * 220.0 * t) * 0.045
    samples = np.stack([base, base], axis=1).astype(np.float32)

    click = int(0.42 * sample_rate)
    samples[click] += np.array([0.55, -0.52], dtype=np.float32)
    drop_start = int(0.80 * sample_rate)
    drop_stop = drop_start + int(0.010 * sample_rate)
    samples[drop_start:drop_stop] *= 0.08
    surge_start = int(1.20 * sample_rate)
    surge_stop = surge_start + int(0.010 * sample_rate)
    samples[surge_start:surge_stop] *= 5.0

    source = tmp_path / "faulty.wav"
    repaired = tmp_path / "repaired.wav"
    _write_test_wav(source, samples, sample_rate)

    before = analyze_wav(source, sample_jump_threshold=0.095)
    after = repair_wav(source, repaired, sample_jump_threshold=0.095)

    assert before["sample_jumps"]["count"] >= 1
    assert before["hard_glitch_score"] == before["glitch_score"]
    assert "spectral_motion_score" in before
    assert before["diagnostic_notes"]
    assert any(row["drop_count"] >= 1 for row in before["frame_anomalies"])
    assert any(row["surge_count"] >= 1 for row in before["frame_anomalies"])
    assert repaired.exists()
    assert after["sample_jumps"]["max_jump"] < before["sample_jumps"]["max_jump"]


def test_music_audio_glitch_probe_reports_envelope_pumping(tmp_path: Path) -> None:
    from tools.music_audio_glitch_probe import analyze_wav

    sample_rate = 44100
    length = sample_rate * 4
    t = np.arange(length, dtype=np.float32) / float(sample_rate)
    tone = np.sin(2.0 * np.pi * 220.0 * t) * 0.06
    flat = np.stack([tone, tone], axis=1).astype(np.float32)
    pump_gain = 0.34 + 0.66 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 2.0 * t))
    pumped = np.stack([tone * pump_gain, tone * pump_gain], axis=1).astype(np.float32)

    flat_path = tmp_path / "flat.wav"
    pumped_path = tmp_path / "pumped.wav"
    _write_test_wav(flat_path, flat, sample_rate)
    _write_test_wav(pumped_path, pumped, sample_rate)

    flat_report = analyze_wav(flat_path, bpm=120.0)
    pumped_report = analyze_wav(pumped_path, bpm=120.0)

    assert pumped_report["envelope_pumping"]["beat_peak_to_peak_db"] > 5.0
    assert pumped_report["envelope_pumping"]["beat_peak_to_peak_db"] > flat_report["envelope_pumping"]["beat_peak_to_peak_db"] + 4.0
    assert pumped_report["envelope_pumping"]["top_modulations"]
