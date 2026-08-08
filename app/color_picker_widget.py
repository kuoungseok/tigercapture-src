"""Small reusable color-picker controls for Tiger Studio authoring surfaces."""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

DEFAULT_BOARD_PALETTE = (
    "#FFF7ED",
    "#FFE0C2",
    "#F59E0B",
    "#EC4899",
    "#8B5CF6",
    "#4C74DB",
    "#3F8FBA",
    "#10B981",
    "#334155",
    "#111827",
)


def normalized_color_text(
    value: object,
    *,
    fallback: str = "#FFFFFFFF",
    include_alpha: bool = True,
) -> str:
    color = QColor(str(value or ""))
    if not color.isValid():
        color = QColor(fallback)
    if not color.isValid():
        color = QColor("#FFFFFFFF")
    return color.name(QColor.HexArgb if include_alpha else QColor.HexRgb).upper()


class ColorPickerButton(QPushButton):
    """Compact swatch button backed by Qt's color picker."""

    color_selected = Signal(str)

    def __init__(
        self,
        color: str = "#FFFFFFFF",
        parent: QWidget | None = None,
        *,
        title: str = "Choose color",
        include_alpha: bool = True,
        presentation: str = "compact",
    ) -> None:
        super().__init__(parent)
        self._title = str(title)
        self._include_alpha = bool(include_alpha)
        self._presentation = str(presentation or "compact").strip().casefold()
        self._color = normalized_color_text(
            color,
            include_alpha=self._include_alpha,
        )
        self.setObjectName("TigerColorPickerButton")
        self.setFixedSize(
            QSize(64, 68)
            if self._presentation == "portrait"
            else QSize(30, 24)
        )
        self.clicked.connect(self.open_picker)
        self._refresh_swatch()

    def color(self) -> str:
        return self._color

    def set_color(self, value: object) -> None:
        candidate = QColor(str(value or ""))
        if not candidate.isValid():
            return
        self._color = normalized_color_text(
            candidate.name(QColor.HexArgb),
            include_alpha=self._include_alpha,
        )
        self._refresh_swatch()

    def choose_color(self, value: object) -> bool:
        """Apply a valid color and emit it; also supports deterministic UI tests."""
        candidate = QColor(str(value or ""))
        if not candidate.isValid():
            return False
        self.set_color(candidate.name(QColor.HexArgb))
        self.color_selected.emit(self._color)
        return True

    def open_picker(self) -> None:
        options = (
            QColorDialog.ShowAlphaChannel
            if self._include_alpha
            else QColorDialog.ColorDialogOption(0)
        )
        chosen = QColorDialog.getColor(
            QColor(self._color),
            self,
            self._title,
            options,
        )
        if chosen.isValid():
            self.choose_color(chosen.name(QColor.HexArgb))

    def _refresh_swatch(self) -> None:
        color = QColor(self._color)
        opaque = QColor(color)
        opaque.setAlpha(255)
        border = "#F3F6FA" if opaque.lightnessF() < 0.42 else "#232831"
        self.setText("")
        self.setToolTip(f"{self._title}: {self._color}")
        if self._presentation == "portrait":
            self.setStyleSheet(
                "QPushButton#TigerColorPickerButton {"
                "background:transparent; border:0; padding:0;"
                "}"
            )
            self.update()
            return
        self.setStyleSheet(
            "QPushButton#TigerColorPickerButton {"
            f"background-color: {opaque.name(QColor.HexRgb)};"
            f"border: 2px solid {border};"
            "border-radius: 5px;"
            "padding: 0;"
            "}"
            "QPushButton#TigerColorPickerButton:hover {"
            "border-color: #72A7FF;"
            "}"
        )

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        if self._presentation != "portrait":
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_portrait_swatch(
            painter,
            QRectF(self.rect()).adjusted(2, 2, -2, -2),
            QColor(self._color),
            selected=self.hasFocus(),
            hovered=self.underMouse(),
        )


def _paint_portrait_swatch(
    painter: QPainter,
    rect: QRectF,
    color: QColor,
    *,
    selected: bool,
    hovered: bool,
) -> None:
    shadow = QRectF(rect).translated(1.5, 2.0)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 42))
    painter.drawRoundedRect(shadow, 3.0, 3.0)
    painter.setPen(
        QPen(
            QColor("#72A7FF") if (selected or hovered) else QColor("#D8D2C8"),
            2.0 if selected else 1.0,
        )
    )
    painter.setBrush(QColor("#FFFDF8"))
    painter.drawRoundedRect(rect, 3.0, 3.0)

    swatch = rect.adjusted(4.0, 4.0, -4.0, -16.0)
    opaque = QColor(color)
    opaque.setAlpha(255)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(opaque)
    painter.drawRect(swatch)
    code_font = painter.font()
    code_font.setPixelSize(7)
    code_font.setBold(False)
    painter.setFont(code_font)
    painter.setPen(QColor("#111111"))
    painter.drawText(
        QRectF(
            rect.left() + 2.0,
            rect.bottom() - 12.0,
            rect.width() - 4.0,
            9.0,
        ),
        Qt.AlignmentFlag.AlignCenter,
        opaque.name(QColor.HexRgb).upper(),
    )


class _PortraitPaletteSwatch(QPushButton):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._portrait_color = QColor(color)
        self._portrait_selected = False
        self.setObjectName("TigerPortraitPaletteSwatch")
        self.setFixedSize(64, 68)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton#TigerPortraitPaletteSwatch {"
            "background:transparent; border:0; padding:0;"
            "}"
        )

    def set_portrait_state(self, color: QColor, *, selected: bool) -> None:
        self._portrait_color = QColor(color)
        self._portrait_selected = bool(selected)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_portrait_swatch(
            painter,
            QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5),
            self._portrait_color,
            selected=self._portrait_selected,
            hovered=self.underMouse(),
        )


class ColorPaletteStrip(QWidget):
    """Always-visible compact swatches shared by authoring boards."""

    color_selected = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        colors: tuple[str, ...] | list[str] | None = None,
        maximum_colors: int = 8,
        presentation: str = "compact",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TigerColorPaletteStrip")
        self._buttons: list[QPushButton] = []
        self._current = ""
        self._maximum_colors = max(1, int(maximum_colors))
        self._presentation = str(presentation or "compact").strip().casefold()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        self.set_colors(colors or DEFAULT_BOARD_PALETTE)

    def colors(self) -> list[str]:
        return [
            str(button.property("tigerColor") or "")
            for button in self._buttons
        ]

    def set_colors(self, colors: tuple[str, ...] | list[str]) -> None:
        while self._buttons:
            button = self._buttons.pop()
            self._layout.removeWidget(button)
            button.deleteLater()
        normalized: list[str] = []
        for value in colors:
            candidate = normalized_color_text(value)
            if candidate not in normalized:
                normalized.append(candidate)
            if len(normalized) >= self._maximum_colors:
                break
        for value in normalized:
            button = (
                _PortraitPaletteSwatch(value, self)
                if self._presentation == "portrait"
                else QPushButton(self)
            )
            button.setObjectName("TigerColorPaletteSwatch")
            button.setProperty("tigerColor", value)
            if self._presentation != "portrait":
                button.setFixedSize(24, 24)
            button.setToolTip(value)
            button.clicked.connect(
                lambda _checked=False, color=value: self.choose_color(color)
            )
            self._layout.addWidget(button)
            self._buttons.append(button)
        self._refresh_selection()

    def choose_color(self, value: object) -> bool:
        candidate = QColor(str(value or ""))
        if not candidate.isValid():
            return False
        self._current = normalized_color_text(candidate.name(QColor.HexArgb))
        self._refresh_selection()
        self.color_selected.emit(self._current)
        return True

    def set_current_color(self, value: object) -> None:
        candidate = QColor(str(value or ""))
        if not candidate.isValid():
            return
        self._current = normalized_color_text(candidate.name(QColor.HexArgb))
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        for button in self._buttons:
            value = str(button.property("tigerColor") or "")
            color = QColor(value)
            opaque = QColor(color)
            opaque.setAlpha(255)
            selected = value == self._current
            if isinstance(button, _PortraitPaletteSwatch):
                button.set_portrait_state(opaque, selected=selected)
                continue
            border = "#FFFFFF" if selected else "#596273"
            width = 3 if selected else 1
            button.setStyleSheet(
                "QPushButton#TigerColorPaletteSwatch {"
                f"background-color: {opaque.name(QColor.HexRgb)};"
                f"border: {width}px solid {border};"
                "border-radius: 5px;"
                "padding: 0;"
                "}"
                "QPushButton#TigerColorPaletteSwatch:hover {"
                "border: 2px solid #72A7FF;"
                "}"
            )


def color_edit_with_picker(
    edit: QLineEdit,
    *,
    title: str,
    include_alpha: bool = True,
    parent: QWidget | None = None,
) -> tuple[QFrame, ColorPickerButton]:
    """Place an existing color edit and a synchronized picker in one field."""
    field = QFrame(parent)
    field.setObjectName("TigerColorPickerField")
    layout = QHBoxLayout(field)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    picker = ColorPickerButton(
        edit.text() or "#FFFFFFFF",
        field,
        title=title,
        include_alpha=include_alpha,
    )
    layout.addWidget(edit, 1)
    layout.addWidget(picker)

    def apply_selected(value: str) -> None:
        edit.setText(value)
        edit.editingFinished.emit()

    picker.color_selected.connect(apply_selected)
    edit.textChanged.connect(picker.set_color)
    return field, picker


__all__ = [
    "ColorPickerButton",
    "ColorPaletteStrip",
    "DEFAULT_BOARD_PALETTE",
    "color_edit_with_picker",
    "normalized_color_text",
]
