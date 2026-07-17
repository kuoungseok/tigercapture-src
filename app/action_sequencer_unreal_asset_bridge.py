"""Internal Unreal asset export bridge for Action Sequencer previews."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNREAL_ASSET_BRIDGE_PROJECT = PROJECT_ROOT / "tools" / "unreal_asset_bridge" / "TigerUnrealAssetBridge.csproj"


def default_owner_unreal_ar_pbr_path(owner_descriptor: Any, *, root: Path | None = None) -> Path:
    base = root or PROJECT_ROOT / "debugCapture"
    project_path = Path(getattr(owner_descriptor, "project_path", "ActionSequencer"))
    project_stem = project_path.stem or "ActionSequencer"
    owner = str(getattr(owner_descriptor, "owner_name", "Owner") or "Owner")
    return base / f"action_sequencer_{project_stem}_{owner}_owner_unreal_skeletal.arpbr"


def export_owner_unreal_ar_pbr_asset(
    owner_descriptor: Any,
    output_path: str | Path | None = None,
    *,
    max_triangles: int = 240_000,
    timeout_s: float = 90.0,
) -> Path:
    """Export the owner render mesh .uasset to a Tiger AR/PBR descriptor."""
    project_path = Path(getattr(owner_descriptor, "project_path", "") or "")
    asset_path = getattr(owner_descriptor, "render_asset_path", None)
    if asset_path is None:
        raise RuntimeError("Owner render mesh is not available.")
    asset_path = Path(asset_path)
    if not project_path.exists():
        raise RuntimeError(f"Unreal project file does not exist: {project_path}")
    if not asset_path.exists():
        raise RuntimeError(f"Owner render mesh does not exist: {asset_path}")
    if not UNREAL_ASSET_BRIDGE_PROJECT.exists():
        raise RuntimeError(f"Internal Unreal asset bridge is missing: {UNREAL_ASSET_BRIDGE_PROJECT}")

    target = Path(output_path) if output_path is not None else default_owner_unreal_ar_pbr_path(owner_descriptor)
    target.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "dotnet",
        "run",
        "--project",
        str(UNREAL_ASSET_BRIDGE_PROJECT),
        "--",
        "export-skeletal-mesh",
        "--project",
        str(project_path),
        "--asset",
        str(asset_path),
        "--out",
        str(target),
        "--max-triangles",
        str(max(1, int(max_triangles))),
    ]

    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        timeout=max(5.0, float(timeout_s)),
        check=False,
    )
    if completed.returncode != 0:
        message = _bridge_error_message(completed.stdout, completed.stderr)
        raise RuntimeError(message)
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"Internal Unreal asset bridge did not write output: {target}")
    return target


def _bridge_error_message(stdout: str, stderr: str) -> str:
    text = "\n".join(part for part in (stderr.strip(), stdout.strip()) if part)
    for candidate in (stderr, stdout):
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if isinstance(payload, dict):
            msg = payload.get("message") or payload.get("error")
            if msg:
                return f"Internal Unreal asset bridge failed: {msg}"
    return f"Internal Unreal asset bridge failed: {text or 'unknown error'}"


__all__ = [
    "UNREAL_ASSET_BRIDGE_PROJECT",
    "default_owner_unreal_ar_pbr_path",
    "export_owner_unreal_ar_pbr_asset",
]
