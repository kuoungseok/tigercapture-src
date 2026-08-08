from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.motion_designer.export_pipeline import MotionProfileExporter
from app.motion_designer.schema import MotionComposition


class MotionExportWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, composition: MotionComposition, request: dict) -> None:
        super().__init__()
        self.composition = MotionComposition.from_dict(composition.to_dict())
        self.request = dict(request)
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        try:
            result = MotionProfileExporter(cancel_check=self._cancelled.is_set).export(
                self.composition,
                str(self.request["profile_id"]),
                str(self.request["output_path"]),
                fps=float(self.request.get("fps") or self.composition.fps),
                time_ms=float(self.request.get("time_ms") or 0.0),
                resume=bool(self.request.get("resume", False)),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.completed.emit(result)


__all__ = ["MotionExportWorker"]
