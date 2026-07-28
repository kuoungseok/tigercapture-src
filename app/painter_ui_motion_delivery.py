"""Property-level delivery preflight for Painter UI motion bindings."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

from app.motion_designer.schema import MotionComposition
from app.motion_designer.ui_motion_binding import (
    UIMotionBinding,
    ui_motion_bindings,
)
from app.painter_ui_document import normalize_ui_document
from app.painter_ui_motion_actor import (
    MOTION_ACTOR_KIND,
    motion_actor_composition_id,
)
from app.painter_ui_motion_bridge import linked_motion_composition_id


MOTION_DELIVERY_SCHEMA = "tigerstudio.painter.ui.motion_delivery.v1"
MOTION_DELIVERY_ADAPTER_VERSION = {
    "web": "capability-only.v1",
    "app": "capability-only.v1",
    "umg": "TigerStudioUMG.v1",
}
MOTION_DELIVERY_TARGETS = ("web", "app", "umg")
MOTION_DELIVERY_RESULTS = (
    "Native",
    "Vector",
    "Material",
    "Baked",
    "Actor Only",
    "Blocked",
)

_TRANSFORM_PROPERTIES = {"position", "scale", "rotation", "opacity", "anchor"}
_MATERIAL_PROPERTIES = {"fill", "stroke", "corner_radius", "progress"}
_VECTOR_FEATURES = {
    "path",
    "path_morph",
    "trim_path",
    "dash_offset",
    "gradient",
    "mask",
    "clip_path",
}
_RASTER_EFFECTS = {
    "blur",
    "glow",
    "shadow",
    "drop_shadow",
    "inner_shadow",
    "mesh_warp",
    "paper_fold",
    "difference_key",
}
_ACTOR_FEATURES = {
    "motion_actor",
    "particle",
    "particles",
    "live2d",
    "spine",
    "mmd",
    "vrm",
    "ar_pbr",
    "audio",
    "tracking",
    "camera_3d",
    "light_3d",
}


def _normal_feature(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")


def _find_object(document: Mapping[str, Any], object_id: str) -> dict[str, Any]:
    selected = next(
        (row for row in document["objects"] if row["id"] == object_id),
        None,
    )
    if selected is None:
        raise ValueError(f"Unknown Painter UI object: {object_id}")
    return dict(selected)


def _binding_features(
    composition: MotionComposition,
    binding: UIMotionBinding,
) -> list[str]:
    features = {
        _normal_feature(name)
        for name in binding.property_names
        if _normal_feature(name)
    }
    layer_ids = set(binding.layer_ids)
    for layer in composition.layers:
        if layer_ids and layer.id not in layer_ids:
            continue
        for name, prop in layer.transform.properties().items():
            if prop.enabled and prop.keyframes:
                features.add(_normal_feature(name))
        for effect in layer.effects:
            features.add(_normal_feature(effect.kind))
        for mask in layer.masks:
            features.add(_normal_feature(mask.kind or "mask"))
        source_params = layer.source.params
        if isinstance(source_params, Mapping):
            for name in ("repeater", "trim_path", "path_morph", "gradient"):
                if source_params.get(name):
                    features.add(name)
    return sorted(features or {"position", "opacity"})


def _requested_mode(binding: UIMotionBinding, target: str) -> str:
    overrides = binding.metadata.get("target_policies")
    if isinstance(overrides, Mapping):
        value = str(overrides.get(target) or "").strip()
        if value:
            return value
    return binding.delivery_policy


def _resolve_feature(
    feature: str,
    target: str,
    *,
    object_kind: str,
    requested: str,
) -> tuple[str, list[str]]:
    if feature in _ACTOR_FEATURES:
        if object_kind == MOTION_ACTOR_KIND:
            return "Actor Only", ["time-varying actor content stays an actor surface"]
        return "Blocked", ["Actor Only is invalid for a normal UI component binding"]

    if feature in _TRANSFORM_PROPERTIES:
        if target == "umg":
            return "Native", ["generated as a UWidgetAnimation transform track"]
        return "Blocked", [
            f"{target} transform capability is known but no executable adapter is installed"
        ]

    if feature in _MATERIAL_PROPERTIES:
        if target == "umg":
            return "Blocked", [
                "UI Material animation generation is not proven by Unreal capture"
            ]
        return "Blocked", [
            f"{target} animated appearance adapter is not implemented"
        ]

    if feature in _VECTOR_FEATURES:
        if target == "web":
            return "Blocked", ["SVG/Canvas animation adapter is not implemented"]
        if target == "umg":
            return "Blocked", [
                "UI Material or deterministic bake is required and not generated yet"
            ]
        return "Blocked", ["native app vector animation adapter is not implemented"]

    if feature in _RASTER_EFFECTS or feature in {"repeater", "replicator"}:
        if requested == "native_only":
            return "Blocked", [f"{feature} requires a visual bake for this target"]
        return "Blocked", [
            "deterministic visual bake is required but no target bake artifact exists"
        ]

    return "Blocked", [f"no declared {target} conversion for feature '{feature}'"]


def motion_delivery_report(
    document_value: Mapping[str, Any],
    object_id: str,
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a non-mutating, feature-level Web/App/UMG delivery report."""
    document = normalize_ui_document(document_value)
    selected_id = str(object_id or "")
    obj = _find_object(document, selected_id)
    composition_id = (
        motion_actor_composition_id(obj)
        if obj["kind"] == MOTION_ACTOR_KIND
        else linked_motion_composition_id(document, selected_id)
    )
    raw_composition = compositions.get(composition_id)
    composition = (
        MotionComposition.from_dict(raw_composition)
        if isinstance(raw_composition, Mapping)
        else raw_composition
    )
    if not isinstance(composition, MotionComposition):
        return {
            "schema": MOTION_DELIVERY_SCHEMA,
            "object_id": selected_id,
            "object_name": str(obj.get("name") or obj["kind"]),
            "object_kind": obj["kind"],
            "attached": False,
            "composition_id": composition_id,
            "bindings": [],
            "targets": [],
            "blockers": ["motion_composition_missing"],
        }

    bindings = [
        binding
        for binding in ui_motion_bindings(composition)
        if binding.source_object_id == selected_id
        or obj["kind"] == MOTION_ACTOR_KIND
    ]
    if obj["kind"] == MOTION_ACTOR_KIND and not bindings:
        bindings = [
            UIMotionBinding(
                source_document_id=document["document_id"],
                source_object_id=selected_id,
                host_layer_id=selected_id,
                layer_ids=[layer.id for layer in composition.layers],
                property_names=["motion_actor"],
                scope="loop",
                loop=bool((obj.get("content") or {}).get("loop", True)),
                animation_name=composition.name,
            )
        ]

    target_rows: list[dict[str, Any]] = []
    all_blockers: list[str] = []
    for target in MOTION_DELIVERY_TARGETS:
        feature_rows: list[dict[str, Any]] = []
        for binding in bindings:
            requested = _requested_mode(binding, target)
            for feature in _binding_features(composition, binding):
                resolved, reasons = _resolve_feature(
                    feature,
                    target,
                    object_kind=obj["kind"],
                    requested=requested,
                )
                feature_rows.append(
                    {
                        "binding_id": binding.id,
                        "feature": feature,
                        "requested": requested,
                        "resolved": resolved,
                        "reasons": reasons,
                        "adapter_version": MOTION_DELIVERY_ADAPTER_VERSION[target],
                        "artifact_revision": int(composition.revision),
                    }
                )
                if resolved == "Blocked":
                    all_blockers.append(
                        f"{target}:{binding.id}:{feature}:{reasons[0]}"
                    )
        counts = Counter(row["resolved"] for row in feature_rows)
        target_rows.append(
            {
                "target": target,
                "adapter_version": MOTION_DELIVERY_ADAPTER_VERSION[target],
                "artifact_revision": int(composition.revision),
                "counts": {
                    result: int(counts.get(result, 0))
                    for result in MOTION_DELIVERY_RESULTS
                },
                "features": feature_rows,
                "ok": not any(
                    row["resolved"] == "Blocked" for row in feature_rows
                ),
            }
        )

    return {
        "schema": MOTION_DELIVERY_SCHEMA,
        "document_id": document["document_id"],
        "document_revision": int(document["revision"]),
        "object_id": selected_id,
        "object_name": str(obj.get("name") or obj["kind"]),
        "object_kind": obj["kind"],
        "attached": True,
        "composition_id": composition.id,
        "composition_name": composition.name,
        "composition_revision": int(composition.revision),
        "bindings": [binding.to_dict() for binding in bindings],
        "targets": target_rows,
        "blockers": sorted(set(all_blockers)),
        "interaction_structure": {
            "must_remain_native": True,
            "preserve": ["accessibility", "focus", "hit_test", "localized_text"],
        },
    }


__all__ = [
    "MOTION_DELIVERY_ADAPTER_VERSION",
    "MOTION_DELIVERY_RESULTS",
    "MOTION_DELIVERY_SCHEMA",
    "MOTION_DELIVERY_TARGETS",
    "motion_delivery_report",
]
