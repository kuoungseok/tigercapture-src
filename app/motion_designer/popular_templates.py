"""Catalog data for the 100 common production Motion templates."""
from __future__ import annotations

import re
from typing import Any


_CATEGORIES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("Logo Reveals", 4000, (
        "Clean Logo Reveal", "Minimal Logo Animation", "Glitch Logo Reveal",
        "Particle Logo Reveal", "Liquid Logo Reveal", "3D Logo Reveal",
        "Fast Logo Sting", "Elegant Logo Animation", "Brush Stroke Logo",
        "Neon Logo Reveal", "Light Burst Logo", "Paper Cut Logo",
        "Smoke Logo Reveal", "Glass Logo Animation", "Kinetic Logo Reveal",
    )),
    ("Lower Thirds", 5000, (
        "Minimal Lower Third", "Modern Corporate Lower Third", "Glitch Lower Third",
        "Clean Name Tag", "Animated Name Title", "Broadcast Lower Third",
        "Simple Callout Lower Third", "Multi-line Lower Third",
        "Stylish Name Badge", "Dynamic Lower Third Pack",
    )),
    ("Titles & Typography", 5000, (
        "Kinetic Typography", "Big Bold Title", "Elegant Title Sequence",
        "Typewriter Text Animation", "Glitch Text Effect",
        "Handwritten Text Animation", "3D Text Animation", "Cinematic Title",
        "Pop-up Text Animation", "Smooth Text Reveal", "Calligraphy Title",
        "Neon Text Animation", "Split Text Animation", "Wave Text Effect",
        "Minimal Title Card",
    )),
    ("Transitions", 1800, (
        "Smooth Zoom Transition", "Glitch Transition", "Light Leak Transition",
        "Film Burn Transition", "Shape Wipe Transition", "Ink Transition",
        "Particle Transition", "Camera Shake Transition", "Vertical Transition",
        "Seamless Match Cut Transition", "Liquid Transition",
        "Paper Fold Transition", "Spin Transition", "Zoom Blur Transition",
        "Distortion Transition",
    )),
    ("Intros & Openers", 8000, (
        "Dynamic Opener", "Corporate Intro", "Fast YouTube Intro",
        "Cinematic Opener", "Minimal Channel Intro", "Energy Intro",
        "Modern Brand Intro", "Storyboard Opener", "Tech Intro",
        "Creative Portfolio Intro",
    )),
    ("Slideshows", 12000, (
        "Clean Photo Slideshow", "Wedding Slideshow", "Travel Slideshow",
        "Parallax Photo Gallery", "Fast Image Slideshow",
        "Elegant Photo Presentation", "Vertical Slideshow",
        "Multi-photo Grid Slideshow", "Ken Burns Slideshow", "3D Photo Gallery",
    )),
    ("Infographics & Data", 10000, (
        "Infographic Pack", "Animated Chart / Graph", "Timeline Infographic",
        "Process Flow Animation", "Statistics / Number Counter",
        "Comparison Chart", "Map Animation", "Icon Animation Pack",
        "Business Presentation Graphics", "HUD / Dashboard Interface",
    )),
    ("Social Media & YouTube", 7000, (
        "YouTube End Screen", "Subscribe Button Animation",
        "Instagram Story Template", "TikTok Vertical Template",
        "Social Media Promo Pack", "Call-to-Action Button",
        "Notification Popup", "Like / Comment Animation",
        "Shorts / Reels Opener", "YouTube Thumbnail Animation",
    )),
    ("Production Essentials", 8000, (
        "Background Loop / Abstract Background",
        "Overlay Pack (Light Leak, Dust, Film Grain)",
        "Countdown Timer", "Product Promo / App Promo",
        "Broadcast News Package",
    )),
)

POPULAR_TOP_10_NAMES = (
    "Clean Logo Reveal",
    "Minimal Logo Animation",
    "Minimal Lower Third",
    "Modern Corporate Lower Third",
    "Kinetic Typography",
    "Smooth Zoom Transition",
    "Fast YouTube Intro",
    "YouTube End Screen",
    "Clean Photo Slideshow",
    "Product Promo / App Promo",
)
_TOP_10_RANK = {
    name: index
    for index, name in enumerate(POPULAR_TOP_10_NAMES, 1)
}


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return f"popular_{slug}"


def _style(name: str) -> str:
    lowered = name.casefold()
    for token in (
        "glitch", "particle", "liquid", "3d", "fast", "elegant", "brush", "neon", "light",
        "paper", "smoke", "glass", "kinetic", "minimal", "corporate",
        "broadcast", "dynamic", "typewriter", "handwritten", "cinematic",
        "pop", "split", "wave", "zoom", "film", "ink", "shake", "vertical",
        "spin", "distortion", "parallax", "grid", "ken burns", "chart",
        "timeline", "counter", "map", "hud", "subscribe", "notification",
        "countdown", "overlay", "background",
    ):
        if token in lowered:
            return token.replace(" ", "_")
    return "clean"


def _variants(name: str, category: str) -> tuple[str, ...]:
    lowered = name.casefold()
    if any(token in lowered for token in ("vertical", "instagram", "tiktok", "shorts", "reels")):
        return ("9:16", "1:1", "16:9")
    if category == "Social Media & YouTube":
        return ("16:9", "9:16", "1:1")
    return ("16:9", "9:16", "1:1")


def _scene_count(category: str, name: str) -> int:
    if category == "Transitions":
        return 2
    if category == "Slideshows":
        return 6
    if category in {"Intros & Openers", "Infographics & Data"}:
        return 4
    if category in {"Social Media & YouTube", "Production Essentials"}:
        return 3
    return 1


def _features(category: str) -> tuple[str, ...]:
    return {
        "Logo Reveals": ("Editable logo placeholder", "Reveal timing", "Accent treatment"),
        "Lower Thirds": ("Editable name and role", "Broadcast-safe placement", "In/out animation"),
        "Titles & Typography": ("Editable typography", "Text animation", "Timing controls"),
        "Transitions": ("A/B scene placeholders", "Transition matte", "Editable duration"),
        "Intros & Openers": ("Multi-beat opener", "Media placeholders", "Brand end card"),
        "Slideshows": ("Replaceable photo slots", "Sequenced timing", "Caption layer"),
        "Infographics & Data": ("Editable values", "Chart shapes", "Label animation"),
        "Social Media & YouTube": ("Platform-safe layout", "CTA controls", "Vertical variant"),
        "Production Essentials": ("Production-ready overlay", "Loopable timing", "Editable colors"),
    }[category]


def _workflow(category: str) -> str:
    return {
        "Logo Reveals": "Brand ident and logo sting",
        "Lower Thirds": "YouTube, interview, and broadcast titling",
        "Titles & Typography": "Editorial and kinetic title design",
        "Transitions": "Scene-to-scene transition overlay",
        "Intros & Openers": "Channel, portfolio, and brand opener",
        "Slideshows": "Photo story and gallery presentation",
        "Infographics & Data": "Data, process, and business explanation",
        "Social Media & YouTube": "Creator and short-form publishing",
        "Production Essentials": "Reusable production overlay and package",
    }[category]


def _build_specs() -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for category, duration_ms, names in _CATEGORIES:
        for name in names:
            rows.append({
                "id": _slug(name),
                "name": name,
                "category": category,
                "duration_ms": duration_ms,
                "variants": _variants(name, category),
                "style": _style(name),
                "featured_rank": int(_TOP_10_RANK.get(name, 0)),
                "scene_count": _scene_count(category, name),
                "features": _features(category),
                "workflow": _workflow(category),
                "description": f"A production-ready {name.lower()} with editable layers and timing.",
                "replace_items": ("Headline", "Subtitle", "Media or logo", "Brand colors"),
                "tags": tuple({
                    "popular 100",
                    category.casefold(),
                    name.casefold(),
                    _style(name).replace("_", " "),
                }),
            })
    if len(rows) != 100:
        raise RuntimeError(f"Popular Motion template catalog must contain 100 entries, got {len(rows)}")
    return tuple(rows)


POPULAR_TEMPLATE_SPECS = _build_specs()
POPULAR_TEMPLATE_BY_ID = {str(row["id"]): row for row in POPULAR_TEMPLATE_SPECS}
POPULAR_TOP_10_IDS = tuple(
    str(row["id"])
    for row in sorted(
        (row for row in POPULAR_TEMPLATE_SPECS if int(row["featured_rank"]) > 0),
        key=lambda row: int(row["featured_rank"]),
    )
)


def is_popular_template(template_id: str) -> bool:
    return str(template_id) in POPULAR_TEMPLATE_BY_ID


__all__ = [
    "POPULAR_TEMPLATE_BY_ID",
    "POPULAR_TEMPLATE_SPECS",
    "POPULAR_TOP_10_IDS",
    "POPULAR_TOP_10_NAMES",
    "is_popular_template",
]
