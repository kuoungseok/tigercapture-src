"""Reviewable platform-aware copy direction for Motion compositions."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping

from app.ai_providers import generate_selected_provider_json

from .schema import MotionComposition
from .story_direction import inspect_story, resolve_platform_profile
from .style_director import STYLE_LOCK_KEY, style_lock


PLATFORM_COPY_PLAN_SCHEMA = "tigerstudio.motion.ai_platform_copy_plan.v1"
PLATFORM_COPY_PREFLIGHT_SCHEMA = "tigerstudio.motion.ai_platform_copy_preflight.v1"

PLATFORM_COPY_LIMITS: dict[str, dict[str, int]] = {
    "landscape_16_9": {
        "hook": 72,
        "headline": 72,
        "subtitle": 120,
        "body": 160,
        "cta": 36,
        "default": 140,
    },
    "vertical_9_16": {
        "hook": 44,
        "headline": 48,
        "subtitle": 76,
        "body": 96,
        "cta": 28,
        "default": 88,
    },
    "square_1_1": {
        "hook": 56,
        "headline": 60,
        "subtitle": 92,
        "body": 120,
        "cta": 32,
        "default": 108,
    },
}

PLATFORM_COPY_CONTRACT: dict[str, Any] = {
    "schema": PLATFORM_COPY_PLAN_SCHEMA,
    "required": [
        "schema",
        "composition_id",
        "base_revision",
        "platform",
        "operations",
    ],
    "operation": {
        "required": [
            "kind",
            "target_id",
            "role",
            "before",
            "after",
            "max_characters",
            "reason",
        ],
        "kind": ["story_beat.copy", "text_layer.text"],
        "rules": [
            "Keep every target_id, kind, role, before, and max_characters unchanged.",
            "Rewrite only after and reason.",
            "Do not add or remove operations.",
            "Keep after within max_characters.",
            "Do not invent factual claims, prices, testimonials, or statistics.",
        ],
    },
}


def _text_role(layer) -> str:
    candidates = (
        layer.metadata.get("story_role"),
        layer.metadata.get("template_role"),
        layer.source.metadata.get("story_role"),
        layer.source.params.get("role"),
    )
    role = next((str(value).strip().lower() for value in candidates if value), "")
    aliases = {
        "main_title": "headline",
        "title": "headline",
        "caption": "subtitle",
        "button": "cta",
    }
    if role:
        return aliases.get(role, role)
    name = layer.name.casefold()
    for token, inferred in (
        ("headline", "headline"),
        ("title", "headline"),
        ("subtitle", "subtitle"),
        ("caption", "subtitle"),
        ("button", "cta"),
        ("cta", "cta"),
        ("body", "body"),
    ):
        if token in name:
            return inferred
    return "body"


def _limit(platform: str, role: str) -> int:
    limits = PLATFORM_COPY_LIMITS[platform]
    return int(limits.get(role, limits["default"]))


def _fit_copy(text: str, limit: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    clipped = normalized[:limit].rstrip()
    if " " in clipped:
        word_safe = clipped.rsplit(" ", 1)[0].rstrip()
        if len(word_safe) >= max(8, int(limit * 0.55)):
            clipped = word_safe
    return clipped.rstrip(" ,.;:-")


def _plan_id(plan: Mapping[str, Any]) -> str:
    stable = {
        key: value
        for key, value in plan.items()
        if key not in {"id", "provider"}
    }
    encoded = json.dumps(
        stable,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"platform_copy_{sha256(encoded).hexdigest()[:20]}"


def _baseline_plan(
    composition: MotionComposition,
    platform: str,
    prompt: str,
) -> dict[str, Any]:
    profile_id, profile = resolve_platform_profile(platform)
    protected = set(style_lock(composition).get("protected_layer_ids") or ())
    operations: list[dict[str, Any]] = []
    story = inspect_story(composition)
    for beat in story.get("beats", []):
        before = str(beat.get("copy") or "").strip()
        linked = {str(value) for value in beat.get("layer_ids", []) if str(value)}
        if not before or linked & protected:
            continue
        role = str(beat.get("role") or "default").strip().lower()
        maximum = _limit(profile_id, role)
        operations.append({
            "kind": "story_beat.copy",
            "target_id": str(beat.get("id") or ""),
            "role": role,
            "before": before,
            "after": _fit_copy(before, maximum),
            "max_characters": maximum,
            "reason": "deterministic_platform_length_fit",
        })
    for layer in composition.layers:
        if layer.id in protected:
            continue
        if layer.layer_type != "text" and layer.source.kind not in {"text", "typography"}:
            continue
        before = str(layer.source.params.get("text") or "").strip()
        if not before:
            continue
        role = _text_role(layer)
        maximum = _limit(profile_id, role)
        operations.append({
            "kind": "text_layer.text",
            "target_id": layer.id,
            "role": role,
            "before": before,
            "after": _fit_copy(before, maximum),
            "max_characters": maximum,
            "reason": "deterministic_platform_length_fit",
        })
    plan = {
        "schema": PLATFORM_COPY_PLAN_SCHEMA,
        "composition_id": composition.id,
        "base_revision": composition.revision,
        "platform": profile_id,
        "profile": {
            "label": str(profile["label"]),
            "width": int(profile["width"]),
            "height": int(profile["height"]),
        },
        "prompt": str(prompt or "").strip(),
        "story_context": {
            "message": str(story.get("message") or ""),
            "audience": str(story.get("audience") or ""),
        },
        "operations": operations,
        "review_required": True,
    }
    plan["id"] = _plan_id(plan)
    return plan


def _target_rows(composition: MotionComposition) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    protected = set(style_lock(composition).get("protected_layer_ids") or ())
    for beat in inspect_story(composition).get("beats", []):
        target_id = str(beat.get("id") or "")
        if target_id:
            rows[("story_beat.copy", target_id)] = {
                "before": str(beat.get("copy") or "").strip(),
                "role": str(beat.get("role") or "default").strip().lower(),
                "protected": bool(
                    {str(value) for value in beat.get("layer_ids", []) if str(value)}
                    & protected
                ),
            }
    for layer in composition.layers:
        if layer.layer_type == "text" or layer.source.kind in {"text", "typography"}:
            rows[("text_layer.text", layer.id)] = {
                "before": str(layer.source.params.get("text") or "").strip(),
                "role": _text_role(layer),
                "protected": layer.id in protected,
            }
    return rows


def validate_platform_copy_plan(
    plan: Mapping[str, Any],
    *,
    composition: MotionComposition,
    expected_operations: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = deepcopy(dict(plan))
    if str(normalized.get("schema") or "") != PLATFORM_COPY_PLAN_SCHEMA:
        raise ValueError("unsupported platform copy plan schema")
    if str(normalized.get("composition_id") or "") != composition.id:
        raise ValueError("platform copy plan targets another composition")
    if int(normalized.get("base_revision", -1)) != composition.revision:
        raise ValueError("platform copy plan is stale; generate it again")
    platform, profile = resolve_platform_profile(str(normalized.get("platform") or ""))
    normalized["platform"] = platform
    normalized["profile"] = {
        "label": str(profile["label"]),
        "width": int(profile["width"]),
        "height": int(profile["height"]),
    }
    operations = normalized.get("operations")
    if not isinstance(operations, list):
        raise ValueError("platform copy operations must be a list")
    current = _target_rows(composition)
    protected = set(style_lock(composition).get("protected_layer_ids") or ())
    expected_signatures = None
    if expected_operations is not None:
        expected_signatures = [
            (
                str(row.get("kind") or ""),
                str(row.get("target_id") or ""),
                str(row.get("role") or ""),
                str(row.get("before") or ""),
                int(row.get("max_characters", 0) or 0),
            )
            for row in expected_operations
        ]
    seen: set[tuple[str, str]] = set()
    validated: list[dict[str, Any]] = []
    for row in operations:
        if not isinstance(row, Mapping):
            raise ValueError("platform copy operation must be an object")
        kind = str(row.get("kind") or "")
        target_id = str(row.get("target_id") or "")
        key = (kind, target_id)
        if kind not in {"story_beat.copy", "text_layer.text"} or key not in current:
            raise ValueError(f"unsupported platform copy target: {kind}:{target_id}")
        if key in seen:
            raise ValueError(f"duplicate platform copy target: {kind}:{target_id}")
        seen.add(key)
        target = current[key]
        if target["protected"] or (
            kind == "text_layer.text" and target_id in protected
        ):
            raise PermissionError(f"platform copy target is protected: {target_id}")
        role = str(row.get("role") or "").strip().lower()
        before = str(row.get("before") or "")
        maximum = int(row.get("max_characters", 0) or 0)
        after = " ".join(str(row.get("after") or "").split())
        if role != target["role"] or before != target["before"]:
            raise ValueError(f"platform copy target changed after planning: {target_id}")
        if maximum != _limit(platform, role):
            raise ValueError(f"invalid platform copy limit: {target_id}")
        if len(after) > maximum:
            raise ValueError(f"platform copy exceeds {maximum} characters: {target_id}")
        validated.append({
            "kind": kind,
            "target_id": target_id,
            "role": role,
            "before": before,
            "after": after,
            "max_characters": maximum,
            "reason": str(row.get("reason") or "platform_copy_rewrite"),
        })
    if expected_signatures is not None:
        actual = [
            (
                row["kind"],
                row["target_id"],
                row["role"],
                row["before"],
                row["max_characters"],
            )
            for row in validated
        ]
        if actual != expected_signatures:
            raise ValueError("AI provider changed the platform copy target set")
    normalized["operations"] = validated
    normalized["review_required"] = True
    normalized["id"] = str(normalized.get("id") or _plan_id(normalized))
    return normalized


def generate_platform_copy_plan(
    composition: MotionComposition,
    *,
    platform: str,
    prompt: str = "",
    provider_id: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    baseline = _baseline_plan(composition, platform, prompt)
    result = generate_selected_provider_json(
        "tiger_studio_motion_platform_copy",
        prompt,
        output_contract=PLATFORM_COPY_CONTRACT,
        input_payload={
            "composition_id": composition.id,
            "base_revision": composition.revision,
            "platform": baseline["platform"],
            "profile": baseline["profile"],
            "story_context": baseline["story_context"],
            "copy_targets": baseline["operations"],
        },
        safe_baseline=baseline,
        validate_payload=lambda value: validate_platform_copy_plan(
            value,
            composition=composition,
            expected_operations=baseline["operations"],
        ),
        provider_id=provider_id,
        env=env,
    )
    if not result.ok or result.payload is None:
        raise ValueError(result.reason or "platform copy planning failed")
    plan = dict(result.payload)
    provider = result.to_dict()
    provider.pop("payload", None)
    plan["provider"] = provider
    plan["id"] = _plan_id(plan)
    return plan


def apply_platform_copy_plan(
    composition: MotionComposition,
    plan: Mapping[str, Any],
    *,
    approved: bool,
) -> tuple[MotionComposition, dict[str, Any]]:
    if not approved:
        raise PermissionError("platform copy plan requires explicit human approval")
    normalized = validate_platform_copy_plan(plan, composition=composition)
    candidate = MotionComposition.from_dict(composition.to_dict())
    beats = {
        str(row.get("id") or ""): row
        for row in candidate.metadata.get("story_direction", {}).get("beats", [])
        if isinstance(row, Mapping)
    }
    layers = {layer.id: layer for layer in candidate.layers}
    changed: list[dict[str, Any]] = []
    for operation in normalized["operations"]:
        before = operation["before"]
        after = operation["after"]
        if before == after:
            continue
        if operation["kind"] == "story_beat.copy":
            beats[operation["target_id"]]["copy"] = after
        else:
            layers[operation["target_id"]].source.params["text"] = after
        changed.append(deepcopy(operation))
    candidate.metadata["ai_platform_copy"] = {
        "schema": PLATFORM_COPY_PLAN_SCHEMA,
        "plan_id": normalized["id"],
        "platform": normalized["platform"],
        "provider": deepcopy(normalized.get("provider") or {}),
        "operations": changed,
    }
    candidate.revision += 1
    return candidate, {
        "plan_id": normalized["id"],
        "platform": normalized["platform"],
        "changed_count": len(changed),
        "changed_targets": [
            f"{row['kind']}:{row['target_id']}" for row in changed
        ],
        "source_transforms_preserved": True,
    }


def preflight_platform_copy_plan(
    composition: MotionComposition,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    try:
        normalized = validate_platform_copy_plan(plan, composition=composition)
    except (KeyError, PermissionError, TypeError, ValueError) as exc:
        normalized = {}
        issues.append({"code": "invalid_platform_copy_plan", "message": str(exc)})
    for row in normalized.get("operations", []):
        if not str(row.get("after") or "").strip():
            warnings.append({
                "code": "empty_platform_copy",
                "target_id": row["target_id"],
            })
    return {
        "schema": PLATFORM_COPY_PREFLIGHT_SCHEMA,
        "ok": not issues,
        "composition_id": composition.id,
        "plan_id": str(normalized.get("id") or ""),
        "issues": issues,
        "warnings": warnings,
        "summary": {
            "operation_count": len(normalized.get("operations") or []),
            "issue_count": len(issues),
            "warning_count": len(warnings),
        },
    }


__all__ = [
    "PLATFORM_COPY_CONTRACT",
    "PLATFORM_COPY_LIMITS",
    "PLATFORM_COPY_PLAN_SCHEMA",
    "PLATFORM_COPY_PREFLIGHT_SCHEMA",
    "apply_platform_copy_plan",
    "generate_platform_copy_plan",
    "preflight_platform_copy_plan",
    "validate_platform_copy_plan",
]
