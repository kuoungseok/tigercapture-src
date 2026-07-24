"""Validated AI brief, storyboard, composition, and patch contracts for Motion Designer."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Mapping

from app.ai_providers import generate_selected_provider_json, provider_snapshot

from .ai_planner import analyze_motion_ai_layers
from .ai_workspace import MotionAIProposal, MotionAIReference
from .schema import (
    MotionBehaviorRef,
    MotionComposition,
    MotionLayer,
    SourceRef,
    new_motion_id,
)
from .validation import validate_composition


MOTION_AI_GENERATION_SCHEMA = "tigercapture.motion.ai.generation-plan.v1"
MOTION_AI_PATCH_SCHEMA = "tigercapture.motion.ai.patch.v1"
MAX_BEATS = 12
MAX_PATCH_OPERATIONS = 64
FORBIDDEN_KEYS = {
    "code", "command", "commands", "eval", "exec", "function", "javascript",
    "mutation", "powershell", "project_mutation", "python", "script", "shell",
    "sql", "subprocess", "terminal",
}
LAYOUTS = {
    "center", "full_bleed", "grid", "lower_third", "split_left",
    "split_right", "title_card",
}
MOTIONS = {"fade", "hold", "pop", "slide_left", "slide_right", "zoom_in", "zoom_out"}
PATCH_TYPES = {"set_behavior", "set_text", "set_timing", "set_transform", "set_visibility"}
TRANSFORM_PROPERTIES = {"anchor", "opacity", "position", "rotation", "scale"}

MOTION_AI_GENERATION_CONTRACT_V1: dict[str, Any] = {
    "schema": MOTION_AI_GENERATION_SCHEMA,
    "root_keys": [
        "schema", "id", "composition_id", "base_revision", "prompt",
        "brief", "beats", "warnings", "metadata",
    ],
    "brief_keys": [
        "objective", "duration_ms", "aspect_ratio", "tone_keywords",
        "title", "subtitle", "cta",
    ],
    "beat_keys": [
        "id", "start_ms", "end_ms", "purpose", "layout", "motion",
        "reference_ids", "text", "notes",
    ],
    "layouts": sorted(LAYOUTS),
    "motions": sorted(MOTIONS),
    "limits": {"max_beats": MAX_BEATS},
}

MOTION_AI_PATCH_CONTRACT_V1: dict[str, Any] = {
    "schema": MOTION_AI_PATCH_SCHEMA,
    "root_keys": [
        "schema", "id", "composition_id", "base_revision", "prompt",
        "summary", "operations", "warnings", "metadata",
    ],
    "operation_keys": ["id", "type", "layer_id", "params", "reason"],
    "operation_types": sorted(PATCH_TYPES),
    "transform_properties": sorted(TRANSFORM_PROPERTIES),
    "limits": {"max_operations": MAX_PATCH_OPERATIONS},
}


class MotionAIContractError(ValueError):
    pass


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MotionAIContractError(f"{path} must be an object")
    return value


def _known_keys(
    value: Mapping[str, Any],
    *,
    allowed: set[str],
    required: set[str],
    path: str,
) -> None:
    unknown = sorted(str(key) for key in value if str(key) not in allowed)
    if unknown:
        raise MotionAIContractError(f"{path} contains unknown keys: {', '.join(unknown)}")
    missing = sorted(key for key in required if key not in value)
    if missing:
        raise MotionAIContractError(f"{path} is missing keys: {', '.join(missing)}")


def _reject_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).strip().casefold()
            if name in FORBIDDEN_KEYS:
                raise MotionAIContractError(f"forbidden key at {path}.{key}")
            _reject_forbidden(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_forbidden(child, f"{path}[{index}]")


def _bounded_text(value: Any, *, limit: int, path: str, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise MotionAIContractError(f"{path} must not be empty")
    if len(text) > limit:
        raise MotionAIContractError(f"{path} exceeds {limit} characters")
    return text


def _int(value: Any, *, path: str, minimum: int = 0, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise MotionAIContractError(f"{path} must be an integer") from exc
    if number < minimum or (maximum is not None and number > maximum):
        suffix = f"..{maximum}" if maximum is not None else f" or greater"
        raise MotionAIContractError(f"{path} must be {minimum}{suffix}")
    return number


@dataclass(slots=True)
class MotionCreativeBrief:
    objective: str
    duration_ms: int
    aspect_ratio: str
    tone_keywords: list[str] = field(default_factory=list)
    title: str = ""
    subtitle: str = ""
    cta: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "duration_ms": int(self.duration_ms),
            "aspect_ratio": self.aspect_ratio,
            "tone_keywords": list(self.tone_keywords),
            "title": self.title,
            "subtitle": self.subtitle,
            "cta": self.cta,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionCreativeBrief":
        data = _mapping(data, "brief")
        keys = {"objective", "duration_ms", "aspect_ratio", "tone_keywords", "title", "subtitle", "cta"}
        _known_keys(data, allowed=keys, required=keys, path="brief")
        tones = data.get("tone_keywords")
        if not isinstance(tones, list):
            raise MotionAIContractError("brief.tone_keywords must be an array")
        return cls(
            objective=_bounded_text(data.get("objective"), limit=1000, path="brief.objective", required=True),
            duration_ms=_int(data.get("duration_ms"), path="brief.duration_ms", minimum=1, maximum=3_600_000),
            aspect_ratio=_bounded_text(data.get("aspect_ratio"), limit=32, path="brief.aspect_ratio", required=True),
            tone_keywords=[_bounded_text(item, limit=80, path="brief.tone_keywords") for item in tones[:16]],
            title=_bounded_text(data.get("title"), limit=300, path="brief.title"),
            subtitle=_bounded_text(data.get("subtitle"), limit=600, path="brief.subtitle"),
            cta=_bounded_text(data.get("cta"), limit=200, path="brief.cta"),
        )


@dataclass(slots=True)
class MotionStoryboardBeat:
    id: str
    start_ms: int
    end_ms: int
    purpose: str
    layout: str
    motion: str
    reference_ids: list[str] = field(default_factory=list)
    text: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
            "purpose": self.purpose,
            "layout": self.layout,
            "motion": self.motion,
            "reference_ids": list(self.reference_ids),
            "text": self.text,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, duration_ms: int) -> "MotionStoryboardBeat":
        data = _mapping(data, "beat")
        keys = {"id", "start_ms", "end_ms", "purpose", "layout", "motion", "reference_ids", "text", "notes"}
        _known_keys(data, allowed=keys, required=keys, path="beat")
        start_ms = _int(data.get("start_ms"), path="beat.start_ms", maximum=duration_ms)
        end_ms = _int(data.get("end_ms"), path="beat.end_ms", minimum=1, maximum=duration_ms)
        if end_ms <= start_ms:
            raise MotionAIContractError("beat.end_ms must be after beat.start_ms")
        layout = _bounded_text(data.get("layout"), limit=40, path="beat.layout", required=True)
        motion = _bounded_text(data.get("motion"), limit=40, path="beat.motion", required=True)
        if layout not in LAYOUTS:
            raise MotionAIContractError(f"unsupported beat.layout: {layout}")
        if motion not in MOTIONS:
            raise MotionAIContractError(f"unsupported beat.motion: {motion}")
        refs = data.get("reference_ids")
        if not isinstance(refs, list):
            raise MotionAIContractError("beat.reference_ids must be an array")
        return cls(
            id=_bounded_text(data.get("id"), limit=120, path="beat.id", required=True),
            start_ms=start_ms,
            end_ms=end_ms,
            purpose=_bounded_text(data.get("purpose"), limit=300, path="beat.purpose", required=True),
            layout=layout,
            motion=motion,
            reference_ids=[_bounded_text(item, limit=160, path="beat.reference_ids") for item in refs[:16]],
            text=_bounded_text(data.get("text"), limit=1200, path="beat.text"),
            notes=_bounded_text(data.get("notes"), limit=1200, path="beat.notes"),
        )


@dataclass(slots=True)
class MotionAIGenerationPlan:
    composition_id: str
    base_revision: int
    prompt: str
    brief: MotionCreativeBrief
    beats: list[MotionStoryboardBeat]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_motion_id("ai_generation"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MOTION_AI_GENERATION_SCHEMA,
            "id": self.id,
            "composition_id": self.composition_id,
            "base_revision": int(self.base_revision),
            "prompt": self.prompt,
            "brief": self.brief.to_dict(),
            "beats": [item.to_dict() for item in self.beats],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MotionAIGenerationPlan":
        data = _mapping(data, "generation_plan")
        _reject_forbidden(data)
        keys = {"schema", "id", "composition_id", "base_revision", "prompt", "brief", "beats", "warnings", "metadata"}
        _known_keys(data, allowed=keys, required=keys, path="generation_plan")
        if str(data.get("schema") or "") != MOTION_AI_GENERATION_SCHEMA:
            raise MotionAIContractError("unsupported Motion AI generation schema")
        brief = MotionCreativeBrief.from_dict(_mapping(data.get("brief"), "brief"))
        rows = data.get("beats")
        if not isinstance(rows, list) or not rows:
            raise MotionAIContractError("generation_plan.beats must contain at least one beat")
        if len(rows) > MAX_BEATS:
            raise MotionAIContractError(f"generation_plan.beats exceeds {MAX_BEATS}")
        beats = [MotionStoryboardBeat.from_dict(_mapping(row, "beat"), duration_ms=brief.duration_ms) for row in rows]
        ids = [item.id for item in beats]
        if len(ids) != len(set(ids)):
            raise MotionAIContractError("generation_plan beat ids must be unique")
        warnings = data.get("warnings")
        metadata = data.get("metadata")
        if not isinstance(warnings, list) or not isinstance(metadata, Mapping):
            raise MotionAIContractError("generation_plan warnings/metadata types are invalid")
        return cls(
            id=_bounded_text(data.get("id"), limit=160, path="generation_plan.id", required=True),
            composition_id=_bounded_text(data.get("composition_id"), limit=160, path="generation_plan.composition_id", required=True),
            base_revision=_int(data.get("base_revision"), path="generation_plan.base_revision", minimum=1),
            prompt=_bounded_text(data.get("prompt"), limit=8000, path="generation_plan.prompt"),
            brief=brief,
            beats=beats,
            warnings=[_bounded_text(item, limit=1200, path="generation_plan.warnings") for item in warnings[:64]],
            metadata=dict(metadata),
        )


def validate_motion_generation_plan(
    data: Mapping[str, Any],
    *,
    composition: MotionComposition | None = None,
    reference_ids: Iterable[str] = (),
) -> dict[str, Any]:
    plan = MotionAIGenerationPlan.from_dict(data)
    if composition is not None:
        if plan.composition_id != composition.id:
            raise MotionAIContractError("generation plan targets a different composition")
        if plan.base_revision != composition.revision:
            raise MotionAIContractError("generation plan was created for a different composition revision")
        if plan.brief.duration_ms != composition.duration_ms:
            raise MotionAIContractError("generation plan duration must match the composition")
        expected_ratio = f"{composition.width}:{composition.height}"
        if not plan.brief.aspect_ratio:
            raise MotionAIContractError(f"generation plan aspect ratio must identify {expected_ratio}")
    known_refs = {str(item) for item in reference_ids if str(item)}
    if known_refs:
        unknown = sorted({ref for beat in plan.beats for ref in beat.reference_ids if ref not in known_refs})
        if unknown:
            raise MotionAIContractError(f"generation plan references unknown assets: {', '.join(unknown)}")
    return plan.to_dict()


def _aspect_ratio(width: int, height: int) -> str:
    def gcd(left: int, right: int) -> int:
        while right:
            left, right = right, left % right
        return max(1, left)

    divisor = gcd(max(1, width), max(1, height))
    return f"{max(1, width) // divisor}:{max(1, height) // divisor}"


def _quoted_text(prompt: str) -> list[str]:
    values = re.findall(r'["\u201c\u201d\'\u2018\u2019]([^"\u201c\u201d\'\u2018\u2019]{1,300})["\u201c\u201d\'\u2018\u2019]', prompt)
    return [" ".join(value.split()) for value in values if value.strip()]


def _prompt_motion(prompt: str, index: int) -> str:
    normalized = prompt.casefold()
    if any(token in normalized for token in ("pop", "bounce", "팝", "튀")):
        return "pop"
    if any(token in normalized for token in ("zoom", "확대", "줌")):
        return "zoom_in"
    if any(token in normalized for token in ("slide", "슬라이드", "밀려")):
        return "slide_left" if index % 2 == 0 else "slide_right"
    return "fade" if index == 0 else ("zoom_in" if index % 2 else "slide_left")


def build_deterministic_generation_plan(
    composition: MotionComposition,
    prompt: str,
    references: Iterable[MotionAIReference | Mapping[str, Any]],
) -> MotionAIGenerationPlan:
    refs = [item if isinstance(item, MotionAIReference) else MotionAIReference.from_dict(item) for item in references]
    images = [item for item in refs if item.kind == "image"]
    text_refs = [item for item in refs if item.kind == "text" and item.text.strip()]
    quoted = _quoted_text(prompt)
    text_values = quoted + [item.text.strip()[:300] for item in text_refs]
    title = text_values[0] if text_values else composition.name
    subtitle = text_values[1] if len(text_values) > 1 else ""
    cta = text_values[-1] if len(text_values) > 2 else ""
    normalized = str(prompt or "").casefold()
    tones = [
        label for tokens, label in (
            (("bold", "강렬", "화려"), "bold"),
            (("clean", "minimal", "깔끔", "미니멀"), "clean"),
            (("cute", "귀여", "kawaii"), "playful"),
            (("cinematic", "영화", "시네마"), "cinematic"),
            (("premium", "luxury", "고급"), "premium"),
        ) if any(token in normalized for token in tokens)
    ] or ["balanced"]
    beat_count = max(1, min(6, len(images) or (3 if prompt.strip() else 1)))
    beats: list[MotionStoryboardBeat] = []
    for index in range(beat_count):
        start_ms = round(composition.duration_ms * index / beat_count)
        end_ms = composition.duration_ms if index == beat_count - 1 else round(composition.duration_ms * (index + 1) / beat_count)
        reference_ids = [images[index % len(images)].id] if images else []
        text = title if index == 0 else (cta if index == beat_count - 1 and cta else "")
        beats.append(MotionStoryboardBeat(
            id=f"beat_{index + 1:02d}",
            start_ms=start_ms,
            end_ms=max(start_ms + 1, end_ms),
            purpose="Hook" if index == 0 else ("Call to action" if index == beat_count - 1 else "Develop"),
            layout="full_bleed" if reference_ids else "title_card",
            motion=_prompt_motion(prompt, index),
            reference_ids=reference_ids,
            text=text,
            notes="Deterministic safe baseline; review before apply.",
        ))
    return MotionAIGenerationPlan(
        composition_id=composition.id,
        base_revision=composition.revision,
        prompt=str(prompt or "").strip(),
        brief=MotionCreativeBrief(
            objective=str(prompt or "").strip() or "Create an editable motion composition",
            duration_ms=composition.duration_ms,
            aspect_ratio=_aspect_ratio(composition.width, composition.height),
            tone_keywords=tones,
            title=title,
            subtitle=subtitle,
            cta=cta,
        ),
        beats=beats,
        warnings=[] if images else ["No image reference was supplied; a native title-card baseline was created."],
        metadata={"planner": "deterministic_baseline", "reference_count": len(refs)},
    )


def _layout_geometry(layout: str, width: int, height: int) -> tuple[float, float, int, int, str]:
    if layout == "split_left":
        return width * .27, height * .5, round(width * .48), round(height * .82), "cover"
    if layout == "split_right":
        return width * .73, height * .5, round(width * .48), round(height * .82), "cover"
    if layout == "center":
        return width * .5, height * .5, round(width * .76), round(height * .76), "contain"
    return width * .5, height * .5, width, height, "cover"


def _motion_behavior(beat: MotionStoryboardBeat) -> MotionBehaviorRef | None:
    span = min(900, max(120, beat.end_ms - beat.start_ms))
    if beat.motion == "hold":
        return None
    params: dict[str, Any] = {"direction": "in"}
    kind = beat.motion
    if kind == "slide_left":
        kind, params = "slide", {"direction": "in", "distance": [180.0, 0.0]}
    elif kind == "slide_right":
        kind, params = "slide", {"direction": "in", "distance": [-180.0, 0.0]}
    elif kind in {"zoom_in", "zoom_out"}:
        kind, params = "pop", {"from": .86 if beat.motion == "zoom_in" else 1.12, "overshoot": .04}
    elif kind == "pop":
        params = {"from": .8, "overshoot": .12}
    # Behaviors are evaluated against layer-local time. Using storyboard
    # timeline offsets here delays every beat after the first one twice.
    return MotionBehaviorRef(kind=kind, start_ms=0, end_ms=span, params=params)


def compile_generation_plan(
    composition: MotionComposition,
    plan: MotionAIGenerationPlan | Mapping[str, Any],
    references: Iterable[MotionAIReference | Mapping[str, Any]],
    *,
    provider: str,
    provider_metadata: Mapping[str, Any] | None = None,
) -> MotionAIProposal:
    normalized = plan if isinstance(plan, MotionAIGenerationPlan) else MotionAIGenerationPlan.from_dict(plan)
    refs = [item if isinstance(item, MotionAIReference) else MotionAIReference.from_dict(item) for item in references]
    validate_motion_generation_plan(normalized.to_dict(), composition=composition, reference_ids=[item.id for item in refs])
    by_id = {item.id: item for item in refs}
    layers: list[MotionLayer] = []
    warnings = list(normalized.warnings)
    for beat in normalized.beats:
        behavior = _motion_behavior(beat)
        image_ref = next((by_id.get(ref_id) for ref_id in beat.reference_ids if by_id.get(ref_id, None) and by_id[ref_id].kind == "image"), None)
        if image_ref is not None:
            x, y, layer_width, layer_height, fit = _layout_geometry(beat.layout, composition.width, composition.height)
            layer = MotionLayer(
                name=image_ref.name or beat.purpose,
                layer_type="image",
                source=SourceRef(kind="image", uri=image_ref.uri, params={
                    "width": layer_width, "height": layer_height, "fit": fit,
                }),
                in_ms=beat.start_ms,
                out_ms=beat.end_ms,
                metadata={
                    "ai_generation_id": normalized.id,
                    "ai_beat_id": beat.id,
                    "ai_reference_id": image_ref.id,
                },
            )
            layer.transform.position.default = [float(x), float(y)]
            if behavior is not None:
                layer.behaviors = [behavior]
            if image_ref.uri and not image_ref.uri.startswith(("http://", "https://")):
                from pathlib import Path
                if not Path(image_ref.uri).is_file():
                    warnings.append(f"Image needs relink before rendering: {image_ref.name or image_ref.uri}")
            layers.append(layer)
        elif beat.layout == "title_card":
            layer = MotionLayer(
                name=f"{beat.purpose} Background",
                layer_type="shape",
                source=SourceRef(kind="shape", params={
                    "primitive": "rectangle", "width": composition.width, "height": composition.height,
                    "fill": "#151922", "stroke": "#151922", "stroke_width": 0.0,
                }),
                in_ms=beat.start_ms,
                out_ms=beat.end_ms,
                metadata={"ai_generation_id": normalized.id, "ai_beat_id": beat.id},
            )
            layer.transform.position.default = [composition.width / 2, composition.height / 2]
            if behavior is not None:
                layer.behaviors = [behavior]
            layers.append(layer)
        if beat.text:
            text_layer = MotionLayer(
                name=f"{beat.purpose} Text",
                layer_type="text",
                source=SourceRef(kind="typography", params={
                    "text": beat.text,
                    "font_family": "Segoe UI",
                    "font_size": max(28, round(composition.height * .075)),
                    "font_weight": 700,
                    "fill": "#f5f7fa",
                    "stroke": "#111317cc",
                    "stroke_width": 1.5,
                    "alignment": "center",
                    "width": round(composition.width * .82),
                    "height": round(composition.height * .24),
                    "line_height": 1.12,
                }),
                in_ms=beat.start_ms,
                out_ms=beat.end_ms,
                metadata={"ai_generation_id": normalized.id, "ai_beat_id": beat.id},
            )
            text_layer.transform.position.default = [composition.width / 2, composition.height * .78]
            if behavior is not None:
                text_layer.behaviors = [MotionBehaviorRef.from_dict(behavior.to_dict())]
            layers.append(text_layer)
    analysis = analyze_motion_ai_layers(composition, layers)
    analysis["generation_plan"] = normalized.to_dict()
    analysis["provider_contract"] = dict(provider_metadata or {})
    warnings.extend(str(item) for item in analysis.get("warnings", []))
    return MotionAIProposal(
        composition_id=composition.id,
        request_id=normalized.id,
        layers=layers,
        summary=f"{normalized.brief.objective} ({len(normalized.beats)} beats, {len(layers)} editable layers)",
        warnings=list(dict.fromkeys(warnings)),
        analysis=analysis,
        provider=provider,
    )


def generate_motion_ai_proposal(
    composition: MotionComposition,
    prompt: str,
    references: Iterable[MotionAIReference | Mapping[str, Any]],
    *,
    provider_id: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 90,
) -> MotionAIProposal:
    refs = [item if isinstance(item, MotionAIReference) else MotionAIReference.from_dict(item) for item in references]
    baseline = build_deterministic_generation_plan(composition, prompt, refs)
    requested_provider = "rule_based" if provider_id in {"local_layout", "rule_based"} else provider_id
    result = generate_selected_provider_json(
        "tiger_studio_motion_generation",
        prompt,
        output_contract=MOTION_AI_GENERATION_CONTRACT_V1,
        input_payload={
            "composition": {
                "id": composition.id,
                "revision": composition.revision,
                "width": composition.width,
                "height": composition.height,
                "fps": composition.fps,
                "duration_ms": composition.duration_ms,
            },
            "references": [item.to_dict() for item in refs],
        },
        safe_baseline=baseline.to_dict(),
        validate_payload=lambda value: validate_motion_generation_plan(
            value, composition=composition, reference_ids=[item.id for item in refs],
        ),
        provider_id=requested_provider,
        env=env,
        timeout_seconds=max(1, int(timeout_seconds)),
    )
    if not result.ok or result.payload is None:
        raise MotionAIContractError(result.reason or "Motion AI generation failed")
    plan = MotionAIGenerationPlan.from_dict(result.payload)
    provider_meta = result.to_dict()
    provider_meta.pop("payload", None)
    proposal = compile_generation_plan(
        composition, plan, refs, provider=result.provider, provider_metadata=provider_meta,
    )
    if result.fallback_used and result.reason:
        proposal.warnings.insert(0, result.reason)
    return proposal


@dataclass(slots=True)
class MotionAIPatchOperation:
    type: str
    layer_id: str
    params: dict[str, Any]
    reason: str = ""
    id: str = field(default_factory=lambda: new_motion_id("ai_patch_op"))

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "layer_id": self.layer_id, "params": dict(self.params), "reason": self.reason}


@dataclass(slots=True)
class MotionAIPatch:
    composition_id: str
    base_revision: int
    prompt: str
    summary: str
    operations: list[MotionAIPatchOperation]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_motion_id("ai_patch"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MOTION_AI_PATCH_SCHEMA,
            "id": self.id,
            "composition_id": self.composition_id,
            "base_revision": int(self.base_revision),
            "prompt": self.prompt,
            "summary": self.summary,
            "operations": [item.to_dict() for item in self.operations],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


def validate_motion_ai_patch(
    data: Mapping[str, Any],
    *,
    composition: MotionComposition | None = None,
) -> dict[str, Any]:
    data = _mapping(data, "patch")
    _reject_forbidden(data)
    keys = {"schema", "id", "composition_id", "base_revision", "prompt", "summary", "operations", "warnings", "metadata"}
    _known_keys(data, allowed=keys, required=keys, path="patch")
    if str(data.get("schema") or "") != MOTION_AI_PATCH_SCHEMA:
        raise MotionAIContractError("unsupported Motion AI patch schema")
    operations = data.get("operations")
    warnings = data.get("warnings")
    metadata = data.get("metadata")
    if not isinstance(operations, list) or len(operations) > MAX_PATCH_OPERATIONS:
        raise MotionAIContractError(f"patch.operations must be an array of at most {MAX_PATCH_OPERATIONS}")
    if not isinstance(warnings, list) or not isinstance(metadata, Mapping):
        raise MotionAIContractError("patch warnings/metadata types are invalid")
    known_layers = {item.id: item for item in composition.layers} if composition is not None else {}
    normalized_ops: list[dict[str, Any]] = []
    op_ids: set[str] = set()
    for index, raw in enumerate(operations):
        row = _mapping(raw, f"patch.operations[{index}]")
        op_keys = {"id", "type", "layer_id", "params", "reason"}
        _known_keys(row, allowed=op_keys, required=op_keys, path=f"patch.operations[{index}]")
        op_id = _bounded_text(row.get("id"), limit=160, path="operation.id", required=True)
        op_type = _bounded_text(row.get("type"), limit=40, path="operation.type", required=True)
        layer_id = _bounded_text(row.get("layer_id"), limit=160, path="operation.layer_id", required=True)
        params = _mapping(row.get("params"), "operation.params")
        if op_id in op_ids:
            raise MotionAIContractError("patch operation ids must be unique")
        if op_type not in PATCH_TYPES:
            raise MotionAIContractError(f"unsupported patch operation: {op_type}")
        if composition is not None and layer_id not in known_layers:
            raise MotionAIContractError(f"patch targets unknown layer: {layer_id}")
        if op_type == "set_text":
            _known_keys(params, allowed={"text"}, required={"text"}, path="operation.params")
            _bounded_text(params.get("text"), limit=4000, path="operation.params.text")
        elif op_type == "set_timing":
            _known_keys(params, allowed={"in_ms", "out_ms"}, required={"in_ms", "out_ms"}, path="operation.params")
            in_ms = _int(params.get("in_ms"), path="operation.params.in_ms")
            end_limit = composition.duration_ms if composition is not None else 3_600_000
            out_ms = _int(params.get("out_ms"), path="operation.params.out_ms", minimum=1, maximum=end_limit)
            if out_ms <= in_ms:
                raise MotionAIContractError("operation timing end must be after start")
        elif op_type == "set_transform":
            _known_keys(params, allowed={"property", "value"}, required={"property", "value"}, path="operation.params")
            prop = str(params.get("property") or "")
            if prop not in TRANSFORM_PROPERTIES:
                raise MotionAIContractError(f"unsupported transform property: {prop}")
        elif op_type == "set_behavior":
            _known_keys(params, allowed={"behavior"}, required={"behavior"}, path="operation.params")
            behavior = _mapping(params.get("behavior"), "operation.params.behavior")
            allowed_behavior = {"id", "kind", "enabled", "start_ms", "end_ms", "params", "metadata"}
            unknown_behavior = sorted(str(key) for key in behavior if str(key) not in allowed_behavior)
            if unknown_behavior:
                raise MotionAIContractError(f"behavior contains unknown keys: {', '.join(unknown_behavior)}")
        elif op_type == "set_visibility":
            _known_keys(params, allowed={"visible"}, required={"visible"}, path="operation.params")
            if not isinstance(params.get("visible"), bool):
                raise MotionAIContractError("operation.params.visible must be boolean")
        op_ids.add(op_id)
        normalized_ops.append({
            "id": op_id,
            "type": op_type,
            "layer_id": layer_id,
            "params": dict(params),
            "reason": _bounded_text(row.get("reason"), limit=600, path="operation.reason"),
        })
    composition_id = _bounded_text(data.get("composition_id"), limit=160, path="patch.composition_id", required=True)
    base_revision = _int(data.get("base_revision"), path="patch.base_revision", minimum=1)
    if composition is not None:
        if composition_id != composition.id:
            raise MotionAIContractError("patch targets a different composition")
        if base_revision != composition.revision:
            raise MotionAIContractError("patch was created for a stale composition revision")
    return {
        "schema": MOTION_AI_PATCH_SCHEMA,
        "id": _bounded_text(data.get("id"), limit=160, path="patch.id", required=True),
        "composition_id": composition_id,
        "base_revision": base_revision,
        "prompt": _bounded_text(data.get("prompt"), limit=8000, path="patch.prompt"),
        "summary": _bounded_text(data.get("summary"), limit=1200, path="patch.summary", required=True),
        "operations": normalized_ops,
        "warnings": [_bounded_text(item, limit=1200, path="patch.warnings") for item in warnings[:64]],
        "metadata": dict(metadata),
    }


def build_deterministic_patch(
    composition: MotionComposition,
    prompt: str,
    layer_ids: Iterable[str],
) -> dict[str, Any]:
    selected = [item for item in composition.layers if item.id in {str(value) for value in layer_ids}]
    normalized = str(prompt or "").casefold()
    quoted = _quoted_text(prompt)
    operations: list[MotionAIPatchOperation] = []
    for layer in selected:
        if quoted and layer.layer_type == "text":
            operations.append(MotionAIPatchOperation(
                type="set_text", layer_id=layer.id, params={"text": quoted[0]}, reason="Quoted replacement text",
            ))
        if any(token in normalized for token in ("fade", "페이드")):
            operations.append(MotionAIPatchOperation(
                type="set_behavior",
                layer_id=layer.id,
                params={"behavior": MotionBehaviorRef(
                    kind="fade", start_ms=layer.in_ms, end_ms=min(layer.out_ms, layer.in_ms + 700),
                    params={"direction": "in"},
                ).to_dict()},
                reason="Requested fade motion",
            ))
        if any(token in normalized for token in ("bigger", "larger", "크게", "확대")):
            current = list(layer.transform.scale.default or [1.0, 1.0])
            operations.append(MotionAIPatchOperation(
                type="set_transform", layer_id=layer.id,
                params={"property": "scale", "value": [float(current[0]) * 1.15, float(current[1]) * 1.15]},
                reason="Requested larger scale",
            ))
    warnings = [] if operations else ["The safe fallback could not infer a scoped edit. Refine the prompt or select target layers."]
    return MotionAIPatch(
        composition_id=composition.id,
        base_revision=composition.revision,
        prompt=str(prompt or "").strip(),
        summary=f"Prepared {len(operations)} scoped Motion edit(s).",
        operations=operations,
        warnings=warnings,
        metadata={"planner": "deterministic_baseline", "target_layer_ids": [item.id for item in selected]},
    ).to_dict()


def generate_motion_ai_patch(
    composition: MotionComposition,
    prompt: str,
    layer_ids: Iterable[str],
    *,
    provider_id: str | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    targets = [item for item in composition.layers if item.id in {str(value) for value in layer_ids}]
    baseline = build_deterministic_patch(composition, prompt, [item.id for item in targets])
    result = generate_selected_provider_json(
        "tiger_studio_motion_patch",
        prompt,
        output_contract=MOTION_AI_PATCH_CONTRACT_V1,
        input_payload={
            "composition_id": composition.id,
            "base_revision": composition.revision,
            "target_layers": [item.to_dict() for item in targets],
        },
        safe_baseline=baseline,
        validate_payload=lambda value: validate_motion_ai_patch(value, composition=composition),
        provider_id="rule_based" if provider_id in {"local_layout", "rule_based"} else provider_id,
        env=env,
    )
    if not result.ok or result.payload is None:
        raise MotionAIContractError(result.reason or "Motion AI patch planning failed")
    payload = dict(result.payload)
    metadata = dict(payload.get("metadata") or {})
    provider_data = result.to_dict()
    provider_data.pop("payload", None)
    metadata["provider_contract"] = provider_data
    payload["metadata"] = metadata
    if result.fallback_used and result.reason:
        payload["warnings"] = list(dict.fromkeys([result.reason, *payload.get("warnings", [])]))
    return validate_motion_ai_patch(payload, composition=composition)


def apply_motion_ai_patch(composition: MotionComposition, patch: Mapping[str, Any]) -> MotionComposition:
    normalized = validate_motion_ai_patch(patch, composition=composition)
    candidate = MotionComposition.from_dict(composition.to_dict())
    by_id = {item.id: item for item in candidate.layers}
    for operation in normalized["operations"]:
        layer = by_id[operation["layer_id"]]
        params = operation["params"]
        op_type = operation["type"]
        if op_type == "set_text":
            if layer.layer_type != "text":
                raise MotionAIContractError(f"set_text requires a text layer: {layer.id}")
            layer.source.params = {**layer.source.params, "text": str(params["text"])}
        elif op_type == "set_timing":
            layer.in_ms = int(params["in_ms"])
            layer.out_ms = int(params["out_ms"])
        elif op_type == "set_transform":
            prop = getattr(layer.transform, str(params["property"]))
            prop.default = params["value"]
        elif op_type == "set_behavior":
            layer.behaviors = [MotionBehaviorRef.from_dict(params["behavior"])]
        elif op_type == "set_visibility":
            layer.visible = bool(params["visible"])
    if normalized["operations"]:
        candidate.revision += 1
    report = validate_composition(candidate)
    if not report.ok:
        raise MotionAIContractError(report.issues[0].message)
    return candidate


def motion_ai_provider_status() -> dict[str, Any]:
    snapshot = provider_snapshot()
    return {
        "selected_provider": snapshot["selected_provider"],
        "effective_generation_provider": snapshot["effective_generation_provider"],
        "fallback_reason": snapshot["fallback_reason"],
        "user_state": snapshot["user_state"],
        "contract": {
            "provider_mutates_project": False,
            "review_before_apply": True,
            "generation_schema": MOTION_AI_GENERATION_SCHEMA,
            "patch_schema": MOTION_AI_PATCH_SCHEMA,
        },
    }


__all__ = [
    "MOTION_AI_GENERATION_CONTRACT_V1",
    "MOTION_AI_GENERATION_SCHEMA",
    "MOTION_AI_PATCH_CONTRACT_V1",
    "MOTION_AI_PATCH_SCHEMA",
    "MotionAIContractError",
    "MotionAIGenerationPlan",
    "MotionAIPatch",
    "MotionAIPatchOperation",
    "MotionCreativeBrief",
    "MotionStoryboardBeat",
    "apply_motion_ai_patch",
    "build_deterministic_generation_plan",
    "build_deterministic_patch",
    "compile_generation_plan",
    "generate_motion_ai_patch",
    "generate_motion_ai_proposal",
    "motion_ai_provider_status",
    "validate_motion_ai_patch",
    "validate_motion_generation_plan",
]
