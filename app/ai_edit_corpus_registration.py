from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_AI_EDIT_MANIFEST = Path("qa_corpus/ai_editing_corpus/manifest.json")


def _read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue
    return ""


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.setdefault("version", 1)
    payload.setdefault("min_real_cases", 20)
    payload.setdefault("cases", [])
    if not isinstance(payload.get("cases"), list):
        payload["cases"] = []
    return payload


def _srt_segment_count(text: str) -> int:
    return len(re.findall(r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}", text or ""))


def _wordish_count(text: str) -> int:
    return len(re.findall(r"[\w가-힣]+", text or "", flags=re.UNICODE))


def _clean_id(value: str, fallback: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    return token or fallback


def _relative_or_absolute(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except Exception:
        return str(path)


def _copy_transcript_for_manifest(transcript_path: Path, manifest_path: Path, case_id: str) -> Path:
    suffix = transcript_path.suffix or ".srt"
    target = manifest_path.parent / "transcripts" / f"{case_id}{suffix}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(transcript_path, target)
    return target


def load_ai_edit_case_template(path: str | Path) -> dict[str, Any]:
    template_path = Path(path)
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("AI edit corpus template must be a JSON object")
    if str(payload.get("kind") or "") != "ai_edit_real_case_template":
        raise ValueError("AI edit corpus template kind must be ai_edit_real_case_template")
    case = payload.get("manifest_case")
    if not isinstance(case, Mapping):
        raise ValueError("AI edit corpus template is missing manifest_case")
    return dict(payload)


def _resolve_template_path(raw_path: str | Path, *, template_path: Path, manifest_path: Path) -> Path:
    path = Path(str(raw_path or "").strip())
    if path.is_absolute():
        return path
    candidates = [
        template_path.parent / path,
        manifest_path.parent / path,
        Path.cwd() / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[1]


def validate_ai_edit_real_case_payload(case: Mapping[str, Any], transcript_text: str) -> dict[str, Any]:
    required_ops = [str(item).strip() for item in list(case.get("required_operations") or []) if str(item).strip()]
    segment_count = _srt_segment_count(transcript_text)
    if segment_count <= 0 and transcript_text.strip():
        segment_count = max(1, transcript_text.count("\n\n") + 1)
    min_segments = max(1, int(case.get("min_segments", 1) or 1))
    missing: list[str] = []
    if bool(case.get("fixture", False)):
        missing.append("fixture_must_be_false")
    if not str(case.get("id") or "").strip():
        missing.append("id")
    if not str(case.get("prompt") or "").strip():
        missing.append("prompt")
    if not str(case.get("language") or "").strip():
        missing.append("language")
    if not str(case.get("scenario") or "").strip():
        missing.append("scenario")
    if not str(case.get("expected_intent") or "").strip():
        missing.append("expected_intent")
    if not required_ops:
        missing.append("required_operations")
    if not transcript_text.strip():
        missing.append("transcript_text")
    if segment_count < min_segments:
        missing.append("transcript_segments")
    if _wordish_count(str(case.get("prompt") or "")) < 3:
        missing.append("natural_language_prompt")
    return {
        "ok": not missing,
        "missing": missing,
        "required_operations": required_ops,
        "segment_count": segment_count,
        "min_segments": min_segments,
        "prompt_word_count": _wordish_count(str(case.get("prompt") or "")),
        "transcript_chars": len(transcript_text),
    }


def register_ai_edit_corpus_case(
    *,
    manifest_path: str | Path = DEFAULT_AI_EDIT_MANIFEST,
    transcript_path: str | Path,
    prompt: str,
    language: str,
    scenario: str,
    expected_intent: str,
    required_operations: Sequence[str],
    case_id: str = "",
    label: str = "",
    source_media_path: str | Path | None = None,
    source_format: str = "srt",
    min_segments: int = 3,
    min_duration_ms: int = 0,
    copy_transcript: bool = True,
    overwrite: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    manifest = Path(manifest_path)
    transcript = Path(transcript_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload = _read_manifest(manifest)
    cases = [dict(row) for row in payload.get("cases", []) if isinstance(row, Mapping)]
    fallback_id = f"ai-edit-real-{len([row for row in cases if not bool(row.get('fixture', False))]) + 1:02d}"
    clean_case_id = _clean_id(case_id or transcript.stem, fallback_id)

    if not transcript.is_file():
        return {
            "ok": False,
            "registered": False,
            "manifest_path": str(manifest),
            "case_id": clean_case_id,
            "warning": "transcript_missing",
            "missing": ["transcript_file"],
        }
    transcript_text = _read_text(transcript)
    stored_transcript = _copy_transcript_for_manifest(transcript, manifest, clean_case_id) if copy_transcript else transcript
    case = {
        "id": clean_case_id,
        "label": str(label or clean_case_id),
        "language": str(language or "").strip(),
        "scenario": str(scenario or "").strip(),
        "fixture": False,
        "source_format": str(source_format or transcript.suffix.lstrip(".") or "srt"),
        "transcript_path": _relative_or_absolute(stored_transcript, manifest.parent),
        "source_media_path": str(source_media_path or ""),
        "prompt": str(prompt or "").strip(),
        "expected_intent": str(expected_intent or "").strip(),
        "required_operations": [str(item).strip() for item in required_operations if str(item).strip()],
        "min_segments": max(1, int(min_segments or 1)),
        "notes": str(notes or ""),
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    if int(min_duration_ms or 0) > 0:
        case["min_duration_ms"] = int(min_duration_ms)

    validation = validate_ai_edit_real_case_payload(case, transcript_text)
    if not validation["ok"]:
        return {
            "ok": False,
            "registered": False,
            "manifest_path": str(manifest),
            "case_id": clean_case_id,
            "warning": "case_requirements_missing",
            "missing": validation["missing"],
            "validation": validation,
        }

    existing_index = next((idx for idx, row in enumerate(cases) if str(row.get("id") or "") == clean_case_id), -1)
    if existing_index >= 0 and not overwrite:
        return {
            "ok": True,
            "registered": False,
            "manifest_path": str(manifest),
            "case_id": clean_case_id,
            "warning": "case_already_exists",
            "validation": validation,
        }
    if existing_index >= 0:
        cases[existing_index] = case
    else:
        cases.append(case)
    payload["cases"] = cases
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    real_count = len([row for row in cases if not bool(row.get("fixture", False))])
    return {
        "ok": True,
        "registered": True,
        "manifest_path": str(manifest),
        "case_id": clean_case_id,
        "case": case,
        "real_cases": real_count,
        "min_real_cases": int(payload.get("min_real_cases", 20) or 20),
        "validation": validation,
        "warning": "",
    }


def register_ai_edit_corpus_case_from_template(
    template_path: str | Path,
    *,
    manifest_path: str | Path = DEFAULT_AI_EDIT_MANIFEST,
    copy_transcript: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    template_file = Path(template_path)
    manifest = Path(manifest_path)
    template = load_ai_edit_case_template(template_file)
    case = dict(template.get("manifest_case") or {})
    transcript_raw = str(case.get("transcript_path") or "").strip()
    transcript_path = _resolve_template_path(transcript_raw, template_path=template_file, manifest_path=manifest)
    report = register_ai_edit_corpus_case(
        manifest_path=manifest,
        transcript_path=transcript_path,
        prompt=str(case.get("prompt") or ""),
        language=str(case.get("language") or ""),
        scenario=str(case.get("scenario") or ""),
        expected_intent=str(case.get("expected_intent") or ""),
        required_operations=list(case.get("required_operations") or []),
        case_id=str(case.get("id") or ""),
        label=str(case.get("label") or ""),
        source_media_path=_resolve_template_path(case.get("source_media_path"), template_path=template_file, manifest_path=manifest)
        if str(case.get("source_media_path") or "").strip()
        else None,
        source_format=str(case.get("source_format") or "srt"),
        min_segments=max(1, int(case.get("min_segments", 3) or 3)),
        min_duration_ms=max(0, int(case.get("min_duration_ms", 0) or 0)),
        copy_transcript=copy_transcript,
        overwrite=overwrite,
        notes=str(case.get("notes") or ""),
    )
    report["template_path"] = str(template_file)
    return report
