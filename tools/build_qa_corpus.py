"""Build a local TigerCapture QA corpus with real media-backed projects.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\build_qa_corpus.py

The generated corpus lives under ``qa_corpus/`` and contains five `.tgp`
projects that exercise timeline editing, filters/masks/tracking, nested
sequences, Live2D/Spine actors, and audio-heavy layouts.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FFMPEG = get_ffmpeg_exe()


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1200:])


def _make_video(path: Path, lavfi: str, *, duration: float = 5.0, fps: int = 30) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i", lavfi,
        "-t", f"{duration:.3f}", "-r", str(fps),
        "-pix_fmt", "yuv420p", str(path),
    ])


def _make_audio(path: Path, *, freq: int = 440, duration: float = 5.0) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i",
        f"sine=frequency={freq}:sample_rate=48000:duration={duration:.3f}",
        "-ac", "2", str(path),
    ])


def _make_dialogue_noise_audio(path: Path, *, duration: float = 6.0, sample_rate: int = 48000) -> None:
    """Create a deterministic speech-like noisy stereo sample for real audio QA."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sample_rate * duration), dtype=np.float32) / float(sample_rate)
    envelope = 0.55 + 0.35 * np.sin(2.0 * math.pi * 2.7 * t)
    voice = (
        0.38 * np.sin(2.0 * math.pi * 180.0 * t)
        + 0.16 * np.sin(2.0 * math.pi * 720.0 * t)
        + 0.08 * np.sin(2.0 * math.pi * 2100.0 * t)
    ) * envelope
    rng = np.random.default_rng(42)
    hiss = rng.normal(0.0, 0.025, size=t.shape).astype(np.float32)
    hum = 0.035 * np.sin(2.0 * math.pi * 60.0 * t)
    left = np.clip(voice + hiss + hum, -0.96, 0.96)
    right = np.clip(voice * 0.92 + hiss * 0.6 - hum * 0.35, -0.96, 0.96)
    pcm = np.column_stack([left, right])
    data = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())


def _copy_if_needed(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    if dst.exists() and dst.stat().st_size == src.stat().st_size:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _mask_dict() -> dict[str, Any]:
    from app.node_mask import BitmapMask

    arr = np.zeros((180, 320), dtype=np.uint8)
    arr[42:130, 82:212] = 255
    mask = BitmapMask(base_width=320, base_height=180, track_object=True, init_frame=0)
    mask.set_from_array(arr)
    mask._cache_track_bbox(0, (82.0, 42.0, 130.0, 88.0))
    mask._cache_track_bbox(10, (94.0, 48.0, 130.0, 88.0))
    return mask.to_dict()


def _clip(
    cid: int,
    source: Path,
    *,
    timeline_in_ms: int,
    source_in_ms: int = 0,
    source_out_ms: int = 5000,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": cid,
        "source_path": str(source.resolve()),
        "source_duration_ms": 5000,
        "timeline_in_ms": timeline_in_ms,
        "source_in_ms": source_in_ms,
        "source_out_ms": source_out_ms,
        "fades": [],
        "zoom_actors": [],
        "typography_actors": [],
        "speed_segments": [],
        "masks": [],
        "node_graph": None,
        "transition_out_type": "",
        "transition_out_ms": 500,
    }
    if extras:
        data.update(extras)
    return data


def _audio_clip(cid: int, source: Path, *, offset_ms: int = 0, duration_ms: int = 5000) -> dict[str, Any]:
    return {
        "id": cid,
        "source_path": str(source.resolve()),
        "duration_ms": duration_ms,
        "offset_ms": offset_ms,
        "trim_start_ms": 0,
        "trim_end_ms": duration_ms,
        "fade_in_ms": 120,
        "fade_out_ms": 120,
        "fades": [],
        "volume_points": [],
        "effects": {},
        "gain": 1.0,
    }


def _base_doc(name: str) -> dict[str, Any]:
    return {
        "version": "1.1",
        "app": "TigerCapture",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "px_per_sec": 70.0,
        "playhead_ms": 0,
        "global_in_ms": -1,
        "global_out_ms": -1,
        "project_settings": {
            "name": name,
            "canvas_width": 1280,
            "canvas_height": 720,
            "fps": 30.0,
            "ratio_label": "16:9",
        },
        "video_tracks": [],
        "audio_tracks": [],
        "subtitles": [],
        "media_pool": [],
        "strokes": [],
        "bubbles": [],
        "stickers": [],
        "timeline_markers": [],
        "lut": {"path": "", "strength": 1.0},
        "export": {
            "quality_id": "high",
            "format_id": "mp4",
            "audio_quality_id": "",
            "resolution": [1280, 720],
            "fps": 30.0,
        },
        "proxy": {"enabled": False, "dir": None},
        "spine_actor_tracks": [],
        "live2d_actor_tracks": [],
        "next_actor_id": 10,
        "next_live2d_id": 10,
    }


def _find_first(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path.resolve()
    return None


def build_corpus(out_dir: Path) -> dict[str, Any]:
    assets = out_dir / "assets"
    projects = out_dir / "projects"
    projects.mkdir(parents=True, exist_ok=True)

    v1 = assets / "qa_testsrc_720p.mp4"
    v2 = assets / "qa_motion_720p.mp4"
    v3 = assets / "qa_green_720p.mp4"
    v4 = assets / "qa_smpte_720p.mp4"
    a1 = assets / "qa_tone_440.wav"
    a2 = assets / "qa_tone_660.wav"
    _make_video(v1, "testsrc2=size=1280x720:rate=30:duration=5", duration=5)
    _make_video(v2, "testsrc=size=1280x720:rate=30:duration=5", duration=5)
    _make_video(v3, "color=c=green:size=1280x720:rate=30:duration=5", duration=5)
    _make_video(v4, "smptebars=size=1280x720:rate=30:duration=5", duration=5)
    _make_audio(a1, freq=440, duration=5)
    _make_audio(a2, freq=660, duration=5)

    spine_skel = _find_first([
        ROOT / "resources/spine_samples/nikke/bba001/bba001_00.skel",
        ROOT / "resources/spine_samples/celestial-circus/export/celestial-circus-pro.json",
    ])
    spine_atlas = _find_first([
        ROOT / "resources/spine_samples/nikke/bba001/bba001_00.atlas",
        ROOT / "resources/spine_samples/celestial-circus/export/celestial-circus-pma.atlas",
        ROOT / "resources/spine_samples/celestial-circus/export/celestial-circus.atlas",
    ])
    spine_tex = _find_first([
        ROOT / "resources/spine_samples/nikke/bba001/bba001.png",
        ROOT / "resources/spine_samples/celestial-circus/images/face.png",
    ])
    live2d_model = _find_first([
        ROOT / "resources/live2d_samples/HoshinoAi/Hoshino_Ai.model3.json",
        ROOT / "resources/live2d_samples/hiyori_free/hiyori_free_t08.model3.json",
        ROOT / "resources/live2d_samples/Senko_Normals/senko.model3.json",
    ])

    written: list[Path] = []

    doc = _base_doc("QA 01 Timeline Audio Basic")
    doc["video_tracks"] = [{
        "id": 1,
        "source_path": str(v1.resolve()),
        "display_name": "Basic video",
        "offset_ms": 0,
        "clips": [
            _clip(1, v1, timeline_in_ms=0, source_out_ms=2600),
            _clip(2, v2, timeline_in_ms=2700, source_out_ms=2300),
        ],
    }]
    doc["audio_tracks"] = [{"id": 1, "display_name": "Tone", "volume": 0.9, "clips": [_audio_clip(1, a1)]}]
    doc["media_pool"] = [str(v1.resolve()), str(v2.resolve()), str(a1.resolve())]
    written.append(_write_project(projects, "01_timeline_audio_basic.tgp", doc))

    doc = _base_doc("QA 02 Masks Filters Tracking")
    doc["video_tracks"] = [{
        "id": 1,
        "source_path": str(v3.resolve()),
        "display_name": "Masks and filters",
        "offset_ms": 0,
        "clips": [_clip(1, v3, timeline_in_ms=0, extras={
            "masks": [_mask_dict()],
            "video_filters": {
                "kind": "video_filters",
                "sharpen": 0.6,
                "vignette": 0.35,
                "vignette_feather": 0.7,
                "denoise": 0.0,
                "chroma_aberration": 0.1,
                "glitch": 0.0,
                "enabled": True,
            },
            "chroma_key": {
                "enabled": True,
                "key_hue": 60,
                "key_sat": 120,
                "key_val": 120,
                "hue_range": 35,
                "sat_min": 40,
                "val_min": 40,
                "spill_suppress": 0.2,
                "bg_r": 20,
                "bg_g": 20,
                "bg_b": 80,
            },
            "bg_removal": {
                "enabled": True,
                "method": "chroma_auto",
                "bg_mode": "blur",
                "bg_r": 0,
                "bg_g": 0,
                "bg_b": 0,
                "bg_blur_radius": 10,
                "feather": 3,
                "threshold": 0.5,
            },
            "stabilizer": {"enabled": True, "smoothing_radius": 3, "crop_ratio": 0.02},
        })],
    }]
    doc["media_pool"] = [str(v3.resolve())]
    written.append(_write_project(projects, "02_masks_filters_tracking.tgp", doc))

    doc = _base_doc("QA 03 Nested Multitrack")
    nested_parent = _clip(1, v1, timeline_in_ms=0, source_out_ms=5000, extras={
        "nested_sequence_id": 301,
        "nested_sequence_name": "Nested QA",
        "nested_child_tracks": [
            [_clip(11, v1, timeline_in_ms=0, source_out_ms=3000)],
            [_clip(12, v2, timeline_in_ms=900, source_out_ms=2600)],
        ],
        "nested_audio_tracks": [[_audio_clip(21, a2, offset_ms=400, duration_ms=4200)]],
    })
    doc["video_tracks"] = [{
        "id": 1,
        "source_path": str(v1.resolve()),
        "display_name": "Nested parent",
        "offset_ms": 0,
        "clips": [nested_parent],
    }]
    doc["media_pool"] = [str(v1.resolve()), str(v2.resolve()), str(a2.resolve())]
    written.append(_write_project(projects, "03_nested_multitrack.tgp", doc))

    doc = _base_doc("QA 04 Actors Live2D Spine")
    doc["video_tracks"] = [{
        "id": 1,
        "source_path": str(v4.resolve()),
        "display_name": "Actor bed",
        "offset_ms": 0,
        "clips": [_clip(1, v4, timeline_in_ms=0)],
    }]
    if spine_skel and spine_atlas:
        doc["spine_actor_tracks"] = [{
            "id": 1,
            "label": "Spine QA",
            "clips": [{
                "skel_path": str(spine_skel),
                "atlas_path": str(spine_atlas),
                "texture_path": str(spine_tex or ""),
                "anim_name": "idle",
                "skin_name": "default",
                "start_ms": 200,
                "duration_ms": 3200,
                "loop": True,
                "pos_x": 0.35,
                "pos_y": 0.55,
                "scale": 0.8,
            }],
        }]
    if live2d_model:
        doc["live2d_actor_tracks"] = [{
            "id": 2,
            "label": "Live2D QA",
            "clips": [{
                "model_path": str(live2d_model),
                "motion_group": "Idle",
                "motion_idx": 0,
                "start_ms": 600,
                "duration_ms": 3400,
                "loop": True,
                "pos_x": 0.68,
                "pos_y": 0.55,
                "scale": 0.55,
                "opacity": 1.0,
                "kf_pos_x": [],
                "kf_pos_y": [],
                "kf_scale": [],
                "kf_opacity": [],
                "blend_in_ms": 200,
                "blend_out_ms": 200,
                "blend_curve": "smoothstep",
            }],
            "blends": [],
        }]
    doc["media_pool"] = [str(v4.resolve())]
    written.append(_write_project(projects, "04_actors_live2d_spine.tgp", doc))

    doc = _base_doc("QA 05 Audio Heavy Mixed")
    doc["video_tracks"] = [{
        "id": 1,
        "source_path": str(v2.resolve()),
        "display_name": "Audio bed",
        "offset_ms": 0,
        "clips": [_clip(1, v2, timeline_in_ms=0)],
    }]
    doc["audio_tracks"] = [
        {"id": 1, "display_name": "Tone 440", "volume": 0.85, "clips": [_audio_clip(1, a1, offset_ms=0)]},
        {"id": 2, "display_name": "Tone 660", "volume": 0.55, "clips": [_audio_clip(2, a2, offset_ms=650)]},
    ]
    doc["subtitles"] = [{
        "start_ms": 500,
        "end_ms": 2500,
        "text": "QA audio-heavy project",
        "x": 0.5,
        "y": 0.82,
    }]
    doc["media_pool"] = [str(v2.resolve()), str(a1.resolve()), str(a2.resolve())]
    written.append(_write_project(projects, "05_audio_heavy_mixed.tgp", doc))

    doc = _base_doc("QA 06 Long Project Stress")
    doc["px_per_sec"] = 42.0
    doc["project_settings"].update({
        "name": "QA 06 Long Project Stress",
        "canvas_width": 1920,
        "canvas_height": 1080,
        "fps": 60.0,
        "ratio_label": "16:9",
        "qa_tags": ["long_project", "proxy", "relink", "nested", "undo_stress"],
    })
    doc["export"].update({"resolution": [1920, 1080], "fps": 60.0, "quality_id": "medium"})
    doc["proxy"] = {"enabled": True, "dir": str((out_dir / "proxy_cache").resolve())}
    video_sources = [v1, v2, v3, v4]
    audio_sources = [a1, a2]
    clip_id = 1
    video_tracks: list[dict[str, Any]] = []
    for track_idx in range(4):
        clips: list[dict[str, Any]] = []
        for idx in range(28):
            source = video_sources[(track_idx + idx) % len(video_sources)]
            start = idx * 12_000 + track_idx * 1_250
            extras: dict[str, Any] = {}
            if idx % 7 == 0:
                extras["transition_out_type"] = "crossfade"
                extras["transition_out_ms"] = 420
            if idx % 9 == 0:
                extras["speed_segments"] = [{
                    "id": clip_id * 10,
                    "start_ms": 700,
                    "end_ms": 2200,
                    "speed": 1.35,
                }]
            if idx in {5, 17} and track_idx == 1:
                extras.update({
                    "nested_sequence_id": 600 + idx,
                    "nested_sequence_name": f"Long Nested {idx}",
                    "nested_child_tracks": [
                        [_clip(10_000 + clip_id, v1, timeline_in_ms=0, source_out_ms=2600)],
                        [_clip(20_000 + clip_id, v2, timeline_in_ms=900, source_out_ms=3200)],
                    ],
                    "nested_audio_tracks": [[_audio_clip(30_000 + clip_id, a2, offset_ms=400, duration_ms=4200)]],
                })
            clips.append(_clip(
                clip_id,
                source,
                timeline_in_ms=start,
                source_in_ms=0,
                source_out_ms=4200,
                extras=extras,
            ))
            clip_id += 1
        video_tracks.append({
            "id": track_idx + 1,
            "source_path": str(video_sources[track_idx % len(video_sources)].resolve()),
            "display_name": f"Long V{track_idx + 1}",
            "offset_ms": 0,
            "clips": clips,
        })
    audio_tracks: list[dict[str, Any]] = []
    audio_id = 1
    for track_idx in range(4):
        clips = []
        for idx in range(34):
            source = audio_sources[(track_idx + idx) % len(audio_sources)]
            clips.append(_audio_clip(
                audio_id,
                source,
                offset_ms=idx * 9_500 + track_idx * 700,
                duration_ms=5000,
            ))
            clips[-1]["gain"] = round(0.65 + 0.07 * (track_idx % 3), 3)
            audio_id += 1
        audio_tracks.append({
            "id": track_idx + 1,
            "display_name": f"Long A{track_idx + 1}",
            "volume": round(0.72 - track_idx * 0.06, 3),
            "clips": clips,
        })
    doc["video_tracks"] = video_tracks
    doc["audio_tracks"] = audio_tracks
    doc["subtitles"] = [
        {"start_ms": 8_000, "end_ms": 13_000, "text": "Long project QA", "x": 0.5, "y": 0.86},
        {"start_ms": 180_000, "end_ms": 187_000, "text": "Nested/proxy/relink stress", "x": 0.5, "y": 0.80},
        {"start_ms": 318_000, "end_ms": 325_000, "text": "Autosave recovery checkpoint", "x": 0.5, "y": 0.84},
    ]
    doc["timeline_markers"] = [
        {"ms": 0, "label": "Start"},
        {"ms": 180_000, "label": "Mid QA"},
        {"ms": 330_000, "label": "Recovery Drill"},
    ]
    doc["media_pool"] = [str(p.resolve()) for p in [v1, v2, v3, v4, a1, a2]]
    written.append(_write_project(projects, "06_long_project_stress.tgp", doc))

    recovery_dir = projects / ".tigercapture_recovery"
    recovery_source = json.loads((projects / "01_timeline_audio_basic.tgp").read_text(encoding="utf-8"))
    recovery_source["saved_at"] = datetime.now(timezone.utc).isoformat()
    recovery_source.setdefault("project_settings", {})["name"] = "QA Recovery Autosave Fixture"
    recovery_path = _write_project(recovery_dir, "01_timeline_audio_basic~autosave.tgp", recovery_source)

    color_audio_samples = out_dir / "color_audio_samples"
    _copy_if_needed(v4, color_audio_samples / "rec709_smpte_scope_sample.mp4")
    _copy_if_needed(v2, color_audio_samples / "motion_waveform_sample.mp4")
    _copy_if_needed(a1, color_audio_samples / "tone_loudness_reference.wav")
    _make_dialogue_noise_audio(color_audio_samples / "dialogue_noise_cleanup_reference.wav")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assets_dir": str(assets.resolve()),
        "projects": [str(p.resolve()) for p in written],
        "recovery_candidates": [str(recovery_path.resolve())],
        "color_audio_samples": {
            "root": str(color_audio_samples.resolve()),
            "video": [
                str((color_audio_samples / "rec709_smpte_scope_sample.mp4").resolve()),
                str((color_audio_samples / "motion_waveform_sample.mp4").resolve()),
            ],
            "audio": [
                str((color_audio_samples / "tone_loudness_reference.wav").resolve()),
                str((color_audio_samples / "dialogue_noise_cleanup_reference.wav").resolve()),
            ],
        },
    }
    manifest_path = out_dir / "qa_corpus_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _write_project(projects: Path, name: str, doc: dict[str, Any]) -> Path:
    path = projects / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("qa_corpus"))
    args = parser.parse_args()
    manifest = build_corpus(args.out)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
