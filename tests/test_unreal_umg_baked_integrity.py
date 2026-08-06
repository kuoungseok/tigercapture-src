from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest


def _document() -> dict:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    source = create_ui_document(320, 240)
    source["artboards"][0]["background"] = "#00000000"
    document, _ = add_ui_object(
        source,
        kind="path",
        x=60,
        y=45,
        width=40,
        height=30,
        content={
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {
                    "path": "M 0 30 L 20 0 L 40 30 Z",
                    "winding_rule": "nonzero",
                }
            ],
            "vector_paths": [{"path": "M 0 30 L 20 0 L 40 30 Z"}],
        },
        style={
            "fill": "#336699FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#336699FF",
                    "opacity": 0.5,
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
        },
    )
    row = document["objects"][0]
    row["rotation"] = 31.0
    row["constraints"] = capture_ui_constraints(
        row,
        {"x": 0.0, "y": 0.0, "width": 320.0, "height": 240.0},
        {"horizontal": "center", "vertical": "center", "pivot_x": 0.2, "pivot_y": 0.8},
    )
    return document


def _package(tmp_path: Path) -> dict:
    from app.painter_ui_umg_adapter import package_painter_umg

    package = package_painter_umg(_document(), tmp_path)
    assert package["ok"] is True
    return package


def _preflight(package: dict) -> dict:
    from app.unreal_umg_document import preflight_umg_document

    return preflight_umg_document(
        package["document"], document_path=package["document_path"]
    )


def test_valid_packaged_baked_requires_and_accepts_explicit_document_base(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    package = _package(tmp_path)
    assert _preflight(package)["ok"] is True
    unbased = preflight_umg_document(package["document"])
    assert unbased["ok"] is False
    assert "baked_resource_file_unverified" in unbased["blockers"][0]["reasons"]


def test_actual_png_bytes_are_hashed_not_trusted_from_declared_fields(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)
    source = tmp_path / package["document"]["Resources"][0]["SourcePath"]
    source.write_bytes(b"forged-png-bytes")
    report = _preflight(package)
    assert report["ok"] is False
    assert "baked_resource_file_hash_mismatch" in report["blockers"][0]["reasons"]


@pytest.mark.parametrize("schema", [True, 3, 17, 999, "13"])
def test_schema_version_outside_supported_integer_range_is_rejected(
    tmp_path: Path,
    schema: object,
) -> None:
    package = _package(tmp_path)
    package["document"]["SchemaVersion"] = schema
    assert _preflight(package)["ok"] is False


def test_schema13_static_vector_contract_remains_valid_inside_schema14_document(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)
    package["document"]["SchemaVersion"] = 14

    assert _preflight(package)["ok"] is True


def test_duplicate_resource_id_and_normalized_destination_are_rejected(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)
    duplicate = copy.deepcopy(package["document"]["Resources"][0])
    package["document"]["Resources"].append(duplicate)
    reasons = _preflight(package)["blockers"][0]["reasons"]
    assert "umg_resource_id_duplicate_or_empty" in reasons
    assert "umg_resource_destination_collision" in reasons

    package = _package(tmp_path / "collision")
    collision = copy.deepcopy(package["document"]["Resources"][0])
    collision["Id"] = "texture_distinct"
    package["document"]["Resources"].append(collision)
    reasons = _preflight(package)["blockers"][0]["reasons"]
    assert "umg_resource_destination_collision" in reasons


@pytest.mark.parametrize(
    "value", ["C:/escape/vector.png", "//server/vector.png", "a\\b.png", "../vector.png"]
)
def test_artifact_relative_paths_reject_drive_unc_backslash_and_traversal(
    tmp_path: Path,
    value: str,
) -> None:
    package = _package(tmp_path)
    layer = package["document"]["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    payload["static_vector_bake"]["png_path"] = value
    layer["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    assert "baked_png_path_invalid" in _preflight(package)["blockers"][0]["reasons"]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("size", "baked_layer_size_mismatch"),
        ("pivot", "baked_layout_expanded_pivot_mismatch"),
        ("position", "baked_layout_position_mismatch"),
        ("rotation", "baked_layout_rotation_mismatch"),
    ],
)
def test_materialized_layout_is_recomputed_not_trusted(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    package = _package(tmp_path)
    layer = package["document"]["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    bake = payload["static_vector_bake"]
    if mutation == "size":
        layer["Size"]["X"] += 1
    elif mutation == "pivot":
        bake["layout_adjustment"]["expanded_pivot"]["X"] += 0.1
    elif mutation == "position":
        bake["layout_adjustment"]["position_preserved"]["X"] += 1
    else:
        bake["layout_adjustment"]["rotation_degrees_preserved"] += 1
    layer["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    assert reason in _preflight(package)["blockers"][0]["reasons"]


@pytest.mark.parametrize(
    "path", ["M 0, L 10 0 L 10 10 Z", "M 0 0 L 10 0 Z m 1 1 l 2 0 z"]
)
def test_self_hashed_malformed_or_context_relative_source_is_rejected(
    tmp_path: Path,
    path: str,
) -> None:
    package = _package(tmp_path)
    layer = package["document"]["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    bake = payload["static_vector_bake"]
    bake["source"]["geometry"][0]["path"] = path
    bake["source"]["geometry_complexity"]["path_bytes"] = len(path.encode())
    bake["source_hash"] = hashlib.sha256(
        json.dumps(
            bake["source"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    layer["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    reasons = _preflight(package)["blockers"][0]["reasons"]
    assert "baked_static_vector_source_not_reproducible" in reasons


def test_resource_destination_settings_and_payload_mapping_are_exact(
    tmp_path: Path,
) -> None:
    package = _package(tmp_path)
    package["document"]["Resources"][0]["DestinationName"] = "TS_other"
    assert "baked_resource_destination_name_invalid" in _preflight(package)["blockers"][0]["reasons"]

    package = _package(tmp_path / "settings")
    package["document"]["Resources"][0]["SettingsJson"] = json.dumps(
        {"Usage": "ImageFill", "SRGB": True, "extra": True}
    )
    assert "baked_resource_settings_invalid" in _preflight(package)["blockers"][0]["reasons"]

    package = _package(tmp_path / "payload")
    layer = package["document"]["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    payload["umg_mapping"] = "forged"
    layer["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    assert "baked_payload_mapping_invalid" in _preflight(package)["blockers"][0]["reasons"]


def test_unreal_preflight_source_pins_materialized_bake_integrity_contract() -> None:
    source = Path(
        "resources/unreal_plugins/UMG/TigerStudioUMG/Source/"
        "TigerStudioUMGEditor/Private/TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")

    for contract in (
        "HashFileSha256",
        "AppendCanonicalJson",
        "baked_static_vector_source_hash_mismatch",
        "ValidateStaticVectorPathSyntax",
        'Tokens[Group + 3] != TEXT("0")',
        'Tokens[Group + 3] != TEXT("1")',
        "ActualSubpathIndices[ItemIndex].X",
        "ActualSubpathIndices[ItemIndex].Y",
        "ValidateStaticVectorPng",
        "baked_resource_png_contract_invalid",
        "umg_resource_destination_collision",
        "baked_resource_file_hash_mismatch",
        "baked_layout_adjustment_invalid",
        "baked_payload_contract_invalid",
    ):
        assert contract in source


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing_layers", "umg_layers_record_invalid"),
        ("layers_not_array", "umg_layers_record_invalid"),
        ("layer_not_object", "umg_layer_record_invalid"),
        ("disposition_missing", "umg_layer_disposition_invalid"),
        ("disposition_unknown", "umg_layer_disposition_invalid"),
        ("resources_not_array", "umg_resources_record_invalid"),
        ("resource_not_object", "umg_resource_record_invalid"),
    ],
)
def test_raw_document_records_never_silently_drop_invalid_rows(
    mutation: str,
    reason: str,
) -> None:
    from app.unreal_umg_document import preflight_umg_document

    document: dict = {"SchemaVersion": 13, "Layers": [], "Resources": []}
    if mutation == "missing_layers":
        document.pop("Layers")
    elif mutation == "layers_not_array":
        document["Layers"] = {}
    elif mutation == "layer_not_object":
        document["Layers"] = [None]
    elif mutation == "disposition_missing":
        document["Layers"] = [{"Id": "bad"}]
    elif mutation == "disposition_unknown":
        document["Layers"] = [{"Id": "bad", "Disposition": "Bogus"}]
    elif mutation == "resources_not_array":
        document["Resources"] = {}
    else:
        document["Resources"] = [None]

    report = preflight_umg_document(document)
    assert report["ok"] is False
    assert reason in {
        item
        for blocker in report["blockers"]
        for item in blocker["reasons"]
    }


def test_unreal_raw_record_gate_runs_before_defaults_and_deserialization() -> None:
    source = Path(
        "resources/unreal_plugins/UMG/TigerStudioUMG/Source/"
        "TigerStudioUMGEditor/Private/TigerStudioUMGImportSubsystem.cpp"
    ).read_text(encoding="utf-8")

    gate = source.index("ValidateRawDocumentRecords(DocumentObject)")
    assert gate < source.index("AddLegacyLayerDefaults(", gate)
    assert gate < source.index("FJsonObjectConverter::JsonObjectToUStruct", gate)
    for reason in (
        "umg_layers_record_invalid",
        "umg_layer_record_invalid",
        "umg_layer_disposition_invalid",
        "umg_resources_record_invalid",
        "umg_resource_record_invalid",
    ):
        assert reason in source
    for disposition in ("Native", "Material", "Baked", "Blocked"):
        assert f'Disposition == TEXT("{disposition}")' in source
