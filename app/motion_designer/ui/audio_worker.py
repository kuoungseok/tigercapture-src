"""Background audio analysis worker for Motion Designer."""
from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.motion_designer.audio_analysis import AudioAnalysisCancelled, analyze_audio


class MotionAudioAnalysisWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, source_path: str, options: dict | None = None) -> None:
        super().__init__()
        self.source_path = str(source_path)
        self.options = dict(options or {})
        self._cancelled = Event()

    @Slot()
    def run(self) -> None:
        try:
            cache = analyze_audio(self.source_path, cancelled=self._cancelled.is_set, **self.options)
        except AudioAnalysisCancelled:
            self.failed.emit("Analysis cancelled")
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(cache.to_dict())

    @Slot()
    def cancel(self) -> None:
        self._cancelled.set()


__all__ = ["MotionAudioAnalysisWorker"]
