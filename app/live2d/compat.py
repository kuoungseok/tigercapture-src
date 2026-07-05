"""Compatibility helpers for Live2D runtime assets.

TigerCapture's renderer ultimately calls live2d-py's ``LoadModelJson``.
That loader expects ordinary Cubism runtime files, while Unity projects often
store the same payload as TextAsset-friendly ``*.bytes`` files, exported JSON
``_bytes`` arrays, raw Unity object dumps, or inside a ``.unitypackage``
archive.  This module converts those inputs into a cached standard Cubism
folder and returns a normal ``*.model3.json`` path.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any


_JSON_ASSET_SUFFIXES = (
    ".model3.json",
    ".motion3.json",
    ".exp3.json",
    ".physics3.json",
    ".pose3.json",
    ".userdata3.json",
    ".cdi3.json",
)

_BINARY_ASSET_SUFFIXES = (
    ".moc3",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".wav",
    ".mp3",
    ".ogg",
    ".m4a",
)

_KNOWN_ASSET_SUFFIXES = _JSON_ASSET_SUFFIXES + _BINARY_ASSET_SUFFIXES
_MAX_SUPPORTED_MOC3_VERSION = 5
_SAFE_MOTION_ITEM_KEYS = {"File", "FadeInTime", "FadeOutTime"}


def cache_root() -> Path:
    override = os.environ.get("TIGERCAPTURE_LIVE2D_COMPAT_CACHE")
    if override:
        root = Path(override)
    else:
        project_local = Path(__file__).resolve().parents[2] / "local_resources"
        if project_local.exists():
            root = project_local / "Live2DCompat"
        else:
            base = os.environ.get("LOCALAPPDATA")
            if base:
                root = Path(base) / "TigerCapture" / "Live2DCompat"
            else:
                root = Path.home() / ".tigercapture" / "live2d_compat"
    root.mkdir(parents=True, exist_ok=True)
    return root


def is_live2d_candidate(path: str | os.PathLike[str]) -> bool:
    p = Path(path)
    if p.is_dir():
        return find_model_in_path(p) is not None
    name = p.name.lower()
    return (
        name.endswith(".model3.json")
        or name.endswith(".model3.json.bytes")
        or name.endswith(".unitypackage")
        or _looks_like_model_json(p)
    )


def find_model_in_path(path: str | os.PathLike[str]) -> Path | None:
    p = Path(path)
    if p.is_file():
        if is_live2d_candidate(p):
            return p
        return _find_nearby_model(p)
    if not p.is_dir():
        return None
    models = sorted(p.rglob("*.model3.json"))
    if models:
        return models[0]
    byte_models = sorted(p.rglob("*.model3.json.bytes"))
    if byte_models:
        return byte_models[0]
    wrapped_models = _find_wrapped_models(p)
    if wrapped_models:
        return wrapped_models[0]
    return None


def normalize_live2d_model_path(path: str | os.PathLike[str]) -> str:
    """Return a ``*.model3.json`` path loadable by live2d-py.

    The returned path may be the original file, or a persistent compatibility
    cache copy when the source uses Unity ``*.bytes`` assets or a
    ``.unitypackage`` archive.
    """
    p = Path(path)
    if p.is_dir():
        found = find_model_in_path(p)
        if found is None:
            return ""
        return normalize_live2d_model_path(found)

    if p.name.lower().endswith(".unitypackage"):
        extracted = _extract_unitypackage(p)
        found = find_model_in_path(extracted)
        if found is None:
            return ""
        return normalize_live2d_model_path(found)

    found = find_model_in_path(p)
    if found is None:
        return ""
    p = found

    try:
        data = _read_json_asset(p)
    except Exception:
        return str(p)

    needs_ascii_cache = _model_needs_ascii_cache(p, data)
    if (
        _model_refs_are_directly_usable(p, data)
        and not _model_refs_need_sanitizing(data)
        and not _model_meta_needs_sanitizing(data)
        and not p.name.lower().endswith(".bytes")
        and not needs_ascii_cache
    ):
        return str(p)

    return str(_write_normalized_model(p, data, ascii_safe=needs_ascii_cache))


def moc3_version(model3_path: str | os.PathLike[str]) -> int:
    try:
        model_path = Path(normalize_live2d_model_path(model3_path))
        data = _read_json_asset(model_path)
        rel = (data.get("FileReferences") or {}).get("Moc") or ""
        moc = _resolve_existing_asset(model_path.parent, rel)
        if moc is None:
            return -1
        with moc.open("rb") as f:
            hdr = f.read(8)
        if hdr[:4] != b"MOC3":
            return -1
        return int(hdr[4])
    except Exception:
        return -1


def model_support_error(model3_path: str | os.PathLike[str]) -> str:
    version = moc3_version(model3_path)
    if version < 0:
        return "Invalid or missing MOC3; this Live2D model cannot be loaded safely."
    if version > _MAX_SUPPORTED_MOC3_VERSION:
        return (
            f"Unsupported MOC3 v{version}; current Live2D Core supports "
            f"up to v{_MAX_SUPPORTED_MOC3_VERSION}."
        )
    return ""


def _read_json_asset(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    data = json.loads(text)
    if isinstance(data, dict) and isinstance(data.get("FileReferences"), dict):
        return data
    payload = _json_bytes_payload(data)
    if payload is None:
        return data
    nested = json.loads(payload.decode("utf-8-sig"))
    if isinstance(nested, dict):
        return nested
    return data


def _source_key(path: Path) -> str:
    try:
        st = path.stat()
        seed = f"{path.resolve()}|{st.st_size}|{st.st_mtime_ns}"
    except Exception:
        seed = str(path)
    return hashlib.sha1(seed.encode("utf-8", "replace")).hexdigest()[:16]


def _strip_known_bytes_suffix(name: str) -> str | None:
    low = name.lower()
    if not low.endswith(".bytes"):
        return None
    base = name[:-6]
    if any(base.lower().endswith(sfx) for sfx in _KNOWN_ASSET_SUFFIXES):
        return base
    return None


def _is_ascii_text(value: object) -> bool:
    try:
        str(value).encode("ascii")
        return True
    except Exception:
        return False


def _model_needs_ascii_cache(model_path: Path, data: dict[str, Any]) -> bool:
    try:
        if not _is_ascii_text(model_path.resolve()):
            return True
    except Exception:
        if not _is_ascii_text(model_path):
            return True
    for rel in _iter_model_refs(data):
        if not _is_ascii_text(rel):
            return True
    return False


def _asset_suffix_for_name(name: str) -> str:
    low = name.lower()
    for suffix in sorted(_KNOWN_ASSET_SUFFIXES, key=len, reverse=True):
        if low.endswith(suffix):
            return suffix
    suffix = Path(name).suffix
    return suffix if suffix else ".bin"


def _strip_ref_bytes_suffix(ref: str) -> str:
    stripped = _strip_known_bytes_suffix(PurePosixPath(ref.replace("\\", "/")).name)
    if not stripped:
        return ref.replace("\\", "/")
    parts = list(PurePosixPath(ref.replace("\\", "/")).parts)
    parts[-1] = stripped
    return str(PurePosixPath(*parts))


def _json_bytes_payload(data: Any) -> bytes | None:
    if not isinstance(data, dict):
        return None
    value = data.get("_bytes")
    if isinstance(value, list):
        try:
            return bytes(int(v) & 0xFF for v in value)
        except Exception:
            return None
    if isinstance(value, str):
        import base64
        try:
            return base64.b64decode(value)
        except Exception:
            return value.encode("utf-8")
    return None


def _read_wrapped_bytes(path: Path) -> bytes | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return _json_bytes_payload(data)


def _looks_like_model_json(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".json":
        return False
    try:
        data = _read_json_asset(path)
    except Exception:
        return False
    refs = data.get("FileReferences")
    if not isinstance(refs, dict):
        return False
    return isinstance(refs.get("Moc"), str) or isinstance(refs.get("Textures"), list)


def _json_bytes_asset_names(path: Path) -> set[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return set()
    if _json_bytes_payload(data) is None:
        return set()

    names: set[str] = set()
    m_name = data.get("m_Name") or data.get("name") or data.get("Name")
    if isinstance(m_name, str) and m_name:
        names.add(m_name)
        names.add(Path(m_name).name)
    names.add(path.stem)
    names.add(path.name)
    return {name.lower() for name in names if name}


def _find_wrapped_models(root: Path) -> list[Path]:
    models: list[Path] = []
    for candidate in sorted(root.rglob("*.json")):
        if candidate.name.lower().endswith(".model3.json"):
            continue
        if _looks_like_model_json(candidate):
            models.append(candidate)
    return models


def _safe_rel_path(pathname: str) -> Path | None:
    pathname = pathname.replace("\\", "/").strip()
    if not pathname:
        return None
    pp = PurePosixPath(pathname)
    parts: list[str] = []
    for part in pp.parts:
        if part in ("", ".", "/") or part == "..":
            continue
        if ":" in part:
            part = part.split(":", 1)[-1]
        if part:
            parts.append(part)
    if not parts:
        return None
    return Path(*parts)


def _extract_unitypackage(path: Path) -> Path:
    out_dir = cache_root() / f"unitypackage_{_source_key(path)}"
    marker = out_dir / ".complete"
    if marker.exists():
        return out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    entries: dict[str, dict[str, tarfile.TarInfo]] = {}
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            parts = PurePosixPath(member.name).parts
            if len(parts) != 2:
                continue
            guid, kind = parts
            if kind in ("asset", "pathname"):
                entries.setdefault(guid, {})[kind] = member

        for pair in entries.values():
            pathname_member = pair.get("pathname")
            asset_member = pair.get("asset")
            if pathname_member is None or asset_member is None:
                continue
            pathname_file = tar.extractfile(pathname_member)
            asset_file = tar.extractfile(asset_member)
            if pathname_file is None or asset_file is None:
                continue
            pathname = pathname_file.read().decode("utf-8-sig", "replace")
            rel = _safe_rel_path(pathname)
            if rel is None:
                continue
            dst = out_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(asset_file.read())

    _mirror_bytes_aliases(out_dir)
    _materialize_wrapped_bytes(out_dir)
    marker.write_text("ok", encoding="utf-8")
    return out_dir


def _mirror_bytes_aliases(root: Path) -> None:
    for src in list(root.rglob("*.bytes")):
        stripped = _strip_known_bytes_suffix(src.name)
        if not stripped:
            continue
        dst = src.with_name(stripped)
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _materialize_wrapped_bytes(root: Path) -> None:
    for src in list(root.rglob("*.json")):
        payload = _read_wrapped_bytes(src)
        if payload is None:
            continue
        name = _asset_name_from_wrapped_json(src, payload)
        if not name:
            continue
        dst = src.with_name(name)
        if dst.exists():
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_trim_known_payload_header(payload, dst.name))


def _find_nearby_model(path: Path) -> Path | None:
    root = path.parent
    models = sorted(root.rglob("*.model3.json"))
    if models:
        return models[0]
    byte_models = sorted(root.rglob("*.model3.json.bytes"))
    if byte_models:
        return byte_models[0]
    wrapped_models = _find_wrapped_models(root)
    if wrapped_models:
        return wrapped_models[0]
    return None


def _resolve_existing_asset(base: Path, rel: str) -> Path | None:
    if not rel:
        return None
    rel_norm = rel.replace("\\", "/")
    safe_rel = _safe_rel_path(rel_norm)
    candidates: list[Path] = []
    if safe_rel is not None:
        direct = base / safe_rel
        candidates.extend([direct, direct.with_name(direct.name + ".bytes")])
        stripped = _strip_known_bytes_suffix(direct.name)
        if stripped:
            candidates.append(direct.with_name(stripped))
    for cand in candidates:
        if cand.is_file():
            return cand

    name = PurePosixPath(rel_norm).name
    names = [name]
    stripped = _strip_known_bytes_suffix(name)
    if stripped:
        names.append(stripped)
    else:
        names.append(name + ".bytes")

    search_roots = [base, base.parent]
    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        for wanted in names:
            try:
                match = next(root.rglob(wanted), None)
            except Exception:
                match = None
            if match and match.is_file():
                return match

        wrapped = _find_wrapped_bytes_asset(root, names)
        if wrapped is not None:
            return wrapped
    return None


def _find_wrapped_bytes_asset(root: Path, names: list[str]) -> Path | None:
    wanted = {name.lower() for name in names}
    wanted_stems = {Path(name).stem.lower() for name in names}
    for candidate in sorted(root.rglob("*.json")):
        names_in_file = _json_bytes_asset_names(candidate)
        if not names_in_file:
            continue
        if names_in_file & wanted:
            return candidate
        if names_in_file & wanted_stems:
            return candidate
    return None


def _asset_name_from_wrapped_json(path: Path, payload: bytes) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        data = {}
    names = _json_bytes_asset_names(path)
    base = next(iter(names), path.stem).strip()
    if "." in Path(base).name:
        return Path(base).name
    if payload.startswith(b"MOC3") or b"MOC3" in payload[:256]:
        return f"{base}.moc3"
    if payload.startswith(b"\x89PNG\r\n\x1a\n") or b"\x89PNG\r\n\x1a\n" in payload[:256]:
        return f"{base}.png"
    if payload.startswith(b"{") or payload.lstrip().startswith(b"{"):
        if isinstance(data, dict):
            m_name = data.get("m_Name")
            if isinstance(m_name, str) and "." in m_name:
                return Path(m_name).name
        return f"{base}.json"
    return ""


def _trim_known_payload_header(raw: bytes, target_name: str) -> bytes:
    low = target_name.lower()
    if low.endswith(".moc3"):
        idx = raw.find(b"MOC3", 0, 512)
        if idx > 0:
            return raw[idx:]
    elif low.endswith(".png"):
        magic = b"\x89PNG\r\n\x1a\n"
        idx = raw.find(magic, 0, 512)
        if idx > 0:
            return raw[idx:]
    elif low.endswith((".jpg", ".jpeg")):
        idx = raw.find(b"\xff\xd8\xff", 0, 512)
        if idx > 0:
            return raw[idx:]
    elif low.endswith(".webp"):
        idx = raw.find(b"RIFF", 0, 512)
        if idx > 0 and raw[idx + 8:idx + 12] == b"WEBP":
            return raw[idx:]
    return raw


def _iter_model_refs(data: dict[str, Any]):
    refs = data.get("FileReferences") or {}
    for key in ("Moc", "Physics", "Pose", "DisplayInfo", "UserData"):
        value = refs.get(key)
        if isinstance(value, str) and value:
            yield value
    for tex in refs.get("Textures") or []:
        if isinstance(tex, str) and tex:
            yield tex
    for expr in refs.get("Expressions") or []:
        value = expr.get("File") if isinstance(expr, dict) else None
        if isinstance(value, str) and value:
            yield value
    for items in (refs.get("Motions") or {}).values():
        for item in items or []:
            if not isinstance(item, dict):
                continue
            for key in ("File", "Sound"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    yield value


def _model_refs_are_directly_usable(model_path: Path, data: dict[str, Any]) -> bool:
    base = model_path.parent
    for rel in _iter_model_refs(data):
        safe = _safe_rel_path(rel)
        if safe is None:
            continue
        asset = base / safe
        if not asset.is_file():
            return False
        if not _asset_payload_is_directly_usable(asset):
            return False
    return True


def _model_refs_need_sanitizing(data: dict[str, Any]) -> bool:
    refs = data.get("FileReferences") or {}
    motions = refs.get("Motions")
    if not isinstance(motions, dict):
        return False
    for group, items in motions.items():
        if not isinstance(group, str) or not _is_ascii_text(group):
            return True
        if not isinstance(items, list):
            return True
        for item in items:
            if not isinstance(item, dict):
                return True
            if set(item.keys()) - _SAFE_MOTION_ITEM_KEYS:
                return True
            file_ref = item.get("File")
            if not isinstance(file_ref, str) or not file_ref:
                return True
            if not file_ref.lower().replace("\\", "/").endswith(".motion3.json"):
                return True
    return False


def _model_meta_needs_sanitizing(data: dict[str, Any]) -> bool:
    hit_areas = data.get("HitAreas")
    if hit_areas is None:
        return False
    if not isinstance(hit_areas, list):
        return True
    for item in hit_areas:
        if not isinstance(item, dict):
            return True
        name = item.get("Name")
        area_id = item.get("Id")
        if not isinstance(name, str) or not name:
            return True
        if not isinstance(area_id, str) or not area_id:
            return True
        if not _is_ascii_text(name) or not _is_ascii_text(area_id):
            return True
    return False


def _sanitize_hit_areas(data: dict[str, Any]) -> None:
    hit_areas = data.get("HitAreas")
    if hit_areas is None:
        return
    if not isinstance(hit_areas, list):
        data.pop("HitAreas", None)
        return
    clean: list[dict[str, str]] = []
    for item in hit_areas:
        if not isinstance(item, dict):
            continue
        name = item.get("Name")
        area_id = item.get("Id")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(area_id, str) or not area_id:
            continue
        if not _is_ascii_text(area_id):
            continue
        safe_name = name if _is_ascii_text(name) else f"Hit{len(clean)}"
        clean.append({"Name": safe_name, "Id": area_id})
    if clean:
        data["HitAreas"] = clean
    else:
        data.pop("HitAreas", None)


def _asset_payload_is_directly_usable(path: Path) -> bool:
    low = path.name.lower()
    if low.endswith(".moc3"):
        try:
            return path.read_bytes()[:4] == b"MOC3"
        except Exception:
            return False
    if low.endswith(".png"):
        try:
            return path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        except Exception:
            return False
    if low.endswith((".jpg", ".jpeg")):
        try:
            return path.read_bytes()[:3] == b"\xff\xd8\xff"
        except Exception:
            return False
    if low.endswith(".webp"):
        try:
            raw = path.read_bytes()[:12]
            return raw[:4] == b"RIFF" and raw[8:12] == b"WEBP"
        except Exception:
            return False
    return True


def _write_normalized_model(
    model_path: Path,
    data: dict[str, Any],
    ascii_safe: bool = False,
) -> Path:
    out_dir = cache_root() / f"model_{_source_key(model_path)}"
    out_dir.mkdir(parents=True, exist_ok=True)
    refs = data.setdefault("FileReferences", {})
    copied_refs: dict[str, Path] = {}
    _sanitize_hit_areas(data)

    def copy_ref(ref: str) -> str:
        adjusted = _strip_ref_bytes_suffix(ref)
        src = _resolve_existing_asset(model_path.parent, ref)
        if src is None and adjusted != ref:
            src = _resolve_existing_asset(model_path.parent, adjusted)
        if src is None and not ascii_safe:
            return adjusted
        if ascii_safe:
            key = str(src.resolve() if src is not None else adjusted)
            safe = copied_refs.get(key)
            if safe is None:
                suffix = _asset_suffix_for_name(adjusted or (src.name if src else "asset"))
                safe = Path("assets") / f"asset_{len(copied_refs):04d}{suffix}"
                copied_refs[key] = safe
        else:
            safe = _safe_rel_path(adjusted)
            if safe is None:
                safe = Path(src.name)
        dst = out_dir / safe
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src is not None and src.resolve() != dst.resolve():
            _write_asset_payload(src, dst)
        return safe.as_posix()

    for key in ("Moc", "Physics", "Pose", "DisplayInfo", "UserData"):
        value = refs.get(key)
        if isinstance(value, str) and value:
            refs[key] = copy_ref(value)

    textures = refs.get("Textures")
    if isinstance(textures, list):
        refs["Textures"] = [
            copy_ref(tex) if isinstance(tex, str) and tex else tex
            for tex in textures
        ]

    expressions = refs.get("Expressions")
    if isinstance(expressions, list):
        for expr in expressions:
            if isinstance(expr, dict) and isinstance(expr.get("File"), str):
                expr["File"] = copy_ref(expr["File"])

    motions = refs.get("Motions")
    if isinstance(motions, dict):
        sanitized_motions: dict[str, list[dict[str, Any]]] = {}
        for group, items in motions.items():
            clean_items: list[dict[str, Any]] = []
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                file_ref = item.get("File")
                if not isinstance(file_ref, str) or not file_ref:
                    continue
                if not file_ref.lower().replace("\\", "/").endswith(".motion3.json"):
                    continue
                clean_item: dict[str, Any] = {"File": copy_ref(file_ref)}
                for key in ("FadeInTime", "FadeOutTime"):
                    value = item.get(key)
                    if isinstance(value, (int, float)):
                        clean_item[key] = value
                clean_items.append(clean_item)
            if clean_items:
                if isinstance(group, str) and group and _is_ascii_text(group):
                    safe_group = group
                else:
                    safe_group = f"Motion{len(sanitized_motions)}"
                while safe_group in sanitized_motions:
                    safe_group = f"Motion{len(sanitized_motions)}"
                sanitized_motions[safe_group] = clean_items
        refs["Motions"] = sanitized_motions

    if ascii_safe:
        model_name = "model.model3.json"
    else:
        model_name = model_path.name
        stripped = _strip_known_bytes_suffix(model_name)
        if stripped:
            model_name = stripped
        if not model_name.lower().endswith(".model3.json"):
            model_name = model_path.stem + ".model3.json"
    out_model = out_dir / model_name
    out_model.write_text(
        json.dumps(data, ensure_ascii=ascii_safe, indent=2),
        encoding="utf-8",
    )
    return out_model


def _write_asset_payload(src: Path, dst: Path) -> None:
    payload = _read_wrapped_bytes(src)
    if payload is None:
        payload = src.read_bytes()
    payload = _trim_known_payload_header(payload, dst.name)
    dst.write_bytes(payload)
