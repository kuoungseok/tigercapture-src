"""Render-profile detection for 3D/AR-PBR assets."""
from __future__ import annotations

from typing import Any, Mapping


AR_PBR_RENDER_PROFILE_SCHEMA = "tigerstudio.ar_pbr.render_profiles.v1"
PROFILE_AUTHORED = "authored"
PROFILE_MARMOSET_PBR = "marmoset_pbr"


def inspect_asset_render_profiles_from_gltf(gltf: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return render profiles available from source glTF/GLB/VRM data.

    `authored` preserves the source shader intent, including VRM MToon. The
    Marmoset-style PBR profile is optional and exposed only when explicit glTF
    PBR material data exists.
    """
    doc = gltf if isinstance(gltf, Mapping) else {}
    source_style = _source_style(doc)
    has_mtoon = _has_mtoon(doc)
    pbr_materials = _pbr_material_summaries(doc, ignore_factor_only=has_mtoon)
    pbr_available = bool(pbr_materials)
    return _profile_payload(
        source_style=source_style,
        pbr_materials=pbr_materials,
        pbr_reason="explicit glTF PBR material data found" if pbr_available else "no explicit PBR maps/factors in source",
    )


def inspect_asset_render_profiles_from_descriptor(descriptor: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return render profiles available from an imported asset descriptor."""
    desc = descriptor if isinstance(descriptor, Mapping) else {}
    existing = desc.get("render_profiles") if isinstance(desc.get("render_profiles"), Mapping) else {}
    if existing.get("schema") == AR_PBR_RENDER_PROFILE_SCHEMA:
        return dict(existing)
    materials = [item for item in desc.get("materials", []) or [] if isinstance(item, Mapping)]
    source_style = _descriptor_source_style(desc, materials)
    pbr_materials = []
    for idx, material in enumerate(materials):
        maps = _descriptor_pbr_maps(material)
        factors = _descriptor_pbr_factors(material)
        if maps or factors:
            pbr_materials.append({
                "index": idx,
                "name": str(material.get("name") or material.get("id") or f"material_{idx}"),
                "maps": sorted(maps),
                "factors": sorted(factors),
                "map_count": len(maps),
            })
    pbr_available = bool(pbr_materials)
    return _profile_payload(
        source_style=source_style,
        pbr_materials=pbr_materials,
        pbr_reason="explicit descriptor PBR material data found" if pbr_available else "no explicit PBR maps/factors in descriptor",
    )


def marmoset_pbr_available(render_profiles: Mapping[str, Any] | None) -> bool:
    profiles = render_profiles if isinstance(render_profiles, Mapping) else {}
    pbr = (profiles.get("profiles") or {}).get(PROFILE_MARMOSET_PBR) if isinstance(profiles.get("profiles"), Mapping) else {}
    return bool(isinstance(pbr, Mapping) and pbr.get("available"))


def _profile_payload(
    *,
    source_style: str,
    pbr_materials: list[dict[str, Any]],
    pbr_reason: str,
) -> dict[str, Any]:
    pbr_available = bool(pbr_materials)
    available_profiles = [PROFILE_AUTHORED]
    if pbr_available:
        available_profiles.append(PROFILE_MARMOSET_PBR)
    return {
        "schema": AR_PBR_RENDER_PROFILE_SCHEMA,
        "default_profile": PROFILE_AUTHORED,
        "active_profile": PROFILE_AUTHORED,
        "source_style": source_style,
        "available_profiles": available_profiles,
        "profiles": {
            PROFILE_AUTHORED: {
                "id": PROFILE_AUTHORED,
                "label": "Authored material",
                "available": True,
                "default": True,
                "style": source_style,
                "preserves_source_shader": True,
            },
            PROFILE_MARMOSET_PBR: {
                "id": PROFILE_MARMOSET_PBR,
                "label": "Marmoset-style PBR",
                "available": pbr_available,
                "default": False,
                "style": "ibl_pbr",
                "optional": True,
                "requires_pbr_data": True,
                "material_count": len(pbr_materials),
                "map_count": sum(int(row.get("map_count", 0) or 0) for row in pbr_materials),
                "materials": pbr_materials,
                "reason": pbr_reason,
            },
        },
    }


def _source_style(gltf: Mapping[str, Any]) -> str:
    if _has_mtoon(gltf):
        return "vrm_mtoon"
    if _has_vrm_extension(gltf):
        return "vrm_authored"
    if _pbr_material_summaries(gltf):
        return "gltf_pbr"
    return "authored"


def _descriptor_source_style(descriptor: Mapping[str, Any], materials: list[Mapping[str, Any]]) -> str:
    if any(_material_is_mtoon(item) for item in materials):
        return "vrm_mtoon"
    if descriptor.get("vrm") or str(descriptor.get("source_ext") or "").casefold() == ".vrm":
        return "vrm_authored"
    if any(_descriptor_pbr_maps(item) or _descriptor_pbr_factors(item) for item in materials):
        return "gltf_pbr"
    return "authored"


def _has_vrm_extension(gltf: Mapping[str, Any]) -> bool:
    extensions = gltf.get("extensions") if isinstance(gltf.get("extensions"), Mapping) else {}
    return "VRM" in extensions or "VRMC_vrm" in extensions


def _has_mtoon(gltf: Mapping[str, Any]) -> bool:
    extensions = gltf.get("extensions") if isinstance(gltf.get("extensions"), Mapping) else {}
    vrm0 = extensions.get("VRM") if isinstance(extensions.get("VRM"), Mapping) else {}
    for material in vrm0.get("materialProperties") or []:
        if isinstance(material, Mapping) and "mtoon" in str(material.get("shader") or "").casefold():
            return True
    return False


def _pbr_material_summaries(gltf: Mapping[str, Any], *, ignore_factor_only: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, material in enumerate(gltf.get("materials") or []):
        if not isinstance(material, Mapping):
            continue
        maps = []
        factors = []
        pbr = material.get("pbrMetallicRoughness") if isinstance(material.get("pbrMetallicRoughness"), Mapping) else {}
        if isinstance(pbr.get("baseColorTexture"), Mapping):
            maps.append("base")
        if isinstance(pbr.get("metallicRoughnessTexture"), Mapping):
            maps.extend(["roughness", "metallic"])
        if "metallicFactor" in pbr:
            factors.append("metallic")
        if "roughnessFactor" in pbr:
            factors.append("roughness")
        if isinstance(material.get("normalTexture"), Mapping):
            maps.append("normal")
        if isinstance(material.get("occlusionTexture"), Mapping):
            maps.append("occlusion")
        if isinstance(material.get("emissiveTexture"), Mapping):
            maps.append("emissive")
        if str(material.get("alphaMode") or "").upper() == "MASK":
            factors.append("alpha_cutoff")
        extensions = material.get("extensions") if isinstance(material.get("extensions"), Mapping) else {}
        if extensions:
            factors.extend(str(name) for name in extensions)
        if maps or (factors and not ignore_factor_only):
            out.append({
                "index": idx,
                "name": str(material.get("name") or f"material_{idx}"),
                "maps": sorted(set(maps)),
                "factors": sorted(set(factors)),
                "map_count": len(set(maps)),
            })
    return out


def _material_is_mtoon(material: Mapping[str, Any]) -> bool:
    shader = str(material.get("shader_model") or material.get("source_shader") or "").casefold()
    return "mtoon" in shader


def _descriptor_pbr_maps(material: Mapping[str, Any]) -> set[str]:
    out: set[str] = set()
    if str(material.get("base_texture_source") or "") == "gltf_pbr_base_color_texture":
        out.add("base")
    for name in ("roughness", "metallic", "specular", "normal", "occlusion", "emissive", "opacity"):
        if not material.get(f"{name}_texture"):
            continue
        source = str(material.get(f"{name}_texture_source") or "")
        if source.startswith("gltf_pbr") or name in {"roughness", "metallic", "specular", "occlusion", "opacity"}:
            out.add(name)
    if material.get("orm_texture") or material.get("metallic_roughness_texture"):
        out.update({"roughness", "metallic"})
        if material.get("orm_texture"):
            out.add("occlusion")
    return out


def _descriptor_pbr_factors(material: Mapping[str, Any]) -> set[str]:
    if _material_is_mtoon(material):
        return set()
    out: set[str] = set()
    if "roughness" in material:
        out.add("roughness")
    if "metallic" in material:
        out.add("metallic")
    return out
