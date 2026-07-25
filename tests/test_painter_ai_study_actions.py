from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _reference(path: Path) -> None:
    image = Image.new("RGB", (160, 200), "#132341")
    draw = ImageDraw.Draw(image)
    draw.ellipse((82, 18, 148, 84), fill="#E7C46B")
    draw.polygon([(34, 176), (58, 52), (80, 176)], fill="#17251F")
    draw.rectangle((74, 116, 150, 184), fill="#B9AE91")
    draw.line((0, 126, 160, 126), fill="#7597B6", width=5)
    image.save(path)


def test_painter_study_actions_build_editable_layers_and_quality_report(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    reference = tmp_path / "study_reference.png"
    _reference(reference)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(256, 320, "#111827"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.study.analyze_reference",
        "paint.study.segment_regions",
        "paint.study.build_underpaint",
        "paint.study.trace_contours",
        "paint.study.generate_strokes",
        "paint.study.compare_render",
        "paint.study.refine_region",
        "paint.study.quality_report",
    } <= action_ids

    analyzed = registry.execute_action(
        "paint.study.analyze_reference",
        {
            "reference_path": str(reference),
            "target_width": 256,
            "region_count": 6,
            "seed": 17,
            "focus_regions": [
                {
                    "id": "subject",
                    "bbox_norm": [0.18, 0.20, 0.58, 0.92],
                    "priority": 2.0,
                }
            ],
        },
    ).to_dict()
    assert analyzed["ok"]
    assert analyzed["result"]["study"]["region_count"] == 6
    assert analyzed["result"]["study"]["focus_regions"][0]["id"] == "subject"

    segmented = registry.execute_action("paint.study.segment_regions", {}).to_dict()
    assert segmented["ok"]
    assert len(segmented["result"]["study"]["regions"]) == 6
    layer_count_before_failed_refine = len(dialog._paint_layers)
    failed_refine = registry.execute_action(
        "paint.study.refine_region",
        {"max_strokes": 20},
    ).to_dict()
    assert not failed_refine["ok"]
    assert len(dialog._paint_layers) == layer_count_before_failed_refine

    underpaint = registry.execute_action(
        "paint.study.build_underpaint",
        {"max_strokes": 120, "layer_name": "Study Underpaint"},
    ).to_dict()
    assert underpaint["ok"]
    assert underpaint["result"]["generated"]["stroke_count"] > 0

    forms = registry.execute_action(
        "paint.study.generate_strokes",
        {"phase": "forms", "max_strokes": 100, "layer_name": "Study Forms"},
    ).to_dict()
    assert forms["ok"]
    contours = registry.execute_action(
        "paint.study.trace_contours",
        {"max_strokes": 80, "layer_name": "Study Contours"},
    ).to_dict()
    assert contours["ok"]
    assert all(
        stroke.source_tool.startswith("ai_study_")
        for stroke in dialog.result_strokes()
    )

    compared = registry.execute_action("paint.study.compare_render", {}).to_dict()
    assert compared["ok"]
    comparison = compared["result"]["study"]
    assert comparison["mean_absolute_error"] >= 0.0
    assert -1.0 <= comparison["luminance_correlation"] <= 1.0

    refined = registry.execute_action(
        "paint.study.refine_region",
        {"max_strokes": 60, "layer_name": "Study Refinement"},
    ).to_dict()
    assert refined["ok"]
    report = registry.execute_action("paint.study.quality_report", {}).to_dict()
    assert report["ok"]
    assert report["result"]["study"]["status"] in {"ready", "needs_refinement"}
    assert not report["result"]["study"]["baked_reference_pixels"]
    assert len(report["result"]["study"]["generated_layers"]) == 4
    assert any(
        row["operation"] == "compare_render"
        for row in report["result"]["study"]["timings"]
    )
    before_undo = report["result"]["study"]["stroke_count"]
    undone = registry.execute_action("paint.history.undo", {}).to_dict()
    assert undone["ok"]
    after_undo = registry.execute_action("paint.study.quality_report", {}).to_dict()
    assert after_undo["result"]["study"]["stroke_count"] < before_undo
    assert len(after_undo["result"]["study"]["generated_layers"]) == 3
    redone = registry.execute_action("paint.history.redo", {}).to_dict()
    assert redone["ok"]
    after_redo = registry.execute_action("paint.study.quality_report", {}).to_dict()
    assert after_redo["result"]["study"]["stroke_count"] == before_undo
    assert len(after_redo["result"]["study"]["generated_layers"]) == 4
    dialog.close()


def test_painter_study_planner_is_deterministic_for_provider_replay(
    tmp_path: Path,
) -> None:
    _app()
    from app.painter_ai_study import analyze_reference, generate_phase_strokes

    reference = tmp_path / "deterministic_reference.png"
    _reference(reference)
    runtime_a, _ = analyze_reference(reference, target_width=256, seed=31)
    runtime_b, _ = analyze_reference(reference, target_width=256, seed=31)
    strokes_a = generate_phase_strokes(
        runtime_a,
        phase="forms",
        layer_id="paint-layer-test",
        max_strokes=24,
    )
    strokes_b = generate_phase_strokes(
        runtime_b,
        phase="forms",
        layer_id="paint-layer-test",
        max_strokes=24,
    )
    assert len(strokes_a) == len(strokes_b) == 24
    assert [stroke.points for stroke in strokes_a] == [stroke.points for stroke in strokes_b]
    assert [stroke.color for stroke in strokes_a] == [stroke.color for stroke in strokes_b]
    assert [stroke.brush_seed for stroke in strokes_a] == [
        stroke.brush_seed for stroke in strokes_b
    ]
