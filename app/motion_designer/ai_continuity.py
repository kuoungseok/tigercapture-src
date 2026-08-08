"""Conversation history, continuity checks, and provenance for Motion AI."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .schema import MotionComposition, new_motion_id


CONTINUITY_SCHEMA = "tigerstudio.motion.ai.continuity.v1"
PROVENANCE_SCHEMA = "tigerstudio.motion.ai.provenance.v1"


def validate_motion_continuity(
    before: MotionComposition,
    after: MotionComposition,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    before_by_id = {item.id: item for item in before.layers}
    after_by_id = {item.id: item for item in after.layers}
    for layer_id, original in before_by_id.items():
        current = after_by_id.get(layer_id)
        if current is None:
            issues.append({
                "code": "existing_layer_removed",
                "layer_id": layer_id,
                "message": "An existing layer disappeared during an additive or scoped AI edit.",
            })
            continue
        if original.source.uri and current.source.uri != original.source.uri:
            issues.append({
                "code": "source_identity_changed",
                "layer_id": layer_id,
                "message": "An existing layer source changed without a replace-source operation.",
            })
        original_reference = str(original.metadata.get("ai_reference_id") or "")
        current_reference = str(current.metadata.get("ai_reference_id") or "")
        if original_reference and current_reference != original_reference:
            issues.append({
                "code": "reference_identity_changed",
                "layer_id": layer_id,
                "message": "An existing AI reference identity changed.",
            })
    valid_ids = set(after_by_id)
    for layer in after.layers:
        if layer.parent_id and layer.parent_id not in valid_ids:
            issues.append({
                "code": "missing_parent",
                "layer_id": layer.id,
                "message": f"Layer parent does not exist: {layer.parent_id}",
            })
        if layer.out_ms <= layer.in_ms:
            issues.append({
                "code": "invalid_timing",
                "layer_id": layer.id,
                "message": "Layer end must remain after its start.",
            })
    return {
        "schema": CONTINUITY_SCHEMA,
        "ok": not issues,
        "base_revision": int(before.revision),
        "result_revision": int(after.revision),
        "preserved_layer_count": len(set(before_by_id) & set(after_by_id)),
        "added_layer_count": len(set(after_by_id) - set(before_by_id)),
        "issues": issues,
    }


def record_motion_ai_event(
    composition: MotionComposition,
    *,
    event_type: str,
    prompt: str,
    provider: str,
    base_revision: int,
    reference_provenance: Iterable[Mapping[str, Any]] = (),
    details: Mapping[str, Any] | None = None,
    continuity: Mapping[str, Any] | None = None,
) -> None:
    metadata = composition.metadata
    history = [
        dict(item)
        for item in metadata.get("motion_ai_history", [])
        if isinstance(item, Mapping)
    ]
    event = {
        "id": new_motion_id("ai_event"),
        "event_type": str(event_type),
        "prompt": str(prompt or ""),
        "provider": str(provider or ""),
        "base_revision": int(base_revision),
        "result_revision": int(composition.revision),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "details": dict(details or {}),
    }
    if continuity is not None:
        event["continuity"] = dict(continuity)
    history.append(event)
    metadata["motion_ai_history"] = history[-32:]

    provenance = [
        dict(item)
        for item in metadata.get("motion_ai_provenance", [])
        if isinstance(item, Mapping)
    ]
    known = {
        str(
            (item.get("provenance") or {}).get("fingerprint")
            if isinstance(item.get("provenance"), Mapping)
            else ""
        )
        for item in provenance
    }
    for item in reference_provenance:
        row = dict(item)
        payload = row.get("provenance")
        fingerprint = (
            str(payload.get("fingerprint") or "")
            if isinstance(payload, Mapping)
            else ""
        )
        if fingerprint and fingerprint in known:
            continue
        provenance.append(row)
        if fingerprint:
            known.add(fingerprint)
    metadata["motion_ai_provenance"] = provenance[-128:]
    metadata["motion_ai_provenance_schema"] = PROVENANCE_SCHEMA


def motion_ai_audit_report(composition: MotionComposition) -> dict[str, Any]:
    return {
        "schema": PROVENANCE_SCHEMA,
        "composition_id": composition.id,
        "revision": int(composition.revision),
        "history": [
            dict(item)
            for item in composition.metadata.get("motion_ai_history", [])
            if isinstance(item, Mapping)
        ],
        "assets": [
            dict(item)
            for item in composition.metadata.get("motion_ai_provenance", [])
            if isinstance(item, Mapping)
        ],
        "c2pa_signed": False,
        "note": (
            "Tiger Studio records editable local provenance. Cryptographic C2PA "
            "signing requires a configured signing identity and is not claimed."
        ),
    }


__all__ = [
    "CONTINUITY_SCHEMA",
    "PROVENANCE_SCHEMA",
    "motion_ai_audit_report",
    "record_motion_ai_event",
    "validate_motion_continuity",
]
