"""Deterministic, serializable audio analysis for Motion Designer."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import subprocess
import wave
from typing import Any, Mapping
from collections.abc import Callable

import numpy as np

from .schema import new_motion_id


ANALYSIS_VERSION = "motion_audio_analysis_v1"
AUDIO_CHANNELS = ("amplitude", "bass", "mid", "treble", "onset")


class AudioAnalysisCancelled(RuntimeError):
    pass


@dataclass(slots=True)
class AudioEnvelopeSample:
    time_ms: int
    amplitude: float = 0.0
    bass: float = 0.0
    mid: float = 0.0
    treble: float = 0.0
    onset: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "time_ms": int(self.time_ms),
            "amplitude": float(self.amplitude),
            "bass": float(self.bass),
            "mid": float(self.mid),
            "treble": float(self.treble),
            "onset": float(self.onset),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AudioEnvelopeSample":
        return cls(
            time_ms=int(data.get("time_ms", 0) or 0),
            **{key: float(data.get(key, 0.0) or 0.0) for key in AUDIO_CHANNELS},
        )


@dataclass(slots=True)
class AudioAnalysisCache:
    id: str = field(default_factory=lambda: new_motion_id("audio_analysis"))
    source_path: str = ""
    source_signature: str = ""
    source_revision: str = ""
    timeline_start_ms: int = 0
    trim_start_ms: int = 0
    duration_ms: int = 0
    sample_rate: int = 22050
    hop_ms: int = 20
    samples: list[AudioEnvelopeSample] = field(default_factory=list)
    beat_markers: list[int] = field(default_factory=list)
    estimated_bpm: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_path": self.source_path,
            "source_signature": self.source_signature,
            "source_revision": self.source_revision,
            "timeline_start_ms": int(self.timeline_start_ms),
            "trim_start_ms": int(self.trim_start_ms),
            "duration_ms": int(self.duration_ms),
            "sample_rate": int(self.sample_rate),
            "hop_ms": int(self.hop_ms),
            "samples": [sample.to_dict() for sample in self.samples],
            "beat_markers": [int(value) for value in self.beat_markers],
            "estimated_bpm": float(self.estimated_bpm),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AudioAnalysisCache":
        return cls(
            id=str(data.get("id") or new_motion_id("audio_analysis")),
            source_path=str(data.get("source_path") or ""),
            source_signature=str(data.get("source_signature") or ""),
            source_revision=str(data.get("source_revision") or ""),
            timeline_start_ms=int(data.get("timeline_start_ms", 0) or 0),
            trim_start_ms=int(data.get("trim_start_ms", 0) or 0),
            duration_ms=max(0, int(data.get("duration_ms", 0) or 0)),
            sample_rate=max(1, int(data.get("sample_rate", 22050) or 22050)),
            hop_ms=max(1, int(data.get("hop_ms", 20) or 20)),
            samples=[AudioEnvelopeSample.from_dict(row) for row in data.get("samples", []) if isinstance(row, Mapping)],
            beat_markers=[int(value) for value in data.get("beat_markers", [])],
            estimated_bpm=float(data.get("estimated_bpm", 0.0) or 0.0),
            metadata=dict(data.get("metadata") or {}),
        )


def audio_source_signature(path: str | Path, source_revision: str = "") -> str:
    source = Path(path).expanduser().resolve()
    stat = source.stat()
    payload = json.dumps({
        "path": str(source).lower(),
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "revision": str(source_revision or ""),
        "analysis": ANALYSIS_VERSION,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def analysis_is_current(cache: AudioAnalysisCache | Mapping[str, Any], path: str | Path,
                        source_revision: str = "") -> bool:
    cached = cache if isinstance(cache, AudioAnalysisCache) else AudioAnalysisCache.from_dict(cache)
    try:
        return cached.source_signature == audio_source_signature(path, source_revision)
    except OSError:
        return False


def _pcm_to_float(raw: bytes, sample_width: int) -> np.ndarray:
    if sample_width == 1:
        return (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    if sample_width == 2:
        return np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if sample_width == 3:
        data = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = data[:, 0] | (data[:, 1] << 8) | (data[:, 2] << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float32) / 8388608.0
    if sample_width == 4:
        return np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    raise ValueError(f"unsupported WAV sample width: {sample_width}")


def _decode_wav(path: Path, sample_rate: int, trim_start_ms: int,
                duration_ms: int | None) -> np.ndarray:
    with wave.open(str(path), "rb") as source:
        channels = max(1, source.getnchannels())
        source_rate = max(1, source.getframerate())
        start_frame = min(source.getnframes(), int(source_rate * trim_start_ms / 1000))
        source.setpos(start_frame)
        frame_count = source.getnframes() - start_frame
        if duration_ms is not None:
            frame_count = min(frame_count, int(source_rate * max(0, duration_ms) / 1000))
        values = _pcm_to_float(source.readframes(frame_count), source.getsampwidth())
    if channels > 1:
        values = values[: (values.size // channels) * channels].reshape(-1, channels).mean(axis=1)
    if source_rate != sample_rate and values.size:
        output_count = max(1, int(round(values.size * sample_rate / source_rate)))
        positions = np.linspace(0.0, max(0, values.size - 1), output_count)
        values = np.interp(positions, np.arange(values.size), values).astype(np.float32)
    return values.astype(np.float32, copy=False)


def _decode_ffmpeg(path: Path, sample_rate: int, trim_start_ms: int,
                   duration_ms: int | None,
                   cancelled: Callable[[], bool] | None = None) -> np.ndarray:
    import imageio_ffmpeg

    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error"]
    if trim_start_ms:
        command += ["-ss", f"{trim_start_ms / 1000.0:.6f}"]
    command += ["-i", str(path)]
    if duration_ms is not None:
        command += ["-t", f"{max(0, duration_ms) / 1000.0:.6f}"]
    command += ["-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "f32le", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        if cancelled and cancelled():
            process.terminate()
            process.communicate()
            raise AudioAnalysisCancelled("Audio analysis cancelled")
        try:
            stdout, stderr = process.communicate(timeout=.1)
            break
        except subprocess.TimeoutExpired:
            continue
    if process.returncode:
        message = stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"audio decode failed: {message or path.name}")
    return np.frombuffer(stdout, dtype="<f4").astype(np.float32, copy=True)


def decode_audio_mono(path: str | Path, *, sample_rate: int = 22050,
                      trim_start_ms: int = 0, duration_ms: int | None = None,
                      cancelled: Callable[[], bool] | None = None) -> np.ndarray:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if cancelled and cancelled():
        raise AudioAnalysisCancelled("Audio analysis cancelled")
    if source.suffix.lower() == ".wav":
        try:
            values = _decode_wav(source, sample_rate, max(0, int(trim_start_ms)), duration_ms)
            if cancelled and cancelled():
                raise AudioAnalysisCancelled("Audio analysis cancelled")
            return values
        except (wave.Error, ValueError):
            pass
    return _decode_ffmpeg(source, sample_rate, max(0, int(trim_start_ms)), duration_ms, cancelled)


def _normalize(values: np.ndarray) -> np.ndarray:
    if not values.size:
        return values.astype(np.float32)
    positive = values[values > 1e-8]
    scale = float(np.percentile(positive, 95)) if positive.size else 1.0
    return np.clip(values / max(1e-8, scale), 0.0, 1.0).astype(np.float32)


def analyze_audio(path: str | Path, *, timeline_start_ms: int = 0, trim_start_ms: int = 0,
                  duration_ms: int | None = None, source_revision: str = "",
                  sample_rate: int = 22050, hop_ms: int = 20,
                  cancelled: Callable[[], bool] | None = None) -> AudioAnalysisCache:
    source = Path(path).expanduser().resolve()
    rate = max(8000, int(sample_rate))
    hop = max(5, int(hop_ms))
    audio = decode_audio_mono(
        source, sample_rate=rate, trim_start_ms=trim_start_ms,
        duration_ms=duration_ms, cancelled=cancelled,
    )
    hop_samples = max(1, int(round(rate * hop / 1000.0)))
    window_size = 1
    while window_size < max(512, hop_samples * 2):
        window_size *= 2
    frame_count = max(1, int(np.ceil(max(1, audio.size) / hop_samples)))
    padded = np.pad(audio, (0, max(0, (frame_count - 1) * hop_samples + window_size - audio.size)))
    window = np.hanning(window_size).astype(np.float32)
    frequencies = np.fft.rfftfreq(window_size, 1.0 / rate)
    bands = ((20.0, 250.0), (250.0, 4000.0), (4000.0, min(16000.0, rate * 0.5)))
    amplitude_raw = np.zeros(frame_count, dtype=np.float32)
    band_raw = np.zeros((frame_count, 3), dtype=np.float32)
    flux = np.zeros(frame_count, dtype=np.float32)
    previous_spectrum: np.ndarray | None = None
    for index in range(frame_count):
        if index % 32 == 0 and cancelled and cancelled():
            raise AudioAnalysisCancelled("Audio analysis cancelled")
        frame = padded[index * hop_samples:index * hop_samples + window_size]
        amplitude_raw[index] = float(np.sqrt(np.mean(frame * frame)))
        spectrum = np.abs(np.fft.rfft(frame * window)).astype(np.float32)
        if previous_spectrum is not None:
            flux[index] = float(np.maximum(spectrum - previous_spectrum, 0.0).mean())
        previous_spectrum = spectrum
        for band_index, (low, high) in enumerate(bands):
            mask = (frequencies >= low) & (frequencies < high)
            if np.any(mask):
                band_raw[index, band_index] = float(np.sqrt(np.mean(spectrum[mask] ** 2)))
    amplitude = _normalize(amplitude_raw)
    total = band_raw.sum(axis=1)
    band_mix = np.divide(band_raw, total[:, None], out=np.zeros_like(band_raw), where=total[:, None] > 1e-8)
    band_mix *= amplitude[:, None]
    onset = _normalize(flux)
    threshold = max(0.28, float(np.mean(onset) + np.std(onset) * 0.45))
    beat_indexes: list[int] = []
    min_spacing = max(1, int(round(200 / hop)))
    for index in range(1, frame_count - 1):
        if onset[index] < threshold or onset[index] < onset[index - 1] or onset[index] < onset[index + 1]:
            continue
        if beat_indexes and index - beat_indexes[-1] < min_spacing:
            if onset[index] > onset[beat_indexes[-1]]:
                beat_indexes[-1] = index
            continue
        beat_indexes.append(index)
    start = max(0, int(timeline_start_ms))
    samples = [AudioEnvelopeSample(
        time_ms=start + index * hop,
        amplitude=float(amplitude[index]),
        bass=float(band_mix[index, 0]),
        mid=float(band_mix[index, 1]),
        treble=float(band_mix[index, 2]),
        onset=float(onset[index]),
    ) for index in range(frame_count)]
    beat_markers = [start + index * hop for index in beat_indexes]
    intervals = np.diff(beat_markers)
    estimated_bpm = float(60000.0 / np.median(intervals)) if intervals.size and np.median(intervals) > 0 else 0.0
    actual_duration = int(round(audio.size * 1000.0 / rate))
    return AudioAnalysisCache(
        source_path=str(source), source_signature=audio_source_signature(source, source_revision),
        source_revision=str(source_revision or ""), timeline_start_ms=start,
        trim_start_ms=max(0, int(trim_start_ms)), duration_ms=actual_duration,
        sample_rate=rate, hop_ms=hop, samples=samples, beat_markers=beat_markers,
        estimated_bpm=estimated_bpm,
        metadata={"analysis_version": ANALYSIS_VERSION, "decoder": "wav_or_ffmpeg", "channels": list(AUDIO_CHANNELS)},
    )


def analysis_value_at(cache: AudioAnalysisCache | Mapping[str, Any], channel: str,
                      composition_time_ms: float) -> float:
    analysis = cache if isinstance(cache, AudioAnalysisCache) else AudioAnalysisCache.from_dict(cache)
    name = str(channel or "amplitude").lower()
    if name not in AUDIO_CHANNELS or not analysis.samples:
        return 0.0
    position = (float(composition_time_ms) - analysis.timeline_start_ms) / max(1, analysis.hop_ms)
    if position < 0.0 or position > len(analysis.samples) - 1:
        return 0.0
    left = int(position)
    right = min(len(analysis.samples) - 1, left + 1)
    t = position - left
    a = float(getattr(analysis.samples[left], name))
    b = float(getattr(analysis.samples[right], name))
    return a + (b - a) * t


__all__ = [
    "ANALYSIS_VERSION", "AUDIO_CHANNELS", "AudioAnalysisCache", "AudioAnalysisCancelled",
    "AudioEnvelopeSample",
    "analysis_is_current", "analysis_value_at", "analyze_audio", "audio_source_signature",
    "decode_audio_mono",
]
