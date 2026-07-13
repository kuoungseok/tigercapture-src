from __future__ import annotations

import json
import math
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.video_editor_preset_browser_style import (
    PRESET_TILE,
    PRESET_TILE_GAP,
    make_pack_icon,
    pack_palette_button_style,
    preset_category_combo_qss,
    preset_category_filter_button_qss,
    preset_menu_qss,
    preset_pack_combo_qss,
    preset_scroll_grid_qss,
    preset_search_qss,
)


class _block_signals:
    def __init__(self, *widgets) -> None:
        self._widgets = widgets
        self._states: list[tuple[object, bool]] = []

    def __enter__(self):
        self._states = []
        for widget in self._widgets:
            if widget is None:
                continue
            try:
                self._states.append((widget, bool(widget.blockSignals(True))))
            except Exception:
                pass
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        for widget, was_blocked in reversed(self._states):
            try:
                widget.blockSignals(was_blocked)
            except Exception:
                pass
        self._states = []


def _preset_state_path() -> Path:
    try:
        from app.paths import default_save_dir

        root = default_save_dir()
    except Exception:
        root = Path.home() / ".tigercapture"
    root.mkdir(parents=True, exist_ok=True)
    return root / "preset_browser_state.json"


def _load_preset_browser_state() -> dict:
    try:
        return json.loads(_preset_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {"favorites": [], "recent": []}


def _save_preset_browser_state(state: dict) -> None:
    try:
        path = _preset_state_path()
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class PresetScrollGrid(QWidget):
    """Scrollable, width-aware preset grid for left-dock collapsible sections."""

    def __init__(
        self,
        cards: list[QWidget],
        *,
        max_height: int = 218,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PresetScrollGridHost")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#PresetScrollGridHost{background:#101112;}")
        self._cards = list(cards)
        self._columns = 0
        self._last_rows = 0
        self._max_height = int(max_height)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 2)
        root.setSpacing(0)

        self._scroll = QScrollArea(self)
        self._scroll.setObjectName("PresetScrollGrid")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setMaximumHeight(self._max_height)
        self._scroll.setMinimumHeight(64 if self._cards else 40)
        self._scroll.setStyleSheet(preset_scroll_grid_qss())

        self._content = QWidget(self._scroll)
        self._content.setObjectName("PresetScrollGridContent")
        self._content.setStyleSheet("QWidget#PresetScrollGridContent{background:#101112;}")
        self._grid = QGridLayout(self._content)
        self._grid.setContentsMargins(8, 6, 8, 6)
        self._grid.setHorizontalSpacing(PRESET_TILE_GAP)
        self._grid.setVerticalSpacing(PRESET_TILE_GAP)
        self._scroll.setWidget(self._content)
        root.addWidget(self._scroll, 0, Qt.AlignmentFlag.AlignTop)
        QTimer.singleShot(0, self._relayout)

    def set_cards(self, cards: list[QWidget]) -> None:
        self._cards = list(cards)
        self._columns = 0
        self._relayout()

    def vertical_scroll_bar(self):
        return self._scroll.verticalScrollBar()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._relayout)

    def _relayout(self) -> None:
        width = max(1, self._scroll.viewport().width() - 28)
        columns = max(2, min(4, (width + PRESET_TILE_GAP) // (PRESET_TILE + PRESET_TILE_GAP)))
        if columns == self._columns and self._grid.count() == len(self._cards):
            return
        self._columns = int(columns)
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget() is not None:
                item.widget().setParent(None)
        rows = math.ceil(len(self._cards) / max(1, self._columns))
        for row in range(max(self._last_rows + 1, rows + 1)):
            self._grid.setRowStretch(row, 0)
        for idx, card in enumerate(self._cards):
            row, col = divmod(idx, self._columns)
            self._grid.addWidget(card, row, col, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._grid.setRowStretch(rows, 1)
        self._last_rows = rows
        height = 12 + rows * PRESET_TILE + max(0, rows - 1) * PRESET_TILE_GAP
        self._content.setMinimumHeight(height)
        self._scroll.setMinimumHeight(min(self._max_height, max(64, height + 2)))


class PresetInspectorPanel(QFrame):
    """Compact detail panel for the currently hovered/selected preset tile."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        details_builder=None,
    ) -> None:
        super().__init__(parent)
        self._details_builder = details_builder
        self._swatch: PresetPreviewSwatch | None = None
        self.setObjectName("PresetInspectorPanel")
        self.setStyleSheet(
            "QFrame#PresetInspectorPanel{background:#111316;border:1px solid rgba(220,225,238,26);border-radius:8px;}"
            "QLabel{background:transparent;color:#9CA5B4;font-size:9px;}"
            "QLabel#PresetInspectorTitle{color:#F0F3F7;font-size:10px;font-weight:650;}"
            "QLabel#PresetInspectorBadges{color:#B8C0CA;font-size:8px;font-weight:600;}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)
        self._swatch_slot = QWidget(self)
        self._swatch_slot.setObjectName("PresetInspectorSwatchSlot")
        self._swatch_slot.setMinimumHeight(56)
        self._swatch_lay = QVBoxLayout(self._swatch_slot)
        self._swatch_lay.setContentsMargins(0, 0, 0, 0)
        self._swatch_lay.setSpacing(0)
        self._title = QLabel("Hover a preset", self)
        self._title.setObjectName("PresetInspectorTitle")
        self._title.setWordWrap(True)
        self._badges = QLabel("Clip  Fast  A/B", self)
        self._badges.setObjectName("PresetInspectorBadges")
        self._badges.setWordWrap(True)
        self._details = QLabel("Rollover previews the result on the current frame.", self)
        self._details.setWordWrap(True)
        self._target_strip = _PresetTargetStrip(self)
        root.addWidget(self._swatch_slot)
        root.addWidget(self._title)
        root.addWidget(self._badges)
        root.addWidget(self._target_strip)
        root.addWidget(self._details)
        target_height = max(168, int(root.sizeHint().height() or 0))
        self.setMinimumHeight(target_height)
        self.setMaximumHeight(target_height + 10)

    def _replace_swatch(self, card) -> None:
        if self._swatch is not None:
            self._swatch.setParent(None)
            self._swatch.deleteLater()
            self._swatch = None
        colors = tuple(getattr(card, "_colors", ("#40444B", "#30343B", "#202328")) or ())
        if len(colors) != 3:
            colors = ("#40444B", "#30343B", "#202328")
        sample_pixmap = None
        sample_fn = getattr(card, "_preview_sample_pixmap", None)
        if callable(sample_fn):
            try:
                sample_pixmap = sample_fn()
            except Exception:
                sample_pixmap = None
        self._swatch = PresetPreviewSwatch(
            colors,  # type: ignore[arg-type]
            kind=str(getattr(card, "_preview_kind", "") or ""),
            label=str(getattr(card, "_label", "") or ""),
            payload=dict(getattr(card, "_preview_payload", {}) or {}),
            tags=tuple(getattr(card, "_tags", ()) or ()),
            category=str(getattr(card, "_category", "") or ""),
            sample_pixmap=sample_pixmap,
            intensity=float(getattr(card, "_preview_intensity", 1.0) or 1.0),
            payload_with_intensity=getattr(card, "_payload_with_intensity_fn", None),
            size=QSize(166, 56),
            parent=self._swatch_slot,
        )
        self._swatch_lay.addWidget(self._swatch)

    def inspect(self, card) -> None:
        self._replace_swatch(card)
        label = str(getattr(card, "_label", "") or "Preset")
        pack = str(getattr(card, "_pack", "") or "")
        category = str(getattr(card, "_category", "") or "")
        badges = list(getattr(card, "_preview_badges", []) or [])
        quality = str(getattr(card, "_quality_badge", "") or "")
        quality_detail = str(getattr(card, "_quality_detail", "") or "")
        if quality:
            badges.append(quality)
        tags = tuple(getattr(card, "_tags", ()) or ())
        details: list[str] = []
        if callable(self._details_builder):
            details = list(self._details_builder(
                str(getattr(card, "_preview_kind", "") or ""),
                dict(getattr(card, "_preview_payload", {}) or {}),
                tags,
            ) or [])
        if quality_detail:
            details.insert(0, quality_detail)
        if not details and tags:
            details.append("Tags: " + ", ".join(tags[:5]))
        self._title.setText(label)
        self._badges.setText("  ".join(badges) if badges else "Preset")
        self._target_strip.set_preset(
            str(getattr(card, "_preview_kind", "") or ""),
            dict(getattr(card, "_preview_payload", {}) or {}),
            tags,
        )
        self._details.setText(
            " / ".join(part for part in (pack, category) if part)
            + ("\n" if details else "")
            + "\n".join(details[:3])
        )


class _PresetTargetStrip(QWidget):
    """Tiny visual map of where a preset wants to be dropped."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PresetTargetStrip")
        self.setFixedHeight(22)
        self._kind = ""
        self._payload: dict = {}
        self._tags: tuple[str, ...] = ()

    def set_preset(self, kind: str, payload: dict | None, tags: tuple[str, ...]) -> None:
        self._kind = str(kind or "").casefold()
        self._payload = dict(payload or {})
        self._tags = tuple(str(tag).casefold() for tag in (tags or ()))
        self.update()

    def _target(self) -> str:
        text = " ".join((self._kind, " ".join(self._tags), " ".join(str(k) for k in self._payload.keys())))
        if "transition" in text or "transition_out" in text:
            return "cut"
        if "title" in text or "caption" in text or "text" in text:
            return "text"
        if "audio" in text or "denoise" in text or "dialogue" in text:
            return "audio"
        if "actor" in text or "live2d" in text or "spine" in text:
            return "actor"
        if "node" in text or "graph" in text or "composite" in text:
            return "node"
        return "clip"

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(0, 1, -1, -1)
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.setBrush(QColor(12, 14, 18, 165))
        painter.drawRoundedRect(r, 7, 7)
        target = self._target()
        slots = ("clip", "cut", "audio", "text", "actor", "node")
        gap = 3
        usable = r.adjusted(4, 3, -4, -3)
        w = max(16, (usable.width() - gap * (len(slots) - 1)) // len(slots))
        for idx, slot in enumerate(slots):
            x = usable.left() + idx * (w + gap)
            sr = QRect(x, usable.top(), w, usable.height())
            active = slot == target
            painter.setPen(QPen(QColor(235, 239, 248, 104 if active else 30), 1))
            painter.setBrush(QColor(58, 64, 72, 230) if active else QColor(28, 31, 36, 180))
            painter.drawRoundedRect(sr, 5, 5)
            painter.setPen(QPen(QColor("#F2F4F8") if active else QColor("#A4ACB8"), 1.2))
            cx, cy = sr.center().x(), sr.center().y()
            if slot == "clip":
                painter.drawRoundedRect(QRect(cx - 5, cy - 4, 10, 8), 2, 2)
            elif slot == "cut":
                painter.drawLine(QPoint(cx - 5, cy - 5), QPoint(cx + 5, cy + 5))
                painter.drawLine(QPoint(cx + 5, cy - 5), QPoint(cx - 5, cy + 5))
            elif slot == "audio":
                path = QPainterPath()
                path.moveTo(cx - 6, cy)
                path.cubicTo(cx - 2, cy - 6, cx + 2, cy + 6, cx + 6, cy)
                painter.drawPath(path)
            elif slot == "text":
                font = painter.font()
                font.setPixelSize(9)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(sr, Qt.AlignmentFlag.AlignCenter, "T")
            elif slot == "actor":
                painter.drawEllipse(QPoint(cx, cy - 2), 3, 3)
                painter.drawRoundedRect(QRect(cx - 5, cy + 2, 10, 5), 3, 3)
            else:
                painter.drawEllipse(QPoint(cx - 4, cy - 3), 2, 2)
                painter.drawEllipse(QPoint(cx + 4, cy - 3), 2, 2)
                painter.drawEllipse(QPoint(cx, cy + 4), 2, 2)
                painter.drawLine(QPoint(cx - 3, cy - 2), QPoint(cx, cy + 3))
                painter.drawLine(QPoint(cx + 3, cy - 2), QPoint(cx, cy + 3))
        painter.end()


class PresetPreviewSwatch(QWidget):
    """Contextual animated preview for a preset tile."""

    def __init__(
        self,
        colors: tuple[str, str, str],
        *,
        kind: str = "",
        label: str = "",
        payload: dict | None = None,
        tags: tuple[str, ...] = (),
        category: str = "",
        sample_pixmap: QPixmap | None = None,
        intensity: float = 1.0,
        payload_with_intensity=None,
        size: QSize | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._colors = colors
        self._kind = str(kind or category or "").casefold()
        self._label = str(label or "")
        self._payload = dict(payload or {})
        self._tags = tuple(str(tag).casefold() for tag in (tags or ()))
        self._sample_pixmap = sample_pixmap if isinstance(sample_pixmap, QPixmap) and not sample_pixmap.isNull() else None
        self._intensity = max(0.0, min(1.25, float(intensity or 1.0)))
        self._payload_with_intensity = payload_with_intensity
        self._phase = 0.0
        self._window_move_suspended = False
        preview_size = size if isinstance(size, QSize) and not size.isEmpty() else QSize(240, 86)
        self.setFixedSize(preview_size)
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.055) % 1.0
        self.update()

    def set_window_move_suspended(self, suspended: bool) -> None:
        suspended = bool(suspended)
        if suspended == self._window_move_suspended:
            return
        self._window_move_suspended = suspended
        if suspended:
            self._timer.stop()
            return
        if self.isVisible() and not self._timer.isActive():
            self._timer.start()

    def set_intensity(self, value: float) -> None:
        self._intensity = max(0.0, min(1.25, float(value or 0.0)))
        self.update()

    def _draw_pixmap_cover(self, painter: QPainter, pixmap: QPixmap, rect: QRect, radius: int = 8) -> None:
        if pixmap.isNull() or rect.width() <= 0 or rect.height() <= 0:
            return
        scaled = pixmap.scaled(
            rect.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        sx = max(0, (scaled.width() - rect.width()) // 2)
        sy = max(0, (scaled.height() - rect.height()) // 2)
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), radius, radius)
        painter.setClipPath(path)
        painter.drawPixmap(rect, scaled, QRect(sx, sy, rect.width(), rect.height()))
        painter.restore()

    def _pixmap_to_rgb(self, pixmap: QPixmap):
        try:
            import numpy as _np

            image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGB888)
            width = image.width()
            height = image.height()
            bytes_per_line = image.bytesPerLine()
            data = bytes(image.constBits())
            arr = _np.frombuffer(data, dtype=_np.uint8)
            arr = arr.reshape((height, bytes_per_line))[:, : width * 3]
            return _np.ascontiguousarray(arr.reshape((height, width, 3)))
        except Exception:
            return None

    def _rgb_to_pixmap(self, rgb) -> QPixmap | None:
        try:
            import numpy as _np

            arr = _np.ascontiguousarray(rgb.astype(_np.uint8, copy=False))
            h, w = arr.shape[:2]
            image = QImage(arr.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
            return QPixmap.fromImage(image)
        except Exception:
            return None

    def _processed_sample_pixmap(self) -> QPixmap | None:
        if self._sample_pixmap is None:
            return None
        rgb = self._pixmap_to_rgb(self._sample_pixmap)
        if rgb is None:
            return None
        if callable(self._payload_with_intensity):
            payload = self._payload_with_intensity(self._payload, self._intensity)
        else:
            payload = dict(self._payload)
        try:
            vf = payload.get("video_filters")
            if isinstance(vf, dict):
                from app.video_filters import VideoFilterParams

                rgb = VideoFilterParams.from_dict(vf).apply_preview(rgb)
        except Exception:
            pass
        try:
            chroma = payload.get("chroma_key")
            if isinstance(chroma, dict) and chroma.get("enabled"):
                import numpy as _np
                from app.chroma_key import ChromaKeyParams

                keyed, alpha = ChromaKeyParams.from_dict(chroma).apply_preview(rgb)
                h, w = keyed.shape[:2]
                checker = _np.zeros_like(keyed)
                yy, xx = _np.indices((h, w))
                cells = ((xx // 10 + yy // 10) % 2).astype(_np.uint8)
                checker[:] = _np.where(cells[:, :, None] == 0, 38, 72)
                checker[:, :, 1] = _np.where(cells == 0, 42, 78)
                checker[:, :, 2] = _np.where(cells == 0, 54, 92)
                a = alpha.astype(_np.float32)[:, :, None] / 255.0
                rgb = _np.clip(
                    keyed.astype(_np.float32) * a + checker.astype(_np.float32) * (1.0 - a),
                    0,
                    255,
                ).astype(_np.uint8)
        except Exception:
            pass
        return self._rgb_to_pixmap(rgb)

    def _draw_frame(self, painter: QPainter, rect: QRect) -> None:
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor("#191D2B"))
        grad.setColorAt(1.0, QColor("#090A10"))
        painter.setPen(QPen(QColor(255, 255, 255, 54), 1))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(rect, 13, 13)
        inner = rect.adjusted(8, 8, -8, -8)
        scene = QLinearGradient(inner.topLeft(), inner.bottomRight())
        scene.setColorAt(0.0, QColor("#252B3C"))
        scene.setColorAt(0.55, QColor("#111421"))
        scene.setColorAt(1.0, QColor("#1A1630"))
        painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
        painter.setBrush(QBrush(scene))
        painter.drawRoundedRect(inner, 9, 9)
        painter.setPen(QPen(QColor(255, 255, 255, 32), 1))
        for x in range(inner.left() + 10, inner.right(), 28):
            painter.drawLine(x, inner.top() + 4, x - 18, inner.bottom() - 4)

    def _draw_effect(self, painter: QPainter, rect: QRect) -> None:
        payload = self._payload
        vf = dict(payload.get("video_filters") or {})
        key = dict(payload.get("chroma_key") or {})
        inner = rect.adjusted(10, 10, -10, -10)
        left = QRect(inner.left(), inner.top(), inner.width() // 2, inner.height())
        right = QRect(left.right(), inner.top(), inner.width() - left.width(), inner.height())
        sample = self._sample_pixmap
        processed = self._processed_sample_pixmap()
        if sample is not None and processed is not None:
            self._draw_pixmap_cover(painter, sample, inner, 8)
            wipe = 0.34 + 0.32 * (0.5 - 0.5 * math.cos(self._phase * math.tau))
            split_x = inner.left() + int(inner.width() * wipe)
            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(inner), 8, 8)
            painter.setClipPath(clip)
            painter.setClipRect(
                QRect(split_x, inner.top(), max(1, inner.right() - split_x + 1), inner.height()),
                Qt.ClipOperation.IntersectClip,
            )
            self._draw_pixmap_cover(painter, processed, inner, 8)
            painter.restore()
            painter.setPen(QPen(QColor(255, 255, 255, 135), 1))
            painter.drawLine(split_x, inner.top() + 4, split_x, inner.bottom() - 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 10, 16, 165))
            painter.drawRoundedRect(QRect(inner.left() + 5, inner.top() + 5, 30, 13), 6, 6)
            painter.drawRoundedRect(QRect(inner.right() - 37, inner.top() + 5, 32, 13), 6, 6)
            font = painter.font()
            font.setPixelSize(8)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRect(inner.left() + 5, inner.top() + 4, 30, 13), Qt.AlignmentFlag.AlignCenter, "A")
            painter.drawText(QRect(inner.right() - 37, inner.top() + 4, 32, 13), Qt.AlignmentFlag.AlignCenter, "B")
            if key.get("enabled"):
                painter.setPen(QPen(QColor("#60E6C5"), 2))
                painter.drawText(inner.adjusted(0, inner.height() - 18, 0, -2), Qt.AlignmentFlag.AlignCenter, "ALPHA")
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#263044"))
        painter.drawRoundedRect(left, 8, 8)
        painter.setBrush(QColor("#35415C"))
        painter.drawEllipse(QPoint(left.center().x() - 14, left.center().y() + 8), 17, 21)
        painter.drawEllipse(QPoint(left.center().x() + 18, left.center().y() - 7), 20, 12)

        if key.get("enabled"):
            painter.setBrush(QColor("#32C66A"))
            painter.drawRoundedRect(right, 8, 8)
            painter.setBrush(QColor(10, 14, 22, 160))
            painter.drawEllipse(QPoint(right.center().x(), right.center().y()), 18, 23)
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawText(right, Qt.AlignmentFlag.AlignCenter, "KEY")
            return

        grad = QLinearGradient(right.topLeft(), right.bottomRight())
        if float(vf.get("denoise", 0) or 0) > 0.2:
            grad.setColorAt(0.0, QColor("#1D2630"))
            grad.setColorAt(1.0, QColor("#2E4250"))
        elif float(vf.get("glitch", 0) or 0) > 0 or float(vf.get("chroma_aberration", 0) or 0) > 0.06:
            grad.setColorAt(0.0, QColor("#FF4F6E"))
            grad.setColorAt(0.5, QColor("#30C8FF"))
            grad.setColorAt(1.0, QColor("#755DFF"))
        elif float(vf.get("vignette", 0) or 0) > 0.15:
            grad.setColorAt(0.0, QColor("#10121B"))
            grad.setColorAt(0.45, QColor("#6177A5"))
            grad.setColorAt(1.0, QColor("#1A1F29"))
        else:
            grad.setColorAt(0.0, QColor("#5CC8FF"))
            grad.setColorAt(1.0, QColor("#FFBD59"))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(right, 8, 8)
        if float(vf.get("glitch", 0) or 0) > 0 or float(vf.get("chroma_aberration", 0) or 0) > 0.06:
            offset = int(self._phase * 20)
            for y in (right.top() + 10, right.center().y(), right.bottom() - 16):
                painter.fillRect(right.left() + 8 + offset % 18, y, 38, 4, QColor(255, 255, 255, 170))
                painter.fillRect(right.left() + 14, y + 5, 54, 3, QColor(20, 255, 220, 150))
        elif float(vf.get("denoise", 0) or 0) > 0.2:
            painter.setBrush(QColor(255, 255, 255, 80))
            for idx in range(16):
                x = right.left() + 8 + (idx * 13) % max(1, right.width() - 16)
                y = right.top() + 8 + (idx * 17) % max(1, right.height() - 16)
                painter.drawEllipse(QPoint(x, y), 1, 1)
            painter.setPen(QPen(QColor("#CFF7FF"), 2))
            painter.drawLine(right.left() + 12, right.center().y(), right.right() - 12, right.center().y())
        else:
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawText(right, Qt.AlignmentFlag.AlignCenter, "FX")
        painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
        painter.drawLine(left.right(), inner.top() + 4, left.right(), inner.bottom() - 4)

    def _draw_transition(self, painter: QPainter, rect: QRect) -> None:
        payload = self._payload
        ttype = str(payload.get("transition_out_type") or payload.get("type") or "").casefold()
        inner = rect.adjusted(12, 16, -12, -16)
        left = QRect(inner.left(), inner.top(), inner.width() // 2 + 8, inner.height())
        right = QRect(inner.center().x() - 8, inner.top(), inner.width() // 2 + 8, inner.height())
        if self._sample_pixmap is not None:
            self._draw_pixmap_cover(painter, self._sample_pixmap, inner, 9)
            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(inner), 9, 9)
            painter.setClipPath(clip)
            if "black" in ttype:
                alpha = 65 + int(120 * (0.5 - 0.5 * math.cos(self._phase * math.tau)))
                painter.fillRect(inner, QColor(0, 0, 0, alpha))
            elif "white" in ttype:
                alpha = 45 + int(130 * (0.5 - 0.5 * math.cos(self._phase * math.tau)))
                painter.fillRect(inner, QColor(255, 255, 255, alpha))
            elif "zoom" in ttype:
                painter.fillRect(inner, QColor(18, 24, 36, 82))
                radius = 13 + int(self._phase * 21)
                painter.setPen(QPen(QColor("#F3F5FB"), 2))
                painter.drawEllipse(inner.center(), radius, radius)
                painter.drawEllipse(inner.center(), max(3, radius // 2), max(3, radius // 2))
            else:
                sweep = inner.left() + int(inner.width() * self._phase)
                b_region = QRect(sweep, inner.top(), max(1, inner.right() - sweep + 1), inner.height())
                painter.fillRect(b_region, QColor(82, 96, 124, 92))
                if "slide" in ttype or "wipe" in ttype:
                    painter.setPen(QPen(QColor("#F3F5FB"), 1))
                    painter.drawLine(sweep, inner.top() + 2, sweep, inner.bottom() - 2)
                else:
                    fade = QLinearGradient(inner.left(), 0, inner.right(), 0)
                    fade.setColorAt(0.0, QColor(255, 255, 255, 0))
                    fade.setColorAt(0.5, QColor(255, 255, 255, 82))
                    fade.setColorAt(1.0, QColor(255, 255, 255, 0))
                    painter.fillRect(inner, QBrush(fade))
            painter.restore()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 10, 16, 168))
            painter.drawRoundedRect(QRect(inner.left() + 5, inner.top() + 5, 24, 13), 6, 6)
            painter.drawRoundedRect(QRect(inner.right() - 29, inner.top() + 5, 24, 13), 6, 6)
            font = painter.font()
            font.setPixelSize(8)
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRect(inner.left() + 5, inner.top() + 4, 24, 13), Qt.AlignmentFlag.AlignCenter, "A")
            painter.drawText(QRect(inner.right() - 29, inner.top() + 4, 24, 13), Qt.AlignmentFlag.AlignCenter, "B")
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#C97815"))
            painter.drawRoundedRect(left, 9, 9)
            painter.setBrush(QColor("#654BFF"))
            painter.drawRoundedRect(right, 9, 9)
        if "white" in ttype:
            painter.setBrush(QColor(255, 255, 255, 185))
            pulse_w = 16 + int(self._phase * 36)
            painter.drawRoundedRect(QRect(inner.center().x() - pulse_w // 2, inner.top(), pulse_w, inner.height()), 8, 8)
            label = "FLASH"
        elif "black" in ttype:
            painter.setBrush(QColor(0, 0, 0, 190))
            pulse_w = 18 + int(self._phase * 34)
            painter.drawRoundedRect(QRect(inner.center().x() - pulse_w // 2, inner.top(), pulse_w, inner.height()), 8, 8)
            label = "DIP"
        elif "slide" in ttype or "wipe" in ttype:
            sweep_x = inner.left() + int(inner.width() * self._phase)
            painter.setBrush(QColor(255, 255, 255, 65))
            painter.drawRect(sweep_x - 10, inner.top(), 20, inner.height())
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            painter.drawLine(inner.left() + 28, inner.center().y(), inner.right() - 28, inner.center().y())
            painter.drawLine(inner.right() - 40, inner.center().y() - 10, inner.right() - 28, inner.center().y())
            painter.drawLine(inner.right() - 40, inner.center().y() + 10, inner.right() - 28, inner.center().y())
            label = "WIPE"
        elif "zoom" in ttype:
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
            radius = 10 + int(self._phase * 18)
            painter.drawEllipse(inner.center(), radius, radius)
            painter.drawEllipse(inner.center(), max(2, radius // 2), max(2, radius // 2))
            label = "ZOOM"
        else:
            fade = QLinearGradient(inner.left(), 0, inner.right(), 0)
            fade.setColorAt(0.0, QColor(255, 255, 255, 0))
            fade.setColorAt(0.5, QColor(255, 255, 255, 150))
            fade.setColorAt(1.0, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(fade))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(inner.adjusted(38, 0, -38, 0), 8, 8)
            label = "MIX"
        painter.setPen(QColor("#FFFFFF"))
        f = painter.font()
        f.setPixelSize(10)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(rect.adjusted(0, 58, 0, -3), Qt.AlignmentFlag.AlignCenter, label)

    def _draw_title(self, painter: QPainter, rect: QRect) -> None:
        payload = self._payload
        inner = rect.adjusted(10, 10, -10, -10)
        painter.setPen(Qt.PenStyle.NoPen)
        if self._sample_pixmap is not None:
            self._draw_pixmap_cover(painter, self._sample_pixmap, inner, 9)
            painter.setBrush(QColor(5, 7, 14, 82))
            painter.drawRoundedRect(inner, 9, 9)
        else:
            painter.setBrush(QColor("#111723"))
            painter.drawRoundedRect(inner, 9, 9)
            painter.setBrush(QColor("#2B3448"))
            painter.drawRect(inner.adjusted(8, 8, -8, -8))
        text = str(payload.get("text") or "TITLE").strip()[:16]
        x_norm = float(payload.get("x_norm", 0.5) or 0.5)
        y_norm = float(payload.get("y_norm", 0.5) or 0.5)
        font_size = max(16, min(72, int(payload.get("font_size", 44) or 44)))
        box_w = max(54, min(inner.width() - 20, 44 + len(text) * 5))
        box_h = 16 + int(font_size / 16)
        cx = inner.left() + int(inner.width() * x_norm)
        cy = inner.top() + int(inner.height() * y_norm)
        anim = str(payload.get("preset_id_in") or payload.get("animation") or "").casefold()
        if "slide" in anim:
            cy += int((1.0 - self._phase) * 12)
        elif "pop" in anim:
            box_w += int(math.sin(self._phase * math.pi) * 8)
        title_rect = QRect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)
        painter.setBrush(QColor(10, 12, 18, 190))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawRoundedRect(title_rect, 8, 8)
        painter.setPen(QColor("#FFFFFF"))
        f = painter.font()
        f.setPixelSize(10)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(title_rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_workflow(self, painter: QPainter, rect: QRect) -> None:
        kind = self._kind
        payload = self._payload
        inner = rect.adjusted(12, 13, -12, -13)
        painter.setPen(Qt.PenStyle.NoPen)
        if "caption" in kind:
            if self._sample_pixmap is not None:
                self._draw_pixmap_cover(painter, self._sample_pixmap, inner, 9)
                painter.setBrush(QColor(5, 7, 12, 96))
                painter.drawRoundedRect(inner, 9, 9)
            else:
                painter.setBrush(QColor("#1B2232"))
                painter.drawRoundedRect(inner, 9, 9)
            cap = QRect(inner.left() + 24, inner.bottom() - 25, inner.width() - 48, 16)
            painter.setBrush(QColor(0, 0, 0, 185))
            painter.drawRoundedRect(cap, 7, 7)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(cap, Qt.AlignmentFlag.AlignCenter, "CAPTION")
            return
        if "sticker" in kind:
            if self._sample_pixmap is not None:
                self._draw_pixmap_cover(painter, self._sample_pixmap, inner, 9)
                painter.setBrush(QColor(5, 7, 12, 104))
                painter.drawRoundedRect(inner, 9, 9)
            else:
                painter.setBrush(QColor("#20283A"))
                painter.drawRoundedRect(inner, 9, 9)
            painter.setBrush(QColor(self._colors[0]))
            bubble = QPainterPath()
            bubble.addRoundedRect(QRectF(inner.left() + 38, inner.top() + 12, 82, 30), 12, 12)
            bubble.moveTo(inner.left() + 60, inner.top() + 42)
            bubble.lineTo(inner.left() + 52, inner.top() + 54)
            bubble.lineTo(inner.left() + 78, inner.top() + 42)
            painter.drawPath(bubble)
            painter.setPen(QColor("#FFFFFF"))
            painter.drawText(QRect(inner.left() + 42, inner.top() + 15, 74, 22), Qt.AlignmentFlag.AlignCenter, "STICKER")
            return
        if "motion" in kind:
            if self._sample_pixmap is not None:
                self._draw_pixmap_cover(painter, self._sample_pixmap, inner, 9)
                painter.setBrush(QColor(5, 7, 12, 110))
                painter.drawRoundedRect(inner, 9, 9)
            else:
                painter.setBrush(QColor("#101722"))
                painter.drawRoundedRect(inner, 9, 9)
            painter.setPen(QPen(QColor(self._colors[1]), 2))
            path = QPainterPath()
            path.moveTo(inner.left() + 12, inner.bottom() - 12)
            path.cubicTo(
                inner.left() + 55,
                inner.top() + 5,
                inner.left() + 92,
                inner.bottom() - 22,
                inner.right() - 12,
                inner.top() + 18,
            )
            painter.drawPath(path)
            painter.setBrush(QColor("#FFFFFF"))
            for t in (0.0, self._phase, 1.0):
                x = inner.left() + 12 + int((inner.width() - 24) * t)
                y = inner.bottom() - 12 - int(math.sin(t * math.pi) * (inner.height() - 26))
                painter.drawEllipse(QPoint(x, y), 4, 4)
            return

        entries = list((payload.get("sequence") or payload.get("steps") or []))
        count = max(3, min(6, len(entries) or 4))
        if self._sample_pixmap is not None:
            self._draw_pixmap_cover(painter, self._sample_pixmap, inner, 9)
            painter.setBrush(QColor(5, 7, 12, 122))
            painter.drawRoundedRect(inner, 9, 9)
        else:
            painter.setBrush(QColor("#111723"))
            painter.drawRoundedRect(inner, 9, 9)
        for row, color in enumerate((self._colors[0], self._colors[1], self._colors[2])):
            y = inner.top() + 10 + row * 17
            for idx in range(count - row % 2):
                x = inner.left() + 10 + idx * 31 + row * 7
                w = 22 + (idx % 2) * 10
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(QRect(x, y, w, 10), 5, 5)
        play_x = inner.left() + int((inner.width() - 20) * self._phase) + 10
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        painter.drawLine(play_x, inner.top() + 6, play_x, inner.bottom() - 6)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        self._draw_frame(painter, rect)
        kind = self._kind
        if "effect" in kind:
            self._draw_effect(painter, rect)
        elif "transition" in kind:
            self._draw_transition(painter, rect)
        elif "title" in kind:
            self._draw_title(painter, rect)
        else:
            self._draw_workflow(painter, rect)
        painter.end()


class PresetBrowser(QWidget):
    """Searchable/category-filtered preset browser with sticky controls."""

    def __init__(
        self,
        cards: list[QWidget],
        *,
        max_height: int,
        placeholder: str,
        extra_controls: list[QWidget] | None = None,
        details_builder=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PresetBrowser")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("QWidget#PresetBrowser{background:#101112;}")
        self._all_cards = list(cards)
        self._extra_controls = list(extra_controls or [])
        self._details_builder = details_builder
        self._uses_integrated_preview = True
        self._inspected_preset_id = ""
        self._category = "All"
        self._pack = "All Packs"
        self._state = _load_preset_browser_state()
        try:
            from app.preset_feedback import preset_discoverability_cards

            hint = preset_discoverability_cards()[0]
            empty_text = f"No matching presets\n\n{hint['title']}\n{hint['body']}"
        except Exception:
            empty_text = "No matching presets\n\nDrag effect presets onto a compatible clip to apply them."
        self._empty_label = QLabel(empty_text, self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            "color:#A6AFBA;font-size:10px;background:#111316;border:1px dashed #30363D;border-radius:7px;padding:12px;"
        )
        self._empty_label.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(5, 4, 5, 5)
        root.setSpacing(4)

        self._state.setdefault("favorites", [])
        self._state.setdefault("recent", [])
        self._apply_card_state()

        self._search = QLineEdit(self)
        self._search.setObjectName("PresetSearch")
        self._search.setPlaceholderText(placeholder)
        self._search.setClearButtonEnabled(True)
        self._search.setFixedHeight(24)
        self._search.setStyleSheet(preset_search_qss())
        self._search.textChanged.connect(self._apply_filter)

        packs = ["All Packs"]
        for card in self._all_cards:
            pack = getattr(card, "pack", "")
            if pack and pack not in packs:
                packs.append(pack)
        self._pack_combo = QComboBox(self)
        self._pack_combo.setObjectName("PresetPackCombo")
        self._pack_combo.setFixedHeight(24)
        self._pack_combo.setStyleSheet(preset_pack_combo_qss())
        for pack in packs:
            self._pack_combo.addItem(make_pack_icon(pack), pack, pack)
        self._pack_combo.setVisible(False)
        self._pack_combo.currentIndexChanged.connect(self._set_pack_from_combo)
        root.addWidget(self._pack_combo)

        self._pack_palette = QWidget(self)
        palette_lay = QHBoxLayout(self._pack_palette)
        palette_lay.setContentsMargins(0, 0, 0, 0)
        palette_lay.setSpacing(5)
        self._pack_palette_group = QButtonGroup(self)
        self._pack_palette_group.setExclusive(True)
        for idx, pack in enumerate(packs[:8]):
            btn = QToolButton(self._pack_palette)
            btn.setCheckable(True)
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(pack)
            btn.setText("A" if pack == "All Packs" else "")
            btn.setStyleSheet(pack_palette_button_style(pack))
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _checked=False, p=pack: self._set_pack_from_palette(p))
            self._pack_palette_group.addButton(btn)
            palette_lay.addWidget(btn)
        palette_lay.addStretch(1)
        self._pack_palette.setVisible(False)

        self._category_combo = QComboBox(self)
        self._category_combo.setObjectName("PresetCategoryCombo")
        self._category_combo.setFixedHeight(24)
        self._category_combo.setStyleSheet(preset_category_combo_qss())
        cats = ["All", "Favorites", "Recent"]
        for card in self._all_cards:
            cat = getattr(card, "category", "")
            if cat and cat not in cats:
                cats.append(cat)
        self._category_labels: dict[str, str] = {}
        for cat in cats:
            if cat == "All":
                label = "All Categories"
            elif cat == "Favorites":
                label = "Favorites"
            elif cat == "Recent":
                label = "Recent"
            else:
                label = str(cat)
            self._category_labels[cat] = label
            self._category_combo.addItem(label, cat)
        self._category_combo.setVisible(False)
        self._category_combo.currentIndexChanged.connect(self._set_category_from_combo)
        root.addWidget(self._category_combo)

        self._category_filter_btn = QToolButton(self)
        self._category_filter_btn.setObjectName("PresetCategoryFilterButton")
        self._category_filter_btn.setFixedSize(28, 24)
        self._category_filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._category_filter_btn.setIcon(app_icon("sliders", size=10, color="#E5E8EF"))
        self._category_filter_btn.setIconSize(icon_size(10))
        self._category_filter_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._category_filter_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._category_filter_btn.setVisible(len(cats) > 1)
        self._category_filter_btn.setStyleSheet(preset_category_filter_button_qss())
        menu = QMenu(self._category_filter_btn)
        menu.setStyleSheet(preset_menu_qss())
        self._category_actions: dict[str, QAction] = {}
        for cat in cats:
            action = menu.addAction(str(self._category_labels.get(cat, cat)))
            action.setCheckable(True)
            action.triggered.connect(lambda _checked=False, c=cat: self._set_category_from_menu(c))
            self._category_actions[cat] = action
        self._category_filter_btn.setMenu(menu)

        control_row = QWidget(self)
        control_row.setObjectName("PresetBrowserControlRow")
        control_row.setFixedHeight(28)
        control_lay = QHBoxLayout(control_row)
        control_lay.setContentsMargins(0, 0, 0, 0)
        control_lay.setSpacing(5)
        control_lay.addWidget(self._search, 1)
        for control in self._extra_controls:
            control_lay.addWidget(control, 0)
        control_lay.addWidget(self._category_filter_btn, 0)
        root.insertWidget(0, control_row)
        self._refresh_category_filter_button()

        self._top_shadow = QWidget(self)
        self._top_shadow.setFixedHeight(3)
        self._top_shadow.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(0,0,0,90),stop:1 rgba(0,0,0,0));"
        )
        self._top_shadow.hide()
        root.addWidget(self._top_shadow)

        self._inspector = PresetInspectorPanel(self, details_builder=self._details_builder)
        root.addWidget(self._inspector)

        self._grid = PresetScrollGrid([], max_height=max_height, parent=self)
        root.addWidget(self._grid)

        self._bottom_shadow = QWidget(self)
        self._bottom_shadow.setFixedHeight(3)
        self._bottom_shadow.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(0,0,0,0),stop:1 rgba(0,0,0,90));"
        )
        root.addWidget(self._bottom_shadow)

        bar = self._grid.vertical_scroll_bar()
        bar.valueChanged.connect(self._update_shadows)
        bar.rangeChanged.connect(lambda _a, _b: self._update_shadows())
        self._apply_filter()

    def _apply_card_state(self) -> None:
        favorites = {str(v) for v in (self._state.get("favorites") or [])}
        recent = [str(v) for v in (self._state.get("recent") or [])]
        recent_rank = {pid: idx + 1 for idx, pid in enumerate(recent)}
        for card in self._all_cards:
            try:
                card._browser = self
                pid = str(getattr(card, "preset_id", ""))
                card.set_library_state(
                    favorite=pid in favorites,
                    recent_rank=recent_rank.get(pid, 0),
                )
            except Exception:
                pass

    def _toggle_favorite(self, card) -> None:
        pid = str(getattr(card, "preset_id", "") or "")
        if not pid:
            return
        favorites = [str(v) for v in (self._state.get("favorites") or [])]
        if pid in favorites:
            favorites = [v for v in favorites if v != pid]
        else:
            favorites.insert(0, pid)
        self._state["favorites"] = favorites[:96]
        _save_preset_browser_state(self._state)
        self._apply_card_state()
        self._apply_filter()

    def _mark_recent(self, card) -> None:
        pid = str(getattr(card, "preset_id", "") or "")
        if not pid:
            return
        recent = [str(v) for v in (self._state.get("recent") or []) if str(v) != pid]
        recent.insert(0, pid)
        self._state["recent"] = recent[:32]
        _save_preset_browser_state(self._state)
        self._apply_card_state()

    def _inspect_card(self, card) -> None:
        previous_id = str(getattr(self, "_inspected_preset_id", "") or "")
        try:
            self._inspector.inspect(card)
            self._inspected_preset_id = str(getattr(card, "preset_id", "") or "")
            current_id = self._inspected_preset_id
            for row in self._all_cards:
                try:
                    pid = str(getattr(row, "preset_id", "") or "")
                    if pid in {previous_id, current_id}:
                        row.update()
                except Exception:
                    pass
        except Exception:
            pass

    def _set_category(self, category: str) -> None:
        self._category = str(category or "All")
        combo = getattr(self, "_category_combo", None)
        if combo is not None:
            idx = combo.findData(self._category)
            if idx >= 0 and idx != combo.currentIndex():
                with _block_signals(combo):
                    combo.setCurrentIndex(idx)
        self._refresh_category_filter_button()
        self._apply_filter()

    def _set_category_from_menu(self, category: str) -> None:
        self._set_category(str(category or "All"))

    def _set_category_from_combo(self) -> None:
        combo = getattr(self, "_category_combo", None)
        self._category = str(combo.currentData() if combo is not None else "All") or "All"
        self._refresh_category_filter_button()
        self._apply_filter()

    def _refresh_category_filter_button(self) -> None:
        label = str(getattr(self, "_category_labels", {}).get(self._category, self._category or "All"))
        btn = getattr(self, "_category_filter_btn", None)
        if btn is not None:
            btn.setText("")
            btn.setToolTip(f"Filter: {label}")
            btn.setAccessibleName(f"Filter: {label}")
        for cat, action in getattr(self, "_category_actions", {}).items():
            try:
                action.setChecked(str(cat) == self._category)
            except Exception:
                pass

    def _set_pack_from_combo(self) -> None:
        self._pack = str(self._pack_combo.currentData() or "All Packs")
        for button in getattr(self, "_pack_palette_group", QButtonGroup()).buttons():
            button.setChecked(button.toolTip() == self._pack)
        self._apply_filter()

    def _set_pack_from_palette(self, pack: str) -> None:
        self._pack = str(pack or "All Packs")
        idx = self._pack_combo.findData(self._pack)
        if idx >= 0:
            with _block_signals(self._pack_combo):
                self._pack_combo.setCurrentIndex(idx)
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self._search.text() if hasattr(self, "_search") else ""
        cards = [
            card for card in self._all_cards
            if (self._pack == "All Packs" or getattr(card, "pack", "") == self._pack)
            and getattr(card, "matches_filter", lambda _q, _c: True)(query, self._category)
        ]
        cards = sorted(
            cards,
            key=lambda card: (
                0 if getattr(card, "is_favorite", False) else 1,
                getattr(card, "_recent_rank", 999) or 999,
                str(getattr(card, "_label", "")).casefold(),
            ),
        )
        self._empty_label.setVisible(not bool(cards))
        self._grid.set_cards(cards if cards else [self._empty_label])
        if cards:
            visible_ids = {str(getattr(card, "preset_id", "") or "") for card in cards}
            if not self._inspected_preset_id or self._inspected_preset_id not in visible_ids:
                self._inspect_card(cards[0])
        QTimer.singleShot(0, self._update_shadows)

    def _update_shadows(self) -> None:
        bar = self._grid.vertical_scroll_bar()
        max_value = bar.maximum()
        self._top_shadow.setVisible(max_value > 0 and bar.value() > 0)
        self._bottom_shadow.setVisible(max_value > 0 and bar.value() < max_value)
