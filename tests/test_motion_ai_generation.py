from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.actions.registry import ActionRegistry
from app.ai_providers import generate_selected_provider_json
from app.motion_designer.ai_generation import (
    MOTION_AI_GENERATION_SCHEMA,
    MotionAIContractError,
    apply_motion_ai_patch,
    build_deterministic_generation_plan,
    compile_generation_plan,
    generate_motion_ai_patch,
    generate_motion_ai_proposal,
    validate_motion_generation_plan,
)
from app.motion_designer.ai_workspace import MotionAIReference, apply_motion_ai_proposal
from app.motion_designer.schema import MotionComposition


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}
        self._motion_clips = []
        self._player = SimpleNamespace(refresh_current_frame=lambda: None)

    def _sync_motion_state_to_player(self) -> None:
        return None

    def _rebuild_motion_lanes(self) -> None:
        return None


def test_shared_provider_json_contract_returns_validated_safe_baseline() -> None:
    baseline = {"schema": "example.v1", "value": 7}

    def validate(value):
        assert set(value) == {"schema", "value"}
        assert value["schema"] == "example.v1"
        return dict(value)

    result = generate_selected_provider_json(
        "test_contract",
        "keep this safe",
        output_contract={"schema": "example.v1", "keys": ["schema", "value"]},
        input_payload={},
        safe_baseline=baseline,
        validate_payload=validate,
        provider_id="rule_based",
    )
    assert result.ok is True
    assert result.provider == "rule_based"
    assert result.payload == baseline
    assert result.metadata["effective_generation_provider"] == "rule_based"


def test_motion_generation_compiles_storyboard_to_editable_layers() -> None:
    composition = MotionComposition(width=1280, height=720, duration_ms=3600)
    references = [
        MotionAIReference(kind="image", name="hero.png", uri="C:/missing/hero.png"),
        MotionAIReference(kind="text", name="copy.txt", text="Second line"),
    ]
    proposal = generate_motion_ai_proposal(
        composition,
        'cinematic fade "TIGER MOTION"',
        references,
        provider_id="rule_based",
    )
    plan = proposal.analysis["generation_plan"]
    assert plan["schema"] == MOTION_AI_GENERATION_SCHEMA
    assert plan["base_revision"] == composition.revision
    assert plan["brief"]["title"] == "TIGER MOTION"
    assert plan["beats"]
    assert proposal.provider == "rule_based"
    assert any(layer.layer_type == "image" for layer in proposal.layers)
    assert any(layer.layer_type == "text" for layer in proposal.layers)
    assert composition.layers == []

    applied = apply_motion_ai_proposal(composition, proposal)
    assert applied.revision == composition.revision + 1
    assert all(layer.metadata.get("ai_beat_id") for layer in applied.layers)


def test_storyboard_behaviors_use_layer_local_time() -> None:
    composition = MotionComposition(width=1280, height=720, duration_ms=3600)
    reference = MotionAIReference(kind="image", name="hero.png", uri="C:/missing/hero.png")
    plan = build_deterministic_generation_plan(composition, 'cinematic fade "TITLE"', [reference])
    plan.beats[0].start_ms = 1_200
    plan.beats[0].end_ms = 3_600

    proposal = compile_generation_plan(
        composition, plan, [reference], provider="rule_based",
    )
    later_layers = [layer for layer in proposal.layers if layer.in_ms > 0 and layer.behaviors]
    assert later_layers
    assert all(layer.behaviors[0].start_ms == 0 for layer in later_layers)
    assert all(0 < layer.behaviors[0].end_ms <= layer.out_ms - layer.in_ms for layer in later_layers)


def test_motion_generation_rejects_provider_commands_and_stale_apply() -> None:
    composition = MotionComposition(duration_ms=2000)
    plan = build_deterministic_generation_plan(composition, "fade", [])
    unsafe = plan.to_dict()
    unsafe["metadata"] = {"shell": "remove files"}
    with pytest.raises(MotionAIContractError, match="forbidden key"):
        validate_motion_generation_plan(unsafe, composition=composition)

    proposal = generate_motion_ai_proposal(composition, 'fade "Title"', [], provider_id="rule_based")
    composition.revision += 1
    with pytest.raises(ValueError, match="stale composition revision"):
        apply_motion_ai_proposal(composition, proposal)


def test_motion_patch_is_layer_scoped_and_applies_as_one_revision() -> None:
    composition = MotionComposition(duration_ms=3000)
    proposal = generate_motion_ai_proposal(composition, 'fade "Before"', [], provider_id="rule_based")
    composition = apply_motion_ai_proposal(composition, proposal)
    text_layer = next(layer for layer in composition.layers if layer.layer_type == "text")

    patch = generate_motion_ai_patch(
        composition,
        'make it bigger and fade "After"',
        [text_layer.id],
        provider_id="rule_based",
    )
    assert {item["layer_id"] for item in patch["operations"]} == {text_layer.id}
    changed = apply_motion_ai_patch(composition, patch)
    updated = next(layer for layer in changed.layers if layer.id == text_layer.id)
    assert changed.revision == composition.revision + 1
    assert updated.source.params["text"] == "After"
    assert updated.transform.scale.default[0] > text_layer.transform.scale.default[0]
    assert updated.behaviors[0].kind == "fade"

    stale = dict(patch)
    with pytest.raises(MotionAIContractError, match="stale composition revision"):
        apply_motion_ai_patch(changed, stale)


def test_motion_ai_generation_actions_expose_review_before_apply_contract() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute("motion.composition.create", {
        "name": "AI Contract", "width": 1080, "height": 1080, "duration_ms": 2400,
    })
    composition_id = created.result["payload"]["composition"]["id"]
    candidate = registry.execute("motion.ai.candidate.generate", {
        "composition_id": composition_id,
        "prompt": 'clean fade "Review Me"',
        "provider": "rule_based",
    })
    assert candidate.ok
    assert candidate.result["analysis"]["generation_plan"]["brief"]["title"] == "Review Me"
    assert owner._motion_compositions[composition_id].layers == []

    applied = registry.execute("motion.ai.apply", {
        "composition_id": composition_id,
        "proposal": candidate.result,
    })
    assert applied.ok
    layer_id = next(
        layer.id for layer in owner._motion_compositions[composition_id].layers if layer.layer_type == "text"
    )
    patch = registry.execute("motion.ai.patch.plan", {
        "composition_id": composition_id,
        "prompt": 'fade "Approved"',
        "layer_ids": [layer_id],
        "provider": "rule_based",
    })
    assert patch.ok
    patched = registry.execute("motion.ai.patch.apply", {
        "composition_id": composition_id,
        "patch": patch.result,
    })
    assert patched.ok
    assert patched.result["operation_count"] == 2

    action_ids = {item["id"] for item in registry.list_actions()}
    assert {
        "motion.ai.provider.status",
        "motion.ai.reference.analyze",
        "motion.ai.brief.create",
        "motion.ai.storyboard.generate",
        "motion.ai.candidate.generate",
        "motion.ai.patch.plan",
        "motion.ai.patch.apply",
    } <= action_ids
