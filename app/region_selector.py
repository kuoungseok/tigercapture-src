from __future__ import annotations

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPen,
    QScreen,
)
from PySide6.QtWidgets import QApplication, QWidget

from app.i18n import tr


DIM_COLOR = QColor(0, 0, 0, 110)
BORDER_COLOR = QColor(0, 103, 192)
LABEL_BG = QColor(0, 0, 0, 200)
LABEL_FG = QColor(255, 255, 255)
MIN_SELECTION_SIZE = 5
LABEL_MARGIN = 48


class _MonitorOverlay(QWidget):
    """Per-monitor overlay window. Reports mouse events in virtual-desktop
    global coordinates to the owning controller; paints dim + selection based
    on controller-provided global selection rect."""

    mouse_pressed = Signal(QPoint)
    mouse_moved = Signal(QPoint)
    mouse_released = Signal()
    escape_pressed = Signal()

    def __init__(self, screen: QScreen, show_hint: bool) -> None:
        super().__init__()
        self._screen = screen
        self._show_hint = show_hint
        self._selection_global: QRect = QRect()
        self._prev_selection_global: QRect = QRect()
        self._hover_global: QPoint | None = None
        self._prev_hint_rect_local: QRect = QRect()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def screen_geometry(self) -> QRect:
        return self._screen.geometry()

    def _global_to_local(self, global_rect: QRect) -> QRect:
        if global_rect.isEmpty():
            return QRect()
        origin = self._screen.geometry().topLeft()
        return QRect(
            global_rect.x() - origin.x(),
            global_rect.y() - origin.y(),
            global_rect.width(),
            global_rect.height(),
        )

    def _global_to_local_point(self, global_pos: QPoint) -> QPoint:
        origin = self._screen.geometry().topLeft()
        return QPoint(global_pos.x() - origin.x(), global_pos.y() - origin.y())

    def update_selection(self, new_global: QRect) -> None:
        screen_rect = self._screen.geometry()
        prev_clipped = self._prev_selection_global.intersected(screen_rect)
        new_clipped = new_global.intersected(screen_rect)
        self._prev_selection_global = new_global
        self._selection_global = new_global

        if prev_clipped.isEmpty() and new_clipped.isEmpty():
            return

        prev_local = self._global_to_local(prev_clipped)
        new_local = self._global_to_local(new_clipped)
        if prev_local.isEmpty():
            dirty = new_local
        elif new_local.isEmpty():
            dirty = prev_local
        else:
            dirty = prev_local.united(new_local)
        dirty = dirty.adjusted(-LABEL_MARGIN, -LABEL_MARGIN, LABEL_MARGIN, LABEL_MARGIN)
        self.update(dirty)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        clip = event.rect()
        full = self.rect()

        screen_rect = self._screen.geometry()
        sel_global_clipped = self._selection_global.intersected(screen_rect)
        sel_local = self._global_to_local(sel_global_clipped)

        has_selection_on_this_screen = not sel_local.isEmpty()

        if has_selection_on_this_screen:
            self._fill_strips_around(painter, full, sel_local, clip)

            if self._selection_global == sel_global_clipped:
                border = sel_local.adjusted(0, 0, -1, -1)
            else:
                border = sel_local
            pen = QPen(BORDER_COLOR)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(border)

            if self._selection_global == sel_global_clipped:
                self._draw_size_label(painter, sel_local, self._selection_global)
        else:
            if self._selection_global.isEmpty():
                painter.fillRect(clip, DIM_COLOR)
                if self._show_hint and self._hover_global is not None:
                    self._draw_hint_label(painter)
            else:
                painter.fillRect(clip, DIM_COLOR)

    @staticmethod
    def _fill_strips_around(
        painter: QPainter, full: QRect, sel: QRect, clip: QRect
    ) -> None:
        top = QRect(full.left(), full.top(), full.width(), sel.top() - full.top())
        bottom = QRect(
            full.left(),
            sel.top() + sel.height(),
            full.width(),
            full.top() + full.height() - (sel.top() + sel.height()),
        )
        left = QRect(full.left(), sel.top(), sel.left() - full.left(), sel.height())
        right = QRect(
            sel.left() + sel.width(),
            sel.top(),
            full.left() + full.width() - (sel.left() + sel.width()),
            sel.height(),
        )
        for strip in (top, bottom, left, right):
            if strip.width() <= 0 or strip.height() <= 0:
                continue
            inter = strip.intersected(clip)
            if not inter.isEmpty():
                painter.fillRect(inter, DIM_COLOR)

    def _draw_size_label(
        self, painter: QPainter, local_rect: QRect, global_rect: QRect
    ) -> None:
        text = f"{global_rect.width()} × {global_rect.height()}"
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        pad_x = 8
        pad_y = 4
        label_w = text_w + pad_x * 2
        label_h = text_h + pad_y * 2

        x = local_rect.left()
        y = local_rect.top() - label_h - 4
        if y < 0:
            y = local_rect.top() + 4
            x = local_rect.left() + 4
        x = max(0, min(x, self.width() - label_w))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(LABEL_BG)
        painter.drawRoundedRect(x, y, label_w, label_h, 4, 4)

        painter.setPen(LABEL_FG)
        painter.drawText(x + pad_x, y + pad_y + metrics.ascent(), text)

    def _draw_hint_label(self, painter: QPainter) -> None:
        assert self._hover_global is not None
        text = tr("region.hint")
        metrics = painter.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        text_h = metrics.height()
        pad_x = 10
        pad_y = 6
        label_w = text_w + pad_x * 2
        label_h = text_h + pad_y * 2

        cursor_local = self._global_to_local_point(self._hover_global)
        x = cursor_local.x() + 16
        y = cursor_local.y() + 16
        x = max(0, min(x, self.width() - label_w))
        y = max(0, min(y, self.height() - label_h))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(LABEL_BG)
        painter.drawRoundedRect(x, y, label_w, label_h, 4, 4)

        painter.setPen(LABEL_FG)
        painter.drawText(x + pad_x, y + pad_y + metrics.ascent(), text)

    def update_hover(self, global_pos: QPoint) -> None:
        if not self._show_hint:
            return
        screen_rect = self._screen.geometry()
        if not screen_rect.contains(global_pos):
            if self._hover_global is not None:
                prev_local = self._global_to_local_point(self._hover_global)
                dirty = QRect(prev_local.x() + 10, prev_local.y() + 10, 320, 50)
                self._hover_global = None
                self.update(dirty)
            return
        self._hover_global = global_pos
        cursor_local = self._global_to_local_point(global_pos)
        hint_rect = QRect(cursor_local.x() + 10, cursor_local.y() + 10, 320, 50)
        if not self._prev_hint_rect_local.isEmpty():
            dirty = hint_rect.united(self._prev_hint_rect_local)
        else:
            dirty = hint_rect
        self._prev_hint_rect_local = hint_rect
        self.update(dirty)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_pressed.emit(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self.mouse_moved.emit(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_released.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            return
        super().keyPressEvent(event)


class RegionSelectorOverlay(QObject):
    """Multi-monitor region selector. Creates one native overlay per QScreen
    so Windows per-monitor DPI cannot distort coordinates.

    Emits ``region_selected(QRect)`` in virtual-desktop global coordinates
    (as reported by ``QMouseEvent.globalPosition``), or ``cancelled()``.
    """

    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._overlays: list[_MonitorOverlay] = []
        self._origin_global: QPoint | None = None
        self._current_global: QPoint | None = None
        self._finished: bool = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(16)
        self._poll_timer.timeout.connect(self._poll_cursor)

    def _selection_rect_global(self) -> QRect:
        if self._origin_global is None or self._current_global is None:
            return QRect()
        x1, y1 = self._origin_global.x(), self._origin_global.y()
        x2, y2 = self._current_global.x(), self._current_global.y()
        return QRect(min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1))

    def start(self) -> None:
        primary = QGuiApplication.primaryScreen()
        for screen in QGuiApplication.screens():
            is_primary = screen is primary
            overlay = _MonitorOverlay(screen, show_hint=is_primary)
            overlay.mouse_pressed.connect(self._on_press)
            overlay.mouse_moved.connect(self._on_move)
            overlay.mouse_released.connect(self._on_release)
            overlay.escape_pressed.connect(self._on_escape)
            overlay.show()
            self._overlays.append(overlay)

        if self._overlays:
            first = self._overlays[0]
            first.raise_()
            first.activateWindow()
            first.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_press(self, global_pos: QPoint) -> None:
        if self._finished:
            return
        self._origin_global = global_pos
        self._current_global = global_pos
        self._broadcast_selection()
        self._poll_timer.start()

    def _on_move(self, global_pos: QPoint) -> None:
        if self._finished:
            return
        if self._origin_global is not None:
            self._current_global = global_pos
            self._broadcast_selection()
        else:
            for ov in self._overlays:
                ov.update_hover(global_pos)

    def _poll_cursor(self) -> None:
        if self._finished or self._origin_global is None:
            self._poll_timer.stop()
            return
        pos = QCursor.pos()
        if pos != self._current_global:
            self._current_global = pos
            self._broadcast_selection()

    def _on_release(self) -> None:
        if self._finished or self._origin_global is None:
            return
        self._poll_timer.stop()
        rect = self._selection_rect_global()
        self._finished = True
        if rect.width() >= MIN_SELECTION_SIZE and rect.height() >= MIN_SELECTION_SIZE:
            self.region_selected.emit(rect)
        else:
            self.cancelled.emit()
        self._close_all()

    def _on_escape(self) -> None:
        if self._finished:
            return
        self._poll_timer.stop()
        self._finished = True
        self.cancelled.emit()
        self._close_all()

    def _broadcast_selection(self) -> None:
        rect = self._selection_rect_global()
        for ov in self._overlays:
            ov.update_selection(rect)

    def _close_all(self) -> None:
        overlays = self._overlays
        self._overlays = []
        for ov in overlays:
            ov.close()


def capture_region_blocking() -> QRect | None:
    """Convenience helper for tests/ad-hoc: blocks via a local event loop."""
    from PySide6.QtCore import QEventLoop

    app = QApplication.instance() or QApplication([])
    loop = QEventLoop()
    result: dict[str, QRect | None] = {"rect": None}

    overlay = RegionSelectorOverlay()

    def on_selected(rect: QRect) -> None:
        result["rect"] = rect
        loop.quit()

    def on_cancelled() -> None:
        result["rect"] = None
        loop.quit()

    overlay.region_selected.connect(on_selected)
    overlay.cancelled.connect(on_cancelled)
    overlay.start()
    loop.exec()
    _ = app
    return result["rect"]
