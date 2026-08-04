"""Explicit resource boundaries for the Painter Actions/MCP surface."""
from __future__ import annotations

from app.painter_palette import MAX_BRUSH_PRESET_WIDTH_PX


PAINT_ACTION_MAX_STROKES_PER_REQUEST = 512
PAINT_ACTION_MAX_POINTS_PER_STROKE = 2048
PAINT_ACTION_MAX_BRUSH_WIDTH_PX = MAX_BRUSH_PRESET_WIDTH_PX
PAINT_ACTION_DEFAULT_REFERENCE_COLORS = 8
PAINT_ACTION_MAX_REFERENCE_COLORS = 12
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
    "default_study_regions": PAINT_ACTION_DEFAULT_STUDY_REGIONS,
    "default_study_strokes": PAINT_ACTION_DEFAULT_STUDY_STROKES,
    "max_study_strokes": PAINT_ACTION_MAX_STUDY_STROKES,
    "scope": "single_paint.stroke.draw_request_and_undo_transaction",
    "document_stroke_capacity_claim": False,
    "artwork_quality_threshold_claim": False,
    "universal_latency_or_memory_safety_claim": False,
}


__all__ = [
    "PAINT_ACTION_MAX_BRUSH_WIDTH_PX",
    "PAINT_ACTION_DEFAULT_REFERENCE_COLORS",
    "PAINT_ACTION_MAX_REFERENCE_COLORS",
    "PAINT_ACTION_DEFAULT_STUDY_REGIONS",
    "PAINT_ACTION_DEFAULT_STUDY_STROKES",
    "PAINT_ACTION_MAX_STUDY_STROKES",
    "PAINT_ACTION_MAX_POINTS_PER_STROKE",
    "PAINT_ACTION_MAX_STROKES_PER_REQUEST",
    "PAINT_ACTION_REQUEST_RESOURCE_CONTRACT",
]
