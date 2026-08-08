from __future__ import annotations

from copy import deepcopy

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.schema import (
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.story_direction import (
    PLATFORM_PLAN_SCHEMA,
    STORY_SCHEMA,
    add_story_beat,
    apply_platform_variant,
    bind_story_audio,
    inspect_story,
    plan_platform_variant,
    preflight_platform,
    preflight_story,
    preview_platform_variant,
    reorder_story_beat,
    update_story,
)


def _layer(
    name: str,
    role: str,
    *,
    size: tuple[int, int],
    position: tuple[float, float],
    text: str = "",
    font_size: float = 52.0,
) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="text" if text else "image",
        source=SourceRef(
            kind="text" if text else "image",
            params={
                "width": size[0],
                "height": size[1],
                "text": text,
                "font_size": font_size,
            },
        ),
        in_ms=0,
        out_ms=15_000,
        metadata={"story_role": role},
    )
    layer.transform.position.default = list(position)
    return layer


def _composition() -> MotionComposition:
    composition = MotionComposition(
        name="Story Ad",
        width=1920,
        height=1080,
        duration_ms=15_000,
    )
    composition.layers = [
        _layer(
            "Background",
            "background",
            size=(1920, 1080),
            position=(960, 540),
        ),
        _layer(
            "Headline",
            "headline",
            size=(1100, 150),
            position=(960, 190),
            text="MAKE THE MORNING MOVE",
            font_size=74,
        ),
        _layer(
            "Character",
            "character",
            size=(620, 900),
            position=(960, 560),
        ),
        _layer(
            "Subtitle",
            "subtitle",
            size=(900, 100),
            position=(960, 830),
            text="A better first beat.",
            font_size=44,
        ),
        _layer(
            "CTA",
            "cta",
            size=(500, 100),
            position=(960, 930),
            text="START NOW",
            font_size=48,
        ),
    ]
    composition.layers[2].transform.position.keyframes = [
        Keyframe(time_ms=0, value=[900.0, 580.0]),
        Keyframe(time_ms=7000, value=[1040.0, 540.0]),
    ]
    return composition


def _add_story(composition: MotionComposition) -> tuple[dict, dict]:
    update_story(
        composition,
        {
            "message": "Energy arrives before the first sip.",
            "audience": "Morning commuters",
        },
    )
    hook = add_story_beat(
        composition,
        role="hook",
        start_ms=0,
        end_ms=1800,
        purpose="Stop the scroll",
        emotion="surprise",
        copy="Before the city wakes",
        layer_ids=[composition.layers[1].id],
    )
    cta = add_story_beat(
        composition,
        role="cta",
        start_ms=13_200,
        end_ms=15_000,
        purpose="Convert",
        emotion="resolve",
        copy="Start now",
        layer_ids=[composition.layers[-1].id],
    )
    return hook, cta


def test_story_beats_audio_and_roundtrip_keep_stable_ids():
    composition = _composition()
    hook, cta = _add_story(composition)
    binding = bind_story_audio(
        composition,
        beat_id=hook["id"],
        source_kind="music",
        source_id="music_cue_morning",
        cue_ms=0,
        tempo_bpm=126,
    )
    reordered = reorder_story_beat(composition, cta["id"], 0)

    restored = MotionComposition.from_dict(composition.to_dict())
    story = inspect_story(restored)

    assert story["schema"] == STORY_SCHEMA
    assert {item["id"] for item in story["beats"]} == {hook["id"], cta["id"]}
    assert reordered[0]["id"] == cta["id"]
    assert story["audio_bindings"][0]["id"] == binding["id"]
    assert story["audio_bindings"][0]["tempo_bpm"] == 126


@pytest.mark.parametrize(
    ("platform", "size"),
    [
        ("16:9", (1920, 1080)),
        ("9:16", (1080, 1920)),
        ("1:1", (1080, 1080)),
    ],
)
def test_platform_variant_is_non_destructive_reviewable_and_safe(platform, size):
    composition = _composition()
    _add_story(composition)
    source = deepcopy(composition.to_dict())

    plan = plan_platform_variant(composition, platform)
    assert plan["schema"] == PLATFORM_PLAN_SCHEMA
    assert plan["diff_summary"]["requires_human_approval"] is True
    assert composition.to_dict() == source

    candidate = apply_platform_variant(composition, plan, approved=True)
    report = preflight_platform(candidate, platform=platform)

    assert (candidate.width, candidate.height) == size
    assert candidate.id != composition.id
    assert [item.id for item in candidate.layers] == [item.id for item in composition.layers]
    assert report["summary"]["clipped_protected_layer_count"] == 0
    assert not [item for item in report["issues"] if item["code"] == "cta_hold_too_short"]
    assert composition.to_dict() == source


def test_platform_variant_requires_approval_and_rejects_stale_plan():
    composition = _composition()
    _add_story(composition)
    plan = plan_platform_variant(composition, "9:16")
    with pytest.raises(PermissionError):
        apply_platform_variant(composition, plan, approved=False)

    composition.revision += 1
    with pytest.raises(ValueError, match="stale"):
        apply_platform_variant(composition, plan, approved=True)


def test_platform_variant_preserves_position_keyframe_ids_and_reflows_values():
    composition = _composition()
    _add_story(composition)
    source_keys = composition.layers[2].transform.position.keyframes
    plan = plan_platform_variant(composition, "9:16")
    candidate = apply_platform_variant(composition, plan, approved=True)
    target_keys = candidate.layers[2].transform.position.keyframes

    assert [item.id for item in target_keys] == [item.id for item in source_keys]
    assert [item.value for item in target_keys] != [item.value for item in source_keys]


def test_story_preflight_reports_missing_structure_and_direction_flip():
    composition = _composition()
    first = add_story_beat(
        composition,
        role="setup",
        start_ms=0,
        end_ms=3000,
        character="Hero",
    )
    second = add_story_beat(
        composition,
        role="proof",
        start_ms=2500,
        end_ms=5000,
        character="Hero",
    )
    state = composition.metadata["story_direction"]
    state["beats"][0]["screen_direction"] = "left_to_right"
    state["beats"][1]["screen_direction"] = "right_to_left"
    state["beats"][1]["layer_ids"] = ["missing_layer"]

    report = preflight_story(composition)
    codes = {item["code"] for item in report["issues"]}

    assert first["id"] and second["id"]
    assert {
        "story_missing_hook",
        "story_missing_cta",
        "overlapping_beats",
        "missing_beat_layers",
        "screen_direction_discontinuity",
    } <= codes


def test_preview_returns_candidate_and_does_not_mutate_source():
    composition = _composition()
    _add_story(composition)
    source = composition.to_dict()

    preview = preview_platform_variant(composition, "square")

    assert preview["plan"]["platform"] == "square_1_1"
    assert preview["candidate"]["width"] == 1080
    assert preview["candidate"]["height"] == 1080
    assert composition.to_dict() == source


class _Owner:
    def __init__(self, composition: MotionComposition) -> None:
        self._motion_compositions = {composition.id: composition}


def test_story_and_platform_actions_are_registered_and_apply_reviewed_variant():
    composition = _composition()
    owner = _Owner(composition)
    registry = ActionRegistry(owner)
    added = registry.execute(
        "motion.story.beat.add",
        {
            "composition_id": composition.id,
            "role": "hook",
            "start_ms": 0,
            "end_ms": 1800,
            "purpose": "Stop the scroll",
        },
    )
    assert added.ok
    hook_id = added.result["beat"]["id"]
    assert registry.execute(
        "motion.story.audio.bind",
        {
            "composition_id": composition.id,
            "beat_id": hook_id,
            "source_kind": "voice",
            "source_id": "voice_line_1",
            "cue_ms": 120,
        },
    ).ok
    plan_result = registry.execute(
        "motion.platform.variant.plan",
        {"composition_id": composition.id, "platform": "9:16"},
    )
    assert plan_result.ok
    plan = plan_result.result["plan"]
    applied = registry.execute(
        "motion.platform.variant.apply",
        {
            "composition_id": composition.id,
            "plan": plan,
            "approved": True,
        },
    )
    assert applied.ok
    variant_id = applied.result["composition"]["id"]
    assert variant_id in owner._motion_compositions
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "motion.story.inspect",
        "motion.story.update",
        "motion.story.beat.add",
        "motion.story.beat.update",
        "motion.story.beat.reorder",
        "motion.story.audio.bind",
        "motion.platform.variant.plan",
        "motion.platform.variant.preview",
        "motion.platform.variant.apply",
        "motion.platform.preflight",
    } <= action_ids
