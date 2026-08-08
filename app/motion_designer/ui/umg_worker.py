from __future__ import annotations

from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from app.motion_designer.schema import MotionComposition
from app.unreal_umg_document import package_motion_composition_for_umg
from app.unreal_umg_workflow import run_unreal_umg_generation


class MotionUMGGenerationWorker(QObject):
    finished = Signal(object)

    def __init__(
        self,
        composition: MotionComposition,
        project_path: str,
        destination_root: str,
    ) -> None:
        super().__init__()
        self._composition = MotionComposition.from_dict(composition.to_dict())
        self._project_path = str(project_path)
        self._destination_root = str(destination_root)
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            project = Path(self._project_path).expanduser().resolve()
            packet_root = (
                project.parent / "TigerStudioSourceAssets" / self._composition.id
            )
            packet = package_motion_composition_for_umg(
                self._composition,
                packet_root,
            )
            if not packet["ok"]:
                self.finished.emit(packet)
                return
            result = run_unreal_umg_generation(
                project,
                packet["document_path"],
                destination_root=self._destination_root,
                cancel_event=self._cancel_event,
            )
            result["packet"] = packet
            self.finished.emit(result)
        except Exception as exc:
            self.finished.emit({"ok": False, "errors": [str(exc)]})


__all__ = ["MotionUMGGenerationWorker"]
