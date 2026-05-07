"""HDR Phase 1: pluggable video-frame decoder.

The legacy ProjectPlayer talks straight to ``cv2.VideoCapture`` for
every track, which is fast and seek-friendly but strips HDR. This
module introduces a thin abstraction so an HDR-aware path can be
swapped in for those tracks without rewriting the player.

Two implementations:

- ``CV2Decoder`` — wraps ``cv2.VideoCapture``. Used for SDR sources
  (the common case). Mirrors the player's existing usage exactly so
  switching to it is byte-equivalent for SDR.

- ``FFmpegToneMapDecoder`` — pipes raw RGB out of an ffmpeg
  subprocess with a ``zscale + tonemap=hable`` filter chain that
  brings PQ/HLG into Rec.709 SDR. Random-seek is implemented by
  killing the subprocess and restarting it with a fresh ``-ss``
  position; sequential reads stay on the existing pipe so a normal
  play loop only spawns one subprocess per session.

Both implementations expose the same surface:

    open()                     # spawn / open
    seek_to_frame(idx)         # request a specific frame on the next read
    read_rgb()                 # → np.ndarray (H, W, 3) uint8 RGB or None
    fps                        # property
    total_frames               # property
    frame_size                 # property — (w, h)
    release()

The decoder factory ``open_decoder(path, hdr_info=None)`` picks the
right backend based on the HDR probe result the Media Pool already
produced.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np


class VideoDecoder:
    """Abstract base — defines the API ``ProjectPlayer`` consumes.

    Subclasses are responsible for caching the last-read frame index
    so ``seek_to_frame(idx)`` followed by ``read_rgb()`` only re-opens
    / re-spawns when a real seek (non-sequential index) happens.
    """

    fps: float = 0.0
    total_frames: int = 0
    frame_size: tuple[int, int] = (0, 0)

    def open(self) -> bool:
        raise NotImplementedError

    def seek_to_frame(self, idx: int) -> None:
        raise NotImplementedError

    def read_rgb(self) -> Optional[np.ndarray]:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
#  cv2-backed decoder (SDR fast path)
# ---------------------------------------------------------------------------


class CV2Decoder(VideoDecoder):
    """Wraps ``cv2.VideoCapture``. Same semantics as the legacy
    direct calls in ProjectPlayer — just behind the abstract API."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._cap = None
        self._next_seek: Optional[int] = None
        self._last_read_idx: int = -2  # so first read forces a seek

    def open(self) -> bool:
        import cv2
        # Attempt hardware-accelerated decode first (DXVA2/NVDEC/VideoToolbox/VAAPI).
        cap_hw = cv2.VideoCapture(str(self._path), cv2.CAP_FFMPEG)
        try:
            cap_hw.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
        except Exception:
            pass
        if cap_hw.isOpened():
            cap = cap_hw
        else:
            cap_hw.release()
            # HW-accelerated open failed — retry with plain software decode.
            cap = cv2.VideoCapture(str(self._path))
            if not cap.isOpened():
                self._cap = None
                return False
        # Log the active HW acceleration mode so we can confirm NVDEC / DXVA2.
        try:
            accel = cap.get(cv2.CAP_PROP_HW_ACCELERATION)
            print(f"[decoder] HW accel: {accel}", file=sys.stderr, flush=True)
        except Exception:
            pass
        self._cap = cap
        self.fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        self.frame_size = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
        )
        return True

    def seek_to_frame(self, idx: int) -> None:
        self._next_seek = max(0, int(idx))

    def read_rgb(self) -> Optional[np.ndarray]:
        import cv2
        if self._cap is None:
            return None
        target = self._next_seek if self._next_seek is not None else self._last_read_idx + 1
        # Skip the seek if we're already at the right place — ``cv2``
        # ``set(POS_FRAMES, ...)`` is expensive on long files.
        if target != self._last_read_idx + 1 or self._next_seek is not None:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        ret, bgr = self._cap.read()
        if not ret or bgr is None:
            self._next_seek = None
            return None
        self._next_seek = None
        self._last_read_idx = target
        return np.ascontiguousarray(bgr[:, :, ::-1])

    def release(self) -> None:
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None


# ---------------------------------------------------------------------------
#  ffmpeg-pipe tonemap decoder (HDR path)
# ---------------------------------------------------------------------------


# Filter chain for PQ/HLG → SDR Rec.709. ``zscale`` is the
# colorimetrically correct path; ``tonemap=hable`` is the most
# forgiving operator for highlight roll-off across HDR content. nominal
# peak luminance ``npl=100`` matches a standard SDR display target.
_HDR_TONEMAP_FILTER = (
    "zscale=t=linear:npl=100,format=gbrpf32le,"
    "zscale=p=bt709,tonemap=hable,"
    "zscale=t=bt709:m=bt709:r=tv,format=rgb24"
)


class FFmpegToneMapDecoder(VideoDecoder):
    """Spawns ffmpeg as a subprocess and reads raw RGB frames from
    its stdout. The filter chain tone-maps PQ/HLG into Rec.709 SDR so
    the existing 8-bit RGB preview pipeline stays unchanged.

    Frame size is probed up-front via a brief ``ffmpeg -i`` parse
    (the same trick used by ``app.hdr_probe``). For seeks we restart
    the subprocess with ``-ss`` since pipe-mode ffmpeg can't rewind.
    """

    def __init__(
        self,
        path: Path | str,
        *,
        fallback_fps: float = 30.0,
    ) -> None:
        self._path = Path(path)
        self._proc: Optional[subprocess.Popen] = None
        self._next_seek: Optional[int] = None
        self._last_read_idx: int = -2
        self._fallback_fps = float(fallback_fps)

    def open(self) -> bool:
        if not _probe_video_dimensions(self._path, self):
            return False
        self._spawn(at_frame=0)
        return self._proc is not None

    def seek_to_frame(self, idx: int) -> None:
        self._next_seek = max(0, int(idx))

    def read_rgb(self) -> Optional[np.ndarray]:
        if self._next_seek is not None and self._next_seek != self._last_read_idx + 1:
            # Real seek — restart the pipe. ffmpeg's -ss before -i is
            # a fast keyframe seek; the resulting pipe starts at the
            # nearest keyframe ≤ requested time, so for frame-accurate
            # we'd need -ss after -i. Phase 1 picks fast over precise.
            self._spawn(at_frame=int(self._next_seek))
        target = self._next_seek if self._next_seek is not None else self._last_read_idx + 1
        self._next_seek = None
        if self._proc is None or self._proc.stdout is None:
            return None
        w, h = self.frame_size
        if w <= 0 or h <= 0:
            return None
        bytes_per_frame = w * h * 3
        try:
            buf = self._proc.stdout.read(bytes_per_frame)
        except Exception:
            return None
        if not buf or len(buf) < bytes_per_frame:
            return None
        self._last_read_idx = target
        arr = np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 3))
        # Returned array shares memory with ``buf`` which the GC may
        # reclaim — ``copy()`` so callers can mutate / outlive this
        # frame's read cycle.
        return arr.copy()

    def release(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            if proc.stdout is not None:
                proc.stdout.close()
        except Exception:
            pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    # ---- internals ----

    def _spawn(self, *, at_frame: int) -> None:
        self.release()
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except Exception:
            return
        seek_seconds = max(0.0, at_frame / max(self.fps, self._fallback_fps))
        # ``-ss SECS`` before ``-i`` is the cheap keyframe seek.
        # ``-an`` drops audio so the pipe carries only video bytes.
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-ss", f"{seek_seconds:.3f}",
            "-i", str(self._path),
            "-vf", _HDR_TONEMAP_FILTER,
            "-pix_fmt", "rgb24",
            "-f", "rawvideo",
            "-an",
            "-",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                bufsize=0,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                ),
            )
            # If we restarted at a non-zero seek, the next ``read_rgb``
            # call should NOT seek again — it just consumes from the
            # fresh pipe.
            self._last_read_idx = at_frame - 1
        except Exception:
            self._proc = None


def _probe_video_dimensions(path: Path, decoder: FFmpegToneMapDecoder) -> bool:
    """Populate ``decoder.fps``, ``decoder.total_frames``, and
    ``decoder.frame_size`` from an ``ffmpeg -i`` parse. Returns False
    when nothing usable was found — the caller treats that as "open
    failed" and fall back to the SDR path.
    """
    import re
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        ffmpeg = get_ffmpeg_exe()
    except Exception:
        return False
    try:
        cp = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=(
                subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            ),
        )
    except Exception:
        return False
    text = (cp.stderr or "") + "\n" + (cp.stdout or "")
    # Width × Height.
    m_size = re.search(r"\b(\d{2,5})x(\d{2,5})\b", text)
    if not m_size:
        return False
    w = int(m_size.group(1))
    h = int(m_size.group(2))
    decoder.frame_size = (w, h)
    # FPS (e.g. "60 fps" or "59.94 fps").
    m_fps = re.search(r",\s*([\d.]+)\s*fps", text)
    decoder.fps = float(m_fps.group(1)) if m_fps else 30.0
    # Duration → estimate total_frames.
    m_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", text)
    if m_dur:
        h_, m_, s_ = m_dur.groups()
        total_s = int(h_) * 3600 + int(m_) * 60 + float(s_)
        decoder.total_frames = int(total_s * decoder.fps)
    return True


# ---------------------------------------------------------------------------
#  Background prefetch wrapper
# ---------------------------------------------------------------------------


class PrefetchDecoder(VideoDecoder):
    """Background-thread frame prefetch. Drop-in VideoDecoder wrapper.

    Decodes BUFFER_SIZE frames ahead in a daemon thread so the main
    thread's read_rgb() returns from a pre-populated cache instead of
    blocking on the codec — this is the primary playback speedup.

    Optional ``preview_height``: frames taller than this value are
    downscaled in the bg thread so main-thread colour-grading numpy
    operations run proportionally faster.  Pass 0 to disable scaling.

    Thread model: the bg thread owns the inner decoder exclusively.
    The main thread only accesses self._buf (under self._cond) and
    the _seek_to / _stopped flags.
    """

    BUFFER_SIZE: int = 12       # frames ahead to keep ready
    READ_TIMEOUT: float = 0.060 # main-thread read_rgb() ceiling (seconds)

    def __init__(self, inner: VideoDecoder, preview_height: int = 0) -> None:
        self._inner = inner
        self.fps = inner.fps
        self.total_frames = inner.total_frames
        self.frame_size = inner.frame_size
        self._preview_height = max(0, int(preview_height))

        self._buf: deque = deque()
        self._cond = threading.Condition()
        self._next_bg: int = 0           # next frame the bg thread will decode
        self._next_fg: int = 0           # next frame the main thread expects
        self._seek_to: Optional[int] = 0 # initial seek to frame 0
        self._eof: bool = False
        self._stopped: bool = False

        self._thread = threading.Thread(
            target=self._run, daemon=True,
            name=f"PfxDec-{id(self):x}",
        )
        self._thread.start()

    # ── VideoDecoder API (main thread) ────────────────────────────────────────

    def seek_to_frame(self, idx: int) -> None:
        idx = max(0, int(idx))
        with self._cond:
            if idx == self._next_fg and self._seek_to is None and not self._eof:
                return  # sequential advance — bg thread is already ahead
            self._buf.clear()
            self._eof = False
            self._next_fg = idx
            self._seek_to = idx
            self._cond.notify_all()

    def read_rgb(self) -> Optional[np.ndarray]:
        deadline = time.monotonic() + self.READ_TIMEOUT
        with self._cond:
            while True:
                if self._buf:
                    rgb = self._buf.popleft()
                    self._next_fg += 1
                    self._cond.notify_all()
                    return rgb
                if self._stopped or self._eof:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(timeout=min(remaining, 0.005))

    def release(self) -> None:
        with self._cond:
            self._stopped = True
            self._cond.notify_all()
        # Short timeout then release the inner decoder so any blocking
        # read_rgb() call in the bg thread returns None quickly.
        self._thread.join(timeout=0.5)
        self._inner.release()

    # ── background decode loop ────────────────────────────────────────────────

    def _run(self) -> None:
        while True:
            # Phase 1: wait until there is room in the buffer.
            need_seek: Optional[int] = None
            with self._cond:
                while (
                    not self._stopped
                    and self._seek_to is None
                    and (len(self._buf) >= self.BUFFER_SIZE or self._eof)
                ):
                    self._cond.wait(timeout=0.1)
                if self._stopped:
                    return
                if self._seek_to is not None:
                    need_seek = self._seek_to
                    self._next_bg = self._seek_to
                    self._seek_to = None
                    self._eof = False

            # Phase 2: seek if requested (fast flag-set, outside lock).
            if need_seek is not None:
                self._inner.seek_to_frame(need_seek)

            # Phase 3: decode (expensive — GIL released inside cv2/ffmpeg).
            rgb = self._inner.read_rgb()

            # Phase 4: optional preview downscale (outside lock).
            if rgb is not None and self._preview_height > 0:
                h, w = rgb.shape[:2]
                if h > self._preview_height:
                    try:
                        import cv2
                        scale = self._preview_height / h
                        rgb = cv2.resize(
                            rgb,
                            (max(1, int(w * scale)), self._preview_height),
                            interpolation=cv2.INTER_LINEAR,
                        )
                    except Exception:
                        pass

            # Phase 5: commit result to buffer.
            with self._cond:
                if self._stopped:
                    return
                if self._seek_to is not None:
                    pass  # new seek arrived while we were decoding — discard stale frame
                elif rgb is None:
                    self._eof = True
                    self._cond.notify_all()
                else:
                    self._buf.append(rgb)
                    self._next_bg += 1
                    self._cond.notify_all()


# ---------------------------------------------------------------------------
#  Factory
# ---------------------------------------------------------------------------


def open_decoder(
    path: Path | str,
    hdr_info=None,
    preview_height: int = 720,
) -> Optional[VideoDecoder]:
    """Pick a decoder based on ``hdr_info`` and wrap it in
    ``PrefetchDecoder`` for background frame prefetch.

    ``preview_height``: frames taller than this are downscaled in the
    bg thread before entering the buffer. Pass 0 to disable scaling.
    """
    is_hdr = bool(getattr(hdr_info, "is_hdr", False))
    if is_hdr:
        d = FFmpegToneMapDecoder(path)
        if d.open():
            return PrefetchDecoder(d, preview_height=preview_height)
        # ffmpeg path failed — fall back to cv2 (preview will look
        # washed-out but the file at least loads).
        d.release()
    cv = CV2Decoder(path)
    if cv.open():
        return PrefetchDecoder(cv, preview_height=preview_height)
    return None
