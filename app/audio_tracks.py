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


def default_effects_state() -> dict:
    """Fresh / neutral state for every effect the sound editor exposes.

    Each sub-dict maps to one FFmpeg filter. ``enabled=False`` (or
    degenerate values like gain=0 / mix=0) means the filter is skipped
    during export so the chain stays short."""
    return {
        "eq": {
            "enabled": False,
            "low":  {"freq": 80.0,    "gain": 0.0, "q": 0.7},
            "mid":  {"freq": 1000.0,  "gain": 0.0, "q": 1.0},
            "high": {"freq": 10000.0, "gain": 0.0, "q": 0.7},
        },
        "comp": {
            "enabled": False,
            "threshold": -20.0,   # dB
            "ratio": 4.0,         # N:1
            "attack_ms": 5.0,
            "release_ms": 150.0,
            "makeup_db": 0.0,
            "knee_db": 2.0,
        },
        "gate": {
            "enabled": False,
            "threshold": -50.0,   # dB
            "reduction": 50.0,    # % (0 = no reduction, 100 = full mute below threshold)
        },
        "reverb": {
            "enabled": False,
            "type": "Room",       # Room / Hall / Plate / Spring (cosmetic preset)
            "size": 30.0,         # 0..100 %
            "decay_s": 1.5,
            "damping": 50.0,      # 0..100 %
            "mix": 20.0,          # 0..100 % (dry/wet)
        },
        "delay": {
            "enabled": False,
            "time_ms": 250.0,
            "feedback": 30.0,     # %
            "mix": 20.0,          # %
        },
        "deesser": {
            "enabled": False,
            "freq": 6000.0,       # Hz
            "threshold": -30.0,   # dB
            "reduction": 40.0,    # %
        },
        "time_stretch": {
            "enabled": False,
            "ratio": 1.0,         # 0.5 .. 2.0
            "algorithm": "atempo",
        },
        "ai_master": {
            # Macro-knob post-processing for AI-generated music (Suno /
            # Udio / ACE-Step etc.). Each knob maps to multiple FFmpeg
            # filters under the hood; see ``_build_effect_chain``.
            "enabled": False,
            "preset": "Custom",
            "air":     0.0,    # 0..8 dB   high-shelf at 10 kHz
            "clarity": 0.0,    # 0..100 %  mud cut + presence boost
            "warmth":  0.0,    # 0..100 %  low-shelf + soft saturation
            "width":   100.0,  # 0..200 %  stereo width (100 = neutral)
            "punch":   0.0,    # 0..100 %  low-band compression
            "excite":  0.0,    # 0..100 %  HF harmonic generation
        },
    }


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
    # Volume envelope — list of (time_norm [0,1], volume [0,2]) tuples.
    # Empty = flat at gain (no automation). Each point maps a normalised
    # position within the clip to a volume multiplier; values are
    # linearly interpolated between points.  Exported as an ffmpeg
    # ``volume`` filter expression.
    volume_points: list = field(default_factory=list)
    # Waveform peaks, shared with split pieces when they come from
    # the same source. Not in equality; updates asynchronously.
    waveform: "np.ndarray | None" = field(default=None, compare=False, repr=False)
    # Spectrum bins (64 log-spaced, 20 Hz – 20 kHz). Computed by
    # SpectrumExtractor in the background alongside waveform extraction.
    spectrum_bins: "np.ndarray | None" = field(default=None, compare=False, repr=False)
    # Effects state for the sound editor's EQ / Dynamics / Effects /
    # Advanced tabs. See ``default_effects_state()`` for the shape.
    # Kept as a plain dict so presets can be serialized / diffed as
    # one value and so the AudioClip dataclass stays schema-stable.
    effects: dict = field(default_factory=lambda: default_effects_state())

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
    pan: float = 0.0             # stereo pan, -1.0 (L) to +1.0 (R)
    label: str = ""              # user-visible strip label (empty = auto)

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
            encoding="utf-8",
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
            # Extract stereo (2 channels).  Emits a shape-(2, N) array
            # where row 0 = left peaks, row 1 = right peaks.  Mono
            # sources produce identical rows.  Downstream code checks
            # for the 2-D shape to decide whether to draw stereo.
            cmd = [
                ffmpeg,
                "-nostdin",
                "-v", "error",
                "-i", str(self._path),
                "-map", "0:a:0",
                "-ac", "2",          # always 2 ch — mono sources duplicate
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

            # Interleaved stereo: [L0,R0, L1,R1, ...]
            samples = np.frombuffer(raw, dtype=np.int16)
            if samples.size < 2:
                self.failed.emit(self._clip_id, "empty decoded stream")
                return

            # Separate channels
            left  = samples[0::2].astype(np.float32)
            right = samples[1::2].astype(np.float32)
            n_ch_samples = min(len(left), len(right))
            samples_per_bucket = max(1, target_sr // WAVEFORM_BUCKETS_PER_SEC)
            n_buckets = n_ch_samples // samples_per_bucket
            if n_buckets == 0:
                self.failed.emit(self._clip_id, "audio too short for peaks")
                return
            left  = left [:n_buckets * samples_per_bucket]
            right = right[:n_buckets * samples_per_bucket]
            l_peaks = np.abs(left .reshape(n_buckets, samples_per_bucket)).max(axis=1) / 32768.0
            r_peaks = np.abs(right.reshape(n_buckets, samples_per_bucket)).max(axis=1) / 32768.0
            # Shape (2, N): row 0 = L, row 1 = R
            stereo_peaks = np.stack([l_peaks, r_peaks]).astype(np.float32)
            self.ready.emit(self._clip_id, stereo_peaks)
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
            # NOTE: Qt QAudioOutput has no per-channel stereo pan API.
            # Pan is applied correctly via the ffmpeg ``apan`` filter during
            # export (see build_audio_filter). During preview we only apply
            # volume; panning is a preview-only limitation of the Qt backend.
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


def _build_effect_chain(effects: dict) -> str:
    """Render the sound-editor effect state into a comma-joined filter
    sub-chain. Returns an empty string when no effect is enabled."""
    if not effects:
        return ""
    parts: list[str] = []

    eq = effects.get("eq") or {}
    if eq.get("enabled"):
        for band_name in ("low", "mid", "high"):
            b = eq.get(band_name) or {}
            gain = float(b.get("gain", 0.0))
            if abs(gain) < 0.05:
                continue
            freq = max(20.0, float(b.get("freq", 1000.0)))
            q = max(0.1, float(b.get("q", 1.0)))
            parts.append(
                f"equalizer=f={freq:.1f}:t=q:w={q:.3f}:g={gain:.2f}"
            )

    comp = effects.get("comp") or {}
    if comp.get("enabled"):
        thr_db = float(comp.get("threshold", -20.0))
        ratio = max(1.0, float(comp.get("ratio", 4.0)))
        atk = max(0.01, float(comp.get("attack_ms", 5.0)) / 1000.0)
        rel = max(0.01, float(comp.get("release_ms", 150.0)) / 1000.0)
        makeup = float(comp.get("makeup_db", 0.0))
        knee = max(1.0, float(comp.get("knee_db", 2.0)))
        # acompressor threshold is linear gain, not dB.
        thr_lin = 10 ** (thr_db / 20.0)
        parts.append(
            f"acompressor=threshold={thr_lin:.4f}:ratio={ratio:.2f}:"
            f"attack={atk * 1000:.1f}:release={rel * 1000:.1f}:"
            f"makeup={10 ** (makeup / 20.0):.3f}:knee={knee:.2f}"
        )

    gate = effects.get("gate") or {}
    if gate.get("enabled"):
        thr_db = float(gate.get("threshold", -50.0))
        reduction = max(0.0, min(100.0, float(gate.get("reduction", 50.0))))
        # Map UI reduction to agate ratio: 50% → 4:1, 100% → 20:1.
        gate_ratio = 1.0 + (reduction / 100.0) * 19.0
        thr_lin = 10 ** (thr_db / 20.0)
        parts.append(
            f"agate=threshold={thr_lin:.4f}:ratio={gate_ratio:.2f}:"
            f"attack=10:release=200"
        )

    reverb = effects.get("reverb") or {}
    if reverb.get("enabled") and float(reverb.get("mix", 0.0)) > 0.5:
        # FFmpeg lacks a convolution reverb out of the box; approximate
        # with aecho — size/decay tune the delay and feedback to give
        # "space" at low CPU cost. Works well enough for BGM duck-in
        # style reverb; dedicated convolution (afir) is a future phase.
        size = max(5.0, min(100.0, float(reverb.get("size", 30.0))))
        decay_s = max(0.1, min(10.0, float(reverb.get("decay_s", 1.5))))
        mix = max(0.0, min(100.0, float(reverb.get("mix", 20.0)))) / 100.0
        # aecho expects delay ms list + decay list.
        delay1 = 20 + size * 0.8              # 28..100 ms
        delay2 = delay1 + size * 0.4          # later bounce
        dec1 = max(0.01, min(0.95, 0.35 + decay_s * 0.08))
        dec2 = dec1 * 0.6
        parts.append(
            f"aecho=0.8:0.9:{delay1:.0f}|{delay2:.0f}:"
            f"{dec1:.2f}|{dec2:.2f}"
        )
        # Blend dry/wet crudely via volume.
        if mix < 1.0:
            parts.append(f"volume={(0.6 + 0.4 * mix):.3f}")

    delay = effects.get("delay") or {}
    if delay.get("enabled") and float(delay.get("mix", 0.0)) > 0.5:
        t_ms = max(1.0, min(2000.0, float(delay.get("time_ms", 250.0))))
        fb = max(0.0, min(0.95, float(delay.get("feedback", 30.0)) / 100.0))
        mix = max(0.0, min(1.0, float(delay.get("mix", 20.0)) / 100.0))
        # aecho handles single-tap delay with feedback = decay parameter.
        parts.append(
            f"aecho=0.7:{0.5 + mix * 0.5:.2f}:{t_ms:.0f}:{fb:.2f}"
        )

    deess = effects.get("deesser") or {}
    if deess.get("enabled"):
        # FFmpeg has ``deesser`` in recent builds; fall back to a
        # narrow-band high-shelf cut if the user's ffmpeg is old. Here
        # we use deesser because it ships in imageio-ffmpeg's 6+ build.
        freq = max(2000.0, min(12000.0, float(deess.get("freq", 6000.0))))
        thr_db = float(deess.get("threshold", -30.0))
        reduction = float(deess.get("reduction", 40.0))
        # Use ``deesser`` filter when available; signature is
        # ``deesser=i=int:m=max:f=freq:s=side``. Safer fallback: a
        # steep negative equalizer in the sibilant band.
        gain = -max(0.0, min(18.0, reduction / 100.0 * 12.0))
        if abs(gain) > 0.2:
            parts.append(f"equalizer=f={freq:.0f}:t=q:w=3.0:g={gain:.2f}")

    ts = effects.get("time_stretch") or {}
    if ts.get("enabled"):
        ratio = max(0.5, min(2.0, float(ts.get("ratio", 1.0))))
        if abs(ratio - 1.0) > 1e-3:
            parts.append(f"atempo={ratio:.4f}")

    ai = effects.get("ai_master") or {}
    if ai.get("enabled"):
        # --- Air: high-shelf at 10 kHz (0..+8 dB) ---
        air = max(0.0, min(8.0, float(ai.get("air", 0.0))))
        if air > 0.05:
            parts.append(f"treble=g={air:.2f}:f=10000")

        # --- Clarity: mud cut @ 300 Hz + presence boost @ 3 kHz ---
        clarity = max(0.0, min(100.0, float(ai.get("clarity", 0.0))))
        if clarity > 0.5:
            mud_db = -(clarity / 100.0) * 4.0     # 0..-4 dB
            pres_db = (clarity / 100.0) * 3.0     # 0..+3 dB
            parts.append(f"equalizer=f=300:t=q:w=1.2:g={mud_db:.2f}")
            parts.append(f"equalizer=f=3000:t=q:w=0.8:g={pres_db:.2f}")

        # --- Warmth: low-shelf @ 150 Hz + light soft-sat ---
        warmth = max(0.0, min(100.0, float(ai.get("warmth", 0.0))))
        if warmth > 0.5:
            w_db = (warmth / 100.0) * 2.0         # 0..+2 dB
            parts.append(f"bass=g={w_db:.2f}:f=150")
            # Soft-saturation approximation via ``asoftclip`` when the
            # knob is driven hard enough to matter. Available in ffmpeg
            # 5+ (imageio-ffmpeg ships 6+). Threshold scaled so the
            # saturation is subtle; full-scale is analog-ish tube sat.
            if warmth > 20.0:
                # param drives knee; keep it gentle.
                p = 0.3 + (warmth / 100.0) * 0.4
                parts.append(f"asoftclip=type=tanh:param={p:.2f}")

        # --- Width: stereo expansion / narrowing (100 % = neutral) ---
        width = float(ai.get("width", 100.0))
        if abs(width - 100.0) > 0.5:
            # extrastereo m=0 → mono, 1 → neutral, ~2.5 → very wide.
            m = max(0.0, min(2.5, width / 100.0))
            parts.append(f"extrastereo=m={m:.3f}:c=0")

        # --- Punch: broad-band compression with fast attack ---
        punch = max(0.0, min(100.0, float(ai.get("punch", 0.0))))
        if punch > 0.5:
            # Threshold lowers + ratio rises as knob moves up.
            thr_db = -18.0 - (punch / 100.0) * 6.0           # -18..-24 dB
            ratio = 2.5 + (punch / 100.0) * 2.5              # 2.5..5.0
            thr_lin = 10 ** (thr_db / 20.0)
            makeup_db = (punch / 100.0) * 3.0                # 0..+3 dB
            parts.append(
                f"acompressor=threshold={thr_lin:.4f}:"
                f"ratio={ratio:.2f}:attack=3:release=80:"
                f"makeup={10 ** (makeup_db / 20.0):.3f}:knee=2"
            )

        # --- Excite: HF harmonic generation ---
        # Narrow high-band saturation approximation: drive a high shelf
        # + soft-clip, which synthesizes the 2nd / 3rd harmonics the
        # spec asks for. Not a true split-band exciter, but audibly
        # close for the "restore air lost to MP3 codec" use case.
        excite = max(0.0, min(100.0, float(ai.get("excite", 0.0))))
        if excite > 0.5:
            # Boost 8 kHz region moderately ...
            e_db = (excite / 100.0) * 5.0                    # 0..+5 dB
            parts.append(f"equalizer=f=8000:t=q:w=1.2:g={e_db:.2f}")
            # ... then run a gentle soft-clip so peaks generate
            # harmonics instead of just getting louder.
            if excite > 15.0:
                p = 0.4 + (excite / 100.0) * 0.5
                parts.append(f"asoftclip=type=tanh:param={p:.2f}")

    return ",".join(parts)


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

        # Master volume (track × gain)
        if abs(vol - 1.0) > 1e-3:
            vlabel = f"[a{idx}v]"
            parts.append(f"{current}volume={vol:.3f}{vlabel}")
            current = vlabel

        # Stereo pan — apan filter maps mono/stereo → stereo with L/R gain.
        # pan=0 → left=1, right=1 (centre); pan=-1 → full left; pan=+1 → full right.
        # Formula: left_gain  = max(0, 1 - pan)
        #          right_gain = max(0, 1 + pan)
        track_pan = float(getattr(track, "pan", 0.0))
        if abs(track_pan) > 0.005:
            pan_l = max(0.0, 1.0 - track_pan)
            pan_r = max(0.0, 1.0 + track_pan)
            panlabel = f"[a{idx}pan]"
            parts.append(
                f"{current}apan=stereo"
                f"|c0=c0*{pan_l:.4f}+c1*{pan_l:.4f}"
                f"|c1=c0*{pan_r:.4f}+c1*{pan_r:.4f}"
                f"{panlabel}"
            )
            current = panlabel

        # Volume envelope — converts the clip's volume_points list
        # to an ffmpeg ``volume`` filter with a linear ramp expression
        # so the rendered audio follows the rubberband automation.
        env_pts = getattr(clip, "volume_points", None) or []
        if env_pts:
            clip_dur_s = clip.effective_length_ms / 1000.0
            # Build a piecewise-linear expression:
            #   t = relative seconds within the concatenated clip
            # ffmpeg ``volume`` expression evaluates ``t`` in seconds.
            # We map [0,1] norm → [0, clip_dur_s].
            # Expression: if(lt(t,t0),v0, if(lt(t,t1), v0+(v1-v0)*(t-t0)/(t1-t0), ...
            def _ramp_expr(pts, dur):
                if not pts:
                    return None
                sorted_pts = sorted(pts, key=lambda p: p[0])
                # Add sentinels so the expression covers full duration
                def _v(p): return max(0.0, min(2.0, float(p[1])))
                def _ts(p): return max(0.0, min(1.0, float(p[0]))) * dur
                all_pts = [(0.0, _v(sorted_pts[0]))] if sorted_pts[0][0] > 0 else []
                all_pts += [(_ts(p), _v(p)) for p in sorted_pts]
                if sorted_pts[-1][0] < 1.0:
                    all_pts.append((dur, _v(sorted_pts[-1])))
                if len(all_pts) < 2:
                    return f"{all_pts[0][1]:.3f}" if all_pts else None
                # Build nested if() chain right-to-left
                expr = f"{all_pts[-1][1]:.3f}"
                for i in range(len(all_pts) - 2, -1, -1):
                    t0, v0 = all_pts[i]
                    t1, v1 = all_pts[i + 1]
                    slope = (v1 - v0) / max(1e-6, t1 - t0)
                    seg = f"{v0:.3f}+{slope:.6f}*(t-{t0:.3f})"
                    expr = f"if(lt(t\\,{t1:.3f}),{seg},{expr})"
                return expr
            env_expr = _ramp_expr(env_pts, clip_dur_s)
            if env_expr:
                elabel = f"[a{idx}e]"
                parts.append(f"{current}volume='{env_expr}'{elabel}")
                current = elabel

        # --- sound-editor effects (clip.effects) ---
        fx_chain = _build_effect_chain(clip.effects)
        if fx_chain:
            fxlabel = f"[a{idx}fx]"
            parts.append(f"{current}{fx_chain}{fxlabel}")
            current = fxlabel

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


# ==================== single-clip audio export ====================


def build_single_clip_filter(clip: "AudioClip") -> tuple[str, int]:
    """Build a filter_complex for exporting one clip as a standalone
    audio file. Returns ``(filter_complex, output_length_ms)``. The
    filter expects the source at ``[0:a]`` and emits the final stream
    at ``[out]``.

    The output timeline starts at 0 (offset is dropped — the Sound
    Editor exports the clip in isolation, not the project timeline).
    Cuts compress the duration; fade positions are mapped into post-
    cut coordinates so they land on the right content.
    """
    surviving = _subtract_cuts(0, clip.effective_length_ms, clip.cuts)
    if not surviving:
        # Entire clip cut out — emit a tiny silence so ffmpeg has
        # something to encode. Users shouldn't really hit this.
        return "anullsrc=r=44100:cl=stereo:d=0.01[out]", 10

    total_out_ms = sum(le - ls for ls, le in surviving)

    def local_to_out(local_ms: int) -> int:
        """Map clip-local ms (pre-cut space) into post-cut output ms."""
        out = 0
        for ls, le in surviving:
            if local_ms <= ls:
                return out
            if local_ms < le:
                return out + (local_ms - ls)
            out += (le - ls)
        return out  # past the end

    parts: list[str] = []
    piece_labels: list[str] = []
    for pi, (ls, le) in enumerate(surviving):
        src_s = (clip.trim_start_ms + ls) / 1000.0
        src_e = (clip.trim_start_ms + le) / 1000.0
        plabel = f"[p{pi}]"
        parts.append(
            f"[0:a]atrim={src_s:.3f}:{src_e:.3f},"
            f"asetpts=PTS-STARTPTS{plabel}"
        )
        piece_labels.append(plabel)

    if len(piece_labels) == 1:
        current = piece_labels[0]
    else:
        current = "[trimmed]"
        parts.append(
            "".join(piece_labels)
            + f"concat=n={len(piece_labels)}:v=0:a=1{current}"
        )

    # Per-clip gain. Track volume is intentionally NOT applied here
    # — Sound Editor is clip-scoped; exporting should match what the
    # user authored in the editor, not a project mix.
    vol = max(0.0, min(2.0, float(clip.gain)))
    if abs(vol - 1.0) > 1e-3:
        nxt = "[vol]"
        parts.append(f"{current}volume={vol:.3f}{nxt}")
        current = nxt

    fx = _build_effect_chain(clip.effects)
    if fx:
        nxt = "[fx]"
        parts.append(f"{current}{fx}{nxt}")
        current = nxt

    fade_filters: list[str] = []
    if clip.fade_in_ms > 0:
        fi_d = max(0.01, clip.fade_in_ms / 1000.0)
        fade_filters.append(f"afade=t=in:st=0.000:d={fi_d:.3f}")
    if clip.fade_out_ms > 0 and total_out_ms > 0:
        fo_st = max(0, total_out_ms - clip.fade_out_ms) / 1000.0
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
        out_start = local_to_out(f_start - clip.trim_start_ms)
        out_end = local_to_out(f_end - clip.trim_start_ms)
        span = (out_end - out_start) / 1000.0
        if span <= 0:
            continue
        st = out_start / 1000.0
        if f_kind == "in":
            fade_filters.append(f"afade=t=in:st={st:.3f}:d={span:.3f}")
        elif f_kind == "out":
            fade_filters.append(f"afade=t=out:st={st:.3f}:d={span:.3f}")
        else:
            half = span / 2.0
            mid = st + half
            fade_filters.append(f"afade=t=out:st={st:.3f}:d={half:.3f}")
            fade_filters.append(f"afade=t=in:st={mid:.3f}:d={half:.3f}")

    if fade_filters:
        parts.append(f"{current}{','.join(fade_filters)}[out]")
    else:
        parts.append(f"{current}anull[out]")

    return ";".join(parts), total_out_ms


# Format key → metadata used by the export UI. ``codec`` is a callable
# ``(AudioQualityPreset) -> list[str]`` because real codec args depend
# on the user-selected sample rate / bitrate / bit depth.
CLIP_EXPORT_FORMATS: dict[str, dict] = {
    "mp3": {
        "ext": ".mp3",
        "codec": lambda q: [
            "-c:a", "libmp3lame", "-b:a", q.mp3_bitrate,
            "-ar", str(q.sample_rate),
        ],
        "label": "MP3",
        "filter": "MP3 (*.mp3)",
        "feature_id": "export.audio.mp3",
    },
    "wav": {
        "ext": ".wav",
        "codec": lambda q: [
            "-c:a", "pcm_s24le" if q.pcm_bits >= 24 else "pcm_s16le",
            "-ar", str(q.sample_rate),
        ],
        "label": "WAV (lossless PCM)",
        "filter": "WAV (*.wav)",
        "feature_id": "export.audio.wav",
    },
    "flac": {
        "ext": ".flac",
        "codec": lambda q: [
            "-c:a", "flac",
            "-compression_level", str(q.flac_compression),
            "-ar", str(q.sample_rate),
            "-sample_fmt", "s32" if q.pcm_bits >= 24 else "s16",
        ],
        "label": "FLAC (lossless)",
        "filter": "FLAC (*.flac)",
        "feature_id": "export.audio.flac",
    },
    "alac": {
        "ext": ".m4a",
        "codec": lambda q: [
            "-c:a", "alac",
            "-ar", str(q.sample_rate),
            "-sample_fmt", "s32p" if q.pcm_bits >= 24 else "s16p",
        ],
        "label": "ALAC (Apple Lossless)",
        "filter": "ALAC (*.m4a)",
        "feature_id": "export.audio.alac",
    },
    "aac": {
        "ext": ".aac",
        "codec": lambda q: [
            "-c:a", "aac", "-b:a", q.aac_bitrate,
            "-ar", str(q.sample_rate),
        ],
        "label": "AAC",
        "filter": "AAC (*.aac)",
        "feature_id": "export.audio.aac",
    },
    "ogg": {
        "ext": ".ogg",
        "codec": lambda q: [
            "-c:a", "libvorbis", "-q:a", str(q.ogg_quality),
            "-ar", str(q.sample_rate),
        ],
        "label": "OGG Vorbis",
        "filter": "OGG (*.ogg)",
        "feature_id": "export.audio.ogg",
    },
}


# ---------------------------------------------------------------------------
#  Audio quality presets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AudioQualityPreset:
    """One row in the audio export quality dropdown.

    All knobs are codec-agnostic — :data:`CLIP_EXPORT_FORMATS` codec
    builders read what they need (sample rate everywhere, bit depth
    for lossless PCM/FLAC/ALAC, lossy bitrate for MP3/AAC, q for OGG)."""

    id: str
    name_key: str
    desc_key: str
    feature_id: str            # tier-gating key
    sample_rate: int           # Hz, 22050 / 44100 / 48000 / 96000
    mp3_bitrate: str           # libmp3lame -b:a (e.g. "192k")
    aac_bitrate: str           # aac        -b:a
    ogg_quality: int           # libvorbis  -q:a, 0..10
    pcm_bits: int              # 16 or 24, applies to WAV/FLAC/ALAC
    flac_compression: int      # 0..12 (8 = strong default)


AUDIO_QUALITY_PRESETS: list[AudioQualityPreset] = [
    AudioQualityPreset(
        id="low",
        name_key="export.audio_quality.low",
        desc_key="export.audio_quality.low.desc",
        feature_id="export.audio_quality.low",
        sample_rate=22050,
        mp3_bitrate="96k", aac_bitrate="96k", ogg_quality=3,
        pcm_bits=16, flac_compression=5,
    ),
    AudioQualityPreset(
        id="standard",
        name_key="export.audio_quality.standard",
        desc_key="export.audio_quality.standard.desc",
        feature_id="export.audio_quality.standard",
        sample_rate=44100,
        mp3_bitrate="192k", aac_bitrate="192k", ogg_quality=5,
        pcm_bits=16, flac_compression=8,
    ),
    AudioQualityPreset(
        id="high",
        name_key="export.audio_quality.high",
        desc_key="export.audio_quality.high.desc",
        feature_id="export.audio_quality.high",
        sample_rate=48000,
        mp3_bitrate="320k", aac_bitrate="320k", ogg_quality=8,
        pcm_bits=24, flac_compression=8,
    ),
    AudioQualityPreset(
        id="studio",
        name_key="export.audio_quality.studio",
        desc_key="export.audio_quality.studio.desc",
        feature_id="export.audio_quality.studio",
        sample_rate=96000,
        mp3_bitrate="320k", aac_bitrate="320k", ogg_quality=10,
        pcm_bits=24, flac_compression=12,
    ),
]


DEFAULT_AUDIO_QUALITY_ID = "standard"


def get_audio_quality_preset(quality_id: str) -> AudioQualityPreset:
    for q in AUDIO_QUALITY_PRESETS:
        if q.id == quality_id:
            return q
    return get_audio_quality_preset(DEFAULT_AUDIO_QUALITY_ID)


class ClipExporter(QThread):
    """Renders one AudioClip to a standalone audio file using FFmpeg.

    Emits ``done(out_path)`` on success, ``failed(reason)`` on error.
    The thread is short-lived (one subprocess call) — safe to start
    and forget."""

    done = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        clip: "AudioClip",
        out_path: "Path | str",
        format_key: str,
        parent: QObject | None = None,
        quality_id: str = DEFAULT_AUDIO_QUALITY_ID,
    ) -> None:
        super().__init__(parent)
        self.clip = clip
        self.out_path = str(out_path)
        self.format_key = format_key
        self.quality_id = quality_id

    def run(self) -> None:
        try:
            import subprocess
            import sys

            from imageio_ffmpeg import get_ffmpeg_exe

            fmt = CLIP_EXPORT_FORMATS.get(self.format_key)
            if fmt is None:
                self.failed.emit(f"Unknown export format: {self.format_key}")
                return
            if self.clip.source_path is None:
                self.failed.emit("Clip has no source file")
                return

            filter_graph, out_ms = build_single_clip_filter(self.clip)
            if out_ms <= 0:
                self.failed.emit("Nothing to export (all content cut out)")
                return

            quality = get_audio_quality_preset(self.quality_id)
            codec_args = fmt["codec"](quality)
            cmd = [
                get_ffmpeg_exe(),
                "-hide_banner",
                "-loglevel", "error",
                "-y",                                  # overwrite
                "-i", str(self.clip.source_path),
                "-filter_complex", filter_graph,
                "-map", "[out]",
                "-vn",                                  # no video
                *codec_args,
                self.out_path,
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=(
                    0x08000000 if sys.platform == "win32" else 0
                ),
            )
            if proc.returncode != 0:
                # ffmpeg error output can be huge; keep the tail.
                err = (proc.stderr or proc.stdout or "")[-1500:]
                self.failed.emit(err or f"ffmpeg exited {proc.returncode}")
                return
            self.done.emit(self.out_path)
        except Exception as e:
            self.failed.emit(str(e))
