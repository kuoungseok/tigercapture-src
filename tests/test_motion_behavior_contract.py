from __future__ import annotations

from app.motion_designer.behaviors import apply_behavior, behavior_contract
from app.motion_designer.schema import MotionBehaviorRef


def _values() -> dict[str, object]:
    return {"position": [100.0, 200.0], "scale": [1.0, 1.0], "rotation": 0.0, "opacity": 1.0}


def test_parameter_behavior_contract_is_truthful_and_queryable() -> None:
    contract = behavior_contract("random_motion")
    assert contract["contract"] == "tiger_parameter_behavior_v1"
    assert contract["supported"] is True
    assert contract["time_model"] == "seeded_noise"
    assert behavior_contract("not_real")["supported"] is False


def test_seeded_random_motion_is_deterministic() -> None:
    behavior = MotionBehaviorRef(
        kind="random_motion",
        start_ms=0,
        end_ms=5000,
        params={"seed": 42, "frequency": 3.5, "position_amount": 12.0, "rotation_amount": 4.0},
    )
    first = _values()
    second = _values()
    apply_behavior(first, behavior, 1733.0)
    apply_behavior(second, behavior, 1733.0)
    assert first == second
    assert first != _values()


def test_drift_integrates_velocity_until_behavior_end() -> None:
    behavior = MotionBehaviorRef(
        kind="drift", start_ms=1000, end_ms=3000, params={"velocity": [50.0, -20.0], "hold_after": True}
    )
    values = _values()
    apply_behavior(values, behavior, 4000.0)
    assert values["position"] == [200.0, 160.0]


def test_behavior_stack_supports_parameter_oscillation() -> None:
    behavior = MotionBehaviorRef(
        kind="oscillate",
        start_ms=0,
        end_ms=1000,
        params={"target": "position_x", "amplitude": 20.0, "cycles": 1.0},
    )
    values = _values()
    apply_behavior(values, behavior, 250.0)
    assert abs(values["position"][0] - 120.0) < 1e-6
