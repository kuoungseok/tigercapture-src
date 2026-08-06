from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile

import pytest


def _manifest_case(
    payload: bytes,
    *,
    relative_path: str = "sample/source.json",
    required_features: list[str] | None = None,
    preserve_features: list[str] | None = None,
) -> dict:
    commit = "1" * 40
    return {
        "schema": "tigercapture.painter.figma_document_corpus.v1",
        "cases": [
            {
                "id": "sample.case",
                "title": "Sample",
                "format": (
                    "figma_rest_archive"
                    if relative_path.endswith(".zip")
                    else "figma_rest_file"
                ),
                "source": {
                    "repository": "example/public-fixtures",
                    "commit": commit,
                    "path": "fixtures/source" + Path(relative_path).suffix,
                    "url": (
                        "https://raw.githubusercontent.com/example/public-fixtures/"
                        f"{commit}/fixtures/source{Path(relative_path).suffix}"
                    ),
                    "html_url": "https://github.com/example/public-fixtures",
                    "license": "MIT",
                    "license_url": "https://github.com/example/public-fixtures/blob/main/LICENSE",
                    "attribution": "Example compatibility fixture",
                },
                "artifact": {
                    "relative_path": relative_path,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                },
                "expectations": {
                    "min_artboards": 1,
                    "min_objects": 1,
                    "required_source_features": required_features or [],
                    "preserve_features": preserve_features or [],
                },
            }
        ],
    }


def _figma_payload() -> dict:
    return {
        "name": "Corpus fixture",
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "0:1",
                    "name": "Page",
                    "type": "CANVAS",
                    "children": [
                        {
                            "id": "1:1",
                            "name": "Card",
                            "type": "FRAME",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 320,
                                "height": 180,
                            },
                            "children": [
                                {
                                    "id": "1:2",
                                    "name": "Stack",
                                    "type": "FRAME",
                                    "layoutMode": "VERTICAL",
                                    "absoluteBoundingBox": {
                                        "x": 24,
                                        "y": 24,
                                        "width": 240,
                                        "height": 100,
                                    },
                                    "children": [
                                        {
                                            "id": "1:3",
                                            "name": "Title",
                                            "type": "TEXT",
                                            "characters": "Compatibility",
                                            "absoluteBoundingBox": {
                                                "x": 36,
                                                "y": 36,
                                                "width": 180,
                                                "height": 24,
                                            },
                                            "style": {
                                                "fontFamily": "Inter",
                                                "fontSize": 18,
                                            },
                                            "fills": [
                                                {
                                                    "type": "SOLID",
                                                    "color": {
                                                        "r": 0.1,
                                                        "g": 0.2,
                                                        "b": 0.3,
                                                    },
                                                }
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }


def _append_vector_fixture(payload: dict, *, complete: bool) -> None:
    frame = payload["document"]["children"][0]["children"][0]
    vector = {
        "id": "1:9",
        "name": "Exact triangle" if complete else "Arbitrary mark",
        "type": "VECTOR",
        "absoluteBoundingBox": {
            "x": 270,
            "y": 30,
            "width": 32,
            "height": 32,
        },
        "fills": [
            {
                "type": "SOLID",
                "color": {"r": 0.1, "g": 0.7, "b": 0.9},
            }
        ],
        "strokes": [],
    }
    if complete:
        vector.update(
            {
                "size": {"x": 32, "y": 32},
                "relativeTransform": [[1, 0, 270], [0, 1, 30]],
                "fillGeometry": [
                    {
                        "path": "M 0 32 L 16 0 L 32 32 Z",
                        "windingRule": "NONZERO",
                    }
                ],
                "strokeGeometry": [],
            }
        )
    frame["children"].append(vector)


def test_checked_in_figma_corpus_manifests_are_pinned_and_licensed() -> None:
    from tools.fetch_painter_ui_figma_document_corpus import (
        _read_manifest,
        validate_manifest,
    )

    root = Path(__file__).resolve().parents[1]
    paths = [
        root / "qa_corpus" / "painter_ui_figma_documents" / "manifest.json",
        root / "qa_corpus" / "painter_ui_figma_documents" / "nightly_manifest.json",
        root
        / "qa_corpus"
        / "painter_ui_figma_documents"
        / "release_manifest.json",
    ]
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    for manifest in manifests:
        validate_manifest(manifest)

    fast_cases = manifests[0]["cases"]
    nightly_cases = manifests[1]["cases"]
    release = manifests[2]
    assert len(fast_cases) == 20
    assert len(nightly_cases) == 4
    expanded_release = _read_manifest(paths[2])
    assert len(expanded_release["cases"]) == 100
    assert len(release["cases"]) == 78
    assert sum(
        int(case["selector"]["observed_nodes"])
        for case in release["cases"]
    ) == 7578
    assert sum(
        int(case["selector"]["observed_json_bytes"])
        for case in release["cases"]
    ) == 12_600_171
    assert len({case["source"]["repository"] for case in fast_cases}) >= 8
    assert {case["format"] for case in fast_cases} >= {
        "figma_rest_file",
        "figma_rest_nodes",
        "figma_rest_node_fragment",
    }
    assert any(case["format"] == "figma_rest_archive" for case in nightly_cases)
    assert all(case["source"]["license"] for case in fast_cases + nightly_cases)
    assert not any(
        "vector" in case.get("expectations", {}).get(
            "required_source_features", []
        )
        or "path" in case.get("expectations", {}).get(
            "preserve_features", []
        )
        for case in fast_cases + nightly_cases
    )
    assert sum(
        "vector_geometry_complete"
        in case.get("expectations", {}).get("required_source_features", [])
        for case in fast_cases + nightly_cases
    ) == 5
    assert sum(
        "figma_reaction"
        in case.get("expectations", {}).get("required_source_features", [])
        for case in fast_cases + nightly_cases
    ) == 3
    assert sum(
        "figma_reaction_recovery"
        in case.get("expectations", {}).get("preserve_features", [])
        for case in fast_cases + nightly_cases
    ) == 2
    assert sum(
        "component_property_binding"
        in case.get("expectations", {}).get(
            "required_source_features", []
        )
        for case in fast_cases + nightly_cases
    ) == 8
    assert sum(
        "component_property_binding_recovery"
        in case.get("expectations", {}).get("preserve_features", [])
        for case in fast_cases + nightly_cases
    ) == 4
    assert sum(
        "figma_variable_binding_alias"
        in case.get("expectations", {}).get(
            "required_source_features", []
        )
        for case in fast_cases + nightly_cases
    ) == 5
    assert sum(
        "figma_variable_binding_alias"
        in case.get("expectations", {}).get("preserve_features", [])
        for case in fast_cases + nightly_cases
    ) == 5


def test_release_manifest_rejects_overlap_semantic_duplicate_and_bad_include(
    tmp_path: Path,
) -> None:
    from tools.fetch_painter_ui_figma_document_corpus import (
        FigmaCorpusError,
        validate_manifest,
    )

    root = Path(__file__).resolve().parents[1]
    path = (
        root
        / "qa_corpus"
        / "painter_ui_figma_documents"
        / "release_manifest.json"
    )
    original = json.loads(path.read_text(encoding="utf-8"))

    overlap = json.loads(json.dumps(original))
    first = overlap["cases"][0]["selector"]
    second = overlap["cases"][1]["selector"]
    second["ancestry"] = [*first["ancestry"], second["node_id"]]
    second["ancestor_canvas_id"] = first["ancestor_canvas_id"]
    with pytest.raises(FigmaCorpusError, match="Overlapping selector"):
        validate_manifest(overlap)

    duplicate = json.loads(json.dumps(original))
    duplicate["cases"][1]["selector"]["semantic_sha256"] = duplicate[
        "cases"
    ][0]["selector"]["semantic_sha256"]
    with pytest.raises(FigmaCorpusError, match="semantic hash"):
        validate_manifest(duplicate)

    unsafe = json.loads(json.dumps(original))
    unsafe["includes"][0]["path"] = "../manifest.json"
    with pytest.raises(FigmaCorpusError, match="Unsafe corpus relative path"):
        validate_manifest(unsafe)


def test_release_manifest_matches_audited_builder_when_archives_available() -> None:
    from tools.build_painter_ui_figma_release_manifest import build_manifest

    root = Path(__file__).resolve().parents[1]
    manifest_path = (
        root
        / "qa_corpus"
        / "painter_ui_figma_documents"
        / "release_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest["source_artifacts"].values()
    assets_root = root / "external" / "assets" / "figma" / "compat_corpus"
    if not all(
        (assets_root / row["artifact"]["relative_path"]).is_file()
        for row in artifacts
    ):
        pytest.skip("selector source archives are not downloaded")

    assert build_manifest() == manifest


def test_figma_corpus_fetcher_verifies_hash_and_uses_cache(tmp_path: Path) -> None:
    from tools.fetch_painter_ui_figma_document_corpus import fetch_corpus

    payload = b'{"document": {}}'
    manifest = _manifest_case(payload)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return payload

    first = fetch_corpus(manifest_path, tmp_path / "assets", fetcher=fetch)
    second = fetch_corpus(
        manifest_path,
        tmp_path / "assets",
        fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("cache missed")),
    )

    assert first["downloaded_count"] == 1
    assert second["cached_count"] == 1
    assert len(calls) == 1
    assert (tmp_path / "assets" / "sample" / "source.json").read_bytes() == payload


def test_imported_inventory_counts_recovered_object_and_artboard_variables() -> None:
    from tools.qa_painter_ui_figma_document_corpus import imported_feature_inventory

    document = {
        "objects": [
            {
                "kind": "rectangle",
                "content": {
                    "figma_variable_bindings": [
                        {"id": "VariableID:native", "status": "native"},
                        {
                            "id": "VariableID:recovered",
                            "status": "recovered",
                        },
                        {
                            "id": "VariableID:unresolved",
                            "status": "unresolved",
                        },
                        {"id": "", "status": "blocked"},
                    ]
                },
            }
        ],
        "interactions": [],
        "sections": [],
        "components": [],
        "tokens": [],
        "linked_targets": {
            "figma": {
                "artboard_variable_bindings": [
                    {
                        "artboard_id": "artboard-1",
                        "id": "VariableID:artboard",
                        "status": "unresolved",
                    }
                ]
            }
        },
    }

    imported = imported_feature_inventory(document)
    assert imported["variable_bindings"] == 2
    assert imported["figma_variable_binding_alias"] == 5
    assert imported["figma_variable_binding_alias_object"] == 4
    assert imported["figma_variable_binding_alias_artboard"] == 1
    assert imported["figma_variable_binding_alias_native"] == 1
    assert imported["figma_variable_binding_alias_recovered"] == 1
    assert imported["figma_variable_binding_alias_unresolved"] == 2
    assert imported["figma_variable_binding_alias_blocked"] == 1


def test_source_inventory_counts_every_figma_variable_alias_slot() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        source_feature_inventory,
    )

    payload = _figma_payload()
    title = payload["document"]["children"][0]["children"][0][
        "children"
    ][0]["children"][0]
    title["boundVariables"] = {
        "fills": [
            {"type": "VARIABLE_ALIAS", "id": "VariableID:fill"},
            None,
            "malformed",
        ],
        "opacity": None,
        "visible": {"type": "VARIABLE_ALIAS"},
        "emptyPaintList": [],
    }

    source = source_feature_inventory(payload)["features"]

    assert source["variable_bindings"] == 1
    assert source["figma_variable_binding_alias"] == 5


def test_corpus_variable_binding_alias_slots_are_conserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tools.qa_painter_ui_figma_document_corpus as corpus

    payload = _figma_payload()
    frame = payload["document"]["children"][0]["children"][0]
    title = frame["children"][0]["children"][0]
    title["boundVariables"] = {
        "fills": [
            {"type": "VARIABLE_ALIAS", "id": "VariableID:text-fill"},
            None,
        ],
        "futureField": {
            "type": "VARIABLE_ALIAS",
            "id": "VariableID:future",
        },
        "opacity": "malformed",
    }
    frame["boundVariables"] = {
        "fills": [
            {"type": "VARIABLE_ALIAS", "id": "VariableID:artboard"},
            {},
        ]
    }

    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=[
            "variable_bindings",
            "figma_variable_binding_alias",
        ],
        preserve_features=[
            "variable_bindings",
            "figma_variable_binding_alias",
        ],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = corpus.run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
    )
    case = report["cases"][0]
    expected = {
        "status": "passed",
        "source_count": 6,
        "imported_count": 6,
        "import_report_count": 6,
        "object_count": 4,
        "artboard_count": 2,
        "native_count": 0,
        "recovered_count": 0,
        "unresolved_count": 2,
        "blocked_count": 4,
        "unclassified_count": 0,
    }

    assert report["passed"] is True, case["errors"]
    assert case["feature_evidence"][
        "figma_variable_binding_aliases"
    ] == expected
    assert report[
        "figma_variable_binding_alias_conservation"
    ] == expected

    real_inventory = corpus.imported_feature_inventory

    def lossy_inventory(document: dict) -> dict[str, int]:
        result = real_inventory(document)
        result["figma_variable_binding_alias"] -= 1
        return result

    monkeypatch.setattr(
        corpus,
        "imported_feature_inventory",
        lossy_inventory,
    )
    failed = corpus.run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "lossy-report",
    )
    assert failed["passed"] is False
    assert "figma_variable_binding_alias_count_not_conserved" in failed[
        "cases"
    ][0]["errors"]


def test_corpus_inventory_separates_geometry_paths_from_source_placeholders() -> None:
    from tools.qa_painter_ui_figma_document_corpus import source_feature_inventory

    payload = _figma_payload()
    _append_vector_fixture(payload, complete=False)
    frame = payload["document"]["children"][0]["children"][0]
    frame["children"].append(
        {
            "id": "1:10",
            "name": "Empty source placeholder",
            "type": "VECTOR",
            "absoluteBoundingBox": {
                "x": 270,
                "y": 70,
                "width": 32,
                "height": 32,
            },
            "fills": [],
            "strokes": [],
        }
    )
    frame["children"].append(
        {
            "id": "1:11",
            "name": "Boolean check",
            "type": "BOOLEAN_OPERATION",
            "size": {"x": 24, "y": 24},
            "relativeTransform": [[1, 0, 270], [0, 1, 110]],
            "absoluteBoundingBox": {
                "x": 270,
                "y": 110,
                "width": 24,
                "height": 24,
            },
            "fills": [{"type": "SOLID", "color": {"r": 1, "g": 0, "b": 0}}],
            "fillGeometry": [{"path": "M 0 0 H 24 V 24 H 0 Z"}],
            "children": [],
        }
    )

    inventory = source_feature_inventory(payload)
    geometry = inventory["vector_geometry"]

    assert inventory["features"]["path_geometry_complete"] == 1
    assert inventory["features"]["boolean_geometry_complete"] == 1
    assert inventory["features"]["source_incomplete_vector_geometry"] == 2
    assert (
        inventory["features"][
            "source_incomplete_vector_geometry_render_relevant"
        ]
        == 1
    )
    assert geometry["complete_count"] == 1
    assert geometry["source_incomplete_count"] == 2
    assert geometry["render_relevant_source_incomplete_count"] == 1
    assert geometry["source_incomplete_blocker_count"] == 1
    assert geometry["blockers"] == [
        {"reason": "source_incomplete_vector_geometry", "count": 1}
    ]

    empty_only_payload = _figma_payload()
    _append_vector_fixture(empty_only_payload, complete=False)
    empty_vector = empty_only_payload["document"]["children"][0]["children"][0][
        "children"
    ][-1]
    empty_vector["fills"] = []
    empty_geometry = source_feature_inventory(empty_only_payload)[
        "vector_geometry"
    ]
    assert empty_geometry["render_relevant_source_incomplete_count"] == 0
    assert empty_geometry["source_incomplete_blocker_count"] == 1
    assert empty_geometry["blockers"] == [
        {"reason": "source_incomplete_vector_geometry", "count": 1}
    ]


def test_corpus_inventory_measures_component_variant_semantics() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        imported_feature_inventory,
        source_feature_inventory,
    )

    payload = {
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "1:1",
                    "name": "Button",
                    "type": "COMPONENT_SET",
                    "componentPropertyDefinitions": {
                        "Label#1:2": {
                            "type": "TEXT",
                            "defaultValue": "Buy",
                        }
                    },
                    "children": [
                        {
                            "id": "1:2",
                            "name": "State=Default",
                            "type": "COMPONENT",
                            "variantProperties": {"State": "Default"},
                            "componentPropertyReferences": {
                                "characters": "Label#1:2"
                            },
                        },
                        {
                            "id": "1:3",
                            "name": "State=Pressed",
                            "type": "COMPONENT",
                            "variantProperties": {"State": "Pressed"},
                        },
                    ],
                }
            ],
        }
    }
    source = source_feature_inventory(payload)["features"]
    assert source["component_variant"] == 2
    assert source["component_property_definition"] == 1
    assert source["component_property_definition_text"] == 1
    assert source["component_property_binding"] == 1
    assert source["variant_property_value"] == 2

    document = {
        "objects": [
            {
                "kind": "frame",
                "component_role": "instance",
                "component_properties": {"Label": "Buy now"},
                "component_property_bindings": {"content.text": "Label"},
                "instance_overrides": {"content.text": "Buy now"},
                "content": {},
            }
        ],
        "components": [
            {
                "id": "component-default",
                "variant_ids": ["component-pressed"],
                "property_definitions": {
                    "Label": {"type": "text", "default": "Buy"}
                },
            },
            {
                "id": "component-pressed",
                "base_component_id": "component-default",
                "variant_ids": [],
                "property_definitions": {},
            },
        ],
        "interactions": [],
        "sections": [],
        "tokens": [],
        "linked_targets": {},
    }
    imported = imported_feature_inventory(document)
    assert imported["component_variant"] == 2
    assert imported["component_property_definition"] == 1
    assert imported["component_property_value"] == 1
    assert imported["component_property_binding"] == 1
    assert imported["component_property_binding_active"] == 1
    assert imported.get("component_property_binding_recovery", 0) == 0
    assert imported["component_instance_override"] == 1


def test_corpus_component_property_binding_slots_are_conserved(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    payload = _figma_payload()
    definition = payload["document"]["children"][0]["children"][0][
        "children"
    ][0]
    definition["type"] = "COMPONENT"
    definition["componentPropertyDefinitions"] = {
        "Label#1:2": {"type": "TEXT", "defaultValue": "Compatibility"},
        "Future#1:3": {"type": "TEXT", "defaultValue": "future"},
    }
    label = definition["children"][0]
    label["componentPropertyReferences"] = {
        "characters": "Label#1:2",
        "futureProperty": "Future#1:3",
    }

    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=["component_property_binding"],
        preserve_features=[
            "component_property_binding",
            "component_property_binding_recovery",
        ],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
    )
    case = report["cases"][0]

    expected = {
        "status": "passed",
        "source_count": 2,
        "active_count": 1,
        "recovered_count": 1,
    }
    assert report["passed"] is True, case["errors"]
    assert case["errors"] == []
    assert case["feature_evidence"][
        "figma_component_property_bindings"
    ] == expected
    assert report[
        "figma_component_property_binding_conservation"
    ] == expected
    assert case["imported_features"][
        "component_property_binding"
    ] == 2
    assert case["imported_features"][
        "component_property_binding_active"
    ] == 1
    assert case["imported_features"][
        "component_property_binding_recovery"
    ] == 1


def test_corpus_reaction_inventory_and_runner_enforce_lossless_conservation(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        run_corpus,
        source_feature_inventory,
    )

    payload = _figma_payload()
    source = payload["document"]["children"][0]["children"][0]["children"][0]
    source["reactions"] = [
        {
            "trigger": {"type": "ON_HOVER"},
            "actions": [
                {
                    "type": "NODE",
                    "destinationId": "1:3",
                    "navigation": "SCROLL_TO",
                },
                {"type": "URL", "url": "https://example.com"},
            ],
        }
    ]
    source_features = source_feature_inventory(payload)["features"]
    assert source_features["figma_reaction"] == 1
    assert source_features["figma_reaction_action"] == 2
    assert source_features["figma_reaction_trigger_on_hover"] == 1
    assert source_features["figma_reaction_navigation_scroll_to"] == 1
    assert source_features["figma_reaction_action_type_url"] == 1

    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=[
            "figma_reaction",
            "figma_reaction_trigger_on_hover",
            "figma_reaction_navigation_scroll_to",
            "figma_reaction_action_type_url",
        ],
        preserve_features=[
            "figma_reaction_native_action_scroll_to",
            "figma_reaction_recovery",
        ],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
    )
    case = report["cases"][0]

    assert report["passed"] is True
    assert case["errors"] == []
    assert case["feature_evidence"]["figma_reactions"] == {
        "status": "passed",
        "source_reaction_count": 1,
        "native_reaction_count": 0,
        "recovered_reaction_count": 1,
        "source_action_count": 2,
        "native_action_count": 1,
        "recovered_action_count": 1,
    }
    assert report["figma_reaction_conservation"] == {
        "status": "passed",
        "source_reaction_count": 1,
        "native_reaction_count": 0,
        "recovered_reaction_count": 1,
        "source_action_count": 2,
        "native_action_count": 1,
        "recovered_action_count": 1,
    }
    imported = case["imported_features"]
    assert imported["figma_reaction_native_action_scroll_to"] == 1
    assert imported["figma_reaction_recovery"] == 1


def test_figma_document_corpus_runner_imports_roundtrips_and_preflights(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=["text", "auto_layout"],
        preserve_features=["text", "auto_layout"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
        write_packages=True,
    )

    assert report["passed"] is True
    assert report["case_count"] == 1
    assert report["passed_count"] == 1
    assert report["cases"][0]["roundtrip_equal"] is True
    assert report["cases"][0]["import"]["object_count"] == 2
    assert report["cases"][0]["umg"]["counts"]["Native"] == 2
    assert report["options"] == {
        "write_packages": True,
        "require_umg_clean": False,
        "render_smoke": False,
        "render_smoke_width": 960,
        "render_smoke_height": 640,
        "render_smoke_max_objects": 0,
        "render_smoke_artboard_count": 4,
        "write_render_pngs": True,
    }
    assert report["cases"][0]["provenance"] == {
        "repository": "example/public-fixtures",
        "commit": "1" * 40,
        "path": "fixtures/source.json",
        "url": (
            "https://raw.githubusercontent.com/example/public-fixtures/"
            + "1" * 40
            + "/fixtures/source.json"
        ),
        "html_url": "https://github.com/example/public-fixtures",
        "license": "MIT",
        "license_url": (
            "https://github.com/example/public-fixtures/blob/main/LICENSE"
        ),
        "attribution": "Example compatibility fixture",
        "creator": "",
        "original_url": "",
        "license_evidence_url": "",
        "license_scope": "",
        "modifications": "",
    }
    assert (tmp_path / "report" / "report.json").is_file()
    assert Path(report["cases"][0]["package"]["exchange_path"]).is_file()


def test_geometry_complete_corpus_case_renders_roundtrips_and_plans_umg_bake(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    payload = _figma_payload()
    _append_vector_fixture(payload, complete=True)
    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=["vector_geometry_complete"],
        preserve_features=["path_geometry"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
        render_smoke=True,
        render_smoke_width=320,
        render_smoke_height=240,
    )

    case = report["cases"][0]
    assert report["passed"] is True
    assert report["vector_geometry_evidence_passed_count"] == 1
    assert report["source_quality_clean_count"] == 1
    assert case["roundtrip_equal"] is True
    assert case["render_smoke"]["status"] == "passed"
    assert case["source_features"]["vector_geometry_complete"] == 1
    assert case["imported_features"]["path_geometry"] == 1
    assert case["source_quality"] == {"clean": True, "blockers": []}
    assert case["feature_evidence"]["vector_geometry"] == {
        "status": "passed",
        "source_complete_count": 1,
        "source_incomplete_count": 0,
        "imported_path_geometry_count": 1,
    }
    assert case["umg"]["counts"]["Baked"] == 1
    assert (
        "figma_vector_geometry_requires_deterministic_bake"
        not in case["umg"]["blocker_reasons"]
    )


def test_source_incomplete_vector_is_not_counted_as_geometry_evidence(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    payload = _figma_payload()
    _append_vector_fixture(payload, complete=False)
    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=["vector_geometry_complete"],
        preserve_features=["path_geometry"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
    )

    case = report["cases"][0]
    assert report["passed"] is False
    assert report["vector_geometry_evidence_passed_count"] == 0
    assert report["source_incomplete_vector_geometry_case_count"] == 1
    assert report["source_incomplete_vector_geometry_blocked_case_count"] == 1
    assert report["source_blocker_reason_totals"] == {
        "source_incomplete_vector_geometry": 1
    }
    assert "required_source_feature_missing:vector_geometry_complete" in case[
        "errors"
    ]
    assert "import_feature_not_preserved:path_geometry" in case["errors"]
    assert case["source_quality"] == {
        "clean": False,
        "blockers": [
            {"reason": "source_incomplete_vector_geometry", "count": 1}
        ],
    }
    assert case["feature_evidence"]["vector_geometry"]["status"] == (
        "source_incomplete"
    )
    assert case["umg"]["blocker_reasons"][
        "figma_vector_source_geometry_missing"
    ] == 1


def test_corpus_preserves_source_geometry_evidence_when_umg_check_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import app.painter_ui_umg_adapter as umg_adapter
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    payload = _figma_payload()
    _append_vector_fixture(payload, complete=True)
    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=["vector_geometry_complete"],
        preserve_features=["path_geometry"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    class FailingSession:
        def __init__(self, _document) -> None:
            raise RuntimeError("downstream UMG probe failed")

    monkeypatch.setattr(
        umg_adapter,
        "PainterUMGConversionSession",
        FailingSession,
    )

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
    )

    case = report["cases"][0]
    assert report["passed"] is False
    assert case["errors"] == ["RuntimeError: downstream UMG probe failed"]
    assert case["source_features"]["vector_geometry_complete"] == 1
    assert case["imported_features"]["path_geometry"] == 1
    assert case["feature_evidence"]["vector_geometry"]["status"] == "passed"


def test_figma_document_corpus_render_smoke_uses_real_painter_overlay(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest = _manifest_case(encoded)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
        render_smoke=True,
        render_smoke_width=320,
        render_smoke_height=240,
    )

    smoke = report["cases"][0]["render_smoke"]
    assert report["passed"] is True
    assert report["render_smoke_attempted_count"] == 1
    assert report["render_smoke_passed_count"] == 1
    assert report["render_smoke_skipped_count"] == 0
    assert report["render_artboard_smoke_attempted_count"] == 1
    assert report["render_artboard_smoke_passed_count"] == 1
    assert report["render_artboard_smoke_failed_count"] == 0
    assert smoke["status"] == "passed"
    assert smoke["renderer"] == "PainterUIDesignOverlay.render(QImage)"
    assert smoke["fit_mode"] == "all"
    assert smoke["artboard_id"] == ""
    assert smoke["width"] == 320
    assert smoke["height"] == 240
    assert smoke["sampled_unique_color_count"] > 1
    assert smoke["sampled_non_background_pixel_count"] > 0
    assert smoke["content_diff_pixel_count"] >= smoke["minimum_content_diff_pixels"]
    assert smoke["content_diff_ratio"] > 0
    assert smoke["content_diff_bounds"] is not None
    assert len(smoke["pixel_sha256"]) == 64
    assert len(smoke["baseline_pixel_sha256"]) == 64
    assert smoke["pixel_sha256"] != smoke["baseline_pixel_sha256"]
    assert Path(smoke["png_path"]).is_file()
    assert smoke["png_bytes"] > 0
    assert Path(smoke["baseline_png_path"]).is_file()
    assert smoke["baseline_png_bytes"] > 0
    selection = smoke["artboard_selection"]
    assert selection["policy"] == "active_first_middle_last_then_even_sample"
    assert selection["requested_count"] == 4
    assert selection["effective_count_limit"] == 4
    assert selection["selected_count"] == 1
    assert selection["available_count"] == 1
    assert selection["budget_limited"] is False
    assert len(smoke["artboards"]) == 1
    focused = smoke["artboards"][0]
    assert focused["status"] == "passed"
    assert focused["fit_mode"] == "artboard"
    assert focused["active"] is True
    assert focused["selection_reasons"] == [
        "active",
        "first",
        "middle",
        "last",
    ]
    assert focused["content_diff_pixel_count"] >= focused[
        "minimum_content_diff_pixels"
    ]
    assert Path(focused["png_path"]).is_file()
    assert Path(focused["baseline_png_path"]).is_file()


def test_artboard_render_selection_covers_active_edges_and_middle() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        _focused_render_count,
        _select_artboards_for_render,
    )

    document = {
        "active_artboard_id": "artboard-b",
        "artboards": [
            {"id": f"artboard-{suffix}", "name": suffix.upper()}
            for suffix in ("a", "b", "c", "d", "e", "f")
        ],
    }

    selected = _select_artboards_for_render(document, 4)

    assert [row["artboard_id"] for row in selected] == [
        "artboard-b",
        "artboard-a",
        "artboard-d",
        "artboard-f",
    ]
    assert [row["artboard_index"] for row in selected] == [1, 0, 3, 5]
    assert _select_artboards_for_render(document, 0) == []
    # The aggregate pixel budget still permits one focused pair next to the
    # legacy whole-document pair at the largest supported render size.
    assert _focused_render_count(
        width=4096,
        height=4096,
        requested_count=4,
    ) == 1


def test_figma_document_corpus_render_smoke_can_skip_large_documents(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest = _manifest_case(encoded)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
        render_smoke=True,
        render_smoke_max_objects=1,
    )

    smoke = report["cases"][0]["render_smoke"]
    assert report["passed"] is True
    assert report["render_smoke_attempted_count"] == 0
    assert report["render_smoke_passed_count"] == 0
    assert report["render_smoke_skipped_count"] == 1
    assert report["render_artboard_smoke_attempted_count"] == 0
    assert report["render_artboard_smoke_passed_count"] == 0
    assert report["render_artboard_smoke_failed_count"] == 0
    assert smoke == {
        "status": "skipped",
        "passed": None,
        "reason": "object_limit_exceeded",
        "object_count": 2,
        "max_objects": 1,
        "artboard_selection": {
            "status": "skipped",
            "reason": "object_limit_exceeded",
            "requested_count": 4,
            "selected_count": 0,
            "available_count": 1,
        },
        "artboards": [],
    }


def test_render_smoke_rejects_object_document_matching_empty_baseline(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from tools.qa_painter_ui_figma_document_corpus import render_document_smoke

    document = create_ui_document(320, 180)
    document["artboards"][0]["name"] = "Visible fixture"
    document, _row = add_ui_object(
        document,
        kind="rectangle",
        x=20,
        y=20,
        width=80,
        height=60,
        style={
            "fill": "#00000000",
            "stroke": "#00000000",
            "stroke_width": 0,
        },
    )

    smoke = render_document_smoke(
        document,
        width=320,
        height=240,
        png_path=tmp_path / "transparent.png",
    )

    assert smoke["status"] == "content_missing"
    assert smoke["passed"] is False
    assert smoke["object_count"] == 1
    assert smoke["content_diff_pixel_count"] == 0
    assert smoke["sampled_content_diff_pixel_count"] == 0
    assert smoke["content_diff_bounds"] is None


def test_figma_archive_corpus_resolves_bundled_image_refs(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    image_ref = "a" * 40
    payload = _figma_payload()
    stack = payload["document"]["children"][0]["children"][0]["children"][0]
    stack["children"] = [
        {
            "id": "1:4",
            "name": "Bundled image",
            "type": "RECTANGLE",
            "absoluteBoundingBox": {"x": 36, "y": 36, "width": 64, "height": 64},
            "fills": [
                {"type": "IMAGE", "imageRef": image_ref, "scaleMode": "FILL"}
            ],
        }
    ]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fixture/document.json", json.dumps(payload))
        archive.writestr(
            f"fixture/images/{image_ref}.png",
            b"\x89PNG\r\n\x1a\ncompatibility-fixture",
        )
    encoded = buffer.getvalue()
    manifest = _manifest_case(
        encoded,
        relative_path="sample/source.zip",
        required_features=["image_fill"],
        preserve_features=["image_fill"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.zip"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)
    stale_image = source_path.parent / "extracted" / "images" / f"{image_ref}.png"
    stale_image.parent.mkdir(parents=True)
    archived_image = b"\x89PNG\r\n\x1a\ncompatibility-fixture"
    stale_image.write_bytes(b"x" * len(archived_image))

    report = run_corpus(manifest_path, tmp_path / "assets", tmp_path / "report")

    case = report["cases"][0]
    assert report["passed"] is True
    assert case["source_details"]["extracted_image_count"] == 1
    assert case["import"]["resources"]["missing_image_count"] == 0
    assert stale_image.read_bytes() == archived_image
    # The image source itself is resolved.  A Fill image inside an Auto Layout
    # panel still needs TigerStudioUMG's dynamic UV binding and must remain an
    # explicit preflight blocker until that runtime path is implemented.
    assert case["umg"]["counts"] == {
        "Baked": 0,
        "Blocked": 1,
        "Material": 0,
        "Native": 1,
    }
    assert case["umg"]["blocker_reasons"] == {
        "image_fill_runtime_resize_requires_dynamic_uv_binding": 1,
    }


def test_figma_corpus_rejects_image_refs_without_source_assets(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    payload = _figma_payload()
    stack = payload["document"]["children"][0]["children"][0]["children"][0]
    stack["children"] = [
        {
            "id": "1:4",
            "name": "Missing image",
            "type": "RECTANGLE",
            "absoluteBoundingBox": {"x": 36, "y": 36, "width": 64, "height": 64},
            "fills": [
                {"type": "IMAGE", "imageRef": "missing-image", "scaleMode": "FILL"}
            ],
        }
    ]
    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(
        encoded,
        required_features=["image_fill"],
        preserve_features=["image_fill"],
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(manifest_path, tmp_path / "assets", tmp_path / "report")

    case = report["cases"][0]
    assert report["passed"] is False
    assert case["import"]["resources"]["missing_image_count"] == 1
    assert "source_image_assets_missing:1" in case["errors"]


def test_figma_corpus_rejects_image_paints_without_refs(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    payload = _figma_payload()
    stack = payload["document"]["children"][0]["children"][0]["children"][0]
    stack["children"] = [
        {
            "id": "1:4",
            "name": "Missing image reference",
            "type": "RECTANGLE",
            "absoluteBoundingBox": {"x": 36, "y": 36, "width": 64, "height": 64},
            "fills": [{"type": "IMAGE", "imageRef": None, "scaleMode": "FILL"}],
        }
    ]
    encoded = json.dumps(payload).encode("utf-8")
    manifest = _manifest_case(encoded, required_features=["image_fill"])
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)

    report = run_corpus(manifest_path, tmp_path / "assets", tmp_path / "report")

    case = report["cases"][0]
    assert report["passed"] is False
    assert case["source_features"]["image_fill_missing_ref"] == 1
    assert "source_image_refs_missing:1" in case["errors"]


@pytest.mark.parametrize(
    ("corrupt", "expected_error"),
    [
        (lambda payload: payload + b"\n", "artifact_size_mismatch"),
        (lambda payload: b"!" + payload[1:], "artifact_sha256_mismatch"),
    ],
)
def test_figma_corpus_reverifies_artifact_before_loading(
    tmp_path: Path,
    monkeypatch,
    corrupt,
    expected_error: str,
) -> None:
    import tools.qa_painter_ui_figma_document_corpus as corpus_tool

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest = _manifest_case(encoded)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(corrupt(encoded))

    def reject_unverified_load(_path):
        raise AssertionError("unverified artifact reached the parser")

    monkeypatch.setattr(corpus_tool, "_load_case_source", reject_unverified_load)
    report = corpus_tool.run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
    )

    assert report["passed"] is False
    assert expected_error in report["cases"][0]["errors"][0]


def test_figma_archive_rejects_duplicate_image_stems(tmp_path: Path) -> None:
    from tools.qa_painter_ui_figma_document_corpus import _load_case_source

    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("fixture/document.json", json.dumps(_figma_payload()))
        archive.writestr("fixture/images/shared.png", b"png")
        archive.writestr("fixture/images/shared.jpg", b"jpg")

    with pytest.raises(ValueError, match="duplicate image stem"):
        _load_case_source(archive_path)


def test_selector_loader_verifies_subtree_and_extracts_only_image_closure(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        _load_selector_case_source,
        _selector_canonical_bytes,
        _selector_semantic_value,
    )

    selected = {
        "id": "2:1",
        "name": "Selected frame",
        "type": "FRAME",
        "absoluteBoundingBox": {"x": 10, "y": 20, "width": 100, "height": 80},
        "children": [
            {
                "id": "2:2",
                "name": "Selected image",
                "type": "RECTANGLE",
                "absoluteBoundingBox": {
                    "x": 10,
                    "y": 20,
                    "width": 50,
                    "height": 40,
                },
                "fills": [{"type": "IMAGE", "imageRef": "selected"}],
            }
        ],
    }
    payload = {
        "name": "Selector fixture",
        "document": {
            "id": "0:0",
            "name": "Document",
            "type": "DOCUMENT",
            "children": [
                {
                    "id": "1:1",
                    "name": "Page",
                    "type": "CANVAS",
                    "children": [selected],
                }
            ],
        },
    }
    archive_path = tmp_path / "source.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("fixture/document.json", json.dumps(payload))
        archive.writestr("fixture/images/selected.png", b"selected-bytes")
        archive.writestr("fixture/images/not-selected.png", b"unused-bytes")
    encoded = archive_path.read_bytes()
    exact = _selector_canonical_bytes(selected)
    semantic = _selector_canonical_bytes(_selector_semantic_value(selected))
    selector = {
        "kind": "node_subtree",
        "node_id": "2:1",
        "ancestor_canvas_id": "1:1",
        "ancestry": ["0:0", "1:1", "2:1"],
        "expected_type": "FRAME",
        "expected_name": "Selected frame",
        "subtree_sha256": hashlib.sha256(exact).hexdigest(),
        "semantic_sha256": hashlib.sha256(semantic).hexdigest(),
        "observed_nodes": 2,
        "observed_json_bytes": len(exact),
        "wrapper": "promote_to_original_canvas",
    }
    artifact = {
        "relative_path": "source.zip",
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }

    wrapped, image_paths, details, evidence = _load_selector_case_source(
        archive_path,
        artifact,
        selector,
        {},
    )

    assert wrapped["document"]["children"][0]["children"] == [selected]
    assert set(image_paths) == {"selected"}
    assert Path(image_paths["selected"]).read_bytes() == b"selected-bytes"
    assert "not-selected" not in image_paths
    assert details["kind"] == "figma_rest_archive_selector"
    assert evidence["selector"]["observed_nodes"] == 2


def _synthetic_performance_report(
    value_ns: object,
    *,
    case_ids: list[str] | None = None,
    options: dict | None = None,
    profile: dict | None = None,
    artifact_sha256: str = "a" * 64,
    sample_count: int | None = None,
) -> dict:
    from tools.qa_painter_ui_figma_document_corpus import (
        _performance_workload_identity,
    )

    resolved_case_ids = case_ids or ["case-a"]
    case_total = (
        value_ns
        if isinstance(value_ns, int)
        and not isinstance(value_ns, bool)
        and value_ns >= 0
        else 100
    )
    quotient, remainder = divmod(case_total, len(resolved_case_ids))
    case_durations = [
        quotient + (1 if index < remainder else 0)
        for index in range(len(resolved_case_ids))
    ]
    cases = [
        {
            "id": case_id,
            "format": "figma_rest_file",
            "artifact": {
                "sha256": artifact_sha256,
                "bytes": 1234,
            },
            "provenance": {
                "commit": "b" * 40,
                "path": f"fixtures/{case_id}.json",
            },
            "performance": {
                "phases": {
                    "load": {
                        "status": "measured",
                        "duration_ns": duration_ns,
                    },
                    "scan": {"status": "measured", "duration_ns": 0},
                    "import": {"status": "measured", "duration_ns": 0},
                    "roundtrip": {
                        "status": "measured",
                        "duration_ns": 0,
                    },
                    "preflight": {
                        "status": "measured",
                        "duration_ns": 0,
                    },
                    "package": {
                        "status": "not_applicable",
                        "duration_ns": None,
                    },
                    "render": {
                        "status": "not_applicable",
                        "duration_ns": None,
                    },
                },
                "non_render_core": {
                    "status": "measured",
                    "duration_ns": duration_ns,
                    "included_phases": [
                        "load",
                        "scan",
                        "import",
                        "roundtrip",
                        "preflight",
                    ],
                    "excluded_phases": ["render"],
                },
            },
        }
        for case_id, duration_ns in zip(
            resolved_case_ids,
            case_durations,
            strict=True,
        )
    ]
    return {
        "schema": "tigercapture.painter.figma_document_corpus_report.v1",
        "case_count": len(cases),
        "cases": cases,
        "performance": {
            "schema": (
                "tigercapture.painter.figma_document_corpus_performance.v2"
            ),
            "measurement_status": "measured",
            "case_ids": resolved_case_ids,
            "workload": _performance_workload_identity(cases),
            "options": options or {"render_smoke": False},
            "profile": profile or {
                "schema": (
                    "tigercapture.painter.figma_document_corpus_perf_profile.v2"
                ),
                "machine": {"node_sha256": "same-machine"},
                "measurement": {
                    "metric_version": "total_case_non_render_core_ns.v2"
                },
            },
            "metric": {
                "name": "total_case_non_render_core_ns",
                "status": "measured",
                "value_ns": value_ns,
                "sample_count": (
                    len(resolved_case_ids)
                    if sample_count is None
                    else sample_count
                ),
            },
        }
    }


@pytest.mark.parametrize("current_ns", [100, 115])
def test_performance_ratchet_accepts_equal_and_exact_15_percent_boundary(
    current_ns: float,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    result = compare_performance_reports(
        _synthetic_performance_report(current_ns),
        _synthetic_performance_report(100),
    )

    assert result["status"] == "passed"
    assert result["max_regression_percent"] == 15.0


def test_performance_ratchet_rejects_more_than_15_percent() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    result = compare_performance_reports(
        _synthetic_performance_report(1_150_001),
        _synthetic_performance_report(1_000_000),
    )

    assert result["status"] == "failed"
    assert result["error"] == "performance_regression_exceeded"


@pytest.mark.parametrize(
    ("current", "expected_reason"),
    [
        (
            _synthetic_performance_report(100, case_ids=["case-b"]),
            "case_ids_mismatch",
        ),
        (
            _synthetic_performance_report(
                100, options={"render_smoke": True}
            ),
            "options_mismatch",
        ),
        (
            _synthetic_performance_report(
                100,
                profile={
                    "schema": (
                        "tigercapture.painter.figma_document_corpus_perf_profile.v2"
                    ),
                    "machine": {"node_sha256": "different-machine"},
                    "measurement": {
                        "metric_version": (
                            "total_case_non_render_core_ns.v2"
                        )
                    },
                },
            ),
            "profile_mismatch",
        ),
    ],
)
def test_performance_ratchet_refuses_incomparable_reports(
    current: dict,
    expected_reason: str,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    result = compare_performance_reports(
        current,
        _synthetic_performance_report(100),
    )

    assert result["status"] == "not_comparable"
    assert expected_reason in result["reasons"]


def test_performance_measurement_without_baseline_is_not_enforced() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    result = compare_performance_reports(
        _synthetic_performance_report(100),
        None,
    )

    assert result == {
        "status": "not_enforced",
        "reason": "performance_baseline_not_provided",
        "max_regression_percent": 15.0,
    }


def test_performance_ratchet_refuses_changed_artifact_with_same_case_id() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    current = _synthetic_performance_report(
        100,
        artifact_sha256="c" * 64,
    )
    baseline = _synthetic_performance_report(
        100,
        artifact_sha256="a" * 64,
    )

    result = compare_performance_reports(current, baseline)

    assert result["status"] == "not_comparable"
    assert "workload_mismatch" in result["reasons"]


def test_performance_ratchet_requires_full_report_not_timing_fragment() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    current = _synthetic_performance_report(100)
    baseline = _synthetic_performance_report(100)
    baseline = {"performance": baseline["performance"]}

    result = compare_performance_reports(current, baseline)

    assert result["status"] == "not_comparable"
    assert "full_report_schema_mismatch" in result["reasons"]
    assert "corpus_cases_missing" in result["reasons"]


@pytest.mark.parametrize("bad_value", ["oops", True, 1.25, -1])
def test_performance_ratchet_rejects_malformed_metric_without_exception(
    bad_value: object,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    result = compare_performance_reports(
        _synthetic_performance_report(bad_value),
        _synthetic_performance_report(100),
    )

    assert result["status"] == "not_comparable"
    assert "metric_value_invalid" in result["reasons"]


def test_performance_ratchet_requires_metric_sample_count_to_match_cases() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    result = compare_performance_reports(
        _synthetic_performance_report(100, sample_count=0),
        _synthetic_performance_report(100),
    )

    assert result["status"] == "not_comparable"
    assert "metric_sample_count_mismatch" in result["reasons"]


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("empty_cases", "current_corpus_cases_invalid"),
        ("null_case", "current_corpus_cases_invalid"),
        ("empty_case_id", "current_case_ids_invalid"),
        ("empty_performance_case_ids", "current_performance_case_ids_invalid"),
        ("tampered_case_count", "current_case_count_invalid"),
        ("garbage_performance_schema", "performance_schema_mismatch"),
    ],
)
def test_performance_ratchet_rejects_malformed_full_report_boundaries(
    mutation: str,
    expected_reason: str,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    current = _synthetic_performance_report(100)
    baseline = _synthetic_performance_report(100)
    if mutation == "empty_cases":
        current["cases"] = []
        current["case_count"] = 0
        current["performance"]["case_ids"] = []
        baseline["cases"] = []
        baseline["case_count"] = 0
        baseline["performance"]["case_ids"] = []
    elif mutation == "null_case":
        current["cases"] = [None]
    elif mutation == "empty_case_id":
        current["cases"][0]["id"] = ""
    elif mutation == "empty_performance_case_ids":
        current["performance"]["case_ids"] = []
    elif mutation == "tampered_case_count":
        current["case_count"] = 2
    elif mutation == "garbage_performance_schema":
        current["performance"]["schema"] = "garbage"
        baseline["performance"]["schema"] = "garbage"

    result = compare_performance_reports(current, baseline)

    assert result["status"] == "not_comparable"
    assert expected_reason in result["reasons"]


def test_performance_ratchet_rejects_exact_100_case_metric_inflation() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    case_ids = [f"case-{index:03d}" for index in range(100)]
    current = _synthetic_performance_report(100, case_ids=case_ids)
    baseline = _synthetic_performance_report(100, case_ids=case_ids)
    baseline["performance"]["metric"]["value_ns"] *= 100

    result = compare_performance_reports(current, baseline)

    assert result["status"] == "not_comparable"
    assert "baseline_case_metric_sum_mismatch" in result["reasons"]


def test_performance_ratchet_requires_measured_top_level_status_on_both_reports() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    current = _synthetic_performance_report(100)
    baseline = _synthetic_performance_report(100)
    current["performance"]["measurement_status"] = "incomplete"
    baseline["performance"]["measurement_status"] = "incomplete"

    result = compare_performance_reports(current, baseline)

    assert result["status"] == "not_comparable"
    assert "current_measurement_status_invalid" in result["reasons"]
    assert "baseline_measurement_status_invalid" in result["reasons"]


def test_performance_ratchet_requires_every_case_measurement_on_both_reports() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    case_ids = ["case-a", "case-b"]
    current = _synthetic_performance_report(100, case_ids=case_ids)
    baseline = _synthetic_performance_report(100, case_ids=case_ids)
    del current["cases"][0]["performance"]
    del baseline["cases"][0]["performance"]

    result = compare_performance_reports(current, baseline)

    assert result["status"] == "not_comparable"
    assert "current_case_performance_invalid" in result["reasons"]
    assert "baseline_case_performance_invalid" in result["reasons"]


def test_performance_ratchet_recomputes_core_duration_from_included_phases() -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    current = _synthetic_performance_report(100)
    current["cases"][0]["performance"]["phases"]["load"][
        "duration_ns"
    ] = 99

    result = compare_performance_reports(
        current,
        _synthetic_performance_report(100),
    )

    assert result["status"] == "not_comparable"
    assert "current_case_core_duration_mismatch" in result["reasons"]


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    [
        ("core", "current_case_non_render_core_invalid"),
        ("phase", "current_case_core_phases_invalid"),
    ],
)
def test_performance_ratchet_rejects_boolean_case_durations(
    field: str,
    expected_reason: str,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
    )

    current = _synthetic_performance_report(100)
    if field == "core":
        current["cases"][0]["performance"]["non_render_core"][
            "duration_ns"
        ] = True
    else:
        current["cases"][0]["performance"]["phases"]["load"][
            "duration_ns"
        ] = True

    result = compare_performance_reports(
        current,
        _synthetic_performance_report(100),
    )

    assert result["status"] == "not_comparable"
    assert expected_reason in result["reasons"]


def test_performance_primary_total_catches_large_case_hidden_by_median() -> None:
    from tools.qa_painter_ui_figma_document_corpus import _aggregate_performance

    phases = (
        "load",
        "scan",
        "import",
        "roundtrip",
        "preflight",
        "package",
        "render",
    )

    def rows(durations: list[int]) -> list[dict]:
        result = []
        for index, duration_ns in enumerate(durations):
            phase_rows = {
                phase: {
                    "status": (
                        "not_applicable"
                        if phase in {"package", "render"}
                        else "measured"
                    ),
                    "duration_ns": duration_ns if phase == "load" else 0,
                    "invocation_count": 1 if phase == "load" else 0,
                }
                for phase in phases
            }
            phase_rows["package"]["duration_ns"] = None
            phase_rows["render"]["duration_ns"] = None
            result.append(
                {
                    "id": f"case-{index}",
                    "performance": {
                        "phases": phase_rows,
                        "non_render_core": {
                            "status": "measured",
                            "duration_ns": duration_ns,
                        },
                    },
                }
            )
        return result

    baseline = _aggregate_performance(
        rows([10, 10, 1000]),
        case_ids=["case-0", "case-1", "case-2"],
        options={"render_smoke": False},
        profile={"machine": "same"},
    )
    current = _aggregate_performance(
        rows([10, 10, 1200]),
        case_ids=["case-0", "case-1", "case-2"],
        options={"render_smoke": False},
        profile={"machine": "same"},
    )

    assert baseline["metric"]["diagnostic_median_case_ns"] == 10
    assert current["metric"]["diagnostic_median_case_ns"] == 10
    assert baseline["metric"]["value_ns"] == 1020
    assert current["metric"]["value_ns"] == 1220


def test_case_phase_timing_accumulates_render_invocations_and_keeps_error() -> None:
    from tools.qa_painter_ui_figma_document_corpus import _CasePhaseTimings

    values = iter([0, 10, 10, 30, 30, 45])
    timings = _CasePhaseTimings(lambda: next(values))
    with timings.measure("render"):
        pass
    with timings.measure("render"):
        pass
    with pytest.raises(RuntimeError, match="render failed"):
        with timings.measure("render"):
            raise RuntimeError("render failed")

    render = timings.report()["phases"]["render"]
    assert render == {
        "status": "error",
        "duration_ns": 45,
        "invocation_count": 3,
    }


def test_run_corpus_injected_clock_reports_all_core_phases_and_no_enforcement(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import (
        compare_performance_reports,
        run_corpus,
    )

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_case(encoded)), encoding="utf-8"
    )
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)
    values = iter([0, 10, 10, 30, 30, 60, 60, 100, 100, 150])

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "report",
        clock_ns=lambda: next(values),
    )

    timing = report["cases"][0]["performance"]
    assert {
        phase: timing["phases"][phase]["duration_ns"]
        for phase in ("load", "scan", "import", "roundtrip", "preflight")
    } == {
        "load": 10,
        "scan": 20,
        "import": 30,
        "roundtrip": 40,
        "preflight": 50,
    }
    assert timing["phases"]["package"] == {
        "status": "not_applicable",
        "duration_ns": None,
        "invocation_count": 0,
    }
    assert timing["non_render_core"]["status"] == "measured"
    assert timing["non_render_core"]["duration_ns"] == 150
    assert timing["clock"] == "injected_test_clock"
    assert report["performance"]["profile"]["measurement"]["clock"] == (
        "injected_test_clock"
    )
    assert report["performance"]["metric"]["value_ns"] == 150
    assert report["performance"]["comparison"]["status"] == "not_enforced"
    assert report["errors"] == []
    assert report["passed"] is True

    production = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "production-report",
    )
    comparison = compare_performance_reports(production, report)
    assert comparison["status"] == "not_comparable"
    assert "profile_mismatch" in comparison["reasons"]


def test_run_corpus_fails_when_baseline_is_not_comparable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import tools.qa_painter_ui_figma_document_corpus as corpus

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_case(encoded)), encoding="utf-8"
    )
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)
    baseline = corpus.run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "baseline-output",
    )
    baseline["performance"]["profile"]["machine"]["node_sha256"] = (
        "different-machine"
    )
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    cli_output = tmp_path / "cli-output"
    monkeypatch.setattr(
        "sys.argv",
        [
            "qa_painter_ui_figma_document_corpus.py",
            "--manifest",
            str(manifest_path),
            "--assets-root",
            str(tmp_path / "assets"),
            "--output",
            str(cli_output),
            "--performance-baseline",
            str(baseline_path),
        ],
    )

    assert corpus.main() == 1
    report = json.loads((cli_output / "report.json").read_text(encoding="utf-8"))
    assert report["performance"]["comparison"]["status"] == "not_comparable"
    assert report["errors"] == ["performance_baseline_not_comparable"]
    assert report["passed"] is False


def test_run_corpus_adds_stable_error_for_comparable_regression(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    encoded = json.dumps(_figma_payload()).encode("utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(_manifest_case(encoded)), encoding="utf-8"
    )
    source_path = tmp_path / "assets" / "sample" / "source.json"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(encoded)
    baseline_values = iter([0, 10, 10, 20, 20, 30, 30, 40, 40, 50])
    baseline = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "baseline-output",
        clock_ns=lambda: next(baseline_values),
    )
    current_values = iter([0, 12, 12, 24, 24, 36, 36, 48, 48, 60])

    report = run_corpus(
        manifest_path,
        tmp_path / "assets",
        tmp_path / "current-output",
        performance_baseline=baseline,
        clock_ns=lambda: next(current_values),
    )

    assert report["performance"]["metric"]["value_ns"] == 60
    assert report["performance"]["comparison"]["status"] == "failed"
    assert report["errors"] == ["performance_regression_exceeded"]
    assert report["passed"] is False


def test_downloaded_fast_figma_corpus_runs_when_available(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = (
        root / "qa_corpus" / "painter_ui_figma_documents" / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets_root = root / "external" / "assets" / "figma" / "compat_corpus"
    if not all(
        (assets_root / Path(case["artifact"]["relative_path"])).is_file()
        for case in manifest["cases"]
    ):
        pytest.skip("public Figma document corpus is not downloaded")

    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    report = run_corpus(manifest_path, assets_root, tmp_path)

    assert report["case_count"] == 20
    assert report["passed"] is True
    assert report["passed_count"] == 20
    assert all(
        int(case["import"]["resources"]["missing_image_count"]) == 0
        for case in report["cases"]
    )
    assert report[
        "figma_component_property_binding_conservation"
    ] == {
        "status": "passed",
        "source_count": 112,
        "active_count": 95,
        "recovered_count": 17,
    }
    assert report[
        "figma_variable_binding_alias_conservation"
    ] == {
        "status": "passed",
        "source_count": 145,
        "imported_count": 145,
        "import_report_count": 145,
        "object_count": 144,
        "artboard_count": 1,
        "native_count": 0,
        "recovered_count": 0,
        "unresolved_count": 101,
        "blocked_count": 44,
        "unclassified_count": 0,
    }


def test_downloaded_release_100_case_corpus_runs_when_available(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[1]
    manifest_path = (
        root
        / "qa_corpus"
        / "painter_ui_figma_documents"
        / "release_manifest.json"
    )
    from tools.fetch_painter_ui_figma_document_corpus import _read_manifest

    manifest = _read_manifest(manifest_path)
    assets_root = root / "external" / "assets" / "figma" / "compat_corpus"
    if not all(
        (assets_root / Path(case["artifact"]["relative_path"])).is_file()
        for case in manifest["cases"]
    ):
        pytest.skip("release Figma corpus is not downloaded")

    from tools.qa_painter_ui_figma_document_corpus import run_corpus

    report = run_corpus(manifest_path, assets_root, tmp_path)

    assert report["case_count"] == 100
    assert report["passed"] is True
    assert report["passed_count"] == 100
    assert report["coverage"]["status"] == "passed"
    assert report["coverage"]["actual_selector_case_count"] == 78
    assert report["coverage"]["actual_selector_nodes"] == 7578
    assert report["coverage"]["actual_missing_image_count"] == 0
