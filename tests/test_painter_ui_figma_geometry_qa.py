from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _classification_payload() -> dict:
    return {
        "name": "Geometry classification",
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "name": "Page",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "1:1",
                            "name": "Board",
                            "type": "FRAME",
                            "absoluteBoundingBox": {
                                "x": 100,
                                "y": 200,
                                "width": 300,
                                "height": 180,
                            },
                            "children": [
                                {
                                    "id": "1:2",
                                    "name": "Flow",
                                    "type": "FRAME",
                                    "layoutMode": "HORIZONTAL",
                                    "layoutWrap": "WRAP",
                                    "primaryAxisAlignItems": "CENTER",
                                    "itemSpacing": -10,
                                    "absoluteBoundingBox": {
                                        "x": 110,
                                        "y": 210,
                                        "width": 220,
                                        "height": 100,
                                    },
                                    "children": [
                                        {
                                            "id": "1:3",
                                            "name": "First",
                                            "type": "RECTANGLE",
                                            "constraints": {
                                                "horizontal": "MAX",
                                                "vertical": "MIN",
                                            },
                                            "absoluteBoundingBox": {
                                                "x": 120,
                                                "y": 220,
                                                "width": 40,
                                                "height": 30,
                                            },
                                        },
                                        {
                                            "id": "1:4",
                                            "name": "Second",
                                            "type": "RECTANGLE",
                                            "absoluteBoundingBox": {
                                                "x": 170,
                                                "y": 220,
                                                "width": 40,
                                                "height": 30,
                                            },
                                        },
                                        {
                                            "id": "1:5",
                                            "name": "Sheared",
                                            "type": "RECTANGLE",
                                            "relativeTransform": [
                                                [1.0, 0.25, 220.0],
                                                [0.0, 1.0, 220.0],
                                            ],
                                            "absoluteBoundingBox": {
                                                "x": 220,
                                                "y": 220,
                                                "width": 40,
                                                "height": 30,
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }


def _classification_document() -> dict:
    artboard_id = "figma-artboard-1-1"
    return {
        "active_artboard_id": artboard_id,
        "artboards": [
            {
                "id": artboard_id,
                "name": "Board",
                "x": 0,
                "y": 0,
                "width": 300,
                "height": 180,
            }
        ],
        "objects": [
            {
                "id": "figma-node-1-2",
                "name": "Flow",
                "kind": "frame",
                "artboard_id": artboard_id,
                "parent_id": "",
                "x": 10,
                "y": 10,
                "width": 220,
                "height": 100,
                "rotation": 0,
                "constraints": {"horizontal": "left", "vertical": "top"},
                "layout": {"mode": "horizontal", "wrap": True},
                "content": {},
            },
            {
                "id": "figma-node-1-3",
                "name": "First",
                "kind": "rectangle",
                "artboard_id": artboard_id,
                "parent_id": "figma-node-1-2",
                "x": 20,
                "y": 20,
                "width": 40,
                "height": 30,
                "rotation": 0,
                "constraints": {"horizontal": "right", "vertical": "top"},
                "layout": {},
                "content": {},
            },
            {
                "id": "figma-node-1-4",
                "name": "Second",
                "kind": "rectangle",
                "artboard_id": artboard_id,
                "parent_id": "figma-node-1-2",
                "x": 70,
                "y": 20,
                "width": 40,
                "height": 30,
                "rotation": 0,
                "constraints": {"horizontal": "left", "vertical": "top"},
                "layout": {},
                "content": {},
            },
            {
                "id": "figma-node-1-5",
                "name": "Sheared",
                "kind": "rectangle",
                "artboard_id": artboard_id,
                "parent_id": "figma-node-1-2",
                "x": 120,
                "y": 20,
                "width": 40,
                "height": 30,
                "rotation": 0,
                "constraints": {"horizontal": "left", "vertical": "top"},
                "layout": {},
                "content": {},
            },
        ],
    }


def test_geometry_measurement_classifies_drift_and_keeps_report_only_default() -> None:
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    document = _classification_document()
    resolved = {
        "figma-node-1-2": {"x": 10, "y": 10, "width": 220, "height": 100},
        # Swap the two direct children along the parent's main axis.
        "figma-node-1-3": {"x": 120, "y": 20, "width": 40, "height": 30},
        "figma-node-1-4": {"x": 20, "y": 20, "width": 40, "height": 30},
        "figma-node-1-5": {"x": 120, "y": 20, "width": 40, "height": 30},
    }

    report = measure_figma_geometry(
        _classification_payload(),
        document,
        resolved_geometry=resolved,
    )

    assert report["gate"] == {
        "enabled": False,
        "passed": None,
        "mode": "report_only",
        "violations": [],
    }
    assert report["measured_count"] == 3
    assert report["drifted_count"] == 2
    assert report["excluded_count"] == 1
    assert report["known_blocked_excluded_count"] == 1
    assert report["unexpected_excluded_count"] == 0
    assert report["excluded_reason_counts"] == {
        "source_affine_shear_not_exactly_comparable": 1,
    }
    assert report["cause_counts"]["center"] == 2
    assert report["cause_counts"]["wrap"] == 2
    assert report["cause_counts"]["negative_spacing"] == 2
    assert report["cause_counts"]["reverse_order"] == 2
    assert report["cause_counts"]["constraints"] == 1
    assert report["drifts"][0]["parent_id"] == "figma-node-1-2"
    assert report["drifts"][0]["center_delta"]["distance"] > 0
    assert report["drifts"][0]["edge_delta"]
    assert report["drifts"][0]["rotation"]["delta_degrees"] == 0
    parent = next(
        row
        for row in report["by_parent"]
        if row["parent_id"] == "figma-node-1-2"
    )
    assert parent["drifted_count"] == 2
    assert parent["excluded_count"] == 1
    assert report["by_artboard"][0]["drifted_count"] == 2


def test_geometry_measurement_gate_is_explicit_and_count_bounded() -> None:
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    document = _classification_document()
    resolved = {
        "figma-node-1-2": {"x": 10, "y": 10, "width": 220, "height": 100},
        "figma-node-1-3": {"x": 120, "y": 20, "width": 40, "height": 30},
        "figma-node-1-4": {"x": 20, "y": 20, "width": 40, "height": 30},
        "figma-node-1-5": {"x": 120, "y": 20, "width": 40, "height": 30},
    }

    strict = measure_figma_geometry(
        _classification_payload(),
        document,
        resolved_geometry=resolved,
        max_drift_px=10,
        max_large_drift_count=0,
    )
    baseline = measure_figma_geometry(
        _classification_payload(),
        document,
        resolved_geometry=resolved,
        max_drift_px=10,
        max_large_drift_count=2,
        max_known_blocked_excluded_count=1,
        max_unexpected_excluded_count=0,
    )

    assert strict["gate"]["enabled"] is True
    assert strict["gate"]["passed"] is False
    assert strict["gate"]["observed_large_drift_count"] == 2
    assert baseline["gate"]["passed"] is True


def test_real_constraint_resolution_exposes_negative_spacing_drift() -> None:
    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    payload = {
        "name": "Negative gap",
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "name": "Page",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "2:1",
                            "name": "Board",
                            "type": "FRAME",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 240,
                                "height": 120,
                            },
                            "children": [
                                {
                                    "id": "2:2",
                                    "name": "Negative stack",
                                    "type": "FRAME",
                                    "layoutMode": "HORIZONTAL",
                                    "itemSpacing": -20,
                                    "absoluteBoundingBox": {
                                        "x": 10,
                                        "y": 10,
                                        "width": 180,
                                        "height": 60,
                                    },
                                    "children": [
                                        {
                                            "id": "2:3",
                                            "name": "A",
                                            "type": "RECTANGLE",
                                            "absoluteBoundingBox": {
                                                "x": 10,
                                                "y": 10,
                                                "width": 60,
                                                "height": 40,
                                            },
                                        },
                                        {
                                            "id": "2:4",
                                            "name": "B",
                                            "type": "RECTANGLE",
                                            "absoluteBoundingBox": {
                                                "x": 50,
                                                "y": 10,
                                                "width": 60,
                                                "height": 40,
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }
    document, _import_report = import_figma_payload(payload)
    # Simulate the historical regression where normalization clamped a
    # negative Figma gap to zero. The production importer currently preserves
    # the value; the measurement gate must still diagnose any recurrence.
    stack = next(row for row in document["objects"] if row["id"] == "figma-node-2-2")
    stack["layout"]["gap"] = 0.0

    report = measure_figma_geometry(payload, document)

    assert report["drifted_count"] >= 1
    assert report["cause_counts"]["negative_spacing"] >= 1
    assert report["max_drift_px"] >= 20


def test_hidden_degenerate_source_geometry_is_an_explicit_blocker() -> None:
    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    payload = {
        "name": "Hidden zero-height text",
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "name": "Page",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "2:1",
                            "name": "Board",
                            "type": "FRAME",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 240,
                                "height": 120,
                            },
                            "children": [
                                {
                                    "id": "2:2",
                                    "name": "Hidden instance content",
                                    "type": "FRAME",
                                    "visible": False,
                                    "layoutMode": "HORIZONTAL",
                                    "layoutSizingHorizontal": "HUG",
                                    "layoutSizingVertical": "HUG",
                                    "absoluteBoundingBox": {
                                        "x": 20,
                                        "y": 20,
                                        "width": 108,
                                        "height": 48,
                                    },
                                    "children": [
                                        {
                                            "id": "2:3",
                                            "name": "Empty override text",
                                            "type": "TEXT",
                                            "characters": "",
                                            "absoluteBoundingBox": {
                                                "x": 89,
                                                "y": 44,
                                                "width": 23,
                                                "height": 0,
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }
    document, _import_report = import_figma_payload(payload)

    report = measure_figma_geometry(payload, document)

    assert report["measured_count"] == 1
    assert report["drifted_count"] == 0
    assert report["excluded_count"] == 1
    assert report["known_blocked_excluded_count"] == 1
    assert report["unexpected_excluded_count"] == 0
    assert report["excluded_reason_counts"] == {
        "source_hidden_degenerate_bounding_box_nonrendered": 1,
    }


def test_geometry_corpus_runner_writes_report_without_enabling_gate(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_geometry import run_geometry_corpus

    payload = _classification_payload()
    encoded = json.dumps(payload).encode("utf-8")
    commit = "1" * 40
    manifest = {
        "schema": "tigercapture.painter.figma_document_corpus.v1",
        "cases": [
            {
                "id": "geometry.sample",
                "title": "Geometry sample",
                "format": "figma_rest_file",
                "source": {
                    "repository": "example/geometry",
                    "commit": commit,
                    "path": "source.json",
                    "url": (
                        "https://raw.githubusercontent.com/example/geometry/"
                        f"{commit}/source.json"
                    ),
                    "html_url": "https://github.com/example/geometry",
                    "license": "MIT",
                    "license_url": "https://github.com/example/geometry/LICENSE",
                    "attribution": "Geometry fixture",
                },
                "artifact": {
                    "relative_path": "geometry.sample/source.json",
                    "bytes": len(encoded),
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                },
                "expectations": {
                    "min_artboards": 1,
                    "min_objects": 1,
                    "required_source_features": [],
                    "preserve_features": [],
                },
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "geometry.sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_geometry_corpus(
        [manifest_path],
        tmp_path / "assets",
        tmp_path / "output",
    )

    assert report["processing_ok"] is True
    assert report["passed"] is True
    assert report["gate"]["mode"] == "report_only"
    assert report["threshold_suggestions"]["m1_target"] == {
        "max_drift_px": 1.0,
        "max_large_drift_count": 0,
        "max_known_blocked_excluded_count": report[
            "known_blocked_excluded_count"
        ],
        "max_unexpected_excluded_count": 0,
        "purpose": (
            "one-pixel fidelity with zero instrumentation exclusions; "
            "explicit source/contract blockers may remain at or below baseline"
        ),
    }
    written = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert written["schema"] == "tigercapture.painter.figma_geometry_corpus_report.v1"
    assert written["case_count"] == 1
