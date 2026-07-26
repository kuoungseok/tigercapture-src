from __future__ import annotations

import json
from pathlib import Path


def test_general_ui_document_crud_validation_and_handoff(tmp_path: Path) -> None:
    from app.painter_ui_delivery import (
        list_ui_delivery_profiles,
        package_design_handoff,
        preflight_ui_delivery,
    )
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
        remove_ui_object,
        update_ui_object,
        validate_ui_document,
    )

    document = create_ui_document(390, 844, name="Phone Home")
    assert document["schema"] == "tigerstudio.painter.ui.v1"
    assert "UCanvasPanel" not in json.dumps(document)
    document, desktop = add_ui_artboard(
        document,
        name="Desktop Home",
        width=1440,
        height=1024,
        breakpoint="desktop",
    )
    document, card = add_ui_object(
        document,
        kind="frame",
        name="Product Card",
        artboard_id=desktop["id"],
        x=80,
        y=120,
        width=360,
        height=420,
        style={"fill": "#18202B"},
    )
    document, button = add_ui_object(
        document,
        kind="button",
        name="Buy Button",
        artboard_id=desktop["id"],
        parent_id=card["id"],
        x=24,
        y=332,
        width=312,
        height=56,
        style={"fill": "#4D79FF"},
        content={"text": "Buy now"},
    )
    document, button = update_ui_object(
        document,
        button["id"],
        {"width": 320, "accessibility": {"role": "button", "label": "Buy now"}},
    )
    assert button["width"] == 320.0
    validation = validate_ui_document(document)
    assert validation["ok"] is True
    assert validation["artboard_count"] == 2
    assert validation["object_count"] == 2
    assert document["revision"] == 4

    profiles = list_ui_delivery_profiles()
    assert {row["target"] for row in profiles["profiles"]} == {
        "asset_export",
        "design_handoff",
        "review_prototype",
        "unreal_umg",
    }
    preflight = preflight_ui_delivery(document, "design_handoff")
    assert preflight["ok"] is True
    assert preflight["counts"]["native"] == 2

    report = package_design_handoff(document, tmp_path / "handoff")
    assert report["ok"] is True
    assert {row["kind"] for row in report["artifacts"]} == {
        "design_document",
        "tokens",
        "components",
        "interactions",
        "manifest",
    }
    manifest = json.loads(
        (tmp_path / "handoff" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["revision"] == 4
    assert manifest["object_count"] == 2

    document, removed = remove_ui_object(document, card["id"])
    assert set(removed["removed_object_ids"]) == {button["id"], card["id"]}
    assert document["objects"] == []
    assert document["selection"]["object_id"] == ""


def test_general_ui_document_rejects_invalid_parent_updates() -> None:
    import pytest

    from app.painter_ui_document import (
        PainterUIDocumentError,
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document()
    document, parent = add_ui_object(document, kind="frame", name="Parent")
    document, child = add_ui_object(
        document,
        kind="text",
        name="Child",
        parent_id=parent["id"],
    )
    with pytest.raises(PainterUIDocumentError, match="Invalid UI object update"):
        update_ui_object(document, parent["id"], {"parent_id": child["id"]})


def test_general_ui_document_switches_artboards_and_clears_foreign_selection() -> None:
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_object,
        create_ui_document,
        set_active_ui_artboard,
    )

    document = create_ui_document(390, 844, name="Phone")
    phone_id = document["active_artboard_id"]
    document, phone_button = add_ui_object(
        document,
        kind="button",
        artboard_id=phone_id,
    )
    document, desktop = add_ui_artboard(
        document,
        name="Desktop",
        width=1440,
        height=900,
    )
    assert document["selection"]["object_id"] == ""
    document = set_active_ui_artboard(document, phone_id)
    assert document["active_artboard_id"] == phone_id
    assert document["selection"]["object_id"] == ""
    document = set_active_ui_artboard(document, desktop["id"])
    assert document["active_artboard_id"] == desktop["id"]
    assert phone_button["id"] in {row["id"] for row in document["objects"]}


def test_general_ui_document_multi_selection_modes_are_stable() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        normalize_ui_document,
        select_ui_object,
        select_ui_objects,
    )

    document = create_ui_document(800, 600)
    rows = []
    for index in range(3):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            x=40 + index * 120,
            y=80,
            width=80,
            height=60,
        )
        rows.append(row)

    document = select_ui_object(document, rows[0]["id"])
    document = select_ui_object(document, rows[1]["id"], mode="add")
    assert document["selection"] == {
        "object_id": rows[1]["id"],
        "object_ids": [rows[0]["id"], rows[1]["id"]],
    }
    document = select_ui_object(document, rows[0]["id"], mode="toggle")
    assert document["selection"]["object_ids"] == [rows[1]["id"]]

    document = select_ui_objects(
        document,
        [rows[2]["id"], rows[0]["id"]],
        primary_object_id=rows[2]["id"],
    )
    restored = normalize_ui_document(document)
    assert restored["selection"] == {
        "object_id": rows[2]["id"],
        "object_ids": [rows[2]["id"], rows[0]["id"]],
    }


def test_general_ui_document_group_ungroup_and_reorder() -> None:
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        group_ui_objects,
        reorder_ui_objects,
        ungroup_ui_object,
        validate_ui_document,
    )

    document = create_ui_document(800, 600)
    rows = []
    for index in range(3):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            x=60 + index * 140,
            y=100,
            width=100,
            height=80,
        )
        rows.append(row)
    document = reorder_ui_objects(document, [rows[0]["id"]], "front")
    ordered = sorted(document["objects"], key=lambda row: row["z_index"])
    assert ordered[-1]["id"] == rows[0]["id"]

    document, group = group_ui_objects(
        document,
        [rows[0]["id"], rows[1]["id"]],
        name="Header Group",
    )
    children = {
        row["id"]: row
        for row in document["objects"]
        if row["id"] in {rows[0]["id"], rows[1]["id"]}
    }
    assert group["kind"] == "group"
    assert {row["parent_id"] for row in children.values()} == {group["id"]}
    assert document["selection"]["object_ids"] == [group["id"]]
    assert validate_ui_document(document)["ok"] is True

    document, result = ungroup_ui_object(document, group["id"])
    assert result["child_object_ids"] == [rows[0]["id"], rows[1]["id"]]
    assert group["id"] not in {row["id"] for row in document["objects"]}
    assert {
        row["parent_id"]
        for row in document["objects"]
        if row["id"] in result["child_object_ids"]
    } == {""}
    assert validate_ui_document(document)["ok"] is True


def test_general_ui_document_drag_hierarchy_move_and_cycle_guard() -> None:
    import pytest

    from app.painter_ui_document import (
        PainterUIDocumentError,
        add_ui_object,
        create_ui_document,
        group_ui_objects,
        move_ui_objects_in_hierarchy,
    )

    document = create_ui_document(800, 600)
    rows = []
    for index in range(3):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            x=50 + index * 140,
            y=90,
            width=100,
            height=70,
        )
        rows.append(row)
    document, group = group_ui_objects(
        document,
        [rows[0]["id"], rows[1]["id"]],
        name="Cards",
    )
    document = move_ui_objects_in_hierarchy(
        document,
        [rows[2]["id"]],
        target_parent_id=group["id"],
        placement="inside",
    )
    by_id = {row["id"]: row for row in document["objects"]}
    assert by_id[rows[2]["id"]]["parent_id"] == group["id"]
    assert document["selection"]["object_ids"] == [rows[2]["id"]]

    document = move_ui_objects_in_hierarchy(
        document,
        [rows[0]["id"]],
        placement="root",
    )
    by_id = {row["id"]: row for row in document["objects"]}
    assert by_id[rows[0]["id"]]["parent_id"] == ""

    document = move_ui_objects_in_hierarchy(
        document,
        [rows[0]["id"]],
        anchor_id=group["id"],
        placement="before",
    )
    ordered = sorted(document["objects"], key=lambda row: row["z_index"])
    ordered_ids = [row["id"] for row in ordered]
    assert ordered_ids.index(rows[0]["id"]) > ordered_ids.index(group["id"])
    document, nested_group = add_ui_object(
        document,
        kind="group",
        name="Nested Group",
        parent_id=group["id"],
        x=80,
        y=100,
        width=200,
        height=120,
    )
    with pytest.raises(PainterUIDocumentError, match="cycle"):
        move_ui_objects_in_hierarchy(
            document,
            [group["id"]],
            target_parent_id=nested_group["id"],
            placement="inside",
        )


def test_general_ui_document_preserves_unknown_kinds_for_explicit_preflight() -> None:
    from app.painter_ui_delivery import preflight_ui_delivery
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(
        {
            "artboards": [{"id": "artboard-1", "width": 800, "height": 600}],
            "objects": [
                {
                    "id": "future-widget-1",
                    "kind": "future_runtime_widget",
                    "artboard_id": "artboard-1",
                    "width": 100,
                    "height": 50,
                }
            ],
        }
    )
    assert document["objects"][0]["kind"] == "future_runtime_widget"
    validation = validate_ui_document(document)
    assert validation["ok"] is False
    assert validation["errors"] == [
        "unsupported_object_kind:future-widget-1:future_runtime_widget"
    ]
    preflight = preflight_ui_delivery(document, "design_handoff")
    assert preflight["ok"] is False
    assert preflight["objects"][0]["disposition"] == "blocked"
