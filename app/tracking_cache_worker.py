from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal


class ObjectTrackingCacheWorker(QThread):
    """Pre-warm BitmapMask tracker caches on a background thread.

    The worker intentionally reuses ``BitmapMask.evaluate()`` instead of
    implementing a second tracker path. That keeps preview, export, saved
    project state, and pre-warmed cache entries on the same bbox format.
    """

    progress = Signal(int, int)       # current frame, total frames
    ready = Signal(object, object)    # tracking_cache_bboxes, failed_frames
    failed = Signal(str)

    def __init__(
        self,
        source_path: Path | str,
        mask_data: dict,
        *,
        start_frame: int = 0,
        max_frames: int = 600,
    ) -> None:
        super().__init__()
        self._source_path = Path(source_path)
        self._mask_data = dict(mask_data or {})
        self._start_frame = max(0, int(start_frame))
        self._max_frames = max(1, int(max_frames))

    def run(self) -> None:
        try:
            import cv2

            from app.node_mask import BitmapMask

            cap = cv2.VideoCapture(str(self._source_path))
            if not cap.isOpened():
                self.failed.emit("source video could not be opened")
                return
            try:
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                start = min(self._start_frame, max(0, total_frames - 1)) if total_frames > 0 else self._start_frame
                end = start + self._max_frames
                if total_frames > 0:
                    end = min(end, total_frames)
                cap.set(cv2.CAP_PROP_POS_FRAMES, start)

                mask = BitmapMask.from_dict(self._mask_data)
                mask.track_object = True
                mask.init_frame = start
                processed = 0
                frame_idx = start
                while frame_idx < end and not self.isInterruptionRequested():
                    ok, bgr = cap.read()
                    if not ok or bgr is None:
                        break
                    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                    mask.evaluate(rgb, frame_idx)
                    processed += 1
                    if processed == 1 or processed % 15 == 0:
                        self.progress.emit(frame_idx, max(start + 1, end))
                    frame_idx += 1

                if processed <= 0:
                    self.failed.emit("no frames decoded for tracking cache")
                    return
                self.ready.emit(
                    dict(mask.tracking_cache_bboxes),
                    set(mask.tracking_failed_frames),
                )
            finally:
                cap.release()
        except Exception as exc:
            self.failed.emit(str(exc) or repr(exc))
