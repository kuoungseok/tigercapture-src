"""Photoshop-style layer panel for the Spine editor.

Shows each slot as a visual layer with texture thumbnail,
visibility toggle, and selection. Much friendlier than a bone tree.
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QPixmap, QImage, QPainter, QFont, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QFrame, QPushButton, QSizePolicy,
)

from app.style import editor_scrollbar_qss
from app.spine_editor.spine_data import SpineSkeleton, RegionAttachment


class _LayerItem(QWidget):
    """One row: eye | thumbnail | name | type-badge."""

    visibility_toggled = Signal(str, bool)   # slot_name, visible
    selected = Signal(str)                   # slot_name

    _SS_BASE = """
        QWidget#LayerItem {{
            background: {bg};
            border-bottom: 1px solid #20263A;
        }}
    """
    _THUMB_SIZE = 40

    def __init__(self, slot_name: str, attach_name: str,
                 thumb: Optional[QPixmap], parent=None):
        super().__init__(parent)
        self.setObjectName("LayerItem")
        self._slot_name = slot_name
        self._visible = True
        self._selected = False
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(6)

        # Eye button
        self._eye = QPushButton("👁")
        self._eye.setFixedSize(24, 24)
        self._eye.setStyleSheet(
            "QPushButton{background:rgba(255,255,255,12);border:1px solid #30384F;border-radius:10px;font-size:14px;color:#E8EAF4;}"
            "QPushButton:hover{background:rgba(255,255,255,28);border-color:#7580A5;color:#fff;}"
        )
        self._eye.clicked.connect(self._toggle_visibility)
        lay.addWidget(self._eye)

        # Thumbnail
        self._thumb_lbl = QLabel()
        self._thumb_lbl.setFixedSize(self._THUMB_SIZE, self._THUMB_SIZE)
        self._thumb_lbl.setStyleSheet(
            "background:#0B0D16; border:1px solid #30384F; border-radius:9px;"
        )
        self._thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if thumb:
            scaled = thumb.scaled(self._THUMB_SIZE, self._THUMB_SIZE,
                                  Qt.AspectRatioMode.KeepAspectRatio,
                                  Qt.TransformationMode.SmoothTransformation)
            self._thumb_lbl.setPixmap(scaled)
        else:
            self._thumb_lbl.setText("?")
            self._thumb_lbl.setStyleSheet(
                "background:#111421;color:#6F7484;font-size:10px;"
                "border:1px solid #30384F;border-radius:9px;"
            )
        lay.addWidget(self._thumb_lbl)

        # Name column
        name_col = QVBoxLayout()
        name_col.setSpacing(2)

        slot_lbl = QLabel(slot_name)
        slot_lbl.setStyleSheet("color:#E8EAF4;font-size:10px;font-weight:bold;")
        slot_lbl.setWordWrap(False)
        name_col.addWidget(slot_lbl)

        if attach_name:
            attach_lbl = QLabel(attach_name)
            attach_lbl.setStyleSheet("color:#A7ADC2;font-size:9px;")
            name_col.addWidget(attach_lbl)

        lay.addLayout(name_col, 1)

        self._update_style()

    def _toggle_visibility(self):
        self._visible = not self._visible
        self._eye.setText("👁" if self._visible else "🚫")
        self.visibility_toggled.emit(self._slot_name, self._visible)
        self._update_style()

    def set_selected(self, sel: bool):
        self._selected = sel
        self._update_style()

    def _update_style(self):
        if self._selected:
            bg = "#251F3E"
            border = "border-left: 3px solid #FF8057;"
        elif not self._visible:
            bg = "#0F121D"
            border = "border-left: 3px solid transparent;"
        else:
            bg = "#111421"
            border = "border-left: 3px solid transparent;"
        self.setStyleSheet(
            f"QWidget#LayerItem{{background:{bg};border-bottom:1px solid #20263A;{border}}}"
        )
        self._thumb_lbl.setOpacity = None  # no-op
        self.setEnabled(True)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._slot_name)
        super().mousePressEvent(e)

    @property
    def slot_name(self) -> str:
        return self._slot_name

    @property
    def visible(self) -> bool:
        return self._visible


class LayerPanel(QWidget):
    """Full layer panel — shows all slots in draw order with thumbnails."""

    slot_selected = Signal(str)             # slot_name
    slot_visibility_changed = Signal(str, bool)  # slot_name, visible

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._atlas: dict = {}
        self._pil_pages: list = []
        self._items: list[_LayerItem] = []
        self._selected_slot: Optional[str] = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setStyleSheet("background:#111421;")
        hdr.setFixedHeight(28)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(8, 0, 8, 0)
        lbl = QLabel("레이어")
        lbl.setStyleSheet("color:#A7ADC2;font-size:10px;font-weight:bold;")
        hl.addWidget(lbl)
        hl.addStretch()

        # Show all / Hide all buttons
        for label, tip, fn in [("👁 전체", "모두 표시", self._show_all),
                                ("🚫 전체", "모두 숨기기", self._hide_all)]:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(20)
            btn.setStyleSheet(
                "QPushButton{background:rgba(255,255,255,18);color:#A7ADC2;border:1px solid #37405A;"
                "border-radius:10px;padding:0 7px;font-size:9px;font-weight:700;}"
                "QPushButton:hover{background:rgba(255,255,255,30);border-color:#7580A5;color:#fff;}"
            )
            btn.clicked.connect(fn)
            hl.addWidget(btn)

        lay.addWidget(hdr)

        # Scroll area for layer items
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            "QScrollArea{border:none;background:#0B0D16;}"
            "QScrollBar:vertical{width:8px;background:transparent;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,38);border-radius:4px;}"
            + editor_scrollbar_qss()
        )

        self._container = QWidget()
        self._container.setStyleSheet("background:#0B0D16;")
        self._container_lay = QVBoxLayout(self._container)
        self._container_lay.setContentsMargins(0, 0, 0, 0)
        self._container_lay.setSpacing(0)
        self._container_lay.addStretch()

        self._scroll.setWidget(self._container)
        lay.addWidget(self._scroll, 1)

        # Status bar
        self._status = QLabel("슬롯 없음")
        self._status.setStyleSheet(
            "color:#A7ADC2;font-size:9px;padding:4px 7px;"
            "background:#0F121D;border-top:1px solid #20263A;"
        )
        lay.addWidget(self._status)

    # ── public API ────────────────────────────────────────────────────────

    def set_data(self, skeleton: SpineSkeleton, atlas: dict, pil_pages: list) -> None:
        self._skeleton = skeleton
        self._atlas = atlas
        self._pil_pages = pil_pages
        self._rebuild()

    def set_skeleton(self, skeleton: SpineSkeleton) -> None:
        self._skeleton = skeleton
        self._rebuild()

    def select_slot(self, slot_name: str) -> None:
        self._selected_slot = slot_name
        for item in self._items:
            item.set_selected(item.slot_name == slot_name)

    def hidden_slots(self) -> set[str]:
        return {item.slot_name for item in self._items if not item.visible}

    # ── internals ─────────────────────────────────────────────────────────

    def _rebuild(self) -> None:
        # Remove old items
        for item in self._items:
            self._container_lay.removeWidget(item)
            item.deleteLater()
        self._items.clear()

        if not self._skeleton:
            self._status.setText("슬롯 없음")
            return

        # Build merged skin for thumbnail lookup
        skin_name = "default"
        merged: dict = {}
        for sn, atts in self._skeleton.skins.get("default", {}).items():
            merged[sn] = dict(atts)

        # Add items in REVERSE draw order (top layer first = visually on top)
        slots_reversed = list(reversed(self._skeleton.slots))
        stretch_idx = self._container_lay.count() - 1  # last item is stretch

        for slot in slots_reversed:
            attach = merged.get(slot.name, {}).get(slot.attachment)
            thumb = self._make_thumb(attach)

            item = _LayerItem(
                slot_name=slot.name,
                attach_name=slot.attachment or "",
                thumb=thumb,
            )
            item.visibility_toggled.connect(self._on_visibility)
            item.selected.connect(self._on_selected)
            self._container_lay.insertWidget(stretch_idx, item)
            self._items.append(item)

        n = len(self._skeleton.slots)
        self._status.setText(f"슬롯 {n}개")

    def _make_thumb(self, attach) -> Optional[QPixmap]:
        """Extract and return a small QPixmap for this attachment."""
        if not isinstance(attach, RegionAttachment) or not self._atlas or not self._pil_pages:
            return None
        try:
            region_name = attach.path or attach.name
            entry = self._atlas.get(region_name)
            if entry is None:
                return None
            page_idx, rx, ry, rw, rh = entry[0], entry[1], entry[2], entry[3], entry[4]
            if page_idx >= len(self._pil_pages) or self._pil_pages[page_idx] is None:
                return None
            pil = self._pil_pages[page_idx]
            tw, th = pil.size
            crop = pil.crop((rx, ry, min(rx+rw, tw), min(ry+rh, th)))
            if crop.mode != "RGBA":
                crop = crop.convert("RGBA")
            data = crop.tobytes("raw", "RGBA")
            qimg = QImage(data, crop.width, crop.height, crop.width*4,
                          QImage.Format.Format_RGBA8888).copy()
            return QPixmap.fromImage(qimg)
        except Exception:
            return None

    def _on_visibility(self, slot_name: str, visible: bool):
        self.slot_visibility_changed.emit(slot_name, visible)

    def _on_selected(self, slot_name: str):
        self._selected_slot = slot_name
        for item in self._items:
            item.set_selected(item.slot_name == slot_name)
        self.slot_selected.emit(slot_name)

    def _show_all(self):
        for item in self._items:
            if not item.visible:
                item._toggle_visibility()

    def _hide_all(self):
        for item in self._items:
            if item.visible:
                item._toggle_visibility()
