"""Shared PBR math used by AR/PBR CPU packet rendering.

The GL shaders carry equivalent functions inline.  Keeping the CPU equations
here makes export QA deterministic and gives tests a stable place to validate
the intended BRDF contract.
"""
from __future__ import annotations

from typing import Any

import numpy as np


PI = float(np.pi)


def srgb_to_linear(value: Any):
    c = np.clip(np.asarray(value, dtype=np.float32), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4)).astype(np.float32)


def linear_to_srgb(value: Any):
    c = np.clip(np.asarray(value, dtype=np.float32), 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055).astype(np.float32)


def dielectric_f0_from_reflectance(reflectance: Any):
    return np.clip(0.02 + np.asarray(reflectance, dtype=np.float32) * 0.06, 0.02, 0.08).astype(np.float32)


def material_f0(albedo: Any, metallic: Any, reflectance: Any):
    base = np.asarray(albedo, dtype=np.float32)
    metal = np.clip(np.asarray(metallic, dtype=np.float32), 0.0, 1.0)
    dielectric = dielectric_f0_from_reflectance(reflectance)
    return dielectric[..., None] * (1.0 - metal[..., None]) + base * metal[..., None]


def substrate_metalness_to_diffuse_albedo_f0(
    *,
    albedo: Any,
    metallic: Any,
    reflectance: Any,
    f0_override: Any | None = None,
):
    """Approximate UE Substrate's metalness helper for Slab inputs.

    Unreal's Substrate graph does not shade from a Metallic socket directly.
    This helper preserves our existing metal/rough authoring contract while
    converting it into DiffuseAlbedo + F0 inputs suitable for the Slab path.
    """
    base = np.clip(np.asarray(albedo, dtype=np.float32), 0.0, 1.0)
    metal = np.clip(np.asarray(metallic, dtype=np.float32), 0.0, 1.0)
    diffuse_albedo = base * (1.0 - metal[..., None])
    if f0_override is None:
        f0 = material_f0(base, metal, reflectance)
    else:
        f0 = np.clip(np.asarray(f0_override, dtype=np.float32), 0.0, 1.0)
    return diffuse_albedo.astype(np.float32), f0.astype(np.float32)


def substrate_f90(
    *,
    f0: Any,
    f90_color: Any = (1.0, 1.0, 1.0),
    f90_mask: Any = 1.0,
    strength: Any = 1.0,
):
    base_f0 = np.clip(np.asarray(f0, dtype=np.float32), 0.0, 1.0)
    color = np.clip(np.asarray(f90_color, dtype=np.float32), 0.0, 1.0)
    mask = np.clip(np.asarray(f90_mask, dtype=np.float32), 0.0, 1.0)
    amount = np.clip(np.asarray(strength, dtype=np.float32), 0.0, 1.0)
    max_f0 = np.max(base_f0, axis=-1)
    visibility = np.clip((max_f0 - 0.02) / 0.02, 0.0, 1.0)
    f90 = np.ones_like(base_f0, dtype=np.float32) * color
    f90 = f90 * visibility[..., None] * mask[..., None] * amount
    return np.clip(f90, 0.0, 1.0).astype(np.float32)


def fresnel_schlick_f90(cos_theta: Any, f0: Any, f90: Any):
    ct = np.clip(np.asarray(cos_theta, dtype=np.float32), 0.0, 1.0)
    base = np.asarray(f0, dtype=np.float32)
    edge = np.asarray(f90, dtype=np.float32)
    return base + (edge - base) * np.power(1.0 - ct[..., None], 5.0)


def fresnel_schlick(cos_theta: Any, f0: Any):
    base = np.asarray(f0, dtype=np.float32)
    return fresnel_schlick_f90(cos_theta, base, np.ones_like(base, dtype=np.float32))


def distribution_ggx(ndoth: Any, roughness: Any):
    h = np.clip(np.asarray(ndoth, dtype=np.float32), 0.0, 1.0)
    r = np.clip(np.asarray(roughness, dtype=np.float32), 0.04, 1.0)
    alpha = r * r
    alpha2 = alpha * alpha
    denom = h * h * (alpha2 - 1.0) + 1.0
    return alpha2 / np.maximum(PI * denom * denom, 1.0e-6)


def geometry_schlick_ggx(ndot: Any, roughness: Any):
    n = np.clip(np.asarray(ndot, dtype=np.float32), 0.0, 1.0)
    r = np.clip(np.asarray(roughness, dtype=np.float32), 0.04, 1.0)
    k = ((r + 1.0) * (r + 1.0)) / 8.0
    return n / np.maximum(n * (1.0 - k) + k, 1.0e-6)


def geometry_smith(ndotv: Any, ndotl: Any, roughness: Any):
    return geometry_schlick_ggx(ndotv, roughness) * geometry_schlick_ggx(ndotl, roughness)


def energy_conserving_diffuse_weight(fresnel: Any, metallic: Any):
    f = np.clip(np.asarray(fresnel, dtype=np.float32), 0.0, 1.0)
    metal = np.clip(np.asarray(metallic, dtype=np.float32), 0.0, 1.0)
    return (1.0 - f) * (1.0 - metal[..., None])


def cook_torrance_direct(
    *,
    albedo: Any,
    f0: Any,
    roughness: Any,
    metallic: Any,
    ndotl: Any,
    ndotv: Any,
    ndoth: Any,
    vdoth: Any,
    light_strength: float = 1.0,
    ao: Any = 1.0,
):
    base = np.asarray(albedo, dtype=np.float32)
    rough = np.clip(np.asarray(roughness, dtype=np.float32), 0.04, 1.0)
    metal = np.clip(np.asarray(metallic, dtype=np.float32), 0.0, 1.0)
    nl = np.clip(np.asarray(ndotl, dtype=np.float32), 0.0, 1.0)
    nv = np.clip(np.asarray(ndotv, dtype=np.float32), 0.0, 1.0)
    nh = np.clip(np.asarray(ndoth, dtype=np.float32), 0.0, 1.0)
    vh = np.clip(np.asarray(vdoth, dtype=np.float32), 0.0, 1.0)
    occlusion = np.clip(np.asarray(ao, dtype=np.float32), 0.0, 1.0)
    fresnel = fresnel_schlick(vh, f0)
    diffuse_weight = energy_conserving_diffuse_weight(fresnel, metal)
    diffuse = diffuse_weight * base / PI
    d = distribution_ggx(nh, rough)
    g = geometry_smith(nv, nl, rough)
    specular = (d[..., None] * g[..., None] * fresnel) / np.maximum(4.0 * nv[..., None] * nl[..., None], 1.0e-5)
    return (diffuse + specular) * nl[..., None] * float(light_strength) * occlusion[..., None]


def cook_torrance_substrate_slab_direct(
    *,
    diffuse_albedo: Any,
    f0: Any,
    f90: Any,
    roughness: Any,
    ndotl: Any,
    ndotv: Any,
    ndoth: Any,
    vdoth: Any,
    light_strength: float = 1.0,
    ao: Any = 1.0,
):
    diffuse_base = np.clip(np.asarray(diffuse_albedo, dtype=np.float32), 0.0, 1.0)
    rough = np.clip(np.asarray(roughness, dtype=np.float32), 0.04, 1.0)
    nl = np.clip(np.asarray(ndotl, dtype=np.float32), 0.0, 1.0)
    nv = np.clip(np.asarray(ndotv, dtype=np.float32), 0.0, 1.0)
    nh = np.clip(np.asarray(ndoth, dtype=np.float32), 0.0, 1.0)
    vh = np.clip(np.asarray(vdoth, dtype=np.float32), 0.0, 1.0)
    occlusion = np.clip(np.asarray(ao, dtype=np.float32), 0.0, 1.0)
    fresnel = fresnel_schlick_f90(vh, f0, f90)
    diffuse = np.clip(1.0 - fresnel, 0.0, 1.0) * diffuse_base / PI
    d = distribution_ggx(nh, rough)
    g = geometry_smith(nv, nl, rough)
    specular = (d[..., None] * g[..., None] * fresnel) / np.maximum(4.0 * nv[..., None] * nl[..., None], 1.0e-5)
    return (diffuse + specular) * nl[..., None] * float(light_strength) * occlusion[..., None]
