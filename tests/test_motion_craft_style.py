from app.motion_designer.craft_style import (
    CRAFT_STYLE_CONTRACT,
    make_craft_style_effect,
    normalize_craft_style,
)
from app.motion_designer.schema import MotionEffectRef


def test_craft_style_contract_round_trips_and_clamps_values() -> None:
    values = normalize_craft_style({
        "amount": 9,
        "grain_size": -5,
        "flicker_warmth": -4,
        "seed": -12,
    }, preset="handmade")
    assert values["amount"] == 1.0
    assert values["grain_size"] == 1.0
    assert values["flicker_warmth"] == -1.0
    assert values["seed"] == 0

    effect = make_craft_style_effect(values, preset="handmade")
    restored = MotionEffectRef.from_dict(effect.to_dict())
    assert restored.kind == "craft_style"
    assert restored.metadata["contract"] == CRAFT_STYLE_CONTRACT
    assert restored.metadata["preset"] == "handmade"
    assert restored.params["grain_size"].default == 1.0
