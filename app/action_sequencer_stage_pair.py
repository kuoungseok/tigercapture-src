"""Role-pair descriptor helpers for Action Sequencer AR/PBR previews."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping


ACTION_SEQUENCER_STAGE_PAIR_SCHEMA = "tigerstudio.ar_pbr.action_sequencer_stage_pair.v1"
DEFAULT_OWNER_STAGE_OFFSET = (0.0, 0.0, -0.92)
DEFAULT_TARGET_STAGE_OFFSET = (0.0, 0.0, 0.92)


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
            rotate_y_180=True,
            keep_skinning=True,
        )
        owner_geometries.append(owner_copy)

        target_copy = _role_geometry_copy(
            geometry,
            role="target",
            role_slot="actor_b",
            name_prefix="Actor B Target",
            center=center,
            offset=target_offset,
            rotate_y_180=False,
            keep_skinning=False,
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
    descriptor["connections"] = original_connections + _target_connections(original_connections, original_geometries)

    warnings = list(descriptor.get("warnings") or [])
    warnings.append(
        "Action Sequencer stage pair preview duplicates the performer mesh as a static Actor B target role until target reaction matching is implemented."
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
                "animation_binding": "static_reaction_slot_pending",
                "target_offset": [float(v) for v in target_offset],
            },
        ],
        "target_reaction_status": "standing_static_placeholder",
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
) -> dict[str, Any]:
    out = deepcopy(dict(geometry))
    source_id = str(out.get("id") or "geometry")
    prefix = "owner" if role_slot == "actor_a" else "target"
    out["id"] = f"{prefix}_{source_id}"
    out["name"] = f"{name_prefix} / {str(out.get('name') or source_id)}"
    out["role"] = role
    out["role_slot"] = role_slot
    out["vertices"] = _transform_points(
        out.get("vertices"),
        center=center,
        offset=offset,
        rotate_y_180=rotate_y_180,
    )
    if rotate_y_180 and isinstance(out.get("normals"), list):
        out["normals"] = _rotate_y_180_vectors(out.get("normals"))
    out["bounds"] = _bounds_from_vertices(out.get("vertices") or [])
    out["model_id"] = f"{prefix}_{str(out.get('model_id') or 'static_model')}"
    if not keep_skinning:
        for key in tuple(out.keys()):
            if "skin" in str(key).casefold():
                out.pop(key, None)
    out["animation_role"] = "owner_animation_track" if keep_skinning else "target_static_until_reaction_base"
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
