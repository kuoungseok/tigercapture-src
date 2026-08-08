"""Schema-18 Painter component acceptance fixture and real-UE QA.

The fixture deliberately uses Painter's normal component authoring services:

* one primary reusable card definition with two visible screen instances;
* one separately counted badge dependency nested inside the card;
* static text and boolean bindings;
* one static variant tuple on the primary definition;
* one named Slot with instance-local static content.

The real-engine half is intentionally small.  It generates the document,
checks the main and reusable Widget Blueprint assets, reopens every asset, and
renders the screen with ``FWidgetRenderer``.  It does not open editor UI.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.painter_ui_components import (
    bind_ui_component_property,
    convert_ui_object_to_component,
    define_ui_component_property,
    define_ui_component_slot,
    insert_ui_object_into_component_slot,
    instantiate_ui_component,
    set_ui_instance_component_property,
)
from app.painter_ui_document import (
    add_ui_object,
    create_ui_document,
    update_ui_component,
    update_ui_object,
    validate_ui_document,
)
from app.painter_ui_umg_adapter import (
    generate_painter_umg,
    painter_ui_to_umg_document,
    preflight_painter_umg,
)
from app.unreal_umg_workflow import DEFAULT_UNREAL_ENGINE_ROOT
from tools.qa_painter_ui_unreal_umg import (
    _ensure_project,
    _render_generated_asset,
    _reopen_generated_asset,
)


COMPONENT_QA_SCHEMA = "tigerstudio.painter.ui.unreal_umg_component_qa.v1"
COMPONENT_DOCUMENT_SCHEMA_VERSION = 18
DEFAULT_WORKSPACE = (
    ROOT
    / "debugCapture"
    / "painter_ui_designer"
    / "unreal_umg_component_schema18"
)
BACKGROUND_ID = "__tiger_artboard_background"
PRIMARY_PROPERTY_DEFAULTS = {
    "Title": "Reusable card",
    "Show badge": True,
}
PRIMARY_VARIANT_VALUES = {"Tone": "Default"}
EXPECTED_PRIMARY_INSTANCE_TITLES = ("First card", "Second card")
COMPONENT_QA_DESTINATION_ROOT = "/Game/TigerStudio/GeneratedComponentQA"


def _component(
    document: Mapping[str, Any],
    component_id: str,
) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            row
            for row in document.get("components", [])
            if str(row.get("id") or "") == str(component_id)
        )
    )


def _object(
    document: Mapping[str, Any],
    object_id: str,
) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            row
            for row in document.get("objects", [])
            if str(row.get("id") or "") == str(object_id)
        )
    )


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_component_qa_fixture() -> dict[str, Any]:
    """Author one primary definition, two instances, and one dependency."""

    document = create_ui_document(960, 540, name="UMG Component QA")
    document["document_id"] = "painter-umg-component-schema18-qa"
    document["interactions"] = []
    document["artboards"][0]["background"] = "#0F172AFF"

    # Keep definitions on the active artboard but outside its visible bounds.
    # They remain valid authoring sources while the screen render contains only
    # the two reusable primary instances.
    document, badge_root = add_ui_object(
        document,
        kind="frame",
        name="Badge Definition",
        x=-760,
        y=32,
        width=92,
        height=32,
        style={"fill": "#16A34AFF", "radius": 0.0},
    )
    document, badge_label = add_ui_object(
        document,
        kind="text",
        name="Badge Label",
        parent_id=badge_root["id"],
        x=-748,
        y=38,
        width=68,
        height=20,
        style={"text_color": "#FFFFFFFF", "font_size": 14},
        content={"text": "NESTED"},
    )
    document, badge_component = convert_ui_object_to_component(
        document,
        root_object_id=badge_root["id"],
        name="Nested Badge",
    )
    # The generic component service creates an interactive state property by
    # default.  This static dependency intentionally exposes no properties.
    document, badge_component = update_ui_component(
        document,
        badge_component["id"],
        {"property_definitions": {}},
    )

    document, card_root = add_ui_object(
        document,
        kind="frame",
        name="Card Definition",
        x=-620,
        y=104,
        width=360,
        height=184,
        style={"fill": "#1E293BFF", "radius": 0.0},
    )
    document, title_source = add_ui_object(
        document,
        kind="text",
        name="Card Title",
        parent_id=card_root["id"],
        x=-596,
        y=124,
        width=232,
        height=32,
        style={"text_color": "#FFFFFFFF", "font_size": 22},
        content={"text": PRIMARY_PROPERTY_DEFAULTS["Title"]},
    )
    document, nested_source_result = instantiate_ui_component(
        document,
        component_id=badge_component["id"],
        x=-376,
        y=120,
    )
    document, nested_source = update_ui_object(
        document,
        nested_source_result["root_object_id"],
        {"parent_id": card_root["id"]},
    )
    document, slot_source = add_ui_object(
        document,
        kind="frame",
        name="Content Slot",
        parent_id=card_root["id"],
        x=-596,
        y=176,
        width=312,
        height=84,
        style={"fill": "#334155FF", "radius": 0.0},
    )
    document, slot_default = add_ui_object(
        document,
        kind="text",
        name="Default Slot Copy",
        parent_id=slot_source["id"],
        x=-580,
        y=196,
        width=272,
        height=28,
        style={"text_color": "#CBD5E1FF", "font_size": 16},
        content={"text": "Default static slot content"},
    )
    document, primary_component = convert_ui_object_to_component(
        document,
        root_object_id=card_root["id"],
        name="Reusable Card",
    )
    document, primary_component = update_ui_component(
        document,
        primary_component["id"],
        {
            "property_definitions": {},
            "metadata": {
                "variant_key": "Tone=Default",
                "variant_properties": copy.deepcopy(
                    PRIMARY_VARIANT_VALUES
                ),
            },
        },
    )
    document, _title_definition = define_ui_component_property(
        document,
        component_id=primary_component["id"],
        property_name="Title",
        definition={
            "type": "text",
            "default": PRIMARY_PROPERTY_DEFAULTS["Title"],
            "description": "Visible card heading",
        },
    )
    document, _show_badge_definition = define_ui_component_property(
        document,
        component_id=primary_component["id"],
        property_name="Show badge",
        definition={
            "type": "boolean",
            "default": PRIMARY_PROPERTY_DEFAULTS["Show badge"],
            "description": "Static nested badge visibility",
        },
    )
    document, _title_binding = bind_ui_component_property(
        document,
        component_id=primary_component["id"],
        source_object_id=title_source["id"],
        property_name="Title",
        target_path="content.text",
    )
    document, _badge_binding = bind_ui_component_property(
        document,
        component_id=primary_component["id"],
        source_object_id=nested_source["id"],
        property_name="Show badge",
        target_path="visible",
    )
    document, slot_definition = define_ui_component_slot(
        document,
        component_id=primary_component["id"],
        source_object_id=slot_source["id"],
        property_name="Content",
        description="Static card body",
        slot_settings={
            "display_empty_by_default": False,
            "max_children": 3,
        },
    )

    document, first_instance = instantiate_ui_component(
        document,
        component_id=primary_component["id"],
        x=80,
        y=96,
    )
    document, second_instance = instantiate_ui_component(
        document,
        component_id=primary_component["id"],
        x=520,
        y=96,
    )
    document, _first_properties = set_ui_instance_component_property(
        document,
        instance_root_id=first_instance["root_object_id"],
        property_name="Title",
        property_value=EXPECTED_PRIMARY_INSTANCE_TITLES[0],
    )
    document, _second_title = set_ui_instance_component_property(
        document,
        instance_root_id=second_instance["root_object_id"],
        property_name="Title",
        property_value=EXPECTED_PRIMARY_INSTANCE_TITLES[1],
    )
    document, _second_visibility = set_ui_instance_component_property(
        document,
        instance_root_id=second_instance["root_object_id"],
        property_name="Show badge",
        property_value=False,
    )
    document, custom_slot_content = add_ui_object(
        document,
        kind="text",
        name="Second Card Slot Override",
        x=544,
        y=184,
        width=272,
        height=28,
        style={"text_color": "#FBBF24FF", "font_size": 17},
        content={"text": "Instance-local static slot content"},
    )
    document, slot_report = insert_ui_object_into_component_slot(
        document,
        instance_root_id=second_instance["root_object_id"],
        property_name="Content",
        object_id=custom_slot_content["id"],
    )

    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise RuntimeError(
            "Component QA fixture is invalid: "
            + ", ".join(str(row) for row in validation["errors"])
        )
    primary_component = _component(document, primary_component["id"])
    badge_component = _component(document, badge_component["id"])
    return {
        "document": document,
        "primary_component": primary_component,
        "dependency_component": badge_component,
        "primary_instance_root_ids": [
            first_instance["root_object_id"],
            second_instance["root_object_id"],
        ],
        "nested_definition_instance_root_id": nested_source["id"],
        "title_source_id": title_source["id"],
        "badge_source_root_id": badge_root["id"],
        "badge_label_id": badge_label["id"],
        "slot_source_id": slot_source["id"],
        "slot_default_id": slot_default["id"],
        "slot_definition": slot_definition,
        "custom_slot_content_id": custom_slot_content["id"],
        "slot_report": slot_report,
    }


def _property_by_name(component: Mapping[str, Any], name: str) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            row
            for row in component.get("Properties", [])
            if str(row.get("Name") or "") == name
        )
    )


def build_component_contract_evidence() -> dict[str, Any]:
    """Build deterministic schema, dependency, property, and Slot evidence."""

    fixture = build_component_qa_fixture()
    document = fixture["document"]
    exported = painter_ui_to_umg_document(document)
    preflight = preflight_painter_umg(document)
    components = list(exported.get("Components") or [])
    instances = list(exported.get("ComponentInstances") or [])
    primary_id = str(fixture["primary_component"]["id"])
    dependency_id = str(fixture["dependency_component"]["id"])
    component_by_id = {
        str(row.get("Id") or ""): row for row in components
    }
    primary = component_by_id.get(primary_id, {})
    dependency = component_by_id.get(dependency_id, {})
    primary_instances = [
        row
        for row in instances
        if str(row.get("ComponentId") or "") == primary_id
        and str(row.get("LayerId") or "")
        in set(fixture["primary_instance_root_ids"])
    ]
    nested_instances = [
        row
        for row in instances
        if str(row.get("ComponentId") or "") == dependency_id
    ]
    nested_placeholder = next(
        (
            row
            for row in primary.get("Layers", [])
            if str(row.get("Id") or "")
            == fixture["nested_definition_instance_root_id"]
        ),
        {},
    )
    try:
        nested_payload = json.loads(
            str(nested_placeholder.get("PayloadJson") or "{}")
        ).get("component_instance", {})
    except (TypeError, ValueError, json.JSONDecodeError):
        nested_payload = {}
    title = (
        _property_by_name(primary, "Title")
        if primary
        else {}
    )
    show_badge = (
        _property_by_name(primary, "Show badge")
        if primary
        else {}
    )
    slots = list(primary.get("Slots") or []) if primary else []
    primary_values = [
        json.loads(str(row.get("PropertyValuesJson") or "{}"))
        for row in primary_instances
    ]
    primary_values.sort(key=lambda row: str(row.get("Title") or ""))
    expected_primary_values = [
        {
            "Title": "First card",
            "Show badge": True,
            "Content": fixture["slot_source_id"],
            "Tone": "Default",
        },
        {
            "Title": "Second card",
            "Show badge": False,
            "Content": fixture["slot_source_id"],
            "Tone": "Default",
        },
    ]
    slot_contents = [
        content
        for row in primary_instances
        for content in row.get("SlotContents", [])
    ]
    expected_bindings = {
        "Title": [
            {
                "LayerId": fixture["title_source_id"],
                "TargetPath": "content.text",
            }
        ],
        "Show badge": [
            {
                "LayerId": fixture["nested_definition_instance_root_id"],
                "TargetPath": "visible",
            }
        ],
    }
    checks = {
        "schema_18": int(exported.get("SchemaVersion") or 0)
        == COMPONENT_DOCUMENT_SCHEMA_VERSION,
        "preflight_ready": bool(preflight.get("ok")),
        "primary_definition_present": bool(primary),
        "dependency_definition_present": bool(dependency),
        "primary_instance_count": len(primary_instances) == 2,
        "screen_instances_are_primary_only": (
            len(instances) == 2 and not nested_instances
        ),
        "dependency_declared": dependency_id
        in list(primary.get("DependencyComponentIds") or []),
        "text_property": (
            title.get("Type") == "text"
            and title.get("DefaultValueJson")
            == _canonical_json(PRIMARY_PROPERTY_DEFAULTS["Title"])
            and title.get("Bindings") == expected_bindings["Title"]
        ),
        "boolean_property": (
            show_badge.get("Type") == "boolean"
            and show_badge.get("DefaultValueJson")
            == _canonical_json(PRIMARY_PROPERTY_DEFAULTS["Show badge"])
            and show_badge.get("Bindings")
            == expected_bindings["Show badge"]
        ),
        "static_variant": str(primary.get("VariantValuesJson") or "")
        == _canonical_json(PRIMARY_VARIANT_VALUES),
        "static_slot": (
            len(slots) == 1
            and slots[0].get("Name") == "Content"
            and slots[0].get("LayerId") == fixture["slot_source_id"]
            and slots[0].get("ExposeOnInstanceOnly") is True
        ),
        "property_values": primary_values == expected_primary_values,
        "slot_content": any(
            row.get("SlotName") == "Content"
            and row.get("RootLayerIds")
            == [fixture["custom_slot_content_id"]]
            for row in slot_contents
        ),
        "nested_component": (
            nested_payload.get("id")
            == fixture["nested_definition_instance_root_id"]
            and nested_payload.get("component_id") == dependency_id
            and nested_payload.get("property_values") == {}
            and nested_payload.get("resolved_overrides") == {}
            and nested_payload.get("slot_contents") == []
        ),
    }
    return {
        "schema": "tigerstudio.painter.ui.unreal_umg_component_contract.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "fixture": fixture,
        "umg_document": exported,
        "preflight": preflight,
        "primary_component_id": primary_id,
        "dependency_component_id": dependency_id,
        "primary_component": copy.deepcopy(primary),
        "dependency_component": copy.deepcopy(dependency),
        "primary_instances": copy.deepcopy(primary_instances),
        "nested_instances": copy.deepcopy(nested_instances),
        "nested_placeholder": copy.deepcopy(nested_placeholder),
        "nested_component_instance_payload": copy.deepcopy(nested_payload),
        "expected_primary_property_values": expected_primary_values,
        "expected_bindings": expected_bindings,
    }


def _safe_unreal_name(value: object) -> str:
    result = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in str(value or "")
    )
    return result or "Document"


def _component_asset_paths(
    contract: Mapping[str, Any],
    *,
    destination_root: str = COMPONENT_QA_DESTINATION_ROOT,
) -> dict[str, str]:
    document_id = _safe_unreal_name(
        contract.get("umg_document", {}).get("DocumentId")
    )
    generated_root = destination_root.rstrip("/") + "/" + document_id
    paths: dict[str, str] = {}
    for component_id in (
        str(contract.get("dependency_component_id") or ""),
        str(contract.get("primary_component_id") or ""),
    ):
        safe_id = _safe_unreal_name(component_id)
        name = "WBP_TS_C_" + safe_id
        paths[component_id] = (
            f"{generated_root}/Components/{name}.{name}"
        )
    return paths


def _component_class_paths(
    contract: Mapping[str, Any],
    *,
    destination_root: str = COMPONENT_QA_DESTINATION_ROOT,
) -> dict[str, str]:
    return {
        component_id: asset_path + "_C"
        for component_id, asset_path in _component_asset_paths(
            contract,
            destination_root=destination_root,
        ).items()
    }


def _main_asset_path(
    contract: Mapping[str, Any],
    *,
    destination_root: str = COMPONENT_QA_DESTINATION_ROOT,
) -> str:
    document_id = _safe_unreal_name(
        contract.get("umg_document", {}).get("DocumentId")
    )
    name = "WBP_TS_" + document_id
    return (
        destination_root.rstrip("/")
        + f"/{document_id}/Widgets/{name}.{name}"
    )


def _class_name(class_path: object) -> str:
    value = str(class_path or "").strip().strip("'\"")
    if not value:
        return ""
    return value.rsplit(".", 1)[-1].rsplit("/", 1)[-1]


def _expected_widget_classes(
    contract: Mapping[str, Any],
    component_class_paths: Mapping[str, str],
) -> dict[str, Any]:
    fixture = contract.get("fixture", {})
    primary_id = str(contract.get("primary_component_id") or "")
    dependency_id = str(contract.get("dependency_component_id") or "")
    primary_class = _class_name(component_class_paths.get(primary_id))
    dependency_class = _class_name(
        component_class_paths.get(dependency_id)
    )
    main = {
        BACKGROUND_ID: "Image",
        **{
            str(layer_id): primary_class
            for layer_id in fixture.get("primary_instance_root_ids", [])
        },
        str(fixture.get("custom_slot_content_id") or ""): "TextBlock",
    }
    badge_root_id = str(fixture.get("badge_source_root_id") or "")
    primary_root_id = str(
        contract.get("primary_component", {}).get("RootLayerId") or ""
    )
    slot_source_id = str(fixture.get("slot_source_id") or "")
    dependency = {
        badge_root_id: "Overlay",
        badge_root_id + "#background": "Image",
        badge_root_id + "#panel": "Overlay",
        str(fixture.get("badge_label_id") or ""): "TextBlock",
    }
    primary = {
        primary_root_id: "Overlay",
        primary_root_id + "#background": "Image",
        primary_root_id + "#panel": "Overlay",
        str(fixture.get("title_source_id") or ""): "TextBlock",
        str(fixture.get("nested_definition_instance_root_id") or ""):
            dependency_class,
        slot_source_id: "Overlay",
        slot_source_id + "#background": "Image",
        slot_source_id + "#named_slot": "NamedSlot",
        str(fixture.get("slot_default_id") or ""): "TextBlock",
    }
    # Generation audits are keyed by source LayerId.  Reopened widget trees
    # use the authored Slot name because UNamedSlot is deliberately named for
    # its public instance-facing API, not its source layer.
    dependency_reopen = {
        key: value
        for key, value in dependency.items()
        if "#" not in key
    }
    primary_reopen = {
        key: value
        for key, value in primary.items()
        if "#" not in key
    }
    primary_reopen["Content"] = "NamedSlot"
    return {
        "main": main,
        "components": {
            dependency_id: dependency,
            primary_id: primary,
        },
        "component_reopen": {
            dependency_id: dependency_reopen,
            primary_id: primary_reopen,
        },
    }


def build_component_generation_contract(
    generation: Mapping[str, Any],
    contract: Mapping[str, Any],
    *,
    destination_root: str = COMPONENT_QA_DESTINATION_ROOT,
) -> dict[str, Any]:
    """Verify deterministic main/component assets, classes, and counts."""

    expected_asset_paths = _component_asset_paths(
        contract,
        destination_root=destination_root,
    )
    expected_class_paths = _component_class_paths(
        contract,
        destination_root=destination_root,
    )
    actual_asset_paths_value = generation.get(
        "generated_component_asset_paths"
    )
    actual_class_paths_value = generation.get(
        "generated_component_class_paths"
    )
    actual_asset_paths = (
        dict(actual_asset_paths_value)
        if isinstance(actual_asset_paths_value, Mapping)
        else {}
    )
    actual_class_paths = (
        dict(actual_class_paths_value)
        if isinstance(actual_class_paths_value, Mapping)
        else {}
    )
    expected_classes = _expected_widget_classes(
        contract,
        expected_class_paths,
    )
    expected_audit = dict(expected_classes["main"])
    for component_id, rows in expected_classes["components"].items():
        expected_audit.update(
            {
                f"component:{component_id}/{layer_id}": class_name
                for layer_id, class_name in rows.items()
            }
        )
    actual_audit_value = generation.get("generated_widget_classes")
    actual_audit = (
        dict(actual_audit_value)
        if isinstance(actual_audit_value, Mapping)
        else {}
    )
    expected_component_ids = set(expected_asset_paths)
    expected_screen_count = len(
        contract.get("umg_document", {}).get("Layers", [])
    )
    checks = {
        "generation_ok": bool(generation.get("ok")),
        "main_asset_loaded": bool(
            generation.get("generated_asset_loaded")
        ),
        "main_asset_class": generation.get("generated_asset_class")
        == "WidgetBlueprint",
        "main_asset_path": str(
            generation.get("generated_asset_path") or ""
        )
        == _main_asset_path(contract, destination_root=destination_root),
        "screen_widget_count": int(
            generation.get("generated_widget_count") or 0
        )
        == expected_screen_count,
        "component_count": int(
            generation.get("generated_component_count") or 0
        )
        == len(expected_component_ids),
        "component_asset_ids": set(actual_asset_paths)
        == expected_component_ids,
        "component_class_ids": set(actual_class_paths)
        == expected_component_ids,
        "component_asset_paths": actual_asset_paths
        == expected_asset_paths,
        "component_class_paths": actual_class_paths
        == expected_class_paths,
        "widget_classes": all(
            actual_audit.get(name) == class_name
            for name, class_name in expected_audit.items()
        ),
    }
    return {
        "schema": "tigerstudio.painter.ui.unreal_umg_component_generation_contract.v1",
        "ok": all(checks.values()),
        "checks": checks,
        "expected_main_asset_path": _main_asset_path(
            contract,
            destination_root=destination_root,
        ),
        "actual_main_asset_path": str(
            generation.get("generated_asset_path") or ""
        ),
        "expected_screen_widget_count": expected_screen_count,
        "actual_screen_widget_count": int(
            generation.get("generated_widget_count") or 0
        ),
        "expected_component_count": len(expected_component_ids),
        "actual_component_count": int(
            generation.get("generated_component_count") or 0
        ),
        "expected_component_asset_paths": expected_asset_paths,
        "actual_component_asset_paths": actual_asset_paths,
        "expected_component_class_paths": expected_class_paths,
        "actual_component_class_paths": actual_class_paths,
        "expected_widget_classes": expected_classes,
        "expected_widget_class_audit": expected_audit,
        "actual_widget_class_audit": actual_audit,
    }


def _validate_reopen(
    value: Mapping[str, Any],
    *,
    expected_widget_classes: Mapping[str, str],
    generation_widget_audit_ok: bool = False,
) -> dict[str, Any]:
    actual_classes_value = value.get("widget_classes")
    actual_classes = (
        dict(actual_classes_value)
        if isinstance(actual_classes_value, Mapping)
        else {}
    )
    minimum_widget_count = len(expected_widget_classes) + 2
    warnings = [str(row) for row in value.get("warnings", [])]
    python_tree_unavailable = (
        not actual_classes
        and any(
            row.startswith(
                "widget_tree_not_exposed_to_python_after_reopen:"
            )
            for row in warnings
        )
    )
    generation_audit_fallback = bool(
        generation_widget_audit_ok and python_tree_unavailable
    )
    checks = {
        "command_ok": bool(value.get("ok")),
        "asset_loaded": bool(value.get("asset_loaded")),
        "asset_class": value.get("asset_class") == "WidgetBlueprint",
        "generated_class_loaded": bool(
            value.get("generated_class_loaded")
        ),
        "widget_count": (
            int(value.get("widget_count") or 0) >= minimum_widget_count
            or generation_audit_fallback
        ),
        "widget_classes": (
            bool(actual_classes)
            and all(
                actual_classes.get(name) == class_name
                for name, class_name in expected_widget_classes.items()
            )
        )
        or generation_audit_fallback,
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "minimum_widget_count": minimum_widget_count,
        "actual_widget_count": int(value.get("widget_count") or 0),
        "widget_tree_verification": (
            "python_reopen_widget_tree"
            if actual_classes
            else "generation_audit_plus_asset_reopen"
            if generation_audit_fallback
            else "unverified"
        ),
        "python_widget_tree_unavailable": python_tree_unavailable,
        "expected_widget_classes": dict(expected_widget_classes),
        "actual_widget_classes": actual_classes,
    }


def _validate_render(
    value: Mapping[str, Any],
    output_path: Path,
    *,
    fixture: Mapping[str, Any],
) -> dict[str, Any]:
    pixel_evidence = value.get("pixel_evidence")
    pixel_evidence = (
        dict(pixel_evidence)
        if isinstance(pixel_evidence, Mapping)
        else {}
    )
    text_value = value.get("widget_text_audit")
    text_audit = (
        dict(text_value) if isinstance(text_value, Mapping) else {}
    )
    visibility_value = value.get("widget_visibility_audit")
    visibility_audit = (
        dict(visibility_value)
        if isinstance(visibility_value, Mapping)
        else {}
    )
    instance_ids = [
        str(row)
        for row in fixture.get("primary_instance_root_ids", [])
    ]
    title_id = str(fixture.get("title_source_id") or "")
    badge_id = str(
        fixture.get("nested_definition_instance_root_id") or ""
    )
    expected_text_audit = {
        f"{instance_id}/{title_id}": title
        for instance_id, title in zip(
            instance_ids,
            EXPECTED_PRIMARY_INSTANCE_TITLES,
            strict=True,
        )
    }
    expected_visibility_audit = {
        f"{instance_id}/{badge_id}": visibility
        for instance_id, visibility in zip(
            instance_ids,
            ("Visible", "Collapsed"),
            strict=True,
        )
    }
    checks = {
        "command_ok": bool(value.get("ok")),
        "fwidget_renderer": value.get("backend")
        == "unreal_fwidget_renderer",
        "dimensions": (
            int(value.get("width") or 0) == 960
            and int(value.get("height") or 0) == 540
        ),
        "visible_content": bool(pixel_evidence.get("visible_content")),
        "instance_text_values": bool(expected_text_audit)
        and all(
            text_audit.get(path) == expected
            for path, expected in expected_text_audit.items()
        ),
        "instance_badge_visibility": bool(expected_visibility_audit)
        and all(
            visibility_audit.get(path) == expected
            for path, expected in expected_visibility_audit.items()
        ),
        "png_exists": output_path.is_file(),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "pixel_evidence": pixel_evidence,
        "expected_widget_text_audit": expected_text_audit,
        "actual_widget_text_audit": text_audit,
        "expected_widget_visibility_audit": expected_visibility_audit,
        "actual_widget_visibility_audit": visibility_audit,
    }


def run_component_qa(
    workspace: Path,
    *,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run schema-18 component acceptance through a real UE commandlet."""

    workspace = workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    contract = build_component_contract_evidence()
    fixture_path = workspace / "component_fixture.json"
    umg_path = workspace / "component_fixture_umg.json"
    fixture_path.write_text(
        json.dumps(
            contract["fixture"]["document"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    umg_path.write_text(
        json.dumps(
            contract["umg_document"],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    paths: dict[str, Any] = {
        "fixture_document": str(fixture_path),
        "umg_document": str(umg_path),
    }
    if not contract["ok"]:
        return {
            "schema": COMPONENT_QA_SCHEMA,
            "ok": False,
            "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
            "paths": paths,
            "contract": contract,
            "generation": {
                "ok": False,
                "reason": "component_contract_preflight_failed",
            },
        }

    project = _ensure_project(workspace)
    generation = generate_painter_umg(
        contract["fixture"]["document"],
        project_path=project,
        output_dir=workspace / "component_packet",
        destination_root=COMPONENT_QA_DESTINATION_ROOT,
        timeout_seconds=timeout_seconds,
    )
    generation_contract = build_component_generation_contract(
        generation,
        contract,
    )
    expected_classes = generation_contract["expected_widget_classes"]
    main_asset_path = str(generation.get("generated_asset_path") or "")
    reopened = (
        _reopen_generated_asset(
            project,
            main_asset_path,
            expected_widget_classes=expected_classes["main"],
            timeout_seconds=timeout_seconds,
        )
        if generation_contract["ok"] and main_asset_path
        else {
            "ok": False,
            "reason": "generation_contract_failed_before_reopen",
        }
    )
    reopen_contract = _validate_reopen(
        reopened,
        expected_widget_classes=expected_classes["main"],
        generation_widget_audit_ok=bool(
            generation_contract["checks"].get("widget_classes")
        ),
    )

    component_reopens: dict[str, Any] = {}
    component_reopen_contracts: dict[str, Any] = {}
    actual_component_paths = generation_contract[
        "actual_component_asset_paths"
    ]
    if generation_contract["ok"]:
        for component_id in (
            contract["dependency_component_id"],
            contract["primary_component_id"],
        ):
            expected = expected_classes["component_reopen"][component_id]
            component_reopens[component_id] = _reopen_generated_asset(
                project,
                actual_component_paths[component_id],
                expected_widget_classes=expected,
                timeout_seconds=timeout_seconds,
            )
            component_reopen_contracts[component_id] = _validate_reopen(
                component_reopens[component_id],
                expected_widget_classes=expected,
                generation_widget_audit_ok=bool(
                    generation_contract["checks"].get("widget_classes")
                ),
            )
    else:
        for component_id in (
            contract["dependency_component_id"],
            contract["primary_component_id"],
        ):
            component_reopens[component_id] = {
                "ok": False,
                "reason": "generation_contract_failed_before_reopen",
            }
            component_reopen_contracts[component_id] = {
                "ok": False,
                "reason": "generation_contract_failed_before_reopen",
            }

    all_reopened = (
        reopen_contract["ok"]
        and all(
            row.get("ok")
            for row in component_reopen_contracts.values()
        )
    )
    output_path = workspace / "component_unreal.png"
    rendered = (
        _render_generated_asset(
            project,
            main_asset_path,
            output_path,
            width=960,
            height=540,
            timeout_seconds=timeout_seconds,
        )
        if all_reopened and main_asset_path
        else {
            "ok": False,
            "reason": "asset_reopen_failed_before_render",
        }
    )
    render_contract = _validate_render(
        rendered,
        output_path,
        fixture=contract["fixture"],
    )
    paths.update(
        {
            "project": str(project),
            "render": str(output_path),
            "generated_asset": main_asset_path,
            "generated_component_assets": actual_component_paths,
        }
    )
    return {
        "schema": COMPONENT_QA_SCHEMA,
        "ok": (
            contract["ok"]
            and generation_contract["ok"]
            and reopen_contract["ok"]
            and all_reopened
            and render_contract["ok"]
        ),
        "engine_root": str(DEFAULT_UNREAL_ENGINE_ROOT),
        "project_path": str(project),
        "paths": paths,
        "contract": contract,
        "generation": generation,
        "generation_contract": generation_contract,
        "reopen": reopened,
        "reopen_contract": reopen_contract,
        "component_reopens": component_reopens,
        "component_reopen_contracts": component_reopen_contracts,
        "render": rendered,
        "render_contract": render_contract,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    report = run_component_qa(
        args.workspace,
        timeout_seconds=args.timeout,
    )
    report_path = args.workspace.expanduser().resolve() / "qa_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"ok": report["ok"], "report": str(report_path)},
            ensure_ascii=False,
        )
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
