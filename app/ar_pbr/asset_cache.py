"""Persistent AR/PBR asset descriptor cache."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def asset_cache_root() -> Path:
    root = ROOT / "debugCapture" / "ar_pbr_asset_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_id(asset_id: str) -> str:
    return "".join(ch for ch in str(asset_id or "") if ch.isalnum() or ch in {"_", "-"}) or "asset_unknown"


def _asset_path(asset_id: str, root: Path | None = None) -> Path:
    return (root or asset_cache_root()) / f"{_safe_id(asset_id)}.json"


def store_asset_descriptor(
    descriptor: dict[str, Any],
    *,
    diagnostics: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    asset_id = str(descriptor.get("id") or "asset_unknown")
    path = _asset_path(asset_id, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "descriptor": descriptor,
        "diagnostics": diagnostics or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {
        "ok": True,
        "asset_id": asset_id,
        "cache_path": str(path),
    }


def load_asset_descriptor(asset_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    path = _asset_path(asset_id, root)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        descriptor = data.get("descriptor") if isinstance(data, dict) else None
        return descriptor if isinstance(descriptor, dict) else None
    except Exception:
        return None


def asset_cache_diagnostics(asset_id: str, *, root: Path | None = None) -> dict[str, Any]:
    path = _asset_path(asset_id, root)
    return {
        "ok": path.exists(),
        "asset_id": str(asset_id),
        "cache_path": str(path),
    }
