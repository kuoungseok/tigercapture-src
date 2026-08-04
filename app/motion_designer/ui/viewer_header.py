from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QWidget

from app.color_picker_widget import ColorPaletteStrip, ColorPickerButton


class ViewerHeader(QWidget):
    zoom_changed = Signal(str)
    grid_changed = Signal(bool)
    safe_changed = Signal(bool)
    color_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionViewerHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        self.fps = QLabel("FPS 30", self)
        self.zoom = QComboBox(self)
        self.zoom.addItems(["Fit", "25%", "50%", "100%", "200%"])
        self.grid = QCheckBox("Grid", self)
        self.safe = QCheckBox("Safe", self)
        self.safe.setChecked(True)
        self.color_picker = ColorPickerButton(
            "#FF3F8FBA",
            self,
            title="Choose selected layer color",
            presentation="portrait",
        )
        self.color_picker.setToolTip(
            "Choose color for the selected Shape or Text layer"
        )
        self.color_picker.setEnabled(False)
        self.color_palette = ColorPaletteStrip(
            self,
            maximum_colors=5,
            presentation="portrait",
        )
        self.color_palette.setEnabled(False)
        layout.addWidget(self.fps)
        layout.addStretch(1)
        layout.addWidget(QLabel("Palette", self))
        layout.addWidget(self.color_palette)
        layout.addWidget(self.color_picker)
        layout.addWidget(self.zoom)
        layout.addWidget(self.grid)
        layout.addWidget(self.safe)
        self.zoom.currentTextChanged.connect(self.zoom_changed)
        self.grid.toggled.connect(self.grid_changed)
        self.safe.toggled.connect(self.safe_changed)
        self.color_picker.color_selected.connect(self.color_changed)
        self.color_palette.color_selected.connect(self.color_changed)

    def set_fps(self, fps: float) -> None:
        self.fps.setText(f"FPS {fps:g}")
