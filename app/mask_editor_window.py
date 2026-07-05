"""MaskEditorWindow — dedicated large-canvas mask editor.

Opens a resizable/maximisable dialog with the current video frame
at a comfortable size so precise rotoscope / polygon work doesn't
have to happen on the tiny main-preview panel.

Features
~~~~~~~~~
  * Maximise button (standard OS titlebar) — window flags set.
  * Zoom toolbar: 50 % / 100 % / 200 % / Fit + Ctrl+Wheel.
  * Three tool modes: Polygon (click vertices), Rect (GrabCut drag),
    Click (SAM / auto-GrabCut).
  * Tiger Orange mask overlay painted live as you draw.
  * Softness, Invert and Track-object controls in the toolbar.
  * OK → commit mask to node; Cancel → leave node unchanged.
"""
from __future__ import annotations

import json
from typing import Callable

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap, QPolygon, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.style import studio_chrome_qss


class _FrameCanvas(QLabel):
    """Zoomable frame canvas with interactive mask drawing tools.

    Internally the canvas always renders at
    ``(src_w * _zoom, src_h * _zoom)`` pixels.  The parent
    QScrollArea handles panning when zoomed above 100 %.

    Coordinate convention: every interaction converts screen-space
    pixel positions to normalised [0, 1] frame coordinates using the
    *zoomed* dimensions so zoom level is transparent to the mask
    math.
    """

    MIN_ZOOM = 0.1
    MAX_ZOOM = 8.0

    def __init__(self, rgb: np.ndarray, parent=None) -> None:
        super().__init__(parent)
        self._rgb = rgb
        self._src_h, self._src_w = rgb.shape[:2]
        self._zoom: float = 1.0

        self._tool = "rect"
        self._points: list[tuple[float, float]] = []
        self._rect_start: QPoint | None = None
        self._rect_end: QPoint | None = None
        self._mask: np.ndarray | None = None   # H×W uint8 at src res
        self._worker = None  # async click worker
        self._status_callback: Callable[[str], None] | None = None
        self._brush_radius_px: int = 18
        self._painting: bool = False
        self._last_brush_src: tuple[int, int] | None = None
        self._brush_preview_pos: QPoint | None = None
        self._preview_softness_norm: float = 0.005
        self._preview_invert: bool = False
        self._undo_stack: list[tuple[np.ndarray | None, list[tuple[float, float]]]] = []
        self._redo_stack: list[tuple[np.ndarray | None, list[tuple[float, float]]]] = []

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        self._rebuild_display()

    # ----------------------------------------------------------------
    # Zoom management
    # ----------------------------------------------------------------

    def zoom(self) -> float:
        return self._zoom

    def set_zoom(self, z: float, *, anchor: QPoint | None = None) -> None:
        """Apply new zoom level and resize the widget.  ``anchor`` is
        the viewport-space pixel under the cursor so the scroll area
        can keep that point stable after the resize."""
        z = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(z)))
        self._zoom = z
        self._rebuild_display()

    def fit_to_viewport(self) -> None:
        """Scale to fill the parent viewport while keeping the full
        frame visible (letterbox / pillarbox)."""
        sa = self.parent()
        if sa is None:
            return
        vw, vh = sa.width() - 4, sa.height() - 4
        if vw <= 0 or vh <= 0:
            return
        z = min(vw / max(1, self._src_w), vh / max(1, self._src_h))
        self.set_zoom(z)

    # ----------------------------------------------------------------
    # Internal helpers
    # ----------------------------------------------------------------

    def _disp_size(self) -> tuple[int, int]:
        return int(self._src_w * self._zoom), int(self._src_h * self._zoom)

    def _rebuild_display(self) -> None:
        dw, dh = self._disp_size()
        self.setFixedSize(dw, dh)
        self._repaint_overlay()

    def _norm(self, pos: QPoint) -> tuple[float, float]:
        """Screen-space pos → normalised (nx, ny) in [0, 1]."""
        dw, dh = self._disp_size()
        return pos.x() / max(1, dw), pos.y() / max(1, dh)

    # ----------------------------------------------------------------
    # Tool state
    # ----------------------------------------------------------------

    def set_tool(self, tool: str) -> None:
        self._tool = tool
        if tool != "polygon":
            self._points = []
        if tool != "rect":
            self._rect_start = self._rect_end = None
        if tool not in {"fg_brush", "bg_brush"}:
            self._painting = False
            self._last_brush_src = None
            self._brush_preview_pos = None
        self._repaint_overlay()

    def set_polygon_points(self, pts: list[tuple[float, float]]) -> None:
        self._points = list(pts)
        self._mask = self._eval_polygon_mask()
        self._repaint_overlay()

    def current_polygon_points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def current_mask(self) -> np.ndarray | None:
        return self._mask

    def set_status_callback(self, callback: Callable[[str], None] | None) -> None:
        self._status_callback = callback

    def _set_status(self, text: str) -> None:
        if self._status_callback is not None:
            try:
                self._status_callback(text)
            except Exception:
                pass

    def _snapshot(self) -> tuple[np.ndarray | None, list[tuple[float, float]]]:
        return (
            None if self._mask is None else self._mask.copy(),
            list(self._points),
        )

    def _restore_snapshot(self, snapshot: tuple[np.ndarray | None, list[tuple[float, float]]]) -> None:
        mask, points = snapshot
        self._mask = None if mask is None else mask.copy()
        self._points = list(points)

    def _push_history(self) -> None:
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo_mask(self) -> bool:
        if not self._undo_stack:
            self._set_status("Nothing to undo.")
            return False
        self._redo_stack.append(self._snapshot())
        self._restore_snapshot(self._undo_stack.pop())
        self._repaint_overlay()
        self._set_status("Mask undo.")
        return True

    def redo_mask(self) -> bool:
        if not self._redo_stack:
            self._set_status("Nothing to redo.")
            return False
        self._undo_stack.append(self._snapshot())
        self._restore_snapshot(self._redo_stack.pop())
        self._repaint_overlay()
        self._set_status("Mask redo.")
        return True

    def set_brush_radius(self, radius_px: int) -> None:
        self._brush_radius_px = max(1, int(radius_px))

    def set_preview_params(self, *, softness_norm: float, invert: bool) -> None:
        self._preview_softness_norm = max(0.0, float(softness_norm))
        self._preview_invert = bool(invert)
        self._repaint_overlay()

    def clear(self) -> None:
        if self._mask is not None or self._points:
            self._push_history()
        self._points = []
        self._rect_start = self._rect_end = None
        self._mask = None
        self._repaint_overlay()

    def postprocess_mask(self, mode: str) -> bool:
        if self._mask is None:
            self._set_status("No mask to edit.")
            return False
        self._push_history()
        try:
            import cv2
            from app.node_mask import _clean_binary_mask
        except Exception:
            self._set_status("Mask cleanup needs OpenCV.")
            return False
        src = np.where(self._mask > 127, 255, 0).astype(np.uint8)
        k = max(3, int(round(min(src.shape[:2]) * 0.006)) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        if mode == "shrink":
            out = cv2.erode(src, kernel, iterations=1)
            status = "Mask shrunk."
        elif mode == "expand":
            out = cv2.dilate(src, kernel, iterations=1)
            status = "Mask expanded."
        else:
            out = _clean_binary_mask(cv2, src)
            status = "Mask cleaned: kept the strongest foreground region."
        self._mask = out
        self._repaint_overlay()
        self._set_status(status)
        return True

    def auto_detect_object(self) -> bool:
        try:
            from app.node_mask import grabcut_from_rect
        except Exception:
            self._set_status("Auto detect needs OpenCV.")
            return False
        self._push_history()
        result = grabcut_from_rect(
            self._rgb,
            (0.05, 0.05, 0.90, 0.90),
            iterations=4,
            seed_point=(0.5, 0.55),
            return_info=True,
        )
        mask, info = result if isinstance(result, tuple) else (result, {})
        if mask is None:
            self._set_status("Auto detect failed. Try Click or a tighter rectangle.")
            return False
        self._mask = mask
        self._repaint_overlay()
        coverage = float((info or {}).get("coverage", 0.0)) * 100.0
        suggestion = str((info or {}).get("suggestion", "Auto mask ready."))
        self._set_status(f"Auto {coverage:.1f}% | {suggestion}")
        return True

    def _ensure_bitmap_mask(self) -> np.ndarray:
        if self._mask is None:
            self._mask = np.zeros((self._src_h, self._src_w), dtype=np.uint8)
        return self._mask

    def _src_point(self, pos: QPoint) -> tuple[int, int]:
        nx, ny = self._norm(pos)
        x = int(round(max(0.0, min(1.0, nx)) * (self._src_w - 1)))
        y = int(round(max(0.0, min(1.0, ny)) * (self._src_h - 1)))
        return x, y

    def _paint_brush(self, pos: QPoint, *, foreground: bool) -> None:
        try:
            import cv2
        except Exception:
            self._set_status("Brush needs OpenCV.")
            return
        mask = self._ensure_bitmap_mask()
        x, y = self._src_point(pos)
        value = 255 if foreground else 0
        radius = max(1, int(self._brush_radius_px))
        if self._last_brush_src is not None:
            lx, ly = self._last_brush_src
            cv2.line(mask, (lx, ly), (x, y), int(value), thickness=radius * 2, lineType=cv2.LINE_AA)
        cv2.circle(mask, (x, y), radius, int(value), thickness=-1, lineType=cv2.LINE_AA)
        self._last_brush_src = (x, y)
        self._mask = mask
        self._brush_preview_pos = pos
        self._repaint_overlay()

    # ----------------------------------------------------------------
    # Mask evaluation
    # ----------------------------------------------------------------

    def _eval_polygon_mask(self) -> np.ndarray | None:
        if len(self._points) < 3:
            return None
        try:
            import cv2
        except ImportError:
            return None
        h, w = self._rgb.shape[:2]
        pts = np.array([[int(x * w), int(y * h)] for x, y in self._points],
                       dtype=np.int32)
        m = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(m, [pts], 255)
        return m

    # ----------------------------------------------------------------
    # Overlay paint
    # ----------------------------------------------------------------

    def _repaint_overlay(self) -> None:
        dw, dh = self._disp_size()
        if dw <= 0 or dh <= 0:
            return
        # Scale source RGB to display size
        try:
            import cv2
            rgb_disp = cv2.resize(self._rgb, (dw, dh), interpolation=cv2.INTER_LINEAR)
        except Exception:
            rgb_disp = self._rgb
        img = QImage(rgb_disp.data, dw, dh, rgb_disp.strides[0],
                     QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(img.copy())
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Mask fill (scaled from src-res mask)
        if self._mask is not None:
            try:
                import cv2 as _cv2
                m_src = self._mask
                soft_px = max(0.0, self._preview_softness_norm) * min(self._src_w, self._src_h)
                if soft_px >= 1.0:
                    ksize = max(3, int(round(soft_px)) | 1)
                    m_src = _cv2.GaussianBlur(m_src, (ksize, ksize), soft_px / 2.0)
                if self._preview_invert:
                    m_src = 255 - m_src
                m_disp = _cv2.resize(m_src, (dw, dh), interpolation=_cv2.INTER_LINEAR)
            except Exception:
                m_disp = self._mask
                if self._preview_invert:
                    m_disp = 255 - m_disp
            if m_disp.shape[:2] != (dh, dw):
                y_idx = np.linspace(0, m_disp.shape[0] - 1, dh).astype(np.int32)
                x_idx = np.linspace(0, m_disp.shape[1] - 1, dw).astype(np.int32)
                m_disp = m_disp[y_idx[:, None], x_idx[None, :]]
            m_disp = np.ascontiguousarray(m_disp, dtype=np.uint8)
            alpha = ((m_disp.astype(np.uint16) * 140) // 255).astype(np.uint8)
            rgba = np.zeros((dh, dw, 4), dtype=np.uint8)
            rgba[..., 0] = 142
            rgba[..., 1] = 152
            rgba[..., 2] = 168
            rgba[..., 3] = alpha
            ov = QImage(
                rgba.data, dw, dh, rgba.strides[0], QImage.Format.Format_RGBA8888,
            ).copy()
            painter.drawImage(0, 0, ov)

        # Dashed rect preview while dragging
        if (self._mask is None and self._rect_start is not None
                and self._rect_end is not None):
            pen = QPen(QColor("#8E98A8"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(142, 152, 168, 44))
            painter.drawRect(QRect(self._rect_start, self._rect_end).normalized())

        # Polygon in-progress
        if self._tool == "polygon" and self._points:
            pts_px = [QPoint(int(x * dw), int(y * dh)) for x, y in self._points]
            painter.setPen(QPen(QColor("#8E98A8"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if len(pts_px) >= 3:
                painter.drawPolygon(QPolygon(pts_px))
            elif len(pts_px) == 2:
                painter.drawLine(pts_px[0], pts_px[1])
            for p in pts_px:
                painter.setBrush(QColor("#F0F3F7"))
                painter.setPen(QPen(QColor("#8E98A8"), 2))
                painter.drawEllipse(p, 5, 5)

        if self._tool in {"fg_brush", "bg_brush"} and self._brush_preview_pos is not None:
            color = QColor("#87A495") if self._tool == "fg_brush" else QColor("#8E98A8")
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            r = max(2, int(round(self._brush_radius_px * self._zoom)))
            painter.drawEllipse(self._brush_preview_pos, r, r)

        painter.end()
        self.setPixmap(pix)

    # ----------------------------------------------------------------
    # Mouse events
    # ----------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        nx, ny = self._norm(pos)
        if self._tool == "polygon":
            self._push_history()
            self._points.append((nx, ny))
            self._mask = self._eval_polygon_mask()
            self._repaint_overlay()
        elif self._tool == "rect":
            self._rect_start = pos
            self._rect_end = pos
            self._mask = None
            self._repaint_overlay()
        elif self._tool == "click":
            self._push_history()
            self._run_click(nx, ny)
        elif self._tool in {"fg_brush", "bg_brush"}:
            self._push_history()
            self._painting = True
            self._last_brush_src = None
            self._paint_brush(pos, foreground=self._tool == "fg_brush")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._tool == "polygon" and len(self._points) >= 3:
            self._push_history()
            if len(self._points) > 3:
                self._points = self._points[:-1]
            self._mask = self._eval_polygon_mask()
            self._repaint_overlay()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._tool == "rect" and self._rect_start is not None:
            self._rect_end = event.position().toPoint()
            self._repaint_overlay()
        elif self._tool in {"fg_brush", "bg_brush"}:
            pos = event.position().toPoint()
            if self._painting:
                self._paint_brush(pos, foreground=self._tool == "fg_brush")
            else:
                self._brush_preview_pos = pos
                self._repaint_overlay()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (self._tool == "rect" and self._rect_start is not None
                and self._rect_end is not None):
            dw, dh = self._disp_size()
            x1 = min(self._rect_start.x(), self._rect_end.x())
            y1 = min(self._rect_start.y(), self._rect_end.y())
            x2 = max(self._rect_start.x(), self._rect_end.x())
            y2 = max(self._rect_start.y(), self._rect_end.y())
            nw = (x2 - x1) / max(1, dw)
            nh = (y2 - y1) / max(1, dh)
            nx, ny = x1 / max(1, dw), y1 / max(1, dh)
            self._rect_start = self._rect_end = None
            if nw > 0.005 and nh > 0.005:
                self._push_history()
                self._run_grabcut(nx, ny, nw, nh)
        if self._tool in {"fg_brush", "bg_brush"}:
            self._painting = False
            self._last_brush_src = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Ctrl+Wheel = zoom in/out anchored at cursor."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.set_zoom(self._zoom * factor)
            event.accept()
        else:
            super().wheelEvent(event)

    # ----------------------------------------------------------------
    # Segmentation runners
    # ----------------------------------------------------------------

    def _run_grabcut(self, nx, ny, nw, nh) -> None:
        from app.node_mask import grabcut_from_rect
        result = grabcut_from_rect(
            self._rgb,
            (nx, ny, nw, nh),
            iterations=4,
            return_info=True,
        )
        m, info = result if isinstance(result, tuple) else (result, {})
        if m is not None:
            self._mask = m
            self._repaint_overlay()
            coverage = float((info or {}).get("coverage", 0.0)) * 100.0
            suggestion = str((info or {}).get("suggestion", "Mask ready."))
            self._set_status(f"GrabCut {coverage:.1f}% | {suggestion}")

    def _run_click(self, nx, ny) -> None:
        """Run SAM / GrabCut in a QThread so the UI stays responsive.
        While processing, the cursor changes to a wait cursor and a
        short status message appears in the hint label of the parent
        MaskEditorWindow (found by walking up the widget hierarchy)."""
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication
        # Show wait cursor immediately so the user knows something is
        # happening (SAM on CPU can take 2-5 seconds first call).
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        rgb = self._rgb.copy()
        src_w, src_h = self._src_w, self._src_h

        class _Worker(QThread):
            def __init__(self, rgb, nx, ny, src_w, src_h):
                super().__init__()
                self._rgb = rgb
                self._nx, self._ny = nx, ny
                self._src_w, self._src_h = src_w, src_h
                self.result = None
                self.info = {}

            def run(self):
                from app.sam_segment import is_sam_available, sam_mask_from_point
                m = None
                if is_sam_available():
                    m = sam_mask_from_point(self._rgb, self._nx, self._ny)
                    if m is not None:
                        self.info = {
                            "quality": "sam",
                            "suggestion": "SAM mask ready. Use Clean/Shrink/Expand if needed.",
                        }
                if m is None:
                    pw = 0.25
                    ph = pw * max(1, self._src_w) / max(1, self._src_h)
                    x0 = max(0.0, self._nx - pw / 2)
                    y0 = max(0.0, self._ny - ph / 2)
                    from app.node_mask import grabcut_from_rect
                    result = grabcut_from_rect(
                        self._rgb,
                        (x0, y0, pw, ph),
                        iterations=4,
                        seed_point=(self._nx, self._ny),
                        return_info=True,
                    )
                    m, self.info = result if isinstance(result, tuple) else (result, {})
                self.result = m

        self._worker = _Worker(rgb, nx, ny, src_w, src_h)
        self._worker.finished.connect(self._on_click_done)
        self._worker.start()

    def _on_click_done(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.restoreOverrideCursor()
        if self._worker is not None and self._worker.result is not None:
            self._mask = self._worker.result
            self._repaint_overlay()
            suggestion = str(getattr(self._worker, "info", {}).get("suggestion", "Mask ready."))
            self._set_status(suggestion)
        self._worker = None


# ---------------------------------------------------------------------------
# MaskEditorWindow
# ---------------------------------------------------------------------------

class MaskEditorWindow(QDialog):
    """Large-canvas rotoscope / mask editor.

    Opens as a resizable, maximisable modal dialog so the user can
    work at a comfortable size rather than the tiny main preview.
    """

    def __init__(
        self,
        rgb_frame: np.ndarray,
        node,
        on_commit: Callable | None = None,
        frame_idx: int = 0,
        parent=None,
    ) -> None:
        super().__init__(
            parent,
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint,
        )
        self._node = node
        self._on_commit = on_commit
        self._frame_idx = int(frame_idx)
        self.setWindowTitle(tr("maskeditor.title"))
        self.setMinimumSize(700, 520)
        self.resize(960, 700)
        self.setStyleSheet(studio_chrome_qss(
            "QDialog { background:#101112; color:#D7DCE4; }"
            "QPushButton#ToolButton {"
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2D333B,stop:0.52 #23282F,stop:1 #171A1F);"
            "color:#F0F3F7; border:1px solid #4A515B;"
            "border-radius:8px; padding:5px 10px; font-size:11px; font-weight:700;"
            "}"
            "QPushButton#ToolButton:hover { background:#303740; border-color:#697585; }"
            "QPushButton#ToolButton:checked { background:#242B34; border-color:#8E98A8; color:#FFFFFF; }"
            "QCheckBox { color:#B9C1CE; spacing:6px; }"
            "QScrollArea { background:#0D0F12; border:1px solid #262B32; border-radius:8px; }"
            "QSlider::groove:horizontal { background:#252A31; height:5px; border-radius:3px; border:none; }"
            "QSlider::sub-page:horizontal { background:#6F7B8C; border-radius:3px; }"
            "QSlider::add-page:horizontal { background:#252A31; border-radius:3px; }"
            "QSlider::handle:horizontal { background:#D9DEE7; width:12px; height:12px; border:1px solid #626D7B; border-radius:6px; margin:-4px 0; }"
            "QSlider::handle:horizontal:hover { background:#EFF2F6; border-color:#8E98A8; }"
            "QDialogButtonBox QPushButton {"
            "background:#20252B; color:#F0F3F7; border:1px solid #3E4651;"
            "border-radius:8px; padding:6px 16px; font-weight:700;"
            "}"
            "QDialogButtonBox QPushButton:hover { background:#303740; border-color:#697585; }"
        ) + (
            "QPushButton#ToolButton {"
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2D333B,stop:0.52 #23282F,stop:1 #171A1F);"
            "color:#F0F3F7; border:1px solid #4A515B;"
            "border-radius:8px; padding:4px 8px; font-size:11px; font-weight:700;"
            "}"
            "QPushButton#ToolButton:hover { background:#303740; border-color:#697585; }"
            "QPushButton#ToolButton:pressed { background:#181C22; border-color:#7A8492; }"
            "QPushButton#ToolButton:checked { background:#242B34; border-color:#8E98A8; color:#FFFFFF; }"
            "QDialogButtonBox QPushButton {"
            "background:#20252B; color:#F0F3F7; border:1px solid #3E4651;"
            "border-radius:8px; padding:6px 16px; font-weight:700;"
            "}"
            "QDialogButtonBox QPushButton:hover { background:#303740; border-color:#697585; }"
        ))

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ---- Tool bar ----
        tb = QHBoxLayout()
        tb.setSpacing(6)
        def _icon_button(btn: QPushButton, icon_name: str, tooltip: str, *, width: int = 42) -> QPushButton:
            btn.setText("")
            btn.setFixedSize(width, 34)
            btn.setIcon(app_icon(icon_name, size=15, color="#F0F3F7"))
            btn.setIconSize(icon_size(15))
            btn.setToolTip(tooltip)
            return btn

        self._tool_btns: list[QPushButton] = []
        for key, label, icon_name in (
            ("polygon", tr("maskeditor.tool.polygon"), "layers"),
            ("rect",    tr("maskeditor.tool.rect"), "fit"),
            ("click",   tr("maskeditor.tool.click"), "target"),
            ("fg_brush", "FG Brush", "person"),
            ("bg_brush", "BG Brush", "blur"),
        ):
            btn = QPushButton("")
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            _icon_button(btn, icon_name, label)
            btn.clicked.connect(lambda _c, k=key: self._set_tool(k))
            tb.addWidget(btn)
            self._tool_btns.append(btn)

        tb.addSpacing(12)
        clear_btn = QPushButton("")
        clear_btn.setObjectName("ToolButton")
        _icon_button(clear_btn, "x", tr("maskeditor.btn.clear"))
        clear_btn.clicked.connect(self._clear)
        tb.addWidget(clear_btn)

        auto_btn = QPushButton("")
        auto_btn.setObjectName("ToolButton")
        _icon_button(auto_btn, "spark", "Auto-detect the strongest object in the frame")
        auto_btn.clicked.connect(lambda: self._canvas.auto_detect_object())
        tb.addWidget(auto_btn)

        clean_btn = QPushButton("")
        clean_btn.setObjectName("ToolButton")
        _icon_button(clean_btn, "scissors", "Remove spill and keep the strongest foreground region")
        clean_btn.clicked.connect(lambda: self._postprocess_mask("clean"))
        tb.addWidget(clean_btn)

        shrink_btn = QPushButton("")
        shrink_btn.setObjectName("ToolButton")
        _icon_button(shrink_btn, "previous", "Contract the current mask by one step")
        shrink_btn.clicked.connect(lambda: self._postprocess_mask("shrink"))
        tb.addWidget(shrink_btn)

        expand_btn = QPushButton("")
        expand_btn.setObjectName("ToolButton")
        _icon_button(expand_btn, "next", "Expand the current mask by one step")
        expand_btn.clicked.connect(lambda: self._postprocess_mask("expand"))
        tb.addWidget(expand_btn)

        undo_btn = QPushButton("")
        undo_btn.setObjectName("ToolButton")
        _icon_button(undo_btn, "previous", "Undo mask edit")
        undo_btn.clicked.connect(lambda: self._canvas.undo_mask())
        tb.addWidget(undo_btn)

        redo_btn = QPushButton("")
        redo_btn.setObjectName("ToolButton")
        _icon_button(redo_btn, "next", "Redo mask edit")
        redo_btn.clicked.connect(lambda: self._canvas.redo_mask())
        tb.addWidget(redo_btn)

        tb.addStretch(1)

        # Zoom controls — clearly labelled so users know what they do
        zoom_out_btn = QPushButton("")
        zoom_out_btn.setObjectName("ToolButton")
        _icon_button(zoom_out_btn, "zoom", "Zoom out (Ctrl+Wheel)", width=38)
        zoom_out_btn.clicked.connect(lambda: self._step_zoom(-1))
        tb.addWidget(zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(46)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setStyleSheet(
            "color:#B9C1CE; font-size:11px; background:#15181D; "
            "border:1px solid #30363D; border-radius:6px; padding:2px;"
        )
        tb.addWidget(self._zoom_label)

        zoom_in_btn = QPushButton("")
        zoom_in_btn.setObjectName("ToolButton")
        _icon_button(zoom_in_btn, "zoom", "Zoom in (Ctrl+Wheel)", width=38)
        zoom_in_btn.clicked.connect(lambda: self._step_zoom(+1))
        tb.addWidget(zoom_in_btn)

        fit_btn = QPushButton("")
        fit_btn.setObjectName("ToolButton")
        _icon_button(fit_btn, "fit", "Fit frame to window", width=42)
        fit_btn.clicked.connect(self._fit)
        tb.addWidget(fit_btn)

        tb.addSpacing(12)

        soft_lbl = QLabel(tr("maskeditor.softness"))
        soft_lbl.setStyleSheet("color:#A8B0BD; font-size:11px;")
        tb.addWidget(soft_lbl)
        self._softness_sld = QSlider(Qt.Orientation.Horizontal)
        self._softness_sld.setRange(0, 50)
        self._softness_sld.setValue(5)
        self._softness_sld.setFixedWidth(70)
        tb.addWidget(self._softness_sld)

        brush_lbl = QLabel("Brush")
        brush_lbl.setStyleSheet("color:#A8B0BD; font-size:11px;")
        tb.addWidget(brush_lbl)
        self._brush_sld = QSlider(Qt.Orientation.Horizontal)
        self._brush_sld.setRange(2, 80)
        self._brush_sld.setValue(18)
        self._brush_sld.setFixedWidth(70)
        tb.addWidget(self._brush_sld)

        self._invert_chk = QCheckBox(tr("maskeditor.invert"))
        tb.addWidget(self._invert_chk)
        self._invert_chk.setToolTip(tr("maskeditor.invert.tip"))
        self._track_chk = QCheckBox(tr("maskeditor.track"))
        self._track_chk.setToolTip(tr("maskeditor.track.tip"))
        tb.addWidget(self._track_chk)

        reset_track_btn = QPushButton("")
        reset_track_btn.setObjectName("ToolButton")
        _icon_button(reset_track_btn, "reset", tr("maskeditor.track.reset.tip"))
        reset_track_btn.clicked.connect(self._reset_tracking_cache)
        tb.addWidget(reset_track_btn)

        add_correction_btn = QPushButton("")
        add_correction_btn.setObjectName("ToolButton")
        _icon_button(add_correction_btn, "keyframe", tr("maskeditor.track.correction.tip"))
        add_correction_btn.clicked.connect(self._add_tracking_correction)
        tb.addWidget(add_correction_btn)

        clear_corrections_btn = QPushButton("")
        clear_corrections_btn.setObjectName("ToolButton")
        _icon_button(clear_corrections_btn, "trash", tr("maskeditor.track.clear_corrections.tip"))
        clear_corrections_btn.clicked.connect(self._clear_tracking_corrections)
        tb.addWidget(clear_corrections_btn)

        root.addLayout(tb)

        # ---- Scroll area + canvas ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas = _FrameCanvas(rgb_frame)
        self._canvas.set_status_callback(self._set_hint)
        self._scroll.setWidget(self._canvas)
        root.addWidget(self._scroll, stretch=1)
        self._brush_sld.valueChanged.connect(self._canvas.set_brush_radius)
        self._softness_sld.valueChanged.connect(lambda _v: self._update_mask_preview_params())
        self._invert_chk.toggled.connect(lambda _v: self._update_mask_preview_params())
        self._update_mask_preview_params()

        # ---- Hint ----
        self._hint = QLabel(tr("maskeditor.hint.rect"))
        self._hint.setStyleSheet("color:#8C95A3; font-size:11px;")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._hint)

        self._track_status = QLabel("")
        self._track_status.setStyleSheet("color:#8C95A3; font-size:10px;")
        self._track_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._track_status)

        self._vfx_status = QLabel("")
        self._vfx_status.setStyleSheet("color:#B9C1CE; font-size:10px;")
        self._vfx_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vfx_status.setWordWrap(True)
        root.addWidget(self._vfx_status)

        graph_row = QHBoxLayout()
        graph_row.addStretch(1)
        self._vfx_graph_btn = QPushButton("VFX Graph")
        self._vfx_graph_btn.setObjectName("ToolButton")
        self._vfx_graph_btn.setToolTip("Inspect the mini compositor payload for this mask.")
        self._vfx_graph_btn.clicked.connect(self.show_vfx_node_graph)
        graph_row.addWidget(self._vfx_graph_btn)
        graph_row.addStretch(1)
        root.addLayout(graph_row)

        # ---- Dialog buttons ----
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        for button in bb.buttons():
            button.setDefault(False)
            button.setAutoDefault(False)
            button.setObjectName("MaskDialogButton")
            button.setStyleSheet(
                "QPushButton#MaskDialogButton {"
                "background:#20252B; color:#F0F3F7; border:1px solid #3E4651;"
                "border-radius:8px; padding:7px 18px; font-weight:700;"
                "}"
                "QPushButton#MaskDialogButton:hover { background:#303740; border-color:#697585; }"
                "QPushButton#MaskDialogButton:pressed { background:#181C22; border-color:#7A8492; }"
            )
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        # Default tool
        self._set_tool("rect")
        self._update_tracking_status()

    # ---- zoom ----

    def _step_zoom(self, direction: int) -> None:
        factor = 1.25 if direction > 0 else 1 / 1.25
        self._canvas.set_zoom(self._canvas.zoom() * factor)
        self._update_zoom_label()

    def _fit(self) -> None:
        self._canvas.fit_to_viewport()
        self._update_zoom_label()

    def _update_zoom_label(self) -> None:
        self._zoom_label.setText(f"{int(round(self._canvas.zoom() * 100))}%")

    def _set_hint(self, text: str) -> None:
        self._hint.setText(str(text or ""))

    def _update_mask_preview_params(self) -> None:
        self._canvas.set_preview_params(
            softness_norm=self._softness_sld.value() / 1000.0,
            invert=self._invert_chk.isChecked(),
        )
        if hasattr(self, "_vfx_status"):
            self._vfx_status.setText(self.vfx_status_text())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self._canvas.undo_mask()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Y:
                self._canvas.redo_mask()
                event.accept()
                return
        super().keyPressEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Fit to viewport on first show so the frame fills the canvas.
        self._canvas.fit_to_viewport()
        self._update_zoom_label()

    # ---- tool ----

    def _set_tool(self, tool: str) -> None:
        for btn in self._tool_btns:
            btn.setChecked(False)
        idx = {
            "polygon": 0,
            "rect": 1,
            "click": 2,
            "fg_brush": 3,
            "bg_brush": 4,
        }.get(tool, 1)
        self._tool_btns[idx].setChecked(True)
        self._canvas.set_tool(tool)
        hints = {
            "polygon": tr("maskeditor.hint.polygon"),
            "rect":    tr("maskeditor.hint.rect"),
            "click":   tr("maskeditor.hint.click"),
            "fg_brush": "Paint foreground into the mask. Ctrl+Z/Ctrl+Y are supported.",
            "bg_brush": "Paint background out of the mask. Ctrl+Z/Ctrl+Y are supported.",
        }
        self._hint.setText(hints.get(tool, ""))

    def _clear(self) -> None:
        self._canvas.clear()
        self._set_tool(self._canvas._tool)

    def _postprocess_mask(self, mode: str) -> None:
        self._canvas.postprocess_mask(mode)

    def _tracking_mask(self):
        try:
            from app.node_mask import BitmapMask
        except Exception:
            return None
        masks = getattr(self._node, "masks", None) or []
        if not masks:
            return None
        mask = masks[0]
        if isinstance(mask, BitmapMask) and getattr(mask, "track_object", False):
            return mask
        return None

    def _current_mask_for_commit(self) -> np.ndarray | None:
        mask = self._canvas.current_mask()
        if mask is None and len(self._canvas.current_polygon_points()) >= 3:
            mask = self._canvas._eval_polygon_mask()
        return mask

    def _update_tracking_status(self) -> None:
        mask = self._tracking_mask()
        if mask is None:
            self._track_status.setText(f"Frame {self._frame_idx}: no tracked mask selected")
            if hasattr(self, "_vfx_status"):
                self._vfx_status.setText(self.vfx_status_text())
            return
        try:
            status = mask.tracking_status_text()
        except Exception:
            status = "Tracking status unavailable"
        self._track_status.setText(f"Frame {self._frame_idx} | {status}")
        if hasattr(self, "_vfx_status"):
            self._vfx_status.setText(self.vfx_status_text())

    def _reset_tracking_cache(self) -> None:
        mask = self._tracking_mask()
        if mask is None:
            self._update_tracking_status()
            return
        mask.reset_tracking_cache(clear_corrections=False)
        self._node.update()
        if self._on_commit:
            try:
                self._on_commit()
            except Exception:
                pass
        self._update_tracking_status()

    def _clear_tracking_corrections(self) -> None:
        mask = self._tracking_mask()
        if mask is None:
            self._update_tracking_status()
            return
        mask.reset_tracking_cache(clear_corrections=True)
        self._node.update()
        if self._on_commit:
            try:
                self._on_commit()
            except Exception:
                pass
        self._update_tracking_status()

    def _add_tracking_correction(self) -> None:
        tracked = self._tracking_mask()
        mask = self._current_mask_for_commit()
        if tracked is None or mask is None:
            self._update_tracking_status()
            return
        if tracked.add_correction_from_mask(mask, self._frame_idx):
            self._node.update()
            if self._on_commit:
                try:
                    self._on_commit()
                except Exception:
                    pass
        self._update_tracking_status()

    # ---- commit ----

    def vfx_repair_payload(self) -> dict:
        """Return a Fusion-style roto/clean-plate repair payload for this mask."""
        points = [
            {"x": float(x), "y": float(y), "feather": self._softness_sld.value() / 1000.0}
            for x, y in self._canvas.current_polygon_points()
        ]
        if len(points) < 3:
            mask = self._current_mask_for_commit()
            if mask is not None:
                ys, xs = np.where(mask > 0)
                if len(xs) and len(ys):
                    x0 = float(xs.min()) / max(1, mask.shape[1])
                    x1 = float(xs.max()) / max(1, mask.shape[1])
                    y0 = float(ys.min()) / max(1, mask.shape[0])
                    y1 = float(ys.max()) / max(1, mask.shape[0])
                    points = [
                        {"x": x0, "y": y0, "feather": self._softness_sld.value() / 1000.0},
                        {"x": x1, "y": y0, "feather": self._softness_sld.value() / 1000.0},
                        {"x": x1, "y": y1, "feather": self._softness_sld.value() / 1000.0},
                        {"x": x0, "y": y1, "feather": self._softness_sld.value() / 1000.0},
                    ]
        if len(points) < 3:
            return {}
        from app.post_pipeline_workflow import build_vfx_repair_plan

        return build_vfx_repair_plan(points, source_frame_ms=int(self._frame_idx)).to_dict()

    def vfx_repair_summary_text(self) -> str:
        """Human-readable clean-plate / planar-tracker state for this mask."""
        payload = self.vfx_repair_payload()
        if not payload:
            return "VFX repair: draw a polygon or mask to enable clean plate + planar tracking."
        roto = payload.get("roto", {}) if isinstance(payload, dict) else {}
        clean = payload.get("clean_plate", {}) if isinstance(payload, dict) else {}
        tracker = payload.get("planar_tracker", {}) if isinstance(payload, dict) else {}
        points = len(roto.get("points", []) or []) if isinstance(roto, dict) else 0
        method = str(clean.get("method", "clean_plate") if isinstance(clean, dict) else "clean_plate")
        feather = float(clean.get("feather", 0.0) if isinstance(clean, dict) else 0.0)
        tracker_state = "on" if isinstance(tracker, dict) and tracker.get("enabled") else "off"
        return (
            f"VFX repair: {points} roto points | {method} | "
            f"feather {feather:.2f} | planar tracker {tracker_state}"
        )

    def vfx_node_graph_payload(self) -> dict:
        """Return the mini Fusion-style node graph for this repair mask."""
        payload = self.vfx_repair_payload()
        if not payload:
            return {}
        from app.post_pipeline_workflow import build_mini_vfx_node_graph

        return build_mini_vfx_node_graph(
            payload,
            include_keyer=False,
            include_title_merge=False,
        ).to_dict()

    def vfx_node_graph_summary_text(self) -> str:
        graph = self.vfx_node_graph_payload()
        nodes = graph.get("nodes", []) if isinstance(graph, dict) else []
        if not nodes:
            return "VFX node graph: draw a mask to enable graph payload."
        kinds = [str(node.get("kind", "")) for node in nodes if isinstance(node, dict)]
        warnings = graph.get("validation_warnings", []) if isinstance(graph, dict) else []
        state = "ready" if not warnings else f"{len(warnings)} warning(s)"
        return f"VFX node graph: {len(nodes)} nodes | {', '.join(kinds[:5])} | {state}"

    def vfx_status_text(self) -> str:
        return f"{self.vfx_repair_summary_text()}\n{self.vfx_node_graph_summary_text()}"

    def show_vfx_node_graph(self) -> None:
        graph = self.vfx_node_graph_payload()
        dlg = QDialog(self)
        dlg.setWindowTitle("VFX Node Graph")
        dlg.resize(620, 420)
        dlg.setStyleSheet(studio_chrome_qss(
            "QDialog { background:#101112; color:#D7DCE4; }"
            "QLabel { color:#D7DCE4; }"
            "QPlainTextEdit { background:#0D0F12; color:#B9C1CE; border:1px solid #30363D; border-radius:8px; padding:8px; }"
            "QDialogButtonBox QPushButton { background:#20252B; color:#F0F3F7; border:1px solid #3E4651; border-radius:8px; padding:6px 16px; font-weight:700; }"
            "QDialogButtonBox QPushButton:hover { background:#303740; border-color:#697585; }"
        ))
        root = QVBoxLayout(dlg)
        title = QLabel(self.vfx_node_graph_summary_text())
        title.setWordWrap(True)
        title.setStyleSheet("font-weight:800;color:#D7DCE4;")
        root.addWidget(title)
        detail = QPlainTextEdit()
        detail.setReadOnly(True)
        detail.setPlainText(json.dumps(graph or {"nodes": []}, indent=2, ensure_ascii=False))
        root.addWidget(detail, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

    def _accept(self) -> None:
        mask = self._current_mask_for_commit()
        if mask is not None:
            from app.node_mask import BitmapMask, PowerWindow
            if self._canvas._tool == "polygon":
                if self._track_chk.isChecked():
                    bm = BitmapMask(
                        softness_norm=self._softness_sld.value() / 1000.0,
                        invert=self._invert_chk.isChecked(),
                        track_object=True,
                        init_frame=self._frame_idx,
                    )
                    bm.set_from_array(mask)
                    self._node.masks = [bm]
                else:
                    pm = PowerWindow(
                        points=self._canvas.current_polygon_points(),
                        softness_norm=self._softness_sld.value() / 1000.0,
                        invert=self._invert_chk.isChecked(),
                    )
                    self._node.masks = [pm]
            else:
                bm = BitmapMask(
                    softness_norm=self._softness_sld.value() / 1000.0,
                    invert=self._invert_chk.isChecked(),
                    track_object=self._track_chk.isChecked(),
                    init_frame=self._frame_idx,
                )
                bm.set_from_array(mask)
                self._node.masks = [bm]
            try:
                payload = self.vfx_repair_payload()
                if payload:
                    setattr(self._node, "vfx_repair_plan", payload)
                    graph = self.vfx_node_graph_payload()
                    if graph:
                        setattr(self._node, "vfx_node_graph", graph)
            except Exception:
                pass
            self._node.update()
            if self._on_commit:
                try:
                    self._on_commit()
                except Exception:
                    pass
        self.accept()

    # ---- convenience ----

    @classmethod
    def open_for_node(cls, rgb_frame, node, on_commit=None, parent=None,
                      frame_idx: int = 0):
        dlg = cls(rgb_frame, node, on_commit=on_commit,
                  frame_idx=frame_idx, parent=parent)
        existing = node.masks[0] if node.masks else None
        if existing is not None:
            from app.node_mask import BitmapMask, PowerWindow
            if isinstance(existing, PowerWindow):
                dlg._set_tool("polygon")
                dlg._canvas.set_polygon_points(existing.points)
                dlg._softness_sld.setValue(int(existing.softness_norm * 1000))
                dlg._invert_chk.setChecked(existing.invert)
            elif isinstance(existing, BitmapMask):
                dlg._softness_sld.setValue(int(existing.softness_norm * 1000))
                dlg._invert_chk.setChecked(existing.invert)
                dlg._track_chk.setChecked(bool(existing.track_object))
                dlg._update_tracking_status()
        return dlg
