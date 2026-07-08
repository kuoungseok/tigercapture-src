"""NLE target-score gap board.

This module does not change readiness scoring.  It explains why a target score
is or is not reachable with the currently attached evidence so UI, local AI, and
MCP clients do not treat synthetic contract coverage as real product proof.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


NLE_TARGET_GAP_SCHEMA = "tigerstudio.nle.target_gap.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def build_nle_target_gap_board(
    readiness_report: Mapping[str, Any] | None = None,
    *,
    target_score: int = 95,
    real_corpus_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a UI-ready gap board for a requested NLE readiness target."""

    report = readiness_report if isinstance(readiness_report, Mapping) else {}
    rows = [dict(row) for row in list(report.get("rows") or []) if isinstance(row, Mapping)]
    target = max(0, min(100, _int(target_score, 95)))
    current_score = _int(report.get("score"), 0)
    blockers = [str(row) for row in list(report.get("blockers") or []) if str(row or "").strip()]
    real_corpus = real_corpus_report if isinstance(real_corpus_report, Mapping) else {}
    real_corpus_summary = (
        real_corpus.get("summary") if isinstance(real_corpus.get("summary"), Mapping) else {}
    )
    real_corpus_thresholds = (
        real_corpus.get("thresholds") if isinstance(real_corpus.get("thresholds"), Mapping) else {}
    )
    row_targets: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("id") or "")
        score = _int(row.get("score"), 0)
        hard_blocked = row_id == "long_large_project_validation" and "real_world_long_project_corpus" in blockers
        row_targets.append(
            {
                "id": row_id,
                "label": str(row.get("label") or row_id),
                "score": score,
                "target": target,
                "gap_to_target": max(0, target - score),
                "status": str(row.get("status") or ""),
                "hard_blocked": hard_blocked,
                "priority": "critical" if hard_blocked else ("high" if score < target else "done"),
                "remaining": list(row.get("remaining") or []),
            }
        )
    row_targets.sort(
        key=lambda row: (
            0 if bool(row.get("hard_blocked")) else 1,
            -_int(row.get("gap_to_target"), 0),
            str(row.get("id") or ""),
        )
    )
    score_gap = max(0, target - current_score)
    real_corpus_blocked = "real_world_long_project_corpus" in blockers
    required_real_corpus = {
        "min_projects": _int(real_corpus_thresholds.get("min_projects"), 3),
        "min_duration_ms": _int(real_corpus_thresholds.get("min_duration_ms"), 30 * 60_000),
        "min_total_video_clips": _int(real_corpus_thresholds.get("min_total_video_clips"), 90),
        "min_total_audio_clips": _int(real_corpus_thresholds.get("min_total_audio_clips"), 20),
        "require_validation_evidence": bool(real_corpus_thresholds.get("require_validation_evidence", True)),
    }
    current_real_corpus = {
        "valid_project_count": _int(real_corpus_summary.get("valid_project_count"), 0),
        "preflight_ready_count": _int(real_corpus_summary.get("preflight_ready_count"), 0),
        "preflight_blocked_count": _int(real_corpus_summary.get("preflight_blocked_count"), 0),
        "validation_ready_count": _int(real_corpus_summary.get("validation_ready_count"), 0),
        "duration_ms": _int(real_corpus_summary.get("duration_ms"), 0),
        "video_clips": _int(real_corpus_summary.get("video_clips"), 0),
        "audio_clips": _int(real_corpus_summary.get("audio_clips"), 0),
        "missing_media_count": _int(real_corpus_summary.get("missing_media_count"), 0),
    }
    corpus_remaining = {
        "projects": max(0, required_real_corpus["min_projects"] - current_real_corpus["valid_project_count"]),
        "preflight_projects": max(
            0,
            required_real_corpus["min_projects"] - current_real_corpus["preflight_ready_count"],
        ),
        "validation_projects": max(
            0,
            required_real_corpus["min_projects"] - current_real_corpus["validation_ready_count"],
        ),
        "duration_ms": max(0, required_real_corpus["min_duration_ms"] - current_real_corpus["duration_ms"]),
        "video_clips": max(0, required_real_corpus["min_total_video_clips"] - current_real_corpus["video_clips"]),
        "audio_clips": max(0, required_real_corpus["min_total_audio_clips"] - current_real_corpus["audio_clips"]),
    }
    next_actions = []
    if real_corpus_blocked:
        next_actions.append("Register and validate real long-form projects before claiming professional NLE parity.")
    if score_gap:
        next_actions.append("Raise low-scoring implementation rows, but keep marketing blocked until hard evidence clears.")
    if not row_targets:
        next_actions.append("Run timeline.professional_nle_readiness first so the target board has rows to analyze.")
    corpus_rows = [
        {
            "id": "valid_project_count",
            "current": current_real_corpus["valid_project_count"],
            "required": required_real_corpus["min_projects"],
            "remaining": corpus_remaining["projects"],
        },
        {
            "id": "preflight_ready_count",
            "current": current_real_corpus["preflight_ready_count"],
            "required": required_real_corpus["min_projects"],
            "remaining": corpus_remaining["preflight_projects"],
            "blocked_count": current_real_corpus["preflight_blocked_count"],
        },
        {
            "id": "validation_ready_count",
            "current": current_real_corpus["validation_ready_count"],
            "required": required_real_corpus["min_projects"],
            "remaining": corpus_remaining["validation_projects"],
        },
        {
            "id": "duration_ms",
            "current": current_real_corpus["duration_ms"],
            "required": required_real_corpus["min_duration_ms"],
            "remaining": corpus_remaining["duration_ms"],
        },
        {
            "id": "video_clips",
            "current": current_real_corpus["video_clips"],
            "required": required_real_corpus["min_total_video_clips"],
            "remaining": corpus_remaining["video_clips"],
        },
        {
            "id": "audio_clips",
            "current": current_real_corpus["audio_clips"],
            "required": required_real_corpus["min_total_audio_clips"],
            "remaining": corpus_remaining["audio_clips"],
        },
    ]
    return {
        "schema": NLE_TARGET_GAP_SCHEMA,
        "ready": bool(rows),
        "target_score": target,
        "current_score": current_score,
        "score_gap": score_gap,
        "target_met": current_score >= target,
        "professional_nle_claim_ok": bool(report.get("professional_nle_claim_ok")),
        "professional_claim_blocked": not bool(report.get("professional_nle_claim_ok")),
        "hard_blockers": blockers,
        "target_score_without_claim_ok_is_misleading": bool(current_score >= target and blockers),
        "sections": [
            {
                "id": "score_rows",
                "title": "Score row gaps",
                "status": "ready",
                "rows": row_targets,
            },
            {
                "id": "real_corpus",
                "title": "Real long-project corpus gate",
                "status": "blocked" if real_corpus_blocked else "ready",
                "rows": corpus_rows,
                "remaining": corpus_remaining,
            },
            {
                "id": "commands",
                "title": "Next commands",
                "status": "ready",
                "rows": [
                    {
                        "id": "open_gate_board",
                        "action_id": "nle.real_corpus.gate_board",
                    },
                    {
                        "id": "open_validation_packet",
                        "action_id": "nle.real_corpus.validation_packet",
                    },
                    {
                        "id": "run_nle_readiness",
                        "command": ".\\.venv\\Scripts\\python.exe tools\\qa_nle_readiness.py --out debugCapture\\nle_readiness_qa.json",
                    },
                    {
                        "id": "run_real_corpus_qa",
                        "command": ".\\.venv\\Scripts\\python.exe tools\\qa_nle_real_project_corpus.py",
                    },
                ],
            },
        ],
        "readiness": {
            "target_gap_board_ready": bool(rows),
            "real_corpus_required_for_claim": real_corpus_blocked,
            "target_score_reached": current_score >= target,
            "claim_safe": bool(report.get("professional_nle_claim_ok")),
        },
        "next_actions": next_actions,
    }


__all__ = ["NLE_TARGET_GAP_SCHEMA", "build_nle_target_gap_board"]
