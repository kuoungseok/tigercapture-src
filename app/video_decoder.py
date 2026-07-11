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
import json
import subprocess
import sys
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Optional

import numpy as np

from app.subprocess_utils import hidden_subprocess_kwargs


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


def _cv2_hw_decode_params(cv2_module) -> list[int]:
    """Return OpenCV FFMPEG open params for hardware decode when available."""
    disabled = os.environ.get("TIGERCAPTURE_DISABLE_HW_DECODE", "").strip().lower()
    if disabled in {"1", "true", "yes", "on"}:
        return []
    enabled = os.environ.get("TIGERCAPTURE_ENABLE_HW_DECODE", "").strip().lower()
    if enabled not in {"1", "true", "yes", "on"}:
        return []
    prop = getattr(cv2_module, "CAP_PROP_HW_ACCELERATION", None)
    accel = getattr(cv2_module, "VIDEO_ACCELERATION_ANY", None)
    if prop is None or accel is None:
        return []
    params = [int(prop), int(accel)]
    raw_device = os.environ.get("TIGERCAPTURE_HW_DEVICE", "").strip()
    device_prop = getattr(cv2_module, "CAP_PROP_HW_DEVICE", None)
    if raw_device and device_prop is not None:
        try:
            params.extend([int(device_prop), int(raw_device)])
        except Exception:
            pass
    return params


def _cv2_forward_seek_window() -> int:
    """Maximum forward frame gap to satisfy by reading instead of seeking.

    For inter-frame codecs, a small forward ``CAP_PROP_POS_FRAMES`` seek can be
    slower than decoding and discarding the intervening frames. Timeline scrub
    and QA samples often jump 10-40 frames forward, so keep this conservative
    and configurable.
    """
    raw = os.environ.get("TIGERCAPTURE_CV2_FORWARD_SEEK_WINDOW", "0").strip()
    try:
        return max(0, min(240, int(raw)))
    except Exception:
        return 0


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
        cap = None
        params = _cv2_hw_decode_params(cv2)
        if params:
            try:
                cap_hw = cv2.VideoCapture(str(self._path), cv2.CAP_FFMPEG, params)
            except Exception:
                cap_hw = None
            if cap_hw is not None and cap_hw.isOpened():
                cap = cap_hw
            elif cap_hw is not None:
                cap_hw.release()
        # Attempt hardware-accelerated decode first (DXVA2/NVDEC/VideoToolbox/VAAPI).
        if cap is None:
            cap_hw = cv2.VideoCapture(str(self._path), cv2.CAP_FFMPEG)
            try:
                cap_hw.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
            except Exception:
                pass
            if cap_hw.isOpened():
                cap = cap_hw
            else:
                cap_hw.release()
        if cap is None:
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
        expected_next = self._last_read_idx + 1
        if target > expected_next:
            gap = target - expected_next
            if gap <= _cv2_forward_seek_window():
                for _ in range(gap):
                    ret, _discard = self._cap.read()
                    if not ret:
                        self._next_seek = None
                        return None
                    self._last_read_idx += 1
            else:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, target)
        elif target != expected_next:
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
                **hidden_subprocess_kwargs(),
            )
            # If we restarted at a non-zero seek, the next ``read_rgb``
            # call should NOT seek again — it just consumes from the
            # fresh pipe.
            self._last_read_idx = at_frame - 1
        except Exception:
            self._proc = None


class FFmpegFrameServerDecoder(VideoDecoder):
    """Process-level RGB preview frame server backed by an FFmpeg pipe."""

    def __init__(
        self,
        path: Path | str,
        *,
        output_height: int | None = None,
        fallback_fps: float = 30.0,
    ) -> None:
        self._path = Path(path)
        self._proc: Optional[subprocess.Popen] = None
        self._next_seek: Optional[int] = None
        self._last_read_idx: int = -2
        self._fallback_fps = float(fallback_fps)
        self._requested_height = output_height
        self._source_frame_size: tuple[int, int] = (0, 0)

    def open(self) -> bool:
        if not _probe_video_dimensions(self._path, self):
            return False
        self._source_frame_size = self.frame_size
        self.frame_size = self._resolve_output_size()
        self._spawn(at_frame=0)
        return self._proc is not None

    def seek_to_frame(self, idx: int) -> None:
        self._next_seek = max(0, int(idx))

    def read_rgb(self) -> Optional[np.ndarray]:
        if self._next_seek is not None and self._next_seek != self._last_read_idx + 1:
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
        return np.frombuffer(buf, dtype=np.uint8).reshape((h, w, 3)).copy()

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

    def _resolve_output_size(self) -> tuple[int, int]:
        src_w, src_h = self._source_frame_size
        src_w = int(src_w or 0)
        src_h = int(src_h or 0)
        if src_w <= 0 or src_h <= 0:
            return (0, 0)
        if self._requested_height is None:
            target_h = 540 if src_h >= 2160 else 720
        else:
            target_h = int(self._requested_height)
        if target_h <= 0 or src_h <= target_h:
            return (src_w, src_h)
        scale = target_h / float(src_h)
        target_w = max(2, int(round(src_w * scale)))
        if target_w % 2:
            target_w += 1
        return (target_w, max(1, target_h))

    def _spawn(self, *, at_frame: int) -> None:
        self.release()
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except Exception:
            return
        seek_seconds = max(0.0, at_frame / max(self.fps, self._fallback_fps))
        src_w, src_h = self._source_frame_size
        out_w, out_h = self.frame_size
        vf = "format=rgb24"
        if src_h > 0 and out_h > 0 and out_h < src_h:
            vf = f"scale={out_w}:{out_h}:flags=bilinear,format=rgb24"
        cmd = [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-ss", f"{seek_seconds:.3f}",
            "-i", str(self._path),
            "-vf", vf,
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
                **hidden_subprocess_kwargs(),
            )
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
            **hidden_subprocess_kwargs(),
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

    BUFFER_SIZE: int = 24       # frames ahead to keep ready
    READ_TIMEOUT: float = 0.080 # main-thread read_rgb() ceiling (seconds)

    def __init__(self, inner: VideoDecoder, preview_height: int = 0) -> None:
        self._inner = inner
        self.fps = inner.fps
        self.total_frames = inner.total_frames
        self.frame_size = inner.frame_size
        self._preview_height = max(0, int(preview_height))
        try:
            self._buffer_size = max(2, min(90, int(os.environ.get("TIGERCAPTURE_PREFETCH_FRAMES", str(self.BUFFER_SIZE)))))
        except Exception:
            self._buffer_size = self.BUFFER_SIZE
        try:
            self._read_timeout = max(0.005, min(0.250, float(os.environ.get("TIGERCAPTURE_PREFETCH_READ_TIMEOUT", str(self.READ_TIMEOUT)))))
        except Exception:
            self._read_timeout = self.READ_TIMEOUT
        try:
            self._forward_seek_window = max(
                0,
                min(240, int(os.environ.get("TIGERCAPTURE_PREFETCH_FORWARD_SEEK_WINDOW", "12"))),
            )
        except Exception:
            self._forward_seek_window = 0
        try:
            self._release_join_timeout = max(
                0.0,
                min(5.0, float(os.environ.get("TIGERCAPTURE_PREFETCH_RELEASE_JOIN_TIMEOUT", "0.5"))),
            )
        except Exception:
            self._release_join_timeout = 0.5

        self._buf: deque[tuple[int, np.ndarray]] = deque()
        self._cond = threading.Condition()
        self._release_lock = threading.Lock()
        self._next_bg: int = 0           # next frame the bg thread will decode
        self._next_fg: int = 0           # next frame the main thread expects
        self._seek_to: Optional[int] = 0 # initial seek to frame 0
        self._eof: bool = False
        self._stopped: bool = False
        self._inner_released: bool = False

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
            while self._buf and self._buf[0][0] < idx:
                self._buf.popleft()
            if self._buf and self._buf[0][0] == idx:
                self._eof = False
                self._next_fg = idx
                self._seek_to = None
                self._cond.notify_all()
                return
            if (
                self._forward_seek_window > 0
                and self._seek_to is None
                and not self._eof
                and idx >= self._next_bg
                and (idx - self._next_bg) <= self._forward_seek_window
            ):
                self._next_fg = idx
                self._cond.notify_all()
                return
            self._buf.clear()
            self._eof = False
            self._next_fg = idx
            self._seek_to = idx
            self._cond.notify_all()

    def read_rgb(self) -> Optional[np.ndarray]:
        deadline = time.monotonic() + self._read_timeout
        with self._cond:
            while True:
                if self._buf:
                    frame_idx, rgb = self._buf[0]
                    if frame_idx < self._next_fg:
                        self._buf.popleft()
                        continue
                    if frame_idx == self._next_fg:
                        self._buf.popleft()
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
            self._buf.clear()
            self._cond.notify_all()
        if self._thread is threading.current_thread():
            self._release_inner_once()
            return
        self._thread.join(timeout=self._release_join_timeout)
        if not self._thread.is_alive():
            self._release_inner_once()

    def _release_inner_once(self) -> None:
        with self._release_lock:
            if self._inner_released:
                return
            self._inner_released = True
        try:
            self._inner.release()
        except Exception:
            pass

    # ── background decode loop ────────────────────────────────────────────────

    def _run(self) -> None:
        while True:
            # Phase 1: wait until there is room in the buffer.
            need_seek: Optional[int] = None
            with self._cond:
                while (
                    not self._stopped
                    and self._seek_to is None
                    and (len(self._buf) >= self._buffer_size or self._eof)
                ):
                    self._cond.wait(timeout=0.1)
                if self._stopped:
                    self._release_inner_once()
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
            try:
                rgb = self._inner.read_rgb()
            except Exception:
                with self._cond:
                    self._eof = True
                    self._cond.notify_all()
                self._release_inner_once()
                return

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
                    self._release_inner_once()
                    return
                if self._seek_to is not None:
                    pass  # new seek arrived while we were decoding — discard stale frame
                elif rgb is None:
                    self._eof = True
                    self._cond.notify_all()
                else:
                    self._buf.append((self._next_bg, rgb))
                    self._next_bg += 1
                    self._cond.notify_all()


class FrameCacheDecoder(VideoDecoder):
    """Small LRU cache for preview scrubbing and repeated frame requests."""

    def __init__(self, inner: VideoDecoder, limit: int = 24) -> None:
        self._inner = inner
        self.fps = inner.fps
        self.total_frames = inner.total_frames
        self.frame_size = inner.frame_size
        self._limit = max(0, int(limit))
        self._cache: "OrderedDict[int, np.ndarray]" = OrderedDict()
        self._next_seek: Optional[int] = 0
        self._last_read_idx: int = -1
        self._inner_aligned: bool = False

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def open(self) -> bool:
        return True

    def seek_to_frame(self, idx: int) -> None:
        self._next_seek = max(0, int(idx))

    def read_rgb(self) -> Optional[np.ndarray]:
        target = self._next_seek if self._next_seek is not None else self._last_read_idx + 1
        self._next_seek = None
        cached = self._cache.get(target)
        if cached is not None:
            self._cache.move_to_end(target)
            self._last_read_idx = target
            self._inner_aligned = False
            return cached.copy()
        if not self._inner_aligned or target != self._last_read_idx + 1:
            self._inner.seek_to_frame(target)
        rgb = self._inner.read_rgb()
        if rgb is None:
            return None
        self._last_read_idx = target
        self._inner_aligned = True
        if self._limit > 0:
            self._cache[target] = np.ascontiguousarray(rgb).copy()
            self._cache.move_to_end(target)
            while len(self._cache) > self._limit:
                self._cache.popitem(last=False)
        return rgb

    def release(self) -> None:
        self._cache.clear()
        self._inner.release()


# ---------------------------------------------------------------------------
#  Factory
# ---------------------------------------------------------------------------


_DECODER_CHOICE_CACHE: dict[str, dict] | None = None


def _preview_decoder_auto_enabled() -> bool:
    mode = os.environ.get("TIGERCAPTURE_PREVIEW_DECODER_AUTO", "").strip().lower()
    frame_server = os.environ.get("TIGERCAPTURE_PREVIEW_FRAME_SERVER", "").strip().lower()
    return mode in {"1", "true", "yes", "on", "auto"} or frame_server == "auto"


def _preview_performance_policy_enabled() -> bool:
    disabled = os.environ.get("TIGERCAPTURE_DISABLE_PREVIEW_PERFORMANCE_POLICY", "").strip().lower()
    return disabled not in {"1", "true", "yes", "on"}


def _probe_preview_source_metadata(path: Path) -> dict[str, object]:
    """Return cheap metadata for preview policy decisions.

    Prefer OpenCV metadata because it is already part of the preview stack and
    avoids spawning FFmpeg for every ordinary source.  Failures simply return an
    empty mapping; the decoder then falls back to legacy behavior.
    """
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if not cap or not cap.isOpened():
            return {}
        try:
            return {
                "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
                "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
                "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0),
            }
        finally:
            try:
                cap.release()
            except Exception:
                pass
    except Exception:
        return {}


def _preview_performance_policy(
    path: Path,
    *,
    requested_preview_height: int | None = None,
) -> dict[str, object]:
    if not _preview_performance_policy_enabled():
        return {}
    try:
        from app.preview_performance_policy import preview_performance_policy_from_probe

        return preview_performance_policy_from_probe(
            _probe_preview_source_metadata(path),
            path=path,
            requested_preview_height=requested_preview_height,
        )
    except Exception:
        return {}


def _effective_preview_height_request(
    path: Path,
    requested_preview_height: int | None,
    policy: dict[str, object] | None,
) -> int | None:
    if requested_preview_height is not None:
        return requested_preview_height
    if not isinstance(policy, dict):
        return None
    try:
        height = int(policy.get("preview_height") or 0)
    except Exception:
        height = 0
    return height if height > 0 else None


def _decoder_choice_cache_path() -> Path | None:
    raw = os.environ.get("TIGERCAPTURE_DECODER_CHOICE_CACHE", "").strip()
    if raw:
        return Path(raw)
    try:
        return Path.home() / "Videos" / "TigerCapture" / ".cache" / "decoder_choices.json"
    except Exception:
        return None


def _load_decoder_choice_cache() -> dict[str, dict]:
    global _DECODER_CHOICE_CACHE
    if _DECODER_CHOICE_CACHE is not None:
        return _DECODER_CHOICE_CACHE
    path = _decoder_choice_cache_path()
    if path is None or not path.exists():
        _DECODER_CHOICE_CACHE = {}
        return _DECODER_CHOICE_CACHE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _DECODER_CHOICE_CACHE = data if isinstance(data, dict) else {}
    except Exception:
        _DECODER_CHOICE_CACHE = {}
    return _DECODER_CHOICE_CACHE


def _save_decoder_choice_cache() -> None:
    cache = _load_decoder_choice_cache()
    path = _decoder_choice_cache_path()
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _decoder_choice_cache_key(path: Path, preview_height: int | None) -> str | None:
    try:
        stat = path.stat()
        resolved = str(path.resolve()).lower()
        margin = os.environ.get("TIGERCAPTURE_PREVIEW_DECODER_AUTO_MARGIN", "0.85").strip()
        bench_frames = os.environ.get("TIGERCAPTURE_PREVIEW_DECODER_BENCH_FRAMES", "3").strip()
        return "|".join([
            "auto-v1",
            resolved,
            str(int(stat.st_size)),
            str(int(stat.st_mtime_ns)),
            str(preview_height if preview_height is not None else "auto"),
            str(margin or "0.85"),
            str(bench_frames or "3"),
            sys.platform,
        ])
    except Exception:
        return None


def _decoder_auto_log(message: str) -> None:
    enabled = os.environ.get("TIGERCAPTURE_DECODER_AUTO_LOG", "").strip().lower()
    if enabled in {"1", "true", "yes", "on"}:
        print(f"[decoder-auto] {message}", file=sys.stderr, flush=True)


def _decoder_benchmark_frames(decoder: VideoDecoder) -> list[int]:
    total = max(0, int(getattr(decoder, "total_frames", 0) or 0))
    fps = max(1.0, float(getattr(decoder, "fps", 30.0) or 30.0))
    if total <= 1:
        frames = [0]
    else:
        frames = [
            0,
            min(total - 1, max(1, int(round(fps)))),
            min(total - 1, max(1, total // 2)),
        ]
    try:
        limit = max(1, min(6, int(os.environ.get("TIGERCAPTURE_PREVIEW_DECODER_BENCH_FRAMES", "3"))))
    except Exception:
        limit = 3
    unique: list[int] = []
    for idx in frames:
        idx = int(max(0, idx))
        if idx not in unique:
            unique.append(idx)
        if len(unique) >= limit:
            break
    return unique or [0]


def _benchmark_decoder_candidate(decoder: VideoDecoder) -> dict[str, object]:
    opened = False
    open_start = time.perf_counter()
    try:
        opened = bool(decoder.open())
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__, "open_ms": 0.0}
    open_ms = (time.perf_counter() - open_start) * 1000.0
    if not opened:
        try:
            decoder.release()
        except Exception:
            pass
        return {"ok": False, "error": "open_failed", "open_ms": round(open_ms, 2)}

    frames = _decoder_benchmark_frames(decoder)
    read_rows: list[float] = []
    try:
        for frame_idx in frames:
            start = time.perf_counter()
            decoder.seek_to_frame(frame_idx)
            rgb = decoder.read_rgb()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            if rgb is None:
                return {
                    "ok": False,
                    "error": "read_failed",
                    "open_ms": round(open_ms, 2),
                    "frames": frames,
                }
            read_rows.append(elapsed_ms)
    except Exception as exc:
        return {
            "ok": False,
            "error": type(exc).__name__,
            "open_ms": round(open_ms, 2),
            "frames": frames,
        }
    finally:
        try:
            decoder.release()
        except Exception:
            pass

    avg_read_ms = sum(read_rows) / max(1, len(read_rows))
    total_ms = open_ms + sum(read_rows)
    return {
        "ok": True,
        "open_ms": round(open_ms, 2),
        "avg_read_ms": round(avg_read_ms, 2),
        "total_ms": round(total_ms, 2),
        "frames": frames,
    }


def _choose_preview_decoder_backend(
    path: Path,
    preview_height: int | None,
) -> str:
    """Return the fastest safe preview decoder backend for this source.

    The benchmark intentionally has a conservative bias: OpenCV remains the
    default unless the FFmpeg frame server wins by a meaningful margin. Local QA
    showed the frame server can be slower on random seeks, so auto mode should
    only switch when this exact source proves it.
    """
    key = _decoder_choice_cache_key(path, preview_height)
    cache = _load_decoder_choice_cache()
    if key:
        cached = cache.get(key)
        if isinstance(cached, dict):
            backend = str(cached.get("backend") or "")
            if backend in {"cv2", "ffmpeg_frame_server"}:
                return backend

    cv = _benchmark_decoder_candidate(CV2Decoder(path))
    fs = _benchmark_decoder_candidate(
        FFmpegFrameServerDecoder(path, output_height=preview_height)
    )

    backend = "cv2"
    cv_ok = bool(cv.get("ok"))
    fs_ok = bool(fs.get("ok"))
    if not cv_ok and fs_ok:
        backend = "ffmpeg_frame_server"
    elif cv_ok and fs_ok:
        cv_score = float(cv.get("total_ms", 999999.0) or 999999.0)
        fs_score = float(fs.get("total_ms", 999999.0) or 999999.0)
        try:
            margin = float(os.environ.get("TIGERCAPTURE_PREVIEW_DECODER_AUTO_MARGIN", "0.85"))
        except Exception:
            margin = 0.85
        margin = max(0.50, min(0.98, margin))
        if fs_score < cv_score * margin:
            backend = "ffmpeg_frame_server"

    if key:
        cache[key] = {
            "backend": backend,
            "created_at": int(time.time()),
            "cv2": cv,
            "ffmpeg_frame_server": fs,
        }
        _save_decoder_choice_cache()
    _decoder_auto_log(f"{path.name}: {backend} cv2={cv} ffmpeg={fs}")
    try:
        from app.loading_performance import record_loading_event

        record_loading_event(
            "decoder.auto",
            "benchmark",
            path=path,
            status="ready",
            detail=f"selected={backend}",
            metadata={
                "backend": backend,
                "preview_height": preview_height,
                "cv2": cv,
                "ffmpeg_frame_server": fs,
            },
        )
    except Exception:
        pass
    return backend


def _wrap_for_preview_prefetch(
    decoder: VideoDecoder,
    preview_height: int,
) -> VideoDecoder:
    required = ("fps", "total_frames", "frame_size", "seek_to_frame", "read_rgb")
    if not all(hasattr(decoder, name) for name in required):
        return decoder
    wrapped: VideoDecoder = PrefetchDecoder(decoder, preview_height=preview_height)
    disabled = os.environ.get("TIGERCAPTURE_DISABLE_FRAME_CACHE", "").strip().lower()
    if disabled in {"1", "true", "yes"}:
        return wrapped
    try:
        limit = int(os.environ.get("TIGERCAPTURE_FRAME_CACHE_LIMIT", "24"))
    except Exception:
        limit = 24
    return FrameCacheDecoder(wrapped, limit=limit)


def _preview_height_from_env() -> int | None:
    raw = os.environ.get("TIGERCAPTURE_PREVIEW_HEIGHT", "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except Exception:
        return None
    if value <= 0:
        return 0
    return max(240, min(2160, value))


def _frame_server_preview_height_hint(requested: int | None) -> int | None:
    """Return the scale height to hand to FFmpeg frame-server candidates.

    The OpenCV path can inspect the source after opening and then choose a
    source-aware preview height. The FFmpeg frame server needs its output size
    before it is benchmarked/opened, otherwise opt-in/auto runs may decode full
    source frames and make the comparison unfairly expensive.
    """
    if requested is not None:
        return max(0, int(requested))
    env_height = _preview_height_from_env()
    if env_height is not None:
        return env_height
    return 720


def _resolve_preview_height(decoder: VideoDecoder, requested: int | None) -> int:
    """Choose the frame height used by the preview prefetch buffer."""
    if requested is not None:
        return max(0, int(requested))
    env_height = _preview_height_from_env()
    if env_height is not None:
        return env_height
    _w, h = getattr(decoder, "frame_size", (0, 0)) or (0, 0)
    if int(h or 0) >= 2160:
        return 540
    return 720


def _preview_frame_server_enabled() -> bool:
    mode = os.environ.get("TIGERCAPTURE_PREVIEW_FRAME_SERVER", "").strip().lower()
    return mode in {"1", "true", "yes", "on", "ffmpeg"}


def _existing_preview_proxy(path: Path) -> Path | None:
    """Return a fresh sibling proxy path for preview decode, if available."""
    disabled = os.environ.get("TIGERCAPTURE_DISABLE_AUTO_PROXY", "").strip()
    if disabled in {"1", "true", "TRUE"}:
        return None
    if path.stem.endswith("_proxy"):
        return None
    proxy = path.parent / "proxies" / f"{path.stem}_proxy.mp4"
    try:
        if not proxy.is_file():
            return None
        if proxy.stat().st_mtime_ns < path.stat().st_mtime_ns:
            return None
        return proxy
    except Exception:
        return None


def open_decoder(
    path: Path | str,
    hdr_info=None,
    preview_height: int | None = None,
) -> Optional[VideoDecoder]:
    """Pick a decoder based on ``hdr_info`` and wrap it in
    ``PrefetchDecoder`` for background frame prefetch.

    ``preview_height``: frames taller than this are downscaled in the
    bg thread before entering the buffer. Pass 0 to disable scaling.
    """
    decode_path = Path(path)
    original_path = decode_path
    open_started = time.perf_counter()
    source_policy = _preview_performance_policy(
        decode_path,
        requested_preview_height=preview_height,
    )
    effective_preview_height = _effective_preview_height_request(
        decode_path,
        preview_height,
        source_policy,
    )

    def _record_open(backend: str, status: str = "ready", **metadata) -> None:
        try:
            from app.loading_performance import record_loading_event

            record_loading_event(
                "decoder.open",
                status,
                path=original_path,
                status=status,
                elapsed_ms=(time.perf_counter() - open_started) * 1000.0,
                detail=backend,
                metadata={
                    "backend": backend,
                    "decode_path": str(decode_path),
                    **metadata,
                },
            )
        except Exception:
            pass

    proxy_path = _existing_preview_proxy(decode_path)
    if proxy_path is not None:
        decode_path = proxy_path
        hdr_info = None
    is_hdr = bool(getattr(hdr_info, "is_hdr", False))
    if is_hdr:
        d = FFmpegToneMapDecoder(decode_path)
        if d.open():
            preview_height = _resolve_preview_height(d, effective_preview_height)
            _record_open(
                "ffmpeg_tonemap",
                proxy=bool(proxy_path),
                preview_height=preview_height,
                hdr=True,
                preview_policy=source_policy,
            )
            return _wrap_for_preview_prefetch(d, preview_height=preview_height)
        # ffmpeg path failed — fall back to cv2 (preview will look
        # washed-out but the file at least loads).
        d.release()
    frame_server_preview_height = _frame_server_preview_height_hint(effective_preview_height)
    policy_auto = bool(
        isinstance(source_policy, dict) and source_policy.get("decoder_auto")
    )
    if _preview_decoder_auto_enabled() or policy_auto:
        backend = _choose_preview_decoder_backend(decode_path, frame_server_preview_height)
        if backend == "ffmpeg_frame_server":
            fs = FFmpegFrameServerDecoder(decode_path, output_height=frame_server_preview_height)
            if fs.open():
                _record_open(
                    "ffmpeg_frame_server",
                    proxy=bool(proxy_path),
                    preview_height=frame_server_preview_height,
                    hdr=False,
                    auto=True,
                    policy_auto=policy_auto,
                    preview_policy=source_policy,
                )
                return _wrap_for_preview_prefetch(fs, preview_height=0)
            fs.release()
    if _preview_frame_server_enabled():
        fs = FFmpegFrameServerDecoder(decode_path, output_height=frame_server_preview_height)
        if fs.open():
            _record_open(
                "ffmpeg_frame_server",
                proxy=bool(proxy_path),
                preview_height=frame_server_preview_height,
                hdr=False,
                forced_frame_server=True,
                preview_policy=source_policy,
            )
            return _wrap_for_preview_prefetch(fs, preview_height=0)
        fs.release()
    cv = CV2Decoder(decode_path)
    if cv.open():
        preview_height = _resolve_preview_height(cv, effective_preview_height)
        _record_open(
            "cv2",
            proxy=bool(proxy_path),
            preview_height=preview_height,
            hdr=False,
            preview_policy=source_policy,
        )
        return _wrap_for_preview_prefetch(cv, preview_height=preview_height)
    _record_open(
        "open_failed",
        status="error",
        proxy=bool(proxy_path),
        preview_policy=source_policy,
    )
    return None
