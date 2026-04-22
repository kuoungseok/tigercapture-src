from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal


def _format_seconds(ms: int) -> float:
    return round(ms / 1000.0, 3)


def build_segments(
    duration_ms: int,
    cuts: list,  # list[CutSegment]
    speed_segments: list,  # list[SpeedSegment]
) -> list[tuple[int, int, float]]:
    """Compute the output segment list from source track data.

    Returns a list of ``(start_ms, end_ms, speed)`` tuples in play-order,
    with cuts removed and speed segments applied. The resulting total
    output length (real time) = sum of (end-start)/speed for each piece.
    """
    if duration_ms <= 0:
        return []

    # 1. Start with the full range
    ranges: list[tuple[int, int, float]] = [(0, duration_ms, 1.0)]

    # 2. Remove cut regions
    for cut in cuts:
        new_ranges: list[tuple[int, int, float]] = []
        for s, e, sp in ranges:
            if e <= cut.start_ms or s >= cut.end_ms:
                new_ranges.append((s, e, sp))
                continue
            if s < cut.start_ms:
                new_ranges.append((s, cut.start_ms, sp))
            if e > cut.end_ms:
                new_ranges.append((cut.end_ms, e, sp))
        ranges = new_ranges

    # 3. Assign speed to matching pieces
    for seg in speed_segments:
        new_ranges = []
        for s, e, sp in ranges:
            if e <= seg.start_ms or s >= seg.end_ms:
                new_ranges.append((s, e, sp))
                continue
            if s < seg.start_ms:
                new_ranges.append((s, seg.start_ms, sp))
            ovl_s = max(s, seg.start_ms)
            ovl_e = min(e, seg.end_ms)
            new_ranges.append((ovl_s, ovl_e, seg.speed))
            if e > seg.end_ms:
                new_ranges.append((seg.end_ms, e, sp))
        ranges = new_ranges

    ranges = [(s, e, sp) for (s, e, sp) in ranges if e > s]
    ranges.sort(key=lambda r: r[0])
    return ranges


def _escape_drawtext(text: str) -> str:
    """Escape a string for FFmpeg drawtext filter 'text=' value."""
    return (
        text.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\\'")
        .replace("%", r"\\%")
    )


def _map_source_to_output(src_ms: int, segments: list[tuple[int, int, float]]) -> float:
    """Return output time (seconds) corresponding to a source time (ms),
    walking through segments. Returns -1 if source time falls in a cut or
    past the final segment."""
    acc_s = 0.0
    for s, e, sp in segments:
        dur_s = (e - s) / max(sp, 0.001) / 1000.0
        if src_ms < s:
            return -1.0  # in a cut region between previous seg and this one
        if s <= src_ms < e:
            return acc_s + (src_ms - s) / max(sp, 0.001) / 1000.0
        acc_s += dur_s
    return -1.0


def _subtitle_filters(
    subtitles: list,
    segments: list[tuple[int, int, float]],
) -> str:
    """Build chained drawtext filters for burn-in subtitles, mapping each
    subtitle's source time range into output time via the segment list.
    Each subtitle can opt out of the background box; in that case we draw
    a thick outline + drop shadow for readability instead."""
    parts = []
    for sub in subtitles:
        if not sub.text.strip():
            continue
        t_start = _map_source_to_output(sub.start_ms, segments)
        t_end = _map_source_to_output(sub.end_ms, segments)
        if t_start < 0 or t_end < 0 or t_end <= t_start:
            continue
        escaped = _escape_drawtext(sub.text).replace("\n", "\\n")
        common = (
            f"drawtext=text='{escaped}':"
            f"fontsize=36:fontcolor=white:"
            f"x=(w-text_w)/2:y=h-text_h-40:"
            f"enable='between(t,{t_start:.3f},{t_end:.3f})'"
        )
        if getattr(sub, "show_box", True):
            style = "box=1:boxcolor=black@0.6:boxborderw=10"
        else:
            style = (
                "bordercolor=black:borderw=3:"
                "shadowcolor=black@0.8:shadowx=2:shadowy=2"
            )
        parts.append(f"{common}:{style}")
    return ",".join(parts)


def build_filter_graph(
    segments: list[tuple[int, int, float]],
    subtitles: list | None = None,
) -> str:
    """Build an FFmpeg filter_complex graph (video-only) from segments,
    optionally burning in subtitles via chained drawtext filters."""
    if not segments:
        return ""
    parts: list[str] = []
    concat_labels: list[str] = []
    for i, (s_ms, e_ms, speed) in enumerate(segments):
        s = _format_seconds(s_ms)
        e = _format_seconds(e_ms)
        pts_factor = 1.0 / max(speed, 0.001)
        parts.append(
            f"[0:v]trim={s}:{e},setpts={pts_factor:.6f}*(PTS-STARTPTS)[v{i}]"
        )
        concat_labels.append(f"[v{i}]")

    sub_chain = ""
    if subtitles:
        sub_chain = _subtitle_filters(subtitles, segments)

    if sub_chain:
        concat = (
            "".join(concat_labels)
            + f"concat=n={len(segments)}:v=1:a=0[concat_v];"
            f"[concat_v]{sub_chain}[outv]"
        )
    else:
        concat = "".join(concat_labels) + f"concat=n={len(segments)}:v=1:a=0[outv]"
    parts.append(concat)
    return ";".join(parts)


class VideoExportThread(QThread):
    """Runs FFmpeg to render edited video (cuts + speed segments applied).

    Video-only for v1 (audio dropped). H.264 + yuv420p output.
    """

    progress = Signal(int, int)  # current_ms, total_ms
    stage = Signal(str)
    finished_success = Signal(Path, int)  # output path, size bytes
    finished_error = Signal(str)

    def __init__(
        self,
        source_path: Path,
        out_path: Path,
        segments: list[tuple[int, int, float]],
        subtitles: list | None = None,
    ) -> None:
        super().__init__()
        self._source = Path(source_path)
        self._out = Path(out_path)
        self._segments = list(segments)
        self._subtitles = list(subtitles) if subtitles else []

    def run(self) -> None:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg = get_ffmpeg_exe()
            if not self._segments:
                raise RuntimeError("No segments to render.")

            self.stage.emit("Building filter graph")
            graph = build_filter_graph(self._segments, self._subtitles)
            total_output_ms = int(
                sum((e - s) / sp for (s, e, sp) in self._segments) + 0.5
            )
            total_output_ms = max(1, total_output_ms)

            cmd = [
                ffmpeg,
                "-y",
                "-i", str(self._source),
                "-filter_complex", graph,
                "-map", "[outv]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-an",
                "-progress", "pipe:2",
                "-nostats",
                str(self._out),
            ]

            self.stage.emit("FFmpeg encoding")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
                creationflags=(
                    0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
                ),
            )

            last_ms = 0
            err_tail: list[str] = []
            assert proc.stderr is not None
            for line in proc.stderr:
                err_tail.append(line)
                if len(err_tail) > 40:
                    err_tail.pop(0)
                # FFmpeg -progress emits lines like "out_time_ms=1234567"
                m = re.match(r"out_time_ms=(\d+)", line.strip())
                if m:
                    cur = int(m.group(1)) // 1000
                    if cur != last_ms:
                        last_ms = cur
                        self.progress.emit(min(cur, total_output_ms), total_output_ms)
                if "progress=end" in line:
                    break

            rc = proc.wait()
            if rc != 0:
                raise RuntimeError(
                    f"FFmpeg exit {rc}: {''.join(err_tail).strip()[-400:]}"
                )
            if not self._out.exists() or self._out.stat().st_size == 0:
                raise RuntimeError("Output file not written.")

            self.finished_success.emit(self._out, self._out.stat().st_size)
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(str(exc))
