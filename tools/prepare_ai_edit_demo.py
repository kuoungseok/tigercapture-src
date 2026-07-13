from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = Path(r"C:\Users\artmouse\Videos\TigerCapture\YouTube Imports")
OUT_DIR = ROOT / "external" / "assets" / "ai_edit_demo"
CLIP_DIR = OUT_DIR / "working_clips"
PROJECT_PATH = OUT_DIR / "TigerStudio_AI_Edit_Demo.tgp"


SEGMENTS = [
    {
        "keyword": "South Korea",
        "out": "01_seoul_sunset_bridge.mp4",
        "start": "00:00:45",
        "duration": 4.2,
        "role": "opening",
    },
    {
        "keyword": "Lamborghini",
        "out": "02_lamborghini_moody_detail.mp4",
        "start": "00:00:27",
        "duration": 3.6,
        "role": "car_detail",
    },
    {
        "keyword": "BUGATTI",
        "out": "03_bugatti_white_car.mp4",
        "start": "00:00:39",
        "duration": 3.2,
        "role": "luxury_insert",
    },
    {
        "keyword": "SAMSUNG",
        "out": "04_oled_color_macro.mp4",
        "start": "00:03:41",
        "duration": 3.2,
        "role": "color_fx",
    },
    {
        "keyword": "Tokyo",
        "out": "05_tokyo_night_city.mp4",
        "start": "00:02:13",
        "duration": 4.0,
        "role": "night_city",
    },
    {
        "keyword": "Le Mans",
        "out": "06_lemans_race_cut.mp4",
        "start": "00:38:29",
        "duration": 3.4,
        "role": "speed_rhythm",
    },
    {
        "keyword": "8k HDR",
        "out": "07_hdr_color_wheel.mp4",
        "start": "00:16:08",
        "duration": 3.0,
        "role": "hdr_insert",
    },
    {
        "keyword": "South Korea",
        "out": "08_seoul_bridge_close.mp4",
        "start": "00:02:07",
        "duration": 4.0,
        "role": "closing",
    },
]


def _ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _find_source(keyword: str) -> Path:
    key = keyword.casefold()
    for path in SOURCE_DIR.glob("*.mp4"):
        if key in path.name.casefold():
            return path
    raise FileNotFoundError(f"no source mp4 matching keyword: {keyword}")


def _probe_duration_ms(path: Path) -> int:
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        cap.release()
        if fps > 0.0 and frames > 0.0:
            return int(round(frames / fps * 1000.0))
    except Exception:
        pass
    return 0


def _render_clip(ffmpeg: str, source: Path, out: Path, start: str, duration: float) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 1024:
        return
    vf = (
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,"
        "fps=30,format=yuv420p"
    )
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        start,
        "-i",
        str(source),
        "-t",
        f"{float(duration):.3f}",
        "-vf",
        vf,
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)


def _clip_doc(idx: int, path: Path, timeline_in_ms: int, duration_ms: int, transition: str, transition_ms: int) -> dict:
    return {
        "id": idx,
        "source_path": str(path.resolve()),
        "source_duration_ms": duration_ms,
        "timeline_in_ms": timeline_in_ms,
        "source_in_ms": 0,
        "source_out_ms": duration_ms,
        "transition_out_type": transition,
        "transition_out_ms": transition_ms,
        "transition_preset_meta": {
            "id": f"ai-demo-{transition or 'cut'}",
            "name": transition.replace("_", " ").title() if transition else "Cut",
            "source": "ai_edit_demo",
        },
        "speed_segments": [
            {
                "start_ms": 0,
                "end_ms": min(duration_ms, 1200),
                "speed": 1.18 if idx % 2 else 0.88,
                "frame_blend": True,
                "blend_mode": "linear",
                "ease_in": 0.35,
                "ease_out": 0.45,
            }
        ],
        "zoom_actors": [
            {
                "id": idx,
                "start_ms": 120,
                "end_ms": max(600, duration_ms - 180),
                "target_x": 0,
                "target_y": 0,
                "target_w": 0,
                "target_h": 0,
                "zoom_in_ms": 420,
                "zoom_out_ms": 360,
                "easing": "smooth_pop",
                "motion_blur": 0.32,
            }
        ],
        "node_graph": {
            "color": {
                "grade": {
                    "brightness": 2,
                    "contrast": 18,
                    "saturation": 8,
                    "shadows_x": -18,
                    "shadows_y": -4,
                    "midtones_x": 4,
                    "midtones_y": 0,
                    "highlights_x": 18,
                    "highlights_y": 6,
                    "offset_x": 0,
                    "offset_y": 0,
                    "shadows_l": -4,
                    "midtones_l": 0,
                    "highlights_l": 5,
                    "offset_l": 0,
                    "hue_vs_hue": [],
                    "color_workflow": {},
                    "advanced_color_toolset": {},
                    "input_lut_path": "",
                    "input_lut_strength": 1.0,
                    "creative_lut_path": "",
                    "creative_lut_strength": 1.0,
                    "output_lut_path": "",
                    "output_lut_strength": 1.0,
                    "preset_id": "ai_demo_cinematic",
                }
            }
        },
    }


def _write_project(clips: list[dict], manifest_rows: list[dict]) -> None:
    timeline_ms = 0
    main_clips = []
    overlay_clips = []
    transitions = ["dissolve", "fade_white", "zoom_in", "wipe_left", "dissolve", "fade_black", ""]
    for idx, row in enumerate(manifest_rows, start=1):
        duration_ms = int(row["duration_ms"])
        transition = transitions[(idx - 1) % len(transitions)]
        clip = _clip_doc(idx, Path(row["path"]), timeline_ms, duration_ms, transition, 320 if transition else 0)
        if idx in {4, 7}:
            clip["timeline_in_ms"] = max(0, timeline_ms - 900)
            clip["connected_parent_track_id"] = 1
            clip["connected_offset_ms"] = -900
            overlay_clips.append(clip)
        else:
            main_clips.append(clip)
            timeline_ms += max(900, duration_ms - 260)

    doc = {
        "version": "1.1",
        "app": "TigerCapture",
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "px_per_sec": 58.0,
        "playhead_ms": 0,
        "global_in_ms": 0,
        "global_out_ms": max(1, timeline_ms),
        "project_settings": {
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "aspect": "16:9",
            "title": "Tiger Studio AI Edit Demo",
        },
        "video_tracks": [
            {
                "id": 1,
                "label": "AI Edit Main Cut",
                "track_type": "video",
                "program_output": True,
                "clips": main_clips,
                "preview_color_compare_mode": "split",
                "preview_compare_labels_enabled": True,
            },
            {
                "id": 2,
                "label": "AI FX Inserts",
                "track_type": "video",
                "program_output": True,
                "clips": overlay_clips,
                "pip_enabled": True,
                "pip_x": 0.76,
                "pip_y": 0.28,
                "pip_scale": 0.34,
                "pip_opacity": 0.94,
            },
        ],
        "audio_tracks": [],
        "subtitles": [
            {"start_ms": 900, "end_ms": 3300, "text": "AI builds the first cut", "style": {"preset_id": "shorts-bold"}},
            {"start_ms": 5200, "end_ms": 8200, "text": "Transitions, speed ramps, and color", "style": {"preset_id": "shorts-bold"}},
            {"start_ms": 11200, "end_ms": 14500, "text": "Editable timeline. Local-first workflow.", "style": {"preset_id": "shorts-bold"}},
        ],
        "media_pool": [str(Path(row["path"]).resolve()) for row in manifest_rows],
        "media_pool_metadata": [
            {
                "path": str(Path(row["path"]).resolve()),
                "kind": "video",
                "name": Path(row["path"]).name,
                "badge": row["role"],
                "source": str(Path(row["source"]).resolve()),
            }
            for row in manifest_rows
        ],
        "ai_edit_demo": {
            "schema": "tigerstudio.demo.ai_edit_multi_clip.v1",
            "prompt": (
                "Create a 45-second high-energy promo edit from these clips. "
                "Cut on rhythm, add short transitions, speed ramps, cinematic color, "
                "and punchy captions."
            ),
            "working_clip_count": len(manifest_rows),
            "capture_target": "Tiger Studio",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROJECT_PATH.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    ffmpeg = _ffmpeg_exe()
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for spec in SEGMENTS:
        source = _find_source(spec["keyword"])
        out = CLIP_DIR / spec["out"]
        _render_clip(ffmpeg, source, out, spec["start"], float(spec["duration"]))
        duration_ms = _probe_duration_ms(out) or int(round(float(spec["duration"]) * 1000))
        rows.append(
            {
                "keyword": spec["keyword"],
                "role": spec["role"],
                "source": str(source),
                "path": str(out),
                "start": spec["start"],
                "duration_ms": duration_ms,
            }
        )
    OUT_DIR.joinpath("manifest.json").write_text(json.dumps({"clips": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_project(rows, rows)
    print(json.dumps({"project": str(PROJECT_PATH), "manifest": str(OUT_DIR / "manifest.json"), "clips": rows}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
