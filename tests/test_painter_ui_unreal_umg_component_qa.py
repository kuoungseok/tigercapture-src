from __future__ import annotations

import copy
from pathlib import Path
from typing import Any


def _valid_generation(contract: dict[str, Any]) -> dict[str, Any]:
    from tools.qa_painter_ui_unreal_umg_component import (
        _component_asset_paths,
        _component_class_paths,
        _expected_widget_classes,
        _main_asset_path,
    )

    asset_paths = _component_asset_paths(contract)
    class_paths = _component_class_paths(contract)
    expected = _expected_widget_classes(contract, class_paths)
    audit = dict(expected["main"])
    for component_id, rows in expected["components"].items():
        audit.update(
            {
                f"component:{component_id}/{layer_id}": class_name
                for layer_id, class_name in rows.items()
            }
        )
    return {
        "ok": True,
        "generated_asset_path": _main_asset_path(contract),
        "generated_asset_loaded": True,
        "generated_asset_class": "WidgetBlueprint",
        "generated_widget_count": len(contract["umg_document"]["Layers"]),
        "generated_component_count": 2,
        "generated_component_asset_paths": asset_paths,
        "generated_component_class_paths": class_paths,
        "generated_widget_classes": audit,
        "errors": [],
        "warnings": [],
    }


def test_component_qa_fixture_authors_primary_instances_and_dependency() -> None:
    from tools.qa_painter_ui_unreal_umg_component import (
        EXPECTED_PRIMARY_INSTANCE_TITLES,
        PRIMARY_VARIANT_VALUES,
        build_component_qa_fixture,
    )

    fixture = build_component_qa_fixture()
    document = fixture["document"]
    primary = fixture["primary_component"]
    dependency = fixture["dependency_component"]

    assert len(document["components"]) == 2
    assert primary["id"] != dependency["id"]
    assert primary["metadata"]["variant_properties"] == (
        PRIMARY_VARIANT_VALUES
    )
    assert primary["property_definitions"]["Title"]["type"] == "text"
    assert (
        primary["property_definitions"]["Show badge"]["type"]
        == "boolean"
    )
    assert primary["property_definitions"]["Content"]["type"] == "slot"
    assert len(fixture["primary_instance_root_ids"]) == 2
    roots = {
        row["id"]: row
        for row in document["objects"]
        if row["id"] in fixture["primary_instance_root_ids"]
    }
    assert {
        roots[object_id]["component_properties"]["Title"]
        for object_id in fixture["primary_instance_root_ids"]
    } == set(EXPECTED_PRIMARY_INSTANCE_TITLES)
    assert fixture["slot_report"]["child_count"] == 2
    assert fixture["custom_slot_content_id"] in fixture["slot_report"][
        "child_ids"
    ]


def test_component_qa_contract_requires_schema18_typed_records() -> None:
    from tools.qa_painter_ui_unreal_umg_component import (
        COMPONENT_DOCUMENT_SCHEMA_VERSION,
        build_component_contract_evidence,
    )

    evidence = build_component_contract_evidence()

    assert evidence["umg_document"]["SchemaVersion"] == (
        COMPONENT_DOCUMENT_SCHEMA_VERSION
    )
    assert evidence["ok"] is True
    assert all(evidence["checks"].values())
    assert len(evidence["primary_instances"]) == 2
    assert evidence["primary_component"]["DependencyComponentIds"] == [
        evidence["dependency_component_id"]
    ]


def test_component_generation_contract_requires_asset_class_and_count_maps(
) -> None:
    from tools.qa_painter_ui_unreal_umg_component import (
        build_component_contract_evidence,
        build_component_generation_contract,
    )

    contract = build_component_contract_evidence()
    generation = _valid_generation(contract)

    evidence = build_component_generation_contract(generation, contract)

    assert evidence["ok"] is True
    assert all(evidence["checks"].values())
    assert evidence["expected_component_count"] == 2
    assert set(evidence["expected_component_asset_paths"]) == {
        contract["primary_component_id"],
        contract["dependency_component_id"],
    }
    primary_id = contract["primary_component_id"]
    dependency_id = contract["dependency_component_id"]
    nested_id = contract["fixture"][
        "nested_definition_instance_root_id"
    ]
    dependency_class = evidence["expected_component_class_paths"][
        dependency_id
    ].rsplit(".", 1)[-1]
    assert evidence["expected_widget_classes"]["components"][
        primary_id
    ][nested_id] == dependency_class

    missing = copy.deepcopy(generation)
    missing["generated_component_asset_paths"].pop(dependency_id)
    missing_evidence = build_component_generation_contract(
        missing,
        contract,
    )
    assert missing_evidence["ok"] is False
    assert missing_evidence["checks"]["component_asset_ids"] is False

    lossy_list = copy.deepcopy(generation)
    lossy_list["generated_component_asset_paths"] = list(
        generation["generated_component_asset_paths"].values()
    )
    lossy_evidence = build_component_generation_contract(
        lossy_list,
        contract,
    )
    assert lossy_evidence["ok"] is False
    assert lossy_evidence["checks"]["component_asset_ids"] is False


def test_component_reopen_uses_generation_audit_when_ue_python_hides_tree(
) -> None:
    from tools.qa_painter_ui_unreal_umg_component import _validate_reopen

    reopened = {
        "ok": True,
        "asset_loaded": True,
        "asset_class": "WidgetBlueprint",
        "generated_class_loaded": True,
        "widget_count": 0,
        "widget_classes": {},
        "warnings": [
            "widget_tree_not_exposed_to_python_after_reopen:private"
        ],
    }
    expected = {"Card": "Overlay", "Title": "TextBlock"}

    verified = _validate_reopen(
        reopened,
        expected_widget_classes=expected,
        generation_widget_audit_ok=True,
    )
    unverified = _validate_reopen(
        reopened,
        expected_widget_classes=expected,
        generation_widget_audit_ok=False,
    )

    assert verified["ok"] is True
    assert verified["widget_tree_verification"] == (
        "generation_audit_plus_asset_reopen"
    )
    assert unverified["ok"] is False


def test_component_qa_reopens_main_and_both_components_then_renders(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.qa_painter_ui_unreal_umg_component as component_qa

    contract = component_qa.build_component_contract_evidence()
    generation = _valid_generation(contract)
    project = tmp_path / "ComponentQA.uproject"
    reopen_calls: list[dict[str, Any]] = []
    render_calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        component_qa,
        "_ensure_project",
        lambda _workspace: project,
    )
    monkeypatch.setattr(
        component_qa,
        "generate_painter_umg",
        lambda *_args, **_kwargs: copy.deepcopy(generation),
    )

    def fake_reopen(
        _project: Path,
        asset_path: str,
        *,
        expected_widget_classes: dict[str, str],
        timeout_seconds: int,
        **_kwargs,
    ) -> dict[str, Any]:
        reopen_calls.append(
            {
                "asset_path": asset_path,
                "expected_widget_classes": copy.deepcopy(
                    expected_widget_classes
                ),
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "ok": True,
            "asset_path": asset_path,
            "asset_loaded": True,
            "asset_class": "WidgetBlueprint",
            "generated_class_loaded": True,
            "widget_count": len(expected_widget_classes) + 2,
            "widget_classes": copy.deepcopy(expected_widget_classes),
        }

    def fake_render(
        _project: Path,
        asset_path: str,
        output_path: Path,
        *,
        width: int,
        height: int,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        output_path.write_bytes(b"component-qa-render")
        render_calls.append(
            {
                "asset_path": asset_path,
                "width": width,
                "height": height,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "ok": True,
            "backend": "unreal_fwidget_renderer",
            "width": width,
            "height": height,
            "pixel_evidence": {"visible_content": True},
            "widget_text_audit": {
                (
                    f"{instance_id}/"
                    f"{contract['fixture']['title_source_id']}"
                ): title
                for instance_id, title in zip(
                    contract["fixture"]["primary_instance_root_ids"],
                    component_qa.EXPECTED_PRIMARY_INSTANCE_TITLES,
                    strict=True,
                )
            },
            "widget_visibility_audit": {
                (
                    f"{instance_id}/"
                    f"{contract['fixture']['nested_definition_instance_root_id']}"
                ): visibility
                for instance_id, visibility in zip(
                    contract["fixture"]["primary_instance_root_ids"],
                    ("Visible", "Collapsed"),
                    strict=True,
                )
            },
        }

    monkeypatch.setattr(
        component_qa,
        "_reopen_generated_asset",
        fake_reopen,
    )
    monkeypatch.setattr(
        component_qa,
        "_render_generated_asset",
        fake_render,
    )

    report = component_qa.run_component_qa(
        tmp_path / "qa",
        timeout_seconds=123,
    )

    assert report["ok"] is True
    assert len(reopen_calls) == 3
    assert len(render_calls) == 1
    assert render_calls[0]["width"] == 960
    assert render_calls[0]["height"] == 540
    assert all(
        row["ok"]
        for row in report["component_reopen_contracts"].values()
    )
    primary_id = contract["primary_component_id"]
    dependency_id = contract["dependency_component_id"]
    nested_id = contract["fixture"][
        "nested_definition_instance_root_id"
    ]
    dependency_class = generation["generated_component_class_paths"][
        dependency_id
    ].rsplit(".", 1)[-1]
    primary_reopen = next(
        row
        for row in reopen_calls
        if row["asset_path"]
        == generation["generated_component_asset_paths"][primary_id]
    )
    assert primary_reopen["expected_widget_classes"][nested_id] == (
        dependency_class
    )
