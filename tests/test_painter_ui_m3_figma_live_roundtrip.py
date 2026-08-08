from __future__ import annotations

import json
from pathlib import Path


def test_live_roundtrip_package_serializes_shared_stable_ids(tmp_path: Path) -> None:
    from tools.qa_painter_ui_m3_figma_live_roundtrip import prepare

    report = prepare(tmp_path)
    code = (Path(report["manifest_path"]).parent / "code.js").read_text(
        encoding="utf-8"
    )

    assert report["phase"] == "prepared"
    assert report["figma_assigned_plugin_id"] is False
    assert report["live_execution_ready"] is False
    assert "getSharedPluginData('tigerstudio',key)" in code
    assert "component_family_id" in code
    assert "pendingSlotRows" in code
    assert "component_source_object_id" in code
    assert "parentRow?(Number(parentRow.x)||0):0" in code
    assert "Tiger Studio live roundtrip JSON copied" in code


def test_prepare_accepts_figma_assigned_plugin_id(tmp_path: Path) -> None:
    from tools.qa_painter_ui_m3_figma_live_roundtrip import prepare

    report = prepare(tmp_path, plugin_id="1234567890123456789")
    manifest = json.loads(Path(report["manifest_path"]).read_text(encoding="utf-8"))

    assert manifest["id"] == "1234567890123456789"
    assert report["figma_assigned_plugin_id"] is True
    assert report["live_execution_ready"] is True


def test_live_roundtrip_consume_requires_all_source_stable_ids(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_m3_figma_live_roundtrip import consume, prepare

    prepared = prepare(tmp_path)
    exchange = json.loads(Path(prepared["exchange_path"]).read_text(encoding="utf-8"))
    document = exchange["document"]
    object_rows = document["objects"]
    component_by_id = {row["id"]: row for row in document["components"]}
    nodes: list[dict] = []
    by_id: dict[str, dict] = {}

    for row in object_rows:
        role = row.get("component_role")
        node_type = (
            "SLOT"
            if row.get("component_slot_property")
            else "COMPONENT"
            if role == "definition" and row.get("component_source_object_id") == row["id"]
            else "INSTANCE"
            if role == "instance"
            else "RECTANGLE"
        )
        current = {
            "id": f"figma:{len(nodes) + 10}",
            "name": row["name"],
            "type": node_type,
            "absoluteBoundingBox": {
                "x": row["x"], "y": row["y"],
                "width": row["width"], "height": row["height"],
            },
            "sharedPluginData": {"tigerstudio": {"stable_id": row["id"]}},
            "children": [],
        }
        if row.get("component_id"):
            current["sharedPluginData"]["tigerstudio"]["component_id"] = row[
                "component_id"
            ]
        if row.get("component_source_object_id"):
            current["sharedPluginData"]["tigerstudio"][
                "component_source_object_id"
            ] = row["component_source_object_id"]
        if node_type == "INSTANCE":
            current["componentId"] = "figma:component"
        if node_type == "COMPONENT":
            component = component_by_id[row["component_id"]]
            if "Actions" in component.get("property_definitions", {}):
                current["componentPropertyDefinitions"] = {
                    "Actions#1:9": {"type": "SLOT", "defaultValue": "figma:slot"}
                }
        nodes.append(current)
        by_id[row["id"]] = current

    for row in object_rows:
        parent = by_id.get(row.get("parent_id", ""))
        if parent:
            parent["children"].append(by_id[row["id"]])
    slot = next(row for row in object_rows if row.get("component_slot_property"))
    by_id[slot["id"]]["id"] = "figma:slot"
    roots = [by_id[row["id"]] for row in object_rows if not row.get("parent_id")]
    snapshot = tmp_path / "figma_live_snapshot.json"
    snapshot.write_text(
        json.dumps({
            "name": "Live snapshot",
            "document": {"id": "0:0", "type": "DOCUMENT", "children": [{
                "id": "0:1", "type": "CANVAS", "name": "Page 1", "children": [{
                    "id": "1:1", "type": "FRAME", "name": "Board",
                    "absoluteBoundingBox": {"x": 0, "y": 0, "width": 900, "height": 700},
                    "children": roots,
                }],
            }]},
        }),
        encoding="utf-8",
    )

    report = consume(tmp_path, snapshot)

    assert report["passed"] is True
    assert report["source_stable_id_count"] == len(object_rows)
    assert report["preserved_stable_id_count"] == len(object_rows)
