from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
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


def compute_fade_filter_chain(
    segments: list[tuple[int, int, float]],
    fade_segments: list,
) -> str:
    """Build a chain of ``fade=t=out`` + ``fade=t=in`` filters for each
    FadeSegment, mapped from track-local time to output time via the segment
    list. Returns "" if there are no fades.

    Each fade segment becomes:
      - fade-out from output time of fade.start_ms, duration = half its length
      - fade-in from output time of midpoint, duration = the other half
    """
    if not fade_segments:
        return ""
    filters: list[str] = []
    for f in fade_segments:
        dur_ms = max(0, f.end_ms - f.start_ms)
        if dur_ms <= 0:
            continue
        kind = getattr(f, "kind", "both")
        t_start = _map_source_to_output(f.start_ms, segments)
        t_end = _map_source_to_output(f.end_ms, segments)
        if t_start < 0 or t_end < 0:
            continue
        if kind == "in":
            d = max(0.01, t_end - t_start)
            filters.append(f"fade=t=in:st={t_start:.3f}:d={d:.3f}")
        elif kind == "out":
            d = max(0.01, t_end - t_start)
            filters.append(f"fade=t=out:st={t_start:.3f}:d={d:.3f}")
        else:  # both
            mid_ms = f.start_ms + dur_ms // 2
            t_mid = _map_source_to_output(mid_ms, segments)
            if t_mid < 0:
                continue
            d_out = max(0.01, t_mid - t_start)
            d_in = max(0.01, t_end - t_mid)
            filters.append(f"fade=t=out:st={t_start:.3f}:d={d_out:.3f}")
            filters.append(f"fade=t=in:st={t_mid:.3f}:d={d_in:.3f}")
    return ",".join(filters)


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


def _overlay_enable_expr(t_start: float, t_end: float | None) -> str:
    if t_end is None or t_end <= t_start:
        return f"gte(t,{t_start:.3f})"
    return f"between(t,{t_start:.3f},{t_end:.3f})"


def build_filter_graph(
    segments: list[tuple[int, int, float]],
    subtitles: list | None = None,
    stroke_overlays: list[tuple[int, float, float | None]] | None = None,
    fade_segments: list | None = None,
) -> str:
    """Build an FFmpeg filter_complex graph (video-only).

    ``fade_segments`` is a list of ``FadeSegment``-like objects (anything
    with ``start_ms`` / ``end_ms``) placed on the track. Each becomes a
    fade-out then fade-in pair in the concatenated output stream.
    """
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

    parts.append(
        "".join(concat_labels)
        + f"concat=n={len(segments)}:v=1:a=0[cv0]"
    )

    current = "[cv0]"
    # Apply fade chain first (before overlays) so strokes / subtitles stay
    # visible even during fade-to-black.
    fade_chain = compute_fade_filter_chain(segments, fade_segments or [])
    if fade_chain:
        label = "[cvf]"
        parts.append(f"{current}{fade_chain}{label}")
        current = label

    if stroke_overlays:
        for i, (input_idx, t_start, t_end) in enumerate(stroke_overlays):
            label = f"[o{i}]"
            enable = _overlay_enable_expr(t_start, t_end)
            parts.append(
                f"{current}[{input_idx}:v]overlay=enable='{enable}'{label}"
            )
            current = label

    sub_chain = ""
    if subtitles:
        sub_chain = _subtitle_filters(subtitles, segments)

    if sub_chain:
        parts.append(f"{current}{sub_chain}[outv]")
    else:
        # Rename current label to [outv] via null filter
        parts.append(f"{current}null[outv]")

    return ";".join(parts)


class VideoExportThread(QThread):
    """Runs FFmpeg to render edited video (cuts + speed segments applied).

    Mixes any attached audio tracks into the output via per-track
    ``atrim + adelay + volume + afade`` filters joined with ``amix``.
    Falls back to video-only (``-an``) when no audio tracks are given.
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
        strokes: list | None = None,
        cuts: list | None = None,
        fade_segments: list | None = None,
        bubbles: list | None = None,
        audio_tracks: list | None = None,
    ) -> None:
        super().__init__()
        self._source = Path(source_path)
        self._out = Path(out_path)
        self._segments = list(segments)
        self._subtitles = list(subtitles) if subtitles else []
        self._strokes = list(strokes) if strokes else []
        self._cuts = list(cuts) if cuts else []
        self._fade_segments = list(fade_segments) if fade_segments else []
        self._bubbles = list(bubbles) if bubbles else []
        self._audio_tracks = list(audio_tracks) if audio_tracks else []
        self._temp_pngs: list[str] = []
        self._temp_output: str | None = None

    def _probe_source_dimensions(self) -> tuple[int, int]:
        """Return (width, height) of the source video. Falls back to
        (1920, 1080) if probing fails."""
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(str(self._source))
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            if w > 0 and h > 0:
                return w, h
        except Exception:
            pass
        return 1920, 1080

    def _prepare_stroke_overlays(
        self,
    ) -> tuple[list[str], list[tuple[int, float, float | None]]]:
        """Group strokes by (start_ms, end_ms), render each group to a
        transparent PNG at source resolution, and return (png_paths,
        overlay_spec) where overlay_spec entries index into the -i list
        starting at 1 (since the source video is -i 0). Also prepares one
        overlay per speech bubble (time-gated from its start_ms)."""
        if not self._strokes and not self._bubbles:
            return [], []
        from app.drawing import render_strokes_to_png

        src_w, src_h = self._probe_source_dimensions()
        width_scale = max(1.0, src_h / 720.0)

        groups: dict[tuple[int, int | None], list] = defaultdict(list)
        for stroke in self._strokes:
            groups[(stroke.start_ms, stroke.end_ms)].append(stroke)

        png_paths: list[str] = []
        overlay_spec: list[tuple[int, float, float | None]] = []
        input_idx = 1  # 0 is the source video
        total_out_s = sum((e - s) / sp for (s, e, sp) in self._segments) / 1000.0

        for (start_ms, end_ms), group_strokes in groups.items():
            t_start = _map_source_to_output(start_ms, self._segments)
            if t_start < 0:
                t_start = 0.0  # clamp strokes that would land in a cut
            if end_ms is None:
                t_end = None
            else:
                t_end_mapped = _map_source_to_output(end_ms, self._segments)
                t_end = t_end_mapped if t_end_mapped >= 0 else total_out_s
            fd, png_path = tempfile.mkstemp(suffix=".png", prefix="gifcam_stroke_")
            os.close(fd)
            ok = render_strokes_to_png(
                group_strokes, src_w, src_h, png_path, width_scale=width_scale
            )
            if not ok:
                try:
                    os.unlink(png_path)
                except OSError:
                    pass
                continue
            png_paths.append(png_path)
            overlay_spec.append((input_idx, t_start, t_end))
            input_idx += 1

        # Speech bubbles — one PNG overlay per bubble, time-gated from its
        # start_ms onward (no end; stays until end of video).
        if self._bubbles:
            from app.drawing import render_bubble_to_png
            for bubble in self._bubbles:
                t_start = _map_source_to_output(
                    int(bubble.start_ms), self._segments
                )
                if t_start < 0:
                    t_start = 0.0
                fd, png_path = tempfile.mkstemp(
                    suffix=".png", prefix="gifcam_bubble_"
                )
                os.close(fd)
                ok = render_bubble_to_png(bubble, src_w, src_h, png_path)
                if not ok:
                    try:
                        os.unlink(png_path)
                    except OSError:
                        pass
                    continue
                png_paths.append(png_path)
                overlay_spec.append((input_idx, t_start, None))
                input_idx += 1
        return png_paths, overlay_spec

    def run(self) -> None:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg = get_ffmpeg_exe()
            if not self._segments:
                raise RuntimeError("No segments to render.")

            self.stage.emit("Building filter graph")
            stroke_png_paths, stroke_overlays = self._prepare_stroke_overlays()
            self._temp_pngs = stroke_png_paths

            graph = build_filter_graph(
                self._segments,
                self._subtitles,
                stroke_overlays,
                fade_segments=self._fade_segments,
            )
            total_output_ms = int(
                sum((e - s) / sp for (s, e, sp) in self._segments) + 0.5
            )
            total_output_ms = max(1, total_output_ms)
            total_output_s = total_output_ms / 1000.0

            # Build audio mixing chain. Input indices for audio files
            # start AFTER the video source (-i 0) and every stroke/bubble
            # overlay PNG (-i 1 .. N).
            from app.audio_tracks import build_audio_filter
            video_input_count = 1 + len(stroke_png_paths)
            audio_graph, audio_inputs, audio_count = build_audio_filter(
                self._audio_tracks,
                video_input_count=video_input_count,
                project_duration_ms=total_output_ms,
            )
            if audio_graph:
                # Append audio portion to the filter_complex graph.
                graph = f"{graph};{audio_graph}"

            # Always write to a sibling temp file first, then atomically move
            # over the destination. Handles two real-world cases:
            #   1. Output == source (user overwriting the clip they're editing)
            #      — FFmpeg would otherwise read-and-write the same handle.
            #   2. Destination is locked (open in a player) — temp write
            #      succeeds; the final replace fails gracefully with a clear
            #      error instead of a corrupted FFmpeg run.
            fd, temp_path = tempfile.mkstemp(
                suffix=self._out.suffix or ".mp4",
                prefix=f"gifcam_export_{self._out.stem}_",
                dir=str(self._out.parent),
            )
            os.close(fd)
            self._temp_output = temp_path

            cmd = [ffmpeg, "-y", "-i", str(self._source)]
            for png in stroke_png_paths:
                cmd.extend(["-i", png])
            # Audio inputs come after video + overlay PNGs so that the
            # input indices in build_audio_filter line up correctly.
            cmd.extend(audio_inputs)
            cmd.extend([
                "-filter_complex", graph,
                "-map", "[outv]",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
            ])
            if audio_count > 0:
                cmd.extend([
                    "-map", "[outa]",
                    "-c:a", "aac",
                    "-b:a", "192k",
                ])
            else:
                cmd.append("-an")
            cmd.extend([
                "-t", f"{total_output_s:.3f}",
                "-progress", "pipe:2",
                "-nostats",
                temp_path,
            ])

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
            temp_out = Path(self._temp_output)
            if not temp_out.exists() or temp_out.stat().st_size == 0:
                raise RuntimeError("Output file not written.")

            # Atomic-replace onto the requested destination. Retry briefly in
            # case Windows still has the target handle open (media player, etc.).
            import time
            last_err: Exception | None = None
            for attempt in range(6):
                try:
                    os.replace(temp_out, self._out)
                    last_err = None
                    break
                except PermissionError as e:
                    last_err = e
                    time.sleep(0.3)
            if last_err is not None:
                raise RuntimeError(
                    f"Could not overwrite '{self._out.name}': "
                    f"another app may be holding the file open. ({last_err})"
                )
            self._temp_output = None  # moved, don't unlink in finally
            self.finished_success.emit(self._out, self._out.stat().st_size)
        except Exception as exc:  # noqa: BLE001
            self.finished_error.emit(str(exc))
        finally:
            for png in self._temp_pngs:
                try:
                    os.unlink(png)
                except OSError:
                    pass
            self._temp_pngs = []
            tp = getattr(self, "_temp_output", None)
            if tp:
                try:
                    os.unlink(tp)
                except OSError:
                    pass
            self._temp_output = None
