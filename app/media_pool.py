"""DaVinci-style media pool.

Drop video files (or GIFs) from the OS into this panel to register
them as importable clips. Drag a clip from the pool onto a track row
to add it to the timeline — the drag carries ``text/uri-list`` so
the existing track drop handler picks it up the same way it would an
OS file drop.

Phase A1 (this file): flat list view with filename + duration; no
thumbnails yet. Phase A2 will add a grid mode with first-frame
thumbnails extracted via cv2.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QMimeData, QPoint, QSize, Qt, QUrl, Signal
from PySide6.QtCore import QRect
from PySide6.QtGui import (
    QColor,
    QDrag,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


# Pool item visuals — square thumbnails in an icon-mode grid. The
# letterbox border keeps frames with a non-square source from being
# squished. Grid cell hugs the icon tightly so the click target is
# (almost) the icon itself — wide cell padding tends to land mouse
# clicks in empty space, which IconMode interprets as rubber-band
# selection rather than a drag-out.
THUMB_SIZE = 96
GRID_W = 104
GRID_H = 124


# Extensions we treat as importable media. Mirrors the editor's track
# drop filter so pool ↔ track behaviour is consistent. The pool now
# accepts audio too — DaVinci treats every media kind through the
# same pool.
VIDEO_EXTS = frozenset({
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".m4v", ".mpg", ".mpeg", ".wmv", ".gif",
})
AUDIO_EXTS = frozenset({
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma",
})
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS


def _kind_for_path(p: Path) -> str:
    suf = p.suffix.lower()
    if suf in VIDEO_EXTS:
        return "V"
    if suf in AUDIO_EXTS:
        return "A"
    return "?"


def _format_duration(ms: int | None) -> str:
    if ms is None or ms <= 0:
        return ""
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _probe_duration_ms(path: Path) -> int | None:
    """Best-effort duration probe via OpenCV. Returns None if it
    fails — we fall back to showing the filename without a duration
    badge in that case."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
            n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
            if fps <= 0 or n_frames <= 0:
                return None
            return int(round((n_frames / fps) * 1000.0))
        finally:
            cap.release()
    except Exception:
        return None


def _make_video_thumbnail(path: Path, size: int = THUMB_SIZE) -> QPixmap | None:
    """Extract the first frame of a video / GIF and letterbox it onto
    a square ``size`` × ``size`` pixmap. Returns None on any failure
    so the caller can fall back to a generic placeholder."""
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return None
        try:
            ret, bgr = cap.read()
        finally:
            cap.release()
        if not ret or bgr is None:
            return None
        h, w = bgr.shape[:2]
        if w <= 0 or h <= 0:
            return None
        # OpenCV gives BGR; flip to RGB once for the QImage view.
        rgb = bgr[:, :, ::-1]
        scale = size / max(w, h)
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        rgb_resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        ox = (size - nw) // 2
        oy = (size - nh) // 2
        canvas[oy:oy + nh, ox:ox + nw] = rgb_resized
        canvas = np.ascontiguousarray(canvas)
        qimg = QImage(
            canvas.data, size, size, size * 3, QImage.Format.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(qimg)
    except Exception:
        return None


def _make_audio_thumbnail(path: Path, size: int = THUMB_SIZE) -> QPixmap:
    """Stylised vertical-bar 'waveform' for audio files. The bar
    heights are seeded by the file size so two different audio files
    produce distinct-looking thumbnails without paying for an actual
    decoded waveform extraction at pool-add time."""
    pm = QPixmap(size, size)
    pm.fill(QColor("#1a1a1a"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    n_bars = 11
    cell = size // (n_bars + 2)
    bar_w = max(2, cell - 1)
    cy = size // 2
    seed = 0
    try:
        seed = int(path.stat().st_size) & 0xFFFFFFFF
    except OSError:
        seed = abs(hash(str(path))) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    heights = rng.uniform(0.30, 0.95, n_bars)
    bar_color = QColor("#9a9a9a")
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bar_color)
    total_w = n_bars * bar_w + (n_bars - 1) * (cell - bar_w)
    x = (size - total_w) // 2
    for h in heights:
        h_px = max(2, int(size * 0.7 * float(h)))
        p.drawRect(QRect(x, cy - h_px // 2, bar_w, h_px))
        x += cell
    # Subtle baseline so even quiet bars sit on a visible line.
    p.setPen(QPen(QColor("#444"), 1))
    p.drawLine(8, cy, size - 8, cy)
    p.end()
    return pm


def _draw_kind_badge(pm: QPixmap, kind: str) -> QPixmap:
    """Overlay a small ``V`` / ``A`` badge in the bottom-right corner
    of a thumbnail so users can tell media types apart at a glance.
    Single-accent grey badge — text alone differentiates."""
    if kind not in ("V", "A"):
        return pm
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    badge_w, badge_h = 18, 14
    pad = 4
    x = out.width() - badge_w - pad
    y = out.height() - badge_h - pad
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(28, 28, 28, 220))
    p.drawRoundedRect(x, y, badge_w, badge_h, 3, 3)
    p.setPen(QPen(QColor("#dddddd"), 1))
    f = QFont(p.font())
    f.setPointSize(8)
    f.setBold(True)
    p.setFont(f)
    p.drawText(QRect(x, y, badge_w, badge_h), Qt.AlignmentFlag.AlignCenter, kind)
    p.end()
    return out


def _draw_hdr_badge(pm: QPixmap, label: str) -> QPixmap:
    """HDR Phase 0: stamp a Tiger Orange pill in the TOP-right corner
    when a video is HDR (HDR10 / HLG / generic HDR). The pill is the
    only place a non-grey accent appears in the pool, so it reads
    immediately as "this clip needs special handling". Bottom-right
    stays reserved for the V/A kind badge."""
    if not label:
        return pm
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    f = QFont(p.font())
    f.setPointSize(7)
    f.setBold(True)
    p.setFont(f)
    fm = p.fontMetrics()
    text_w = fm.horizontalAdvance(label) + 10
    text_h = 14
    pad = 4
    x = out.width() - text_w - pad
    y = pad
    # Tiger Orange fill, white text — reuses the brand accent.
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#D85A30"))
    p.drawRoundedRect(x, y, text_w, text_h, 3, 3)
    p.setPen(QPen(QColor("#ffffff")))
    p.drawText(
        QRect(x, y, text_w, text_h),
        Qt.AlignmentFlag.AlignCenter, label,
    )
    p.end()
    return out


def _placeholder_pixmap(size: int = THUMB_SIZE) -> QPixmap:
    """Solid neutral-grey placeholder for files we couldn't decode."""
    pm = QPixmap(size, size)
    pm.fill(QColor("#222"))
    p = QPainter(pm)
    p.setPen(QColor("#666"))
    p.drawRect(0, 0, size - 1, size - 1)
    p.end()
    return pm


class _MediaPoolList(QListWidget):
    """``QListWidget`` subclass that exposes pool items as
    ``text/uri-list`` drags so any drop target which accepts OS file
    drops (the editor's track rows) receives them too.

    Drag initiation is wired directly from ``mousePressEvent`` /
    ``mouseMoveEvent`` because Qt's IconMode default startDrag path
    on PySide6 6.11 tends to swallow the gesture into rubber-band
    selection — items end up being selected instead of dragged.
    Owning the threshold + ``QDrag.exec()`` ourselves makes the
    behaviour deterministic regardless of view mode.
    """

    # Right-click landed on empty list space (no item under cursor).
    # The parent ``MediaPool`` listens and pops a "Load video..."
    # menu so the user has a discoverable alternative to drag-drop.
    empty_context_menu = Signal(QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._press_pos: QPoint | None = None
        self._press_item: QListWidgetItem | None = None

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # type: ignore[override]
        md = QMimeData()
        urls: list[QUrl] = []
        for item in items:
            path = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(path, str) and path:
                urls.append(QUrl.fromLocalFile(path))
        if urls:
            md.setUrls(urls)
        return md

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self._press_pos = pos
            self._press_item = self.itemAt(pos)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        # Manual drag-threshold check. The instant the cursor moves
        # past Qt's drag-distance from the press point AND the press
        # was on a real item, we hand off to ``_begin_drag``. After
        # that we eat the move event so the view doesn't also start
        # a rubber-band sweep from the same gesture.
        if (
            self._press_pos is not None
            and self._press_item is not None
            and (event.buttons() & Qt.MouseButton.LeftButton)
        ):
            from PySide6.QtWidgets import QApplication
            delta = (event.position().toPoint() - self._press_pos)
            if delta.manhattanLength() >= QApplication.startDragDistance():
                item = self._press_item
                self._press_pos = None
                self._press_item = None
                self._begin_drag(item)
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._press_pos = None
        self._press_item = None
        super().mouseReleaseEvent(event)

    def _begin_drag(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(path, str) or not path:
            return
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(self)
        drag.setMimeData(md)
        pm = item.icon().pixmap(THUMB_SIZE, THUMB_SIZE)
        if pm.isNull() or pm.width() == 0 or pm.height() == 0:
            pm = _placeholder_pixmap(THUMB_SIZE)
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(pm.width() // 2, pm.height() // 2))
        drag.exec(Qt.DropAction.CopyAction)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(event.pos())
        if item is None:
            self.empty_context_menu.emit(event.globalPos())
            event.accept()
            return
        super().contextMenuEvent(event)


class MediaPool(QWidget):
    """Imported-media list. Drop OS files in to register, drag items
    out to drop them on a track."""

    item_added = Signal(str)        # absolute file path
    item_removed = Signal(str)      # absolute file path
    popout_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Set of absolute paths already registered, so a second drop of
        # the same file is a no-op (no duplicates in the pool).
        self._registered: set[str] = set()

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._title_label = QLabel(tr("media_pool.title"))
        self._title_label.setStyleSheet(
            "font-weight: 600; color: palette(text);"
        )
        header.addWidget(self._title_label)
        header.addStretch(1)

        self._remove_btn = QPushButton(tr("media_pool.btn.remove"))
        self._remove_btn.setObjectName("ToolButton")
        self._remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._remove_btn.clicked.connect(self._on_remove_selected)
        header.addWidget(self._remove_btn)

        self._popout_btn = QPushButton("⛶")
        self._popout_btn.setObjectName("PreviewPopoutIcon")
        self._popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._popout_btn.setToolTip(tr("media_pool.popout.tooltip"))
        self._popout_btn.setFixedSize(28, 24)
        self._popout_btn.clicked.connect(self.popout_requested.emit)
        header.addWidget(self._popout_btn)
        root.addLayout(header)

        self._list = _MediaPoolList()
        self._list.empty_context_menu.connect(self._show_context_menu)
        self._list.setMinimumHeight(180)
        # Drag OUT only — pool items go to tracks, but tracks don't
        # send anything back, and we don't allow rearranging inside
        # the pool either. Without ``DragOnly`` the default
        # ``NoDragDrop`` mode swallows the drag-start gesture so
        # mouse-down on an item just changes selection.
        self._list.setDragEnabled(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._list.setDefaultDropAction(Qt.DropAction.CopyAction)
        # SingleSelection avoids the IconMode rubber-band that
        # competes with drag-out — clicking on or near an item
        # immediately selects it, no rectangular sweep.
        self._list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection,
        )
        self._list.setSelectionRectVisible(False)
        # Grid / icon mode — square thumbnails over a wrapped
        # filename. ``Static`` movement disables drag-rearranging
        # within the pool itself; the only drag we want is the one
        # OUT to a track.
        self._list.setViewMode(QListWidget.ViewMode.IconMode)
        self._list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self._list.setGridSize(QSize(GRID_W, GRID_H))
        self._list.setMovement(QListWidget.Movement.Static)
        self._list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._list.setUniformItemSizes(True)
        self._list.setSpacing(6)
        self._list.setWordWrap(True)
        self._list.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        # Empty-state hint visible until the first file lands.
        self._empty_label = QLabel(tr("media_pool.empty_hint"))
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            "color: palette(mid); font-style: italic; padding: 24px;"
        )
        root.addWidget(self._empty_label)
        root.addWidget(self._list, stretch=1)
        self._list.hide()

    # ---- public API ----

    def items(self) -> list[str]:
        """All registered file paths in pool order."""
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    def add_path(self, path: Path | str) -> bool:
        """Register a single media path. Returns True if added (False
        if duplicate or filtered out by extension)."""
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            return False
        if p.suffix.lower() not in MEDIA_EXTS:
            return False
        key = str(p)
        if key in self._registered:
            return False
        self._registered.add(key)

        kind = _kind_for_path(p)
        dur_ms = _probe_duration_ms(p)
        dur_str = _format_duration(dur_ms)
        # Filename on first line, duration as a small caption below.
        # The icon-mode grid wraps each entry's text under the icon,
        # so a real newline keeps duration on its own row.
        if dur_str:
            text = f"{p.name}\n{dur_str}"
        else:
            text = p.name
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setToolTip(f"{key}\n{dur_str}" if dur_str else key)
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        # Pick a thumbnail strategy by media kind: video → first frame,
        # audio → stylised waveform-bar placeholder. Stamp a V / A
        # badge on the corner so the kind reads at a glance.
        if kind == "V":
            thumb = _make_video_thumbnail(p) or _placeholder_pixmap()
        elif kind == "A":
            thumb = _make_audio_thumbnail(p)
        else:
            thumb = _placeholder_pixmap()
        thumb = _draw_kind_badge(thumb, kind)
        # HDR Phase 0: probe video files for HDR metadata and stamp
        # the badge. We only probe video (audio is never HDR) and only
        # once per file ingest. The probe spawns ``ffmpeg -i`` so it
        # adds ~150-300 ms per import; acceptable for Phase 0, will
        # move to a worker thread once HDR decode/preview lands.
        hdr_info = None
        if kind == "V":
            try:
                from app.hdr_probe import probe_hdr
                hdr_info = probe_hdr(p)
                if hdr_info.is_hdr:
                    thumb = _draw_hdr_badge(thumb, hdr_info.standard_label)
            except Exception:
                # Probe failure is non-fatal — clip still loads as SDR.
                hdr_info = None
        item.setIcon(QIcon(thumb))
        # Stash the probe result on the item so the workbench / future
        # decode paths can read it without re-probing.
        if hdr_info is not None:
            item.setData(Qt.ItemDataRole.UserRole + 1, hdr_info)
            if hdr_info.is_hdr:
                item.setToolTip(
                    f"{key}\n{dur_str}\n[{hdr_info.standard_label}] "
                    f"transfer={hdr_info.transfer or '?'}, "
                    f"primaries={hdr_info.primaries or '?'}, "
                    f"pixfmt={hdr_info.pix_fmt or '?'}\n"
                    "Note: preview decoded as SDR (HDR Phase 1 pending)"
                    if dur_str else
                    f"{key}\n[{hdr_info.standard_label}]"
                )
        self._list.addItem(item)
        self._refresh_empty_state()
        self.item_added.emit(key)
        return True

    def remove_path(self, path: str) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self._list.takeItem(i)
                self._registered.discard(path)
                self._refresh_empty_state()
                self.item_removed.emit(path)
                return

    def retranslate(self) -> None:
        self._title_label.setText(tr("media_pool.title"))
        self._remove_btn.setText(tr("media_pool.btn.remove"))
        self._popout_btn.setToolTip(tr("media_pool.popout.tooltip"))
        self._empty_label.setText(tr("media_pool.empty_hint"))

    # ---- DnD: accept OS file drops ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasUrls():
            for url in md.urls():
                if url.isLocalFile():
                    p = Path(url.toLocalFile())
                    if p.suffix.lower() in MEDIA_EXTS:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dragMoveEvent(self, event) -> None:
        # Same predicate as enter — keeps the drop cursor consistent
        # while hovering over the list.
        self.dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        if not md.hasUrls():
            event.ignore()
            return
        added_any = False
        for url in md.urls():
            if not url.isLocalFile():
                continue
            if self.add_path(url.toLocalFile()):
                added_any = True
        if added_any:
            event.acceptProposedAction()
        else:
            event.ignore()

    # ---- context menu / file dialog ----

    def contextMenuEvent(self, event) -> None:
        """Right-click on the panel itself (placeholder area when the
        pool is empty, or padding around the list). Forwards to the
        same handler the list uses for its empty-area right-clicks."""
        self._show_context_menu(event.globalPos())
        event.accept()

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        act_load = menu.addAction(tr("media_pool.menu.load_files"))
        chosen = menu.exec(global_pos)
        if chosen is act_load:
            self._open_file_dialog()

    def _open_file_dialog(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(MEDIA_EXTS))
        filter_str = f"{tr('media_pool.dialog.filter')} ({exts})"
        paths, _ = QFileDialog.getOpenFileNames(
            self, tr("media_pool.dialog.title"), "", filter_str,
        )
        for p in paths:
            self.add_path(p)

    # ---- internal ----

    def _on_remove_selected(self) -> None:
        for item in self._list.selectedItems():
            path = item.data(Qt.ItemDataRole.UserRole)
            row = self._list.row(item)
            self._list.takeItem(row)
            if isinstance(path, str):
                self._registered.discard(path)
                self.item_removed.emit(path)
        self._refresh_empty_state()

    def _refresh_empty_state(self) -> None:
        is_empty = self._list.count() == 0
        self._empty_label.setVisible(is_empty)
        self._list.setVisible(not is_empty)
