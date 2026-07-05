from app.product_gap_push import PUSH_ORDER, build_product_gap_push_report


def test_product_gap_push_preserves_requested_order_and_truth() -> None:
    report = build_product_gap_push_report()

    assert report["kind"] == "product_gap_push"
    assert report["requested_order"] == [3, 4, 5, 1, 2, 6]
    assert [row["id"] for row in report["areas"]] == list(PUSH_ORDER)
    assert report["all_requested_areas_covered"] is True
    assert report["ok"] is True
    assert "does not turn missing real-world corpus" in report["truth"]


def test_product_gap_push_separates_implementation_from_claim_ready() -> None:
    report = build_product_gap_push_report()
    areas = {row["id"]: row for row in report["areas"]}

    assert areas["ai_editing_quality"]["label"].startswith("3.")
    assert areas["real_recording_corpus"]["label"].startswith("4.")
    assert areas["capcut_template_scale"]["label"].startswith("5.")
    assert areas["gpu_preview_export_parity"]["label"].startswith("1.")
    assert areas["ar_pbr_renderer_quality"]["label"].startswith("2.")
    assert areas["release_trust"]["label"].startswith("6.")
    assert isinstance(report["implementation_ready"], bool)
    assert isinstance(report["claim_ready"], bool)
    assert isinstance(report["next_actions"], (list, tuple))
    assert areas["ai_editing_quality"]["evidence"]["provider"]["use_provider"] is True
    assert "descript_lite_readiness" in areas["ai_editing_quality"]["evidence"]
    assert areas["ai_editing_quality"]["evidence"]["descript_lite_readiness"]["descript_lite_claim_ready"] is True
    assert "sidecar_intake_summary" in areas["real_recording_corpus"]["evidence"]
    assert "next_sidecar_capture" in areas["real_recording_corpus"]["evidence"]
    assert "release_evidence_progress" in areas["real_recording_corpus"]["evidence"]
    assert areas["ar_pbr_renderer_quality"]["evidence"]["checks"]["full_gpu_export_service_contract"] is True
    assert isinstance(areas["ar_pbr_renderer_quality"]["evidence"]["checks"]["full_model_view_gpu_export"], bool)
    assert "full_gpu_export_service" in areas["ar_pbr_renderer_quality"]["evidence"]
