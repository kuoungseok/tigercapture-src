"""Create deterministic media for review/demo automation.

The generated files live under the review automation workspace by default.
They are inputs for screenshot/GIF/PPT/HTML review automation and are separate
from the ordinary QA corpus so product demos can evolve without breaking QA
fixtures.
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
from imageio_ffmpeg import get_ffmpeg_exe


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.review_automation.dev_gate import require_review_automation_dev
from app.review_automation.paths import (
    DEFAULT_REVIEW_SAMPLE_REPORT,
    DEFAULT_REVIEW_SAMPLE_ROOT,
    DEFAULT_REVIEW_VIDEO_SOURCE_DIR,
)


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1600:])


def _make_video(path: Path, lavfi: str, *, duration: float, fps: int, force: bool) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_exe()
    _run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            lavfi,
            "-t",
            f"{duration:.3f}",
            "-r",
            str(fps),
            "-pix_fmt",
            "yuv420p",
            str(path),
        ]
    )


def _discover_source_videos(source_dir: Path | None) -> list[Path]:
    if source_dir is None:
        return []
    try:
        if not source_dir.exists() or not source_dir.is_dir():
            return []
        videos = [
            path
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ]
    except Exception:
        return []
    return sorted(videos, key=lambda path: path.stat().st_mtime, reverse=True)


def _make_video_from_source(
    source: Path,
    path: Path,
    *,
    duration: float,
    fps: int,
    force: bool,
) -> bool:
    if path.exists() and not force:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = get_ffmpeg_exe()
    video_transform_args = [
        "-t",
        f"{duration:.3f}",
        "-vf",
        "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
        "-r",
        str(fps),
        "-pix_fmt",
        "yuv420p",
    ]
    audio_encode_args = [
        "-c:a",
        "aac",
        "-ac",
        "2",
        "-ar",
        "48000",
        "-shortest",
    ]
    try:
        _run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a:0",
                *video_transform_args,
                *audio_encode_args,
                str(path),
            ]
        )
    except Exception:
        # Imported clips can be video-only. Keep the real source frames, but
        # attach a quiet deterministic stream so audio extraction QA remains
        # reproducible.
        try:
            _run(
                [
                    ffmpeg,
                    "-y",
                    "-i",
                    str(source),
                    "-f",
                    "lavfi",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    *video_transform_args,
                    *audio_encode_args,
                    str(path),
                ]
            )
        except Exception:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass
            return False
    return path.exists()


def _make_video_from_first_available_source(
    sources: list[Path],
    path: Path,
    *,
    duration: float,
    fps: int,
    force: bool,
) -> Path | None:
    for source in sources:
        if _make_video_from_source(source, path, duration=duration, fps=fps, force=force):
            return source
    return None


def _remove_generated_sample(path: Path, *, sample_root: Path) -> None:
    try:
        resolved = path.resolve()
        media_root = (sample_root / "media").resolve()
        if media_root in resolved.parents or resolved == media_root:
            path.unlink(missing_ok=True)
    except Exception:
        pass


def _write_video_source_metadata(
    manifest_path: Path,
    *,
    sources: dict[str, Path],
    allow_synthetic_video: bool,
) -> None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return
    resources = payload.get("resources")
    if not isinstance(resources, list):
        return
    for item in resources:
        if not isinstance(item, dict):
            continue
        resource_id = str(item.get("id") or "")
        if resource_id not in {"overview_screen_demo", "screenstudio_cursor_demo"}:
            continue
        metadata = dict(item.get("metadata") or {})
        metadata["requires_youtube_import_source"] = not bool(allow_synthetic_video)
        if resource_id in sources:
            metadata["source_mode"] = "youtube_imports"
            metadata["source_path"] = str(sources[resource_id])
        elif allow_synthetic_video:
            metadata["source_mode"] = "synthetic_fallback"
            metadata["source_path"] = ""
        else:
            metadata["source_mode"] = "missing_youtube_imports"
            metadata["source_path"] = ""
        item["metadata"] = metadata
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_dialogue_audio(path: Path, *, duration: float = 7.0, sample_rate: int = 48000, force: bool = False) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sample_rate * duration), dtype=np.float32) / float(sample_rate)
    envelope = 0.45 + 0.35 * np.sin(2.0 * math.pi * 2.1 * t)
    voice = (
        0.35 * np.sin(2.0 * math.pi * 155.0 * t)
        + 0.14 * np.sin(2.0 * math.pi * 510.0 * t)
        + 0.07 * np.sin(2.0 * math.pi * 1850.0 * t)
    ) * envelope
    rng = np.random.default_rng(20260627)
    room = rng.normal(0.0, 0.018, size=t.shape).astype(np.float32)
    click = np.zeros_like(t)
    for center in (0.8, 3.2, 5.4):
        idx = int(center * sample_rate)
        click[idx : idx + 120] += np.linspace(0.18, 0.0, 120, dtype=np.float32)
    left = np.clip(voice + room + click, -0.96, 0.96)
    right = np.clip(voice * 0.9 + room * 0.7 - click * 0.35, -0.96, 0.96)
    pcm = np.column_stack([left, right])
    data = (pcm * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(data.tobytes())


def _make_poster(path: Path, *, force: bool = False) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return
    width, height = 1280, 720
    yy, xx = np.indices((height, width), dtype=np.float32)
    bg = np.zeros((height, width, 3), dtype=np.uint8)
    bg[..., 0] = np.clip(18 + xx / width * 36, 0, 255).astype(np.uint8)
    bg[..., 1] = np.clip(24 + yy / height * 46, 0, 255).astype(np.uint8)
    bg[..., 2] = np.clip(42 + (1.0 - xx / width) * 70, 0, 255).astype(np.uint8)
    image = Image.fromarray(bg, "RGB")
    draw = ImageDraw.Draw(image)
    from app.review_automation.fonts import load_pil_font

    title_font = load_pil_font(72, bold=True)
    body_font = load_pil_font(30)
    draw.rounded_rectangle((70, 70, 1210, 650), radius=34, outline=(125, 146, 255), width=4, fill=(10, 14, 28))
    draw.text((120, 130), "TigerCapture Review Demo", fill=(244, 247, 255), font=title_font)
    rows = [
        "Auto Polish evidence",
        "AI Script Edit fixtures",
        "Creator Assist media",
        "QA-backed screenshots and GIFs",
    ]
    for idx, row in enumerate(rows):
        y = 270 + idx * 68
        draw.rounded_rectangle((130, y, 520, y + 42), radius=14, fill=(45, 60, 110))
        draw.text((152, y + 6), row, fill=(238, 242, 255), font=body_font)
    image.save(path)


def _write_transcript(path: Path, *, force: bool = False) -> None:
    if path.exists() and not force:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """1
00:00:00,800 --> 00:00:02,700
오늘은 TigerCapture의 자동 줌과 커서 강조를 보여드릴게요.

2
00:00:03,000 --> 00:00:04,800
Um this part becomes a clean tutorial cut.

3
00:00:05,200 --> 00:00:07,000
이제 자막과 쇼츠 후보를 함께 만들 수 있습니다.

4
00:00:07,400 --> 00:00:09,200
The review page uses these assets as stable evidence.
""",
        encoding="utf-8",
    )


def _write_cursor_sidecar(video: Path, *, force: bool = False) -> Path:
    from app.screenstudio_sidecar_capture import write_cursor_sidecar

    sidecar = Path(str(video) + ".cursor.json")
    if sidecar.exists() and not force:
        return sidecar
    events = [
        {"t_ms": 250, "x_norm": 0.18, "y_norm": 0.62, "kind": "move", "hit_role": "timeline", "cursor_style": "pointer"},
        {"t_ms": 900, "x_norm": 0.32, "y_norm": 0.42, "kind": "click", "hit_role": "button", "hit_label": "Auto Polish"},
        {"t_ms": 1400, "x_norm": 0.48, "y_norm": 0.44, "kind": "release", "hit_role": "button", "hit_label": "Auto Polish"},
        {"t_ms": 2300, "x_norm": 0.54, "y_norm": 0.56, "kind": "drag", "hit_role": "viewer", "hit_label": "Zoom crop"},
        {"t_ms": 3300, "x_norm": 0.67, "y_norm": 0.46, "kind": "drag", "hit_role": "viewer", "hit_label": "Zoom crop"},
        {"t_ms": 3900, "x_norm": 0.67, "y_norm": 0.46, "kind": "release", "hit_role": "viewer", "hit_label": "Zoom crop"},
        {"t_ms": 5100, "x_norm": 0.44, "y_norm": 0.34, "kind": "hotkey", "label": "Ctrl K", "hit_role": "command_palette"},
        {"t_ms": 6200, "x_norm": 0.74, "y_norm": 0.66, "kind": "click", "hit_role": "export", "hit_label": "Export"},
    ]
    write_cursor_sidecar(
        video,
        events,
        out_path=sidecar,
        duration_ms=7200,
        frame_w=1280,
        frame_h=720,
        source="review_sample_generator",
    )
    return sidecar


def prepare_review_sample_resources(
    out_root: Path,
    *,
    force: bool = False,
    media: bool = True,
    video_source_dir: Path | None = DEFAULT_REVIEW_VIDEO_SOURCE_DIR,
    allow_synthetic_video: bool = False,
) -> dict[str, Any]:
    from app.review_automation.sample_resources import review_sample_resource_report, write_review_sample_manifest

    out_root.mkdir(parents=True, exist_ok=True)
    media_dir = out_root / "media"
    manifest_path = out_root / "manifest.json"
    write_review_sample_manifest(manifest_path, overwrite=bool(force or not manifest_path.exists()), sample_root=out_root)

    source_videos = _discover_source_videos(video_source_dir) if media else []
    used_sources: dict[str, Path] = {}

    if media:
        overview_video = media_dir / "overview_screen_demo.mp4"
        overview_source = _make_video_from_first_available_source(
            source_videos,
            overview_video,
            duration=6.0,
            fps=30,
            force=force,
        )
        if overview_source:
            used_sources["overview_screen_demo"] = overview_source
        elif allow_synthetic_video:
            _make_video(
                overview_video,
                "testsrc2=size=1280x720:rate=30:duration=6",
                duration=6.0,
                fps=30,
                force=force,
            )
        else:
            _remove_generated_sample(overview_video, sample_root=out_root)

        cursor_video = media_dir / "screenstudio_cursor_demo.mp4"
        cursor_candidates = [path for path in source_videos if path != overview_source] or source_videos
        cursor_source = _make_video_from_first_available_source(
            cursor_candidates,
            cursor_video,
            duration=7.2,
            fps=30,
            force=force,
        )
        if cursor_source:
            used_sources["screenstudio_cursor_demo"] = cursor_source
        elif allow_synthetic_video:
            _make_video(
                cursor_video,
                "testsrc=size=1280x720:rate=30:duration=7.2",
                duration=7.2,
                fps=30,
                force=force,
            )
        else:
            _remove_generated_sample(cursor_video, sample_root=out_root)
        if cursor_video.exists():
            _write_cursor_sidecar(cursor_video, force=force)
        _make_dialogue_audio(media_dir / "dialogue_cleanup_demo.wav", force=force)
        _write_transcript(media_dir / "ai_script_transcript_demo.srt", force=force)
        _make_poster(media_dir / "review_overview_poster.png", force=force)

    _write_video_source_metadata(
        manifest_path,
        sources=used_sources,
        allow_synthetic_video=allow_synthetic_video,
    )
    report = review_sample_resource_report(manifest_path, create_default_if_missing=False)
    report["video_source_dir"] = str(video_source_dir) if video_source_dir else ""
    if used_sources:
        report["video_source_mode"] = "youtube_imports"
    elif allow_synthetic_video:
        report["video_source_mode"] = "synthetic_fallback"
    else:
        report["video_source_mode"] = "missing_youtube_imports"
    report["video_source_files"] = {
        key: str(value)
        for key, value in used_sources.items()
    }
    if not allow_synthetic_video:
        required = {"overview_screen_demo", "screenstudio_cursor_demo"}
        missing = sorted(required - set(used_sources))
        report["missing_youtube_import_source_ids"] = missing
        report["ok"] = bool(report.get("ok")) and not missing
    return report


def main() -> int:
    try:
        require_review_automation_dev(ROOT)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description="Prepare TigerCapture review/demo sample resources.")
    parser.add_argument("--out-root", type=Path, default=DEFAULT_REVIEW_SAMPLE_ROOT)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REVIEW_SAMPLE_REPORT)
    parser.add_argument("--video-source-dir", type=Path, default=DEFAULT_REVIEW_VIDEO_SOURCE_DIR)
    parser.add_argument("--synthetic-video", action="store_true", help="Ignore imported videos and generate deterministic synthetic clips.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--manifest-only", action="store_true", help="Write manifest and folders without generating media.")
    args = parser.parse_args()

    report = prepare_review_sample_resources(
        args.out_root,
        force=bool(args.force),
        media=not bool(args.manifest_only),
        video_source_dir=None if args.synthetic_video else args.video_source_dir,
        allow_synthetic_video=bool(args.synthetic_video),
    )
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") or args.manifest_only else 1


if __name__ == "__main__":
    raise SystemExit(main())
