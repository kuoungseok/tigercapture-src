"""Validated AI edit-plan contracts for transcript-driven editing.

This module is intentionally deterministic and dependency-light. AI providers
may propose JSON, but only validated EditPlan data leaves this boundary.
"""
from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence as SequenceABC
from dataclasses import dataclass, field
import json
from typing import Any, Mapping, Sequence


EDIT_PLAN_SCHEMA_VERSION = 1

AI_EDIT_PLAN_SCHEMA_V1 = {
    "schema_version": EDIT_PLAN_SCHEMA_VERSION,
    "name": "tigercapture.ai_edit_plan",
    "plan_keys": [
        "schema_version",
        "provider",
        "id",
        "intent",
        "summary",
        "operations",
        "warnings",
        "requires_review",
        "review_cards",
        "quality_score",
        "metadata",
    ],
    "operation_keys": [
        "id",
        "type",
        "target",
        "start_ms",
        "end_ms",
        "text",
        "style_preset_id",
        "params",
        "metadata",
        "reason",
        "confidence",
        "quality_score",
        "source",
    ],
}

ALLOWED_OPERATION_TYPES = frozenset(
    {
        "delete_time_range",
        "keep_time_range",
        "ripple_cut_text_range",
        "remove_silence",
        "remove_filler_words",
        "create_subtitles",
        "restyle_subtitles",
        "add_marker",
        "add_chapter_markers",
        "add_auto_zoom",
        "add_callout",
        "apply_preset",
        "create_short_candidate",
        "set_reframe",
        "add_render_queue_job",
        "add_live2d_dialogue",
        "add_spine_dialogue",
        "create_publish_package",
        "replace_audio_range",
    }
)

FORBIDDEN_EXECUTION_KEYS = frozenset(
    {
        "code",
        "command",
        "commands",
        "exec",
        "eval",
        "function",
        "mutation",
        "project_mutation",
        "python",
        "script",
        "shell",
        "subprocess",
    }
)

PLAN_KEYS = frozenset(
    {
        "schema_version",
        "provider",
        "id",
        "intent",
        "summary",
        "operations",
        "warnings",
        "requires_review",
        "review_cards",
        "quality_score",
        "metadata",
    }
)

OPERATION_KEYS = frozenset(
    {
        "id",
        "type",
        "target",
        "start_ms",
        "end_ms",
        "text",
        "style_preset_id",
        "params",
        "metadata",
        "reason",
        "confidence",
        "quality_score",
        "source",
    }
)


class EditPlanValidationError(ValueError):
    """Raised when a proposed edit plan is not safe, known JSON data."""


TIME_RANGE_OPERATION_TYPES = frozenset(
    {"delete_time_range", "keep_time_range", "ripple_cut_text_range", "create_short_candidate"}
)


def _coerce_ms(value: Any, *, field_name: str) -> int:
    try:
        result = int(round(float(value)))
    except Exception as exc:
        raise EditPlanValidationError(f"{field_name} must be a number of milliseconds") from exc
    if result < 0:
        raise EditPlanValidationError(f"{field_name} must be >= 0")
    return result


def _stable_json_value(value: Any) -> Any:
    if isinstance(value, MappingABC):
        return {str(key): _stable_json_value(value[key]) for key in sorted(value, key=lambda item: str(item))}
    if isinstance(value, (list, tuple)):
        return [_stable_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise EditPlanValidationError(f"non JSON-serializable value: {type(value).__name__}")


def _reject_forbidden_keys(value: Any, *, path: str = "payload") -> None:
    if isinstance(value, MappingABC):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key.casefold() in FORBIDDEN_EXECUTION_KEYS:
                raise EditPlanValidationError(f"{path}.{key} is not allowed in AI edit plans")
            _reject_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for idx, child in enumerate(value):
            _reject_forbidden_keys(child, path=f"{path}[{idx}]")


def stable_json_dumps(value: Any) -> str:
    """Serialize JSON deterministically for QA snapshots and plan hashing."""
    return json.dumps(_stable_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_primitive_string(value: Any) -> bool:
    return isinstance(value, str)


def _validate_subtitle_rows(value: Any) -> None:
    if not isinstance(value, SequenceABC) or isinstance(value, (str, bytes)):
        raise EditPlanValidationError("create_subtitles params.rows must be a list")
    for idx, row in enumerate(value):
        if not isinstance(row, MappingABC):
            raise EditPlanValidationError(f"create_subtitles params.rows[{idx}] must be an object")
        for key in ("start_ms", "end_ms", "text"):
            if key not in row:
                raise EditPlanValidationError(f"create_subtitles params.rows[{idx}] missing {key}")
        start_ms = _coerce_ms(row.get("start_ms"), field_name=f"params.rows[{idx}].start_ms")
        end_ms = _coerce_ms(row.get("end_ms"), field_name=f"params.rows[{idx}].end_ms")
        if end_ms <= start_ms:
            raise EditPlanValidationError(f"create_subtitles params.rows[{idx}] end_ms must be greater than start_ms")
        if not str(row.get("text") or "").strip():
            raise EditPlanValidationError(f"create_subtitles params.rows[{idx}] text is required")


def _validate_operation_contract(operation: "EditOperation") -> None:
    if operation.type in TIME_RANGE_OPERATION_TYPES:
        if operation.start_ms is None or operation.end_ms is None:
            raise EditPlanValidationError(f"{operation.type} requires start_ms and end_ms")
    if operation.type == "create_subtitles":
        if "rows" in operation.params:
            _validate_subtitle_rows(operation.params.get("rows"))
    if operation.type == "add_render_queue_job":
        has_render_target = operation.target == "render_queue"
        has_variant_format = bool(operation.params.get("variant")) and bool(operation.params.get("format"))
        if not has_render_target and not has_variant_format:
            raise EditPlanValidationError("add_render_queue_job requires target render_queue or params variant/format")
    if operation.type == "add_callout":
        has_text = bool(str(operation.text or operation.params.get("label") or operation.params.get("body") or "").strip())
        if not has_text:
            raise EditPlanValidationError("add_callout requires text, params.label, or params.body")
        if operation.target in {"selected_video", "timeline", "video_track", "active_video_track"}:
            if operation.start_ms is None or operation.end_ms is None:
                raise EditPlanValidationError("timeline add_callout requires start_ms and end_ms")
    if operation.type in {"add_live2d_dialogue", "add_spine_dialogue"}:
        dialogue = operation.params.get("dialogue")
        if not str(operation.text or dialogue or "").strip():
            raise EditPlanValidationError(f"{operation.type} requires text or params.dialogue")
    if operation.type == "replace_audio_range":
        if operation.start_ms is None or operation.end_ms is None:
            raise EditPlanValidationError("replace_audio_range requires start_ms and end_ms")
        replacement_text = str(operation.text or operation.params.get("replacement_text") or "").strip()
        generated_asset = str(operation.params.get("generated_asset_id") or "").strip()
        if not replacement_text and not generated_asset:
            raise EditPlanValidationError("replace_audio_range requires text/replacement_text or generated_asset_id")
        if not bool(operation.params.get("preview_required", False)):
            raise EditPlanValidationError("replace_audio_range requires preview_required=true")


@dataclass(frozen=True)
class TranscriptWord:
    text: str
    start_ms: int
    end_ms: int
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not str(self.text).strip():
            raise EditPlanValidationError("transcript word text is required")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise EditPlanValidationError("transcript word time range must be positive")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise EditPlanValidationError("transcript word confidence must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "text": self.text,
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
        }
        if self.confidence is not None:
            data["confidence"] = float(self.confidence)
        return data


@dataclass(frozen=True)
class TranscriptSegment:
    id: str
    start_ms: int
    end_ms: int
    text: str
    speaker: str | None = None
    words: tuple[TranscriptWord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise EditPlanValidationError("transcript segment id is required")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise EditPlanValidationError(f"transcript segment {self.id} has invalid time range")
        if not str(self.text).strip():
            raise EditPlanValidationError(f"transcript segment {self.id} text is required")
        for word in self.words:
            if word.start_ms < self.start_ms or word.end_ms > self.end_ms:
                raise EditPlanValidationError(f"word in segment {self.id} falls outside segment range")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
            "text": self.text,
        }
        if self.speaker:
            data["speaker"] = self.speaker
        if self.words:
            data["words"] = [word.to_dict() for word in self.words]
        return data


@dataclass(frozen=True)
class TranscriptDocument:
    id: str
    source_media_id: str
    language: str = "und"
    created_by: str = "manual"
    segments: tuple[TranscriptSegment, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise EditPlanValidationError("transcript id is required")
        if not str(self.source_media_id).strip():
            raise EditPlanValidationError("source media id is required")
        seen: set[str] = set()
        for segment in self.segments:
            if segment.id in seen:
                raise EditPlanValidationError(f"duplicate transcript segment id: {segment.id}")
            seen.add(segment.id)
        _stable_json_value(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "id": self.id,
            "source_media_id": self.source_media_id,
            "language": self.language,
            "created_by": self.created_by,
            "segments": [segment.to_dict() for segment in self.segments],
        }
        if self.metadata:
            data["metadata"] = _stable_json_value(self.metadata)
        return data


@dataclass(frozen=True)
class EditOperation:
    type: str
    id: str = ""
    target: str = "selected_video_linked_audio"
    start_ms: int | None = None
    end_ms: int | None = None
    text: str | None = None
    style_preset_id: str | None = None
    params: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""
    confidence: float | None = None
    quality_score: int | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if self.type not in ALLOWED_OPERATION_TYPES:
            raise EditPlanValidationError(f"operation type is not allowed: {self.type}")
        if self.start_ms is not None and self.start_ms < 0:
            raise EditPlanValidationError("operation start_ms must be >= 0")
        if self.end_ms is not None and self.end_ms < 0:
            raise EditPlanValidationError("operation end_ms must be >= 0")
        if self.start_ms is not None and self.end_ms is not None and self.end_ms <= self.start_ms:
            raise EditPlanValidationError("operation end_ms must be greater than start_ms")
        if self.confidence is not None and not 0.0 <= float(self.confidence) <= 1.0:
            raise EditPlanValidationError("operation confidence must be in [0, 1]")
        if self.quality_score is not None and not 0 <= int(self.quality_score) <= 100:
            raise EditPlanValidationError("operation quality_score must be in [0, 100]")
        _reject_forbidden_keys(self.params, path="operation.params")
        _reject_forbidden_keys(self.metadata, path="operation.metadata")
        _stable_json_value(self.params)
        _stable_json_value(self.metadata)
        _validate_operation_contract(self)

    def with_id(self, operation_id: str) -> "EditOperation":
        return EditOperation(
            id=operation_id,
            type=self.type,
            target=self.target,
            start_ms=self.start_ms,
            end_ms=self.end_ms,
            text=self.text,
            style_preset_id=self.style_preset_id,
            params=dict(self.params),
            metadata=dict(self.metadata),
            reason=self.reason,
            confidence=self.confidence,
            quality_score=self.quality_score,
            source=self.source,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "target": self.target,
        }
        if self.start_ms is not None:
            data["start_ms"] = int(self.start_ms)
        if self.end_ms is not None:
            data["end_ms"] = int(self.end_ms)
        if self.text is not None:
            data["text"] = self.text
        if self.style_preset_id is not None:
            data["style_preset_id"] = self.style_preset_id
        if self.params:
            data["params"] = _stable_json_value(self.params)
        if self.metadata:
            data["metadata"] = _stable_json_value(self.metadata)
        if self.reason:
            data["reason"] = self.reason
        if self.confidence is not None:
            data["confidence"] = float(self.confidence)
        if self.quality_score is not None:
            data["quality_score"] = int(self.quality_score)
        if self.source:
            data["source"] = self.source
        return data


@dataclass(frozen=True)
class ReviewCard:
    id: str
    title: str
    operation_ids: tuple[str, ...] = field(default_factory=tuple)
    quality_score: int = 0
    reason: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise EditPlanValidationError("review card id is required")
        if not str(self.title).strip():
            raise EditPlanValidationError("review card title is required")
        if not 0 <= int(self.quality_score) <= 100:
            raise EditPlanValidationError("review card quality_score must be in [0, 100]")
        _reject_forbidden_keys(self.metadata, path="review_card.metadata")
        _stable_json_value(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "operation_ids": list(self.operation_ids),
            "quality_score": int(self.quality_score),
        }
        if self.reason:
            data["reason"] = self.reason
        if self.metadata:
            data["metadata"] = _stable_json_value(self.metadata)
        return data


@dataclass(frozen=True)
class EditPlan:
    id: str
    intent: str
    summary: str
    operations: tuple[EditOperation, ...]
    warnings: tuple[str, ...] = field(default_factory=tuple)
    requires_review: bool = True
    review_cards: tuple[ReviewCard, ...] = field(default_factory=tuple)
    quality_score: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = EDIT_PLAN_SCHEMA_VERSION
    provider: str = "rule_based"

    def __post_init__(self) -> None:
        if int(self.schema_version) != EDIT_PLAN_SCHEMA_VERSION:
            raise EditPlanValidationError(
                f"unsupported edit plan schema_version: {self.schema_version}"
            )
        if not str(self.id).strip():
            raise EditPlanValidationError("edit plan id is required")
        if not str(self.intent).strip():
            raise EditPlanValidationError("edit plan intent is required")
        if not str(self.summary).strip():
            raise EditPlanValidationError("edit plan summary is required")
        if not 0 <= int(self.quality_score) <= 100:
            raise EditPlanValidationError("plan quality_score must be in [0, 100]")
        seen: set[str] = set()
        for operation in self.operations:
            if not operation.id:
                raise EditPlanValidationError("operation id is required after normalization")
            if operation.id in seen:
                raise EditPlanValidationError(f"duplicate operation id: {operation.id}")
            seen.add(operation.id)
        card_operation_ids = {op_id for card in self.review_cards for op_id in card.operation_ids}
        missing = card_operation_ids - seen
        if missing:
            raise EditPlanValidationError(f"review card references missing operations: {sorted(missing)}")
        _reject_forbidden_keys(self.metadata, path="plan.metadata")
        _stable_json_value(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "schema_version": int(self.schema_version),
            "provider": str(self.provider or "rule_based"),
            "id": self.id,
            "intent": self.intent,
            "summary": self.summary,
            "operations": [operation.to_dict() for operation in self.operations],
            "warnings": list(self.warnings),
            "requires_review": bool(self.requires_review),
            "quality_score": int(self.quality_score),
        }
        if self.review_cards:
            data["review_cards"] = [card.to_dict() for card in self.review_cards]
        if self.metadata:
            data["metadata"] = _stable_json_value(self.metadata)
        return data

    def to_stable_json(self) -> str:
        return stable_json_dumps(self.to_dict())


def make_operation_id(index: int, operation_type: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in operation_type.casefold()).strip("_")
    return f"op_{index:03d}_{slug or 'operation'}"


def normalize_operations(operations: Sequence[EditOperation]) -> tuple[EditOperation, ...]:
    normalized: list[EditOperation] = []
    seen: set[str] = set()
    for idx, operation in enumerate(operations, start=1):
        op_id = str(operation.id or make_operation_id(idx, operation.type)).strip()
        if op_id in seen:
            raise EditPlanValidationError(f"duplicate operation id: {op_id}")
        seen.add(op_id)
        normalized.append(operation.with_id(op_id))
    return tuple(normalized)


def build_edit_plan(
    *,
    plan_id: str,
    intent: str,
    summary: str,
    operations: Sequence[EditOperation],
    warnings: Sequence[str] | None = None,
    requires_review: bool = True,
    review_cards: Sequence[ReviewCard] | None = None,
    quality_score: int = 0,
    metadata: Mapping[str, Any] | None = None,
    provider: str = "rule_based",
) -> EditPlan:
    return EditPlan(
        id=plan_id,
        intent=intent,
        summary=summary,
        operations=normalize_operations(operations),
        warnings=tuple(str(item) for item in (warnings or ())),
        requires_review=requires_review,
        review_cards=tuple(review_cards or ()),
        quality_score=quality_score,
        metadata=dict(metadata or {}),
        provider=provider,
    )


def operation_from_dict(payload: Mapping[str, Any]) -> EditOperation:
    unknown = set(str(key) for key in payload) - OPERATION_KEYS
    if unknown:
        raise EditPlanValidationError(f"unknown operation keys: {sorted(unknown)}")
    _reject_forbidden_keys(payload, path="operation")
    op_type = str(payload.get("type") or "").strip()
    start_ms = None if payload.get("start_ms") is None else _coerce_ms(payload.get("start_ms"), field_name="start_ms")
    end_ms = None if payload.get("end_ms") is None else _coerce_ms(payload.get("end_ms"), field_name="end_ms")
    confidence = payload.get("confidence")
    quality_score = payload.get("quality_score")
    return EditOperation(
        id=str(payload.get("id") or "").strip(),
        type=op_type,
        target=str(payload.get("target") or "selected_video_linked_audio"),
        start_ms=start_ms,
        end_ms=end_ms,
        text=None if payload.get("text") is None else str(payload.get("text")),
        style_preset_id=None if payload.get("style_preset_id") is None else str(payload.get("style_preset_id")),
        params=dict(payload.get("params") or {}),
        metadata=dict(payload.get("metadata") or {}),
        reason=str(payload.get("reason") or ""),
        confidence=None if confidence is None else float(confidence),
        quality_score=None if quality_score is None else int(quality_score),
        source=str(payload.get("source") or ""),
    )


def review_card_from_dict(payload: Mapping[str, Any]) -> ReviewCard:
    _reject_forbidden_keys(payload, path="review_card")
    operation_ids = payload.get("operation_ids") or ()
    if not isinstance(operation_ids, SequenceABC) or isinstance(operation_ids, (str, bytes)):
        raise EditPlanValidationError("review_card.operation_ids must be a list")
    if any(not _is_primitive_string(item) for item in operation_ids):
        raise EditPlanValidationError("review_card.operation_ids must contain strings only")
    return ReviewCard(
        id=str(payload.get("id") or "").strip(),
        title=str(payload.get("title") or "").strip(),
        operation_ids=tuple(operation_ids),
        quality_score=int(payload.get("quality_score") or 0),
        reason=str(payload.get("reason") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )


def edit_plan_from_dict(payload: Mapping[str, Any]) -> EditPlan:
    unknown = set(str(key) for key in payload) - PLAN_KEYS
    if unknown:
        raise EditPlanValidationError(f"unknown plan keys: {sorted(unknown)}")
    _reject_forbidden_keys(payload, path="plan")
    schema_version = int(payload.get("schema_version") or EDIT_PLAN_SCHEMA_VERSION)
    if schema_version != EDIT_PLAN_SCHEMA_VERSION:
        raise EditPlanValidationError(f"unsupported edit plan schema_version: {schema_version}")
    operations_raw = payload.get("operations")
    if not isinstance(operations_raw, SequenceABC) or isinstance(operations_raw, (str, bytes)):
        raise EditPlanValidationError("plan.operations must be a list")
    operations = [operation_from_dict(item) for item in operations_raw if isinstance(item, MappingABC)]
    if len(operations) != len(operations_raw):
        raise EditPlanValidationError("plan.operations must contain objects only")
    review_cards_raw = payload.get("review_cards") or []
    if not isinstance(review_cards_raw, SequenceABC) or isinstance(review_cards_raw, (str, bytes)):
        raise EditPlanValidationError("plan.review_cards must be a list")
    if any(not isinstance(item, MappingABC) for item in review_cards_raw):
        raise EditPlanValidationError("plan.review_cards must contain objects only")
    warnings_raw = payload.get("warnings", [])
    if not isinstance(warnings_raw, SequenceABC) or isinstance(warnings_raw, (str, bytes)):
        raise EditPlanValidationError("plan.warnings must be a list")
    if any(not _is_primitive_string(item) for item in warnings_raw):
        raise EditPlanValidationError("plan.warnings must contain strings only")
    return build_edit_plan(
        plan_id=str(payload.get("id") or "").strip(),
        intent=str(payload.get("intent") or "").strip(),
        summary=str(payload.get("summary") or "").strip(),
        operations=operations,
        warnings=list(warnings_raw),
        requires_review=bool(payload.get("requires_review", True)),
        review_cards=[review_card_from_dict(item) for item in review_cards_raw],
        quality_score=int(payload.get("quality_score") or 0),
        metadata=dict(payload.get("metadata") or {}),
        provider=str(payload.get("provider") or "rule_based"),
    )


def validate_edit_plan_json(text: str) -> EditPlan:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EditPlanValidationError(f"invalid EditPlan JSON: {exc}") from exc
    if not isinstance(payload, MappingABC):
        raise EditPlanValidationError("EditPlan JSON must be an object")
    return edit_plan_from_dict(payload)
