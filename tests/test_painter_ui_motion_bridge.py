from __future__ import annotations

import pytest


def _auto_layout_document():
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(640, 360)
    document, group = add_ui_object(
        document,
        kind="group",
        name="Toolbar",
        x=20,
        y=30,
        width=400,
        height=100,
    )
    document, _group = update_ui_object(
        document,
        group["id"],
        {
            "layout": {
                "direction": "horizontal",
                "padding": 10,
                "gap": 8,
                "align": "center",
            }
        },
    )
    document, first = add_ui_object(
        document,
        kind="button",
        name="Back",
        parent_id=group["id"],
        width=80,
        height=40,
    )
    document, second = add_ui_object(
        document,
        kind="button",
        name="Continue",
        parent_id=group["id"],
        width=120,
        height=40,
    )
    return document, group, first, second


def test_painter_ui_motion_mapping_uses_stable_object_ids() -> None:
    from app.painter_ui_motion_bridge import (
        attach_motion_composition,
        create_or_sync_ui_motion_composition,
        linked_motion_composition_id,
        resolved_ui_geometry,
    )

    document, group, first, second = _auto_layout_document()
    geometry = resolved_ui_geometry(document)
    assert geometry[first["id"]]["x"] == pytest.approx(30.0)
    assert geometry[first["id"]]["y"] == pytest.approx(60.0)
    assert geometry[second["id"]]["x"] == pytest.approx(118.0)

    composition = create_or_sync_ui_motion_composition(
        document,
        group["id"],
        duration_ms=900,
    )
    assert {layer.id for layer in composition.layers} == {
        group["id"],
        first["id"],
        second["id"],
    }
    assert composition.duration_ms == 900
    linked = attach_motion_composition(
        document,
        group["id"],
        composition.id,
    )
    assert (
        linked_motion_composition_id(linked, group["id"])
        == composition.id
    )


def test_motion_auto_layout_excludes_hidden_children_from_flow() -> None:
    from app.painter_ui_document import add_ui_object
    from app.painter_ui_motion_bridge import resolved_ui_geometry

    document, group, first, second = _auto_layout_document()
    document["objects"][2]["visible"] = False
    document, last = add_ui_object(
        document,
        kind="button",
        name="Finish",
        parent_id=group["id"],
        width=60,
        height=40,
    )

    geometry = resolved_ui_geometry(document)

    assert geometry[first["id"]]["x"] == pytest.approx(30.0)
    assert geometry[last["id"]]["x"] == pytest.approx(118.0)
    assert geometry[second["id"]]["width"] == pytest.approx(120.0)


def test_auto_layout_change_rebases_motion_without_losing_offset() -> None:
    from app.motion_designer.schema import Keyframe
    from app.painter_ui_document import update_ui_object
    from app.painter_ui_motion_bridge import create_or_sync_ui_motion_composition

    document, group, first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    first_layer = next(layer for layer in composition.layers if layer.id == first["id"])
    base = list(first_layer.transform.position.default)
    first_layer.transform.position.default = [base[0] + 12.0, base[1] - 4.0]
    first_layer.transform.position.keyframes = [
        Keyframe(time_ms=300, value=[base[0] + 30.0, base[1] + 5.0])
    ]

    changed, _row = update_ui_object(
        document,
        group["id"],
        {
            "layout": {
                "direction": "horizontal",
                "padding": {"left": 30, "top": 10, "right": 10, "bottom": 10},
                "gap": 8,
                "align": "center",
            }
        },
    )
    synced = create_or_sync_ui_motion_composition(
        changed,
        group["id"],
        composition,
    )
    first_layer = next(layer for layer in synced.layers if layer.id == first["id"])
    assert first_layer.transform.position.default == pytest.approx(
        [base[0] + 32.0, base[1] - 4.0]
    )
    assert first_layer.transform.position.keyframes[0].value == pytest.approx(
        [base[0] + 50.0, base[1] + 5.0]
    )


def test_motion_preview_states_evaluate_painter_layers() -> None:
    from app.motion_designer.schema import Keyframe
    from app.painter_ui_motion_bridge import (
        create_or_sync_ui_motion_composition,
        motion_preview_states,
    )

    document, group, first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(
        document,
        group["id"],
        duration_ms=1000,
    )
    layer = next(layer for layer in composition.layers if layer.id == first["id"])
    start = list(layer.transform.position.default)
    layer.transform.position.keyframes = [
        Keyframe(time_ms=0, value=start),
        Keyframe(time_ms=1000, value=[start[0] + 100.0, start[1]]),
    ]
    states = motion_preview_states(composition, 500)
    assert states[first["id"]]["position"][0] == pytest.approx(start[0] + 50.0)
    assert states[first["id"]]["position"][1] == pytest.approx(start[1])


def test_legacy_motion_link_migrates_to_binding_id_and_interaction() -> None:
    from app.painter_ui_motion_bridge import (
        create_or_sync_ui_motion_composition,
        inspect_motion_binding_links,
        migrate_motion_binding_links,
    )

    document, group, _first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    document["linked_targets"]["motion_designer"] = {
        "version": 1,
        "object_bindings": {group["id"]: composition.id},
    }
    document["interactions"].append(
        {
            "id": "ui-interaction-motion",
            "name": "Play",
            "source_object_id": group["id"],
            "trigger": "click",
            "action": "play_animation",
            "target_artboard_id": "",
            "target_object_id": group["id"],
            "component_id": "",
            "motion_clip_id": composition.id,
            "parameters": {},
            "enabled": True,
        }
    )

    before = inspect_motion_binding_links(
        document, {composition.id: composition}
    )
    assert before["links"][0]["status"] == "legacy_link"

    migrated, report = migrate_motion_binding_links(
        document, {composition.id: composition}
    )
    ref = migrated["linked_targets"]["motion_designer"][
        "object_bindings"
    ][group["id"]]
    assert ref == {
        "composition_id": composition.id,
        "binding_id": f"ui-binding-{group['id']}",
        "composition_revision": composition.revision,
    }
    assert migrated["interactions"][0]["motion_clip_id"] == ref["binding_id"]
    assert report["migrated_link_count"] == 1
    assert report["migrated_interaction_count"] == 1
    assert report["links"][0]["status"] == "ok"


def test_motion_link_relink_and_detach_preserve_composition() -> None:
    from app.painter_ui_motion_bridge import (
        create_or_sync_ui_motion_composition,
        detach_motion_binding,
        linked_motion_binding_id,
        relink_motion_binding,
    )

    document, group, _first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    binding_id = f"ui-binding-{group['id']}"
    linked = relink_motion_binding(
        document,
        group["id"],
        composition.id,
        binding_id,
        {composition.id: composition},
    )
    assert linked_motion_binding_id(linked, group["id"]) == binding_id

    detached, result = detach_motion_binding(linked, group["id"])
    assert result["detached"] is True
    assert result["composition_id"] == composition.id
    assert linked_motion_binding_id(detached, group["id"]) == ""
    assert composition.id in {composition.id: composition}


def test_motion_link_inspection_reports_stale_and_orphan_links() -> None:
    from app.painter_ui_motion_bridge import (
        attach_motion_composition,
        create_or_sync_ui_motion_composition,
        inspect_motion_binding_links,
    )

    document, group, _first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    document = attach_motion_composition(
        document,
        group["id"],
        composition.id,
        binding_id=f"ui-binding-{group['id']}",
        composition_revision=composition.revision + 2,
    )
    report = inspect_motion_binding_links(
        document, {composition.id: composition}
    )
    assert report["links"][0]["status"] == "stale_revision"
    assert report["ok"] is True

    document["linked_targets"]["motion_designer"]["object_bindings"][
        "removed-object"
    ] = composition.id
    report = inspect_motion_binding_links(
        document, {composition.id: composition}
    )
    assert report["ok"] is False
    assert any(
        row["status"] == "orphan_object" for row in report["links"]
    )


def test_object_delete_removes_motion_link_without_deleting_composition() -> None:
    from app.motion_designer.ui_motion_binding import ui_motion_bindings
    from app.painter_ui_document import remove_ui_object
    from app.painter_ui_motion_bridge import (
        attach_motion_composition,
        create_or_sync_ui_motion_composition,
        linked_motion_composition_id,
    )

    document, group, _first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    binding = ui_motion_bindings(composition)[0]
    document = attach_motion_composition(
        document,
        group["id"],
        composition.id,
        binding_id=binding.id,
        composition_revision=composition.revision,
    )

    removed_document, result = remove_ui_object(document, group["id"])
    assert result["removed_motion_link_object_ids"] == [group["id"]]
    assert linked_motion_composition_id(removed_document, group["id"]) == ""
    assert composition.id


def test_motion_link_inspection_validates_play_animation_binding() -> None:
    from app.motion_designer.ui_motion_binding import ui_motion_bindings
    from app.painter_ui_motion_bridge import (
        attach_motion_composition,
        create_or_sync_ui_motion_composition,
        inspect_motion_binding_links,
    )

    document, group, _first, _second = _auto_layout_document()
    composition = create_or_sync_ui_motion_composition(document, group["id"])
    binding = ui_motion_bindings(composition)[0]
    document = attach_motion_composition(
        document,
        group["id"],
        composition.id,
        binding_id=binding.id,
        composition_revision=composition.revision,
    )
    document["interactions"].append(
        {
            "id": "ui-interaction-motion",
            "name": "Play",
            "source_object_id": group["id"],
            "trigger": "click",
            "action": "play_animation",
            "target_artboard_id": "",
            "target_object_id": group["id"],
            "component_id": "",
            "motion_clip_id": "missing-binding",
            "parameters": {},
            "enabled": True,
        }
    )
    report = inspect_motion_binding_links(
        document, {composition.id: composition}
    )
    assert report["ok"] is False
    assert any(
        error.startswith("missing_interaction_motion_binding")
        for error in report["errors"]
    )
