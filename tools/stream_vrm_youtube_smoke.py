"""Stream a cached internal-VRM Program Output frame to a live target.

This is a manual QA tool for private YouTube ingest checks. It reads the stream
key only from an environment variable and redacts it from every report.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.broadcast_output_session import BroadcastOutputSession  # noqa: E402
from app.vtuber.openseeface_motion import (  # noqa: E402
    load_openseeface_motion_csv,
    summarize_openseeface_motion,
)


DEFAULT_PREVIEW = ROOT / "debugCapture" / "internal_vrm_broadcast_preflight.png"
DEFAULT_STATUS = ROOT / "debugCapture" / "vrm_youtube_3min_status.jsonl"
DEFAULT_REPORT = ROOT / "debugCapture" / "vrm_youtube_3min_report.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream cached VRM Program Output to YouTube for QA.")
    parser.add_argument("--duration-s", type=int, default=180)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--preview", default=str(DEFAULT_PREVIEW))
    parser.add_argument("--status", default=str(DEFAULT_STATUS))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--video-bitrate-kbps", type=int, default=3600)
    parser.add_argument("--env-key", default="TC_YT_KEY_RAW")
    parser.add_argument("--motion-csv", default="", help="Optional OpenSeeFace CSV used to drive the VRM Program Output.")
    args = parser.parse_args(argv)

    stream_key = str(os.environ.get(args.env_key, "")).strip().lstrip("\\/").strip()
    os.environ.pop(args.env_key, None)

    status_path = Path(args.status)
    report_path = Path(args.report)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    def log(row: dict[str, object]) -> None:
        payload = {**row, "at": time.time()}
        with status_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    if not stream_key:
        log({"event": "error", "error": "missing_stream_key"})
        return 2

    width = max(1, int(args.width))
    height = max(1, int(args.height))
    fps = max(1, int(args.fps))
    duration_s = max(1, int(args.duration_s))
    frames_expected = int(duration_s * fps)

    preview_path = Path(args.preview)
    if not preview_path.is_file():
        log({"event": "error", "error": "missing_vrm_preview", "path": str(preview_path)})
        return 3

    sprite, sprite_bbox = _load_vrm_sprite(preview_path, width=width, height=height)
    bg = _make_stage_background(width, height)
    motion_frames = load_openseeface_motion_csv(args.motion_csv) if str(args.motion_csv or "").strip() else ()
    motion_summary = summarize_openseeface_motion(motion_frames)

    session = BroadcastOutputSession(
        {
            "target_id": "youtube_live",
            "stream_key": stream_key,
            "video_bitrate_kbps": int(args.video_bitrate_kbps),
            "audio_bitrate_kbps": 160,
            "max_retries": 0,
        },
        {"width": width, "height": height, "fps": fps},
    )
    started = session.start()
    log(
        {
            "event": "started",
            "state": started.get("state"),
            "preflight_ok": started.get("preflight_ok"),
            "warnings": started.get("warnings", []),
            "secret_leaked": stream_key in str(started),
            "sprite_bbox": sprite_bbox,
            "motion_csv": str(args.motion_csv or ""),
            "motion_frame_count": len(motion_frames),
            "motion_drives_vrm_pose": bool(motion_summary.get("drives_vrm_pose")),
        }
    )
    if started.get("state") != "running":
        log(
            {
                "event": "start_failed",
                "state": started.get("state"),
                "last_error": started.get("last_error"),
                "secret_leaked": stream_key in str(started),
            }
        )
        return 4

    last = started
    started_at = time.perf_counter()
    try:
        for frame_index in range(frames_expected):
            t = frame_index / fps
            frame = _compose_frame(
                bg,
                sprite,
                sprite_bbox=sprite_bbox,
                frame_index=frame_index,
                frames_expected=frames_expected,
                time_s=t,
                motion=_motion_for_time(motion_frames, t),
            )
            last = session.write_frame(frame)
            if last.get("state") != "running":
                log(
                    {
                        "event": "stream_state_changed",
                        "frame": frame_index,
                        "state": last.get("state"),
                        "last_error": last.get("last_error"),
                        "platform_error_kind": last.get("platform_error_kind"),
                        "secret_leaked": stream_key in str(last),
                    }
                )
                break
            if frame_index > 0 and frame_index % (fps * 30) == 0:
                log(_progress_row(last, elapsed_s=int(round(t)), stream_key=stream_key))
            delay = started_at + (frame_index + 1) / fps - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
    finally:
        time.sleep(1.0)
        before_stop = session.status()
        stopped = session.stop(timeout_s=6.0)

    report = {
        "schema": "tigercapture.broadcast.youtube_vrm_3min_smoke.v1",
        "ok": before_stop.get("state") == "running"
        and int(before_stop.get("frames_written") or 0) >= frames_expected - 10,
        "target": "youtube_live",
        "visibility": "private",
                "program_output": "internal_vrm_fallback_milica",
                "mapping_source": "trump_openseeface_motion_csv" if motion_frames else "idle_internal_motion",
                "motion_csv": str(args.motion_csv or ""),
                "motion": motion_summary,
                "avatar_source": "external/assets/vtuber/booth_milica/Milica1.3free/Milica_v1.3.vrm",
        "duration_s": duration_s,
        "frames_expected": frames_expected,
        "frames_written": int(before_stop.get("frames_written") or 0),
        "estimated_fps": float(before_stop.get("estimated_fps") or 0.0),
        "backpressure_count": int(before_stop.get("backpressure_count") or 0),
        "write_error_count": int(before_stop.get("write_error_count") or 0),
        "last_exit_code": before_stop.get("last_exit_code"),
        "platform_error_kind": before_stop.get("platform_error_kind"),
        "recovery_action": before_stop.get("recovery_action"),
        "secret_redacted": not (stream_key in str(before_stop) or stream_key in str(stopped)),
        "stopped_state": stopped.get("state"),
        "notes": (
            "3-minute private YouTube ingest using internal VRM fallback Program Output. "
            "Stream key, account, chat, and URL are omitted."
        ),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log({"event": "finished", **report})
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "frames_written": report["frames_written"],
                "estimated_fps": report["estimated_fps"],
                "backpressure_count": report["backpressure_count"],
                "write_error_count": report["write_error_count"],
                "secret_redacted": report["secret_redacted"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if bool(report["ok"]) else 5


def _load_vrm_sprite(path: Path, *, width: int, height: int) -> tuple[dict[str, np.ndarray], list[int]]:
    img = Image.open(path).convert("RGBA")
    if img.size != (width, height):
        img = img.resize((width, height), Image.Resampling.LANCZOS)
    rgba = np.asarray(img).copy()
    red = rgba[..., 0].astype(np.int16)
    green = rgba[..., 1].astype(np.int16)
    blue = rgba[..., 2].astype(np.int16)
    key_mask = (green > 210) & (red < 80) & (blue < 80)
    rgba[..., 3] = np.where(key_mask, 0, rgba[..., 3])
    alpha = rgba[..., 3]
    ys, xs = np.where(alpha > 8)
    if xs.size == 0:
        raise ValueError("VRM sprite is empty after chroma key")
    x0, x1 = max(0, int(xs.min()) - 4), min(width, int(xs.max()) + 5)
    y0, y1 = max(0, int(ys.min()) - 4), min(height, int(ys.max()) + 5)
    crop = rgba[y0:y1, x0:x1, :].copy()
    return (
        {
            "rgb": crop[..., :3].astype(np.float32),
            "alpha": crop[..., 3:4].astype(np.float32) / 255.0,
            "width": np.asarray([crop.shape[1]], dtype=np.int32),
            "height": np.asarray([crop.shape[0]], dtype=np.int32),
        },
        [x0, y0, x1, y1],
    )


def _make_stage_background(width: int, height: int) -> np.ndarray:
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    bg = np.zeros((height, width, 3), dtype=np.float32)
    bg[..., 0] = 18 + 22 * (1 - y) + 10 * x
    bg[..., 1] = 22 + 26 * (1 - y)
    bg[..., 2] = 34 + 42 * (1 - y) + 16 * (1 - x)
    for gx in range(0, width, 80):
        bg[:, gx : gx + 1, :] += 12
    for gy in range(0, height, 80):
        bg[gy : gy + 1, :, :] += 8
    bg[int(height * 0.78) :, :, :] *= 0.52
    cx = width * 0.56
    cy = height * 0.88
    grid_x = np.arange(width)[None, :]
    grid_y = np.arange(height)[:, None]
    ellipse = ((grid_x - cx) / 310.0) ** 2 + ((grid_y - cy) / 42.0) ** 2
    shadow = np.clip(1.0 - ellipse, 0, 1)[..., None]
    bg = bg * (1.0 - 0.36 * shadow)
    return np.clip(bg, 0, 255).astype(np.uint8)


def _compose_frame(
    bg: np.ndarray,
    sprite: dict[str, np.ndarray],
    *,
    sprite_bbox: list[int],
    frame_index: int,
    frames_expected: int,
    time_s: float,
    motion: object | None = None,
) -> np.ndarray:
    frame = bg.copy()
    height, width = frame.shape[:2]
    pulse = int((math.sin(time_s * 4.0) * 0.5 + 0.5) * 70)
    frame[28:70, 28:340, :] = [18, 22, 32]
    frame[34:64, 36:66, :] = [230, 30 + pulse, 42]
    frame[34:64, 80:316, :] = [36, 48, 62]
    frame[40:58, 88 : 88 + int((math.sin(time_s * 1.8) * 0.5 + 0.5) * 210), :] = [88, 220, 180]
    progress = int((frame_index + 1) / max(1, frames_expected) * (width - 80))
    frame[height - 42 : height - 20, 36 : width - 36, :] = np.maximum(
        frame[height - 42 : height - 20, 36 : width - 36, :], [24, 34, 44]
    )
    frame[height - 38 : height - 24, 40 : 40 + progress, :] = [70, 220, 150]

    yaw = float(getattr(motion, "yaw_deg", 0.0) or 0.0)
    pitch = float(getattr(motion, "pitch_deg", 0.0) or 0.0)
    roll = float(getattr(motion, "roll_deg", 0.0) or 0.0)
    mouth = max(0.0, min(1.0, float(getattr(motion, "mouth_open", 0.0) or 0.0)))
    blink = max(
        0.0,
        min(
            1.0,
            float(max(float(getattr(motion, "blink_l", 0.0) or 0.0), float(getattr(motion, "blink_r", 0.0) or 0.0))),
        ),
    )
    chin = max(-1.0, min(1.0, float(getattr(motion, "chin_offset_x_norm", 0.0) or 0.0)))

    x0, y0, _, _ = sprite_bbox
    sw = int(sprite["width"][0])
    sh = int(sprite["height"][0])
    px = x0 + int(yaw * 1.6 + roll * 0.7 + chin * 36.0)
    py = y0 + int(-pitch * 1.25 + math.sin(time_s * 1.5) * 2)
    sx0 = max(0, -px)
    sy0 = max(0, -py)
    tx0 = max(0, px)
    ty0 = max(0, py)
    w = min(sw - sx0, width - tx0)
    h = min(sh - sy0, height - ty0)
    if w > 0 and h > 0:
        src_rgb = sprite["rgb"][sy0 : sy0 + h, sx0 : sx0 + w, :]
        src_alpha = sprite["alpha"][sy0 : sy0 + h, sx0 : sx0 + w, :]
        dst = frame[ty0 : ty0 + h, tx0 : tx0 + w, :].astype(np.float32)
        frame[ty0 : ty0 + h, tx0 : tx0 + w, :] = np.clip(
            src_rgb * src_alpha + dst * (1.0 - src_alpha), 0, 255
        ).astype(np.uint8)
        # This stream smoke path is plumbing-only. Do not draw fake eye/mouth
        # overlays on top of the cached VRM sprite; expression quality is judged
        # with the local VRM render preflight.

    marker_x = 40 + int(((time_s * 120) % max(1, width - 120)))
    frame[92:106, marker_x : marker_x + 64, :] = [245, 245, 245]
    _draw_motion_meter(frame, yaw=yaw, pitch=pitch, mouth=mouth, blink=blink, chin=chin)
    return frame


def _motion_for_time(frames: tuple[object, ...], time_s: float) -> object | None:
    if not frames:
        return None
    max_time = max(1, int(getattr(frames[-1], "time_ms", 0) or 0))
    target = int(round((float(time_s) * 1000.0) % max_time))
    return min(frames, key=lambda frame: abs(int(getattr(frame, "time_ms", 0) or 0) - target))


def _draw_motion_meter(frame: np.ndarray, *, yaw: float, pitch: float, mouth: float, blink: float, chin: float) -> None:
    height, width = frame.shape[:2]
    base_x = width - 328
    base_y = 28
    frame[base_y : base_y + 112, base_x : base_x + 292, :] = [18, 22, 32]
    rows = (
        (0, yaw, -45.0, 45.0, [80, 190, 255]),
        (1, pitch, -35.0, 35.0, [255, 210, 90]),
        (2, mouth, 0.0, 1.0, [240, 80, 110]),
        (3, blink, 0.0, 1.0, [170, 130, 255]),
        (4, chin, -1.0, 1.0, [100, 230, 160]),
    )
    for row, value, lo, hi, color in rows:
        y = base_y + 12 + row * 19
        x0 = base_x + 52
        x1 = base_x + 260
        frame[y : y + 8, x0:x1, :] = [42, 52, 66]
        norm = max(0.0, min(1.0, (float(value) - lo) / max(1e-6, hi - lo)))
        center = x0 + int((x1 - x0) * 0.5)
        pos = x0 + int((x1 - x0) * norm)
        if pos >= center:
            frame[y : y + 8, center:pos, :] = color
        else:
            frame[y : y + 8, pos:center, :] = color


def _progress_row(status: dict[str, object], *, elapsed_s: int, stream_key: str) -> dict[str, object]:
    return {
        "event": "progress",
        "elapsed_s": elapsed_s,
        "frames_written": int(status.get("frames_written") or 0),
        "estimated_fps": float(status.get("estimated_fps") or 0.0),
        "backpressure_count": int(status.get("backpressure_count") or 0),
        "write_error_count": int(status.get("write_error_count") or 0),
        "secret_leaked": stream_key in str(status),
    }


if __name__ == "__main__":
    raise SystemExit(main())
