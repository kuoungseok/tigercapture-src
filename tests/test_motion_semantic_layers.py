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
    normalize_object_hints,
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


def test_object_hints_create_named_independent_grabcut_candidates() -> None:
    height, width = 160, 300
    yy, xx = np.indices((height, width))
    rgb = np.stack(
        (
            18 + xx % 13,
            22 + yy % 11,
            28 + (xx + yy) % 9,
        ),
        axis=-1,
    ).astype(np.uint8)
    rgb[30:140, 30:105] = (210, 55, 65)
    rgb[38:132, 38:97] = np.stack(
        (
            190 + yy[38:132, 38:97] % 35,
            35 + xx[38:132, 38:97] % 20,
            55 + yy[38:132, 38:97] % 25,
        ),
        axis=-1,
    )
    rgb[55:125, 175:275] = (35, 110, 225)
    rgb[65:115, 185:265] = np.stack(
        (
            25 + xx[65:115, 185:265] % 25,
            90 + yy[65:115, 185:265] % 35,
            205 + xx[65:115, 185:265] % 35,
        ),
        axis=-1,
    )
    alpha = np.full((height, width), 255, dtype=np.uint8)

    result = segment_image(
        rgb,
        alpha,
        mode="basic",
        max_elements=4,
        object_hints=[
            {
                "id": "hero",
                "label": "character",
                "bbox": [0.05, 0.1, 0.4, 0.85],
            },
            {
                "id": "vehicle",
                "label": "car",
                "bbox": [0.52, 0.22, 0.45, 0.7],
            },
        ],
    )

    assert result.provider == "grabcut_box_hints"
    assert {item.semantic_label for item in result.candidates} == {
        "character",
        "car",
    }
    assert {
        item.metadata["object_hint_id"] for item in result.candidates
    } == {"hero", "vehicle"}
    assert result.diagnostics["guided_candidate_count"] == 2


def test_seeded_object_hint_preserves_both_dark_legs_and_clears_gap() -> None:
    height, width = 180, 160
    yy, xx = np.indices((height, width))
    rgb = np.stack(
        (
            18 + xx % 6,
            20 + yy % 7,
            24 + (xx + yy) % 5,
        ),
        axis=-1,
    ).astype(np.uint8)
    rgb[20:90, 45:115] = (190, 70, 92)
    rgb[80:155, 48:73] = (28, 30, 35)
    rgb[80:155, 87:112] = (30, 31, 36)
    rgb[148:165, 40:75] = (215, 215, 220)
    rgb[148:165, 86:121] = (210, 212, 218)
    alpha = np.full((height, width), 255, dtype=np.uint8)

    result = segment_image(
        rgb,
        alpha,
        mode="basic",
        max_elements=2,
        object_hints=[{
            "id": "character",
            "label": "character",
            "bbox": [0.2, 0.05, 0.6, 0.9],
            "foreground_points": [
                [0.38, 0.62],
                [0.62, 0.62],
                [0.34, 0.86],
                [0.66, 0.86],
            ],
            "background_points": [
                [0.5, 0.66],
                [0.5, 0.82],
            ],
        }],
    )

    mask = result.candidates[0].mask
    assert mask[112, 61] > 0
    assert mask[112, 99] > 0
    assert mask[155, 55] > 0
    assert mask[155, 103] > 0
    assert mask[118, 80] == 0
    assert mask[148, 80] == 0


def test_object_hint_normalization_preserves_segmentation_points() -> None:
    hint = normalize_object_hints([{
        "id": "hero",
        "label": "character",
        "bbox": [0.1, 0.2, 0.4, 0.7],
        "foreground_points": [[0.2, 0.4], [40, 80]],
        "background_points": [[0.3, 0.8]],
    }])[0]

    assert hint.foreground_points == ((0.2, 0.4), (40.0, 80.0))
    assert hint.background_points == ((0.3, 0.8),)
    assert hint.to_dict()["foreground_points"] == [[0.2, 0.4], [40.0, 80.0]]


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
