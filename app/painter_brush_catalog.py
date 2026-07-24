"""Professional Painter brush catalog and renderer profiles."""
from __future__ import annotations

from typing import Final


DESIGNER_BRUSH_RENDER_PROFILES: Final[dict[str, dict[str, float | str]]] = {
    "soft_round": {"mode": "soft", "body": 1.00, "alpha": 0.20, "layers": 5},
    "hard_flat": {"mode": "flat", "body": 0.82, "alpha": 0.82, "lanes": 3},
    "soft_flat": {"mode": "soft_flat", "body": 1.05, "alpha": 0.24, "layers": 5},
    "pixel_square": {"mode": "pixel", "body": 0.92, "alpha": 1.00, "spacing": 0.72},
    "graphite_pencil": {"mode": "grain", "body": 0.22, "alpha": 0.54, "density": 7},
    "charcoal_vine": {"mode": "grain", "body": 0.58, "alpha": 0.36, "density": 13},
    "charcoal_block": {"mode": "grain", "body": 0.92, "alpha": 0.48, "density": 17},
    "technical_ink": {"mode": "strands", "body": 0.46, "alpha": 0.92, "lanes": 2},
    "expressive_ink": {"mode": "strands", "body": 0.72, "alpha": 0.80, "lanes": 5},
    "watercolor_wash": {"mode": "wash", "body": 1.22, "alpha": 0.13, "blooms": 5},
    "watercolor_edge": {"mode": "wash", "body": 0.96, "alpha": 0.18, "blooms": 7},
    "gouache_flat": {"mode": "paint", "body": 0.88, "alpha": 0.70, "lanes": 7},
    "acrylic_bristle": {"mode": "paint", "body": 0.76, "alpha": 0.62, "lanes": 11},
    "airbrush_soft": {"mode": "soft", "body": 1.45, "alpha": 0.09, "layers": 7},
    "skin_blender": {"mode": "soft", "body": 1.14, "alpha": 0.13, "layers": 6},
    "hair_strand": {"mode": "strands", "body": 0.68, "alpha": 0.72, "lanes": 9},
    "foliage_scatter": {"mode": "scatter", "body": 0.44, "alpha": 0.64, "density": 8},
    "cloud_smoke": {"mode": "cloud", "body": 1.34, "alpha": 0.10, "density": 9},
    "rock_ground": {"mode": "grain", "body": 1.06, "alpha": 0.42, "density": 19},
    "fabric_grunge": {"mode": "crosshatch", "body": 0.82, "alpha": 0.34, "density": 13},
    "paint_splatter": {"mode": "scatter", "body": 0.26, "alpha": 0.78, "density": 14},
}

DESIGNER_BRUSH_STYLE_IDS: Final[frozenset[str]] = frozenset(DESIGNER_BRUSH_RENDER_PROFILES)


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

