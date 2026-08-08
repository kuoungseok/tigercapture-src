"""Shared Figma-style fill editor used by every Painter UI inspector."""
from __future__ import annotations

import colorsys
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMenu,
)

from app.painter_ui_advanced_appearance import normalize_ui_paint


FILL_TYPES = (
    ("solid", "▣", "단색"),
    ("linear", "⠿", "그라디언트"),
    ("pattern", "▦", "패턴"),
    ("image", "▧", "이미지"),
    ("video", "▻", "동영상"),
    ("shader", "≋", "셰이더 채우기"),
)

BLEND_MODES = (
    ("일반", "normal"), ("어둡게", "darken"), ("곱하기", "multiply"),
    ("더 어둡게", "color_burn"), ("색상 번", "linear_burn"),
    ("밝게", "lighten"), ("화면", "screen"), ("더 밝게", "linear_dodge"),
    ("컬러 닷지", "color_dodge"), ("오버레이", "overlay"),
    ("소프트 라이트", "soft_light"), ("하드 라이트", "hard_light"),
    ("차이", "difference"), ("제외", "exclusion"), ("색조", "hue"),
    ("채도", "saturation"), ("색상", "color"), ("광도", "luminosity"),
)


def _hex_color(text: str, fallback: str = "#FFFFFFFF") -> QColor:
    value = str(text or fallback).strip()
    if not value.startswith("#"):
        value = "#" + value
    raw = value[1:]
    if len(raw) == 6:
        raw += "FF"
    if len(raw) == 8:
        try:
            return QColor(
                int(raw[0:2], 16), int(raw[2:4], 16),
                int(raw[4:6], 16), int(raw[6:8], 16),
            )
        except ValueError:
            pass
    return _hex_color(fallback, "#FFFFFFFF") if value.upper() != fallback.upper() else QColor(255, 255, 255)


def _rgba_hex(color: QColor) -> str:
    return "#{:02X}{:02X}{:02X}{:02X}".format(
        color.red(), color.green(), color.blue(), color.alpha()
    )


class _ColorPlane(QWidget):
    color_changed = Signal(QColor)

    def __init__(self, color: QColor, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 290)
        self.setObjectName("PainterUIColorPlane")
        self._hue = color.hsvHueF() if color.hsvHueF() >= 0 else 0.0
        self._sat = color.hsvSaturationF()
        self._val = color.valueF()

    def color(self) -> QColor:
        return QColor.fromHsvF(self._hue, self._sat, self._val)

    def set_color(self, color: QColor) -> None:
        hue = color.hsvHueF()
        self._hue = hue if hue >= 0 else self._hue
        self._sat = color.hsvSaturationF()
        self._val = color.valueF()
        self.update()

    def set_hue(self, hue: float) -> None:
        self._hue = max(0.0, min(1.0, hue))
        self.update()

    def _pick(self, pos: QPointF) -> None:
        self._sat = max(0.0, min(1.0, pos.x() / max(1, self.width())))
        self._val = 1.0 - max(0.0, min(1.0, pos.y() / max(1, self.height())))
        self.update()
        self.color_changed.emit(self.color())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._pick(event.position())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        hue = QColor.fromHsvF(self._hue, 1.0, 1.0)
        horizontal = QLinearGradient(rect.topLeft(), rect.topRight())
        horizontal.setColorAt(0, Qt.GlobalColor.white)
        horizontal.setColorAt(1, hue)
        painter.fillRect(rect, horizontal)
        vertical = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        vertical.setColorAt(0, QColor(0, 0, 0, 0))
        vertical.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(rect, vertical)
        point = QPointF(rect.left() + self._sat * rect.width(), rect.bottom() - self._val * rect.height())
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(point, 6, 6)


class _TrackSlider(QSlider):
    """Figma-like pill track with a crisp circular handle."""

    def __init__(self, orientation=Qt.Orientation.Horizontal, parent=None) -> None:
        super().__init__(orientation, parent)
        self.setFixedHeight(24)
        self.setMouseTracking(True)

    def _track_rect(self) -> QRectF:
        return QRectF(2, 5, max(1, self.width() - 4), 14)

    def _ratio(self) -> float:
        span = self.maximum() - self.minimum()
        return (self.value() - self.minimum()) / span if span else 0.0

    def _set_from_x(self, x: float) -> None:
        ratio = max(0.0, min(1.0, (x - 2) / max(1.0, self.width() - 4)))
        self.setValue(round(self.minimum() + ratio * (self.maximum() - self.minimum())))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._set_from_x(event.position().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._set_from_x(event.position().x())

    def _paint_track(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(QColor("#C8C8C8"), 1))
        painter.setBrush(QColor("#F7F7F7"))
        painter.drawRoundedRect(rect, 7, 7)

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._track_rect()
        self._paint_track(painter, rect)
        x = rect.left() + rect.width() * self._ratio()
        center = QPointF(x, rect.center().y())
        painter.setPen(QPen(QColor("#8FB7D5"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawEllipse(center, 10, 10)


class _HueSlider(_TrackSlider):
    def _paint_track(self, painter: QPainter, rect: QRectF) -> None:
        gradient = QLinearGradient(rect.topLeft(), rect.topRight())
        for index in range(7):
            gradient.setColorAt(index / 6, QColor.fromHsvF(index / 6, 1.0, 1.0))
        painter.setPen(QPen(QColor("#C8C8C8"), 1))
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 7, 7)


class _AlphaSlider(_TrackSlider):
    def __init__(self, color: QColor, parent=None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._color = QColor(color)

    def set_base_color(self, color: QColor) -> None:
        self._color = QColor(color)
        self.update()

    def _paint_track(self, painter: QPainter, rect: QRectF) -> None:
        painter.save()
        painter.setClipPath(self._rounded_path(rect))
        cell = 7
        for y in range(int(rect.top()), int(rect.bottom()) + cell, cell):
            for x in range(int(rect.left()), int(rect.right()) + cell, cell):
                shade = 225 if ((x // cell) + (y // cell)) % 2 else 248
                painter.fillRect(x, y, cell, cell, QColor(shade, shade, shade))
        start = QColor(self._color); start.setAlpha(0)
        end = QColor(self._color); end.setAlpha(255)
        gradient = QLinearGradient(rect.topLeft(), rect.topRight())
        gradient.setColorAt(0, start); gradient.setColorAt(1, end)
        painter.fillRect(rect, gradient)
        painter.restore()
        painter.setPen(QPen(QColor("#C8C8C8"), 1)); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 7, 7)

    @staticmethod
    def _rounded_path(rect: QRectF):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath(); path.addRoundedRect(rect, 7, 7); return path


class _CheckerPreview(QFrame):
    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(parent)
        self._text = text
        self._pixmap = QPixmap()
        self.setMinimumHeight(210)
        self.setObjectName("PainterUICheckerPreview")

    def set_text(self, text: str) -> None:
        self._text = text
        self.update()

    def set_source(self, path: str) -> None:
        self._pixmap = QPixmap(path) if path else QPixmap()
        self._text = Path(path).name if path else self._text
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        size = 18
        for y in range(0, self.height(), size):
            for x in range(0, self.width(), size):
                value = 232 if ((x // size) + (y // size)) % 2 else 248
                painter.fillRect(x, y, size, size, QColor(value, value, value))
        painter.setPen(QColor("#343434"))
        if not self._pixmap.isNull():
            target = self._pixmap.scaled(
                self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                (self.width() - target.width()) // 2,
                (self.height() - target.height()) // 2,
                target,
            )
        else:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._text)


class PainterUIFillComponent(QFrame):
    """Reusable fill surface. It owns UI state but never mutates a document."""

    paint_changed = Signal(object)
    close_requested = Signal()
    fill_type_changed = Signal(str)

    def __init__(self, paint: Mapping[str, Any], *, stroke: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIFillComponent")
        self._stroke = bool(stroke)
        self._source = normalize_ui_paint(paint, stroke=stroke)
        self._active_type = str(self._source.get("type") or "solid")
        self._build()
        self.set_paint(self._source)

    def _build(self) -> None:
        self.setStyleSheet(
            """
            QFrame#PainterUIFillComponent { background:#FFFFFF; color:#171717; border:1px solid #D9D9D9; border-radius:14px; }
            QLabel { color:#171717; border:none; }
            QComboBox, QLineEdit { background:#F5F5F5; color:#171717; border:1px solid #E5E5E5; border-radius:7px; min-height:32px; padding:0 9px; }
            QToolButton, QPushButton { background:transparent; color:#171717; border:none; border-radius:7px; min-height:32px; padding:0 8px; }
            QToolButton:hover, QPushButton:hover { background:#F0F0F0; }
            QToolButton:checked { background:#F1F1F1; color:#111111; }
            QSlider::groove:horizontal { height:10px; background:#EFEFEF; border:1px solid #CFCFCF; border-radius:5px; }
            QSlider::handle:horizontal { width:20px; margin:-6px 0; background:#FFFFFF; border:1px solid #9CB9D0; border-radius:10px; }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        custom = QLabel("사용자 지정")
        custom.setStyleSheet("background:#F1F1F1; border-radius:7px; padding:7px 10px; font-weight:600;")
        header.addWidget(custom)
        library = QLabel("라이브러리")
        library.setStyleSheet("color:#8B8B8B; padding:7px 6px;")
        header.addWidget(library)
        header.addStretch(1)
        add = QToolButton(); add.setText("+"); add.setToolTip("스타일 추가")
        header.addWidget(add)
        close = QToolButton(); close.setText("×"); close.setToolTip("닫기")
        close.clicked.connect(self.close_requested)
        header.addWidget(close)
        root.addLayout(header)

        type_row = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        self.type_group.setExclusive(True)
        self.type_buttons: dict[str, QToolButton] = {}
        for index, (kind, icon, tooltip) in enumerate(FILL_TYPES):
            button = QToolButton()
            button.setText(icon)
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.setFixedSize(34, 34)
            button.clicked.connect(lambda _checked=False, k=kind: self.set_fill_type(k))
            self.type_group.addButton(button, index)
            self.type_buttons[kind] = button
            type_row.addWidget(button)
        type_row.addStretch(1)
        self.blend_button = QToolButton()
        self.blend_button.setText("◔")
        self.blend_button.setToolTip("혼합 모드")
        self.blend_button.clicked.connect(self._cycle_blend_menu)
        type_row.addWidget(self.blend_button)
        root.addLayout(type_row)

        self.pages = QStackedWidget()
        root.addWidget(self.pages)
        self._build_solid_page()
        self._build_gradient_page()
        self._build_pattern_page()
        self._build_image_page()
        self._build_video_page()
        self._build_shader_page()

        self.blend_combo = QComboBox()
        for label, key in BLEND_MODES:
            self.blend_combo.addItem(label, key)
        self.blend_combo.currentIndexChanged.connect(self._emit_change)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.valueChanged.connect(self._emit_change)
        self.opacity_label = QLabel("100%")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        self.blend_combo.hide()
        self.opacity_slider.hide()
        self.opacity_label.hide()

    def _build_solid_page(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 8, 8, 8); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.color_plane = _ColorPlane(QColor("#D9D9D9"))
        self.color_plane.color_changed.connect(self._plane_changed)
        layout.addWidget(self.color_plane)
        self.hue_slider = _HueSlider(Qt.Orientation.Horizontal)
        self.hue_slider.setRange(0, 359)
        self.hue_slider.valueChanged.connect(self._hue_changed)
        layout.addWidget(self.hue_slider)
        self.alpha_slider = _AlphaSlider(QColor("#D9D9D9"))
        self.alpha_slider.setRange(0, 100)
        self.alpha_slider.valueChanged.connect(self._color_fields_changed)
        layout.addWidget(self.alpha_slider)
        row = QHBoxLayout()
        self.color_format = QComboBox(); self.color_format.addItems(["Hex", "RGB", "HSL"])
        row.addWidget(self.color_format)
        self.color_edit = QLineEdit(); self.color_edit.setPlaceholderText("D9D9D9")
        self.color_edit.editingFinished.connect(self._color_edit_changed)
        row.addWidget(self.color_edit, 1)
        self.color_opacity = QLineEdit("100"); self.color_opacity.setFixedWidth(58)
        self.color_opacity.editingFinished.connect(self._color_opacity_changed)
        row.addWidget(self.color_opacity)
        row.addWidget(QLabel("%"))
        layout.addLayout(row)
        source = QComboBox(); source.addItem("이 페이지에서")
        layout.addWidget(source)
        self.pages.addWidget(page)

    def _build_gradient_page(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 8, 8, 8); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        row = QHBoxLayout()
        self.gradient_kind = QComboBox()
        self.gradient_kind.addItem("선형", "linear"); self.gradient_kind.addItem("방사형", "radial")
        self.gradient_kind.currentIndexChanged.connect(self._gradient_kind_changed)
        row.addWidget(self.gradient_kind, 1)
        reverse = QToolButton(); reverse.setText("⇄"); reverse.setToolTip("그라디언트 반전")
        reverse.clicked.connect(self._reverse_gradient)
        row.addWidget(reverse)
        layout.addLayout(row)
        self.gradient_preview = QLabel()
        self.gradient_preview.setMinimumHeight(54)
        layout.addWidget(self.gradient_preview)
        layout.addWidget(QLabel("중지점"))
        self.stop_start_position = QLineEdit("0"); self.stop_start_color = QLineEdit("#FFFFFFFF")
        self.stop_end_position = QLineEdit("100"); self.stop_end_color = QLineEdit("#737373FF")
        for widgets in ((self.stop_start_position, self.stop_start_color), (self.stop_end_position, self.stop_end_color)):
            stop_row = QHBoxLayout(); stop_row.addWidget(widgets[0]); stop_row.addWidget(QLabel("%")); stop_row.addWidget(widgets[1], 1)
            layout.addLayout(stop_row)
            widgets[0].editingFinished.connect(self._refresh_gradient)
            widgets[1].editingFinished.connect(self._refresh_gradient)
        layout.addStretch(1)
        self.pages.addWidget(page)

    def _build_pattern_page(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 8, 8, 8); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.pattern_preview = _CheckerPreview("소스 선택…")
        self.pattern_preview.setMinimumHeight(180)
        layout.addWidget(self.pattern_preview)
        self.pattern_kind = QComboBox()
        for label, key in (("점", "dots"), ("격자", "grid"), ("줄무늬", "stripes"), ("체커", "checker")):
            self.pattern_kind.addItem(label, key)
        layout.addWidget(self.pattern_kind)
        tile_row = QHBoxLayout(); tile_row.addWidget(QLabel("타일 유형"))
        self.pattern_tile_group = QButtonGroup(self); self.pattern_tile_group.setExclusive(True)
        self.pattern_tile_buttons: dict[str, QToolButton] = {}
        for index, (label, key) in enumerate((("⠿", "grid"), ("∷", "offset"))):
            button = QToolButton(); button.setText(label); button.setCheckable(True); button.setChecked(index == 0)
            self.pattern_tile_group.addButton(button, index); self.pattern_tile_buttons[key] = button; tile_row.addWidget(button)
        tile_row.addStretch(1); layout.addLayout(tile_row)
        grid = QGridLayout()
        self.pattern_scale = QLineEdit("100"); self.pattern_gap_x = QLineEdit("0"); self.pattern_gap_y = QLineEdit("0")
        self.pattern_foreground = QLineEdit("#C8D2E0FF"); self.pattern_background = QLineEdit("#FFFFFFFF")
        self.pattern_source = QLineEdit(); self.pattern_source.setPlaceholderText("캔버스 개체 ID")
        for row, (label, widget) in enumerate((("확대/축소", self.pattern_scale), ("간격 X", self.pattern_gap_x), ("간격 Y", self.pattern_gap_y), ("전경", self.pattern_foreground), ("배경", self.pattern_background), ("소스", self.pattern_source))):
            grid.addWidget(QLabel(label), row, 0); grid.addWidget(widget, row, 1)
        layout.addLayout(grid)
        align_row = QHBoxLayout(); align_row.addWidget(QLabel("정렬"))
        self.pattern_alignment_group = QButtonGroup(self); self.pattern_alignment_group.setExclusive(True)
        self.pattern_alignment_buttons: dict[str, QToolButton] = {}
        for index, key in enumerate(("top_left", "top", "top_right", "left", "center", "right", "bottom_left", "bottom", "bottom_right")):
            button = QToolButton(); button.setText("•"); button.setCheckable(True); button.setFixedSize(25, 25); button.setChecked(key == "top_left")
            self.pattern_alignment_group.addButton(button, index); self.pattern_alignment_buttons[key] = button; align_row.addWidget(button)
        layout.addLayout(align_row)
        self.pages.addWidget(page)

    def _media_header(self, layout: QVBoxLayout, kind: str) -> tuple[QComboBox, QLineEdit, _CheckerPreview]:
        row = QHBoxLayout()
        fit = QComboBox()
        for label, key in (("채우기", "fill"), ("맞추기", "fit"), ("자르기", "crop"), ("타일", "tile")):
            fit.addItem(label, key)
        row.addWidget(fit)
        row.addStretch(1)
        browse = QPushButton("컴퓨터에서 업로드")
        row.addWidget(browse)
        layout.addLayout(row)
        preview = _CheckerPreview("이미지를 선택하세요" if kind == "image" else "동영상을 선택하세요")
        preview.setMinimumHeight(300)
        layout.addWidget(preview)
        path = QLineEdit(); path.setPlaceholderText("소스 파일 경로")
        browse.clicked.connect(lambda: self._browse_media(kind, path, preview))
        layout.addWidget(path)
        return fit, path, preview

    def _build_image_page(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 8, 8, 8); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.image_fit, self.image_path, self.image_preview = self._media_header(layout, "image")
        create = QPushButton("▧  이미지 만들기")
        create.setToolTip("이미지 생성 도구는 별도 워크플로에서 연결됩니다")
        layout.addWidget(create)
        self.image_adjustments: dict[str, QSlider] = {}
        for label, key in (("노출", "exposure"), ("대비", "contrast"), ("채도", "saturation"), ("온도", "temperature"), ("색조", "tint"), ("하이라이트", "highlights")):
            row = QHBoxLayout(); row.addWidget(QLabel(label))
            slider = _TrackSlider(Qt.Orientation.Horizontal); slider.setRange(-100, 100); slider.setValue(0)
            row.addWidget(slider, 1); layout.addLayout(row); self.image_adjustments[key] = slider
        self.pages.addWidget(page)

    def _build_video_page(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 8, 8, 8); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.video_fit, self.video_path, self.video_preview = self._media_header(layout, "video")
        notice = QLabel("동영상 채우기는 Painter 미리보기에서 포스터로 표시되며 Unreal 내보내기에는 런타임 미디어 어댑터가 필요합니다.")
        notice.setWordWrap(True); notice.setStyleSheet("background:#F5F5F5; border-radius:8px; padding:12px; color:#555555;")
        layout.addWidget(notice)
        self.pages.addWidget(page)

    def _build_shader_page(self) -> None:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(8, 8, 8, 8); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        title = QLabel("셰이더 채우기  베타"); title.setStyleSheet("font-weight:650;")
        layout.addWidget(title)
        search = QLineEdit(); search.setPlaceholderText("검색"); layout.addWidget(search)
        self.shader_combo = QComboBox()
        for label, key in (("Mesh gradient", "mesh_gradient"), ("Water caustic", "water_caustic"), ("Star field", "star_field"), ("Clouds", "clouds")):
            self.shader_combo.addItem(label, key)
        layout.addWidget(self.shader_combo)
        notice = QLabel("셰이더는 Painter에서 미리보기 가능한 실험 기능입니다. Unreal 출력 전에는 UI Material 또는 결정적 베이크가 필요합니다.")
        notice.setWordWrap(True); notice.setStyleSheet("background:#F5F5F5; border-radius:8px; padding:12px; color:#555555;")
        layout.addWidget(notice); layout.addStretch(1)
        self.pages.addWidget(page)

    def set_fill_type(self, kind: str) -> None:
        kind = "linear" if kind == "radial" else str(kind)
        self._active_type = kind
        index = {"solid": 0, "linear": 1, "pattern": 2, "image": 3, "video": 4, "shader": 5}.get(kind, 0)
        self.pages.setCurrentIndex(index)
        if kind in self.type_buttons:
            self.type_buttons[kind].setChecked(True)
        self.fill_type_changed.emit(kind)
        self._emit_change()

    def set_paint(self, paint: Mapping[str, Any]) -> None:
        self._source = normalize_ui_paint(paint, stroke=self._stroke)
        kind = str(self._source.get("type") or "solid")
        self.set_fill_type(kind)
        color = _hex_color(str(self._source.get("color") or "#FFFFFFFF"))
        self.color_plane.set_color(color)
        self.alpha_slider.set_base_color(color)
        self.hue_slider.setValue(round(max(0.0, color.hsvHueF()) * 359))
        self.alpha_slider.setValue(round(color.alphaF() * 100))
        self.color_edit.setText(_rgba_hex(color)[1:7])
        self.color_opacity.setText(str(round(color.alphaF() * 100)))
        gradient = dict(self._source.get("gradient") or {})
        stops = list(gradient.get("stops") or [])
        if stops:
            self.stop_start_position.setText(str(round(float(stops[0].get("position", 0)) * 100)))
            self.stop_start_color.setText(str(stops[0].get("color") or "#FFFFFFFF"))
            self.stop_end_position.setText(str(round(float(stops[-1].get("position", 1)) * 100)))
            self.stop_end_color.setText(str(stops[-1].get("color") or "#737373FF"))
        self.gradient_kind.setCurrentIndex(max(0, self.gradient_kind.findData(kind if kind in {"linear", "radial"} else "linear")))
        pattern = dict(self._source.get("pattern") or {})
        self.pattern_kind.setCurrentIndex(max(0, self.pattern_kind.findData(pattern.get("kind"))))
        scale_percent = pattern.get("scale_percent")
        if scale_percent is None:
            scale_percent = float(pattern.get("scale", 12) or 12) / 12.0 * 100.0
        self.pattern_scale.setText(str(scale_percent))
        self.pattern_gap_x.setText(str(pattern.get("gap_x", 0))); self.pattern_gap_y.setText(str(pattern.get("gap_y", 0)))
        self.pattern_foreground.setText(str(pattern.get("foreground") or "#C8D2E0FF")); self.pattern_background.setText(str(pattern.get("background") or "#FFFFFFFF")); self.pattern_source.setText(str(pattern.get("source_id") or ""))
        alignment = str(pattern.get("alignment") or "top_left")
        if alignment in self.pattern_alignment_buttons:
            self.pattern_alignment_buttons[alignment].setChecked(True)
        self.image_path.setText(str(self._source.get("source_path") or "")); self.video_path.setText(str(self._source.get("source_path") or ""))
        if kind == "image": self.image_preview.set_source(self.image_path.text())
        self.image_fit.setCurrentIndex(max(0, self.image_fit.findData(self._source.get("fit")))); self.video_fit.setCurrentIndex(max(0, self.video_fit.findData(self._source.get("fit"))))
        for key, slider in self.image_adjustments.items():
            slider.setValue(round(float(dict(self._source.get("adjustments") or {}).get(key, 0))))
        self.shader_combo.setCurrentIndex(max(0, self.shader_combo.findData(self._source.get("shader_preset"))))
        self.opacity_slider.setValue(round(float(self._source.get("opacity", 1.0)) * 100))
        self.blend_combo.setCurrentIndex(max(0, self.blend_combo.findData(self._source.get("blend_mode"))))
        self._refresh_gradient()

    def _plane_changed(self, color: QColor) -> None:
        color.setAlpha(round(self.alpha_slider.value() * 2.55))
        self.color_edit.setText(_rgba_hex(color)[1:7]); self.alpha_slider.set_base_color(color); self._emit_change()

    def _hue_changed(self, value: int) -> None:
        self.color_plane.set_hue(value / 359.0); self._plane_changed(self.color_plane.color())

    def _color_fields_changed(self, _value: int) -> None:
        self.color_opacity.setText(str(self.alpha_slider.value())); self._emit_change()

    def _color_edit_changed(self) -> None:
        color = _hex_color(self.color_edit.text()); color.setAlpha(round(self.alpha_slider.value() * 2.55)); self.color_plane.set_color(color); self.alpha_slider.set_base_color(color); self._emit_change()

    def _color_opacity_changed(self) -> None:
        try: value = int(float(self.color_opacity.text()))
        except ValueError: value = 100
        self.alpha_slider.setValue(max(0, min(100, value)))

    def _gradient_kind_changed(self) -> None:
        if self.pages.currentIndex() == 1:
            self._active_type = str(self.gradient_kind.currentData() or "linear"); self._emit_change()

    def _reverse_gradient(self) -> None:
        a, b = self.stop_start_color.text(), self.stop_end_color.text()
        self.stop_start_color.setText(b); self.stop_end_color.setText(a); self._refresh_gradient()

    def _refresh_gradient(self) -> None:
        start = _hex_color(self.stop_start_color.text()); end = _hex_color(self.stop_end_color.text())
        self.gradient_preview.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {start.name()},stop:1 {end.name()}); border:1px solid #46515F; border-radius:6px;")
        self._emit_change()

    def _browse_media(self, kind: str, target: QLineEdit, preview: _CheckerPreview) -> None:
        filters = "동영상 (*.mp4 *.mov *.webm *.gif)" if kind == "video" else "이미지 (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        path, _ = QFileDialog.getOpenFileName(self, "소스 선택", str(Path.home()), filters)
        if path:
            target.setText(path); preview.set_source(path); self._emit_change()

    def _cycle_blend_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#1E1E1E; color:white; border:1px solid #333; padding:7px; }"
            "QMenu::item { min-width:150px; padding:8px 18px; border-radius:5px; }"
            "QMenu::item:selected { background:#353535; }"
        )
        current = str(self.blend_combo.currentData() or "normal")
        for label, key in BLEND_MODES:
            action = menu.addAction(("✓  " if key == current else "    ") + label)
            action.setData(key)
        chosen = menu.exec(self.blend_button.mapToGlobal(self.blend_button.rect().bottomRight()))
        if chosen is not None:
            index = self.blend_combo.findData(chosen.data())
            if index >= 0:
                self.blend_combo.setCurrentIndex(index)

    def _emit_change(self, *_args) -> None:
        if hasattr(self, "opacity_slider"):
            self.paint_changed.emit(self.paint())

    @staticmethod
    def _float(edit: QLineEdit, default: float) -> float:
        try: return float(edit.text())
        except ValueError: return default

    def paint(self) -> dict[str, Any]:
        color = _hex_color(self.color_edit.text()); color.setAlpha(round(self.alpha_slider.value() * 2.55))
        kind = self._active_type
        row: dict[str, Any] = {
            "type": kind, "visible": bool(self._source.get("visible", True)),
            "opacity": self.opacity_slider.value() / 100.0,
            "blend_mode": str(self.blend_combo.currentData() or "normal"),
            "color": _rgba_hex(color),
        }
        if kind in {"linear", "radial"}:
            row["gradient"] = {"type": kind, "start": {"x": 0.0, "y": 0.5}, "end": {"x": 1.0, "y": 0.5}, "stops": [
                {"position": max(0, min(100, self._float(self.stop_start_position, 0))) / 100, "color": self.stop_start_color.text()},
                {"position": max(0, min(100, self._float(self.stop_end_position, 100))) / 100, "color": self.stop_end_color.text()},
            ]}
        elif kind == "pattern":
            alignment = next((key for key, button in self.pattern_alignment_buttons.items() if button.isChecked()), "top_left")
            tile_type = next((key for key, button in self.pattern_tile_buttons.items() if button.isChecked()), "grid")
            scale_percent = self._float(self.pattern_scale, 100)
            row["pattern"] = {"kind": str(self.pattern_kind.currentData() or "dots"), "foreground": self.pattern_foreground.text(), "background": self.pattern_background.text(), "scale": max(2.0, scale_percent * 0.12), "scale_percent": scale_percent, "gap_x": self._float(self.pattern_gap_x, 0), "gap_y": self._float(self.pattern_gap_y, 0), "alignment": alignment, "tile_type": tile_type, "source_id": self.pattern_source.text().strip()}
        elif kind == "image":
            row.update(source_path=self.image_path.text().strip(), fit=str(self.image_fit.currentData() or "fill"), adjustments={key: slider.value() for key, slider in self.image_adjustments.items()})
        elif kind == "video":
            row.update(source_path=self.video_path.text().strip(), fit=str(self.video_fit.currentData() or "fill"), autoplay=True, loop=True, muted=True, frame_time_ms=0.0)
        elif kind == "shader":
            row.update(shader_preset=str(self.shader_combo.currentData() or "mesh_gradient"), shader_parameters={})
        if self._stroke:
            row.update(width=float(self._source.get("width", 1.0)), align=str(self._source.get("align") or "center"))
        return normalize_ui_paint(row, stroke=self._stroke)


__all__ = ["BLEND_MODES", "FILL_TYPES", "PainterUIFillComponent"]
