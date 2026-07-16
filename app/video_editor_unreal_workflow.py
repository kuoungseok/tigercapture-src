"""Unreal Engine bridge entry points for the editor shell."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from app.unreal_link_reference_paths import format_unreal_link_reference_report


UNREAL_ENGINE_PROJECT_DIALOG_TITLE = "Open UnrealEngine5 project"
UNREAL_ENGINE_PROJECT_FILTER = "Unreal Engine 5 Project (*.uproject);;All Files (*)"
UNREAL_ENGINE_START_CONNECTED_LABEL = "Start with connected project"
UNREAL_ENGINE_OPEN_PROJECT_LABEL = "Open UnrealEngine5 project"

ProjectDialogGetter = Callable[[QWidget | None, str, str, str], tuple[str, str]]
ConnectedProjectChoice = Literal["start", "open", "cancel"]


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


def connected_unreal_engine_project_path(owner: object) -> Path | None:
    text = str(getattr(owner, "_unreal_engine_project_path", "") or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.suffix.lower() != ".uproject":
        return None
    return path


def choose_unreal_engine_link_start_mode(
    parent: QWidget | None,
    project_path: Path,
    *,
    message_box_factory: Callable[[QWidget | None], QMessageBox] | None = None,
) -> ConnectedProjectChoice:
    box = (message_box_factory or QMessageBox)(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Unreal Engine Link")
    box.setText(f"Connected project:\n{project_path}")
    box.setInformativeText("Start with the connected project, or open another Unreal Engine 5 project.")
    start_btn = box.addButton(UNREAL_ENGINE_START_CONNECTED_LABEL, QMessageBox.ButtonRole.AcceptRole)
    open_btn = box.addButton(UNREAL_ENGINE_OPEN_PROJECT_LABEL, QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(start_btn)
    box.exec()
    clicked = box.clickedButton()
    if clicked is start_btn:
        return "start"
    if clicked is open_btn:
        return "open"
    return "cancel"


def start_unreal_engine_link_with_project(owner: object, project_path: Path) -> dict[str, str]:
    setattr(owner, "_unreal_engine_project_path", str(project_path))
    return {
        "status": "connected",
        "project_path": str(project_path),
    }


def open_unreal_engine_link(self) -> None:
    connected_project = connected_unreal_engine_project_path(self)
    if connected_project is not None:
        choice = choose_unreal_engine_link_start_mode(self, connected_project)
        if choice == "cancel":
            return
        if choice == "start":
            start_unreal_engine_link_with_project(self, connected_project)
            QMessageBox.information(
                self,
                "Unreal Engine Link",
                f"Started with connected Unreal Engine 5 project:\n{connected_project}\n\n"
                f"{format_unreal_link_reference_report()}",
            )
            return

    initial_dir = str(connected_project.parent) if connected_project is not None else ""
    project_path = select_unreal_engine_project_file(self, initial_dir=initial_dir)
    if project_path is None:
        return
    start_unreal_engine_link_with_project(self, project_path)
    QMessageBox.information(
        self,
        "Unreal Engine Link",
        f"Selected Unreal Engine 5 project:\n{project_path}\n\n"
        f"{format_unreal_link_reference_report()}",
    )


__all__ = [
    "UNREAL_ENGINE_OPEN_PROJECT_LABEL",
    "UNREAL_ENGINE_PROJECT_DIALOG_TITLE",
    "UNREAL_ENGINE_PROJECT_FILTER",
    "UNREAL_ENGINE_START_CONNECTED_LABEL",
    "choose_unreal_engine_link_start_mode",
    "connected_unreal_engine_project_path",
    "open_unreal_engine_link",
    "select_unreal_engine_project_file",
    "start_unreal_engine_link_with_project",
]
