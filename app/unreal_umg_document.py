"""Provider-neutral Tiger Studio UMG document and resource packaging."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.motion_designer.interactive_button import button_component
from app.motion_designer.schema import AnimatedProperty, MotionComposition, MotionLayer


TIGER_UMG_SCHEMA_VERSION = 2
SUPPORTED_NATIVE_LAYERS = {"group", "shape", "text", "image"}


def _value2(value: Any, default: tuple[float, float]) -> list[float]:
    row = list(value) if isinstance(value, (list, tuple)) else list(default)
    return [
        float(row[0]) if row else float(default[0]),
        float(row[1]) if len(row) > 1 else float(default[1]),
    ]


def _vector2(value: Any, default: tuple[float, float]) -> dict[str, float]:
    row = _value2(value, default)
    return {"X": row[0], "Y": row[1]}


def _resource_id(path: Path, kind: str) -> str:
    key = f"{kind}:{path.resolve()}".encode("utf-8", errors="surrogatepass")
    return f"{kind}_{hashlib.sha256(key).hexdigest()[:20]}"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _animated_track(
    layer_id: str,
    property_name: str,
    prop: AnimatedProperty,
) -> dict[str, Any] | None:
    if not prop.enabled or not prop.keyframes:
        return None
    values = []
    for key in prop.keyframes:
        raw = key.value
        if isinstance(raw, (list, tuple)):
            vector = [float(value) for value in list(raw)[:4]]
        else:
            vector = [float(raw)]
        vector.extend([0.0] * (4 - len(vector)))
        values.append(
            {
                "TimeMilliseconds": int(key.time_ms),
                "Value": {
                    "X": vector[0],
                    "Y": vector[1],
                    "Z": vector[2],
                    "W": vector[3],
                },
                "Interpolation": str(key.interpolation or "linear"),
                "InTangent": _vector2(key.in_tangent, (0.667, 1.0)),
                "OutTangent": _vector2(key.out_tangent, (0.333, 0.0)),
            }
        )
    return {
        "LayerId": layer_id,
        "AnimationName": str(prop.metadata.get("umg_animation") or "TigerTimeline"),
        "Property": property_name,
        "Keyframes": values,
    }


def _layer_payload(layer: MotionLayer) -> dict[str, Any]:
    params = dict(layer.source.params)
    return {
        "source_kind": layer.source.kind,
        "source_params": params,
        "text": str(params.get("text") or layer.name if layer.layer_type == "text" else ""),
        "fill": str(params.get("fill") or params.get("color") or "#ffffff"),
        "font_size": float(params.get("font_size", 48.0) or 48.0),
    }


def motion_composition_to_umg_document(
    composition: MotionComposition,
    *,
    provider: str = "motion_designer",
) -> dict[str, Any]:
    resources: dict[str, dict[str, Any]] = {}
    layers: list[dict[str, Any]] = []
    animations: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []

    def register_resource(uri: str, kind: str) -> str:
        if not uri:
            return ""
        path = Path(uri).expanduser()
        resource_id = _resource_id(path, kind)
        resources.setdefault(
            resource_id,
            {
                "Id": resource_id,
                "Kind": kind,
                "SourcePath": str(path),
                "DestinationName": f"TS_{resource_id}",
                "ContentHash": _file_hash(path) if path.is_file() else "",
                "SettingsJson": "{}",
            },
        )
        return resource_id

    for layer in composition.layers:
        component = button_component(layer)
        layer_kind = "Button" if component is not None else layer.layer_type.title()
        disposition = "Native"
        if layer.layer_type not in SUPPORTED_NATIVE_LAYERS:
            disposition = "Blocked"
            layer_kind = "Unsupported"

        asset_id = ""
        if layer.layer_type == "image":
            asset_id = register_resource(layer.source.uri, "texture")
        font_file = str(layer.source.params.get("font_file") or "")
        font_asset_id = register_resource(font_file, "font") if font_file else ""

        position = _vector2(layer.transform.position.default, (0.0, 0.0))
        scale = _vector2(layer.transform.scale.default, (1.0, 1.0))
        anchor = _vector2(layer.transform.anchor.default, (0.5, 0.5))
        width = float(layer.source.params.get("width", 100.0) or 100.0)
        height = float(layer.source.params.get("height", 100.0) or 100.0)
        payload = _layer_payload(layer)
        payload["font_asset_id"] = font_asset_id

        layers.append(
            {
                "Id": layer.id,
                "ParentId": layer.parent_id,
                "Name": layer.name,
                "Kind": layer_kind,
                "Disposition": disposition,
                "Position": position,
                "Size": {"X": width, "Y": height},
                "Scale": scale,
                "Anchor": anchor,
                "RotationDegrees": float(layer.transform.rotation.default or 0.0),
                "Opacity": float(layer.transform.opacity.default or 0.0),
                "AssetId": asset_id,
                "PayloadJson": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            }
        )

        for property_name, prop in layer.transform.properties().items():
            if property_name == "anchor":
                continue
            track = _animated_track(layer.id, property_name, prop)
            if track is not None:
                animations.append(track)

        if component is not None:
            for trigger, actions in component.actions.items():
                action_rows = []
                for action in actions:
                    resource_id = ""
                    if action.resource_uri:
                        resource_kind = "sound" if action.action_type == "play_sound" else "texture"
                        resource_id = register_resource(action.resource_uri, resource_kind)
                    action_rows.append(
                        {
                            "Type": action.action_type,
                            "TargetId": action.target_id,
                            "Name": action.name,
                            "ResourceId": resource_id,
                            "ResourcePath": "",
                            "ValueJson": json.dumps(action.value, ensure_ascii=False),
                            "ParametersJson": json.dumps(
                                action.parameters,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            ),
                        }
                    )
                interactions.append(
                    {
                        "ComponentId": layer.id,
                        "Trigger": trigger,
                        "Actions": action_rows,
                    }
                )

    return {
        "SchemaVersion": TIGER_UMG_SCHEMA_VERSION,
        "Provider": provider,
        "DocumentId": composition.id,
        "Revision": int(composition.revision),
        "Width": int(composition.width),
        "Height": int(composition.height),
        "FrameRate": float(composition.fps),
        "DurationMilliseconds": int(composition.duration_ms),
        "Resources": list(resources.values()),
        "Layers": layers,
        "Animations": animations,
        "Interactions": interactions,
    }


def _resource_rows(document: Mapping[str, Any]) -> Iterable[dict[str, Any]]:
    for row in document.get("Resources", []):
        if isinstance(row, dict):
            yield row


def package_umg_document(
    document: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    root = Path(output_dir).expanduser().resolve()
    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    packaged = json.loads(json.dumps(document, ensure_ascii=False))
    missing: list[str] = []
    copied: list[str] = []
    for row in _resource_rows(packaged):
        source = Path(str(row.get("SourcePath") or "")).expanduser()
        if not source.is_file():
            missing.append(str(source))
            continue
        suffix = source.suffix.lower()
        destination = assets_dir / f"{row['Id']}{suffix}"
        if not destination.is_file() or _file_hash(destination) != _file_hash(source):
            shutil.copy2(source, destination)
        row["SourcePath"] = destination.relative_to(root).as_posix()
        row["ContentHash"] = _file_hash(destination)
        copied.append(str(destination))

    document_path = root / "tiger_umg_document.json"
    document_path.write_text(
        json.dumps(packaged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": not missing,
        "document_path": str(document_path),
        "asset_count": len(list(_resource_rows(packaged))),
        "copied": copied,
        "missing": missing,
        "document": packaged,
    }


def package_motion_composition_for_umg(
    composition: MotionComposition,
    output_dir: str | Path,
    *,
    provider: str = "motion_designer",
) -> dict[str, Any]:
    return package_umg_document(
        motion_composition_to_umg_document(composition, provider=provider),
        output_dir,
    )


__all__ = [
    "TIGER_UMG_SCHEMA_VERSION",
    "motion_composition_to_umg_document",
    "package_motion_composition_for_umg",
    "package_umg_document",
]
