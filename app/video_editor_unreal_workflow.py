"""Unreal Engine bridge entry points for the editor shell."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Literal

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from app.action_sequencer_owner_render import (
    default_action_sequencer_project_path,
    open_action_sequencer_owner_render_window,
)

UNREAL_ENGINE_PROJECT_DIALOG_TITLE = "Open UnrealEngine5 project"
UNREAL_ENGINE_PROJECT_FILTER = "Unreal Engine 5 Project (*.uproject);;All Files (*)"
UNREAL_ENGINE_START_CONNECTED_LABEL = "Start with connected project"
UNREAL_ENGINE_OPEN_PROJECT_LABEL = "Open UnrealEngine5 project"
UNREAL_ENGINE_PROJECT_SETTINGS_KEY = "unreal_link/last_project_path"

ProjectDialogGetter = Callable[[QWidget | None, str, str, str], tuple[str, str]]
ConnectedProjectChoice = Literal["start", "open", "cancel"]


def _unreal_link_settings() -> Any:
    from PySide6.QtCore import QSettings

    return QSettings("TigerCapture", "TigerCapture")


def remember_connected_unreal_engine_project(
    project_path: Path | str | None,
    *,
    settings: Any | None = None,
) -> None:
    store = settings or _unreal_link_settings()
    if project_path is None:
        store.remove(UNREAL_ENGINE_PROJECT_SETTINGS_KEY)
    else:
        store.setValue(
            UNREAL_ENGINE_PROJECT_SETTINGS_KEY,
            str(Path(project_path).expanduser().resolve()),
        )
    store.sync()


def load_connected_unreal_engine_project(
    *,
    settings: Any | None = None,
) -> Path | None:
    store = settings or _unreal_link_settings()
    value = store.value(UNREAL_ENGINE_PROJECT_SETTINGS_KEY, "")
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.suffix.lower() == ".uproject" and path.is_file():
        return path
    store.remove(UNREAL_ENGINE_PROJECT_SETTINGS_KEY)
    store.sync()
    return None


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


def connected_unreal_engine_project_path(
    owner: object,
    *,
    settings: Any | None = None,
) -> Path | None:
    text = str(getattr(owner, "_unreal_engine_project_path", "") or "").strip()
    if text:
        path = Path(text)
        if path.suffix.lower() == ".uproject":
            return path
    path = load_connected_unreal_engine_project(settings=settings)
    if path is not None:
        setattr(owner, "_unreal_engine_project_path", str(path))
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


def start_unreal_engine_link_with_project(
    owner: object,
    project_path: Path,
    *,
    settings: Any | None = None,
) -> dict[str, str]:
    project_path = Path(project_path).expanduser().resolve()
    setattr(owner, "_unreal_engine_project_path", str(project_path))
    remember_connected_unreal_engine_project(project_path, settings=settings)
    return {
        "status": "connected",
        "project_path": str(project_path),
    }


def _open_owner_render_window(owner: QWidget, project_path: Path) -> None:
    start_unreal_engine_link_with_project(owner, project_path)
    open_action_sequencer_owner_render_window(owner, project_path)
    flash = getattr(owner, "_flash_status", None)
    if callable(flash):
        flash(f"Owner Render: {project_path.name}")


def open_unreal_engine_link(self) -> None:
    connected_project = connected_unreal_engine_project_path(self)
    if connected_project is not None:
        choice = choose_unreal_engine_link_start_mode(self, connected_project)
        if choice == "cancel":
            return
        if choice == "start":
            _open_owner_render_window(self, connected_project)
            return

    default_project = default_action_sequencer_project_path()
    if connected_project is not None:
        initial_dir = str(connected_project.parent)
    elif default_project.exists():
        initial_dir = str(default_project.parent)
    else:
        initial_dir = ""
    project_path = select_unreal_engine_project_file(self, initial_dir=initial_dir)
    if project_path is None:
        return
    _open_owner_render_window(self, project_path)


__all__ = [
    "UNREAL_ENGINE_OPEN_PROJECT_LABEL",
    "UNREAL_ENGINE_PROJECT_DIALOG_TITLE",
    "UNREAL_ENGINE_PROJECT_FILTER",
    "UNREAL_ENGINE_PROJECT_SETTINGS_KEY",
    "UNREAL_ENGINE_START_CONNECTED_LABEL",
    "choose_unreal_engine_link_start_mode",
    "connected_unreal_engine_project_path",
    "load_connected_unreal_engine_project",
    "open_unreal_engine_link",
    "remember_connected_unreal_engine_project",
    "select_unreal_engine_project_file",
    "start_unreal_engine_link_with_project",
]
