from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.rigging import (
    apply_motion_preset,
    create_humanoid_rig,
    set_two_bone_ik_constraint,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.validation import validate_composition


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
REAL_PART_SETS = (
    (
        "spine_girl",
        "resources/spine_samples/mix-and-match/images/girl/body.png",
        "resources/spine_samples/mix-and-match/images/girl/arm-front.png",
        "resources/spine_samples/mix-and-match/images/girl/leg-front.png",
    ),
    (
        "spine_erikari",
        "resources/spine_samples/chibi-stickers/images/erikari/body.png",
        "resources/spine_samples/chibi-stickers/images/erikari/arm.png",
        "resources/spine_samples/chibi-stickers/images/erikari/leg.png",
    ),
    (
        "spine_circus",
        "resources/spine_samples/celestial-circus/images/body-top.png",
        "resources/spine_samples/celestial-circus/images/arm-front-up.png",
        "resources/spine_samples/celestial-circus/images/leg-front.png",
    ),
)


def _real_asset_composition(row: tuple[str, str, str, str]) -> MotionComposition:
    name, body_path, arm_path, leg_path = row
    layers: list[MotionLayer] = []
    for layer_id, path in (
        ("body", body_path),
        ("arm", arm_path),
        ("leg", leg_path),
    ):
        source_path = ROOT / path
        assert source_path.is_file()
        layer = MotionLayer(
            id=f"{name}_{layer_id}",
            name=f"{name} {layer_id}",
            layer_type="image",
            source=SourceRef(
                kind="image",
                uri=str(source_path),
                params={"fit": "contain", "width": 320, "height": 360},
            ),
            out_ms=600_000,
        )
        layer.transform.position.default = [160.0, 180.0]
        layers.append(layer)
    composition = MotionComposition(
        id=f"qa_{name}",
        name=f"Rig QA {name}",
        width=320,
        height=360,
        fps=30.0,
        duration_ms=600_000,
        layers=layers,
    )
    rig = create_humanoid_rig(
        composition,
        layer_slots={
            "torso": layers[0].id,
            "right_upper_arm": layers[1].id,
            "right_thigh": layers[2].id,
        },
    )
    by_slot = {(bone.role, bone.side): bone.id for bone in rig.bones}
    set_two_bone_ik_constraint(
        composition,
        rig.id,
        root_bone_id=by_slot[("thigh", "right")],
        mid_bone_id=by_slot[("shin", "right")],
        end_bone_id=by_slot[("foot", "right")],
        target={
            "default": [190, 344],
            "keyframes": [
                {"time_ms": 0, "value": [190, 344]},
                {"time_ms": 300_000, "value": [205, 330]},
                {"time_ms": 600_000, "value": [190, 344]},
            ],
        },
        pole=[230, 280],
        lock_end=True,
    )
    apply_motion_preset(
        composition,
        rig.id,
        "arm_wave",
        start_ms=0,
        end_ms=600_000,
    )
    return composition


@pytest.mark.parametrize("asset_row", REAL_PART_SETS, ids=[row[0] for row in REAL_PART_SETS])
def test_real_character_parts_render_and_ten_minute_cache_stays_bounded(
    asset_row: tuple[str, str, str, str],
) -> None:
    QApplication.instance() or QApplication([])
    composition = _real_asset_composition(asset_row)
    assert validate_composition(composition).ok
    renderer = MotionExportRenderer(cache_capacity=12)
    for index in range(60):
        time_ms = round(index * composition.duration_ms / 59)
        assert len(evaluate_composition(composition, time_ms)) == 3
        frame = renderer.render_frame(
            composition,
            time_ms,
            width=160,
            height=180,
        )
        assert not frame.isNull()
        assert frame.hasAlphaChannel()
        assert renderer.cache.diagnostics()["size"] <= 12
    assert renderer.cache.diagnostics() == {"size": 12, "capacity": 12}
