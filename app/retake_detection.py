"""Transcript-level retake and mistake cleanup planners.

The detector is deliberately deterministic. It does not claim ASR magic; it
turns obvious repeated takes, restarts, and mistake phrases into reviewable cut
operations that the existing AI Script apply path can materialize later.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any

from app.ai_edit_plan import EditOperation, EditPlan, ReviewCard, TranscriptDocument, TranscriptSegment, build_edit_plan


RESTART_PHRASES = (
    "다시",
    "아니",
    "잠깐",
    "미안",
    "죄송",
    "실수",
    "틀렸",
    "처음부터",
    "scratch that",
    "try again",
    "again",
    "sorry",
    "my bad",
    "no wait",
    "wait",
    "restart",
    "redo",
    "take two",
)

_WORD_RE = re.compile(r"[\w가-힣]+", re.UNICODE)


@dataclass(frozen=True)
class CleanupCandidate:
    id: str
    kind: str
    segment_id: str
    start_ms: int
    end_ms: int
    text: str
    keep_segment_id: str = ""
    confidence: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "segment_id": self.segment_id,
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
            "text": self.text,
            "keep_segment_id": self.keep_segment_id,
            "confidence": float(self.confidence),
            "reason": self.reason,
        }


def _tokens(text: str) -> list[str]:
    return [match.group(0).casefold() for match in _WORD_RE.finditer(str(text or ""))]


def _normalized_text(text: str) -> str:
    tokens = _tokens(text)
    filtered = [token for token in tokens if token not in {"um", "uh", "er", "ah", "음", "어", "그"}]
    return " ".join(filtered)


def _similarity(left: str, right: str) -> float:
    a = _normalized_text(left)
    b = _normalized_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(a=a, b=b).ratio()


def _segment_quality(segment: TranscriptSegment) -> float:
    if not segment.words:
        return max(0.1, min(1.0, len(_tokens(segment.text)) / 12.0))
    confidences = [float(word.confidence) for word in segment.words if word.confidence is not None]
    if confidences:
        return sum(confidences) / len(confidences)
    return max(0.1, min(1.0, len(segment.words) / 12.0))


def _best_take(segments: Iterable[TranscriptSegment]) -> TranscriptSegment:
    return max(segments, key=lambda segment: (_segment_quality(segment), segment.end_ms, len(segment.text)))


def detect_retake_candidates(
    document: TranscriptDocument,
    *,
    similarity_threshold: float = 0.82,
    max_gap_ms: int = 20_000,
) -> list[CleanupCandidate]:
    """Detect repeated takes and mark non-best takes for reviewable removal."""
    segments = sorted(document.segments, key=lambda segment: (segment.start_ms, segment.end_ms))
    clusters: list[list[TranscriptSegment]] = []
    for segment in segments:
        if not _normalized_text(segment.text):
            continue
        matched = False
        for cluster in clusters:
            last = cluster[-1]
            if segment.start_ms - last.end_ms > max_gap_ms:
                continue
            if _similarity(cluster[0].text, segment.text) >= similarity_threshold:
                cluster.append(segment)
                matched = True
                break
        if not matched:
            clusters.append([segment])
    candidates: list[CleanupCandidate] = []
    for cluster_idx, cluster in enumerate(clusters, start=1):
        if len(cluster) < 2:
            continue
        keep = _best_take(cluster)
        for segment in cluster:
            if segment.id == keep.id:
                continue
            confidence = _similarity(segment.text, keep.text)
            candidates.append(
                CleanupCandidate(
                    id=f"retake_{cluster_idx:03d}_{segment.id}",
                    kind="retake",
                    segment_id=segment.id,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=segment.text,
                    keep_segment_id=keep.id,
                    confidence=max(0.0, min(1.0, confidence)),
                    reason=f"Similar to kept take {keep.id}.",
                )
            )
    return candidates


def _has_repeated_adjacent_phrase(tokens: list[str]) -> bool:
    if len(tokens) < 4:
        return False
    for size in (1, 2, 3):
        for idx in range(0, len(tokens) - size * 2 + 1):
            if tokens[idx: idx + size] == tokens[idx + size: idx + size * 2]:
                return True
    return False


def detect_mistake_candidates(document: TranscriptDocument) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    for segment in document.segments:
        text = str(segment.text or "")
        lowered = text.casefold()
        matched_phrase = next((phrase for phrase in RESTART_PHRASES if phrase.casefold() in lowered), "")
        tokens = _tokens(text)
        repeated = _has_repeated_adjacent_phrase(tokens)
        if not matched_phrase and not repeated:
            continue
        reason = f"Restart phrase: {matched_phrase}" if matched_phrase else "Repeated adjacent phrase"
        confidence = 0.78 if matched_phrase else 0.68
        candidates.append(
            CleanupCandidate(
                id=f"mistake_{segment.id}",
                kind="mistake",
                segment_id=segment.id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=text,
                confidence=confidence,
                reason=reason,
            )
        )
    return candidates


def _operations_from_candidates(candidates: list[CleanupCandidate], *, source: str) -> list[EditOperation]:
    return [
        EditOperation(
            id=f"op_{idx:03d}_{source}",
            type="delete_time_range",
            target="selected_video_linked_audio",
            start_ms=candidate.start_ms,
            end_ms=candidate.end_ms,
            text=candidate.text,
            params={
                "source_operation": source,
                "candidate": candidate.to_dict(),
                "segment_id": candidate.segment_id,
            },
            source=source,
            reason=candidate.reason,
            confidence=candidate.confidence,
            quality_score=int(round(100 * max(0.0, min(1.0, candidate.confidence)))),
        )
        for idx, candidate in enumerate(candidates, start=1)
    ]


def plan_remove_retakes(document: TranscriptDocument) -> EditPlan:
    candidates = detect_retake_candidates(document)
    operations = _operations_from_candidates(candidates, source="retake_detection")
    return build_edit_plan(
        plan_id="plan_remove_retakes",
        intent="remove_retakes",
        summary=f"Remove {len(operations)} repeated-take candidate(s) after review.",
        operations=operations,
        warnings=[] if operations else ["no_retake_candidates_detected"],
        review_cards=[
            ReviewCard(
                id="card_retakes",
                title="Retakes",
                operation_ids=tuple(operation.id for operation in operations),
                quality_score=82 if operations else 60,
                reason="Repeated takes are heuristic candidates and must be reviewed before apply.",
            )
        ]
        if operations
        else [],
        quality_score=82 if operations else 60,
        metadata={"transcript_id": document.id, "candidate_count": len(candidates)},
    )


def plan_remove_mistakes(document: TranscriptDocument) -> EditPlan:
    candidates = detect_mistake_candidates(document)
    operations = _operations_from_candidates(candidates, source="mistake_detection")
    return build_edit_plan(
        plan_id="plan_remove_mistakes",
        intent="remove_mistakes",
        summary=f"Remove {len(operations)} restart/mistake candidate(s) after review.",
        operations=operations,
        warnings=[] if operations else ["no_mistake_candidates_detected"],
        review_cards=[
            ReviewCard(
                id="card_mistakes",
                title="Mistakes and false starts",
                operation_ids=tuple(operation.id for operation in operations),
                quality_score=76 if operations else 60,
                reason="False starts are heuristic candidates and must be reviewed before apply.",
            )
        ]
        if operations
        else [],
        quality_score=76 if operations else 60,
        metadata={"transcript_id": document.id, "candidate_count": len(candidates)},
    )


__all__ = [
    "CleanupCandidate",
    "detect_mistake_candidates",
    "detect_retake_candidates",
    "plan_remove_mistakes",
    "plan_remove_retakes",
]
