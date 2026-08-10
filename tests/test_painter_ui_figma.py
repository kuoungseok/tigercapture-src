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


def _with_primary_fill_variable_binding(payload: dict) -> dict:
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["boundVariables"] = {
        "fills": [
            {
                "type": "VARIABLE_ALIAS",
                "id": "VariableID:1",
            }
        ]
    }
    return payload


def test_figma_baseline_alignment_preserves_resolved_child_metrics() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "name": "Baseline",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "Page",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Artboard",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 800,
                                "height": 300,
                            },
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "FRAME",
                                    "name": "Baseline row",
                                    "absoluteBoundingBox": {
                                        "x": 100,
                                        "y": 50,
                                        "width": 545,
                                        "height": 140,
                                    },
                                    "layoutMode": "HORIZONTAL",
                                    "counterAxisAlignItems": "BASELINE",
                                    "itemSpacing": 38,
                                    "paddingLeft": 24,
                                    "paddingTop": 24,
                                    "paddingRight": 24,
                                    "paddingBottom": 24,
                                    "children": [
                                        {
                                            "id": "3:1",
                                            "type": "FRAME",
                                            "name": "Medium",
                                            "absoluteBoundingBox": {
                                                "x": 124,
                                                "y": 101,
                                                "width": 129,
                                                "height": 55,
                                            },
                                            "children": [],
                                        },
                                        {
                                            "id": "3:2",
                                            "type": "FRAME",
                                            "name": "Large",
                                            "absoluteBoundingBox": {
                                                "x": 291,
                                                "y": 74,
                                                "width": 215,
                                                "height": 92,
                                            },
                                            "children": [],
                                        },
                                        {
                                            "id": "3:3",
                                            "type": "FRAME",
                                            "name": "Small",
                                            "absoluteBoundingBox": {
                                                "x": 544,
                                                "y": 117,
                                                "width": 77,
                                                "height": 35,
                                            },
                                            "children": [],
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

    document, report = import_figma_payload(payload)
    rows = {row["name"]: row for row in document["objects"]}

    assert rows["Baseline row"]["layout"]["cross_alignment"] == "baseline"
    assert [
        rows[name]["layout"]["baseline_offset"]
        for name in ("Medium", "Large", "Small")
    ] == [51.0, 78.0, 35.0]
    assert any(
        "baseline_alignment_preserved_from_resolved_geometry" in warning
        for warning in report["warnings"]
    )
    geometry = resolve_ui_constraints(document)
    assert [
        geometry[rows[name]["id"]]["y"]
        for name in ("Medium", "Large", "Small")
    ] == [101.0, 74.0, 117.0]


def test_figma_missing_auto_layout_cross_bounds_use_resolved_child_evidence() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "name": "Missing parent bounds",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "Page",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Card",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 320,
                                "height": 180,
                            },
                            "layoutMode": "VERTICAL",
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "FRAME",
                                    "name": "Header",
                                    "layoutMode": "HORIZONTAL",
                                    "counterAxisAlignItems": "CENTER",
                                    "layoutSizingHorizontal": "FILL",
                                    "paddingLeft": 16,
                                    "paddingTop": 8,
                                    "paddingRight": 16,
                                    "paddingBottom": 8,
                                    "children": [
                                        {
                                            "id": "3:1",
                                            "type": "INSTANCE",
                                            "name": "Avatar",
                                            "absoluteBoundingBox": {
                                                "x": 16,
                                                "y": 8,
                                                "width": 24,
                                                "height": 24,
                                            },
                                            "children": [],
                                        },
                                        {
                                            "id": "3:2",
                                            "type": "TEXT",
                                            "name": "Missing title bounds",
                                            "characters": "Card title",
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

    document, report = import_figma_payload(payload)
    rows = {row["name"]: row for row in document["objects"]}
    header = rows["Header"]
    avatar = rows["Avatar"]

    assert header["y"] == 0.0
    assert header["height"] == 40.0
    assert header["content"]["figma_missing_bounds_recovery"] == {
        "status": "cross_axis_inferred",
        "reason": "missing_absolute_bounding_box",
        "axis": "height",
        "alignment": "center",
        "evidence_child_ids": ["3:1"],
        "inferred_position": 0.0,
        "inferred_size": 40.0,
    }
    assert any(
        "missing_auto_layout_cross_bounds_inferred" in warning
        for warning in report["warnings"]
    )
    geometry = resolve_ui_constraints(document)
    assert geometry[avatar["id"]]["y"] == 8.0


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
        _with_primary_fill_variable_binding(_figma_payload()),
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
    variable_binding = component["content"]["figma_variable_bindings"][0]
    assert variable_binding["status"] == "native"
    assert variable_binding["id"] == "VariableID:1"
    assert variable_binding["raw_alias"] == {
        "type": "VARIABLE_ALIAS",
        "id": "VariableID:1",
    }
    assert report["variable_binding_count"] == 1
    assert report["variable_binding_relink_count"] == 0
    text = next(row for row in document["objects"] if row["kind"] == "text")
    assert text["content"]["text"] == "Pay now"
    assert text["x"] == 150
    assert text["style"]["text_color"] == "#FFFFFFFF"
    assert text["style"]["font_family"] == "Inter"
    assert text["style"]["font_size"] == 16
    assert text["style"]["font_weight"] == 600
    assert text["style"]["text_align"] == "center"


def test_figma_import_preserves_unresolved_variable_alias_without_fabricating_token() -> None:
    from app.painter_ui_figma import import_figma_payload, inspect_figma_compatibility
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document, report = import_figma_payload(
        _with_primary_fill_variable_binding(_figma_payload()),
        source="missing-variables.json",
    )

    component = next(
        row for row in document["objects"] if row["component_role"] == "definition"
    )
    assert document["tokens"] == []
    assert component["token_bindings"] == {}
    assert component["style"]["fill"] == "#1A4CE6FF"
    assert component["content"]["figma_variable_bindings"] == [
        {
            "field": "fills",
            "alias_index": 0,
            "source_was_list": True,
            "id": "VariableID:1",
            "type": "VARIABLE_ALIAS",
            "target_path": "style.fill",
            "token_id": component["content"]["figma_variable_bindings"][0][
                "token_id"
            ],
            "status": "unresolved",
            "reason": "missing_variable_definition",
            "raw_alias": {
                "type": "VARIABLE_ALIAS",
                "id": "VariableID:1",
            },
        }
    ]
    assert report["variable_binding_count"] == 1
    assert report["unresolved_variable_binding_count"] == 1
    assert report["variable_binding_relink_count"] == 1
    assert any(
        "figma_variable_binding_requires_token_relink:"
        "missing_variable_definition:VariableID:1" in warning
        for warning in report["warnings"]
    )

    compatibility = inspect_figma_compatibility(document)
    variable_blockers = [
        row
        for row in compatibility["objects"]
        if "figma_variable_binding_requires_token_relink" in row["reason"]
    ]
    assert len(variable_blockers) == 1
    assert variable_blockers[0]["status"] == "blocked"
    preflight = preflight_painter_umg(document)
    assert any(
        "figma_variable_binding_requires_token_relink" in row["reasons"]
        for row in preflight["blockers"]
    )


def test_figma_import_recovers_multiple_and_unsupported_variable_aliases() -> None:
    from app.painter_ui_figma import import_figma_payload, inspect_figma_compatibility

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["boundVariables"] = {
        "fills": [
            {"type": "VARIABLE_ALIAS", "id": "VariableID:1"},
            {"type": "VARIABLE_ALIAS", "id": "VariableID:2"},
        ],
        "textRangeFills": [
            {"type": "VARIABLE_ALIAS", "id": "VariableID:3"},
        ],
        "opacity": {"type": "VARIABLE_ALIAS", "id": "VariableID:4"},
    }

    def color_variable(name: str, red: float) -> dict:
        return {
            "name": name,
            "resolvedType": "COLOR",
            "valuesByMode": {
                "1:0": {"r": red, "g": 0.2, "b": 0.3, "a": 1}
            },
        }

    document, report = import_figma_payload(
        payload,
        source="mixed-variable-bindings.json",
        variables_payload={
            "meta": {
                "variables": {
                    "VariableID:1": color_variable("Primary", 0.1),
                    "VariableID:2": color_variable("Secondary", 0.2),
                    "VariableID:3": color_variable("Range", 0.3),
                }
            }
        },
    )

    imported = next(
        row for row in document["objects"] if row["component_role"] == "definition"
    )
    records = {
        (row["field"], row["alias_index"]): row
        for row in imported["content"]["figma_variable_bindings"]
    }
    assert records[("fills", 0)]["status"] == "native"
    assert records[("fills", 1)]["status"] == "recovered"
    assert records[("fills", 1)]["reason"] == (
        "multiple_aliases_require_per_paint_binding"
    )
    assert records[("textRangeFills", 0)]["status"] == "blocked"
    assert records[("textRangeFills", 0)]["reason"] == (
        "unsupported_bound_variable_field"
    )
    assert records[("opacity", 0)]["status"] == "unresolved"
    assert records[("opacity", 0)]["raw_alias"]["id"] == "VariableID:4"
    assert set(imported["token_bindings"]) == {"style.fill"}
    assert report["variable_binding_count"] == 4
    assert report["unresolved_variable_binding_count"] == 1
    assert report["variable_binding_relink_count"] == 3

    variable_blockers = [
        row
        for row in inspect_figma_compatibility(document)["objects"]
        if "figma_variable_binding_requires_token_relink" in row["reason"]
    ]
    assert len(variable_blockers) == 3
    assert not any(row["id"].endswith(":fills:0") for row in variable_blockers)


def test_figma_import_preserves_artboard_variable_binding_as_root_recovery() -> None:
    from app.painter_ui_figma import import_figma_payload, inspect_figma_compatibility
    from app.painter_ui_umg_adapter import preflight_painter_umg

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"][0].pop("boundVariables", None)
    frame["boundVariables"] = {
        "fills": {"type": "VARIABLE_ALIAS", "id": "VariableID:artboard"}
    }

    document, report = import_figma_payload(
        payload,
        source="artboard-variable.json",
    )

    artboard_id = document["artboards"][0]["id"]
    bindings = document["linked_targets"]["figma"][
        "artboard_variable_bindings"
    ]
    assert len(bindings) == 1
    assert bindings[0]["artboard_id"] == artboard_id
    assert bindings[0]["figma_node_id"] == "1:1"
    assert bindings[0]["id"] == "VariableID:artboard"
    assert bindings[0]["raw_alias"] == {
        "type": "VARIABLE_ALIAS",
        "id": "VariableID:artboard",
    }
    assert bindings[0]["status"] == "unresolved"
    assert report["variable_binding_count"] == 1
    assert report["variable_binding_relink_count"] == 1
    assert any(
        row["id"].startswith(f"{artboard_id}:figma-variable:")
        and "figma_variable_binding_requires_token_relink" in row["reason"]
        for row in inspect_figma_compatibility(document)["objects"]
    )
    preflight = preflight_painter_umg(document, artboard_id=artboard_id)
    assert any(
        row["object_id"] == artboard_id
        and row["name"] == "Figma artboard variable bindings"
        and row["reasons"] == ["figma_variable_binding_requires_token_relink"]
        for row in preflight["blockers"]
    )


def test_figma_top_level_component_variable_alias_is_not_duplicated() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["type"] = "COMPONENT"
    frame["boundVariables"] = {
        "fills": {"type": "VARIABLE_ALIAS", "id": "VariableID:component"}
    }

    document, report = import_figma_payload(
        payload,
        source="top-level-component-variable.json",
    )

    imported_frame = next(
        row for row in document["objects"] if row["name"] == "Mobile Checkout"
    )
    assert len(imported_frame["content"]["figma_variable_bindings"]) == 1
    assert document["linked_targets"]["figma"][
        "artboard_variable_bindings"
    ] == []
    assert report["variable_binding_count"] == 1


def test_figma_text_import_preserves_pixel_line_height_and_auto_width() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    label = payload["document"]["children"][0]["children"][0]["children"][0][
        "children"
    ][0]
    label["style"]["lineHeightPx"] = 19.363636
    label["style"]["textAutoResize"] = "WIDTH_AND_HEIGHT"

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    text = next(row for row in document["objects"] if row["kind"] == "text")
    assert text["style"]["line_height"] == 19.363636
    assert text["style"]["line_height_unit"] == "px"
    assert text["content"]["text_resize"] == "auto_width"


def test_figma_remote_instance_fallback_detaches_expanded_descendants() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "name": "Remote component snapshot",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "Page 1",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Board",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 640,
                                "height": 480,
                            },
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "INSTANCE",
                                    "name": "Remote card",
                                    "componentId": "99:42",
                                    "componentPropertyReferences": {
                                        "mainComponent": "Card body#99:1",
                                    },
                                    "absoluteBoundingBox": {
                                        "x": 40,
                                        "y": 40,
                                        "width": 320,
                                        "height": 180,
                                    },
                                    "children": [
                                        {
                                            "id": "2:2",
                                            "type": "RECTANGLE",
                                            "name": "Background",
                                            "absoluteBoundingBox": {
                                                "x": 40,
                                                "y": 40,
                                                "width": 320,
                                                "height": 180,
                                            },
                                        },
                                        {
                                            "id": "2:3",
                                            "type": "TEXT",
                                            "name": "Title",
                                            "characters": "Remote card",
                                            "componentPropertyReferences": {
                                                "characters": "Title#99:2",
                                                "visible": "Show title#99:3",
                                            },
                                            "absoluteBoundingBox": {
                                                "x": 64,
                                                "y": 64,
                                                "width": 160,
                                                "height": 24,
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

    document, report = import_figma_payload(payload, source="GitHubSample")

    assert report["ok"] is True
    remote = next(row for row in document["objects"] if row["id"] == "figma-node-2-1")
    descendants = [
        row for row in document["objects"] if row["parent_id"] == remote["id"]
    ]
    # An instance is frame-like in Figma - it paints its own fills - so it
    # imports as a frame even when its remote component cannot be resolved.
    assert remote["kind"] == "frame"
    assert remote["component_id"] == ""
    assert remote["content"]["figma_component_id"] == "figma-component-99-42"
    assert remote["content"]["remote_component"]["status"] == "missing"
    assert descendants
    assert all(row["component_id"] == "" for row in descendants)
    assert remote["component_property_bindings"] == {}
    assert remote["content"]["figma_component_property_bindings"] == {
        "component_id": "Card body",
    }
    title = next(row for row in descendants if row["name"] == "Title")
    assert title["component_property_bindings"] == {}
    assert title["content"]["figma_component_property_bindings"] == {
        "content.text": "Title",
        "visible": "Show title",
    }
    assert (
        "converted:figma-node-2-1:remote_component_instance_to_group"
        in report["warnings"]
    )
    assert (
        "converted:figma-node-2-1:remote_component_property_bindings_detached"
        in report["warnings"]
    )
    assert (
        "converted:figma-node-2-3:remote_component_property_bindings_detached"
        in report["warnings"]
    )


def test_figma_local_instance_expansion_detaches_resolved_descendant_bindings() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    definition = frame["children"][0]
    definition["componentPropertyDefinitions"] = {
        "Label#2:9": {
            "type": "TEXT",
            "defaultValue": "Pay now",
        }
    }
    definition_label = definition["children"][0]
    definition_label["componentPropertyReferences"] = {
        "characters": "Label#2:9",
    }
    instance = frame["children"][1]
    instance["children"] = [
        {
            "id": "I3:1;2:2",
            "type": "TEXT",
            "name": "Resolved Label",
            "characters": "Pay now",
            "componentPropertyReferences": {
                "characters": "Label#2:9",
            },
            "absoluteBoundingBox": {
                "x": 250,
                "y": 786,
                "width": 90,
                "height": 20,
            },
        }
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    source_label = next(
        row for row in document["objects"] if row["name"] == "Label"
    )
    resolved_label = next(
        row for row in document["objects"] if row["name"] == "Resolved Label"
    )
    assert source_label["component_property_bindings"] == {
        "content.text": "Label",
    }
    assert resolved_label["component_property_bindings"] == {}
    assert resolved_label["content"]["figma_component_property_bindings"] == {
        "content.text": "Label",
    }
    assert (
        "converted:figma-node-I3-1-2-2:"
        "expanded_instance_property_bindings_resolved"
        in report["warnings"]
    )


def test_figma_component_property_reference_slots_are_lossless_and_blocked(
    tmp_path: Path,
) -> None:
    import pytest

    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        PainterUIFigmaError,
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    payload = _figma_payload()
    definition = payload["document"]["children"][0]["children"][0]["children"][0]
    definition["componentPropertyDefinitions"] = {
        "Label#2:9": {"type": "TEXT", "defaultValue": "Pay now"},
        "Tone#2:10": {"type": "TEXT", "defaultValue": "strong"},
    }
    label = definition["children"][0]
    raw_references = {
        "characters": "Label#2:9",
        "futureToneField": "Tone#2:10",
    }
    label["componentPropertyReferences"] = raw_references

    document, report = import_figma_payload(
        payload,
        source="component-property-references.json",
    )
    imported_label = next(
        row for row in document["objects"] if row["name"] == "Label"
    )
    content = imported_label["content"]

    assert report["source_component_property_binding_count"] == 2
    assert report["native_component_property_binding_count"] == 1
    assert report["recovered_component_property_binding_count"] == 1
    assert report["component_property_binding_count_conserved"] is True
    assert imported_label["component_property_bindings"] == {
        "content.text": "Label"
    }
    assert content["figma_component_property_bindings"] == {
        "figma_field:futureToneField": "Tone#2:10"
    }
    assert content["figma_component_property_references"] == raw_references
    assert normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    ) == document

    compatibility = inspect_figma_compatibility(document)
    binding_rows = [
        row
        for row in compatibility["objects"]
        if row["id"].startswith(
            f"{imported_label['id']}:figma-component-property-"
        )
    ]
    assert {row["status"] for row in binding_rows} == {"native", "blocked"}
    assert any(
        "figma_component_property_reference_field_unsupported"
        in row["reason"]
        for row in binding_rows
        if row["status"] == "blocked"
    )
    with pytest.raises(PainterUIFigmaError, match="blocked"):
        export_figma_plugin_package(document, tmp_path / "property-binding")

    umg = painter_ui_to_umg_document(document)
    umg_layer = next(
        row for row in umg["Layers"] if row["Id"] == imported_label["id"]
    )
    payload_json = json.loads(umg_layer["PayloadJson"])
    assert payload_json["component_property_bindings"] == {
        "content.text": "Label"
    }
    assert payload_json["figma_component_property_bindings"] == {
        "figma_field:futureToneField": "Tone#2:10"
    }
    assert payload_json["figma_component_property_references"] == raw_references
    assert {
        "figma_component_property_binding_requires_umg_component_parameter_binding",
        "figma_component_property_reference_field_unsupported",
    } <= set(umg_layer["BlockReasons"])
    preflight = preflight_painter_umg(document)
    blocker = next(
        row
        for row in preflight["blockers"]
        if row["object_id"] == imported_label["id"]
    )
    assert set(umg_layer["BlockReasons"]) <= set(blocker["reasons"])


def test_figma_component_set_detaches_nested_instance_source_bindings() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "id": "10:1",
        "type": "COMPONENT_SET",
        "name": "Cookie banner",
        "absoluteBoundingBox": {
            "x": 100,
            "y": 200,
            "width": 640,
            "height": 240,
        },
        "componentPropertyDefinitions": {
            "Service#10:9": {
                "type": "TEXT",
                "defaultValue": "Cookies on service",
            }
        },
        "children": [
            {
                "id": "10:2",
                "type": "COMPONENT",
                "name": "Responded=False",
                "absoluteBoundingBox": {
                    "x": 100,
                    "y": 200,
                    "width": 640,
                    "height": 240,
                },
                "children": [
                    {
                        "id": "10:3",
                        "type": "TEXT",
                        "name": "Heading",
                        "characters": "Cookies on service",
                        "componentPropertyReferences": {
                            "characters": "Service#10:9",
                        },
                        "absoluteBoundingBox": {
                            "x": 124,
                            "y": 224,
                            "width": 240,
                            "height": 30,
                        },
                    },
                    {
                        "id": "10:4",
                        "type": "INSTANCE",
                        "name": "Remote button",
                        "componentId": "99:1",
                        "componentProperties": {
                            "Content#99:9": {
                                "type": "TEXT",
                                "value": "Hide cookie message",
                            }
                        },
                        "absoluteBoundingBox": {
                            "x": 124,
                            "y": 280,
                            "width": 220,
                            "height": 48,
                        },
                        "children": [
                            {
                                "id": "I10:4;99:2",
                                "type": "TEXT",
                                "name": "Resolved button label",
                                "characters": "Hide cookie message",
                                "componentPropertyReferences": {
                                    "characters": "Content#99:9",
                                },
                                "absoluteBoundingBox": {
                                    "x": 140,
                                    "y": 294,
                                    "width": 180,
                                    "height": 20,
                                },
                            }
                        ],
                    },
                ],
            }
        ],
    }

    document, report = import_figma_payload(payload, source="GitHubFragment")

    assert report["ok"] is True
    heading = next(row for row in document["objects"] if row["name"] == "Heading")
    assert heading["component_property_bindings"] == {
        "content.text": "Service",
    }
    resolved = next(
        row
        for row in document["objects"]
        if row["name"] == "Resolved button label"
    )
    assert resolved["content"]["text"] == "Hide cookie message"
    assert resolved["component_property_bindings"] == {}
    assert resolved["content"]["figma_component_property_bindings"] == {
        "content.text": "Content",
    }
    assert (
        "converted:figma-node-I10-4-99-2:"
        "expanded_instance_property_bindings_resolved"
        in report["warnings"]
    )


def test_figma_corner_smoothing_imports_and_exports_as_editable_style(
    tmp_path: Path,
) -> None:
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
    )

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["cornerSmoothing"] = 0.72
    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    button = next(row for row in document["objects"] if row["name"] == "Primary Button")
    assert button["style"]["corner_smoothing"] == 0.72
    export = export_figma_plugin_package(document, tmp_path / "smoothing")
    code = (Path(export["output_dir"]) / "code.js").read_text("utf-8")
    assert "node.cornerSmoothing=Math.max(0,Math.min(1" in code


def test_figma_import_preserves_canvas_pages_and_page_scoped_artboards() -> None:
    from app.painter_ui_document import active_ui_page_document, set_active_ui_page
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    payload["document"]["children"].append(
        {
            "id": "10:1",
            "type": "CANVAS",
            "name": "Archive",
            "children": [
                {
                    "id": "10:2",
                    "type": "FRAME",
                    "name": "Legacy Screen",
                    "absoluteBoundingBox": {
                        "x": 0,
                        "y": 0,
                        "width": 800,
                        "height": 600,
                    },
                    "children": [],
                }
            ],
        }
    )
    document, report = import_figma_payload(
        payload,
        source="AbCdEf123456",
    )

    assert report["page_count"] == 2
    assert [row["name"] for row in document["pages"]] == [
        "Screens",
        "Archive",
    ]
    screens_artboard = next(
        row for row in document["artboards"] if row["name"] == "Mobile Checkout"
    )
    archive_artboard = next(
        row for row in document["artboards"] if row["name"] == "Legacy Screen"
    )
    # Each page keeps its own Figma canvas grid, so pages are separated by
    # being stacked rather than interleaved on one endless row.
    assert archive_artboard["y"] >= (
        screens_artboard["y"] + screens_artboard["height"]
    )
    archive_page = document["pages"][1]
    document = set_active_ui_page(document, archive_page["id"])
    scoped = active_ui_page_document(document)
    assert [row["name"] for row in scoped["artboards"]] == ["Legacy Screen"]


def test_figma_component_set_imports_variants_and_instance_properties() -> None:
    from app.painter_ui_components import switch_ui_component_instance_variant
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"] = [
        {
            "id": "10:1",
            "type": "COMPONENT_SET",
            "name": "Button",
            "absoluteBoundingBox": {
                "x": 124,
                "y": 260,
                "width": 342,
                "height": 120,
            },
            "componentPropertyDefinitions": {
                "State": {
                    "type": "VARIANT",
                    "defaultValue": "Default",
                    "variantOptions": ["Default", "Pressed"],
                },
                "Label#10:8": {
                    "type": "TEXT",
                    "defaultValue": "Continue",
                },
                "Leading icon#10:9": {
                    "type": "BOOLEAN",
                    "defaultValue": True,
                },
            },
            "children": [
                {
                    "id": "10:2",
                    "type": "COMPONENT",
                    "name": "State=Default",
                    "variantProperties": {"State": "Default"},
                    "reactions": [
                        {
                            "trigger": {"type": "ON_CLICK"},
                            "actions": [
                                {
                                    "type": "NODE",
                                    "destinationId": "10:4",
                                    "navigation": "CHANGE_TO",
                                }
                            ],
                        }
                    ],
                    "absoluteBoundingBox": {
                        "x": 124,
                        "y": 260,
                        "width": 342,
                        "height": 52,
                    },
                    "children": [
                        {
                            "id": "10:3",
                            "type": "TEXT",
                            "name": "Label",
                            "characters": "Continue",
                            "componentPropertyReferences": {
                                "characters": "Label#10:8"
                            },
                            "absoluteBoundingBox": {
                                "x": 240,
                                "y": 276,
                                "width": 100,
                                "height": 20,
                            },
                        }
                    ],
                },
                {
                    "id": "10:4",
                    "type": "COMPONENT",
                    "name": "State=Pressed",
                    "variantProperties": {"State": "Pressed"},
                    "absoluteBoundingBox": {
                        "x": 124,
                        "y": 328,
                        "width": 342,
                        "height": 52,
                    },
                    "children": [
                        {
                            "id": "10:5",
                            "type": "TEXT",
                            "name": "Label",
                            "characters": "Continue",
                            "componentPropertyReferences": {
                                "characters": "Label#10:8"
                            },
                            "absoluteBoundingBox": {
                                "x": 240,
                                "y": 344,
                                "width": 100,
                                "height": 20,
                            },
                        }
                    ],
                },
            ],
        },
        {
            "id": "10:6",
            "type": "INSTANCE",
            "name": "Continue Button",
            "componentId": "10:4",
            "componentProperties": {
                "State": {"type": "VARIANT", "value": "Pressed"},
                "Label#10:8": {"type": "TEXT", "value": "Buy now"},
                "Leading icon#10:9": {"type": "BOOLEAN", "value": False},
            },
            "absoluteBoundingBox": {
                "x": 124,
                "y": 420,
                "width": 342,
                "height": 52,
            },
            "children": [],
        },
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    assert report["component_count"] == 2
    family = next(
        row for row in document["components"] if not row["base_component_id"]
    )
    variant = next(
        row for row in document["components"] if row["base_component_id"]
    )
    assert family["variant_ids"] == [variant["id"]]
    assert variant["base_component_id"] == family["id"]
    assert family["property_definitions"]["State"] == {
        "type": "enum",
        "default": "Default",
        "values": ["Default", "Pressed"],
        "description": "",
    }
    assert family["property_definitions"]["Label"]["type"] == "text"
    assert family["property_definitions"]["Leading icon"]["type"] == "boolean"
    assert family["metadata"]["variant_key"] == "State=Default"
    assert variant["metadata"]["variant_key"] == "State=Pressed"
    assert variant["metadata"]["variant_source_map"]["root/0"] == (
        "figma-node-10-5"
    )
    variant_label = next(
        row
        for row in document["objects"]
        if row["id"] == "figma-node-10-5"
    )
    assert variant_label["component_property_bindings"] == {
        "content.text": "Label"
    }
    instance = next(
        row for row in document["objects"] if row["component_role"] == "instance"
    )
    assert instance["component_id"] == variant["id"]
    assert instance["component_source_object_id"] == variant["root_object_id"]
    assert instance["variant"] == "State=Pressed"
    assert instance["component_properties"] == {
        "State": "Pressed",
        "Label": "Buy now",
        "Leading icon": False,
    }
    change_to = document["interactions"][0]
    assert change_to["action"] == "change_variant"
    assert change_to["component_id"] == variant["id"]
    assert change_to["target_object_id"] == family["root_object_id"]
    document, switched = switch_ui_component_instance_variant(
        document,
        instance_root_id=instance["id"],
        target_component_id=family["id"],
    )
    assert switched["component_id"] == family["id"]
    switched_rows = [
        row for row in document["objects"] if row["id"] in switched["object_ids"]
    ]
    assert len(switched_rows) == 2
    switched_root = next(row for row in switched_rows if not row["parent_id"])
    switched_label = next(row for row in switched_rows if row["kind"] == "text")
    assert switched_root["component_properties"]["Label"] == "Buy now"
    assert switched_label["component_source_object_id"] == "figma-node-10-3"


def test_figma_nested_instance_swap_maps_scope_and_stable_component_ids() -> None:
    from app.painter_ui_components import (
        instantiate_ui_component,
        set_ui_instance_component_property,
    )
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"] = [
        {
            "id": "20:1",
            "key": "icon-square-key",
            "type": "COMPONENT",
            "name": "Square Icon",
            "absoluteBoundingBox": {
                "x": 120,
                "y": 260,
                "width": 24,
                "height": 24,
            },
            "children": [],
        },
        {
            "id": "20:2",
            "key": "icon-round-key",
            "type": "COMPONENT",
            "name": "Round Icon",
            "absoluteBoundingBox": {
                "x": 160,
                "y": 260,
                "width": 24,
                "height": 24,
            },
            "children": [],
        },
        {
            "id": "21:1",
            "type": "COMPONENT",
            "name": "Card",
            "componentPropertyDefinitions": {
                "Icon#21:9": {
                    "type": "INSTANCE_SWAP",
                    "defaultValue": "20:1",
                    "preferredValues": [
                        {"type": "COMPONENT", "key": "icon-round-key"}
                    ],
                }
            },
            "absoluteBoundingBox": {
                "x": 120,
                "y": 320,
                "width": 240,
                "height": 96,
            },
            "children": [
                {
                    "id": "21:2",
                    "type": "INSTANCE",
                    "name": "Icon",
                    "componentId": "20:1",
                    "componentPropertyReferences": {
                        "mainComponent": "Icon#21:9"
                    },
                    "absoluteBoundingBox": {
                        "x": 144,
                        "y": 344,
                        "width": 24,
                        "height": 24,
                    },
                    "children": [],
                }
            ],
        },
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    card = next(row for row in document["components"] if row["name"] == "Card")
    icon_a = next(
        row for row in document["components"] if row["name"] == "Square Icon"
    )
    icon_b = next(
        row for row in document["components"] if row["name"] == "Round Icon"
    )
    assert card["property_definitions"]["Icon"]["default"] == icon_a["id"]
    assert card["property_definitions"]["Icon"]["preferred_values"] == [
        icon_b["id"]
    ]
    nested_source = next(
        row for row in document["objects"] if row["id"] == "figma-node-21-2"
    )
    assert nested_source["component_id"] == icon_a["id"]
    assert nested_source["component_source_object_id"] == icon_a["root_object_id"]
    assert nested_source["component_scope_id"] == card["id"]
    assert nested_source["component_scope_source_object_id"] == nested_source["id"]
    assert nested_source["component_property_bindings"] == {
        "component_id": "Icon"
    }

    document, instance = instantiate_ui_component(
        document,
        component_id=card["id"],
        x=420,
        y=320,
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Icon",
        property_value=icon_b["id"],
    )
    swapped = next(
        row
        for row in document["objects"]
        if row["component_scope_id"] == card["id"]
        and row["parent_id"] == instance["root_object_id"]
    )
    assert swapped["component_id"] == icon_b["id"]


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


def test_figma_nodes_response_preserves_mixed_frame_and_leaf_targets() -> None:
    from app.painter_ui_figma import import_figma_payload

    frame = _figma_payload()["document"]["children"][0]["children"][0]
    leaf = {
        "id": "8:1",
        "type": "RECTANGLE",
        "name": "Detached Swatch",
        "absoluteBoundingBox": {
            "x": 900,
            "y": 120,
            "width": 48,
            "height": 48,
        },
        "fills": [
            {
                "type": "SOLID",
                "color": {"r": 0.2, "g": 0.4, "b": 0.8},
            }
        ],
    }
    payload = {
        "name": "Mixed dashboard nodes",
        "version": "8",
        "nodes": {
            "1:1": {"document": frame},
            "8:1": {"document": leaf},
        },
    }

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    assert report["artboard_count"] == 2
    assert report["object_count"] == 4
    swatch = next(
        row for row in document["objects"] if row["id"] == "figma-node-8-1"
    )
    assert swatch["name"] == "Detached Swatch"
    assert swatch["x"] == 0
    assert swatch["y"] == 0
    assert any(
        row["name"] == "Detached Swatch" for row in document["artboards"]
    )


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


def test_figma_missing_tooltip_arrow_recovers_exact_triangle_geometry() -> None:
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_umg_adapter import preflight_painter_umg

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].extend(
        [
            {
                "id": "9:11",
                "type": "VECTOR",
                "name": "Arrow",
                "absoluteBoundingBox": {
                    "x": 140,
                    "y": 240,
                    "width": 12,
                    "height": 6,
                },
                "fills": [
                    {
                        "type": "SOLID",
                        "color": {"r": 0.1, "g": 0.2, "b": 0.3},
                    }
                ],
                "strokes": [],
            },
            {
                "id": "9:12",
                "type": "VECTOR",
                "name": "Arrow",
                "rotation": -3.141592653589793,
                "absoluteBoundingBox": {
                    "x": 180,
                    "y": 240,
                    "width": 6,
                    "height": 12,
                },
                "fills": [
                    {
                        "type": "SOLID",
                        "color": {"r": 0.1, "g": 0.2, "b": 0.3},
                    }
                ],
                "strokes": [],
            },
        ]
    )

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    down = next(row for row in document["objects"] if row["name"] == "Arrow")
    left = next(
        row
        for row in document["objects"]
        if row["id"] == "figma-node-9-12"
    )
    assert down["content"]["vector_paths"] == ["M 0 0 L 12 0 L 6 6 Z"]
    assert left["content"]["vector_paths"] == ["M 6 0 L 6 12 L 0 6 Z"]
    assert left["rotation"] == 0.0
    assert down["content"]["figma_vector_geometry_recovery"] == {
        "kind": "triangle",
        "source": "semantic_primitive",
        "editability": "editable_path",
        "consumed_rotation": False,
    }
    assert not any("9:11:VECTOR:missing_geometry_paths" in row for row in report["warnings"])
    assert not any("9:12:VECTOR:missing_geometry_paths" in row for row in report["warnings"])
    assert sum(
        "semantic_primitive_geometry_recovered:triangle" in row
        for row in report["warnings"]
    ) == 2
    preflight = preflight_painter_umg(document)
    for vector in (down, left):
        blocker = next(
            row
            for row in preflight["blockers"]
            if row["object_id"] == vector["id"]
        )
        assert (
            "figma_semantic_vector_primitive_requires_deterministic_bake"
            in blocker["reasons"]
        )


def test_figma_missing_named_rectangle_recovers_editable_path() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:13",
            "type": "VECTOR",
            "name": "Rectangle 4",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 1053,
                "height": 1024,
            },
            "fills": [
                {
                    "type": "SOLID",
                    "color": {"r": 1, "g": 1, "b": 1},
                }
            ],
            "strokes": [],
        }
    )

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    rectangle = next(
        row for row in document["objects"] if row["id"] == "figma-node-9-13"
    )
    assert rectangle["content"]["vector_paths"] == [
        "M 0 0 H 1053 V 1024 H 0 Z"
    ]
    assert rectangle["content"]["figma_vector_geometry_recovery"]["kind"] == (
        "rectangle"
    )
    assert (
        "converted:9:13:VECTOR:semantic_primitive_geometry_recovered:rectangle"
        in report["warnings"]
    )


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


def test_figma_svg_render_fallback_preserves_pixels_and_reports_lost_editability(
    tmp_path,
) -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_figma import (
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_style_renderer import draw_ui_vector_paths
    from app.painter_ui_umg_adapter import preflight_painter_umg

    svg_path = tmp_path / "exact-vector.svg"
    svg_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="12" cy="12" r="10" fill="#ff0066"/>'
        "</svg>",
        encoding="utf-8",
    )
    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:14",
            "type": "VECTOR",
            "name": "Arbitrary logo",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 24,
                "height": 24,
            },
        }
    )

    document, report = import_figma_payload(
        payload,
        source="AbCdEf123456",
        vector_render_paths={"9:14": str(svg_path)},
    )

    vector = next(
        row for row in document["objects"] if row["id"] == "figma-node-9-14"
    )
    assert vector["content"]["vector_render_path"] == str(svg_path)
    assert vector["content"]["figma_vector_geometry_recovery"] == {
        "kind": "svg_render",
        "source": "figma_render_api",
        "editability": "render_only",
    }
    assert (
        "converted:9:14:VECTOR:figma_svg_render_fallback_noneditable"
        in report["warnings"]
    )
    assert not any("9:14:VECTOR:missing_geometry_paths" in row for row in report["warnings"])
    compatibility = inspect_figma_compatibility(document)
    compatibility_row = next(
        row for row in compatibility["objects"] if row["id"] == vector["id"]
    )
    assert compatibility_row["status"] == "converted"
    assert "editable vector path geometry is unavailable" in compatibility_row[
        "reason"
    ]
    preflight = preflight_painter_umg(document)
    vector_blocker = next(
        row
        for row in preflight["blockers"]
        if row["object_id"] == vector["id"]
    )
    assert (
        "figma_vector_render_fallback_requires_deterministic_bake"
        in vector_blocker["reasons"]
    )

    _app()
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    assert draw_ui_vector_paths(
        painter,
        QRectF(4, 4, 24, 24),
        vector["content"],
        vector["style"],
    ) is True
    painter.end()
    assert image.pixelColor(16, 16).alpha() > 0
    assert image.pixelColor(4, 4).alpha() == 0


def test_figma_file_requests_exact_svg_for_vector_missing_editable_paths(
    tmp_path,
) -> None:
    from app.painter_ui_figma import import_figma_file

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:15",
            "type": "VECTOR",
            "name": "Unrecoverable icon",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 24,
                "height": 24,
            },
        }
    )
    requested_urls: list[str] = []

    class Response:
        def __init__(self, data: bytes, content_type: str) -> None:
            self._data = data
            self.headers = {"Content-Type": content_type}

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return self._data

    def opener(request, *, timeout):
        assert timeout == 4.0
        url = request.full_url
        requested_urls.append(url)
        if "/files/AbCdEf123456?" in url:
            return Response(json.dumps(payload).encode("utf-8"), "application/json")
        if url.endswith("/files/AbCdEf123456/images"):
            return Response(b'{"meta":{"images":{}}}', "application/json")
        if url.endswith("/files/AbCdEf123456/variables/local"):
            return Response(b"{}", "application/json")
        if "/images/AbCdEf123456?" in url:
            return Response(
                json.dumps(
                    {"images": {"9:15": "https://cdn.example/icon.svg"}}
                ).encode("utf-8"),
                "application/json",
            )
        if url == "https://cdn.example/icon.svg":
            return Response(
                b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                b'<path d="M2 12L12 2L22 12L12 22Z" fill="#00aaee"/>'
                b"</svg>",
                "image/svg+xml",
            )
        raise AssertionError(f"unexpected URL: {url}")

    document, report = import_figma_file(
        "AbCdEf123456",
        token="test-token",
        timeout=4.0,
        opener=opener,
        asset_root=tmp_path,
    )

    vector = next(
        row for row in document["objects"] if row["id"] == "figma-node-9-15"
    )
    render_path = Path(vector["content"]["vector_render_path"])
    assert render_path.is_file()
    assert render_path.suffix == ".svg"
    assert report["downloaded_vector_render_count"] == 1
    assert (
        "converted:9:15:VECTOR:figma_svg_render_fallback_noneditable"
        in report["warnings"]
    )
    render_request = next(
        url for url in requested_urls if "/images/AbCdEf123456?" in url
    )
    assert "ids=9%3A15" in render_request
    assert "format=svg" in render_request
    assert "svg_include_id=true" in render_request


def test_figma_linear_and_radial_gradients_preserve_handles_and_stops() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].extend(
        [
            {
                "id": "9:31",
                "type": "RECTANGLE",
                "name": "Linear gradient",
                "absoluteBoundingBox": {
                    "x": 140,
                    "y": 240,
                    "width": 120,
                    "height": 60,
                },
                "fills": [
                    {
                        "type": "GRADIENT_LINEAR",
                        "opacity": 0.5,
                        "gradientHandlePositions": [
                            {"x": 0.1, "y": 0.5},
                            {"x": 0.9, "y": 0.5},
                            {"x": 0.1, "y": 1.0},
                        ],
                        "gradientStops": [
                            {
                                "position": 0,
                                "color": {"r": 1, "g": 0, "b": 0, "a": 1},
                            },
                            {
                                "position": 1,
                                "color": {"r": 0, "g": 0, "b": 1, "a": 0.8},
                            },
                        ],
                    }
                ],
            },
            {
                "id": "9:32",
                "type": "ELLIPSE",
                "name": "Radial gradient",
                "absoluteBoundingBox": {
                    "x": 280,
                    "y": 240,
                    "width": 60,
                    "height": 60,
                },
                "fills": [
                    {
                        "type": "GRADIENT_RADIAL",
                        "gradientHandlePositions": [
                            {"x": 0.5, "y": 0.5},
                            {"x": 1.0, "y": 0.5},
                            {"x": 0.5, "y": 1.0},
                        ],
                        "gradientStops": [
                            {
                                "position": 0,
                                "color": {"r": 1, "g": 1, "b": 1, "a": 1},
                            },
                            {
                                "position": 1,
                                "color": {"r": 0, "g": 0, "b": 0, "a": 0},
                            },
                        ],
                    }
                ],
            },
        ]
    )

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    linear = next(row for row in document["objects"] if row["name"] == "Linear gradient")
    radial = next(row for row in document["objects"] if row["name"] == "Radial gradient")
    assert linear["style"]["fill"] == "#00000000"
    assert linear["style"]["fill_gradient"] == {
        "type": "linear",
        "start": {"x": 0.1, "y": 0.5},
        "end": {"x": 0.9, "y": 0.5},
        "width": {"x": 0.1, "y": 1.0},
        "stops": [
            {"position": 0.0, "color": "#FF0000FF"},
            {"position": 1.0, "color": "#0000FFCC"},
        ],
    }
    assert linear["style"]["fills"][0]["opacity"] == 0.5
    assert linear["style"]["fills"][0]["gradient"]["stops"] == (
        linear["style"]["fill_gradient"]["stops"]
    )
    assert radial["style"]["fill_gradient"]["type"] == "radial"


def test_figma_paint_opacity_round_trip_does_not_double_color_alpha(
    tmp_path: Path,
) -> None:
    from PySide6.QtCore import QRectF

    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
    )
    from app.painter_ui_style_renderer import ui_fill_brush
    from app.unreal_umg_material import painter_style_umg_material

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].extend(
        [
            {
                "id": "9:41",
                "type": "RECTANGLE",
                "name": "Half solid and stroke",
                "absoluteBoundingBox": {
                    "x": 140,
                    "y": 300,
                    "width": 120,
                    "height": 60,
                },
                "cornerRadius": 8,
                "fills": [
                    {
                        "type": "SOLID",
                        "opacity": 0.5,
                        "color": {"r": 1, "g": 0, "b": 0, "a": 0.8},
                    }
                ],
                "strokes": [
                    {
                        "type": "SOLID",
                        "opacity": 0.5,
                        "color": {"r": 0, "g": 0, "b": 1, "a": 0.6},
                    }
                ],
                "strokeWeight": 2,
                "strokeAlign": "INSIDE",
            },
            {
                "id": "9:42",
                "type": "RECTANGLE",
                "name": "Half gradient",
                "absoluteBoundingBox": {
                    "x": 280,
                    "y": 300,
                    "width": 120,
                    "height": 60,
                },
                "fills": [
                    {
                        "type": "GRADIENT_RADIAL",
                        "opacity": 0.5,
                        "gradientHandlePositions": [
                            {"x": 0.5, "y": 0.5},
                            {"x": 1.0, "y": 0.5},
                            {"x": 0.5, "y": 1.0},
                        ],
                        "gradientStops": [
                            {
                                "position": 0,
                                "color": {"r": 1, "g": 1, "b": 1, "a": 0.8},
                            },
                            {
                                "position": 1,
                                "color": {"r": 0, "g": 0, "b": 0, "a": 0.4},
                            },
                        ],
                    }
                ],
            },
        ]
    )
    document, report = import_figma_payload(payload, source="AbCdEf123456")
    assert report["ok"] is True
    by_name = {row["name"]: row for row in document["objects"]}
    solid = by_name["Half solid and stroke"]
    gradient = by_name["Half gradient"]

    assert solid["style"]["fills"][0]["color"] == "#FF0000CC"
    assert solid["style"]["fills"][0]["opacity"] == 0.5
    assert solid["style"]["strokes"][0]["color"] == "#0000FF99"
    assert solid["style"]["strokes"][0]["opacity"] == 0.5
    assert gradient["style"]["fills"][0]["opacity"] == 0.5
    assert [
        row["color"]
        for row in gradient["style"]["fills"][0]["gradient"]["stops"]
    ] == ["#FFFFFFCC", "#00000066"]
    assert gradient["style"]["fill_gradient"]["stops"] == (
        gradient["style"]["fills"][0]["gradient"]["stops"]
    )

    # Painter consumes color alpha * paint opacity exactly once: 0.8 * 0.5.
    assert ui_fill_brush(solid["style"]).color().alpha() == 102
    gradient_brush = ui_fill_brush(
        gradient["style"],
        QRectF(0.0, 0.0, 120.0, 60.0),
    )
    assert [
        color.alpha()
        for _position, color in gradient_brush.gradient().stops()
    ] == [102, 51]

    solid_material = painter_style_umg_material(
        solid["style"],
        source_kind="rectangle",
        size={"X": solid["width"], "Y": solid["height"]},
    )
    gradient_material = painter_style_umg_material(
        gradient["style"],
        source_kind="rectangle",
        size={"X": gradient["width"], "Y": gradient["height"]},
    )
    assert solid_material is not None
    assert solid_material["FillColor"] == "#FF0000CC"
    assert solid_material["Opacity"] == 0.5
    assert solid_material["Stroke"]["Color"] == "#0000FF4C"
    assert gradient_material is not None
    assert gradient_material["Kind"] == "RadialGradient"
    assert gradient_material["Opacity"] == 0.5
    assert gradient_material["Stops"][0]["Color"] == "#FFFFFFCC"

    export = export_figma_plugin_package(document, tmp_path / "opacity")
    exchange = json.loads(
        (Path(export["output_dir"]) / "figma_exchange.json").read_text("utf-8")
    )
    exported = {row["name"]: row for row in exchange["document"]["objects"]}
    assert exported["Half solid and stroke"]["style"]["fills"][0] == (
        solid["style"]["fills"][0]
    )
    assert exported["Half gradient"]["style"]["fills"][0] == (
        gradient["style"]["fills"][0]
    )


def test_painter_gradient_brush_and_vector_path_render_distinct_stop_colors() -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_style_renderer import draw_ui_vector_paths, ui_fill_brush

    _app()
    style = {
        "fill": "#00000000",
        "fill_gradient": {
            "type": "linear",
            "start": {"x": 0.0, "y": 0.5},
            "end": {"x": 1.0, "y": 0.5},
            "width": {"x": 0.0, "y": 1.0},
            "stops": [
                {"position": 0.0, "color": "#FF0000FF"},
                {"position": 1.0, "color": "#0000FFFF"},
            ],
        },
    }
    image = QImage(80, 40, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.fillRect(QRectF(0, 0, 40, 40), ui_fill_brush(style))
    assert draw_ui_vector_paths(
        painter,
        QRectF(40, 0, 40, 40),
        {
            "vector_fill_geometry": [
                {
                    "path": "M 0 0 L 40 0 L 40 40 L 0 40 Z",
                    "winding_rule": "nonzero",
                }
            ]
        },
        style,
    )
    painter.end()

    assert image.pixelColor(3, 20).red() > image.pixelColor(3, 20).blue()
    assert image.pixelColor(36, 20).blue() > image.pixelColor(36, 20).red()
    assert image.pixelColor(43, 20).red() > image.pixelColor(43, 20).blue()
    assert image.pixelColor(76, 20).blue() > image.pixelColor(76, 20).red()


def test_figma_shadow_stack_preserves_drop_inner_order_and_legacy_alias() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["effects"] = [
        {
            "type": "DROP_SHADOW",
            "color": {"r": 1, "g": 0, "b": 0, "a": 0.5},
            "offset": {"x": -3, "y": 4},
            "radius": 8,
            "spread": 2,
            "blendMode": "MULTIPLY",
            "visible": True,
        },
        {
            "type": "INNER_SHADOW",
            "color": {"r": 0, "g": 0, "b": 1, "a": 0.25},
            "offset": {"x": 1, "y": 2},
            "radius": 3,
            "spread": -1,
            "visible": True,
        },
        {
            "type": "DROP_SHADOW",
            "color": {"r": 0, "g": 1, "b": 0, "a": 1},
            "offset": {"x": 0, "y": 12},
            "radius": 18,
            "visible": False,
        },
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    assert report["ok"] is True
    button = next(row for row in document["objects"] if row["name"] == "Primary Button")
    assert button["style"]["effects"] == [
        {
            "type": "drop_shadow",
            "color": "#FF000080",
            "x": -3.0,
            "y": 4.0,
            "blur": 8.0,
            "spread": 2.0,
            "blend_mode": "multiply",
        },
        {
            "type": "inner_shadow",
            "color": "#0000FF40",
            "x": 1.0,
            "y": 2.0,
            "blur": 3.0,
            "spread": -1.0,
            "blend_mode": "normal",
        },
    ]
    assert button["style"]["shadow"] == {
        "color": "#FF000080",
        "x": -3.0,
        "y": 4.0,
        "blur": 8.0,
        "spread": 2.0,
    }


def test_figma_blur_effects_preserve_type_radius_and_export_code(
    tmp_path: Path,
) -> None:
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
    )

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["effects"] = [
        {"type": "LAYER_BLUR", "radius": 7, "visible": True},
        {"type": "BACKGROUND_BLUR", "radius": 18, "visible": True},
    ]
    document, report = import_figma_payload(payload, source="AbCdEf123456")
    assert report["ok"] is True
    button = next(
        row for row in document["objects"] if row["name"] == "Primary Button"
    )
    assert button["style"]["effects"] == [
        {"type": "layer_blur", "radius": 7.0},
        {"type": "background_blur", "radius": 18.0},
    ]

    package = export_figma_plugin_package(document, tmp_path)
    code = (
        Path(package["output_dir"]) / "code.js"
    ).read_text(encoding="utf-8")
    assert "LAYER_BLUR" in code
    assert "BACKGROUND_BLUR" in code


def test_figma_frame_clip_content_round_trips_as_editable_property(
    tmp_path: Path,
) -> None:
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
    )

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["clipsContent"] = True
    document, report = import_figma_payload(payload, source="AbCdEf123456")
    assert report["ok"] is True
    frame = next(
        row for row in document["objects"] if row["name"] == "Primary Button"
    )
    assert frame["kind"] == "frame"
    assert frame["clip_content"] is True

    package = export_figma_plugin_package(document, tmp_path)
    code = (
        Path(package["output_dir"]) / "code.js"
    ).read_text(encoding="utf-8")
    assert "node.clipsContent=!!row.clip_content" in code


def test_painter_renders_multiple_outer_and_inner_shadow_effects() -> None:
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_style_renderer import (
        draw_ui_object_inner_shadows,
        draw_ui_object_shadow,
    )

    _app()
    image = QImage(80, 60, QImage.Format.Format_ARGB32)
    image.fill(0)
    rect = QRectF(20, 15, 40, 30)
    style = {
        "radius": 0,
        "effects": [
            {
                "type": "drop_shadow",
                "color": "#FF0000FF",
                "x": -8,
                "y": 0,
                "blur": 0,
                "spread": 2,
            },
            {
                "type": "drop_shadow",
                "color": "#0000FFFF",
                "x": 8,
                "y": 0,
                "blur": 0,
                "spread": 2,
            },
            {
                "type": "inner_shadow",
                "color": "#00FF00FF",
                "x": 0,
                "y": 0,
                "blur": 6,
                "spread": 0,
            },
        ],
    }
    painter = QPainter(image)
    assert draw_ui_object_shadow(painter, rect, "rectangle", style)
    painter.fillRect(rect, QColor("#FFFFFFFF"))
    assert draw_ui_object_inner_shadows(painter, rect, "rectangle", style)
    painter.end()

    assert image.pixelColor(14, 30).red() > image.pixelColor(14, 30).blue()
    assert image.pixelColor(66, 30).blue() > image.pixelColor(66, 30).red()
    assert image.pixelColor(22, 30).green() > image.pixelColor(22, 30).red()
    assert image.pixelColor(40, 30) == QColor("#FFFFFFFF")


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
                    "opacity": 0.65,
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
    assert image["style"]["fills"][0]["type"] == "image"
    assert image["style"]["fills"][0]["opacity"] == 0.65
    assert image["style"]["fills"][0]["source_path"] == ""
    assert report["resources"]["missing_image_count"] == 0

    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    umg = painter_ui_to_umg_document(document)
    layer = next(row for row in umg["Layers"] if row["Id"] == image["id"])
    assert layer["Disposition"] == "Native"
    assert layer["ImageFill"]["AssetId"] == layer["AssetId"]
    assert layer["ImageFill"]["Mode"] == "Fill"
    assert layer["ImageFill"]["Opacity"] == 0.65
    # Resources are sorted by id and now include the text font face, so this
    # has to name the resource it means rather than index the first one.
    texture = next(
        row for row in umg["Resources"] if row["Kind"] == "texture"
    )
    assert texture["SourcePath"] == str(image_path)


def test_figma_rest_stretch_transform_renders_and_maps_to_umg_crop(
    tmp_path: Path,
) -> None:
    _app()
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_asset_export import render_ui_artboard
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    image_path = tmp_path / "figma-stretch.png"
    source = QImage(100, 60, QImage.Format.Format_ARGB32)
    source.fill(QColor("#35B96B"))
    painter = QPainter(source)
    painter.fillRect(0, 0, 50, 60, QColor("#DD3344"))
    painter.end()
    assert source.save(str(image_path), "PNG")
    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "9:44",
            "type": "RECTANGLE",
            "name": "REST stretch crop",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 100,
                "height": 60,
            },
            "fills": [
                {
                    "type": "IMAGE",
                    "imageRef": "stretch-ref",
                    "scaleMode": "STRETCH",
                    "imageTransform": [
                        [0.5, 0.0, 0.5],
                        [0.0, 1.0, 0.0],
                    ],
                    "opacity": 0.75,
                }
            ],
        }
    )

    document, report = import_figma_payload(
        payload,
        source="AbCdEf123456",
        image_paths={"stretch-ref": str(image_path)},
    )
    row = next(item for item in document["objects"] if item["name"] == "REST stretch crop")
    assert row["content"]["image_fit"] == "stretch"
    assert row["content"]["image_opacity"] == 0.75
    assert row["content"]["figma_image_transform"] == [
        [0.5, 0.0, 0.5],
        [0.0, 1.0, 0.0],
    ]
    assert row["content"]["figma_image_transform_semantics"] == (
        "target_normalized_to_source_normalized"
    )
    assert not any(
        "figma_image_transform" in warning for warning in report["warnings"]
    )

    rendered = render_ui_artboard(document, document["active_artboard_id"])
    sampled = rendered.pixelColor(50, 70)
    assert sampled.green() > sampled.red()
    assert sampled.green() > sampled.blue()

    umg = painter_ui_to_umg_document(document)
    layer = next(item for item in umg["Layers"] if item["Id"] == row["id"])
    assert layer["Disposition"] == "Native"
    assert layer["ImageFill"]["Mode"] == "Crop"
    assert layer["ImageFill"]["Crop"] == {
        "Enabled": True,
        "Units": "Normalized",
        "X": 0.5,
        "Y": 0.0,
        "Width": 0.5,
        "Height": 1.0,
    }


def test_figma_image_paint_preserves_tile_filters_and_crop_transform() -> None:
    from app.painter_ui_figma import map_figma_plugin_paints

    paint = map_figma_plugin_paints(
        [
            {
                "type": "IMAGE",
                "visible": True,
                "opacity": 0.8,
                "scaleMode": "CROP",
                "scalingFactor": 1.5,
                "rotation": 12,
                "filters": {
                    "contrast": 0.25,
                    "saturation": -0.5,
                    "shadows": 0.125,
                },
                "imageTransform": [[1, 0, 0.1], [0, 1, 0.2]],
            }
        ]
    )[0]

    assert paint["type"] == "image"
    assert paint["fit"] == "crop"
    assert paint["tile_scale"] == 1.5
    assert paint["rotation"] == 12
    assert paint["adjustments"]["contrast"] == 25
    assert paint["adjustments"]["saturation"] == -50
    assert paint["adjustments"]["shadows"] == 12.5
    assert paint["figma_image_transform"] == [
        [1, 0, 0.1],
        [0, 1, 0.2],
    ]


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


def test_figma_center_constraints_preserve_authored_offset_on_first_resolve() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_motion_bridge import resolved_ui_geometry

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["layoutMode"] = "NONE"
    frame["absoluteBoundingBox"] = {
        "x": 100,
        "y": 200,
        "width": 1280,
        "height": 720,
    }
    frame["children"] = [
        {
            "id": "2:99",
            "type": "RECTANGLE",
            "name": "Centered tutorial hint",
            "absoluteBoundingBox": {
                "x": 1312,
                "y": 868,
                "width": 40,
                "height": 40,
            },
            "constraints": {
                "horizontal": "CENTER",
                "vertical": "CENTER",
            },
        }
    ]

    document, report = import_figma_payload(payload)

    assert report["ok"] is True
    hint = document["objects"][0]
    assert (hint["x"], hint["y"]) == (1212.0, 668.0)
    assert hint["constraints"]["center_offset_x"] == 592.0
    assert hint["constraints"]["center_offset_y"] == 328.0

    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(document),
    )
    assert geometry[hint["id"]] == {
        "x": 1212.0,
        "y": 668.0,
        "width": 40.0,
        "height": 40.0,
    }


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


def test_figma_negative_spacing_preserves_flow_order_and_reverse_z_metadata() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import (
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_motion_bridge import resolved_ui_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    artboard["children"] = [
        {
            "id": "8:20",
            "type": "FRAME",
            "name": "Overlapping avatars",
            "layoutMode": "HORIZONTAL",
            "itemSpacing": -20,
            "itemReverseZIndex": True,
            "primaryAxisAlignItems": "MIN",
            "counterAxisAlignItems": "MIN",
            "layoutSizingHorizontal": "FIXED",
            "layoutSizingVertical": "FIXED",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 260,
                "width": 200,
                "height": 40,
            },
            "children": [
                {
                    "id": f"8:{index}",
                    "type": "RECTANGLE",
                    "name": f"Avatar {index}",
                    "absoluteBoundingBox": {
                        "x": x,
                        "y": 260,
                        "width": 80,
                        "height": 40,
                    },
                }
                for index, x in ((21, 140), (22, 200), (23, 260))
            ],
        }
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")
    rows = {row["name"]: row for row in document["objects"]}
    stack = rows["Overlapping avatars"]

    assert report["ok"] is True
    assert stack["layout"]["mode"] == "horizontal"
    assert stack["layout"]["gap"] == -20.0
    assert stack["layout"]["cross_gap"] == 0.0
    assert stack["layout"]["reverse_z_index"] is True
    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    # itemReverseZIndex changes overlapping paint stacking only. Source child
    # order remains the Auto Layout flow order.
    assert [geometry[rows[f"Avatar {index}"]["id"]]["x"] for index in range(21, 24)] == [
        40.0,
        100.0,
        160.0,
    ]


def test_figma_auto_layout_includes_visible_stroke_footprints() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_motion_bridge import resolved_ui_geometry
    from app.painter_ui_umg_auto_layout import painter_umg_auto_layout_contract

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    artboard["children"] = [
        {
            "id": "8:40",
            "type": "FRAME",
            "name": "Stroke footprint row",
            "layoutMode": "HORIZONTAL",
            "layoutSizingHorizontal": "HUG",
            "layoutSizingVertical": "HUG",
            "itemSpacing": 32,
            "strokesIncludedInLayout": True,
            "strokeWeight": 1,
            "strokeAlign": "INSIDE",
            "strokes": [
                {
                    "type": "SOLID",
                    "color": {"r": 0.8, "g": 0.7, "b": 1.0},
                }
            ],
            "absoluteBoundingBox": {
                "x": 140,
                "y": 260,
                "width": 354,
                "height": 98,
            },
            "children": [
                {
                    "id": f"8:{index}",
                    "type": "RECTANGLE",
                    "name": f"Outlined item {index}",
                    "layoutSizingHorizontal": "FIXED",
                    "layoutSizingVertical": "FIXED",
                    "strokeWeight": 8,
                    "strokeAlign": "OUTSIDE",
                    "strokes": [
                        {
                            "type": "SOLID",
                            "color": {"r": 0.1, "g": 0.1, "b": 0.1},
                        }
                    ],
                    "absoluteBoundingBox": {
                        "x": x,
                        "y": 269,
                        "width": 80,
                        "height": 80,
                    },
                }
                for index, x in ((41, 149), (42, 277), (43, 405))
            ],
        }
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")
    rows = {row["name"]: row for row in document["objects"]}
    parent = rows["Stroke footprint row"]

    assert report["ok"] is True
    assert parent["layout"]["include_strokes"] is True
    assert parent["layout"]["stroke_insets"] == {
        "left": 1.0,
        "top": 1.0,
        "right": 1.0,
        "bottom": 1.0,
    }
    assert rows["Outlined item 41"]["layout"]["stroke_outsets"] == {
        "left": 8.0,
        "top": 8.0,
        "right": 8.0,
        "bottom": 8.0,
    }

    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    assert geometry[parent["id"]] == {
        "x": 40.0,
        "y": 60.0,
        "width": 354.0,
        "height": 98.0,
    }
    assert [
        (
            geometry[rows[f"Outlined item {index}"]["id"]]["x"],
            geometry[rows[f"Outlined item {index}"]["id"]]["y"],
        )
        for index in (41, 42, 43)
    ] == [(49.0, 69.0), (177.0, 69.0), (305.0, 69.0)]

    contract = painter_umg_auto_layout_contract(document)
    assert contract["blockers_by_id"][parent["id"]] == [
        "auto_layout_strokes_included_requires_"
        "deterministic_bake_or_slot_spacers"
    ]


def test_figma_outer_reflection_flattens_local_auto_layout_snapshot() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import (
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_motion_bridge import resolved_ui_geometry
    from app.painter_ui_umg_adapter import preflight_painter_umg

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    artboard["children"] = [
        {
            "id": "8:30",
            "type": "GROUP",
            "name": "Reflected visuals",
            "relativeTransform": [[1, 0, 40], [0, -1, 180]],
            "size": {"x": 160, "y": 140},
            "absoluteBoundingBox": {
                "x": 140,
                "y": 240,
                "width": 160,
                "height": 140,
            },
            "children": [
                {
                    "id": "8:31",
                    "type": "FRAME",
                    "name": "Visual layout",
                    "layoutMode": "VERTICAL",
                    "itemSpacing": 20,
                    "primaryAxisAlignItems": "MIN",
                    "counterAxisAlignItems": "MIN",
                    "relativeTransform": [[1, 0, 20], [0, 1, 20]],
                    "size": {"x": 100, "y": 100},
                    "absoluteBoundingBox": {
                        "x": 160,
                        "y": 260,
                        "width": 100,
                        "height": 100,
                    },
                    "children": [
                        {
                            "id": "8:32",
                            "type": "RECTANGLE",
                            "name": "First reflected row",
                            "relativeTransform": [[1, 0, 0], [0, 1, 0]],
                            "size": {"x": 100, "y": 30},
                            "absoluteBoundingBox": {
                                "x": 160,
                                "y": 330,
                                "width": 100,
                                "height": 30,
                            },
                        },
                        {
                            "id": "8:33",
                            "type": "RECTANGLE",
                            "name": "Second reflected row",
                            "relativeTransform": [[1, 0, 0], [0, 1, 50]],
                            "size": {"x": 100, "y": 30},
                            "absoluteBoundingBox": {
                                "x": 160,
                                "y": 280,
                                "width": 100,
                                "height": 30,
                            },
                        },
                    ],
                }
            ],
        }
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")
    rows = {row["name"]: row for row in document["objects"]}
    stack = rows["Visual layout"]
    recovery = stack["content"]["figma_auto_layout_recovery"]

    assert report["ok"] is True
    assert stack["layout"]["mode"] == "none"
    assert recovery["reason_codes"] == ["outer_affine_transform"]
    assert recovery["outer_affine_ignored"] is True
    assert recovery["outer_affine_reason"] == (
        "outer_affine_snapshot_requires_reflection_support"
    )
    before = {
        row["id"]: {
            key: float(row[key]) for key in ("x", "y", "width", "height")
        }
        for row in (
            stack,
            rows["First reflected row"],
            rows["Second reflected row"],
        )
    }
    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    assert {object_id: geometry[object_id] for object_id in before} == before
    assert geometry[rows["First reflected row"]["id"]]["y"] > geometry[
        rows["Second reflected row"]["id"]
    ]["y"]

    compatibility = inspect_figma_compatibility(document)
    outer_affine = next(
        row
        for row in compatibility["objects"]
        if row["id"] == f"{stack['id']}:outer-affine-transform"
    )
    assert outer_affine["status"] == "blocked"
    assert outer_affine["reason"] == (
        "outer_affine_snapshot_requires_reflection_support"
    )
    preflight = preflight_painter_umg(document)
    assert any(
        row["object_id"] == stack["id"]
        and "figma_transformed_auto_layout_requires_affine_layout"
        in row["reasons"]
        for row in preflight["blockers"]
    )


def test_figma_ordinary_orthogonal_affine_uses_cumulative_matrix_geometry() -> None:
    import math
    import pytest

    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    diagonal_extent = 10.0 / math.sqrt(2.0)
    artboard["children"] = [
        {
            "id": "8:40",
            "type": "RECTANGLE",
            "name": "Ordinary rotated rectangle",
            # REST archives can retain a radian-valued convenience field;
            # relativeTransform is the authoritative affine contract.
            "rotation": math.pi / 2.0,
            "relativeTransform": [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0]],
            "size": {"x": 20.0, "y": 40.0},
            "absoluteBoundingBox": {
                "x": 150.0,
                "y": 260.0,
                "width": 40.0,
                "height": 20.0,
            },
        },
        {
            "id": "8:41",
            "type": "LINE",
            "name": "Zero-width diagonal",
            "rotation": -math.pi / 4.0,
            "relativeTransform": [
                [math.sqrt(0.5), math.sqrt(0.5), 0.0],
                [-math.sqrt(0.5), math.sqrt(0.5), 0.0],
            ],
            "size": {"x": 0.0, "y": 10.0},
            "absoluteBoundingBox": {
                "x": 220.0,
                "y": 300.0,
                "width": diagonal_extent,
                "height": diagonal_extent,
            },
        },
    ]

    document, report = import_figma_payload(payload)
    rows = {row["name"]: row for row in document["objects"]}
    rectangle = rows["Ordinary rotated rectangle"]
    line = rows["Zero-width diagonal"]

    assert report["ok"] is True
    assert rectangle["width"] == 20.0
    assert rectangle["height"] == 40.0
    assert rectangle["rotation"] == 90.0
    affine = rectangle["content"]["figma_affine_snapshot_geometry"]
    assert affine["status"] == "rotation_scale_mapped"
    assert affine["scope"] == "ordinary_node_cumulative_transform"
    assert line["rotation"] == pytest.approx(-45.0)
    assert line["width"] == 1.0
    assert line["height"] == pytest.approx(9.0)
    assert line["content"]["figma_affine_snapshot_geometry"][
        "minimum_extent_adjustment"
    ]["strategy"] == "least_squares_source_aabb"

    geometry = measure_figma_geometry(payload, document)
    assert geometry["measured_count"] == 2
    assert geometry["excluded_count"] == 0
    assert geometry["max_drift_px"] == pytest.approx(0.0, abs=0.000001)


def test_figma_cancelling_parent_child_affine_consumes_raw_rotation() -> None:
    import math

    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    reflection = [[0.0, -1.0, 0.0], [-1.0, 0.0, 0.0]]
    artboard["children"] = [
        {
            "id": "8:42",
            "type": "GROUP",
            "name": "Reflected group",
            "rotation": -math.pi / 2.0,
            "relativeTransform": reflection,
            "size": {"x": 589.0, "y": 640.0},
            "absoluteBoundingBox": {
                "x": 120.0,
                "y": 220.0,
                "width": 640.0,
                "height": 589.0,
            },
            "children": [
                {
                    "id": "8:43",
                    "type": "RECTANGLE",
                    "name": "Cancelled mask",
                    # Archive convenience rotation values may be radians;
                    # the paired relative transforms are authoritative and
                    # multiply to identity in canvas space.
                    "rotation": -math.pi / 2.0,
                    "relativeTransform": reflection,
                    "size": {"x": 640.0, "y": 589.0},
                    "absoluteBoundingBox": {
                        "x": 120.0,
                        "y": 220.0,
                        "width": 640.0,
                        "height": 589.0,
                    },
                }
            ],
        }
    ]

    document, report = import_figma_payload(payload)
    mask = next(row for row in document["objects"] if row["name"] == "Cancelled mask")
    recovery = mask["content"]["figma_affine_snapshot_geometry"]

    assert mask["rotation"] == 0.0
    assert mask["width"] == 640.0
    assert mask["height"] == 589.0
    assert recovery["status"] == "cumulative_identity_consumed"
    assert recovery["source_rotation"] == -math.pi / 2.0
    assert recovery["rotation"] == 0.0
    assert (
        "converted:8:43:AFFINE:cumulative_identity_transform_consumed"
        in report["warnings"]
    )
    geometry = measure_figma_geometry(payload, document)
    measurement = next(
        row
        for row in geometry["object_measurements"]
        if row["source_node_id"] == "8:43"
    )
    assert measurement["drift_px"] == 0.0


def test_figma_legacy_intrinsic_text_radian_quarter_turn_recovers_local_box() -> None:
    import math

    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    artboard["children"] = [
        {
            "id": "8:44",
            "type": "TEXT",
            "name": "Legacy vertical label",
            "rotation": -math.pi / 2.0,
            "characters": "Ivantom",
            "style": {
                "fontFamily": "Inter",
                "fontSize": 128.0,
                "lineHeightPx": 154.90908813476562,
                "textAutoResize": "WIDTH_AND_HEIGHT",
            },
            "absoluteBoundingBox": {
                "x": 150.0,
                "y": 260.0,
                "width": 155.0,
                "height": 484.0,
            },
        }
    ]

    document, _report = import_figma_payload(payload)
    label = document["objects"][0]
    recovery = label["content"]["figma_affine_snapshot_geometry"]

    assert label["rotation"] == -90.0
    assert label["width"] == 484.0
    assert label["height"] == 155.0
    assert recovery["status"] == "rotation_scale_mapped"
    assert recovery["missing_local_size_recovery"] == (
        "quarter_turn_aabb_inverse"
    )
    assert recovery["source_rotation_unit_recovery"] == (
        "legacy_radians_inferred_from_text_line_height"
    )
    geometry = measure_figma_geometry(payload, document)
    assert geometry["measured_count"] == 1
    assert geometry["max_drift_px"] == 0.0


def test_figma_affine_near_zero_negative_size_uses_editable_minimum_extent() -> None:
    import math

    from app.painter_ui_figma import import_figma_payload
    from tools.qa_painter_ui_figma_geometry import measure_figma_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    artboard["children"] = [
        {
            "id": "8:45",
            "type": "VECTOR",
            "name": "Degenerate arrow",
            "rotation": -math.pi,
            "relativeTransform": [
                [-1.0, 0.0, 0.0],
                [0.0, -1.0, 0.0],
            ],
            "size": {"x": 44.0, "y": -0.000004},
            "absoluteBoundingBox": {
                "x": 150.0,
                "y": 260.0,
                "width": 44.0,
                "height": 0.000008,
            },
        }
    ]

    document, _report = import_figma_payload(payload)
    arrow = document["objects"][0]
    recovery = arrow["content"]["figma_affine_snapshot_geometry"]

    assert abs(abs(arrow["rotation"]) - 180.0) < 0.000001
    assert arrow["width"] == 44.0
    assert arrow["height"] == 1.0
    assert recovery["near_zero_negative_local_size_clamped"] == {
        "height": -0.000004,
    }
    assert recovery["minimum_extent_adjustment"]["axis"] == "height"
    geometry = measure_figma_geometry(payload, document)
    assert geometry["measured_count"] == 1
    assert geometry["max_drift_px"] <= 0.5


def test_figma_transformed_auto_layout_preserves_snapshot_absolute_geometry() -> None:
    import math
    import pytest

    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_motion_bridge import resolved_ui_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["relativeTransform"] = [
        [0.0, -1.0, 0.0],
        [-1.0, 0.0, 0.0],
    ]
    artboard["children"] = [
        {
            "id": "8:1",
            "type": "FRAME",
            "name": "Rotated stack",
            "layoutMode": "VERTICAL",
            "itemSpacing": 4.312737464904785,
            "primaryAxisSizingMode": "AUTO",
            "counterAxisSizingMode": "AUTO",
            "rotation": -0.7853981633974483,
            "relativeTransform": [
                [0.7071067690849304, 0.7071067690849304, -262.0],
                [-0.7071067690849304, 0.7071067690849304, -85.0],
            ],
            "size": {"x": 468.65081787109375, "y": 634.6912231445312},
            "absoluteBoundingBox": {
                "x": 140.0,
                "y": 220.0,
                "width": 780.1806258181314,
                "height": 780.1806258181314,
            },
            "children": [
                {
                    "id": "8:2",
                    "type": "RECTANGLE",
                    "name": "Rotated line AABB 1",
                    "relativeTransform": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                    "size": {"x": 468.65081787109375, "y": 0.7187896370887756},
                    "absoluteBoundingBox": {
                        "x": 588.2862,
                        "y": 668.2862,
                        "width": 331.89442667177264,
                        "height": 331.89442667177264,
                    },
                },
                {
                    "id": "8:3",
                    "type": "RECTANGLE",
                    "name": "Rotated line AABB 2",
                    "relativeTransform": [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 633.972900390625],
                    ],
                    "size": {"x": 468.65081787109375, "y": 0.7187896370887756},
                    "absoluteBoundingBox": {
                        "x": 140.0,
                        "y": 220.0,
                        "width": 331.89442667177264,
                        "height": 331.89442667177264,
                    },
                },
            ],
        }
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")
    stack = next(row for row in document["objects"] if row["name"] == "Rotated stack")
    recovery = stack["content"]["figma_auto_layout_recovery"]

    assert stack["layout"]["mode"] == "none"
    # Flatten only the container's internal flow. It must retain its original
    # participation in an outer Auto Layout parent.
    assert stack["layout"]["positioning"] == "auto"
    assert stack["layout"]["width_sizing"] == "fixed"
    assert stack["layout"]["height_sizing"] == "fixed"
    assert recovery["status"] == "snapshot_absolute_geometry"
    assert recovery["reason"] == "transformed_auto_layout_requires_affine_layout"
    assert recovery["mapped_layout"]["mode"] == "vertical"
    assert recovery["source_layout"]["layoutMode"] == "VERTICAL"
    assert recovery["relative_transform"] == payload["document"]["children"][0][
        "children"
    ][0]["children"][0]["relativeTransform"]
    assert recovery["affected_child_ids"] == ["8:2", "8:3"]
    assert recovery["outer_affine_ignored"] is True
    assert recovery["outer_affine_reason"] == (
        "outer_affine_snapshot_requires_reflection_support"
    )
    assert (
        "converted:figma-node-8-1:"
        "transformed_auto_layout_flattened_to_snapshot_absolute_geometry"
    ) in report["warnings"]
    assert (
        "blocked:8:1:AFFINE:"
        "outer_affine_snapshot_requires_reflection_support"
    ) in report["warnings"]

    first_line = next(
        row
        for row in document["objects"]
        if row["name"] == "Rotated line AABB 1"
    )
    assert stack["width"] == pytest.approx(468.65081787109375)
    assert stack["height"] == pytest.approx(634.6912231445312)
    assert stack["rotation"] == pytest.approx(-45.0)
    assert first_line["width"] == pytest.approx(468.65081787109375)
    assert first_line["height"] == 1.0
    assert first_line["rotation"] == pytest.approx(-45.0)
    affine = first_line["content"]["figma_affine_snapshot_geometry"]
    assert affine["status"] == "rotation_scale_mapped"
    assert affine["effective_linear_transform"][0][0] == 0.7071067690849304
    assert affine["effective_linear_transform"][1][0] == -0.7071067690849304
    source_bounds = payload["document"]["children"][0]["children"][0][
        "children"
    ][0]["children"][0]["absoluteBoundingBox"]
    artboard_bounds = artboard["absoluteBoundingBox"]
    assert first_line["x"] + first_line["width"] * 0.5 == pytest.approx(
        source_bounds["x"]
        + source_bounds["width"] * 0.5
        - artboard_bounds["x"]
    )
    assert first_line["y"] + first_line["height"] * 0.5 == pytest.approx(
        source_bounds["y"]
        + source_bounds["height"] * 0.5
        - artboard_bounds["y"]
    )
    direction_x = math.cos(math.radians(first_line["rotation"]))
    direction_y = math.sin(math.radians(first_line["rotation"]))
    assert direction_x > 0.0
    assert direction_y < 0.0
    rendered_aabb_width = (
        abs(first_line["width"] * direction_x)
        + abs(first_line["height"] * direction_y)
    )
    assert abs(rendered_aabb_width - source_bounds["width"]) < 1.0

    source_geometry = {
        str(row["id"]): {
            key: float(row[key]) for key in ("x", "y", "width", "height")
        }
        for row in document["objects"]
    }
    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(
            document,
            normalize=False,
            resolve_responsive=False,
        ),
    )
    for object_id, expected in source_geometry.items():
        assert geometry[object_id] == expected

    roundtrip = normalize_ui_document(json.loads(json.dumps(document)))
    roundtrip_stack = next(
        row for row in roundtrip["objects"] if row["id"] == stack["id"]
    )
    assert roundtrip_stack["content"]["figma_auto_layout_recovery"] == recovery
    compatibility = inspect_figma_compatibility(document)
    converted = next(
        row
        for row in compatibility["objects"]
        if row["id"] == f"{stack['id']}:transformed-auto-layout"
    )
    assert converted["status"] == "converted"
    outer_affine = next(
        row
        for row in compatibility["objects"]
        if row["id"] == f"{stack['id']}:outer-affine-transform"
    )
    assert outer_affine == {
        "id": f"{stack['id']}:outer-affine-transform",
        "status": "blocked",
        "reason": "outer_affine_snapshot_requires_reflection_support",
    }


def test_figma_flattened_auto_layout_keeps_outer_flow_participation() -> None:
    from app.painter_ui_constraints import resolve_ui_constraints
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_motion_bridge import resolved_ui_geometry

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["layoutMode"] = "NONE"
    artboard["children"] = [
        {
            "id": "8:10",
            "type": "FRAME",
            "name": "Hug column",
            "layoutMode": "VERTICAL",
            "layoutSizingHorizontal": "FIXED",
            "layoutSizingVertical": "HUG",
            "itemSpacing": 10,
            "absoluteBoundingBox": {
                "x": 140,
                "y": 260,
                "width": 100,
                "height": 70,
            },
            "children": [
                {
                    "id": "8:11",
                    "type": "RECTANGLE",
                    "name": "First row",
                    "layoutSizingHorizontal": "FIXED",
                    "layoutSizingVertical": "FIXED",
                    "absoluteBoundingBox": {
                        "x": 140,
                        "y": 260,
                        "width": 100,
                        "height": 20,
                    },
                },
                {
                    "id": "8:12",
                    "type": "FRAME",
                    "name": "Flattened affine row",
                    "layoutMode": "HORIZONTAL",
                    "layoutSizingHorizontal": "FIXED",
                    "layoutSizingVertical": "FIXED",
                    "size": {"x": 100, "y": 40},
                    "absoluteBoundingBox": {
                        "x": 140,
                        "y": 290,
                        "width": 100,
                        "height": 40,
                    },
                    "children": [
                        {
                            "id": "8:13",
                            "type": "RECTANGLE",
                            "name": "Rotated content",
                            "size": {"x": 20, "y": 20},
                            "relativeTransform": [
                                [0.70710678, -0.70710678, 0],
                                [0.70710678, 0.70710678, 0],
                            ],
                            "absoluteBoundingBox": {
                                "x": 150,
                                "y": 296,
                                "width": 28.2842712,
                                "height": 28.2842712,
                            },
                        }
                    ],
                },
            ],
        }
    ]

    document, report = import_figma_payload(payload)
    assert report["ok"] is True
    rows = {row["name"]: row for row in document["objects"]}
    column = rows["Hug column"]
    affine_row = rows["Flattened affine row"]
    assert affine_row["content"]["figma_auto_layout_recovery"]["status"] == (
        "snapshot_absolute_geometry"
    )
    assert affine_row["layout"]["mode"] == "none"
    assert affine_row["layout"]["positioning"] == "auto"

    geometry = resolve_ui_constraints(
        document,
        resolved_ui_geometry(document),
    )
    assert geometry[column["id"]]["height"] == 70.0
    assert geometry[affine_row["id"]] == {
        "x": 40.0,
        "y": 90.0,
        "width": 100.0,
        "height": 40.0,
    }


def test_figma_hug_fill_cycle_uses_resolved_parent_size_without_moving_geometry() -> None:
    from app.painter_ui_document import validate_ui_document
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    artboard = payload["document"]["children"][0]["children"][0]
    artboard["children"] = [
        {
            "id": "8:1",
            "type": "FRAME",
            "name": "Hug card",
            "layoutMode": "HORIZONTAL",
            "layoutSizingHorizontal": "HUG",
            "layoutSizingVertical": "HUG",
            "absoluteBoundingBox": {
                "x": 140,
                "y": 260,
                "width": 246,
                "height": 92,
            },
            "children": [
                {
                    "id": "8:2",
                    "type": "RECTANGLE",
                    "name": "Fill body",
                    "layoutSizingHorizontal": "FILL",
                    "layoutSizingVertical": "FILL",
                    "absoluteBoundingBox": {
                        "x": 140,
                        "y": 260,
                        "width": 246,
                        "height": 92,
                    },
                },
                {
                    "id": "8:3",
                    "type": "RECTANGLE",
                    "name": "Absolute decoration",
                    "layoutSizingHorizontal": "FILL",
                    "layoutSizingVertical": "FILL",
                    "layoutPositioning": "ABSOLUTE",
                    "absoluteBoundingBox": {
                        "x": 150,
                        "y": 270,
                        "width": 32,
                        "height": 32,
                    },
                },
            ],
        }
    ]

    document, report = import_figma_payload(payload, source="AbCdEf123456")

    parent = next(
        row for row in document["objects"] if row["id"] == "figma-node-8-1"
    )
    child = next(
        row for row in document["objects"] if row["id"] == "figma-node-8-2"
    )
    assert (parent["x"], parent["y"], parent["width"], parent["height"]) == (
        40.0,
        60.0,
        246.0,
        92.0,
    )
    assert (child["x"], child["y"], child["width"], child["height"]) == (
        40.0,
        60.0,
        246.0,
        92.0,
    )
    assert parent["layout"]["width_sizing"] == "fixed"
    assert parent["layout"]["height_sizing"] == "fixed"
    assert child["layout"]["width_sizing"] == "fill"
    assert child["layout"]["height_sizing"] == "fill"
    assert report["ok"] is True
    assert validate_ui_document(document)["errors"] == []
    assert (
        "converted:figma-node-8-1:layout.width_sizing:hug_to_fixed:"
        "figma_hug_fill_cycle_preserve_absolute_geometry:figma-node-8-2"
        in report["warnings"]
    )
    assert (
        "converted:figma-node-8-1:layout.height_sizing:hug_to_fixed:"
        "figma_hug_fill_cycle_preserve_absolute_geometry:figma-node-8-2"
        in report["warnings"]
    )
    assert all("figma-node-8-3" not in warning for warning in report["warnings"])


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
    assert "figma.combineAsVariants" in code
    assert "node.setProperties(values)" in code
    assert "ordered.filter(isInstanceRoot)" in code
    assert "GRADIENT_LINEAR" in code
    assert "gradientHandlePositions" in code
    assert "INNER_SHADOW" in code
    assert "node.effects=effectRows(s)" in code
    assert "node.cornerSmoothing=Math.max(0,Math.min(1" in code
    assert "function imagePaint(row,imageHash)" in code
    assert "result.imageTransform=transform||[[1,0,0],[0,1,0]]" in code
    assert "result.scalingFactor=Math.max(.0001" in code
    assert "'highlights','shadows'" in code


def test_figma_export_preserves_component_family_and_variant_properties(
    tmp_path: Path,
) -> None:
    from app.painter_ui_components import (
        add_ui_component_change_to_interaction,
        bind_ui_component_property,
        convert_ui_object_to_component,
        create_ui_component_variant,
        instantiate_ui_component,
        resolve_ui_component_document,
        set_ui_instance_component_property,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_figma import export_figma_plugin_package

    document = create_ui_document(800, 600, name="Components")
    artboard = document["artboards"][0]
    document, root = add_ui_object(
        document,
        kind="button",
        name="Button",
        artboard_id=artboard["id"],
        x=40,
        y=40,
        width=160,
        height=48,
    )
    document, label = add_ui_object(
        document,
        kind="text",
        name="Label",
        artboard_id=artboard["id"],
        parent_id=root["id"],
        x=72,
        y=54,
        width=96,
        height=24,
        content={"text": "Continue"},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Button",
    )
    component["property_definitions"].update(
        {
            "Label": {
                "type": "text",
                "default": "Continue",
                "values": [],
                "description": "",
            },
            "Leading icon": {
                "type": "boolean",
                "default": True,
                "values": [],
                "description": "",
            },
        }
    )
    for index, row in enumerate(document["components"]):
        if row["id"] == component["id"]:
            document["components"][index] = component
            break
    document, _ = bind_ui_component_property(
        document,
        component_id=component["id"],
        source_object_id=label["id"],
        property_name="Label",
        target_path="content.text",
    )
    document, variant = create_ui_component_variant(
        document,
        component_id=component["id"],
        name="Button / Pressed",
        variant_key="state=pressed",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=variant["id"],
        x=280,
        y=40,
    )
    document, _change_to = add_ui_component_change_to_interaction(
        document,
        source_component_id=component["id"],
        target_component_id=variant["id"],
        trigger="click",
    )
    document, _ = set_ui_instance_component_property(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Label",
        property_value="Buy now",
    )
    resolved = resolve_ui_component_document(document)
    resolved_instance_label = next(
        row
        for row in resolved["objects"]
        if row["component_role"] == "instance"
        and row["kind"] == "text"
    )
    assert resolved_instance_label["content"]["text"] == "Buy now"

    report = export_figma_plugin_package(document, tmp_path / "out")
    target = Path(report["output_dir"])
    exchange = json.loads((target / "figma_exchange.json").read_text("utf-8"))
    family = next(
        row for row in exchange["document"]["components"] if not row["base_component_id"]
    )
    exported_variant = next(
        row for row in exchange["document"]["components"] if row["base_component_id"]
    )
    exported_instance = next(
        row
        for row in exchange["document"]["objects"]
        if row["component_role"] == "instance"
        and not row["parent_id"]
    )
    assert family["variant_ids"] == [exported_variant["id"]]
    assert family["property_definitions"]["Label"]["type"] == "text"
    assert family["property_definitions"]["Leading icon"]["type"] == "boolean"
    assert exported_variant["metadata"]["variant_key"] == "state=pressed"
    assert exported_instance["component_properties"]["Label"] == "Buy now"
    exported_label = next(
        row
        for row in exchange["document"]["objects"]
        if row["id"] == label["id"]
    )
    assert exported_label["component_property_bindings"] == {
        "content.text": "Label"
    }
    code = (target / "code.js").read_text("utf-8")
    assert "node.componentPropertyReferences=references" in code
    assert "'CHANGE_TO'" in code
    assert "preferredValues:" in code


def test_figma_export_blocks_unsupported_component_property_type(
    tmp_path: Path,
) -> None:
    import pytest

    from app.painter_ui_components import convert_ui_object_to_component
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_figma import (
        PainterUIFigmaError,
        export_figma_plugin_package,
        inspect_figma_compatibility,
    )

    document = create_ui_document(640, 480, name="Unsupported property")
    document, root = add_ui_object(document, kind="button", name="Button")
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    component["property_definitions"]["Slot"] = {
        "type": "slot",
        "default": "",
        "values": [],
        "description": "",
    }
    document["components"][0] = component

    compatibility = inspect_figma_compatibility(document)

    assert compatibility["counts"]["blocked"] == 1
    assert compatibility["objects"][-1]["id"] == f"{component['id']}:Slot"
    with pytest.raises(PainterUIFigmaError, match="blocked"):
        export_figma_plugin_package(document, tmp_path / "out")


def test_figma_slot_import_and_export_preserve_native_slot_contract(
    tmp_path: Path,
) -> None:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )

    payload = {
        "name": "Slot import",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "type": "CANVAS",
                    "name": "Page 1",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "COMPONENT",
                            "name": "Card",
                            "componentPropertyDefinitions": {
                                "Content#1:9": {
                                    "type": "SLOT",
                                    "defaultValue": "1:2",
                                    "description": "Flexible card body",
                                    "preferredValues": [],
                                    "slotSettings": {
                                        "stretchChildOnInsert": True,
                                        "displayEmptyByDefault": True,
                                        "minChildren": 0,
                                        "maxChildren": 4,
                                        "allowPreferredValuesOnly": False,
                                    },
                                }
                            },
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 320,
                                "height": 240,
                            },
                            "children": [
                                {
                                    "id": "1:2",
                                    "type": "SLOT",
                                    "name": "Content",
                                    "absoluteBoundingBox": {
                                        "x": 20,
                                        "y": 20,
                                        "width": 280,
                                        "height": 180,
                                    },
                                    "children": [],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
        "components": {"1:1": {"key": "card-key", "name": "Card"}},
    }
    imported, report = import_figma_payload(payload, source="SlotFile123")
    assert report["ok"] is True
    imported_component = imported["components"][0]
    imported_definition = imported_component["property_definitions"]["Content"]
    assert imported_definition["type"] == "slot"
    assert imported_definition["default"] == "figma-node-1-2"
    assert imported_definition["slot_settings"]["max_children"] == 4
    imported_slot = next(
        row for row in imported["objects"] if row["id"] == "figma-node-1-2"
    )
    assert imported_slot["component_slot_property"] == "Content"

    document = create_ui_document(640, 480, name="Slot export")
    document, root = add_ui_object(document, kind="frame", name="Card")
    document, slot = add_ui_object(
        document,
        kind="frame",
        name="Content",
        parent_id=root["id"],
    )
    document, component = convert_ui_object_to_component(
        document, root_object_id=root["id"], name="Card"
    )
    document, _ = define_ui_component_slot(
        document,
        component_id=component["id"],
        source_object_id=slot["id"],
        property_name="Content",
        description="Flexible card body",
        slot_settings={"max_children": 4, "display_empty_by_default": True},
    )
    compatibility = inspect_figma_compatibility(document)
    assert compatibility["counts"]["blocked"] == 0
    target = tmp_path / "slot-plugin"
    export_report = export_figma_plugin_package(document, target)
    code = (Path(export_report["output_dir"]) / "code.js").read_text("utf-8")
    assert "parent.createSlot()" in code
    assert "type==='slot'" in code
    assert "allowPreferredValuesOnly" in code


def test_figma_shared_plugin_data_preserves_object_component_and_slot_ids() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "name": "Stable roundtrip",
        "document": {"id": "0:0", "type": "DOCUMENT", "children": [{
            "id": "0:1", "type": "CANVAS", "name": "Page 1", "children": [{
                "id": "1:1", "type": "FRAME", "name": "Board",
                "absoluteBoundingBox": {"x": 0, "y": 0, "width": 640, "height": 480},
                "children": [{
                    "id": "1:2", "type": "COMPONENT", "name": "Card",
                    "sharedPluginData": {"tigerstudio": {
                        "stable_id": "ui-object-card", "component_id": "ui-component-card",
                    }},
                    "componentPropertyDefinitions": {
                        "Content#1:9": {"type": "SLOT", "defaultValue": "1:3"}
                    },
                    "absoluteBoundingBox": {"x": 20, "y": 20, "width": 280, "height": 180},
                    "children": [{
                        "id": "1:3", "type": "SLOT", "name": "Content",
                        "sharedPluginData": {"tigerstudio": {"stable_id": "ui-object-slot"}},
                        "absoluteBoundingBox": {"x": 40, "y": 40, "width": 240, "height": 120},
                        "children": [],
                    }],
                }, {
                    "id": "1:4", "type": "INSTANCE", "name": "Card Instance",
                    "componentId": "1:2",
                    "sharedPluginData": {"tigerstudio": {
                        "stable_id": "ui-object-instance", "component_id": "ui-component-card",
                    }},
                    "absoluteBoundingBox": {"x": 320, "y": 20, "width": 280, "height": 180},
                    "children": [],
                }],
            }],
        }]},
        "components": {"1:2": {"key": "card-key", "name": "Card"}},
    }

    imported, report = import_figma_payload(payload, source="StableFile123")

    assert report["ok"] is True
    assert {row["id"] for row in imported["objects"]} >= {
        "ui-object-card", "ui-object-slot", "ui-object-instance",
    }
    component = next(row for row in imported["components"] if row["id"] == "ui-component-card")
    assert component["root_object_id"] == "ui-object-card"
    assert component["property_definitions"]["Content"]["default"] == "ui-object-slot"
    instance = next(row for row in imported["objects"] if row["id"] == "ui-object-instance")
    assert instance["component_id"] == "ui-component-card"
    assert instance["component_source_object_id"] == "ui-object-card"


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


def test_figma_import_accepts_single_rest_frame_fragment() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "id": "10:1",
        "name": "Fragment Card",
        "type": "FRAME",
        "absoluteBoundingBox": {"x": 40, "y": 80, "width": 320, "height": 180},
        "children": [
            {
                "id": "10:2",
                "name": "Card title",
                "type": "TEXT",
                "characters": "A real REST node fragment",
                "absoluteBoundingBox": {
                    "x": 64,
                    "y": 104,
                    "width": 220,
                    "height": 24,
                },
                "style": {"fontFamily": "Inter", "fontSize": 18},
                "fills": [
                    {"type": "SOLID", "color": {"r": 0.1, "g": 0.2, "b": 0.3}}
                ],
            }
        ],
    }

    document, report = import_figma_payload(payload, source="fragment.json")

    assert report["artboard_count"] == 1
    assert report["object_count"] == 1
    assert document["artboards"][0]["name"] == "Fragment Card"
    assert document["objects"][0]["kind"] == "text"
    assert document["objects"][0]["content"]["text"] == "A real REST node fragment"


def test_figma_import_wraps_single_leaf_fragment_in_an_artboard() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = {
        "id": "20:1",
        "name": "Standalone label",
        "type": "TEXT",
        "characters": "Leaf fixture",
        "absoluteBoundingBox": {"x": 10, "y": 20, "width": 120, "height": 30},
        "style": {"fontFamily": "Inter", "fontSize": 16},
    }

    document, report = import_figma_payload(payload, source="leaf.json")

    assert report["artboard_count"] == 1
    assert report["object_count"] == 1
    assert document["objects"][0]["kind"] == "text"
    assert document["objects"][0]["x"] == 0.0
    assert document["objects"][0]["y"] == 0.0


def test_figma_import_preserves_and_blocks_unsupported_conic_gradient() -> None:
    from app.painter_ui_figma import import_figma_payload, inspect_figma_compatibility
    from app.painter_ui_umg_adapter import preflight_painter_umg

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "30:1",
            "name": "Angular gradient",
            "type": "RECTANGLE",
            "absoluteBoundingBox": {"x": 140, "y": 320, "width": 120, "height": 80},
            "fills": [
                {
                    "type": "GRADIENT_ANGULAR",
                    "gradientHandlePositions": [
                        {"x": 0.5, "y": 0.5},
                        {"x": 1.0, "y": 0.5},
                        {"x": 0.5, "y": 1.0},
                    ],
                    "gradientStops": [
                        {"position": 0, "color": {"r": 1, "g": 0, "b": 0, "a": 1}},
                        {"position": 1, "color": {"r": 0, "g": 0, "b": 1, "a": 1}},
                    ],
                }
            ],
        }
    )

    document, report = import_figma_payload(payload, source="angular.json")
    angular = next(row for row in document["objects"] if row["name"] == "Angular gradient")

    unsupported = angular["content"]["figma_unsupported_paints"]
    assert unsupported[0]["type"] == "GRADIENT_ANGULAR"
    assert unsupported[0]["target"] == "fills"
    assert any("GRADIENT_ANGULAR" in warning for warning in report["warnings"])
    assert inspect_figma_compatibility(document)["counts"]["blocked"] == 1
    preflight = preflight_painter_umg(document)
    assert any(
        "figma_conic_or_diamond_gradient_requires_material_or_bake"
        in blocker["reasons"]
        for blocker in preflight["blockers"]
    )


def test_figma_import_reads_modern_rest_interactions_field() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    component["interactions"] = component.pop("reactions")

    document, report = import_figma_payload(payload, source="modern-interactions.json")

    assert report["interaction_count"] == 1
    assert len(document["interactions"]) == 1
    assert document["interactions"][0]["action"] == "navigate"


def test_figma_on_hover_scroll_to_roundtrips_and_exports_as_native_reaction(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    payload = _figma_payload()
    component = payload["document"]["children"][0]["children"][0]["children"][0]
    raw_reaction = {
        "trigger": {"type": "ON_HOVER"},
        "actions": [
            {
                "type": "NODE",
                "destinationId": "3:1",
                "navigation": "SCROLL_TO",
                "transition": {"type": "DISSOLVE", "duration": 0.2},
                "preserveScrollPosition": True,
            }
        ],
    }
    component["reactions"] = [raw_reaction]

    document, report = import_figma_payload(
        payload,
        source="native-hover-scroll.json",
    )

    assert report["source_reaction_count"] == 1
    assert report["source_reaction_action_count"] == 1
    assert report["native_reaction_count"] == 1
    assert report["native_reaction_action_count"] == 1
    assert report["blocked_recovery_reaction_count"] == 0
    assert report["blocked_recovery_action_count"] == 0
    assert report["reaction_count_conserved"] is True
    assert report["reaction_action_count_conserved"] is True
    interaction = document["interactions"][0]
    assert interaction["trigger"] == "hover"
    assert interaction["action"] == "scroll_to"
    metadata = interaction["parameters"]["figma_reaction"]
    assert metadata["raw_reaction"] == raw_reaction
    assert metadata["raw_trigger"] == raw_reaction["trigger"]
    assert metadata["raw_action"] == raw_reaction["actions"][0]
    assert (
        document["linked_targets"]["figma"]["reaction_recovery"] == []
    )
    assert normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    ) == document

    compatibility = inspect_figma_compatibility(document)
    assert compatibility["counts"]["blocked"] == 0
    package = export_figma_plugin_package(document, tmp_path / "native-reaction")
    exchange = json.loads(
        Path(package["exchange_path"]).read_text(encoding="utf-8")
    )
    assert normalize_ui_document(exchange["document"]) == document
    code = (Path(package["output_dir"]) / "code.js").read_text(
        encoding="utf-8"
    )
    assert "hover:'ON_HOVER'" in code
    assert "scroll_to:'SCROLL_TO'" in code
    assert "const reactionsBySource=new Map()" in code
    assert "await source.setReactionsAsync(reactions)" in code
    assert "Reaction export failed for ${sourceId}" in code

    umg = painter_ui_to_umg_document(document)
    assert umg["Interactions"][0]["Trigger"] == "hovered"
    assert umg["PainterSource"]["FigmaReactionRecovery"] == []
    preflight = preflight_painter_umg(document)
    assert any(
        "figma_scroll_to_requires_umg_scrollbox_binding"
        in blocker["reasons"]
        for blocker in preflight["blockers"]
    )


def test_figma_reaction_failures_are_lossless_recovery_and_explicit_blockers(
    tmp_path: Path,
) -> None:
    import pytest

    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        PainterUIFigmaError,
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    component = frame["children"][0]
    component["reactions"] = [
        {
            "trigger": {"type": "ON_HOVER"},
            "actions": [
                {
                    "type": "NODE",
                    "destinationId": "3:1",
                    "navigation": "SCROLL_TO",
                },
                {"type": "URL", "url": "https://example.com/help"},
            ],
        },
        {
            "trigger": {"type": "ON_MEDIA_END"},
            "actions": [
                {
                    "type": "NODE",
                    "destinationId": "3:1",
                    "navigation": "NAVIGATE",
                }
            ],
        },
        {
            "trigger": {"type": "ON_CLICK"},
            "actions": [
                {
                    "type": "NODE",
                    "destinationId": None,
                    "navigation": "SCROLL_TO",
                }
            ],
        },
        {"trigger": {"type": "ON_CLICK"}, "actions": [None]},
        {"trigger": {"type": "ON_CLICK"}, "actions": []},
    ]
    frame["interactions"] = [
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
    ]

    document, report = import_figma_payload(
        payload,
        source="blocked-reactions.json",
    )
    recovery = document["linked_targets"]["figma"]["reaction_recovery"]

    assert report["source_reaction_count"] == 6
    assert report["source_reaction_action_count"] == 6
    assert report["native_reaction_count"] == 0
    assert report["native_reaction_action_count"] == 1
    assert report["blocked_recovery_reaction_count"] == 6
    assert report["blocked_recovery_action_count"] == 5
    assert report["reaction_count_conserved"] is True
    assert report["reaction_action_count_conserved"] is True
    assert len(document["interactions"]) == 1
    assert document["interactions"][0]["action"] == "scroll_to"
    assert len(recovery) == 6
    partial = next(row for row in recovery if row["status"] == "partial")
    artboard_recovery = next(
        row for row in recovery if row["source_kind"] == "artboard"
    )
    assert partial["raw_reaction"] == component["reactions"][0]
    assert artboard_recovery["raw_reaction"] == frame["interactions"][0]
    reasons = {
        reason
        for row in recovery
        for reason in row["reasons"]
    }
    assert {
        "figma_prototype_url_action_requires_runtime_policy",
        "figma_reaction_trigger_unsupported",
        "figma_scroll_to_missing_destination",
        "figma_reaction_action_malformed",
        "figma_reaction_has_no_actions",
        "figma_reaction_artboard_source_unsupported",
    } <= reasons
    assert normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    ) == document

    compatibility = inspect_figma_compatibility(document)
    blocked_ids = {
        row["id"]
        for row in compatibility["objects"]
        if row["status"] == "blocked"
    }
    assert {row["id"] for row in recovery} <= blocked_ids
    with pytest.raises(PainterUIFigmaError, match="blocked"):
        export_figma_plugin_package(document, tmp_path / "blocked-reactions")

    umg = painter_ui_to_umg_document(document)
    assert umg["PainterSource"]["FigmaReactionRecovery"] == recovery
    preflight = preflight_painter_umg(document)
    recovery_blockers = [
        row
        for row in preflight["blockers"]
        if row["name"] == "Figma reaction recovery"
    ]
    assert len(recovery_blockers) == 6
    umg_reasons = {
        reason
        for row in recovery_blockers
        for reason in row["reasons"]
    }
    assert reasons <= umg_reasons


def test_figma_top_level_instance_screen_preserves_descendant_reactions() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    page = payload["document"]["children"][0]
    page["children"].append(
        {
            "id": "4:1",
            "type": "INSTANCE",
            "name": "Instance Screen",
            "componentId": "missing:screen",
            "absoluteBoundingBox": {
                "x": 600,
                "y": 200,
                "width": 390,
                "height": 844,
            },
            "children": [
                {
                    "id": "I4:1;4:2",
                    "type": "FRAME",
                    "name": "Inherited CTA",
                    "absoluteBoundingBox": {
                        "x": 624,
                        "y": 700,
                        "width": 160,
                        "height": 52,
                    },
                    "componentPropertyReferences": {
                        "visible": "Visible#4:9"
                    },
                    "reactions": [
                        {
                            "trigger": {"type": "ON_HOVER"},
                            "actions": [
                                {
                                    "type": "NODE",
                                    "destinationId": "I4:1;4:3",
                                    "navigation": "SCROLL_TO",
                                }
                            ],
                        }
                    ],
                    "children": [],
                },
                {
                    "id": "I4:1;4:3",
                    "type": "RECTANGLE",
                    "name": "Scroll Target",
                    "absoluteBoundingBox": {
                        "x": 624,
                        "y": 300,
                        "width": 160,
                        "height": 52,
                    },
                },
            ],
        }
    )

    document, report = import_figma_payload(
        payload,
        source="top-level-instance-screen.json",
    )

    assert any(row["name"] == "Instance Screen" for row in document["artboards"])
    source = next(
        row for row in document["objects"] if row["name"] == "Inherited CTA"
    )
    assert source["component_property_bindings"] == {}
    inherited = next(
        row
        for row in document["interactions"]
        if row["parameters"]
        .get("figma_reaction", {})
        .get("source_figma_node_id")
        == "I4:1;4:2"
    )
    assert inherited["trigger"] == "hover"
    assert inherited["action"] == "scroll_to"
    assert report["source_reaction_count"] == 2
    assert report["native_reaction_count"] == 2
    assert report["blocked_recovery_reaction_count"] == 0
    assert report["reaction_count_conserved"] is True


def test_figma_import_reports_flattened_artboard_layout_and_reactions() -> None:
    from app.painter_ui_figma import import_figma_payload

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    frame["layoutMode"] = "VERTICAL"
    frame["interactions"] = [
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
    ]

    _document, report = import_figma_payload(payload, source="artboard-layout.json")

    assert any(
        "artboard_auto_layout_flattened_to_absolute_geometry" in warning
        for warning in report["warnings"]
    )
    assert any(
        "artboard_source_unsupported" in warning for warning in report["warnings"]
    )


def _instance_override_payload() -> dict:
    """A component whose instance authors a different label than the default."""
    return {
        "id": "20:1",
        "type": "FRAME",
        "name": "Screen",
        "absoluteBoundingBox": {"x": 0, "y": 0, "width": 400, "height": 300},
        "children": [
            {
                "id": "20:2",
                "type": "COMPONENT",
                "name": "CTA",
                "absoluteBoundingBox": {
                    "x": 0,
                    "y": 0,
                    "width": 200,
                    "height": 60,
                },
                "children": [
                    {
                        "id": "20:3",
                        "type": "TEXT",
                        "name": "Label",
                        "characters": "Get started",
                        "absoluteBoundingBox": {
                            "x": 10,
                            "y": 10,
                            "width": 180,
                            "height": 40,
                        },
                    }
                ],
            },
            {
                "id": "20:10",
                "type": "INSTANCE",
                "name": "CTA",
                "componentId": "20:2",
                "absoluteBoundingBox": {
                    "x": 0,
                    "y": 120,
                    "width": 200,
                    "height": 60,
                },
                "children": [
                    {
                        "id": "I20:10;20:3",
                        "type": "TEXT",
                        "name": "Label",
                        "characters": "Start",
                        "absoluteBoundingBox": {
                            "x": 10,
                            "y": 130,
                            "width": 180,
                            "height": 40,
                        },
                    }
                ],
            },
        ],
    }


def test_figma_expanded_instance_descendants_link_to_their_definition_node():
    from app.painter_ui_figma import import_figma_payload

    document, report = import_figma_payload(_instance_override_payload())
    by_id = {row["id"]: row for row in document["objects"]}
    descendant = next(
        row
        for row in document["objects"]
        if str((row.get("content") or {}).get("figma_node_id") or "")
        == "I20:10;20:3"
    )
    definition = next(
        row
        for row in document["objects"]
        if str((row.get("content") or {}).get("figma_node_id") or "") == "20:3"
    )

    # Without this link nothing downstream can tell the authored "Start" from
    # the component default, so the definition gets replayed instead.
    assert descendant["component_source_object_id"] == definition["id"]
    assert descendant["content"]["text"] == "Start"
    assert definition["content"]["text"] == "Get started"
    assert not [
        warning
        for warning in report["warnings"]
        if "instance_subtree_shape_differs" in warning
    ]
    assert by_id[descendant["id"]] is descendant


def test_umg_instance_override_is_derived_from_the_expanded_descendant():
    import json

    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    document, _ = import_figma_payload(_instance_override_payload())
    definition = next(
        row
        for row in document["objects"]
        if str((row.get("content") or {}).get("figma_node_id") or "") == "20:3"
    )

    umg = painter_ui_to_umg_document(document)
    instance = next(
        row
        for row in umg["ComponentInstances"]
        if str(row.get("ComponentId") or "")
    )
    overrides = json.loads(str(instance["ResolvedOverridesJson"]))

    assert overrides == {definition["id"]: {"content.text": "Start"}}


def test_umg_projection_shows_the_authored_instance_label_not_the_default():
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_umg_simulator import project_painter_ui_umg_widgets

    document, _ = import_figma_payload(_instance_override_payload())
    artboard_id = document["artboards"][0]["id"]

    projection = project_painter_ui_umg_widgets(
        document,
        artboard_id=artboard_id,
    )

    labels = sorted(
        str((row.get("content") or {}).get("text") or "")
        for row in projection["document"]["objects"]
        if str((row.get("content") or {}).get("text") or "")
    )
    # The component definition also sits on this artboard, so one "Get started"
    # is its own render. The instance must contribute "Start" -- before the
    # override was derived it replayed the default and both read "Get started".
    # A button whose label silently reverts is worse than a shape that renders
    # imprecisely: it exports wrong information.
    assert labels.count("Start") == 1
    assert labels.count("Get started") == 1
