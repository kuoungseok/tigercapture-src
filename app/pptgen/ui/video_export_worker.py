"""Background MP4 export worker for the PPT generator UI."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

from app.pptgen.schema import DeckSpec
from app.pptgen.timeline import PptTimeline
from app.pptgen.video_export import PptVideoExportCancelled, export_deck_video


class PptVideoExportWorker(QThread):
    progressChanged = Signal(object)
    resultReady = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        deck: DeckSpec,
        output_path: str | Path,
        *,
        timeline: PptTimeline | None = None,
        fps: int = 30,
        size: tuple[int, int] = (1280, 720),
        audio_path: str | Path | None = None,
        audio_bitrate: str = "192k",
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.deck = copy.deepcopy(deck)
        self.timeline = copy.deepcopy(timeline) if timeline is not None else None
        self.output_path = Path(output_path)
        self.fps = int(fps or 30)
        self.size = (int(size[0] or 1280), int(size[1] or 720))
        self.audio_path = str(audio_path or "")
        self.audio_bitrate = str(audio_bitrate or "192k")
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True
        self.requestInterruption()

    def _is_cancelled(self) -> bool:
        return bool(self._cancel_requested or self.isInterruptionRequested())

    def run(self) -> None:  # noqa: D401
        try:
            result = export_deck_video(
                self.deck,
                self.output_path,
                fps=self.fps,
                size=self.size,
                timeline=self.timeline,
                audio_path=self.audio_path or None,
                audio_bitrate=self.audio_bitrate,
                progress_cb=lambda event: self.progressChanged.emit(dict(event)),
                cancel_requested=self._is_cancelled,
            )
        except PptVideoExportCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.resultReady.emit(dict(result))


__all__ = ["PptVideoExportWorker"]
