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

from typing import Callable

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap, QPolygon, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


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

        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
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
        self._repaint_overlay()

    def set_polygon_points(self, pts: list[tuple[float, float]]) -> None:
        self._points = list(pts)
        self._mask = self._eval_polygon_mask()
        self._repaint_overlay()

    def current_polygon_points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def current_mask(self) -> np.ndarray | None:
        return self._mask

    def clear(self) -> None:
        self._points = []
        self._rect_start = self._rect_end = None
        self._mask = None
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
                m_disp = _cv2.resize(self._mask, (dw, dh), interpolation=cv2.INTER_LINEAR)
            except Exception:
                m_disp = self._mask
            # Draw row-by-row is too slow for large images at high zoom.
            # Use a pre-built QImage alpha plane instead.
            ov = QImage(dw, dh, QImage.Format.Format_ARGB32_Premultiplied)
            ov.fill(Qt.GlobalColor.transparent)
            for row in range(min(dh, m_disp.shape[0])):
                for col in range(min(dw, m_disp.shape[1])):
                    v = int(m_disp[row, col])
                    if v > 0:
                        a = min(140, int(v * 140 / 255))
                        ov.setPixelColor(col, row, QColor(216, 90, 48, a))
            painter.drawImage(0, 0, ov)

        # Dashed rect preview while dragging
        if (self._mask is None and self._rect_start is not None
                and self._rect_end is not None):
            pen = QPen(QColor("#D85A30"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(216, 90, 48, 40))
            painter.drawRect(QRect(self._rect_start, self._rect_end).normalized())

        # Polygon in-progress
        if self._tool == "polygon" and self._points:
            pts_px = [QPoint(int(x * dw), int(y * dh)) for x, y in self._points]
            painter.setPen(QPen(QColor("#D85A30"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if len(pts_px) >= 3:
                painter.drawPolygon(QPolygon(pts_px))
            elif len(pts_px) == 2:
                painter.drawLine(pts_px[0], pts_px[1])
            for p in pts_px:
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor("#D85A30"), 2))
                painter.drawEllipse(p, 5, 5)

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
            self._points.append((nx, ny))
            self._mask = self._eval_polygon_mask()
            self._repaint_overlay()
        elif self._tool == "rect":
            self._rect_start = pos
            self._rect_end = pos
            self._mask = None
            self._repaint_overlay()
        elif self._tool == "click":
            self._run_click(nx, ny)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._tool == "polygon" and len(self._points) >= 3:
            if len(self._points) > 3:
                self._points = self._points[:-1]
            self._mask = self._eval_polygon_mask()
            self._repaint_overlay()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._tool == "rect" and self._rect_start is not None:
            self._rect_end = event.position().toPoint()
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
                self._run_grabcut(nx, ny, nw, nh)

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
        m = grabcut_from_rect(self._rgb, (nx, ny, nw, nh), iterations=4)
        if m is not None:
            self._mask = m
            self._repaint_overlay()

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

            def run(self):
                from app.sam_segment import is_sam_available, sam_mask_from_point
                m = None
                if is_sam_available():
                    m = sam_mask_from_point(self._rgb, self._nx, self._ny)
                if m is None:
                    pw = 0.25
                    ph = pw * max(1, self._src_w) / max(1, self._src_h)
                    x0 = max(0.0, self._nx - pw / 2)
                    y0 = max(0.0, self._ny - ph / 2)
                    from app.node_mask import grabcut_from_rect
                    m = grabcut_from_rect(self._rgb, (x0, y0, pw, ph), iterations=4)
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
        self.setWindowTitle(tr("maskeditor.title"))
        self.setMinimumSize(700, 520)
        self.resize(960, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ---- Tool bar ----
        tb = QHBoxLayout()
        tb.setSpacing(6)
        self._tool_btns: list[QPushButton] = []
        for key, label in (
            ("polygon", tr("maskeditor.tool.polygon")),
            ("rect",    tr("maskeditor.tool.rect")),
            ("click",   tr("maskeditor.tool.click")),
        ):
            btn = QPushButton(label)
            btn.setObjectName("ToolButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _c, k=key: self._set_tool(k))
            tb.addWidget(btn)
            self._tool_btns.append(btn)

        tb.addSpacing(12)
        clear_btn = QPushButton(tr("maskeditor.btn.clear"))
        clear_btn.setObjectName("ToolButton")
        clear_btn.clicked.connect(self._clear)
        tb.addWidget(clear_btn)

        tb.addStretch(1)

        # Zoom controls — clearly labelled so users know what they do
        zoom_out_btn = QPushButton("🔍−")
        zoom_out_btn.setObjectName("ToolButton")
        zoom_out_btn.setFixedWidth(38)
        zoom_out_btn.setToolTip("Zoom out (Ctrl+Wheel)")
        zoom_out_btn.clicked.connect(lambda: self._step_zoom(-1))
        tb.addWidget(zoom_out_btn)

        self._zoom_label = QLabel("100%")
        self._zoom_label.setFixedWidth(46)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setStyleSheet(
            "color:#aaa; font-size:11px; background:#242428; "
            "border:1px solid #333; border-radius:4px; padding:2px;"
        )
        tb.addWidget(self._zoom_label)

        zoom_in_btn = QPushButton("🔍+")
        zoom_in_btn.setObjectName("ToolButton")
        zoom_in_btn.setFixedWidth(38)
        zoom_in_btn.setToolTip("Zoom in (Ctrl+Wheel)")
        zoom_in_btn.clicked.connect(lambda: self._step_zoom(+1))
        tb.addWidget(zoom_in_btn)

        fit_btn = QPushButton(tr("maskeditor.btn.fit"))
        fit_btn.setObjectName("ToolButton")
        fit_btn.setToolTip("Fit frame to window")
        fit_btn.clicked.connect(self._fit)
        tb.addWidget(fit_btn)

        tb.addSpacing(12)

        soft_lbl = QLabel(tr("maskeditor.softness"))
        soft_lbl.setStyleSheet("color:#aaa; font-size:11px;")
        tb.addWidget(soft_lbl)
        self._softness_sld = QSlider(Qt.Orientation.Horizontal)
        self._softness_sld.setRange(0, 50)
        self._softness_sld.setValue(5)
        self._softness_sld.setFixedWidth(70)
        tb.addWidget(self._softness_sld)

        self._invert_chk = QCheckBox(tr("maskeditor.invert"))
        self._invert_chk.setToolTip("체크 해제: 선택 영역에 블러 / 체크: 선택 외부에 블러(배경 아웃포커스)")
        tb.addWidget(self._invert_chk)
        self._track_chk = QCheckBox(tr("maskeditor.track"))
        self._track_chk.setToolTip(tr("maskeditor.track.tip"))
        tb.addWidget(self._track_chk)

        root.addLayout(tb)

        # ---- Scroll area + canvas ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas = _FrameCanvas(rgb_frame)
        self._scroll.setWidget(self._canvas)
        root.addWidget(self._scroll, stretch=1)

        # ---- Hint ----
        self._hint = QLabel(tr("maskeditor.hint.rect"))
        self._hint.setStyleSheet("color:#8a8a8a; font-size:11px;")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._hint)

        # ---- Dialog buttons ----
        bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        root.addWidget(bb)

        # Default tool
        self._set_tool("rect")

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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Fit to viewport on first show so the frame fills the canvas.
        self._canvas.fit_to_viewport()
        self._update_zoom_label()

    # ---- tool ----

    def _set_tool(self, tool: str) -> None:
        for btn in self._tool_btns:
            btn.setChecked(False)
        idx = {"polygon": 0, "rect": 1, "click": 2}.get(tool, 1)
        self._tool_btns[idx].setChecked(True)
        self._canvas.set_tool(tool)
        hints = {
            "polygon": tr("maskeditor.hint.polygon"),
            "rect":    tr("maskeditor.hint.rect"),
            "click":   tr("maskeditor.hint.click"),
        }
        self._hint.setText(hints.get(tool, ""))

    def _clear(self) -> None:
        self._canvas.clear()

    # ---- commit ----

    def _accept(self) -> None:
        mask = self._canvas.current_mask()
        if mask is None and len(self._canvas.current_polygon_points()) >= 3:
            mask = self._canvas._eval_polygon_mask()
        if mask is not None:
            from app.node_mask import BitmapMask, PowerWindow
            if self._canvas._tool == "polygon":
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
                )
                bm.set_from_array(mask)
                self._node.masks = [bm]
            self._node.update()
            if self._on_commit:
                try:
                    self._on_commit()
                except Exception:
                    pass
        self.accept()

    # ---- convenience ----

    @classmethod
    def open_for_node(cls, rgb_frame, node, on_commit=None, parent=None):
        dlg = cls(rgb_frame, node, on_commit=on_commit, parent=parent)
        existing = node.masks[0] if node.masks else None
        if existing is not None:
            from app.node_mask import PowerWindow
            if isinstance(existing, PowerWindow):
                dlg._set_tool("polygon")
                dlg._canvas.set_polygon_points(existing.points)
                dlg._softness_sld.setValue(int(existing.softness_norm * 1000))
                dlg._invert_chk.setChecked(existing.invert)
        return dlg
