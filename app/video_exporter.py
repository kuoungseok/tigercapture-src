from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
#  Export quality presets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityPreset:
    """One row in the export-quality dropdown.

    Holds codec-agnostic quality knobs. The actual ffmpeg args depend
    on which :class:`ExportFormat` is paired with it — a single preset
    can map to libx264 (``crf``/``ffmpeg_preset``) or libvpx-vp9
    (``crf_vp9``)."""

    id: str
    name_key: str            # i18n key for the visible label
    desc_key: str            # i18n key for the secondary description
    crf: int                 # libx264 CRF (lower = higher quality)
    crf_vp9: int             # libvpx-vp9 CRF (different scale 0..63)
    ffmpeg_preset: str       # libx264 -preset value
    feature_id: str          # tier-gating key (see app.tier)


# VP9 CRF chart (mapped so VP9 visual quality ~ libx264 of the same row):
# low=35, standard=30, high=28, best=24. VP9's CRF range is 0..63 with
# lower meaning higher quality.
QUALITY_PRESETS: list[QualityPreset] = [
    QualityPreset(
        id="low",
        name_key="export.quality.low",
        desc_key="export.quality.low.desc",
        crf=28, crf_vp9=35, ffmpeg_preset="veryfast",
        feature_id="export.quality.low",
    ),
    QualityPreset(
        id="standard",
        name_key="export.quality.standard",
        desc_key="export.quality.standard.desc",
        crf=23, crf_vp9=30, ffmpeg_preset="fast",
        feature_id="export.quality.standard",
    ),
    QualityPreset(
        id="high",
        name_key="export.quality.high",
        desc_key="export.quality.high.desc",
        crf=20, crf_vp9=28, ffmpeg_preset="medium",
        feature_id="export.quality.high",
    ),
    QualityPreset(
        id="best",
        name_key="export.quality.best",
        desc_key="export.quality.best.desc",
        crf=17, crf_vp9=24, ffmpeg_preset="slow",
        feature_id="export.quality.best",
    ),
]


DEFAULT_QUALITY_ID = "high"


def get_quality_preset(quality_id: str) -> QualityPreset:
    for q in QUALITY_PRESETS:
        if q.id == quality_id:
            return q
    return get_quality_preset(DEFAULT_QUALITY_ID)


# ---------------------------------------------------------------------------
#  Export formats (container + codec pair)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExportFormat:
    """One row in the export-format dropdown.

    The pair (video_codec, audio_codec) decides the ffmpeg args; the
    extension drives the Save dialog filter and final filename. Format
    is independent of QualityPreset — both are picked separately and
    combined at encode time by :meth:`build_video_args`."""

    id: str
    name_key: str
    desc_key: str
    extension: str           # ".mp4"
    video_codec: str         # "libx264", "libvpx-vp9"
    audio_codec: str         # "aac", "libopus"
    audio_bitrate: str       # "192k", "128k"
    feature_id: str          # tier-gating key

    def build_video_args(self, q: QualityPreset) -> list[str]:
        """ffmpeg ``-c:v ...`` segment for this format paired with the
        given quality preset."""
        if self.video_codec == "libx264":
            return [
                "-c:v", "libx264",
                "-preset", q.ffmpeg_preset,
                "-crf", str(q.crf),
                "-pix_fmt", "yuv420p",
            ]
        if self.video_codec == "libvpx-vp9":
            return [
                "-c:v", "libvpx-vp9",
                "-crf", str(q.crf_vp9),
                "-b:v", "0",            # constant-quality (CRF) mode
                "-deadline", "good",
                "-row-mt", "1",
                "-pix_fmt", "yuv420p",
            ]
        # Fallback — should never hit; future-proof so a misconfigured
        # registry still produces a playable file.
        return [
            "-c:v", self.video_codec,
            "-pix_fmt", "yuv420p",
        ]

    def build_audio_args(self) -> list[str]:
        return [
            "-c:a", self.audio_codec,
            "-b:a", self.audio_bitrate,
        ]


EXPORT_FORMATS: list[ExportFormat] = [
    ExportFormat(
        id="mp4",
        name_key="export.format.mp4",
        desc_key="export.format.mp4.desc",
        extension=".mp4",
        video_codec="libx264", audio_codec="aac", audio_bitrate="192k",
        feature_id="export.format.mp4",
    ),
    ExportFormat(
        id="webm",
        name_key="export.format.webm",
        desc_key="export.format.webm.desc",
        extension=".webm",
        video_codec="libvpx-vp9", audio_codec="libopus", audio_bitrate="128k",
        feature_id="export.format.webm",
    ),
    ExportFormat(
        id="mov",
        name_key="export.format.mov",
        desc_key="export.format.mov.desc",
        extension=".mov",
        video_codec="libx264", audio_codec="aac", audio_bitrate="192k",
        feature_id="export.format.mov",
    ),
]


DEFAULT_FORMAT_ID = "mp4"


def get_export_format(format_id: str) -> ExportFormat:
    for f in EXPORT_FORMATS:
        if f.id == format_id:
            return f
    return get_export_format(DEFAULT_FORMAT_ID)


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
    typo_overlays: list[tuple[int, float, float]] | None = None,
    color_grade=None,
) -> str:
    """Build an FFmpeg filter_complex graph (video-only).

    ``fade_segments`` is a list of ``FadeSegment``-like objects (anything
    with ``start_ms`` / ``end_ms``) placed on the track. Each becomes a
    fade-out then fade-in pair in the concatenated output stream.

    ``typo_overlays`` is a list of ``(input_idx, t_start, t_end)`` for
    typography MOV inputs. Each gets time-shifted via ``setpts`` so its
    own frame 0 aligns with ``t_start`` in the output, then composited
    with an ``enable=between(t,start,end)`` overlay.

    ``color_grade`` is an optional :class:`app.color_grading.ColorGrade`.
    When provided (and non-identity), an ``eq + colorbalance`` filter is
    inserted right after the source concat so the grade applies under
    every overlay (strokes, typography, subtitles all stay un-graded).
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

    # Color grading — applied to the concatenated stream before any
    # overlay so strokes/typo/subs remain at their authored colors.
    if color_grade is not None:
        from app.color_grading import to_ffmpeg_filters
        cg_expr = to_ffmpeg_filters(color_grade)
        if cg_expr:
            label = "[cvg]"
            parts.append(f"{current}{cg_expr}{label}")
            current = label

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

    # Typography overlays — each MOV starts playing at its t_start in
    # the output timeline. ``setpts=PTS-STARTPTS+OFFSET/TB`` shifts the
    # MOV stream so its first frame appears at OFFSET seconds.
    if typo_overlays:
        for i, (input_idx, t_start, t_end) in enumerate(typo_overlays):
            shift_label = f"[t{i}s]"
            ovl_label = f"[t{i}o]"
            parts.append(
                f"[{input_idx}:v]setpts=PTS-STARTPTS+{t_start:.3f}/TB,"
                f"format=rgba{shift_label}"
            )
            enable = _overlay_enable_expr(t_start, t_end)
            parts.append(
                f"{current}{shift_label}overlay=enable='{enable}':"
                f"shortest=0{ovl_label}"
            )
            current = ovl_label

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
        stickers: list | None = None,
        audio_tracks: list | None = None,
        # Each tuple: (start_ms, end_ms, TextClip) where times are in
        # the active track's *source* ms (same convention as bubbles
        # and stickers — _map_source_to_output translates them through
        # cuts/speed to the output timeline). The exporter renders
        # each clip to a small MOV with alpha and overlays it.
        text_actors_source: list | None = None,
        quality_id: str = DEFAULT_QUALITY_ID,
        format_id: str = DEFAULT_FORMAT_ID,
        color_grade=None,
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
        self._stickers = list(stickers) if stickers else []
        self._audio_tracks = list(audio_tracks) if audio_tracks else []
        self._text_actors_source = list(text_actors_source) if text_actors_source else []
        self._quality = get_quality_preset(quality_id)
        self._format = get_export_format(format_id)
        self._color_grade = color_grade        # ColorGrade or None
        self._temp_pngs: list[str] = []
        self._temp_movs: list[str] = []
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
        if (
            not self._strokes
            and not self._bubbles
            and not self._stickers
        ):
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
            fd, png_path = tempfile.mkstemp(suffix=".png", prefix="bitdam_stroke_")
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
                    suffix=".png", prefix="bitdam_bubble_"
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

        # PNG stickers — pre-baked at source resolution (rotation + global
        # opacity folded into the PNG alpha by PIL), time-gated between
        # start_ms and end_ms. Z-ordered so lower indices overlay first
        # and end up *behind* later ones.
        if self._stickers:
            from app.drawing import render_sticker_to_png
            ordered = sorted(self._stickers, key=lambda s: int(getattr(s, "z_index", 0)))
            for sticker in ordered:
                t_start = _map_source_to_output(
                    int(sticker.start_ms), self._segments
                )
                if t_start < 0:
                    t_start = 0.0
                # ``end_ms`` semantics: -1 / None = run to the end.
                end_raw = getattr(sticker, "end_ms", -1)
                if end_raw is None or int(end_raw) < 0:
                    t_end = None
                else:
                    t_end_mapped = _map_source_to_output(
                        int(end_raw), self._segments
                    )
                    t_end = t_end_mapped if t_end_mapped >= 0 else total_out_s
                fd, png_path = tempfile.mkstemp(
                    suffix=".png", prefix="bitdam_sticker_"
                )
                os.close(fd)
                ok = render_sticker_to_png(sticker, src_w, src_h, png_path)
                if not ok:
                    try:
                        os.unlink(png_path)
                    except OSError:
                        pass
                    continue
                png_paths.append(png_path)
                overlay_spec.append((input_idx, t_start, t_end))
                input_idx += 1
        return png_paths, overlay_spec

    def _prepare_typography_overlays(
        self, src_w: int, src_h: int, fps: int, base_input_idx: int,
    ) -> tuple[list[str], list[tuple[int, float, float]]]:
        """Pre-render every TextClip to a small QtRLE-encoded MOV with
        alpha. Returns (mov_paths, overlay_spec) where each entry is
        ``(input_idx, t_start_output, t_end_output)`` in *output*
        seconds (cuts/speed already mapped)."""
        if not self._text_actors_source:
            return [], []
        from app.typo_render import render_clip_to_mov

        mov_paths: list[str] = []
        overlay_spec: list[tuple[int, float, float]] = []
        input_idx = int(base_input_idx)
        total_out_s = sum((e - s) / sp for (s, e, sp) in self._segments) / 1000.0

        for entry in self._text_actors_source:
            try:
                start_ms, end_ms, clip = entry
            except (TypeError, ValueError):
                continue
            t_start = _map_source_to_output(int(start_ms), self._segments)
            if t_start < 0:
                t_start = 0.0
            t_end_mapped = _map_source_to_output(int(end_ms), self._segments)
            t_end = t_end_mapped if t_end_mapped >= 0 else total_out_s
            if t_end <= t_start:
                continue

            fd, mov_path = tempfile.mkstemp(
                suffix=".mov", prefix="bitdam_typo_",
            )
            os.close(fd)
            ok = render_clip_to_mov(clip, Path(mov_path), src_w, src_h, fps=fps)
            if not ok:
                try:
                    os.unlink(mov_path)
                except OSError:
                    pass
                continue
            mov_paths.append(mov_path)
            overlay_spec.append((input_idx, float(t_start), float(t_end)))
            input_idx += 1
        return mov_paths, overlay_spec

    def run(self) -> None:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg = get_ffmpeg_exe()
            if not self._segments:
                raise RuntimeError("No segments to render.")

            self.stage.emit("Building filter graph")
            stroke_png_paths, stroke_overlays = self._prepare_stroke_overlays()
            self._temp_pngs = stroke_png_paths

            # Typography MOVs come AFTER the stroke/bubble/sticker PNGs
            # in the -i list so existing overlay indices stay stable.
            src_w, src_h = self._probe_source_dimensions()
            typo_mov_paths, typo_overlays = self._prepare_typography_overlays(
                src_w=src_w, src_h=src_h, fps=30,
                base_input_idx=1 + len(stroke_png_paths),
            )
            self._temp_movs = typo_mov_paths

            graph = build_filter_graph(
                self._segments,
                self._subtitles,
                stroke_overlays,
                fade_segments=self._fade_segments,
                typo_overlays=typo_overlays,
                color_grade=self._color_grade,
            )
            total_output_ms = int(
                sum((e - s) / sp for (s, e, sp) in self._segments) + 0.5
            )
            total_output_ms = max(1, total_output_ms)
            total_output_s = total_output_ms / 1000.0

            # Build audio mixing chain. Input indices for audio files
            # start AFTER the video source (-i 0), every stroke/bubble/
            # sticker PNG, AND every typography MOV.
            from app.audio_tracks import build_audio_filter
            video_input_count = 1 + len(stroke_png_paths) + len(typo_mov_paths)
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
                prefix=f"bitdam_export_{self._out.stem}_",
                dir=str(self._out.parent),
            )
            os.close(fd)
            self._temp_output = temp_path

            cmd = [ffmpeg, "-y", "-i", str(self._source)]
            for png in stroke_png_paths:
                cmd.extend(["-i", png])
            for mov in typo_mov_paths:
                cmd.extend(["-i", mov])
            # Audio inputs come after video + overlay PNGs + typography
            # MOVs so input indices in build_audio_filter line up.
            cmd.extend(audio_inputs)
            cmd.extend([
                "-filter_complex", graph,
                "-map", "[outv]",
            ])
            cmd.extend(self._format.build_video_args(self._quality))
            if audio_count > 0:
                # External audio tracks supplant the source video's
                # audio — the original soundtrack is dropped so the
                # user's chosen BGM / voiceover isn't layered on top
                # of the video's own audio.
                cmd.extend(["-map", "[outa]"])
                cmd.extend(self._format.build_audio_args())
            else:
                # No external audio tracks — pass through the source
                # video's audio when it exists. The ``?`` after ``0:a``
                # makes the stream optional, so silent source videos
                # don't fail the mux.
                cmd.extend(["-map", "0:a?"])
                cmd.extend(self._format.build_audio_args())
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
            for mov in getattr(self, "_temp_movs", []) or []:
                try:
                    os.unlink(mov)
                except OSError:
                    pass
            self._temp_movs = []
            tp = getattr(self, "_temp_output", None)
            if tp:
                try:
                    os.unlink(tp)
                except OSError:
                    pass
            self._temp_output = None
