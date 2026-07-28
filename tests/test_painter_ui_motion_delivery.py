from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionEffectRef,
)
from app.motion_designer.ui_motion_binding import (
    UIMotionBinding,
    set_ui_motion_bindings,
)
from app.painter_ui_document import add_ui_object, create_ui_document
from app.painter_ui_motion_actor import add_motion_actor
from app.painter_ui_motion_bridge import (
    attach_motion_composition,
    create_or_sync_ui_motion_composition,
)
from app.painter_ui_motion_delivery import motion_delivery_report


def _linked_button():
    document, row = add_ui_object(
        create_ui_document(),
        kind="button",
        name="Buy",
        x=20,
        y=20,
        width=140,
        height=44,
    )
    composition = create_or_sync_ui_motion_composition(
        document,
        row["id"],
        duration_ms=400,
    )
    binding = UIMotionBinding(
        source_document_id=document["document_id"],
        source_object_id=row["id"],
        host_layer_id=row["id"],
        layer_ids=[row["id"]],
        property_names=["position", "opacity"],
        scope="transition",
        trigger="hovered",
        from_state="normal",
        to_state="hover",
        animation_name="Hover",
    )
    set_ui_motion_bindings(composition, [binding])
    document = attach_motion_composition(document, row["id"], composition.id)
    return document, row, composition


def test_motion_delivery_reports_features_per_target_without_false_app_claims():
    document, row, composition = _linked_button()
    report = motion_delivery_report(
        document,
        row["id"],
        {composition.id: composition},
    )

    targets = {item["target"]: item for item in report["targets"]}
    assert report["attached"] is True
    assert targets["umg"]["counts"]["Native"] == 2
    assert targets["web"]["counts"]["Blocked"] == 2
    assert targets["app"]["counts"]["Blocked"] == 2
    assert all(
        item["artifact_revision"] == composition.revision
        for target in report["targets"]
        for item in target["features"]
    )


def test_motion_delivery_mixes_native_transform_and_unproven_visual_effect():
    document, row, composition = _linked_button()
    composition.layers[0].effects.append(MotionEffectRef(kind="blur"))
    binding = UIMotionBinding.from_dict(
        composition.metadata["ui_motion_bindings"][0]
    )
    binding.property_names = []
    composition.layers[0].transform.position = AnimatedProperty(
        value_type="vec2",
        default=[0.0, 0.0],
        keyframes=[
            Keyframe(time_ms=0, value=[0.0, 0.0]),
            Keyframe(time_ms=400, value=[8.0, 0.0]),
        ],
    )
    set_ui_motion_bindings(composition, [binding])

    report = motion_delivery_report(
        document,
        row["id"],
        {composition.id: composition},
    )
    umg = next(item for item in report["targets"] if item["target"] == "umg")
    resolutions = {
        item["feature"]: item["resolved"] for item in umg["features"]
    }
    assert resolutions["position"] == "Native"
    assert resolutions["blur"] == "Blocked"


def test_actor_only_is_limited_to_motion_actor_objects():
    document, row, composition = _linked_button()
    binding = UIMotionBinding.from_dict(
        composition.metadata["ui_motion_bindings"][0]
    )
    binding.property_names = ["motion_actor"]
    set_ui_motion_bindings(composition, [binding])
    report = motion_delivery_report(
        document,
        row["id"],
        {composition.id: composition},
    )
    assert all(
        feature["resolved"] == "Blocked"
        for target in report["targets"]
        for feature in target["features"]
    )

    actor_document, actor = add_motion_actor(
        create_ui_document(),
        MotionComposition(name="Actor", layers=composition.layers),
    )
    actor_composition = MotionComposition(
        id=(actor["content"]["motion_composition_id"]),
        name="Actor",
        layers=composition.layers,
    )
    actor_report = motion_delivery_report(
        actor_document,
        actor["id"],
        {actor_composition.id: actor_composition},
    )
    assert all(
        feature["resolved"] == "Actor Only"
        for target in actor_report["targets"]
        for feature in target["features"]
    )
