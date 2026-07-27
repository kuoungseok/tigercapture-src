from __future__ import annotations

import json
import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _figma_payload() -> dict:
    return {
        "name": "Checkout",
        "version": "42",
        "lastModified": "2026-07-27T00:00:00Z",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "Screens",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Mobile Checkout",
                            "absoluteBoundingBox": {
                                "x": 100,
                                "y": 200,
                                "width": 390,
                                "height": 844,
                            },
                            "backgrounds": [
                                {
                                    "type": "SOLID",
                                    "color": {"r": 1, "g": 1, "b": 1},
                                }
                            ],
                            "layoutMode": "VERTICAL",
                            "itemSpacing": 16,
                            "paddingLeft": 24,
                            "paddingTop": 24,
                            "paddingRight": 24,
                            "paddingBottom": 24,
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "COMPONENT",
                                    "name": "Primary Button",
                                    "absoluteBoundingBox": {
                                        "x": 124,
                                        "y": 700,
                                        "width": 342,
                                        "height": 52,
                                    },
                                    "cornerRadius": 8,
                                    "boundVariables": {
                                        "fills": [
                                            {
                                                "type": "VARIABLE_ALIAS",
                                                "id": "VariableID:1",
                                            }
                                        ]
                                    },
                                    "reactions": [
                                        {
                                            "trigger": {"type": "ON_CLICK"},
                                            "actions": [
                                                {
                                                    "type": "NODE",
                                                    "destinationId": "3:1",
                                                    "navigation": "NAVIGATE",
                                                }
                                            ],
                                        }
                                    ],
                                    "fills": [
                                        {
                                            "type": "SOLID",
                                            "color": {
                                                "r": 0.1,
                                                "g": 0.3,
                                                "b": 0.9,
                                            },
                                        }
                                    ],
                                    "children": [
                                        {
                                            "id": "2:2",
                                            "type": "TEXT",
                                            "name": "Label",
                                            "characters": "Pay now",
                                            "style": {
                                                "fontFamily": "Inter",
                                                "fontSize": 16,
                                                "fontWeight": 600,
                                                "textAlignHorizontal": "CENTER",
                                            },
                                            "absoluteBoundingBox": {
                                                "x": 250,
                                                "y": 716,
                                                "width": 90,
                                                "height": 20,
                                            },
                                            "fills": [
                                                {
                                                    "type": "SOLID",
                                                    "color": {
                                                        "r": 1,
                                                        "g": 1,
                                                        "b": 1,
                                                    },
                                                }
                                            ],
                                        }
                                    ],
                                },
                                {
                                    "id": "3:1",
                                    "type": "INSTANCE",
                                    "name": "Pay Button",
                                    "componentId": "2:1",
                                    "absoluteBoundingBox": {
                                        "x": 124,
                                        "y": 770,
                                        "width": 342,
                                        "height": 52,
                                    },
                                    "children": [],
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }


def test_figma_file_key_supports_design_file_and_raw_key() -> None:
    from app.painter_ui_figma import figma_file_key

    assert (
        figma_file_key("https://www.figma.com/design/AbCdEf123456/Checkout?node-id=1-1")
        == "AbCdEf123456"
    )
    assert figma_file_key("AbCdEf123456") == "AbCdEf123456"


def test_figma_payload_imports_editable_layout_component_and_variables() -> None:
    from app.painter_ui_figma import import_figma_payload

    document, report = import_figma_payload(
        _figma_payload(),
        source="https://www.figma.com/design/AbCdEf123456/Checkout",
        variables_payload={
            "meta": {
                "variables": {
                    "VariableID:1": {
                        "name": "Color/Brand",
                        "resolvedType": "COLOR",
                        "valuesByMode": {
                            "1:0": {"r": 0.1, "g": 0.3, "b": 0.9, "a": 1}
                        },
                    }
                }
            }
        },
    )
    assert report["ok"] is True
    assert report["artboard_count"] == 1
    assert report["component_count"] == 1
    assert report["token_count"] == 1
    assert report["interaction_count"] == 1
    assert document["artboards"][0]["width"] == 390
    component = next(
        row for row in document["objects"] if row["component_role"] == "definition"
    )
    instance = next(
        row for row in document["objects"] if row["component_role"] == "instance"
    )
    assert instance["component_id"] == component["component_id"]
    assert instance["component_source_object_id"] == component["id"]
    assert component["token_bindings"]["style.fill"] == document["tokens"][0]["id"]
    text = next(row for row in document["objects"] if row["kind"] == "text")
    assert text["content"]["text"] == "Pay now"
    assert text["x"] == 150
    assert text["style"]["text_color"] == "#FFFFFFFF"
    assert text["style"]["font_family"] == "Inter"
    assert text["style"]["font_size"] == 16
    assert text["style"]["font_weight"] == 600
    assert text["style"]["text_align"] == "center"


def test_figma_import_activates_the_richest_visible_artboard() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    canvas = payload["document"]["children"][0]
    token_frame = {
        "id": "0:token",
        "type": "FRAME",
        "name": "Design Tokens",
        "absoluteBoundingBox": {
            "x": 0,
            "y": 0,
            "width": 240,
            "height": 120,
        },
        "children": [
            {
                "id": "0:swatch",
                "type": "RECTANGLE",
                "name": "Swatch",
                "absoluteBoundingBox": {
                    "x": 10,
                    "y": 10,
                    "width": 40,
                    "height": 40,
                },
            }
        ],
    }
    canvas["children"].insert(0, token_frame)

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert document["active_artboard_id"] == "figma-artboard-1-1"
    assert report["active_artboard_id"] == document["active_artboard_id"]


def test_figma_nodes_response_imports_as_editable_artboards() -> None:
    from app.painter_ui_figma import import_figma_payload

    frame = _figma_payload()["document"]["children"][0]["children"][0]
    payload = {
        "name": "Dashboard nodes",
        "version": "7",
        "nodes": {
            "1:1": {
                "document": frame,
                "components": {},
                "componentSets": {},
                "styles": {},
            }
        },
    }

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    assert report["artboard_count"] == 1
    assert report["object_count"] == 3
    assert document["artboards"][0]["name"] == "Mobile Checkout"
    assert document["active_artboard_id"] == "figma-artboard-1-1"


def test_figma_vector_without_geometry_is_reported_instead_of_box_substituted() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:1",
            "type": "VECTOR",
            "name": "Logo glyph",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 24,
                "height": 24,
            },
            "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}}],
        }
    )

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    vector = next(row for row in document["objects"] if row["name"] == "Logo glyph")
    assert vector["kind"] == "path"
    assert vector["content"].get("vector_paths", []) == []
    assert "blocked:9:1:VECTOR:missing_geometry_paths" in report["warnings"]


def test_figma_vector_geometry_is_preserved_for_svg_rendering() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:2",
            "type": "VECTOR",
            "name": "Triangle",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 24,
                "height": 24,
            },
            "fillGeometry": [{"path": "M 0 24 L 12 0 L 24 24 Z"}],
        }
    )

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    vector = next(row for row in document["objects"] if row["name"] == "Triangle")
    assert vector["content"]["vector_paths"] == ["M 0 24 L 12 0 L 24 24 Z"]
    assert vector["content"]["vector_fill_geometry"] == [
        {
            "path": "M 0 24 L 12 0 L 24 24 Z",
            "winding_rule": "nonzero",
        }
    ]
    assert not any("9:2:VECTOR:missing_geometry_paths" in row for row in report["warnings"])


def test_figma_stroke_geometry_and_line_style_are_preserved() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:3",
            "type": "VECTOR",
            "name": "Outlined icon",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 24,
                "height": 24,
            },
            "strokeGeometry": [
                {
                    "path": "M 2 12 L 22 12",
                    "windingRule": "EVENODD",
                }
            ],
            "strokes": [
                {
                    "type": "SOLID",
                    "color": {"r": 0.25, "g": 0.5, "b": 0.75},
                }
            ],
            "strokeWeight": 2,
            "strokeCap": "ROUND",
            "strokeJoin": "BEVEL",
            "strokeDashes": [4, 2],
        }
    )

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    vector = next(row for row in document["objects"] if row["name"] == "Outlined icon")
    assert vector["content"]["vector_stroke_geometry"] == [
        {
            "path": "M 2 12 L 22 12",
            "winding_rule": "evenodd",
        }
    ]
    assert vector["style"]["stroke_width"] == 2
    assert vector["style"]["stroke_cap"] == "round"
    assert vector["style"]["stroke_join"] == "bevel"
    assert vector["style"]["stroke_dash"] == [4, 2]
    assert not any("9:3:VECTOR:missing_geometry_paths" in row for row in report["warnings"])


def test_figma_stroke_geometry_renders_without_a_filled_bounding_box() -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_style_renderer import draw_ui_vector_paths

    _app()
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    rendered = draw_ui_vector_paths(
        painter,
        QRectF(4, 4, 24, 24),
        {
            "vector_stroke_geometry": [
                {
                    "path": "M 2 12 L 22 12",
                    "winding_rule": "nonzero",
                }
            ]
        },
        {
            "stroke": "#40A0FFFF",
            "stroke_width": 3,
            "stroke_cap": "round",
        },
    )
    painter.end()

    assert rendered is True
    assert image.pixelColor(16, 16).alpha() > 0
    assert image.pixelColor(4, 4).alpha() == 0


def test_figma_image_asset_maps_to_shared_renderer_contract(tmp_path: Path) -> None:
    from app.painter_ui_figma import import_figma_payload

    image_path = tmp_path / "hero.png"
    image_path.write_bytes(b"fixture")
    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:4",
            "type": "RECTANGLE",
            "name": "Hero image",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 240,
                "height": 120,
            },
            "fills": [
                {
                    "type": "IMAGE",
                    "imageRef": "hero-ref",
                    "scaleMode": "FILL",
                }
            ],
        }
    )

    document, report = import_figma_payload(
        payload,
        source="AbCdEf123456",
        image_paths={"hero-ref": str(image_path)},
    )

    image = next(row for row in document["objects"] if row["name"] == "Hero image")
    assert image["kind"] == "image"
    assert image["content"]["source_path"] == str(image_path)
    assert image["content"]["image_fit"] == "fill"
    assert image["content"]["image_status"] == "ready"
    assert report["resources"]["missing_image_count"] == 0


def test_figma_missing_images_and_fonts_are_reported() -> None:
    from app.painter_ui_figma import import_figma_payload, inspect_figma_resources

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:5",
            "type": "RECTANGLE",
            "name": "Missing hero",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 240,
                "height": 120,
            },
            "fills": [
                {
                    "type": "IMAGE",
                    "imageRef": "missing-ref",
                    "scaleMode": "FIT",
                }
            ],
        }
    )
    frame["children"][0]["children"][0]["style"]["fontFamily"] = "Rare Figma Font"

    document, report = import_figma_payload(payload, source="AbCdEf123456")
    resources = inspect_figma_resources(
        document,
        available_font_families={"Arial", "Inter"},
    )

    assert "blocked:9:5:IMAGE:missing_asset:missing-ref" in report["warnings"]
    assert resources["missing_image_count"] == 1
    assert resources["missing_images"][0]["name"] == "Missing hero"
    assert resources["missing_fonts"] == ["Rare Figma Font"]


def test_figma_auto_layout_maps_wrap_sizing_grow_stretch_and_limits() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame.update(
        {
            "layoutMode": "HORIZONTAL",
            "layoutWrap": "WRAP",
            "itemSpacing": 12,
            "counterAxisSpacing": 28,
            "primaryAxisSizingMode": "AUTO",
            "counterAxisSizingMode": "FIXED",
        }
    )
    child = frame["children"][0]
    child.update(
        {
            "layoutGrow": 1,
            "layoutAlign": "STRETCH",
            "minWidth": 120,
            "minHeight": 40,
            "maxWidth": 360,
            "maxHeight": 80,
        }
    )

    document, _report = import_figma_payload(payload, source="AbCdEf123456")

    imported_child = next(
        row for row in document["objects"] if row["name"] == "Primary Button"
    )
    assert imported_child["layout"]["width_sizing"] == "fill"
    assert imported_child["layout"]["height_sizing"] == "fill"
    assert imported_child["constraints"]["min_width"] == 120
    assert imported_child["constraints"]["min_height"] == 40
    assert imported_child["constraints"]["max_width"] == 360
    assert imported_child["constraints"]["max_height"] == 80

    component_payload = _figma_payload()
    component = (
        component_payload["document"]["children"][0]["children"][0]["children"][0]
    )
    component.update(
        {
            "layoutMode": "VERTICAL",
            "itemSpacing": 10,
            "counterAxisSpacing": 22,
            "primaryAxisSizingMode": "AUTO",
            "counterAxisSizingMode": "FIXED",
        }
    )
    document, _report = import_figma_payload(
        component_payload,
        source="AbCdEf123456",
    )
    imported_component = next(
        row for row in document["objects"] if row["name"] == "Primary Button"
    )
    assert imported_component["layout"]["mode"] == "vertical"
    assert imported_component["layout"]["gap"] == 10
    assert imported_component["layout"]["cross_gap"] == 22
    assert imported_component["layout"]["height_sizing"] == "hug"
    assert imported_component["layout"]["width_sizing"] == "fixed"


def test_figma_append_remaps_stable_ids_without_collisions() -> None:
    from app.painter_ui_figma import import_figma_payload, merge_figma_document

    imported, _ = import_figma_payload(_figma_payload(), source="AbCdEf123456")
    merged = merge_figma_document(imported, imported, mode="append")
    ids = [
        row["id"]
        for key in ("artboards", "objects", "components", "tokens", "interactions")
        for row in merged[key]
    ]
    assert len(merged["artboards"]) == 2
    assert len(ids) == len(set(ids))


def test_figma_export_creates_editable_plugin_bundle_with_embedded_image(
    tmp_path: Path,
) -> None:
    from app.painter_ui_figma import export_figma_plugin_package
    from app.painter_ui_templates import instantiate_ui_template

    image = tmp_path / "sample.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    document, _ = instantiate_ui_template("mobile_onboarding")
    document["objects"].append(
        {
            "id": "export-image",
            "kind": "image",
            "name": "Product",
            "artboard_id": document["active_artboard_id"],
            "x": 20,
            "y": 20,
            "width": 64,
            "height": 64,
            "content": {"image_path": str(image), "image_mode": "fill"},
        }
    )
    report = export_figma_plugin_package(document, tmp_path / "out")
    target = Path(report["output_dir"])
    assert (target / "manifest.json").is_file()
    assert (target / "code.js").is_file()
    exchange = json.loads((target / "figma_exchange.json").read_text("utf-8"))
    assert exchange["schema"] == "tigerstudio.painter.ui.figma_exchange.v1"
    assert exchange["assets"]["export-image"]["base64"]
    code = (target / "code.js").read_text("utf-8")
    assert "figma.variables.createVariableCollection" in code
    assert "setReactionsAsync" in code
    assert "createInstance" in code


def test_painter_publish_panel_exposes_figma_tab() -> None:
    _app()
    from PySide6.QtWidgets import QTabWidget

    from app.painter_ui_production_panel import PainterUIProductionPanel

    panel = PainterUIProductionPanel()
    tabs = panel.findChild(QTabWidget)
    assert tabs is not None
    labels = [tabs.tabText(index) for index in range(tabs.count())]
    assert "Figma" in labels
    assert panel.figma_panel.token_edit.echoMode().name == "Password"
    assert panel.figma_panel.resource_label.wordWrap() is True
