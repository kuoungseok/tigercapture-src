from __future__ import annotations

import argparse
import json
import math
import sys
import wave
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import music_composer as composer
from tools.music_audio_glitch_probe import analyze_wav


STAGE_ORDER = [
    "00_dry_note_mix",
    "01_shaped_stem_mix",
    "02_bus_polish_no_spatial_mix",
    "03_bus_spatial_gain_mix",
    "04_master_no_micro_mix",
    "05_master_full_mix",
]

ABLATION_ORDER = [
    "dry_no_drums_mix",
    "dry_drums_only_mix",
]


def _empty(length: int) -> np.ndarray:
    return np.zeros((length, 2), dtype=np.float32)


def _render_track_notes(composition: composer.MusicComposition, track: composer.MusicTrack, length: int) -> np.ndarray:
    samples = _empty(length)
    for clip in track.clips:
        for note in clip.notes:
            composer._render_note_tone(  # noqa: SLF001 - diagnostic tool intentionally probes private render stages.
                samples,
                note,
                bpm=composition.bpm,
                role=track.role,
                volume=track.volume,
                pan=track.pan,
                timing_jitter_scale=0.12,
            )
    return samples


def _sum_rows(rows: list[np.ndarray], length: int) -> np.ndarray:
    mix = _empty(length)
    for row in rows:
        mix += row
    return mix


def _resample_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if src_rate == dst_rate:
        return samples.astype(np.float32, copy=True)
    if len(samples) <= 1:
        return samples.astype(np.float32, copy=True)
    duration = (len(samples) - 1) / float(src_rate)
    dst_len = int(round(duration * float(dst_rate))) + 1
    src_x = np.arange(len(samples), dtype=np.float64) / float(src_rate)
    dst_x = np.arange(dst_len, dtype=np.float64) / float(dst_rate)
    out = np.zeros((dst_len, samples.shape[1]), dtype=np.float32)
    for channel in range(samples.shape[1]):
        out[:, channel] = np.interp(dst_x, src_x, samples[:, channel]).astype(np.float32)
    return out


def _write_wav_at_rate(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -0.999, 0.999) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(int(samples.shape[1]))
        handle.setsampwidth(2)
        handle.setframerate(int(sample_rate))
        handle.writeframes(pcm.tobytes())


def _playback_safe_samples(samples: np.ndarray) -> tuple[np.ndarray, int]:
    sample_rate = 48000
    safe = _resample_linear(samples, composer.SAMPLE_RATE, sample_rate)
    peak = float(np.max(np.abs(safe))) if safe.size else 0.0
    if peak > 0.000001:
        safe = safe * min(8.0, 0.45 / peak)
    return safe.astype(np.float32, copy=False), sample_rate


def _metrics_for_report(report: dict[str, Any]) -> dict[str, Any]:
    pumping = report.get("envelope_pumping") or {}
    return {
        "glitch_score": int(report.get("glitch_score") or 0),
        "sample_jumps": int((report.get("sample_jumps") or {}).get("count") or 0),
        "max_jump": float((report.get("sample_jumps") or {}).get("max_jump") or 0.0),
        "frame_anomalies": [
            {
                "window_ms": row.get("window_ms"),
                "drops": row.get("drop_count"),
                "surges": row.get("surge_count"),
            }
            for row in report.get("frame_anomalies", [])
        ],
        "beat_peak_to_peak_db": float(pumping.get("beat_peak_to_peak_db") or 0.0),
        "motion_db_std": float(pumping.get("motion_db_std") or 0.0),
        "db_step_p95": float(pumping.get("db_step_p95") or 0.0),
        "top_modulations": list(pumping.get("top_modulations") or [])[:4],
    }


def _write_and_analyze(path: Path, samples: np.ndarray, *, bpm: int) -> dict[str, Any]:
    composer._write_wav(path, samples)  # noqa: SLF001
    report = analyze_wav(path, bpm=bpm)
    report_path = path.with_suffix(path.suffix + ".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    safe_samples, safe_rate = _playback_safe_samples(samples)
    safe_path = path.with_name(f"{path.stem}_playback_safe_48k.wav")
    _write_wav_at_rate(safe_path, safe_samples, safe_rate)
    return {
        "wav": str(path),
        "playback_safe_wav": str(safe_path),
        "report": str(report_path),
        "metrics": _metrics_for_report(report),
    }


def render_sample_production_stages(
    *,
    output_dir: Path,
    prompt: str,
    duration_ms: int,
    genre: str,
    mood: str,
    bpm: int,
    key: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    composition = composer.compose_music(
        prompt=prompt,
        duration_ms=duration_ms,
        genre=genre,
        mood=mood,
        bpm=bpm,
        key=key,
    )
    length = max(1, int(math.ceil((composition.duration_ms + 3000) / 1000.0 * composer.SAMPLE_RATE)))
    bus_order = ["percussion", "low", "orchestra", "pads", "lead", "fx"]
    bus_gains = {
        "percussion": 0.74,
        "low": 0.72,
        "orchestra": 0.74,
        "pads": 0.68,
        "lead": 0.70,
        "fx": 0.54,
    }

    raw_tracks = [_render_track_notes(composition, track, length) for track in composition.tracks]
    shaped_tracks: list[np.ndarray] = []
    bus_polished_tracks: list[tuple[str, np.ndarray]] = []
    for track, raw in zip(composition.tracks, raw_tracks):
        shaped = raw.copy()
        composer._shape_stem(track.role, shaped)  # noqa: SLF001
        shaped_tracks.append(shaped)

        bus_name = composer._sample_production_bus_for_role(track.role)  # noqa: SLF001
        polished = shaped.copy()
        composer._apply_sample_bus_polish(polished, bus=bus_name, bpm=composition.bpm, spatial=False)  # noqa: SLF001
        bus_polished_tracks.append((bus_name, polished))

    buses = {name: _empty(length) for name in bus_order}
    for bus_name, samples in bus_polished_tracks:
        buses[bus_name] += samples

    stage_samples: dict[str, np.ndarray] = {
        "00_dry_note_mix": _sum_rows(raw_tracks, length),
        "01_shaped_stem_mix": _sum_rows(shaped_tracks, length),
        "02_bus_polish_no_spatial_mix": _sum_rows([samples for _bus, samples in bus_polished_tracks], length),
    }

    spatial_mix = _empty(length)
    for bus_name in bus_order:
        bus_samples = buses[bus_name].copy()
        if not np.any(bus_samples):
            continue
        composer._apply_sample_bus_polish(bus_samples, bus=bus_name, bpm=composition.bpm, spatial=True)  # noqa: SLF001
        bus_samples *= float(bus_gains.get(bus_name, 0.72))
        spatial_mix += bus_samples
    if composition.tracks:
        spatial_mix *= min(1.0, 4.0 / math.sqrt(max(1.0, float(len(composition.tracks)))))
    stage_samples["03_bus_spatial_gain_mix"] = spatial_mix

    master_no_micro = spatial_mix.copy()
    composer._sample_production_master(  # noqa: SLF001
        master_no_micro,
        bpm=composition.bpm,
        key=composition.key,
        prompt=composition.prompt,
        repair_micro_dropouts=False,
    )
    stage_samples["04_master_no_micro_mix"] = master_no_micro

    master_full = spatial_mix.copy()
    composer._sample_production_master(  # noqa: SLF001
        master_full,
        bpm=composition.bpm,
        key=composition.key,
        prompt=composition.prompt,
        repair_micro_dropouts=True,
    )
    stage_samples["05_master_full_mix"] = master_full

    stages: list[dict[str, Any]] = []
    for stage_name in STAGE_ORDER:
        wav_path = output_dir / f"{composition.id}_{stage_name}.wav"
        analyzed = _write_and_analyze(wav_path, stage_samples[stage_name], bpm=composition.bpm)
        stages.append(
            {
                "stage": stage_name,
                **analyzed,
            }
        )

    no_drums = _empty(length)
    drums_only = _empty(length)
    for track, raw in zip(composition.tracks, raw_tracks):
        if track.role == "drums":
            drums_only += raw
        else:
            no_drums += raw
    ablations: list[dict[str, Any]] = []
    for name, samples in (("dry_no_drums_mix", no_drums), ("dry_drums_only_mix", drums_only)):
        wav_path = output_dir / f"{composition.id}_{name}.wav"
        analyzed = _write_and_analyze(wav_path, samples, bpm=composition.bpm)
        ablations.append({"stage": name, **analyzed})

    summary = {
        "composition_id": composition.id,
        "prompt": composition.prompt,
        "bpm": composition.bpm,
        "key": composition.key,
        "output_dir": str(output_dir),
        "stages": stages,
        "ablations": ablations,
    }
    summary_path = output_dir / f"{composition.id}_stage_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Music Lab sample-production stages for elimination testing.")
    parser.add_argument("--output-dir", type=Path, default=Path("debugCapture/music_stage_probe"))
    parser.add_argument("--prompt", default="original NCS style melodic EDM hook with long evolving lead")
    parser.add_argument("--duration-ms", type=int, default=45000)
    parser.add_argument("--genre", default="melodic EDM")
    parser.add_argument("--mood", default="bright uplifting")
    parser.add_argument("--bpm", type=int, default=128)
    parser.add_argument("--key", default="A minor")
    args = parser.parse_args()

    summary = render_sample_production_stages(
        output_dir=args.output_dir,
        prompt=args.prompt,
        duration_ms=args.duration_ms,
        genre=args.genre,
        mood=args.mood,
        bpm=args.bpm,
        key=args.key,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
