from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from app.motion_designer.image_decomposition import decompose_image
from app.motion_designer.image_decomposition_edits import (
    merge_decomposition_elements,
    replace_decomposition_element_mask,
    set_decomposition_lock,
    set_decomposition_parent,
    set_decomposition_pivot,
    set_decomposition_z_order,
    split_decomposition_element,
)


def _decomposition(tmp_path: Path):
    source = Image.new("RGB", (320, 180), (230, 235, 240))
    painter = ImageDraw.Draw(source)
    painter.ellipse((45, 35, 135, 145), fill=(220, 55, 45))
    painter.rectangle((205, 45, 280, 135), fill=(30, 100, 220))
    source_path = tmp_path / "source.png"
    source.save(source_path)
    return decompose_image(
        source_path,
        width=320,
        height=180,
        cache_root=tmp_path / "cache",
        include_depth=False,
        segmentation_mode="basic",
        reconstruct_text=False,
        force=True,
    )


def test_merge_split_and_lock_create_non_destructive_manifests(tmp_path: Path) -> None:
    result = _decomposition(tmp_path)
    visual_ids = [item.id for item in result.elements if item.role != "text"]
    assert len(visual_ids) >= 2
    merged = merge_decomposition_elements(result, visual_ids[:2])
    assert merged.diagnostics["edited"] is True
    merged_element = next(item for item in merged.elements if item.id.startswith("merged_"))
    assert Path(merged_element.rgba_path).is_file()
    assert Path(merged_element.mask_path).is_file()

    split = split_decomposition_element(
        merged,
        merged_element.id,
        axis="vertical",
        position=0.5,
    )
    split_rows = [item for item in split.elements if item.id.startswith(f"{merged_element.id}_part_")]
    assert len(split_rows) == 2
    locked = set_decomposition_lock(
        split,
        [split_rows[0].id],
        locked=True,
    )
    locked_row = next(item for item in locked.elements if item.id == split_rows[0].id)
    assert locked_row.metadata["motion_lock_to_background"] is True
    assert locked.diagnostics["validation"]["ok"] is True


def test_parent_edit_records_group_and_rejects_cycles(tmp_path: Path) -> None:
    result = _decomposition(tmp_path)
    visual = [item for item in result.elements if item.role != "text"]
    assert len(visual) >= 2
    parented = set_decomposition_parent(
        result,
        [visual[1].id],
        parent_id=visual[0].id,
    )
    child = next(item for item in parented.elements if item.id == visual[1].id)
    assert child.metadata["parent_id"] == visual[0].id
    with pytest.raises(ValueError, match="cycle"):
        set_decomposition_parent(
            parented,
            [visual[0].id],
            parent_id=visual[1].id,
        )


def test_manual_mask_replacement_rebuilds_rgba_and_integrity(tmp_path: Path) -> None:
    result = _decomposition(tmp_path)
    target = next(item for item in result.elements if item.role != "text")
    mask = Image.new("L", (320, 180), 0)
    ImageDraw.Draw(mask).ellipse((80, 30, 230, 165), fill=255)
    mask_path = tmp_path / "manual_mask.png"
    mask.save(mask_path)
    changed = replace_decomposition_element_mask(
        result,
        target.id,
        mask_path,
    )
    edited = next(item for item in changed.elements if item.id == target.id)
    assert edited.metadata["manual_mask_revision"] is True
    assert edited.bbox[2] > target.bbox[2]
    assert Path(edited.rgba_path).is_file()
    assert changed.diagnostics["validation"]["ok"] is True


def test_pivot_and_z_order_edits_survive_graph_refresh(tmp_path: Path) -> None:
    result = _decomposition(tmp_path)
    target = next(item for item in result.elements if item.role != "text")
    pivoted = set_decomposition_pivot(
        result,
        target.id,
        pivot=(41.5, 72.0),
    )
    pivoted_target = next(item for item in pivoted.elements if item.id == target.id)
    assert pivoted_target.metadata["pivot"] == [41.5, 72.0]
    reordered = set_decomposition_z_order(
        pivoted,
        target.id,
        z_order=99,
    )
    reordered_target = next(item for item in reordered.elements if item.id == target.id)
    assert reordered_target.metadata["z_order"] == 99
