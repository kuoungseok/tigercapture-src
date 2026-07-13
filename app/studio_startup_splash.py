"""Lightweight Tiger Studio startup window.

The full editor imports and constructs a large widget tree, including an
OpenGL preview surface.  This window is intentionally tiny and dependency-light
so users see a clear startup state before that heavier work begins.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


def _branding_logo_path() -> Path | None:
    roots: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.append(Path(__file__).resolve().parent.parent)
    roots.append(Path.cwd())
    for root in roots:
        branding_dir = root / "resources" / "branding"
        for name in ("tiger_studio_logo_transparent.png", "tiger_studio_logo.png"):
            candidate = branding_dir / name
            if candidate.exists():
                return candidate
    return None


class StudioStartupSplash(QWidget):
    """Small status window shown while Tiger Studio builds the editor."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setObjectName("StudioStartupSplash")
        self.setWindowTitle("Tiger Studio")
        self.setFixedSize(620, 420)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        panel = QFrame(self)
        panel.setObjectName("StudioStartupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        logo = QLabel(panel)
        logo.setObjectName("StudioStartupLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setMinimumHeight(178)
        logo.setMaximumHeight(188)
        logo_path = _branding_logo_path()
        if logo_path is not None:
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                logo.setPixmap(
                    pixmap.scaled(
                        440,
                        188,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        if logo.pixmap() is None:
            logo.setText("TIGER STUDIO")
        layout.addWidget(logo)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        mark = QLabel("TC", panel)
        mark.setObjectName("StudioStartupMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(mark)
        title = QLabel("Tiger Studio", panel)
        title.setObjectName("StudioStartupTitle")
        brand_row.addWidget(title, stretch=1)
        layout.addLayout(brand_row)

        self._status = QLabel("Starting editor...", panel)
        self._status.setObjectName("StudioStartupStatus")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._detail = QLabel("Preparing the workspace and GPU preview surface.", panel)
        self._detail.setObjectName("StudioStartupDetail")
        self._detail.setWordWrap(True)
        layout.addWidget(self._detail)

        self._progress = QProgressBar(panel)
        self._progress.setObjectName("StudioStartupProgress")
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        root.addWidget(panel)
        self.setStyleSheet(
            """
            QWidget#StudioStartupSplash {
                background: #080B10;
                color: #EAF0FF;
                font-family: "Segoe UI", Arial, sans-serif;
            }
            QFrame#StudioStartupPanel {
                background: #101620;
                border: 1px solid #263248;
                border-radius: 8px;
            }
            QLabel#StudioStartupMark {
                min-width: 46px;
                max-width: 46px;
                min-height: 46px;
                max-height: 46px;
                border-radius: 8px;
                background: #1B2636;
                border: 1px solid #3D4E68;
                color: #9EE6B8;
                font-weight: 800;
                font-size: 17px;
            }
            QLabel#StudioStartupTitle {
                color: #FFFFFF;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#StudioStartupLogo {
                background: transparent;
                border: none;
                color: #FFFFFF;
                font-size: 26px;
                font-weight: 900;
            }
            QLabel#StudioStartupStatus {
                color: #EAF0FF;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#StudioStartupDetail {
                color: #AAB5C8;
                font-size: 12px;
            }
            QProgressBar#StudioStartupProgress {
                min-height: 8px;
                max-height: 8px;
                border: 1px solid #2B364C;
                border-radius: 4px;
                background: #070A0F;
            }
            QProgressBar#StudioStartupProgress::chunk {
                border-radius: 4px;
                background: #82E6A8;
            }
            """
        )

    def set_status(self, status: str, detail: str = "") -> None:
        self._status.setText(str(status or "Starting editor..."))
        self._detail.setText(str(detail or ""))

    def set_error(self, detail: str) -> None:
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self.set_status("Tiger Studio could not finish startup.", detail)
