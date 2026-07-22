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
