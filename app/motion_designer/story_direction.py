"""Editable story beats and non-destructive platform reflow for Motion Designer."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from .schema import MotionComposition, MotionLayer, new_motion_id


STORY_SCHEMA = "tigerstudio.motion.story_direction.v1"
PLATFORM_PLAN_SCHEMA = "tigerstudio.motion.platform_variant_plan.v1"
STORY_METADATA_KEY = "story_direction"

BEAT_ROLES = (
    "hook",
    "setup",
    "desire",
    "conflict",
    "reveal",
    "proof",
    "payoff",
    "cta",
)

PLATFORM_PROFILES: dict[str, dict[str, Any]] = {
    "landscape_16_9": {
        "label": "Landscape 16:9",
        "width": 1920,
        "height": 1080,
        "safe": (0.05, 0.06, 0.95, 0.92),
        "subtitle": (0.08, 0.76, 0.92, 0.90),
        "min_text_px": 30.0,
        "cta_hold_ms": 1200,
    },
    "vertical_9_16": {
        "label": "Vertical 9:16",
        "width": 1080,
        "height": 1920,
        "safe": (0.07, 0.08, 0.93, 0.88),
        "subtitle": (0.08, 0.72, 0.92, 0.84),
        "min_text_px": 36.0,
        "cta_hold_ms": 1400,
    },
    "square_1_1": {
        "label": "Square 1:1",
        "width": 1080,
        "height": 1080,
        "safe": (0.07, 0.07, 0.93, 0.90),
        "subtitle": (0.08, 0.72, 0.92, 0.86),
        "min_text_px": 32.0,
        "cta_hold_ms": 1300,
    },
}

_PLATFORM_ALIASES = {
    "16:9": "landscape_16_9",
    "landscape": "landscape_16_9",
    "youtube": "landscape_16_9",
    "9:16": "vertical_9_16",
    "vertical": "vertical_9_16",
    "shorts": "vertical_9_16",
    "reels": "vertical_9_16",
    "tiktok": "vertical_9_16",
    "1:1": "square_1_1",
    "square": "square_1_1",
    "feed": "square_1_1",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _vector(value: Any, default: tuple[float, float]) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return [_number(value[0], default[0]), _number(value[1], default[1])]
    return [float(default[0]), float(default[1])]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _story_state(composition: MotionComposition, *, create: bool) -> dict[str, Any]:
    raw = composition.metadata.get(STORY_METADATA_KEY)
    state = dict(raw) if isinstance(raw, Mapping) else {}
    state["schema"] = STORY_SCHEMA
    state["title"] = str(state.get("title") or composition.name)
    state["message"] = str(state.get("message") or "")
    state["audience"] = str(state.get("audience") or "")
    state["beats"] = [
        dict(item)
        for item in state.get("beats", [])
        if isinstance(item, Mapping)
    ]
    state["audio_bindings"] = [
        dict(item)
        for item in state.get("audio_bindings", [])
        if isinstance(item, Mapping)
    ]
    state["character_continuity"] = dict(
        state.get("character_continuity")
        if isinstance(state.get("character_continuity"), Mapping)
        else {}
    )
    if create:
        composition.metadata[STORY_METADATA_KEY] = state
    return state


def inspect_story(composition: MotionComposition) -> dict[str, Any]:
    """Return the normalized, serializable story document."""
    state = _story_state(composition, create=False)
    state["beats"] = sorted(
        state["beats"],
        key=lambda item: (_int(item.get("order"), 0), _int(item.get("start_ms"), 0)),
    )
    return deepcopy(state)


def update_story(
    composition: MotionComposition,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    state = _story_state(composition, create=True)
    for key in ("title", "message", "audience"):
        if key in changes:
            state[key] = str(changes.get(key) or "")
    continuity = changes.get("character_continuity")
    if isinstance(continuity, Mapping):
        state["character_continuity"] = {
            **state["character_continuity"],
            **dict(continuity),
        }
    composition.metadata[STORY_METADATA_KEY] = state
    return inspect_story(composition)


def _beat_by_id(state: Mapping[str, Any], beat_id: str) -> dict[str, Any]:
    for beat in state.get("beats", []):
        if str(beat.get("id") or "") == beat_id:
            return beat
    raise KeyError(f"unknown story beat: {beat_id}")


def add_story_beat(
    composition: MotionComposition,
    *,
    role: str,
    start_ms: int,
    end_ms: int,
    purpose: str = "",
    emotion: str = "",
    character: str = "",
    copy: str = "",
    visual: str = "",
    audio_cue: str = "",
    scene_id: str = "",
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    state = _story_state(composition, create=True)
    normalized_role = str(role or "setup").strip().lower()
    if normalized_role not in BEAT_ROLES:
        raise ValueError(f"unsupported story beat role: {role}")
    start = _clamp(float(start_ms), 0.0, float(composition.duration_ms))
    end = _clamp(float(end_ms), start + 1.0, float(composition.duration_ms))
    beat = {
        "id": new_motion_id("beat"),
        "order": len(state["beats"]),
        "role": normalized_role,
        "start_ms": int(start),
        "end_ms": int(end),
        "purpose": str(purpose or ""),
        "emotion": str(emotion or ""),
        "character": str(character or ""),
        "copy": str(copy or ""),
        "visual": str(visual or ""),
        "audio_cue": str(audio_cue or ""),
        "scene_id": str(scene_id or ""),
        "layer_ids": [str(item) for item in layer_ids if str(item)],
    }
    state["beats"].append(beat)
    composition.metadata[STORY_METADATA_KEY] = state
    return deepcopy(beat)


def update_story_beat(
    composition: MotionComposition,
    beat_id: str,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    state = _story_state(composition, create=True)
    beat = _beat_by_id(state, beat_id)
    for key in (
        "purpose",
        "emotion",
        "character",
        "copy",
        "visual",
        "audio_cue",
        "scene_id",
    ):
        if key in changes:
            beat[key] = str(changes.get(key) or "")
    if "role" in changes:
        role = str(changes.get("role") or "").strip().lower()
        if role not in BEAT_ROLES:
            raise ValueError(f"unsupported story beat role: {role}")
        beat["role"] = role
    if "start_ms" in changes or "end_ms" in changes:
        start = _clamp(
            float(changes.get("start_ms", beat["start_ms"])),
            0.0,
            float(composition.duration_ms),
        )
        end = _clamp(
            float(changes.get("end_ms", beat["end_ms"])),
            start + 1.0,
            float(composition.duration_ms),
        )
        beat["start_ms"], beat["end_ms"] = int(start), int(end)
    if "layer_ids" in changes:
        rows = changes.get("layer_ids")
        if not isinstance(rows, (list, tuple)):
            raise ValueError("layer_ids must be a list")
        beat["layer_ids"] = [str(item) for item in rows if str(item)]
    composition.metadata[STORY_METADATA_KEY] = state
    return deepcopy(beat)


def reorder_story_beat(
    composition: MotionComposition,
    beat_id: str,
    order: int,
) -> list[dict[str, Any]]:
    state = _story_state(composition, create=True)
    beats = sorted(
        state["beats"],
        key=lambda item: (_int(item.get("order"), 0), _int(item.get("start_ms"), 0)),
    )
    beat = _beat_by_id({"beats": beats}, beat_id)
    beats.remove(beat)
    beats.insert(max(0, min(len(beats), int(order))), beat)
    for index, item in enumerate(beats):
        item["order"] = index
    state["beats"] = beats
    composition.metadata[STORY_METADATA_KEY] = state
    return deepcopy(beats)


def bind_story_audio(
    composition: MotionComposition,
    *,
    beat_id: str,
    source_kind: str,
    source_id: str,
    cue_ms: int,
    label: str = "",
    tempo_bpm: float | None = None,
) -> dict[str, Any]:
    state = _story_state(composition, create=True)
    _beat_by_id(state, beat_id)
    kind = str(source_kind or "").strip().lower()
    if kind not in {"voice", "music"}:
        raise ValueError("source_kind must be voice or music")
    state["audio_bindings"] = [
        item
        for item in state["audio_bindings"]
        if not (
            str(item.get("beat_id") or "") == beat_id
            and str(item.get("source_kind") or "") == kind
        )
    ]
    binding = {
        "id": new_motion_id("story_audio"),
        "beat_id": beat_id,
        "source_kind": kind,
        "source_id": str(source_id or ""),
        "cue_ms": max(0, min(composition.duration_ms, int(cue_ms))),
        "label": str(label or ""),
    }
    if tempo_bpm is not None:
        binding["tempo_bpm"] = _clamp(float(tempo_bpm), 20.0, 320.0)
    state["audio_bindings"].append(binding)
    composition.metadata[STORY_METADATA_KEY] = state
    return deepcopy(binding)


def resolve_platform_profile(platform: str) -> tuple[str, dict[str, Any]]:
    key = str(platform or "").strip().lower().replace("-", "_").replace(" ", "_")
    key = _PLATFORM_ALIASES.get(key, key)
    if key not in PLATFORM_PROFILES:
        raise ValueError(f"unsupported platform profile: {platform}")
    return key, deepcopy(PLATFORM_PROFILES[key])


def _layer_role(layer: MotionLayer) -> str:
    candidates = (
        layer.metadata.get("story_role"),
        layer.metadata.get("template_role"),
        layer.source.metadata.get("story_role"),
        layer.source.params.get("role"),
    )
    value = next((str(item).strip().lower() for item in candidates if item), "")
    aliases = {
        "main_title": "headline",
        "title": "headline",
        "caption": "subtitle",
        "body": "body",
        "button": "cta",
        "hero": "character",
        "actor": "character",
    }
    if value:
        return aliases.get(value, value)
    name = layer.name.lower()
    for token, role in (
        ("background", "background"),
        ("headline", "headline"),
        ("title", "headline"),
        ("subtitle", "subtitle"),
        ("caption", "subtitle"),
        ("cta", "cta"),
        ("button", "cta"),
        ("character", "character"),
        ("mascot", "mascot"),
    ):
        if token in name:
            return role
    return "content"


def _layer_priority(layer: MotionLayer, role: str) -> int:
    explicit = layer.metadata.get("story_priority")
    if explicit is not None:
        return max(0, min(100, _int(explicit, 50)))
    return {
        "cta": 100,
        "headline": 95,
        "subtitle": 90,
        "character": 88,
        "mascot": 88,
        "body": 75,
        "content": 60,
        "background": 10,
    }.get(role, 50)


def _layer_size(layer: MotionLayer) -> tuple[float, float]:
    params = layer.source.params
    return (
        max(1.0, _number(params.get("width"), 320.0)),
        max(1.0, _number(params.get("height"), 180.0)),
    )


def _safe_pixels(profile: Mapping[str, Any], key: str = "safe") -> tuple[float, float, float, float]:
    width, height = float(profile["width"]), float(profile["height"])
    left, top, right, bottom = profile[key]
    return left * width, top * height, right * width, bottom * height


def _target_position(
    role: str,
    source_position: list[float],
    source_size: tuple[int, int],
    profile: Mapping[str, Any],
) -> list[float]:
    width, height = float(profile["width"]), float(profile["height"])
    safe_left, safe_top, safe_right, safe_bottom = _safe_pixels(profile)
    nx = source_position[0] / max(1.0, float(source_size[0]))
    ny = source_position[1] / max(1.0, float(source_size[1]))
    x, y = nx * width, ny * height
    if role == "headline":
        x, y = width * 0.5, height * 0.18
    elif role == "subtitle":
        subtitle = _safe_pixels(profile, "subtitle")
        x, y = width * 0.5, (subtitle[1] + subtitle[3]) * 0.5
    elif role == "cta":
        x, y = width * 0.5, height * 0.84
    elif role in {"character", "mascot"}:
        x, y = width * 0.5, height * (0.54 if height > width else 0.52)
    elif role == "background":
        x, y = width * 0.5, height * 0.5
    return [
        round(_clamp(x, safe_left, safe_right), 3),
        round(_clamp(y, safe_top, safe_bottom), 3),
    ]


def _target_scale(
    layer: MotionLayer,
    role: str,
    source_size: tuple[int, int],
    profile: Mapping[str, Any],
) -> list[float]:
    current = _vector(layer.transform.scale.default, (1.0, 1.0))
    target_width, target_height = float(profile["width"]), float(profile["height"])
    source_width, source_height = float(source_size[0]), float(source_size[1])
    area_factor = (
        (target_width * target_height)
        / max(1.0, source_width * source_height)
    ) ** 0.5
    if role == "background":
        factor = max(target_width / source_width, target_height / source_height)
    elif role in {"character", "mascot"}:
        layer_width, layer_height = _layer_size(layer)
        available_width = target_width * (0.78 if target_height > target_width else 0.55)
        available_height = target_height * 0.72
        factor = min(
            available_width / max(1.0, layer_width * abs(current[0])),
            available_height / max(1.0, layer_height * abs(current[1])),
        )
    elif layer.layer_type == "text" or layer.source.kind in {"text", "typography"}:
        layer_width, _layer_height = _layer_size(layer)
        safe_left, _safe_top, safe_right, _safe_bottom = _safe_pixels(profile)
        width_factor = (safe_right - safe_left) / max(
            1.0,
            layer_width * abs(current[0]),
        )
        factor = min(max(0.72, area_factor), width_factor)
    else:
        factor = area_factor
    return [round(current[0] * factor, 6), round(current[1] * factor, 6)]


def _scale_factor(
    layer: MotionLayer,
    role: str,
    source_size: tuple[int, int],
    profile: Mapping[str, Any],
) -> tuple[float, float]:
    current = _vector(layer.transform.scale.default, (1.0, 1.0))
    target = _target_scale(layer, role, source_size, profile)
    return (
        target[0] / current[0] if abs(current[0]) > 1e-9 else 1.0,
        target[1] / current[1] if abs(current[1]) > 1e-9 else 1.0,
    )


def _plan_id(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"platform_plan_{sha256(encoded).hexdigest()[:20]}"


def plan_platform_variant(
    composition: MotionComposition,
    platform: str,
) -> dict[str, Any]:
    """Build a deterministic, reviewable reflow plan without changing the source."""
    profile_id, profile = resolve_platform_profile(platform)
    source_size = (composition.width, composition.height)
    operations: list[dict[str, Any]] = [
        {
            "kind": "composition.resize",
            "path": "composition.size",
            "before": [composition.width, composition.height],
            "after": [profile["width"], profile["height"]],
            "reason": profile["label"],
        }
    ]
    for layer in composition.layers:
        if not layer.visible:
            continue
        role = _layer_role(layer)
        priority = _layer_priority(layer, role)
        position = _vector(
            layer.transform.position.default,
            (composition.width * 0.5, composition.height * 0.5),
        )
        target_position = _target_position(role, position, source_size, profile)
        target_scale = _target_scale(layer, role, source_size, profile)
        before_scale = _vector(layer.transform.scale.default, (1.0, 1.0))
        if target_position != [round(item, 3) for item in position]:
            operations.append(
                {
                    "kind": "layer.position",
                    "layer_id": layer.id,
                    "layer_name": layer.name,
                    "role": role,
                    "priority": priority,
                    "path": "transform.position.default",
                    "before": position,
                    "after": target_position,
                    "reason": "priority_safe_reflow",
                }
            )
        if target_scale != [round(item, 6) for item in before_scale]:
            operations.append(
                {
                    "kind": "layer.scale",
                    "layer_id": layer.id,
                    "layer_name": layer.name,
                    "role": role,
                    "priority": priority,
                    "path": "transform.scale.default",
                    "before": before_scale,
                    "after": target_scale,
                    "reason": "role_aware_scale",
                }
            )
        if layer.transform.position.keyframes:
            before_keys = [
                {"id": key.id, "time_ms": key.time_ms, "value": deepcopy(key.value)}
                for key in layer.transform.position.keyframes
            ]
            after_keys = [
                {
                    **item,
                    "value": _target_position(
                        role,
                        _vector(item["value"], tuple(position)),
                        source_size,
                        profile,
                    ),
                }
                for item in before_keys
            ]
            operations.append(
                {
                    "kind": "layer.position_keyframes",
                    "layer_id": layer.id,
                    "layer_name": layer.name,
                    "role": role,
                    "priority": priority,
                    "path": "transform.position.keyframes",
                    "before": before_keys,
                    "after": after_keys,
                    "reason": "preserve_animated_reflow",
                }
            )
        if layer.transform.scale.keyframes:
            factor_x, factor_y = _scale_factor(layer, role, source_size, profile)
            before_keys = [
                {"id": key.id, "time_ms": key.time_ms, "value": deepcopy(key.value)}
                for key in layer.transform.scale.keyframes
            ]
            after_keys = [
                {
                    **item,
                    "value": [
                        round(_vector(item["value"], (1.0, 1.0))[0] * factor_x, 6),
                        round(_vector(item["value"], (1.0, 1.0))[1] * factor_y, 6),
                    ],
                }
                for item in before_keys
            ]
            operations.append(
                {
                    "kind": "layer.scale_keyframes",
                    "layer_id": layer.id,
                    "layer_name": layer.name,
                    "role": role,
                    "priority": priority,
                    "path": "transform.scale.keyframes",
                    "before": before_keys,
                    "after": after_keys,
                    "reason": "preserve_animated_scale",
                }
            )
        if layer.layer_type == "text" or layer.source.kind in {"text", "typography"}:
            before_font = _number(layer.source.params.get("font_size"), 48.0)
            role_minimum = {
                "headline": float(profile["width"]) * 0.055,
                "subtitle": float(profile["width"]) * 0.032,
                "cta": float(profile["width"]) * 0.038,
            }.get(role, float(profile["min_text_px"]))
            target_font = max(
                float(profile["min_text_px"]),
                role_minimum,
                before_font
                * (
                    (
                        float(profile["width"]) * float(profile["height"])
                    )
                    / max(1.0, composition.width * composition.height)
                )
                ** 0.5,
            )
            target_font = round(target_font, 3)
            if abs(target_font - before_font) > 0.001:
                operations.append(
                    {
                        "kind": "text.font_size",
                        "layer_id": layer.id,
                        "layer_name": layer.name,
                        "role": role,
                        "priority": priority,
                        "path": "source.params.font_size",
                        "before": before_font,
                        "after": target_font,
                        "reason": "platform_minimum_text_size",
                    }
                )
    payload = {
        "schema": PLATFORM_PLAN_SCHEMA,
        "source_composition_id": composition.id,
        "source_revision": composition.revision,
        "platform": profile_id,
        "profile": profile,
        "operations": operations,
    }
    payload["id"] = _plan_id(payload)
    payload["diff_summary"] = {
        "operation_count": len(operations),
        "layer_count": len({item.get("layer_id") for item in operations if item.get("layer_id")}),
        "requires_human_approval": True,
        "source_unchanged": True,
    }
    return payload


def apply_platform_variant(
    composition: MotionComposition,
    plan: Mapping[str, Any],
    *,
    approved: bool,
) -> MotionComposition:
    """Apply an approved plan to a clone and preserve the source composition."""
    if not approved:
        raise PermissionError("platform variant requires explicit human approval")
    if str(plan.get("schema") or "") != PLATFORM_PLAN_SCHEMA:
        raise ValueError("invalid platform variant plan schema")
    if str(plan.get("source_composition_id") or "") != composition.id:
        raise ValueError("platform variant plan belongs to another composition")
    if _int(plan.get("source_revision"), -1) != composition.revision:
        raise ValueError("platform variant plan is stale; preview it again")
    candidate = composition.clone(
        new_id=True,
        name=f"{composition.name} - {plan.get('platform')}",
    )
    layer_map = {layer.id: layer for layer in candidate.layers}
    for operation in plan.get("operations", []):
        if not isinstance(operation, Mapping):
            continue
        kind = str(operation.get("kind") or "")
        after = operation.get("after")
        if kind == "composition.resize":
            candidate.width, candidate.height = int(after[0]), int(after[1])
            continue
        layer = layer_map.get(str(operation.get("layer_id") or ""))
        if layer is None:
            continue
        if kind == "layer.position":
            layer.transform.position.default = list(after)
        elif kind == "layer.scale":
            layer.transform.scale.default = list(after)
        elif kind == "layer.position_keyframes":
            by_id = {key.id: key for key in layer.transform.position.keyframes}
            for row in after or []:
                key = by_id.get(str(row.get("id") or ""))
                if key is not None:
                    key.value = list(row.get("value") or key.value)
        elif kind == "layer.scale_keyframes":
            by_id = {key.id: key for key in layer.transform.scale.keyframes}
            for row in after or []:
                key = by_id.get(str(row.get("id") or ""))
                if key is not None:
                    key.value = list(row.get("value") or key.value)
        elif kind == "text.font_size":
            layer.source.params["font_size"] = float(after)
    candidate.metadata["platform_variant"] = {
        "schema": PLATFORM_PLAN_SCHEMA,
        "plan_id": str(plan.get("id") or ""),
        "platform": str(plan.get("platform") or ""),
        "source_composition_id": composition.id,
        "source_revision": composition.revision,
        "approved": True,
        "diff": deepcopy(list(plan.get("operations") or [])),
    }
    candidate.revision = 1
    return candidate


def preview_platform_variant(
    composition: MotionComposition,
    platform: str,
) -> dict[str, Any]:
    plan = plan_platform_variant(composition, platform)
    candidate = apply_platform_variant(composition, plan, approved=True)
    report = preflight_platform(candidate, platform=plan["platform"])
    return {
        "plan": plan,
        "candidate": candidate.to_dict(),
        "preflight": report,
        "source_unchanged": composition.to_dict()
        == MotionComposition.from_dict(composition.to_dict()).to_dict(),
    }


def _layer_bounds(layer: MotionLayer) -> tuple[float, float, float, float]:
    position = _vector(layer.transform.position.default, (0.0, 0.0))
    scale = _vector(layer.transform.scale.default, (1.0, 1.0))
    anchor = _vector(layer.transform.anchor.default, (0.5, 0.5))
    width, height = _layer_size(layer)
    scaled_width, scaled_height = abs(width * scale[0]), abs(height * scale[1])
    left = position[0] - scaled_width * anchor[0]
    top = position[1] - scaled_height * anchor[1]
    return left, top, left + scaled_width, top + scaled_height


def preflight_story(composition: MotionComposition) -> dict[str, Any]:
    state = inspect_story(composition)
    beats = state["beats"]
    issues: list[dict[str, Any]] = []
    known_layers = {layer.id for layer in composition.layers}
    last_end = 0
    last_direction: dict[str, str] = {}
    for index, beat in enumerate(beats):
        beat_id = str(beat.get("id") or "")
        start = _int(beat.get("start_ms"), 0)
        end = _int(beat.get("end_ms"), 0)
        if end <= start or start < 0 or end > composition.duration_ms:
            issues.append({"code": "invalid_beat_range", "beat_id": beat_id})
        if index and start < last_end:
            issues.append({"code": "overlapping_beats", "beat_id": beat_id})
        last_end = max(last_end, end)
        missing = [item for item in beat.get("layer_ids", []) if item not in known_layers]
        if missing:
            issues.append(
                {"code": "missing_beat_layers", "beat_id": beat_id, "layer_ids": missing}
            )
        character = str(beat.get("character") or "")
        direction = str(beat.get("screen_direction") or "")
        if character and direction:
            previous = last_direction.get(character)
            if previous and previous != direction and not bool(beat.get("direction_change_motivated")):
                issues.append(
                    {
                        "code": "screen_direction_discontinuity",
                        "beat_id": beat_id,
                        "character": character,
                        "before": previous,
                        "after": direction,
                    }
                )
            last_direction[character] = direction
    if not beats:
        issues.append({"code": "story_has_no_beats"})
    roles = {str(item.get("role") or "") for item in beats}
    if "hook" not in roles:
        issues.append({"code": "story_missing_hook"})
    if "cta" not in roles:
        issues.append({"code": "story_missing_cta"})
    return {
        "schema": "tigerstudio.motion.story_preflight.v1",
        "ok": not issues,
        "composition_id": composition.id,
        "beat_count": len(beats),
        "issues": issues,
    }


def preflight_platform(
    composition: MotionComposition,
    *,
    platform: str,
) -> dict[str, Any]:
    profile_id, profile = resolve_platform_profile(platform)
    safe = _safe_pixels(profile)
    subtitle_safe = _safe_pixels(profile, "subtitle")
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    for layer in composition.layers:
        if not layer.visible:
            continue
        role = _layer_role(layer)
        bounds = _layer_bounds(layer)
        expected = subtitle_safe if role == "subtitle" else safe
        protected = role in {"headline", "subtitle", "cta", "character", "mascot"}
        epsilon = 0.05
        clipped = (
            bounds[0] < expected[0] - epsilon
            or bounds[1] < expected[1] - epsilon
            or bounds[2] > expected[2] + epsilon
            or bounds[3] > expected[3] + epsilon
        )
        if protected and clipped:
            issues.append(
                {
                    "code": f"{role}_outside_safe_area",
                    "layer_id": layer.id,
                    "bounds": [round(item, 2) for item in bounds],
                    "safe": [round(item, 2) for item in expected],
                }
            )
        if layer.layer_type == "text" or layer.source.kind in {"text", "typography"}:
            font_size = _number(layer.source.params.get("font_size"), 48.0)
            if font_size < float(profile["min_text_px"]):
                issues.append(
                    {
                        "code": "text_below_platform_minimum",
                        "layer_id": layer.id,
                        "font_size": font_size,
                        "minimum": profile["min_text_px"],
                    }
                )
            text = str(
                layer.source.params.get("text")
                or layer.source.params.get("content")
                or ""
            )
            capacity = max(12, int((bounds[2] - bounds[0]) / max(1.0, font_size * 0.55)))
            if len(text) > capacity * 4:
                issues.append(
                    {
                        "code": "text_density_high",
                        "layer_id": layer.id,
                        "characters": len(text),
                        "recommended_max": capacity * 4,
                    }
                )
        checks.append(
            {
                "layer_id": layer.id,
                "role": role,
                "protected": protected,
                "clipped": bool(protected and clipped),
            }
        )
    state = inspect_story(composition)
    cta_beats = [item for item in state["beats"] if item.get("role") == "cta"]
    for beat in cta_beats:
        hold_ms = _int(beat.get("end_ms")) - _int(beat.get("start_ms"))
        if hold_ms < int(profile["cta_hold_ms"]):
            issues.append(
                {
                    "code": "cta_hold_too_short",
                    "beat_id": beat.get("id"),
                    "hold_ms": hold_ms,
                    "minimum_ms": profile["cta_hold_ms"],
                }
            )
    return {
        "schema": "tigerstudio.motion.platform_preflight.v1",
        "ok": not issues,
        "composition_id": composition.id,
        "platform": profile_id,
        "profile": profile,
        "checks": checks,
        "issues": issues,
        "summary": {
            "protected_layer_count": sum(1 for item in checks if item["protected"]),
            "clipped_protected_layer_count": sum(1 for item in checks if item["clipped"]),
            "issue_count": len(issues),
        },
    }


__all__ = [
    "BEAT_ROLES",
    "PLATFORM_PLAN_SCHEMA",
    "PLATFORM_PROFILES",
    "STORY_METADATA_KEY",
    "STORY_SCHEMA",
    "add_story_beat",
    "apply_platform_variant",
    "bind_story_audio",
    "inspect_story",
    "plan_platform_variant",
    "preflight_platform",
    "preflight_story",
    "preview_platform_variant",
    "reorder_story_beat",
    "resolve_platform_profile",
    "update_story",
    "update_story_beat",
]
