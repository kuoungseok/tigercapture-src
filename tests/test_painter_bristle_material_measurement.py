from __future__ import annotations

import json
import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_m52_bristle_material_measurement_passes(tmp_path) -> None:
    from tools.measure_painter_bristle_material import main

    output = tmp_path / "m52.json"
    assert main(["--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert len(report["checks"]) == 27
    assert report["measurements"]["style_count"] == 13
    assert report["measurements"]["preview_export_max_delta_lsb"] <= 1
    assert report["claim_boundary"]["physical_bristle_or_rheology"] is False
    assert report["claim_boundary"]["external_product_pixel_parity"] is False
