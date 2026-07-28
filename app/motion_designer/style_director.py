"""Reviewable AI style direction built from ordinary Motion authoring data."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from app.ai_providers import provider_snapshot

from .craft_style import make_craft_style_effect
from .glass_material import make_glass_effect
from .schema import MotionComposition, MotionEffectRef, MotionLayer, new_motion_id
from .stop_motion import set_stop_motion, set_stop_motion_material
from .validation import validate_composition


STYLE_DIRECTOR_SCHEMA = "tigerstudio.motion.ai_style_plan.v1"
STYLE_CANDIDATE_SCHEMA = "tigerstudio.motion.ai_style_candidate.v1"
STYLE_LOCK_SCHEMA = "tigerstudio.motion.ai_style_lock.v1"
STORY_PLAN_SCHEMA = "tigerstudio.motion.ai_story_plan.v1"
STYLE_DIRECTOR_KEY = "ai_style_director"
STYLE_LOCK_KEY = "ai_style_lock"
STYLE_IDS = ("clean", "craft", "collage", "glass", "stop_motion")


def _visual_layers(
    composition: MotionComposition,
    layer_ids: Iterable[str] = (),
) -> list[MotionLayer]:
    requested = {str(item) for item in layer_ids if str(item)}
    known = {layer.id for layer in composition.layers}
    missing = sorted(requested - known)
    if missing:
        raise KeyError(f"unknown style target layers: {missing}")
    return [
        layer
        for layer in composition.layers
        if layer.layer_type not in {
            "group", "null", "camera", "light", "audio", "adjustment",
        }
        and (not requested or layer.id in requested)
    ]


def _style_words(prompt: str) -> list[str]:
    text = str(prompt or "").casefold()
    labels = []
    for label, tokens in (
        ("premium", ("premium", "luxury", "editorial", "고급")),
        ("handmade", ("handmade", "craft", "paper", "collage", "수공", "종이")),
        ("glass", ("glass", "glossy", "liquid", "유리", "글래스")),
        ("tactile", ("clay", "felt", "stop motion", "stop-motion", "점토")),
        ("clean", ("clean", "minimal", "simple", "미니멀", "깔끔")),
        ("energetic", ("dynamic", "energetic", "impact", "active", "화려", "강렬")),
    ):
        if any(token in text for token in tokens):
            labels.append(label)
    return labels or ["balanced"]


def _story_intent(prompt: str) -> dict[str, Any]:
    text = " ".join(str(prompt or "").split())
    quoted = [
        " ".join(value.split())
        for value in re.findall(r'["“”\']([^"“”\']{1,240})["“”\']', text)
    ]
    return {
        "message": quoted[0] if quoted else text[:360],
        "cta": quoted[-1] if quoted else "",
        "tone": "energetic" if "energetic" in _style_words(text) else "balanced",
        "requested_story": any(
            token in text.casefold()
            for token in ("story", "narrative", "hook", "cta", "스토리", "이야기")
        ),
    }


def _reference_rows(references: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in references:
        row = dict(source)
        metadata = dict(row.get("metadata") or {})
        provenance = dict(metadata.get("provenance") or {})
        uri = str(row.get("uri") or "")
        if uri and not provenance:
            path = Path(uri).expanduser()
            provenance = {
                "source_uri": str(path),
                "exists": path.is_file(),
                "kind": str(row.get("kind") or "reference"),
            }
        rows.append({
            "id": str(row.get("id") or new_motion_id("style_reference")),
            "kind": str(row.get("kind") or "text"),
            "name": str(row.get("name") or ""),
            "uri": uri,
            "provenance": provenance,
        })
    return rows


def _backend_summary(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    providers = dict(snapshot.get("providers") or {})
    selected = str(snapshot.get("selected_provider") or "rule_based")
    effective = str(snapshot.get("effective_generation_provider") or "rule_based")
    selected_row = dict(providers.get(selected) or {})
    return {
        "selected_provider": selected,
        "effective_provider": effective,
        "available": bool(selected_row.get("available", effective == "rule_based")),
        "fallback_used": selected != effective,
        "fallback_reason": str(snapshot.get("fallback_reason") or ""),
        "estimated_cost": {
            "currency": "USD",
            "amount": 0.0,
            "basis": "deterministic_local_style_compilation",
        },
        "capabilities": {
            "segmentation": "optional_existing_pipeline",
            "glass_gpu_realtime": False,
            "glass_fallback": "shared_raster_cpu",
            "painterly_3d": False,
            "painterly_3d_fallback": "editable_2d_craft_treatment",
        },
    }


def _candidate(
    style_id: str,
    layer_ids: list[str],
    *,
    seed: int,
    style_words: list[str],
) -> dict[str, Any]:
    operations: list[dict[str, Any]]
    warnings: list[str] = []
    if style_id == "clean":
        operations = [{"type": "owned_style_clear"}]
    elif style_id == "craft":
        preset = "luxury_paper" if "premium" in style_words else "handmade"
        operations = [{
            "type": "craft_set",
            "preset": preset,
            "seed": seed,
        }]
    elif style_id == "collage":
        operations = [
            {"type": "collage_board_create", "layout": "manual", "seed": seed},
            {"type": "craft_set", "preset": "printed_poster", "seed": seed},
        ]
    elif style_id == "glass":
        operations = [{
            "type": "glass_set",
            "preset": "glossy" if "premium" in style_words else "frosted",
        }]
        warnings.append(
            "Realtime Glass GPU is unavailable; preview uses the shared raster fallback.",
        )
    else:
        operations = [{
            "type": "stop_motion_set",
            "settings": {
                "enabled": True,
                "exposure_frames": 2,
                "pose_jitter_px": 1.8,
                "rotation_jitter_deg": 0.45,
                "scale_jitter": 0.009,
                "motion_style": "contact_settle",
                "seed": seed,
            },
            "material": "clay",
        }]
    return {
        "schema": STYLE_CANDIDATE_SCHEMA,
        "id": new_motion_id("style_candidate"),
        "style_id": style_id,
        "title": style_id.replace("_", " ").title(),
        "target_layer_ids": list(layer_ids),
        "operations": operations,
        "warnings": warnings,
        "preview_times_ms": [0],
        "provenance": {
            "kind": "generated",
            "generator": "tiger_style_director_v1",
            "editable_result": True,
        },
        "preserves": [
            "layer_ids",
            "transform_defaults",
            "transform_keyframes",
            "source_media",
            "manual_effects",
        ],
    }


def plan_style_direction(
    composition: MotionComposition,
    prompt: str,
    references: Iterable[Mapping[str, Any]] = (),
    *,
    layer_ids: Iterable[str] = (),
    backend_snapshot: Mapping[str, Any] | None = None,
    seed: int = 20260729,
) -> dict[str, Any]:
    layers = _visual_layers(composition, layer_ids)
    words = _style_words(prompt)
    backend = _backend_summary(backend_snapshot or provider_snapshot())
    candidates = [
        _candidate(
            style_id,
            [layer.id for layer in layers],
            seed=int(seed),
            style_words=words,
        )
        for style_id in STYLE_IDS
    ]
    return {
        "schema": STYLE_DIRECTOR_SCHEMA,
        "id": new_motion_id("style_plan"),
        "composition_id": composition.id,
        "base_revision": composition.revision,
        "prompt": str(prompt or ""),
        "style_intent": {
            "keywords": words,
            "target_layer_ids": [layer.id for layer in layers],
            "seed": int(seed),
        },
        "story_intent": _story_intent(prompt),
        "references": _reference_rows(references),
        "backend": backend,
        "candidates": candidates,
        "review_required": True,
    }


def _validate_plan(
    composition: MotionComposition,
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = deepcopy(dict(plan))
    if str(normalized.get("schema") or "") != STYLE_DIRECTOR_SCHEMA:
        raise ValueError("unsupported AI style plan schema")
    if str(normalized.get("composition_id") or "") != composition.id:
        raise ValueError("AI style plan targets a different composition")
    if int(normalized.get("base_revision", -1)) != composition.revision:
        raise ValueError("AI style plan was created for a stale composition revision")
    candidates = normalized.get("candidates")
    if not isinstance(candidates, list) or {
        str(row.get("style_id") or "")
        for row in candidates
        if isinstance(row, Mapping)
    } != set(STYLE_IDS):
        raise ValueError("AI style plan must contain the five required candidates")
    return normalized


def _transform_fingerprint(composition: MotionComposition) -> str:
    rows = [
        {
            "id": layer.id,
            "transform": layer.transform.to_dict(),
            "source": layer.source.to_dict(),
        }
        for layer in composition.layers
    ]
    return sha256(repr(rows).encode("utf-8")).hexdigest()


def _remove_owned_effects(layer: MotionLayer) -> None:
    layer.effects = [
        effect
        for effect in layer.effects
        if not bool(effect.metadata.get("style_director"))
    ]


def _add_owned_effect(
    layer: MotionLayer,
    effect: MotionEffectRef,
    *,
    candidate_id: str,
) -> None:
    _remove_owned_effects(layer)
    effect.metadata.update({
        "style_director": True,
        "style_candidate_id": candidate_id,
        "provenance": "generated",
    })
    layer.effects.append(effect)


def set_style_lock(
    composition: MotionComposition,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    current = dict(composition.metadata.get(STYLE_LOCK_KEY) or {})
    current.update({
        key: deepcopy(value)
        for key, value in changes.items()
        if key in {
            "font_family",
            "texture_uri",
            "seed",
            "mascot_layer_ids",
            "protected_layer_ids",
        }
    })
    current["schema"] = STYLE_LOCK_SCHEMA
    current["seed"] = max(0, int(current.get("seed", 20260729) or 20260729))
    current["mascot_layer_ids"] = list(dict.fromkeys(
        str(item) for item in current.get("mascot_layer_ids", []) if str(item)
    ))
    current["protected_layer_ids"] = list(dict.fromkeys(
        str(item) for item in current.get("protected_layer_ids", []) if str(item)
    ))
    composition.metadata[STYLE_LOCK_KEY] = current
    return deepcopy(current)


def style_lock(composition: MotionComposition) -> dict[str, Any]:
    source = dict(composition.metadata.get(STYLE_LOCK_KEY) or {})
    source.setdefault("schema", STYLE_LOCK_SCHEMA)
    source["seed"] = max(0, int(source.get("seed", 20260729) or 20260729))
    source["mascot_layer_ids"] = list(dict.fromkeys(
        str(item) for item in source.get("mascot_layer_ids", []) if str(item)
    ))
    source["protected_layer_ids"] = list(dict.fromkeys(
        str(item) for item in source.get("protected_layer_ids", []) if str(item)
    ))
    return source


def apply_style_candidate(
    composition: MotionComposition,
    plan: Mapping[str, Any],
    candidate_id: str,
    *,
    approved: bool,
) -> tuple[MotionComposition, dict[str, Any]]:
    if not approved:
        raise ValueError("AI style candidate requires explicit approval")
    normalized = _validate_plan(composition, plan)
    candidate = next(
        (
            dict(row)
            for row in normalized["candidates"]
            if str(row.get("id") or "") == str(candidate_id)
        ),
        None,
    )
    if candidate is None:
        raise KeyError(f"unknown AI style candidate: {candidate_id}")
    before = _transform_fingerprint(composition)
    result = MotionComposition.from_dict(composition.to_dict())
    lock = style_lock(result)
    protected = set(lock.get("protected_layer_ids") or ())
    target_ids = [
        str(item)
        for item in candidate.get("target_layer_ids", [])
        if str(item) and str(item) not in protected
    ]
    visually_changed_ids: set[str] = set()
    layers = {layer.id: layer for layer in result.layers}
    for layer_id in target_ids:
        if (
            any(
                bool(effect.metadata.get("style_director"))
                for effect in layers[layer_id].effects
            )
            or bool(layers[layer_id].metadata.get("style_director_stop_motion"))
        ):
            visually_changed_ids.add(layer_id)
        _remove_owned_effects(layers[layer_id])
        if layers[layer_id].metadata.get("style_director_stop_motion"):
            layers[layer_id].metadata.pop("stop_motion", None)
            layers[layer_id].metadata.pop("stop_motion_material", None)
            layers[layer_id].metadata.pop("style_director_stop_motion", None)
    boards = list(result.metadata.get("collage_boards") or [])
    removed_board_ids = {
        str(board.get("id") or "")
        for board in boards
        if isinstance(board, Mapping) and board.get("style_director")
    }
    if removed_board_ids:
        result.metadata["collage_boards"] = [
            board for board in boards
            if str(board.get("id") or "") not in removed_board_ids
        ]
        for layer in result.layers:
            item = layer.metadata.get("collage_item")
            if (
                isinstance(item, Mapping)
                and str(item.get("board_id") or "") in removed_board_ids
            ):
                visually_changed_ids.add(layer.id)
                layer.metadata.pop("collage_item", None)
    for operation in candidate.get("operations", []):
        kind = str(operation.get("type") or "")
        if kind == "owned_style_clear":
            for layer_id in target_ids:
                _remove_owned_effects(layers[layer_id])
        elif kind == "craft_set":
            for layer_id in target_ids:
                effect = make_craft_style_effect(
                    {
                        "seed": int(operation.get("seed", lock["seed"])),
                        "seed_locked": True,
                    },
                    preset=str(operation.get("preset") or "handmade"),
                )
                _add_owned_effect(
                    layers[layer_id],
                    effect,
                    candidate_id=str(candidate["id"]),
                )
                visually_changed_ids.add(layer_id)
        elif kind == "glass_set" and target_ids:
            glass_target_id = next(
                (
                    layer_id
                    for layer_id in target_ids
                    if (
                        float(layers[layer_id].source.params.get("width", 0.0) or 0.0)
                        < result.width * 0.9
                        or float(layers[layer_id].source.params.get("height", 0.0) or 0.0)
                        < result.height * 0.9
                    )
                ),
                target_ids[0],
            )
            effect = make_glass_effect(
                preset=str(operation.get("preset") or "frosted"),
            )
            _add_owned_effect(
                layers[glass_target_id],
                effect,
                candidate_id=str(candidate["id"]),
            )
            visually_changed_ids.add(glass_target_id)
        elif kind == "collage_board_create" and target_ids:
            from .collage import create_collage_board

            board = create_collage_board(
                result,
                target_ids,
                name="AI Editorial Collage",
                layout="manual",
                seed=int(operation.get("seed", lock["seed"])),
            )
            board_state = next(
                row
                for row in result.metadata["collage_boards"]
                if row["id"] == board["id"]
            )
            board_state["style_director"] = {
                "candidate_id": str(candidate["id"]),
                "provenance": "generated",
            }
            visually_changed_ids.update(target_ids)
        elif kind == "stop_motion_set" and target_ids:
            settings = dict(operation.get("settings") or {})
            set_stop_motion(result, settings, layer_ids=target_ids)
            for layer_id in target_ids:
                set_stop_motion_material(
                    result,
                    [layer_id],
                    preset=str(operation.get("material") or "clay"),
                    seed=int(settings.get("seed", lock["seed"])),
                )
                layer = layers[layer_id]
                layer.metadata["style_director_stop_motion"] = {
                    "candidate_id": str(candidate["id"]),
                    "provenance": "generated",
                }
                for effect in layer.effects:
                    if effect.metadata.get("stop_motion_material"):
                        effect.metadata.update({
                            "style_director": True,
                            "style_candidate_id": str(candidate["id"]),
                            "provenance": "generated",
                        })
                visually_changed_ids.add(layer_id)
    if _transform_fingerprint(result) != before:
        raise RuntimeError(
            "AI style candidate attempted to change source or transform/keyframe data",
        )
    result.metadata[STYLE_DIRECTOR_KEY] = {
        "schema": STYLE_DIRECTOR_SCHEMA,
        "plan_id": str(normalized["id"]),
        "candidate_id": str(candidate["id"]),
        "style_id": str(candidate["style_id"]),
        "prompt": str(normalized.get("prompt") or ""),
        "references": deepcopy(normalized.get("references") or []),
        "backend": deepcopy(normalized.get("backend") or {}),
        "provenance": "generated",
    }
    result.revision += 1
    validation = validate_composition(result)
    if not validation.ok:
        raise ValueError(validation.issues[0].message)
    return result, {
        "plan_id": str(normalized["id"]),
        "candidate_id": str(candidate["id"]),
        "style_id": str(candidate["style_id"]),
        "protected_layer_ids": sorted(protected),
        "applied_layer_ids": target_ids,
        "visually_changed_layer_ids": [
            layer_id for layer_id in target_ids if layer_id in visually_changed_ids
        ],
        "transform_keyframes_preserved": True,
    }


def plan_story_direction(
    composition: MotionComposition,
    prompt: str,
) -> dict[str, Any]:
    intent = _story_intent(prompt)
    roles = ("hook", "setup", "desire", "conflict", "reveal", "proof", "payoff", "cta")
    beats = []
    for index, role in enumerate(roles):
        start = round(composition.duration_ms * index / len(roles))
        end = round(composition.duration_ms * (index + 1) / len(roles))
        beats.append({
            "id": new_motion_id("story_beat"),
            "role": role,
            "start_ms": start,
            "end_ms": max(start + 1, end),
            "purpose": role.replace("_", " ").title(),
            "emotion": "resolve" if role == "cta" else intent["tone"],
            "copy": intent["cta"] if role == "cta" else "",
        })
    return {
        "schema": STORY_PLAN_SCHEMA,
        "id": new_motion_id("ai_story_plan"),
        "composition_id": composition.id,
        "base_revision": composition.revision,
        "intent": intent,
        "beats": beats,
        "review_required": True,
    }


def apply_story_direction(
    composition: MotionComposition,
    plan: Mapping[str, Any],
    *,
    approved: bool,
) -> tuple[MotionComposition, dict[str, Any]]:
    if not approved:
        raise ValueError("AI story plan requires explicit approval")
    if str(plan.get("schema") or "") != STORY_PLAN_SCHEMA:
        raise ValueError("unsupported AI story plan schema")
    if str(plan.get("composition_id") or "") != composition.id:
        raise ValueError("AI story plan targets a different composition")
    if int(plan.get("base_revision", -1)) != composition.revision:
        raise ValueError("AI story plan was created for a stale composition revision")
    from .story_direction import add_story_beat, update_story

    result = MotionComposition.from_dict(composition.to_dict())
    intent = dict(plan.get("intent") or {})
    update_story(result, {
        "message": str(intent.get("message") or ""),
        "style_director_plan_id": str(plan.get("id") or ""),
    })
    result.metadata["story_direction"]["beats"] = []
    for beat in plan.get("beats", []):
        created = add_story_beat(result, **{
            key: value
            for key, value in dict(beat).items()
            if key in {
                "role", "start_ms", "end_ms", "purpose", "emotion", "copy",
            }
        })
        created["id"] = str(beat.get("id") or created["id"])
        result.metadata["story_direction"]["beats"][-1]["id"] = created["id"]
    result.revision += 1
    return result, {
        "plan_id": str(plan.get("id") or ""),
        "beat_count": len(result.metadata["story_direction"]["beats"]),
    }


def trend_preflight(
    composition: MotionComposition,
    plan: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if plan is not None:
        try:
            normalized = _validate_plan(composition, plan)
        except (KeyError, TypeError, ValueError) as exc:
            issues.append({"code": "invalid_style_plan", "message": str(exc)})
            normalized = {}
        backend = dict(normalized.get("backend") or {})
        capabilities = dict(backend.get("capabilities") or {})
        if not capabilities.get("glass_gpu_realtime", False):
            warnings.append({
                "code": "glass_gpu_fallback",
                "fallback": capabilities.get("glass_fallback", "shared_raster_cpu"),
            })
        if not capabilities.get("painterly_3d", False):
            warnings.append({
                "code": "painterly_3d_unavailable",
                "fallback": capabilities.get(
                    "painterly_3d_fallback",
                    "editable_2d_craft_treatment",
                ),
            })
    else:
        normalized = {}
        warnings.append({"code": "style_plan_missing"})
    lock = style_lock(composition)
    known = {layer.id for layer in composition.layers}
    unknown_locks = sorted(
        (
            set(lock.get("protected_layer_ids") or ())
            | set(lock.get("mascot_layer_ids") or ())
        )
        - known
    )
    if unknown_locks:
        issues.append({
            "code": "style_lock_unknown_layers",
            "layer_ids": unknown_locks,
        })
    return {
        "schema": "tigerstudio.motion.ai_trend_preflight.v1",
        "ok": not issues,
        "composition_id": composition.id,
        "plan_id": str(normalized.get("id") or ""),
        "issues": issues,
        "warnings": warnings,
        "style_lock": lock,
        "summary": {
            "issue_count": len(issues),
            "warning_count": len(warnings),
            "candidate_count": len(normalized.get("candidates") or []),
        },
    }


__all__ = [
    "STORY_PLAN_SCHEMA",
    "STYLE_CANDIDATE_SCHEMA",
    "STYLE_DIRECTOR_SCHEMA",
    "STYLE_IDS",
    "STYLE_LOCK_SCHEMA",
    "apply_story_direction",
    "apply_style_candidate",
    "plan_story_direction",
    "plan_style_direction",
    "set_style_lock",
    "style_lock",
    "trend_preflight",
]
