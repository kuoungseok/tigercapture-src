"""Reviewable sentence-level AI voice replacement contracts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.ai_edit_plan import EditOperation, EditPlan, ReviewCard, TranscriptDocument, build_edit_plan
from app.transcript_document import segment_by_id


@dataclass(frozen=True)
class VoiceConsentGrant:
    id: str
    subject_label: str
    rights_scope: str
    provider_id: str
    granted: bool = False
    audit_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "subject_label": str(self.subject_label),
            "rights_scope": str(self.rights_scope),
            "provider_id": str(self.provider_id),
            "granted": bool(self.granted),
            "audit_note": str(self.audit_note),
        }


def voice_clone_consent_contract(consent: VoiceConsentGrant | Mapping[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(consent, VoiceConsentGrant):
        grant = consent
    else:
        raw = dict(consent or {})
        grant = VoiceConsentGrant(
            id=str(raw.get("id") or "consent_missing"),
            subject_label=str(raw.get("subject_label") or ""),
            rights_scope=str(raw.get("rights_scope") or ""),
            provider_id=str(raw.get("provider_id") or "custom_voice_slot"),
            granted=bool(raw.get("granted", False)),
            audit_note=str(raw.get("audit_note") or ""),
        )
    missing = []
    if not grant.subject_label:
        missing.append("subject_label")
    if not grant.rights_scope:
        missing.append("rights_scope")
    if not grant.audit_note:
        missing.append("audit_note")
    return {
        "ok": bool(grant.granted and not missing),
        "requires_explicit_consent": True,
        "allows_custom_voice_generation": bool(grant.granted and not missing),
        "missing": missing,
        "consent": grant.to_dict(),
    }


def sentence_voice_replacement_operation(
    document: TranscriptDocument,
    *,
    segment_id: str,
    replacement_text: str,
    provider_id: str = "system_tts_slot",
    generated_asset_id: str = "",
) -> EditOperation:
    segment = segment_by_id(document, segment_id)
    text = str(replacement_text or "").strip()
    if not text:
        raise ValueError("replacement_text is required")
    return EditOperation(
        id=f"replace_voice_{segment.id}",
        type="replace_audio_range",
        target="linked_dialogue_audio",
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        text=text,
        params={
            "source_transcript_id": document.id,
            "segment_id": segment.id,
            "original_text": segment.text,
            "replacement_text": text,
            "voice_provider_id": str(provider_id),
            "generated_asset_id": str(generated_asset_id or f"pending_tts_{segment.id}"),
            "tts_mode": "reviewed_sentence_replacement",
            "preview_required": True,
            "fallback": "adr_recording_cue",
        },
        metadata={
            "source_media_id": document.source_media_id,
            "language": document.language,
            "speaker": segment.speaker or "",
        },
        reason="Regenerate only the edited sentence as a reviewed dialogue replacement.",
        confidence=0.78,
        quality_score=80,
        source="ai_voice_replacement",
    )


def build_sentence_voice_replacement_plan(
    document: TranscriptDocument,
    *,
    segment_id: str,
    replacement_text: str,
    provider_id: str = "system_tts_slot",
    generated_asset_id: str = "",
) -> EditPlan:
    operation = sentence_voice_replacement_operation(
        document,
        segment_id=segment_id,
        replacement_text=replacement_text,
        provider_id=provider_id,
        generated_asset_id=generated_asset_id,
    )
    card = ReviewCard(
        id=f"review_{operation.id}",
        title="Review regenerated sentence audio",
        operation_ids=(operation.id,),
        quality_score=80,
        reason="Compare the generated sentence against surrounding dialogue before replacing timeline audio.",
        metadata={
            "preview_required": True,
            "voice_provider_id": provider_id,
            "fallback": "adr_recording_cue",
        },
    )
    return build_edit_plan(
        plan_id=f"voice_replace_{segment_id}",
        intent="sentence_voice_replacement",
        summary="Replace one edited transcript sentence with reviewed generated or ADR audio.",
        operations=[operation],
        warnings=(
            "Synthetic or cloned voices require explicit rights review before final export.",
            "If no local TTS provider is configured, create an ADR cue instead of mutating audio.",
        ),
        requires_review=True,
        review_cards=[card],
        quality_score=80,
        metadata={
            "source_transcript_id": document.id,
            "voice_provider_id": provider_id,
            "review_required": True,
            "custom_voice_requires_consent": True,
        },
        provider="ai_voice_replacement",
    )


def ai_voice_replacement_readiness_report(document: TranscriptDocument | None = None) -> dict[str, Any]:
    if document is None:
        from app.ai_edit_plan import TranscriptSegment

        document = TranscriptDocument(
            id="voice_qa_doc",
            source_media_id="voice_qa_clip",
            language="ko-en",
            created_by="ai_voice_replacement_qa",
            segments=(
                TranscriptSegment(
                    id="seg_001",
                    start_ms=1200,
                    end_ms=2800,
                    text="Original line for replacement.",
                    speaker="speaker_1",
                ),
            ),
        )
    plan = build_sentence_voice_replacement_plan(
        document,
        segment_id=document.segments[0].id,
        replacement_text="Updated line for replacement.",
    )
    consent_missing = voice_clone_consent_contract()
    consent_granted = voice_clone_consent_contract(
        VoiceConsentGrant(
            id="qa_consent",
            subject_label="QA narrator",
            rights_scope="local test sentence replacement",
            provider_id="custom_voice_slot",
            granted=True,
            audit_note="Synthetic QA grant used to verify consent gating.",
        )
    )
    checks = {
        "sentence_regenerate_plan": bool(plan.operations and plan.operations[0].type == "replace_audio_range"),
        "review_required": bool(plan.requires_review and plan.review_cards),
        "adr_fallback": plan.operations[0].params.get("fallback") == "adr_recording_cue",
        "consent_blocks_custom_voice_without_grant": not bool(consent_missing.get("allows_custom_voice_generation")),
        "consent_allows_custom_voice_with_grant": bool(consent_granted.get("allows_custom_voice_generation")),
    }
    return {
        "kind": "ai_voice_replacement_qa",
        "ok": all(checks.values()),
        "ai_voice_replacement_contract_ready": all(checks.values()),
        "checks": checks,
        "plan": plan.to_dict(),
        "consent_missing": consent_missing,
        "consent_granted": consent_granted,
    }


__all__ = [
    "VoiceConsentGrant",
    "ai_voice_replacement_readiness_report",
    "build_sentence_voice_replacement_plan",
    "sentence_voice_replacement_operation",
    "voice_clone_consent_contract",
]
