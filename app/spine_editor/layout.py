"""Shared placement math for Spine editor and timeline preview."""
from __future__ import annotations

SPINE_PREVIEW_FIT_MARGIN = 0.78
SPINE_EDITOR_FRAME_MARGIN = 0.76


def _fit_aspect_rect(
    width: int,
    height: int,
    aspect_ratio: float,
    margin: float,
) -> tuple[float, float, float, float]:
    """Fit a fixed-aspect output frame inside the editor viewport."""
    viewport_w = max(1.0, float(width))
    viewport_h = max(1.0, float(height))
    aspect = max(0.05, min(20.0, float(aspect_ratio)))
    margin = max(0.05, min(1.0, float(margin)))
    available_w = viewport_w * margin
    available_h = viewport_h * margin
    if available_w / available_h >= aspect:
        frame_h = available_h
        frame_w = frame_h * aspect
    else:
        frame_w = available_w
        frame_h = frame_w / aspect
    return (
        (viewport_w - frame_w) / 2.0,
        (viewport_h - frame_h) / 2.0,
        frame_w,
        frame_h,
    )


def compute_spine_screen_layout(
    bounds: tuple[float, float, float, float] | None,
    width: int,
    height: int,
    pos_x: float,
    pos_y: float,
    scale: float,
    *,
    margin: float = SPINE_PREVIEW_FIT_MARGIN,
) -> tuple[float, float, float]:
    """Return ``(final_scale, offset_x, offset_y)`` for Spine renderers.

    ``pos_x`` / ``pos_y`` are normalized screen-center coordinates.  The
    renderer receives offsets relative to the frame center and internally maps
    them as ``cx = width / 2 + offset_x`` and ``cy = height / 2 - offset_y``.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    user_offset_x = (float(pos_x) - 0.5) * width
    user_offset_y = (float(pos_y) - 0.5) * height
    final_scale = max(0.02, min(20.0, float(scale)))
    offset_x = user_offset_x
    offset_y = -user_offset_y
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        visual_w = max(1.0, float(max_x) - float(min_x))
        visual_h = max(1.0, float(max_y) - float(min_y))
        fit_scale = min(width * margin / visual_w, height * margin / visual_h)
        fit_scale = max(0.02, min(20.0, fit_scale))
        final_scale = max(0.02, min(20.0, fit_scale * float(scale)))
        center_x = (float(min_x) + float(max_x)) / 2.0
        center_y = (float(min_y) + float(max_y)) / 2.0
        offset_x = user_offset_x - center_x * final_scale
        offset_y = -user_offset_y - center_y * final_scale
    return final_scale, offset_x, offset_y


def compute_spine_editor_view_transform(
    bounds: tuple[float, float, float, float] | None,
    width: int,
    height: int,
    pos_x: float,
    pos_y: float,
    scale: float,
    *,
    mode: str = "work",
    margin: float = SPINE_PREVIEW_FIT_MARGIN,
    work_margin: float = SPINE_EDITOR_FRAME_MARGIN,
    frame_aspect_ratio: float | None = None,
) -> tuple[float, float, float, tuple[float, float, float, float]]:
    """Return editor camera transform and visible final-frame rectangle.

    The frame is fitted independently from the actor, so placement and scale
    controls move only the actor. ``work`` leaves breathing room around the
    frame; ``final`` uses the largest frame that fits the viewport.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    aspect = float(frame_aspect_ratio or (float(width) / float(height)))
    normalized_mode = str(mode or "work").lower()
    frame_margin = work_margin if normalized_mode in {"work", "safe", "canvas"} else 1.0
    frame_x, frame_y, frame_w, frame_h = _fit_aspect_rect(
        width,
        height,
        aspect,
        frame_margin,
    )
    final_scale, final_offset_x, final_offset_y = compute_spine_screen_layout(
        bounds,
        max(1, round(frame_w)),
        max(1, round(frame_h)),
        pos_x,
        pos_y,
        scale,
        margin=margin,
    )
    # Timeline/offscreen renderers receive offsets relative to the frame centre.
    # The editor viewport stores the world origin directly in widget pixels, so
    # convert the shared renderer placement before applying the work-view camera.
    final_origin_x = frame_x + frame_w / 2.0 + final_offset_x
    final_origin_y = frame_y + frame_h / 2.0 - final_offset_y
    return final_scale, final_origin_x, final_origin_y, (
        frame_x,
        frame_y,
        frame_w,
        frame_h,
    )
