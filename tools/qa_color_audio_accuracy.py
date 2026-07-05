"""Color/Audio accuracy QA.

This is a deterministic reference suite for the professional Color/Audio layer,
with optional real media samples. It does not judge creative quality; it
verifies that scopes, color-management metadata, loudness math, and
dialogue-cleanup payloads keep producing stable numbers as the UI and exporter
evolve.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VIDEO_SAMPLE_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".png", ".jpg", ".jpeg"}
AUDIO_SAMPLE_SUFFIXES = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".mp4", ".mov", ".mkv", ".webm"}


def _check(name: str, ok: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), **details}


def _safe_name(path: Path) -> str:
    stem = path.stem or path.name or "sample"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem)[:80]


def _ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _is_no_audio_stream_error(message: str) -> bool:
    text = (message or "").casefold()
    return (
        "output file does not contain any stream" in text
        or "does not contain any stream" in text
        or "stream specifier" in text and "matches no streams" in text
        or "audio:0" in text and "matches no streams" in text
    )


def discover_color_audio_samples(root: Path | str, *, limit_per_kind: int = 24) -> dict[str, list[Path]]:
    """Discover real samples for scopes, LUT/OCIO, loudness, and cleanup QA."""
    source = Path(root)
    out = {"video": [], "audio": []}
    if not source.exists():
        return out
    files = [path for path in sorted(source.rglob("*")) if path.is_file()]
    for path in files:
        suffix = path.suffix.casefold()
        if suffix in VIDEO_SAMPLE_SUFFIXES and len(out["video"]) < int(limit_per_kind):
            out["video"].append(path)
        if suffix in AUDIO_SAMPLE_SUFFIXES and len(out["audio"]) < int(limit_per_kind):
            out["audio"].append(path)
    return out


def _mid_luma_ramp() -> np.ndarray:
    values = np.linspace(16, 239, 256, dtype=np.uint8)
    ramp = np.tile(values[None, :], (64, 1))
    return np.dstack([ramp, ramp, ramp]).copy()


def _clipped_reference() -> np.ndarray:
    frame = np.zeros((64, 128, 3), dtype=np.uint8)
    frame[:, 64:] = 255
    return frame


def _color_scope_checks() -> list[dict[str, Any]]:
    from app.color_scopes import render_scope, scope_quality_diagnostics

    ramp = _mid_luma_ramp()
    diag = scope_quality_diagnostics(ramp)
    checks = [
        _check(
            "scope.mid_luma_ramp",
            bool(diag["ok"])
            and 5.0 <= float(diag["luma_ire_p01"]) <= 8.0
            and 92.0 <= float(diag["luma_ire_p99"]) <= 95.0
            and float(diag["saturation_p95"]) <= 0.01,
            diagnostics=diag,
        )
    ]
    clipped = scope_quality_diagnostics(_clipped_reference())
    checks.append(_check(
        "scope.clipping_warnings",
        {
            "shadow clipping",
            "highlight clipping",
            "channel clipping",
        }.issubset(set(clipped.get("warnings") or [])),
        diagnostics=clipped,
    ))
    for kind in ("histogram", "parade", "waveform", "vectorscope"):
        scope = render_scope(kind, ramp, 160, 100)
        checks.append(_check(
            f"scope.render.{kind}",
            scope.shape == (100, 160, 3)
            and scope.dtype == np.uint8
            and int(np.unique(scope.reshape(-1, 3), axis=0).shape[0]) > 1,
            unique_colors=int(np.unique(scope.reshape(-1, 3), axis=0).shape[0]),
        ))
    return checks


def _color_management_checks() -> list[dict[str, Any]]:
    from app.color_management import (
        ColorManagementSettings,
        append_lut_filter_graph,
        compare_ffprobe_color_metadata,
        export_color_metadata,
        validate_color_management,
    )

    rec709 = ColorManagementSettings()
    hdr = ColorManagementSettings.from_dict({
        "output_space": "rec2020",
        "output_transfer": "pq",
        "hdr_mode": True,
    })
    aces = ColorManagementSettings.from_dict({"working_space": "acescg"})
    lut = ColorManagementSettings.from_dict({
        "creative_lut": {
            "path": "E:/looks/show.cube",
            "strength": 0.5,
            "enabled": True,
        }
    })
    graph, out_label = append_lut_filter_graph("", "v0", lut, output_prefix="qa_lut")
    hdr_meta = export_color_metadata(hdr)
    checks = [
        _check(
            "color.metadata.rec709",
            export_color_metadata(rec709) == {
                "colorspace": "bt709",
                "color_primaries": "bt709",
                "color_trc": "bt709",
                "pix_fmt": "yuv420p",
            },
        ),
        _check(
            "color.metadata.hdr_pq",
            hdr_meta.get("colorspace") == "bt2020nc"
            and hdr_meta.get("color_primaries") == "bt2020"
            and hdr_meta.get("color_trc") == "smpte2084"
            and hdr_meta.get("pix_fmt") == "yuv420p10le",
            metadata=hdr_meta,
        ),
        _check(
            "color.validation.aces_without_ocio_warns",
            "ACES working space is selected without an OCIO config path."
            in validate_color_management(aces).get("warnings", []),
            validation=validate_color_management(aces),
        ),
        _check(
            "color.lut.intensity_filter_graph",
            "lut3d=file='E\\:/looks/show.cube'" in graph
            and "blend=all_mode=normal:all_opacity=0.5000" in graph
            and out_label == "qa_lut0",
            graph=graph,
            out_label=out_label,
        ),
        _check(
            "color.ffprobe.metadata_compare",
            compare_ffprobe_color_metadata(
                {"color_management": hdr.to_dict()},
                {
                    "color_space": "bt2020nc",
                    "color_primaries": "bt2020",
                    "color_transfer": "smpte2084",
                },
            ).get("ok") is True,
        ),
    ]
    return checks


def _target_sine(target_lufs: float, *, sample_rate: int = 48000, seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(sample_rate * seconds), dtype=np.float32) / float(sample_rate)
    rms = 10.0 ** ((float(target_lufs) + 0.691) / 20.0)
    amp = min(0.99, rms * math.sqrt(2.0))
    mono = amp * np.sin(2.0 * math.pi * 1000.0 * t)
    return np.column_stack([mono, mono]).astype(np.float32)


def _audio_checks() -> list[dict[str, Any]]:
    from app.audio_accuracy import audio_signal_diagnostics, integrated_lufs_approx, stereo_correlation
    from app.audio_workflow import dialogue_cleanup_effects, loudness_target

    target = loudness_target("shortform")
    sine = _target_sine(target.integrated_lufs)
    diag = audio_signal_diagnostics(
        sine,
        target_lufs=target.integrated_lufs,
        true_peak_limit_db=target.true_peak_db,
    )
    inverse = sine.copy()
    inverse[:, 1] *= -1.0
    cleanup = dialogue_cleanup_effects(strength=1.4, de_reverb=-1.0)
    dc = cleanup.get("dialogue_cleanup", {})
    deesser = cleanup.get("deesser", {})
    loud = np.column_stack([
        np.sin(np.linspace(0.0, 100.0, 48000, dtype=np.float32)),
        np.sin(np.linspace(0.0, 100.0, 48000, dtype=np.float32)),
    ]).astype(np.float32)
    loud_diag = audio_signal_diagnostics(loud, target_lufs=-14.0, true_peak_limit_db=-1.0)
    return [
        _check(
            "audio.loudness.target_sine",
            diag["ok"] and abs(float(diag["integrated_lufs"]) - target.integrated_lufs) <= 0.2,
            diagnostics=diag,
        ),
        _check(
            "audio.loudness.true_peak_warning",
            "true peak exceeds limit" in loud_diag.get("warnings", []),
            diagnostics=loud_diag,
        ),
        _check(
            "audio.stereo.negative_correlation",
            stereo_correlation(inverse) < -0.99,
            correlation=stereo_correlation(inverse),
        ),
        _check(
            "audio.dialogue_cleanup.clamps",
            dc.get("strength") == 1.0
            and dc.get("de_reverb") == 0.0
            and dc.get("noise_reduction") == 22.0
            and deesser.get("reduction") == 65.0,
            payload=cleanup,
        ),
        _check(
            "audio.loudness.helper_matches_meter_formula",
            abs(integrated_lufs_approx(sine) - target.integrated_lufs) <= 0.2,
            lufs=integrated_lufs_approx(sine),
        ),
    ]


def _decode_pcm_wav(path: Path, *, max_seconds: float = 10.0) -> tuple[np.ndarray, int] | None:
    try:
        with wave.open(str(path), "rb") as wf:
            channels = max(1, int(wf.getnchannels()))
            sample_rate = int(wf.getframerate())
            sample_width = int(wf.getsampwidth())
            frames = min(int(wf.getnframes()), int(sample_rate * max_seconds))
            raw = wf.readframes(frames)
    except Exception:
        return None
    if not raw:
        return None
    if sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    elif sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        return None
    usable = (data.size // channels) * channels
    if usable <= 0:
        return None
    pcm = data[:usable].reshape(-1, channels)
    if channels == 1:
        pcm = np.column_stack([pcm[:, 0], pcm[:, 0]])
    elif channels > 2:
        pcm = pcm[:, :2]
    return pcm.astype(np.float32, copy=False), sample_rate


def _decode_audio_sample(path: Path, *, max_seconds: float = 10.0) -> tuple[np.ndarray, int]:
    wav_result = _decode_pcm_wav(path, max_seconds=max_seconds)
    if wav_result is not None:
        return wav_result
    sample_rate = 48000
    cmd = [
        _ffmpeg_exe(),
        "-v", "error",
        "-t", f"{max_seconds:.3f}",
        "-i", str(path),
        "-vn",
        "-ac", "2",
        "-ar", str(sample_rate),
        "-f", "f32le",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0 or not proc.stdout:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"ffmpeg audio decode failed with code {proc.returncode}")
    data = np.frombuffer(proc.stdout, dtype=np.float32)
    usable = (data.size // 2) * 2
    if usable <= 0:
        raise RuntimeError("decoded audio did not contain samples")
    return data[:usable].reshape(-1, 2), sample_rate


def _decode_video_frame(path: Path, *, width: int = 320, height: int = 180) -> np.ndarray:
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2"
    )
    cmd = [
        _ffmpeg_exe(),
        "-v", "error",
        "-i", str(path),
        "-frames:v", "1",
        "-vf", vf,
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    expected = width * height * 3
    if proc.returncode != 0 or len(proc.stdout) < expected:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(stderr or f"ffmpeg frame decode failed with code {proc.returncode}")
    return np.frombuffer(proc.stdout[:expected], dtype=np.uint8).reshape(height, width, 3).copy()


def _real_sample_checks(
    *,
    video_samples: list[Path] | None = None,
    audio_samples: list[Path] | None = None,
) -> list[dict[str, Any]]:
    from app.audio_accuracy import audio_signal_diagnostics
    from app.audio_workflow import loudness_target
    from app.color_scopes import render_scope, scope_quality_diagnostics

    checks: list[dict[str, Any]] = []
    target = loudness_target("shortform")
    for path in video_samples or []:
        name = f"real.video_scope.{_safe_name(path)}"
        try:
            frame = _decode_video_frame(path)
            diag = scope_quality_diagnostics(frame)
            scope = render_scope("waveform", frame, 160, 100)
            finite_diag = all(
                np.isfinite(float(diag[key]))
                for key in ("luma_ire_p01", "luma_ire_p50", "luma_ire_p99", "saturation_p95")
            )
            checks.append(_check(
                name,
                path.exists()
                and frame.shape == (180, 320, 3)
                and scope.shape == (100, 160, 3)
                and finite_diag,
                diagnostics=diag,
                frame_mean=float(frame.mean()),
                warnings=diag.get("warnings", []),
            ))
        except Exception as exc:
            checks.append(_check(name, False, error=str(exc), path=str(path)))
    for path in audio_samples or []:
        name = f"real.audio_diagnostics.{_safe_name(path)}"
        try:
            pcm, sample_rate = _decode_audio_sample(path)
            diag = audio_signal_diagnostics(
                pcm,
                target_lufs=target.integrated_lufs,
                true_peak_limit_db=target.true_peak_db,
            )
            finite_diag = all(
                np.isfinite(float(diag[key]))
                for key in ("integrated_lufs", "true_peak_dbfs", "stereo_correlation")
            )
            checks.append(_check(
                name,
                path.exists() and pcm.size > 0 and finite_diag,
                diagnostics=diag,
                sample_rate=sample_rate,
                seconds=float(pcm.shape[0]) / float(sample_rate or 1),
                warnings=diag.get("warnings", []),
            ))
        except Exception as exc:
            error = str(exc)
            if path.suffix.casefold() in VIDEO_SAMPLE_SUFFIXES and _is_no_audio_stream_error(error):
                checks.append(_check(
                    name,
                    True,
                    skipped=True,
                    reason="no_audio_stream",
                    path=str(path),
                ))
            else:
                checks.append(_check(name, False, error=error, path=str(path)))
    return checks


def build_report(
    *,
    video_samples: list[Path] | None = None,
    audio_samples: list[Path] | None = None,
) -> dict[str, Any]:
    video_samples = list(video_samples or [])
    audio_samples = list(audio_samples or [])
    sections = {
        "color_scopes": _color_scope_checks(),
        "color_management": _color_management_checks(),
        "audio": _audio_checks(),
    }
    real_samples = _real_sample_checks(
        video_samples=video_samples,
        audio_samples=audio_samples,
    )
    if real_samples:
        sections["real_samples"] = real_samples
    failures = [
        row
        for rows in sections.values()
        for row in rows
        if not row.get("ok")
    ]
    return {
        "ok": not failures,
        "summary": {
            "checks": sum(len(rows) for rows in sections.values()),
            "failures": len(failures),
            "sections": {name: {"checks": len(rows), "failures": sum(1 for row in rows if not row.get("ok"))}
                         for name, rows in sections.items()},
            "sample_sources": {
                "video": [str(path) for path in video_samples],
                "audio": [str(path) for path in audio_samples],
            },
        },
        "sections": sections,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Color/Audio accuracy QA.")
    parser.add_argument("--out", type=Path, default=Path("debugCapture/color_audio_accuracy_qa.json"))
    parser.add_argument(
        "--video-sample",
        type=Path,
        action="append",
        default=[],
        help="Optional real video/image sample to decode and run scope diagnostics on.",
    )
    parser.add_argument(
        "--audio-sample",
        type=Path,
        action="append",
        default=[],
        help="Optional real audio/video sample to decode and run loudness diagnostics on.",
    )
    parser.add_argument(
        "--sample-root",
        type=Path,
        default=None,
        help="Folder containing real color/audio QA samples. Defaults to qa_corpus/color_audio_samples when it exists.",
    )
    args = parser.parse_args(argv)
    video_samples = list(args.video_sample or [])
    audio_samples = list(args.audio_sample or [])
    sample_root = args.sample_root
    if sample_root is None:
        default_root = Path("qa_corpus/color_audio_samples")
        sample_root = default_root if default_root.exists() else None
    if sample_root is not None:
        discovered = discover_color_audio_samples(sample_root)
        video_samples.extend(path for path in discovered["video"] if path not in video_samples)
        audio_samples.extend(path for path in discovered["audio"] if path not in audio_samples)
    report = build_report(video_samples=video_samples, audio_samples=audio_samples)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report: {args.out}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
