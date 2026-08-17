from __future__ import annotations

import binascii
import copy
import hashlib
import json
from pathlib import Path
import struct

import pytest


def test_static_vector_audit_case_filter_is_exact_and_fails_closed() -> None:
    from tools.qa_painter_ui_umg_static_vector_bake import _select_manifest_cases

    manifest = {
        "schema": "fixture",
        "cases": [
            {"id": "case-a", "artifact": {}},
            {"id": "case-b", "artifact": {}},
            {"id": "case-c", "artifact": {}},
        ],
    }
    selected = _select_manifest_cases(manifest, {"case-c", "case-a"})

    assert [row["id"] for row in selected["cases"]] == ["case-a", "case-c"]
    assert manifest["cases"][1]["id"] == "case-b"
    assert _select_manifest_cases(manifest, None) is manifest
    with pytest.raises(ValueError, match="Unknown static-vector audit case id"):
        _select_manifest_cases(manifest, {"case-missing"})
    with pytest.raises(ValueError, match="manifest cases must be an array"):
        _select_manifest_cases({"cases": {}}, {"case-a"})


def test_static_vector_audit_selector_loader_never_expands_to_full_archive(
    tmp_path: Path,
) -> None:
    from tools.qa_painter_ui_umg_static_vector_bake import (
        _load_audit_case_source,
    )

    calls: list[str] = []
    selector_payload = {"document": {"id": "selector-only"}}

    def load_selector(source_path, artifact, selector, cache):
        calls.append("selector")
        assert source_path == tmp_path / "source.zip"
        assert artifact == {"relative_path": "source.zip"}
        assert selector == {"node_id": "1:2"}
        cache[("source", "hash")] = {"cached": True}
        return selector_payload, {"image": "selected.png"}, {"kind": "selector"}, {}

    def load_full(_source_path):
        calls.append("full")
        raise AssertionError("selector audit must not load the full archive")

    def verify(_source_path, _artifact):
        calls.append("verify")
        raise AssertionError("selector loader owns artifact verification")

    cache: dict[tuple[str, str], dict] = {}
    payload, images, details = _load_audit_case_source(
        {
            "id": "selector-case",
            "artifact": {"relative_path": "source.zip"},
            "selector": {"node_id": "1:2"},
        },
        tmp_path / "source.zip",
        cache,
        load_case_source=load_full,
        load_selector_case_source=load_selector,
        verify_case_artifact=verify,
    )

    assert calls == ["selector"]
    assert payload is selector_payload
    assert images == {"image": "selected.png"}
    assert details == {"kind": "selector"}
    assert cache == {("source", "hash"): {"cached": True}}


def _row(paths: str | list[str]) -> dict:
    values = [paths] if isinstance(paths, str) else paths
    return {
        "kind": "path",
        "content": {
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {"path": path, "winding_rule": "nonzero"}
                for path in values
            ],
            "vector_paths": list(values),
        },
        "style": {
            "fill": "#F97316FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "color": "#F97316FF",
                    "opacity": 1.0,
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
        },
    }


def _plan(paths: str | list[str]) -> dict:
    from app.unreal_umg_static_vector_bake import plan_static_vector_bake

    return plan_static_vector_bake(
        _row(paths),
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )


def _png_chunks(payload: bytes) -> list[tuple[bytes, bytes]]:
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    chunks: list[tuple[bytes, bytes]] = []
    offset = 8
    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        kind = payload[offset + 4 : offset + 8]
        data_start = offset + 8
        data_end = data_start + length
        data = payload[data_start:data_end]
        crc = struct.unpack(">I", payload[data_end : data_end + 4])[0]
        assert crc == binascii.crc32(kind + data) & 0xFFFFFFFF
        chunks.append((kind, data))
        offset = data_end + 4
        if kind == b"IEND":
            break
    assert offset == len(payload)
    return chunks


def test_v2_v3_png_and_manifest_pin_exact_srgb_straight_alpha_contract(
    tmp_path: Path,
) -> None:
    from PySide6.QtGui import QImage

    from app.unreal_umg_static_vector_bake import (
        STATIC_VECTOR_BAKE_COLOR_CONTRACT,
        STATIC_VECTOR_BAKE_RENDERER,
        STATIC_VECTOR_BAKE_SCHEMA,
        write_static_vector_bake,
    )

    plan = _plan("M 0 0 L 40 0 L 40 30 L 0 30 Z")
    assert plan["available"] is True
    assert STATIC_VECTOR_BAKE_SCHEMA == "tigerstudio.umg.static_vector_bake.v4"
    assert STATIC_VECTOR_BAKE_RENDERER == "qt_svg_fill_stroke_geometry_v5"
    assert STATIC_VECTOR_BAKE_COLOR_CONTRACT == {
        "color_space": "sRGB",
        "alpha_mode": "straight",
        "channel_depth_bits": 8,
        "png_srgb_rendering_intent": 0,
    }
    assert plan["source"]["schema"] == STATIC_VECTOR_BAKE_SCHEMA
    assert plan["source"]["renderer"]["id"] == STATIC_VECTOR_BAKE_RENDERER
    assert plan["source"]["color_contract"] == STATIC_VECTOR_BAKE_COLOR_CONTRACT

    first = write_static_vector_bake(plan, tmp_path)
    second = write_static_vector_bake(plan, tmp_path)
    png = Path(first["png_path"]).read_bytes()
    chunks = _png_chunks(png)
    assert [kind for kind, _data in chunks] == [
        b"IHDR",
        b"sRGB",
        b"IDAT",
        b"IEND",
    ]
    width, height, depth, color_type, compression, filtering, interlace = (
        struct.unpack(">IIBBBBB", chunks[0][1])
    )
    assert (width, height, depth, color_type) == (44, 34, 8, 6)
    assert (compression, filtering, interlace) == (0, 0, 0)
    assert chunks[1] == (b"sRGB", b"\x00")
    assert hashlib.sha256(png).hexdigest() == first["content_hash"]
    assert second["reused"] is True

    manifest = json.loads(
        Path(first["manifest_path"]).read_text(encoding="utf-8")
    )
    assert manifest["schema"] == STATIC_VECTOR_BAKE_SCHEMA
    assert manifest["color_contract"] == STATIC_VECTOR_BAKE_COLOR_CONTRACT
    assert manifest["source"]["color_contract"] == STATIC_VECTOR_BAKE_COLOR_CONTRACT
    image = QImage(str(first["png_path"]))
    assert not image.isNull()
    center = image.pixelColor(22, 17)
    assert (center.red(), center.green(), center.blue(), center.alpha()) == (
        249,
        115,
        22,
        255,
    )


@pytest.mark.parametrize(
    "path",
    [
        "M,0,0 L 10 0 L 10 10 Z",
        "M 0,,0 L 10 0 L 10 10 Z",
        "M 0 0, L 10 0 L 10 10 Z",
        "M 0 0 L 10 0 L 10 10 Z,",
        "M 0 0 L 10 0 L 10 10 Z m 2 2 l 2 0 l 0 2 z",
        "M 5 15 A -10 10 0 1 1 25 15 Z",
        "M 5 15 A 10 10 0 2 1 25 15 Z",
        "M 5 15 A 10 10 0 1.0 1 25 15 Z",
        "M 5 15 A 10 10 0 +1 1 25 15 Z",
        "M 0 0 L 10\u00a00 L 10 10 Z",
    ],
)
def test_malformed_or_context_dependent_relative_svg_is_never_qt_recovered(
    path: str,
) -> None:
    plan = _plan(path)

    assert plan["available"] is False
    assert (
        "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
        in plan["reasons"]
    )


@pytest.mark.parametrize(
    "path",
    [
        "m 5 15 a 10 10 0 1 1 20 0 a 10 10 0 1 1 -20 0 z",
        "M0,0 L40,0 L40,30 L0,30 Z",
        "M 1 1 L 10 1 L 10 10 Z M 20 20 l 8 0 l 0 8 z",
    ],
)
def test_self_contained_relative_commands_and_absolute_subpaths_remain_supported(
    path: str,
) -> None:
    plan = _plan(path)

    assert plan["available"] is True
    assert plan["source"]["subpath_contract"]["count"] >= 1


@pytest.mark.parametrize(
    ("paths", "reason"),
    [
        (
            "M 1 1 L 10 1 L 10 10 Z M -2 2 L 4 2 L 4 8 Z",
            "figma_vector_static_bake_subpath_outside_logical_bounds",
        ),
        (
            ["M 1 1 L 10 1 L 10 10 Z", "M 41 1 L 45 1 L 45 8 Z"],
            "figma_vector_static_bake_subpath_outside_logical_bounds",
        ),
        (
            "M 1 1 L 10 1 L 10 10 Z M 20 5 L 20 20 L 20 5 Z",
            "figma_vector_static_bake_subpath_degenerate",
        ),
    ],
)
def test_every_closed_subpath_is_independently_bounded_and_non_degenerate(
    paths: str | list[str],
    reason: str,
) -> None:
    plan = _plan(paths)

    assert plan["available"] is False
    assert reason in plan["reasons"]
    assert "figma_vector_static_bake_visible_geometry_missing" in plan["reasons"]


def test_subpath_contract_accepts_exact_logical_boundary_and_enforces_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.unreal_umg_static_vector_bake as static_bake

    boundary = _plan("M 0 0 L 40 0 L 40 30 L 0 30 Z")
    assert boundary["available"] is True
    assert boundary["source"]["subpath_contract"]["items"][0]["bounds"] == {
        "x": 0.0,
        "y": 0.0,
        "width": 40.0,
        "height": 30.0,
    }

    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_SUBPATHS", 2)
    capped = static_bake.plan_static_vector_bake(
        _row(
            "M 1 1 L 4 1 L 4 4 Z "
            "M 8 1 L 11 1 L 11 4 Z "
            "M 15 1 L 18 1 L 18 4 Z"
        ),
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    assert capped["available"] is False
    assert "figma_vector_static_bake_subpath_limit_exceeded" in capped["reasons"]


def test_geometry_row_byte_and_total_token_caps_run_before_svg_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.unreal_umg_static_vector_bake as static_bake

    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS", 1)
    row_limited = static_bake.plan_static_vector_bake(
        _row(["M 1 1 L 4 1 L 4 4 Z", "M 8 1 L 11 1 L 11 4 Z"]),
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    assert row_limited["available"] is False
    assert (
        "figma_vector_static_bake_geometry_row_limit_exceeded"
        in row_limited["reasons"]
    )

    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS", 256)
    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_PATH_BYTES", 20)
    byte_limited = static_bake.plan_static_vector_bake(
        _row("M 1 1 L 20 1 L 20 20 L 1 20 Z"),
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    assert byte_limited["available"] is False
    assert (
        "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
        in byte_limited["reasons"]
    )

    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_PATH_BYTES", 1024)
    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_PATH_TOKENS", 16)
    total_token_limited = static_bake.plan_static_vector_bake(
        _row(["M 1 1 L 4 1 L 4 4 Z", "M 8 1 L 11 1 L 11 4 Z"]),
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    assert total_token_limited["available"] is False
    assert (
        "figma_vector_static_bake_path_syntax_or_complexity_unsupported"
        in total_token_limited["reasons"]
    )


def test_malformed_or_over_limit_legacy_vector_paths_cannot_be_silently_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.unreal_umg_static_vector_bake as static_bake

    row = _row("M 1 1 L 20 1 L 20 20 Z")
    row["content"]["vector_paths"] = [None]
    malformed = static_bake.plan_static_vector_bake(
        row,
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    assert malformed["available"] is False
    assert "figma_vector_static_bake_geometry_sources_disagree" in malformed[
        "reasons"
    ]

    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_GEOMETRY_ROWS", 1)
    row["content"]["vector_paths"] = [
        "M 1 1 L 20 1 L 20 20 Z",
        "M 2 2 L 4 2 L 4 4 Z",
    ]
    over_limit = static_bake.plan_static_vector_bake(
        row,
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    assert over_limit["available"] is False
    assert "figma_vector_static_bake_geometry_sources_disagree" in over_limit[
        "reasons"
    ]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("subpath_bounds", "subpath contract was mutated"),
        ("color_contract", "color contract is not reproducible"),
        ("renderer", "renderer contract is not reproducible"),
        ("complexity", "geometry complexity was mutated"),
    ],
)
def test_writer_rederives_hashed_contract_fields_instead_of_trusting_metadata(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    import app.unreal_umg_static_vector_bake as static_bake

    plan = copy.deepcopy(_plan("M 1 1 L 39 1 L 39 29 L 1 29 Z"))
    source = plan["source"]
    if mutation == "subpath_bounds":
        source["subpath_contract"]["items"][0]["bounds"]["x"] = 3.0
    elif mutation == "color_contract":
        source["color_contract"]["color_space"] = "linear"
    elif mutation == "renderer":
        source["renderer"]["id"] = "untrusted_renderer"
    else:
        source["geometry_complexity"]["token_count"] += 1

    # Re-hash the forged source so this specifically proves field derivation,
    # not merely the outer source-hash equality check.
    plan["source_hash"] = hashlib.sha256(
        static_bake._canonical_bytes(source)
    ).hexdigest()
    with pytest.raises(ValueError, match=message):
        static_bake.write_static_vector_bake(plan, tmp_path)


def test_gate_audit_uses_final_actual_and_packaged_persisted_transition() -> None:
    from tools.qa_painter_ui_umg_static_vector_bake import _foundation_probe

    probe = _foundation_probe()

    assert probe["passed"] is True
    assert probe["materialization"]["planned_transition_evidence"]["valid"] is True
    assert probe["materialization"]["packaged_transition_matches"] is True
    assert probe["materialization"]["persisted_transition_matches"] is True
    assert probe["materialization"]["packaged_after_matches_final_reasons"] is True
    assert probe["later_blocker_probe"]["preserved"] is True
    assert probe["later_blocker_probe"]["transition"]["after"] == [
        "prototype_sticky_requires_umg_runtime_binding"
    ]


def test_gate_audit_rejects_forged_after_or_unrelated_removed_reason() -> None:
    from tools.qa_painter_ui_umg_static_vector_bake import (
        VECTOR_GATE,
        _gate_transition_evidence,
    )

    layer = {
        "Disposition": "Baked",
        "BlockReasons": [],
    }
    forged = {
        "available": True,
        "gate_transition": {
            "before": [VECTOR_GATE, "unrelated"],
            "after": [],
            "satisfied": [VECTOR_GATE, "unrelated"],
        },
    }
    evidence = _gate_transition_evidence(layer, forged)
    assert evidence["valid"] is False
    assert "gate_transition_removed_unrelated_reason" in evidence["errors"]

    forged["gate_transition"] = {
        "before": [VECTOR_GATE],
        "after": ["late_blocker"],
        "satisfied": [VECTOR_GATE],
    }
    evidence = _gate_transition_evidence(layer, forged)
    assert evidence["valid"] is False
    assert "gate_transition_after_not_final_layer_reasons" in evidence["errors"]
