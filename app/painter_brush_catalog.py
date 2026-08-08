"""Professional Painter brush catalog and renderer profiles."""
from __future__ import annotations

from typing import Final


DESIGNER_BRUSH_RENDER_PROFILES: Final[dict[str, dict[str, int | str]]] = {
    # Width, opacity, spacing, hardness, angle, and roundness are deliberately
    # absent: the public brush controls are their sole source of truth.
    "soft_round": {"mode": "soft", "layers": 5},
    "hard_flat": {"mode": "flat"},
    "soft_flat": {"mode": "soft_flat", "layers": 5},
    "pixel_square": {"mode": "pixel"},
    "graphite_pencil": {"mode": "grain", "marks_per_sample": 2},
    "charcoal_vine": {"mode": "grain", "marks_per_sample": 3},
    "charcoal_block": {"mode": "grain", "marks_per_sample": 4},
    "technical_ink": {"mode": "strands", "lanes": 2},
    "expressive_ink": {"mode": "strands", "lanes": 5},
    "watercolor_wash": {"mode": "wash"},
    "watercolor_edge": {"mode": "wash"},
    "gouache_flat": {"mode": "paint", "lanes": 7},
    "acrylic_bristle": {"mode": "paint", "lanes": 11},
    "airbrush_soft": {"mode": "soft", "layers": 7},
    "skin_blender": {"mode": "soft", "layers": 6},
    "hair_strand": {"mode": "strands", "lanes": 9},
    "foliage_scatter": {"mode": "scatter", "marks_per_sample": 2},
    "cloud_smoke": {"mode": "cloud", "marks_per_sample": 2},
    "rock_ground": {"mode": "grain", "marks_per_sample": 4},
    "fabric_grunge": {"mode": "crosshatch", "marks_per_sample": 3},
    "paint_splatter": {"mode": "scatter", "marks_per_sample": 3},
}

DESIGNER_BRUSH_STYLE_IDS: Final[frozenset[str]] = frozenset(DESIGNER_BRUSH_RENDER_PROFILES)
DESIGNER_PROFILE_PUBLIC_CONTROL_KEYS: Final[frozenset[str]] = frozenset(
    {"body", "alpha", "spacing", "hardness", "angle", "roundness"}
)


def _preset(
    category: str,
    name: str,
    style: str,
    width: int,
    opacity: int,
    hardness: int,
    spacing: int,
    angle: int = 0,
    roundness: int = 100,
) -> dict[str, object]:
    return {
        "category": category,
        "name": name,
        "style": style,
        "width": width,
        "opacity": opacity,
        "hardness": hardness,
        "spacing": spacing,
        "angle": angle,
        "roundness": roundness,
    }


DESIGNER_BRUSH_PRESETS: Final[tuple[dict[str, object], ...]] = (
    _preset("Basic", "Hard Round", "round", 18, 100, 100, 10),
    _preset("Basic", "Soft Round", "soft_round", 34, 46, 24, 8),
    _preset("Basic", "Hard Flat", "hard_flat", 30, 100, 96, 12, 0, 28),
    _preset("Basic", "Soft Flat", "soft_flat", 38, 54, 34, 10, 0, 32),
    _preset("Basic", "Pixel Square", "pixel_square", 4, 100, 100, 100, 0, 100),
    _preset("Drawing", "Graphite HB", "graphite_pencil", 5, 72, 82, 18, -8, 38),
    _preset("Drawing", "Vine Charcoal", "charcoal_vine", 16, 66, 58, 28, 12, 42),
    _preset("Drawing", "Charcoal Block", "charcoal_block", 28, 74, 72, 24, -18, 28),
    _preset("Ink", "Technical Pen", "technical_ink", 5, 100, 100, 8),
    _preset("Ink", "Expressive Inker", "expressive_ink", 11, 92, 88, 10, -4, 46),
    _preset("Water Media", "Watercolor Wash", "watercolor_wash", 52, 34, 18, 8),
    _preset("Water Media", "Watercolor Edge", "watercolor_edge", 34, 48, 42, 12),
    _preset("Water Media", "Opaque Gouache", "gouache_flat", 32, 92, 86, 13, 0, 52),
    _preset("Water Media", "Acrylic Bristle", "acrylic_bristle", 28, 90, 84, 16, 4, 40),
    _preset("Airbrush", "Soft Airbrush", "airbrush_soft", 56, 28, 12, 7),
    _preset("Concept", "Skin Blender", "skin_blender", 44, 30, 16, 6),
    _preset("Concept", "Hair Strands", "hair_strand", 18, 86, 78, 14, 0, 34),
    _preset("Concept", "Foliage Scatter", "foliage_scatter", 42, 82, 76, 44, 8, 62),
    _preset("Concept", "Cloud and Smoke", "cloud_smoke", 58, 36, 14, 34),
    _preset("Texture", "Rock and Ground", "rock_ground", 46, 78, 88, 36, 14, 48),
    _preset("Texture", "Fabric Grunge", "fabric_grunge", 34, 68, 74, 28, -12, 54),
    _preset("FX", "Paint Splatter", "paint_splatter", 32, 94, 92, 58),
)
