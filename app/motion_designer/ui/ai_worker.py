"""Background provider worker for Motion Designer AI proposals."""
from __future__ import annotations

from pathlib import Path
from threading import Event

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
                "auto_detect_objects": bool(
                    self._request.get("auto_detect_objects", True)
                ),
                "object_detector_model": str(
                    self._request.get("object_detector_model") or ""
                ),
                "matting_mode": str(
                    self._request.get("matting_mode") or "edge_aware"
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


class MotionAICandidatePreviewWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        composition: MotionComposition,
        candidates: list[dict],
        cache_root: str | Path,
    ) -> None:
        super().__init__()
        self._composition = MotionComposition.from_dict(composition.to_dict())
        self._candidates = [dict(item) for item in candidates]
        self._cache_root = Path(cache_root)
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @Slot()
    def run(self) -> None:
        if self._cancelled.is_set():
            self.completed.emit({"previews": []})
            return
        try:
            from app.motion_designer.candidate_preview import (
                render_candidate_preview_set,
            )

            result = render_candidate_preview_set(
                self._composition,
                self._candidates,
                cache_root=self._cache_root,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            if self._cancelled.is_set():
                result["previews"] = []
            self.completed.emit(result)


class MotionAIPatchWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        composition: MotionComposition,
        prompt: str,
        layer_ids: list[str],
        provider_id: str = "",
    ) -> None:
        super().__init__()
        self._composition = MotionComposition.from_dict(composition.to_dict())
        self._prompt = str(prompt)
        self._layer_ids = [str(item) for item in layer_ids]
        self._provider_id = str(provider_id)

    @Slot()
    def run(self) -> None:
        try:
            from app.motion_designer.ai_generation import generate_motion_ai_patch
            from app.motion_designer.ai_patch_diff import build_motion_ai_patch_diff

            patch = generate_motion_ai_patch(
                self._composition,
                self._prompt,
                self._layer_ids,
                provider_id=self._provider_id or None,
            )
            diff = build_motion_ai_patch_diff(self._composition, patch)
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit({"patch": patch, "diff": diff})


__all__ = [
    "MotionAICandidatePreviewWorker",
    "MotionAIGenerationWorker",
    "MotionAIPatchWorker",
]
