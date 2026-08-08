from __future__ import annotations

from app.motion_designer.choreography_director import (
    CHOREOGRAPHY_DIRECTOR_SCHEMA,
    infer_shot_grammar,
    plan_choreography_candidates,
    select_choreography_candidate,
)


def _elements(count: int = 8) -> list[dict]:
    return [{
        "id": f"element_{index}",
        "role": "primary_subject" if index == 0 else "secondary_element",
        "depth": 0.2 + index * 0.08,
        "metadata": {},
    } for index in range(count)]


def test_director_builds_three_ranked_candidates_and_infers_grammar() -> None:
    report = plan_choreography_candidates(
        _elements(),
        duration_ms=4000,
        max_camera_travel_ratio=0.04,
        prompt="Newspaper headline burst around the subject",
        audio_hits_ms=(250, 500, 750, 1000),
    )

    assert report["schema"] == CHOREOGRAPHY_DIRECTOR_SCHEMA
    assert report["shot_grammar"] == "headline_burst"
    assert {item["variant"] for item in report["candidates"]} == {
        "clean", "dynamic", "collage",
    }
    assert report["recommended_candidate_id"] in report["ranking"]
    assert all("readability_score" in item["metrics"] for item in report["candidates"])


def test_director_limits_simultaneous_layer_entrances() -> None:
    report = plan_choreography_candidates(
        _elements(10),
        duration_ms=6000,
        max_camera_travel_ratio=0.04,
        max_simultaneous_motion=2,
    )

    assert all(
        item["metrics"]["max_simultaneous_motion"] <= 2
        for item in report["candidates"]
    )
    assert infer_shot_grammar("friendly character wave hello") == "puppet_greeting"


def test_candidate_selection_requires_approval_and_known_id() -> None:
    import pytest

    report = plan_choreography_candidates(
        _elements(),
        duration_ms=3000,
        max_camera_travel_ratio=0.03,
    )
    candidate_id = report["recommended_candidate_id"]
    selected = select_choreography_candidate(report, candidate_id, approved=True)
    assert selected["id"] == candidate_id
    with pytest.raises(ValueError, match="explicit approval"):
        select_choreography_candidate(report, candidate_id, approved=False)
    with pytest.raises(KeyError, match="unknown choreography"):
        select_choreography_candidate(report, "missing", approved=True)
