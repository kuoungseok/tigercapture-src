from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.schema import Keyframe, MotionComposition, MotionLayer
from app.motion_designer.interactive_button import create_button_component
from app.motion_designer.ui_motion_binding import (
    UI_MOTION_BINDINGS_KEY,
    UIMotionBinding,
    ui_animation_name,
    ui_motion_bindings,
    upsert_ui_motion_binding,
    validate_ui_motion_bindings,
)
from app.motion_designer.validation import validate_composition
from app.unreal_umg_document import motion_composition_to_umg_document


class Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def _composition() -> tuple[MotionComposition, MotionLayer]:
    layer = MotionLayer(name="Painter CTA", layer_type="shape", out_ms=1000)
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=[320.0, 180.0]),
        Keyframe(time_ms=180, value=[320.0, 174.0]),
    ]
    layer.transform.opacity.keyframes = [
        Keyframe(time_ms=0, value=0.7),
        Keyframe(time_ms=180, value=1.0),
    ]
    return MotionComposition(duration_ms=1000, layers=[layer]), layer


def _binding(layer: MotionLayer, **changes) -> dict:
    row = UIMotionBinding(
        id="ui-binding-hover",
        source_document_id="painter-document-7",
        source_object_id="button-primary",
        source_component_id="component-primary-button",
        layer_ids=[layer.id],
        property_names=["position", "opacity"],
        scope="transition",
        trigger="pointer_enter",
        from_state="normal",
        to_state="hover",
        animation_name="PrimaryButtonHover",
    ).to_dict()
    row.update(changes)
    return row


def test_ui_motion_binding_round_trip_and_composition_validation() -> None:
    composition, layer = _composition()
    upsert_ui_motion_binding(composition, _binding(layer))

    restored = MotionComposition.from_dict(composition.to_dict())
    bindings = ui_motion_bindings(restored)
    assert len(bindings) == 1
    assert bindings[0].source_object_id == "button-primary"
    assert bindings[0].delivery_request == {
        "web": "native_preferred",
        "app": "native_preferred",
        "umg": "native_preferred",
    }
    assert "delivery_policy" not in bindings[0].to_dict()
    assert ui_animation_name(restored, layer.id, "position") == "PrimaryButtonHover"
    assert validate_ui_motion_bindings(restored)["ok"] is True
    assert validate_composition(restored).ok is True


def test_ui_motion_binding_rejects_missing_layer_and_native_material_track() -> None:
    composition, layer = _composition()
    upsert_ui_motion_binding(
        composition,
        _binding(
            layer,
            layer_ids=["missing-layer"],
            property_names=["fill"],
            delivery_request={
                "web": "native_preferred",
                "app": "bake_allowed",
                "umg": "native_only",
            },
        ),
    )
    report = validate_ui_motion_bindings(composition)
    codes = {row["code"] for row in report["errors"]}
    assert "missing_ui_motion_layer" in codes
    assert "ui_motion_requires_material" in codes
    validation_codes = {issue.code for issue in validate_composition(composition).issues}
    assert codes <= validation_codes


def test_ui_motion_binding_migrates_legacy_delivery_policies_to_target_map() -> None:
    composition, layer = _composition()
    legacy = _binding(layer)
    legacy.pop("delivery_request")
    legacy["delivery_policy"] = "bake_allowed"
    legacy["metadata"] = {
        "target_policies": {
            "web": "native_preferred",
            "umg": "native_only",
        }
    }

    binding = upsert_ui_motion_binding(composition, legacy)

    assert binding.delivery_request == {
        "web": "native_preferred",
        "app": "bake_allowed",
        "umg": "native_only",
    }
    saved = binding.to_dict()
    assert saved["version"] == 2
    assert "delivery_policy" not in saved
    assert "target_policies" not in saved["metadata"]


def test_ui_motion_binding_names_native_umg_tracks() -> None:
    composition, layer = _composition()
    create_button_component(layer)
    upsert_ui_motion_binding(
        composition,
        _binding(layer, host_layer_id=layer.id),
    )

    document = motion_composition_to_umg_document(composition)
    tracks = {
        (row["LayerId"], row["Property"]): row["AnimationName"]
        for row in document["Animations"]
    }
    assert tracks[(layer.id, "position")] == "PrimaryButtonHover"
    assert tracks[(layer.id, "opacity")] == "PrimaryButtonHover"
    hover = next(
        row
        for row in document["Interactions"]
        if row["ComponentId"] == layer.id and row["Trigger"] == "hovered"
    )
    assert any(
        action["Type"] == "play_animation"
        and action["Name"] == "PrimaryButtonHover"
        for action in hover["Actions"]
    )


def test_ui_motion_binding_actions_set_list_preflight_and_remove() -> None:
    composition, layer = _composition()
    owner = Owner(composition)
    registry = ActionRegistry(owner)

    created = registry.execute(
        "motion.ui_binding.set",
        {"composition_id": composition.id, "binding": _binding(layer)},
    )
    assert created.ok
    assert UI_MOTION_BINDINGS_KEY in composition.metadata

    listed = registry.execute(
        "motion.ui_binding.list",
        {"composition_id": composition.id},
    )
    assert listed.ok
    assert listed.result["count"] == 1
    assert listed.result["bindings"][0]["source_object_id"] == "button-primary"

    preflight = registry.execute(
        "motion.ui_binding.preflight",
        {"composition_id": composition.id},
    )
    assert preflight.ok
    assert preflight.result["ok"] is True

    removed = registry.execute(
        "motion.ui_binding.remove",
        {
            "composition_id": composition.id,
            "binding_id": "ui-binding-hover",
        },
        confirm_destructive=True,
    )
    assert removed.ok
    assert ui_motion_bindings(composition) == []
