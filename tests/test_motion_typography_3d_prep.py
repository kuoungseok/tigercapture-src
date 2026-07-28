from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.schema import MotionLayer, SourceRef
from app.motion_designer.typography_3d_prep import (
    CHARACTER_3D_PREP_CONTRACT,
    prepare_character_3d_data,
)


def _text_layer() -> MotionLayer:
    return MotionLayer(
        id="title",
        name="Title",
        layer_type="text",
        source=SourceRef(kind="typography", params={"text": "A\u0301B"}),
        out_ms=1000,
    )


def test_character_3d_prep_preserves_grapheme_spans_and_overrides() -> None:
    layer = _text_layer()
    payload = prepare_character_3d_data(
        layer,
        depth=18,
        bevel=2,
        z_spacing=3,
        overrides={"1": {"rotation": [0, 30, 0], "material_slot": "accent"}},
    )
    assert payload["contract"] == CHARACTER_3D_PREP_CONTRACT
    assert payload["render_status"] == "prepared_for_m19_not_rendered_in_m16"
    assert payload["glyph_count"] == 2
    assert payload["glyphs"][0]["text"] == "A\u0301"
    assert payload["glyphs"][1]["position"][2] == 3
    assert payload["glyphs"][1]["rotation"] == [0.0, 30.0, 0.0]
    assert payload["glyphs"][1]["material_slot"] == "accent"
    assert layer.metadata["character_3d_prep"] == payload


def test_character_3d_prep_action_is_registered_and_mutates_layer() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    layer = _text_layer()
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": layer.to_dict()},
    ).ok
    result = registry.execute(
        "motion.typography.character_3d.prepare",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "depth": 20,
            "bevel": 3,
        },
    )
    assert result.ok
    assert result.result["character_3d_prep"]["depth"] == 20
