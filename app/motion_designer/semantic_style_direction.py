"""Provider-backed semantic recommendation for editable Motion style plans."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from app.ai_providers import generate_selected_provider_json

from .schema import MotionComposition


SEMANTIC_STYLE_SCHEMA = "tigerstudio.motion.ai_semantic_style_direction.v1"
SEMANTIC_STYLE_CONTRACT: dict[str, Any] = {
    "schema": SEMANTIC_STYLE_SCHEMA,
    "required": [
        "schema",
        "composition_id",
        "base_revision",
        "recommended_style_id",
        "ranking",
        "candidate_notes",
        "story_guidance",
    ],
    "rules": [
        "Use every supplied style_id exactly once in ranking and candidate_notes.",
        "Do not invent layers, assets, facts, prices, testimonials, or statistics.",
        "Recommendation is advisory and must not mutate the project.",
        "Keep every note and story guidance field concise.",
    ],
}


def _style_ids(style_plan: Mapping[str, Any]) -> list[str]:
    values = [
        str(row.get("style_id") or "")
        for row in style_plan.get("candidates", [])
        if isinstance(row, Mapping) and str(row.get("style_id") or "")
    ]
    if len(values) != len(set(values)) or not values:
        raise ValueError("style plan requires unique candidates")
    return values


def _baseline(
    composition: MotionComposition,
    style_plan: Mapping[str, Any],
) -> dict[str, Any]:
    style_ids = _style_ids(style_plan)
    words = {
        str(value)
        for value in dict(style_plan.get("style_intent") or {}).get(
            "keywords",
            [],
        )
    }
    if "glass" in words:
        recommended = "glass"
    elif "tactile" in words:
        recommended = "stop_motion"
    elif "handmade" in words and "energetic" in words:
        recommended = "collage"
    elif "handmade" in words or "premium" in words:
        recommended = "craft"
    else:
        recommended = "clean"
    recommended = recommended if recommended in style_ids else style_ids[0]
    ranking = [recommended, *[item for item in style_ids if item != recommended]]
    tone = str(
        dict(style_plan.get("story_intent") or {}).get("tone") or "balanced"
    )
    return {
        "schema": SEMANTIC_STYLE_SCHEMA,
        "composition_id": composition.id,
        "base_revision": composition.revision,
        "recommended_style_id": recommended,
        "ranking": ranking,
        "rationale": (
            f"{recommended.replace('_', ' ').title()} best matches the "
            f"{', '.join(sorted(words)) or 'balanced'} direction."
        ),
        "candidate_notes": [
            {
                "style_id": style_id,
                "note": (
                    "Primary editable direction."
                    if style_id == recommended
                    else "Alternate treatment for visual comparison."
                ),
            }
            for style_id in ranking
        ],
        "story_guidance": {
            "hook": "Establish the promise immediately.",
            "pace": (
                "Use decisive changes and short holds."
                if tone == "energetic"
                else "Use clear beats and readable holds."
            ),
            "payoff": "Resolve the visual system before the CTA.",
        },
        "review_required": True,
    }


def validate_semantic_style_direction(
    direction: Mapping[str, Any],
    *,
    composition: MotionComposition,
    style_plan: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = deepcopy(dict(direction))
    if str(normalized.get("schema") or "") != SEMANTIC_STYLE_SCHEMA:
        raise ValueError("unsupported semantic style direction schema")
    if str(normalized.get("composition_id") or "") != composition.id:
        raise ValueError("semantic style direction targets another composition")
    if int(normalized.get("base_revision", -1)) != composition.revision:
        raise ValueError("semantic style direction is stale")
    expected = _style_ids(style_plan)
    expected_set = set(expected)
    recommended = str(normalized.get("recommended_style_id") or "")
    ranking = [str(value) for value in normalized.get("ranking", [])]
    if recommended not in expected_set:
        raise ValueError("semantic recommendation uses an unknown style")
    if len(ranking) != len(expected) or set(ranking) != expected_set:
        raise ValueError("semantic style ranking must contain every candidate once")
    notes = normalized.get("candidate_notes")
    if not isinstance(notes, list):
        raise ValueError("semantic candidate notes must be a list")
    note_ids = [
        str(row.get("style_id") or "")
        for row in notes
        if isinstance(row, Mapping)
    ]
    if len(note_ids) != len(expected) or set(note_ids) != expected_set:
        raise ValueError("semantic candidate notes must cover every style")
    validated_notes = []
    for row in notes:
        style_id = str(row.get("style_id") or "")
        note = " ".join(str(row.get("note") or "").split())
        if len(note) > 280:
            raise ValueError(f"semantic candidate note is too long: {style_id}")
        validated_notes.append({"style_id": style_id, "note": note})
    guidance = normalized.get("story_guidance")
    if not isinstance(guidance, Mapping):
        raise ValueError("semantic story guidance must be an object")
    validated_guidance = {}
    for key in ("hook", "pace", "payoff"):
        value = " ".join(str(guidance.get(key) or "").split())
        if len(value) > 280:
            raise ValueError(f"semantic story guidance is too long: {key}")
        validated_guidance[key] = value
    rationale = " ".join(str(normalized.get("rationale") or "").split())
    if len(rationale) > 480:
        raise ValueError("semantic recommendation rationale is too long")
    normalized.update({
        "recommended_style_id": recommended,
        "ranking": ranking,
        "rationale": rationale,
        "candidate_notes": validated_notes,
        "story_guidance": validated_guidance,
        "review_required": True,
    })
    return normalized


def generate_semantic_style_direction(
    composition: MotionComposition,
    style_plan: Mapping[str, Any],
    *,
    provider_id: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if str(style_plan.get("composition_id") or "") != composition.id:
        raise ValueError("style plan targets another composition")
    if int(style_plan.get("base_revision", -1)) != composition.revision:
        raise ValueError("style plan is stale")
    baseline = _baseline(composition, style_plan)
    result = generate_selected_provider_json(
        "tiger_studio_motion_semantic_style_direction",
        str(style_plan.get("prompt") or ""),
        output_contract=SEMANTIC_STYLE_CONTRACT,
        input_payload={
            "composition_id": composition.id,
            "base_revision": composition.revision,
            "style_intent": deepcopy(style_plan.get("style_intent") or {}),
            "story_intent": deepcopy(style_plan.get("story_intent") or {}),
            "references": deepcopy(style_plan.get("references") or []),
            "candidates": [
                {
                    "style_id": row.get("style_id"),
                    "title": row.get("title"),
                    "operations": row.get("operations"),
                    "warnings": row.get("warnings"),
                }
                for row in style_plan.get("candidates", [])
                if isinstance(row, Mapping)
            ],
        },
        safe_baseline=baseline,
        validate_payload=lambda value: validate_semantic_style_direction(
            value,
            composition=composition,
            style_plan=style_plan,
        ),
        provider_id=provider_id,
        env=env,
    )
    if not result.ok or result.payload is None:
        raise ValueError(result.reason or "semantic style direction failed")
    direction = dict(result.payload)
    provider = result.to_dict()
    provider.pop("payload", None)
    direction["provider"] = provider
    return direction


__all__ = [
    "SEMANTIC_STYLE_CONTRACT",
    "SEMANTIC_STYLE_SCHEMA",
    "generate_semantic_style_direction",
    "validate_semantic_style_direction",
]
