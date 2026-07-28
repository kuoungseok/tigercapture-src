from __future__ import annotations

import json
from pathlib import Path

from app.motion_designer.interactive_button import ButtonAction, create_button_component
from app.actions.registry import ActionRegistry
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer, SourceRef
from app.unreal_umg_document import (
    motion_composition_to_umg_document,
    package_motion_composition_for_umg,
)


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_motion_umg_document_keeps_resources_animation_and_click_actions(
    tmp_path: Path,
) -> None:
    image = tmp_path / "button.png"
    image.write_bytes(b"image")
    sound = tmp_path / "click.wav"
    sound.write_bytes(b"sound")
    layer = MotionLayer(
        id="cta",
        name="CTA",
        layer_type="image",
        source=SourceRef(
            kind="image",
            uri=str(image),
            params={"width": 320, "height": 96},
        ),
    )
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[100, 200]),
        Keyframe(time_ms=500, value=[180, 200], interpolation="ease_out"),
    ]
    button = create_button_component(layer)
    button.actions["clicked"] = [
        ButtonAction(action_type="play_animation", name="TigerTimeline"),
        ButtonAction(action_type="play_sound", resource_uri=str(sound)),
        ButtonAction(action_type="emit_event", name="purchase"),
    ]
    layer.metadata["interactive_component"] = button.to_dict()
    composition = MotionComposition(
        id="advert",
        width=1280,
        height=720,
        duration_ms=2000,
        layers=[layer],
    )

    document = motion_composition_to_umg_document(composition)
    assert document["SchemaVersion"] == 3
    assert document["Layers"][0]["Kind"] == "Button"
    assert document["Animations"][0]["Property"] == "position"
    assert [row["Type"] for row in document["Interactions"][0]["Actions"]] == [
        "play_animation",
        "play_sound",
        "emit_event",
    ]
    assert all(
        row["ResourcePath"] == ""
        for row in document["Interactions"][0]["Actions"]
    )
    assert {row["Kind"] for row in document["Resources"]} == {"texture", "sound"}

    result = package_motion_composition_for_umg(composition, tmp_path / "packet")
    assert result["ok"] is True
    payload = json.loads(Path(result["document_path"]).read_text(encoding="utf-8"))
    assert all(row["SourcePath"].startswith("assets/") for row in payload["Resources"])


def test_motion_umg_actions_package_the_same_document(tmp_path: Path) -> None:
    layer = MotionLayer(id="shape", name="Shape", layer_type="shape")
    composition = MotionComposition(id="umg_actions", layers=[layer])
    registry = ActionRegistry(_Owner(composition))
    action_ids = {row["id"] for row in registry.list_actions()}
    assert "motion.umg.preflight" in action_ids
    assert "motion.umg.plugin.install" in action_ids
    assert "motion.umg.generate" in action_ids

    result = registry.execute(
        "motion.umg.package",
        {"composition_id": composition.id, "output_dir": str(tmp_path / "packet")},
    )
    assert result.ok
    document_path = Path(result.result["document_path"])
    assert document_path.is_file()


def test_umg_preflight_blocks_motion_features_that_require_a_real_bake() -> None:
    layer = MotionLayer(
        id="animated_logo",
        name="Animated Logo",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "shape": "path",
                "path": {
                    "closed": True,
                    "points": [
                        {"position": [0, 0]},
                        {"position": [100, 0]},
                        {"position": [50, 100]},
                    ],
                },
                "offset_path": {"amount": 8, "join": "round"},
                "stroke_gradient": {
                    "type": "linear",
                    "stops": [[0, "#ffffff"], [1, "#00ffff"]],
                },
            },
        ),
    )
    layer.metadata["path_morph"] = {
        "contract": "tigerstudio.motion.path_morph.v1",
    }
    document = motion_composition_to_umg_document(MotionComposition(
        id="blocked_features",
        layers=[layer],
    ))
    exported = document["Layers"][0]
    payload = json.loads(exported["PayloadJson"])
    assert exported["Disposition"] == "Blocked"
    assert "shape_operator_requires_bake:offset_path" in payload["umg_block_reasons"]
    assert "motion_feature_requires_bake:path_morph" in payload["umg_block_reasons"]


def test_umg_preflight_never_silently_drops_keyers_or_masks() -> None:
    from app.motion_designer.schema import MotionEffectRef, MotionMaskRef

    layer = MotionLayer(
        id="keyed",
        name="Keyed",
        layer_type="image",
        source=SourceRef(kind="image"),
        effects=[MotionEffectRef(kind="chroma_key")],
        masks=[MotionMaskRef(kind="path")],
    )
    document = motion_composition_to_umg_document(
        MotionComposition(layers=[layer]),
    )
    payload = json.loads(document["Layers"][0]["PayloadJson"])
    assert document["Layers"][0]["Disposition"] == "Blocked"
    assert "effect_requires_bake:chroma_key" in payload["umg_block_reasons"]
    assert "mask_requires_bake:path" in payload["umg_block_reasons"]


def test_umg_preflight_never_silently_drops_motion_effect_group_scope() -> None:
    from app.motion_designer.schema import MotionEffectRef

    group = MotionLayer(
        id="effect_group",
        name="Effect Group",
        layer_type="group",
        effects=[MotionEffectRef(kind="glow")],
        metadata={
            "effect_group": {
                "enabled": True,
                "mode": "selected_descendants",
                "layer_ids": ["child"],
            },
        },
    )
    child = MotionLayer(id="child", parent_id=group.id, layer_type="shape")
    document = motion_composition_to_umg_document(
        MotionComposition(layers=[child, group]),
    )
    exported = next(row for row in document["Layers"] if row["Id"] == group.id)
    payload = json.loads(exported["PayloadJson"])
    assert exported["Disposition"] == "Blocked"
    assert "motion_feature_requires_bake:effect_group" in payload["umg_block_reasons"]
    assert "effect_requires_bake:glow" in payload["umg_block_reasons"]


def test_umg_preflight_marks_new_motion_effects_for_deterministic_bake() -> None:
    from app.motion_designer.schema import MotionEffectRef

    layer = MotionLayer(
        id="styled",
        name="Styled",
        layer_type="shape",
        effects=[
            MotionEffectRef(kind="drop_shadow"),
            MotionEffectRef(kind="light_sweep"),
            MotionEffectRef(kind="fractal_noise"),
            MotionEffectRef(kind="posterize"),
            MotionEffectRef(kind="craft_style"),
        ],
    )
    document = motion_composition_to_umg_document(
        MotionComposition(layers=[layer]),
    )
    payload = json.loads(document["Layers"][0]["PayloadJson"])
    assert document["Layers"][0]["Disposition"] == "Blocked"
    assert {
        "effect_requires_bake:drop_shadow",
        "effect_requires_bake:light_sweep",
        "effect_requires_bake:fractal_noise",
        "effect_requires_bake:posterize",
        "effect_requires_bake:craft_style",
    } <= set(payload["umg_block_reasons"])


def test_umg_preflight_never_silently_drops_motion_color_management() -> None:
    layer = MotionLayer(id="title", layer_type="text")
    composition = MotionComposition(layers=[layer])
    composition.metadata["color_management"]["project"].update({
        "working_space": "acescg",
        "view_transform": "aces-1.3",
        "output_space": "rec2020",
        "output_transfer": "pq",
        "hdr_mode": True,
    })
    document = motion_composition_to_umg_document(composition)
    payload = json.loads(document["Layers"][0]["PayloadJson"])
    assert document["Layers"][0]["Disposition"] == "Blocked"
    assert (
        "motion_feature_requires_bake:color_management"
        in payload["umg_block_reasons"]
    )
