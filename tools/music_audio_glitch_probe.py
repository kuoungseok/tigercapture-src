from __future__ import annotations

import argparse
import csv
import json
import math
import wave
from pathlib import Path
from typing import Any

import numpy as np


def _read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    if sample_width != 2:
        raise ValueError(f"Only 16-bit PCM WAV is supported, got {sample_width * 8}-bit: {path}")
    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if channels <= 0:
        raise ValueError(f"Invalid channel count: {channels}")
    return data.reshape(-1, channels), sample_rate


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -0.999, 0.999)
    pcm = (clipped * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(int(samples.shape[1]))
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(pcm.tobytes())


def _frame_rms(samples: np.ndarray, sample_rate: int, window_ms: float) -> tuple[np.ndarray, int]:
    window = max(1, int(round(sample_rate * float(window_ms) / 1000.0)))
    rows = []
    for start in range(0, max(0, len(samples) - window), window):
        rows.append(float(np.sqrt(np.mean(samples[start:start + window] ** 2))))
    return np.asarray(rows, dtype=np.float32), window


def _top_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return rows[: max(0, int(limit))]


def _detect_frame_anomalies(samples: np.ndarray, sample_rate: int, *, window_ms: float) -> dict[str, Any]:
    rms, window = _frame_rms(samples, sample_rate, window_ms)
    global_rms = float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0
    drops: list[dict[str, Any]] = []
    surges: list[dict[str, Any]] = []
    for idx in range(1, len(rms) - 1):
        neighbor = float((rms[idx - 1] + rms[idx + 1]) * 0.5)
        current = float(rms[idx])
        timestamp = idx * window / float(sample_rate)
        if neighbor > max(0.015, global_rms * 0.55) and current < neighbor * 0.22:
            drops.append(
                {
                    "time_sec": round(timestamp, 6),
                    "rms": current,
                    "neighbor_rms": neighbor,
                    "ratio": current / max(neighbor, 1e-9),
                }
            )
        if neighbor > max(0.015, global_rms * 0.40) and current > max(global_rms * 1.70, neighbor * 2.40):
            surges.append(
                {
                    "time_sec": round(timestamp, 6),
                    "rms": current,
                    "neighbor_rms": neighbor,
                    "ratio": current / max(neighbor, 1e-9),
                }
            )
    drops.sort(key=lambda row: row["ratio"])
    surges.sort(key=lambda row: row["ratio"], reverse=True)
    return {
        "window_ms": float(window_ms),
        "drop_count": len(drops),
        "surge_count": len(surges),
        "drops": _top_rows(drops, 40),
        "surges": _top_rows(surges, 40),
    }


def _detect_sample_jumps(samples: np.ndarray, sample_rate: int, *, threshold: float = 0.095) -> dict[str, Any]:
    if len(samples) < 2:
        return {"threshold": threshold, "count": 0, "max_jump": 0.0, "events": []}
    jumps = np.max(np.abs(np.diff(samples, axis=0)), axis=1)
    indices = np.where(jumps > float(threshold))[0]
    events = [
        {
            "time_sec": round(float(idx) / float(sample_rate), 6),
            "jump": float(jumps[idx]),
        }
        for idx in indices
    ]
    events.sort(key=lambda row: row["jump"], reverse=True)
    return {
        "threshold": float(threshold),
        "count": len(events),
        "max_jump": float(np.max(jumps)) if jumps.size else 0.0,
        "events": _top_rows(events, 80),
    }


def _spectral_wobble(samples: np.ndarray, sample_rate: int) -> dict[str, Any]:
    mono = np.mean(samples, axis=1)
    frame = max(256, int(round(sample_rate * 0.050)))
    hop = max(128, frame // 2)
    if len(mono) < frame:
        return {"count": 0, "events": []}
    window = np.hanning(frame).astype(np.float32)
    freqs = np.fft.rfftfreq(frame, 1.0 / sample_rate)
    mask = (freqs >= 80.0) & (freqs <= 2200.0)
    rows: list[tuple[float, float, float, float]] = []
    for start in range(0, len(mono) - frame + 1, hop):
        chunk = mono[start:start + frame]
        rms = float(np.sqrt(np.mean(chunk * chunk)))
        if rms < 0.010:
            continue
        spec = np.abs(np.fft.rfft(chunk * window))
        band = spec[mask]
        if band.size == 0:
            continue
        peak_idx = int(np.argmax(band))
        peak = float(band[peak_idx])
        mean = float(np.mean(band) + 1e-9)
        dominance = peak / mean
        if dominance < 14.0:
            continue
        rows.append((start / float(sample_rate), float(freqs[mask][peak_idx]), rms, dominance))
    events: list[dict[str, Any]] = []
    for prev, current in zip(rows, rows[1:]):
        time_delta = current[0] - prev[0]
        if time_delta > 0.080:
            continue
        rms_ratio = current[2] / max(prev[2], 1e-9)
        if not 0.72 <= rms_ratio <= 1.38:
            continue
        freq_ratio = abs(current[1] - prev[1]) / max(1.0, min(current[1], prev[1]))
        if 0.045 < freq_ratio < 0.35:
            events.append(
                {
                    "time_sec": round(current[0], 6),
                    "prev_freq_hz": round(prev[1], 3),
                    "freq_hz": round(current[1], 3),
                    "relative_jump": freq_ratio,
                    "dominance": current[3],
                }
            )
    events.sort(key=lambda row: row["relative_jump"], reverse=True)
    return {"count": len(events), "events": _top_rows(events, 80)}


def _envelope_pumping(samples: np.ndarray, sample_rate: int, *, bpm: float = 0.0) -> dict[str, Any]:
    mono = np.mean(samples, axis=1)
    window = max(1, int(round(sample_rate * 0.020)))
    if len(mono) < window * 16:
        return {
            "window_ms": 20.0,
            "motion_db_std": 0.0,
            "db_step_p95": 0.0,
            "db_step_max": 0.0,
            "top_modulations": [],
            "beat_rate_hz": 0.0,
            "beat_peak_to_peak_db": 0.0,
        }
    env = np.asarray(
        [float(np.sqrt(np.mean(mono[start:start + window] ** 2))) for start in range(0, len(mono) - window, window)],
        dtype=np.float32,
    )
    db = 20.0 * np.log10(env + 1e-6)
    db_delta = np.abs(np.diff(db)) if len(db) > 1 else np.asarray([], dtype=np.float32)
    log_env = np.log(env + 1e-6)
    frame_rate = sample_rate / float(window)
    smooth_width = max(3, int(round(0.60 * frame_rate)))
    if smooth_width % 2 == 0:
        smooth_width += 1
    trend = np.convolve(log_env, np.ones(smooth_width, dtype=np.float32) / float(smooth_width), mode="same")
    motion = log_env - trend
    if len(motion) > smooth_width * 2:
        motion = motion[smooth_width:-smooth_width]
    if len(motion) < 8:
        top_modulations: list[dict[str, Any]] = []
        motion_db_std = 0.0
    else:
        centered = motion - float(np.mean(motion))
        spec = np.abs(np.fft.rfft(centered * np.hanning(len(centered))))
        freqs = np.fft.rfftfreq(len(centered), 1.0 / frame_rate)
        mask = (freqs >= 0.4) & (freqs <= 8.0)
        band_freqs = freqs[mask]
        band_spec = spec[mask]
        if band_spec.size:
            top_indices = np.argsort(band_spec)[-8:][::-1]
            top_modulations = [
                {
                    "hz": round(float(band_freqs[index]), 3),
                    "strength": round(float(band_spec[index]), 3),
                }
                for index in top_indices
            ]
        else:
            top_modulations = []
        motion_db_std = float(np.std(centered) * 20.0 / math.log(10.0))
    beat_rate_hz = float(bpm) / 60.0 if float(bpm or 0.0) > 0.0 else 0.0
    beat_peak_to_peak_db = 0.0
    if beat_rate_hz > 0.0 and len(motion) >= 8:
        time = np.arange(len(motion), dtype=np.float64) / float(frame_rate)
        matrix = np.column_stack(
            [
                np.sin(2.0 * math.pi * beat_rate_hz * time),
                np.cos(2.0 * math.pi * beat_rate_hz * time),
                np.ones_like(time),
            ]
        )
        coeff, *_ = np.linalg.lstsq(matrix, motion.astype(np.float64), rcond=None)
        amp = float(math.sqrt(float(coeff[0]) ** 2 + float(coeff[1]) ** 2))
        beat_peak_to_peak_db = 2.0 * amp * 20.0 / math.log(10.0)
    return {
        "window_ms": 20.0,
        "motion_db_std": round(motion_db_std, 3),
        "db_step_p95": round(float(np.percentile(db_delta, 95)) if db_delta.size else 0.0, 3),
        "db_step_max": round(float(np.max(db_delta)) if db_delta.size else 0.0, 3),
        "top_modulations": top_modulations,
        "beat_rate_hz": round(beat_rate_hz, 3),
        "beat_peak_to_peak_db": round(beat_peak_to_peak_db, 3),
    }


def analyze_wav(path: Path, *, sample_jump_threshold: float = 0.095, bpm: float = 0.0) -> dict[str, Any]:
    samples, sample_rate = _read_wav(path)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = [float(np.sqrt(np.mean(samples[:, channel] ** 2))) for channel in range(samples.shape[1])]
    windows = [
        _detect_frame_anomalies(samples, sample_rate, window_ms=window_ms)
        for window_ms in (10.0, 25.0, 50.0)
    ]
    jumps = _detect_sample_jumps(samples, sample_rate, threshold=sample_jump_threshold)
    wobble = _spectral_wobble(samples, sample_rate)
    pumping = _envelope_pumping(samples, sample_rate, bpm=bpm)
    hard_score = (
        jumps["count"] * 3
        + sum(row["drop_count"] for row in windows if row["window_ms"] >= 25.0)
        + sum(row["surge_count"] * 2 for row in windows if row["window_ms"] <= 25.0)
    )
    spectral_motion_score = wobble["count"] * 2
    return {
        "path": str(path.resolve()),
        "sample_rate": sample_rate,
        "channels": int(samples.shape[1]),
        "duration_sec": len(samples) / float(sample_rate),
        "peak": peak,
        "rms": rms,
        "glitch_score": int(hard_score),
        "hard_glitch_score": int(hard_score),
        "spectral_motion_score": int(spectral_motion_score),
        "sample_jumps": jumps,
        "frame_anomalies": windows,
        "spectral_wobble": wobble,
        "envelope_pumping": pumping,
        "diagnostic_notes": [
            "glitch_score counts hard discontinuities, isolated frame drops, and surges.",
            "spectral_wobble is a candidate list only; musical bass/chord changes can appear here.",
            "envelope_pumping tracks beat-rate volume motion; high values can sound like huffing/pumping even when glitch_score is zero.",
            "Inspect stems before treating spectral_wobble as a tape/wow/flutter defect.",
        ],
    }


def _smooth_sample_jumps(samples: np.ndarray, sample_rate: int, *, threshold: float, radius_ms: float) -> None:
    if len(samples) < 4:
        return
    radius = max(2, int(round(sample_rate * float(radius_ms) / 1000.0)))
    jumps = np.max(np.abs(np.diff(samples, axis=0)), axis=1)
    indices = np.where(jumps > float(threshold))[0] + 1
    for idx in indices:
        start = max(1, int(idx) - radius)
        stop = min(len(samples) - 2, int(idx) + radius)
        if stop <= start:
            continue
        left = samples[start - 1].copy()
        right = samples[stop + 1].copy()
        count = stop - start + 1
        fade = np.linspace(0.0, 1.0, count + 2, dtype=np.float32)[1:-1]
        interp = left[None, :] * (1.0 - fade[:, None]) + right[None, :] * fade[:, None]
        samples[start:stop + 1] = samples[start:stop + 1] * 0.30 + interp * 0.70


def _repair_frame_drops(samples: np.ndarray, sample_rate: int, *, window_ms: float) -> None:
    rms, window = _frame_rms(samples, sample_rate, window_ms)
    if len(rms) < 3:
        return
    global_rms = float(np.sqrt(np.mean(samples * samples)))
    for idx in range(1, len(rms) - 1):
        neighbor = float((rms[idx - 1] + rms[idx + 1]) * 0.5)
        current = float(rms[idx])
        if neighbor <= max(0.012, global_rms * 0.35):
            continue
        if current >= neighbor * 0.35 or current <= 0.000001:
            continue
        gain = min(2.25, max(1.0, (neighbor * 0.45) / current))
        start = idx * window
        stop = min(len(samples), start + window)
        fade = min((stop - start) // 2, max(8, window // 4))
        envelope = np.full(stop - start, gain, dtype=np.float32)
        if fade > 1:
            envelope[:fade] = np.linspace(1.0, gain, fade, dtype=np.float32)
            envelope[-fade:] = np.linspace(gain, 1.0, fade, dtype=np.float32)
        samples[start:stop] *= envelope[:, None]


def _repair_frame_surges(samples: np.ndarray, sample_rate: int, *, window_ms: float) -> None:
    rms, window = _frame_rms(samples, sample_rate, window_ms)
    if len(rms) < 3:
        return
    global_rms = float(np.sqrt(np.mean(samples * samples)))
    for idx in range(1, len(rms) - 1):
        neighbor = float((rms[idx - 1] + rms[idx + 1]) * 0.5)
        current = float(rms[idx])
        if neighbor <= max(0.012, global_rms * 0.25):
            continue
        if current <= max(global_rms * 1.50, neighbor * 2.20):
            continue
        target = max(global_rms * 1.30, neighbor * 2.00)
        gain = max(0.70, min(1.0, target / max(current, 0.000001)))
        start = idx * window
        stop = min(len(samples), start + window)
        fade = min((stop - start) // 2, max(8, window // 4))
        envelope = np.full(stop - start, gain, dtype=np.float32)
        if fade > 1:
            envelope[:fade] = np.linspace(1.0, gain, fade, dtype=np.float32)
            envelope[-fade:] = np.linspace(gain, 1.0, fade, dtype=np.float32)
        samples[start:stop] *= envelope[:, None]


def repair_wav(input_path: Path, output_path: Path, *, sample_jump_threshold: float = 0.095, bpm: float = 0.0) -> dict[str, Any]:
    samples, sample_rate = _read_wav(input_path)
    repaired = samples.astype(np.float32, copy=True)
    _smooth_sample_jumps(repaired, sample_rate, threshold=sample_jump_threshold, radius_ms=0.32)
    for window_ms in (5.0, 10.0, 25.0):
        _repair_frame_drops(repaired, sample_rate, window_ms=window_ms)
        _repair_frame_surges(repaired, sample_rate, window_ms=window_ms)
    peak = float(np.max(np.abs(repaired))) if repaired.size else 0.0
    if peak > 0.98:
        repaired *= 0.98 / peak
    _write_wav(output_path, repaired, sample_rate)
    return analyze_wav(output_path, sample_jump_threshold=sample_jump_threshold, bpm=bpm)


def _write_events_csv(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for event in report["sample_jumps"]["events"]:
        rows.append({"kind": "sample_jump", **event})
    for window in report["frame_anomalies"]:
        for event in window["drops"]:
            rows.append({"kind": f"drop_{window['window_ms']}ms", **event})
        for event in window["surges"]:
            rows.append({"kind": f"surge_{window['window_ms']}ms", **event})
    for event in report["spectral_wobble"]["events"]:
        rows.append({"kind": "spectral_wobble", **event})
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze and conservatively repair short audio glitches in WAV files.")
    parser.add_argument("input_wav", type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--events-csv", type=Path, default=None)
    parser.add_argument("--repair-output", type=Path, default=None)
    parser.add_argument("--sample-jump-threshold", type=float, default=0.095)
    parser.add_argument("--bpm", type=float, default=0.0)
    args = parser.parse_args()

    report = analyze_wav(args.input_wav, sample_jump_threshold=args.sample_jump_threshold, bpm=args.bpm)
    if args.repair_output:
        repair_report = repair_wav(
            args.input_wav,
            args.repair_output,
            sample_jump_threshold=args.sample_jump_threshold,
            bpm=args.bpm,
        )
        report["repair_output"] = str(args.repair_output.resolve())
        report["repair_report"] = repair_report
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.events_csv:
        _write_events_csv(args.events_csv, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
