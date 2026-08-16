"""Compact editing surface shown when a UI frame is selected."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.painter_ui_advanced_appearance import normalize_ui_advanced_style
from app.painter_ui_paint_editor import PainterUIPaintStackEditor
from app.painter_ui_umg_panel_selector import PainterUIUMGPanelSelector


class PainterUIFrameSelectionPanel(QFrame):
    geometry_changed = Signal(object)
    properties_changed = Signal(object)
    align_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIFrameSelectionPanel")
        self._syncing = False
        self._row: dict[str, Any] = {}
        self.setStyleSheet(
            """
            QFrame#PainterUIFrameSelectionPanel { background:#1E2228; border:none; }
            QLabel#PainterUIFrameInspectorTitle { color:#F2F5F9; font-size:13px; font-weight:700; }
            QLabel#PainterUIFrameInspectorSection { color:#E1E7EF; font-size:11px; font-weight:650; padding-top:6px; }
            QLabel#PainterUIFrameInspectorHint { color:#8995A5; font-size:9px; }
            QLabel#PainterUIUMGPanelTitle,
            QLabel#PainterUIUMGPanelEffective { color:#DDE7F2; font-weight:650; }
            QLabel#PainterUIUMGPanelReason { color:#8995A5; font-size:9px; }
            QComboBox#PainterUIUMGPanelModeCombo {
                background:#11161D; color:#EDF2F8; border:1px solid #303A47;
                border-radius:4px; min-height:28px; padding:0 5px;
            }
            QDoubleSpinBox#PainterUIFrameInspectorValue {
                background:#11161D; color:#EDF2F8; border:1px solid #303A47;
                border-radius:4px; min-height:28px; padding:0 5px;
            }
            QPushButton#PainterUIFrameInspectorIcon {
                background:#151B23; color:#DDE5EF; border:1px solid #303A47;
                border-radius:4px; min-height:28px; padding:0 6px;
            }
            QPushButton#PainterUIFrameInspectorIcon:hover { background:#293442; }
            QPushButton#PainterUIFrameInspectorIcon:checked {
                background:#315F9B; border-color:#6B9DDD; color:#FFFFFF;
            }
            QCheckBox#PainterUIFrameInspectorClip { color:#DDE5EF; min-height:28px; }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.title = QLabel("프레임")
        self.title.setObjectName("PainterUIFrameInspectorTitle")
        layout.addWidget(self.title)

        layout.addWidget(self._section("위치"))
        align_row = QHBoxLayout()
        align_row.setSpacing(3)
        self.align_buttons: dict[str, QPushButton] = {}
        for command, label in (
            ("left", "L"),
            ("hcenter", "HC"),
            ("right", "R"),
            ("top", "T"),
            ("vcenter", "VC"),
            ("bottom", "B"),
        ):
            button = self._button(label)
            button.setToolTip(command)
            button.clicked.connect(
                lambda _checked=False, value=command:
                self.align_requested.emit(value)
            )
            self.align_buttons[command] = button
            align_row.addWidget(button, 1)
        layout.addLayout(align_row)

        transform_grid = QGridLayout()
        transform_grid.setContentsMargins(0, 0, 0, 0)
        transform_grid.setHorizontalSpacing(5)
        transform_grid.setVerticalSpacing(5)
        self.geometry_controls: dict[str, QDoubleSpinBox] = {}
        for index, (key, prefix) in enumerate(
            (("x", "X"), ("y", "Y"), ("rotation", "°"))
        ):
            spin = self._spin(prefix)
            spin.setRange(-100000.0, 100000.0)
            spin.editingFinished.connect(self._emit_geometry)
            self.geometry_controls[key] = spin
            transform_grid.addWidget(spin, index // 2, index % 2)
        layout.addLayout(transform_grid)

        layout.addWidget(self._section("레이아웃"))
        flow_row = QHBoxLayout()
        flow_row.setSpacing(3)
        self.flow_buttons: dict[str, QPushButton] = {}
        for mode, label in (
            ("none", "자유"),
            ("vertical", "↓"),
            ("horizontal", "→"),
            ("wrap", "격자"),
        ):
            button = self._button(label, checkable=True)
            button.clicked.connect(
                lambda _checked=False, value=mode: self._set_layout(value)
            )
            self.flow_buttons[mode] = button
            flow_row.addWidget(button, 1)
        layout.addLayout(flow_row)

        self.umg_panel_selector = PainterUIUMGPanelSelector(self)
        self.umg_panel_selector.mode_changed.connect(
            self._set_umg_panel_mode
        )
        layout.addWidget(self.umg_panel_selector)

        size_grid = QGridLayout()
        size_grid.setContentsMargins(0, 0, 0, 0)
        size_grid.setHorizontalSpacing(5)
        self.width_spin = self._spin("W")
        self.height_spin = self._spin("H")
        for spin in (self.width_spin, self.height_spin):
            spin.setRange(1.0, 100000.0)
            spin.editingFinished.connect(self._emit_geometry)
        size_grid.addWidget(self.width_spin, 0, 0)
        size_grid.addWidget(self.height_spin, 0, 1)
        layout.addLayout(size_grid)
        self.clip_check = QCheckBox("넘친 콘텐츠 숨기기")
        self.clip_check.setObjectName("PainterUIFrameInspectorClip")
        self.clip_check.toggled.connect(self._emit_properties)
        layout.addWidget(self.clip_check)

        layout.addWidget(self._section("외형"))
        appearance = QGridLayout()
        appearance.setContentsMargins(0, 0, 0, 0)
        appearance.setHorizontalSpacing(5)
        self.opacity_spin = self._spin("%")
        self.opacity_spin.setRange(0.0, 100.0)
        self.opacity_spin.editingFinished.connect(self._emit_properties)
        self.radius_spin = self._spin("R")
        self.radius_spin.setRange(0.0, 10000.0)
        self.radius_spin.editingFinished.connect(self._emit_properties)
        appearance.addWidget(self.opacity_spin, 0, 0)
        appearance.addWidget(self.radius_spin, 0, 1)
        layout.addLayout(appearance)

        self.fill_editor = PainterUIPaintStackEditor("채우기")
        self.fill_editor.paints_changed.connect(self._fills_changed)
        layout.addWidget(self.fill_editor)
        self.stroke_editor = PainterUIPaintStackEditor("외곽선", stroke=True)
        self.stroke_editor.paints_changed.connect(self._strokes_changed)
        layout.addWidget(self.stroke_editor)

        self.effect_button = self._button("효과   +")
        self.effect_button.setToolTip("고급 외형 편집기에서 효과를 추가합니다")
        layout.addWidget(self.effect_button)
        self.layout_guide_button = self._button("레이아웃 가이드   +")
        layout.addWidget(self.layout_guide_button)
        layout.addStretch(1)

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("PainterUIFrameInspectorSection")
        return label

    @staticmethod
    def _button(text: str, *, checkable: bool = False) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("PainterUIFrameInspectorIcon")
        button.setCheckable(checkable)
        return button

    @staticmethod
    def _spin(prefix: str) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setObjectName("PainterUIFrameInspectorValue")
        spin.setDecimals(1)
        spin.setPrefix(f"{prefix}  ")
        spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        return spin

    def set_frame(
        self,
        row: Mapping[str, Any],
        document: Mapping[str, Any] | None = None,
        *,
        normalize: bool = True,
    ) -> None:
        """Show ``row``'s frame properties.

        ``normalize=False`` promises ``document`` is canonical. The UMG panel
        classifier walks the whole document, so without this a selection
        change re-derived every row just to fill in this panel.
        """
        self._row = dict(row)
        self._syncing = True
        try:
            self.title.setText(str(row.get("name") or "프레임"))
            for key, spin in self.geometry_controls.items():
                spin.setValue(float(row.get(key) or 0.0))
            self.width_spin.setValue(float(row.get("width") or 1.0))
            self.height_spin.setValue(float(row.get("height") or 1.0))
            self.clip_check.setChecked(bool(row.get("clip_content", False)))
            self.opacity_spin.setValue(float(row.get("opacity", 1.0)) * 100.0)
            style = normalize_ui_advanced_style(row.get("style"))
            radii = dict(style.get("corner_radii") or {})
            self.radius_spin.setValue(float(radii.get("top_left") or 0.0))
            self.fill_editor.set_paints(style.get("fills"))
            self.stroke_editor.set_paints(style.get("strokes"))
            layout = dict(row.get("layout") or {})
            mode = str(layout.get("mode") or "none")
            active = "wrap" if mode == "horizontal" and layout.get("wrap") else mode
            for key, button in self.flow_buttons.items():
                button.setChecked(key == active)
            self.umg_panel_selector.set_context(
                document,
                row,
                editable=not bool(row.get("locked", False)),
                normalize=normalize,
            )
        finally:
            self._syncing = False

    def _emit_geometry(self) -> None:
        if self._syncing:
            return
        self.geometry_changed.emit(
            {
                "x": self.geometry_controls["x"].value(),
                "y": self.geometry_controls["y"].value(),
                "rotation": self.geometry_controls["rotation"].value(),
                "width": self.width_spin.value(),
                "height": self.height_spin.value(),
            }
        )

    def _set_layout(self, requested: str) -> None:
        if self._syncing:
            return
        layout = dict(self._row.get("layout") or {})
        layout["mode"] = "horizontal" if requested == "wrap" else requested
        layout["wrap"] = requested == "wrap"
        self.properties_changed.emit({"layout": layout})

    def _set_umg_panel_mode(self, requested: str) -> None:
        if self._syncing:
            return
        layout = dict(self._row.get("layout") or {})
        layout["umg_panel_mode"] = str(requested or "auto")
        self.properties_changed.emit({"layout": layout})

    def umg_panel_state(self) -> dict[str, Any]:
        return self.umg_panel_selector.state()

    def _emit_properties(self) -> None:
        if self._syncing:
            return
        style = dict(self._row.get("style") or {})
        radius = self.radius_spin.value()
        style["corner_radii"] = {
            "top_left": radius,
            "top_right": radius,
            "bottom_right": radius,
            "bottom_left": radius,
        }
        self.properties_changed.emit(
            {
                "clip_content": self.clip_check.isChecked(),
                "opacity": self.opacity_spin.value() / 100.0,
                "style": style,
            }
        )

    def _fills_changed(self, paints: object) -> None:
        if self._syncing:
            return
        style = normalize_ui_advanced_style(self._row.get("style"))
        style["fills"] = list(paints or [])
        first = next((row for row in style["fills"] if row.get("visible", True)), None)
        if first and first.get("type") == "solid":
            style["fill"] = str(first.get("color") or "#00000000")
        self.properties_changed.emit({"style": style})

    def _strokes_changed(self, paints: object) -> None:
        if self._syncing:
            return
        style = normalize_ui_advanced_style(self._row.get("style"))
        style["strokes"] = list(paints or [])
        first = next((row for row in style["strokes"] if row.get("visible", True)), None)
        if first:
            style["stroke"] = str(first.get("color") or "#00000000")
            style["stroke_width"] = float(first.get("width") or 0.0)
            style["stroke_align"] = str(first.get("align") or "center")
        self.properties_changed.emit({"style": style})


__all__ = ["PainterUIFrameSelectionPanel"]
