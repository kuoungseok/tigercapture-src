"""Persistent camera-solution cache helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def camera_solution_cache_root() -> Path:
    root = ROOT / "debugCapture" / "camera_solution_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _solution_path(solution_id: str, root: Path | None = None) -> Path:
    sid = "".join(ch for ch in str(solution_id or "") if ch.isalnum() or ch in {"_", "-"})
    return (root or camera_solution_cache_root()) / f"{sid or 'cam_unknown'}.json"


def store_camera_solution(solution: dict[str, Any], *, root: Path | None = None) -> dict[str, Any]:
    solution_id = str(solution.get("id") or "cam_unknown")
    path = _solution_path(solution_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(solution, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {
        "ok": True,
        "camera_solution_id": solution_id,
        "cache_path": str(path),
    }


def load_camera_solution(solution_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    path = _solution_path(solution_id, root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None

