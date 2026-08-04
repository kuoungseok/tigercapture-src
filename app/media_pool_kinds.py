"""Media Pool kind, extension, cache, and display-label helpers."""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import Qt

from app.image_media import IMAGE_EXTS


# Pool item visuals — square thumbnails in an icon-mode grid. The
# letterbox border keeps frames with a non-square source from being
# squished. Grid cell hugs the icon tightly so the click target is
# (almost) the icon itself — wide cell padding tends to land mouse
# clicks in empty space, which IconMode interprets as rubber-band
# selection rather than a drag-out.
THUMB_SIZE = 64
FEATURED_THUMB_W = 164
FEATURED_THUMB_H = 92
LIST_THUMB_W = 48
LIST_THUMB_H = 27
LIST_ROW_H = 40
GRID_W = 84
GRID_H = 106
ROLE_PERFORMANCE_SOURCE = Qt.ItemDataRole.UserRole + 9
ROLE_MMD_BADGE = Qt.ItemDataRole.UserRole + 10
VRM_AVATAR_MIME_TYPE = "application/x-tigerstudio-vrm-avatar"
_CACHE_LIMIT = 96
_DURATION_CACHE: "OrderedDict[tuple[str, int, int], int | None]" = OrderedDict()
_VIDEO_THUMB_CACHE: "OrderedDict[tuple[str, int, int, int], QPixmap]" = OrderedDict()


def _file_cache_key(path: Path) -> tuple[str, int, int]:
    try:
        st = path.stat()
        return str(path.resolve()), int(st.st_mtime_ns), int(st.st_size)
    except Exception:
        return str(path), 0, 0


def _cache_get(cache: OrderedDict, key):
    if key not in cache:
        return None
    value = cache.pop(key)
    cache[key] = value
    return value


def _cache_put(cache: OrderedDict, key, value) -> None:
    cache[key] = value
    while len(cache) > _CACHE_LIMIT:
        cache.popitem(last=False)


# Extensions we treat as importable media. Mirrors the editor's track
# drop filter so pool ↔ track behaviour is consistent. The pool now
# accepts audio too — DaVinci treats every media kind through the
# same pool.
VIDEO_EXTS = frozenset({
    ".mp4", ".mov", ".mkv", ".avi", ".webm",
    ".m4v", ".mpg", ".mpeg", ".wmv", ".gif",
})
AUDIO_EXTS = frozenset({
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma",
})
SPINE_EXTS = frozenset({
    ".skel", ".json", ".atlas",
})
VRM_EXTS = frozenset({
    ".vrm",
})
try:
    from app.ar_pbr.schema import SUPPORTED_ASSET_EXTS as _AR_PBR_SUPPORTED_ASSET_EXTS
except Exception:
    _AR_PBR_SUPPORTED_ASSET_EXTS = frozenset({
        ".fbx", ".glb", ".gltf", ".obj", ".usd", ".usdz", ".vrm",
    })
AR_PBR_EXTS = frozenset(str(ext).casefold() for ext in _AR_PBR_SUPPORTED_ASSET_EXTS) - VRM_EXTS
MMD_MODEL_EXTS = frozenset({
    ".pmx", ".pmd",
})
MMD_MOTION_EXTS = frozenset({
    ".vmd",
})
MOTION_PROJECT_EXTS = frozenset({
    ".tgmotion",
})
MMD_EXTS = MMD_MODEL_EXTS
MEDIA_EXTS = (
    VIDEO_EXTS | AUDIO_EXTS | IMAGE_EXTS | SPINE_EXTS | AR_PBR_EXTS
    | VRM_EXTS | MMD_EXTS | MOTION_PROJECT_EXTS
)
THREE_D_IMPORT_FILTER = (
    "3D / MMD Assets (*.fbx *.glb *.gltf *.obj *.usd *.usdz *.vrm *.pmx *.pmd *.pbx.json);;"
    "AR/PBR 3D Assets (*.fbx *.glb *.gltf *.obj *.usd *.usdz);;"
    "MMD Models (*.pmx *.pmd *.pbx.json);;"
    "VRM Avatars (*.vrm);;"
    "All Files (*)"
)


def _is_mmd_package_path(path: Path) -> bool:
    return path.name.casefold().endswith(".pbx.json")


def _is_3d_import_path(path: Path) -> bool:
    suffix = path.suffix.casefold()
    return (
        suffix in AR_PBR_EXTS
        or suffix in VRM_EXTS
        or suffix in MMD_MODEL_EXTS
        or _is_mmd_package_path(path)
    )


def _mmd_badge_label_for_path(path: Path) -> str:
    return "MMD"


def _mmd_kind_name_for_path(path: Path) -> str:
    return "MMD Motion" if path.suffix.casefold() == ".vmd" else "MMD Model"


def _badge_label_for_path(kind: str, path: Path | None = None) -> str:
    if kind == "M" and path is not None:
        return _mmd_badge_label_for_path(path)
    return {
        "I": "IMG",
        "R": "VRM",
        "M": "MMD",
        "G": "MOTION",
    }.get(kind, kind)


def _kind_for_path(p: Path) -> str:
    suf = p.suffix.lower()
    if suf in VIDEO_EXTS:
        return "V"
    if suf in IMAGE_EXTS:
        return "I"
    if suf in AUDIO_EXTS:
        return "A"
    if suf in MOTION_PROJECT_EXTS:
        return "G"
    if _is_mmd_package_path(p):
        return "M"
    if suf in SPINE_EXTS:
        return "S"
    if suf in VRM_EXTS:
        return "R"
    if suf in MMD_EXTS:
        return "M"
    if suf in AR_PBR_EXTS:
        return "3"
    return "?"


def _format_duration(ms: int | None) -> str:
    if ms is None or ms <= 0:
        return ""
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def _clean_item_stem(path: Path) -> str:
    name = (path.stem or path.name).replace("\uFF5C", "|").replace("\u3000", " ")
    return " ".join(name.split()) or path.name


def _middle_ellipsis(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 5:
        return f"{text[:max(1, max_chars - 3)]}..."
    tail = max(3, min(6, max_chars // 3))
    head = max(4, max_chars - tail - 3)
    return f"{text[:head]}...{text[-tail:]}"


def _compact_item_name(path: Path, max_chars: int = 11, *, include_suffix: bool = True) -> str:
    """Short display label; full path remains in tooltip."""
    name = _middle_ellipsis(_clean_item_stem(path), max_chars)
    suffix = path.suffix
    if include_suffix and suffix and len(name) + len(suffix) <= max_chars + 4:
        return f"{name}{suffix}"
    return name


def _media_pool_item_text(path: Path, duration: str, view_mode: str) -> str:
    if view_mode == "list":
        display_name = _compact_item_name(path, max_chars=24, include_suffix=False)
    else:
        display_name = _compact_item_name(path, max_chars=11)
    return f"{display_name}\n{duration}" if duration else display_name

