"""Standalone PySide window for the user PPT generator."""
from __future__ import annotations

import copy
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QColorDialog,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.pptgen.fonts import recommended_font_families
from app.pptgen.asset_bridge import slide_element_from_media_asset, slide_element_from_typography
from app.pptgen.assets import add_deck_asset, insert_deck_asset_to_slide, list_deck_assets, remove_deck_asset
from app.pptgen.animations import (
    ANIMATION_EASINGS,
    ANIMATION_TRIGGERS,
    ANIMATION_TYPES,
    animation_payload,
    set_element_animation,
)
from app.pptgen.actor_posters import ensure_actor_poster, ensure_deck_actor_posters
from app.pptgen.animation_runtime import animated_rect, ease_progress, element_animation_state
from app.pptgen.autosave import (
    delete_ppt_recovery_file,
    list_ppt_recovery_candidates,
    ppt_autosave_path,
    save_ppt_autosave,
)
from app.pptgen.drag_payloads import (
    has_ppt_drag_payload,
    timeline_clip_payload_from_mime,
    typography_payload_from_mime,
)
from app.pptgen.editor_bridge import deck_from_editor_timeline
from app.pptgen.editing import align_element, duplicate_element, set_element_z_order, unique_element_id
from app.pptgen.formula import evaluate_numeric_formula, format_formula_value
from app.pptgen.history import PptHistoryStack, deck_from_history_snapshot
from app.pptgen.import_pptx import import_pptx_deck
from app.pptgen.overlays import header_footer_settings, set_header_footer, slide_overlay_elements
from app.pptgen.pdf_export import export_deck_pdf
from app.pptgen.preview import render_contact_sheet, render_deck_pngs
from app.pptgen.project_io import PPTGEN_PROJECT_FILTER, load_deck_project, save_deck_project
from app.pptgen.sample import create_sample_deck
from app.pptgen.schema import DeckSpec, ElementStyle, SlideElement, SlideSpec
from app.pptgen.templates import apply_template_to_slide
from app.pptgen.timeline import PptTimeline, add_slide, move_slide, remove_slide
from app.pptgen.ui.data_editor import edit_chart_data, edit_table_data
from app.pptgen.ui.animation_lane import AnimationLaneWidget
from app.pptgen.ui.media_panel import PptMediaPoolPanel
from app.pptgen.ui.style import PPT_EDITOR_QSS
from app.pptgen.ui.template_gallery import choose_template_id, deck_from_selected_template
from app.pptgen.ui.video_export_worker import PptVideoExportWorker
from app.pptgen.validation import validate_deck, validation_report
from app.pptgen.writer_python_pptx import write_pptx_compatible


def _ui_font(
    point_size: int,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    family: str = "",
    letter_spacing: float = 0.0,
) -> QFont:
    font = QFont(family) if family else QFont()
    font.setPointSize(max(7, int(point_size)))
    font.setBold(bool(bold))
    font.setItalic(bool(italic))
    font.setUnderline(bool(underline))
    if letter_spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, float(letter_spacing))
    return font


class SlideCanvas(QWidget):
    selectedElementChanged = Signal(str)
    slideContentChanged = Signal()
    deleteRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.deck: DeckSpec | None = None
        self.slide: SlideSpec | None = None
        self.selected_element_id = ""
        self.playhead_ms = 0
        self._drag_mode = ""
        self._drag_handle = ""
        self._drag_element_id = ""
        self._drag_start_px = (0.0, 0.0)
        self._drag_start_rect = (0.0, 0.0, 0.0, 0.0)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_slide(
        self,
        deck: DeckSpec,
        slide: SlideSpec | None,
        selected_element_id: str = "",
        *,
        playhead_ms: int = 0,
    ) -> None:
        self.deck = deck
        self.slide = slide
        self.selected_element_id = selected_element_id
        self.playhead_ms = max(0, int(playhead_ms or 0))
        self.update()

    def _slide_rect(self):
        margin = 28
        aw = max(1, self.width() - margin * 2)
        ah = max(1, self.height() - margin * 2)
        scale = min(aw / 16.0, ah / 9.0)
        sw = int(16 * scale)
        sh = int(9 * scale)
        return (int((self.width() - sw) / 2), int((self.height() - sh) / 2), sw, sh)

    def _element_rect(self, element: SlideElement) -> tuple[int, int, int, int]:
        left, top, sw, sh = self._slide_rect()
        return (
            left + int(element.x * sw),
            top + int(element.y * sh),
            int(element.w * sw),
            int(element.h * sh),
        )

    def _ease(self, value: float, easing: str) -> float:
        return ease_progress(value, easing)

    def _animation_state(self, element: SlideElement) -> dict[str, float | bool]:
        return element_animation_state(element, int(self.playhead_ms)).to_dict()

    def _animated_rect(self, element: SlideElement, rect: tuple[int, int, int, int] | None = None) -> tuple[int, int, int, int]:
        _left, _top, sw, sh = self._slide_rect()
        state = element_animation_state(element, int(self.playhead_ms))
        return animated_rect(rect or self._element_rect(element), (sw, sh), state)

    def _event_pos(self, event) -> tuple[float, float]:
        return (
            float(event.position().x()) if hasattr(event, "position") else float(event.x()),
            float(event.position().y()) if hasattr(event, "position") else float(event.y()),
        )

    def _selected_element(self) -> SlideElement | None:
        if not self.slide or not self.selected_element_id:
            return None
        for element in self.slide.elements:
            if element.id == self.selected_element_id:
                return element
        return None

    def _resize_handles(self, element: SlideElement) -> dict[str, tuple[int, int, int, int]]:
        x, y, w, h = self._element_rect(element)
        size = 9
        half = size // 2
        cx = x + w // 2
        cy = y + h // 2
        right = x + w
        bottom = y + h
        points = {
            "nw": (x, y),
            "n": (cx, y),
            "ne": (right, y),
            "e": (right, cy),
            "se": (right, bottom),
            "s": (cx, bottom),
            "sw": (x, bottom),
            "w": (x, cy),
        }
        return {name: (px - half, py - half, size, size) for name, (px, py) in points.items()}

    def _hit_resize_handle(self, px: float, py: float) -> str:
        element = self._selected_element()
        if not element or element.locked:
            return ""
        for name, (x, y, w, h) in self._resize_handles(element).items():
            if x <= px <= x + w and y <= py <= y + h:
                return name
        return ""

    def _begin_drag(self, mode: str, element: SlideElement, px: float, py: float, *, handle: str = "") -> None:
        if element.locked:
            return
        self._drag_mode = mode
        self._drag_handle = handle
        self._drag_element_id = element.id
        self._drag_start_px = (float(px), float(py))
        self._drag_start_rect = (float(element.x), float(element.y), float(element.w), float(element.h))

    def _clear_drag(self) -> None:
        self._drag_mode = ""
        self._drag_handle = ""
        self._drag_element_id = ""

    def _drag_element(self) -> SlideElement | None:
        if not self.slide or not self._drag_element_id:
            return None
        for element in self.slide.elements:
            if element.id == self._drag_element_id:
                return element
        return None

    def _apply_drag(self, element: SlideElement, px: float, py: float) -> None:
        _left, _top, sw, sh = self._slide_rect()
        start_x, start_y = self._drag_start_px
        dx = (float(px) - start_x) / max(1, sw)
        dy = (float(py) - start_y) / max(1, sh)
        ox, oy, ow, oh = self._drag_start_rect
        if self._drag_mode == "move":
            element.x = max(0.0, min(1.0 - ow, ox + dx))
            element.y = max(0.0, min(1.0 - oh, oy + dy))
        elif self._drag_mode == "resize":
            min_w = 0.02
            min_h = 0.01 if element.kind == "line" else 0.02
            left = ox
            top = oy
            right = ox + ow
            bottom = oy + oh
            if "w" in self._drag_handle:
                left = max(0.0, min(right - min_w, ox + dx))
            if "e" in self._drag_handle:
                right = min(1.0, max(left + min_w, ox + ow + dx))
            if "n" in self._drag_handle:
                top = max(0.0, min(bottom - min_h, oy + dy))
            if "s" in self._drag_handle:
                bottom = min(1.0, max(top + min_h, oy + oh + dy))
            element.x = left
            element.y = top
            element.w = max(min_w, right - left)
            element.h = max(min_h, bottom - top)
        self.update()

    def _drop_position(self, px: float, py: float, w: float, h: float) -> tuple[float, float]:
        left, top, sw, sh = self._slide_rect()
        x = (float(px) - left) / max(1, sw)
        y = (float(py) - top) / max(1, sh)
        return max(0.0, min(1.0 - w, x)), max(0.0, min(1.0 - h, y))

    def _mime_has_supported_asset(self, mime) -> bool:
        if has_ppt_drag_payload(mime):
            return True
        if mime.hasUrls():
            return any(url.isLocalFile() for url in mime.urls())
        if mime.hasText() and str(mime.text() or "").strip():
            return True
        return False

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._mime_has_supported_asset(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if not self.slide:
            event.ignore()
            return
        mime = event.mimeData()
        px, py = self._event_pos(event)
        created = self._add_elements_from_mime(mime, px, py)
        if not created:
            event.ignore()
            return
        self.selected_element_id = created[-1].id
        self.selectedElementChanged.emit(self.selected_element_id)
        self.slideContentChanged.emit()
        event.acceptProposedAction()

    def _add_elements_from_mime(self, mime, px: float, py: float) -> list[SlideElement]:
        if not self.slide:
            return []
        created: list[SlideElement] = []
        start_index = len(self.slide.elements) + 1
        timeline_payload = timeline_clip_payload_from_mime(mime)
        typography_payload = typography_payload_from_mime(mime)
        if timeline_payload is not None:
            source_path = str(timeline_payload.get("source_path") or "").strip()
            element_id = f"{self.slide.id}-timeline-{start_index}"
            if source_path:
                probe = slide_element_from_media_asset(
                    source_path,
                    element_id,
                    source="editor_timeline_drag",
                )
                x, y = self._drop_position(px, py, probe.w, probe.h)
                element = slide_element_from_media_asset(
                    source_path,
                    element_id,
                    x=x,
                    y=y,
                    source="editor_timeline_drag",
                )
            else:
                x, y = self._drop_position(px, py, 0.54, 0.34)
                element = SlideElement(
                    id=element_id,
                    kind="timeline_moment",
                    name=str(timeline_payload.get("label") or "Timeline clip"),
                    x=x,
                    y=y,
                    w=0.54,
                    h=0.34,
                    style=ElementStyle(fill="#F3F6FA", stroke="#D85A30", stroke_width=1.2, color="#182033", font_size=18),
                )
            element.metadata.update(
                {
                    "source": "editor_timeline_drag",
                    "track_id": timeline_payload.get("track_id"),
                    "clip_id": timeline_payload.get("clip_id"),
                    "timeline_in_ms": timeline_payload.get("timeline_in_ms"),
                    "duration_ms": timeline_payload.get("duration_ms"),
                    "source_in_ms": timeline_payload.get("source_in_ms"),
                    "source_out_ms": timeline_payload.get("source_out_ms"),
                }
            )
            self.slide.add_element(element)
            created.append(element)
        elif typography_payload is not None:
            probe = slide_element_from_typography(typography_payload, f"{self.slide.id}-typo-{start_index}")
            x, y = self._drop_position(px, py, probe.w, probe.h)
            element = slide_element_from_typography(
                typography_payload,
                f"{self.slide.id}-typo-{start_index}",
                x=x,
                y=y,
                source="editor_typography_drag",
            )
            self.slide.add_element(element)
            created.append(element)
        elif mime.hasUrls():
            for offset, url in enumerate(mime.urls()):
                if not url.isLocalFile():
                    continue
                element_id = f"{self.slide.id}-asset-{start_index + offset}"
                probe = slide_element_from_media_asset(url.toLocalFile(), element_id)
                x, y = self._drop_position(px + offset * 18, py + offset * 18, probe.w, probe.h)
                element = slide_element_from_media_asset(url.toLocalFile(), element_id, x=x, y=y)
                if self.deck is not None:
                    add_deck_asset(self.deck, url.toLocalFile(), kind=element.kind, source="canvas_drop")
                self.slide.add_element(element)
                created.append(element)
        elif mime.hasText() and str(mime.text() or "").strip():
            probe = slide_element_from_typography({"text": mime.text()}, f"{self.slide.id}-typo-{start_index}")
            x, y = self._drop_position(px, py, probe.w, probe.h)
            element = slide_element_from_typography({"text": mime.text()}, f"{self.slide.id}-typo-{start_index}", x=x, y=y)
            self.slide.add_element(element)
            created.append(element)
        return created

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.slide:
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if hasattr(event, "button") and event.button() != Qt.MouseButton.LeftButton:
            return
        px, py = self._event_pos(event)
        handle = self._hit_resize_handle(px, py)
        selected = self._selected_element()
        if handle and selected:
            self._begin_drag("resize", selected, px, py, handle=handle)
            event.accept()
            return
        for element in reversed(sorted(self.slide.elements, key=lambda row: int(row.z_index))):
            if not element.visible:
                continue
            x, y, w, h = self._element_rect(element)
            if x <= px <= x + w and y <= py <= y + h:
                self.selected_element_id = element.id
                self.selectedElementChanged.emit(element.id)
                self._begin_drag("move", element, px, py)
                event.accept()
                return
        self.selected_element_id = ""
        self.selectedElementChanged.emit("")
        self._clear_drag()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self.deleteRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        px, py = self._event_pos(event)
        if self._drag_mode:
            element = self._drag_element()
            if element:
                self._apply_drag(element, px, py)
            event.accept()
            return
        handle = self._hit_resize_handle(px, py)
        if handle:
            cursors = {
                "n": Qt.CursorShape.SizeVerCursor,
                "s": Qt.CursorShape.SizeVerCursor,
                "e": Qt.CursorShape.SizeHorCursor,
                "w": Qt.CursorShape.SizeHorCursor,
                "nw": Qt.CursorShape.SizeFDiagCursor,
                "se": Qt.CursorShape.SizeFDiagCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor,
                "sw": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursors.get(handle, Qt.CursorShape.ArrowCursor))
            return
        selected = self._selected_element()
        if selected:
            x, y, w, h = self._element_rect(selected)
            if x <= px <= x + w and y <= py <= y + h:
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._clear_drag()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        event.accept()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#101114"))
        left, top, sw, sh = self._slide_rect()
        deck = self.deck
        slide = self.slide
        bg = QColor(slide.background if slide and slide.background else (deck.theme.background if deck else "#171A21"))
        painter.fillRect(left, top, sw, sh, bg)
        painter.setPen(QPen(QColor("#333333"), 1))
        painter.drawRect(left, top, sw, sh)
        if not deck or not slide:
            painter.setPen(QColor("#A8B0BE"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No slide")
            return
        for element in sorted(slide.elements, key=lambda row: int(row.z_index)):
            if not element.visible:
                continue
            state = self._animation_state(element)
            if not bool(state["visible"]):
                continue
            x, y, w, h = self._animated_rect(element)
            painter.save()
            painter.setOpacity(max(0.0, min(1.0, float(state["opacity"]))))
            if element.kind in {"text", "typography_actor"}:
                if element.style.fill:
                    painter.fillRect(x, y, w, h, QColor(element.style.fill))
                painter.setPen(QColor(element.style.color))
                painter.setFont(
                    _ui_font(
                        max(8, int(element.style.font_size * sw / 1280)),
                        bool(element.style.bold),
                        bool(element.style.italic),
                        bool(element.style.underline),
                        element.style.font_family,
                        float(element.style.letter_spacing or 0.0),
                    )
                )
                flags = Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
                if element.style.align == "center":
                    flags |= Qt.AlignmentFlag.AlignHCenter
                elif element.style.align == "right":
                    flags |= Qt.AlignmentFlag.AlignRight
                painter.drawText(x, y, w, h, int(flags), element.text)
                if element.id == self.selected_element_id:
                    self._paint_selection(painter, element)
            elif element.kind == "table":
                self._paint_table(painter, element, x, y, w, h, deck)
                if element.id == self.selected_element_id:
                    self._paint_selection(painter, element)
            elif element.kind == "line":
                self._paint_line(painter, element, x, y, w, h, deck)
                if element.id == self.selected_element_id:
                    self._paint_selection(painter, element)
            elif element.kind == "chart":
                self._paint_chart(painter, element, x, y, w, h, deck)
                if element.id == self.selected_element_id:
                    self._paint_selection(painter, element)
            elif element.kind == "image":
                self._paint_image(painter, element, x, y, w, h, deck)
                if element.id == self.selected_element_id:
                    self._paint_selection(painter, element)
            else:
                painter.fillRect(x, y, w, h, QColor(element.style.fill or deck.theme.surface))
                painter.setPen(QPen(QColor(element.style.stroke or deck.theme.accent), max(1, int(element.style.stroke_width or 1))))
                painter.drawRect(x, y, w, h)
                painter.setPen(QColor(element.style.color or deck.theme.ink))
                painter.setFont(_ui_font(12, True))
                painter.drawText(x + 8, y + 8, max(1, w - 16), max(1, h - 16), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), element.name or element.kind)
                if element.id == self.selected_element_id:
                    self._paint_selection(painter, element)
            painter.restore()
        try:
            slide_index = deck.slides.index(slide) + 1
        except ValueError:
            slide_index = 1
        for overlay in slide_overlay_elements(deck, slide.id, slide_index=slide_index, slide_count=len(deck.slides)):
            x, y, w, h = self._element_rect(overlay)
            painter.setPen(QColor(overlay.style.color))
            painter.setFont(_ui_font(max(7, int(overlay.style.font_size * sw / 1280)), family=overlay.style.font_family))
            flags = Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap
            if overlay.style.align == "center":
                flags |= Qt.AlignmentFlag.AlignHCenter
            elif overlay.style.align == "right":
                flags |= Qt.AlignmentFlag.AlignRight
            painter.drawText(x, y, w, h, int(flags), overlay.text)

    def _paint_selection(self, painter: QPainter, element: SlideElement) -> None:
        x, y, w, h = self._animated_rect(element)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#D85A30"), 2))
        painter.drawRect(x, y, max(1, w), max(1, h))
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#D85A30"), 1))
        for hx, hy, hw, hh in self._resize_handles(element).values():
            painter.drawRect(hx, hy, hw, hh)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _paint_table(self, painter: QPainter, element: SlideElement, x: int, y: int, w: int, h: int, deck: DeckSpec) -> None:
        rows = max(1, int(element.metadata.get("rows", 3) or 3))
        cols = max(1, int(element.metadata.get("cols", 3) or 3))
        raw_cells = element.metadata.get("cells")
        cells: list[list[str]] = []
        if isinstance(raw_cells, list):
            for row in raw_cells[:rows]:
                cells.append([str(cell) for cell in row[:cols]] if isinstance(row, list) else [])
        while len(cells) < rows:
            cells.append([])
        for row_idx, row in enumerate(cells):
            while len(row) < cols:
                row.append(f"Cell {row_idx + 1}-{len(row) + 1}")
        header = bool(element.metadata.get("header", True))
        header_fill = QColor(str(element.metadata.get("header_fill") or "#EAF1FF"))
        body_fill = QColor(str(element.metadata.get("body_fill") or element.style.fill or "#FFFFFF"))
        grid = QColor(str(element.metadata.get("grid_color") or element.style.stroke or "#B8C2D6"))
        cell_w = max(1, w / cols)
        cell_h = max(1, h / rows)
        painter.setFont(_ui_font(max(7, int(element.style.font_size * max(0.45, w / 1280))), bool(element.style.bold), family=element.style.font_family))
        for row in range(rows):
            for col in range(cols):
                cx = int(round(x + col * cell_w))
                cy = int(round(y + row * cell_h))
                cw = int(round(x + (col + 1) * cell_w)) - cx
                ch = int(round(y + (row + 1) * cell_h)) - cy
                painter.fillRect(cx, cy, max(1, cw), max(1, ch), header_fill if header and row == 0 else body_fill)
                painter.setPen(QPen(grid, 1))
                painter.drawRect(cx, cy, max(1, cw), max(1, ch))
                painter.setPen(QColor(element.style.color or deck.theme.ink))
                cell_text = format_formula_value(cells[row][col], cells=cells)
                painter.drawText(cx + 7, cy + 4, max(1, cw - 14), max(1, ch - 8), int(Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap), cell_text)

    def _paint_line(self, painter: QPainter, element: SlideElement, x: int, y: int, w: int, h: int, deck: DeckSpec) -> None:
        stroke = QColor(element.style.stroke or element.style.color or deck.theme.accent)
        painter.setPen(QPen(stroke, max(1, int(element.style.stroke_width or 2))))
        mid_y = y + max(1, h) // 2
        painter.drawLine(x, mid_y, x + max(1, w), mid_y)

    def _paint_chart(self, painter: QPainter, element: SlideElement, x: int, y: int, w: int, h: int, deck: DeckSpec) -> None:
        painter.fillRect(x, y, w, h, QColor(element.style.fill or "#F7F9FC"))
        painter.setPen(QPen(QColor(element.style.stroke or deck.theme.accent), max(1, int(element.style.stroke_width or 1))))
        painter.drawRect(x, y, w, h)
        raw_labels = element.metadata.get("labels") or ["A", "B", "C", "D"]
        raw_values = element.metadata.get("values") or [32, 58, 44, 72]
        labels = [str(label) for label in raw_labels] if isinstance(raw_labels, list) else ["A", "B", "C", "D"]
        source_values = list(raw_values) if isinstance(raw_values, list) else [32.0, 58.0, 44.0, 72.0]
        cells = [[labels[index] if index < len(labels) else f"Item {index + 1}", value] for index, value in enumerate(source_values)]
        values: list[float] = []
        for value in source_values:
            try:
                values.append(evaluate_numeric_formula(value, cells=cells))
            except Exception:
                values.append(0.0)
        if not values:
            values = [32.0, 58.0, 44.0, 72.0]
        count = max(1, min(len(labels), len(values), 8))
        labels = labels[:count] or ["A"]
        values = values[:count] or [1.0]
        max_value = max(1.0, max(values))
        pad_x = max(10, int(w * 0.08))
        pad_y = max(10, int(h * 0.12))
        plot_left = x + pad_x
        plot_right = x + w - pad_x
        plot_top = y + pad_y
        plot_bottom = y + h - pad_y
        painter.setPen(QPen(QColor("#9AA7BA"), 1))
        painter.drawLine(plot_left, plot_bottom, plot_right, plot_bottom)
        painter.drawLine(plot_left, plot_top, plot_left, plot_bottom)
        slot = max(1.0, (plot_right - plot_left) / max(1, count))
        gap = max(3, int(slot * 0.18))
        bar_w = max(2, int(slot - gap * 2))
        bar_fill = QColor(str(element.metadata.get("bar_fill") or deck.theme.accent))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bar_fill)
        for index, value in enumerate(values):
            x0 = int(plot_left + index * slot + gap)
            y1 = plot_bottom
            y0 = int(plot_bottom - (plot_bottom - plot_top) * max(0.0, value) / max_value)
            painter.drawRect(x0, y0, bar_w, max(1, y1 - y0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QColor("#5E6A7D"))
        painter.setFont(_ui_font(max(7, int(10 * max(0.65, w / 640)))))
        for index, label in enumerate(labels):
            x0 = int(plot_left + index * slot)
            painter.drawText(x0, min(y + h - 4, plot_bottom + 4), int(slot), 14, int(Qt.AlignmentFlag.AlignCenter), label)

    def _paint_image(self, painter: QPainter, element: SlideElement, x: int, y: int, w: int, h: int, deck: DeckSpec) -> None:
        pixmap = QPixmap(element.source_path)
        if pixmap.isNull():
            painter.fillRect(x, y, w, h, QColor(element.style.fill or deck.theme.surface))
            painter.setPen(QPen(QColor(element.style.stroke or deck.theme.accent), max(1, int(element.style.stroke_width or 1))))
            painter.drawRect(x, y, w, h)
            painter.setPen(QColor(deck.theme.muted))
            painter.drawText(x + 8, y + 8, max(1, w - 16), max(1, h - 16), int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap), "Missing image")
            return
        scaled = pixmap.scaled(max(1, w), max(1, h), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        sx = max(0, (scaled.width() - max(1, w)) // 2)
        sy = max(0, (scaled.height() - max(1, h)) // 2)
        painter.drawPixmap(QRect(x, y, max(1, w), max(1, h)), scaled, QRect(sx, sy, max(1, w), max(1, h)))


class SlideTimelineWidget(QWidget):
    slideSelected = Signal(str)
    playheadChanged = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.deck: DeckSpec | None = None
        self.timeline = PptTimeline()
        self.setMinimumHeight(148)

    def set_deck(self, deck: DeckSpec, timeline: PptTimeline) -> None:
        self.deck = deck
        self.timeline = timeline
        self.update()

    def _total_duration(self) -> int:
        return max(1, sum(max(1, int(clip.duration_ms)) for clip in self.timeline.slide_clips))

    def _lane_metrics(self) -> tuple[int, int, int, int]:
        left = 78
        right = max(left + 1, self.width() - 16)
        return left, right, 68, 46

    def _clip_rects(self) -> list[tuple[object, int, int, int, int]]:
        if not self.timeline.slide_clips:
            return []
        left, right, y, height = self._lane_metrics()
        total = self._total_duration()
        width = max(1, right - left)
        rows: list[tuple[object, int, int, int, int]] = []
        cursor = left
        for idx, clip in enumerate(self.timeline.slide_clips):
            if idx == len(self.timeline.slide_clips) - 1:
                clip_w = max(1, right - cursor)
            else:
                clip_w = max(36, int(round(width * max(1, int(clip.duration_ms)) / total)))
            rows.append((clip, cursor, y, clip_w, height))
            cursor += clip_w
        return rows

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self.deck or not self.timeline.slide_clips:
            return
        x = event.position().x() if hasattr(event, "position") else event.x()
        y = event.position().y() if hasattr(event, "position") else event.y()
        for clip, cx, cy, cw, ch in self._clip_rects():
            if cx <= x <= cx + cw and cy - 22 <= y <= cy + ch + 16:
                self.timeline.selected_slide_id = clip.slide_id
                local = max(0.0, min(1.0, (float(x) - cx) / max(1, cw)))
                self.timeline.playhead_ms = int(clip.start_ms + local * max(1, int(clip.duration_ms)))
                self.slideSelected.emit(clip.slide_id)
                self.playheadChanged.emit()
                self.update()
                return

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor("#15161B"))
        if not self.deck:
            return
        total = self._total_duration()
        left, right, lane_y, lane_h = self._lane_metrics()
        width = max(1, right - left)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(_ui_font(10, True))
        painter.drawText(14, 12, 140, 18, int(Qt.AlignmentFlag.AlignLeft), "PPT Timeline")
        painter.setPen(QColor("#8A8A8A"))
        painter.setFont(_ui_font(8))
        painter.drawText(14, 34, 120, 16, int(Qt.AlignmentFlag.AlignLeft), "Slide track")
        painter.drawText(right - 96, 12, 96, 18, int(Qt.AlignmentFlag.AlignRight), f"{total / 1000:.1f}s")

        ruler_y = 44
        painter.setPen(QPen(QColor("#2A2A2A"), 1))
        painter.drawLine(left, ruler_y, right, ruler_y)
        tick_step = 1000 if total <= 15000 else 5000
        for t in range(0, total + tick_step, tick_step):
            tx = left + int(width * min(t, total) / total)
            major = t % 5000 == 0
            painter.setPen(QPen(QColor("#424242" if major else "#333333"), 1))
            painter.drawLine(tx, ruler_y - (8 if major else 5), tx, ruler_y + (8 if major else 5))
            if major:
                painter.setPen(QColor("#8A8A8A"))
                painter.setFont(_ui_font(7))
                painter.drawText(tx - 18, ruler_y - 24, 36, 14, int(Qt.AlignmentFlag.AlignCenter), f"{t // 1000}s")

        painter.setPen(QPen(QColor("#2A2A2A"), 1))
        painter.drawRect(left, lane_y - 8, width, lane_h + 16)

        for idx, clip in enumerate(self.timeline.slide_clips, start=1):
            rect = next((row for row in self._clip_rects() if row[0] is clip), None)
            if rect is None:
                continue
            _clip, x, y, clip_w, height = rect
            selected = clip.slide_id == self.timeline.selected_slide_id
            painter.fillRect(x, y, clip_w - 2, height, QColor("#3A2C26" if selected else "#222431"))
            painter.setPen(QPen(QColor("#D85A30" if selected else "#333333"), 2 if selected else 1))
            painter.drawRect(x, y, max(1, clip_w - 2), height)
            slide = self.deck.slide_by_id(clip.slide_id)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(_ui_font(9, True))
            painter.drawText(x + 8, y + 7, clip_w - 16, 17, int(Qt.AlignmentFlag.AlignLeft), f"{idx}. {slide.title if slide else clip.slide_id}")
            painter.setPen(QColor("#8A8A8A"))
            painter.setFont(_ui_font(8))
            painter.drawText(
                x + 8,
                y + 28,
                clip_w - 16,
                14,
                int(Qt.AlignmentFlag.AlignLeft),
                f"{clip.start_ms / 1000:.1f}s - {clip.end_ms / 1000:.1f}s",
            )
            if slide is not None:
                diamonds = []
                for element in slide.elements:
                    payload = animation_payload(element.animation)
                    if payload["in_animation"] == "none":
                        continue
                    local = max(0, min(int(clip.duration_ms), int(payload["start_ms"])))
                    marker_x = x + int(max(0, clip_w - 2) * local / max(1, int(clip.duration_ms)))
                    diamonds.append(marker_x)
                painter.setBrush(QColor("#8BD8FF"))
                painter.setPen(QPen(QColor("#0E1117"), 1))
                for marker_x in diamonds[:12]:
                    cy = y + height - 10
                    painter.drawPolygon([
                        QPoint(marker_x, cy - 4),
                        QPoint(marker_x + 4, cy),
                        QPoint(marker_x, cy + 4),
                        QPoint(marker_x - 4, cy),
                    ])
                painter.setBrush(Qt.BrushStyle.NoBrush)

        playhead = max(0, min(total, int(getattr(self.timeline, "playhead_ms", 0) or 0)))
        px = left + int(width * playhead / total)
        painter.setPen(QPen(QColor("#D85A30"), 2))
        painter.drawLine(px, ruler_y - 12, px, lane_y + lane_h + 16)
        painter.setBrush(QColor("#D85A30"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon([
            QPoint(px - 6, ruler_y - 13),
            QPoint(px + 6, ruler_y - 13),
            QPoint(px, ruler_y - 4),
        ])


class PptGeneratorWindow(QMainWindow):
    def __init__(self, deck: DeckSpec | None = None, *, source_owner: object | None = None) -> None:
        super().__init__()
        try:
            from PySide6.QtWidgets import QApplication
            from app.font_fallback import apply_ui_font

            apply_ui_font(QApplication.instance())
        except Exception:
            pass
        self.deck = deck or create_sample_deck()
        self.source_owner = source_owner
        self.project_path: Path | None = None
        self.timeline = PptTimeline.from_deck(self.deck)
        self.selected_element_id = ""
        self._syncing_text_controls = False
        self._syncing_animation_controls = False
        self._element_clipboard: SlideElement | None = None
        self._history = PptHistoryStack(max_undo_steps=50)
        self._history.reset(self.deck)
        self._history_restoring = False
        self._dirty = False
        self._autosave_path: Path | None = None
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30000)
        self._autosave_timer.timeout.connect(self._autosave_if_dirty)
        self._autosave_timer.start()
        self._ppt_playing = False
        self._ppt_last_tick = 0.0
        self._video_export_worker: PptVideoExportWorker | None = None
        self._video_export_progress: QProgressDialog | None = None
        self._ppt_play_timer = QTimer(self)
        self._ppt_play_timer.setInterval(33)
        self._ppt_play_timer.timeout.connect(self._advance_ppt_playback)
        self.setWindowTitle("TigerCapture PPT Generator")
        self.resize(1320, 820)
        self._build_ui()
        self._install_shortcuts()
        self._refresh_all()

    def set_deck(self, deck: DeckSpec, *, project_path: str | Path | None = None) -> None:
        self.deck = deck
        self.project_path = Path(project_path) if project_path else None
        self.timeline = PptTimeline.from_deck(self.deck)
        self.selected_element_id = ""
        self._history.reset(self.deck)
        self._dirty = False
        self._autosave_path = None
        self._refresh_all()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("PptEditorRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)
        self.setCentralWidget(root)

        command_bar = QWidget(root)
        command_bar.setObjectName("PptCommandBar")
        top = QHBoxLayout(command_bar)
        top.setContentsMargins(10, 7, 10, 7)
        top.setSpacing(6)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 8, 0)
        title_col.setSpacing(1)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        app_title = QLabel("PPT Editor", command_bar)
        app_title.setObjectName("PptWindowTitle")
        badge = QLabel("BETA", command_bar)
        badge.setObjectName("PptBadge")
        title_row.addWidget(app_title)
        title_row.addWidget(badge)
        title_row.addStretch(1)
        title_col.addLayout(title_row)
        self.title_label = QLabel("Untitled Presentation", command_bar)
        self.title_label.setObjectName("PptDeckTitle")
        title_col.addWidget(self.title_label)
        top.addLayout(title_col, 1)

        for label, icon_name, handler, primary in [
            ("New", "plus", self._new_deck, False),
            ("Open", "project", self._open_deck, False),
            ("Import", "document", self._import_pptx_file, False),
            ("Recovery", "replay", self._open_recovery_deck, False),
            ("Save", "save", self._save_deck, False),
            ("Save As", "save", self._save_deck_as, False),
            ("Undo", "previous", self._undo_ppt, False),
            ("Redo", "next", self._redo_ppt, False),
            ("Timeline", "video", self._import_from_editor, False),
            ("Still", "camera", self._add_current_cut_image, False),
            ("Templates", "layers", self._choose_template, False),
            ("Slide", "plus", self._add_slide, False),
            ("Duplicate", "nest", self._duplicate_slide, False),
            ("Delete", "trash", self._delete_slide, False),
            ("Header", "caption", self._edit_header_footer, False),
            ("Play", "play", self._toggle_ppt_playback, False),
            ("Stop", "stop", self._stop_ppt_playback, False),
            ("PPTX", "export", self._export_pptx, True),
            ("PDF", "document", self._export_pdf, False),
            ("MP4", "video", self._export_video, False),
            ("PNGs", "camera", self._export_pngs, False),
            ("Check", "health", self._show_validation, False),
        ]:
            button = self._make_command_button(label, icon_name, handler, primary=primary)
            if label == "Play":
                self.play_button = button
            elif label == "Undo":
                self.undo_button = button
            elif label == "Redo":
                self.redo_button = button
            top.addWidget(button)
        outer.addWidget(command_bar)
        outer.addWidget(self._build_text_toolbar(), 0)

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.setObjectName("PptMainSplitter")
        split.setChildrenCollapsible(False)
        outer.addWidget(split, 1)

        left = QWidget(split)
        left.setObjectName("PptLeftDock")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._build_insert_toolbox(left))
        self.media_pool_panel = PptMediaPoolPanel(left)
        self.media_pool_panel.addRequested.connect(self._add_media_pool_files)
        self.media_pool_panel.insertRequested.connect(self._insert_media_pool_asset)
        self.media_pool_panel.removeRequested.connect(self._remove_media_pool_asset)
        left_layout.addWidget(self.media_pool_panel)
        left_layout.addWidget(self._make_section_header("Slides", "Page order and timing"))
        self.slide_list = QListWidget()
        self.slide_list.setObjectName("PptSlideList")
        self.slide_list.currentRowChanged.connect(self._select_slide_index)
        left_layout.addWidget(self.slide_list, 1)
        split.addWidget(left)

        canvas_frame = QFrame(split)
        canvas_frame.setObjectName("PptCanvasFrame")
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(8, 8, 8, 8)
        canvas_layout.setSpacing(8)
        self.canvas = SlideCanvas(canvas_frame)
        self.canvas.setObjectName("PptSlideCanvas")
        self.canvas.selectedElementChanged.connect(self._select_element_id)
        self.canvas.slideContentChanged.connect(self._refresh_selected)
        self.canvas.deleteRequested.connect(self._delete_selected_element)
        canvas_layout.addWidget(self.canvas, 1)
        self.timeline_widget = SlideTimelineWidget(canvas_frame)
        self.timeline_widget.slideSelected.connect(self._select_slide_id)
        self.timeline_widget.playheadChanged.connect(self._timeline_playhead_changed)
        canvas_layout.addWidget(self.timeline_widget, 0)
        self.animation_lane_widget = AnimationLaneWidget(canvas_frame)
        self.animation_lane_widget.animationSelected.connect(self._select_animation_lane_item)
        self.animation_lane_widget.animationTimingChanged.connect(self._animation_lane_timing_changed)
        canvas_layout.addWidget(self.animation_lane_widget, 0)
        split.addWidget(canvas_frame)

        right = QWidget(split)
        right.setObjectName("PptRightDock")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._make_section_header("Elements", "Selected slide layers"))
        self.element_list = QListWidget()
        self.element_list.setObjectName("PptElementList")
        self.element_list.setMaximumHeight(118)
        self.element_list.currentRowChanged.connect(self._select_element_row)
        self.element_list.installEventFilter(self)
        right_layout.addWidget(self.element_list)
        right_layout.addWidget(self._build_element_tools(right))
        self.edit_data_button = self._make_panel_button("Edit Data / Formula", "sliders")
        self.edit_data_button.clicked.connect(self._edit_selected_data)
        right_layout.addWidget(self.edit_data_button)
        self.replace_image_button = self._make_panel_button("Load / Replace Image", "media")
        self.replace_image_button.clicked.connect(self._choose_image_for_selected)
        right_layout.addWidget(self.replace_image_button)
        right_layout.addWidget(self._build_animation_panel(right))

        right_layout.addWidget(self._make_section_header("Speaker Notes", "Presenter text"))
        self.notes = QPlainTextEdit()
        self.notes.setObjectName("PptNotes")
        self.notes.setPlaceholderText("Speaker notes for the selected slide")
        self.notes.textChanged.connect(self._notes_changed)
        right_layout.addWidget(self.notes, 1)
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("PptPanelHint")
        self.validation_label.setWordWrap(True)
        right_layout.addWidget(self.validation_label)
        split.addWidget(right)
        split.setSizes([220, 840, 260])

        root.setStyleSheet(PPT_EDITOR_QSS)

    def _make_section_header(self, title: str, caption: str = "") -> QWidget:
        host = QWidget(self)
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        label = QLabel(title, host)
        label.setObjectName("PptSectionHeader")
        layout.addWidget(label)
        if caption:
            sub = QLabel(caption, host)
            sub.setObjectName("PptSectionCaption")
            layout.addWidget(sub)
        return host

    def _make_command_button(self, label: str, icon_name: str, handler, *, primary: bool = False) -> QPushButton:
        button = QPushButton(label, self)
        button.setObjectName("PptPrimaryButton" if primary else "PptCommandButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(app_icon(icon_name, size=14, color="#FFFFFF" if primary else "#D7DAE7"))
        button.setIconSize(icon_size(14))
        button.clicked.connect(handler)
        return button

    def _make_panel_button(self, label: str, icon_name: str) -> QPushButton:
        button = QPushButton(label, self)
        button.setObjectName("PptInsertButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(app_icon(icon_name, size=14, color="#D7DAE7"))
        button.setIconSize(icon_size(14))
        return button

    def _make_element_tool_button(self, label: str, icon_name: str, handler) -> QPushButton:
        button = QPushButton(label, self)
        button.setObjectName("PptElementToolButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(app_icon(icon_name, size=13, color="#D7DAE7"))
        button.setIconSize(icon_size(13))
        button.clicked.connect(handler)
        return button

    def _build_element_tools(self, parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("PptElementTools")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        edit_row.setSpacing(4)
        self.copy_element_button = self._make_element_tool_button("Copy", "nest", self._copy_selected_element)
        self.paste_element_button = self._make_element_tool_button("Paste", "plus", self._paste_element)
        self.duplicate_element_button = self._make_element_tool_button("Duplicate", "nest", self._duplicate_selected_element)
        for button in (self.copy_element_button, self.paste_element_button, self.duplicate_element_button):
            edit_row.addWidget(button)
        layout.addLayout(edit_row)

        layer_row = QHBoxLayout()
        layer_row.setContentsMargins(0, 0, 0, 0)
        layer_row.setSpacing(4)
        self.front_element_button = self._make_element_tool_button("Front", "next", lambda: self._set_selected_z_order("front"))
        self.back_element_button = self._make_element_tool_button("Back", "previous", lambda: self._set_selected_z_order("back"))
        for button in (self.front_element_button, self.back_element_button):
            layer_row.addWidget(button)
        layout.addLayout(layer_row)

        align_h_row = QHBoxLayout()
        align_h_row.setContentsMargins(0, 0, 0, 0)
        align_h_row.setSpacing(4)
        self.align_left_button = self._make_element_tool_button("Left", "previous", lambda: self._align_selected_element(horizontal="left"))
        self.align_center_button = self._make_element_tool_button("Center", "fit", lambda: self._align_selected_element(horizontal="center"))
        self.align_right_button = self._make_element_tool_button("Right", "next", lambda: self._align_selected_element(horizontal="right"))
        for button in (self.align_left_button, self.align_center_button, self.align_right_button):
            align_h_row.addWidget(button)
        layout.addLayout(align_h_row)

        align_v_row = QHBoxLayout()
        align_v_row.setContentsMargins(0, 0, 0, 0)
        align_v_row.setSpacing(4)
        self.align_top_button = self._make_element_tool_button("Top", "chevron-up", lambda: self._align_selected_element(vertical="top"))
        self.align_middle_button = self._make_element_tool_button("Middle", "fit", lambda: self._align_selected_element(vertical="middle"))
        self.align_bottom_button = self._make_element_tool_button("Bottom", "chevron-down", lambda: self._align_selected_element(vertical="bottom"))
        for button in (self.align_top_button, self.align_middle_button, self.align_bottom_button):
            align_v_row.addWidget(button)
        layout.addLayout(align_v_row)
        return panel

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self._undo_ppt)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self._redo_ppt)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._duplicate_selected_element)

    def _commit_history(self, label: str = "Edit") -> None:
        if self._history_restoring:
            return
        if self._history.push(self.deck, label=label):
            self._dirty = True
            self._update_window_caption()
            self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        undo_button = getattr(self, "undo_button", None)
        redo_button = getattr(self, "redo_button", None)
        if undo_button is not None:
            undo_label = self._history.undo_label()
            undo_button.setEnabled(self._history.can_undo())
            undo_button.setToolTip(f"Undo {undo_label}" if undo_label else "Undo")
        if redo_button is not None:
            redo_label = self._history.redo_label()
            redo_button.setEnabled(self._history.can_redo())
            redo_button.setToolTip(f"Redo {redo_label}" if redo_label else "Redo")

    def _restore_history_snapshot(self, snapshot: dict | None) -> bool:
        if snapshot is None:
            return False
        current_slide_id = str(getattr(self.timeline, "selected_slide_id", "") or "")
        current_element_id = str(self.selected_element_id or "")
        self._history_restoring = True
        try:
            self.deck = deck_from_history_snapshot(snapshot)
            self.timeline = PptTimeline.from_deck(self.deck)
            if current_slide_id and self.deck.slide_by_id(current_slide_id) is not None:
                self.timeline.select_slide(current_slide_id)
            self.selected_element_id = current_element_id
            self._dirty = True
            self._refresh_all()
        finally:
            self._history_restoring = False
        self._update_history_buttons()
        return True

    def _undo_ppt(self) -> bool:
        return self._restore_history_snapshot(self._history.undo())

    def _redo_ppt(self) -> bool:
        return self._restore_history_snapshot(self._history.redo())

    def ppt_history_status(self) -> dict:
        return {
            "schema": "tigercapture.ppt.history_status.v1",
            "can_undo": self._history.can_undo(),
            "can_redo": self._history.can_redo(),
            "undo_label": self._history.undo_label(),
            "redo_label": self._history.redo_label(),
            "history_depth": self._history.depth(),
            "dirty": bool(self._dirty),
            "autosave_path": str(self._autosave_path or ""),
        }

    def undo_deck_edit(self) -> dict:
        changed = self._undo_ppt()
        result = self.ppt_history_status()
        result.update({"schema": "tigercapture.ppt.undo.v1", "changed": bool(changed)})
        return result

    def redo_deck_edit(self) -> dict:
        changed = self._redo_ppt()
        result = self.ppt_history_status()
        result.update({"schema": "tigercapture.ppt.redo.v1", "changed": bool(changed)})
        return result

    def _autosave_if_dirty(self) -> None:
        if not self._dirty:
            return
        try:
            self._autosave_path = save_ppt_autosave(self.deck, project_path=self.project_path)
        except Exception:
            return

    def save_recovery_copy(self) -> dict:
        self._autosave_path = save_ppt_autosave(self.deck, project_path=self.project_path)
        return {
            "schema": "tigercapture.ppt.autosave.v1",
            "path": str(self._autosave_path),
            "dirty": bool(self._dirty),
            "slide_count": len(self.deck.slides),
        }

    def recovery_candidates(self, *, limit: int = 20) -> dict:
        candidates = list_ppt_recovery_candidates(
            project_path=self.project_path,
            deck_id=self.deck.id,
            limit=max(1, int(limit or 20)),
        )
        return {
            "schema": "tigercapture.ppt.recovery_candidates.v1",
            "candidate_count": len(candidates),
            "candidates": candidates,
        }

    def delete_recovery_copy(self, path: str | Path) -> dict:
        result = delete_ppt_recovery_file(path)
        if self._autosave_path and Path(result["path"]).resolve() == self._autosave_path.resolve():
            self._autosave_path = None
        return result

    def open_recovery_copy(self, path: str | Path = "") -> dict:
        raw_path = str(path or "").strip()
        if not raw_path:
            valid = [row for row in self.recovery_candidates()["candidates"] if row.get("valid")]
            if not valid:
                raise RuntimeError("No valid PPT recovery copy is available")
            raw_path = str(valid[0].get("path") or "")
        source = Path(raw_path)
        deck = load_deck_project(source)
        self.set_deck(deck)
        self._dirty = True
        self._autosave_path = source
        self._update_window_caption()
        return {
            "schema": "tigercapture.ppt.recovery_opened.v1",
            "path": str(source),
            "deck_id": deck.id,
            "title": deck.title,
            "slide_count": len(deck.slides),
            "dirty": True,
        }

    def _cleanup_saved_recovery_copies(self) -> None:
        targets: list[Path] = []
        if self._autosave_path is not None:
            targets.append(self._autosave_path)
        if self.project_path is not None:
            targets.append(ppt_autosave_path(project_path=self.project_path))
        seen: set[str] = set()
        for path in targets:
            try:
                key = str(path.resolve())
            except Exception:
                key = str(path)
            if key in seen:
                continue
            seen.add(key)
            try:
                if path.exists():
                    delete_ppt_recovery_file(path)
            except Exception:
                pass

    def _mark_saved(self) -> None:
        self._cleanup_saved_recovery_copies()
        self._dirty = False
        self._autosave_path = None
        self._update_window_caption()
        self._update_history_buttons()

    def _confirm_save_or_discard_changes(self, action_label: str) -> bool:
        if not self._dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Unsaved PPT changes")
        box.setText(f"Save changes before {action_label}?")
        box.setInformativeText("Unsaved edits will be lost if you discard them.")
        save_button = box.addButton("Save", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(save_button)
        box.exec()
        clicked = box.clickedButton()
        if clicked is save_button:
            return self._save_deck()
        if clicked is discard_button:
            return True
        if clicked is cancel_button:
            return False
        return False

    def _build_animation_panel(self, parent: QWidget) -> QFrame:
        panel = QFrame(parent)
        panel.setObjectName("PptAnimationPanel")
        layout = QFormLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self.animation_combo = QComboBox(panel)
        self.animation_combo.addItems(list(ANIMATION_TYPES))
        self.animation_combo.currentTextChanged.connect(self._animation_controls_changed)
        layout.addRow("Effect", self.animation_combo)

        self.animation_trigger_combo = QComboBox(panel)
        self.animation_trigger_combo.addItems(list(ANIMATION_TRIGGERS))
        self.animation_trigger_combo.currentTextChanged.connect(self._animation_controls_changed)
        layout.addRow("Trigger", self.animation_trigger_combo)

        self.animation_click_index_spin = QSpinBox(panel)
        self.animation_click_index_spin.setRange(0, 999)
        self.animation_click_index_spin.setSpecialValueText("Auto")
        self.animation_click_index_spin.setSingleStep(1)
        self.animation_click_index_spin.valueChanged.connect(self._animation_controls_changed)
        layout.addRow("Click #", self.animation_click_index_spin)

        self.animation_start_spin = QSpinBox(panel)
        self.animation_start_spin.setRange(0, 600000)
        self.animation_start_spin.setSingleStep(100)
        self.animation_start_spin.setSuffix(" ms")
        self.animation_start_spin.valueChanged.connect(self._animation_controls_changed)
        layout.addRow("Start", self.animation_start_spin)

        self.animation_duration_spin = QSpinBox(panel)
        self.animation_duration_spin.setRange(1, 60000)
        self.animation_duration_spin.setSingleStep(50)
        self.animation_duration_spin.setSuffix(" ms")
        self.animation_duration_spin.valueChanged.connect(self._animation_controls_changed)
        layout.addRow("Duration", self.animation_duration_spin)

        self.animation_easing_combo = QComboBox(panel)
        self.animation_easing_combo.addItems(list(ANIMATION_EASINGS))
        self.animation_easing_combo.currentTextChanged.connect(self._animation_controls_changed)
        layout.addRow("Easing", self.animation_easing_combo)

        self.animation_motion_x_spin = QDoubleSpinBox(panel)
        self.animation_motion_x_spin.setRange(-1.0, 1.0)
        self.animation_motion_x_spin.setDecimals(2)
        self.animation_motion_x_spin.setSingleStep(0.02)
        self.animation_motion_x_spin.valueChanged.connect(self._animation_controls_changed)
        layout.addRow("Move X", self.animation_motion_x_spin)

        self.animation_motion_y_spin = QDoubleSpinBox(panel)
        self.animation_motion_y_spin.setRange(-1.0, 1.0)
        self.animation_motion_y_spin.setDecimals(2)
        self.animation_motion_y_spin.setSingleStep(0.02)
        self.animation_motion_y_spin.valueChanged.connect(self._animation_controls_changed)
        layout.addRow("Move Y", self.animation_motion_y_spin)

        self.animation_scale_spin = QDoubleSpinBox(panel)
        self.animation_scale_spin.setRange(0.1, 4.0)
        self.animation_scale_spin.setDecimals(2)
        self.animation_scale_spin.setSingleStep(0.05)
        self.animation_scale_spin.valueChanged.connect(self._animation_controls_changed)
        layout.addRow("Scale", self.animation_scale_spin)
        return panel

    def _build_insert_toolbox(self, parent: QWidget) -> QFrame:
        box = QFrame(parent)
        box.setObjectName("InsertToolbox")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)
        title = QLabel("Insert")
        title.setObjectName("ToolbarGroupLabel")
        layout.addWidget(title)
        for label, icon_name, handler in [
            ("Text Box", "caption", self._add_text),
            ("Document Box", "layers", self._add_content_box),
            ("Table", "grid", self._add_table),
            ("Image", "media", self._add_image_box),
            ("Shape", "fit", self._add_shape),
            ("Line", "slide", self._add_line),
            ("Chart", "scopes", self._add_chart),
        ]:
            button = self._make_panel_button(label, icon_name)
            button.setParent(box)
            button.clicked.connect(handler)
            layout.addWidget(button)
        return box

    def _build_text_toolbar(self) -> QFrame:
        bar = QFrame(self)
        bar.setObjectName("PptTextFormatBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(7)

        label = QLabel("Text", bar)
        label.setObjectName("ToolbarGroupLabel")
        layout.addWidget(label)

        self.font_combo = QComboBox(bar)
        self.font_combo.setEditable(False)
        self.font_combo.addItems(self._available_font_families())
        self.font_combo.setMinimumWidth(180)
        self.font_combo.setMaximumWidth(260)
        self.font_combo.currentTextChanged.connect(self._font_controls_changed)
        layout.addWidget(self.font_combo, 1)

        self.size_spin = QSpinBox(bar)
        self.size_spin.setRange(8, 160)
        self.size_spin.setSingleStep(1)
        self.size_spin.setFixedWidth(74)
        self.size_spin.valueChanged.connect(self._font_controls_changed)
        layout.addWidget(self.size_spin)

        self.bold_button = self._make_toggle_button("B")
        self.italic_button = self._make_toggle_button("I")
        self.underline_button = self._make_toggle_button("U")
        for button in (self.bold_button, self.italic_button, self.underline_button):
            button.setParent(bar)
            button.toggled.connect(self._font_controls_changed)
            layout.addWidget(button)

        self.align_combo = QComboBox(bar)
        self.align_combo.addItems(["left", "center", "right"])
        self.align_combo.setFixedWidth(102)
        self.align_combo.currentTextChanged.connect(self._font_controls_changed)
        layout.addWidget(self.align_combo)

        line_label = QLabel("Line", bar)
        line_label.setObjectName("ToolbarGroupLabel")
        layout.addWidget(line_label)
        self.line_height_spin = QDoubleSpinBox(bar)
        self.line_height_spin.setRange(0.8, 2.4)
        self.line_height_spin.setDecimals(2)
        self.line_height_spin.setSingleStep(0.05)
        self.line_height_spin.setFixedWidth(78)
        self.line_height_spin.valueChanged.connect(self._font_controls_changed)
        layout.addWidget(self.line_height_spin)

        self.color_button = QPushButton("#182033", bar)
        self.color_button.setObjectName("PptColorButton")
        self.color_button.setFixedWidth(96)
        self.color_button.clicked.connect(self._choose_text_color)
        layout.addWidget(self.color_button)
        layout.addStretch(2)
        return bar

    def _available_font_families(self) -> list[str]:
        try:
            installed = QFontDatabase.families()
        except Exception:
            try:
                installed = QFontDatabase().families()
            except Exception:
                installed = []
        return recommended_font_families(installed)

    def _make_toggle_button(self, text: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName("PptFormatToggle")
        button.setText(text)
        button.setCheckable(True)
        if text == "B":
            button.setFont(_ui_font(10, True))
        elif text == "I":
            button.setFont(_ui_font(10, False, True))
        elif text == "U":
            button.setFont(_ui_font(10, False, False, True))
        return button

    def _update_window_caption(self) -> None:
        title = self.deck.title or "Untitled Presentation"
        marker = f" - {self.project_path.name}" if self.project_path else ""
        dirty = " *" if self._dirty else ""
        self.setWindowTitle(f"TigerCapture PPT Generator{marker}{dirty}")
        if hasattr(self, "title_label"):
            self.title_label.setText(f"{title}{dirty}")

    def _refresh_all(self) -> None:
        self._update_window_caption()
        current = self.timeline.selected_slide_id
        self.slide_list.blockSignals(True)
        self.slide_list.clear()
        for idx, slide in enumerate(self.deck.slides, start=1):
            item = QListWidgetItem(f"{idx}. {slide.title or slide.id}")
            item.setData(Qt.ItemDataRole.UserRole, slide.id)
            self.slide_list.addItem(item)
        row = next((idx for idx, slide in enumerate(self.deck.slides) if slide.id == current), 0)
        if self.deck.slides:
            self.slide_list.setCurrentRow(max(0, row))
        self.slide_list.blockSignals(False)
        self.timeline_widget.set_deck(self.deck, self.timeline)
        self._refresh_media_pool()
        self._refresh_selected()
        self._update_history_buttons()

    def _selected_slide(self) -> SlideSpec | None:
        return self.deck.slide_by_id(self.timeline.selected_slide_id) or (self.deck.slides[0] if self.deck.slides else None)

    def _refresh_media_pool(self) -> None:
        panel = getattr(self, "media_pool_panel", None)
        if panel is not None:
            panel.set_assets(list_deck_assets(self.deck))

    def _add_media_pool_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Add PPT Media",
            "",
            "Media Files (*.png *.jpg *.jpeg *.webp *.bmp *.gif *.mp4 *.mov *.mkv *.avi *.webm *.m4v *.fbx *.glb *.gltf *.obj *.usd *.usdz *.vrm *.pmx *.pmd *.wav *.mp3 *.m4a *.aac *.ogg *.flac);;All Files (*.*)",
        )
        if not paths:
            return
        last_id = ""
        for path in paths:
            asset = add_deck_asset(self.deck, path, source="ppt_media_pool_picker")
            last_id = str(asset.get("id") or last_id)
        self._refresh_media_pool()
        if last_id:
            self.media_pool_panel.set_assets(list_deck_assets(self.deck), selected_asset_id=last_id)
        self._commit_history("Add media")

    def _insert_media_pool_asset(self, asset_id: str) -> None:
        slide = self._selected_slide()
        if slide is None:
            return
        idx = len(slide.elements) + 1
        element = insert_deck_asset_to_slide(
            self.deck,
            asset_id,
            slide,
            element_id=f"{slide.id}-asset-{idx}",
            source="ppt_media_pool",
        )
        ensure_actor_poster(element)
        self.timeline.select_slide(slide.id)
        self.selected_element_id = element.id
        self._refresh_all()

    def _remove_media_pool_asset(self, asset_id: str) -> None:
        try:
            remove_deck_asset(self.deck, asset_id)
        except Exception as exc:
            QMessageBox.warning(self, "Media Pool", str(exc))
            return
        self._refresh_media_pool()
        self._commit_history("Remove media")

    def add_media_asset_to_slide(
        self,
        path: str | Path,
        *,
        slide_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
        kind: str | None = None,
        source: str = "action",
    ) -> SlideElement:
        slide = self.deck.slide_by_id(slide_id) if slide_id else self._selected_slide()
        if slide is None:
            raise RuntimeError("No slide is available")
        asset = add_deck_asset(self.deck, path, kind=kind, source=source)
        idx = len(slide.elements) + 1
        element = slide_element_from_media_asset(
            path,
            f"{slide.id}-asset-{idx}",
            x=x,
            y=y,
            w=w,
            h=h,
            kind=kind,
            source=source,
        )
        element.metadata["ppt_asset_id"] = str(asset.get("id") or "")
        ensure_actor_poster(element)
        slide.add_element(element)
        self.timeline.select_slide(slide.id)
        self.selected_element_id = element.id
        self._refresh_all()
        return element

    def add_image_file_to_slide(
        self,
        path: str | Path,
        *,
        slide_id: str = "",
        replace_element_id: str = "",
        x: float = 0.18,
        y: float = 0.24,
        w: float | None = None,
        h: float | None = None,
    ) -> SlideElement:
        slide = self.deck.slide_by_id(slide_id) if slide_id else self._selected_slide()
        if slide is None:
            raise RuntimeError("No slide is available")
        image_path = Path(path)
        if not image_path.exists():
            raise RuntimeError(f"Image file not found: {image_path}")
        asset = add_deck_asset(self.deck, image_path, kind="image", source="ppt_image_picker")
        target_id = str(replace_element_id or "").strip()
        if target_id:
            for index, current in enumerate(slide.elements):
                if current.id != target_id:
                    continue
                if current.kind not in {"image", "image_placeholder"}:
                    raise RuntimeError(f"element is not image-compatible: {target_id}")
                replacement = slide_element_from_media_asset(
                    image_path,
                    current.id,
                    x=current.x,
                    y=current.y,
                    w=current.w,
                    h=current.h,
                    kind="image",
                    source="ppt_image_picker",
                )
                replacement.z_index = current.z_index
                replacement.rotation = current.rotation
                replacement.opacity = current.opacity
                replacement.visible = current.visible
                replacement.locked = current.locked
                replacement.metadata["ppt_asset_id"] = str(asset.get("id") or "")
                slide.elements[index] = replacement
                self.timeline.select_slide(slide.id)
                self.selected_element_id = replacement.id
                self._refresh_all()
                return replacement
            raise RuntimeError(f"element not found: {target_id}")
        idx = len(slide.elements) + 1
        element = slide_element_from_media_asset(
            image_path,
            f"{slide.id}-image-{idx}",
            x=x,
            y=y,
            w=w,
            h=h,
            kind="image",
            source="ppt_image_picker",
        )
        element.metadata["ppt_asset_id"] = str(asset.get("id") or "")
        slide.add_element(element)
        self.timeline.select_slide(slide.id)
        self.selected_element_id = element.id
        self._refresh_all()
        return element

    def ensure_actor_posters(self, *, force: bool = False) -> dict[str, object]:
        result = ensure_deck_actor_posters(self.deck, force=bool(force))
        if int(result.get("generated_count") or 0) > 0:
            self._refresh_selected()
        return result

    def validate_deck_report(self) -> dict[str, object]:
        return validation_report(self.deck)

    def add_typography_to_slide(
        self,
        payload: object,
        *,
        slide_id: str = "",
        x: float = 0.21,
        y: float = 0.42,
        w: float = 0.58,
        h: float = 0.13,
        source: str = "action",
    ) -> SlideElement:
        slide = self.deck.slide_by_id(slide_id) if slide_id else self._selected_slide()
        if slide is None:
            raise RuntimeError("No slide is available")
        idx = len(slide.elements) + 1
        element = slide_element_from_typography(
            payload,
            f"{slide.id}-typo-{idx}",
            x=x,
            y=y,
            w=w,
            h=h,
            source=source,
        )
        slide.add_element(element)
        self.timeline.select_slide(slide.id)
        self.selected_element_id = element.id
        self._refresh_all()
        return element

    def _slide_elements(self, slide: SlideSpec | None = None) -> list[SlideElement]:
        target = slide or self._selected_slide()
        if not target:
            return []
        return list(target.elements)

    def _text_elements(self, slide: SlideSpec | None = None) -> list[SlideElement]:
        return [element for element in self._slide_elements(slide) if element.kind == "text"]

    def _ensure_selected_element(self, slide: SlideSpec | None) -> None:
        elements = self._slide_elements(slide)
        ids = {element.id for element in elements}
        if self.selected_element_id not in ids:
            self.selected_element_id = elements[0].id if elements else ""

    def _selected_element(self) -> SlideElement | None:
        if not self.selected_element_id:
            return None
        for element in self._slide_elements():
            if element.id == self.selected_element_id:
                return element
        return None

    def _timeline_total_ms(self) -> int:
        return max(1, sum(max(1, int(clip.duration_ms)) for clip in self.timeline.slide_clips))

    def _slide_local_playhead_ms(self, slide: SlideSpec | None) -> int:
        if slide is None:
            return 0
        playhead = int(getattr(self.timeline, "playhead_ms", 0) or 0)
        for clip in self.timeline.slide_clips:
            if clip.slide_id != slide.id:
                continue
            return max(0, min(max(1, int(clip.duration_ms)), playhead - int(clip.start_ms)))
        return 0

    def _selected_slide_duration_ms(self, slide: SlideSpec | None) -> int:
        if slide is None:
            return 5000
        for clip in self.timeline.slide_clips:
            if clip.slide_id == slide.id:
                return max(1, int(clip.duration_ms))
        return max(1, int(getattr(slide, "duration_ms", 5000) or 5000))

    def _refresh_animation_lane(self) -> None:
        widget = getattr(self, "animation_lane_widget", None)
        if widget is None:
            return
        slide = self._selected_slide()
        widget.set_context(
            self.deck,
            slide,
            selected_element_id=self.selected_element_id,
            local_playhead_ms=self._slide_local_playhead_ms(slide),
            slide_duration_ms=self._selected_slide_duration_ms(slide),
        )

    def _refresh_selected(self) -> None:
        slide = self._selected_slide()
        self._ensure_selected_element(slide)
        self.canvas.set_slide(self.deck, slide, self.selected_element_id, playhead_ms=self._slide_local_playhead_ms(slide))
        self.notes.blockSignals(True)
        self.notes.setPlainText(slide.speaker_notes if slide else "")
        self.notes.blockSignals(False)
        issues = validate_deck(self.deck)
        errors = sum(1 for issue in issues if issue.severity == "error")
        warnings = sum(1 for issue in issues if issue.severity == "warning")
        self.validation_label.setText(f"Validation: {errors} errors, {warnings} warnings")
        self._refresh_element_list()
        self._refresh_font_controls()
        self._refresh_data_controls()
        self._refresh_image_controls()
        self._refresh_animation_controls()
        self._refresh_element_tool_buttons()
        self.timeline_widget.update()
        self._refresh_animation_lane()
        self._commit_history("Edit slide")

    def _refresh_element_list(self) -> None:
        self.element_list.blockSignals(True)
        self.element_list.clear()
        selected_row = -1
        for row, element in enumerate(self._slide_elements()):
            label = element.name or element.id
            snippet = " ".join(str(element.text or element.kind).split())
            anim = animation_payload(element.animation)["in_animation"]
            anim_badge = f" [{anim}]" if anim != "none" else ""
            item = QListWidgetItem(f"{label}{anim_badge}: {snippet[:34]}")
            item.setData(Qt.ItemDataRole.UserRole, element.id)
            self.element_list.addItem(item)
            if element.id == self.selected_element_id:
                selected_row = row
        self.element_list.setCurrentRow(selected_row)
        self.element_list.blockSignals(False)

    def _refresh_font_controls(self) -> None:
        element = self._selected_element()
        enabled = element is not None and element.kind == "text"
        controls = [
            self.font_combo,
            self.size_spin,
            self.bold_button,
            self.italic_button,
            self.underline_button,
            self.align_combo,
            self.line_height_spin,
            self.color_button,
        ]
        self._syncing_text_controls = True
        try:
            for control in controls:
                control.setEnabled(enabled)
            if not element:
                self.color_button.setText("No text")
                self.color_button.setStyleSheet("")
                return
            family = element.style.font_family or self.deck.theme.font_family
            family_index = self.font_combo.findText(family, Qt.MatchFlag.MatchFixedString)
            if family_index < 0:
                self.font_combo.insertItem(0, family)
                family_index = 0
            self.font_combo.setCurrentIndex(family_index)
            self.size_spin.setValue(int(element.style.font_size))
            self.bold_button.setChecked(bool(element.style.bold))
            self.italic_button.setChecked(bool(element.style.italic))
            self.underline_button.setChecked(bool(element.style.underline))
            align_index = self.align_combo.findText(str(element.style.align or "left").lower(), Qt.MatchFlag.MatchFixedString)
            self.align_combo.setCurrentIndex(max(0, align_index))
            self.line_height_spin.setValue(float(element.style.line_height or 1.2))
            self._update_color_button(element.style.color)
        finally:
            self._syncing_text_controls = False

    def _refresh_data_controls(self) -> None:
        element = self._selected_element()
        enabled = element is not None and element.kind in {"table", "chart"}
        self.edit_data_button.setEnabled(bool(enabled))
        if element is None:
            self.edit_data_button.setText("Edit Data / Formula")
        elif element.kind == "table":
            self.edit_data_button.setText("Edit Table Data")
        elif element.kind == "chart":
            self.edit_data_button.setText("Edit Chart Data")
        else:
            self.edit_data_button.setText("Edit Data / Formula")

    def _refresh_image_controls(self) -> None:
        element = self._selected_element()
        enabled = element is not None and element.kind in {"image", "image_placeholder"}
        self.replace_image_button.setEnabled(bool(enabled))
        if element is not None and element.kind == "image":
            self.replace_image_button.setText("Replace Image")
        elif element is not None and element.kind == "image_placeholder":
            self.replace_image_button.setText("Load Image")
        else:
            self.replace_image_button.setText("Load / Replace Image")

    def _refresh_element_tool_buttons(self) -> None:
        element = self._selected_element()
        enabled = element is not None and not bool(getattr(element, "locked", False))
        for name in (
            "copy_element_button",
            "duplicate_element_button",
            "front_element_button",
            "back_element_button",
            "align_left_button",
            "align_center_button",
            "align_right_button",
            "align_top_button",
            "align_middle_button",
            "align_bottom_button",
        ):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(bool(enabled))
        paste_button = getattr(self, "paste_element_button", None)
        if paste_button is not None:
            paste_button.setEnabled(self._element_clipboard is not None and self._selected_slide() is not None)

    def _refresh_animation_controls(self) -> None:
        element = self._selected_element()
        enabled = element is not None
        controls = [
            self.animation_combo,
            self.animation_trigger_combo,
            self.animation_click_index_spin,
            self.animation_start_spin,
            self.animation_duration_spin,
            self.animation_easing_combo,
            self.animation_motion_x_spin,
            self.animation_motion_y_spin,
            self.animation_scale_spin,
        ]
        self._syncing_animation_controls = True
        try:
            for control in controls:
                control.setEnabled(bool(enabled))
            payload = animation_payload(element.animation) if element is not None else {
                "in_animation": "none",
                "trigger": "on_slide_start",
                "click_index": 0,
                "start_ms": 0,
                "duration_ms": 450,
                "easing": "ease_out",
                "motion_x": 0.0,
                "motion_y": 0.0,
                "scale": 1.0,
            }
            effect_index = self.animation_combo.findText(str(payload["in_animation"]), Qt.MatchFlag.MatchFixedString)
            self.animation_combo.setCurrentIndex(max(0, effect_index))
            trigger_index = self.animation_trigger_combo.findText(str(payload["trigger"]), Qt.MatchFlag.MatchFixedString)
            self.animation_trigger_combo.setCurrentIndex(max(0, trigger_index))
            self.animation_click_index_spin.setValue(int(payload.get("click_index", 0) or 0))
            self.animation_click_index_spin.setEnabled(bool(enabled) and str(payload["trigger"]) == "on_click")
            easing_index = self.animation_easing_combo.findText(str(payload["easing"]), Qt.MatchFlag.MatchFixedString)
            self.animation_easing_combo.setCurrentIndex(max(0, easing_index))
            self.animation_start_spin.setValue(int(payload["start_ms"]))
            self.animation_duration_spin.setValue(int(payload["duration_ms"]))
            self.animation_motion_x_spin.setValue(float(payload["motion_x"]))
            self.animation_motion_y_spin.setValue(float(payload["motion_y"]))
            self.animation_scale_spin.setValue(float(payload["scale"]))
        finally:
            self._syncing_animation_controls = False

    def _update_color_button(self, color: str) -> None:
        color = color or "#F5F7FA"
        self.color_button.setText(color.upper())
        text_color = "#FFFFFF" if QColor(color).lightness() < 128 else "#0E1117"
        self.color_button.setStyleSheet(
            f"QPushButton#PptColorButton {{ background: {color}; color: {text_color}; "
            "border: 1px solid #333333; border-radius: 6px; padding: 6px 10px; }"
            "QPushButton#PptColorButton:hover { border-color: #D85A30; }"
        )

    def _select_slide_index(self, index: int) -> None:
        if index < 0 or index >= len(self.deck.slides):
            return
        self._select_slide_id(self.deck.slides[index].id)

    def _select_slide_id(self, slide_id: str) -> None:
        self.timeline.select_slide(slide_id)
        current_playhead = int(getattr(self.timeline, "playhead_ms", 0) or 0)
        for clip in self.timeline.slide_clips:
            if clip.slide_id == slide_id:
                if not (int(clip.start_ms) <= current_playhead < int(clip.end_ms)):
                    self.timeline.playhead_ms = int(clip.start_ms)
                break
        self.selected_element_id = ""
        row = next((idx for idx, slide in enumerate(self.deck.slides) if slide.id == slide_id), -1)
        if row >= 0 and self.slide_list.currentRow() != row:
            self.slide_list.blockSignals(True)
            self.slide_list.setCurrentRow(row)
            self.slide_list.blockSignals(False)
        self._refresh_selected()

    def _select_element_id(self, element_id: str) -> None:
        ids = {element.id for element in self._slide_elements()}
        self.selected_element_id = element_id if element_id in ids else ""
        slide = self._selected_slide()
        self.canvas.set_slide(self.deck, slide, self.selected_element_id, playhead_ms=self._slide_local_playhead_ms(slide))
        self._refresh_element_list()
        self._refresh_font_controls()
        self._refresh_data_controls()
        self._refresh_image_controls()
        self._refresh_animation_controls()

    def _timeline_playhead_changed(self) -> None:
        clip = self.timeline.clip_at(int(getattr(self.timeline, "playhead_ms", 0) or 0))
        if clip is not None and clip.slide_id != self.timeline.selected_slide_id:
            self._select_slide_id(clip.slide_id)
            return
        slide = self._selected_slide()
        self.canvas.set_slide(self.deck, slide, self.selected_element_id, playhead_ms=self._slide_local_playhead_ms(slide))
        self.timeline_widget.update()
        self._refresh_animation_lane()

    def _select_animation_lane_item(self, element_id: str, local_ms: int) -> None:
        slide = self._selected_slide()
        if slide is None:
            return
        ids = {element.id for element in slide.elements}
        self.selected_element_id = element_id if element_id in ids else self.selected_element_id
        for clip in self.timeline.slide_clips:
            if clip.slide_id != slide.id:
                continue
            self.timeline.playhead_ms = int(clip.start_ms) + max(0, min(max(1, int(clip.duration_ms)), int(local_ms or 0)))
            break
        self._refresh_selected()

    def _animation_lane_timing_changed(self, element_id: str, start_ms: int, duration_ms: int) -> None:
        slide = self._selected_slide()
        if slide is None:
            return
        ids = {element.id for element in slide.elements}
        if element_id not in ids:
            return
        self.selected_element_id = element_id
        set_element_animation(
            self.deck,
            element_id,
            slide_id=slide.id,
            start_ms=int(start_ms),
            duration_ms=int(duration_ms),
        )
        for clip in self.timeline.slide_clips:
            if clip.slide_id == slide.id:
                self.timeline.playhead_ms = int(clip.start_ms) + max(0, min(max(1, int(clip.duration_ms)), int(start_ms)))
                break
        self.canvas.set_slide(self.deck, slide, self.selected_element_id, playhead_ms=self._slide_local_playhead_ms(slide))
        self._refresh_element_list()
        self._refresh_animation_controls()
        self.timeline_widget.update()
        self._refresh_animation_lane()

    def _update_play_button(self) -> None:
        button = getattr(self, "play_button", None)
        if button is None:
            return
        if self._ppt_playing:
            button.setText("Pause")
            button.setIcon(app_icon("pause", size=14, color="#D7DAE7"))
        else:
            button.setText("Play")
            button.setIcon(app_icon("play", size=14, color="#D7DAE7"))

    def _toggle_ppt_playback(self) -> None:
        if self._ppt_playing:
            self._ppt_playing = False
            self._ppt_play_timer.stop()
            self._update_play_button()
            return
        if not self.timeline.slide_clips:
            return
        total = self._timeline_total_ms()
        if int(self.timeline.playhead_ms) >= total - 1:
            self.timeline.playhead_ms = 0
        self._ppt_playing = True
        self._ppt_last_tick = time.monotonic()
        self._ppt_play_timer.start()
        self._update_play_button()

    def _stop_ppt_playback(self) -> None:
        self._ppt_playing = False
        self._ppt_play_timer.stop()
        clip = self.timeline.clip_at(int(getattr(self.timeline, "playhead_ms", 0) or 0))
        self.timeline.playhead_ms = int(clip.start_ms) if clip is not None else 0
        self._timeline_playhead_changed()
        self._update_play_button()

    def _advance_ppt_playback(self) -> None:
        if not self._ppt_playing:
            return
        now = time.monotonic()
        delta_ms = max(1, int(round((now - self._ppt_last_tick) * 1000.0)))
        self._ppt_last_tick = now
        total = self._timeline_total_ms()
        next_ms = int(getattr(self.timeline, "playhead_ms", 0) or 0) + delta_ms
        if next_ms >= total:
            self.timeline.playhead_ms = max(0, total - 1)
            self._ppt_playing = False
            self._ppt_play_timer.stop()
            self._update_play_button()
        else:
            self.timeline.playhead_ms = next_ms
        self._timeline_playhead_changed()

    def _select_element_row(self, index: int) -> None:
        item = self.element_list.item(index)
        self._select_element_id(str(item.data(Qt.ItemDataRole.UserRole)) if item else "")

    def _notes_changed(self) -> None:
        slide = self._selected_slide()
        if slide:
            slide.speaker_notes = self.notes.toPlainText()
            self._commit_history("Edit notes")

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.element_list and event.type() == QEvent.Type.KeyPress:
            if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
                if self._delete_selected_element():
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        text_focus = isinstance(self.focusWidget(), (QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox))
        if not text_focus and event.matches(QKeySequence.StandardKey.Copy):
            if self._copy_selected_element():
                event.accept()
                return
        if not text_focus and event.matches(QKeySequence.StandardKey.Paste):
            if self._paste_element() is not None:
                event.accept()
                return
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            if self._delete_selected_element():
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_save_or_discard_changes("closing"):
            event.accept()
        else:
            event.ignore()

    def _new_deck(self) -> None:
        if not self._confirm_save_or_discard_changes("creating a new deck"):
            return
        template_id = choose_template_id(self, mode="new")
        if not template_id:
            return
        self.set_deck(deck_from_selected_template(template_id))

    def _open_deck(self) -> None:
        if not self._confirm_save_or_discard_changes("opening another deck"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open PPT Project", "", PPTGEN_PROJECT_FILTER)
        if not path:
            return
        try:
            self.set_deck(load_deck_project(path), project_path=path)
        except Exception as exc:
            QMessageBox.warning(self, "Open failed", str(exc))

    def _import_pptx_file(self) -> None:
        if not self._confirm_save_or_discard_changes("importing a PPTX file"):
            return
        path, _ = QFileDialog.getOpenFileName(self, "Import PPTX", "", "PowerPoint (*.pptx);;All Files (*.*)")
        if not path:
            return
        try:
            deck = import_pptx_deck(path)
            self.set_deck(deck)
            self._dirty = True
            self._update_window_caption()
        except Exception as exc:
            QMessageBox.warning(self, "PPTX import failed", str(exc))

    def _open_recovery_deck(self) -> None:
        if not self._confirm_save_or_discard_changes("opening a recovery copy"):
            return
        candidates = list(self.recovery_candidates()["candidates"])
        if not candidates:
            QMessageBox.information(self, "Recovery", "No PPT recovery copies were found.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Open PPT Recovery Copy")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select a recovery copy to open as an unsaved deck.", dialog))
        listing = QListWidget(dialog)
        first_valid_row = -1
        for index, row in enumerate(candidates):
            path = str(row.get("path") or "")
            title = str(row.get("title") or Path(path).name)
            stamp = str(row.get("modified_iso") or "")
            slides = int(row.get("slide_count") or 0)
            valid = bool(row.get("valid"))
            suffix = f"{slides} slides - {stamp}" if valid else f"Unreadable - {row.get('reason') or ''}"
            item = QListWidgetItem(f"{title}\n{suffix}\n{path}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            if not valid:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            elif first_valid_row < 0:
                first_valid_row = index
            listing.addItem(item)
        if first_valid_row >= 0:
            listing.setCurrentRow(first_valid_row)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Open | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        item = listing.currentItem()
        if item is None:
            return
        try:
            self.open_recovery_copy(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        except Exception as exc:
            QMessageBox.warning(self, "Recovery failed", str(exc))

    def _save_deck(self) -> bool:
        if self.project_path is None:
            return self._save_deck_as()
        try:
            self.project_path = save_deck_project(self.deck, self.project_path)
            self._mark_saved()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False

    def _save_deck_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save PPT Project", "presentation.tgppt", PPTGEN_PROJECT_FILTER)
        if not path:
            return False
        try:
            self.project_path = save_deck_project(self.deck, path)
            self._mark_saved()
            self._refresh_all()
            return True
        except Exception as exc:
            QMessageBox.warning(self, "Save failed", str(exc))
            return False

    def _import_from_editor(self) -> None:
        if not self._confirm_save_or_discard_changes("importing the editor timeline"):
            return
        if self.source_owner is None:
            QMessageBox.information(self, "Import Timeline", "No editor timeline is connected to this window.")
            return
        try:
            deck = deck_from_editor_timeline(self.source_owner, title=self.deck.title or "Timeline Presentation")
        except Exception as exc:
            QMessageBox.warning(self, "Import Timeline failed", str(exc))
            return
        self.set_deck(deck)

    def _add_current_cut_image(self) -> None:
        if self.source_owner is None:
            QMessageBox.information(self, "Add Still Image", "No editor timeline is connected to this window.")
            return
        method = getattr(self.source_owner, "_ppt_add_timeline_clip_still", None)
        if not callable(method):
            QMessageBox.information(self, "Add Still Image", "Timeline still import is not available in this editor.")
            return
        try:
            setattr(self.source_owner, "_ppt_generator_window", self)
            method(slide_id=self.timeline.selected_slide_id)
        except Exception as exc:
            QMessageBox.warning(self, "Add Still Image failed", str(exc))

    def _choose_template(self) -> None:
        template_id = choose_template_id(self, mode="apply")
        if not template_id:
            return
        self.apply_template_to_current_slide(template_id)

    def apply_template_to_current_slide(self, template_id: str) -> SlideSpec:
        slide = self._selected_slide()
        if slide is None:
            raise RuntimeError("No slide is available")
        apply_template_to_slide(slide, template_id)
        self.timeline = PptTimeline.from_deck(self.deck)
        self.timeline.select_slide(slide.id)
        self.selected_element_id = ""
        self._refresh_all()
        return slide

    def _add_slide(self) -> None:
        number = len(self.deck.slides) + 1
        slide = SlideSpec(id=f"slide-{number:03d}", title=f"New Slide {number}", duration_ms=5000)
        slide.add_element(SlideElement.text_box(f"el-{number}-title", f"New Slide {number}", x=0.08, y=0.1, w=0.7, h=0.12, font_size=40, bold=True))
        self.timeline = add_slide(self.deck, slide)
        self.timeline.select_slide(slide.id)
        self._refresh_all()

    def _unique_slide_id(self, base: str) -> str:
        existing = {slide.id for slide in self.deck.slides}
        candidate = base
        suffix = 2
        while candidate in existing:
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def _duplicate_slide(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        try:
            index = self.deck.slides.index(slide)
        except ValueError:
            index = len(self.deck.slides) - 1
        clone = copy.deepcopy(slide)
        clone.id = self._unique_slide_id(f"{slide.id}-copy")
        clone.title = f"{slide.title or slide.id} Copy"
        for idx, element in enumerate(clone.elements, start=1):
            element.id = f"{clone.id}-el-{idx:03d}"
        self.timeline = add_slide(self.deck, clone, index=index + 1)
        self.timeline.select_slide(clone.id)
        self.selected_element_id = ""
        self._refresh_all()

    def _delete_slide(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        if len(self.deck.slides) <= 1:
            QMessageBox.information(self, "Delete Slide", "At least one slide must remain.")
            return
        index = self.deck.slides.index(slide) if slide in self.deck.slides else 0
        remaining = [row for row in self.deck.slides if row.id != slide.id]
        target_slide_id = remaining[min(index, len(remaining) - 1)].id if remaining else ""
        self.timeline = remove_slide(self.deck, slide.id)
        if target_slide_id:
            self.timeline.select_slide(target_slide_id)
        self.selected_element_id = ""
        self._refresh_all()

    def _delete_selected_element(self) -> bool:
        slide = self._selected_slide()
        element = self._selected_element()
        if slide is None or element is None or element.locked:
            return False
        try:
            index = slide.elements.index(element)
        except ValueError:
            return False
        del slide.elements[index]
        if slide.elements:
            self.selected_element_id = slide.elements[min(index, len(slide.elements) - 1)].id
        else:
            self.selected_element_id = ""
        self._refresh_selected()
        return True

    def _copy_selected_element(self) -> bool:
        element = self._selected_element()
        if element is None:
            return False
        self._element_clipboard = copy.deepcopy(element)
        self._refresh_element_tool_buttons()
        return True

    def _paste_element(self) -> SlideElement | None:
        slide = self._selected_slide()
        if slide is None or self._element_clipboard is None:
            return None
        clone = copy.deepcopy(self._element_clipboard)
        clone.id = unique_element_id(slide, f"{clone.id}-copy")
        clone.name = f"{clone.name or clone.kind} Copy"
        clone.x = max(0.0, min(1.0, float(clone.x) + 0.03))
        clone.y = max(0.0, min(1.0, float(clone.y) + 0.03))
        clone.z_index = max((int(row.z_index) for row in slide.elements), default=-1) + 1
        slide.add_element(clone)
        self.selected_element_id = clone.id
        self._refresh_selected()
        return clone

    def _duplicate_selected_element(self) -> SlideElement | None:
        element = self._selected_element()
        if element is None:
            return None
        try:
            _slide, clone = duplicate_element(self.deck, element.id, slide_id=self.timeline.selected_slide_id)
        except Exception as exc:
            QMessageBox.warning(self, "Duplicate failed", str(exc))
            return None
        self.selected_element_id = clone.id
        self._refresh_selected()
        return clone

    def _set_selected_z_order(self, mode: str) -> SlideElement | None:
        element = self._selected_element()
        if element is None:
            return None
        try:
            _slide, updated = set_element_z_order(self.deck, element.id, slide_id=self.timeline.selected_slide_id, mode=mode)
        except Exception as exc:
            QMessageBox.warning(self, "Layer order failed", str(exc))
            return None
        self.selected_element_id = updated.id
        self._refresh_selected()
        return updated

    def _align_selected_element(self, *, horizontal: str = "", vertical: str = "") -> SlideElement | None:
        element = self._selected_element()
        if element is None:
            return None
        try:
            _slide, updated = align_element(
                self.deck,
                element.id,
                slide_id=self.timeline.selected_slide_id,
                horizontal=horizontal,
                vertical=vertical,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Align failed", str(exc))
            return None
        self.selected_element_id = updated.id
        self._refresh_selected()
        return updated

    def _edit_selected_data(self) -> None:
        element = self._selected_element()
        if element is None:
            return
        changed = False
        if element.kind == "table":
            changed = edit_table_data(self, element)
        elif element.kind == "chart":
            changed = edit_chart_data(self, element)
        if changed:
            self._refresh_selected()

    def _choose_image_path(self, title: str = "Load Image") -> str:
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif);;All Files (*)",
        )
        return str(path or "")

    def _choose_image_for_selected(self) -> None:
        element = self._selected_element()
        if element is None or element.kind not in {"image", "image_placeholder"}:
            return
        path = self._choose_image_path("Replace Image" if element.kind == "image" else "Load Image")
        if not path:
            return
        try:
            self.add_image_file_to_slide(path, replace_element_id=element.id)
        except Exception as exc:
            QMessageBox.warning(self, "Image Load failed", str(exc))

    def _edit_header_footer(self) -> None:
        settings = header_footer_settings(self.deck)
        dialog = QDialog(self)
        dialog.setWindowTitle("Header / Footer")
        layout = QFormLayout(dialog)

        show_header = QCheckBox(dialog)
        show_header.setChecked(bool(settings.get("show_header")))
        header_text = QLineEdit(str(settings.get("header_text") or ""), dialog)
        layout.addRow("Show header", show_header)
        layout.addRow("Header text", header_text)

        show_footer = QCheckBox(dialog)
        show_footer.setChecked(bool(settings.get("show_footer")))
        footer_text = QLineEdit(str(settings.get("footer_text") or ""), dialog)
        layout.addRow("Show footer", show_footer)
        layout.addRow("Footer text", footer_text)

        show_date = QCheckBox(dialog)
        show_date.setChecked(bool(settings.get("show_date")))
        date_text = QLineEdit(str(settings.get("date_text") or ""), dialog)
        date_text.setPlaceholderText("Auto: YYYY-MM-DD")
        layout.addRow("Show date", show_date)
        layout.addRow("Date text", date_text)

        show_slide_number = QCheckBox(dialog)
        show_slide_number.setChecked(bool(settings.get("show_slide_number")))
        layout.addRow("Show slide #", show_slide_number)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, dialog)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        set_header_footer(
            self.deck,
            show_header=show_header.isChecked(),
            header_text=header_text.text().strip(),
            show_footer=show_footer.isChecked(),
            footer_text=footer_text.text().strip(),
            show_date=show_date.isChecked(),
            date_text=date_text.text().strip(),
            show_slide_number=show_slide_number.isChecked(),
        )
        self.canvas.update()
        self._commit_history("Edit header/footer")

    def _add_text(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        idx = len(slide.elements) + 1
        element = SlideElement.text_box(f"{slide.id}-text-{idx}", "New text block", x=0.12, y=0.68, w=0.64, h=0.12, font_size=26)
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _add_content_box(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        idx = len(slide.elements) + 1
        element = SlideElement(
            id=f"{slide.id}-content-{idx}",
            kind="shape",
            name="Content Box",
            x=0.12,
            y=0.26,
            w=0.58,
            h=0.36,
            style=ElementStyle(fill="#F7F9FC", stroke="#B8C2D6", stroke_width=1.0),
        )
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _add_table(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        idx = len(slide.elements) + 1
        element = SlideElement.table(f"{slide.id}-table-{idx}", x=0.12, y=0.26, w=0.62, h=0.34, rows=4, cols=3)
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _add_image_box(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        path = self._choose_image_path("Insert Image")
        if path:
            try:
                self.add_image_file_to_slide(path, x=0.18, y=0.24)
            except Exception as exc:
                QMessageBox.warning(self, "Image Load failed", str(exc))
            return
        idx = len(slide.elements) + 1
        element = SlideElement(
            id=f"{slide.id}-imagebox-{idx}",
            kind="image_placeholder",
            name="Image Box",
            x=0.58,
            y=0.24,
            w=0.28,
            h=0.34,
            style=ElementStyle(fill="#F3F6FA", stroke="#2F6FED", stroke_width=1.0),
        )
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _add_shape(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        idx = len(slide.elements) + 1
        element = SlideElement(
            id=f"{slide.id}-shape-{idx}",
            kind="shape",
            name="Shape",
            x=0.16,
            y=0.32,
            w=0.24,
            h=0.22,
            style=ElementStyle(fill="#EAF1FF", stroke="#2F6FED", stroke_width=1.4),
        )
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _add_line(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        idx = len(slide.elements) + 1
        element = SlideElement.line(f"{slide.id}-line-{idx}", x=0.18, y=0.58, w=0.46, h=0.03)
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _add_chart(self) -> None:
        slide = self._selected_slide()
        if not slide:
            return
        idx = len(slide.elements) + 1
        element = SlideElement.chart(f"{slide.id}-chart-{idx}", x=0.48, y=0.28, w=0.34, h=0.32)
        slide.add_element(element)
        self.selected_element_id = element.id
        self._refresh_selected()

    def _font_controls_changed(self, *_args) -> None:
        if self._syncing_text_controls:
            return
        element = self._selected_element()
        if not element or element.kind != "text":
            return
        element.style.font_family = self.font_combo.currentText() or self.deck.theme.font_family
        element.style.font_size = int(self.size_spin.value())
        element.style.bold = bool(self.bold_button.isChecked())
        element.style.italic = bool(self.italic_button.isChecked())
        element.style.underline = bool(self.underline_button.isChecked())
        element.style.align = self.align_combo.currentText() or "left"
        element.style.line_height = float(self.line_height_spin.value())
        self.canvas.update()
        self._commit_history("Format text")

    def _animation_controls_changed(self, *_args) -> None:
        if self._syncing_animation_controls:
            return
        element = self._selected_element()
        if element is None:
            return
        set_element_animation(
            self.deck,
            element.id,
            slide_id=self.timeline.selected_slide_id,
            in_animation=self.animation_combo.currentText(),
            out_animation="none",
            trigger=self.animation_trigger_combo.currentText(),
            click_index=int(self.animation_click_index_spin.value()),
            start_ms=int(self.animation_start_spin.value()),
            duration_ms=int(self.animation_duration_spin.value()),
            easing=self.animation_easing_combo.currentText(),
            motion_x=float(self.animation_motion_x_spin.value()),
            motion_y=float(self.animation_motion_y_spin.value()),
            scale=float(self.animation_scale_spin.value()),
        )
        self.canvas.update()
        self.timeline_widget.update()
        self._refresh_animation_lane()
        self._refresh_animation_controls()
        self._refresh_element_list()
        self._commit_history("Edit animation")

    def _choose_text_color(self) -> None:
        element = self._selected_element()
        if not element or element.kind != "text":
            return
        picked = QColorDialog.getColor(QColor(element.style.color), self, "Text Color")
        if not picked.isValid():
            return
        element.style.color = picked.name().upper()
        self._update_color_button(element.style.color)
        self.canvas.update()
        self._commit_history("Set text color")

    def _export_pptx(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PPTX", "pptgen.pptx", "PowerPoint (*.pptx)")
        if not path:
            return
        ensure_deck_actor_posters(self.deck)
        out = write_pptx_compatible(self.deck, path)
        QMessageBox.information(self, "Export complete", f"Wrote:\n{out}")

    def _export_pdf(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "pptgen.pdf", "PDF (*.pdf)")
        if not path:
            return
        ensure_deck_actor_posters(self.deck)
        result = export_deck_pdf(self.deck, path, backend="auto", timeout_sec=120)
        if result.get("ok"):
            backend = str(result.get("backend") or "PDF")
            QMessageBox.information(self, "Export complete", f"Wrote:\n{result.get('output_pdf')}\n\nBackend: {backend}")
            return
        attempts = [
            f"{row.get('host')}: {row.get('status')} - {row.get('reason') or row.get('stderr_tail') or 'no detail'}"
            for row in list(result.get("attempts") or [])
        ]
        detail = "\n".join(attempts) or str(result.get("reason") or "No PDF backend was available.")
        QMessageBox.warning(self, "PDF export failed", detail)

    def _export_video(self) -> None:
        if self._video_export_worker is not None and self._video_export_worker.isRunning():
            QMessageBox.information(self, "MP4 export", "An MP4 export is already running.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export MP4", "pptgen.mp4", "MP4 Video (*.mp4)")
        if not path:
            return
        ensure_deck_actor_posters(self.deck)
        audio_path = ""
        for key in ("narration_audio_path", "audio_path", "soundtrack_path"):
            audio_path = str(self.deck.metadata.get(key) or "").strip()
            if audio_path:
                break
        self._start_video_export(path, audio_path=audio_path)

    def _start_video_export(self, path: str | Path, *, audio_path: str = "") -> None:
        worker = PptVideoExportWorker(
            self.deck,
            path,
            timeline=self.timeline,
            fps=30,
            size=(1280, 720),
            audio_path=audio_path or None,
            parent=self,
        )
        dialog = QProgressDialog("Preparing MP4 export...", "Cancel", 0, 100, self)
        dialog.setWindowTitle("Export MP4")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setValue(0)
        dialog.canceled.connect(worker.cancel)

        worker.progressChanged.connect(self._video_export_progress_changed)
        worker.resultReady.connect(self._video_export_finished)
        worker.failed.connect(self._video_export_failed)
        worker.cancelled.connect(self._video_export_cancelled)
        worker.finished.connect(worker.deleteLater)

        self._video_export_worker = worker
        self._video_export_progress = dialog
        worker.start()

    def _video_export_progress_changed(self, event: object) -> None:
        dialog = self._video_export_progress
        if dialog is None:
            return
        data = dict(event) if isinstance(event, dict) else {}
        frames = int(data.get("frames_written") or 0)
        total = max(1, int(data.get("total_frames") or 1))
        percent = max(0, min(100, int(round(frames * 100 / total))))
        slide_id = str(data.get("slide_id") or "")
        dialog.setLabelText(f"Exporting MP4... {frames}/{total} frames {slide_id}".strip())
        dialog.setValue(percent)

    def _clear_video_export_worker(self) -> None:
        dialog = self._video_export_progress
        if dialog is not None:
            dialog.close()
        self._video_export_progress = None
        self._video_export_worker = None

    def _video_export_finished(self, result_obj: object) -> None:
        result = dict(result_obj) if isinstance(result_obj, dict) else {}
        self._clear_video_export_worker()
        audio_line = "Audio muxed" if result.get("audio_muxed") else "No audio"
        QMessageBox.information(
            self,
            "MP4 export complete",
            f"Wrote {result.get('frames_written', 0)} frames"
            f" with {result.get('transition_count', 0)} transitions. {audio_line}:\n{result.get('output_path') or ''}",
        )

    def _video_export_failed(self, message: str) -> None:
        self._clear_video_export_worker()
        QMessageBox.warning(self, "MP4 export failed", str(message))

    def _video_export_cancelled(self) -> None:
        self._clear_video_export_worker()
        QMessageBox.information(self, "MP4 export", "MP4 export cancelled.")

    def _export_pngs(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Export PNG slides")
        if not path:
            return
        out_dir = Path(path)
        ensure_deck_actor_posters(self.deck)
        render_deck_pngs(self.deck, out_dir)
        sheet = render_contact_sheet(self.deck, out_dir / "contact_sheet.png")
        QMessageBox.information(self, "Export complete", f"Wrote slide PNGs and:\n{sheet}")

    def _show_validation(self) -> None:
        report = validation_report(self.deck)
        issues = [row for row in list(report.get("issues") or []) if isinstance(row, dict)]
        if not issues:
            QMessageBox.information(self, "Validation", "No issues.")
            return
        text = "\n".join(f"[{row.get('severity')}] {row.get('code')}: {row.get('message')}" for row in issues[:25])
        QMessageBox.information(self, "Validation", text)


PptGeneratorPrototypeWindow = PptGeneratorWindow


__all__ = ["PptGeneratorPrototypeWindow", "PptGeneratorWindow", "SlideCanvas", "SlideTimelineWidget"]
