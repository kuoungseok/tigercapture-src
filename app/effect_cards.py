"""Drag-source effect cards for the timeline.

Each card is a compact pill that lives in the editor's left-dock
"Effects Library". Dragging a card drops a new actor onto a track at
the cursor position via the matching MIME type:

- ``FadeCard``        → ``FADE_MIME_TYPE``  (FadeSegment)
- ``ZoomCard``        → ``ZOOM_MIME_TYPE``  (ZoomActor)
- ``SpeedCard``       → ``SPEED_MIME_TYPE`` (SpeedSegment)
- ``TypographyCard``  → ``TEXT_CLIP_MIME``  (TextClip on the typography lane)

The classes were extracted from ``video_editor_window.py`` so that
12k-line file keeps shrinking. They're self-contained — no editor or
track state, just QDrag + visual swatch + a label. The receiving
end (``TrackRow`` / ``TextLaneRow``) handles the actual data model
mutation.
"""
from __future__ import annotations

from PySide6.QtCore import QMimeData, QPoint, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDrag,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QPolygon,
)
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from app.i18n import tr
from app.style import (
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_ORANGE,
    COLOR_BG_L3,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_PRIMARY,
)
from app.typography import TEXT_CLIP_MIME


# MIME type identifiers for the per-card drag payloads. Kept here
# (not in video_editor_window) so card consumers can import them
# without dragging the editor module along.
FADE_MIME_TYPE = "application/x-tigercapture-transition"
SPEED_MIME_TYPE = "application/x-tigercapture-speed"
ZOOM_MIME_TYPE = "application/x-tigercapture-zoom"


# ---------------------------------------------------------------------------
#  Fade
# ---------------------------------------------------------------------------


class FadeCard(QWidget):
    """Draggable "Fade" transition card. Drag-drop onto a track creates a
    FadeSegment at the drop position; the embedded combo's value sets the
    new segment's default duration."""

    DEFAULT_DURATION_MS = 400

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("FadeCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(120)
        self.setStyleSheet(
            f"""
            QWidget#FadeCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#FadeCard:hover {{
                border-color: {COLOR_ACCENT_ORANGE};
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 12, 4)
        row.setSpacing(8)

        swatch = _FadeSwatch()
        swatch.setFixedSize(44, 22)
        row.addWidget(swatch)

        title = QLabel(tr("veditor.fade_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        self.setToolTip(tr("veditor.fade_card.hint"))

    def selected_duration_ms(self) -> int:
        return self.DEFAULT_DURATION_MS

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mime = QMimeData()
        mime.setData(FADE_MIME_TYPE, str(self.selected_duration_ms()).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _FadeSwatch(QWidget):
    """Mini horizontal fade gradient — doubles as a visual "icon" for the
    Fade transition card. Black → orange glow → transparent."""

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        # Left half: fade-out (content → black)
        g1 = QLinearGradient(0, 0, w / 2, 0)
        g1.setColorAt(0.0, QColor("#4a6a8a"))
        g1.setColorAt(1.0, QColor("#0a0a0e"))
        painter.fillRect(0, 0, int(w / 2), h, QBrush(g1))
        # Right half: fade-in (black → content) with an orange glow join
        g2 = QLinearGradient(w / 2, 0, w, 0)
        g2.setColorAt(0.0, QColor("#0a0a0e"))
        g2.setColorAt(0.5, QColor(216, 90, 48, 180))
        g2.setColorAt(1.0, QColor("#4a6a8a"))
        painter.fillRect(int(w / 2), 0, w - int(w / 2), h, QBrush(g2))
        # Vertical join marker
        pen = QPen(QColor(COLOR_ACCENT_ORANGE))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawLine(int(w / 2), 0, int(w / 2), h)


# ---------------------------------------------------------------------------
#  Zoom
# ---------------------------------------------------------------------------


class ZoomCard(QWidget):
    """Draggable "Zoom" card. Drop on a track to spawn a ZoomActor at the
    drop position; the actor's target rectangle starts unset and the user
    picks it via the modal that opens on click."""

    DEFAULT_DURATION_MS = 2000

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ZoomCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(120)
        self.setStyleSheet(
            f"""
            QWidget#ZoomCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#ZoomCard:hover {{
                border-color: {COLOR_ACCENT_BLUE};
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 12, 4)
        row.setSpacing(8)

        icon = QLabel("🔍")
        icon.setStyleSheet("font-size: 16px;")
        row.addWidget(icon)

        title = QLabel(tr("veditor.zoom_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        self.setToolTip(tr("veditor.zoom_card.hint"))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mime = QMimeData()
        mime.setData(ZOOM_MIME_TYPE, str(self.DEFAULT_DURATION_MS).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = self.grab()
        drag.setPixmap(pix)
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


# ---------------------------------------------------------------------------
#  Typography
# ---------------------------------------------------------------------------


class TypographyCard(QWidget):
    """Draggable "T" card for spawning a TextClip on the typography lane.

    Structure mirrors ``FadeCard``: a compact pill with a visual swatch
    and a label, drag starts a QDrag with ``TEXT_CLIP_MIME`` so the
    receiving lane can distinguish text-clip drops from generic file
    drops or fade-card drops."""

    DEFAULT_DURATION_MS = 2000     # 2-second clip by default

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TypographyCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(120)
        self.setStyleSheet(
            f"""
            QWidget#TypographyCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#TypographyCard:hover {{
                border-color: #D85A30;
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 12, 4)
        row.setSpacing(8)

        swatch = _TypographySwatch()
        swatch.setFixedSize(44, 22)
        row.addWidget(swatch)

        title = QLabel(tr("veditor.typo_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        self.setToolTip(tr("veditor.typo_card.hint"))

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        mime = QMimeData()
        mime.setData(
            TEXT_CLIP_MIME,
            str(self.DEFAULT_DURATION_MS).encode("utf-8"),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _TypographySwatch(QWidget):
    """Orange-to-pink gradient with a bold "T" glyph — visual identity
    for the TypographyCard. Matches the colour the clip chip paints so
    users recognize the two as the same affordance."""

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#D85A30"))
        grad.setColorAt(1.0, QColor("#B83FAD"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#D85A30"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        painter.setPen(QPen(QColor("#FFFFFF")))
        f = QFont(painter.font())
        f.setBold(True)
        f.setPointSize(int(h * 0.55))
        painter.setFont(f)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "T")


# ---------------------------------------------------------------------------
#  Speed
# ---------------------------------------------------------------------------


class SpeedCard(QWidget):
    """Draggable card for spawning a SpeedSegment on a video track.

    Has a compact speed selector (combo) so the user can pick the rate
    *before* dragging — matches how other NLEs let you pre-configure
    the tool before applying. Drop on a TrackRow creates a 2-second
    segment at the selected speed.

    Slow-motion presets (¼x Smooth, ½x Smooth) automatically enable
    frame blending so playback is smooth instead of choppy.  Fast-
    forward presets (2x Fast, 4x Fast) are plain speed-up entries
    with no blending.

    MIME payload format: ``"{speed:.6f}|{duration_ms}|{frame_blend}|{blend_mode}"``
    where ``frame_blend`` is ``"1"`` or ``"0"`` and ``blend_mode`` is
    ``"linear"`` or ``"optical_flow"``.  Old 2-token payloads
    (``"{speed}|{dur}"``) are still accepted by the drop handler."""

    DEFAULT_DURATION_MS = 2000
    # (speed, frame_blend, blend_mode, label)
    PRESET_ENTRIES = [
        (0.25, True,  "linear", "¼x Smooth"),
        (0.50, True,  "linear", "½x Smooth"),
        (0.75, False, "linear",       "¾x"),
        (1.50, False, "linear",       "1.5x"),
        (2.0,  False, "linear",       "2x Fast"),
        (4.0,  False, "linear",       "4x Fast"),
        (8.0,  False, "linear",       "8x"),
        (16.0, False, "linear",       "16x"),
    ]
    # Speed-only list used by TrackRow wheel and right-click menu (legacy API).
    PRESETS = [e[0] for e in PRESET_ENTRIES]
    DEFAULT_SPEED = 2.0

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SpeedCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedHeight(40)
        self.setMinimumWidth(150)
        self.setStyleSheet(
            f"""
            QWidget#SpeedCard {{
                background-color: {COLOR_BG_L5};
                border: 1px solid {COLOR_BORDER_DEFAULT};
                border-radius: 6px;
            }}
            QWidget#SpeedCard:hover {{
                border-color: {COLOR_ACCENT_HOVER};
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 4, 10, 4)
        row.setSpacing(8)

        swatch = _SpeedSwatch()
        swatch.setFixedSize(44, 22)
        row.addWidget(swatch)

        title = QLabel(tr("veditor.speed_card.title"))
        title.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; font-weight: 700;")
        row.addWidget(title)

        # Preset selector — don't start a drag when the user clicks
        # inside the combo, only when they grab the body.
        self._combo = QComboBox()
        for speed, fb, bm, label in self.PRESET_ENTRIES:
            # Store (speed, frame_blend, blend_mode) as tuple user-data
            self._combo.addItem(label, (speed, fb, bm))
        # Default selection: "2x Fast"
        default_label = next(
            (e[3] for e in self.PRESET_ENTRIES if abs(e[0] - self.DEFAULT_SPEED) < 1e-3 and not e[1]),
            self.PRESET_ENTRIES[0][3],
        )
        self._combo.setCurrentText(default_label)
        self._combo.setFixedWidth(90)
        self._combo.setStyleSheet(
            f"QComboBox {{ background-color: {COLOR_BG_L3}; color: {COLOR_TEXT_PRIMARY}; "
            f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; padding: 2px 6px; }}"
        )
        row.addWidget(self._combo)

        self.setToolTip(tr("veditor.speed_card.hint"))

    @staticmethod
    def _format_preset(p: float) -> str:
        """Legacy label formatter — returns plain speed string like '2x'."""
        if abs(p - round(p)) < 1e-3:
            return f"{int(round(p))}x"
        return f"{p:g}x"

    def selected_speed(self) -> float:
        data = self._combo.currentData()
        if isinstance(data, tuple):
            return float(data[0])
        if isinstance(data, (int, float)) and data > 0:
            return float(data)
        return self.DEFAULT_SPEED

    def selected_frame_blend(self) -> bool:
        data = self._combo.currentData()
        if isinstance(data, tuple) and len(data) >= 2:
            return bool(data[1])
        return False

    def selected_blend_mode(self) -> str:
        data = self._combo.currentData()
        if isinstance(data, tuple) and len(data) >= 3:
            return str(data[2])
        return "linear"

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        # Don't steal clicks from the combo — if the user clicked on
        # the combo area, let Qt handle it normally.
        combo_rect = self._combo.geometry()
        if combo_rect.contains(event.position().toPoint()):
            super().mousePressEvent(event)
            return

        speed = self.selected_speed()
        fb = "1" if self.selected_frame_blend() else "0"
        bm = self.selected_blend_mode()
        payload = f"{speed:.6f}|{self.DEFAULT_DURATION_MS}|{fb}|{bm}"
        mime = QMimeData()
        mime.setData(SPEED_MIME_TYPE, payload.encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)


class _SpeedSwatch(QWidget):
    """Mini visual for the SpeedCard — three forward-chevrons on a
    blue pad to suggest 'fast forward'."""

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor("#ff7a4a"))
        grad.setColorAt(1.0, QColor("#b04722"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#ff7a4a"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        # Three chevron arrows ">"
        painter.setPen(QPen(QColor("#FFFFFF"), 2))
        tri_w = 5
        cy = h // 2
        # spacing between chevrons
        spacing = 7
        start_x = (w - (3 * spacing - 1)) // 2
        for i in range(3):
            x = start_x + i * spacing
            painter.drawLine(x, cy - tri_w, x + tri_w, cy)
            painter.drawLine(x + tri_w, cy, x, cy + tri_w)
