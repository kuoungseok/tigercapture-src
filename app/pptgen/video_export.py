"""MP4 export for timeline-native PPT presentations."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from app.pptgen.preview import DEFAULT_SIZE, render_slide_image
from app.pptgen.schema import DeckSpec, SlideSpec
from app.pptgen.timeline import PptTimeline, SlideClip


ProgressCallback = Callable[[dict[str, Any]], None]
CancelCallback = Callable[[], bool]
DEFAULT_TRANSITION_MS = 500
DEFAULT_AUDIO_BITRATE = "192k"


class PptVideoExportCancelled(RuntimeError):
    """Raised when a PPT MP4 export is cancelled cooperatively."""


def normalize_transition(value: Any) -> str:
    raw = str(value or "cut").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "cut",
        "none": "cut",
        "hard_cut": "cut",
        "dissolve": "fade",
        "crossfade": "fade",
        "cross_fade": "fade",
        "fade_through": "fade",
    }
    normalized = aliases.get(raw, raw)
    return normalized if normalized in {"cut", "fade"} else "cut"


def _ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
    except Exception as exc:  # pragma: no cover - depends on optional package
        raise RuntimeError("imageio_ffmpeg is required for PPT video export") from exc
    return str(get_ffmpeg_exe())


def _audio_path_from_deck(deck: DeckSpec) -> Path | None:
    for key in ("narration_audio_path", "audio_path", "soundtrack_path"):
        value = str(deck.metadata.get(key) or "").strip()
        if value:
            return Path(value)
    return None


def _validate_audio_path(path: str | Path | None) -> Path | None:
    if path is None or not str(path).strip():
        return None
    audio = Path(path)
    if not audio.is_file():
        raise RuntimeError(f"audio file not found: {audio}")
    if audio.stat().st_size <= 0:
        raise RuntimeError(f"audio file is empty: {audio}")
    return audio


def _normalize_size(size: tuple[int, int] = DEFAULT_SIZE) -> tuple[int, int]:
    width = max(16, int(size[0] or DEFAULT_SIZE[0]))
    height = max(16, int(size[1] or DEFAULT_SIZE[1]))
    if width % 2:
        width += 1
    if height % 2:
        height += 1
    return width, height


def frame_count_for_duration(duration_ms: int, fps: int) -> int:
    return max(1, int(round(max(1, int(duration_ms or 1)) * max(1, int(fps or 1)) / 1000.0)))


def transition_duration_ms(
    current_clip: SlideClip,
    next_clip: SlideClip | None,
    *,
    default_ms: int = DEFAULT_TRANSITION_MS,
) -> int:
    if next_clip is None or normalize_transition(getattr(current_clip, "transition_out", "cut")) == "cut":
        return 0
    current_duration = max(1, int(getattr(current_clip, "duration_ms", 1) or 1))
    next_duration = max(1, int(getattr(next_clip, "duration_ms", 1) or 1))
    return max(0, min(int(default_ms), current_duration // 2, next_duration // 2))


def _slide_by_id(deck: DeckSpec, slide_id: str) -> SlideSpec | None:
    return deck.slide_by_id(slide_id)


def build_ffmpeg_video_export_command(
    *,
    ffmpeg: str,
    output_path: str | Path,
    size: tuple[int, int],
    fps: int,
    audio_path: str | Path | None = None,
    audio_bitrate: str = DEFAULT_AUDIO_BITRATE,
) -> list[str]:
    width, height = _normalize_size(size)
    fps_value = max(1, min(120, int(fps or 30)))
    command = [
        str(ffmpeg),
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps_value),
        "-i",
        "-",
    ]
    audio = _validate_audio_path(audio_path)
    if audio is not None:
        command.extend(["-i", str(audio), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", str(audio_bitrate or DEFAULT_AUDIO_BITRATE), "-af", "apad", "-shortest"])
    else:
        command.append("-an")
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ]
    )
    return command


def _render_video_frame(
    deck: DeckSpec,
    slide: SlideSpec,
    *,
    size: tuple[int, int],
    local_ms: int,
    next_slide: SlideSpec | None = None,
    next_local_ms: int = 0,
    transition: str = "cut",
    transition_alpha: float = 0.0,
):
    current = render_slide_image(deck, slide, size=size, playhead_ms=local_ms)
    if next_slide is None or normalize_transition(transition) == "cut":
        return current
    alpha = max(0.0, min(1.0, float(transition_alpha)))
    if alpha <= 0.0:
        return current
    if alpha >= 1.0:
        return render_slide_image(deck, next_slide, size=size, playhead_ms=max(0, int(next_local_ms)))
    next_frame = render_slide_image(deck, next_slide, size=size, playhead_ms=max(0, int(next_local_ms)))
    return Image.blend(current.convert("RGB"), next_frame.convert("RGB"), alpha)


def export_deck_video(
    deck: DeckSpec,
    output_path: str | Path,
    *,
    fps: int = 30,
    size: tuple[int, int] = DEFAULT_SIZE,
    timeline: PptTimeline | None = None,
    ffmpeg_exe: str | None = None,
    audio_path: str | Path | None = None,
    audio_bitrate: str = DEFAULT_AUDIO_BITRATE,
    progress_cb: ProgressCallback | None = None,
    cancel_requested: CancelCallback | None = None,
) -> dict[str, Any]:
    if not deck.slides:
        raise RuntimeError("deck has no slides")
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    width, height = _normalize_size(size)
    fps_value = max(1, min(120, int(fps or 30)))
    timeline_model = timeline or PptTimeline.from_deck(deck)
    clips = [clip for clip in timeline_model.slide_clips if _slide_by_id(deck, clip.slide_id) is not None]
    if not clips:
        raise RuntimeError("deck timeline has no exportable slide clips")

    ffmpeg = str(ffmpeg_exe or _ffmpeg_exe())
    resolved_audio = _validate_audio_path(audio_path) or _validate_audio_path(_audio_path_from_deck(deck))
    command = build_ffmpeg_video_export_command(
        ffmpeg=ffmpeg,
        output_path=out,
        size=(width, height),
        fps=fps_value,
        audio_path=resolved_audio,
        audio_bitrate=audio_bitrate,
    )
    total_frames = sum(frame_count_for_duration(clip.duration_ms, fps_value) for clip in clips)
    transition_count = 0
    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    frames_written = 0
    try:
        assert proc.stdin is not None
        for clip_index, clip in enumerate(clips, start=1):
            slide = _slide_by_id(deck, clip.slide_id)
            if slide is None:
                continue
            next_clip = clips[clip_index] if clip_index < len(clips) else None
            next_slide = _slide_by_id(deck, next_clip.slide_id) if next_clip is not None else None
            transition = normalize_transition(getattr(clip, "transition_out", getattr(slide, "transition", "cut")))
            fade_ms = transition_duration_ms(clip, next_clip) if next_slide is not None else 0
            if fade_ms > 0:
                transition_count += 1
            transition_start_ms = max(0, int(clip.duration_ms) - fade_ms)
            clip_frames = frame_count_for_duration(clip.duration_ms, fps_value)
            for frame_index in range(clip_frames):
                if cancel_requested is not None and bool(cancel_requested()):
                    raise PptVideoExportCancelled("PPT video export cancelled")
                local_ms = int(round(frame_index * 1000.0 / fps_value))
                alpha = 0.0
                next_local_ms = 0
                if fade_ms > 0 and local_ms >= transition_start_ms:
                    alpha = min(1.0, max(0.0, (local_ms - transition_start_ms) / max(1, fade_ms)))
                    next_local_ms = int(round(alpha * fade_ms))
                frame = _render_video_frame(
                    deck,
                    slide,
                    size=(width, height),
                    local_ms=local_ms,
                    next_slide=next_slide,
                    next_local_ms=next_local_ms,
                    transition=transition,
                    transition_alpha=alpha,
                )
                proc.stdin.write(frame.tobytes("raw", "RGB"))
                frames_written += 1
                if progress_cb and (frames_written == 1 or frames_written == total_frames or frames_written % max(1, fps_value) == 0):
                    progress_cb(
                        {
                            "frames_written": frames_written,
                            "total_frames": total_frames,
                            "clip_index": clip_index,
                            "slide_id": slide.id,
                        }
                    )
        proc.stdin.close()
        proc.stdin = None
        stdout, stderr = proc.communicate()
    except Exception:
        if proc.stdin is not None:
            try:
                proc.stdin.close()
            except Exception:
                pass
        proc.kill()
        proc.wait(timeout=5)
        raise

    stderr_text = (stderr or b"").decode("utf-8", errors="replace")
    stdout_text = (stdout or b"").decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError((stderr_text or stdout_text or f"ffmpeg exited {proc.returncode}")[-2000:])
    return {
        "schema": "tigercapture.ppt.video_export.v1",
        "ok": bool(out.is_file() and out.stat().st_size > 0),
        "output_path": str(out),
        "slide_count": len(clips),
        "fps": fps_value,
        "size": [width, height],
        "frames_written": frames_written,
        "duration_ms": int(round(frames_written * 1000.0 / fps_value)),
        "transition_count": transition_count,
        "default_transition_ms": DEFAULT_TRANSITION_MS,
        "audio_path": str(resolved_audio) if resolved_audio is not None else "",
        "audio_muxed": resolved_audio is not None,
        "audio_bitrate": str(audio_bitrate or DEFAULT_AUDIO_BITRATE),
        "ffmpeg": ffmpeg,
    }


__all__ = [
    "DEFAULT_TRANSITION_MS",
    "DEFAULT_AUDIO_BITRATE",
    "build_ffmpeg_video_export_command",
    "export_deck_video",
    "frame_count_for_duration",
    "normalize_transition",
    "PptVideoExportCancelled",
    "transition_duration_ms",
]
