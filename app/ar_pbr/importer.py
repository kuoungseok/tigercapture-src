"""3D asset import adapter for AR/PBR tracks.

The importer is intentionally UI-neutral and dependency-light. It accepts FBX as
a first-class source format, tries optional scene loaders when available, and
returns a stable placeholder descriptor when real import is unavailable.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.fbx_ascii import parse_ascii_fbx_metadata
from app.ar_pbr.fbx_binary import parse_binary_fbx_metadata
from app.ar_pbr.gltf_loader import GLTF_EXTS, parse_gltf_metadata
from app.ar_pbr.schema import SUPPORTED_ASSET_EXTS, normalize_ar_track


FBX_EXTS = frozenset({".fbx"})
RUNTIME_PREFERRED_FORMAT = "glb"
DESCRIPTOR_CACHE_SCHEMA_VERSION = 3


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def importer_backend_status() -> dict[str, Any]:
    """Return optional importer dependency availability without importing them."""
    autodesk_fbx_sdk = _module_available("fbx") or _module_available("FbxCommon")
    return {
        "fbx_supported": True,
        "external_renderer_required": False,
        "available_backends": {
            "internal_ascii_fbx": True,
            "internal_binary_fbx": True,
            "internal_gltf": True,
            "internal_vrm": True,
            "trimesh": _module_available("trimesh"),
            "pyassimp": _module_available("pyassimp"),
            "autodesk_fbx_sdk": autodesk_fbx_sdk,
        },
        "preferred_runtime_format": RUNTIME_PREFERRED_FORMAT,
        "notes": [
            "FBX is accepted as source data.",
            "VRM is accepted through the internal GLB/glTF avatar path.",
            "Runtime rendering should prefer GLB/glTF-style PBR materials.",
            "Optional import backends are lazy-loaded only during import.",
        ],
    }


def resolve_asset_path(asset_path: str | Path, project_root: str | Path | None = None) -> Path:
    path = Path(asset_path)
    if path.is_absolute() or project_root is None:
        return path
    return Path(project_root) / path


def _asset_id(path: Path) -> str:
    try:
        stat = path.stat()
        seed = f"{path.resolve()}:{stat.st_size}:{stat.st_mtime_ns}"
    except Exception:
        seed = str(path)
    return "asset_" + hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _descriptor_cache_disabled(settings: Mapping[str, Any]) -> bool:
    if bool(settings.get("disable_descriptor_cache", False)):
        return True
    import os

    value = os.environ.get("TIGERCAPTURE_DISABLE_AR_PBR_DESCRIPTOR_CACHE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _descriptor_cache_matches(
    descriptor: Mapping[str, Any],
    path: Path,
    *,
    max_triangles_per_geometry: int,
) -> bool:
    try:
        st = path.stat()
        cache = descriptor.get("cache") if isinstance(descriptor.get("cache"), Mapping) else {}
        if int(cache.get("source_size", -1)) != int(st.st_size):
            return False
        if int(cache.get("source_mtime_ns", -1)) != int(st.st_mtime_ns):
            return False
        if int(cache.get("schema_version", 0) or 0) != DESCRIPTOR_CACHE_SCHEMA_VERSION:
            return False
        cached_triangles = int(cache.get("max_triangles_per_geometry", 0) or 0)
        return cached_triangles >= int(max_triangles_per_geometry)
    except Exception:
        return False


def _attach_descriptor_cache_metadata(
    descriptor: dict[str, Any],
    path: Path,
    *,
    max_triangles_per_geometry: int,
) -> dict[str, Any]:
    try:
        st = path.stat()
        descriptor["cache"] = {
            **(descriptor.get("cache") if isinstance(descriptor.get("cache"), dict) else {}),
            "source_size": int(st.st_size),
            "source_mtime_ns": int(st.st_mtime_ns),
            "max_triangles_per_geometry": int(max_triangles_per_geometry),
            "schema_version": DESCRIPTOR_CACHE_SCHEMA_VERSION,
        }
    except Exception:
        pass
    return descriptor


def _base_descriptor(path: Path, ext: str, *, state: str, backend: str) -> dict[str, Any]:
    return {
        "id": _asset_id(path),
        "type": "ar_pbr_asset",
        "source_path": str(path),
        "source_ext": ext,
        "source_format": ext.lstrip("."),
        "runtime_format": "ar_scene_descriptor",
        "preferred_runtime_format": RUNTIME_PREFERRED_FORMAT,
        "requires_runtime_conversion": ext in FBX_EXTS,
        "import_state": state,
        "backend": backend,
        "mesh_count": 0,
        "material_count": 0,
        "animation_count": 0,
        "animation_clips": [],
        "skeletal_mesh_count": 0,
        "skin_count": 0,
        "skeletons": [],
        "bones": [],
        "bounds": {
            "center": [0.0, 0.0, 0.0],
            "size": [1.0, 1.0, 1.0],
        },
        "source_fbx_version": None,
        "units": {
            "scale_to_meters": 1.0,
            "source": "unknown",
        },
        "axes": {
            "up": "Y",
            "forward": "-Z",
            "source": "assumed",
        },
        "geometries": [],
        "models": [],
        "materials": [],
        "connections": [],
        "warnings": [],
    }


def _base_diagnostics(path: Path, ext: str) -> dict[str, Any]:
    status = importer_backend_status()
    return {
        "ok": True,
        "imported": False,
        "fallback": False,
        "backend": "",
        "asset_path": str(path),
        "source_ext": ext,
        "path_exists": path.exists(),
        "fbx_source": ext in FBX_EXTS,
        "gltf_source": ext in GLTF_EXTS,
        "vrm_source": ext == ".vrm",
        "available_backends": status["available_backends"],
        "warnings": [],
        "errors": [],
    }


def _placeholder(
    path: Path,
    ext: str,
    diagnostics: dict[str, Any],
    reason: str,
    *,
    ok: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor = _base_descriptor(path, ext, state="placeholder", backend="placeholder")
    descriptor["warnings"].append(reason)
    diagnostics["ok"] = bool(ok)
    diagnostics["fallback"] = True
    diagnostics["backend"] = "placeholder"
    if ok:
        diagnostics["warnings"].append(reason)
    else:
        diagnostics["errors"].append(reason)
    return descriptor, diagnostics


def _attach_support_report(
    descriptor: dict[str, Any],
    diagnostics: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.ar_pbr.asset_support import classify_asset_support

    support = classify_asset_support(descriptor, diagnostics)
    descriptor["support"] = support
    diagnostics["support"] = support
    return descriptor, diagnostics


def _bounds_from_any(bounds: Any) -> dict[str, list[float]]:
    try:
        import numpy as np

        arr = np.asarray(bounds, dtype=np.float64)
        if arr.shape != (2, 3):
            raise ValueError("bounds must be 2x3")
        lo = arr[0]
        hi = arr[1]
        center = (lo + hi) * 0.5
        size = np.maximum(hi - lo, 0.0)
        return {
            "center": [float(v) for v in center],
            "size": [float(max(v, 1e-6)) for v in size],
        }
    except Exception:
        return {
            "center": [0.0, 0.0, 0.0],
            "size": [1.0, 1.0, 1.0],
        }


def _material_name(material: Any, fallback: str) -> str:
    name = getattr(material, "name", None)
    if name:
        return str(name)
    return fallback


def _summarize_trimesh_scene(scene: Any, path: Path, ext: str) -> dict[str, Any]:
    descriptor = _base_descriptor(path, ext, state="ready", backend="trimesh")
    geometry = getattr(scene, "geometry", None)
    if isinstance(geometry, Mapping):
        meshes = list(geometry.values())
    else:
        meshes = [scene]

    materials: list[dict[str, Any]] = []
    for idx, mesh in enumerate(meshes):
        visual = getattr(mesh, "visual", None)
        material = getattr(visual, "material", None)
        if material is not None:
            materials.append({"name": _material_name(material, f"material_{idx}")})

    descriptor["mesh_count"] = len(meshes)
    descriptor["material_count"] = len(materials)
    descriptor["materials"] = materials
    descriptor["bounds"] = _bounds_from_any(getattr(scene, "bounds", None))
    return descriptor


def _import_with_trimesh(path: Path, ext: str) -> tuple[dict[str, Any], str]:
    try:
        import trimesh
    except Exception as exc:
        return {}, f"trimesh unavailable: {type(exc).__name__}"

    try:
        scene = trimesh.load(str(path), force="scene", process=False)
        return _summarize_trimesh_scene(scene, path, ext), ""
    except Exception as exc:
        return {}, f"trimesh failed: {type(exc).__name__}: {exc}"


def _summarize_pyassimp_scene(scene: Any, path: Path, ext: str) -> dict[str, Any]:
    descriptor = _base_descriptor(path, ext, state="ready", backend="pyassimp")
    meshes = getattr(scene, "meshes", []) or []
    materials = getattr(scene, "materials", []) or []
    animations = getattr(scene, "animations", []) or []
    descriptor["mesh_count"] = len(meshes)
    descriptor["material_count"] = len(materials)
    descriptor["animation_count"] = len(animations)
    descriptor["materials"] = [
        {"name": str(getattr(material, "name", None) or f"material_{idx}")}
        for idx, material in enumerate(materials)
    ]
    return descriptor


def _descriptor_from_ascii_fbx(path: Path, ext: str, metadata: dict[str, Any]) -> dict[str, Any]:
    descriptor = _base_descriptor(path, ext, state="ready", backend=str(metadata.get("parser") or "internal_ascii_fbx"))
    descriptor["source_fbx_version"] = metadata.get("fbx_version")
    descriptor["mesh_count"] = int(metadata.get("mesh_count") or 0)
    descriptor["material_count"] = int(metadata.get("material_count") or 0)
    descriptor["animation_count"] = int(metadata.get("animation_count") or 0)
    descriptor["animation_clips"] = metadata.get("animation_clips") or []
    descriptor["skeletal_mesh_count"] = int(metadata.get("skeletal_mesh_count") or 0)
    descriptor["skin_count"] = int(metadata.get("skin_count") or 0)
    descriptor["skeletons"] = metadata.get("skeletons") or []
    descriptor["bones"] = metadata.get("bones") or []
    descriptor["texture_count"] = int(metadata.get("texture_count") or 0)
    descriptor["bounds"] = metadata.get("bounds") or descriptor["bounds"]
    descriptor["units"] = metadata.get("units") or descriptor["units"]
    descriptor["axes"] = metadata.get("axes") or descriptor["axes"]
    descriptor["geometries"] = metadata.get("geometries") or []
    descriptor["models"] = metadata.get("models") or []
    descriptor["materials"] = metadata.get("materials") or []
    descriptor["connections"] = metadata.get("connections") or []
    descriptor["warnings"].extend(metadata.get("warnings") or [])
    return descriptor


def _descriptor_from_gltf(path: Path, ext: str, metadata: dict[str, Any]) -> dict[str, Any]:
    descriptor = _base_descriptor(path, ext, state="ready", backend=str(metadata.get("parser") or "internal_gltf"))
    descriptor["source_gltf_version"] = metadata.get("gltf_version")
    descriptor["extensions_used"] = metadata.get("extensions_used") or []
    descriptor["extensions_required"] = metadata.get("extensions_required") or []
    descriptor["vrm"] = metadata.get("vrm") or {}
    descriptor["render_profiles"] = metadata.get("render_profiles") or {}
    descriptor["mesh_count"] = int(metadata.get("mesh_count") or 0)
    descriptor["material_count"] = int(metadata.get("material_count") or 0)
    descriptor["animation_count"] = int(metadata.get("animation_count") or 0)
    descriptor["animation_clips"] = metadata.get("animation_clips") or []
    descriptor["skeletal_mesh_count"] = int(metadata.get("skeletal_mesh_count") or 0)
    descriptor["skin_count"] = int(metadata.get("skin_count") or 0)
    descriptor["skeletons"] = metadata.get("skeletons") or []
    descriptor["bones"] = metadata.get("bones") or []
    descriptor["texture_count"] = int(metadata.get("texture_count") or 0)
    descriptor["bounds"] = metadata.get("bounds") or descriptor["bounds"]
    descriptor["units"] = metadata.get("units") or descriptor["units"]
    descriptor["axes"] = metadata.get("axes") or descriptor["axes"]
    descriptor["geometries"] = metadata.get("geometries") or []
    descriptor["models"] = metadata.get("models") or []
    descriptor["materials"] = metadata.get("materials") or []
    descriptor["connections"] = metadata.get("connections") or []
    descriptor["warnings"].extend(metadata.get("warnings") or [])
    return descriptor


def _import_with_pyassimp(path: Path, ext: str) -> tuple[dict[str, Any], str]:
    try:
        import pyassimp
    except Exception as exc:
        return {}, f"pyassimp unavailable: {type(exc).__name__}"

    scene = None
    try:
        scene = pyassimp.load(str(path))
        return _summarize_pyassimp_scene(scene, path, ext), ""
    except Exception as exc:
        return {}, f"pyassimp failed: {type(exc).__name__}: {exc}"
    finally:
        if scene is not None:
            try:
                pyassimp.release(scene)
            except Exception:
                pass


def _import_scene(
    path: Path,
    ext: str,
    diagnostics: dict[str, Any],
    *,
    placeholder_ok: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    descriptor, error = _import_with_trimesh(path, ext)
    if descriptor:
        diagnostics["imported"] = True
        diagnostics["backend"] = "trimesh"
        return descriptor, diagnostics
    diagnostics["warnings"].append(error)
    return _placeholder(path, ext, diagnostics, "no usable scene importer backend", ok=placeholder_ok)


def _import_fbx(
    path: Path,
    ext: str,
    diagnostics: dict[str, Any],
    *,
    placeholder_ok: bool,
    max_triangles_per_geometry: int = 12000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    errors: list[str] = []

    metadata, error = parse_ascii_fbx_metadata(path)
    if metadata:
        diagnostics["imported"] = True
        diagnostics["backend"] = "internal_ascii_fbx"
        return _descriptor_from_ascii_fbx(path, ext, metadata), diagnostics
    errors.append(error)

    metadata, error = parse_binary_fbx_metadata(path, max_triangles_per_geometry=max_triangles_per_geometry)
    if metadata:
        diagnostics["imported"] = True
        diagnostics["backend"] = "internal_binary_fbx"
        diagnostics["warnings"].extend(metadata.get("warnings") or [])
        return _descriptor_from_ascii_fbx(path, ext, metadata), diagnostics
    errors.append(error)

    descriptor, error = _import_with_trimesh(path, ext)
    if descriptor:
        diagnostics["imported"] = True
        diagnostics["backend"] = "trimesh"
        return descriptor, diagnostics
    errors.append(error)

    descriptor, error = _import_with_pyassimp(path, ext)
    if descriptor:
        diagnostics["imported"] = True
        diagnostics["backend"] = "pyassimp"
        return descriptor, diagnostics
    errors.append(error)

    if diagnostics["available_backends"].get("autodesk_fbx_sdk"):
        errors.append("autodesk_fbx_sdk detected but adapter is not implemented yet")
    else:
        errors.append("autodesk_fbx_sdk unavailable")

    diagnostics["warnings"].extend(err for err in errors if err)
    return _placeholder(path, ext, diagnostics, "FBX importer backend unavailable or failed", ok=placeholder_ok)


def _import_gltf(
    path: Path,
    ext: str,
    diagnostics: dict[str, Any],
    *,
    placeholder_ok: bool,
    max_triangles_per_geometry: int = 12000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    metadata, error = parse_gltf_metadata(path, max_triangles_per_geometry=max_triangles_per_geometry)
    if metadata:
        diagnostics["imported"] = True
        diagnostics["backend"] = "internal_gltf"
        diagnostics["warnings"].extend(metadata.get("warnings") or [])
        return _descriptor_from_gltf(path, ext, metadata), diagnostics
    diagnostics["warnings"].append(error)

    descriptor, error = _import_with_trimesh(path, ext)
    if descriptor:
        diagnostics["imported"] = True
        diagnostics["backend"] = "trimesh"
        return descriptor, diagnostics
    diagnostics["warnings"].append(error)
    return _placeholder(path, ext, diagnostics, "glTF importer backend unavailable or failed", ok=placeholder_ok)


def import_asset(
    asset_path: str | Path,
    *,
    project_root: str | Path | None = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import or inspect a 3D asset and return descriptor plus diagnostics.

    `settings` currently supports:
    - `placeholder_on_error`: default true. When false, unsupported or missing
      assets set diagnostics["ok"] to false while still returning a descriptor.
    """
    settings_map = settings or {}
    placeholder_ok = bool(settings_map.get("placeholder_on_error", True))
    max_triangles = int(settings_map.get("max_triangles_per_geometry", 12000) or 12000)
    path = resolve_asset_path(asset_path, project_root)
    ext = path.suffix.casefold()
    diagnostics = _base_diagnostics(path, ext)

    if ext not in SUPPORTED_ASSET_EXTS:
        descriptor, diagnostics = _placeholder(
            path,
            ext,
            diagnostics,
            f"unsupported asset extension: {ext or '<none>'}",
            ok=False,
        )
        return _attach_support_report(descriptor, diagnostics)
    if not path.exists():
        descriptor, diagnostics = _placeholder(path, ext, diagnostics, "asset file does not exist", ok=placeholder_ok)
        return _attach_support_report(descriptor, diagnostics)

    if not _descriptor_cache_disabled(settings_map):
        try:
            from app.ar_pbr.asset_cache import load_asset_descriptor

            cached = load_asset_descriptor(_asset_id(path))
            if isinstance(cached, dict) and _descriptor_cache_matches(
                cached,
                path,
                max_triangles_per_geometry=max(100, max_triangles),
            ):
                diagnostics["ok"] = True
                diagnostics["imported"] = True
                diagnostics["cached"] = True
                diagnostics["backend"] = str(cached.get("backend") or "descriptor_cache")
                diagnostics["warnings"].append("loaded ar/pbr asset descriptor from persistent cache")
                return _attach_support_report(dict(cached), diagnostics)
        except Exception as exc:
            diagnostics["warnings"].append(f"descriptor cache read failed: {type(exc).__name__}")

    if ext in FBX_EXTS:
        descriptor, diagnostics = _import_fbx(
            path,
            ext,
            diagnostics,
            placeholder_ok=placeholder_ok,
            max_triangles_per_geometry=max(100, max_triangles),
        )
    elif ext in GLTF_EXTS:
        descriptor, diagnostics = _import_gltf(
            path,
            ext,
            diagnostics,
            placeholder_ok=placeholder_ok,
            max_triangles_per_geometry=max(100, max_triangles),
        )
    else:
        descriptor, diagnostics = _import_scene(path, ext, diagnostics, placeholder_ok=placeholder_ok)

    descriptor = _attach_descriptor_cache_metadata(
        descriptor,
        path,
        max_triangles_per_geometry=max(100, max_triangles),
    )
    descriptor, diagnostics = _attach_support_report(descriptor, diagnostics)
    if not _descriptor_cache_disabled(settings_map):
        try:
            from app.ar_pbr.asset_cache import store_asset_descriptor

            cache_info = store_asset_descriptor(descriptor, diagnostics=diagnostics)
            diagnostics["descriptor_cache"] = cache_info
        except Exception as exc:
            diagnostics.setdefault("warnings", []).append(f"descriptor cache write failed: {type(exc).__name__}")
    return descriptor, diagnostics


def import_track_asset(
    track: Mapping[str, Any],
    *,
    project_root: str | Path | None = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Import the asset referenced by an AR/PBR track."""
    normalized = normalize_ar_track(track)
    asset_path = str(normalized.get("asset_path") or "")
    if not asset_path:
        path = resolve_asset_path("", project_root)
        diagnostics = _base_diagnostics(path, "")
        descriptor, diagnostics = _placeholder(path, "", diagnostics, "track has no asset_path", ok=False)
        return _attach_support_report(descriptor, diagnostics)
    descriptor, diagnostics = import_asset(asset_path, project_root=project_root, settings=settings)
    diagnostics["track_id"] = normalized["id"]
    descriptor["track_id"] = normalized["id"]
    return descriptor, diagnostics
