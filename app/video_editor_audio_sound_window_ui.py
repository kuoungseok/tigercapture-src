from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import (
    COLOR_APP_BG,
    COLOR_BG_L2,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_SUBTLE,
    COLOR_PANEL_BG,
    COLOR_PANEL_BG_ALT,
    COLOR_PANEL_HEADER,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)
from app.video_editor_audio_style import (
    AUDIO_BG,
    AUDIO_BLUE,
    AUDIO_BORDER,
    AUDIO_BORDER_HI,
    AUDIO_PANEL,
    AUDIO_TEXT_DIM,
)
from app.video_editor_audio_waveform_widgets import _EqCurveView

def _qss(self) -> str:
    return f"""
        QWidget {{
            background-color: {COLOR_APP_BG};
            color: {COLOR_TEXT_PRIMARY};
            font-family: "Malgun Gothic", "Noto Sans KR", "Noto Sans CJK KR",
                         "Pretendard", "Segoe UI Variable", "Segoe UI", "Arial", "Tahoma";
            letter-spacing: 0px;
        }}
        QWidget#SETitleBar {{
            background-color: {COLOR_PANEL_HEADER};
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QWidget#SEFileInfo {{
            background-color: {COLOR_PANEL_BG};
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QWidget#SEAnalysisDeck {{
            background-color: {AUDIO_BG};
        }}
        QWidget#SEWaveformSection {{
            background-color: {AUDIO_PANEL};
            border: 1px solid {AUDIO_BORDER};
            border-radius: 7px;
        }}
        QWidget#SEScopePanel {{
            background-color: {AUDIO_PANEL};
            border: 1px solid {AUDIO_BORDER};
            border-radius: 7px;
        }}
        QLabel#SEScopeTitle {{
            color: {AUDIO_TEXT_DIM};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0px;
        }}
        QWidget#SETabBar {{
            background-color: {COLOR_PANEL_BG};
            border-top: 1px solid {COLOR_BORDER_SUBTLE};
            border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QPushButton#SETab {{
            background: transparent;
            color: {COLOR_TEXT_TERTIARY};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 10px 16px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0px;
        }}
        QPushButton#SETab:hover {{ color: {COLOR_TEXT_SECONDARY}; }}
        QPushButton#SETab:checked {{
            color: {COLOR_TEXT_PRIMARY};
            border-bottom: 2px solid {AUDIO_BLUE};
        }}
        QPushButton#SETabAI {{
            background: transparent;
            color: {COLOR_TEXT_TERTIARY};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 10px 16px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0px;
        }}
        QPushButton#SETabAI:hover {{ color: {COLOR_TEXT_SECONDARY}; }}
        QPushButton#SETabAI:checked {{
            color: {COLOR_TEXT_PRIMARY};
            border-bottom: 2px solid {AUDIO_BLUE};
        }}
        QWidget#SEContent {{ background-color: {COLOR_APP_BG}; }}
        QWidget#SETransport {{
            background-color: {COLOR_PANEL_BG};
            border-top: 1px solid {COLOR_BORDER_SUBTLE};
        }}
        QPushButton#SEActionBtn {{
            background-color: {COLOR_BG_L5};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_DEFAULT};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: 600;
        }}
        QPushButton#SEActionBtn:hover {{
            background-color: #282828;
            border-color: {AUDIO_BORDER_HI};
        }}
        QPushButton#SEActionBtn:checked {{
            background-color: #202020;
            border-color: {AUDIO_BLUE};
            color: {COLOR_TEXT_PRIMARY};
        }}
        QPushButton#SEPresetBtn {{
            background-color: {COLOR_PANEL_BG_ALT};
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid {COLOR_BORDER_DEFAULT};
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 11px;
        }}
        QPushButton#SEPresetBtn:hover {{
            background-color: {COLOR_BG_L5};
            color: {COLOR_TEXT_PRIMARY};
            border-color: #66717F;
        }}
        QPushButton#SEAIPresetBtn {{
            background-color: #15181D;
            color: {COLOR_TEXT_SECONDARY};
            border: 1px solid #30363D;
            border-radius: 6px;
            padding: 10px 12px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        QPushButton#SEAIPresetBtn:hover {{
            background-color: #202020;
            color: {COLOR_TEXT_PRIMARY};
            border-color: {AUDIO_BORDER_HI};
        }}
        QPushButton#SEAIPresetBtn[selected="true"] {{
            background-color: #202020;
            color: {COLOR_TEXT_PRIMARY};
            border-color: {AUDIO_BLUE};
        }}
        QPushButton#SEPlayBtn {{
            background-color: #202020;
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {AUDIO_BORDER_HI};
            border-radius: 18px;
            font-size: 14px;
            font-weight: 700;
        }}
        QPushButton#SEPlayBtn:hover {{
            background-color: #282828;
            border-color: {AUDIO_BLUE};
        }}
        QPushButton#SEClose {{
            background-color: {COLOR_BG_L5};
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {COLOR_BORDER_DEFAULT};
            border-radius: 6px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: 600;
        }}
        QPushButton#SEApply {{
            background-color: #202020;
            color: {COLOR_TEXT_PRIMARY};
            border: 1px solid {AUDIO_BORDER_HI};
            border-radius: 6px;
            padding: 6px 16px;
            font-size: 12px;
            font-weight: 700;
        }}
    """

def _build_tab_bar(self) -> QWidget:
    bar = QWidget()
    bar.setObjectName("SETabBar")
    bar.setFixedHeight(42)
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(16, 0, 16, 0)
    lay.setSpacing(0)

    from PySide6.QtWidgets import QButtonGroup

    self._tab_group = QButtonGroup(self)
    self._tab_group.setExclusive(True)
    tabs = [
        ("basic", tr("veditor.sound_editor.tab.basic")),
        ("eq", tr("veditor.sound_editor.tab.eq")),
        ("dynamics", tr("veditor.sound_editor.tab.dynamics")),
        ("effects", tr("veditor.sound_editor.tab.effects")),
        ("advanced", tr("veditor.sound_editor.tab.advanced")),
        ("ai_master", tr("veditor.sound_editor.tab.ai_master")),
    ]
    self._tab_buttons: dict[str, QPushButton] = {}
    for tab_id, tab_label in tabs:
        # "AI Master" gets an orange accent + "NEW" badge appended
        # via HTML ??QPushButton supports rich text through a
        # QTextDocument paint path. Simplest trick: append NEW as
        # a unicode suffix styled via QSS descendant selectors.
        if tab_id == "ai_master":
            btn = QPushButton(f"{tab_label}  NEW")
            btn.setObjectName("SETabAI")
        else:
            btn = QPushButton(tab_label)
            btn.setObjectName("SETab")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if tab_id == "basic":
            btn.setChecked(True)
        btn.clicked.connect(lambda _c, t=tab_id: self._switch_tab(t))
        self._tab_group.addButton(btn)
        self._tab_buttons[tab_id] = btn
        lay.addWidget(btn)
    lay.addStretch(1)
    return bar

def _build_basic_tab(self) -> QWidget:
    from app.knob_widget import (
        FlowLayout,
        KnobWidget,
        fmt_db, fmt_pan, fmt_seconds, fmt_semitones, fmt_speed,
    )

    c = self.clip
    # Map current clip state into knob starting values.
    init_vol_db = self._track_volume_to_db(self._get_track_volume())
    # Pan reads from the owning track (same source the export
    # apan filter uses). Knob domain is -100..+100, track.pan is
    # -1.0..+1.0.
    init_pan = self._get_track_pan() * 100.0
    init_fade_in = c.fade_in_ms / 1000.0
    init_fade_out = c.fade_out_ms / 1000.0
    init_speed = getattr(c, "_se_speed", 1.0)
    init_pitch = getattr(c, "_se_pitch", 0.0)

    panel = QWidget()
    panel.setObjectName("SEBasicTab")
    root = QVBoxLayout(panel)
    root.setContentsMargins(20, 18, 20, 18)
    root.setSpacing(14)

    # --- knob grid (wraps to a 2nd row when the editor is narrow) ---
    knob_row = FlowLayout(h_spacing=12, v_spacing=8)

    self._knob_volume = KnobWidget(
        label="Volume", value=init_vol_db, minimum=-60, maximum=12,
        default=0, unit="dB", color="blue", formatter=fmt_db,
    )
    self._knob_pan = KnobWidget(
        label="Pan", value=init_pan, minimum=-100, maximum=100,
        default=0, color="green", bipolar=True, formatter=fmt_pan,
    )
    self._knob_fade_in = KnobWidget(
        label="Fade In", value=init_fade_in, minimum=0, maximum=10,
        default=0, unit=" s", color="blue", formatter=fmt_seconds,
    )
    self._knob_fade_out = KnobWidget(
        label="Fade Out", value=init_fade_out, minimum=0, maximum=10,
        default=0, unit=" s", color="blue", formatter=fmt_seconds,
    )
    self._knob_speed = KnobWidget(
        label="Speed", value=init_speed, minimum=0.5, maximum=2.0,
        default=1.0, color="orange", formatter=fmt_speed,
    )
    self._knob_pitch = KnobWidget(
        label="Pitch", value=init_pitch, minimum=-12, maximum=12,
        default=0, unit=" st", color="orange", formatter=fmt_semitones,
    )

    # Wire knobs to live state
    self._knob_volume.valueChanged.connect(self._on_volume_knob)
    self._knob_pan.valueChanged.connect(self._on_pan_knob)
    self._knob_fade_in.valueChanged.connect(self._on_fade_in_knob)
    self._knob_fade_out.valueChanged.connect(self._on_fade_out_knob)
    self._knob_speed.valueChanged.connect(self._on_speed_knob)
    self._knob_pitch.valueChanged.connect(self._on_pitch_knob)

    for k in (
        self._knob_volume, self._knob_pan,
        self._knob_fade_in, self._knob_fade_out,
        self._knob_speed, self._knob_pitch,
    ):
        knob_row.addWidget(k)
    root.addLayout(knob_row)

    # --- action buttons ---
    actions = QHBoxLayout()
    actions.setSpacing(8)
    self._btn_mute = QPushButton(tr("veditor.sound_editor.basic.mute"))
    self._btn_mute.setObjectName("SEActionBtn")
    self._btn_mute.setCheckable(True)
    self._btn_mute.toggled.connect(self._on_mute_toggled)
    self._btn_reverse = QPushButton(tr("veditor.sound_editor.basic.reverse"))
    self._btn_reverse.setObjectName("SEActionBtn")
    self._btn_reverse.setCheckable(True)
    self._btn_reverse.toggled.connect(
        lambda on: setattr(self.clip, "_se_reverse", on)
    )
    self._btn_reset = QPushButton(tr("veditor.sound_editor.basic.reset_all"))
    self._btn_reset.setObjectName("SEActionBtn")
    self._btn_reset.clicked.connect(self._reset_basic_to_defaults)

    actions.addWidget(self._btn_mute)
    actions.addWidget(self._btn_reverse)
    actions.addSpacing(20)
    actions.addWidget(self._btn_reset)
    actions.addStretch(1)
    root.addLayout(actions)

    # --- presets ---
    presets_row = QHBoxLayout()
    presets_row.setSpacing(6)
    presets_label = QLabel(tr("veditor.sound_editor.basic.presets"))
    presets_label.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
        f"font-weight: 700; letter-spacing: 1px;"
    )
    presets_row.addWidget(presets_label)
    for preset_name in self.BASIC_PRESETS.keys():
        b = QPushButton(preset_name)
        b.setObjectName("SEPresetBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _c, n=preset_name: self._apply_preset(n))
        presets_row.addWidget(b)
    presets_row.addStretch(1)
    root.addLayout(presets_row)

    root.addStretch(1)
    return panel

def _build_eq_tab(self) -> QWidget:
    from app.knob_widget import KnobWidget, fmt_db, fmt_hz
    eq = self.clip.effects["eq"]

    panel = QWidget()
    panel.setObjectName("SEContent")
    root = QVBoxLayout(panel)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(10)

    # Enable toggle at top
    self._eq_enabled_btn = QPushButton(tr("veditor.sound_editor.fx.enabled"))
    self._eq_enabled_btn.setObjectName("SEActionBtn")
    self._eq_enabled_btn.setCheckable(True)
    self._eq_enabled_btn.setChecked(bool(eq.get("enabled")))
    self._eq_enabled_btn.toggled.connect(lambda on: self._set_fx("eq", "enabled", on))
    self._fx_enable_buttons["eq"] = self._eq_enabled_btn
    row_top = QHBoxLayout()
    row_top.addWidget(self._eq_enabled_btn)
    row_top.addStretch(1)
    root.addLayout(row_top)

    # Curve visualization
    self._eq_curve = _EqCurveView(self.clip)
    self._eq_curve.setFixedHeight(88)
    root.addWidget(self._eq_curve)

    # 3 band rows (each with Freq / Gain / Q)
    def _band_ui(band: str, freq_range: tuple[float, float]) -> QHBoxLayout:
        band_state = eq[band]
        row = QHBoxLayout()
        row.setSpacing(10)
        lbl = QLabel(band.upper())
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; "
            f"font-weight: 700; letter-spacing: 2px; min-width: 50px;"
        )
        row.addWidget(lbl)

        k_freq = KnobWidget(
            label="Freq", value=band_state["freq"],
            minimum=freq_range[0], maximum=freq_range[1],
            default=band_state["freq"],
            color="blue", logarithmic=True, formatter=fmt_hz,
        )
        k_gain = KnobWidget(
            label="Gain", value=band_state["gain"],
            minimum=-12, maximum=12, default=0,
            color="green", bipolar=True, formatter=fmt_db,
        )
        k_q = KnobWidget(
            label="Q", value=band_state["q"],
            minimum=0.1, maximum=10, default=band_state["q"],
            color="orange",
            formatter=lambda v: f"{v:.2f}",
        )
        k_freq.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "freq"), v))
        k_gain.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "gain"), v))
        k_q.valueChanged.connect(lambda v, b=band: self._set_fx("eq", (b, "q"), v))
        row.addWidget(k_freq)
        row.addWidget(k_gain)
        row.addWidget(k_q)
        row.addStretch(1)
        return row

    root.addLayout(_band_ui("low", (20, 250)))
    root.addLayout(_band_ui("mid", (200, 5000)))
    root.addLayout(_band_ui("high", (2000, 20000)))

    # Presets
    root.addLayout(self._preset_row(
        self.EQ_PRESETS.keys(),
        lambda name: self._apply_eq_preset(name),
    ))
    root.addStretch(1)
    return panel

def _build_dynamics_tab(self) -> QWidget:
    from app.knob_widget import FlowLayout, KnobWidget, fmt_db
    comp = self.clip.effects["comp"]
    gate = self.clip.effects["gate"]

    panel = QWidget()
    panel.setObjectName("SEContent")
    root = QVBoxLayout(panel)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(14)

    # --- Compressor ---
    comp_header = self._fx_header(
        tr("veditor.sound_editor.dyn.compressor"),
        "comp",
    )
    self._comp_enabled_btn = comp_header[1]
    root.addWidget(comp_header[0])

    comp_row = FlowLayout(h_spacing=10, v_spacing=6)

    k_thr = KnobWidget(
        label="Threshold", value=comp["threshold"], minimum=-60, maximum=0,
        default=-20, unit=" dB", color="blue", formatter=fmt_db,
    )
    k_ratio = KnobWidget(
        label="Ratio", value=comp["ratio"], minimum=1, maximum=20,
        default=4, color="orange", formatter=lambda v: f"{v:.1f}:1",
    )
    k_atk = KnobWidget(
        label="Attack", value=comp["attack_ms"], minimum=0.1, maximum=100,
        default=5, color="green", logarithmic=True, formatter=lambda v: f"{v:.1f} ms",
    )
    k_rel = KnobWidget(
        label="Release", value=comp["release_ms"], minimum=10, maximum=1000,
        default=150, color="green", logarithmic=True, formatter=lambda v: f"{v:.0f} ms",
    )
    k_makeup = KnobWidget(
        label="Makeup", value=comp["makeup_db"], minimum=0, maximum=24,
        default=0, unit=" dB", color="blue", formatter=fmt_db,
    )
    k_knee = KnobWidget(
        label="Knee", value=comp["knee_db"], minimum=0, maximum=10,
        default=2, color="orange", formatter=lambda v: f"{v:.1f} dB",
    )
    k_thr.valueChanged.connect(lambda v: self._set_fx("comp", "threshold", v))
    k_ratio.valueChanged.connect(lambda v: self._set_fx("comp", "ratio", v))
    k_atk.valueChanged.connect(lambda v: self._set_fx("comp", "attack_ms", v))
    k_rel.valueChanged.connect(lambda v: self._set_fx("comp", "release_ms", v))
    k_makeup.valueChanged.connect(lambda v: self._set_fx("comp", "makeup_db", v))
    k_knee.valueChanged.connect(lambda v: self._set_fx("comp", "knee_db", v))
    for k in (k_thr, k_ratio, k_atk, k_rel, k_makeup, k_knee):
        comp_row.addWidget(k)
    root.addLayout(comp_row)

    # Presets
    root.addLayout(self._preset_row(
        self.DYN_PRESETS.keys(),
        lambda name: self._apply_dyn_preset(name),
    ))

    # --- Gate ---
    gate_header = self._fx_header(
        tr("veditor.sound_editor.dyn.gate"),
        "gate",
    )
    self._gate_enabled_btn = gate_header[1]
    root.addWidget(gate_header[0])

    gate_row = FlowLayout(h_spacing=10, v_spacing=6)
    k_gthr = KnobWidget(
        label="Threshold", value=gate["threshold"], minimum=-80, maximum=0,
        default=-50, unit=" dB", color="blue", formatter=fmt_db,
    )
    k_gred = KnobWidget(
        label="Reduction", value=gate["reduction"], minimum=0, maximum=100,
        default=50, color="orange", formatter=lambda v: f"{v:.0f} %",
    )
    k_gthr.valueChanged.connect(lambda v: self._set_fx("gate", "threshold", v))
    k_gred.valueChanged.connect(lambda v: self._set_fx("gate", "reduction", v))
    gate_row.addWidget(k_gthr)
    gate_row.addWidget(k_gred)
    root.addLayout(gate_row)

    root.addStretch(1)
    return panel

def _build_effects_tab(self) -> QWidget:
    from app.knob_widget import FlowLayout, KnobWidget

    rev = self.clip.effects["reverb"]
    delay = self.clip.effects["delay"]

    panel = QWidget()
    panel.setObjectName("SEContent")
    root = QVBoxLayout(panel)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(14)

    # --- Reverb ---
    rev_header_row = QHBoxLayout()
    rev_header = self._fx_header(
        tr("veditor.sound_editor.fx.reverb"), "reverb"
    )
    self._rev_enabled_btn = rev_header[1]
    rev_header_row.addWidget(rev_header[0])

    # Type dropdown
    from PySide6.QtWidgets import QComboBox
    self._rev_type = QComboBox()
    self._rev_type.addItems(["Room", "Hall", "Plate", "Spring"])
    self._rev_type.setCurrentText(rev["type"])
    self._rev_type.currentTextChanged.connect(
        lambda t: self._set_fx("reverb", "type", t)
    )
    rev_header_row.addWidget(self._rev_type)
    rev_header_row.addStretch(1)
    root.addLayout(rev_header_row)

    rev_row = FlowLayout(h_spacing=10, v_spacing=6)
    k_size = KnobWidget(
        label="Size", value=rev["size"], minimum=0, maximum=100,
        default=30, color="blue", formatter=lambda v: f"{v:.0f} %",
    )
    k_decay = KnobWidget(
        label="Decay", value=rev["decay_s"], minimum=0.1, maximum=10,
        default=1.5, color="blue", formatter=lambda v: f"{v:.1f} s",
    )
    k_damp = KnobWidget(
        label="Damping", value=rev["damping"], minimum=0, maximum=100,
        default=50, color="orange", formatter=lambda v: f"{v:.0f} %",
    )
    k_mix = KnobWidget(
        label="Mix", value=rev["mix"], minimum=0, maximum=100,
        default=20, color="green", formatter=lambda v: f"{v:.0f} %",
    )
    k_size.valueChanged.connect(lambda v: self._set_fx("reverb", "size", v))
    k_decay.valueChanged.connect(lambda v: self._set_fx("reverb", "decay_s", v))
    k_damp.valueChanged.connect(lambda v: self._set_fx("reverb", "damping", v))
    k_mix.valueChanged.connect(lambda v: self._set_fx("reverb", "mix", v))
    for k in (k_size, k_decay, k_damp, k_mix):
        rev_row.addWidget(k)
    root.addLayout(rev_row)

    root.addLayout(self._preset_row(
        self.FX_PRESETS.keys(),
        lambda name: self._apply_fx_preset(name),
    ))

    # --- Delay ---
    delay_header = self._fx_header(
        tr("veditor.sound_editor.fx.delay"), "delay"
    )
    self._delay_enabled_btn = delay_header[1]
    root.addWidget(delay_header[0])

    delay_row = FlowLayout(h_spacing=10, v_spacing=6)
    k_time = KnobWidget(
        label="Time", value=delay["time_ms"], minimum=0, maximum=2000,
        default=250, color="blue", formatter=lambda v: f"{v:.0f} ms",
    )
    k_fb = KnobWidget(
        label="Feedback", value=delay["feedback"], minimum=0, maximum=95,
        default=30, color="orange", formatter=lambda v: f"{v:.0f} %",
    )
    k_dmix = KnobWidget(
        label="Mix", value=delay["mix"], minimum=0, maximum=100,
        default=20, color="green", formatter=lambda v: f"{v:.0f} %",
    )
    k_time.valueChanged.connect(lambda v: self._set_fx("delay", "time_ms", v))
    k_fb.valueChanged.connect(lambda v: self._set_fx("delay", "feedback", v))
    k_dmix.valueChanged.connect(lambda v: self._set_fx("delay", "mix", v))
    for k in (k_time, k_fb, k_dmix):
        delay_row.addWidget(k)
    root.addLayout(delay_row)

    root.addStretch(1)
    return panel

def _build_advanced_tab(self) -> QWidget:
    from app.knob_widget import FlowLayout, KnobWidget, fmt_db, fmt_hz, fmt_speed
    deess = self.clip.effects["deesser"]
    ts = self.clip.effects["time_stretch"]

    panel = QWidget()
    panel.setObjectName("SEContent")
    root = QVBoxLayout(panel)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(14)

    # --- De-esser ---
    deess_header = self._fx_header(
        tr("veditor.sound_editor.adv.deesser"), "deesser"
    )
    self._deess_enabled_btn = deess_header[1]
    root.addWidget(deess_header[0])

    deess_row = FlowLayout(h_spacing=10, v_spacing=6)
    k_dfreq = KnobWidget(
        label="Frequency", value=deess["freq"], minimum=2000, maximum=12000,
        default=6000, color="blue", logarithmic=True, formatter=fmt_hz,
    )
    k_dthr = KnobWidget(
        label="Threshold", value=deess["threshold"], minimum=-60, maximum=0,
        default=-30, unit=" dB", color="green", formatter=fmt_db,
    )
    k_dred = KnobWidget(
        label="Reduction", value=deess["reduction"], minimum=0, maximum=100,
        default=40, color="orange", formatter=lambda v: f"{v:.0f} %",
    )
    k_dfreq.valueChanged.connect(lambda v: self._set_fx("deesser", "freq", v))
    k_dthr.valueChanged.connect(lambda v: self._set_fx("deesser", "threshold", v))
    k_dred.valueChanged.connect(lambda v: self._set_fx("deesser", "reduction", v))
    for k in (k_dfreq, k_dthr, k_dred):
        deess_row.addWidget(k)
    root.addLayout(deess_row)

    # --- Time Stretch ---
    ts_header = self._fx_header(
        tr("veditor.sound_editor.adv.time_stretch"), "time_stretch"
    )
    self._ts_enabled_btn = ts_header[1]
    root.addWidget(ts_header[0])

    ts_row = QHBoxLayout()
    ts_row.setSpacing(10)
    k_ratio = KnobWidget(
        label="Ratio", value=ts["ratio"], minimum=0.5, maximum=2.0,
        default=1.0, color="orange", formatter=fmt_speed,
    )
    k_ratio.valueChanged.connect(lambda v: self._set_fx("time_stretch", "ratio", v))
    ts_row.addWidget(k_ratio)

    # Algorithm dropdown
    from PySide6.QtWidgets import QComboBox
    self._ts_algo = QComboBox()
    self._ts_algo.addItems(["atempo", "rubberband"])
    self._ts_algo.setCurrentText(ts.get("algorithm", "atempo"))
    self._ts_algo.currentTextChanged.connect(
        lambda t: self._set_fx("time_stretch", "algorithm", t)
    )
    algo_label = QLabel(tr("veditor.sound_editor.adv.algorithm"))
    algo_label.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px;")
    ts_row.addWidget(algo_label)
    ts_row.addWidget(self._ts_algo)
    ts_row.addStretch(1)
    root.addLayout(ts_row)

    # --- Markers list ---
    markers_label = QLabel(tr("veditor.sound_editor.adv.markers"))
    markers_label.setStyleSheet(
        f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
        f"font-weight: 700; letter-spacing: 1px; padding-top: 8px;"
    )
    root.addWidget(markers_label)

    from PySide6.QtWidgets import QListWidget
    self._markers_list = QListWidget()
    self._markers_list.setMaximumHeight(110)
    self._refresh_markers_list()
    # Jump to marker on double-click
    self._markers_list.itemDoubleClicked.connect(self._on_marker_list_dblclick)
    root.addWidget(self._markers_list)

    root.addStretch(1)
    return panel

def _build_ai_master_tab(self) -> QWidget:
    from app.knob_widget import FlowLayout, KnobWidget, fmt_db, fmt_percentage
    ai = self.clip.effects["ai_master"]

    panel = QWidget()
    panel.setObjectName("SEContent")
    root = QVBoxLayout(panel)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(14)

    # --- One-Click Fix (preset buttons) ---
    preset_header = QLabel(tr("veditor.sound_editor.ai.one_click"))
    preset_header.setStyleSheet(
        f"color: {COLOR_TEXT_SECONDARY}; font-size: 11px; "
        f"font-weight: 700; letter-spacing: 1px;"
    )
    root.addWidget(preset_header)

    # 6 preset buttons in a 3x2 grid ??gives the AI-model labels
    # room to breathe without eating the knob row's vertical space.
    from PySide6.QtWidgets import QGridLayout
    preset_grid = QGridLayout()
    preset_grid.setSpacing(6)
    names = list(self.AI_PRESETS.keys())
    for idx, name in enumerate(names):
        b = QPushButton(name)
        b.setObjectName("SEAIPresetBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        # Highlight the currently-applied preset.
        if ai.get("preset") == name:
            b.setProperty("selected", True)
        b.clicked.connect(lambda _c, n=name: self._apply_ai_preset(n))
        preset_grid.addWidget(b, idx // 3, idx % 3)
    root.addLayout(preset_grid)
    root.addWidget(self._build_professional_audio_preset_section())

    # --- Detailed controls (6 macro knobs) ---
    ctrl_header = self._fx_header(
        tr("veditor.sound_editor.ai.detailed"),
        "ai_master",
    )
    self._ai_enabled_btn = ctrl_header[1]
    root.addWidget(ctrl_header[0])

    knob_row = FlowLayout(h_spacing=10, v_spacing=6)

    k_air = KnobWidget(
        label="Air", value=float(ai["air"]),
        minimum=0, maximum=8, default=0, unit=" dB",
        color="green", formatter=fmt_db,
    )
    k_clarity = KnobWidget(
        label="Clarity", value=float(ai["clarity"]),
        minimum=0, maximum=100, default=0,
        color="blue", formatter=fmt_percentage,
    )
    k_warmth = KnobWidget(
        label="Warmth", value=float(ai["warmth"]),
        minimum=0, maximum=100, default=0,
        color="orange", formatter=fmt_percentage,
    )
    k_width = KnobWidget(
        label="Width", value=float(ai["width"]),
        minimum=0, maximum=200, default=100,
        color="green", bipolar=True, formatter=fmt_percentage,
    )
    k_punch = KnobWidget(
        label="Punch", value=float(ai["punch"]),
        minimum=0, maximum=100, default=0,
        color="blue", formatter=fmt_percentage,
    )
    k_excite = KnobWidget(
        label="Excite", value=float(ai["excite"]),
        minimum=0, maximum=100, default=0,
        color="orange", formatter=fmt_percentage,
    )

    # Any knob touch implies "user wants custom tuning" ??mark the
    # preset state as Custom so the grid highlight doesn't lie.
    def _on_knob(field: str, value: float) -> None:
        self._set_fx("ai_master", field, float(value))
        if self.clip.effects["ai_master"].get("preset") != "Custom":
            self._set_fx("ai_master", "preset", "Custom")

    k_air.valueChanged.connect(lambda v: _on_knob("air", v))
    k_clarity.valueChanged.connect(lambda v: _on_knob("clarity", v))
    k_warmth.valueChanged.connect(lambda v: _on_knob("warmth", v))
    k_width.valueChanged.connect(lambda v: _on_knob("width", v))
    k_punch.valueChanged.connect(lambda v: _on_knob("punch", v))
    k_excite.valueChanged.connect(lambda v: _on_knob("excite", v))

    for k in (k_air, k_clarity, k_warmth, k_width, k_punch, k_excite):
        knob_row.addWidget(k)
    root.addLayout(knob_row)

    # --- Per-knob description strip (mirrors the HTML mock) ---
    desc_row = FlowLayout(h_spacing=10, v_spacing=4)
    for key in ("air", "clarity", "warmth", "width", "punch", "excite"):
        lbl = QLabel(tr(f"veditor.sound_editor.ai.desc.{key}"))
        lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lbl.setWordWrap(True)
        lbl.setFixedWidth(88)
        lbl.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;"
        )
        desc_row.addWidget(lbl)
    root.addLayout(desc_row)

    # --- Hint / note ---
    note = QLabel(tr("veditor.sound_editor.ai.hint"))
    note.setWordWrap(True)
    note.setStyleSheet(
        f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px; "
        f"padding-top: 6px;"
    )
    root.addWidget(note)

    root.addWidget(self._build_source_separation_section())

    root.addStretch(1)
    return panel

def _build_professional_audio_preset_section(self) -> QWidget:
    box = QFrame()
    box.setObjectName("SEProfessionalAudioSection")
    box.setStyleSheet(
        "QFrame#SEProfessionalAudioSection {"
        "background-color: rgba(74, 144, 216, 0.08);"
        "border: 1px solid rgba(74, 144, 216, 0.30);"
        "border-radius: 6px;"
        "}"
    )
    lay = QVBoxLayout(box)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(8)

    title = QLabel("PROFESSIONAL AUDIO PRESETS")
    title.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; "
        f"font-weight: 700; letter-spacing: 1px;"
    )
    lay.addWidget(title)

    try:
        from app.preset_library import presets_by_kind
        presets = presets_by_kind("audio")
    except Exception:
        presets = []

    grid = QGridLayout()
    grid.setSpacing(6)
    for idx, preset in enumerate(presets):
        b = QPushButton(preset.name)
        b.setObjectName("SEPresetBtn")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setToolTip(f"{preset.name}\n{preset.description}")
        b.clicked.connect(lambda _c, p=preset: self._apply_audio_library_preset(p))
        grid.addWidget(b, idx // 3, idx % 3)
    if not presets:
        empty = QLabel("No audio presets")
        empty.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
        grid.addWidget(empty, 0, 0)
    lay.addLayout(grid)

    hint = QLabel("Dialogue cleanup, loudness, and music-master presets render through the export audio chain.")
    hint.setWordWrap(True)
    hint.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")
    lay.addWidget(hint)
    return box

def _build_source_separation_section(self) -> QWidget:
    box = QFrame()
    box.setObjectName("SEStemSection")
    box.setStyleSheet(
        "QFrame#SEStemSection {"
        "background-color: #15181D;"
        "border: 1px solid #30363D;"
        "border-radius: 6px;"
        "}"
    )
    lay = QVBoxLayout(box)
    lay.setContentsMargins(12, 10, 12, 10)
    lay.setSpacing(6)

    title = QLabel(tr("veditor.sound_editor.stems.title"))
    title.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-size: 12px; "
        f"font-weight: 700; letter-spacing: 1px;"
    )
    body = QLabel(tr("veditor.sound_editor.stems.body"))
    body.setWordWrap(True)
    body.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")

    row = QHBoxLayout()
    self._stem_method_combo = QComboBox()
    self._stem_method_combo.addItem("Auto", True)
    self._stem_method_combo.addItem("Fast fallback", False)
    self._stem_method_combo.setToolTip(
        "Auto uses Demucs when installed. Fast fallback is quicker but less accurate."
    )
    self._stem_separate_btn = QPushButton(tr("veditor.sound_editor.stems.button"))
    self._stem_separate_btn.setObjectName("SEActionBtn")
    self._stem_separate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._stem_separate_btn.clicked.connect(self._on_separate_vocals_clicked)
    row.addWidget(self._stem_method_combo)
    row.addWidget(self._stem_separate_btn)
    row.addStretch(1)

    try:
        from app.audio_separation import planned_separation_method
        method_hint = planned_separation_method(prefer_demucs=True)
    except Exception:
        method_hint = "FFmpeg mid/side"
    warning = QLabel(
        "Backend: "
        + method_hint
        + (
            " - fallback quality; works best with centered vocals"
            if method_hint.lower().startswith("ffmpeg") else ""
        )
    )
    warning.setWordWrap(True)
    warning.setStyleSheet(f"color: {COLOR_TEXT_TERTIARY}; font-size: 10px;")

    lay.addWidget(title)
    lay.addWidget(body)
    lay.addWidget(warning)
    lay.addLayout(row)
    return box

def _build_transport(self) -> QWidget:
    bar = QWidget()
    bar.setObjectName("SETransport")
    bar.setFixedHeight(58)
    lay = QHBoxLayout(bar)
    lay.setContentsMargins(16, 10, 16, 10)
    lay.setSpacing(8)

    def _mk_icon_btn(icon_name: str, tooltip: str, handler) -> QPushButton:
        b = QPushButton("")
        b.setObjectName("SEActionBtn")
        b.setFixedSize(32, 32)
        b.setIcon(app_icon(icon_name, size=15, color="#D7DAE7"))
        b.setIconSize(icon_size(15))
        b.setToolTip(tooltip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(handler)
        return b

    self._prev_marker_btn = _mk_icon_btn(
        "previous", tr("veditor.sound_editor.tooltip.prev_marker"),
        self._go_to_prev_marker,
    )
    self._play_btn = QPushButton("")
    self._play_btn.setObjectName("SEPlayBtn")
    self._play_btn.setFixedSize(36, 36)
    self._play_btn.setIcon(app_icon("play", size=16, color="#FFFFFF"))
    self._play_btn.setIconSize(icon_size(16))
    self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._play_btn.clicked.connect(self._toggle_play)
    self._next_marker_btn = _mk_icon_btn(
        "next", tr("veditor.sound_editor.tooltip.next_marker"),
        self._go_to_next_marker,
    )
    self._add_marker_btn = _mk_icon_btn(
        "marker", tr("veditor.sound_editor.tooltip.add_marker"),
        self._add_marker_at_playhead,
    )
    self._loop_btn = _mk_icon_btn(
        "loop", tr("veditor.sound_editor.tooltip.loop"),
        lambda: None,  # replaced below
    )
    self._loop_btn.setCheckable(True)
    # We want toggled state, so replace the clicked handler with
    # a noop and rely on the checked state directly.
    self._loop_btn.clicked.disconnect()

    self._position_label = QLabel("0:00 / 0:00")
    self._position_label.setStyleSheet(
        f"color: {COLOR_TEXT_PRIMARY}; font-family: Consolas, monospace; font-size: 12px;"
    )

    vol_icon = QLabel("")
    vol_icon.setPixmap(app_icon("speaker", size=14, color="#BFC4D4").pixmap(icon_size(14)))
    vol_icon.setFixedSize(18, 18)
    vol_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    self._transport_volume_slider = StudioSlider("audio")
    self._transport_volume_slider.setRange(0, 100)
    self._transport_volume_slider.setFixedWidth(100)
    self._transport_volume_slider.valueChanged.connect(
        lambda v: self._player_output.setVolume(max(0.0, min(1.0, v / 100.0)))
    )

    # Audio export quality dropdown ??sits left of the export
    # button. Default = "standard" (44.1 kHz / 192 kbps / 16-bit),
    # which matches the Free tier ceiling.
    from app.audio_tracks import DEFAULT_AUDIO_QUALITY_ID
    self._audio_export_quality_id = DEFAULT_AUDIO_QUALITY_ID
    self._audio_quality_btn = QToolButton()
    self._audio_quality_btn.setObjectName("AudioQualityDropdown")
    self._audio_quality_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._audio_quality_btn.setPopupMode(
        QToolButton.ToolButtonPopupMode.InstantPopup,
    )
    self._audio_quality_btn.setToolTip(tr("veditor.export.quality.tooltip"))
    self._audio_quality_btn.setMinimumHeight(28)
    self._audio_quality_btn.setStyleSheet(
        f"QToolButton#AudioQualityDropdown {{ "
        f"background-color: {COLOR_BG_L2}; color: {COLOR_TEXT_PRIMARY}; "
        f"border: 1px solid {COLOR_BORDER_DEFAULT}; border-radius: 4px; "
        f"padding: 3px 26px 3px 10px; font-size: 11px; }}"
        f"QToolButton#AudioQualityDropdown:hover {{ "
        f"background-color: {COLOR_BG_L5}; border-color: #5a5a62; }}"
        f"QToolButton#AudioQualityDropdown::menu-indicator {{ "
        f"image: none; subcontrol-origin: padding; "
        f"subcontrol-position: right center; right: 8px; }}"
    )
    self._refresh_audio_quality_btn_label()
    self._build_audio_quality_menu()

    self._export_btn = QPushButton(tr("veditor.sound_editor.export"))
    self._export_btn.setObjectName("SEClose")
    self._export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._export_btn.setToolTip(tr("veditor.sound_editor.export.tooltip"))
    self._export_btn.clicked.connect(self._on_export_clicked)

    self._apply_btn = QPushButton(tr("veditor.sound_editor.apply"))
    self._apply_btn.setObjectName("SEApply")
    self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._apply_btn.clicked.connect(self._apply_and_close)

    self._close_btn = QPushButton(tr("veditor.sound_editor.close"))
    self._close_btn.setObjectName("SEClose")
    self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    self._close_btn.clicked.connect(self.close)

    lay.addWidget(self._prev_marker_btn)
    lay.addWidget(self._play_btn)
    lay.addWidget(self._next_marker_btn)
    lay.addSpacing(6)
    lay.addWidget(self._add_marker_btn)
    lay.addWidget(self._loop_btn)
    lay.addSpacing(10)
    lay.addWidget(self._position_label)
    lay.addStretch(1)
    lay.addWidget(vol_icon)
    lay.addWidget(self._transport_volume_slider)
    lay.addSpacing(14)
    lay.addWidget(self._audio_quality_btn)
    lay.addWidget(self._export_btn)
    lay.addWidget(self._close_btn)
    lay.addWidget(self._apply_btn)

    # --- keyboard shortcuts (scoped to this window) ---
    from PySide6.QtGui import QKeySequence, QShortcut
    for key, handler in (
        ("Space", self._toggle_play),
        ("M",     self._add_marker_at_playhead),
        ("L",     lambda: self._loop_btn.setChecked(not self._loop_btn.isChecked())),
        (",",     self._go_to_prev_marker),
        (".",     self._go_to_next_marker),
    ):
        sc = QShortcut(QKeySequence(key), self)
        sc.setContext(Qt.ShortcutContext.WindowShortcut)
        sc.activated.connect(handler)

    return bar

