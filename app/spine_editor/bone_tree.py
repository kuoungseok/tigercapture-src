"""Bone hierarchy tree panel."""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QPushButton, QHBoxLayout,
)
from app.spine_editor.spine_data import SpineSkeleton, Bone


class BoneTreePanel(QWidget):
    bone_selected = Signal(str)   # bone name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._building = False
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        header = QHBoxLayout()
        lbl = QLabel("BONES")
        lbl.setStyleSheet("color:#A7ADC2; font-size:10px; font-weight:800; padding:4px 8px;")
        add_btn = QPushButton("+")
        add_btn.setFixedSize(22, 22)
        add_btn.setStyleSheet("QPushButton{background:rgba(255,255,255,18);color:#E8EAF4;border:1px solid #37405A;border-radius:11px;font-size:14px;font-weight:800;}"
                              "QPushButton:hover{background:rgba(255,255,255,30);border-color:#7580A5;color:#fff;}")
        add_btn.setToolTip("Add child bone")
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(add_btn)
        lay.addLayout(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet("""
            QTreeWidget{background:#0B0D16;border:1px solid #30384F;border-radius:12px;color:#E8EAF4;font-size:11px;}
            QTreeWidget::item{padding:4px 6px;border-radius:8px;}
            QTreeWidget::item:selected{background:#6F5CFF;color:#fff;}
            QTreeWidget::item:hover:!selected{background:rgba(255,255,255,24);}
            QTreeWidget::branch{background:#0B0D16;}
        """)
        self._tree.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self._tree)

    def set_skeleton(self, skel: SpineSkeleton) -> None:
        self._skeleton = skel
        self.refresh()

    def refresh(self) -> None:
        self._building = True
        self._tree.clear()
        if not self._skeleton:
            self._building = False
            return
        items = {}
        for bone in self._skeleton.bones:
            item = QTreeWidgetItem([bone.name])
            item.setData(0, Qt.ItemDataRole.UserRole, bone.name)
            items[bone.name] = item
        for bone in self._skeleton.bones:
            item = items[bone.name]
            if bone.parent and bone.parent in items:
                items[bone.parent].addChild(item)
            else:
                self._tree.addTopLevelItem(item)
        self._tree.expandAll()
        self._building = False

    def select_bone(self, name: str) -> None:
        self._building = True
        self._tree.clearSelection()
        for i in range(self._tree.topLevelItemCount()):
            self._find_and_select(self._tree.topLevelItem(i), name)
        self._building = False

    def _find_and_select(self, item: QTreeWidgetItem, name: str) -> bool:
        if item.data(0, Qt.ItemDataRole.UserRole) == name:
            item.setSelected(True)
            self._tree.scrollToItem(item)
            return True
        for i in range(item.childCount()):
            if self._find_and_select(item.child(i), name):
                return True
        return False

    def _on_item_clicked(self, item: QTreeWidgetItem):
        if not self._building:
            self.bone_selected.emit(item.data(0, Qt.ItemDataRole.UserRole) or "")
