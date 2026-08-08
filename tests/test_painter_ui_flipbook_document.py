from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from app.motion_designer.schema import (
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.painter_ui_document import (
    create_ui_document,
    normalize_ui_document,
    validate_ui_document,
)
from app.painter_ui_flipbook_bake import bake_motion_composition_flipbook
from app.painter_ui_flipbook_document import (
    PAINTER_UI_FLIPBOOK_ATTACHMENT_SCHEMA,
    PAINTER_UI_FLIPBOOK_ATTACH_REPORT_SCHEMA,
    PainterUIFlipbookAttachError,
    attach_flipbook_bake_to_painter_document,
)


def _composition() -> MotionComposition:
    layer = MotionLayer(
        id="motion_card",
        name="Motion Card",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "rectangle",
                "width": 6,
                "height": 6,
                "fill": "#37A0FF",
                "stroke": "transparent",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [4, 4]
    return MotionComposition(
        id="attach_composition",
        name="Attach Composition",
        width=8,
        height=8,
        fps=2.0,
        duration_ms=1000,
        revision=11,
        layers=[layer],
        metadata={"playback_scope": "ambient_loop"},
    )


def _document(kind: str = "rectangle") -> dict[str, object]:
    document = create_ui_document(320, 180, name="Attach Test")
    artboard_id = str(document["active_artboard_id"])
    document["revision"] = 6
    document["objects"] = [
        {
            "id": "panel",
            "kind": "frame",
            "name": "Panel",
            "artboard_id": artboard_id,
            "parent_id": "",
            "x": 10,
            "y": 10,
            "width": 200,
            "height": 120,
            "content": {"raw_figma": {"node_id": "1:1"}},
        },
        {
            "id": "target",
            "kind": kind,
            "name": "Continue Card",
            "artboard_id": artboard_id,
            "parent_id": "panel",
            "x": 20,
            "y": 24,
            "width": 96,
            "height": 48,
            "style": {
                "fills": [{"type": "solid", "color": "#112233"}],
                "radius": 7,
            },
            "content": {
                "text": "Continue",
                "raw_figma": {
                    "node_id": "2:4",
                    "boundVariables": {"fills": {"id": "VariableID:9"}},
                },
                "custom_payload": {"preserve": [1, 2, 3]},
            },
            "constraints": {"horizontal": "center", "vertical": "bottom"},
            "accessibility": {
                "role": "button",
                "label": "Continue",
                "focus_order": 2,
            },
        },
        {
            "id": "label",
            "kind": "text",
            "name": "Label",
            "artboard_id": artboard_id,
            "parent_id": "target",
            "x": 28,
            "y": 36,
            "width": 60,
            "height": 18,
            "content": {"text": "Continue"},
        },
    ]
    document["interactions"] = [
        {
            "id": "interaction-keep",
            "name": "Keep click",
            "source_object_id": "target",
            "trigger": "click",
            "action": "play_animation",
            "motion_clip_id": "motion-1",
            "parameters": {"speed": 1.0},
            "enabled": True,
        }
    ]
    return normalize_ui_document(document)


def _target(document: dict[str, object]) -> dict[str, object]:
    return next(row for row in document["objects"] if row["id"] == "target")


@pytest.mark.parametrize("kind", ["rectangle", "image"])
def test_attach_is_non_destructive_roundtrips_and_is_idempotent(
    tmp_path: Path,
    kind: str,
) -> None:
    bake = bake_motion_composition_flipbook(
        _composition(),
        tmp_path / kind,
    )
    document = _document(kind)
    original = copy.deepcopy(document)
    original_bake_manifest = copy.deepcopy(bake.manifest)
    before_target = copy.deepcopy(_target(document))

    updated, report = attach_flipbook_bake_to_painter_document(
        document,
        "target",
        bake,
    )

    assert document == original
    assert bake.manifest == original_bake_manifest
    assert updated is not document
    assert updated["revision"] == 7
    assert report["schema"] == PAINTER_UI_FLIPBOOK_ATTACH_REPORT_SCHEMA
    assert report["changed"] is True
    assert report["idempotent_reuse"] is False
    assert report["input_revision"] == 6
    assert report["result_revision"] == 7
    assert report["material_ready"] is True
    assert report["block_reasons"] == []

    after_target = _target(updated)
    assert {
        key: value for key, value in after_target.items() if key != "content"
    } == {
        key: value for key, value in before_target.items() if key != "content"
    }
    for key, value in before_target["content"].items():
        assert after_target["content"][key] == value
    assert updated["interactions"] == original["interactions"]
    assert [row["parent_id"] for row in updated["objects"]] == [
        row["parent_id"] for row in original["objects"]
    ]
    assert next(row for row in updated["objects"] if row["id"] == "label") == next(
        row for row in original["objects"] if row["id"] == "label"
    )

    flipbook = after_target["content"]["flipbook"]
    assert set(flipbook) == {
        "source_path",
        "columns",
        "rows",
        "frame_count",
        "fps",
        "start_frame",
        "loop",
        "phase",
        "static_frame_override",
        "enabled",
    }
    assert flipbook == {
        "source_path": str(bake.atlas_path.resolve()),
        "columns": 1,
        "rows": 2,
        "frame_count": 2,
        "fps": 2.0,
        "start_frame": 0,
        "loop": True,
        "phase": 0.0,
        "static_frame_override": -1,
        "enabled": True,
    }
    provenance = after_target["content"]["flipbook_bake"]
    assert provenance["schema"] == PAINTER_UI_FLIPBOOK_ATTACHMENT_SCHEMA
    assert provenance["manifest_path"] == str(bake.manifest_path.resolve())
    assert provenance["manifest_sha256"] == hashlib.sha256(
        bake.manifest_path.read_bytes()
    ).hexdigest()
    assert provenance["atlas_sha256"] == bake.manifest["atlas"]["sha256"]
    assert provenance["composition_id"] == "attach_composition"
    assert provenance["composition_revision"] == 11
    assert provenance["time_origin"] == "global_time"

    serialized = json.dumps(updated, ensure_ascii=False)
    roundtripped = normalize_ui_document(json.loads(serialized))
    roundtrip_target = _target(roundtripped)
    assert roundtrip_target["content"]["flipbook"] == flipbook
    assert roundtrip_target["content"]["flipbook_bake"] == provenance
    assert roundtrip_target["style"] == after_target["style"]
    assert roundtrip_target["constraints"] == after_target["constraints"]
    assert roundtrip_target["accessibility"] == after_target["accessibility"]
    assert validate_ui_document(roundtripped)["ok"] is True

    repeated, repeated_report = attach_flipbook_bake_to_painter_document(
        updated,
        "target",
        bake,
    )
    assert repeated == updated
    assert repeated["revision"] == 7
    assert repeated_report["changed"] is False
    assert repeated_report["idempotent_reuse"] is True
    assert repeated_report["input_revision"] == 7
    assert repeated_report["result_revision"] == 7


def test_event_triggered_attach_preserves_global_time_blocker(
    tmp_path: Path,
) -> None:
    bake = bake_motion_composition_flipbook(
        _composition(),
        tmp_path,
        playback_scope="click",
    )

    updated, report = attach_flipbook_bake_to_painter_document(
        _document(),
        "target",
        bake,
    )

    reason = "flipbook_trigger_requires_dynamic_material_time_origin"
    metadata = _target(updated)["content"]["flipbook_bake"]
    assert metadata["playback_scope"] == "event_triggered"
    assert metadata["time_origin"] == "global_time"
    assert metadata["material_ready"] is False
    assert metadata["block_reasons"] == [reason]
    assert report["playback_scope"] == "event_triggered"
    assert report["time_origin"] == "global_time"
    assert report["material_ready"] is False
    assert report["block_reasons"] == [reason]


def test_attach_rejects_missing_or_unsupported_object_without_mutation(
    tmp_path: Path,
) -> None:
    bake = bake_motion_composition_flipbook(_composition(), tmp_path)
    document = _document()
    original = copy.deepcopy(document)

    with pytest.raises(PainterUIFlipbookAttachError) as missing:
        attach_flipbook_bake_to_painter_document(document, "missing", bake)
    assert missing.value.block_reasons == (
        "flipbook_attach_object_missing:missing",
    )
    with pytest.raises(PainterUIFlipbookAttachError) as unsupported:
        attach_flipbook_bake_to_painter_document(document, "label", bake)
    assert unsupported.value.block_reasons == (
        "flipbook_attach_object_kind_unsupported:text",
    )
    assert document == original


def test_attach_rejects_missing_and_mutated_bake_files(tmp_path: Path) -> None:
    bake = bake_motion_composition_flipbook(
        _composition(),
        tmp_path / "missing",
    )
    document = _document()

    missing_atlas = replace(bake, atlas_path=tmp_path / "not-there.png")
    with pytest.raises(PainterUIFlipbookAttachError) as atlas_missing:
        attach_flipbook_bake_to_painter_document(
            document,
            "target",
            missing_atlas,
        )
    assert atlas_missing.value.block_reasons == (
        "flipbook_attach_atlas_missing",
    )

    missing_manifest = replace(
        bake,
        manifest_path=tmp_path / "not-there.manifest.json",
    )
    with pytest.raises(PainterUIFlipbookAttachError) as manifest_missing:
        attach_flipbook_bake_to_painter_document(
            document,
            "target",
            missing_manifest,
        )
    assert manifest_missing.value.block_reasons == (
        "flipbook_attach_manifest_missing",
    )

    bake.atlas_path.write_bytes(b"mutated-atlas")
    with pytest.raises(PainterUIFlipbookAttachError) as atlas_mutated:
        attach_flipbook_bake_to_painter_document(document, "target", bake)
    assert atlas_mutated.value.block_reasons == (
        "flipbook_attach_atlas_hash_mismatch",
    )

    fresh = bake_motion_composition_flipbook(
        _composition(),
        tmp_path / "manifest-mutated",
    )
    fresh.manifest_path.write_bytes(fresh.manifest_path.read_bytes() + b" ")
    with pytest.raises(PainterUIFlipbookAttachError) as manifest_mutated:
        attach_flipbook_bake_to_painter_document(document, "target", fresh)
    assert manifest_mutated.value.block_reasons == (
        "flipbook_attach_manifest_hash_mismatch",
    )

    forged = bake_motion_composition_flipbook(
        _composition(),
        tmp_path / "bake-hash-mutated",
    )
    forged_manifest = copy.deepcopy(forged.manifest)
    forged_manifest["bake_sha256"] = "0" * 64
    forged.manifest_path.write_bytes(
        (
            json.dumps(
                forged_manifest,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    )
    forged_result = replace(forged, manifest=forged_manifest)
    with pytest.raises(PainterUIFlipbookAttachError) as bake_hash_mutated:
        attach_flipbook_bake_to_painter_document(
            document,
            "target",
            forged_result,
        )
    assert bake_hash_mutated.value.block_reasons == (
        "flipbook_attach_bake_hash_mismatch",
    )
