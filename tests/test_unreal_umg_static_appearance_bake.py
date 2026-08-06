from __future__ import annotations

import binascii
import copy
import hashlib
import json
from pathlib import Path
import struct
import zlib

import pytest


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def _pixels(width: int, height: int) -> bytes:
    return bytes(
        channel
        for y in range(height)
        for x in range(width)
        for channel in (
            (x * 29 + y * 7) % 256,
            (x * 3 + y * 31) % 256,
            (x * 11 + y * 13) % 256,
            96 + (x * 17 + y * 19) % 160,
        )
    )


def _png_bytes(
    width: int,
    height: int,
    *,
    rgba: bytes | None = None,
    color_type: int = 6,
    depth: int = 8,
    srgb: bytes | None = b"\x00",
    interlace: int = 0,
    extras: tuple[tuple[bytes, bytes], ...] = (),
) -> bytes:
    channels = 4 if color_type == 6 else 3
    source = rgba if rgba is not None else _pixels(width, height)
    if channels == 3:
        source = bytes(
            channel
            for index in range(0, len(source), 4)
            for channel in source[index : index + 3]
        )
    row_bytes = width * channels
    scanlines = b"".join(
        b"\x00" + source[y * row_bytes : (y + 1) * row_bytes]
        for y in range(height)
    )
    chunks = [
        _chunk(
            b"IHDR",
            struct.pack(">IIBBBBB", width, height, depth, color_type, 0, 0, interlace),
        )
    ]
    if srgb is not None:
        chunks.append(_chunk(b"sRGB", srgb))
    chunks.extend(_chunk(kind, data) for kind, data in extras)
    chunks.extend(
        (
            _chunk(b"IDAT", zlib.compress(scanlines, level=6)),
            _chunk(b"IEND", b""),
        )
    )
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunks)


def _write_png(path: Path, width: int = 12, height: int = 8, **kwargs) -> bytes:
    payload = _png_bytes(width, height, **kwargs)
    path.write_bytes(payload)
    return payload


def _row(png_path: Path) -> dict:
    bounds = {"x": 40.0, "y": 50.0, "width": 12.0, "height": 8.0}
    return {
        "id": "figma-2-1",
        "kind": "rectangle",
        "name": "Exact noise",
        "x": 40.0,
        "y": 50.0,
        "width": 12.0,
        "height": 8.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "style": {
            "fill": "#334D66FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#334D66FF",
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
            "radius": 2.0,
            "corner_radii": {
                "top_left": 2.0,
                "top_right": 2.0,
                "bottom_right": 2.0,
                "bottom_left": 2.0,
            },
            "corner_smoothing": 0.0,
            "effects": [
                {
                    "type": "noise",
                    "color": "#19334CBF",
                    "blend_mode": "soft_light",
                    "noise_size": 6.0,
                    "noise_type": "duotone",
                    "density": 0.42,
                    "secondary_color": "#E6CCB280",
                }
            ],
        },
        "content": {
            "figma_node_id": "2:1",
            "figma_type": "RECTANGLE",
            "boolean": {"enabled": False},
            "figma_exact_render": {
                "png_path": str(png_path),
                "source": "figma_render_api",
                "node_id": "2:1",
                "format": "png",
                "scale": 1.0,
                "source_bounds": copy.deepcopy(bounds),
                "render_bounds": copy.deepcopy(bounds),
                # Acquisition may append unrelated provenance. The planner
                # ignores it instead of weakening its required contract.
                "request_id": "render-request-7",
            },
        },
        "mask": {"enabled": False},
    }


def _plan(row: dict) -> dict:
    from app.unreal_umg_static_appearance_bake import (
        plan_static_appearance_bake,
    )

    return plan_static_appearance_bake(
        row,
        resolved_size={"width": 12.0, "height": 8.0},
        has_children=False,
        runtime_size_dynamic=False,
    )


def _document(png_path: Path) -> dict:
    from app.painter_ui_document import create_ui_document

    document = create_ui_document(320, 240)
    document["artboards"][0]["background"] = "#00000000"
    row = _row(png_path)
    row.update(
        {
            "artboard_id": document["active_artboard_id"],
            "parent_id": "",
            "visible": True,
            "locked": False,
            "clip_content": False,
            "z_index": 0,
            "constraints": {"horizontal": "left", "vertical": "top"},
            "layout": {},
            "token_bindings": {},
            "accessibility": {},
        }
    )
    document["objects"] = [row]
    return document


def _texture_row(png_path: Path) -> dict:
    row = _row(png_path)
    row["name"] = "Exact texture"
    row["style"]["effects"] = [
        {
            "type": "texture",
            "radius": 4.0,
            "noise_size": 8.0,
            "clip_to_shape": True,
            "noise_size_vector": {"x": 8.0, "y": 12.0},
        }
    ]
    return row


def _texture_document(png_path: Path) -> dict:
    document = _document(png_path)
    texture = _texture_row(png_path)
    for key in (
        "artboard_id",
        "parent_id",
        "visible",
        "locked",
        "clip_content",
        "z_index",
        "constraints",
        "layout",
        "token_bindings",
        "accessibility",
    ):
        texture[key] = copy.deepcopy(document["objects"][0][key])
    document["objects"] = [texture]
    return document


def test_exact_noise_plan_hashes_canonical_effect_source_png_and_rgba(
    tmp_path: Path,
) -> None:
    png_path = tmp_path / "figma-noise.png"
    png_bytes = _write_png(
        png_path,
        extras=((b"tEXt", b"Generator\x00Figma exact render"),),
    )
    row = _row(png_path)
    plan = _plan(row)

    assert plan["status"] == "available"
    assert plan["available"] is True
    assert plan["reasons"] == []
    assert plan["kind"] == "static_figma_appearance_png"
    assert plan["intended_gate"] == (
        "figma_noise_effect_requires_ui_material_or_deterministic_bake"
    )
    assert plan["integration_status"] == (
        "tigerstudio_umg_schema14_candidate"
    )
    assert plan["input_png"]["png_sha256"] == hashlib.sha256(png_bytes).hexdigest()
    assert plan["input_png"]["pixel_rgba_sha256"] == hashlib.sha256(
        _pixels(12, 8)
    ).hexdigest()
    effect_bytes = json.dumps(
        row["style"]["effects"][0],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert plan["effect_hash"] == hashlib.sha256(effect_bytes).hexdigest()
    source_bytes = json.dumps(
        plan["source"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert plan["source_hash"] == hashlib.sha256(source_bytes).hexdigest()
    assert plan["source"]["render_contract"] == {
        "source": "figma_render_api",
        "format": "png",
        "scale": 1.0,
    }
    assert "intended_gate" not in plan["source"]
    assert set(plan["source"]) == {
        "schema",
        "figma_node_id",
        "logical_size",
        "pixel_size",
        "source_bounds",
        "render_bounds",
        "render_contract",
        "effect",
        "effect_hash",
        "fill",
        "shape",
        "input_png_sha256",
        "pixel_rgba_sha256",
        "color_contract",
    }

    # Filesystem location and extra acquisition metadata do not alter the
    # canonical identity when the exact artifact and semantics are identical.
    second_path = tmp_path / "other-location.png"
    second_path.write_bytes(png_bytes)
    second = _row(second_path)
    second["content"]["figma_exact_render"]["request_id"] = "other-request"
    second_plan = _plan(second)
    assert second_plan["source_hash"] == plan["source_hash"]


def test_exact_texture_plan_uses_distinct_schema_kind_and_gate(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_static_appearance_bake import (
        STATIC_TEXTURE_BAKE_INTENDED_GATE,
        STATIC_TEXTURE_BAKE_KIND,
        STATIC_TEXTURE_BAKE_SCHEMA,
    )

    png_path = tmp_path / "figma-texture.png"
    png_bytes = _write_png(png_path)
    plan = _plan(_texture_row(png_path))

    assert plan["status"] == "available"
    assert plan["available"] is True
    assert plan["reasons"] == []
    assert plan["kind"] == STATIC_TEXTURE_BAKE_KIND
    assert plan["intended_gate"] == STATIC_TEXTURE_BAKE_INTENDED_GATE
    assert plan["integration_status"] == "tigerstudio_umg_schema15_candidate"
    assert plan["source"]["schema"] == STATIC_TEXTURE_BAKE_SCHEMA
    assert plan["source"]["intended_gate"] == (
        STATIC_TEXTURE_BAKE_INTENDED_GATE
    )
    assert plan["source"]["effect"] == {
        "type": "texture",
        "radius": 4.0,
        "noise_size": 8.0,
        "clip_to_shape": True,
        "noise_size_vector": {"x": 8.0, "y": 12.0},
    }
    assert plan["input_png"]["png_sha256"] == hashlib.sha256(
        png_bytes
    ).hexdigest()


def test_noise_numeric_fields_reject_json_boolean_stand_ins(
    tmp_path: Path,
) -> None:
    png_path = tmp_path / "figma-noise.png"
    _write_png(png_path)
    row = _row(png_path)
    row["style"]["effects"][0]["noise_size"] = True

    assert (
        "figma_appearance_static_bake_noise_effect_not_normalized"
        in _plan(row)["reasons"]
    )


def test_texture_candidate_requires_one_normalized_visible_texture(
    tmp_path: Path,
) -> None:
    png_path = tmp_path / "figma-texture.png"
    _write_png(png_path)

    hidden = _texture_row(png_path)
    hidden["style"]["effects"][0]["visible"] = False
    assert _plan(hidden)["status"] == "not_applicable"

    unnormalized = _texture_row(png_path)
    unnormalized["style"]["effects"][0]["radius"] = -1.0
    assert (
        "figma_appearance_static_bake_texture_effect_not_normalized"
        in _plan(unnormalized)["reasons"]
    )

    integer_clip = _texture_row(png_path)
    integer_clip["style"]["effects"][0]["clip_to_shape"] = 1
    assert (
        "figma_appearance_static_bake_texture_effect_not_normalized"
        in _plan(integer_clip)["reasons"]
    )

    boolean_radius = _texture_row(png_path)
    boolean_radius["style"]["effects"][0]["radius"] = True
    assert (
        "figma_appearance_static_bake_texture_effect_not_normalized"
        in _plan(boolean_radius)["reasons"]
    )

    boolean_vector = _texture_row(png_path)
    boolean_vector["style"]["effects"][0]["noise_size_vector"]["x"] = True
    assert (
        "figma_appearance_static_bake_texture_effect_not_normalized"
        in _plan(boolean_vector)["reasons"]
    )

    multiple = _texture_row(png_path)
    multiple["style"]["effects"].append(
        {"type": "layer_blur", "radius": 2.0}
    )
    assert (
        "figma_appearance_static_bake_requires_one_visible_texture_effect"
        in _plan(multiple)["reasons"]
    )

    ambiguous = _texture_row(png_path)
    ambiguous["style"]["effects"].append(
        copy.deepcopy(_row(png_path)["style"]["effects"][0])
    )
    assert _plan(ambiguous)["reasons"] == [
        "figma_appearance_static_bake_effect_kind_ambiguous"
    ]


def test_materialization_reencodes_deterministically_and_records_provenance(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_static_appearance_bake import (
        write_static_appearance_bake,
    )

    input_path = tmp_path / "input.png"
    input_bytes = _write_png(
        input_path,
        extras=((b"tEXt", b"Request\x00volatile acquisition metadata"),),
    )
    plan = _plan(_row(input_path))
    first = write_static_appearance_bake(plan, tmp_path / "package")
    second = write_static_appearance_bake(plan, tmp_path / "package")
    output_path = Path(first["png_path"])
    manifest_path = Path(first["manifest_path"])
    output_bytes = output_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert first["reused"] is False
    assert second["reused"] is True
    assert output_bytes != input_bytes
    assert b"volatile acquisition metadata" not in output_bytes
    assert output_bytes.count(b"sRGB") == 1
    assert hashlib.sha256(output_bytes).hexdigest() == manifest["content_hash"]
    assert manifest["pixel_rgba_sha256"] == hashlib.sha256(
        _pixels(12, 8)
    ).hexdigest()
    assert manifest["provenance"]["input_png_sha256"] == hashlib.sha256(
        input_bytes
    ).hexdigest()
    assert manifest["provenance"]["source_bounds"] == manifest["provenance"][
        "render_bounds"
    ]
    assert manifest["integration_status"] == (
        "tigerstudio_umg_schema14_artifact"
    )
    assert manifest["schema"] == "tigerstudio.umg.static_appearance_bake.v1"
    assert manifest["kind"] == "static_figma_appearance_png"
    assert Path(first["png_path"]).name.startswith("TS_Appearance_")
    assert manifest["umg_support_claimed"] is True
    assert str(input_path.resolve()) not in manifest_path.read_text(encoding="utf-8")


def test_optional_exact_render_format_scale_and_record_node_use_safe_defaults(
    tmp_path: Path,
) -> None:
    png_path = tmp_path / "input.png"
    _write_png(png_path)
    row = _row(png_path)
    exact = row["content"]["figma_exact_render"]
    exact.pop("format")
    exact.pop("scale")
    exact.pop("node_id")

    plan = _plan(row)

    assert plan["status"] == "available"
    assert plan["source"]["figma_node_id"] == "2:1"
    assert plan["source"]["render_contract"]["format"] == "png"
    assert plan["source"]["render_contract"]["scale"] == 1.0


def test_non_noise_rows_are_not_applicable(tmp_path: Path) -> None:
    png_path = tmp_path / "input.png"
    _write_png(png_path)
    row = _row(png_path)
    row["style"]["effects"] = []

    assert _plan(row) == {
        "kind": "static_figma_appearance_png",
        "status": "not_applicable",
        "available": False,
        "reasons": [],
    }


def test_hidden_noise_is_not_a_candidate_or_new_umg_blocker(tmp_path: Path) -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    row = _row(png_path)
    row["style"]["effects"][0]["visible"] = False
    assert _plan(row)["status"] == "not_applicable"

    document = _document(png_path)
    document["objects"][0]["style"]["effects"][0]["visible"] = False
    converted = painter_ui_to_umg_document(document)
    layer = converted["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    assert converted["SchemaVersion"] == 13
    assert payload["static_appearance_bake"]["status"] == "not_applicable"
    assert not any(
        "appearance_static_bake" in reason
        for reason in layer["BlockReasons"]
    )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("kind", "figma_appearance_static_bake_requires_rectangle"),
        ("figma_type", "figma_appearance_static_bake_requires_figma_rectangle"),
        ("rotation", "figma_appearance_static_bake_requires_unrotated"),
        ("opacity", "figma_appearance_static_bake_object_opacity_unsupported"),
        ("object_blend", "figma_appearance_static_bake_object_blend_unsupported"),
        ("second_effect", "figma_appearance_static_bake_requires_one_visible_noise_effect"),
        ("unnormalized_effect", "figma_appearance_static_bake_noise_effect_not_normalized"),
        ("density", "figma_appearance_static_bake_noise_density_out_of_range"),
        ("gradient_fill", "figma_appearance_static_bake_requires_one_solid_fill"),
        ("fill_blend", "figma_appearance_static_bake_fill_blend_unsupported"),
        ("stroke", "figma_appearance_static_bake_stroke_unsupported"),
        ("image", "figma_appearance_static_bake_image_unsupported"),
        ("mask", "figma_appearance_static_bake_mask_unsupported"),
        ("boolean", "figma_appearance_static_bake_boolean_unsupported"),
        ("shape", "figma_appearance_static_bake_rectangle_shape_invalid"),
    ],
)
def test_visual_or_semantic_expansion_stays_unsafe(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    png_path = tmp_path / "input.png"
    _write_png(png_path)
    row = _row(png_path)
    if mutation == "kind":
        row["kind"] = "ellipse"
    elif mutation == "figma_type":
        row["content"]["figma_type"] = "FRAME"
    elif mutation == "rotation":
        row["rotation"] = 0.1
    elif mutation == "opacity":
        row["opacity"] = 0.5
    elif mutation == "object_blend":
        row["style"]["blend_mode"] = "multiply"
    elif mutation == "second_effect":
        row["style"]["effects"].append(
            {"type": "layer_blur", "radius": 4.0}
        )
    elif mutation == "unnormalized_effect":
        row["style"]["effects"][0]["blend_mode"] = "SOFT_LIGHT"
    elif mutation == "density":
        row["style"]["effects"][0]["density"] = 1.1
    elif mutation == "gradient_fill":
        row["style"]["fills"][0]["type"] = "linear"
    elif mutation == "fill_blend":
        row["style"]["fills"][0]["blend_mode"] = "multiply"
    elif mutation == "stroke":
        row["style"]["strokes"] = [
            {
                "type": "solid",
                "visible": True,
                "color": "#FFFFFFFF",
                "width": 1.0,
            }
        ]
    elif mutation == "image":
        row["content"]["image_path"] = "other.png"
    elif mutation == "mask":
        row["mask"]["enabled"] = True
    elif mutation == "boolean":
        row["content"]["boolean"]["enabled"] = True
    else:
        row["style"]["corner_radii"]["top_left"] = float("nan")

    plan = _plan(row)

    assert plan["status"] == "unsafe"
    assert plan["available"] is False
    assert reason in plan["reasons"]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing", "figma_appearance_static_bake_exact_render_record_missing"),
        ("source", "figma_appearance_static_bake_exact_render_source_unsupported"),
        ("format", "figma_appearance_static_bake_exact_render_format_unsupported"),
        ("scale", "figma_appearance_static_bake_exact_render_scale_unsupported"),
        ("node", "figma_appearance_static_bake_exact_render_node_id_mismatch"),
        ("bounds", "figma_appearance_static_bake_exact_render_bounds_mismatch"),
        ("bounds_size", "figma_appearance_static_bake_exact_render_bounds_size_mismatch"),
        ("path", "figma_appearance_static_bake_png_path_missing"),
        ("file", "figma_appearance_static_bake_png_missing"),
    ],
)
def test_exact_render_binding_fails_closed(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    png_path = tmp_path / "input.png"
    _write_png(png_path)
    row = _row(png_path)
    exact = row["content"]["figma_exact_render"]
    if mutation == "missing":
        row["content"].pop("figma_exact_render")
    elif mutation == "source":
        exact["source"] = "local_approximation"
    elif mutation == "format":
        exact["format"] = "jpeg"
    elif mutation == "scale":
        exact["scale"] = 2.0
    elif mutation == "node":
        exact["node_id"] = "9:9"
    elif mutation == "bounds":
        exact["render_bounds"]["x"] += 1.0
    elif mutation == "bounds_size":
        exact["source_bounds"]["width"] = 13.0
        exact["render_bounds"]["width"] = 13.0
    elif mutation == "path":
        exact["png_path"] = ""
    else:
        exact["png_path"] = str(tmp_path / "missing.png")

    plan = _plan(row)

    assert plan["status"] == "unsafe"
    assert reason in plan["reasons"]


def test_leaf_fixed_size_and_integer_pixel_contracts_fail_closed(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_static_appearance_bake import (
        plan_static_appearance_bake,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    row = _row(png_path)

    child = plan_static_appearance_bake(
        row,
        resolved_size={"width": 12.0, "height": 8.0},
        has_children=True,
        runtime_size_dynamic=False,
    )
    dynamic = plan_static_appearance_bake(
        row,
        resolved_size={"width": 12.0, "height": 8.0},
        has_children=False,
        runtime_size_dynamic=True,
    )
    fractional = plan_static_appearance_bake(
        row,
        resolved_size={"width": 12.5, "height": 8.0},
        has_children=False,
        runtime_size_dynamic=False,
    )

    assert "figma_appearance_static_bake_requires_leaf" in child["reasons"]
    assert "figma_appearance_static_bake_requires_fixed_size" in dynamic["reasons"]
    assert (
        "figma_appearance_static_bake_fractional_dimensions_unsupported"
        in fractional["reasons"]
    )


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("rgb", "figma_appearance_static_bake_png_not_rgba8"),
        ("no_srgb", "figma_appearance_static_bake_png_srgb_intent_invalid"),
        ("wrong_intent", "figma_appearance_static_bake_png_srgb_intent_invalid"),
        ("icc", "figma_appearance_static_bake_png_srgb_intent_invalid"),
        ("interlace", "figma_appearance_static_bake_png_interlace_unsupported"),
        ("wrong_size", "figma_appearance_static_bake_png_dimensions_mismatch"),
        ("crc", "figma_appearance_static_bake_png_structure_invalid"),
    ],
)
def test_png_contract_rejects_ambiguous_or_non_rgba8_inputs(
    tmp_path: Path,
    variant: str,
    reason: str,
) -> None:
    png_path = tmp_path / "input.png"
    if variant == "rgb":
        _write_png(png_path, color_type=2)
    elif variant == "no_srgb":
        _write_png(png_path, srgb=None)
    elif variant == "wrong_intent":
        _write_png(png_path, srgb=b"\x01")
    elif variant == "icc":
        _write_png(png_path, extras=((b"iCCP", b"profile\x00\x00invalid"),))
    elif variant == "interlace":
        _write_png(png_path, interlace=1)
    elif variant == "wrong_size":
        _write_png(png_path, width=11, height=8)
    else:
        payload = bytearray(_png_bytes(12, 8))
        payload[-8] ^= 0x01
        png_path.write_bytes(payload)

    plan = _plan(_row(png_path))

    assert plan["status"] == "unsafe"
    assert reason in plan["reasons"]


def test_materialization_rejects_plan_tamper_input_change_and_collision(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_static_appearance_bake import (
        write_static_appearance_bake,
    )

    input_path = tmp_path / "input.png"
    _write_png(input_path)
    plan = _plan(_row(input_path))

    tampered = copy.deepcopy(plan)
    tampered["source"]["effect"]["density"] = 0.9
    with pytest.raises(ValueError, match="effect hash mismatch"):
        write_static_appearance_bake(tampered, tmp_path / "tampered")

    changed = copy.deepcopy(plan)
    _write_png(input_path, rgba=bytes(reversed(_pixels(12, 8))))
    with pytest.raises(ValueError, match="input PNG changed after planning"):
        write_static_appearance_bake(changed, tmp_path / "changed")

    _write_png(input_path)
    plan = _plan(_row(input_path))
    artifact = write_static_appearance_bake(plan, tmp_path / "collision")
    output_path = Path(artifact["png_path"])
    output_path.write_bytes(b"not-the-content-addressed-png")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_static_appearance_bake(plan, tmp_path / "collision")
    assert output_path.read_bytes() == b"not-the-content-addressed-png"


def test_effect_or_exact_png_mutation_changes_source_identity(tmp_path: Path) -> None:
    first_path = tmp_path / "first.png"
    _write_png(first_path)
    first_row = _row(first_path)
    first = _plan(first_row)

    effect_row = copy.deepcopy(first_row)
    effect_row["style"]["effects"][0]["density"] = 0.43
    effect = _plan(effect_row)
    assert effect["effect_hash"] != first["effect_hash"]
    assert effect["source_hash"] != first["source_hash"]

    second_path = tmp_path / "second.png"
    rgba = bytearray(_pixels(12, 8))
    rgba[0] ^= 0x01
    _write_png(second_path, rgba=bytes(rgba))
    pixel = _plan(_row(second_path))
    assert pixel["effect_hash"] == first["effect_hash"]
    assert pixel["input_png"]["pixel_rgba_sha256"] != first["input_png"][
        "pixel_rgba_sha256"
    ]
    assert pixel["source_hash"] != first["source_hash"]


def test_safe_exact_noise_enters_schema14_baked_source_plan(tmp_path: Path) -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.unreal_umg_baked import (
        validate_umg_static_appearance_source_plan,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    document = _document(png_path)
    converted = painter_ui_to_umg_document(document)
    layer = converted["Layers"][0]
    report = preflight_painter_umg(document)

    assert converted["SchemaVersion"] == 14
    assert layer["Disposition"] == "Baked", layer["BlockReasons"]
    assert layer["BlockReasons"] == []
    assert report["ok"] is True, report["blockers"]
    assert report["counts"] == {
        "Native": 0,
        "Material": 0,
        "Baked": 1,
        "Blocked": 0,
    }
    assert report["bake_plans"] == [
        {
            "object_id": layer["Id"],
            "name": layer["Name"],
            "status": "available",
            "kind": "static_figma_appearance_png",
        }
    ]
    assert validate_umg_static_appearance_source_plan(
        layer,
        document_schema_version=14,
    ) == []
    assert validate_umg_static_appearance_source_plan(
        layer,
        document_schema_version=13,
    ) == ["baked_static_appearance_requires_schema_14"]


def test_safe_exact_texture_enters_schema15_and_only_satisfies_texture_gate(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )
    from app.unreal_umg_baked import (
        validate_umg_static_appearance_source_plan,
    )
    from app.unreal_umg_static_appearance_bake import (
        STATIC_TEXTURE_BAKE_INTENDED_GATE,
        STATIC_TEXTURE_BAKE_KIND,
        STATIC_TEXTURE_BAKE_SCHEMA,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    document = _texture_document(png_path)
    converted = painter_ui_to_umg_document(document)
    layer = converted["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    bake = payload["static_appearance_bake"]
    report = preflight_painter_umg(document)

    assert converted["SchemaVersion"] == 15
    assert layer["Disposition"] == "Baked"
    assert layer["BlockReasons"] == []
    assert payload["painter_conversion"] == "static_texture_png_bake"
    assert payload["umg_mapping"] == "package_time_texture2d_image_fill"
    assert bake["kind"] == STATIC_TEXTURE_BAKE_KIND
    assert bake["source"]["schema"] == STATIC_TEXTURE_BAKE_SCHEMA
    assert bake["intended_gate"] == STATIC_TEXTURE_BAKE_INTENDED_GATE
    assert bake["gate_transition"] == {
        "before": [STATIC_TEXTURE_BAKE_INTENDED_GATE],
        "after": [],
        "satisfied": [STATIC_TEXTURE_BAKE_INTENDED_GATE],
    }
    assert report["ok"] is True, report["blockers"]
    assert validate_umg_static_appearance_source_plan(
        layer,
        document_schema_version=15,
    ) == []
    assert validate_umg_static_appearance_source_plan(
        layer,
        document_schema_version=14,
    ) == ["baked_static_texture_requires_schema_15"]


def test_exact_texture_gate_never_removes_an_unrelated_blocker(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_static_appearance_bake import (
        STATIC_TEXTURE_BAKE_INTENDED_GATE,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    document = _texture_document(png_path)
    document["objects"][0]["content"]["figma_variable_bindings"] = [
        {"status": "blocked", "id": "VariableID:texture"}
    ]
    converted = painter_ui_to_umg_document(document)
    layer = converted["Layers"][0]
    bake = json.loads(layer["PayloadJson"])["static_appearance_bake"]

    assert converted["SchemaVersion"] == 13
    assert layer["Disposition"] == "Blocked"
    assert layer["BlockReasons"] == [
        "figma_variable_binding_requires_token_relink"
    ]
    assert bake["gate_transition"]["satisfied"] == [
        STATIC_TEXTURE_BAKE_INTENDED_GATE
    ]
    assert bake["gate_transition"]["after"] == layer["BlockReasons"]


def test_schema15_texture_rejects_kind_schema_or_gate_tuple_tamper(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_baked import (
        validate_umg_static_appearance_source_plan,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    layer = painter_ui_to_umg_document(
        _texture_document(png_path)
    )["Layers"][0]

    gate_tamper = copy.deepcopy(layer)
    payload = json.loads(gate_tamper["PayloadJson"])
    payload["static_appearance_bake"]["intended_gate"] = (
        "figma_noise_effect_requires_ui_material_or_deterministic_bake"
    )
    gate_tamper["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    assert "baked_static_appearance_intended_gate_invalid" in (
        validate_umg_static_appearance_source_plan(
            gate_tamper,
            document_schema_version=15,
        )
    )

    schema_tamper = copy.deepcopy(layer)
    payload = json.loads(schema_tamper["PayloadJson"])
    payload["static_appearance_bake"]["source"]["schema"] = (
        "tigerstudio.umg.static_appearance_bake.v1"
    )
    schema_tamper["PayloadJson"] = json.dumps(
        payload,
        separators=(",", ":"),
    )
    reasons = validate_umg_static_appearance_source_plan(
        schema_tamper,
        document_schema_version=15,
    )
    assert "baked_static_appearance_schema_unsupported" in reasons
    assert "baked_static_appearance_source_hash_mismatch" in reasons


def test_schema14_source_preflight_rejects_plan_gate_or_input_tamper(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document
    from app.unreal_umg_baked import (
        validate_umg_static_appearance_source_plan,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    layer = painter_ui_to_umg_document(_document(png_path))["Layers"][0]

    mutated = copy.deepcopy(layer)
    payload = json.loads(mutated["PayloadJson"])
    payload["static_appearance_bake"]["source"]["effect"]["density"] = 0.9
    mutated["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    reasons = validate_umg_static_appearance_source_plan(
        mutated,
        document_schema_version=14,
    )
    assert "baked_static_appearance_effect_hash_mismatch" in reasons
    assert "baked_static_appearance_source_hash_mismatch" in reasons

    mutated = copy.deepcopy(layer)
    payload = json.loads(mutated["PayloadJson"])
    payload["static_appearance_bake"]["gate_transition"]["after"] = [
        "unrelated_blocker"
    ]
    mutated["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    assert "baked_static_appearance_gate_transition_invalid" in (
        validate_umg_static_appearance_source_plan(
            mutated,
            document_schema_version=14,
        )
    )

    png_path.write_bytes(b"changed-after-source-plan")
    assert "baked_static_appearance_source_not_reproducible" in (
        validate_umg_static_appearance_source_plan(
            layer,
            document_schema_version=14,
        )
    )


def test_schema14_package_materializes_typed_image_without_expanding_layout(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import (
        package_painter_umg,
        painter_ui_to_umg_document,
    )
    from app.unreal_umg_document import preflight_umg_document

    png_path = tmp_path / "input.png"
    _write_png(
        png_path,
        extras=((b"tEXt", b"Request\x00exact-figma-noise"),),
    )
    document = _document(png_path)
    planned = painter_ui_to_umg_document(document)["Layers"][0]
    package = package_painter_umg(document, tmp_path / "package")

    assert package["ok"] is True, {
        "source": package["preflight"],
        "packaged": package["packaged_preflight"],
    }
    assert package["preflight"]["counts"]["Baked"] == 1
    assert package["packaged_preflight"]["counts"]["Baked"] == 1
    assert len(package["static_bakes"]) == 1
    artifact = package["static_bakes"][0]
    assert artifact["kind"] == "static_figma_appearance_png"
    layer = package["document"]["Layers"][0]
    for key in (
        "Size",
        "Anchor",
        "RenderTransformPivot",
        "Position",
        "RotationDegrees",
        "CanvasSlot",
    ):
        assert layer[key] == planned[key]
    assert layer["Disposition"] == "Baked"
    assert layer["Kind"] == "Image"
    assert layer["ImageFill"]["Mode"] == "Stretch"
    assert layer["ImageFill"]["SourceSize"] == planned["Size"]
    assert layer["AssetId"].startswith("texture_")
    payload = json.loads(layer["PayloadJson"])
    bake = payload["static_appearance_bake"]
    assert bake["status"] == "materialized"
    assert "intended_gate" not in bake
    assert "intended_gate" not in bake["source"]
    assert bake["satisfied_gate"] == (
        "figma_noise_effect_requires_ui_material_or_deterministic_bake"
    )
    assert bake["gate_transition"]["satisfied"] == [bake["satisfied_gate"]]
    assert bake["layout_preservation"]["Size"] == planned["Size"]
    assert bake["source_canonical_json"] == json.dumps(
        bake["source"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert hashlib.sha256(
        bake["source_canonical_json"].encode("utf-8")
    ).hexdigest() == bake["source_hash"]
    assert hashlib.sha256(
        bake["effect_canonical_json"].encode("utf-8")
    ).hexdigest() == bake["effect_hash"]
    assert bake["umg_support_claimed"] is True

    generic = preflight_umg_document(
        package["document"],
        document_path=package["document_path"],
    )
    assert generic["ok"] is True, generic["blockers"]


def test_schema15_texture_package_materializes_distinct_typed_contract(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.unreal_umg_baked import validate_umg_materialized_baked_layer
    from app.unreal_umg_document import preflight_umg_document
    from app.unreal_umg_static_appearance_bake import (
        STATIC_TEXTURE_BAKE_INTENDED_GATE,
        STATIC_TEXTURE_BAKE_KIND,
        STATIC_TEXTURE_BAKE_SCHEMA,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    package = package_painter_umg(
        _texture_document(png_path),
        tmp_path / "package",
    )

    assert package["ok"] is True, package["packaged_preflight"]
    assert package["document"]["SchemaVersion"] == 15
    assert len(package["static_bakes"]) == 1
    artifact = package["static_bakes"][0]
    assert artifact["schema"] == STATIC_TEXTURE_BAKE_SCHEMA
    assert artifact["kind"] == STATIC_TEXTURE_BAKE_KIND
    assert artifact["intended_gate"] == STATIC_TEXTURE_BAKE_INTENDED_GATE
    assert artifact["integration_status"] == (
        "tigerstudio_umg_schema15_artifact"
    )
    assert Path(artifact["png_path"]).name.startswith("TS_Texture_")
    assert artifact["layout_preservation"]["policy"] == (
        "preserve_exact_layer_layout"
    )
    assert "layout_adjustment" not in artifact

    document = package["document"]
    layer = document["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    bake = payload["static_appearance_bake"]
    assert payload["painter_conversion"] == "static_texture_png_bake"
    assert payload["umg_mapping"] == (
        "texture2d_image_fill_from_static_texture_bake"
    )
    assert bake["kind"] == STATIC_TEXTURE_BAKE_KIND
    assert bake["intended_gate"] == STATIC_TEXTURE_BAKE_INTENDED_GATE
    assert bake["satisfied_gate"] == STATIC_TEXTURE_BAKE_INTENDED_GATE
    assert bake["integration_status"] == (
        "tigerstudio_umg_schema15_materialized"
    )
    package_root = Path(package["document_path"]).parent
    assert validate_umg_materialized_baked_layer(
        layer,
        document_schema_version=15,
        resources=document["Resources"],
        resource_base_path=package_root,
    ) == []
    assert validate_umg_materialized_baked_layer(
        layer,
        document_schema_version=14,
        resources=document["Resources"],
        resource_base_path=package_root,
    ) == ["baked_static_texture_requires_schema_15"]
    assert preflight_umg_document(
        document,
        document_path=package["document_path"],
    )["ok"] is True


def test_schema14_mixed_package_keeps_schema13_vector_bake_behavior(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import (
        package_painter_umg,
        painter_ui_to_umg_document,
    )
    from app.unreal_umg_document import preflight_umg_document

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    document = _document(png_path)
    vector = {
        "id": "figma-vector-1",
        "kind": "path",
        "name": "Static vector",
        "artboard_id": document["active_artboard_id"],
        "parent_id": "",
        "x": 80.0,
        "y": 90.0,
        "width": 40.0,
        "height": 30.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "visible": True,
        "locked": False,
        "clip_content": False,
        "z_index": 1,
        "constraints": {"horizontal": "left", "vertical": "top"},
        "layout": {},
        "style": {
            "fill": "#336699FF",
            "fills": [
                {
                    "type": "solid",
                    "visible": True,
                    "opacity": 1.0,
                    "color": "#336699FF",
                    "blend_mode": "normal",
                }
            ],
            "stroke": "#00000000",
            "stroke_width": 0.0,
            "strokes": [],
            "blend_mode": "normal",
            "radius": 0.0,
            "corner_radii": {
                "top_left": 0.0,
                "top_right": 0.0,
                "bottom_right": 0.0,
                "bottom_left": 0.0,
            },
            "corner_smoothing": 0.0,
            "effects": [],
        },
        "content": {
            "figma_node_id": "3:1",
            "figma_type": "VECTOR",
            "vector_fill_geometry": [
                {
                    "path": "M 0 30 L 20 0 L 40 30 Z",
                    "winding_rule": "nonzero",
                }
            ],
            "vector_paths": ["M 0 30 L 20 0 L 40 30 Z"],
            "boolean": {"enabled": False},
        },
        "mask": {"enabled": False},
        "token_bindings": {},
        "accessibility": {},
    }
    document["objects"].append(vector)
    planned = painter_ui_to_umg_document(document)
    planned_by_id = {row["Id"]: row for row in planned["Layers"]}
    package = package_painter_umg(document, tmp_path / "package")
    baked_by_id = {row["Id"]: row for row in package["document"]["Layers"]}

    assert planned["SchemaVersion"] == 14
    assert package["ok"] is True
    assert package["preflight"]["counts"]["Baked"] == 2
    assert {artifact["kind"] for artifact in package["static_bakes"]} == {
        "static_figma_appearance_png",
        "static_vector_png",
    }
    assert baked_by_id["figma-2-1"]["Size"] == planned_by_id[
        "figma-2-1"
    ]["Size"]
    assert baked_by_id["figma-vector-1"]["Size"] == {"X": 44.0, "Y": 34.0}
    assert preflight_umg_document(
        package["document"],
        document_path=package["document_path"],
    )["ok"] is True


def test_exact_noise_gate_does_not_remove_an_unrelated_blocker(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import (
        painter_ui_to_umg_document,
        preflight_painter_umg,
    )

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    document = _document(png_path)
    document["objects"][0]["content"]["figma_variable_bindings"] = [
        {"status": "blocked", "id": "VariableID:1:2"}
    ]
    converted = painter_ui_to_umg_document(document)
    layer = converted["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    appearance = payload["static_appearance_bake"]
    report = preflight_painter_umg(document)

    assert converted["SchemaVersion"] == 13
    assert appearance["available"] is True
    assert appearance["gate_transition"]["satisfied"] == [
        "figma_noise_effect_requires_ui_material_or_deterministic_bake"
    ]
    assert appearance["gate_transition"]["after"] == [
        "figma_variable_binding_requires_token_relink"
    ]
    assert layer["Disposition"] == "Blocked"
    assert layer["BlockReasons"] == [
        "figma_variable_binding_requires_token_relink"
    ]
    assert report["ok"] is False
    assert report["counts"]["Blocked"] == 1


def test_missing_exact_render_never_satisfies_noise_gate(tmp_path: Path) -> None:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    png_path = tmp_path / "input.png"
    _write_png(png_path)
    document = _document(png_path)
    document["objects"][0]["content"].pop("figma_exact_render")
    converted = painter_ui_to_umg_document(document)
    layer = converted["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    appearance = payload["static_appearance_bake"]

    assert converted["SchemaVersion"] == 13
    assert layer["Disposition"] == "Blocked"
    assert appearance["status"] == "unsafe"
    assert appearance["gate_transition"]["satisfied"] == []
    assert (
        "figma_noise_effect_requires_ui_material_or_deterministic_bake"
        in layer["BlockReasons"]
    )
    assert (
        "figma_appearance_static_bake_exact_render_record_missing"
        in layer["BlockReasons"]
    )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("source_hash", "baked_static_appearance_source_hash_mismatch"),
        ("effect_hash", "baked_static_appearance_effect_hash_mismatch"),
        (
            "source_canonical",
            "baked_static_appearance_source_json_not_canonical",
        ),
        (
            "effect_canonical",
            "baked_static_appearance_effect_canonical_json_mismatch",
        ),
        ("provenance", "baked_static_appearance_provenance_invalid"),
        ("layout", "baked_static_appearance_layout_changed"),
        ("layer_size", "baked_static_appearance_layout_changed"),
        ("gate", "baked_static_appearance_gate_transition_invalid"),
        ("satisfied_gate", "baked_satisfied_gate_invalid"),
        ("mapping", "baked_payload_mapping_invalid"),
        ("image_fill", "baked_image_fill_contract_invalid"),
        ("resource_hash", "baked_resource_content_hash_mismatch"),
        ("manifest_hash", "baked_manifest_file_hash_mismatch"),
        ("source_pixel_hash", "baked_static_appearance_pixel_rgba_sha256_invalid"),
        ("logical_too_large", "baked_static_appearance_logical_size_invalid"),
        ("hidden_effect", "baked_static_appearance_effect_invalid"),
    ],
)
def test_schema14_materialized_contract_rejects_hash_provenance_or_layout_tamper(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.unreal_umg_baked import validate_umg_materialized_baked_layer

    input_path = tmp_path / "input.png"
    _write_png(input_path)
    package = package_painter_umg(_document(input_path), tmp_path / "package")
    document = copy.deepcopy(package["document"])
    layer = document["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    bake = payload["static_appearance_bake"]
    if mutation == "source_hash":
        bake["source_hash"] = "0" * 64
    elif mutation == "effect_hash":
        bake["effect_hash"] = "0" * 64
    elif mutation == "source_canonical":
        bake["source_canonical_json"] += " "
    elif mutation == "effect_canonical":
        bake["effect_canonical_json"] = "{}"
    elif mutation == "provenance":
        bake["provenance"]["figma_node_id"] = "9:9"
    elif mutation == "layout":
        bake["layout_preservation"]["Size"]["X"] += 1.0
    elif mutation == "layer_size":
        layer["Size"]["X"] += 1.0
    elif mutation == "gate":
        bake["gate_transition"]["after"] = ["unrelated_blocker"]
    elif mutation == "satisfied_gate":
        bake["satisfied_gate"] = "some_other_gate"
    elif mutation == "mapping":
        payload["umg_mapping"] = "native_or_converted"
    elif mutation == "image_fill":
        layer["ImageFill"]["Tint"] = "#FF00FFFF"
    elif mutation == "resource_hash":
        document["Resources"][0]["ContentHash"] = "0" * 64
    elif mutation == "manifest_hash":
        bake["manifest_sha256"] = "0" * 64
    elif mutation == "source_pixel_hash":
        bake["source"]["pixel_rgba_sha256"] = "not-a-hash"
    elif mutation == "logical_too_large":
        bake["source"]["logical_size"]["width"] = 4097.0
        bake["source"]["pixel_size"]["width"] = 4097
    else:
        bake["source"]["effect"]["visible"] = False
    layer["PayloadJson"] = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    reasons = validate_umg_materialized_baked_layer(
        layer,
        document_schema_version=14,
        resources=document["Resources"],
        resource_base_path=Path(package["document_path"]).parent,
    )

    assert reason in reasons


def test_materialized_appearance_is_rejected_by_schema13_and_png_tamper(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.unreal_umg_baked import validate_umg_materialized_baked_layer

    input_path = tmp_path / "input.png"
    _write_png(input_path)
    package = package_painter_umg(_document(input_path), tmp_path / "package")
    document = package["document"]
    layer = document["Layers"][0]
    root = Path(package["document_path"]).parent

    assert validate_umg_materialized_baked_layer(
        layer,
        document_schema_version=13,
        resources=document["Resources"],
        resource_base_path=root,
    ) == ["baked_static_appearance_requires_schema_14"]

    resource_path = root / document["Resources"][0]["SourcePath"]
    resource_path.write_bytes(b"not-a-valid-exact-render")
    reasons = validate_umg_materialized_baked_layer(
        layer,
        document_schema_version=14,
        resources=document["Resources"],
        resource_base_path=root,
    )
    assert "baked_static_appearance_png_invalid" in reasons
