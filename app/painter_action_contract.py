"""Explicit resource boundaries for the Painter Actions/MCP surface."""
from __future__ import annotations

import math
import operator
from numbers import Real

from app.painter_brush_catalog import DESIGNER_BRUSH_STYLE_IDS
from app.painter_palette import MAX_BRUSH_PRESET_WIDTH_PX


PAINT_ACTION_MAX_STROKES_PER_REQUEST = 512
PAINT_ACTION_MAX_POINTS_PER_STROKE = 2048
PAINT_ACTION_PATH_MIN_POINTS = 2
PAINT_ACTION_PATH_SELECTION_MIN_POINTS = 3
PAINT_ACTION_PATH_COORDINATE_MIN_NORM = 0.0
PAINT_ACTION_PATH_COORDINATE_MAX_NORM = 1.0
PAINT_ACTION_PATH_INDEX_MIN = 0
PAINT_ACTION_PATH_NAME_MIN_CHARACTERS = 1
PAINT_ACTION_MAX_BRUSH_WIDTH_PX = MAX_BRUSH_PRESET_WIDTH_PX
PAINT_ACTION_STROKE_MIN_WIDTH_PX = 0.25
PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT = 1
PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT = 100
PAINT_ACTION_STROKE_ENGINE_VERSION_MIN = 1
PAINT_ACTION_STROKE_ENGINE_VERSION_MAX = 2
PAINT_ACTION_STROKE_BRISTLE_COUNT_MIN = 0
PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX = 64
PAINT_ACTION_STROKE_SEED_MIN = 0
PAINT_ACTION_STROKE_SEED_MAX = (1 << 64) - 1
PAINT_ACTION_STROKE_DEFAULT_COLOR = "#EEF2F7"
PAINT_ACTION_STROKE_DEFAULT_WIDTH_PX = 4.0
PAINT_ACTION_STROKE_DEFAULT_STYLE = "round"
PAINT_ACTION_STROKE_DEFAULT_PATH_MODE = "smooth"
PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION = 0.28
PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS = {
    "pressure": 1.0,
    "tilt": 0.5,
    "tilt_x": 0.0,
    "tilt_y": 0.0,
    "rotation": 0.5,
    "tangential_pressure": 0.0,
    "load": 1.0,
}
PAINT_ACTION_STROKE_DEFAULT_MATERIAL_CHANNELS = {
    "load": 0.0,
    "thickness": 0.0,
    "wetness": 0.0,
    "gloss": 0.0,
    "roughness": 0.56,
    "plow": 0.0,
    "resaturation": 0.0,
    "negative_depth": False,
}
PAINT_ACTION_STROKE_SEED_INDEX_FACTOR = 7919
PAINT_ACTION_STROKE_SEED_POINT_FACTOR = 131
PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT = 100
PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM = 0.04
PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM = 1.0 - PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM
PAINT_ACTION_BRUSH_OPACITY_MIN_PERCENT = 10
PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT = 100
# QPoint stores each canvas-pan coordinate as the platform Qt signed int.
# The bundled PySide6 runtime accepts the full 32-bit range and raises
# OverflowError immediately outside it.
PAINT_ACTION_QPOINT_COORDINATE_MIN = -(1 << 31)
PAINT_ACTION_QPOINT_COORDINATE_MAX = (1 << 31) - 1
PAINT_ACTION_BRUSH_STYLES = tuple(
    sorted(
        {
            "round", "marker", "highlighter", "dashed", "loaded_oil",
            "impasto_oil", "oil_smear", "soft_oil_glaze", "real_wet_oil",
            "bristle_oil", "dry_oil", "palette_knife", "filbert_oil",
            "flat_hog_oil", "fan_bristle_oil", "rigger_oil", "scumble_oil",
            "stipple_oil", "knife_scrape_oil", "textured_chalk",
        }
        | set(DESIGNER_BRUSH_STYLE_IDS)
    )
)
PAINT_ACTION_DEFAULT_REFERENCE_COLORS = 8
PAINT_ACTION_MAX_REFERENCE_COLORS = 12
PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX = 64
PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX = 8192
PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX = 640
PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX = 360
PAINT_ACTION_PBR_PREVIEW_MIN_PX = 64
PAINT_ACTION_PBR_PREVIEW_MAX_PX = 1024
PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX = 512
PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES = 128 * 1024 * 1024
PAINT_ACTION_DEFAULT_STUDY_REGIONS = 12
PAINT_ACTION_DEFAULT_STUDY_STROKES = 5000
PAINT_ACTION_MAX_STUDY_STROKES = 50000

PAINT_ACTION_REQUEST_RESOURCE_CONTRACT = {
    "schema": "tigerstudio.painter.action_request_resource_policy.v1",
    "source": "tiger_authored_atomic_action_payload_guard",
    "max_strokes_per_request": PAINT_ACTION_MAX_STROKES_PER_REQUEST,
    "max_points_per_stroke": PAINT_ACTION_MAX_POINTS_PER_STROKE,
    "max_brush_width_px": PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
    "default_reference_colors": PAINT_ACTION_DEFAULT_REFERENCE_COLORS,
    "max_reference_colors": PAINT_ACTION_MAX_REFERENCE_COLORS,
    "blockout_preview_min_px": PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX,
    "blockout_preview_max_px": PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX,
    "blockout_preview_default_width_px": PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
    "blockout_preview_default_height_px": PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    "default_study_regions": PAINT_ACTION_DEFAULT_STUDY_REGIONS,
    "default_study_strokes": PAINT_ACTION_DEFAULT_STUDY_STROKES,
    "max_study_strokes": PAINT_ACTION_MAX_STUDY_STROKES,
    "scope": "single_painter_action_request_response_and_undo_transaction",
    "document_stroke_capacity_claim": False,
    "artwork_quality_threshold_claim": False,
    "universal_latency_or_memory_safety_claim": False,
}

PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT = {
    "schema": "tigerstudio.painter.pbr_preview_resource_policy.v1",
    "source": "tiger_authored_measured_cpu_preview_resource_policy",
    "minimum_px": PAINT_ACTION_PBR_PREVIEW_MIN_PX,
    "maximum_px": PAINT_ACTION_PBR_PREVIEW_MAX_PX,
    "default_px": PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
    "retained_array_budget_bytes": PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES,
    "measured_backend": "cpu",
    "universal_latency_or_memory_safety_claim": False,
    "gpu_parity_claim": False,
    "visual_quality_threshold_claim": False,
}


def normalize_painter_pbr_preview_width(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Painter PBR preview width must be an integer")
    try:
        width = operator.index(value)
    except TypeError as exc:
        raise TypeError("Painter PBR preview width must be an integer") from exc
    if not PAINT_ACTION_PBR_PREVIEW_MIN_PX <= width <= PAINT_ACTION_PBR_PREVIEW_MAX_PX:
        raise ValueError(
            "Painter PBR preview width must be between "
            f"{PAINT_ACTION_PBR_PREVIEW_MIN_PX} and "
            f"{PAINT_ACTION_PBR_PREVIEW_MAX_PX} pixels"
        )
    return width


def normalize_painter_numeric_color_components(value: object) -> tuple[float, float, float]:
    if not isinstance(value, list):
        raise TypeError("Painter numeric color values must be an array")
    if len(value) != 3:
        raise ValueError("Painter numeric color requires exactly three values")
    if any(isinstance(component, bool) or not isinstance(component, Real) for component in value):
        raise TypeError("Painter numeric color values must be finite numbers")
    components = tuple(float(component) for component in value)
    if not all(math.isfinite(component) for component in components):
        raise ValueError("Painter numeric color values must be finite numbers")
    return components


__all__ = [
    "PAINT_ACTION_MAX_BRUSH_WIDTH_PX",
    "PAINT_ACTION_STROKE_MIN_WIDTH_PX",
    "PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT",
    "PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT",
    "PAINT_ACTION_STROKE_ENGINE_VERSION_MIN",
    "PAINT_ACTION_STROKE_ENGINE_VERSION_MAX",
    "PAINT_ACTION_STROKE_BRISTLE_COUNT_MIN",
    "PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX",
    "PAINT_ACTION_STROKE_SEED_MIN",
    "PAINT_ACTION_STROKE_SEED_MAX",
    "PAINT_ACTION_STROKE_DEFAULT_COLOR",
    "PAINT_ACTION_STROKE_DEFAULT_WIDTH_PX",
    "PAINT_ACTION_STROKE_DEFAULT_STYLE",
    "PAINT_ACTION_STROKE_DEFAULT_PATH_MODE",
    "PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION",
    "PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS",
    "PAINT_ACTION_STROKE_DEFAULT_MATERIAL_CHANNELS",
    "PAINT_ACTION_STROKE_SEED_INDEX_FACTOR",
    "PAINT_ACTION_STROKE_SEED_POINT_FACTOR",
    "PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT",
    "PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM",
    "PAINT_ACTION_EDITOR_OBJECT_MAX_POSITION_NORM",
    "PAINT_ACTION_BRUSH_OPACITY_MIN_PERCENT",
    "PAINT_ACTION_BRUSH_OPACITY_MAX_PERCENT",
    "PAINT_ACTION_QPOINT_COORDINATE_MIN",
    "PAINT_ACTION_QPOINT_COORDINATE_MAX",
    "PAINT_ACTION_BRUSH_STYLES",
    "PAINT_ACTION_DEFAULT_REFERENCE_COLORS",
    "PAINT_ACTION_MAX_REFERENCE_COLORS",
    "PAINT_ACTION_BLOCKOUT_PREVIEW_MIN_PX",
    "PAINT_ACTION_BLOCKOUT_PREVIEW_MAX_PX",
    "PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX",
    "PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX",
    "PAINT_ACTION_PBR_PREVIEW_MIN_PX",
    "PAINT_ACTION_PBR_PREVIEW_MAX_PX",
    "PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX",
    "PAINT_ACTION_PBR_RETAINED_ARRAY_BUDGET_BYTES",
    "PAINT_ACTION_PBR_PREVIEW_RESOURCE_CONTRACT",
    "normalize_painter_pbr_preview_width",
    "normalize_painter_numeric_color_components",
    "PAINT_ACTION_DEFAULT_STUDY_REGIONS",
    "PAINT_ACTION_DEFAULT_STUDY_STROKES",
    "PAINT_ACTION_MAX_STUDY_STROKES",
    "PAINT_ACTION_MAX_POINTS_PER_STROKE",
    "PAINT_ACTION_PATH_MIN_POINTS",
    "PAINT_ACTION_PATH_SELECTION_MIN_POINTS",
    "PAINT_ACTION_PATH_COORDINATE_MIN_NORM",
    "PAINT_ACTION_PATH_COORDINATE_MAX_NORM",
    "PAINT_ACTION_PATH_INDEX_MIN",
    "PAINT_ACTION_PATH_NAME_MIN_CHARACTERS",
    "PAINT_ACTION_MAX_STROKES_PER_REQUEST",
    "PAINT_ACTION_REQUEST_RESOURCE_CONTRACT",
]
