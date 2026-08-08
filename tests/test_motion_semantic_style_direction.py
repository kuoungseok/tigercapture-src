from __future__ import annotations

from copy import deepcopy

import pytest

from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.semantic_style_direction import (
    SEMANTIC_STYLE_SCHEMA,
    generate_semantic_style_direction,
    validate_semantic_style_direction,
)
from app.motion_designer.style_director import plan_style_direction


def _composition() -> MotionComposition:
    return MotionComposition(
        id="semantic_style_comp",
        revision=5,
        layers=[
            MotionLayer(
                id="hero",
                name="Hero",
                layer_type="shape",
                source=SourceRef(kind="shape"),
                out_ms=3000,
            ),
        ],
    )


def test_semantic_style_direction_recommends_and_ranks_every_candidate():
    composition = _composition()
    plan = plan_style_direction(
        composition,
        "Energetic handmade editorial launch",
        seed=17,
    )
    direction = generate_semantic_style_direction(
        composition,
        plan,
        provider_id="rule_based",
    )

    assert direction["schema"] == SEMANTIC_STYLE_SCHEMA
    assert direction["recommended_style_id"] == "collage"
    assert direction["ranking"][0] == "collage"
    assert set(direction["ranking"]) == {
        "clean", "craft", "collage", "glass", "stop_motion",
    }
    assert direction["provider"]["provider"] == "rule_based"
    assert direction["review_required"] is True


def test_semantic_style_direction_rejects_candidate_injection_and_stale_revision():
    composition = _composition()
    plan = plan_style_direction(composition, "Premium glass launch")
    direction = generate_semantic_style_direction(
        composition,
        plan,
        provider_id="rule_based",
    )
    injected = deepcopy(direction)
    injected["ranking"][0] = "unknown"
    with pytest.raises(ValueError, match="every candidate"):
        validate_semantic_style_direction(
            injected,
            composition=composition,
            style_plan=plan,
        )

    composition.revision += 1
    with pytest.raises(ValueError, match="stale"):
        generate_semantic_style_direction(
            composition,
            plan,
            provider_id="rule_based",
        )
