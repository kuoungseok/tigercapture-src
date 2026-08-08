from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class PainterPalettePreset:
    key: str
    name: str
    subtitle: str
    colors: tuple[str, ...]
    columns: int = 6
    material_profile: tuple[tuple[str, float], ...] = ()
    recommended_brush_style: str = ""


PAINTER_PALETTE_PRESETS: tuple[PainterPalettePreset, ...] = (
    PainterPalettePreset(
        "oil_colour_studies",
        "Oil Colour Studies",
        "Palette knife · dimensional paint",
        (
            "#8E2635", "#D95871", "#8B2730",
            "#C7492D", "#EF7653", "#B7662E",
            "#E29131", "#F1B54A", "#9D9436",
            "#4D7B42", "#6FAF66", "#46876A",
            "#237B72", "#62B1A7", "#478FA7",
            "#2D689E", "#66A5C8", "#4C699C",
            "#354985", "#6F78B5", "#6D61A0",
            "#2F315D", "#3E436E", "#636484",
            "#26324A", "#48495B", "#5E5366",
            "#282838", "#3F3B50", "#56505C",
        ),
        columns=3,
        material_profile=(
            ("load", 0.94),
            ("thickness", 0.90),
            ("wetness", 0.24),
            ("gloss", 0.42),
            ("roughness", 0.44),
        ),
        recommended_brush_style="palette_knife",
    ),
    PainterPalettePreset(
        "skin_tones",
        "Skin Tones",
        "Portrait · warm to deep",
        (
            "#F7D8C2", "#F1C3A7", "#E9AE8C", "#D99069", "#BF704A", "#8C482B",
            "#F1C7A3", "#DFAB7D", "#C98A5E", "#A96039", "#783B24", "#4B291D",
            "#E7B594", "#C98F70", "#A96E53", "#86513F", "#663B30", "#3C271F",
            "#F5C9AF", "#E5A37F", "#D1815B", "#B9603E", "#8F432C", "#5B3025",
            "#C99372", "#AC7054", "#925842", "#744334", "#563329", "#34231E",
        ),
    ),
    PainterPalettePreset(
        "vibrant_contrast",
        "Vibrant Contrast",
        "Editorial · clean accents",
        (
            "#D1476B", "#F0641E", "#1679C5", "#D87E99", "#8FCFC1", "#F7F4ED",
            "#80254C", "#FFB326", "#2C4E8C", "#D7DB64", "#54415D", "#181B22",
        ),
    ),
    PainterPalettePreset(
        "botanical",
        "Botanical Study",
        "Natural · foliage and earth",
        (
            "#E8D9B5", "#BFC99A", "#84A46B", "#466B45", "#244333", "#172D25",
            "#E0A46D", "#A96742", "#70422F", "#C6A76B", "#798B5B", "#354D39",
        ),
    ),
    PainterPalettePreset(
        "cinematic_night",
        "Cinematic Night",
        "Cool shadows · warm light",
        (
            "#101A2A", "#1D2D46", "#2D4961", "#3D6C78", "#68A1A2", "#C0D4C8",
            "#482E3D", "#7B3B3A", "#B5583C", "#E58B4D", "#F3C878", "#F1E4C2",
        ),
    ),
)


def _qcolors(values: tuple[str, ...]) -> tuple[QColor, ...]:
    return tuple(QColor(value) for value in values)


class PainterColorDisc(QWidget):
    """Procreate-style hue/saturation disc with harmony companion markers."""

    colorChanged = Signal(QColor)
    DISPLAY_SIZE = 360
    MIN_DISPLAY_SIZE = 110

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterColorDisc")
        self._color = QColor("#FF4D16")
        self._harmony = "complementary"
        self._display_size = self.DISPLAY_SIZE
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.set_display_size(self.DISPLAY_SIZE)

    def sizeHint(self) -> QSize:
        return QSize(self._display_size, self._display_size)

    def set_display_size(self, size: int) -> None:
        self._display_size = max(self.MIN_DISPLAY_SIZE, min(self.DISPLAY_SIZE, int(size)))
        self.setFixedSize(self._display_size, self._display_size)
        self.update()

    def set_color(self, color: QColor) -> None:
        value = QColor(color)
        if value.isValid() and value != self._color:
            self._color = value
            self.update()

    def set_harmony(self, mode: str) -> None:
        normalized = str(mode or "full").strip().lower()
        if normalized != self._harmony:
            self._harmony = normalized
            self.update()

    def _disc_geometry(self) -> tuple[QPointF, float]:
        side = min(self.width(), self.height())
        return QPointF(self.width() / 2.0, self.height() / 2.0), max(1.0, side / 2.0 - 9.0)

    def _marker_point(self, hue: float, saturation: float) -> QPointF:
        center, radius = self._disc_geometry()
        angle = math.radians(-float(hue))
        distance = radius * max(0.0, min(1.0, float(saturation)))
        return QPointF(
            center.x() + math.cos(angle) * distance,
            center.y() + math.sin(angle) * distance,
        )

    def _companion_hues(self, hue: float) -> tuple[float, ...]:
        offsets = {
            "complementary": (180.0,),
            "split_complementary": (150.0, 210.0),
            "analogous": (-30.0, 30.0),
            "triadic": (120.0, 240.0),
            "tetradic": (90.0, 180.0, 270.0),
        }.get(self._harmony, ())
        return tuple((hue + offset) % 360.0 for offset in offsets)

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center, radius = self._disc_geometry()
        disc = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2.0,
            radius * 2.0,
        )
        hue = QConicalGradient(center, 0.0)
        hue.setColorAt(0.000, QColor("#FF0000"))
        hue.setColorAt(0.167, QColor("#FFFF00"))
        hue.setColorAt(0.333, QColor("#00FF00"))
        hue.setColorAt(0.500, QColor("#00FFFF"))
        hue.setColorAt(0.667, QColor("#0000FF"))
        hue.setColorAt(0.833, QColor("#FF00FF"))
        hue.setColorAt(1.000, QColor("#FF0000"))
        painter.setPen(QPen(QColor(255, 255, 255, 24), 1))
        painter.setBrush(hue)
        painter.drawEllipse(disc)

        saturation = QRadialGradient(center, radius)
        saturation.setColorAt(0.0, QColor(255, 255, 255, 255))
        saturation.setColorAt(0.55, QColor(255, 255, 255, 90))
        saturation.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(saturation)
        painter.drawEllipse(disc)

        current_hue = self._color.hueF()
        current_hue = 0.0 if current_hue < 0 else current_hue * 360.0
        current_sat = self._color.saturationF()
        for companion_hue in self._companion_hues(current_hue):
            point = self._marker_point(companion_hue, max(0.58, current_sat))
            companion = QColor.fromHsvF(companion_hue / 360.0, max(0.58, current_sat), 1.0)
            shadow_point = QPointF(point.x() + 2.0, point.y() + 3.0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 125))
            painter.drawEllipse(shadow_point, 9.0, 9.0)
            painter.setPen(QPen(QColor("#ECECEC"), 1.4))
            painter.setBrush(companion)
            painter.drawEllipse(point, 7.0, 7.0)

        point = self._marker_point(current_hue, current_sat)
        shadow_point = QPointF(point.x() + 2.5, point.y() + 3.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 150))
        painter.drawEllipse(shadow_point, 13.0, 13.0)
        painter.setPen(QPen(QColor(255, 255, 255, 65), 1.0))
        painter.setBrush(QColor(0, 0, 0, 35))
        painter.drawEllipse(point, 12.0, 12.0)
        painter.setPen(QPen(QColor("#F4F4F4"), 2.0))
        painter.setBrush(self._color)
        painter.drawEllipse(point, 10.0, 10.0)
        painter.setPen(QPen(QColor(0, 0, 0, 100), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(point, 8.0, 8.0)

    def _select_at(self, position: QPointF) -> None:
        center, radius = self._disc_geometry()
        dx = position.x() - center.x()
        dy = position.y() - center.y()
        distance = math.hypot(dx, dy)
        saturation = max(0.0, min(1.0, distance / radius))
        hue = (-math.degrees(math.atan2(dy, dx))) % 360.0
        value = max(0.12, self._color.valueF())
        color = QColor.fromHsvF(hue / 360.0, saturation, value)
        self.set_color(color)
        self.colorChanged.emit(QColor(color))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._select_at(event.position())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._select_at(event.position())
            event.accept()
            return
        super().mouseMoveEvent(event)


class _PainterPresetDaub(QPushButton):
    """Interactive paint-daub swatch used by preset cards."""

    def __init__(
        self,
        color: QColor,
        parent: QWidget | None = None,
        *,
        relief: bool = False,
    ) -> None:
        super().__init__(parent)
        self._daub_color = QColor(color)
        self._relief = bool(relief)
        self.setObjectName("PainterPresetDaub")
        self.setMinimumSize(32, 38)
        self.setMaximumHeight(48)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton#PainterPresetDaub {"
            "background:transparent; border:0; padding:0;"
            "}"
        )

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bounds = QRectF(self.rect()).adjusted(3.0, 3.0, -3.0, -3.0)
        if self._relief:
            self._paint_palette_knife_daub(painter, bounds)
            return
        center = bounds.center()
        rx = bounds.width() * 0.48
        ry = bounds.height() * 0.46
        path = QPainterPath()
        points: list[QPointF] = []
        for index in range(18):
            angle = math.tau * index / 18.0
            variation = 1.0 + 0.055 * math.sin(index * 2.7 + self._daub_color.hueF() * 5.0)
            points.append(
                QPointF(
                    center.x() + math.cos(angle) * rx * variation,
                    center.y() + math.sin(angle) * ry * variation,
                )
            )
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._daub_color)
        painter.drawPath(path)

        highlight = QColor(self._daub_color).lighter(145)
        highlight.setAlpha(105 if self.underMouse() else 70)
        painter.setPen(QPen(highlight, 1.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(
            bounds.adjusted(3.0, 3.0, -3.0, -3.0),
            205 * 16,
            70 * 16,
        )
        if self.underMouse() or self.hasFocus():
            painter.setPen(QPen(QColor("#171717"), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(bounds.adjusted(0.5, 0.5, -0.5, -0.5))

    def _paint_palette_knife_daub(self, painter: QPainter, bounds: QRectF) -> None:
        """Paint a thick, directional knife smear rather than a flat color badge."""
        x, y, w, h = bounds.x(), bounds.y(), bounds.width(), bounds.height()
        phase = max(0.0, self._daub_color.hueF()) * math.tau
        top_a = math.sin(phase + 0.8) * 1.5
        top_b = math.sin(phase + 2.3) * 1.3
        bottom_a = math.cos(phase + 0.4) * 1.4
        body = QPainterPath()
        body.moveTo(x + 2.0, y + h * 0.34)
        body.cubicTo(
            x + w * 0.10,
            y + 2.0 + top_a,
            x + w * 0.30,
            y + 4.0 - top_a,
            x + w * 0.46,
            y + 2.5 + top_b,
        )
        body.cubicTo(
            x + w * 0.66,
            y + 1.0 - top_b,
            x + w * 0.87,
            y + 5.0 + top_a,
            x + w - 1.0,
            y + h * 0.31,
        )
        body.lineTo(x + w - 4.0, y + h * 0.78)
        body.cubicTo(
            x + w * 0.80,
            y + h - 1.0 - bottom_a,
            x + w * 0.60,
            y + h - 4.0 + bottom_a,
            x + w * 0.43,
            y + h - 2.0,
        )
        body.cubicTo(
            x + w * 0.25,
            y + h - 0.5 + bottom_a,
            x + w * 0.08,
            y + h - 5.0 - bottom_a,
            x + 1.0,
            y + h * 0.69,
        )
        body.closeSubpath()

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(24, 16, 12, 82))
        painter.drawPath(body.translated(2.2, 3.0))

        under_edge = QColor(self._daub_color).darker(158)
        painter.setBrush(under_edge)
        painter.drawPath(body.translated(0.5, 1.5))
        gradient = QLinearGradient(x, y, x, y + h)
        gradient.setColorAt(0.0, QColor(self._daub_color).lighter(128))
        gradient.setColorAt(0.38, self._daub_color)
        gradient.setColorAt(1.0, QColor(self._daub_color).darker(118))
        painter.setBrush(gradient)
        painter.drawPath(body)

        light = QColor(self._daub_color).lighter(178)
        light.setAlpha(185 if self.underMouse() else 145)
        dark = QColor(self._daub_color).darker(170)
        dark.setAlpha(150)
        ridge_top = QPainterPath()
        ridge_top.moveTo(x + w * 0.10, y + h * 0.35)
        ridge_top.cubicTo(
            x + w * 0.28,
            y + h * 0.18,
            x + w * 0.54,
            y + h * 0.25,
            x + w * 0.88,
            y + h * 0.31,
        )
        painter.setPen(
            QPen(light, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawPath(ridge_top)

        groove = QPainterPath()
        groove.moveTo(x + w * 0.08, y + h * 0.59)
        groove.cubicTo(
            x + w * 0.30,
            y + h * 0.48,
            x + w * 0.57,
            y + h * 0.62,
            x + w * 0.90,
            y + h * 0.50,
        )
        painter.setPen(
            QPen(dark, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawPath(groove)

        scrape = QColor(self._daub_color).lighter(190)
        scrape.setAlpha(115)
        painter.setPen(
            QPen(scrape, 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        for ratio, lift in ((0.30, 0.0), (0.48, 1.4), (0.68, -0.8)):
            sx = x + w * ratio
            painter.drawLine(
                QPointF(sx, y + h * 0.32 + lift),
                QPointF(sx + w * 0.12, y + h * 0.43 + lift),
            )

        if self.underMouse() or self.hasFocus():
            painter.setPen(QPen(QColor("#171717"), 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(body)


class PainterPresetBoard(QWidget):
    colorSelected = Signal(QColor)
    presetSelected = Signal(str, object)
    materialPresetSelected = Signal(str, object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterPresetBoard")
        self._active_key = PAINTER_PALETTE_PRESETS[0].key
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        heading = QLabel("Palette Presets")
        heading.setObjectName("PaintColorBoardHeading")
        root.addWidget(heading)
        heading.hide()
        subtitle = QLabel("Choose a pack, then paint with any swatch.")
        subtitle.setObjectName("PaintColorBoardSubtitle")
        root.addWidget(subtitle)
        subtitle.hide()

        scroll = QScrollArea()
        scroll.setObjectName("PainterPresetScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        cards = QVBoxLayout(host)
        cards.setContentsMargins(5, 5, 9, 8)
        cards.setSpacing(12)
        self._cards: dict[str, QFrame] = {}
        self._swatch_buttons: list[QPushButton] = []
        for preset in PAINTER_PALETTE_PRESETS:
            card = self._make_card(preset)
            cards.addWidget(card)
            self._cards[preset.key] = card
        cards.addStretch(1)
        scroll.setWidget(host)
        root.addWidget(scroll)
        self._refresh_cards()

    def presets(self) -> tuple[PainterPalettePreset, ...]:
        return PAINTER_PALETTE_PRESETS

    def select_preset(self, key: str) -> None:
        preset = next((item for item in PAINTER_PALETTE_PRESETS if item.key == key), None)
        if preset is None:
            return
        self._active_key = preset.key
        self._refresh_cards()
        self.presetSelected.emit(preset.name, _qcolors(preset.colors))

    def _make_card(self, preset: PainterPalettePreset) -> QFrame:
        card = QFrame()
        card.setObjectName("PainterPalettePresetCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 13)
        layout.setSpacing(4)
        header = QPushButton(preset.name)
        header.setObjectName("PainterPalettePresetHeader")
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(
            "QPushButton#PainterPalettePresetHeader {"
            "background:transparent; border:0; color:#241F1B;"
            "font-family:'Georgia'; font-size:18px; font-style:italic;"
            "font-weight:600; padding:0 2px 1px 2px;"
            "}"
            "QPushButton#PainterPalettePresetHeader:hover { color:#A55332; }"
        )
        header.clicked.connect(lambda _checked=False, key=preset.key: self.select_preset(key))
        layout.addWidget(header)
        meta = QLabel(f"{len(preset.colors)} Colors · {preset.subtitle}")
        meta.setObjectName("PaintColorBoardSubtitle")
        meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        meta.setStyleSheet(
            "QLabel {"
            "background:transparent; color:#756A61; border:0;"
            "font-size:8px; padding:0 0 5px 0;"
            "}"
        )
        layout.addWidget(meta)
        if preset.material_profile:
            badge = QLabel("HEIGHT  ·  NORMAL  ·  ROUGHNESS")
            badge.setObjectName("PainterMaterialPresetBadge")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                "QLabel {"
                "background:#24201D; color:#F1D7AA; border-radius:6px;"
                "font-size:8px; font-weight:700; padding:3px 5px;"
                "}"
            )
            layout.addWidget(badge)
        grid = QGridLayout()
        grid.setContentsMargins(0, 3, 0, 0)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(3)
        for index, value in enumerate(preset.colors):
            color = QColor(value)
            button = _PainterPresetDaub(
                color,
                relief=bool(preset.material_profile),
            )
            button.setObjectName("PainterPresetSwatch")
            button.setFixedHeight(44)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"{preset.name} · {color.name().upper()}")
            button.clicked.connect(
                lambda _checked=False, c=QColor(color), key=preset.key: self._choose_color(key, c)
            )
            columns = max(1, int(preset.columns))
            grid.addWidget(button, index // columns, index % columns)
            grid.setColumnStretch(index % columns, 1)
            self._swatch_buttons.append(button)
        layout.addLayout(grid)
        return card

    def _choose_color(self, key: str, color: QColor) -> None:
        if key != self._active_key:
            self.select_preset(key)
        preset = next((item for item in PAINTER_PALETTE_PRESETS if item.key == key), None)
        if preset is not None and preset.material_profile:
            self.materialPresetSelected.emit(
                preset.name,
                dict(preset.material_profile),
                preset.recommended_brush_style,
            )
        self.colorSelected.emit(QColor(color))

    def _refresh_cards(self) -> None:
        for key, card in self._cards.items():
            active = key == self._active_key
            card.setProperty("active", active)
            card.setStyleSheet(
                "QFrame#PainterPalettePresetCard {"
                "background:#FAF8F3;"
                f"border:{'2px solid #D17B51' if active else '1px solid #D8D1C8'};"
                "border-radius:10px;"
                "}"
            )
