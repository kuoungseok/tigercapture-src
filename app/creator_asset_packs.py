"""Local creator asset-pack catalog.

CapCut-like products feel fast because stickers, backgrounds, SFX cues, and
short loops are always nearby.  TigerCapture remains local-first, so this module
defines a deterministic local asset-pack contract that can later be backed by
real packaged files or user/imported packs.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CreatorAsset:
    id: str
    kind: str
    name: str
    tags: tuple[str, ...]
    license_id: str
    source: str
    payload: Mapping[str, Any]
    preview: Mapping[str, Any]


BUILTIN_CREATOR_ASSETS: tuple[CreatorAsset, ...] = (
    CreatorAsset(
        "sticker-save-burst",
        "sticker",
        "Save Burst",
        ("capcut", "sticker", "cta", "short-form", "save"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "burst", "text": "SAVE", "color": "#FF6F61", "animation": "pulse-pop"},
        {"swatch": "#FF6F61", "icon": "spark"},
    ),
    CreatorAsset(
        "sticker-follow-pill",
        "sticker",
        "Follow Pill",
        ("capcut", "sticker", "cta", "follow", "social"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "pill", "text": "FOLLOW", "color": "#7C5CFF", "animation": "bounce"},
        {"swatch": "#7C5CFF", "icon": "plus"},
    ),
    CreatorAsset(
        "sticker-tap-target",
        "sticker",
        "Tap Target",
        ("capcut", "sticker", "tap", "cursor", "tutorial"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "ring", "text": "TAP", "color": "#5BE7D1", "animation": "ripple"},
        {"swatch": "#5BE7D1", "icon": "target"},
    ),
    CreatorAsset(
        "sticker-wow-pop",
        "sticker",
        "Wow Pop",
        ("capcut", "sticker", "reaction", "short-form", "meme"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "bubble", "text": "WOW", "color": "#FFD45A", "animation": "squash"},
        {"swatch": "#FFD45A", "icon": "star"},
    ),
    CreatorAsset(
        "sticker-hotkey-keycap",
        "sticker",
        "Hotkey Keycap",
        ("capcut", "sticker", "hotkey", "tutorial", "keyboard"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "keycap", "text": "CTRL K", "color": "#292F45", "animation": "press"},
        {"swatch": "#292F45", "icon": "key"},
    ),
    CreatorAsset(
        "sticker-product-tag",
        "sticker",
        "Product Tag",
        ("capcut", "sticker", "product", "commerce", "label"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "price_tag", "text": "NEW", "color": "#FF8B5A", "animation": "slide-in"},
        {"swatch": "#FF8B5A", "icon": "tag"},
    ),
    CreatorAsset(
        "background-neon-glass",
        "background",
        "Neon Glass",
        ("capcut", "background", "gradient", "glass", "short-form"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "gradient", "colors": ["#13152B", "#7C5CFF", "#5BE7D1"], "blur": 0.34},
        {"swatch": "#7C5CFF", "icon": "gradient"},
    ),
    CreatorAsset(
        "background-warm-product",
        "background",
        "Warm Product",
        ("capcut", "background", "product", "commerce", "warm"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "radial", "colors": ["#FF8B5A", "#FFD45A", "#1B1D2F"], "vignette": 0.18},
        {"swatch": "#FF8B5A", "icon": "gradient"},
    ),
    CreatorAsset(
        "background-clean-tutorial",
        "background",
        "Clean Tutorial",
        ("capcut", "background", "tutorial", "screen-recording", "clean"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "linear", "colors": ["#0F1324", "#263453", "#2F79FF"], "blur": 0.20},
        {"swatch": "#2F79FF", "icon": "panel"},
    ),
    CreatorAsset(
        "background-soft-caption",
        "background",
        "Soft Caption",
        ("capcut", "background", "caption", "readability", "vertical"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "linear", "colors": ["#101320", "#423166", "#D94F90"], "safe_caption_band": True},
        {"swatch": "#D94F90", "icon": "subtitle"},
    ),
    CreatorAsset(
        "background-gameplay-energy",
        "background",
        "Gameplay Energy",
        ("capcut", "background", "gameplay", "energy", "short-form"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "mesh", "colors": ["#11131C", "#4F7BFF", "#FFDD55"], "speed": 0.35},
        {"swatch": "#4F7BFF", "icon": "bolt"},
    ),
    CreatorAsset(
        "background-podcast-depth",
        "background",
        "Podcast Depth",
        ("capcut", "background", "podcast", "voice", "chapter"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "blurred-panel", "colors": ["#171A2C", "#2D3359"], "grain": 0.05},
        {"swatch": "#2D3359", "icon": "mic"},
    ),
    CreatorAsset(
        "sfx-pop-soft",
        "sfx",
        "Soft Pop",
        ("capcut", "sfx", "pop", "caption", "short-form"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "short soft sine pop", "duration_ms": 180, "gain_db": -8.0},
        {"swatch": "#FFD45A", "icon": "sound"},
    ),
    CreatorAsset(
        "sfx-click-bright",
        "sfx",
        "Bright Click",
        ("capcut", "sfx", "click", "cursor", "tutorial"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "bright cursor click", "duration_ms": 90, "gain_db": -10.0},
        {"swatch": "#5BE7D1", "icon": "cursor"},
    ),
    CreatorAsset(
        "sfx-whoosh-feed",
        "sfx",
        "Feed Whoosh",
        ("capcut", "sfx", "whoosh", "transition", "vertical"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "quick upward whoosh", "duration_ms": 320, "gain_db": -7.0},
        {"swatch": "#7C5CFF", "icon": "arrow-up"},
    ),
    CreatorAsset(
        "sfx-sparkle-hit",
        "sfx",
        "Sparkle Hit",
        ("capcut", "sfx", "sparkle", "reveal", "product"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "tiny sparkle hit", "duration_ms": 420, "gain_db": -9.0},
        {"swatch": "#FF9FD2", "icon": "spark"},
    ),
    CreatorAsset(
        "loop-tutorial-pulse",
        "loop",
        "Tutorial Pulse",
        ("capcut", "loop", "music", "tutorial", "voice-bed"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "subtle tutorial pulse bed", "bpm": 92, "duration_ms": 8000, "gain_db": -18.0},
        {"swatch": "#2F79FF", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-short-energy",
        "loop",
        "Short Energy",
        ("capcut", "loop", "music", "short-form", "upbeat"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "short upbeat social loop", "bpm": 126, "duration_ms": 8000, "gain_db": -17.0},
        {"swatch": "#FF6F61", "icon": "wave"},
    ),
    CreatorAsset(
        "sticker-ai-magic-badge",
        "sticker",
        "AI Magic Badge",
        ("capcut", "sticker", "ai", "magic", "creator", "one-click"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "spark_badge", "text": "AI", "color": "#8A7CFF", "animation": "spark-pop"},
        {"swatch": "#8A7CFF", "icon": "spark"},
    ),
    CreatorAsset(
        "sticker-pro-con-toggle",
        "sticker",
        "Pro Con Toggle",
        ("capcut", "sticker", "review", "product", "pro-con"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "segmented", "text": "PRO / CON", "color": "#5BE7D1", "animation": "switch"},
        {"swatch": "#5BE7D1", "icon": "toggle"},
    ),
    CreatorAsset(
        "sticker-chapter-spark",
        "sticker",
        "Chapter Spark",
        ("capcut", "sticker", "podcast", "chapter", "dialogue"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "chapter_dot", "text": "01", "color": "#6EA8FF", "animation": "slide-pop"},
        {"swatch": "#6EA8FF", "icon": "chapter"},
    ),
    CreatorAsset(
        "sticker-rank-medal",
        "sticker",
        "Rank Medal",
        ("capcut", "sticker", "ranking", "listicle", "countdown"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "medal", "text": "#1", "color": "#FFD45A", "animation": "drop-bounce"},
        {"swatch": "#FFD45A", "icon": "medal"},
    ),
    CreatorAsset(
        "sticker-caption-arrow",
        "sticker",
        "Caption Arrow",
        ("capcut", "sticker", "caption", "callout", "tutorial"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "arrow_label", "text": "LOOK", "color": "#FF7A59", "animation": "nudge"},
        {"swatch": "#FF7A59", "icon": "arrow"},
    ),
    CreatorAsset(
        "sticker-live-bubble",
        "sticker",
        "Live Bubble",
        ("capcut", "sticker", "stream", "live", "gameplay"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "live_pill", "text": "LIVE", "color": "#FF4F7B", "animation": "pulse"},
        {"swatch": "#FF4F7B", "icon": "broadcast"},
    ),
    CreatorAsset(
        "background-ios-panel",
        "background",
        "iOS Control Panel",
        ("capcut", "background", "screen-recording", "ios", "glass"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "glass-grid", "colors": ["#101424", "#253456", "#8A7CFF"], "blur": 0.42, "panel_glow": True},
        {"swatch": "#8A7CFF", "icon": "panel"},
    ),
    CreatorAsset(
        "background-candy-wallpaper",
        "background",
        "Candy Wallpaper",
        ("capcut", "background", "wallpaper", "screenstudio", "gradient"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "mesh", "colors": ["#FF7A59", "#F7CF5C", "#4DD3FF", "#A576FF"], "blur": 0.38},
        {"swatch": "#FF7A59", "icon": "palette"},
    ),
    CreatorAsset(
        "background-clean-whiteboard",
        "background",
        "Clean Whiteboard",
        ("capcut", "background", "education", "tutorial", "clean"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "linear", "colors": ["#F5F7FF", "#DDE7FF", "#BFD3FF"], "dark_text_safe": True},
        {"swatch": "#DDE7FF", "icon": "board"},
    ),
    CreatorAsset(
        "background-review-table",
        "background",
        "Review Table",
        ("capcut", "background", "review", "product", "comparison"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "split", "colors": ["#141827", "#222B44", "#FFDD55"], "comparison_grid": True},
        {"swatch": "#222B44", "icon": "compare"},
    ),
    CreatorAsset(
        "background-news-blueprint",
        "background",
        "News Blueprint",
        ("capcut", "background", "news", "editorial", "documentary"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "linear", "colors": ["#0D1324", "#1D3B64", "#6EA8FF"], "lower_third_safe": True},
        {"swatch": "#1D3B64", "icon": "news"},
    ),
    CreatorAsset(
        "background-anime-stage",
        "background",
        "Anime Stage",
        ("capcut", "background", "anime", "spine", "live2d", "character"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "radial", "colors": ["#1A1630", "#6B4DFF", "#FF9FD2"], "character_safe": True},
        {"swatch": "#6B4DFF", "icon": "actor"},
    ),
    CreatorAsset(
        "sfx-caption-pop-bright",
        "sfx",
        "Caption Pop Bright",
        ("capcut", "sfx", "caption", "pop", "word-pop"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "bright caption tick pop", "duration_ms": 120, "gain_db": -9.0},
        {"swatch": "#FFDD55", "icon": "sound"},
    ),
    CreatorAsset(
        "sfx-ui-confirm",
        "sfx",
        "UI Confirm",
        ("capcut", "sfx", "ui", "confirm", "tutorial"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "clean ui confirm blip", "duration_ms": 160, "gain_db": -11.0},
        {"swatch": "#5BE7D1", "icon": "check"},
    ),
    CreatorAsset(
        "sfx-ranking-hit",
        "sfx",
        "Ranking Hit",
        ("capcut", "sfx", "ranking", "impact", "countdown"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "short medal impact hit", "duration_ms": 260, "gain_db": -8.5},
        {"swatch": "#FFD45A", "icon": "medal"},
    ),
    CreatorAsset(
        "sfx-glass-open",
        "sfx",
        "Glass Open",
        ("capcut", "sfx", "screenstudio", "panel", "open"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "soft glass panel open", "duration_ms": 260, "gain_db": -10.0},
        {"swatch": "#8A7CFF", "icon": "panel"},
    ),
    CreatorAsset(
        "sfx-sticker-boing",
        "sfx",
        "Sticker Boing",
        ("capcut", "sfx", "sticker", "bounce", "reaction"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "tiny sticker boing", "duration_ms": 300, "gain_db": -9.5},
        {"swatch": "#FF9FD2", "icon": "spring"},
    ),
    CreatorAsset(
        "sfx-voice-clean-toggle",
        "sfx",
        "Voice Clean Toggle",
        ("capcut", "sfx", "voice", "dialogue", "cleanup"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "subtle voice clean switch", "duration_ms": 180, "gain_db": -12.0},
        {"swatch": "#64D980", "icon": "mic"},
    ),
    CreatorAsset(
        "loop-podcast-soft-bed",
        "loop",
        "Podcast Soft Bed",
        ("capcut", "loop", "music", "podcast", "dialogue", "voice-bed"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "soft podcast bed", "bpm": 84, "duration_ms": 12000, "gain_db": -20.0},
        {"swatch": "#6EA8FF", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-product-clean",
        "loop",
        "Product Clean",
        ("capcut", "loop", "music", "product", "commercial"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "clean product demo loop", "bpm": 104, "duration_ms": 10000, "gain_db": -18.5},
        {"swatch": "#FF8B5A", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-gameplay-drive",
        "loop",
        "Gameplay Drive",
        ("capcut", "loop", "music", "gameplay", "stream", "energy"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "energetic gameplay drive loop", "bpm": 132, "duration_ms": 10000, "gain_db": -17.5},
        {"swatch": "#4F7BFF", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-lofi-study",
        "loop",
        "Lofi Study",
        ("capcut", "loop", "music", "education", "tutorial", "calm"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "lofi study tutorial bed", "bpm": 78, "duration_ms": 12000, "gain_db": -19.0},
        {"swatch": "#BFD3FF", "icon": "wave"},
    ),
    CreatorAsset(
        "sticker-subscribe-bell",
        "sticker",
        "Subscribe Bell",
        ("capcut", "sticker", "subscribe", "cta", "vlog"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "bell_badge", "text": "SUB", "color": "#FF6F61", "animation": "ring-pop"},
        {"swatch": "#FF6F61", "icon": "bell"},
    ),
    CreatorAsset(
        "sticker-reaction-fire",
        "sticker",
        "Reaction Fire",
        ("capcut", "sticker", "meme", "reaction", "fire"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "flame_burst", "text": "HOT", "color": "#FF8B5A", "animation": "flicker-pop"},
        {"swatch": "#FF8B5A", "icon": "flame"},
    ),
    CreatorAsset(
        "sticker-before-after-label",
        "sticker",
        "Before After Label",
        ("capcut", "sticker", "beauty", "before-after", "comparison"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "split_label", "text": "BEFORE / AFTER", "color": "#FF9FD2", "animation": "wipe"},
        {"swatch": "#FF9FD2", "icon": "compare"},
    ),
    CreatorAsset(
        "sticker-price-drop",
        "sticker",
        "Price Drop",
        ("capcut", "sticker", "commerce", "product", "deal"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"shape": "deal_tag", "text": "SALE", "color": "#FFD45A", "animation": "drop-bounce"},
        {"swatch": "#FFD45A", "icon": "tag"},
    ),
    CreatorAsset(
        "background-stream-neon",
        "background",
        "Stream Neon",
        ("capcut", "background", "stream", "gameplay", "neon"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "mesh", "colors": ["#080B17", "#2F79FF", "#7C5CFF", "#5BE7D1"], "chat_safe": True},
        {"swatch": "#2F79FF", "icon": "broadcast"},
    ),
    CreatorAsset(
        "background-food-pop",
        "background",
        "Food Pop",
        ("capcut", "background", "food", "review", "warm"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "radial", "colors": ["#FF8B5A", "#FFD45A", "#FFF2D6"], "plate_safe": True},
        {"swatch": "#FFD45A", "icon": "spark"},
    ),
    CreatorAsset(
        "background-fitness-energy",
        "background",
        "Fitness Energy",
        ("capcut", "background", "fitness", "challenge", "energy"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "linear", "colors": ["#101320", "#37D6C6", "#6EA8FF"], "timer_safe": True},
        {"swatch": "#37D6C6", "icon": "bolt"},
    ),
    CreatorAsset(
        "background-beauty-soft",
        "background",
        "Beauty Soft",
        ("capcut", "background", "beauty", "fashion", "soft"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"type": "mesh", "colors": ["#1A1425", "#FF9FD2", "#A576FF", "#F7CF5C"], "skin_tone_safe": True},
        {"swatch": "#FF9FD2", "icon": "palette"},
    ),
    CreatorAsset(
        "sfx-swipe-tick",
        "sfx",
        "Swipe Tick",
        ("capcut", "sfx", "swipe", "transition", "short-form"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "tight swipe tick", "duration_ms": 140, "gain_db": -9.0},
        {"swatch": "#6EA8FF", "icon": "arrow"},
    ),
    CreatorAsset(
        "sfx-like-chime",
        "sfx",
        "Like Chime",
        ("capcut", "sfx", "like", "social", "cta"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "soft like chime", "duration_ms": 420, "gain_db": -10.5},
        {"swatch": "#FF9FD2", "icon": "heart"},
    ),
    CreatorAsset(
        "sfx-glitch-tap",
        "sfx",
        "Glitch Tap",
        ("capcut", "sfx", "glitch", "meme", "gameplay"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "tiny glitch tap", "duration_ms": 220, "gain_db": -8.5},
        {"swatch": "#7C5CFF", "icon": "glitch"},
    ),
    CreatorAsset(
        "sfx-camera-shutter",
        "sfx",
        "Camera Shutter",
        ("capcut", "sfx", "beauty", "fashion", "photo"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "clean camera shutter", "duration_ms": 180, "gain_db": -8.0},
        {"swatch": "#FF9FD2", "icon": "camera"},
    ),
    CreatorAsset(
        "sfx-countdown-beep",
        "sfx",
        "Countdown Beep",
        ("capcut", "sfx", "fitness", "countdown", "challenge"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "short countdown beep", "duration_ms": 160, "gain_db": -9.0},
        {"swatch": "#37D6C6", "icon": "timer"},
    ),
    CreatorAsset(
        "sfx-success-rise",
        "sfx",
        "Success Rise",
        ("capcut", "sfx", "product", "reveal", "success"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "small success rise", "duration_ms": 520, "gain_db": -10.0},
        {"swatch": "#64D980", "icon": "check"},
    ),
    CreatorAsset(
        "loop-fashion-pop",
        "loop",
        "Fashion Pop",
        ("capcut", "loop", "music", "fashion", "beauty", "upbeat"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "glossy fashion pop loop", "bpm": 116, "duration_ms": 10000, "gain_db": -18.0},
        {"swatch": "#FF9FD2", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-tech-review",
        "loop",
        "Tech Review",
        ("capcut", "loop", "music", "tech", "product", "review"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "clean tech review pulse", "bpm": 98, "duration_ms": 12000, "gain_db": -18.5},
        {"swatch": "#5BE7D1", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-vlog-warm",
        "loop",
        "Vlog Warm",
        ("capcut", "loop", "music", "vlog", "daily", "warm"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "warm vlog bed", "bpm": 88, "duration_ms": 12000, "gain_db": -19.0},
        {"swatch": "#FFD45A", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-meme-bounce",
        "loop",
        "Meme Bounce",
        ("capcut", "loop", "music", "meme", "reaction", "bounce"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "playful meme bounce loop", "bpm": 128, "duration_ms": 8000, "gain_db": -17.5},
        {"swatch": "#FF8B5A", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-news-tension",
        "loop",
        "News Tension",
        ("capcut", "loop", "music", "news", "documentary", "tension"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "light editorial tension loop", "bpm": 90, "duration_ms": 12000, "gain_db": -20.0},
        {"swatch": "#6EA8FF", "icon": "wave"},
    ),
    CreatorAsset(
        "loop-fitness-drive",
        "loop",
        "Fitness Drive",
        ("capcut", "loop", "music", "fitness", "challenge", "energy"),
        "tigercapture-built-in-generated",
        "builtin_generated",
        {"synthesis_hint": "energetic fitness drive loop", "bpm": 136, "duration_ms": 10000, "gain_db": -17.0},
        {"swatch": "#37D6C6", "icon": "wave"},
    ),
)


CREATOR_ASSET_KIND_TARGETS: dict[str, int] = {
    "sticker": 26,
    "background": 26,
    "sfx": 26,
    "loop": 22,
}


CREATOR_ASSET_SERIES: tuple[dict[str, Any], ...] = (
    {"id": "travel", "name": "Travel", "tags": ("travel", "vlog", "landscape"), "color": "#56C7FF", "icon": "map"},
    {"id": "finance", "name": "Finance", "tags": ("finance", "money", "tips"), "color": "#64D980", "icon": "chart"},
    {"id": "anime", "name": "Anime", "tags": ("anime", "actor", "reaction"), "color": "#B67CFF", "icon": "spark"},
    {"id": "food", "name": "Food", "tags": ("food", "recipe", "product"), "color": "#FFB84D", "icon": "plate"},
    {"id": "real-estate", "name": "Real Estate", "tags": ("real-estate", "tour", "property"), "color": "#6EA8FF", "icon": "home"},
    {"id": "education", "name": "Education", "tags": ("education", "tutorial", "lesson"), "color": "#5BE7D1", "icon": "book"},
    {"id": "fitness-boost", "name": "Fitness Boost", "tags": ("fitness", "challenge", "routine"), "color": "#37D6C6", "icon": "timer"},
    {"id": "news-brief", "name": "News Brief", "tags": ("news", "documentary", "brief"), "color": "#8DA2FF", "icon": "caption"},
    {"id": "beauty-glow", "name": "Beauty Glow", "tags": ("beauty", "fashion", "camera"), "color": "#FF9FD2", "icon": "camera"},
    {"id": "gameplay-clutch", "name": "Gameplay Clutch", "tags": ("gameplay", "stream", "highlight"), "color": "#FF7A59", "icon": "bolt"},
)


def _generated_creator_asset_extensions() -> tuple[CreatorAsset, ...]:
    assets: list[CreatorAsset] = []
    for row in CREATOR_ASSET_SERIES:
        slug = str(row["id"])
        label = str(row["name"])
        tags = tuple(str(tag) for tag in row["tags"])
        color = str(row["color"])
        icon = str(row["icon"])
        assets.extend(
            [
                CreatorAsset(
                    f"sticker-{slug}-hook",
                    "sticker",
                    f"{label} Hook",
                    ("capcut", "sticker", "hook", "short-form", *tags),
                    "tigercapture-built-in-generated",
                    "builtin_generated",
                    {"shape": "rounded_badge", "text": label.upper()[:12], "color": color, "animation": "pop-slide"},
                    {"swatch": color, "icon": icon},
                ),
                CreatorAsset(
                    f"background-{slug}-wash",
                    "background",
                    f"{label} Wash",
                    ("capcut", "background", "gradient", "vertical", *tags),
                    "tigercapture-built-in-generated",
                    "builtin_generated",
                    {"type": "mesh", "colors": ["#101320", color, "#242A45"], "blur": 0.24, "grain": 0.04},
                    {"swatch": color, "icon": "gradient"},
                ),
                CreatorAsset(
                    f"sfx-{slug}-accent",
                    "sfx",
                    f"{label} Accent",
                    ("capcut", "sfx", "accent", "short-form", *tags),
                    "tigercapture-built-in-generated",
                    "builtin_generated",
                    {"synthesis_hint": f"short {label.casefold()} creator accent", "duration_ms": 260, "gain_db": -9.0},
                    {"swatch": color, "icon": "sound"},
                ),
                CreatorAsset(
                    f"loop-{slug}-bed",
                    "loop",
                    f"{label} Bed",
                    ("capcut", "loop", "music", "voice-bed", *tags),
                    "tigercapture-built-in-generated",
                    "builtin_generated",
                    {"synthesis_hint": f"{label.casefold()} creator music bed", "bpm": 104, "duration_ms": 10000, "gain_db": -18.5},
                    {"swatch": color, "icon": "wave"},
                ),
            ]
        )
    return tuple(assets)


def _normalized(text: str) -> str:
    out = str(text or "").casefold()
    for ch in ("-", "_", "/", "\\", ":", "|", "(", ")", "[", "]"):
        out = out.replace(ch, " ")
    return " ".join(out.split())


def _asset_from_mapping(row: Mapping[str, Any]) -> CreatorAsset | None:
    try:
        asset_id = str(row.get("id") or "").strip()
        kind = str(row.get("kind") or "").strip()
        name = str(row.get("name") or asset_id).strip()
        if not asset_id or not kind or not name:
            return None
        tags = tuple(str(tag).strip() for tag in row.get("tags", []) if str(tag).strip())
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        preview = row.get("preview") if isinstance(row.get("preview"), dict) else {}
        return CreatorAsset(
            id=asset_id,
            kind=kind,
            name=name,
            tags=tags,
            license_id=str(row.get("license_id") or "unknown"),
            source=str(row.get("source") or "external_pack"),
            payload=payload,
            preview=preview,
        )
    except Exception:
        return None


def load_creator_asset_pack(path: Path | str) -> list[CreatorAsset]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return []
    rows: Iterable[Any]
    if isinstance(payload, dict):
        rows = payload.get("assets", [])
    else:
        rows = payload if isinstance(payload, list) else []
    assets: list[CreatorAsset] = []
    for row in rows:
        if isinstance(row, dict):
            asset = _asset_from_mapping(row)
            if asset is not None:
                assets.append(asset)
    return assets


def creator_asset_catalog(extra_paths: Iterable[Path | str] = ()) -> list[CreatorAsset]:
    assets = list(BUILTIN_CREATOR_ASSETS) + list(_generated_creator_asset_extensions())
    seen = {asset.id for asset in assets}
    for path in extra_paths:
        for asset in load_creator_asset_pack(path):
            if asset.id not in seen:
                assets.append(asset)
                seen.add(asset.id)
    return assets


def search_creator_assets(
    query: str,
    *,
    kind: str | None = None,
    extra_paths: Iterable[Path | str] = (),
    limit: int = 20,
) -> list[dict[str, Any]]:
    query_tokens = set(_normalized(query).split())
    kind_norm = _normalized(kind or "")
    matches: list[tuple[int, CreatorAsset]] = []
    curated_ids = {asset.id for asset in BUILTIN_CREATOR_ASSETS}
    for asset in creator_asset_catalog(extra_paths):
        if kind_norm and _normalized(asset.kind) != kind_norm:
            continue
        haystack = _normalized(" ".join([asset.id, asset.kind, asset.name, *asset.tags]))
        if not query_tokens:
            score = 1
        else:
            score = sum(1 for token in query_tokens if token in haystack)
        if score:
            matches.append((score, asset))
    matches.sort(key=lambda item: (-item[0], 0 if item[1].id in curated_ids else 1, item[1].kind, item[1].name))
    return [asdict(asset) for _score, asset in matches[: max(1, int(limit))]]


def creator_asset_preview_storyboard(asset: CreatorAsset | Mapping[str, Any]) -> dict[str, Any]:
    """Return small preview metadata for asset browsers and QA.

    The preview remains synthetic/local: it describes how the asset should be
    represented in a card, hover popover, or A/B preview without requiring a
    packaged bitmap/audio file.
    """
    if isinstance(asset, CreatorAsset):
        row = asdict(asset)
    else:
        row = dict(asset)
    kind = str(row.get("kind") or "asset")
    payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
    preview = row.get("preview") if isinstance(row.get("preview"), dict) else {}
    tags = [str(tag) for tag in row.get("tags", []) if str(tag)]
    cues: list[str] = []
    timeline_usage = "overlay"
    if kind == "sticker":
        cues = [str(payload.get("shape") or "sticker"), str(payload.get("animation") or "pop")]
        timeline_usage = "sticker_overlay"
    elif kind == "background":
        cues = [str(payload.get("type") or "background"), "wallpaper_palette"]
        timeline_usage = "canvas_background"
    elif kind == "sfx":
        cues = [str(payload.get("synthesis_hint") or "sfx"), f"{int(payload.get('duration_ms', 0) or 0)}ms"]
        timeline_usage = "audio_hit"
    elif kind == "loop":
        cues = [str(payload.get("synthesis_hint") or "loop"), f"{int(payload.get('bpm', 0) or 0)}bpm"]
        timeline_usage = "music_bed"
    return {
        "id": str(row.get("id") or ""),
        "kind": kind,
        "name": str(row.get("name") or row.get("id") or ""),
        "before_label": "Source",
        "after_label": str(row.get("name") or kind.title()),
        "accent": str(preview.get("swatch") or payload.get("color") or "#8A7CFF"),
        "icon": str(preview.get("icon") or kind),
        "cues": [cue for cue in cues if cue],
        "timeline_usage": timeline_usage,
        "intent_tags": tags[:6],
        "preview_ready": bool(preview.get("swatch") and preview.get("icon")),
        "local_generated": str(row.get("source") or "") == "builtin_generated",
    }


CREATOR_ASSET_INTENT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "tutorial": ("sticker", "background", "sfx", "loop"),
    "product": ("sticker", "background", "sfx", "loop"),
    "gameplay": ("sticker", "background", "loop"),
    "podcast": ("sticker", "background", "loop"),
    "caption": ("sticker", "background", "sfx"),
    "review": ("sticker", "background"),
    "screenstudio": ("background", "sfx"),
    "anime": ("background",),
    "meme": ("sticker", "sfx", "loop"),
    "beauty": ("sticker", "background", "sfx", "loop"),
    "fitness": ("background", "sfx", "loop"),
    "vlog": ("sticker", "loop"),
}


CREATOR_ASSET_COLLECTIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "tutorial-click-polish",
        "name": "Tutorial Click Polish",
        "intent": "tutorial",
        "tags": ("tutorial", "cursor", "screen-recording", "click"),
        "asset_ids": (
            "background-clean-tutorial",
            "sticker-tap-target",
            "sticker-hotkey-keycap",
            "sfx-click-bright",
            "sfx-ui-confirm",
            "loop-tutorial-pulse",
        ),
    },
    {
        "id": "product-review-clean",
        "name": "Product Review Clean",
        "intent": "product",
        "tags": ("product", "review", "commerce", "deal"),
        "asset_ids": (
            "background-warm-product",
            "background-review-table",
            "sticker-product-tag",
            "sticker-price-drop",
            "sfx-sparkle-hit",
            "sfx-success-rise",
            "loop-product-clean",
            "loop-tech-review",
        ),
    },
    {
        "id": "gameplay-stream-pop",
        "name": "Gameplay Stream Pop",
        "intent": "gameplay",
        "tags": ("gameplay", "stream", "reaction", "glitch"),
        "asset_ids": (
            "background-gameplay-energy",
            "background-stream-neon",
            "sticker-live-bubble",
            "sfx-glitch-tap",
            "loop-gameplay-drive",
        ),
    },
    {
        "id": "caption-word-pop",
        "name": "Caption Word Pop",
        "intent": "caption",
        "tags": ("caption", "word-pop", "subtitle", "readability"),
        "asset_ids": (
            "background-soft-caption",
            "sticker-caption-arrow",
            "sfx-caption-pop-bright",
            "sfx-pop-soft",
        ),
    },
    {
        "id": "screenstudio-wallpaper",
        "name": "Screen Studio Wallpaper",
        "intent": "screenstudio",
        "tags": ("screenstudio", "wallpaper", "panel", "glass"),
        "asset_ids": (
            "background-candy-wallpaper",
            "background-ios-panel",
            "sfx-glass-open",
            "sfx-swipe-tick",
        ),
    },
    {
        "id": "podcast-chapter-soft",
        "name": "Podcast Chapter Soft",
        "intent": "podcast",
        "tags": ("podcast", "dialogue", "chapter", "voice"),
        "asset_ids": (
            "background-podcast-depth",
            "sticker-chapter-spark",
            "sfx-voice-clean-toggle",
            "loop-podcast-soft-bed",
        ),
    },
    {
        "id": "beauty-before-after",
        "name": "Beauty Before After",
        "intent": "beauty",
        "tags": ("beauty", "fashion", "before-after", "photo"),
        "asset_ids": (
            "background-beauty-soft",
            "sticker-before-after-label",
            "sfx-camera-shutter",
            "loop-fashion-pop",
        ),
    },
    {
        "id": "fitness-challenge-drive",
        "name": "Fitness Challenge Drive",
        "intent": "fitness",
        "tags": ("fitness", "challenge", "countdown", "energy"),
        "asset_ids": (
            "background-fitness-energy",
            "sfx-countdown-beep",
            "loop-fitness-drive",
        ),
    },
    {
        "id": "meme-reaction-bounce",
        "name": "Meme Reaction Bounce",
        "intent": "meme",
        "tags": ("meme", "reaction", "fire", "bounce"),
        "asset_ids": (
            "sticker-reaction-fire",
            "sfx-sticker-boing",
            "sfx-glitch-tap",
            "loop-meme-bounce",
        ),
    },
    {
        "id": "vlog-warm-cta",
        "name": "Vlog Warm CTA",
        "intent": "vlog",
        "tags": ("vlog", "daily", "subscribe", "warm"),
        "asset_ids": (
            "sticker-subscribe-bell",
            "sfx-like-chime",
            "loop-vlog-warm",
        ),
    },
)


def creator_asset_intent_coverage(assets: Iterable[CreatorAsset]) -> dict[str, dict[str, Any]]:
    by_intent: dict[str, dict[str, list[str]]] = {}
    for intent, required_kinds in CREATOR_ASSET_INTENT_REQUIREMENTS.items():
        by_intent[intent] = {kind: [] for kind in required_kinds}
    for asset in assets:
        tags = {str(tag).casefold() for tag in asset.tags}
        text = _normalized(" ".join((asset.id, asset.name, asset.kind, *asset.tags)))
        for intent, required_kinds in CREATOR_ASSET_INTENT_REQUIREMENTS.items():
            if asset.kind not in required_kinds:
                continue
            if intent in tags or intent in text:
                by_intent[intent][asset.kind].append(asset.id)
    out: dict[str, dict[str, Any]] = {}
    for intent, rows in by_intent.items():
        missing = [kind for kind, ids in rows.items() if not ids]
        out[intent] = {
            "ok": not missing,
            "missing": missing,
            "by_kind": rows,
            "asset_count": sum(len(ids) for ids in rows.values()),
        }
    return out


def creator_asset_collection_shelves(assets: Iterable[CreatorAsset] | None = None) -> list[dict[str, Any]]:
    catalog = {asset.id: asset for asset in list(assets or creator_asset_catalog())}
    shelves: list[dict[str, Any]] = []
    for collection in CREATOR_ASSET_COLLECTIONS:
        ids = [str(asset_id) for asset_id in collection.get("asset_ids", [])]
        rows = [catalog[asset_id] for asset_id in ids if asset_id in catalog]
        missing = [asset_id for asset_id in ids if asset_id not in catalog]
        kind_counts: dict[str, int] = {}
        palette: list[str] = []
        drop_targets: list[str] = []
        for asset in rows:
            kind_counts[asset.kind] = kind_counts.get(asset.kind, 0) + 1
            swatch = str(asset.preview.get("swatch") or asset.payload.get("color") or "")
            if swatch and swatch not in palette:
                palette.append(swatch)
            storyboard = creator_asset_preview_storyboard(asset)
            target = str(storyboard.get("timeline_usage") or "")
            if target and target not in drop_targets:
                drop_targets.append(target)
        shelves.append({
            "id": str(collection.get("id") or ""),
            "name": str(collection.get("name") or collection.get("id") or ""),
            "intent": str(collection.get("intent") or ""),
            "tags": list(collection.get("tags", []) or []),
            "asset_ids": ids,
            "ready_asset_ids": [asset.id for asset in rows],
            "asset_count": len(rows),
            "missing": missing,
            "ready": not missing and bool(rows),
            "kind_counts": dict(sorted(kind_counts.items())),
            "palette": palette[:5],
            "drop_targets": drop_targets,
            "drag_payload": {
                "type": "creator_asset_collection",
                "collection_id": str(collection.get("id") or ""),
                "asset_ids": [asset.id for asset in rows],
                "intent": str(collection.get("intent") or ""),
            },
        })
    return shelves


def creator_asset_recommendation_board(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] = (),
    *,
    extra_paths: Iterable[Path | str] = (),
    limit: int = 8,
) -> dict[str, Any]:
    assets = creator_asset_catalog(extra_paths)
    shelves = creator_asset_collection_shelves(assets)
    text_parts: list[str] = []
    project = dict(project_summary or {})
    text_parts.extend(str(value) for value in project.values() if isinstance(value, (str, int, float, bool)))
    for segment in project.get("transcript_segments", []) or []:
        if isinstance(segment, Mapping):
            text_parts.append(str(segment.get("text") or ""))
    for item in media_items:
        if not isinstance(item, Mapping):
            continue
        text_parts.extend(str(item.get(key) or "") for key in ("name", "kind"))
        for key in ("tags", "object_tags", "dialogue"):
            values = item.get(key, [])
            if isinstance(values, (list, tuple, set)):
                text_parts.extend(str(value) for value in values)
            elif values:
                text_parts.append(str(values))
    query_text = _normalized(" ".join(text_parts))
    ranked: list[tuple[int, dict[str, Any]]] = []
    for shelf in shelves:
        tags = [str(tag) for tag in shelf.get("tags", [])]
        tokens = {_normalized(tag) for tag in tags if _normalized(tag)}
        tokens.add(_normalized(str(shelf.get("intent") or "")))
        score = sum(4 for token in tokens if token and token in query_text)
        if shelf.get("ready"):
            score += 8
        score += min(6, int(shelf.get("asset_count", 0) or 0))
        ranked.append((score, shelf))
    ranked.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    cards = []
    for score, shelf in ranked[: max(1, int(limit))]:
        cards.append({
            "id": shelf["id"],
            "name": shelf["name"],
            "intent": shelf["intent"],
            "score": score,
            "ready": bool(shelf.get("ready")),
            "asset_count": int(shelf.get("asset_count", 0) or 0),
            "palette": list(shelf.get("palette", []) or []),
            "drop_targets": list(shelf.get("drop_targets", []) or []),
            "drag_payload": dict(shelf.get("drag_payload", {}) or {}),
            "reason": "matched_project_context" if score > int(shelf.get("asset_count", 0) or 0) + 8 else "starter_pack",
        })
    return {
        "kind": "creator_asset_recommendation_board",
        "ok": bool(cards) and all(bool(card.get("ready")) for card in cards[:3]),
        "query": query_text,
        "cards": cards,
        "card_count": len(cards),
        "collection_count": len(shelves),
        "ready_collection_count": sum(1 for shelf in shelves if shelf.get("ready")),
        "primary_collection_id": cards[0]["id"] if cards else "",
        "local_first": True,
        "cloud_required": False,
    }


def creator_asset_pack_report(extra_paths: Iterable[Path | str] = ()) -> dict[str, Any]:
    assets = creator_asset_catalog(extra_paths)
    by_kind: dict[str, int] = {}
    licenses: dict[str, int] = {}
    for asset in assets:
        by_kind[asset.kind] = by_kind.get(asset.kind, 0) + 1
        licenses[asset.license_id] = licenses.get(asset.license_id, 0) + 1

    targets: dict[str, dict[str, Any]] = {}
    issues: list[dict[str, Any]] = []
    for kind, target in CREATOR_ASSET_KIND_TARGETS.items():
        count = int(by_kind.get(kind, 0) or 0)
        missing = max(0, int(target) - count)
        targets[kind] = {"count": count, "target": int(target), "missing": missing, "ok": missing == 0}
        if missing:
            issues.append({
                "kind": kind,
                "severity": "medium",
                "message": f"Creator asset pack is short on {kind} assets.",
                "action": f"Add at least {missing} more licensed/generated {kind} asset(s).",
            })
    license_ok = all(asset.license_id and asset.license_id != "unknown" for asset in assets)
    if not license_ok:
        issues.append({
            "kind": "license",
            "severity": "high",
            "message": "One or more creator assets have missing license metadata.",
            "action": "Attach explicit license_id before shipping asset packs.",
        })
    target_score = sum(100 if row["ok"] else max(40, int(100 * row["count"] / max(1, row["target"]))) for row in targets.values())
    score = round(target_score / max(1, len(targets)), 2)
    if not license_ok:
        score = min(score, 70.0)
    storyboards = [creator_asset_preview_storyboard(asset) for asset in assets]
    preview_ready_count = sum(1 for row in storyboards if row.get("preview_ready"))
    intent_coverage = creator_asset_intent_coverage(assets)
    collection_shelves = creator_asset_collection_shelves(assets)
    ready_collection_count = sum(1 for row in collection_shelves if row.get("ready"))
    recommendation_board = creator_asset_recommendation_board(
        {
            "duration_s": 64,
            "screen_recording": True,
            "dialogue": True,
            "transcript_segments": [
                {"text": "Show the product shortcut, add captions, and make the click easy to follow."},
            ],
        },
        [
            {
                "name": "product tutorial screen recording.mp4",
                "kind": "video",
                "tags": ["tutorial", "product", "screen-recording"],
                "object_tags": ["cursor", "button"],
            }
        ],
        extra_paths=extra_paths,
    )
    missing_intents = [intent for intent, row in intent_coverage.items() if not row.get("ok")]
    if missing_intents:
        issues.append({
            "kind": "intent_coverage",
            "severity": "medium",
            "message": "One or more creator intents lack a complete local asset set.",
            "action": "Add generated starter assets for: " + ", ".join(missing_intents),
        })
        score = min(score, 88.0)
    if ready_collection_count < len(CREATOR_ASSET_COLLECTIONS):
        issues.append({
            "kind": "collection_shelves",
            "severity": "medium",
            "message": "One or more creator asset shelves are missing local assets.",
            "action": "Fill every collection so creator recommendations never lead to empty shelves.",
        })
        score = min(score, 90.0)
    if not recommendation_board.get("ok"):
        issues.append({
            "kind": "recommendation_board",
            "severity": "medium",
            "message": "Creator asset recommendation board is not ready.",
            "action": "Keep at least three ready local-first recommendation cards available.",
        })
        score = min(score, 90.0)
    return {
        "kind": "creator_asset_packs",
        "ok": not issues,
        "score": score,
        "summary": {
            "assets": len(assets),
            "licenses": len(licenses),
            "kinds": len(by_kind),
            "built_in_assets": sum(1 for asset in assets if asset.source == "builtin_generated"),
            "generated_extension_assets": len(_generated_creator_asset_extensions()),
            "preview_storyboards": len(storyboards),
            "preview_ready_assets": preview_ready_count,
            "covered_intents": sum(1 for row in intent_coverage.values() if row.get("ok")),
            "intent_count": len(intent_coverage),
            "collection_shelves": len(collection_shelves),
            "ready_collection_shelves": ready_collection_count,
            "recommendation_cards": int(recommendation_board.get("card_count", 0) or 0),
        },
        "by_kind": dict(sorted(by_kind.items())),
        "licenses": dict(sorted(licenses.items())),
        "targets": targets,
        "intent_coverage": intent_coverage,
        "collection_shelves": collection_shelves,
        "recommendation_board": recommendation_board,
        "issues": issues,
        "preview_storyboards": storyboards[:12],
        "sample_assets": [asdict(asset) for asset in assets[:8]],
    }
