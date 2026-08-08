"""Canonical serialized domains for Painter Painting layers."""
from __future__ import annotations


PAINTER_LAYER_NAME_MAX_CHARACTERS = 80
PAINTER_LAYER_ID_MIN_CHARACTERS = 1
PAINTER_LAYER_TYPES = ("standard", "material")
PAINTER_LAYER_COLOR_LABEL_IDS = (
    "none",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "violet",
    "gray",
)


__all__ = [
    "PAINTER_LAYER_COLOR_LABEL_IDS",
    "PAINTER_LAYER_ID_MIN_CHARACTERS",
    "PAINTER_LAYER_NAME_MAX_CHARACTERS",
    "PAINTER_LAYER_TYPES",
]
