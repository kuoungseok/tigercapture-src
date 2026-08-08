from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import urllib.parse

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODERN_EFFECT_MANIFEST = (
    ROOT / "qa_corpus" / "painter_ui_figma_modern_effects" / "manifest.json"
)


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _modern_effect_payload() -> dict:
    return {
        "name": "Modern effects",
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
                            "name": "Board",
                            "absoluteBoundingBox": {
                                "x": 0,
                                "y": 0,
                                "width": 320,
                                "height": 240,
                            },
                            "backgrounds": [
                                {
                                    "type": "SOLID",
                                    "color": {"r": 1, "g": 1, "b": 1},
                                }
                            ],
                            "children": [
                                {
                                    "id": "2:1",
                                    "type": "RECTANGLE",
                                    "name": "Effect card",
                                    "absoluteBoundingBox": {
                                        "x": 40,
                                        "y": 50,
                                        "width": 180,
                                        "height": 110,
                                    },
                                    "fills": [
                                        {
                                            "type": "SOLID",
                                            "color": {
                                                "r": 0.2,
                                                "g": 0.3,
                                                "b": 0.4,
                                            },
                                        }
                                    ],
                                    "effects": [
                                        {
                                            "type": "LAYER_BLUR",
                                            "blurType": "PROGRESSIVE",
                                            "radius": 24,
                                            "startRadius": 2,
                                            "startOffset": {"x": 0.1, "y": 0.2},
                                            "endOffset": {"x": 0.8, "y": 0.9},
                                            "visible": True,
                                        },
                                        {
                                            "type": "BACKGROUND_BLUR",
                                            "blurType": "PROGRESSIVE",
                                            "radius": 18,
                                            "startRadius": 1,
                                            "startOffset": {"x": 0.0, "y": 0.0},
                                            "endOffset": {"x": 1.0, "y": 1.0},
                                            "visible": True,
                                        },
                                        {
                                            "type": "NOISE",
                                            "color": {
                                                "r": 0.1,
                                                "g": 0.2,
                                                "b": 0.3,
                                                "a": 0.75,
                                            },
                                            "secondaryColor": {
                                                "r": 0.9,
                                                "g": 0.8,
                                                "b": 0.7,
                                                "a": 0.5,
                                            },
                                            "blendMode": "SOFT_LIGHT",
                                            "noiseSize": 6,
                                            "noiseType": "DUOTONE",
                                            "density": 0.42,
                                            "visible": True,
                                        },
                                        {
                                            "type": "TEXTURE",
                                            "radius": 5,
                                            "noiseSize": 12,
                                            "clipToShape": True,
                                            "visible": True,
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


def _effect_card(document: dict) -> dict:
    return next(row for row in document["objects"] if row["name"] == "Effect card")


_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
    "AAAADUlEQVR42mNk+M/wHwAF/gL+X2HFVQAAAABJRU5ErkJggg=="
)


class _Response:
    def __init__(self, data: bytes, content_type: str) -> None:
        self._data = data
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._data


def test_license_pinned_real_plugin_capture_preserves_noise_and_texture_values() -> None:
    import hashlib

    from app.painter_ui_figma import import_figma_payload

    manifest = json.loads(MODERN_EFFECT_MANIFEST.read_text(encoding="utf-8"))
    artifact = manifest["artifacts"][0]
    capture_path = (
        ROOT
        / "external"
        / "assets"
        / "figma"
        / "compat_corpus"
        / artifact["relative_path"]
    )
    if not capture_path.is_file():
        pytest.skip("downloaded OpenPencil compatibility capture is unavailable")
    payload_bytes = capture_path.read_bytes()
    assert len(payload_bytes) == artifact["bytes"]
    assert hashlib.sha256(payload_bytes).hexdigest() == artifact["sha256"]
    license_path = (
        ROOT
        / "external"
        / "assets"
        / "figma"
        / "compat_corpus"
        / artifact["license_relative_path"]
    )
    assert hashlib.sha256(license_path.read_bytes()).hexdigest() == artifact[
        "license_sha256"
    ]
    assert license_path.read_text(encoding="utf-8").startswith("MIT License")
    assert artifact["origin"] == "real_plugin_api_capture"
    assert "plugin_api_capture_not_rest_response" in artifact["limitations"]
    assert "no_render_png_golden" in artifact["limitations"]

    capture = json.loads(payload_bytes)
    noise_results = capture["effects"]["noise"]["results"]
    texture_result = capture["effects"]["textureAndGlass"]["results"][
        "TEXTURE"
    ]
    effects = [
        noise_results["MONOTONE"]["effects"][0],
        noise_results["DUOTONE"]["effects"][0],
        noise_results["MULTITONE"]["effects"][0],
        texture_result["effects"][0],
    ]
    rest_shape = _modern_effect_payload()
    card = rest_shape["document"]["children"][0]["children"][0]["children"][0]
    card["effects"] = effects
    document, report = import_figma_payload(
        rest_shape,
        source="open-pencil-real-plugin-api-capture.json",
    )

    assert report["ok"] is True
    imported = _effect_card(document)["style"]["effects"]
    assert [row["type"] for row in imported] == [
        "noise",
        "noise",
        "noise",
        "texture",
    ]
    assert [row["noise_type"] for row in imported[:3]] == [
        "monotone",
        "duotone",
        "multitone",
    ]
    assert imported[0]["noise_size_vector"] == {"x": 0.5, "y": 0.5}
    assert imported[0]["density"] == 0.4000000059604645
    assert imported[1]["secondary_color"] == "#FFFFFFFF"
    assert imported[2]["opacity"] == 0.699999988079071
    assert imported[3]["radius"] == 8.0
    assert imported[3]["clip_to_shape"] is True


def test_effect_normalizer_does_not_coerce_modern_figma_types_to_shadow() -> None:
    from app.painter_ui_appearance import normalize_ui_effect

    noise = normalize_ui_effect(
        {
            "type": "NOISE",
            "color": {"r": 1, "g": 0, "b": 0, "a": 0.5},
            "blendMode": "LINEAR_DODGE",
            "noiseSize": 5,
            "noiseType": "MULTITONE",
            "density": 0.3,
            "opacity": 0.7,
            "visible": False,
        }
    )
    assert noise == {
        "type": "noise",
        "color": "#FF000080",
        "blend_mode": "linear_dodge",
        "noise_size": 5.0,
        "noise_type": "multitone",
        "density": 0.3,
        "opacity": 0.7,
        "visible": False,
    }
    assert normalize_ui_effect(
        {
            "type": "TEXTURE",
            "radius": 4,
            "noiseSize": 9,
            "clipToShape": True,
        }
    )["type"] == "texture"
    assert normalize_ui_effect(
        {
            "type": "LAYER_BLUR",
            "radius": 14,
            "blurType": "PROGRESSIVE",
            "startRadius": 2,
            "startOffset": {"x": 0, "y": 0},
            "endOffset": {"x": 1, "y": 1},
        }
    )["blur_type"] == "progressive"


def test_progressive_blur_classifier_keeps_primary_reason_and_adds_exact_png_safety() -> None:
    from app.painter_ui_appearance import ui_effect_render_block_reasons

    layer = {
        "type": "layer_blur",
        "blur_type": "progressive",
        "radius": 24,
        "start_radius": 2,
        "start_offset": {"x": 0.1, "y": 0.2},
        "end_offset": {"x": 0.8, "y": 0.9},
    }
    layer_reason = (
        "figma_progressive_layer_blur_requires_"
        "ui_material_or_deterministic_bake"
    )
    assert ui_effect_render_block_reasons(layer) == [layer_reason]
    assert ui_effect_render_block_reasons(
        layer,
        exact_render={
            "source_bounds": {
                "x": 40,
                "y": 50,
                "width": 180,
                "height": 110,
            },
            "render_bounds": {
                "x": 34,
                "y": 44,
                "width": 192,
                "height": 122,
            },
        },
    ) == [
        layer_reason,
        "figma_progressive_layer_blur_render_bounds_expansion_"
        "requires_layout_aware_bake",
    ]
    background = {
        "type": "background_blur",
        "blur_type": "progressive",
        "radius": 18,
    }
    assert ui_effect_render_block_reasons(background) == [
        "figma_progressive_background_blur_requires_"
        "ui_material_or_deterministic_bake",
        "figma_progressive_background_blur_backdrop_dependency_"
        "requires_runtime_composition",
    ]
    assert ui_effect_render_block_reasons({**background, "visible": False}) == []


def test_modern_figma_effects_survive_rest_json_and_plugin_export(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )

    document, report = import_figma_payload(
        _modern_effect_payload(),
        source="modern-effects-rest.json",
    )
    assert report["ok"] is True
    effects = _effect_card(document)["style"]["effects"]
    assert effects == [
        {
            "type": "layer_blur",
            "radius": 24.0,
            "blur_type": "progressive",
            "start_radius": 2.0,
            "start_offset": {"x": 0.1, "y": 0.2},
            "end_offset": {"x": 0.8, "y": 0.9},
        },
        {
            "type": "background_blur",
            "radius": 18.0,
            "blur_type": "progressive",
            "start_radius": 1.0,
            "start_offset": {"x": 0.0, "y": 0.0},
            "end_offset": {"x": 1.0, "y": 1.0},
        },
        {
            "type": "noise",
            "color": "#1A334CBF",
            "blend_mode": "soft_light",
            "noise_size": 6.0,
            "noise_type": "duotone",
            "density": 0.42,
            "secondary_color": "#E6CCB280",
        },
        {
            "type": "texture",
            "radius": 5.0,
            "noise_size": 12.0,
            "clip_to_shape": True,
        },
    ]

    # The provider-neutral document must keep the beta fields through normal
    # JSON serialization and document normalization.
    restored = normalize_ui_document(json.loads(json.dumps(document)))
    assert _effect_card(restored)["style"]["effects"] == effects

    compatibility = inspect_figma_compatibility(restored)
    assert compatibility["ok"] is True
    assert compatibility["render_blocker_count"] == 4
    reasons = {row["reason"] for row in compatibility["render_blockers"]}
    assert reasons == {
        "figma_progressive_layer_blur_requires_ui_material_or_deterministic_bake",
        "figma_progressive_background_blur_requires_ui_material_or_deterministic_bake",
        "figma_noise_effect_requires_ui_material_or_deterministic_bake",
        "figma_texture_effect_requires_ui_material_or_deterministic_bake",
    }

    package = export_figma_plugin_package(restored, tmp_path)
    exchange = json.loads(
        Path(package["exchange_path"]).read_text(encoding="utf-8")
    )
    assert _effect_card(exchange["document"])["style"]["effects"] == effects
    code = (Path(package["output_dir"]) / "code.js").read_text(
        encoding="utf-8"
    )
    for marker in (
        "type:'NOISE'",
        "type:'TEXTURE'",
        "effect.blurType=blurType",
        "effect.startRadius=",
        "effect.startOffset=",
        "effect.endOffset=",
        "effect.secondaryColor=",
        "clipToShape:!!row.clip_to_shape",
    ):
        assert marker in code


def test_hidden_modern_effect_is_preserved_but_not_render_blocking(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        _figma_exact_effect_node_ids,
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )

    payload = _modern_effect_payload()
    card = payload["document"]["children"][0]["children"][0]["children"][0]
    hidden_noise = dict(card["effects"][2])
    hidden_noise["visible"] = False
    card["effects"] = [hidden_noise]

    document, report = import_figma_payload(payload, source="hidden-effect.json")
    effect = _effect_card(document)["style"]["effects"][0]

    assert report["ok"] is True
    assert effect["type"] == "noise"
    assert effect["visible"] is False
    assert _figma_exact_effect_node_ids(payload) == []
    compatibility = inspect_figma_compatibility(document)
    assert compatibility["render_blocker_count"] == 0
    assert normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    ) == document

    package = export_figma_plugin_package(document, tmp_path)
    exchange = json.loads(
        Path(package["exchange_path"]).read_text(encoding="utf-8")
    )
    assert _effect_card(exchange["document"])["style"]["effects"][0][
        "visible"
    ] is False
    code = (Path(package["output_dir"]) / "code.js").read_text(
        encoding="utf-8"
    )
    assert "visible:row.visible!==false" in code


def test_hidden_progressive_blurs_round_trip_without_exact_render_request(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        _figma_exact_effect_node_ids,
        export_figma_plugin_package,
        import_figma_payload,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import preflight_painter_umg

    payload = _modern_effect_payload()
    card = payload["document"]["children"][0]["children"][0]["children"][0]
    hidden_blurs = []
    for source_effect in card["effects"][:2]:
        effect = dict(source_effect)
        effect["visible"] = False
        hidden_blurs.append(effect)
    card["effects"] = hidden_blurs

    document, report = import_figma_payload(
        payload,
        source="hidden-progressive-blurs.json",
    )
    effects = _effect_card(document)["style"]["effects"]
    expected_fields = [
        {
            "type": "layer_blur",
            "radius": 24.0,
            "blur_type": "progressive",
            "start_radius": 2.0,
            "start_offset": {"x": 0.1, "y": 0.2},
            "end_offset": {"x": 0.8, "y": 0.9},
            "visible": False,
        },
        {
            "type": "background_blur",
            "radius": 18.0,
            "blur_type": "progressive",
            "start_radius": 1.0,
            "start_offset": {"x": 0.0, "y": 0.0},
            "end_offset": {"x": 1.0, "y": 1.0},
            "visible": False,
        },
    ]
    assert report["ok"] is True
    assert effects == expected_fields
    assert _figma_exact_effect_node_ids(payload) == []
    assert inspect_figma_compatibility(document)["render_blockers"] == []
    umg_preflight = preflight_painter_umg(document)
    assert not any(
        row["object_id"] == _effect_card(document)["id"]
        and any("progressive" in reason for reason in row["reasons"])
        for row in umg_preflight["blockers"]
    )
    assert normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    ) == document

    package = export_figma_plugin_package(document, tmp_path)
    exchange = json.loads(
        Path(package["exchange_path"]).read_text(encoding="utf-8")
    )
    assert _effect_card(exchange["document"])["style"]["effects"] == (
        expected_fields
    )


def test_authenticated_import_downloads_exact_modern_effect_png(
    tmp_path: Path,
) -> None:
    from app.painter_ui_document import normalize_ui_document
    from app.painter_ui_figma import (
        import_figma_file,
        inspect_figma_compatibility,
    )
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    payload = _modern_effect_payload()
    card = payload["document"]["children"][0]["children"][0]["children"][0]
    card["absoluteRenderBounds"] = {
        "x": 34,
        "y": 44,
        "width": 192,
        "height": 122,
    }
    requested_urls: list[str] = []

    def opener(request, *, timeout):
        assert timeout == 4.0
        url = request.full_url
        requested_urls.append(url)
        if "/files/AbCdEf123456?" in url:
            return _Response(
                json.dumps(payload).encode("utf-8"),
                "application/json",
            )
        if url.endswith("/files/AbCdEf123456/images"):
            return _Response(b'{"meta":{"images":{}}}', "application/json")
        if url.endswith("/files/AbCdEf123456/variables/local"):
            return _Response(b"{}", "application/json")
        if "/images/AbCdEf123456?" in url:
            return _Response(
                json.dumps(
                    {
                        "images": {
                            "2:1": "https://cdn.example/effect-card.png"
                        }
                    }
                ).encode("utf-8"),
                "application/json",
            )
        if url == "https://cdn.example/effect-card.png":
            return _Response(_ONE_PIXEL_PNG, "image/png")
        raise AssertionError(f"unexpected URL: {url}")

    document, report = import_figma_file(
        "AbCdEf123456",
        token="test-token",
        timeout=4.0,
        opener=opener,
        asset_root=tmp_path,
    )

    exact = _effect_card(document)["content"]["figma_exact_render"]
    png_path = Path(exact["png_path"])
    assert png_path.is_file()
    assert png_path.read_bytes() == _ONE_PIXEL_PNG
    assert png_path.parent == (tmp_path / "effect-renders").resolve()
    assert exact == {
        "png_path": str(png_path),
        "source_bounds": {
            "x": 40.0,
            "y": 50.0,
            "width": 180.0,
            "height": 110.0,
        },
        "render_bounds": {
            "x": 34.0,
            "y": 44.0,
            "width": 192.0,
            "height": 122.0,
        },
        "source": "figma_render_api",
        "node_id": "2:1",
        "format": "png",
        "scale": 1.0,
        "effect_types": [
            "progressive_layer_blur",
            "progressive_background_blur",
            "noise",
            "texture",
        ],
        "provenance": {
            "file_key": "AbCdEf123456",
            "endpoint": "GET /v1/images/:key",
            "authenticated_import": True,
        },
    }
    assert report["requested_effect_render_count"] == 1
    assert report["downloaded_effect_render_count"] == 1
    assert not any(
        warning.startswith("effect_render_") for warning in report["warnings"]
    )
    restored = normalize_ui_document(
        json.loads(json.dumps(document, ensure_ascii=False))
    )
    assert _effect_card(restored)["content"]["figma_exact_render"] == exact

    render_request = next(
        url for url in requested_urls if "/images/AbCdEf123456?" in url
    )
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(render_request).query)
    assert query == {"ids": ["2:1"], "format": ["png"], "scale": ["1"]}

    compatibility = inspect_figma_compatibility(document)
    blockers = {
        row["effect_type"]: row
        for row in compatibility["render_blockers"]
    }
    assert blockers["layer_blur"]["reason"] == (
        "figma_progressive_layer_blur_requires_"
        "ui_material_or_deterministic_bake"
    )
    assert blockers["layer_blur"]["diagnostics"] == [
        "figma_progressive_layer_blur_render_bounds_expansion_"
        "requires_layout_aware_bake"
    ]
    assert blockers["background_blur"]["reason"] == (
        "figma_progressive_background_blur_requires_"
        "ui_material_or_deterministic_bake"
    )
    assert blockers["background_blur"]["diagnostics"] == [
        "figma_progressive_background_blur_backdrop_dependency_"
        "requires_runtime_composition"
    ]
    assert all(row["exact_render_available"] for row in blockers.values())

    umg_document = painter_ui_to_umg_document(document)
    umg_layer = next(
        row for row in umg_document["Layers"] if row["Id"] == _effect_card(document)["id"]
    )
    assert umg_layer["Disposition"] == "Blocked"
    assert {
        "figma_progressive_layer_blur_requires_"
        "ui_material_or_deterministic_bake",
        "figma_progressive_layer_blur_render_bounds_expansion_"
        "requires_layout_aware_bake",
        "figma_progressive_background_blur_requires_"
        "ui_material_or_deterministic_bake",
        "figma_progressive_background_blur_backdrop_dependency_"
        "requires_runtime_composition",
    } <= set(umg_layer["BlockReasons"])


def test_effect_render_url_requests_are_chunked_at_one_hundred() -> None:
    from app.painter_ui_figma import _figma_effect_render_urls

    node_ids = [f"8:{index}" for index in range(101)]
    chunks: list[list[str]] = []

    def opener(request, *, timeout):
        assert timeout == 2.0
        query = urllib.parse.parse_qs(
            urllib.parse.urlsplit(request.full_url).query
        )
        ids = query["ids"][0].split(",")
        chunks.append(ids)
        assert query["format"] == ["png"]
        assert query["scale"] == ["1"]
        return _Response(
            json.dumps(
                {
                    "images": {
                        node_id: f"https://cdn.example/{node_id}.png"
                        for node_id in ids
                    }
                }
            ).encode("utf-8"),
            "application/json",
        )

    urls, warnings = _figma_effect_render_urls(
        "AbCdEf123456",
        node_ids,
        token="test-token",
        timeout=2.0,
        opener=opener,
    )

    assert [len(chunk) for chunk in chunks] == [100, 1]
    assert set(urls) == set(node_ids)
    assert warnings == []


def test_effect_render_request_failure_is_explicit_warning() -> None:
    from app.painter_ui_figma import _figma_effect_render_urls

    def opener(_request, *, timeout):
        assert timeout == 2.0
        raise OSError("simulated render request failure")

    urls, warnings = _figma_effect_render_urls(
        "AbCdEf123456",
        ["2:1"],
        token="test-token",
        timeout=2.0,
        opener=opener,
    )

    assert urls == {}
    assert len(warnings) == 1
    assert warnings[0].startswith("effect_render_request_failed:2:1:")


def test_effect_render_missing_url_is_explicit_warning(tmp_path: Path) -> None:
    from app.painter_ui_figma import (
        import_figma_file,
        inspect_figma_compatibility,
    )

    payload = _modern_effect_payload()

    def opener(request, *, timeout):
        url = request.full_url
        if "/files/AbCdEf123456?" in url:
            return _Response(
                json.dumps(payload).encode("utf-8"),
                "application/json",
            )
        if url.endswith("/files/AbCdEf123456/images"):
            return _Response(b'{"meta":{"images":{}}}', "application/json")
        if url.endswith("/files/AbCdEf123456/variables/local"):
            return _Response(b"{}", "application/json")
        if "/images/AbCdEf123456?" in url:
            return _Response(b'{"images":{}}', "application/json")
        raise AssertionError(f"unexpected URL: {url}")

    document, report = import_figma_file(
        "AbCdEf123456",
        token="test-token",
        timeout=4.0,
        opener=opener,
        asset_root=tmp_path,
    )

    assert report["requested_effect_render_count"] == 1
    assert report["downloaded_effect_render_count"] == 0
    assert "effect_render_missing:2:1" in report["warnings"]
    assert "figma_exact_render" not in _effect_card(document)["content"]
    reasons = {
        row["reason"]
        for row in inspect_figma_compatibility(document)["render_blockers"]
    }
    assert {
        "figma_progressive_layer_blur_requires_"
        "ui_material_or_deterministic_bake",
        "figma_progressive_background_blur_requires_"
        "ui_material_or_deterministic_bake",
    } <= reasons


def test_effect_render_download_failure_is_explicit_warning(
    tmp_path: Path,
) -> None:
    from app.painter_ui_figma import (
        import_figma_file,
        inspect_figma_compatibility,
    )

    payload = _modern_effect_payload()

    def opener(request, *, timeout):
        url = request.full_url
        if "/files/AbCdEf123456?" in url:
            return _Response(
                json.dumps(payload).encode("utf-8"),
                "application/json",
            )
        if url.endswith("/files/AbCdEf123456/images"):
            return _Response(b'{"meta":{"images":{}}}', "application/json")
        if url.endswith("/files/AbCdEf123456/variables/local"):
            return _Response(b"{}", "application/json")
        if "/images/AbCdEf123456?" in url:
            return _Response(
                b'{"images":{"2:1":"https://cdn.example/failed.png"}}',
                "application/json",
            )
        if url == "https://cdn.example/failed.png":
            raise OSError("simulated render download failure")
        raise AssertionError(f"unexpected URL: {url}")

    document, report = import_figma_file(
        "AbCdEf123456",
        token="test-token",
        timeout=4.0,
        opener=opener,
        asset_root=tmp_path,
    )

    assert report["requested_effect_render_count"] == 1
    assert report["downloaded_effect_render_count"] == 0
    assert any(
        warning.startswith("effect_render_download_failed:2:1:")
        for warning in report["warnings"]
    )
    assert "figma_exact_render" not in _effect_card(document)["content"]
    reasons = {
        row["reason"]
        for row in inspect_figma_compatibility(document)["render_blockers"]
    }
    assert {
        "figma_progressive_layer_blur_requires_"
        "ui_material_or_deterministic_bake",
        "figma_progressive_background_blur_requires_"
        "ui_material_or_deterministic_bake",
    } <= reasons


def test_modern_figma_effects_are_not_uniformly_faked_and_block_umg() -> None:
    from app.painter_ui_figma import import_figma_payload
    from app.painter_ui_style_renderer import ui_blur_radius
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document, _report = import_figma_payload(
        _modern_effect_payload(),
        source="modern-effects-rest.json",
    )
    card = _effect_card(document)
    assert ui_blur_radius(card["style"], "layer_blur") == 0.0
    assert ui_blur_radius(card["style"], "background_blur") == 0.0
    assert ui_blur_radius(
        {"effects": [{"type": "layer_blur", "radius": 7}]},
        "layer_blur",
    ) == 7.0

    preflight = preflight_painter_umg(document)
    blocker = next(
        row for row in preflight["blockers"] if row["object_id"] == card["id"]
    )
    assert {
        "figma_progressive_layer_blur_requires_ui_material_or_deterministic_bake",
        "figma_progressive_background_blur_requires_ui_material_or_deterministic_bake",
        "figma_noise_effect_requires_ui_material_or_deterministic_bake",
        "figma_texture_effect_requires_ui_material_or_deterministic_bake",
    } <= set(blocker["reasons"])


def test_appearance_editor_keeps_beta_figma_effects_read_only_and_lossless() -> None:
    from app.painter_ui_appearance_editor import PainterUIAppearanceDialog

    _app()
    style = {
        "effects": [
            {
                "type": "layer_blur",
                "radius": 20,
                "blur_type": "progressive",
                "start_radius": 2,
                "start_offset": {"x": 0, "y": 0},
                "end_offset": {"x": 1, "y": 1},
            },
            {
                "type": "noise",
                "color": "#112233FF",
                "blend_mode": "overlay",
                "noise_size": 4,
                "noise_type": "monotone",
                "density": 0.5,
            },
            {
                "type": "texture",
                "radius": 3,
                "noise_size": 8,
                "clip_to_shape": False,
            },
        ]
    }
    dialog = PainterUIAppearanceDialog(style)
    assert dialog.effect_list.count() == 3
    assert dialog.appearance_style()["effects"] == style["effects"]
    dialog.close()
