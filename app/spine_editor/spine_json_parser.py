"""Full Spine JSON / binary .skel parser (Spine v3.x / v4.x).

Supports:
  - .json  / .skel.json   — Spine JSON export
  - .skel               — Spine binary (v3.6–v4.1, read-only)
  - .atlas              — texture atlas metadata

Usage:
    skel = load_spine_file("character.json")   # JSON
    skel = load_spine_file("character.skel")   # binary
"""
from __future__ import annotations
import json
import math
import re
import struct
from pathlib import Path
from typing import Optional, BinaryIO

from app.spine_editor.spine_data import (
    Bone, Slot, RegionAttachment, BoneKeyframe, BoneTimeline,
    DeformKeyframe, DeformTimeline, SlotAttachmentKeyframe,
    SlotAttachmentTimeline, IKConstraint, IKKeyframe, IKTimeline,
    Animation, SpineSkeleton, _parse_transform_mode,
)


def detect_spine_binary_version(path: str | Path) -> str:
    """Best-effort version sniff for Spine binary files."""
    try:
        with open(path, "rb") as f:
            head = f.read(256)
    except Exception:
        return ""
    match = re.search(rb"\d+\.\d+(?:\.\d+)?", head)
    return match.group(0).decode("ascii", errors="ignore") if match else ""


# ── Public entry point ─────────────────────────────────────────────────────

def load_spine_file(path: str) -> SpineSkeleton:
    """Auto-detect format and parse a Spine skeleton file."""
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in (".json", ".txt") or p.name.endswith(".skel.json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return parse_spine_json(data)
    elif suffix == ".skel":
        version = detect_spine_binary_version(path)
        try:
            parts = [int(part) for part in version.split(".")[:2]]
        except Exception:
            parts = []
        if len(parts) >= 2 and (parts[0], parts[1]) >= (4, 2):
            raise ValueError(
                f"Unsupported Spine binary v{version}; current parser supports "
                "Spine 3.8 and 4.0/4.1 best-effort. Use JSON export or a 4.2 runtime."
            )
        with open(path, "rb") as f:
            return _parse_spine_binary(f)
    else:
        raise ValueError(f"Unknown Spine file extension: {suffix!r}")


def load_atlas(path: str) -> dict[str, tuple[int, ...]]:
    """
    Parse a Spine .atlas file (v3 and v4 formats).
    Returns {region_name: (page_index, x, y, w, h, rotate_degrees,
                           orig_w, orig_h, off_x, off_y, stored_w, stored_h)}.

    Spine 3.x: region properties are indented.
    Spine 4.x: region properties are NOT indented (flat format).
    Both formats are handled by a state-machine parser.
    """
    regions: dict[str, tuple] = {}
    try:
        with open(path, encoding="utf-8-sig") as f:   # utf-8-sig strips BOM
            lines = [ln.rstrip("\n\r") for ln in f]

        _IMG_EXTS = {"png", "jpg", "webp", "jpeg"}
        # Page-level property keys that appear without indentation in v4
        _PAGE_KEYS = {"size", "filter", "repeat", "format", "pma", "scale",
                      "atlas", "premultipliedAlpha"}

        page_index = -1
        cur_region: str | None = None
        rx = ry = rw = rh = 0
        orig_w = orig_h = 0
        off_x = off_y = 0
        rrotate = 0
        stored_w = stored_h = 0

        def _flush():
            nonlocal cur_region, rx, ry, rw, rh, orig_w, orig_h, off_x, off_y, rrotate, stored_w, stored_h
            if cur_region and rw > 0 and rh > 0:
                ow = orig_w or rw
                oh = orig_h or rh
                sw, sh = stored_w, stored_h
                if sw <= 0 or sh <= 0:
                    if rrotate in (90, 270):
                        sw, sh = rh, rw
                    else:
                        sw, sh = rw, rh
                regions[cur_region] = (
                    max(0, page_index), rx, ry, rw, rh, rrotate,
                    ow, oh, off_x, off_y, sw, sh
                )
            cur_region = None
            rx = ry = rw = rh = 0
            orig_w = orig_h = 0
            off_x = off_y = 0
            rrotate = 0
            stored_w = stored_h = 0

        for line in lines:
            if not line.strip():
                continue
            stripped = line.strip()
            is_indented = line[0] in (" ", "\t")

            if ":" in stripped:
                key = stripped.split(":", 1)[0].strip()
                val = stripped.split(":", 1)[1].strip()

                # Indented → always a region property (Spine 3.x style)
                # Non-indented + known page key → page property, skip
                # Non-indented + unknown key + inside region → region property (Spine 4.x)
                if not is_indented and key in _PAGE_KEYS:
                    _flush()  # page props signal end of previous region
                    continue

                # Region property (indented 3.x OR non-indented 4.x inside a region)
                if cur_region is not None or is_indented:
                    if key == "bounds":
                        parts = val.split(",")
                        if len(parts) >= 4:
                            rx, ry, rw, rh = (int(p.strip()) for p in parts[:4])
                    elif key == "xy":
                        parts = val.split(",")
                        rx, ry = int(parts[0].strip()), int(parts[1].strip())
                    elif key == "size" and cur_region is not None:
                        parts = val.split(",")
                        rw, rh = int(parts[0].strip()), int(parts[1].strip())
                    elif key == "orig":
                        parts = val.split(",")
                        if len(parts) >= 2:
                            orig_w, orig_h = int(parts[0].strip()), int(parts[1].strip())
                    elif key == "offset":
                        parts = val.split(",")
                        if len(parts) >= 2:
                            off_x, off_y = int(parts[0].strip()), int(parts[1].strip())
                    elif key == "offsets":
                        parts = val.split(",")
                        if len(parts) >= 4:
                            off_x, off_y, orig_w, orig_h = (
                                int(p.strip()) for p in parts[:4]
                            )
                    elif key == "rotate":
                        lower_val = val.lower()
                        if "true" in lower_val:
                            rrotate = 90
                        elif "false" in lower_val:
                            rrotate = 0
                        else:
                            try:
                                rrotate = int(float(val)) % 360
                            except Exception:
                                rrotate = 0
                    # offsets/index/etc. — ignored for now
                continue

            # No colon — image filename or region name
            if "." in stripped:
                ext = stripped.rsplit(".", 1)[-1].lower()
                if ext in _IMG_EXTS:
                    _flush()
                    page_index += 1
                    continue

            # Region name
            _flush()
            cur_region = stripped

        _flush()
    except Exception:
        pass
    return regions


def load_atlas_pages(atlas_path: str) -> list[str]:
    """Return list of page image filenames referenced by the atlas."""
    pages = []
    try:
        with open(atlas_path, encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip()
                if stripped and "." in stripped and not line.startswith(" ") and not line.startswith("\t"):
                    ext = stripped.rsplit(".", 1)[-1].lower()
                    if ext in ("png", "jpg", "webp", "jpeg") and not stripped.startswith("#"):
                        pages.append(stripped)
    except Exception:
        pass
    return pages


def atlas_is_pma(atlas_path: str) -> bool:
    """Return True if the atlas declares premultiplied alpha (pma:true)."""
    try:
        with open(atlas_path, encoding="utf-8-sig") as f:
            for line in f:
                stripped = line.strip().lower()
                if stripped.startswith("pma:"):
                    return "true" in stripped
                # Stop scanning once we leave the header (first region name)
                if stripped and ":" not in stripped and "." not in stripped:
                    break
    except Exception:
        pass
    return False


# ── JSON parser ────────────────────────────────────────────────────────────

def parse_spine_json(data: dict) -> SpineSkeleton:
    """Parse Spine JSON (v3.x / v4.x) into SpineSkeleton."""
    sk = data.get("skeleton", {})
    skel = SpineSkeleton(
        name=sk.get("name", "skeleton"),
        width=float(sk.get("width", 500)),
        height=float(sk.get("height", 800)),
    )

    # ── Bones
    for bd in data.get("bones", []):
        skel.bones.append(Bone(
            name=bd["name"],
            parent=bd.get("parent"),
            x=float(bd.get("x", 0)),
            y=float(bd.get("y", 0)),
            rotation=float(bd.get("rotation", 0)),
            scale_x=float(bd.get("scaleX", 1)),
            scale_y=float(bd.get("scaleY", 1)),
            shear_x=float(bd.get("shearX", 0)),
            shear_y=float(bd.get("shearY", 0)),
            length=float(bd.get("length", 60)),
            transform_mode=_parse_transform_mode(bd.get("transform", "normal")),
        ))

    # ── Slots
    for sd in data.get("slots", []):
        skel.slots.append(Slot(
            name=sd["name"],
            bone=sd["bone"],
            attachment=sd.get("attachment"),
            color=sd.get("color", "ffffffff"),
        ))

    # ── Skins (v3: dict-of-dicts, v4: list of {name, attachments})
    skins_raw = data.get("skins", {})
    if isinstance(skins_raw, list):
        for skin_data in skins_raw:
            skin_name = skin_data.get("name", "default")
            skel.skins[skin_name] = _parse_skin_attachments(skin_data.get("attachments", {}))
    else:
        for skin_name, slot_dict in skins_raw.items():
            skel.skins[skin_name] = _parse_skin_attachments(slot_dict)

    for order, ik_data in enumerate(data.get("ik", [])):
        skel.ik_constraints.append(
            IKConstraint(
                name=ik_data.get("name", ""),
                bones=list(ik_data.get("bones", [])),
                target=ik_data.get("target", ""),
                order=int(ik_data.get("order", order)),
                mix=float(ik_data.get("mix", 1.0)),
                compress=bool(ik_data.get("compress", False)),
                stretch=bool(ik_data.get("stretch", False)),
                uniform=bool(ik_data.get("uniform", False)),
            )
        )

    resolve_linked_meshes(skel)

    # ── Animations
    for anim_name, anim_data in data.get("animations", {}).items():
        anim = _parse_animation(anim_name, anim_data, skel)
        skel.animations[anim_name] = anim

    skel.update_world_transforms()
    skel.store_bind_pose()  # save bind rotations BEFORE any animation is applied
    return skel


def _parse_skin_attachments(slot_dict: dict) -> dict:
    skin: dict = {}
    for slot_name, attach_dict in slot_dict.items():
        skin[slot_name] = {}
        for attach_name, attach_data in attach_dict.items():
            skin[slot_name][attach_name] = _parse_attachment(attach_name, attach_data)
    return skin


def resolve_linked_meshes(skel) -> None:
    """For each linkedmesh attachment, copy vertices+triangles from the parent skin's mesh.

    UV coordinates are NOT copied — linkedmesh defines its own UVs pointing to
    its own skin-specific atlas region. Only mesh_weights (bone influence data)
    and mesh_triangles (topology) are shared with the parent.
    """
    for skin_name, skin_data in skel.skins.items():
        for slot_name, attachments in skin_data.items():
            for attach_name, attach in attachments.items():
                if getattr(attach, 'mesh_weights', None) == [] and getattr(attach, '_linked_skin', None):
                    parent_skin = skel.skins.get(attach._linked_skin, {})
                    parent_slot = parent_skin.get(slot_name, {})
                    parent_attach = parent_slot.get(attach._linked_parent or attach_name)
                    if parent_attach and getattr(parent_attach, 'mesh_weights', None):
                        attach.mesh_weights = parent_attach.mesh_weights
                        # Keep linked mesh's own UVs (skin-specific texture region)
                        # Only copy triangles if the linked mesh has none of its own
                        if not attach.mesh_triangles:
                            attach.mesh_triangles = getattr(parent_attach, 'mesh_triangles', [])
                        if not attach.mesh_uvs:
                            attach.mesh_uvs = getattr(parent_attach, 'mesh_uvs', [])


_NON_VISUAL_TYPES = {"point", "boundingbox", "path", "clipping"}

def _parse_attachment(name: str, data: dict) -> RegionAttachment:
    attach_name = data.get("name", name)
    uvs = list(data.get("uvs", []))
    n_verts = len(uvs) // 2
    mesh_weights = _parse_mesh_weights(data.get("vertices", []), n_verts)
    attach = RegionAttachment(
        name=name,
        path=data.get("path", attach_name),
        x=float(data.get("x", 0)),
        y=float(data.get("y", 0)),
        rotation=float(data.get("rotation", 0)),
        scale_x=float(data.get("scaleX", 1)),
        scale_y=float(data.get("scaleY", 1)),
        width=float(data.get("width", 100)),
        height=float(data.get("height", 100)),
        mesh_weights=mesh_weights,
        mesh_uvs=list(data.get("uvs", [])),
        mesh_triangles=list(data.get("triangles", [])),
    )
    attach_type = data.get("type", "region")
    if attach_type in _NON_VISUAL_TYPES:
        attach._non_visual = True
    if attach_type == "linkedmesh":
        attach._linked_skin   = data.get("skin", "")
        attach._linked_parent = data.get("parent", name)
    return attach


def _parse_mesh_weights(vertices: list, n_verts: int = 0) -> list:
    """Parse Spine mesh vertices array into [(bone_idx, lx, ly, weight), ...] per vertex.

    Weighted format: [count, bone_idx, lx, ly, weight, ...] repeated per vertex.
    Unweighted format: [lx, ly, lx, ly, ...] — 2 values per vertex.

    For unweighted verts bone_idx is set to -1 (sentinel: "use slot's own bone").
    Detection: if len(vertices) == 2*n_verts → unweighted; otherwise weighted.
    Falls back to heuristic when n_verts is unknown.
    """
    if not vertices:
        return []
    result = []
    i = 0

    # Reliable detection when n_verts is known (passed from UV list length)
    is_unweighted = (n_verts > 0 and len(vertices) == 2 * n_verts)
    if not is_unweighted and n_verts > 0 and len(vertices) > 2 * n_verts:
        is_unweighted = False  # weighted
    elif not is_unweighted:
        # Heuristic fallback: if first value is a small non-negative integer (bone count) → weighted
        is_unweighted = not (len(vertices) > 0 and isinstance(vertices[0], (int, float)) and 0 <= vertices[0] <= 16)

    if is_unweighted:
        # Unweighted: pairs of (lx, ly) — bone_idx=-1 means "use slot's own bone"
        while i + 1 < len(vertices):
            lx = float(vertices[i])
            ly = float(vertices[i + 1])
            result.append([(-1, lx, ly, 1.0)])
            i += 2
        return result

    # Weighted format: [count, bone_idx, lx, ly, weight, ...] per vertex
    while i < len(vertices):
        count = int(vertices[i]); i += 1
        vtx_bones = []
        for _ in range(count):
            if i + 3 >= len(vertices):
                i = len(vertices)
                break
            bone_idx = int(vertices[i])
            lx      = float(vertices[i + 1])
            ly      = float(vertices[i + 2])
            weight  = float(vertices[i + 3])
            vtx_bones.append((bone_idx, lx, ly, weight))
            i += 4
        result.append(vtx_bones)
    return result


def _mesh_is_weighted(attach: RegionAttachment | None) -> bool:
    if not attach:
        return False
    for vtx_bones in getattr(attach, "mesh_weights", []) or []:
        for bone_idx, _lx, _ly, _weight in vtx_bones:
            if bone_idx >= 0:
                return True
    return False


def _mesh_deform_value_count(attach: RegionAttachment | None) -> int:
    if not attach:
        return 0
    weights = getattr(attach, "mesh_weights", []) or []
    if _mesh_is_weighted(attach):
        return sum(len(vtx_bones) for vtx_bones in weights) * 2
    return len(weights) * 2


def _mesh_unweighted_base_vertices(attach: RegionAttachment | None) -> list[float]:
    if not attach or _mesh_is_weighted(attach):
        return []
    flat: list[float] = []
    for vtx_bones in getattr(attach, "mesh_weights", []) or []:
        if len(vtx_bones) != 1:
            return []
        bone_idx, lx, ly, weight = vtx_bones[0]
        if bone_idx >= 0 or abs(weight - 1.0) > 1e-5:
            return []
        flat.extend([float(lx), float(ly)])
    return flat


def _parse_json_deform_frame(kf: dict, attach: RegionAttachment | None) -> list[float]:
    value_count = _mesh_deform_value_count(attach)
    weighted = _mesh_is_weighted(attach)
    values = [float(v) for v in kf.get("vertices", [])]
    start = int(kf.get("offset", 0))

    if weighted:
        deform = [0.0] * max(value_count, start + len(values))
        if values:
            deform[start:start + len(values)] = values
        return deform

    base_vertices = _mesh_unweighted_base_vertices(attach)
    if base_vertices:
        value_count = len(base_vertices)
    deform_offsets = [0.0] * max(value_count, start + len(values))
    if values:
        deform_offsets[start:start + len(values)] = values
    if base_vertices:
        if len(deform_offsets) < len(base_vertices):
            deform_offsets.extend([0.0] * (len(base_vertices) - len(deform_offsets)))
        return [
            base_vertices[i] + deform_offsets[i]
            for i in range(len(base_vertices))
        ]
    return deform_offsets


def _parse_animation(name: str, data: dict, skel: SpineSkeleton | None = None) -> Animation:
    anim = Animation(name=name)
    duration = 0.0

    # bones timelines
    for bone_name, timelines in data.get("bones", {}).items():
        for prop, kf_list in timelines.items():
            tl = BoneTimeline(bone=bone_name, property=prop)
            for kf in kf_list:
                # "value" for translate/scale, "angle"/"value" for rotate
                val = kf.get("value", kf.get("angle", kf.get("x", kf.get("y", 0.0))))
                curve = kf.get("curve", "linear")
                time = float(kf.get("time", 0))
                tl.keyframes.append(BoneKeyframe(
                    time=time,
                    value=float(val),
                    curve="bezier" if isinstance(curve, list) else str(curve),
                ))
                duration = max(duration, time)
            if tl.keyframes:
                anim.timelines.append(tl)

    # slots timelines (color/attachment — stored but not evaluated for now)
    for slot_name, timelines in data.get("slots", {}).items():
        for prop, kf_list in timelines.items():
            if prop == "attachment":
                tl = SlotAttachmentTimeline(slot=slot_name)
                for kf in kf_list:
                    time = float(kf.get("time", 0))
                    tl.keyframes.append(
                        SlotAttachmentKeyframe(
                            time=time,
                            attachment=kf.get("name", kf.get("attachment")),
                        )
                    )
                    duration = max(duration, time)
                if tl.keyframes:
                    anim.timelines.append(tl)
                continue

            tl = BoneTimeline(bone=f"__slot_{slot_name}", property=prop)
            for kf in kf_list:
                time = float(kf.get("time", 0))
                tl.keyframes.append(BoneKeyframe(
                    time=time,
                    value=0.0,
                ))
                duration = max(duration, time)
            if tl.keyframes:
                anim.timelines.append(tl)

    # IK timelines
    for ik_name, kf_list in data.get("ik", {}).items():
        setup_mix = 1.0
        if skel is not None:
            con = next((c for c in skel.ik_constraints if c.name == ik_name), None)
            if con is not None:
                setup_mix = con.mix
        tl = IKTimeline(name=ik_name)
        for kf in kf_list:
            time = float(kf.get("time", 0))
            curve = kf.get("curve", "linear")
            tl.keyframes.append(IKKeyframe(
                time=time,
                mix=float(kf.get("mix", setup_mix)),
                curve="bezier" if isinstance(curve, list) else str(curve),
            ))
            duration = max(duration, time)
        if tl.keyframes:
            anim.timelines.append(tl)

    if skel is not None:
        deform_data = data.get("deform", data.get("ffd", {}))
        for _skin_name, slot_map in deform_data.items():
            for slot_name, attachments in slot_map.items():
                for attachment_name, kf_list in attachments.items():
                    attach = _find_attachment(skel, slot_name, attachment_name)
                    tl = DeformTimeline(slot=slot_name, attachment=attachment_name)
                    for kf in kf_list:
                        time = float(kf.get("time", 0))
                        curve = kf.get("curve", "linear")
                        tl.keyframes.append(
                            DeformKeyframe(
                                time=time,
                                vertices=_parse_json_deform_frame(kf, attach),
                                curve="bezier" if isinstance(curve, list) else str(curve),
                            )
                        )
                        duration = max(duration, time)
                    if tl.keyframes:
                        anim.timelines.append(tl)

    anim.duration = max(duration, 1.0)
    return anim


# ── Binary .skel parser ────────────────────────────────────────────────────
# Implements Spine 3.6–4.1 binary format (subset: bones, slots, animations).
# Full mesh/path/IK data is skipped (seek-past strategy).

class _BinaryReader:
    """Minimal binary reader with Spine's string/varint encoding."""

    def __init__(self, f: BinaryIO):
        self._f = f
        self._strings: list[str] = []

    def read_byte(self) -> int:
        return struct.unpack("B", self._f.read(1))[0]

    def read_bool(self) -> bool:
        return self.read_byte() != 0

    def read_varint(self, optimise_positive: bool = True) -> int:
        """Read variable-length int32. Spine caps at 5 bytes (like spine-ts readInt)."""
        b = self.read_byte()
        result = b & 0x7F
        if b & 0x80:
            b = self.read_byte()
            result |= (b & 0x7F) << 7
            if b & 0x80:
                b = self.read_byte()
                result |= (b & 0x7F) << 14
                if b & 0x80:
                    b = self.read_byte()
                    result |= (b & 0x7F) << 21
                    if b & 0x80:
                        b = self.read_byte()
                        result |= (b & 0x7F) << 28
        if not optimise_positive:
            result = (result >> 1) ^ -(result & 1)
        return result

    def read_float(self) -> float:
        return struct.unpack(">f", self._f.read(4))[0]

    def read_int(self) -> int:
        return struct.unpack(">i", self._f.read(4))[0]

    def read_short(self) -> int:
        return struct.unpack(">H", self._f.read(2))[0]

    def read_string(self) -> Optional[str]:
        idx = self.read_varint()
        if idx == 0:
            return None
        real_idx = idx - 1
        if real_idx < 0 or real_idx >= len(self._strings):
            return f"__str_{idx}"
        return self._strings[real_idx]

    def skip_bytes(self, n: int) -> None:
        self._f.read(n)


def _parse_spine_binary(f: BinaryIO) -> SpineSkeleton:
    r = _BinaryReader(f)

    # Header
    hash_str, version_str = _read_binary_header(f)

    # Detect version
    try:
        parts = version_str.split(".")
        major = int(parts[0]) if parts else 3
        minor = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        major, minor = 3, 0

    is_v4  = major >= 4
    is_38p = (major == 3 and minor >= 8) or is_v4
    non_essential = False  # default; updated below if applicable

    # 3.8+ header: x, y, width, height (4.x adds non-essential flag)
    if is_38p:
        _x     = struct.unpack(">f", f.read(4))[0]
        _y     = struct.unpack(">f", f.read(4))[0]
    _width = struct.unpack(">f", f.read(4))[0]
    _height = struct.unpack(">f", f.read(4))[0]

    if is_v4:
        non_essential = f.read(1)[0] != 0
        if non_essential:
            f.read(4)      # fps
            _read_bstr(f)  # images path
            _read_bstr(f)  # audio path
    elif is_38p:
        # 3.8: non-essential flag + optional fps/images/audio
        non_essential = f.read(1)[0] != 0
        if non_essential:
            f.read(4)  # fps float
            _read_bstr(f)  # images path
            _read_bstr(f)  # audio path

    # String table: Spine 4.x uses a string table; Spine 3.8 uses inline strings.
    if is_v4:
        n_strings = r.read_varint()
        r._strings = [_read_bstr_raw(f) for _ in range(n_strings)]

    def read_str_38() -> Optional[str]:
        """Spine 3.8 inline string: varint byteCount (0=null,1=empty,n=n-1 chars)."""
        byte_count = r.read_varint(optimise_positive=True)
        if byte_count == 0:
            return None
        if byte_count == 1:
            return ""
        return f.read(byte_count - 1).decode("utf-8", errors="replace")

    def read_str() -> Optional[str]:
        if is_v4:
            return _read_bstr(f)
        return read_str_38()

    # Spine 3.8 has a string table for attachment/skin/animation names.
    # Bone and slot names use inline strings (read_str_38), but attachment
    # names use table indices (same 0=null / 1=empty / n=table[n-2] encoding as 4.x).
    str_table_38: list[str] = []
    if is_38p and not is_v4:
        n_str_table = r.read_varint()
        str_table_38 = [read_str_38() or "" for _ in range(n_str_table)]

    def read_str_idx_38() -> Optional[str]:
        """Read a 3.8 string table reference: 0=null, n=strings[n-1] (1-indexed)."""
        idx = r.read_varint()
        if idx == 0:
            return None
        real = idx - 1
        return str_table_38[real] if 0 <= real < len(str_table_38) else f"__str_{idx}"

    def read_ref() -> Optional[str]:
        if is_v4:
            return r.read_string()
        return read_str_idx_38()

    skel = SpineSkeleton(name=hash_str or "skeleton", width=_width, height=_height)

    # ── Bones
    n_bones = r.read_varint()
    bone_names: list[str] = []
    for i in range(n_bones):
        bone_name = read_str() or f"bone_{i}"
        bone_names.append(bone_name)
        # Root bone (i==0) has no parent field
        if i > 0:
            p_raw = r.read_varint()
            parent_name = bone_names[p_raw] if 0 <= p_raw < len(bone_names) else None
        else:
            parent_name = None

        rotation = r.read_float()
        x = r.read_float()
        y = r.read_float()
        scale_x = r.read_float()
        scale_y = r.read_float()
        shear_x = r.read_float()
        shear_y = r.read_float()
        length = r.read_float()
        _transform_mode = r.read_varint()
        if is_v4 or is_38p:
            r.read_bool()  # skinRequired
        # non-essential mode includes bone color (RGBA)
        if non_essential:
            f.read(4)  # bone color

        skel.bones.append(Bone(
            name=bone_name, parent=parent_name,
            x=x, y=y, rotation=rotation,
            scale_x=scale_x, scale_y=scale_y,
            shear_x=shear_x, shear_y=shear_y,
            length=length,
            transform_mode=_transform_mode,
        ))

    # ── Slots
    try:
        n_slots = r.read_varint()
        slot_names: list[str] = []
        for i in range(n_slots):
            slot_name = read_str() or f"slot_{i}"
            slot_names.append(slot_name)
            bone_idx = r.read_varint()
            bone_name = bone_names[bone_idx] if bone_idx < len(bone_names) else "root"

            if is_38p and not is_v4:
                # 3.8: colors are raw 4-byte RGBA ints, attachment via string-table index
                f.read(4)  # main color (raw bytes)
                f.read(4)  # dark color (raw bytes, -1 = no dark)
                attach = read_str_idx_38()
            else:
                f.read(4)  # main color (raw bytes)
                f.read(4)  # dark color (raw bytes, -1 = no dark)
                attach = read_ref()

            _blend = r.read_varint()
            skel.slots.append(Slot(name=slot_name, bone=bone_name, attachment=attach))
    except Exception as e:
        import sys
        print(f"[spine binary] slot parse stopped at {i}/{n_slots}: {e}", file=sys.stderr)

    # ── Synthesize a "default" skin from slot attachment names.
    # Full skin binary parsing is complex; instead build a minimal skin so the
    # renderer can look up RegionAttachment data via the atlas at render time.
    parsed_default_skin: dict = {}
    parsed_skins: dict[str, dict] = {}
    event_audio_flags: list[bool] = []
    after_slots_pos = f.tell()
    if is_v4:
        try:
            parsed_skins = _parse_skins_and_constraints_v4(
                r, f, skel, bone_names, slot_names, non_essential, read_str, read_ref,
                has_sequence=(major, minor) >= (4, 1),
                event_audio_flags=event_audio_flags,
            )
            parsed_default_skin = parsed_skins.get("default", {})
        except Exception:
            parsed_skins = {}
            parsed_default_skin = {}
            event_audio_flags = []
            f.seek(after_slots_pos)
    elif is_38p:
        try:
            parsed_default_skin = _parse_skins_and_constraints_38(
                r, f, slot_names, non_essential, read_str_38, read_str_idx_38
            )
        except Exception:
            parsed_default_skin = {}
            f.seek(after_slots_pos)

    default_skin: dict = {}
    for slot in skel.slots:
        if slot.attachment:
            attach_name = slot.attachment
            default_skin[slot.name] = {
                attach_name: RegionAttachment(
                    name=attach_name,
                    path=attach_name,  # atlas region name == attachment name
                    width=100.0,
                    height=100.0,
                )
            }
    if default_skin:
        skel.skins["default"] = default_skin
    if parsed_default_skin:
        skel.skins["default"] = parsed_default_skin
    for skin_name, skin in parsed_skins.items():
        if skin_name != "default":
            skel.skins[skin_name] = skin
    if parsed_skins:
        resolve_linked_meshes(skel)

    # ── Skip IK / transforms / paths for animation (best-effort)
    try:
        if is_v4 and parsed_skins:
            _parse_binary_animations_v4(
                r, f, skel, bone_names, slot_names, read_str, read_ref,
                has_sequence=(major, minor) >= (4, 1),
                event_audio_flags=event_audio_flags,
            )
        elif is_38p and not is_v4 and parsed_default_skin:
            _parse_binary_animations_38(
                r, f, skel, bone_names, slot_names, read_str_38, read_str_idx_38
            )
        else:
            _skip_skins_and_constraints(r, f, n_bones, n_slots, is_v4)
            _parse_binary_animations(r, f, skel, bone_names, slot_names, is_v4)
    except Exception:
        pass  # partial parse; bones/slots/default skin are already loaded
    skel.store_bind_pose()
    skel.update_world_transforms()
    return skel


def _read_binary_header(f: BinaryIO) -> tuple[str, str]:
    """Read standard Spine header, with NIKKE raw-hash header fallback.

    Some NIKKE exports start with an 8-byte binary hash followed by the usual
    varint-prefixed version string. The standard parser expects a string hash
    first, so without this fallback the stream becomes misaligned immediately.
    """
    start = f.tell()
    head = f.read(32)
    f.seek(start)
    if len(head) >= 10:
        version_len = head[8]
        version_end = 8 + version_len
        if 1 < version_len <= 16 and version_end <= len(head):
            version_bytes = head[9:version_end]
            version_peek = version_bytes.decode("ascii", errors="ignore")
            if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version_peek or ""):
                raw_hash = f.read(8)
                version_str = _read_bstr(f)
                return raw_hash.hex(), version_str

    try:
        hash_str = _read_bstr(f)
        version_str = _read_bstr(f)
    except Exception:
        f.seek(start)
        raw_hash = f.read(8)
        version_str = _read_bstr(f)
        if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version_str or ""):
            return raw_hash.hex(), version_str
        raise
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version_str or ""):
        return hash_str, version_str

    f.seek(start)
    raw_hash = f.read(8)
    version_str = _read_bstr(f)
    if re.fullmatch(r"\d+\.\d+(?:\.\d+)?", version_str or ""):
        return raw_hash.hex(), version_str

    f.seek(start)
    return hash_str, version_str


def _read_bstr(f: BinaryIO) -> str:
    """Read a Spine binary string (full varint length, length-1 bytes of data).

    All Spine binary strings use varint-prefixed length encoding.
    Previously only read 1 byte — fails for strings >= 128 bytes (e.g. long Korean paths).
    """
    b = f.read(1)
    if not b:
        return ""
    length = b[0] & 0x7F
    shift = 7
    while b[0] & 0x80:
        b = f.read(1)
        if not b:
            break
        length |= (b[0] & 0x7F) << shift
        shift += 7
    if length == 0:
        return ""
    return f.read(length - 1).decode("utf-8", errors="replace")


def _read_bstr_raw(f: BinaryIO) -> str:
    """Read a varint-length-prefixed string from string table."""
    b = f.read(1)[0]
    length = b & 0x7F
    shift = 7
    while b & 0x80:
        b = f.read(1)[0]
        length |= (b & 0x7F) << shift
        shift += 7
    if length == 0:
        return ""
    return f.read(length - 1).decode("utf-8", errors="replace")


def _synthesize_default_skin(skel: SpineSkeleton) -> dict:
    """Build a minimal atlas-name skin when binary skin parsing is unavailable."""
    default_skin: dict = {}
    for slot in skel.slots:
        if slot.attachment:
            attach_name = slot.attachment
            default_skin[slot.name] = {
                attach_name: RegionAttachment(
                    name=attach_name,
                    path=attach_name,
                    width=100.0,
                    height=100.0,
                )
            }
    return default_skin


def _parse_skins_and_constraints_38(
    r: _BinaryReader,
    f: BinaryIO,
    slot_names: list[str],
    non_essential: bool,
    read_str,
    read_ref,
) -> dict:
    """Parse Spine 3.8 constraints/skins enough for static game exports.

    Blue Archive style exports keep most visible placement in mesh attachments.
    The old binary reader skipped this block, leaving only slot names.
    """
    _skip_constraints_38(r, f, non_essential, read_str)
    default_skin = _read_skin_38(
        r, f, slot_names, non_essential, read_ref, default_skin=True
    )

    n_skins = r.read_varint(optimise_positive=True)
    for _ in range(n_skins):
        _read_skin_38(r, f, slot_names, non_essential, read_ref, default_skin=False, read_str=read_str)

    _skip_events_38(r, f, read_str)
    return default_skin


def _parse_skins_and_constraints_v4(
    r: _BinaryReader,
    f: BinaryIO,
    skel: SpineSkeleton,
    bone_names: list[str],
    slot_names: list[str],
    non_essential: bool,
    read_str,
    read_ref,
    has_sequence: bool,
    event_audio_flags: list[bool] | None = None,
) -> dict[str, dict]:
    _skip_constraints_v4(r, f, read_str, skel, bone_names)

    skins: dict[str, dict] = {}
    default_skin = _read_skin_v4(
        r, f, slot_names, non_essential, read_ref, default_skin=True,
        has_sequence=has_sequence,
    )
    if default_skin:
        skins["default"] = default_skin

    n_skins = r.read_varint(optimise_positive=True)
    for _ in range(n_skins):
        skin_name, skin = _read_skin_v4(
            r, f, slot_names, non_essential, read_ref, default_skin=False,
            has_sequence=has_sequence,
        )
        if skin:
            skins[skin_name] = skin

    _skip_events_v4(r, f, read_str, read_ref, event_audio_flags)
    return skins


def _skip_constraints_v4(
    r: _BinaryReader,
    f: BinaryIO,
    read_str,
    skel: SpineSkeleton | None = None,
    bone_names: list[str] | None = None,
) -> None:
    n = r.read_varint(optimise_positive=True)
    for _ in range(n):
        name = read_str() or f"ik_{_}"
        order = r.read_varint(optimise_positive=True)
        r.read_bool()  # skinRequired
        bones: list[str] = []
        for __ in range(r.read_varint(optimise_positive=True)):
            bone_idx = r.read_varint(optimise_positive=True)
            if bone_names and 0 <= bone_idx < len(bone_names):
                bones.append(bone_names[bone_idx])
        target_idx = r.read_varint(optimise_positive=True)
        target = (
            bone_names[target_idx]
            if bone_names and 0 <= target_idx < len(bone_names)
            else ""
        )
        mix = r.read_float()
        r.read_float()  # softness
        _bend_direction = r.read_byte()
        compress = r.read_bool()
        stretch = r.read_bool()
        uniform = r.read_bool()
        if skel is not None:
            skel.ik_constraints.append(IKConstraint(
                name=name,
                bones=bones,
                target=target,
                order=order,
                mix=mix,
                compress=compress,
                stretch=stretch,
                uniform=uniform,
            ))

    n = r.read_varint(optimise_positive=True)
    for _ in range(n):
        read_str()
        r.read_varint(optimise_positive=True)  # order
        r.read_bool()  # skinRequired
        for __ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
        r.read_varint(optimise_positive=True)  # target
        r.read_bool()  # local
        r.read_bool()  # relative
        f.read(4 * 12)

    n = r.read_varint(optimise_positive=True)
    for _ in range(n):
        read_str()
        r.read_varint(optimise_positive=True)  # order
        r.read_bool()  # skinRequired
        for __ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
        r.read_varint(optimise_positive=True)  # target slot
        r.read_varint(optimise_positive=True)  # position mode
        r.read_varint(optimise_positive=True)  # spacing mode
        r.read_varint(optimise_positive=True)  # rotate mode
        f.read(4 * 6)


def _read_skin_v4(
    r: _BinaryReader,
    f: BinaryIO,
    slot_names: list[str],
    non_essential: bool,
    read_ref,
    default_skin: bool,
    has_sequence: bool,
) -> tuple[str, dict] | dict:
    if default_skin:
        skin_name = "default"
        slot_count = r.read_varint(optimise_positive=True)
        if slot_count == 0:
            return {}
    else:
        skin_name = read_ref() or "skin"
        for _ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
        for _ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
        for _ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
        for _ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
        slot_count = r.read_varint(optimise_positive=True)

    skin: dict = {}
    for _ in range(slot_count):
        slot_idx = r.read_varint(optimise_positive=True)
        slot_name = slot_names[slot_idx] if 0 <= slot_idx < len(slot_names) else f"slot_{slot_idx}"
        n_attach = r.read_varint(optimise_positive=True)
        slot_skin = skin.setdefault(slot_name, {})
        for attach_i in range(n_attach):
            attach_name = read_ref() or f"attachment_{attach_i}"
            attach = _read_attachment_v4(
                r, f, attach_name, non_essential, read_ref, has_sequence
            )
            if attach is not None:
                slot_skin[attach_name] = attach

    if default_skin:
        return skin
    return skin_name, skin


def _read_sequence_v4(r: _BinaryReader) -> None:
    if not r.read_bool():
        return
    r.read_varint(optimise_positive=True)  # count
    r.read_varint(optimise_positive=True)  # start
    r.read_varint(optimise_positive=True)  # digits
    r.read_varint(optimise_positive=True)  # setup index


def _read_attachment_v4(
    r: _BinaryReader,
    f: BinaryIO,
    attachment_name: str,
    non_essential: bool,
    read_ref,
    has_sequence: bool,
) -> RegionAttachment | None:
    actual_name = read_ref() or attachment_name
    atype = r.read_byte()

    if atype == 0:  # region
        path = read_ref() or actual_name
        rotation = r.read_float()
        x = r.read_float()
        y = r.read_float()
        scale_x = r.read_float()
        scale_y = r.read_float()
        width = r.read_float()
        height = r.read_float()
        f.read(4)
        if has_sequence:
            _read_sequence_v4(r)
        return RegionAttachment(
            name=attachment_name,
            path=path,
            x=x,
            y=y,
            rotation=rotation,
            scale_x=scale_x,
            scale_y=scale_y,
            width=width,
            height=height,
        )

    if atype == 1:  # bounding box
        vertex_count = r.read_varint(optimise_positive=True)
        _read_vertices_38(r, vertex_count)
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    if atype == 2:  # mesh
        path = read_ref() or actual_name
        f.read(4)
        vertex_count = r.read_varint(optimise_positive=True)
        uvs = [r.read_float() for _ in range(vertex_count * 2)]
        triangles = _read_short_array_38(r)
        mesh_weights = _read_vertices_38(r, vertex_count)
        r.read_varint(optimise_positive=True)  # hull length
        if has_sequence:
            _read_sequence_v4(r)
        if non_essential:
            _read_short_array_38(r)
            width = r.read_float()
            height = r.read_float()
        else:
            width = height = 100.0
        return RegionAttachment(
            name=attachment_name,
            path=path,
            width=width,
            height=height,
            mesh_weights=mesh_weights,
            mesh_uvs=uvs,
            mesh_triangles=triangles,
        )

    if atype == 3:  # linked mesh
        path = read_ref() or actual_name
        f.read(4)
        skin = read_ref() or "default"
        parent = read_ref() or attachment_name
        inherit_timeline = r.read_bool()
        if has_sequence:
            _read_sequence_v4(r)
        if non_essential:
            width = r.read_float()
            height = r.read_float()
        else:
            width = height = 100.0
        attach = RegionAttachment(name=attachment_name, path=path, width=width, height=height)
        attach._linked_skin = skin
        attach._linked_parent = parent
        attach._inherit_timeline = inherit_timeline
        return attach

    if atype == 4:  # path
        r.read_bool()
        r.read_bool()
        vertex_count = r.read_varint(optimise_positive=True)
        _read_vertices_38(r, vertex_count)
        for _ in range(max(0, vertex_count // 3)):
            r.read_float()
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    if atype == 5:  # point
        r.read_float()
        r.read_float()
        r.read_float()
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    if atype == 6:  # clipping
        r.read_varint(optimise_positive=True)
        vertex_count = r.read_varint(optimise_positive=True)
        _read_vertices_38(r, vertex_count)
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    return None


def _skip_events_v4(
    r: _BinaryReader,
    f: BinaryIO,
    read_str,
    read_ref,
    event_audio_flags: list[bool] | None = None,
) -> None:
    n = r.read_varint(optimise_positive=True)
    for _ in range(n):
        read_ref()
        r.read_varint(optimise_positive=False)
        r.read_float()
        read_str()
        audio = read_str()
        if event_audio_flags is not None:
            event_audio_flags.append(bool(audio))
        if audio:
            r.read_float()
            r.read_float()


def _skip_constraints_38(r: _BinaryReader, f: BinaryIO, non_essential: bool, read_str) -> None:
    n = r.read_varint()
    for _ in range(n):
        read_str()
        r.read_varint()
        r.read_bool()
        for __ in range(r.read_varint()):
            r.read_varint()
        r.read_varint()
        r.read_float()
        r.read_float()
        r.read_byte()
        r.read_bool()
        r.read_bool()
        r.read_bool()

    n = r.read_varint()
    for _ in range(n):
        read_str()
        r.read_varint()
        r.read_bool()
        for __ in range(r.read_varint()):
            r.read_varint()
        r.read_varint()
        r.read_bool()
        r.read_bool()
        # Spine 3.8 transform constraints store offsets and mix values here.
        for __ in range(12):
            r.read_float()

    n = r.read_varint()
    for _ in range(n):
        read_str()
        r.read_varint()
        r.read_bool()
        for __ in range(r.read_varint()):
            r.read_varint()
        r.read_varint()
        r.read_varint()
        r.read_varint()
        r.read_varint()
        for __ in range(5):
            r.read_float()


def _read_skin_38(
    r: _BinaryReader,
    f: BinaryIO,
    slot_names: list[str],
    non_essential: bool,
    read_ref,
    default_skin: bool,
    read_str=None,
) -> dict:
    if not default_skin and read_str is not None:
        read_str()

    skin: dict = {}
    n_slots = r.read_varint(optimise_positive=True)
    for _ in range(n_slots):
        slot_idx = r.read_varint(optimise_positive=True)
        slot_name = slot_names[slot_idx] if 0 <= slot_idx < len(slot_names) else f"slot_{slot_idx}"
        n_attach = r.read_varint(optimise_positive=True)
        slot_skin = skin.setdefault(slot_name, {})
        for attach_i in range(n_attach):
            attach_name = read_ref() or f"attachment_{attach_i}"
            attach = _read_attachment_38(r, f, attach_name, non_essential, read_ref)
            if attach is not None:
                slot_skin[attach_name] = attach
    return skin


def _read_attachment_38(
    r: _BinaryReader,
    f: BinaryIO,
    attachment_name: str,
    non_essential: bool,
    read_ref,
) -> RegionAttachment | None:
    actual_name = read_ref() or attachment_name
    atype = r.read_byte()

    if atype == 0:  # region
        path = read_ref() or actual_name
        rotation = r.read_float()
        x = r.read_float()
        y = r.read_float()
        scale_x = r.read_float()
        scale_y = r.read_float()
        width = r.read_float()
        height = r.read_float()
        f.read(4)
        return RegionAttachment(
            name=attachment_name,
            path=path,
            x=x,
            y=y,
            rotation=rotation,
            scale_x=scale_x,
            scale_y=scale_y,
            width=width,
            height=height,
        )

    if atype == 1:  # bounding box
        vertex_count = r.read_varint(optimise_positive=True)
        _read_vertices_38(r, vertex_count)
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    if atype == 2:  # mesh
        path = read_ref() or actual_name
        f.read(4)
        vertex_count = r.read_varint(optimise_positive=True)
        uvs = [r.read_float() for _ in range(vertex_count * 2)]
        triangles = _read_short_array_38(r)
        mesh_weights = _read_vertices_38(r, vertex_count)
        r.read_varint(optimise_positive=True)  # hull length
        if non_essential:
            _read_short_array_38(r)  # edges
            width = r.read_float()
            height = r.read_float()
        else:
            width = 100.0
            height = 100.0
        return RegionAttachment(
            name=attachment_name,
            path=path,
            width=width,
            height=height,
            mesh_weights=mesh_weights,
            mesh_uvs=uvs,
            mesh_triangles=triangles,
        )

    if atype == 3:  # linked mesh
        path = read_ref() or actual_name
        f.read(4)
        skin = read_ref() or "default"
        parent = read_ref() or attachment_name
        r.read_bool()
        if non_essential:
            width = r.read_float()
            height = r.read_float()
        else:
            width = height = 100.0
        attach = RegionAttachment(name=attachment_name, path=path, width=width, height=height)
        attach._linked_skin = skin
        attach._linked_parent = parent
        return attach

    if atype == 4:  # path
        r.read_bool()
        r.read_bool()
        vertex_count = r.read_varint(optimise_positive=True)
        _read_vertices_38(r, vertex_count)
        for _ in range(max(0, vertex_count // 3)):
            r.read_float()
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    if atype == 5:  # point
        r.read_float()
        r.read_float()
        r.read_float()
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    if atype == 6:  # clipping
        r.read_varint(optimise_positive=True)
        vertex_count = r.read_varint(optimise_positive=True)
        _read_vertices_38(r, vertex_count)
        if non_essential:
            f.read(4)
        attach = RegionAttachment(name=attachment_name, path=actual_name)
        attach._non_visual = True
        return attach

    return None


def _read_vertices_38(r: _BinaryReader, vertex_count: int) -> list:
    weighted = r.read_bool()
    if not weighted:
        values = [r.read_float() for _ in range(vertex_count * 2)]
        return [[(-1, values[i], values[i + 1], 1.0)] for i in range(0, len(values), 2)]

    result = []
    for _ in range(vertex_count):
        count = r.read_varint(optimise_positive=True)
        influences = []
        for __ in range(count):
            bone_idx = r.read_varint(optimise_positive=True)
            lx = r.read_float()
            ly = r.read_float()
            weight = r.read_float()
            influences.append((bone_idx, lx, ly, weight))
        result.append(influences)
    return result


def _read_short_array_38(r: _BinaryReader) -> list[int]:
    n = r.read_varint(optimise_positive=True)
    return [r.read_short() for _ in range(n)]


def _skip_events_38(r: _BinaryReader, f: BinaryIO, read_str) -> None:
    n = r.read_varint()
    for _ in range(n):
        read_str()
        r.read_varint()
        r.read_float()
        read_str()


def _skip_skins_and_constraints(r: _BinaryReader, f: BinaryIO,
                                 n_bones: int, n_slots: int, is_v4: bool) -> None:
    """Skip IK, transform, path constraints and skins."""
    # IK constraints
    n = r.read_varint()
    for _ in range(n):
        r.read_string()  # name
        r.read_varint()  # order
        if is_v4:
            r.read_bool()  # skin-required
        n_bones_ik = r.read_varint()
        for __ in range(n_bones_ik):
            r.read_varint()  # bone index
        r.read_varint()  # target bone
        r.read_varint()  # mix
        f.read(4)  # softness
        r.read_byte()  # bend positive
        r.read_bool()  # compress
        r.read_bool()  # stretch
        r.read_bool()  # uniform

    # Transform constraints
    n = r.read_varint()
    for _ in range(n):
        r.read_string()
        r.read_varint()
        if is_v4:
            r.read_bool()
        n_bt = r.read_varint()
        for __ in range(n_bt):
            r.read_varint()
        r.read_varint()
        r.read_bool()
        f.read(4 * 10)  # various floats

    # Path constraints
    n = r.read_varint()
    for _ in range(n):
        r.read_string()
        r.read_varint()
        if is_v4:
            r.read_bool()
        n_bt = r.read_varint()
        for __ in range(n_bt):
            r.read_varint()
        r.read_varint()
        r.read_varint()
        r.read_varint()
        r.read_varint()
        f.read(4 * 3)  # floats

    # Default skin
    _skip_skin(r, f, is_v4)

    # Non-default skins
    n = r.read_varint()
    for _ in range(n):
        _skip_skin(r, f, is_v4)

    # Events
    n = r.read_varint()
    for _ in range(n):
        r.read_string()
        r.read_varint()
        f.read(4)
        r.read_float()
        r.read_string()
        if is_v4:
            r.read_string()
            r.read_bool()


def _skip_skin(r: _BinaryReader, f: BinaryIO, is_v4: bool) -> None:
    if is_v4:
        r.read_string()  # name
        n_bones = r.read_varint()
        for _ in range(n_bones):
            r.read_varint()
        n_ik = r.read_varint()
        for _ in range(n_ik):
            r.read_varint()
        n_tr = r.read_varint()
        for _ in range(n_tr):
            r.read_varint()
        n_pt = r.read_varint()
        for _ in range(n_pt):
            r.read_varint()
    n_slots = r.read_varint()
    for _ in range(n_slots):
        r.read_varint()  # slot index
        n_attach = r.read_varint()
        for __ in range(n_attach):
            r.read_string()  # name
            r.read_string()  # attachment key
            _skip_attachment(r, f, is_v4)


def _skip_attachment(r: _BinaryReader, f: BinaryIO, is_v4: bool) -> None:
    atype = r.read_byte()
    if atype == 0:  # region
        r.read_string()
        r.read_string()
        if is_v4:
            r.read_varint()
        f.read(4)  # color
        f.read(4 * 5)  # x,y,scaleX,scaleY,rotation
        f.read(4 * 2)  # width,height
    elif atype == 1:  # bounding box
        r.read_string()
        n = r.read_varint() * 2
        f.read(4 * n)
        if is_v4:
            f.read(4)
    elif atype == 2:  # mesh
        r.read_string()
        if is_v4:
            r.read_varint()
        f.read(4)  # color
        n_uv = r.read_varint()
        f.read(4 * n_uv * 2)  # uvs
        n_tri = r.read_varint()
        f.read(2 * n_tri)  # triangles
        n_v = r.read_varint()
        f.read(4 * n_v * 2)  # vertices
        f.read(4 * 2)  # hull, edges (int)
        f.read(4 * 2)  # width, height
    # Other types: skip (this is a best-effort parser)


def _read_curve_38(r: _BinaryReader, f: BinaryIO) -> str:
    curve = r.read_byte()
    if curve == 1:
        return "stepped"
    if curve == 2:
        f.read(4 * 4)
    return "linear"


def _find_attachment(skel: SpineSkeleton, slot_name: str, attachment_name: str) -> RegionAttachment | None:
    for skin in skel.skins.values():
        attach = skin.get(slot_name, {}).get(attachment_name)
        if isinstance(attach, RegionAttachment):
            return attach
    return None


def _flatten_unweighted_vertices(attach: RegionAttachment | None) -> list[float]:
    if not attach:
        return []
    flat: list[float] = []
    for vtx_bones in getattr(attach, "mesh_weights", []) or []:
        if len(vtx_bones) != 1:
            return []
        bone_idx, lx, ly, weight = vtx_bones[0]
        if bone_idx >= 0 or abs(weight - 1.0) > 1e-5:
            return []
        flat.extend([float(lx), float(ly)])
    return flat


def _read_curve_v4(r: _BinaryReader, f: BinaryIO, value_count: int = 1) -> str:
    curve = r.read_byte()
    if curve == 1:
        return "stepped"
    if curve == 2:
        f.read(4 * 4 * max(1, value_count))
        return "bezier"
    return "linear"


def _read_timeline1_v4(
    r: _BinaryReader,
    f: BinaryIO,
    frame_count: int,
    scale: float = 1.0,
) -> list[BoneKeyframe]:
    if frame_count <= 0:
        return []
    time = r.read_float()
    value = r.read_float() * scale
    keyframes: list[BoneKeyframe] = []
    for frame_idx in range(frame_count):
        if frame_idx == frame_count - 1:
            keyframes.append(BoneKeyframe(time=time, value=value))
            break
        next_time = r.read_float()
        next_value = r.read_float() * scale
        curve = _read_curve_v4(r, f, 1)
        keyframes.append(BoneKeyframe(time=time, value=value, curve=curve))
        time = next_time
        value = next_value
    return keyframes


def _read_timeline2_v4(
    r: _BinaryReader,
    f: BinaryIO,
    frame_count: int,
    scale: float = 1.0,
) -> tuple[list[BoneKeyframe], list[BoneKeyframe]]:
    if frame_count <= 0:
        return [], []
    time = r.read_float()
    value1 = r.read_float() * scale
    value2 = r.read_float() * scale
    keyframes1: list[BoneKeyframe] = []
    keyframes2: list[BoneKeyframe] = []
    for frame_idx in range(frame_count):
        if frame_idx == frame_count - 1:
            keyframes1.append(BoneKeyframe(time=time, value=value1))
            keyframes2.append(BoneKeyframe(time=time, value=value2))
            break
        next_time = r.read_float()
        next_value1 = r.read_float() * scale
        next_value2 = r.read_float() * scale
        curve = _read_curve_v4(r, f, 2)
        keyframes1.append(BoneKeyframe(time=time, value=value1, curve=curve))
        keyframes2.append(BoneKeyframe(time=time, value=value2, curve=curve))
        time = next_time
        value1 = next_value1
        value2 = next_value2
    return keyframes1, keyframes2


def _skip_float_timeline_v4(
    r: _BinaryReader,
    f: BinaryIO,
    frame_count: int,
    value_count: int,
) -> float:
    if frame_count <= 0:
        return 0.0
    time = r.read_float()
    f.read(4 * value_count)
    duration = time
    for frame_idx in range(frame_count):
        if frame_idx == frame_count - 1:
            break
        time = r.read_float()
        f.read(4 * value_count)
        _read_curve_v4(r, f, value_count)
        duration = max(duration, time)
    return duration


def _skip_byte_timeline_v4(
    r: _BinaryReader,
    f: BinaryIO,
    frame_count: int,
    byte_count: int,
) -> float:
    if frame_count <= 0:
        return 0.0
    time = r.read_float()
    f.read(byte_count)
    duration = time
    for frame_idx in range(frame_count):
        if frame_idx == frame_count - 1:
            break
        time = r.read_float()
        f.read(byte_count)
        _read_curve_v4(r, f, byte_count)
        duration = max(duration, time)
    return duration


def _deform_shape_for_attachment(
    attach: RegionAttachment | None,
) -> tuple[bool, list[float], int]:
    weights = getattr(attach, "mesh_weights", []) if attach is not None else []
    weighted = any(
        bone_idx >= 0
        for vtx_bones in weights or []
        for bone_idx, _lx, _ly, _weight in vtx_bones
    )
    if weighted:
        influence_count = sum(len(vtx_bones) for vtx_bones in weights or [])
        return True, [], influence_count * 2
    base_vertices = _flatten_unweighted_vertices(attach)
    if base_vertices:
        return False, base_vertices, len(base_vertices)
    if weights:
        return False, [], len(weights) * 2
    return False, [], 0


def _find_skin_attachment(
    skel: SpineSkeleton,
    skin_idx: int,
    slot_name: str,
    attachment_name: str,
) -> RegionAttachment | None:
    skin_items = list(skel.skins.values())
    if 0 <= skin_idx < len(skin_items):
        attach = skin_items[skin_idx].get(slot_name, {}).get(attachment_name)
        if isinstance(attach, RegionAttachment):
            return attach
    return _find_attachment(skel, slot_name, attachment_name)


def _read_deform_timeline_v4(
    r: _BinaryReader,
    f: BinaryIO,
    frame_count: int,
    slot_name: str,
    attachment_name: str,
    attach: RegionAttachment | None,
) -> DeformTimeline:
    _bezier_count = r.read_varint(optimise_positive=True)
    weighted, base_vertices, deform_len = _deform_shape_for_attachment(attach)
    tl = DeformTimeline(slot=slot_name, attachment=attachment_name)
    if frame_count <= 0:
        return tl

    time = r.read_float()
    for frame_idx in range(frame_count):
        end_count = r.read_varint(optimise_positive=True)
        if end_count == 0:
            deform = [0.0] * deform_len if weighted else list(base_vertices)
        else:
            start = r.read_varint(optimise_positive=True)
            length = max(deform_len, start + end_count)
            deform = [0.0] * length
            for i in range(end_count):
                deform[start + i] = r.read_float()
            if not weighted and base_vertices:
                if len(deform) < len(base_vertices):
                    deform.extend([0.0] * (len(base_vertices) - len(deform)))
                for i, base in enumerate(base_vertices):
                    deform[i] += base

        if frame_idx == frame_count - 1:
            tl.keyframes.append(DeformKeyframe(time=time, vertices=deform))
            break
        next_time = r.read_float()
        curve = _read_curve_v4(r, f, 1)
        tl.keyframes.append(DeformKeyframe(time=time, vertices=deform, curve=curve))
        time = next_time
    return tl


def _skip_sequence_timeline_v4(r: _BinaryReader, frame_count: int) -> float:
    duration = 0.0
    for _ in range(frame_count):
        time = r.read_float()
        r.read_int()
        r.read_float()
        duration = max(duration, time)
    return duration


def _parse_binary_animations_v4(
    r: _BinaryReader,
    f: BinaryIO,
    skel: SpineSkeleton,
    bone_names: list[str],
    slot_names: list[str],
    read_str,
    read_ref,
    has_sequence: bool,
    event_audio_flags: list[bool] | None = None,
) -> None:
    n_anims = r.read_varint(optimise_positive=True)
    for anim_i in range(n_anims):
        anim_name = read_str() or f"animation_{anim_i}"
        anim = Animation(name=anim_name)
        duration = 0.0

        r.read_varint(optimise_positive=True)  # total timeline count

        for _ in range(r.read_varint(optimise_positive=True)):
            slot_idx = r.read_varint(optimise_positive=True)
            slot_name = slot_names[slot_idx] if 0 <= slot_idx < len(slot_names) else f"slot_{slot_idx}"
            for __ in range(r.read_varint(optimise_positive=True)):
                tl_type = r.read_byte()
                frame_count = r.read_varint(optimise_positive=True)
                if tl_type == 0:
                    tl = SlotAttachmentTimeline(slot=slot_name)
                    for ___ in range(frame_count):
                        time = r.read_float()
                        attachment = read_ref()
                        tl.keyframes.append(SlotAttachmentKeyframe(time=time, attachment=attachment))
                        duration = max(duration, time)
                    if tl.keyframes:
                        anim.timelines.append(tl)
                else:
                    components = {1: 4, 2: 3, 3: 7, 4: 6, 5: 1}.get(tl_type, 4)
                    r.read_varint(optimise_positive=True)  # bezier count
                    duration = max(duration, _skip_byte_timeline_v4(r, f, frame_count, components))

        for _ in range(r.read_varint(optimise_positive=True)):
            bone_idx = r.read_varint(optimise_positive=True)
            bone_name = bone_names[bone_idx] if 0 <= bone_idx < len(bone_names) else f"bone_{bone_idx}"
            for __ in range(r.read_varint(optimise_positive=True)):
                tl_type = r.read_byte()
                frame_count = r.read_varint(optimise_positive=True)
                r.read_varint(optimise_positive=True)  # bezier count

                if tl_type == 0:
                    tl = BoneTimeline(bone=bone_name, property="rotate")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)
                elif tl_type == 1:
                    kx, ky = _read_timeline2_v4(r, f, frame_count)
                    anim.timelines.append(BoneTimeline(bone=bone_name, property="translateX", keyframes=kx))
                    anim.timelines.append(BoneTimeline(bone=bone_name, property="translateY", keyframes=ky))
                elif tl_type == 2:
                    tl = BoneTimeline(bone=bone_name, property="translateX")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)
                elif tl_type == 3:
                    tl = BoneTimeline(bone=bone_name, property="translateY")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)
                elif tl_type == 4:
                    kx, ky = _read_timeline2_v4(r, f, frame_count)
                    anim.timelines.append(BoneTimeline(bone=bone_name, property="scaleX", keyframes=kx))
                    anim.timelines.append(BoneTimeline(bone=bone_name, property="scaleY", keyframes=ky))
                elif tl_type == 5:
                    tl = BoneTimeline(bone=bone_name, property="scaleX")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)
                elif tl_type == 6:
                    tl = BoneTimeline(bone=bone_name, property="scaleY")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)
                elif tl_type == 7:
                    kx, ky = _read_timeline2_v4(r, f, frame_count)
                    anim.timelines.append(BoneTimeline(bone=bone_name, property="shearX", keyframes=kx))
                    anim.timelines.append(BoneTimeline(bone=bone_name, property="shearY", keyframes=ky))
                elif tl_type == 8:
                    tl = BoneTimeline(bone=bone_name, property="shearX")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)
                elif tl_type == 9:
                    tl = BoneTimeline(bone=bone_name, property="shearY")
                    tl.keyframes = _read_timeline1_v4(r, f, frame_count)
                    anim.timelines.append(tl)

        for _ in range(r.read_varint(optimise_positive=True)):
            ik_idx = r.read_varint(optimise_positive=True)
            frame_count = r.read_varint(optimise_positive=True)
            r.read_varint(optimise_positive=True)  # bezier count
            ik_name = (
                skel.ik_constraints[ik_idx].name
                if 0 <= ik_idx < len(skel.ik_constraints)
                else f"ik_{ik_idx}"
            )
            tl = IKTimeline(name=ik_name)
            if frame_count > 0:
                time = r.read_float()
                mix = r.read_float()
                r.read_float()  # softness
                for frame_idx in range(frame_count):
                    r.read_byte()  # bendDirection
                    r.read_bool()  # compress
                    r.read_bool()  # stretch
                    if frame_idx == frame_count - 1:
                        tl.keyframes.append(IKKeyframe(time=time, mix=mix))
                        break
                    next_time = r.read_float()
                    next_mix = r.read_float()
                    r.read_float()  # next softness
                    curve = _read_curve_v4(r, f, 2)
                    tl.keyframes.append(IKKeyframe(time=time, mix=mix, curve=curve))
                    time = next_time
                    mix = next_mix
            if tl.keyframes:
                duration = max(duration, tl.keyframes[-1].time)
                anim.timelines.append(tl)

        for _ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)  # transform constraint index
            frame_count = r.read_varint(optimise_positive=True)
            r.read_varint(optimise_positive=True)  # bezier count
            duration = max(duration, _skip_float_timeline_v4(r, f, frame_count, 6))

        for _ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)  # path constraint index
            for __ in range(r.read_varint(optimise_positive=True)):
                tl_type = r.read_byte()
                frame_count = r.read_varint(optimise_positive=True)
                r.read_varint(optimise_positive=True)  # bezier count
                value_count = 3 if tl_type == 2 else 1
                duration = max(duration, _skip_float_timeline_v4(r, f, frame_count, value_count))

        for _ in range(r.read_varint(optimise_positive=True)):
            skin_idx = r.read_varint(optimise_positive=True)
            for __ in range(r.read_varint(optimise_positive=True)):
                slot_idx = r.read_varint(optimise_positive=True)
                slot_name = slot_names[slot_idx] if 0 <= slot_idx < len(slot_names) else f"slot_{slot_idx}"
                for ___ in range(r.read_varint(optimise_positive=True)):
                    attachment_name = read_ref() or ""
                    attach = _find_skin_attachment(skel, skin_idx, slot_name, attachment_name)
                    if has_sequence:
                        timeline_type = r.read_byte()
                        frame_count = r.read_varint(optimise_positive=True)
                        if timeline_type == 0:
                            tl = _read_deform_timeline_v4(
                                r, f, frame_count, slot_name, attachment_name, attach
                            )
                            if tl.keyframes:
                                duration = max(duration, tl.keyframes[-1].time)
                                anim.timelines.append(tl)
                        elif timeline_type == 1:
                            duration = max(duration, _skip_sequence_timeline_v4(r, frame_count))
                    else:
                        frame_count = r.read_varint(optimise_positive=True)
                        tl = _read_deform_timeline_v4(
                            r, f, frame_count, slot_name, attachment_name, attach
                        )
                        if tl.keyframes:
                            duration = max(duration, tl.keyframes[-1].time)
                            anim.timelines.append(tl)

        for _ in range(r.read_varint(optimise_positive=True)):
            time = r.read_float()
            offset_count = r.read_varint(optimise_positive=True)
            for __ in range(offset_count):
                r.read_varint(optimise_positive=True)
                r.read_varint(optimise_positive=True)
            duration = max(duration, time)

        for _ in range(r.read_varint(optimise_positive=True)):
            time = r.read_float()
            event_idx = r.read_varint(optimise_positive=True)
            r.read_varint(optimise_positive=False)
            r.read_float()
            if r.read_bool():
                read_str()
            if event_audio_flags and 0 <= event_idx < len(event_audio_flags):
                if event_audio_flags[event_idx]:
                    r.read_float()
                    r.read_float()
            duration = max(duration, time)

        for tl in anim.timelines:
            keyframes = getattr(tl, "keyframes", None)
            if keyframes:
                duration = max(duration, keyframes[-1].time)
        anim.duration = max(duration, 1e-6)
        skel.animations[anim_name] = anim


def _parse_binary_animations_38(
    r: _BinaryReader,
    f: BinaryIO,
    skel: SpineSkeleton,
    bone_names: list[str],
    slot_names: list[str],
    read_str,
    read_ref,
) -> None:
    n_anims = r.read_varint(optimise_positive=True)
    for _ in range(n_anims):
        anim_name = read_str() or "animation"
        anim = Animation(name=anim_name)
        duration = 0.0

        # Slot timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            slot_idx = r.read_varint(optimise_positive=True)
            slot_name = slot_names[slot_idx] if 0 <= slot_idx < len(slot_names) else f"slot_{slot_idx}"
            for ___ in range(r.read_varint(optimise_positive=True)):
                tl_type = r.read_byte()
                frame_count = r.read_varint(optimise_positive=True)
                if tl_type == 0:
                    tl = SlotAttachmentTimeline(slot=slot_name)
                    for _frame_idx in range(frame_count):
                        time = r.read_float()
                        attachment = read_ref()
                        tl.keyframes.append(
                            SlotAttachmentKeyframe(time=time, attachment=attachment)
                        )
                        duration = max(duration, time)
                    anim.timelines.append(tl)
                else:
                    tl = BoneTimeline(bone=f"__slot_{slot_name}", property="color")
                    for frame_idx in range(frame_count):
                        time = r.read_float()
                        if tl_type == 1:
                            f.read(4)
                        elif tl_type == 2:
                            f.read(8)
                        if frame_idx < frame_count - 1:
                            _read_curve_38(r, f)
                        duration = max(duration, time)
                    anim.timelines.append(tl)

        # Bone timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            bone_idx = r.read_varint(optimise_positive=True)
            bone_name = bone_names[bone_idx] if 0 <= bone_idx < len(bone_names) else f"bone_{bone_idx}"
            for ___ in range(r.read_varint(optimise_positive=True)):
                tl_type = r.read_byte()
                frame_count = r.read_varint(optimise_positive=True)
                if tl_type == 0:
                    tl = BoneTimeline(bone=bone_name, property="rotate")
                    for frame_idx in range(frame_count):
                        time = r.read_float()
                        value = r.read_float()
                        curve = _read_curve_38(r, f) if frame_idx < frame_count - 1 else "linear"
                        tl.keyframes.append(BoneKeyframe(time=time, value=value, curve=curve))
                        duration = max(duration, time)
                    anim.timelines.append(tl)
                elif tl_type in (1, 2, 3):
                    prop_x, prop_y = {
                        1: ("translateX", "translateY"),
                        2: ("scaleX", "scaleY"),
                        3: ("shearX", "shearY"),
                    }[tl_type]
                    tl_x = BoneTimeline(bone=bone_name, property=prop_x)
                    tl_y = BoneTimeline(bone=bone_name, property=prop_y)
                    for frame_idx in range(frame_count):
                        time = r.read_float()
                        x = r.read_float()
                        y = r.read_float()
                        curve = _read_curve_38(r, f) if frame_idx < frame_count - 1 else "linear"
                        tl_x.keyframes.append(BoneKeyframe(time=time, value=x, curve=curve))
                        tl_y.keyframes.append(BoneKeyframe(time=time, value=y, curve=curve))
                        duration = max(duration, time)
                    anim.timelines.extend([tl_x, tl_y])

        # IK timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
            frame_count = r.read_varint(optimise_positive=True)
            for frame_idx in range(frame_count):
                time = r.read_float()
                r.read_float()
                r.read_float()
                r.read_byte()
                r.read_bool()
                r.read_bool()
                if frame_idx < frame_count - 1:
                    _read_curve_38(r, f)
                duration = max(duration, time)

        # Transform constraint timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
            frame_count = r.read_varint(optimise_positive=True)
            for frame_idx in range(frame_count):
                time = r.read_float()
                f.read(4 * 5)
                if frame_idx < frame_count - 1:
                    _read_curve_38(r, f)
                duration = max(duration, time)

        # Path constraint timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)
            for ___ in range(r.read_varint(optimise_positive=True)):
                tl_type = r.read_byte()
                frame_count = r.read_varint(optimise_positive=True)
                value_count = 2 if tl_type == 2 else 1
                for frame_idx in range(frame_count):
                    time = r.read_float()
                    f.read(4 * value_count)
                    if frame_idx < frame_count - 1:
                        _read_curve_38(r, f)
                    duration = max(duration, time)

        # Deform timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            r.read_varint(optimise_positive=True)  # skin index; names are enough for our skin map.
            for ___ in range(r.read_varint(optimise_positive=True)):
                slot_idx = r.read_varint(optimise_positive=True)
                slot_name = slot_names[slot_idx] if 0 <= slot_idx < len(slot_names) else f"slot_{slot_idx}"
                for ____ in range(r.read_varint(optimise_positive=True)):
                    attachment_name = read_ref() or ""
                    attach = _find_attachment(skel, slot_name, attachment_name)
                    base_vertices = _flatten_unweighted_vertices(attach)
                    frame_count = r.read_varint(optimise_positive=True)
                    tl = DeformTimeline(slot=slot_name, attachment=attachment_name)
                    for frame_idx in range(frame_count):
                        time = r.read_float()
                        count = r.read_varint(optimise_positive=True)
                        if count == 0:
                            deform = list(base_vertices)
                        else:
                            start = r.read_varint(optimise_positive=True)
                            values = [r.read_float() for _ in range(count)]
                            length = max(len(base_vertices), start + count)
                            deform = [0.0] * length
                            deform[start:start + count] = values
                            if base_vertices:
                                if len(deform) < len(base_vertices):
                                    deform.extend([0.0] * (len(base_vertices) - len(deform)))
                                deform = [
                                    deform[i] + base_vertices[i]
                                    for i in range(len(base_vertices))
                                ]
                        curve = _read_curve_38(r, f) if frame_idx < frame_count - 1 else "linear"
                        tl.keyframes.append(DeformKeyframe(time=time, vertices=deform, curve=curve))
                        duration = max(duration, time)
                    if tl.keyframes:
                        anim.timelines.append(tl)

        # Draw order timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            time = r.read_float()
            offset_count = r.read_varint(optimise_positive=True)
            for ___ in range(offset_count):
                r.read_varint(optimise_positive=True)
                r.read_varint(optimise_positive=False)
            duration = max(duration, time)

        # Event timelines.
        for __ in range(r.read_varint(optimise_positive=True)):
            time = r.read_float()
            r.read_varint(optimise_positive=True)
            r.read_varint(optimise_positive=False)
            r.read_float()
            if r.read_bool():
                read_str()
            duration = max(duration, time)

        anim.duration = max(duration, 1e-6)
        skel.animations[anim_name] = anim


def _parse_binary_animations(r: _BinaryReader, f: BinaryIO,
                              skel: SpineSkeleton,
                              bone_names: list[str], slot_names: list[str],
                              is_v4: bool) -> None:
    n_anims = r.read_varint()
    for _ in range(n_anims):
        anim_name = r.read_string() or "animation"
        anim = Animation(name=anim_name)

        # Slot timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_varint()  # slot idx
            n_tl = r.read_varint()
            for ___ in range(n_tl):
                tl_type = r.read_byte()
                n_kf = r.read_varint()
                if tl_type == 0:  # attachment
                    for ____ in range(n_kf):
                        r.read_float()
                        r.read_string()
                elif tl_type == 1:  # color
                    for ____ in range(n_kf):
                        r.read_float()
                        f.read(4)
                        if n_kf > 1:
                            f.read(4 * 6)  # curve
                elif tl_type == 2:  # two-color
                    for ____ in range(n_kf):
                        r.read_float()
                        f.read(4)
                        f.read(4)
                        if n_kf > 1:
                            f.read(4 * 6)

        # Bone timelines
        n = r.read_varint()
        for __ in range(n):
            bone_idx = r.read_varint()
            bone_name = bone_names[bone_idx] if bone_idx < len(bone_names) else f"b{bone_idx}"
            n_tl = r.read_varint()
            for ___ in range(n_tl):
                tl_type = r.read_byte()
                n_kf = r.read_varint()
                prop = {0: "rotate", 1: "translateX", 2: "translateY",
                        3: "scaleX", 4: "scaleY",
                        5: "shearX", 6: "shearY"}.get(tl_type, f"tl{tl_type}")
                tl = BoneTimeline(bone=bone_name, property=prop)
                for kf_i in range(n_kf):
                    t = r.read_float()
                    val = r.read_float()
                    if kf_i < n_kf - 1:
                        curve = r.read_byte()
                        if curve == 2:  # bezier
                            f.read(4 * 6)
                    tl.keyframes.append(BoneKeyframe(time=t, value=val))
                if tl.keyframes:
                    anim.timelines.append(tl)

        # IK timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_varint()
            n_kf = r.read_varint()
            for ___ in range(n_kf):
                r.read_float()
                r.read_float()
                r.read_float()
                r.read_byte()
                if n_kf > 1:
                    curve = r.read_byte()
                    if curve == 2:
                        f.read(4 * 6)

        # Transform timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_varint()
            n_kf = r.read_varint()
            for ___ in range(n_kf):
                r.read_float()
                f.read(4 * 4)
                if n_kf > 1:
                    curve = r.read_byte()
                    if curve == 2:
                        f.read(4 * 6)

        # Path timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_varint()
            r.read_byte()
            n_kf = r.read_varint()
            for ___ in range(n_kf):
                r.read_float()
                r.read_float()
                if n_kf > 1:
                    curve = r.read_byte()
                    if curve == 2:
                        f.read(4 * 6)

        # Deform timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_varint()  # skin idx
            n_slot = r.read_varint()
            for ___ in range(n_slot):
                r.read_varint()
                n_tl2 = r.read_varint()
                for ____ in range(n_tl2):
                    r.read_varint()
                    n_kf = r.read_varint()
                    for _____ in range(n_kf):
                        r.read_float()
                        end = r.read_varint()
                        if end != 0:
                            start = r.read_varint()
                            f.read(4 * (end - start + 1))
                        if n_kf > 1:
                            curve = r.read_byte()
                            if curve == 2:
                                f.read(4 * 6)

        # Draw order timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_float()
            n_off = r.read_varint()
            f.read(8 * n_off)

        # Event timelines (skip)
        n = r.read_varint()
        for __ in range(n):
            r.read_float()
            r.read_varint()
            r.read_varint()
            r.read_float()
            has_str = r.read_bool()
            if has_str:
                r.read_string()
            if is_v4:
                r.read_bool()
                if r.read_bool():
                    r.read_string()

        bone_tls = [tl for tl in anim.timelines if not tl.bone.startswith("__")]
        anim.duration = max(
            (tl.keyframes[-1].time for tl in bone_tls if tl.keyframes),
            default=1.0,
        )
        skel.animations[anim_name] = anim
