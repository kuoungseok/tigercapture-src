"""Qt-free Painter UI to Motion Designer authoring bridge."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.motion_designer.interactive_button import (
    button_component,
    create_button_component,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui_motion_binding import (
    UIMotionBinding,
    upsert_ui_motion_binding,
)
from app.painter_ui_document import normalize_ui_document


PAINTER_MOTION_TARGET = "motion_designer"
PAINTER_MOTION_LINK_VERSION = 2


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _padding(value: Any) -> tuple[float, float, float, float]:
    if isinstance(value, Mapping):
        return tuple(
            max(0.0, _number(value.get(key)))
            for key in ("left", "top", "right", "bottom")
        )
    if isinstance(value, (list, tuple)):
        rows = [_number(item) for item in value]
        if len(rows) >= 4:
            return tuple(max(0.0, item) for item in rows[:4])
        if len(rows) >= 2:
            return (
                max(0.0, rows[0]),
                max(0.0, rows[1]),
                max(0.0, rows[0]),
                max(0.0, rows[1]),
            )
    amount = max(0.0, _number(value))
    return amount, amount, amount, amount


def resolved_ui_geometry(
    value: Mapping[str, Any],
    *,
    normalize: bool = True,
    resolve_responsive: bool = True,
) -> dict[str, dict[str, float]]:
    """Resolve current absolute geometry, including basic auto-layout parents."""
    document = normalize_ui_document(value) if normalize else dict(value)
    from app.painter_ui_responsive import resolve_ui_responsive_document

    if resolve_responsive:
        document = resolve_ui_responsive_document(document)
    objects = {row["id"]: row for row in document["objects"]}
    geometry = {
        row["id"]: {
            "x": float(row["x"]),
            "y": float(row["y"]),
            "width": float(row["width"]),
            "height": float(row["height"]),
        }
        for row in document["objects"]
    }
    children: dict[str, list[dict[str, Any]]] = {}
    for row in document["objects"]:
        children.setdefault(str(row["parent_id"] or ""), []).append(row)
    for rows in children.values():
        rows.sort(key=lambda item: (int(item["z_index"]), item["id"]))

    def resolve_parent(parent_id: str, stack: tuple[str, ...]) -> None:
        if parent_id in stack:
            return
        parent = objects.get(parent_id)
        if parent is None:
            return
        parent_geometry = geometry[parent_id]
        layout = parent.get("layout")
        layout = layout if isinstance(layout, Mapping) else {}
        direction = str(
            layout.get("direction")
            or layout.get("mode")
            or layout.get("type")
            or ""
        ).strip().casefold()
        if direction in {"auto_horizontal", "row"}:
            direction = "horizontal"
        elif direction in {"auto_vertical", "column"}:
            direction = "vertical"
        if direction in {"horizontal", "vertical"}:
            left, top, right, bottom = _padding(layout.get("padding", 0.0))
            gap = max(0.0, _number(layout.get("gap", 0.0)))
            align = str(
                layout.get("align")
                or layout.get("cross_alignment")
                or "start"
            ).strip().casefold()
            cursor = (
                parent_geometry["x"] + left
                if direction == "horizontal"
                else parent_geometry["y"] + top
            )
            content_width = max(
                1.0, parent_geometry["width"] - left - right
            )
            content_height = max(
                1.0, parent_geometry["height"] - top - bottom
            )
            for child in children.get(parent_id, []):
                if not bool(child.get("visible", True)):
                    continue
                child_layout = (
                    child["layout"]
                    if isinstance(child.get("layout"), Mapping)
                    else {}
                )
                if str(
                    child_layout.get("positioning")
                    or child_layout.get("position")
                    or ""
                ).casefold() == "absolute":
                    continue
                rect = geometry[child["id"]]
                if direction == "horizontal":
                    rect["x"] = cursor
                    if align == "center":
                        rect["y"] = (
                            parent_geometry["y"]
                            + top
                            + (content_height - rect["height"]) * 0.5
                        )
                    elif align == "end":
                        rect["y"] = (
                            parent_geometry["y"] + top
                            + content_height - rect["height"]
                        )
                    else:
                        rect["y"] = parent_geometry["y"] + top
                    if align == "stretch":
                        rect["height"] = content_height
                    cursor += rect["width"] + gap
                else:
                    rect["y"] = cursor
                    if align == "center":
                        rect["x"] = (
                            parent_geometry["x"]
                            + left
                            + (content_width - rect["width"]) * 0.5
                        )
                    elif align == "end":
                        rect["x"] = (
                            parent_geometry["x"] + left
                            + content_width - rect["width"]
                        )
                    else:
                        rect["x"] = parent_geometry["x"] + left
                    if align == "stretch":
                        rect["width"] = content_width
                    cursor += rect["height"] + gap
        for child in children.get(parent_id, []):
            resolve_parent(child["id"], (*stack, parent_id))

    for root in children.get("", []):
        resolve_parent(root["id"], ())
    return geometry


def linked_motion_binding_ref(
    value: Mapping[str, Any],
    object_id: str,
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    # Read-only: callers holding a canonical document skip the defensive
    # copy, which dominates click latency on large imported files.
    document = normalize_ui_document(value) if normalize else value
    target = document["linked_targets"].get(PAINTER_MOTION_TARGET)
    target = target if isinstance(target, Mapping) else {}
    bindings = target.get("object_bindings")
    bindings = bindings if isinstance(bindings, Mapping) else {}
    raw = bindings.get(str(object_id))
    if isinstance(raw, Mapping):
        return {
            "composition_id": str(raw.get("composition_id") or ""),
            "binding_id": str(raw.get("binding_id") or ""),
            "composition_revision": max(
                0, int(raw.get("composition_revision", 0) or 0)
            ),
        }
    return {
        "composition_id": str(raw or ""),
        "binding_id": "",
        "composition_revision": 0,
    }


def linked_motion_composition_id(
    value: Mapping[str, Any],
    object_id: str,
    *,
    normalize: bool = True,
) -> str:
    return linked_motion_binding_ref(
        value,
        object_id,
        normalize=normalize,
    )["composition_id"]


def linked_motion_binding_id(
    value: Mapping[str, Any],
    object_id: str,
    *,
    normalize: bool = True,
) -> str:
    return linked_motion_binding_ref(
        value,
        object_id,
        normalize=normalize,
    )["binding_id"]


def attach_motion_composition(
    value: Mapping[str, Any],
    object_id: str,
    composition_id: str,
    *,
    binding_id: str = "",
    composition_revision: int = 0,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    linked_targets = copy.deepcopy(document["linked_targets"])
    target = linked_targets.get(PAINTER_MOTION_TARGET)
    target = copy.deepcopy(dict(target)) if isinstance(target, Mapping) else {}
    bindings = target.get("object_bindings")
    bindings = copy.deepcopy(dict(bindings)) if isinstance(bindings, Mapping) else {}
    bindings[str(object_id)] = {
        "composition_id": str(composition_id),
        "binding_id": str(binding_id),
        "composition_revision": max(0, int(composition_revision or 0)),
    }
    target.update(
        {
            "version": PAINTER_MOTION_LINK_VERSION,
            "object_bindings": bindings,
        }
    )
    linked_targets[PAINTER_MOTION_TARGET] = target
    document["linked_targets"] = linked_targets
    document["revision"] = int(document["revision"]) + 1
    return document


def _composition_value(
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
    composition_id: str,
) -> MotionComposition | None:
    value = compositions.get(str(composition_id))
    if isinstance(value, MotionComposition):
        return value
    if isinstance(value, Mapping):
        return MotionComposition.from_dict(value)
    return None


def _binding_for_object(
    composition: MotionComposition,
    object_id: str,
    binding_id: str = "",
) -> UIMotionBinding | None:
    from app.motion_designer.ui_motion_binding import ui_motion_bindings

    rows = ui_motion_bindings(composition)
    if binding_id:
        return next((row for row in rows if row.id == binding_id), None)
    return next(
        (row for row in rows if row.source_object_id == str(object_id)),
        None,
    )


def inspect_motion_binding_links(
    value: Mapping[str, Any],
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    # Read-only: callers holding a canonical document skip the defensive
    # copy, which dominates click latency on large imported files.
    document = normalize_ui_document(value) if normalize else value
    objects_by_id = {row["id"]: row for row in document["objects"]}
    object_ids = set(objects_by_id)
    target = document["linked_targets"].get(PAINTER_MOTION_TARGET)
    target = target if isinstance(target, Mapping) else {}
    raw_bindings = target.get("object_bindings")
    raw_bindings = raw_bindings if isinstance(raw_bindings, Mapping) else {}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    resolved_binding_ids: set[str] = set()
    composition_to_binding: dict[str, str] = {}
    for object_id in sorted(str(key) for key in raw_bindings):
        ref = linked_motion_binding_ref(document, object_id, normalize=False)
        composition = _composition_value(
            compositions, ref["composition_id"]
        )
        binding = (
            _binding_for_object(
                composition,
                object_id,
                ref["binding_id"],
            )
            if composition is not None
            else None
        )
        status = "ok"
        if object_id not in object_ids:
            status = "orphan_object"
            errors.append(f"orphan_motion_object:{object_id}")
        elif composition is None:
            status = "missing_composition"
            errors.append(
                f"missing_motion_composition:{object_id}:{ref['composition_id']}"
            )
        elif binding is None:
            status = "missing_binding"
            errors.append(
                f"missing_motion_binding:{object_id}:{ref['binding_id']}"
            )
        elif not ref["binding_id"]:
            status = "legacy_link"
            warnings.append(f"legacy_motion_link:{object_id}")
        elif (
            ref["composition_revision"]
            and ref["composition_revision"] != composition.revision
        ):
            status = "stale_revision"
            warnings.append(
                f"stale_motion_revision:{object_id}:"
                f"{ref['composition_revision']}:{composition.revision}"
            )
        rows.append(
            {
                "object_id": object_id,
                "object_name": str(
                    (objects_by_id.get(object_id) or {}).get("name")
                    or object_id
                ),
                **ref,
                "resolved_binding_id": binding.id if binding else "",
                "current_composition_revision": (
                    int(composition.revision) if composition else 0
                ),
                "status": status,
            }
        )
        if binding is not None:
            resolved_binding_ids.add(binding.id)
            composition_to_binding[composition.id] = binding.id
    for interaction in document["interactions"]:
        if interaction["action"] != "play_animation":
            continue
        interaction_id = interaction["id"]
        motion_ref = str(interaction.get("motion_clip_id") or "")
        if not motion_ref:
            errors.append(
                f"missing_interaction_motion_binding:{interaction_id}"
            )
            continue
        if motion_ref in composition_to_binding:
            warnings.append(
                f"legacy_interaction_motion_link:{interaction_id}:{motion_ref}"
            )
            continue
        if motion_ref not in resolved_binding_ids:
            errors.append(
                f"missing_interaction_motion_binding:"
                f"{interaction_id}:{motion_ref}"
            )
            continue
        source_ref = linked_motion_binding_ref(
            document, interaction["source_object_id"]
        )
        if source_ref["binding_id"] and source_ref["binding_id"] != motion_ref:
            errors.append(
                f"interaction_motion_binding_mismatch:"
                f"{interaction_id}:{source_ref['binding_id']}:{motion_ref}"
            )
    return {
        "schema": "tigerstudio.painter.ui.motion_links.v2",
        "ok": not errors,
        "document_id": document["document_id"],
        "document_revision": int(document["revision"]),
        "selected_object_id": str(
            document["selection"].get("object_id") or ""
        ),
        "link_version": int(target.get("version", 1) or 1),
        "links": rows,
        "errors": errors,
        "warnings": warnings,
    }


def migrate_motion_binding_links(
    value: Mapping[str, Any],
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target = document["linked_targets"].get(PAINTER_MOTION_TARGET)
    target = copy.deepcopy(dict(target)) if isinstance(target, Mapping) else {}
    raw_bindings = target.get("object_bindings")
    raw_bindings = (
        copy.deepcopy(dict(raw_bindings))
        if isinstance(raw_bindings, Mapping)
        else {}
    )
    migrated = 0
    unresolved: list[str] = []
    binding_refs_by_object: dict[str, tuple[str, str]] = {}
    for object_id, raw in list(raw_bindings.items()):
        ref = linked_motion_binding_ref(document, str(object_id))
        composition = _composition_value(
            compositions, ref["composition_id"]
        )
        binding = (
            _binding_for_object(
                composition,
                str(object_id),
                ref["binding_id"],
            )
            if composition is not None
            else None
        )
        if composition is None or binding is None:
            unresolved.append(str(object_id))
            continue
        normalized = {
            "composition_id": composition.id,
            "binding_id": binding.id,
            "composition_revision": int(composition.revision),
        }
        if raw != normalized:
            migrated += 1
        raw_bindings[str(object_id)] = normalized
        binding_refs_by_object[str(object_id)] = (
            composition.id,
            binding.id,
        )
    target.update(
        {
            "version": PAINTER_MOTION_LINK_VERSION,
            "object_bindings": raw_bindings,
        }
    )
    document["linked_targets"][PAINTER_MOTION_TARGET] = target
    interaction_migrations = 0
    for interaction in document["interactions"]:
        legacy = str(interaction.get("motion_clip_id") or "")
        source_composition_id, source_binding_id = (
            binding_refs_by_object.get(
                str(interaction.get("source_object_id") or ""),
                ("", ""),
            )
        )
        if legacy and legacy == source_composition_id and source_binding_id:
            interaction["motion_clip_id"] = source_binding_id
            interaction_migrations += 1
    if migrated or interaction_migrations:
        document["revision"] = int(document["revision"]) + 1
    report = inspect_motion_binding_links(document, compositions)
    report.update(
        {
            "migrated_link_count": migrated,
            "migrated_interaction_count": interaction_migrations,
            "unresolved_object_ids": sorted(unresolved),
        }
    )
    return document, report


def relink_motion_binding(
    value: Mapping[str, Any],
    object_id: str,
    composition_id: str,
    binding_id: str,
    compositions: Mapping[str, MotionComposition | Mapping[str, Any]],
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    if str(object_id) not in {row["id"] for row in document["objects"]}:
        raise ValueError(f"Painter UI object not found: {object_id}")
    composition = _composition_value(compositions, composition_id)
    if composition is None:
        raise ValueError(f"Motion composition not found: {composition_id}")
    binding = _binding_for_object(composition, object_id, binding_id)
    if binding is None or binding.source_object_id != str(object_id):
        raise ValueError(
            f"Motion binding does not belong to object: {binding_id}"
        )
    return attach_motion_composition(
        document,
        object_id,
        composition.id,
        binding_id=binding.id,
        composition_revision=composition.revision,
    )


def detach_motion_binding(
    value: Mapping[str, Any],
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target = document["linked_targets"].get(PAINTER_MOTION_TARGET)
    target = copy.deepcopy(dict(target)) if isinstance(target, Mapping) else {}
    bindings = target.get("object_bindings")
    bindings = (
        copy.deepcopy(dict(bindings)) if isinstance(bindings, Mapping) else {}
    )
    ref = linked_motion_binding_ref(document, object_id)
    removed = bindings.pop(str(object_id), None)
    if removed is None:
        return document, {"detached": False, "object_id": str(object_id)}
    target["version"] = PAINTER_MOTION_LINK_VERSION
    target["object_bindings"] = bindings
    document["linked_targets"][PAINTER_MOTION_TARGET] = target
    cleared_interactions: list[str] = []
    if ref["binding_id"]:
        for interaction in document["interactions"]:
            if interaction.get("motion_clip_id") == ref["binding_id"]:
                interaction["motion_clip_id"] = ""
                cleared_interactions.append(interaction["id"])
    document["revision"] = int(document["revision"]) + 1
    return document, {
        "detached": True,
        "object_id": str(object_id),
        **ref,
        "cleared_interaction_ids": cleared_interactions,
    }


def _object_subtree(
    document: Mapping[str, Any],
    root_object_id: str,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in document["objects"]]
    selected = {str(root_object_id)}
    changed = True
    while changed:
        changed = False
        for row in rows:
            if row["parent_id"] in selected and row["id"] not in selected:
                selected.add(row["id"])
                changed = True
    return [row for row in rows if row["id"] in selected]


def _layer_type(kind: str) -> str:
    if kind in {"frame", "group"}:
        return "group"
    if kind == "text":
        return "text"
    if kind == "image":
        return "image"
    return "shape"


def _source_ref(row: Mapping[str, Any], geometry: Mapping[str, float]) -> SourceRef:
    kind = str(row["kind"])
    style = dict(row.get("style") or {})
    content = dict(row.get("content") or {})
    params: dict[str, Any] = {
        "width": float(geometry["width"]),
        "height": float(geometry["height"]),
        "fill": str(style.get("fill") or "#506884"),
        "stroke": str(style.get("stroke") or "#93A3B8"),
        "stroke_width": float(style.get("stroke_width", 1.0) or 0.0),
        "radius": float(style.get("radius", 0.0) or 0.0),
    }
    if kind == "ellipse":
        params["shape"] = "ellipse"
    else:
        params["shape"] = "rectangle"
    if kind in {"text", "button"}:
        params.update(
            {
                "text": str(content.get("text") or row["name"]),
                "text_color": str(style.get("text_color") or "#F2F5F9"),
                "font_size": float(style.get("font_size", 16.0) or 16.0),
                "font_axes": dict(style.get("font_axes") or {}),
            }
        )
    uri = str(content.get("source_path") or content.get("path") or "")
    return SourceRef(kind=_layer_type(kind), uri=uri, params=params)


def _sync_source_ref(
    layer: MotionLayer,
    row: Mapping[str, Any],
    geometry: Mapping[str, float],
) -> None:
    updated = _source_ref(row, geometry)
    previous = layer.source
    params = dict(updated.params)
    for name, value in dict(previous.params or {}).items():
        if isinstance(value, Mapping) and (
            "keyframes" in value or "expression" in value
        ):
            animated = copy.deepcopy(dict(value))
            if "default" in animated and name in params:
                animated["default"] = params[name]
            params[name] = animated
    layer.source = SourceRef(
        kind=updated.kind,
        uri=updated.uri or previous.uri,
        params=params,
    )


def _rebase_position(layer: MotionLayer, center: list[float]) -> None:
    metadata = layer.metadata.get("painter_ui_source")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    old = metadata.get("layout_center")
    if isinstance(old, (list, tuple)) and len(old) >= 2:
        dx = float(center[0]) - float(old[0])
        dy = float(center[1]) - float(old[1])
        default = list(layer.transform.position.default or [0.0, 0.0])
        layer.transform.position.default = [
            float(default[0]) + dx,
            float(default[1]) + dy,
        ]
        for keyframe in layer.transform.position.keyframes:
            value = list(keyframe.value or [0.0, 0.0])
            keyframe.value = [
                float(value[0]) + dx,
                float(value[1]) + dy,
            ]
    else:
        layer.transform.position.default = list(center)


def _rebase_scalar_property(
    layer: MotionLayer,
    property_name: str,
    base_value: float,
    metadata_name: str,
    *,
    clamp: tuple[float, float] | None = None,
) -> None:
    metadata = layer.metadata.get("painter_ui_source")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    prop = getattr(layer.transform, property_name)
    old = metadata.get(metadata_name)
    if old is None:
        prop.default = float(base_value)
        return
    delta = float(base_value) - float(old)

    def adjusted(value: Any) -> float:
        result = float(value or 0.0) + delta
        if clamp is not None:
            result = max(clamp[0], min(clamp[1], result))
        return result

    prop.default = adjusted(prop.default)
    for keyframe in prop.keyframes:
        keyframe.value = adjusted(keyframe.value)


def create_or_sync_ui_motion_composition(
    value: Mapping[str, Any],
    object_id: str,
    existing: MotionComposition | Mapping[str, Any] | None = None,
    *,
    duration_ms: int = 600,
) -> MotionComposition:
    document = normalize_ui_document(value)
    row_by_id = {row["id"]: row for row in document["objects"]}
    root = row_by_id.get(str(object_id))
    if root is None:
        raise ValueError(f"Painter UI object not found: {object_id}")
    artboard = next(
        row for row in document["artboards"]
        if row["id"] == root["artboard_id"]
    )
    if isinstance(existing, MotionComposition):
        composition = existing
    elif isinstance(existing, Mapping):
        composition = MotionComposition.from_dict(existing)
    else:
        composition = MotionComposition(
            name=f"{root['name']} UI Motion",
            width=int(artboard["width"]),
            height=int(artboard["height"]),
            duration_ms=max(1, int(duration_ms)),
        )
    composition.width = int(artboard["width"])
    composition.height = int(artboard["height"])
    composition.metadata["painter_ui_source"] = {
        "document_id": document["document_id"],
        "object_id": root["id"],
        "component_id": root["component_id"],
        "artboard_id": artboard["id"],
        "layout_policy": "resolve_then_rebase_motion_offsets",
    }

    geometry = resolved_ui_geometry(document)
    existing_layers = {layer.id: layer for layer in composition.layers}
    mapped_ids: list[str] = []
    for row in _object_subtree(document, root["id"]):
        rect = geometry[row["id"]]
        center = [
            float(rect["x"]) + float(rect["width"]) * 0.5,
            float(rect["y"]) + float(rect["height"]) * 0.5,
        ]
        layer = existing_layers.get(row["id"])
        if layer is None:
            layer = MotionLayer(
                id=row["id"],
                name=row["name"],
                layer_type=_layer_type(row["kind"]),
                source=_source_ref(row, rect),
                out_ms=composition.duration_ms,
            )
            composition.layers.append(layer)
        else:
            layer.name = row["name"]
            layer.layer_type = _layer_type(row["kind"])
            _sync_source_ref(layer, row, rect)
            layer.out_ms = max(layer.in_ms + 1, composition.duration_ms)
        _rebase_position(layer, center)
        _rebase_scalar_property(
            layer,
            "rotation",
            float(row["rotation"]),
            "layout_rotation",
        )
        _rebase_scalar_property(
            layer,
            "opacity",
            float(row["opacity"]),
            "layout_opacity",
            clamp=(0.0, 1.0),
        )
        layer.metadata["painter_ui_source"] = {
            "document_id": document["document_id"],
            "object_id": row["id"],
            "component_id": row["component_id"],
            "parent_object_id": row["parent_id"],
            "artboard_id": row["artboard_id"],
            "layout_center": center,
            "layout_rect": dict(rect),
            "layout_rotation": float(row["rotation"]),
            "layout_opacity": float(row["opacity"]),
        }
        if row["kind"] == "button" and button_component(layer) is None:
            create_button_component(layer)
        mapped_ids.append(layer.id)

    composition.layers = [
        layer
        for layer in composition.layers
        if (
            not isinstance(layer.metadata.get("painter_ui_source"), Mapping)
            or layer.id in mapped_ids
        )
    ]
    root_layer = next(layer for layer in composition.layers if layer.id == root["id"])
    upsert_ui_motion_binding(
        composition,
        UIMotionBinding(
            id=f"ui-binding-{root['id']}",
            source_document_id=document["document_id"],
            source_object_id=root["id"],
            source_component_id=root["component_id"],
            host_layer_id=root_layer.id,
            layer_ids=mapped_ids,
            scope="transition" if root["kind"] == "button" else "entrance",
            trigger="pointer_enter" if root["kind"] == "button" else "",
            from_state="normal" if root["kind"] == "button" else "",
            to_state="hover" if root["kind"] == "button" else "",
            animation_name=f"UI_{root['id']}_Motion",
            autoplay=root["kind"] != "button",
            delivery_request={
                "web": "native_preferred",
                "app": "native_preferred",
                "umg": "native_preferred",
            },
        ).to_dict(),
    )
    return composition


def motion_preview_states(
    composition: MotionComposition,
    time_ms: int,
) -> dict[str, dict[str, Any]]:
    from app.motion_designer.evaluator import evaluate_composition

    return {
        state.id: {
            "position": list(state.position),
            "scale": list(state.scale),
            "rotation": float(state.rotation),
            "opacity": float(state.opacity),
        }
        for state in evaluate_composition(
            composition,
            max(0, int(time_ms)) % max(1, int(composition.duration_ms)),
        )
    }


__all__ = [
    "PAINTER_MOTION_LINK_VERSION",
    "PAINTER_MOTION_TARGET",
    "attach_motion_composition",
    "create_or_sync_ui_motion_composition",
    "detach_motion_binding",
    "inspect_motion_binding_links",
    "linked_motion_binding_id",
    "linked_motion_binding_ref",
    "linked_motion_composition_id",
    "migrate_motion_binding_links",
    "motion_preview_states",
    "relink_motion_binding",
    "resolved_ui_geometry",
]
