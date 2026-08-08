from __future__ import annotations

import pytest


def test_active_deletion_selects_predecessor_within_remaining_catalog() -> None:
    from app.painter_catalog_indices import catalog_index_after_active_deletion

    assert catalog_index_after_active_deletion(5, remaining_count=8) == 4
    assert catalog_index_after_active_deletion(0, remaining_count=8) == 0
    assert catalog_index_after_active_deletion(9, remaining_count=8) == 7
    with pytest.raises(ValueError, match="retain"):
        catalog_index_after_active_deletion(0, remaining_count=0)


def test_custom_brush_move_is_one_step_and_boundary_clamped() -> None:
    from app.painter_catalog_indices import moved_custom_brush_index

    assert moved_custom_brush_index(1, count=3, direction=-1) == 0
    assert moved_custom_brush_index(1, count=3, direction=1) == 2
    assert moved_custom_brush_index(0, count=3, direction=-1) == 0
    assert moved_custom_brush_index(2, count=3, direction=1) == 2
    for invalid in (0, 2, -2):
        with pytest.raises(ValueError, match="direction"):
            moved_custom_brush_index(1, count=3, direction=invalid)
    with pytest.raises(IndexError):
        moved_custom_brush_index(3, count=3, direction=1)
    for invalid in (True, 1.0, "1"):
        with pytest.raises(TypeError):
            moved_custom_brush_index(1, count=3, direction=invalid)
