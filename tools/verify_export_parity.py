"""Synthetic export parity smoke tests.

Run from the repository root:

    .venv\\Scripts\\python.exe tools\\verify_export_parity.py

The script creates tiny temporary media and verifies paths that are easy to
regress: actor overlays, masked node graph, clip-level filters, chroma key,
background-removal pipeline, stabilizer export completion, audio separation
fallback, and tracked mask serialization.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import cv2
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image, ImageDraw
from PySide6.QtCore import QCoreApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.chroma_key import ChromaKeyParams
from app.color_grading import ColorGrade
from app.node_mask import BitmapMask
from app.audio_separation import SeparationCancelled, separate_audio_stems
from app.video_exporter import VideoExportThread
from app.video_filters import VideoFilterParams
from app.video_stabilizer import StabilizerParams


FFMPEG = get_ffmpeg_exe()


def _run(cmd: list[str], *, stdin: bytes | None = None) -> None:
    proc = subprocess.run(
        cmd,
        input=stdin,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace")[-1000:])


def _solid_video(path: Path, color: str, *, size: str = "64x64") -> None:
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i",
        f"color=c={color}:s={size}:d=1:r=5",
        "-pix_fmt", "yuv420p", str(path),
    ])


def _first_rgb(path: Path) -> np.ndarray:
    cap = cv2.VideoCapture(str(path))
    ok, bgr = cap.read()
    cap.release()
    if not ok or bgr is None:
        raise RuntimeError(f"Could not read output frame: {path}")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _export(source: Path, out: Path, *, segments=None, **kwargs) -> None:
    app = QCoreApplication.instance() or QCoreApplication([])
    _ = app
    errors: list[str] = []
    quality_id = kwargs.pop("quality_id", "high")
    format_id = kwargs.pop("format_id", "mp4")
    target_fps = kwargs.pop("target_fps", 5.0)
    thread = VideoExportThread(
        source,
        out,
        segments or [(0, 1000, 1.0)],
        quality_id=quality_id,
        format_id=format_id,
        target_fps=target_fps,
        **kwargs,
    )
    thread.finished_error.connect(lambda msg: errors.append(msg))
    thread.run()
    if errors:
        raise RuntimeError(errors[-1])
    if not out.exists() or out.stat().st_size <= 0:
        raise RuntimeError(f"Export did not write output: {out}")


def verify_masked_node(tmp: Path) -> None:
    source = tmp / "node_source.mp4"
    out = tmp / "node_out.mp4"
    _solid_video(source, "black")
    mask_arr = np.zeros((64, 64), dtype=np.uint8)
    mask_arr[4:28, 4:28] = 255
    mask = BitmapMask(base_width=64, base_height=64)
    mask.set_from_array(mask_arr)
    node = SimpleNamespace(
        NODE_KIND="serial",
        bypassed=False,
        blur_params=None,
        blur_invert_mask=True,
        effect_params=None,
        color_grade=ColorGrade(brightness=80),
    )
    _export(source, out, node_item_chain=[(node, [mask])])
    rgb = _first_rgb(out)
    inside = rgb[12, 12].tolist()
    outside = rgb[45, 45].tolist()
    assert min(inside) > 80 and max(outside) < 20, (inside, outside)


def verify_tracked_masked_node(tmp: Path) -> None:
    source = tmp / "tracked_node_source.mp4"
    out = tmp / "tracked_node_out.mp4"
    _solid_video(source, "black")
    mask_arr = np.zeros((64, 64), dtype=np.uint8)
    mask_arr[16:40, 20:44] = 255
    mask = BitmapMask(
        base_width=64,
        base_height=64,
        track_object=True,
        init_frame=0,
        softness_norm=0.0,
    )
    mask.set_from_array(mask_arr)
    assert mask.add_correction_from_mask(mask_arr, 0)
    node = SimpleNamespace(
        NODE_KIND="serial",
        bypassed=False,
        blur_params=None,
        blur_invert_mask=True,
        effect_params=None,
        color_grade=ColorGrade(brightness=90),
    )
    _export(source, out, node_item_chain=[(node, [mask])])
    rgb = _first_rgb(out)
    inside = rgb[24, 28].tolist()
    outside = rgb[4, 4].tolist()
    assert min(inside) > 90 and max(outside) < 20, (inside, outside)


def verify_actor_overlays(tmp: Path) -> None:
    source = tmp / "actor_source.mp4"
    live_mov = tmp / "live2d.mov"
    out = tmp / "actor_out.mp4"
    _solid_video(source, "black")

    frames = []
    for _ in range(5):
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle([4, 4, 27, 27], fill=(255, 0, 0, 255))
        frames.append(img.tobytes())
    proc = subprocess.Popen([
        FFMPEG, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgba", "-s", "64x64", "-r", "5", "-i", "pipe:0",
        "-vcodec", "prores_ks", "-profile:v", "4444",
        "-pix_fmt", "yuva444p10le", "-an", str(live_mov),
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert proc.stdin is not None
    for frame in frames:
        proc.stdin.write(frame)
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("Could not create Live2D overlay fixture")

    class FakeSpineClip:
        start_ms = 0
        end_ms = 1000
        duration_ms = 1000

        def get_renderer(self):
            return self

        def render_frame(self, w, h, frame_ms):
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(img).rectangle([36, 36, 59, 59], fill=(0, 255, 0, 255))
            return img

    class FakeSpineTrack:
        clips = [FakeSpineClip()]

    _export(
        source,
        out,
        spine_actor_tracks=[FakeSpineTrack()],
        live2d_pre_rendered=[(str(live_mov), 0.0, 1.0)],
    )
    rgb = _first_rgb(out)
    red = rgb[12, 12].tolist()
    green = rgb[46, 46].tolist()
    assert red[0] > 120 and red[1] < 100 and red[2] < 100, red
    assert green[1] > 120 and green[0] < 100 and green[2] < 100, green


def verify_chroma_key(tmp: Path) -> None:
    source = tmp / "green.mp4"
    out = tmp / "chroma_out.mp4"
    _solid_video(source, "green")
    effect = SimpleNamespace(
        video_filters=None,
        chroma_key=ChromaKeyParams(
            enabled=True, key_hue=60, hue_range=40,
            sat_min=40, val_min=40, spill_suppress=0.0,
            bg_r=255, bg_g=0, bg_b=0,
        ),
        bg_removal=None,
        stabilizer=None,
    )
    _export(source, out, clip_effects=[effect])
    pixel = _first_rgb(out)[32, 32].tolist()
    assert pixel[0] > 160 and pixel[1] < 80 and pixel[2] < 80, pixel


def verify_video_filter(tmp: Path) -> None:
    source = tmp / "white.mp4"
    out = tmp / "filter_out.mp4"
    _solid_video(source, "white")
    effect = SimpleNamespace(
        video_filters=VideoFilterParams(vignette=1.0, vignette_feather=0.5),
        chroma_key=None,
        bg_removal=None,
        stabilizer=None,
    )
    _export(source, out, clip_effects=[effect])
    rgb = _first_rgb(out)
    assert min(rgb[32, 32].tolist()) > 180
    assert max(rgb[0, 0].tolist()) < 80


class FakeBackgroundRemoval:
    def is_identity(self):
        return False

    def apply(self, rgb):
        out = np.zeros_like(rgb)
        out[..., 2] = 255
        return out


def verify_background_pipeline(tmp: Path) -> None:
    source = tmp / "bg_source.mp4"
    out = tmp / "bg_out.mp4"
    _solid_video(source, "white")
    effect = SimpleNamespace(
        video_filters=None,
        chroma_key=None,
        bg_removal=FakeBackgroundRemoval(),
        stabilizer=None,
    )
    _export(source, out, clip_effects=[effect])
    pixel = _first_rgb(out)[32, 32].tolist()
    assert pixel[2] > 180 and pixel[0] < 80 and pixel[1] < 80, pixel


def verify_stabilizer_smoke(tmp: Path) -> None:
    source = tmp / "stab_source.mp4"
    out = tmp / "stab_out.mp4"
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i",
        "testsrc2=size=96x64:rate=5:duration=1",
        "-pix_fmt", "yuv420p", str(source),
    ])
    effect = SimpleNamespace(
        video_filters=None,
        chroma_key=None,
        bg_removal=None,
        stabilizer=StabilizerParams(enabled=True, smoothing_radius=3, crop_ratio=0.02),
    )
    _export(source, out, clip_effects=[effect])


def verify_render_clip_transition(tmp: Path) -> None:
    red = tmp / "transition_red.mp4"
    blue = tmp / "transition_blue.mp4"
    out = tmp / "transition_out.mp4"
    _solid_video(red, "red")
    _solid_video(blue, "blue")

    class Clip:
        def __init__(self, source_path: Path, timeline_in_ms: int, timeline_out_ms: int) -> None:
            self.source_path = source_path
            self.source_in_ms = 0
            self.timeline_in_ms = int(timeline_in_ms)
            self.timeline_out_ms = int(timeline_out_ms)
            self.transition_out_type = ""
            self.transition_out_ms = 0
            self.fades = []
            self.is_nested_sequence = False
            self.typography_actors = []

        def contains_timeline_ms(self, ms: int) -> bool:
            return self.timeline_in_ms <= int(ms) < self.timeline_out_ms

    first = Clip(red, 0, 1000)
    first.transition_out_type = "dissolve"
    first.transition_out_ms = 500
    second = Clip(blue, 1000, 2000)

    _export(
        red,
        out,
        segments=[(0, 1000, 1.0)],
        render_clip_tracks=[[first, second]],
        target_fps=10.0,
    )
    rgb = _first_rgb(out)
    # The first frame should be red. Later transition frames are checked by
    # seeking into the output so the test proves the prerendered clip-track base
    # path is active, not just that the source encoded.
    cap = cv2.VideoCapture(str(out))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 7)
    ok, bgr = cap.read()
    cap.release()
    if not ok or bgr is None:
        raise AssertionError("could not read dissolve frame")
    blend = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    first_pixel = rgb[32, 32].tolist()
    blend_pixel = blend[32, 32].tolist()
    assert first_pixel[0] > 120 and first_pixel[2] < 100, first_pixel
    assert blend_pixel[0] > 40 and blend_pixel[2] > 40, blend_pixel


def verify_audio_separation_fallback(tmp: Path) -> None:
    source = tmp / "stereo_source.wav"
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i",
        "aevalsrc=sin(2*PI*440*t)|sin(2*PI*660*t):s=44100:d=0.5",
        "-ac", "2", str(source),
    ])
    result = separate_audio_stems(source, tmp, prefer_demucs=False)
    assert result.method == "FFmpeg mid/side", result.method
    assert result.vocals_path.exists() and result.vocals_path.stat().st_size > 0
    assert result.instrumental_path.exists() and result.instrumental_path.stat().st_size > 0


def verify_audio_separation_cancel(tmp: Path) -> None:
    source = tmp / "cancel_source.wav"
    _run([
        FFMPEG, "-y", "-f", "lavfi", "-i",
        "aevalsrc=sin(2*PI*220*t)|sin(2*PI*330*t):s=44100:d=1.0",
        "-ac", "2", str(source),
    ])
    try:
        separate_audio_stems(
            source,
            tmp,
            prefer_demucs=False,
            is_cancelled=lambda: True,
        )
    except SeparationCancelled:
        return
    raise AssertionError("separation did not honor cancellation")


def verify_tracking_roundtrip(tmp: Path) -> None:
    _ = tmp
    mask_arr = np.zeros((64, 64), dtype=np.uint8)
    mask_arr[16:40, 20:44] = 255
    mask = BitmapMask(base_width=64, base_height=64, track_object=True, init_frame=2)
    mask.set_from_array(mask_arr)
    mask.track_object = True
    assert mask.add_correction_from_mask(mask_arr, 2)
    mask._cache_track_bbox(5, (22.0, 18.0, 24.0, 24.0))
    mask._ensure_tracking_state()
    mask._failed_frames.add(9)
    mask.tracking_failed_frames.add(9)

    restored = BitmapMask.from_dict(mask.to_dict())
    status = restored.tracking_status()
    assert status["enabled"] is True
    assert status["corrections"] == 1, status
    assert status["cached_frames"] == 1, status
    assert status["failed_frames"] == 1, status
    assert "failures 1" in restored.tracking_status_text()


EXPORT_PARITY_CHECKS: tuple[Callable[[Path], None], ...] = (
    verify_masked_node,
    verify_tracked_masked_node,
    verify_actor_overlays,
    verify_chroma_key,
    verify_video_filter,
    verify_background_pipeline,
    verify_stabilizer_smoke,
    verify_render_clip_transition,
    verify_audio_separation_fallback,
    verify_audio_separation_cancel,
    verify_tracking_roundtrip,
)


def run_export_parity_smoke_report(
    *,
    report_path: Path | None = None,
    verbose: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="tc_export_parity_") as root:
        tmp = Path(root)
        for check in EXPORT_PARITY_CHECKS:
            started = datetime.now(timezone.utc)
            row = {
                "name": check.__name__,
                "ok": False,
                "error": "",
                "started_at": started.isoformat(),
            }
            try:
                check(tmp)
                row["ok"] = True
                if verbose:
                    print(f"ok {check.__name__}")
            except Exception as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                if verbose:
                    print(f"FAIL {check.__name__}: {row['error']}")
            rows.append(row)
    failures = [row for row in rows if not row.get("ok")]
    feature_map = {
        "masked_node_graph": "verify_masked_node",
        "tracked_mask_node_graph": "verify_tracked_masked_node",
        "spine_live2d_actor_overlays": "verify_actor_overlays",
        "chroma_key": "verify_chroma_key",
        "video_filters": "verify_video_filter",
        "background_removal": "verify_background_pipeline",
        "stabilizer": "verify_stabilizer_smoke",
        "transitions": "verify_render_clip_transition",
        "audio_separation": "verify_audio_separation_fallback",
        "audio_cancel": "verify_audio_separation_cancel",
        "tracking_serialization": "verify_tracking_roundtrip",
    }
    by_name = {str(row.get("name")): bool(row.get("ok")) for row in rows}
    payload = {
        "ok": not failures,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "kind": "export_parity_smoke",
        "summary": {
            "checks": len(rows),
            "passing": sum(1 for row in rows if row.get("ok")),
            "failing": len(failures),
        },
        "features": {
            feature: bool(by_name.get(check_name))
            for feature, check_name in feature_map.items()
        },
        "checks": rows,
        "failures": failures,
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        payload["report"] = str(report_path)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run synthetic export parity smoke tests.")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "debugCapture" / "export_parity_smoke_qa.json",
        help="Write JSON report here.",
    )
    args = parser.parse_args(argv)
    report = run_export_parity_smoke_report(report_path=args.out, verbose=True)
    print(json.dumps({
        "ok": report.get("ok"),
        "report": report.get("report"),
        "summary": report.get("summary"),
        "failures": report.get("failures"),
    }, ensure_ascii=False, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
