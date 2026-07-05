"""Convert PMX model data into packets consumed by OpenGLPreviewWidget."""
from __future__ import annotations

from functools import lru_cache
import math
from pathlib import Path
import re
from typing import Any, Mapping

import numpy as np

from .animation import MMDPoseGeometry
from .lighting import resolve_mmd_lighting
from .pmx import MMDMaterial, MMDModel


MMD_RENDER_TOON = "toon"
MMD_RENDER_BUCKET_OPAQUE = 0
MMD_RENDER_BUCKET_CUTOUT = 1
MMD_RENDER_BUCKET_TRANSPARENT = 2
MMD_MATERIAL_DEFAULT = 0
MMD_MATERIAL_SKIN = 1
MMD_MATERIAL_HAIR = 2
MMD_MATERIAL_EMISSIVE = 3
MMD_MATERIAL_TRANSPARENT = 4
MMD_MATERIAL_STOCKING = 5
MMD_MATERIAL_EYE = 6
MMD_MATERIAL_LIP = 7
MMD_MATERIAL_METAL = 8
MMD_GPU_MORPH_SLOTS = 2
_PMX_MATERIAL_FLAG_EDGE = 0x10
_PMX_MATERIAL_FLAG_GROUND_SHADOW = 0x02
_PMX_MATERIAL_FLAG_CAST_SELF_SHADOW = 0x04
_PMX_MATERIAL_FLAG_RECEIVE_SELF_SHADOW = 0x08

_RENDER_BUCKET_NAMES = {
    MMD_RENDER_BUCKET_OPAQUE: "opaque",
    MMD_RENDER_BUCKET_CUTOUT: "cutout",
    MMD_RENDER_BUCKET_TRANSPARENT: "transparent",
}

_MATERIAL_CLASS_NAMES = {
    MMD_MATERIAL_DEFAULT: "default",
    MMD_MATERIAL_SKIN: "skin",
    MMD_MATERIAL_HAIR: "hair",
    MMD_MATERIAL_EMISSIVE: "emissive",
    MMD_MATERIAL_TRANSPARENT: "transparent",
    MMD_MATERIAL_STOCKING: "stocking",
    MMD_MATERIAL_EYE: "eye",
    MMD_MATERIAL_LIP: "lip",
    MMD_MATERIAL_METAL: "metal",
}


def render_bucket_name(value: int) -> str:
    return _RENDER_BUCKET_NAMES.get(int(value), "transparent" if int(value) >= MMD_RENDER_BUCKET_TRANSPARENT else "opaque")


def material_class_name(value: int) -> str:
    return _MATERIAL_CLASS_NAMES.get(int(value), "default")


def _clean_texture_path(value: str) -> str:
    return str(value or "").replace("\\", "/").strip().strip("\x00")


def _resolve_texture_index(model: MMDModel, idx: int) -> str:
    if idx < 0 or idx >= len(model.textures):
        return ""
    raw = _clean_texture_path(model.textures[idx])
    if not raw:
        return ""
    base = model.path.parent
    direct = base / raw
    if direct.is_file():
        return str(direct)
    by_name = base / Path(raw).name
    if by_name.is_file():
        return str(by_name)
    needle = Path(raw).name.casefold()
    try:
        for candidate in base.rglob("*"):
            if candidate.is_file() and candidate.name.casefold() == needle:
                return str(candidate)
    except Exception:
        pass
    return str(direct)


def _resolve_texture(model: MMDModel, material: MMDMaterial) -> str:
    return _resolve_texture_index(model, int(material.texture_index))


def _resolve_sphere_texture(model: MMDModel, material: MMDMaterial) -> str:
    return _resolve_texture_index(model, int(material.sphere_texture_index))


def _resolve_toon_texture(model: MMDModel, material: MMDMaterial) -> str:
    if not material.toon_shared:
        return _resolve_texture_index(model, int(material.toon_texture_index))
    idx = max(0, min(9, int(material.toon_texture_index)))
    candidates = [f"toon{idx + 1:02d}.bmp", "toon_defo.bmp"]
    for name in candidates:
        direct = model.path.parent / name
        if direct.is_file():
            return str(direct)
    try:
        for candidate in model.path.parent.rglob("*"):
            if candidate.is_file() and candidate.name.casefold() in {v.casefold() for v in candidates}:
                return str(candidate)
    except Exception:
        pass
    return ""


def _texture_stat_key(path: str) -> tuple[str, int, int] | None:
    if not str(path or "").strip():
        return None
    try:
        p = Path(str(path))
        if not p.is_file():
            return None
        st = p.stat()
        return str(p.resolve()), int(st.st_size), int(st.st_mtime_ns)
    except Exception:
        return None


@lru_cache(maxsize=256)
def _texture_alpha_mode_cached(path: str, size: int, mtime_ns: int) -> str:
    try:
        from PIL import Image

        image = Image.open(path)
        if image.mode == "P" and "transparency" in image.info:
            image = image.convert("RGBA")
        if image.mode not in {"RGBA", "LA"}:
            return "opaque"
        alpha = image.getchannel("A")
        extrema = alpha.getextrema()
        if not extrema or int(extrema[0]) >= 250:
            return "opaque"
        try:
            import numpy as _np

            arr = _np.asarray(alpha, dtype=_np.uint8)
            total = max(1, int(arr.size))
            mid_ratio = float(_np.count_nonzero((arr > 4) & (arr < 250))) / total
            opaque_ratio = float(_np.count_nonzero(arr >= 250)) / total
            transparent_ratio = float(_np.count_nonzero(arr <= 4)) / total
            if transparent_ratio <= 0.002 and opaque_ratio >= 0.94:
                return "opaque"
            if mid_ratio <= 0.025 and opaque_ratio > 0.01 and transparent_ratio > 0.01:
                return "cutout"
        except Exception:
            pass
        return "blend"
    except Exception:
        return "opaque"


def _texture_alpha_mode(path: str) -> str:
    key = _texture_stat_key(path)
    if key is None:
        return "opaque"
    return _texture_alpha_mode_cached(*key)


@lru_cache(maxsize=128)
def _texture_alpha_array_cached(path: str, size: int, mtime_ns: int) -> np.ndarray | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            if image.mode == "P" and "transparency" in image.info:
                image = image.convert("RGBA")
            if image.mode not in {"RGBA", "LA"}:
                return None
            alpha = image.getchannel("A")
            return np.asarray(alpha, dtype=np.uint8).copy()
    except Exception:
        return None


def _texture_alpha_array(path: str) -> np.ndarray | None:
    key = _texture_stat_key(path)
    if key is None:
        return None
    return _texture_alpha_array_cached(*key)


def _material_uv_sample_points(uvs: np.ndarray) -> np.ndarray:
    uv_rows = np.asarray(uvs, dtype=np.float32)
    if uv_rows.ndim != 2 or uv_rows.shape[1] < 2 or uv_rows.size <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    uv_rows = uv_rows[:, :2]
    points = [uv_rows]
    usable = int(uv_rows.shape[0] // 3) * 3
    if usable >= 3:
        tris = uv_rows[:usable].reshape((-1, 3, 2))
        a = tris[:, 0, :]
        b = tris[:, 1, :]
        c = tris[:, 2, :]
        points.extend(
            [
                (a + b + c) / 3.0,
                (a + b) * 0.5,
                (b + c) * 0.5,
                (c + a) * 0.5,
                a * 0.60 + b * 0.20 + c * 0.20,
                a * 0.20 + b * 0.60 + c * 0.20,
                a * 0.20 + b * 0.20 + c * 0.60,
            ]
        )
    samples = np.concatenate(points, axis=0)
    finite = np.isfinite(samples).all(axis=1)
    if not np.any(finite):
        return np.zeros((0, 2), dtype=np.float32)
    return np.clip(samples[finite], 0.0, 1.0).astype(np.float32, copy=False)


def _material_uv_alpha_stats(texture_path: str, uvs: np.ndarray) -> dict[str, float | str]:
    alpha = _texture_alpha_array(texture_path)
    if alpha is None or alpha.ndim != 2 or alpha.size <= 0:
        return {"mode": "opaque", "sample_count": 0.0, "min": 255.0, "max": 255.0, "mean": 255.0}
    samples = _material_uv_sample_points(uvs)
    if samples.size <= 0:
        return {"mode": "opaque", "sample_count": 0.0, "min": 255.0, "max": 255.0, "mean": 255.0}

    h, w = int(alpha.shape[0]), int(alpha.shape[1])
    xs = np.rint(samples[:, 0] * max(0, w - 1)).astype(np.int32, copy=False)
    ys = np.rint((1.0 - samples[:, 1]) * max(0, h - 1)).astype(np.int32, copy=False)
    values = alpha[np.clip(ys, 0, h - 1), np.clip(xs, 0, w - 1)]
    total = max(1, int(values.size))
    mid_ratio = float(np.count_nonzero((values > 4) & (values < 250))) / total
    opaque_ratio = float(np.count_nonzero(values >= 250)) / total
    transparent_ratio = float(np.count_nonzero(values <= 4)) / total
    mean_alpha = float(np.mean(values)) if total > 0 else 255.0
    min_alpha = float(np.min(values)) if total > 0 else 255.0
    max_alpha = float(np.max(values)) if total > 0 else 255.0
    mode = "opaque"
    if mid_ratio >= 0.18 or (mid_ratio > 0.04 and mean_alpha < 245.0 and opaque_ratio < 0.94):
        mode = "blend"
    elif transparent_ratio > 0.01 and mid_ratio <= 0.04 and opaque_ratio > 0.01:
        mode = "cutout"
    if min_alpha >= 250.0:
        mode = "opaque"
    return {
        "mode": mode,
        "sample_count": float(total),
        "min": min_alpha,
        "max": max_alpha,
        "mean": mean_alpha,
        "mid_ratio": mid_ratio,
        "opaque_ratio": opaque_ratio,
        "transparent_ratio": transparent_ratio,
    }


def _refine_render_bucket_with_material_alpha(
    texture_path: str,
    diffuse: tuple[float, float, float, float],
    uvs: np.ndarray,
    render_bucket: int,
    alpha_cutoff: float,
) -> tuple[int, float, dict[str, float | str]]:
    stats = _material_uv_alpha_stats(texture_path, uvs)
    if float(diffuse[3]) < 0.999:
        return render_bucket, alpha_cutoff, stats
    mode = str(stats.get("mode") or "opaque")
    if mode == "blend":
        return MMD_RENDER_BUCKET_TRANSPARENT, 0.002, stats
    if mode == "cutout" and int(render_bucket) < MMD_RENDER_BUCKET_TRANSPARENT:
        return MMD_RENDER_BUCKET_CUTOUT, max(0.25, float(alpha_cutoff)), stats
    return render_bucket, alpha_cutoff, stats


@lru_cache(maxsize=256)
def _texture_darkest_rgb_cached(path: str, size: int, mtime_ns: int) -> tuple[float, float, float]:
    try:
        from PIL import Image

        image = Image.open(path).convert("RGBA")
        arr = np.asarray(image, dtype=np.uint8)
        if arr.ndim != 3 or arr.shape[2] < 4:
            return 0.34, 0.34, 0.34
        alpha = arr[:, :, 3] > 8
        rgb = arr[:, :, :3]
        if np.any(alpha):
            rgb = rgb[alpha]
        else:
            rgb = rgb.reshape((-1, 3))
        if rgb.size <= 0:
            return 0.34, 0.34, 0.34
        linear = rgb.astype(np.float32) / 255.0
        luma = linear[:, 0] * 0.2126 + linear[:, 1] * 0.7152 + linear[:, 2] * 0.0722
        idx = int(np.argmin(luma))
        value = linear[idx]
        return float(value[0]), float(value[1]), float(value[2])
    except Exception:
        return 0.34, 0.34, 0.34


def _texture_darkest_rgb(path: str) -> tuple[float, float, float]:
    key = _texture_stat_key(path)
    if key is None:
        return 0.34, 0.34, 0.34
    return _texture_darkest_rgb_cached(*key)


@lru_cache(maxsize=256)
def _texture_mean_rgb_cached(path: str, size: int, mtime_ns: int) -> tuple[float, float, float] | None:
    try:
        from PIL import Image

        image = Image.open(path).convert("RGBA")
        image.thumbnail((256, 256), Image.Resampling.BILINEAR)
        arr = np.asarray(image, dtype=np.uint8)
        if arr.ndim != 3 or arr.shape[2] < 4:
            return None
        alpha = arr[:, :, 3] > 8
        rgb = arr[:, :, :3]
        if np.any(alpha):
            rgb = rgb[alpha]
        else:
            rgb = rgb.reshape((-1, 3))
        if rgb.size <= 0:
            return None
        linear = rgb.astype(np.float32) / 255.0
        value = np.mean(linear, axis=0)
        return float(value[0]), float(value[1]), float(value[2])
    except Exception:
        return None


def _texture_mean_rgb(path: str, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    key = _texture_stat_key(path)
    if key is not None:
        value = _texture_mean_rgb_cached(*key)
        if value is not None:
            return value
    return tuple(float(v) for v in fallback[:3])


def _render_bucket_and_cutoff(texture_path: str, diffuse: tuple[float, float, float, float]) -> tuple[int, float]:
    alpha = float(diffuse[3]) if len(diffuse) >= 4 else 1.0
    if alpha < 0.999:
        return MMD_RENDER_BUCKET_TRANSPARENT, 0.002
    mode = _texture_alpha_mode(texture_path)
    if mode == "cutout":
        return MMD_RENDER_BUCKET_CUTOUT, 0.35
    if mode == "blend":
        return MMD_RENDER_BUCKET_TRANSPARENT, 0.002
    return MMD_RENDER_BUCKET_OPAQUE, 0.002


def _material_text_blob(material: MMDMaterial, *paths: str) -> str:
    parts = [
        material.name,
        material.english_name,
        material.memo,
    ]
    for value in paths:
        cleaned = _clean_texture_path(value)
        if cleaned:
            p = Path(cleaned)
            parts.extend([p.name, p.stem])
    return " ".join(str(part or "") for part in parts).casefold()


def _material_name_blob(material: MMDMaterial) -> str:
    return " ".join(
        str(part or "")
        for part in (material.name, material.english_name, material.memo)
    ).casefold()


def _material_paths_blob(*paths: str) -> str:
    parts: list[str] = []
    for value in paths:
        cleaned = _clean_texture_path(value)
        if cleaned:
            p = Path(cleaned)
            parts.extend([p.name, p.stem])
    return " ".join(parts).casefold()


def _material_has_keyword(blob: str, *, ascii_tokens: tuple[str, ...], substrings: tuple[str, ...]) -> bool:
    tokens = set(re.findall(r"[a-z0-9]+", blob))
    return any(key in tokens for key in ascii_tokens) or any(key in blob for key in substrings)


def _material_is_eye(name_blob: str) -> bool:
    compact = name_blob.replace(" ", "")
    if any(value in compact for value in ("\u795e\u4e4b\u773c", "vision")):
        return False
    cjk_tokens = {part for part in re.split(r"\s+", name_blob) if part}
    if compact in {"\u76ee", "\u773c", "\u773c\u775b", "\u773c\u7403"} or cjk_tokens.intersection(
        {"\u76ee", "\u773c", "\u773c\u775b", "\u773c\u7403"}
    ):
        return True
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("catchlight", "eye", "eyes", "highlight", "iris", "pupil"),
        substrings=(
            "\u767d\u76ee",
            "\u9ed2\u76ee",
            "\u76ee\u5149",
            "\u661f\u76ee",
            "\u77b3",
            "\u8679\u5f69",
        ),
    )


def _material_is_eye_highlight(name_blob: str) -> bool:
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("catchlight", "highlight"),
        substrings=(
            "\u76ee\u5149",
            "\u773c\u5149",
            "\u30cf\u30a4\u30e9\u30a4\u30c8",
            "\u30cf\u30a4\u30e9\u30a4\u30c4",
        ),
    )


def _material_is_eye_shadow(name_blob: str) -> bool:
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("eyeshadow", "eyeline", "eyelid", "shadow"),
        substrings=(
            "\u76ee\u5f71",
            "\u773c\u5f71",
            "\u76ee\u7dda",
            "\u76ee\u7ebf",
            "\u773c\u7dda",
            "\u773c\u7ebf",
        ),
    )


def _material_is_sclera(name_blob: str) -> bool:
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("sclera", "whiteeye", "whiteeyes"),
        substrings=("\u767d\u76ee", "\u767d\u773c"),
    )


def _material_is_lip(name_blob: str) -> bool:
    if "\u8896" in name_blob:
        return False
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("kuchi", "lip", "lips", "mouth", "tongue"),
        substrings=(
            "\uc785",
            "\uc785\uc220",
            "\ud600",
            "\uce58\uc544",
            "\uc774\ube68",
            "\u5507",
            "\u53e3\u820c",
            "\u53e3\u5185",
            "\u820c",
            "\u53e3",
            "\u30ea\u30c3\u30d7",
            "\u30af\u30c1",
        ),
    )


def _material_is_face_surface(name_blob: str) -> bool:
    compact = name_blob.replace(" ", "")
    if compact in {"\u9854", "\u989c", "\u8138", "\u9762", "\uc5bc\uad74"}:
        return True
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("face", "facial"),
        substrings=(
            "\u9854",
            "\u989c",
            "\u8138",
            "\u9762\u90e8",
            "\uc5bc\uad74",
        ),
    )


def _material_is_brow_lash_or_mouth_detail(name_blob: str) -> bool:
    return _material_has_keyword(
        name_blob,
        ascii_tokens=(
            "brow",
            "brows",
            "eyebrow",
            "eyebrows",
            "eyelash",
            "eyelashes",
            "lash",
            "lashes",
            "mouth",
            "mouthline",
            "teeth",
            "tooth",
        ),
        substrings=(
            "\ub208",
            "\ub208\uc379",
            "\uc18d\ub208\uc379",
            "\u7709",
            "\u776b",
            "\u307e\u3064\u3052",
            "\u30de\u30c4\u30b2",
            "\uc785",
            "\uc785\uc220",
            "\ud600",
            "\uce58\uc544",
            "\uc774\ube68",
            "\u53e3",
            "\u53e3\u7dda",
            "\u53e3\u7ebf",
            "\u5507",
            "\u820c",
            "\u6b6f",
            "\u9f7f",
            "\u9f52",
            "\u4e8c\u91cd",
        ),
    )


def _material_is_eye_detail(name_blob: str) -> bool:
    return _material_is_eye(name_blob) or _material_is_eye_shadow(name_blob)


def _material_is_brow_lash_detail(name_blob: str) -> bool:
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("brow", "brows", "eyebrow", "eyebrows", "eyelash", "eyelashes", "lash", "lashes"),
        substrings=(
            "\ub208\uc379",
            "\uc18d\ub208\uc379",
            "\u7709",
            "\u776b",
            "\u307e\u3064\u3052",
            "\u30de\u30c4\u30b2",
        ),
    )


def _material_suppresses_outline(material: MMDMaterial, material_class: int, texture: str = "") -> bool:
    name_blob = _material_name_blob(material)
    return (
        int(material_class) in {MMD_MATERIAL_EYE, MMD_MATERIAL_LIP}
        or _material_is_hair_accessory(name_blob)
        or (int(material_class) == MMD_MATERIAL_HAIR and _material_is_internal_hair(name_blob))
        or (int(material_class) == MMD_MATERIAL_HAIR and _material_is_bright_generic_head_hair(material, texture))
        or _material_is_eye_detail(name_blob)
        or _material_is_brow_lash_or_mouth_detail(name_blob)
    )


def _material_edge_enabled(material: MMDMaterial, material_class: int, *, strict_flags: bool, texture: str = "") -> bool:
    if _material_suppresses_outline(material, material_class, texture):
        return False
    if float(material.edge_size) <= 0.001 or float(material.edge_color[3]) <= 0.001:
        return False
    # PMX carries an explicit material edge bit. PMD/Aplaybox adapters can
    # synthesize edge size/color without that bit, so only PMX is strict.
    if not strict_flags and int(material.flags) == 0:
        return True
    return bool(int(material.flags) & _PMX_MATERIAL_FLAG_EDGE)


def _styled_edge(
    material: MMDMaterial,
    material_class: int,
    texture: str,
) -> tuple[tuple[float, float, float, float], float]:
    edge = tuple(float(v) for v in material.edge_color)
    size = float(material.edge_size)
    diffuse_rgb = tuple(float(v) for v in material.diffuse[:3])
    name_blob = _material_name_blob(material)
    if int(material_class) == MMD_MATERIAL_SKIN and _material_is_face_surface(name_blob):
        base = np.asarray(_texture_mean_rgb(texture, diffuse_rgb), dtype=np.float32)
        warm = np.asarray((0.28, 0.14, 0.11), dtype=np.float32)
        rgb = np.clip(base * 0.42 + warm * 0.58, 0.10, 0.58)
        return (
            float(rgb[0]),
            float(rgb[1]),
            float(rgb[2]),
            min(float(edge[3]), 0.58),
        ), max(0.0, size * 0.22)
    if int(material_class) == MMD_MATERIAL_HAIR:
        base = np.asarray(_texture_mean_rgb(texture, diffuse_rgb), dtype=np.float32)
        # Hair outlines should read as a toned-down version of the actual
        # hair color, not as a generic black stroke. Bright hair needs an even
        # softer line because a dark backface band reads as black beside ears.
        luma = float(np.dot(base, np.asarray((0.2126, 0.7152, 0.0722), dtype=np.float32)))
        bright = float(np.clip((luma - 0.34) / 0.36, 0.0, 1.0))
        bright = bright * bright * (3.0 - 2.0 * bright)
        value_scale = 0.70 + bright * 0.18
        rgb = np.clip(base * value_scale, 0.045, 0.78)
        alpha = min(float(edge[3]), 0.58 - bright * 0.18)
        size_scale = 0.34 - bright * 0.12
        return (
            float(rgb[0]),
            float(rgb[1]),
            float(rgb[2]),
            alpha,
        ), max(0.0, size * size_scale)
    return edge, size


def _material_is_hair_accessory(name_blob: str) -> bool:
    return _material_has_keyword(
        name_blob,
        ascii_tokens=(
            "accessory",
            "band",
            "bow",
            "clip",
            "hairband",
            "hairclip",
            "hairtie",
            "ornament",
            "ribbon",
            "tie",
        ),
        substrings=(
            "\u9aea\u5e26",
            "\u9aea\u5e2f",
            "\u9aee\u5e26",
            "\u9aee\u5e2f",
            "\u5934\u9970",
            "\u982d\u98fe",
            "\u30ea\u30dc\u30f3",
            "\u30d8\u30a2\u30d0\u30f3\u30c9",
            "\u98fe",
            "\u9970",
        ),
    )


def _material_is_hair(name_blob: str) -> bool:
    if _material_is_hair_accessory(name_blob):
        return False
    return _material_has_keyword(
        name_blob,
        ascii_tokens=("hair", "kami"),
        substrings=("\u9aea", "\u53d1", "\u9aee", "\u982d\u53d1", "\u982d\u9aee", "\u5934\u53d1"),
    )


def _material_is_internal_hair(name_blob: str) -> bool:
    compact = "".join(ch for ch in str(name_blob or "").casefold() if not ch.isspace())
    if any(value in compact for value in ("fronthair", "innerhair", "insidehair")):
        return True
    return _material_has_keyword(
        name_blob,
        ascii_tokens=(
            "bang",
            "bangs",
            "fringe",
            "front hair",
            "fronthair",
            "inner hair",
            "innerhair",
            "inside hair",
            "insidehair",
        ),
        substrings=(
            "\u524d\u9aea",
            "\u524d\u9aee",
            "\u524d\u53d1",
            "\u5185\u9aea",
            "\u5167\u9aee",
            "\u5185\u53d1",
            "\uc55e\uba38\ub9ac",
        ),
    )


def _material_is_bright_generic_head_hair(material: MMDMaterial, texture: str) -> bool:
    if not texture:
        return False
    name_blob = _material_name_blob(material)
    compact = "".join(ch for ch in name_blob.casefold() if not ch.isspace())
    if compact not in {
        "hair",
        "kami",
        "\u9aea",
        "\u9aee",
        "\u53d1",
        "\u982d\u53d1",
        "\u982d\u9aee",
        "\u5934\u53d1",
    }:
        return False
    base = np.asarray(_texture_mean_rgb(texture, tuple(float(v) for v in material.diffuse[:3])), dtype=np.float32)
    luma = float(np.dot(base, np.asarray((0.2126, 0.7152, 0.0722), dtype=np.float32)))
    return luma >= 0.50


def _material_is_emissive_surface(blob: str) -> bool:
    return _material_has_keyword(
        blob,
        ascii_tokens=(
            "al",
            "autoluminous",
            "display",
            "emissive",
            "emission",
            "emit",
            "glow",
            "lamp",
            "lcd",
            "led",
            "light",
            "luminous",
            "monitor",
            "neon",
            "screen",
        ),
        substrings=(
            "\u767a\u5149",
            "\u767c\u5149",
            "\u5149\u308b",
            "\u753b\u9762",
            "\u30b9\u30af\u30ea\u30fc\u30f3",
            "\u5c4f\u5e55",
            "\u87a2\u5e55",
            "\u8424\u5e55",
        ),
    )


def _material_class(
    material: MMDMaterial,
    *,
    texture: str,
    toon_texture: str,
    sphere_texture: str,
    render_bucket: int,
) -> int:
    name_blob = _material_name_blob(material)
    path_blob = _material_paths_blob(texture, toon_texture, sphere_texture)
    combined_blob = f"{name_blob} {path_blob}"
    if _material_is_emissive_surface(combined_blob):
        return MMD_MATERIAL_EMISSIVE
    if _material_has_keyword(
        combined_blob,
        ascii_tokens=(
            "legging",
            "leggings",
            "legwear",
            "nylon",
            "pantyhose",
            "sock",
            "socks",
            "stocking",
            "stockings",
            "thighhigh",
            "tights",
        ),
        substrings=(
            "\u30b9\u30c8\u30c3\u30ad\u30f3\u30b0",
            "\u30bf\u30a4\u30c4",
            "\u30cb\u30fc\u30bd",
            "\u30cb\u30fc\u30cf\u30a4",
            "\u9774\u4e0b",
            "\u9ed1\u4e1d",
            "\u9ed1\u7d72",
            "\u4e1d\u889c",
            "\u7d72\u896a",
            "\u889c",
            "\u896a",
        ),
    ):
        return MMD_MATERIAL_STOCKING
    if _material_is_eye(name_blob):
        return MMD_MATERIAL_EYE
    if _material_is_lip(name_blob):
        return MMD_MATERIAL_LIP
    if _material_is_hair(name_blob):
        return MMD_MATERIAL_HAIR
    if _material_has_keyword(
        combined_blob,
        ascii_tokens=(
            "armor",
            "blade",
            "chain",
            "gem",
            "gold",
            "jewel",
            "metal",
            "ring",
            "silver",
            "sword",
            "weapon",
        ),
        substrings=(
            "\u91d1\u5c5e",
            "\u91d1",
            "\u9280",
            "\u94f6",
            "\u5b9d\u77f3",
            "\u5bf6\u77f3",
            "\u795e\u4e4b\u773c",
            "\u7532",
            "\u98fe",
            "\u9970",
            "\u8033\u5760",
            "\u5934\u9970",
            "\u982d\u98fe",
        ),
    ):
        return MMD_MATERIAL_METAL
    if _material_has_keyword(
        name_blob,
        ascii_tokens=("skin", "hada", "face", "hand", "arm", "leg", "neck", "body", "head"),
        substrings=(
            "\u808c",
            "\u9854",
            "\u989c",
            "\u8138",
            "\u4f53",
            "\u8eab",
            "\u9996",
            "\u817f",
            "\u811a",
            "\u8db3",
            "\u624b",
            "\u8155",
            "\u80f8",
            "\u8179",
        ),
    ):
        return MMD_MATERIAL_SKIN
    generic_name = not name_blob or name_blob in {"mat", "material", "new", "\u65b0\u898f"}
    if generic_name and _material_has_keyword(
        path_blob,
        ascii_tokens=("skin", "hada", "face", "body"),
        substrings=("\u808c", "\u9854", "\u989c", "\u8138", "\u4f53", "\u8eab"),
    ):
        return MMD_MATERIAL_SKIN
    if generic_name and _material_is_hair(path_blob):
        return MMD_MATERIAL_HAIR
    if int(render_bucket) >= MMD_RENDER_BUCKET_TRANSPARENT:
        return MMD_MATERIAL_TRANSPARENT
    return MMD_MATERIAL_DEFAULT


def _material_shader_controls(material_class: int, render_bucket: int) -> dict[str, float]:
    controls = {
        "toon_ao_strength": 0.08,
        "skin_warmth": 0.0,
        "highlight_clamp": 1.0,
        "rim_boost": 1.0,
        "sphere_strength": 1.0,
        "matcap_specular_strength": 0.0,
        "toon_highlight_strength": 0.0,
        "toon_highlight_size": 0.62,
        "hair_angel_ring_strength": 0.0,
        "hair_angel_ring_center": 0.48,
        "hair_angel_ring_width": 0.055,
        "eye_highlight_strength": 0.0,
        "lip_specular_strength": 0.0,
        "wrap_diffuse": 0.0,
        "emissive_strength": 0.0,
        "skin_shadow_soften": 0.0,
        "skin_shadow_lift": 0.0,
    }
    if material_class == MMD_MATERIAL_SKIN:
        controls.update(
            {
                "toon_ao_strength": 0.025,
                "skin_warmth": 0.34,
                "highlight_clamp": 0.97,
                "rim_boost": 0.85,
                "sphere_strength": 0.24,
                "wrap_diffuse": 0.36,
                "skin_shadow_soften": 0.28,
                "skin_shadow_lift": 0.34,
            }
        )
    elif material_class == MMD_MATERIAL_HAIR:
        controls.update(
            {
                "toon_ao_strength": 0.06,
                "highlight_clamp": 0.96,
                "rim_boost": 1.55,
                "sphere_strength": 0.52,
                "matcap_specular_strength": 0.16,
                "toon_highlight_strength": 0.34,
                "toon_highlight_size": 0.58,
                "hair_angel_ring_strength": 0.0,
                "hair_angel_ring_center": 0.50,
                "hair_angel_ring_width": 0.075,
                "wrap_diffuse": 0.04,
            }
        )
    elif material_class == MMD_MATERIAL_EYE:
        controls.update(
            {
                "toon_ao_strength": 0.0,
                "highlight_clamp": 1.0,
                "rim_boost": 0.70,
                "sphere_strength": 0.40,
                "matcap_specular_strength": 0.28,
                "toon_highlight_strength": 0.22,
                "toon_highlight_size": 0.72,
                "eye_highlight_strength": 1.20,
                "wrap_diffuse": 0.02,
            }
        )
    elif material_class == MMD_MATERIAL_LIP:
        controls.update(
            {
                "toon_ao_strength": 0.015,
                "skin_warmth": 0.16,
                "highlight_clamp": 1.0,
                "rim_boost": 0.85,
                "sphere_strength": 0.35,
                "matcap_specular_strength": 0.22,
                "toon_highlight_strength": 0.08,
                "toon_highlight_size": 0.70,
                "lip_specular_strength": 0.82,
                "wrap_diffuse": 0.16,
                "skin_shadow_soften": 0.16,
                "skin_shadow_lift": 0.12,
            }
        )
    elif material_class == MMD_MATERIAL_STOCKING:
        controls.update(
            {
                "toon_ao_strength": 0.055,
                "highlight_clamp": 1.0,
                "rim_boost": 1.35,
                "sphere_strength": 1.35,
                "matcap_specular_strength": 0.78,
                "wrap_diffuse": 0.02,
            }
        )
    elif material_class == MMD_MATERIAL_METAL:
        controls.update(
            {
                "toon_ao_strength": 0.035,
                "highlight_clamp": 1.0,
                "rim_boost": 1.25,
                "sphere_strength": 1.35,
                "matcap_specular_strength": 0.95,
                "toon_highlight_strength": 0.42,
                "toon_highlight_size": 0.74,
                "wrap_diffuse": 0.0,
            }
        )
    elif material_class == MMD_MATERIAL_EMISSIVE:
        controls.update(
            {
                "toon_ao_strength": 0.0,
                "highlight_clamp": 1.0,
                "rim_boost": 1.20,
                "sphere_strength": 1.0,
                "emissive_strength": 1.0,
            }
        )
    elif material_class == MMD_MATERIAL_TRANSPARENT:
        controls.update(
            {
                "toon_ao_strength": 0.0,
                "highlight_clamp": 1.0,
                "rim_boost": 0.90,
                "sphere_strength": 0.70,
            }
        )
    if int(render_bucket) >= MMD_RENDER_BUCKET_TRANSPARENT and material_class not in {
        MMD_MATERIAL_SKIN,
        MMD_MATERIAL_HAIR,
        MMD_MATERIAL_STOCKING,
        MMD_MATERIAL_EYE,
        MMD_MATERIAL_LIP,
        MMD_MATERIAL_METAL,
    }:
        controls["toon_ao_strength"] = 0.0
    return controls


def _material_named_shader_controls(material: MMDMaterial, material_class: int) -> dict[str, float]:
    name_blob = _material_name_blob(material)
    if int(material_class) == MMD_MATERIAL_EYE and _material_is_eye_highlight(name_blob):
        return {"emissive_strength": 0.56}
    return {}


def _material_styled_diffuse(material: MMDMaterial, diffuse: tuple[float, ...]) -> tuple[float, float, float, float]:
    rgba = tuple(float(v) for v in (tuple(diffuse) + (1.0, 1.0, 1.0, 1.0))[:4])
    name_blob = _material_name_blob(material)
    alpha = float(rgba[3])
    if _material_is_eye_shadow(name_blob):
        alpha = min(alpha * 0.55, 0.22)
    elif _material_is_eye_highlight(name_blob):
        alpha = min(alpha * 0.72, 0.24)
    return (float(rgba[0]), float(rgba[1]), float(rgba[2]), float(alpha))


def _material_face_layer_priority(material: MMDMaterial, material_class: int) -> int:
    name_blob = _material_name_blob(material)
    if _material_is_sclera(name_blob):
        return 20
    if _material_is_eye_shadow(name_blob):
        return 30
    if int(material_class) == MMD_MATERIAL_EYE:
        if _material_is_eye_highlight(name_blob):
            return 60
        return 40
    if _material_is_brow_lash_detail(name_blob):
        return 70
    return 0


def _material_draw_priority(material: MMDMaterial, material_class: int, render_bucket: int, *paths: str) -> int:
    if int(render_bucket) < MMD_RENDER_BUCKET_TRANSPARENT:
        return 0
    name_blob = _material_name_blob(material)
    blob = f"{name_blob} {_material_paths_blob(*paths)}"
    if material_class == MMD_MATERIAL_EMISSIVE:
        return 80
    if material_class == MMD_MATERIAL_HAIR and _material_is_internal_hair(name_blob):
        return 76
    if material_class == MMD_MATERIAL_EYE:
        return 70
    if material_class == MMD_MATERIAL_LIP:
        return 60
    if material_class == MMD_MATERIAL_METAL:
        return 52
    if material_class == MMD_MATERIAL_STOCKING:
        return 42
    if material_class == MMD_MATERIAL_SKIN:
        return 36
    if material_class == MMD_MATERIAL_HAIR:
        return 24
    if _material_has_keyword(
        blob,
        ascii_tokens=("lace", "veil", "skirt", "cloth", "dress", "frill", "ribbon"),
        substrings=("\u30ec\u30fc\u30b9", "\u30b9\u30ab\u30fc\u30c8", "\u88d9", "\u857e\u4e1d", "\u857e\u7d72", "\u30d5\u30ea\u30eb"),
    ):
        return 18
    return 10


def _material_self_shadow_policy(
    material: MMDMaterial,
    material_class: int,
    render_bucket: int,
    *,
    strict_flags: bool,
) -> dict[str, bool | str]:
    flags = int(material.flags)
    name_blob = _material_name_blob(material)
    detail_layer = (
        int(material_class) in {MMD_MATERIAL_EYE, MMD_MATERIAL_LIP, MMD_MATERIAL_EMISSIVE, MMD_MATERIAL_TRANSPARENT}
        or _material_is_eye_detail(name_blob)
        or _material_is_brow_lash_or_mouth_detail(name_blob)
    )
    if int(render_bucket) >= MMD_RENDER_BUCKET_TRANSPARENT:
        return {
            "casts_self_shadow": False,
            "receives_self_shadow": False,
            "shadow_policy": "transparent_layer",
            "pmx_ground_shadow": bool(flags & _PMX_MATERIAL_FLAG_GROUND_SHADOW),
            "pmx_cast_self_shadow": bool(flags & _PMX_MATERIAL_FLAG_CAST_SELF_SHADOW),
            "pmx_receive_self_shadow": bool(flags & _PMX_MATERIAL_FLAG_RECEIVE_SELF_SHADOW),
        }
    if detail_layer:
        return {
            "casts_self_shadow": False,
            "receives_self_shadow": False,
            "shadow_policy": "face_detail_layer",
            "pmx_ground_shadow": bool(flags & _PMX_MATERIAL_FLAG_GROUND_SHADOW),
            "pmx_cast_self_shadow": bool(flags & _PMX_MATERIAL_FLAG_CAST_SELF_SHADOW),
            "pmx_receive_self_shadow": bool(flags & _PMX_MATERIAL_FLAG_RECEIVE_SELF_SHADOW),
        }
    if strict_flags:
        casts = bool(flags & _PMX_MATERIAL_FLAG_CAST_SELF_SHADOW)
        receives = bool(flags & _PMX_MATERIAL_FLAG_RECEIVE_SELF_SHADOW)
        policy = "pmx_flags"
    else:
        casts = True
        receives = True
        policy = "legacy_default"
    return {
        "casts_self_shadow": bool(casts),
        "receives_self_shadow": bool(receives),
        "shadow_policy": policy,
        "pmx_ground_shadow": bool(flags & _PMX_MATERIAL_FLAG_GROUND_SHADOW),
        "pmx_cast_self_shadow": bool(flags & _PMX_MATERIAL_FLAG_CAST_SELF_SHADOW),
        "pmx_receive_self_shadow": bool(flags & _PMX_MATERIAL_FLAG_RECEIVE_SELF_SHADOW),
    }


def _render_group_sort_key(group: dict[str, Any]) -> tuple[int, int, int, int]:
    bucket = int(group.get("render_bucket", MMD_RENDER_BUCKET_OPAQUE) or MMD_RENDER_BUCKET_OPAQUE)
    material_index = int(group.get("material_index", 0) or 0)
    if bucket >= MMD_RENDER_BUCKET_TRANSPARENT:
        face_layer_priority = int(group.get("face_layer_priority", 0) or 0)
        if face_layer_priority > 0:
            depth_band = round(float(group.get("sort_depth", 0.0) or 0.0) * 2.0) * 50
            return bucket, -depth_band, face_layer_priority, material_index
        depth_band = round(float(group.get("sort_depth", 0.0) or 0.0) * 100.0)
        priority = int(group.get("draw_priority", 0) or 0)
        return bucket, -depth_band, priority, material_index
    return bucket, 0, 0, material_index


def _material_bucket_rows(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for draw_order, group in enumerate(groups):
        material_class = int(group.get("material_class", MMD_MATERIAL_DEFAULT) or MMD_MATERIAL_DEFAULT)
        render_bucket = int(group.get("render_bucket", MMD_RENDER_BUCKET_OPAQUE) or MMD_RENDER_BUCKET_OPAQUE)
        diffuse = tuple(float(v) for v in (group.get("diffuse") or (0.0, 0.0, 0.0, 1.0)))
        rows.append(
            {
                "draw_order": int(draw_order),
                "material_index": int(group.get("material_index", draw_order) or 0),
                "name": str(group.get("name") or ""),
                "english_name": str(group.get("english_name") or ""),
                "material_class": int(material_class),
                "material_class_name": material_class_name(material_class),
                "render_bucket": int(render_bucket),
                "render_bucket_name": render_bucket_name(render_bucket),
                "draw_priority": int(group.get("draw_priority", 0) or 0),
                "face_layer_priority": int(group.get("face_layer_priority", 0) or 0),
                "sort_key": [int(v) for v in _render_group_sort_key(group)],
                "alpha": float(diffuse[3] if len(diffuse) > 3 else 1.0),
                "vertex_count": int(group.get("vertex_count", 0) or 0),
                "triangle_count": int((int(group.get("vertex_count", 0) or 0)) // 3),
                "depth_write": bool(group.get("depth_write", render_bucket <= MMD_RENDER_BUCKET_CUTOUT)),
                "casts_shadow": bool(group.get("casts_shadow", render_bucket <= MMD_RENDER_BUCKET_CUTOUT)),
                "receives_shadow": bool(group.get("receives_shadow", render_bucket <= MMD_RENDER_BUCKET_CUTOUT)),
                "casts_self_shadow": bool(group.get("casts_self_shadow", group.get("casts_shadow", False))),
                "receives_self_shadow": bool(group.get("receives_self_shadow", group.get("receives_shadow", False))),
                "shadow_policy": str(group.get("shadow_policy") or "legacy_default"),
                "pmx_ground_shadow": bool(group.get("pmx_ground_shadow", False)),
                "pmx_cast_self_shadow": bool(group.get("pmx_cast_self_shadow", False)),
                "pmx_receive_self_shadow": bool(group.get("pmx_receive_self_shadow", False)),
                "alpha_cutoff": float(group.get("alpha_cutoff", 0.0) or 0.0),
                "uv_alpha_mode": str(group.get("uv_alpha_mode") or "opaque"),
                "uv_alpha_sample_count": int(float(group.get("uv_alpha_sample_count", 0.0) or 0.0)),
                "uv_alpha_min": float(group.get("uv_alpha_min", 255.0)),
                "uv_alpha_max": float(group.get("uv_alpha_max", 255.0)),
                "uv_alpha_mean": float(group.get("uv_alpha_mean", 255.0)),
                "uv_alpha_mid_ratio": float(group.get("uv_alpha_mid_ratio", 0.0) or 0.0),
                "uv_alpha_opaque_ratio": float(group.get("uv_alpha_opaque_ratio", 0.0) or 0.0),
                "uv_alpha_transparent_ratio": float(group.get("uv_alpha_transparent_ratio", 0.0) or 0.0),
                "sort_depth": float(group.get("sort_depth", 0.0) or 0.0),
                "sort_depth_center": float(group.get("sort_depth_center", 0.0) or 0.0),
                "sort_depth_near": float(group.get("sort_depth_near", 0.0) or 0.0),
                "sort_depth_far": float(group.get("sort_depth_far", 0.0) or 0.0),
                "sort_depth_span": float(group.get("sort_depth_span", 0.0) or 0.0),
                "texture": str(group.get("texture") or ""),
                "toon_texture": str(group.get("toon_texture") or ""),
                "sphere_texture": str(group.get("sphere_texture") or ""),
                "sphere_mode": int(group.get("sphere_mode", 0) or 0),
                "edge_enabled": bool(group.get("edge_enabled")),
                "edge_color": [float(v) for v in (group.get("edge_color") or (0.0, 0.0, 0.0, 0.0))],
                "edge_size": float(group.get("edge_size", 0.0) or 0.0),
                "toon_ao_strength": float(group.get("toon_ao_strength", 0.0) or 0.0),
                "matcap_specular_strength": float(group.get("matcap_specular_strength", 0.0) or 0.0),
                "emissive_strength": float(group.get("emissive_strength", 0.0) or 0.0),
            }
        )
    return rows


def _material_class_counts(groups: list[dict[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in _MATERIAL_CLASS_NAMES.values()}
    for group in groups:
        name = material_class_name(int(group.get("material_class", MMD_MATERIAL_DEFAULT) or MMD_MATERIAL_DEFAULT))
        counts[name] = int(counts.get(name, 0)) + 1
    return {key: value for key, value in counts.items() if value}


def _gpu_vertex_morph_delta_slots(
    model: MMDModel,
    morph_names: tuple[str, ...],
    *,
    slot_count: int = MMD_GPU_MORPH_SLOTS,
) -> tuple[np.ndarray, ...]:
    if not morph_names or slot_count <= 0:
        return ()
    morph_by_name = {}
    for morph in model.morphs:
        if morph.vertex_morph is None:
            continue
        morph_by_name[str(morph.name)] = morph
        if morph.english_name:
            morph_by_name[str(morph.english_name)] = morph
    vertex_count = int(np.asarray(model.positions).shape[0])
    slots: list[np.ndarray] = []
    for name in morph_names[:slot_count]:
        deltas = np.zeros((vertex_count, 3), dtype=np.float32)
        morph = morph_by_name.get(str(name))
        if morph is not None and morph.vertex_morph is not None:
            indices = np.asarray(morph.vertex_morph.indices, dtype=np.int64)
            offsets = np.asarray(morph.vertex_morph.offsets, dtype=np.float32)
            valid = (indices >= 0) & (indices < vertex_count)
            if np.any(valid):
                deltas[indices[valid]] = offsets[valid]
        slots.append(np.ascontiguousarray(deltas, dtype=np.float32))
    return tuple(slots)


def _material_packet(
    model: MMDModel,
    material: MMDMaterial,
    material_index: int,
    material_indices: np.ndarray,
    positions: np.ndarray,
    normals: np.ndarray,
    *,
    gpu_skinning: bool = False,
    bone_matrix_count: int = 0,
    morph_deltas: tuple[np.ndarray, ...] = (),
) -> dict[str, Any] | None:
    usable = int(material_indices.size // 3) * 3
    if usable <= 0:
        return None
    idx = np.asarray(material_indices[:usable], dtype=np.int64)
    max_index = int(positions.shape[0]) - 1
    if max_index < 0:
        return None
    idx = np.clip(idx, 0, max_index)
    pos = positions[idx]
    tri_normals = normals[idx]
    uvs = model.uvs[idx]
    uv_min = np.min(uvs, axis=0)
    uv_max = np.max(uvs, axis=0)
    stride_floats = 8
    if gpu_skinning and int(bone_matrix_count) > 0:
        bone_indices = np.asarray(model.weights.bone_indices[idx], dtype=np.float32)
        bone_weights = np.asarray(model.weights.bone_weights[idx], dtype=np.float32)
        valid_bones = (bone_indices >= 0.0) & (bone_indices < float(bone_matrix_count))
        bone_weights = np.where(valid_bones, bone_weights, 0.0).astype(np.float32, copy=False)
        bone_indices = np.where(valid_bones, bone_indices, 0.0).astype(np.float32, copy=False)
        weight_sum = np.sum(bone_weights, axis=1, keepdims=True)
        missing = weight_sum[:, 0] <= 0.00001
        if np.any(missing):
            bone_indices[missing, 0] = 0.0
            bone_weights[missing, 0] = 1.0
            weight_sum[missing, 0] = 1.0
        bone_weights = bone_weights / np.maximum(weight_sum, 0.00001)
        row_parts = [pos, tri_normals, uvs, bone_indices, bone_weights]
        if morph_deltas:
            for slot in range(MMD_GPU_MORPH_SLOTS):
                if slot < len(morph_deltas):
                    slot_deltas = np.asarray(morph_deltas[slot], dtype=np.float32)
                    if slot_deltas.ndim == 2 and slot_deltas.shape[1] >= 3 and slot_deltas.shape[0] > max_index:
                        row_parts.append(slot_deltas[idx, :3])
                    else:
                        row_parts.append(np.zeros_like(pos, dtype=np.float32))
                else:
                    row_parts.append(np.zeros_like(pos, dtype=np.float32))
            stride_floats = 16 + MMD_GPU_MORPH_SLOTS * 3
        else:
            stride_floats = 16
        vertex_rows = np.concatenate(row_parts, axis=1).astype(np.float32, copy=False)
    else:
        vertex_rows = np.concatenate([pos, tri_normals, uvs], axis=1).astype(np.float32, copy=False)
    diffuse = _material_styled_diffuse(material, tuple(float(v) for v in material.diffuse))
    ambient = tuple(float(v) for v in material.ambient)
    specular = tuple(float(v) for v in material.specular)
    texture = _resolve_texture(model, material)
    toon_texture = _resolve_toon_texture(model, material)
    sphere_texture = _resolve_sphere_texture(model, material)
    render_bucket, alpha_cutoff = _render_bucket_and_cutoff(texture, diffuse)
    render_bucket, alpha_cutoff, uv_alpha_stats = _refine_render_bucket_with_material_alpha(
        texture,
        diffuse,
        uvs,
        render_bucket,
        alpha_cutoff,
    )
    material_class = _material_class(
        material,
        texture=texture,
        toon_texture=toon_texture,
        sphere_texture=sphere_texture,
        render_bucket=render_bucket,
    )
    shader_controls = _material_shader_controls(material_class, render_bucket)
    shader_controls.update(_material_named_shader_controls(material, material_class))
    draw_priority = _material_draw_priority(material, material_class, render_bucket, texture, toon_texture, sphere_texture)
    face_layer_priority = _material_face_layer_priority(material, material_class)
    edge_color, edge_size = _styled_edge(material, material_class, texture)
    strict_flags = model.path.suffix.casefold() == ".pmx"
    shadow_policy = _material_self_shadow_policy(
        material,
        material_class,
        render_bucket,
        strict_flags=strict_flags,
    )
    casts_self_shadow = bool(shadow_policy.get("casts_self_shadow", False))
    receives_self_shadow = bool(shadow_policy.get("receives_self_shadow", False))
    return {
        "name": material.name or material.english_name,
        "english_name": material.english_name,
        "material_index": int(material_index),
        "texture": texture,
        "sphere_texture": sphere_texture,
        "sphere_mode": int(material.sphere_mode),
        "toon_texture": toon_texture,
        "toon_shadow_color": _texture_darkest_rgb(toon_texture),
        "toon_shared": bool(material.toon_shared),
        "toon_index": int(material.toon_texture_index),
        "material_class": int(material_class),
        "face_layer_priority": int(face_layer_priority),
        **shader_controls,
        "vertices": np.ascontiguousarray(vertex_rows.reshape(-1), dtype=np.float32),
        "vertex_stride_floats": int(stride_floats),
        "gpu_skinning": bool(stride_floats > 8),
        "gpu_morph_slot_count": int(len(morph_deltas)) if stride_floats > 16 else 0,
        "vertex_count": int(vertex_rows.shape[0]),
        "diffuse": diffuse,
        "ambient": ambient,
        "specular": specular,
        "specular_strength": float(material.specular_strength),
        "edge_color": edge_color,
        "edge_size": float(edge_size),
        "edge_enabled": bool(
            _material_edge_enabled(
                material,
                material_class,
                strict_flags=strict_flags,
                texture=texture,
            )
        ),
        "flags": int(material.flags),
        "render_bucket": int(render_bucket),
        "draw_priority": int(draw_priority),
        "alpha_cutoff": float(alpha_cutoff),
        "uv_alpha_mode": str(uv_alpha_stats.get("mode") or "opaque"),
        "uv_alpha_sample_count": int(float(uv_alpha_stats.get("sample_count", 0.0) or 0.0)),
        "uv_alpha_min": float(uv_alpha_stats.get("min", 255.0)),
        "uv_alpha_max": float(uv_alpha_stats.get("max", 255.0)),
        "uv_alpha_mean": float(uv_alpha_stats.get("mean", 255.0)),
        "uv_alpha_mid_ratio": float(uv_alpha_stats.get("mid_ratio", 0.0) or 0.0),
        "uv_alpha_opaque_ratio": float(uv_alpha_stats.get("opaque_ratio", 0.0) or 0.0),
        "uv_alpha_transparent_ratio": float(uv_alpha_stats.get("transparent_ratio", 0.0) or 0.0),
        "sort_depth": 0.0,
        "center": tuple(float(v) for v in np.mean(pos, axis=0)),
        "bounds_min": tuple(float(v) for v in np.min(pos, axis=0)),
        "bounds_max": tuple(float(v) for v in np.max(pos, axis=0)),
        "uv_min": tuple(float(v) for v in uv_min),
        "uv_max": tuple(float(v) for v in uv_max),
        "depth_write": bool(render_bucket <= MMD_RENDER_BUCKET_CUTOUT),
        "casts_shadow": bool(casts_self_shadow),
        "receives_shadow": bool(receives_self_shadow),
        **shadow_policy,
    }


def _bounds(model: MMDModel, positions: np.ndarray | None = None) -> dict[str, Any]:
    if positions is not None and np.asarray(positions).size:
        arr = np.asarray(positions, dtype=np.float32)
        mins = np.min(arr, axis=0)
        maxs = np.max(arr, axis=0)
    else:
        mins = np.asarray(model.bounds_min, dtype=np.float32)
        maxs = np.asarray(model.bounds_max, dtype=np.float32)
    center = (mins + maxs) * 0.5
    size = np.maximum(maxs - mins, 0.0001)
    radius = float(np.linalg.norm(size) * 0.5)
    fit_extent = float(max(size[1], size[0] * 1.35, size[2] * 1.15, 0.0001))
    return {
        "min": tuple(float(v) for v in mins),
        "max": tuple(float(v) for v in maxs),
        "center": tuple(float(v) for v in center),
        "size": tuple(float(v) for v in size),
        "radius": max(0.0001, radius),
        "fit_extent": max(0.0001, fit_extent),
    }


def _rotation_matrix(pitch: float, yaw: float, roll: float) -> np.ndarray:
    px = math.radians(float(pitch))
    yy = math.radians(float(yaw))
    rz = math.radians(float(roll))
    cx, sx = math.cos(px), math.sin(px)
    cy, sy = math.cos(yy), math.sin(yy)
    cz, sz = math.cos(rz), math.sin(rz)
    rx = np.asarray([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float32)
    ry = np.asarray([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
    rz_mat = np.asarray([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
    return ry @ rx @ rz_mat


def _sort_render_groups(
    groups: list[dict[str, Any]],
    bounds: dict[str, Any],
    *,
    pitch: float,
    yaw: float,
    roll: float,
) -> list[dict[str, Any]]:
    center = np.asarray(bounds.get("center") or (0.0, 0.0, 0.0), dtype=np.float32)
    rotation = _rotation_matrix(pitch, yaw, roll)
    for group in groups:
        group_center = np.asarray(group.get("center") or center, dtype=np.float32)
        local = group_center - center
        center_depth = float((rotation @ local)[2])
        mins = np.asarray(group.get("bounds_min") or group_center, dtype=np.float32)
        maxs = np.asarray(group.get("bounds_max") or group_center, dtype=np.float32)
        corners = np.asarray(
            [
                (mins[0], mins[1], mins[2]),
                (mins[0], mins[1], maxs[2]),
                (mins[0], maxs[1], mins[2]),
                (mins[0], maxs[1], maxs[2]),
                (maxs[0], mins[1], mins[2]),
                (maxs[0], mins[1], maxs[2]),
                (maxs[0], maxs[1], mins[2]),
                (maxs[0], maxs[1], maxs[2]),
            ],
            dtype=np.float32,
        )
        depths = (rotation @ (corners - center).T)[2]
        group["sort_depth_center"] = center_depth
        group["sort_depth_near"] = float(np.min(depths))
        group["sort_depth_far"] = float(np.max(depths))
        group["sort_depth_span"] = float(np.max(depths) - np.min(depths))
        group["sort_depth"] = float(np.max(depths))

    sorted_groups = sorted(groups, key=_render_group_sort_key)
    for group in sorted_groups:
        group["render_bucket_name"] = render_bucket_name(int(group.get("render_bucket", MMD_RENDER_BUCKET_OPAQUE) or 0))
        group["material_class_name"] = material_class_name(int(group.get("material_class", MMD_MATERIAL_DEFAULT) or 0))
        group["draw_sort_key"] = [int(value) for value in _render_group_sort_key(group)]
    return sorted_groups


def _apply_hair_angel_ring_bounds(groups: list[dict[str, Any]]) -> None:
    hair_groups = [
        group
        for group in groups
        if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_HAIR
        and float(group.get("hair_angel_ring_strength", 0.0) or 0.0) > 0.001
    ]
    if not hair_groups:
        return
    mins = np.asarray([group.get("bounds_min") for group in hair_groups], dtype=np.float32)
    maxs = np.asarray([group.get("bounds_max") for group in hair_groups], dtype=np.float32)
    if mins.ndim != 2 or maxs.ndim != 2 or mins.shape[1] < 3 or maxs.shape[1] < 3:
        return
    union_min = np.min(mins[:, :3], axis=0)
    union_max = np.max(maxs[:, :3], axis=0)
    size = np.maximum(union_max - union_min, 0.0001)
    ring_min = union_min.copy()
    ring_max = union_max.copy()
    ring_min[1] = union_max[1] - size[1] * 0.46
    ring_max[1] = union_max[1] - size[1] * 0.07
    ring_min[0] = union_min[0] + size[0] * 0.08
    ring_max[0] = union_max[0] - size[0] * 0.08
    for group in hair_groups:
        group["hair_ring_bounds_min"] = tuple(float(v) for v in ring_min)
        group["hair_ring_bounds_max"] = tuple(float(v) for v in ring_max)


def _material_tuning_value(tuning: Mapping[str, Any] | None, key: str, default: float = 1.0) -> float:
    if not isinstance(tuning, Mapping):
        return float(default)
    try:
        return max(0.0, min(2.0, float(tuning.get(key, default))))
    except Exception:
        return float(default)


def _scale_group_float(group: dict[str, Any], key: str, scale: float, limit: float = 3.0) -> None:
    try:
        group[key] = max(0.0, min(float(limit), float(group.get(key, 0.0) or 0.0) * float(scale)))
    except Exception:
        pass


def _apply_material_tuning(groups: list[dict[str, Any]], tuning: Mapping[str, Any] | None) -> None:
    if not isinstance(tuning, Mapping):
        return
    skin = _material_tuning_value(tuning, "skin_warmth")
    hair = _material_tuning_value(tuning, "hair_highlight")
    eye = _material_tuning_value(tuning, "eye_highlight")
    lip = _material_tuning_value(tuning, "lip_specular")
    matcap = _material_tuning_value(tuning, "matcap_specular")
    emissive = _material_tuning_value(tuning, "emissive")
    for group in groups:
        material_class = int(group.get("material_class", 0) or 0)
        if material_class == MMD_MATERIAL_SKIN:
            _scale_group_float(group, "skin_warmth", skin, 2.0)
            _scale_group_float(group, "skin_shadow_lift", skin, 1.0)
            _scale_group_float(group, "skin_shadow_soften", skin, 1.0)
        elif material_class == MMD_MATERIAL_HAIR:
            _scale_group_float(group, "toon_highlight_strength", hair, 2.0)
            _scale_group_float(group, "rim_boost", hair, 3.0)
        elif material_class == MMD_MATERIAL_EYE:
            _scale_group_float(group, "eye_highlight_strength", eye, 2.5)
        elif material_class == MMD_MATERIAL_LIP:
            _scale_group_float(group, "lip_specular_strength", lip, 2.5)
        elif material_class in {MMD_MATERIAL_STOCKING, MMD_MATERIAL_METAL}:
            _scale_group_float(group, "matcap_specular_strength", matcap, 2.5)
            _scale_group_float(group, "sphere_strength", matcap, 2.5)
        if float(group.get("emissive_strength", 0.0) or 0.0) > 0.001:
            _scale_group_float(group, "emissive_strength", emissive, 3.0)


def build_mmd_render_item(
    model: MMDModel,
    *,
    render_mode: str = MMD_RENDER_TOON,
    yaw: float = 0.0,
    pitch: float = -8.0,
    roll: float = 0.0,
    zoom: float = 1.0,
    offset_x: float = 0.0,
    offset_y: float = -0.02,
    light_dir: tuple[float, float, float] = (0.42, -0.76, -0.48),
    lighting_preset: str = "studio_soft",
    lighting: Mapping[str, Any] | None = None,
    bloom_strength: float | None = None,
    material_tuning: Mapping[str, Any] | None = None,
    pose_geometry: MMDPoseGeometry | None = None,
    camera_controls: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Build a draw item accepted by ``OpenGLPreviewWidget.set_mmd_overlay_items``."""
    positions = pose_geometry.positions if pose_geometry is not None else model.positions
    normals = pose_geometry.normals if pose_geometry is not None else model.normals
    bone_matrices = None
    if pose_geometry is not None:
        candidate_matrices = getattr(pose_geometry, "bone_matrices", None)
        try:
            candidate_matrices = np.asarray(candidate_matrices, dtype=np.float32)
        except Exception:
            candidate_matrices = None
        if (
            candidate_matrices is not None
            and candidate_matrices.ndim == 3
            and candidate_matrices.shape[1:] == (4, 4)
            and int(candidate_matrices.shape[0]) > 0
            and not bool(pose_geometry.skinned)
            and int(pose_geometry.active_sdef_count) <= 0
        ):
            bone_matrices = np.ascontiguousarray(candidate_matrices, dtype=np.float32)
    gpu_skinning = bone_matrices is not None
    bone_matrix_count = int(bone_matrices.shape[0]) if bone_matrices is not None else 0
    gpu_morph_names: tuple[str, ...] = ()
    gpu_morph_weights: tuple[float, ...] = ()
    if gpu_skinning and pose_geometry is not None:
        gpu_morph_names = tuple(str(name) for name in getattr(pose_geometry, "gpu_morph_names", ())[:MMD_GPU_MORPH_SLOTS])
        raw_weights = tuple(float(weight) for weight in getattr(pose_geometry, "gpu_morph_weights", ())[:MMD_GPU_MORPH_SLOTS])
        gpu_morph_weights = tuple(raw_weights[i] if i < len(raw_weights) else 0.0 for i in range(len(gpu_morph_names)))
    model_sdef_count = int(np.count_nonzero(np.asarray(model.weights.weight_types, dtype=np.uint8) == 3))
    pose_sdef_count = int(pose_geometry.active_sdef_count) if pose_geometry is not None else model_sdef_count
    sdef_cpu_skinning_required = bool(model_sdef_count > 0)
    gpu_fallback_reason = "sdef_cpu_skinning_required" if sdef_cpu_skinning_required and not gpu_skinning else ""
    morph_deltas = _gpu_vertex_morph_delta_slots(model, gpu_morph_names) if gpu_morph_names else ()
    camera = camera_controls if isinstance(camera_controls, dict) else {}
    yaw = float(camera.get("yaw", yaw))
    pitch = float(camera.get("pitch", pitch))
    roll = float(camera.get("roll", roll))
    zoom = float(camera.get("zoom", zoom))
    offset_x = float(camera.get("offset_x", offset_x))
    offset_y = float(camera.get("offset_y", offset_y))
    groups: list[dict[str, Any]] = []
    cursor = 0
    for material_index, material in enumerate(model.materials):
        count = max(0, int(material.surface_count))
        if count <= 0:
            continue
        group = _material_packet(
            model,
            material,
            material_index,
            model.indices[cursor:cursor + count],
            positions,
            normals,
            gpu_skinning=gpu_skinning,
            bone_matrix_count=bone_matrix_count,
            morph_deltas=morph_deltas,
        )
        cursor += count
        if group is not None:
            groups.append(group)
    if not groups and model.indices.size >= 3:
        fallback = MMDMaterial(
            name="Default",
            english_name="Default",
            diffuse=(0.86, 0.82, 0.78, 1.0),
            specular=(0.2, 0.2, 0.2),
            specular_strength=8.0,
            ambient=(0.24, 0.24, 0.24),
            flags=0,
            edge_color=(0.02, 0.02, 0.02, 1.0),
            edge_size=0.0,
            texture_index=-1,
            sphere_texture_index=-1,
            sphere_mode=0,
            toon_texture_index=-1,
            toon_shared=False,
            memo="",
            surface_count=int(model.indices.size),
        )
        group = _material_packet(
            model,
            fallback,
            0,
            model.indices,
            positions,
            normals,
            gpu_skinning=gpu_skinning,
            bone_matrix_count=bone_matrix_count,
            morph_deltas=morph_deltas,
        )
        if group is not None:
            groups.append(group)
    mode = str(render_mode or MMD_RENDER_TOON).strip().casefold()
    if mode != MMD_RENDER_TOON:
        mode = MMD_RENDER_TOON
    lighting_overrides = dict(lighting or {})
    if bloom_strength is not None:
        value = max(0.0, min(2.0, float(bloom_strength)))
        lighting_overrides["bloom_enabled"] = value > 0.001
        lighting_overrides["bloom_strength"] = value
    resolved_lighting = resolve_mmd_lighting(lighting_preset, lighting_overrides)
    light_dir = tuple(float(v) for v in resolved_lighting.get("key_dir") or light_dir)
    bounds = _bounds(model, positions)
    _apply_material_tuning(groups, material_tuning)
    _apply_hair_angel_ring_bounds(groups)
    groups = _sort_render_groups(groups, bounds, pitch=pitch, yaw=yaw, roll=roll)
    bucket_counts = {
        "opaque": int(sum(1 for group in groups if int(group.get("render_bucket", 0) or 0) == MMD_RENDER_BUCKET_OPAQUE)),
        "cutout": int(sum(1 for group in groups if int(group.get("render_bucket", 0) or 0) == MMD_RENDER_BUCKET_CUTOUT)),
        "transparent": int(sum(1 for group in groups if int(group.get("render_bucket", 0) or 0) >= MMD_RENDER_BUCKET_TRANSPARENT)),
    }
    transparent_depths = [
        float(group.get("sort_depth", 0.0) or 0.0)
        for group in groups
        if int(group.get("render_bucket", 0) or 0) >= MMD_RENDER_BUCKET_TRANSPARENT
    ]
    transparent_sorted = all(
        transparent_depths[i] >= transparent_depths[i + 1] - 0.00001
        for i in range(max(0, len(transparent_depths) - 1))
    )
    missing_texture_rows = [
        {
            "material_index": int(group.get("material_index", -1)),
            "name": str(group.get("name") or ""),
            "texture": str(group.get("texture") or ""),
        }
        for group in groups
        if str(group.get("texture") or "").strip() and not Path(str(group.get("texture") or "")).is_file()
    ]
    missing_texture_count = int(len(missing_texture_rows))
    material_rows = _material_bucket_rows(groups)
    material_class_counts = _material_class_counts(groups)
    return {
        "type": "mmd_pmx",
        "path": str(model.path),
        "mesh_id": f"{model.path.resolve()}:{model.vertex_count}:{model.triangle_count}",
        "groups": groups,
        "bounds": bounds,
        "render_mode": mode,
        "yaw": float(yaw),
        "pitch": float(pitch),
        "roll": float(roll),
        "zoom": max(0.05, float(zoom)),
        "offset_x": float(offset_x),
        "offset_y": float(offset_y),
        "light_dir": tuple(float(v) for v in light_dir),
        "lighting": resolved_lighting,
        "gpu_skinning": bool(gpu_skinning),
        "bone_matrices": bone_matrices,
        "gpu_morph_names": gpu_morph_names,
        "gpu_morph_weights": gpu_morph_weights,
        "gpu_morph_slot_count": int(len(gpu_morph_names)),
        "diagnostics": {
            "vertex_count": int(model.vertex_count),
            "triangle_count": int(model.triangle_count),
            "material_count": int(len(model.materials)),
            "draw_group_count": int(len(groups)),
            "opaque_group_count": bucket_counts["opaque"],
            "cutout_group_count": bucket_counts["cutout"],
            "transparent_group_count": bucket_counts["transparent"],
            "material_bucket_counts": dict(bucket_counts),
            "material_class_counts": material_class_counts,
            "material_bucket_rows": material_rows,
            "transparent_material_rows": [
                row for row in material_rows
                if int(row.get("render_bucket", 0) or 0) >= MMD_RENDER_BUCKET_TRANSPARENT
            ],
            "skin_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_SKIN)),
            "hair_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_HAIR)),
            "stocking_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_STOCKING)),
            "eye_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_EYE)),
            "lip_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_LIP)),
            "metal_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_METAL)),
            "emissive_group_count": int(sum(1 for group in groups if int(group.get("material_class", 0) or 0) == MMD_MATERIAL_EMISSIVE)),
            "toon_contact_ao_group_count": int(sum(1 for group in groups if float(group.get("toon_ao_strength", 0.0) or 0.0) > 0.001)),
            "outline_group_count": int(sum(1 for group in groups if bool(group.get("edge_enabled")))),
            "shadow_caster_group_count": int(sum(1 for group in groups if bool(group.get("casts_shadow", True)))),
            "self_shadow_caster_group_count": int(sum(1 for group in groups if bool(group.get("casts_self_shadow", False)))),
            "self_shadow_receiver_group_count": int(sum(1 for group in groups if bool(group.get("receives_self_shadow", False)))),
            "pmx_shadow_flag_group_count": int(
                sum(
                    1
                    for group in groups
                    if bool(group.get("pmx_cast_self_shadow", False)) or bool(group.get("pmx_receive_self_shadow", False))
                )
            ),
            "sphere_texture_group_count": int(sum(1 for group in groups if str(group.get("sphere_texture") or "").strip())),
            "toon_texture_group_count": int(sum(1 for group in groups if str(group.get("toon_texture") or "").strip())),
            "bloom_group_count": int(sum(1 for group in groups if float(group.get("emissive_strength", 0.0) or 0.0) > 0.001)),
            "missing_texture_count": missing_texture_count,
            "missing_texture_rows": missing_texture_rows,
            "missing_texture_paths": [str(row.get("texture") or "") for row in missing_texture_rows],
            "transparent_sort_depth_monotonic": bool(transparent_sorted),
            "texture_count": int(len(model.textures)),
            "bone_count": int(len(model.bones)),
            "morph_count": int(len(model.morphs)),
            "skinned": bool(pose_geometry.skinned) if pose_geometry is not None else False,
            "gpu_skinning": bool(gpu_skinning),
            "gpu_skinning_available": bool(not sdef_cpu_skinning_required),
            "gpu_skinning_fallback_reason": gpu_fallback_reason,
            "sdef_cpu_skinning_required": bool(sdef_cpu_skinning_required),
            "sdef_weight_count": int(model_sdef_count),
            "bone_matrix_count": int(bone_matrix_count),
            "gpu_morph_slot_count": int(len(gpu_morph_names)),
            "gpu_morph_active_count": int(len(gpu_morph_names)),
            "mmd_vbo_cache_enabled": bool(gpu_skinning),
            "mmd_vbo_cache_size": 0,
            "mmd_vbo_cache_limit": 0,
            "mmd_vbo_cache_binds": 0,
            "mmd_vbo_cache_hits": 0,
            "mmd_vbo_cache_misses": 0,
            "mmd_vbo_cache_hit_rate": 0.0,
            "mmd_vbo_transient_uploads": 0,
            "mmd_vbo_uploaded_bytes": 0,
            "mmd_vbo_cached_bytes": 0,
            "mmd_vbo_cache_evictions": 0,
            "active_bone_count": int(pose_geometry.active_bone_count) if pose_geometry is not None else 0,
            "active_morph_count": int(pose_geometry.active_morph_count) if pose_geometry is not None else 0,
            "active_ik_count": int(pose_geometry.active_ik_count) if pose_geometry is not None else 0,
            "physics_body_count": int(pose_geometry.physics_body_count) if pose_geometry is not None else 0,
            "active_sdef_count": int(pose_sdef_count),
            "rigid_body_count": int(len(model.rigid_bodies)),
            "joint_count": int(len(model.joints)),
            "lighting_preset": str(resolved_lighting.get("preset") or "studio_soft"),
            "soft_shadow_enabled": bool(float(resolved_lighting.get("soft_shadow_strength", 0.0) or 0.0) > 0.001),
            "shadow_map_size": int(resolved_lighting.get("shadow_map_size", 1024) or 1024),
            "ground_shadow_enabled": bool(float(resolved_lighting.get("ground_shadow_strength", 0.0) or 0.0) > 0.001),
            "bloom_enabled": bool(resolved_lighting.get("bloom_enabled", True)),
            "bloom_strength": float(resolved_lighting.get("bloom_strength", 0.36) or 0.0),
            "hemisphere_ambient_enabled": True,
        },
    }
