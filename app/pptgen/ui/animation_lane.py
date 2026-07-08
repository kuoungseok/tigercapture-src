"""Slide-level PPT animation timing lane widget."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.pptgen.animation_lanes import AnimationLaneRow, adjust_animation_timing, animation_lane_rows_for_slide
from app.pptgen.schema import DeckSpec, SlideSpec


def _ui_font(point_size: int, bold: bool = False) -> QFont:
    font = QFont()
    font.setPointSize(max(7, int(point_size)))
    font.setBold(bool(bold))
    return font


class AnimationLaneWidget(QWidget):
    animationSelected = Signal(str, int)
    animationTimingChanged = Signal(str, int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.deck: DeckSpec | None = None
        self.slide: SlideSpec | None = None
        self.selected_element_id = ""
        self.local_playhead_ms = 0
        self.slide_duration_ms = 5000
        self._rows: list[AnimationLaneRow] = []
        self._drag_mode = ""
        self._drag_element_id = ""
        self._drag_start_x = 0
        self._drag_start_ms = 0
        self._drag_duration_ms = 0
        self.setObjectName("PptAnimationLaneWidget")
        self.setMinimumHeight(104)
        self.setMouseTracking(True)

    def set_context(
        self,
        deck: DeckSpec,
        slide: SlideSpec | None,
        *,
        selected_element_id: str = "",
        local_playhead_ms: int = 0,
        slide_duration_ms: int = 5000,
    ) -> None:
        self.deck = deck
        self.slide = slide
        self.selected_element_id = str(selected_element_id or "")
        self.local_playhead_ms = max(0, int(local_playhead_ms or 0))
        self.slide_duration_ms = max(1, int(slide_duration_ms or getattr(slide, "duration_ms", 5000) or 5000))
        self._rows = animation_lane_rows_for_slide(slide)
        visible_rows = max(2, min(5, max(1, len(self._rows))))
        self.setMinimumHeight(52 + visible_rows * 24)
        self.update()

    def _clear_drag(self) -> None:
        self._drag_mode = ""
        self._drag_element_id = ""
        self._drag_start_x = 0
        self._drag_start_ms = 0
        self._drag_duration_ms = 0

    def _metrics(self) -> tuple[int, int, int, int]:
        left = 130
        right = max(left + 1, self.width() - 16)
        top = 32
        row_h = 22
        return left, right, top, row_h

    def _row_rects(self) -> list[tuple[AnimationLaneRow, QRect]]:
        left, right, top, row_h = self._metrics()
        width = max(1, right - left)
        rows: list[tuple[AnimationLaneRow, QRect]] = []
        for index, row in enumerate(self._rows):
            x = left + int(width * max(0, row.start_ms) / self.slide_duration_ms)
            end_x = left + int(width * min(self.slide_duration_ms, max(row.start_ms + 1, row.end_ms)) / self.slide_duration_ms)
            y = top + index * row_h
            rows.append((row, QRect(x, y + 3, max(5, end_x - x), row_h - 6)))
        return rows

    def _delta_ms_for_x(self, x: int) -> int:
        left, right, _top, _row_h = self._metrics()
        return int(round((int(x) - int(self._drag_start_x)) * self.slide_duration_ms / max(1, right - left)))

    def _drag_row(self) -> AnimationLaneRow | None:
        for row in self._rows:
            if row.element_id != self._drag_element_id:
                continue
            return AnimationLaneRow(
                slide_id=row.slide_id,
                element_id=row.element_id,
                element_name=row.element_name,
                element_kind=row.element_kind,
                effect=row.effect,
                trigger=row.trigger,
                click_index=row.click_index,
                start_ms=int(self._drag_start_ms),
                duration_ms=int(self._drag_duration_ms),
                end_ms=int(self._drag_start_ms) + int(self._drag_duration_ms),
                z_index=row.z_index,
                lane_index=row.lane_index,
            )
        return None

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._rows:
            return
        pos = event.position().toPoint() if hasattr(event, "position") else QPoint(event.x(), event.y())
        for row, rect in self._row_rects():
            hit = rect.adjusted(-4, -4, 4, 4)
            label_hit = QRect(8, rect.y() - 2, 118, rect.height() + 4)
            if hit.contains(pos):
                edge = max(6, min(10, rect.width() // 3))
                if abs(pos.x() - rect.left()) <= edge:
                    self._drag_mode = "trim_start"
                elif abs(pos.x() - rect.right()) <= edge:
                    self._drag_mode = "trim_end"
                else:
                    self._drag_mode = "move"
                self._drag_element_id = row.element_id
                self._drag_start_x = int(pos.x())
                self._drag_start_ms = int(row.start_ms)
                self._drag_duration_ms = int(row.duration_ms)
                self.animationSelected.emit(row.element_id, row.start_ms)
                return
            if label_hit.contains(pos):
                self._clear_drag()
                self.animationSelected.emit(row.element_id, row.start_ms)
                return
        left, right, top, row_h = self._metrics()
        if top - 8 <= pos.y() <= top + max(1, len(self._rows)) * row_h + 8 and left <= pos.x() <= right:
            local = int(self.slide_duration_ms * (pos.x() - left) / max(1, right - left))
            element_id = self.selected_element_id or self._rows[0].element_id
            self.animationSelected.emit(element_id, max(0, min(self.slide_duration_ms, local)))

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position().toPoint() if hasattr(event, "position") else QPoint(event.x(), event.y())
        if not self._drag_mode:
            cursor = Qt.CursorShape.ArrowCursor
            for _row, rect in self._row_rects():
                if not rect.adjusted(-4, -4, 4, 4).contains(pos):
                    continue
                edge = max(6, min(10, rect.width() // 3))
                cursor = Qt.CursorShape.SizeHorCursor if abs(pos.x() - rect.left()) <= edge or abs(pos.x() - rect.right()) <= edge else Qt.CursorShape.OpenHandCursor
                break
            self.setCursor(cursor)
            return
        row = self._drag_row()
        if row is None:
            return
        start_ms, duration_ms = adjust_animation_timing(
            row,
            self._delta_ms_for_x(int(pos.x())),
            self._drag_mode,
            self.slide_duration_ms,
        )
        self.animationTimingChanged.emit(row.element_id, int(start_ms), int(duration_ms))

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        if self._drag_mode:
            self._clear_drag()
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#12141A"))
        left, right, top, row_h = self._metrics()
        width = max(1, right - left)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(_ui_font(9, True))
        painter.drawText(12, 10, 150, 16, int(Qt.AlignmentFlag.AlignLeft), "Animation Lanes")
        painter.setPen(QColor("#8A8A8A"))
        painter.setFont(_ui_font(8))
        painter.drawText(right - 96, 10, 96, 14, int(Qt.AlignmentFlag.AlignRight), f"{self.slide_duration_ms / 1000:.1f}s")

        ruler_y = 25
        painter.setPen(QPen(QColor("#2C3038"), 1))
        painter.drawLine(left, ruler_y, right, ruler_y)
        tick_step = 500 if self.slide_duration_ms <= 6000 else 1000
        for tick in range(0, self.slide_duration_ms + tick_step, tick_step):
            x = left + int(width * min(tick, self.slide_duration_ms) / self.slide_duration_ms)
            major = tick % 1000 == 0
            painter.setPen(QPen(QColor("#444A56" if major else "#2C3038"), 1))
            painter.drawLine(x, ruler_y - (6 if major else 3), x, ruler_y + (6 if major else 3))
            if major:
                painter.setPen(QColor("#8A8A8A"))
                painter.setFont(_ui_font(7))
                painter.drawText(x - 18, 5, 36, 12, int(Qt.AlignmentFlag.AlignCenter), f"{tick / 1000:.0f}s")

        if not self._rows:
            painter.setPen(QColor("#707783"))
            painter.setFont(_ui_font(8))
            painter.drawText(12, 42, max(1, self.width() - 24), 28, int(Qt.AlignmentFlag.AlignLeft), "No animated elements on this slide")
        else:
            for row, rect in self._row_rects():
                y = rect.y()
                selected = row.element_id == self.selected_element_id
                painter.setPen(QColor("#6F7787"))
                painter.setFont(_ui_font(8, selected))
                label = f"{row.element_name}"
                painter.drawText(10, y - 1, 112, rect.height() + 4, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), label)
                painter.setPen(QPen(QColor("#272B34"), 1))
                painter.drawLine(left, y + rect.height() // 2, right, y + rect.height() // 2)
                color = QColor("#D85A30" if selected else "#2F6FED")
                if row.trigger == "on_click":
                    color = QColor("#8B5CF6" if not selected else "#D85A30")
                painter.setBrush(color)
                painter.setPen(QPen(QColor("#F5F7FA" if selected else "#0E1117"), 1))
                painter.drawRoundedRect(rect, 5, 5)
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(_ui_font(7, True))
                prefix = f"#{row.click_index} " if row.trigger == "on_click" and row.click_index > 0 else ""
                text = f"{prefix}{row.effect}  {row.start_ms}ms"
                painter.drawText(rect.adjusted(6, 0, -4, 0), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)

        play_x = left + int(width * min(self.slide_duration_ms, self.local_playhead_ms) / self.slide_duration_ms)
        bottom = max(top + 28, top + max(1, len(self._rows)) * row_h + 10)
        painter.setPen(QPen(QColor("#D85A30"), 2))
        painter.drawLine(play_x, ruler_y - 8, play_x, bottom)
        painter.setBrush(QColor("#D85A30"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon([
            QPoint(play_x - 5, ruler_y - 9),
            QPoint(play_x + 5, ruler_y - 9),
            QPoint(play_x, ruler_y - 2),
        ])


__all__ = ["AnimationLaneWidget"]
