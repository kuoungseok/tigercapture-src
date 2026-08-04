from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.motion_designer.performance_gate import (
    PERFORMANCE_GATE_SCHEMA,
    run_motion_performance_gate,
    stress_template_switches,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="Shape",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={"width": 80, "height": 60, "fill": "#24677f"},
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [64.0, 36.0]
    return MotionComposition(
        name="Performance Gate",
        width=128,
        height=72,
        duration_ms=1000,
        layers=[layer],
    )


def test_performance_gate_reports_determinism_timing_fallback_and_cache() -> None:
    QApplication.instance() or QApplication([])
    report = run_motion_performance_gate(
        _composition(),
        sample_times_ms=[0.0, 500.0],
        iterations=2,
        width=64,
        height=36,
        cache_max_bytes=1024 * 1024,
    )

    assert report["schema"] == PERFORMANCE_GATE_SCHEMA
    assert report["ok"] is True
    assert report["checks"]["deterministic_frames"] is True
    assert report["checks"]["cache_budget_and_hit"] is True
    assert report["render_count"] == 4
    assert report["timing"]["p95_ms"] >= 0.0
    assert sum(report["backend_counts"].values()) == 4
    assert len(report["frame_hashes"]) == 2


def test_template_switch_stress_does_not_accumulate_managed_layers() -> None:
    report = stress_template_switches(
        MotionComposition(width=320, height=180, duration_ms=1000),
        ["clean_lower_third", "character_nameplate"],
        iterations=6,
        variant="16:9",
        max_retained_bytes=128 * 1024 * 1024,
    )

    assert report["ok"] is True
    assert report["layer_growth"] == 0
    assert report["later_max_layers"] <= report["baseline_max_layers"]
