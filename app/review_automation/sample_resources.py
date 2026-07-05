from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .paths import DEFAULT_REVIEW_SAMPLE_MANIFEST, DEFAULT_REVIEW_SAMPLE_ROOT, ROOT

SCHEMA_VERSION = 1


def _rel(path: Path, *, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


@dataclass(frozen=True)
class ReviewSampleResource:
    id: str
    kind: str
    path: str
    role: str
    title: str
    required: bool = True
    tags: tuple[str, ...] = ()
    sidecars: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReviewSampleResource":
        return cls(
            id=str(payload.get("id") or ""),
            kind=str(payload.get("kind") or "file"),
            path=str(payload.get("path") or ""),
            role=str(payload.get("role") or ""),
            title=str(payload.get("title") or payload.get("id") or ""),
            required=bool(payload.get("required", True)),
            tags=tuple(str(item) for item in _as_list(payload.get("tags"))),
            sidecars=tuple(str(item) for item in _as_list(payload.get("sidecars"))),
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "role": self.role,
            "title": self.title,
            "required": bool(self.required),
            "tags": list(self.tags),
            "sidecars": list(self.sidecars),
            "metadata": dict(self.metadata or {}),
        }

    def resolved_path(self, *, root: Path = ROOT) -> Path:
        path = Path(self.path)
        return path if path.is_absolute() else root / path

    def resolved_sidecars(self, *, root: Path = ROOT) -> list[Path]:
        out: list[Path] = []
        for item in self.sidecars:
            path = Path(item)
            out.append(path if path.is_absolute() else root / path)
        return out


def build_default_review_sample_manifest(
    sample_root: str | Path = DEFAULT_REVIEW_SAMPLE_ROOT,
    *,
    created_by: str = "review_sample_resources",
) -> dict[str, Any]:
    """Return the default review-demo manifest.

    The manifest lives under the review automation workspace and points to
    files in its ``samples/media`` folder. The actual binary media is generated
    by ``tools/prepare_review_sample_resources.py`` so product repo history does
    not carry large demo files.
    """

    root = Path(sample_root)
    media = root / "media"
    resources = [
        ReviewSampleResource(
            id="overview_screen_demo",
            kind="video",
            path=_rel(media / "overview_screen_demo.mp4"),
            role="overview",
            title="Editor overview sample video",
            tags=("overview", "screen-recording", "video"),
            metadata={"duration_ms": 6000, "frame_size": [1280, 720], "fps": 30},
        ),
        ReviewSampleResource(
            id="screenstudio_cursor_demo",
            kind="video",
            path=_rel(media / "screenstudio_cursor_demo.mp4"),
            role="screenstudio_auto_polish",
            title="Auto Polish cursor/click/hotkey demo video",
            tags=("screenstudio", "cursor", "auto-polish", "video"),
            sidecars=(_rel(media / "screenstudio_cursor_demo.mp4.cursor.json"),),
            metadata={
                "duration_ms": 7200,
                "frame_size": [1280, 720],
                "fps": 30,
                "requires_cursor_sidecar": True,
            },
        ),
        ReviewSampleResource(
            id="dialogue_cleanup_demo",
            kind="audio",
            path=_rel(media / "dialogue_cleanup_demo.wav"),
            role="audio_voice",
            title="Dialogue cleanup demo audio",
            tags=("audio", "dialogue", "voice-cleanup"),
            metadata={"duration_ms": 7000, "sample_rate": 48000},
        ),
        ReviewSampleResource(
            id="ai_script_transcript_demo",
            kind="transcript",
            path=_rel(media / "ai_script_transcript_demo.srt"),
            role="ai_script_edit",
            title="AI Script Edit transcript",
            tags=("ai", "transcript", "script-edit", "captions"),
            metadata={"language": "ko-en", "segments": 4},
        ),
        ReviewSampleResource(
            id="review_overview_poster",
            kind="image",
            path=_rel(media / "review_overview_poster.png"),
            role="html_deck",
            title="Review automation poster image",
            tags=("poster", "html", "deck"),
            metadata={"frame_size": [1280, 720]},
        ),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "tigercapture_review_sample_resources",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": created_by,
        "sample_root": _rel(root),
        "media_root": _rel(media),
        "resources": [row.to_dict() for row in resources],
        "notes": [
            "Generated media is intentionally local and reproducible.",
            "Do not commit large generated media unless release policy changes.",
            "Review automation should use this manifest instead of hard-coded media paths.",
        ],
    }


def write_review_sample_manifest(
    manifest_path: str | Path = DEFAULT_REVIEW_SAMPLE_MANIFEST,
    *,
    overwrite: bool = True,
    sample_root: str | Path | None = None,
) -> Path:
    path = Path(manifest_path)
    if path.exists() and not overwrite:
        return path
    root = Path(sample_root) if sample_root is not None else path.parent
    payload = build_default_review_sample_manifest(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_review_sample_manifest(
    manifest_path: str | Path = DEFAULT_REVIEW_SAMPLE_MANIFEST,
    *,
    create_default_if_missing: bool = False,
) -> dict[str, Any]:
    path = Path(manifest_path)
    if not path.exists():
        if create_default_if_missing:
            write_review_sample_manifest(path)
        else:
            return build_default_review_sample_manifest(path.parent)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return build_default_review_sample_manifest(path.parent)
    return payload if isinstance(payload, dict) else build_default_review_sample_manifest(path.parent)


def iter_review_sample_resources(manifest: Mapping[str, Any]) -> Iterable[ReviewSampleResource]:
    for item in _as_list(manifest.get("resources")):
        if isinstance(item, Mapping):
            resource = ReviewSampleResource.from_dict(item)
            if resource.id and resource.path:
                yield resource


def review_sample_resource_report(
    manifest_path: str | Path = DEFAULT_REVIEW_SAMPLE_MANIFEST,
    *,
    root: str | Path = ROOT,
    create_default_if_missing: bool = False,
) -> dict[str, Any]:
    project_root = Path(root)
    path = Path(manifest_path)
    manifest = load_review_sample_manifest(path, create_default_if_missing=create_default_if_missing)
    rows: list[dict[str, Any]] = []
    missing_required = 0
    missing_optional = 0
    for resource in iter_review_sample_resources(manifest):
        main_path = resource.resolved_path(root=project_root)
        sidecars = resource.resolved_sidecars(root=project_root)
        sidecar_rows = [
            {
                "path": _rel(item, root=project_root),
                "exists": item.exists(),
            }
            for item in sidecars
        ]
        exists = main_path.exists()
        sidecars_ok = all(row["exists"] for row in sidecar_rows)
        metadata = dict(resource.metadata or {})
        source_required = bool(metadata.get("requires_youtube_import_source"))
        source_mode = str(metadata.get("source_mode") or "")
        source_ok = (not source_required) or source_mode == "youtube_imports"
        ready = bool(exists and sidecars_ok and source_ok)
        if not ready:
            if resource.required:
                missing_required += 1
            else:
                missing_optional += 1
        rows.append(
            {
                "id": resource.id,
                "kind": resource.kind,
                "role": resource.role,
                "title": resource.title,
                "path": _rel(main_path, root=project_root),
                "exists": bool(exists),
                "sidecars": sidecar_rows,
                "ready": ready,
                "required": bool(resource.required),
                "tags": list(resource.tags),
                "metadata": metadata,
                "source_ready": bool(source_ok),
                "source_mode": source_mode,
            }
        )
    return {
        "kind": "review_sample_resource_report",
        "ok": missing_required == 0,
        "manifest_path": _rel(path, root=project_root),
        "manifest_exists": path.exists(),
        "sample_root": str(manifest.get("sample_root") or DEFAULT_REVIEW_SAMPLE_ROOT.as_posix()),
        "resource_count": len(rows),
        "ready_count": sum(1 for row in rows if row.get("ready")),
        "missing_required_count": missing_required,
        "missing_optional_count": missing_optional,
        "resources": rows,
        "prepare_command": ".\\.venv\\Scripts\\python.exe tools\\prepare_review_sample_resources.py",
    }
