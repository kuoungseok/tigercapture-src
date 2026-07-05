"""Safe intake helpers for real AI edit corpus cases.

The AI edit claim needs real user projects, not more synthetic fixtures. This
module creates checklist templates that help collect those cases without adding
placeholder entries to the manifest or pretending the smart-edit claim is ready.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Mapping

from app.ai_edit_corpus_quality import load_ai_edit_corpus_cases


DEFAULT_AI_EDIT_TARGET = 20

_SLOT_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "language": "ko",
        "scenario": "long_tutorial",
        "expected_intent": "clean_tutorial",
        "required_operations": ["delete_time_range", "create_subtitles", "add_auto_zoom", "add_chapter_markers"],
    },
    {
        "language": "en",
        "scenario": "tutorial",
        "expected_intent": "clean_tutorial",
        "required_operations": ["delete_time_range", "create_subtitles", "add_auto_zoom", "add_chapter_markers"],
    },
    {
        "language": "ko",
        "scenario": "shortform",
        "expected_intent": "shorts",
        "required_operations": ["create_short_candidate", "set_reframe", "create_subtitles", "add_render_queue_job"],
    },
    {
        "language": "en",
        "scenario": "product",
        "expected_intent": "product_demo",
        "required_operations": ["apply_preset", "add_callout", "add_auto_zoom", "create_subtitles"],
    },
)


def _profile_for_slot(index: int) -> dict[str, Any]:
    return dict(_SLOT_PROFILES[(max(1, index) - 1) % len(_SLOT_PROFILES)])


def _case_id(index: int) -> str:
    return f"ai-edit-real-{index:02d}"


def _from_template_command(template_path: str | Path) -> str:
    return (
        "python tools/register_ai_edit_corpus_case.py "
        f"--from-template {json.dumps(str(template_path), ensure_ascii=False)} "
        "--overwrite"
    )


def ai_edit_case_template(index: int, *, template_path: str | Path | None = None) -> dict[str, Any]:
    """Return a manifest-ready template that is not counted until filled."""
    profile = _profile_for_slot(index)
    case_id = _case_id(index)
    language = str(profile["language"])
    scenario = str(profile["scenario"])
    required_ops = list(profile["required_operations"])
    registration_command = _from_template_command(template_path or "<this-ai-edit-template.json>")
    return {
        "kind": "ai_edit_real_case_template",
        "schema_version": 1,
        "counts_for_ai_claim": False,
        "instructions": [
            "Fill this with a real user recording/transcript before copying it into qa_corpus/ai_editing_corpus/manifest.json.",
            "Keep fixture=false only for real projects with a source transcript and expected edit intent.",
            "Fill manifest_case.prompt and manifest_case.transcript_path, then run registration_command; it validates the transcript and prompt first.",
            "Run tools/qa_ai_edit_corpus_quality.py --manifest qa_corpus/ai_editing_corpus/manifest.json --use-provider after adding cases.",
        ],
        "registration_command": registration_command,
        "manifest_case": {
            "id": case_id,
            "label": f"Real AI edit case {index:02d}",
            "language": language,
            "scenario": scenario,
            "fixture": False,
            "source_format": "srt",
            "transcript_path": f"transcripts/{case_id}.srt",
            "source_media_path": "",
            "prompt": "",
            "expected_intent": profile["expected_intent"],
            "required_operations": required_ops,
            "min_segments": 3,
            "notes": "Replace placeholders with a real editing request, real transcript, and expected operations.",
        },
        "acceptance_checklist": {
            "real_user_project": False,
            "transcript_or_asr_available": False,
            "prompt_is_natural_language": False,
            "expected_operations_reviewed": False,
            "provider_plan_reviewed_before_apply": False,
        },
    }


def _missing_case_requirements(case: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    if bool(case.get("fixture", False)):
        missing.append("real_case")
    if not str(case.get("prompt") or "").strip():
        missing.append("prompt")
    if not str(case.get("language") or "").strip():
        missing.append("language")
    if not str(case.get("scenario") or "").strip():
        missing.append("scenario")
    if not str(case.get("transcript") or case.get("transcript_path") or "").strip():
        missing.append("transcript")
    if not list(case.get("required_operations") or []):
        missing.append("required_operations")
    if not str(case.get("expected_intent") or "").strip():
        missing.append("expected_intent")
    return missing


def build_ai_edit_corpus_intake_report(
    *,
    manifest_path: str | Path | None = None,
    target_min: int = DEFAULT_AI_EDIT_TARGET,
    template_dir: str | Path | None = None,
    write_templates: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Build a real-corpus intake report and optionally write safe templates."""
    target = max(1, int(target_min or DEFAULT_AI_EDIT_TARGET))
    cases, manifest = load_ai_edit_corpus_cases(manifest_path)
    real_cases = [case for case in cases if not bool(case.get("fixture", False))]
    fixture_cases = [case for case in cases if bool(case.get("fixture", False))]
    out_dir = Path(template_dir) if template_dir else Path("qa_corpus") / "ai_editing_corpus" / "intake_templates"

    rows: list[dict[str, Any]] = []
    templates_written = 0
    templates_skipped_existing = 0
    ready_cases = 0
    for idx in range(1, target + 1):
        case = real_cases[idx - 1] if idx <= len(real_cases) else None
        template_path = out_dir / f"{_case_id(idx)}.template.json"
        if case is not None:
            missing = _missing_case_requirements(case)
            ready = not missing
            ready_cases += 1 if ready else 0
            rows.append(
                {
                    "index": idx,
                    "case_id": str(case.get("id") or _case_id(idx)),
                    "state": "ready" if ready else "needs_metadata",
                    "ready": ready,
                    "missing_requirements": missing,
                    "language": str(case.get("language") or ""),
                    "scenario": str(case.get("scenario") or ""),
                    "prompt": str(case.get("prompt") or "")[:160],
                    "template_path": "",
                }
            )
            continue

        template_write = "not_requested"
        if write_templates:
            if template_path.exists() and not overwrite:
                templates_skipped_existing += 1
                template_write = "skipped_existing"
            else:
                template_path.parent.mkdir(parents=True, exist_ok=True)
                template_path.write_text(
                    json.dumps(ai_edit_case_template(idx, template_path=template_path), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                templates_written += 1
                template_write = "written"
        profile = _profile_for_slot(idx)
        required_ops = list(profile["required_operations"])
        rows.append(
            {
                "index": idx,
                "case_id": _case_id(idx),
                "state": "template_needed",
                "ready": False,
                "missing_requirements": ["real_case", "prompt", "transcript", "provider_review"],
                "language": profile["language"],
                "scenario": profile["scenario"],
                "prompt": "",
                "template_path": str(template_path),
                "template_write": template_write,
                "registration_command": _from_template_command(template_path),
            }
        )

    missing_real_cases = max(0, target - len(real_cases))
    category_languages = sorted({str(case.get("language") or "") for case in real_cases if str(case.get("language") or "")})
    category_scenarios = sorted({str(case.get("scenario") or "") for case in real_cases if str(case.get("scenario") or "")})
    next_actions: list[str] = []
    if missing_real_cases:
        next_actions.append(f"Collect {missing_real_cases} more real AI edit cases with transcript, prompt, and expected operations.")
    if write_templates:
        next_actions.append(f"Fill templates in {out_dir}, then run each registration_command to validate and register them.")
    else:
        next_actions.append("Run tools/prepare_ai_edit_corpus_intake.py --write-templates to create real-case templates.")
    next_actions.append("Prefer tools/register_ai_edit_corpus_case.py over manual manifest edits so placeholder prompts are rejected.")
    next_actions.append("Run tools/qa_ai_edit_corpus_quality.py --use-provider after adding real cases and wiring an AI provider.")

    return {
        "ok": ready_cases >= target,
        "claim_unblocked_by_templates": False,
        "manifest": manifest,
        "summary": {
            "target_min": target,
            "cases": len(cases),
            "fixture_cases": len(fixture_cases),
            "real_cases": len(real_cases),
            "ready_real_cases": ready_cases,
            "missing_real_cases": missing_real_cases,
            "templates_written": templates_written,
            "templates_skipped_existing": templates_skipped_existing,
            "languages": category_languages,
            "scenarios": category_scenarios,
        },
        "rows": rows,
        "next_actions": next_actions,
    }
