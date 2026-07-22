"""Deterministic Motion asset relinking for moved project folders."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import MotionComposition, MotionLayer


MOTION_RELINK_SCHEMA = "tigercapture.motion.relink.v1"
_REMOTE_PREFIXES = ("http://", "https://", "data:")
_EXPLICIT_PATH_KEYS = {
    "atlas_path", "audio_path", "depth_path", "environment_path", "font_file",
    "hdri_path", "model_path", "motion_path", "resolved_path", "source_path",
    "sprite_uri", "texture_path", "video_path",
}


@dataclass(frozen=True, slots=True)
class MotionAssetReference:
    layer_id: str
    layer_name: str
    kind: str
    location: tuple[str, ...]
    value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "layer_name": self.layer_name,
            "kind": self.kind,
            "location": ".".join(self.location),
            "value": self.value,
        }


def _is_path_key(key: str) -> bool:
    value = str(key).casefold()
    return value in _EXPLICIT_PATH_KEYS or value.endswith("_path") or value.endswith("_file")


def _walk_path_values(value: Any, prefix: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], str]]:
    if not isinstance(value, Mapping):
        return
    for raw_key, child in value.items():
        key = str(raw_key)
        location = (*prefix, key)
        if isinstance(child, str) and child.strip() and _is_path_key(key):
            yield location, child.strip()
        elif isinstance(child, Mapping):
            yield from _walk_path_values(child, location)


def collect_motion_asset_references(composition: MotionComposition) -> list[MotionAssetReference]:
    references: list[MotionAssetReference] = []
    for layer in composition.layers:
        uri = str(layer.source.uri or "").strip()
        if uri:
            references.append(MotionAssetReference(
                layer.id, layer.name, layer.source.kind or layer.layer_type, ("source", "uri"), uri,
            ))
        for location, value in _walk_path_values(layer.source.params, ("source", "params")):
            references.append(MotionAssetReference(
                layer.id, layer.name, layer.source.kind or layer.layer_type, location, value,
            ))
    return references


def _relative_to_root(path: Path, root: Path) -> Path | None:
    if not path.is_absolute():
        return path
    try:
        return path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return None


def _basename_index(root: Path, names: set[str]) -> dict[str, list[Path]]:
    index = {name.casefold(): [] for name in names if name}
    if not root.is_dir() or not index:
        return index
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        key = candidate.name.casefold()
        if key in index:
            index[key].append(candidate.resolve())
    return index


def build_motion_relink_plan(composition: MotionComposition, *, old_root: str | Path,
                             new_root: str | Path) -> dict[str, Any]:
    old_base = Path(old_root).expanduser().resolve(strict=False)
    new_base = Path(new_root).expanduser().resolve(strict=False)
    references = collect_motion_asset_references(composition)
    names: set[str] = set()
    for reference in references:
        if reference.value.casefold().startswith(_REMOTE_PREFIXES):
            continue
        source = Path(reference.value).expanduser()
        relative = _relative_to_root(source, old_base)
        exact = (new_base / relative).resolve(strict=False) if relative is not None else None
        if exact is None or not exact.is_file():
            names.add(source.name)
    name_index = _basename_index(new_base, names)
    rows: list[dict[str, Any]] = []
    for reference in references:
        original = reference.value
        row = {**reference.to_dict(), "candidate": "", "strategy": "", "status": ""}
        if original.casefold().startswith(_REMOTE_PREFIXES):
            row.update(status="external", strategy="preserve_remote", candidate=original)
            rows.append(row)
            continue
        source = Path(original).expanduser()
        relative = _relative_to_root(source, old_base)
        exact = (new_base / relative).resolve(strict=False) if relative is not None else None
        if exact is not None and exact.is_file():
            row.update(status="resolved", strategy="relative", candidate=str(exact))
        else:
            candidates = name_index.get(source.name.casefold(), [])
            if len(candidates) == 1:
                row.update(status="resolved", strategy="unique_basename", candidate=str(candidates[0]))
            elif len(candidates) > 1:
                row.update(
                    status="ambiguous", strategy="manual_required",
                    candidates=[str(path) for path in candidates],
                )
            else:
                row.update(status="missing", strategy="manual_required")
        rows.append(row)
    resolved = [row for row in rows if row["status"] == "resolved"]
    ambiguous = [row for row in rows if row["status"] == "ambiguous"]
    missing = [row for row in rows if row["status"] == "missing"]
    changed = [row for row in resolved if Path(row["candidate"]) != Path(row["value"])]
    return {
        "schema": MOTION_RELINK_SCHEMA,
        "ok": new_base.is_dir() and not ambiguous and not missing,
        "composition_id": composition.id,
        "composition_revision": composition.revision,
        "old_root": str(old_base),
        "new_root": str(new_base),
        "new_root_exists": new_base.is_dir(),
        "reference_count": len(rows),
        "resolved_count": len(resolved),
        "changed_count": len(changed),
        "ambiguous_count": len(ambiguous),
        "missing_count": len(missing),
        "rows": rows,
    }


def _set_reference(layer: MotionLayer, location: str, value: str) -> None:
    parts = tuple(part for part in str(location).split(".") if part)
    if parts == ("source", "uri"):
        layer.source.uri = value
        return
    if parts[:2] != ("source", "params"):
        raise ValueError(f"Unsupported Motion relink location: {location}")
    target: dict[str, Any] = layer.source.params
    for key in parts[2:-1]:
        child = target.get(key)
        if not isinstance(child, dict):
            child = {}
            target[key] = child
        target = child
    target[parts[-1]] = value


def apply_motion_relink(composition: MotionComposition, *, old_root: str | Path,
                        new_root: str | Path, allow_partial: bool = False) -> tuple[MotionComposition, dict[str, Any]]:
    plan = build_motion_relink_plan(composition, old_root=old_root, new_root=new_root)
    if not plan["new_root_exists"]:
        raise FileNotFoundError(f"Motion relink root not found: {plan['new_root']}")
    if not allow_partial and (plan["ambiguous_count"] or plan["missing_count"]):
        raise ValueError(
            "Motion relink requires manual review: "
            f"{plan['ambiguous_count']} ambiguous, {plan['missing_count']} missing"
        )
    candidate = MotionComposition.from_dict(composition.to_dict())
    layers = {layer.id: layer for layer in candidate.layers}
    changed = 0
    for row in plan["rows"]:
        if row["status"] != "resolved" or not row.get("candidate"):
            continue
        target = str(row["candidate"])
        if Path(target) == Path(str(row["value"])):
            continue
        layer = layers.get(str(row["layer_id"]))
        if layer is None:
            raise ValueError(f"Motion relink layer disappeared: {row['layer_id']}")
        _set_reference(layer, str(row["location"]), target)
        changed += 1
    if changed:
        candidate.revision += 1
        candidate.metadata.pop("broadcast_cache", None)
    candidate.metadata["project_asset_root"] = str(Path(new_root).expanduser().resolve(strict=False))
    history = list(candidate.metadata.get("relink_history") or [])
    history.append({
        "schema": MOTION_RELINK_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "old_root": plan["old_root"],
        "new_root": plan["new_root"],
        "changed_count": changed,
        "partial": bool(plan["ambiguous_count"] or plan["missing_count"]),
    })
    candidate.metadata["relink_history"] = history[-20:]
    result = deepcopy(plan)
    result.update({"applied": True, "changed": bool(changed), "changed_count": changed,
                   "composition_revision": candidate.revision})
    return candidate, result


__all__ = [
    "MOTION_RELINK_SCHEMA", "MotionAssetReference", "apply_motion_relink",
    "build_motion_relink_plan", "collect_motion_asset_references",
]
