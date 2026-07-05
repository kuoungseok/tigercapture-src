"""Texture-map planning helpers shared by AR/PBR preview and export paths."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.udim import (
    decode_udim_tiles,
    primary_udim_path,
    udim_metadata_for_path,
)


TEXTURE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp"}

CANONICAL_TEXTURE_MAPS: tuple[str, ...] = (
    "base",
    "roughness",
    "metallic",
    "specular",
    "normal",
    "occlusion",
    "emissive",
    "opacity",
    "height",
)
SCALAR_TEXTURE_MAPS: tuple[str, ...] = (
    "roughness",
    "metallic",
    "specular",
    "occlusion",
    "opacity",
    "height",
)
MATERIAL_TEXTURE_METADATA: tuple[str, ...] = (
    "alpha_mode",
    "alpha_cutoff",
    "emissive_factor",
    "uv_v_flip",
)
TEXTURE_MAP_METADATA: tuple[str, ...] = (
    "wrap_s",
    "wrap_t",
)
ORM_ALIASES: tuple[str, ...] = (
    "orm_map",
    "orm_texture",
    "occlusion_roughness_metallic_map",
    "occlusion_roughness_metallic_texture",
)
METALLIC_ROUGHNESS_ALIASES: tuple[str, ...] = (
    "metallic_roughness_map",
    "metallic_roughness_texture",
)

MAP_ALIASES: dict[str, tuple[str, ...]] = {
    "base": (
        "base_map",
        "base_texture",
        "base_color_map",
        "base_color_texture",
        "albedo_map",
        "albedo_texture",
        "diffuse_map",
        "diffuse_texture",
        "color_map",
        "texture",
    ),
    "roughness": ("roughness_map", "roughness_texture"),
    "metallic": ("metallic_map", "metallic_texture", "metalness_map", "metalness_texture"),
    "specular": ("specular_map", "specular_texture", "reflectance_map", "reflectance_texture"),
    "normal": ("normal_map", "normal_texture", "bump_map", "bump_texture"),
    "occlusion": (
        "occlusion_map",
        "occlusion_texture",
        "ambient_occlusion_map",
        "ambient_occlusion_texture",
        "ao_map",
        "ao_texture",
    ),
    "emissive": (
        "emissive_map",
        "emissive_texture",
        "emission_map",
        "emission_texture",
    ),
    "opacity": (
        "opacity_map",
        "opacity_texture",
        "alpha_map",
        "alpha_texture",
        "mask_map",
        "mask_texture",
    ),
    "height": (
        "height_map",
        "height_texture",
        "displacement_map",
        "displacement_texture",
        "parallax_map",
        "parallax_texture",
        "bump_height_map",
        "bump_height_texture",
    ),
}

_PLAN_CACHE: dict[tuple[str, str, str], tuple[dict[str, dict[str, str]], dict[str, Any]]] = {}
_AVERAGE_CACHE: dict[tuple[str, int, int], tuple[int, int, int]] = {}


def _material_signature(descriptor: Mapping[str, Any]) -> str:
    parts: list[str] = [f"texture_count={int(descriptor.get('texture_count', 0) or 0)}"]
    for material in descriptor.get("materials", []) or []:
        if not isinstance(material, Mapping):
            continue
        fields = [str(material.get("id") or ""), str(material.get("name") or "")]
        for alias in (*ORM_ALIASES, *METALLIC_ROUGHNESS_ALIASES):
            if material.get(alias):
                fields.append(f"{alias}={material.get(alias)}")
        for aliases in MAP_ALIASES.values():
            for alias in aliases:
                if material.get(alias):
                    fields.append(f"{alias}={material.get(alias)}")
        for key in MATERIAL_TEXTURE_METADATA:
            if material.get(key) is not None:
                fields.append(f"{key}={material.get(key)}")
        parts.append("|".join(fields))
    return "\n".join(parts)


def _directory_signature(directory: Path) -> str:
    try:
        rows = []
        for path in directory.iterdir():
            if path.suffix.casefold() not in TEXTURE_EXTS:
                continue
            try:
                st = path.stat()
                rows.append(f"{path.name}:{st.st_size}:{st.st_mtime_ns}")
            except OSError:
                rows.append(path.name)
        return "\n".join(sorted(rows))
    except Exception:
        return ""


def _texture_files(directory: Path) -> dict[str, Path]:
    try:
        return {
            path.name.casefold(): path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in TEXTURE_EXTS
        }
    except Exception:
        return {}


def _resolve_texture_path(asset_dir: Path, raw: Any) -> tuple[str, bool]:
    text = str(raw or "").strip()
    if not text:
        return "", False
    path = Path(text)
    candidates = [path] if path.is_absolute() else [asset_dir / path, Path(text)]
    for candidate in candidates:
        try:
            if candidate.exists():
                return str(candidate.resolve()), True
        except Exception:
            pass
    for candidate in candidates:
        primary = primary_udim_path(candidate)
        if primary:
            return primary, True
    return str(candidates[0]), False


def _find_texture(files: Mapping[str, Path], required: tuple[str, ...]) -> str | None:
    required_lower = tuple(part.casefold() for part in required if part)
    for name, path in files.items():
        if all(part in name for part in required_lower):
            return str(path)
    return None


def _group_from_material_name(name: str) -> str:
    lowered = str(name or "").casefold()
    if "wheel" in lowered:
        return "wheel"
    if "body" in lowered or "paint" in lowered or "car" in lowered:
        return "body"
    if "glass" in lowered or "window" in lowered:
        return "glass"
    if "skin" in lowered or "face" in lowered:
        return "skin"
    return ""


def _heuristic_maps_for_material(files: Mapping[str, Path], material_name: str) -> dict[str, str]:
    group = _group_from_material_name(material_name)
    candidates: dict[str, tuple[tuple[str, ...], ...]] = {}
    if group == "body":
        candidates = {
            "base": ((group, "bodyd"), (group, "albedo"), (group, "base"), (group, "diff"), (group, "d.png")),
            "metallic": ((group, "bodym"), (group, "metal"), (group, "m.png")),
            "roughness": ((group, "bodyr"), (group, "rough"), (group, "r.png")),
            "specular": ((group, "bodys"), (group, "spec"), (group, "s.png")),
            "normal": ((group, "bodyn"), (group, "normal"), (group, "n.png")),
            "occlusion": ((group, "bodyao"), (group, "occlusion"), (group, "ao")),
            "emissive": ((group, "bodyemissive"), (group, "emissive"), (group, "emission")),
            "opacity": ((group, "bodyopacity"), (group, "opacity"), (group, "alpha"), (group, "mask")),
            "height": ((group, "bodyheight"), (group, "height"), (group, "displacement"), (group, "disp"), (group, "parallax")),
        }
    elif group == "wheel":
        candidates = {
            "base": ((group, "wheeld"), (group, "albedo"), (group, "base"), (group, "diff"), (group, "d.png")),
            "metallic": ((group, "wheelm"), (group, "metal"), (group, "m.png")),
            "roughness": ((group, "rough"), (group, "r.png")),
            "specular": ((group, "specular"), (group, "spec"), (group, "s.png")),
            "normal": ((group, "wheeln"), (group, "normal"), (group, "n.png")),
            "occlusion": ((group, "wheelao"), (group, "occlusion"), (group, "ao")),
            "emissive": ((group, "emissive"), (group, "emission")),
            "opacity": ((group, "opacity"), (group, "alpha"), (group, "mask")),
            "height": ((group, "height"), (group, "displacement"), (group, "disp"), (group, "parallax")),
        }
    elif group:
        candidates = {
            "base": ((group, "albedo"), (group, "base"), (group, "diff"), (group, "d.png")),
            "roughness": ((group, "rough"), (group, "r.png")),
            "normal": ((group, "normal"), (group, "n.png")),
            "occlusion": ((group, "occlusion"), (group, "ao")),
            "emissive": ((group, "emissive"), (group, "emission")),
            "opacity": ((group, "opacity"), (group, "alpha"), (group, "mask")),
            "height": ((group, "height"), (group, "displacement"), (group, "disp"), (group, "parallax")),
        }
    maps: dict[str, str] = {}
    for map_name, groups in candidates.items():
        for required in groups:
            found = _find_texture(files, required)
            if found:
                maps[map_name] = found
                break
    return maps


def _first_resolved_alias(
    *,
    asset_dir: Path,
    material: Mapping[str, Any],
    aliases: tuple[str, ...],
    material_name: str,
    missing: list[dict[str, str]],
    missing_map_name: str,
) -> tuple[str, bool]:
    for alias in aliases:
        raw = material.get(alias)
        if not raw:
            continue
        resolved, exists = _resolve_texture_path(asset_dir, raw)
        if exists:
            return resolved, True
        missing.append({"material": material_name, "map": missing_map_name, "path": resolved})
        return "", True
    return "", False


def _copy_material_metadata(maps: dict[str, str], material: Mapping[str, Any]) -> None:
    for key in MATERIAL_TEXTURE_METADATA:
        if material.get(key) is None:
            continue
        value = material.get(key)
        if isinstance(value, (list, tuple)):
            maps[key] = ",".join(str(item) for item in value)
        else:
            maps[key] = str(value)


def _copy_texture_map_metadata(maps: dict[str, str], material: Mapping[str, Any], map_name: str) -> None:
    for suffix in TEXTURE_MAP_METADATA:
        value = material.get(f"{map_name}_{suffix}")
        if value is None:
            value = material.get(suffix)
        if value is not None:
            maps[f"{map_name}_{suffix}"] = str(value)


def _copy_udim_metadata(maps: dict[str, str], map_name: str, path: str) -> None:
    meta = udim_metadata_for_path(path)
    if not bool(meta.get("enabled")):
        return
    tiles = decode_udim_tiles(meta.get("tiles_json"))
    if not tiles:
        return
    maps[f"{map_name}_udim_tiles"] = str(meta["tiles_json"])
    maps[f"{map_name}_udim_tile_count"] = str(int(meta["tile_count"]))
    maps[f"{map_name}_udim_primary_tile"] = str(int(meta["primary_tile"]))
    maps[f"{map_name}_udim_sampling_model"] = str(meta["sampling_model"])


def resolve_material_texture_plan(
    asset_path: str | Path | None,
    descriptor: Mapping[str, Any],
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Return material -> texture-map path plan plus a product-facing summary.

    The GL preview packet shader still uses a cheap base-map average tint, while
    headless export can sample UV texture triangles from this plan. Both paths
    use the same readiness diagnostics so missing or unresolved texture maps are
    not hidden behind a flat material color.
    """
    asset = Path(str(asset_path or ""))
    asset_dir = asset.parent if str(asset) else Path.cwd()
    key = (str(asset), _material_signature(descriptor), _directory_signature(asset_dir))
    cached = _PLAN_CACHE.get(key)
    if cached is not None:
        plan, diag = cached
        return deepcopy(plan), deepcopy(diag)

    files = _texture_files(asset_dir)
    plan: dict[str, dict[str, str]] = {}
    missing: list[dict[str, str]] = []
    explicit_reference_count = 0
    materials = [m for m in descriptor.get("materials", []) or [] if isinstance(m, Mapping)]

    for idx, material in enumerate(materials):
        name = str(material.get("name") or material.get("id") or f"material_{idx}")
        maps: dict[str, str] = {}
        orm_path, orm_referenced = _first_resolved_alias(
            asset_dir=asset_dir,
            material=material,
            aliases=ORM_ALIASES,
            material_name=name,
            missing=missing,
            missing_map_name="orm",
        )
        if orm_referenced:
            explicit_reference_count += 1
        if orm_path:
            for map_name, channel in (("occlusion", "r"), ("roughness", "g"), ("metallic", "b")):
                maps[map_name] = orm_path
                maps[f"{map_name}_channel"] = channel
                _copy_texture_map_metadata(maps, material, map_name)
                _copy_udim_metadata(maps, map_name, orm_path)
        metal_rough_path, metal_rough_referenced = _first_resolved_alias(
            asset_dir=asset_dir,
            material=material,
            aliases=METALLIC_ROUGHNESS_ALIASES,
            material_name=name,
            missing=missing,
            missing_map_name="metallic_roughness",
        )
        if metal_rough_referenced:
            explicit_reference_count += 1
        if metal_rough_path:
            for map_name, channel in (("roughness", "g"), ("metallic", "b")):
                maps[map_name] = metal_rough_path
                maps[f"{map_name}_channel"] = channel
                _copy_texture_map_metadata(maps, material, map_name)
                _copy_udim_metadata(maps, map_name, metal_rough_path)
        for map_name, aliases in MAP_ALIASES.items():
            for alias in aliases:
                raw = material.get(alias)
                if not raw:
                    continue
                explicit_reference_count += 1
                resolved, exists = _resolve_texture_path(asset_dir, raw)
                if exists:
                    maps[map_name] = resolved
                    _copy_udim_metadata(maps, map_name, resolved)
                    channel = material.get(f"{map_name}_channel")
                    if channel:
                        maps[f"{map_name}_channel"] = str(channel)
                    _copy_texture_map_metadata(maps, material, map_name)
                else:
                    missing.append({"material": name, "map": map_name, "path": resolved})
                break
        if not maps:
            maps = _heuristic_maps_for_material(files, name)
        if maps:
            for map_name in CANONICAL_TEXTURE_MAPS:
                if maps.get(map_name):
                    _copy_udim_metadata(maps, map_name, str(maps[map_name]))
            _copy_material_metadata(maps, material)
            plan[name] = maps

    map_count = sum(1 for maps in plan.values() for key in CANONICAL_TEXTURE_MAPS if maps.get(key))
    udim_maps: list[dict[str, Any]] = []
    for material_name, maps in plan.items():
        for map_name in CANONICAL_TEXTURE_MAPS:
            tiles = decode_udim_tiles(maps.get(f"{map_name}_udim_tiles"))
            if not tiles:
                continue
            udim_maps.append({
                "material": str(material_name),
                "map": map_name,
                "tile_count": len(tiles),
                "primary_tile": int(maps.get(f"{map_name}_udim_primary_tile") or 0),
                "tiles": sorted(int(tile) for tile in tiles),
            })
    descriptor_texture_count = int(descriptor.get("texture_count", 0) or 0)
    if missing:
        status = "missing"
    elif map_count > 0:
        status = "ready"
    elif descriptor_texture_count > 0 or explicit_reference_count > 0:
        status = "referenced"
    else:
        status = "none"
    diag = {
        "status": status,
        "directory": str(asset_dir),
        "material_count": len(materials),
        "planned_material_count": len(plan),
        "map_count": map_count,
        "base_map_count": sum(1 for maps in plan.values() if maps.get("base")),
        "roughness_map_count": sum(1 for maps in plan.values() if maps.get("roughness")),
        "metallic_map_count": sum(1 for maps in plan.values() if maps.get("metallic")),
        "normal_map_count": sum(1 for maps in plan.values() if maps.get("normal")),
        "occlusion_map_count": sum(1 for maps in plan.values() if maps.get("occlusion")),
        "emissive_map_count": sum(1 for maps in plan.values() if maps.get("emissive")),
        "opacity_map_count": sum(1 for maps in plan.values() if maps.get("opacity")),
        "height_map_count": sum(1 for maps in plan.values() if maps.get("height")),
        "udim_material_count": len({row["material"] for row in udim_maps}),
        "udim_map_count": len(udim_maps),
        "udim_tile_count": sum(int(row["tile_count"]) for row in udim_maps),
        "udim_maps": udim_maps,
        "udim_status": "ready" if udim_maps else "none",
        "udim_sampling_model": "uv_integer_tile_lookup",
        "orm_material_count": sum(
            1
            for maps in plan.values()
            if maps.get("occlusion")
            and maps.get("occlusion") == maps.get("roughness") == maps.get("metallic")
            and maps.get("occlusion_channel") == "r"
            and maps.get("roughness_channel") == "g"
            and maps.get("metallic_channel") == "b"
        ),
        "missing_count": len(missing),
        "missing": missing,
        "descriptor_texture_count": descriptor_texture_count,
        "explicit_reference_count": explicit_reference_count,
        "normal_map_status": "enabled_when_material_has_normal_map",
        "occlusion_map_status": "enabled_when_material_has_occlusion_map",
        "emissive_map_status": "enabled_when_material_has_emissive_map",
        "opacity_map_status": "enabled_when_material_has_opacity_map_or_base_alpha",
        "height_map_status": "enabled_when_material_has_height_or_displacement_map",
        "material_map_contract": list(CANONICAL_TEXTURE_MAPS),
    }
    _PLAN_CACHE[key] = (deepcopy(plan), deepcopy(diag))
    return plan, diag


def _average_rgb(path: str) -> tuple[int, int, int] | None:
    try:
        p = Path(path)
        st = p.stat()
        key = (str(p.resolve()), int(st.st_size), int(st.st_mtime_ns))
        cached = _AVERAGE_CACHE.get(key)
        if cached is not None:
            return cached
        from PIL import Image
        import numpy as np

        image = Image.open(p).convert("RGB")
        image.thumbnail((32, 32), Image.Resampling.BILINEAR)
        arr = np.asarray(image, dtype=np.float32)
        if arr.size <= 0:
            return None
        rgb = tuple(max(0, min(255, int(round(v)))) for v in arr.reshape(-1, 3).mean(axis=0))
        _AVERAGE_CACHE[key] = rgb  # type: ignore[assignment]
        return rgb  # type: ignore[return-value]
    except Exception:
        return None


def material_base_texture_color(
    texture_plan: Mapping[str, Mapping[str, str]],
    material: Mapping[str, Any],
    *,
    alpha: int = 255,
) -> tuple[int, int, int, int] | None:
    if not texture_plan:
        return None
    material_name = str(material.get("name") or material.get("id") or "")
    maps = texture_plan.get(material_name) if material_name else None
    if maps is None and len(texture_plan) == 1:
        maps = next(iter(texture_plan.values()))
    if not isinstance(maps, Mapping):
        return None
    base = maps.get("base")
    if not base:
        return None
    rgb = _average_rgb(str(base))
    if rgb is None:
        return None
    return (rgb[0], rgb[1], rgb[2], max(0, min(255, int(alpha))))


def material_base_texture_path(
    texture_plan: Mapping[str, Mapping[str, str]],
    material: Mapping[str, Any],
) -> str:
    if not texture_plan:
        return ""
    material_name = str(material.get("name") or material.get("id") or "")
    maps = texture_plan.get(material_name) if material_name else None
    if maps is None and len(texture_plan) == 1:
        maps = next(iter(texture_plan.values()))
    if not isinstance(maps, Mapping):
        return ""
    return str(maps.get("base") or "")
