"""Corpus-level quality gates for AI Script Edit.

This module keeps the AI editing claim honest: deterministic rules can prove
that the safe plan pipeline works, but "AI edits intelligently" needs real
long-form, bilingual, tutorial, and short-form corpus evidence plus a wired
LLM/agent provider.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json
from typing import Any, Mapping, Sequence


def _srt_time(ms: int) -> str:
    ms = max(0, int(ms))
    hh, rem = divmod(ms, 3_600_000)
    mm, rem = divmod(rem, 60_000)
    ss, milli = divmod(rem, 1000)
    return f"{hh:02d}:{mm:02d}:{ss:02d},{milli:03d}"


def _make_srt(lines: Sequence[tuple[int, int, str]]) -> str:
    blocks = []
    for idx, (start_ms, end_ms, text) in enumerate(lines, start=1):
        blocks.append(f"{idx}\n{_srt_time(start_ms)} --> {_srt_time(end_ms)}\n{text}")
    return "\n\n".join(blocks) + "\n"


def _long_korean_tutorial_srt() -> str:
    rows = []
    for idx in range(12):
        start = idx * 60_000
        rows.append(
            (
                start,
                start + 8_000,
                f"어 이제 {idx + 1}번째 단계에서 커서 클릭과 메뉴 이동을 설명합니다.",
            )
        )
    return _make_srt(rows)


BUILTIN_AI_EDIT_CORPUS_CASES: tuple[dict[str, Any], ...] = (
    {
        "id": "ko_tutorial_cleanup",
        "label": "Korean tutorial cleanup",
        "language": "ko",
        "scenario": "tutorial",
        "fixture": True,
        "prompt": "군더더기 빼고 자막과 자동 줌까지 보기 좋게 정리해줘",
        "source_format": "srt",
        "transcript": _make_srt(
            [
                (1_000, 4_000, "어 오늘은 재질 편집을 설명하겠습니다."),
                (5_000, 8_000, "이제 base color를 연결하고 클릭 위치를 확대합니다."),
                (9_000, 12_000, "그러니까 마지막에는 결과 화면을 확인합니다."),
            ]
        ),
        "silence_intervals": [{"start_ms": 4_000, "end_ms": 5_200}],
        "expected_intent": "clean_tutorial",
        "required_operations": ["delete_time_range", "create_subtitles", "add_auto_zoom", "add_chapter_markers"],
        "min_segments": 3,
    },
    {
        "id": "en_tutorial_cleanup",
        "label": "English tutorial cleanup",
        "language": "en",
        "scenario": "tutorial",
        "fixture": True,
        "prompt": "Clean this tutorial, remove filler words, add captions and cursor zoom suggestions",
        "source_format": "srt",
        "transcript": _make_srt(
            [
                (0, 2_800, "Um today we explain the material graph."),
                (3_400, 6_800, "You know we connect base color and then click preview."),
                (8_000, 11_500, "Basically the final render should be easy to follow."),
            ]
        ),
        "silence_intervals": [{"start_ms": 6_800, "end_ms": 8_000}],
        "expected_intent": "clean_tutorial",
        "required_operations": ["delete_time_range", "create_subtitles", "add_auto_zoom", "add_chapter_markers"],
        "min_segments": 3,
    },
    {
        "id": "shortform_vertical",
        "label": "Short-form vertical cut",
        "language": "ko",
        "scenario": "shortform",
        "fixture": True,
        "prompt": "이 영상에서 틱톡 쇼츠 후보를 만들고 세로 자막까지 준비해줘",
        "source_format": "srt",
        "transcript": _make_srt(
            [
                (0, 2_500, "처음 3초에 결과를 먼저 보여줍니다."),
                (3_000, 7_000, "두 번째 장면에서는 실패한 예시와 해결법을 비교합니다."),
                (8_000, 12_000, "마지막에는 바로 따라 할 수 있는 팁을 정리합니다."),
            ]
        ),
        "expected_intent": "shorts",
        "required_operations": ["create_short_candidate", "set_reframe", "create_subtitles", "add_render_queue_job"],
        "min_segments": 3,
    },
    {
        "id": "product_demo",
        "label": "Product demo",
        "language": "en",
        "scenario": "product",
        "fixture": True,
        "prompt": "Turn this into a clean product launch demo with callouts and captions",
        "source_format": "srt",
        "transcript": _make_srt(
            [
                (500, 3_000, "The new dashboard loads projects faster."),
                (3_500, 7_000, "Here is the export queue and the review step."),
                (7_500, 11_000, "The result is ready for a launch clip."),
            ]
        ),
        "expected_intent": "product_demo",
        "required_operations": ["apply_preset", "add_callout", "add_auto_zoom", "create_subtitles"],
        "min_segments": 3,
    },
    {
        "id": "long_bilingual_tutorial",
        "label": "Long bilingual tutorial",
        "language": "ko",
        "scenario": "long_tutorial",
        "fixture": True,
        "prompt": "긴 튜토리얼을 챕터와 자막 중심으로 정리하고 군더더기를 줄여줘",
        "source_format": "srt",
        "transcript": _long_korean_tutorial_srt(),
        "silence_intervals": [{"start_ms": 120_000, "end_ms": 121_200}, {"start_ms": 420_000, "end_ms": 421_600}],
        "expected_intent": "clean_tutorial",
        "required_operations": ["delete_time_range", "create_subtitles", "add_chapter_markers", "add_auto_zoom"],
        "min_segments": 10,
        "min_duration_ms": 600_000,
    },
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _load_case_transcript(case: Mapping[str, Any], *, base_dir: Path | None = None) -> str:
    if case.get("transcript") is not None:
        return str(case.get("transcript") or "")
    transcript_path = str(case.get("transcript_path") or "").strip()
    if not transcript_path:
        return ""
    path = Path(transcript_path)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    return ""


def load_ai_edit_corpus_cases(manifest_path: str | Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load AI edit corpus cases, falling back to built-in fixtures."""
    path = Path(manifest_path) if manifest_path else Path("qa_corpus/ai_editing_corpus/manifest.json")
    manifest = _read_json(path)
    raw_cases = manifest.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        return [dict(case) for case in BUILTIN_AI_EDIT_CORPUS_CASES], {
            "path": str(path),
            "found": False,
            "source": "builtin_fixtures",
            "min_real_cases": int(manifest.get("min_real_cases", 20) or 20) if manifest else 20,
        }
    base_dir = path.parent
    cases = []
    for idx, raw in enumerate(raw_cases, start=1):
        if not isinstance(raw, Mapping):
            continue
        case = dict(raw)
        case.setdefault("id", f"case_{idx:03d}")
        case.setdefault("source_format", "auto")
        case.setdefault("fixture", False)
        case["transcript"] = _load_case_transcript(case, base_dir=base_dir)
        cases.append(case)
    return cases, {
        "path": str(path),
        "found": True,
        "source": "manifest",
        "min_real_cases": int(manifest.get("min_real_cases", 20) or 20),
    }


def _case_duration_ms(document: Any) -> int:
    segments = list(getattr(document, "segments", ()) or ())
    if not segments:
        return 0
    return max(int(segment.end_ms) for segment in segments) - min(int(segment.start_ms) for segment in segments)


def _score_case(
    *,
    case: Mapping[str, Any],
    plan: Any,
    document: Any,
    validation_ok: bool,
    provider_result: Mapping[str, Any],
) -> tuple[int, list[str], dict[str, Any]]:
    required_ops = [str(item) for item in (case.get("required_operations") or [])]
    op_counts = Counter(str(operation.type) for operation in getattr(plan, "operations", ()) or ())
    missing_ops = [op for op in required_ops if op_counts.get(op, 0) <= 0]
    expected_intent = str(case.get("expected_intent") or "").strip()
    intent_match = not expected_intent or str(getattr(plan, "intent", "")) == expected_intent
    review_cards = list(getattr(plan, "review_cards", ()) or ())
    operation_ids = {operation.id for operation in getattr(plan, "operations", ()) or ()}
    cards_valid = bool(review_cards) and all(set(card.operation_ids) <= operation_ids and card.operation_ids for card in review_cards)
    min_segments = int(case.get("min_segments", 1) or 1)
    segment_count = len(getattr(document, "segments", ()) or ())
    min_duration_ms = int(case.get("min_duration_ms", 0) or 0)
    duration_ms = _case_duration_ms(document)

    failures = []
    if not validation_ok:
        failures.append("plan_validation_failed")
    if not intent_match:
        failures.append("intent_mismatch")
    if missing_ops:
        failures.append("missing_required_operations")
    if segment_count < min_segments:
        failures.append("not_enough_transcript_segments")
    if min_duration_ms and duration_ms < min_duration_ms:
        failures.append("duration_below_minimum")
    if not cards_valid:
        failures.append("review_cards_missing_or_invalid")

    coverage = 1.0 if not required_ops else (len(required_ops) - len(missing_ops)) / max(1, len(required_ops))
    score = 0
    score += 20 if validation_ok else 0
    score += 20 if intent_match else 0
    score += int(round(25 * coverage))
    score += 15 if cards_valid else 0
    score += 10 if segment_count >= min_segments else 0
    score += 5 if not min_duration_ms or duration_ms >= min_duration_ms else 0
    score += min(5, int(getattr(plan, "quality_score", 0) or 0) // 20)
    if provider_result.get("fallback_used"):
        score = min(score, 82)

    metrics = {
        "expected_intent": expected_intent,
        "actual_intent": str(getattr(plan, "intent", "")),
        "intent_match": intent_match,
        "required_operations": required_ops,
        "operation_counts": dict(sorted(op_counts.items())),
        "missing_operations": missing_ops,
        "review_cards_valid": cards_valid,
        "segment_count": segment_count,
        "duration_ms": duration_ms,
        "provider": str(getattr(plan, "provider", "") or provider_result.get("provider") or "rule_based"),
        "provider_result": dict(provider_result),
    }
    return min(100, max(0, score)), failures, metrics


def _plan_case(
    case: Mapping[str, Any],
    *,
    use_provider: bool,
    env: Mapping[str, str] | None,
    provider_timeout_seconds: int | None = None,
    provider_retries: int = 0,
) -> dict[str, Any]:
    from app.ai_edit_plan import EditPlanValidationError, validate_edit_plan_json
    from app.ai_providers import generate_selected_provider_plan
    from app.ai_script_edit_panel import ScriptEditPanelModel

    case_id = str(case.get("id") or "case")
    prompt = str(case.get("prompt") or "")
    transcript = _load_case_transcript(case)
    model = ScriptEditPanelModel(source_media_id=str(case.get("source_media_id") or case_id), language=str(case.get("language") or "und"))
    document = model.import_transcript_text(
        transcript,
        source_format=str(case.get("source_format") or "auto"),
        document_id=f"ai_corpus_{case_id}",
        language=str(case.get("language") or "und"),
    )
    model.set_silence_intervals(case.get("silence_intervals") or [])
    base_plan = model.generate_plan_from_prompt(prompt)
    provider_result: dict[str, Any] = {"used": False, "provider": "rule_based", "fallback_used": False}
    plan = base_plan
    if use_provider:
        attempts: list[dict[str, Any]] = []
        result = None
        max_attempts = max(1, int(provider_retries or 0) + 1)
        for attempt_index in range(1, max_attempts + 1):
            provider_kwargs: dict[str, Any] = {"document": document, "env": env}
            if provider_timeout_seconds:
                provider_kwargs["timeout_seconds"] = int(provider_timeout_seconds)
            result = generate_selected_provider_plan(
                prompt,
                base_plan,
                **provider_kwargs,
            )
            attempt_metadata = dict(result.metadata or {})
            attempt = {
                "index": attempt_index,
                "ok": bool(result.ok),
                "provider": result.provider,
                "fallback_used": bool(attempt_metadata.get("fallback_used") or not result.ok),
                "message": result.reason,
                "metadata": attempt_metadata,
            }
            attempts.append(attempt)
            if result.ok and result.plan is not None:
                break
        assert result is not None
        result_metadata = dict(result.metadata or {})
        provider_result = {
            "used": True,
            "ok": bool(result.ok),
            "provider": result.provider,
            "fallback_used": bool(result_metadata.get("fallback_used") or not result.ok),
            "message": result.reason,
            "metadata": result_metadata,
            "attempts": attempts,
            "attempt_count": len(attempts),
        }
        if result.plan is not None:
            plan = result.plan
    validation_ok = False
    validation_error = ""
    try:
        restored = validate_edit_plan_json(plan.to_stable_json())
        validation_ok = restored.to_stable_json() == plan.to_stable_json()
    except EditPlanValidationError as exc:
        validation_error = str(exc)
    score, failures, metrics = _score_case(
        case=case,
        plan=plan,
        document=document,
        validation_ok=validation_ok,
        provider_result=provider_result,
    )
    return {
        "id": case_id,
        "label": str(case.get("label") or case_id),
        "language": str(case.get("language") or "und"),
        "scenario": str(case.get("scenario") or "general"),
        "fixture": bool(case.get("fixture", False)),
        "ok": not failures,
        "score": score,
        "failures": failures,
        "validation_error": validation_error,
        "metrics": metrics,
        "plan": plan.to_dict(),
    }


def build_ai_edit_corpus_quality_report(
    *,
    manifest_path: str | Path | None = None,
    use_provider: bool = False,
    env: Mapping[str, str] | None = None,
    provider_timeout_seconds: int | None = None,
    provider_retries: int = 0,
) -> dict[str, Any]:
    from app.ai_providers import effective_generation_provider_id, selected_ai_provider_id, ai_provider_readiness

    cases, manifest = load_ai_edit_corpus_cases(manifest_path)
    rows = []
    for case in cases:
        try:
            rows.append(
                _plan_case(
                    case,
                    use_provider=use_provider,
                    env=env,
                    provider_timeout_seconds=provider_timeout_seconds,
                    provider_retries=provider_retries,
                )
            )
        except Exception as exc:
            rows.append(
                {
                    "id": str(case.get("id") or "case"),
                    "label": str(case.get("label") or case.get("id") or "case"),
                    "language": str(case.get("language") or "und"),
                    "scenario": str(case.get("scenario") or "general"),
                    "fixture": bool(case.get("fixture", False)),
                    "ok": False,
                    "score": 0,
                    "failures": ["case_exception"],
                    "exception": str(exc),
                    "metrics": {},
                    "plan": {},
                }
            )
    total = len(rows)
    failures = [row["id"] for row in rows if not row.get("ok")]
    average_score = int(round(sum(int(row.get("score", 0) or 0) for row in rows) / max(1, total)))
    languages = sorted({str(row.get("language") or "und") for row in rows})
    scenarios = sorted({str(row.get("scenario") or "general") for row in rows})
    real_cases = [row for row in rows if not bool(row.get("fixture"))]
    fixture_cases = [row for row in rows if bool(row.get("fixture"))]
    readiness = ai_provider_readiness(env)
    selected_provider = selected_ai_provider_id(env)
    effective_provider = effective_generation_provider_id(env)
    provider_row = readiness.get(effective_provider) or readiness.get(selected_provider) or {}
    provider_results = [
        dict((row.get("metrics") or {}).get("provider_result") or {})
        for row in rows
        if isinstance(row, dict)
    ]
    provider_attempts = [row for row in provider_results if row.get("used")]
    provider_successes = [row for row in provider_attempts if row.get("ok") and not row.get("fallback_used")]
    provider_fallbacks = [row for row in provider_attempts if row.get("fallback_used") or not row.get("ok")]
    provider_total_attempts = sum(max(1, int(row.get("attempt_count", 1) or 1)) for row in provider_attempts)
    provider_executor_wired = bool(provider_row.get("executor_wired") or provider_attempts)
    provider_uses_llm_source = effective_provider not in {"", "rule_based", "manual_json"} or bool(provider_successes)
    provider_fallback = str(provider_row.get("generation_fallback_provider") or "")
    provider_setup_state = str(provider_row.get("setup_state") or "")
    provider_direct_generation_ready = (
        provider_uses_llm_source
        and provider_executor_wired
        and (provider_fallback != "rule_based" or bool(provider_successes))
        and provider_setup_state != "executor_failed"
    )
    provider_is_llm = bool(
        use_provider
        and provider_direct_generation_ready
        and len(provider_successes) == total
        and not provider_fallbacks
    )

    category_requirements = {
        "korean": any(lang.startswith("ko") for lang in languages),
        "english": any(lang.startswith("en") for lang in languages),
        "tutorial": any("tutorial" in scenario for scenario in scenarios),
        "shortform": any(scenario in {"shortform", "shorts"} for scenario in scenarios),
        "product": any("product" in scenario for scenario in scenarios),
        "long": any("long" in scenario for scenario in scenarios),
    }
    missing_categories = [name for name, ok in category_requirements.items() if not ok]
    min_real_cases = int(manifest.get("min_real_cases", 20) or 20)
    corpus_quality_ok = total >= 5 and not failures and average_score >= 80 and not missing_categories
    real_corpus_ready = len(real_cases) >= min_real_cases and corpus_quality_ok
    safe_mvp_ready = total >= 5 and average_score >= 75 and len(failures) <= max(0, total // 5)

    claim_blockers = []
    if not provider_executor_wired or not provider_uses_llm_source:
        claim_blockers.append("provider_executor_not_wired")
    elif not use_provider:
        claim_blockers.append("provider_not_exercised_on_corpus")
    elif not provider_successes:
        claim_blockers.append("provider_execution_failed_on_corpus")
    elif provider_fallbacks:
        claim_blockers.append("provider_execution_fallbacks_present")
    if len(real_cases) < min_real_cases:
        claim_blockers.append("real_user_corpus_below_min")
    if missing_categories:
        claim_blockers.append("coverage_categories_missing")
    if failures:
        claim_blockers.append("case_failures_present")
    if average_score < 85:
        claim_blockers.append("average_quality_below_smart_edit_claim")

    return {
        "ok": safe_mvp_ready,
        "score": average_score,
        "safe_mvp_ready": safe_mvp_ready,
        "smart_edit_claim_ready": bool(corpus_quality_ok and real_corpus_ready and provider_is_llm and not claim_blockers),
        "corpus_quality_ok": corpus_quality_ok,
        "real_corpus_ready": real_corpus_ready,
        "claim_blockers": claim_blockers,
        "manifest": manifest,
        "provider": {
            "selected": selected_provider,
            "effective": effective_provider,
            "use_provider": bool(use_provider),
            "executor_wired": provider_executor_wired,
            "direct_generation_ready": provider_direct_generation_ready,
            "exercised_on_corpus": bool(use_provider),
            "corpus_attempts": len(provider_attempts),
            "corpus_provider_calls": provider_total_attempts,
            "corpus_direct_successes": len(provider_successes),
            "corpus_fallbacks": len(provider_fallbacks),
            "provider_timeout_seconds": int(provider_timeout_seconds or 0),
            "provider_retries": max(0, int(provider_retries or 0)),
            "is_llm_claim_ready": provider_is_llm,
            "state": provider_row,
        },
        "summary": {
            "cases": total,
            "fixture_cases": len(fixture_cases),
            "real_cases": len(real_cases),
            "min_real_cases": min_real_cases,
            "failures": len(failures),
            "languages": languages,
            "scenarios": scenarios,
            "missing_categories": missing_categories,
        },
        "category_requirements": category_requirements,
        "failures": failures,
        "cases": rows,
        "claim_guidance": {
            "safe": "local-first Script Edit MVP with review/apply safety",
            "unsafe_until_ready": "AI가 긴 영상과 숏폼을 영리하게 자동 편집한다",
            "reason": "Smart-edit claims require a wired LLM/agent provider and a real user corpus, not only deterministic fixtures.",
        },
    }
