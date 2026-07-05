"""New Project Dialog — canvas ratio, resolution, fps."""
from __future__ import annotations
from dataclasses import dataclass
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QFont, QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSizePolicy, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.style import studio_chrome_qss


@dataclass
class ProjectSettings:
    name: str = "새 프로젝트"
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    ratio_label: str = "16:9"
    starter_template_id: str = "blank"
    starter_template_label: str = "Blank"


DEFAULT_STARTER_TEMPLATE_ID = "screen-recording-demo"

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

_STARTER_TEMPLATES = [
    ("blank", "Blank", "Start with an empty timeline"),
    ("screen-recording-demo", "Screen Recording Demo", "Cursor, zoom, caption, and clean background defaults"),
    ("vertical-shorts", "Vertical Shorts", "9:16 hook, captions, sticker, and loudness defaults"),
    ("gameplay-highlight", "Gameplay Highlight", "Fast cuts, zoom emphasis, and punchy audio chain"),
    ("product-demo", "Product Demo", "Clean title, callout, B-roll, and product color starter"),
    ("actor-showcase", "Live2D/Spine Actor", "Actor lane, nameplate, and QA-friendly defaults"),
]

_RATIO_DEFAULT_RES_INDEX = {
    "16:9": 1,
    "9:16": 1,
    "1:1": 0,
    "4:3": 0,
    "21:9": 0,
    "4:5": 0,
}


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
        bg = QColor("#171B2A") if not self._selected else QColor("#422B74")
        border = QColor("#FFF0D8") if self._selected else QColor("#37405A")
        p.setBrush(bg)
        p.setPen(QPen(border, 2 if self._selected else 1))
        p.drawRoundedRect(2, 2, W-4, H-4, 8, 8)
        # Icon rect
        iw, ih = self._icon_w, self._icon_h
        ix = (W - iw) // 2
        iy = 14
        icon_bg = QColor("#252C45") if not self._selected else QColor("#6F5CFF")
        icon_border = QColor("#9C8EFF") if self._selected else QColor("#4A5575")
        p.setBrush(icon_bg)
        p.setPen(QPen(icon_border, 1))
        p.drawRoundedRect(ix, iy, iw, ih, 3, 3)
        # Label
        f = QFont()
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#ffffff") if self._selected else QColor("#E8EAF4"))
        p.drawText(QRect(0, iy + ih + 6, W, 18), Qt.AlignmentFlag.AlignCenter, self.label)
        # Desc
        f2 = QFont()
        f2.setPixelSize(9)
        p.setFont(f2)
        p.setPen(QColor("#A7ADC2"))
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
        self.setStyleSheet(studio_chrome_qss("QDialog{background:#0B0D16;color:#E6E8F2;}"))
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
        self._name_edit.setStyleSheet("")
        name_row.addWidget(self._name_edit)
        root.addLayout(name_row)

        # Ratio cards
        ratio_lbl = QLabel("화면 비율")
        ratio_lbl.setStyleSheet("font-weight:bold; font-size:12px; color:#C9CEDC;")
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
        res_grp.setStyleSheet("")
        res_inner = QVBoxLayout(res_grp)
        self._res_combo = QComboBox()
        self._res_combo.setStyleSheet("")
        res_inner.addWidget(self._res_combo)
        settings_row.addWidget(res_grp, 2)

        fps_grp = QGroupBox("프레임 레이트")
        fps_grp.setStyleSheet("")
        fps_inner = QVBoxLayout(fps_grp)
        self._fps_combo = QComboBox()
        self._fps_combo.setStyleSheet("")
        for label, _ in _FPS_OPTIONS:
            self._fps_combo.addItem(f"{label} fps")
        self._fps_combo.setCurrentIndex(3)   # 30fps default
        fps_inner.addWidget(self._fps_combo)
        settings_row.addWidget(fps_grp, 1)

        root.addLayout(settings_row)

        starter_grp = QGroupBox("Starter template")
        starter_grp.setStyleSheet("")
        starter_inner = QVBoxLayout(starter_grp)
        self._starter_combo = QComboBox()
        self._starter_combo.setStyleSheet("")
        for template_id, label, desc in _STARTER_TEMPLATES:
            self._starter_combo.addItem(label, {"id": template_id, "label": label, "description": desc})
        for index, (template_id, _label, _desc) in enumerate(_STARTER_TEMPLATES):
            if template_id == DEFAULT_STARTER_TEMPLATE_ID:
                self._starter_combo.setCurrentIndex(index)
                break
        self._starter_combo.currentIndexChanged.connect(self._on_starter_changed)
        starter_inner.addWidget(self._starter_combo)
        starter_hint = QLabel("기본 추천은 화면녹화용 배경, 커서, 클릭, 자동 줌, 60fps 내보내기를 바로 맞춥니다.")
        starter_hint.setWordWrap(True)
        starter_hint.setStyleSheet("color:#A7ADC2;font-size:10px;")
        starter_inner.addWidget(starter_hint)
        root.addWidget(starter_grp)

        # Buttons
        btns = QDialogButtonBox()
        create_btn = QPushButton("프로젝트 만들기")
        create_btn.setDefault(True)
        create_btn.setProperty("variant", "primary")
        cancel_btn = QPushButton("취소")
        btns.addButton(create_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        btns.accepted.connect(self._on_create)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

        # Init
        self._select_ratio("16:9")
        self._on_starter_changed()

    def _select_ratio(self, label: str):
        self._ratio = label
        for lbl, card in self._cards.items():
            card.set_selected(lbl == label)
        # Refresh resolution combo
        self._res_combo.clear()
        for res_label, w, h in _RESOLUTIONS.get(label, []):
            self._res_combo.addItem(res_label, (w, h))
        default_index = int(_RATIO_DEFAULT_RES_INDEX.get(label, 0))
        if 0 <= default_index < self._res_combo.count():
            self._res_combo.setCurrentIndex(default_index)

    def _set_fps_value(self, fps: float) -> None:
        for idx, (_label, value) in enumerate(_FPS_OPTIONS):
            if abs(float(value) - float(fps)) < 0.001:
                self._fps_combo.setCurrentIndex(idx)
                return

    def _on_starter_changed(self) -> None:
        starter = self._starter_combo.currentData() or {}
        starter_id = str(starter.get("id") or "")
        if starter_id == "vertical-shorts":
            self._select_ratio("9:16")
            self._set_fps_value(60.0)
        elif starter_id in {"screen-recording-demo", "gameplay-highlight"}:
            self._select_ratio("16:9")
            self._set_fps_value(60.0)
        elif starter_id == "product-demo":
            self._select_ratio("16:9")
            self._set_fps_value(30.0)

    def _on_create(self):
        name = self._name_edit.text().strip() or "새 프로젝트"
        res_data = self._res_combo.currentData()
        if res_data:
            w, h = res_data
        else:
            w, h = 1920, 1080
        fps_label = _FPS_OPTIONS[self._fps_combo.currentIndex()][0]
        fps_val = _FPS_OPTIONS[self._fps_combo.currentIndex()][1]
        starter = self._starter_combo.currentData() or {}
        self.result_settings = ProjectSettings(
            name=name,
            width=w,
            height=h,
            fps=fps_val,
            ratio_label=self._ratio,
            starter_template_id=str(starter.get("id") or "blank"),
            starter_template_label=str(starter.get("label") or "Blank"),
        )
        self.accept()
