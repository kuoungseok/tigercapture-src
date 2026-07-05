"""Depth estimation and cache helpers for AR/PBR compositing."""

from app.depth.estimator import depth_backend_status, estimate_depth_from_luma

__all__ = ["estimate_depth_from_luma", "depth_backend_status"]

