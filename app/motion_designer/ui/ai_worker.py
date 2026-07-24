"""Background provider worker for Motion Designer AI proposals."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from app.motion_designer.ai_generation import (
    generate_motion_ai_candidates,
    generate_motion_ai_proposal,
)
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
            options = {
                "provider_id": str(self._request.get("provider") or "") or None,
                "timeout_seconds": 30,
                "decompose_images": bool(
                    self._request.get("decompose_images", True)
                ),
                "max_decomposed_elements": int(
                    self._request.get("max_decomposed_elements", 5)
                ),
                "segmentation_mode": str(
                    self._request.get("segmentation_mode") or "auto"
                ),
                "inpaint_mode": str(
                    self._request.get("inpaint_mode") or "auto"
                ),
                "reconstruct_text": bool(
                    self._request.get("reconstruct_text", True)
                ),
                "ocr_native_threshold": float(
                    self._request.get("ocr_native_threshold", 0.78)
                ),
            }
            requested_variant = str(
                self._request.get("motion_variant") or "auto"
            )
            if requested_variant == "auto":
                candidates = generate_motion_ai_candidates(
                    self._composition,
                    str(self._request.get("prompt") or ""),
                    self._request.get("references") or [],
                    **options,
                )
            else:
                candidates = [generate_motion_ai_proposal(
                    self._composition,
                    str(self._request.get("prompt") or ""),
                    self._request.get("references") or [],
                    motion_variant=requested_variant,
                    **options,
                )]
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit({
                "schema": "tigerstudio.motion.ai.candidate_set.v1",
                "selected_index": 0,
                "candidates": [item.to_dict() for item in candidates],
            })


__all__ = ["MotionAIGenerationWorker"]
