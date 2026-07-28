from __future__ import annotations

from copy import deepcopy

import pytest

from app.motion_designer.platform_copy import (
    PLATFORM_COPY_PLAN_SCHEMA,
    apply_platform_copy_plan,
    generate_platform_copy_plan,
    preflight_platform_copy_plan,
    validate_platform_copy_plan,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.story_direction import add_story_beat
from app.motion_designer.style_director import set_style_lock


def _composition() -> MotionComposition:
    title = MotionLayer(
        id="title",
        name="Main Headline",
        layer_type="text",
        source=SourceRef(
            kind="text",
            params={
                "text": (
                    "A deliberately long product headline that should become "
                    "shorter for a vertical performance advertisement"
                ),
                "role": "headline",
                "font_size": 72,
            },
        ),
        out_ms=5000,
    )
    protected = MotionLayer(
        id="legal",
        name="Legal Body",
        layer_type="text",
        source=SourceRef(
            kind="text",
            params={"text": "Protected legal copy", "role": "body"},
        ),
        out_ms=5000,
    )
    composition = MotionComposition(
        id="platform_copy_comp",
        name="Platform Copy",
        width=1920,
        height=1080,
        duration_ms=5000,
        revision=7,
        layers=[title, protected],
    )
    add_story_beat(
        composition,
        role="hook",
        start_ms=0,
        end_ms=1800,
        copy="This opening hook is intentionally much too long for a vertical short",
        layer_ids=["title"],
    )
    set_style_lock(composition, {"protected_layer_ids": ["legal"]})
    return composition


def test_platform_copy_plan_uses_shared_provider_boundary_and_protection():
    composition = _composition()
    plan = generate_platform_copy_plan(
        composition,
        platform="vertical",
        prompt="Make the copy concise and energetic.",
        provider_id="rule_based",
    )

    assert plan["schema"] == PLATFORM_COPY_PLAN_SCHEMA
    assert plan["platform"] == "vertical_9_16"
    assert plan["review_required"] is True
    assert plan["provider"]["provider"] == "rule_based"
    assert {row["target_id"] for row in plan["operations"]} == {
        "title",
        composition.metadata["story_direction"]["beats"][0]["id"],
    }
    assert all(
        len(row["after"]) <= row["max_characters"]
        for row in plan["operations"]
    )


def test_platform_copy_apply_requires_approval_and_preserves_motion():
    composition = _composition()
    before = [
        (layer.id, deepcopy(layer.transform.to_dict()), layer.source.uri)
        for layer in composition.layers
    ]
    plan = generate_platform_copy_plan(
        composition,
        platform="9:16",
        provider_id="rule_based",
    )

    with pytest.raises(PermissionError, match="explicit human approval"):
        apply_platform_copy_plan(composition, plan, approved=False)
    result, report = apply_platform_copy_plan(composition, plan, approved=True)

    assert report["source_transforms_preserved"] is True
    assert result.revision == 8
    assert composition.revision == 7
    assert [
        (layer.id, layer.transform.to_dict(), layer.source.uri)
        for layer in result.layers
    ] == before
    assert result.layers[1].source.params["text"] == "Protected legal copy"
    assert len(result.layers[0].source.params["text"]) <= 48


def test_platform_copy_rejects_provider_target_changes_and_stale_plans():
    composition = _composition()
    plan = generate_platform_copy_plan(
        composition,
        platform="square",
        provider_id="rule_based",
    )
    changed_target = deepcopy(plan)
    changed_target["operations"][0]["target_id"] = "legal"
    with pytest.raises((PermissionError, ValueError)):
        validate_platform_copy_plan(changed_target, composition=composition)

    composition.revision += 1
    with pytest.raises(ValueError, match="stale"):
        apply_platform_copy_plan(composition, plan, approved=True)


def test_platform_copy_preflight_reports_overflow_without_mutation():
    composition = _composition()
    plan = generate_platform_copy_plan(
        composition,
        platform="vertical",
        provider_id="rule_based",
    )
    invalid = deepcopy(plan)
    invalid["operations"][0]["after"] = "x" * 200
    report = preflight_platform_copy_plan(composition, invalid)

    assert report["ok"] is False
    assert report["issues"][0]["code"] == "invalid_platform_copy_plan"
    assert composition.revision == 7
