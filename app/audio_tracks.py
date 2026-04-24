"""Audio tracks for the video editor.

Adds a second kind of timeline row alongside the existing video tracks:
each ``AudioTrack`` loads an mp3/wav/m4a/aac/ogg/flac file and plays as
background music (or voiceover) during preview and final export.

Design mirrors ``VideoTrack``:
- ``offset_ms`` places the clip on the project timeline.
- ``trim_start_ms`` / ``trim_end_ms`` select a sub-region of the source.
- ``volume`` (0.0–1.0) scales output.
- ``fade_in_ms`` / ``fade_out_ms`` give a simple ramp at each end.

Preview playback is driven by ``AudioMixer`` (below): one ``QMediaPlayer``
per audio track, each listening to the ``ProjectPlayer``'s state and
position signals. Mixing at preview time is done by the OS audio engine
(Windows: MMDevice; macOS: CoreAudio) — no Python-side resampling.

Final export builds an FFmpeg filter_complex with per-track
``atrim + adelay + volume + afade`` nodes, optionally joined with
``amix``. See ``build_audio_filter`` below.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


AUDIO_EXTS = frozenset({".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma"})
VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".wmv", ".gif"})


def is_audio_path(path: Path | str) -> bool:
    p = Path(path)
    return p.suffix.lower() in AUDIO_EXTS


def is_video_path(path: Path | str) -> bool:
    p = Path(path)
    return p.suffix.lower() in VIDEO_EXTS


@dataclass
class AudioTrack:
    id: int
    source_path: Path | None = None
    duration_ms: int = 0         # natural duration of the source file
    offset_ms: int = 0           # where this clip starts on the project timeline
    trim_start_ms: int = 0       # take source[trim_start_ms : trim_end_ms]
    trim_end_ms: int = 0         # 0 means "use full duration"
    volume: float = 1.0          # 0.0 (silent) – 1.0 (100%); clamped to 2.0 max
    fade_in_ms: int = 0
    fade_out_ms: int = 0

    @property
    def effective_trim_end_ms(self) -> int:
        if self.trim_end_ms > 0:
            return min(self.trim_end_ms, self.duration_ms)
        return self.duration_ms

    @property
    def effective_length_ms(self) -> int:
        """Length this clip occupies on the project timeline (after trim)."""
        return max(0, self.effective_trim_end_ms - self.trim_start_ms)

    @property
    def display_name(self) -> str:
        if self.source_path is None:
            return ""
        return self.source_path.stem


def probe_audio_duration_ms(path: Path) -> int:
    """Return duration of an audio file in milliseconds, or 0 if probing
    fails. Uses imageio-ffmpeg's bundled ffprobe alternative — we call
    ffmpeg with -f null and parse its duration line. Robust but slow;
    callers should probe once per load and cache the result on the
    AudioTrack.
    """
    try:
        # ffmpeg -i input.mp3 2>&1 | grep Duration → "Duration: HH:MM:SS.ms"
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
        # ffmpeg writes probing info to stderr even on success (rc=1 when
        # no output file is given; that's expected).
        m = re.search(
            r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr or ""
        )
        if not m:
            return 0
        h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
        return int((h * 3600 + mn * 60 + s) * 1000)
    except Exception:
        return 0


class AudioMixer(QObject):
    """Synchronizes multiple ``AudioTrack`` playbacks with a ``ProjectPlayer``.

    Each audio track gets its own ``QMediaPlayer`` + ``QAudioOutput``. The
    mixer listens to the project player's state / position / duration
    changes and:

    - **Seek** → for each track, compute the track-local source position
      and ``setPosition`` on its player. If the project time falls
      outside the track's [offset, offset+length) window, pause it.
    - **Play** → start any track whose current window contains the
      project position; leave others paused.
    - **Pause / Stop** → pause every track.
    - **Volume** / fade → applied via QAudioOutput.setVolume using a
      simple linear ramp computed at each tick.

    The mixer also exposes ``add_track`` / ``remove_track`` /
    ``update_track`` so the editor can push model changes in. Tracks are
    identified by their ``id`` field.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tracks: dict[int, AudioTrack] = {}
        self._players: dict[int, QMediaPlayer] = {}
        self._outputs: dict[int, QAudioOutput] = {}
        self._project_playing: bool = False
        self._project_position_ms: int = 0
        # Fade ramp ticks (~33 Hz) — only active while playing.
        self._volume_timer = QTimer(self)
        self._volume_timer.setInterval(30)
        self._volume_timer.timeout.connect(self._apply_volumes)

    # ---------- track lifecycle ----------

    def add_track(self, track: AudioTrack) -> None:
        self._tracks[track.id] = track
        if track.source_path is not None:
            self._ensure_player(track)

    def remove_track(self, track_id: int) -> None:
        self._tracks.pop(track_id, None)
        player = self._players.pop(track_id, None)
        if player is not None:
            try:
                player.stop()
                player.setSource(QUrl())
            except Exception:
                pass
            player.deleteLater()
        out = self._outputs.pop(track_id, None)
        if out is not None:
            out.deleteLater()

    def update_track(self, track: AudioTrack) -> None:
        """Called when a track's source / offset / trim / volume / fades
        change. Re-syncs the underlying QMediaPlayer to match."""
        self._tracks[track.id] = track
        if track.source_path is None:
            # Source cleared — tear down player if any.
            player = self._players.pop(track.id, None)
            if player is not None:
                try:
                    player.stop()
                    player.setSource(QUrl())
                except Exception:
                    pass
                player.deleteLater()
            out = self._outputs.pop(track.id, None)
            if out is not None:
                out.deleteLater()
            return
        self._ensure_player(track)
        self._sync_to_project_position(track.id)

    def _ensure_player(self, track: AudioTrack) -> None:
        if track.source_path is None:
            return
        player = self._players.get(track.id)
        if player is None:
            output = QAudioOutput(self)
            player = QMediaPlayer(self)
            player.setAudioOutput(output)
            self._players[track.id] = player
            self._outputs[track.id] = output
        # (Re)set source if changed.
        current = player.source()
        new_url = QUrl.fromLocalFile(str(track.source_path))
        if current != new_url:
            player.setSource(new_url)

    def clear(self) -> None:
        for tid in list(self._players.keys()):
            self.remove_track(tid)
        self._tracks.clear()

    # ---------- project player sync ----------

    @Slot(object)
    def on_state_changed(self, state) -> None:
        """Accepts the PlayerState enum from ``ProjectPlayer``."""
        from app.simple_video_player import PlayerState

        if state is PlayerState.PLAYING:
            self._project_playing = True
            self._resume_all()
            self._volume_timer.start()
        else:
            self._project_playing = False
            self._pause_all()
            self._volume_timer.stop()

    @Slot(int)
    def on_position_changed(self, ms: int) -> None:
        self._project_position_ms = max(0, int(ms))
        # While playing we let each QMediaPlayer run at its own cadence
        # (saves seek thrash). When paused/scrubbed, ProjectPlayer emits
        # position_changed after set_position → re-sync every track.
        if not self._project_playing:
            for tid in self._players:
                self._sync_to_project_position(tid)

    def _resume_all(self) -> None:
        for tid in self._players:
            self._sync_to_project_position(tid)

    def _pause_all(self) -> None:
        for player in self._players.values():
            try:
                player.pause()
            except Exception:
                pass

    def _sync_to_project_position(self, track_id: int) -> None:
        track = self._tracks.get(track_id)
        player = self._players.get(track_id)
        if track is None or player is None:
            return
        project_ms = self._project_position_ms
        if not self._is_within_window(track, project_ms):
            try:
                player.pause()
            except Exception:
                pass
            return
        src_ms = track.trim_start_ms + (project_ms - track.offset_ms)
        src_ms = max(0, min(src_ms, track.effective_trim_end_ms))
        try:
            # Qt's setPosition is in ms. Only seek when drift > 80 ms to
            # avoid fighting the decoder's forward progress.
            if abs(player.position() - src_ms) > 80:
                player.setPosition(int(src_ms))
            if self._project_playing and player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                player.play()
        except Exception:
            pass

    @staticmethod
    def _is_within_window(track: AudioTrack, project_ms: int) -> bool:
        start = track.offset_ms
        end = track.offset_ms + track.effective_length_ms
        return start <= project_ms < end

    def _apply_volumes(self) -> None:
        """Per-tick volume update applying base volume + fade ramps."""
        for tid, track in self._tracks.items():
            out = self._outputs.get(tid)
            if out is None:
                continue
            v = self._volume_at(track, self._project_position_ms)
            try:
                # QAudioOutput.setVolume expects [0.0, 1.0]. Clamp.
                out.setVolume(max(0.0, min(1.0, v)))
            except Exception:
                pass

    @staticmethod
    def _volume_at(track: AudioTrack, project_ms: int) -> float:
        if not AudioMixer._is_within_window(track, project_ms):
            return 0.0
        base = max(0.0, track.volume)
        local_ms = project_ms - track.offset_ms
        end_ms = track.effective_length_ms
        # Fade in ramp from 0 → 1 across fade_in_ms
        if track.fade_in_ms > 0 and local_ms < track.fade_in_ms:
            base *= local_ms / track.fade_in_ms
        # Fade out ramp from 1 → 0 across last fade_out_ms
        if track.fade_out_ms > 0:
            fo_start = end_ms - track.fade_out_ms
            if local_ms > fo_start:
                remaining = max(0, end_ms - local_ms)
                base *= remaining / track.fade_out_ms
        return base


# =================== FFmpeg filter-graph helpers ===================


def build_audio_filter(
    audio_tracks: list[AudioTrack],
    video_input_count: int,
    project_duration_ms: int,
) -> tuple[str, list[str], int]:
    """Build the audio portion of an FFmpeg filter_complex.

    Parameters
    ----------
    audio_tracks:
        AudioTracks with a valid source_path and positive effective length.
    video_input_count:
        How many inputs (``-i``) the video side already consumed. Audio
        files get appended after those, so the first audio input index
        is ``video_input_count`` and subsequent tracks increment from
        there.
    project_duration_ms:
        Final project duration on the output timeline. Each audio
        track's output is capped to this so a long BGM tail doesn't
        extend the MP4 past the video.

    Returns
    -------
    (audio_graph, audio_inputs, audio_input_count)
        ``audio_graph`` is the semicolon-joined filter chain terminating
        in ``[outa]`` — empty string if ``audio_tracks`` is empty.
        ``audio_inputs`` is the list of ``-i <path>`` pairs to append to
        the ffmpeg command. ``audio_input_count`` is the number of
        inputs consumed (== number of valid audio tracks).
    """
    valid = [
        t for t in audio_tracks
        if t.source_path is not None and t.effective_length_ms > 0
    ]
    if not valid:
        return "", [], 0

    # -i flags to append after the video-side inputs.
    inputs: list[str] = []
    for t in valid:
        inputs.extend(["-i", str(t.source_path)])

    parts: list[str] = []
    amix_labels: list[str] = []
    out_cap_s = max(0.001, project_duration_ms / 1000.0)

    for rel_idx, t in enumerate(valid):
        input_idx = video_input_count + rel_idx
        trim_s = t.trim_start_ms / 1000.0
        trim_end_s = t.effective_trim_end_ms / 1000.0
        delay_ms = max(0, int(t.offset_ms))
        vol = max(0.0, min(2.0, float(t.volume)))
        label_atrim = f"[a{rel_idx}t]"
        label_adelay = f"[a{rel_idx}d]"
        label_vol = f"[a{rel_idx}v]"
        label_final = f"[a{rel_idx}]"

        # 1. Trim source to [trim_start, trim_end].
        parts.append(
            f"[{input_idx}:a]atrim={trim_s:.3f}:{trim_end_s:.3f},"
            f"asetpts=PTS-STARTPTS{label_atrim}"
        )

        # 2. Delay to place on project timeline. `adelay=ms|ms` (per
        #    channel). Use ``all=1`` to apply to every channel.
        if delay_ms > 0:
            parts.append(
                f"{label_atrim}adelay={delay_ms}:all=1{label_adelay}"
            )
            current = label_adelay
        else:
            current = label_atrim

        # 3. Volume scalar.
        if abs(vol - 1.0) > 1e-3:
            parts.append(f"{current}volume={vol:.3f}{label_vol}")
            current = label_vol

        # 4. Fade in / out. FFmpeg afade uses seconds + duration.
        local_len_ms = t.effective_length_ms
        fade_filters: list[str] = []
        if t.fade_in_ms > 0:
            fi_s = (t.offset_ms) / 1000.0
            fi_d = max(0.01, t.fade_in_ms / 1000.0)
            fade_filters.append(f"afade=t=in:st={fi_s:.3f}:d={fi_d:.3f}")
        if t.fade_out_ms > 0:
            fo_st = (t.offset_ms + local_len_ms - t.fade_out_ms) / 1000.0
            fo_d = max(0.01, t.fade_out_ms / 1000.0)
            fade_filters.append(f"afade=t=out:st={fo_st:.3f}:d={fo_d:.3f}")
        if fade_filters:
            parts.append(f"{current}{','.join(fade_filters)}{label_final}")
        else:
            # rename current label to the canonical per-track label
            parts.append(f"{current}anull{label_final}")

        amix_labels.append(label_final)

    if len(amix_labels) == 1:
        # Single track → just alias [outa].
        parts.append(f"{amix_labels[0]}atrim=0:{out_cap_s:.3f}[outa]")
    else:
        # amix sums the inputs; ``normalize=0`` preserves per-track
        # volumes rather than scaling down by 1/N. Cap to project length.
        parts.append(
            "".join(amix_labels)
            + f"amix=inputs={len(amix_labels)}:normalize=0:"
            f"duration=longest[amixed]"
        )
        parts.append(f"[amixed]atrim=0:{out_cap_s:.3f}[outa]")

    return ";".join(parts), inputs, len(valid)
