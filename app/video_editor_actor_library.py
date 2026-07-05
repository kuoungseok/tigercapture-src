"""Compact actor-source library for the renewed editor left rail."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.effect_cards import Live2DCard, SpineCard


class _ActorSourceRow(QWidget):
    def __init__(self, card: QWidget, title: str, detail: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActorSourceRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(44)
        row = QHBoxLayout(self)
        row.setContentsMargins(7, 5, 7, 5)
        row.setSpacing(8)
        card.setFixedSize(34, 34)
        row.addWidget(card, 0, Qt.AlignmentFlag.AlignVCenter)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        title_label = QLabel(title, self)
        title_label.setObjectName("ActorSourceTitle")
        detail_label = QLabel(detail, self)
        detail_label.setObjectName("ActorSourceDetail")
        detail_label.setWordWrap(False)
        text_col.addWidget(title_label)
        text_col.addWidget(detail_label)
        row.addLayout(text_col, stretch=1)


class ActorLibraryPanel(QWidget):
    """Left-rail actor source list with draggable Live2D/Spine cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ActorLibraryPanel")
        self.live2d_card = Live2DCard()
        self.spine_card = SpineCard()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setSpacing(6)
        layout.addWidget(
            _ActorSourceRow(
                self.live2d_card,
                "Live2D",
                "model / motion / actor lane",
                self,
            )
        )
        layout.addWidget(
            _ActorSourceRow(
                self.spine_card,
                "Spine",
                "skeleton / atlas / actor lane",
                self,
            )
        )
        layout.addStretch(1)

        self.setStyleSheet(
            """
            QWidget#ActorLibraryPanel {
                background:#101010;
                border:none;
            }
            QWidget#ActorSourceRow {
                background:#141414;
                border:1px solid #272727;
                border-radius:6px;
            }
            QWidget#ActorSourceRow:hover {
                background:#181818;
                border-color:#3A3A3A;
            }
            QLabel#ActorSourceTitle {
                background:transparent;
                border:none;
                color:#E1E4EA;
                font-size:10px;
                font-weight:620;
            }
            QLabel#ActorSourceDetail {
                background:transparent;
                border:none;
                color:#7E858E;
                font-size:8px;
                font-weight:500;
            }
            """
        )
