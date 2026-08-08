from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.schema import MotionComposition
from app.unreal_umg_workflow import preflight_umg_project
from app.icons import unreal_engine_icon
from .style import MOTION_DESIGNER_QSS


class MotionUMGPanel(QWidget):
    generate_requested = Signal(str, str)
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionUMGPanel")
        self._composition: MotionComposition | None = None
        self._busy = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(7)
        header = QHBoxLayout()
        logo = QLabel(self)
        logo.setPixmap(unreal_engine_icon(42, color="#f2f4f7").pixmap(42, 42))
        logo.setFixedSize(46, 46)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(logo)
        header_text = QVBoxLayout()
        heading = QLabel("Unreal Link", self)
        heading.setObjectName("MotionInspectorSection")
        subtitle = QLabel("Tiger Studio / Unreal Engine 5", self)
        subtitle.setObjectName("MotionOutputDetail")
        header_text.addWidget(heading)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        layout.addLayout(header)

        detail = QLabel(
            "Tiger Studio installs its project plugin, imports referenced "
            "resources, then generates and compiles an editable Widget Blueprint.",
            self,
        )
        detail.setWordWrap(True)
        detail.setObjectName("MotionOutputDetail")
        layout.addWidget(detail)

        form = QFormLayout()
        self.project_path = QLineEdit(self)
        self.project_path.setPlaceholderText("Choose an Unreal .uproject")
        browse = QPushButton("...", self)
        browse.setFixedWidth(30)
        browse.setToolTip("Choose Unreal project")
        project_row = QHBoxLayout()
        project_row.addWidget(self.project_path, 1)
        project_row.addWidget(browse)
        form.addRow("Project", project_row)

        self.destination_root = QLineEdit("/Game/TigerStudio/Generated", self)
        form.addRow("Content", self.destination_root)
        layout.addLayout(form)

        self.status = QLabel("Choose an Unreal project", self)
        self.status.setWordWrap(True)
        self.status.setObjectName("MotionOutputStatus")
        layout.addWidget(self.status)

        self.generate_button = QPushButton("Generate Widget Blueprint", self)
        self.generate_button.setObjectName("MotionPrimaryButton")
        self.generate_button.setEnabled(False)
        layout.addWidget(self.generate_button)
        layout.addStretch(1)

        browse.clicked.connect(self._browse)
        self.project_path.textChanged.connect(self._refresh)
        self.generate_button.clicked.connect(self._request_generate)

    def set_composition(self, composition: MotionComposition) -> None:
        self._composition = MotionComposition.from_dict(composition.to_dict())
        self._refresh()

    def _browse(self) -> None:
        initial = (
            str(Path(self.project_path.text()).parent)
            if self.project_path.text()
            else ""
        )
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Unreal Engine 5 project",
            initial,
            "Unreal Engine Project (*.uproject)",
        )
        if path:
            self.project_path.setText(path)

    def _refresh(self) -> None:
        path = self.project_path.text().strip()
        if self._busy:
            return
        if not path:
            self.status.setText("Choose an Unreal project")
            self.generate_button.setEnabled(False)
            return
        try:
            report = preflight_umg_project(path)
        except Exception as exc:
            self.status.setText(f"Blocked: {exc}")
            self.generate_button.setEnabled(False)
            return
        plugin = report["plugin"]
        if report["blockers"]:
            self.status.setText("Blocked: " + ", ".join(report["blockers"]))
        elif not plugin["installed"]:
            self.status.setText(
                "Ready. The Tiger Studio UMG project plugin will be installed "
                "and enabled automatically."
            )
        elif plugin["update_required"]:
            self.status.setText(
                "Ready. The project plugin will be updated before generation."
            )
        else:
            self.status.setText("Ready. Project plugin is installed and enabled.")
        self.generate_button.setEnabled(
            report["ok"] and self._composition is not None
        )

    def _request_generate(self) -> None:
        if self._busy:
            self.cancel_requested.emit()
            return
        if self._composition is None:
            return
        self.generate_requested.emit(
            self.project_path.text().strip(),
            self.destination_root.text().strip() or "/Game/TigerStudio/Generated",
        )

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = bool(busy)
        self.project_path.setEnabled(not busy)
        self.destination_root.setEnabled(not busy)
        self.generate_button.setEnabled(True)
        self.generate_button.setText(
            "Cancel" if busy else "Generate Widget Blueprint"
        )
        if message:
            self.status.setText(message)
        if not busy:
            self._refresh()

    def show_result(self, result: dict) -> None:
        self._busy = False
        if result.get("ok"):
            self.status.setText(
                "Generated: " + str(result.get("generated_asset_path") or "")
            )
        else:
            errors = result.get("errors") or [
                result.get("message") or "Generation failed"
            ]
            self.status.setText(
                "Failed: " + " | ".join(str(item) for item in errors)
            )
        self.project_path.setEnabled(True)
        self.destination_root.setEnabled(True)
        self.generate_button.setText("Generate Widget Blueprint")
        self.generate_button.setEnabled(bool(self.project_path.text().strip()))


class MotionUnrealLinkDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionUnrealLinkDialog")
        self.setWindowTitle("Unreal Link")
        self.resize(520, 360)
        self.setStyleSheet(MOTION_DESIGNER_QSS)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        self.panel = MotionUMGPanel(self)
        layout.addWidget(self.panel)


__all__ = ["MotionUMGPanel", "MotionUnrealLinkDialog"]
