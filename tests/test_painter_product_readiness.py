from __future__ import annotations


def _complete_evidence():
    from app.painter_product_readiness import painting_scenarios

    return {
        row["id"]: {stage: True for stage in row["stages"]}
        for row in painting_scenarios()
    }


def test_product_readiness_requires_every_real_workflow_stage() -> None:
    from app.painter_product_readiness import evaluate_painting_readiness

    evidence = _complete_evidence()
    report = evaluate_painting_readiness(
        evidence, tests_passed=True, recovery_passed=True, stress_passed=True
    )
    assert report["passed"] is True
    assert report["release_ready"] is False
    assert report["classification"] == "automated_baseline_only"
    assert report["scope"] == "painting_only"
    evidence["character"]["render"] = False
    report = evaluate_painting_readiness(
        evidence, tests_passed=True, recovery_passed=True, stress_passed=True
    )
    assert report["passed"] is False
    assert report["missing"] == ["character.render"]
    assert set(evidence["stress"]) == {"large_stroke_render", "bounded_tile_cache", "reopen"}
    assert set(evidence["display_input"]) == {
        "offscreen_window_760x560",
        "offscreen_window_1080p",
        "simulated_high_dpi_layout",
        "4k_tile_cardinality",
        "synthetic_tablet_channel_roundtrip",
    }


def test_product_readiness_never_claims_full_competitor_parity() -> None:
    from app.painter_product_readiness import painting_known_limitations

    rows = {row["id"]: row["text"] for row in painting_known_limitations()}
    assert "No full Photoshop" in rows["parity"]
    assert "device-specific" in rows["tablet_hardware"]
    assert "blocked or explicitly baked" in rows["psd_advanced"]


def test_support_matrix_declares_precision_color_and_psd_boundaries() -> None:
    from app.painter_product_readiness import painting_support_matrix

    matrix = painting_support_matrix()
    assert matrix["flat_export"]["PNG"]["bits"] == (8, 16)
    assert matrix["color"]["working_space"] == "sRGB"
    assert matrix["layered_exchange"]["PSD"]["policy_for_unsupported"] == (
        "blocked", "explicit_bake"
    )


def test_release_readiness_requires_provenance_not_boolean_only() -> None:
    from app.painter_evidence_contract import RELEASE_CLAIM_REQUIREMENTS, evidence_record
    from app.painter_product_readiness import evaluate_painting_readiness

    records = [
        evidence_record(
            f"qa-{claim_id}",
            kinds[0],
            passed=True,
            producer="independent-qa",
            claims=(claim_id,),
        )
        for claim_id, kinds in RELEASE_CLAIM_REQUIREMENTS.items()
    ]
    report = evaluate_painting_readiness(
        _complete_evidence(),
        tests_passed=True,
        recovery_passed=True,
        stress_passed=True,
        evidence_records=records,
    )
    assert report["passed"] is True
    assert report["release_ready"] is True
    assert report["classification"] == "release_evidence"
