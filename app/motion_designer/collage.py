"""Provider-neutral editable collage contract for Motion Designer."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from math import hypot
from pathlib import Path
from random import Random
from typing import Any

from .commands import find_layer
from .schema import (
    AnimatedProperty,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    MotionMaskRef,
    MotionTransform,
    SourceRef,
    new_motion_id,
)
from .vector_shapes import VectorPath, VectorPoint


COLLAGE_CONTRACT = "tigerstudio.motion.collage.v1"
COLLAGE_METADATA_KEY = "collage_boards"
COLLAGE_EDGE_MODES = ("smart", "polygon", "torn", "feather", "fiber")
COLLAGE_ATTACHMENTS = ("none", "glue", "tape", "staple", "pin", "fold")
COLLAGE_LAYOUTS = ("manual", "editorial", "scatter", "education", "luxury")


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: Any, minimum: float, maximum: float, default: float) -> float:
    return max(minimum, min(maximum, _number(value, default)))


def _boards(composition: MotionComposition) -> list[dict[str, Any]]:
    rows = composition.metadata.get(COLLAGE_METADATA_KEY)
    if not isinstance(rows, list):
        rows = []
        composition.metadata[COLLAGE_METADATA_KEY] = rows
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            normalized.append(dict(row))
    composition.metadata[COLLAGE_METADATA_KEY] = normalized
    return normalized


def collage_boards(composition: MotionComposition) -> list[dict[str, Any]]:
    """Return detached board payloads suitable for actions and persistence."""
    rows = composition.metadata.get(COLLAGE_METADATA_KEY)
    if not isinstance(rows, list):
        return []
    return deepcopy([
        dict(row)
        for row in rows
        if isinstance(row, Mapping)
    ])


def find_collage_board(
    composition: MotionComposition,
    board_id: str,
) -> dict[str, Any]:
    for board in _boards(composition):
        if str(board.get("id") or "") == str(board_id):
            return board
    raise ValueError(f"collage board not found: {board_id}")


def find_collage_item(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    board = find_collage_board(composition, board_id)
    for item in board.get("items", []):
        if isinstance(item, Mapping) and str(item.get("id") or "") == str(item_id):
            return board, item
    raise ValueError(f"collage item not found: {item_id}")


def _source_fingerprint(layer: MotionLayer) -> dict[str, Any]:
    uri = str(layer.source.uri or "")
    path = Path(uri).expanduser() if uri else None
    return {
        "kind": str(layer.source.kind),
        "uri": uri,
        "revision": str(path.stat().st_mtime_ns) if path and path.is_file() else "",
    }


def _new_item(layer: MotionLayer, *, z_index: int) -> dict[str, Any]:
    item_id = new_motion_id("collage_item")
    edge = {
        "mode": "smart",
        "roughness": 0.0,
        "feather": 0.0,
        "seed": 17,
        "points": [],
    }
    attachment = {
        "kind": "none",
        "color": "#D8D0B099",
        "strength": 0.35,
        "angle": 0.0,
    }
    return {
        "id": item_id,
        "layer_id": layer.id,
        "z_index": int(z_index),
        "edge": edge,
        "attachment": attachment,
        "source": _source_fingerprint(layer),
        "painter_link": {},
    }


def create_collage_board(
    composition: MotionComposition,
    layer_ids: Sequence[str],
    *,
    name: str = "Collage Board",
    layout: str = "manual",
    seed: int = 17,
) -> dict[str, Any]:
    layout_id = str(layout or "manual").lower()
    if layout_id not in COLLAGE_LAYOUTS:
        raise ValueError(f"unsupported collage layout: {layout}")
    unique_ids = list(dict.fromkeys(str(value) for value in layer_ids if str(value)))
    if not unique_ids:
        raise ValueError("collage board requires at least one layer")
    layers = [find_layer(composition, layer_id) for layer_id in unique_ids]
    board_id = new_motion_id("collage")
    board = {
        "schema": COLLAGE_CONTRACT,
        "id": board_id,
        "name": str(name or "Collage Board"),
        "layout": layout_id,
        "seed": max(0, int(seed)),
        "items": [_new_item(layer, z_index=index) for index, layer in enumerate(layers)],
        "painter_document_id": "",
    }
    _boards(composition).append(board)
    for item, layer in zip(board["items"], layers):
        layer.metadata["collage_item"] = {
            "schema": COLLAGE_CONTRACT,
            "board_id": board_id,
            "item_id": item["id"],
        }
    apply_collage_layout(composition, board_id)
    return deepcopy(board)


def add_collage_item(
    composition: MotionComposition,
    board_id: str,
    layer_id: str,
) -> dict[str, Any]:
    board = find_collage_board(composition, board_id)
    layer = find_layer(composition, layer_id)
    for item in board.get("items", []):
        if str(item.get("layer_id") or "") == layer.id:
            raise ValueError(f"layer already belongs to collage board: {layer.id}")
    item = _new_item(layer, z_index=len(board.get("items", [])))
    board.setdefault("items", []).append(item)
    layer.metadata["collage_item"] = {
        "schema": COLLAGE_CONTRACT,
        "board_id": board_id,
        "item_id": item["id"],
    }
    return deepcopy(item)


def update_collage_item(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    _board, item = find_collage_item(composition, board_id, item_id)
    allowed = {"label", "locked", "notes"}
    for key in allowed:
        if key in changes:
            item[key] = deepcopy(changes[key])
    if "layer_id" in changes and str(changes["layer_id"]) != str(item["layer_id"]):
        replacement = find_layer(composition, str(changes["layer_id"]))
        item["layer_id"] = replacement.id
        item["source"] = _source_fingerprint(replacement)
        replacement.metadata["collage_item"] = {
            "schema": COLLAGE_CONTRACT,
            "board_id": board_id,
            "item_id": item_id,
        }
    return deepcopy(item)


def reorder_collage_item(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    z_index: int,
) -> dict[str, Any]:
    board, item = find_collage_item(composition, board_id, item_id)
    rows = list(board.get("items", []))
    rows.remove(item)
    target = max(0, min(len(rows), int(z_index)))
    rows.insert(target, item)
    for index, row in enumerate(rows):
        row["z_index"] = index
    board["items"] = rows

    board_layer_ids = [str(row["layer_id"]) for row in rows]
    board_id_set = set(board_layer_ids)
    units: dict[str, list[MotionLayer]] = {
        layer_id: []
        for layer_id in board_layer_ids
    }
    for layer in composition.layers:
        if layer.id in board_id_set:
            units[layer.id].append(layer)
        elif layer.parent_id in board_id_set:
            units[layer.parent_id].append(layer)
    moved_ids = {
        layer.id
        for unit in units.values()
        for layer in unit
    }
    board_layers = [
        layer
        for layer_id in board_layer_ids
        for layer in units[layer_id]
    ]
    indices = [
        index for index, layer in enumerate(composition.layers)
        if layer.id in moved_ids
    ]
    if indices:
        first = min(indices)
        composition.layers = [
            layer for layer in composition.layers if layer.id not in moved_ids
        ]
        composition.layers[first:first] = board_layers
    return deepcopy(item)


def _jagged_rectangle(
    width: float,
    height: float,
    *,
    roughness: float,
    seed: int,
) -> VectorPath:
    rng = Random(int(seed))
    amount = max(0.0, min(1.0, float(roughness)))
    step = max(8.0, min(width, height) / 14.0)
    points: list[tuple[float, float]] = []

    def add_edge(
        start: tuple[float, float],
        end: tuple[float, float],
        normal: tuple[float, float],
    ) -> None:
        distance = hypot(end[0] - start[0], end[1] - start[1])
        count = max(2, int(distance / step))
        for index in range(count):
            ratio = index / count
            jitter = rng.uniform(-1.0, 1.0) * step * 0.34 * amount
            points.append((
                start[0] + (end[0] - start[0]) * ratio + normal[0] * jitter,
                start[1] + (end[1] - start[1]) * ratio + normal[1] * jitter,
            ))

    add_edge((0.0, 0.0), (width, 0.0), (0.0, 1.0))
    add_edge((width, 0.0), (width, height), (-1.0, 0.0))
    add_edge((width, height), (0.0, height), (0.0, -1.0))
    add_edge((0.0, height), (0.0, 0.0), (1.0, 0.0))
    return VectorPath(
        points=[VectorPoint((float(x), float(y))) for x, y in points],
        closed=True,
    )


def _edge_mask(layer: MotionLayer) -> MotionMaskRef | None:
    return next(
        (
            mask for mask in layer.masks
            if bool(mask.metadata.get("collage_edge_mask"))
        ),
        None,
    )


def set_collage_edge(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    *,
    mode: str,
    roughness: float = 0.35,
    feather: float = 0.0,
    seed: int = 17,
    points: Sequence[Sequence[float]] | None = None,
) -> dict[str, Any]:
    _board, item = find_collage_item(composition, board_id, item_id)
    mode_id = str(mode or "smart").lower()
    if mode_id not in COLLAGE_EDGE_MODES:
        raise ValueError(f"unsupported collage edge mode: {mode}")
    layer = find_layer(composition, str(item["layer_id"]))
    width = max(1.0, _number(layer.source.params.get("width"), composition.width))
    height = max(1.0, _number(layer.source.params.get("height"), composition.height))
    normalized_points = [
        [float(point[0]), float(point[1])]
        for point in (points or ())
        if len(point) >= 2
    ]
    edge = {
        "mode": mode_id,
        "roughness": _clamp(roughness, 0.0, 1.0, 0.35),
        "feather": _clamp(feather, 0.0, 64.0, 0.0),
        "seed": max(0, int(seed)),
        "points": normalized_points,
    }
    item["edge"] = edge

    existing = _edge_mask(layer)
    if mode_id == "smart":
        if existing is not None:
            layer.masks.remove(existing)
    else:
        if mode_id == "polygon" and len(normalized_points) >= 3:
            path = VectorPath(
                points=[VectorPoint((row[0], row[1])) for row in normalized_points],
                closed=True,
            )
        else:
            visual_roughness = edge["roughness"]
            if mode_id == "feather":
                visual_roughness *= 0.2
            elif mode_id == "fiber":
                visual_roughness = max(visual_roughness, 0.62)
            elif mode_id == "torn":
                visual_roughness = max(visual_roughness, 0.78)
            path = _jagged_rectangle(
                width,
                height,
                roughness=visual_roughness,
                seed=edge["seed"],
            )
        mask = MotionMaskRef(
            kind="path",
            mode="add",
            params={
                "path": AnimatedProperty(value_type="path", default=path.to_dict()),
                "feather": AnimatedProperty(
                    default=max(
                        edge["feather"],
                        4.0 if mode_id == "feather" else 1.2 if mode_id == "fiber" else 0.0,
                    ),
                ),
                "expansion": AnimatedProperty(default=0.0),
                "opacity": AnimatedProperty(default=1.0),
            },
            metadata={
                "collage_edge_mask": True,
                "board_id": board_id,
                "item_id": item_id,
                "mode": mode_id,
            },
        )
        if existing is None:
            layer.masks.append(mask)
        else:
            mask.id = existing.id
            layer.masks[layer.masks.index(existing)] = mask
    return deepcopy(edge)


def _remove_attachment_layers(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
) -> None:
    composition.layers = [
        layer
        for layer in composition.layers
        if not (
            layer.metadata.get("collage_attachment")
            and str(layer.metadata.get("collage_board_id") or "") == board_id
            and str(layer.metadata.get("collage_item_id") or "") == item_id
        )
    ]


def _attachment_layer(
    source: MotionLayer,
    *,
    board_id: str,
    item_id: str,
    kind: str,
    width: float,
    height: float,
    color: str,
    angle: float,
) -> MotionLayer:
    primitive = "ellipse" if kind == "pin" else "rectangle"
    is_glue = kind == "glue"
    return MotionLayer(
        name=f"{source.name} / {kind.title()}",
        layer_type="shape",
        parent_id=source.id,
        source=SourceRef(
            kind="shape",
            params={
                "primitive": primitive,
                "width": width,
                "height": height,
                "radius": min(width, height) * 0.5 if primitive == "ellipse" else 2.0,
                "fill": "#55000000" if is_glue else color,
                "stroke": "#00000000" if is_glue else "#33000000",
                "stroke_width": 1.0,
            },
        ),
        transform=MotionTransform.from_dict({
            "position": {
                "value_type": "vector2",
                "default": [8.0, 10.0] if is_glue else [0.0, -max(20.0, height * 1.8)],
            },
            "scale": {"value_type": "vector2", "default": [1.0, 1.0]},
            "rotation": {"default": float(angle)},
            "opacity": {"default": 1.0},
            "anchor": {"value_type": "vector2", "default": [0.5, 0.5]},
        }),
        in_ms=source.in_ms,
        out_ms=source.out_ms,
        blend_mode="multiply" if is_glue else "normal",
        effects=(
            [
                MotionEffectRef(
                    kind="gaussian_blur",
                    params={"radius": AnimatedProperty(default=8.0)},
                ),
            ]
            if is_glue
            else []
        ),
        metadata={
            "collage_attachment": True,
            "collage_attachment_kind": kind,
            "collage_board_id": board_id,
            "collage_item_id": item_id,
        },
    )


def set_collage_attachment(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    *,
    kind: str,
    color: str = "#D8D0B099",
    strength: float = 0.35,
    angle: float = 0.0,
) -> dict[str, Any]:
    _board, item = find_collage_item(composition, board_id, item_id)
    kind_id = str(kind or "none").lower()
    if kind_id not in COLLAGE_ATTACHMENTS:
        raise ValueError(f"unsupported collage attachment: {kind}")
    source = find_layer(composition, str(item["layer_id"]))
    amount = _clamp(strength, 0.0, 1.0, 0.35)
    attachment = {
        "kind": kind_id,
        "color": str(color or "#D8D0B099"),
        "strength": amount,
        "angle": _clamp(angle, -180.0, 180.0, 0.0),
    }
    item["attachment"] = attachment
    _remove_attachment_layers(composition, board_id, item_id)
    source.effects = [
        effect
        for effect in source.effects
        if not bool(effect.metadata.get("collage_attachment"))
    ]
    if kind_id == "fold":
        source.effects.append(
            MotionEffectRef(
                kind="paper_fold",
                params={
                    "strength": AnimatedProperty(default=amount),
                    "angle": AnimatedProperty(default=attachment["angle"]),
                    "width": AnimatedProperty(
                        default=max(14.0, _number(source.source.params.get("width"), 320.0) * 0.11),
                    ),
                },
                metadata={
                    "collage_attachment": True,
                    "collage_board_id": board_id,
                    "collage_item_id": item_id,
                },
            ),
        )
    elif kind_id != "none":
        source_width = max(40.0, _number(source.source.params.get("width"), 320.0))
        source_height = max(40.0, _number(source.source.params.get("height"), 180.0))
        dimensions = {
            "glue": (source_width, source_height),
            "tape": (min(110.0, source_width * 0.3), 26.0),
            "staple": (28.0, 4.0),
            "pin": (18.0, 18.0),
        }[kind_id]
        decoration = _attachment_layer(
            source,
            board_id=board_id,
            item_id=item_id,
            kind=kind_id,
            width=dimensions[0],
            height=dimensions[1],
            color=attachment["color"],
            angle=attachment["angle"],
        )
        source_index = composition.layers.index(source)
        composition.layers.insert(
            source_index if kind_id == "glue" else source_index + 1,
            decoration,
        )
    return deepcopy(attachment)


def set_collage_scan_cleanup(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    *,
    white_balance: float = 0.8,
    paper_remove: float = 0.0,
    ink_preserve: float = 0.75,
    threshold: float = 0.72,
) -> dict[str, Any]:
    _board, item = find_collage_item(composition, board_id, item_id)
    layer = find_layer(composition, str(item["layer_id"]))
    settings = {
        "white_balance": _clamp(white_balance, 0.0, 1.0, 0.8),
        "paper_remove": _clamp(paper_remove, 0.0, 1.0, 0.0),
        "ink_preserve": _clamp(ink_preserve, 0.0, 1.0, 0.75),
        "threshold": _clamp(threshold, 0.05, 0.98, 0.72),
    }
    previous = next(
        (
            effect for effect in layer.effects
            if effect.kind == "scan_cleanup"
            and bool(effect.metadata.get("collage_scan_cleanup"))
        ),
        None,
    )
    effect = MotionEffectRef(
        kind="scan_cleanup",
        params={
            key: AnimatedProperty(default=value)
            for key, value in settings.items()
        },
        metadata={
            "collage_scan_cleanup": True,
            "collage_board_id": board_id,
            "collage_item_id": item_id,
        },
    )
    if previous is None:
        layer.effects.append(effect)
    else:
        effect.id = previous.id
        layer.effects[layer.effects.index(previous)] = effect
    item["scan_cleanup"] = settings
    return deepcopy(settings)


def apply_collage_layout(
    composition: MotionComposition,
    board_id: str,
) -> dict[str, Any]:
    board = find_collage_board(composition, board_id)
    layout = str(board.get("layout") or "manual")
    if layout == "manual":
        return deepcopy(board)
    rng = Random(int(board.get("seed", 17) or 17))
    items = list(board.get("items", []))
    columns = max(1, min(4, round(len(items) ** 0.5)))
    spacing_x = composition.width / (columns + 1)
    rows = max(1, (len(items) + columns - 1) // columns)
    spacing_y = composition.height / (rows + 1)
    for index, item in enumerate(items):
        layer = find_layer(composition, str(item["layer_id"]))
        column = index % columns
        row = index // columns
        x = spacing_x * (column + 1)
        y = spacing_y * (row + 1)
        rotation = 0.0
        if layout in {"scatter", "editorial"}:
            x += rng.uniform(-0.12, 0.12) * spacing_x
            y += rng.uniform(-0.12, 0.12) * spacing_y
            rotation = rng.uniform(-8.0, 8.0)
        elif layout == "education":
            rotation = (-2.0 if index % 2 else 2.0)
        elif layout == "luxury":
            rotation = rng.uniform(-1.0, 1.0)
        layer.transform.position.default = [x, y]
        layer.transform.rotation.default = rotation
    return deepcopy(board)


def replace_collage_item_source(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Replace media while preserving layer, pivot, parent, timing and item IDs."""
    _board, item = find_collage_item(composition, board_id, item_id)
    layer = find_layer(composition, str(item["layer_id"]))
    preserved = {
        "layer_id": layer.id,
        "parent_id": layer.parent_id,
        "in_ms": layer.in_ms,
        "out_ms": layer.out_ms,
        "source_in_ms": layer.source_in_ms,
        "time_scale": layer.time_scale,
        "reverse": layer.reverse,
        "transform": layer.transform.to_dict(),
    }
    layer.source = SourceRef.from_dict(source)
    layer.layer_type = str(source.get("layer_type") or layer.layer_type)
    item["source"] = _source_fingerprint(layer)
    return {"item": deepcopy(item), "preserved": preserved}


def set_collage_painter_link(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
    *,
    document_id: str,
    object_id: str,
    revision: int = 1,
) -> dict[str, Any]:
    board, item = find_collage_item(composition, board_id, item_id)
    link = {
        "schema": "tigerstudio.motion.collage.painter_link.v1",
        "document_id": str(document_id or ""),
        "object_id": str(object_id or ""),
        "motion_layer_id": str(item["layer_id"]),
        "revision": max(1, int(revision)),
    }
    if not link["document_id"] or not link["object_id"]:
        raise ValueError("Painter link requires document_id and object_id")
    item["painter_link"] = link
    board["painter_document_id"] = link["document_id"]
    return deepcopy(link)


def collage_painter_payload(
    composition: MotionComposition,
    board_id: str,
    item_id: str,
) -> dict[str, Any]:
    _board, item = find_collage_item(composition, board_id, item_id)
    layer = find_layer(composition, str(item["layer_id"]))
    return {
        "schema": "tigerstudio.motion.collage.painter_handoff.v1",
        "board_id": board_id,
        "item_id": item_id,
        "motion_layer_id": layer.id,
        "name": layer.name,
        "source": layer.source.to_dict(),
        "edge": deepcopy(item.get("edge", {})),
        "attachment": deepcopy(item.get("attachment", {})),
        "painter_link": deepcopy(item.get("painter_link", {})),
    }


def preflight_collage(
    composition: MotionComposition,
    board_id: str,
) -> dict[str, Any]:
    board = find_collage_board(composition, board_id)
    layer_ids = {layer.id for layer in composition.layers}
    issues: list[str] = []
    item_ids: set[str] = set()
    painter_keys: set[tuple[str, str]] = set()
    for item in board.get("items", []):
        item_id = str(item.get("id") or "")
        layer_id = str(item.get("layer_id") or "")
        if not item_id:
            issues.append("collage_item_missing_id")
        elif item_id in item_ids:
            issues.append(f"duplicate_collage_item_id:{item_id}")
        item_ids.add(item_id)
        if layer_id not in layer_ids:
            issues.append(f"missing_collage_layer:{layer_id}")
        link = item.get("painter_link")
        if isinstance(link, Mapping) and link:
            key = (str(link.get("document_id") or ""), str(link.get("object_id") or ""))
            if not all(key):
                issues.append(f"incomplete_painter_link:{item_id}")
            elif key in painter_keys:
                issues.append(f"duplicate_painter_object_link:{key[1]}")
            painter_keys.add(key)
            if str(link.get("motion_layer_id") or "") != layer_id:
                issues.append(f"painter_layer_id_mismatch:{item_id}")
    return {
        "schema": "tigerstudio.motion.collage.preflight.v1",
        "ok": not issues,
        "board_id": board_id,
        "item_count": len(board.get("items", [])),
        "issues": sorted(set(issues)),
        "preview_disposition": "native_editable",
        "umg_disposition": "deterministic_bake",
        "umg_reason": "motion_feature_requires_bake:collage_item",
    }


__all__ = [
    "COLLAGE_ATTACHMENTS",
    "COLLAGE_CONTRACT",
    "COLLAGE_EDGE_MODES",
    "COLLAGE_LAYOUTS",
    "COLLAGE_METADATA_KEY",
    "add_collage_item",
    "apply_collage_layout",
    "collage_boards",
    "collage_painter_payload",
    "create_collage_board",
    "find_collage_board",
    "find_collage_item",
    "preflight_collage",
    "reorder_collage_item",
    "replace_collage_item_source",
    "set_collage_attachment",
    "set_collage_edge",
    "set_collage_painter_link",
    "set_collage_scan_cleanup",
    "update_collage_item",
]
