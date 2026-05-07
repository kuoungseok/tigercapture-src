"""New Project Dialog — canvas ratio, resolution, fps."""
from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget,
)


@dataclass
class ProjectSettings:
    name: str = "새 프로젝트"
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    ratio_label: str = "16:9"


# ── Aspect-ratio presets ───────────────────────────────────────────────────

_RATIOS = [
    # (label, w, h, description, icon_w, icon_h)
    ("16:9",  16, 9,  "유튜브 · 일반 가로",  48, 27),
    ("9:16",   9, 16, "쇼츠 · 릴스 · 틱톡",  27, 48),
    ("1:1",    1,  1, "인스타그램 정방형",    36, 36),
    ("4:3",    4,  3, "클래식",              40, 30),
    ("21:9",  21,  9, "시네마스코프",        54, 23),
    ("4:5",    4,  5, "인스타 세로",         32, 40),
]

_RESOLUTIONS = {
    "16:9":  [("4K  3840×2160", 3840, 2160),
              ("1080p  1920×1080", 1920, 1080),
              ("720p  1280×720", 1280, 720)],
    "9:16":  [("4K  2160×3840", 2160, 3840),
              ("1080p  1080×1920", 1080, 1920),
              ("720p  720×1280", 720, 1280)],
    "1:1":   [("1080  1080×1080", 1080, 1080),
              ("720  720×720", 720, 720)],
    "4:3":   [("1080p  1440×1080", 1440, 1080),
              ("720p  960×720", 960, 720)],
    "21:9":  [("1080p  2560×1080", 2560, 1080),
              ("720p  1720×720", 1720, 720)],
    "4:5":   [("1080p  864×1080", 864, 1080),
              ("720p  576×720", 576, 720)],
}

_FPS_OPTIONS = [("23.976", 23.976), ("24", 24.0), ("25", 25.0),
                ("30", 30.0), ("60", 60.0)]


# ── Ratio card widget ──────────────────────────────────────────────────────

class _RatioCard(QWidget):
    def __init__(self, label, w_ratio, h_ratio, desc, icon_w, icon_h, parent=None):
        super().__init__(parent)
        self.label = label
        self.w_ratio = w_ratio
        self.h_ratio = h_ratio
        self._selected = False
        self.setFixedSize(88, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_w = icon_w
        self._icon_h = icon_h
        self._desc = desc

    def set_selected(self, v: bool):
        self._selected = v
        self.update()

    def mousePressEvent(self, e):
        self.parent().parent()._select_ratio(self.label)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        # Background
        bg = QColor("#2a2a38") if not self._selected else QColor("#1e2a4a")
        border = QColor("#5070c8") if self._selected else QColor("#3a3a4a")
        p.setBrush(bg)
        p.setPen(QPen(border, 2 if self._selected else 1))
        p.drawRoundedRect(2, 2, W-4, H-4, 8, 8)
        # Icon rect
        iw, ih = self._icon_w, self._icon_h
        ix = (W - iw) // 2
        iy = 14
        icon_bg = QColor("#3a4060") if not self._selected else QColor("#2a3a70")
        icon_border = QColor("#6080e0") if self._selected else QColor("#5060a0")
        p.setBrush(icon_bg)
        p.setPen(QPen(icon_border, 1))
        p.drawRoundedRect(ix, iy, iw, ih, 3, 3)
        # Label
        f = QFont()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff") if self._selected else QColor("#ccccdd"))
        p.drawText(QRect(0, iy + ih + 6, W, 18), Qt.AlignmentFlag.AlignCenter, self.label)
        # Desc
        f2 = QFont()
        f2.setPixelSize(9)
        p.setFont(f2)
        p.setPen(QColor("#8888aa"))
        p.drawText(QRect(2, iy + ih + 26, W-4, 28),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                   self._desc)
        p.end()


# ── Dialog ─────────────────────────────────────────────────────────────────

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새 프로젝트")
        self.setMinimumWidth(560)
        self.setStyleSheet("background:#1a1a24; color:#ccccdd;")
        self._ratio = "16:9"
        self._cards: dict[str, _RatioCard] = {}
        self.result_settings: ProjectSettings | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("새 프로젝트")
        f = title.font(); f.setPixelSize(18); f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color:#ffffff;")
        root.addWidget(title)

        # Project name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("프로젝트 이름"))
        self._name_edit = QLineEdit("새 프로젝트")
        self._name_edit.setStyleSheet(
            "background:#2a2a38; border:1px solid #44445a; border-radius:4px;"
            "padding:4px 8px; color:#ffffff; font-size:13px;"
        )
        name_row.addWidget(self._name_edit)
        root.addLayout(name_row)

        # Ratio cards
        ratio_lbl = QLabel("화면 비율")
        ratio_lbl.setStyleSheet("font-weight:bold; font-size:12px; color:#aaaacc;")
        root.addWidget(ratio_lbl)

        cards_container = QWidget()
        cards_layout = QHBoxLayout(cards_container)
        cards_layout.setSpacing(8)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        for label, wr, hr, desc, iw, ih in _RATIOS:
            card = _RatioCard(label, wr, hr, desc, iw, ih, cards_container)
            cards_layout.addWidget(card)
            self._cards[label] = card
        cards_layout.addStretch()
        root.addWidget(cards_container)

        # Resolution + FPS row
        settings_row = QHBoxLayout()

        res_grp = QGroupBox("해상도")
        res_grp.setStyleSheet(
            "QGroupBox{border:1px solid #33334a; border-radius:6px; margin-top:8px;"
            "padding-top:4px; color:#aaaacc; font-size:11px;}"
            "QGroupBox::title{subcontrol-origin:margin; left:8px;}"
        )
        res_inner = QVBoxLayout(res_grp)
        self._res_combo = QComboBox()
        self._res_combo.setStyleSheet(
            "background:#2a2a38; border:1px solid #44445a; border-radius:4px;"
            "padding:4px 8px; color:#ffffff; font-size:12px;"
        )
        res_inner.addWidget(self._res_combo)
        settings_row.addWidget(res_grp, 2)

        fps_grp = QGroupBox("프레임 레이트")
        fps_grp.setStyleSheet(res_grp.styleSheet())
        fps_inner = QVBoxLayout(fps_grp)
        self._fps_combo = QComboBox()
        self._fps_combo.setStyleSheet(self._res_combo.styleSheet())
        for label, _ in _FPS_OPTIONS:
            self._fps_combo.addItem(f"{label} fps")
        self._fps_combo.setCurrentIndex(3)   # 30fps default
        fps_inner.addWidget(self._fps_combo)
        settings_row.addWidget(fps_grp, 1)

        root.addLayout(settings_row)

        # Buttons
        btns = QDialogButtonBox()
        create_btn = QPushButton("프로젝트 만들기")
        create_btn.setDefault(True)
        create_btn.setStyleSheet(
            "QPushButton{background:#4060c0; color:#fff; border:none; border-radius:6px;"
            "padding:8px 24px; font-size:13px; font-weight:bold;}"
            "QPushButton:hover{background:#5070d0;}"
        )
        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(
            "QPushButton{background:#2a2a38; color:#aaa; border:1px solid #44445a;"
            "border-radius:6px; padding:8px 16px; font-size:13px;}"
            "QPushButton:hover{background:#33334a;}"
        )
        btns.addButton(create_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        btns.accepted.connect(self._on_create)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # Init
        self._select_ratio("16:9")

    def _select_ratio(self, label: str):
        self._ratio = label
        for lbl, card in self._cards.items():
            card.set_selected(lbl == label)
        # Refresh resolution combo
        self._res_combo.clear()
        for res_label, w, h in _RESOLUTIONS.get(label, []):
            self._res_combo.addItem(res_label, (w, h))

    def _on_create(self):
        name = self._name_edit.text().strip() or "새 프로젝트"
        res_data = self._res_combo.currentData()
        if res_data:
            w, h = res_data
        else:
            w, h = 1920, 1080
        fps_label = _FPS_OPTIONS[self._fps_combo.currentIndex()][0]
        fps_val = _FPS_OPTIONS[self._fps_combo.currentIndex()][1]
        self.result_settings = ProjectSettings(
            name=name, width=w, height=h, fps=fps_val, ratio_label=self._ratio,
        )
        self.accept()
