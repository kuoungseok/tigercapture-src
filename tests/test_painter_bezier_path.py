from __future__ import annotations

import pytest


def test_bezier_path_uses_handles_and_closes() -> None:
    from app.painter_bezier_path import bezier_selection_mask, build_bezier_path

    points = [(0.1, 0.5), (0.9, 0.5), (0.5, 0.9)]
    handles = [[0.1, 0.5, 0.25, 0.1], [0.75, 0.1, 0.9, 0.5], [0.5, 0.9, 0.5, 0.9]]
    path = build_bezier_path(points, handles, width=100, height=80, closed=True)
    assert not path.isEmpty()
    assert path.elementCount() > len(points)
    mask = bezier_selection_mask(points, handles, 100, 80)
    assert mask.pixelColor(50, 50).alpha() > 0


def test_anchor_add_delete_corner_and_smooth_conversion() -> None:
    from app.painter_bezier_path import edit_anchor

    points = [(0.1, 0.1), (0.9, 0.9)]
    points, handles = edit_anchor(points, [], 1, operation="add", point=(0.5, 0.2))
    assert len(points) == 3
    points, handles = edit_anchor(points, handles, 1, operation="smooth", out_handle=(0.7, 0.2))
    assert handles[1][:2] == pytest.approx([0.3, 0.2])
    points, handles = edit_anchor(points, handles, 1, operation="corner")
    assert handles[1] == [0.5, 0.2, 0.5, 0.2]
    points, handles = edit_anchor(points, handles, 1, operation="delete")
    assert len(points) == 2 and len(handles) == 2
