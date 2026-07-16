"""Unreal Engine bridge entry points for the editor shell."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from app.unreal_link_reference_paths import format_unreal_link_reference_report


UNREAL_ENGINE_PROJECT_DIALOG_TITLE = "Open UnrealEngine5 project"
UNREAL_ENGINE_PROJECT_FILTER = "Unreal Engine 5 Project (*.uproject);;All Files (*)"

ProjectDialogGetter = Callable[[QWidget | None, str, str, str], tuple[str, str]]


def select_unreal_engine_project_file(
    parent: QWidget | None,
    *,
    initial_dir: str = "",
    dialog_getter: ProjectDialogGetter | None = None,
) -> Path | None:
    getter = dialog_getter or QFileDialog.getOpenFileName
    path, _selected_filter = getter(
        parent,
        UNREAL_ENGINE_PROJECT_DIALOG_TITLE,
        initial_dir,
        UNREAL_ENGINE_PROJECT_FILTER,
    )
    text = str(path or "").strip()
    if not text:
        return None
    return Path(text)


def open_unreal_engine_link(self) -> None:
    previous = getattr(self, "_unreal_engine_project_path", "")
    initial_dir = str(Path(previous).parent) if previous else ""
    project_path = select_unreal_engine_project_file(self, initial_dir=initial_dir)
    if project_path is None:
        return
    setattr(self, "_unreal_engine_project_path", str(project_path))
    QMessageBox.information(
        self,
        "Unreal Engine Link",
        f"Selected Unreal Engine 5 project:\n{project_path}\n\n"
        f"{format_unreal_link_reference_report()}",
    )


__all__ = [
    "UNREAL_ENGINE_PROJECT_DIALOG_TITLE",
    "UNREAL_ENGINE_PROJECT_FILTER",
    "open_unreal_engine_link",
    "select_unreal_engine_project_file",
]
