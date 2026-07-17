"""Internal Unreal asset export bridge for Action Sequencer previews."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNREAL_ASSET_BRIDGE_PROJECT = PROJECT_ROOT / "tools" / "unreal_asset_bridge" / "TigerUnrealAssetBridge.csproj"
UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT = PROJECT_ROOT / "tools" / "unreal_asset_bridge" / "export_animation_clip_unreal.py"


def default_owner_unreal_ar_pbr_path(owner_descriptor: Any, *, root: Path | None = None) -> Path:
    base = root or PROJECT_ROOT / "debugCapture"
    project_path = Path(getattr(owner_descriptor, "project_path", "ActionSequencer"))
    project_stem = project_path.stem or "ActionSequencer"
    owner = str(getattr(owner_descriptor, "owner_name", "Owner") or "Owner")
    return base / f"action_sequencer_{project_stem}_{owner}_owner_unreal_skeletal.arpbr"


def default_owner_unreal_animation_clip_path(
    owner_descriptor: Any,
    animation_path: str | Path,
    *,
    root: Path | None = None,
) -> Path:
    base = root or PROJECT_ROOT / "debugCapture" / "action_sequencer_animation_clips"
    project_path = Path(getattr(owner_descriptor, "project_path", "ActionSequencer"))
    project_stem = _safe_file_stem(project_path.stem or "ActionSequencer")
    owner = _safe_file_stem(str(getattr(owner_descriptor, "owner_name", "Owner") or "Owner"))
    animation = _safe_file_stem(Path(animation_path).stem or "Animation")
    return base / f"action_sequencer_{project_stem}_{owner}_{animation}.animation_clip.json"


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


def export_owner_unreal_animation_clip(
    owner_descriptor: Any,
    animation_path: str | Path,
    output_path: str | Path | None = None,
    *,
    max_samples: int = 90,
    timeout_s: float = 90.0,
) -> dict[str, Any]:
    """Export a selected Unreal UAnimSequence to the AR/PBR animation clip schema."""
    project_path = Path(getattr(owner_descriptor, "project_path", "") or "")
    asset_path = Path(animation_path)
    if not project_path.exists():
        raise RuntimeError(f"Unreal project file does not exist: {project_path}")
    if not asset_path.exists():
        raise RuntimeError(f"Animation sequence does not exist: {asset_path}")
    if not UNREAL_ASSET_BRIDGE_PROJECT.exists():
        raise RuntimeError(f"Internal Unreal asset bridge is missing: {UNREAL_ASSET_BRIDGE_PROJECT}")

    target = Path(output_path) if output_path is not None else default_owner_unreal_animation_clip_path(owner_descriptor, asset_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "dotnet",
        "run",
        "--project",
        str(UNREAL_ASSET_BRIDGE_PROJECT),
        "--",
        "export-animation-clip",
        "--project",
        str(project_path),
        "--asset",
        str(asset_path),
        "--out",
        str(target),
        "--max-samples",
        str(max(2, int(max_samples))),
    ]
    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    if reference_mesh is not None:
        reference_mesh_path = Path(reference_mesh)
        if reference_mesh_path.exists():
            command.extend(["--reference-mesh", str(reference_mesh_path)])

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
        return _export_owner_unreal_animation_clip_via_editor(
            owner_descriptor,
            asset_path,
            target,
            max_samples=max_samples,
            timeout_s=max(timeout_s, 240.0),
            first_error=message,
        )
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"Internal Unreal asset bridge did not write output: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    clip = payload.get("animation_clip") if isinstance(payload, dict) else None
    if not isinstance(clip, dict):
        raise RuntimeError(f"Internal Unreal asset bridge wrote an invalid animation payload: {target}")
    clip = dict(clip)
    clip["_export_path"] = str(target)
    return clip


def _export_owner_unreal_animation_clip_via_editor(
    owner_descriptor: Any,
    asset_path: Path,
    target: Path,
    *,
    max_samples: int,
    timeout_s: float,
    first_error: str,
) -> dict[str, Any]:
    from app.unreal_link_reference_paths import DEFAULT_UE_ENGINE_ROOT, UE_ENGINE_ENV

    project_path = Path(getattr(owner_descriptor, "project_path", "") or "")
    if not UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT.exists():
        raise RuntimeError(f"{first_error}; Unreal Editor fallback script is missing: {UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT}")
    ue_root = Path(os.environ.get(UE_ENGINE_ENV, "").strip() or DEFAULT_UE_ENGINE_ROOT)
    editor_cmd = ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    if not editor_cmd.exists():
        editor_cmd = ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    if not editor_cmd.exists():
        raise RuntimeError(f"{first_error}; Unreal Editor fallback is unavailable: {editor_cmd}")

    animation_game_path = _content_asset_game_path(project_path, asset_path)
    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    reference_mesh_game_path = ""
    if reference_mesh is not None:
        reference_mesh_path = Path(reference_mesh)
        if reference_mesh_path.exists():
            reference_mesh_game_path = _content_asset_game_path(project_path, reference_mesh_path)

    env = dict(os.environ)
    env.update({
        "TIGERSTUDIO_UNREAL_ANIM_ASSET": animation_game_path,
        "TIGERSTUDIO_UNREAL_ANIM_OUT": str(target),
        "TIGERSTUDIO_UNREAL_ANIM_MAX_SAMPLES": str(max(2, int(max_samples))),
        "TIGERSTUDIO_UNREAL_ANIM_SOURCE_FILE": str(asset_path),
    })
    if reference_mesh_game_path:
        env["TIGERSTUDIO_UNREAL_REFERENCE_MESH"] = reference_mesh_game_path

    command = [
        str(editor_cmd),
        str(project_path),
        "-unattended",
        "-nop4",
        "-nosplash",
        "-NullRHI",
        f"-ExecutePythonScript={UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT}",
    ]
    startupinfo = None
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0

    completed = subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        timeout=max(30.0, float(timeout_s)),
        check=False,
    )
    if completed.returncode != 0 and (not target.exists() or target.stat().st_size <= 0):
        raise RuntimeError(
            f"{first_error}; Unreal Editor fallback failed: "
            f"{_bridge_error_message(completed.stdout, completed.stderr)}"
        )
    if not target.exists() or target.stat().st_size <= 0:
        raise RuntimeError(f"{first_error}; Unreal Editor fallback did not write output: {target}")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise RuntimeError(f"{first_error}; Unreal Editor fallback failed: {payload.get('message') or payload.get('error')}")
    clip = payload.get("animation_clip") if isinstance(payload, dict) else None
    if not isinstance(clip, dict):
        raise RuntimeError(f"{first_error}; Unreal Editor fallback wrote an invalid animation payload: {target}")
    clip = dict(clip)
    clip["_export_path"] = str(target)
    clip["_exporter"] = str(payload.get("exporter") or "unreal_editor_python") if isinstance(payload, dict) else "unreal_editor_python"
    return clip


def _content_asset_game_path(project_path: Path, asset_path: Path) -> str:
    content_root = project_path.parent / "Content"
    try:
        rel = asset_path.resolve().relative_to(content_root.resolve())
    except Exception as exc:
        raise RuntimeError(f"Asset is not inside the project's Content directory: {asset_path}") from exc
    return "/Game/" + rel.with_suffix("").as_posix()


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


def _safe_file_stem(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    return safe.strip("_") or "asset"


__all__ = [
    "UNREAL_ASSET_BRIDGE_PROJECT",
    "default_owner_unreal_ar_pbr_path",
    "default_owner_unreal_animation_clip_path",
    "export_owner_unreal_ar_pbr_asset",
    "export_owner_unreal_animation_clip",
]
