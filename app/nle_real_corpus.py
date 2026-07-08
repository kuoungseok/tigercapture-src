"""Real-project corpus helpers for conservative NLE readiness.

The generated QA corpus is useful for regression tests, but it is not evidence
that Tiger Studio can survive real long-form editing.  This module tracks real
user projects separately so readiness gates can distinguish product evidence
from synthetic fixtures.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "qa_corpus" / "nle_real_projects" / "manifest.json"
NLE_REAL_CORPUS_SCHEMA = "tigerstudio.nle.real_project_corpus.v1"
NLE_REAL_CORPUS_DISCOVERY_SCHEMA = "tigerstudio.nle.real_project_corpus.discovery.v1"
NLE_REAL_CORPUS_INTAKE_SCHEMA = "tigerstudio.nle.real_project_corpus.intake_board.v1"
NLE_REAL_CORPUS_COLLECTION_KIT_SCHEMA = "tigerstudio.nle.real_project_corpus.collection_kit.v1"
NLE_REAL_CORPUS_GATE_BOARD_SCHEMA = "tigerstudio.nle.real_project_corpus.gate_board.v1"
NLE_REAL_CORPUS_VALIDATION_PLAN_SCHEMA = "tigerstudio.nle.real_project_corpus.validation_plan.v1"
NLE_REAL_CORPUS_VALIDATION_EVIDENCE_SCHEMA = "tigerstudio.nle.real_project_corpus.validation_evidence.v1"
NLE_REAL_CORPUS_VALIDATION_REPORT_SCHEMA = "tigerstudio.nle.real_project_corpus.validation_report.v1"
NLE_REAL_CORPUS_VALIDATION_PACKET_SCHEMA = "tigerstudio.nle.real_project_corpus.validation_packet.v1"
NLE_REAL_CORPUS_VALIDATION_PREFLIGHT_SCHEMA = "tigerstudio.nle.real_project_corpus.validation_preflight.v1"
PROJECT_SUFFIXES = {".tgp", ".json"}
VALIDATION_CHECK_IDS = {
    "open_reopen",
    "scrub_sampling",
    "proxy_relink_health",
    "undo_recovery",
    "short_export",
    "nested_proxy_edge_cases",
}
VALIDATION_PASS_STATUSES = {"pass", "passed", "ok", "ready", "not_applicable"}
VALIDATION_FAIL_STATUSES = {"fail", "failed", "blocked", "error"}
DISCOVERY_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "debugcapture",
    "node_modules",
    "site-packages",
}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_path(path: str | Path) -> Path:
    row = Path(path)
    return row if row.is_absolute() else (ROOT / row)


def _default_discovery_roots() -> list[Path]:
    rows = [
        ROOT / "projects",
        ROOT / "qa_corpus" / "nle_real_projects",
    ]
    try:
        home = Path.home()
        rows.extend(
            [
                home / "Documents" / "TigerCapture",
                home / "Videos" / "TigerCapture",
            ]
        )
    except Exception:
        pass
    return rows


def _bounded_project_files(root: Path, *, max_depth: int = 5) -> list[Path]:
    root = _as_path(root)
    if root.is_file():
        return [root] if root.suffix.lower() in PROJECT_SUFFIXES else []
    if not root.exists() or not root.is_dir():
        return []
    base_depth = len(root.parts)
    rows: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        depth = max(0, len(current_path.parts) - base_depth)
        dirnames[:] = [
            name
            for name in dirnames
            if name.lower() not in DISCOVERY_SKIP_DIRS and depth < max(0, int(max_depth))
        ]
        for name in filenames:
            path = current_path / name
            if path.suffix.lower() in PROJECT_SUFFIXES:
                rows.append(path)
    return rows


def _walk_video_clips(clips: Sequence[Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for clip in clips or []:
        if not isinstance(clip, Mapping):
            continue
        rows.append(clip)
        for child in clip.get("nested_child_clips") or []:
            if isinstance(child, Mapping):
                rows.extend(_walk_video_clips([child]))
        for track in clip.get("nested_child_tracks") or []:
            if isinstance(track, Sequence):
                rows.extend(_walk_video_clips(track))
        for track in clip.get("nested_video_tracks") or []:
            if isinstance(track, Mapping):
                rows.extend(_walk_video_clips(track.get("clips") or []))
    return rows


def _walk_audio_clips(clips: Sequence[Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for clip in clips or []:
        if isinstance(clip, Mapping):
            rows.append(clip)
    return rows


def _clip_end_ms(clip: Mapping[str, Any]) -> int:
    start = _int(clip.get("timeline_in_ms", clip.get("offset_ms", clip.get("start_ms", 0))), 0)
    if "source_out_ms" in clip or "source_in_ms" in clip:
        duration = _int(clip.get("source_out_ms"), 0) - _int(clip.get("source_in_ms"), 0)
    elif "timeline_out_ms" in clip:
        return max(start, _int(clip.get("timeline_out_ms"), start))
    else:
        duration = _int(clip.get("duration_ms"), 0)
    return start + max(0, duration)


def _project_duration_ms(doc: Mapping[str, Any]) -> int:
    ends = [_int(doc.get("duration_ms"), 0)]
    for track in doc.get("video_tracks") or []:
        if isinstance(track, Mapping):
            ends.extend(_clip_end_ms(clip) for clip in _walk_video_clips(track.get("clips") or []))
    for track in doc.get("audio_tracks") or []:
        if isinstance(track, Mapping):
            ends.extend(_clip_end_ms(clip) for clip in _walk_audio_clips(track.get("clips") or []))
    return max(ends or [0])


def _media_paths(doc: Mapping[str, Any], *, base_dir: Path) -> list[str]:
    paths: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if not text:
            return
        if text.startswith("data:") or text.startswith("http://") or text.startswith("https://"):
            return
        paths.append(text)

    for item in doc.get("media_pool") or []:
        if isinstance(item, Mapping):
            for key in ("path", "source_path", "media_path", "file"):
                add(item.get(key))
    for track_key in ("video_tracks", "audio_tracks", "actor_tracks"):
        for track in doc.get(track_key) or []:
            if not isinstance(track, Mapping):
                continue
            for clip in _walk_video_clips(track.get("clips") or []):
                for key in ("path", "source_path", "media_path", "file", "audio_path"):
                    add(clip.get(key))
    unique: list[str] = []
    seen: set[str] = set()
    for value in paths:
        resolved = str((base_dir / value).resolve()) if not Path(value).is_absolute() else str(Path(value).resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _looks_generated_fixture(path: Path) -> bool:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    if "qa_corpus" in parts and "projects" in parts:
        return True
    return any(token in name for token in ("synthetic", "generated", "fixture", "stress_qa", "long_project_stress"))


def project_metrics(project_path: str | Path) -> dict[str, Any]:
    """Return read-only metrics for a Tiger Studio project-like JSON file."""

    path = _as_path(project_path)
    doc = _load_json(path)
    video_tracks = [track for track in list(doc.get("video_tracks") or []) if isinstance(track, Mapping)]
    audio_tracks = [track for track in list(doc.get("audio_tracks") or []) if isinstance(track, Mapping)]
    video_clips = [clip for track in video_tracks for clip in _walk_video_clips(track.get("clips") or [])]
    audio_clips = [clip for track in audio_tracks for clip in _walk_audio_clips(track.get("clips") or [])]
    media_paths = _media_paths(doc, base_dir=path.parent)
    missing = [row for row in media_paths if not Path(row).exists()]
    nested = sum(
        1
        for clip in video_clips
        if clip.get("nested_sequence_id") or clip.get("nested_child_tracks") or clip.get("nested_child_clips")
    )
    return {
        "schema": "tigerstudio.nle.project_metrics.v1",
        "path": str(path),
        "exists": path.exists(),
        "parse_ok": bool(doc),
        "project_name": str(doc.get("name") or doc.get("project_name") or path.stem),
        "duration_ms": _project_duration_ms(doc),
        "video_tracks": len(video_tracks),
        "video_clips": len(video_clips),
        "audio_tracks": len(audio_tracks),
        "audio_clips": len(audio_clips),
        "media_reference_count": len(media_paths),
        "missing_media_count": len(missing),
        "missing_media": missing[:20],
        "nested_sequence_count": nested,
        "generated_fixture_like": _looks_generated_fixture(path),
    }


def _project_like(metrics: Mapping[str, Any]) -> bool:
    return bool(metrics.get("parse_ok")) and (
        _int(metrics.get("duration_ms"), 0) > 0
        or _int(metrics.get("video_tracks"), 0) > 0
        or _int(metrics.get("audio_tracks"), 0) > 0
        or _int(metrics.get("video_clips"), 0) > 0
        or _int(metrics.get("audio_clips"), 0) > 0
    )


def _candidate_valid_for_corpus(
    metrics: Mapping[str, Any],
    *,
    min_project_duration_ms: int,
    allow_generated: bool,
) -> bool:
    generated = bool(metrics.get("generated_fixture_like"))
    return bool(
        metrics.get("exists")
        and _project_like(metrics)
        and (allow_generated or not generated)
        and _int(metrics.get("duration_ms"), 0) >= max(0, int(min_project_duration_ms))
        and (_int(metrics.get("video_clips"), 0) + _int(metrics.get("audio_clips"), 0)) >= 5
        and _int(metrics.get("missing_media_count"), 0) == 0
    )


def discover_nle_real_project_candidates(
    search_roots: Sequence[str | Path] | None = None,
    *,
    manifest_path: str | Path | None = None,
    max_results: int = 40,
    max_depth: int = 5,
    allow_generated: bool = False,
    min_project_duration_ms: int = 5 * 60_000,
) -> dict[str, Any]:
    """Find project-like files that can be registered as real NLE corpus evidence."""

    roots = [_as_path(row) for row in (search_roots or _default_discovery_roots()) if str(row or "").strip()]
    manifest = load_manifest(manifest_path or DEFAULT_MANIFEST_PATH)
    registered_paths = {
        str(_as_path(row.get("path") or "").resolve())
        for row in list(manifest.get("projects") or [])
        if isinstance(row, Mapping) and str(row.get("path") or "").strip()
    }
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    scanned_files = 0
    parseable_projects = 0
    for root in roots:
        for path in _bounded_project_files(root, max_depth=max_depth):
            resolved = str(path.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            scanned_files += 1
            metrics = project_metrics(path)
            if not _project_like(metrics):
                continue
            parseable_projects += 1
            generated = bool(metrics.get("generated_fixture_like"))
            already_registered = resolved in registered_paths
            valid_for_corpus = _candidate_valid_for_corpus(
                metrics,
                min_project_duration_ms=min_project_duration_ms,
                allow_generated=allow_generated,
            )
            warnings: list[str] = []
            if generated and not allow_generated:
                warnings.append("generated_fixture_rejected")
            if _int(metrics.get("missing_media_count"), 0) > 0:
                warnings.append("missing_media")
            if _int(metrics.get("duration_ms"), 0) < max(0, int(min_project_duration_ms)):
                warnings.append("too_short")
            if (_int(metrics.get("video_clips"), 0) + _int(metrics.get("audio_clips"), 0)) < 5:
                warnings.append("too_few_clips")
            if already_registered:
                warnings.append("already_registered")
            candidates.append(
                {
                    "path": resolved,
                    "label": str(metrics.get("project_name") or path.stem),
                    "already_registered": already_registered,
                    "valid_for_corpus": valid_for_corpus,
                    "would_register": bool(valid_for_corpus and not already_registered),
                    "warnings": warnings,
                    "metrics": metrics,
                }
            )
    candidates.sort(
        key=lambda row: (
            0 if row.get("would_register") else 1,
            0 if row.get("valid_for_corpus") else 1,
            -_int((row.get("metrics") or {}).get("duration_ms"), 0),
            -_int((row.get("metrics") or {}).get("video_clips"), 0),
            str(row.get("path") or ""),
        )
    )
    limited = candidates[: max(1, int(max_results))]
    report = build_nle_real_project_corpus_report(manifest_path=manifest_path or DEFAULT_MANIFEST_PATH)
    needed = {
        "projects": max(0, _int((report.get("thresholds") or {}).get("min_projects"), 3) - _int((report.get("summary") or {}).get("valid_project_count"), 0)),
        "validation_projects": max(0, _int((report.get("thresholds") or {}).get("min_projects"), 3) - _int((report.get("summary") or {}).get("validation_ready_count"), 0)),
        "duration_ms": max(0, _int((report.get("thresholds") or {}).get("min_duration_ms"), 30 * 60_000) - _int((report.get("summary") or {}).get("duration_ms"), 0)),
        "video_clips": max(0, _int((report.get("thresholds") or {}).get("min_total_video_clips"), 90) - _int((report.get("summary") or {}).get("video_clips"), 0)),
        "audio_clips": max(0, _int((report.get("thresholds") or {}).get("min_total_audio_clips"), 20) - _int((report.get("summary") or {}).get("audio_clips"), 0)),
    }
    return {
        "schema": NLE_REAL_CORPUS_DISCOVERY_SCHEMA,
        "ready": True,
        "manifest": str(_as_path(manifest_path or DEFAULT_MANIFEST_PATH)),
        "roots": [str(root) for root in roots],
        "scanned_files": scanned_files,
        "parseable_project_count": parseable_projects,
        "candidate_count": len(candidates),
        "shown_candidate_count": len(limited),
        "registerable_count": sum(1 for row in candidates if row.get("would_register")),
        "needed_for_claim": needed,
        "current_corpus": {
            "claim_ready": bool(report.get("claim_ready")),
            "summary": dict(report.get("summary") or {}),
            "blockers": list(report.get("blockers") or []),
        },
        "candidates": limited,
    }


def _candidate_board_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), Mapping) else {}
    would_register = bool(candidate.get("would_register"))
    row = {
        "path": str(candidate.get("path") or ""),
        "label": str(candidate.get("label") or ""),
        "would_register": would_register,
        "valid_for_corpus": bool(candidate.get("valid_for_corpus")),
        "already_registered": bool(candidate.get("already_registered")),
        "warnings": list(candidate.get("warnings") or []),
        "duration_ms": _int(metrics.get("duration_ms"), 0),
        "video_clips": _int(metrics.get("video_clips"), 0),
        "audio_clips": _int(metrics.get("audio_clips"), 0),
        "missing_media_count": _int(metrics.get("missing_media_count"), 0),
        "generated_fixture_like": bool(metrics.get("generated_fixture_like")),
    }
    if would_register:
        row["primary_action"] = {
            "id": "nle.real_corpus.register",
            "params": {
                "project_path": row["path"],
                "label": row["label"],
            },
        }
    return row


def build_nle_real_project_intake_board(
    search_roots: Sequence[str | Path] | None = None,
    *,
    manifest_path: str | Path | None = None,
    max_results: int = 20,
    max_depth: int = 5,
    allow_generated: bool = False,
) -> dict[str, Any]:
    """Build a UI-ready board for collecting real long-project NLE evidence.

    This intentionally does not clear the professional NLE claim gate.  It
    tells the app, local AI, and MCP clients which real projects can be
    registered, which candidates were rejected, and what thresholds remain.
    """

    manifest = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    status = build_nle_real_project_corpus_report(manifest_path=manifest)
    discovery = discover_nle_real_project_candidates(
        search_roots=search_roots,
        manifest_path=manifest,
        max_results=max(1, int(max_results)),
        max_depth=max(0, int(max_depth)),
        allow_generated=bool(allow_generated),
    )
    candidates = [row for row in list(discovery.get("candidates") or []) if isinstance(row, Mapping)]
    registerable = [row for row in candidates if bool(row.get("would_register"))]
    rejected = [row for row in candidates if not bool(row.get("would_register"))]
    summary = status.get("summary") if isinstance(status.get("summary"), Mapping) else {}
    thresholds = status.get("thresholds") if isinstance(status.get("thresholds"), Mapping) else {}
    needed = discovery.get("needed_for_claim") if isinstance(discovery.get("needed_for_claim"), Mapping) else {}
    registered_projects = [row for row in list(status.get("projects") or []) if isinstance(row, Mapping)]

    threshold_rows = [
        {
            "id": "projects",
            "label": "Real projects",
            "current": _int(summary.get("valid_project_count"), 0),
            "required": _int(thresholds.get("min_projects"), 3),
            "remaining": _int(needed.get("projects"), 0),
        },
        {
            "id": "duration_ms",
            "label": "Aggregate duration",
            "current": _int(summary.get("duration_ms"), 0),
            "required": _int(thresholds.get("min_duration_ms"), 30 * 60_000),
            "remaining": _int(needed.get("duration_ms"), 0),
        },
        {
            "id": "validation_projects",
            "label": "Validated real projects",
            "current": _int(summary.get("validation_ready_count"), 0),
            "required": _int(thresholds.get("min_projects"), 3),
            "remaining": _int(needed.get("validation_projects"), 0),
        },
        {
            "id": "video_clips",
            "label": "Video clips",
            "current": _int(summary.get("video_clips"), 0),
            "required": _int(thresholds.get("min_total_video_clips"), 90),
            "remaining": _int(needed.get("video_clips"), 0),
        },
        {
            "id": "audio_clips",
            "label": "Audio clips",
            "current": _int(summary.get("audio_clips"), 0),
            "required": _int(thresholds.get("min_total_audio_clips"), 20),
            "remaining": _int(needed.get("audio_clips"), 0),
        },
    ]
    sections = [
        {
            "id": "claim_gate",
            "title": "Professional NLE claim gate",
            "status": "ready" if bool(status.get("claim_ready")) else "blocked",
            "rows": threshold_rows,
            "blockers": list(status.get("blockers") or []),
        },
        {
            "id": "registerable_projects",
            "title": "Registerable real projects",
            "status": "ready" if registerable else "empty",
            "rows": [_candidate_board_row(row) for row in registerable],
        },
        {
            "id": "rejected_candidates",
            "title": "Rejected or incomplete candidates",
            "status": "warning" if rejected else "ok",
            "rows": [_candidate_board_row(row) for row in rejected[:10]],
        },
        {
            "id": "registered_projects",
            "title": "Registered corpus projects",
            "status": "ready" if registered_projects else "empty",
            "rows": [
                {
                    "id": str(row.get("id") or ""),
                    "label": str(row.get("label") or ""),
                    "path": str(row.get("path") or ""),
                    "valid": bool(row.get("valid")),
                    "duration_ms": _int((row.get("metrics") or {}).get("duration_ms"), 0) if isinstance(row.get("metrics"), Mapping) else 0,
                    "video_clips": _int((row.get("metrics") or {}).get("video_clips"), 0) if isinstance(row.get("metrics"), Mapping) else 0,
                    "audio_clips": _int((row.get("metrics") or {}).get("audio_clips"), 0) if isinstance(row.get("metrics"), Mapping) else 0,
                }
                for row in registered_projects
            ],
        },
    ]
    next_actions = []
    if registerable:
        next_actions.append("Register selected real projects, then rerun real corpus QA.")
    if not bool(status.get("claim_ready")):
        next_actions.append("Add at least three non-generated long projects with media present before claiming professional NLE parity.")
    if not candidates:
        next_actions.append("Point discovery at a folder containing saved Tiger Studio projects.")

    return {
        "schema": NLE_REAL_CORPUS_INTAKE_SCHEMA,
        "ready": True,
        "claim_ready": bool(status.get("claim_ready")),
        "manifest": str(manifest),
        "registerable_count": len(registerable),
        "candidate_count": _int(discovery.get("candidate_count"), len(candidates)),
        "shown_candidate_count": len(candidates),
        "needed_for_claim": dict(needed),
        "sections": sections,
        "commands": {
            "discover_enabled": True,
            "register_selected_enabled": bool(registerable),
            "run_corpus_qa_enabled": True,
            "open_project_folder_enabled": True,
        },
        "next_actions": next_actions,
        "discovery": {
            "roots": list(discovery.get("roots") or []),
            "scanned_files": _int(discovery.get("scanned_files"), 0),
            "parseable_project_count": _int(discovery.get("parseable_project_count"), 0),
            "registerable_count": _int(discovery.get("registerable_count"), 0),
        },
        "current_corpus": {
            "claim_ready": bool(status.get("claim_ready")),
            "summary": dict(summary),
            "blockers": list(status.get("blockers") or []),
        },
    }


def build_nle_real_project_collection_kit(
    search_roots: Sequence[str | Path] | None = None,
    *,
    manifest_path: str | Path | None = None,
    max_results: int = 20,
    max_depth: int = 5,
    allow_generated: bool = False,
) -> dict[str, Any]:
    """Return a UI/AI-ready kit for collecting real long-project NLE evidence.

    This is intentionally procedural.  It does not mark the corpus ready; it
    gives the editor, local AI, and MCP callers a safe route from discovery to
    registration to QA rerun without treating generated fixtures as product
    evidence.
    """

    intake = build_nle_real_project_intake_board(
        search_roots=search_roots,
        manifest_path=manifest_path,
        max_results=max(1, int(max_results)),
        max_depth=max(0, int(max_depth)),
        allow_generated=bool(allow_generated),
    )
    manifest = str(intake.get("manifest") or _as_path(manifest_path or DEFAULT_MANIFEST_PATH))
    sections = [row for row in list(intake.get("sections") or []) if isinstance(row, Mapping)]
    claim_gate = next((row for row in sections if row.get("id") == "claim_gate"), {})
    registerable_section = next((row for row in sections if row.get("id") == "registerable_projects"), {})
    rejected_section = next((row for row in sections if row.get("id") == "rejected_candidates"), {})
    threshold_rows = [dict(row) for row in list(claim_gate.get("rows") or []) if isinstance(row, Mapping)]
    registerable_rows = [dict(row) for row in list(registerable_section.get("rows") or []) if isinstance(row, Mapping)]
    rejected_rows = [dict(row) for row in list(rejected_section.get("rows") or []) if isinstance(row, Mapping)]
    validation = build_nle_real_project_validation_report(manifest_path=manifest)
    validation_summary = validation.get("summary") if isinstance(validation.get("summary"), Mapping) else {}
    validation_projects = [dict(row) for row in list(validation.get("projects") or []) if isinstance(row, Mapping)]
    validation_cli_examples = []
    for row in validation_projects[:5]:
        project_path = str(row.get("path") or "").strip()
        if not project_path:
            continue
        validation_cli_examples.append(
            {
                "project_id": str(row.get("id") or ""),
                "label": str(row.get("label") or Path(project_path).stem),
                "command": (
                    ".\\.venv\\Scripts\\python.exe tools\\register_nle_real_project_validation.py "
                    f"--project {json.dumps(project_path)} "
                    f"--manifest {json.dumps(manifest)} "
                    "--all-passed --operator qa"
                ),
            }
        )
    steps = [
        {
            "id": "save_real_projects",
            "label": "Save real Tiger Studio projects",
            "status": "required",
            "detail": "Use real user projects with source media present; generated QA fixtures do not count for the claim gate.",
        },
        {
            "id": "scan_project_roots",
            "label": "Scan project folders",
            "status": "ready",
            "action_id": "nle.real_corpus.discover",
        },
        {
            "id": "review_candidates",
            "label": "Review registerable and rejected candidates",
            "status": "ready",
            "action_id": "nle.real_corpus.intake_board",
        },
        {
            "id": "register_selected",
            "label": "Register selected real projects",
            "status": "ready" if registerable_rows else "waiting_for_candidates",
            "action_id": "nle.real_corpus.register",
        },
        {
            "id": "run_validation_plan",
            "label": "Run per-project validation checks",
            "status": "ready" if _int(validation_summary.get("valid_project_count"), 0) else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_plan",
        },
        {
            "id": "open_validation_packet",
            "label": "Open a project-specific validation packet",
            "status": "ready" if _int(validation_summary.get("valid_project_count"), 0) else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_packet",
        },
        {
            "id": "run_validation_preflight",
            "label": "Run machine preflight before recording evidence",
            "status": "ready" if _int(validation_summary.get("valid_project_count"), 0) else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_preflight",
        },
        {
            "id": "register_validation_evidence",
            "label": "Register redacted validation evidence",
            "status": "ready" if _int(validation_summary.get("valid_project_count"), 0) else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_evidence.register",
        },
        {
            "id": "review_validation_report",
            "label": "Review validation evidence status",
            "status": "ready",
            "action_id": "nle.real_corpus.validation_report",
        },
        {
            "id": "rerun_corpus_qa",
            "label": "Rerun real corpus QA",
            "status": "ready",
            "command": ".\\.venv\\Scripts\\python.exe tools\\qa_nle_real_project_corpus.py",
        },
        {
            "id": "rerun_nle_readiness",
            "label": "Rerun NLE readiness",
            "status": "ready",
            "command": ".\\.venv\\Scripts\\python.exe tools\\qa_nle_readiness.py --out debugCapture\\nle_readiness_qa.json",
        },
    ]
    action_sequence = [
        {
            "id": "nle.real_corpus.discover",
            "params": {
                "search_roots": [str(row) for row in (search_roots or ())],
                "manifest_path": manifest,
                "max_results": max(1, int(max_results)),
                "max_depth": max(0, int(max_depth)),
                "allow_generated": bool(allow_generated),
            },
        },
        {
            "id": "nle.real_corpus.intake_board",
            "params": {
                "search_roots": [str(row) for row in (search_roots or ())],
                "manifest_path": manifest,
                "max_results": max(1, int(max_results)),
                "max_depth": max(0, int(max_depth)),
                "allow_generated": bool(allow_generated),
            },
        },
        {
            "id": "timeline.professional_nle_readiness",
            "params": {},
        },
        {
            "id": "nle.real_corpus.validation_report",
            "params": {
                "manifest_path": manifest,
            },
        },
        {
            "id": "nle.real_corpus.validation_packet",
            "params": {
                "manifest_path": manifest,
            },
        },
        {
            "id": "nle.real_corpus.validation_preflight",
            "params": {
                "manifest_path": manifest,
            },
        },
    ]
    return {
        "schema": NLE_REAL_CORPUS_COLLECTION_KIT_SCHEMA,
        "ready": True,
        "claim_ready": bool(intake.get("claim_ready")),
        "manifest": manifest,
        "steps": steps,
        "thresholds": threshold_rows,
        "candidates": {
            "registerable_count": len(registerable_rows),
            "rejected_count": len(rejected_rows),
            "registerable_preview": registerable_rows[:5],
            "rejected_preview": rejected_rows[:5],
        },
        "validation": {
            "claim_ready": bool(validation.get("claim_ready")),
            "summary": dict(validation_summary),
            "blockers": list(validation.get("blockers") or []),
            "cli_examples": validation_cli_examples,
        },
        "commands": {
            "open_intake_board_enabled": True,
            "discover_enabled": True,
            "register_selected_enabled": bool(registerable_rows),
            "open_validation_plan_enabled": True,
            "open_validation_packet_enabled": _int(validation_summary.get("valid_project_count"), 0) > 0,
            "open_validation_preflight_enabled": _int(validation_summary.get("valid_project_count"), 0) > 0,
            "register_validation_evidence_enabled": _int(validation_summary.get("valid_project_count"), 0) > 0,
            "open_validation_report_enabled": True,
            "run_corpus_qa_enabled": True,
            "run_nle_readiness_enabled": True,
        },
        "action_sequence": action_sequence,
        "next_actions": list(intake.get("next_actions") or []),
        "readiness": {
            "collection_kit_ready": True,
            "real_corpus_claim_ready": bool(intake.get("claim_ready")),
            "validation_evidence_ready": bool(validation.get("claim_ready")),
            "validation_ready_count": _int(validation_summary.get("validation_ready_count"), 0),
            "requires_user_projects": not bool(intake.get("claim_ready")),
        },
    }


def build_nle_real_project_gate_board(
    search_roots: Sequence[str | Path] | None = None,
    *,
    manifest_path: str | Path | None = None,
    max_results: int = 20,
    max_depth: int = 5,
    allow_generated: bool = False,
) -> dict[str, Any]:
    """Return one claim-gate board for real long-project NLE evidence.

    This is the product-facing answer to "why is professional NLE claim still
    blocked?" It deliberately does not manufacture evidence; it combines corpus
    status, discovery, registration, validation, and rerun commands so the next
    human/agent step is unambiguous.
    """

    manifest = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    status = build_nle_real_project_corpus_report(manifest_path=manifest)
    intake = build_nle_real_project_intake_board(
        search_roots=search_roots,
        manifest_path=manifest,
        max_results=max(1, int(max_results)),
        max_depth=max(0, int(max_depth)),
        allow_generated=bool(allow_generated),
    )
    validation_plan = build_nle_real_project_validation_plan(manifest_path=manifest)
    validation_report = build_nle_real_project_validation_report(manifest_path=manifest)

    summary = status.get("summary") if isinstance(status.get("summary"), Mapping) else {}
    thresholds = status.get("thresholds") if isinstance(status.get("thresholds"), Mapping) else {}
    checks = status.get("checks") if isinstance(status.get("checks"), Mapping) else {}
    blockers = [str(row) for row in list(status.get("blockers") or [])]
    needed = intake.get("needed_for_claim") if isinstance(intake.get("needed_for_claim"), Mapping) else {}
    validation_summary = (
        validation_report.get("summary") if isinstance(validation_report.get("summary"), Mapping) else {}
    )
    plan_summary = validation_plan.get("summary") if isinstance(validation_plan.get("summary"), Mapping) else {}
    intake_sections = [
        row for row in list(intake.get("sections") or []) if isinstance(row, Mapping)
    ]
    registerable_section = next(
        (row for row in intake_sections if row.get("id") == "registerable_projects"),
        {},
    )
    rejected_section = next(
        (row for row in intake_sections if row.get("id") == "rejected_candidates"),
        {},
    )
    registerable_rows = [
        dict(row)
        for row in list(registerable_section.get("rows") or [])
        if isinstance(row, Mapping)
    ]
    rejected_rows = [
        dict(row)
        for row in list(rejected_section.get("rows") or [])
        if isinstance(row, Mapping)
    ]
    validation_projects = [
        dict(row)
        for row in list(validation_report.get("projects") or [])
        if isinstance(row, Mapping)
    ]
    validation_ready = [row for row in validation_projects if bool(row.get("validation_ready"))]
    validation_missing = [
        row
        for row in validation_projects
        if bool(row.get("valid_for_corpus")) and not bool(row.get("validation_ready"))
    ]

    threshold_rows = [
        {
            "id": "real_project_count",
            "label": "Real projects",
            "current": _int(summary.get("valid_project_count"), 0),
            "required": _int(thresholds.get("min_projects"), 3),
            "remaining": _int(needed.get("projects"), 0),
            "ok": bool(checks.get("real_project_count")),
        },
        {
            "id": "validation_evidence",
            "label": "Validated projects",
            "current": _int(summary.get("validation_ready_count"), 0),
            "required": _int(thresholds.get("min_projects"), 3),
            "remaining": _int(needed.get("validation_projects"), 0),
            "ok": bool(checks.get("validation_evidence")),
        },
        {
            "id": "aggregate_duration",
            "label": "Aggregate duration",
            "current": _int(summary.get("duration_ms"), 0),
            "required": _int(thresholds.get("min_duration_ms"), 30 * 60_000),
            "remaining": _int(needed.get("duration_ms"), 0),
            "ok": bool(checks.get("aggregate_duration")),
        },
        {
            "id": "aggregate_video_clips",
            "label": "Video clips",
            "current": _int(summary.get("video_clips"), 0),
            "required": _int(thresholds.get("min_total_video_clips"), 90),
            "remaining": _int(needed.get("video_clips"), 0),
            "ok": bool(checks.get("aggregate_video_clips")),
        },
        {
            "id": "aggregate_audio_clips",
            "label": "Audio clips",
            "current": _int(summary.get("audio_clips"), 0),
            "required": _int(thresholds.get("min_total_audio_clips"), 20),
            "remaining": _int(needed.get("audio_clips"), 0),
            "ok": bool(checks.get("aggregate_audio_clips")),
        },
        {
            "id": "no_missing_media",
            "label": "No missing media",
            "current": _int(summary.get("missing_media_count"), 0),
            "required": 0,
            "remaining": _int(summary.get("missing_media_count"), 0),
            "ok": bool(checks.get("no_missing_media")),
        },
    ]
    blocked_threshold_rows = [row for row in threshold_rows if not bool(row.get("ok"))]
    workflow_steps = [
        {
            "id": "discover",
            "label": "Scan folders for saved projects",
            "status": "ready",
            "action_id": "nle.real_corpus.discover",
        },
        {
            "id": "register",
            "label": "Register real user projects",
            "status": "ready" if registerable_rows else "waiting_for_candidates",
            "action_id": "nle.real_corpus.register",
        },
        {
            "id": "validate",
            "label": "Run open/scrub/proxy/undo/export checks",
            "status": "ready" if _int(plan_summary.get("ready_for_validation_count"), 0) else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_plan",
        },
        {
            "id": "validation_packet",
            "label": "Open the project validation packet",
            "status": "ready" if validation_missing else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_packet",
        },
        {
            "id": "validation_preflight",
            "label": "Check machine prerequisites before recording evidence",
            "status": "ready" if validation_missing else "waiting_for_registered_projects",
            "action_id": "nle.real_corpus.validation_preflight",
        },
        {
            "id": "register_validation_evidence",
            "label": "Register redacted validation evidence",
            "status": "ready" if validation_missing else "waiting_for_validation",
            "action_id": "nle.real_corpus.validation_evidence.register",
        },
        {
            "id": "rerun",
            "label": "Rerun NLE readiness QA",
            "status": "ready",
            "command": ".\\.venv\\Scripts\\python.exe tools\\qa_nle_readiness.py --out debugCapture\\nle_readiness_qa.json",
        },
    ]
    next_actions: list[str] = []
    if registerable_rows:
        next_actions.append("Register the listed real projects, then open the validation plan.")
    if validation_missing:
        next_actions.append("Complete validation checks and register redacted evidence for missing projects.")
    if not registerable_rows and _int(summary.get("valid_project_count"), 0) < _int(thresholds.get("min_projects"), 3):
        next_actions.append("Point discovery at folders containing saved real Tiger Studio projects.")
    if blockers:
        next_actions.append("Keep professional NLE marketing blocked until this board is claim_ready.")

    return {
        "schema": NLE_REAL_CORPUS_GATE_BOARD_SCHEMA,
        "ready": True,
        "claim_ready": bool(status.get("claim_ready")),
        "professional_nle_claim_blocked": not bool(status.get("claim_ready")),
        "manifest": str(manifest),
        "summary": {
            "registered_project_count": _int(summary.get("registered_project_count"), 0),
            "valid_project_count": _int(summary.get("valid_project_count"), 0),
            "validation_ready_count": _int(summary.get("validation_ready_count"), 0),
            "missing_validation_count": _int(validation_summary.get("missing_validation_count"), 0),
            "duration_ms": _int(summary.get("duration_ms"), 0),
            "video_clips": _int(summary.get("video_clips"), 0),
            "audio_clips": _int(summary.get("audio_clips"), 0),
            "missing_media_count": _int(summary.get("missing_media_count"), 0),
        },
        "sections": [
            {
                "id": "claim_gate",
                "title": "Professional NLE claim gate",
                "status": "ready" if bool(status.get("claim_ready")) else "blocked",
                "rows": threshold_rows,
                "blockers": blockers,
            },
            {
                "id": "blocked_requirements",
                "title": "Blocked requirements",
                "status": "warning" if blocked_threshold_rows else "ok",
                "rows": blocked_threshold_rows,
            },
            {
                "id": "registerable_projects",
                "title": "Registerable projects",
                "status": "ready" if registerable_rows else "empty",
                "rows": registerable_rows[:10],
            },
            {
                "id": "rejected_candidates",
                "title": "Rejected or incomplete candidates",
                "status": "warning" if rejected_rows else "ok",
                "rows": rejected_rows[:10],
            },
            {
                "id": "validation_missing",
                "title": "Needs validation evidence",
                "status": "warning" if validation_missing else "ok",
                "rows": validation_missing[:10],
            },
            {
                "id": "validation_ready",
                "title": "Validation ready",
                "status": "ready" if validation_ready else "empty",
                "rows": validation_ready[:10],
            },
            {
                "id": "workflow",
                "title": "Next workflow",
                "status": "ready",
                "rows": workflow_steps,
            },
        ],
        "commands": {
            "discover_enabled": True,
            "open_intake_board_enabled": True,
            "open_collection_kit_enabled": True,
            "register_selected_enabled": bool(registerable_rows),
            "open_validation_plan_enabled": True,
            "open_validation_packet_enabled": bool(validation_missing),
            "open_validation_preflight_enabled": bool(validation_missing),
            "register_validation_evidence_enabled": bool(validation_missing),
            "open_validation_report_enabled": True,
            "run_corpus_qa_enabled": True,
            "run_nle_readiness_enabled": True,
        },
        "action_sequence": [
            {
                "id": "nle.real_corpus.intake_board",
                "params": {
                    "search_roots": [str(row) for row in (search_roots or ())],
                    "manifest_path": str(manifest),
                    "max_results": max(1, int(max_results)),
                    "max_depth": max(0, int(max_depth)),
                    "allow_generated": bool(allow_generated),
                },
            },
            {
                "id": "nle.real_corpus.validation_plan",
                "params": {"manifest_path": str(manifest)},
            },
            {
                "id": "nle.real_corpus.validation_report",
                "params": {"manifest_path": str(manifest)},
            },
            {
                "id": "nle.real_corpus.validation_packet",
                "params": {"manifest_path": str(manifest)},
            },
            {
                "id": "nle.real_corpus.validation_preflight",
                "params": {"manifest_path": str(manifest)},
            },
            {
                "id": "timeline.professional_nle_readiness",
                "params": {},
            },
        ],
        "next_actions": next_actions,
        "readiness": {
            "gate_board_ready": True,
            "registration_workflow_ready": True,
            "validation_workflow_ready": True,
            "real_project_corpus_claim_ready": bool(status.get("claim_ready")),
            "requires_real_user_projects": not bool(status.get("claim_ready")),
        },
        "current_corpus": {
            "checks": dict(checks),
            "blockers": blockers,
            "summary": dict(summary),
        },
    }


def _validation_checks_for_metrics(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    duration_ms = _int(metrics.get("duration_ms"), 0)
    video_clips = _int(metrics.get("video_clips"), 0)
    audio_clips = _int(metrics.get("audio_clips"), 0)
    missing_media = _int(metrics.get("missing_media_count"), 0)
    nested_count = _int(metrics.get("nested_sequence_count"), 0)
    return [
        {
            "id": "open_reopen",
            "label": "Open and reopen project",
            "required": True,
            "status": "ready" if bool(metrics.get("exists")) and bool(metrics.get("parse_ok")) else "blocked",
            "evidence": {"parse_ok": bool(metrics.get("parse_ok"))},
        },
        {
            "id": "scrub_sampling",
            "label": "Scrub source/record/timeline sample points",
            "required": True,
            "status": "ready" if duration_ms >= 5 * 60_000 and video_clips >= 5 else "needs_longer_project",
            "sample_points_ms": [
                max(0, int(duration_ms * ratio))
                for ratio in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
            ],
        },
        {
            "id": "proxy_relink_health",
            "label": "Run proxy/relink/offline media health",
            "required": True,
            "status": "ready" if missing_media == 0 else "needs_relink",
            "evidence": {"missing_media_count": missing_media},
        },
        {
            "id": "undo_recovery",
            "label": "Run destructive-edit undo/recovery rehearsal",
            "required": True,
            "status": "ready" if video_clips + audio_clips >= 5 else "needs_more_clips",
            "action_id": "timeline.undo_recovery_playbook",
        },
        {
            "id": "short_export",
            "label": "Export representative review range",
            "required": True,
            "status": "ready" if duration_ms >= 60_000 else "needs_timeline_duration",
            "range_ms": [max(0, int(duration_ms * 0.4)), max(0, min(duration_ms, int(duration_ms * 0.4) + 30_000))],
        },
        {
            "id": "nested_proxy_edge_cases",
            "label": "Check nested/proxy edge cases",
            "required": nested_count > 0,
            "status": "ready" if nested_count > 0 else "not_applicable",
            "evidence": {"nested_sequence_count": nested_count},
        },
    ]


def _normalize_validation_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in VALIDATION_PASS_STATUSES:
        return "passed" if text != "not_applicable" else "not_applicable"
    if text in VALIDATION_FAIL_STATUSES:
        return "failed"
    if text in {"skip", "skipped"}:
        return "skipped"
    if text in {"pending", "todo", "waiting", ""}:
        return "pending"
    return "pending"


def _normalize_validation_checks(checks: Sequence[Any] | Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Normalize user/operator validation evidence by check id."""

    rows: list[Any]
    if isinstance(checks, Mapping):
        rows = [
            {"id": key, **(value if isinstance(value, Mapping) else {"status": value})}
            for key, value in checks.items()
        ]
    else:
        rows = list(checks or [])
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        check_id = str(row.get("id") or row.get("check_id") or "").strip()
        if check_id not in VALIDATION_CHECK_IDS:
            continue
        normalized[check_id] = {
            "id": check_id,
            "status": _normalize_validation_status(row.get("status")),
            "notes": str(row.get("notes") or row.get("note") or "").strip(),
            "artifact_path": str(row.get("artifact_path") or row.get("path") or "").strip(),
            "duration_ms": _int(row.get("duration_ms"), 0),
        }
    return normalized


def _validation_evidence_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    required = [row for row in rows if bool(row.get("required"))]
    passed = [row for row in required if str(row.get("status") or "") in {"passed", "not_applicable"}]
    failed = [row for row in required if str(row.get("status") or "") == "failed"]
    pending = [row for row in required if str(row.get("status") or "") == "pending"]
    skipped = [row for row in required if str(row.get("status") or "") == "skipped"]
    return {
        "required_count": len(required),
        "passed_required_count": len(passed),
        "failed_required_count": len(failed),
        "pending_required_count": len(pending),
        "skipped_required_count": len(skipped),
        "all_required_passed": bool(required) and len(passed) == len(required),
    }


def _validation_evidence_rows(metrics: Mapping[str, Any], checks: Mapping[str, Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    supplied = checks or {}
    rows: list[dict[str, Any]] = []
    for base in _validation_checks_for_metrics(metrics):
        check_id = str(base.get("id") or "")
        evidence = supplied.get(check_id) if isinstance(supplied.get(check_id), Mapping) else {}
        status = _normalize_validation_status(evidence.get("status") if evidence else None)
        if not bool(base.get("required")) and status == "pending":
            status = "not_applicable"
        rows.append(
            {
                "id": check_id,
                "label": str(base.get("label") or check_id),
                "required": bool(base.get("required")),
                "status": status,
                "notes": str(evidence.get("notes") or "").strip(),
                "artifact_path": str(evidence.get("artifact_path") or "").strip(),
                "duration_ms": _int(evidence.get("duration_ms"), 0),
                "expected_status": str(base.get("status") or ""),
            }
        )
    return rows


def _select_project_for_validation(
    projects: Sequence[Mapping[str, Any]],
    *,
    manifest_path: Path,
    project_id: str = "",
    project_path: str | Path | None = None,
) -> tuple[int, dict[str, Any] | None, bool]:
    """Find an explicit project or the next registered project needing validation."""

    index, entry = _find_manifest_project(projects, project_id=project_id, project_path=project_path)
    auto_selected = False
    if index >= 0 and entry is not None:
        return index, entry, auto_selected

    report = build_nle_real_project_validation_report(manifest_path=manifest_path)
    for row in list(report.get("projects") or []):
        if not isinstance(row, Mapping):
            continue
        if bool(row.get("valid_for_corpus")) and not bool(row.get("validation_ready")):
            index, entry = _find_manifest_project(projects, project_id=str(row.get("id") or ""))
            auto_selected = entry is not None
            if entry is not None:
                return index, entry, auto_selected

    for row in projects:
        if not isinstance(row, Mapping):
            continue
        index, entry = _find_manifest_project(projects, project_id=str(row.get("id") or ""))
        auto_selected = entry is not None
        if entry is not None:
            return index, entry, auto_selected
    return -1, None, auto_selected


def _machine_preflight_rows(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    duration_ms = _int(metrics.get("duration_ms"), 0)
    video_clips = _int(metrics.get("video_clips"), 0)
    audio_clips = _int(metrics.get("audio_clips"), 0)
    missing_media = _int(metrics.get("missing_media_count"), 0)
    total_clips = video_clips + audio_clips
    nested_count = _int(metrics.get("nested_sequence_count"), 0)
    return [
        {
            "id": "project_exists",
            "label": "Project file exists",
            "status": "pass" if bool(metrics.get("exists")) else "blocked",
            "evidence": {"path": str(metrics.get("path") or "")},
        },
        {
            "id": "parse_ok",
            "label": "Project can be parsed",
            "status": "pass" if bool(metrics.get("parse_ok")) else "blocked",
        },
        {
            "id": "not_generated_fixture",
            "label": "Not a generated QA fixture",
            "status": "pass" if not bool(metrics.get("generated_fixture_like")) else "blocked",
        },
        {
            "id": "no_missing_media",
            "label": "No missing media references",
            "status": "pass" if missing_media == 0 else "blocked",
            "evidence": {"missing_media_count": missing_media},
        },
        {
            "id": "min_duration",
            "label": "Long enough for scrub/export validation",
            "status": "pass" if duration_ms >= 5 * 60_000 else "blocked",
            "evidence": {"duration_ms": duration_ms, "minimum_ms": 5 * 60_000},
        },
        {
            "id": "min_clip_count",
            "label": "Enough clips for undo/edit validation",
            "status": "pass" if total_clips >= 5 else "blocked",
            "evidence": {"video_clips": video_clips, "audio_clips": audio_clips, "minimum_total_clips": 5},
        },
        {
            "id": "scrub_sample_plan_ready",
            "label": "Scrub sample points can be generated",
            "status": "pass" if duration_ms >= 5 * 60_000 and video_clips >= 5 else "blocked",
            "sample_points_ms": [
                max(0, int(duration_ms * ratio))
                for ratio in (0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0)
            ],
        },
        {
            "id": "short_export_range_ready",
            "label": "Representative short export range can be generated",
            "status": "pass" if duration_ms >= 60_000 else "blocked",
            "range_ms": [max(0, int(duration_ms * 0.4)), max(0, min(duration_ms, int(duration_ms * 0.4) + 30_000))],
        },
        {
            "id": "nested_check_applicable",
            "label": "Nested/proxy edge-case check applicability",
            "status": "pass" if nested_count > 0 else "not_applicable",
            "evidence": {"nested_sequence_count": nested_count},
        },
    ]


def build_nle_real_project_validation_preflight(
    *,
    project_id: str = "",
    project_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return machine checks before an operator records real-project evidence.

    This is intentionally not proof. It only says whether the project is ready
    for human validation, then provides a pending evidence template.
    """

    manifest_path = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    projects = [dict(row) for row in manifest.get("projects") or [] if isinstance(row, Mapping)]
    index, entry, auto_selected = _select_project_for_validation(
        projects,
        manifest_path=manifest_path,
        project_id=project_id,
        project_path=project_path,
    )
    if index < 0 or entry is None:
        return {
            "schema": NLE_REAL_CORPUS_VALIDATION_PREFLIGHT_SCHEMA,
            "ready": False,
            "ok": False,
            "reason": "no_registered_project",
            "manifest": str(manifest_path),
            "machine_checks": [],
            "operator_checks": [],
            "commands": {
                "open_intake_board_enabled": True,
                "register_project_enabled": True,
                "register_validation_evidence_enabled": False,
            },
            "readiness": {
                "validation_preflight_ready": False,
                "machine_preflight_passed": False,
                "operator_evidence_required": True,
            },
        }

    metrics = project_metrics(_as_path(entry.get("path") or ""))
    machine_rows = _machine_preflight_rows(metrics)
    machine_blockers = [
        str(row.get("id") or "")
        for row in machine_rows
        if str(row.get("status") or "") == "blocked"
    ]
    machine_passed = not machine_blockers
    base_checks = _validation_checks_for_metrics(metrics)
    operator_rows: list[dict[str, Any]] = []
    for row in base_checks:
        check_id = str(row.get("id") or "")
        required = bool(row.get("required"))
        if not required:
            status = "ready_for_operator" if str(row.get("status") or "") == "ready" else "not_applicable"
        else:
            status = "ready_for_operator" if machine_passed and str(row.get("status") or "") == "ready" else "blocked"
        operator_rows.append(
            {
                "id": check_id,
                "label": str(row.get("label") or check_id),
                "required": required,
                "status": status,
                "expected_machine_status": str(row.get("status") or ""),
                "sample_points_ms": list(row.get("sample_points_ms") or []),
                "range_ms": list(row.get("range_ms") or []),
            }
        )
    template_checks = [
        {
            "id": str(row.get("id") or ""),
            "status": "pending",
            "notes": "",
            "artifact_path": "",
        }
        for row in operator_rows
        if bool(row.get("required"))
    ]
    return {
        "schema": NLE_REAL_CORPUS_VALIDATION_PREFLIGHT_SCHEMA,
        "ready": True,
        "ok": True,
        "manifest": str(manifest_path),
        "auto_selected": auto_selected,
        "project": {
            "id": str(entry.get("id") or ""),
            "label": str(entry.get("label") or metrics.get("project_name") or ""),
            "path": str(entry.get("path") or ""),
        },
        "summary": {
            "machine_preflight_passed": machine_passed,
            "machine_blockers": machine_blockers,
            "operator_required_count": sum(1 for row in operator_rows if bool(row.get("required"))),
            "operator_ready_count": sum(1 for row in operator_rows if str(row.get("status") or "") == "ready_for_operator"),
            "operator_evidence_required": True,
        },
        "machine_checks": machine_rows,
        "operator_checks": operator_rows,
        "suggested_validation_checks": template_checks,
        "sections": [
            {
                "id": "machine_checks",
                "title": "Machine preflight checks",
                "status": "ready" if machine_passed else "blocked",
                "rows": machine_rows,
            },
            {
                "id": "operator_checks",
                "title": "Operator validation checks",
                "status": "ready" if machine_passed else "blocked",
                "rows": operator_rows,
            },
        ],
        "commands": {
            "open_validation_packet_enabled": True,
            "register_validation_evidence_enabled": machine_passed,
            "run_corpus_qa_enabled": True,
            "run_nle_readiness_enabled": True,
        },
        "action_template": {
            "id": "nle.real_corpus.validation_evidence.register",
            "params": {
                "project_id": str(entry.get("id") or ""),
                "project_path": str(entry.get("path") or ""),
                "manifest_path": str(manifest_path),
                "checks": template_checks,
                "operator": "qa",
                "notes": "",
                "evidence_path": "",
            },
            "requires_operator_review": True,
        },
        "readiness": {
            "validation_preflight_ready": True,
            "project_registered": True,
            "machine_preflight_passed": machine_passed,
            "operator_evidence_required": True,
            "safe_to_register_after_operator_review": machine_passed,
        },
        "next_actions": [
            "Fix machine blockers before manual validation." if not machine_passed else "Run the operator checks on the real project.",
            "Only change pending checks to passed after the result was actually observed.",
            "Register redacted validation evidence, then rerun real corpus QA.",
        ],
    }


def build_nle_real_project_validation_plan(
    *,
    manifest_path: str | Path | None = None,
    min_projects: int = 3,
    min_duration_ms: int = 30 * 60_000,
    min_total_video_clips: int = 90,
    min_total_audio_clips: int = 20,
) -> dict[str, Any]:
    """Return a UI-ready plan for validating registered real NLE projects."""

    status = build_nle_real_project_corpus_report(
        manifest_path=manifest_path,
        min_projects=min_projects,
        min_duration_ms=min_duration_ms,
        min_total_video_clips=min_total_video_clips,
        min_total_audio_clips=min_total_audio_clips,
    )
    project_rows: list[dict[str, Any]] = []
    for project in list(status.get("projects") or []):
        if not isinstance(project, Mapping):
            continue
        metrics = project.get("metrics") if isinstance(project.get("metrics"), Mapping) else {}
        checks = _validation_checks_for_metrics(metrics)
        required = [row for row in checks if bool(row.get("required"))]
        blocked = [
            row
            for row in required
            if str(row.get("status") or "") not in {"ready", "not_applicable"}
        ]
        project_rows.append(
            {
                "id": str(project.get("id") or ""),
                "label": str(project.get("label") or ""),
                "path": str(project.get("path") or ""),
                "valid_for_corpus": bool(project.get("valid")),
                "ready_for_validation": bool(project.get("valid")) and not blocked,
                "checks": checks,
                "blocked_check_count": len(blocked),
                "metrics": {
                    "duration_ms": _int(metrics.get("duration_ms"), 0),
                    "video_clips": _int(metrics.get("video_clips"), 0),
                    "audio_clips": _int(metrics.get("audio_clips"), 0),
                    "missing_media_count": _int(metrics.get("missing_media_count"), 0),
                    "nested_sequence_count": _int(metrics.get("nested_sequence_count"), 0),
                },
            }
        )
    ready_projects = [row for row in project_rows if bool(row.get("ready_for_validation"))]
    blocked_projects = [row for row in project_rows if not bool(row.get("ready_for_validation"))]
    return {
        "schema": NLE_REAL_CORPUS_VALIDATION_PLAN_SCHEMA,
        "ready": True,
        "claim_ready": bool(status.get("claim_ready")),
        "manifest": str(status.get("manifest") or _as_path(manifest_path or DEFAULT_MANIFEST_PATH)),
        "summary": {
            "registered_project_count": _int((status.get("summary") or {}).get("registered_project_count"), 0),
            "valid_project_count": _int((status.get("summary") or {}).get("valid_project_count"), 0),
            "ready_for_validation_count": len(ready_projects),
            "blocked_project_count": len(blocked_projects),
            "blockers": list(status.get("blockers") or []),
        },
        "sections": [
            {
                "id": "ready_projects",
                "title": "Ready for validation",
                "status": "ready" if ready_projects else "empty",
                "rows": ready_projects,
            },
            {
                "id": "blocked_projects",
                "title": "Needs repair before validation",
                "status": "warning" if blocked_projects else "ok",
                "rows": blocked_projects,
            },
            {
                "id": "manual_qa_steps",
                "title": "Manual validation steps",
                "status": "ready",
                "rows": [
                    {"id": "open_reopen", "label": "Open, save, close, and reopen each project."},
                    {"id": "scrub", "label": "Scrub 7 timeline sample points and verify preview/audio stays responsive."},
                    {"id": "proxy_relink", "label": "Run proxy/relink health and resolve missing media before export."},
                    {"id": "undo", "label": "Perform split/trim/ripple/delete then undo/redo and reopen recovery copy."},
                    {"id": "export", "label": "Export a representative 30s review range and compare duration/frame health."},
                ],
            },
        ],
        "commands": {
            "open_project_enabled": bool(project_rows),
            "run_proxy_relink_health_enabled": bool(project_rows),
            "run_undo_recovery_playbook_enabled": True,
            "run_short_export_enabled": bool(ready_projects),
            "rerun_real_corpus_qa_enabled": True,
            "rerun_nle_readiness_enabled": True,
        },
        "readiness": {
            "validation_plan_ready": True,
            "has_registered_projects": bool(project_rows),
            "has_ready_projects": bool(ready_projects),
            "real_corpus_claim_ready": bool(status.get("claim_ready")),
        },
    }


def _find_manifest_project(
    projects: Sequence[Mapping[str, Any]],
    *,
    project_id: str = "",
    project_path: str | Path | None = None,
) -> tuple[int, dict[str, Any]] | tuple[int, None]:
    resolved_path = ""
    if project_path and str(project_path).strip():
        try:
            resolved_path = str(_as_path(project_path).resolve())
        except Exception:
            resolved_path = str(project_path)
    wanted_id = str(project_id or "").strip()
    for index, row in enumerate(projects):
        if not isinstance(row, Mapping):
            continue
        row_id = str(row.get("id") or "")
        row_path = str(row.get("path") or "")
        try:
            row_path = str(_as_path(row_path).resolve()) if row_path else ""
        except Exception:
            pass
        if wanted_id and row_id == wanted_id:
            return index, dict(row)
        if resolved_path and row_path == resolved_path:
            return index, dict(row)
    return -1, None


def preview_nle_real_project_validation_evidence(
    *,
    project_id: str = "",
    project_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    checks: Sequence[Any] | Mapping[str, Any] | None = None,
    notes: str = "",
    operator: str = "",
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return the validation evidence payload that would be written."""

    manifest_path = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    projects = [dict(row) for row in manifest.get("projects") or [] if isinstance(row, Mapping)]
    index, entry = _find_manifest_project(projects, project_id=project_id, project_path=project_path)
    if index < 0 or entry is None:
        return {
            "ok": False,
            "schema": NLE_REAL_CORPUS_VALIDATION_EVIDENCE_SCHEMA,
            "reason": "project_not_registered",
            "manifest": str(manifest_path),
            "project_id": str(project_id or ""),
            "project_path": str(project_path or ""),
        }
    metrics = project_metrics(_as_path(entry.get("path") or ""))
    normalized = _normalize_validation_checks(checks)
    rows = _validation_evidence_rows(metrics, normalized)
    summary = _validation_evidence_summary(rows)
    evidence = {
        "schema": NLE_REAL_CORPUS_VALIDATION_EVIDENCE_SCHEMA,
        "updated_at": _now_iso(),
        "project_id": str(entry.get("id") or ""),
        "project_path": str(entry.get("path") or ""),
        "operator": str(operator or "").strip(),
        "notes": str(notes or "").strip(),
        "evidence_path": str(evidence_path or "").strip(),
        "checks": rows,
        "summary": summary,
        "status": "passed" if bool(summary.get("all_required_passed")) else "incomplete",
    }
    return {
        "ok": True,
        "schema": NLE_REAL_CORPUS_VALIDATION_EVIDENCE_SCHEMA,
        "manifest": str(manifest_path),
        "project": {
            "id": str(entry.get("id") or ""),
            "label": str(entry.get("label") or metrics.get("project_name") or ""),
            "path": str(entry.get("path") or ""),
            "valid": bool(
                metrics.get("exists")
                and metrics.get("parse_ok")
                and not bool(metrics.get("generated_fixture_like"))
                and _int(metrics.get("missing_media_count"), 0) == 0
            ),
        },
        "would_write": evidence,
    }


def register_nle_real_project_validation_evidence(
    *,
    project_id: str = "",
    project_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    checks: Sequence[Any] | Mapping[str, Any] | None = None,
    notes: str = "",
    operator: str = "",
    evidence_path: str | Path | None = None,
) -> dict[str, Any]:
    """Attach redacted validation evidence to a registered real corpus project."""

    preview = preview_nle_real_project_validation_evidence(
        project_id=project_id,
        project_path=project_path,
        manifest_path=manifest_path,
        checks=checks,
        notes=notes,
        operator=operator,
        evidence_path=evidence_path,
    )
    if not bool(preview.get("ok")):
        return preview
    manifest_path = _as_path(preview.get("manifest") or manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    projects = [dict(row) for row in manifest.get("projects") or [] if isinstance(row, Mapping)]
    project = preview.get("project") if isinstance(preview.get("project"), Mapping) else {}
    index, entry = _find_manifest_project(
        projects,
        project_id=str(project.get("id") or project_id or ""),
        project_path=str(project.get("path") or project_path or ""),
    )
    if index < 0 or entry is None:
        return {
            "ok": False,
            "schema": NLE_REAL_CORPUS_VALIDATION_EVIDENCE_SCHEMA,
            "reason": "project_not_registered",
            "manifest": str(manifest_path),
        }
    entry["validation_evidence"] = dict(preview.get("would_write") or {})
    projects[index] = entry
    payload = {
        "schema": NLE_REAL_CORPUS_SCHEMA,
        "updated_at": _now_iso(),
        "projects": projects,
    }
    _write_json(manifest_path, payload)
    return {
        "ok": True,
        "schema": NLE_REAL_CORPUS_VALIDATION_EVIDENCE_SCHEMA,
        "manifest": str(manifest_path),
        "project": {
            "id": str(entry.get("id") or ""),
            "label": str(entry.get("label") or ""),
            "path": str(entry.get("path") or ""),
        },
        "validation_evidence": dict(entry.get("validation_evidence") or {}),
    }


def build_nle_real_project_validation_report(
    *,
    manifest_path: str | Path | None = None,
    min_projects: int = 3,
) -> dict[str, Any]:
    """Summarize registered real-project validation evidence.

    This report is separate from the metric-only corpus gate. It makes the
    remaining real-world blocker operational by showing whether registered
    projects have completed the required open/scrub/proxy/undo/export checks.
    """

    manifest_path = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    corpus = build_nle_real_project_corpus_report(
        manifest_path=manifest_path,
        min_projects=min_projects,
        require_validation_evidence=False,
    )
    manifest_by_id = {
        str(row.get("id") or ""): dict(row)
        for row in list(manifest.get("projects") or [])
        if isinstance(row, Mapping)
    }
    project_rows: list[dict[str, Any]] = []
    for project in list(corpus.get("projects") or []):
        if not isinstance(project, Mapping):
            continue
        entry = manifest_by_id.get(str(project.get("id") or ""), {})
        metrics = project.get("metrics") if isinstance(project.get("metrics"), Mapping) else {}
        evidence = entry.get("validation_evidence") if isinstance(entry.get("validation_evidence"), Mapping) else {}
        supplied = _normalize_validation_checks(evidence.get("checks") if isinstance(evidence, Mapping) else None)
        rows = _validation_evidence_rows(metrics, supplied)
        summary = _validation_evidence_summary(rows)
        validation_ready = bool(project.get("valid")) and bool(summary.get("all_required_passed"))
        project_rows.append(
            {
                "id": str(project.get("id") or ""),
                "label": str(project.get("label") or ""),
                "path": str(project.get("path") or ""),
                "valid_for_corpus": bool(project.get("valid")),
                "validation_ready": validation_ready,
                "evidence_status": str(evidence.get("status") or ("passed" if validation_ready else "missing")),
                "summary": summary,
                "checks": rows,
                "updated_at": str(evidence.get("updated_at") or ""),
            }
        )
    ready = [row for row in project_rows if bool(row.get("validation_ready"))]
    missing = [
        row
        for row in project_rows
        if bool(row.get("valid_for_corpus")) and not bool(row.get("validation_ready"))
    ]
    failed_count = sum(
        _int((row.get("summary") or {}).get("failed_required_count"), 0)
        for row in project_rows
        if isinstance(row.get("summary"), Mapping)
    )
    validation_claim_ready = bool(corpus.get("claim_ready")) and len(ready) >= max(1, int(min_projects)) and failed_count == 0
    blockers: list[str] = list(corpus.get("blockers") or [])
    if len(ready) < max(1, int(min_projects)):
        blockers.append("validation_evidence_count")
    if failed_count:
        blockers.append("validation_failed_checks")
    return {
        "schema": NLE_REAL_CORPUS_VALIDATION_REPORT_SCHEMA,
        "ready": True,
        "claim_ready": validation_claim_ready,
        "metric_corpus_claim_ready": bool(corpus.get("claim_ready")),
        "manifest": str(manifest_path),
        "summary": {
            "registered_project_count": _int((corpus.get("summary") or {}).get("registered_project_count"), 0),
            "valid_project_count": _int((corpus.get("summary") or {}).get("valid_project_count"), 0),
            "validation_ready_count": len(ready),
            "missing_validation_count": len(missing),
            "failed_required_check_count": failed_count,
            "min_projects": max(1, int(min_projects)),
        },
        "projects": project_rows,
        "sections": [
            {
                "id": "validation_ready",
                "title": "Validation ready projects",
                "status": "ready" if ready else "empty",
                "rows": ready,
            },
            {
                "id": "missing_or_incomplete",
                "title": "Missing or incomplete validation",
                "status": "warning" if missing else "ok",
                "rows": missing,
            },
        ],
        "commands": {
            "register_validation_evidence_enabled": True,
            "rerun_real_corpus_qa_enabled": True,
            "rerun_nle_readiness_enabled": True,
        },
        "blockers": blockers,
    }


def build_nle_real_project_validation_packet(
    *,
    project_id: str = "",
    project_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> dict[str, Any]:
    """Return a project-specific operator packet for real NLE validation.

    The packet is a guided form, not proof. It never marks checks as passed by
    itself; it gives UI/AI/MCP callers a concrete checklist plus copyable action
    and CLI templates for registering redacted evidence after the operator has
    actually run the checks.
    """

    manifest_path = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    projects = [dict(row) for row in manifest.get("projects") or [] if isinstance(row, Mapping)]
    index, entry, auto_selected = _select_project_for_validation(
        projects,
        manifest_path=manifest_path,
        project_id=project_id,
        project_path=project_path,
    )
    if index < 0 or entry is None:
        return {
            "schema": NLE_REAL_CORPUS_VALIDATION_PACKET_SCHEMA,
            "ready": False,
            "ok": False,
            "reason": "no_registered_project",
            "manifest": str(manifest_path),
            "sections": [],
            "commands": {
                "open_intake_board_enabled": True,
                "register_project_enabled": True,
                "register_validation_evidence_enabled": False,
            },
            "next_actions": [
                "Register at least one real Tiger Studio project before creating a validation packet.",
            ],
        }

    metrics = project_metrics(_as_path(entry.get("path") or ""))
    validation = entry.get("validation_evidence") if isinstance(entry.get("validation_evidence"), Mapping) else {}
    supplied = _normalize_validation_checks(validation.get("checks") if isinstance(validation, Mapping) else None)
    rows = _validation_evidence_rows(metrics, supplied)
    summary = _validation_evidence_summary(rows)
    valid_for_corpus = bool(
        metrics.get("exists")
        and metrics.get("parse_ok")
        and not bool(metrics.get("generated_fixture_like"))
        and _int(metrics.get("missing_media_count"), 0) == 0
        and _int(metrics.get("duration_ms"), 0) >= 5 * 60_000
        and (_int(metrics.get("video_clips"), 0) + _int(metrics.get("audio_clips"), 0)) >= 5
    )
    required_rows = [row for row in rows if bool(row.get("required"))]
    optional_rows = [row for row in rows if not bool(row.get("required"))]
    pending_required = [row for row in required_rows if str(row.get("status") or "") != "passed"]
    template_checks = [
        {
            "id": str(row.get("id") or ""),
            "status": "pending",
            "notes": "",
            "artifact_path": "",
        }
        for row in required_rows
    ]
    include_nested = any(row.get("id") == "nested_proxy_edge_cases" and bool(row.get("required")) for row in rows)
    cli_command = (
        ".\\.venv\\Scripts\\python.exe tools\\register_nle_real_project_validation.py "
        f"--project {json.dumps(str(entry.get('path') or ''))} "
        f"--manifest {json.dumps(str(manifest_path))} "
        "--all-passed --operator qa"
    )
    if include_nested:
        cli_command += " --include-nested"

    redaction_rules = [
        "Do not include private source media, stream keys, customer names, or account identifiers.",
        "Evidence notes should describe pass/fail behavior and artifact type, not expose private timeline content.",
        "Use redacted screenshot/report paths only when the artifact can be regenerated or safely shared.",
    ]
    manual_steps = [
        {
            "id": "open_reopen",
            "label": "Open, save, close, and reopen the project.",
            "required": True,
        },
        {
            "id": "scrub_sampling",
            "label": "Scrub the generated sample points and verify preview/audio responsiveness.",
            "required": True,
            "sample_points_ms": next(
                (list(row.get("sample_points_ms") or []) for row in _validation_checks_for_metrics(metrics) if row.get("id") == "scrub_sampling"),
                [],
            ),
        },
        {
            "id": "proxy_relink_health",
            "label": "Run proxy/relink health and confirm missing media is resolved.",
            "required": True,
        },
        {
            "id": "undo_recovery",
            "label": "Run split/trim/ripple/delete then undo/redo and reopen recovery checks.",
            "required": True,
        },
        {
            "id": "short_export",
            "label": "Export a representative 30s range and confirm duration/frame health.",
            "required": True,
        },
    ]
    if include_nested:
        manual_steps.append(
            {
                "id": "nested_proxy_edge_cases",
                "label": "Validate nested/proxy edge cases for this project.",
                "required": False,
            }
        )

    return {
        "schema": NLE_REAL_CORPUS_VALIDATION_PACKET_SCHEMA,
        "ready": True,
        "ok": True,
        "manifest": str(manifest_path),
        "auto_selected": auto_selected,
        "project": {
            "id": str(entry.get("id") or ""),
            "label": str(entry.get("label") or metrics.get("project_name") or ""),
            "path": str(entry.get("path") or ""),
            "valid_for_corpus": valid_for_corpus,
        },
        "summary": {
            "all_required_passed": bool(summary.get("all_required_passed")),
            "required_count": _int(summary.get("required_count"), 0),
            "passed_required_count": _int(summary.get("passed_required_count"), 0),
            "pending_required_count": _int(summary.get("pending_required_count"), 0),
            "failed_required_count": _int(summary.get("failed_required_count"), 0),
            "pending_required_ids": [str(row.get("id") or "") for row in pending_required],
        },
        "sections": [
            {
                "id": "project_metrics",
                "title": "Project metrics",
                "status": "ready" if valid_for_corpus else "blocked",
                "rows": [
                    {"id": "duration_ms", "value": _int(metrics.get("duration_ms"), 0)},
                    {"id": "video_clips", "value": _int(metrics.get("video_clips"), 0)},
                    {"id": "audio_clips", "value": _int(metrics.get("audio_clips"), 0)},
                    {"id": "missing_media_count", "value": _int(metrics.get("missing_media_count"), 0)},
                ],
            },
            {
                "id": "required_checks",
                "title": "Required validation checks",
                "status": "ready" if valid_for_corpus else "blocked",
                "rows": required_rows,
            },
            {
                "id": "optional_checks",
                "title": "Optional validation checks",
                "status": "ready",
                "rows": optional_rows,
            },
            {
                "id": "manual_steps",
                "title": "Operator steps",
                "status": "ready",
                "rows": manual_steps,
            },
            {
                "id": "redaction_rules",
                "title": "Redaction rules",
                "status": "required",
                "rows": [{"id": f"rule_{index + 1}", "label": rule} for index, rule in enumerate(redaction_rules)],
            },
        ],
        "commands": {
            "register_validation_evidence_enabled": valid_for_corpus,
            "open_validation_report_enabled": True,
            "run_corpus_qa_enabled": True,
            "run_nle_readiness_enabled": True,
        },
        "action_template": {
            "id": "nle.real_corpus.validation_evidence.register",
            "params": {
                "project_id": str(entry.get("id") or ""),
                "project_path": str(entry.get("path") or ""),
                "manifest_path": str(manifest_path),
                "checks": template_checks,
                "operator": "qa",
                "notes": "",
                "evidence_path": "",
            },
            "requires_operator_review": True,
        },
        "cli_template": {
            "command": cli_command,
            "requires_operator_review": True,
        },
        "readiness": {
            "validation_packet_ready": True,
            "project_registered": True,
            "project_valid_for_corpus": valid_for_corpus,
            "evidence_complete": bool(summary.get("all_required_passed")),
            "safe_to_register_after_operator_checks": valid_for_corpus,
        },
        "next_actions": [
            "Run the required checks manually on the real project.",
            "Edit the action template statuses/notes to match actual results.",
            "Register redacted validation evidence, then rerun real corpus QA.",
        ],
    }


def load_manifest(path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = _as_path(path or DEFAULT_MANIFEST_PATH)
    payload = _load_json(manifest_path)
    projects = payload.get("projects") if isinstance(payload.get("projects"), list) else []
    return {
        "schema": NLE_REAL_CORPUS_SCHEMA,
        "updated_at": str(payload.get("updated_at") or ""),
        "projects": [row for row in projects if isinstance(row, Mapping)],
    }


def register_real_project(
    project_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
    label: str = "",
    notes: str = "",
    allow_generated: bool = False,
) -> dict[str, Any]:
    """Register a real project for NLE corpus QA.

    Generated fixtures are rejected by default so the release gate cannot be
    accidentally satisfied by the QA corpus.
    """

    path = _as_path(project_path)
    metrics = project_metrics(path)
    generated = bool(metrics.get("generated_fixture_like"))
    if generated and not allow_generated:
        return {
            "ok": False,
            "schema": NLE_REAL_CORPUS_SCHEMA,
            "reason": "generated_fixture_rejected",
            "project": str(path),
            "metrics": metrics,
        }

    manifest_path = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    resolved = str(path.resolve())
    row_id = "real_" + hashlib.sha1(resolved.encode("utf-8", errors="ignore")).hexdigest()[:12]
    entry = {
        "id": row_id,
        "path": resolved,
        "label": label or metrics.get("project_name") or path.stem,
        "notes": notes,
        "source_kind": "generated_fixture" if generated else "real_user_project",
        "registered_at": _now_iso(),
        "metrics": metrics,
    }
    projects = [dict(row) for row in manifest.get("projects") or [] if str(row.get("path") or "") != resolved]
    projects.append(entry)
    payload = {
        "schema": NLE_REAL_CORPUS_SCHEMA,
        "updated_at": _now_iso(),
        "projects": projects,
    }
    _write_json(manifest_path, payload)
    return {
        "ok": True,
        "schema": NLE_REAL_CORPUS_SCHEMA,
        "manifest": str(manifest_path),
        "project": entry,
        "project_count": len(projects),
    }


def build_nle_real_project_corpus_report(
    *,
    manifest_path: str | Path | None = None,
    min_projects: int = 3,
    min_duration_ms: int = 30 * 60_000,
    min_total_video_clips: int = 90,
    min_total_audio_clips: int = 20,
    min_project_duration_ms: int = 5 * 60_000,
    require_validation_evidence: bool = True,
) -> dict[str, Any]:
    """Build the real-project corpus gate used by NLE readiness QA."""

    manifest_path = _as_path(manifest_path or DEFAULT_MANIFEST_PATH)
    manifest = load_manifest(manifest_path)
    projects: list[dict[str, Any]] = []
    totals = {
        "duration_ms": 0,
        "video_clips": 0,
        "audio_clips": 0,
        "missing_media_count": 0,
        "valid_project_count": 0,
        "validation_ready_count": 0,
        "validation_missing_count": 0,
        "validation_failed_required_check_count": 0,
        "preflight_ready_count": 0,
        "preflight_blocked_count": 0,
        "registered_project_count": len(manifest.get("projects") or []),
    }
    generated_count = 0
    for entry in manifest.get("projects") or []:
        path = _as_path(entry.get("path") or "")
        metrics = project_metrics(path)
        source_kind = str(entry.get("source_kind") or "real_user_project")
        generated = bool(metrics.get("generated_fixture_like")) or source_kind != "real_user_project"
        if generated:
            generated_count += 1
        valid = (
            bool(metrics.get("exists"))
            and bool(metrics.get("parse_ok"))
            and not generated
            and _int(metrics.get("duration_ms"), 0) >= min_project_duration_ms
            and (_int(metrics.get("video_clips"), 0) + _int(metrics.get("audio_clips"), 0)) >= 5
            and _int(metrics.get("missing_media_count"), 0) == 0
        )
        if valid:
            totals["valid_project_count"] += 1
            totals["duration_ms"] += _int(metrics.get("duration_ms"), 0)
            totals["video_clips"] += _int(metrics.get("video_clips"), 0)
            totals["audio_clips"] += _int(metrics.get("audio_clips"), 0)
        validation = entry.get("validation_evidence") if isinstance(entry.get("validation_evidence"), Mapping) else {}
        validation_rows = _validation_evidence_rows(
            metrics,
            _normalize_validation_checks(validation.get("checks") if isinstance(validation, Mapping) else None),
        )
        validation_summary = _validation_evidence_summary(validation_rows)
        preflight_rows = _machine_preflight_rows(metrics)
        preflight_blockers = [
            str(row.get("id") or "")
            for row in preflight_rows
            if str(row.get("status") or "") == "blocked"
        ]
        preflight_ready = valid and not preflight_blockers
        if valid and preflight_ready:
            totals["preflight_ready_count"] += 1
        elif valid:
            totals["preflight_blocked_count"] += 1
        validation_ready = valid and bool(validation_summary.get("all_required_passed"))
        if valid and validation_ready:
            totals["validation_ready_count"] += 1
        elif valid:
            totals["validation_missing_count"] += 1
        totals["validation_failed_required_check_count"] += _int(validation_summary.get("failed_required_count"), 0)
        totals["missing_media_count"] += _int(metrics.get("missing_media_count"), 0)
        projects.append(
            {
                "id": str(entry.get("id") or ""),
                "label": str(entry.get("label") or metrics.get("project_name") or path.stem),
                "path": str(path),
                "source_kind": source_kind,
                "valid": valid,
                "preflight_ready": preflight_ready,
                "preflight_blockers": preflight_blockers,
                "validation_ready": validation_ready,
                "validation_summary": validation_summary,
                "metrics": metrics,
            }
        )

    checks = {
        "manifest_exists": manifest_path.exists(),
        "real_project_count": totals["valid_project_count"] >= max(1, int(min_projects)),
        "aggregate_duration": totals["duration_ms"] >= max(1, int(min_duration_ms)),
        "aggregate_video_clips": totals["video_clips"] >= max(0, int(min_total_video_clips)),
        "aggregate_audio_clips": totals["audio_clips"] >= max(0, int(min_total_audio_clips)),
        "no_missing_media": totals["missing_media_count"] == 0 and totals["valid_project_count"] > 0,
        "no_generated_fixtures": generated_count == 0,
        "validation_preflight": (
            not bool(require_validation_evidence)
            or totals["preflight_ready_count"] >= max(1, int(min_projects))
        ),
        "validation_evidence": (
            not bool(require_validation_evidence)
            or (
                totals["validation_ready_count"] >= max(1, int(min_projects))
                and totals["validation_failed_required_check_count"] == 0
            )
        ),
    }
    blockers = [name for name, ok in checks.items() if not ok]
    claim_ready = not blockers
    return {
        "schema": NLE_REAL_CORPUS_SCHEMA,
        "ok": claim_ready,
        "claim_ready": claim_ready,
        "real_world_corpus": claim_ready,
        "manifest": str(manifest_path),
        "thresholds": {
            "min_projects": max(1, int(min_projects)),
            "min_duration_ms": max(1, int(min_duration_ms)),
            "min_total_video_clips": max(0, int(min_total_video_clips)),
            "min_total_audio_clips": max(0, int(min_total_audio_clips)),
            "min_project_duration_ms": max(0, int(min_project_duration_ms)),
            "require_validation_evidence": bool(require_validation_evidence),
        },
        "summary": totals,
        "checks": checks,
        "blockers": blockers,
        "projects": projects,
    }
