from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QThread, Signal

from app.subprocess_utils import hidden_subprocess_kwargs


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

    def build_video_args(
        self, q: QualityPreset, *, hdr_passthrough: bool = False,
    ) -> list[str]:
        """ffmpeg ``-c:v ...`` segment for this format paired with the
        given quality preset.

        ``hdr_passthrough=True`` switches to libx265 + 10-bit + BT.2020
        PQ metadata so an HDR source survives encoding intact. The
        existing libx264 / libvpx-vp9 8-bit path is the default and
        kept byte-equivalent. The ``mov``/``mp4`` containers happily
        carry HEVC; ``.webm`` doesn't, so this branch ignores the
        format codec choice and forces libx265 (the export dialog
        offers passthrough only for HEVC-friendly containers).
        """
        if hdr_passthrough:
            # ``-tag:v hvc1`` is what Apple Quicktime / iOS need to
            # play HEVC out of an .mp4 / .mov container; any other
            # tag (e.g. hev1) won't open on macOS Preview.
            # ``hdr-opt=1:repeat-headers=1`` makes every IDR carry
            # the colorimetry so any cut later still plays as HDR.
            x265_params = (
                "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:"
                "hdr-opt=1:repeat-headers=1"
            )
            return [
                "-c:v", "libx265",
                "-preset", q.ffmpeg_preset,
                "-crf", str(q.crf),
                "-pix_fmt", "yuv420p10le",
                "-tag:v", "hvc1",
                "-x265-params", x265_params,
                # Container-level colour metadata so a player that
                # doesn't parse x265-params (e.g. some browsers) still
                # honours HDR.
                "-color_primaries", "bt2020",
                "-color_trc", "smpte2084",
                "-colorspace", "bt2020nc",
                "-color_range", "tv",
            ]
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

    Phase 1.5e: this is the legacy entry point. New code should call
    ``build_segments_from_clips`` so user-driven splits + clip drags
    show up in the export. Kept here so callers that haven't migrated
    yet keep working.
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


def build_segments_from_clips(
    clips: list,
    speed_segments: list,
) -> list[tuple[int, int, float]]:
    """Phase 1.5e: derive the export-time segment list from a track's
    ``clips`` field (Phase 1.5d's stored ``list[VideoClip]``).

    Walks ``clips`` in their *project-time* order (i.e. sorted by
    ``timeline_in_ms``) and emits ``(source_in_ms, source_out_ms, 1.0)``
    for each. Then folds in ``speed_segments`` the same way the legacy
    ``build_segments`` did, so existing speed UX keeps working.

    Source-time gaps (from cuts within a clip's source) are already
    encoded by each clip's ``[source_in_ms, source_out_ms)`` window —
    no separate cuts list needed. Project-time gaps between clips
    (from a user dragging halves apart after a split) are *not* emitted
    as black-frame holes; the legacy concat-back-to-back behaviour is
    preserved. A future Phase 1.5f could synthesise blank ranges to
    bake project gaps into the output, but DaVinci-style "compact
    export" is the more common expectation.

    Returns segments in ``source-ms`` (not project-ms) so the existing
    ``build_filter_graph`` / ``[0:v]trim=...`` path keeps working with
    the single source video at index 0.
    """
    if not clips:
        return []
    ranges: list[tuple[int, int, float]] = []
    try:
        from app.timeline_model import expanded_timeline_clips
        clips = expanded_timeline_clips(list(clips))
    except Exception:
        clips = list(clips)
    # Sort clips by project-time so the output plays them in user-
    # arranged order. Sorting source-ms would be wrong if the user
    # rearranged clips (Phase 1.5d Step B drag).
    sorted_clips = sorted(clips, key=lambda c: c.timeline_in_ms)
    for clip in sorted_clips:
        s = int(clip.source_in_ms)
        e = int(clip.effective_source_out_ms)
        if e > s:
            ranges.append((s, e, 1.0))

    # Speed segments still apply per source-ms (single-source today).
    # Phase 1.5e doesn't ship per-clip speed yet; speed is treated as
    # a global track-level property and folded in here.
    for seg in speed_segments or []:
        new_ranges: list[tuple[int, int, float]] = []
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

    return [(s, e, sp) for (s, e, sp) in ranges if e > s]


def build_project_segments_from_clips(clips: list) -> list[tuple[int, int, float]]:
    """Compact export segments in project-time coordinates."""
    if not clips:
        return []
    ranges: list[tuple[int, int, float]] = []
    for clip in sorted(clips, key=lambda c: int(getattr(c, "timeline_in_ms", 0))):
        s = int(getattr(clip, "timeline_in_ms", 0))
        e = int(getattr(clip, "timeline_out_ms", 0))
        if e > s:
            ranges.append((s, e, 1.0))
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
    zoom_actors: list | None = None,
    zoom_frame_size: tuple[int, int] | None = None,
    hdr_info=None,
    hdr_passthrough: bool = False,
    pre_rendered_base: bool = False,
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

    HDR Phase 2: ``hdr_info`` (``app.hdr_probe.HDRInfo`` or None). When
    the source is HDR (PQ/HLG), a ``zscale + tonemap=hable`` chain is
    inserted right after concat so the exported file matches what the
    user sees in the preview (Phase 1 already tone-maps the preview).
    Phase 2b will add a real HDR10 / HLG passthrough path; until then
    SDR output is the sane default for the existing libx264 / yuv420p
    encoder targets.

    ``pre_rendered_base=True`` means input 0 is already a preview-parity
    raw video stream with timeline cuts/speed and CPU-only node effects baked.
    In that mode this graph starts at ``[0:v]`` and only applies export-time
    overlays/subtitles/fades, avoiding a second trim/concat/color pass.
    """
    if not segments:
        return ""
    parts: list[str] = []
    if pre_rendered_base:
        parts.append("[0:v]setpts=PTS-STARTPTS[cv0]")
    else:
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

    # HDR Phase 2: tonemap PQ/HLG → Rec.709 SDR before any other
    # filter, UNLESS Phase 2b passthrough is on. ``yuv420p`` at the
    # tail keeps the chain encoder-ready for libx264 / libvpx-vp9 /
    # libaom-av1 without needing extra ``-pix_fmt`` flags downstream.
    is_hdr_source = hdr_info is not None and getattr(hdr_info, "is_hdr", False)
    if is_hdr_source and not hdr_passthrough and not pre_rendered_base:
        tonemap = (
            "zscale=t=linear:npl=100,format=gbrpf32le,"
            "zscale=p=bt709,tonemap=hable,"
            "zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
        )
        label = "[cvtm]"
        parts.append(f"{current}{tonemap}{label}")
        current = label
    elif is_hdr_source and hdr_passthrough and not pre_rendered_base:
        # HDR Phase 2b: force the chain to 10-bit BT.2020 PQ output
        # so the encoder gets the bit depth + colorimetry it expects.
        # Most ffmpeg builds decode HDR sources as ``yuv420p10le``
        # natively, but a ``format=`` filter pins it explicitly.
        label = "[cvhdr]"
        parts.append(f"{current}format=yuv420p10le{label}")
        current = label

    # Zoom actors — Ken-Burns crop+scale chain, time-varying. Inserted
    # before colour grading so the grade operates on the cropped pixels
    # the user actually sees (matches preview's order in
    # project_player._render_frame_at).
    if zoom_actors and zoom_frame_size is not None and not pre_rendered_base:
        from app.video_editor_window import build_zoom_ffmpeg_filter
        zw, zh = zoom_frame_size
        z_expr = build_zoom_ffmpeg_filter(zoom_actors, segments, zw, zh)
        if z_expr:
            label = "[cvz]"
            parts.append(f"{current}{z_expr}{label}")
            current = label

    # Color grading — applied to the concatenated stream before any
    # overlay so strokes/typo/subs remain at their authored colors.
    if color_grade is not None and not pre_rendered_base:
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
        spine_actor_tracks: list | None = None,   # list[SpineActorTrack]
        # Live2D: pre-rendered on the main thread before start().
        # Each entry: (mov_path: str, t_start_s: float, t_end_s: float)
        live2d_pre_rendered: list | None = None,
        quality_id: str = DEFAULT_QUALITY_ID,
        format_id: str = DEFAULT_FORMAT_ID,
        color_grade=None,
        node_item_chain: list | None = None,
        clip_effects: list | None = None,
        zoom_actors: list | None = None,
        hdr_info=None,
        hdr_passthrough: bool = False,
        target_width: "int | None" = None,
        target_height: "int | None" = None,
        target_fps: "float | None" = None,
        render_clip_tracks: list | None = None,
        force_prerender_base: bool = False,
        project_settings: dict | None = None,
        ar_pbr_tracks: list | None = None,
        ar_pbr_asset_descriptors: dict | None = None,
        mmd_tracks: list | None = None,
        mmd_pre_rendered: list | None = None,
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
        self._spine_actor_tracks = list(spine_actor_tracks) if spine_actor_tracks else []
        self._live2d_pre_rendered: list[tuple[str, float, float]] = (
            list(live2d_pre_rendered) if live2d_pre_rendered else []
        )
        self._quality = get_quality_preset(quality_id)
        self._format = get_export_format(format_id)
        self._color_grade = color_grade        # ColorGrade or None
        self._node_item_chain = list(node_item_chain) if node_item_chain else []
        self._clip_effects = list(clip_effects) if clip_effects else []
        self._clip_stabilizers: dict[int, object] = {}
        self._clip_stabilizer_last_frame: dict[int, int] = {}
        self._zoom_actors = list(zoom_actors) if zoom_actors else []
        # HDR Phase 2: when set, ``build_filter_graph`` prepends a
        # tonemap chain to convert PQ/HLG → SDR Rec.709. Same operator
        # the preview uses (Phase 1) so what the user sees IS what
        # they get in the exported file.
        self._hdr_info = hdr_info
        # HDR Phase 2b: ``True`` overrides the SDR tonemap and routes
        # the chain to a 10-bit libx265 + bt2020 PQ encoder so HDR
        # survives intact. Editor sets this from the export-time
        # "HDR passthrough" dialog when the source is HDR.
        self._hdr_passthrough = bool(hdr_passthrough) and (
            hdr_info is not None and getattr(hdr_info, "is_hdr", False)
        )
        # Resolution / FPS presets — None means "use source value".
        self._target_width: int | None = int(target_width) if target_width else None
        self._target_height: int | None = int(target_height) if target_height else None
        self._target_fps: float | None = float(target_fps) if target_fps else None
        self._render_clip_tracks = [
            list(track) for track in (render_clip_tracks or [])
        ]
        self._force_prerender_base = bool(force_prerender_base)
        self._project_settings = dict(project_settings or {})
        try:
            from app.ar_pbr.schema import normalize_ar_tracks

            self._ar_pbr_tracks = normalize_ar_tracks(list(ar_pbr_tracks or []))
        except Exception:
            self._ar_pbr_tracks = list(ar_pbr_tracks or [])
        try:
            from app.mmd.schema import normalize_mmd_tracks

            self._mmd_tracks = normalize_mmd_tracks(list(mmd_tracks or []))
        except Exception:
            self._mmd_tracks = list(mmd_tracks or [])
        self._mmd_pre_rendered: list[tuple[str, float, float]] = (
            list(mmd_pre_rendered) if mmd_pre_rendered else []
        )
        self._ar_pbr_asset_descriptor_cache: dict[str, dict] = {
            str(key): dict(value)
            for key, value in (ar_pbr_asset_descriptors or {}).items()
            if isinstance(value, Mapping)
        }
        self._ar_pbr_asset_import_errors: dict[str, str] = {}
        self._ar_pbr_last_export_diagnostics: dict[str, Any] = {}
        self._mmd_last_export_diagnostics: dict[str, Any] = {}
        self._temp_pngs: list[str] = []
        self._temp_movs: list[str] = []
        self._temp_output: str | None = None
        self._cancel_requested = False
        self._proc = None

    def cancel(self) -> None:
        """Request cancellation and stop any active FFmpeg subprocess."""
        self._cancel_requested = True
        proc = getattr(self, "_proc", None)
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    def _project_color_metadata_args(self) -> list[str]:
        """Return FFmpeg container color metadata for non-HDR-passthrough exports."""
        if self._hdr_passthrough:
            return []
        try:
            from app.color_management import validate_export_color_consistency

            report = validate_export_color_consistency(self._project_settings)
            args = list(report.get("ffmpeg_args") or [])
        except Exception:
            return []
        filtered: list[str] = []
        i = 0
        while i < len(args):
            key = args[i]
            value = args[i + 1] if i + 1 < len(args) else None
            if key == "-pix_fmt":
                i += 2
                continue
            if value is None:
                filtered.append(key)
                i += 1
            else:
                filtered.extend([key, value])
                i += 2
        return filtered

    def _append_project_lut_filters(self, graph: str, input_label: str) -> tuple[str, str]:
        try:
            from app.color_management import append_lut_filter_graph

            cm = (self._project_settings or {}).get("color_management")
            return append_lut_filter_graph(graph, input_label, cm)
        except Exception:
            return graph, input_label

    def _raise_if_canceled(self) -> None:
        if self._cancel_requested:
            raise RuntimeError("Export canceled")

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

    def _probe_source_fps(self) -> float:
        """Return source FPS for raw preview-effect export fallbacks."""
        try:
            import cv2  # type: ignore
            cap = cv2.VideoCapture(str(self._source))
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            cap.release()
            if 1.0 <= fps <= 240.0:
                return fps
        except Exception:
            pass
        return 30.0

    @staticmethod
    def _node_chain_needs_prerender(node_item_chain: list | None) -> bool:
        """Return True when the preview node chain cannot be represented
        reliably by the existing FFmpeg-only export path."""
        for node_item, _masks in node_item_chain or []:
            if getattr(node_item, "bypassed", False):
                continue
            kind = getattr(node_item, "NODE_KIND", "serial")
            if kind == "blur":
                bp = getattr(node_item, "blur_params", None)
                if bp is not None and not bp.is_identity():
                    return True
                continue
            ep = getattr(node_item, "effect_params", None)
            if ep is not None and not ep.is_identity():
                return True
            grade = getattr(node_item, "color_grade", None)
            if grade is not None and not grade.is_identity():
                return True
        return False

    @staticmethod
    def _clip_effects_need_prerender(clip_effects: list | None) -> bool:
        for effect in clip_effects or []:
            if effect is None:
                continue
            if getattr(effect, "cursor_events", None) or getattr(effect, "screenstudio_polish", None):
                return True
            if getattr(effect, "frame_repairs", None):
                return True
            for attr in ("stabilizer", "video_filters", "chroma_key", "bg_removal"):
                params = getattr(effect, attr, None)
                if params is not None and not params.is_identity():
                    return True
        return False

    def _screenstudio_fx_need_prerender(self) -> bool:
        try:
            from app.screenstudio_polish import screenstudio_fx_enabled
            if screenstudio_fx_enabled(project_settings=self._project_settings):
                return True
            for effect in self._clip_effects or []:
                if screenstudio_fx_enabled(effect, self._project_settings):
                    return True
            for track in self._render_clip_tracks or []:
                for clip in track or []:
                    if getattr(clip, "frame_repairs", None):
                        return True
                    if screenstudio_fx_enabled(clip, self._project_settings):
                        return True
        except Exception:
            return False
        return False

    def _apply_screen_frame_style_cpu(self, rgb):
        try:
            from app.screenstudio_polish import apply_screen_frame_style_rgb
            return apply_screen_frame_style_rgb(
                rgb,
                project_settings=self._project_settings,
                target_size=None,
            )
        except Exception:
            return rgb

    def _apply_screenstudio_effect_cpu(self, rgb, source_ms: int, owner):
        try:
            from app.screenstudio_polish import apply_screenstudio_fx_rgb
            return apply_screenstudio_fx_rgb(
                rgb,
                int(source_ms),
                owner=owner,
                project_settings=self._project_settings,
                target_size=None,
            )
        except Exception:
            return rgb

    def _source_position_for_output_ms(self, output_ms: float) -> tuple[int, int]:
        out_cursor = 0.0
        last_end = 0
        last_idx = max(0, len(self._segments) - 1)
        for idx, (s_ms, e_ms, speed) in enumerate(self._segments):
            speed = max(float(speed), 0.001)
            seg_out = (e_ms - s_ms) / speed
            last_end = int(e_ms)
            if output_ms <= out_cursor + seg_out:
                local = max(0.0, output_ms - out_cursor)
                return int(round(s_ms + local * speed)), idx
            out_cursor += seg_out
        return last_end, last_idx

    def _source_ms_for_output_ms(self, output_ms: float) -> int:
        return self._source_position_for_output_ms(output_ms)[0]

    def _clip_effect_for_segment(self, segment_idx: int):
        if 0 <= segment_idx < len(self._clip_effects):
            return self._clip_effects[segment_idx]
        return None

    def _render_project_position_for_output_ms(self, output_ms: float) -> tuple[int, int]:
        out_cursor = 0.0
        last_end = 0
        last_idx = max(0, len(self._segments) - 1)
        for idx, (s_ms, e_ms, speed) in enumerate(self._segments):
            speed = max(float(speed), 0.001)
            seg_out = (e_ms - s_ms) / speed
            last_end = int(e_ms)
            if output_ms <= out_cursor + seg_out:
                local = max(0.0, output_ms - out_cursor)
                return int(round(s_ms + local * speed)), idx
            out_cursor += seg_out
        return last_end, last_idx

    def _decode_cv_clip_rgb(
        self,
        clip,
        project_ms: int,
        caps: dict,
        *,
        src_w: int,
        src_h: int,
    ):
        import cv2  # type: ignore

        sp = getattr(clip, "source_path", None)
        if sp is None:
            return None, 0
        sp = Path(sp)
        entry = caps.get(sp)
        if entry is None:
            cap = cv2.VideoCapture(str(sp))
            if not cap.isOpened():
                return None, 0
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            if fps <= 0:
                fps = 30.0
            entry = (cap, fps)
            caps[sp] = entry
        cap, fps = entry
        source_ms = int(getattr(clip, "source_in_ms", 0)) + (
            int(project_ms) - int(getattr(clip, "timeline_in_ms", 0))
        )
        frame_idx = max(0, int(source_ms / 1000.0 * fps))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, bgr = cap.read()
        if not ok or bgr is None:
            return None, frame_idx
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if rgb.shape[1] != src_w or rgb.shape[0] != src_h:
            rgb = cv2.resize(rgb, (src_w, src_h), interpolation=cv2.INTER_LINEAR)
        try:
            from app.frame_repair import apply_frame_repair_rgb

            def _repair_reader(idx: int):
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(idx)))
                ok_next, bgr_next = cap.read()
                if not ok_next or bgr_next is None:
                    return None
                rgb_next = cv2.cvtColor(bgr_next, cv2.COLOR_BGR2RGB)
                if rgb_next.shape[1] != src_w or rgb_next.shape[0] != src_h:
                    rgb_next = cv2.resize(rgb_next, (src_w, src_h), interpolation=cv2.INTER_LINEAR)
                return rgb_next

            rgb, _repair_applied = apply_frame_repair_rgb(
                rgb,
                clip=clip,
                source_ms=source_ms,
                fps=fps,
                frame_reader=_repair_reader,
            )
        except Exception:
            pass
        rgb = self._apply_clip_stabilizer_cpu(rgb, clip, id(clip), frame_idx)
        rgb = self._apply_clip_zoom_cpu(rgb, clip, source_ms)
        rgb = self._apply_clip_post_effects_cpu(rgb, clip)
        rgb = self._apply_clip_node_graph_cpu(rgb, clip)
        rgb = self._overlay_clip_typography_cpu(rgb, clip, source_ms)
        try:
            from app.screenstudio_polish import apply_cursor_fx_rgb
            rgb = apply_cursor_fx_rgb(
                rgb,
                source_ms,
                owner=clip,
                project_settings=self._project_settings,
            )
        except Exception:
            pass
        return rgb, frame_idx

    @staticmethod
    def _alpha_composite_rgba_pil(base_rgb, overlay):
        if overlay is None:
            return base_rgb
        try:
            import numpy as np
            bbox = overlay.getbbox()
            if not bbox:
                return base_rgb
            h, w = base_rgb.shape[:2]
            x0, y0, x1, y1 = bbox
            x0 = max(0, min(w, x0)); x1 = max(0, min(w, x1))
            y0 = max(0, min(h, y0)); y1 = max(0, min(h, y1))
            if x1 <= x0 or y1 <= y0:
                return base_rgb
            arr = np.asarray(overlay.crop((x0, y0, x1, y1)), dtype=np.uint16)
            if arr.ndim != 3 or arr.shape[2] < 4:
                return base_rgb
            alpha = arr[:, :, 3:4]
            if not np.any(alpha):
                return base_rgb
            result = base_rgb.copy()
            dst = result[y0:y1, x0:x1].astype(np.uint16)
            result[y0:y1, x0:x1] = (
                (arr[:, :, :3] * alpha + dst * (255 - alpha) + 127) // 255
            ).astype(np.uint8)
            return result
        except Exception:
            return base_rgb

    def _composite_nested_spine_cpu(self, rgb, tracks: list, nested_ms: int):
        result = rgb
        h, w = rgb.shape[:2]
        for actor_track in tracks or []:
            for actor_clip in getattr(actor_track, "clips", []) or []:
                if not (int(getattr(actor_clip, "start_ms", 0)) <= nested_ms < int(getattr(actor_clip, "end_ms", 0))):
                    continue
                try:
                    pil_frame = actor_clip.render_frame(
                        w, h, nested_ms,
                        animated=True,
                        fast_preview=False,
                        use_gl=False,
                    )
                    result = self._alpha_composite_rgba_pil(result, pil_frame)
                except Exception:
                    pass
        return result

    def _composite_nested_live2d_cpu(self, rgb, tracks: list, nested_ms: int):
        result = rgb
        h, w = rgb.shape[:2]
        for actor_track in tracks or []:
            try:
                pil_frame = actor_track.render_at(nested_ms, w, h)
                result = self._alpha_composite_rgba_pil(result, pil_frame)
            except Exception:
                pass
        return result

    def _render_clip_content_rgb(
        self,
        clip,
        project_ms: int,
        caps: dict,
        *,
        src_w: int,
        src_h: int,
    ):
        if bool(getattr(clip, "is_nested_sequence", False)):
            nested_ms = int(project_ms) - int(getattr(clip, "timeline_in_ms", 0))
            nested_tracks = clip.nested_tracks() if hasattr(clip, "nested_tracks") else []
            rgb = (
                self._render_clip_tracks_rgb(
                    nested_tracks,
                    nested_ms,
                    caps,
                    src_w=src_w,
                    src_h=src_h,
                )
                if nested_tracks else None
            )
            if rgb is None and (
                getattr(clip, "nested_spine_actor_tracks", None)
                or getattr(clip, "nested_live2d_actor_tracks", None)
            ):
                import numpy as np
                rgb = np.zeros((src_h, src_w, 3), dtype=np.uint8)
            if rgb is None:
                return None
            rgb = self._composite_nested_spine_cpu(
                rgb,
                list(getattr(clip, "nested_spine_actor_tracks", []) or []),
                nested_ms,
            )
            rgb = self._composite_nested_live2d_cpu(
                rgb,
                list(getattr(clip, "nested_live2d_actor_tracks", []) or []),
                nested_ms,
            )
            return rgb
        rgb, _frame_idx = self._decode_cv_clip_rgb(
            clip,
            project_ms,
            caps,
            src_w=src_w,
            src_h=src_h,
        )
        return rgb

    def _apply_nested_clip_fades_cpu(self, rgb, clip, project_ms: int):
        fades = list(getattr(clip, "fades", []) or [])
        if not fades:
            return rgb
        source_ms = int(getattr(clip, "source_in_ms", 0)) + (
            int(project_ms) - int(getattr(clip, "timeline_in_ms", 0))
        )
        scale = 1.0
        for fade in fades:
            if not fade.contains(source_ms):
                continue
            span = max(1, int(getattr(fade, "duration_ms", 0)))
            t = (source_ms - int(getattr(fade, "start_ms", 0))) / span
            kind = getattr(fade, "kind", "both")
            if kind == "in":
                scale *= max(0.0, min(1.0, t))
            elif kind == "out":
                scale *= max(0.0, min(1.0, 1.0 - t))
            else:
                scale *= max(0.0, min(1.0, 1.0 - t * 2.0)) if t < 0.5 else max(0.0, min(1.0, (t - 0.5) * 2.0))
        if scale >= 0.999:
            return rgb
        import numpy as np
        return np.clip(rgb.astype(np.float32) * float(scale), 0, 255).astype(np.uint8)

    def _apply_nested_transition_cpu(
        self,
        rgb,
        clip,
        child_track: list,
        project_ms: int,
        caps: dict,
        *,
        src_w: int,
        src_h: int,
    ):
        ttype = str(getattr(clip, "transition_out_type", "") or "")
        if not ttype:
            return rgb
        t_ms = max(1, int(getattr(clip, "transition_out_ms", 500)))
        clip_out_ms = int(getattr(clip, "timeline_out_ms", 0))
        t_start_ms = clip_out_ms - t_ms
        if int(project_ms) < t_start_ms:
            return rgb
        import numpy as np
        alpha = min(1.0, max(0.0, (int(project_ms) - t_start_ms) / max(1, t_ms)))
        if ttype == "fade_black":
            return np.clip(rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
        if ttype == "fade_white":
            white = np.full_like(rgb, 255, dtype=np.float32)
            return np.clip(rgb.astype(np.float32) * (1.0 - alpha) + white * alpha, 0, 255).astype(np.uint8)
        if ttype != "dissolve":
            return rgb
        next_clip = None
        for candidate in sorted(child_track, key=lambda c: int(getattr(c, "timeline_in_ms", 0))):
            if int(getattr(candidate, "timeline_in_ms", 0)) >= clip_out_ms:
                next_clip = candidate
                break
        if next_clip is None:
            return np.clip(rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
        next_pos = int(getattr(next_clip, "timeline_in_ms", 0)) + max(0, int(project_ms) - t_start_ms)
        rgb_next = self._render_clip_content_rgb(
            next_clip,
            next_pos,
            caps,
            src_w=src_w,
            src_h=src_h,
        )
        if rgb_next is None:
            return np.clip(rgb.astype(np.float32) * (1.0 - alpha), 0, 255).astype(np.uint8)
        try:
            import cv2  # type: ignore
            h, w = rgb.shape[:2]
            if rgb_next.shape[:2] != (h, w):
                rgb_next = cv2.resize(rgb_next, (w, h), interpolation=cv2.INTER_LINEAR)
            return cv2.addWeighted(rgb, float(1.0 - alpha), rgb_next, float(alpha), 0.0)
        except Exception:
            return rgb

    def _render_clip_tracks_rgb(
        self,
        tracks: list,
        project_ms: int,
        caps: dict,
        *,
        src_w: int,
        src_h: int,
    ):
        import cv2  # type: ignore
        import numpy as np

        result = None
        for child_track in tracks:
            active = None
            for clip in sorted(child_track, key=lambda c: int(getattr(c, "timeline_in_ms", 0))):
                try:
                    from app.vtuber.performance_source import is_performance_source_clip

                    if is_performance_source_clip(clip):
                        continue
                except Exception:
                    if bool(getattr(clip, "performance_source", False)):
                        continue
                if clip.contains_timeline_ms(project_ms):
                    active = clip
            if active is None:
                continue
            rgb = self._render_clip_content_rgb(
                active,
                project_ms,
                caps,
                src_w=src_w,
                src_h=src_h,
            )
            if rgb is None:
                continue
            rgb = self._apply_nested_clip_fades_cpu(rgb, active, project_ms)
            rgb = self._apply_nested_transition_cpu(
                rgb,
                active,
                child_track,
                project_ms,
                caps,
                src_w=src_w,
                src_h=src_h,
            )
            if result is None:
                result = rgb.copy()
            else:
                h, w = result.shape[:2]
                if rgb.shape[:2] != (h, w):
                    rgb = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_LINEAR)
                result = rgb
        if result is None:
            result = np.zeros((src_h, src_w, 3), dtype=np.uint8)
        return result

    @staticmethod
    def _default_ar_pbr_export_camera_solution(width: int, height: int) -> dict:
        focal = float(max(1, min(width, height))) * 1.15
        return {
            "id": "export_default_camera",
            "frame_size": [int(width), int(height)],
            "intrinsics": {
                "fx": focal,
                "fy": focal,
                "cx": float(width) * 0.5,
                "cy": float(height) * 0.5,
            },
        }

    @staticmethod
    def _ar_pbr_track_wants_depth(track: Mapping[str, Any]) -> bool:
        placement = track.get("placement") if isinstance(track.get("placement"), Mapping) else {}
        mode = str((placement or {}).get("mode") or "").casefold()
        return bool(track.get("occlusion")) or mode in {
            "road_plane_anchor",
            "plane_anchor",
            "screen_plane",
            "scene_anchor",
        }

    def _ar_pbr_camera_solution_for_export(
        self,
        width: int,
        height: int,
        active_tracks: list[dict],
    ) -> dict:
        for track in active_tracks:
            candidate = track.get("camera_solution") if isinstance(track, Mapping) else None
            if isinstance(candidate, Mapping) and candidate.get("intrinsics"):
                return dict(candidate)
            solution_id = str(track.get("camera_solution_id") or "") if isinstance(track, Mapping) else ""
            if not solution_id:
                continue
            try:
                from app.camera_solve.cache import load_camera_solution

                loaded = load_camera_solution(solution_id)
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                pass
        return self._default_ar_pbr_export_camera_solution(width, height)

    def _ar_pbr_depth_frame_for_export(self, rgb, project_ms: int, active_tracks: list[dict]):
        for track in active_tracks:
            source_id = str(track.get("depth_source_id") or "") if isinstance(track, Mapping) else ""
            if not source_id:
                continue
            try:
                from app.depth.cache import load_depth_frame

                depth = load_depth_frame(source_id, int(project_ms), allow_nearest_ms=80)
                if depth is not None:
                    return depth
            except Exception:
                pass
        if not any(self._ar_pbr_track_wants_depth(track) for track in active_tracks):
            return None
        try:
            from app.depth.estimator import estimate_depth

            depth, _diag = estimate_depth(
                rgb,
                source_id="export_runtime",
                time_ms=int(project_ms),
            )
            return depth
        except Exception:
            return None

    def _ar_pbr_descriptor_for_export_track(self, track: Mapping[str, Any]) -> dict:
        track_id = str(track.get("id") or "")
        asset_path = str(track.get("asset_path") or "")
        keys = [key for key in (track_id, asset_path) if key]
        if asset_path:
            try:
                keys.append(str(Path(asset_path).expanduser().resolve()))
            except Exception:
                pass
        for key in keys:
            cached = self._ar_pbr_asset_descriptor_cache.get(key)
            if isinstance(cached, dict):
                descriptor = self._ar_pbr_prepare_export_descriptor_support(
                    cached,
                    asset_path=asset_path,
                    track_id=track_id,
                )
                self._ar_pbr_asset_descriptor_cache[key] = descriptor
                return descriptor
        if not asset_path:
            return {}
        try:
            from app.ar_pbr.importer import import_asset

            descriptor, diagnostics = import_asset(
                asset_path,
                settings={
                    "placeholder_on_error": True,
                    "max_triangles_per_geometry": 120_000,
                },
            )
            descriptor = dict(descriptor or {})
            descriptor = self._ar_pbr_prepare_export_descriptor_support(
                descriptor,
                asset_path=asset_path,
                track_id=track_id,
                diagnostics=diagnostics,
            )
            for key in keys:
                self._ar_pbr_asset_descriptor_cache[key] = descriptor
            if diagnostics and not diagnostics.get("ok", True):
                self._ar_pbr_asset_import_errors[track_id or asset_path] = "; ".join(
                    str(item) for item in diagnostics.get("warnings", []) or []
                )
            return descriptor
        except Exception as exc:
            self._ar_pbr_asset_import_errors[track_id or asset_path] = f"{type(exc).__name__}: {exc}"
            return {}

    @staticmethod
    def _ar_pbr_prepare_export_descriptor_support(
        descriptor: Mapping[str, Any] | None,
        *,
        asset_path: str = "",
        track_id: str = "",
        diagnostics: Mapping[str, Any] | None = None,
    ) -> dict:
        from app.ar_pbr.asset_support import classify_asset_support, public_asset_support

        data = dict(descriptor or {})
        support = data.get("support")
        if not isinstance(support, dict):
            imported = bool(data.get("geometries")) or str(data.get("import_state") or "") == "ready"
            support = classify_asset_support(
                data,
                diagnostics or {"imported": imported, "fallback": False},
            )
            data["support"] = support
        data["support_ui"] = public_asset_support(
            support,
            asset_path=asset_path or str(data.get("source_path") or ""),
            track_id=track_id,
        )
        return data

    @staticmethod
    def _ar_pbr_export_asset_support_rows(
        active_tracks: list[dict],
        descriptors: Mapping[str, dict],
    ) -> list[dict]:
        from app.ar_pbr.asset_support import public_asset_support

        rows: list[dict] = []
        seen: set[str] = set()
        for track in active_tracks:
            if not isinstance(track, Mapping):
                continue
            track_id = str(track.get("id") or "")
            asset_path = str(track.get("asset_path") or "")
            descriptor = None
            for key in (track_id, asset_path):
                candidate = descriptors.get(key) if isinstance(descriptors, Mapping) else None
                if isinstance(candidate, dict):
                    descriptor = candidate
                    break
            if descriptor is None:
                continue
            support_ui = descriptor.get("support_ui")
            if isinstance(support_ui, dict):
                row = dict(support_ui)
                if not row.get("track_id"):
                    row["track_id"] = track_id
                if not row.get("asset_path"):
                    row["asset_path"] = asset_path
            else:
                row = public_asset_support(
                    descriptor.get("support") if isinstance(descriptor.get("support"), dict) else None,
                    asset_path=asset_path,
                    track_id=track_id,
                )
            dedupe_key = track_id or asset_path or str(row.get("asset_path") or "")
            if dedupe_key and dedupe_key in seen:
                continue
            if dedupe_key:
                seen.add(dedupe_key)
            rows.append(row)
        return rows

    def _ar_pbr_export_settings(self, active_tracks: list[dict]) -> dict:
        descriptors: dict[str, dict] = {}
        for track in active_tracks:
            descriptor = self._ar_pbr_descriptor_for_export_track(track)
            if not descriptor:
                continue
            track_id = str(track.get("id") or "")
            asset_path = str(track.get("asset_path") or "")
            for key in (track_id, asset_path):
                if key:
                    descriptors[key] = descriptor
        asset_support = self._ar_pbr_export_asset_support_rows(active_tracks, descriptors)
        return {
            "renderer": "software_pbr",
            "asset_descriptors": descriptors,
            "asset_support": asset_support,
            "camera_z": 3.25,
            "shadow_blur": 3.0,
            "gpu_triangle_limit": 120_000,
            "packet_ssaa": 2,
            "export_bake": True,
        }

    @staticmethod
    def _ar_pbr_export_renderer_mode() -> str:
        try:
            value = os.environ.get("TIGERCAPTURE_AR_PBR_EXPORT_RENDERER", "gpu").strip().casefold()
        except Exception:
            value = "gpu"
        if value in {"software", "software_pbr", "cpu"}:
            return "software"
        if value in {"gpu", "opengl", "offscreen", "offscreen_gpu", "full_gpu"}:
            return "gpu"
        if value in {"off", "disabled", "none", "0", "false"}:
            return "off"
        return "packet"

    def _apply_ar_pbr_export_cpu(self, rgb, project_ms: int):
        tracks = list(getattr(self, "_ar_pbr_tracks", []) or [])
        if not tracks:
            return rgb
        try:
            import numpy as np
            from app.ar_pbr.compositor import composite_export_frame
            from app.ar_pbr.schema import track_active_at

            active = [track for track in tracks if track_active_at(track, int(project_ms))]
            if not active:
                return rgb
            height, width = rgb.shape[:2]
            camera_solution = self._ar_pbr_camera_solution_for_export(width, height, active)
            depth_frame = self._ar_pbr_depth_frame_for_export(rgb, int(project_ms), active)
            settings = self._ar_pbr_export_settings(active)
            mode = self._ar_pbr_export_renderer_mode()
            settings["renderer"] = "full_gpu" if mode == "gpu" else ("packet" if mode == "packet" else "software_pbr")
            diagnostics: dict[str, Any]
            if mode == "off":
                return rgb
            if mode in {"packet", "gpu"}:
                from app.ar_pbr.export_packet_renderer import (
                    render_gpu_packet_export_frame,
                    render_offscreen_gpu_export_frame,
                )

                renderer = render_offscreen_gpu_export_frame if mode == "gpu" else render_gpu_packet_export_frame
                out, diagnostics = renderer(
                    rgb,
                    time_ms=int(project_ms),
                    ar_tracks=tracks,
                    camera_solution=camera_solution,
                    depth_frame=depth_frame,
                    settings=settings,
                )
                if not (diagnostics or {}).get("ok", True) or not (diagnostics or {}).get("rendered_track_count"):
                    fallback_out, fallback_diag = composite_export_frame(
                        rgb,
                        time_ms=int(project_ms),
                        ar_tracks=tracks,
                        camera_solution=camera_solution,
                        depth_frame=depth_frame,
                        settings=settings,
                    )
                    diagnostics["software_fallback"] = fallback_diag
                    out = fallback_out
            else:
                out, diagnostics = composite_export_frame(
                    rgb,
                    time_ms=int(project_ms),
                    ar_tracks=tracks,
                    camera_solution=camera_solution,
                    depth_frame=depth_frame,
                    settings=settings,
                )
            if self._ar_pbr_asset_import_errors:
                diagnostics["asset_import_errors"] = dict(self._ar_pbr_asset_import_errors)
            if settings.get("asset_support"):
                diagnostics["asset_support"] = list(settings.get("asset_support") or [])
            self._ar_pbr_last_export_diagnostics = diagnostics
            return np.ascontiguousarray(out) if out is not rgb else rgb
        except Exception as exc:
            self._ar_pbr_last_export_diagnostics = {
                "ok": False,
                "fallback": True,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
            return rgb

    def _apply_mmd_export_cpu(self, rgb, project_ms: int):
        if getattr(self, "_mmd_pre_rendered", None):
            self._mmd_last_export_diagnostics = {
                "ok": True,
                "mode": "pre_rendered_alpha_overlay",
                "overlay_count": int(len(self._mmd_pre_rendered)),
                "rendered_track_count": int(len(getattr(self, "_mmd_tracks", []) or [])),
            }
            return rgb
        tracks = list(getattr(self, "_mmd_tracks", []) or [])
        if not tracks:
            return rgb
        try:
            from app.mmd.schema import track_active_at

            active = [track for track in tracks if track_active_at(track, int(project_ms))]
            if not active:
                return rgb
            self._mmd_last_export_diagnostics = {
                "ok": False,
                "mode": "preview_only_pending_offscreen_renderer",
                "active_track_count": int(len(active)),
                "rendered_track_count": 0,
                "track_ids": [str(track.get("id") or "") for track in active],
                "warnings": [
                    "MMD tracks reached export, but offscreen MMD OpenGL export compositing is not implemented yet.",
                ],
            }
            return rgb
        except Exception as exc:
            self._mmd_last_export_diagnostics = {
                "ok": False,
                "mode": "mmd_export_diagnostics_error",
                "active_track_count": 0,
                "rendered_track_count": 0,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
            return rgb

    def _write_clip_track_base_frames(
        self,
        stdin,
        *,
        src_w: int,
        src_h: int,
        export_fps: float,
        total_output_ms: int,
    ) -> None:
        import numpy as np

        caps: dict = {}
        try:
            total_frames = max(1, int(round(total_output_ms / 1000.0 * export_fps)))
            for i in range(total_frames):
                self._raise_if_canceled()
                out_ms = i * 1000.0 / max(export_fps, 0.001)
                project_ms, _segment_idx = self._render_project_position_for_output_ms(out_ms)
                rgb = self._render_clip_tracks_rgb(
                    self._render_clip_tracks,
                    project_ms,
                    caps,
                    src_w=src_w,
                    src_h=src_h,
                )
                rgb = self._apply_zoom_cpu(rgb, project_ms)
                rgb = self._apply_node_chain_cpu(rgb, int(project_ms / 1000.0 * export_fps))
                rgb = self._apply_legacy_color_grade_cpu(rgb)
                rgb = self._apply_ar_pbr_export_cpu(rgb, int(project_ms))
                rgb = self._apply_mmd_export_cpu(rgb, int(project_ms))
                rgb = self._apply_screen_frame_style_cpu(rgb)
                stdin.write(np.ascontiguousarray(rgb).tobytes())
                cur_ms = int(round((i + 1) * total_output_ms / total_frames))
                self.progress.emit(min(cur_ms, total_output_ms), total_output_ms)
        finally:
            for cap, _fps in caps.values():
                try:
                    cap.release()
                except Exception:
                    pass

    def _apply_zoom_cpu(self, rgb, source_ms: int):
        if not self._zoom_actors:
            return rgb
        try:
            import cv2  # type: ignore
            from types import SimpleNamespace
            from app.timeline_model import find_active_zoom, zoom_motion_blur_amount, zoom_window_at
            h, w = rgb.shape[:2]
            zactor = find_active_zoom(
                SimpleNamespace(zoom_actors=self._zoom_actors),
                int(source_ms),
            )
            if zactor is None:
                return rgb
            window = zoom_window_at(zactor, int(source_ms), w, h)
            if window is None:
                return rgb
            cx, cy, cw, ch = window
            cx_i = max(0, int(round(cx)))
            cy_i = max(0, int(round(cy)))
            cw_i = max(1, int(round(cw)))
            ch_i = max(1, int(round(ch)))
            cx_i = min(cx_i, max(0, w - cw_i))
            cy_i = min(cy_i, max(0, h - ch_i))
            cropped = rgb[cy_i:cy_i + ch_i, cx_i:cx_i + cw_i]
            out = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
            blur_amount = float(zoom_motion_blur_amount(zactor, int(source_ms)))
            if blur_amount > 0.001:
                kernel = max(3, int(round(3 + blur_amount * 12)))
                if kernel % 2 == 0:
                    kernel += 1
                softened = cv2.GaussianBlur(out, (kernel, kernel), 0)
                alpha = min(0.42, 0.12 + blur_amount * 0.42)
                out = cv2.addWeighted(out, 1.0 - alpha, softened, alpha, 0)
            return out
        except Exception:
            return rgb

    def _apply_clip_zoom_cpu(self, rgb, clip, source_ms: int):
        try:
            import cv2  # type: ignore
            from app.timeline_model import find_active_zoom, zoom_motion_blur_amount, zoom_window_at

            zactor = find_active_zoom(clip, int(source_ms))
            if zactor is None:
                return rgb
            h, w = rgb.shape[:2]
            window = zoom_window_at(zactor, int(source_ms), w, h)
            if window is None:
                return rgb
            cx, cy, cw, ch = window
            cx_i = max(0, int(round(cx)))
            cy_i = max(0, int(round(cy)))
            cw_i = max(1, int(round(cw)))
            ch_i = max(1, int(round(ch)))
            cx_i = min(cx_i, max(0, w - cw_i))
            cy_i = min(cy_i, max(0, h - ch_i))
            cropped = rgb[cy_i:cy_i + ch_i, cx_i:cx_i + cw_i]
            out = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
            blur_amount = float(zoom_motion_blur_amount(zactor, int(source_ms)))
            if blur_amount > 0.001:
                kernel = max(3, int(round(3 + blur_amount * 12)))
                if kernel % 2 == 0:
                    kernel += 1
                softened = cv2.GaussianBlur(out, (kernel, kernel), 0)
                alpha = min(0.42, 0.12 + blur_amount * 0.42)
                out = cv2.addWeighted(out, 1.0 - alpha, softened, alpha, 0)
            return out
        except Exception:
            return rgb

    def _apply_node_chain_cpu(self, rgb, frame_idx: int):
        if not self._node_item_chain:
            return rgb
        try:
            from app.project_player import _apply_node_effect_player
            for node_item, masks in self._node_item_chain:
                rgb = _apply_node_effect_player(
                    node_item, rgb, masks or [], int(frame_idx)
                )
        except Exception:
            return rgb
        return rgb

    def _apply_legacy_color_grade_cpu(self, rgb):
        if self._node_item_chain:
            return rgb
        grade = self._color_grade
        if grade is None or grade.is_identity():
            return rgb
        try:
            from app.color_grading import apply_to_rgb
            return apply_to_rgb(rgb, grade)
        except Exception:
            return rgb

    def _apply_clip_stabilizer_cpu(self, rgb, effect, segment_idx: int, frame_idx: int):
        params = getattr(effect, "stabilizer", None) if effect is not None else None
        if params is None or params.is_identity():
            return rgb
        try:
            from app.video_stabilizer import FrameStabilizer
            last_frame = self._clip_stabilizer_last_frame.get(segment_idx)
            if last_frame is None or frame_idx <= last_frame:
                stabilizer = FrameStabilizer(params)
                stabilizer.reset()
                self._clip_stabilizers[segment_idx] = stabilizer
            else:
                stabilizer = self._clip_stabilizers.get(segment_idx)
                if stabilizer is None:
                    stabilizer = FrameStabilizer(params)
                    self._clip_stabilizers[segment_idx] = stabilizer
            self._clip_stabilizer_last_frame[segment_idx] = int(frame_idx)
            return stabilizer.apply(rgb)
        except Exception:
            return rgb

    def _apply_clip_post_effects_cpu(self, rgb, effect):
        if effect is None:
            return rgb
        video_filters = getattr(effect, "video_filters", None)
        if video_filters is not None and not video_filters.is_identity():
            try:
                rgb = video_filters.apply(rgb)
            except Exception:
                pass
        chroma_key = getattr(effect, "chroma_key", None)
        if chroma_key is not None and not chroma_key.is_identity():
            try:
                rgb, _alpha = chroma_key.apply(rgb)
            except Exception:
                pass
        bg_removal = getattr(effect, "bg_removal", None)
        if bg_removal is not None and not bg_removal.is_identity():
            try:
                rgb = bg_removal.apply(rgb)
            except Exception:
                pass
        return rgb

    def _apply_clip_node_graph_cpu(self, rgb, clip):
        try:
            ng = getattr(clip, "node_graph", None)
            color_node = getattr(ng, "color", None)
            grade = getattr(color_node, "grade", None)
            if grade is not None and not grade.is_identity():
                from app.color_grading import apply_to_rgb
                return apply_to_rgb(rgb, grade)
        except Exception:
            pass
        return rgb

    def _overlay_clip_typography_cpu(self, rgb, clip, source_ms: int):
        actors = [
            actor for actor in getattr(clip, "typography_actors", []) or []
            if int(getattr(actor, "start_ms", 0)) <= int(source_ms) < int(getattr(actor, "end_ms", 0))
        ]
        if not actors:
            return rgb
        try:
            import numpy as np
            from PySide6.QtGui import QImage
            from app.typo_render import render_clip_frame
            h, w = rgb.shape[:2]
            base = rgb.astype(np.float32)
            for actor in actors:
                local_s = max(
                    0.0,
                    (int(source_ms) - int(getattr(actor, "start_ms", 0))) / 1000.0,
                )
                img = render_clip_frame(actor, local_s, w, h).convertToFormat(
                    QImage.Format.Format_RGBA8888
                )
                bpl = int(img.bytesPerLine())
                arr = np.frombuffer(img.bits(), dtype=np.uint8).reshape((h, bpl))[:, :w * 4]
                rgba = arr.reshape((h, w, 4)).astype(np.float32)
                alpha = rgba[:, :, 3:4] / 255.0
                base = rgba[:, :, :3] * alpha + base * (1.0 - alpha)
            return np.clip(base, 0, 255).astype(np.uint8)
        except Exception:
            return rgb

    def _write_prerendered_base_frames(
        self,
        stdin,
        *,
        src_w: int,
        src_h: int,
        export_fps: float,
        total_output_ms: int,
    ) -> None:
        """Write preview-parity RGB frames to FFmpeg stdin.

        This is the escape hatch for effects that FFmpeg cannot express:
        node graph blur/effect/color chains and tracked masks are evaluated
        with the same Python helpers used by ProjectPlayer.
        """
        import cv2  # type: ignore
        import numpy as np

        cap = cv2.VideoCapture(str(self._source))
        if not cap.isOpened():
            raise RuntimeError(f"Could not open source video: {self._source}")
        source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if source_fps <= 0:
            source_fps = self._probe_source_fps()

        try:
            total_frames = max(1, int(round(total_output_ms / 1000.0 * export_fps)))
            last_frame_idx = -1
            last_rgb = None
            for i in range(total_frames):
                self._raise_if_canceled()
                out_ms = i * 1000.0 / max(export_fps, 0.001)
                source_ms, segment_idx = self._source_position_for_output_ms(out_ms)
                clip_effect = self._clip_effect_for_segment(segment_idx)
                frame_idx = max(0, int(source_ms / 1000.0 * source_fps))
                if frame_idx != last_frame_idx or last_rgb is None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ok, bgr = cap.read()
                    if not ok or bgr is None:
                        rgb = np.zeros((src_h, src_w, 3), dtype=np.uint8)
                    else:
                        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                        if rgb.shape[1] != src_w or rgb.shape[0] != src_h:
                            rgb = cv2.resize(rgb, (src_w, src_h), interpolation=cv2.INTER_LINEAR)
                    last_frame_idx = frame_idx
                    last_rgb = rgb
                else:
                    rgb = last_rgb.copy()

                try:
                    from app.frame_repair import apply_frame_repair_rgb

                    def _repair_reader(idx: int):
                        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(idx)))
                        ok_next, bgr_next = cap.read()
                        if not ok_next or bgr_next is None:
                            return None
                        rgb_next = cv2.cvtColor(bgr_next, cv2.COLOR_BGR2RGB)
                        if rgb_next.shape[1] != src_w or rgb_next.shape[0] != src_h:
                            rgb_next = cv2.resize(rgb_next, (src_w, src_h), interpolation=cv2.INTER_LINEAR)
                        return rgb_next

                    rgb, _repair_applied = apply_frame_repair_rgb(
                        rgb,
                        clip=clip_effect,
                        source_ms=source_ms,
                        fps=source_fps,
                        frame_reader=_repair_reader,
                    )
                    if _repair_applied:
                        last_frame_idx = -1
                except Exception:
                    pass

                rgb = self._apply_clip_stabilizer_cpu(
                    rgb, clip_effect, segment_idx, frame_idx
                )
                rgb = self._apply_zoom_cpu(rgb, source_ms)
                rgb = self._apply_node_chain_cpu(rgb, frame_idx)
                rgb = self._apply_legacy_color_grade_cpu(rgb)
                rgb = self._apply_clip_post_effects_cpu(rgb, clip_effect)
                project_ms, _project_segment_idx = self._render_project_position_for_output_ms(out_ms)
                rgb = self._apply_ar_pbr_export_cpu(rgb, int(project_ms))
                rgb = self._apply_mmd_export_cpu(rgb, int(project_ms))
                rgb = self._apply_screenstudio_effect_cpu(rgb, source_ms, clip_effect)
                stdin.write(np.ascontiguousarray(rgb).tobytes())
                cur_ms = int(round((i + 1) * total_output_ms / total_frames))
                self.progress.emit(min(cur_ms, total_output_ms), total_output_ms)
        finally:
            cap.release()

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
            fd, png_path = tempfile.mkstemp(suffix=".png", prefix="tigercapture_stroke_")
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
                    suffix=".png", prefix="tigercapture_bubble_"
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
                    suffix=".png", prefix="tigercapture_sticker_"
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
                suffix=".mov", prefix="tigercapture_typo_",
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

    def _prepare_spine_actor_overlays(
        self, src_w: int, src_h: int, fps: int, base_input_idx: int,
    ) -> tuple[list[str], list[tuple[int, float, float]]]:
        """Pre-render each SpineActorClip to a temp RGBA MOV (prores4444),
        returns (mov_paths, overlay_spec)."""
        if not self._spine_actor_tracks:
            return [], []
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
        except ImportError:
            return [], []

        import subprocess
        import tempfile as _tmpfile
        from PIL import Image as _PIL_Image

        ffmpeg_exe = get_ffmpeg_exe()
        mov_paths: list[str] = []
        overlay_spec: list[tuple[int, float, float]] = []
        input_idx = int(base_input_idx)
        total_out_s = sum((e - s) / sp for (s, e, sp) in self._segments) / 1000.0

        for actor_track in self._spine_actor_tracks:
            for clip in actor_track.clips:
                t_start = clip.start_ms / 1000.0
                t_end = clip.end_ms / 1000.0
                if t_end <= t_start or t_start > total_out_s:
                    continue

                renderer = clip.get_renderer()
                if renderer is None:
                    continue

                n_frames = max(1, int(clip.duration_ms / 1000.0 * fps))
                fd, mov_path = _tmpfile.mkstemp(
                    suffix=".mov", prefix="tc_spine_actor_"
                )
                os.close(fd)

                cmd = [
                    ffmpeg_exe, "-y",
                    "-f", "rawvideo", "-vcodec", "rawvideo",
                    "-pix_fmt", "rgba",
                    "-s", f"{src_w}x{src_h}",
                    "-r", str(fps),
                    "-i", "pipe:0",
                    "-vcodec", "prores_ks",
                    "-profile:v", "4444",
                    "-pix_fmt", "yuva444p10le",
                    "-an",
                    mov_path,
                ]
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        **hidden_subprocess_kwargs(),
                    )
                    for fi in range(n_frames):
                        frame_ms = clip.start_ms + int(fi / fps * 1000)
                        pil_frame = clip.render_frame(src_w, src_h, frame_ms)
                        if pil_frame is None:
                            pil_frame = _PIL_Image.new("RGBA", (src_w, src_h))
                        # PIL RGBA → raw bytes
                        proc.stdin.write(pil_frame.tobytes())
                    proc.stdin.close()
                    proc.wait()
                    if proc.returncode != 0:
                        raise RuntimeError("ffmpeg spine encode failed")
                except Exception:
                    try:
                        os.unlink(mov_path)
                    except OSError:
                        pass
                    continue

                mov_paths.append(mov_path)
                overlay_spec.append((input_idx, float(t_start), float(t_end)))
                input_idx += 1

        return mov_paths, overlay_spec

    @staticmethod
    def pre_render_live2d_actors(
        tracks: list,
        source_path: str,
        fps: int,
        segments: list,
        progress_cb=None,
        frame_size: tuple[int, int] | None = None,
    ) -> list:
        """Pre-render Live2D actor clips to temp ProRes 4444 MOVs.

        **Must be called on the main (Qt event loop) thread** before
        ``VideoExportThread.start()`` because Live2D rendering requires an
        active OpenGL context.

        Returns a list of ``(mov_path, t_start_s, t_end_s)`` tuples that
        can be passed as ``live2d_pre_rendered`` to the thread constructor.
        """
        if not tracks:
            return []
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
        except ImportError:
            return []

        import subprocess
        import tempfile as _tmpfile
        from PIL import Image as _PIL_Image

        # Probe source video dimensions unless the caller is rendering an
        # actor-only file and already knows the desired output frame size.
        src_w, src_h = 1920, 1080
        if frame_size is not None:
            try:
                src_w = max(1, int(frame_size[0]))
                src_h = max(1, int(frame_size[1]))
            except Exception:
                src_w, src_h = 1920, 1080
        else:
            try:
                import cv2 as _cv2
                cap = _cv2.VideoCapture(source_path)
                w = int(cap.get(_cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(_cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    src_w, src_h = w, h
            except Exception:
                pass

        ffmpeg_exe = get_ffmpeg_exe()
        result: list[tuple[str, float, float]] = []
        total_out_s = sum((e - s) / sp for (s, e, sp) in segments) / 1000.0

        # Count total clips for progress reporting
        all_clips = [c for t in tracks for c in getattr(t, "clips", [])]
        n_total = sum(
            max(1, int(c.duration_ms / 1000.0 * fps))
            for c in all_clips
        ) or 1
        rendered = 0

        for actor_track in tracks:
            for clip in getattr(actor_track, "clips", []):
                t_start = clip.start_ms / 1000.0
                t_end = clip.end_ms / 1000.0
                if t_end <= t_start or t_start > total_out_s:
                    continue

                n_frames = max(1, int(clip.duration_ms / 1000.0 * fps))
                fd, mov_path = _tmpfile.mkstemp(
                    suffix=".mov", prefix="tc_live2d_actor_"
                )
                os.close(fd)

                cmd = [
                    ffmpeg_exe, "-y",
                    "-f", "rawvideo", "-vcodec", "rawvideo",
                    "-pix_fmt", "rgba",
                    "-s", f"{src_w}x{src_h}",
                    "-r", str(fps),
                    "-i", "pipe:0",
                    "-vcodec", "prores_ks",
                    "-profile:v", "4444",
                    "-pix_fmt", "yuva444p10le",
                    "-an",
                    mov_path,
                ]
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        **hidden_subprocess_kwargs(),
                    )
                    for fi in range(n_frames):
                        frame_ms = clip.start_ms + int(fi / fps * 1000)
                        pil_frame = clip.render_frame(src_w, src_h, frame_ms)
                        if pil_frame is None:
                            pil_frame = _PIL_Image.new("RGBA", (src_w, src_h))
                        proc.stdin.write(pil_frame.tobytes())
                        rendered += 1
                        if progress_cb is not None:
                            progress_cb(int(rendered * 100 / n_total))
                    proc.stdin.close()
                    proc.wait()
                    if proc.returncode != 0:
                        raise RuntimeError("ffmpeg live2d encode failed")
                except Exception:
                    try:
                        os.unlink(mov_path)
                    except OSError:
                        pass
                    continue

                result.append((mov_path, float(t_start), float(t_end)))

        return result

    @staticmethod
    def pre_render_mmd_actors(
        tracks: list,
        source_path: str = "",
        fps: int = 30,
        segments: list[tuple[int, int, float]] | None = None,
        progress_cb=None,
        frame_size: tuple[int, int] | None = None,
    ) -> list[tuple[str, float, float]]:
        """Pre-render active MMD tracks to one full-frame alpha MOV."""
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
        except ImportError:
            return []
        try:
            from PySide6.QtGui import QGuiApplication
            if QGuiApplication.instance() is None:
                return []
        except Exception:
            return []
        try:
            from app.mmd.schema import normalize_mmd_tracks

            mmd_tracks = normalize_mmd_tracks(list(tracks or []))
        except Exception:
            mmd_tracks = list(tracks or [])
        if not mmd_tracks:
            return []

        import subprocess
        import tempfile as _tmpfile

        import numpy as np

        segments = list(segments or [(0, 1000, 1.0)])
        fps = max(1, min(120, int(round(float(fps or 30)))))

        def project_ms_for_output_ms(output_ms: float) -> int:
            out_cursor = 0.0
            last_end = 0
            for s_ms, e_ms, speed in segments:
                speed = max(float(speed), 0.001)
                seg_out = (int(e_ms) - int(s_ms)) / speed
                last_end = int(e_ms)
                if output_ms <= out_cursor + seg_out:
                    local = max(0.0, output_ms - out_cursor)
                    return int(round(int(s_ms) + local * speed))
                out_cursor += seg_out
            return int(last_end)

        def probe_size() -> tuple[int, int]:
            if frame_size is not None:
                try:
                    w, h = int(frame_size[0]), int(frame_size[1])
                    if w > 0 and h > 0:
                        return w, h
                except Exception:
                    pass
            try:
                import cv2  # type: ignore

                cap = cv2.VideoCapture(str(source_path))
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    return w, h
            except Exception:
                pass
            return 1920, 1080

        src_w, src_h = probe_size()
        total_output_ms = max(1, int(sum((int(e) - int(s)) / max(float(sp), 0.001) for s, e, sp in segments) + 0.5))
        total_output_s = total_output_ms / 1000.0
        total_frames = max(1, int(round(total_output_s * fps)))
        fd, mov_path = _tmpfile.mkstemp(suffix=".mov", prefix="tc_mmd_actor_")
        os.close(fd)

        cmd = [
            get_ffmpeg_exe(),
            "-y",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{src_w}x{src_h}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",
            "-vcodec",
            "prores_ks",
            "-profile:v",
            "4444",
            "-pix_fmt",
            "yuva444p10le",
            "-an",
            mov_path,
        ]

        rendered_frames = 0
        player = None
        proc = None
        try:
            from app.mmd.offscreen_export import MMDOffscreenGLRenderer
            from app.project_player import ProjectPlayer

            player = ProjectPlayer()
            player.set_mmd_tracks(mmd_tracks)
            renderer = MMDOffscreenGLRenderer()
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                **hidden_subprocess_kwargs(),
            )
            assert proc.stdin is not None
            blank = np.zeros((src_h, src_w, 4), dtype=np.uint8)
            for frame_idx in range(total_frames):
                output_ms = frame_idx * 1000.0 / max(float(fps), 0.001)
                project_ms = project_ms_for_output_ms(output_ms)
                try:
                    items = player._mmd_overlay_items(project_ms, animate=True)
                    rgba = renderer.render_array(items, src_w, src_h) if items else blank
                    if rgba is None:
                        rgba = blank
                    if rgba.shape[0] != src_h or rgba.shape[1] != src_w or rgba.shape[2] < 4:
                        rgba = blank
                    elif int(np.max(rgba[:, :, 3])) > 0 or int(np.max(rgba[:, :, :3])) > 0:
                        rendered_frames += 1
                except Exception:
                    rgba = blank
                proc.stdin.write(np.ascontiguousarray(rgba[:, :, :4], dtype=np.uint8).tobytes())
                if progress_cb is not None and (frame_idx % max(1, fps // 2) == 0 or frame_idx + 1 == total_frames):
                    try:
                        progress_cb(int((frame_idx + 1) * 100 / max(1, total_frames)))
                    except Exception:
                        pass
            proc.stdin.close()
            proc.wait()
            if proc.returncode != 0 or rendered_frames <= 0:
                raise RuntimeError("mmd pre-render produced no visible active frames")
        except Exception:
            try:
                if proc is not None and proc.stdin is not None and not proc.stdin.closed:
                    proc.stdin.close()
            except Exception:
                pass
            try:
                os.unlink(mov_path)
            except OSError:
                pass
            return []
        finally:
            if player is not None:
                try:
                    player.release()
                except Exception:
                    pass

        return [(mov_path, 0.0, total_output_s)]

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
            export_fps = float(self._target_fps or self._probe_source_fps() or 30.0)
            overlay_fps = max(1, int(round(export_fps)))
            use_prerendered_base = (
                self._force_prerender_base
                or self._node_chain_needs_prerender(self._node_item_chain)
                or self._clip_effects_need_prerender(self._clip_effects)
                or bool(self._render_clip_tracks)
                or bool(self._ar_pbr_tracks)
                or bool(self._mmd_tracks)
                or self._screenstudio_fx_need_prerender()
            )
            typo_mov_paths, typo_overlays = self._prepare_typography_overlays(
                src_w=src_w, src_h=src_h, fps=overlay_fps,
                base_input_idx=1 + len(stroke_png_paths),
            )

            # Spine actor MOVs come AFTER typography MOVs
            self.stage.emit("Baking Spine actors")
            spine_mov_paths, spine_overlays = self._prepare_spine_actor_overlays(
                src_w=src_w, src_h=src_h, fps=overlay_fps,
                base_input_idx=1 + len(stroke_png_paths) + len(typo_mov_paths),
            )
            # Live2D MOVs were pre-rendered on the main thread before start().
            # Assign input indices continuing after spine MOVs.
            live2d_overlays: list[tuple[int, float, float]] = []
            live2d_mov_paths: list[str] = []
            if self._live2d_pre_rendered:
                self.stage.emit("Adding Live2D actors")
                l2d_base = 1 + len(stroke_png_paths) + len(typo_mov_paths) + len(spine_mov_paths)
                for i, (mov_path, t_start, t_end) in enumerate(self._live2d_pre_rendered):
                    live2d_mov_paths.append(mov_path)
                    live2d_overlays.append((l2d_base + i, float(t_start), float(t_end)))

            mmd_overlays: list[tuple[int, float, float]] = []
            mmd_mov_paths: list[str] = []
            if self._mmd_pre_rendered:
                self.stage.emit("Adding MMD actors")
                mmd_base = 1 + len(stroke_png_paths) + len(typo_mov_paths) + len(spine_mov_paths) + len(live2d_mov_paths)
                for i, (mov_path, t_start, t_end) in enumerate(self._mmd_pre_rendered):
                    mmd_mov_paths.append(mov_path)
                    mmd_overlays.append((mmd_base + i, float(t_start), float(t_end)))

            self._temp_movs = typo_mov_paths + spine_mov_paths + live2d_mov_paths + mmd_mov_paths

            all_overlays = (typo_overlays or []) + (spine_overlays or []) + live2d_overlays + mmd_overlays
            graph = build_filter_graph(
                self._segments,
                self._subtitles,
                stroke_overlays,
                fade_segments=self._fade_segments,
                typo_overlays=all_overlays,
                color_grade=self._color_grade,
                zoom_actors=self._zoom_actors,
                zoom_frame_size=(src_w, src_h),
                hdr_info=self._hdr_info,
                hdr_passthrough=self._hdr_passthrough,
                pre_rendered_base=use_prerendered_base,
            )
            video_out_label = "outv"
            graph, video_out_label = self._append_project_lut_filters(graph, video_out_label)
            total_output_ms = int(
                sum((e - s) / sp for (s, e, sp) in self._segments) + 0.5
            )
            total_output_ms = max(1, total_output_ms)
            total_output_s = total_output_ms / 1000.0

            # Build audio mixing chain. Input indices for audio files
            # start AFTER the video source (-i 0), every stroke/bubble/
            # sticker PNG, AND every typography+spine+live2d+mmd MOV.
            from app.audio_tracks import build_audio_filter
            video_input_count = (1 + len(stroke_png_paths)
                                 + len(typo_mov_paths) + len(spine_mov_paths)
                                 + len(live2d_mov_paths) + len(mmd_mov_paths))
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
                prefix=f"tigercapture_export_{self._out.stem}_",
                dir=str(self._out.parent),
            )
            os.close(fd)
            self._temp_output = temp_path

            if use_prerendered_base:
                cmd = [
                    ffmpeg, "-y",
                    "-f", "rawvideo", "-vcodec", "rawvideo",
                    "-pix_fmt", "rgb24",
                    "-s", f"{src_w}x{src_h}",
                    "-r", f"{export_fps:.3f}",
                    "-i", "pipe:0",
                ]
            else:
                cmd = [ffmpeg, "-y", "-i", str(self._source)]
            for png in stroke_png_paths:
                cmd.extend(["-i", png])
            for mov in typo_mov_paths:
                cmd.extend(["-i", mov])
            for mov in spine_mov_paths:
                cmd.extend(["-i", mov])
            for mov in live2d_mov_paths:
                cmd.extend(["-i", mov])
            for mov in mmd_mov_paths:
                cmd.extend(["-i", mov])
            source_audio_input_idx: int | None = None
            if use_prerendered_base and audio_count == 0 and not self._render_clip_tracks:
                source_audio_input_idx = video_input_count
                cmd.extend(["-i", str(self._source)])
            # Audio inputs come after video + overlay PNGs + typography,
            # Spine, Live2D, and MMD MOVs so build_audio_filter indices line up.
            cmd.extend(audio_inputs)
            cmd.extend([
                "-filter_complex", graph,
                "-map", f"[{video_out_label}]",
            ])
            video_args = self._format.build_video_args(
                self._quality, hdr_passthrough=self._hdr_passthrough,
            )
            video_args.extend(self._project_color_metadata_args())
            cmd.extend(video_args)
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
                if source_audio_input_idx is not None:
                    cmd.extend(["-map", f"{source_audio_input_idx}:a?"])
                else:
                    cmd.extend(["-map", "0:a?"])
                cmd.extend(self._format.build_audio_args())
            # Resolution preset: scale + letterbox/pillarbox padding.
            if self._target_width and self._target_height:
                tw, th = self._target_width, self._target_height
                scale_filter = (
                    f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                    f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2"
                )
                cmd.extend(["-vf", scale_filter])
            # FPS preset.
            if self._target_fps:
                cmd.extend(["-r", f"{self._target_fps:.3f}"])
            cmd.extend(["-t", f"{total_output_s:.3f}"])
            if use_prerendered_base:
                cmd.extend(["-loglevel", "error", temp_path])
            else:
                cmd.extend([
                    "-progress", "pipe:2",
                    "-nostats",
                    temp_path,
                ])

            self.stage.emit("FFmpeg encoding")
            if use_prerendered_base:
                self.stage.emit("Rendering preview effects")
                proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    **hidden_subprocess_kwargs(),
                )
                self._proc = proc
                assert proc.stdin is not None
                try:
                    if self._render_clip_tracks:
                        self._write_clip_track_base_frames(
                            proc.stdin,
                            src_w=src_w,
                            src_h=src_h,
                            export_fps=export_fps,
                            total_output_ms=total_output_ms,
                        )
                    else:
                        self._write_prerendered_base_frames(
                            proc.stdin,
                            src_w=src_w,
                            src_h=src_h,
                            export_fps=export_fps,
                            total_output_ms=total_output_ms,
                        )
                except BrokenPipeError:
                    pass
                try:
                    proc.stdin.close()
                except OSError:
                    pass
                err_bytes = proc.stderr.read() if proc.stderr is not None else b""
                rc = proc.wait()
                self._proc = None
                err_tail_text = err_bytes.decode("utf-8", errors="replace")
            else:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    errors="replace",
                    **hidden_subprocess_kwargs(),
                )
                self._proc = proc

                last_ms = 0
                err_tail: list[str] = []
                assert proc.stderr is not None
                for line in proc.stderr:
                    if self._cancel_requested:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        break
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
                self._proc = None
                err_tail_text = "".join(err_tail)
            self._raise_if_canceled()
            if rc != 0:
                raise RuntimeError(
                    f"FFmpeg exit {rc}: {err_tail_text.strip()[-400:]}"
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
            self._proc = None
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
