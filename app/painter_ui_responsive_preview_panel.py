"""Transient responsive preview matrix for Painter UI Design."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text
from app.painter_ui_responsive_preview import (
    RESPONSIVE_PREVIEW_CONTEXTS,
    build_ui_responsive_preview_matrix,
)
from app.painter_ui_workspace import PainterUIDesignOverlay


class _ResponsivePreviewCard(QFrame):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIResponsivePreviewCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)
        self.title_label = QLabel(label)
        self.title_label.setObjectName("PaintMuted")
        layout.addWidget(self.title_label)
        self.preview = PainterUIDesignOverlay(self)
        self.preview.setEnabled(False)
        self.preview.set_rulers_visible(False)
        self.preview.set_artboard_labels_visible(False)
        self.preview.setMinimumSize(180, 128)
        layout.addWidget(self.preview, 1)

    def set_document(self, document: Mapping[str, Any]) -> None:
        self.preview.set_document(document)
        QTimer.singleShot(0, self.preview.fit_artboard)

    def event(self, event: QEvent) -> bool:
        result = super().event(event)
        if event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.preview.fit_artboard)
        return result


class PainterUIResponsivePreviewPanel(QDialog):
    """A non-modal six-context preview that never mutates the document."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIResponsivePreviewPanel")
        self.setWindowTitle(painter_text("Responsive Preview"))
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.resize(920, 610)
        self.setStyleSheet(
            """
            QDialog#PainterUIResponsivePreviewPanel {
                background: #10151D;
                border: 1px solid #2C3746;
            }
            QDialog#PainterUIResponsivePreviewPanel QLabel {
                color: #DCE5F0;
            }
            QDialog#PainterUIResponsivePreviewPanel QLabel#PaintMuted {
                color: #97A5B7;
            }
            QFrame#PainterUIResponsivePreviewCard {
                background: #161C25;
                border: 1px solid #2A3442;
            }
            QPushButton#PainterUIInspectorIconButton {
                background: #18212C;
                border: 1px solid #334154;
                border-radius: 4px;
                padding: 3px;
            }
            QPushButton#PainterUIInspectorIconButton:hover {
                background: #233044;
                border-color: #55739A;
            }
            """
        )
        self._report: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        title_row = QHBoxLayout()
        title = QLabel(painter_text("Responsive Preview"))
        title.setObjectName("PainterUIInspectorTitle")
        self.summary_label = QLabel(
            painter_text("Preview only - document is unchanged")
        )
        self.summary_label.setObjectName("PaintMuted")
        close_button = QPushButton()
        close_button.setObjectName("PainterUIInspectorIconButton")
        close_button.setIcon(app_icon("x", size=12, color="#B8C4D3"))
        close_button.setIconSize(icon_size(12))
        close_button.setToolTip(painter_text("Close"))
        close_button.clicked.connect(self.close)
        title_row.addWidget(title)
        title_row.addWidget(self.summary_label, 1)
        title_row.addWidget(close_button)
        root.addLayout(title_row)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        self.cards: list[_ResponsivePreviewCard] = []
        for index, (breakpoint, orientation, width, height) in enumerate(
            RESPONSIVE_PREVIEW_CONTEXTS
        ):
            card = _ResponsivePreviewCard(
                f"{breakpoint.title()} · {orientation.title()} "
                f"{width} × {height}",
                self,
            )
            self.cards.append(card)
            grid.addWidget(card, index // 3, index % 3)
        root.addLayout(grid, 1)

    def set_document(self, value: Mapping[str, Any] | None) -> None:
        documents, report = build_ui_responsive_preview_matrix(value)
        self._report = report
        for card, document in zip(self.cards, documents):
            card.set_document(document)
        self.summary_label.setText(
            painter_text("Preview only - document is unchanged")
            + f" · {report['active_artboard_name']}"
        )

    def report(self) -> dict[str, Any]:
        return dict(self._report)


__all__ = ["PainterUIResponsivePreviewPanel"]
