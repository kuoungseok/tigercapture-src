"""Background worker for Motion Designer mask tracking analysis."""
from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.motion_designer.tracking_provider import (
    MotionTrackingCancelled,
    MotionTrackingRequest,
    generate_tracking_cache,
)


class MotionTrackingWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str, str)
    progress = Signal(str, int, int)

    def __init__(self, mask_id: str, request: MotionTrackingRequest) -> None:
        super().__init__()
        self.mask_id = str(mask_id)
        self.request = request
        self._cancelled = Event()

    @Slot()
    def run(self) -> None:
        try:
            cache = generate_tracking_cache(
                self.request,
                progress=lambda done, total: self.progress.emit(self.mask_id, done, total),
                cancelled=self._cancelled.is_set,
            )
        except MotionTrackingCancelled:
            self.failed.emit(self.mask_id, "Tracking cancelled")
        except Exception as exc:
            self.failed.emit(self.mask_id, str(exc))
        else:
            self.completed.emit(self.mask_id, cache.to_dict())

    @Slot()
    def cancel(self) -> None:
        self._cancelled.set()


class MotionFaceTrackingWorker(QObject):
    completed = Signal(str, object)
    failed = Signal(str, str)
    progress = Signal(str, int, int)

    def __init__(self, job_id: str, video_path: str) -> None:
        super().__init__()
        self.job_id = str(job_id)
        self.video_path = str(video_path)
        self._cancelled = Event()

    @Slot()
    def run(self) -> None:
        try:
            if self._cancelled.is_set():
                raise MotionTrackingCancelled("motion tracking was cancelled")
            from app.motion_designer.tracking_workflow import (
                face_tracking_cache_from_video,
            )

            self.progress.emit(self.job_id, 0, 1)
            cache = face_tracking_cache_from_video(self.video_path)
            if self._cancelled.is_set():
                raise MotionTrackingCancelled("motion tracking was cancelled")
        except MotionTrackingCancelled:
            self.failed.emit(self.job_id, "Tracking cancelled")
        except Exception as exc:
            self.failed.emit(self.job_id, str(exc))
        else:
            self.progress.emit(self.job_id, 1, 1)
            self.completed.emit(self.job_id, cache.to_dict())

    @Slot()
    def cancel(self) -> None:
        self._cancelled.set()
