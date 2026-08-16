"""Shared fill/stroke stack editor for Painter UI inspectors."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
)

from app.painter_ui_advanced_appearance import normalize_ui_paint, normalize_ui_paints
from app.painter_ui_fill_component import FILL_TYPES, PainterUIFillComponent, _hex_color


_TYPE_LABELS = {
    "solid": "단색",
    "linear": "선형",
    "radial": "방사형",
    "pattern": "패턴",
    "image": "이미지",
    "video": "동영상",
    "shader": "셰이더",
}


class PainterUIPaintDialog(QDialog):
    """Dialog shell around the single shared fill component."""

    def __init__(self, paint: Mapping[str, Any], *, stroke: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIPaintDialog")
        self.setWindowTitle("외곽선" if stroke else "채우기")
        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(360)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.fill_component = PainterUIFillComponent(paint, stroke=stroke, parent=self)
        root.addWidget(self.fill_component, 1)
        self.fill_component.close_requested.connect(self.accept)
        self.fill_component.fill_type_changed.connect(self._resize_for_type)
        self._resize_for_type(str(self.fill_component._active_type))

        # Compatibility names used by existing automation and tests.
        self.type_combo = _FillTypeComboAdapter(self.fill_component)
        for name in (
            "pages", "color_edit", "opacity_slider", "blend_combo",
            "gradient_kind", "pattern_kind", "pattern_scale", "pattern_source",
            "image_path", "image_fit", "video_path", "video_fit", "shader_combo",
        ):
            setattr(self, name, getattr(self.fill_component, name))

    def paint(self) -> dict[str, Any]:
        return self.fill_component.paint()

    def _resize_for_type(self, kind: str) -> None:
        heights = {
            "solid": 535,
            "linear": 430,
            "radial": 430,
            "pattern": 650,
            "image": 790,
            "video": 650,
            "shader": 560,
        }
        self.setFixedHeight(heights.get(str(kind), 650))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.accept()
        event.accept()


class _FillTypeComboAdapter:
    """Small compatibility adapter for the former QComboBox API."""

    _values = ("solid", "linear", "radial", "pattern", "image", "video", "shader")

    def __init__(self, component: PainterUIFillComponent) -> None:
        self._component = component

    def count(self) -> int:
        return len(self._values)

    def itemData(self, index: int) -> str | None:  # noqa: N802
        return self._values[index] if 0 <= index < len(self._values) else None

    def findData(self, value: object) -> int:  # noqa: N802
        try:
            return self._values.index(str(value))
        except ValueError:
            return -1

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        if 0 <= index < len(self._values):
            kind = self._values[index]
            self._component.set_fill_type(kind)
            if kind in {"linear", "radial"}:
                self._component.gradient_kind.setCurrentIndex(
                    max(0, self._component.gradient_kind.findData(kind))
                )

    def currentData(self) -> str:  # noqa: N802
        return self._component._active_type


class PainterUIPaintStackEditor(QFrame):
    """Reusable stack used by frame, shape, text and future inspectors."""

    paints_changed = Signal(object)

    def __init__(self, title: str, *, stroke: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIPaintStackEditor")
        self._stroke = bool(stroke)
        self._paints: list[dict[str, Any]] = []
        self.setStyleSheet(
            """
            QFrame#PainterUIPaintStackEditor { background:transparent; border:none; }
            QLabel#PainterUIPaintStackTitle { color:#E1E7EF; font-weight:650; }
            QFrame#PainterUIPaintRow { background:#11161D; border:1px solid #2D3744; border-radius:5px; }
            QToolButton { background:transparent; color:#DDE5EF; border:none; min-width:24px; min-height:26px; }
            QToolButton:hover { background:#293442; border-radius:4px; }
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 2, 0, 2)
        root.setSpacing(4)
        header = QHBoxLayout()
        label = QLabel(title); label.setObjectName("PainterUIPaintStackTitle")
        header.addWidget(label); header.addStretch(1)
        add = QToolButton(); add.setText("+"); add.setToolTip(f"{title} 추가")
        add.clicked.connect(self._add); header.addWidget(add)
        root.addLayout(header)
        self.rows_layout = QVBoxLayout(); self.rows_layout.setContentsMargins(0, 0, 0, 0); self.rows_layout.setSpacing(3)
        root.addLayout(self.rows_layout)

    def set_paints(self, value: object) -> None:
        self._paints = normalize_ui_paints(value, stroke=self._stroke)
        self._rebuild()

    def paints(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._paints)

    def _clear_rows(self) -> None:
        # Each row's buttons connect to a lambda that closes over ``self``, and
        # ``self`` owns the row through this layout -- a reference cycle that
        # only Python's cyclic GC can break. ``deleteLater`` alone leaves that
        # cycle standing until GC gets around to it, which on a document with
        # frequent selection changes showed up as periodic multi-hundred-ms
        # stalls. Disconnecting here breaks the cycle immediately instead of
        # waiting on GC.
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                for button in widget.findChildren(QToolButton):
                    try:
                        button.clicked.disconnect()
                    except (RuntimeError, TypeError):
                        pass
                widget.deleteLater()

    def _rebuild(self) -> None:
        self._clear_rows()
        for index, paint in enumerate(self._paints):
            row = QFrame(); row.setObjectName("PainterUIPaintRow")
            layout = QHBoxLayout(row); layout.setContentsMargins(5, 2, 3, 2); layout.setSpacing(3)
            visible = QToolButton(); visible.setText("◉" if paint.get("visible", True) else "○")
            visible.clicked.connect(lambda _=False, i=index: self._toggle(i)); layout.addWidget(visible)
            swatch = QToolButton()
            swatch.setObjectName("PainterUIPaintSwatch")
            swatch.setFixedSize(22, 22)
            swatch.setCursor(Qt.CursorShape.PointingHandCursor)
            swatch.setToolTip("색상 및 채우기 편집")
            color = _hex_color(str(paint.get("color") or "#FFFFFFFF"))
            swatch.setStyleSheet(
                f"QToolButton#PainterUIPaintSwatch {{ background:{color.name()}; "
                "border:1px solid #9AA5B1; border-radius:4px; padding:0; }}"
                "QToolButton#PainterUIPaintSwatch:hover { border:2px solid #168CFF; }"
            )
            swatch.clicked.connect(lambda _=False, i=index: self._edit(i))
            layout.addWidget(swatch)
            edit = QToolButton(); edit.setText(_TYPE_LABELS.get(str(paint.get("type")), "채우기"))
            edit.clicked.connect(lambda _=False, i=index: self._edit(i)); layout.addWidget(edit, 1)
            opacity = QLabel(f"{round(float(paint.get('opacity', 1.0)) * 100)}%")
            opacity.setStyleSheet("color:#AAB5C3;"); layout.addWidget(opacity)
            remove = QToolButton(); remove.setText("−"); remove.clicked.connect(lambda _=False, i=index: self._remove(i)); layout.addWidget(remove)
            self.rows_layout.addWidget(row)

    def _add(self) -> None:
        paint = normalize_ui_paint({"type": "solid", "color": "#FFFFFFFF", "width": 1.0, "align": "center"}, stroke=self._stroke)
        dialog = PainterUIPaintDialog(paint, stroke=self._stroke, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._paints.insert(0, dialog.paint()); self._commit()

    def _edit(self, index: int) -> None:
        if not 0 <= index < len(self._paints): return
        dialog = PainterUIPaintDialog(self._paints[index], stroke=self._stroke, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._paints[index] = dialog.paint(); self._commit()

    def _toggle(self, index: int) -> None:
        if 0 <= index < len(self._paints):
            self._paints[index]["visible"] = not bool(self._paints[index].get("visible", True)); self._commit()

    def _remove(self, index: int) -> None:
        if 0 <= index < len(self._paints): self._paints.pop(index); self._commit()

    def _commit(self) -> None:
        self._rebuild(); self.paints_changed.emit(self.paints())


__all__ = ["PainterUIFillComponent", "PainterUIPaintDialog", "PainterUIPaintStackEditor"]
