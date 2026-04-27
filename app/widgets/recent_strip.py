from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.capture import pil_to_qimage
from app.i18n import tr
from app.paths import open_in_explorer
from app.recent_captures import RecentCapture, format_size, list_recent, load_thumbnail


CARD_W = 140
CARD_H = 120
THUMB_W = 130
THUMB_H = 74


class _RecentCard(QWidget):
    clicked = Signal(Path)
    reveal_requested = Signal(Path)
    delete_requested = Signal(Path)

    def __init__(self, capture: RecentCapture) -> None:
        super().__init__()
        self._capture = capture
        self.setObjectName("RecentCard")
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self._thumb_label = QLabel()
        self._thumb_label.setObjectName("RecentThumb")
        self._thumb_label.setFixedSize(THUMB_W, THUMB_H)
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setScaledContents(False)
        layout.addWidget(self._thumb_label, alignment=Qt.AlignmentFlag.AlignCenter)

        name_label = QLabel(capture.path.name)
        name_label.setObjectName("RecentName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setToolTip(capture.path.name)
        name_label.setWordWrap(False)
        fm = name_label.fontMetrics()
        name_label.setText(fm.elidedText(capture.path.name, Qt.TextElideMode.ElideMiddle, THUMB_W))
        layout.addWidget(name_label)

        kind_label = tr(f"recent.kind.{capture.kind}")
        size_label = QLabel(f"{format_size(capture.size_bytes)}  ·  {kind_label}")
        size_label.setObjectName("RecentMeta")
        size_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(size_label)

        self._render_thumbnail()

    def _render_thumbnail(self) -> None:
        pil_img = load_thumbnail(self._capture, (THUMB_W, THUMB_H))
        if pil_img is None:
            self._thumb_label.setText(self._placeholder_text())
            self._thumb_label.setProperty("videoPlaceholder", True)
            self._thumb_label.style().unpolish(self._thumb_label)
            self._thumb_label.style().polish(self._thumb_label)
            return
        qimg = pil_to_qimage(pil_img)
        pix = QPixmap.fromImage(qimg)
        self._thumb_label.setPixmap(pix)

    def _placeholder_text(self) -> str:
        if self._capture.kind == "video":
            return "🎬\nMP4"
        if self._capture.kind == "gif":
            return "GIF"
        return "IMG"

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._capture.path)

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        reveal = menu.addAction(tr("recent.menu.reveal"))
        open_default = menu.addAction(tr("recent.menu.open"))
        menu.addSeparator()
        delete = menu.addAction(tr("recent.menu.delete"))
        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is reveal:
            self.reveal_requested.emit(self._capture.path)
        elif chosen is open_default:
            import os

            os.startfile(str(self._capture.path))
        elif chosen is delete:
            self.delete_requested.emit(self._capture.path)


class RecentStrip(QScrollArea):
    """Horizontally scrolling strip of recent capture cards."""

    item_activated = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("RecentStrip")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setFixedHeight(CARD_H + 20)

        self._container = QWidget()
        self._container.setObjectName("RecentStripContainer")
        self._layout = QHBoxLayout(self._container)
        self._layout.setContentsMargins(4, 8, 4, 8)
        self._layout.setSpacing(8)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setWidget(self._container)

    def refresh(self, save_dir: Path) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        entries = list_recent(save_dir)
        if not entries:
            # Build a fresh empty label every refresh — keeping a
            # long-lived ``self._empty_label`` would crash here on
            # the second refresh because the clear loop above already
            # marked the previous instance for ``deleteLater``.
            empty_label = QLabel(tr("main.recent.empty"))
            empty_label.setObjectName("RecentEmpty")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(empty_label)
            return

        for capture in entries:
            card = _RecentCard(capture)
            card.clicked.connect(self._on_card_clicked)
            card.reveal_requested.connect(open_in_explorer)
            card.delete_requested.connect(self._on_delete)
            self._layout.addWidget(card)
        self._layout.addStretch(1)
        self._save_dir = save_dir

    def _on_card_clicked(self, path: Path) -> None:
        self.item_activated.emit(path)

    def _on_delete(self, path: Path) -> None:
        from PySide6.QtWidgets import QMessageBox

        ans = QMessageBox.question(
            self,
            tr("recent.delete.title"),
            tr("recent.delete.body", name=path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        try:
            path.unlink()
        except OSError:
            pass
        if hasattr(self, "_save_dir"):
            self.refresh(self._save_dir)
