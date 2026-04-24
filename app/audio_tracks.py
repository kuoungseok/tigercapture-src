"""Audio tracks for the video editor (multi-clip model).

Data model:

- An ``AudioTrack`` is a *lane* on the timeline. It carries track-level
  state (id, master volume) and owns a list of ``AudioClip`` s laid
  out on that lane.
- An ``AudioClip`` is one piece of decoded audio referencing a source
  file, with its own ``offset_ms`` (where it starts on the project
  timeline), trim range into the source, fade actors, cut regions,
  selection state, and cached waveform peaks.

Splitting a clip (user's "cut selection" flow) produces two clips on
the same track, not two tracks — this matches DAW / NLE convention
(Premiere, DaVinci, Audition, Logic, Reaper).

Preview playback (``AudioMixer``):
- One ``QMediaPlayer`` per clip. Each listens to the ``ProjectPlayer``
  state and its clip's window, playing only when the project time
  falls inside its window. The OS audio engine mixes — no Python
  resampling.

Final export (``build_audio_filter``):
- Every non-empty clip from every track becomes an FFmpeg ``-i`` input
  and gets its own ``atrim + adelay + volume + afade`` chain; all
  results are ``amix`` ed. Track-level volume multiplies into the
  clip's volume factor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

if TYPE_CHECKING:
    import numpy as np


AUDIO_EXTS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma"})
VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".gif"})

# Waveform extraction: ~40 peak buckets per second of source audio.
WAVEFORM_BUCKETS_PER_SEC = 40


def is_audio_path(path: Path | str) -> bool:
    p = Path(path)
    return p.suffix.lower() in AUDIO_EXTS


def is_video_path(path: Path | str) -> bool:
    p = Path(path)
    return p.suffix.lower() in VIDEO_EXTS


# ============================== data model ==============================


@dataclass
class AudioClip:
    """A single audio clip placed on an AudioTrack lane."""

    id: int
    source_path: Path | None = None
    duration_ms: int = 0         # natural duration of the source file
    offset_ms: int = 0           # where this clip starts on the project timeline
    trim_start_ms: int = 0       # take source[trim_start_ms : trim_end_ms]
    trim_end_ms: int = 0         # 0 means "use full duration"
    fade_in_ms: int = 0
    fade_out_ms: int = 0
    fades: list = field(default_factory=list)   # FadeSegment-like objects
    cuts: list = field(default_factory=list)    # CutSegment-like objects
    selection_start_ms: int = -1
    selection_end_ms: int = -1
    # Gain factor stacked on top of track.volume (reserved for future
    # per-clip gain control). Kept at 1.0 for now.
    gain: float = 1.0
    # Waveform peaks, shared with split pieces when they come from
    # the same source. Not in equality; updates asynchronously.
    waveform: "np.ndarray | None" = field(default=None, compare=False, repr=False)

    @property
    def effective_trim_end_ms(self) -> int:
        if self.trim_end_ms > 0:
            return min(self.trim_end_ms, self.duration_ms)
        return self.duration_ms

    @property
    def effective_length_ms(self) -> int:
        return max(0, self.effective_trim_end_ms - self.trim_start_ms)

    @property
    def display_name(self) -> str:
        if self.source_path is None:
            return ""
        return self.source_path.stem


@dataclass
class AudioTrack:
    """A timeline lane holding zero or more AudioClips."""

    id: int
    volume: float = 1.0          # master multiplier, 0.0 – 1.5
    clips: list[AudioClip] = field(default_factory=list)

    @property
    def is_loaded(self) -> bool:
        return any(c.source_path is not None for c in self.clips)

    @property
    def first_clip(self) -> AudioClip | None:
        for c in self.clips:
            if c.source_path is not None:
                return c
        return self.clips[0] if self.clips else None

    @property
    def display_name(self) -> str:
        """Label for the track header. When the track has clips from
        different sources, fall back to a "multi-clip" shorthand; with
        a single source name, show that filename."""
        names = {c.source_path.stem for c in self.clips if c.source_path is not None}
        if len(names) == 1:
            return next(iter(names))
        if len(names) > 1:
            return f"{len(self.clips)} clips"
        return ""

    def extent_ms(self) -> int:
        """Latest project-ms any clip on this track reaches."""
        return max(
            (
                c.offset_ms + c.effective_length_ms
                for c in self.clips if c.source_path is not None
            ),
            default=0,
        )

    def clip_at_project_ms(self, project_ms: int) -> AudioClip | None:
        """Return the first clip whose timeline window contains ``project_ms``."""
        for c in self.clips:
            if c.source_path is None:
                continue
            if c.offset_ms <= project_ms < c.offset_ms + c.effective_length_ms:
                return c
        return None


def probe_audio_duration_ms(path: Path) -> int:
    """Return duration of an audio stream in ms, or 0 if probing fails
    OR the file contains no audio stream at all.

    Supports both audio files (mp3/wav/etc.) and video files with an
    audio track (mp4/mov/etc.) — ffmpeg's ``-i`` output always lists
    ``Stream #...: Audio: ...`` for decodable audio streams, so a
    simple substring search distinguishes "has audio" from "video-only
    file" even when the container reports a duration.
    """
    try:
        import re
        import subprocess
        import sys

        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg = get_ffmpeg_exe()
        proc = subprocess.run(
            [ffmpeg, "-i", str(path)],
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=(
                0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
            ),
        )
        stderr = proc.stderr or ""
        # Reject files that advertise only video / data / subtitle streams.
        if "Audio:" not in stderr:
            return 0
        m = re.search(
            r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr
        )
        if not m:
            return 0
        h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return int((h * 3600 + mn * 60 + s) * 1000)
    except Exception:
        return 0


class WaveformExtractor(QThread):
    """Background waveform-peak extractor. Emits ``ready(clip_id, peaks)``
    on success, ``failed(clip_id, reason)`` on decode failure. Tagged
    with the AudioClip id so the editor can route results correctly."""

    ready = Signal(int, object)  # clip_id, np.ndarray
    failed = Signal(int, str)

    def __init__(self, clip_id: int, path: Path) -> None:
        super().__init__()
        self._clip_id = clip_id
        self._path = Path(path)

    def run(self) -> None:
        import sys
        try:
            import subprocess

            import numpy as np
            from imageio_ffmpeg import get_ffmpeg_exe

            ffmpeg = get_ffmpeg_exe()
            target_sr = 8000
            cmd = [
                ffmpeg,
                "-nostdin",
                "-v", "error",
                "-i", str(self._path),
                # Explicitly pick the first audio stream. For video
                # containers (mp4/mov), ``-vn`` alone sometimes leaves
                # ffmpeg trying to copy subtitle/data streams and fail;
                # ``-map 0:a:0`` avoids that.
                "-map", "0:a:0",
                "-ac", "1",
                "-ar", str(target_sr),
                "-f", "s16le",
                "-acodec", "pcm_s16le",
                "pipe:1",
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=(
                    0x08000000 if sys.platform == "win32" else 0
                ),
            )
            raw, err = proc.communicate()
            if proc.returncode != 0 or not raw:
                err_text = (err or b"").decode("utf-8", errors="replace").strip()
                print(
                    f"[waveform] ffmpeg failed for {self._path.name}: "
                    f"rc={proc.returncode} err={err_text[-300:]}",
                    file=sys.stderr, flush=True,
                )
                self.failed.emit(
                    self._clip_id,
                    err_text or f"ffmpeg exited {proc.returncode}",
                )
                return

            samples = np.frombuffer(raw, dtype=np.int16)
            if samples.size == 0:
                self.failed.emit(self._clip_id, "empty decoded stream")
                return

            samples_per_bucket = max(1, target_sr // WAVEFORM_BUCKETS_PER_SEC)
            n_buckets = samples.size // samples_per_bucket
            if n_buckets == 0:
                self.failed.emit(self._clip_id, "audio too short for peaks")
                return
            samples = samples[: n_buckets * samples_per_bucket]
            buckets = samples.reshape(n_buckets, samples_per_bucket)
            peaks = (np.abs(buckets).max(axis=1).astype(np.float32)) / 32768.0
            self.ready.emit(self._clip_id, peaks)
        except Exception as exc:
            print(
                f"[waveform] extractor crashed for {self._path.name}: {exc!r}",
                file=sys.stderr, flush=True,
            )
            try:
                self.failed.emit(self._clip_id, str(exc))
            except Exception:
                pass


# ============================== preview mixer ==============================


class AudioMixer(QObject):
    """Per-clip ``QMediaPlayer`` synchronization engine.

    One QMediaPlayer per live clip. As the project player moves, we
    start / stop / seek each clip's player so only the clips whose
    window contains the current time are audible.

    Volume per clip at time t = track.volume × clip.gain × fade-envelope.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tracks: dict[int, AudioTrack] = {}
        # clip_id → (QMediaPlayer, QAudioOutput, track_id)
        self._players: dict[int, tuple[QMediaPlayer, QAudioOutput, int]] = {}
        self._project_playing: bool = False
        self._project_position_ms: int = 0
        self._volume_timer = QTimer(self)
        self._volume_timer.setInterval(30)
        self._volume_timer.timeout.connect(self._apply_volumes)

    # ---------- lifecycle ----------

    def add_track(self, track: AudioTrack) -> None:
        self._tracks[track.id] = track
        for clip in track.clips:
            if clip.source_path is not None:
                self._ensure_player(clip, track.id)

    def remove_track(self, track_id: int) -> None:
        track = self._tracks.pop(track_id, None)
        if track is not None:
            for clip in list(track.clips):
                self._remove_player(clip.id)

    def update_track(self, track: AudioTrack) -> None:
        """Caller invokes after any structural change (clip added,
        removed, source swapped, trim adjusted). Rebuilds the set of
        live players to match ``track.clips`` exactly."""
        self._tracks[track.id] = track
        desired_ids = {c.id for c in track.clips if c.source_path is not None}
        # Drop players for clips that no longer exist / lost their source.
        for cid, (_p, _o, tid) in list(self._players.items()):
            if tid == track.id and cid not in desired_ids:
                self._remove_player(cid)
        for clip in track.clips:
            if clip.source_path is None:
                continue
            self._ensure_player(clip, track.id)
        # After structural update, resync positions immediately.
        for clip in track.clips:
            if clip.id in self._players:
                self._sync_clip_to_project(clip.id)

    def clear(self) -> None:
        for cid in list(self._players.keys()):
            self._remove_player(cid)
        self._tracks.clear()

    def _ensure_player(self, clip: AudioClip, track_id: int) -> None:
        if clip.source_path is None:
            return
        existing = self._players.get(clip.id)
        if existing is None:
            output = QAudioOutput(self)
            player = QMediaPlayer(self)
            player.setAudioOutput(output)
            self._players[clip.id] = (player, output, track_id)
        player, output, _tid = self._players[clip.id]
        new_url = QUrl.fromLocalFile(str(clip.source_path))
        if player.source() != new_url:
            player.setSource(new_url)

    def _remove_player(self, clip_id: int) -> None:
        entry = self._players.pop(clip_id, None)
        if entry is None:
            return
        player, output, _tid = entry
        try:
            player.stop()
            player.setSource(QUrl())
        except Exception:
            pass
        player.deleteLater()
        output.deleteLater()

    # ---------- ProjectPlayer sync ----------

    @Slot(object)
    def on_state_changed(self, state) -> None:
        from app.simple_video_player import PlayerState

        if state is PlayerState.PLAYING:
            self._project_playing = True
            for cid in self._players:
                self._sync_clip_to_project(cid)
            self._volume_timer.start()
        else:
            self._project_playing = False
            for player, _o, _t in self._players.values():
                try:
                    player.pause()
                except Exception:
                    pass
            self._volume_timer.stop()

    @Slot(int)
    def on_position_changed(self, ms: int) -> None:
        self._project_position_ms = max(0, int(ms))
        if not self._project_playing:
            for cid in self._players:
                self._sync_clip_to_project(cid)

    def _sync_clip_to_project(self, clip_id: int) -> None:
        entry = self._players.get(clip_id)
        if entry is None:
            return
        player, _output, track_id = entry
        track = self._tracks.get(track_id)
        if track is None:
            return
        clip = next((c for c in track.clips if c.id == clip_id), None)
        if clip is None or clip.source_path is None:
            return
        project_ms = self._project_position_ms
        if not self._is_within_window(clip, project_ms):
            try:
                player.pause()
            except Exception:
                pass
            return
        src_ms = clip.trim_start_ms + (project_ms - clip.offset_ms)
        src_ms = max(0, min(src_ms, clip.effective_trim_end_ms))
        try:
            if abs(player.position() - src_ms) > 80:
                player.setPosition(int(src_ms))
            if (
                self._project_playing
                and player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
            ):
                player.play()
        except Exception:
            pass

    @staticmethod
    def _is_within_window(clip: AudioClip, project_ms: int) -> bool:
        start = clip.offset_ms
        end = clip.offset_ms + clip.effective_length_ms
        return start <= project_ms < end

    def _apply_volumes(self) -> None:
        for cid, (_p, output, tid) in self._players.items():
            track = self._tracks.get(tid)
            if track is None:
                continue
            clip = next((c for c in track.clips if c.id == cid), None)
            if clip is None:
                continue
            v = self._volume_at(track, clip, self._project_position_ms)
            try:
                output.setVolume(max(0.0, min(1.0, v)))
            except Exception:
                pass

    @staticmethod
    def _volume_at(track: AudioTrack, clip: AudioClip, project_ms: int) -> float:
        if not AudioMixer._is_within_window(clip, project_ms):
            return 0.0
        base = max(0.0, track.volume) * max(0.0, clip.gain)
        local_ms = project_ms - clip.offset_ms
        end_ms = clip.effective_length_ms
        source_ms = clip.trim_start_ms + local_ms

        # Edge fade-in / fade-out (back-compat).
        if clip.fade_in_ms > 0 and local_ms < clip.fade_in_ms:
            base *= local_ms / clip.fade_in_ms
        if clip.fade_out_ms > 0:
            fo_start = end_ms - clip.fade_out_ms
            if local_ms > fo_start:
                remaining = max(0, end_ms - local_ms)
                base *= remaining / clip.fade_out_ms

        # Cuts — clip-local ms domain.
        for cut in clip.cuts:
            if cut.start_ms <= local_ms < cut.end_ms:
                return 0.0

        # Drag-drop fade actors (kind = in / out / both).
        for f in clip.fades:
            f_start = f.start_ms
            f_end = f.end_ms
            if source_ms < f_start or source_ms > f_end or f_end <= f_start:
                continue
            kind = getattr(f, "kind", "both")
            span = f_end - f_start
            if kind == "in":
                t = (source_ms - f_start) / span
                base *= max(0.0, min(1.0, t))
            elif kind == "out":
                t = (source_ms - f_start) / span
                base *= max(0.0, min(1.0, 1.0 - t))
            else:
                mid = f_start + span // 2
                if source_ms < mid:
                    t = (source_ms - f_start) / max(1, mid - f_start)
                    base *= max(0.0, min(1.0, 1.0 - t))
                else:
                    t = (source_ms - mid) / max(1, f_end - mid)
                    base *= max(0.0, min(1.0, t))
        return base


# ============================== export pipeline ==============================


def _subtract_cuts(
    start_ms: int, end_ms: int, cuts: list
) -> list[tuple[int, int]]:
    """Return disjoint ranges inside [start_ms, end_ms] with each cut's
    [start_ms, end_ms) removed. Cuts are clip-local ms (same domain as
    the range). Empty list means the whole window was cut out."""
    ranges: list[tuple[int, int]] = [(start_ms, end_ms)]
    for cut in cuts:
        try:
            cs = int(cut.start_ms)
            ce = int(cut.end_ms)
        except Exception:
            continue
        if ce <= cs:
            continue
        new_ranges: list[tuple[int, int]] = []
        for s, e in ranges:
            if ce <= s or cs >= e:
                new_ranges.append((s, e))
                continue
            if s < cs:
                new_ranges.append((s, cs))
            if e > ce:
                new_ranges.append((ce, e))
        ranges = new_ranges
    return [(s, e) for s, e in ranges if e > s]


def build_audio_filter(
    tracks: list[AudioTrack],
    video_input_count: int,
    project_duration_ms: int,
) -> tuple[str, list[str], int]:
    """Build the audio portion of an FFmpeg filter_complex.

    Iterates over every loaded clip of every track. Each clip becomes
    an independent ffmpeg -i input with its own atrim / adelay /
    volume / fade chain; everything amixes together at the end.

    Returns (graph, -i list, number_of_audio_inputs).
    """
    clips: list[tuple[AudioTrack, AudioClip]] = []
    for t in tracks:
        for c in t.clips:
            if c.source_path is not None and c.effective_length_ms > 0:
                clips.append((t, c))
    if not clips:
        return "", [], 0

    inputs: list[str] = []
    for _t, c in clips:
        inputs.extend(["-i", str(c.source_path)])

    parts: list[str] = []
    amix_labels: list[str] = []
    out_cap_s = max(0.001, project_duration_ms / 1000.0)

    for idx, (track, clip) in enumerate(clips):
        input_idx = video_input_count + idx
        delay_ms = max(0, int(clip.offset_ms))
        vol = max(0.0, min(2.0, float(track.volume) * float(clip.gain)))
        label_final = f"[a{idx}]"

        # Survive cuts: local ranges (clip-local ms, clip.cuts domain) →
        # source ranges that actually play back.
        surviving_local = _subtract_cuts(0, clip.effective_length_ms, clip.cuts)

        piece_labels: list[str] = []
        for pi, (ls, le) in enumerate(surviving_local):
            src_s = (clip.trim_start_ms + ls) / 1000.0
            src_e = (clip.trim_start_ms + le) / 1000.0
            plabel = f"[a{idx}p{pi}]"
            parts.append(
                f"[{input_idx}:a]atrim={src_s:.3f}:{src_e:.3f},"
                f"asetpts=PTS-STARTPTS{plabel}"
            )
            piece_labels.append(plabel)

        if not piece_labels:
            continue

        if len(piece_labels) == 1:
            current = piece_labels[0]
        else:
            concat_label = f"[a{idx}c]"
            parts.append(
                "".join(piece_labels)
                + f"concat=n={len(piece_labels)}:v=0:a=1{concat_label}"
            )
            current = concat_label

        if delay_ms > 0:
            dlabel = f"[a{idx}d]"
            parts.append(f"{current}adelay={delay_ms}:all=1{dlabel}")
            current = dlabel

        if abs(vol - 1.0) > 1e-3:
            vlabel = f"[a{idx}v]"
            parts.append(f"{current}volume={vol:.3f}{vlabel}")
            current = vlabel

        local_len_ms = clip.effective_length_ms
        fade_filters: list[str] = []
        if clip.fade_in_ms > 0:
            fi_s = clip.offset_ms / 1000.0
            fi_d = max(0.01, clip.fade_in_ms / 1000.0)
            fade_filters.append(f"afade=t=in:st={fi_s:.3f}:d={fi_d:.3f}")
        if clip.fade_out_ms > 0:
            fo_st = (clip.offset_ms + local_len_ms - clip.fade_out_ms) / 1000.0
            fo_d = max(0.01, clip.fade_out_ms / 1000.0)
            fade_filters.append(f"afade=t=out:st={fo_st:.3f}:d={fo_d:.3f}")

        for f in clip.fades:
            try:
                f_start = int(f.start_ms)
                f_end = int(f.end_ms)
                f_kind = getattr(f, "kind", "both")
            except Exception:
                continue
            if f_end <= f_start:
                continue
            proj_start = clip.offset_ms + (f_start - clip.trim_start_ms)
            proj_end = clip.offset_ms + (f_end - clip.trim_start_ms)
            span = (proj_end - proj_start) / 1000.0
            if span <= 0:
                continue
            if f_kind == "in":
                fade_filters.append(
                    f"afade=t=in:st={proj_start / 1000.0:.3f}:d={span:.3f}"
                )
            elif f_kind == "out":
                fade_filters.append(
                    f"afade=t=out:st={proj_start / 1000.0:.3f}:d={span:.3f}"
                )
            else:
                half = span / 2.0
                mid_s = proj_start / 1000.0 + half
                fade_filters.append(
                    f"afade=t=out:st={proj_start / 1000.0:.3f}:d={half:.3f}"
                )
                fade_filters.append(
                    f"afade=t=in:st={mid_s:.3f}:d={half:.3f}"
                )

        if fade_filters:
            parts.append(f"{current}{','.join(fade_filters)}{label_final}")
        else:
            parts.append(f"{current}anull{label_final}")

        amix_labels.append(label_final)

    if not amix_labels:
        return "", [], 0

    if len(amix_labels) == 1:
        parts.append(f"{amix_labels[0]}atrim=0:{out_cap_s:.3f}[outa]")
    else:
        parts.append(
            "".join(amix_labels)
            + f"amix=inputs={len(amix_labels)}:normalize=0:"
            f"duration=longest[amixed]"
        )
        parts.append(f"[amixed]atrim=0:{out_cap_s:.3f}[outa]")

    return ";".join(parts), inputs, len(clips)
