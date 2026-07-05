"""Audio editor style tokens for the main editor renewal pass."""

from __future__ import annotations

AUDIO_BG = "#101010"
AUDIO_BG_ALT = "#121212"
AUDIO_PANEL = "#151515"
AUDIO_PANEL_SOFT = "#181818"
AUDIO_BORDER = "#292929"
AUDIO_BORDER_HI = "#3A3A3A"
AUDIO_TEXT = "#D9DDE2"
AUDIO_TEXT_MUTED = "#A6ACB4"
AUDIO_TEXT_DIM = "#757B84"
AUDIO_LINE = "#B8C5B4"
AUDIO_LINE_DIM = "#7F8C82"
AUDIO_GREEN = "#76917B"
AUDIO_AMBER = "#A49669"
AUDIO_RED = "#A4635E"
AUDIO_BLUE = "#8F9CAD"

MIXER_PANEL_QSS = (
    f"QWidget#AudioMixerPanel {{ background: {AUDIO_BG}; "
    f"border-top: 1px solid {AUDIO_BORDER}; }}"
)

MIXER_TITLE_QSS = (
    f"QWidget#MixerTitleBar {{ background: {AUDIO_PANEL}; "
    f"border-bottom: 1px solid {AUDIO_BORDER}; }}"
)

MIXER_SCOPES_QSS = (
    f"QWidget#MixerScopesCol {{ background: {AUDIO_BG_ALT}; "
    f"border-left: 1px solid {AUDIO_BORDER}; }}"
)

MIXER_SPLITTER_QSS = (
    f"QSplitter::handle {{ background: {AUDIO_BORDER}; }}"
    f"QSplitter::handle:hover {{ background: {AUDIO_BORDER_HI}; }}"
)

CHANNEL_SLIDER_QSS = (
    "QSlider::groove:vertical { background:#252525; width:2px; border-radius:1px; }"
    f"QSlider::add-page:vertical {{ background:{AUDIO_BLUE}; border-radius:1px; }}"
    "QSlider::sub-page:vertical { background:#252525; border-radius:1px; }"
    "QSlider::handle:vertical { background:#D3D7DC; border:1px solid #686E76; "
    "width:11px; height:11px; margin:0 -5px; border-radius:5px; }"
)

PAN_SLIDER_QSS = (
    "QSlider::groove:horizontal { background:#272727; height:2px; border-radius:1px; }"
    "QSlider::sub-page:horizontal { background:#777F8B; border-radius:1px; }"
    "QSlider::add-page:horizontal { background:#272727; border-radius:1px; }"
    "QSlider::handle:horizontal { background:#D5D9DE; border:1px solid #626A74; "
    "width:8px; height:8px; margin:-4px 0; border-radius:4px; }"
)
