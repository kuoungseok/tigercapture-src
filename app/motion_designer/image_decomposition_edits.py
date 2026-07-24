"""Non-destructive edits for cached layered-image decomposition manifests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from .image_decomposition import (
    DecomposedImageElement,
    ImageDecompositionResult,
    _fit_rgba_canvas,
    _save_mask,
    _save_rgba,
)


def _normalized_result(
    value: ImageDecompositionResult | Mapping[str, Any],
) -> ImageDecompositionResult:
    return (
        value
        if isinstance(value, ImageDecompositionResult)
        else ImageDecompositionResult.from_dict(value)
    )


def _edit_target(
    result: ImageDecompositionResult,
    operation: Mapping[str, Any],
) -> Path:
    payload = json.dumps(operation, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(
        f"{result.source_hash}|{payload}".encode("utf-8")
    ).hexdigest()[:20]
    background = Path(result.background_path)
    root = background.parent if background.parent.is_dir() else Path.cwd()
    target = root / "edits" / digest
    target.mkdir(parents=True, exist_ok=True)
    return target


def _clone_result(result: ImageDecompositionResult) -> ImageDecompositionResult:
    return ImageDecompositionResult.from_dict(result.to_dict())


def _refresh_graph_and_validation(
    result: ImageDecompositionResult,
    *,
    operation: Mapping[str, Any],
    target: Path,
) -> ImageDecompositionResult:
    from .layer_graph import build_layer_graph

    graph = build_layer_graph(
        result.elements,
        width=result.width,
        height=result.height,
    )
    graph_by_id = graph.by_id()
    for element in result.elements:
        node = graph_by_id.get(element.id)
        if node is None:
            continue
        # Explicit edit values win over automatic graph suggestions.
        element.metadata.setdefault("parent_id", node.parent_id)
        element.metadata.setdefault("motion_group_id", node.motion_group_id)
        element.metadata.setdefault("rigid", node.rigid)
        element.metadata["pivot"] = [float(node.pivot[0]), float(node.pivot[1])]
        element.metadata["z_order"] = int(node.z_order)
    result.diagnostics = {
        **dict(result.diagnostics),
        "cache_hit": False,
        "edited": True,
        "edit_operation": dict(operation),
        "layer_graph": graph.to_dict(),
    }
    from .image_motion_validation import validate_decomposition_result

    validation = validate_decomposition_result(result)
    result.diagnostics["validation"] = validation.to_dict()
    result.diagnostics["warnings"] = list(dict.fromkeys([
        *[str(item) for item in result.diagnostics.get("warnings", [])],
        *validation.warnings,
        *[f"Validation error: {item}" for item in validation.errors],
    ]))
    (target / "manifest.json").write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def merge_decomposition_elements(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_ids: Iterable[str],
) -> ImageDecompositionResult:
    from .mask_integrity import analyze_mask_integrity, merge_masks, motion_lock_required
    from PIL import Image
    import numpy as np

    result = _clone_result(_normalized_result(value))
    requested = {str(item) for item in element_ids if str(item)}
    selected = [
        item for item in result.elements
        if item.id in requested and item.role != "text" and item.mask_path
    ]
    if len(selected) < 2:
        raise ValueError("merge requires at least two visual decomposition elements")
    operation = {"kind": "merge", "element_ids": sorted(requested)}
    target = _edit_target(result, operation)
    masks = [
        np.asarray(Image.open(item.mask_path).convert("L"), dtype=np.uint8)
        for item in selected
    ]
    merged_mask = merge_masks(masks)
    rgb, _ = _fit_rgba_canvas(
        Path(result.source_path),
        result.width,
        result.height,
    )
    new_id = f"merged_{hashlib.sha256('|'.join(sorted(requested)).encode('utf-8')).hexdigest()[:10]}"
    rgba_path = target / f"{new_id}.png"
    mask_path = target / f"{new_id}_mask.png"
    _save_rgba(rgba_path, rgb, merged_mask)
    _save_mask(mask_path, merged_mask)
    integrity = analyze_mask_integrity(merged_mask)
    primary = next((item for item in selected if item.role == "primary_subject"), None)
    role = "primary_subject" if primary is not None else "secondary_element"
    locked, reason = motion_lock_required(integrity, role=role)
    depth_weight = sum(max(0.0001, item.area_ratio) for item in selected)
    depth = sum(item.depth * max(0.0001, item.area_ratio) for item in selected) / depth_weight
    confidence = min(item.confidence for item in selected)
    merged = DecomposedImageElement(
        id=new_id,
        role=role,
        label="Merged Subject" if role == "primary_subject" else "Merged Element",
        bbox=integrity.bbox,
        rgba_path=str(rgba_path.resolve()),
        mask_path=str(mask_path.resolve()),
        area_ratio=integrity.area_ratio,
        depth=depth,
        confidence=confidence,
        motion_hint="hero_parallax" if role == "primary_subject" else "staggered_parallax",
        metadata={
            "merged_from": sorted(requested),
            "mask_integrity": integrity.to_dict(),
            "mask_fill_ratio": integrity.mask_fill_ratio,
            "motion_lock_to_background": locked,
            "motion_lock_reason": reason,
            "rigid": role == "primary_subject" or locked,
        },
    )
    first_index = min(result.elements.index(item) for item in selected)
    result.elements = [
        item for item in result.elements if item.id not in requested
    ]
    result.elements.insert(first_index, merged)
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=target,
    )


def split_decomposition_element(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_id: str,
    *,
    axis: str,
    position: float,
) -> ImageDecompositionResult:
    from .mask_integrity import analyze_mask_integrity, motion_lock_required, split_mask
    from PIL import Image
    import numpy as np

    result = _clone_result(_normalized_result(value))
    source_element = next(
        (
            item for item in result.elements
            if item.id == str(element_id) and item.role != "text" and item.mask_path
        ),
        None,
    )
    if source_element is None:
        raise ValueError(f"visual decomposition element not found: {element_id}")
    operation = {
        "kind": "split",
        "element_id": str(element_id),
        "axis": str(axis),
        "position": float(position),
    }
    target = _edit_target(result, operation)
    source_mask = np.asarray(
        Image.open(source_element.mask_path).convert("L"),
        dtype=np.uint8,
    )
    masks = split_mask(source_mask, axis=axis, position=position)
    rgb, _ = _fit_rgba_canvas(
        Path(result.source_path),
        result.width,
        result.height,
    )
    replacements: list[DecomposedImageElement] = []
    for index, mask in enumerate(masks, 1):
        integrity = analyze_mask_integrity(mask)
        if integrity.area <= 0:
            continue
        new_id = f"{source_element.id}_part_{index}"
        rgba_path = target / f"{new_id}.png"
        mask_path = target / f"{new_id}_mask.png"
        _save_rgba(rgba_path, rgb, mask)
        _save_mask(mask_path, mask)
        role = source_element.role if index == 1 else "secondary_element"
        locked, reason = motion_lock_required(integrity, role=role)
        replacements.append(DecomposedImageElement(
            id=new_id,
            role=role,
            label=f"{source_element.label} Part {index}",
            bbox=integrity.bbox,
            rgba_path=str(rgba_path.resolve()),
            mask_path=str(mask_path.resolve()),
            area_ratio=integrity.area_ratio,
            depth=source_element.depth,
            confidence=source_element.confidence,
            motion_hint=source_element.motion_hint,
            metadata={
                **dict(source_element.metadata),
                "split_from": source_element.id,
                "mask_integrity": integrity.to_dict(),
                "mask_fill_ratio": integrity.mask_fill_ratio,
                "motion_lock_to_background": locked,
                "motion_lock_reason": reason,
            },
        ))
    if len(replacements) < 2:
        raise ValueError("split did not create two non-empty masks")
    source_index = result.elements.index(source_element)
    result.elements.pop(source_index)
    for replacement in reversed(replacements):
        result.elements.insert(source_index, replacement)
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=target,
    )


def set_decomposition_lock(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_ids: Iterable[str],
    *,
    locked: bool,
) -> ImageDecompositionResult:
    result = _clone_result(_normalized_result(value))
    requested = {str(item) for item in element_ids if str(item)}
    changed = 0
    for element in result.elements:
        if element.id not in requested or element.role == "text":
            continue
        element.metadata["motion_lock_to_background"] = bool(locked)
        element.metadata["motion_lock_reason"] = "user_locked" if locked else ""
        element.metadata["rigid"] = bool(locked) or element.role == "primary_subject"
        changed += 1
    if changed == 0:
        raise ValueError("no matching visual decomposition elements were found")
    operation = {
        "kind": "lock",
        "element_ids": sorted(requested),
        "locked": bool(locked),
    }
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=_edit_target(result, operation),
    )


def replace_decomposition_element_mask(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_id: str,
    mask_source: str | Path,
) -> ImageDecompositionResult:
    from .mask_integrity import analyze_mask_integrity, motion_lock_required
    from PIL import Image
    import numpy as np

    result = _clone_result(_normalized_result(value))
    element = next(
        (
            item
            for item in result.elements
            if item.id == str(element_id)
            and item.role != "text"
            and item.mask_path
        ),
        None,
    )
    if element is None:
        raise ValueError(f"visual decomposition element not found: {element_id}")
    source = Path(mask_source).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"replacement mask not found: {source}")
    mask_image = Image.open(source).convert("L")
    if mask_image.size != (result.width, result.height):
        mask_image = mask_image.resize(
            (result.width, result.height),
            Image.Resampling.NEAREST,
        )
    mask = np.asarray(mask_image, dtype=np.uint8)
    mask = np.where(mask >= 128, 255, 0).astype(np.uint8)
    integrity = analyze_mask_integrity(mask)
    if integrity.area <= 0:
        raise ValueError("replacement mask cannot be empty")
    operation = {
        "kind": "replace_mask",
        "element_id": element.id,
        "source_name": source.name,
    }
    target = _edit_target(result, operation)
    rgb, _ = _fit_rgba_canvas(
        Path(result.source_path),
        result.width,
        result.height,
    )
    rgba_path = target / f"{element.id}.png"
    mask_path = target / f"{element.id}_mask.png"
    _save_rgba(rgba_path, rgb, mask)
    _save_mask(mask_path, mask)
    locked, reason = motion_lock_required(integrity, role=element.role)
    element.rgba_path = str(rgba_path.resolve())
    element.mask_path = str(mask_path.resolve())
    element.bbox = integrity.bbox
    element.area_ratio = integrity.area_ratio
    element.metadata = {
        **dict(element.metadata),
        "mask_integrity": integrity.to_dict(),
        "mask_fill_ratio": integrity.mask_fill_ratio,
        "motion_lock_to_background": locked,
        "motion_lock_reason": reason,
        "manual_mask_revision": True,
    }
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=target,
    )


def replace_decomposition_element_mask(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_id: str,
    mask_source: str | Path,
) -> ImageDecompositionResult:
    from .mask_integrity import analyze_mask_integrity, motion_lock_required
    from PIL import Image
    import numpy as np

    result = _clone_result(_normalized_result(value))
    element = next(
        (
            item
            for item in result.elements
            if item.id == str(element_id)
            and item.role != "text"
            and item.mask_path
        ),
        None,
    )
    if element is None:
        raise ValueError(f"visual decomposition element not found: {element_id}")
    source = Path(mask_source).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"replacement mask not found: {source}")
    mask_image = Image.open(source).convert("L")
    if mask_image.size != (result.width, result.height):
        mask_image = mask_image.resize(
            (result.width, result.height),
            Image.Resampling.NEAREST,
        )
    mask = np.asarray(mask_image, dtype=np.uint8)
    mask = np.where(mask >= 128, 255, 0).astype(np.uint8)
    integrity = analyze_mask_integrity(mask)
    if integrity.area <= 0:
        raise ValueError("replacement mask cannot be empty")
    operation = {
        "kind": "replace_mask",
        "element_id": element.id,
        "source_name": source.name,
    }
    target = _edit_target(result, operation)
    rgb, _ = _fit_rgba_canvas(
        Path(result.source_path),
        result.width,
        result.height,
    )
    rgba_path = target / f"{element.id}.png"
    mask_path = target / f"{element.id}_mask.png"
    _save_rgba(rgba_path, rgb, mask)
    _save_mask(mask_path, mask)
    locked, reason = motion_lock_required(integrity, role=element.role)
    element.rgba_path = str(rgba_path.resolve())
    element.mask_path = str(mask_path.resolve())
    element.bbox = integrity.bbox
    element.area_ratio = integrity.area_ratio
    element.metadata = {
        **dict(element.metadata),
        "mask_integrity": integrity.to_dict(),
        "mask_fill_ratio": integrity.mask_fill_ratio,
        "motion_lock_to_background": locked,
        "motion_lock_reason": reason,
        "manual_mask_revision": True,
    }
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=target,
    )


def set_decomposition_parent(
    value: ImageDecompositionResult | Mapping[str, Any],
    child_ids: Iterable[str],
    *,
    parent_id: str,
) -> ImageDecompositionResult:
    from .layer_graph import build_layer_graph, validate_layer_graph

    result = _clone_result(_normalized_result(value))
    requested = {str(item) for item in child_ids if str(item)}
    parent_id = str(parent_id or "")
    ids = {item.id for item in result.elements}
    if parent_id and parent_id not in ids:
        raise ValueError(f"decomposition parent element not found: {parent_id}")
    changed = 0
    for element in result.elements:
        if element.id not in requested:
            continue
        if element.id == parent_id:
            raise ValueError("an element cannot be parented to itself")
        element.metadata["parent_id"] = parent_id
        element.metadata["motion_group_id"] = (
            f"group_{parent_id}" if parent_id else f"group_{element.id}"
        )
        element.metadata["rigid"] = bool(parent_id)
        changed += 1
    if changed == 0:
        raise ValueError("no matching decomposition children were found")
    operation = {
        "kind": "parent",
        "child_ids": sorted(requested),
        "parent_id": parent_id,
    }
    graph_warnings = validate_layer_graph(
        build_layer_graph(
            result.elements,
            width=result.width,
            height=result.height,
        )
    )
    if any("cycle" in item.casefold() for item in graph_warnings):
        raise ValueError("decomposition parent edit would create a cycle")
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=_edit_target(result, operation),
    )


def set_decomposition_pivot(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_id: str,
    *,
    pivot: Iterable[float],
) -> ImageDecompositionResult:
    result = _clone_result(_normalized_result(value))
    values = list(pivot)
    if len(values) < 2:
        raise ValueError("pivot requires x and y")
    element = next(
        (item for item in result.elements if item.id == str(element_id)),
        None,
    )
    if element is None:
        raise ValueError(f"decomposition element not found: {element_id}")
    element.metadata["pivot"] = [
        max(0.0, min(float(result.width), float(values[0]))),
        max(0.0, min(float(result.height), float(values[1]))),
    ]
    operation = {
        "kind": "pivot",
        "element_id": element.id,
        "pivot": list(element.metadata["pivot"]),
    }
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=_edit_target(result, operation),
    )


def set_decomposition_z_order(
    value: ImageDecompositionResult | Mapping[str, Any],
    element_id: str,
    *,
    z_order: int,
) -> ImageDecompositionResult:
    result = _clone_result(_normalized_result(value))
    element = next(
        (item for item in result.elements if item.id == str(element_id)),
        None,
    )
    if element is None:
        raise ValueError(f"decomposition element not found: {element_id}")
    element.metadata["z_order"] = int(z_order)
    operation = {
        "kind": "z_order",
        "element_id": element.id,
        "z_order": int(z_order),
    }
    return _refresh_graph_and_validation(
        result,
        operation=operation,
        target=_edit_target(result, operation),
    )


__all__ = [
    "merge_decomposition_elements",
    "replace_decomposition_element_mask",
    "replace_decomposition_element_mask",
    "set_decomposition_lock",
    "set_decomposition_parent",
    "set_decomposition_pivot",
    "set_decomposition_z_order",
    "split_decomposition_element",
]
