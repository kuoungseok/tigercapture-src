"""Shared placement math for Spine editor and timeline preview."""
from __future__ import annotations

SPINE_PREVIEW_FIT_MARGIN = 0.78


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
    work_margin: float = 0.76,
) -> tuple[float, float, float, tuple[float, float, float, float]]:
    """Return editor camera transform and visible final-frame rectangle.

    ``final`` mode maps the Spine actor exactly as the preview/export frame does.
    ``work`` mode keeps that final placement, then zooms the editor camera out
    only when needed so oversized or off-frame actors stay inspectable while the
    final output frame remains visible as an overlay rectangle.
    """
    width = max(1, int(width))
    height = max(1, int(height))
    final_scale, final_offset_x, final_offset_y = compute_spine_screen_layout(
        bounds,
        width,
        height,
        pos_x,
        pos_y,
        scale,
        margin=margin,
    )
    # Timeline/offscreen renderers receive offsets relative to the frame centre.
    # The editor viewport stores the world origin directly in widget pixels, so
    # convert the shared renderer placement before applying the work-view camera.
    final_origin_x = float(width) / 2.0 + final_offset_x
    final_origin_y = float(height) / 2.0 - final_offset_y
    if str(mode or "work").lower() not in {"work", "safe", "canvas"} or not bounds:
        return final_scale, final_origin_x, final_origin_y, (
            0.0,
            0.0,
            float(width),
            float(height),
        )

    min_x, min_y, max_x, max_y = bounds
    actor_left = final_origin_x + float(min_x) * final_scale
    actor_right = final_origin_x + float(max_x) * final_scale
    actor_top = final_origin_y - float(max_y) * final_scale
    actor_bottom = final_origin_y - float(min_y) * final_scale

    union_left = min(0.0, actor_left)
    union_top = min(0.0, actor_top)
    union_right = max(float(width), actor_right)
    union_bottom = max(float(height), actor_bottom)
    union_w = max(1.0, union_right - union_left)
    union_h = max(1.0, union_bottom - union_top)

    view_scale = min(
        1.0,
        float(width) * float(work_margin) / union_w,
        float(height) * float(work_margin) / union_h,
    )
    view_scale = max(0.02, min(1.0, view_scale))
    union_cx = (union_left + union_right) / 2.0
    union_cy = (union_top + union_bottom) / 2.0
    view_offset_x = float(width) / 2.0 - union_cx * view_scale
    view_offset_y = float(height) / 2.0 - union_cy * view_scale

    return (
        final_scale * view_scale,
        final_origin_x * view_scale + view_offset_x,
        final_origin_y * view_scale + view_offset_y,
        (
            view_offset_x,
            view_offset_y,
            float(width) * view_scale,
            float(height) * view_scale,
        ),
    )
