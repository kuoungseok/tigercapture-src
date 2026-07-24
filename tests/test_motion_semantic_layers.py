from __future__ import annotations

import numpy as np

from app.motion_designer.layer_graph import build_layer_graph, validate_layer_graph
from app.motion_designer.mask_integrity import (
    analyze_mask_integrity,
    merge_masks,
    motion_lock_required,
    split_mask,
)
from app.motion_designer.semantic_segmentation import (
    BasicLocalSegmentationProvider,
    SamSegmentationProvider,
    segmentation_capabilities,
    segment_image,
)


def test_basic_segmentation_returns_provider_and_candidates() -> None:
    rgb = np.full((120, 200, 3), 18, dtype=np.uint8)
    rgb[25:105, 65:145] = (230, 84, 42)
    alpha = np.full((120, 200), 255, dtype=np.uint8)
    result = segment_image(rgb, alpha, mode="basic", max_elements=4)
    assert result.provider in {"grabcut_border_seed", "border_color_distance"}
    assert result.candidates
    assert result.foreground_mask.shape == alpha.shape
    assert result.summary()["requested_mode"] == "basic"


def test_source_alpha_has_priority_over_optional_sam() -> None:
    rgb = np.full((80, 100, 3), 40, dtype=np.uint8)
    alpha = np.zeros((80, 100), dtype=np.uint8)
    alpha[15:70, 20:85] = 255
    result = segment_image(rgb, alpha, mode="auto", max_elements=3)
    assert result.provider == "source_alpha"
    assert result.transparent_source is True
    assert result.candidates


def test_segmentation_provider_contract_reports_real_capabilities() -> None:
    capabilities = segmentation_capabilities()
    assert capabilities["local_basic"]["available"] is True
    assert capabilities["local_basic"]["point_hints"] is False
    assert capabilities["local_sam"]["available"] is SamSegmentationProvider.available()
    assert BasicLocalSegmentationProvider().available() is True


def test_sparse_mask_is_locked_and_mask_edit_operations_are_deterministic() -> None:
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[10:90, 10:15] = 255
    mask[10:15, 10:90] = 255
    mask[85:90, 10:90] = 255
    mask[10:90, 85:90] = 255
    report = analyze_mask_integrity(mask)
    locked, reason = motion_lock_required(report, role="primary_subject")
    assert report.sparse_or_hollow is True
    assert locked is True
    assert reason == "sparse_or_hollow_primary_mask"

    left, right = split_mask(mask, axis="vertical", position=0.5)
    merged = merge_masks((left, right))
    assert np.array_equal(merged, mask)


def test_layer_graph_attaches_overlapping_secondary_to_primary() -> None:
    rows = [
        {
            "id": "hero",
            "role": "primary_subject",
            "bbox": [30, 10, 100, 160],
            "depth": 0.5,
            "area_ratio": 0.3,
            "confidence": 0.9,
            "metadata": {},
        },
        {
            "id": "prop",
            "role": "secondary_element",
            "bbox": [90, 65, 35, 40],
            "depth": 0.7,
            "area_ratio": 0.04,
            "confidence": 0.8,
            "metadata": {},
        },
        {
            "id": "title",
            "role": "text",
            "bbox": [20, 10, 160, 25],
            "depth": 0.98,
            "area_ratio": 0.02,
            "confidence": 0.95,
            "metadata": {},
        },
    ]
    graph = build_layer_graph(rows, width=200, height=180)
    by_id = graph.by_id()
    assert by_id["hero"].rigid is True
    assert by_id["prop"].parent_id == "hero"
    assert by_id["prop"].motion_group_id == by_id["hero"].motion_group_id
    assert by_id["title"].motion_group_id == "group_typography"
    assert validate_layer_graph(graph) == []
