from __future__ import annotations

import json
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _mixed_stroke_payload() -> dict:
    return {
        "name": "Mixed stroke fixture",
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
                            "name": "Artboard",
                            "type": "FRAME",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 64,
                                "height": 64,
                            },
                            "children": [
                                {
                                    "id": "1:2",
                                    "name": "Mixed border",
                                    "type": "RECTANGLE",
                                    "absoluteBoundingBox": {
                                        "x": 10,
                                        "y": 10,
                                        "width": 20,
                                        "height": 20,
                                    },
                                    "size": {"x": 20, "y": 20},
                                    "fills": [
                                        {
                                            "type": "SOLID",
                                            "color": {
                                                "r": 0.75,
                                                "g": 0.75,
                                                "b": 0.75,
                                                "a": 1,
                                            },
                                        }
                                    ],
                                    "fillGeometry": [
                                        {
                                            "path": "M0 0H20V20H0Z",
                                            "windingRule": "NONZERO",
                                        }
                                    ],
                                    "strokes": [
                                        {
                                            "type": "SOLID",
                                            "color": {
                                                "r": 0,
                                                "g": 0,
                                                "b": 0,
                                                "a": 1,
                                            },
                                        }
                                    ],
                                    # Figma strokeGeometry is centered even
                                    # when strokeAlign is INSIDE. These four
                                    # expanded side polygons therefore extend
                                    # both inside and outside the fill shape.
                                    "strokeGeometry": [
                                        {
                                            "path": (
                                                "M-4 -5H23L17 5H4Z "
                                                "M23 22H-4L4 18H17Z "
                                                "M-4 22V-5L4 5V18Z "
                                                "M23 -5V22L17 18V5Z"
                                            ),
                                            "windingRule": "NONZERO",
                                        }
                                    ],
                                    "strokeWeight": 1,
                                    "individualStrokeWeights": {
                                        "top": 5,
                                        "right": 3,
                                        "bottom": 2,
                                        "left": 4,
                                    },
                                    "strokeAlign": "INSIDE",
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }


def test_figma_mixed_strokes_survive_import_and_document_roundtrip() -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_document_corpus import (
        imported_feature_inventory,
        source_feature_inventory,
    )

    payload = _mixed_stroke_payload()
    document, report = import_figma_payload(payload)
    row = document["objects"][0]

    assert row["style"]["individual_stroke_weights"] == {
        "top": 5.0,
        "right": 3.0,
        "bottom": 2.0,
        "left": 4.0,
    }
    assert row["content"]["figma_stroke_geometry"] == {
        "representation": "expanded_outline",
        "source": "strokeGeometry",
        "viewport": {"width": 20.0, "height": 20.0},
    }
    assert (
        "converted:1:2:STROKE:"
        "individual_stroke_weights_rendered_from_expanded_geometry"
        in report["warnings"]
    )

    roundtrip = normalize_ui_document(json.loads(json.dumps(document)))
    assert roundtrip["objects"][0]["style"]["individual_stroke_weights"] == (
        row["style"]["individual_stroke_weights"]
    )
    assert roundtrip["objects"][0]["content"]["figma_stroke_geometry"] == (
        row["content"]["figma_stroke_geometry"]
    )
    source_features = source_feature_inventory(payload)["features"]
    imported_features = imported_feature_inventory(document)
    assert source_features["individual_stroke_weights"] == 1
    assert source_features["stroke_geometry"] == 1
    assert imported_features["individual_stroke_weights"] == 1
    assert imported_features["stroke_geometry"] == 1


def test_figma_centered_stroke_geometry_is_clipped_to_inside_alignment() -> None:
    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_figma import import_figma_payload

    _app()
    document, _report = import_figma_payload(_mixed_stroke_payload())
    image = render_ui_artboard(document, document["active_artboard_id"])

    # The centered expanded outline is clipped to the rectangle. The authored
    # per-edge widths are top=5, right=3, bottom=2, left=4 pixels.
    assert image.pixelColor(20, 12).name() == "#000000"
    assert image.pixelColor(20, 16).name() == "#bfbfbf"
    assert image.pixelColor(12, 20).name() == "#000000"
    assert image.pixelColor(15, 20).name() == "#bfbfbf"
    assert image.pixelColor(28, 20).name() == "#000000"
    assert image.pixelColor(26, 20).name() == "#bfbfbf"
    assert image.pixelColor(20, 29).name() == "#000000"
    assert image.pixelColor(20, 27).name() == "#bfbfbf"
    assert image.pixelColor(20, 8).name() == "#ffffff"


def test_figma_centered_stroke_geometry_is_subtracted_for_outside_alignment() -> None:
    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_figma import import_figma_payload

    _app()
    payload = _mixed_stroke_payload()
    node = payload["document"]["children"][0]["children"][0]["children"][0]
    node["strokeAlign"] = "OUTSIDE"
    document, _report = import_figma_payload(payload)
    image = render_ui_artboard(document, document["active_artboard_id"])

    assert image.pixelColor(20, 8).name() == "#000000"
    assert image.pixelColor(20, 12).name() == "#bfbfbf"
    assert image.pixelColor(8, 20).name() == "#000000"
    assert image.pixelColor(12, 20).name() == "#bfbfbf"


def test_figma_mixed_and_non_miter_strokes_are_explicit_umg_blockers() -> None:
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_umg_adapter import preflight_painter_umg

    payload = _mixed_stroke_payload()
    node = payload["document"]["children"][0]["children"][0]["children"][0]
    node["strokeJoin"] = "ROUND"
    node["strokeCap"] = "ROUND"
    node["strokeDashes"] = [4, 2]
    node["strokeMiterAngle"] = 7.0
    document, _report = import_figma_payload(payload)

    preflight = preflight_painter_umg(document)
    blocker = next(
        row for row in preflight["blockers"] if row["object_id"] == "figma-node-1-2"
    )
    assert {
        "figma_individual_stroke_weights_require_deterministic_bake",
        "figma_dashed_stroke_requires_deterministic_bake",
        "figma_stroke_cap_requires_deterministic_bake",
        "figma_stroke_join_requires_deterministic_bake",
        "figma_stroke_miter_angle_requires_deterministic_bake",
    } <= set(blocker["reasons"])


def test_figma_export_code_restores_individual_edges_and_line_style() -> None:
    from app.painter_ui_figma import _plugin_code, import_figma_payload

    document, _report = import_figma_payload(_mixed_stroke_payload())
    source = _plugin_code({"document": document, "assets": {}})

    assert "strokeTopWeight" in source
    assert "strokeRightWeight" in source
    assert "strokeBottomWeight" in source
    assert "strokeLeftWeight" in source
    assert "node.dashPattern" in source
    assert "node.strokeCap" in source
    assert "node.strokeJoin" in source
