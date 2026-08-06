from __future__ import annotations

import operator


PAINTER_GRID_SIZE_MIN_PX = 4
PAINTER_GRID_SIZE_MAX_PX = 512
PAINTER_GRID_SIZE_DEFAULT_PX = 64
PAINTER_GRID_SIZE_CONTRACT = {
    "schema": "tigerstudio.painter.grid_size_policy.v1",
    "domain_px": [PAINTER_GRID_SIZE_MIN_PX, PAINTER_GRID_SIZE_MAX_PX],
    "default_px": PAINTER_GRID_SIZE_DEFAULT_PX,
    "source": "tiger_authored_visible_document_grid_control_domain",
    "artwork_quality_threshold_claim": False,
}


def normalize_painter_grid_size_px(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("Painter grid size must be an integer, not bool")
    try:
        size_px = operator.index(value)
    except TypeError as exc:
        raise TypeError("Painter grid size must be an integer") from exc
    return max(PAINTER_GRID_SIZE_MIN_PX, min(PAINTER_GRID_SIZE_MAX_PX, size_px))
