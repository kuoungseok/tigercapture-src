from __future__ import annotations


def test_creative_layer_readiness_report_blocks_full_suite_claim():
    from app.creative_layer_readiness import (
        build_creative_layer_readiness_report,
        format_creative_layer_readiness_summary,
    )

    actions = {
        "clip.set_filter",
        "transition.apply",
        "transition.clear",
        "text.add",
        "text.set_keyframes",
        "node.graph.set",
        "node.add",
        "node.connect",
        "node.set_param",
        "node.delete",
        "actor.add",
        "actor.set_transform",
        "actor.set_keyframes",
    }
    presets = {
        "by_kind": {
            "effect": 36,
            "transition": 30,
            "title": 34,
            "actor": 8,
            "sticker": 12,
            "template": 12,
        }
    }
    report = build_creative_layer_readiness_report(
        {"summary": {"video_clip_count": 2}},
        action_ids=actions,
        preset_summary=presets,
    )
    summary = format_creative_layer_readiness_summary(report)

    assert report["schema"] == "tigerstudio.creative_layer_readiness.v1"
    assert report["full_creative_suite_claim_ok"] is False
    assert "Full creative-suite claim: not allowed" in summary
    assert {
        "effects_filter_stack",
        "transition_workflow",
        "typography_motion",
        "node_graph_productization",
        "live2d_spine_actor_workflow",
        "ar_pbr_3d_compositing",
        "template_ecosystem",
    } <= {row["id"] for row in report["rows"]}
    assert "ar_pbr_3d_compositing" in report["blockers"]


def test_creative_layer_readiness_uses_ar_pbr_full_gpu_smoke_evidence():
    from app.creative_layer_readiness import build_creative_layer_readiness_report

    report = build_creative_layer_readiness_report(
        {},
        ar_pbr_full_gpu_report={
            "full_gpu_export_available": True,
            "smoke_render": {
                "ok": True,
                "mode": "full_model_view_gpu_export_service",
                "fallback": False,
            },
        },
    )

    ar_row = next(row for row in report["rows"] if row["id"] == "ar_pbr_3d_compositing")
    assert ar_row["score"] >= 60
    assert "ar_pbr_3d_compositing" not in report["blockers"]
    assert report["full_creative_suite_claim_ok"] is False


def test_creative_layer_readiness_qa_payload_is_json_ready():
    from tools.qa_creative_layer_readiness import run_creative_layer_readiness_qa

    payload = run_creative_layer_readiness_qa()

    assert payload["kind"] == "creative_layer_readiness"
    assert payload["ok"] is True
    assert payload["release_claim_gate_ok"] is False
    assert payload["report"]["schema"] == "tigerstudio.creative_layer_readiness.v1"
