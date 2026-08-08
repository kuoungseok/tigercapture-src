from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.ai_planner import analyze_motion_ai_layers
from app.motion_designer.ai_workspace import MotionAIReference, build_motion_ai_proposal
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def test_ai_dry_run_reports_cost_missing_assets_and_bake_requirements() -> None:
    composition = MotionComposition(width=1280, height=720, duration_ms=3000)
    proposal = build_motion_ai_proposal(composition, references=[
        MotionAIReference(kind="image", name="missing.png", uri="C:/missing-motion-reference.png"),
        MotionAIReference(kind="text", name="copy.txt", text="MOTION TITLE"),
    ])
    analysis = proposal.analysis
    assert analysis["schema"] == "tigercapture.motion.ai.analysis.v1"
    assert analysis["created_layer_count"] == 2
    assert analysis["renderer_cost"]["grade"] == "realtime"
    assert analysis["missing_assets"][0]["uri"].endswith("missing-motion-reference.png")
    assert any("relink" in warning for warning in proposal.warnings)


def test_ai_analysis_marks_character_source_as_broadcast_cache_required() -> None:
    composition = MotionComposition(duration_ms=2000)
    layer = MotionLayer(
        name="Avatar", layer_type="vrm_actor", out_ms=2000,
        source=SourceRef(kind="vrm_actor", uri="C:/missing-avatar.vrm"),
    )
    analysis = analyze_motion_ai_layers(composition, [layer])
    assert analysis["renderer_cost"]["grade"] == "cached"
    assert analysis["bake_requirements"][0]["requirement"] == "broadcast_alpha_cache"
    assert analysis["missing_assets"][0]["kind"] == "vrm_actor"


def test_motion_ai_action_returns_analysis_without_mutating_project() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {"comp": MotionComposition(id="comp")}

    owner = Owner()
    registry = ActionRegistry(owner)
    planned = registry.execute("motion.ai.plan", {
        "composition_id": "comp",
        "prompt": 'fade in "AI TITLE"',
        "references": [{"kind": "image", "name": "missing.png", "uri": "C:/missing.png"}],
    })
    assert planned.ok
    assert planned.result["analysis"]["created_layer_count"] == 2
    assert planned.result["analysis"]["renderer_cost"]["cost_units"] > 0
    assert owner._motion_compositions["comp"].layers == []
