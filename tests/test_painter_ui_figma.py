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
