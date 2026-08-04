from __future__ import annotations

import pytest


def _document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600, name="Advanced")
    document, mask = add_ui_object(
        document,
        kind="ellipse",
        name="Mask",
        x=40,
        y=40,
        width=160,
        height=160,
    )
    document, first = add_ui_object(
        document,
        kind="rectangle",
        name="First",
        x=40,
        y=40,
        width=220,
        height=120,
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        name="Second",
        x=100,
        y=80,
        width=220,
        height=120,
    )
    document, text = add_ui_object(
        document,
        kind="text",
        name="Title",
        x=40,
        y=240,
        width=300,
        height=80,
        content={"text": "Tiger Studio"},
    )
    return document, mask, first, second, text


def test_ui_mask_contract_create_update_reorder_remove() -> None:
    from app.painter_ui_document import validate_ui_document
    from app.painter_ui_masks import (
        create_ui_mask,
        inspect_ui_mask,
        remove_ui_mask,
        reorder_ui_mask_targets,
        update_ui_mask,
    )

    document, mask, first, second, _text = _document()
    document, row = create_ui_mask(
        document,
        mask["id"],
        target_ids=[first["id"], second["id"]],
    )
    assert row["mask"]["enabled"]
    assert inspect_ui_mask(document, mask["id"])["target_ids"] == [
        first["id"],
        second["id"],
    ]
    document, row = update_ui_mask(
        document,
        mask["id"],
        {"inverted": True, "outline": True},
    )
    assert row["mask"]["inverted"] and row["mask"]["outline"]
    document, row = reorder_ui_mask_targets(
        document,
        mask["id"],
        [second["id"], first["id"]],
    )
    assert row["mask"]["target_ids"][0] == second["id"]
    document = remove_ui_mask(document, mask["id"])
    assert not inspect_ui_mask(document, mask["id"])["enabled"]
    assert validate_ui_document(document)["ok"]


def test_advanced_appearance_stacks_corners_and_blend() -> None:
    from app.painter_ui_advanced_appearance import (
        inspect_ui_advanced_appearance,
        mutate_ui_paint,
        set_ui_corner_geometry,
        set_ui_object_blend_mode,
    )

    document, _mask, first, _second, _text = _document()
    document, _ = set_ui_object_blend_mode(document, first["id"], "multiply")
    document, _ = mutate_ui_paint(
        document,
        first["id"],
        stack="fill",
        operation="add",
        paint={"type": "solid", "color": "#FF0000FF"},
        index=0,
    )
    document, _ = mutate_ui_paint(
        document,
        first["id"],
        stack="stroke",
        operation="add",
        paint={
            "type": "solid",
            "color": "#00FFFFFF",
            "width": 4,
            "align": "inside",
        },
    )
    document, _ = set_ui_corner_geometry(
        document,
        first["id"],
        corner_radii={
            "top_left": 2,
            "top_right": 8,
            "bottom_right": 16,
            "bottom_left": 24,
        },
        stroke_align="inside",
    )
    report = inspect_ui_advanced_appearance(document, first["id"])
    assert report["blend_mode"] == "multiply"
    assert report["fills"][0]["color"] == "#FF0000FF"
    assert report["strokes"][0]["align"] == "inside"
    assert report["corner_radii"]["bottom_left"] == 24


def test_mixed_text_ranges_and_remote_component_recovery() -> None:
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_remote_components import (
        inspect_remote_components,
        localize_remote_component,
        relink_remote_component,
    )
    from app.painter_ui_text_ranges import (
        inspect_ui_text_ranges,
        remove_ui_text_range_style,
        set_ui_text_range_style,
    )

    document, _mask, first, _second, text = _document()
    document, _ = set_ui_text_range_style(
        document,
        text["id"],
        0,
        5,
        {"font_weight": 700, "color": "#FFAA00FF"},
    )
    report = inspect_ui_text_ranges(document, text["id"])
    assert report["ranges"][0]["end"] == 5
    document = remove_ui_text_range_style(document, text["id"], 0, 5)
    assert not inspect_ui_text_ranges(document, text["id"])["ranges"]

    document, first = update_ui_object(
        document,
        first["id"],
        {
            "content": {
                **first["content"],
                "remote_component": {
                    "component_key": "remote:key",
                    "component_name": "Remote Card",
                    "status": "missing",
                },
            }
        },
    )
    assert inspect_remote_components(document)["missing_count"] == 1
    document, row = relink_remote_component(
        document,
        first["id"],
        component_key="remote:new",
        source_file_key="file-key",
    )
    assert row["content"]["remote_component"]["status"] == "linked"
    document, row = localize_remote_component(
        document,
        first["id"],
        name="Local Card",
    )
    assert row["component_role"] == "definition"


def test_boolean_vectors_and_sections_persist_with_stable_ids() -> None:
    from app.painter_ui_boolean import (
        inspect_ui_boolean,
        release_ui_boolean,
        set_ui_boolean,
    )
    from app.painter_ui_document import normalize_ui_document, validate_ui_document
    from app.painter_ui_sections import (
        create_ui_section,
        inspect_ui_sections,
        remove_ui_section,
        update_ui_section,
    )

    document, mask, first, second, _text = _document()
    document, row = set_ui_boolean(
        document,
        mask["id"],
        "exclude",
        [first["id"], second["id"]],
    )
    assert row["content"]["boolean"]["operation"] == "exclude"
    assert inspect_ui_boolean(document, mask["id"])["enabled"]
    document = release_ui_boolean(document, mask["id"])
    assert not inspect_ui_boolean(document, mask["id"])["enabled"]

    document, section = create_ui_section(
        document,
        {
            "name": "Dashboard",
            "object_ids": [first["id"], second["id"]],
        },
    )
    stable_id = section["id"]
    document, section = update_ui_section(
        document,
        stable_id,
        {"name": "Dashboard Updated", "collapsed": True},
    )
    assert section["id"] == stable_id
    assert inspect_ui_sections(document)["sections"][0]["collapsed"]
    roundtrip = normalize_ui_document(document)
    assert roundtrip["sections"][0]["id"] == stable_id
    assert validate_ui_document(roundtrip)["ok"]
    document = remove_ui_section(roundtrip, stable_id)
    assert not inspect_ui_sections(document)["sections"]


def test_advanced_action_families_are_registered() -> None:
    from app.actions.registry import ActionRegistry

    action_ids = {row["id"] for row in ActionRegistry().list_actions()}
    assert {
        "paint.ui.mask.create",
        "paint.ui.mask.update",
        "paint.ui.mask.remove",
        "paint.ui.mask.reorder",
        "paint.ui.appearance.blend.set",
        "paint.ui.appearance.paint.add",
        "paint.ui.appearance.corner.set",
        "paint.ui.appearance.stroke.set",
        "paint.ui.text.range.style.set",
        "paint.ui.component.remote.relink",
        "paint.ui.vector.boolean.compose",
        "paint.ui.vector.boolean.set",
        "paint.ui.section.create",
    } <= action_ids


def test_invalid_mask_and_boolean_references_are_rejected() -> None:
    from app.painter_ui_boolean import set_ui_boolean
    from app.painter_ui_document import PainterUIDocumentError
    from app.painter_ui_masks import create_ui_mask

    document, mask, first, _second, _text = _document()
    with pytest.raises(PainterUIDocumentError):
        create_ui_mask(document, mask["id"], target_ids=["missing"])
    with pytest.raises(PainterUIDocumentError):
        set_ui_boolean(document, mask["id"], "union", [first["id"]])


def test_figma_advanced_features_import_and_export(tmp_path) -> None:
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
    )

    payload = {
        "name": "Advanced Figma",
        "comments": [
            {
                "message": "Review this mask",
                "user": {"handle": "Designer"},
                "client_meta": {"node_id": "2:1", "x": 0.25, "y": 0.75},
            }
        ],
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "1:0",
                    "type": "CANVAS",
                    "name": "Page",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "SECTION",
                            "name": "Dashboard",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 800,
                                "height": 600,
                            },
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "ELLIPSE",
                                    "name": "Mask",
                                    "isMask": True,
                                    "absoluteBoundingBox": {
                                        "x": 20,
                                        "y": 20,
                                        "width": 160,
                                        "height": 160,
                                    },
                                    "fills": [
                                        {
                                            "type": "SOLID",
                                            "color": {
                                                "r": 1,
                                                "g": 1,
                                                "b": 1,
                                            },
                                        },
                                        {
                                            "type": "SOLID",
                                            "opacity": 0.5,
                                            "color": {
                                                "r": 1,
                                                "g": 0,
                                                "b": 0,
                                            },
                                        },
                                    ],
                                    "blendMode": "MULTIPLY",
                                },
                                {
                                    "id": "2:2",
                                    "type": "TEXT",
                                    "name": "Title",
                                    "characters": "Tiger UI",
                                    "characterStyleOverrides": [
                                        1, 1, 1, 1, 1, 0, 0, 0
                                    ],
                                    "styleOverrideTable": {
                                        "1": {
                                            "fontWeight": 700,
                                            "fills": [
                                                {
                                                    "type": "SOLID",
                                                    "color": {
                                                        "r": 1,
                                                        "g": 0.5,
                                                        "b": 0,
                                                    },
                                                }
                                            ],
                                        }
                                    },
                                    "style": {"fontFamily": "Inter", "fontSize": 24},
                                    "absoluteBoundingBox": {
                                        "x": 40,
                                        "y": 40,
                                        "width": 240,
                                        "height": 60,
                                    },
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }
    document, report = import_figma_payload(
        payload,
        source="AbCdEf123456",
    )
    mask = next(row for row in document["objects"] if row["name"] == "Mask")
    text = next(row for row in document["objects"] if row["name"] == "Title")
    assert mask["mask"]["enabled"]
    assert mask["mask"]["target_ids"] == [text["id"]]
    assert len(mask["style"]["fills"]) == 2
    assert mask["style"]["blend_mode"] == "multiply"
    assert text["content"]["text_ranges"][0]["style"]["font_weight"] == 700
    assert report["section_count"] == 1
    assert report["comment_count"] == 1

    package = export_figma_plugin_package(document, tmp_path)
    code = (tmp_path / "TigerStudioFigmaExport" / "code.js").read_text(
        encoding="utf-8"
    )
    assert package["ok"]
    assert "node.isMask" in code
    assert "setRangeFontSize" in code
    assert "figma.createSection" in code
    assert "figma.union" in code


def test_umg_preflight_explicitly_blocks_unimplemented_advanced_features() -> None:
    from app.painter_ui_masks import create_ui_mask
    from app.painter_ui_text_ranges import set_ui_text_range_style
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document, mask, first, _second, text = _document()
    document, _ = create_ui_mask(
        document,
        mask["id"],
        target_ids=[first["id"]],
    )
    document, _ = set_ui_text_range_style(
        document,
        text["id"],
        0,
        5,
        {"font_weight": 700},
    )
    report = preflight_painter_umg(document)
    assert not report["ok"]
    reasons = {
        reason
        for blocker in report["blockers"]
        for reason in blocker["reasons"]
    }
    assert "painter_ui_mask_requires_umg_material_or_bake" in reasons
    assert "mixed_text_ranges_require_rich_text_conversion" in reasons


def test_m1b7_nested_figma_boolean_import_hierarchy_and_export_order(
    tmp_path,
) -> None:
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
    )

    def box(x, y, width, height):
        return {"x": x, "y": y, "width": width, "height": height}

    payload = {
        "name": "Nested Boolean",
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "1:0",
                    "type": "CANVAS",
                    "name": "Page 1",
                    "children": [
                        {
                            "id": "1:1",
                            "type": "FRAME",
                            "name": "Canvas",
                            "absoluteBoundingBox": box(0, 0, 800, 600),
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "BOOLEAN_OPERATION",
                                    "name": "Outer",
                                    "booleanOperation": "SUBTRACT",
                                    "absoluteBoundingBox": box(100, 100, 240, 180),
                                    "children": [
                                        {
                                            "id": "2:2",
                                            "type": "BOOLEAN_OPERATION",
                                            "name": "Inner",
                                            "booleanOperation": "UNION",
                                            "absoluteBoundingBox": box(100, 100, 200, 180),
                                            "children": [
                                                {
                                                    "id": "2:3",
                                                    "type": "RECTANGLE",
                                                    "name": "Base",
                                                    "absoluteBoundingBox": box(100, 100, 160, 160),
                                                },
                                                {
                                                    "id": "2:4",
                                                    "type": "ELLIPSE",
                                                    "name": "Lobe",
                                                    "absoluteBoundingBox": box(180, 100, 120, 160),
                                                },
                                            ],
                                        },
                                        {
                                            "id": "2:5",
                                            "type": "ELLIPSE",
                                            "name": "Cut",
                                            "absoluteBoundingBox": box(250, 140, 90, 90),
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

    document, report = import_figma_payload(payload, source="AbCdEf123456")
    assert report["ok"] is True
    rows = {row["name"]: row for row in document["objects"]}
    outer = rows["Outer"]
    inner = rows["Inner"]
    assert outer["content"]["boolean"] == {
        "enabled": True,
        "group": True,
        "operation": "subtract",
        "operand_ids": [inner["id"], rows["Cut"]["id"]],
    }
    assert inner["content"]["boolean"]["operation"] == "union"
    assert inner["content"]["boolean"]["operand_ids"] == [
        rows["Base"]["id"],
        rows["Lobe"]["id"],
    ]
    assert inner["parent_id"] == outer["id"]
    assert rows["Base"]["parent_id"] == inner["id"]
    assert rows["Lobe"]["parent_id"] == inner["id"]
    assert rows["Cut"]["parent_id"] == outer["id"]

    package = export_figma_plugin_package(document, tmp_path)
    code = (tmp_path / "TigerStudioFigmaExport" / "code.js").read_text(
        encoding="utf-8"
    )
    assert package["ok"]
    assert "const booleanDepth=" in code
    assert "Boolean cycle includes" in code
    assert "booleanRows.sort" in code
    assert "result.setSharedPluginData('tigerstudio','stable_id',row.id)" in code


def test_m1b7_umg_preflight_keeps_boolean_explicitly_blocked() -> None:
    from app.painter_ui_boolean import compose_ui_boolean
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    document, _mask, first, second, _text = _document()
    document, group = compose_ui_boolean(
        document,
        "exclude",
        [first["id"], second["id"]],
    )

    report = preflight_painter_umg(document)
    blocker = next(
        row for row in report["blockers"] if row["object_id"] == group["id"]
    )
    umg_document = painter_ui_to_umg_document(document)
    layer = next(row for row in umg_document["Layers"] if row["Id"] == group["id"])
    assert report["ok"] is False
    assert blocker["reasons"] == [
        "painter_ui_boolean_requires_deterministic_bake"
    ]
    assert layer["Disposition"] == "Blocked"
    assert layer["BlockReasons"] == blocker["reasons"]
    assert layer["PayloadJson"]


def test_object_removal_cleans_mask_boolean_and_section_references() -> None:
    from app.painter_ui_boolean import set_ui_boolean
    from app.painter_ui_document import remove_ui_object, validate_ui_document
    from app.painter_ui_masks import create_ui_mask
    from app.painter_ui_sections import create_ui_section

    document, mask, first, second, _text = _document()
    document, _ = create_ui_mask(
        document,
        mask["id"],
        target_ids=[first["id"], second["id"]],
    )
    document, _ = set_ui_boolean(
        document,
        mask["id"],
        "union",
        [first["id"], second["id"]],
    )
    document, _ = create_ui_section(
        document,
        {"name": "Shapes", "object_ids": [first["id"], second["id"]]},
    )
    document, _cleanup = remove_ui_object(document, first["id"])
    mask_row = next(row for row in document["objects"] if row["id"] == mask["id"])
    assert mask_row["mask"]["target_ids"] == [second["id"]]
    assert not mask_row["content"]["boolean"]["enabled"]
    assert document["sections"][0]["object_ids"] == [second["id"]]
    assert validate_ui_document(document)["ok"]
