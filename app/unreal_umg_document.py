"""Provider-neutral Tiger Studio UMG document and resource packaging."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.motion_designer.interactive_button import button_component
from app.motion_designer.schema import AnimatedProperty, MotionComposition, MotionLayer
from app.unreal_umg_layout import (
    TIGER_UMG_SCHEMA_VERSION,
    motion_layer_layout,
)
from app.unreal_umg_image_fill import (
    UMGImageFillConversion,
    motion_image_fill_conversion,
    validate_umg_image_fill_record,
)
from app.unreal_umg_material import (
    motion_shape_gradient_material,
    validate_umg_material_record,
)


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
    *,
    animation_name: str = "",
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
        "AnimationName": str(
            animation_name
            or prop.metadata.get("umg_animation")
            or "TigerTimeline"
        ),
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


def _static_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, Mapping):
        value = value.get("default", default)
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _umg_block_reasons(
    layer: MotionLayer,
    image_fill: UMGImageFillConversion | None = None,
) -> list[str]:
    if layer.layer_type not in SUPPORTED_NATIVE_LAYERS:
        return [f"unsupported_layer_type:{layer.layer_type}"]
    params = layer.source.params
    reasons: list[str] = list(
        image_fill.block_reasons if image_fill is not None else []
    )
    if layer.layer_type == "shape":
        gradient_material = (
            None
            if image_fill is not None
            else motion_shape_gradient_material(
                params,
                layer_type=layer.layer_type,
            )
        )
        primitive = str(
            params.get("shape")
            or params.get("primitive")
            or "rectangle"
        ).lower()
        if primitive != "rectangle":
            reasons.append(f"shape_primitive_requires_bake:{primitive}")
        radius = params.get("radius", 0.0)
        if _static_number(radius) > 0.0 and image_fill is None:
            reasons.append("rounded_shape_requires_bake")
        for key in (
            "path", "boolean", "trim", "offset_path", "repeater",
            "stroke_gradient", "dash", "stroke_taper",
        ):
            value = params.get(key)
            if value not in (None, {}, [], 0, 0.0, False):
                reasons.append(f"shape_operator_requires_bake:{key}")
        if (
            params.get("gradient") not in (None, {}, [], False)
            and gradient_material is None
        ):
            reasons.append(
                "multiple_shape_fills_require_ui_material_or_bake"
                if image_fill is not None
                else "shape_operator_requires_bake:gradient"
            )
        if _static_number(params.get("stroke_width", 0.0)) > 0.0:
            reasons.append("shape_stroke_requires_bake")
        if gradient_material is not None:
            reasons.extend(
                validate_umg_material_record(
                    gradient_material,
                    layer_kind="Shape",
                )
            )
    elif layer.layer_type == "text":
        for key in (
            "text_animation", "text_animators", "text_path", "font_axes",
            "font_file", "font_family", "stroke", "shadow_color",
            "background_color",
        ):
            value = params.get(key)
            if value not in (None, {}, [], "", 0, 0.0, False, "transparent"):
                reasons.append(f"text_feature_requires_bake:{key}")
        if _static_number(params.get("stroke_width", 0.0)) > 0.0:
            reasons.append("text_stroke_requires_bake")
    animated_source = [
        key for key, value in params.items()
        if isinstance(value, Mapping) and value.get("keyframes")
    ]
    reasons.extend(
        f"animated_source_requires_bake:{key}" for key in animated_source
    )
    for metadata_key in (
        "path_morph",
        "time_remap",
        "effect_group",
        "collage_item",
        "collage_attachment",
        "replicator",
        "motion_blur",
        "puppet_mesh",
        "expressions",
    ):
        value = layer.metadata.get(metadata_key)
        if value not in (None, {}, [], False):
            reasons.append(f"motion_feature_requires_bake:{metadata_key}")
    if layer.behaviors:
        reasons.append("motion_feature_requires_bake:behaviors")
    stop_motion = layer.metadata.get("stop_motion")
    if (
        isinstance(stop_motion, Mapping)
        and bool(stop_motion.get("enabled", False))
    ):
        reasons.append("motion_feature_requires_bake:stop_motion")
    frame_blending = layer.metadata.get("frame_blending")
    if (
        isinstance(frame_blending, Mapping)
        and str(frame_blending.get("mode") or "off") != "off"
    ):
        reasons.append("motion_feature_requires_bake:frame_blending")
    reasons.extend(
        f"effect_requires_bake:{effect.kind}"
        for effect in layer.effects
        if effect.enabled
    )
    reasons.extend(
        f"mask_requires_bake:{mask.kind}"
        for mask in layer.masks
    )
    return sorted(set(reasons))


def motion_composition_to_umg_document(
    composition: MotionComposition,
    *,
    provider: str = "motion_designer",
) -> dict[str, Any]:
    from app.motion_designer.ui_motion_binding import (
        UI_MOTION_UMG_TRIGGERS,
        ui_animation_name,
        ui_motion_bindings,
    )

    resources: dict[str, dict[str, Any]] = {}
    layers: list[dict[str, Any]] = []
    animations: list[dict[str, Any]] = []
    interactions: list[dict[str, Any]] = []
    from app.color_runtime import display_transform_required
    from app.motion_designer.color_management import settings_from_composition_metadata

    motion_color = settings_from_composition_metadata(composition.metadata)
    document_block_reasons = (
        ["motion_feature_requires_bake:color_management"]
        if display_transform_required(motion_color.project)
        or motion_color.project.is_hdr()
        or motion_color.project.ocio_config_path
        else []
    )
    stop_motion = composition.metadata.get("stop_motion")
    if (
        isinstance(stop_motion, Mapping)
        and bool(stop_motion.get("enabled", False))
    ):
        document_block_reasons.append(
            "motion_feature_requires_bake:stop_motion",
        )

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
        image_fill_conversion = motion_image_fill_conversion(layer)
        material_record = (
            None
            if image_fill_conversion is not None
            else motion_shape_gradient_material(
                layer.source.params,
                layer_type=layer.layer_type,
            )
        )
        block_reasons = sorted(set([
            *_umg_block_reasons(layer, image_fill_conversion),
            *document_block_reasons,
        ]))
        disposition = (
            "Blocked"
            if block_reasons
            else "Material"
            if material_record is not None
            else "Native"
        )
        if layer.layer_type not in SUPPORTED_NATIVE_LAYERS:
            layer_kind = "Unsupported"

        asset_id = ""
        image_fill_record: dict[str, Any] = {}
        if image_fill_conversion is not None:
            asset_id = register_resource(
                image_fill_conversion.source_path,
                "texture",
            )
            image_fill_record = image_fill_conversion.bind_asset(asset_id)
        font_file = str(layer.source.params.get("font_file") or "")
        font_asset_id = register_resource(font_file, "font") if font_file else ""

        position = _vector2(layer.transform.position.default, (0.0, 0.0))
        scale = _vector2(layer.transform.scale.default, (1.0, 1.0))
        anchor = _vector2(layer.transform.anchor.default, (0.5, 0.5))
        width = float(layer.source.params.get("width", 100.0) or 100.0)
        height = float(layer.source.params.get("height", 100.0) or 100.0)
        layout_fields = motion_layer_layout(
            position=position,
            size=(width, height),
            anchor=anchor,
        )
        payload = _layer_payload(layer)
        payload["font_asset_id"] = font_asset_id
        payload["image_fill"] = dict(image_fill_record)
        payload["umg_mapping"] = (
            "blocked_preflight"
            if block_reasons
            else "ui_material_custom_hlsl"
            if disposition == "Material"
            else "native"
        )
        payload["umg_block_reasons"] = block_reasons

        layers.append(
            {
                "Id": layer.id,
                "ParentId": layer.parent_id,
                "Name": layer.name,
                "Kind": layer_kind,
                "Disposition": disposition,
                "BlockReasons": block_reasons,
                **layout_fields,
                "Scale": scale,
                "RotationDegrees": float(layer.transform.rotation.default or 0.0),
                "Opacity": float(layer.transform.opacity.default or 0.0),
                "AssetId": asset_id,
                "ImageFill": image_fill_record,
                "Material": (
                    material_record if disposition == "Material" else {}
                ),
                "PayloadJson": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            }
        )

        for property_name, prop in layer.transform.properties().items():
            if property_name == "anchor":
                continue
            track = _animated_track(
                layer.id,
                property_name,
                prop,
                animation_name=ui_animation_name(
                    composition,
                    layer.id,
                    property_name,
                ),
            )
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

    layer_by_id = {layer.id: layer for layer in composition.layers}
    for binding in ui_motion_bindings(composition):
        host_layer_id = (
            binding.host_layer_id
            or (
                binding.source_object_id
                if binding.source_object_id in layer_by_id
                else ""
            )
            or (binding.layer_ids[0] if binding.layer_ids else "")
        )
        host_layer = layer_by_id.get(host_layer_id)
        trigger = UI_MOTION_UMG_TRIGGERS.get(binding.trigger, "")
        if (
            host_layer is None
            or button_component(host_layer) is None
            or not trigger
            or not binding.animation_name
        ):
            continue
        action_row = {
            "Type": "play_animation",
            "TargetId": host_layer_id,
            "Name": binding.animation_name,
            "ResourceId": "",
            "ResourcePath": "",
            "ValueJson": "null",
            "ParametersJson": json.dumps(
                {
                    "ui_binding_id": binding.id,
                    "source_document_id": binding.source_document_id,
                    "source_object_id": binding.source_object_id,
                    "scope": binding.scope,
                    "from_state": binding.from_state,
                    "to_state": binding.to_state,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        }
        existing = next(
            (
                row
                for row in interactions
                if row["ComponentId"] == host_layer_id
                and row["Trigger"].casefold() == trigger.casefold()
            ),
            None,
        )
        if existing is None:
            interactions.append(
                {
                    "ComponentId": host_layer_id,
                    "Trigger": trigger,
                    "Actions": [action_row],
                }
            )
        elif not any(
            action["Type"] == "play_animation"
            and action["Name"] == binding.animation_name
            for action in existing["Actions"]
        ):
            existing["Actions"].append(action_row)

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


def preflight_umg_document(document: Mapping[str, Any]) -> dict[str, Any]:
    schema_version = int(document.get("SchemaVersion", 0) or 0)
    counts = {"Native": 0, "Material": 0, "Baked": 0, "Blocked": 0}
    blockers: list[dict[str, Any]] = []
    for row in document.get("Layers", []):
        if not isinstance(row, Mapping):
            continue
        disposition = str(row.get("Disposition") or "Blocked")
        counts[disposition] = counts.get(disposition, 0) + 1
        image_reasons = validate_umg_image_fill_record(
            row.get("ImageFill"),
            layer_asset_id=str(row.get("AssetId") or ""),
        )
        if disposition == "Material":
            reasons = [
                *image_reasons,
                *validate_umg_material_record(
                    row.get("Material"),
                    layer_kind=str(row.get("Kind") or ""),
                    document_schema_version=schema_version,
                ),
            ]
            if not reasons:
                continue
        elif disposition == "Baked":
            reasons = ["baked_generation_unavailable"]
        elif disposition == "Blocked":
            reasons = [
                str(reason)
                for reason in row.get("BlockReasons", [])
                if str(reason)
            ] or ["unsupported_layer"]
        else:
            reasons = image_reasons
            if not reasons:
                continue
        blockers.append({
            "layer_id": str(row.get("Id") or ""),
            "name": str(row.get("Name") or ""),
            "reasons": reasons,
        })
    return {
        "schema_version": schema_version,
        "ok": not blockers,
        "counts": counts,
        "blockers": blockers,
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
    preflight = preflight_umg_document(packaged)
    return {
        "ok": not missing and preflight["ok"],
        "document_path": str(document_path),
        "asset_count": len(list(_resource_rows(packaged))),
        "copied": copied,
        "missing": missing,
        "document": packaged,
        "preflight": preflight,
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
    "preflight_umg_document",
]
