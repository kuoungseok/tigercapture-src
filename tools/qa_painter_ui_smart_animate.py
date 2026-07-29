from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_artboard,
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )
    from app.painter_ui_prototype import export_ui_prototype
    from app.painter_ui_prototype_authoring import (
        add_ui_prototype_flow,
        set_ui_prototype_transition,
    )

    document = create_ui_document(390, 844)
    source_artboard_id = document["active_artboard_id"]
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Checkout Card",
        x=36,
        y=72,
        width=250,
        height=120,
        style={
            "fills": [
                {
                    "type": "solid",
                    "color": "#24415E",
                    "opacity": 1.0,
                    "visible": True,
                }
            ],
        },
    )
    document, _label = add_ui_object(
        document,
        kind="text",
        name="Checkout",
        parent_id=root["id"],
        x=24,
        y=34,
        width=160,
        height=42,
        content={"text": "Open checkout"},
    )
    document, component = convert_ui_object_to_component(
        document,
        root_object_id=root["id"],
    )
    document, target_artboard = add_ui_artboard(
        document,
        name="Checkout Details",
        width=390,
        height=844,
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=component["id"],
        artboard_id=target_artboard["id"],
        x=72,
        y=180,
    )
    target_root = next(
        row
        for row in document["objects"]
        if row["id"] == instance["root_object_id"]
    )
    target_style = dict(target_root["style"])
    target_style["fills"] = [
        {
            "type": "solid",
            "color": "#4978A8",
            "opacity": 1.0,
            "visible": True,
        }
    ]
    target_style["corner_radii"] = {
        "top_left": 18.0,
        "top_right": 18.0,
        "bottom_right": 18.0,
        "bottom_left": 18.0,
    }
    document, _updated = update_ui_object(
        document,
        target_root["id"],
        {
            "width": 300,
            "height": 220,
            "opacity": 0.88,
            "style": target_style,
        },
    )
    document, interaction = add_ui_interaction(
        document,
        source_object_id=root["id"],
        trigger="click",
        action="navigate",
        target_artboard_id=target_artboard["id"],
    )
    document, _interaction = set_ui_prototype_transition(
        document,
        interaction["id"],
        {
            "kind": "smart_animate",
            "duration_ms": 700,
            "easing": "ease_in_out",
        },
    )
    document, _flow = add_ui_prototype_flow(
        document,
        name="Checkout",
        artboard_id=source_artboard_id,
        start_object_id=root["id"],
    )
    output = (
        ROOT
        / "debugCapture"
        / "painter_ui_designer"
        / "smart_animate_runtime"
    )
    report = export_ui_prototype(document, output)
    (output / "qa_meta.json").write_text(
        json.dumps(
            {
                "source_object_id": root["id"],
                "target_object_id": target_root["id"],
                "entrypoint": report["entrypoint"],
                "inspection": report["inspection"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
