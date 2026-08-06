from __future__ import annotations

import copy

import pytest


EXPECTED_COUNTS = {
    "Native": 0,
    "Material": 0,
    "Baked": 0,
    "Blocked": 0,
}


def _native_layer() -> dict:
    return {
        "Id": "native",
        "Name": "Native",
        "Kind": "Image",
        "Disposition": "Native",
    }


def _generic_document() -> dict:
    return {
        "SchemaVersion": 13,
        "Resources": [],
        "Layers": [_native_layer()],
    }


def _painter_document() -> dict:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    source = create_ui_document(320, 180)
    source["artboards"][0]["background"] = "#00000000"
    document, _row = add_ui_object(
        source,
        kind="rectangle",
        x=16,
        y=20,
        width=80,
        height=40,
    )
    return painter_ui_to_umg_document(document)


@pytest.mark.parametrize("layers", [None, {}, "layers", 7, False])
def test_generic_preflight_rejects_missing_or_wrong_layers_container(
    layers: object,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    document = _generic_document()
    if layers is None:
        document.pop("Layers")
    else:
        document["Layers"] = layers

    report = preflight_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert set(report["counts"]) == {
        "Native",
        "Material",
        "Baked",
        "Blocked",
    }
    assert report["blockers"] == [
        {
            "layer_id": "",
            "name": "Tiger UMG document",
            "reasons": ["umg_layers_record_invalid"],
        }
    ]


@pytest.mark.parametrize("row", [None, [], "layer", 3, False])
def test_generic_preflight_rejects_non_mapping_layer_rows(row: object) -> None:
    from app.unreal_umg_document import preflight_umg_document

    document = _generic_document()
    document["Layers"] = [row]

    report = preflight_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"][0]["reasons"] == [
        "umg_layer_record_invalid"
    ]


@pytest.mark.parametrize(
    "disposition",
    [pytest.param(None, id="missing"), "", "native", "Unknown", 1, False, []],
)
def test_generic_preflight_rejects_non_exact_disposition_without_new_count_key(
    disposition: object,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    document = _generic_document()
    layer = document["Layers"][0]
    if disposition is None:
        layer.pop("Disposition")
    else:
        layer["Disposition"] = disposition

    report = preflight_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"] == [
        {
            "layer_id": "native",
            "name": "Native",
            "reasons": ["umg_layer_disposition_invalid"],
        }
    ]


def test_generic_preflight_counts_only_the_exact_four_dispositions() -> None:
    from app.unreal_umg_document import preflight_umg_document

    document = _generic_document()
    document["Layers"] = [
        _native_layer(),
        {
            "Id": "material",
            "Name": "Material",
            "Kind": "Image",
            "Disposition": "Material",
        },
        {
            "Id": "baked",
            "Name": "Baked",
            "Kind": "Image",
            "Disposition": "Baked",
        },
        {
            "Id": "blocked",
            "Name": "Blocked",
            "Kind": "Unsupported",
            "Disposition": "Blocked",
            "BlockReasons": ["unsupported_fixture"],
        },
    ]

    report = preflight_umg_document(document)

    assert report["counts"] == {
        "Native": 1,
        "Material": 1,
        "Baked": 1,
        "Blocked": 1,
    }
    assert set(report["counts"]) == {
        "Native",
        "Material",
        "Baked",
        "Blocked",
    }


@pytest.mark.parametrize("schema_version", range(4, 14))
def test_generic_preflight_preserves_schema_4_to_13_native_documents_without_resources(
    schema_version: int,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    report = preflight_umg_document(
        {
            "SchemaVersion": schema_version,
            "Layers": [_native_layer()],
        }
    )

    assert report == {
        "schema_version": schema_version,
        "ok": True,
        "counts": {
            "Native": 1,
            "Material": 0,
            "Baked": 0,
            "Blocked": 0,
        },
        "blockers": [],
    }


@pytest.mark.parametrize("resources", [None, {}, "resources", 3, False])
def test_generic_preflight_rejects_present_wrong_resources_container(
    resources: object,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    document = _generic_document()
    document["Resources"] = resources

    report = preflight_umg_document(document)

    assert report["ok"] is False
    assert report["counts"]["Native"] == 1
    assert report["blockers"][0]["reasons"] == [
        "umg_resources_record_invalid"
    ]


@pytest.mark.parametrize("row", [None, [], "resource", 5, False])
def test_generic_preflight_rejects_non_mapping_resource_rows(row: object) -> None:
    from app.unreal_umg_document import preflight_umg_document

    document = _generic_document()
    document["Resources"] = [row]

    report = preflight_umg_document(document)

    assert report["ok"] is False
    assert report["counts"]["Native"] == 1
    assert report["blockers"][0]["reasons"] == [
        "umg_resource_record_invalid"
    ]


def test_generic_package_cannot_filter_an_invalid_resource_row_into_success(
    tmp_path,
) -> None:
    from app.unreal_umg_document import package_umg_document

    document = _generic_document()
    document["Resources"] = [None]

    package = package_umg_document(document, tmp_path)

    assert package["ok"] is False
    assert package["preflight"]["blockers"][0]["reasons"] == [
        "umg_resource_record_invalid"
    ]


def test_generic_preflight_rejects_a_non_mapping_document_without_throwing() -> None:
    from app.unreal_umg_document import preflight_umg_document

    report = preflight_umg_document(None)  # type: ignore[arg-type]

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"][0]["reasons"] == [
        "umg_document_record_invalid",
        "umg_layers_record_invalid",
        "umg_schema_version_unsupported",
    ]


def test_painter_internal_preflight_keeps_valid_generated_document_green() -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    report = _preflight_painter_umg_document(_painter_document())

    assert report["ok"] is True
    assert report["counts"] == {
        "Native": 1,
        "Material": 0,
        "Baked": 0,
        "Blocked": 0,
    }
    assert report["blockers"] == []


@pytest.mark.parametrize("layers", [None, {}, "layers", 7, False])
def test_painter_internal_preflight_rejects_missing_or_wrong_layers_container(
    layers: object,
) -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    document = _painter_document()
    if layers is None:
        document.pop("Layers")
    else:
        document["Layers"] = layers

    report = _preflight_painter_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"][0] == {
        "object_id": "",
        "name": "Tiger UMG document",
        "reasons": ["umg_layers_record_invalid"],
    }


@pytest.mark.parametrize("row", [None, [], "layer", 3, False])
def test_painter_internal_preflight_rejects_non_mapping_layer_rows(
    row: object,
) -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    document = _painter_document()
    document["Layers"] = [row]

    report = _preflight_painter_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"][0]["reasons"] == [
        "umg_layer_record_invalid"
    ]


@pytest.mark.parametrize(
    "disposition",
    [pytest.param(None, id="missing"), "", "native", "Unknown", 1, False, []],
)
def test_painter_internal_preflight_rejects_non_exact_disposition(
    disposition: object,
) -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    document = _painter_document()
    layer = document["Layers"][0]
    if disposition is None:
        layer.pop("Disposition")
    else:
        layer["Disposition"] = disposition

    report = _preflight_painter_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"] == [
        {
            "object_id": str(layer["Id"]),
            "name": str(layer["Name"]),
            "reasons": ["umg_layer_disposition_invalid"],
        }
    ]


@pytest.mark.parametrize(
    ("mode", "resources", "reason"),
    [
        ("missing", None, "umg_resources_record_invalid"),
        ("wrong", {}, "umg_resources_record_invalid"),
        ("wrong", "resources", "umg_resources_record_invalid"),
        ("row", [None], "umg_resource_record_invalid"),
        ("row", ["resource"], "umg_resource_record_invalid"),
    ],
)
def test_painter_internal_preflight_rejects_malformed_resources(
    mode: str,
    resources: object,
    reason: str,
) -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    document = copy.deepcopy(_painter_document())
    if mode == "missing":
        document.pop("Resources")
    else:
        document["Resources"] = resources

    report = _preflight_painter_umg_document(document)

    assert report["ok"] is False
    assert report["counts"]["Native"] == 1
    assert report["resource_count"] == 0
    assert reason in report["blockers"][0]["reasons"]


@pytest.mark.parametrize(
    "document",
    [
        {"SchemaVersion": 13, "Resources": []},
        {"SchemaVersion": 13, "Resources": [], "Layers": None},
        {"SchemaVersion": 13, "Resources": [None], "Layers": []},
    ],
)
def test_painter_internal_preflight_minimal_malformed_records_never_throw(
    document: dict,
) -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    report = _preflight_painter_umg_document(document)

    assert report["ok"] is False
    assert report["counts"] == EXPECTED_COUNTS
    assert report["blockers"][0]["reasons"] in (
        ["umg_layers_record_invalid"],
        ["umg_resource_record_invalid"],
    )


def test_painter_internal_preflight_rejects_resource_identity_aliases() -> None:
    from app.painter_ui_umg_adapter import _preflight_painter_umg_document

    document = _painter_document()
    document["Resources"] = [
        {
            "Id": "texture_duplicate",
            "Kind": "texture",
            "SourcePath": "missing-a.png",
            "DestinationName": "Same Name",
        },
        {
            "Id": "texture_duplicate",
            "Kind": "texture",
            "SourcePath": "missing-b.png",
            "DestinationName": "Same-Name",
        },
    ]

    report = _preflight_painter_umg_document(document)

    assert report["ok"] is False
    assert {
        "umg_resource_id_duplicate_or_empty",
        "umg_resource_destination_collision",
    } <= set(report["blockers"][0]["reasons"])
