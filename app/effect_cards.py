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

from PySide6.QtCore import QMimeData, QPoint, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDrag,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygon,
)
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
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
FADE_MIME_TYPE   = "application/x-tigercapture-transition"
SPEED_MIME_TYPE  = "application/x-tigercapture-speed"
ZOOM_MIME_TYPE   = "application/x-tigercapture-zoom"
LIVE2D_MIME_TYPE = "application/x-live2d-actor-new"
SPINE_MIME_TYPE  = "application/x-spine-actor-new"


_CARD_TEXT = "#F4F5F7"
_CARD_BG_0 = "#3A3D43"
_CARD_BG_1 = "#24272D"
_CARD_BORDER = "#51555E"
_PALETTE_TILE_SIZE = 32
_PALETTE_SWATCH_SIZE = 26


def _effect_card_qss(object_name: str, hover_color: str) -> str:
    return f"""
        QWidget#{object_name} {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
        }}
        QWidget#{object_name}:hover {{
            background-color: rgba(255, 255, 255, 8);
            border-color: rgba(230, 232, 238, 150);
        }}
        QWidget#{object_name} QLabel {{
            background: transparent;
            color: #111421;
        }}
        QWidget#{object_name}:hover QLabel {{
            color: {_CARD_TEXT};
        }}
    """


def _style_effect_title(label: QLabel) -> None:
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(10)
    label.setFont(font)
    label.setStyleSheet("")


def _square_card_layout(card: QWidget) -> QVBoxLayout:
    row = QVBoxLayout(card)
    row.setContentsMargins(2, 2, 2, 2)
    row.setSpacing(0)
    row.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return row


class _EffectTile(QWidget):
    """Square icon tile whose text label appears only while hovered."""

    def __init__(self) -> None:
        super().__init__()
        self._hover_labels: list[tuple[QLabel, str]] = []
        self.setMouseTracking(True)

    def _register_hover_label(self, label: QLabel, text: str) -> None:
        label.setFixedHeight(0)
        label.setMaximumHeight(0)
        label.setText("")
        self._hover_labels.append((label, text))

    def enterEvent(self, event) -> None:
        for label, text in self._hover_labels:
            label.setText(text)
        try:
            super().enterEvent(event)
        except TypeError:
            pass

    def leaveEvent(self, event) -> None:
        for label, _text in self._hover_labels:
            label.setText("")
        try:
            super().leaveEvent(event)
        except TypeError:
            pass


class _PaletteSwatch(QWidget):
    """Small wallpaper-style color swatch used by timeline palette cards."""

    def __init__(
        self,
        stops: tuple[tuple[str, str], ...],
        *,
        icon_name: str | None = None,
        glyph: str | None = None,
    ) -> None:
        super().__init__()
        self._stops = stops
        self._icon_name = icon_name
        self._glyph = glyph

    @staticmethod
    def _alpha(hex_color: str, alpha: int) -> QColor:
        color = QColor(hex_color)
        color.setAlpha(max(0, min(255, int(alpha))))
        return color

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        radius = 7
        rect = self.rect().adjusted(0, 0, -1, -1)
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0.0, QColor("#4A4D54"))
        base.setColorAt(0.48, QColor("#343840"))
        base.setColorAt(1.0, QColor("#24272D"))
        painter.setPen(QPen(QColor(255, 255, 255, 76), 1))
        painter.setBrush(QBrush(base))
        painter.drawRoundedRect(rect, radius, radius)

        clip = QPainterPath()
        clip.addRoundedRect(QRectF(rect), radius, radius)
        painter.save()
        painter.setClipPath(clip)
        if self._stops:
            main_a, main_b = self._stops[0]
            accent = QLinearGradient(0, 0, w, h)
            accent.setColorAt(0.0, self._alpha(main_a, 84))
            accent.setColorAt(1.0, self._alpha(main_b, 36))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(accent))
            painter.drawPolygon(QPolygon([
                QPoint(max(0, w - 12), 0),
                QPoint(w, 0),
                QPoint(w, max(10, h - 4)),
                QPoint(max(4, w - 22), h),
            ]))
            if len(self._stops) > 1:
                lower_a, lower_b = self._stops[1]
                bottom = QLinearGradient(0, h - 4, w, h - 4)
                bottom.setColorAt(0.0, self._alpha(lower_a, 120))
                bottom.setColorAt(1.0, self._alpha(lower_b, 80))
                painter.setBrush(QBrush(bottom))
                painter.drawRoundedRect(2, h - 5, max(1, w - 4), 3, 1, 1)
            if len(self._stops) > 2:
                edge_a, edge_b = self._stops[2]
                edge = QLinearGradient(0, 0, 0, h)
                edge.setColorAt(0.0, self._alpha(edge_a, 80))
                edge.setColorAt(1.0, self._alpha(edge_b, 30))
                painter.setBrush(QBrush(edge))
                painter.drawRoundedRect(1, 4, 2, max(1, h - 8), 1, 1)
        painter.restore()

        shade = QLinearGradient(0, 0, 0, h)
        shade.setColorAt(0.0, QColor(255, 255, 255, 38))
        shade.setColorAt(0.38, QColor(255, 255, 255, 7))
        shade.setColorAt(1.0, QColor(0, 0, 0, 74))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(shade))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius - 1, radius - 1)

        if self._glyph:
            painter.setPen(QPen(QColor("#F1F3F7"), 1))
            font = QFont(painter.font())
            font.setBold(True)
            font.setPointSize(max(8, int(h * 0.48)))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._glyph)
        elif self._icon_name:
            pix = app_icon(self._icon_name, size=16, color="#F1F3F7").pixmap(icon_size(16))
            painter.setOpacity(0.96)
            painter.drawPixmap((w - pix.width()) // 2, (h - pix.height()) // 2, pix)


# ---------------------------------------------------------------------------
#  Fade
# ---------------------------------------------------------------------------


class FadeCard(_EffectTile):
    """Draggable "Fade" transition card. Drag-drop onto a track creates a
    FadeSegment at the drop position; the embedded combo's value sets the
    new segment's default duration."""

    DEFAULT_DURATION_MS = 400

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("FadeCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(_PALETTE_TILE_SIZE, _PALETTE_TILE_SIZE)
        self.setStyleSheet(_effect_card_qss("FadeCard", "#FF8A5E"))
        row = _square_card_layout(self)

        swatch = _PaletteSwatch(
            (
                ("#7DC9FF", "#2B456F"),
                ("#10131F", "#05060A"),
                ("#FF885E", "#82334B"),
            ),
            icon_name="fade",
        )
        swatch.setFixedSize(_PALETTE_SWATCH_SIZE, _PALETTE_SWATCH_SIZE)
        row.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Fade")
        _style_effect_title(title)
        self._register_hover_label(title, "Fade")
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

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


class ZoomCard(_EffectTile):
    """Draggable "Zoom" card. Drop on a track to spawn a ZoomActor at the
    drop position; the actor's target rectangle starts unset and the user
    picks it via the modal that opens on click."""

    DEFAULT_DURATION_MS = 2000

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ZoomCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(_PALETTE_TILE_SIZE, _PALETTE_TILE_SIZE)
        self.setStyleSheet(_effect_card_qss("ZoomCard", "#A99CFF"))
        row = _square_card_layout(self)

        swatch = _PaletteSwatch(
            (
                ("#8F7CFF", "#4432B8"),
                ("#4EC8FF", "#225EAB"),
                ("#FFD266", "#D8686E"),
            ),
            icon_name="zoom",
        )
        swatch.setFixedSize(_PALETTE_SWATCH_SIZE, _PALETTE_SWATCH_SIZE)
        row.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Zoom")
        _style_effect_title(title)
        self._register_hover_label(title, "Zoom")
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

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


class TypographyCard(_EffectTile):
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
        self.setFixedSize(_PALETTE_TILE_SIZE, _PALETTE_TILE_SIZE)
        self.setStyleSheet(_effect_card_qss("TypographyCard", "#FF78B8"))
        row = _square_card_layout(self)

        swatch = _PaletteSwatch(
            (
                ("#FF7A4A", "#C94438"),
                ("#F455A8", "#8B4CF0"),
                ("#FFE083", "#F16B69"),
            ),
            glyph="T",
        )
        swatch.setFixedSize(_PALETTE_SWATCH_SIZE, _PALETTE_SWATCH_SIZE)
        row.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Text")
        _style_effect_title(title)
        self._register_hover_label(title, "Text")
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

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


class SpeedCard(_EffectTile):
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
    # Normalize visible combo labels. The legacy literal block above may contain
    # mojibake in older worktrees; these are the labels used at runtime.
    PRESET_ENTRIES = [
        (0.25, True,  "linear", "0.25x Smooth"),
        (0.50, True,  "linear", "0.5x Smooth"),
        (0.75, False, "linear", "0.75x"),
        (1.50, False, "linear", "1.5x"),
        (2.0,  False, "linear", "2x Fast"),
        (4.0,  False, "linear", "4x Fast"),
        (8.0,  False, "linear", "8x"),
        (16.0, False, "linear", "16x"),
    ]
    PRESETS = [e[0] for e in PRESET_ENTRIES]

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SpeedCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(_PALETTE_TILE_SIZE, _PALETTE_TILE_SIZE)
        self.setStyleSheet(_effect_card_qss("SpeedCard", "#FF9A5E"))
        row = _square_card_layout(self)

        swatch = _PaletteSwatch(
            (
                ("#FF995D", "#D14836"),
                ("#FFD45D", "#FF7A45"),
                ("#8C6BFF", "#415AE8"),
            ),
            icon_name="chevrons",
        )
        swatch.setFixedSize(_PALETTE_SWATCH_SIZE, _PALETTE_SWATCH_SIZE)
        row.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Speed")
        _style_effect_title(title)
        self._register_hover_label(title, "Speed")
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Preset selector — don't start a drag when the user clicks
        # inside the combo, only when they grab the body.
        self._combo = QComboBox(self)
        for speed, fb, bm, label in self.PRESET_ENTRIES:
            # Store (speed, frame_blend, blend_mode) as tuple user-data
            self._combo.addItem(label, (speed, fb, bm))
        # Default selection: "2x Fast"
        default_label = next(
            (e[3] for e in self.PRESET_ENTRIES if abs(e[0] - self.DEFAULT_SPEED) < 1e-3 and not e[1]),
            self.PRESET_ENTRIES[0][3],
        )
        self._combo.setCurrentText(default_label)
        self._combo.setFixedWidth(78)
        self._combo.setStyleSheet(
            "QComboBox { background-color: #111421; color: #F8F4EA; "
            "border: 1px solid #3A4158; border-radius: 9px; padding: 3px 16px 3px 7px; "
            "font-size: 11px; font-weight: 700; }"
            "QComboBox:hover { border-color: #FF9A5E; background-color: #181C2A; }"
            "QComboBox::drop-down { border: none; width: 15px; }"
            "QComboBox::down-arrow { image: none; border: none; }"
        )
        self._combo.hide()

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
        if self._combo.isVisible() and combo_rect.contains(event.position().toPoint()):
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


# ---------------------------------------------------------------------------
#  Live2D
# ---------------------------------------------------------------------------


class Live2DCard(_EffectTile):
    """Draggable Live2D actor card.

    Drag onto the timeline to create an empty Live2D actor clip at the drop
    position. Double-click to open the Live2D editor.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Live2DCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(_PALETTE_TILE_SIZE, _PALETTE_TILE_SIZE)
        self.setStyleSheet(_effect_card_qss("Live2DCard", "#8F98A5"))
        row = _square_card_layout(self)

        swatch = _PaletteSwatch(
            (
                ("#4A4E55", "#272B31"),
                ("#8F98A5", "#59616B"),
            ),
            icon_name="live2d",
        )
        swatch.setFixedSize(_PALETTE_SWATCH_SIZE, _PALETTE_SWATCH_SIZE)
        row.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Live2D")
        _style_effect_title(title)
        self._register_hover_label(title, "Live2D")
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setToolTip(
            "드래그: 타임라인에 Live2D 액터 추가\n"
            "더블클릭: Live2D 에디터 열기"
        )

        self.setToolTip(
            "Drag to the timeline to add a Live2D actor.\n"
            "Double-click to open the Live2D editor."
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not hasattr(self, "_drag_start"):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 8:
            return
        from PySide6.QtCore import QByteArray
        mime = QMimeData()
        mime.setData(LIVE2D_MIME_TYPE, QByteArray(b"1"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self._drag_start)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Signal via parent chain — VideoEditorWindow catches this
            w = self.window()
            if hasattr(w, "_open_live2d_viewer"):
                w._open_live2d_viewer()


class _Live2DSwatch(QWidget):
    """Purple-blue gradient swatch with a ribbon/bow icon."""

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#7040c0"))
        grad.setColorAt(1.0, QColor("#4060d0"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#7040c0"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)
        # Bow/ribbon shape  — two overlapping ellipses
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 200))
        cx, cy = w // 2, h // 2
        r = min(w, h) // 4
        painter.drawEllipse(cx - r * 2, cy - r, r * 2, r * 2)
        painter.drawEllipse(cx, cy - r, r * 2, r * 2)
        painter.drawEllipse(cx - r // 2, cy - r // 2, r, r)


# ---------------------------------------------------------------------------
#  Spine
# ---------------------------------------------------------------------------


class SpineCard(_EffectTile):
    """Draggable Spine actor card."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SpineCard")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setFixedSize(_PALETTE_TILE_SIZE, _PALETTE_TILE_SIZE)
        self.setStyleSheet(_effect_card_qss("SpineCard", "#8F98A5"))
        row = _square_card_layout(self)

        swatch = _PaletteSwatch(
            (
                ("#4A4E55", "#272B31"),
                ("#8F98A5", "#59616B"),
            ),
            icon_name="spine",
        )
        swatch.setFixedSize(_PALETTE_SWATCH_SIZE, _PALETTE_SWATCH_SIZE)
        row.addWidget(swatch, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Spine")
        _style_effect_title(title)
        self._register_hover_label(title, "Spine")
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        self.setToolTip(
            "Drag to the timeline to add a Spine actor.\n"
            "Double-click to open the Spine editor."
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_start = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if not hasattr(self, "_drag_start"):
            return
        if (event.position().toPoint() - self._drag_start).manhattanLength() < 8:
            return
        from PySide6.QtCore import QByteArray
        mime = QMimeData()
        mime.setData(SPINE_MIME_TYPE, QByteArray(b"1"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self._drag_start)
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        drag.exec(Qt.DropAction.CopyAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            w = self.window()
            if hasattr(w, "_open_spine_editor"):
                w._open_spine_editor()


class _SpineSwatch(QWidget):
    """Small orange actor-rig icon for the Spine card."""

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0.0, QColor("#D85A30"))
        grad.setColorAt(1.0, QColor("#6e4a92"))
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(QColor("#D85A30"), 1))
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 4, 4)

        painter.setPen(QPen(QColor(255, 255, 255, 220), 2))
        cx = w // 2
        head_y = max(5, h // 4)
        body_y = h // 2 + 1
        foot_y = h - 4
        painter.drawEllipse(cx - 3, head_y - 3, 6, 6)
        painter.drawLine(cx, head_y + 3, cx, body_y)
        painter.drawLine(cx, body_y, cx - 8, body_y - 2)
        painter.drawLine(cx, body_y, cx + 8, body_y - 2)
        painter.drawLine(cx, body_y, cx - 6, foot_y)
        painter.drawLine(cx, body_y, cx + 6, foot_y)
