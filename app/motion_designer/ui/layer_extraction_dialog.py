"""Review and non-destructively repair one image decomposition."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.image_decomposition import ImageDecompositionResult
from app.motion_designer.image_decomposition_edits import (
    merge_decomposition_elements,
    replace_decomposition_element_mask,
    set_decomposition_lock,
    set_decomposition_parent,
    set_decomposition_pivot,
    set_decomposition_z_order,
    split_decomposition_element,
)
from .mask_refine_canvas import MaskRefineCanvas


def _reconstruction_image(result: ImageDecompositionResult) -> QImage:
    background = Image.open(result.background_path).convert("RGBA")
    for element in result.elements:
        if element.role == "text" or not element.rgba_path:
            continue
        background.alpha_composite(Image.open(element.rgba_path).convert("RGBA"))
    raw = background.tobytes("raw", "RGBA")
    image = QImage(
        raw,
        background.width,
        background.height,
        background.width * 4,
        QImage.Format_RGBA8888,
    )
    return image.copy()


class LayerExtractionDialog(QDialog):
    def __init__(self, decomposition: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Layer Extraction")
        self.setObjectName("MotionLayerExtractionDialog")
        self.resize(980, 650)
        self._context = {
            "reference_id": str(decomposition.get("reference_id") or ""),
            "beat_id": str(decomposition.get("beat_id") or ""),
        }
        self._result = ImageDecompositionResult.from_dict(decomposition)
        from app.motion_designer.cutout_quality import (
            evaluate_decomposition_cutout_quality,
        )

        evaluate_decomposition_cutout_quality(self._result)

        root = QVBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal, self)
        root.addWidget(splitter, 1)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 6, 0)
        left_layout.addWidget(QLabel("LAYERS", left))
        self.layers = QListWidget(left)
        self.layers.setSelectionMode(QListWidget.ExtendedSelection)
        self.layers.currentItemChanged.connect(self._load_selected_mask)
        left_layout.addWidget(self.layers, 1)
        self.parent_combo = QComboBox(left)
        self.parent_combo.setToolTip("Parent selected layers to another visual layer")
        left_layout.addWidget(self.parent_combo)
        parent_row = QHBoxLayout()
        self.parent_button = QPushButton("Set Parent", left)
        self.parent_button.clicked.connect(self._set_parent)
        parent_row.addWidget(self.parent_button)
        clear_parent = QPushButton("Clear", left)
        clear_parent.clicked.connect(self._clear_parent)
        parent_row.addWidget(clear_parent)
        left_layout.addLayout(parent_row)
        pivot_row = QHBoxLayout()
        self.pivot_x = QDoubleSpinBox(left)
        self.pivot_x.setRange(0, self._result.width)
        self.pivot_x.setPrefix("X ")
        pivot_row.addWidget(self.pivot_x)
        self.pivot_y = QDoubleSpinBox(left)
        self.pivot_y.setRange(0, self._result.height)
        self.pivot_y.setPrefix("Y ")
        pivot_row.addWidget(self.pivot_y)
        left_layout.addLayout(pivot_row)
        set_pivot = QPushButton("Set Pivot", left)
        set_pivot.clicked.connect(self._set_pivot)
        left_layout.addWidget(set_pivot)

        center = QWidget(splitter)
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(6, 0, 6, 0)
        preview_row = QHBoxLayout()
        self.preview_mode = QComboBox(center)
        self.preview_mode.addItems(["Mask Edit", "Original", "Reconstruction"])
        self.preview_mode.currentIndexChanged.connect(self._update_preview_mode)
        preview_row.addWidget(self.preview_mode)
        preview_row.addStretch(1)
        self.add_brush = QToolButton(center)
        self.add_brush.setText("+")
        self.add_brush.setCheckable(True)
        self.add_brush.setChecked(True)
        self.add_brush.setToolTip("Add to mask")
        self.add_brush.clicked.connect(lambda: self._set_brush_mode("add"))
        preview_row.addWidget(self.add_brush)
        self.remove_brush = QToolButton(center)
        self.remove_brush.setText("-")
        self.remove_brush.setCheckable(True)
        self.remove_brush.setToolTip("Remove from mask")
        self.remove_brush.clicked.connect(lambda: self._set_brush_mode("remove"))
        preview_row.addWidget(self.remove_brush)
        self.radius = QSlider(Qt.Horizontal, center)
        self.radius.setRange(2, 96)
        self.radius.setValue(18)
        self.radius.setMaximumWidth(150)
        self.radius.valueChanged.connect(self.canvas_brush_radius)
        preview_row.addWidget(self.radius)
        center_layout.addLayout(preview_row)
        self.canvas = MaskRefineCanvas(center)
        center_layout.addWidget(self.canvas, 1)
        self.preview = QLabel(center)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumSize(320, 180)
        self.preview.setVisible(False)
        center_layout.addWidget(self.preview, 1)
        self.status = QLabel("", center)
        self.status.setObjectName("MotionAIStatus")
        center_layout.addWidget(self.status)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.addWidget(QLabel("REPAIR", right))
        save_mask = QPushButton("Save Mask", right)
        save_mask.clicked.connect(self._save_mask)
        right_layout.addWidget(save_mask)
        merge = QPushButton("Merge Selected", right)
        merge.clicked.connect(self._merge)
        right_layout.addWidget(merge)
        split_h = QPushButton("Split Horizontal", right)
        split_h.clicked.connect(lambda: self._split("horizontal"))
        right_layout.addWidget(split_h)
        split_v = QPushButton("Split Vertical", right)
        split_v.clicked.connect(lambda: self._split("vertical"))
        right_layout.addWidget(split_v)
        lock = QPushButton("Lock to Background", right)
        lock.clicked.connect(lambda: self._lock(True))
        right_layout.addWidget(lock)
        unlock = QPushButton("Unlock", right)
        unlock.clicked.connect(lambda: self._lock(False))
        right_layout.addWidget(unlock)
        front = QPushButton("Bring Forward", right)
        front.clicked.connect(lambda: self._change_order(1))
        right_layout.addWidget(front)
        back = QPushButton("Send Backward", right)
        back.clicked.connect(lambda: self._change_order(-1))
        right_layout.addWidget(back)
        right_layout.addStretch(1)
        splitter.setSizes([220, 600, 190])

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            parent=self,
        )
        self.buttons.button(QDialogButtonBox.Ok).setText("Use Repaired Layers")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self._refresh()

    def result_dict(self) -> dict:
        result = self._result.to_dict()
        result.update(self._context)
        return result

    def canvas_brush_radius(self, value: int) -> None:
        self.canvas.set_brush_radius(value)

    def _selected_ids(self) -> list[str]:
        return [
            str(item.data(Qt.UserRole) or "")
            for item in self.layers.selectedItems()
            if str(item.data(Qt.UserRole) or "")
        ]

    def _selected_visual(self):
        current = self.layers.currentItem()
        element_id = str(current.data(Qt.UserRole) or "") if current else ""
        return next(
            (
                item for item in self._result.elements
                if item.id == element_id and item.role != "text" and item.mask_path
            ),
            None,
        )

    def _refresh(self, preferred_id: str = "") -> None:
        selected = preferred_id or (
            str(self.layers.currentItem().data(Qt.UserRole) or "")
            if self.layers.currentItem()
            else ""
        )
        self.layers.blockSignals(True)
        self.layers.clear()
        for element in self._result.elements:
            item = QListWidgetItem(element.label)
            item.setData(Qt.UserRole, element.id)
            details = [element.role]
            if element.metadata.get("motion_lock_to_background"):
                details.append("locked")
            if element.metadata.get("parent_id"):
                details.append(f"parent: {element.metadata['parent_id']}")
            item.setToolTip(" / ".join(details))
            self.layers.addItem(item)
            if element.id == selected:
                self.layers.setCurrentItem(item)
        self.layers.blockSignals(False)
        self.parent_combo.clear()
        self.parent_combo.addItem("No parent", "")
        for element in self._result.elements:
            if element.role != "text":
                self.parent_combo.addItem(element.label, element.id)
        if self.layers.currentRow() < 0 and self.layers.count():
            self.layers.setCurrentRow(0)
        self._load_selected_mask()
        validation = self._result.diagnostics.get("validation", {})
        quality = self._result.diagnostics.get("cutout_quality", {})
        accepted = bool(quality.get("accepted"))
        quality_status = str(quality.get("status") or "unavailable")
        self.status.setText(
            f"{len(self._result.elements)} layers / "
            f"cutout {quality_status} / "
            f"integrity {'passed' if validation.get('ok') else 'review required'}"
            + (
                " / Fix the mask before use."
                if not accepted
                else ""
            )
        )
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(accepted)

    def _load_selected_mask(self, *_args) -> None:
        element = self._selected_visual()
        if element is None:
            return
        self.canvas.set_images(
            QImage(self._result.source_path),
            QImage(element.mask_path),
        )
        pivot = list(element.metadata.get("pivot") or [
            element.bbox[0] + element.bbox[2] * 0.5,
            element.bbox[1] + element.bbox[3] * 0.5,
        ])
        self.pivot_x.setValue(float(pivot[0]))
        self.pivot_y.setValue(float(pivot[1]))

    def _update_preview_mode(self, index: int) -> None:
        mask_mode = int(index) == 0
        self.canvas.setVisible(mask_mode)
        self.preview.setVisible(not mask_mode)
        if mask_mode:
            return
        image = (
            QImage(self._result.source_path)
            if int(index) == 1
            else _reconstruction_image(self._result)
        )
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(
            self.preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        ))

    def _set_brush_mode(self, mode: str) -> None:
        self.canvas.set_mode(mode)
        self.add_brush.setChecked(mode == "add")
        self.remove_brush.setChecked(mode == "remove")

    def _apply_edit(self, callback, preferred_id: str = "") -> None:
        try:
            self._result = callback()
        except Exception as exc:
            QMessageBox.warning(self, "Layer Extraction", str(exc))
            return
        self._refresh(preferred_id)

    def _save_mask(self) -> None:
        element = self._selected_visual()
        if element is None:
            return
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as handle:
            path = Path(handle.name)
        try:
            if not self.canvas.mask_image().save(str(path), "PNG"):
                raise RuntimeError("Could not save the edited mask.")
            self._apply_edit(
                lambda: replace_decomposition_element_mask(
                    self._result,
                    element.id,
                    path,
                ),
                element.id,
            )
        finally:
            path.unlink(missing_ok=True)

    def _merge(self) -> None:
        selected = self._selected_ids()
        self._apply_edit(
            lambda: merge_decomposition_elements(self._result, selected)
        )

    def _split(self, axis: str) -> None:
        element = self._selected_visual()
        if element is None:
            return
        self._apply_edit(
            lambda: split_decomposition_element(
                self._result,
                element.id,
                axis=axis,
                position=0.5,
            )
        )

    def _lock(self, locked: bool) -> None:
        selected = self._selected_ids()
        self._apply_edit(
            lambda: set_decomposition_lock(
                self._result,
                selected,
                locked=locked,
            ),
            selected[0] if selected else "",
        )

    def _set_parent(self) -> None:
        children = self._selected_ids()
        parent_id = str(self.parent_combo.currentData() or "")
        self._apply_edit(
            lambda: set_decomposition_parent(
                self._result,
                children,
                parent_id=parent_id,
            ),
            children[0] if children else "",
        )

    def _clear_parent(self) -> None:
        children = self._selected_ids()
        self._apply_edit(
            lambda: set_decomposition_parent(
                self._result,
                children,
                parent_id="",
            ),
            children[0] if children else "",
        )

    def _set_pivot(self) -> None:
        element = self._selected_visual()
        if element is None:
            return
        self._apply_edit(
            lambda: set_decomposition_pivot(
                self._result,
                element.id,
                pivot=(self.pivot_x.value(), self.pivot_y.value()),
            ),
            element.id,
        )

    def _change_order(self, delta: int) -> None:
        element = self._selected_visual()
        if element is None:
            return
        current = int(element.metadata.get("z_order", 0) or 0)
        self._apply_edit(
            lambda: set_decomposition_z_order(
                self._result,
                element.id,
                z_order=current + int(delta),
            ),
            element.id,
        )


__all__ = ["LayerExtractionDialog"]
