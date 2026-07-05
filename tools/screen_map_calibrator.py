from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QAction, QColor, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT.parent / "ReviewAutomationWorkspace" / "source_assets" / "templates"
DEBUG_ROOT = ROOT.parent / "ReviewAutomationWorkspace" / "outputs" / "template_debug" / "screen_map_calibration"

DEFAULT_TEMPLATE = TEMPLATE_ROOT / "multi_monitor_front_facing_catalog_template_v2_tight.png"
DEFAULT_SCREEN_MAP = DEFAULT_TEMPLATE.with_suffix(".screen-map.json")


@dataclass
class Region:
    id: str
    x: int
    y: int
    width: int
    height: int
    fit: str = "cover"
    mapping: str = "rect"
    notes: str = ""

    @property
    def rect(self) -> QRectF:
        return QRectF(self.x, self.y, self.width, self.height)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rect": {
                "x": int(self.x),
                "y": int(self.y),
                "width": int(self.width),
                "height": int(self.height),
            },
            "fit": self.fit,
            "mapping": self.mapping,
            "notes": self.notes,
        }


class ScreenRectItem(QGraphicsRectItem):
    def __init__(self, region: Region, color: QColor) -> None:
        super().__init__(region.rect)
        self.region_id = region.id
        self.on_changed: Any = None
        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setZValue(10)
        self._normal_pen = QPen(color, 2)
        self._selected_pen = QPen(QColor("#ffffff"), 2)
        self._fill = QColor(color)
        self._fill.setAlpha(42)
        self.setBrush(self._fill)
        self.setPen(self._normal_pen)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.setPen(self._selected_pen if bool(value) else self._normal_pen)
        if change == QGraphicsItem.ItemPositionHasChanged:
            if callable(self.on_changed):
                self.on_changed(self.region_id, self.sceneBoundingRect())
        return super().itemChange(change, value)


class ScreenMapCanvas(QGraphicsView):
    regionChanged = Signal(str, QRectF)
    regionSelected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._items: dict[str, ScreenRectItem] = {}
        self._image_path: Path | None = None
        self._zoom = 1.0
        self._fill_mode = False
        self._colors = {
            "left_monitor": QColor("#46d8ff"),
            "center_monitor": QColor("#2fffd8"),
            "right_monitor": QColor("#a6ff65"),
            "laptop_screen": QColor("#b78cff"),
            "ipad_screen": QColor("#ffbd5e"),
        }

    @property
    def image_path(self) -> Path | None:
        return self._image_path

    def load_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise RuntimeError(f"Could not load image: {path}")
        self._image_path = path
        self.scene().clear()
        self._items.clear()
        self._pixmap_item = self.scene().addPixmap(pixmap)
        self._pixmap_item.setZValue(0)
        self.scene().setSceneRect(QRectF(pixmap.rect()))
        self.resetTransform()
        self._zoom = 1.0

    def set_regions(self, regions: list[Region]) -> None:
        for item in self._items.values():
            self.scene().removeItem(item)
        self._items.clear()
        for index, region in enumerate(regions):
            color = self._colors.get(region.id, QColor.fromHsv((index * 70) % 360, 180, 255))
            item = ScreenRectItem(region, color)
            item.on_changed = self.regionChanged.emit
            self.scene().addItem(item)
            self._items[region.id] = item
        self.set_fill_mode(self._fill_mode)

    def set_region_rect(self, region_id: str, rect: QRectF) -> None:
        item = self._items.get(region_id)
        if item is None:
            return
        blocked = item.blockSignals(True)
        item.setPos(0, 0)
        item.setRect(rect)
        item.blockSignals(blocked)

    def selected_region_id(self) -> str | None:
        for region_id, item in self._items.items():
            if item.isSelected():
                return region_id
        return None

    def select_region(self, region_id: str) -> None:
        for item_id, item in self._items.items():
            item.setSelected(item_id == region_id)
        self.centerOn(self._items[region_id])

    def set_zoom_percent(self, value: int) -> None:
        value = max(25, min(800, value))
        self.resetTransform()
        self._zoom = value / 100.0
        self.scale(self._zoom, self._zoom)

    def set_fill_mode(self, enabled: bool) -> None:
        self._fill_mode = enabled
        for item in self._items.values():
            color = item._fill
            color.setAlpha(130 if enabled else 42)
            item.setBrush(color)

    def keyPressEvent(self, event: Any) -> None:
        selected = self.selected_region_id()
        if selected:
            item = self._items[selected]
            step = 10 if event.modifiers() & Qt.ShiftModifier else 1
            dx = dy = 0
            if event.key() == Qt.Key_Left:
                dx = -step
            elif event.key() == Qt.Key_Right:
                dx = step
            elif event.key() == Qt.Key_Up:
                dy = -step
            elif event.key() == Qt.Key_Down:
                dy = step
            if dx or dy:
                item.moveBy(dx, dy)
                self.regionChanged.emit(selected, item.sceneBoundingRect())
                event.accept()
                return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        super().mousePressEvent(event)
        selected = self.selected_region_id()
        if selected:
            self.regionSelected.emit(selected)


class ScreenMapCalibrator(QMainWindow):
    def __init__(self, template_path: Path = DEFAULT_TEMPLATE, screen_map_path: Path = DEFAULT_SCREEN_MAP) -> None:
        super().__init__()
        self.setWindowTitle("TigerCapture Screen Map Calibrator")
        self.resize(1500, 900)
        self.template_path = template_path
        self.screen_map_path = screen_map_path
        self.regions: dict[str, Region] = {}
        self._updating_controls = False

        self.canvas = ScreenMapCanvas()
        self.canvas.regionChanged.connect(self._on_canvas_region_changed)
        self.canvas.regionSelected.connect(self._select_region)

        self.region_list = QListWidget()
        self.region_list.currentItemChanged.connect(self._on_region_list_changed)

        self.x_spin = self._make_spin()
        self.y_spin = self._make_spin()
        self.w_spin = self._make_spin(min_value=1)
        self.h_spin = self._make_spin(min_value=1)
        for spin in (self.x_spin, self.y_spin, self.w_spin, self.h_spin):
            spin.valueChanged.connect(self._on_spin_changed)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(25, 800)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.canvas.set_zoom_percent)
        self.zoom_label = QLabel("100%")
        self.zoom_slider.valueChanged.connect(lambda value: self.zoom_label.setText(f"{value}%"))

        self.fill_check = QCheckBox("Fill preview")
        self.fill_check.toggled.connect(self.canvas.set_fill_mode)

        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.map_label = QLabel()
        self.map_label.setWordWrap(True)

        self._build_ui()
        self._build_toolbar()
        self._install_shortcuts()
        self.load(template_path, screen_map_path)

    def _make_spin(self, min_value: int = -10000) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(min_value, 100000)
        spin.setSingleStep(1)
        return spin

    def _build_ui(self) -> None:
        form = QFormLayout()
        form.addRow("x", self.x_spin)
        form.addRow("y", self.y_spin)
        form.addRow("width", self.w_spin)
        form.addRow("height", self.h_spin)

        nudge_row = QHBoxLayout()
        for label, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, x=dx, y=dy: self._nudge(x, y))
            nudge_row.addWidget(button)

        size_row = QHBoxLayout()
        for label, dw, dh in (("W-", -1, 0), ("W+", 1, 0), ("H-", 0, -1), ("H+", 0, 1)):
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, w=dw, h=dh: self._resize(w, h))
            size_row.addWidget(button)

        button_row = QHBoxLayout()
        add_button = QPushButton("Add Region")
        add_button.clicked.connect(self._add_region)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_region)
        save_button = QPushButton("Save JSON")
        save_button.clicked.connect(self.save_screen_map)
        export_button = QPushButton("Export Preview PNG")
        export_button.clicked.connect(self.export_preview_png)
        button_row.addWidget(add_button)
        button_row.addWidget(remove_button)
        button_row.addWidget(save_button)
        button_row.addWidget(export_button)

        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("Zoom"))
        zoom_row.addWidget(self.zoom_slider)
        zoom_row.addWidget(self.zoom_label)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.addWidget(QLabel("Regions"))
        side_layout.addWidget(self.region_list, 1)
        side_layout.addLayout(form)
        side_layout.addLayout(nudge_row)
        side_layout.addLayout(size_row)
        side_layout.addWidget(self.fill_check)
        side_layout.addLayout(zoom_row)
        side_layout.addLayout(button_row)
        side_layout.addWidget(QLabel("Template"))
        side_layout.addWidget(self.path_label)
        side_layout.addWidget(QLabel("Screen Map"))
        side_layout.addWidget(self.map_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.canvas)

        splitter = QSplitter()
        splitter.addWidget(scroll)
        splitter.addWidget(side)
        splitter.setSizes([1100, 360])
        self.setCentralWidget(splitter)

        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #101419; color: #d7dde6; }
            QGraphicsView { background: #07090c; border: 1px solid #27313d; }
            QListWidget, QSpinBox {
                background: #151b22; border: 1px solid #303a46; border-radius: 6px;
                padding: 4px; color: #eef4ff;
            }
            QPushButton {
                background: #1a222c; border: 1px solid #394656; border-radius: 8px;
                padding: 7px 10px; color: #eef4ff;
            }
            QPushButton:hover { background: #222c38; }
            QLabel { color: #c5ceda; }
            QToolBar { background: #101419; border-bottom: 1px solid #27313d; spacing: 8px; }
            """
        )

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Screen Map")
        self.addToolBar(toolbar)

        open_template = QAction("Open Template", self)
        open_template.triggered.connect(self.open_template)
        toolbar.addAction(open_template)

        open_map = QAction("Open Map", self)
        open_map.triggered.connect(self.open_screen_map)
        toolbar.addAction(open_map)

        save_map = QAction("Save", self)
        save_map.setShortcut(QKeySequence.Save)
        save_map.triggered.connect(self.save_screen_map)
        toolbar.addAction(save_map)

        export = QAction("Export PNG", self)
        export.triggered.connect(self.export_preview_png)
        toolbar.addAction(export)

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_screen_map)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.open_template)

    def load(self, template_path: Path, screen_map_path: Path | None = None) -> None:
        self.template_path = template_path
        self.canvas.load_image(template_path)
        self.path_label.setText(str(template_path))
        if screen_map_path and screen_map_path.exists():
            self.screen_map_path = screen_map_path
            self._load_screen_map(screen_map_path)
        else:
            self.regions = {
                "left_monitor": Region("left_monitor", 100, 100, 300, 200),
                "center_monitor": Region("center_monitor", 430, 100, 300, 200),
                "right_monitor": Region("right_monitor", 760, 100, 300, 200),
            }
        self._refresh_region_ui()

    def _load_screen_map(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_regions = payload.get("screen_regions")
        if not isinstance(raw_regions, list):
            raw_regions = []
            raw_by_id = payload.get("regions")
            if isinstance(raw_by_id, dict):
                for region_id, value in raw_by_id.items():
                    if isinstance(value, dict):
                        item = dict(value)
                        item.setdefault("id", region_id)
                        raw_regions.append(item)
        regions: dict[str, Region] = {}
        for item in raw_regions:
            if not isinstance(item, dict):
                continue
            rect = item.get("rect")
            if not isinstance(rect, dict):
                continue
            region_id = str(item.get("id") or "").strip()
            if not region_id:
                continue
            regions[region_id] = Region(
                id=region_id,
                x=int(rect.get("x") or 0),
                y=int(rect.get("y") or 0),
                width=int(rect.get("width") or 1),
                height=int(rect.get("height") or 1),
                fit=str(item.get("fit") or "cover"),
                mapping=str(item.get("mapping") or "rect"),
                notes=str(item.get("notes") or ""),
            )
        self.regions = regions
        self.map_label.setText(str(path))

    def _refresh_region_ui(self) -> None:
        self.region_list.blockSignals(True)
        self.region_list.clear()
        for region_id in self.regions:
            self.region_list.addItem(QListWidgetItem(region_id))
        self.region_list.blockSignals(False)
        self.canvas.set_regions(list(self.regions.values()))
        if self.regions:
            self.region_list.setCurrentRow(0)
            self._select_region(next(iter(self.regions)))

    def _current_region_id(self) -> str | None:
        item = self.region_list.currentItem()
        return item.text() if item else None

    def _current_region(self) -> Region | None:
        region_id = self._current_region_id()
        return self.regions.get(region_id) if region_id else None

    def _select_region(self, region_id: str) -> None:
        if region_id not in self.regions:
            return
        matches = self.region_list.findItems(region_id, Qt.MatchExactly)
        if matches:
            self.region_list.setCurrentItem(matches[0])
        self.canvas.select_region(region_id)
        self._update_controls_from_region(self.regions[region_id])

    def _on_region_list_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if current is None:
            return
        self._select_region(current.text())

    def _update_controls_from_region(self, region: Region) -> None:
        self._updating_controls = True
        self.x_spin.setValue(region.x)
        self.y_spin.setValue(region.y)
        self.w_spin.setValue(region.width)
        self.h_spin.setValue(region.height)
        self._updating_controls = False

    def _on_canvas_region_changed(self, region_id: str, rect: QRectF) -> None:
        region = self.regions.get(region_id)
        if region is None:
            return
        region.x = round(rect.x())
        region.y = round(rect.y())
        region.width = round(rect.width())
        region.height = round(rect.height())
        if self._current_region_id() == region_id:
            self._update_controls_from_region(region)

    def _on_spin_changed(self) -> None:
        if self._updating_controls:
            return
        region = self._current_region()
        if region is None:
            return
        region.x = self.x_spin.value()
        region.y = self.y_spin.value()
        region.width = self.w_spin.value()
        region.height = self.h_spin.value()
        self.canvas.set_region_rect(region.id, region.rect)

    def _nudge(self, dx: int, dy: int) -> None:
        region = self._current_region()
        if region is None:
            return
        region.x += dx
        region.y += dy
        self.canvas.set_region_rect(region.id, region.rect)
        self._update_controls_from_region(region)

    def _resize(self, dw: int, dh: int) -> None:
        region = self._current_region()
        if region is None:
            return
        region.width = max(1, region.width + dw)
        region.height = max(1, region.height + dh)
        self.canvas.set_region_rect(region.id, region.rect)
        self._update_controls_from_region(region)

    def _add_region(self) -> None:
        base = "region"
        index = 1
        while f"{base}_{index}" in self.regions:
            index += 1
        region_id = f"{base}_{index}"
        self.regions[region_id] = Region(region_id, 100, 100, 320, 180)
        self._refresh_region_ui()
        self._select_region(region_id)

    def _remove_region(self) -> None:
        region_id = self._current_region_id()
        if not region_id:
            return
        self.regions.pop(region_id, None)
        self._refresh_region_ui()

    def open_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open template",
            str(TEMPLATE_ROOT),
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        template = Path(path)
        screen_map = template.with_suffix(".screen-map.json")
        self.load(template, screen_map if screen_map.exists() else None)

    def open_screen_map(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open screen-map",
            str(TEMPLATE_ROOT),
            "Screen Map (*.json)",
        )
        if not path:
            return
        self.screen_map_path = Path(path)
        self._load_screen_map(self.screen_map_path)
        self._refresh_region_ui()

    def screen_map_payload(self) -> dict[str, Any]:
        image = QImage(str(self.template_path))
        regions = [region.to_json() for region in self.regions.values()]
        return {
            "schema": "tiger.review.template.screen_map.calibrated.v1",
            "template": self.template_path.name,
            "image_size": {"width": image.width(), "height": image.height()},
            "screen_regions": regions,
            "regions": {
                region["id"]: {
                    "rect": region["rect"],
                    "fit": region["fit"],
                    "mapping": region["mapping"],
                    "notes": region["notes"],
                }
                for region in regions
            },
            "rules": [
                "Generated by tools/screen_map_calibrator.py.",
                "Replace only declared screen regions with real TigerCapture captures.",
                "Do not distort template hardware.",
            ],
        }

    def save_screen_map(self) -> None:
        path = self.screen_map_path
        if not path:
            path = self.template_path.with_suffix(".screen-map.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.screen_map_payload(), indent=2), encoding="utf-8")
        self.screen_map_path = path
        self.map_label.setText(str(path))
        QMessageBox.information(self, "Saved", f"Saved screen map:\\n{path}")

    def export_preview_png(self) -> None:
        if not self.template_path.exists():
            return
        DEBUG_ROOT.mkdir(parents=True, exist_ok=True)
        out = DEBUG_ROOT / f"{self.template_path.stem}_calibration_preview.png"
        image = QImage(str(self.template_path)).convertToFormat(QImage.Format_ARGB32)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing, True)
        for region in self.regions.values():
            color = QColor("#00ffe1")
            fill = QColor("#00ffe1")
            fill.setAlpha(36)
            painter.fillRect(region.rect, fill)
            painter.setPen(QPen(color, 3))
            painter.drawRect(region.rect)
            painter.drawText(QPointF(region.x + 10, region.y + 24), region.id)
        painter.end()
        image.save(str(out))
        QMessageBox.information(self, "Exported", f"Exported preview PNG:\\n{out}")


def main(argv: list[str]) -> int:
    template = Path(argv[1]) if len(argv) > 1 else DEFAULT_TEMPLATE
    screen_map = Path(argv[2]) if len(argv) > 2 else template.with_suffix(".screen-map.json")
    app = QApplication(sys.argv)
    window = ScreenMapCalibrator(template, screen_map)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
