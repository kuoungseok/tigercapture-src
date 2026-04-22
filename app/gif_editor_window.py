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
from app.foreground_tracker import ForegroundInfo
from app.i18n import tr
from app.modes import CaptureMode
from app.paths import open_in_explorer
from app.quick_paste import copy_file_to_clipboard, paste_into_window
from app.style import APP_QSS


EDITOR_EXTRA_QSS = """
QWidget#EditorRoot { background-color: #f3f3f3; }
QWidget#PreviewHost { background-color: #1e1e1e; border-radius: 4px; }
QLabel#FrameInfo { color: #3a3a3a; font-size: 12px; font-weight: 600; }
QLabel#OptionLabel { color: #5a5a5a; font-size: 12px; }
QLabel#EstLabel { color: #0067c0; font-size: 12px; font-weight: 700; }
QWidget#TimelineHost { background-color: #ffffff; border: 1px solid #e1e1e1; border-radius: 4px; }
"""

FPS_CHOICES = [5, 10, 15, 20, 24, 30, 48, 60]
SCALE_CHOICES = [(100, 1.0), (75, 0.75), (50, 0.5), (25, 0.25)]
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

    def __init__(self) -> None:
        super().__init__()
        self._thumbs: list[QPixmap | None] = []
        self._selected: set[int] = set()
        self._current: int = 0
        self._last_clicked: int | None = None

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
            x = THUMB_GAP + idx * (THUMB_W + THUMB_GAP)
            y = TIMELINE_V_PAD
            self.update(x - 1, y - 1, THUMB_W + 2, THUMB_H + TIMELINE_V_PAD + 10)

    def _resize_to_content(self) -> None:
        total_w = THUMB_GAP + len(self._thumbs) * (THUMB_W + THUMB_GAP)
        self.setMinimumWidth(max(total_w, 0))
        self.resize(max(total_w, 0), self.height())

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
        cell = THUMB_W + THUMB_GAP
        idx = x // cell
        if 0 <= idx < len(self._thumbs):
            xx = idx * cell
            if xx <= x < xx + THUMB_W:
                return int(idx)
        return None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        for i, pix in enumerate(self._thumbs):
            x = THUMB_GAP + i * (THUMB_W + THUMB_GAP)
            y = TIMELINE_V_PAD + 3
            if pix is None:
                painter.fillRect(x, y, THUMB_W, THUMB_H, QColor(230, 230, 230))
            else:
                painter.drawPixmap(x, y, THUMB_W, THUMB_H, pix)

            if i in self._selected:
                pen = QPen(QColor(0, 103, 192))
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(x - 1, y - 1, THUMB_W + 2, THUMB_H + 2)

            if i == self._current:
                pen = QPen(QColor(229, 70, 70))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(x, y - 4, x + THUMB_W, y - 4)
                painter.drawLine(x, y + THUMB_H + 3, x + THUMB_W, y + THUMB_H + 3)

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
        root.addWidget(self._build_info_row())
        root.addWidget(self._build_timeline())
        root.addLayout(self._build_options_row())

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
            "output_path": out,
        }
        self._pending_quick_paste = True
        self._last_saved_path = out
        if self._mode is CaptureMode.VIDEO:
            self.save_mp4_requested.emit(self._frames, options)
        else:
            self.save_requested.emit(self._frames, options)

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
        layout.addWidget(self._preview_label, stretch=1)
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

        self.estimate_label = QLabel(tr("editor.info.estimate_empty"))
        self.estimate_label.setObjectName("EstLabel")

        row.addWidget(fps_label)
        row.addWidget(self.fps_combo)
        row.addSpacing(16)
        row.addWidget(scale_label)
        row.addWidget(self.scale_combo)
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

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._scale_preview_to_fit()

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
        per_frame_bytes = (scaled_w * scaled_h) * 0.45
        total = per_frame_bytes * n
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
            "output_path": out,
        }
        self._last_saved_path = out
        self.save_requested.emit(self._frames, options)

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
            "output_path": out,
        }
        self._last_saved_path = out
        self.save_mp4_requested.emit(self._frames, options)

    @staticmethod
    def _suggested_name_mp4() -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"gifcam_{stamp}.mp4"

    def _on_open_folder(self) -> None:
        if self._last_saved_path and self._last_saved_path.exists():
            open_in_explorer(self._last_saved_path)
        else:
            open_in_explorer(self._save_dir)

    @staticmethod
    def _suggested_name() -> str:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return f"gifcam_{stamp}.gif"

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
            "output_path": out,
        }
        self._pending_pro_editor = True
        self._last_saved_path = out
        self.save_mp4_requested.emit(self._frames, options)

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

    def begin_export_progress(self, total_frames: int) -> None:
        dlg = QProgressDialog(
            tr("editor.progress.body"),
            None,
            0,
            max(1, total_frames * 3),
            self,
        )
        dlg.setWindowTitle(tr("editor.progress.title"))
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
            self._progress_dialog.setLabelText(
                tr("editor.progress.with_stage", stage=stage)
            )

    def _close_progress(self) -> None:
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
