from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from app.timeline_thumbnail_cache import (
    prepare_timeline_thumb_cache as _prepare_timeline_thumb_cache,
    timeline_thumb_cache_dir as _timeline_thumb_cache_dir,
)


THUMB_H = 48                  # thumbnail extract/display height in pixels
THUMB_SECONDS_PER_TILE = 3.0  # target seconds between thumbnails
MIN_THUMBS = 2
MAX_THUMBS = 96


def probe_video_duration_ms(path: Path) -> int:
    """Return duration of the video at ``path`` in milliseconds.
    Returns 0 if the file cannot be opened or has no duration information."""
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        from app.native_worker import native_media_probe

        probe = native_media_probe(path, ffmpeg_path=get_ffmpeg_exe())
        if probe is not None and probe.has_video and probe.duration_ms > 0:
            return int(probe.duration_ms)
    except Exception:
        pass
    try:
        import cv2 as _cv2
        cap = _cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return 0
        fps = float(cap.get(_cv2.CAP_PROP_FPS) or 0)
        total = int(cap.get(_cv2.CAP_PROP_FRAME_COUNT) or 0)
        cap.release()
        if fps > 0 and total > 0:
            return int(total / fps * 1000)
    except Exception:
        pass
    return 0


class ThumbnailExtractor(QThread):
    """Extracts evenly-spaced thumbnail frames for a track's video using
    OpenCV. The count is chosen dynamically from video duration so that one
    thumbnail roughly represents ``THUMB_SECONDS_PER_TILE`` of footage,
    clamped to [MIN_THUMBS, MAX_THUMBS].

    When ``clip_id`` is given the extractor is operating in per-clip mode:
    ``clip_thumb_ready`` and ``clip_count_determined`` are emitted instead
    of (or in addition to) the track-level signals, letting the editor store
    thumbnails on the individual ``VideoClip`` rather than the track.
    """

    count_determined = Signal(int, int)        # track_id, count
    thumb_ready = Signal(int, int, object)     # track_id, index, QImage
    finished_extracting = Signal(int)          # track_id
    # Per-clip variants (only emitted when clip_id is set)
    clip_count_determined = Signal(int, int, int)       # track_id, clip_id, count
    clip_thumb_ready = Signal(int, int, int, object)    # track_id, clip_id, idx, QImage

    def __init__(
        self,
        track_id: int,
        path: Path,
        thumb_height: int,
        clip_id: int = -1,
    ) -> None:
        super().__init__()
        self._track_id = track_id
        self._path = Path(path)
        self._thumb_h = max(16, int(thumb_height))
        self._stop = False
        self._clip_id = clip_id

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        cap = None
        cache_dir = None
        try:
            try:
                cache_dir = _timeline_thumb_cache_dir(self._path, self._thumb_h)
                if cache_dir is not None:
                    from imageio_ffmpeg import get_ffmpeg_exe

                    from app.native_worker import native_generate_timeline_thumbnails

                    files = native_generate_timeline_thumbnails(
                        self._path,
                        cache_dir,
                        ffmpeg_path=get_ffmpeg_exe(),
                        thumb_h=self._thumb_h,
                        min_thumbs=MIN_THUMBS,
                        max_thumbs=MAX_THUMBS,
                        seconds_per_tile=THUMB_SECONDS_PER_TILE,
                    )
                    if files:
                        images: list[QImage] = []
                        for file_path in files:
                            if self._stop:
                                return
                            image = QImage(str(file_path))
                            if image.isNull():
                                images = []
                                break
                            images.append(image)
                        if images:
                            count = len(images)
                            _prepare_timeline_thumb_cache(self._path, count, self._thumb_h)
                            self.count_determined.emit(self._track_id, count)
                            if self._clip_id >= 0:
                                self.clip_count_determined.emit(
                                    self._track_id, self._clip_id, count
                                )
                            for i, image in enumerate(images):
                                if self._stop:
                                    return
                                self.thumb_ready.emit(self._track_id, i, image)
                                if self._clip_id >= 0:
                                    self.clip_thumb_ready.emit(
                                        self._track_id, self._clip_id, i, image
                                    )
                            return
            except Exception:
                pass

            if cache_dir is not None:
                files = sorted(cache_dir.glob("[0-9][0-9][0-9][0-9].png"))
                if len(files) >= MIN_THUMBS:
                    images: list[QImage] = []
                    for file_path in files[:MAX_THUMBS]:
                        if self._stop:
                            return
                        image = QImage(str(file_path))
                        if image.isNull():
                            images = []
                            break
                        images.append(image)
                    if images:
                        count = len(images)
                        _prepare_timeline_thumb_cache(self._path, count, self._thumb_h)
                        self.count_determined.emit(self._track_id, count)
                        if self._clip_id >= 0:
                            self.clip_count_determined.emit(
                                self._track_id, self._clip_id, count
                            )
                        for i, image in enumerate(images):
                            if self._stop:
                                return
                            self.thumb_ready.emit(self._track_id, i, image)
                            if self._clip_id >= 0:
                                self.clip_thumb_ready.emit(
                                    self._track_id, self._clip_id, i, image
                                )
                        return

            import cv2
            import numpy as np

            cap = cv2.VideoCapture(str(self._path))
            if not cap.isOpened():
                return
            fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if total_frames <= 0:
                return
            duration_s = total_frames / fps if fps > 0 else 0
            count = max(
                MIN_THUMBS,
                min(MAX_THUMBS, int(round(duration_s / THUMB_SECONDS_PER_TILE))),
            )
            self.count_determined.emit(self._track_id, count)
            if self._clip_id >= 0:
                self.clip_count_determined.emit(self._track_id, self._clip_id, count)

            for i in range(count):
                if self._stop:
                    return
                frame_idx = min(
                    total_frames - 1,
                    int((i + 0.5) * total_frames / count),
                )
                target_ms = (frame_idx / max(fps, 0.001)) * 1000.0
                cap.set(cv2.CAP_PROP_POS_MSEC, target_ms)
                ret, bgr = cap.read()
                if not ret or bgr is None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                    ret, bgr = cap.read()
                if not ret or bgr is None:
                    continue

                h, w = bgr.shape[:2]
                if h != self._thumb_h:
                    new_w = max(1, int(round(w * self._thumb_h / h)))
                    bgr = cv2.resize(
                        bgr, (new_w, self._thumb_h), interpolation=cv2.INTER_AREA
                    )
                    h, w = bgr.shape[:2]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                contig = np.ascontiguousarray(rgb)
                qimg = QImage(
                    contig.data, w, h, contig.strides[0], QImage.Format.Format_RGB888
                ).copy()
                self.thumb_ready.emit(self._track_id, i, qimg)
                if self._clip_id >= 0:
                    self.clip_thumb_ready.emit(self._track_id, self._clip_id, i, qimg)
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            self.finished_extracting.emit(self._track_id)
