"""pyqtgraph-based scopes panel.

Replaces the QLabel + rasterised pixmap path with pyqtgraph
``PlotWidget``s. The histogram becomes a real R / G / B line plot
(prettier and faster); parade / waveform / vectorscope keep using
the existing ``color_scopes`` raster computations but display them
through pyqtgraph's ``ImageItem`` so we get HiDPI scaling, value
read-outs on hover, and consistent axes.

Public API:
    ``ScopesPanelPG(player, parent=None)`` — drop-in replacement for
    the old ``ScopesPanel``. Subscribes to ``player.frame_ready`` and
    re-computes the active scope when a fresh frame arrives.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.color_scopes import (
    compute_parade,
    compute_vectorscope,
    compute_waveform,
)
from app.i18n import tr


# Single-source colour palette so all four scopes match the editor's
# brand chrome without bringing in the styles module's import here.
_BG = "#0a0a0e"
_FG = "#aaaaaa"
_GRID = "#2a2a2a"
_R = "#e54646"
_G = "#5dca5d"
_B = "#3686d8"

pg.setConfigOptions(antialias=True, background=_BG, foreground=_FG)


def _qimg_to_rgb(qimg: QImage) -> np.ndarray:
    """Cheap QImage → contiguous uint8 (H, W, 3) RGB ndarray. Used by
    the panel's frame_ready slot to feed scope inputs."""
    img = qimg.convertToFormat(QImage.Format.Format_RGB888)
    w, h = img.width(), img.height()
    ptr = img.constBits()
    arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 3)
    return arr.reshape((h, w, 3)).copy()


# ---------------------------------------------------------------------------
#  Individual scope widgets
# ---------------------------------------------------------------------------


class _HistogramScope(QWidget):
    """R / G / B histogram as three line plots over the 0..255 range.
    Bin count is fixed at 256 so each pixel lands in its own bin —
    cheaper than re-binning and visually cleaner."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setBackground(_BG)
        self._plot.setMenuEnabled(False)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideButtons()
        self._plot.showGrid(x=False, y=True, alpha=0.15)
        self._plot.setXRange(0, 255, padding=0)
        self._plot.setLabel("bottom", "value", color=_FG)
        self._plot.getAxis("bottom").setStyle(tickLength=4)
        self._plot.getAxis("left").setStyle(tickLength=4)

        self._curve_r = self._plot.plot(pen=pg.mkPen(_R, width=1.4))
        self._curve_g = self._plot.plot(pen=pg.mkPen(_G, width=1.4))
        self._curve_b = self._plot.plot(pen=pg.mkPen(_B, width=1.4))
        v.addWidget(self._plot)

    def update_frame(self, rgb: np.ndarray) -> None:
        x = np.arange(256)
        # ``np.bincount`` is ~3× faster than ``np.histogram`` for the
        # uint8-into-256-bins case and produces the same result.
        h_r = np.bincount(rgb[..., 0].ravel(), minlength=256)
        h_g = np.bincount(rgb[..., 1].ravel(), minlength=256)
        h_b = np.bincount(rgb[..., 2].ravel(), minlength=256)
        self._curve_r.setData(x, h_r)
        self._curve_g.setData(x, h_g)
        self._curve_b.setData(x, h_b)


class _RasterScope(QWidget):
    """Display a rasterised scope image (parade / waveform /
    vectorscope) via pyqtgraph's ``ImageItem``. The actual computation
    stays in ``color_scopes`` since those produce shaped images that
    don't fit a simple line-plot model."""

    def __init__(
        self,
        kind: str,
        parent: Optional[QWidget] = None,
        out_w: int = 360,
        out_h: int = 220,
    ) -> None:
        super().__init__(parent)
        self._kind = kind
        self._out_w = int(out_w)
        self._out_h = int(out_h)
        self.setMinimumHeight(180)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setBackground(_BG)
        self._plot.setMenuEnabled(False)
        self._plot.setMouseEnabled(x=False, y=False)
        self._plot.hideButtons()
        self._plot.hideAxis("left")
        self._plot.hideAxis("bottom")
        # Lock the view so the image fills the plot regardless of
        # widget resizing.
        self._plot.getViewBox().setAspectLocked(False)
        self._plot.getViewBox().setRange(
            xRange=(0, self._out_w), yRange=(0, self._out_h),
            padding=0, disableAutoRange=True,
        )

        self._image_item = pg.ImageItem(axisOrder="row-major")
        self._plot.addItem(self._image_item)
        v.addWidget(self._plot)

    def update_frame(self, rgb: np.ndarray) -> None:
        if self._kind == "parade":
            out = compute_parade(rgb, self._out_w, self._out_h)
        elif self._kind == "waveform":
            out = compute_waveform(rgb, self._out_w, self._out_h)
        elif self._kind == "vectorscope":
            out = compute_vectorscope(rgb, self._out_w, self._out_h)
        else:
            return
        # color_scopes returns (H, W, 3) with origin top-left. Flip
        # Y so pyqtgraph (origin bottom-left in plot coords) shows it
        # right-side-up.
        flipped = np.ascontiguousarray(out[::-1])
        self._image_item.setImage(flipped, autoLevels=False, levels=(0, 255))


# ---------------------------------------------------------------------------
#  Panel
# ---------------------------------------------------------------------------


class ScopesPanelPG(QWidget):
    """Drop-in replacement for the legacy QLabel-based ScopesPanel.
    Same constructor signature (``ScopesPanelPG(player)``) and same
    visual footprint — picker dropdown on top, scope below."""

    SCOPE_W = 360
    SCOPE_H = 220

    def __init__(self, player, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._player = player
        self._latest_rgb: np.ndarray | None = None
        self.setFixedHeight(self.SCOPE_H + 38)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        title = QLabel(tr("veditor.scopes.title"))
        title.setStyleSheet(
            "color: #8a8a8a; font-size: 11px; font-weight: 600;"
        )
        head.addWidget(title)
        head.addStretch(1)
        self._kind_combo = QComboBox()
        for kid, key in (
            ("histogram",   "veditor.scopes.histogram"),
            ("parade",      "veditor.scopes.parade"),
            ("waveform",    "veditor.scopes.waveform"),
            ("vectorscope", "veditor.scopes.vectorscope"),
        ):
            self._kind_combo.addItem(tr(key), userData=kid)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        head.addWidget(self._kind_combo)
        outer.addLayout(head)

        # Stack of scope widgets — switched by the dropdown. Only the
        # visible one re-renders on each frame; the others stay idle.
        self._stack = QStackedWidget()
        self._stack.setFixedSize(self.SCOPE_W, self.SCOPE_H)
        self._scopes: dict[str, QWidget] = {
            "histogram":   _HistogramScope(),
            "parade":      _RasterScope("parade", out_w=self.SCOPE_W, out_h=self.SCOPE_H),
            "waveform":    _RasterScope("waveform", out_w=self.SCOPE_W, out_h=self.SCOPE_H),
            "vectorscope": _RasterScope("vectorscope", out_w=self.SCOPE_W, out_h=self.SCOPE_H),
        }
        self._index_for: dict[str, int] = {}
        for kid in ("histogram", "parade", "waveform", "vectorscope"):
            self._index_for[kid] = self._stack.addWidget(self._scopes[kid])
        outer.addWidget(self._stack, alignment=Qt.AlignmentFlag.AlignCenter)

        self._player.frame_ready.connect(self._on_frame_ready)

    # ---- public ----

    def current_kind(self) -> str:
        kid = self._kind_combo.currentData()
        return str(kid) if kid else "histogram"

    # ---- slots ----

    def _on_kind_changed(self) -> None:
        kid = self.current_kind()
        idx = self._index_for.get(kid, 0)
        self._stack.setCurrentIndex(idx)
        if self._latest_rgb is not None:
            self._scopes[kid].update_frame(self._latest_rgb)

    def _on_frame_ready(self, qimg) -> None:
        try:
            self._latest_rgb = _qimg_to_rgb(qimg)
            self._scopes[self.current_kind()].update_frame(self._latest_rgb)
        except Exception:
            # Bad frame data — skip silently rather than tearing the
            # whole editor's signal chain.
            pass
