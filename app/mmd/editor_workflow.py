"""Editor-side MMD actor workflow helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from app.mmd.schema import normalize_playback, normalize_render


def mmd_motion_library_for_model(
    model_path: str | Path,
    *,
    current_motion_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return VMD motions that belong to the model's folder.

    The Media Pool intentionally does not expose VMD as normal media; the MMD
    Actor Editor lists sibling VMD files instead.
    """
    try:
        model = Path(model_path).expanduser().resolve()
    except Exception:
        model = Path(str(model_path or ""))
    folder = model.parent if str(model) else Path()
    motions: list[Path] = []
    if folder and folder.exists():
        try:
            motions.extend(sorted((p.resolve() for p in folder.glob("*.vmd") if p.is_file()), key=lambda p: p.name.casefold()))
        except Exception:
            motions = []
    if current_motion_path:
        try:
            current = Path(current_motion_path).expanduser().resolve()
            if current.is_file() and current.suffix.casefold() == ".vmd":
                motions.append(current)
        except Exception:
            pass
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for motion in motions:
        key = str(motion)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": motion.stem,
                "filename": motion.name,
                "path": key,
                "same_folder": bool(folder and motion.parent == folder),
            }
        )
    return rows


def mmd_motion_library_for_track(track: Mapping[str, Any] | None, *, model_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return a de-duplicated VMD list for an MMD track.

    Sources are ordered as: same-folder motions, current motion, then the
    track's explicitly-added motion library.
    """
    track_data = track if isinstance(track, Mapping) else {}
    model = model_path or str(track_data.get("model_path") or "")
    current = str(track_data.get("motion_path") or "")
    rows = mmd_motion_library_for_model(model, current_motion_path=current)
    for extra in list(track_data.get("motion_library") or []):
        rows.extend(mmd_motion_library_for_model(model, current_motion_path=extra))

    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        path = str(row.get("path") or "")
        if path and path not in unique:
            unique[path] = row
    return list(unique.values())


def add_mmd_motion_to_library(track: dict[str, Any], motion_path: str | Path) -> str:
    if not isinstance(track, dict):
        raise ValueError("MMD track must be a dict")
    motion = Path(motion_path).expanduser().resolve()
    if motion.suffix.casefold() != ".vmd":
        raise ValueError("MMD motion must be a .vmd file")
    library = [str(v) for v in (track.get("motion_library") or []) if str(v)]
    resolved = str(motion)
    if resolved not in library:
        library.append(resolved)
    track["motion_library"] = library
    return resolved


def apply_mmd_motion_to_track(track: dict[str, Any], motion_path: str | Path) -> dict[str, Any]:
    if not isinstance(track, dict):
        raise ValueError("MMD track must be a dict")
    motion = Path(motion_path).expanduser().resolve()
    if motion.suffix.casefold() != ".vmd":
        raise ValueError("MMD motion must be a .vmd file")
    if not motion.is_file():
        raise FileNotFoundError(str(motion))
    track["motion_path"] = str(motion)
    return track


def apply_mmd_settings_to_track(
    track: dict[str, Any],
    *,
    playback: Mapping[str, Any] | None = None,
    render: Mapping[str, Any] | None = None,
    material: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(track, dict):
        raise ValueError("MMD track must be a dict")
    if playback:
        base = dict(track.get("playback") if isinstance(track.get("playback"), dict) else {})
        base.update(dict(playback))
        track["playback"] = normalize_playback(base)
    if render or material:
        base_render = dict(track.get("render") if isinstance(track.get("render"), dict) else {})
        if render:
            base_render.update(dict(render))
        if material:
            current_material = dict(base_render.get("material") if isinstance(base_render.get("material"), dict) else {})
            current_material.update(dict(material))
            base_render["material"] = current_material
        track["render"] = normalize_render(base_render)
    return track
