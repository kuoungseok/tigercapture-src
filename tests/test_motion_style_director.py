from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.style_director import (
    STORY_PLAN_SCHEMA,
    STYLE_DIRECTOR_SCHEMA,
    STYLE_IDS,
    apply_story_direction,
    apply_style_candidate,
    plan_story_direction,
    plan_style_direction,
    set_style_lock,
    trend_preflight,
)


BACKEND = {
    "selected_provider": "claude_mcp",
    "effective_generation_provider": "rule_based",
    "fallback_reason": "Offline test fallback",
    "providers": {
        "claude_mcp": {"available": False},
        "rule_based": {"available": True},
    },
}


def _composition() -> MotionComposition:
    hero = MotionLayer(
        id="hero",
        name="Hero",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 180,
            "height": 220,
            "fill": "#e97955",
            "stroke": "#281a24",
            "stroke_width": 4,
        }),
        out_ms=5000,
        effects=[MotionEffectRef(kind="glow", metadata={"manual": True})],
    )
    hero.transform.position = AnimatedProperty(
        value_type="vector2",
        default=[180.0, 180.0],
        keyframes=[
            Keyframe(
                id="key_start",
                time_ms=0,
                value=[180.0, 180.0],
                interpolation="bezier",
            ),
            Keyframe(
                id="key_end",
                time_ms=5000,
                value=[460.0, 180.0],
                interpolation="bezier",
            ),
        ],
    )
    title = MotionLayer(
        id="title",
        name="Title",
        layer_type="text",
        source=SourceRef(kind="text", params={
            "text": "TIGER",
            "font_family": "Arial",
            "font_size": 64,
            "fill": "#ffffff",
            "width": 400,
            "height": 100,
        }),
        out_ms=5000,
    )
    title.transform.position.default = [320.0, 70.0]
    return MotionComposition(
        id="style_comp",
        name="Style Director",
        width=640,
        height=360,
        fps=30,
        duration_ms=5000,
        revision=4,
        layers=[hero, title],
    )


def _plan(composition: MotionComposition) -> dict:
    return plan_style_direction(
        composition,
        'Premium handmade launch. Story hook, then "Create boldly".',
        [{
            "id": "ref_image",
            "kind": "image",
            "name": "mood.png",
            "uri": "missing-mood.png",
            "metadata": {
                "provenance": {
                    "kind": "image",
                    "fingerprint": "abc123",
                },
            },
        }],
        backend_snapshot=BACKEND,
        seed=41,
    )


def _candidate(plan: dict, style_id: str) -> dict:
    return next(row for row in plan["candidates"] if row["style_id"] == style_id)


def test_style_plan_separates_style_story_backend_cost_and_provenance():
    composition = _composition()
    plan = _plan(composition)

    assert plan["schema"] == STYLE_DIRECTOR_SCHEMA
    assert {row["style_id"] for row in plan["candidates"]} == set(STYLE_IDS)
    assert {"premium", "handmade"} <= set(plan["style_intent"]["keywords"])
    assert plan["story_intent"]["requested_story"] is True
    assert plan["backend"]["fallback_used"] is True
    assert plan["backend"]["estimated_cost"]["amount"] == 0.0
    assert plan["references"][0]["provenance"]["fingerprint"] == "abc123"
    assert all(row["provenance"]["editable_result"] for row in plan["candidates"])


@pytest.mark.parametrize("style_id", STYLE_IDS)
def test_each_style_candidate_preserves_source_transform_keys_and_manual_effect(
    style_id,
):
    composition = _composition()
    plan = _plan(composition)
    candidate = _candidate(plan, style_id)
    before_transform = [
        (layer.id, deepcopy(layer.transform.to_dict()), deepcopy(layer.source.to_dict()))
        for layer in composition.layers
    ]

    result, report = apply_style_candidate(
        composition,
        plan,
        candidate["id"],
        approved=True,
    )

    assert report["transform_keyframes_preserved"] is True
    assert [
        (layer.id, layer.transform.to_dict(), layer.source.to_dict())
        for layer in result.layers
    ] == before_transform
    assert result.layers[0].effects[0].kind == "glow"
    assert result.layers[0].effects[0].metadata["manual"] is True
    assert result.metadata["ai_style_director"]["style_id"] == style_id
    assert composition.revision == 4


def test_style_candidate_requires_approval_and_rejects_stale_revision():
    composition = _composition()
    plan = _plan(composition)
    candidate = _candidate(plan, "craft")

    with pytest.raises(ValueError, match="explicit approval"):
        apply_style_candidate(composition, plan, candidate["id"], approved=False)
    composition.revision += 1
    with pytest.raises(ValueError, match="stale"):
        apply_style_candidate(composition, plan, candidate["id"], approved=True)


def test_style_apply_report_names_only_layers_with_visual_style_changes():
    composition = _composition()
    plan = _plan(composition)

    _craft_result, craft_report = apply_style_candidate(
        composition,
        plan,
        _candidate(plan, "craft")["id"],
        approved=True,
    )
    _glass_result, glass_report = apply_style_candidate(
        composition,
        plan,
        _candidate(plan, "glass")["id"],
        approved=True,
    )

    assert craft_report["visually_changed_layer_ids"] == ["hero", "title"]
    assert glass_report["visually_changed_layer_ids"] == ["hero"]


def test_style_lock_protects_layer_and_persists_brand_controls():
    composition = _composition()
    lock = set_style_lock(composition, {
        "font_family": "Noto Sans",
        "texture_uri": "paper.png",
        "seed": 99,
        "mascot_layer_ids": ["hero"],
        "protected_layer_ids": ["hero"],
    })
    plan = _plan(composition)
    craft = _candidate(plan, "craft")
    result, report = apply_style_candidate(
        composition,
        plan,
        craft["id"],
        approved=True,
    )

    assert lock["font_family"] == "Noto Sans"
    assert lock["seed"] == 99
    assert report["protected_layer_ids"] == ["hero"]
    assert not any(
        effect.metadata.get("style_director")
        for effect in result.layers[0].effects
    )
    assert any(
        effect.metadata.get("style_director")
        for effect in result.layers[1].effects
    )


def test_clean_candidate_only_removes_previous_style_director_data():
    composition = _composition()
    plan = _plan(composition)
    craft = _candidate(plan, "craft")
    styled, _report = apply_style_candidate(
        composition,
        plan,
        craft["id"],
        approved=True,
    )
    clean_plan = _plan(styled)
    clean = _candidate(clean_plan, "clean")
    cleaned, report = apply_style_candidate(
        styled,
        clean_plan,
        clean["id"],
        approved=True,
    )

    assert all(
        not effect.metadata.get("style_director")
        for layer in cleaned.layers
        for effect in layer.effects
    )
    assert cleaned.layers[0].effects[0].kind == "glow"
    assert report["visually_changed_layer_ids"] == ["hero", "title"]


def test_clean_candidate_reports_no_visual_change_on_unstyled_document():
    composition = _composition()
    plan = _plan(composition)

    _cleaned, report = apply_style_candidate(
        composition,
        plan,
        _candidate(plan, "clean")["id"],
        approved=True,
    )

    assert report["visually_changed_layer_ids"] == []


def test_story_plan_is_reviewed_stable_and_applies_all_beats():
    composition = _composition()
    plan = plan_story_direction(
        composition,
        'Tell a story and finish with "Try Tiger".',
    )
    assert plan["schema"] == STORY_PLAN_SCHEMA
    expected_ids = [row["id"] for row in plan["beats"]]

    result, report = apply_story_direction(composition, plan, approved=True)

    assert report["beat_count"] == 8
    assert [
        row["id"]
        for row in result.metadata["story_direction"]["beats"]
    ] == expected_ids
    assert result.metadata["story_direction"]["beats"][-1]["copy"] == "Try Tiger"


def test_trend_preflight_exposes_fallbacks_and_invalid_locks():
    composition = _composition()
    set_style_lock(composition, {"protected_layer_ids": ["missing"]})
    plan = _plan(composition)
    report = trend_preflight(composition, plan)

    assert report["ok"] is False
    assert report["summary"]["candidate_count"] == 5
    assert {row["code"] for row in report["warnings"]} == {
        "glass_gpu_fallback",
        "painterly_3d_unavailable",
    }
    assert report["issues"][0]["code"] == "style_lock_unknown_layers"


def test_style_preview_worker_renders_all_five_candidates_with_real_renderer(
    tmp_path,
):
    from app.motion_designer.ui.ai_worker import MotionAIStylePreviewWorker

    completed = []
    failed = []
    worker = MotionAIStylePreviewWorker(
        _composition(),
        {"prompt": "Premium tactile launch", "seed": 53},
        tmp_path,
    )
    worker.completed.connect(completed.append)
    worker.failed.connect(failed.append)
    worker.run()

    assert failed == []
    assert completed
    payload = completed[0]
    assert payload["schema"] == "tigerstudio.motion.ai_style_preview_set.v1"
    assert len(payload["previews"]) == 5
    assert all(row["render_source"] == "MotionExportRenderer" for row in payload["previews"])
    assert all(Path(row["thumbnail_path"]).is_file() for row in payload["previews"])
