from __future__ import annotations

import json


def test_m54_action_schema_resource_measurement_passes(tmp_path) -> None:
    from tools.measure_painter_action_schema_resources import main

    output = tmp_path / "m54.json"
    assert main(["--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["scope"] == "painting_only_ui_design_excluded"
    assert report["passed"] is True
    assert report["checks_passed"] == report["checks_total"] == 15
    assert all(report["checks"].values())
    measurements = report["measurements"]
    assert [
        row["width"] for row in measurements["cpu_generation"]
    ] == [64, 256, 512, 1024]
    assert measurements["projected_2048_unique_retained_array_bytes"] > (
        measurements["authored_retained_array_budget_bytes"]
    )
    assert report["claim_boundary"][
        "universal_latency_or_memory_safety_claim"
    ] is False
    assert report["claim_boundary"]["gpu_parity_claim"] is False
    assert report["claim_boundary"]["visual_quality_threshold_claim"] is False
