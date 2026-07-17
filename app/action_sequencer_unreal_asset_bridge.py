"""Internal Unreal asset export bridge for Action Sequencer previews."""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNREAL_ASSET_BRIDGE_PROJECT = PROJECT_ROOT / "tools" / "unreal_asset_bridge" / "TigerUnrealAssetBridge.csproj"
UNREAL_ASSET_BRIDGE_DLL = PROJECT_ROOT / "tools" / "unreal_asset_bridge" / "bin" / "Debug" / "net8.0" / "TigerUnrealAssetBridge.dll"
UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT = PROJECT_ROOT / "tools" / "unreal_asset_bridge" / "export_animation_clip_unreal.py"
ANIMATION_ROTATION_SPACE = "tiger_basis_quat_v1"


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


def owner_unreal_animation_clip_cache_status(
    owner_descriptor: Any,
    animation_path: str | Path,
    *,
    max_samples: int = 48,
) -> dict[str, Any]:
    """Return a cheap cache hint for an owner AnimSequence preview clip."""

    asset_path = Path(animation_path)
    target = default_owner_unreal_animation_clip_path(owner_descriptor, asset_path)
    status = {
        "animation_path": str(asset_path),
        "cache_path": str(target),
        "exists": bool(target.exists() and target.stat().st_size > 0),
        "fresh": False,
        "validated": False,
        "max_samples": int(max_samples),
    }
    if not status["exists"]:
        return status
    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    reference_mesh_path = Path(reference_mesh) if reference_mesh is not None else None
    if reference_mesh_path is not None and not reference_mesh_path.exists():
        reference_mesh_path = None
    try:
        source_mtime = asset_path.stat().st_mtime
        if reference_mesh_path is not None:
            source_mtime = max(source_mtime, reference_mesh_path.stat().st_mtime)
        status["fresh"] = target.stat().st_mtime >= source_mtime
    except Exception:
        status["fresh"] = False
    return status


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

    command = _internal_bridge_command(
        "export-skeletal-mesh",
        "--project",
        str(project_path),
        "--asset",
        str(asset_path),
        "--out",
        str(target),
        "--max-triangles",
        str(max(1, int(max_triangles))),
    )

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
    use_cache: bool = True,
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

    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    reference_mesh_path = Path(reference_mesh) if reference_mesh is not None else None
    if reference_mesh_path is not None and not reference_mesh_path.exists():
        reference_mesh_path = None
    if use_cache:
        cached = _load_cached_animation_clip_if_fresh(
            target,
            asset_path=asset_path,
            reference_mesh_path=reference_mesh_path,
            max_samples=max_samples,
        )
        if cached is not None:
            return cached

    command = _internal_bridge_command(
        "export-animation-clip",
        "--project",
        str(project_path),
        "--asset",
        str(asset_path),
        "--out",
        str(target),
        "--max-samples",
        str(max(2, int(max_samples))),
    )
    if reference_mesh_path is not None:
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
    clip = _normalize_animation_clip_payload(payload, clip)
    clip["_export_path"] = str(target)
    return clip


def export_owner_unreal_animation_clips_batch(
    owner_descriptor: Any,
    animation_paths: list[str | Path] | tuple[str | Path, ...],
    *,
    max_samples: int = 48,
    timeout_s: float = 900.0,
    use_cache: bool = True,
) -> dict[str, dict[str, Any]]:
    """Export multiple owner AnimSequences using one Unreal Editor fallback session.

    Per-click one-clip export is too slow for an Action Sequencer browser. This
    entry point validates existing caches first, then exports the remaining
    AnimSequences in a single Unreal Editor process so the user can browse the
    list more like an asset inspector.
    """

    paths = _unique_existing_paths(animation_paths)
    results: dict[str, dict[str, Any]] = {}
    missing: list[Path] = []
    project_path = Path(getattr(owner_descriptor, "project_path", "") or "")
    if not project_path.exists():
        raise RuntimeError(f"Unreal project file does not exist: {project_path}")

    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    reference_mesh_path = Path(reference_mesh) if reference_mesh is not None else None
    if reference_mesh_path is not None and not reference_mesh_path.exists():
        reference_mesh_path = None

    for asset_path in paths:
        target = default_owner_unreal_animation_clip_path(owner_descriptor, asset_path)
        if use_cache:
            cached = _load_cached_animation_clip_if_fresh(
                target,
                asset_path=asset_path,
                reference_mesh_path=reference_mesh_path,
                max_samples=max_samples,
            )
            if cached is not None:
                results[str(asset_path)] = {
                    "status": "cached",
                    "animation_path": str(asset_path),
                    "cache_path": str(target),
                    "clip": cached,
                    "summary": _clip_summary(cached),
                }
                continue
        missing.append(asset_path)

    if not missing:
        return results

    internal_results = _export_owner_unreal_animation_clips_via_internal_batch(
        owner_descriptor,
        missing,
        max_samples=max_samples,
        timeout_s=min(max(30.0, timeout_s), 180.0),
    )
    remaining: list[Path] = []
    deferred_failures: dict[str, dict[str, Any]] = {}
    for asset_path in missing:
        key = str(asset_path)
        result = internal_results.get(key)
        if result and result.get("status") == "animation_clip_exported":
            results[key] = result
            continue
        if result and result.get("status") == "unsupported_animation_asset":
            results[key] = result
            continue
        if result:
            deferred_failures[key] = result
        remaining.append(asset_path)

    if remaining:
        editor_results = _export_owner_unreal_animation_clips_via_editor_batch(
            owner_descriptor,
            remaining,
            max_samples=max_samples,
            timeout_s=timeout_s,
        )
        for asset_path in remaining:
            key = str(asset_path)
            result = editor_results.get(key)
            if result is not None:
                results[key] = result
            elif key in deferred_failures:
                results[key] = deferred_failures[key]
    return results


def _export_owner_unreal_animation_clips_via_internal_batch(
    owner_descriptor: Any,
    animation_paths: list[Path],
    *,
    max_samples: int,
    timeout_s: float,
) -> dict[str, dict[str, Any]]:
    project_path = Path(getattr(owner_descriptor, "project_path", "") or "")
    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    reference_mesh_path = Path(reference_mesh) if reference_mesh is not None else None
    if reference_mesh_path is not None and not reference_mesh_path.exists():
        reference_mesh_path = None

    batch_items: list[dict[str, Any]] = []
    results: dict[str, dict[str, Any]] = {}
    for asset_path in animation_paths:
        target = default_owner_unreal_animation_clip_path(owner_descriptor, asset_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        batch_items.append({
            "asset": str(asset_path),
            "out": str(target),
            "source_file": str(asset_path),
            "max_samples": int(max_samples),
        })

    if not batch_items:
        return results

    manifest_dir = PROJECT_ROOT / "debugCapture" / "action_sequencer_animation_clips"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    batch_json = manifest_dir / f"internal_batch_in_{int(time.time() * 1000)}.json"
    manifest = manifest_dir / f"internal_batch_out_{int(time.time() * 1000)}.json"
    batch_json.write_text(json.dumps({"items": batch_items}, ensure_ascii=False), encoding="utf-8")

    command = _internal_bridge_command(
        "export-animation-clips",
        "--project",
        str(project_path),
        "--batch-json",
        str(batch_json),
        "--out",
        str(manifest),
        "--max-samples",
        str(max(2, int(max_samples))),
    )
    if reference_mesh_path is not None:
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
        timeout=max(10.0, float(timeout_s)),
        check=False,
    )
    if completed.returncode != 0 and (not manifest.exists() or manifest.stat().st_size <= 0):
        message = _bridge_error_message(completed.stdout, completed.stderr)
        for item in batch_items:
            source = str(item["source_file"])
            results[source] = {
                "status": "export_failed",
                "animation_path": source,
                "cache_path": str(item["out"]),
                "error": "InternalCue4ParseBatchFailed",
                "message": message,
            }
        return results

    payload: dict[str, Any] = {}
    if manifest.exists() and manifest.stat().st_size > 0:
        try:
            loaded = json.loads(manifest.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}

    item_results = payload.get("results") if isinstance(payload.get("results"), list) else []
    by_source: dict[str, dict[str, Any]] = {}
    for raw in item_results:
        if not isinstance(raw, dict):
            continue
        source = str(raw.get("source_file") or "")
        if source:
            by_source[source] = raw

    for item in batch_items:
        source = str(item["source_file"])
        target = Path(str(item["out"]))
        raw = by_source.get(source, {})
        if bool(raw.get("ok")) and target.exists() and target.stat().st_size > 0:
            try:
                clip_payload = json.loads(target.read_text(encoding="utf-8"))
                clip = clip_payload.get("animation_clip") if isinstance(clip_payload, dict) else None
                if not isinstance(clip, dict):
                    raise RuntimeError("invalid animation payload")
                clip = _normalize_animation_clip_payload(clip_payload, clip)
                clip["_export_path"] = str(target)
                clip["_exporter"] = str(clip_payload.get("exporter") or payload.get("exporter") or "internal_cue4parse_batch")
                results[source] = {
                    "status": "animation_clip_exported",
                    "animation_path": source,
                    "cache_path": str(target),
                    "clip": clip,
                    "summary": _clip_summary(clip),
                }
                continue
            except Exception as exc:
                raw = {
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
        message = str(raw.get("message") or "Internal CUE4Parse batch export did not write this clip.")
        unsupported = "No UAnimSequence export" in message
        results[source] = {
            "status": "unsupported_animation_asset" if unsupported else "export_failed",
            "animation_path": source,
            "cache_path": str(target),
            "error": str(raw.get("error") or "InternalCue4ParseMissingOutput"),
            "message": message,
        }
    return results


def _load_cached_animation_clip_if_fresh(
    target: Path,
    *,
    asset_path: Path,
    reference_mesh_path: Path | None,
    max_samples: int,
) -> dict[str, Any] | None:
    if not target.exists() or target.stat().st_size <= 0:
        return None
    try:
        target_mtime = target.stat().st_mtime
        source_mtime = asset_path.stat().st_mtime
        if reference_mesh_path is not None:
            source_mtime = max(source_mtime, reference_mesh_path.stat().st_mtime)
        if target_mtime < source_mtime:
            return None
        payload = json.loads(target.read_text(encoding="utf-8"))
        clip = payload.get("animation_clip") if isinstance(payload, dict) else None
        if not isinstance(clip, dict):
            return None
        clip = _normalize_animation_clip_payload(payload, clip)
        if str(clip.get("rotation_space") or "") != ANIMATION_ROTATION_SPACE:
            return None
        requested_samples = max(2, int(max_samples))
        exported_samples = int(float(clip.get("sampled_frame_count") or payload.get("sampled_frame_count") or 0))
        if exported_samples > 0 and exported_samples < requested_samples:
            return None
        if exported_samples <= 0 and requested_samples > 2:
            return None
        out = dict(clip)
        out["_export_path"] = str(target)
        out["_exporter"] = str(payload.get("exporter") or out.get("_exporter") or "cached_animation_clip")
        out["_cache_hit"] = True
        return out
    except Exception:
        return None


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
    clip = _normalize_animation_clip_payload(payload, clip)
    clip["_export_path"] = str(target)
    clip["_exporter"] = str(payload.get("exporter") or "unreal_editor_python") if isinstance(payload, dict) else "unreal_editor_python"
    return clip


def _export_owner_unreal_animation_clips_via_editor_batch(
    owner_descriptor: Any,
    animation_paths: list[Path],
    *,
    max_samples: int,
    timeout_s: float,
) -> dict[str, dict[str, Any]]:
    from app.unreal_link_reference_paths import DEFAULT_UE_ENGINE_ROOT, UE_ENGINE_ENV

    project_path = Path(getattr(owner_descriptor, "project_path", "") or "")
    if not UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT.exists():
        raise RuntimeError(f"Unreal Editor fallback script is missing: {UNREAL_EDITOR_ANIMATION_EXPORT_SCRIPT}")
    ue_root = Path(os.environ.get(UE_ENGINE_ENV, "").strip() or DEFAULT_UE_ENGINE_ROOT)
    editor_cmd = ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"
    if not editor_cmd.exists():
        editor_cmd = ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    if not editor_cmd.exists():
        raise RuntimeError(f"Unreal Editor fallback is unavailable: {editor_cmd}")

    reference_mesh = getattr(owner_descriptor, "render_asset_path", None)
    reference_mesh_game_path = ""
    if reference_mesh is not None:
        reference_mesh_path = Path(reference_mesh)
        if reference_mesh_path.exists():
            reference_mesh_game_path = _content_asset_game_path(project_path, reference_mesh_path)

    batch_items: list[dict[str, Any]] = []
    results: dict[str, dict[str, Any]] = {}
    for asset_path in animation_paths:
        target = default_owner_unreal_animation_clip_path(owner_descriptor, asset_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            item = {
                "asset": _content_asset_game_path(project_path, asset_path),
                "out": str(target),
                "source_file": str(asset_path),
                "max_samples": int(max_samples),
            }
            if reference_mesh_game_path:
                item["reference_mesh"] = reference_mesh_game_path
            batch_items.append(item)
        except Exception as exc:
            results[str(asset_path)] = {
                "status": "export_failed",
                "animation_path": str(asset_path),
                "cache_path": str(target),
                "error": type(exc).__name__,
                "message": str(exc),
            }

    if not batch_items:
        return results

    manifest = PROJECT_ROOT / "debugCapture" / "action_sequencer_animation_clips" / f"batch_{int(time.time() * 1000)}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "TIGERSTUDIO_UNREAL_ANIM_BATCH_JSON": json.dumps(batch_items, ensure_ascii=False),
        "TIGERSTUDIO_UNREAL_ANIM_BATCH_OUT": str(manifest),
    })
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
    batch_payload: dict[str, Any] = {}
    if manifest.exists() and manifest.stat().st_size > 0:
        try:
            batch_payload = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            batch_payload = {}
    if completed.returncode != 0 and not batch_payload:
        message = _bridge_error_message(completed.stdout, completed.stderr)
        for item in batch_items:
            source = str(item.get("source_file") or "")
            results[source] = {
                "status": "export_failed",
                "animation_path": source,
                "cache_path": str(item.get("out") or ""),
                "error": "UnrealEditorBatchFailed",
                "message": message,
            }
        return results

    for item in batch_items:
        source = str(item.get("source_file") or "")
        target = Path(str(item.get("out") or ""))
        if target.exists() and target.stat().st_size > 0:
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("ok") is False:
                    raise RuntimeError(str(payload.get("message") or payload.get("error") or "export failed"))
                clip = payload.get("animation_clip") if isinstance(payload, dict) else None
                if not isinstance(clip, dict):
                    raise RuntimeError("invalid animation payload")
                clip = _normalize_animation_clip_payload(payload, clip)
                clip["_export_path"] = str(target)
                clip["_exporter"] = str(payload.get("exporter") or "unreal_editor_python_batch")
                results[source] = {
                    "status": "animation_clip_exported",
                    "animation_path": source,
                    "cache_path": str(target),
                    "clip": clip,
                    "summary": _clip_summary(clip),
                }
                continue
            except Exception as exc:
                results[source] = {
                    "status": "export_failed",
                    "animation_path": source,
                    "cache_path": str(target),
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
                continue
        results[source] = {
            "status": "export_failed",
            "animation_path": source,
            "cache_path": str(target),
            "error": "MissingOutput",
            "message": "Unreal Editor batch export did not write this clip.",
        }
    return results


def _unique_existing_paths(paths: list[str | Path] | tuple[str | Path, ...]) -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()
    for value in paths:
        path = Path(value)
        key = str(path)
        if key in seen or not path.exists():
            continue
        seen.add(key)
        out.append(path)
    return out


def _internal_bridge_command(*args: str) -> list[str]:
    if _internal_bridge_dll_is_fresh():
        return ["dotnet", str(UNREAL_ASSET_BRIDGE_DLL), *args]
    return [
        "dotnet",
        "run",
        "--project",
        str(UNREAL_ASSET_BRIDGE_PROJECT),
        "--",
        *args,
    ]


def _internal_bridge_dll_is_fresh() -> bool:
    if not UNREAL_ASSET_BRIDGE_DLL.exists():
        return False
    try:
        dll_mtime = UNREAL_ASSET_BRIDGE_DLL.stat().st_mtime
        source_mtime = max(
            (UNREAL_ASSET_BRIDGE_PROJECT.parent / "Program.cs").stat().st_mtime,
            UNREAL_ASSET_BRIDGE_PROJECT.stat().st_mtime,
        )
        return dll_mtime >= source_mtime
    except Exception:
        return False


def _clip_summary(clip: dict[str, Any] | None) -> dict[str, Any]:
    data = clip if isinstance(clip, dict) else {}
    curves = data.get("model_curves") if isinstance(data.get("model_curves"), dict) else {}
    return {
        "id": str(data.get("id") or data.get("name") or ""),
        "name": str(data.get("name") or data.get("id") or ""),
        "duration_ms": float(data.get("duration_ms", 0.0) or 0.0),
        "frame_count": int(data.get("frame_count", 0) or 0),
        "sampled_frame_count": int(data.get("sampled_frame_count", 0) or 0),
        "bone_curve_count": len(curves),
        "source_mode": str(data.get("source_mode") or data.get("_exporter") or "unreal_editor_python_batch"),
        "export_path": str(data.get("_export_path") or ""),
    }


def _normalize_animation_clip_payload(payload: dict[str, Any], clip: dict[str, Any]) -> dict[str, Any]:
    out = dict(clip)
    rotation_space = str(out.get("rotation_space") or payload.get("rotation_space") or "")
    if not rotation_space and _legacy_animation_cache_is_usable(payload, out):
        rotation_space = ANIMATION_ROTATION_SPACE
        out["legacy_rotation_space_assumed"] = True
    if rotation_space:
        out["rotation_space"] = rotation_space
    return out


def _legacy_animation_cache_is_usable(payload: dict[str, Any], clip: dict[str, Any]) -> bool:
    """Accept older local caches that already contain Tiger-space bone curves."""

    exporter = str(payload.get("exporter") or clip.get("_exporter") or "").strip().casefold()
    source_mode = str(clip.get("source_mode") or "").strip().casefold()
    if exporter not in {"unreal_editor_python", "cached_animation_clip"} and not source_mode.startswith("unreal_editor_python"):
        return False
    curves = clip.get("model_curves")
    if not isinstance(curves, dict) or not curves:
        return False
    sampled = int(float(clip.get("sampled_frame_count") or payload.get("sampled_frame_count") or 0))
    if sampled < 2:
        return False
    for key, curve in curves.items():
        if not str(key).startswith("bone_") or not isinstance(curve, dict):
            continue
        if isinstance(curve.get("rotation_quat"), dict) and isinstance(curve.get("translation"), dict):
            return True
    return False


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
    "ANIMATION_ROTATION_SPACE",
    "UNREAL_ASSET_BRIDGE_PROJECT",
    "default_owner_unreal_ar_pbr_path",
    "default_owner_unreal_animation_clip_path",
    "export_owner_unreal_ar_pbr_asset",
    "export_owner_unreal_animation_clip",
    "export_owner_unreal_animation_clips_batch",
    "owner_unreal_animation_clip_cache_status",
]
