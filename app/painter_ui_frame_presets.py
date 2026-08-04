"""Tool-context inspector for Figma-style region tools."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


FRAME_PRESET_GROUPS: tuple[
    tuple[str, tuple[tuple[str, int, int], ...]], ...
] = (
    (
        "스마트폰",
        (
            ("iPhone 17", 402, 874),
            ("iPhone 16 및 17 Pro", 402, 874),
            ("iPhone 16", 393, 852),
            ("iPhone 16 및 17 Pro Max", 440, 956),
            ("iPhone 16 플러스", 430, 932),
            ("iPhone Air", 420, 912),
            ("iPhone 14 및 15 Pro Max", 430, 932),
            ("iPhone 14 및 15 Pro", 393, 852),
            ("iPhone 13 및 14", 390, 844),
            ("iPhone 14 플러스", 428, 926),
            ("Android 컴팩트", 412, 917),
            ("Android 미디엄", 700, 840),
        ),
    ),
    (
        "태블릿",
        (
            ("iPad mini 8.3", 744, 1133),
            ("Surface Pro 8", 1440, 960),
            ("iPad Pro 11인치", 834, 1194),
            ("iPad Pro 12.9인치", 1024, 1366),
            ("Android 확장판", 1280, 800),
        ),
    ),
    (
        "데스크톱",
        (
            ("MacBook Air", 1280, 832),
            ("MacBook Pro 14인치", 1512, 982),
            ("MacBook Pro 16인치", 1728, 1117),
            ("데스크톱", 1440, 1024),
            ("와이어프레임", 1440, 1024),
            ("TV", 1280, 720),
        ),
    ),
    (
        "프레젠테이션",
        (
            ("슬라이드 16:9", 1920, 1080),
            ("슬라이드 4:3", 1024, 768),
        ),
    ),
    (
        "스마트워치",
        (
            ("Apple Watch Series 10 42mm", 187, 223),
            ("Apple Watch Series 10 46mm", 208, 248),
            ("Apple Watch 41mm", 176, 215),
            ("Apple Watch 45mm", 198, 242),
            ("Apple Watch 44mm", 184, 224),
            ("Apple Watch 40mm", 162, 197),
        ),
    ),
    (
        "종이",
        (
            ("A4", 595, 842),
            ("A5", 420, 595),
            ("A6", 297, 420),
            ("레터", 612, 792),
            ("타블로이드", 792, 1224),
        ),
    ),
    (
        "소셜 미디어",
        (
            ("Twitter 게시물", 1200, 675),
            ("Twitter 헤더", 1500, 500),
            ("Facebook 게시물", 1200, 630),
            ("페이스북 커버", 820, 312),
            ("Instagram 게시물", 1080, 1350),
            ("Instagram 스토리", 1080, 1920),
            ("Dribbble Shot", 400, 300),
            ("Dribbble Shot HD", 800, 600),
            ("LinkedIn 커버", 1584, 396),
        ),
    ),
    ("Figma 커뮤니티", ()),
    ("아카이브", ()),
)


class PainterUIFramePresetsPanel(QFrame):
    preset_requested = Signal(str, int, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIFramePresetsPanel")
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._mode = "frame"
        self._group_toggles: list[QToolButton] = []
        self._group_rows: list[QWidget] = []
        self.setStyleSheet(
            """
            QFrame#PainterUIFramePresetsPanel { background:#1E2228; border:none; }
            QScrollArea#PainterUIFramePresetScroll,
            QScrollArea#PainterUIFramePresetScroll > QWidget > QWidget {
                background:#1E2228; border:none;
            }
            QLabel#PainterUIRegionToolTitle { color:#F1F4F8; font-size:12px; font-weight:650; }
            QLabel#PainterUIRegionToolHelp { color:#AEB8C5; font-size:10px; }
            QToolButton#PainterUIFramePresetGroup {
                background:transparent; color:#E4E9F0; border:none;
                border-top:1px solid #303741; text-align:left;
                padding:7px 4px; font-size:11px;
                min-height:36px; max-height:36px;
            }
            QToolButton#PainterUIFramePresetGroup:hover { background:#272D35; }
            QWidget#PainterUIFramePresetRows { background:#171B21; }
            QPushButton#PainterUIFramePreset {
                background:transparent; color:#DDE4EC; border:none;
                padding:0 12px; min-height:36px; max-height:36px;
            }
            QPushButton#PainterUIFramePreset:hover { background:#2C3541; }
            QLabel#PainterUIFramePresetName { color:#E5EBF2; font-size:10px; }
            QLabel#PainterUIFramePresetSize { color:#8F9AAA; font-size:10px; }
            """
        )
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(8, 8, 8, 8)
        self._layout.setSpacing(0)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.title = QLabel("프레임")
        self.title.setObjectName("PainterUIRegionToolTitle")
        self._layout.addWidget(self.title)
        self.help = QLabel("")
        self.help.setObjectName("PainterUIRegionToolHelp")
        self.help.setWordWrap(True)
        self.help.hide()
        self._layout.addWidget(self.help)
        self._groups_host = QWidget()
        groups_layout = QVBoxLayout(self._groups_host)
        groups_layout.setContentsMargins(0, 8, 0, 0)
        groups_layout.setSpacing(0)
        for group_index, (group_name, presets) in enumerate(FRAME_PRESET_GROUPS):
            toggle = QToolButton()
            toggle.setObjectName("PainterUIFramePresetGroup")
            toggle.setText(group_name)
            toggle.setCheckable(True)
            toggle.setChecked(False)
            toggle.setArrowType(Qt.ArrowType.RightArrow)
            toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            groups_layout.addWidget(toggle)
            self._group_toggles.append(toggle)
            rows = QWidget()
            rows.setObjectName("PainterUIFramePresetRows")
            rows_layout = QVBoxLayout(rows)
            rows_layout.setContentsMargins(0, 0, 0, 4)
            rows_layout.setSpacing(0)
            for name, width, height in presets:
                button = QPushButton("")
                button.setObjectName("PainterUIFramePreset")
                button.setAccessibleName(name)
                button_layout = QHBoxLayout(button)
                button_layout.setContentsMargins(12, 0, 10, 0)
                button_layout.setSpacing(8)
                name_label = QLabel(name)
                name_label.setObjectName("PainterUIFramePresetName")
                size_label = QLabel(f"{width}×{height}")
                size_label.setObjectName("PainterUIFramePresetSize")
                size_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                for label in (name_label, size_label):
                    label.setAttribute(
                        Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                        True,
                    )
                button_layout.addWidget(name_label, 1)
                button_layout.addWidget(size_label)
                button.clicked.connect(
                    lambda _checked=False, n=name, w=width, h=height:
                    self.preset_requested.emit(n, w, h)
                )
                rows_layout.addWidget(button)
            rows.hide()
            self._group_rows.append(rows)
            toggle.clicked.connect(
                lambda checked, index=group_index:
                self._set_group_open(index, checked)
            )
            groups_layout.addWidget(rows)
        groups_layout.addStretch(1)
        self._groups_scroll = QScrollArea()
        self._groups_scroll.setObjectName("PainterUIFramePresetScroll")
        self._groups_scroll.setWidgetResizable(True)
        self._groups_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._groups_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._groups_scroll.setWidget(self._groups_host)
        self._groups_scroll.viewport().setStyleSheet("background:#1E2228;")
        self._layout.addWidget(self._groups_scroll, 1)
        self._set_group_open(0, True)

    def _set_group_open(self, index: int, opened: bool) -> None:
        for group_index, (toggle, rows) in enumerate(
            zip(self._group_toggles, self._group_rows)
        ):
            active = bool(opened and group_index == int(index))
            toggle.blockSignals(True)
            toggle.setChecked(active)
            toggle.blockSignals(False)
            toggle.setArrowType(
                Qt.ArrowType.DownArrow
                if active else Qt.ArrowType.RightArrow
            )
            rows.setVisible(active)

    def set_mode(self, mode: str) -> None:
        self._mode = str(mode or "frame")
        frame_mode = self._mode == "frame"
        self._groups_host.setVisible(frame_mode)
        self.help.setVisible(not frame_mode)
        if frame_mode:
            self.title.setText("프레임")
            self.help.setText("")
        elif self._mode == "section":
            self.title.setText("섹션")
            self.help.setText(
                "캔버스에서 드래그하여 여러 프레임과 개체를 정리하는 영역을 만듭니다."
            )
        else:
            self.title.setText("슬라이스")
            self.help.setText(
                "캔버스에서 드래그하여 내보낼 영역을 지정합니다."
            )


__all__ = ["FRAME_PRESET_GROUPS", "PainterUIFramePresetsPanel"]
