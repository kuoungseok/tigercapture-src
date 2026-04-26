"""Typography preset bundles (Phase 4a — first eight).

A preset captures animation choice + intensity + timing + style as a
single unit. Applying one to a clip overwrites the corresponding fields
on the clip's TextStyle + AnimationConfig — anything the preset doesn't
specify is left as-is.

Phase 4b additions (deferred): Eve glitch (RGB split), YOASOBI lyric
sync, Mafumafu blur, Niconico chorus member system, DEVILA strobe (with
photosensitivity warning).
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TypographyPreset:
    """One preset bundle.

    ``style_overrides`` is a partial dict — only listed fields are
    copied onto ``clip.style``. Same shape as TextStyle's attributes.
    Animation fields are explicit (most presets care about them)."""

    id: str
    name_key: str                              # i18n key for display
    category: str                              # 'utaite'/'korean'/'devila'/...
    icon: str = "✨"

    # Animation
    in_animation: str = "fade-in"
    out_animation: str = "fade-out"
    in_duration: float = 0.5                   # seconds
    out_duration: float = 0.5
    in_intensity: float = 100.0
    out_intensity: float = 100.0

    # Style overrides (partial — anything missing keeps clip's current value).
    style_overrides: dict[str, Any] = field(default_factory=dict)

    # Free-form metadata: reference artist name shown in the picker tile,
    # short description for tooltip, etc.
    reference_artist: str = ""
    description: str = ""


# ---------------------------------------------------------------------------
#  Builtin presets
# ---------------------------------------------------------------------------


BUILTIN_PRESETS: list[TypographyPreset] = [
    # --- Utaite / J-MV ---
    TypographyPreset(
        id="ado-explosion",
        name_key="preset.ado_explosion",
        category="utaite",
        icon="💥",
        in_animation="pop-in",
        out_animation="fade-out",
        in_duration=0.45,
        out_duration=0.30,
        in_intensity=160.0,
        style_overrides={
            "font_family": "Shippori Mincho",
            "font_size": 110,
            "font_weight": 900,
            "color": "#FFFFFF",
            "shadow_color": "#FF0033",
            "shadow_offset_x": 8,
            "shadow_offset_y": -4,
            "shadow_blur": 0,
            "outline_color": None,
            "outline_width": 0,
            "background_color": None,
        },
        reference_artist="Ado",
    ),
    TypographyPreset(
        id="eve-glitch",
        name_key="preset.eve_glitch",
        category="utaite",
        icon="⚡",
        in_animation="eve-glitch-in",
        out_animation="fade-out",
        in_duration=0.8,
        out_duration=0.4,
        in_intensity=120.0,
        style_overrides={
            "font_family": "Noto Sans JP",
            "font_size": 84,
            "font_weight": 900,
            "color": "#FFFFFF",
            "letter_spacing": 6,
            "outline_color": None,
            "outline_width": 0,
            "shadow_color": None,
            "background_color": None,
        },
        reference_artist="Eve",
    ),
    TypographyPreset(
        id="suda-whitespace",
        name_key="preset.suda_whitespace",
        category="utaite",
        icon="✦",
        in_animation="fade-in",
        out_animation="fade-out",
        in_duration=1.2,
        out_duration=0.8,
        in_intensity=100.0,
        style_overrides={
            "font_family": "Noto Serif JP",
            "font_size": 48,
            "font_weight": 300,
            "color": "#FFFFFF",
            "letter_spacing": 6,
            "shadow_color": None,
            "outline_color": None,
            "background_color": None,
        },
        reference_artist="須田景凪",
    ),
    TypographyPreset(
        id="title-card",
        name_key="preset.title_card",
        category="utaite",
        icon="🪧",
        in_animation="fade-in",
        out_animation="fade-out",
        in_duration=0.9,
        out_duration=0.5,
        in_intensity=100.0,
        style_overrides={
            "font_family": "Noto Serif KR",
            "font_size": 96,
            "font_weight": 700,
            "color": "#FFFFFF",
            "outline_color": "#0a0a0e",
            "outline_width": 4,
            "shadow_color": None,
            "background_color": None,
        },
    ),
    # --- DEVILA / EDM (lite — strobe deferred to Phase 4b) ---
    TypographyPreset(
        id="edm-drop-laser",
        name_key="preset.edm_drop_laser",
        category="devila",
        icon="⚡",
        in_animation="pop-in",
        out_animation="fade-out",
        in_duration=0.30,
        out_duration=0.30,
        in_intensity=180.0,
        style_overrides={
            "font_family": "Impact",
            "font_size": 130,
            "font_weight": 900,
            "color": "#00FFFF",
            "outline_color": "#FF006E",
            "outline_width": 5,
            "shadow_color": "#00FFFF",
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
            "shadow_blur": 0,
            "background_color": None,
        },
    ),
    # --- Korean broadcast styles ---
    TypographyPreset(
        id="kor-entertainment",
        name_key="preset.kor_entertainment",
        category="korean",
        icon="🎉",
        in_animation="pop-in",
        out_animation="fade-out",
        in_duration=0.35,
        out_duration=0.30,
        in_intensity=130.0,
        style_overrides={
            "font_family": "Pretendard",
            "font_size": 96,
            "font_weight": 900,
            "color": "#FFEB3B",
            "outline_color": "#000000",
            "outline_width": 4,
            "shadow_color": "#000000",
            "shadow_offset_x": 3,
            "shadow_offset_y": 3,
            "shadow_blur": 0,
            "background_color": None,
        },
    ),
    TypographyPreset(
        id="kor-news",
        name_key="preset.kor_news",
        category="korean",
        icon="📰",
        in_animation="slide-up-in",
        out_animation="slide-down-out",
        in_duration=0.45,
        out_duration=0.35,
        in_intensity=80.0,
        out_intensity=80.0,
        style_overrides={
            "font_family": "Noto Sans KR",
            "font_size": 44,
            "font_weight": 700,
            "color": "#FFFFFF",
            "background_color": "#1E3A8A",
            "background_padding": 14,
            "background_radius": 0,
            "outline_color": None,
            "shadow_color": None,
        },
    ),
    TypographyPreset(
        id="kor-drama",
        name_key="preset.kor_drama",
        category="korean",
        icon="🎬",
        in_animation="fade-in",
        out_animation="fade-out",
        in_duration=0.7,
        out_duration=0.5,
        style_overrides={
            "font_family": "Nanum Myeongjo",
            "font_size": 36,
            "font_weight": 400,
            "color": "#FFFFFF",
            "shadow_color": "#000000",
            "shadow_offset_x": 1,
            "shadow_offset_y": 2,
            "shadow_blur": 2,
            "outline_color": None,
            "background_color": None,
        },
    ),
    # --- Kinetic / motion bundles ---
    TypographyPreset(
        id="kinetic-bounce",
        name_key="preset.kinetic_bounce",
        category="kinetic",
        icon="⤓",
        in_animation="bounce-in",
        out_animation="fade-out",
        in_duration=0.9,
        out_duration=0.4,
        in_intensity=120.0,
        style_overrides={
            "font_family": "Pretendard",
            "font_size": 92,
            "font_weight": 900,
            "color": "#FFEB3B",
            "outline_color": "#000000",
            "outline_width": 4,
            "shadow_color": None,
            "background_color": None,
        },
    ),
    TypographyPreset(
        id="kinetic-cyclone",
        name_key="preset.kinetic_cyclone",
        category="kinetic",
        icon="🌀",
        in_animation="spiral-in",
        out_animation="burst-out",
        in_duration=1.0,
        out_duration=0.6,
        in_intensity=120.0,
        out_intensity=130.0,
        style_overrides={
            "font_family": "Noto Sans JP",
            "font_size": 84,
            "font_weight": 900,
            "color": "#FFFFFF",
            "shadow_color": "#4a9bee",
            "shadow_offset_x": 0,
            "shadow_offset_y": 0,
            "shadow_blur": 0,
            "outline_color": None,
            "background_color": None,
        },
    ),
    TypographyPreset(
        id="kinetic-spin-title",
        name_key="preset.kinetic_spin_title",
        category="kinetic",
        icon="⟳",
        in_animation="spin-in",
        out_animation="fade-out",
        in_duration=0.7,
        out_duration=0.5,
        in_intensity=110.0,
        style_overrides={
            "font_family": "Impact",
            "font_size": 120,
            "font_weight": 900,
            "color": "#FFFFFF",
            "outline_color": "#0a0a0e",
            "outline_width": 5,
            "shadow_color": None,
            "background_color": None,
        },
    ),
    TypographyPreset(
        id="kor-vlog",
        name_key="preset.kor_vlog",
        category="korean",
        icon="🌸",
        in_animation="fade-in",
        out_animation="fade-out",
        in_duration=0.6,
        out_duration=0.4,
        style_overrides={
            "font_family": "Gaegu",
            "font_size": 56,
            "font_weight": 700,
            "color": "#FF6B9D",
            "letter_spacing": 3,
            "shadow_color": None,
            "outline_color": None,
            "background_color": None,
        },
    ),
]


# ---------------------------------------------------------------------------
#  Lookup + apply
# ---------------------------------------------------------------------------


_BY_ID: dict[str, TypographyPreset] = {p.id: p for p in BUILTIN_PRESETS}


def get_preset(preset_id: str) -> TypographyPreset | None:
    return _BY_ID.get(preset_id)


def list_presets(category: str | None = None) -> list[TypographyPreset]:
    if category is None:
        return list(BUILTIN_PRESETS)
    return [p for p in BUILTIN_PRESETS if p.category == category]


def apply_preset(clip, preset: TypographyPreset) -> None:
    """Copy the preset onto ``clip`` (in place). Style fields not
    listed in ``style_overrides`` are left untouched so users keep
    their local tweaks (position, alignment, etc.) when switching
    presets."""
    # Animation
    clip.animation.in_animation = preset.in_animation
    clip.animation.out_animation = preset.out_animation
    clip.animation.in_duration = float(preset.in_duration)
    clip.animation.out_duration = float(preset.out_duration)
    clip.animation.in_intensity = float(preset.in_intensity)
    clip.animation.out_intensity = float(preset.out_intensity)
    # Presets define a single primary animation per slot — clear any
    # composed extras the user had stacked on the previous selection so
    # the preset reads cleanly. Users can re-add modifiers afterward.
    clip.animation.in_extras = []
    clip.animation.out_extras = []
    clip.animation.hold_extras = []

    # Style overrides — only listed fields are copied.
    for field_name, value in (preset.style_overrides or {}).items():
        if hasattr(clip.style, field_name):
            setattr(clip.style, field_name, copy.deepcopy(value))
