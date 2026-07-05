"""Project-track helpers for MMD model overlays."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from app.mmd.physics import SECONDARY_ROTATION_HINT_SCALE, SPRING_PHYSICS_RESPONSE
from app.mmd.schema import normalize_mmd_track


MMD_MIME_TYPE = "application/x-tigerstudio-mmd"
DEFAULT_MMD_CLIP_MS = 10_000
MMD_MIN_CLIP_MS = 250


def is_mmd_model_path(path: str | Path) -> bool:
    p = Path(path)
    suffix = p.suffix.casefold()
    return suffix in {".pmx", ".pmd"} or p.name.casefold().endswith(".pbx.json")


def is_mmd_motion_path(path: str | Path) -> bool:
    return Path(path).suffix.casefold() == ".vmd"


def is_mmd_asset_path(path: str | Path) -> bool:
    return is_mmd_model_path(path) or is_mmd_motion_path(path)


def split_mmd_paths(paths: Iterable[str | Path]) -> tuple[list[Path], list[Path]]:
    models: list[Path] = []
    motions: list[Path] = []
    seen: set[str] = set()
    for raw in paths or []:
        try:
            path = Path(raw).expanduser().resolve()
        except Exception:
            continue
        key = str(path)
        if not key or key in seen:
            continue
        seen.add(key)
        if is_mmd_model_path(path):
            models.append(path)
        elif is_mmd_motion_path(path):
            motions.append(path)
    return models, motions


def mmd_paths_from_mime(mime: Any) -> list[Path]:
    """Return normalized PMX/PMD/PBX/VMD paths carried by a Qt mime payload."""
    paths: list[Path] = []
    if mime is None:
        return paths
    try:
        if mime.hasFormat(MMD_MIME_TYPE):
            raw = bytes(mime.data(MMD_MIME_TYPE)).decode("utf-8", errors="ignore")
            for line in raw.splitlines():
                text = line.strip()
                if text:
                    paths.append(Path(text))
    except Exception:
        pass
    try:
        if mime.hasUrls():
            for url in mime.urls():
                path = Path(url.toLocalFile())
                if is_mmd_asset_path(path):
                    paths.append(path)
    except Exception:
        pass
    models, motions = split_mmd_paths(paths)
    return models + motions


def mmd_track_start_ms(track: dict[str, Any]) -> int:
    return max(0, int(track.get("start_ms", 0) or 0))


def mmd_track_end_ms(track: dict[str, Any]) -> int:
    start = mmd_track_start_ms(track)
    end = int(track.get("end_ms", 0) or 0)
    if end <= start:
        duration = max(1, int(track.get("duration_ms", DEFAULT_MMD_CLIP_MS) or DEFAULT_MMD_CLIP_MS))
        end = start + duration
    return end


def mmd_track_duration_ms(track: dict[str, Any]) -> int:
    return max(MMD_MIN_CLIP_MS, mmd_track_end_ms(track) - mmd_track_start_ms(track))


def set_mmd_track_range(
    track: dict[str, Any],
    start_ms: int,
    end_ms: int,
    *,
    min_duration_ms: int = MMD_MIN_CLIP_MS,
) -> dict[str, Any]:
    start = max(0, int(start_ms or 0))
    end = max(start + int(min_duration_ms), int(end_ms or start + DEFAULT_MMD_CLIP_MS))
    track["start_ms"] = start
    track["end_ms"] = end
    track["duration_ms"] = max(int(min_duration_ms), end - start)
    return track


def next_mmd_track_id(tracks: Iterable[dict[str, Any]], *, prefix: str = "mmd") -> str:
    max_seen = 0
    for track in tracks or []:
        text = str(track.get("id") or "")
        if text.startswith(f"{prefix}_"):
            try:
                max_seen = max(max_seen, int(text.rsplit("_", 1)[1]))
            except Exception:
                pass
    return f"{prefix}_{max_seen + 1:03d}"


def duplicate_mmd_track(
    track: dict[str, Any],
    *,
    track_id: str,
    start_ms: int | None = None,
) -> dict[str, Any]:
    clone = deepcopy(track)
    clone["id"] = str(track_id)
    duration = mmd_track_duration_ms(track)
    start = mmd_track_end_ms(track) if start_ms is None else max(0, int(start_ms or 0))
    return set_mmd_track_range(clone, start, start + duration)


def mmd_track_label(track: dict[str, Any], *, fallback: str = "MMD Actor") -> str:
    model_text = str(track.get("model_path") or "")
    motion_text = str(track.get("motion_path") or "")
    label = Path(model_text).stem if model_text else fallback
    if motion_text:
        label = f"{label} / {Path(motion_text).stem}"
    return label


def mmd_motion_duration_ms(path: str | Path | None) -> int:
    if not path:
        return 0
    motion_path = Path(path)
    if not is_mmd_motion_path(motion_path) or not motion_path.is_file():
        return 0
    try:
        from app.mmd.vmd import load_vmd

        motion = load_vmd(motion_path)
        return max(1_000, int(round((max(1, int(motion.max_frame)) / 30.0) * 1000.0)))
    except Exception:
        return 0


def create_preview_mmd_track(
    model_path: str | Path,
    *,
    track_id: str,
    start_ms: int = 0,
    duration_ms: int = DEFAULT_MMD_CLIP_MS,
    motion_path: str | Path | None = None,
) -> dict:
    model = Path(model_path).expanduser().resolve()
    motion = Path(motion_path).expanduser().resolve() if motion_path else None
    motion_duration = mmd_motion_duration_ms(motion)
    duration = max(1_000, int(duration_ms or 0), int(motion_duration or 0))
    return normalize_mmd_track(
        {
            "id": str(track_id),
            "model_path": str(model),
            "motion_path": str(motion) if motion else "",
            "motion_library": [str(motion)] if motion else [],
            "start_ms": max(0, int(start_ms or 0)),
            "duration_ms": duration,
            "view": {
                "yaw": 0.0,
                "pitch": -4.0,
                "zoom": 0.72,
                "offset_x": 0.0,
                "offset_y": 0.02,
            },
            "render": {
                "mode": "toon",
                "lighting_preset": "studio_soft",
                "bloom_strength": 0.30,
            },
            "playback": {
                "loop": True,
                "enable_ik": True,
                "enable_physics": True,
                "gpu_skinning": True,
                "gpu_morph_slots": 2,
                "physics_backend": "auto",
                "physics_update_interval_frames": 2.0,
                "physics_smoothing_response": 0.88,
                "physics_rotation_hint_scale": SECONDARY_ROTATION_HINT_SCALE,
                "physics_spring_response": SPRING_PHYSICS_RESPONSE,
                "foot_ik_reach_limit": 0.985,
            },
        }
    )
