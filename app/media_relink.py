"""Project media relink helpers.

The editor stores absolute media/model paths in several places: media pool,
video/audio clips, nested clips, and actor clips.  These helpers repair missing
paths by searching user-selected roots for files with matching filenames.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


RELINK_EXTS = {
    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".gif",
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
    ".skel", ".json", ".atlas", ".png", ".jpg", ".jpeg", ".webp",
    ".moc3", ".model3.json", ".motion3.json",
}

VIDEO_RELINK_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".gif"}


@dataclass(frozen=True)
class RelinkChange:
    old_path: str
    new_path: str
    reason: str


def _looks_like_relinkable_path(value: str) -> bool:
    if not value or len(value) > 4096:
        return False
    path = Path(value)
    name = path.name
    if not name or "." not in name:
        return False
    lower = name.lower()
    if lower.endswith(".model3.json") or lower.endswith(".motion3.json"):
        return True
    return path.suffix.lower() in RELINK_EXTS


def build_relink_index(search_roots: Iterable[Path | str]) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for raw_root in search_roots:
        root = Path(raw_root)
        if not root.exists():
            continue
        files: Iterable[Path]
        if root.is_file():
            files = [root]
        else:
            try:
                files = root.rglob("*")
            except Exception:
                continue
        for path in files:
            try:
                if not path.is_file():
                    continue
            except Exception:
                continue
            if not _looks_like_relinkable_path(str(path)):
                continue
            index.setdefault(path.name.lower(), []).append(path)
    for key in list(index):
        index[key] = sorted(set(index[key]), key=lambda p: (len(str(p)), str(p).lower()))
    return index


def collect_relinkable_paths(doc: dict[str, Any]) -> list[str]:
    """Return unique relinkable path strings, regardless of existence."""
    paths: list[str] = []
    seen: set[str] = set()

    def _walk(value) -> None:
        if isinstance(value, dict):
            for child in value.values():
                _walk(child)
            return
        if isinstance(value, list):
            for child in value:
                _walk(child)
            return
        if not isinstance(value, str) or not _looks_like_relinkable_path(value):
            return
        if value in seen:
            return
        seen.add(value)
        paths.append(value)

    _walk(doc)
    return sorted(paths)


def relinkable_occurrences(doc: dict[str, Any]) -> dict[str, int]:
    """Count every occurrence of relinkable path strings in a project doc."""
    counts: dict[str, int] = {}

    def _walk(value) -> None:
        if isinstance(value, dict):
            for child in value.values():
                _walk(child)
            return
        if isinstance(value, list):
            for child in value:
                _walk(child)
            return
        if isinstance(value, str) and _looks_like_relinkable_path(value):
            counts[value] = counts.get(value, 0) + 1

    _walk(doc)
    return counts


def _is_video_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in VIDEO_RELINK_EXTS


def _proxy_path_for_source(path: Path | str) -> Path:
    source = Path(path)
    return source.parent / "proxies" / f"{source.stem}_proxy.mp4"


def _proxy_state_for_source(path: Path | str) -> str:
    """Return not_video, missing, ready, stale, or source_missing."""
    source = Path(path)
    if not _is_video_path(source):
        return "not_video"
    if not source.exists():
        return "source_missing"
    proxy = _proxy_path_for_source(source)
    if not proxy.exists():
        return "missing"
    try:
        if proxy.stat().st_mtime_ns < source.stat().st_mtime_ns:
            return "stale"
    except OSError:
        return "missing"
    return "ready"


def build_media_health_report(
    doc: dict[str, Any],
    search_roots: Iterable[Path | str] = (),
) -> dict[str, Any]:
    """Build a long-project media health report.

    This is broader than relink: it reports missing paths, relink candidates,
    filename collisions, repeated references, and sibling proxy state so the
    editor can show a missing-media browser without hiding proxy debt.
    """
    paths = collect_relinkable_paths(doc)
    occurrence_counts = relinkable_occurrences(doc)
    roots = [Path(root) for root in search_roots]
    index = build_relink_index(roots) if roots else {}
    filename_buckets: dict[str, list[str]] = {}
    for path in paths:
        filename_buckets.setdefault(Path(path).name.lower(), []).append(path)

    rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    proxy_counts: dict[str, int] = {}
    for path in paths:
        p = Path(path)
        filename_key = p.name.lower()
        try:
            exists = p.exists()
        except Exception:
            exists = False
        candidate_paths = [
            str(candidate.resolve())
            for candidate in index.get(filename_key, [])
        ]
        proxy_state = _proxy_state_for_source(p)
        if proxy_state != "not_video":
            proxy_counts[proxy_state] = proxy_counts.get(proxy_state, 0) + 1
        if not exists:
            status = "missing"
        elif len(filename_buckets.get(filename_key, [])) > 1:
            status = "filename_collision"
        elif proxy_state == "stale":
            status = "proxy_stale"
        elif proxy_state == "missing":
            status = "proxy_missing"
        else:
            status = "ok"
        if not exists and len(candidate_paths) > 1:
            status = "relink_conflict"
        status_counts[status] = status_counts.get(status, 0) + 1
        rows.append({
            "path": path,
            "filename": p.name,
            "exists": exists,
            "occurrences": int(occurrence_counts.get(path, 0)),
            "status": status,
            "candidates": candidate_paths,
            "candidate_count": len(candidate_paths),
            "filename_collision": len(filename_buckets.get(filename_key, [])) > 1,
            "proxy_state": proxy_state,
            "proxy_path": str(_proxy_path_for_source(p)) if proxy_state != "not_video" else "",
        })

    rows.sort(key=lambda row: (row["status"] == "ok", row["filename"].lower(), row["path"]))
    return {
        "ok": not any(row["status"] in {"missing", "relink_conflict", "proxy_stale"} for row in rows),
        "total_paths": len(paths),
        "search_roots": [str(root) for root in roots],
        "status_counts": status_counts,
        "proxy_counts": proxy_counts,
        "rows": rows,
    }


def _pick_candidate(old_path: str, index: dict[str, list[Path]]) -> Path | None:
    old = Path(old_path)
    candidates = index.get(old.name.lower()) or []
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    old_parent_name = old.parent.name.lower()
    for candidate in candidates:
        if candidate.parent.name.lower() == old_parent_name:
            return candidate
    return candidates[0]


def candidate_paths_for_missing(
    missing_paths: Iterable[str],
    search_roots: Iterable[Path | str],
) -> dict[str, list[str]]:
    """Return candidate replacement paths for each missing path string."""
    index = build_relink_index(search_roots)
    out: dict[str, list[str]] = {}
    for old_path in missing_paths:
        candidates = index.get(Path(old_path).name.lower()) or []
        out[str(old_path)] = [str(path.resolve()) for path in candidates]
    return out


def build_relink_plan(
    doc: dict[str, Any],
    search_roots: Iterable[Path | str],
) -> dict[str, Any]:
    """Build a UI-friendly missing-media relink plan.

    Rows with exactly one candidate are ready to apply. Rows with multiple
    candidates are conflicts that should be reviewed by the user.
    """
    roots = [Path(root) for root in search_roots]
    missing = missing_relinkable_paths(doc)
    index = build_relink_index(roots)
    rows: list[dict[str, Any]] = []
    conflict_count = 0
    resolved_count = 0
    unresolved_count = 0
    for old_path in missing:
        candidate_paths = index.get(Path(old_path).name.lower()) or []
        candidates = [str(path.resolve()) for path in candidate_paths]
        preferred = _pick_candidate(old_path, index)
        selected = str(preferred.resolve()) if preferred is not None else ""
        if len(candidates) > 1:
            status = "conflict"
            conflict_count += 1
        elif len(candidates) == 1:
            status = "resolved"
            resolved_count += 1
        else:
            status = "missing"
            unresolved_count += 1
        rows.append({
            "old_path": old_path,
            "filename": Path(old_path).name,
            "candidates": candidates,
            "selected": selected,
            "status": status,
            "conflict": len(candidates) > 1,
        })
    return {
        "missing_count": len(missing),
        "resolved_count": resolved_count,
        "conflict_count": conflict_count,
        "unresolved_count": unresolved_count,
        "search_roots": [str(root) for root in roots],
        "rows": rows,
    }


def missing_relinkable_paths(doc: dict[str, Any]) -> list[str]:
    """Return unique relinkable path strings that currently do not exist."""
    missing: list[str] = []
    for value in collect_relinkable_paths(doc):
        try:
            exists = Path(value).exists()
        except Exception:
            exists = False
        if not exists:
            missing.append(value)
    return sorted(missing)


def relink_project_doc(
    doc: dict[str, Any],
    search_roots: Iterable[Path | str],
    *,
    choices: Mapping[str, Path | str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(new_doc, report)`` with missing path strings replaced.

    Existing paths are left untouched. Missing path strings are replaced only
    when a filename match is found under one of the supplied roots.
    """
    index = build_relink_index(search_roots)
    new_doc = copy.deepcopy(doc)
    changes: list[RelinkChange] = []
    unresolved: list[str] = []
    choice_map = {str(k): Path(v) for k, v in (choices or {}).items() if str(v)}

    def _walk(value):
        if isinstance(value, dict):
            for key, child in list(value.items()):
                value[key] = _walk(child)
            return value
        if isinstance(value, list):
            for idx, child in enumerate(list(value)):
                value[idx] = _walk(child)
            return value
        if not isinstance(value, str):
            return value
        if not _looks_like_relinkable_path(value):
            return value
        try:
            if Path(value).exists():
                return value
        except Exception:
            pass
        candidate = choice_map.get(value)
        reason = "user choice" if candidate is not None else "filename match"
        if candidate is not None:
            try:
                if not candidate.exists():
                    candidate = None
            except Exception:
                candidate = None
        if candidate is None:
            candidate = _pick_candidate(value, index)
            reason = "filename match"
        if candidate is None:
            if value not in unresolved:
                unresolved.append(value)
            return value
        new_value = str(candidate.resolve())
        changes.append(
            RelinkChange(
                old_path=value,
                new_path=new_value,
                reason=reason,
            )
        )
        return new_value

    _walk(new_doc)
    report = {
        "changed": len(changes),
        "changes": [change.__dict__ for change in changes],
        "unresolved": sorted(unresolved),
        "search_roots": [str(Path(root)) for root in search_roots],
    }
    return new_doc, report


def relink_project_file(
    project_path: Path | str,
    search_roots: Iterable[Path | str],
    *,
    out_path: Path | str | None = None,
    in_place: bool = False,
    choices: Mapping[str, Path | str] | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Relink a .tgp file and write the repaired project JSON.

    By default this is non-destructive and writes ``<name>.relinked.tgp`` next
    to the source project. Passing ``in_place=True`` updates the original file.
    """
    project = Path(project_path)
    doc = json.loads(project.read_text(encoding="utf-8"))
    missing_before = missing_relinkable_paths(doc)
    new_doc, report = relink_project_doc(doc, search_roots, choices=choices)
    missing_after = missing_relinkable_paths(new_doc)

    if in_place:
        out = project
    elif out_path is not None:
        out = Path(out_path)
    else:
        out = project.with_name(f"{project.stem}.relinked{project.suffix}")

    out.write_text(
        json.dumps(new_doc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report.update({
        "project": str(project),
        "out": str(out),
        "missing_before": missing_before,
        "missing_after": missing_after,
    })
    return out, report
