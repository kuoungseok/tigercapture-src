from __future__ import annotations

from app.motion_designer.motion_choreography import (
    infer_motion_variant,
    plan_motion_choreography,
)


def _elements() -> list[dict]:
    return [
        {
            "id": "hero",
            "role": "primary_subject",
            "depth": 0.55,
            "metadata": {"rigid": True},
        },
        {
            "id": "star",
            "role": "secondary_element",
            "depth": 0.85,
            "metadata": {},
        },
        {
            "id": "arrow",
            "role": "secondary_element",
            "depth": 0.75,
            "metadata": {},
        },
    ]


def test_variant_inference_recognizes_collage_and_dynamic_prompts() -> None:
    assert infer_motion_variant(prompt="comic collage poster") == "collage"
    assert infer_motion_variant(prompt="fast active product reveal") == "dynamic"
    assert infer_motion_variant(prompt="quiet premium title") == "clean"


def test_dynamic_choreography_gives_independent_layers_distinct_motion() -> None:
    plan = plan_motion_choreography(
        _elements(),
        duration_ms=3000,
        max_camera_travel_ratio=0.04,
        requested_variant="dynamic",
    )
    cues = plan.by_element_id()
    assert plan.variant == "dynamic"
    assert cues["star"].end_offset_ratio != cues["arrow"].end_offset_ratio
    assert cues["star"].start_ms != cues["arrow"].start_ms
    assert plan.warnings == []


def test_audio_hits_drive_secondary_stagger_and_locks_are_preserved() -> None:
    rows = _elements()
    rows[0]["metadata"]["motion_lock_to_background"] = True
    rows[1]["metadata"].update({"parent_id": "hero", "rigid": True})
    plan = plan_motion_choreography(
        rows,
        duration_ms=3000,
        max_camera_travel_ratio=0.012,
        requested_variant="collage",
        audio_hits_ms=(320, 640),
    )
    cues = plan.by_element_id()
    assert cues["hero"].lock_to_background is True
    assert cues["hero"].end_offset_ratio == plan.camera.end_offset_ratio
    assert cues["star"].lock_to_parent is True
    assert cues["arrow"].start_ms in {320, 640}
    assert abs(plan.camera.end_offset_ratio[0]) <= 0.012
