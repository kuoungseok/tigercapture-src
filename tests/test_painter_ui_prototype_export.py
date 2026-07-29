from __future__ import annotations

from pathlib import Path

from app.painter_ui_document import (
    add_ui_artboard,
    add_ui_interaction,
    add_ui_object,
    create_ui_document,
)
from app.painter_ui_prototype import export_ui_prototype
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


def test_initial_state_uses_active_flow_artboard() -> None:
    from app.painter_ui_prototype import prototype_initial_state

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
