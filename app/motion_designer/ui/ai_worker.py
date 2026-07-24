"""Background provider worker for Motion Designer AI proposals."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.motion_designer.ai_generation import generate_motion_ai_proposal
from app.motion_designer.schema import MotionComposition


class MotionAIGenerationWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, composition: MotionComposition, request: dict) -> None:
        super().__init__()
        self._composition = MotionComposition.from_dict(composition.to_dict())
        self._request = dict(request)

    @Slot()
    def run(self) -> None:
        try:
            proposal = generate_motion_ai_proposal(
                self._composition,
                str(self._request.get("prompt") or ""),
                self._request.get("references") or [],
                provider_id=str(self._request.get("provider") or "") or None,
                timeout_seconds=30,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(proposal.to_dict())


__all__ = ["MotionAIGenerationWorker"]
