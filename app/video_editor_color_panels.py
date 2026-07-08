from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.video_editor_popouts import ColorPopoutWindow, SectionPopoutWindow
from app.style import (
    COLOR_BG_L2,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_TERTIARY,
    editor_scrollbar_qss,
)
from app.studio_slider import StudioSlider
from app.video_editor_color_widgets import _HueCurveWidget, _LumaDial, parse_cube_lut
from app.video_editor_layout_specs import (
    VIEWER_TOP_STRETCH,
    WORKBENCH_SLOT_MIN_WIDTH,
    WORKBENCH_TOP_STRETCH,
)

__all__ = [
    "_build_color_inline_panel",
    "_build_color_compact_palette_panel",
    "_build_color_reference_workbench_panel",
    "_build_color_grading_panel",
    "_commit_color_preview_edit",
    "_update_color_dock_visibility",
    "_sync_color_panel",
    "_sync_color_inline_panel",
    "_compact_color_card_style",
    "_pulse_compact_color_card",
    "_pulse_compact_color_cards",
    "_set_color_reference_workspace_ratio",
    "_format_color_slider_label",
    "_refresh_color_target_badge",
    "_sync_color_compare_buttons",
    "parent_widget_for_color",
    "_on_color_page_closed",
    "_disable_color_power_window_overlay",
    "_toggle_color_scopes_popout",
    "_on_color_scopes_popout_closed",
    "_load_lut_file",
    "_on_lut_strength_changed",
    "_on_color_slider_changed",
    "_on_color_wheel_changed",
    "_reset_color_wheel_region",
    "_sync_both_color_panels_except",
    "_on_color_luma_changed",
    "_on_hue_curve_changed",
    "_on_color_reset",
    "_on_color_preset_picked",
    "_on_professional_color_preset_picked",
    "_switch_page",
    "_close_color_page",
]


def _build_color_inline_panel(self) -> QWidget:
    """Compact horizontal color panel that appears above the timeline
    ruler when a Color node is selected.  4 wheels in a row at 120px,
    with R/G/B/L readouts below each.  Mirrors the right-dock panel
    but laid out for the wide timeline area."""
    from app.color_page_window import _Wheel

    _BG = "#17171c"
    _BG_SEC = "#1d1d24"
    _LABEL = "#9090aa"
    _TEXT  = "#d4d4e0"
    _VALBG = "#0d0d14"
    _BORD  = "#2c2c38"
    _TINY  = "font-size: 10px;"
    _SB_QSS = ""
    WHEEL_SIZE = 120

    host = QWidget()
    host.setStyleSheet(f"background:{_BG}; border-bottom:1px solid #2a2a38;")
    host.setFixedHeight(WHEEL_SIZE + 120)  # wheel + label + readouts + sliders

    row = QHBoxLayout(host)
    row.setContentsMargins(12, 8, 12, 8)
    row.setSpacing(0)

    self._inline_wheels: dict[str, object]  = {}
    self._inline_lumas:  dict[str, object]  = {}

    specs = [
        ("shadows",    "Lift"),
        ("midtones",   "Gamma"),
        ("highlights", "Gain"),
        ("offset",     "Offset"),
    ]

    for i, (region, label) in enumerate(specs):
        sec = QWidget()
        sec.setAutoFillBackground(True)
        _pal = sec.palette()
        _pal.setColor(sec.backgroundRole(), QColor(_BG_SEC))
        sec.setPalette(_pal)
        vl = QVBoxLayout(sec)
        vl.setContentsMargins(6, 5, 6, 5)
        vl.setSpacing(3)

        # header: label + ??
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0,0,0,0); hdr.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"background:transparent;border:none;color:{_LABEL};"
            "font-size:10px;font-weight:600;letter-spacing:0.4px;"
        )
        hdr.addWidget(lbl); hdr.addStretch()
        rst = QPushButton("x")
        rst.setFixedSize(16, 16)
        rst.setCursor(Qt.CursorShape.PointingHandCursor)
        rst.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_LABEL};"
            "border:none;font-size:12px;padding:0;}}"
            f"QPushButton:hover{{color:{_TEXT};}}"
        )
        hdr.addWidget(rst)
        vl.addLayout(hdr)

        # wheel
        w = _Wheel()
        w.setFixedSize(WHEEL_SIZE, WHEEL_SIZE)
        w.value_changed.connect(
            lambda x, y, r=region: self._on_color_wheel_changed(r, x, y)
        )
        rst.clicked.connect(
            lambda checked=False, ww=w: ww.set_value(0, 0)
        )
        vl.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        self._inline_wheels[region] = w

        # readouts
        r4 = QHBoxLayout(); r4.setSpacing(2); r4.setContentsMargins(0,0,0,0)
        for hint in ("R","G","B","L"):
            sb = QDoubleSpinBox()
            sb.setRange(-5.0, 5.0); sb.setValue(0.0)
            sb.setDecimals(2); sb.setSingleStep(0.01)
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sb.setStyleSheet(_SB_QSS)
            sb.setToolTip(hint)
            r4.addWidget(sb)
            if hint == "L":
                class _Compat:
                    def __init__(self, s): self._s = s
                    def blockSignals(self, v): self._s.blockSignals(v)
                    def setValue(self, v): self._s.setValue(v / 100.0)
                self._inline_lumas[region] = _Compat(sb)
        vl.addLayout(r4)

        row.addWidget(sec, 1)

        if i < len(specs) - 1:
            div = QFrame()
            div.setFrameShape(QFrame.Shape.VLine)
            div.setFixedWidth(1)
            div.setStyleSheet(f"background:{_BORD};border:none;")
            row.addWidget(div)

    # Close (?? button on the right
    close_btn = QPushButton("x")
    close_btn.setFixedSize(20, 20)
    close_btn.setText("")
    close_btn.setIcon(app_icon("clear", size=14, color="#8F95A8"))
    close_btn.setIconSize(icon_size(14))
    close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    close_btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{_LABEL};"
        "border:none;font-size:16px;padding:0;}}"
        f"QPushButton:hover{{color:{_TEXT};}}"
    )
    close_btn.clicked.connect(
        lambda: self._color_inline_panel.setVisible(False)
    )
    row.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignTop)

    # Bottom bar: Brightness / Contrast / Saturation compact sliders
    bottom = QWidget()
    bottom.setStyleSheet(f"background:{_BG}; border-top:1px solid {_BORD};")
    blay = QHBoxLayout(bottom)
    blay.setContentsMargins(12, 4, 12, 4)
    blay.setSpacing(16)
    self._inline_sliders: dict[str, object] = {}
    for key, label_str in [("brightness","Brightness"),("contrast","Contrast"),("saturation","Saturation")]:
        grp = QHBoxLayout(); grp.setSpacing(4); grp.setContentsMargins(0,0,0,0)
        lbl = QLabel(label_str)
        lbl.setStyleSheet(f"color:{_LABEL};font-size:10px;background:transparent;border:none;")
        lbl.setFixedWidth(26)
        sl = StudioSlider("accent")
        sl.setRange(-100, 100); sl.setValue(0)
        val_lbl = QLabel("0")
        val_lbl.setFixedWidth(22)
        val_lbl.setStyleSheet(f"color:{_TEXT};font-size:10px;background:transparent;border:none;")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sl.valueChanged.connect(
            lambda v, k=key, vl=val_lbl: (
                vl.setText(str(v)),
                self._on_color_slider_changed(k, v),
            )
        )
        grp.addWidget(lbl); grp.addWidget(sl, 1); grp.addWidget(val_lbl)
        blay.addLayout(grp, 1)
        self._inline_sliders[key] = sl
    host_outer = QWidget()
    host_outer.setStyleSheet(f"background:{_BG};")
    outer_lay = QVBoxLayout(host_outer)
    outer_lay.setContentsMargins(0, 0, 0, 0)
    outer_lay.setSpacing(0)
    outer_lay.addWidget(host)
    outer_lay.addWidget(bottom)

    return host_outer

def _build_color_compact_palette_panel(self, parent: QWidget | None = None) -> QWidget:
    """Screen-recorder style compact colour dock for the editor view.

    The full Color Page still owns the deep controls.  This dock is the
    quick, always-visible palette above the timeline, so it intentionally
    avoids large numeric readouts that overlap at normal editor heights.
    """
    from app.color_page_window import _Wheel
    from app.knob_widget import KnobWidget

    if not hasattr(self, "_compact_color_card_style"):
        self._compact_color_card_style = _compact_color_card_style
    if not hasattr(self, "_pulse_compact_color_card"):
        self._pulse_compact_color_card = lambda card: _pulse_compact_color_card(self, card)
    if not hasattr(self, "_pulse_compact_color_cards"):
        self._pulse_compact_color_cards = lambda: _pulse_compact_color_cards(self)

    WHEEL_SIZE = 78
    self._color_wheels: dict[str, object] = {}
    self._color_lumas: dict[str, object] = {}
    self._color_readouts: dict[str, list] = {}
    self._color_luma_dials: dict[str, object] = {}
    self._color_sliders: dict[str, object] = {}
    self._color_palette_cards: list[QWidget] = []

    host = QWidget(parent)
    host.setObjectName("CompactColorDock")
    host.setMinimumHeight(214)
    host.setMaximumHeight(236)
    host.setMinimumWidth(0)
    host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    host.setStyleSheet(
        """
        QWidget#CompactColorDock {
            background:#101112;
            border:1px solid #262B32;
            border-radius:18px;
        }
        QFrame#ColorPaletteCard {
            border:1px solid rgba(255,255,255,26);
            border-radius:18px;
        }
        QFrame#ColorPaletteCard:hover {
            border-color:rgba(185,195,210,92);
        }
        QLabel#ColorPaletteLabel {
            color:#D7DCE4;
            font-size:10px;
            font-weight:700;
            letter-spacing:0px;
            background:transparent;
            border:none;
        }
        QLabel#ColorPaletteHint {
            color:#8C95A3;
            font-size:9px;
            font-weight:700;
            background:transparent;
            border:none;
        }
        QToolButton#ColorPresetDropdown,
        QPushButton#ColorDockButton {
            background:#171A1F;
            color:#D7DCE4;
            border:1px solid #30363D;
            border-radius:13px;
            padding:5px 10px;
            font-size:11px;
            font-weight:700;
        }
        QToolButton#ColorPresetDropdown:hover,
        QPushButton#ColorDockButton:hover {
            background:#20252B;
            border-color:#596474;
        }
        QPushButton#ColorDockIconButton {
            background:#171A1F;
            border:1px solid #30363D;
            border-radius:13px;
            padding:0px;
        }
        QPushButton#ColorDockIconButton:hover {
            background:#20252B;
            border-color:#596474;
        }
        QPushButton#ColorCompareButton {
            color:#B9C1CE;
            background:#15181D;
            border:1px solid #30363D;
            border-radius:13px;
            padding:4px 9px;
            font-size:10px;
            font-weight:700;
        }
        QPushButton#ColorCompareButton:hover {
            background:#20252B;
            border-color:#596474;
        }
        QPushButton#ColorCompareButton:checked {
            color:#F0F3F7;
            background:#242B34;
            border-color:#8E98A8;
        }
        QPushButton#LutPathField {
            color:#B9C1CE;
            background:#15181D;
            border:1px solid #30363D;
            border-radius:13px;
            padding:5px 10px;
            font-size:10px;
            font-weight:700;
            text-align:left;
        }
        QPushButton#LutPathField:hover {
            background:#20252B;
            border-color:#596474;
        }
        QLabel#ColorTargetBadge {
            color:#B9C1CE;
            background:#15181D;
            border:1px solid #30363D;
            border-radius:12px;
            padding:4px 9px;
            font-size:10px;
            font-weight:700;
        }
        """
    )

    root = QVBoxLayout(host)
    root.setContentsMargins(12, 10, 12, 10)
    root.setSpacing(8)

    top = QHBoxLayout()
    top.setContentsMargins(0, 0, 0, 0)
    top.setSpacing(8)

    self._color_preset_btn = QToolButton(host)
    self._color_preset_btn.setObjectName("ColorPresetDropdown")
    self._color_preset_btn.setProperty("compactColorDock", True)
    self._color_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._color_preset_btn.setPopupMode(
        QToolButton.ToolButtonPopupMode.InstantPopup,
    )
    self._color_preset_btn.setIcon(app_icon("grading", size=14, color="#FFFFFF"))
    self._color_preset_btn.setIconSize(icon_size(14))
    self._color_preset_btn.setMinimumWidth(130)
    self._color_preset_btn.setMaximumWidth(210)
    top.addWidget(self._color_preset_btn, 0)

    self._lut_name_label = QPushButton("LUT", host)
    self._lut_name_label.setObjectName("LutPathField")
    self._lut_name_label.setCursor(Qt.CursorShape.PointingHandCursor)
    self._lut_name_label.setToolTip("?대┃?섏뿬 .cube LUT ?뚯씪 ?좏깮")
    self._lut_name_label.clicked.connect(self._load_lut_file)
    self._lut_name_label.setMaximumWidth(170)
    top.addWidget(self._lut_name_label, 0)

    self._lut_strength_slider = StudioSlider("accent", host)
    self._lut_strength_slider.setRange(0, 100)
    self._lut_strength_slider.setValue(100)
    self._lut_strength_slider.setFixedWidth(118)
    self._lut_strength_slider.valueChanged.connect(self._on_lut_strength_changed)
    top.addWidget(self._lut_strength_slider, 0)

    self._lut_pct_label = QLabel("100%", host)
    self._lut_pct_label.setObjectName("ColorPaletteHint")
    self._lut_pct_label.setFixedWidth(38)
    self._lut_pct_label.setAlignment(
        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
    )
    top.addWidget(self._lut_pct_label, 0)

    reset_all = QPushButton(host)
    reset_all.setObjectName("ColorDockIconButton")
    reset_all.setCursor(Qt.CursorShape.PointingHandCursor)
    reset_all.setFixedSize(28, 28)
    reset_all.setToolTip(tr("color.reset"))
    reset_all.setIcon(app_icon("reset", size=14, color="#F8F4EA"))
    reset_all.setIconSize(icon_size(14))
    reset_all.clicked.connect(
        lambda: (self._on_color_reset(), self._pulse_compact_color_cards()),
    )
    top.addWidget(reset_all, 0)

    page_btn = QPushButton("Page", host)
    page_btn.setObjectName("ColorDockButton")
    page_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    page_btn.setToolTip("Open the full Color Page for scopes, qualifiers, windows, and color management.")
    page_btn.setIcon(app_icon("grading", size=13, color="#F8F4EA"))
    page_btn.setIconSize(icon_size(13))
    page_btn.setFixedHeight(28)
    page_btn.clicked.connect(getattr(self, "_open_color_page", lambda: None))
    top.addWidget(page_btn, 0)

    self._color_before_btn = QPushButton("Before", host)
    self._color_before_btn.setObjectName("ColorCompareButton")
    self._color_before_btn.setCheckable(True)
    self._color_before_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._color_before_btn.setToolTip("Preview the active frame before ColorGrade nodes. Export is unaffected.")
    self._color_before_btn.clicked.connect(lambda: self._set_color_preview_compare_mode("before"))
    top.addWidget(self._color_before_btn, 0)

    self._color_split_btn = QPushButton("Split", host)
    self._color_split_btn.setObjectName("ColorCompareButton")
    self._color_split_btn.setCheckable(True)
    self._color_split_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._color_split_btn.setToolTip("Split preview: before color on the left, graded result on the right.")
    self._color_split_btn.clicked.connect(lambda: self._set_color_preview_compare_mode("split"))
    top.addWidget(self._color_split_btn, 0)

    self._color_target_badge = QLabel("Target: --", host)
    self._color_target_badge.setObjectName("ColorTargetBadge")
    self._color_target_badge.setMinimumWidth(150)
    self._color_target_badge.setMaximumWidth(260)
    self._color_target_badge.setToolTip(
        "Shows which color node or track fallback is driving the preview.",
    )
    top.addWidget(self._color_target_badge, 0)
    top.addStretch(1)
    root.addLayout(top)

    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(10)

    wheel_specs = [
        ("shadows", tr("color.wheel.shadows"), "#3553E8", "#B85CF6"),
        ("midtones", tr("color.wheel.midtones"), "#FF8057", "#FFD36B"),
        ("highlights", tr("color.wheel.highlights"), "#21C9D6", "#67E8A5"),
        ("offset", tr("color.wheel.offset"), "#755DF2", "#F653A6"),
    ]

    def _on_luma_from_wheel(region: str, slider: QSlider, value: int) -> None:
        slider.blockSignals(True)
        slider.setValue(int(value))
        slider.blockSignals(False)
        self._on_color_luma_changed(region, value)

    def _on_luma_from_slider(region: str, wheel: _Wheel, value: int) -> None:
        wheel.set_luma(int(value), emit=False)
        self._on_color_luma_changed(region, value)

    for region, label, c0, c1 in wheel_specs:
        card = QFrame(host)
        card.setObjectName("ColorPaletteCard")
        card.setMinimumWidth(162)
        card.setMaximumWidth(210)
        card.setProperty("paletteStart", c0)
        card.setProperty("paletteEnd", c1)
        card.setStyleSheet(self._compact_color_card_style(c0, c1))
        self._color_palette_cards.append(card)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(10, 8, 10, 8)
        vl.setSpacing(4)

        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(4)
        title = QLabel(label, card)
        title.setObjectName("ColorPaletteLabel")
        hdr.addWidget(title)
        hdr.addStretch(1)
        rst = QPushButton(card)
        rst.setObjectName("ColorDockIconButton")
        rst.setCursor(Qt.CursorShape.PointingHandCursor)
        rst.setToolTip(f"{label} reset")
        rst.setFixedSize(22, 22)
        rst.setIcon(app_icon("reset", size=12, color="#F8F4EA"))
        rst.setIconSize(icon_size(12))
        hdr.addWidget(rst)
        vl.addLayout(hdr)

        wheel_row = QHBoxLayout()
        wheel_row.setContentsMargins(0, 0, 0, 0)
        wheel_row.setSpacing(8)
        w = _Wheel(card)
        w.setFixedSize(WHEEL_SIZE, WHEEL_SIZE)
        w.value_changed.connect(
            lambda x, y, r=region: self._on_color_wheel_changed(r, x, y),
        )
        wheel_row.addWidget(w, 0, Qt.AlignmentFlag.AlignLeft)
        self._color_wheels[region] = w

        luma_box = QVBoxLayout()
        luma_box.setContentsMargins(0, 4, 0, 0)
        luma_box.setSpacing(4)
        luma_label = QLabel("LUMA", card)
        luma_label.setObjectName("ColorPaletteHint")
        luma_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        luma_box.addWidget(luma_label)
        luma = StudioSlider("accent", card)
        luma.setRange(-100, 100)
        luma.setValue(0)
        luma_box.addWidget(luma)
        wheel_row.addLayout(luma_box, 1)
        vl.addLayout(wheel_row)
        self._color_lumas[region] = luma

        w.luma_changed.connect(
            lambda v, r=region, s=luma: _on_luma_from_wheel(r, s, v),
        )
        luma.valueChanged.connect(
            lambda v, r=region, ww=w: _on_luma_from_slider(r, ww, v),
        )
        rst.clicked.connect(
            lambda checked=False, ww=w, c=card: (
                ww.set_value(0, 0),
                ww.set_luma(0),
                self._pulse_compact_color_card(c),
            ),
        )
        body.addWidget(card, 1)

    knob_host = QFrame(host)
    knob_host.setObjectName("ColorPaletteCard")
    knob_host.setMinimumWidth(286)
    knob_host.setMaximumWidth(306)
    knob_host.setProperty("paletteStart", "#1A2034")
    knob_host.setProperty("paletteEnd", "#241437")
    knob_host.setStyleSheet(self._compact_color_card_style("#1A2034", "#241437"))
    self._color_palette_cards.append(knob_host)
    kl = QVBoxLayout(knob_host)
    kl.setContentsMargins(10, 8, 10, 7)
    kl.setSpacing(3)
    ktitle = QLabel("PRIMARY", knob_host)
    ktitle.setObjectName("ColorPaletteLabel")
    kl.addWidget(ktitle)
    knobs = QHBoxLayout()
    knobs.setContentsMargins(0, 0, 0, 0)
    knobs.setSpacing(2)

    def _signed_pct(v: float) -> str:
        n = int(round(v))
        return f"{n:+d}" if n != 0 else "0"

    knob_specs = (
        ("brightness", tr("color.slider.brightness"), "#AAB3C0"),
        ("contrast", tr("color.slider.contrast"), "#8E98A8"),
        ("saturation", tr("color.slider.saturation"), "#87A495"),
    )
    for key, label, color in knob_specs:
        knob = KnobWidget(
            label=label,
            value=0.0,
            minimum=-100.0,
            maximum=100.0,
            default=0.0,
            color=color,
            bipolar=True,
            formatter=_signed_pct,
            parent=knob_host,
        )
        knob.valueChanged.connect(
            lambda v, k=key: self._on_color_slider_changed(k, int(round(v))),
        )
        knobs.addWidget(knob, 0)
        self._color_sliders[key] = knob
    kl.addLayout(knobs)
    body.addWidget(knob_host, 0)

    root.addLayout(body, 1)
    install_menu = getattr(self, "_install_lazy_menu_builder", None)
    if callable(install_menu):
        install_menu(self._color_preset_btn, self._build_color_preset_menu)
    else:
        self._build_color_preset_menu()
    self._sync_color_panel()
    refresh_badge = getattr(self, "_refresh_color_target_badge", None)
    if callable(refresh_badge):
        refresh_badge()
    sync_compare = getattr(self, "_sync_color_compare_buttons", None)
    if callable(sync_compare):
        sync_compare()
    return host


def _switch_page(self, page: str) -> None:
    is_color = page == "color"
    self._page_edit_btn.setChecked(not is_color)
    self._page_color_btn.setChecked(is_color)
    if is_color:
        self._show_color_dock_page()
    else:
        self._close_color_page()
        self._update_color_dock_visibility(None)
        self._refresh_preview_after_color_toggle()


def _close_color_page(self) -> None:
    self._disable_color_power_window_overlay()
    if self._color_page_window is not None:
        self._color_page_window.close()

def _build_color_reference_workbench_panel(self) -> QWidget:
    """Reference-style Color Grading workbench for active color nodes."""
    from app.color_page_window import _Wheel
    from app.studio_slider import StudioSlider

    class _CurvePreview(QWidget):
        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self.setMinimumHeight(62)
            self.setMaximumHeight(68)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            r = self.rect().adjusted(10, 10, -10, -12)
            p.fillRect(self.rect(), QColor("#101010"))
            p.setPen(QPen(QColor(255, 255, 255, 14), 1))
            for i in range(1, 5):
                x = r.left() + r.width() * i / 5
                y = r.top() + r.height() * i / 5
                p.drawLine(int(x), r.top(), int(x), r.bottom())
                p.drawLine(r.left(), int(y), r.right(), int(y))
            p.setPen(QPen(QColor(255, 255, 255, 62), 1.0))
            p.drawLine(r.bottomLeft(), r.topRight())

            def _curve(points: tuple[tuple[float, float], ...], color: str, width: float) -> None:
                path = QPainterPath()
                path.moveTo(r.left(), r.bottom())
                for idx, (px, py) in enumerate(points):
                    pt = QPointF(
                        r.left() + r.width() * px,
                        r.bottom() - r.height() * py,
                    )
                    if idx == 0:
                        path.lineTo(pt)
                    else:
                        prev = path.currentPosition()
                        cx = (prev.x() + pt.x()) / 2.0
                        path.cubicTo(QPointF(cx, prev.y()), QPointF(cx, pt.y()), pt)
                line_color = QColor(color)
                line_color.setAlpha(138)
                p.setPen(QPen(line_color, width))
                p.drawPath(path)

            _curve(((.18, .24), (.35, .64), (.52, .45), (.72, .70), (1.0, .96)), "#8FA2C8", 1.2)
            _curve(((.12, .15), (.28, .36), (.50, .48), (.70, .55), (1.0, .93)), "#8EA88E", 1.1)
            _curve(((.10, .10), (.32, .30), (.48, .58), (.65, .50), (1.0, .88)), "#B58A8A", 1.1)
            dot_color = QColor("#DCE2EE")
            dot_color.setAlpha(172)
            p.setBrush(dot_color)
            p.setPen(Qt.PenStyle.NoPen)
            for px, py in ((.18, .24), (.35, .64), (.52, .45), (.72, .70), (1.0, .96)):
                p.drawEllipse(
                    QPointF(r.left() + r.width() * px, r.bottom() - r.height() * py),
                    2.0,
                    2.0,
                )

    class _MiniColorScopes(QWidget):
        """Compact scopes drawn from the current preview pixmap."""

        def __init__(self, editor, parent: QWidget | None = None, *, detached: bool = False) -> None:
            super().__init__(parent)
            self._editor = editor
            self._detached = bool(detached)
            if self._detached:
                self.setMinimumHeight(520)
                self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            else:
                self.setMinimumHeight(354)
                self.setMaximumHeight(396)
                self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        def _sample_image(self):
            pm = getattr(self._editor, "_preview_pixmap", None)
            if pm is None or pm.isNull():
                return None
            try:
                return pm.toImage().convertToFormat(QImage.Format.Format_RGB32).scaled(
                    512 if self._detached else 384,
                    288 if self._detached else 216,
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            except Exception:
                return None

        def _image_to_rgb(self, image: QImage):
            try:
                import numpy as np

                img = image.convertToFormat(QImage.Format.Format_RGB888)
                width = int(img.width())
                height = int(img.height())
                ptr = img.constBits()
                data = np.frombuffer(ptr, dtype=np.uint8, count=height * img.bytesPerLine())
                data = data.reshape((height, img.bytesPerLine()))
                return data[:, : width * 3].reshape((height, width, 3)).copy()
            except Exception:
                return None

        def _scope_image(self, rgb, kind: str, width: int, height: int) -> QImage | None:
            try:
                from app.color_scopes import render_scope

                arr = render_scope(kind, rgb, max(8, int(width)), max(8, int(height)))
                qimg = QImage(
                    arr.data,
                    int(arr.shape[1]),
                    int(arr.shape[0]),
                    int(arr.strides[0]),
                    QImage.Format.Format_RGB888,
                )
                return qimg.copy()
            except Exception:
                return None

        def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.fillRect(self.rect(), QColor("#0D1116"))
            r = self.rect().adjusted(7, 6, -7, -7)
            gap = 6
            col_w = max(18, (r.width() - gap) // 2)
            row_h = max(18, (r.height() - gap) // 2)
            panels = (
                (QRect(r.left(), r.top(), col_w, row_h), "Luma / Levels", "waveform"),
                (QRect(r.left() + col_w + gap, r.top(), r.width() - col_w - gap, row_h), "Histogram", "histogram"),
                (QRect(r.left(), r.top() + row_h + gap, col_w, r.height() - row_h - gap), "RGB Parade", "parade"),
                (
                    QRect(r.left() + col_w + gap, r.top() + row_h + gap, r.width() - col_w - gap, r.height() - row_h - gap),
                    "Vectorscope",
                    "vectorscope",
                ),
            )

            img = self._sample_image()
            rgb = self._image_to_rgb(img) if img is not None else None

            def _frame(rect: QRect, title: str, kind: str) -> None:
                p.setPen(QPen(QColor(160, 176, 195, 34), 1))
                p.setBrush(QColor(8, 10, 12, 150))
                p.drawRoundedRect(rect, 5, 5)
                plot = rect.adjusted(5, 14, -5, -5)
                if rgb is not None and plot.width() > 2 and plot.height() > 2:
                    scope = self._scope_image(rgb, kind, plot.width(), plot.height())
                    if scope is not None:
                        p.drawImage(plot, scope)
                else:
                    p.setPen(QPen(QColor(128, 139, 152, 70), 1))
                    if kind == "vectorscope":
                        radius = max(5, min(plot.width(), plot.height()) // 3)
                        p.drawEllipse(plot.center(), radius, radius)
                        p.drawLine(plot.center().x() - radius, plot.center().y(), plot.center().x() + radius, plot.center().y())
                    elif kind == "histogram":
                        for idx in range(5):
                            x = plot.left() + int(plot.width() * idx / 4)
                            p.drawLine(x, plot.bottom(), x, plot.top() + int(plot.height() * (idx % 3 + 1) / 4))
                    else:
                        p.drawLine(plot.left(), plot.center().y(), plot.right(), plot.center().y())
                p.setPen(QColor(190, 198, 210, 126))
                font = QFont(p.font())
                font.setPixelSize(8)
                font.setBold(False)
                p.setFont(font)
                p.drawText(
                    rect.adjusted(6, 3, -6, -3),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                    title,
                )

            for rect, title, kind in panels:
                _frame(rect, title, kind)

    self._color_scope_widget_cls = _MiniColorScopes
    self._color_wheels = {}
    self._color_lumas = {}
    self._color_readouts = {}
    self._color_luma_dials = {}
    self._color_sliders = {}
    self._color_slider_labels = {}
    self._color_slider_label_formats = {}
    self._color_palette_cards = []

    host = QWidget(self._workbench_section_host if hasattr(self, "_workbench_section_host") else None)
    host.setObjectName("ReferenceColorWorkbench")
    host.setStyleSheet(
        """
        QWidget#ReferenceColorWorkbench {
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #11171C, stop:0.55 #0E1216, stop:1 #0A0C0F);
            border:1px solid #2A333C;
            border-radius:10px;
        }
        QLabel#ColorSideTitle {
            color:#E9EDF4;
            font-size:11px;
            font-weight:560;
            background:transparent;
        }
        QLabel#ColorSideSection {
            color:#D8DEE7;
            font-size:10px;
            font-weight:520;
            background:transparent;
        }
        QLabel#ColorSideValue {
            color:#BBC4D0;
            font-size:9px;
            font-weight:500;
            background:transparent;
            border:none;
            padding:0;
        }
        QLabel#ColorControlLabel {
            color:#C9D0DA;
            font-size:10px;
            font-weight:480;
            background:transparent;
            border:none;
            padding:0;
        }
        QFrame#ColorSideCard {
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 rgba(255,255,255,10), stop:1 rgba(255,255,255,4));
            border:1px solid rgba(152,166,183,38);
            border-radius:9px;
        }
        QFrame#ColorWheelDeck {
            background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #151B21, stop:1 #101419);
            border:1px solid rgba(160,176,195,50);
            border-radius:10px;
        }
        QLabel#ColorWheelValue {
            background:rgba(8,10,13,150);
            color:#CFD5DE;
            border:1px solid rgba(150,162,177,35);
            border-radius:5px;
            padding:1px 5px;
            font-size:8px;
            font-weight:500;
        }
        QLabel#ColorControlValue {
            background:rgba(8,10,13,150);
            color:#D9DEE7;
            border:1px solid rgba(150,162,177,38);
            border-radius:5px;
            padding:1px 5px;
            font-size:9px;
            font-weight:500;
        }
        QPushButton#ColorSideTab {
            background:transparent;
            color:#8F98A6;
            border:none;
            border-bottom:1px solid transparent;
            padding:2px 7px 4px 7px;
            font-size:8px;
            font-weight:620;
        }
        QPushButton#ColorSideTab:checked {
            color:#E9EDF4;
            border-bottom:1px solid #B7BDC5;
        }
        QToolButton#ColorSideDropdown,
        QToolButton#ColorSideButton,
        QPushButton#ColorSideButton {
            background:#171717;
            color:#D9DEE7;
            border:1px solid #303030;
            border-radius:6px;
            padding:4px 8px;
            font-size:8px;
            font-weight:600;
        }
        QToolButton#ColorSideDropdown:hover,
        QToolButton#ColorSideButton:hover,
        QPushButton#ColorSideButton:hover {
            background:#202020;
            border-color:#515151;
        }
        QPushButton#ColorSideButton:checked {
            background:#242424;
            color:#F0F3F7;
            border-color:#8A8F98;
        }
        QPushButton#LutPathField {
            background:#171717;
            color:#B8C0CC;
            border:1px solid #303030;
            border-radius:6px;
            padding:4px 8px;
            text-align:left;
            font-size:8px;
            font-weight:600;
        }
        """
    )
    root = QVBoxLayout(host)
    root.setContentsMargins(7, 6, 7, 7)
    root.setSpacing(5)
    root.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

    title_row = QHBoxLayout()
    title_row.setContentsMargins(0, 0, 0, 0)
    title_row.setSpacing(5)
    title = QLabel("Color Grading", host)
    title.setObjectName("ColorSideTitle")
    title_row.addWidget(title, 1)
    for name in ("Color", "Light", "FX"):
        tab = QPushButton(name, host)
        tab.setObjectName("ColorSideTab")
        tab.setCheckable(True)
        tab.setChecked(name == "Color")
        tab.setFixedHeight(22)
        title_row.addWidget(tab, 0)
    pop = QPushButton("", host)
    pop.setObjectName("ColorSideButton")
    pop.setFixedSize(24, 22)
    pop.setIcon(app_icon("popout", size=12, color="#D7DAE7"))
    pop.setIconSize(icon_size(12))
    pop.setToolTip(tr("veditor.color_popout.tooltip"))
    pop.clicked.connect(self._toggle_color_popout)
    title_row.addWidget(pop, 0)
    root.addLayout(title_row)

    preset_row = QHBoxLayout()
    preset_row.setContentsMargins(0, 0, 0, 0)
    preset_row.setSpacing(5)
    self._color_preset_btn = QToolButton(host)
    self._color_preset_btn.setObjectName("ColorSideDropdown")
    self._color_preset_btn.setProperty("compactColorDock", True)
    self._color_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._color_preset_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    self._color_preset_btn.setIcon(app_icon("grading", size=12, color="#D7DAE7"))
    self._color_preset_btn.setIconSize(icon_size(12))
    self._color_preset_btn.setFixedSize(34, 26)
    preset_row.addWidget(self._color_preset_btn, 0)
    preset_row.addStretch(1)
    self._color_before_btn = QPushButton("Before", host)
    self._color_before_btn.setObjectName("ColorSideButton")
    self._color_before_btn.setCheckable(True)
    self._color_before_btn.setFixedWidth(72)
    self._color_before_btn.clicked.connect(lambda: self._set_color_preview_compare_mode("before"))
    preset_row.addWidget(self._color_before_btn, 0)
    self._color_split_btn = QPushButton("Split", host)
    self._color_split_btn.setObjectName("ColorSideButton")
    self._color_split_btn.setCheckable(True)
    self._color_split_btn.setFixedWidth(72)
    self._color_split_btn.clicked.connect(lambda: self._set_color_preview_compare_mode("split"))
    preset_row.addWidget(self._color_split_btn, 0)
    root.addLayout(preset_row)

    curves_card = QFrame(host)
    curves_card.setObjectName("ColorSideCard")
    curves_card.setMinimumHeight(86)
    curves_layout = QVBoxLayout(curves_card)
    curves_layout.setContentsMargins(8, 6, 8, 7)
    curves_layout.setSpacing(5)
    c_head = QHBoxLayout()
    c_head.setContentsMargins(0, 0, 0, 0)
    c_label = QLabel("Curves", curves_card)
    c_label.setObjectName("ColorSideSection")
    c_head.addWidget(c_label)
    rgb = QLabel("RGB", curves_card)
    rgb.setObjectName("ColorSideValue")
    c_head.addStretch(1)
    c_head.addWidget(rgb)
    curves_layout.addLayout(c_head)
    curves_layout.addWidget(_CurvePreview(curves_card))
    curves_card.hide()

    wheel_card = QFrame(host)
    wheel_card.setObjectName("ColorWheelDeck")
    wheel_card.setMinimumHeight(244)
    wheel_card.setMaximumHeight(270)
    wheel_layout = QVBoxLayout(wheel_card)
    wheel_layout.setContentsMargins(10, 7, 10, 8)
    wheel_layout.setSpacing(6)
    wheel_header = QHBoxLayout()
    wheel_header.setContentsMargins(0, 0, 0, 0)
    wheel_header.setSpacing(7)
    wheel_chev = QToolButton(wheel_card)
    wheel_chev.setObjectName("ColorSideButton")
    wheel_chev.setFixedSize(22, 21)
    wheel_chev.setIcon(app_icon("chevron-down", size=12, color="#AEB7C6"))
    wheel_chev.setIconSize(icon_size(12))
    wheel_chev.setAutoRaise(True)
    wheel_header.addWidget(wheel_chev)
    wheel_title = QLabel("Color Wheels", wheel_card)
    wheel_title.setObjectName("ColorSideSection")
    wheel_header.addWidget(wheel_title, 1)
    wheel_reset = QPushButton("", wheel_card)
    wheel_reset.setObjectName("ColorSideButton")
    wheel_reset.setFixedSize(24, 22)
    wheel_reset.setIcon(app_icon("reset", size=12, color="#AEB7C6"))
    wheel_reset.setIconSize(icon_size(12))
    wheel_reset.setToolTip("Reset color grade")
    wheel_reset.clicked.connect(self._on_color_reset)
    wheel_header.addWidget(wheel_reset)
    wheel_more = QPushButton("", wheel_card)
    wheel_more.setObjectName("ColorSideButton")
    wheel_more.setFixedSize(24, 22)
    wheel_more.setIcon(app_icon("more", size=12, color="#AEB7C6"))
    wheel_more.setIconSize(icon_size(12))
    wheel_more.setToolTip("Color wheel options")
    wheel_header.addWidget(wheel_more)
    wheel_layout.addLayout(wheel_header)
    wheels = QHBoxLayout()
    wheels.setContentsMargins(6, 0, 6, 0)
    wheels.setSpacing(18)
    for region, label in (
        ("shadows", "Lift"),
        ("midtones", "Gamma"),
        ("highlights", "Gain"),
        ("offset", "Offset"),
    ):
        cell_widget = QWidget(wheel_card)
        cell = QVBoxLayout(cell_widget)
        cell.setContentsMargins(0, 0, 0, 0)
        cell.setSpacing(7)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(2)
        top.addStretch(1)
        lbl = QLabel(label, cell_widget)
        lbl.setObjectName("ColorSideValue")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top.addWidget(lbl, 0, Qt.AlignmentFlag.AlignCenter)
        rst = QToolButton(cell_widget)
        rst.setObjectName("ColorSideButton")
        rst.setFixedSize(18, 18)
        rst.setIcon(app_icon("reset", size=10, color="#9DA6B2"))
        rst.setIconSize(icon_size(10))
        rst.setAutoRaise(True)
        rst.setToolTip(f"Reset {label}")
        rst.clicked.connect(
            lambda checked=False, r=region: self._reset_color_wheel_region(r),
        )
        top.addWidget(rst)
        cell.addLayout(top)
        wheel = _Wheel(cell_widget)
        wheel.setFixedSize(110, 110)
        wheel.value_changed.connect(
            lambda x, y, r=region: self._on_color_wheel_changed(r, x, y),
        )
        wheel.luma_changed.connect(
            lambda v, r=region: self._on_color_luma_changed(r, v),
        )
        cell.addWidget(wheel, 0, Qt.AlignmentFlag.AlignCenter)
        self._color_wheels[region] = wheel
        val = QLabel("0.00   |   0.00   |   0.00", cell_widget)
        val.setObjectName("ColorWheelValue")
        val.setFixedHeight(22)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell.addWidget(val)
        self._color_readouts[region] = [val]
        wheels.addWidget(cell_widget)
    wheel_layout.addLayout(wheels)
    root.addWidget(wheel_card)

    def _fmt_control_value(
        value: int,
        scale: float = 1.0,
        signed: bool = False,
        display: str = "plain",
    ) -> str:
        if display == "fraction":
            return f"{float(value) / 100.0:.2f}"
        if display == "ratio":
            return f"{1.0 + float(value) / 100.0:.2f}"
        v = float(value) / scale
        if scale == 1.0:
            iv = int(round(v))
            return f"{iv:+d}" if signed and iv else str(iv)
        return f"{v:+.1f}" if signed and abs(v) > 0.001 else f"{v:.1f}"

    def _make_control_row(
        parent: QWidget,
        label: str,
        value: int,
        *,
        key: str | None = None,
        kind: str = "neutral",
        scale: float = 1.0,
        signed: bool = False,
        display: str = "plain",
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        lab = QLabel(label, parent)
        lab.setObjectName("ColorControlLabel")
        lab.setFixedWidth(72)
        lab.setFixedHeight(18)
        row.addWidget(lab)
        slider = StudioSlider(kind, parent)
        slider.setRange(-100, 100)
        slider.setValue(int(value))
        row.addWidget(slider, 1)
        val = QLabel(_fmt_control_value(value, scale=scale, signed=signed, display=display), parent)
        val.setObjectName("ColorControlValue")
        val.setFixedWidth(42)
        val.setFixedHeight(18)
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(val)
        slider.valueChanged.connect(
            lambda v, target=val, sc=scale, sg=signed, dis=display: target.setText(
                _fmt_control_value(int(v), scale=sc, signed=sg, display=dis),
            ),
        )
        if key:
            slider.valueChanged.connect(
                lambda v, k=key: self._on_color_slider_changed(k, int(v)),
            )
            self._color_sliders[key] = slider
            self._color_slider_labels[key] = val
            self._color_slider_label_formats[key] = (display, float(scale), bool(signed))
        return row

    def _vdivider(parent: QWidget) -> QFrame:
        line = QFrame(parent)
        line.setFixedWidth(1)
        line.setStyleSheet("background:rgba(164,176,190,34);border:none;")
        return line

    light_card = QFrame(host)
    light_card.setObjectName("ColorSideCard")
    light_card.setMinimumHeight(70)
    light_card.setMaximumHeight(78)
    light_layout = QVBoxLayout(light_card)
    light_layout.setContentsMargins(8, 6, 8, 7)
    light_layout.setSpacing(5)
    light_title = QLabel("Light", light_card)
    light_title.setObjectName("ColorSideSection")
    light_layout.addWidget(light_title)
    light_body = QHBoxLayout()
    light_body.setContentsMargins(0, 0, 0, 0)
    light_body.setSpacing(9)
    light_left = QVBoxLayout()
    light_left.setSpacing(4)
    light_left.addLayout(
        _make_control_row(light_card, "Temperature", 21, kind="temperature", scale=10.0, signed=True),
    )
    light_left.addLayout(
        _make_control_row(light_card, "Tint", -32, kind="tint", scale=10.0, signed=True),
    )
    light_body.addLayout(light_left, 1)
    light_body.addWidget(_vdivider(light_card))
    light_right = QVBoxLayout()
    light_right.setSpacing(4)
    light_right.addLayout(
        _make_control_row(light_card, "Exposure", 0, key="brightness", display="fraction"),
    )
    light_right.addLayout(
        _make_control_row(light_card, "Contrast", 0, key="contrast", display="ratio"),
    )
    light_body.addLayout(light_right, 1)
    light_layout.addLayout(light_body)
    root.addWidget(light_card)

    primary_card = QFrame(host)
    primary_card.setObjectName("ColorSideCard")
    primary_card.setMinimumHeight(106)
    primary_card.setMaximumHeight(118)
    primary_layout = QVBoxLayout(primary_card)
    primary_layout.setContentsMargins(8, 6, 8, 7)
    primary_layout.setSpacing(5)
    primary_title = QLabel("Primary", primary_card)
    primary_title.setObjectName("ColorSideSection")
    primary_layout.addWidget(primary_title)
    primary_body = QHBoxLayout()
    primary_body.setContentsMargins(0, 0, 0, 0)
    primary_body.setSpacing(9)
    primary_left = QVBoxLayout()
    primary_left.setSpacing(4)
    for key, label in (
        ("highlights_l", "Highlights"),
        ("midtones_l", "Midtones"),
        ("shadows_l", "Shadows"),
        ("offset_l", "Blacks"),
    ):
        primary_left.addLayout(
            _make_control_row(primary_card, label, 0, key=key, signed=True),
        )
    primary_body.addLayout(primary_left, 1)
    primary_body.addWidget(_vdivider(primary_card))
    primary_right = QVBoxLayout()
    primary_right.setSpacing(4)
    primary_right.addLayout(_make_control_row(primary_card, "Whites", 8, signed=True))
    primary_right.addLayout(_make_control_row(primary_card, "Soft Clip", 10, signed=True))
    primary_right.addLayout(_make_control_row(primary_card, "Pivot", 50, scale=100.0))
    primary_right.addLayout(
        _make_control_row(primary_card, "Saturation", 0, key="saturation", display="ratio"),
    )
    primary_body.addLayout(primary_right, 1)
    primary_layout.addLayout(primary_body)
    root.addWidget(primary_card)

    scopes_card = QFrame(host)
    scopes_card.setObjectName("ColorSideCard")
    scopes_card.setMinimumHeight(456)
    scopes_card.setMaximumHeight(516)
    scopes_layout = QVBoxLayout(scopes_card)
    scopes_layout.setContentsMargins(8, 6, 8, 7)
    scopes_layout.setSpacing(5)
    scopes_head = QHBoxLayout()
    scopes_head.setContentsMargins(0, 0, 0, 0)
    scopes_head.setSpacing(5)
    scopes_title = QLabel("Scopes", scopes_card)
    scopes_title.setObjectName("ColorSideSection")
    scopes_head.addWidget(scopes_title, 1)
    scopes_popout = QPushButton("", scopes_card)
    scopes_popout.setObjectName("ColorSideButton")
    scopes_popout.setFixedSize(24, 22)
    scopes_popout.setIcon(app_icon("popout", size=12, color="#D7DAE7"))
    scopes_popout.setIconSize(icon_size(12))
    scopes_popout.setToolTip("Pop out color scopes")
    scopes_popout.clicked.connect(self._toggle_color_scopes_popout)
    scopes_head.addWidget(scopes_popout, 0)
    self._color_scope_popout_btn = scopes_popout
    scopes_layout.addLayout(scopes_head)
    self._color_scope_preview = _MiniColorScopes(self, scopes_card)
    self._color_scope_preview.setMinimumHeight(354)
    self._color_scope_preview.setMaximumHeight(396)
    scopes_layout.addWidget(self._color_scope_preview)
    root.addWidget(scopes_card)

    # Keep the side panel visibly close to the reference: mask controls are
    # compact inspector actions, not a separate bottom toolbar.
    mask_card = QFrame(host)
    mask_card.setObjectName("ColorSideCard")
    mask_card.setMinimumHeight(42)
    mask_layout = QHBoxLayout(mask_card)
    mask_layout.setContentsMargins(8, 6, 8, 7)
    mask_layout.setSpacing(5)
    mask_title = QLabel("Mask", mask_card)
    mask_title.setObjectName("ColorSideSection")
    mask_layout.addWidget(mask_title)
    mask_layout.addStretch(1)
    for label, icon_name, action in (
        ("Window", "target", "power_window"),
        ("Key", "grading", "hsl"),
        ("Person", "person", "magic:person"),
        ("Roto", "scissors", "track_region"),
    ):
        btn = QPushButton(label, mask_card)
        btn.setObjectName("ColorSideButton")
        btn.setIcon(app_icon(icon_name, size=11, color="#D7DAE7"))
        btn.setIconSize(icon_size(11))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(
            lambda checked=False, kind=action: self._mask_toolbar_action(kind),
        )
        mask_layout.addWidget(btn)
    root.addWidget(mask_card)

    lut_row = QHBoxLayout()
    lut_row.setContentsMargins(0, 0, 0, 0)
    lut_row.setSpacing(5)
    self._lut_name_label = QPushButton("LUT", host)
    self._lut_name_label.setObjectName("LutPathField")
    self._lut_name_label.clicked.connect(self._load_lut_file)
    lut_row.addWidget(self._lut_name_label, 1)
    self._lut_strength_slider = StudioSlider("accent", host)
    self._lut_strength_slider.setRange(0, 100)
    self._lut_strength_slider.setValue(100)
    self._lut_strength_slider.setFixedWidth(74)
    self._lut_strength_slider.valueChanged.connect(self._on_lut_strength_changed)
    lut_row.addWidget(self._lut_strength_slider, 0)
    self._lut_pct_label = QLabel("100%", host)
    self._lut_pct_label.setObjectName("ColorSideValue")
    self._lut_pct_label.setFixedWidth(32)
    lut_row.addWidget(self._lut_pct_label)
    root.addLayout(lut_row)

    self._color_target_badge = QLabel("Target: --", host)
    self._color_target_badge.setObjectName("ColorTargetBadge")
    self._color_target_badge.setStyleSheet(
        "QLabel#ColorTargetBadge{background:#151515;color:#AEB7C5;"
        "border:1px solid rgba(255,255,255,16);border-radius:7px;"
        "padding:5px 8px;font-size:8px;font-weight:600;}"
    )
    root.addWidget(self._color_target_badge)
    root.addStretch(1)

    install_menu = getattr(self, "_install_lazy_menu_builder", None)
    if callable(install_menu):
        install_menu(self._color_preset_btn, self._build_color_preset_menu)
    else:
        self._build_color_preset_menu()
    self._sync_color_panel()
    scroll = QScrollArea(self._workbench_section_host if hasattr(self, "_workbench_section_host") else None)
    scroll.setObjectName("ReferenceColorWorkbenchScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    scroll.setStyleSheet(
        "QScrollArea#ReferenceColorWorkbenchScroll{background:transparent;border:none;}"
        "QScrollArea#ReferenceColorWorkbenchScroll > QWidget > QWidget{background:transparent;}"
        + editor_scrollbar_qss("QScrollArea#ReferenceColorWorkbenchScroll")
    )
    scroll.setWidget(host)
    return scroll

def _build_color_grading_panel(self) -> QWidget:
    """DaVinci Resolve-style colour panel ??2?? wheel grid for the narrow dock."""
    from app.color_page_window import _Wheel

    _BG_SECTION = "#1d1d24"
    _LABEL_CLR  = "#9090aa"
    _TEXT_CLR   = "#d4d4e0"
    _VAL_BG     = "#0d0d14"
    _BORDER_CLR = "#2c2c38"
    _TINY = "font-size: 10px;"
    _SBOX_QSS = (
        "QDoubleSpinBox{background:#15181D;color:#D7DCE4;"
        "border:1px solid #30363D;border-radius:9px;padding:3px 5px;font-size:10px;}"
        "QDoubleSpinBox:hover{background:#20252B;border-color:#596474;}"
        "QDoubleSpinBox:focus{border-color:#8E98A8;}"
        "QDoubleSpinBox::up-button,QDoubleSpinBox::down-button{width:0;}"
    )
    _PANEL_BUTTON_QSS = (
        "QPushButton{background:#1A1D22;color:#D7DCE4;"
        "border:1px solid #30363D;border-radius:8px;"
        "padding:5px 12px;font-size:11px;font-weight:700;}"
        "QPushButton:hover{background:#20252B;border-color:#596474;color:#F0F3F7;}"
        "QPushButton:pressed{background:#242B34;border-color:#8E98A8;}"
    )

    WHEEL_SIZE = 145   # smaller than ColorPage (180) to fit narrow dock

    host = QWidget()
    host.setObjectName("ColorPanel")
    host.setStyleSheet(
        "QWidget#ColorPanel{background:#101112;"
        "border:1px solid #262B32;border-radius:16px;}"
    )
    host.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    outer = QVBoxLayout(host)
    outer.setContentsMargins(8, 8, 8, 8)
    outer.setSpacing(8)
    # Let Qt compute the host's minimumHeight from its children so the
    # scroll area always gets enough space to show the full 2?? wheel grid.
    outer.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

    # ???? Preset row ??????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    preset_row = QHBoxLayout()
    preset_row.setContentsMargins(0, 0, 0, 0)
    preset_row.setSpacing(4)

    self._color_preset_btn = QToolButton()
    self._color_preset_btn.setObjectName("ColorPresetDropdown")
    self._color_preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._color_preset_btn.setPopupMode(
        QToolButton.ToolButtonPopupMode.InstantPopup,
    )
    self._color_preset_btn.setMinimumHeight(28)
    self._color_preset_btn.setStyleSheet(
        "QToolButton#ColorPresetDropdown { "
        "background-color:#171A1F; color:#D7DCE4; "
        "border:1px solid #30363D; border-radius:14px; "
        "padding:5px 28px 5px 12px; font-size:11px; font-weight:700; min-height:26px; }"
        "QToolButton#ColorPresetDropdown:hover { "
        "background-color:#20252B; border-color:#596474; color:#F0F3F7; }"
        "QToolButton#ColorPresetDropdown:pressed { "
        "background-color:#242B34; border-color:#8E98A8; }"
        "QToolButton#ColorPresetDropdown::menu-indicator { "
        "image: none; subcontrol-origin: padding; subcontrol-position: right center; right: 9px; }"
    )
    preset_row.addWidget(self._color_preset_btn)
    preset_row.addStretch(1)

    rst_all = QPushButton(tr("color.reset"))
    rst_all.setObjectName("ToolButton")
    rst_all.setCursor(Qt.CursorShape.PointingHandCursor)
    rst_all.setStyleSheet(_PANEL_BUTTON_QSS)
    rst_all.clicked.connect(self._on_color_reset)
    preset_row.addWidget(rst_all)
    outer.addLayout(preset_row)

    # ???? 4 wheel sections in 2?? grid ??????????????????????????????????????????????????????????????????????????????
    self._color_wheels: dict[str, object] = {}   # region ??_Wheel
    self._color_lumas:  dict[str, object] = {}   # region ??_LumaCompat
    self._color_readouts: dict[str, list] = {}   # region ??[sb_r, sb_g, sb_b]
    self._color_luma_dials: dict[str, _LumaDial] = {}  # region ??_LumaDial

    wheel_specs = [
        ("shadows",    tr("color.wheel.shadows")),
        ("midtones",   tr("color.wheel.midtones")),
        ("highlights", tr("color.wheel.highlights")),
        ("offset",     tr("color.wheel.offset")),
    ]

    def _make_section(region: str, label: str) -> QWidget:
        sec = QWidget()
        sec.setObjectName("InlineColorWheelSection")
        sec.setMinimumWidth(WHEEL_SIZE + 24)
        # Minimum height: label(18) + spacing(4) + wheel + spacing(4) + readouts(22) + margins(12)
        sec.setMinimumHeight(WHEEL_SIZE + 60)
        sec.setStyleSheet(
            "QWidget#InlineColorWheelSection{background:#15181D;"
            "border:1px solid #30363D;border-radius:16px;}"
            "QWidget#InlineColorWheelSection:hover{border-color:#596474;}"
        )
        vl = QVBoxLayout(sec)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(6)

        # header
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"background:transparent; border:none; color:{_LABEL_CLR}; "
            "font-size:10px; font-weight:600; letter-spacing:0.5px;"
        )
        hdr.addWidget(lbl)
        hdr.addStretch()
        rst_btn = QPushButton("x")
        rst_btn.setFixedSize(18, 18)
        rst_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        rst_btn.setStyleSheet(
            "QPushButton { background:#171A1F; color:#A8B0BD; "
            "border:1px solid #30363D; border-radius:9px; font-size:12px; padding:0; }"
            "QPushButton:hover { background:#20252B; color:#F0F3F7; border-color:#596474; }"
        )
        hdr.addWidget(rst_btn)
        vl.addLayout(hdr)

        # wheel
        w = _Wheel()
        w.setFixedSize(WHEEL_SIZE, WHEEL_SIZE)
        w.value_changed.connect(
            lambda x, y, r=region: self._on_color_wheel_changed(r, x, y)
        )
        w.luma_changed.connect(
            lambda v, r=region: self._on_color_luma_changed(r, v)
        )
        rst_btn.clicked.connect(lambda checked=False, ww=w: (ww.set_value(0, 0), ww.set_luma(0)))
        vl.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        self._color_wheels[region] = w

        # readouts R G B L
        row4 = QHBoxLayout()
        row4.setSpacing(3)
        row4.setContentsMargins(0, 0, 0, 0)
        _BAR_COLORS = {"R":"#e84040","G":"#40c040","B":"#4080e8","L":"#b0b0b0"}
        for hint in ("R", "G", "B", "L"):
            # Each readout: spinbox + 2px coloured bottom bar
            cell = QWidget()
            cell.setStyleSheet("background:transparent;")
            cl = QVBoxLayout(cell); cl.setContentsMargins(0,0,0,0); cl.setSpacing(1)
            sb = QDoubleSpinBox()
            sb.setRange(-5.0, 5.0)
            sb.setValue(0.0)
            sb.setDecimals(2)
            sb.setSingleStep(0.01)
            sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sb.setStyleSheet(_SBOX_QSS)
            sb.setToolTip(hint)
            cl.addWidget(sb)
            bar = QFrame(); bar.setFixedHeight(2)
            bar.setStyleSheet(f"background:{_BAR_COLORS[hint]};border:none;")
            cl.addWidget(bar)
            row4.addWidget(cell)
            if hint == "L":
                class _LumaCompat:
                    def __init__(self, spinbox):
                        self._sb = spinbox
                    def blockSignals(self, v): self._sb.blockSignals(v)
                    def setValue(self, v): self._sb.setValue(v / 100.0)
                self._color_lumas[region] = _LumaCompat(sb)
            elif hint == "R":
                self._color_readouts.setdefault(region, [None, None, None])[0] = sb
            elif hint == "G":
                self._color_readouts.setdefault(region, [None, None, None])[1] = sb
            elif hint == "B":
                self._color_readouts.setdefault(region, [None, None, None])[2] = sb
        vl.addLayout(row4)

        # Luma dial
        luma_dial = _LumaDial()
        luma_dial.value_changed.connect(
            lambda v, r=region: self._on_color_luma_changed(r, v)
        )
        self._color_luma_dials[region] = luma_dial
        vl.addWidget(luma_dial)
        return sec

    # 4 wheels in a single horizontal row (1??)
    wheels_row = QHBoxLayout()
    wheels_row.setSpacing(6)
    wheels_row.setContentsMargins(0, 0, 0, 0)
    for region, label in wheel_specs:
        wheels_row.addWidget(_make_section(region, label), 1)
    outer.addLayout(wheels_row)

    # ???? Divider ????????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    div = QFrame()
    div.setFrameShape(QFrame.Shape.HLine)
    div.setStyleSheet(
        f"background-color: {COLOR_BORDER_DEFAULT}; border: none;"
    )
    div.setFixedHeight(1)
    outer.addWidget(div)

    # ???? Master knobs: Brightness / Contrast / Saturation ??????????????????????????????????????
    from app.knob_widget import KnobWidget

    self._color_sliders: dict = {}
    # NOTE: _color_readouts is initialized ABOVE (before _make_section calls)
    # and populated by _make_section. Do NOT reset it here.

    def _signed_pct(v: float) -> str:
        n = int(round(v))
        return f"{n:+d}" if n != 0 else "0"

    knob_specs = (
        ("brightness", "color.slider.brightness", "blue"),
        ("contrast",   "color.slider.contrast",   "blue"),
        ("saturation", "color.slider.saturation", "green"),
    )
    knobs_host = QWidget()
    knobs_row = QHBoxLayout(knobs_host)
    knobs_row.setContentsMargins(0, 4, 0, 4)
    knobs_row.setSpacing(8)
    knobs_row.addStretch(1)
    for key, label_key, color in knob_specs:
        knob = KnobWidget(
            label=tr(label_key),
            value=0.0,
            minimum=-100.0,
            maximum=100.0,
            default=0.0,
            color=color,
            bipolar=True,
            formatter=_signed_pct,
        )
        knob.valueChanged.connect(
            lambda v, k=key: self._on_color_slider_changed(k, int(round(v)))
        )
        knobs_row.addWidget(knob, 0)
        self._color_sliders[key] = knob
    knobs_row.addStretch(1)
    outer.addWidget(knobs_host)

    # ???? Hue curve ??????????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    div2 = QFrame()
    div2.setFrameShape(QFrame.Shape.HLine)
    div2.setStyleSheet(
        f"background-color: {COLOR_BORDER_DEFAULT}; border: none;"
    )
    div2.setFixedHeight(1)
    outer.addWidget(div2)

    hue_lbl = QLabel(tr("color.section.hue_curve"))
    hue_lbl.setStyleSheet(
        f"color:{_LABEL_CLR}; font-size:10px; font-weight:600; "
        "background:transparent; border:none; margin-top:4px;"
    )
    outer.addWidget(hue_lbl)

    self._hue_curve = _HueCurveWidget()
    self._hue_curve.setFixedHeight(108)
    self._hue_curve.points_changed.connect(self._on_hue_curve_changed)
    outer.addWidget(self._hue_curve)

    # ???? LUT section ??????????????????????????????????????????????????????????????????????????????????????????????????????????????????
    div3 = QFrame()
    div3.setFrameShape(QFrame.Shape.HLine)
    div3.setStyleSheet(
        f"background-color: {COLOR_BORDER_DEFAULT}; border: none;"
    )
    div3.setFixedHeight(1)
    outer.addWidget(div3)

    lut_host = QWidget()
    lut_host.setObjectName("ColorLutPanel")
    lut_host.setStyleSheet(
        "QWidget#ColorLutPanel { background:#15181D;"
        "border:1px solid #30363D; border-radius:16px; }"
    )
    lut_vlay = QVBoxLayout(lut_host)
    lut_vlay.setContentsMargins(12, 10, 12, 10)
    lut_vlay.setSpacing(8)

    # Row 1: LUT title + load/clear buttons
    lut_top = QHBoxLayout()
    lut_top.setSpacing(6)
    lut_title = QLabel("3D LUT")
    lut_title.setStyleSheet(
        "color: #F8F4EA; font-size: 11px; font-weight: 900;"
    )
    lut_top.addWidget(lut_title)
    lut_top.addStretch(1)

    load_lut_btn = QPushButton("遺덈윭?ㅺ린")
    load_lut_btn.setObjectName("ToolButton")
    load_lut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    load_lut_btn.setFixedHeight(26)
    load_lut_btn.setFixedWidth(74)
    load_lut_btn.setStyleSheet(_PANEL_BUTTON_QSS)
    load_lut_btn.clicked.connect(self._load_lut_file)
    lut_top.addWidget(load_lut_btn)

    clear_lut_btn = QPushButton("?쒓굅")
    clear_lut_btn.setObjectName("ToolButton")
    clear_lut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    clear_lut_btn.setFixedHeight(26)
    clear_lut_btn.setFixedWidth(48)
    clear_lut_btn.setStyleSheet(_PANEL_BUTTON_QSS)
    clear_lut_btn.clicked.connect(self._clear_lut)
    lut_top.addWidget(clear_lut_btn)
    lut_vlay.addLayout(lut_top)

    # Row 2: Clickable path field
    _default_lut_dir = str(
        (Path(__file__).parent.parent / "resources" / "luts").resolve()
    ).replace("\\", "/")
    self._lut_name_label = QPushButton(_default_lut_dir)
    self._lut_name_label.setObjectName("LutPathField")
    self._lut_name_label.setCursor(Qt.CursorShape.PointingHandCursor)
    self._lut_name_label.setFlat(True)
    self._lut_name_label.setStyleSheet(
        "QPushButton#LutPathField {"
        "  color: #A8B0BD; font-size: 10px; text-align: left; font-weight:700;"
        "  background: #171A1F; border: 1px solid #30363D;"
        "  border-radius: 12px; padding: 6px 9px;"
        "}"
        "QPushButton#LutPathField:hover { border-color: #596474; color: #F0F3F7; background:#20252B; }"
    )
    self._lut_name_label.clicked.connect(self._load_lut_file)
    self._lut_name_label.setToolTip("?대┃?섏뿬 .cube LUT ?뚯씪 ?좏깮")
    lut_vlay.addWidget(self._lut_name_label)

    # Row 3: Strength slider
    lut_str_row = QHBoxLayout()
    lut_str_row.setSpacing(8)
    lut_str_lbl = QLabel("媛뺣룄")
    lut_str_lbl.setStyleSheet("color: #A7ADC2; font-size: 10px; font-weight:800;")
    lut_str_lbl.setFixedWidth(28)
    lut_str_row.addWidget(lut_str_lbl)

    self._lut_strength_slider = StudioSlider("accent")
    self._lut_strength_slider.setRange(0, 100)
    self._lut_strength_slider.setValue(100)
    self._lut_strength_slider.valueChanged.connect(self._on_lut_strength_changed)
    lut_str_row.addWidget(self._lut_strength_slider, 1)

    self._lut_pct_label = QLabel("100%")
    self._lut_pct_label.setStyleSheet(
        "color:#E8EAF4;font-size:10px;font-weight:800;"
        "background:rgba(255,255,255,10);border:1px solid rgba(255,255,255,18);"
        "border-radius:9px;padding:2px 5px;"
    )
    self._lut_pct_label.setFixedWidth(42)
    lut_str_row.addWidget(self._lut_pct_label)
    lut_vlay.addLayout(lut_str_row)

    outer.addWidget(lut_host)

    outer.addStretch(1)

    install_menu = getattr(self, "_install_lazy_menu_builder", None)
    if callable(install_menu):
        install_menu(self._color_preset_btn, self._build_color_preset_menu)
    else:
        self._build_color_preset_menu()
    self._sync_color_panel()
    return host

def _commit_color_preview_edit(self, *, rebuild_chain: bool = False) -> None:
    """Make a color-control edit visible in the viewer immediately."""
    def _refresh_badge() -> None:
        try:
            refresh = getattr(self, "_refresh_color_target_badge", None)
            if callable(refresh):
                refresh()
        except Exception:
            pass

    track = self._active_track() if hasattr(self, "_active_track") else None
    target = getattr(self, "_node_grade_target", None)
    grade = getattr(target, "color_grade", None) if target is not None else None
    if grade is None and track is not None:
        grade = getattr(track, "color_grade", None)

    if track is not None and grade is not None:
        chain = getattr(track, "node_item_chain", None)
        if chain is None:
            try:
                if getattr(track, "color_grade", None) is not grade:
                    track.color_grade = grade
            except Exception:
                pass
        elif target is not None:
            try:
                chain_nodes = [item for item, _masks in list(chain or [])]
                if target not in chain_nodes:
                    rebuild_chain = True
            except Exception:
                rebuild_chain = True

    if rebuild_chain:
        try:
            self._rebuild_active_chain()
        except Exception:
            pass
        if track is not None and target is not None and grade is not None:
            try:
                chain = list(getattr(track, "node_item_chain", None) or [])
                chain_nodes = [item for item, _masks in chain]
                if target not in chain_nodes:
                    masks = list(getattr(target, "masks", None) or [])
                    track.node_item_chain = [(target, masks)]
                    track.color_grade_chain = [grade]
                    track.node_mask_chain = [masks or None]
            except Exception:
                pass

    player = getattr(self, "_player", None)
    if player is None:
        _refresh_badge()
        return
    try:
        if hasattr(player, "clear_preview_prerender_cache"):
            player.clear_preview_prerender_cache()
    except Exception:
        pass
    try:
        player.refresh_current_frame()
        _refresh_badge()
        return
    except Exception:
        pass
    try:
        player.set_position(player.position())
    except Exception:
        pass
    _refresh_badge()

def _update_color_dock_visibility(self, selected_node=None) -> None:
    """Show the bottom color dock only when a colour-grading node
    is the active selection. Other node types (future Blur / LUT /
    etc.) will surface their controls in the right-side workbench
    panel ??keeping the bottom dock dedicated to wide-format
    wheel work where it actually fits."""
    # If a popout is open the header strip is showing a
    # placeholder, not the panel ??leave it alone.
    if getattr(self, "_color_popout", None) is not None:
        return
    if not hasattr(self, "_color_header_widget"):
        return
    # Color-grading nodes expose a non-None ``color_grade`` field.
    # Effect/blur nodes intentionally set it to None, so checking the
    # field directly is more robust than relying on module identity in
    # test harnesses or plugin reloads.
    is_color_node = (
        selected_node is not None
        and getattr(selected_node, "color_grade", None) is not None
    )
    self._set_color_reference_workspace_ratio(is_color_node)
    stack = getattr(self, "_workbench_stack", None)
    color_page = getattr(self, "_color_workbench_panel", None)
    edit_page = getattr(self, "_workbench_panel", None)
    if stack is not None and color_page is not None and edit_page is not None:
        if is_color_node:
            color_page.show()
            stack.setCurrentWidget(color_page)
            try:
                track = self._active_track()
                if track is not None and not getattr(track, "preview_color_compare_mode", ""):
                    setattr(track, "preview_color_compare_mode", "split")
                    self._sync_color_compare_buttons()
                    player = getattr(self, "_player", None)
                    if player is not None:
                        try:
                            player.refresh_current_frame()
                        except Exception:
                            pass
            except Exception:
                pass
        else:
            stack.setCurrentWidget(edit_page)
            color_page.hide()

    # The reference-driven editor default is now a right-side Color
    # Grading workbench. Keep the old wide bottom dock available for
    # explicit popout/full-page paths, but do not let it consume the
    # timeline whenever a color node is selected.
    show_bottom_dock = False
    self._color_header_widget.setVisible(show_bottom_dock)
    self._color_row_host.setVisible(show_bottom_dock)
    main_splitter = getattr(self, "_main_dock_splitter", None)
    if main_splitter is not None:
        main_splitter.setMinimumHeight(410)
        main_splitter.setMaximumHeight(600)
        main_splitter.updateGeometry()
    # Mask toolbar follows the dock ??same activation rule.
    if hasattr(self, "_mask_toolbar_widget"):
        self._mask_toolbar_widget.setVisible(show_bottom_dock)
    # Show/hide the splitter pane that wraps header + toolbar + row.
    # When hidden the splitter collapses that pane to zero so the
    # timeline section gets all the available vertical space.
    if hasattr(self, "_color_container"):
        self._color_container.setVisible(show_bottom_dock)
        if show_bottom_dock:
            self._color_container.setMinimumHeight(318)
            self._color_container.setMaximumHeight(330)
        else:
            self._color_container.setMinimumHeight(0)
    splitter = getattr(self, "_color_timeline_splitter", None)
    color_container = getattr(self, "_color_container", None)
    timeline_host = getattr(self, "_timeline_section_host", None)
    if splitter is not None and color_container is not None and timeline_host is not None:
        color_idx = splitter.indexOf(color_container)
        timeline_idx = splitter.indexOf(timeline_host)
        sizes = list(splitter.sizes())
        if (
            color_idx >= 0
            and timeline_idx >= 0
            and color_idx < len(sizes)
            and timeline_idx < len(sizes)
        ):
            if show_bottom_dock:
                sizes[color_idx] = max(sizes[color_idx], 324)
                sizes[timeline_idx] = max(sizes[timeline_idx], 260)
            else:
                sizes[color_idx] = 0
                sizes[timeline_idx] = max(
                    sizes[timeline_idx],
                    int(getattr(self, "_timeline_compact_min_height", 210)),
                )
            splitter.setSizes(sizes)
            splitter.updateGeometry()

def _sync_color_panel(self) -> None:
    """Pull current track's grade into wheels + knobs + preset
    label. Blocks signals so this isn't recorded as a user-driven
    change. Safe to call before a track exists."""
    grade = self._active_color_grade()
    for key, knob in getattr(self, "_color_sliders", {}).items():
        value = int(getattr(grade, key)) if grade is not None else 0
        knob.blockSignals(True)
        try:
            knob.setValue(float(value), emit=False)
        except TypeError:
            knob.setValue(int(value))
        knob.blockSignals(False)
        label = getattr(self, "_color_slider_labels", {}).get(key)
        if label is not None:
            label.setText(self._format_color_slider_label(key, int(value)))
    for region, wheel in getattr(self, "_color_wheels", {}).items():
        if grade is not None:
            x = int(getattr(grade, f"{region}_x", 0))
            y = int(getattr(grade, f"{region}_y", 0))
            lv = int(getattr(grade, f"{region}_l", 0))
        else:
            x = y = lv = 0
        wheel.set_value(x, y, emit=False)
        # Sync luma arc indicator
        if hasattr(wheel, "set_luma"):
            wheel.set_luma(lv, emit=False)
        # Sync readout spinboxes
        self._update_wheel_readouts(region, x, y)
    for region, luma in getattr(self, "_color_lumas", {}).items():
        value = int(getattr(grade, f"{region}_l", 0)) if grade is not None else 0
        luma.blockSignals(True)
        luma.setValue(value)
        luma.blockSignals(False)
    for region, dial in getattr(self, "_color_luma_dials", {}).items():
        v = int(getattr(grade, f"{region}_l", 0)) if grade is not None else 0
        dial.blockSignals(True)
        dial.set_value(v, emit=False)
        dial.blockSignals(False)
    if hasattr(self, "_hue_curve"):
        pts = list(grade.hue_vs_hue) if grade is not None else []
        # Block signal so set_points doesn't bounce back through
        # _on_hue_curve_changed and dirty the preset id.
        self._hue_curve.blockSignals(True)
        self._hue_curve.set_points(pts)
        self._hue_curve.blockSignals(False)
    self._refresh_color_preset_btn_label()
    if self._color_preset_btn.menu() is not None:
        self._build_color_preset_menu()
    self._sync_color_power_window_overlay()
    refresh_badge = getattr(self, "_refresh_color_target_badge", None)
    if callable(refresh_badge):
        refresh_badge()
    sync_compare = getattr(self, "_sync_color_compare_buttons", None)
    if callable(sync_compare):
        sync_compare()


def _sync_color_inline_panel(self) -> None:
    """Sync the inline panel wheels, readouts, and sliders with the active grade."""
    grade = self._active_color_grade()
    # Sync master sliders
    for key, sl in getattr(self, "_inline_sliders", {}).items():
        v = int(getattr(grade, key, 0)) if grade else 0
        sl.blockSignals(True); sl.setValue(v); sl.blockSignals(False)
    for region, wheel in self._inline_wheels.items():
        x = int(getattr(grade, f"{region}_x", 0)) if grade else 0
        y = int(getattr(grade, f"{region}_y", 0)) if grade else 0
        wheel.set_value(x, y, emit=False)
    for region, compat in self._inline_lumas.items():
        v = int(getattr(grade, f"{region}_l", 0)) if grade else 0
        compat.blockSignals(True)
        compat.setValue(v)
        compat.blockSignals(False)


def _compact_color_card_style(c0: str, c1: str, *, pulse: bool = False) -> str:
    border = "rgba(185,195,210,110)" if pulse else "rgba(185,195,210,34)"
    glow = "rgba(185,195,210,45)" if pulse else "rgba(255,255,255,0)"
    return (
        "QFrame#ColorPaletteCard{"
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #191C21,stop:.62 #15181D,stop:1 #101112);"
        f"border:{2 if pulse else 1}px solid {border};"
        "border-radius:18px;"
        f"selection-background-color:{glow};"
        "}"
        "QFrame#ColorPaletteCard:hover{border-color:rgba(185,195,210,92);}"
    )


def _pulse_compact_color_card(self, card: QWidget | None) -> None:
    if card is None:
        return
    c0 = str(card.property("paletteStart") or "#1A2034")
    c1 = str(card.property("paletteEnd") or "#755DF2")
    try:
        card.setStyleSheet(self._compact_color_card_style(c0, c1, pulse=True))
        QTimer.singleShot(
            180,
            lambda w=card, a=c0, b=c1: w.setStyleSheet(
                self._compact_color_card_style(a, b, pulse=False),
            ),
        )
    except Exception:
        pass


def _pulse_compact_color_cards(self) -> None:
    for card in list(getattr(self, "_color_palette_cards", []) or []):
        self._pulse_compact_color_card(card)


def _set_color_reference_workspace_ratio(self, active: bool) -> None:
    layout = getattr(self, "_top_work_layout", None)
    viewer = getattr(self, "_viewer_column", None)
    workbench = getattr(self, "_top_workbench_slot", None)
    if layout is None or viewer is None or workbench is None:
        return
    viewer_idx = layout.indexOf(viewer)
    workbench_idx = layout.indexOf(workbench)
    if viewer_idx < 0 or workbench_idx < 0:
        return
    if active:
        layout.setStretch(viewer_idx, max(3, VIEWER_TOP_STRETCH - 2))
        layout.setStretch(workbench_idx, max(8, WORKBENCH_TOP_STRETCH + 4))
        workbench.setMinimumWidth(max(620, WORKBENCH_SLOT_MIN_WIDTH))
    else:
        layout.setStretch(viewer_idx, VIEWER_TOP_STRETCH)
        layout.setStretch(workbench_idx, WORKBENCH_TOP_STRETCH)
        workbench.setMinimumWidth(WORKBENCH_SLOT_MIN_WIDTH)
    for widget in (viewer, workbench, getattr(self, "_top_work_area", None)):
        if widget is not None:
            widget.updateGeometry()


def _format_color_slider_label(self, key: str, value: int) -> str:
    display, scale, signed = getattr(
        self,
        "_color_slider_label_formats",
        {},
    ).get(key, ("plain", 1.0, False))
    if display == "fraction":
        return f"{float(value) / 100.0:.2f}"
    if display == "ratio":
        return f"{1.0 + float(value) / 100.0:.2f}"
    if float(scale) != 1.0:
        scaled = float(value) / float(scale)
        if signed and abs(scaled) > 0.001:
            return f"{scaled:+.1f}"
        return f"{scaled:.1f}"
    iv = int(value)
    return f"{iv:+d}" if signed and iv else str(iv)


def _refresh_color_target_badge(self) -> None:
    """Update the compact Color Dock's active grading target label."""
    badge = getattr(self, "_color_target_badge", None)
    if badge is None:
        return
    target = getattr(self, "_node_grade_target", None)
    grade = getattr(target, "color_grade", None) if target is not None else None
    if target is not None and grade is not None:
        label = str(
            getattr(target, "label", "")
            or getattr(target, "node_id", "")
            or "Color Node"
        )
        node_id = str(getattr(target, "node_id", "") or "")
        text = f"Target: {label}"
        if node_id and node_id not in label:
            text = f"Target: {label} ({node_id})"
        tooltip = "Color changes are applied to this node in the active preview chain."
    else:
        track = self._active_track() if hasattr(self, "_active_track") else None
        if track is not None:
            track_id = getattr(track, "id", None)
            track_label = str(
                getattr(track, "display_name", "")
                or getattr(track, "name", "")
                or "Active Track"
            )
            suffix = f" {track_id}" if track_id is not None else ""
            text = f"Target: Track{suffix}"
            tooltip = f"Color changes are applied to the active track fallback grade: {track_label}"
        else:
            text = "Target: --"
            tooltip = "Select a video clip or color node to grade."
    badge.setText(text)
    badge.setToolTip(tooltip)


def _sync_color_compare_buttons(self) -> None:
    track = self._active_track() if hasattr(self, "_active_track") else None
    mode = str(getattr(track, "preview_color_compare_mode", "") or "").casefold()
    before_btn = getattr(self, "_color_before_btn", None)
    split_btn = getattr(self, "_color_split_btn", None)
    for btn, expected in ((before_btn, "before"), (split_btn, "split")):
        if btn is None:
            continue
        try:
            btn.blockSignals(True)
            btn.setChecked(mode == expected)
            btn.blockSignals(False)
        except Exception:
            pass
    sync_viewer = getattr(self, "_sync_viewer_compare_button", None)
    if callable(sync_viewer):
        sync_viewer()


def _load_lut_from_path(self, path: str, *, warn_on_failure: bool = False) -> bool:
        """Parse a .cube LUT, precompute the 256夷 cache, and update
        the editor state + UI badge. Returns True on success.

        Used both by the file-dialog flow (``_load_lut_file``) and by
        project-load (``project_io.load_project``) so a re-opened
        session re-applies the same LUT automatically."""
        lut = parse_cube_lut(path)
        if lut is None:
            if warn_on_failure:
                QMessageBox.warning(
                    self,
                    "LUT Error",
                    "Could not parse the selected .cube file.\n"
                    "Only 3D LUT files (LUT_3D_SIZE) are supported.",
                )
            return False
        import numpy as _np
        try:
            s = lut.shape[0]
            vals = _np.arange(256, dtype=_np.float32) * ((s - 1) / 255.0)
            ri = _np.clip(vals.astype(_np.int32), 0, s - 2)
            rf = vals - ri
            ri1 = ri + 1
            r_, g_, b_ = ri[:, None, None], ri[None, :, None], ri[None, None, :]
            r1_, g1_, b1_ = ri1[:, None, None], ri1[None, :, None], ri1[None, None, :]
            rrf, grf, brf = rf[:, None, None], rf[None, :, None], rf[None, None, :]
            c000 = lut[b_, g_, r_]; c001 = lut[b_, g_, r1_]
            c010 = lut[b_, g1_, r_]; c011 = lut[b_, g1_, r1_]
            c100 = lut[b1_, g_, r_]; c101 = lut[b1_, g_, r1_]
            c110 = lut[b1_, g1_, r_]; c111 = lut[b1_, g1_, r1_]
            cache = (c000*(1-rrf)*(1-grf)*(1-brf) + c001*rrf*(1-grf)*(1-brf) +
                     c010*(1-rrf)*grf*(1-brf)    + c011*rrf*grf*(1-brf)    +
                     c100*(1-rrf)*(1-grf)*brf    + c101*rrf*(1-grf)*brf    +
                     c110*(1-rrf)*grf*brf        + c111*rrf*grf*brf)
            self._lut_cache = _np.clip(cache * 255, 0, 255).astype(_np.uint8)
        except Exception:
            self._lut_cache = None
        self._lut_data = lut
        self._lut_path = path
        name = Path(path).stem
        if hasattr(self, "_player"):
            try:
                self._player.refresh_current_frame()
            except Exception:
                pass
        label = getattr(self, "_lut_name_label", None)
        if label is not None:
            label.setText(f"LUT {name}")
            label.setStyleSheet(
                "QPushButton#LutPathField {"
                "  color: #D8FFE8; font-size: 10px; text-align: left; font-weight:800;"
                "  background: rgba(93,202,165,32); border: 1px solid rgba(93,202,165,150);"
                "  border-radius: 12px; padding: 6px 9px;"
                "}"
                "QPushButton#LutPathField:hover { border-color: #8FF0CD; background: rgba(93,202,165,45); }"
            )
            label.setToolTip(path)
        return True


def parent_widget_for_color(self) -> QWidget:
    """Return the editor widget that owns the docked color row."""
    return self


def _on_color_page_closed(self) -> None:
    self._color_page_window = None
    btn = getattr(self, "_page_color_btn", None)
    if btn is not None:
        btn.setChecked(False)
    btn2 = getattr(self, "_page_edit_btn", None)
    if btn2 is not None:
        btn2.setChecked(True)
    self._disable_color_power_window_overlay()


def _disable_color_power_window_overlay(self) -> None:
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is not None and hasattr(canvas, "set_color_power_window_editor"):
        try:
            canvas.set_color_power_window_editor(None, None, active=False)
        except Exception:
            pass


def _load_lut_file(self) -> None:
    """Open a file dialog to load a .cube LUT file."""
    lut_dir = str((Path(__file__).parent.parent / "resources" / "luts").resolve())
    start_dir = str(Path(self._lut_path).parent) if self._lut_path else lut_dir
    path, _ = QFileDialog.getOpenFileName(
        self,
        "3D LUT ?뚯씪 ?좏깮",
        start_dir,
        "LUT Files (*.cube);;All Files (*)",
    )
    if not path:
        return
    self._load_lut_from_path(path, warn_on_failure=True)


def _on_lut_strength_changed(self, value: int) -> None:
    """Slider moved: update LUT blend strength."""
    self._lut_strength = value / 100.0
    if hasattr(self, "_lut_pct_label"):
        self._lut_pct_label.setText(f"{value}%")
    self._commit_color_preview_edit(rebuild_chain=False)


def _on_color_slider_changed(self, key: str, value: int) -> None:
    grade = self._active_color_grade()
    if grade is None:
        return
    setattr(grade, key, int(value))
    if grade.preset_id != "none":
        grade.preset_id = "custom"
    label = getattr(self, "_color_slider_labels", {}).get(key)
    if label is not None:
        label.setText(self._format_color_slider_label(key, int(value)))
    self._refresh_color_preset_btn_label()
    self._commit_color_preview_edit(rebuild_chain=False)


def _on_color_wheel_changed(self, region: str, x: int, y: int) -> None:
    grade = self._active_color_grade()
    if grade is None:
        return
    setattr(grade, f"{region}_x", int(x))
    setattr(grade, f"{region}_y", int(y))
    if grade.preset_id != "none":
        grade.preset_id = "custom"
    self._refresh_color_preset_btn_label()
    self._update_wheel_readouts(region, x, y)
    self._sync_both_color_panels_except(region)
    self._commit_color_preview_edit(rebuild_chain=False)


def _reset_color_wheel_region(self, region: str) -> None:
    if region not in {"shadows", "midtones", "highlights", "offset"}:
        return
    grade = self._active_color_grade()
    if grade is None:
        return
    setattr(grade, f"{region}_x", 0)
    setattr(grade, f"{region}_y", 0)
    setattr(grade, f"{region}_l", 0)
    if grade.preset_id != "none":
        grade.preset_id = "custom"
    self._sync_color_panel()
    self._commit_color_preview_edit(rebuild_chain=False)


def _sync_both_color_panels_except(self, changed_region: str = "") -> None:
    """Lightweight sync: update dock wheels from grade."""
    grade = self._active_color_grade()
    if grade is None:
        return
    for region, wheel in getattr(self, "_color_wheels", {}).items():
        x = int(getattr(grade, f"{region}_x", 0))
        y = int(getattr(grade, f"{region}_y", 0))
        wheel.set_value(x, y, emit=False)


def _on_color_luma_changed(self, region: str, value: int) -> None:
    grade = self._active_color_grade()
    if grade is None:
        return
    setattr(grade, f"{region}_l", int(value))
    if grade.preset_id != "none":
        grade.preset_id = "custom"
    self._refresh_color_preset_btn_label()
    self._commit_color_preview_edit(rebuild_chain=False)


def _on_hue_curve_changed(self, points) -> None:
    grade = self._active_color_grade()
    if grade is None:
        return
    grade.hue_vs_hue = list(points)
    if grade.preset_id != "none":
        grade.preset_id = "custom"
    self._refresh_color_preset_btn_label()
    self._commit_color_preview_edit(rebuild_chain=True)


def _on_color_reset(self) -> None:
    grade = self._active_color_grade()
    if grade is None:
        return
    grade.reset()
    self._sync_color_panel()
    self._commit_color_preview_edit(rebuild_chain=True)


def _on_color_preset_picked(self, preset_id: str) -> None:
    from app import tier
    from app.color_grading import apply_preset, get_preset

    preset = get_preset(preset_id)
    if tier.is_locked(preset.feature_id):
        self._show_upsell(preset.feature_id, tr(preset.name_key))
        if self._color_preset_btn.menu() is not None:
            self._build_color_preset_menu()
        return
    grade = self._active_color_grade()
    if grade is None:
        return
    apply_preset(grade, preset_id)
    self._sync_color_panel()
    self._commit_color_preview_edit(rebuild_chain=True)


def _on_professional_color_preset_picked(self, preset) -> None:
    from app.preset_library import apply_color_preset_to_grade

    grade = self._active_color_grade()
    if grade is None:
        return
    workflow = apply_color_preset_to_grade(grade, preset)
    grade.preset_id = preset.id
    try:
        setattr(grade, "color_workflow", dict(workflow))
    except Exception:
        pass
    target_node = getattr(self, "_node_grade_target", None)
    if target_node is not None:
        try:
            setattr(target_node, "color_workflow", dict(workflow))
        except Exception:
            pass
    self._sync_color_panel()
    self._commit_color_preview_edit(rebuild_chain=True)

# Color page and power-window helpers moved out of VideoEditorWindow.
def _toggle_color_popout(self) -> None:
    """Detach / re-attach the color section. Same widget tree
    moves between the editor root layout and a floating window
    ??sliders/wheels keep their state across the transition."""
    if self._color_popout is not None and self._color_popout.isVisible():
        self._color_popout.close()
        return
    self._color_popout = ColorPopoutWindow(self)
    self._color_popout.closed.connect(self._on_color_popout_closed)
    # Replace in-editor host with a placeholder so the rest of
    # the editor's layout doesn't collapse upward.
    self._color_root_layout.removeWidget(self._color_row_host)
    self._color_placeholder = QLabel(tr("veditor.color_popout.placeholder"))
    self._color_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._color_placeholder.setMinimumHeight(80)
    self._color_placeholder.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-style: italic; "
        f"background-color: {COLOR_BG_L2}; "
        f"border: 1px dashed {COLOR_BORDER_DEFAULT}; border-radius: 4px;"
    )
    self._color_root_layout.insertWidget(
        self._color_root_index, self._color_placeholder,
    )
    # Move the host into the popout and show it.
    self._color_popout.install(self._color_row_host)
    self._color_popout.show()
    self._color_popout.raise_()
    self._color_popout.activateWindow()


def _on_color_popout_closed(self) -> None:
    """Pop-out window closing ??restore the host into the editor."""
    if self._color_placeholder is not None:
        idx = self._color_root_layout.indexOf(self._color_placeholder)
        self._color_root_layout.removeWidget(self._color_placeholder)
        self._color_placeholder.deleteLater()
        self._color_placeholder = None
    else:
        idx = self._color_root_index
    # Reparent back to the editor.
    self._color_row_host.setParent(self.parent_widget_for_color())
    self._color_root_layout.insertWidget(
        max(0, idx), self._color_row_host,
    )
    self._color_row_host.show()
    if self._color_popout is not None:
        self._color_popout.deleteLater()
        self._color_popout = None


def _toggle_color_scopes_popout(self) -> None:
    """Open a detached live scopes dock without removing the Workbench copy."""
    popout = getattr(self, "_color_scopes_popout", None)
    if popout is not None and popout.isVisible():
        popout.close()
        return

    scope_cls = getattr(self, "_color_scope_widget_cls", None)
    if scope_cls is None:
        return

    popout = SectionPopoutWindow(
        "Color Scopes",
        width=980,
        height=720,
        min_width=560,
        min_height=420,
        parent=self,
    )
    self._color_scopes_popout = popout
    popout.closed.connect(self._on_color_scopes_popout_closed)

    host = QWidget(popout)
    host.setObjectName("DetachedColorScopesDock")
    host.setStyleSheet(
        """
        QWidget#DetachedColorScopesDock {
            background:#0D1116;
            border:1px solid rgba(152,166,183,42);
            border-radius:8px;
        }
        QLabel#DetachedColorScopesTitle {
            color:#E4E9F1;
            font-size:12px;
            font-weight:650;
            background:transparent;
        }
        QPushButton#DetachedColorScopesButton {
            background:#171717;
            color:#D9DEE7;
            border:1px solid #303030;
            border-radius:6px;
            padding:3px 8px;
        }
        QPushButton#DetachedColorScopesButton:hover {
            background:#202020;
            border-color:#515151;
        }
        """
    )
    layout = QVBoxLayout(host)
    layout.setContentsMargins(10, 8, 10, 10)
    layout.setSpacing(8)
    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(6)
    title = QLabel("Color Scopes", host)
    title.setObjectName("DetachedColorScopesTitle")
    header.addWidget(title, 1)
    dock_btn = QPushButton("", host)
    dock_btn.setObjectName("DetachedColorScopesButton")
    dock_btn.setFixedSize(28, 24)
    dock_btn.setIcon(app_icon("popout", size=12, color="#D7DAE7"))
    dock_btn.setIconSize(icon_size(12))
    dock_btn.setToolTip("Dock scopes back into the Workbench")
    dock_btn.clicked.connect(popout.close)
    header.addWidget(dock_btn, 0)
    layout.addLayout(header)

    scope_widget = scope_cls(self, host, detached=True)
    layout.addWidget(scope_widget, 1)
    popout.install(host)

    timer = QTimer(popout)
    timer.setInterval(250)
    timer.timeout.connect(scope_widget.update)
    timer.start()
    popout._scope_widget = scope_widget
    popout._scope_update_timer = timer

    popout.show()
    popout.raise_()
    popout.activateWindow()


def _on_color_scopes_popout_closed(self) -> None:
    popout = getattr(self, "_color_scopes_popout", None)
    if popout is None:
        return
    timer = getattr(popout, "_scope_update_timer", None)
    if timer is not None:
        try:
            timer.stop()
        except Exception:
            pass
    popout.deleteLater()
    self._color_scopes_popout = None


def _show_color_dock_page(self) -> None:
    """Reveal the embedded color dock and bind it to a color node."""
    self._close_color_page()
    target = None
    try:
        wb = getattr(self, "_workbench_panel", None)
        target = wb.primary_node() if wb is not None else None
        if target is not None:
            self._node_grade_target = target
    except Exception:
        target = getattr(self, "_node_grade_target", None)
    if target is None:
        target = getattr(self, "_node_grade_target", None)
    try:
        self._sync_color_panel()
    except Exception:
        pass
    self._update_color_dock_visibility(target)
    try:
        self._rebuild_active_chain()
    except Exception:
        pass
    self._refresh_preview_after_color_toggle()
    self._page_edit_btn.setChecked(False)
    self._page_color_btn.setChecked(True)


def _open_color_page(self) -> None:
    """Open (or raise) the full-screen Color Page window."""
    if self._color_page_window is None:
        from app.color_page_window import ColorPageWindow
        self._color_page_window = ColorPageWindow(self)
        self._color_page_window.grade_changed.connect(
            self._on_color_page_grade_changed
        )
        self._color_page_window.destroyed.connect(
            self._on_color_page_closed
        )
    self._color_page_window.show()
    self._color_page_window.raise_()
    self._color_page_window.activateWindow()
    # Push current grade into the page
    try:
        grade = self._active_color_grade()
        if grade is not None:
            self._color_page_window.update_grade(grade)
            rgb = self._current_preview_rgb()
            if rgb is not None:
                self._color_page_window.update_frame(rgb, grade)
    except Exception:
        pass
    self._sync_color_power_window_overlay()


def _on_color_page_grade_changed(self, grade) -> None:
    """Relay grade changes made in the Color Page back to the editor."""
    try:
        self._on_color_wheel_changed.__func__  # check exists
    except AttributeError:
        pass
    # Sync all editor color-panel widgets without retriggering the page
    try:
        self._sync_color_panel()
    except Exception:
        pass
    # Rebuild the live node chain as workflow/qualifier/window changes can
    # move a grade between shader-safe and CPU-only paths.  This also clears
    # preview caches and redraws once when paused.
    try:
        self._rebuild_active_chain()
    except Exception:
        try:
            self._player.refresh_current_frame()
        except Exception:
            pass
    self._sync_color_power_window_overlay()


def _sync_color_power_window_overlay(self) -> None:
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is None or not hasattr(canvas, "set_color_power_window_editor"):
        return
    cpw = getattr(self, "_color_page_window", None)
    if cpw is None or not cpw.isVisible():
        self._disable_color_power_window_overlay()
        return
    try:
        from app.color_workflow import ColorNodeWorkflow

        grade = self._active_color_grade()
        workflow = ColorNodeWorkflow.from_dict(
            getattr(grade, "color_workflow", None) or {},
        ) if grade is not None else None
        window = workflow.window if workflow is not None else None
        active = bool(window is not None and window.enabled)
        canvas.set_color_power_window_editor(
            window.to_dict() if window is not None else None,
            self._on_color_power_window_dragged,
            active=active,
        )
    except Exception:
        self._disable_color_power_window_overlay()


def _on_color_power_window_dragged(self, payload: dict, commit: bool = False) -> None:
    grade = self._active_color_grade()
    if grade is None:
        return
    try:
        from app.color_workflow import ColorNodeWorkflow, TrackingWindow

        existing = dict(getattr(grade, "color_workflow", None) or {})
        workflow = ColorNodeWorkflow.from_dict(existing)
        window = TrackingWindow.from_dict(payload)
        data = workflow.to_dict()
        data["window"] = window.to_dict()
        data["enabled"] = bool(
            window.enabled
            or workflow.qualifier.enabled
            or not workflow.curves.is_identity()
        )
        grade.color_workflow = data if data["enabled"] else {}
        target_node = getattr(self, "_node_grade_target", None)
        if target_node is not None:
            try:
                setattr(target_node, "color_workflow", dict(grade.color_workflow))
            except Exception:
                pass
    except Exception:
        return

    cpw = getattr(self, "_color_page_window", None)
    if cpw is not None and cpw.isVisible():
        try:
            cpw.update_grade(grade)
        except Exception:
            pass
    try:
        from time import monotonic

        now_ms = monotonic() * 1000.0
        last_ms = float(getattr(self, "_last_color_window_preview_refresh_ms", 0.0))
        if commit or now_ms - last_ms >= 33.0:
            self._last_color_window_preview_refresh_ms = now_ms
            self._player.refresh_current_frame()
    except Exception:
        pass
    if commit:
        try:
            self._register_change("power window")
        except Exception:
            pass


def _active_color_grade(self):
    """DaVinci routing: the Color panel always edits the
    currently-bound NODE's grade. Falls back to the track's
    legacy ``color_grade`` only when no graph node is bound
    (e.g. an audio clip is selected, or the workbench panel
    hasn't materialised yet).

    ``_node_grade_target`` is the NodeItem bound by
    ``_on_node_graph_selection`` / ``_bind_default_node_grade``.
    We dereference its ``color_grade`` lazily so a node deleted
    while the panel is open falls through gracefully.
    """
    target_node = getattr(self, "_node_grade_target", None)
    if target_node is not None:
        grade = getattr(target_node, "color_grade", None)
        if grade is not None:
            return grade
    track = self._active_track()
    if track is None:
        return None
    if getattr(track, "color_grade", None) is None:
        from app.color_grading import ColorGrade
        track.color_grade = ColorGrade()
    return track.color_grade


def _set_color_preview_compare_mode(self, mode: str) -> None:
    """Set preview-only color compare mode for the active track."""
    track = self._active_track() if hasattr(self, "_active_track") else None
    if track is None:
        self._sync_color_compare_buttons()
        return
    wanted = str(mode or "").casefold()
    if wanted not in {"before", "split"}:
        wanted = ""
    current = str(getattr(track, "preview_color_compare_mode", "") or "").casefold()
    next_mode = "" if current == wanted else wanted
    try:
        setattr(track, "preview_color_compare_mode", next_mode)
    except Exception:
        pass
    self._sync_color_compare_buttons()
    player = getattr(self, "_player", None)
    try:
        if hasattr(player, "clear_preview_prerender_cache"):
            player.clear_preview_prerender_cache()
    except Exception:
        pass
    try:
        player.refresh_current_frame()
    except Exception:
        try:
            player.set_position(player.position())
        except Exception:
            pass
    try:
        label = "Color compare off" if not next_mode else f"Color compare: {next_mode}"
        self._flash_status(label)
    except Exception:
        pass


def _clear_lut(self) -> None:
    """Remove the currently loaded LUT."""
    self._lut_data = None
    self._lut_path = ""
    self._lut_strength = 1.0
    label = getattr(self, "_lut_name_label", None)
    if label is not None:
        from pathlib import Path as _P
        _default = str((_P(__file__).parent.parent / "resources" / "luts").resolve()).replace("\\", "/")
        label.setText(_default)
        label.setStyleSheet(
            "QPushButton#LutPathField {"
            "  color: #A7ADC2; font-size: 10px; text-align: left; font-weight:700;"
            "  background: rgba(255,255,255,10); border: 1px solid #30384F;"
            "  border-radius: 12px; padding: 6px 9px;"
            "}"
            "QPushButton#LutPathField:hover { border-color: #7580A5; color: #FFFFFF; background:rgba(255,255,255,18); }"
        )
        label.setToolTip("?대┃?섏뿬 .cube LUT ?뚯씪 ?좏깮")
    slider = getattr(self, "_lut_strength_slider", None)
    if slider is not None:
        slider.blockSignals(True)
        slider.setValue(100)
        slider.blockSignals(False)


def _update_wheel_readouts(self, region: str, x: int, y: int) -> None:
    """Update R/G/B spinbox readouts for the given region's wheel position."""
    sbs = getattr(self, "_color_readouts", {}).get(region)
    if not sbs:
        return
    try:
        from app.color_grading import _wheel_to_rgb_offset
        dR, dG, dB = _wheel_to_rgb_offset(x, y)
        if len(sbs) == 1 and hasattr(sbs[0], "setText"):
            sbs[0].setText(f"{dR:.2f}   |   {dG:.2f}   |   {dB:.2f}")
            return
        if len(sbs) < 3:
            return
        for sb, v in zip(sbs[:3], (dR, dG, dB)):
            if sb is not None:
                sb.blockSignals(True)
                if hasattr(sb, "setValue"):
                    sb.setValue(round(float(v), 2))
                elif hasattr(sb, "setText"):
                    sb.setText(f"{float(v):.2f}")
                sb.blockSignals(False)
    except Exception:
        pass


def _refresh_color_preset_btn_label(self) -> None:
    from app.color_grading import get_preset
    grade = self._active_color_grade()
    if grade is None:
        label = tr("color.preset.none")
    elif grade.preset_id == "custom":
        label = tr("color.preset.custom")
    else:
        try:
            label = tr(get_preset(grade.preset_id).name_key)
        except Exception:
            try:
                from app.preset_library import presets_by_kind
                by_id = {p.id: p.name for p in presets_by_kind("color")}
                label = by_id.get(grade.preset_id, tr("color.preset.custom"))
            except Exception:
                label = tr("color.preset.custom")
    full_text = f"{tr('color.preset.label')}: {label}"
    if bool(self._color_preset_btn.property("compactColorDock")):
        self._color_preset_btn.setText(f"{label}  v")
    else:
        self._color_preset_btn.setText(f"{full_text}  v")
    self._color_preset_btn.setToolTip(full_text)


def _build_color_preset_menu(self) -> None:
    from app.color_grading import COLOR_PRESETS
    from app import tier
    menu = QMenu(self._color_preset_btn)
    menu.setObjectName("ColorPresetMenu")
    menu.setStyleSheet(
        "QMenu#ColorPresetMenu { "
        "background-color:#131724; color:#E8EAF4; border:1px solid #4F5B7C; "
        "border-radius:14px; padding:6px; font-size:12px; }"
        "QMenu#ColorPresetMenu::item { "
        "padding:8px 18px 8px 36px; border-radius:9px; margin:1px 0px; }"
        "QMenu#ColorPresetMenu::item:selected { background-color:#6F5CFF; color:#FFFFFF; }"
        "QMenu#ColorPresetMenu::item:checked { "
        "background-color:rgba(111,92,255,90); color:#FFFFFF; font-weight:800; }"
    )
    grade = self._active_color_grade()
    current_id = grade.preset_id if grade is not None else "none"
    for p in COLOR_PRESETS:
        badge = ""
        if tier.requires_pro(p.feature_id):
            badge = "LOCKED PRO  " if tier.is_locked(p.feature_id) else "PRO  "
        label = f"{p.icon}  {badge}{tr(p.name_key)}  -  {tr(p.desc_key)}"
        act = menu.addAction(label)
        act.setCheckable(True)
        act.setChecked(p.id == current_id)
        act.triggered.connect(
            lambda _checked=False, pid=p.id: self._on_color_preset_picked(pid)
        )
    try:
        from app.preset_library import presets_by_kind
        color_presets = presets_by_kind("color")
    except Exception:
        color_presets = []
    if color_presets:
        menu.addSeparator()
        for preset in color_presets:
            act = menu.addAction(f"* {preset.name}  -  {preset.description}")
            act.setCheckable(True)
            act.setChecked(preset.id == current_id)
            act.triggered.connect(
                lambda _checked=False, p=preset: self._on_professional_color_preset_picked(p)
            )
    self._color_preset_btn.setMenu(menu)
