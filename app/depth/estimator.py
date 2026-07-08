"""Depth estimation entry points.

The real provider registry lives in :mod:`app.depth.providers`. This module is
kept as a compatibility surface for older imports.
"""
from __future__ import annotations

from typing import Any

from app.depth.providers import (
    SYNTHETIC_LUMA_PROVIDER_ID,
    depth_provider_status,
    estimate_depth,
    registered_depth_providers,
)


def depth_backend_status() -> dict[str, Any]:
    """Return depth provider availability without downloading models."""
    return depth_provider_status()


def estimate_depth_from_luma(
    frame: Any,
    *,
    source_id: str = "",
    time_ms: int = 0,
    vertical_weight: float = 0.7,
) -> tuple[Any, dict[str, Any]]:
    """Return the deterministic synthetic depth fallback."""
    provider = registered_depth_providers()[SYNTHETIC_LUMA_PROVIDER_ID]
    return provider.estimate(
        frame,
        source_id=source_id,
        time_ms=time_ms,
        options={"vertical_weight": vertical_weight},
    )


__all__ = ["depth_backend_status", "estimate_depth", "estimate_depth_from_luma"]
