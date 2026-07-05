"""Project-audio bus mixdown helpers for live broadcast output."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from app.audio_tracks import AudioTrack, build_audio_filter
from app.subprocess_utils import hidden_subprocess_kwargs


PROJECT_AUDIO_BUS_SCHEMA = "tigerstudio.broadcast.project_audio_bus_mixdown.v1"


@dataclass(frozen=True)
class ProjectAudioBusMixdownPlan:
    """A deterministic FFmpeg plan for rendering timeline audio to WAV."""

    output_path: str
    duration_ms: int
    audio_input_count: int
    command: list[str]
    silent: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PROJECT_AUDIO_BUS_SCHEMA,
            "output_path": self.output_path,
            "duration_ms": int(self.duration_ms),
            "audio_input_count": int(self.audio_input_count),
            "command": list(self.command),
            "silent": bool(self.silent),
        }


def project_audio_bus_extent_ms(tracks: Sequence[AudioTrack] | None) -> int:
    """Return the latest timeline point touched by loaded audio tracks."""
    extents: list[int] = []
    for track in tracks or []:
        try:
            if not bool(getattr(track, "is_loaded", False)):
                continue
            extent = getattr(track, "extent_ms", None)
            value = extent() if callable(extent) else 0
            extents.append(int(value or 0))
        except Exception:
            continue
    return max(extents, default=0)


def build_project_audio_bus_mixdown_plan(
    tracks: Sequence[AudioTrack] | None,
    output_path: str | Path,
    *,
    duration_ms: int | None = None,
    ffmpeg_exe: str = "ffmpeg",
    sample_rate: int = 48000,
    channels: int = 2,
) -> ProjectAudioBusMixdownPlan:
    """Build a WAV mixdown command using the editor export audio graph.

    This intentionally reuses :func:`app.audio_tracks.build_audio_filter`, so
    timeline clip trims, cuts, fades, gain, pan, automation, and clip effects
    match export as closely as possible.
    """
    track_list = list(tracks or [])
    resolved_duration = int(duration_ms or 0)
    if resolved_duration <= 0:
        resolved_duration = project_audio_bus_extent_ms(track_list)
    resolved_duration = max(1, resolved_duration)
    out_path = str(Path(output_path))
    sample_rate = max(8000, int(sample_rate or 48000))
    channels = max(1, min(8, int(channels or 2)))
    graph, audio_inputs, audio_count = build_audio_filter(track_list, 0, resolved_duration)
    if audio_count <= 0 or not graph:
        layout = "mono" if channels == 1 else "stereo"
        command = [
            str(ffmpeg_exe),
            "-y",
            "-f",
            "lavfi",
            "-t",
            _seconds_arg(resolved_duration),
            "-i",
            f"anullsrc=channel_layout={layout}:sample_rate={sample_rate}",
            "-vn",
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            out_path,
        ]
        return ProjectAudioBusMixdownPlan(
            output_path=out_path,
            duration_ms=resolved_duration,
            audio_input_count=0,
            command=command,
            silent=True,
        )
    command = [
        str(ffmpeg_exe),
        "-y",
        *audio_inputs,
        "-filter_complex",
        graph,
        "-map",
        "[outa]",
        "-vn",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        "-c:a",
        "pcm_s16le",
        out_path,
    ]
    return ProjectAudioBusMixdownPlan(
        output_path=out_path,
        duration_ms=resolved_duration,
        audio_input_count=audio_count,
        command=command,
        silent=False,
    )


def render_project_audio_bus_mixdown(
    tracks: Sequence[AudioTrack] | None,
    output_path: str | Path,
    *,
    duration_ms: int | None = None,
    ffmpeg_exe: str | None = None,
    sample_rate: int = 48000,
    channels: int = 2,
    runner: Callable[..., Any] | None = None,
    timeout_s: float | None = None,
) -> dict[str, Any]:
    """Render the project audio bus to a temporary WAV and return diagnostics."""
    if not ffmpeg_exe:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg_exe = str(get_ffmpeg_exe())
        except Exception:
            ffmpeg_exe = "ffmpeg"
    plan = build_project_audio_bus_mixdown_plan(
        tracks,
        output_path,
        duration_ms=duration_ms,
        ffmpeg_exe=str(ffmpeg_exe),
        sample_rate=sample_rate,
        channels=channels,
    )
    run = runner or subprocess.run
    try:
        result = run(
            plan.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return {
            **plan.to_dict(),
            "ok": False,
            "returncode": -1,
            "error": str(exc),
        }
    return {
        **plan.to_dict(),
        "ok": int(getattr(result, "returncode", 1)) == 0,
        "returncode": int(getattr(result, "returncode", 1)),
        "stderr_tail": _tail_text(getattr(result, "stderr", b"")),
    }


def with_ffmpeg_progress_args(command: Sequence[str]) -> list[str]:
    """Return an FFmpeg command that emits machine-readable progress lines."""
    parts = [str(item) for item in command]
    if not parts:
        return []
    return [parts[0], "-nostats", "-progress", "pipe:1", *parts[1:]]


def render_project_audio_bus_mixdown_progressive(
    tracks: Sequence[AudioTrack] | None,
    output_path: str | Path,
    *,
    duration_ms: int | None = None,
    ffmpeg_exe: str | None = None,
    sample_rate: int = 48000,
    channels: int = 2,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    cancel_requested: Callable[[], bool] | None = None,
    popen_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Render with FFmpeg `-progress` diagnostics and cooperative cancel."""
    if not ffmpeg_exe:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg_exe = str(get_ffmpeg_exe())
        except Exception:
            ffmpeg_exe = "ffmpeg"
    plan = build_project_audio_bus_mixdown_plan(
        tracks,
        output_path,
        duration_ms=duration_ms,
        ffmpeg_exe=str(ffmpeg_exe),
        sample_rate=sample_rate,
        channels=channels,
    )
    command = with_ffmpeg_progress_args(plan.command)
    popen = popen_factory or subprocess.Popen
    started_at = time.time()
    try:
        proc = popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **hidden_subprocess_kwargs(),
        )
    except Exception as exc:
        return {
            **plan.to_dict(),
            "command": command,
            "ok": False,
            "returncode": -1,
            "cancelled": False,
            "error": str(exc),
        }

    progress: dict[str, Any] = {
        "schema": "tigerstudio.broadcast.project_audio_bus_mixdown_progress.v1",
        "output_path": plan.output_path,
        "duration_ms": int(plan.duration_ms),
        "progress": 0.0,
        "out_time_ms": 0,
        "state": "running",
    }
    cancelled = False
    try:
        while True:
            if cancel_requested is not None and bool(cancel_requested()):
                cancelled = True
                progress["state"] = "cancelled"
                _terminate_process(proc)
                break
            stdout = getattr(proc, "stdout", None)
            line = stdout.readline() if stdout is not None else ""
            if line:
                update = _parse_progress_line(line, plan.duration_ms)
                if update:
                    progress.update(update)
                    if progress_callback is not None:
                        progress_callback(dict(progress))
                if progress.get("ffmpeg_progress") == "end":
                    break
                continue
            if hasattr(proc, "poll") and proc.poll() is not None:
                break
            time.sleep(0.05)
        try:
            returncode = int(proc.wait(timeout=1.0))
        except Exception:
            returncode = int(proc.poll() if hasattr(proc, "poll") and proc.poll() is not None else -1)
    finally:
        if cancelled:
            _terminate_process(proc)

    stderr_text = ""
    try:
        stderr = getattr(proc, "stderr", None)
        stderr_text = stderr.read() if stderr is not None else ""
    except Exception:
        stderr_text = ""
    final_progress = 1.0 if returncode == 0 and not cancelled else float(progress.get("progress") or 0.0)
    if progress_callback is not None:
        progress_callback(
            {
                **progress,
                "state": "cancelled" if cancelled else ("done" if returncode == 0 else "error"),
                "progress": final_progress,
                "returncode": int(returncode),
            }
        )
    return {
        **plan.to_dict(),
        "command": command,
        "ok": int(returncode) == 0 and not cancelled,
        "returncode": int(returncode),
        "cancelled": bool(cancelled),
        "progress": final_progress,
        "elapsed_seconds": max(0.0, time.time() - started_at),
        "stderr_tail": _tail_text(stderr_text),
    }


def _seconds_arg(duration_ms: int) -> str:
    return f"{max(0.001, int(duration_ms) / 1000.0):.3f}".rstrip("0").rstrip(".")


def _tail_text(value: bytes | str, limit: int = 1200) -> str:
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = str(value or "")
    return text[-limit:]


def _parse_progress_line(line: str, duration_ms: int) -> dict[str, Any]:
    text = str(line or "").strip()
    if not text or "=" not in text:
        return {}
    key, value = text.split("=", 1)
    if key == "out_time_ms":
        try:
            out_ms = max(0, int(int(value) / 1000))
        except Exception:
            return {}
        duration = max(1, int(duration_ms or 1))
        return {
            "out_time_ms": out_ms,
            "progress": max(0.0, min(1.0, out_ms / duration)),
            "state": "running",
        }
    if key == "progress":
        return {"ffmpeg_progress": value, "state": "done" if value == "end" else "running"}
    return {key: value}


def _terminate_process(proc: Any) -> None:
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        proc.wait(timeout=0.5)
        return
    except Exception:
        pass
    try:
        proc.kill()
    except Exception:
        pass
