"""Inspector panel — shows and edits selected bone properties."""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QGroupBox,
)
from app.spine_editor.spine_data import SpineSkeleton, Bone


class BoneInspector(QWidget):
    bone_changed = Signal(str)   # bone name

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._bone_name: Optional[str] = None
        self._updating = False
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        self._lbl = QLabel("뼈대를 선택하세요")
        self._lbl.setStyleSheet("color:#A7ADC2; font-size:11px; padding:8px;")
        lay.addWidget(self._lbl)

        self._grp = QGroupBox("로컬 변환")
        self._grp.setStyleSheet(
            "QGroupBox{background:#111421;border:1px solid #30384F;border-radius:14px;margin-top:10px;"
            "color:#A7ADC2;font-size:10px;font-weight:800;}"
            "QGroupBox::title{subcontrol-origin:margin;left:10px;padding:0 6px;}"
        )
        form = QFormLayout(self._grp)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def spinbox(lo=-9999, hi=9999, dec=1, step=1.0):
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi); sb.setDecimals(dec); sb.setSingleStep(step)
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setStyleSheet("QDoubleSpinBox{background:rgba(255,255,255,13);color:#EEF0F8;"
                             "border:1px solid #30384F;border-radius:12px;padding:5px 8px;}"
                             "QDoubleSpinBox:focus{border-color:#8A7CFF;}")
            return sb

        self._x   = spinbox(); self._x.valueChanged.connect(self._on_changed)
        self._y   = spinbox(); self._y.valueChanged.connect(self._on_changed)
        self._rot = spinbox(-360, 360, 1, 1.0); self._rot.valueChanged.connect(self._on_changed)
        self._len = spinbox(0, 9999, 0, 5.0); self._len.valueChanged.connect(self._on_changed)

        form.addRow("X:", self._x)
        form.addRow("Y:", self._y)
        form.addRow("회전(°):", self._rot)
        form.addRow("길이:", self._len)
        lay.addWidget(self._grp)
        lay.addStretch()
        self._grp.hide()

    def set_skeleton(self, skel: SpineSkeleton) -> None:
        self._skeleton = skel

    def set_bone(self, name: str) -> None:
        self._bone_name = name
        if not name or not self._skeleton:
            self._lbl.show(); self._grp.hide(); return
        bone = self._skeleton.bone(name)
        if not bone:
            self._lbl.show(); self._grp.hide(); return
        self._lbl.hide(); self._grp.show()
        self._lbl.setText(name)
        self._updating = True
        self._x.setValue(bone.x); self._y.setValue(bone.y)
        self._rot.setValue(bone.rotation); self._len.setValue(bone.length)
        self._updating = False

    def _on_changed(self):
        if self._updating or not self._bone_name or not self._skeleton:
            return
        bone = self._skeleton.bone(self._bone_name)
        if bone:
            bone.x = self._x.value(); bone.y = self._y.value()
            bone.rotation = self._rot.value(); bone.length = self._len.value()
            self._skeleton.update_world_transforms()
            self.bone_changed.emit(self._bone_name)
