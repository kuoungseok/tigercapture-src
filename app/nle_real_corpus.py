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
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_PATH = ROOT / "qa_corpus" / "nle_real_projects" / "manifest.json"
NLE_REAL_CORPUS_SCHEMA = "tigerstudio.nle.real_project_corpus.v1"


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
        totals["missing_media_count"] += _int(metrics.get("missing_media_count"), 0)
        projects.append(
            {
                "id": str(entry.get("id") or ""),
                "label": str(entry.get("label") or metrics.get("project_name") or path.stem),
                "path": str(path),
                "source_kind": source_kind,
                "valid": valid,
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
        },
        "summary": totals,
        "checks": checks,
        "blockers": blockers,
        "projects": projects,
    }
