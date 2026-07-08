"""Autosave helpers for PPT generator project recovery."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from app.pptgen.project_io import load_deck_project, save_deck_project
from app.pptgen.schema import DeckSpec


AUTOSAVE_SUFFIX = ".autosave.tgppt"


def _safe_name(value: str, fallback: str = "untitled") -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._")
    return name or fallback


def ppt_autosave_path(
    *,
    project_path: str | Path | None = None,
    deck_id: str = "",
    root: str | Path | None = None,
) -> Path:
    """Return the recovery path used for a deck autosave."""
    if project_path:
        source = Path(project_path)
        return source.with_name(f"{source.stem}{AUTOSAVE_SUFFIX}")
    base = Path(root) if root else Path.home() / "AppData" / "Local" / "TigerCapture" / "pptgen_autosave"
    return base / f"{_safe_name(deck_id)}{AUTOSAVE_SUFFIX}"


def ppt_autosave_root(root: str | Path | None = None) -> Path:
    """Return the directory used for untitled deck recovery copies."""
    return Path(root) if root else Path.home() / "AppData" / "Local" / "TigerCapture" / "pptgen_autosave"


def _candidate_payload(path: Path) -> dict:
    try:
        stat = path.stat()
    except OSError as exc:
        return {
            "path": str(path),
            "valid": False,
            "reason": str(exc),
            "title": "",
            "deck_id": "",
            "slide_count": 0,
            "modified_time": 0.0,
            "modified_iso": "",
            "size_bytes": 0,
        }
    payload = {
        "path": str(path),
        "valid": False,
        "reason": "",
        "title": "",
        "deck_id": "",
        "slide_count": 0,
        "modified_time": float(stat.st_mtime),
        "modified_iso": datetime.fromtimestamp(float(stat.st_mtime)).isoformat(timespec="seconds"),
        "size_bytes": int(stat.st_size),
    }
    try:
        deck = load_deck_project(path)
    except Exception as exc:
        payload["reason"] = str(exc)
        return payload
    payload.update(
        {
            "valid": True,
            "title": deck.title,
            "deck_id": deck.id,
            "slide_count": len(deck.slides),
        }
    )
    return payload


def list_ppt_recovery_candidates(
    *,
    project_path: str | Path | None = None,
    deck_id: str = "",
    root: str | Path | None = None,
    limit: int = 20,
) -> list[dict]:
    """List readable autosave candidates, newest first."""
    paths: dict[str, Path] = {}
    if project_path:
        sibling = ppt_autosave_path(project_path=project_path)
        paths[str(sibling.resolve())] = sibling
        for path in sibling.parent.glob(f"*{AUTOSAVE_SUFFIX}"):
            paths[str(path.resolve())] = path
    base = ppt_autosave_root(root)
    if base.exists():
        for path in base.glob(f"*{AUTOSAVE_SUFFIX}"):
            paths[str(path.resolve())] = path
    if deck_id:
        path = ppt_autosave_path(deck_id=deck_id, root=root)
        paths[str(path.resolve())] = path
    rows = [
        _candidate_payload(path)
        for path in paths.values()
        if path.exists() and path.is_file()
    ]
    rows.sort(key=lambda row: float(row.get("modified_time") or 0.0), reverse=True)
    return rows[: max(1, int(limit or 20))]


def delete_ppt_recovery_file(path: str | Path) -> dict:
    """Delete a recovery copy, refusing to touch non-autosave files."""
    target = Path(path)
    if not target.name.endswith(AUTOSAVE_SUFFIX):
        raise ValueError(f"Refusing to delete non-recovery file: {target}")
    existed = target.exists()
    if existed:
        target.unlink()
    return {
        "schema": "tigercapture.ppt.recovery_deleted.v1",
        "path": str(target),
        "deleted": bool(existed),
    }


def save_ppt_autosave(
    deck: DeckSpec,
    *,
    project_path: str | Path | None = None,
    root: str | Path | None = None,
) -> Path:
    """Write a recovery copy and return its path."""
    target = ppt_autosave_path(project_path=project_path, deck_id=deck.id, root=root)
    return save_deck_project(deck, target)


__all__ = [
    "AUTOSAVE_SUFFIX",
    "delete_ppt_recovery_file",
    "list_ppt_recovery_candidates",
    "ppt_autosave_path",
    "ppt_autosave_root",
    "save_ppt_autosave",
]
