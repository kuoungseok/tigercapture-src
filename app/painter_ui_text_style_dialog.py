"""Figma-style text named-style creation dialog."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class PainterUITextStyleDialog(QDialog):
    style_created = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUITextStyleDialog")
        self.setWindowTitle("새 텍스트 스타일 만들기")
        self.setModal(False)
        self.setMinimumSize(440, 590)
        self.resize(440, 620)
        self.setStyleSheet(
            """
            QDialog#PainterUITextStyleDialog { background:#1E2228; color:#E8EDF4; }
            QLabel { color:#C7D0DB; }
            QLabel#PainterUITextStyleHeading { color:#F4F7FB; font-size:13px; font-weight:700; }
            QLabel#PainterUITextStylePreview { background:#161B22; color:#F5F7FA; border:none; font-size:16px; }
            QLabel#PainterUITextStyleSection { color:#F0F3F7; font-size:11px; font-weight:650; }
            QLineEdit, QComboBox, QFontComboBox, QDoubleSpinBox {
                background:#11161D; color:#EDF2F8; border:1px solid #333D49;
                border-radius:5px; min-height:32px; padding:0 8px;
            }
            QPushButton#PainterUITextStyleCreate {
                background:#168BFF; color:#FFFFFF; border:none; border-radius:6px;
                min-height:36px; padding:0 16px; font-weight:650;
            }
            QPushButton#PainterUITextStyleCreate:hover { background:#0879DF; }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)
        heading = QLabel("새 텍스트 스타일 만들기")
        heading.setObjectName("PainterUITextStyleHeading")
        root.addWidget(heading)
        self.preview = QLabel("Rag 123")
        self.preview.setObjectName("PainterUITextStylePreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(160)
        root.addWidget(self.preview)

        form = QFormLayout()
        form.setContentsMargins(8, 6, 8, 6)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("새 텍스트 스타일")
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("용도는 무엇인가요?")
        form.addRow("이름", self.name_edit)
        form.addRow("설명", self.description_edit)
        root.addLayout(form)
        section = QLabel("속성")
        section.setObjectName("PainterUITextStyleSection")
        root.addWidget(section)
        self.family_combo = QFontComboBox()
        self.family_combo.setCurrentFont(QFont("Inter"))
        root.addWidget(self.family_combo)
        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.weight_combo = QComboBox()
        for label, weight in (
            ("Light", 300),
            ("Regular", 400),
            ("Medium", 500),
            ("Semibold", 600),
            ("Bold", 700),
        ):
            self.weight_combo.addItem(label, weight)
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(1.0, 1000.0)
        self.size_spin.setValue(12.0)
        self.size_spin.setSuffix(" px")
        type_row.addWidget(self.weight_combo, 1)
        type_row.addWidget(self.size_spin, 1)
        root.addLayout(type_row)
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)
        self.line_height_spin = QDoubleSpinBox()
        self.line_height_spin.setRange(0.0, 1000.0)
        self.line_height_spin.setSpecialValueText("자동")
        self.line_height_spin.setSuffix(" px")
        self.letter_spacing_spin = QDoubleSpinBox()
        self.letter_spacing_spin.setRange(-100.0, 1000.0)
        self.letter_spacing_spin.setSuffix(" %")
        metrics_row.addWidget(self.line_height_spin, 1)
        metrics_row.addWidget(self.letter_spacing_spin, 1)
        root.addLayout(metrics_row)
        root.addStretch(1)
        footer = QFrame()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.addStretch(1)
        self.create_button = QPushButton("스타일 만들기")
        self.create_button.setObjectName("PainterUITextStyleCreate")
        self.create_button.clicked.connect(self._create)
        footer_layout.addWidget(self.create_button)
        root.addWidget(footer)
        for control in (
            self.family_combo,
            self.weight_combo,
            self.size_spin,
            self.line_height_spin,
            self.letter_spacing_spin,
        ):
            if hasattr(control, "currentIndexChanged"):
                control.currentIndexChanged.connect(self._sync_preview)
            if hasattr(control, "valueChanged"):
                control.valueChanged.connect(self._sync_preview)
        self._sync_preview()

    def values(self) -> dict:
        line_height = self.line_height_spin.value()
        return {
            "name": self.name_edit.text().strip() or "새 텍스트 스타일",
            "description": self.description_edit.text().strip(),
            "kind": "text",
            "properties": {
                "font_family": self.family_combo.currentFont().family(),
                "font_size": self.size_spin.value(),
                "font_weight": int(self.weight_combo.currentData() or 400),
                "font_style": "normal",
                "line_height": line_height if line_height > 0 else "auto",
                "letter_spacing": self.letter_spacing_spin.value(),
            },
            "token_bindings": {},
        }

    def _sync_preview(self, *_args) -> None:
        font = QFont(self.family_combo.currentFont())
        font.setPointSizeF(max(1.0, self.size_spin.value()))
        font.setWeight(
            QFont.Weight(int(self.weight_combo.currentData() or 400))
        )
        font.setLetterSpacing(
            QFont.SpacingType.PercentageSpacing,
            100.0 + self.letter_spacing_spin.value(),
        )
        self.preview.setFont(font)

    def _create(self) -> None:
        self.style_created.emit(self.values())
        self.accept()


__all__ = ["PainterUITextStyleDialog"]
