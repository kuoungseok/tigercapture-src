from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QPoint, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.capture import pil_to_qimage
from app.drawing import (
    DrawingCanvas,
    PaintDialog,
    SpeechBubble,
    SpeechBubbleItem,
    Sticker,
    StickerItem,
    Stroke,
    _sticker_active,
    compose_pil_bubbles,
    compose_pil_frame_with_overlays,
    compose_pil_stickers,
)
from app.foreground_tracker import ForegroundInfo
from app.i18n import tr
from app.modes import CaptureMode
from app.paths import open_in_explorer
from app.quick_paste import copy_file_to_clipboard, paste_into_window
from app.style import APP_QSS
from app.subtitles import SubtitlePanel


from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_BG_L1,
    COLOR_BG_L2,
    COLOR_BG_L3,
    COLOR_BORDER_SUBTLE,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)


EDITOR_EXTRA_QSS = f"""
QWidget#EditorRoot {{ background-color: {COLOR_BG_L3}; }}
QWidget#PreviewHost {{ background-color: {COLOR_BG_L1}; border-radius: 4px; }}
QLabel#FrameInfo {{ color: {COLOR_TEXT_SECONDARY}; font-size: 12px; font-weight: 600; }}
QLabel#OptionLabel {{ color: {COLOR_TEXT_TERTIARY}; font-size: 12px; }}
QLabel#EstLabel {{ color: {COLOR_ACCENT_BLUE}; font-size: 12px; font-weight: 700; }}
QWidget#TimelineHost {{ background-color: {COLOR_BG_L2}; border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: 4px; }}
"""

FPS_CHOICES = [5, 10, 15, 20, 24, 30, 48, 60]
SCALE_CHOICES = [(100, 1.0), (75, 0.75), (50, 0.5), (25, 0.25)]

# Palette caps for GIF export. 256 is the format ceiling and matches
# pre-1.4 behaviour; 64 is a sweet spot for screen-recording GIFs.
COLOR_CHOICES = [256, 128, 64, 32, 16]
# gifsicle --lossy levels. 0 means lossless (still applies -O3).
# 60 is the value TigerCapture shipped with through 1.3.
LOSSY_CHOICES = [
    (0,   "editor.opt.lossy.off"),
    (30,  "editor.opt.lossy.light"),
    (60,  "editor.opt.lossy.medium"),
    (80,  "editor.opt.lossy.strong"),
    (120, "editor.opt.lossy.aggressive"),
]


# File-size estimate correction factors. The legacy 0.45 byte/pixel
# heuristic in :meth:`GifEditorWindow._refresh_estimate` was anchored to
# the historical defaults (256 colours, gifsicle --lossy=60). These
# tables rescale the estimate when the user picks different settings.
# Numbers come from sampling typical screen-capture GIFs across the
# combinations and aren't analytically exact — good enough for "is this
# going to be 800 KB or 4 MB" decisions.
_COLOR_SIZE_FACTORS = {
    256: 1.00,
    128: 0.85,
    64:  0.65,
    32:  0.50,
    16:  0.35,
}
_LOSSY_SIZE_FACTORS = {
    0:   1.65,    # lossless — bigger than the lossy=60 baseline
    30:  1.30,
    60:  1.00,    # baseline (legacy default)
    80:  0.75,
    120: 0.50,
}


def _color_size_factor(max_colors: int) -> float:
    return _COLOR_SIZE_FACTORS.get(int(max_colors), 1.0)


def _lossy_size_factor(lossy: int) -> float:
    return _LOSSY_SIZE_FACTORS.get(int(lossy), 1.0)
THUMB_W = 96
THUMB_H = 54
THUMB_GAP = 4
TIMELINE_V_PAD = 10


def _fast_thumbnail_pil(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Fast thumbnail using Image.reduce() for large downscales."""
    w, h = img.size
    factor = min(w // max(1, target_w), h // max(1, target_h))
    if factor >= 2:
        try:
            small = img.reduce(factor)
        except Exception:
            small = img
    else:
        small = img
    thumb = small.copy()
    thumb.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    return thumb


class _ThumbnailGenThread(QThread):
    """Generates fast thumbnails in the background and emits them one by one.

    Emits ``thumb_ready(idx, PIL.Image)``. Main thread is responsible for
    converting to QPixmap (cheap) and installing into the timeline.
    """

    thumb_ready = Signal(int, object)
    all_done = Signal()

    def __init__(self, frames: list[Image.Image], target_w: int, target_h: int) -> None:
        super().__init__()
        self._frames = list(frames)
        self._w = target_w
        self._h = target_h
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        for i, f in enumerate(self._frames):
            if self._stop:
                return
            try:
                thumb = _fast_thumbnail_pil(f, self._w, self._h)
            except Exception:
                continue
            self.thumb_ready.emit(i, thumb)
        self.all_done.emit()


class FrameTimeline(QWidget):
    """Horizontal strip of frame thumbnails with selection and keyboard delete."""

    current_frame_changed = Signal(int)
    selection_changed = Signal(list)
    delete_requested = Signal()

    MIN_THUMB_W = 28
    MAX_THUMB_W = 260

    def __init__(self) -> None:
        super().__init__()
        self._thumbs: list[QPixmap | None] = []
        self._selected: set[int] = set()
        self._current: int = 0
        self._last_clicked: int | None = None
        self._thumb_w: int = THUMB_W  # per-instance, wheel-zoomable

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(THUMB_H + TIMELINE_V_PAD * 2 + 6)

    def frame_count(self) -> int:
        return len(self._thumbs)

    def set_thumbnails(self, thumbs: list[QPixmap | None]) -> None:
        self._thumbs = list(thumbs)
        self._selected.clear()
        self._last_clicked = None
        self._current = 0 if thumbs else -1
        self._resize_to_content()
        self.update()

    def set_thumbnail_at(self, idx: int, pix: QPixmap) -> None:
        if 0 <= idx < len(self._thumbs):
            self._thumbs[idx] = pix
            x = THUMB_GAP + idx * (self._thumb_w + THUMB_GAP)
            y = TIMELINE_V_PAD
            self.update(x - 1, y - 1, self._thumb_w + 2, THUMB_H + TIMELINE_V_PAD + 10)

    def _resize_to_content(self) -> None:
        total_w = THUMB_GAP + len(self._thumbs) * (self._thumb_w + THUMB_GAP)
        self.setMinimumWidth(max(total_w, 0))
        self.resize(max(total_w, 0), self.height())

    def wheelEvent(self, event) -> None:
        """Mouse wheel over the frame strip zooms thumbnail width (= timeline
        length). Ctrl or plain wheel both zoom — frame strip is horizontal
        only so there's no vertical scroll to conflict with."""
        delta = event.angleDelta().y()
        if delta == 0:
            return super().wheelEvent(event)
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_w = max(self.MIN_THUMB_W, min(self.MAX_THUMB_W, int(self._thumb_w * factor)))
        if new_w == self._thumb_w:
            event.accept()
            return
        self._thumb_w = new_w
        self._resize_to_content()
        self.update()
        event.accept()

    def remove_indices(self, indices: list[int]) -> None:
        if not indices:
            return
        index_set = set(indices)
        self._thumbs = [t for i, t in enumerate(self._thumbs) if i not in index_set]
        self._selected.clear()
        self._last_clicked = None
        if self._current >= len(self._thumbs):
            self._current = max(0, len(self._thumbs) - 1)
        self._resize_to_content()
        self.update()
        self.selection_changed.emit([])
        if self._current >= 0:
            self.current_frame_changed.emit(self._current)

    def set_current(self, idx: int) -> None:
        if self._thumbs and 0 <= idx < len(self._thumbs) and idx != self._current:
            self._current = idx
            self.update()
            self.current_frame_changed.emit(idx)

    def current_index(self) -> int:
        return self._current

    def selected_indices(self) -> list[int]:
        return sorted(self._selected)

    def _frame_at(self, pos: QPoint) -> int | None:
        x = pos.x() - THUMB_GAP
        if x < 0:
            return None
        cell = self._thumb_w + THUMB_GAP
        idx = x // cell
        if 0 <= idx < len(self._thumbs):
            xx = idx * cell
            if xx <= x < xx + self._thumb_w:
                return int(idx)
        return None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        for i, pix in enumerate(self._thumbs):
            x = THUMB_GAP + i * (self._thumb_w + THUMB_GAP)
            y = TIMELINE_V_PAD + 3
            if pix is None:
                painter.fillRect(x, y, self._thumb_w, THUMB_H, QColor(60, 60, 68))
            else:
                painter.drawPixmap(x, y, self._thumb_w, THUMB_H, pix)

            if i in self._selected:
                pen = QPen(QColor(0, 103, 192))
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x - 1, y - 1, self._thumb_w + 2, THUMB_H + 2)

            if i == self._current:
                pen = QPen(QColor(229, 70, 70))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(x, y - 4, x + self._thumb_w, y - 4)
                painter.drawLine(x, y + THUMB_H + 3, x + self._thumb_w, y + THUMB_H + 3)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        idx = self._frame_at(event.position().toPoint())
        if idx is None:
            return
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier and self._last_clicked is not None:
            lo, hi = min(self._last_clicked, idx), max(self._last_clicked, idx)
            self._selected = set(range(lo, hi + 1))
        elif mods & Qt.KeyboardModifier.ControlModifier:
            if idx in self._selected:
                self._selected.discard(idx)
            else:
                self._selected.add(idx)
            self._last_clicked = idx
        else:
            self._selected = {idx}
            self._last_clicked = idx
        self._current = idx
        self.selection_changed.emit(sorted(self._selected))
        self.current_frame_changed.emit(idx)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key == Qt.Key.Key_Delete and self._selected:
            self.delete_requested.emit()
            return
        if key == Qt.Key.Key_Left:
            self.set_current(max(0, self._current - 1))
            return
        if key == Qt.Key.Key_Right:
            self.set_current(min(len(self._thumbs) - 1, self._current + 1))
            return
        super().keyPressEvent(event)


class GifEditorWindow(QWidget):
    """Frame-by-frame editor for recorded clips.

    ``mode`` controls the visual identity and which save action is shown as
    the primary button. Both GIF and MP4 exports are always available, but
    the primary (blue) button matches the mode the user originally recorded
    in, so GIF-intent and video-intent recordings feel distinct.
    """

    save_requested = Signal(list, dict)
    save_mp4_requested = Signal(list, dict)
    send_to_pro_editor_requested = Signal(list, dict)

    def __init__(
        self,
        frames: list[Image.Image],
        fps: int,
        save_dir: Path,
        mode: CaptureMode = CaptureMode.GIF,
        controller=None,
    ) -> None:
        super().__init__()
        self._frames: list[Image.Image] = list(frames)
        self._fps = int(fps) if fps > 0 else 15
        self._save_dir = save_dir
        self._mode = mode
        self._controller = controller
        self._playback_timer = QTimer(self)
        self._playback_timer.timeout.connect(self._advance_playback)
        self._is_playing = False
        self._current_index = 0
        self._current_pixmap: QPixmap | None = None
        self._last_saved_path: Path | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._thumb_thread: _ThumbnailGenThread | None = None
        self._quick_paste_target: ForegroundInfo | None = None
        self._pending_quick_paste: bool = False
        self._pending_pro_editor: bool = False
        self._strokes: list[Stroke] = []
        self._bubbles: list[SpeechBubble] = []
        self._bubble_items: list[SpeechBubbleItem] = []
        self._stickers: list[Sticker] = []
        self._sticker_items: list[StickerItem] = []
        self._current_frame_pix: QPixmap | None = None

        self.setObjectName("EditorRoot")
        title_key = "editor.title.video" if mode is CaptureMode.VIDEO else "editor.title.gif"
        self.setWindowTitle(tr(title_key))
        self.resize(1140, 760)
        self.setStyleSheet(APP_QSS + EDITOR_EXTRA_QSS)

        self._build_ui()
        self._rebuild_from_frames()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        root.addLayout(self._build_toolbar())
        root.addWidget(self._build_preview(), stretch=1)

        self._paint_hint_label = QLabel(tr("paint.hint"))
        self._paint_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._paint_hint_label.setStyleSheet(
            "color: #6a6a6a; font-size: 11px; padding: 2px;"
        )
        root.addWidget(self._paint_hint_label)

        root.addWidget(self._build_info_row())
        root.addWidget(self._build_timeline())
        root.addLayout(self._build_options_row())

        self._subtitle_panel = SubtitlePanel(
            position_provider=lambda: self._current_time_ms()
        )
        self._subtitle_panel.subtitles_changed.connect(
            self._update_subtitle_overlay
        )
        root.addWidget(self._subtitle_panel)

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        if self._mode is CaptureMode.VIDEO:
            self.save_btn = QPushButton(tr("editor.btn.save_mp4"))
            self.save_btn.clicked.connect(self._on_save_mp4)
        else:
            self.save_btn = QPushButton(tr("editor.btn.save_gif"))
            self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setObjectName("PrimaryToolButton")
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.play_btn = QPushButton(tr("editor.btn.play"))
        self.play_btn.setObjectName("ToolButton")
        self.play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.play_btn.clicked.connect(self._toggle_playback)

        self.delete_btn = QPushButton(tr("editor.btn.delete"))
        self.delete_btn.setObjectName("ToolButton")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._delete_selected)
        self.delete_btn.setEnabled(False)

        self.folder_btn = QPushButton(tr("editor.btn.folder"))
        self.folder_btn.setObjectName("ToolButton")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.folder_btn.clicked.connect(self._on_open_folder)

        if self._mode is CaptureMode.VIDEO:
            self.pro_editor_btn = QPushButton(tr("editor.btn.pro_editor"))
            self.pro_editor_btn.setObjectName("ToolButton")
            self.pro_editor_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.pro_editor_btn.clicked.connect(self._on_send_to_pro_editor)
        else:
            self.pro_editor_btn = None

        self.quick_paste_btn = QPushButton(tr("editor.btn.quick_paste"))
        self.quick_paste_btn.setObjectName("ToolButton")
        self.quick_paste_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_paste_btn.clicked.connect(self._on_quick_paste)

        self.quick_paste_target_label = QLabel(tr("editor.quick_paste.no_target"))
        self.quick_paste_target_label.setObjectName("QuickPasteTarget")

        row.addWidget(self.save_btn)
        if self.pro_editor_btn is not None:
            row.addWidget(self.pro_editor_btn)
        row.addSpacing(8)
        row.addWidget(self.quick_paste_btn)
        row.addWidget(self.quick_paste_target_label)
        row.addSpacing(8)
        row.addWidget(self.play_btn)
        row.addWidget(self.delete_btn)
        row.addStretch(1)
        row.addWidget(self.folder_btn)
        return row

    def update_quick_paste_target(self, info: ForegroundInfo | None) -> None:
        self._quick_paste_target = info
        if info is None:
            self.quick_paste_target_label.setText(tr("editor.quick_paste.no_target"))
            self.quick_paste_btn.setEnabled(False)
            return
        self.quick_paste_target_label.setText(
            tr("editor.quick_paste.target", target=info.short_label)
        )
        self.quick_paste_btn.setEnabled(True)

    def _on_quick_paste(self) -> None:
        if not self._frames:
            return
        target = self._quick_paste_target
        if target is None:
            QMessageBox.information(
                self,
                tr("editor.quick_paste.error_title"),
                tr("editor.quick_paste.error_no_target"),
            )
            return
        if self._last_saved_path and self._last_saved_path.exists():
            self._execute_quick_paste(self._last_saved_path)
            return

        # Not saved yet — auto-save to default path, then paste
        suffix = ".mp4" if self._mode is CaptureMode.VIDEO else ".gif"
        default_name = self._suggested_name_mp4() if suffix == ".mp4" else self._suggested_name()
        out = self._save_dir / default_name
        options = {
            "fps": self._get_fps(),
            "scale": self._get_scale(),
            "max_colors": self._get_max_colors(),
            "lossy": self._get_lossy(),
            "output_path": out,
        }
        self._pending_quick_paste = True
        self._last_saved_path = out
        if self._mode is CaptureMode.VIDEO:
            self.save_mp4_requested.emit(self._composed_frames(), options)
        else:
            self.save_requested.emit(self._composed_frames(), options)

    def _execute_quick_paste(self, path: Path) -> None:
        target = self._quick_paste_target
        if target is None:
            return
        try:
            copy_file_to_clipboard(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                tr("editor.quick_paste.error_title"),
                str(exc),
            )
            return
        ok = paste_into_window(target.hwnd)
        if not ok:
            QMessageBox.information(
                self,
                tr("editor.quick_paste.error_title"),
                tr("editor.quick_paste.error_target_gone"),
            )

    def _build_preview(self) -> QWidget:
        host = QWidget()
        host.setObjectName("PreviewHost")
        self._preview_host = host
        layout = QVBoxLayout(host)
        layout.setContentsMargins(12, 12, 12, 12)

        self._preview_label = QLabel("")
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview_label.setToolTip(tr("paint.hint"))
        self._preview_label.installEventFilter(self)
        layout.addWidget(self._preview_label, stretch=1)

        # Drawing canvas overlay (click-through, tool=off)
        self._drawing_canvas = DrawingCanvas(
            get_time_ms=lambda: self._current_time_ms(),
            get_strokes=lambda: self._strokes,
            parent=host,
        )

        # Subtitle overlay (bottom-centered)
        self._subtitle_overlay = QLabel(host)
        self._subtitle_overlay.setStyleSheet(
            "QLabel { color: white; background-color: rgba(0,0,0,180); "
            "padding: 6px 14px; border-radius: 4px; "
            "font-size: 18px; font-weight: 600; }"
        )
        self._subtitle_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_overlay.setWordWrap(True)
        self._subtitle_overlay.hide()
        return host

    def _build_info_row(self) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)

        self._frame_info = QLabel("")
        self._frame_info.setObjectName("FrameInfo")
        layout.addWidget(self._frame_info)
        layout.addStretch(1)

        self._duration_info = QLabel("")
        self._duration_info.setObjectName("FrameInfo")
        layout.addWidget(self._duration_info)
        return host

    def _build_timeline(self) -> QWidget:
        self._timeline = FrameTimeline()
        self._timeline.current_frame_changed.connect(self._show_frame)
        self._timeline.selection_changed.connect(self._on_selection_changed)
        self._timeline.delete_requested.connect(self._delete_selected)

        scroll = QScrollArea()
        scroll.setObjectName("TimelineHost")
        scroll.setWidget(self._timeline)
        scroll.setWidgetResizable(False)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(THUMB_H + TIMELINE_V_PAD * 2 + 26)
        self._timeline_scroll = scroll
        return scroll

    def _build_options_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        fps_label = QLabel(tr("editor.opt.fps"))
        fps_label.setObjectName("OptionLabel")
        self.fps_combo = QComboBox()
        for fps in FPS_CHOICES:
            self.fps_combo.addItem(f"{fps}", userData=fps)
        self._set_combo_value(self.fps_combo, self._fps)
        self.fps_combo.currentIndexChanged.connect(self._refresh_estimate)

        scale_label = QLabel(tr("editor.opt.scale"))
        scale_label.setObjectName("OptionLabel")
        self.scale_combo = QComboBox()
        for pct, ratio in SCALE_CHOICES:
            self.scale_combo.addItem(f"{pct}%", userData=ratio)
        self._set_combo_value(self.scale_combo, 1.0)
        self.scale_combo.currentIndexChanged.connect(self._refresh_estimate)

        # Palette cap (compression option 1)
        colors_label = QLabel(tr("editor.opt.colors"))
        colors_label.setObjectName("OptionLabel")
        self.colors_combo = QComboBox()
        for c in COLOR_CHOICES:
            self.colors_combo.addItem(str(c), userData=c)
        self._set_combo_value(self.colors_combo, 256)
        self.colors_combo.currentIndexChanged.connect(self._refresh_estimate)

        # gifsicle --lossy level (compression option 2)
        lossy_label = QLabel(tr("editor.opt.lossy"))
        lossy_label.setObjectName("OptionLabel")
        self.lossy_combo = QComboBox()
        for level, key in LOSSY_CHOICES:
            self.lossy_combo.addItem(tr(key), userData=level)
        self._set_combo_value(self.lossy_combo, 60)
        self.lossy_combo.currentIndexChanged.connect(self._refresh_estimate)

        self.estimate_label = QLabel(tr("editor.info.estimate_empty"))
        self.estimate_label.setObjectName("EstLabel")

        row.addWidget(fps_label)
        row.addWidget(self.fps_combo)
        row.addSpacing(16)
        row.addWidget(scale_label)
        row.addWidget(self.scale_combo)
        row.addSpacing(16)
        row.addWidget(colors_label)
        row.addWidget(self.colors_combo)
        row.addSpacing(16)
        row.addWidget(lossy_label)
        row.addWidget(self.lossy_combo)
        row.addStretch(1)
        row.addWidget(self.estimate_label)
        return row

    @staticmethod
    def _set_combo_value(combo: QComboBox, value) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _rebuild_from_frames(self) -> None:
        placeholders: list[QPixmap | None] = [None] * len(self._frames)
        self._timeline.set_thumbnails(placeholders)
        if self._frames:
            self._current_index = 0
            self._timeline.set_current(0)
            self._show_frame(0)
        self._refresh_info()
        self._refresh_estimate()
        self._start_thumbnail_generation()
        # Tell the subtitle panel how long the clip is for time-input clamps.
        dur_ms = int(len(self._frames) * 1000 / max(1, self._get_fps()))
        if hasattr(self, "_subtitle_panel"):
            self._subtitle_panel.set_project_duration(dur_ms)

    def _start_thumbnail_generation(self) -> None:
        self._stop_thumbnail_thread()
        if not self._frames:
            return
        t = _ThumbnailGenThread(self._frames, THUMB_W, THUMB_H)
        t.thumb_ready.connect(self._on_thumb_ready)
        t.all_done.connect(self._on_thumbs_done)
        t.finished.connect(t.deleteLater)
        self._thumb_thread = t
        t.start()

    def _stop_thumbnail_thread(self) -> None:
        if self._thumb_thread is not None:
            self._thumb_thread.stop()
            self._thumb_thread.quit()
            self._thumb_thread.wait(300)
            self._thumb_thread = None

    def _on_thumb_ready(self, idx: int, thumb_pil: Image.Image) -> None:
        if idx >= len(self._frames):
            return
        qimg = pil_to_qimage(thumb_pil)
        pix = QPixmap.fromImage(qimg).scaled(
            THUMB_W,
            THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._timeline.set_thumbnail_at(idx, pix)

    def _on_thumbs_done(self) -> None:
        self._thumb_thread = None

    def _show_frame(self, idx: int) -> None:
        if not (0 <= idx < len(self._frames)):
            self._preview_label.clear()
            self._current_pixmap = None
            return
        self._current_index = idx
        qimg = pil_to_qimage(self._frames[idx])
        self._current_pixmap = QPixmap.fromImage(qimg)
        self._scale_preview_to_fit()
        self._refresh_info()
        self._update_subtitle_overlay()
        self._drawing_canvas.raise_()
        self._subtitle_overlay.raise_()
        self._drawing_canvas.update()
        self._update_bubble_visibility()

    def _scale_preview_to_fit(self) -> None:
        if self._current_pixmap is None:
            return
        avail = self._preview_host.size()
        scaled = self._current_pixmap.scaled(
            max(avail.width() - 24, 40),
            max(avail.height() - 24, 40),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(scaled)
        self._sync_overlay_to_video_rect()

    def _sync_overlay_to_video_rect(self) -> None:
        """Constrain drawing canvas to the actual pixmap rect inside the
        preview label so strokes can't spill into the letterbox area."""
        host = self._preview_host
        if self._current_pixmap is None or self._current_pixmap.isNull():
            self._drawing_canvas.setGeometry(
                0, 0, host.width(), host.height()
            )
            return
        # preview_label is the only thing in preview_host's layout, with
        # (12,12,12,12) margins. Its geometry in host coords is margin-offset.
        lg = self._preview_label.geometry()
        src_w, src_h = self._current_pixmap.width(), self._current_pixmap.height()
        if lg.width() <= 0 or lg.height() <= 0 or src_w <= 0 or src_h <= 0:
            return
        scale = min(lg.width() / src_w, lg.height() / src_h)
        vw = max(1, int(src_w * scale))
        vh = max(1, int(src_h * scale))
        vx = lg.x() + (lg.width() - vw) // 2
        vy = lg.y() + (lg.height() - vh) // 2
        self._drawing_canvas.setGeometry(vx, vy, vw, vh)
        self._reposition_subtitle_overlay()

    def _reposition_subtitle_overlay(self) -> None:
        host = self._preview_host
        if not self._subtitle_overlay.isVisible():
            return
        self._subtitle_overlay.adjustSize()
        ov_w = min(int(host.width() * 0.9), max(200, self._subtitle_overlay.width()))
        ov_h = self._subtitle_overlay.heightForWidth(ov_w)
        if ov_h <= 0:
            ov_h = self._subtitle_overlay.height()
        x = (host.width() - ov_w) // 2
        y = host.height() - ov_h - 14
        self._subtitle_overlay.setFixedWidth(ov_w)
        self._subtitle_overlay.move(max(0, x), max(0, y))

    def _current_time_ms(self) -> int:
        fps = max(1, self._get_fps())
        return int(self._current_index * 1000 / fps)

    def _update_subtitle_overlay(self) -> None:
        sub = self._subtitle_panel.active_subtitle(self._current_time_ms())
        if sub is None or not sub.text.strip():
            self._subtitle_overlay.hide()
            return
        self._subtitle_overlay.setText(sub.text)
        if sub.show_box:
            self._subtitle_overlay.setStyleSheet(
                "QLabel { color: white; background-color: rgba(0,0,0,180); "
                "padding: 6px 14px; border-radius: 4px; "
                "font-size: 18px; font-weight: 600; }"
            )
        else:
            self._subtitle_overlay.setStyleSheet(
                "QLabel { color: white; background-color: transparent; "
                "padding: 4px 10px; font-size: 20px; font-weight: 900; }"
            )
        self._reposition_subtitle_overlay()
        self._subtitle_overlay.show()

    def eventFilter(self, obj, event):
        if obj is self._preview_label and event.type() == event.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._open_paint_dialog()
                return True
            if event.button() == Qt.MouseButton.RightButton:
                self._show_preview_context_menu(event.globalPosition().toPoint())
                return True
        return super().eventFilter(obj, event)

    def _open_paint_dialog(self) -> None:
        if self._current_pixmap is None or self._current_pixmap.isNull():
            return
        was_playing = self._is_playing
        if was_playing:
            self._toggle_playback()

        # Hide preview bubble / sticker items while the dialog owns them
        for item in list(self._bubble_items):
            item.deleteLater()
        self._bubble_items.clear()
        for item in list(self._sticker_items):
            item.deleteLater()
        self._sticker_items.clear()

        dlg = PaintDialog(
            background_pixmap=self._current_pixmap,
            initial_strokes=self._strokes,
            time_ms=self._current_time_ms(),
            parent=self,
            initial_bubbles=self._bubbles,
            initial_stickers=self._stickers,
        )
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._strokes = dlg.result_strokes()
            self._bubbles = dlg.result_bubbles()
            self._stickers = dlg.result_stickers()
            self._drawing_canvas.update()
        for sticker in self._stickers:
            self._spawn_sticker_item(sticker)
        for bubble in self._bubbles:
            self._spawn_bubble_item(bubble)
        self._update_bubble_visibility()
        self._update_sticker_visibility()

    # ------------- speech bubbles -------------

    def _spawn_bubble_item(self, bubble: SpeechBubble) -> SpeechBubbleItem:
        item = SpeechBubbleItem(bubble, self._drawing_canvas)
        item.sync_to_parent()
        item.show()
        item.moved.connect(lambda it=item: it.sync_to_bubble())
        item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
        self._bubble_items.append(item)
        item.raise_()
        return item

    def _remove_bubble(self, bubble: SpeechBubble, item: SpeechBubbleItem) -> None:
        if bubble in self._bubbles:
            self._bubbles.remove(bubble)
        if item in self._bubble_items:
            self._bubble_items.remove(item)
        item.deleteLater()

    def _resync_bubbles_to_preview(self) -> None:
        for item in self._bubble_items:
            item.sync_to_parent()

    def _update_bubble_visibility(self) -> None:
        t = self._current_time_ms()
        for item in self._bubble_items:
            item.setVisible(item.bubble.start_ms <= t)

    # ------------- stickers -------------

    def _spawn_sticker_item(self, sticker: Sticker) -> StickerItem:
        item = StickerItem(sticker, self._drawing_canvas)
        item.sync_to_parent()
        item.show()
        item.moved.connect(lambda it=item: it.sync_to_sticker())
        item.deleted.connect(lambda it=item, s=sticker: self._remove_sticker(s, it))
        item.duplicated.connect(lambda s=sticker: self._duplicate_sticker(s))
        item.raise_requested.connect(lambda s=sticker: self._reorder_sticker(s, +1))
        item.lower_requested.connect(lambda s=sticker: self._reorder_sticker(s, -1))
        self._sticker_items.append(item)
        # Bubbles stay on top of stickers.
        for b_item in self._bubble_items:
            b_item.raise_()
        return item

    def _remove_sticker(self, sticker: Sticker, item: StickerItem) -> None:
        if sticker in self._stickers:
            self._stickers.remove(sticker)
        if item in self._sticker_items:
            self._sticker_items.remove(item)
        item.deleteLater()

    def _duplicate_sticker(self, sticker: Sticker) -> None:
        import copy
        dup = copy.deepcopy(sticker)
        dup.x_norm = min(0.95, dup.x_norm + 0.03)
        dup.y_norm = min(0.95, dup.y_norm + 0.03)
        current_max = max((s.z_index for s in self._stickers), default=0)
        dup.z_index = current_max + 1
        self._stickers.append(dup)
        self._spawn_sticker_item(dup)
        self._update_sticker_visibility()

    def _reorder_sticker(self, sticker: Sticker, direction: int) -> None:
        if direction > 0:
            sticker.z_index = max(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) + 1
        else:
            sticker.z_index = min(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) - 1
        self._sticker_items.sort(key=lambda it: int(it.sticker.z_index))
        for it in self._sticker_items:
            it.raise_()
        for b_item in self._bubble_items:
            b_item.raise_()

    def _resync_stickers_to_preview(self) -> None:
        for item in self._sticker_items:
            item.sync_to_parent()

    def _update_sticker_visibility(self) -> None:
        t = self._current_time_ms()
        for item in self._sticker_items:
            item.setVisible(_sticker_active(item.sticker, t))

    def _show_preview_context_menu(self, global_pos) -> None:
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        clear_action = menu.addAction(tr("paint.btn.clear_all"))
        clear_action.setEnabled(bool(self._strokes))
        chosen = menu.exec(global_pos)
        if chosen is clear_action:
            self._strokes.clear()
            self._drawing_canvas.update()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._scale_preview_to_fit()
        self._resync_bubbles_to_preview()
        self._resync_stickers_to_preview()

    def _refresh_info(self) -> None:
        n = len(self._frames)
        i = self._current_index
        if n == 0:
            self._frame_info.setText(tr("editor.info.frame_none"))
            self._duration_info.setText("")
            return
        duration_s = n / max(1, self._get_fps())
        self._frame_info.setText(tr("editor.info.frame_counter", current=i + 1, total=n))
        self._duration_info.setText(
            tr("editor.info.duration", seconds=duration_s, fps=self._get_fps())
        )

    def _refresh_estimate(self) -> None:
        self._refresh_info()
        n = len(self._frames)
        if n == 0:
            self.estimate_label.setText(tr("editor.info.estimate_empty"))
            return
        w, h = self._frames[0].size
        ratio = self._get_scale()
        scaled_w = int(w * ratio)
        scaled_h = int(h * ratio)
        # The 0.45 byte/pixel constant was calibrated against pre-1.4
        # output (256 colours + gifsicle --lossy=60). Apply correction
        # factors when the user picks a different palette cap or lossy
        # level so the estimate tracks real file size.
        per_frame_bytes = (scaled_w * scaled_h) * 0.45
        total = per_frame_bytes * n
        total *= _color_size_factor(self._get_max_colors())
        total *= _lossy_size_factor(self._get_lossy())
        self.estimate_label.setText(
            tr("editor.info.estimate", size=self._format_size(int(total)))
        )

    @staticmethod
    def _format_size(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        return f"{n / (1024 * 1024):.1f} MB"

    def _get_fps(self) -> int:
        return int(self.fps_combo.currentData() or self._fps)

    def _get_scale(self) -> float:
        return float(self.scale_combo.currentData() or 1.0)

    def _get_max_colors(self) -> int:
        # Defensive — if combo wasn't built (older window paths), keep
        # the historical 256-colour default.
        combo = getattr(self, "colors_combo", None)
        if combo is None:
            return 256
        return int(combo.currentData() or 256)

    def _get_lossy(self) -> int:
        combo = getattr(self, "lossy_combo", None)
        if combo is None:
            return 60
        # currentData() can be 0 (lossless) — must use ``is None`` check.
        data = combo.currentData()
        return 60 if data is None else int(data)

    def _on_selection_changed(self, indices: list[int]) -> None:
        self.delete_btn.setEnabled(bool(indices))

    def _delete_selected(self) -> None:
        indices = self._timeline.selected_indices()
        if not indices:
            return
        index_set = set(indices)
        self._stop_thumbnail_thread()
        self._frames = [f for i, f in enumerate(self._frames) if i not in index_set]
        self._timeline.remove_indices(indices)
        if self._frames:
            new_idx = min(self._current_index, len(self._frames) - 1)
            self._current_index = max(0, new_idx)
            self._show_frame(self._current_index)
        else:
            self._preview_label.clear()
            self._current_pixmap = None
            self._current_index = -1
        self._refresh_estimate()
        self._start_thumbnail_generation()

    def _toggle_playback(self) -> None:
        if not self._frames:
            return
        if self._is_playing:
            self._playback_timer.stop()
            self._is_playing = False
            self.play_btn.setText(tr("editor.btn.play"))
        else:
            interval = max(1, int(1000 / self._get_fps()))
            self._playback_timer.start(interval)
            self._is_playing = True
            self.play_btn.setText(tr("editor.btn.pause"))

    def _advance_playback(self) -> None:
        if not self._frames:
            self._playback_timer.stop()
            self._is_playing = False
            self.play_btn.setText(tr("editor.btn.play"))
            return
        next_idx = (self._current_index + 1) % len(self._frames)
        self._timeline.set_current(next_idx)

    def closeEvent(self, event) -> None:
        self._stop_thumbnail_thread()
        super().closeEvent(event)

    def _composed_frames(self) -> list[Image.Image]:
        """Return frames with strokes + subtitles + bubbles + stickers
        burned in."""
        if (
            not self._strokes
            and not self._subtitle_panel.subtitles()
            and not self._bubbles
            and not self._stickers
        ):
            return self._frames
        fps = max(1, self._get_fps())
        subs = self._subtitle_panel.subtitles()
        if self._frames:
            h = self._frames[0].size[1]
            width_scale = max(1.0, h / 720.0)
        else:
            width_scale = 1.0
        out = []
        for i, frame in enumerate(self._frames):
            t_ms = int(i * 1000 / fps)
            composed = compose_pil_frame_with_overlays(
                frame, self._strokes, subs, t_ms, width_scale=width_scale
            )
            # Stickers go beneath bubbles so captions stay legible.
            if self._stickers:
                composed = compose_pil_stickers(composed, self._stickers, t_ms)
            if self._bubbles:
                composed = compose_pil_bubbles(composed, self._bubbles, t_ms)
            out.append(composed)
        return out

    def _on_save(self) -> None:
        if not self._frames:
            QMessageBox.warning(
                self,
                tr("editor.dialog.save_fail_title"),
                tr("editor.dialog.save_fail_no_frames"),
            )
            return
        default = self._save_dir / self._suggested_name()
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("editor.dialog.gif_save_title"),
            str(default),
            tr("editor.dialog.gif_filter"),
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".gif":
            out = out.with_suffix(".gif")

        options = {
            "fps": self._get_fps(),
            "scale": self._get_scale(),
            "max_colors": self._get_max_colors(),
            "lossy": self._get_lossy(),
            "output_path": out,
        }
        self._last_saved_path = out
        self.save_requested.emit(self._composed_frames(), options)

    def _on_save_mp4(self) -> None:
        if not self._frames:
            QMessageBox.warning(
                self,
                tr("editor.dialog.save_fail_title"),
                tr("editor.dialog.save_fail_no_frames"),
            )
            return
        default = self._save_dir / self._suggested_name_mp4()
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("editor.dialog.mp4_save_title"),
            str(default),
            tr("editor.dialog.mp4_filter"),
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".mp4":
            out = out.with_suffix(".mp4")
        options = {
            "fps": self._get_fps(),
            "scale": self._get_scale(),
            "max_colors": self._get_max_colors(),
            "lossy": self._get_lossy(),
            "output_path": out,
        }
        self._last_saved_path = out
        self.save_mp4_requested.emit(self._composed_frames(), options)

    @staticmethod
    def _suggested_name_mp4() -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"tigercapture_{stamp}.mp4"

    def _on_open_folder(self) -> None:
        if self._last_saved_path and self._last_saved_path.exists():
            open_in_explorer(self._last_saved_path)
        else:
            open_in_explorer(self._save_dir)

    @staticmethod
    def _suggested_name() -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"tigercapture_{stamp}.gif"

    def _on_send_to_pro_editor(self) -> None:
        if not self._frames:
            return
        if self._last_saved_path and self._last_saved_path.exists():
            self.send_to_pro_editor_requested.emit(self._frames, {"output_path": self._last_saved_path})
            return
        out = self._save_dir / self._suggested_name_mp4()
        options = {
            "fps": self._get_fps(),
            "scale": self._get_scale(),
            "max_colors": self._get_max_colors(),
            "lossy": self._get_lossy(),
            "output_path": out,
        }
        self._pending_pro_editor = True
        self._last_saved_path = out
        self.save_mp4_requested.emit(self._composed_frames(), options)

    def notify_saved(self, path: Path) -> None:
        self._close_progress()
        self._last_saved_path = path
        if self._pending_quick_paste:
            self._pending_quick_paste = False
            self._execute_quick_paste(path)
            return
        if self._pending_pro_editor:
            self._pending_pro_editor = False
            self.send_to_pro_editor_requested.emit([], {"output_path": path})
            return
        QMessageBox.information(
            self,
            tr("editor.dialog.saved_title"),
            tr(
                "editor.dialog.saved_body",
                path=str(path),
                size=self._format_size(path.stat().st_size),
            ),
        )

    def notify_save_failed(self, message: str) -> None:
        self._close_progress()
        self._pending_quick_paste = False
        self._pending_pro_editor = False
        QMessageBox.critical(self, tr("editor.dialog.save_error_title"), message)

    def begin_export_progress(self, total_frames: int, kind: str = "gif") -> None:
        # Pick labels based on what is actually being saved so an MP4 export
        # doesn't show "Saving GIF" in the progress dialog.
        if kind == "mp4":
            title = tr("editor.progress.mp4_title")
            body = tr("editor.progress.mp4_body")
        else:
            title = tr("editor.progress.title")
            body = tr("editor.progress.body")
        self._progress_kind = kind
        dlg = QProgressDialog(
            body, None, 0, max(1, total_frames * 3), self,
        )
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
        dlg.setMinimumDuration(0)
        dlg.setAutoClose(False)
        dlg.setAutoReset(False)
        dlg.setCancelButton(None)
        dlg.setValue(0)
        dlg.show()
        self._progress_dialog = dlg

    def update_export_progress(self, current: int, total: int) -> None:
        if self._progress_dialog is not None:
            if self._progress_dialog.maximum() != total:
                self._progress_dialog.setMaximum(total)
            self._progress_dialog.setValue(current)

    def update_export_stage(self, stage: str) -> None:
        if self._progress_dialog is not None:
            key = (
                "editor.progress.mp4_with_stage"
                if getattr(self, "_progress_kind", "gif") == "mp4"
                else "editor.progress.with_stage"
            )
            self._progress_dialog.setLabelText(tr(key, stage=stage))

    def _close_progress(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
