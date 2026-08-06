from __future__ import annotations

import json


def test_m53_persistence_exchange_measurement_passes(tmp_path) -> None:
    from tools.measure_painter_persistence_exchange import main

    output = tmp_path / "m53.json"
    assert main(["--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))

    assert report["scope"] == "painting_only_ui_design_excluded"
    assert report["passed"] is True
    assert report["checks_passed"] == report["checks_total"] == 18
    assert all(report["checks"].values())
    assert report["measurements"]["uint16_values_checked"] == 65536
    assert report["claim_boundary"]["external_application_interoperability_certified"] is False
    assert report["claim_boundary"]["power_loss_atomicity_claim"] is False
    assert report["claim_boundary"]["universal_recovery_capacity_claim"] is False
    assert report["claim_boundary"]["universal_print_quality_or_bleed_claim"] is False
