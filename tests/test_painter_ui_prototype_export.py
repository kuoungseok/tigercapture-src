from __future__ import annotations

from pathlib import Path

from app.painter_ui_document import (
    add_ui_artboard,
    add_ui_interaction,
    add_ui_object,
    create_ui_document,
)
from app.painter_ui_prototype import (
    execute_ui_prototype_trigger,
    export_ui_prototype,
    prototype_delay_schedule,
    prototype_initial_state,
)
from app.painter_ui_prototype_authoring import set_ui_prototype_transition
from app.painter_ui_prototype_authoring import add_ui_prototype_flow


def test_html_export_includes_extended_runtime_and_transition(
    tmp_path: Path,
) -> None:
    document = create_ui_document(390, 844)
    source_artboard = document["active_artboard_id"]
    document, target_artboard = add_ui_artboard(
        document,
        name="Details",
        width=390,
        height=844,
    )
    document, source = add_ui_object(
        document,
        kind="button",
        name="Open",
        artboard_id=source_artboard,
    )
    document, interaction = add_ui_interaction(
        document,
        source_object_id=source["id"],
        trigger="click",
        action="navigate",
        target_artboard_id=target_artboard["id"],
    )
    document, _row = set_ui_prototype_transition(
        document,
        interaction["id"],
        {
            "kind": "smart_animate",
            "duration_ms": 320,
            "easing": "ease_in_out",
        },
    )

    report = export_ui_prototype(document, tmp_path)
    html = Path(report["entrypoint"]).read_text(encoding="utf-8")

    assert report["ok"] is True
    assert 'x.action==="swap_overlay"' in html
    assert 'x.action==="set_variable"' in html
    assert 'x.action==="scroll_to"' in html
    assert 'x.trigger==="delay"' in html
    assert '"gamepadconnected"' in html
    assert '"smart_animate"' in html
    assert "captureSmart" in html
    assert "animateSmart" in html
    assert "applyInstanceVariant" in html
    assert "interactionCandidates" in html
    assert "state.component_variants[id]" in html
    assert "p.reset_component_state" in html
    assert "corner_radius" in html
    assert 'ease_in_out:"ease-in-out"' in html
    assert "browser_transform_fade_approximation" not in html


def test_initial_state_uses_active_flow_artboard() -> None:
    document = create_ui_document(390, 844)
    document, second = add_ui_artboard(
        document,
        name="Flow Start",
        width=390,
        height=844,
    )
    document, _flow = add_ui_prototype_flow(
        document,
        name="Primary",
        artboard_id=second["id"],
    )

    assert prototype_initial_state(document)["artboard_id"] == second["id"]


def test_delay_schedule_is_scoped_and_executes_one_interaction() -> None:
    document = create_ui_document(390, 844)
    artboard_id = document["active_artboard_id"]
    document, source = add_ui_object(
        document,
        kind="button",
        name="Delayed",
        artboard_id=artboard_id,
    )
    document, first = add_ui_interaction(
        document,
        source_object_id=source["id"],
        trigger="delay",
        action="play_sound",
        parameters={"delay_ms": 120, "asset_id": "one"},
    )
    document, _second = add_ui_interaction(
        document,
        source_object_id=source["id"],
        trigger="delay",
        action="play_sound",
        parameters={"delay_ms": 240, "asset_id": "two"},
    )
    state = prototype_initial_state(document)

    schedule = prototype_delay_schedule(document, state)
    assert [row["delay_ms"] for row in schedule] == [120, 240]
    runtime = execute_ui_prototype_trigger(
        document,
        state,
        source_object_id=source["id"],
        trigger="delay",
        interaction_id=first["id"],
    )
    assert runtime["matched_interaction_ids"] == [first["id"]]
    assert len(runtime["events"]) == 1
