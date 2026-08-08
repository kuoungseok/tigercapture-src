"""Context panel for editable Painter UI shape layers."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QSize, Signal, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
)

from app.icons import app_icon, icon_size
from app.painter_ui_advanced_appearance import normalize_ui_advanced_style
from app.painter_ui_paint_editor import PainterUIPaintStackEditor
from app.painter_ui_parametric_shapes import normalize_parametric_shape_content


_SHAPE_TITLES = {
    "rectangle": "직사각형",
    "ellipse": "타원",
    "line": "선",
    "arrow": "화살표",
    "polygon": "다각형",
    "star": "별",
    "arc": "호",
}


class PainterUIShapeSelectionPanel(QFrame):
    geometry_changed = Signal(object)
    properties_changed = Signal(object)
    align_requested = Signal(str)
    advanced_appearance_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIShapeSelectionPanel")
        self._syncing = False
        self._row: dict[str, Any] = {}
        self._boolean_operand_appearance_locked = False
        self.setStyleSheet(
            """
            QFrame#PainterUIShapeSelectionPanel { background:#1E2228; border:none; }
            QLabel#PainterUIShapeInspectorTitle { color:#F2F5F9; font-size:13px; font-weight:700; }
            QLabel#PainterUIShapeInspectorSection { color:#E1E7EF; font-size:11px; font-weight:650; padding-top:6px; }
            QLabel#PainterUIShapeInspectorHint { color:#8D99A8; font-size:9px; }
            QLineEdit#PainterUIShapeInspectorValue,
            QSpinBox#PainterUIShapeInspectorValue,
            QDoubleSpinBox#PainterUIShapeInspectorValue {
                background:#11161D; color:#EDF2F8; border:1px solid #303A47;
                border-radius:4px; min-height:28px; padding:0 5px;
            }
            QPushButton#PainterUIShapeInspectorIcon {
                background:#151B23; color:#DDE5EF; border:1px solid #303A47;
                border-radius:4px; min-height:28px; padding:0 6px;
            }
            QPushButton#PainterUIShapeInspectorIcon:hover { background:#293442; }
            QPushButton#PainterUIShapeInspectorIcon:checked {
                background:#315F9B; border-color:#6B9DDD; color:#FFFFFF;
            }
            QToolButton#PainterUIShapeInspectorTool {
                background:transparent; color:#DDE5EF; border:none;
                border-radius:4px; min-width:24px; max-width:24px;
                min-height:28px; max-height:28px;
            }
            QToolButton#PainterUIShapeInspectorTool:hover { background:#293442; }
            QToolButton#PainterUIShapeInspectorTool:checked {
                background:#315F9B; color:#FFFFFF;
            }
            QFrame#PainterUIShapeInspectorSeparator {
                background:#303741; border:none; min-height:1px; max-height:1px;
            }
            QLabel#PainterUIShapeInspectorField { color:#8995A5; font-size:9px; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(3)
        self.title = QLabel("도형")
        self.title.setObjectName("PainterUIShapeInspectorTitle")
        header.addWidget(self.title, 1)
        self.header_buttons: dict[str, QToolButton] = {}
        for key, icon_name, tooltip in (
            ("properties", "grid", "속성"),
            ("component", "workflow", "컴포넌트 만들기"),
            ("appearance", "color", "외형"),
            ("more", "more", "더 보기"),
        ):
            button = self._tool_button(icon_name, tooltip)
            if key == "appearance":
                button.clicked.connect(self.advanced_appearance_requested)
            self.header_buttons[key] = button
            header.addWidget(button)
        layout.addLayout(header)
        self.parent_hint = QLabel("캔버스 최상위 레이어")
        self.parent_hint.setObjectName("PainterUIShapeInspectorHint")
        layout.addWidget(self.parent_hint)
        layout.addWidget(self._separator())

        layout.addWidget(self._section("위치"))
        layout.addWidget(self._field_label("정렬"))
        align_row = QHBoxLayout()
        align_row.setSpacing(3)
        self.align_buttons: dict[str, QPushButton] = {}
        for command, label in (
            ("left", "L"), ("hcenter", "HC"), ("right", "R"),
            ("top", "T"), ("vcenter", "VC"), ("bottom", "B"),
        ):
            button = self._button("")
            button.setIcon(self._alignment_icon(command))
            button.setIconSize(QSize(16, 16))
            button.setFixedWidth(28)
            button.setToolTip(command)
            button.clicked.connect(
                lambda _checked=False, value=command:
                self.align_requested.emit(value)
            )
            self.align_buttons[command] = button
            align_row.addWidget(button, 1)
        layout.addLayout(align_row)

        layout.addWidget(self._field_label("위치"))
        position_grid = QGridLayout()
        position_grid.setHorizontalSpacing(5)
        position_grid.setVerticalSpacing(5)
        self.geometry_controls: dict[str, QDoubleSpinBox] = {}
        for index, (key, prefix) in enumerate(
            (("x", "X"), ("y", "Y"), ("width", "W"),
             ("height", "H"), ("rotation", "°"))
        ):
            spin = self._double_spin(prefix)
            spin.setRange(-100000.0, 100000.0)
            if key in {"width", "height"}:
                spin.setMinimum(1.0)
            spin.editingFinished.connect(self._emit_geometry)
            self.geometry_controls[key] = spin
            if key in {"x", "y"}:
                position_grid.addWidget(spin, 0, index)
        layout.addLayout(position_grid)

        layout.addWidget(self._field_label("회전"))
        rotation_row = QHBoxLayout()
        rotation_row.setSpacing(5)
        self.geometry_controls["rotation"].setMinimumWidth(0)
        self.geometry_controls["rotation"].setMaximumWidth(130)
        rotation_row.addWidget(self.geometry_controls["rotation"], 1)
        self.flip_horizontal_button = self._tool_button(
            "flip-horizontal", "좌우 반전", checkable=True
        )
        self.flip_vertical_button = self._tool_button(
            "flip-vertical", "상하 반전", checkable=True
        )
        self.flip_horizontal_button.clicked.connect(
            lambda checked=False: self._toggle_flip("x", bool(checked))
        )
        self.flip_vertical_button.clicked.connect(
            lambda checked=False: self._toggle_flip("y", bool(checked))
        )
        rotation_row.addWidget(self.flip_horizontal_button)
        rotation_row.addWidget(self.flip_vertical_button)
        layout.addLayout(rotation_row)

        layout.addWidget(self._separator())
        layout.addWidget(self._section("레이아웃"))
        layout.addWidget(self._field_label("크기"))
        size_row = QHBoxLayout()
        size_row.setSpacing(5)
        self.geometry_controls["width"].setMinimumWidth(0)
        self.geometry_controls["height"].setMinimumWidth(0)
        self.geometry_controls["width"].setMaximumWidth(82)
        self.geometry_controls["height"].setMaximumWidth(82)
        size_row.addWidget(self.geometry_controls["width"], 1)
        size_row.addWidget(self.geometry_controls["height"], 1)
        self.aspect_lock = self._tool_button(
            "lock", "비율 잠금", checkable=True
        )
        size_row.addWidget(self.aspect_lock)
        layout.addLayout(size_row)

        self.shape_section = self._section("도형")
        layout.addWidget(self.shape_section)
        self.shape_parameters = QFrame()
        parameter_grid = QGridLayout(self.shape_parameters)
        parameter_grid.setContentsMargins(0, 0, 0, 0)
        parameter_grid.setHorizontalSpacing(5)
        parameter_grid.setVerticalSpacing(5)
        self.points_spin = QSpinBox()
        self.points_spin.setObjectName("PainterUIShapeInspectorValue")
        self.points_spin.setRange(3, 60)
        self.points_spin.editingFinished.connect(self._emit_properties)
        self.inner_spin = self._double_spin("안쪽 %")
        self.inner_spin.setRange(0.0, 95.0)
        self.inner_spin.editingFinished.connect(self._emit_properties)
        self.parameter_rotation_spin = self._double_spin("회전 °")
        self.parameter_rotation_spin.setRange(-360.0, 360.0)
        self.parameter_rotation_spin.editingFinished.connect(
            self._emit_properties
        )
        self.start_spin = self._double_spin("시작 °")
        self.start_spin.setRange(-360.0, 360.0)
        self.start_spin.editingFinished.connect(self._emit_properties)
        self.sweep_spin = self._double_spin("범위 °")
        self.sweep_spin.setRange(-360.0, 360.0)
        self.sweep_spin.editingFinished.connect(self._emit_properties)
        parameter_grid.addWidget(self.points_spin, 0, 0)
        parameter_grid.addWidget(self.inner_spin, 0, 1)
        parameter_grid.addWidget(self.parameter_rotation_spin, 1, 0)
        parameter_grid.addWidget(self.start_spin, 2, 0)
        parameter_grid.addWidget(self.sweep_spin, 2, 1)
        layout.addWidget(self.shape_parameters)

        layout.addWidget(self._separator())
        layout.addWidget(self._section("외형"))
        appearance = QGridLayout()
        appearance.setHorizontalSpacing(5)
        appearance.setVerticalSpacing(4)
        self.opacity_spin = self._double_spin("%")
        self.opacity_spin.setRange(0.0, 100.0)
        self.opacity_spin.editingFinished.connect(self._emit_properties)
        self.radius_spin = self._double_spin("R")
        self.radius_spin.setRange(0.0, 10000.0)
        self.radius_spin.editingFinished.connect(self._emit_properties)
        appearance.addWidget(self._field_label("불투명도"), 0, 0)
        appearance.addWidget(self._field_label("모서리 반경"), 0, 1)
        appearance.addWidget(self.opacity_spin, 1, 0)
        appearance.addWidget(self.radius_spin, 1, 1)
        self.corner_mode_button = self._tool_button(
            "fit", "개별 모서리", checkable=True
        )
        self.corner_mode_button.toggled.connect(
            self._set_individual_corners_visible
        )
        appearance.addWidget(self.corner_mode_button, 1, 2)
        layout.addLayout(appearance)

        self.corner_controls_frame = QFrame()
        corner_grid = QGridLayout(self.corner_controls_frame)
        corner_grid.setContentsMargins(0, 0, 0, 0)
        corner_grid.setHorizontalSpacing(5)
        corner_grid.setVerticalSpacing(5)
        self.corner_controls: dict[str, QDoubleSpinBox] = {}
        for index, (key, prefix) in enumerate((
            ("top_left", "↖"),
            ("top_right", "↗"),
            ("bottom_left", "↙"),
            ("bottom_right", "↘"),
        )):
            spin = self._double_spin(prefix)
            spin.setRange(0.0, 10000.0)
            spin.editingFinished.connect(self._emit_properties)
            self.corner_controls[key] = spin
            corner_grid.addWidget(spin, index // 2, index % 2)
        self.corner_controls_frame.hide()
        layout.addWidget(self.corner_controls_frame)

        layout.addWidget(self._separator())
        self.fill_editor = PainterUIPaintStackEditor("채우기")
        self.fill_editor.paints_changed.connect(self._fills_changed)
        layout.addWidget(self.fill_editor)
        self.stroke_editor = PainterUIPaintStackEditor("외곽선", stroke=True)
        self.stroke_editor.paints_changed.connect(self._strokes_changed)
        layout.addWidget(self.stroke_editor)
        layout.addWidget(self._separator())
        self.effect_button = self._button("효과                                      +")
        self.effect_button.clicked.connect(self.advanced_appearance_requested)
        layout.addWidget(self.effect_button)
        self.export_button = self._button("내보내기   +")
        layout.addWidget(self.export_button)
        layout.addStretch(1)

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("PainterUIShapeInspectorSection")
        return label

    @staticmethod
    def _button(text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("PainterUIShapeInspectorIcon")
        return button

    @staticmethod
    def _tool_button(
        icon_name: str,
        tooltip: str,
        *,
        checkable: bool = False,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName("PainterUIShapeInspectorTool")
        button.setCheckable(checkable)
        button.setIcon(app_icon(icon_name, size=15, color="#DDE5EF"))
        button.setIconSize(icon_size(15))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setFixedSize(24, 28)
        return button

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("PainterUIShapeInspectorField")
        return label

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("PainterUIShapeInspectorSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        return separator

    @staticmethod
    def _alignment_icon(command: str) -> QIcon:
        pixmap = QPixmap(18, 18)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor("#DDE5EF"), 1.5))
        horizontal = command in {"left", "hcenter", "right"}
        if horizontal:
            anchor = {"left": 3, "hcenter": 9, "right": 15}[command]
            painter.drawLine(anchor, 3, anchor, 15)
            if command == "left":
                starts = (5, 5, 5)
            elif command == "right":
                starts = (13, 13, 13)
            else:
                starts = (9, 9, 9)
            widths = (8, 11, 6)
            for row, (start, width) in enumerate(zip(starts, widths)):
                y = 5 + row * 4
                if command == "left":
                    painter.drawLine(start, y, start + width, y)
                elif command == "right":
                    painter.drawLine(start - width, y, start, y)
                else:
                    painter.drawLine(start - width // 2, y, start + width // 2, y)
        else:
            anchor = {"top": 3, "vcenter": 9, "bottom": 15}[command]
            painter.drawLine(3, anchor, 15, anchor)
            heights = (8, 11, 6)
            for column, height in enumerate(heights):
                x = 5 + column * 4
                if command == "top":
                    painter.drawLine(x, 5, x, 5 + height)
                elif command == "bottom":
                    painter.drawLine(x, 13 - height, x, 13)
                else:
                    painter.drawLine(x, 9 - height // 2, x, 9 + height // 2)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def _double_spin(prefix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName("PainterUIShapeInspectorValue")
        spin.setDecimals(1)
        spin.setPrefix(f"{prefix}  ")
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        return spin

    def set_shape(
        self,
        row: Mapping[str, Any],
        document: Mapping[str, Any] | None = None,
    ) -> None:
        self._row = dict(row)
        content = dict(row.get("content") or {})
        kind = str(row.get("kind") or "rectangle").casefold()
        display_kind = "arrow" if kind == "line" and content.get("arrow_end") else kind
        parent_id = str(row.get("parent_id") or "")
        parent = next(
            (
                item for item in (document or {}).get("objects", [])
                if str(item.get("id") or "") == parent_id
            ),
            None,
        )
        from app.painter_ui_boolean import is_ui_boolean_group

        boolean_operand = bool(parent is not None and is_ui_boolean_group(parent))
        self._syncing = True
        try:
            self.title.setText(_SHAPE_TITLES.get(display_kind, "도형"))
            self.parent_hint.setText(
                f"{str(parent.get('name') or '프레임')} 안의 레이어"
                if parent is not None else "캔버스 최상위 레이어"
            )
            for key, spin in self.geometry_controls.items():
                spin.setValue(float(row.get(key) or 0.0))
            self.flip_horizontal_button.setChecked(bool(content.get("flip_x", False)))
            self.flip_vertical_button.setChecked(bool(content.get("flip_y", False)))
            style = normalize_ui_advanced_style(row.get("style"))
            self.opacity_spin.setValue(float(row.get("opacity", 1.0)) * 100.0)
            radii = dict(style.get("corner_radii") or {})
            self.radius_spin.setValue(float(radii.get("top_left") or 0.0))
            for key, spin in self.corner_controls.items():
                spin.setValue(float(radii.get(key) or 0.0))
            radius_values = {
                round(float(radii.get(key) or 0.0), 6)
                for key in self.corner_controls
            }
            individual_corners = kind == "rectangle" and len(radius_values) > 1
            self.corner_mode_button.setChecked(individual_corners)
            self.radius_spin.setVisible(kind in {"rectangle", "polygon", "star"})
            self.corner_mode_button.setVisible(kind == "rectangle")
            self._set_individual_corners_visible(individual_corners)
            self.fill_editor.setVisible(kind != "line")
            self.fill_editor.set_paints(style.get("fills"))
            self.stroke_editor.set_paints(style.get("strokes"))
            parameters = normalize_parametric_shape_content(kind, content)
            if kind in {"polygon", "star"}:
                self.radius_spin.setValue(
                    float(parameters.get("corner_radius", 0.0))
                )
            self.points_spin.setValue(int(parameters.get("point_count", 5)))
            self.inner_spin.setValue(float(parameters.get("inner_radius", 0.45)) * 100.0)
            self.parameter_rotation_spin.setValue(
                float(parameters.get("rotation_offset", -90.0))
            )
            self.start_spin.setValue(float(parameters.get("start_angle", -90.0)))
            self.sweep_spin.setValue(float(parameters.get("sweep_angle", 270.0)))
            parametric = kind in {"polygon", "star", "arc"}
            self.shape_section.setVisible(parametric)
            self.shape_parameters.setVisible(parametric)
            self.points_spin.setVisible(kind in {"polygon", "star"})
            self.inner_spin.setVisible(kind in {"star", "arc"})
            self.parameter_rotation_spin.setVisible(kind in {"polygon", "star"})
            self.start_spin.setVisible(kind == "arc")
            self.sweep_spin.setVisible(kind == "arc")
            self._set_boolean_operand_appearance_locked(boolean_operand)
        finally:
            self._syncing = False

    def _set_boolean_operand_appearance_locked(self, locked: bool) -> None:
        """Keep Boolean-child geometry editable while the group owns appearance."""
        self._boolean_operand_appearance_locked = bool(locked)
        enabled = not self._boolean_operand_appearance_locked
        reason = (
            "Boolean 그룹의 채우기·외곽선·효과가 적용됩니다"
            if locked
            else ""
        )
        for widget in (
            self.opacity_spin,
            self.fill_editor,
            self.stroke_editor,
            self.effect_button,
            self.header_buttons["appearance"],
        ):
            widget.setEnabled(enabled)
            widget.setToolTip(reason)

    def _set_individual_corners_visible(self, visible: bool) -> None:
        enabled = bool(visible and not self.corner_mode_button.isHidden())
        self.corner_controls_frame.setVisible(enabled)

    def _toggle_flip(self, axis: str, checked: bool) -> None:
        if self._syncing:
            return
        content = dict(self._row.get("content") or {})
        content[f"flip_{axis}"] = bool(checked)
        self.properties_changed.emit({"content": content})

    def _emit_geometry(self) -> None:
        if self._syncing:
            return
        changes = {
            key: spin.value() for key, spin in self.geometry_controls.items()
        }
        if self.aspect_lock.isChecked():
            old_width = max(1.0, float(self._row.get("width") or 1.0))
            old_height = max(1.0, float(self._row.get("height") or 1.0))
            width_changed = abs(changes["width"] - old_width) >= abs(
                changes["height"] - old_height
            )
            if width_changed:
                changes["height"] = changes["width"] * old_height / old_width
            else:
                changes["width"] = changes["height"] * old_width / old_height
        self.geometry_changed.emit(changes)

    def _emit_properties(self) -> None:
        if self._syncing:
            return
        kind = str(self._row.get("kind") or "rectangle").casefold()
        style = normalize_ui_advanced_style(self._row.get("style"))
        radius = self.radius_spin.value()
        if kind == "rectangle":
            style["corner_radii"] = (
                {
                    key: spin.value()
                    for key, spin in self.corner_controls.items()
                }
                if self.corner_mode_button.isChecked()
                else {
                    key: radius for key in (
                        "top_left", "top_right", "bottom_right", "bottom_left"
                    )
                }
            )
        changes: dict[str, Any] = {
            "opacity": self.opacity_spin.value() / 100.0,
            "style": style,
        }
        if kind in {"polygon", "star", "arc"}:
            content = dict(self._row.get("content") or {})
            content.update(
                {
                    "point_count": self.points_spin.value(),
                    "inner_radius": self.inner_spin.value() / 100.0,
                    "rotation_offset": self.parameter_rotation_spin.value(),
                    "start_angle": self.start_spin.value(),
                    "sweep_angle": self.sweep_spin.value(),
                    "corner_radius": radius,
                }
            )
            changes["content"] = normalize_parametric_shape_content(kind, content)
        self.properties_changed.emit(changes)

    def _fills_changed(self, paints: object) -> None:
        if self._syncing or self._boolean_operand_appearance_locked:
            return
        style = normalize_ui_advanced_style(self._row.get("style"))
        style["fills"] = list(paints or [])
        first = next((item for item in style["fills"] if item.get("visible", True)), None)
        if first and first.get("type") == "solid":
            style["fill"] = str(first.get("color") or "#00000000")
        self.properties_changed.emit({"style": style})

    def _strokes_changed(self, paints: object) -> None:
        if self._syncing or self._boolean_operand_appearance_locked:
            return
        style = normalize_ui_advanced_style(self._row.get("style"))
        style["strokes"] = list(paints or [])
        first = next((item for item in style["strokes"] if item.get("visible", True)), None)
        if first:
            style["stroke"] = str(first.get("color") or "#00000000")
            style["stroke_width"] = float(first.get("width") or 0.0)
            style["stroke_align"] = str(first.get("align") or "center")
        self.properties_changed.emit({"style": style})


__all__ = ["PainterUIShapeSelectionPanel"]
