"""Role-pair descriptor helpers for Action Sequencer AR/PBR previews."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping


ACTION_SEQUENCER_STAGE_PAIR_SCHEMA = "tigerstudio.ar_pbr.action_sequencer_stage_pair.v1"
DEFAULT_OWNER_STAGE_OFFSET = (0.0, 0.0, 1.08)
DEFAULT_TARGET_STAGE_OFFSET = (0.0, 0.0, -1.08)


def default_action_sequencer_stage_pair_path(
    owner_descriptor: Any,
    *,
    root: Path | None = None,
) -> Path:
    base = root or Path(__file__).resolve().parents[1] / "debugCapture"
    project_path = Path(getattr(owner_descriptor, "project_path", "ActionSequencer"))
    project_stem = _safe_file_stem(project_path.stem or "ActionSequencer")
    owner = _safe_file_stem(str(getattr(owner_descriptor, "owner_name", "Owner") or "Owner"))
    return base / f"action_sequencer_{project_stem}_{owner}_stage_pair.arpbr"


def write_action_sequencer_stage_pair_asset(
    owner_asset_path: str | Path,
    owner_descriptor: Any,
    output_path: str | Path | None = None,
    *,
    owner_offset: tuple[float, float, float] = DEFAULT_OWNER_STAGE_OFFSET,
    target_offset: tuple[float, float, float] = DEFAULT_TARGET_STAGE_OFFSET,
) -> Path:
    source = Path(owner_asset_path)
    target = Path(output_path) if output_path is not None else default_action_sequencer_stage_pair_path(owner_descriptor)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_ar_pbr_payload(source)
    descriptor = _payload_descriptor(payload)
    pair_descriptor = build_action_sequencer_stage_pair_descriptor(
        descriptor,
        owner_descriptor=owner_descriptor,
        owner_offset=owner_offset,
        target_offset=target_offset,
    )
    target.write_text(
        json.dumps(
            {
                "schema": ACTION_SEQUENCER_STAGE_PAIR_SCHEMA,
                "runtime_format": "ar_scene_descriptor",
                "descriptor": pair_descriptor,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


def build_action_sequencer_stage_pair_descriptor(
    source_descriptor: Mapping[str, Any],
    *,
    owner_descriptor: Any | None = None,
    owner_offset: tuple[float, float, float] = DEFAULT_OWNER_STAGE_OFFSET,
    target_offset: tuple[float, float, float] = DEFAULT_TARGET_STAGE_OFFSET,
) -> dict[str, Any]:
    descriptor = deepcopy(dict(source_descriptor or {}))
    original_geometries = [dict(item) for item in descriptor.get("geometries") or [] if isinstance(item, Mapping)]
    original_connections = [dict(item) for item in descriptor.get("connections") or [] if isinstance(item, Mapping)]
    original_models = [dict(item) for item in descriptor.get("models") or [] if isinstance(item, Mapping)]
    original_bones = [dict(item) for item in descriptor.get("bones") or [] if isinstance(item, Mapping)]
    target_bone_index_offset = _target_bone_index_offset(original_bones)
    source_bounds = _bounds_from_geometries(original_geometries) or _bounds_from_any(descriptor.get("bounds"))
    center = tuple(float(v) for v in source_bounds.get("center", [0.0, 0.0, 0.0])[:3])

    owner_geometries: list[dict[str, Any]] = []
    target_geometries: list[dict[str, Any]] = []
    for geometry in original_geometries:
        owner_copy = _role_geometry_copy(
            geometry,
            role="performer",
            role_slot="actor_a",
            name_prefix="Actor A Performer",
            center=center,
            offset=owner_offset,
            rotate_y_180=False,
            keep_skinning=True,
            target_bone_index_offset=0,
            remap_target_skinning=False,
        )
        owner_geometries.append(owner_copy)

        target_copy = _role_geometry_copy(
            geometry,
            role="target",
            role_slot="actor_b",
            name_prefix="Actor B Target",
            center=center,
            offset=target_offset,
            rotate_y_180=True,
            keep_skinning=True,
            target_bone_index_offset=target_bone_index_offset,
            remap_target_skinning=True,
        )
        target_geometries.append(target_copy)

    descriptor["schema"] = ACTION_SEQUENCER_STAGE_PAIR_SCHEMA
    descriptor["id"] = f"{str(descriptor.get('id') or 'action_sequencer')}_stage_pair"
    descriptor["source_format"] = "action_sequencer_stage_pair"
    descriptor["runtime_format"] = "ar_scene_descriptor"
    descriptor["backend"] = "action_sequencer_stage_pair"
    descriptor["geometries"] = owner_geometries + target_geometries
    descriptor["mesh_count"] = len(descriptor["geometries"])
    descriptor["geometry_count"] = len(descriptor["geometries"])
    descriptor["bounds"] = _bounds_from_geometries(descriptor["geometries"]) or source_bounds
    descriptor["models"] = original_models + _target_models(original_models)
    descriptor["bones"] = original_bones + _target_bones(original_bones, index_offset=target_bone_index_offset)
    descriptor["connections"] = original_connections + _target_connections(original_connections, original_geometries)

    warnings = list(descriptor.get("warnings") or [])
    warnings.append(
        "Action Sequencer stage pair preview duplicates the performer skeleton for an independent Actor B target reaction slot."
    )
    descriptor["warnings"] = warnings

    metadata = dict(descriptor.get("metadata") or {})
    owner_name = str(getattr(owner_descriptor, "owner_name", "Actor A") or "Actor A")
    metadata["action_sequencer_stage_pair"] = {
        "schema": ACTION_SEQUENCER_STAGE_PAIR_SCHEMA,
        "roles": [
            {
                "id": "actor_a",
                "technical_role": "performer",
                "label": "Actor A",
                "display_name": owner_name,
                "stage_position": "left",
                "stage_forward": "+X / screen right",
                "stage_offset": [float(v) for v in owner_offset],
                "animation_binding": "owner_animation_track",
            },
            {
                "id": "actor_b",
                "technical_role": "target",
                "label": "Actor B",
                "display_name": "Target",
                "stage_position": "right",
                "stage_forward": "-X / screen left",
                "animation_binding": "target_reaction_animation_track",
                "target_offset": [float(v) for v in target_offset],
                "target_bone_index_offset": int(target_bone_index_offset),
            },
        ],
        "target_reaction_status": "target_animation_slot_available",
        "next_step": "Reaction Base Finder -> Target Root Warp -> Contact Constraint Layer -> IK Polish",
    }
    descriptor["metadata"] = metadata
    return descriptor


def _role_geometry_copy(
    geometry: Mapping[str, Any],
    *,
    role: str,
    role_slot: str,
    name_prefix: str,
    center: tuple[float, float, float],
    offset: tuple[float, float, float],
    rotate_y_180: bool,
    keep_skinning: bool,
    target_bone_index_offset: int,
    remap_target_skinning: bool,
) -> dict[str, Any]:
    out = deepcopy(dict(geometry))
    source_id = str(out.get("id") or "geometry")
    prefix = "owner" if role_slot == "actor_a" else "target"
    out["id"] = f"{prefix}_{source_id}"
    out["name"] = f"{name_prefix} / {str(out.get('name') or source_id)}"
    out["role"] = role
    out["role_slot"] = role_slot
    transformed_vertices = _transform_points(
        out.get("vertices"),
        center=center,
        offset=offset,
        rotate_y_180=rotate_y_180,
    )
    out["stage_transform"] = {
        "enabled": True,
        "center": [float(v) for v in center],
        "offset": [float(v) for v in offset],
        "rotate_y_180": bool(rotate_y_180),
    }
    out["bounds"] = _bounds_from_vertices(transformed_vertices)
    out["model_id"] = f"{prefix}_{str(out.get('model_id') or 'static_model')}"
    if not keep_skinning:
        for key in tuple(out.keys()):
            if "skin" in str(key).casefold():
                out.pop(key, None)
    elif remap_target_skinning:
        out["skin_weights"] = _remap_target_skin_weights(
            out.get("skin_weights"),
            bone_index_offset=target_bone_index_offset,
        )
        if isinstance(out.get("skin_joint_ids"), list):
            out["skin_joint_ids"] = [
                f"target_{str(item)}" if not str(item).startswith("target_") else str(item)
                for item in out["skin_joint_ids"]
            ]
    out["animation_role"] = "owner_animation_track" if role_slot == "actor_a" else "target_reaction_animation_track"
    return out


def _target_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not models:
        return out
    for model in models:
        model_id = str(model.get("id") or "")
        if not model_id:
            continue
        copied = deepcopy(model)
        copied["id"] = f"target_{model_id}"
        copied["name"] = f"Actor B Target / {str(copied.get('name') or model_id)}"
        copied["type"] = str(copied.get("type") or "Mesh")
        copied["role"] = "target"
        copied["role_slot"] = "actor_b"
        out.append(copied)
    return out


def _target_bone_index_offset(bones: list[dict[str, Any]]) -> int:
    indices = []
    for idx, bone in enumerate(bones):
        try:
            indices.append(int(bone.get("index", idx)))
        except Exception:
            indices.append(idx)
    return max(indices, default=-1) + 1


def _target_bones(bones: list[dict[str, Any]], *, index_offset: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    id_by_index: dict[int, str] = {}
    for idx, bone in enumerate(bones):
        try:
            bone_index = int(bone.get("index", idx))
        except Exception:
            bone_index = idx
        bone_id = str(bone.get("id") or f"bone_{bone_index}")
        id_by_index[bone_index] = bone_id
    for idx, bone in enumerate(bones):
        copied = deepcopy(bone)
        try:
            source_index = int(copied.get("index", idx))
        except Exception:
            source_index = idx
        source_id = str(copied.get("id") or f"bone_{source_index}")
        copied["id"] = f"target_{source_id}"
        copied["name"] = f"Target / {str(copied.get('name') or source_id)}"
        copied["index"] = source_index + int(index_offset)
        copied["role"] = "target"
        copied["role_slot"] = "actor_b"
        parent_id = str(copied.get("parent_id") or "")
        if parent_id:
            copied["parent_id"] = f"target_{parent_id}"
        try:
            parent_index = int(copied.get("parent_index", -1))
        except Exception:
            parent_index = -1
        if parent_index >= 0:
            copied["parent_index"] = parent_index + int(index_offset)
            if not copied.get("parent_id"):
                parent_source_id = id_by_index.get(parent_index)
                if parent_source_id:
                    copied["parent_id"] = f"target_{parent_source_id}"
        out.append(copied)
    return out


def _remap_target_skin_weights(value: Any, *, bone_index_offset: int) -> Any:
    if isinstance(value, Mapping):
        out = deepcopy(dict(value))
        joints = out.get("joints")
        if isinstance(joints, list):
            out["joints"] = [_offset_bone_index(item, bone_index_offset) for item in joints]
        return out
    if not isinstance(value, list):
        return value
    remapped: list[Any] = []
    for row in value:
        if isinstance(row, Mapping):
            item = deepcopy(dict(row))
            if isinstance(item.get("joints"), list):
                item["joints"] = [_offset_bone_index(joint, bone_index_offset) for joint in item["joints"]]
            if "bone_index" in item:
                source_index = _int_or_none(item.get("bone_index"))
                item["bone_index"] = _offset_bone_index(item.get("bone_index"), bone_index_offset)
                if source_index is not None and not item.get("bone_id"):
                    item["bone_id"] = f"target_bone_{source_index}"
            if "joint" in item:
                item["joint"] = _offset_bone_index(item.get("joint"), bone_index_offset)
            if "joint_index" in item:
                item["joint_index"] = _offset_bone_index(item.get("joint_index"), bone_index_offset)
            for key in ("bone_id", "model_id"):
                text = str(item.get(key) or "")
                if text and not text.startswith("target_"):
                    item[key] = f"target_{text}"
            remapped.append(item)
        elif isinstance(row, list):
            remapped.append(_remap_target_skin_weights(row, bone_index_offset=bone_index_offset))
        else:
            remapped.append(row)
    return remapped


def _offset_bone_index(value: Any, offset: int) -> int:
    try:
        return int(value) + int(offset)
    except Exception:
        return int(offset)


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _target_connections(
    connections: list[dict[str, Any]],
    geometries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    geometry_ids = {str(item.get("id") or "") for item in geometries}
    out: list[dict[str, Any]] = []
    for connection in connections:
        child = str(connection.get("child") or "")
        copied = deepcopy(connection)
        if child in geometry_ids:
            copied["child"] = f"target_{child}"
            parent = str(copied.get("parent") or "")
            copied["parent"] = f"target_{parent}" if parent else "target_static_model"
        else:
            parent = str(copied.get("parent") or "")
            if parent:
                copied["parent"] = f"target_{parent}"
        out.append(copied)
    return out


def _transform_points(
    points: Any,
    *,
    center: tuple[float, float, float],
    offset: tuple[float, float, float],
    rotate_y_180: bool,
) -> list[list[float]]:
    if not isinstance(points, list):
        return []
    cx, cy, cz = center
    ox, oy, oz = offset
    out: list[list[float]] = []
    for point in points:
        row = _vec3(point)
        x = cx - (row[0] - cx) if rotate_y_180 else row[0]
        z = cz - (row[2] - cz) if rotate_y_180 else row[2]
        out.append([
            round(x + ox, 6),
            round(row[1] + oy, 6),
            round(z + oz, 6),
        ])
    return out


def _rotate_y_180_vectors(points: Any) -> list[list[float]]:
    if not isinstance(points, list):
        return []
    out: list[list[float]] = []
    for point in points:
        row = _vec3(point)
        out.append([round(-row[0], 6), round(row[1], 6), round(-row[2], 6)])
    return out


def _bounds_from_geometries(geometries: list[Mapping[str, Any]]) -> dict[str, list[float]] | None:
    bounds = [_bounds_from_any(item.get("bounds")) for item in geometries if isinstance(item, Mapping)]
    bounds = [item for item in bounds if item]
    if not bounds:
        all_vertices: list[list[float]] = []
        for geometry in geometries:
            vertices = geometry.get("vertices")
            if isinstance(vertices, list):
                all_vertices.extend(_vec3(point) for point in vertices)
        return _bounds_from_vertices(all_vertices) if all_vertices else None
    mins: list[list[float]] = []
    maxs: list[list[float]] = []
    for item in bounds:
        center = _vec3(item.get("center"))
        size = _vec3(item.get("size"), default=(0.0, 0.0, 0.0))
        half = [max(0.0, value) * 0.5 for value in size]
        mins.append([center[idx] - half[idx] for idx in range(3)])
        maxs.append([center[idx] + half[idx] for idx in range(3)])
    lo = [min(row[idx] for row in mins) for idx in range(3)]
    hi = [max(row[idx] for row in maxs) for idx in range(3)]
    return _bounds_from_min_max(lo, hi)


def _bounds_from_vertices(vertices: list[Any]) -> dict[str, list[float]]:
    rows = [_vec3(point) for point in vertices]
    if not rows:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}
    lo = [min(row[idx] for row in rows) for idx in range(3)]
    hi = [max(row[idx] for row in rows) for idx in range(3)]
    return _bounds_from_min_max(lo, hi)


def _bounds_from_min_max(lo: list[float], hi: list[float]) -> dict[str, list[float]]:
    return {
        "center": [round((lo[idx] + hi[idx]) * 0.5, 6) for idx in range(3)],
        "size": [round(max(1.0e-6, hi[idx] - lo[idx]), 6) for idx in range(3)],
    }


def _bounds_from_any(value: Any) -> dict[str, list[float]]:
    if not isinstance(value, Mapping):
        return {}
    center = _vec3(value.get("center"))
    size = _vec3(value.get("size"), default=(1.0, 1.0, 1.0))
    return {"center": center, "size": size}


def _vec3(value: Any, *, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> list[float]:
    if isinstance(value, (list, tuple)):
        raw = list(value)[:3]
    else:
        raw = []
    raw += [default[len(raw)]] if len(raw) < 1 else []
    raw += [default[len(raw)]] if len(raw) < 2 else []
    raw += [default[len(raw)]] if len(raw) < 3 else []
    out: list[float] = []
    for idx in range(3):
        try:
            out.append(float(raw[idx]))
        except Exception:
            out.append(float(default[idx]))
    return out


def _load_ar_pbr_payload(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Action Sequencer stage pair source could not be read: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"Action Sequencer stage pair source is not a JSON object: {path}")
    return data


def _payload_descriptor(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = payload.get("descriptor")
    return nested if isinstance(nested, Mapping) else payload


def _safe_file_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or ""))
    return cleaned.strip("_") or "ActionSequencer"


__all__ = [
    "ACTION_SEQUENCER_STAGE_PAIR_SCHEMA",
    "DEFAULT_OWNER_STAGE_OFFSET",
    "DEFAULT_TARGET_STAGE_OFFSET",
    "build_action_sequencer_stage_pair_descriptor",
    "default_action_sequencer_stage_pair_path",
    "write_action_sequencer_stage_pair_asset",
]
