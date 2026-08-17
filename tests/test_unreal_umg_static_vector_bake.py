from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _vector_document(
    *,
    horizontal: str = "left",
    vertical: str = "top",
    pivot_x: float = 0.25,
    pivot_y: float = 0.75,
) -> dict:
    from app.painter_ui_constraints import capture_ui_constraints
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, _row = add_ui_object(
        create_ui_document(320, 240),
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
            # Import/round-trip code has historically used both forms.
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
    authored = document["objects"][0]
    authored["rotation"] = 31.0
    authored["constraints"] = capture_ui_constraints(
        authored,
        {"x": 0.0, "y": 0.0, "width": 320.0, "height": 240.0},
        {
            "horizontal": horizontal,
            "vertical": vertical,
            "pivot_x": pivot_x,
            "pivot_y": pivot_y,
        },
    )
    document["artboards"][0]["background"] = "#00000000"
    return document


def _layer(document: dict) -> dict:
    from app.painter_ui_umg_adapter import painter_ui_to_umg_document

    return painter_ui_to_umg_document(document)["Layers"][0]


def test_pure_preflight_reports_available_baked_plan_without_claiming_native() -> None:
    from app.painter_ui_umg_adapter import preflight_painter_umg

    report = preflight_painter_umg(_vector_document())

    assert report["ok"] is True
    assert report["counts"] == {
        "Native": 0,
        "Material": 0,
        "Baked": 1,
        "Blocked": 0,
    }
    assert report["bake_plans"] == [
        {
            "object_id": report["bake_plans"][0]["object_id"],
            "name": "Path",
            "status": "available",
            "kind": "static_vector_png",
        }
    ]
    layer = _layer(_vector_document())
    assert layer["Disposition"] == "Baked"
    payload = json.loads(layer["PayloadJson"])
    assert payload["umg_mapping"] == "package_time_texture2d_image_fill"
    assert payload["static_vector_bake"]["source"]["fill_rgba"] == [
        51,
        102,
        153,
        128,
    ]


def test_source_plan_and_materialized_record_use_distinct_validation_states() -> None:
    from app.unreal_umg_baked import validate_umg_static_vector_source_plan

    layer = _layer(_vector_document())
    assert validate_umg_static_vector_source_plan(layer) == []

    payload = json.loads(layer["PayloadJson"])
    payload["static_vector_bake"]["source_hash"] = "0" * 64
    layer["PayloadJson"] = json.dumps(payload, separators=(",", ":"))
    assert "baked_static_vector_source_hash_mismatch" in (
        validate_umg_static_vector_source_plan(layer)
    )


@pytest.mark.parametrize("anchor_mode", ["left", "center", "right"])
def test_package_bake_preserves_point_anchor_rotation_and_world_pivot(
    tmp_path: Path,
    anchor_mode: str,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg

    document = _vector_document(
        horizontal=anchor_mode,
        vertical={"left": "top", "center": "center", "right": "bottom"}[
            anchor_mode
        ],
        pivot_x=0.2,
        pivot_y=0.8,
    )
    planned = _layer(document)
    package = package_painter_umg(document, tmp_path / anchor_mode)

    assert package["ok"] is True
    assert package["preflight"]["counts"]["Baked"] == 1
    assert package["packaged_preflight"]["counts"]["Baked"] == 1
    assert package["preflight"]["bake_plans"][0]["status"] == "available"
    assert package["packaged_preflight"]["bake_plans"][0]["status"] == (
        "materialized"
    )
    baked = package["document"]["Layers"][0]
    assert baked["Disposition"] == "Baked"
    assert baked["ImageFill"]["Mode"] == "Stretch"
    assert baked["AssetId"].startswith("texture_")
    assert baked["RotationDegrees"] == pytest.approx(planned["RotationDegrees"])
    assert baked["Position"] == planned["Position"]
    assert baked["CanvasSlot"]["AnchorMinimum"] == planned["CanvasSlot"][
        "AnchorMinimum"
    ]
    assert baked["CanvasSlot"]["AnchorMaximum"] == planned["CanvasSlot"][
        "AnchorMaximum"
    ]
    assert baked["CanvasSlot"]["Offsets"]["Left"] == pytest.approx(
        planned["CanvasSlot"]["Offsets"]["Left"]
    )
    assert baked["CanvasSlot"]["Offsets"]["Top"] == pytest.approx(
        planned["CanvasSlot"]["Offsets"]["Top"]
    )
    assert baked["Size"] == {"X": 44.0, "Y": 34.0}
    assert baked["CanvasSlot"]["Offsets"]["Right"] == pytest.approx(44.0)
    assert baked["CanvasSlot"]["Offsets"]["Bottom"] == pytest.approx(34.0)

    # Position is the unchanged world pivot. The expanded top-left plus the
    # transparent padding lands on the original unexpanded top-left.
    original_left = planned["Position"]["X"] - (
        planned["RenderTransformPivot"]["X"] * planned["Size"]["X"]
    )
    original_top = planned["Position"]["Y"] - (
        planned["RenderTransformPivot"]["Y"] * planned["Size"]["Y"]
    )
    expanded_left = baked["Position"]["X"] - (
        baked["RenderTransformPivot"]["X"] * baked["Size"]["X"]
    )
    expanded_top = baked["Position"]["Y"] - (
        baked["RenderTransformPivot"]["Y"] * baked["Size"]["Y"]
    )
    assert expanded_left + 2.0 == pytest.approx(original_left)
    assert expanded_top + 2.0 == pytest.approx(original_top)


def test_package_writes_deterministic_alpha_png_manifest_and_reuses_identical(
    tmp_path: Path,
) -> None:
    from PySide6.QtGui import QImage

    from app.painter_ui_umg_adapter import package_painter_umg

    _app()
    output = tmp_path / "package"
    first = package_painter_umg(_vector_document(), output)
    second = package_painter_umg(_vector_document(), output)
    artifact = first["static_bakes"][0]
    png_path = Path(artifact["png_path"])
    manifest_path = Path(artifact["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert artifact["reused"] is False
    assert second["static_bakes"][0]["reused"] is True
    assert manifest["content_hash"] == hashlib.sha256(png_path.read_bytes()).hexdigest()
    assert manifest["source_hash"] == artifact["source_hash"]
    image = QImage(str(png_path))
    assert (image.width(), image.height()) == (44, 34)
    assert image.pixelColor(0, 0).alpha() == 0
    assert image.pixelColor(22, 20).alpha() in {127, 128}
    assert image.pixelColor(43, 0).alpha() == 0
    alpha_points = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    ]
    assert min(x for x, _y in alpha_points) >= 2
    assert max(x for x, _y in alpha_points) <= 41
    assert min(y for _x, y in alpha_points) >= 2
    assert max(y for _x, y in alpha_points) <= 31


def test_schema_13_generic_preflight_accepts_only_materialized_baked_package(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.unreal_umg_document import preflight_umg_document

    package = package_painter_umg(_vector_document(), tmp_path)
    report = preflight_umg_document(
        package["document"],
        document_path=package["document_path"],
    )

    assert report["ok"] is True
    assert report["counts"] == {
        "Native": 0,
        "Material": 0,
        "Baked": 1,
        "Blocked": 0,
    }
    assert report["blockers"] == []

    legacy = json.loads(json.dumps(package["document"]))
    legacy["SchemaVersion"] = 12
    legacy_report = preflight_umg_document(legacy)
    assert legacy_report["ok"] is False
    assert legacy_report["blockers"][0]["reasons"] == [
        "baked_generation_unavailable"
    ]


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("kind", "baked_static_vector_layer_kind_unsupported"),
        ("crop", "baked_image_fill_contract_invalid"),
        ("tint", "baked_image_fill_contract_invalid"),
        ("material", "baked_conflicting_visual_record"),
        ("asset_id", "baked_asset_id_mismatch"),
        ("status", "baked_materialization_record_invalid"),
        ("content_hash", "baked_resource_content_hash_mismatch"),
    ],
)
def test_schema_13_materialized_baked_contract_rejects_visual_or_provenance_tamper(
    tmp_path: Path,
    mutation: str,
    reason: str,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.unreal_umg_document import preflight_umg_document

    document = package_painter_umg(_vector_document(), tmp_path)["document"]
    layer = document["Layers"][0]
    payload = json.loads(layer["PayloadJson"])
    if mutation == "kind":
        layer["Kind"] = "Shape"
    elif mutation == "crop":
        layer["ImageFill"]["Crop"]["Enabled"] = True
    elif mutation == "tint":
        layer["ImageFill"]["Tint"] = "#FF00FFFF"
    elif mutation == "material":
        layer["Material"] = {"Schema": "unexpected"}
    elif mutation == "asset_id":
        layer["ImageFill"]["AssetId"] = "texture_other"
    elif mutation == "status":
        payload["static_vector_bake"]["status"] = "available"
    elif mutation == "content_hash":
        document["Resources"][0]["ContentHash"] = "0" * 64
    layer["PayloadJson"] = json.dumps(payload, separators=(",", ":"))

    report = preflight_umg_document(document)

    assert report["ok"] is False
    assert reason in report["blockers"][0]["reasons"]


def test_simulator_projects_valid_packaged_baked_as_typed_uimage(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from app.painter_ui_umg_simulator import project_tiger_umg_document

    package = package_painter_umg(_vector_document(), tmp_path)
    packaged = package["document"]
    packaged["Resources"][0]["SourcePath"] = package["static_bakes"][0][
        "png_path"
    ]

    projection = project_tiger_umg_document(packaged)
    widget = projection["widgets"][0]

    assert projection["ready"] is True
    assert projection["complete"] is True
    assert widget["disposition"] == "Baked"
    assert widget["rendered"] is True
    assert widget["widget_class"] == "UImage"
    assert widget["generator_action"] == "construct_baked"
    assert "ImageFill.AssetId" in widget["consumed_properties"]


def test_static_bake_mutation_changes_identity_and_collision_never_overwrites(
    tmp_path: Path,
) -> None:
    from app.unreal_umg_static_vector_bake import (
        plan_static_vector_bake,
        write_static_vector_bake,
    )

    row = _vector_document()["objects"][0]
    plan = plan_static_vector_bake(
        row,
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    artifact = write_static_vector_bake(plan, tmp_path)
    mutated = json.loads(json.dumps(row))
    mutated["style"]["fills"][0]["color"] = "#FF0000FF"
    mutated_plan = plan_static_vector_bake(
        mutated,
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    mutated_artifact = write_static_vector_bake(mutated_plan, tmp_path)
    assert mutated_plan["source_hash"] != plan["source_hash"]
    assert mutated_artifact["png_path"] != artifact["png_path"]

    collision_path = Path(artifact["png_path"])
    collision_path.write_bytes(b"not-the-content-addressed-png")
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        write_static_vector_bake(plan, tmp_path)
    assert collision_path.read_bytes() == b"not-the-content-addressed-png"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("stroke", "figma_vector_static_bake_stroke_unsupported"),
        ("effect", "figma_vector_static_bake_effect_unsupported"),
        ("mask", "figma_vector_static_bake_mask_unsupported"),
        ("boolean", "figma_vector_static_bake_boolean_unsupported"),
        ("child", "figma_vector_static_bake_requires_leaf"),
        ("gap", "figma_vector_static_bake_geometry_incomplete"),
    ],
)
def test_unsafe_vector_cases_remain_explicitly_blocked(
    mutation: str,
    reason: str,
) -> None:
    from app.painter_ui_document import add_ui_object
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = _vector_document()
    row = document["objects"][0]
    if mutation == "stroke":
        # A single center-aligned solid stroke that fits inside the bake's
        # padding is now composited into the bake (see stroke_rgba/
        # stroke_width). Use two strokes here so this case still exercises
        # the genuinely-unsupported path.
        row["style"]["strokes"] = [
            {"type": "solid", "visible": True, "color": "#FFFFFFFF", "width": 2},
            {"type": "solid", "visible": True, "color": "#000000FF", "width": 1},
        ]
    elif mutation == "effect":
        row["style"]["effects"] = [
            {"type": "drop_shadow", "visible": True, "color": "#00000080"}
        ]
    elif mutation == "mask":
        row["mask"] = {"enabled": True}
    elif mutation == "boolean":
        row["content"]["boolean"] = {"enabled": True, "operation": "union"}
    elif mutation == "child":
        document, _child = add_ui_object(
            document,
            kind="rectangle",
            parent_id=row["id"],
            x=65,
            y=50,
            width=5,
            height=5,
        )
    else:
        row["content"]["vector_fill_geometry"][0]["path"] = "M 0 0 L 40 0"
        row["content"]["vector_paths"] = ["M 0 0 L 40 0"]

    report = preflight_painter_umg(document)
    blocker = next(
        item
        for item in report["blockers"]
        if item["object_id"] == row["id"]
    )
    assert reason in blocker["reasons"]
    assert "figma_vector_geometry_requires_deterministic_bake" in blocker["reasons"]


def test_stretched_vector_plan_stays_blocked_and_layout_expansion_rejects_stretch() -> None:
    from app.unreal_umg_static_vector_bake import expand_umg_layer_for_static_bake

    document = _vector_document(horizontal="stretch", vertical="stretch")
    layer = _layer(document)
    assert layer["Disposition"] == "Blocked"
    assert "figma_vector_static_bake_requires_fixed_size" in layer["BlockReasons"]

    fixed_layer = _layer(_vector_document())
    payload = json.loads(fixed_layer["PayloadJson"])
    fixed_layer["CanvasSlot"]["AnchorMaximum"]["X"] = 1.0
    with pytest.raises(ValueError, match="stretched Canvas slot"):
        expand_umg_layer_for_static_bake(
            fixed_layer,
            payload["static_vector_bake"],
        )


@pytest.mark.parametrize(
    ("path", "expected_reason"),
    [
        (
            "M 0 0 X 10 10 Z",
            "figma_vector_static_bake_path_syntax_or_complexity_unsupported",
        ),
        (
            "M 0 0 Z",
            "figma_vector_static_bake_visible_geometry_missing",
        ),
        (
            "M 100 100 L 120 100 L 110 120 Z",
            "figma_vector_static_bake_visible_geometry_missing",
        ),
        (
            "M 0 0 L 10 0 L 10 10 Z M 20 20 L 30 20",
            "figma_vector_static_bake_path_syntax_or_complexity_unsupported",
        ),
    ],
)
def test_invalid_degenerate_outside_and_partly_open_paths_stay_blocked(
    path: str,
    expected_reason: str,
) -> None:
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = _vector_document()
    row = document["objects"][0]
    row["content"]["vector_fill_geometry"] = [
        {"path": path, "winding_rule": "nonzero"}
    ]
    row["content"]["vector_paths"] = [path]

    report = preflight_painter_umg(document)
    blocker = next(
        item for item in report["blockers"] if item["object_id"] == row["id"]
    )

    assert report["counts"]["Baked"] == 0
    assert "figma_vector_geometry_requires_deterministic_bake" in blocker["reasons"]
    assert expected_reason in blocker["reasons"]


def test_unknown_winding_rule_stays_explicitly_blocked() -> None:
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = _vector_document()
    row = document["objects"][0]
    row["content"]["vector_fill_geometry"][0]["winding_rule"] = "future-rule"

    report = preflight_painter_umg(document)
    blocker = next(
        item for item in report["blockers"] if item["object_id"] == row["id"]
    )

    assert "figma_vector_static_bake_winding_rule_unsupported" in blocker["reasons"]


def test_standard_relative_and_arc_svg_commands_are_in_the_pinned_subset() -> None:
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = _vector_document()
    row = document["objects"][0]
    path = "M 5 15 a 10 10 0 1 1 20 0 a 10 10 0 1 1 -20 0 Z"
    row["content"]["vector_fill_geometry"] = [
        {"path": path, "winding_rule": "evenodd"}
    ]
    row["content"]["vector_paths"] = [path]

    report = preflight_painter_umg(document)

    assert report["ok"] is True
    assert report["counts"]["Baked"] == 1


def test_transparent_fill_stays_blocked_instead_of_becoming_empty_native_image() -> None:
    from app.painter_ui_umg_adapter import preflight_painter_umg

    document = _vector_document()
    document["objects"][0]["style"]["fills"][0]["opacity"] = 0.0

    report = preflight_painter_umg(document)
    reasons = report["blockers"][0]["reasons"]

    assert report["counts"]["Baked"] == 0
    assert "figma_vector_static_bake_transparent_fill_unsupported" in reasons


def test_geometry_complexity_cap_is_enforced_before_qt_svg_render(
    monkeypatch,
) -> None:
    import app.unreal_umg_static_vector_bake as static_bake

    monkeypatch.setattr(static_bake, "STATIC_VECTOR_BAKE_MAX_PATH_TOKENS", 8)
    row = _vector_document()["objects"][0]

    plan = static_bake.plan_static_vector_bake(
        row,
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )

    assert plan["available"] is False
    assert "figma_vector_static_bake_path_syntax_or_complexity_unsupported" in plan[
        "reasons"
    ]


@pytest.mark.parametrize(
    ("field", "mutated"),
    [
        ("pixel_size", {"width": 100_000, "height": 100_000}),
        ("padding", {"left": 0, "top": 0, "right": 0, "bottom": 0}),
        ("logical_size", {"width": 4000.0, "height": 3000.0}),
        ("layout_policy", "mutated"),
    ],
)
def test_writer_rederives_and_rejects_unhashed_plan_field_mutation(
    tmp_path: Path,
    field: str,
    mutated: object,
) -> None:
    from app.unreal_umg_static_vector_bake import (
        plan_static_vector_bake,
        write_static_vector_bake,
    )

    row = _vector_document()["objects"][0]
    plan = plan_static_vector_bake(
        row,
        resolved_size={"width": 40.0, "height": 30.0},
        has_children=False,
        runtime_size_dynamic=False,
    )
    plan[field] = mutated

    with pytest.raises(ValueError, match="mutated after preflight"):
        write_static_vector_bake(plan, tmp_path)


def test_manifest_keeps_renderer_source_pixel_hash_and_baked_provenance(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg

    package = package_painter_umg(_vector_document(), tmp_path)
    artifact = package["static_bakes"][0]
    manifest = json.loads(
        Path(artifact["manifest_path"]).read_text(encoding="utf-8")
    )

    assert len(manifest["pixel_rgba_sha256"]) == 64
    assert manifest["source"]["renderer"]["id"] == "qt_svg_fill_stroke_geometry_v4"
    assert manifest["source"]["geometry"][0]["path"].endswith("Z")
    assert manifest["origin_disposition"] == "Baked"
    assert manifest["satisfied_gate"] == (
        "figma_vector_geometry_requires_deterministic_bake"
    )


def test_hidden_vector_remains_hidden_after_bake_and_records_source_visibility(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg

    document = _vector_document()
    document["objects"][0]["visible"] = False
    planned = _layer(document)
    package = package_painter_umg(document, tmp_path)
    baked = package["document"]["Layers"][0]

    assert planned["Opacity"] == 0.0
    assert baked["Opacity"] == 0.0
    assert json.loads(baked["PayloadJson"])["source_visible"] is False
    assert package["preflight"]["counts"]["Baked"] == 1
    assert package["packaged_preflight"]["counts"]["Baked"] == 1


def test_unreal_pixel_gate_accepts_full_reference_and_rejects_shape_substitution(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _fixture,
        _image_evidence,
        _reference_capture,
    )

    package = package_painter_umg(_fixture(), tmp_path / "package")
    capture = _reference_capture(package)
    reference_path = tmp_path / "full_reference.png"
    capture.save(reference_path)
    reference = _image_evidence(reference_path, package)
    assert reference["ok"] is True
    assert reference["rotated_evenodd_ring"]["mask"]["iou"] == 1.0
    rotated_evidence = reference["rotated_evenodd_ring"]
    assert rotated_evidence["reference_projection"] == (
        "slate_pixel_snapped_box_two_triangle_piecewise_affine_uv_"
        "then_bilinear_png_alpha"
    )
    assert rotated_evidence["slate_pixel_snapping"]["triangle_indices"] == [
        [0, 1, 2],
        [2, 1, 3],
    ]

    substituted = capture.copy()
    primary_box = tuple(reference["primary_box"])
    rectangle = Image.new(
        "RGBA",
        (primary_box[2] - primary_box[0], primary_box[3] - primary_box[1]),
        (71, 175, 133, 127),
    )
    substituted.paste(rectangle, primary_box[:2])
    substituted_path = tmp_path / "substituted.png"
    substituted.save(substituted_path)
    evidence = _image_evidence(substituted_path, package)

    assert evidence["ok"] is False
    assert evidence["alpha_mask_exact"] is False
    assert evidence["alpha_error_pixel_count"] > 0


def test_unreal_rotated_reference_models_slate_pixel_snapped_quad(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _bilinear_alpha,
        _fixture,
        _mask_comparison,
        _slate_pixel_snapped_box_projection,
        _transformed_alpha_frame,
        _ue_round_to_float,
        _world_to_local,
    )

    package = package_painter_umg(_fixture(), tmp_path / "package")
    layers = {row["Name"]: row for row in package["document"]["Layers"]}
    artifacts = {row["object_id"]: row for row in package["static_bakes"]}
    rotated = layers["Rotated EvenOdd Ring"]
    with Image.open(artifacts[rotated["Id"]]["png_path"]) as source:
        ring_bake = source.convert("RGBA")

    projection = _slate_pixel_snapped_box_projection(rotated)
    exact_vertices = [
        [131.3987152568479, 49.38371816011363],
        [164.02579559016732, 64.59797558277882],
        [116.18445783418274, 82.01079849343303],
        [148.81153816750214, 97.22505591609821],
    ]
    for actual, expected in zip(
        projection["exact_world_vertices"],
        exact_vertices,
        strict=True,
    ):
        assert actual == pytest.approx(expected)
    assert projection["snapped_world_vertices"] == [
        [131.0, 49.0],
        [164.0, 65.0],
        [116.0, 82.0],
        [149.0, 97.0],
    ]
    assert projection["triangle_indices"] == [[0, 1, 2], [2, 1, 3]]
    assert _ue_round_to_float(10.5) == 11.0
    assert _ue_round_to_float(-10.5) == -10.0

    slate_reference = _transformed_alpha_frame(
        rotated,
        ring_bake,
        (192, 128),
    )
    exact_match = _mask_comparison(slate_reference, slate_reference)
    assert exact_match["iou"] == 1.0
    assert exact_match["expected"]["occupancy"] == 775
    assert exact_match["expected"]["bbox"] == [119, 52, 161, 94]

    # The old single inverse-transform reference is the Qt-style projection.
    # Its stable mismatch against the real UE golden (770 vs 775 pixels) is
    # what this Slate vertex-snapping model fixes without lowering IoU 0.98.
    source_alpha = ring_bake.getchannel("A")
    legacy_values: list[int] = []
    for y in range(128):
        for x in range(192):
            local_x, local_y = _world_to_local(rotated, x + 0.5, y + 0.5)
            legacy_values.append(
                _bilinear_alpha(source_alpha, local_x, local_y)
            )
    legacy_reference = Image.new("L", (192, 128), 0)
    legacy_reference.putdata(legacy_values)
    legacy_comparison = _mask_comparison(
        legacy_reference,
        slate_reference,
    )
    assert legacy_comparison["expected"]["occupancy"] == 770
    assert legacy_comparison["actual"]["occupancy"] == 775
    assert legacy_comparison["intersection"] == 759
    assert legacy_comparison["union"] == 786
    assert legacy_comparison["iou"] == pytest.approx(0.9656488549618321)


def test_unreal_pixel_gate_rejects_nine_pixel_ring_fake(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _fixture,
        _image_evidence,
        _reference_capture,
        _transformed_alpha_frame,
        _world_sample,
    )

    package = package_painter_umg(_fixture(), tmp_path / "package")
    layers = {row["Name"]: row for row in package["document"]["Layers"]}
    artifacts = {row["object_id"]: row for row in package["static_bakes"]}
    rotated = layers["Rotated EvenOdd Ring"]
    with Image.open(artifacts[rotated["Id"]]["png_path"]) as source:
        ring_bake = source.convert("RGBA")
    expected_ring = _transformed_alpha_frame(rotated, ring_bake, (192, 128))
    ring_bbox = expected_ring.getbbox()
    assert ring_bbox is not None

    fake = _reference_capture(package)
    fake.paste((0, 0, 0, 0), ring_bbox)
    solid_x, solid_y = _world_sample(rotated, 6.0, 18.0)
    for y in range(solid_y - 1, solid_y + 2):
        for x in range(solid_x - 1, solid_x + 2):
            fake.putpixel((x, y), (249, 115, 22, 255))
    fake_path = tmp_path / "nine_pixel_fake.png"
    fake.save(fake_path)

    evidence = _image_evidence(fake_path, package)
    mask = evidence["rotated_evenodd_ring"]["mask"]
    assert evidence["ok"] is False
    assert mask["ok"] is False
    assert mask["actual"]["occupancy"] <= 9
    assert mask["iou"] < 0.02


def test_unreal_pixel_gate_rejects_straight_srgb_in_translucent_capture(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _fixture,
        _image_evidence,
        _reference_capture,
    )

    package = package_painter_umg(_fixture(), tmp_path / "package")
    capture = _reference_capture(package)
    reference_path = tmp_path / "reference.png"
    capture.save(reference_path)
    reference = _image_evidence(reference_path, package)
    assert reference["ok"] is True

    wrong = capture.copy()
    pixels = wrong.load()
    left, top, right, bottom = reference["primary_box"]
    straight_rgb = tuple(
        reference["primary_color_contract"]["source_plateau_rgb"]
    )
    for y in range(top, bottom):
        for x in range(left, right):
            alpha = pixels[x, y][3]
            if alpha > 0:
                pixels[x, y] = (*straight_rgb, alpha)
    wrong_path = tmp_path / "straight_srgb_translucent.png"
    wrong.save(wrong_path)

    evidence = _image_evidence(wrong_path, package)
    assert evidence["ok"] is False
    assert evidence["alpha_mask_exact"] is True
    assert evidence["primary_rgb"]["ok"] is False
    assert evidence["primary_rgb"]["visible_rgb_error_pixel_count"] > 100


def test_unreal_pixel_gate_rejects_constant_color_at_bilinear_ring_fringe(
    tmp_path: Path,
) -> None:
    from PIL import Image

    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _fixture,
        _image_evidence,
        _linear_premultiplied_srgb_byte,
        _reference_capture,
        _transformed_alpha_frame,
    )

    package = package_painter_umg(_fixture(), tmp_path / "package")
    capture = _reference_capture(package)
    reference_path = tmp_path / "gpu_edge_reference.png"
    capture.save(reference_path)
    reference = _image_evidence(reference_path, package)
    assert reference["ok"] is True

    layers = {row["Name"]: row for row in package["document"]["Layers"]}
    artifacts = {row["object_id"]: row for row in package["static_bakes"]}
    rotated = layers["Rotated EvenOdd Ring"]
    with Image.open(artifacts[rotated["Id"]]["png_path"]) as source:
        ring_bake = source.convert("RGBA")
    expected_alpha = _transformed_alpha_frame(
        rotated,
        ring_bake,
        capture.size,
    )
    source_rgb = reference["rotated_evenodd_ring"]["color_contract"][
        "source_plateau_rgb"
    ]

    # This is the old fringe model: it ignores that bilinear filtering also
    # attenuates RGB against transparent-black texels before alpha blending.
    wrong = capture.copy()
    wrong_pixels = wrong.load()
    for index, expected_alpha_byte in enumerate(expected_alpha.tobytes()):
        if expected_alpha_byte <= 0:
            continue
        x = index % wrong.width
        y = index // wrong.width
        actual_alpha = wrong_pixels[x, y][3]
        if actual_alpha <= 0:
            continue
        wrong_rgb = (
            source_rgb
            if actual_alpha >= 254
            else [
                _linear_premultiplied_srgb_byte(channel, actual_alpha)
                for channel in source_rgb
            ]
        )
        wrong_pixels[x, y] = (*wrong_rgb, actual_alpha)
    wrong_path = tmp_path / "constant_color_ring_fringe.png"
    wrong.save(wrong_path)

    evidence = _image_evidence(wrong_path, package)
    ring = evidence["rotated_evenodd_ring"]
    assert evidence["ok"] is False
    assert evidence["primary_rgb"]["ok"] is True
    assert ring["mask"]["iou"] == 1.0
    assert ring["rgb"]["plateau_rgb_error_pixel_count"] == 0
    assert ring["rgb"]["visible_rgb_error_pixel_count"] > 100
    assert max(ring["rgb"]["rgb_channel_abs_error_max"]) > 30


def test_unreal_color_reference_uses_linear_light_alpha_multiply() -> None:
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _linear_premultiplied_srgb_byte,
    )

    source = (249, 115, 22)
    assert tuple(
        _linear_premultiplied_srgb_byte(channel, 128) for channel in source
    ) == (183, 83, 13)
    assert (183, 83, 13) != tuple(round(channel * 128 / 255) for channel in source)


def test_unreal_edge_reference_decodes_srgb_before_bilinear_and_blend() -> None:
    from PIL import Image

    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _bilinear_srgb_texture_sample,
        _linear_premultiplied_srgb_byte,
        _slate_sample_over_transparent_rgba,
    )

    source = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    source.putdata([(255, 0, 0, 255), (0, 0, 0, 0)])
    sampled = _bilinear_srgb_texture_sample(source, 0.5, 0.5)

    assert sampled == pytest.approx((0.5, 0.0, 0.0, 0.5))
    assert _slate_sample_over_transparent_rgba(sampled) == (137, 0, 0, 128)
    # Filtering the encoded bytes first would produce a much darker result.
    assert _linear_premultiplied_srgb_byte(128, 128) != 137


def test_unreal_qa_requires_schema_16_background_and_two_materialized_baked_layers(
    tmp_path: Path,
) -> None:
    from app.painter_ui_umg_adapter import package_painter_umg
    from tools.qa_painter_ui_unreal_umg_static_vector_bake import (
        _fixture,
        _materialization_evidence,
    )

    package = package_painter_umg(_fixture(), tmp_path / "package")
    evidence = _materialization_evidence(package)

    assert evidence["ok"] is True
    assert evidence["schema_version"] == 16
    assert evidence["packaged_preflight_counts"] == {
        "Native": 1,
        "Material": 0,
        "Baked": 2,
        "Blocked": 0,
    }
    assert evidence["artboard_background"] == {
        "id": "__tiger_artboard_background",
        "kind": "Image",
        "disposition": "Native",
        "visibility": "HitTestInvisible",
    }
    assert [row["status"] for row in evidence["payloads"]] == [
        "materialized",
        "materialized",
    ]
    assert [row["renderer_id"] for row in evidence["payloads"]] == [
        "qt_svg_fill_stroke_geometry_v4",
        "qt_svg_fill_stroke_geometry_v4",
    ]


def test_generation_applies_lossless_texture_settings_only_to_materialized_baked() -> None:
    source_path = (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "unreal_plugins"
        / "UMG"
        / "TigerStudioUMG"
        / "Source"
        / "TigerStudioUMGEditor"
        / "Private"
        / "TigerStudioUMGGeneration.cpp"
    )
    source = source_path.read_text(encoding="utf-8")
    texture_branch = source[source.index("if (UTexture2D* Texture = Cast<UTexture2D>") :]
    texture_branch = texture_branch[: texture_branch.index(
        "else if (ImageFillResourceIds.Contains"
    )]
    baked_start = texture_branch.index("if (bMaterializedBaked)")
    flipbook_start = texture_branch.index("else if (bFlipbook)")
    baked_branch = texture_branch[baked_start:flipbook_start]
    ordinary_prefix = texture_branch[:baked_start]

    for contract in (
        "Texture->LODGroup = TEXTUREGROUP_UI;",
        "Texture->NeverStream = true;",
        "Texture->SRGB = true;",
        "Texture->CompressionNoAlpha = false;",
        "Texture->CompressionSettings = TC_EditorIcon;",
        "Texture->MipGenSettings = TMGS_NoMipmaps;",
        "Texture->AddressX = TextureAddress::TA_Clamp;",
        "Texture->AddressY = TextureAddress::TA_Clamp;",
    ):
        assert contract in baked_branch
        assert contract not in ordinary_prefix
    assert "FTextureCompilingManager::Get().FinishCompilation({ Texture });" in (
        texture_branch
    )
    assert "Texture->UpdateResource();" in texture_branch
    assert "if (bMaterializedBaked || bFlipbook)" in texture_branch


def _component_vector_document() -> tuple[dict, str]:
    """Return a document whose only bakeable vector lives inside a component."""
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, root = add_ui_object(
        create_ui_document(320, 240),
        kind="frame",
        name="Badge",
        x=20,
        y=20,
        width=60,
        height=50,
    )
    document, vector = add_ui_object(
        document,
        kind="path",
        name="Chevron",
        parent_id=root["id"],
        x=30,
        y=30,
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
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
        name="Badge",
    )
    document, _instance = instantiate_ui_component(
        document,
        component_id=component["id"],
        x=140,
        y=120,
    )
    return document, vector["id"]


def test_static_vector_bakes_inside_components_are_materialized(
    tmp_path: Path,
) -> None:
    """A component-owned Baked layer must arrive with its asset, not a plan."""
    _app()
    from app.painter_ui_umg_adapter import package_painter_umg

    document, _vector_id = _component_vector_document()

    package = package_painter_umg(document, tmp_path)

    component_layers = [
        layer
        for component in package["document"]["Components"]
        for layer in component["Layers"]
        if str(layer.get("Disposition")) == "Baked"
    ]
    assert component_layers, "fixture no longer bakes anything inside a component"
    resource_ids = {
        str(row["Id"]) for row in package["document"]["Resources"]
    }
    for layer in component_layers:
        payload = json.loads(str(layer["PayloadJson"]))
        # Left as "available" the layer claims a bake it never produced, and the
        # plugin rejects the whole document as an invalid Baked record.
        assert payload["static_vector_bake"]["status"] == "materialized"
        assert str(layer["AssetId"]) in resource_ids
        assert layer["ImageFill"]
        assert layer["ImageFill"]["AssetId"] == layer["AssetId"]
    assert len(package["static_bakes"]) == len(component_layers)
    baked_reasons = [
        reason
        for blocker in package["packaged_preflight"]["blockers"]
        for reason in blocker.get("reasons", [])
        if "baked" in reason
    ]
    assert baked_reasons == []
