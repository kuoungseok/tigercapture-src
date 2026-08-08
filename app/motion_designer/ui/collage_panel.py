"""Compact authoring controls for editable collage boards."""
from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.motion_designer.collage import (
    COLLAGE_ATTACHMENTS,
    COLLAGE_EDGE_MODES,
    COLLAGE_LAYOUTS,
    collage_boards,
)
from app.motion_designer.collage_assets import collage_asset_catalog
from app.motion_designer.schema import MotionComposition, MotionLayer


class CollagePanel(QWidget):
    asset_requested = Signal(str, int)
    create_requested = Signal(str, int)
    edge_requested = Signal(str, float, float, int)
    attachment_requested = Signal(str, str, float, float)
    scan_requested = Signal(float, float, float, float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._board_id = ""
        self._item_id = ""
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        heading = QLabel("Mixed Media Collage", self)
        heading.setObjectName("MotionInspectorSection")
        root.addWidget(heading)
        self.status = QLabel(
            "Select a layer, create a board, then refine its edge and attachment.",
            self,
        )
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        form = QFormLayout()
        self.asset = QComboBox(self)
        for row in collage_asset_catalog():
            self.asset.addItem(str(row["name"]), str(row["id"]))
            self.asset.setItemData(
                self.asset.count() - 1,
                str(row["description"]),
                3,
            )
        form.addRow("Starter Material", self.asset)
        self.layout_mode = QComboBox(self)
        for value in COLLAGE_LAYOUTS:
            self.layout_mode.addItem(value.replace("_", " ").title(), value)
        self.seed = QSpinBox(self)
        self.seed.setRange(0, 2_147_483_647)
        self.seed.setValue(17)
        form.addRow("Board Layout", self.layout_mode)
        form.addRow("Locked Seed", self.seed)

        self.edge_mode = QComboBox(self)
        for value in COLLAGE_EDGE_MODES:
            self.edge_mode.addItem(value.title(), value)
        self.roughness = QDoubleSpinBox(self)
        self.roughness.setRange(0.0, 1.0)
        self.roughness.setSingleStep(0.05)
        self.roughness.setValue(0.35)
        self.feather = QDoubleSpinBox(self)
        self.feather.setRange(0.0, 64.0)
        self.feather.setSingleStep(0.5)
        form.addRow("Edge", self.edge_mode)
        form.addRow("Roughness", self.roughness)
        form.addRow("Feather", self.feather)

        self.attachment = QComboBox(self)
        for value in COLLAGE_ATTACHMENTS:
            self.attachment.addItem(value.title(), value)
        self.strength = QDoubleSpinBox(self)
        self.strength.setRange(0.0, 1.0)
        self.strength.setSingleStep(0.05)
        self.strength.setValue(0.35)
        self.angle = QDoubleSpinBox(self)
        self.angle.setRange(-180.0, 180.0)
        self.angle.setSingleStep(1.0)
        form.addRow("Attachment", self.attachment)
        form.addRow("Strength", self.strength)
        form.addRow("Angle", self.angle)

        self.white_balance = QDoubleSpinBox(self)
        self.white_balance.setRange(0.0, 1.0)
        self.white_balance.setSingleStep(0.05)
        self.white_balance.setValue(0.8)
        self.paper_remove = QDoubleSpinBox(self)
        self.paper_remove.setRange(0.0, 1.0)
        self.paper_remove.setSingleStep(0.05)
        self.ink_preserve = QDoubleSpinBox(self)
        self.ink_preserve.setRange(0.0, 1.0)
        self.ink_preserve.setSingleStep(0.05)
        self.ink_preserve.setValue(0.75)
        form.addRow("Scan White Balance", self.white_balance)
        form.addRow("Remove Paper", self.paper_remove)
        form.addRow("Preserve Ink", self.ink_preserve)
        root.addLayout(form)

        buttons = QHBoxLayout()
        self.asset_button = QPushButton("Add Material", self)
        self.create_button = QPushButton("Create Board", self)
        self.edge_button = QPushButton("Apply Edge", self)
        self.attachment_button = QPushButton("Attach", self)
        self.scan_button = QPushButton("Clean Scan", self)
        root.addWidget(self.asset_button)
        buttons.addWidget(self.create_button)
        buttons.addWidget(self.edge_button)
        buttons.addWidget(self.attachment_button)
        buttons.addWidget(self.scan_button)
        root.addLayout(buttons)
        root.addStretch(1)

        self.asset_button.clicked.connect(
            lambda: self.asset_requested.emit(
                str(self.asset.currentData()),
                self.seed.value(),
            ),
        )
        self.create_button.clicked.connect(
            lambda: self.create_requested.emit(
                str(self.layout_mode.currentData()),
                self.seed.value(),
            ),
        )
        self.edge_button.clicked.connect(
            lambda: self.edge_requested.emit(
                str(self.edge_mode.currentData()),
                self.roughness.value(),
                self.feather.value(),
                self.seed.value(),
            ),
        )
        self.attachment_button.clicked.connect(
            lambda: self.attachment_requested.emit(
                str(self.attachment.currentData()),
                "#D8D0B099",
                self.strength.value(),
                self.angle.value(),
            ),
        )
        self.scan_button.clicked.connect(
            lambda: self.scan_requested.emit(
                self.white_balance.value(),
                self.paper_remove.value(),
                self.ink_preserve.value(),
                0.72,
            ),
        )
        self.set_context(None, None)

    def set_context(
        self,
        composition: MotionComposition | None,
        layer: MotionLayer | None,
    ) -> None:
        self._board_id = ""
        self._item_id = ""
        if composition is not None and layer is not None:
            for board in collage_boards(composition):
                for item in board.get("items", []):
                    if (
                        isinstance(item, Mapping)
                        and str(item.get("layer_id") or "") == layer.id
                    ):
                        self._board_id = str(board.get("id") or "")
                        self._item_id = str(item.get("id") or "")
                        edge = item.get("edge")
                        if isinstance(edge, Mapping):
                            index = self.edge_mode.findData(str(edge.get("mode") or "smart"))
                            if index >= 0:
                                self.edge_mode.setCurrentIndex(index)
                            self.roughness.setValue(float(edge.get("roughness", 0.35)))
                            self.feather.setValue(float(edge.get("feather", 0.0)))
                            self.seed.setValue(int(edge.get("seed", 17)))
                        attachment = item.get("attachment")
                        if isinstance(attachment, Mapping):
                            index = self.attachment.findData(
                                str(attachment.get("kind") or "none"),
                            )
                            if index >= 0:
                                self.attachment.setCurrentIndex(index)
                            self.strength.setValue(float(attachment.get("strength", 0.35)))
                            self.angle.setValue(float(attachment.get("angle", 0.0)))
                        scan = item.get("scan_cleanup")
                        if isinstance(scan, Mapping):
                            self.white_balance.setValue(
                                float(scan.get("white_balance", 0.8)),
                            )
                            self.paper_remove.setValue(
                                float(scan.get("paper_remove", 0.0)),
                            )
                            self.ink_preserve.setValue(
                                float(scan.get("ink_preserve", 0.75)),
                            )
                        break
                if self._item_id:
                    break
        selected = layer is not None
        linked = bool(self._board_id and self._item_id)
        self.asset_button.setEnabled(True)
        self.create_button.setEnabled(selected and not linked)
        self.edge_button.setEnabled(linked)
        self.attachment_button.setEnabled(linked)
        self.scan_button.setEnabled(linked)
        self.status.setText(
            f"Board {self._board_id} / Item {self._item_id}"
            if linked
            else (
                "Selected layer is ready for a new collage board."
                if selected
                else "Select a layer to start a collage board."
            )
        )

    @property
    def board_id(self) -> str:
        return self._board_id

    @property
    def item_id(self) -> str:
        return self._item_id


__all__ = ["CollagePanel"]
