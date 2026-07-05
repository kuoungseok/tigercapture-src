"""Editor preset library for effects, titles, transitions, and workflow packs."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class EditorPreset:
    id: str
    kind: str  # effect / title / transition / color / audio / template / caption_style / sticker / motion / actor
    name: str
    description: str = ""
    tags: tuple[str, ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EditorPreset":
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            name=str(data.get("name") or data["id"]),
            description=str(data.get("description") or ""),
            tags=tuple(str(t) for t in data.get("tags", []) or []),
            payload=dict(data.get("payload") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "payload": dict(self.payload),
        }


BUILTIN_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-clean-dissolve",
        kind="transition",
        name="Clean Dissolve",
        description="Short cross dissolve for ordinary cuts.",
        tags=("basic", "editorial"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 500},
    ),
    EditorPreset(
        id="transition-dip-white",
        kind="transition",
        name="Dip White",
        description="Flash-like transition for highlights or beat hits.",
        tags=("flash", "music"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 260},
    ),
    EditorPreset(
        id="transition-dip-black",
        kind="transition",
        name="Dip Black",
        description="Fast fade through black for chapter breaks.",
        tags=("basic", "chapter"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 360},
    ),
    EditorPreset(
        id="transition-beat-dissolve",
        kind="transition",
        name="Beat Dissolve",
        description="Very short dissolve for music cuts and montage beats.",
        tags=("music", "montage"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 180},
    ),
    EditorPreset(
        id="transition-long-dissolve",
        kind="transition",
        name="Long Dissolve",
        description="Slower dissolve for scenic or emotional cuts.",
        tags=("cinematic", "slow"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 900},
    ),
    EditorPreset(
        id="effect-punchy-gameplay",
        kind="effect",
        name="Punchy Gameplay",
        description="Sharper, darker-edge clip filter preset for gameplay.",
        tags=("gameplay", "contrast"),
        payload={
            "video_filters": {
                "enabled": True,
                "sharpen": 0.35,
                "vignette": 0.18,
                "vignette_feather": 0.75,
                "chroma_aberration": 0.03,
            }
        },
    ),
    EditorPreset(
        id="effect-soft-focus",
        kind="effect",
        name="Soft Focus",
        description="Subtle vignette and low sharpening for character shots.",
        tags=("portrait", "character"),
        payload={
            "video_filters": {
                "enabled": True,
                "sharpen": 0.0,
                "vignette": 0.12,
                "vignette_feather": 0.9,
            }
        },
    ),
    EditorPreset(
        id="effect-clean-sharpen",
        kind="effect",
        name="Clean Sharpen",
        description="Light sharpening without stylized edge darkening.",
        tags=("utility", "sharp"),
        payload={
            "video_filters": {
                "enabled": True,
                "sharpen": 0.22,
                "vignette": 0.0,
                "denoise": 0.0,
            }
        },
    ),
    EditorPreset(
        id="effect-stream-glitch",
        kind="effect",
        name="Stream Glitch",
        description="Short-form glitch look for alerts, intros, or beat hits.",
        tags=("glitch", "stream"),
        payload={
            "video_filters": {
                "enabled": True,
                "sharpen": 0.18,
                "chroma_aberration": 0.18,
                "glitch": 0.22,
            }
        },
    ),
    EditorPreset(
        id="effect-noise-cleanup",
        kind="effect",
        name="Noise Cleanup",
        description="Conservative denoise preset for noisy captures.",
        tags=("utility", "denoise"),
        payload={
            "video_filters": {
                "enabled": True,
                "denoise": 0.45,
                "sharpen": 0.08,
            }
        },
    ),
    EditorPreset(
        id="effect-green-screen-clean",
        kind="effect",
        name="Green Screen Clean",
        description="Starter chroma key for ordinary green-screen footage.",
        tags=("keying", "green-screen"),
        payload={
            "chroma_key": {
                "enabled": True,
                "key_hue": 60,
                "key_sat": 120,
                "key_val": 120,
                "hue_range": 30,
                "sat_min": 55,
                "val_min": 55,
                "spill_suppress": 0.35,
            }
        },
    ),
    EditorPreset(
        id="title-stream-pop",
        kind="title",
        name="Stream Pop",
        description="Bold outlined title for stream/game captions.",
        tags=("caption", "gameplay"),
        payload={
            "text": "TITLE",
            "duration_ms": 2200,
            "typography_preset_id": "kor-entertainment",
        },
    ),
    EditorPreset(
        id="title-cinematic-card",
        kind="title",
        name="Cinematic Card",
        description="Large centered serif title.",
        tags=("title", "cinematic"),
        payload={
            "text": "TITLE",
            "duration_ms": 2600,
            "typography_preset_id": "title-card",
        },
    ),
    EditorPreset(
        id="title-lower-third-clean",
        kind="title",
        name="Lower Third Clean",
        description="Compact lower-third identifier.",
        tags=("lower-third", "caption"),
        payload={
            "text": "NAME / ROLE",
            "duration_ms": 3200,
            "font_size": 42,
            "x_norm": 0.28,
            "y_norm": 0.78,
            "preset_id_in": "slide-up-in",
            "preset_id_out": "fade-out",
        },
    ),
    EditorPreset(
        id="title-short-caption",
        kind="title",
        name="Short Caption",
        description="Small readable caption near the lower center.",
        tags=("caption", "subtitle"),
        payload={
            "text": "CAPTION",
            "duration_ms": 1800,
            "font_size": 38,
            "x_norm": 0.5,
            "y_norm": 0.82,
            "preset_id_in": "fade-in",
            "preset_id_out": "fade-out",
        },
    ),
    EditorPreset(
        id="title-beat-stamp",
        kind="title",
        name="Beat Stamp",
        description="Quick centered stamp for rhythm edits.",
        tags=("music", "short-form"),
        payload={
            "text": "NOW",
            "duration_ms": 900,
            "font_size": 64,
            "x_norm": 0.5,
            "y_norm": 0.48,
            "preset_id_in": "pop-in",
            "preset_id_out": "pop-out",
        },
    ),
)


COMMERCIAL_POLISH_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-micro-dissolve",
        kind="transition",
        name="Micro Dissolve",
        description="Almost invisible blend for removing hard capture jumps.",
        tags=("basic", "micro", "cleanup"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 90},
    ),
    EditorPreset(
        id="transition-slow-fade-black",
        kind="transition",
        name="Slow Fade Black",
        description="Long fade through black for act breaks.",
        tags=("chapter", "slow", "cinematic"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 1300},
    ),
    EditorPreset(
        id="transition-hit-white",
        kind="transition",
        name="Hit White",
        description="Short white hit for impact frames.",
        tags=("impact", "flash", "short-form"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 140},
    ),
    EditorPreset(
        id="transition-soft-scene",
        kind="transition",
        name="Soft Scene",
        description="Moderate dissolve for B-roll and scenic cuts.",
        tags=("b-roll", "cinematic", "soft"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 680},
    ),
    EditorPreset(
        id="transition-dialogue-bridge",
        kind="transition",
        name="Dialogue Bridge",
        description="Neutral dissolve timed for voice-led edits.",
        tags=("dialogue", "editorial"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 420},
    ),
    EditorPreset(
        id="effect-esports-crisp",
        kind="effect",
        name="Esports Crisp",
        description="Clean, sharp gameplay look with restrained vignette.",
        tags=("gameplay", "sharp", "stream"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.48, "vignette": 0.08, "vignette_feather": 0.82}},
    ),
    EditorPreset(
        id="effect-snow-legibility",
        kind="effect",
        name="Snow Legibility",
        description="Sharpen and edge focus for bright snow or desert captures.",
        tags=("gameplay", "outdoor", "utility"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.32, "vignette": 0.16, "vignette_feather": 0.7}},
    ),
    EditorPreset(
        id="effect-ui-capture-clean",
        kind="effect",
        name="UI Capture Clean",
        description="Low-noise utility preset for menus and software capture.",
        tags=("utility", "ui", "capture"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.16, "denoise": 0.25, "vignette": 0.0}},
    ),
    EditorPreset(
        id="effect-character-focus",
        kind="effect",
        name="Character Focus",
        description="Portrait-friendly edge focus for Live2D or face shots.",
        tags=("portrait", "character", "soft"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.18, "vignette": 0.22, "vignette_feather": 0.95}},
    ),
    EditorPreset(
        id="effect-music-video-pop",
        kind="effect",
        name="Music Video Pop",
        description="Sharper short-form look with mild chromatic edge energy.",
        tags=("music", "short-form", "pop"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.28, "vignette": 0.2, "vignette_feather": 0.78, "chroma_aberration": 0.08}},
    ),
    EditorPreset(
        id="effect-archive-cleanup",
        kind="effect",
        name="Archive Cleanup",
        description="Denoise-first preset for compressed or old footage.",
        tags=("cleanup", "denoise", "archive"),
        payload={"video_filters": {"enabled": True, "denoise": 0.62, "sharpen": 0.04, "vignette": 0.0}},
    ),
    EditorPreset(
        id="effect-blue-screen-clean",
        kind="effect",
        name="Blue Screen Clean",
        description="Starter chroma key for blue-screen footage.",
        tags=("keying", "blue-screen"),
        payload={"chroma_key": {"enabled": True, "key_hue": 120, "key_sat": 120, "key_val": 120, "hue_range": 28, "sat_min": 50, "val_min": 50, "spill_suppress": 0.3}},
    ),
    EditorPreset(
        id="effect-green-screen-tight",
        kind="effect",
        name="Green Screen Tight",
        description="Narrower key for cleaner studio green footage.",
        tags=("keying", "green-screen", "studio"),
        payload={"chroma_key": {"enabled": True, "key_hue": 60, "key_sat": 140, "key_val": 130, "hue_range": 18, "sat_min": 70, "val_min": 65, "spill_suppress": 0.45}},
    ),
    EditorPreset(
        id="title-match-intro",
        kind="title",
        name="Match Intro",
        description="Fast title card for game rounds or match openings.",
        tags=("gameplay", "intro", "title"),
        payload={"text": "MATCH START", "duration_ms": 1600, "font_size": 68, "x_norm": 0.5, "y_norm": 0.42, "preset_id_in": "pop-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-chapter-minimal",
        kind="title",
        name="Chapter Minimal",
        description="Quiet chapter title for long-form edits.",
        tags=("chapter", "minimal", "long-form"),
        payload={"text": "CHAPTER", "duration_ms": 2800, "font_size": 52, "x_norm": 0.5, "y_norm": 0.5, "preset_id_in": "fade-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-top-left-label",
        kind="title",
        name="Top Left Label",
        description="Small persistent locator label.",
        tags=("label", "utility", "caption"),
        payload={"text": "LOCATION", "duration_ms": 4000, "font_size": 30, "x_norm": 0.16, "y_norm": 0.12, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-score-callout",
        kind="title",
        name="Score Callout",
        description="Short score or stat callout for gameplay clips.",
        tags=("gameplay", "score", "callout"),
        payload={"text": "+100", "duration_ms": 1100, "font_size": 72, "x_norm": 0.68, "y_norm": 0.28, "preset_id_in": "pop-in", "preset_id_out": "pop-out"},
    ),
    EditorPreset(
        id="title-speaker-tag",
        kind="title",
        name="Speaker Tag",
        description="Compact speaker label near lower third.",
        tags=("dialogue", "lower-third", "speaker"),
        payload={"text": "SPEAKER", "duration_ms": 3000, "font_size": 34, "x_norm": 0.25, "y_norm": 0.74, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-live2d-nameplate",
        kind="title",
        name="Live2D Nameplate",
        description="Character-name plate that sits clear of actor overlays.",
        tags=("live2d", "character", "lower-third"),
        payload={"text": "CHARACTER", "duration_ms": 2600, "font_size": 40, "x_norm": 0.72, "y_norm": 0.82, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
)


PROFESSIONAL_WORKFLOW_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="color-qualifier-skin-soften",
        kind="color",
        name="Skin Qualifier Soften",
        description="Warm HSL qualifier starter for face/skin cleanup nodes.",
        tags=("color", "qualifier", "portrait", "tracking"),
        payload={
            "color_grade": {"brightness": 2, "contrast": -4, "saturation": -6, "temperature": 4},
            "color_workflow": {
                "enabled": True,
                "name": "Skin Soften",
                "qualifier": {
                    "enabled": True,
                    "hue_center": 28.0,
                    "hue_width": 22.0,
                    "sat_min": 0.12,
                    "sat_max": 0.85,
                    "val_min": 0.18,
                    "val_max": 1.0,
                    "softness": 0.12,
                },
                "window": {"enabled": False},
                "curves": {"master": [(0, 2), (90, 92), (190, 188), (255, 253)]},
                "opacity": 0.72,
            },
        },
    ),
    EditorPreset(
        id="color-window-face-focus",
        kind="color",
        name="Face Focus Window",
        description="Tracked power-window starter for subject brightness and contrast.",
        tags=("color", "window", "tracking", "portrait"),
        payload={
            "color_grade": {"brightness": 9, "contrast": 6, "saturation": 4},
            "color_workflow": {
                "enabled": True,
                "name": "Tracked Face Window",
                "qualifier": {"enabled": False},
                "window": {
                    "enabled": True,
                    "shape": "ellipse",
                    "x": 0.5,
                    "y": 0.43,
                    "w": 0.34,
                    "h": 0.42,
                    "feather": 0.18,
                    "opacity": 0.85,
                    "track_object": True,
                },
                "curves": {"master": [(0, 0), (64, 58), (160, 168), (255, 255)]},
                "opacity": 1.0,
            },
        },
    ),
    EditorPreset(
        id="color-curves-contrast-s",
        kind="color",
        name="Curves Contrast S",
        description="Classic S-curve with restrained saturation for captured footage.",
        tags=("color", "curves", "contrast", "utility"),
        payload={
            "color_grade": {"brightness": 0, "contrast": 4, "saturation": 3},
            "color_workflow": {
                "enabled": True,
                "name": "S Curve",
                "qualifier": {"enabled": False},
                "window": {"enabled": False},
                "curves": {"master": [(0, 0), (48, 38), (128, 128), (208, 220), (255, 255)]},
                "opacity": 1.0,
            },
        },
    ),
    EditorPreset(
        id="color-hdr-zone-product-pop",
        kind="color",
        name="HDR Zone Product Pop",
        description="HDR-zone starter that lifts product detail while protecting highlights.",
        tags=("color", "hdr", "zone", "product", "resolve"),
        payload={
            "color_grade": {"brightness": 0, "contrast": 10, "saturation": 4},
            "advanced_color_toolset": {
                "enabled": True,
                "processing_bits": 32,
                "yrgb": True,
                "hdr_zones": {
                    "enabled": True,
                    "shadow": 5,
                    "dark": 3,
                    "light": 6,
                    "highlight": -4,
                    "specular": -8,
                    "pivot": 0.55,
                },
                "log_wheels": {
                    "shadows": [-0.01, 0.0, 0.02],
                    "midtones": [0.01, 0.0, 0.0],
                    "highlights": [0.0, 0.0, -0.01],
                    "pivot": 0.52,
                },
                "hue_curves": {
                    "hue_vs_sat": [[0, 0.08], [45, 0.05], [120, -0.04], [220, 0.02]],
                    "hue_vs_luma": [[45, 0.02], [210, -0.015]],
                },
                "warper_points": [
                    {"hue": 30, "saturation": 0.7, "hue_shift": -4, "sat_scale": 1.06},
                ],
            },
        },
    ),
    EditorPreset(
        id="color-log-soft-film",
        kind="color",
        name="Log Soft Film",
        description="Soft log-wheel contrast with gentle warm highlights for screen recordings.",
        tags=("color", "log", "film", "resolve"),
        payload={
            "color_grade": {"brightness": 1, "contrast": 6, "saturation": -2},
            "advanced_color_toolset": {
                "enabled": True,
                "processing_bits": 32,
                "yrgb": True,
                "hdr_zones": {"enabled": True, "shadow": -2, "dark": -3, "light": 4, "highlight": -2, "pivot": 0.50},
                "log_wheels": {
                    "shadows": [-0.015, -0.005, 0.015],
                    "midtones": [0.008, 0.002, -0.002],
                    "highlights": [0.018, 0.008, -0.006],
                    "pivot": 0.48,
                },
                "hue_curves": {
                    "hue_vs_sat": [[20, 0.04], [110, -0.05], [210, -0.03]],
                    "hue_vs_luma": [[35, 0.015], [220, -0.01]],
                },
            },
        },
    ),
    EditorPreset(
        id="color-warper-skin-protect",
        kind="color",
        name="Warper Skin Protect",
        description="Color Warper starter that keeps skin warm while cooling busy backgrounds.",
        tags=("color", "warper", "skin", "portrait", "resolve"),
        payload={
            "color_grade": {"brightness": 2, "contrast": 3, "saturation": 1},
            "advanced_color_toolset": {
                "enabled": True,
                "processing_bits": 32,
                "yrgb": True,
                "hue_curves": {
                    "hue_vs_hue": [[28, -2], [210, 3]],
                    "hue_vs_sat": [[28, 0.06], [120, -0.08], [220, -0.04]],
                },
                "warper_points": [
                    {"hue": 28, "saturation": 0.55, "hue_shift": -2, "sat_scale": 1.08},
                    {"hue": 115, "saturation": 0.55, "hue_shift": 4, "sat_scale": 0.92},
                    {"hue": 220, "saturation": 0.45, "hue_shift": -3, "sat_scale": 0.95},
                ],
            },
        },
    ),
    EditorPreset(
        id="audio-dialogue-cleanup-light",
        kind="audio",
        name="Dialogue Cleanup Light",
        description="Low-risk spoken voice cleanup for ordinary screen recordings.",
        tags=("audio", "dialogue", "cleanup", "voice"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.45,
                "noise_reduction": 12.0,
                "highpass_hz": 85.0,
                "hum_remove": True,
                "presence_db": 2.2,
                "air_db": 0.8,
                "de_reverb": 0.12,
                "mouth_click": False,
                "plosive": True,
                "auto_level": True,
            },
            "deesser": {"enabled": True, "freq": 6500.0, "threshold": -31.0, "reduction": 42.0},
        },
    ),
    EditorPreset(
        id="audio-dialogue-cleanup-strong",
        kind="audio",
        name="Dialogue Cleanup Strong",
        description="More aggressive voice cleanup for noisy recordings.",
        tags=("audio", "dialogue", "cleanup", "voice", "noise"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.78,
                "noise_reduction": 19.0,
                "highpass_hz": 105.0,
                "hum_remove": True,
                "presence_db": 3.8,
                "air_db": 1.7,
                "de_reverb": 0.32,
                "mouth_click": True,
                "plosive": True,
                "auto_level": True,
            },
            "deesser": {"enabled": True, "freq": 6800.0, "threshold": -34.0, "reduction": 58.0},
            "comp": {"enabled": True, "threshold": -22.0, "ratio": 3.2, "attack_ms": 4.0, "release_ms": 120.0, "makeup_db": 2.0, "knee_db": 2.0},
        },
    ),
    EditorPreset(
        id="audio-loudness-shortform",
        kind="audio",
        name="Loudness Short-form",
        description="Web video loudness target for shorts and social clips.",
        tags=("audio", "loudness", "short-form", "delivery"),
        payload={"loudness": {"enabled": True, "target_i": -14.0, "true_peak": -1.0, "lra": 11.0, "target_id": "shortform"}},
    ),
    EditorPreset(
        id="audio-loudness-podcast",
        kind="audio",
        name="Loudness Podcast Voice",
        description="Spoken-word loudness target with tighter loudness range.",
        tags=("audio", "loudness", "dialogue", "podcast"),
        payload={"loudness": {"enabled": True, "target_i": -16.0, "true_peak": -1.5, "lra": 7.0, "target_id": "podcast"}},
    ),
    EditorPreset(
        id="audio-music-master-web",
        kind="audio",
        name="Music Master Web",
        description="Simple web master chain for music beds and AI music.",
        tags=("audio", "music", "master", "delivery"),
        payload={
            "ai_master": {
                "enabled": True,
                "preset": "Web Music",
                "air": 2.4,
                "clarity": 42.0,
                "warmth": 18.0,
                "width": 112.0,
                "punch": 32.0,
                "excite": 20.0,
            },
            "loudness": {"enabled": True, "target_i": -14.0, "true_peak": -1.0, "lra": 9.0, "target_id": "stream_music"},
        },
    ),
    EditorPreset(
        id="template-shortform-hook-caption",
        kind="template",
        name="Short-form Hook Caption",
        description="Fast hook, bold captions, hit transition, and web loudness.",
        tags=("template", "short-form", "caption", "one-click"),
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-beat-stamp", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-auto-bold-pop"},
                {"kind": "transition", "preset_id": "transition-hit-white"},
                {"kind": "audio", "preset_id": "audio-loudness-shortform"},
            ]
        },
    ),
    EditorPreset(
        id="template-gameplay-highlight",
        kind="template",
        name="Gameplay Highlight",
        description="Gameplay contrast, impact transition, score callout, and music master.",
        tags=("template", "gameplay", "highlight", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-esports-crisp"},
                {"kind": "title", "preset_id": "title-score-callout"},
                {"kind": "transition", "preset_id": "transition-hit-white"},
                {"kind": "audio", "preset_id": "audio-music-master-web"},
            ]
        },
    ),
    EditorPreset(
        id="template-live2d-reaction",
        kind="template",
        name="Live2D Reaction",
        description="Actor-safe nameplate, character focus, and clean captions.",
        tags=("template", "live2d", "character", "reaction"),
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-live2d-nameplate"},
                {"kind": "effect", "preset_id": "effect-character-focus"},
                {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
            ]
        },
    ),
    EditorPreset(
        id="template-before-after",
        kind="template",
        name="Before After Reveal",
        description="Utility template for comparison edits and repair demos.",
        tags=("template", "comparison", "utility", "one-click"),
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-top-left-label"},
                {"kind": "transition", "preset_id": "transition-clean-dissolve"},
                {"kind": "motion", "preset_id": "motion-camera-punch-in"},
            ]
        },
    ),
    EditorPreset(
        id="template-dialogue-cleanup-cut",
        kind="template",
        name="Dialogue Cleanup Cut",
        description="Voice cleanup, podcast loudness, and readable subtitles.",
        tags=("template", "dialogue", "audio", "subtitle"),
        payload={
            "sequence": [
                {"kind": "audio", "preset_id": "audio-dialogue-cleanup-strong"},
                {"kind": "audio", "preset_id": "audio-loudness-podcast"},
                {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
            ]
        },
    ),
    EditorPreset(
        id="caption-auto-bold-pop",
        kind="caption_style",
        name="Auto Caption Bold Pop",
        description="High-contrast short-form caption style.",
        tags=("caption", "short-form", "subtitle", "style"),
        payload={"font_size": 54, "font_weight": 800, "fill": "#ffffff", "stroke": "#111111", "stroke_width": 7, "y_norm": 0.78, "animation": "pop-in"},
    ),
    EditorPreset(
        id="caption-auto-karaoke",
        kind="caption_style",
        name="Auto Caption Karaoke",
        description="Word-highlight caption styling for music or voice beats.",
        tags=("caption", "karaoke", "music", "subtitle"),
        payload={"font_size": 48, "fill": "#f7f7f2", "stroke": "#101216", "highlight": "#ffcc33", "stroke_width": 6, "word_highlight": True},
    ),
    EditorPreset(
        id="caption-clean-subtitle",
        kind="caption_style",
        name="Clean Subtitle",
        description="Readable subtitle style for long-form dialogue.",
        tags=("caption", "dialogue", "subtitle", "clean"),
        payload={"font_size": 38, "fill": "#f4f5f7", "stroke": "#0b0d10", "stroke_width": 4, "y_norm": 0.84},
    ),
    EditorPreset(
        id="sticker-hit-marker",
        kind="sticker",
        name="Hit Marker",
        description="Impact sticker for gameplay and reaction edits.",
        tags=("sticker", "gameplay", "impact", "short-form"),
        payload={"shape": "crosshair", "duration_ms": 520, "scale": 1.0, "animation": "pop-in"},
    ),
    EditorPreset(
        id="sticker-arrow-callout",
        kind="sticker",
        name="Arrow Callout",
        description="Readable pointer sticker for tutorials or object focus.",
        tags=("sticker", "tutorial", "callout", "utility"),
        payload={"shape": "arrow", "duration_ms": 1800, "scale": 0.85, "color": "#ff6a35"},
    ),
    EditorPreset(
        id="sticker-reaction-bubble",
        kind="sticker",
        name="Reaction Bubble",
        description="Small reaction bubble for creator commentary edits.",
        tags=("sticker", "reaction", "live2d", "short-form"),
        payload={"shape": "bubble", "duration_ms": 1500, "scale": 0.9, "animation": "slide-up-in"},
    ),
    EditorPreset(
        id="motion-camera-punch-in",
        kind="motion",
        name="Camera Punch In",
        description="Fast zoom-in motion preset for impact frames.",
        tags=("motion", "zoom", "impact", "short-form"),
        payload={"keyframes": [{"t": 0.0, "scale": 1.0}, {"t": 0.18, "scale": 1.16}, {"t": 1.0, "scale": 1.08}], "easing": "easeOutCubic"},
    ),
    EditorPreset(
        id="motion-ken-burns-soft",
        kind="motion",
        name="Ken Burns Soft",
        description="Slow editorial zoom and pan for stills or quiet B-roll.",
        tags=("motion", "b-roll", "photo", "cinematic"),
        payload={"keyframes": [{"t": 0.0, "scale": 1.0, "x": 0.5, "y": 0.5}, {"t": 1.0, "scale": 1.08, "x": 0.52, "y": 0.48}], "easing": "linear"},
    ),
    EditorPreset(
        id="motion-shake-impact",
        kind="motion",
        name="Impact Shake",
        description="Short impact shake for hits and beat drops.",
        tags=("motion", "shake", "impact", "gameplay"),
        payload={"duration_ms": 260, "amplitude": 0.018, "frequency": 22.0, "decay": 0.75},
    ),
)


SOCIAL_CREATOR_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-snap-zoom",
        kind="transition",
        name="Snap Zoom",
        description="Fast dissolve-width cut point for punch-in edits.",
        tags=("transition", "short-form", "impact", "zoom"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 110},
    ),
    EditorPreset(
        id="transition-comment-pop",
        kind="transition",
        name="Comment Pop",
        description="Brief white hit for comment/reaction reveals.",
        tags=("transition", "comment", "reaction", "short-form"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 170},
    ),
    EditorPreset(
        id="transition-tutorial-step",
        kind="transition",
        name="Tutorial Step",
        description="Clean editorial dissolve between instructional steps.",
        tags=("transition", "tutorial", "how-to", "utility"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 260},
    ),
    EditorPreset(
        id="transition-stream-stinger-lite",
        kind="transition",
        name="Stream Stinger Lite",
        description="Short dip-through-black substitute for stream stingers.",
        tags=("transition", "stream", "stinger", "gameplay"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 240},
    ),
    EditorPreset(
        id="transition-product-reveal",
        kind="transition",
        name="Product Reveal",
        description="Soft reveal transition for feature demos and comparison cuts.",
        tags=("transition", "product", "demo", "commercial"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 520},
    ),
    EditorPreset(
        id="effect-tutorial-cursor-clarity",
        kind="effect",
        name="Tutorial Cursor Clarity",
        description="UI/screen capture filter tuned for readable tutorials.",
        tags=("effect", "tutorial", "screen", "cursor", "utility"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.24, "denoise": 0.14, "vignette": 0.0}},
    ),
    EditorPreset(
        id="effect-vertical-creator-clean",
        kind="effect",
        name="Vertical Creator Clean",
        description="Balanced short-form look that keeps faces and UI readable.",
        tags=("effect", "short-form", "vertical", "creator", "social"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.22, "denoise": 0.08, "vignette": 0.1, "vignette_feather": 0.88}},
    ),
    EditorPreset(
        id="effect-vtuber-overlay-pop",
        kind="effect",
        name="VTuber Overlay Pop",
        description="Character-overlay friendly focus with mild chromatic energy.",
        tags=("effect", "vtuber", "live2d", "spine", "reaction", "character"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.2, "vignette": 0.18, "vignette_feather": 0.92, "chroma_aberration": 0.04}},
    ),
    EditorPreset(
        id="effect-product-demo-polish",
        kind="effect",
        name="Product Demo Polish",
        description="Crisp utility grade for product, app, and feature demos.",
        tags=("effect", "product", "demo", "commercial", "ui"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.26, "denoise": 0.12, "vignette": 0.04, "vignette_feather": 0.9}},
    ),
    EditorPreset(
        id="effect-night-gameplay-recover",
        kind="effect",
        name="Night Gameplay Recover",
        description="Denoise and restrained edge focus for dark gameplay captures.",
        tags=("effect", "gameplay", "night", "cleanup"),
        payload={"video_filters": {"enabled": True, "denoise": 0.35, "sharpen": 0.16, "vignette": 0.06, "vignette_feather": 0.82}},
    ),
    EditorPreset(
        id="effect-meme-punch",
        kind="effect",
        name="Meme Punch",
        description="Loud edge-energy preset for punchline and reaction beats.",
        tags=("effect", "meme", "reaction", "short-form", "impact"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.34, "vignette": 0.16, "vignette_feather": 0.72, "chroma_aberration": 0.12, "glitch": 0.08}},
    ),
    EditorPreset(
        id="title-hook-question",
        kind="title",
        name="Hook Question",
        description="First-second question title for short-form openings.",
        tags=("title", "hook", "short-form", "social"),
        payload={"text": "WAIT, WHAT?", "duration_ms": 1300, "font_size": 58, "x_norm": 0.5, "y_norm": 0.26, "preset_id_in": "pop-in", "preset_id_out": "pop-out"},
    ),
    EditorPreset(
        id="title-tutorial-step",
        kind="title",
        name="Tutorial Step Label",
        description="Compact step title for how-to edits.",
        tags=("title", "tutorial", "how-to", "step"),
        payload={"text": "STEP 1", "duration_ms": 1800, "font_size": 42, "x_norm": 0.18, "y_norm": 0.16, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-comment-pin",
        kind="title",
        name="Pinned Comment",
        description="Comment-style callout for creator replies.",
        tags=("title", "comment", "reaction", "social"),
        payload={"text": "COMMENT", "duration_ms": 2600, "font_size": 34, "x_norm": 0.5, "y_norm": 0.18, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-price-tag",
        kind="title",
        name="Price Tag",
        description="Readable feature/price label for product clips.",
        tags=("title", "product", "demo", "commercial"),
        payload={"text": "$19", "duration_ms": 1600, "font_size": 52, "x_norm": 0.72, "y_norm": 0.32, "preset_id_in": "pop-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-warning-banner",
        kind="title",
        name="Warning Banner",
        description="Strong upper banner for risk, fail, or important moments.",
        tags=("title", "warning", "gameplay", "tutorial"),
        payload={"text": "WATCH THIS", "duration_ms": 1700, "font_size": 44, "x_norm": 0.5, "y_norm": 0.12, "preset_id_in": "slide-up-in", "preset_id_out": "pop-out"},
    ),
    EditorPreset(
        id="title-subscribe-lower",
        kind="title",
        name="Subscribe Lower",
        description="Quiet creator CTA that avoids the center action.",
        tags=("title", "creator", "social", "lower-third"),
        payload={"text": "SUBSCRIBE", "duration_ms": 2400, "font_size": 36, "x_norm": 0.24, "y_norm": 0.86, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="color-social-vertical-pop",
        kind="color",
        name="Social Vertical Pop",
        description="Short-form color starter with a face-safe contrast lift.",
        tags=("color", "short-form", "vertical", "creator"),
        payload={
            "color_grade": {"brightness": 3, "contrast": 8, "saturation": 8, "temperature": 1},
            "color_workflow": {
                "enabled": True,
                "name": "Social Pop",
                "qualifier": {"enabled": False},
                "window": {"enabled": False},
                "curves": {"master": [(0, 0), (52, 44), (128, 130), (210, 222), (255, 255)]},
                "opacity": 0.92,
            },
        },
    ),
    EditorPreset(
        id="color-product-demo-clean",
        kind="color",
        name="Product Demo Clean",
        description="Neutral product/app demo grade with readable whites.",
        tags=("color", "product", "demo", "commercial", "ui"),
        payload={
            "color_grade": {"brightness": 4, "contrast": 3, "saturation": -2, "temperature": 0},
            "color_workflow": {
                "enabled": True,
                "name": "Product Clean",
                "qualifier": {"enabled": False},
                "window": {"enabled": False},
                "curves": {"master": [(0, 2), (80, 82), (180, 184), (255, 254)]},
                "opacity": 0.86,
            },
        },
    ),
    EditorPreset(
        id="audio-streamer-voice",
        kind="audio",
        name="Streamer Voice",
        description="Creator voice cleanup with web loudness and presence.",
        tags=("audio", "dialogue", "stream", "creator", "voice"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.62,
                "noise_reduction": 15.0,
                "highpass_hz": 90.0,
                "hum_remove": True,
                "presence_db": 3.0,
                "air_db": 1.4,
                "de_reverb": 0.18,
                "mouth_click": True,
                "plosive": True,
                "auto_level": True,
            },
            "comp": {"enabled": True, "threshold": -20.0, "ratio": 2.8, "attack_ms": 5.0, "release_ms": 105.0, "makeup_db": 1.8, "knee_db": 2.5},
            "loudness": {"enabled": True, "target_i": -14.0, "true_peak": -1.0, "lra": 8.0, "target_id": "shortform"},
        },
    ),
    EditorPreset(
        id="audio-ducked-music-bed",
        kind="audio",
        name="Ducked Music Bed",
        description="Music bed starter for social edits with conservative web loudness.",
        tags=("audio", "music", "short-form", "delivery"),
        payload={
            "ai_master": {"enabled": True, "preset": "Ducked Bed", "air": 1.2, "clarity": 26.0, "warmth": 14.0, "width": 106.0, "punch": 18.0, "excite": 8.0},
            "loudness": {"enabled": True, "target_i": -18.0, "true_peak": -1.5, "lra": 10.0, "target_id": "music_bed"},
        },
    ),
    EditorPreset(
        id="caption-meme-punch",
        kind="caption_style",
        name="Meme Punch Caption",
        description="Large punchline caption for reaction and meme edits.",
        tags=("caption", "meme", "reaction", "short-form"),
        payload={"font_size": 62, "font_weight": 900, "fill": "#ffffff", "stroke": "#050505", "stroke_width": 8, "y_norm": 0.72, "animation": "pop-in"},
    ),
    EditorPreset(
        id="caption-vertical-safe",
        kind="caption_style",
        name="Vertical Safe Caption",
        description="Safe-zone caption style for Shorts/Reels/TikTok framing.",
        tags=("caption", "vertical", "short-form", "safe-zone"),
        payload={"font_size": 46, "font_weight": 800, "fill": "#f7f7f7", "stroke": "#111111", "stroke_width": 6, "y_norm": 0.7, "animation": "slide-up-in"},
    ),
    EditorPreset(
        id="caption-streamer-outline",
        kind="caption_style",
        name="Streamer Outline Caption",
        description="Readable outline caption for game capture backgrounds.",
        tags=("caption", "stream", "gameplay", "subtitle"),
        payload={"font_size": 42, "font_weight": 800, "fill": "#ffe45e", "stroke": "#111214", "stroke_width": 6, "y_norm": 0.8, "animation": "fade-in"},
    ),
    EditorPreset(
        id="caption-tutorial-compact",
        kind="caption_style",
        name="Tutorial Compact Caption",
        description="Small instruction caption that leaves the work area visible.",
        tags=("caption", "tutorial", "utility", "screen"),
        payload={"font_size": 34, "font_weight": 700, "fill": "#f2f4f8", "stroke": "#14161a", "stroke_width": 4, "y_norm": 0.88, "animation": "fade-in"},
    ),
    EditorPreset(
        id="sticker-subscribe-ping",
        kind="sticker",
        name="Subscribe Ping",
        description="Small CTA sticker for creator edits.",
        tags=("sticker", "creator", "social", "cta"),
        payload={"shape": "subscribe", "text": "SUB", "duration_ms": 1400, "scale": 0.8, "color": "#ff4d4d", "x_norm": 0.8, "y_norm": 0.2},
    ),
    EditorPreset(
        id="sticker-circle-highlight",
        kind="sticker",
        name="Circle Highlight",
        description="Simple target marker for product and tutorial focus.",
        tags=("sticker", "tutorial", "product", "callout"),
        payload={"shape": "circle", "text": "O", "duration_ms": 1500, "scale": 0.95, "color": "#57d9ff", "x_norm": 0.58, "y_norm": 0.42},
    ),
    EditorPreset(
        id="sticker-censor-label",
        kind="sticker",
        name="Censor Label",
        description="Quick label for privacy, spoilers, and comic timing.",
        tags=("sticker", "meme", "privacy", "label"),
        payload={"shape": "censor", "text": "HIDE", "duration_ms": 1200, "scale": 0.75, "color": "#111111", "x_norm": 0.5, "y_norm": 0.5},
    ),
    EditorPreset(
        id="sticker-new-badge",
        kind="sticker",
        name="New Badge",
        description="Small badge for product or feature announcements.",
        tags=("sticker", "product", "demo", "commercial"),
        payload={"shape": "badge", "text": "NEW", "duration_ms": 1600, "scale": 0.72, "color": "#35f2a6", "x_norm": 0.74, "y_norm": 0.24},
    ),
    EditorPreset(
        id="sticker-step-marker",
        kind="sticker",
        name="Step Marker",
        description="Numbered marker for tutorial steps.",
        tags=("sticker", "tutorial", "step", "how-to"),
        payload={"shape": "step", "text": "1", "duration_ms": 1700, "scale": 0.8, "color": "#ffcc33", "x_norm": 0.18, "y_norm": 0.22},
    ),
    EditorPreset(
        id="sticker-like-burst",
        kind="sticker",
        name="Like Burst",
        description="Short positive-feedback sticker for social clips.",
        tags=("sticker", "social", "reaction", "cta"),
        payload={"shape": "burst", "text": "LIKE", "duration_ms": 900, "scale": 0.85, "color": "#b57cff", "x_norm": 0.68, "y_norm": 0.3},
    ),
    EditorPreset(
        id="motion-vertical-reframe",
        kind="motion",
        name="Vertical Reframe Push",
        description="Gentle punch-in for vertical social framing.",
        tags=("motion", "vertical", "short-form", "reframe"),
        payload={"keyframes": [{"t": 0.0, "scale": 1.0, "x": 0.5, "y": 0.5}, {"t": 1.0, "scale": 1.12, "x": 0.5, "y": 0.46}], "easing": "easeOutCubic"},
    ),
    EditorPreset(
        id="motion-product-push",
        kind="motion",
        name="Product Push",
        description="Slow feature-demo push for product closeups.",
        tags=("motion", "product", "demo", "commercial"),
        payload={"keyframes": [{"t": 0.0, "scale": 1.0, "x": 0.5, "y": 0.5}, {"t": 1.0, "scale": 1.07, "x": 0.52, "y": 0.5}], "easing": "linear"},
    ),
    EditorPreset(
        id="motion-beat-bounce",
        kind="motion",
        name="Beat Bounce",
        description="Tiny bounce motion for punchline or music beats.",
        tags=("motion", "music", "meme", "short-form"),
        payload={"duration_ms": 360, "amplitude": 0.012, "frequency": 16.0, "decay": 0.68},
    ),
    EditorPreset(
        id="template-social-listicle",
        kind="template",
        name="Social Listicle",
        description="Hook, vertical-safe captions, CTA, and web loudness.",
        tags=("template", "short-form", "vertical", "social", "one-click"),
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-hook-question", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-vertical-safe"},
                {"kind": "motion", "preset_id": "motion-vertical-reframe"},
                {"kind": "sticker", "preset_id": "sticker-like-burst", "at_ms": 900},
                {"kind": "audio", "preset_id": "audio-loudness-shortform"},
            ]
        },
    ),
    EditorPreset(
        id="template-tutorial-step-by-step",
        kind="template",
        name="Tutorial Step-by-step",
        description="Screen clarity, step label, compact captions, and callout marker.",
        tags=("template", "tutorial", "how-to", "screen", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-tutorial-cursor-clarity"},
                {"kind": "title", "preset_id": "title-tutorial-step", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-tutorial-compact"},
                {"kind": "sticker", "preset_id": "sticker-step-marker", "at_ms": 350},
                {"kind": "transition", "preset_id": "transition-tutorial-step"},
            ]
        },
    ),
    EditorPreset(
        id="template-product-demo-clean",
        kind="template",
        name="Product Demo Clean",
        description="Polished product/app demo pack with reveal, badge, and clean grade.",
        tags=("template", "product", "demo", "commercial", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-product-demo-polish"},
                {"kind": "color", "preset_id": "color-product-demo-clean"},
                {"kind": "title", "preset_id": "title-price-tag", "at_ms": 400},
                {"kind": "sticker", "preset_id": "sticker-new-badge", "at_ms": 700},
                {"kind": "motion", "preset_id": "motion-product-push"},
                {"kind": "transition", "preset_id": "transition-product-reveal"},
            ]
        },
    ),
    EditorPreset(
        id="template-stream-highlight-pack",
        kind="template",
        name="Stream Highlight Pack",
        description="Gameplay filter, streamer captions, voice chain, hit marker, and stinger.",
        tags=("template", "stream", "gameplay", "highlight", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-esports-crisp"},
                {"kind": "caption_style", "preset_id": "caption-streamer-outline"},
                {"kind": "audio", "preset_id": "audio-streamer-voice"},
                {"kind": "sticker", "preset_id": "sticker-hit-marker", "at_ms": 300},
                {"kind": "transition", "preset_id": "transition-stream-stinger-lite"},
            ]
        },
    ),
    EditorPreset(
        id="template-reaction-punch-pack",
        kind="template",
        name="Reaction Punch Pack",
        description="Pinned comment, meme punch captions, reaction bubble, and impact motion.",
        tags=("template", "reaction", "meme", "short-form", "one-click"),
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-comment-pin", "at_ms": 0},
                {"kind": "effect", "preset_id": "effect-meme-punch"},
                {"kind": "caption_style", "preset_id": "caption-meme-punch"},
                {"kind": "sticker", "preset_id": "sticker-reaction-bubble", "at_ms": 500},
                {"kind": "motion", "preset_id": "motion-beat-bounce"},
                {"kind": "transition", "preset_id": "transition-comment-pop"},
            ]
        },
    ),
    EditorPreset(
        id="template-clean-talking-head",
        kind="template",
        name="Clean Talking Head",
        description="Voice cleanup, face-safe grade, readable captions, and lower CTA.",
        tags=("template", "dialogue", "creator", "talking-head", "one-click"),
        payload={
            "sequence": [
                {"kind": "audio", "preset_id": "audio-streamer-voice"},
                {"kind": "color", "preset_id": "color-social-vertical-pop"},
                {"kind": "caption_style", "preset_id": "caption-clean-subtitle"},
                {"kind": "title", "preset_id": "title-subscribe-lower", "at_ms": 1200},
            ]
        },
    ),
)


PRODUCTION_TEMPLATE_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-documentary-cut",
        kind="transition",
        name="Documentary Cut",
        description="Neutral dissolve for voice-led documentary edits.",
        tags=("transition", "documentary", "editorial", "voice"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 360},
    ),
    EditorPreset(
        id="transition-ranking-pop",
        kind="transition",
        name="Ranking Pop",
        description="Short white hit for rank changes and countdown reveals.",
        tags=("transition", "ranking", "short-form", "impact"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 130},
    ),
    EditorPreset(
        id="transition-mobile-slide-lite",
        kind="transition",
        name="Mobile Slide Lite",
        description="Fast clean transition for app and phone-screen demos.",
        tags=("transition", "mobile", "app", "tutorial"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 150},
    ),
    EditorPreset(
        id="transition-news-break",
        kind="transition",
        name="News Break",
        description="Brief dip-through-black for segment breaks and headlines.",
        tags=("transition", "news", "chapter", "editorial"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 220},
    ),
    EditorPreset(
        id="effect-documentary-clarity",
        kind="effect",
        name="Documentary Clarity",
        description="Natural sharpening and mild denoise for voice-led edits.",
        tags=("effect", "documentary", "editorial", "clarity"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.18, "denoise": 0.18, "vignette": 0.04, "vignette_feather": 0.9}},
    ),
    EditorPreset(
        id="effect-anime-cleanline",
        kind="effect",
        name="Anime Cleanline",
        description="Clean edge emphasis for anime, Spine, and Live2D captures.",
        tags=("effect", "anime", "live2d", "spine", "character"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.3, "denoise": 0.06, "vignette": 0.08, "vignette_feather": 0.94}},
    ),
    EditorPreset(
        id="effect-mobile-screen-pop",
        kind="effect",
        name="Mobile Screen Pop",
        description="Readable phone/app capture look with controlled contrast.",
        tags=("effect", "mobile", "app", "screen", "tutorial"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.2, "denoise": 0.1, "vignette": 0.0}},
    ),
    EditorPreset(
        id="effect-food-product-gloss",
        kind="effect",
        name="Food Product Gloss",
        description="Bright product polish for food, merch, and closeups.",
        tags=("effect", "food", "product", "commercial", "gloss"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.24, "denoise": 0.1, "vignette": 0.06, "vignette_feather": 0.86}},
    ),
    EditorPreset(
        id="effect-hdr-soft-recover",
        kind="effect",
        name="HDR Soft Recover",
        description="Gentle cleanup starter for bright capture footage.",
        tags=("effect", "hdr", "cleanup", "utility"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.12, "denoise": 0.22, "vignette": 0.0}},
    ),
    EditorPreset(
        id="title-news-lower-third",
        kind="title",
        name="News Lower Third",
        description="Compact headline lower third for news or update clips.",
        tags=("title", "news", "lower-third", "editorial"),
        payload={"text": "HEADLINE", "duration_ms": 3200, "font_size": 38, "x_norm": 0.28, "y_norm": 0.78, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-hotkey-tip",
        kind="title",
        name="Hotkey Tip",
        description="Small keyboard-tip label for app tutorials.",
        tags=("title", "hotkey", "tutorial", "screen"),
        payload={"text": "CTRL + S", "duration_ms": 2200, "font_size": 34, "x_norm": 0.22, "y_norm": 0.18, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-ranking-number",
        kind="title",
        name="Ranking Number",
        description="Large rank number for list and countdown videos.",
        tags=("title", "ranking", "listicle", "short-form"),
        payload={"text": "#1", "duration_ms": 1200, "font_size": 76, "x_norm": 0.18, "y_norm": 0.28, "preset_id_in": "pop-in", "preset_id_out": "pop-out"},
    ),
    EditorPreset(
        id="title-release-badge",
        kind="title",
        name="Release Badge",
        description="Short badge title for updates, patches, and releases.",
        tags=("title", "release", "product", "badge"),
        payload={"text": "NEW UPDATE", "duration_ms": 1700, "font_size": 40, "x_norm": 0.68, "y_norm": 0.2, "preset_id_in": "pop-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="audio-dialogue-noisy-room",
        kind="audio",
        name="Noisy Room Dialogue",
        description="More cleanup for room noise, hum, and inconsistent speech.",
        tags=("audio", "dialogue", "noise", "cleanup", "voice"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.84,
                "noise_reduction": 22.0,
                "highpass_hz": 115.0,
                "hum_remove": True,
                "presence_db": 4.1,
                "air_db": 1.2,
                "de_reverb": 0.38,
                "mouth_click": True,
                "plosive": True,
                "auto_level": True,
            },
            "deesser": {"enabled": True, "freq": 7000.0, "threshold": -35.0, "reduction": 62.0},
            "loudness": {"enabled": True, "target_i": -16.0, "true_peak": -1.2, "lra": 8.0, "target_id": "voice_noisy_room"},
        },
    ),
    EditorPreset(
        id="audio-voiceover-bright-web",
        kind="audio",
        name="Voiceover Bright Web",
        description="Bright web voiceover chain with safe loudness.",
        tags=("audio", "voiceover", "dialogue", "delivery"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.56,
                "noise_reduction": 10.0,
                "highpass_hz": 90.0,
                "hum_remove": True,
                "presence_db": 3.5,
                "air_db": 2.0,
                "de_reverb": 0.14,
                "mouth_click": False,
                "plosive": True,
                "auto_level": True,
            },
            "comp": {"enabled": True, "threshold": -21.0, "ratio": 2.6, "attack_ms": 4.5, "release_ms": 95.0, "makeup_db": 1.6, "knee_db": 2.0},
            "loudness": {"enabled": True, "target_i": -14.0, "true_peak": -1.0, "lra": 9.0, "target_id": "web_voiceover"},
        },
    ),
    EditorPreset(
        id="caption-documentary-clear",
        kind="caption_style",
        name="Documentary Clear Caption",
        description="Readable subtitle style for quiet editorial videos.",
        tags=("caption", "documentary", "editorial", "subtitle"),
        payload={"font_size": 36, "font_weight": 650, "fill": "#f3f4f6", "stroke": "#111318", "stroke_width": 4, "y_norm": 0.82, "animation": "fade-in"},
    ),
    EditorPreset(
        id="caption-hotkey-small",
        kind="caption_style",
        name="Hotkey Small Caption",
        description="Small tutorial caption that avoids covering the cursor.",
        tags=("caption", "hotkey", "tutorial", "screen"),
        payload={"font_size": 30, "font_weight": 700, "fill": "#ffffff", "stroke": "#12151a", "stroke_width": 4, "y_norm": 0.9, "animation": "fade-in"},
    ),
    EditorPreset(
        id="sticker-hotkey-keycap",
        kind="sticker",
        name="Hotkey Keycap",
        description="Keyboard keycap sticker for software tutorials.",
        tags=("sticker", "hotkey", "tutorial", "screen"),
        payload={"shape": "keycap", "text": "K", "duration_ms": 1700, "scale": 0.72, "color": "#3fa7ff", "x_norm": 0.18, "y_norm": 0.78},
    ),
    EditorPreset(
        id="sticker-ranking-medal",
        kind="sticker",
        name="Ranking Medal",
        description="Small medal badge for listicle and countdown edits.",
        tags=("sticker", "ranking", "listicle", "short-form"),
        payload={"shape": "medal", "text": "1", "duration_ms": 1200, "scale": 0.82, "color": "#ffd45a", "x_norm": 0.22, "y_norm": 0.22},
    ),
    EditorPreset(
        id="template-news-brief",
        kind="template",
        name="News Brief",
        description="Headline lower third, documentary clarity, clear captions, and segment break.",
        tags=("template", "news", "documentary", "editorial", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-documentary-clarity"},
                {"kind": "title", "preset_id": "title-news-lower-third", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-documentary-clear"},
                {"kind": "transition", "preset_id": "transition-news-break"},
                {"kind": "audio", "preset_id": "audio-voiceover-bright-web"},
            ]
        },
    ),
    EditorPreset(
        id="template-hotkey-tutorial",
        kind="template",
        name="Hotkey Tutorial",
        description="Screen pop, hotkey title, keycap sticker, small captions, and mobile-safe cut.",
        tags=("template", "hotkey", "tutorial", "screen", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-mobile-screen-pop"},
                {"kind": "title", "preset_id": "title-hotkey-tip", "at_ms": 0},
                {"kind": "sticker", "preset_id": "sticker-hotkey-keycap", "at_ms": 260},
                {"kind": "caption_style", "preset_id": "caption-hotkey-small"},
                {"kind": "transition", "preset_id": "transition-mobile-slide-lite"},
            ]
        },
    ),
    EditorPreset(
        id="template-ranking-short",
        kind="template",
        name="Ranking Short",
        description="Rank number, medal sticker, bold transition, and short-form loudness.",
        tags=("template", "ranking", "listicle", "short-form", "one-click"),
        payload={
            "sequence": [
                {"kind": "title", "preset_id": "title-ranking-number", "at_ms": 0},
                {"kind": "sticker", "preset_id": "sticker-ranking-medal", "at_ms": 200},
                {"kind": "caption_style", "preset_id": "caption-auto-bold-pop"},
                {"kind": "transition", "preset_id": "transition-ranking-pop"},
                {"kind": "audio", "preset_id": "audio-loudness-shortform"},
            ]
        },
    ),
    EditorPreset(
        id="template-anime-reaction-clean",
        kind="template",
        name="Anime Reaction Clean",
        description="Cleanline effect, actor-safe nameplate, reaction caption, and bright voice.",
        tags=("template", "anime", "live2d", "spine", "reaction", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-anime-cleanline"},
                {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-meme-punch"},
                {"kind": "audio", "preset_id": "audio-voiceover-bright-web"},
                {"kind": "transition", "preset_id": "transition-comment-pop"},
            ]
        },
    ),
    EditorPreset(
        id="template-product-food-gloss",
        kind="template",
        name="Product Food Gloss",
        description="Glossy product/food look with release badge and gentle product push.",
        tags=("template", "food", "product", "commercial", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-food-product-gloss"},
                {"kind": "color", "preset_id": "color-product-demo-clean"},
                {"kind": "title", "preset_id": "title-release-badge", "at_ms": 300},
                {"kind": "motion", "preset_id": "motion-product-push"},
                {"kind": "transition", "preset_id": "transition-product-reveal"},
            ]
        },
    ),
)


CONTENT_EXPANSION_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-broll-wipe-lite",
        kind="transition",
        name="B-roll Wipe Lite",
        description="Fast dissolve-style break for B-roll inserts and cutaways.",
        tags=("transition", "b-roll", "cutaway", "editorial"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 210},
    ),
    EditorPreset(
        id="transition-review-split",
        kind="transition",
        name="Review Split",
        description="Clean split-point transition for comparisons and product reviews.",
        tags=("transition", "review", "comparison", "product"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 240},
    ),
    EditorPreset(
        id="transition-podcast-chapter",
        kind="transition",
        name="Podcast Chapter",
        description="Quiet chapter transition for talking-head and podcast edits.",
        tags=("transition", "podcast", "chapter", "dialogue"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 300},
    ),
    EditorPreset(
        id="effect-broll-soft-detail",
        kind="effect",
        name="B-roll Soft Detail",
        description="Natural detail and slight vignette for supporting footage.",
        tags=("effect", "b-roll", "cutaway", "editorial"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.16, "denoise": 0.12, "vignette": 0.08, "vignette_feather": 0.92}},
    ),
    EditorPreset(
        id="effect-podcast-face-clean",
        kind="effect",
        name="Podcast Face Clean",
        description="Low-risk talking-head cleanup that keeps skin texture intact.",
        tags=("effect", "podcast", "dialogue", "talking-head"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.14, "denoise": 0.2, "vignette": 0.05, "vignette_feather": 0.94}},
    ),
    EditorPreset(
        id="effect-product-review-neutral",
        kind="effect",
        name="Product Review Neutral",
        description="Readable neutral polish for product reviews and desk demos.",
        tags=("effect", "review", "product", "demo"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.22, "denoise": 0.08, "vignette": 0.04, "vignette_feather": 0.88}},
    ),
    EditorPreset(
        id="effect-patch-note-readable",
        kind="effect",
        name="Patch Note Readable",
        description="Crisp UI capture preset for update notes and changelog screens.",
        tags=("effect", "patch-note", "ui", "screen", "tutorial"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.26, "denoise": 0.16, "vignette": 0.0}},
    ),
    EditorPreset(
        id="title-broll-context",
        kind="title",
        name="B-roll Context",
        description="Small upper label that explains a cutaway without stealing focus.",
        tags=("title", "b-roll", "cutaway", "editorial"),
        payload={"text": "CONTEXT", "duration_ms": 2400, "font_size": 30, "x_norm": 0.18, "y_norm": 0.16, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-podcast-topic",
        kind="title",
        name="Podcast Topic",
        description="Lower topic card for long-form dialogue chapters.",
        tags=("title", "podcast", "dialogue", "chapter"),
        payload={"text": "TOPIC", "duration_ms": 3600, "font_size": 38, "x_norm": 0.34, "y_norm": 0.76, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-review-verdict",
        kind="title",
        name="Review Verdict",
        description="Compact verdict tag for product pros, cons, and ratings.",
        tags=("title", "review", "product", "verdict"),
        payload={"text": "VERDICT", "duration_ms": 2200, "font_size": 46, "x_norm": 0.72, "y_norm": 0.2, "preset_id_in": "pop-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="title-patch-note",
        kind="title",
        name="Patch Note",
        description="Update-note title for version changes, fixes, and feature clips.",
        tags=("title", "patch-note", "update", "screen"),
        payload={"text": "PATCH NOTE", "duration_ms": 2300, "font_size": 42, "x_norm": 0.5, "y_norm": 0.18, "preset_id_in": "slide-up-in", "preset_id_out": "fade-out"},
    ),
    EditorPreset(
        id="audio-podcast-balanced",
        kind="audio",
        name="Podcast Balanced",
        description="Dialogue chain for long-form podcast/talking-head exports.",
        tags=("audio", "podcast", "dialogue", "voice", "loudness"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.62,
                "noise_reduction": 13.0,
                "highpass_hz": 80.0,
                "hum_remove": True,
                "presence_db": 2.8,
                "air_db": 1.1,
                "de_reverb": 0.18,
                "mouth_click": True,
                "plosive": True,
                "auto_level": True,
            },
            "deesser": {"enabled": True, "freq": 6600.0, "threshold": -32.0, "reduction": 48.0},
            "loudness": {"enabled": True, "target_i": -16.0, "true_peak": -1.2, "lra": 10.0, "target_id": "podcast_balanced"},
        },
    ),
    EditorPreset(
        id="audio-review-room-tone",
        kind="audio",
        name="Review Room Tone",
        description="Voice cleanup for desk reviews with mild room reflections.",
        tags=("audio", "review", "dialogue", "cleanup"),
        payload={
            "dialogue_cleanup": {
                "enabled": True,
                "strength": 0.58,
                "noise_reduction": 11.0,
                "highpass_hz": 92.0,
                "hum_remove": True,
                "presence_db": 2.5,
                "air_db": 0.9,
                "de_reverb": 0.22,
                "mouth_click": False,
                "plosive": True,
                "auto_level": True,
            },
            "loudness": {"enabled": True, "target_i": -15.0, "true_peak": -1.0, "lra": 9.0, "target_id": "review_room_tone"},
        },
    ),
    EditorPreset(
        id="caption-podcast-readable",
        kind="caption_style",
        name="Podcast Readable Caption",
        description="Long-form dialogue caption style with calmer motion.",
        tags=("caption", "podcast", "dialogue", "subtitle"),
        payload={"font_size": 34, "font_weight": 650, "fill": "#f7f7f3", "stroke": "#151515", "stroke_width": 4, "y_norm": 0.84, "animation": "fade-in"},
    ),
    EditorPreset(
        id="caption-review-procon",
        kind="caption_style",
        name="Review Pro/Con Caption",
        description="Compact caption style for product review pros and cons.",
        tags=("caption", "review", "product", "comparison"),
        payload={"font_size": 36, "font_weight": 800, "fill": "#ffffff", "stroke": "#1a1f2a", "stroke_width": 5, "y_norm": 0.79, "animation": "pop-in"},
    ),
    EditorPreset(
        id="sticker-pro-con-pill",
        kind="sticker",
        name="Pro/Con Pill",
        description="Small pros/cons label for product review moments.",
        tags=("sticker", "review", "product", "comparison"),
        payload={"shape": "pill", "text": "PRO", "duration_ms": 1600, "scale": 0.78, "color": "#27c46a", "x_norm": 0.18, "y_norm": 0.2},
    ),
    EditorPreset(
        id="sticker-broll-arrow",
        kind="sticker",
        name="B-roll Arrow",
        description="Subtle pointer sticker for cutaway details.",
        tags=("sticker", "b-roll", "cutaway", "callout"),
        payload={"shape": "arrow", "text": "", "duration_ms": 1400, "scale": 0.7, "color": "#f4b942", "x_norm": 0.68, "y_norm": 0.34},
    ),
    EditorPreset(
        id="motion-slow-kenburns",
        kind="motion",
        name="Slow Ken Burns",
        description="Gentle push for B-roll or still-image style inserts.",
        tags=("motion", "b-roll", "cutaway", "documentary"),
        payload={"type": "ken_burns", "scale_from": 1.0, "scale_to": 1.06, "duration_ms": 4200, "ease": "ease_in_out"},
    ),
    EditorPreset(
        id="motion-review-compare-slide",
        kind="motion",
        name="Review Compare Slide",
        description="Simple side-by-side movement for comparisons.",
        tags=("motion", "review", "comparison", "product"),
        payload={"type": "slide_compare", "from_x": -0.08, "to_x": 0.0, "duration_ms": 900, "ease": "ease_out"},
    ),
    EditorPreset(
        id="template-broll-story-insert",
        kind="template",
        name="B-roll Story Insert",
        description="Soft detail, context label, arrow callout, and gentle push for cutaways.",
        tags=("template", "b-roll", "cutaway", "documentary", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-broll-soft-detail"},
                {"kind": "title", "preset_id": "title-broll-context", "at_ms": 0},
                {"kind": "sticker", "preset_id": "sticker-broll-arrow", "at_ms": 500},
                {"kind": "motion", "preset_id": "motion-slow-kenburns"},
                {"kind": "transition", "preset_id": "transition-broll-wipe-lite"},
            ]
        },
    ),
    EditorPreset(
        id="template-podcast-chapter",
        kind="template",
        name="Podcast Chapter",
        description="Talking-head cleanup, topic card, readable captions, and podcast loudness.",
        tags=("template", "podcast", "dialogue", "chapter", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-podcast-face-clean"},
                {"kind": "audio", "preset_id": "audio-podcast-balanced"},
                {"kind": "title", "preset_id": "title-podcast-topic", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-podcast-readable"},
                {"kind": "transition", "preset_id": "transition-podcast-chapter"},
            ]
        },
    ),
    EditorPreset(
        id="template-product-review-verdict",
        kind="template",
        name="Product Review Verdict",
        description="Neutral review polish, verdict tag, pro/con badge, and room-tone voice chain.",
        tags=("template", "review", "product", "comparison", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-product-review-neutral"},
                {"kind": "audio", "preset_id": "audio-review-room-tone"},
                {"kind": "title", "preset_id": "title-review-verdict", "at_ms": 0},
                {"kind": "sticker", "preset_id": "sticker-pro-con-pill", "at_ms": 450},
                {"kind": "caption_style", "preset_id": "caption-review-procon"},
                {"kind": "transition", "preset_id": "transition-review-split"},
            ]
        },
    ),
    EditorPreset(
        id="template-patch-note-update",
        kind="template",
        name="Patch Note Update",
        description="Readable UI capture, update title, hotkey caption, and mobile-safe transition.",
        tags=("template", "patch-note", "update", "screen", "tutorial", "one-click"),
        payload={
            "sequence": [
                {"kind": "effect", "preset_id": "effect-patch-note-readable"},
                {"kind": "title", "preset_id": "title-patch-note", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-hotkey-small"},
                {"kind": "transition", "preset_id": "transition-mobile-slide-lite"},
            ]
        },
    ),
)


SCREEN_STUDIO_STYLE_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-cursor-pop-cut",
        kind="transition",
        name="Cursor Pop Cut",
        description="Fast playful cut with a bright UI-pop feel.",
        tags=("screen-studio", "cursor", "short-form", "tutorial"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 140},
    ),
    EditorPreset(
        id="transition-wallpaper-swipe",
        kind="transition",
        name="Wallpaper Swipe",
        description="Soft gradient-style swipe for template scene changes.",
        tags=("screen-studio", "wallpaper", "gradient", "template"),
        payload={"transition_out_type": "slide_left", "transition_out_ms": 420},
    ),
    EditorPreset(
        id="transition-bouncy-ui-card",
        kind="transition",
        name="Bouncy UI Card",
        description="Rounded-card style beat transition for app walkthroughs.",
        tags=("screen-studio", "ui", "card", "short-form"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 220},
    ),
    EditorPreset(
        id="transition-soft-purple-dip",
        kind="transition",
        name="Soft Purple Dip",
        description="Polished purple dip for creator templates.",
        tags=("screen-studio", "purple", "creator"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 260},
    ),
    EditorPreset(
        id="transition-quick-zoom-snap",
        kind="transition",
        name="Quick Zoom Snap",
        description="Short energetic zoom-snap bridge for shorts.",
        tags=("capcut", "short-form", "zoom", "social"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 120},
    ),
    EditorPreset(
        id="effect-screenstudio-clean-glow",
        kind="effect",
        name="Clean UI Glow",
        description="Slight detail, vignette, and soft creator-app contrast.",
        tags=("screen-studio", "tutorial", "ui", "clean"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.16, "vignette": 0.08, "vignette_feather": 0.92}},
    ),
    EditorPreset(
        id="effect-wallpaper-gradient-pop",
        kind="effect",
        name="Wallpaper Gradient Pop",
        description="Preview-oriented palette preset for wallpaper/template looks.",
        tags=("screen-studio", "wallpaper", "gradient", "template"),
        payload={
            "video_filters": {"enabled": True, "sharpen": 0.08, "vignette": 0.06, "chroma_aberration": 0.012},
            "background_palette": ["#FF7A59", "#7F6BFF", "#67D8FF", "#FFD36A"],
        },
    ),
    EditorPreset(
        id="effect-caption-safe-soft",
        kind="effect",
        name="Caption Safe Soft",
        description="Softens busy screen recordings behind big captions.",
        tags=("caption", "short-form", "tutorial", "screen-studio"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.04, "vignette": 0.16, "vignette_feather": 0.85}},
    ),
    EditorPreset(
        id="title-cursor-demo-step",
        kind="title",
        name="Cursor Demo Step",
        description="Compact step label styled for screen recordings.",
        tags=("screen-studio", "tutorial", "cursor", "step"),
        payload={"text": "STEP 1", "duration_ms": 2200, "font_size": 44, "color": "#FFFFFF", "bg_color": "#7F6BFF", "x_norm": 0.23, "y_norm": 0.18},
    ),
    EditorPreset(
        id="title-wallpaper-heading",
        kind="title",
        name="Wallpaper Heading",
        description="Large centered heading for gradient-backed templates.",
        tags=("screen-studio", "wallpaper", "gradient", "short-form"),
        payload={"text": "MAKE IT POP", "duration_ms": 2400, "font_size": 58, "color": "#FFFFFF", "bg_color": "#FF6A35", "x_norm": 0.5, "y_norm": 0.23},
    ),
    EditorPreset(
        id="title-short-hook-pill",
        kind="title",
        name="Short Hook Pill",
        description="Rounded hook caption for the first second of shorts.",
        tags=("short-form", "hook", "capcut", "caption"),
        payload={"text": "WAIT FOR IT", "duration_ms": 1600, "font_size": 48, "color": "#FFFFFF", "bg_color": "#151827", "x_norm": 0.5, "y_norm": 0.16},
    ),
    EditorPreset(
        id="title-feature-callout-bubble",
        kind="title",
        name="Feature Callout Bubble",
        description="Friendly floating callout for app/product walkthroughs.",
        tags=("screen-studio", "product", "tutorial", "callout"),
        payload={"text": "New feature", "duration_ms": 2200, "font_size": 40, "color": "#101320", "bg_color": "#FFD36A", "x_norm": 0.68, "y_norm": 0.32},
    ),
    EditorPreset(
        id="title-final-cta-glass",
        kind="title",
        name="Final CTA Glass",
        description="Clean final call-to-action in a glassy lower pill.",
        tags=("short-form", "cta", "creator", "screen-studio"),
        payload={"text": "Try this next", "duration_ms": 2600, "font_size": 42, "color": "#FFFFFF", "bg_color": "#252A3C", "x_norm": 0.5, "y_norm": 0.78},
    ),
    EditorPreset(
        id="caption-screenstudio-soft",
        kind="caption_style",
        name="ScreenStudio Soft Caption",
        description="Soft high-contrast caption that fits clean UI demos.",
        tags=("screen-studio", "caption", "tutorial", "short-form"),
        payload={"font_size": 42, "fill": "#FFFFFF", "stroke": "#111320", "stroke_width": 3, "x_norm": 0.5, "y_norm": 0.82, "duration_ms": 1800},
    ),
    EditorPreset(
        id="caption-hook-gradient",
        kind="caption_style",
        name="Hook Gradient Caption",
        description="Bold creator caption for CapCut-style hooks.",
        tags=("capcut", "caption", "short-form", "hook"),
        payload={"font_size": 48, "fill": "#FFFFFF", "stroke": "#7F6BFF", "stroke_width": 4, "x_norm": 0.5, "y_norm": 0.78, "duration_ms": 1500},
    ),
    EditorPreset(
        id="caption-minimal-keynote",
        kind="caption_style",
        name="Minimal Keynote Caption",
        description="Small clean caption for product/tutorial overlays.",
        tags=("product", "tutorial", "caption", "minimal"),
        payload={"font_size": 34, "fill": "#F5F7FF", "stroke": "#111320", "stroke_width": 2, "x_norm": 0.5, "y_norm": 0.86, "duration_ms": 2100},
    ),
    EditorPreset(
        id="sticker-cursor-spark",
        kind="sticker",
        name="Cursor Spark",
        description="Small animated-feeling cursor spark sticker.",
        tags=("screen-studio", "cursor", "spark", "tutorial"),
        payload={"shape": "badge", "text": "*", "duration_ms": 900, "color": "#FFD36A", "x_norm": 0.58, "y_norm": 0.42, "scale": 0.9, "animation": "pop-in"},
    ),
    EditorPreset(
        id="sticker-drag-drop-chip",
        kind="sticker",
        name="Drag Drop Chip",
        description="Visual chip for drag-and-drop moments.",
        tags=("screen-studio", "drag", "tutorial", "ui"),
        payload={"shape": "bubble", "text": "DROP", "duration_ms": 1200, "color": "#67D8FF", "x_norm": 0.38, "y_norm": 0.36, "scale": 0.86, "animation": "pop-in"},
    ),
    EditorPreset(
        id="sticker-template-confetti",
        kind="sticker",
        name="Template Confetti",
        description="Celebratory badge for template reveals.",
        tags=("capcut", "template", "creator", "short-form"),
        payload={"shape": "burst", "text": "WOW", "duration_ms": 1000, "color": "#FF7A59", "x_norm": 0.76, "y_norm": 0.24, "scale": 0.9, "animation": "pop-in"},
    ),
    EditorPreset(
        id="sticker-glass-arrow",
        kind="sticker",
        name="Glass Arrow",
        description="Clean arrow callout for UI/product shots.",
        tags=("screen-studio", "callout", "product", "tutorial"),
        payload={"shape": "arrow", "text": "LOOK", "duration_ms": 1300, "color": "#8A7CFF", "x_norm": 0.64, "y_norm": 0.44, "scale": 0.84, "animation": "pop-in"},
    ),
    EditorPreset(
        id="motion-cursor-follow-pop",
        kind="motion",
        name="Cursor Follow Pop",
        description="Short punch-in motion for cursor-driven moments.",
        tags=("screen-studio", "cursor", "zoom", "tutorial"),
        payload={"duration_ms": 1050, "scale": 1.16, "x_norm": 0.54, "y_norm": 0.42},
    ),
    EditorPreset(
        id="motion-wallpaper-float",
        kind="motion",
        name="Wallpaper Float",
        description="Subtle floating motion for background/wallpaper scenes.",
        tags=("screen-studio", "wallpaper", "gradient", "template"),
        payload={"duration_ms": 2600, "scale": 1.06, "x_norm": 0.5, "y_norm": 0.5},
    ),
    EditorPreset(
        id="motion-hook-bounce-in",
        kind="motion",
        name="Hook Bounce In",
        description="Fast bounce-in punch for short-form intros.",
        tags=("capcut", "short-form", "hook", "motion"),
        payload={"duration_ms": 900, "scale": 1.2, "x_norm": 0.5, "y_norm": 0.5},
    ),
    EditorPreset(
        id="color-screen-recorder-clean",
        kind="color",
        name="Screen Recorder Clean",
        description="Neutral UI recording grade with mild contrast.",
        tags=("screen-studio", "tutorial", "ui", "rec709"),
        payload={"color_grade": {"exposure": 2, "contrast": 8, "saturation": 2}, "color_workflow": {"scope": "waveform", "intent": "ui-clean"}},
    ),
    EditorPreset(
        id="template-screenstudio-cursor-demo",
        kind="template",
        name="ScreenStudio Cursor Demo",
        description="Cursor-focused tutorial template with title, sticker, motion, and pop cut.",
        tags=("screen-studio", "tutorial", "cursor", "short-form"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-screenstudio-clean-glow", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-cursor-demo-step", "at_ms": 0},
            {"kind": "sticker", "preset_id": "sticker-cursor-spark", "at_ms": 420},
            {"kind": "motion", "preset_id": "motion-cursor-follow-pop", "at_ms": 500},
            {"kind": "transition", "preset_id": "transition-cursor-pop-cut"},
        ]},
    ),
    EditorPreset(
        id="template-wallpaper-palette-hook",
        kind="template",
        name="Wallpaper Palette Hook",
        description="Gradient/wallpaper opening template for creator videos.",
        tags=("screen-studio", "wallpaper", "gradient", "short-form"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-wallpaper-gradient-pop", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-wallpaper-heading", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-hook-gradient", "at_ms": 300},
            {"kind": "motion", "preset_id": "motion-wallpaper-float", "at_ms": 0},
            {"kind": "transition", "preset_id": "transition-wallpaper-swipe"},
        ]},
    ),
    EditorPreset(
        id="template-capcut-hook-stack",
        kind="template",
        name="CapCut Hook Stack",
        description="Hook title, caption, confetti, bounce, and fast transition for shorts.",
        tags=("capcut", "short-form", "hook", "social"),
        payload={"sequence": [
            {"kind": "title", "preset_id": "title-short-hook-pill", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-hook-gradient", "at_ms": 180},
            {"kind": "sticker", "preset_id": "sticker-template-confetti", "at_ms": 520},
            {"kind": "motion", "preset_id": "motion-hook-bounce-in", "at_ms": 0},
            {"kind": "transition", "preset_id": "transition-quick-zoom-snap"},
        ]},
    ),
    EditorPreset(
        id="template-product-ui-callout",
        kind="template",
        name="Product UI Callout",
        description="Product/tutorial template with glass arrow and feature bubble.",
        tags=("screen-studio", "product", "tutorial", "callout"),
        payload={"sequence": [
            {"kind": "color", "preset_id": "color-screen-recorder-clean", "at_ms": 0, "target": "color"},
            {"kind": "title", "preset_id": "title-feature-callout-bubble", "at_ms": 300},
            {"kind": "sticker", "preset_id": "sticker-glass-arrow", "at_ms": 500},
            {"kind": "caption_style", "preset_id": "caption-minimal-keynote", "at_ms": 900},
            {"kind": "transition", "preset_id": "transition-bouncy-ui-card"},
        ]},
    ),
)


SCREEN_STUDIO_MICRO_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-cursor-spotlight-wipe",
        kind="transition",
        name="Cursor Spotlight Wipe",
        description="Cursor-centered wipe for focused UI walkthrough cuts.",
        tags=("screen-studio", "cursor", "transition", "tutorial"),
        payload={"transition_out_type": "iris", "transition_out_ms": 360},
    ),
    EditorPreset(
        id="transition-glass-panel-push",
        kind="transition",
        name="Glass Panel Push",
        description="Soft glass-panel push for modern app demos.",
        tags=("screen-studio", "glass", "product", "transition"),
        payload={"transition_out_type": "slide_left", "transition_out_ms": 300},
    ),
    EditorPreset(
        id="effect-wallpaper-aurora",
        kind="effect",
        name="Wallpaper Aurora",
        description="Bright aurora palette for wallpaper-style intro cards.",
        tags=("screen-studio", "wallpaper", "gradient", "background"),
        payload={"background_palette": ["#FF8C5A", "#7A67FF", "#58D5FF", "#FFE076"], "video_filters": {"enabled": True, "vignette": 0.05}},
    ),
    EditorPreset(
        id="effect-clean-ui-depth",
        kind="effect",
        name="Clean UI Depth",
        description="Subtle depth and clarity for screen recordings.",
        tags=("screen-studio", "ui", "clean", "tutorial"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.12, "vignette": 0.04, "chroma_aberration": 0.006}},
    ),
    EditorPreset(
        id="title-key-moment-chip",
        kind="title",
        name="Key Moment Chip",
        description="Small bright chip for important cursor moments.",
        tags=("screen-studio", "cursor", "title", "tutorial"),
        payload={"text": "KEY MOMENT", "duration_ms": 1500, "font_size": 34, "color": "#101320", "bg_color": "#FFD36A", "x_norm": 0.5, "y_norm": 0.18},
    ),
    EditorPreset(
        id="caption-ui-demo-soft-glass",
        kind="caption_style",
        name="UI Demo Soft Glass",
        description="Glass-caption style for screen recordings.",
        tags=("screen-studio", "caption", "glass", "tutorial"),
        payload={"font_size": 38, "fill": "#FFFFFF", "stroke": "#101320", "stroke_width": 2, "x_norm": 0.5, "y_norm": 0.84, "duration_ms": 2100},
    ),
    EditorPreset(
        id="sticker-click-ring",
        kind="sticker",
        name="Click Ring",
        description="Click ring sticker for cursor emphasis.",
        tags=("screen-studio", "cursor", "click", "sticker"),
        payload={"shape": "ring", "text": "", "duration_ms": 700, "color": "#8A7CFF", "x_norm": 0.5, "y_norm": 0.5, "scale": 0.82, "animation": "pulse"},
    ),
    EditorPreset(
        id="sticker-hotkey-pair",
        kind="sticker",
        name="Hotkey Pair",
        description="Two-key hotkey badge for tutorials.",
        tags=("screen-studio", "hotkey", "tutorial", "sticker"),
        payload={"shape": "keycap", "text": "Ctrl K", "duration_ms": 1300, "color": "#252A3C", "x_norm": 0.5, "y_norm": 0.72, "scale": 0.92, "animation": "pop-in"},
    ),
    EditorPreset(
        id="motion-ui-focus-drift",
        kind="motion",
        name="UI Focus Drift",
        description="Subtle focus drift for polished screen demos.",
        tags=("screen-studio", "ui", "motion", "tutorial"),
        payload={"duration_ms": 1800, "scale": 1.08, "x_norm": 0.53, "y_norm": 0.45},
    ),
    EditorPreset(
        id="template-screenstudio-hotkey-demo",
        kind="template",
        name="ScreenStudio Hotkey Demo",
        description="Hotkey-focused tutorial template with keycap, title, and clean UI depth.",
        tags=("screen-studio", "hotkey", "tutorial", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-key-moment-chip", "at_ms": 0},
            {"kind": "sticker", "preset_id": "sticker-hotkey-pair", "at_ms": 320},
            {"kind": "motion", "preset_id": "motion-ui-focus-drift", "at_ms": 0},
            {"kind": "transition", "preset_id": "transition-glass-panel-push"},
        ]},
    ),
    EditorPreset(
        id="template-cursor-click-highlight",
        kind="template",
        name="Cursor Click Highlight",
        description="Cursor click emphasis pack with ring sticker and spotlight wipe.",
        tags=("screen-studio", "cursor", "click", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-screenstudio-clean-glow", "at_ms": 0, "target": "selected_clip"},
            {"kind": "sticker", "preset_id": "sticker-click-ring", "at_ms": 380},
            {"kind": "caption_style", "preset_id": "caption-ui-demo-soft-glass", "at_ms": 500},
            {"kind": "transition", "preset_id": "transition-cursor-spotlight-wipe"},
        ]},
    ),
)


SCREEN_STUDIO_TEMPLATE_PACK_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="template-cursor-tutorial-chapter",
        kind="template",
        name="Cursor Tutorial Chapter",
        description="Clean chapter opener for cursor-driven lessons.",
        tags=("screen-studio", "cursor", "tutorial", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-cursor-demo-step", "at_ms": 0},
            {"kind": "sticker", "preset_id": "sticker-click-ring", "at_ms": 500},
            {"kind": "caption_style", "preset_id": "caption-ui-demo-soft-glass", "at_ms": 700},
        ]},
    ),
    EditorPreset(
        id="template-product-launch-clean",
        kind="template",
        name="Product Launch Clean",
        description="Product-demo opener with feature bubble and glass arrow.",
        tags=("screen-studio", "product", "launch", "template"),
        payload={"sequence": [
            {"kind": "color", "preset_id": "color-screen-recorder-clean", "at_ms": 0, "target": "color"},
            {"kind": "title", "preset_id": "title-feature-callout-bubble", "at_ms": 120},
            {"kind": "sticker", "preset_id": "sticker-glass-arrow", "at_ms": 440},
            {"kind": "transition", "preset_id": "transition-glass-panel-push"},
        ]},
    ),
    EditorPreset(
        id="template-shorts-hook-caption-burst",
        kind="template",
        name="Shorts Hook Caption Burst",
        description="Fast hook stack for short-form videos.",
        tags=("capcut", "short-form", "hook", "template"),
        payload={"sequence": [
            {"kind": "title", "preset_id": "title-short-hook-pill", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-hook-gradient", "at_ms": 160},
            {"kind": "sticker", "preset_id": "sticker-template-confetti", "at_ms": 520},
            {"kind": "transition", "preset_id": "transition-quick-zoom-snap"},
        ]},
    ),
    EditorPreset(
        id="template-gaming-highlight-screen",
        kind="template",
        name="Gaming Highlight Screen",
        description="Creator/gameplay highlight with impact and score callout.",
        tags=("gameplay", "gaming", "highlight", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-punchy-gameplay", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-score-callout", "at_ms": 180},
            {"kind": "motion", "preset_id": "motion-shake-impact", "at_ms": 580},
            {"kind": "transition", "preset_id": "transition-hit-white"},
        ]},
    ),
    EditorPreset(
        id="template-corporate-clean-demo",
        kind="template",
        name="Corporate Clean Demo",
        description="Quiet professional screen-demo template.",
        tags=("corporate", "clean", "product", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "caption_style", "preset_id": "caption-minimal-keynote", "at_ms": 300},
            {"kind": "title", "preset_id": "title-final-cta-glass", "at_ms": 1800},
        ]},
    ),
)


SCREEN_STUDIO_DELIVERY_TEMPLATE_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="template-screenstudio-record-edit-export",
        kind="template",
        name="Record Edit Export",
        description="One-click Screen Studio style flow for clean recording, cursor focus, and export-ready handoff.",
        tags=("screen-studio", "tutorial", "cursor", "export", "template", "one-click"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-key-moment-chip", "at_ms": 160},
            {"kind": "sticker", "preset_id": "sticker-click-ring", "at_ms": 520},
            {"kind": "motion", "preset_id": "motion-ui-focus-drift", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-ui-demo-soft-glass", "at_ms": 760},
            {"kind": "transition", "preset_id": "transition-cursor-spotlight-wipe"},
        ]},
    ),
    EditorPreset(
        id="template-screenstudio-click-to-cut",
        kind="template",
        name="Click To Cut",
        description="Blade/editing explainer template with animated scissor cue and compact tooltip.",
        tags=("screen-studio", "timeline", "scissors", "tutorial", "template", "one-click"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-screenstudio-clean-glow", "at_ms": 0, "target": "selected_clip"},
            {"kind": "sticker", "preset_id": "sticker-cursor-scissor-snip", "at_ms": 320},
            {"kind": "title", "preset_id": "title-floating-tooltip-chip", "at_ms": 360},
            {"kind": "motion", "preset_id": "motion-scissor-cut-pop", "at_ms": 320},
            {"kind": "transition", "preset_id": "transition-cursor-pop-cut"},
        ]},
    ),
    EditorPreset(
        id="template-screenstudio-wallpaper-demo",
        kind="template",
        name="Wallpaper Demo",
        description="Bright wallpaper-palette opener for app walkthroughs and tutorial chapters.",
        tags=("screen-studio", "wallpaper", "gradient", "tutorial", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-wallpaper-aurora", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-wallpaper-heading", "at_ms": 0},
            {"kind": "motion", "preset_id": "motion-wallpaper-float", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-hook-gradient", "at_ms": 420},
            {"kind": "transition", "preset_id": "transition-wallpaper-swipe"},
        ]},
    ),
    EditorPreset(
        id="template-screenstudio-product-walkthrough",
        kind="template",
        name="Product Walkthrough",
        description="Polished product demo template with clean grade, feature bubble, and callout arrow.",
        tags=("screen-studio", "product", "demo", "walkthrough", "template", "one-click"),
        payload={"sequence": [
            {"kind": "color", "preset_id": "color-screen-recorder-clean", "at_ms": 0, "target": "color"},
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-feature-callout-bubble", "at_ms": 260},
            {"kind": "sticker", "preset_id": "sticker-glass-arrow", "at_ms": 560},
            {"kind": "caption_style", "preset_id": "caption-minimal-keynote", "at_ms": 920},
            {"kind": "transition", "preset_id": "transition-glass-panel-push"},
        ]},
    ),
    EditorPreset(
        id="template-screenstudio-short-export",
        kind="template",
        name="Short Export",
        description="Vertical-friendly hook template for quick share-ready exports.",
        tags=("screen-studio", "short-form", "vertical", "export", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-wallpaper-mint-orchid", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-short-hook-pill", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-hook-gradient", "at_ms": 180},
            {"kind": "sticker", "preset_id": "sticker-template-confetti", "at_ms": 540},
            {"kind": "transition", "preset_id": "transition-quick-zoom-snap"},
        ]},
    ),
)


SCREEN_STUDIO_ANIMATED_ICON_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="sticker-cursor-scissor-snip",
        kind="sticker",
        name="Cursor Scissor Snip",
        description="Animated-feeling scissor cue for blade cuts.",
        tags=("screen-studio", "cursor", "scissors", "timeline", "animated-icon"),
        payload={"shape": "scissors", "text": "", "duration_ms": 760, "color": "#FF744D", "x_norm": 0.54, "y_norm": 0.46, "scale": 0.92, "animation": "snip-pop"},
    ),
    EditorPreset(
        id="sticker-cursor-zoom-bloom",
        kind="sticker",
        name="Cursor Zoom Bloom",
        description="Blooming magnifier icon for zoom emphasis.",
        tags=("screen-studio", "cursor", "zoom", "animated-icon"),
        payload={"shape": "magnifier", "text": "", "duration_ms": 820, "color": "#7D6BFF", "x_norm": 0.5, "y_norm": 0.5, "scale": 0.86, "animation": "pulse"},
    ),
    EditorPreset(
        id="sticker-drag-handle-glide",
        kind="sticker",
        name="Drag Handle Glide",
        description="Small moving handle cue for drag-and-drop tutorials.",
        tags=("screen-studio", "drag", "cursor", "animated-icon"),
        payload={"shape": "handle", "text": "", "duration_ms": 980, "color": "#65D8FF", "x_norm": 0.46, "y_norm": 0.5, "scale": 0.8, "animation": "slide-pop"},
    ),
    EditorPreset(
        id="effect-wallpaper-sunset-pop",
        kind="effect",
        name="Wallpaper Sunset Pop",
        description="Warm Screen Studio-style wallpaper palette.",
        tags=("screen-studio", "wallpaper", "gradient", "palette"),
        payload={"background_palette": ["#FF6B4A", "#FFB25F", "#776BFF", "#4CD9F5"], "video_filters": {"enabled": True, "vignette": 0.04, "sharpen": 0.06}},
    ),
    EditorPreset(
        id="effect-wallpaper-mint-orchid",
        kind="effect",
        name="Wallpaper Mint Orchid",
        description="Fresh mint/orchid palette for soft app demos.",
        tags=("screen-studio", "wallpaper", "gradient", "palette"),
        payload={"background_palette": ["#57E3C3", "#70B7FF", "#B271FF", "#FFE07A"], "video_filters": {"enabled": True, "vignette": 0.05, "sharpen": 0.04}},
    ),
    EditorPreset(
        id="title-floating-tooltip-chip",
        kind="title",
        name="Floating Tooltip Chip",
        description="Compact tooltip label that pairs with icon-only controls.",
        tags=("screen-studio", "tooltip", "ui", "cursor"),
        payload={"text": "Click here", "duration_ms": 1300, "font_size": 32, "color": "#FFFFFF", "bg_color": "#23283A", "x_norm": 0.57, "y_norm": 0.36},
    ),
    EditorPreset(
        id="motion-scissor-cut-pop",
        kind="motion",
        name="Scissor Cut Pop",
        description="Short pop movement for blade/scissor moments.",
        tags=("screen-studio", "scissors", "timeline", "motion"),
        payload={"duration_ms": 760, "scale": 1.18, "x_norm": 0.54, "y_norm": 0.46},
    ),
    EditorPreset(
        id="motion-drag-snap-land",
        kind="motion",
        name="Drag Snap Land",
        description="Snap-to-position motion for drag/drop explanations.",
        tags=("screen-studio", "drag", "timeline", "motion"),
        payload={"duration_ms": 920, "scale": 1.1, "x_norm": 0.48, "y_norm": 0.5},
    ),
    EditorPreset(
        id="template-screenstudio-blade-explain",
        kind="template",
        name="ScreenStudio Blade Explain",
        description="Timeline blade explanation template with scissor cue and tooltip.",
        tags=("screen-studio", "timeline", "scissors", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "sticker", "preset_id": "sticker-cursor-scissor-snip", "at_ms": 360},
            {"kind": "title", "preset_id": "title-floating-tooltip-chip", "at_ms": 420},
            {"kind": "motion", "preset_id": "motion-scissor-cut-pop", "at_ms": 360},
            {"kind": "transition", "preset_id": "transition-cursor-pop-cut"},
        ]},
    ),
    EditorPreset(
        id="template-wallpaper-palette-switch",
        kind="template",
        name="Wallpaper Palette Switch",
        description="Palette-switching intro template for Screen Studio-like backgrounds.",
        tags=("screen-studio", "wallpaper", "palette", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-wallpaper-sunset-pop", "at_ms": 0, "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-wallpaper-heading", "at_ms": 0},
            {"kind": "motion", "preset_id": "motion-wallpaper-float", "at_ms": 0},
            {"kind": "transition", "preset_id": "transition-wallpaper-swipe"},
        ]},
    ),
)


SCREEN_STUDIO_QUICK_RESULT_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="effect-screenstudio-default-polish",
        kind="effect",
        name="ScreenStudio Default Polish",
        description="Default clean screen-recording look: readable UI, light depth, no heavy grading.",
        tags=("screen-studio", "default", "screen-recording", "quick-result"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.18, "denoise": 0.10, "vignette": 0.06, "vignette_feather": 0.86}},
    ),
    EditorPreset(
        id="transition-cursor-settle-pop",
        kind="transition",
        name="Cursor Settle Pop",
        description="Tiny click-settle transition for interface tutorials.",
        tags=("screen-studio", "cursor", "click", "tutorial", "quick-result"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 85},
    ),
    EditorPreset(
        id="title-screenstudio-step-chip",
        kind="title",
        name="ScreenStudio Step Chip",
        description="Compact rounded step label for tutorial chapters.",
        tags=("screen-studio", "tutorial", "step", "chip", "quick-result"),
        payload={"text": "Step 1", "duration_ms": 1800, "font_size": 34, "x_norm": 0.18, "y_norm": 0.16, "preset_id_in": "pop-in", "preset_id_out": "fade-out", "bg_color": "#282F45", "color": "#FFFFFF"},
    ),
    EditorPreset(
        id="sticker-cursor-click-ripple",
        kind="sticker",
        name="Cursor Click Ripple",
        description="Soft ripple cue for visible click feedback in screen recordings.",
        tags=("screen-studio", "cursor", "click", "animated-icon", "quick-result"),
        payload={"shape": "ripple", "text": "", "duration_ms": 620, "scale": 0.88, "color": "#7A68FF", "x_norm": 0.52, "y_norm": 0.48, "animation": "click-ripple"},
    ),
    EditorPreset(
        id="motion-auto-zoom-ease-soft",
        kind="motion",
        name="Auto Zoom Ease Soft",
        description="Gentle zoom push that reads like Screen Studio's default motion.",
        tags=("screen-studio", "auto-zoom", "motion", "quick-result"),
        payload={"keyframes": [{"t": 0.0, "scale": 1.0, "x": 0.5, "y": 0.5}, {"t": 1.0, "scale": 1.085, "x": 0.51, "y": 0.48}], "easing": "easeOutCubic", "duration_ms": 1100},
    ),
    EditorPreset(
        id="template-screenstudio-quick-tutorial",
        kind="template",
        name="ScreenStudio Quick Tutorial",
        description="One-click tutorial polish: readable screen, step chip, click ripple, soft auto-zoom.",
        tags=("screen-studio", "tutorial", "quick-result", "template", "one-click"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-screenstudio-default-polish", "target": "selected_clip"},
            {"kind": "title", "preset_id": "title-screenstudio-step-chip", "at_ms": 0},
            {"kind": "sticker", "preset_id": "sticker-cursor-click-ripple", "at_ms": 420},
            {"kind": "motion", "preset_id": "motion-auto-zoom-ease-soft", "at_ms": 0},
            {"kind": "transition", "preset_id": "transition-cursor-settle-pop"},
        ]},
    ),
    EditorPreset(
        id="template-product-demo-quick-result",
        kind="template",
        name="Product Demo Quick Result",
        description="Fast app/product demo polish with clean default look, product push, and a new badge.",
        tags=("screen-studio", "product", "demo", "quick-result", "template"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-screenstudio-default-polish", "target": "selected_clip"},
            {"kind": "motion", "preset_id": "motion-product-push"},
            {"kind": "sticker", "preset_id": "sticker-new-badge", "at_ms": 560},
            {"kind": "title", "preset_id": "title-floating-tooltip-chip", "at_ms": 700},
            {"kind": "transition", "preset_id": "transition-product-card-swipe"},
        ]},
    ),
    EditorPreset(
        id="template-shorts-click-highlight",
        kind="template",
        name="Shorts Click Highlight",
        description="Short-form click highlight pack with caption style, ripple, and fast transition.",
        tags=("capcut", "screen-studio", "shorts", "click", "template", "quick-result"),
        payload={"sequence": [
            {"kind": "effect", "preset_id": "effect-readable-screen-text", "target": "selected_clip"},
            {"kind": "caption_style", "preset_id": "caption-capcut-word-pop"},
            {"kind": "sticker", "preset_id": "sticker-cursor-click-ripple", "at_ms": 240},
            {"kind": "transition", "preset_id": "transition-shortform-white-hit"},
        ]},
    ),
)


CREATOR_EFFECT_TRANSITION_EXPANSION_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="transition-cursor-click-flash",
        kind="transition",
        name="Cursor Click Flash",
        description="Very short white flash for click emphasis and cursor tutorials.",
        tags=("screen-studio", "cursor", "click", "tutorial"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 110},
    ),
    EditorPreset(
        id="transition-ui-panel-slide",
        kind="transition",
        name="UI Panel Slide",
        description="Clean panel slide for moving between app screens.",
        tags=("screen-studio", "ui", "panel", "tutorial"),
        payload={"transition_out_type": "slide_left", "transition_out_ms": 320},
    ),
    EditorPreset(
        id="transition-soft-zoom-bridge",
        kind="transition",
        name="Soft Zoom Bridge",
        description="Soft zoom-in bridge for demo steps and product reveals.",
        tags=("screen-studio", "zoom", "tutorial", "product"),
        payload={"transition_out_type": "zoom_in", "transition_out_ms": 360},
    ),
    EditorPreset(
        id="transition-reverse-zoom-out",
        kind="transition",
        name="Reverse Zoom Out",
        description="Zoom-out transition for ending a focused callout.",
        tags=("screen-studio", "zoom", "outro", "product"),
        payload={"transition_out_type": "zoom_out", "transition_out_ms": 420},
    ),
    EditorPreset(
        id="transition-clean-wipe-left",
        kind="transition",
        name="Clean Wipe Left",
        description="Simple left wipe for tutorial chapter changes.",
        tags=("clean", "wipe", "product", "tutorial"),
        payload={"transition_out_type": "wipe_left", "transition_out_ms": 360},
    ),
    EditorPreset(
        id="transition-shortform-white-hit",
        kind="transition",
        name="Shortform White Hit",
        description="Fast flash hit for beat edits and shorts.",
        tags=("capcut", "short-form", "beat", "flash"),
        payload={"transition_out_type": "fade_white", "transition_out_ms": 95},
    ),
    EditorPreset(
        id="transition-chapter-soft-black",
        kind="transition",
        name="Chapter Soft Black",
        description="Soft black chapter fade for longer tutorial sections.",
        tags=("chapter", "course", "tutorial", "fade"),
        payload={"transition_out_type": "fade_black", "transition_out_ms": 520},
    ),
    EditorPreset(
        id="transition-demo-step-dissolve",
        kind="transition",
        name="Demo Step Dissolve",
        description="Short dissolve for understated screen-recording steps.",
        tags=("tutorial", "step", "screen-recording", "clean"),
        payload={"transition_out_type": "dissolve", "transition_out_ms": 260},
    ),
    EditorPreset(
        id="transition-product-card-swipe",
        kind="transition",
        name="Product Card Swipe",
        description="Card-like slide for product feature panels.",
        tags=("product", "card", "screen-studio", "template"),
        payload={"transition_out_type": "slide_left", "transition_out_ms": 460},
    ),
    EditorPreset(
        id="transition-stream-beat-wipe",
        kind="transition",
        name="Stream Beat Wipe",
        description="Quick wipe for stream and gameplay beat cuts.",
        tags=("stream", "gameplay", "beat", "wipe"),
        payload={"transition_out_type": "wipe_left", "transition_out_ms": 180},
    ),
    EditorPreset(
        id="effect-readable-screen-text",
        kind="effect",
        name="Readable Screen Text",
        description="Sharpened, lightly cleaned screen recording preset for small UI text.",
        tags=("screen-recording", "text", "tutorial", "utility"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.28, "denoise": 0.08, "vignette": 0.04, "vignette_feather": 0.9}},
    ),
    EditorPreset(
        id="effect-cursor-focus-vignette",
        kind="effect",
        name="Cursor Focus Vignette",
        description="Gentle focus vignette for cursor-led explanations.",
        tags=("cursor", "focus", "tutorial", "screen-studio"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.16, "vignette": 0.22, "vignette_feather": 0.78}},
    ),
    EditorPreset(
        id="effect-soft-webcam-clean",
        kind="effect",
        name="Soft Webcam Clean",
        description="Soft cleanup preset for webcam or facecam inserts.",
        tags=("webcam", "portrait", "creator", "cleanup"),
        payload={"video_filters": {"enabled": True, "denoise": 0.28, "sharpen": 0.1, "vignette": 0.1, "vignette_feather": 0.9}},
    ),
    EditorPreset(
        id="effect-product-screen-polish",
        kind="effect",
        name="Product Screen Polish",
        description="Clean product-demo polish for app and web UI footage.",
        tags=("product", "ui", "screen-recording", "clean"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.2, "denoise": 0.06, "vignette": 0.08, "vignette_feather": 0.92, "chroma_aberration": 0.008}},
    ),
    EditorPreset(
        id="effect-retro-glitch-lite",
        kind="effect",
        name="Retro Glitch Lite",
        description="Light chroma and glitch treatment for quick stylized cuts.",
        tags=("glitch", "retro", "stream", "short-form"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.12, "chroma_aberration": 0.1, "glitch": 0.12, "vignette": 0.06, "vignette_feather": 0.82}},
    ),
    EditorPreset(
        id="effect-anime-overlay-crisp",
        kind="effect",
        name="Anime Overlay Crisp",
        description="Crisp overlay preset for anime, Live2D, and Spine actor footage.",
        tags=("anime", "spine", "live2d", "character"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.24, "vignette": 0.06, "vignette_feather": 0.9, "chroma_aberration": 0.01}},
    ),
    EditorPreset(
        id="effect-dark-game-lift",
        kind="effect",
        name="Dark Game Lift",
        description="Clarity preset for dark gameplay while keeping edges readable.",
        tags=("gameplay", "dark", "recover", "contrast"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.18, "denoise": 0.12, "vignette": 0.05, "vignette_feather": 0.95}},
    ),
    EditorPreset(
        id="effect-document-capture-clean",
        kind="effect",
        name="Document Capture Clean",
        description="High-readability cleanup for document and code capture.",
        tags=("document", "text", "screen-recording", "tutorial"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.32, "denoise": 0.18, "vignette": 0.0}},
    ),
    EditorPreset(
        id="effect-social-pop-lite",
        kind="effect",
        name="Social Pop Lite",
        description="Light pop treatment for social clips without heavy distortion.",
        tags=("capcut", "short-form", "social", "pop"),
        payload={"video_filters": {"enabled": True, "sharpen": 0.2, "vignette": 0.12, "vignette_feather": 0.82, "chroma_aberration": 0.025}},
    ),
    EditorPreset(
        id="effect-low-light-denoise",
        kind="effect",
        name="Low Light Denoise",
        description="Heavier denoise pass for low-light webcam or gameplay clips.",
        tags=("denoise", "low-light", "webcam", "cleanup"),
        payload={"video_filters": {"enabled": True, "denoise": 0.5, "sharpen": 0.06, "vignette": 0.04, "vignette_feather": 0.88}},
    ),
)


CAPCUT_CREATOR_WORKFLOW_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="caption-capcut-word-pop",
        kind="caption_style",
        name="CapCut Word Pop",
        description="Large short-form caption style with bright word emphasis.",
        tags=("capcut", "caption", "auto-caption", "short-form", "vertical"),
        payload={
            "font_size": 58,
            "font_weight": 900,
            "fill": "#FFFFFF",
            "stroke": "#0E1020",
            "stroke_width": 8,
            "highlight": "#FFDD55",
            "word_highlight": True,
            "y_norm": 0.76,
            "animation": "word-pop",
        },
    ),
    EditorPreset(
        id="caption-capcut-karaoke-fast",
        kind="caption_style",
        name="CapCut Fast Karaoke",
        description="Fast karaoke caption treatment for voice/music clips.",
        tags=("capcut", "caption", "karaoke", "auto-caption", "music"),
        payload={
            "font_size": 50,
            "fill": "#F7F8FF",
            "stroke": "#11131C",
            "stroke_width": 6,
            "highlight": "#70F0FF",
            "word_highlight": True,
            "karaoke_speed": "fast",
            "y_norm": 0.80,
        },
    ),
    EditorPreset(
        id="title-capcut-hook-question",
        kind="title",
        name="CapCut Hook Question",
        description="Bright first-second hook question for social clips.",
        tags=("capcut", "title", "hook", "short-form", "vertical"),
        payload={
            "text": "WAIT, WHAT?",
            "duration_ms": 1300,
            "font_size": 66,
            "color": "#101320",
            "bg_color": "#FFDD55",
            "x_norm": 0.5,
            "y_norm": 0.18,
            "preset_id_in": "pop-in",
            "preset_id_out": "pop-out",
        },
    ),
    EditorPreset(
        id="sticker-social-cta-burst",
        kind="sticker",
        name="Social CTA Burst",
        description="Small follow/save/share burst for short-form endings.",
        tags=("capcut", "sticker", "social", "cta", "short-form"),
        payload={
            "shape": "burst",
            "text": "SAVE",
            "duration_ms": 1100,
            "scale": 0.88,
            "color": "#FF6F61",
            "x_norm": 0.78,
            "y_norm": 0.18,
            "animation": "pulse",
        },
    ),
    EditorPreset(
        id="motion-subject-keep-reframe",
        kind="motion",
        name="Subject Keep Reframe",
        description="Safe vertical reframe motion that follows the primary subject.",
        tags=("capcut", "motion", "reframe", "subject", "vertical"),
        payload={
            "target_aspect": "9:16",
            "keep_subject": True,
            "safe_margin": 0.12,
            "keyframes": [
                {"t": 0.0, "scale": 1.08, "x": 0.5, "y": 0.48},
                {"t": 1.0, "scale": 1.12, "x": 0.5, "y": 0.50},
            ],
            "easing": "smooth",
        },
    ),
    EditorPreset(
        id="transition-feed-swipe-up",
        kind="transition",
        name="Feed Swipe Up",
        description="Vertical feed-like swipe transition for Shorts/Reels edits.",
        tags=("capcut", "transition", "feed", "vertical", "short-form"),
        payload={"transition_out_type": "slide_up", "transition_out_ms": 260},
    ),
    EditorPreset(
        id="effect-ai-background-cutout-pop",
        kind="effect",
        name="AI Background Cutout Pop",
        description="Background-removal friendly look with subject edge cleanup hints.",
        tags=("capcut", "effect", "background-removal", "cutout", "short-form"),
        payload={
            "background_removal": {
                "enabled": True,
                "mode": "object-or-person",
                "edge_feather": 0.08,
                "spill_cleanup": 0.18,
                "fallback": "manual-mask-tracker",
            },
            "video_filters": {"enabled": True, "sharpen": 0.10, "vignette": 0.03},
        },
    ),
    EditorPreset(
        id="audio-capcut-voice-enhance",
        kind="audio",
        name="CapCut Voice Enhance",
        description="Creator voice cleanup with noise reduction, clarity, and short-form loudness.",
        tags=("capcut", "audio", "voice", "dialogue", "cleanup", "short-form"),
        payload={
            "dialogue_cleanup": {"enabled": True, "strength": 0.72, "de_reverb": 0.18, "de_ess": 0.22},
            "ai_master": {"enabled": True, "preset": "Creator Voice", "clarity": 58.0, "warmth": 12.0, "air": 2.0},
            "loudness": {"enabled": True, "target_i": -14.0, "true_peak": -1.0, "lra": 8.0, "target_id": "shortform"},
        },
    ),
    EditorPreset(
        id="audio-vocal-music-separation",
        kind="audio",
        name="Vocal Music Separation",
        description="Route the clip through the Sound Editor two-stem vocal/instrumental separation workflow.",
        tags=("capcut", "audio", "stem", "separation", "vocal", "music"),
        payload={
            "source_separation": {
                "enabled": True,
                "mode": "two_stems_vocals",
                "prefer_demucs": True,
                "fallback": "ffmpeg_center_extract",
                "add_stems_to_timeline": True,
            }
        },
    ),
    EditorPreset(
        id="template-capcut-auto-caption-shorts",
        kind="template",
        name="CapCut Auto Caption Shorts",
        description="Hook title, word-pop captions, voice enhance, CTA, and feed swipe for quick shorts.",
        tags=("capcut", "template", "auto-caption", "short-form", "vertical", "one-click"),
        payload={"sequence": [
            {"kind": "title", "preset_id": "title-capcut-hook-question", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-capcut-word-pop", "at_ms": 160},
            {"kind": "audio", "preset_id": "audio-capcut-voice-enhance", "condition": "if_audio"},
            {"kind": "audio", "preset_id": "audio-vocal-music-separation", "condition": "if_music"},
            {"kind": "sticker", "preset_id": "sticker-social-cta-burst", "at_ms": 1800},
            {"kind": "transition", "preset_id": "transition-feed-swipe-up"},
        ]},
    ),
    EditorPreset(
        id="template-capcut-long-to-shorts",
        kind="template",
        name="CapCut Long To Shorts",
        description="Template-first plan for extracting vertical captioned clips from longer recordings.",
        tags=("capcut", "template", "long-to-shorts", "auto-caption", "short-form", "one-click"),
        payload={"sequence": [
            {"kind": "motion", "preset_id": "motion-subject-keep-reframe", "at_ms": 0},
            {"kind": "title", "preset_id": "title-capcut-hook-question", "at_ms": 0},
            {"kind": "caption_style", "preset_id": "caption-capcut-word-pop", "at_ms": 220},
            {"kind": "audio", "preset_id": "audio-capcut-voice-enhance", "condition": "if_audio"},
            {"kind": "transition", "preset_id": "transition-feed-swipe-up"},
        ]},
    ),
    EditorPreset(
        id="template-capcut-subject-reframe",
        kind="template",
        name="CapCut Subject Reframe",
        description="Subject-aware vertical reframe with cutout-ready polish and readable captions.",
        tags=("capcut", "template", "reframe", "subject", "vertical", "one-click"),
        payload={"sequence": [
            {"kind": "motion", "preset_id": "motion-subject-keep-reframe", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-ai-background-cutout-pop", "condition": "if_cutout"},
            {"kind": "caption_style", "preset_id": "caption-capcut-karaoke-fast", "at_ms": 180},
        ]},
    ),
    EditorPreset(
        id="template-capcut-smart-search-edit",
        kind="template",
        name="CapCut Smart Search Edit",
        description="Search-driven edit starter for object/dialogue/person tagged media.",
        tags=("capcut", "template", "smart-search", "media", "dialogue", "one-click"),
        payload={"sequence": [
            {"kind": "title", "preset_id": "title-capcut-hook-question", "at_ms": 0},
            {"kind": "effect", "preset_id": "effect-clean-ui-depth", "at_ms": 0, "target": "selected_clip"},
            {"kind": "caption_style", "preset_id": "caption-capcut-word-pop", "at_ms": 260},
            {"kind": "motion", "preset_id": "motion-hook-bounce-in", "at_ms": 0},
        ]},
    ),
    EditorPreset(
        id="template-capcut-social-publish-kit",
        kind="template",
        name="CapCut Social Publish Kit",
        description="Final pass for social export: captions, CTA sticker, voice polish, and feed-safe transition.",
        tags=("capcut", "template", "social", "export", "publish", "short-form", "one-click"),
        payload={"sequence": [
            {"kind": "caption_style", "preset_id": "caption-capcut-word-pop", "at_ms": 0},
            {"kind": "sticker", "preset_id": "sticker-social-cta-burst", "at_ms": 1200},
            {"kind": "audio", "preset_id": "audio-capcut-voice-enhance", "condition": "if_audio"},
            {"kind": "transition", "preset_id": "transition-feed-swipe-up"},
        ]},
    ),
)


ACTOR_WORKFLOW_PRESETS: tuple[EditorPreset, ...] = (
    EditorPreset(
        id="actor-live2d-placeholder",
        kind="actor",
        name="Live2D Actor Placeholder",
        description="Create a Live2D actor lane placeholder at the template time.",
        tags=("actor", "live2d", "character", "template"),
        payload={"actor_kind": "live2d", "duration_ms": 3600, "open_editor": False},
    ),
    EditorPreset(
        id="actor-spine-placeholder",
        kind="actor",
        name="Spine Actor Placeholder",
        description="Create a Spine actor lane placeholder at the template time.",
        tags=("actor", "spine", "character", "template"),
        payload={"actor_kind": "spine", "duration_ms": 3600, "open_editor": False},
    ),
    EditorPreset(
        id="template-live2d-actor-spotlight",
        kind="template",
        name="Live2D Actor Spotlight",
        description="Create a Live2D actor placeholder with nameplate, reaction caption, and voice polish.",
        tags=("template", "live2d", "actor", "character", "reaction", "one-click"),
        payload={
            "sequence": [
                {"kind": "actor", "preset_id": "actor-live2d-placeholder", "at_ms": 0, "duration_ms": 3600, "target": "active_track"},
                {"kind": "effect", "preset_id": "effect-vtuber-overlay-pop", "condition": "if_video"},
                {"kind": "title", "preset_id": "title-live2d-nameplate", "at_ms": 0},
                {"kind": "caption_style", "preset_id": "caption-meme-punch"},
                {"kind": "audio", "preset_id": "audio-voiceover-bright-web", "condition": "if_audio"},
            ]
        },
    ),
    EditorPreset(
        id="template-spine-actor-action",
        kind="template",
        name="Spine Actor Action",
        description="Create a Spine actor placeholder with action-friendly character focus and impact polish.",
        tags=("template", "spine", "actor", "character", "gameplay", "one-click"),
        payload={
            "sequence": [
                {"kind": "actor", "preset_id": "actor-spine-placeholder", "at_ms": 0, "duration_ms": 3600, "target": "active_track"},
                {"kind": "effect", "preset_id": "effect-vtuber-overlay-pop", "condition": "if_video"},
                {"kind": "title", "preset_id": "title-score-callout", "at_ms": 220},
                {"kind": "motion", "preset_id": "motion-shake-impact", "at_ms": 620},
                {"kind": "transition", "preset_id": "transition-hit-white"},
            ]
        },
    ),
)


def _load_json_presets(path: Path) -> list[EditorPreset]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("presets", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    presets: list[EditorPreset] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            presets.append(EditorPreset.from_dict(row))
        except Exception:
            continue
    return presets


def _load_json_payload(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _builtin_presets() -> list[EditorPreset]:
    return (
        list(BUILTIN_PRESETS)
        + list(COMMERCIAL_POLISH_PRESETS)
        + list(PROFESSIONAL_WORKFLOW_PRESETS)
        + list(SOCIAL_CREATOR_PRESETS)
        + list(PRODUCTION_TEMPLATE_PRESETS)
        + list(CONTENT_EXPANSION_PRESETS)
        + list(SCREEN_STUDIO_STYLE_PRESETS)
        + list(SCREEN_STUDIO_MICRO_PRESETS)
        + list(SCREEN_STUDIO_TEMPLATE_PACK_PRESETS)
        + list(SCREEN_STUDIO_DELIVERY_TEMPLATE_PRESETS)
        + list(SCREEN_STUDIO_ANIMATED_ICON_PRESETS)
        + list(SCREEN_STUDIO_QUICK_RESULT_PRESETS)
        + list(CREATOR_EFFECT_TRANSITION_EXPANSION_PRESETS)
        + list(CAPCUT_CREATOR_WORKFLOW_PRESETS)
        + list(ACTOR_WORKFLOW_PRESETS)
    )


def _builtin_preset_ids() -> set[str]:
    return {preset.id for preset in _builtin_presets()}


def user_preset_dir() -> Path:
    """Return the writable preset pack directory for this install."""
    try:
        from app.paths import default_save_dir

        root = default_save_dir()
    except Exception:
        root = Path.home() / ".tigercapture"
    path = root / "preset_packs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_preset_file() -> Path:
    """Primary JSON pack used for presets saved from the editor UI."""
    return user_preset_dir() / "user_presets.json"


def _default_extra_paths() -> list[Path]:
    root = user_preset_dir()
    paths: list[Path] = []
    primary = user_preset_file()
    if primary.exists():
        paths.append(primary)
    for path in sorted(root.glob("*.json")):
        if path != primary:
            paths.append(path)
    return paths


def load_editor_presets(extra_paths: Iterable[Path | str] = ()) -> list[EditorPreset]:
    presets = _builtin_presets()
    seen = {preset.id for preset in presets}
    all_extra_paths = [*_default_extra_paths(), *list(extra_paths or ())]
    for raw_path in all_extra_paths:
        for preset in _load_json_presets(Path(raw_path)):
            if preset.id in seen:
                continue
            seen.add(preset.id)
            presets.append(preset)
    return presets


def save_user_preset(preset: EditorPreset) -> Path:
    """Create or replace a preset in the user's editable preset pack."""
    path = user_preset_file()
    existing = _load_json_presets(path)
    rows = [item for item in existing if item.id != preset.id]
    rows.append(preset)
    payload = {"schema": 1, "source": "TigerCapture user presets", "presets": [p.to_dict() for p in rows]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def import_preset_pack(path: Path | str) -> int:
    """Copy a JSON preset pack into the user pack directory.

    Returns the number of valid presets found in the source pack. Invalid packs
    are rejected by returning 0 without copying.
    """
    src = Path(path)
    presets = _load_json_presets(src)
    if not presets:
        return 0
    dest = user_preset_dir() / src.name
    if dest.exists():
        stem = src.stem
        suffix = src.suffix or ".json"
        for idx in range(2, 1000):
            candidate = user_preset_dir() / f"{stem}-{idx}{suffix}"
            if not candidate.exists():
                dest = candidate
                break
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return len(presets)


def export_user_presets(path: Path | str) -> Path:
    """Export all user-loaded presets, excluding bundled presets, to a JSON pack."""
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    bundled_ids = _builtin_preset_ids()
    rows = [
        preset.to_dict()
        for preset in load_editor_presets()
        if preset.id not in bundled_ids
    ]
    payload = {"schema": 1, "source": "TigerCapture exported preset pack", "presets": rows}
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return dest


def inspect_preset_pack(path: Path | str) -> dict[str, Any]:
    """Inspect a single user preset pack for conflicts and repair hints."""
    pack_path = Path(path)
    raw = _load_json_payload(pack_path)
    rows = raw.get("presets", raw) if isinstance(raw, dict) else raw
    row_count = len(rows) if isinstance(rows, list) else 0
    presets = _load_json_presets(pack_path)
    ids = [preset.id for preset in presets]
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    for preset_id in ids:
        if preset_id in seen and preset_id not in duplicate_ids:
            duplicate_ids.append(preset_id)
        seen.add(preset_id)
    builtin_conflicts = sorted(set(ids) & _builtin_preset_ids())
    known_ids = _builtin_preset_ids() | set(ids)
    missing_refs: list[dict[str, Any]] = []
    for preset in presets:
        if preset.kind != "template":
            continue
        for entry in template_sequence(preset):
            ref_id = str(entry.get("preset_id", "") or "")
            if ref_id and ref_id not in known_ids:
                missing_refs.append({
                    "template_id": preset.id,
                    "preset_id": ref_id,
                    "kind": str(entry.get("kind", "") or ""),
                })
    issues: list[str] = []
    if row_count != len(presets):
        issues.append("invalid_rows")
    if duplicate_ids:
        issues.append("duplicate_ids")
    if builtin_conflicts:
        issues.append("builtin_id_conflicts")
    if missing_refs:
        issues.append("missing_template_refs")
    schema = raw.get("schema") if isinstance(raw, dict) else None
    source = raw.get("source") if isinstance(raw, dict) else ""
    return {
        "path": str(pack_path),
        "name": pack_path.name[:-9] if pack_path.name.endswith(".disabled") else pack_path.name,
        "schema": schema,
        "source": str(source or ""),
        "count": len(presets),
        "row_count": row_count,
        "invalid_count": max(0, row_count - len(presets)),
        "duplicate_ids": duplicate_ids,
        "builtin_conflicts": builtin_conflicts,
        "missing_refs": missing_refs,
        "issues": issues,
        "ok": not issues,
    }


def list_user_preset_packs() -> list[dict[str, Any]]:
    """Return user preset pack files and their enabled state."""
    root = user_preset_dir()
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        info = inspect_preset_pack(path)
        rows.append({
            **info,
            "path": str(path),
            "name": path.name,
            "enabled": True,
            "primary": path == user_preset_file(),
        })
    for path in sorted(root.glob("*.json.disabled")):
        info = inspect_preset_pack(path)
        rows.append({
            **info,
            "path": str(path),
            "name": path.name[:-9],
            "enabled": False,
            "primary": False,
        })
    id_to_packs: dict[str, list[str]] = {}
    for row in rows:
        if not row.get("enabled"):
            continue
        for preset in _load_json_presets(Path(str(row.get("path", "")))):
            id_to_packs.setdefault(preset.id, []).append(str(row.get("name", "")))
    cross_conflicts = {
        preset_id: packs
        for preset_id, packs in id_to_packs.items()
        if len(set(packs)) > 1
    }
    for row in rows:
        pack_name = str(row.get("name", ""))
        ids = [preset.id for preset in _load_json_presets(Path(str(row.get("path", ""))))]
        row_conflicts = [
            preset_id for preset_id in ids
            if pack_name in cross_conflicts.get(preset_id, [])
        ]
        row["cross_pack_conflicts"] = sorted(set(row_conflicts))
        if row_conflicts and "cross_pack_conflicts" not in row["issues"]:
            row["issues"] = [*list(row.get("issues", []) or []), "cross_pack_conflicts"]
            row["ok"] = False
    return rows


def preset_pack_marketplace_report() -> dict[str, Any]:
    """Summarize installed user preset packs as a small marketplace dashboard."""
    packs = list_user_preset_packs()
    kind_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    pack_cards: list[dict[str, Any]] = []
    for row in packs:
        presets = _load_json_presets(Path(str(row.get("path", ""))))
        local_kinds: dict[str, int] = {}
        local_tags: dict[str, int] = {}
        for preset in presets:
            local_kinds[preset.kind] = local_kinds.get(preset.kind, 0) + 1
            kind_counts[preset.kind] = kind_counts.get(preset.kind, 0) + 1
            for tag in preset.tags:
                local_tags[tag] = local_tags.get(tag, 0) + 1
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        issues = list(row.get("issues", []) or [])
        if issues:
            recommendation = "Repair or disable before using this pack in one-click templates."
            score = max(20, 82 - len(issues) * 18)
        elif not row.get("enabled"):
            recommendation = "Disabled pack; enable it if these presets should appear in the editor."
            score = 72
        elif int(row.get("count", 0) or 0) < 4:
            recommendation = "Small pack; consider merging into a themed collection."
            score = 86
        else:
            recommendation = "Ready"
            score = 100
        coverage = ", ".join(f"{kind}:{count}" for kind, count in sorted(local_kinds.items())[:4]) or "empty"
        pack_cards.append({
            "name": row.get("name", ""),
            "path": row.get("path", ""),
            "enabled": bool(row.get("enabled")),
            "primary": bool(row.get("primary")),
            "count": int(row.get("count", 0) or 0),
            "issues": issues,
            "duplicate_ids": list(row.get("duplicate_ids", []) or []),
            "builtin_conflicts": list(row.get("builtin_conflicts", []) or []),
            "cross_pack_conflicts": list(row.get("cross_pack_conflicts", []) or []),
            "missing_refs": list(row.get("missing_refs", []) or []),
            "score": score,
            "coverage": coverage,
            "kinds": dict(sorted(local_kinds.items())),
            "top_tags": dict(sorted(local_tags.items(), key=lambda item: (-item[1], item[0]))[:8]),
            "recommendation": recommendation,
        })

    enabled = [row for row in packs if row.get("enabled")]
    disabled = [row for row in packs if not row.get("enabled")]
    issue_packs = [row for row in packs if row.get("issues")]
    recommendations: list[str] = []
    if not packs:
        recommendations.append("Import or create a user preset pack to build a reusable template library.")
    if issue_packs:
        recommendations.append(f"Repair {len(issue_packs)} pack(s) with conflicts or broken template references.")
    if disabled:
        recommendations.append(f"{len(disabled)} pack(s) are disabled and hidden from preset search.")
    if sum(int(row.get("count", 0) or 0) for row in enabled) < 12:
        recommendations.append("Installed enabled pack coverage is still small for production template browsing.")
    if not recommendations:
        recommendations.append("Preset packs are ready for browsing and one-click template use.")
    return {
        "total_packs": len(packs),
        "enabled_packs": len(enabled),
        "disabled_packs": len(disabled),
        "issue_packs": len(issue_packs),
        "total_presets": sum(int(row.get("count", 0) or 0) for row in packs),
        "enabled_presets": sum(int(row.get("count", 0) or 0) for row in enabled),
        "kind_counts": dict(sorted(kind_counts.items())),
        "top_tags": dict(sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:12]),
        "packs": pack_cards,
        "recommendations": recommendations,
        "ok": not issue_packs,
    }


def set_user_preset_pack_enabled(path: Path | str, enabled: bool) -> Path:
    """Enable/disable a user pack by renaming it in the pack directory."""
    src = Path(path)
    root = user_preset_dir().resolve()
    resolved = src.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("Preset pack is outside the user preset directory")
    if resolved == user_preset_file().resolve():
        raise ValueError("The primary user preset pack cannot be disabled")
    if bool(enabled):
        name = src.name
        if name.endswith(".disabled"):
            name = name[:-9]
        dest = src.with_name(name)
    else:
        if src.name.endswith(".disabled"):
            return src
        dest = src.with_name(src.name + ".disabled")
    if dest == src:
        return dest
    if dest.exists():
        raise FileExistsError(dest)
    src.rename(dest)
    return dest


def delete_user_preset_pack(path: Path | str) -> None:
    """Delete a non-primary user preset pack."""
    src = Path(path)
    root = user_preset_dir().resolve()
    resolved = src.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("Preset pack is outside the user preset directory")
    if resolved == user_preset_file().resolve():
        raise ValueError("The primary user preset pack cannot be deleted")
    src.unlink(missing_ok=True)


def repair_user_preset_pack(path: Path | str) -> dict[str, Any]:
    """Rewrite a user pack into a normalized, loadable JSON pack.

    A timestamped backup is written beside the original. Duplicate ids are
    skipped after their first valid occurrence, and template sequence entries
    that point to missing presets are removed rather than left broken.
    """
    pack_path = Path(path)
    if not pack_path.exists():
        raise FileNotFoundError(pack_path)
    root = user_preset_dir().resolve()
    resolved = pack_path.resolve()
    if root not in resolved.parents and resolved != root:
        raise ValueError("Preset pack is outside the user preset directory")
    raw = _load_json_payload(pack_path)
    rows = raw.get("presets", raw) if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        rows = []
    valid: list[EditorPreset] = []
    seen: set[str] = set()
    duplicate_count = 0
    invalid_count = 0
    for row in rows:
        if not isinstance(row, dict):
            invalid_count += 1
            continue
        try:
            preset = EditorPreset.from_dict(row)
        except Exception:
            invalid_count += 1
            continue
        if preset.id in seen:
            duplicate_count += 1
            continue
        seen.add(preset.id)
        valid.append(preset)
    known_ids = _builtin_preset_ids() | {preset.id for preset in valid}
    repaired: list[EditorPreset] = []
    removed_refs = 0
    for preset in valid:
        if preset.kind == "template":
            payload = dict(preset.payload)
            sequence = payload.get("sequence")
            if isinstance(sequence, list):
                next_sequence = []
                for entry in sequence:
                    if not isinstance(entry, dict):
                        removed_refs += 1
                        continue
                    ref_id = str(entry.get("preset_id", "") or "")
                    if ref_id and ref_id in known_ids:
                        next_sequence.append(entry)
                    else:
                        removed_refs += 1
                payload["sequence"] = next_sequence
                preset = EditorPreset(
                    id=preset.id,
                    kind=preset.kind,
                    name=preset.name,
                    description=preset.description,
                    tags=preset.tags,
                    payload=payload,
                )
        repaired.append(preset)
    backup = pack_path.with_suffix(pack_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    backup.write_text(pack_path.read_text(encoding="utf-8"), encoding="utf-8")
    payload = {
        "schema": 1,
        "source": "TigerCapture repaired preset pack",
        "repaired_at": datetime.now().isoformat(timespec="seconds"),
        "presets": [preset.to_dict() for preset in repaired],
    }
    pack_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(pack_path),
        "backup": str(backup),
        "count": len(repaired),
        "invalid_removed": invalid_count,
        "duplicates_removed": duplicate_count,
        "missing_refs_removed": removed_refs,
    }


def presets_by_kind(kind: str, extra_paths: Iterable[Path | str] = ()) -> list[EditorPreset]:
    kind = str(kind)
    return [preset for preset in load_editor_presets(extra_paths) if preset.kind == kind]


def preset_by_id(preset_id: str, extra_paths: Iterable[Path | str] = ()) -> EditorPreset | None:
    preset_id = str(preset_id or "")
    for preset in load_editor_presets(extra_paths):
        if preset.id == preset_id:
            return preset
    return None


def template_sequence(preset: EditorPreset | dict[str, Any]) -> list[dict[str, Any]]:
    """Return normalized sequence entries from a template preset payload."""
    payload = dict(preset.payload if isinstance(preset, EditorPreset) else preset)
    raw = payload.get("sequence")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        preset_id = str(item.get("preset_id", "") or "")
        kind = str(item.get("kind", "") or "")
        if not preset_id:
            continue
        out.append({**item, "kind": kind, "preset_id": preset_id})
    return out


def preset_preview_storyboard(preset: EditorPreset | dict[str, Any]) -> dict[str, Any]:
    """Return lightweight A/B preview metadata for preset cards and QA."""
    if isinstance(preset, EditorPreset):
        kind = preset.kind
        name = preset.name
        payload = dict(preset.payload)
        preset_id = preset.id
    else:
        payload = dict(preset)
        kind = str(payload.get("kind") or payload.get("preset_kind") or "preset")
        name = str(payload.get("name") or payload.get("id") or kind.title())
        preset_id = str(payload.get("id") or name)
    cues: list[str] = []
    before = "Original frame"
    after = name
    accent = "#755DF2"
    bake_targets: list[str] = []
    if kind == "effect" or "video_filters" in payload:
        vf = payload.get("video_filters", {}) if isinstance(payload.get("video_filters"), dict) else {}
        if vf.get("contrast") or vf.get("brightness") or vf.get("saturation"):
            cues.append("tone")
        if vf.get("sharpen") or vf.get("denoise"):
            cues.append("detail")
        if payload.get("chroma_key"):
            cues.append("key")
            accent = "#36D1DC"
        if payload.get("background_blur") or vf.get("blur"):
            cues.append("blur")
        bake_targets.append("clip_filter")
    elif kind == "transition" or "transition_out_type" in payload:
        cues.append(str(payload.get("transition_out_type") or "transition"))
        after = f"{name} midpoint"
        accent = "#FF8057"
        bake_targets.append("transition")
    elif kind == "title" or "text" in payload:
        cues.append("title")
        after = str(payload.get("text") or name)
        accent = "#F65368"
        bake_targets.append("title_overlay")
    elif kind == "color" or "color_grade" in payload or "advanced_color_toolset" in payload:
        cues.append("grade")
        if isinstance(payload.get("advanced_color_toolset"), dict):
            cues.append("advanced")
        accent = "#8A7CFF"
        bake_targets.append("color_grade")
    elif kind == "audio" or any(k in payload for k in ("loudness", "dialogue_cleanup", "eq", "comp")):
        cues.append("audio")
        accent = "#5DCAA5"
        bake_targets.append("audio_chain")
    elif kind == "template" or isinstance(payload.get("sequence"), list):
        sequence = payload.get("sequence", []) if isinstance(payload.get("sequence"), list) else []
        cues.extend(str(row.get("kind") or row.get("preset_id") or "step") for row in sequence[:4] if isinstance(row, dict))
        after = f"{name} sequence"
        accent = "#FFB454"
        bake_targets.append("template_sequence")
    return {
        "id": preset_id,
        "kind": kind,
        "before_label": before,
        "after_label": after,
        "accent": accent,
        "cues": cues or [kind],
        "bake_targets": bake_targets,
    }


def presets_by_tags(tags: Iterable[str], extra_paths: Iterable[Path | str] = ()) -> list[EditorPreset]:
    wanted = {str(tag).lower() for tag in tags if str(tag)}
    if not wanted:
        return load_editor_presets(extra_paths)
    return [
        preset for preset in load_editor_presets(extra_paths)
        if wanted.issubset({tag.lower() for tag in preset.tags})
    ]


def search_presets(
    query: str = "",
    *,
    kind: str | None = None,
    tags: Iterable[str] = (),
    extra_paths: Iterable[Path | str] = (),
) -> list[EditorPreset]:
    """Search presets by id, name, description, and tags."""
    q_groups = _search_term_groups(query)
    wanted_tags = {str(tag).lower() for tag in tags if str(tag)}
    results: list[tuple[int, EditorPreset]] = []
    for preset in load_editor_presets(extra_paths):
        if kind is not None and preset.kind != str(kind):
            continue
        preset_tags = {tag.lower() for tag in preset.tags}
        if wanted_tags and not wanted_tags.issubset(preset_tags):
            continue
        haystack = _search_text(" ".join((
            preset.id,
            preset.name,
            preset.description,
            " ".join(preset.tags),
        )))
        if q_groups and not all(any(term in haystack for term in group) for group in q_groups):
            continue
        results.append((_search_score(haystack, q_groups), preset))
    if q_groups:
        results.sort(key=lambda item: (-item[0], item[1].kind, item[1].name.casefold()))
    return [preset for _score, preset in results]


PRESET_SEARCH_ALIASES: dict[str, tuple[str, ...]] = {
    "쇼츠": ("short form", "shortform", "vertical", "social", "reel", "caption"),
    "숏폼": ("short form", "shortform", "vertical", "social", "reel", "caption"),
    "캡컷": ("capcut", "short form", "auto caption", "template", "social"),
    "자동자막": ("auto caption", "caption", "subtitle", "capcut"),
    "자동": ("auto", "caption", "template", "capcut"),
    "배경제거": ("background removal", "cutout", "green screen", "capcut"),
    "세로변환": ("vertical", "reframe", "subject", "capcut"),
    "릴스": ("short form", "vertical", "reel", "social"),
    "틱톡": ("short form", "vertical", "tiktok", "social"),
    "게임": ("gameplay", "game", "esports", "stream", "capture"),
    "튜토리얼": ("tutorial", "how to", "hotkey", "step", "screen"),
    "강좌": ("tutorial", "how to", "step", "screen"),
    "대사": ("dialogue", "voice", "podcast", "talking head"),
    "보컬": ("dialogue", "voice", "vocal"),
    "선명": ("clean", "clarity", "cleanup", "sharp", "readable"),
    "노이즈": ("noise", "denoise", "cleanup", "dialogue"),
    "자막": ("caption", "subtitle"),
    "상품": ("product", "demo", "commercial", "review"),
    "리뷰": ("review", "product", "comparison", "verdict"),
    "브이로그": ("b roll", "b-roll", "cutaway", "documentary", "story"),
    "뉴스": ("news", "documentary", "editorial"),
    "순위": ("ranking", "listicle", "countdown"),
    "니케": ("spine", "anime", "character", "reaction"),
    "스파인": ("spine", "actor", "character"),
    "라이브2d": ("live2d", "actor", "character"),
    "라이브디": ("live2d", "actor", "character"),
    "캐릭터": ("character", "actor", "live2d", "spine"),
}


def _search_term_groups(query: Any) -> list[tuple[str, ...]]:
    terms = _search_text(query).split()
    groups: list[tuple[str, ...]] = []
    for term in terms:
        aliases = PRESET_SEARCH_ALIASES.get(term, ())
        normalized = [_search_text(term)]
        normalized.extend(_search_text(alias) for alias in aliases)
        group = tuple(item for item in dict.fromkeys(normalized) if item)
        if group:
            groups.append(group)
    return groups


def _search_score(haystack: str, groups: list[tuple[str, ...]]) -> int:
    if not groups:
        return 0
    score = 0
    for group in groups:
        for idx, term in enumerate(group):
            if term and term in haystack:
                score += max(1, 8 - idx)
                break
    return score


def _search_text(value: Any) -> str:
    text = str(value or "").lower()
    for ch in ("-", "_", "/", "\\", ":", "|", "(", ")", "[", "]"):
        text = text.replace(ch, " ")
    return " ".join(text.split())


def preset_library_summary(extra_paths: Iterable[Path | str] = ()) -> dict[str, Any]:
    """Return counts and tag coverage for product/library diagnostics."""
    presets = load_editor_presets(extra_paths)
    counts: dict[str, int] = {}
    tags: dict[str, int] = {}
    for preset in presets:
        counts[preset.kind] = counts.get(preset.kind, 0) + 1
        for tag in preset.tags:
            tags[tag] = tags.get(tag, 0) + 1
    return {
        "total": len(presets),
        "by_kind": counts,
        "tags": dict(sorted(tags.items(), key=lambda item: (-item[1], item[0]))),
    }


def title_drag_payload(preset: EditorPreset) -> dict[str, Any]:
    """Return the timeline title payload used by the existing drag/drop path."""
    payload = dict(preset.payload)
    typo_id = str(payload.get("typography_preset_id") or "")
    out = {
        "id": preset.id,
        "name": preset.name,
        "icon": str(payload.get("icon") or "T"),
        "text": str(payload.get("text") or preset.name.upper()),
        "duration_ms": int(payload.get("duration_ms", 3000) or 3000),
        "desc": preset.description,
        "font_size": int(payload.get("font_size", 56) or 56),
        "color": str(payload.get("color") or "#ffffff"),
        "bg_color": str(payload.get("bg_color") or ""),
        "x_norm": float(payload.get("x_norm", 0.5)),
        "y_norm": float(payload.get("y_norm", 0.5)),
        "preset_id_in": str(payload.get("preset_id_in") or "fade-in"),
        "preset_id_out": str(payload.get("preset_id_out") or "fade-out"),
    }
    if typo_id:
        out["typography_preset_id"] = typo_id
    return out


def transition_drag_payload(preset: EditorPreset, *, default_ms: int | None = None) -> dict[str, Any]:
    """Return the compact transition payload consumed by TrackRow drops."""
    payload = dict(preset.payload)
    return {
        "type": str(payload.get("transition_out_type") or payload.get("type") or "dissolve"),
        "ms": int(default_ms or payload.get("transition_out_ms") or payload.get("ms") or 500),
        "preset_id": preset.id,
        "name": preset.name,
    }


def apply_effect_preset_to_clip(clip: Any, preset: EditorPreset | dict[str, Any]) -> bool:
    """Apply an effect preset payload to a timeline clip.

    This intentionally supports a small, explicit payload surface first. The UI
    can drag presets onto clips today, while future preset kinds can extend this
    function without changing the timeline drop contract.
    """
    payload = dict(preset.payload if isinstance(preset, EditorPreset) else preset)
    if isinstance(preset, EditorPreset):
        preset_meta = {"id": preset.id, "name": preset.name, "kind": preset.kind}
    else:
        raw_meta = payload.get("__preset_meta")
        preset_meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}
        if not preset_meta:
            preset_meta = {
                "id": str(payload.get("preset_id") or payload.get("id") or ""),
                "name": str(payload.get("preset_name") or payload.get("name") or ""),
                "kind": str(payload.get("kind") or "effect"),
            }
    preset_meta = {k: v for k, v in preset_meta.items() if v not in (None, "")}
    changed = False

    video_filters = payload.get("video_filters")
    if isinstance(video_filters, dict):
        from app.video_filters import VideoFilterParams

        params = VideoFilterParams.from_dict(video_filters)
        try:
            params.preset_meta = dict(preset_meta)
        except Exception:
            pass
        setattr(clip, "video_filters", params)
        changed = True

    chroma_key = payload.get("chroma_key")
    if isinstance(chroma_key, dict):
        from app.chroma_key import ChromaKeyParams

        params = ChromaKeyParams.from_dict(chroma_key)
        setattr(clip, "chroma_key", params)
        changed = True

    return changed


def apply_audio_preset_to_clip(clip: Any, preset: EditorPreset | dict[str, Any]) -> bool:
    """Apply an audio preset to an AudioClip-like object."""
    payload = dict(preset.payload if isinstance(preset, EditorPreset) else preset)
    from app.audio_workflow import apply_audio_preset_to_clip as _apply_audio

    return bool(_apply_audio(clip, payload))


def apply_color_preset_to_grade(grade: Any, preset: EditorPreset | dict[str, Any]) -> dict[str, Any]:
    """Apply color-grade fields and return the node workflow payload.

    The return value can be attached to a node graph or UI color-node model. The
    function mutates only fields that exist on the supplied ColorGrade-like
    object, so older grade objects remain compatible.
    """
    payload = dict(preset.payload if isinstance(preset, EditorPreset) else preset)
    grade_payload = payload.get("color_grade") if isinstance(payload.get("color_grade"), dict) else {}
    for key, value in grade_payload.items():
        if hasattr(grade, key):
            try:
                setattr(grade, key, int(value))
            except Exception:
                setattr(grade, key, value)
    advanced = payload.get("advanced_color_toolset")
    if isinstance(advanced, dict) and hasattr(grade, "advanced_color_toolset"):
        try:
            setattr(grade, "advanced_color_toolset", dict(advanced))
        except Exception:
            pass
    workflow = payload.get("color_workflow")
    return dict(workflow) if isinstance(workflow, dict) else {}


def one_click_preset_plan(project_summary: dict[str, Any]) -> list[EditorPreset]:
    """Return ordered presets for a coarse one-click edit plan."""
    summary = project_summary or {}
    ids: list[str] = []

    if summary.get("shortform") or summary.get("vertical") or summary.get("duration_s", 9999) <= 90:
        ids.extend([
            "template-capcut-auto-caption-shorts",
            "template-capcut-subject-reframe",
            "template-capcut-social-publish-kit",
            "template-screenstudio-short-export",
            "template-shortform-hook-caption",
            "template-capcut-hook-stack",
            "template-shorts-hook-caption-burst",
            "template-wallpaper-palette-hook",
            "template-social-listicle",
            "caption-auto-bold-pop",
            "caption-vertical-safe",
            "transition-hit-white",
            "audio-loudness-shortform",
        ])
    if summary.get("capcut") or summary.get("auto_caption") or summary.get("long_to_shorts") or summary.get("social_export"):
        ids.extend([
            "template-capcut-long-to-shorts",
            "template-capcut-auto-caption-shorts",
            "template-capcut-smart-search-edit",
            "template-capcut-subject-reframe",
            "template-capcut-social-publish-kit",
            "caption-capcut-word-pop",
            "audio-capcut-voice-enhance",
            "audio-vocal-music-separation",
            "effect-ai-background-cutout-pop",
        ])
    if summary.get("gameplay") or summary.get("game"):
        ids.extend([
            "template-gameplay-highlight",
            "template-gaming-highlight-screen",
            "effect-esports-crisp",
            "sticker-hit-marker",
            "motion-shake-impact",
        ])
    if summary.get("dialogue") or summary.get("voice") or summary.get("podcast"):
        ids.extend([
            "template-dialogue-cleanup-cut",
            "template-clean-talking-head",
            "template-podcast-chapter",
            "audio-dialogue-cleanup-strong",
            "audio-streamer-voice",
            "audio-podcast-balanced",
            "audio-loudness-podcast",
            "caption-clean-subtitle",
        ])
    if summary.get("live2d"):
        ids.extend([
            "template-live2d-actor-spotlight",
            "actor-live2d-placeholder",
        ])
    if summary.get("spine"):
        ids.extend([
            "template-spine-actor-action",
            "actor-spine-placeholder",
        ])
    if summary.get("live2d") or summary.get("spine") or summary.get("character"):
        ids.extend([
            "template-live2d-reaction",
            "title-live2d-nameplate",
            "effect-character-focus",
            "effect-vtuber-overlay-pop",
        ])
    if summary.get("tutorial") or summary.get("howto") or summary.get("how_to") or summary.get("screen_recording"):
        ids.extend([
            "template-screenstudio-record-edit-export",
            "template-screenstudio-click-to-cut",
            "template-screenstudio-wallpaper-demo",
            "template-screenstudio-cursor-demo",
            "template-screenstudio-hotkey-demo",
            "template-cursor-click-highlight",
            "template-cursor-tutorial-chapter",
            "template-tutorial-step-by-step",
            "effect-screenstudio-clean-glow",
            "effect-clean-ui-depth",
            "effect-tutorial-cursor-clarity",
            "caption-tutorial-compact",
            "sticker-step-marker",
        ])
    if summary.get("product") or summary.get("demo") or summary.get("commercial"):
        ids.extend([
            "template-screenstudio-product-walkthrough",
            "template-product-ui-callout",
            "template-product-launch-clean",
            "template-corporate-clean-demo",
            "template-product-demo-clean",
            "effect-product-demo-polish",
            "color-product-demo-clean",
            "sticker-new-badge",
        ])
    if summary.get("review") or summary.get("comparison") or summary.get("verdict"):
        ids.extend([
            "template-product-review-verdict",
            "effect-product-review-neutral",
            "caption-review-procon",
            "sticker-pro-con-pill",
        ])
    if summary.get("broll") or summary.get("b_roll") or summary.get("cutaway"):
        ids.extend([
            "template-broll-story-insert",
            "effect-broll-soft-detail",
            "motion-slow-kenburns",
        ])
    if summary.get("reaction") or summary.get("meme") or summary.get("creator") or summary.get("stream"):
        ids.extend([
            "template-reaction-punch-pack",
            "template-stream-highlight-pack",
            "effect-meme-punch",
            "audio-streamer-voice",
        ])
    if summary.get("news") or summary.get("documentary") or summary.get("editorial"):
        ids.extend([
            "template-news-brief",
            "template-broll-story-insert",
            "effect-documentary-clarity",
            "caption-documentary-clear",
            "audio-voiceover-bright-web",
        ])
    if summary.get("ranking") or summary.get("listicle") or summary.get("countdown"):
        ids.extend([
            "template-ranking-short",
            "title-ranking-number",
            "sticker-ranking-medal",
            "transition-ranking-pop",
        ])
    if summary.get("anime") or summary.get("mobile") or summary.get("food"):
        if summary.get("anime"):
            ids.extend(["template-anime-reaction-clean", "effect-anime-cleanline"])
        if summary.get("mobile"):
            ids.extend(["template-hotkey-tutorial", "effect-mobile-screen-pop"])
        if summary.get("food"):
            ids.extend(["template-product-food-gloss", "effect-food-product-gloss"])
    if summary.get("patch") or summary.get("patch_note") or summary.get("update"):
        ids.extend([
            "template-patch-note-update",
            "effect-patch-note-readable",
            "title-patch-note",
        ])
    if not ids:
        ids.extend(["color-curves-contrast-s", "effect-clean-sharpen", "audio-loudness-shortform"])

    by_id = {preset.id: preset for preset in load_editor_presets()}
    out: list[EditorPreset] = []
    seen: set[str] = set()
    for preset_id in ids:
        preset = by_id.get(preset_id)
        if preset is None or preset.id in seen:
            continue
        seen.add(preset.id)
        out.append(preset)
    return out


PRESET_ECOSYSTEM_KIND_TARGETS: dict[str, int] = {
    "effect": 32,
    "transition": 27,
    "title": 30,
    "audio": 11,
    "color": 6,
    "template": 31,
    "caption_style": 14,
    "sticker": 17,
    "motion": 11,
    "actor": 2,
}


PRESET_ECOSYSTEM_TOPIC_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "short-form": ("template", "effect", "transition", "caption_style", "audio"),
    "gameplay": ("template", "effect", "title", "sticker", "motion"),
    "tutorial": ("template", "effect", "title", "caption_style", "sticker"),
    "product": ("template", "effect", "title", "color", "sticker"),
    "dialogue": ("template", "audio", "caption_style"),
    "live2d": ("template", "actor", "effect", "title"),
    "spine": ("template", "actor", "effect", "title"),
    "news": ("template", "effect", "caption_style", "audio"),
    "ranking": ("template", "title", "sticker", "transition"),
    "b-roll": ("template", "effect", "motion", "sticker"),
    "podcast": ("template", "audio", "caption_style", "title"),
    "review": ("template", "effect", "caption_style", "sticker", "audio"),
    "patch-note": ("template", "effect", "title", "caption_style"),
    "capcut": ("template", "caption_style", "sticker", "motion", "audio", "transition", "effect"),
}


PRESET_ECOSYSTEM_TOPIC_ALIASES: dict[str, tuple[str, ...]] = {
    "news": ("documentary", "editorial", "voiceover"),
    "patch-note": ("patch", "update", "hotkey", "screen"),
    "b-roll": ("broll", "cutaway"),
    "short-form": ("shortform", "vertical", "social"),
    "spine": ("anime", "character", "actor"),
    "capcut": ("short-form", "auto-caption", "vertical", "social"),
}


_ONE_CLICK_TOPIC_SUMMARIES: dict[str, dict[str, Any]] = {
    "short-form": {"shortform": True},
    "gameplay": {"gameplay": True},
    "tutorial": {"tutorial": True},
    "product": {"product": True},
    "dialogue": {"dialogue": True},
    "live2d": {"live2d": True},
    "spine": {"spine": True},
    "news": {"news": True},
    "ranking": {"ranking": True},
    "b-roll": {"broll": True},
    "podcast": {"podcast": True},
    "review": {"review": True},
    "patch-note": {"patch_note": True},
    "capcut": {"capcut": True, "shortform": True, "auto_caption": True},
}


def _preset_matches_topic(preset: EditorPreset, topic: str) -> bool:
    topic_terms = {
        topic,
        topic.replace("-", " "),
        topic.replace("-", "_"),
    }
    topic_terms.update(PRESET_ECOSYSTEM_TOPIC_ALIASES.get(topic, ()))
    preset_tags = {tag.lower() for tag in preset.tags}
    text = _search_text(" ".join((preset.id, preset.name, preset.description, " ".join(preset.tags))))
    return any(term in preset_tags or _search_text(term) in text for term in topic_terms)


def _template_reference_issues(presets: list[EditorPreset]) -> list[dict[str, Any]]:
    by_id = {preset.id: preset for preset in presets}
    issues: list[dict[str, Any]] = []
    for template in presets:
        if template.kind != "template":
            continue
        for item in template_sequence(template):
            ref_id = str(item.get("preset_id") or "")
            ref_kind = str(item.get("kind") or "")
            if ref_kind == "caption":
                ref_kind = "caption_style"
            referenced = by_id.get(ref_id)
            if referenced is None:
                issues.append({
                    "template_id": template.id,
                    "preset_id": ref_id,
                    "kind": ref_kind,
                    "problem": "missing",
                })
                continue
            if ref_kind and referenced.kind != ref_kind:
                issues.append({
                    "template_id": template.id,
                    "preset_id": ref_id,
                    "kind": ref_kind,
                    "actual_kind": referenced.kind,
                    "problem": "kind_mismatch",
                })
    return issues


def preset_ecosystem_report(extra_paths: Iterable[Path | str] = ()) -> dict[str, Any]:
    """Audit built-in/external preset coverage for product-readiness checks."""
    presets = load_editor_presets(extra_paths)
    summary = preset_library_summary(extra_paths)
    by_kind = dict(summary.get("by_kind", {}) or {})
    kind_targets: dict[str, dict[str, int | bool]] = {}
    issues: list[dict[str, Any]] = []
    for kind, target in PRESET_ECOSYSTEM_KIND_TARGETS.items():
        count = int(by_kind.get(kind, 0) or 0)
        missing = max(0, int(target) - count)
        kind_targets[kind] = {
            "count": count,
            "target": int(target),
            "missing": missing,
            "ok": missing <= 0,
        }
        if missing:
            issues.append({
                "area": "preset_template_ecosystem",
                "severity": "medium" if missing >= 3 else "low",
                "message": f"Preset library is short on {kind} presets.",
                "action": "Add more production-ready presets for the missing category.",
                "kind": kind,
                "count": count,
                "target": int(target),
                "missing": missing,
            })

    topic_coverage: dict[str, dict[str, Any]] = {}
    for topic, required_kinds in PRESET_ECOSYSTEM_TOPIC_REQUIREMENTS.items():
        rows: dict[str, list[str]] = {}
        for kind in required_kinds:
            rows[kind] = [
                preset.id
                for preset in presets
                if preset.kind == kind and _preset_matches_topic(preset, topic)
            ]
        missing_kinds = [kind for kind, ids in rows.items() if not ids]
        topic_coverage[topic] = {
            "ok": not missing_kinds,
            "missing_kinds": missing_kinds,
            "by_kind": {kind: ids[:8] for kind, ids in rows.items()},
        }
        if missing_kinds:
            issues.append({
                "area": "preset_template_ecosystem",
                "severity": "low",
                "message": f"Preset ecosystem has weak {topic} coverage.",
                "action": "Add presets so the topic has templates plus matching effects, titles, audio, and motion/caption helpers.",
                "topic": topic,
                "missing_kinds": missing_kinds,
            })

    reference_issues = _template_reference_issues(presets)
    if reference_issues:
        issues.append({
            "area": "preset_template_ecosystem",
            "severity": "high",
            "message": "Some template presets reference missing or mismatched child presets.",
            "action": "Fix template sequence preset ids before shipping the preset pack.",
            "reference_issue_count": len(reference_issues),
        })

    one_click_plans: dict[str, list[str]] = {}
    weak_plans: list[str] = []
    for topic, summary_payload in _ONE_CLICK_TOPIC_SUMMARIES.items():
        ids = [preset.id for preset in one_click_preset_plan(summary_payload)]
        one_click_plans[topic] = ids
        if not any(preset_id.startswith("template-") for preset_id in ids):
            weak_plans.append(topic)
    if weak_plans:
        issues.append({
            "area": "preset_template_ecosystem",
            "severity": "medium",
            "message": "Some one-click plans do not start from a template preset.",
            "action": "Route each major content topic through a template-first one-click plan.",
            "topics": weak_plans,
        })

    score = 100
    for issue in issues:
        severity = str(issue.get("severity") or "")
        if severity == "high":
            score -= 18
        elif severity == "medium":
            score -= 8
        else:
            score -= 3
    return {
        "ok": not any(issue.get("severity") == "high" for issue in issues) and score >= 80,
        "score": max(0, min(100, score)),
        "summary": summary,
        "kind_targets": kind_targets,
        "topic_coverage": topic_coverage,
        "template_reference_issues": reference_issues,
        "one_click_plans": one_click_plans,
        "issues": issues,
    }
